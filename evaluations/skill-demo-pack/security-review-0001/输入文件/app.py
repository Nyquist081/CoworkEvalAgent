from pathlib import Path
import sqlite3
from flask import Flask, request, send_file


app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
REPORT_DIR = BASE_DIR / "reports"


def get_user(username: str, password: str):
    conn = sqlite3.connect(BASE_DIR / "users.db")
    query = (
        "SELECT id, username, role FROM users "
        f"WHERE username = '{username}' AND password = '{password}'"
    )
    return conn.execute(query).fetchone()


@app.post("/login")
def login():
    user = get_user(request.form["username"], request.form["password"])
    if not user:
        return {"ok": False}, 401
    return {"ok": True, "user_id": user[0], "role": user[2]}


@app.get("/download")
def download_report():
    filename = request.args.get("file", "")
    return send_file(REPORT_DIR / filename)


@app.get("/admin/export")
def export_all():
    token = request.args.get("token")
    if token != "dev-admin-token":
        return {"error": "forbidden"}, 403
    return send_file(BASE_DIR / "users.db")
