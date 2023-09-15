from dash import Dash, html, dcc
from dash.dependencies import Input, Output
import plotly.graph_objects as go

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
                        'STANDARD': 'Standard'
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
                )
                ],
            style={
                "overflow": "scroll",
                "position": "fixed",
                "top": 0,
                "left": 0,
                "bottom": 0,
                "width": "16rem",
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
                "margin-left": "18rem",
                "margin-right": "2rem",
                "padding": "2rem 1rem"
            }
        )
    ]
)

@app.callback(Output('graph', 'figure'),
              Input('index-provider-selection', 'value'),
              Input('index-provider-selection', 'options'),
              Input('index-selection', 'value'),
              Input('index-selection', 'options'),
              Input('size-selection', 'value'),
              Input('size-selection', 'options'),
              Input('style-selection', 'value'),
              Input('style-selection', 'options'),
              Input('currency-selection', 'value'),
              Input('tax-treatment-selection', 'value'),
              Input('interval-selection', 'value')
              )
def update_graph(
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
    df = read_msci_data(f'data/{index_provider}/{index}/{size}/{style}/*{currency} {tax_treatment} {interval}*.xls')
    data = [
        go.Scatter(
            x=df.index,
            y=df['price'],
            mode='lines',
        )
    ]
    layout = go.Layout(
        title=" ".join(
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
    )
    return dict(data=data, layout=layout)

if __name__ == '__main__':
    app.run()
