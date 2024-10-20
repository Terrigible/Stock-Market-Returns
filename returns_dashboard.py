from functools import cache
from glob import glob
from io import StringIO
from itertools import cycle

import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from dash import Dash, no_update, ctx
from dash.dependencies import Input, Output, State
from plotly.colors import DEFAULT_PLOTLY_COLORS

from funcs.calcs_numba import (
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
    read_greatlink_data,
    read_msci_data,
    read_shiller_sp500_data,
    read_ft_data,
)
from layout import app_layout

import json


@cache
def load_df(
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
            f"data/{security["source"]}/{security["msci_base_index"]}/{security["msci_size"]}/{security["msci_style"]}/*{security["msci_tax_treatment"]} {interval}*.xls"
        ).iloc[:, 0]
    elif source == "FRED":
        if security["fred_index"] == "US-T":
            series = load_us_treasury_returns()[security["us_treasury_duration"]]
            if interval == "Monthly":
                series = series.resample("BME").last()
    elif source == "MAS":
        if security["mas_index"] == "SGS":
            series = load_sgs_returns()[security["sgs_duration"]]
            series = series.div(
                load_usdsgd().resample("D").ffill().ffill().reindex(series.index)
            )
            if interval == "Monthly":
                series = series.resample("BME").last()
    elif source == "Others":
        if security["others_index"] == "STI":
            series = read_ft_data("Straits Times Index USD Gross").iloc[:, 0]
        elif security["others_index"] == "SPX":
            series = read_ft_data(
                f"S&P 500 USD {security["others_tax_treatment"]}"
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
        else:
            raise ValueError(f"Invalid index: {security}")
        if interval == "Monthly":
            series = series.resample("BME").last()
    elif source == "YF":
        ticker_currency = security["currency"]
        series = pd.read_json(StringIO(yf_security), orient="index").iloc[:, 0]
        if ticker_currency != "USD":
            if ticker_currency == "SGD":
                series = series.div(
                    load_usdsgd().resample("D").ffill().ffill().reindex(series.index)
                )
            else:
                if ticker_currency == "GBp":
                    series = series.div(100)
                    ticker_currency = "GBP"
                if ticker_currency in load_fred_usd_fx().columns:
                    series = series.mul(
                        load_fred_usd_fx()[ticker_currency]
                        .resample("D")
                        .ffill()
                        .ffill()
                        .reindex(series.index)
                    )
                elif ticker_currency in load_mas_sgd_fx().columns:
                    series = series.mul(
                        load_mas_sgd_fx()[ticker_currency]
                        .resample("D")
                        .ffill()
                        .ffill()
                        .reindex(series.index)
                    )
                    series = series.div(
                        load_usdsgd()
                        .resample("D")
                        .ffill()
                        .ffill()
                        .reindex(series.index)
                    )
        if interval == "Monthly":
            series = series.resample("BME").last()
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
                f"Fundsmith {fund.replace("Class ", "")} EUR Acc"
            ).iloc[:, 0]
        elif fund_company == "Dimensional":
            series = read_ft_data(f"Dimensional {fund} GBP Accumulation").iloc[:, 0]
        else:
            raise ValueError(f"Invalid fund: {fund}")
        if fund_currency != "USD":
            if fund_currency == "SGD":
                series = series.div(
                    load_usdsgd().resample("D").ffill().ffill().reindex(series.index)
                )
            else:
                if fund_currency in load_fred_usd_fx().columns:
                    series = series.mul(
                        load_fred_usd_fx()[fund_currency]
                        .resample("D")
                        .ffill()
                        .ffill()
                        .reindex(series.index)
                    )
                elif fund_currency in load_mas_sgd_fx().columns:
                    series = series.mul(
                        load_mas_sgd_fx()[fund_currency]
                        .resample("D")
                        .ffill()
                        .ffill()
                        .reindex(series.index)
                    )
                    series = series.div(
                        load_usdsgd()
                        .resample("D")
                        .ffill()
                        .ffill()
                        .reindex(series.index)
                    )
        if interval == "Monthly":
            series = series.resample("BME").last()
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
    return series


