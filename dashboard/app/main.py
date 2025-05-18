import time

import fastapi
import prometheus_api_client
from app import config_schema
from fastapi import responses, staticfiles, templating

QUERIES = config_schema.load_queries_config().queries


# Base FastAPI application
app = fastapi.FastAPI(
    title='Home Lab Dashboard',
    description='Prometheus-powered dashboard for system stats, containers, and more.',
)
templates = templating.Jinja2Templates(directory='app/templates')
app.mount('/assets', staticfiles.StaticFiles(directory='app/assets'), name='assets')

# Prometheus connection
PROM_URL = 'http://prometheus:9090'
prom = prometheus_api_client.PrometheusConnect(url=PROM_URL, disable_ssl=True)  # type: ignore[reportArgumentType]


# Main site definition
@app.get('/', response_class=responses.HTMLResponse)
def home(request: fastapi.Request):
    return templates.TemplateResponse(
        name='index.html.jinja2',
        context=dict(
            request=request,
            widgets=[q for q in QUERIES if 'widget' in q.types],
            charts=[q for q in QUERIES if 'chart' in q.types],
        ),
    )


# Dynamically register /widgets/<id>
for q in QUERIES:
    if 'widget' not in q.types:
        continue

    @app.get(f'/widgets/{q.name}', response_class=responses.HTMLResponse)
    def widget_route(
        request: fastapi.Request,
        _q: config_schema.Query = q,
    ) -> responses.HTMLResponse:
        result = prom.custom_query(query=_q.query)  # type: ignore[reportArgumentType]
        return render_widget(_q, request, result)


# Dynamically register /api/<id>-timeseries
for q in QUERIES:
    if 'chart' not in q.types:
        continue

    @app.get(f'/api/{q.name}-timeseries')
    def timeseries_route(_q: config_schema.Query = q) -> dict[str, float]:
        result = prom.custom_query(query=_q.query)  # type: ignore[reportArgumentType]
        value = float(result[0]['value'][1]) if result else 0.0
        return {'timestamp': time.time(), 'value': value}


def render_widget(
    query: config_schema.Query,
    request: fastapi.Request,
    result: list[dict[str, str]],
) -> fastapi.responses.HTMLResponse:
    value = round(float(result[0]['value'][1]), 2) if result else 'N/A'
    return templates.TemplateResponse(
        name='widget.html.jinja2',
        context=dict(query=query, request=request, value=value),
    )
