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
    download_ft_data,
    get_ft_api_key,
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
    cached_security: str | None,
):
    security: dict[str, str] = json.loads(security_str)
    source = security["source"]
    if source == "MSCI":
        series = read_msci_data(
            f"data/"
            f"MSCI/"
            f"{security['msci_base_index']}/"
            f"{security['msci_size']}/"
            f"{security['msci_style']}/"
            f"*{security['msci_tax_treatment']} {interval}.csv"
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
        series = pd.read_json(StringIO(cached_security), orient="index", typ="series")
        series = convert_price_to_usd(series, ticker_currency)
        if interval == "Monthly":
            series = series.pipe(resample_bme)
    elif source == "FT":
        ticker_currency = security["currency"]
        series = pd.read_json(StringIO(cached_security), orient="index", typ="series")
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
                    series.index
                    - pd.offsets.DateOffset(months=return_durations[return_duration])
                    + pd.offsets.Day(1)
                    - pd.offsets.BDay(1)
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


app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])

server = app.server

app.layout = app_layout


@app.callback(
    Output("index-selection-container", "style"),
    Output("stock-etf-selection-container", "style"),
    Output("fund-selection-container", "style"),
    Output("fund-index-selection-container", "style"),
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
            f"data/"
            f"{index_provider}/"
            f"{msci_base_index}/"
            f"{msci_size}/"
            f"{msci_style}/"
            f"* {msci_tax_treatment}*.csv"
        ):
            return True, no_update, no_update

        index_json = json.dumps(
            {
                "source": "MSCI",
                "msci_base_index": msci_base_index,
                "msci_size": msci_size,
                "msci_style": msci_style,
                "msci_tax_treatment": msci_tax_treatment,
            }
        )
        index_name_template = [
            index_provider_options[index_provider],
            msci_base_index_options[msci_base_index],
            (None if msci_size == "STANDARD" else msci_size_options[msci_size]),
            (
                "Cap"
                if msci_size in ["SMALL", "SMID", "MID", "LARGE"]
                and msci_style == "BLEND"
                else None
            ),
            (None if msci_style == "BLEND" else msci_style_options[msci_style]),
            msci_tax_treatment,
        ]
        index_name = " ".join(
            field for field in index_name_template if field is not None
        )

    elif index_provider == "FRED":
        if fred_index == "US-T":
            index_json = json.dumps(
                {
                    "source": "FRED",
                    "fred_index": fred_index,
                    "us_treasury_duration": us_treasury_duration,
                }
            )
            index_name = (
                f"{us_treasury_duration_options[us_treasury_duration]}"
                f"{fred_index_options[fred_index]}"
            )
        else:
            return True, no_update, no_update

    elif index_provider == "MAS":
        if mas_index == "SGS":
            index_json = json.dumps(
                {
                    "source": "MAS",
                    "mas_index": mas_index,
                    "sgs_duration": sgs_duration,
                }
            )
            index_name = (
                f"{sgs_duration_options[sgs_duration]} {mas_index_options[mas_index]}"
            )
        else:
            return True, no_update, no_update

    else:
        others_tax_treatment = (
            "Gross"
            if others_index in ["STI", "AWORLDS", "SREIT"]
            else others_tax_treatment
        )
        index_json = json.dumps(
            {
                "source": "Others",
                "others_index": others_index,
                "others_tax_treatment": others_tax_treatment,
            }
        )
        index_name = f"{others_index_options[others_index]} {others_tax_treatment}"

    if selected_securities is None:
        return False, [index_json], {index_json: index_name}
    if index_json in selected_securities:
        return no_update
    selected_securities.append(index_json)
    selected_securities_options.update({index_json: index_name})
    return False, selected_securities, selected_securities_options


