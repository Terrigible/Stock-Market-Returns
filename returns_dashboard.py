from functools import cache
from glob import glob
from io import StringIO

import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State
from contextlib import redirect_stderr

from funcs.calcs_numba import (
    calculate_dca_return_with_fees_and_interest_vector,
    calculate_lumpsum_return_with_fees_and_interest_vector)
from funcs.loaders import (load_fed_funds_rate, load_fred_usd_fx,
                           load_mas_sgd_fx, load_sg_cpi,
                           load_sgd_interest_rates, load_us_cpi,
                           load_us_treasury_returns, load_usdsgd,
                           read_gmo_data, read_greatlink_data, read_msci_data,
                           read_shiller_sp500_data, read_spx_data,
                           read_sti_data)


@cache
def load_df(security: str, interval: str, currency: str, adjust_for_inflation: str, yf_security: str | None):
    source = security.split('|')[0]
    if source == 'MSCI':
        series = read_msci_data('data/{}/{}/{}/{}/*{} {}*.xls'.format(*security.split('|'), interval)).iloc[:, 0]
    elif source == 'US Treasury':
        series = load_us_treasury_returns()[security.split('|')[1]]
        if interval == 'Monthly':
            series = series.resample('BME').last()
    elif source == 'Others':
        if security.split('|')[1] == 'STI':
            series = read_sti_data().iloc[:, 0]
        elif security.split('|')[1] == 'SPX':
            series = read_spx_data(security.split('|')[2]).iloc[:, 0]
            if interval == 'Daily':
                series = series.resample('B').interpolate('linear')
        elif security.split('|')[1] == 'SHILLER_SPX':
            series = read_shiller_sp500_data(security.split('|')[2]).iloc[:, 0]
            if interval == 'Daily':
                series = series.resample('B').interpolate('linear')
        else:
            raise ValueError('Invalid index')
        if interval == 'Monthly':
            series = series.resample('BME').last()
    elif source == 'YF':
        ticker_currency = security.split('|')[2]
        series = pd.read_json(StringIO(yf_security), orient='index').iloc[:, 0]
        if ticker_currency != 'USD':
            if ticker_currency == 'SGD':
                series = series.div(load_usdsgd().resample('D').ffill().ffill().reindex(series.index))
            else:
                if ticker_currency == 'GBp':
                    series = series.div(100)
                    ticker_currency = 'GBP'
                if ticker_currency in load_fred_usd_fx().columns:
                    series = series.mul(load_fred_usd_fx()[ticker_currency].resample('D').ffill().ffill().reindex(series.index))
                elif ticker_currency in load_mas_sgd_fx().columns:
                    series = series.mul(load_mas_sgd_fx()[ticker_currency].resample('D').ffill().ffill().reindex(series.index))
                    series = series.div(load_usdsgd().resample('D').ffill().ffill().reindex(series.index))
        if interval == 'Monthly':
            series = series.resample('BME').last()
    elif source == 'Fund':
        fund_company, fund, currency = security.split('|')[1:]
        if fund_company == 'Great Eastern':
            series = read_greatlink_data(fund).iloc[:, 0]
        elif fund_company == 'GMO':
            series = read_gmo_data().iloc[:, 0]
        if interval == 'Monthly':
            series = series.resample('BME').last()
    else:
        raise ValueError('Invalid index')
    if currency == 'USD':
        if adjust_for_inflation == 'Yes':
            series = series.div(load_us_cpi().iloc[:, 0].resample('D').ffill().ffill().reindex(series.index))
    elif currency == 'SGD':
        series = series.mul(load_usdsgd().resample('D').ffill().ffill().reindex(series.index))
        if adjust_for_inflation == 'Yes':
            series = series.div(load_sg_cpi().iloc[:, 0].resample('D').ffill().ffill().reindex(series.index))
    return series


def transform_df(series: pd.Series, interval: str, y_var: str, return_duration: str, return_type: str) -> pd.Series:
    if y_var == 'price':
        return series
    if y_var == 'drawdown':
        return series.div(series.cummax()).sub(1)
    return_durations = {
        '1m': 1,
        '3m': 3,
        '6m': 6,
        '1y': 12,
        '2y': 24,
        '3y': 36,
        '5y': 60,
        '10y': 120,
        '15y': 180,
        '20y': 240,
        '25y': 300,
        '30y': 360,
    }
    if interval == 'Monthly':
        series = series.pct_change(return_durations[return_duration])
    elif interval == 'Daily':
        series = (
            series
            .div(
                series
                .reindex(
                    np.busday_offset(
                        (series.index - pd.offsets.DateOffset(months=return_durations[return_duration]))
                        .to_numpy()
                        .astype('datetime64[D]'),
                        0,
                        roll='backward'
                    )
                    .astype('datetime64[ns]')
                )
                .set_axis(series.index, axis=0)
            )
            .sub(1)
        )
    else:
        raise ValueError('Invalid interval')
    if return_type == 'annualized':
        series = series.add(1).pow(12 / round(return_durations[return_duration])).sub(1)
    return series.dropna()


