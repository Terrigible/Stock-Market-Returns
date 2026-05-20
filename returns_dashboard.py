import json
from functools import partial
from io import StringIO
from itertools import cycle
from typing import TypedDict

import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import polars as pl
import python_calamine  # noqa: F401 # Reduces latency for first pd.read_excel call
import scipy.interpolate  # noqa: F401 # Reduces latency for first pd.Resampler.interpolate call
import yfinance as yf
from dash import ClientsideFunction, Dash, ctx, no_update, set_props
from dash.dependencies import Input, Output, State
from plotly.colors import DEFAULT_PLOTLY_COLORS
from pydantic import Json, TypeAdapter, ValidationError
from yfinance.exceptions import YFException

from funcs.calcs_numpy import (
    calculate_dca_portfolio_value_with_fees_and_interest_vector,
    calculate_withdrawal_portfolio_value_with_fees_vector,
    compute_bootstrap_max_drawdown,
    generate_bootstrap_indices,
    simulate_bootstrap_accumulation,
    simulate_bootstrap_withdrawal,
)
from funcs.loaders import (
    download_ft_data,
    fast_bday_downsample,
    fast_bday_upsample,
    get_sgx_dividends,
    load_cpi,
    load_fed_funds_returns,
    load_fred_usd_fx,
    load_mas_sgd_fx,
    load_sgd_interest_rates_returns,
    load_sgs_returns,
    load_us_treasury_returns,
    load_usdsgd,
    read_ft_data,
    read_greatlink_data,
    read_msci_data,
    read_shiller_sp500_data,
)
from layout import app_layout
from models import (
    BacktestYVar,
    BootstrapYVar,
    Currency,
    DimensionalFund,
    DistributionChartType,
    DrawdownType,
    FREDIndex,
    FundCompany,
    FundsmithFund,
    GMOFund,
    GreatLinkFund,
    IndexProvider,
    Interval,
    MASIndex,
    MSCICountryIndex,
    MSCIIndexType,
    MSCIRegionalIndex,
    MSCISize,
    MSCIStyle,
    OthersIndex,
    ReturnAnnualisation,
    ReturnDuration,
    ReturnInterval,
    RollingReturnsPresentation,
    SGSDuration,
    TaxTreatment,
    USTreasuryDuration,
    YVar,
)
from schemas import (
    AccumulationBootstrapStrategy,
    AccumulationStrategy,
    Allocation,
    DimensionalSecurity,
    FredFfrSecurity,
    FredTreasurySecurity,
    FtSecurity,
    FundSecurity,
    FundsmithSecurity,
    GMOSecurity,
    GreatlinkSecurity,
    IndexSecurity,
    MasSgsSecurity,
    MasSoraSecurity,
    MsciSecurity,
    Portfolio,
    Security,
    ShillerSpxSecurity,
    SpxSecurity,
    SreitSecurity,
    WithdrawalBootstrapStrategy,
    WithdrawalStrategy,
    YfSecurity,
    parse_security,
)
from update_graph import GraphParams, PrevLayout, RelayoutData

yf.config.debug.hide_exceptions = False


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
):
    if currency == "USD":
        return series
    usd_sgd = load_usdsgd().resample("D").ffill().ffill().reindex(series.index)
    if currency == "SGD":
        return series.div(usd_sgd)
    usd_fx = load_fred_usd_fx().resample("D").ffill().ffill().reindex(series.index)
    if currency == "GBp":
        series = series.div(100)
        currency = "GBP"
    if currency in usd_fx.columns:
        return series.mul(usd_fx[currency])
    sgd_fx = load_mas_sgd_fx().resample("D").ffill().ffill().reindex(series.index)
    if currency in sgd_fx.columns:
        return series.mul(sgd_fx[currency]).div(usd_sgd)
    return series


def load_data(
    security: Security,
    interval: Interval,
    currency: Currency,
    adjust_for_inflation: bool,
    cached_security: str | None,
):
    if isinstance(security, MsciSecurity):
        series = read_msci_data(
            f"data/"
            f"MSCI/"
            f"{security.msci_base_index}/"
            f"{security.msci_size}/"
            f"{security.msci_style}/"
            f"*{security.msci_tax_treatment} {interval}.csv"
        )
    elif isinstance(security, FredTreasurySecurity):
        series = (
            load_us_treasury_returns()[security.us_treasury_duration]
            .dropna()
            .pipe(fast_bday_downsample)
        )
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
    elif isinstance(security, FredFfrSecurity):
        fed_funds_returns = load_fed_funds_returns()
        series = fed_funds_returns.pipe(fast_bday_downsample)
        if interval == Interval.MONTHLY:
            series = fed_funds_returns.pipe(resample_bme)
    elif isinstance(security, MasSgsSecurity):
        series = (
            load_sgs_returns()[security.sgs_duration]
            .dropna()
            .pipe(fast_bday_downsample)
        )
        series = convert_price_to_usd(series, "SGD")
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
    elif isinstance(security, MasSoraSecurity):
        sgd_interest_rates_returns = load_sgd_interest_rates_returns()
        sgd_interest_rates_returns = convert_price_to_usd(
            sgd_interest_rates_returns, "SGD"
        )
        series = sgd_interest_rates_returns.pipe(fast_bday_downsample)
        if interval == Interval.MONTHLY:
            series = sgd_interest_rates_returns.pipe(resample_bme)
    elif isinstance(security, (SpxSecurity, ShillerSpxSecurity, SreitSecurity)):
        if isinstance(security, (SpxSecurity)):
            series = read_ft_data(f"S&P 500 USD {security.others_tax_treatment}")
            if interval == Interval.DAILY:
                series = series.pipe(fast_bday_upsample)
        elif isinstance(security, ShillerSpxSecurity):
            series = read_shiller_sp500_data(security.others_tax_treatment)
            if interval == Interval.DAILY:
                series = series.pipe(fast_bday_upsample)
        elif isinstance(security, SreitSecurity):
            series = read_ft_data("iEdge S-REIT Leaders USD Gross")
        else:
            raise ValueError(f"Invalid index: {security}")
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
    elif isinstance(security, (YfSecurity, FtSecurity)):
        ticker_currency = security.currency
        series = pd.read_json(StringIO(cached_security), orient="index", typ="series")
        series = convert_price_to_usd(series, ticker_currency)
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
    elif isinstance(
        security,
        (GreatlinkSecurity, GMOSecurity, FundsmithSecurity, DimensionalSecurity),
    ):
        if isinstance(security, GreatlinkSecurity):
            series = read_greatlink_data(security.fund)
        elif isinstance(security, GMOSecurity):
            series = read_ft_data("GMO Quality Investment Fund")
        elif isinstance(security, FundsmithSecurity):
            series = read_ft_data(
                f"Fundsmith {security.fund.replace('Class ', '')} EUR Acc"
            )
        elif isinstance(security, DimensionalSecurity):
            series = read_ft_data(f"Dimensional {security.fund} GBP Accumulation")
        else:
            raise ValueError(f"Invalid fund: {security.fund}")
        series = convert_price_to_usd(series, security.currency)
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
    else:
        raise ValueError(f"Invalid index: {security}")
    if currency == Currency.SGD:
        series = series.mul(
            load_usdsgd().resample("D").ffill().ffill().reindex(series.index)
        )
    if adjust_for_inflation:
        series = series.div(
            load_cpi(currency)
            .resample("D")
            .interpolate("pchip")
            .ffill()
            .reindex(series.index)
        )
    return series.rename_axis("date").rename("price")