@app.callback(
    Output("stock-etf-toast", "children"),
    Output("stock-etf-toast", "is_open"),
    Output("selected-securities", "value", allow_duplicate=True),
    Output("selected-securities", "options", allow_duplicate=True),
    Output("yf-invalid-securities-store", "data"),
    Output("cached-securities-store", "data"),
    Input("add-stock-etf-button", "n_clicks"),
    State("selected-securities", "value"),
    State("selected-securities", "options"),
    State("stock-etf-input", "value"),
    State("stock-etf-tax-treatment-selection", "value"),
    State("yf-invalid-securities-store", "data"),
    State("cached-securities-store", "data"),
    prevent_initial_call=True,
    running=[(Output("add-stock-etf-button", "disabled"), True, False)],
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
    selected_securities_options[new_yf_security] = (
        f"yfinance: {ticker_symbol} {tax_treatment}"
    )

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
    Output("fund-index-toast", "children"),
    Output("fund-index-toast", "is_open"),
    Output("selected-securities", "value", allow_duplicate=True),
    Output("selected-securities", "options", allow_duplicate=True),
    Output("ft-invalid-securities-store", "data"),
    Output("cached-securities-store", "data", allow_duplicate=True),
    Output("ft-api-key-store", "data"),
    Input("add-fund-index-button", "n_clicks"),
    State("selected-securities", "value"),
    State("selected-securities", "options"),
    State("fund-index-input", "value"),
    State("ft-invalid-securities-store", "data"),
    State("cached-securities-store", "data"),
    State("ft-api-key-store", "data"),
    prevent_initial_call=True,
    running=[(Output("add-fund-index-button", "disabled"), True, False)],
)
def add_fund_index(
    _,
    selected_securities: list[str],
    selected_securities_options: dict,
    fund_index: str,
    ft_invalid_securities_store: list[str],
    ft_securities_store: dict,
    stored_ft_api_key: str | None,
):
    if not fund_index:
        return no_update
    if ";" in fund_index:
        return "Invalid character: ;", True, no_update, no_update, no_update, no_update
    if fund_index in ft_invalid_securities_store:
        return (
            "The selected ticker is not available",
            True,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
        )
    for ft_security_str in ft_securities_store:
        ft_security = json.loads(ft_security_str)
        if fund_index != ft_security["ticker"]:
            continue
        if ft_security_str in selected_securities:
            return no_update
        if ft_security_str in selected_securities_options:
            selected_securities.append(ft_security_str)
            return (
                no_update,
                no_update,
                selected_securities,
                selected_securities_options,
                no_update,
                ft_securities_store,
                no_update,
            )
    if stored_ft_api_key is not None:
        ft_api_key = stored_ft_api_key
    else:
        ft_api_key = get_ft_api_key()
    try:
        df, ticker, currency = download_ft_data(fund_index, ft_api_key)
    except ValueError as e:
        ft_invalid_securities_store.append(fund_index)
        return (
            str(e),
            True,
            no_update,
            no_update,
            ft_invalid_securities_store,
            no_update,
            ft_api_key,
        )

    new_ft_security = json.dumps(
        {
            "source": "FT",
            "ticker": ticker,
            "currency": currency,
        }
    )
    selected_securities.append(new_ft_security)
    selected_securities_options[new_ft_security] = f"FT: {ticker}"

    ft_securities_store[new_ft_security] = df["price"].to_json(orient="index")

    return (
        no_update,
        no_update,
        selected_securities,
        selected_securities_options,
        no_update,
        ft_securities_store,
        ft_api_key,
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
    security_json = json.dumps(
        {
            "source": "Fund",
            "fund_company": fund_company,
            "fund": fund,
            "currency": currency,
        }
    )
    security_name = (
        f"{f'{fund_company} ' if fund_company != 'Great Eastern' else ''}{fund}"
    )
    if security_json in selected_securities:
        return no_update
    selected_securities.append(security_json)
    selected_securities_options.update({security_json: security_name})
    return selected_securities, selected_securities_options


def update_selection_visibility(y_var: str):
    show = {"display": "block"}
    hide = {"display": "none"}

    log_scale_style = show if y_var == "price" else hide

    percent_scale_style = show if y_var == "price" else hide

    return_selection_style = (
        show if y_var in ["rolling_returns", "calendar_returns"] else hide
    )
    rolling_return_selection_style = show if y_var == "rolling_returns" else hide
    calendar_return_selection_style = show if y_var == "calendar_returns" else hide

    return (
        log_scale_style,
        percent_scale_style,
        return_selection_style,
        rolling_return_selection_style,
        calendar_return_selection_style,
    )


@app.callback(
    Output("log-scale-switch", "style"),
    Output("percent-scale-switch", "style"),
    Output("return-selection", "style"),
    Output("rolling-return-selection-container", "style"),
    Output("calendar-return-selection-container", "style"),
    Input("y-var-selection", "value"),
)
def update_returns_dashboard_selection_visibility(y_var: str):
    return update_selection_visibility(y_var)


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


def update_graph(
    df: pd.DataFrame,
    trace_colourmap: dict[str, str],
    trace_options: dict[str, str],
    y_var: str,
    log_scale: bool,
    percent_scale: bool,
    return_duration: str,
    return_duration_options: dict[str, str],
    return_interval: str,
    return_interval_options: dict[str, str],
    return_type: str,
    return_type_options: dict[str, str],
    baseline_trace: str,
    baseline_trace_options: dict[str, str],
    chart_type: str,
    relayout_data: dict | None = None,
):
    layout = go.Layout(
        hovermode="x",
        showlegend=True,
        legend=go.layout.Legend(valign="top"),
        uirevision=y_var,
        yaxis_uirevision=y_var + str(log_scale) + str(percent_scale),
    )

    if y_var == "price":
        layout.update(
            title="Price",
            yaxis_tickformat=".2f",
        )

        start_date = None
        end_date = None
        if relayout_data:
            if relayout_data.get("price", None):
                if (
                    ctx.triggered_id != ["graph", "portfolio-graph"]
                    and "xaxis.range[0]" in relayout_data["price"]
                ):
                    layout.update(
                        xaxis_range=(
                            relayout_data["price"]["xaxis.range[0]"],
                            relayout_data["price"]["xaxis.range[1]"],
                        )
                    )
                if relayout_data.get(y_var, None):
                    if "xaxis.range[0]" in relayout_data["price"]:
                        try:
                            start_date = pd.to_datetime(
                                relayout_data["price"]["xaxis.range[0]"]
                            )
                            end_date = pd.to_datetime(
                                relayout_data["price"]["xaxis.range[1]"]
                            )
                        except (ValueError, TypeError):
                            start_date = None
                            end_date = None

        price_adj = 0
        hoverinfo = None

        if not percent_scale and not log_scale:
            layout.update(
                yaxis_autorangeoptions_minallowed=df.loc[start_date:].min().min()
            )
            layout.update(
                yaxis_autorangeoptions_maxallowed=df.loc[:end_date].max().max()
            )
        if percent_scale:
            layout.update(yaxis_uirevision=False)
            for column in df.columns:
                series = df[column].dropna()
                if series.empty:
                    df[column] = np.nan
                    continue
                baseline_value = None
                if start_date:
                    visible_series = series[series.index >= start_date]
                    if not visible_series.empty:
                        baseline_value = visible_series.iloc[0]
                if baseline_value is None:
                    baseline_value = series.iloc[0]
                if baseline_value != 0:
                    df[column] = df[column].div(baseline_value).sub(1)
                else:
                    df[column] = np.nan
            if not log_scale:
                layout.update(
                    yaxis_autorangeoptions_minallowed=df.loc[start_date:].min().min()
                )
                layout.update(
                    yaxis_autorangeoptions_maxallowed=df.loc[:end_date].max().max()
                )
            layout.update(title="% Change")
            layout.update(yaxis_tickformat="+.2%")

        if log_scale:
            layout.update(yaxis_type="log")
            if ctx.triggered_id not in ["graph", "portfolio-graph"]:
                yaxis_range = [
                    np.log10(df.loc[start_date:].min().min() + 1),
                    np.log10(df.loc[:end_date].max().max() + 1),
                ]
                layout.update(yaxis_range=yaxis_range)

        if percent_scale and log_scale:
            price_adj = 1
            hoverinfo = "text+name"
            ytickvals = (
                list(n / 10 for n in range(0, 11))
                + list(n / 10 + 1 for n in range(1, 11))
                + [base * 10**exp + 1 for exp in range(6) for base in range(1, 10)]
            )
            yticktexts = [f"{tick - 1:+.2%}" for tick in ytickvals]
            layout.update(yaxis_tickvals=ytickvals)
            layout.update(yaxis_ticktext=yticktexts)

        data = [
            go.Scatter(
                x=df.index,
                y=df[column].add(price_adj),
                name=trace_options[column],
                line=go.scatter.Line(color=trace_colourmap[column]),
                hoverinfo=hoverinfo,
                hovertext=df[column].apply(lambda x: f"{x:+.2%}")
                if log_scale and percent_scale
                else None,
            )
            for column in df.columns
        ]
        return data, layout

    if y_var == "drawdown":
        layout = layout.update(
            title="Drawdown",
            yaxis_tickformat=".2%",
        )

        data = [
            go.Scatter(
                x=df.index,
                y=df[column],
                name=trace_options[column],
                line=go.scatter.Line(color=trace_colourmap[column]),
            )
            for column in df.columns
        ]
        return data, layout

    if y_var == "rolling_returns":
        layout.update(yaxis_tickformat=".2%")

        title = (
            f"{return_duration_options[return_duration]} "
            f"{return_type_options[return_type]} Rolling Returns"
        )

        if baseline_trace != "None":
            df = df.sub(df[baseline_trace], axis=0, level=0).dropna(
                subset=df.columns.difference([baseline_trace]), how="all"
            )
            title += f" vs {baseline_trace_options[baseline_trace]}"

        layout = layout.update(
            title=title,
        )

        if chart_type == "line":
            data = [
                go.Scatter(
                    x=df.index,
                    y=df[column],
                    name=trace_options[column],
                    line=go.scatter.Line(
                        color=trace_colourmap[column],
                        dash=("dash" if column == baseline_trace else None),
                    ),
                )
                for column in df.columns
            ]

        elif chart_type == "hist":
            vertical_line = go.layout.Shape(
                type="line",
                x0=0,
                x1=0,
                y0=0,
                y1=1,
                yref="paper",
                line=go.layout.shape.Line(
                    color=trace_colourmap[baseline_trace]
                    if baseline_trace != "None"
                    else "grey",
                    width=1,
                    dash="dash",
                ),
                opacity=0.7,
            )
            layout.update(
                barmode="overlay",
                shapes=[vertical_line],
            )

            data = [
                go.Histogram(
                    x=[None],
                    name=trace_options[baseline_trace],
                    marker=go.histogram.Marker(color=trace_colourmap[baseline_trace]),
                    histnorm="probability",
                    opacity=0.7,
                    showlegend=True,
                )
                if baseline_trace != "None"
                else None,
                *[
                    go.Histogram(
                        x=df[column],
                        name=trace_options[column],
                        marker=go.histogram.Marker(color=trace_colourmap[column]),
                        histnorm="probability",
                        opacity=0.7,
                        showlegend=True,
                    )
                    for column in df.columns
                    if column != baseline_trace
                ],
            ]
            data = [trace for trace in data if trace is not None]

        else:
            raise ValueError("Invalid chart_type")
        return data, layout

    if y_var == "calendar_returns":
        layout.update(
            xaxis_ticklabelmode="period",
            yaxis_tickformat=".2%",
            barmode="group",
        )

        title = f"{return_interval_options[return_interval]} Returns"

        if baseline_trace != "None":
            df = (
                df.sub(df[baseline_trace], axis=0, level=0)
                .dropna(subset=df.columns.difference([baseline_trace]), how="all")
                .drop(columns=baseline_trace)
            )
            title += f" vs {baseline_trace_options[baseline_trace]}"

        layout.update(title=title)

        if return_interval == "1mo":
            index_offset = pd.offsets.BMonthEnd(0)
            xperiod = "M1"
            layout.update(xaxis_tickformat="%b %Y")
        elif return_interval == "3mo":
            index_offset = pd.offsets.BQuarterEnd(0)
            xperiod = "M3"
            layout.update(xaxis_tickformat="Q%q %Y")
        elif return_interval == "1y":
            index_offset = pd.offsets.BYearEnd(0)
            xperiod = "M12"
            layout.update(xaxis_tickformat="%Y")
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
                name=trace_options[column],
                hovertext=hovertext,
                marker=go.bar.Marker(color=trace_colourmap[column]),
            )
            for column in df.columns
            if column != baseline_trace
        ]
        return data, layout
    raise ValueError("Invalid y_var")


