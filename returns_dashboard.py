from functools import cache, reduce
from itertools import cycle
from typing import TypedDict

import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import polars as pl
import python_calamine  # noqa: F401 # Reduces latency for first pd.read_excel call
import scipy.interpolate  # noqa: F401 # Reduces latency for first pd.Resampler.interpolate call
from dash import (
    ClientsideFunction,
    Dash,
    Input,
    Output,
    State,
    callback,
    clientside_callback,
    ctx,
    no_update,
    set_props,
)
from plotly.colors import DEFAULT_PLOTLY_COLORS
from pydantic import Json, TypeAdapter, ValidationError

from funcs.calcs_numpy import (
    calculate_dca_portfolio_value_with_fees_and_interest_vector,
    calculate_withdrawal_portfolio_value_with_fees_vector,
    compute_bootstrap_max_drawdown,
    generate_bootstrap_indices,
    simulate_bootstrap_accumulation,
    simulate_bootstrap_withdrawal,
)
from funcs.loaders_pl import (
    get_ft_symbol_info,
    load_cpi,
    load_fed_funds_returns,
    load_fred_usd_fx,
    load_mas_sgd_fx,
    load_sgd_interest_rates_returns,
    load_usdsgd,
    pchip_daily_upsample,
    resample_bme,
    validate_yf_ticker,
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
    AccumulationBacktestStrategy,
    AccumulationBootstrapStrategy,
    Allocation,
    BacktestStrategy,
    BaseSecurity,
    BootstrapStrategy,
    FtSecurity,
    FundSecurity,
    Holding,
    IndexSecurity,
    Portfolio,
    Security,
    WithdrawalBacktestStrategy,
    WithdrawalBootstrapStrategy,
    YfSecurity,
)
from update_graph import GraphParams, PrevLayout, RelayoutData


def convert_price(
    df: pl.DataFrame,
    source_currency: str,
    destination_currency: Currency,
) -> pl.DataFrame:
    if source_currency == destination_currency:
        return df

    usd_sgd = (
        load_usdsgd()
        .sort("date")
        .upsample("date", every="1d", maintain_order=True)
        .fill_null(strategy="forward")
    )

    if source_currency == "USD" and destination_currency == Currency.SGD:
        return df.join(usd_sgd, on="date", how="left").select(
            "date", price=pl.col("price") * pl.col("usdsgd")
        )
    if source_currency == "SGD" and destination_currency == Currency.USD:
        return df.join(usd_sgd, on="date", how="left").select(
            "date", price=pl.col("price") / pl.col("usdsgd")
        )

    usd_fx = (
        load_fred_usd_fx()
        .sort("date")
        .upsample("date", every="1d", maintain_order=True)
        .fill_null(strategy="forward")
    )

    if source_currency == "GBp":
        df = df.with_columns(pl.col("price") / 100)
        source_currency = "GBP"

    if source_currency in usd_fx.columns:
        usd_series = df.join(
            usd_fx.select("date", source_currency), on="date", how="left"
        ).select("date", price=pl.col("price") * pl.col(source_currency))
        if destination_currency == Currency.USD:
            return usd_series
        if destination_currency == Currency.SGD:
            return usd_series.join(usd_sgd, on="date", how="left").select(
                "date", price=pl.col("price") * pl.col("usdsgd")
            )

    sgd_fx = (
        load_mas_sgd_fx()
        .sort("date")
        .upsample("date", every="1d", maintain_order=True)
        .fill_null(strategy="forward")
    )

    if source_currency in sgd_fx.columns:
        sgd_series = df.join(
            sgd_fx.select("date", source_currency), on="date", how="left"
        ).select("date", price=pl.col("price") * pl.col(source_currency))
        if destination_currency == Currency.SGD:
            return sgd_series
        if destination_currency == Currency.USD:
            return sgd_series.join(usd_sgd, on="date", how="left").select(
                "date", price=pl.col("price") / pl.col("usdsgd")
            )

    return df


@cache
def load_security(
    security_str: str,
    interval: Interval,
    currency: Currency,
    adjust_for_inflation: bool,
):
    security: Security = TypeAdapter(Security).validate_json(security_str)
    df = security.load_data(interval)

    df = convert_price(df, security.currency, currency)
    if adjust_for_inflation:
        cpi = load_cpi(currency)
        cpi = cpi.pipe(pchip_daily_upsample, "cpi").fill_null(strategy="forward")
        df = df.join(cpi, on="date", how="left").select(
            "date", price=pl.col("price") / pl.col("cpi")
        )
    return df.sort("date")


def load_portfolio(
    portfolio: Portfolio,
    currency: Currency,
    adjust_for_inflation: bool,
):
    dfs = [
        load_security(
            allocation.security.model_dump_json(),
            Interval.MONTHLY,
            currency,
            adjust_for_inflation,
        ).rename({"price": allocation.security.model_dump_json()})
        for allocation in portfolio.allocations
    ]
    portfolio_df = reduce(
        lambda left, right: left.join(right, on="date", how="full", coalesce=True), dfs
    )
    portfolio_series = (
        portfolio_df.with_columns(
            pl.col(allocation.security.model_dump_json())
            .pct_change()
            .mul(allocation.weight)
            .truediv(100)
            for allocation in portfolio.allocations
        )
        .select(
            "date",
            price=pl.sum_horizontal(pl.all().exclude("date"), ignore_nulls=False)
            .add(1)
            .cum_prod(),
        )
        .select(
            "date",
            price=pl.when(
                pl.int_range(pl.len())
                == pl.arg_where(pl.col("price").is_not_null()).first().sub(1)
            )
            .then(1)
            .otherwise(pl.col("price")),
        )
        .drop_nulls()
    )
    return portfolio_series


def load_series(
    holding: Holding,
    interval: Interval,
    currency: Currency,
    adjust_for_inflation: bool,
):
    if isinstance(holding, BaseSecurity):
        df = load_security(
            holding.model_dump_json(),
            interval,
            currency,
            adjust_for_inflation,
        )
    elif isinstance(holding, Portfolio):
        df = load_portfolio(holding, currency, adjust_for_inflation)
    else:
        raise ValueError(f"Invalid holding type: {holding.holding_type}")
    return df


app = Dash(
    serve_locally=False,
    eager_loading=True,
    compress=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)

server = app.server

app.layout = app_layout


