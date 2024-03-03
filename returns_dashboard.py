from glob import glob
from io import StringIO

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yahooquery as yq
from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State

from funcs.loaders import load_usdsgd, read_msci_data, read_spx_data, read_sti_data, load_sg_cpi, load_us_cpi, load_us_treasury_returns, load_fred_usd_fx, load_mas_sgd_fx


def load_df(security: str, interval: str, currency: str, adjust_for_inflation: str, yf_securities: dict[str, str]):
    source = security.split('|')[0]
    if source == 'MSCI':
        series = read_msci_data('data/{}/{}/{}/{}/*{} {}*.xls'.format(*security.split('|'), interval)).iloc[:, 0]
    elif source == 'US Treasury':
        series = load_us_treasury_returns(security.split('|')[1])
        if interval == 'Monthly':
            series = series.resample('BM').last()
    elif source == 'Others':
        if security.split('|')[1] == 'STI':
            series = read_sti_data().iloc[:, 0]
        elif security.split('|')[1] == 'SPX':
            series = read_spx_data(security.split('|')[2]).iloc[:, 0]
        else:
            raise ValueError('Invalid index')
        if interval == 'Monthly':
            series = series.resample('BM').last()
    elif source == 'YF':
        ticker_currency = security.split('|')[2]
        series = pd.read_json(StringIO(yf_securities[security]), orient='index').iloc[:, 0]
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
            series = series.resample('BM').last()
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
                    searchable=False,
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
                            searchable=False,
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
                                        'KOKUSAI INDEX (WORLD ex JP)': 'World ex Japan',
                                        'JAPAN': 'Japan',
                                    },
                                    value='WORLD',
                                    clearable=False,
                                    searchable=False,
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
                                    searchable=False,
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
                                    searchable=False,
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
                                    searchable=False,
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
                                    searchable=False,
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
                                    searchable=False,
                                    id='others-index-selection'
                                ),
                                html.Div(
                                    [
                                        html.Label('Tax Treatment'),
                                        dcc.Dropdown(
                                            [
                                                'Gross',
                                                'Net'
                                            ],
                                            value='Gross',
                                            clearable=False,
                                            searchable=False,
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
                        html.P('Warning: Loading Yahoo Finance data may take a while'),
                        html.Label('Tax Treatment'),
                        dcc.Dropdown(
                            [
                                'Gross',
                                'Net'
                            ],
                            value='Gross',
                            clearable=False,
                            searchable=False,
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
                    searchable=False,
                    id='interval-selection'
                ),
                html.Label('Currency'),
                dcc.Dropdown(
                    [
                        'SGD',
                        'USD',
                    ],
                    value='USD',
                    clearable=False,
                    searchable=False,
                    id='currency-selection'
                ),
                html.Label('Adjust for Inflation'),
                dcc.Dropdown(
                    [
                        'No',
                        'Yes',
                    ],
                    value='No',
                    clearable=False,
                    searchable=False,
                    id='inflation-adjustment-selection'
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
                    searchable=False,
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
                            searchable=False,
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
                            searchable=False,
                            id='return-type-selection'
                        ),
                        html.Label('Baseline'),
                        dcc.Dropdown(
                            {
                                'None': 'None',
                            },
                            value='None',
                            clearable=False,
                            searchable=False,
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
                'box-sizing': 'border-box',
                'flex': '1',
                'overflow': 'auto',
            }
        ),
        dcc.Graph(
            id='graph',
            style={
                'width': '85%',
                'height': '100%',
                'box-sizing': 'border-box',
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
    yf_securities: dict[str, str],
):
    ticker = yq.Ticker(stock_etf)
    ticker.validation
    if ticker.invalid_symbols:
        return selected_securities, selected_securities_options, yf_securities
    currency = ticker.summary_detail[stock_etf]['currency']
    new_yf_security = f'YF|{stock_etf}|{currency}|{tax_treatment}'
    if new_yf_security in selected_securities:
        return selected_securities, selected_securities_options, yf_securities
    selected_securities.append(new_yf_security)
    selected_securities_options[new_yf_security] = f'{stock_etf} {tax_treatment}'

    df = ticker.history(period='max').droplevel(0)
    if tax_treatment == 'Net':
        manually_adjusted = df['close'].add(df['dividends'].mul(0.7)).div(df['close'].shift(1)).fillna(1).cumprod()
        manually_adjusted = manually_adjusted.div(manually_adjusted.iloc[-1]).mul(df['adjclose'].iloc[-1])
        df['adjclose'] = manually_adjusted
    yf_securities[new_yf_security] = df['adjclose'].to_json(orient='index')

    return selected_securities, selected_securities_options, yf_securities


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
    if y_var == 'return':
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
                                                                         yf_securities), interval, y_var, return_duration, return_type)
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
            type='log' if 'log' in log_scale else 'linear'
        )
    )
    return dict(data=data, layout=layout)


if __name__ == '__main__':
    app.run()