@app.callback(
    Output("graph-xaxis-relayout-store", "data"),
    State("graph-xaxis-relayout-store", "data"),
    State("y-var-selection", "value"),
    Input("graph", "relayoutData"),
)
def update_xaxis_relayout_store(
    current_data: dict | None,
    y_var: str,
    relayout_data: dict,
):
    if current_data is None:
        return {y_var: relayout_data}
    for key in relayout_data:
        if "xaxis" in key:
            current_data.update({y_var: relayout_data})
            break
    return current_data


@app.callback(
    Output("graph", "figure"),
    Input("selected-securities", "value"),
    Input("selected-securities", "options"),
    Input("cached-securities-store", "data"),
    Input("currency-selection", "value"),
    Input("inflation-adjustment-selection", "value"),
    Input("y-var-selection", "value"),
    Input("log-scale-switch", "value"),
    Input("percent-scale-switch", "value"),
    Input("return-duration-selection", "value"),
    Input("return-duration-selection", "options"),
    Input("return-interval-selection", "value"),
    Input("return-interval-selection", "options"),
    Input("return-type-selection", "value"),
    Input("return-type-selection", "options"),
    Input("interval-selection", "value"),
    Input("baseline-security-selection", "value"),
    Input("baseline-security-selection", "options"),
    Input("chart-type-selection", "value"),
    Input("graph-xaxis-relayout-store", "data"),
)
def update_security_graph(
    selected_securities: list[str],
    selected_securities_options: dict[str, str],
    cached_securities: dict[str, str],
    currency: str,
    adjust_for_inflation: str,
    y_var: str,
    log_scale: bool,
    percent_scale: bool,
    return_duration: str,
    return_duration_options: dict[str, str],
    return_interval: str,
    return_interval_options: dict[str, str],
    return_type: str,
    return_type_options: dict[str, str],
    interval: str,
    baseline_security: str,
    baseline_security_options: dict[str, str],
    chart_type: str,
    relayout_data: dict | None,
):
    securities_colourmap = dict(
        zip(
            selected_securities_options.keys(),
            cycle(DEFAULT_PLOTLY_COLORS),
        )
    )
    df = pd.DataFrame(
        {
            selected_security: transform_data(
                load_data(
                    selected_security,
                    "Monthly" if y_var == "calendar_returns" else interval,
                    currency,
                    adjust_for_inflation,
                    cached_securities.get(selected_security),
                ),
                interval,
                y_var,
                return_duration,
                return_interval,
                return_type,
            )
            for selected_security in selected_securities
        }
    )
    data, layout = update_graph(
        df,
        securities_colourmap,
        selected_securities_options,
        y_var,
        log_scale,
        percent_scale,
        return_duration,
        return_duration_options,
        return_interval,
        return_interval_options,
        return_type,
        return_type_options,
        baseline_security,
        baseline_security_options,
        chart_type,
        relayout_data,
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
    if ctx.triggered_id == "add-security-button":
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
    if ctx.triggered_id == "portfolio-allocations":
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
    Output("portfolio-allocations", "value", allow_duplicate=True),
    Output("portfolio-allocations", "options", allow_duplicate=True),
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
        return [portfolio_str], {portfolio_str: portfolio_title}, [], {}
    if portfolio_str in portfolio_strs:
        return no_update
    portfolio_strs.append(portfolio_str)
    portfolio_options.update({portfolio_str: portfolio_title})
    return portfolio_strs, portfolio_options, [], {}


@app.callback(
    Output("portfolio-log-scale-switch", "style"),
    Output("portfolio-percent-scale-switch", "style"),
    Output("portfolio-return-selection", "style"),
    Output("portfolio-rolling-return-selection-container", "style"),
    Output("portfolio-calendar-return-selection-container", "style"),
    Input("portfolio-y-var-selection", "value"),
)
def update_portfolio_selection_visibility(y_var: str):
    return update_selection_visibility(y_var)


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


def load_portfolio(
    portfolio_str: str,
    currency: str,
    adjust_for_inflation: str,
    yf_securities: dict[str, str],
):
    portfolio_allocation_strs: list[str] = json.loads(portfolio_str)
    portfolio_allocations: dict[str, int | float] = reduce(
        dict.__or__, map(json.loads, portfolio_allocation_strs)
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
        portfolio_series.index.get_indexer([portfolio_series.first_valid_index()])[0]
        - 1
    ] = 1
    portfolio_series = portfolio_series.dropna()
    return portfolio_series


@app.callback(
    Output("portfolio-graph-xaxis-relayout-store", "data"),
    State("portfolio-graph-xaxis-relayout-store", "data"),
    State("portfolio-y-var-selection", "value"),
    Input("portfolio-graph", "relayoutData"),
)
def update_portfolio_xaxis_relayout_store(
    current_data: dict | None,
    y_var: str,
    relayout_data: dict,
):
    if current_data is None:
        return {y_var: relayout_data}
    for key in relayout_data:
        if "xaxis" in key:
            current_data.update({y_var: relayout_data})
            break
    return current_data


@app.callback(
    Output("portfolio-graph", "figure"),
    Input("portfolios", "value"),
    State("portfolios", "options"),
    State("cached-securities-store", "data"),
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
    Input("portfolio-log-scale-switch", "value"),
    Input("portfolio-percent-scale-switch", "value"),
    Input("portfolio-chart-type-selection", "value"),
    Input("portfolio-graph-xaxis-relayout-store", "data"),
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
    baseline_portfolio: str,
    baseline_portfolio_options: dict[str, str],
    log_scale: bool,
    percent_scale: bool,
    chart_type: str,
    relayout_data: dict | None,
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
    portfolio_options = {
        k: v.replace(", ", "<br>") for k, v in portfolio_options.items()
    }
    portfolios_df = pd.concat(
        [
            transform_data(
                load_portfolio(
                    portfolio_str, currency, adjust_for_inflation, yf_securities
                ),
                "Monthly",
                y_var,
                return_duration,
                return_interval,
                return_type,
            ).rename(portfolio_str)
            for portfolio_str in portfolio_strs
        ],
        axis=1,
    )
    data, layout = update_graph(
        portfolios_df,
        portfolios_colourmap,
        portfolio_options,
        y_var,
        log_scale,
        percent_scale,
        return_duration,
        return_duration_options,
        return_interval,
        return_interval_options,
        return_type,
        return_type_options,
        baseline_portfolio,
        baseline_portfolio_options,
        chart_type,
        relayout_data,
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
    Output("accumulation-investment-amount-label", "children"),
    Output("accumulation-dca-input-container", "style"),
    Input("accumulation-ls-dca-selection", "value"),
)
def update_ls_input_visibility(ls_dca: str):
    if ls_dca == "LS":
        return "Total Investment Amount", {"display": "none"}
    return "Initial Portfolio Value", {"display": "block"}


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
    State("accumulation-monthly-investment-inflation-adjustment-switch", "value"),
    State("accumulation-investment-horizon-input", "value"),
    State("accumulation-dca-length-input", "value"),
    State("accumulation-dca-interval-input", "value"),
    State("accumulation-variable-transaction-fees-input", "value"),
    State("accumulation-fixed-transaction-fees-input", "value"),
    State("accumulation-annualised-holding-fees-input", "value"),
    State("accumulation-ending-value-inflation-adjustment-switch", "value"),
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
    adjust_monthly_investment_for_inflation: bool,
    investment_horizon: int | None,
    dca_length: int | None,
    dca_interval: int | None,
    variable_transaction_fees: int | float | None,
    fixed_transaction_fees: int | float | None,
    annualised_holding_fees: int | float | None,
    adjust_ending_value_for_inflation: bool,
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
            "adjust_monthly_investment_for_inflation": adjust_monthly_investment_for_inflation,
            "dca_length": dca_length,
            "dca_interval": dca_interval,
            "variable_transaction_fees": variable_transaction_fees,
            "fixed_transaction_fees": fixed_transaction_fees,
            "annualised_holding_fees": annualised_holding_fees,
            "adjust_ending_value_for_inflation": adjust_ending_value_for_inflation,
        }
    )
    if ls_dca == "LS":
        strategy_name = (
            f"{strategy_portfolio_options[strategy_portfolio]} {currency}, "
            f"Lump Sum, "
            f"{investment_amount} invested for {investment_horizon} months, "
            f"DCA over {dca_length} months every {dca_interval} months, "
            f"{variable_transaction_fees}% + ${fixed_transaction_fees} Fee, "
            f"{annualised_holding_fees}% p.a. Holding Fees, "
            f"Ending value {'' if adjust_ending_value_for_inflation else 'not '}adjusted for inflation"
        )
    else:
        strategy_name = (
            f"{strategy_portfolio_options[strategy_portfolio]} {currency}, "
            f"DCA, "
            f"{investment_amount} initial capital, "
            f"{monthly_investment} invested monthly for {dca_length} months, "
            f"{dca_interval} months apart, held for {investment_horizon} months, "
            f"Monthly investment {'' if adjust_monthly_investment_for_inflation else 'not '}adjusted for inflation, "
            f"{variable_transaction_fees}% + ${fixed_transaction_fees} Fee, "
            f"{annualised_holding_fees}% p.a. Holding Fees, "
            f"Ending value {'' if adjust_ending_value_for_inflation else 'not '}adjusted for inflation"
        )

    if strategies is None:
        return [strategy_str], {strategy_str: strategy_name}
    if strategy_str in strategies:
        return no_update
    strategies.append(strategy_str)
    strategy_options.update({strategy_str: strategy_name})
    return strategies, strategy_options


