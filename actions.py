"""Safe action tools for the CS4680 agent. No arbitrary shell execution."""
from __future__ import annotations
import ast
import json
import math
import operator
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import requests

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'agent_data'
WORKSPACE = DATA_DIR / 'workspace'
DB_PATH = DATA_DIR / 'agent.db'
LOG_PATH = DATA_DIR / 'audit.jsonl'
MAX_CONTENT = 12000
ALLOWED_ACTIONS = {
    'list_files', 'write_file', 'read_file', 'delete_file',
    'add_note', 'list_notes', 'search_notes', 'calculate', 'weather'
}


def setup() -> None:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.execute('CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL)')


def audit(action: str, args: dict, outcome: str, detail: str) -> None:
    setup()
    # Don't put note bodies, file contents, or API secrets in the audit trail.
    safe_args = {k: ('[content omitted]' if k in {'content', 'body'} else str(v)[:180]) for k, v in args.items()}
    item = {'timestamp': datetime.now(timezone.utc).isoformat(), 'action': action, 'args': safe_args, 'outcome': outcome, 'detail': detail[:500]}
    with LOG_PATH.open('a', encoding='utf-8') as f:
        f.write(json.dumps(item) + '\n')


def safe_path(name: str) -> Path:
    if not isinstance(name, str) or not name.strip() or len(name) > 180:
        raise ValueError('A valid filename is required (up to 180 characters).')
    if '\\' in name or '\x00' in name or Path(name).is_absolute():
        raise ValueError('Only relative paths inside the workspace are allowed.')
    p = (WORKSPACE / name).resolve()
    if not p.is_relative_to(WORKSPACE.resolve()) or p == WORKSPACE.resolve():
        raise ValueError('This path is outside the permitted workspace.')
    if p.suffix.lower() not in {'.txt', '.md', '.csv', '.json'}:
        raise ValueError('Only .txt, .md, .csv, and .json files are supported.')
    return p


BINARY_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def safe_calculate(expression: str) -> float | int:
    if not isinstance(expression, str) or len(expression) > 100:
        raise ValueError('Expression must be at most 100 characters.')
    node = ast.parse(expression, mode='eval')

    def visit(n: ast.AST, depth: int = 0) -> float | int:
        if depth > 16:
            raise ValueError('Expression is too complex.')
        if isinstance(n, ast.Expression):
            return visit(n.body, depth + 1)
        if isinstance(n, ast.Constant) and type(n.value) in {int, float}:
            if abs(n.value) > 1e12:
                raise ValueError('Number too large.')
            return n.value
        if isinstance(n, ast.UnaryOp) and type(n.op) in UNARY_OPS:
            return UNARY_OPS[type(n.op)](visit(n.operand, depth + 1))
        if isinstance(n, ast.BinOp) and type(n.op) in BINARY_OPS:
            a, b = visit(n.left, depth + 1), visit(n.right, depth + 1)
            if isinstance(n.op, ast.Pow) and (abs(b) > 12 or abs(a) > 1e6):
                raise ValueError('Exponentiation limit exceeded.')
            answer = BINARY_OPS[type(n.op)](a, b)
            if not math.isfinite(answer) or abs(answer) > 1e15:
                raise ValueError('Result too large.')
            return answer
        raise ValueError('Only numbers and arithmetic operators are supported.')

    return visit(node)


def get_weather(city: str) -> str:
    if not isinstance(city, str) or not 1 <= len(city.strip()) <= 80:
        raise ValueError('Enter a city name.')
    geo = requests.get('https://geocoding-api.open-meteo.com/v1/search', params={'name': city, 'count': 1}, timeout=8)
    geo.raise_for_status()
    results = geo.json().get('results') or []
    if not results:
        raise ValueError('City not found.')
    loc = results[0]
    res = requests.get('https://api.open-meteo.com/v1/forecast', params={'latitude': loc['latitude'], 'longitude': loc['longitude'], 'current': 'temperature_2m,relative_humidity_2m,wind_speed_10m', 'temperature_unit': 'fahrenheit', 'wind_speed_unit': 'mph', 'timezone': 'auto'}, timeout=8)
    res.raise_for_status()
    w = res.json()['current']
    return f"{loc['name']}, {loc.get('country', '')}: {w['temperature_2m']} °F, humidity {w['relative_humidity_2m']}%, wind {w['wind_speed_10m']} mph (as of {w['time']} local time)."