def transform_data(
    series: pd.Series,
    interval: Interval,
    y_var: YVar,
    return_duration: ReturnDuration,
    return_interval: ReturnInterval,
    return_annualisation: ReturnAnnualisation,
) -> pd.Series:
    if y_var == YVar.PRICE:
        return series
    if y_var == YVar.DRAWDOWN:
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
    if y_var == YVar.ROLLING_RETURNS:
        if interval == Interval.MONTHLY:
            series = series.pct_change(return_durations[return_duration])
        elif interval == Interval.DAILY:
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
        if return_annualisation == ReturnAnnualisation.ANNUALISED:
            series = series.add(1).pow(12 / return_durations[return_duration]).sub(1)
        return series.dropna()
    if y_var == YVar.CALENDAR_RETURNS:
        df_pl = pl.from_pandas(series.reset_index())
        df_pl = (
            df_pl.sort("date")
            .set_sorted("date")
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


app = Dash(
    serve_locally=False,
    eager_loading=True,
    compress=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)

server = app.server

app.layout = app_layout


app.clientside_callback(
    ClientsideFunction(
        namespace="visibility", function_name="updateSecuritySelectionVisibility"
    ),
    Output("index-selection-container", "style"),
    Output("fund-selection-container", "style"),
    Output("yf-security-selection-container", "style"),
    Output("ft-security-selection-container", "style"),
    Input("security-type-selection", "value"),
    Input("security-type-selection", "options"),
)


app.clientside_callback(
    ClientsideFunction(
        namespace="visibility", function_name="updateIndexSelectionVisibility"
    ),
    Output("msci-index-selection-container", "style"),
    Output("fred-index-selection-container", "style"),
    Output("mas-index-selection-container", "style"),
    Output("others-index-selection-container", "style"),
    Input("index-provider-selection", "value"),
    Input("index-provider-selection", "options"),
)


@app.callback(
    Output("msci-index-selection", "options"),
    Output("msci-index-selection", "value"),
    Input("msci-index-type-selection", "value"),
)
def update_msci_index_options(index_type: MSCIIndexType):
    if index_type == MSCIIndexType.REGIONAL:
        return MSCIRegionalIndex.to_dict(), MSCIRegionalIndex.WORLD
    if index_type == MSCIIndexType.COUNTRY:
        return MSCICountryIndex.to_dict(), MSCICountryIndex.AUSTRALIA


app.clientside_callback(
    ClientsideFunction(
        namespace="visibility",
        function_name="updateOthersTaxTreatmentSelectionVisibility",
    ),
    Output("others-tax-treatment-selection-container", "style"),
    Input("others-index-selection", "value"),
)


app.clientside_callback(
    ClientsideFunction(
        namespace="visibility", function_name="updateFredDurationSelectionVisibility"
    ),
    Output("us-treasury-index-selection-container", "style"),
    Input("fred-index-selection", "value"),
)


app.clientside_callback(
    ClientsideFunction(
        namespace="visibility", function_name="updateMasDurationSelectionVisibility"
    ),
    Output("sgs-index-selection-container", "style"),
    Input("mas-index-selection", "value"),
)


app.clientside_callback(
    ClientsideFunction(namespace="toast", function_name="updateToast"),
    Output("toast", "children"),
    Output("toast", "is_open"),
    Input("toast-store", "data"),
)


@app.callback(
    Output("selected-securities", "value"),
    Output("selected-securities", "options"),
    Input("add-index-button", "n_clicks"),
    State("selected-securities", "value"),
    State("selected-securities", "options"),
    State("index-provider-selection", "value"),
    State("msci-index-selection", "value"),
    State("msci-size-selection", "value"),
    State("msci-style-selection", "value"),
    State("msci-tax-treatment-selection", "value"),
    State("fred-index-selection", "value"),
    State("us-treasury-duration-selection", "value"),
    State("mas-index-selection", "value"),
    State("sgs-duration-selection", "value"),
    State("others-index-selection", "value"),
    State("others-tax-treatment-selection", "value"),
)
def add_index(
    _,
    selected_securities: None | list[str],
    selected_securities_options: dict[str, str],
    index_provider: IndexProvider,
    msci_base_index: MSCIRegionalIndex | MSCICountryIndex,
    msci_size: MSCISize,
    msci_style: MSCIStyle,
    msci_tax_treatment: TaxTreatment,
    fred_index: FREDIndex,
    us_treasury_duration: USTreasuryDuration,
    mas_index: MASIndex,
    sgs_duration: SGSDuration,
    others_index: OthersIndex,
    others_tax_treatment: TaxTreatment,
):
    try:
        model: IndexSecurity = TypeAdapter(IndexSecurity).validate_python(
            {
                "source": index_provider,
                "msci_base_index": msci_base_index,
                "msci_size": msci_size,
                "msci_style": msci_style,
                "msci_tax_treatment": msci_tax_treatment,
                "fred_index": fred_index,
                "us_treasury_duration": us_treasury_duration,
                "mas_index": mas_index,
                "sgs_duration": sgs_duration,
                "others_index": others_index,
                "others_tax_treatment": others_tax_treatment,
            }
        )
    except ValidationError as e:
        set_props(
            "toast-store",
            {
                "data": "\n".join(
                    err["msg"]
                    for err in e.errors(
                        include_url=False,
                        include_context=False,
                        include_input=False,
                    )
                )
            },
        )
        return no_update
    index_json = model.model_dump_json(exclude_none=True)
    index_name = model.label

    if selected_securities is None:
        return [index_json], {index_json: index_name}
    if index_json in selected_securities:
        return no_update
    selected_securities.append(index_json)
    selected_securities_options.update({index_json: index_name})
    return selected_securities, selected_securities_options


@app.callback(
    Output("selected-securities", "value", allow_duplicate=True),
    Output("selected-securities", "options", allow_duplicate=True),
    Output("cached-securities-store", "data"),
    Input("add-yf-security-button", "n_clicks"),
    State("selected-securities", "value"),
    State("selected-securities", "options"),
    State("yf-security-input", "value"),
    State("yf-security-tax-treatment-selection", "value"),
    State("yf-invalid-securities-store", "data"),
    State("cached-securities-store", "data"),
    prevent_initial_call=True,
    running=[(Output("add-yf-security-button", "disabled"), True, False)],
)
def add_yf_security(
    _,
    selected_securities: list[str],
    selected_securities_options: dict[str, str],
    yf_security: str | None,
    tax_treatment: TaxTreatment,
    yf_invalid_securities_store: list[str],
    yf_securities_store: dict[str, str],
):
    if not yf_security:
        return no_update
    if ";" in yf_security:
        set_props("toast-store", {"data": "Invalid character: ;"})
        return no_update
    if yf_security in yf_invalid_securities_store:
        set_props("toast-store", {"data": "The selected ticker is not available"})
        return no_update
    for stored_yf_security_str in yf_securities_store:
        stored_yf_security = json.loads(stored_yf_security_str)
        if yf_security != stored_yf_security["ticker"]:
            continue
        if tax_treatment != stored_yf_security["tax_treatment"]:
            continue
        if stored_yf_security_str in selected_securities:
            return no_update
        if stored_yf_security_str in selected_securities_options:
            selected_securities.append(stored_yf_security_str)
            return (
                selected_securities,
                selected_securities_options,
                no_update,
            )
    ticker = yf.Ticker(yf_security)
    if ticker.history_metadata == {}:
        yf_invalid_securities_store.append(yf_security)
        set_props("toast-store", {"data": "The selected ticker is not available"})
        set_props("yf-invalid-securities-store", {"data": yf_invalid_securities_store})
        return no_update
    ticker_symbol = ticker.ticker
    if not ticker_symbol:
        yf_invalid_securities_store.append(yf_security)
        set_props("toast-store", {"data": "The selected ticker is not available"})
        set_props("yf-invalid-securities-store", {"data": yf_invalid_securities_store})
        return no_update
    if "currency" not in ticker.history_metadata:
        currency = "USD"
        set_props(
            "toast-store",
            {
                "data": "The selected ticker does not have currency information. Defaulting to USD."
            },
        )
    else:
        currency = ticker.history_metadata["currency"]
    new_yf_security = YfSecurity(
        ticker=ticker_symbol,
        currency=currency,
        tax_treatment=tax_treatment,
    )
    new_yf_security_json = new_yf_security.model_dump_json(exclude_none=True)
    selected_securities.append(new_yf_security_json)
    selected_securities_options[new_yf_security_json] = new_yf_security.label
    try:
        df = ticker.history(period="max", auto_adjust=False).tz_localize(None)
    except YFException as e:
        yf_invalid_securities_store.append(yf_security)
        set_props("toast-store", {"data": f"The selected ticker is not available: {e}"})
        set_props("yf-invalid-securities-store", {"data": yf_invalid_securities_store})
        return no_update
    if tax_treatment == TaxTreatment.NET and "Dividends" in df.columns:
        manually_adjusted = (
            df["Close"]
            .add(df["Dividends"].mul(0.7))
            .div(df["Close"].shift(1))
            .fillna(1)
            .cumprod()
        )
        df["Adj Close"] = manually_adjusted.div(manually_adjusted.iloc[-1]).mul(
            df["Adj Close"].iloc[-1]
        )
    yf_securities_store[new_yf_security_json] = df["Adj Close"].to_json(
        orient="index", date_format="iso"
    )

    return (
        selected_securities,
        selected_securities_options,
        yf_securities_store,
    )


@app.callback(
    Output("selected-securities", "value", allow_duplicate=True),
    Output("selected-securities", "options", allow_duplicate=True),
    Output("cached-securities-store", "data", allow_duplicate=True),
    Output("ft-api-key-store", "data"),
    Input("add-ft-security-button", "n_clicks"),
    State("selected-securities", "value"),
    State("selected-securities", "options"),
    State("ft-security-input", "value"),
    State("ft-invalid-securities-store", "data"),
    State("cached-securities-store", "data"),
    State("ft-api-key-store", "data"),
    prevent_initial_call=True,
    running=[(Output("add-ft-security-button", "disabled"), True, False)],
)
def add_ft_security(
    _,
    selected_securities: list[str],
    selected_securities_options: dict,
    ft_security: str,
    ft_invalid_securities_store: list[str],
    ft_securities_store: dict[str, str],
    stored_ft_api_key: str | None,
):
    if not ft_security:
        return no_update
    if ";" in ft_security:
        set_props("toast-store", {"data": "Invalid character: ;"})
        return no_update
    if ft_security in ft_invalid_securities_store:
        set_props("toast-store", {"data": "The selected ticker is not available"})
        return no_update
    for ft_security_str in ft_securities_store:
        stored_ft_security = json.loads(ft_security_str)
        if ft_security != stored_ft_security["ticker"]:
            continue
        if ft_security_str in selected_securities:
            return no_update
        if ft_security_str in selected_securities_options:
            selected_securities.append(ft_security_str)
            return (
                selected_securities,
                selected_securities_options,
                no_update,
                no_update,
            )
    try:
        series, ticker, currency, ft_api_key = download_ft_data(
            ft_security, stored_ft_api_key
        )
    except ValueError as e:
        ft_invalid_securities_store.append(ft_security)
        set_props("toast-store", {"data": f"Error: {e}"})
        set_props("ft-invalid-securities-store", {"data": ft_invalid_securities_store})
        return no_update

    dividends = False

    if ft_security.upper().endswith(":SES"):
        dividends = True
        dividends_series = get_sgx_dividends(ticker.removesuffix(":SES"))
        dividends_series = dividends_series.reindex(series.index, fill_value=0)
        manually_adjusted = (
            series.add(dividends_series).div(series.shift(1)).fillna(1).cumprod()
        )
        series = manually_adjusted.div(manually_adjusted.iloc[-1]).mul(series.iloc[-1])

    new_ft_security = FtSecurity(
        ticker=ticker,
        currency=currency,
        dividends=dividends,
    )
    new_ft_security_str = new_ft_security.model_dump_json(exclude_none=True)
    selected_securities.append(new_ft_security_str)
    selected_securities_options[new_ft_security_str] = new_ft_security.label

    ft_securities_store[new_ft_security_str] = series.to_json(
        orient="index", date_format="iso"
    )

    return (
        selected_securities,
        selected_securities_options,
        ft_securities_store,
        ft_api_key,
    )


@app.callback(
    Output("fund-selection", "options"),
    Output("fund-selection", "value"),
    Input("fund-company-selection", "value"),
)
def update_fund_selection_options(fund_company: FundCompany):
    if fund_company == FundCompany.GREATLINK:
        return GreatLinkFund.to_dict(), GreatLinkFund.ASEAN_GROWTH_FUND
    if fund_company == FundCompany.GMO:
        return GMOFund.to_dict(), GMOFund.QUALITY_INVESTMENT_FUND
    if fund_company == FundCompany.FUNDSMITH:
        return FundsmithFund.to_dict(), FundsmithFund.EQUITY_FUND_CLASS_T
    if fund_company == FundCompany.DIMENSIONAL:
        return DimensionalFund.to_dict(), DimensionalFund.WORLD_EQUITY_FUND
    return (
        {},
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
    fund_company: FundCompany,
    fund: GreatLinkFund | GMOFund | FundsmithFund | DimensionalFund,
):
    fund_security: FundSecurity = TypeAdapter(FundSecurity).validate_python(
        {
            "fund_company": fund_company,
            "fund": fund,
        }
    )
    security_json = fund_security.model_dump_json(exclude_none=True)
    security_name = fund_security.label
    if security_json in selected_securities:
        return no_update
    selected_securities.append(security_json)
    selected_securities_options.update({security_json: security_name})
    return selected_securities, selected_securities_options


app.clientside_callback(
    ClientsideFunction(
        namespace="visibility", function_name="updateSelectionVisibility"
    ),
    Output("price-selection-container", "style"),
    Output("return-selection", "style"),
    Output("rolling-return-selection-container", "style"),
    Output("calendar-return-selection-container", "style"),
    Input("y-var-selection", "value"),
)


app.clientside_callback(
    ClientsideFunction(
        namespace="visibility",
        function_name="updateRollingReturnsDistributionChartTypeVisibility",
    ),
    Output("rolling-returns-distribution-chart-type-selection-container", "style"),
    Input("rolling-returns-presentation-selection", "value"),
)


app.clientside_callback(
    ClientsideFunction(
        namespace="options",
        function_name="updateBaselineSecuritySelectionOptions",
    ),
    Output("baseline-security-selection", "options"),
    Output("baseline-security-selection", "value"),
    Output("baseline-security-selection", "disabled"),
    Input("selected-securities", "value"),
    Input("selected-securities", "options"),
    Input("baseline-security-selection", "value"),
    prevent_initial_call=True,
)


app.clientside_callback(
    ClientsideFunction(namespace="state", function_name="updateLastLayoutStore"),
    Output("graph-last-layout-state-store", "data"),
    Input("graph", "figure"),
    State("y-var-selection", "value"),
    prevent_initial_call=True,
)


@app.callback(
    Output("graph", "figure"),
    Input("selected-securities", "value"),
    Input("selected-securities", "options"),
    Input("cached-securities-store", "data"),
    Input("currency-selection", "value"),
    Input("inflation-adjustment-switch", "value"),
    Input("y-var-selection", "value"),
    Input("log-scale-switch", "value"),
    Input("percent-scale-switch", "value"),
    Input("auto-scale-switch", "value"),
    Input("return-duration-selection", "value"),
    Input("return-interval-selection", "value"),
    Input("return-annualisation-selection", "value"),
    Input("interval-selection", "value"),
    Input("baseline-security-selection", "value"),
    Input("baseline-security-selection", "options"),
    Input("rolling-returns-presentation-selection", "value"),
    Input("rolling-returns-distribution-chart-type-selection", "value"),
    Input("graph", "relayoutData"),
    State("graph-last-layout-state-store", "data"),
)
def update_security_graph(
    selected_securities_strs: list[str],
    selected_securities_options: dict[str, str],
    cached_securities: dict[str, str],
    currency: Currency,
    adjust_for_inflation: bool,
    y_var: YVar,
    log_scale: bool,
    percent_scale: bool,
    auto_scale: bool,
    return_duration: ReturnDuration,
    return_interval: ReturnInterval,
    return_annualisation: ReturnAnnualisation,
    interval: Interval,
    baseline_security: str,
    baseline_security_options: dict[str, str],
    rolling_returns_presentation: RollingReturnsPresentation,
    rolling_returns_distribution_chart_type: DistributionChartType,
    relayout_data: RelayoutData | None,
    prev_layout: PrevLayout | None,
):
    if not selected_securities_strs:
        return no_update
    securities_colourmap = dict(
        zip(
            selected_securities_options.keys(),
            cycle(DEFAULT_PLOTLY_COLORS),
        )
    )
    selected_securities = TypeAdapter(list[Json[Security]]).validate_python(
        selected_securities_strs
    )
    df = pd.DataFrame(
        {
            selected_security.model_dump_json(): transform_data(
                load_data(
                    selected_security,
                    Interval.MONTHLY if y_var == YVar.CALENDAR_RETURNS else interval,
                    currency,
                    adjust_for_inflation,
                    cached_securities.get(selected_security.model_dump_json()),
                ),
                interval,
                y_var,
                return_duration,
                return_interval,
                return_annualisation,
            )
            for selected_security in selected_securities
        }
    )

    uirevision = (
        currency
        + str(adjust_for_inflation)
        + y_var
        + str(log_scale)
        + str(percent_scale)
        + return_duration
        + return_interval
        + return_annualisation
        + baseline_security
        + rolling_returns_presentation
        + rolling_returns_distribution_chart_type
    )

    relayout_data = relayout_data or {"autosize": True}

    graph_params: GraphParams = TypeAdapter(GraphParams).validate_python(
        {
            "df": df,
            "trace_colourmap": securities_colourmap,
            "trace_options": selected_securities_options,
            "y_var": y_var,
            "log_scale": log_scale,
            "percent_scale": percent_scale,
            "auto_scale": auto_scale,
            "return_duration": return_duration,
            "return_interval": return_interval,
            "return_annualisation": return_annualisation,
            "baseline_trace": baseline_security,
            "baseline_trace_options": baseline_security_options,
            "rolling_returns_presentation": rolling_returns_presentation,
            "rolling_returns_distribution_chart_type": rolling_returns_distribution_chart_type,
            "relayout_data": relayout_data,
            "uirevision": uirevision,
            "prev_layout": prev_layout,
        }
    )

    data, layout = graph_params.update_graph()
    return dict(data=data, layout=layout)


app.clientside_callback(
    ClientsideFunction(
        namespace="options",
        function_name="updateSecuritySelectionOptions",
    ),
    Output("portfolio-security-selection", "options"),
    Output("portfolio-security-selection", "value"),
    Input("selected-securities", "options"),
)


@app.callback(
    Output("portfolio-allocations", "value"),
    Output("portfolio-allocations", "options"),
    Input("add-security-button", "n_clicks"),
    Input("portfolio-allocations", "value"),
    State("portfolio-security-selection", "value"),
    State("security-weight", "value"),
    allow_duplicate=True,
    prevent_initial_call=True,
)
def add_allocation(
    _,
    portfolio_allocation_strs: list[str] | None,
    security_str: str,
    weight: float | int | None,
):
    if ctx.triggered_id == "add-security-button":
        if weight is None:
            return no_update
        portfolio = Portfolio(
            TypeAdapter(list[Json[Allocation]]).validate_python(
                portfolio_allocation_strs or []
            )
        )
        new_allocation = Allocation(
            security=parse_security(security_str),
            weight=weight,
        )
        if new_allocation in portfolio.root:
            return no_update
        portfolio.add_allocation(new_allocation=new_allocation)
        return list(portfolio.to_plotly_options().keys()), portfolio.to_plotly_options()
    elif ctx.triggered_id == "portfolio-allocations":
        if portfolio_allocation_strs is None:
            raise ValueError("This should not happen")
        portfolio = Portfolio(
            TypeAdapter(list[Json[Allocation]]).validate_python(
                portfolio_allocation_strs
            )
        )
        return list(portfolio.to_plotly_options().keys()), portfolio.to_plotly_options()
    return no_update


app.clientside_callback(
    ClientsideFunction(
        namespace="update_values",
        function_name="portfolioWeightsSum",
    ),
    Output("portfolio-weights-sum", "children"),
    Input("portfolio-allocations", "value"),
    prevent_initial_call=True,
)


@app.callback(
    Output("portfolios", "value"),
    Output("portfolios", "options"),
    Output("portfolio-allocations", "value", allow_duplicate=True),
    Output("portfolio-allocations", "options", allow_duplicate=True),
    Input("add-portfolio-button", "n_clicks"),
    State("portfolios", "value"),
    State("portfolios", "options"),
    State("portfolio-allocations", "value"),
    prevent_initial_call=True,
)
def add_portfolio(
    _,
    portfolio_strs: list[str] | None,
    portfolio_options: dict[str, str],
    portfolio_allocation_strs: list[str] | None,
):
    if not portfolio_allocation_strs:
        return no_update
    portfolio = Portfolio(
        TypeAdapter(list[Json[Allocation]]).validate_python(portfolio_allocation_strs)
    )
    if sum([allocation.weight for allocation in portfolio.root]) != 100:
        return no_update
    portfolio_str = portfolio.model_dump_json(exclude_none=True)
    if portfolio_strs is None:
        return ([portfolio_str], {portfolio_str: portfolio.label}, [], {})
    if portfolio_str in portfolio_strs:
        return no_update
    portfolio_strs.append(portfolio_str)
    portfolio_options.update({portfolio_str: portfolio.label})
    return (portfolio_strs, portfolio_options, [], {})


app.clientside_callback(
    ClientsideFunction(
        namespace="visibility", function_name="updateSelectionVisibility"
    ),
    Output("portfolio-price-selection-container", "style"),
    Output("portfolio-return-selection", "style"),
    Output("portfolio-rolling-return-selection-container", "style"),
    Output("portfolio-calendar-return-selection-container", "style"),
    Input("portfolio-y-var-selection", "value"),
)


app.clientside_callback(
    ClientsideFunction(
        namespace="visibility",
        function_name="updateRollingReturnsDistributionChartTypeVisibility",
    ),
    Output(
        "portfolio-rolling-returns-distribution-chart-type-selection-container", "style"
    ),
    Input("portfolio-rolling-returns-presentation-selection", "value"),
)


app.clientside_callback(
    ClientsideFunction(
        namespace="options",
        function_name="updateBaselineSecuritySelectionOptions",
    ),
    Output("portfolio-baseline-security-selection", "options"),
    Output("portfolio-baseline-security-selection", "value"),
    Output("portfolio-baseline-security-selection", "disabled"),
    Input("portfolios", "value"),
    Input("portfolios", "options"),
    Input("portfolio-baseline-security-selection", "value"),
    prevent_initial_call=True,
)


def load_portfolio(
    portfolio: Portfolio,
    currency: Currency,
    adjust_for_inflation: bool,
    yf_securities: dict[str, str],
):
    securities = [allocation.security for allocation in portfolio.root]
    weights = [allocation.weight for allocation in portfolio.root]
    portfolio_df = pd.concat(
        [
            load_data(
                security,
                Interval.MONTHLY,
                currency,
                adjust_for_inflation,
                yf_securities.get(security.model_dump_json()),
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
        portfolio_series.index.get_indexer(
            pd.Index([portfolio_series.first_valid_index()])
        )[0]
        - 1
    ] = 1
    portfolio_series = portfolio_series.dropna()
    return portfolio_series


app.clientside_callback(
    ClientsideFunction(namespace="state", function_name="updateLastLayoutStore"),
    Output("portfolio-graph-last-layout-state-store", "data"),
    Input("portfolio-graph", "figure"),
    State("portfolio-y-var-selection", "value"),
    prevent_initial_call=True,
)


@app.callback(
    Output("portfolio-graph", "figure"),
    Input("portfolios", "value"),
    Input("portfolio-currency-selection", "value"),
    Input("portfolio-inflation-adjustment-switch", "value"),
    Input("portfolio-y-var-selection", "value"),
    Input("portfolio-return-duration-selection", "value"),
    Input("portfolio-return-interval-selection", "value"),
    Input("portfolio-return-annualisation-selection", "value"),
    Input("portfolio-baseline-security-selection", "value"),
    Input("portfolio-baseline-security-selection", "options"),
    Input("portfolio-log-scale-switch", "value"),
    Input("portfolio-percent-scale-switch", "value"),
    Input("portfolio-auto-scale-switch", "value"),
    Input("portfolio-rolling-returns-presentation-selection", "value"),
    Input("portfolio-rolling-returns-distribution-chart-type-selection", "value"),
    Input("portfolio-graph", "relayoutData"),
    State("portfolios", "options"),
    State("cached-securities-store", "data"),
    State("portfolio-graph-last-layout-state-store", "data"),
    prevent_initial_call=True,
)
def update_portfolio_graph(
    portfolio_strs: list[str],
    currency: Currency,
    adjust_for_inflation: bool,
    y_var: YVar,
    return_duration: ReturnDuration,
    return_interval: ReturnInterval,
    return_annualisation: ReturnAnnualisation,
    baseline_portfolio: str,
    baseline_portfolio_options: dict[str, str],
    log_scale: bool,
    percent_scale: bool,
    auto_scale: bool,
    rolling_returns_presentation: RollingReturnsPresentation,
    rolling_returns_distribution_chart_type: DistributionChartType,
    relayout_data: RelayoutData | None,
    portfolio_options: dict[str, str],
    yf_securities: dict[str, str],
    prev_layout: PrevLayout | None,
):
    if not portfolio_strs:
        return no_update
    portfolios_colourmap = dict(
        zip(
            portfolio_options.keys(),
            cycle(DEFAULT_PLOTLY_COLORS),
        )
    )
    portfolio_options = {
        k: v.replace("\n", "<br>") for k, v in portfolio_options.items()
    }
    portfolios = TypeAdapter(list[Json[Portfolio]]).validate_python(portfolio_strs)
    portfolios_df = pd.concat(
        [
            transform_data(
                load_portfolio(
                    portfolio, currency, adjust_for_inflation, yf_securities
                ),
                Interval.MONTHLY,
                y_var,
                return_duration,
                return_interval,
                return_annualisation,
            ).rename(portfolio.model_dump_json())
            for portfolio in portfolios
        ],
        axis=1,
    )

    uirevision = (
        currency
        + str(adjust_for_inflation)
        + y_var
        + str(log_scale)
        + str(percent_scale)
        + return_duration
        + return_interval
        + return_annualisation
        + baseline_portfolio
        + rolling_returns_presentation
        + rolling_returns_distribution_chart_type
    )

    relayout_data = relayout_data or {"autosize": True}

    graph_params: GraphParams = TypeAdapter(GraphParams).validate_python(
        {
            "df": portfolios_df,
            "trace_colourmap": portfolios_colourmap,
            "trace_options": portfolio_options,
            "y_var": y_var,
            "log_scale": log_scale,
            "percent_scale": percent_scale,
            "auto_scale": auto_scale,
            "return_duration": return_duration,
            "return_interval": return_interval,
            "return_annualisation": return_annualisation,
            "baseline_trace": baseline_portfolio,
            "baseline_trace_options": baseline_portfolio_options,
            "rolling_returns_presentation": rolling_returns_presentation,
            "rolling_returns_distribution_chart_type": rolling_returns_distribution_chart_type,
            "relayout_data": relayout_data,
            "uirevision": uirevision,
            "prev_layout": prev_layout,
        }
    )
    data, layout = graph_params.update_graph()
    return dict(data=data, layout=layout)


app.clientside_callback(
    ClientsideFunction(
        namespace="options",
        function_name="updateStrategyPortfolioOptions",
    ),
    Output("backtest-accumulation-strategy-portfolio", "options"),
    Output("backtest-withdrawal-strategy-portfolio", "options"),
    Output("bootstrap-accumulation-strategy-portfolio", "options"),
    Output("bootstrap-withdrawal-strategy-portfolio", "options"),
    Output("backtest-accumulation-strategy-portfolio", "value"),
    Output("backtest-withdrawal-strategy-portfolio", "value"),
    Output("bootstrap-accumulation-strategy-portfolio", "value"),
    Output("bootstrap-withdrawal-strategy-portfolio", "value"),
    Input("portfolios", "options"),
    prevent_initial_call=True,
)


app.clientside_callback(
    ClientsideFunction(
        namespace="visibility", function_name="updateStrategyDrawdownTypeVisibility"
    ),
    Output("backtest-accumulation-drawdown-type-container", "style"),
    Input("backtest-accumulation-y-var-selection", "value"),
)


app.clientside_callback(
    ClientsideFunction(
        namespace="visibility", function_name="updateStrategyDrawdownTypeVisibility"
    ),
    Output("backtest-withdrawal-drawdown-type-container", "style"),
    Input("backtest-withdrawal-y-var-selection", "value"),
)


@app.callback(
    Output("backtest-accumulation-strategies", "value"),
    Output("backtest-accumulation-strategies", "options"),
    Input("backtest-accumulation-add-strategy-button", "n_clicks"),
    State("backtest-accumulation-strategies", "value"),
    State("backtest-accumulation-strategies", "options"),
    State("backtest-accumulation-strategy-portfolio", "value"),
    State("backtest-accumulation-strategy-currency-selection", "value"),
    State("backtest-accumulation-investment-amount-input", "value"),
    State("backtest-accumulation-monthly-investment-input", "value"),
    State(
        "backtest-accumulation-monthly-investment-inflation-adjustment-switch", "value"
    ),
    State("backtest-accumulation-investment-horizon-input", "value"),
    State("backtest-accumulation-dca-length-input", "value"),
    State("backtest-accumulation-dca-interval-input", "value"),
    State("backtest-accumulation-variable-transaction-fees-input", "value"),
    State("backtest-accumulation-fixed-transaction-fees-input", "value"),
    State("backtest-accumulation-annualised-holding-fees-input", "value"),
    State("backtest-accumulation-portfolio-value-inflation-adjustment-switch", "value"),
    prevent_initial_call=True,
)
def update_backtest_accumulation_strategies(
    _,
    strategies: list[str] | None,
    strategy_options: dict[str, str],
    strategy_portfolio: str | None,
    currency: Currency,
    investment_amount: int | float | None,
    monthly_investment: int | float | None,
    adjust_monthly_investment_for_inflation: bool,
    investment_horizon: int | None,
    dca_length: int | None,
    dca_interval: int | None,
    variable_transaction_fees: int | float | None,
    fixed_transaction_fees: int | float | None,
    annualised_holding_fees: int | float | None,
    adjust_portfolio_value_for_inflation: bool,
):
    if strategy_portfolio is None:
        return no_update
    try:
        strategy = AccumulationStrategy(
            strategy_portfolio=Portfolio.model_validate_json(strategy_portfolio),
            currency=currency,
            investment_amount=investment_amount or 0,
            monthly_investment=monthly_investment or 0,
            adjust_monthly_investment_for_inflation=adjust_monthly_investment_for_inflation,
            investment_horizon=investment_horizon or dca_length or 0,
            dca_length=dca_length or 0,
            dca_interval=dca_interval or 1,
            variable_transaction_fees=variable_transaction_fees or 0,
            fixed_transaction_fees=fixed_transaction_fees or 0,
            annualised_holding_fees=annualised_holding_fees or 0,
            adjust_portfolio_value_for_inflation=adjust_portfolio_value_for_inflation,
        )
    except ValidationError:
        # set_props(
        #     "toast-store",
        #     {
        #         "data": "\n".join(
        #             err["msg"]
        #             for err in e.errors(
        #                 include_url=False,
        #                 include_context=False,
        #                 include_input=False,
        #             )
        #         )
        #     },
        # )
        return no_update

    strategy_str = strategy.model_dump_json()
    strategy_name = strategy.label

    if strategies is None:
        return [strategy_str], {strategy_str: strategy_name}
    if strategy_str in strategies:
        return no_update
    strategies.append(strategy_str)
    strategy_options.update({strategy_str: strategy_name})
    return strategies, strategy_options


def simulate_backtest_accumulation_strategy(
    yf_securities: dict[str, str], strategy: AccumulationStrategy
):
    strategy_series = load_portfolio(
        strategy.strategy_portfolio, strategy.currency, False, yf_securities
    )
    cash_returns = (
        (
            load_fed_funds_returns()
            if strategy.currency == Currency.USD
            else load_sgd_interest_rates_returns()
        )
        .resample("BME")
        .last()
        .pct_change()
        .reindex(strategy_series.index)
        .to_numpy()
    )
    cpi = load_cpi(strategy.currency).reindex(strategy_series.index).to_numpy()

    portfolio_values = pd.DataFrame(
        calculate_dca_portfolio_value_with_fees_and_interest_vector(
            strategy_series.pct_change().to_numpy(),
            strategy.dca_length,
            strategy.dca_interval,
            strategy.investment_horizon,
            strategy.investment_amount,
            strategy.monthly_investment,
            strategy.adjust_monthly_investment_for_inflation,
            strategy.variable_transaction_fees,
            strategy.fixed_transaction_fees,
            strategy.annualised_holding_fees,
            strategy.adjust_portfolio_value_for_inflation,
            cpi,
            cash_returns,
        ),
        index=strategy_series.index,
        columns=range(strategy.investment_horizon + 1),
    )
    return portfolio_values


@app.callback(
    Output("backtest-accumulation-strategy-graph", "figure"),
    Input("backtest-accumulation-strategies", "value"),
    State("backtest-accumulation-strategies", "options"),
    Input("backtest-accumulation-index-by-start-date", "value"),
    Input("backtest-accumulation-y-var-selection", "value"),
    Input("backtest-accumulation-drawdown-type-selection", "value"),
    State("cached-securities-store", "data"),
    prevent_initial_call=True,
)
def update_backtest_accumulation_strategy_graph(
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    index_by_start_date: bool,
    y_var: BacktestYVar,
    drawdown_type: DrawdownType,
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
    dfs: dict[str, pd.DataFrame] = {}
    for strategy_str in strategy_strs:
        strategy = AccumulationStrategy.model_validate_json(strategy_str)
        portfolio_values = simulate_backtest_accumulation_strategy(
            yf_securities, strategy
        )
        investment_horizon = strategy.investment_horizon
        if index_by_start_date:
            portfolio_values = portfolio_values.shift(-investment_horizon)
        portfolio_values = portfolio_values.dropna(how="all")
        dfs.update({strategy_str: portfolio_values})

    if y_var == BacktestYVar.ENDING_VALUES:
        values = pd.concat(
            [df.iloc[:, -1].rename(name) for name, df in dfs.items()], axis=1
        )
    elif y_var == BacktestYVar.MAX_DRAWDOWN:
        if drawdown_type == DrawdownType.PERCENT:
            values = pd.concat(
                [
                    df.T.div(df.T.cummax()).sub(1).min().rename(name)
                    for name, df in dfs.items()
                ],
                axis=1,
            )
        else:
            values = pd.concat(
                [
                    df.T.sub(df.T.cummax()).min().rename(name)
                    for name, df in dfs.items()
                ],
                axis=1,
            )
    else:
        raise ValueError("Invalid y_var")

    return {
        "data": [
            go.Scatter(
                x=values.index,
                y=values[strategy],
                mode="lines",
                line=go.scatter.Line(color=strategies_colourmap[strategy]),
                name=strategy_options[strategy].replace("\n", "<br>"),
            )
            for strategy in values.columns
        ],
        "layout": go.Layout(
            title="Strategy Performance",
            hovermode="x",
            showlegend=True,
            legend=go.layout.Legend(x=0, valign="top", bgcolor="rgba(255,255,255,0.5)"),
            yaxis_side="right",
            margin=go.layout.Margin(t=90, b=30, l=10, r=90, autoexpand=True),
        ),
    }


class Point(TypedDict):
    x: str


class ClickData(TypedDict):
    points: list[Point]


@app.callback(
    Output("backtest-accumulation-strategy-clicked-date-store", "data"),
    Output("backtest-accumulation-strategy-show-details-button", "children"),
    Output("backtest-accumulation-strategy-show-details-button", "disabled"),
    Input("backtest-accumulation-strategy-graph", "clickData"),
    Input("backtest-accumulation-strategies", "value"),
    prevent_initial_call=True,
)
def handle_backtest_accumulation_strategy_graph_interaction(click_data: ClickData, _):
    if ctx.triggered_id == "backtest-accumulation-strategies":
        return None, "Click a data point to view portfolio growth", True

    clicked_date = pd.to_datetime(click_data["points"][0]["x"])
    date_str = clicked_date.strftime("%b %Y")
    return clicked_date.isoformat(), f"View Portfolio Growth for {date_str}", False


@app.callback(
    Output("backtest-accumulation-strategy-modal", "is_open"),
    Output("backtest-accumulation-strategy-modal-graph", "figure"),
    Input("backtest-accumulation-strategy-show-details-button", "n_clicks"),
    State("backtest-accumulation-strategy-clicked-date-store", "data"),
    State("backtest-accumulation-strategies", "value"),
    State("backtest-accumulation-strategies", "options"),
    State("backtest-accumulation-index-by-start-date", "value"),
    State("cached-securities-store", "data"),
    prevent_initial_call=True,
)
def show_backtest_accumulation_strategy_modal(
    _,
    clicked_date_str: str,
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    index_by_start_date: bool,
    yf_securities: dict[str, str],
):
    if not clicked_date_str:
        return False, {}

    clicked_date = pd.to_datetime(clicked_date_str)

    strategies_colourmap = dict(
        zip(strategy_options.keys(), cycle(DEFAULT_PLOTLY_COLORS))
    )

    traces = []
    for strategy_str in strategy_strs:
        strategy = AccumulationStrategy.model_validate_json(strategy_str)
        portfolio_values = simulate_backtest_accumulation_strategy(
            yf_securities, strategy
        )
        investment_horizon = strategy.investment_horizon
        if index_by_start_date:
            portfolio_values = portfolio_values.shift(-investment_horizon)
        portfolio_values = portfolio_values.dropna(how="all")
        if clicked_date not in portfolio_values.index:
            continue

        row = portfolio_values.loc[clicked_date]

        date_range = partial(pd.date_range, periods=investment_horizon + 1, freq="BME")

        if index_by_start_date:
            dates = date_range(start=clicked_date)
        else:
            dates = date_range(end=clicked_date)

        traces.append(
            go.Scatter(
                x=dates,
                y=row.values,
                mode="lines",
                line=go.scatter.Line(color=strategies_colourmap[strategy_str]),
                name=strategy_options[strategy_str].replace("\n", "<br>"),
            )
        )

    if not traces:
        return False, {}

    return True, {
        "data": traces,
        "layout": go.Layout(
            title=f"Portfolio Growth {'from' if index_by_start_date else 'ending'} {clicked_date.strftime('%b %Y')}",
            hovermode="x",
            showlegend=True,
            legend=go.layout.Legend(x=0, valign="top", bgcolor="rgba(255,255,255,0.5)"),
            yaxis_side="right",
            margin=go.layout.Margin(t=90, b=30, l=10, r=90, autoexpand=True),
        ),
    }


@app.callback(
    Output("backtest-withdrawal-strategies", "value"),
    Output("backtest-withdrawal-strategies", "options"),
    Input("backtest-withdrawal-add-strategy-button", "n_clicks"),
    State("backtest-withdrawal-strategies", "value"),
    State("backtest-withdrawal-strategies", "options"),
    State("backtest-withdrawal-strategy-portfolio", "value"),
    State("backtest-withdrawal-strategy-currency-selection", "value"),
    State("backtest-withdrawal-initial-capital-input", "value"),
    State("backtest-withdrawal-monthly-amount-input", "value"),
    State("backtest-withdrawal-monthly-inflation-adjustment-switch", "value"),
    State("backtest-withdrawal-horizon-input", "value"),
    State("backtest-withdrawal-interval-input", "value"),
    State("backtest-withdrawal-variable-transaction-fees-input", "value"),
    State("backtest-withdrawal-fixed-transaction-fees-input", "value"),
    State("backtest-withdrawal-annualised-holding-fees-input", "value"),
    prevent_initial_call=True,
)
def update_backtest_withdrawal_strategies(
    _,
    strategies: list[str] | None,
    strategy_options: dict[str, str],
    strategy_portfolio: str | None,
    currency: Currency,
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
    try:
        strategy = WithdrawalStrategy(
            strategy_portfolio=Portfolio.model_validate_json(strategy_portfolio),
            currency=currency,
            initial_capital=initial_capital or 0,
            monthly_withdrawal=monthly_withdrawal or 0,
            adjust_for_inflation=adjust_for_inflation,
            withdrawal_horizon=withdrawal_horizon or 0,
            withdrawal_interval=withdrawal_interval or 1,
            variable_transaction_fees=variable_transaction_fees or 0,
            fixed_transaction_fees=fixed_transaction_fees or 0,
            annualised_holding_fees=annualised_holding_fees or 0,
        )
    except ValidationError:
        # set_props(
        #     "toast-store",
        #     {
        #         "data": "\n".join(
        #             err["msg"]
        #             for err in e.errors(
        #                 include_url=False,
        #                 include_context=False,
        #                 include_input=False,
        #             )
        #         )
        #     },
        # )
        return no_update

    strategy_str = strategy.model_dump_json()
    strategy_name = strategy.label

    if strategies is None:
        return [strategy_str], {strategy_str: strategy_name}
    if strategy_str in strategies:
        return no_update
    strategies.append(strategy_str)
    strategy_options.update({strategy_str: strategy_name})
    return strategies, strategy_options


def simulate_backtest_withdrawal_strategy(
    yf_securities: dict[str, str], strategy: WithdrawalStrategy
):

    strategy_series = load_portfolio(
        strategy.strategy_portfolio, strategy.currency, False, yf_securities
    )
    cpi = (
        np.ones(len(strategy_series))
        if not strategy.adjust_for_inflation
        else load_cpi(strategy.currency).reindex(strategy_series.index).to_numpy()
    )

    portfolio_values = pd.DataFrame(
        calculate_withdrawal_portfolio_value_with_fees_vector(
            strategy_series.pct_change().to_numpy(),
            strategy.withdrawal_horizon,
            strategy.withdrawal_interval,
            strategy.initial_capital,
            strategy.monthly_withdrawal,
            cpi,
            strategy.variable_transaction_fees,
            strategy.fixed_transaction_fees,
            strategy.annualised_holding_fees,
        ),
        index=strategy_series.index,
        columns=range(strategy.withdrawal_horizon + 1),
    )
    return portfolio_values


@app.callback(
    Output("backtest-withdrawal-strategy-graph", "figure"),
    Input("backtest-withdrawal-strategies", "value"),
    State("backtest-withdrawal-strategies", "options"),
    Input("backtest-withdrawal-index-by-start-date", "value"),
    Input("backtest-withdrawal-y-var-selection", "value"),
    Input("backtest-withdrawal-drawdown-type-selection", "value"),
    State("cached-securities-store", "data"),
    prevent_initial_call=True,
)
def update_backtest_withdrawal_strategy_graph(
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    index_by_start_date: bool,
    y_var: BacktestYVar,
    drawdown_type: DrawdownType,
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
    dfs: dict[str, pd.DataFrame] = {}
    for strategy_str in strategy_strs:
        strategy = WithdrawalStrategy.model_validate_json(strategy_str)
        portfolio_values = simulate_backtest_withdrawal_strategy(
            yf_securities, strategy
        )
        withdrawal_horizon = strategy.withdrawal_horizon
        if index_by_start_date:
            portfolio_values = portfolio_values.shift(-withdrawal_horizon)
        portfolio_values = portfolio_values.dropna(how="all")
        dfs.update({strategy_str: portfolio_values})

    if y_var == BacktestYVar.ENDING_VALUES:
        values = pd.concat(
            [df.iloc[:, -1].rename(name) for name, df in dfs.items()], axis=1
        )
    elif y_var == BacktestYVar.MAX_DRAWDOWN:
        if drawdown_type == DrawdownType.PERCENT:
            values = pd.concat(
                [
                    df.T.div(df.T.cummax()).sub(1).min().rename(name)
                    for name, df in dfs.items()
                ],
                axis=1,
            )
        else:
            values = pd.concat(
                [
                    df.T.sub(df.T.cummax()).min().rename(name)
                    for name, df in dfs.items()
                ],
                axis=1,
            )
    else:
        raise ValueError("Invalid y_var")

    return {
        "data": [
            go.Scatter(
                x=values.index,
                y=values[strategy],
                mode="lines",
                line=go.scatter.Line(color=strategies_colourmap[strategy]),
                name=strategy_options[strategy].replace("\n", "<br>"),
            )
            for strategy in values.columns
        ],
        "layout": go.Layout(
            title="Strategy Performance",
            hovermode="x",
            showlegend=True,
            legend=go.layout.Legend(x=0, valign="top", bgcolor="rgba(255,255,255,0.5)"),
            yaxis_side="right",
            margin=go.layout.Margin(t=90, b=30, l=10, r=90, autoexpand=True),
        ),
    }


@app.callback(
    Output("backtest-withdrawal-strategy-clicked-date-store", "data"),
    Output("backtest-withdrawal-strategy-show-details-button", "children"),
    Output("backtest-withdrawal-strategy-show-details-button", "disabled"),
    Input("backtest-withdrawal-strategy-graph", "clickData"),
    Input("backtest-withdrawal-strategies", "value"),
    prevent_initial_call=True,
)
def handle_backtest_withdrawal_strategy_graph_interaction(click_data: ClickData, _):
    if ctx.triggered_id == "backtest-withdrawal-strategies":
        return None, "Click a data point to view portfolio value", True

    clicked_date = pd.to_datetime(click_data["points"][0]["x"])
    date_str = clicked_date.strftime("%b %Y")
    return clicked_date.isoformat(), f"View Portfolio Value for {date_str}", False


@app.callback(
    Output("backtest-withdrawal-strategy-modal", "is_open"),
    Output("backtest-withdrawal-strategy-modal-graph", "figure"),
    Input("backtest-withdrawal-strategy-show-details-button", "n_clicks"),
    State("backtest-withdrawal-strategy-clicked-date-store", "data"),
    State("backtest-withdrawal-strategies", "value"),
    State("backtest-withdrawal-strategies", "options"),
    State("backtest-withdrawal-index-by-start-date", "value"),
    State("cached-securities-store", "data"),
    prevent_initial_call=True,
)
def show_backtest_withdrawal_strategy_modal(
    _,
    clicked_date_str: str,
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    index_by_start_date: bool,
    yf_securities: dict[str, str],
):
    if not clicked_date_str:
        return False, {}

    clicked_date = pd.to_datetime(clicked_date_str)

    strategies_colourmap = dict(
        zip(strategy_options.keys(), cycle(DEFAULT_PLOTLY_COLORS))
    )

    traces = []
    for strategy_str in strategy_strs:
        strategy = WithdrawalStrategy.model_validate_json(strategy_str)
        portfolio_values = simulate_backtest_withdrawal_strategy(
            yf_securities, strategy
        )
        withdrawal_horizon = strategy.withdrawal_horizon
        if index_by_start_date:
            portfolio_values = portfolio_values.shift(-withdrawal_horizon)
        portfolio_values = portfolio_values.dropna(how="all")

        if clicked_date not in portfolio_values.index:
            continue

        row = portfolio_values.loc[clicked_date]

        date_range = partial(pd.date_range, periods=withdrawal_horizon + 1, freq="BME")

        if index_by_start_date:
            dates = date_range(start=clicked_date)
        else:
            dates = date_range(end=clicked_date)

        traces.append(
            go.Scatter(
                x=dates,
                y=row.values,
                mode="lines",
                line=go.scatter.Line(color=strategies_colourmap[strategy_str]),
                name=strategy_options[strategy_str].replace("\n", "<br>"),
            )
        )

    if not traces:
        return False, {}

    return True, {
        "data": traces,
        "layout": go.Layout(
            title=f"Portfolio Value {'from' if index_by_start_date else 'ending'} {clicked_date.strftime('%b %Y')}",
            hovermode="x",
            showlegend=True,
            legend=go.layout.Legend(x=0, valign="top", bgcolor="rgba(255,255,255,0.5)"),
            yaxis_side="right",
            margin=go.layout.Margin(t=90, b=30, l=10, r=90, autoexpand=True),
        ),
    }


QUANTILE_KEYS = [0.01, 0.05, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
BANDS = [(0.01, 0.99, 0.15), (0.05, 0.95, 0.25), (0.25, 0.75, 0.40)]


def _build_quantile_fan_traces(
    months: np.ndarray,
    quantiles: dict[float, np.ndarray],
    color: str,
    strategy_name: str,
) -> list[go.Scatter]:
    traces = []
    for lo, hi, opacity in BANDS:
        traces.append(
            go.Scatter(
                x=months,
                y=quantiles[lo],
                mode="lines",
                line=dict(width=0),
                legendgroup=strategy_name,
                showlegend=False,
                hoverinfo="skip",
            )
        )
        traces.append(
            go.Scatter(
                x=months,
                y=quantiles[hi],
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor=color.replace("rgb(", "rgba(").rstrip(")") + f", {opacity})",
                legendgroup=strategy_name,
                showlegend=False,
                hoverinfo="skip",
            )
        )
    customdata = np.column_stack(
        [
            quantiles[0.99],
            quantiles[0.95],
            quantiles[0.75],
            quantiles[0.50],
            quantiles[0.25],
            quantiles[0.05],
            quantiles[0.01],
        ]
    )
    traces.append(
        go.Scatter(
            x=months,
            y=quantiles[0.50],
            mode="lines",
            line=dict(color=color, width=2),
            name=strategy_name.replace("\n", "<br>"),
            legendgroup=strategy_name,
            customdata=customdata,
            hovertemplate=(
                "p99: %{customdata[0]:$,.0f}<br>"
                "p95: %{customdata[1]:$,.0f}<br>"
                "p75: %{customdata[2]:$,.0f}<br>"
                "<b>p50: %{customdata[3]:$,.0f}</b><br>"
                "p25: %{customdata[4]:$,.0f}<br>"
                "p5: %{customdata[5]:$,.0f}<br>"
                "p1: %{customdata[6]:$,.0f}"
            ),
            showlegend=True,
        )
    )
    return traces


def simulate_bootstrap_accumulation_strategy(
    yf_securities: dict[str, str],
    strategy: AccumulationBootstrapStrategy,
):

    strategy_series = load_portfolio(
        strategy.strategy_portfolio, strategy.currency, False, yf_securities
    ).pct_change()
    cpi = load_cpi(strategy.currency).pct_change()
    cash_returns = (
        (
            load_fed_funds_returns()
            if strategy.currency == Currency.USD
            else load_sgd_interest_rates_returns()
        )
        .resample("BME")
        .last()
        .pct_change()
    )
    common_idx = strategy_series.index.intersection(cpi.index).intersection(
        cash_returns.index
    )[1:]
    strategy_series = strategy_series.loc[common_idx].to_numpy()
    cpi = cpi.loc[common_idx].to_numpy()
    cash_returns = cash_returns.loc[common_idx].to_numpy()

    n_data = len(strategy_series)
    sample_length = strategy.investment_horizon + 1
    indices = generate_bootstrap_indices(
        strategy.num_bootstrap_samples, sample_length, n_data, strategy.avg_block_length
    )
    portfolio_values = simulate_bootstrap_accumulation(
        strategy_series,
        cpi,
        cash_returns,
        indices,
        strategy.dca_length,
        strategy.dca_interval,
        strategy.investment_horizon,
        strategy.investment_amount,
        strategy.monthly_investment,
        strategy.adjust_monthly_investment_for_inflation,
        strategy.variable_transaction_fees,
        strategy.fixed_transaction_fees,
        strategy.annualised_holding_fees,
        strategy.adjust_portfolio_value_for_inflation,
    )
    return portfolio_values


def simulate_bootstrap_withdrawal_strategy(
    yf_securities: dict[str, str],
    strategy: WithdrawalBootstrapStrategy,
):

    strategy_series = load_portfolio(
        strategy.strategy_portfolio, strategy.currency, False, yf_securities
    )
    if strategy.adjust_for_inflation:
        cpi_series = load_cpi(strategy.currency)
        common_idx = strategy_series.index.intersection(cpi_series.index)
        strategy_series = strategy_series.loc[common_idx]
        cpi = cpi_series.loc[common_idx].pct_change().to_numpy()
    else:
        cpi = np.zeros(len(strategy_series))

    monthly_returns = strategy_series.pct_change().to_numpy()[1:]
    cpi = cpi[1:]

    n_data = len(monthly_returns)
    sample_length = strategy.withdrawal_horizon + 1
    indices = generate_bootstrap_indices(
        strategy.num_bootstrap_samples,
        sample_length,
        n_data,
        strategy.avg_block_length,
    )
    portfolio_values = simulate_bootstrap_withdrawal(
        monthly_returns,
        cpi,
        indices,
        strategy.withdrawal_horizon,
        strategy.withdrawal_interval,
        strategy.initial_capital,
        strategy.monthly_withdrawal,
        strategy.variable_transaction_fees,
        strategy.fixed_transaction_fees,
        strategy.annualised_holding_fees,
    )
    return portfolio_values


@app.callback(
    Output("bootstrap-accumulation-strategies", "value"),
    Output("bootstrap-accumulation-strategies", "options"),
    Input("bootstrap-accumulation-add-strategy-button", "n_clicks"),
    State("bootstrap-accumulation-strategies", "value"),
    State("bootstrap-accumulation-strategies", "options"),
    State("bootstrap-accumulation-strategy-portfolio", "value"),
    State("bootstrap-accumulation-strategy-currency-selection", "value"),
    State("bootstrap-accumulation-investment-amount-input", "value"),
    State("bootstrap-accumulation-monthly-investment-input", "value"),
    State(
        "bootstrap-accumulation-monthly-investment-inflation-adjustment-switch", "value"
    ),
    State("bootstrap-accumulation-investment-horizon-input", "value"),
    State("bootstrap-accumulation-dca-length-input", "value"),
    State("bootstrap-accumulation-dca-interval-input", "value"),
    State("bootstrap-accumulation-variable-transaction-fees-input", "value"),
    State("bootstrap-accumulation-fixed-transaction-fees-input", "value"),
    State("bootstrap-accumulation-annualised-holding-fees-input", "value"),
    State(
        "bootstrap-accumulation-portfolio-value-inflation-adjustment-switch", "value"
    ),
    State("bootstrap-accumulation-num-samples-input", "value"),
    State("bootstrap-accumulation-avg-block-length-input", "value"),
    prevent_initial_call=True,
)
def update_bootstrap_accumulation_strategies(
    _,
    strategies: list[str] | None,
    strategy_options: dict[str, str],
    strategy_portfolio: str | None,
    currency: Currency,
    investment_amount: int | float | None,
    monthly_investment: int | float | None,
    adjust_monthly_investment_for_inflation: bool,
    investment_horizon: int | None,
    dca_length: int | None,
    dca_interval: int | None,
    variable_transaction_fees: int | float | None,
    fixed_transaction_fees: int | float | None,
    annualised_holding_fees: int | float | None,
    adjust_portfolio_value_for_inflation: bool,
    num_samples: int | None,
    avg_block_len: int | float | None,
):
    if strategy_portfolio is None:
        return no_update
    try:
        strategy = AccumulationBootstrapStrategy(
            strategy_portfolio=Portfolio.model_validate_json(strategy_portfolio),
            currency=currency,
            investment_amount=investment_amount or 0,
            monthly_investment=monthly_investment or 0,
            adjust_monthly_investment_for_inflation=adjust_monthly_investment_for_inflation,
            investment_horizon=investment_horizon or dca_length or 0,
            dca_length=dca_length or 0,
            dca_interval=dca_interval or 1,
            variable_transaction_fees=variable_transaction_fees or 0,
            fixed_transaction_fees=fixed_transaction_fees or 0,
            annualised_holding_fees=annualised_holding_fees or 0,
            adjust_portfolio_value_for_inflation=adjust_portfolio_value_for_inflation,
            num_bootstrap_samples=num_samples or 1000,
            avg_block_length=avg_block_len or 120,
        )
    except ValidationError:
        # set_props(
        #     "toast-store",
        #     {
        #         "data": "\n".join(
        #             err["msg"]
        #             for err in e.errors(
        #                 include_url=False,
        #                 include_context=False,
        #                 include_input=False,
        #             )
        #         )
        #     },
        # )
        return no_update

    strategy_str = strategy.model_dump_json()
    strategy_name = strategy.label

    if strategies is None:
        return [strategy_str], {strategy_str: strategy_name}
    if strategy_str in strategies:
        return no_update
    strategies.append(strategy_str)
    strategy_options.update({strategy_str: strategy_name})
    return strategies, strategy_options


@app.callback(
    Output("bootstrap-accumulation-graph", "figure"),
    Input("bootstrap-accumulation-strategies", "value"),
    State("bootstrap-accumulation-strategies", "options"),
    Input("bootstrap-accumulation-y-var-selection", "value"),
    Input("bootstrap-accumulation-log-scale-switch", "value"),
    State("cached-securities-store", "data"),
    prevent_initial_call=True,
)
def update_bootstrap_accumulation_graph(
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    y_var: BootstrapYVar,
    log_scale: bool,
    yf_securities: dict[str, str],
):
    if not strategy_strs:
        return {
            "data": [],
            "layout": {
                "title": "Bootstrap Accumulation Strategy",
            },
        }
    strategies_colourmap = dict(
        zip(strategy_options.keys(), cycle(DEFAULT_PLOTLY_COLORS))
    )
    all_traces = []
    for strategy_str in strategy_strs:
        strategy = AccumulationBootstrapStrategy.model_validate_json(strategy_str)
        portfolio_values = simulate_bootstrap_accumulation_strategy(
            yf_securities, strategy
        )
        investment_horizon = strategy.investment_horizon
        months = np.arange(investment_horizon + 1)
        if y_var == BootstrapYVar.PORTFOLIO_VALUES:
            values = portfolio_values
        else:
            values = compute_bootstrap_max_drawdown(portfolio_values)
        quantiles = dict(zip(QUANTILE_KEYS, np.quantile(values, QUANTILE_KEYS, axis=0)))
        all_traces.extend(
            _build_quantile_fan_traces(
                months,
                quantiles,
                strategies_colourmap[strategy_str],
                strategy_options[strategy_str],
            )
        )

    return {
        "data": all_traces,
        "layout": go.Layout(
            title="Bootstrap Accumulation Strategy",
            xaxis_title="Month",
            yaxis_title="Portfolio Value ($)"
            if y_var == BootstrapYVar.PORTFOLIO_VALUES
            else "Max Drawdown ($)",
            hovermode="x",
            showlegend=True,
            legend=go.layout.Legend(x=0, valign="top", bgcolor="rgba(255,255,255,0.5)"),
            yaxis_side="right",
            yaxis_type="log" if log_scale else "linear",
            margin=go.layout.Margin(t=90, b=30, l=10, r=90, autoexpand=True),
        ),
    }


@app.callback(
    Output("bootstrap-withdrawal-strategies", "value"),
    Output("bootstrap-withdrawal-strategies", "options"),
    Input("bootstrap-withdrawal-add-strategy-button", "n_clicks"),
    State("bootstrap-withdrawal-strategies", "value"),
    State("bootstrap-withdrawal-strategies", "options"),
    State("bootstrap-withdrawal-strategy-portfolio", "value"),
    State("bootstrap-withdrawal-strategy-currency-selection", "value"),
    State("bootstrap-withdrawal-initial-capital-input", "value"),
    State("bootstrap-withdrawal-monthly-amount-input", "value"),
    State("bootstrap-withdrawal-monthly-inflation-adjustment-switch", "value"),
    State("bootstrap-withdrawal-horizon-input", "value"),
    State("bootstrap-withdrawal-interval-input", "value"),
    State("bootstrap-withdrawal-variable-transaction-fees-input", "value"),
    State("bootstrap-withdrawal-fixed-transaction-fees-input", "value"),
    State("bootstrap-withdrawal-annualised-holding-fees-input", "value"),
    State("bootstrap-withdrawal-num-samples-input", "value"),
    State("bootstrap-withdrawal-avg-block-length-input", "value"),
    prevent_initial_call=True,
)
def update_bootstrap_withdrawal_strategies(
    _,
    strategies: list[str] | None,
    strategy_options: dict[str, str],
    strategy_portfolio: str | None,
    currency: Currency,
    initial_capital: int | float | None,
    monthly_withdrawal: int | float | None,
    adjust_for_inflation: bool,
    withdrawal_horizon: int | None,
    withdrawal_interval: int | None,
    variable_transaction_fees: int | float | None,
    fixed_transaction_fees: int | float | None,
    annualised_holding_fees: int | float | None,
    num_samples: int | None,
    avg_block_len: int | float | None,
):
    if strategy_portfolio is None:
        return no_update
    try:
        strategy = WithdrawalBootstrapStrategy(
            strategy_portfolio=Portfolio.model_validate_json(strategy_portfolio),
            currency=currency,
            initial_capital=initial_capital or 0,
            monthly_withdrawal=monthly_withdrawal or 0,
            adjust_for_inflation=adjust_for_inflation,
            withdrawal_horizon=withdrawal_horizon or 0,
            withdrawal_interval=withdrawal_interval or 1,
            variable_transaction_fees=variable_transaction_fees or 0,
            fixed_transaction_fees=fixed_transaction_fees or 0,
            annualised_holding_fees=annualised_holding_fees or 0,
            num_bootstrap_samples=num_samples or 1000,
            avg_block_length=avg_block_len or 120,
        )
    except ValidationError:
        # set_props(
        #     "toast-store",
        #     {
        #         "data": "\n".join(
        #             err["msg"]
        #             for err in e.errors(
        #                 include_url=False,
        #                 include_context=False,
        #                 include_input=False,
        #             )
        #         )
        #     },
        # )
        return no_update

    strategy_str = strategy.model_dump_json()
    strategy_name = strategy.label

    if strategies is None:
        return [strategy_str], {strategy_str: strategy_name}
    if strategy_str in strategies:
        return no_update
    strategies.append(strategy_str)
    strategy_options.update({strategy_str: strategy_name})
    return strategies, strategy_options


@app.callback(
    Output("bootstrap-withdrawal-graph", "figure"),
    Input("bootstrap-withdrawal-strategies", "value"),
    State("bootstrap-withdrawal-strategies", "options"),
    Input("bootstrap-withdrawal-y-var-selection", "value"),
    Input("bootstrap-withdrawal-log-scale-switch", "value"),
    State("cached-securities-store", "data"),
    prevent_initial_call=True,
)
def update_bootstrap_withdrawal_graph(
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    y_var: BootstrapYVar,
    log_scale: bool,
    yf_securities: dict[str, str],
):
    if not strategy_strs:
        return {
            "data": [],
            "layout": {
                "title": "Bootstrap Withdrawal Strategy",
            },
        }
    strategies_colourmap = dict(
        zip(strategy_options.keys(), cycle(DEFAULT_PLOTLY_COLORS))
    )
    all_traces = []
    for strategy_str in strategy_strs:
        strategy = WithdrawalBootstrapStrategy.model_validate_json(strategy_str)
        portfolio_values = simulate_bootstrap_withdrawal_strategy(
            yf_securities, strategy
        )
        withdrawal_horizon = strategy.withdrawal_horizon
        months = np.arange(withdrawal_horizon + 1)
        if y_var == BootstrapYVar.PORTFOLIO_VALUES:
            values = portfolio_values
        else:
            values = compute_bootstrap_max_drawdown(portfolio_values)
        quantiles = dict(zip(QUANTILE_KEYS, np.quantile(values, QUANTILE_KEYS, axis=0)))
        all_traces.extend(
            _build_quantile_fan_traces(
                months,
                quantiles,
                strategies_colourmap[strategy_str],
                strategy_options[strategy_str],
            )
        )

    return {
        "data": all_traces,
        "layout": go.Layout(
            title="Bootstrap Withdrawal Strategy",
            xaxis_title="Month",
            yaxis_title="Portfolio Value ($)"
            if y_var == BootstrapYVar.PORTFOLIO_VALUES
            else "Max Drawdown ($)",
            hovermode="x",
            showlegend=True,
            legend=go.layout.Legend(x=0, valign="top", bgcolor="rgba(255,255,255,0.5)"),
            yaxis_side="right",
            yaxis_type="log" if log_scale else "linear",
            margin=go.layout.Margin(t=90, b=30, l=10, r=90, autoexpand=True),
        ),
    }


if __name__ == "__main__":
    app.run("0.0.0.0", debug=True)
