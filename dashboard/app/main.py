import time

import fastapi
import psutil
from fastapi import responses, staticfiles, templating

app = fastapi.FastAPI()
templates = templating.Jinja2Templates(directory='app/templates')
app.mount('/static', staticfiles.StaticFiles(directory='app/static'), name='static')


@app.get('/', response_class=responses.HTMLResponse)
def home(request: fastapi.Request):
    return templates.TemplateResponse('index.html', {'request': request})


@app.get('/widgets/uptime', response_class=responses.HTMLResponse)
def get_uptime(request: fastapi.Request):
    uptime_seconds = time.time() - psutil.boot_time()
    return templates.TemplateResponse(
        'widgets/uptime.html', {'request': request, 'uptime': uptime_seconds}
    )


@app.get('/widgets/cpu', response_class=responses.HTMLResponse)
def get_cpu(request: fastapi.Request):
    cpu = psutil.cpu_percent()
    return templates.TemplateResponse(
        'widgets/cpu.html', {'request': request, 'cpu': cpu}
    )


@app.get('/widgets/memory', response_class=responses.HTMLResponse)
def get_memory(request: fastapi.Request):
    mem = psutil.virtual_memory().percent
    return templates.TemplateResponse(
        'widgets/memory.html', {'request': request, 'memory': mem}
    )
