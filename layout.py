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
                            html.Label("Security Type"),
                            dbc.Select(
                                [
                                    "Index",
                                    "Stock/ETF",
                                    "Fund",
                                ],
                                value="Index",
                                id="security-type-selection",
                            ),
                            html.Div(
                                [
                                    html.Label("Index Provider"),
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
                                            html.Label("Index"),
                                            dbc.Select(
                                                {
                                                    "WORLD": "World",
                                                    "ACWI": "ACWI",
                                                    "SINGAPORE": "Singapore",
                                                    "EM (EMERGING MARKETS)": "Emerging Markets",
                                                    "WORLD ex USA": "World ex USA",
                                                    "USA": "USA",
                                                    "KOKUSAI INDEX (WORLD ex JP)": "World ex Japan",
                                                    "JAPAN": "Japan",
                                                },
                                                value="WORLD",
                                                id="msci-index-selection",
                                            ),
                                            html.Label("Size"),
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
                                            html.Label("Style"),
                                            dbc.Select(
                                                {
                                                    "BLEND": "None",
                                                    "GROWTH": "Growth",
                                                    "VALUE": "Value",
                                                },
                                                value="BLEND",
                                                id="msci-style-selection",
                                            ),
                                            html.Label("Tax Treatment"),
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
                                            html.Label("Index"),
                                            dbc.Select(
                                                {
                                                    "US-T": "US Treasuries",
                                                },
                                                value="US-T",
                                                id="fred-index-selection",
                                            ),
                                            html.Div(
                                                [
                                                    html.Label("Duration"),
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
                                            html.Label("Index"),
                                            dbc.Select(
                                                {
                                                    "SGS": "SGS",
                                                },
                                                value="SGS",
                                                id="mas-index-selection",
                                            ),
                                            html.Div(
                                                [
                                                    html.Label("Duration"),
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
                                            html.Label("Index"),
                                            dbc.Select(
                                                {
                                                    "STI": "STI",
                                                    "SPX": "S&P 500",
                                                    "SHILLER_SPX": "Shiller S&P 500",
                                                },
                                                value="STI",
                                                id="others-index-selection",
                                            ),
                                            html.Div(
                                                [
                                                    html.Label("Tax Treatment"),
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
                                    html.Button("Add Index", id="add-index-button"),
                                ],
                                id="index-selection-container",
                            ),
                            html.Div(
                                [
                                    html.P(),
                                    html.Label("Stock/ETF (Yahoo Finance Ticker)"),
                                    html.Br(),
                                    dcc.Input(id="stock-etf-input", type="text"),
                                    html.Label("Tax Treatment"),
                                    dbc.Select(
                                        ["Gross", "Net"],
                                        value="Gross",
                                        id="stock-etf-tax-treatment-selection",
                                    ),
                                    html.P(),
                                    html.Button(
                                        "Add Stock/ETF", id="add-stock-etf-button"
                                    ),
                                ],
                                id="stock-etf-selection-container",
                            ),
                            dcc.Store(
                                id="yf-securities-store", storage_type="memory", data={}
                            ),
                            html.Div(
                                [
                                    html.Label("Fund Company"),
                                    dbc.Select(
                                        [
                                            "Great Eastern",
                                            "GMO",
                                            "Fundsmith",
                                        ],
                                        value="Great Eastern",
                                        id="fund-company-selection",
                                    ),
                                    html.Label("Fund"),
                                    dbc.Select(
                                        [],
                                        id="fund-selection",
                                    ),
                                    html.P(),
                                    html.Button("Add Fund", id="add-fund-button"),
                                ],
                                id="fund-selection-container",
                            ),
                            html.P(),
                            html.Label("Selected Securities"),
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
                            html.Label("Interval"),
                            dbc.Select(
                                ["Monthly", "Daily"],
                                value="Monthly",
                                id="interval-selection",
                            ),
                            html.Label("Currency"),
                            dbc.Select(
                                [
                                    "SGD",
                                    "USD",
                                ],
                                value="USD",
                                id="currency-selection",
                            ),
                            html.Label("Adjust for Inflation"),
                            dbc.Select(
                                [
                                    "No",
                                    "Yes",
                                ],
                                value="No",
                                id="inflation-adjustment-selection",
                            ),
                            html.Label("Value"),
                            dbc.Select(
                                {
                                    "price": "Price",
                                    "drawdown": "Drawdown",
                                    "rolling_returns": "Rolling Returns",
                                },
                                value="price",
                                id="y-var-selection",
                            ),
                            dcc.Checklist(
                                {"log": "Logarithmic Scale"},
                                value=[],
                                id="log-scale-selection",
                            ),
                            html.Div(
                                [
                                    html.Label("Return Duration"),
                                    dbc.Select(
                                        {
                                            "1m": "1 Month",
                                            "3m": "3 Months",
                                            "6m": "6 Months",
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
                                        value="1m",
                                        id="return-duration-selection",
                                    ),
                                    html.Label("Return Type"),
                                    dbc.Select(
                                        {
                                            "cumulative": "Cumulative",
                                            "annualized": "Annualized",
                                        },
                                        value="cumulative",
                                        id="return-type-selection",
                                    ),
                                    html.Label("Chart Type"),
                                    dbc.Select(
                                        {
                                            "line": "Line",
                                            "hist": "Histogram",
                                        },
                                        value="line",
                                        id="chart-type-selection",
                                    ),
                                    html.Label("Baseline"),
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
                            "padding": "1rem",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "height": "95vh",
                    "box-sizing": "border-box",
                    "justify-content": "space-between",
                    "padding": "1rem 1rem",
                },
            ),
        ),
        dbc.Tab(
            label="Portfolio Constructor",
            children=html.Div(
                [
                    html.Div(
                        [
                            html.Label("Security"),
                            dbc.Select(
                                {},
                                id="portfolio-security-selection",
                            ),
                            html.Label("Weight (%)"),
                            dcc.Input(
                                id="security-weight",
                                type="number",
                                min=0,
                                max=100,
                            ),
                            html.P(),
                            html.Button("Add Security", id="add-security-button"),
                            html.P(),
                            html.Label("Portfolio Allocations"),
                            dcc.Dropdown(
                                {},
                                id="portfolio-allocations",
                                multi=True,
                            ),
                            html.Button("Add Portfolio", id="add-portfolio-button"),
                            html.P(),
                            dcc.Dropdown(
                                {},
                                id="portfolios",
                                multi=True,
                            ),
                            html.Label("Currency"),
                            dbc.Select(
                                [
                                    "SGD",
                                    "USD",
                                ],
                                value="USD",
                                id="portfolio-currency-selection",
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
                            "padding": "1rem",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "height": "95vh",
                    "box-sizing": "border-box",
                    "justify-content": "space-between",
                    "padding": "1rem 1rem",
                },
            ),
        ),
        dbc.Tab(
            label="Strategy Tester",
            children=html.Div(
                [
                    html.Div(
                        [
                            html.Label("Portfolio"),
                            dcc.Dropdown(
                                {},
                                id="strategy-portfolio",
                            ),
                            html.Label("Currency"),
                            dbc.Select(
                                [
                                    "SGD",
                                    "USD",
                                ],
                                value="SGD",
                                id="strategy-currency-selection",
                            ),
                            html.Label("Lump Sum / DCA"),
                            dbc.Select(
                                {"LS": "Lump Sum", "DCA": "DCA"},
                                value="LS",
                                id="ls-dca-selection",
                            ),
                            html.Div(
                                [
                                    html.Label("Total Investment Amount"),
                                    dcc.Input(
                                        id="investment-amount-input",
                                        type="number",
                                    ),
                                ],
                                id="ls-input-container",
                            ),
                            html.Div(
                                [
                                    html.Label("Monthly Investment Amount"),
                                    dcc.Input(
                                        id="monthly-investment-input",
                                        type="number",
                                    ),
                                ],
                                id="dca-input-container",
                            ),
                            html.Label("Investment Horizon (Months)"),
                            dcc.Input(
                                id="investment-horizon-input",
                                type="number",
                            ),
                            html.Label("DCA Length (Months)"),
                            dcc.Input(
                                id="dca-length-input",
                                type="number",
                            ),
                            html.Label("DCA Interval (Months)"),
                            dcc.Input(
                                id="dca-interval-input",
                                type="number",
                            ),
                            html.Label("Variable Transaction Fees (%)"),
                            dcc.Input(
                                id="variable-transaction-fees-input",
                                type="number",
                            ),
                            html.Label("Fixed Transaction Fees ($)"),
                            dcc.Input(
                                id="fixed-transaction-fees-input",
                                type="number",
                            ),
                            html.Label("Annualised Holding Fees (% p.a.)"),
                            dcc.Input(
                                id="annualised-holding-fees-input",
                                type="number",
                            ),
                            html.Button("Add Strategy", id="add-strategy-button"),
                            html.P(),
                            html.Label("Strategies"),
                            dcc.Dropdown(
                                {},
                                multi=True,
                                id="strategies",
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
                        id="strategy-graph",
                        style={
                            "width": "85%",
                            "height": "100%",
                            "padding": "1rem",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "height": "95vh",
                    "box-sizing": "border-box",
                    "justify-content": "space-between",
                    "padding": "1rem 1rem",
                },
            ),
        ),
    ]
)