clientside_callback(
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


clientside_callback(
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


@callback(
    Output("msci-index-selection", "options"),
    Output("msci-index-selection", "value"),
    Input("msci-index-type-selection", "value"),
)
def update_msci_index_options(index_type: MSCIIndexType):
    options = MSCIIndexType(index_type).indexes
    return options.to_dict(), list(options)[0]


clientside_callback(
    ClientsideFunction(
        namespace="visibility",
        function_name="updateOthersTaxTreatmentSelectionVisibility",
    ),
    Output("others-tax-treatment-selection-container", "style"),
    Input("others-index-selection", "value"),
)


clientside_callback(
    ClientsideFunction(
        namespace="visibility", function_name="updateFredDurationSelectionVisibility"
    ),
    Output("us-treasury-index-selection-container", "style"),
    Input("fred-index-selection", "value"),
)


clientside_callback(
    ClientsideFunction(
        namespace="visibility", function_name="updateMasDurationSelectionVisibility"
    ),
    Output("sgs-index-selection-container", "style"),
    Input("mas-index-selection", "value"),
)


clientside_callback(
    ClientsideFunction(namespace="toast", function_name="updateToast"),
    Output("toast", "children"),
    Output("toast", "is_open"),
    Input("toast-store", "data"),
)


@callback(
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


@callback(
    Output("selected-securities", "value", allow_duplicate=True),
    Output("selected-securities", "options", allow_duplicate=True),
    Output("yf-valid-securities-store", "data"),
    Output("yf-ticker-currency-store", "data"),
    Input("add-yf-security-button", "n_clicks"),
    State("selected-securities", "value"),
    State("selected-securities", "options"),
    State("yf-security-input", "value"),
    State("yf-security-tax-treatment-selection", "value"),
    State("yf-invalid-securities-store", "data"),
    State("yf-valid-securities-store", "data"),
    State("yf-ticker-currency-store", "data"),
    prevent_initial_call=True,
    running=[(Output("add-yf-security-button", "disabled"), True, False)],
)
def add_yf_security(
    _,
    selected_securities: list[str],
    selected_securities_options: dict[str, str],
    yf_security: str | None,
    tax_treatment: TaxTreatment,
    yf_invalid_ticker_store: list[str],
    yf_valid_ticker_store: dict[str, str],
    yf_ticker_currency_store: dict[str, str | None],
):
    if not yf_security:
        return no_update
    if ";" in yf_security:
        set_props("toast-store", {"data": "Invalid character: ;"})
        return no_update
    if yf_security in yf_invalid_ticker_store:
        set_props("toast-store", {"data": "The selected ticker is not available"})
        return no_update
    if yf_security in yf_valid_ticker_store:
        yf_security = yf_valid_ticker_store[yf_security]
    if yf_security in yf_valid_ticker_store.values():
        new_yf_security = YfSecurity(
            ticker=yf_security,
            currency=yf_ticker_currency_store[yf_security] or "USD",
            tax_treatment=tax_treatment,
        )
        new_yf_security_json = new_yf_security.model_dump_json(exclude_none=True)
        if new_yf_security_json in selected_securities_options:
            selected_securities.append(new_yf_security_json)
            return selected_securities, no_update, no_update, no_update
        selected_securities.append(new_yf_security_json)
        selected_securities_options[new_yf_security_json] = new_yf_security.label

        return (selected_securities, selected_securities_options, no_update, no_update)

    (validated_ticker, currency) = validate_yf_ticker(yf_security)

    if validated_ticker is None:
        yf_invalid_ticker_store.append(yf_security)
        set_props("toast-store", {"data": "The selected ticker is not available"})
        set_props("yf-invalid-securities-store", {"data": yf_invalid_ticker_store})
        return no_update

    if currency is None:
        set_props(
            "toast-store",
            {
                "data": "The selected ticker does not have currency information. Defaulting to USD."
            },
        )

    yf_valid_ticker_store[yf_security] = validated_ticker
    yf_ticker_currency_store[validated_ticker] = currency

    new_yf_security = YfSecurity(
        ticker=validated_ticker,
        currency=currency or "USD",
        tax_treatment=tax_treatment,
    )
    new_yf_security_json = new_yf_security.model_dump_json(exclude_none=True)
    selected_securities.append(new_yf_security_json)
    selected_securities_options[new_yf_security_json] = new_yf_security.label

    return (
        selected_securities,
        selected_securities_options,
        yf_valid_ticker_store,
        yf_ticker_currency_store,
    )


@callback(
    Output("selected-securities", "value", allow_duplicate=True),
    Output("selected-securities", "options", allow_duplicate=True),
    Output("ft-valid-securities-store", "data", allow_duplicate=True),
    Output("ft-ticker-info-store", "data"),
    Input("add-ft-security-button", "n_clicks"),
    State("selected-securities", "value"),
    State("selected-securities", "options"),
    State("ft-security-input", "value"),
    State("ft-invalid-securities-store", "data"),
    State("ft-valid-securities-store", "data"),
    State("ft-ticker-info-store", "data"),
    prevent_initial_call=True,
    running=[(Output("add-ft-security-button", "disabled"), True, False)],
)
def add_ft_security(
    _,
    selected_securities: list[str],
    selected_securities_options: dict,
    ft_security: str,
    ft_invalid_ticker_store: list[str],
    ft_valid_ticker_store: dict[str, str],
    ft_ticker_info_store: dict[str, str],
):
    if not ft_security:
        return no_update
    if ft_security in ft_valid_ticker_store:
        ft_security = ft_valid_ticker_store[ft_security]
    if ft_security in ft_valid_ticker_store.values():
        new_ft_security_str = ft_ticker_info_store[ft_security]
        if new_ft_security_str in selected_securities:
            return no_update
        if new_ft_security_str in selected_securities_options:
            selected_securities.append(new_ft_security_str)
            return (
                selected_securities,
                selected_securities_options,
                no_update,
                no_update,
            )

        new_ft_security = FtSecurity.model_validate_json(new_ft_security_str)
        selected_securities.append(new_ft_security_str)
        selected_securities_options[new_ft_security_str] = new_ft_security.label
        return (
            selected_securities,
            selected_securities_options,
            no_update,
            no_update,
        )

    symbol_info = get_ft_symbol_info(ft_security)
    if symbol_info is None:
        ft_invalid_ticker_store.append(ft_security)
        set_props("toast-store", {"data": "The selected ticker is not available"})
        set_props("ft-invalid-securities-store", {"data": ft_invalid_ticker_store})
        return no_update

    ft_valid_ticker_store[ft_security] = symbol_info["basic"]["symbol"]

    dividends = ft_security.upper().endswith(":SES")

    new_ft_security = FtSecurity(
        ticker=symbol_info["basic"]["symbol"],
        currency=symbol_info["basic"]["currency"],
        issue_type=symbol_info["details"]["issueType"],
        inception_date=symbol_info["details"]["inceptionDate"],
        dividends=dividends,
    )
    new_ft_security_str = new_ft_security.model_dump_json(exclude_none=True)
    ft_ticker_info_store[symbol_info["basic"]["symbol"]] = new_ft_security_str
    selected_securities.append(new_ft_security_str)
    selected_securities_options[new_ft_security_str] = new_ft_security.label

    return (
        selected_securities,
        selected_securities_options,
        ft_valid_ticker_store,
        ft_ticker_info_store,
    )


@callback(
    Output("fund-selection", "options"),
    Output("fund-selection", "value"),
    Input("fund-company-selection", "value"),
)
def update_fund_selection_options(fund_company: FundCompany | None):
    if fund_company is None:
        return {}, None
    fund_class = FundCompany(fund_company).funds
    return fund_class.to_dict(), list(fund_class)[0]


@callback(
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


clientside_callback(
    ClientsideFunction(
        namespace="visibility", function_name="updateSelectionVisibility"
    ),
    Output("price-selection-container", "style"),
    Output("return-selection", "style"),
    Output("rolling-return-selection-container", "style"),
    Output("calendar-return-selection-container", "style"),
    Input("y-var-selection", "value"),
)


clientside_callback(
    ClientsideFunction(
        namespace="visibility",
        function_name="updateRollingReturnsDistributionChartTypeVisibility",
    ),
    Output("rolling-returns-distribution-chart-type-selection-container", "style"),
    Input("rolling-returns-presentation-selection", "value"),
)


clientside_callback(
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


clientside_callback(
    ClientsideFunction(namespace="state", function_name="updateLastLayoutStore"),
    Output("graph-last-layout-state-store", "data"),
    Input("graph", "figure"),
    State("y-var-selection", "value"),
    prevent_initial_call=True,
)


def update_holding_graph(
    selected_holdings_strs: list[str],
    selected_holdings_options: dict[str, str],
    currency: Currency,
    adjust_for_inflation: bool,
    y_var: YVar,
    log_scale: bool,
    percent_scale: bool,
    auto_scale: bool,
    return_duration: ReturnDuration,
    return_interval: ReturnInterval,
    return_annualisation: ReturnAnnualisation,
    baseline_trace: str,
    rolling_returns_presentation: RollingReturnsPresentation,
    rolling_returns_distribution_chart_type: DistributionChartType,
    relayout_data: RelayoutData | None,
    prev_layout: PrevLayout | None,
    interval: Interval,
):
    if not selected_holdings_strs:
        return no_update
    securities_colourmap = dict(
        zip(
            selected_holdings_options.keys(),
            cycle(DEFAULT_PLOTLY_COLORS),
        )
    )
    selected_holdings = TypeAdapter(list[Json[Holding]]).validate_python(
        selected_holdings_strs
    )
    dfs = [
        load_series(
            selected_security,
            interval,
            currency,
            adjust_for_inflation,
        ).rename({"price": selected_security.model_dump_json()})
        for selected_security in selected_holdings
    ]
    df = reduce(
        lambda left, right: left.join(right, on="date", how="full", coalesce=True), dfs
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
        + baseline_trace
        + rolling_returns_presentation
        + rolling_returns_distribution_chart_type
    )

    relayout_data = relayout_data or {"autosize": True}

    graph_params: GraphParams = TypeAdapter(GraphParams).validate_python(
        {
            "df": df,
            "trace_colourmap": securities_colourmap,
            "y_var": y_var,
            "log_scale": log_scale,
            "percent_scale": percent_scale,
            "auto_scale": auto_scale,
            "interval": interval,
            "return_duration": return_duration,
            "return_interval": return_interval,
            "return_annualisation": return_annualisation,
            "baseline_trace": baseline_trace,
            "rolling_returns_presentation": rolling_returns_presentation,
            "rolling_returns_distribution_chart_type": rolling_returns_distribution_chart_type,
            "relayout_data": relayout_data,
            "uirevision": uirevision,
            "prev_layout": prev_layout,
        }
    )

    data, layout = graph_params.update_graph()
    return dict(data=data, layout=layout)


@callback(
    Output("graph", "figure"),
    Input("selected-securities", "value"),
    Input("selected-securities", "options"),
    Input("currency-selection", "value"),
    Input("inflation-adjustment-switch", "value"),
    Input("y-var-selection", "value"),
    Input("log-scale-switch", "value"),
    Input("percent-scale-switch", "value"),
    Input("auto-scale-switch", "value"),
    Input("return-duration-selection", "value"),
    Input("return-interval-selection", "value"),
    Input("return-annualisation-selection", "value"),
    Input("baseline-security-selection", "value"),
    Input("rolling-returns-presentation-selection", "value"),
    Input("rolling-returns-distribution-chart-type-selection", "value"),
    Input("graph", "relayoutData"),
    State("graph-last-layout-state-store", "data"),
    Input("interval-selection", "value"),
    prevent_initial_call=True,
)
def update_security_graph(
    selected_securities_strs: list[str],
    selected_securities_options: dict[str, str],
    currency: Currency,
    adjust_for_inflation: bool,
    y_var: YVar,
    log_scale: bool,
    percent_scale: bool,
    auto_scale: bool,
    return_duration: ReturnDuration,
    return_interval: ReturnInterval,
    return_annualisation: ReturnAnnualisation,
    baseline_security: str,
    rolling_returns_presentation: RollingReturnsPresentation,
    rolling_returns_distribution_chart_type: DistributionChartType,
    relayout_data: RelayoutData | None,
    prev_layout: PrevLayout | None,
    interval: Interval,
):
    interval = Interval.MONTHLY if y_var == YVar.CALENDAR_RETURNS else interval
    return update_holding_graph(
        selected_securities_strs,
        selected_securities_options,
        currency,
        adjust_for_inflation,
        y_var,
        log_scale,
        percent_scale,
        auto_scale,
        return_duration,
        return_interval,
        return_annualisation,
        baseline_security,
        rolling_returns_presentation,
        rolling_returns_distribution_chart_type,
        relayout_data,
        prev_layout,
        interval,
    )


clientside_callback(
    ClientsideFunction(
        namespace="options",
        function_name="updateSecuritySelectionOptions",
    ),
    Output("portfolio-security-selection", "options"),
    Output("portfolio-security-selection", "value"),
    Input("selected-securities", "options"),
)


@callback(
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
    set_props("security-weight", {"required": False})
    portfolio = Portfolio(
        allocations=TypeAdapter(list[Json[Allocation]]).validate_python(
            portfolio_allocation_strs or []
        )
    )
    if ctx.triggered_id == "portfolio-allocations":
        return list(portfolio.to_plotly_options().keys()), portfolio.to_plotly_options()

    if weight is None:
        set_props("security-weight", {"required": True})
        return no_update
    new_allocation = Allocation(
        security=TypeAdapter(Security).validate_json(security_str),
        weight=weight,
    )
    if new_allocation in portfolio.allocations:
        return no_update
    portfolio.add_allocation(new_allocation=new_allocation)
    return list(portfolio.to_plotly_options().keys()), portfolio.to_plotly_options()


clientside_callback(
    ClientsideFunction(
        namespace="update_values",
        function_name="portfolioWeightsSum",
    ),
    Output("portfolio-weights-sum", "children"),
    Input("portfolio-allocations", "value"),
    prevent_initial_call=True,
)


@callback(
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
        allocations=TypeAdapter(list[Json[Allocation]]).validate_python(
            portfolio_allocation_strs
        )
    )
    if sum([allocation.weight for allocation in portfolio.allocations]) != 100:
        return no_update
    portfolio_str = portfolio.model_dump_json(exclude_none=True)
    if portfolio_strs is None:
        return ([portfolio_str], {portfolio_str: portfolio.label}, [], {})
    if portfolio_str in portfolio_strs:
        return no_update
    portfolio_strs.append(portfolio_str)
    portfolio_options.update({portfolio_str: portfolio.label})
    return (portfolio_strs, portfolio_options, [], {})


clientside_callback(
    ClientsideFunction(
        namespace="visibility", function_name="updateSelectionVisibility"
    ),
    Output("portfolio-price-selection-container", "style"),
    Output("portfolio-return-selection", "style"),
    Output("portfolio-rolling-return-selection-container", "style"),
    Output("portfolio-calendar-return-selection-container", "style"),
    Input("portfolio-y-var-selection", "value"),
)


clientside_callback(
    ClientsideFunction(
        namespace="visibility",
        function_name="updateRollingReturnsDistributionChartTypeVisibility",
    ),
    Output(
        "portfolio-rolling-returns-distribution-chart-type-selection-container", "style"
    ),
    Input("portfolio-rolling-returns-presentation-selection", "value"),
)


clientside_callback(
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


clientside_callback(
    ClientsideFunction(namespace="state", function_name="updateLastLayoutStore"),
    Output("portfolio-graph-last-layout-state-store", "data"),
    Input("portfolio-graph", "figure"),
    State("portfolio-y-var-selection", "value"),
    prevent_initial_call=True,
)


@callback(
    Output("portfolio-graph", "figure"),
    Input("portfolios", "value"),
    State("portfolios", "options"),
    Input("portfolio-currency-selection", "value"),
    Input("portfolio-inflation-adjustment-switch", "value"),
    Input("portfolio-y-var-selection", "value"),
    Input("portfolio-log-scale-switch", "value"),
    Input("portfolio-percent-scale-switch", "value"),
    Input("portfolio-auto-scale-switch", "value"),
    Input("portfolio-return-duration-selection", "value"),
    Input("portfolio-return-interval-selection", "value"),
    Input("portfolio-return-annualisation-selection", "value"),
    Input("portfolio-baseline-security-selection", "value"),
    Input("portfolio-rolling-returns-presentation-selection", "value"),
    Input("portfolio-rolling-returns-distribution-chart-type-selection", "value"),
    Input("portfolio-graph", "relayoutData"),
    State("portfolio-graph-last-layout-state-store", "data"),
    prevent_initial_call=True,
)
def update_portfolio_graph(
    portfolio_strs: list[str],
    portfolio_options: dict[str, str],
    currency: Currency,
    adjust_for_inflation: bool,
    y_var: YVar,
    log_scale: bool,
    percent_scale: bool,
    auto_scale: bool,
    return_duration: ReturnDuration,
    return_interval: ReturnInterval,
    return_annualisation: ReturnAnnualisation,
    baseline_portfolio: str,
    rolling_returns_presentation: RollingReturnsPresentation,
    rolling_returns_distribution_chart_type: DistributionChartType,
    relayout_data: RelayoutData | None,
    prev_layout: PrevLayout | None,
):
    interval = Interval.MONTHLY
    return update_holding_graph(
        portfolio_strs,
        portfolio_options,
        currency,
        adjust_for_inflation,
        y_var,
        log_scale,
        percent_scale,
        auto_scale,
        return_duration,
        return_interval,
        return_annualisation,
        baseline_portfolio,
        rolling_returns_presentation,
        rolling_returns_distribution_chart_type,
        relayout_data,
        prev_layout,
        interval,
    )


clientside_callback(
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


clientside_callback(
    ClientsideFunction(namespace="disabled", function_name="isStrategyInputInvalid"),
    Output("backtest-accumulation-add-strategy-button", "disabled"),
    Input("backtest-accumulation-strategy-portfolio", "value"),
    Input("backtest-accumulation-investment-amount-input", "value"),
    Input("backtest-accumulation-monthly-investment-input", "value"),
    Input("backtest-accumulation-dca-duration-input", "value"),
    Input("backtest-accumulation-dca-interval-input", "value"),
    Input("backtest-accumulation-coast-duration-input", "value"),
    Input("backtest-accumulation-variable-transaction-fees-input", "value"),
    Input("backtest-accumulation-fixed-transaction-fees-input", "value"),
    Input("backtest-accumulation-annualised-holding-fees-input", "value"),
)


clientside_callback(
    ClientsideFunction(namespace="disabled", function_name="isStrategyInputInvalid"),
    Output("backtest-withdrawal-add-strategy-button", "disabled"),
    Input("backtest-withdrawal-strategy-portfolio", "value"),
    Input("backtest-withdrawal-initial-capital-input", "value"),
    Input("backtest-withdrawal-coast-duration-input", "value"),
    Input("backtest-withdrawal-monthly-amount-input", "value"),
    Input("backtest-withdrawal-duration-input", "value"),
    Input("backtest-withdrawal-interval-input", "value"),
    Input("backtest-withdrawal-variable-transaction-fees-input", "value"),
    Input("backtest-withdrawal-fixed-transaction-fees-input", "value"),
    Input("backtest-withdrawal-annualised-holding-fees-input", "value"),
)


clientside_callback(
    ClientsideFunction(namespace="disabled", function_name="isStrategyInputInvalid"),
    Output("bootstrap-accumulation-add-strategy-button", "disabled"),
    Input("bootstrap-accumulation-strategy-portfolio", "value"),
    Input("bootstrap-accumulation-investment-amount-input", "value"),
    Input("bootstrap-accumulation-monthly-investment-input", "value"),
    Input("bootstrap-accumulation-dca-duration-input", "value"),
    Input("bootstrap-accumulation-dca-interval-input", "value"),
    Input("bootstrap-accumulation-coast-duration-input", "value"),
    Input("bootstrap-accumulation-variable-transaction-fees-input", "value"),
    Input("bootstrap-accumulation-fixed-transaction-fees-input", "value"),
    Input("bootstrap-accumulation-annualised-holding-fees-input", "value"),
    Input("bootstrap-accumulation-num-samples-input", "value"),
    Input("bootstrap-accumulation-avg-block-length-input", "value"),
)


clientside_callback(
    ClientsideFunction(namespace="disabled", function_name="isStrategyInputInvalid"),
    Output("bootstrap-withdrawal-add-strategy-button", "disabled"),
    Input("bootstrap-withdrawal-strategy-portfolio", "value"),
    Input("bootstrap-withdrawal-initial-capital-input", "value"),
    Input("bootstrap-withdrawal-coast-duration-input", "value"),
    Input("bootstrap-withdrawal-monthly-amount-input", "value"),
    Input("bootstrap-withdrawal-duration-input", "value"),
    Input("bootstrap-withdrawal-interval-input", "value"),
    Input("bootstrap-withdrawal-variable-transaction-fees-input", "value"),
    Input("bootstrap-withdrawal-fixed-transaction-fees-input", "value"),
    Input("bootstrap-withdrawal-annualised-holding-fees-input", "value"),
    Input("bootstrap-withdrawal-num-samples-input", "value"),
    Input("bootstrap-withdrawal-avg-block-length-input", "value"),
)


clientside_callback(
    ClientsideFunction(
        namespace="visibility", function_name="updateStrategyDrawdownTypeVisibility"
    ),
    Output("backtest-accumulation-drawdown-type-container", "style"),
    Input("backtest-accumulation-y-var-selection", "value"),
)


clientside_callback(
    ClientsideFunction(
        namespace="visibility", function_name="updateStrategyDrawdownTypeVisibility"
    ),
    Output("backtest-withdrawal-drawdown-type-container", "style"),
    Input("backtest-withdrawal-y-var-selection", "value"),
)


@callback(
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
    State("backtest-accumulation-coast-duration-input", "value"),
    State("backtest-accumulation-dca-duration-input", "value"),
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
    strategy_portfolio: str,
    currency: Currency,
    investment_amount: int | float,
    monthly_investment: int | float,
    adjust_monthly_investment_for_inflation: bool,
    coast_duration: int,
    dca_duration: int,
    dca_interval: int,
    variable_transaction_fees: int | float,
    fixed_transaction_fees: int | float,
    annualised_holding_fees: int | float,
    adjust_portfolio_value_for_inflation: bool,
):
    strategy = AccumulationBacktestStrategy(
        strategy_portfolio=Portfolio.model_validate_json(strategy_portfolio),
        currency=currency,
        investment_amount=investment_amount,
        monthly_investment=monthly_investment,
        adjust_monthly_investment_for_inflation=adjust_monthly_investment_for_inflation,
        coast_duration=coast_duration,
        dca_duration=dca_duration,
        dca_interval=dca_interval,
        variable_transaction_fees=variable_transaction_fees,
        fixed_transaction_fees=fixed_transaction_fees,
        annualised_holding_fees=annualised_holding_fees,
        adjust_portfolio_value_for_inflation=adjust_portfolio_value_for_inflation,
    )

    strategy_str = strategy.model_dump_json()
    strategy_name = strategy.label

    if strategies is None:
        return [strategy_str], {strategy_str: strategy_name}
    if strategy_str in strategies:
        return no_update
    strategies.append(strategy_str)
    strategy_options.update({strategy_str: strategy_name})
    return strategies, strategy_options


def simulate_backtest_accumulation_strategy(strategy: AccumulationBacktestStrategy):
    strategy_series = load_series(
        strategy.strategy_portfolio,
        Interval.MONTHLY,
        strategy.currency,
        False,
    )
    cash_returns = (
        load_fed_funds_returns()
        if strategy.currency == Currency.USD
        else load_sgd_interest_rates_returns()
    ).pipe(resample_bme)
    cpi = load_cpi(strategy.currency)

    df = (
        strategy_series.rename({"price": "strategy"})
        .join(
            cash_returns.rename({"price": "cash"}),
            on="date",
            coalesce=True,
            maintain_order="left",
        )
        .join(cpi, on="date", coalesce=True, maintain_order="left")
    )

    portfolio_values = pd.DataFrame(
        calculate_dca_portfolio_value_with_fees_and_interest_vector(
            df.get_column("strategy").pct_change().to_numpy(),
            strategy.dca_duration,
            strategy.dca_interval,
            strategy.strategy_horizon,
            strategy.investment_amount,
            strategy.monthly_investment,
            strategy.adjust_monthly_investment_for_inflation,
            strategy.variable_transaction_fees,
            strategy.fixed_transaction_fees,
            strategy.annualised_holding_fees,
            strategy.adjust_portfolio_value_for_inflation,
            df.get_column("cpi").to_numpy(),
            df.get_column("cash").to_numpy(),
        ),
        index=df.get_column("date").to_pandas(),
        columns=range(strategy.strategy_horizon + 1),
    )
    return portfolio_values


def simulate_backtest_withdrawal_strategy(strategy: WithdrawalBacktestStrategy):

    strategy_series = load_series(
        strategy.strategy_portfolio,
        Interval.MONTHLY,
        strategy.currency,
        False,
    )
    cpi = load_cpi(strategy.currency)

    df = strategy_series.rename({"price": "strategy"}).join(
        cpi, on="date", coalesce=True, maintain_order="left"
    )

    portfolio_values = pd.DataFrame(
        calculate_withdrawal_portfolio_value_with_fees_vector(
            df.get_column("strategy").pct_change().to_numpy(),
            strategy.coast_duration,
            strategy.strategy_horizon,
            strategy.withdrawal_interval,
            strategy.initial_capital,
            strategy.monthly_withdrawal,
            df.get_column("cpi").to_numpy(),
            strategy.variable_transaction_fees,
            strategy.fixed_transaction_fees,
            strategy.annualised_holding_fees,
            strategy.adjust_withdrawals_for_inflation,
            strategy.adjust_portfolio_value_for_inflation,
        ),
        index=df.get_column("date").to_pandas(),
        columns=range(strategy.strategy_horizon + 1),
    )
    return portfolio_values


def simulate_backtest_strategy(
    strategy: BacktestStrategy,
):
    if isinstance(strategy, AccumulationBacktestStrategy):
        return simulate_backtest_accumulation_strategy(strategy)
    if isinstance(strategy, WithdrawalBacktestStrategy):
        return simulate_backtest_withdrawal_strategy(strategy)
    raise ValueError("Invalid strategy type")


def update_backtest_strategy_graph(
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    index_by_start_date: bool,
    y_var: BacktestYVar,
    drawdown_type: DrawdownType,
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
        strategy: BacktestStrategy = TypeAdapter(BacktestStrategy).validate_json(
            strategy_str
        )
        portfolio_values = simulate_backtest_strategy(strategy)
        if index_by_start_date:
            portfolio_values = portfolio_values.shift(-strategy.strategy_horizon)
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


@callback(
    Output("backtest-accumulation-strategy-graph", "figure"),
    Input("backtest-accumulation-strategies", "value"),
    State("backtest-accumulation-strategies", "options"),
    Input("backtest-accumulation-index-by-start-date", "value"),
    Input("backtest-accumulation-y-var-selection", "value"),
    Input("backtest-accumulation-drawdown-type-selection", "value"),
    prevent_initial_call=True,
)
def update_backtest_accumulation_strategy_graph(
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    index_by_start_date: bool,
    y_var: BacktestYVar,
    drawdown_type: DrawdownType,
):
    return update_backtest_strategy_graph(
        strategy_strs,
        strategy_options,
        index_by_start_date,
        y_var,
        drawdown_type,
    )


def show_backtest_strategy_modal(
    clicked_date_str: str,
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    index_by_start_date: bool,
):
    if not clicked_date_str:
        return False, {}

    clicked_date = pd.to_datetime(clicked_date_str)

    strategies_colourmap = dict(
        zip(strategy_options.keys(), cycle(DEFAULT_PLOTLY_COLORS))
    )

    traces = []
    for strategy_str in strategy_strs:
        strategy: BacktestStrategy = TypeAdapter(BacktestStrategy).validate_json(
            strategy_str
        )
        portfolio_values = simulate_backtest_strategy(strategy)
        portfolio_values = portfolio_values.dropna(how="all")
        end_date = clicked_date
        if index_by_start_date:
            end_date = clicked_date + pd.offsets.BMonthEnd(strategy.strategy_horizon)
        if end_date not in portfolio_values.index:
            continue

        dates = pd.date_range(
            end=end_date, periods=strategy.strategy_horizon + 1, freq="BME"
        )

        traces.append(
            go.Scatter(
                x=dates,
                y=portfolio_values.loc[end_date].values,
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


class Point(TypedDict):
    x: str


class ClickData(TypedDict):
    points: list[Point]


@callback(
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


@callback(
    Output("backtest-accumulation-strategy-modal", "is_open"),
    Output("backtest-accumulation-strategy-modal-graph", "figure"),
    Input("backtest-accumulation-strategy-show-details-button", "n_clicks"),
    State("backtest-accumulation-strategy-clicked-date-store", "data"),
    State("backtest-accumulation-strategies", "value"),
    State("backtest-accumulation-strategies", "options"),
    State("backtest-accumulation-index-by-start-date", "value"),
    prevent_initial_call=True,
)
def show_backtest_accumulation_strategy_modal(
    _,
    clicked_date_str: str,
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    index_by_start_date: bool,
):
    return show_backtest_strategy_modal(
        clicked_date_str,
        strategy_strs,
        strategy_options,
        index_by_start_date,
    )


@callback(
    Output("backtest-withdrawal-strategies", "value"),
    Output("backtest-withdrawal-strategies", "options"),
    Input("backtest-withdrawal-add-strategy-button", "n_clicks"),
    State("backtest-withdrawal-strategies", "value"),
    State("backtest-withdrawal-strategies", "options"),
    State("backtest-withdrawal-strategy-portfolio", "value"),
    State("backtest-withdrawal-strategy-currency-selection", "value"),
    State("backtest-withdrawal-initial-capital-input", "value"),
    State("backtest-withdrawal-coast-duration-input", "value"),
    State("backtest-withdrawal-monthly-amount-input", "value"),
    State("backtest-withdrawal-monthly-inflation-adjustment-switch", "value"),
    State("backtest-withdrawal-duration-input", "value"),
    State("backtest-withdrawal-interval-input", "value"),
    State("backtest-withdrawal-variable-transaction-fees-input", "value"),
    State("backtest-withdrawal-fixed-transaction-fees-input", "value"),
    State("backtest-withdrawal-annualised-holding-fees-input", "value"),
    State("backtest-withdrawal-portfolio-value-inflation-adjustment-switch", "value"),
    prevent_initial_call=True,
)
def update_backtest_withdrawal_strategies(
    _,
    strategies: list[str] | None,
    strategy_options: dict[str, str],
    strategy_portfolio: str,
    currency: Currency,
    initial_capital: int | float,
    coast_duration: int,
    monthly_withdrawal: int | float,
    adjust_withdrawals_for_inflation: bool,
    withdrawal_duration: int,
    withdrawal_interval: int,
    variable_transaction_fees: int | float,
    fixed_transaction_fees: int | float,
    annualised_holding_fees: int | float,
    adjust_portfolio_value_for_inflation: bool,
):
    strategy = WithdrawalBacktestStrategy(
        strategy_portfolio=Portfolio.model_validate_json(strategy_portfolio),
        currency=currency,
        initial_capital=initial_capital,
        coast_duration=coast_duration,
        monthly_withdrawal=monthly_withdrawal,
        adjust_withdrawals_for_inflation=adjust_withdrawals_for_inflation,
        adjust_portfolio_value_for_inflation=adjust_portfolio_value_for_inflation,
        withdrawal_duration=withdrawal_duration,
        withdrawal_interval=withdrawal_interval,
        variable_transaction_fees=variable_transaction_fees,
        fixed_transaction_fees=fixed_transaction_fees,
        annualised_holding_fees=annualised_holding_fees,
    )

    strategy_str = strategy.model_dump_json()
    strategy_name = strategy.label

    if strategies is None:
        return [strategy_str], {strategy_str: strategy_name}
    if strategy_str in strategies:
        return no_update
    strategies.append(strategy_str)
    strategy_options.update({strategy_str: strategy_name})
    return strategies, strategy_options


@callback(
    Output("backtest-withdrawal-strategy-graph", "figure"),
    Input("backtest-withdrawal-strategies", "value"),
    State("backtest-withdrawal-strategies", "options"),
    Input("backtest-withdrawal-index-by-start-date", "value"),
    Input("backtest-withdrawal-y-var-selection", "value"),
    Input("backtest-withdrawal-drawdown-type-selection", "value"),
    prevent_initial_call=True,
)
def update_backtest_withdrawal_strategy_graph(
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    index_by_start_date: bool,
    y_var: BacktestYVar,
    drawdown_type: DrawdownType,
):
    return update_backtest_strategy_graph(
        strategy_strs,
        strategy_options,
        index_by_start_date,
        y_var,
        drawdown_type,
    )


@callback(
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


@callback(
    Output("backtest-withdrawal-strategy-modal", "is_open"),
    Output("backtest-withdrawal-strategy-modal-graph", "figure"),
    Input("backtest-withdrawal-strategy-show-details-button", "n_clicks"),
    State("backtest-withdrawal-strategy-clicked-date-store", "data"),
    State("backtest-withdrawal-strategies", "value"),
    State("backtest-withdrawal-strategies", "options"),
    State("backtest-withdrawal-index-by-start-date", "value"),
    prevent_initial_call=True,
)
def show_backtest_withdrawal_strategy_modal(
    _,
    clicked_date_str: str,
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    index_by_start_date: bool,
):
    return show_backtest_strategy_modal(
        clicked_date_str,
        strategy_strs,
        strategy_options,
        index_by_start_date,
    )


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


def simulate_bootstrap_accumulation_strategy(strategy: AccumulationBootstrapStrategy):
    strategy_series = load_series(
        strategy.strategy_portfolio,
        Interval.MONTHLY,
        strategy.currency,
        False,
    )
    cash_returns = (
        load_fed_funds_returns()
        if strategy.currency == Currency.USD
        else load_sgd_interest_rates_returns()
    ).pipe(resample_bme)
    cpi = load_cpi(strategy.currency)

    df = (
        strategy_series.rename({"price": "strategy"})
        .join(
            cash_returns.rename({"price": "cash"}),
            on="date",
            coalesce=True,
            maintain_order="left",
        )
        .join(cpi, on="date", coalesce=True, maintain_order="left")
        .with_columns(pl.all().exclude("date").pct_change())
        .drop_nulls()
    )

    strategy_series = df.get_column("strategy").to_numpy()
    cpi = df.get_column("cpi").to_numpy()
    cash_returns = df.get_column("cash").to_numpy()

    n_data = len(strategy_series)
    sample_length = strategy.strategy_horizon + 1
    indices = generate_bootstrap_indices(
        strategy.num_bootstrap_samples, sample_length, n_data, strategy.avg_block_length
    )
    portfolio_values = simulate_bootstrap_accumulation(
        strategy_series,
        cpi,
        cash_returns,
        indices,
        strategy.dca_duration,
        strategy.dca_interval,
        strategy.strategy_horizon,
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
    strategy: WithdrawalBootstrapStrategy,
):

    strategy_series = load_series(
        strategy.strategy_portfolio,
        Interval.MONTHLY,
        strategy.currency,
        False,
    )
    cpi = load_cpi(strategy.currency)

    df = strategy_series.rename({"price": "strategy"}).join(
        cpi, on="date", coalesce=True, maintain_order="left"
    )

    monthly_returns = df.get_column("strategy").pct_change().to_numpy()[1:]
    cpi = df.get_column("cpi").pct_change().to_numpy()[1:]

    n_data = len(monthly_returns)
    sample_length = strategy.strategy_horizon + 1
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
        strategy.coast_duration,
        strategy.strategy_horizon,
        strategy.withdrawal_interval,
        strategy.initial_capital,
        strategy.monthly_withdrawal,
        strategy.variable_transaction_fees,
        strategy.fixed_transaction_fees,
        strategy.annualised_holding_fees,
        strategy.adjust_withdrawals_for_inflation,
        strategy.adjust_portfolio_value_for_inflation,
    )
    return portfolio_values


def simulate_bootstrap_strategy(
    strategy: BootstrapStrategy,
):
    if isinstance(strategy, AccumulationBootstrapStrategy):
        return simulate_bootstrap_accumulation_strategy(strategy)
    if isinstance(strategy, WithdrawalBootstrapStrategy):
        return simulate_bootstrap_withdrawal_strategy(strategy)
    raise ValueError("Invalid strategy type")


@callback(
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
    State("bootstrap-accumulation-coast-duration-input", "value"),
    State("bootstrap-accumulation-dca-duration-input", "value"),
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
    strategy_portfolio: str,
    currency: Currency,
    investment_amount: int | float,
    monthly_investment: int | float,
    adjust_monthly_investment_for_inflation: bool,
    coast_duration: int,
    dca_duration: int,
    dca_interval: int,
    variable_transaction_fees: int | float,
    fixed_transaction_fees: int | float,
    annualised_holding_fees: int | float,
    adjust_portfolio_value_for_inflation: bool,
    num_samples: int,
    avg_block_len: int | float,
):
    strategy = AccumulationBootstrapStrategy(
        strategy_portfolio=Portfolio.model_validate_json(strategy_portfolio),
        currency=currency,
        investment_amount=investment_amount,
        monthly_investment=monthly_investment,
        adjust_monthly_investment_for_inflation=adjust_monthly_investment_for_inflation,
        coast_duration=coast_duration,
        dca_duration=dca_duration,
        dca_interval=dca_interval,
        variable_transaction_fees=variable_transaction_fees,
        fixed_transaction_fees=fixed_transaction_fees,
        annualised_holding_fees=annualised_holding_fees,
        adjust_portfolio_value_for_inflation=adjust_portfolio_value_for_inflation,
        num_bootstrap_samples=num_samples,
        avg_block_length=avg_block_len,
    )

    strategy_str = strategy.model_dump_json()
    strategy_name = strategy.label

    if strategies is None:
        return [strategy_str], {strategy_str: strategy_name}
    if strategy_str in strategies:
        return no_update
    strategies.append(strategy_str)
    strategy_options.update({strategy_str: strategy_name})
    return strategies, strategy_options


def update_bootstrap_strategy_graph(
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    y_var: BootstrapYVar,
    log_scale: bool,
):
    if not strategy_strs:
        return {
            "data": [],
            "layout": {
                "title": "Strategy Performance",
            },
        }
    strategies_colourmap = dict(
        zip(strategy_options.keys(), cycle(DEFAULT_PLOTLY_COLORS))
    )
    all_traces = []
    for strategy_str in strategy_strs:
        strategy: BootstrapStrategy = TypeAdapter(BootstrapStrategy).validate_json(
            strategy_str
        )
        portfolio_values = simulate_bootstrap_strategy(strategy)
        months = np.arange(strategy.strategy_horizon + 1)
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
            title="Strategy Performance",
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


@callback(
    Output("bootstrap-accumulation-graph", "figure"),
    Input("bootstrap-accumulation-strategies", "value"),
    State("bootstrap-accumulation-strategies", "options"),
    Input("bootstrap-accumulation-y-var-selection", "value"),
    Input("bootstrap-accumulation-log-scale-switch", "value"),
    prevent_initial_call=True,
)
def update_bootstrap_accumulation_graph(
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    y_var: BootstrapYVar,
    log_scale: bool,
):
    return update_bootstrap_strategy_graph(
        strategy_strs, strategy_options, y_var, log_scale
    )


@callback(
    Output("bootstrap-withdrawal-strategies", "value"),
    Output("bootstrap-withdrawal-strategies", "options"),
    Input("bootstrap-withdrawal-add-strategy-button", "n_clicks"),
    State("bootstrap-withdrawal-strategies", "value"),
    State("bootstrap-withdrawal-strategies", "options"),
    State("bootstrap-withdrawal-strategy-portfolio", "value"),
    State("bootstrap-withdrawal-strategy-currency-selection", "value"),
    State("bootstrap-withdrawal-initial-capital-input", "value"),
    State("bootstrap-withdrawal-coast-duration-input", "value"),
    State("bootstrap-withdrawal-monthly-amount-input", "value"),
    State("bootstrap-withdrawal-monthly-inflation-adjustment-switch", "value"),
    State("bootstrap-withdrawal-duration-input", "value"),
    State("bootstrap-withdrawal-interval-input", "value"),
    State("bootstrap-withdrawal-variable-transaction-fees-input", "value"),
    State("bootstrap-withdrawal-fixed-transaction-fees-input", "value"),
    State("bootstrap-withdrawal-annualised-holding-fees-input", "value"),
    State("bootstrap-withdrawal-num-samples-input", "value"),
    State("bootstrap-withdrawal-avg-block-length-input", "value"),
    State("bootstrap-withdrawal-portfolio-value-inflation-adjustment-switch", "value"),
    prevent_initial_call=True,
)
def update_bootstrap_withdrawal_strategies(
    _,
    strategies: list[str] | None,
    strategy_options: dict[str, str],
    strategy_portfolio: str,
    currency: Currency,
    initial_capital: int | float,
    coast_duration: int,
    monthly_withdrawal: int | float,
    adjust_withdrawals_for_inflation: bool,
    withdrawal_duration: int,
    withdrawal_interval: int,
    variable_transaction_fees: int | float,
    fixed_transaction_fees: int | float,
    annualised_holding_fees: int | float,
    num_samples: int,
    avg_block_len: int | float,
    adjust_portfolio_value_for_inflation: bool,
):
    strategy = WithdrawalBootstrapStrategy(
        strategy_portfolio=Portfolio.model_validate_json(strategy_portfolio),
        currency=currency,
        initial_capital=initial_capital,
        coast_duration=coast_duration,
        monthly_withdrawal=monthly_withdrawal,
        adjust_withdrawals_for_inflation=adjust_withdrawals_for_inflation,
        adjust_portfolio_value_for_inflation=adjust_portfolio_value_for_inflation,
        withdrawal_duration=withdrawal_duration,
        withdrawal_interval=withdrawal_interval,
        variable_transaction_fees=variable_transaction_fees,
        fixed_transaction_fees=fixed_transaction_fees,
        annualised_holding_fees=annualised_holding_fees,
        num_bootstrap_samples=num_samples,
        avg_block_length=avg_block_len,
    )

    strategy_str = strategy.model_dump_json()
    strategy_name = strategy.label

    if strategies is None:
        return [strategy_str], {strategy_str: strategy_name}
    if strategy_str in strategies:
        return no_update
    strategies.append(strategy_str)
    strategy_options.update({strategy_str: strategy_name})
    return strategies, strategy_options


@callback(
    Output("bootstrap-withdrawal-graph", "figure"),
    Input("bootstrap-withdrawal-strategies", "value"),
    State("bootstrap-withdrawal-strategies", "options"),
    Input("bootstrap-withdrawal-y-var-selection", "value"),
    Input("bootstrap-withdrawal-log-scale-switch", "value"),
    prevent_initial_call=True,
)
def update_bootstrap_withdrawal_graph(
    strategy_strs: list[str],
    strategy_options: dict[str, str],
    y_var: BootstrapYVar,
    log_scale: bool,
):
    return update_bootstrap_strategy_graph(
        strategy_strs,
        strategy_options,
        y_var,
        log_scale,
    )


if __name__ == "__main__":
    app.run("0.0.0.0", debug=True)
