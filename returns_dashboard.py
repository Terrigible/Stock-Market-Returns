from glob import glob
from io import StringIO

import pandas as pd
import plotly.graph_objects as go
import yahooquery as yq
from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State

from funcs import load_usdsgd, read_msci_data, read_spx_data, read_sti_data, load_sg_cpi, load_us_cpi, load_us_treasury_returns


def load_df(security: str, interval: str, currency: str, yf_securities: dict[str, str]):
    if security.split('-')[0] == 'MSCI':
        df = read_msci_data('data/{}/{}/{}/{}/*{} {}*.xls'.format(*security.split('-'), interval))
    elif security.split('-')[0] == 'US Treasury':
        df = load_us_treasury_returns(security.split('-')[1]).to_frame()
        if interval == 'Monthly':
            df = df.resample('BM').last()
    elif security.split('-')[0] == 'Others':
        if security.split('-')[1] == 'STI':
            df = read_sti_data()
        elif security.split('-')[1] == 'SPX':
            df = read_spx_data()
        else:
            raise ValueError('Invalid index')
        if interval == 'Monthly':
            df = df.resample('BM').last()
    elif security.split('-')[0] == 'YF':
        df = pd.read_json(StringIO(yf_securities[security.split('-')[1]]), orient='index')
        if interval == 'Monthly':
            df = df.resample('BM').last()
    else:
        raise ValueError('Invalid index')
    series = df.iloc[:, 0]
    if currency == 'SGD':
        series = series.mul(load_usdsgd().resample('D').ffill().ffill().reindex(series.index))
    if currency == 'SG CPI':
        series = series.div(load_sg_cpi().iloc[:, 0].resample('D').ffill().ffill().reindex(series.index))
    if currency == 'US CPI':
        series = series.div(load_us_cpi().iloc[:, 0].resample('D').ffill().ffill().reindex(series.index))
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
                    (series.index - pd.offsets.DateOffset(months=return_durations[return_duration]))
                    .to_series()
                    .apply(pd.offsets.BusinessDay().rollback)
                    .set_axis(series.index)
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


app = Dash()

server = app.server

