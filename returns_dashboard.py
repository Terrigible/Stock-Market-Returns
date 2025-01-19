import json
from functools import cache, reduce
from glob import glob
from io import StringIO
from itertools import cycle

import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import polars as pl
import yfinance as yf
from dash import Dash, ctx, no_update
from dash.dependencies import Input, Output, State
from plotly.colors import DEFAULT_PLOTLY_COLORS

from funcs.calcs_numpy import (
    calculate_dca_portfolio_value_with_fees_and_interest_vector,
    calculate_lumpsum_portfolio_value_with_fees_and_interest_vector,
    calculate_withdrawal_portfolio_value_with_fees_vector,
)
from funcs.loaders import (
    load_fed_funds_rate,
    load_fred_usd_fx,
    load_mas_sgd_fx,
    load_sg_cpi,
    load_sgd_interest_rates,
    load_sgs_returns,
    load_us_cpi,
    load_us_treasury_returns,
    load_usdsgd,
    read_ft_data,
    read_greatlink_data,
    read_msci_data,
    read_shiller_sp500_data,
)
from layout import app_layout


def resample_bme(series: pd.Series):
    df = (
        series.rename("price")
        .to_frame()
        .assign(date=series.index)
        .resample("BME")
        .last()
    )
    new_index = df.index[:-1].union([df["date"].iloc[-1]])
    return df["price"].set_axis(new_index)


def convert_price_to_usd(
    series: pd.Series,
    currency: str,
    usd_sgd: pd.Series = load_usdsgd(),
    usd_fx: pd.DataFrame = load_fred_usd_fx(),
    sgd_fx: pd.DataFrame = load_mas_sgd_fx(),
):
    if currency == "USD":
        return series
    if currency == "SGD":
        return series.div(usd_sgd.resample("D").ffill().ffill().reindex(series.index))
    if currency == "GBp":
        series = series.div(100)
        currency = "GBP"
    if currency in usd_fx.columns:
        return series.mul(
            usd_fx[currency].resample("D").ffill().ffill().reindex(series.index)
        )
    if currency in sgd_fx.columns:
        return series.mul(
            sgd_fx[currency].resample("D").ffill().ffill().reindex(series.index)
        ).div(usd_sgd.resample("D").ffill().ffill().reindex(series.index))
    return series


@cache
def load_data(
    security_str: str,
    interval: str,
    currency: str,
    adjust_for_inflation: str,
    yf_security: str | None,
):
    security: dict[str, str] = json.loads(security_str)
    source = security["source"]
    if source == "MSCI":
        series = read_msci_data(
            f"data/MSCI/{security['msci_base_index']}/{security['msci_size']}/{security['msci_style']}/*{security['msci_tax_treatment']} {interval}*.xls"
        ).iloc[:, 0]
    elif source == "FRED":
        if security["fred_index"] == "US-T":
            series = load_us_treasury_returns()[security["us_treasury_duration"]]
            if interval == "Monthly":
                series = series.pipe(resample_bme)
        else:
            raise ValueError(f"Invalid index: {security}")
    elif source == "MAS":
        if security["mas_index"] == "SGS":
            series = load_sgs_returns()[security["sgs_duration"]]
            series = series.div(
                load_usdsgd().resample("D").ffill().ffill().reindex(series.index)
            )
            if interval == "Monthly":
                series = series.pipe(resample_bme)
        else:
            raise ValueError(f"Invalid index: {security}")
    elif source == "Others":
        if security["others_index"] == "STI":
            series = read_ft_data("Straits Times Index USD Gross").iloc[:, 0]
        elif security["others_index"] == "SPX":
            series = read_ft_data(
                f"S&P 500 USD {security['others_tax_treatment']}"
            ).iloc[:, 0]
            if interval == "Daily":
                series = series.resample("B").interpolate("linear")
        elif security["others_index"] == "SHILLER_SPX":
            series = read_shiller_sp500_data(security["others_tax_treatment"]).iloc[
                :, 0
            ]
            if interval == "Daily":
                series = series.resample("B").interpolate("linear")
        elif security["others_index"] == "AWORLDS":
            series = read_ft_data("FTSE All-World USD Gross").iloc[:, 0]
        elif security["others_index"] == "SREIT":
            series = read_ft_data("iEdge S-REIT Leaders SGD Gross").iloc[:, 0]
            series = convert_price_to_usd(series, "SGD")
        else:
            raise ValueError(f"Invalid index: {security}")
        if interval == "Monthly":
            series = series.pipe(resample_bme)
    elif source == "YF":
        ticker_currency = security["currency"]
        series = pd.read_json(StringIO(yf_security), orient="index", typ="series")
        series = convert_price_to_usd(series, ticker_currency)
        if interval == "Monthly":
            series = series.pipe(resample_bme)
    elif source == "Fund":
        fund_company = security["fund_company"]
        fund = security["fund"]
        fund_currency = security["currency"]
        if fund_company == "Great Eastern":
            series = read_greatlink_data(fund).iloc[:, 0]
        elif fund_company == "GMO":
            series = read_ft_data("GMO Quality Investment Fund").iloc[:, 0]
        elif fund_company == "Fundsmith":
            series = read_ft_data(
                f"Fundsmith {fund.replace('Class ', '')} EUR Acc"
            ).iloc[:, 0]
        elif fund_company == "Dimensional":
            series = read_ft_data(f"Dimensional {fund} GBP Accumulation").iloc[:, 0]
        else:
            raise ValueError(f"Invalid fund: {fund}")
        series = convert_price_to_usd(series, fund_currency)
        if interval == "Monthly":
            series = series.pipe(resample_bme)
    else:
        raise ValueError(f"Invalid index: {security}")
    if currency == "USD":
        if adjust_for_inflation == "Yes":
            series = series.div(
                load_us_cpi()
                .iloc[:, 0]
                .resample("D")
                .interpolate("pchip")
                .ffill()
                .reindex(series.index)
            )
    elif currency == "SGD":
        series = series.mul(
            load_usdsgd().resample("D").ffill().ffill().reindex(series.index)
        )
        if adjust_for_inflation == "Yes":
            series = series.div(
                load_sg_cpi()
                .iloc[:, 0]
                .resample("D")
                .interpolate("pchip")
                .ffill()
                .reindex(series.index)
            )
    return series.rename_axis("date").rename("price")


def transform_data(
    series: pd.Series,
    interval: str,
    y_var: str,
    return_duration: str,
    return_interval: str,
    return_type: str,
) -> pd.Series:
    if y_var == "price":
        return series
    if y_var == "drawdown":
        return series.div(series.cummax()).sub(1)
    return_durations = {
        "1mo": 1,
        "3mo": 3,
        "6mo": 6,
        "1y": 12,
        "2y": 24,
        "3y": 36,
        "5y": 60,
        "10y": 120,
        "15y": 180,
        "20y": 240,
        "25y": 300,
        "30y": 360,
    }
    if y_var == "rolling_returns":
        if interval == "Monthly":
            series = series.pct_change(return_durations[return_duration])
        elif interval == "Daily":
            series = series.div(
                series.reindex(
                    (
                        series.index
                        - pd.offsets.DateOffset(
                            months=return_durations[return_duration]
                        )
                        + pd.offsets.Day(1)
                        - pd.offsets.BDay(1)
                    )
                ).set_axis(series.index, axis=0)
            ).sub(1)
        else:
            raise ValueError("Invalid interval")
        if return_type == "annualized":
            series = series.add(1).pow(12 / return_durations[return_duration]).sub(1)
        return series.dropna()
    if y_var == "calendar_returns":
        df_pl = pl.from_pandas(series.reset_index())
        df_pl = (
            df_pl.set_sorted("date")
            .group_by_dynamic("date", every=return_interval)
            .agg(
                pl.col("date").last().alias("date_end"),
                pl.col("price").last(),
            )
            .select(
                pl.col("date_end").alias("date"),
                pl.col("price").pct_change().alias("return"),
            )
            .drop_nulls()
        )
        df = df_pl.to_pandas().set_index("date").loc[:, "return"]
        return df
    raise ValueError("Invalid y_var")


