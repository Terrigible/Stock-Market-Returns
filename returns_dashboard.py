from dash import Dash, html, dcc
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go

from funcs import read_msci_data

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
                        'SINGAPORE': 'Singapore'
                    },
                    value='WORLD',
                    id='index-selection'
                ),
                html.Label('Size'),
                dcc.Dropdown(
                    {
                        'STANDARD': 'Standard',
                        'SMALL': 'Small',
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
                html.Label('Interval'),
                dcc.Dropdown(
                    [
                        'Monthly',
                        'Daily'
                    ],
                    value='Monthly',
                    id='interval-selection'
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
    State('tax-treatment-selection', 'value'),
    State('interval-selection', 'value')
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
    tax_treatment: str,
    interval: str
    ):
    selected_indexes_options[f'{index_provider}-{index}-{size}-{style}-{currency}-{tax_treatment}-{interval}'] = " ".join(
                filter(
                    None,
                    [
                        index_provider_options[index_provider],
                        index_options[index],
                        (None if size == 'STANDARD' else size_options[size]),
                        (None if style == 'BLEND' else style_options[style]),
                        currency,
                        tax_treatment,
                        interval
                    ]
                )
            )
    if selected_indexes is None:
        return [f'{index_provider}-{index}-{size}-{style}-{currency}-{tax_treatment}-{interval}'], selected_indexes_options
    elif f'{index_provider}-{index}-{size}-{style}-{currency}-{tax_treatment}-{interval}' in selected_indexes:
        return selected_indexes, selected_indexes_options
    else:
        selected_indexes.append(f'{index_provider}-{index}-{size}-{style}-{currency}-{tax_treatment}-{interval}')
        return selected_indexes, selected_indexes_options

@app.callback(Output('graph', 'figure'),
              Input('selected-indexes', 'value'),
              Input('selected-indexes', 'options'),
              )
def update_graph(
    selected_indexes: list[str],
    selected_indexes_options: dict[str, str]
    ):
    data = [
        go.Scatter(
            x=read_msci_data('data/{}/{}/{}/{}/*{} {} {}*.xls'.format(*selected_index.split('-'))).index,
            y=read_msci_data('data/{}/{}/{}/{}/*{} {} {}*.xls'.format(*selected_index.split('-')))['price'],
            mode='lines',
            name=selected_indexes_options[selected_index]
        )
        for selected_index in selected_indexes
    ]
    layout = go.Layout(
        title='price'
    )
    return dict(data=data, layout=layout)

if __name__ == '__main__':
    app.run()
