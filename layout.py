import dash_bootstrap_components as dbc
from dash import dcc, html

from models import (
    BacktestYVar,
    BootstrapYVar,
    Currency,
    DistributionChartType,
    DrawdownType,
    FREDIndex,
    FundCompany,
    IndexProvider,
    Interval,
    MASIndex,
    MSCIIndexType,
    MSCIRegionalIndex,
    MSCISize,
    MSCIStyle,
    OthersIndex,
    ReturnAnnualisation,
    ReturnDuration,
    ReturnInterval,
    RollingReturnsPresentation,
    SecurityType,
    SGSDuration,
    TaxTreatment,
    USTreasuryDuration,
    YVar,
)

app_layout = html.Div(
    dbc.Tabs(
        [
            dbc.Tab(
                label="Returns Dashboard",
                children=html.Div(
                    [
                        html.Div(
                            [
                                dbc.Label(
                                    "Security Type", html_for="security-type-selection"
                                ),
                                dbc.Select(
                                    SecurityType.to_dict(),
                                    value=SecurityType.INDEX,
                                    id="security-type-selection",
                                ),
                                html.Div(
                                    [
                                        dbc.Label(
                                            "Index Provider",
                                            html_for="index-provider-selection",
                                        ),
                                        dbc.Select(
                                            IndexProvider.to_dict(),
                                            value=IndexProvider.MSCI,
                                            id="index-provider-selection",
                                        ),
                                        html.Div(
                                            [
                                                dbc.Label(
                                                    "Index Type",
                                                    html_for="msci-index-type-selection",
                                                ),
                                                dbc.Select(
                                                    MSCIIndexType.to_dict(),
                                                    value=MSCIIndexType.REGIONAL,
                                                    id="msci-index-type-selection",
                                                ),
                                                dbc.Label(
                                                    "Base Index",
                                                    html_for="msci-index-selection",
                                                ),
                                                dbc.Select(
                                                    MSCIRegionalIndex.to_dict(),
                                                    value=MSCIRegionalIndex.WORLD,
                                                    id="msci-index-selection",
                                                ),
                                                dbc.Label(
                                                    "Size",
                                                    html_for="msci-size-selection",
                                                ),
                                                dbc.Select(
                                                    MSCISize.to_dict(),
                                                    value=MSCISize.STANDARD,
                                                    id="msci-size-selection",
                                                ),
                                                dbc.Label(
                                                    "Style",
                                                    html_for="msci-style-selection",
                                                ),
                                                dbc.Select(
                                                    MSCIStyle.to_dict(),
                                                    value=MSCIStyle.BLEND,
                                                    id="msci-style-selection",
                                                ),
                                                dbc.Label(
                                                    "Tax Treatment",
                                                    html_for="msci-tax-treatment-selection",
                                                ),
                                                dbc.Select(
                                                    TaxTreatment.to_dict(),
                                                    value=TaxTreatment.GROSS,
                                                    id="msci-tax-treatment-selection",
                                                ),
                                            ],
                                            id="msci-index-selection-container",
                                        ),
                                        html.Div(
                                            [
                                                dbc.Label(
                                                    "Index",
                                                    html_for="fred-index-selection",
                                                ),
                                                dbc.Select(
                                                    FREDIndex.to_dict(),
                                                    value=FREDIndex.US_T,
                                                    id="fred-index-selection",
                                                ),
                                                html.Div(
                                                    [
                                                        dbc.Label(
                                                            "Duration",
                                                            html_for="us-treasury-duration-selection",
                                                        ),
                                                        dbc.Select(
                                                            USTreasuryDuration.to_dict(),
                                                            value=USTreasuryDuration.DURATION_1MO,
                                                            id="us-treasury-duration-selection",
                                                        ),
                                                    ],
                                                    id="us-treasury-index-selection-container",
                                                ),
                                            ],
                                            id="fred-index-selection-container",
                                        ),
                                        html.Div(
                                            [
                                                dbc.Label(
                                                    "Index",
                                                    html_for="mas-index-selection",
                                                ),
                                                dbc.Select(
                                                    MASIndex.to_dict(),
                                                    value=MASIndex.SGS,
                                                    id="mas-index-selection",
                                                ),
                                                html.Div(
                                                    [
                                                        dbc.Label(
                                                            "Duration",
                                                            html_for="sgs-duration-selection",
                                                        ),
                                                        dbc.Select(
                                                            SGSDuration.to_dict(),
                                                            value=SGSDuration.DURATION_1Y,
                                                            id="sgs-duration-selection",
                                                        ),
                                                    ],
                                                    id="sgs-index-selection-container",
                                                ),
                                            ],
                                            id="mas-index-selection-container",
                                        ),
                                        html.Div(
                                            [
                                                dbc.Label(
                                                    "Index",
                                                    html_for="others-index-selection",
                                                ),
                                                dbc.Select(
                                                    OthersIndex.to_dict(),
                                                    value=OthersIndex.SPX,
                                                    id="others-index-selection",
                                                ),
                                                html.Div(
                                                    [
                                                        dbc.Label(
                                                            "Tax Treatment",
                                                            html_for="others-tax-treatment-selection",
                                                        ),
                                                        dbc.Select(
                                                            TaxTreatment.to_dict(),
                                                            value=TaxTreatment.GROSS,
                                                            id="others-tax-treatment-selection",
                                                        ),
                                                    ],
                                                    id="others-tax-treatment-selection-container",
                                                ),
                                            ],
                                            id="others-index-selection-container",
                                        ),
                                        html.P(),
                                        dbc.Button("Add Index", id="add-index-button"),
                                    ],
                                    id="index-selection-container",
                                ),
                                html.Div(
                                    [
                                        html.P(),
                                        dbc.Label(
                                            "Yahoo Finance Ticker",
                                            html_for="yf-security-input",
                                        ),
                                        html.Br(),
                                        dbc.Input(id="yf-security-input", type="text"),
                                        dbc.Label(
                                            "Tax Treatment",
                                            html_for="yf-security-tax-treatment-selection",
                                        ),
                                        dbc.Select(
                                            TaxTreatment.to_dict(),
                                            value=TaxTreatment.GROSS,
                                            id="yf-security-tax-treatment-selection",
                                        ),
                                        html.P(),
                                        dbc.Button(
                                            "Add Stock/ETF", id="add-yf-security-button"
                                        ),
                                        html.P(),
                                    ],
                                    id="yf-security-selection-container",
                                ),
                                dcc.Store(
                                    id="yf-invalid-securities-store",
                                    storage_type="memory",
                                    data=[],
                                ),
                                dcc.Store(
                                    id="yf-valid-securities-store",
                                    storage_type="memory",
                                    data={},
                                ),
                                dcc.Store(
                                    id="yf-ticker-currency-store",
                                    storage_type="memory",
                                    data={},
                                ),
                                html.Div(
                                    [
                                        dbc.Label(
                                            "Fund Company",
                                            html_for="fund-company-selection",
                                        ),
                                        dbc.Select(
                                            FundCompany.to_dict(),
                                            value=FundCompany.GREATLINK,
                                            id="fund-company-selection",
                                        ),
                                        dbc.Label("Fund", html_for="fund-selection"),
                                        dbc.Select(
                                            {},
                                            id="fund-selection",
                                        ),
                                        html.P(),
                                        dbc.Button("Add Fund", id="add-fund-button"),
                                    ],
                                    id="fund-selection-container",
                                ),
                                html.Div(
                                    [
                                        html.P(),
                                        dbc.Label(
                                            "FT Ticker", html_for="ft-security-input"
                                        ),
                                        html.Br(),
                                        dbc.Input(id="ft-security-input", type="text"),
                                        html.P(),
                                        dbc.Button(
                                            "Add FT Security",
                                            id="add-ft-security-button",
                                        ),
                                        html.P(),
                                    ],
                                    id="ft-security-selection-container",
                                ),
                                dcc.Store(
                                    id="ft-invalid-securities-store",
                                    storage_type="memory",
                                    data=[],
                                ),
                                dcc.Store(
                                    id="ft-valid-securities-store",
                                    storage_type="memory",
                                    data={},
                                ),
                                dcc.Store(
                                    id="ft-ticker-info-store",
                                    storage_type="memory",
                                    data={},
                                ),
                                dcc.Store(
                                    id="toast-store", storage_type="memory", data=""
                                ),
                                html.P(),
                                html.Div(
                                    [
                                        dbc.Toast(
                                            "",
                                            id="toast",
                                            header="Info",
                                            is_open=False,
                                            dismissable=True,
                                            duration=5000,
                                            color="info",
                                        ),
                                    ],
                                    style={"display": "flex"},
                                ),
                                html.P(),
                                dbc.Label(
                                    "Selected Securities",
                                    html_for="selected-securities",
                                ),
                                html.Div(
                                    [
                                        dcc.Dropdown(
                                            {},
                                            multi=True,
                                            searchable=False,
                                            id="selected-securities",
                                            style={"width": 0, "flexGrow": 1},
                                        ),
                                    ],
                                    style={"display": "flex"},
                                ),
                                dbc.Label("Interval", html_for="interval-selection"),
                                dbc.Select(
                                    Interval.to_dict(),
                                    value=Interval.MONTHLY,
                                    id="interval-selection",
                                ),
                                dbc.Label("Currency", html_for="currency-selection"),
                                dbc.Select(
                                    Currency.to_dict(),
                                    value=Currency.USD,
                                    id="currency-selection",
                                ),
                                dbc.Switch(
                                    "inflation-adjustment-switch",
                                    value=False,
                                    label="Adjust for Inflation",
                                ),
                                dbc.Label("Value", html_for="y-var-selection"),
                                dbc.Select(
                                    YVar.to_dict(),
                                    value=YVar.PRICE,
                                    id="y-var-selection",
                                ),
                                html.Div(
                                    [
                                        dbc.Switch(
                                            "log-scale-switch",
                                            value=False,
                                            label="Logarithmic Scale",
                                        ),
                                        dbc.Switch(
                                            "percent-scale-switch",
                                            value=False,
                                            label="% Scale",
                                        ),
                                        dbc.Switch(
                                            "auto-scale-switch",
                                            value=False,
                                            label="Auto Scale",
                                        ),
                                    ],
                                    id="price-selection-container",
                                ),
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                dbc.Label(
                                                    "Return Interval",
                                                    html_for="return-interval-selection",
                                                ),
                                                dbc.Select(
                                                    ReturnInterval.to_dict(),
                                                    value=ReturnInterval.MONTHLY,
                                                    id="return-interval-selection",
                                                ),
                                            ],
                                            id="calendar-return-selection-container",
                                        ),
                                        html.Div(
                                            [
                                                dbc.Label(
                                                    "Return Duration",
                                                    html_for="return-duration-selection",
                                                ),
                                                dbc.Select(
                                                    ReturnDuration.to_dict(),
                                                    value=ReturnDuration.DURATION_1MO,
                                                    id="return-duration-selection",
                                                ),
                                                dbc.Label(
                                                    "Return Annualisation",
                                                    html_for="return-annualisation-selection",
                                                ),
                                                dbc.Select(
                                                    ReturnAnnualisation.to_dict(),
                                                    value=ReturnAnnualisation.CUMULATIVE,
                                                    id="return-annualisation-selection",
                                                ),
                                                dbc.Label(
                                                    "Presentation",
                                                    html_for="rolling-returns-presentation-selection",
                                                ),
                                                dbc.Select(
                                                    RollingReturnsPresentation.to_dict(),
                                                    value=RollingReturnsPresentation.TIMESERIES,
                                                    id="rolling-returns-presentation-selection",
                                                ),
                                                html.Div(
                                                    [
                                                        dbc.Label(
                                                            "Chart Type",
                                                            html_for="rolling-returns-distribution-chart-type-selection",
                                                        ),
                                                        dbc.Select(
                                                            DistributionChartType.to_dict(),
                                                            value=DistributionChartType.HISTOGRAM,
                                                            id="rolling-returns-distribution-chart-type-selection",
                                                        ),
                                                    ],
                                                    id="rolling-returns-distribution-chart-type-selection-container",
                                                ),
                                            ],
                                            id="rolling-return-selection-container",
                                        ),
                                        dbc.Label(
                                            "Baseline",
                                            html_for="baseline-security-selection",
                                        ),
                                        dbc.Select(
                                            {
                                                "None": "None",
                                            },
                                            value="None",
                                            id="baseline-security-selection",
                                        ),
                                    ],
                                    id="return-selection",
                                ),
                            ],
                            className="sidebar",
                        ),
                        html.Div(
                            [
                                dcc.Graph(
                                    responsive=True,
                                    id="graph",
                                    config={"toImageButtonOptions": {"scale": 4}},
                                ),
                                dcc.Store(
                                    id="graph-last-layout-state-store",
                                    storage_type="memory",
                                ),
                            ],
                            className="graph-container",
                        ),
                    ],
                ),
            ),
            dbc.Tab(
                label="Portfolio Constructor",
                children=html.Div(
                    [
                        html.Div(
                            [
                                dbc.Label(
                                    "Security", html_for="portfolio-security-selection"
                                ),
                                dbc.Select(
                                    {},
                                    id="portfolio-security-selection",
                                ),
                                dbc.Label("Weight (%)", html_for="security-weight"),
                                dbc.Input(
                                    id="security-weight",
                                    type="number",
                                    step=0.01,
                                    min=0.01,
                                    max=100,
                                ),
                                html.P(),
                                dbc.Button("Add Security", id="add-security-button"),
                                html.P(),
                                dbc.Label(
                                    "Portfolio Allocations",
                                    html_for="portfolio-allocations",
                                ),
                                html.Div(
                                    [
                                        dcc.Dropdown(
                                            {},
                                            id="portfolio-allocations",
                                            multi=True,
                                            searchable=False,
                                            className="show-all-dropdown-value-items",
                                            style={"width": 0, "flexGrow": 1},
                                        )
                                    ],
                                    style={"display": "flex"},
                                ),
                                html.P(
                                    "Sum of Weights: ",
                                    id="portfolio-weights-sum",
                                ),
                                html.P(),
                                dbc.Button("Add Portfolio", id="add-portfolio-button"),
                                html.P(),
                                html.Div(
                                    [
                                        dcc.Dropdown(
                                            {},
                                            id="portfolios",
                                            multi=True,
                                            searchable=False,
                                            style={"width": 0, "flexGrow": 1},
                                        )
                                    ],
                                    style={"display": "flex"},
                                ),
                                dbc.Label(
                                    "Currency", html_for="portfolio-currency-selection"
                                ),
                                dbc.Select(
                                    Currency.to_dict(),
                                    value=Currency.USD,
                                    id="portfolio-currency-selection",
                                ),
                                dbc.Switch(
                                    "portfolio-inflation-adjustment-switch",
                                    value=False,
                                    label="Adjust for Inflation",
                                ),
                                dbc.Label(
                                    "Value", html_for="portfolio-y-var-selection"
                                ),
                                dbc.Select(
                                    YVar.to_dict(),
                                    value=YVar.PRICE,
                                    id="portfolio-y-var-selection",
                                ),
                                html.Div(
                                    [
                                        dbc.Switch(
                                            "portfolio-log-scale-switch",
                                            value=False,
                                            label="Logarithmic Scale",
                                        ),
                                        dbc.Switch(
                                            "portfolio-percent-scale-switch",
                                            value=False,
                                            label="% Scale",
                                        ),
                                        dbc.Switch(
                                            "portfolio-auto-scale-switch",
                                            value=False,
                                            label="Auto Scale",
                                        ),
                                    ],
                                    id="portfolio-price-selection-container",
                                ),
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                dbc.Label(
                                                    "Return Interval",
                                                    html_for="portfolio-return-interval-selection",
                                                ),
                                                dbc.Select(
                                                    ReturnInterval.to_dict(),
                                                    value=ReturnInterval.MONTHLY,
                                                    id="portfolio-return-interval-selection",
                                                ),
                                            ],
                                            id="portfolio-calendar-return-selection-container",
                                        ),
                                        html.Div(
                                            [
                                                dbc.Label(
                                                    "Return Duration",
                                                    html_for="portfolio-return-duration-selection",
                                                ),
                                                dbc.Select(
                                                    ReturnDuration.to_dict(),
                                                    value=ReturnDuration.DURATION_1MO,
                                                    id="portfolio-return-duration-selection",
                                                ),
                                                dbc.Label(
                                                    "Return Annualisation",
                                                    html_for="portfolio-return-annualisation-selection",
                                                ),
                                                dbc.Select(
                                                    ReturnAnnualisation.to_dict(),
                                                    value=ReturnAnnualisation.CUMULATIVE,
                                                    id="portfolio-return-annualisation-selection",
                                                ),
                                                dbc.Label(
                                                    "Presentation",
                                                    html_for="portfolio-rolling-returns-presentation-selection",
                                                ),
                                                dbc.Select(
                                                    RollingReturnsPresentation.to_dict(),
                                                    value=RollingReturnsPresentation.TIMESERIES,
                                                    id="portfolio-rolling-returns-presentation-selection",
                                                ),
                                                html.Div(
                                                    [
                                                        dbc.Label(
                                                            "Chart Type",
                                                            html_for="portfolio-rolling-returns-distribution-chart-type-selection",
                                                        ),
                                                        dbc.Select(
                                                            DistributionChartType.to_dict(),
                                                            value=DistributionChartType.HISTOGRAM,
                                                            id="portfolio-rolling-returns-distribution-chart-type-selection",
                                                        ),
                                                    ],
                                                    id="portfolio-rolling-returns-distribution-chart-type-selection-container",
                                                ),
                                            ],
                                            id="portfolio-rolling-return-selection-container",
                                        ),
                                        dbc.Label(
                                            "Baseline",
                                            html_for="portfolio-baseline-security-selection",
                                        ),
                                        dbc.Select(
                                            {
                                                "None": "None",
                                            },
                                            value="None",
                                            id="portfolio-baseline-security-selection",
                                        ),
                                    ],
                                    id="portfolio-return-selection",
                                ),
                            ],
                            className="sidebar",
                        ),
                        html.Div(
                            [
                                dcc.Graph(
                                    responsive=True,
                                    id="portfolio-graph",
                                    config={"toImageButtonOptions": {"scale": 4}},
                                ),
                                dcc.Store(
                                    id="portfolio-graph-last-layout-state-store",
                                    storage_type="memory",
                                ),
                            ],
                            className="graph-container",
                        ),
                    ],
                ),
            ),
            dbc.Tab(
                label="Accumulation Strategy Backtester",
                children=html.Div(
                    [
                        html.Div(
                            [
                                dbc.Label(
                                    "Portfolio",
                                    html_for="backtest-accumulation-strategy-portfolio",
                                ),
                                html.Div(
                                    [
                                        dbc.Select(
                                            {},
                                            id="backtest-accumulation-strategy-portfolio",
                                            style={"width": 0, "flexGrow": 1},
                                        ),
                                    ],
                                    style={"display": "flex"},
                                ),
                                dbc.Label(
                                    "Currency",
                                    html_for="backtest-accumulation-strategy-currency-selection",
                                ),
                                dbc.Select(
                                    Currency.to_dict(),
                                    value=Currency.SGD,
                                    id="backtest-accumulation-strategy-currency-selection",
                                ),
                                dbc.Label(
                                    "Initial Portfolio Value",
                                    html_for="backtest-accumulation-investment-amount-input",
                                ),
                                dbc.Input(
                                    id="backtest-accumulation-investment-amount-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Monthly Investment Amount",
                                    html_for="backtest-accumulation-monthly-investment-input",
                                ),
                                dbc.Input(
                                    id="backtest-accumulation-monthly-investment-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Switch(
                                    "backtest-accumulation-monthly-investment-inflation-adjustment-switch",
                                    value=False,
                                    label="Adjust for Inflation",
                                    style={"marginTop": "0"},
                                ),
                                dbc.Label(
                                    "DCA Duration (Months)",
                                    html_for="backtest-accumulation-dca-duration-input",
                                ),
                                dbc.Input(
                                    id="backtest-accumulation-dca-duration-input",
                                    type="number",
                                    min=0,
                                    step=1,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "DCA Interval (Months)",
                                    html_for="backtest-accumulation-dca-interval-input",
                                ),
                                dbc.Input(
                                    id="backtest-accumulation-dca-interval-input",
                                    type="number",
                                    min=1,
                                    step=1,
                                    value=1,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Coast Duration (Months)",
                                    html_for="backtest-accumulation-coast-duration-input",
                                ),
                                dbc.Input(
                                    id="backtest-accumulation-coast-duration-input",
                                    type="number",
                                    min=0,
                                    step=1,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Variable Transaction Fees (%)",
                                    html_for="backtest-accumulation-variable-transaction-fees-input",
                                ),
                                dbc.Input(
                                    id="backtest-accumulation-variable-transaction-fees-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Fixed Transaction Fees ($)",
                                    html_for="backtest-accumulation-fixed-transaction-fees-input",
                                ),
                                dbc.Input(
                                    id="backtest-accumulation-fixed-transaction-fees-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Annualised Holding Fees (% p.a.)",
                                    html_for="backtest-accumulation-annualised-holding-fees-input",
                                ),
                                dbc.Input(
                                    id="backtest-accumulation-annualised-holding-fees-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Switch(
                                    "backtest-accumulation-portfolio-value-inflation-adjustment-switch",
                                    value=False,
                                    label="Adjust Portfolio Value for Inflation",
                                ),
                                html.P(),
                                dbc.Button(
                                    "Add Strategy",
                                    id="backtest-accumulation-add-strategy-button",
                                ),
                                html.P(),
                                dbc.Label(
                                    "Strategies",
                                    html_for="backtest-accumulation-strategies",
                                ),
                                html.Div(
                                    [
                                        dcc.Dropdown(
                                            {},
                                            multi=True,
                                            searchable=False,
                                            id="backtest-accumulation-strategies",
                                            optionHeight=200,
                                            style={"width": 0, "flexGrow": 1},
                                        )
                                    ],
                                    style={"display": "flex"},
                                ),
                                dbc.Switch(
                                    "backtest-accumulation-index-by-start-date",
                                    value=False,
                                    label="Index by Start Date",
                                ),
                                dbc.Label(
                                    "Value",
                                    html_for="backtest-accumulation-y-var-selection",
                                ),
                                dbc.Select(
                                    BacktestYVar.to_dict(),
                                    value=BacktestYVar.ENDING_VALUES,
                                    id="backtest-accumulation-y-var-selection",
                                ),
                                html.Div(
                                    [
                                        dbc.Label(
                                            "Drawdown Type",
                                            html_for="backtest-accumulation-drawdown-type-selection",
                                        ),
                                        dbc.Select(
                                            DrawdownType.to_dict(),
                                            value=DrawdownType.PERCENT,
                                            id="backtest-accumulation-drawdown-type-selection",
                                        ),
                                    ],
                                    id="backtest-accumulation-drawdown-type-container",
                                    style={"display": "none"},
                                ),
                            ],
                            className="sidebar",
                        ),
                        html.Div(
                            [
                                dcc.Graph(
                                    responsive=True,
                                    figure={
                                        "data": [],
                                        "layout": {
                                            "autosize": True,
                                            "title": "Strategy Performance",
                                        },
                                    },
                                    id="backtest-accumulation-strategy-graph",
                                    config={"toImageButtonOptions": {"scale": 4}},
                                ),
                                dcc.Store(
                                    id="backtest-accumulation-strategy-clicked-date-store"
                                ),
                                dbc.Button(
                                    "Click a data point to view portfolio growth",
                                    id="backtest-accumulation-strategy-show-details-button",
                                    disabled=True,
                                    style={"marginTop": "10px", "borderRadius": "0"},
                                ),
                            ],
                            className="graph-container",
                        ),
                        dbc.Modal(
                            [
                                dbc.ModalHeader("Portfolio Growth"),
                                dbc.ModalBody(
                                    dcc.Graph(
                                        id="backtest-accumulation-strategy-modal-graph",
                                        style={"height": "100%"},
                                        config={"toImageButtonOptions": {"scale": 4}},
                                    )
                                ),
                            ],
                            id="backtest-accumulation-strategy-modal",
                            fullscreen=True,
                            is_open=False,
                        ),
                    ],
                ),
            ),
            dbc.Tab(
                label="Withdrawal Strategy Backtester",
                children=html.Div(
                    [
                        html.Div(
                            [
                                dbc.Label(
                                    "Portfolio",
                                    html_for="backtest-withdrawal-strategy-portfolio",
                                ),
                                html.Div(
                                    [
                                        dbc.Select(
                                            {},
                                            id="backtest-withdrawal-strategy-portfolio",
                                            style={"width": 0, "flexGrow": 1},
                                        ),
                                    ],
                                    style={"display": "flex"},
                                ),
                                dbc.Label(
                                    "Currency",
                                    html_for="backtest-withdrawal-strategy-currency-selection",
                                ),
                                dbc.Select(
                                    Currency.to_dict(),
                                    value=Currency.SGD,
                                    id="backtest-withdrawal-strategy-currency-selection",
                                ),
                                dbc.Label(
                                    "Initial Capital",
                                    html_for="backtest-withdrawal-initial-capital-input",
                                ),
                                dbc.Input(
                                    id="backtest-withdrawal-initial-capital-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Coast Duration (Months)",
                                    html_for="backtest-withdrawal-coast-duration-input",
                                ),
                                dbc.Input(
                                    id="backtest-withdrawal-coast-duration-input",
                                    type="number",
                                    step=1,
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Monthly Withdrawal Amount",
                                    html_for="backtest-withdrawal-monthly-amount-input",
                                ),
                                dbc.Input(
                                    id="backtest-withdrawal-monthly-amount-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Switch(
                                    "backtest-withdrawal-monthly-inflation-adjustment-switch",
                                    value=False,
                                    label="Adjust for Inflation",
                                    style={"marginTop": "0"},
                                ),
                                dbc.Label(
                                    "Withdrawal Duration (Months)",
                                    html_for="backtest-withdrawal-duration-input",
                                ),
                                dbc.Input(
                                    id="backtest-withdrawal-duration-input",
                                    type="number",
                                    min=0,
                                    step=1,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Withdrawal Interval (Months)",
                                    html_for="backtest-withdrawal-interval-input",
                                ),
                                dbc.Input(
                                    id="backtest-withdrawal-interval-input",
                                    type="number",
                                    min=1,
                                    step=1,
                                    value=1,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Variable Transaction Fees (%)",
                                    html_for="backtest-withdrawal-variable-transaction-fees-input",
                                ),
                                dbc.Input(
                                    id="backtest-withdrawal-variable-transaction-fees-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Fixed Transaction Fees ($)",
                                    html_for="backtest-withdrawal-fixed-transaction-fees-input",
                                ),
                                dbc.Input(
                                    id="backtest-withdrawal-fixed-transaction-fees-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Annualised Holding Fees (% p.a.)",
                                    html_for="backtest-withdrawal-annualised-holding-fees-input",
                                ),
                                dbc.Input(
                                    id="backtest-withdrawal-annualised-holding-fees-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Switch(
                                    "backtest-withdrawal-portfolio-value-inflation-adjustment-switch",
                                    value=False,
                                    label="Adjust Portfolio Value for Inflation",
                                    style={"marginTop": "0"},
                                ),
                                html.P(),
                                dbc.Button(
                                    "Add Strategy",
                                    id="backtest-withdrawal-add-strategy-button",
                                ),
                                html.P(),
                                dbc.Label(
                                    "Strategies",
                                    html_for="backtest-withdrawal-strategies",
                                ),
                                html.Div(
                                    [
                                        dcc.Dropdown(
                                            {},
                                            multi=True,
                                            searchable=False,
                                            id="backtest-withdrawal-strategies",
                                            optionHeight=150,
                                            style={"width": 0, "flexGrow": 1},
                                        )
                                    ],
                                    style={"display": "flex"},
                                ),
                                dbc.Switch(
                                    id="backtest-withdrawal-index-by-start-date",
                                    value=False,
                                    label="Index by Start Date",
                                ),
                                dbc.Label(
                                    "Value",
                                    html_for="backtest-withdrawal-y-var-selection",
                                ),
                                dbc.Select(
                                    BacktestYVar.to_dict(),
                                    value=BacktestYVar.ENDING_VALUES,
                                    id="backtest-withdrawal-y-var-selection",
                                ),
                                html.Div(
                                    [
                                        dbc.Label(
                                            "Drawdown Type",
                                            html_for="backtest-withdrawal-drawdown-type-selection",
                                        ),
                                        dbc.Select(
                                            DrawdownType.to_dict(),
                                            value=DrawdownType.PERCENT,
                                            id="backtest-withdrawal-drawdown-type-selection",
                                        ),
                                    ],
                                    id="backtest-withdrawal-drawdown-type-container",
                                    style={"display": "none"},
                                ),
                            ],
                            className="sidebar",
                        ),
                        html.Div(
                            [
                                dcc.Graph(
                                    responsive=True,
                                    figure={
                                        "data": [],
                                        "layout": {
                                            "autosize": True,
                                            "title": "Strategy Performance",
                                        },
                                    },
                                    id="backtest-withdrawal-strategy-graph",
                                    config={"toImageButtonOptions": {"scale": 4}},
                                ),
                                dcc.Store(
                                    id="backtest-withdrawal-strategy-clicked-date-store"
                                ),
                                dbc.Button(
                                    "Click a data point to view details",
                                    id="backtest-withdrawal-strategy-show-details-button",
                                    disabled=True,
                                    style={"marginTop": "10px", "borderRadius": "0"},
                                ),
                            ],
                            className="graph-container",
                        ),
                        dbc.Modal(
                            [
                                dbc.ModalHeader("Portfolio Value"),
                                dbc.ModalBody(
                                    dcc.Graph(
                                        id="backtest-withdrawal-strategy-modal-graph",
                                        style={"height": "100%"},
                                        config={"toImageButtonOptions": {"scale": 4}},
                                    )
                                ),
                            ],
                            id="backtest-withdrawal-strategy-modal",
                            fullscreen=True,
                            is_open=False,
                        ),
                    ],
                ),
            ),
            dbc.Tab(
                label="Accumulation Bootstrap",
                children=html.Div(
                    [
                        html.Div(
                            [
                                dbc.Label(
                                    "Portfolio",
                                    html_for="bootstrap-accumulation-strategy-portfolio",
                                ),
                                html.Div(
                                    [
                                        dbc.Select(
                                            {},
                                            id="bootstrap-accumulation-strategy-portfolio",
                                            style={"width": 0, "flexGrow": 1},
                                        ),
                                    ],
                                    style={"display": "flex"},
                                ),
                                dbc.Label(
                                    "Currency",
                                    html_for="bootstrap-accumulation-strategy-currency-selection",
                                ),
                                dbc.Select(
                                    Currency.to_dict(),
                                    value=Currency.SGD,
                                    id="bootstrap-accumulation-strategy-currency-selection",
                                ),
                                dbc.Label(
                                    "Initial Portfolio Value",
                                    html_for="bootstrap-accumulation-investment-amount-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-accumulation-investment-amount-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Monthly Investment Amount",
                                    html_for="bootstrap-accumulation-monthly-investment-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-accumulation-monthly-investment-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Switch(
                                    "bootstrap-accumulation-monthly-investment-inflation-adjustment-switch",
                                    value=False,
                                    label="Adjust for Inflation",
                                    style={"marginTop": "0"},
                                ),
                                dbc.Label(
                                    "DCA Duration (Months)",
                                    html_for="bootstrap-accumulation-dca-duration-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-accumulation-dca-duration-input",
                                    type="number",
                                    min=0,
                                    step=1,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "DCA Interval (Months)",
                                    html_for="bootstrap-accumulation-dca-interval-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-accumulation-dca-interval-input",
                                    type="number",
                                    min=1,
                                    step=1,
                                    value=1,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Coast Duration (Months)",
                                    html_for="bootstrap-accumulation-coast-duration-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-accumulation-coast-duration-input",
                                    type="number",
                                    min=0,
                                    step=1,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Variable Transaction Fees (%)",
                                    html_for="bootstrap-accumulation-variable-transaction-fees-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-accumulation-variable-transaction-fees-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Fixed Transaction Fees ($)",
                                    html_for="bootstrap-accumulation-fixed-transaction-fees-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-accumulation-fixed-transaction-fees-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Annualised Holding Fees (% p.a.)",
                                    html_for="bootstrap-accumulation-annualised-holding-fees-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-accumulation-annualised-holding-fees-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Switch(
                                    "bootstrap-accumulation-portfolio-value-inflation-adjustment-switch",
                                    value=False,
                                    label="Adjust Portfolio Value for Inflation",
                                ),
                                dbc.Label(
                                    "Num. Bootstrap Samples",
                                    html_for="bootstrap-accumulation-num-samples-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-accumulation-num-samples-input",
                                    type="number",
                                    min=100,
                                    value=1000,
                                    step=1,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Avg. Block Length (Months)",
                                    html_for="bootstrap-accumulation-avg-block-length-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-accumulation-avg-block-length-input",
                                    type="number",
                                    min=2,
                                    value=120,
                                    required=True,
                                ),
                                html.P(),
                                dbc.Button(
                                    "Add Strategy",
                                    id="bootstrap-accumulation-add-strategy-button",
                                ),
                                html.P(),
                                dbc.Label(
                                    "Strategies",
                                    html_for="bootstrap-accumulation-strategies",
                                ),
                                html.Div(
                                    [
                                        dcc.Dropdown(
                                            {},
                                            multi=True,
                                            searchable=False,
                                            id="bootstrap-accumulation-strategies",
                                            optionHeight=200,
                                            style={"width": 0, "flexGrow": 1},
                                        )
                                    ],
                                    style={"display": "flex"},
                                ),
                                dbc.Label(
                                    "Value",
                                    html_for="bootstrap-accumulation-y-var-selection",
                                ),
                                dbc.Select(
                                    BootstrapYVar.to_dict(),
                                    value=BootstrapYVar.PORTFOLIO_VALUES,
                                    id="bootstrap-accumulation-y-var-selection",
                                ),
                                dbc.Switch(
                                    "bootstrap-accumulation-log-scale-switch",
                                    value=False,
                                    label="Logarithmic Scale",
                                ),
                            ],
                            className="sidebar",
                        ),
                        html.Div(
                            [
                                dcc.Graph(
                                    responsive=True,
                                    figure={
                                        "data": [],
                                        "layout": {
                                            "autosize": True,
                                            "title": "Bootstrap Accumulation Strategy",
                                        },
                                    },
                                    id="bootstrap-accumulation-graph",
                                    config={"toImageButtonOptions": {"scale": 4}},
                                ),
                            ],
                            className="graph-container",
                        ),
                    ],
                ),
            ),
            dbc.Tab(
                label="Withdrawal Bootstrap",
                children=html.Div(
                    [
                        html.Div(
                            [
                                dbc.Label(
                                    "Portfolio",
                                    html_for="bootstrap-withdrawal-strategy-portfolio",
                                ),
                                html.Div(
                                    [
                                        dbc.Select(
                                            {},
                                            id="bootstrap-withdrawal-strategy-portfolio",
                                            style={"width": 0, "flexGrow": 1},
                                        ),
                                    ],
                                    style={"display": "flex"},
                                ),
                                dbc.Label(
                                    "Currency",
                                    html_for="bootstrap-withdrawal-strategy-currency-selection",
                                ),
                                dbc.Select(
                                    Currency.to_dict(),
                                    value=Currency.SGD,
                                    id="bootstrap-withdrawal-strategy-currency-selection",
                                ),
                                dbc.Label(
                                    "Initial Capital",
                                    html_for="bootstrap-withdrawal-initial-capital-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-withdrawal-initial-capital-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Coast Duration (Months)",
                                    html_for="bootstrap-withdrawal-coast-duration-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-withdrawal-coast-duration-input",
                                    type="number",
                                    step=1,
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Monthly Withdrawal Amount",
                                    html_for="bootstrap-withdrawal-monthly-amount-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-withdrawal-monthly-amount-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Switch(
                                    "bootstrap-withdrawal-monthly-inflation-adjustment-switch",
                                    value=False,
                                    label="Adjust for Inflation",
                                    style={"marginTop": "0"},
                                ),
                                dbc.Label(
                                    "Withdrawal Duration (Months)",
                                    html_for="bootstrap-withdrawal-duration-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-withdrawal-duration-input",
                                    type="number",
                                    min=0,
                                    step=1,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Withdrawal Interval (Months)",
                                    html_for="bootstrap-withdrawal-interval-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-withdrawal-interval-input",
                                    type="number",
                                    min=1,
                                    step=1,
                                    value=1,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Variable Transaction Fees (%)",
                                    html_for="bootstrap-withdrawal-variable-transaction-fees-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-withdrawal-variable-transaction-fees-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Fixed Transaction Fees ($)",
                                    html_for="bootstrap-withdrawal-fixed-transaction-fees-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-withdrawal-fixed-transaction-fees-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Annualised Holding Fees (% p.a.)",
                                    html_for="bootstrap-withdrawal-annualised-holding-fees-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-withdrawal-annualised-holding-fees-input",
                                    type="number",
                                    min=0,
                                    value=0,
                                    required=True,
                                ),
                                dbc.Switch(
                                    "bootstrap-withdrawal-portfolio-value-inflation-adjustment-switch",
                                    value=False,
                                    label="Adjust Portfolio Value for Inflation",
                                    style={"marginTop": "0"},
                                ),
                                dbc.Label(
                                    "Num. Bootstrap Samples",
                                    html_for="bootstrap-withdrawal-num-samples-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-withdrawal-num-samples-input",
                                    type="number",
                                    min=100,
                                    value=1000,
                                    step=1,
                                    required=True,
                                ),
                                dbc.Label(
                                    "Avg. Block Length (Months)",
                                    html_for="bootstrap-withdrawal-avg-block-length-input",
                                ),
                                dbc.Input(
                                    id="bootstrap-withdrawal-avg-block-length-input",
                                    type="number",
                                    min=2,
                                    value=120,
                                    required=True,
                                ),
                                html.P(),
                                dbc.Button(
                                    "Add Strategy",
                                    id="bootstrap-withdrawal-add-strategy-button",
                                ),
                                html.P(),
                                dbc.Label(
                                    "Strategies",
                                    html_for="bootstrap-withdrawal-strategies",
                                ),
                                html.Div(
                                    [
                                        dcc.Dropdown(
                                            {},
                                            multi=True,
                                            searchable=False,
                                            id="bootstrap-withdrawal-strategies",
                                            optionHeight=150,
                                            style={"width": 0, "flexGrow": 1},
                                        )
                                    ],
                                    style={"display": "flex"},
                                ),
                                dbc.Label(
                                    "Value",
                                    html_for="bootstrap-withdrawal-y-var-selection",
                                ),
                                dbc.Select(
                                    BootstrapYVar.to_dict(),
                                    value=BootstrapYVar.PORTFOLIO_VALUES,
                                    id="bootstrap-withdrawal-y-var-selection",
                                ),
                                dbc.Switch(
                                    "bootstrap-withdrawal-log-scale-switch",
                                    value=False,
                                    label="Logarithmic Scale",
                                ),
                            ],
                            className="sidebar",
                        ),
                        html.Div(
                            [
                                dcc.Graph(
                                    responsive=True,
                                    figure={
                                        "data": [],
                                        "layout": {
                                            "autosize": True,
                                            "title": "Bootstrap Withdrawal Strategy",
                                        },
                                    },
                                    id="bootstrap-withdrawal-graph",
                                    config={"toImageButtonOptions": {"scale": 4}},
                                ),
                            ],
                            className="graph-container",
                        ),
                    ],
                ),
            ),
        ],
        style={
            "textWrap": "nowrap",
            "flexWrap": "nowrap",
            "overflowX": "scroll",
            "overflowY": "hidden",
        },
    ),
    style={"height": "100svh"},
)