def load_df(
    security_str: str,
    interval: str,
    currency: str,
    adjust_for_inflation: str,
    yf_security: str | None,
    y_var: str,
    return_duration: str,
    return_interval: str,
    return_type: str,
) -> pd.Series:
    series = load_data(
        security_str,
        "Monthly" if y_var == "calendar_returns" else interval,
        currency,
        adjust_for_inflation,
        yf_security,
    )
    return transform_data(
        series,
        interval,
        y_var,
        return_duration,
        return_interval,
        return_type,
    )


app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])

server = app.server

app.layout = app_layout


@app.callback(
    Output("index-selection-container", "style"),
    Output("stock-etf-selection-container", "style"),
    Output("fund-selection-container", "style"),
    Input("security-type-selection", "value"),
    Input("security-type-selection", "options"),
)
def update_index_selection_visibility(
    security_type: str, security_type_options: list[str]
):
    return tuple(
        {"display": "block"}
        if security_type == security_type_option
        else {"display": "none"}
        for security_type_option in security_type_options
    )


@app.callback(
    Output("msci-index-selection-container", "style"),
    Output("fred-index-selection-container", "style"),
    Output("mas-index-selection-container", "style"),
    Output("others-index-selection-container", "style"),
    Input("index-provider-selection", "value"),
    Input("index-provider-selection", "options"),
)
def update_msci_index_selection_visibility(
    index_provider: str, index_provider_options: dict[str, str]
):
    return tuple(
        {"display": "block"}
        if index_provider == index_provider_option
        else {"display": "none"}
        for index_provider_option in index_provider_options
    )


@app.callback(
    Output("msci-index-selection", "options"),
    Output("msci-index-selection", "value"),
    Input("msci-index-type-selection", "value"),
)
def update_msci_index_options(index_type: str):
    if index_type == "Regional":
        return {
            "WORLD": "World",
            "ACWI": "ACWI",
            "EM (EMERGING MARKETS)": "Emerging Markets",
            "WORLD ex USA": "World ex USA",
            "KOKUSAI INDEX (WORLD ex JP)": "World ex Japan",
            "EUROPE": "Europe",
        }, "WORLD"
    if index_type == "Country":
        return {
            "AUSTRALIA": "Australia",
            "AUSTRIA": "Austria",
            "BELGIUM": "Belgium",
            "CANADA": "Canada",
            "DENMARK": "Denmark",
            "FINLAND": "Finland",
            "FRANCE": "France",
            "GERMANY": "Germany",
            "HONG KONG": "Hong Kong",
            "IRELAND": "Ireland",
            "ISRAEL": "Israel",
            "ITALY": "Italy",
            "JAPAN": "Japan",
            "NETHERLANDS": "Netherlands",
            "NEW ZEALAND": "New Zealand",
            "NORWAY": "Norway",
            "PORTUGAL": "Portugal",
            "SINGAPORE": "Singapore",
            "SPAIN": "Spain",
            "SWEDEN": "Sweden",
            "SWITZERLAND": "Switzerland",
            "UNITED KINGDOM": "United Kingdom",
            "USA": "USA",
        }, "AUSTRALIA"


@app.callback(
    Output("others-tax-treatment-selection-container", "style"),
    Input("others-index-selection", "value"),
)
def update_others_tax_treatment_selection_visibility(others_index: str):
    if others_index in ["STI", "AWORLDS", "SREIT"]:
        return {"display": "none"}
    else:
        return {"display": "block"}


@app.callback(
    Output("index-toast", "is_open"),
    Output("selected-securities", "value"),
    Output("selected-securities", "options"),
    Input("add-index-button", "n_clicks"),
    State("selected-securities", "value"),
    State("selected-securities", "options"),
    State("index-provider-selection", "value"),
    State("index-provider-selection", "options"),
    State("msci-index-selection", "value"),
    State("msci-index-selection", "options"),
    State("msci-size-selection", "value"),
    State("msci-size-selection", "options"),
    State("msci-style-selection", "value"),
    State("msci-style-selection", "options"),
    State("msci-tax-treatment-selection", "value"),
    State("fred-index-selection", "value"),
    State("fred-index-selection", "options"),
    State("us-treasury-duration-selection", "value"),
    State("us-treasury-duration-selection", "options"),
    State("mas-index-selection", "value"),
    State("mas-index-selection", "options"),
    State("sgs-duration-selection", "value"),
    State("sgs-duration-selection", "options"),
    State("others-index-selection", "value"),
    State("others-index-selection", "options"),
    State("others-tax-treatment-selection", "value"),
)
def add_index(
    _,
    selected_securities: None | list[str],
    selected_securities_options: dict[str, str],
    index_provider: str,
    index_provider_options: dict[str, str],
    msci_base_index: str,
    msci_base_index_options: dict[str, str],
    msci_size: str,
    msci_size_options: dict[str, str],
    msci_style: str,
    msci_style_options: dict[str, str],
    msci_tax_treatment: str,
    fred_index: str,
    fred_index_options: dict[str, str],
    us_treasury_duration: str,
    us_treasury_duration_options: dict[str, str],
    mas_index: str,
    mas_index_options: dict[str, str],
    sgs_duration: str,
    sgs_duration_options: dict[str, str],
    others_index: str,
    others_index_options: dict[str, str],
    others_tax_treatment: str,
):
    if index_provider == "MSCI":
        if not glob(
            f"data/{index_provider}/{msci_base_index}/{msci_size}/{msci_style}/* {msci_tax_treatment}*.xls"
        ):
            return True, no_update, no_update
        index = (
            json.dumps(
                {
                    "source": "MSCI",
                    "msci_base_index": msci_base_index,
                    "msci_size": msci_size,
                    "msci_style": msci_style,
                    "msci_tax_treatment": msci_tax_treatment,
                }
            ),
            " ".join(
                filter(
                    None,
                    [
                        index_provider_options[index_provider],
                        msci_base_index_options[msci_base_index],
                        (
                            None
                            if msci_size == "STANDARD"
                            else msci_size_options[msci_size]
                        ),
                        (
                            "Cap"
                            if msci_size in ["SMALL", "SMID", "MID", "LARGE"]
                            and msci_style == "BLEND"
                            else None
                        ),
                        (
                            None
                            if msci_style == "BLEND"
                            else msci_style_options[msci_style]
                        ),
                        msci_tax_treatment,
                    ],
                )
            ),
        )
    elif index_provider == "FRED":
        if fred_index == "US-T":
            index = (
                json.dumps(
                    {
                        "source": "FRED",
                        "fred_index": fred_index,
                        "us_treasury_duration": us_treasury_duration,
                    }
                ),
                f"{us_treasury_duration_options[us_treasury_duration]} {fred_index_options[fred_index]}",
            )
        else:
            return True, no_update, no_update
    elif index_provider == "MAS":
        if mas_index == "SGS":
            index = (
                json.dumps(
                    {
                        "source": "MAS",
                        "mas_index": mas_index,
                        "sgs_duration": sgs_duration,
                    }
                ),
                f"{sgs_duration_options[sgs_duration]} {mas_index_options[mas_index]}",
            )
        else:
            return True, no_update, no_update
    else:
        others_tax_treatment = (
            "Gross"
            if others_index in ["STI", "AWORLDS", "SREIT"]
            else others_tax_treatment
        )
        index = (
            json.dumps(
                {
                    "source": "Others",
                    "others_index": others_index,
                    "others_tax_treatment": others_tax_treatment,
                }
            ),
            f"{others_index_options[others_index]} {others_tax_treatment}",
        )
    if selected_securities is None:
        return False, [index[0]], {index[0]: index[1]}
    if index[0] in selected_securities:
        return no_update
    selected_securities.append(index[0])
    selected_securities_options.update({index[0]: index[1]})
    return False, selected_securities, selected_securities_options


