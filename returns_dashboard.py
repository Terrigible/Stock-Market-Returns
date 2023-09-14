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
                dcc.Graph(id='graph'),
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
              Input('index-selection', 'value'))
def update_graph(index_provider, index):
    data = go.Scatter()
    layout = go.Layout(title=f'{index_provider} {index}')
    return dict(data=data, layout=layout)

if __name__ == '__main__':
    app.run()