app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])

server = app.server

app.layout = dbc.Tabs(
    [
        dbc.Tab(
            label='Returns Dashboard',
            children=html.Div(
                [
                    html.Div(
                        [
                            html.Label('Security Type'),
                            dbc.Select(
                                [
                                    'Index',
                                    'Stock/ETF',
                                    'Fund',
                                ],
                                value='Index',
                                id='security-type-selection'
                            ),
                            html.Div(
                                [
                                    html.Label('Index Provider'),
                                    dbc.Select(
                                        {
                                            'MSCI': 'MSCI',
                                            'US Treasury': 'US Treasury',
                                            'Others': 'Others'
                                        },
                                        value='MSCI',
                                        id='index-provider-selection'
                                    ),
                                    html.Div(
                                        [
                                            html.Label('Index'),
                                            dbc.Select(
                                                {
                                                    'WORLD': 'World',
                                                    'ACWI': 'ACWI',
                                                    'SINGAPORE': 'Singapore',
                                                    'EM (EMERGING MARKETS)': 'Emerging Markets',
                                                    'WORLD ex USA': 'World ex USA',
                                                    'USA': 'USA',
                                                    'KOKUSAI INDEX (WORLD ex JP)': 'World ex Japan',
                                                    'JAPAN': 'Japan',
                                                },
                                                value='WORLD',
                                                id='msci-index-selection'
                                            ),
                                            html.Label('Size'),
                                            dbc.Select(
                                                {
                                                    'STANDARD': 'Standard',
                                                    'SMALL': 'Small',
                                                    'SMID': 'SMID',
                                                    'MID': 'Mid',
                                                    'LARGE': 'Large',
                                                    'IMI': 'IMI',
                                                },
                                                value='STANDARD',
                                                id='msci-size-selection'
                                            ),
                                            html.Label('Style'),
                                            dbc.Select(
                                                {
                                                    'BLEND': 'None',
                                                    'GROWTH': 'Growth',
                                                    'VALUE': 'Value'
                                                },
                                                value='BLEND',
                                                id='msci-style-selection'
                                            ),
                                            html.Label('Tax Treatment'),
                                            dbc.Select(
                                                [
                                                    'Gross',
                                                    'Net'
                                                ],
                                                value='Gross',
                                                id='msci-tax-treatment-selection'
                                            ),
                                        ],
                                        id='msci-index-selection-container'
                                    ),
                                    html.Div(
                                        [
                                            html.Label('Duration'),
                                            dbc.Select(
                                                {
                                                    '1MO': '1 Month',
                                                    '3MO': '3 Months',
                                                    '6MO': '6 Months',
                                                    '1': '1 Year',
                                                    '2': '2 Years',
                                                    '3': '3 Years',
                                                    '5': '5 Years',
                                                    '7': '7 Years',
                                                    '10': '10 Years',
                                                    '20': '20 Years',
                                                    '30': '30 Years',
                                                },
                                                value='1MO',
                                                id='us-treasury-duration-selection',
                                            ),
                                        ],
                                        id='us-treasury-index-selection-container'
                                    ),
                                    html.Div(
                                        [
                                            html.Label('Index'),
                                            dbc.Select(
                                                {
                                                    'STI': 'STI',
                                                    'SPX': 'S&P 500',
                                                    'SHILLER_SPX': 'Shiller S&P 500',
                                                },
                                                value='STI',
                                                id='others-index-selection'
                                            ),
                                            html.Div(
                                                [
                                                    html.Label('Tax Treatment'),
                                                    dbc.Select(
                                                        [
                                                            'Gross',
                                                            'Net'
                                                        ],
                                                        value='Gross',
                                                        id='others-tax-treatment-selection'
                                                    ),
                                                ],
                                                id='others-tax-treatment-selection-container'
                                            ),
                                        ],
                                        id='others-index-selection-container'
                                    ),
                                    html.P(),
                                    html.Button(
                                        'Add Index',
                                        id='add-index-button'
                                    ),
                                ],
                                id='index-selection-container',
                            ),
                            html.Div(
                                [
                                    html.P(),
                                    html.Label('Stock/ETF (Yahoo Finance Ticker)'),
                                    html.Br(),
                                    dcc.Input(id='stock-etf-input', type='text'),
                                    html.Label('Tax Treatment'),
                                    dbc.Select(
                                        [
                                            'Gross',
                                            'Net'
                                        ],
                                        value='Gross',
                                        id='stock-etf-tax-treatment-selection'
                                    ),
                                    html.P(),
                                    html.Button(
                                        'Add Stock/ETF',
                                        id='add-stock-etf-button'
                                    ),
                                ],
                                id='stock-etf-selection-container',
                            ),
                            dcc.Store(id='yf-securities-store', storage_type='memory', data={}),
                            html.Div(
                                [
                                    html.Label('Fund Company'),
                                    dbc.Select(
                                        [
                                            'Great Eastern',
                                            'GMO',
                                        ],
                                        value='Great Eastern',
                                        id='fund-company-selection',
                                    ),
                                    html.Label('Fund'),
                                    dbc.Select(
                                        [],
                                        id='fund-selection',
                                    ),
                                    html.P(),
                                    html.Button(
                                        'Add Fund',
                                        id='add-fund-button'
                                    )
                                ],
                                id='fund-selection-container',
                            ),
                            html.P(),
                            html.Label('Selected Securities'),
                            dcc.Dropdown(
                                {},
                                multi=True,
                                searchable=False,
                                id='selected-securities',
                            ),
                            html.Label('Interval'),
                            dbc.Select(
                                [
                                    'Monthly',
                                    'Daily'
                                ],
                                value='Monthly',
                                id='interval-selection'
                            ),
                            html.Label('Currency'),
                            dbc.Select(
                                [
                                    'SGD',
                                    'USD',
                                ],
                                value='USD',
                                id='currency-selection'
                            ),
                            html.Label('Adjust for Inflation'),
                            dbc.Select(
                                [
                                    'No',
                                    'Yes',
                                ],
                                value='No',
                                id='inflation-adjustment-selection'
                            ),
                            html.Label('Value'),
                            dbc.Select(
                                {
                                    'price': 'Price',
                                    'drawdown': 'Drawdown',
                                    'rolling_returns': 'Rolling Returns'
                                },
                                value='price',
                                id='y-var-selection'
                            ),
                            dcc.Checklist(
                                {
                                    'log': 'Logarithmic Scale'
                                },
                                value=[],
                                id='log-scale-selection'
                            ),
                            html.Div(
                                [
                                    html.Label('Return Duration'),
                                    dbc.Select(
                                        {
                                            '1m': '1 Month',
                                            '3m': '3 Months',
                                            '6m': '6 Months',
                                            '1y': '1 Year',
                                            '2y': '2 Years',
                                            '3y': '3 Years',
                                            '5y': '5 Years',
                                            '10y': '10 Years',
                                            '15y': '15 Years',
                                            '20y': '20 Years',
                                            '25y': '25 Years',
                                            '30y': '30 Years',
                                        },
                                        value='1m',
                                        id='return-duration-selection'
                                    ),
                                    html.Label('Return Type'),
                                    dbc.Select(
                                        {
                                            'cumulative': 'Cumulative',
                                            'annualized': 'Annualized'
                                        },
                                        value='cumulative',
                                        id='return-type-selection'
                                    ),
                                    html.Label('Baseline'),
                                    dbc.Select(
                                        {
                                            'None': 'None',
                                        },
                                        value='None',
                                        id='baseline-security-selection'
                                    ),
                                ],
                                id='return-selection',
                                style={
                                    'display': 'block'
                                }
                            )
                        ],
                        style={
                            'width': '15%',
                            'padding': '1rem',
                            'flex': '1',
                            'overflow': 'auto',
                        }
                    ),
                    dcc.Graph(
                        id='graph',
                        style={
                            'width': '85%',
                            'height': '100%',
                            'padding': '1rem',
                        }
                    ),
                ],
                style={
                    'display': 'flex',
                    'height': '95vh',
                    'box-sizing': 'border-box',
                    'justify-content': 'space-between',
                    'padding': '1rem 1rem'
                }
            )
        ),
        dcc.Tab(
            label='Portfolio Simulator',
            children=html.Div(
                [
                    html.Div(
                        [
                            html.Label('Security'),
                            dcc.Dropdown(
                                {},
                                id='portfolio-security',
                            ),
                            html.Label('Currency'),
                            dbc.Select(
                                [
                                    'SGD',
                                    'USD',
                                ],
                                value='SGD',
                                id='portfolio-currency-selection'
                            ),
                            html.Label('Lump Sum / DCA'),
                            dbc.Select(
                                {
                                    'LS': 'Lump Sum',
                                    'DCA': 'DCA'
                                },
                                value='LS',
                                id='ls-dca-selection'
                            ),
                            html.Div(
                                [
                                    html.Label('Total Investment Amount'),
                                    dcc.Input(
                                        id='investment-amount-input',
                                        type='number',
                                    ),
                                ],
                                id='ls-input-container',
                            ),
                            html.Div(
                                [
                                    html.Label('Monthly Investment Amount'),
                                    dcc.Input(
                                        id='monthly-investment-input',
                                        type='number',
                                    ),
                                ],
                                id='dca-input-container',
                            ),
                            html.Label('Investment Horizon (Months)'),
                            dcc.Input(
                                id='investment-horizon-input',
                                type='number',
                            ),
                            html.Label('DCA Length (Months)'),
                            dcc.Input(
                                id='dca-length-input',
                                type='number',
                            ),
                            html.Label('DCA Interval (Months)'),
                            dcc.Input(
                                id='dca-interval-input',
                                type='number',
                            ),
                            html.Label('Variable Transaction Fees (%)'),
                            dcc.Input(
                                id='variable-transaction-fees-input',
                                type='number',
                            ),
                            html.Label('Fixed Transaction Fees ($)'),
                            dcc.Input(
                                id='fixed-transaction-fees-input',
                                type='number',
                            ),
                            html.Label('Annualised Holding Fees (% p.a.)'),
                            dcc.Input(
                                id='annualised-holding-fees-input',
                                type='number',
                            ),
                            html.Button(
                                'Add Portfolio',
                                id='add-portfolio-button'
                            ),
                            html.P(),
                            html.Label('Portfolios'),
                            dcc.Dropdown(
                                {},
                                multi=True,
                                id='portfolios',
                            ),
                        ],
                        style={
                            'width': '15%',
                            'padding': '1rem',
                            'flex': '1',
                            'overflow': 'auto',
                        }
                    ),
                    dcc.Graph(
                        figure={
                            'data': [],
                            'layout': {
                                'title': 'Portfolio Simulation',
                            }
                        },
                        id='portfolio-graph',
                        style={
                            'width': '85%',
                            'height': '100%',
                            'padding': '1rem',
                        }
                    ),
                ],
                style={
                    'display': 'flex',
                    'height': '95vh',
                    'box-sizing': 'border-box',
                    'justify-content': 'space-between',
                    'padding': '1rem 1rem'
                }
            )
        )
    ]
)