@app.callback(
    Output("stock-etf-toast", "children"),
    Output("stock-etf-toast", "is_open"),
    Output("selected-securities", "value", allow_duplicate=True),
    Output("selected-securities", "options", allow_duplicate=True),
    Output("yf-invalid-securities-store", "data"),
    Output("yf-securities-store", "data"),
    Input("add-stock-etf-button", "n_clicks"),
    State("selected-securities", "value"),
    State("selected-securities", "options"),
    State("stock-etf-input", "value"),
    State("stock-etf-tax-treatment-selection", "value"),
    State("yf-invalid-securities-store", "data"),
    State("yf-securities-store", "data"),
    prevent_initial_call=True,
)
def add_stock_etf(
    _,
    selected_securities: list[str],
    selected_securities_options: dict[str, str],
    stock_etf: str | None,
    tax_treatment: str,
    yf_invalid_securities_store: list[str],
    yf_securities_store: dict[str, str],
):
    if not stock_etf:
        return no_update
    if ";" in stock_etf:
        return "Invalid character: ;", True, no_update, no_update, no_update, no_update
    if stock_etf in yf_invalid_securities_store:
        return (
            "The selected ticker is not available",
            True,
            no_update,
            no_update,
            no_update,
            no_update,
        )
    for yf_security_str in yf_securities_store:
        yf_security = json.loads(yf_security_str)
        if stock_etf != yf_security["ticker"]:
            continue
        if tax_treatment != yf_security["tax_treatment"]:
            continue
        if yf_security_str in selected_securities:
            return no_update
        if yf_security_str in selected_securities_options:
            selected_securities.append(yf_security_str)
            return (
                no_update,
                no_update,
                selected_securities,
                selected_securities_options,
                no_update,
                yf_securities_store,
            )
    ticker = yf.Ticker(stock_etf)
    if ticker.history_metadata == {}:
        yf_invalid_securities_store.append(stock_etf)
        return (
            "The selected ticker is not available",
            True,
            no_update,
            no_update,
            yf_invalid_securities_store,
            no_update,
        )
    ticker_symbol = ticker.ticker
    if "currency" not in ticker.history_metadata:
        currency = "USD"
        toast = (
            "The selected ticker does not have currency information. Defaulting to USD."
        )
        show_toast = True
    else:
        currency = ticker.history_metadata["currency"]
        toast = no_update
        show_toast = no_update
    new_yf_security = json.dumps(
        {
            "source": "YF",
            "ticker": ticker_symbol,
            "currency": currency,
            "tax_treatment": tax_treatment,
        }
    )
    selected_securities.append(new_yf_security)
    selected_securities_options[new_yf_security] = f"{ticker_symbol} {tax_treatment}"

    df = ticker.history(period="max", auto_adjust=False)
    df = df.set_index(df.index.tz_localize(None))
    if tax_treatment == "Net" and "Dividends" in df.columns:
        manually_adjusted = (
            df["Close"]
            .add(df["Dividends"].mul(0.7))
            .div(df["Close"].shift(1))
            .fillna(1)
            .cumprod()
        )
        manually_adjusted = manually_adjusted.div(manually_adjusted.iloc[-1]).mul(
            df["Adj Close"].iloc[-1]
        )
        df["Adj Close"] = manually_adjusted
    yf_securities_store[new_yf_security] = df["Adj Close"].to_json(orient="index")

    return (
        toast,
        show_toast,
        selected_securities,
        selected_securities_options,
        no_update,
        yf_securities_store,
    )


@app.callback(
    Output("fund-selection", "options"),
    Output("fund-selection", "value"),
    Input("fund-company-selection", "value"),
)
def update_fund_selection_options(fund_company: str):
    if fund_company == "Great Eastern":
        return (
            [
                "Great Eastern-Lion Dynamic Balanced",
                "Great Eastern-Lion Dynamic Growth",
                "GreatLink ASEAN Growth",
                "GreatLink Asia Dividend Advantage",
                "GreatLink Asia High Dividend Equity",
                "GreatLink Asia Pacific Equity",
                "GreatLink Cash",
                "GreatLink China Growth",
                "GreatLink Diversified Growth Portfolio",
                "GreatLink European Sustainable Equity Fund",
                "GreatLink Far East Ex Japan Equities",
                "GreatLink Global Bond",
                "GreatLink Global Disruptive Innovation Fund",
                "GreatLink Global Emerging Markets Equity",
                "GreatLink Global Equity Alpha",
                "GreatLink Global Equity",
                "GreatLink Global Optimum",
                "GreatLink Global Perspective",
                "GreatLink Global Real Estate Securities",
                "GreatLink Global Supreme",
                "GreatLink Global Technology",
                "GreatLink Income Bond",
                "GreatLink Income Focus",
                "GreatLink International Health Care Fund",
                "GreatLink LifeStyle Balanced Portfolio",
                "GreatLink LifeStyle Dynamic Portfolio",
                "GreatLink LifeStyle Progressive Portfolio",
                "GreatLink LifeStyle Secure Portfolio",
                "GreatLink LifeStyle Steady Portfolio",
                "GreatLink Lion Asian Balanced",
                "GreatLink Lion India",
                "GreatLink Lion Japan Growth",
                "GreatLink Lion Vietnam",
                "GreatLink Multi-Sector Income",
                "GreatLink Multi-Theme Equity",
                "GreatLink Short Duration Bond",
                "GreatLink Singapore Equities",
                "GreatLink Sustainable Global Thematic Fund",
                "GreatLink US Income and Growth Fund (Dis)",
            ],
            "Great Eastern-Lion Dynamic Balanced",
        )
    if fund_company == "GMO":
        return (
            [
                "Quality Investment Fund",
            ],
            "Quality Investment Fund",
        )
    if fund_company == "Fundsmith":
        return (
            [
                "Equity Fund Class T",
                "Equity Fund Class R",
            ],
            "Equity Fund Class T",
        )
    if fund_company == "Dimensional":
        return (["World Equity Fund"], "World Equity Fund")
    return (
        [],
        None,
    )


