import dash
from dash import html
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
from dash import dcc
import flask
import secrets
from flask import session
from bleak import BleakClient, BleakScanner
import asyncio
import threading
import uuid
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go

import warnings

warnings.filterwarnings("ignore")

clients = {}
service_uuid = "fe8a042a-c4e3-11ea-87d0-0242ac130003"
characteristics_uuid = "fe8a0438-c4e3-11ea-87d0-0242ac130003"

heart_rate_commands = [0x806400, 0x80710403000000, 0xc070010101, 0xc0700203000000, 0xc070030100,
                       0xc07005020000, 0x80720100, 0xc072020a00000000000000000000,
                       0xc072030c000000000000000000000000,
                       0xc072052c0000000000000000000000000000000000000000000000000000000000000000010000000000000000000000,
                       0xc072045c0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000,
                       0x807604a0860100,
                       0x806617000700073f000000000402040003101004000310101010,
                       0x80660701000048000000,
                       0x80661a0257000000000009000000000000001500010000000000000000,
                       0x8066170300020000000000000000000000000000000000000000,
                       0x8066170400000000000000000000000000000000000000000000,
                       0x80660a05000000a76403075707,
                       0x80661606000000000000000000000000000000000000000000,
                       0x80660c070303000000000000000000,
                       0x80667b0800000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000,
                       0x80661e090700000a9f0001000000000000000000004f0000000000000000010000,
                       0x8066060a0000000000, 0x8066030b0000,
                       0x806814000101051e0519320600000090d00300d0bf0b00,
                       0x806c00, 0x806900, 0x807700, 0x806e00]

server = flask.Flask(__name__)
app = dash.Dash(__name__,
                server=server,
                external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP],
                suppress_callback_exceptions=True,
                meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1'}])
app.server.secret_key = secrets.token_hex(16)


async def scan_and_connect(device_mac_address, session_id):
    session_info = clients.get(session_id)
    if session_info and session_info.get("connected"):
        session['connection_status'] = 'Connected'
        session['connection_status_color'] = "success"
        return {
            "status": "already_connected",
            "message": f"Successfully connected to device {device_mac_address}!"
        }
    else:
        try:
            devices = await BleakScanner.discover()
            for device in devices:
                if device.address == device_mac_address:
                    Client = BleakClient(device.address)
                    await asyncio.wait_for(Client.connect(), timeout=20)
                    if Client.is_connected:
                        clients[session_id] = {
                            "client": Client,
                            "connected": True
                        }
                        session['connection_status'] = 'Connected'
                        session['connection_status_color'] = "success"

                        return {
                            "status": "success",
                            "message": f"Successfully connected to device {device_mac_address}!"
                        }
                    else:
                        session['connection_status'] = 'Not Connected'
                        session['connection_status_color'] = "danger"
                        return {
                            "status": "failure",
                            "message": f"Failed to connect to device {device_mac_address}."
                        }
            else:
                session['connection_status'] = 'No Device found'
                session['connection_status_color'] = "danger"
                return {
                    "status": "device_failure",
                    "message": f"No device found {device_mac_address}."
                }

        except Exception as e:
            session['connection_status'] = 'Connect Again'
            session['connection_status_color'] = "danger"
            return {
                "status": "error",
                "message": f"An error occurred: {e}"
            }


async def disconnect(session_id):
    try:
        session_info = clients.get(session_id)
        if not session_info:
            session['connection_status'] = 'No active device'
            session['connection_status_color'] = "danger"
            return {
                "status": "No_active",
                "message": "No active session to disconnect."
            }

        Client = session_info.get("client")
        if not Client:
            session['connection_status'] = 'No active device'
            session['connection_status_color'] = "danger"
            return {
                "status": "No_active",
                "message": "No active client to disconnect."
            }

        if Client.is_connected:
            try:
                await asyncio.wait_for(Client.disconnect(), timeout=10)
            except asyncio.TimeoutError:
                session['connection_status'] = 'Disconnect Again'
                session['connection_status_color'] = "danger"
                return {
                    "status": "failure",
                    "message": "Timeout occurred while disconnecting."
                }
            finally:
                clients.pop(session_id, None)
                session['connection_status'] = 'Disconnected'
                session['connection_status_color'] = "danger"
                return {
                    "status": "success",
                    "message": "Successfully disconnected!"
                }
        else:
            session['connection_status'] = 'No active device'
            session['connection_status_color'] = "danger"
            return {
                "status": "No_active",
                "message": "No active connection to disconnect."
            }
    except Exception as e:
        session['connection_status'] = 'Disconnect Again'
        session['connection_status_color'] = "success"
        return {
            "status": "error",
            "message": f"An error occurred: {e}"
        }