@app.callback(
    Output("accumulation-strategy-graph", "figure"),
    Input("accumulation-strategies", "value"),
    State("accumulation-strategies", "options"),
    State("cached-securities-store", "data"),
    prevent_initial_call=True,
)
def update_accumulation_strategy_graph(
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    yf_securities: dict[str, str],
):
    if not strategy_strs:
        return {
            "data": [],
            "layout": {
                "title": "Strategy Performance",
            },
        }
    strategies_colourmap = dict(
        zip(
            strategy_options.keys(),
            cycle(DEFAULT_PLOTLY_COLORS),
        )
    )
    series = []
    for strategy_str in strategy_strs:
        strategy: dict[str, str | int | float] = json.loads(strategy_str)
        strategy_portfolio = str(strategy["strategy_portfolio"])
        currency = str(strategy["currency"])
        ls_dca = str(strategy["ls_dca"])
        investment_amount = float(strategy["investment_amount"])
        investment_horizon = int(strategy["investment_horizon"])
        monthly_investment = float(strategy["monthly_investment"])
        adjust_monthly_investment_for_inflation = bool(
            strategy["adjust_monthly_investment_for_inflation"]
        )
        dca_length = int(strategy["dca_length"])
        dca_interval = int(strategy["dca_interval"])
        variable_transaction_fees = float(strategy["variable_transaction_fees"])
        fixed_transaction_fees = float(strategy["fixed_transaction_fees"])
        annualised_holding_fees = float(strategy["annualised_holding_fees"])
        adjust_ending_value_for_inflation = bool(
            strategy["adjust_ending_value_for_inflation"]
        )

        variable_transaction_fees /= 100
        annualised_holding_fees /= 100
        strategy_series = load_portfolio(
            strategy_portfolio, currency, "No", yf_securities
        )
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
        cpi = us_cpi if currency == "USD" else sg_cpi if currency == "SGD" else None
        if cpi is None:
            raise ValueError("Invalid currency")

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
                    adjust_ending_value_for_inflation,
                    cpi,
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
                    investment_amount,
                    monthly_investment,
                    adjust_monthly_investment_for_inflation,
                    variable_transaction_fees,
                    fixed_transaction_fees,
                    annualised_holding_fees,
                    adjust_ending_value_for_inflation,
                    cpi,
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
                line=go.scatter.Line(color=strategies_colourmap[strategy]),
                name=strategy_options[strategy].replace(", ", "<br>"),
            )
            for strategy in ending_values.columns
        ],
        "layout": go.Layout(
            title="Strategy Performance",
            hovermode="x",
            showlegend=True,
            legend=go.layout.Legend(valign="top"),
        ),
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
    State("withdrawal-monthly-inflation-adjustment-switch", "value"),
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
    adjust_for_inflation: bool,
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

    strategy_name = (
        f"{strategy_portfolio_options[strategy_portfolio]} {currency}, "
        f"{monthly_withdrawal} withdrawn monthly, "
        f"{withdrawal_interval} months apart for {withdrawal_horizon} months, "
        f"Monthly withdrawal {'' if adjust_for_inflation else 'not '}adjusted for inflation, "
        f"{variable_transaction_fees}% + ${fixed_transaction_fees} Fee, "
        f"{annualised_holding_fees}% p.a. Holding Fees"
    )

    if strategies is None:
        return [strategy_str], {strategy_str: strategy_name}
    if strategy_str in strategies:
        return no_update
    strategies.append(strategy_str)
    strategy_options.update({strategy_str: strategy_name})
    return strategies, strategy_options