@app.callback(
    Output('index-selection-container', 'style'),
    Output('stock-etf-selection-container', 'style'),
    Output('fund-selection-container', 'style'),
    Input('security-type-selection', 'value'),
    Input('security-type-selection', 'options'),
)
def update_index_selection_visibility(security_type: str, security_type_options: list[str]):
    return tuple(
        {'display': 'block'} if security_type == security_type_option
        else {'display': 'none'}
        for security_type_option in security_type_options
    )


@app.callback(
    Output('msci-index-selection-container', 'style'),
    Output('us-treasury-index-selection-container', 'style'),
    Output('others-index-selection-container', 'style'),
    Input('index-provider-selection', 'value'),
)
def update_msci_index_selection_visibility(index_provider: str):
    if index_provider == 'MSCI':
        return {'display': 'block'}, {'display': 'none'}, {'display': 'none'}
    elif index_provider == 'US Treasury':
        return {'display': 'none'}, {'display': 'block'}, {'display': 'none'}
    else:
        return {'display': 'none'}, {'display': 'none'}, {'display': 'block'}


@app.callback(
    Output('others-tax-treatment-selection-container', 'style'),
    Input('others-index-selection', 'value'),
)
def update_others_tax_treatment_selection_visibility(others_index: str):
    if others_index == 'STI':
        return {'display': 'none'}
    else:
        return {'display': 'block'}