def transform_df(
    series: pd.Series, interval: str, y_var: str, return_duration: str, return_type: str
) -> pd.Series:
    if y_var == "price":
        return series
    if y_var == "drawdown":
        return series.div(series.cummax()).sub(1)
    return_durations = {
        "1m": 1,
        "3m": 3,
        "6m": 6,
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
    if interval == "Monthly":
        series = series.pct_change(return_durations[return_duration])
    elif interval == "Daily":
        series = series.div(
            series.reindex(
                np.busday_offset(
                    (
                        series.index
                        - pd.offsets.DateOffset(
                            months=return_durations[return_duration]
                        )
                    )
                    .to_numpy()
                    .astype("datetime64[D]"),
                    0,
                    roll="backward",
                ).astype("datetime64[ns]")
            ).set_axis(series.index, axis=0)
        ).sub(1)
    else:
        raise ValueError("Invalid interval")
    if return_type == "annualized":
        series = series.add(1).pow(12 / round(return_durations[return_duration])).sub(1)
    return series.dropna()


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
    Output("others-tax-treatment-selection-container", "style"),
    Input("others-index-selection", "value"),
)
def update_others_tax_treatment_selection_visibility(others_index: str):
    if others_index in ["STI", "AWORLDS"]:
        return {"display": "none"}
    else:
        return {"display": "block"}