@app.callback(
    Output("selected-securities", "value", allow_duplicate=True),
    Output("selected-securities", "options", allow_duplicate=True),
    Input("add-fund-button", "n_clicks"),
    State("selected-securities", "value"),
    State("selected-securities", "options"),
    State("fund-company-selection", "value"),
    State("fund-selection", "value"),
    prevent_initial_call=True,
)
def add_fund(
    _,
    selected_securities: list[str],
    selected_securities_options: dict[str, str],
    fund_company: str,
    fund: str,
):
    if fund_company == "Great Eastern":
        currency = "SGD"
    elif fund_company == "GMO":
        currency = "USD"
    elif fund_company == "Fundsmith":
        currency = "EUR"
    elif fund_company == "Dimensional":
        currency = "GBP"
    else:
        return no_update
    security = (
        json.dumps(
            {
                "source": "Fund",
                "fund_company": fund_company,
                "fund": fund,
                "currency": currency,
            }
        ),
        f"{f'{fund_company} ' if fund_company != 'Great Eastern' else ''}{fund}",
    )
    if security[0] in selected_securities:
        return no_update
    selected_securities.append(security[0])
    selected_securities_options.update({security[0]: security[1]})
    return selected_securities, selected_securities_options


@app.callback(
    Output("log-scale-selection", "style"),
    Output("log-scale-selection", "value"),
    Input("y-var-selection", "value"),
    Input("log-scale-selection", "value"),
)
def update_log_scale(y_var: str, log_scale: list[str]):
    if y_var == "price":
        return {"display": "block"}, log_scale
    return {"display": "none"}, []


@app.callback(
    Output("rolling-return-selection-container", "style"),
    Output("calendar-return-selection-container", "style"),
    Input("y-var-selection", "value"),
)
def update_return_duration_visibility(y_var: str):
    if y_var == "rolling_returns":
        return {"display": "block"}, {"display": "none"}
    return {"display": "none"}, {"display": "block"}


@app.callback(Output("return-selection", "style"), Input("y-var-selection", "value"))
def update_return_selection_visibility(y_var: str):
    if y_var in ["rolling_returns", "calendar_returns"]:
        return {"display": "block"}
    return {"display": "none"}


@app.callback(
    Output("baseline-security-selection", "options"),
    Output("baseline-security-selection", "value"),
    Output("baseline-security-selection", "disabled"),
    Input("selected-securities", "value"),
    Input("selected-securities", "options"),
    Input("baseline-security-selection", "value"),
)
def update_baseline_security_selection_options(
    selected_securities: list[str],
    selected_securities_options: dict[str, str],
    baseline_security: str,
):
    return (
        {
            "None": "None",
            **{
                k: v
                for k, v in selected_securities_options.items()
                if k in selected_securities
            },
        },
        baseline_security
        if baseline_security in selected_securities and len(selected_securities) > 1
        else "None",
        len(selected_securities) <= 1,
    )


@app.callback(
    Output("graph", "figure"),
    Input("selected-securities", "value"),
    Input("selected-securities", "options"),
    Input("yf-securities-store", "data"),
    Input("currency-selection", "value"),
    Input("inflation-adjustment-selection", "value"),
    Input("y-var-selection", "value"),
    Input("return-duration-selection", "value"),
    Input("return-duration-selection", "options"),
    Input("return-interval-selection", "value"),
    Input("return-interval-selection", "options"),
    Input("return-type-selection", "value"),
    Input("return-type-selection", "options"),
    Input("interval-selection", "value"),
    Input("baseline-security-selection", "value"),
    Input("baseline-security-selection", "options"),
    Input("log-scale-selection", "value"),
    Input("chart-type-selection", "value"),
)
def update_graph(
    selected_securities: list[str],
    selected_securities_options: dict[str, str],
    yf_securities: dict[str, str],
    currency: str,
    adjust_for_inflation: str,
    y_var: str,
    return_duration: str,
    return_duration_options: dict[str, str],
    return_interval: str,
    return_interval_options: dict[str, str],
    return_type: str,
    return_type_options: dict[str, str],
    interval: str,
    baseline_security: str,
    baseline_security_options: dict[str, str],
    log_scale: list[str],
    chart_type: str,
):
    securities_colourmap = dict(
        zip(
            selected_securities_options.keys(),
            cycle(DEFAULT_PLOTLY_COLORS),
        )
    )
    df = pd.DataFrame(
        {
            selected_security: load_df(
                selected_security,
                interval,
                currency,
                adjust_for_inflation,
                yf_securities.get(selected_security),
                y_var,
                return_duration,
                return_interval,
                return_type,
            )
            for selected_security in selected_securities
        }
    )
    if y_var in ["rolling_returns", "calendar_returns"] and baseline_security != "None":
        non_baseline_securities = df.columns.difference([baseline_security])
        df = df.sub(df[baseline_security], axis=0, level=0).dropna(
            subset=non_baseline_securities, how="all"
        )
        if y_var == "calendar_returns":
            df = df.drop(columns=baseline_security)
    if y_var == "rolling_returns" and chart_type == "hist":
        data = list(
            filter(
                None,
                [
                    go.Histogram(
                        x=[None],
                        name=selected_securities_options[baseline_security],
                        marker=dict(color=securities_colourmap[baseline_security]),
                        histnorm="probability",
                        opacity=0.7,
                        showlegend=True,
                    )
                    if baseline_security != "None"
                    else None,
                    *[
                        go.Histogram(
                            x=df[column],
                            name=selected_securities_options[column],
                            marker=dict(color=securities_colourmap[column]),
                            histnorm="probability",
                            opacity=0.7,
                            showlegend=True,
                        )
                        for column in df.columns
                        if column != baseline_security
                    ],
                ],
            )
        )

    elif y_var == "calendar_returns":
        if return_interval == "1mo":
            index_offset = pd.offsets.BMonthEnd(0)
            xperiod = "M1"
            xtickformat = "%b %Y"
        elif return_interval == "3mo":
            index_offset = pd.offsets.BQuarterEnd(0)
            xperiod = "M3"
            xtickformat = "Q%q %Y"
        elif return_interval == "1y":
            index_offset = pd.offsets.BYearEnd(0)
            xperiod = "M12"
            xtickformat = "%Y"
        else:
            raise ValueError("Invalid return_interval")

        hovertext = df.index.to_series().apply(
            lambda x: x.strftime("As of %d %b %Y") if x != x + index_offset else ""
        )
        data = [
            go.Bar(
                x=df.index + index_offset,
                y=df[column],
                xperiod=xperiod,
                xperiodalignment="middle",
                name=selected_securities_options[column],
                hovertext=hovertext,
                marker=dict(color=securities_colourmap[column]),
            )
            for column in df.columns
            if column != baseline_security
        ]
    else:
        data = [
            go.Scatter(
                x=df.index,
                y=df[column],
                name=selected_securities_options[column],
                line=dict(color=securities_colourmap[column], dash="dash")
                if y_var == "rolling_returns" and column == baseline_security
                else dict(color=securities_colourmap[column]),
            )
            for column in df.columns
        ]

    if y_var == "rolling_returns" and chart_type == "hist":
        barmode = "overlay"
        shapes = [
            dict(
                type="line",
                x0=0,
                x1=0,
                y0=0,
                y1=1,
                yref="paper",
                line=dict(
                    color=securities_colourmap[baseline_security]
                    if baseline_security != "None"
                    else "grey",
                    width=1,
                    dash="dash",
                ),
                opacity=0.7,
            )
        ]
    elif y_var == "calendar_returns":
        barmode = "group"
        shapes = None
    else:
        barmode = None
        shapes = None

    if y_var == "price":
        title = "Price"
        ytickformat = ".2f"
    elif y_var == "drawdown":
        title = "Drawdown"
        ytickformat = ".2%"
    elif y_var == "rolling_returns":
        title = f"{return_duration_options[return_duration]} {return_type_options[return_type]} Rolling Returns"
        ytickformat = ".2%"
    elif y_var == "calendar_returns":
        title = f"{return_interval_options[return_interval]} Returns"
        ytickformat = ".2%"
    else:
        raise ValueError("Invalid y_var")
    if baseline_security != "None":
        title += f" vs {baseline_security_options[baseline_security]}"

    layout = go.Layout(
        title=title,
        hovermode="x",
        xaxis=(
            dict(
                ticklabelmode="period",
                tickformat=xtickformat,
            )
            if y_var == "calendar_returns"
            else None
        ),
        yaxis=dict(
            tickformat=ytickformat,
            type="log" if "log" in log_scale else "linear",
        ),
        barmode=barmode,
        showlegend=True,
        shapes=shapes,
    )
    return dict(data=data, layout=layout)