@app.callback(
    Output('selected-securities', 'value'),
    Output('selected-securities', 'options'),
    Input('add-index-button', 'n_clicks'),
    State('selected-securities', 'value'),
    State('selected-securities', 'options'),
    State('index-provider-selection', 'value'),
    State('index-provider-selection', 'options'),
    State('msci-index-selection', 'value'),
    State('msci-index-selection', 'options'),
    State('msci-size-selection', 'value'),
    State('msci-size-selection', 'options'),
    State('msci-style-selection', 'value'),
    State('msci-style-selection', 'options'),
    State('msci-tax-treatment-selection', 'value'),
    State('us-treasury-duration-selection', 'value'),
    State('us-treasury-duration-selection', 'options'),
    State('others-index-selection', 'value'),
    State('others-index-selection', 'options'),
    State('others-tax-treatment-selection', 'value'),
)
def add_index(
    _,
    selected_securities: None | list[str],
    selected_securities_options: dict[str, str],
    index_provider: str,
    index_provider_options: dict[str, str],
    msci_index: str,
    msci_index_options: dict[str, str],
    msci_size: str,
    msci_size_options: dict[str, str],
    msci_style: str,
    msci_style_options: dict[str, str],
    msci_tax_treatment: str,
    us_treasury_duration: str,
    us_treasury_duration_options: dict[str, str],
    others_index: str,
    others_index_options: dict[str, str],
    others_tax_treatment: str,
):
    if index_provider == 'MSCI':
        if glob(f'data/{index_provider}/{msci_index}/{msci_size}/{msci_style}/* {msci_tax_treatment}*.xls') == []:
            return selected_securities, selected_securities_options
        index = (
            f'{index_provider}|{msci_index}|{msci_size}|{msci_style}|{msci_tax_treatment}', " ".join(
                filter(
                    None,
                    [
                        index_provider_options[index_provider],
                        msci_index_options[msci_index],
                        (None if msci_size == 'STANDARD' else msci_size_options[msci_size]),
                        (None if msci_style == 'BLEND' else msci_style_options[msci_style]),
                        msci_tax_treatment,
                    ]
                )
            )
        )
    elif index_provider == 'US Treasury':
        index = (
            f'{index_provider}|{us_treasury_duration}', f'{us_treasury_duration_options[us_treasury_duration]} US Treasuries'
        )
    else:
        index = (
            f'Others|{others_index}|{others_tax_treatment}', f'{others_index_options[others_index]} {others_tax_treatment}'
        )
    if selected_securities is None:
        return [index[0]], {index[0]: index[1]}
    if index[0] in selected_securities:
        return selected_securities, selected_securities_options
    selected_securities.append(index[0])
    selected_securities_options.update({index[0]: index[1]})
    return selected_securities, selected_securities_options