app.layout = html.Div(
    [
        html.Div(
            [
                html.Label('Security Type'),
                dcc.Dropdown(
                    [
                        'Index',
                        'Stock/ETF'
                    ],
                    value='Index',
                    clearable=False,
                    id='security-type-selection'
                ),
                html.Div(
                    [
                        html.Label('Index Provider'),
                        dcc.Dropdown(
                            {
                                'MSCI': 'MSCI',
                                'US Treasury': 'US Treasury',
                                'Others': 'Others'
                            },
                            value='MSCI',
                            clearable=False,
                            id='index-provider-selection'
                        ),
                        html.Div(
                            [
                                html.Label('Index'),
                                dcc.Dropdown(
                                    {
                                        'WORLD': 'World',
                                        'ACWI': 'ACWI',
                                        'SINGAPORE': 'Singapore',
                                        'EM (EMERGING MARKETS)': 'Emerging Markets',
                                        'USA': 'USA',
                                    },
                                    value='WORLD',
                                    clearable=False,
                                    id='msci-index-selection'
                                ),
                                html.Label('Size'),
                                dcc.Dropdown(
                                    {
                                        'STANDARD': 'Standard',
                                        'SMALL': 'Small',
                                        'SMID': 'SMID',
                                        'MID': 'Mid',
                                        'LARGE': 'Large',
                                        'IMI': 'IMI',
                                    },
                                    value='STANDARD',
                                    clearable=False,
                                    id='msci-size-selection'
                                ),
                                html.Label('Style'),
                                dcc.Dropdown(
                                    {
                                        'BLEND': 'None',
                                        'GROWTH': 'Growth',
                                        'VALUE': 'Value'
                                    },
                                    value='BLEND',
                                    clearable=False,
                                    id='msci-style-selection'
                                ),
                                html.Label('Tax Treatment'),
                                dcc.Dropdown(
                                    [
                                        'Gross',
                                        'Net'
                                    ],
                                    value='Gross',
                                    clearable=False,
                                    id='msci-tax-treatment-selection'
                                ),
                            ],
                            id='msci-index-selection-container'
                        ),
                        html.Div(
                            [
                                html.Label('Duration'),
                                dcc.Dropdown(
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
                                dcc.Dropdown(
                                    {
                                        'STI': 'STI',
                                        'SPX': 'S&P 500',
                                    },
                                    value='STI',
                                    clearable=False,
                                    id='others-index-selection'
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
                        html.P('Warning: Loading Yahoo Finance data may take a while'),
                        html.P(),
                        html.Button(
                            'Add Stock/ETF',
                            id='add-stock-etf-button'
                        ),
                    ],
                    id='stock-etf-selection-container',
                ),
                dcc.Store(id='yf-securities-store', storage_type='memory', data={}),
                html.P(),
                html.Label('Selected Securities'),
                dcc.Dropdown(
                    {},
                    multi=True,
                    id='selected-securities',
                ),
                html.Label('Interval'),
                dcc.Dropdown(
                    [
                        'Monthly',
                        'Daily'
                    ],
                    value='Monthly',
                    clearable=False,
                    id='interval-selection'
                ),
                html.Label('Currency'),
                dcc.Dropdown(
                    [
                        'SGD',
                        'USD',
                        'SG CPI',
                        'US CPI',
                    ],
                    value='USD',
                    clearable=False,
                    id='currency-selection'
                ),
                html.Label('Value'),
                dcc.Dropdown(
                    {
                        'price': 'Price',
                        'drawdown': 'Drawdown',
                        'return': 'Return'
                    },
                    value='price',
                    clearable=False,
                    id='y-var-selection'
                ),
                html.Div(
                    [
                        html.Label('Return Duration'),
                        dcc.Dropdown(
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
                            clearable=False,
                            id='return-duration-selection'
                        ),
                        html.Label('Return Type'),
                        dcc.Dropdown(
                            {
                                'cumulative': 'Cumulative',
                                'annualized': 'Annualized'
                            },
                            value='cumulative',
                            clearable=False,
                            id='return-type-selection'
                        ),
                        html.Label('Baseline'),
                        dcc.Dropdown(
                            {
                                'None': 'None',
                            },
                            value='None',
                            clearable=False,
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
                "overflow": "scroll",
                "position": "fixed",
                "top": 0,
                "left": 0,
                "bottom": 0,
                "width": "18rem",
                "padding": "2rem 1rem"
            }
        ),
        html.Div(
            [
                dcc.Graph(
                    id='graph',
                    style={
                        'height': '90vh'
                    }
                ),
            ],
            style={
                "margin-left": "20rem",
                "margin-right": "2rem",
                "padding": "2rem 1rem"
            }
        )
    ]
)


@app.callback(
    Output('index-selection-container', 'style'),
    Output('stock-etf-selection-container', 'style'),
    Input('security-type-selection', 'value'),
)
def update_index_selection_visibility(security_type: str):
    if security_type == 'Index':
        return {'display': 'block'}, {'display': 'none'}
    else:
        return {'display': 'none'}, {'display': 'block'}


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
    others_index_options: dict[str, str]
):
    if index_provider == 'MSCI':
        if glob(f'data/{index_provider}/{msci_index}/{msci_size}/{msci_style}/* {msci_tax_treatment}*.xls') == []:
            return selected_securities, selected_securities_options
        selected_securities_options[f'{index_provider}-{msci_index}-{msci_size}-{msci_style}-{msci_tax_treatment}'] = " ".join(
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
        if selected_securities is None:
            return [f'{index_provider}-{msci_index}-{msci_size}-{msci_style}-{msci_tax_treatment}'], selected_securities_options
        elif f'{index_provider}-{msci_index}-{msci_size}-{msci_style}-{msci_tax_treatment}' in selected_securities:
            return selected_securities, selected_securities_options
        else:
            selected_securities.append(f'{index_provider}-{msci_index}-{msci_size}-{msci_style}-{msci_tax_treatment}')
            return selected_securities, selected_securities_options
    elif index_provider == 'US Treasury':
        if selected_securities is None:
            return [f'{index_provider}-{us_treasury_duration}'], selected_securities_options
        elif f'{index_provider}-{us_treasury_duration}' in selected_securities:
            return selected_securities, selected_securities_options
        else:
            selected_securities.append(f'{index_provider}-{us_treasury_duration}')
            selected_securities_options[f'{index_provider}-{us_treasury_duration}'] = f'{us_treasury_duration_options[us_treasury_duration]} US Treasuries'
            return selected_securities, selected_securities_options
    else:
        if selected_securities is None:
            return [f'Others-{others_index}'], selected_securities_options
        elif f'Others-{others_index}' in selected_securities:
            return selected_securities, selected_securities_options
        else:
            selected_securities.append(f'Others-{others_index}')
            selected_securities_options[f'Others-{others_index}'] = others_index_options[others_index]
            return selected_securities, selected_securities_options


@app.callback(
    Output('selected-securities', 'value', allow_duplicate=True),
    Output('selected-securities', 'options', allow_duplicate=True),
    Input('add-stock-etf-button', 'n_clicks'),
    State('selected-securities', 'value'),
    State('selected-securities', 'options'),
    State('stock-etf-input', 'value'),
    prevent_initial_call=True
)
def add_stock_etf(
    _,
    selected_securities: list[str],
    selected_securities_options: dict[str, str],
    stock_etf: str,
):
    ticker = yq.Ticker(stock_etf)
    ticker.validation
    if ticker.invalid_symbols:
        return selected_securities, selected_securities_options
    if f'YF-{stock_etf}' in selected_securities:
        return selected_securities, selected_securities_options
    else:
        selected_securities.append(f'YF-{stock_etf}')
        selected_securities_options[f'YF-{stock_etf}'] = stock_etf
        return selected_securities, selected_securities_options


@app.callback(
    Output('yf-securities-store', 'data'),
    Input('yf-securities-store', 'data'),
    Input('selected-securities', 'value'),
)
def update_yf_securities_store(yf_securities: dict[str, str], selected_securities: list[str]):
    yf_securities = yf_securities or {}
    for selected_security in selected_securities:
        if selected_security.split('-')[0] == 'YF':
            ticker = selected_security.split('-')[1]
            if ticker not in yf_securities:
                df = yq.Ticker(ticker).history(period='max').droplevel(0)
                yf_securities[ticker] = df['adjclose'].to_json(orient='index')
    return yf_securities


@app.callback(
    Output('return-selection', 'style'),
    Input('y-var-selection', 'value')
)
def update_return_selection_visibility(y_var: str):
    if y_var == 'return':
        return {'display': 'block'}
    else:
        return {'display': 'none'}


@app.callback(
    Output('baseline-security-selection', 'options'),
    Input('selected-securities', 'value'),
    Input('selected-securities', 'options'),
)
def update_baseline_security_selection_options(selected_securities: list[str], selected_securities_options: dict[str, str]):
    return {
        'None': 'None',
        **{
            selected_security: selected_securities_options[selected_security]
            for selected_security in selected_securities
        }
    }


@app.callback(
    Output('graph', 'figure'),
    Input('selected-securities', 'value'),
    Input('selected-securities', 'options'),
    Input('yf-securities-store', 'data'),
    Input('currency-selection', 'value'),
    Input('y-var-selection', 'value'),
    Input('y-var-selection', 'options'),
    Input('return-duration-selection', 'value'),
    Input('return-duration-selection', 'options'),
    Input('return-type-selection', 'value'),
    Input('return-type-selection', 'options'),
    Input('interval-selection', 'value'),
    Input('baseline-security-selection', 'value'),
    Input('baseline-security-selection', 'options'),
)
def update_graph(
    selected_securities: list[str],
    selected_securities_options: dict[str, str],
    yf_securities: dict[str, str],
    currency: str,
    y_var: str,
    y_var_options: dict[str, str],
    return_duration: str,
    return_duration_options: dict[str, str],
    return_type: str,
    return_type_options: dict[str, str],
    interval: str,
    baseline_security: str,
    baseline_security_options: dict[str, str],
):
    df = pd.DataFrame(
        {
            selected_securities_options[selected_security]: transform_df(load_df(selected_security, interval, currency, yf_securities), interval, y_var, return_duration, return_type)
            for selected_security in selected_securities
        }
    )
    if y_var == 'return' and baseline_security != 'None':
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
        title=f'{return_duration_options[return_duration]} {return_type_options[return_type]} Return' if y_var == 'return' else y_var_options[y_var],
        hovermode='x unified',
        yaxis=dict(
            tickformat='.2f' if y_var == 'price' else '.2%',
        )
    )
    return dict(data=data, layout=layout)


if __name__ == '__main__':
    app.run()
