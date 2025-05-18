import json
import pathlib
import sqlite3

import fastapi
from fastapi import requests, responses, staticfiles, templating

app = fastapi.FastAPI(
    title='Mortgage Calculator',
    description='SQlite-backed calculator application',
)
templates = templating.Jinja2Templates(directory='app/templates')
app.mount('/assets', staticfiles.StaticFiles(directory='app/assets'), name='assets')

db_path = pathlib.Path('/data/calculations.db')

DB_INIT_SQL = """
    CREATE TABLE IF NOT EXISTS calculations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        data TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """


def init_db():
    """Create and initialize database if not already"""
    with sqlite3.connect(db_path) as conn:
        conn.execute(DB_INIT_SQL)


@app.get('/', response_class=responses.HTMLResponse)
def read_root(request: requests.Request):
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            'SELECT id, name FROM calculations ORDER BY created_at DESC'
        ).fetchall()
    return templates.TemplateResponse(
        'index.html.jinja2', {'request': request, 'saved_calcs': rows}
    )


@app.post('/save')
def save_calc(name: str = fastapi.Form(...), data: str = fastapi.Form(...)):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'INSERT INTO calculations (name, data) VALUES (?, ?)', (name, data)
        )
    return responses.RedirectResponse('/', status_code=303)


@app.get('/calc/{calc_id}', response_class=responses.HTMLResponse)
def load_calc(request: requests.Request, calc_id: int):
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            'SELECT id, name, data FROM calculations WHERE id = ?', (calc_id,)
        ).fetchone()
        rows = conn.execute(
            'SELECT id, name FROM calculations ORDER BY created_at DESC'
        ).fetchall()
    data: dict[str, str] = json.loads(row[2]) if row else {}
    return templates.TemplateResponse(
        'index.html.jinja2',
        {'request': request, 'saved_calcs': rows, 'loaded': data, 'name': row[1]},
    )


init_db()


@app.get('/calc/{id}')
def get_calc(id: int):
    # Load and return calculation
    ...