@app.callback(
    Output('selected-securities', 'value', allow_duplicate=True),
    Output('selected-securities', 'options', allow_duplicate=True),
    Output('yf-securities-store', 'data'),
    Input('add-stock-etf-button', 'n_clicks'),
    State('selected-securities', 'value'),
    State('selected-securities', 'options'),
    State('stock-etf-input', 'value'),
    State('stock-etf-tax-treatment-selection', 'value'),
    State('yf-securities-store', 'data'),
    prevent_initial_call=True
)
def add_stock_etf(
    _,
    selected_securities: list[str],
    selected_securities_options: dict[str, str],
    stock_etf: str,
    tax_treatment: str,
    yf_securities_store: dict[str, str],
):
    if ';' in stock_etf:
        return selected_securities, selected_securities_options, yf_securities_store
    for yf_security in yf_securities_store:
        yss_ticker, _, yss_tax_treatment = yf_security.split('|')[1:]
        if stock_etf == yss_ticker and tax_treatment == yss_tax_treatment:
            if selected_securities is None:
                return [yf_security], {yf_security: f'{stock_etf} {tax_treatment}'}, yf_securities_store
            if yf_security in selected_securities:
                return selected_securities, selected_securities_options, yf_securities_store
    ticker = yf.Ticker(stock_etf)
    with StringIO() as ticker_info_output_buffer, redirect_stderr(ticker_info_output_buffer):
        ticker_info = ticker.info
        ticker_info_output = ticker_info_output_buffer.getvalue()
    if "404 Client Error: Not Found for url" in ticker_info_output:
        return selected_securities, selected_securities_options, yf_securities_store
    if ticker_info_output:
        print(ticker_info_output)
    if "currency" not in ticker_info:
        return selected_securities, selected_securities_options, yf_securities_store
    ticker_symbol = ticker.ticker
    currency = ticker_info['currency']
    new_yf_security = f'YF|{ticker_symbol}|{currency}|{tax_treatment}'
    if new_yf_security in selected_securities:
        return selected_securities, selected_securities_options, yf_securities_store
    selected_securities.append(new_yf_security)
    selected_securities_options[new_yf_security] = f'{ticker_symbol} {tax_treatment}'

    df = ticker.history(period='max', auto_adjust=False)
    df.set_index(df.index.tz_localize(None))
    if tax_treatment == 'Net' and 'dividends' in df.columns:
        manually_adjusted = df['Close'].add(df['dividends'].mul(0.7)).div(df['Close'].shift(1)).fillna(1).cumprod()
        manually_adjusted = manually_adjusted.div(manually_adjusted.iloc[-1]).mul(df['Adj Close'].iloc[-1])
        df['Adj Close'] = manually_adjusted
    yf_securities_store[new_yf_security] = df['Adj Close'].to_json(orient='index')

    return selected_securities, selected_securities_options, yf_securities_store