@app.callback(
    Output("withdrawal-strategy-graph", "figure"),
    Input("withdrawal-strategies", "value"),
    State("withdrawal-strategies", "options"),
    State("cached-securities-store", "data"),
    prevent_initial_call=True,
)
def update_withdrawal_strategy_graph(
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    yf_securities: dict[str, str],
):
    if not strategy_strs:
        return {
            "data": [],
            "layout": {
                "title": "Strategy Performance",
            },
        }
    strategies_colourmap = dict(
        zip(
            strategy_options.keys(),
            cycle(DEFAULT_PLOTLY_COLORS),
        )
    )
    series = []
    for strategy_str in strategy_strs:
        strategy: dict[str, str | int | float] = json.loads(strategy_str)
        strategy_portfolio = str(strategy["strategy_portfolio"])
        currency = str(strategy["currency"])
        initial_capital = float(strategy["initial_capital"])
        withdrawal_horizon = int(strategy["withdrawal_horizon"])
        monthly_withdrawal = float(strategy["monthly_withdrawal"])
        adjust_for_inflation = bool(strategy["adjust_for_inflation"])
        withdrawal_interval = int(strategy["withdrawal_interval"])
        variable_transaction_fees = float(strategy["variable_transaction_fees"])
        fixed_transaction_fees = float(strategy["fixed_transaction_fees"])
        annualised_holding_fees = float(strategy["annualised_holding_fees"])
        variable_transaction_fees /= 100
        annualised_holding_fees /= 100

        strategy_series = load_portfolio(
            strategy_portfolio, currency, "No", yf_securities
        )
        us_cpi = load_us_cpi()["us_cpi"].reindex(strategy_series.index).to_numpy()
        sg_cpi = load_sg_cpi()["sg_cpi"].reindex(strategy_series.index).to_numpy()
        cpi = (
            np.ones(len(strategy_series))
            if not adjust_for_inflation
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
                line=go.scatter.Line(color=strategies_colourmap[strategy]),
                name=strategy_options[strategy].replace(", ", "<br>"),
            )
            for strategy in ending_values.columns
        ],
        "layout": go.Layout(
            title="Strategy Performance",
            hovermode="x",
            showlegend=True,
            legend=go.layout.Legend(valign="top"),
        ),
    }


if __name__ == "__main__":
    app.run(debug=True)