@app.callback(
    Output("portfolio-security-selection", "options"),
    Input("selected-securities", "options"),
)
def update_security_options(security_options: dict[str, str]):
    return security_options


@app.callback(
    Output("portfolio-allocations", "value"),
    Output("portfolio-allocations", "options"),
    Input("add-security-button", "n_clicks"),
    Input("portfolio-allocations", "value"),
    State("portfolio-allocations", "options"),
    State("portfolio-security-selection", "value"),
    State("portfolio-security-selection", "options"),
    State("security-weight", "value"),
    allow_duplicate=True,
)
def add_allocation(
    _,
    portfolio_allocation_strs: list[str] | None,
    portfolio_allocation_options: dict[str, str],
    security: str,
    security_options: dict[str, str],
    weight: float | int | None,
):
    trigger = ctx.triggered_id
    if trigger is None:
        return no_update
    if trigger == "add-security-button":
        if weight is None:
            return no_update
        new_allocation = json.dumps({security: weight})
        if not portfolio_allocation_strs:
            return [new_allocation], {
                new_allocation: f"{weight}% {security_options[security]}"
            }
        if new_allocation in portfolio_allocation_strs:
            return no_update
        portfolio_allocations: dict[str, int | float] = reduce(
            dict.__or__, map(json.loads, portfolio_allocation_strs)
        )
        if security in portfolio_allocations:
            old_weight = portfolio_allocations[security]
            portfolio_allocation_strs.remove(json.dumps({security: old_weight}))
            portfolio_allocation_options.pop(json.dumps({security: old_weight}))

        portfolio_allocation_strs.append(new_allocation)
        portfolio_allocation_options.update(
            {new_allocation: f"{weight}% {security_options[security]}"}
        )
        return portfolio_allocation_strs, portfolio_allocation_options
    if trigger == "portfolio-allocations":
        if portfolio_allocation_strs is None:
            raise ValueError("This should not happen")
        return portfolio_allocation_strs, {
            portfolio_allocation: portfolio_allocation_options[portfolio_allocation]
            for portfolio_allocation in portfolio_allocation_strs
        }
    return no_update


@app.callback(
    Output("portfolios", "value"),
    Output("portfolios", "options"),
    Input("add-portfolio-button", "n_clicks"),
    State("portfolios", "value"),
    State("portfolios", "options"),
    State("portfolio-allocations", "value"),
    State("portfolio-allocations", "options"),
    prevent_initial_call=True,
)
def add_portfolio(
    _,
    portfolio_strs: list[str] | None,
    portfolio_options: dict[str, str],
    portfolio_allocation_strs: list[str] | None,
    portfolio_allocations_options: dict[str, str],
):
    if not portfolio_allocation_strs:
        return no_update
    portfolio_allocations: dict[str, int | float] = reduce(
        dict.__or__, map(json.loads, portfolio_allocation_strs)
    )
    weights = portfolio_allocations.values()
    if sum(weights) != 100:
        return no_update
    portfolio_str = json.dumps(portfolio_allocation_strs)
    portfolio_title = ", ".join(
        portfolio_allocations_options[portfolio_allocation]
        for portfolio_allocation in portfolio_allocation_strs
    )
    if portfolio_strs is None:
        return [portfolio_str], {portfolio_str: portfolio_title}
    if portfolio_str in portfolio_strs:
        return no_update
    portfolio_strs.append(portfolio_str)
    portfolio_options.update({portfolio_str: portfolio_title})
    return portfolio_strs, portfolio_options


@app.callback(
    Output("portfolio-log-scale-selection", "style"),
    Output("portfolio-log-scale-selection", "value"),
    Input("portfolio-y-var-selection", "value"),
    Input("portfolio-log-scale-selection", "value"),
)
def update_portfolio_log_scale(y_var: str, log_scale: list[str]):
    if y_var == "price":
        return {"display": "block"}, log_scale
    return {"display": "none"}, []


@app.callback(
    Output("portfolio-rolling-return-selection-container", "style"),
    Output("portfolio-calendar-return-selection-container", "style"),
    Input("portfolio-y-var-selection", "value"),
)
def update_portfolio_return_duration_visibility(y_var: str):
    if y_var == "rolling_returns":
        return {"display": "block"}, {"display": "none"}
    return {"display": "none"}, {"display": "block"}


@app.callback(
    Output("portfolio-return-selection", "style"),
    Input("portfolio-y-var-selection", "value"),
)
def update_portfolio_return_selection_visibility(y_var: str):
    if y_var in ["rolling_returns", "calendar_returns"]:
        return {"display": "block"}
    return {"display": "none"}


@app.callback(
    Output("portfolio-baseline-security-selection", "options"),
    Output("portfolio-baseline-security-selection", "value"),
    Output("portfolio-baseline-security-selection", "disabled"),
    Input("portfolios", "value"),
    Input("portfolios", "options"),
    Input("portfolio-baseline-security-selection", "value"),
)
def update_portfolio_baseline_security_selection_options(
    selected_securities: list[str],
    selected_securities_options: dict[str, str],
    baseline_security: str,
):
    if not selected_securities:
        return {"None": "None"}, "None", True
    return (
        {
            "None": "None",
            **{
                k: v
                for k, v in selected_securities_options.items()
                if k in selected_securities
            },
        },
        baseline_security
        if baseline_security in selected_securities and len(selected_securities) > 1
        else "None",
        len(selected_securities) <= 1,
    )