@app.callback(
    Output('fund-selection', 'options'),
    Output('fund-selection', 'value'),
    Input('fund-company-selection', 'value')
)
def update_fund_selection_options(fund_company: str):
    if fund_company == 'Great Eastern':
        return (
            [
                'Great Eastern-Lion Dynamic Balanced',
                'Great Eastern-Lion Dynamic Growth',
                'GreatLink ASEAN Growth',
                'GreatLink Asia Pacific Equity',
                'GreatLink Cash',
                'GreatLink China Growth',
                'GreatLink Diversified Growth Portfolio',
                'GreatLink European Sustainable Equity Fund',
                'GreatLink Far East Ex Japan Equities',
                'GreatLink Global Bond',
                'GreatLink Global Disruptive Innovation Fund',
                'GreatLink Global Emerging Markets Equity',
                'GreatLink Global Equity Alpha',
                'GreatLink Global Equity',
                'GreatLink Global Optimum',
                'GreatLink Global Perspective',
                'GreatLink Global Real Estate Securities',
                'GreatLink Global Supreme',
                'GreatLink Global Technology',
                'GreatLink Income Bond',
                'GreatLink Income Focus',
                'GreatLink International Health Care Fund',
                'GreatLink LifeStyle Balanced Portfolio',
                'GreatLink LifeStyle Dynamic Portfolio',
                'GreatLink LifeStyle Progressive Portfolio',
                'GreatLink LifeStyle Secure Portfolio',
                'GreatLink LifeStyle Steady Portfolio',
                'GreatLink Lion Asian Balanced',
                'GreatLink Lion India',
                'GreatLink Lion Japan Growth',
                'GreatLink Lion Vietnam',
                'GreatLink Multi-Sector Income',
                'GreatLink Multi-Theme Equity',
                'GreatLink Short Duration Bond',
                'GreatLink Singapore Equities',
                'GreatLink Sustainable Global Thematic Fund',
                'GreatLink US Income and Growth Fund (Dis)'
            ],
            'Great Eastern-Lion Dynamic Balanced',
        )
    elif fund_company == 'GMO':
        return (
            [
                'Quality Investment Fund',
            ],
            'Quality Investment Fund',
        )
    else:
        return (
            [],
            None,
        )


@app.callback(
    Output('selected-securities', 'value', allow_duplicate=True),
    Output('selected-securities', 'options', allow_duplicate=True),
    Input('add-fund-button', 'n_clicks'),
    State('selected-securities', 'value'),
    State('selected-securities', 'options'),
    State('fund-company-selection', 'value'),
    State('fund-selection', 'value'),
    prevent_initial_call=True
)
def add_fund(
    _,
    selected_securities: list[str],
    selected_securities_options: dict[str, str],
    fund_company: str,
    fund: str,
):
    if fund_company == 'Great Eastern':
        currency = 'SGD'
    else:
        currency = 'USD'
    fund = (f'Fund|{fund_company}|{fund}|{currency}', f'{f'{fund_company} ' if fund_company != 'Great Eastern' else ''}{fund}')
    if fund[0] in selected_securities:
        return selected_securities, selected_securities_options
    selected_securities.append(fund[0])
    selected_securities_options.update({fund[0]: fund[1]})
    return selected_securities, selected_securities_options


@app.callback(
    Output('log-scale-selection', 'style'),
    Output('log-scale-selection', 'value'),
    Input('y-var-selection', 'value'),
    Input('log-scale-selection', 'value')
)
def update_log_scale(y_var: str, log_scale: list[str]):
    if y_var == 'price':
        return {'display': 'block'}, log_scale
    else:
        return {'display': 'none'}, []


@app.callback(
    Output('return-selection', 'style'),
    Input('y-var-selection', 'value')
)
def update_return_selection_visibility(y_var: str):
    if y_var == 'rolling_returns':
        return {'display': 'block'}
    else:
        return {'display': 'none'}


@app.callback(
    Output('baseline-security-selection', 'options'),
    Output('baseline-security-selection', 'value'),
    Input('selected-securities', 'value'),
    Input('selected-securities', 'options'),
    Input('baseline-security-selection', 'value'),
)
def update_baseline_security_selection_options(
    selected_securities: list[str],
    selected_securities_options: dict[str, str],
    baseline_security: str,
):
    return {
        'None': 'None',
        **{
            k: v
            for k, v in selected_securities_options.items()
            if k in selected_securities
        }
    }, baseline_security if baseline_security in selected_securities else 'None'


