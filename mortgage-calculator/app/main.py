import fastapi
from fastapi import responses

app = fastapi.FastAPI(
    title='Mortgage Calculator',
    description='SQlite-backed calculator application',
)


def render_homepage() -> None: ...


@app.get('/')
def index():
    return responses.HTMLResponse(render_homepage())


@app.post('/save')
def save_calc(name: str, data: dict):
    # Store named calculation in DB
    ...


@app.get('/calc/{id}')
def get_calc(id: int):
    # Load and return calculation
    ...