def run_coroutine(coroutine):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coroutine)


async def read_and_store_gatt_characteristics(session_id, data_storage):
    byte_arrays = []
    session_info = clients.get(session_id)
    if not session_info:
        session['connection_status'] = 'No active device'
        session['connection_status_color'] = "danger"
        return {
            "status": "No_active",
            "message": "No active session to Read."
        }

    client = session_info.get("client")
    if not client:
        session['connection_status'] = 'No active device'
        session['connection_status_color'] = "danger"
        return {
            "status": "No_active",
            "message": "No active client to read."
        }

    if client.is_connected:
        try:
            services = await client.get_services()
            for service in services:
                if service.uuid == service_uuid:
                    characteristics = service.characteristics
                    for characteristic in characteristics:
                        if characteristic.uuid == characteristics_uuid:
                            await client.start_notify(characteristics_uuid,
                                                      lambda sender, data: store_data(session_id, data, data_storage))
                            byte_arrays.extend([x.to_bytes((x.bit_length() + 7) // 8, 'big')
                                                for x in heart_rate_commands])

                            for command in byte_arrays:
                                response = await client.write_gatt_char(characteristics_uuid, command,
                                                                        response=True)
                                print("Write successful. Response:", response)
                            await asyncio.sleep(10)
                            turn_off_led_command = b'\x80o\x00'
                            await client.write_gatt_char(characteristics_uuid, turn_off_led_command,
                                                         response=True)
            return {
                "status": "success",
                "message": data_storage
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"An error occurred: {e}"
            }
    else:
        return {
            "status": "failure",
            "message": "No active connection to read from."
        }


async def monitor_connection(client, session_id):
    while True:
        if not client.is_connected:
            print(f"Client disconnected for session {session_id}, updating status...")
            clients.pop(session_id, None)
            session['connection_status'] = 'Disconnected'
            session['connection_status_color'] = "danger"
            break
        await asyncio.sleep(1)


def store_data(session_id, data, data_storage):
    hexadecimal_data = data.hex()
    integers = [int(hexadecimal_data[i:i + 4], 16) for i in range(0, len(hexadecimal_data), 4)]
    if session_id not in data_storage:
        data_storage[session_id] = []
    data_storage[session_id].extend(integers)


app.layout = html.Div([
    dbc.Container([
        html.Div([
            dbc.Button('Connect', id='connect-button', color='primary', style={'margin': '10px', 'width': '100px'}),
            dbc.Button('Disconnect', id='disconnect-button', color='primary',
                       style={'margin': '10px', 'width': '100px'}),
            dcc.Loading(
                id="loading-status-button",
                type="circle",
                children=dbc.Button('Status', id='status-button', color='primary', disabled=True,
                                    style={'margin': '10px', 'width': '150px'})
            ),
        ], style={'display': 'flex', 'justify-content': 'flex-end', 'margin': '0px'}),
        html.Div([
            html.Br(),
            html.H3("Unlocking insights into your health with Data-Driven analysis", style={'marginLeft': '20px',
                                                                                            'color': '#ffffff',
                                                                                            'fontFamily': 'sans-serif',
                                                                                            'textAlign': 'left'}),
            html.P(
                "Gain a deeper understanding of your well-being through your Physiological Signals",
                style={'marginLeft': '20px', 'color': '#ffffff', 'fontSize': '15px'}),
        ], style={'marginLeft': '50px'}, className="g-3"),
        html.Br(),
        html.Div([
            dbc.Row([
                dbc.Col(dcc.Dropdown(
                    id="patient-id-db",
                    options=[{'label': j, 'value': j} for j in ["Chiranjeevi", "Mahesh"]],
                    placeholder="Patient_id",
                    style={"height": "40px", 'borderRadius': '10px'}
                ), xs=12, sm=12, md=6, lg=8, xl=8),
                dbc.Col(
                    dbc.Button('Submit', id='submit-patient', color='primary',
                               style={"width": "50%", 'borderRadius': '10px', "height": "40px",
                                      "backgroundColor": "transparent"}),
                    xs=12, sm=12, md=6, lg=4, xl=4),
            ], justify="around", align="left", style={'width': '100%', 'textAlign': 'left'})
        ], style={'textAlign': 'left', 'width': '100%', 'marginLeft': '70px'}),
        html.Br(),
        html.Hr(style={'size': '10', 'borderColor': '#ffffff', 'borderHeight': "20vh",
                       'marginLeft': '70px', 'marginRight': '70px'}),
        html.Br(),
        html.Div(id="output-div-measurement")
    ], fluid=True),
], style={
    'backgroundColor': 'black',
    'minHeight': '100vh',
    'width': '100vw',
    'overflowX': 'hidden',
    'margin': '0',
    'padding': '0'
})

@app.callback(
    Output('status-button', 'children'),
    Output('status-button', 'color'),
    [Input('connect-button', 'n_clicks'),
     Input('disconnect-button', 'n_clicks')],
    [State('connect-button', 'n_clicks_timestamp'),
     State('disconnect-button', 'n_clicks_timestamp')]
)
def manage_ble_connection(connect_clicks, disconnect_clicks, connect_timestamp, disconnect_timestamp):
    session_id = session.get('session_id')
    device_mac_address = "CA:DE:07:50:DE:0C"

    if connect_clicks is None and disconnect_clicks is None:
        session['session_id'] = str(uuid.uuid4())
        session['connection_status'] = "No active device"
        session['connection_status_color'] = "danger"
        return session['connection_status'], session['connection_status_color']

    if connect_timestamp is not None and (disconnect_timestamp is None or connect_timestamp > disconnect_timestamp):
        run_coroutine(scan_and_connect(device_mac_address, session_id))

    if disconnect_timestamp is not None and (connect_timestamp is None or disconnect_timestamp > connect_timestamp):
        run_coroutine(disconnect(session_id))

    print(session)
    print(clients)
    return session['connection_status'], session['connection_status_color']


@app.callback(
    Output('output-div-measurement', 'children'),
    Input('submit-patient', 'n_clicks'),
    State('patient-id-db', 'value'),
)
def submit_patient_id(n_clicks, patient_id):
    if n_clicks is not None:
        if patient_id:
            return html.Div([
                html.Div([
                    html.H1('Vital Measurement', className='card-title', style={"color": "#ffffff"}),
                    dbc.Button('Measure/Start Measurement', id='start-measurement-button', color='primary',
                               className='mt-2', style={"backgroundColor": "transparent"}),
                ], style={'width': '50%', 'margin': 'auto', 'textAlign': 'center'}),
                html.Br(),
                html.Hr(style={'size': '10', 'borderColor': '#ffffff', 'borderHeight': "20vh",
                               'marginLeft': '70px', 'marginRight': '70px'}),
                html.Br(),
                html.Div(id="measurement-output")
            ])
        else:
            return html.Div([
                html.P('Please select the patient', className='card-title', style={"color": "red"}),
            ], style={'width': '50%', 'margin': 'auto', 'textAlign': 'center'}),


@app.callback(
    Output('measurement-output', 'children'),
    Input('start-measurement-button', 'n_clicks'),
    prevent_initial_call=True
)
def start_data_collection(n_clicks):
    session_id = session.get('session_id')
    if n_clicks is None:
        return dash.no_update

    data_storage = {}
    result = run_coroutine(read_and_store_gatt_characteristics(session_id, data_storage))

    if result['status'] == 'success':
        data = result["message"][session_id]
        df = pd.DataFrame(data, columns=["Data"])
    else:
        return html.Div([
            html.P(result["message"], className='card-title', style={"color": "red"}),
        ], style={'width': '50%', 'margin': 'auto', 'textAlign': 'center'}),

    return html.Div([
        dcc.Store(id='stored-data', data=df.to_dict('records')),
        html.Div([
            dbc.Container([
                html.Div([
                    dbc.Row([
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.Div(
                                                    [
                                                        html.I(className="bi bi-heart-fill",
                                                               style={"font-size": "2rem", "color": "#ffffff"}),
                                                        html.P("Heart Rate", className="card-text",
                                                               style={"color": "#ffffff"}),
                                                        html.P("60 BPM", className="card-text",
                                                               style={"color": "#3efb47"}),
                                                    ],
                                                    style={"textAlign": "center"}
                                                )
                                            ]
                                        )
                                    ],
                                    className="mb-4",
                                    style={"maxWidth": "540px", "border": "none"},
                                    color="black",
                                )
                            ],
                            xs=12, sm=12, md=6, lg=2, xl=2
                        ),
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.Div(
                                                    [
                                                        html.I(className="bi bi-droplet",
                                                               style={"font-size": "2rem", "color": "#ffffff"}),
                                                        html.P("SPO2", className="card-text",
                                                               style={"color": "#ffffff"}),
                                                        html.P("97%", className="card-text",
                                                               style={"color": "#3efb47"}),
                                                    ],
                                                    style={"textAlign": "center"}
                                                )
                                            ]
                                        )
                                    ],
                                    className="mb-4",
                                    style={"maxWidth": "540px", "border": "none"},
                                    color="black",
                                )
                            ],
                            xs=12, sm=12, md=6, lg=2, xl=2
                        ),
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.Div(
                                                    [
                                                        html.I(className="bi bi-heart-pulse-fill",
                                                               style={"font-size": "2rem", "color": "#ffffff"}),
                                                        html.P("Blood Pressure", className="card-text",
                                                               style={"color": "#ffffff"}),
                                                        html.P("120/80 mmHg", className="card-text",
                                                               style={"color": "#3efb47"}),
                                                    ],
                                                    style={"textAlign": "center"}
                                                )
                                            ]
                                        )
                                    ],
                                    className="mb-4",
                                    style={"maxWidth": "540px", "border": "none"},
                                    color="black",
                                )
                            ],
                            xs=12, sm=12, md=6, lg=2, xl=2
                        ),
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.Div(
                                                    [
                                                        html.I(className="bi bi-activity",
                                                               style={"font-size": "2rem", "color": "#ffffff"}),
                                                        html.P("Electrocardiogram", className="card-text",
                                                               style={"color": "#ffffff"}),
                                                        html.P("AFIB", className="card-text",
                                                               style={"color": "red"}),
                                                    ],
                                                    style={"textAlign": "center"}
                                                )
                                            ]
                                        )
                                    ],
                                    className="mb-4",
                                    style={"maxWidth": "540px", "border": "none"},
                                    color="black",
                                )
                            ],
                            xs=12, sm=12, md=6, lg=2, xl=2
                        ),
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.Div(
                                                    [
                                                        html.I(className="bi bi-lungs",
                                                               style={"font-size": "2rem", "color": "#ffffff"}),
                                                        html.P("Respiration Rate", className="card-text",
                                                               style={"color": "#ffffff"}),
                                                        html.P("15 Per minute", className="card-text",
                                                               style={"color": "#3efb47"}),
                                                    ],
                                                    style={"textAlign": "center"}
                                                )
                                            ]
                                        )
                                    ],
                                    className="mb-4",
                                    style={"maxWidth": "540px", "border": "none"},
                                    color="black",
                                )
                            ],
                            xs=12, sm=12, md=6, lg=2, xl=2
                        ),
                    ], justify="around", className="g-3"),

                ], style={'marginLeft': '50px'}, className="g-3"),
            ], fluid=True),
        ]),
        html.Div(id='output-div-plots'),
        dcc.Interval(
            id='graph-interval-component',
            interval=1000,
            n_intervals=0
        ),
    ])