@app.callback(
    Output('graph', 'figure'),
    Input('selected-securities', 'value'),
    Input('selected-securities', 'options'),
    Input('yf-securities-store', 'data'),
    Input('currency-selection', 'value'),
    Input('inflation-adjustment-selection', 'value'),
    Input('y-var-selection', 'value'),
    Input('y-var-selection', 'options'),
    Input('return-duration-selection', 'value'),
    Input('return-duration-selection', 'options'),
    Input('return-type-selection', 'value'),
    Input('return-type-selection', 'options'),
    Input('interval-selection', 'value'),
    Input('baseline-security-selection', 'value'),
    Input('baseline-security-selection', 'options'),
    Input('log-scale-selection', 'value'),
)
def update_graph(
    selected_securities: list[str],
    selected_securities_options: dict[str, str],
    yf_securities: dict[str, str],
    currency: str,
    adjust_for_inflation: str,
    y_var: str,
    y_var_options: dict[str, str],
    return_duration: str,
    return_duration_options: dict[str, str],
    return_type: str,
    return_type_options: dict[str, str],
    interval: str,
    baseline_security: str,
    baseline_security_options: dict[str, str],
    log_scale: list[str],
):
    df = pd.DataFrame(
        {
            selected_securities_options[selected_security]: transform_df(load_df(selected_security, interval, currency, adjust_for_inflation,
                                                                         yf_securities.get(selected_security)), interval, y_var, return_duration, return_type)
            for selected_security in selected_securities
        }
    )
    if y_var == 'rolling_returns' and baseline_security != 'None':
        df = df.sub(df[baseline_security_options[baseline_security]], axis=0, level=0)
    data = [
        go.Scatter(
            x=df.index,
            y=df[column],
            mode='lines',
            name=column
        )
        for column in df.columns
    ]
    layout = go.Layout(
        title=f'{return_duration_options[return_duration]} {return_type_options[return_type]} Rolling Returns' if y_var == 'rolling_returns' else y_var_options[y_var],
        hovermode='x unified',
        yaxis=dict(
            tickformat='.2f' if y_var == 'price' else '.2%',
            type='log' if 'log' in log_scale else 'linear'
        )
    )
    return dict(data=data, layout=layout)


@app.callback(
    Output('portfolio-security', 'options'),
    Input('selected-securities', 'options'),
)
def update_portfolio_securities(selected_securities_options: dict[str, str]):
    return selected_securities_options


@app.callback(
    Output('ls-input-container', 'style'),
    Output('dca-input-container', 'style'),
    Input('ls-dca-selection', 'value'),
)
def update_ls_input_visibility(ls_dca: str):
    if ls_dca == 'LS':
        return {'display': 'block'}, {'display': 'none'}
    else:
        return {'display': 'none'}, {'display': 'block'}


@app.callback(
    Output('portfolios', 'value'),
    Output('portfolios', 'options'),
    Input('add-portfolio-button', 'n_clicks'),
    State('portfolios', 'value'),
    State('portfolios', 'options'),
    State('portfolio-security', 'value'),
    State('portfolio-security', 'options'),
    State('portfolio-currency-selection', 'value'),
    State('ls-dca-selection', 'value'),
    State('investment-amount-input', 'value'),
    State('monthly-investment-input', 'value'),
    State('investment-horizon-input', 'value'),
    State('dca-length-input', 'value'),
    State('dca-interval-input', 'value'),
    State('variable-transaction-fees-input', 'value'),
    State('fixed-transaction-fees-input', 'value'),
    State('annualised-holding-fees-input', 'value'),
    prevent_initial_call=True,
)
def update_portfolios(
    _,
    portfolios: list[str],
    portfolios_options: dict[str, str],
    portfolio_security: str,
    portfolio_security_options: dict[str, str],
    currency: str,
    ls_dca: str,
    investment_amount: float,
    monthly_investment: float,
    investment_horizon: int,
    dca_length: int,
    dca_interval: int,
    variable_transaction_fees: float,
    fixed_transaction_fees: float,
    annualised_holding_fees: float,
):
    if portfolio_security is None:
        return portfolios, portfolios_options
    if ls_dca == 'LS':
        if investment_amount is None:
            return portfolios, portfolios_options
        if investment_horizon is None:
            return portfolios, portfolios_options
        if dca_length is None:
            dca_length = 1
        if dca_interval is None:
            dca_interval = 1
    if ls_dca == 'DCA':
        if monthly_investment is None:
            return portfolios, portfolios_options
        if dca_length is None:
            return portfolios, portfolios_options
        if investment_horizon is None:
            investment_horizon = dca_length
        if dca_interval is None:
            dca_interval = 1
    if dca_length > investment_horizon:
        return portfolios, portfolios_options
    if variable_transaction_fees is None:
        variable_transaction_fees = 0
    if fixed_transaction_fees is None:
        fixed_transaction_fees = 0
    if annualised_holding_fees is None:
        annualised_holding_fees = 0
    if variable_transaction_fees < 0 or fixed_transaction_fees < 0 or annualised_holding_fees < 0:
        return portfolios, portfolios_options
    if ls_dca == 'LS':
        portfolio = (
            f'{portfolio_security};{currency};{ls_dca};{investment_amount};{investment_horizon};{monthly_investment};{
                dca_length};{dca_interval};{variable_transaction_fees};{fixed_transaction_fees};{annualised_holding_fees}',
            f'{portfolio_security_options[portfolio_security]} {currency}, {"Lump Sum"}, {investment_amount} invested for {investment_horizon} months, {f" DCA over {
                dca_length} months every {dca_interval} months"} {variable_transaction_fees/100}% + ${fixed_transaction_fees} Fee, {annualised_holding_fees}% p.a. Holding Fees'
        )

    else:
        portfolio = (
            f'{portfolio_security};{currency};{ls_dca};{investment_amount};{investment_horizon};{monthly_investment};{
                dca_length};{dca_interval};{variable_transaction_fees};{fixed_transaction_fees};{annualised_holding_fees}',
            f'{portfolio_security_options[portfolio_security]} {currency}, {"DCA"}, {monthly_investment} invested monthly for {dca_length} months, {
                dca_interval} months apart, {variable_transaction_fees/100}% + ${fixed_transaction_fees} Fee, {annualised_holding_fees}% p.a. Holding Fees'

        )

    if portfolios is None:
        return [portfolio[0]], {portfolio[0]: portfolio[1]}
    if portfolio[0] in portfolios:
        return portfolios, portfolios_options
    portfolios.append(portfolio[0])
    portfolios_options.update({portfolio[0]: portfolio[1]})
    return portfolios, portfolios_options