@app.callback(
    Output("portfolio-graph", "figure"),
    Input("portfolios", "value"),
    State("portfolios", "options"),
    State("yf-securities-store", "data"),
    Input("portfolio-currency-selection", "value"),
    Input("portfolio-inflation-adjustment-selection", "value"),
    Input("portfolio-y-var-selection", "value"),
    Input("portfolio-return-duration-selection", "value"),
    Input("portfolio-return-duration-selection", "options"),
    Input("portfolio-return-interval-selection", "value"),
    Input("portfolio-return-interval-selection", "options"),
    Input("portfolio-return-type-selection", "value"),
    Input("portfolio-return-type-selection", "options"),
    Input("portfolio-baseline-security-selection", "value"),
    Input("portfolio-baseline-security-selection", "options"),
    Input("portfolio-log-scale-selection", "value"),
    Input("portfolio-chart-type-selection", "value"),
)
def update_portfolio_graph(
    portfolio_strs: list[str],
    portfolio_options: dict[str, str],
    yf_securities: dict[str, str],
    currency: str,
    adjust_for_inflation: str,
    y_var: str,
    return_duration: str,
    return_duration_options: dict[str, str],
    return_interval: str,
    return_interval_options: dict[str, str],
    return_type: str,
    return_type_options: dict[str, str],
    baseline_security: str,
    baseline_security_options: dict[str, str],
    log_scale: list[str],
    chart_type: str,
):
    if not portfolio_strs:
        return {
            "data": [],
            "layout": {
                "title": "Portfolio Performance",
            },
        }
    portfolios_colourmap = dict(
        zip(
            portfolio_options.keys(),
            cycle(DEFAULT_PLOTLY_COLORS),
        )
    )
    data = []
    for portfolio_str in portfolio_strs:
        portfolio: list[str] = json.loads(portfolio_str)
        portfolio_allocations: dict[str, int | float] = reduce(
            dict.__or__, map(json.loads, portfolio)
        )
        securities = portfolio_allocations.keys()
        weights = list(portfolio_allocations.values())
        portfolio_df = pd.concat(
            [
                load_data(
                    security,
                    "Monthly",
                    currency,
                    adjust_for_inflation,
                    yf_securities.get(security),
                )
                for security in securities
            ],
            axis=1,
        )
        portfolio_series = (
            portfolio_df.pct_change()
            .mul(weights)
            .div(100)
            .sum(axis=1, skipna=False)
            .add(1)
            .cumprod()
            .rename("price")
        )
        portfolio_series.iloc[
            portfolio_series.index.get_indexer([portfolio_series.first_valid_index()])[
                0
            ]
            - 1
        ] = 1
        portfolio_series = transform_data(
            portfolio_series,
            "Monthly",
            y_var,
            return_duration,
            return_interval,
            return_type,
        ).rename(portfolio_str)
        data.append(portfolio_series)
    portfolios_df = pd.concat(data, axis=1)
    if y_var in ["rolling_returns", "calendar_returns"] and baseline_security != "None":
        non_baseline_securities = portfolios_df.columns.difference([baseline_security])
        portfolios_df = portfolios_df.sub(
            portfolios_df[baseline_security], axis=0, level=0
        ).dropna(subset=non_baseline_securities, how="all")
        if y_var == "calendar_returns":
            portfolios_df = portfolios_df.drop(columns=baseline_security)
    if y_var == "rolling_returns" and chart_type == "hist":
        data = list(
            filter(
                None,
                [
                    go.Histogram(
                        x=[None],
                        name=portfolio_options[baseline_security],
                        marker=dict(color=portfolios_colourmap[baseline_security]),
                        histnorm="probability",
                        opacity=0.7,
                        showlegend=True,
                    )
                    if baseline_security != "None"
                    else None,
                    *[
                        go.Histogram(
                            x=portfolios_df[column],
                            name=portfolio_options[column],
                            marker=dict(color=portfolios_colourmap[column]),
                            histnorm="probability",
                            opacity=0.7,
                            showlegend=True,
                        )
                        for column in portfolios_df.columns
                        if column != baseline_security
                    ],
                ],
            )
        )

    elif y_var == "calendar_returns":
        if return_interval == "1mo":
            index_offset = pd.offsets.BMonthEnd(0)
            xperiod = "M1"
            xtickformat = "%b %Y"
        elif return_interval == "3mo":
            index_offset = pd.offsets.BQuarterEnd(0)
            xperiod = "M3"
            xtickformat = "Q%q %Y"
        elif return_interval == "1y":
            index_offset = pd.offsets.BYearEnd(0)
            xperiod = "M12"
            xtickformat = "%Y"
        else:
            raise ValueError("Invalid return_interval")

        hovertext = portfolios_df.index.to_series().apply(
            lambda x: x.strftime("As of %d %b %Y") if x != x + index_offset else ""
        )
        data = [
            go.Bar(
                x=portfolios_df.index + index_offset,
                y=portfolios_df[column],
                xperiod=xperiod,
                xperiodalignment="middle",
                name=portfolio_options[column],
                hovertext=hovertext,
                marker=dict(color=portfolios_colourmap[column]),
            )
            for column in portfolios_df.columns
            if column != baseline_security
        ]
    else:
        data = [
            go.Scatter(
                x=portfolios_df.index,
                y=portfolios_df[column],
                name=portfolio_options[column],
                line=dict(color=portfolios_colourmap[column], dash="dash")
                if y_var == "rolling_returns" and column == baseline_security
                else dict(color=portfolios_colourmap[column]),
            )
            for column in portfolios_df.columns
        ]

    if y_var == "rolling_returns" and chart_type == "hist":
        barmode = "overlay"
        shapes = [
            dict(
                type="line",
                x0=0,
                x1=0,
                y0=0,
                y1=1,
                yref="paper",
                line=dict(
                    color=portfolios_colourmap[baseline_security]
                    if baseline_security != "None"
                    else "grey",
                    width=1,
                    dash="dash",
                ),
                opacity=0.7,
            )
        ]
    elif y_var == "calendar_returns":
        barmode = "group"
        shapes = None
    else:
        barmode = None
        shapes = None

    if y_var == "price":
        title = "Price"
        ytickformat = ".2f"
    elif y_var == "drawdown":
        title = "Drawdown"
        ytickformat = ".2%"
    elif y_var == "rolling_returns":
        title = f"{return_duration_options[return_duration]} {return_type_options[return_type]} Rolling Returns"
        ytickformat = ".2%"
    elif y_var == "calendar_returns":
        title = f"{return_interval_options[return_interval]} Returns"
        ytickformat = ".2%"
    else:
        raise ValueError("Invalid y_var")
    if baseline_security != "None":
        title += f" vs {baseline_security_options[baseline_security]}"

    layout = go.Layout(
        title=title,
        hovermode="x",
        xaxis=(
            dict(
                ticklabelmode="period",
                tickformat=xtickformat,
            )
            if y_var == "calendar_returns"
            else None
        ),
        yaxis=dict(
            tickformat=ytickformat,
            type="log" if "log" in log_scale else "linear",
        ),
        barmode=barmode,
        showlegend=True,
        shapes=shapes,
    )
    return dict(data=data, layout=layout)


@app.callback(
    Output("accumulation-strategy-portfolio", "options"),
    Output("withdrawal-strategy-portfolio", "options"),
    Input("portfolios", "options"),
)
def update_strategy_portfolios(portfolio_options: dict[str, str]):
    return portfolio_options, portfolio_options


@app.callback(
    Output("accumulation-ls-input-container", "style"),
    Output("accumulation-dca-input-container", "style"),
    Input("accumulation-ls-dca-selection", "value"),
)
def update_ls_input_visibility(ls_dca: str):
    if ls_dca == "LS":
        return {"display": "block"}, {"display": "none"}
    return {"display": "none"}, {"display": "block"}


