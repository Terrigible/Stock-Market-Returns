import dash_bootstrap_components as dbc
from dash import dcc, html

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
                                    [
                                        "Index",
                                        "Preset Fund",
                                        "Yahoo Finance",
                                        "Financial Times",
                                    ],
                                    value="Index",
                                    id="security-type-selection",
                                ),
                                html.Div(
                                    [
                                        dbc.Label(
                                            "Index Provider",
                                            html_for="index-provider-selection",
                                        ),
                                        dbc.Select(
                                            {
                                                "MSCI": "MSCI",
                                                "FRED": "FRED",
                                                "MAS": "MAS",
                                                "Others": "Others",
                                            },
                                            value="MSCI",
                                            id="index-provider-selection",
                                        ),
                                        html.Div(
                                            [
                                                dbc.Label(
                                                    "Index Type",
                                                    html_for="msci-index-type-selection",
                                                ),
                                                dbc.Select(
                                                    ["Regional", "Country"],
                                                    value="Regional",
                                                    id="msci-index-type-selection",
                                                ),
                                                dbc.Label(
                                                    "Base Index",
                                                    html_for="msci-index-selection",
                                                ),
                                                dbc.Select(
                                                    {
                                                        "WORLD": "World",
                                                        "ACWI": "ACWI",
                                                        "EM (EMERGING MARKETS)": "Emerging Markets",
                                                        "WORLD ex USA": "World ex USA",
                                                        "KOKUSAI INDEX (WORLD ex JP)": "World ex Japan",
                                                        "EUROPE": "Europe",
                                                    },
                                                    value="WORLD",
                                                    id="msci-index-selection",
                                                ),
                                                dbc.Label(
                                                    "Size",
                                                    html_for="msci-size-selection",
                                                ),
                                                dbc.Select(
                                                    {
                                                        "STANDARD": "Standard",
                                                        "SMALL": "Small",
                                                        "SMID": "SMID",
                                                        "MID": "Mid",
                                                        "LARGE": "Large",
                                                        "IMI": "IMI",
                                                    },
                                                    value="STANDARD",
                                                    id="msci-size-selection",
                                                ),
                                                dbc.Label(
                                                    "Style",
                                                    html_for="msci-style-selection",
                                                ),
                                                dbc.Select(
                                                    {
                                                        "BLEND": "None",
                                                        "GROWTH": "Growth",
                                                        "VALUE": "Value",
                                                    },
                                                    value="BLEND",
                                                    id="msci-style-selection",
                                                ),
                                                dbc.Label(
                                                    "Tax Treatment",
                                                    html_for="msci-tax-treatment-selection",
                                                ),
                                                dbc.Select(
                                                    ["Gross", "Net"],
                                                    value="Gross",
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
                                                    {
                                                        "US-T": "US Treasuries",
                                                        "FFR": "Fed Funds Rate",
                                                    },
                                                    value="US-T",
                                                    id="fred-index-selection",
                                                ),
                                                html.Div(
                                                    [
                                                        dbc.Label(
                                                            "Duration",
                                                            html_for="us-treasury-duration-selection",
                                                        ),
                                                        dbc.Select(
                                                            {
                                                                "1MO": "1 Month",
                                                                "3MO": "3 Months",
                                                                "6MO": "6 Months",
                                                                "1": "1 Year",
                                                                "2": "2 Years",
                                                                "3": "3 Years",
                                                                "5": "5 Years",
                                                                "7": "7 Years",
                                                                "10": "10 Years",
                                                                "20": "20 Years",
                                                                "30": "30 Years",
                                                            },
                                                            value="1MO",
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
                                                    {
                                                        "SGS": "SGS",
                                                        "SORA": "SORA",
                                                    },
                                                    value="SGS",
                                                    id="mas-index-selection",
                                                ),
                                                html.Div(
                                                    [
                                                        dbc.Label(
                                                            "Duration",
                                                            html_for="sgs-duration-selection",
                                                        ),
                                                        dbc.Select(
                                                            {
                                                                "1": "1 Year",
                                                                "2": "2 Years",
                                                                "5": "5 Years",
                                                                "10": "10 Years",
                                                                "15": "15 Years",
                                                                "20": "20 Years",
                                                                "30": "30 Years",
                                                                "50": "50 Years",
                                                            },
                                                            value="1",
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
                                                    {
                                                        "SPX": "S&P 500",
                                                        "SHILLER_SPX": "Shiller S&P 500",
                                                        "SREIT": "iEdge S-REIT Leaders",
                                                    },
                                                    value="SPX",
                                                    id="others-index-selection",
                                                ),
                                                html.Div(
                                                    [
                                                        dbc.Label(
                                                            "Tax Treatment",
                                                            html_for="others-tax-treatment-selection",
                                                        ),
                                                        dbc.Select(
                                                            ["Gross", "Net"],
                                                            value="Gross",
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
                                            ["Gross", "Net"],
                                            value="Gross",
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
                                    id="cached-securities-store",
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
                                            [
                                                "GreatLink",
                                                "GMO",
                                                "Fundsmith",
                                                "Dimensional",
                                            ],
                                            value="GreatLink",
                                            id="fund-company-selection",
                                        ),
                                        dbc.Label("Fund", html_for="fund-selection"),
                                        dbc.Select(
                                            [],
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
                                    id="ft-api-key-store",
                                    storage_type="local",
                                    data=None,
                                ),
                                dcc.Store(
                                    id="ft-invalid-securities-store",
                                    storage_type="memory",
                                    data=[],
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
                                dcc.Store(
                                    id="securities-colourmap-store",
                                    storage_type="memory",
                                    data={},
                                ),
                                dbc.Label("Interval", html_for="interval-selection"),
                                dbc.Select(
                                    ["Monthly", "Daily"],
                                    value="Monthly",
                                    id="interval-selection",
                                ),
                                dbc.Label("Currency", html_for="currency-selection"),
                                dbc.Select(
                                    [
                                        "SGD",
                                        "USD",
                                    ],
                                    value="USD",
                                    id="currency-selection",
                                ),
                                dbc.Label(
                                    "Adjust for Inflation",
                                    html_for="inflation-adjustment-selection",
                                ),
                                dbc.Select(
                                    [
                                        "No",
                                        "Yes",
                                    ],
                                    value="No",
                                    id="inflation-adjustment-selection",
                                ),
                                dbc.Label("Value", html_for="y-var-selection"),
                                dbc.Select(
                                    {
                                        "price": "Price",
                                        "drawdown": "Drawdown",
                                        "rolling_returns": "Rolling Returns",
                                        "calendar_returns": "Calendar Returns",
                                    },
                                    value="price",
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
                                                    {
                                                        "1mo": "Monthly",
                                                        "3mo": "Quarterly",
                                                        "1y": "Annual",
                                                    },
                                                    value="1mo",
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
                                                    {
                                                        "1mo": "1 Month",
                                                        "3mo": "3 Months",
                                                        "6mo": "6 Months",
                                                        "1y": "1 Year",
                                                        "2y": "2 Years",
                                                        "3y": "3 Years",
                                                        "5y": "5 Years",
                                                        "10y": "10 Years",
                                                        "15y": "15 Years",
                                                        "20y": "20 Years",
                                                        "25y": "25 Years",
                                                        "30y": "30 Years",
                                                    },
                                                    value="1mo",
                                                    id="return-duration-selection",
                                                ),
                                                dbc.Label(
                                                    "Return Annualisation",
                                                    html_for="return-annualisation-selection",
                                                ),
                                                dbc.Select(
                                                    {
                                                        "cumulative": "Cumulative",
                                                        "annualised": "Annualised",
                                                    },
                                                    value="cumulative",
                                                    id="return-annualisation-selection",
                                                ),
                                                dbc.Label(
                                                    "Presentation",
                                                    html_for="rolling-returns-presentation-selection",
                                                ),
                                                dbc.Select(
                                                    {
                                                        "timeseries": "Time Series",
                                                        "dist": "Distribution",
                                                    },
                                                    value="timeseries",
                                                    id="rolling-returns-presentation-selection",
                                                ),
                                                html.Div(
                                                    [
                                                        dbc.Label(
                                                            "Chart Type",
                                                            html_for="rolling-returns-distribution-chart-type-selection",
                                                        ),
                                                        dbc.Select(
                                                            {
                                                                "hist": "Histogram",
                                                                "box": "Box Plot",
                                                            },
                                                            value="hist",
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
                                    [
                                        "SGD",
                                        "USD",
                                    ],
                                    value="USD",
                                    id="portfolio-currency-selection",
                                ),
                                dbc.Label(
                                    "Adjust for Inflation",
                                    html_for="portfolio-inflation-adjustment-selection",
                                ),
                                dbc.Select(
                                    [
                                        "No",
                                        "Yes",
                                    ],
                                    value="No",
                                    id="portfolio-inflation-adjustment-selection",
                                ),
                                dbc.Label(
                                    "Value", html_for="portfolio-y-var-selection"
                                ),
                                dbc.Select(
                                    {
                                        "price": "Price",
                                        "drawdown": "Drawdown",
                                        "rolling_returns": "Rolling Returns",
                                        "calendar_returns": "Calendar Returns",
                                    },
                                    value="price",
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
                                                    {
                                                        "1mo": "Monthly",
                                                        "3mo": "Quarterly",
                                                        "1y": "Annual",
                                                    },
                                                    value="1mo",
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
                                                    {
                                                        "1mo": "1 Month",
                                                        "3mo": "3 Months",
                                                        "6mo": "6 Months",
                                                        "1y": "1 Year",
                                                        "2y": "2 Years",
                                                        "3y": "3 Years",
                                                        "5y": "5 Years",
                                                        "10y": "10 Years",
                                                        "15y": "15 Years",
                                                        "20y": "20 Years",
                                                        "25y": "25 Years",
                                                        "30y": "30 Years",
                                                    },
                                                    value="1mo",
                                                    id="portfolio-return-duration-selection",
                                                ),
                                                dbc.Label(
                                                    "Return Annualisation",
                                                    html_for="portfolio-return-annualisation-selection",
                                                ),
                                                dbc.Select(
                                                    {
                                                        "cumulative": "Cumulative",
                                                        "annualised": "Annualised",
                                                    },
                                                    value="cumulative",
                                                    id="portfolio-return-annualisation-selection",
                                                ),
                                                dbc.Label(
                                                    "Presentation",
                                                    html_for="portfolio-rolling-returns-presentation-selection",
                                                ),
                                                dbc.Select(
                                                    {
                                                        "timeseries": "Time Series",
                                                        "dist": "Distribution",
                                                    },
                                                    value="timeseries",
                                                    id="portfolio-rolling-returns-presentation-selection",
                                                ),
                                                html.Div(
                                                    [
                                                        dbc.Label(
                                                            "Chart Type",
                                                            html_for="portfolio-rolling-returns-distribution-chart-type-selection",
                                                        ),
                                                        dbc.Select(
                                                            {
                                                                "hist": "Histogram",
                                                                "box": "Box Plot",
                                                            },
                                                            value="hist",
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
                                    [
                                        "SGD",
                                        "USD",
                                    ],
                                    value="SGD",
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
                                ),
                                dbc.Label(
                                    "Monthly Investment Amount",
                                    html_for="backtest-accumulation-monthly-investment-input",
                                ),
                                dbc.Input(
                                    id="backtest-accumulation-monthly-investment-input",
                                    type="number",
                                    min=0,
                                ),
                                dbc.Switch(
                                    "backtest-accumulation-monthly-investment-inflation-adjustment-switch",
                                    value=False,
                                    label="Adjust for Inflation",
                                    style={"marginTop": "0"},
                                ),
                                dbc.Label(
                                    "Investment Horizon (Months)",
                                    html_for="backtest-accumulation-investment-horizon-input",
                                ),
                                dbc.Input(
                                    id="backtest-accumulation-investment-horizon-input",
                                    type="number",
                                    min=1,
                                    step=1,
                                ),
                                dbc.Label(
                                    "DCA Length (Months)",
                                    html_for="backtest-accumulation-dca-length-input",
                                ),
                                dbc.Input(
                                    id="backtest-accumulation-dca-length-input",
                                    type="number",
                                    min=1,
                                    step=1,
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
                                ),
                                dbc.Label(
                                    "Variable Transaction Fees (%)",
                                    html_for="backtest-accumulation-variable-transaction-fees-input",
                                ),
                                dbc.Input(
                                    id="backtest-accumulation-variable-transaction-fees-input",
                                    type="number",
                                    min=0,
                                ),
                                dbc.Label(
                                    "Fixed Transaction Fees ($)",
                                    html_for="backtest-accumulation-fixed-transaction-fees-input",
                                ),
                                dbc.Input(
                                    id="backtest-accumulation-fixed-transaction-fees-input",
                                    type="number",
                                    min=0,
                                ),
                                dbc.Label(
                                    "Annualised Holding Fees (% p.a.)",
                                    html_for="backtest-accumulation-annualised-holding-fees-input",
                                ),
                                dbc.Input(
                                    id="backtest-accumulation-annualised-holding-fees-input",
                                    type="number",
                                    min=0,
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
                                    {
                                        "ending_values": "Ending Values",
                                        "max_drawdown": "Max Drawdown",
                                    },
                                    value="ending_values",
                                    id="backtest-accumulation-y-var-selection",
                                ),
                                html.Div(
                                    [
                                        dbc.Label(
                                            "Drawdown Type",
                                            html_for="backtest-accumulation-drawdown-type-selection",
                                        ),
                                        dbc.Select(
                                            {
                                                "percent": "Percent Drawdown",
                                                "dollar": "Dollar Drawdown",
                                            },
                                            value="percent",
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
                                    [
                                        "SGD",
                                        "USD",
                                    ],
                                    value="SGD",
                                    id="backtest-withdrawal-strategy-currency-selection",
                                ),
                                dbc.Label(
                                    "Initial Capital",
                                    html_for="backtest-withdrawal-initial-capital-input",
                                ),
                                dbc.Input(
                                    id="backtest-withdrawal-initial-capital-input",
                                    type="number",
                                    min=0.01,
                                ),
                                dbc.Label(
                                    "Monthly Withdrawal Amount",
                                    html_for="backtest-withdrawal-monthly-amount-input",
                                ),
                                dbc.Input(
                                    id="backtest-withdrawal-monthly-amount-input",
                                    type="number",
                                    min=0.01,
                                ),
                                dbc.Switch(
                                    "backtest-withdrawal-monthly-inflation-adjustment-switch",
                                    value=False,
                                    label="Adjust for Inflation",
                                    style={"marginTop": "0"},
                                ),
                                dbc.Label(
                                    "Withdrawal Horizon (Months)",
                                    html_for="backtest-withdrawal-horizon-input",
                                ),
                                dbc.Input(
                                    id="backtest-withdrawal-horizon-input",
                                    type="number",
                                    min=1,
                                    step=1,
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
                                ),
                                dbc.Label(
                                    "Variable Transaction Fees (%)",
                                    html_for="backtest-withdrawal-variable-transaction-fees-input",
                                ),
                                dbc.Input(
                                    id="backtest-withdrawal-variable-transaction-fees-input",
                                    type="number",
                                    min=0,
                                ),
                                dbc.Label(
                                    "Fixed Transaction Fees ($)",
                                    html_for="backtest-withdrawal-fixed-transaction-fees-input",
                                ),
                                dbc.Input(
                                    id="backtest-withdrawal-fixed-transaction-fees-input",
                                    type="number",
                                    min=0,
                                ),
                                dbc.Label(
                                    "Annualised Holding Fees (% p.a.)",
                                    html_for="backtest-withdrawal-annualised-holding-fees-input",
                                ),
                                dbc.Input(
                                    id="backtest-withdrawal-annualised-holding-fees-input",
                                    type="number",
                                    min=0,
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
                                    {
                                        "ending_values": "Ending Values",
                                        "max_drawdown": "Max Drawdown",
                                    },
                                    value="ending_values",
                                    id="backtest-withdrawal-y-var-selection",
                                ),
                                html.Div(
                                    [
                                        dbc.Label(
                                            "Drawdown Type",
                                            html_for="backtest-withdrawal-drawdown-type-selection",
                                        ),
                                        dbc.Select(
                                            {
                                                "percent": "Percent Drawdown",
                                                "dollar": "Dollar Drawdown",
                                            },
                                            value="percent",
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