#
@app.callback(Output('output-div-plots', 'children'),
              Input('graph-interval-component', 'n_intervals'),
              State('stored-data', 'data'))
def make_graphs(graph_interval, stored_rawdata):
    if stored_rawdata is not None:
        end_index = (graph_interval + 1) * 200
        stored_raw_df = pd.DataFrame(stored_rawdata)

        stop_index = 6000
        start_index = max(0, end_index - 1000)

        if end_index > stop_index:
            end_index = stop_index
            start_index = 0

        trace_ppg = go.Scatter(
            x=stored_raw_df.index[start_index:end_index],
            y=stored_raw_df['Data'].iloc[start_index:end_index],
            mode='lines',
            name='PPG',
            line=dict(color='blue')
        )

        fig = go.Figure(trace_ppg)
        fig.update_layout(
            height=500,
            title=dict(
                text='OPTICAL AND ELECTRICAL SIGNALS',
                font=dict(color='#ffffff')
            ),
            xaxis_title=dict(
                text='TimeStamp[Sec]',
                font=dict(color='#ffffff')
            ),
            yaxis_title=dict(
                text='Amplitude',
                font=dict(color='#ffffff')
            ),
            xaxis=dict(
                tickmode='array',
                tickangle=-45,
                tickfont=dict(size=10, color='white'),
                showgrid=True,
                gridcolor='rgba(128,128,128,0.2)',
                gridwidth=1,
                zeroline=False,
                linecolor='rgb(204, 204, 204)',
                linewidth=2
            ),
            yaxis=dict(
                tickfont=dict(color='white'),
                showgrid=True,
                gridcolor='rgba(128,128,128,0.2)',
                gridwidth=1,
                zeroline=False,
                linecolor='rgb(204, 204, 204)',
                linewidth=2
            ),
            plot_bgcolor='black',
            paper_bgcolor='black',
            font=dict(color='white')
        )
        return dcc.Graph(figure=fig)

    empty_fig = go.Figure()
    empty_fig.update_layout(
        title=' ',
        xaxis_title='TimeStamp[Sec]',
        yaxis_title='Amplitude',
        plot_bgcolor='black',
        paper_bgcolor='black',
        font=dict(color='white')
    )

    return dcc.Graph(figure=empty_fig)


if __name__ == '__main__':
    app.run_server(debug=False, host='0.0.0.0', port=8000)