@app.callback(
    Output("accumulation-strategies", "value"),
    Output("accumulation-strategies", "options"),
    Input("add-accumulation-strategy-button", "n_clicks"),
    State("accumulation-strategies", "value"),
    State("accumulation-strategies", "options"),
    State("accumulation-strategy-portfolio", "value"),
    State("accumulation-strategy-portfolio", "options"),
    State("accumulation-strategy-currency-selection", "value"),
    State("accumulation-ls-dca-selection", "value"),
    State("accumulation-investment-amount-input", "value"),
    State("accumulation-monthly-investment-input", "value"),
    State("accumulation-inflation-adjustment-selection", "value"),
    State("accumulation-investment-horizon-input", "value"),
    State("accumulation-dca-length-input", "value"),
    State("accumulation-dca-interval-input", "value"),
    State("accumulation-variable-transaction-fees-input", "value"),
    State("accumulation-fixed-transaction-fees-input", "value"),
    State("accumulation-annualised-holding-fees-input", "value"),
    prevent_initial_call=True,
)
def update_accumulation_strategies(
    _,
    strategies: list[str] | None,
    strategy_options: dict[str, str],
    strategy_portfolio: str | None,
    strategy_portfolio_options: dict[str, str],
    currency: str,
    ls_dca: str,
    investment_amount: int | float | None,
    monthly_investment: int | float | None,
    adjust_for_inflation: str,
    investment_horizon: int | None,
    dca_length: int | None,
    dca_interval: int | None,
    variable_transaction_fees: int | float | None,
    fixed_transaction_fees: int | float | None,
    annualised_holding_fees: int | float | None,
):
    if strategy_portfolio is None:
        return no_update
    if dca_interval is None:
        dca_interval = 1

    if ls_dca == "LS":
        if investment_amount is None:
            return no_update
        if investment_horizon is None:
            return no_update
        if dca_length is None:
            dca_length = 1
    elif ls_dca == "DCA":
        if monthly_investment is None:
            return no_update
        if dca_length is None:
            return no_update
        if investment_horizon is None:
            investment_horizon = dca_length
    else:
        return no_update

    if variable_transaction_fees is None:
        variable_transaction_fees = 0
    if fixed_transaction_fees is None:
        fixed_transaction_fees = 0
    if annualised_holding_fees is None:
        annualised_holding_fees = 0

    if dca_length > investment_horizon:
        return no_update

    if (
        variable_transaction_fees < 0
        or fixed_transaction_fees < 0
        or annualised_holding_fees < 0
    ):
        return no_update
    investment_amount = investment_amount or 0
    monthly_investment = monthly_investment or 0
    strategy_str = json.dumps(
        {
            "strategy_portfolio": strategy_portfolio,
            "currency": currency,
            "ls_dca": ls_dca,
            "investment_amount": investment_amount,
            "investment_horizon": investment_horizon,
            "monthly_investment": monthly_investment,
            "adjust_for_inflation": adjust_for_inflation,
            "dca_length": dca_length,
            "dca_interval": dca_interval,
            "variable_transaction_fees": variable_transaction_fees,
            "fixed_transaction_fees": fixed_transaction_fees,
            "annualised_holding_fees": annualised_holding_fees,
        }
    )
    if ls_dca == "LS":
        strategy = (
            strategy_str,
            f"{strategy_portfolio_options[strategy_portfolio]} {currency}, "
            f"Lump Sum, "
            f"{investment_amount} invested for {investment_horizon} months, "
            f"DCA over {dca_length} months every {dca_interval} months, "
            f"{variable_transaction_fees}% + ${fixed_transaction_fees} Fee, "
            f"{annualised_holding_fees}% p.a. Holding Fees",
        )
    else:
        strategy = (
            strategy_str,
            f"{strategy_portfolio_options[strategy_portfolio]} {currency}, "
            f"DCA,"
            f"{monthly_investment} invested monthly for {dca_length} months, "
            f"{dca_interval} months apart, held for {investment_horizon} months, "
            f"{adjust_for_inflation} adjusted for inflation, "
            f"{variable_transaction_fees}% + ${fixed_transaction_fees} Fee, "
            f"{annualised_holding_fees}% p.a. Holding Fees",
        )

    if strategies is None:
        return [strategy[0]], {strategy[0]: strategy[1]}
    if strategy[0] in strategies:
        return no_update
    strategies.append(strategy[0])
    strategy_options.update({strategy[0]: strategy[1]})
    return strategies, strategy_options


@app.callback(
    Output("accumulation-strategy-graph", "figure"),
    Input("accumulation-strategies", "value"),
    State("accumulation-strategies", "options"),
    State("yf-securities-store", "data"),
    prevent_initial_call=True,
)
def update_accumulation_strategy_graph(
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    yf_securities: dict[str, str],
):
    series = []
    if not strategy_strs:
        return {
            "data": [],
            "layout": {
                "title": "Strategy Performance",
            },
        }
    for strategy_str in strategy_strs:
        strategy: dict[str, str | int | float] = json.loads(strategy_str)
        strategy_portfolio = str(strategy["strategy_portfolio"])
        currency = str(strategy["currency"])
        ls_dca = str(strategy["ls_dca"])
        investment_amount = float(strategy["investment_amount"])
        investment_horizon = int(strategy["investment_horizon"])
        monthly_investment = float(strategy["monthly_investment"])
        adjust_for_inflation = str(strategy["adjust_for_inflation"])
        dca_length = int(strategy["dca_length"])
        dca_interval = int(strategy["dca_interval"])
        variable_transaction_fees = float(strategy["variable_transaction_fees"])
        fixed_transaction_fees = float(strategy["fixed_transaction_fees"])
        annualised_holding_fees = float(strategy["annualised_holding_fees"])

        portfolio_allocation_strs: list[str] = json.loads(strategy_portfolio)
        portfolio_allocations: dict[str, int | float] = reduce(
            dict.__or__, map(json.loads, portfolio_allocation_strs)
        )
        variable_transaction_fees /= 100
        annualised_holding_fees /= 100
        securities = portfolio_allocations.keys()
        weights = list(portfolio_allocations.values())
        if sum(weights) > 100:
            return no_update
        strategy_series = pd.concat(
            [
                load_data(
                    security,
                    "Monthly",
                    currency,
                    "No",
                    yf_securities.get(security),
                )
                for security in securities
            ],
            axis=1,
        )
        strategy_series = (
            strategy_series.pct_change()
            .mul(weights)
            .div(100)
            .sum(axis=1, skipna=False)
            .add(1)
            .cumprod()
        )
        strategy_series.iloc[
            strategy_series.index.get_indexer([strategy_series.first_valid_index()])[0]
            - 1
        ] = 1
        interest_rates = (
            load_fed_funds_rate()[1].reindex(strategy_series.index).fillna(0).to_numpy()
            if currency == "USD"
            else load_sgd_interest_rates()[1]["sgd_ir_1m"]
            .reindex(strategy_series.index)
            .fillna(0)
            .to_numpy()
        )
        us_cpi = load_us_cpi()["us_cpi"].reindex(strategy_series.index).to_numpy()
        sg_cpi = load_sg_cpi()["sg_cpi"].reindex(strategy_series.index).to_numpy()
        cpi = (
            np.ones(len(strategy_series))
            if adjust_for_inflation != "Monthly Investment"
            else us_cpi
            if currency == "USD"
            else sg_cpi
        )

        if ls_dca == "LS":
            ending_values = pd.Series(
                calculate_lumpsum_portfolio_value_with_fees_and_interest_vector(
                    strategy_series.pct_change().to_numpy(),
                    dca_length,
                    dca_interval,
                    investment_horizon,
                    investment_amount,
                    variable_transaction_fees,
                    fixed_transaction_fees,
                    annualised_holding_fees,
                    interest_rates,
                ),
                index=strategy_series.index,
                name=strategy_str,
            )
        else:
            ending_values = pd.Series(
                calculate_dca_portfolio_value_with_fees_and_interest_vector(
                    strategy_series.pct_change().to_numpy(),
                    dca_length,
                    dca_interval,
                    investment_horizon,
                    monthly_investment,
                    cpi,
                    variable_transaction_fees,
                    fixed_transaction_fees,
                    annualised_holding_fees,
                    interest_rates,
                ),
                index=strategy_series.index,
                name=strategy_str,
            )
        series.append(ending_values)
    ending_values = pd.concat(series, axis=1, names=strategy_strs)
    return {
        "data": [
            go.Scatter(
                x=ending_values.index,
                y=ending_values[strategy],
                mode="lines",
                name=strategy_options[strategy],
            )
            for strategy in ending_values.columns
        ],
        "layout": {
            "title": "Strategy Performance",
        },
    }