def execute(action: str, args: dict[str, Any], *, confirmed_delete: bool = False) -> str:
    setup()
    try:
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f'Unsupported action: {action}')
        if not isinstance(args, dict):
            raise ValueError('Action arguments must be an object.')
        if action == 'list_files':
            items = sorted(str(p.relative_to(WORKSPACE)) for p in WORKSPACE.rglob('*') if p.is_file() and not p.is_symlink())
            result = 'Workspace files: ' + (', '.join(items[:100]) if items else '(none)')
        elif action == 'write_file':
            p = safe_path(args.get('filename', ''))
            content = args.get('content', '')
            if not isinstance(content, str) or len(content) > MAX_CONTENT:
                raise ValueError('File content must be text and at most 12,000 characters.')
            if p.exists():
                raise ValueError('File already exists. Choose another filename (overwriting is disabled).')
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
            result = f'Created {p.relative_to(WORKSPACE)} ({len(content)} characters).'
        elif action == 'read_file':
            p = safe_path(args.get('filename', ''))
            if not p.is_file():
                raise ValueError('File not found.')
            if p.stat().st_size > 50000:
                raise ValueError('File is too large to display.')
            result = f'Contents of {p.relative_to(WORKSPACE)}:\n{p.read_text(encoding="utf-8")}'
        elif action == 'delete_file':
            if not confirmed_delete:
                raise PermissionError('Deletion requires explicit confirmation in the UI.')
            p = safe_path(args.get('filename', ''))
            if not p.is_file():
                raise ValueError('File not found.')
            p.unlink()
            result = f'Deleted {p.relative_to(WORKSPACE)}.'
        elif action == 'add_note':
            title, body = args.get('title', ''), args.get('body', '')
            if not isinstance(title, str) or not isinstance(body, str) or not title.strip() or len(title) > 150 or len(body) > MAX_CONTENT:
                raise ValueError('Note needs a title (1-150 chars) and a body (at most 12,000 chars).')
            with sqlite3.connect(DB_PATH) as db:
                cursor = db.execute('INSERT INTO notes (title,body,created_at) VALUES (?,?,?)', (title, body, datetime.now(timezone.utc).isoformat()))
                note_id = cursor.lastrowid
            result = f'Saved note #{note_id}: {title}'
        elif action == 'list_notes':
            with sqlite3.connect(DB_PATH) as db:
                rows = db.execute('SELECT id,title,created_at FROM notes ORDER BY id DESC LIMIT 30').fetchall()
            result = 'Notes:\n' + ('\n'.join(f'#{id}: {title} ({created})' for id, title, created in rows) if rows else '(none)')
        elif action == 'search_notes':
            keyword = args.get('keyword', '')
            if not isinstance(keyword, str) or not keyword.strip() or len(keyword) > 100:
                raise ValueError('Search keyword must be 1-100 characters.')
            with sqlite3.connect(DB_PATH) as db:
                rows = db.execute('SELECT id,title,body FROM notes WHERE title LIKE ? OR body LIKE ? ORDER BY id DESC LIMIT 10', (f'%{keyword}%', f'%{keyword}%')).fetchall()
            result = 'Matching notes:\n' + ('\n'.join(f'#{id} {title}: {body[:500]}' for id, title, body in rows) if rows else '(none)')
        elif action == 'calculate':
            expression = args.get('expression', '')
            result = f'{expression} = {safe_calculate(expression)}'
        elif action == 'weather':
            result = get_weather(args.get('city', ''))
        audit(action, args, 'success', result[:180])
        return result
    except Exception as exc:
        message = f'{type(exc).__name__}: {exc}'
        audit(action, args if isinstance(args, dict) else {}, 'error', message)
        return f'ERROR: {message}'
