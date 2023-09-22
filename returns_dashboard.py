from glob import glob
from dash import Dash, html, dcc
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go

from funcs import read_msci_data, add_return_columns

def load_msci_df_with_return_columns(filename: str):
    df = read_msci_data(filename)
    if 'Monthly' in filename:
        durations = [1, 3, 6, 12, 24, 36, 60, 120, 180, 240, 300, 360]
    else:
        durations = [33, 66, 131, 261, 522, 783, 1305, 2609, 3915, 5218, 6523, 7827]
    add_return_columns(
        df,
        periods = ['1m', '3m', '6m', '1y', '2y', '3y', '5y', '10y', '15y', '20y', '25y', '30y'],
        durations = durations
        )
    return df

app = Dash()

app.layout = html.Div(
    [
        html.Div(
            [
                html.Label('Index Provider'),
                dcc.Dropdown(
                    {
                        'MSCI': 'MSCI'
                    },
                    value='MSCI',
                    id='index-provider-selection'
                ),
                html.Label('Index'),
                dcc.Dropdown(
                    {
                        'WORLD': 'World',
                        'ACWI': 'ACWI',
                        'SINGAPORE': 'Singapore',
                        'EM (EMERGING MARKETS)': 'Emerging Markets',
                    },
                    value='WORLD',
                    id='index-selection'
                ),
                html.Label('Size'),
                dcc.Dropdown(
                    {
                        'STANDARD': 'Standard',
                        'SMALL': 'Small',
                        'MID': 'Mid',
                        'LARGE': 'Large',
                    },
                    value='STANDARD',
                    id='size-selection'
                ),
                html.Label('Style'),
                dcc.Dropdown(
                    {
                        'BLEND': 'None',
                        'GROWTH': 'Growth',
                        'VALUE': 'Value'
                    },
                    value='BLEND',
                    id='style-selection'
                ),
                html.Label('Currency'),
                dcc.Dropdown(
                    [
                        'USD'
                    ],
                    value='USD',
                    id='currency-selection'
                    ),
                html.Label('Tax Treatment'),
                dcc.Dropdown(
                    [
                        'Gross',
                        'Net'
                    ],
                    value='Gross',
                    id='tax-treatment-selection'
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
                dcc.Dropdown(
                    {
                        'price': 'Price',
                        '1m_cumulative': '1m Cumulative Return',
                        '3m_cumulative': '3m Cumulative Return',
                        '6m_cumulative': '6m Cumulative Return',
                        '1y_cumulative': '1y Cumulative Return',
                        '2y_cumulative': '2y Cumulative Return',
                        '3y_cumulative': '3y Cumulative Return',
                        '5y_cumulative': '5y Cumulative Return',
                        '10y_cumulative': '10y Cumulative Return',
                        '15y_cumulative': '15y Cumulative Return',
                        '20y_cumulative': '20y Cumulative Return',
                        '25y_cumulative': '25y Cumulative Return',
                        '30y_cumulative': '30y Cumulative Return',
                        '1m_annualized': '1m Annualized Return',
                        '3m_annualized': '3m Annualized Return',
                        '6m_annualized': '6m Annualized Return',
                        '1y_annualized': '1y Annualized Return',
                        '2y_annualized': '2y Annualized Return',
                        '3y_annualized': '3y Annualized Return',
                        '5y_annualized': '5y Annualized Return',
                        '10y_annualized': '10y Annualized Return',
                        '15y_annualized': '15y Annualized Return',
                        '20y_annualized': '20y Annualized Return',
                        '25y_annualized': '25y Annualized Return',
                        '30y_annualized': '30y Annualized Return',
                    },
                    value='price',
                    id='column-selection'
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
    Output('selected-indexes', 'value'),
    Output('selected-indexes', 'options'),
    Input('add-index-button', 'n_clicks'),
    State('selected-indexes', 'value'),
    State('selected-indexes', 'options'),
    State('index-provider-selection', 'value'),
    State('index-provider-selection', 'options'),
    State('index-selection', 'value'),
    State('index-selection', 'options'),
    State('size-selection', 'value'),
    State('size-selection', 'options'),
    State('style-selection', 'value'),
    State('style-selection', 'options'),
    State('currency-selection', 'value'),
    State('tax-treatment-selection', 'value')
)
def add_index(
    _,
    selected_indexes: None | list[str],
    selected_indexes_options: dict[str, str],
    index_provider: str,
    index_provider_options: dict[str, str],
    index: str,
    index_options: dict[str, str],
    size: str,
    size_options: dict[str, str],
    style: str,
    style_options: dict[str, str],
    currency: str,
    tax_treatment: str
    ):
    if glob(f'data/{index_provider}/{index}/{size}/{style}/*{currency} {tax_treatment}*.xls') == []:
        return selected_indexes, selected_indexes_options
    selected_indexes_options[f'{index_provider}-{index}-{size}-{style}-{currency}-{tax_treatment}'] = " ".join(
                filter(
                    None,
                    [
                        index_provider_options[index_provider],
                        index_options[index],
                        (None if size == 'STANDARD' else size_options[size]),
                        (None if style == 'BLEND' else style_options[style]),
                        currency,
                        tax_treatment
                    ]
                )
            )
    if selected_indexes is None:
        return [f'{index_provider}-{index}-{size}-{style}-{currency}-{tax_treatment}'], selected_indexes_options
    elif f'{index_provider}-{index}-{size}-{style}-{currency}-{tax_treatment}' in selected_indexes:
        return selected_indexes, selected_indexes_options
    else:
        selected_indexes.append(f'{index_provider}-{index}-{size}-{style}-{currency}-{tax_treatment}')
        return selected_indexes, selected_indexes_options

@app.callback(
    Output('graph', 'figure'),
    Input('selected-indexes', 'value'),
    Input('selected-indexes', 'options'),
    Input('column-selection', 'value'),
    Input('column-selection', 'options'),
    Input('interval-selection', 'value')
)
def update_graph(
    selected_indexes: list[str],
    selected_indexes_options: dict[str, str],
    column: str,
    column_options: dict[str, str],
    interval: str
    ):
    data = [
        go.Scatter(
            x=load_msci_df_with_return_columns('data/{}/{}/{}/{}/*{} {} {}*.xls'.format(*selected_index.split('-'), interval)).index,
            y=load_msci_df_with_return_columns('data/{}/{}/{}/{}/*{} {} {}*.xls'.format(*selected_index.split('-'), interval))[column],
            mode='lines',
            name=selected_indexes_options[selected_index]
        )
        for selected_index in selected_indexes
    ]
    layout = go.Layout(
        title=column_options[column],
        hovermode='x unified',
        yaxis=dict(
            tickformat='.2f' if column == 'price' else '.2%',
        )
    )
    return dict(data=data, layout=layout)

if __name__ == '__main__':
    app.run()
