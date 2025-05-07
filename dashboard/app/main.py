import time

import fastapi
import prometheus_api_client
from fastapi import responses, staticfiles, templating


def render_widget(
    request: fastapi.Request,
    label: str,
    result: list,
    *,
    unit: str = '%',
    id: str = None,
) -> fastapi.responses.HTMLResponse:
    value = round(float(result[0]['value'][1]), 2) if result else 'N/A'
    return templates.TemplateResponse(
        'widget.html',
        {
            'request': request,
            'label': label,
            'value': value,
            'unit': unit,
            'id': id or label.lower().replace(' ', '-'),
        },
    )


PROM_URL = 'http://prometheus:9090'
prom = prometheus_api_client.PrometheusConnect(url=PROM_URL, disable_ssl=True)

app = fastapi.FastAPI()
templates = templating.Jinja2Templates(directory='app/templates')
app.mount('/static', staticfiles.StaticFiles(directory='app/static'), name='static')


@app.get('/', response_class=responses.HTMLResponse)
def home(request: fastapi.Request):
    return templates.TemplateResponse('index.html', {'request': request})


@app.get('/widgets/cpu', response_class=fastapi.responses.HTMLResponse)
def get_cpu(request: fastapi.Request):
    result = prom.custom_query(
        query='100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)'  # noqa: E501
    )
    return render_widget(request, 'CPU Usage', result)


@app.get('/widgets/memory', response_class=fastapi.responses.HTMLResponse)
def get_memory(request: fastapi.Request):
    result = prom.custom_query(
        query='(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100'  # noqa: E501
    )
    return render_widget(request, 'Memory Usage', result)


@app.get('/widgets/disk', response_class=fastapi.responses.HTMLResponse)
def get_disk(request: fastapi.Request):
    result = prom.custom_query(
        query='100 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} * 100)'  # noqa: E501
    )
    return render_widget(request, 'Disk Usage', result)


@app.get('/widgets/network-rx', response_class=fastapi.responses.HTMLResponse)
def get_network_rx(request: fastapi.Request):
    result = prom.custom_query(
        query='rate(node_network_receive_bytes_total{device="eth0"}[1m])'
    )
    return render_widget(request, 'Network RX', result, unit=' bytes/sec')


@app.get('/api/cpu-timeseries')
def get_cpu_timeseries():
    result = prom.custom_query(
        query='100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)'  # noqa: E501
    )
    if result:
        value = float(result[0]['value'][1])
    else:
        value = 0.0
    return {'timestamp': time.time(), 'value': value}


@app.get('/api/memory-timeseries')
def get_memory_timeseries():
    result = prom.custom_query(
        query='(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100'  # noqa: E501
    )
    if result:
        value = float(result[0]['value'][1])
    else:
        value = 0.0
    return {'timestamp': time.time(), 'value': value}