@app.callback(
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
            return no_update
        index = (
            json.dumps(
                {
                    "source": index_provider,
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
                        "source": index_provider,
                        "fred_index": fred_index,
                        "us_treasury_duration": us_treasury_duration,
                    }
                ),
                f"{us_treasury_duration_options[us_treasury_duration]} {fred_index_options[fred_index]}",
            )
    elif index_provider == "MAS":
        if mas_index == "SGS":
            index = (
                json.dumps(
                    {
                        "source": index_provider,
                        "mas_index": mas_index,
                        "sgs_duration": sgs_duration,
                    }
                ),
                f"{sgs_duration_options[sgs_duration]} {mas_index_options[mas_index]}",
            )
    else:
        index = (
            json.dumps(
                {
                    "source": index_provider,
                    "others_index": others_index,
                    "others_tax_treatment": others_tax_treatment,
                }
            ),
            f"{others_index_options[others_index]} {others_tax_treatment}",
        )
    if selected_securities is None:
        return [index[0]], {index[0]: index[1]}
    if index[0] in selected_securities:
        return no_update
    selected_securities.append(index[0])
    selected_securities_options.update({index[0]: index[1]})
    return selected_securities, selected_securities_options


@app.callback(
    Output("selected-securities", "value", allow_duplicate=True),
    Output("selected-securities", "options", allow_duplicate=True),
    Output("yf-securities-store", "data"),
    Input("add-stock-etf-button", "n_clicks"),
    State("selected-securities", "value"),
    State("selected-securities", "options"),
    State("stock-etf-input", "value"),
    State("stock-etf-tax-treatment-selection", "value"),
    State("yf-securities-store", "data"),
    prevent_initial_call=True,
)
def add_stock_etf(
    _,
    selected_securities: list[str],
    selected_securities_options: dict[str, str],
    stock_etf: str,
    tax_treatment: str,
    yf_securities_store: dict[str, str],
):
    if ";" in stock_etf:
        return no_update
    for yf_security in yf_securities_store:
        yss_ticker = json.loads(yf_security)["ticker"]
        yss_tax_treatment = json.loads(yf_security)["tax_treatment"]
        if stock_etf == yss_ticker and tax_treatment == yss_tax_treatment:
            if yf_security in selected_securities:
                return no_update
            if yf_security in selected_securities_options:
                selected_securities.append(yf_security)
                return no_update
    ticker = yf.Ticker(stock_etf)
    if ticker.history_metadata == {}:
        return no_update
    if "currency" not in ticker.history_metadata:
        return no_update
    ticker_symbol = ticker.ticker
    currency = ticker.history_metadata["currency"]
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

    return selected_securities, selected_securities_options, yf_securities_store


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
    elif fund_company == "GMO":
        return (
            [
                "Quality Investment Fund",
            ],
            "Quality Investment Fund",
        )
    elif fund_company == "Fundsmith":
        return (
            [
                "Equity Fund Class T",
                "Equity Fund Class R",
            ],
            "Equity Fund Class T",
        )
    elif fund_company == "Dimensional":
        return (["World Equity Fund"], "World Equity Fund")
    else:
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
        currency = "USD"
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
        f'{f'{fund_company} ' if fund_company != 'Great Eastern' else ''}{fund}',
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
    else:
        return {"display": "none"}, []


@app.callback(Output("return-selection", "style"), Input("y-var-selection", "value"))
def update_return_selection_visibility(y_var: str):
    if y_var == "rolling_returns":
        return {"display": "block"}
    else:
        return {"display": "none"}


@app.callback(
    Output("baseline-security-selection", "options"),
    Output("baseline-security-selection", "value"),
    Input("selected-securities", "value"),
    Input("selected-securities", "options"),
    Input("baseline-security-selection", "value"),
)
def update_baseline_security_selection_options(
    selected_securities: list[str],
    selected_securities_options: dict[str, str],
    baseline_security: str,
):
    return {
        "None": "None",
        **{
            k: v
            for k, v in selected_securities_options.items()
            if k in selected_securities
        },
    }, baseline_security if baseline_security in selected_securities else "None"


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
            selected_security: transform_df(
                load_df(
                    selected_security,
                    interval,
                    currency,
                    adjust_for_inflation,
                    yf_securities.get(selected_security),
                ),
                interval,
                y_var,
                return_duration,
                return_type,
            )
            for selected_security in selected_securities
        }
    )
    if y_var == "rolling_returns" and baseline_security != "None":
        df = df.sub(df[baseline_security], axis=0, level=0)
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
        temp_fig = go.Figure(
            data=data, layout=go.Layout(barmode="overlay")
        ).full_figure_for_development(warn=False)

    match y_var:
        case "price":
            title = "Price"
            tickformat = ".2f"
        case "drawdown":
            title = "Drawdown"
            tickformat = ".2%"
        case "rolling_returns":
            title = f"{return_duration_options[return_duration]} {return_type_options[return_type]} Rolling Returns"
            if baseline_security != "None":
                title += f" vs {baseline_security_options[baseline_security]}"
            tickformat = ".2%"
        case _:
            raise ValueError("Invalid y_var")

    layout = go.Layout(
        title=title,
        hovermode="x unified",
        yaxis=dict(
            tickformat=tickformat,
            type="log" if "log" in log_scale else "linear",
        ),
        barmode="overlay"
        if y_var == "rolling_returns" and chart_type == "hist"
        else None,
        showlegend=True,
        shapes=[
            dict(
                type="line",
                x0=0,
                x1=0,
                y0=0,
                y1=temp_fig.layout.yaxis.range[1] * 1.05,
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
        if y_var == "rolling_returns" and chart_type == "hist"
        else None,
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
        if portfolio_allocation_strs is None:
            return [new_allocation], {
                new_allocation: f"{weight}% {security_options[security]}"
            }
        if new_allocation in portfolio_allocation_strs:
            return no_update
        portfolio_allocations: list[dict[str, int | float]] = [
            json.loads(portfolio_allocation_str)
            for portfolio_allocation_str in portfolio_allocation_strs
        ]
        if security in [
            security
            for portfolio_allocation in portfolio_allocations
            for security in portfolio_allocation
        ]:
            old_weight = [
                portfolio_allocation[security]
                for portfolio_allocation in portfolio_allocations
                if security in portfolio_allocation
            ][0]
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
    if portfolio_allocation_strs is None:
        return no_update
    weights = [
        float(value)
        for portfolio_allocation_str in portfolio_allocation_strs
        for value in json.loads(portfolio_allocation_str).values()
    ]
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
    Output("portfolio-graph", "figure"),
    Input("portfolios", "value"),
    State("portfolios", "options"),
    Input("portfolio-currency-selection", "value"),
    State("yf-securities-store", "data"),
)
def update_portfolio_graph(
    portfolio_strs: list[str],
    portfolio_options: dict[str, str],
    currency: str,
    yf_securities: dict[str, str],
):
    if not portfolio_strs:
        return {
            "data": [],
            "layout": {
                "title": "Portfolio Performance",
            },
        }
    data = []
    for portfolio_str in portfolio_strs:
        portfolio: list[str] = json.loads(portfolio_str)
        portfolio_allocations: list[dict[str, int | float]] = [
            json.loads(portfolio_allocation_str)
            for portfolio_allocation_str in portfolio
        ]
        securities = [
            security
            for portfolio_allocation in portfolio_allocations
            for security in portfolio_allocation
        ]
        weights = [
            float(weight)
            for portfolio_allocation in portfolio_allocations
            for weight in portfolio_allocation.values()
        ]
        df = pd.concat(
            [
                load_df(
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
        series = (
            df.pct_change()
            .mul(weights)
            .div(100)
            .sum(axis=1, skipna=False)
            .add(1)
            .cumprod()
        )
        series.iloc[series.index.get_indexer([series.first_valid_index()])[0] - 1] = 1
        data.append(
            go.Scatter(
                x=series.index,
                y=series,
                name=portfolio_options[portfolio_str],
            )
        )
    layout = {
        "title": "Portfolio Performance",
    }
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
    else:
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
            f"{strategy_portfolio_options[strategy_portfolio]} {currency}, Lump Sum, {investment_amount} invested for {investment_horizon} months, DCA over {dca_length} months every {dca_interval} months, {adjust_for_inflation} adjusted for inflation, {variable_transaction_fees}% + ${fixed_transaction_fees} Fee, {annualised_holding_fees}% p.a. Holding Fees",
        )
    else:
        strategy = (
            strategy_str,
            f"{strategy_portfolio_options[strategy_portfolio]} {currency}, DCA, {monthly_investment} invested monthly for {dca_length} months, {dca_interval} months apart, held for {investment_horizon} months, {adjust_for_inflation} adjusted for inflation, {variable_transaction_fees}% + ${fixed_transaction_fees} Fee, {annualised_holding_fees}% p.a. Holding Fees",
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
        strategy: dict[str, str] = json.loads(strategy_str)
        strategy_portfolio = strategy["strategy_portfolio"]
        currency = strategy["currency"]
        ls_dca = strategy["ls_dca"]
        investment_amount = strategy["investment_amount"]
        investment_horizon = strategy["investment_horizon"]
        monthly_investment = strategy["monthly_investment"]
        adjust_for_inflation = strategy["adjust_for_inflation"]
        dca_length = strategy["dca_length"]
        dca_interval = strategy["dca_interval"]
        variable_transaction_fees = strategy["variable_transaction_fees"]
        fixed_transaction_fees = strategy["fixed_transaction_fees"]
        annualised_holding_fees = strategy["annualised_holding_fees"]
        (
            investment_amount,
            investment_horizon,
            monthly_investment,
            dca_length,
            dca_interval,
            variable_transaction_fees,
            fixed_transaction_fees,
            annualised_holding_fees,
        ) = (
            *[
                float(x)
                for x in [
                    investment_amount,
                    investment_horizon,
                    monthly_investment,
                    dca_length,
                    dca_interval,
                    variable_transaction_fees,
                    fixed_transaction_fees,
                    annualised_holding_fees,
                ]
            ],
        )
        portfolio_allocation_strs: list[str] = json.loads(strategy_portfolio)
        portfolio_allocations: list[dict[str, int | float]] = [
            json.loads(portfolio_allocation_str)
            for portfolio_allocation_str in portfolio_allocation_strs
        ]
        investment_horizon = int(investment_horizon)
        dca_length = int(dca_length)
        dca_interval = int(dca_interval)
        variable_transaction_fees /= 100
        annualised_holding_fees /= 100
        securities = [
            security
            for portfolio_allocation in portfolio_allocations
            for security in portfolio_allocation
        ]
        weights = [
            float(weight)
            for portfolio_allocation in portfolio_allocations
            for weight in portfolio_allocation.values()
        ]
        if sum(weights) > 100:
            return no_update
        strategy_series = pd.concat(
            [
                load_df(
                    security,
                    "Monthly",
                    currency,
                    "Yes" if adjust_for_inflation == "Returns" else "No",
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
        us_cpi = (
            load_us_cpi()["us_cpi"]
            .reindex(strategy_series.index)
            .pct_change()
            .to_numpy()
        )
        sg_cpi = (
            load_sg_cpi()["sg_cpi"]
            .reindex(strategy_series.index)
            .pct_change()
            .to_numpy()
        )
        cpi = (
            np.zeros(len(strategy_series))
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
        f"{strategy_portfolio_options[strategy_portfolio]} {currency}, {monthly_withdrawal} withdrawn monthly, {withdrawal_interval} months apart for {withdrawal_horizon} months, {adjust_for_inflation} adjusted for inflation, {variable_transaction_fees}% + ${fixed_transaction_fees} Fee, {annualised_holding_fees}% p.a. Holding Fees",
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
        strategy: dict[str, str] = json.loads(strategy_str)
        strategy_portfolio = strategy["strategy_portfolio"]
        currency = strategy["currency"]
        initial_capital = strategy["initial_capital"]
        withdrawal_horizon = strategy["withdrawal_horizon"]
        monthly_withdrawal = strategy["monthly_withdrawal"]
        adjust_for_inflation = strategy["adjust_for_inflation"]
        withdrawal_interval = strategy["withdrawal_interval"]
        variable_transaction_fees = strategy["variable_transaction_fees"]
        fixed_transaction_fees = strategy["fixed_transaction_fees"]
        annualised_holding_fees = strategy["annualised_holding_fees"]
        (
            initial_capital,
            withdrawal_horizon,
            monthly_withdrawal,
            withdrawal_interval,
            variable_transaction_fees,
            fixed_transaction_fees,
            annualised_holding_fees,
        ) = (
            *[
                float(x)
                for x in [
                    initial_capital,
                    withdrawal_horizon,
                    monthly_withdrawal,
                    withdrawal_interval,
                    variable_transaction_fees,
                    fixed_transaction_fees,
                    annualised_holding_fees,
                ]
            ],
        )
        portfolio_allocation_strs: list[str] = json.loads(strategy_portfolio)
        portfolio_allocations: list[dict[str, int | float]] = [
            json.loads(portfolio_allocation_str)
            for portfolio_allocation_str in portfolio_allocation_strs
        ]
        withdrawal_horizon = int(withdrawal_horizon)
        withdrawal_interval = int(withdrawal_interval)
        variable_transaction_fees /= 100
        annualised_holding_fees /= 100
        securities = [
            security
            for portfolio_allocation in portfolio_allocations
            for security in portfolio_allocation
        ]
        weights = [
            float(weight)
            for portfolio_allocation in portfolio_allocations
            for weight in portfolio_allocation.values()
        ]
        if sum(weights) > 100:
            return no_update
        strategy_series = pd.concat(
            [
                load_df(
                    security,
                    "Monthly",
                    currency,
                    "Yes" if adjust_for_inflation == "Returns" else "No",
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
        us_cpi = (
            load_us_cpi()["us_cpi"]
            .reindex(strategy_series.index)
            .pct_change()
            .to_numpy()
        )
        sg_cpi = (
            load_sg_cpi()["sg_cpi"]
            .reindex(strategy_series.index)
            .pct_change()
            .to_numpy()
        )
        cpi = (
            np.zeros(len(strategy_series))
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
