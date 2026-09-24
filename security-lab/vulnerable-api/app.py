import os
import subprocess

import psycopg2
from fastapi import FastAPI, HTTPException, Request

app = FastAPI(title="vulnerable-api", debug=True)

DB_DSN = os.environ.get(
    "LAB_DATABASE_URL",
    "host=test-db port=5432 dbname=labdb user=lab password=lab123",
)

ADMIN_TOKEN = "admin-secret-token"
DEFAULT_CREDENTIALS = {"username": "admin", "password": "admin123"}


def _db():
    return psycopg2.connect(DB_DSN)


def _require_token(request: Request) -> bool:
    return request.headers.get("X-Auth-Token") == ADMIN_TOKEN


@app.get("/")
def index():
    return {"service": "vulnerable-api", "docs": "/docs"}


@app.post("/api/login")
def login(username: str, password: str):
    if username == DEFAULT_CREDENTIALS["username"] and password == DEFAULT_CREDENTIALS["password"]:
        return {"token": ADMIN_TOKEN, "user": username}
    raise HTTPException(status_code=401, detail="incorrect login or password")


@app.get("/api/users")
def list_users(name: str):
    conn = _db()
    cur = conn.cursor()
    cur.execute(f"SELECT id, username, email, role FROM users WHERE username LIKE '%{name}%'")
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "username": r[1], "email": r[2], "role": r[3]} for r in rows]


@app.get("/api/user/{user_id}")
def get_user(user_id: int):
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, password, email, role FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")
    return {"id": row[0], "username": row[1], "password": row[2], "email": row[3], "role": row[4]}


@app.post("/api/ping")
def ping(host: str):
    result = subprocess.run(f"ping -c 1 {host}", shell=True, capture_output=True, text=True)
    return {"host": host, "output": result.stdout + result.stderr}


@app.get("/api/config")
def config():
    return {
        "database_url": DB_DSN,
        "admin_token": ADMIN_TOKEN,
        "smtp": {"host": "smtp.lab.local", "password": "mailer-weak-pass"},
        "api_key": "sk-live-cyberops-0000-1111",
    }


@app.post("/api/orders")
def create_order(request: Request, product: str, amount: float):
    if not _require_token(request):
        raise HTTPException(status_code=401, detail="invalid token")
    conn = _db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (user_id, product, amount, status) VALUES (1, %s, %s, 'pending')",
        (product, amount),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "product": product, "amount": amount}