@app.callback(
    Output("withdrawal-strategies", "value"),
    Output("withdrawal-strategies", "options"),
    Input("add-withdrawal-strategy-button", "n_clicks"),
    State("withdrawal-strategies", "value"),
    State("withdrawal-strategies", "options"),
    State("withdrawal-strategy-portfolio", "value"),
    State("withdrawal-strategy-portfolio", "options"),
    State("withdrawal-strategy-currency-selection", "value"),
    State("withdrawal-initial-capital-input", "value"),
    State("monthly-withdrawal-input", "value"),
    State("withdrawal-inflation-adjustment-selection", "value"),
    State("withdrawal-horizon-input", "value"),
    State("withdrawal-interval-input", "value"),
    State("withdrawal-variable-transaction-fees-input", "value"),
    State("withdrawal-fixed-transaction-fees-input", "value"),
    State("withdrawal-annualised-holding-fees-input", "value"),
    prevent_initial_call=True,
)
def update_withdrawal_strategies(
    _,
    strategies: list[str] | None,
    strategy_options: dict[str, str],
    strategy_portfolio: str | None,
    strategy_portfolio_options: dict[str, str],
    currency: str,
    initial_capital: int | float | None,
    monthly_withdrawal: int | float | None,
    adjust_for_inflation: str,
    withdrawal_horizon: int | None,
    withdrawal_interval: int | None,
    variable_transaction_fees: int | float | None,
    fixed_transaction_fees: int | float | None,
    annualised_holding_fees: int | float | None,
):
    if strategy_portfolio is None:
        return no_update
    if initial_capital is None:
        return no_update
    if monthly_withdrawal is None:
        return no_update
    if withdrawal_horizon is None:
        return no_update
    if withdrawal_interval is None:
        withdrawal_interval = 1

    if variable_transaction_fees is None:
        variable_transaction_fees = 0
    if fixed_transaction_fees is None:
        fixed_transaction_fees = 0
    if annualised_holding_fees is None:
        annualised_holding_fees = 0

    if (
        variable_transaction_fees < 0
        or fixed_transaction_fees < 0
        or annualised_holding_fees < 0
    ):
        return no_update
    initial_capital = initial_capital or 0
    monthly_withdrawal = monthly_withdrawal or 0
    strategy_str = json.dumps(
        {
            "strategy_portfolio": strategy_portfolio,
            "currency": currency,
            "initial_capital": initial_capital,
            "withdrawal_horizon": withdrawal_horizon,
            "monthly_withdrawal": monthly_withdrawal,
            "adjust_for_inflation": adjust_for_inflation,
            "withdrawal_interval": withdrawal_interval,
            "variable_transaction_fees": variable_transaction_fees,
            "fixed_transaction_fees": fixed_transaction_fees,
            "annualised_holding_fees": annualised_holding_fees,
        }
    )

    strategy = (
        strategy_str,
        f"{strategy_portfolio_options[strategy_portfolio]} {currency}, "
        f"{monthly_withdrawal} withdrawn monthly, "
        f"{withdrawal_interval} months apart for {withdrawal_horizon} months, "
        f"{adjust_for_inflation} adjusted for inflation, "
        f"{variable_transaction_fees}% + ${fixed_transaction_fees} Fee, "
        f"{annualised_holding_fees}% p.a. Holding Fees",
    )

    if strategies is None:
        return [strategy[0]], {strategy[0]: strategy[1]}
    if strategy[0] in strategies:
        return no_update
    strategies.append(strategy[0])
    strategy_options.update({strategy[0]: strategy[1]})
    return strategies, strategy_options


@app.callback(
    Output("withdrawal-strategy-graph", "figure"),
    Input("withdrawal-strategies", "value"),
    State("withdrawal-strategies", "options"),
    State("yf-securities-store", "data"),
    prevent_initial_call=True,
)
def update_withdrawal_strategy_graph(
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    yf_securities: dict[str, str],
):
    series = []
    if not strategy_strs:
        return {
            "data": [],
            "layout": {
                "title": "Strategy Performance",
            },
        }
    for strategy_str in strategy_strs:
        strategy: dict[str, str | int | float] = json.loads(strategy_str)
        strategy_portfolio = str(strategy["strategy_portfolio"])
        currency = str(strategy["currency"])
        initial_capital = float(strategy["initial_capital"])
        withdrawal_horizon = int(strategy["withdrawal_horizon"])
        monthly_withdrawal = float(strategy["monthly_withdrawal"])
        adjust_for_inflation = str(strategy["adjust_for_inflation"])
        withdrawal_interval = int(strategy["withdrawal_interval"])
        variable_transaction_fees = float(strategy["variable_transaction_fees"])
        fixed_transaction_fees = float(strategy["fixed_transaction_fees"])
        annualised_holding_fees = float(strategy["annualised_holding_fees"])

        portfolio_allocation_strs: list[str] = json.loads(strategy_portfolio)
        portfolio_allocations: dict[str, int | float] = reduce(
            dict.__or__, map(json.loads, portfolio_allocation_strs)
        )
        variable_transaction_fees /= 100
        annualised_holding_fees /= 100
        securities = portfolio_allocations.keys()
        weights = list(portfolio_allocations.values())
        if sum(weights) > 100:
            return no_update
        strategy_series = pd.concat(
            [
                load_data(
                    security,
                    "Monthly",
                    currency,
                    "No",
                    yf_securities.get(security),
                )
                for security in securities
            ],
            axis=1,
        )
        strategy_series = (
            strategy_series.pct_change()
            .mul(weights)
            .div(100)
            .sum(axis=1, skipna=False)
            .add(1)
            .cumprod()
        )
        strategy_series.iloc[
            strategy_series.index.get_indexer([strategy_series.first_valid_index()])[0]
            - 1
        ] = 1
        us_cpi = load_us_cpi()["us_cpi"].reindex(strategy_series.index).to_numpy()
        sg_cpi = load_sg_cpi()["sg_cpi"].reindex(strategy_series.index).to_numpy()
        cpi = (
            np.ones(len(strategy_series))
            if adjust_for_inflation != "Monthly Withdrawal"
            else us_cpi
            if currency == "USD"
            else sg_cpi
        )

        ending_values = pd.Series(
            calculate_withdrawal_portfolio_value_with_fees_vector(
                strategy_series.pct_change().to_numpy(),
                withdrawal_horizon,
                withdrawal_interval,
                initial_capital,
                monthly_withdrawal,
                cpi,
                variable_transaction_fees,
                fixed_transaction_fees,
                annualised_holding_fees,
            ),
            index=strategy_series.index,
            name=strategy_str,
        )
        series.append(ending_values)
    ending_values = pd.concat(series, axis=1, names=strategy_strs)
    return {
        "data": [
            go.Scatter(
                x=ending_values.index,
                y=ending_values[strategy],
                mode="lines",
                name=strategy_options[strategy],
            )
            for strategy in ending_values.columns
        ],
        "layout": {
            "title": "Strategy Performance",
        },
    }


if __name__ == "__main__":
    app.run(debug=True)
