from glob import glob
from dash import Dash, html, dcc
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import pandas as pd

from funcs import read_msci_data, add_return_columns, read_sti_data, read_spx_data


def load_df(index: str, interval: str):
    if index.split('-')[0] == 'MSCI':
        return read_msci_data('data/{}/{}/{}/{}/*{} {} {}*.xls'.format(*index.split('-'), interval))
    if index.split('-')[0] == 'Others':
        if index.split('-')[1] == 'STI':
            df = read_sti_data()
        elif index.split('-')[1] == 'SPX':
            df = read_spx_data()
        else:
            raise ValueError('Invalid index')
        if interval == 'Monthly':
            df = df.resample('BM').last()
        return df
    raise ValueError('Invalid index')


def transform_df(df: pd.DataFrame, interval: str, y_var: str, return_duration: str, return_type: str) -> pd.Series:
    series = df['price']
    if y_var == 'price':
        return series
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
    interval_multiplier = 1 if interval == 'Monthly' else 21.5
    series = series.pct_change(periods=round(return_durations[return_duration]*interval_multiplier))
    if return_type == 'annualized':
        series = series.add(1).pow(12 / round(return_durations[return_duration]*interval_multiplier)).sub(1)
    return series.dropna()


app = Dash()

app.layout = html.Div(
    [
        html.Div(
            [
                html.Label('Index Provider'),
                dcc.Dropdown(
                    {
                        'MSCI': 'MSCI',
                        'Others': 'Others'
                    },
                    value='MSCI',
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
                            id='msci-style-selection'
                        ),
                        html.Label('Currency'),
                        dcc.Dropdown(
                            [
                                'USD'
                            ],
                            value='USD',
                            id='msci-currency-selection'
                        ),
                        html.Label('Tax Treatment'),
                        dcc.Dropdown(
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
                        html.Label('Index'),
                        dcc.Dropdown(
                            {
                                'STI': 'STI',
                                'SPX': 'S&P 500',
                            },
                            value='STI',
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
                html.P(),
                html.Label('Selected Indexes'),
                dcc.Dropdown(
                    {},
                    multi=True,
                    id='selected-indexes',
                ),
                html.Label('Interval'),
                dcc.Dropdown(
                    [
                        'Monthly',
                        'Daily'
                    ],
                    value='Monthly',
                    id='interval-selection'
                ),
                html.Label('Value'),
                dcc.Dropdown(
                    {
                        'price': 'Price',
                        'return': 'Return'
                    },
                    value='price',
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
                            id='return-duration-selection'
                        ),
                        html.Label('Return Type'),
                        dcc.Dropdown(
                            {
                                'cumulative': 'Cumulative',
                                'annualized': 'Annualized'
                            },
                            value='cumulative',
                            id='return-type-selection'
                        )
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
    Output('msci-index-selection-container', 'style'),
    Output('others-index-selection-container', 'style'),
    Input('index-provider-selection', 'value'),
)
def update_msci_index_selection_visibility(index_provider: str):
    if index_provider == 'MSCI':
        return {'display': 'block'}, {'display': 'none'}
    else:
        return {'display': 'none'}, {'display': 'block'}


@app.callback(
    Output('selected-indexes', 'value'),
    Output('selected-indexes', 'options'),
    Input('add-index-button', 'n_clicks'),
    State('selected-indexes', 'value'),
    State('selected-indexes', 'options'),
    State('index-provider-selection', 'value'),
    State('index-provider-selection', 'options'),
    State('msci-index-selection', 'value'),
    State('msci-index-selection', 'options'),
    State('msci-size-selection', 'value'),
    State('msci-size-selection', 'options'),
    State('msci-style-selection', 'value'),
    State('msci-style-selection', 'options'),
    State('msci-currency-selection', 'value'),
    State('msci-tax-treatment-selection', 'value'),
    State('others-index-selection', 'value'),
    State('others-index-selection', 'options'),
)
def add_index(
    _,
    selected_indexes: None | list[str],
    selected_indexes_options: dict[str, str],
    index_provider: str,
    index_provider_options: dict[str, str],
    msci_index: str,
    msci_index_options: dict[str, str],
    msci_size: str,
    msci_size_options: dict[str, str],
    msci_style: str,
    msci_style_options: dict[str, str],
    msci_currency: str,
    msci_tax_treatment: str,
    others_index: str,
    others_index_options: dict[str, str]
):
    if index_provider == 'MSCI':
        if glob(f'data/{index_provider}/{msci_index}/{msci_size}/{msci_style}/*{msci_currency} {msci_tax_treatment}*.xls') == []:
            return selected_indexes, selected_indexes_options
        selected_indexes_options[f'{index_provider}-{msci_index}-{msci_size}-{msci_style}-{msci_currency}-{msci_tax_treatment}'] = " ".join(
            filter(
                None,
                [
                    index_provider_options[index_provider],
                    msci_index_options[msci_index],
                    (None if msci_size == 'STANDARD' else msci_size_options[msci_size]),
                    (None if msci_style == 'BLEND' else msci_style_options[msci_style]),
                    msci_currency,
                    msci_tax_treatment
                ]
            )
        )
        if selected_indexes is None:
            return [f'{index_provider}-{msci_index}-{msci_size}-{msci_style}-{msci_currency}-{msci_tax_treatment}'], selected_indexes_options
        elif f'{index_provider}-{msci_index}-{msci_size}-{msci_style}-{msci_currency}-{msci_tax_treatment}' in selected_indexes:
            return selected_indexes, selected_indexes_options
        else:
            selected_indexes.append(f'{index_provider}-{msci_index}-{msci_size}-{msci_style}-{msci_currency}-{msci_tax_treatment}')
            return selected_indexes, selected_indexes_options
    else:
        if selected_indexes is None:
            return [f'Others-{others_index}'], selected_indexes_options
        elif f'Others-{others_index}' in selected_indexes:
            return selected_indexes, selected_indexes_options
        else:
            selected_indexes.append(f'Others-{others_index}')
            selected_indexes_options[f'Others-{others_index}'] = others_index_options[others_index]
            return selected_indexes, selected_indexes_options


@app.callback(
    Output('return-selection', 'style'),
    Input('y-var-selection', 'value')
)
def update_return_selection_visibility(y_var: str):
    if y_var == 'price':
        return {'display': 'none'}
    else:
        return {'display': 'block'}


@app.callback(
    Output('graph', 'figure'),
    Input('selected-indexes', 'value'),
    Input('selected-indexes', 'options'),
    Input('y-var-selection', 'value'),
    Input('y-var-selection', 'options'),
    Input('return-duration-selection', 'value'),
    Input('return-duration-selection', 'options'),
    Input('return-type-selection', 'value'),
    Input('return-type-selection', 'options'),
    Input('interval-selection', 'value')
)
def update_graph(
    selected_indexes: list[str],
    selected_indexes_options: dict[str, str],
    y_var: str,
    y_var_options: dict[str, str],
    return_duration: str,
    return_duration_options: dict[str, str],
    return_type: str,
    return_type_options: dict[str, str],
    interval: str
):
    data = [
        go.Scatter(
            x=transform_df(load_df(selected_index, interval), interval, y_var, return_duration, return_type).index,
            y=transform_df(load_df(selected_index, interval), interval, y_var, return_duration, return_type),
            mode='lines',
            name=selected_indexes_options[selected_index]
        )
        for selected_index in selected_indexes
    ]
    layout = go.Layout(
        title=y_var_options[y_var] if y_var == 'price' else f'{return_duration_options[return_duration]} {return_type_options[return_type]} Return',
        hovermode='x unified',
        yaxis=dict(
            tickformat='.2f' if y_var == 'price' else '.2%',
        )
    )
    return dict(data=data, layout=layout)


if __name__ == '__main__':
    app.run()