@app.callback(
    Output('portfolio-graph', 'figure'),
    Input('portfolios', 'value'),
    State('portfolios', 'options'),
    State('yf-securities-store', 'data'),
    prevent_initial_call=True,
)
def update_portfolio_graph(
    portfolios: list[str],
    portfolio_options: dict[str, str],
    yf_securities: dict[str, str],

):
    series = []
    if not portfolios:
        return {
            'data': [],
            'layout': {
                'title': 'Portfolio Simulation',
            }
        }
    for portfolio in portfolios:
        portfolio_security, currency, ls_dca, investment_amount, investment_horizon, monthly_investment, dca_length, dca_interval, variable_transaction_fees, fixed_transaction_fees, annualised_holding_fees = portfolio.split(
            ';')
        investment_amount, investment_horizon, monthly_investment, dca_length, dca_interval, variable_transaction_fees, fixed_transaction_fees, annualised_holding_fees = (
            *[float(x) if x != 'None' else 0 for x in [investment_amount, investment_horizon, monthly_investment,
                                                       dca_length, dca_interval, variable_transaction_fees, fixed_transaction_fees, annualised_holding_fees]],
        )
        variable_transaction_fees /= 100
        annualised_holding_fees /= 100
        portfolio_series = pd.Series(
            load_df(portfolio_security, 'Monthly', currency, 'No', yf_securities.get(portfolio_security)),
            name=portfolio_security
        )
        interest_rates = load_fed_funds_rate()[1].reindex(portfolio_series.index).fillna(0).to_numpy() if currency == 'USD' else load_sgd_interest_rates()[
            1]['sgd_ir_1m'].reindex(portfolio_series.index).fillna(0).to_numpy()

        if ls_dca == 'LS':
            ending_values = pd.Series(
                calculate_lumpsum_return_with_fees_and_interest_vector(
                    portfolio_series.pct_change().to_numpy(),
                    dca_length,
                    dca_interval,
                    investment_horizon,
                    investment_amount,
                    variable_transaction_fees,
                    fixed_transaction_fees,
                    annualised_holding_fees,
                    interest_rates
                ),
                index=portfolio_series.index,
                name=portfolio
            ).add(1).mul(investment_amount)
        else:
            ending_values = pd.Series(
                calculate_dca_return_with_fees_and_interest_vector(
                    portfolio_series.pct_change().to_numpy(),
                    dca_length,
                    dca_interval,
                    investment_horizon,
                    monthly_investment,
                    variable_transaction_fees,
                    fixed_transaction_fees,
                    annualised_holding_fees,
                    interest_rates
                ),
                index=portfolio_series.index,
                name=portfolio

            ).add(1).mul(monthly_investment * dca_length)
        series.append(ending_values)
    ending_values = pd.concat(series, axis=1, names=portfolios)
    return {
        'data': [
            go.Scatter(
                x=ending_values.index,
                y=ending_values[security],
                mode='lines',
                name=portfolio_options[security]
            )
            for security in ending_values.columns
        ],
        'layout': {
            'title': 'Portfolio Simulation',
        }
    }


if __name__ == '__main__':
    app.run(debug=True)
