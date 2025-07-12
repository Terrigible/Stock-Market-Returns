import dash_bootstrap_components as dbc
from dash import dcc, html

app_layout = dbc.Tabs(
    [
        dbc.Tab(
            label="Returns Dashboard",
            children=html.Div(
                [
                    html.Div(
                        [
                            dbc.Label("Security Type"),
                            dbc.Select(
                                [
                                    "Index",
                                    "Stock/ETF",
                                    "Preset Fund",
                                    "Custom Fund/Index",
                                ],
                                value="Index",
                                id="security-type-selection",
                            ),
                            html.Div(
                                [
                                    dbc.Label("Index Provider"),
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
                                            dbc.Label("Index Type"),
                                            dbc.Select(
                                                ["Regional", "Country"],
                                                value="Regional",
                                                id="msci-index-type-selection",
                                            ),
                                            dbc.Label("Base Index"),
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
                                            dbc.Label("Size"),
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
                                            dbc.Label("Style"),
                                            dbc.Select(
                                                {
                                                    "BLEND": "None",
                                                    "GROWTH": "Growth",
                                                    "VALUE": "Value",
                                                },
                                                value="BLEND",
                                                id="msci-style-selection",
                                            ),
                                            dbc.Label("Tax Treatment"),
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
                                            dbc.Label("Index"),
                                            dbc.Select(
                                                {
                                                    "US-T": "US Treasuries",
                                                },
                                                value="US-T",
                                                id="fred-index-selection",
                                            ),
                                            html.Div(
                                                [
                                                    dbc.Label("Duration"),
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
                                            dbc.Label("Index"),
                                            dbc.Select(
                                                {
                                                    "SGS": "SGS",
                                                },
                                                value="SGS",
                                                id="mas-index-selection",
                                            ),
                                            html.Div(
                                                [
                                                    dbc.Label("Duration"),
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
                                            dbc.Label("Index"),
                                            dbc.Select(
                                                {
                                                    "STI": "STI",
                                                    "SPX": "S&P 500",
                                                    "SHILLER_SPX": "Shiller S&P 500",
                                                    "AWORLDS": "FTSE All-World",
                                                    "SREIT": "iEdge S-REIT Leaders",
                                                },
                                                value="STI",
                                                id="others-index-selection",
                                            ),
                                            html.Div(
                                                [
                                                    dbc.Label("Tax Treatment"),
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
                                    dbc.Label("Stock/ETF (Yahoo Finance Ticker)"),
                                    html.Br(),
                                    dbc.Input(id="stock-etf-input", type="text"),
                                    dbc.Label("Tax Treatment"),
                                    dbc.Select(
                                        ["Gross", "Net"],
                                        value="Gross",
                                        id="stock-etf-tax-treatment-selection",
                                    ),
                                    html.P(),
                                    dbc.Button(
                                        "Add Stock/ETF", id="add-stock-etf-button"
                                    ),
                                    html.P(),
                                ],
                                id="stock-etf-selection-container",
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
                                    dbc.Label("Fund Company"),
                                    dbc.Select(
                                        [
                                            "Great Eastern",
                                            "GMO",
                                            "Fundsmith",
                                            "Dimensional",
                                        ],
                                        value="Great Eastern",
                                        id="fund-company-selection",
                                    ),
                                    dbc.Label("Fund"),
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
                                    dbc.Label("Fund/Index (FT Ticker)"),
                                    html.Br(),
                                    dbc.Input(id="fund-index-input", type="text"),
                                    html.P(),
                                    dbc.Button(
                                        "Add Fund/Index", id="add-fund-index-button"
                                    ),
                                    html.P(),
                                ],
                                id="fund-index-selection-container",
                            ),
                            dcc.Store(
                                id="ft-api-key-store",
                                storage_type="memory",
                                data=None,
                            ),
                            dcc.Store(
                                id="ft-invalid-securities-store",
                                storage_type="memory",
                                data=[],
                            ),
                            dcc.Store(id="toast-store", storage_type="memory", data=""),
                            dbc.Toast(
                                "",
                                id="toast",
                                header="Info",
                                is_open=False,
                                dismissable=True,
                                duration=2000,
                                color="info",
                            ),
                            html.P(),
                            dbc.Label("Selected Securities"),
                            dcc.Dropdown(
                                {},
                                multi=True,
                                searchable=False,
                                id="selected-securities",
                            ),
                            dcc.Store(
                                id="securities-colourmap-store",
                                storage_type="memory",
                                data={},
                            ),
                            dbc.Label("Interval"),
                            dbc.Select(
                                ["Monthly", "Daily"],
                                value="Monthly",
                                id="interval-selection",
                            ),
                            dbc.Label("Currency"),
                            dbc.Select(
                                [
                                    "SGD",
                                    "USD",
                                ],
                                value="USD",
                                id="currency-selection",
                            ),
                            dbc.Label("Adjust for Inflation"),
                            dbc.Select(
                                [
                                    "No",
                                    "Yes",
                                ],
                                value="No",
                                id="inflation-adjustment-selection",
                            ),
                            dbc.Label("Value"),
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
                            dbc.Switch(
                                "log-scale-switch",
                                value=False,
                                label="Logarithmic Scale",
                            ),
                            dbc.Switch(
                                "percent-scale-switch", value=False, label="% Scale"
                            ),
                            dbc.Switch(
                                "auto-scale-switch", value=False, label="Auto Scale"
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            dbc.Label("Return Interval"),
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
                                            dbc.Label("Return Duration"),
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
                                            dbc.Label("Return Type"),
                                            dbc.Select(
                                                {
                                                    "cumulative": "Cumulative",
                                                    "annualized": "Annualized",
                                                },
                                                value="cumulative",
                                                id="return-type-selection",
                                            ),
                                            dbc.Label("Chart Type"),
                                            dbc.Select(
                                                {
                                                    "timeseries": "Time Series",
                                                    "dist": "Distribution",
                                                },
                                                value="timeseries",
                                                id="chart-type-selection",
                                            ),
                                        ],
                                        id="rolling-return-selection-container",
                                    ),
                                    dbc.Label("Baseline"),
                                    dbc.Select(
                                        {
                                            "None": "None",
                                        },
                                        value="None",
                                        id="baseline-security-selection",
                                    ),
                                ],
                                id="return-selection",
                                style={"display": "block"},
                            ),
                        ],
                        className="dashboard-bootstrap",
                        style={
                            "width": "15%",
                            "padding": "1rem",
                            "flex": "1",
                            "overflow": "auto",
                        },
                    ),
                    dcc.Graph(
                        id="graph",
                        style={
                            "width": "85%",
                            "height": "100%",
                        },
                    ),
                    dcc.Store(id="graph-xaxis-relayout-store", storage_type="memory"),
                ],
                style={
                    "display": "flex",
                    "height": "95vh",
                    "boxSizing": "border-box",
                },
            ),
        ),
        dbc.Tab(
            label="Portfolio Constructor",
            children=html.Div(
                [
                    html.Div(
                        [
                            dbc.Label("Security"),
                            dbc.Select(
                                {},
                                id="portfolio-security-selection",
                            ),
                            dbc.Label("Weight (%)"),
                            dbc.Input(
                                id="security-weight",
                                type="number",
                                min=0,
                                max=100,
                            ),
                            html.P(),
                            dbc.Button("Add Security", id="add-security-button"),
                            html.P(),
                            dbc.Label("Portfolio Allocations"),
                            dcc.Dropdown(
                                {},
                                id="portfolio-allocations",
                                multi=True,
                            ),
                            html.P(
                                "Sum of Weights: ",
                                id="portfolio-weights-sum",
                            ),
                            html.P(),
                            dbc.Button("Add Portfolio", id="add-portfolio-button"),
                            html.P(),
                            dcc.Dropdown(
                                {},
                                id="portfolios",
                                multi=True,
                            ),
                            dbc.Label("Currency"),
                            dbc.Select(
                                [
                                    "SGD",
                                    "USD",
                                ],
                                value="USD",
                                id="portfolio-currency-selection",
                            ),
                            dbc.Label("Adjust for Inflation"),
                            dbc.Select(
                                [
                                    "No",
                                    "Yes",
                                ],
                                value="No",
                                id="portfolio-inflation-adjustment-selection",
                            ),
                            dbc.Label("Value"),
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
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            dbc.Label("Return Interval"),
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
                                            dbc.Label("Return Duration"),
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
                                            dbc.Label("Return Type"),
                                            dbc.Select(
                                                {
                                                    "cumulative": "Cumulative",
                                                    "annualized": "Annualized",
                                                },
                                                value="cumulative",
                                                id="portfolio-return-type-selection",
                                            ),
                                            dbc.Label("Chart Type"),
                                            dbc.Select(
                                                {
                                                    "timeseries": "Time Series",
                                                    "dist": "Distribution",
                                                },
                                                value="timeseries",
                                                id="portfolio-chart-type-selection",
                                            ),
                                        ],
                                        id="portfolio-rolling-return-selection-container",
                                    ),
                                    dbc.Label("Baseline"),
                                    dbc.Select(
                                        {
                                            "None": "None",
                                        },
                                        value="None",
                                        id="portfolio-baseline-security-selection",
                                    ),
                                ],
                                id="portfolio-return-selection",
                                style={"display": "block"},
                            ),
                        ],
                        style={
                            "width": "15%",
                            "padding": "1rem",
                            "flex": "1",
                            "overflow": "auto",
                        },
                    ),
                    dcc.Graph(
                        figure={
                            "data": [],
                            "layout": {
                                "title": "Portfolio Simulation",
                            },
                        },
                        id="portfolio-graph",
                        style={
                            "width": "85%",
                            "height": "100%",
                        },
                    ),
                    dcc.Store(
                        id="portfolio-graph-xaxis-relayout-store", storage_type="memory"
                    ),
                ],
                style={
                    "display": "flex",
                    "height": "95vh",
                    "boxSizing": "border-box",
                },
            ),
        ),
        dbc.Tab(
            label="Accumulation Strategy Tester",
            children=html.Div(
                [
                    html.Div(
                        [
                            dbc.Label("Portfolio"),
                            dbc.Select(
                                {},
                                id="accumulation-strategy-portfolio",
                            ),
                            dbc.Label("Currency"),
                            dbc.Select(
                                [
                                    "SGD",
                                    "USD",
                                ],
                                value="SGD",
                                id="accumulation-strategy-currency-selection",
                            ),
                            dbc.Label("Lump Sum / DCA"),
                            dbc.Select(
                                {"LS": "Lump Sum", "DCA": "DCA"},
                                value="LS",
                                id="accumulation-ls-dca-selection",
                            ),
                            dbc.Label(
                                "Total Investment Amount",
                                id="accumulation-investment-amount-label",
                            ),
                            dbc.Input(
                                id="accumulation-investment-amount-input",
                                type="number",
                                min=0.01,
                            ),
                            html.Div(
                                [
                                    dbc.Label("Monthly Investment Amount"),
                                    dbc.Input(
                                        id="accumulation-monthly-investment-input",
                                        type="number",
                                        min=0.01,
                                    ),
                                    dbc.Switch(
                                        "accumulation-monthly-investment-inflation-adjustment-switch",
                                        value=False,
                                        label="Adjust for Inflation",
                                        style={"marginTop": "0"},
                                    ),
                                ],
                                id="accumulation-dca-input-container",
                            ),
                            dbc.Label("Investment Horizon (Months)"),
                            dbc.Input(
                                id="accumulation-investment-horizon-input",
                                type="number",
                                min=1,
                                step=1,
                            ),
                            dbc.Label("DCA Length (Months)"),
                            dbc.Input(
                                id="accumulation-dca-length-input",
                                type="number",
                                min=1,
                                step=1,
                            ),
                            dbc.Label("DCA Interval (Months)"),
                            dbc.Input(
                                id="accumulation-dca-interval-input",
                                type="number",
                                min=1,
                                step=1,
                            ),
                            dbc.Label("Variable Transaction Fees (%)"),
                            dbc.Input(
                                id="accumulation-variable-transaction-fees-input",
                                type="number",
                                min=0,
                            ),
                            dbc.Label("Fixed Transaction Fees ($)"),
                            dbc.Input(
                                id="accumulation-fixed-transaction-fees-input",
                                type="number",
                                min=0,
                            ),
                            dbc.Label("Annualised Holding Fees (% p.a.)"),
                            dbc.Input(
                                id="accumulation-annualised-holding-fees-input",
                                type="number",
                                min=0,
                            ),
                            dbc.Switch(
                                "accumulation-ending-value-inflation-adjustment-switch",
                                value=False,
                                label="Adjust Ending Value for Inflation",
                            ),
                            html.P(),
                            dbc.Button(
                                "Add Strategy", id="add-accumulation-strategy-button"
                            ),
                            html.P(),
                            dbc.Label("Strategies"),
                            dcc.Dropdown(
                                {},
                                multi=True,
                                id="accumulation-strategies",
                                optionHeight=150,
                            ),
                        ],
                        style={
                            "width": "15%",
                            "padding": "1rem",
                            "flex": "1",
                            "overflow": "auto",
                        },
                    ),
                    dcc.Graph(
                        figure={
                            "data": [],
                            "layout": {
                                "title": "Strategy Performance",
                            },
                        },
                        id="accumulation-strategy-graph",
                        style={
                            "width": "85%",
                            "height": "100%",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "height": "95vh",
                    "boxSizing": "border-box",
                },
            ),
        ),
        dbc.Tab(
            label="Withdrawal Strategy Tester",
            children=html.Div(
                [
                    html.Div(
                        [
                            dbc.Label("Portfolio"),
                            dbc.Select(
                                {},
                                id="withdrawal-strategy-portfolio",
                            ),
                            dbc.Label("Currency"),
                            dbc.Select(
                                [
                                    "SGD",
                                    "USD",
                                ],
                                value="SGD",
                                id="withdrawal-strategy-currency-selection",
                            ),
                            dbc.Label("Initial Capital"),
                            dbc.Input(
                                id="withdrawal-initial-capital-input",
                                type="number",
                                min=0.01,
                            ),
                            dbc.Label("Monthly Withdrawal Amount"),
                            dbc.Input(
                                id="monthly-withdrawal-input",
                                type="number",
                                min=0.01,
                            ),
                            dbc.Switch(
                                "withdrawal-monthly-inflation-adjustment-switch",
                                value=False,
                                label="Adjust for Inflation",
                                style={"marginTop": "0"},
                            ),
                            dbc.Label("Withdrawal Horizon (Months)"),
                            dbc.Input(
                                id="withdrawal-horizon-input",
                                type="number",
                                min=1,
                                step=1,
                            ),
                            dbc.Label("Withdrawal Interval (Months)"),
                            dbc.Input(
                                id="withdrawal-interval-input",
                                type="number",
                                min=1,
                                step=1,
                            ),
                            dbc.Label("Variable Transaction Fees (%)"),
                            dbc.Input(
                                id="withdrawal-variable-transaction-fees-input",
                                type="number",
                                min=0,
                            ),
                            dbc.Label("Fixed Transaction Fees ($)"),
                            dbc.Input(
                                id="withdrawal-fixed-transaction-fees-input",
                                type="number",
                                min=0,
                            ),
                            dbc.Label("Annualised Holding Fees (% p.a.)"),
                            dbc.Input(
                                id="withdrawal-annualised-holding-fees-input",
                                type="number",
                                min=0,
                            ),
                            html.P(),
                            dbc.Button(
                                "Add Strategy", id="add-withdrawal-strategy-button"
                            ),
                            html.P(),
                            dbc.Label("Strategies"),
                            dcc.Dropdown(
                                {},
                                multi=True,
                                id="withdrawal-strategies",
                                optionHeight=150,
                            ),
                        ],
                        style={
                            "width": "15%",
                            "padding": "1rem",
                            "flex": "1",
                            "overflow": "auto",
                        },
                    ),
                    dcc.Graph(
                        figure={
                            "data": [],
                            "layout": {
                                "title": "Strategy Performance",
                            },
                        },
                        id="withdrawal-strategy-graph",
                        style={
                            "width": "85%",
                            "height": "100%",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "height": "95vh",
                    "boxSizing": "border-box",
                },
            ),
        ),
    ],
    style={"flexWrap": "nowrap", "overflow": "scroll"},
)
