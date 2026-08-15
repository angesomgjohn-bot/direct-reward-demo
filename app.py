from flask import Flask, request, redirect, url_for, session, render_template_string
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

DB = "database.db"


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance REAL DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Demo Wallet</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #111827;
            color: white;
            margin: 0;
        }

        .container {
            max-width: 430px;
            margin: 40px auto;
            padding: 20px;
        }

        .card {
            background: #1f2937;
            padding: 22px;
            border-radius: 15px;
            margin-bottom: 15px;
        }

        input {
            width: 100%;
            box-sizing: border-box;
            padding: 13px;
            margin: 8px 0;
            border-radius: 8px;
            border: none;
        }

        button {
            width: 100%;
            padding: 13px;
            border: none;
            border-radius: 8px;
            background: #22c55e;
            color: white;
            font-size: 16px;
            margin-top: 8px;
        }

        a {
            color: #60a5fa;
            text-decoration: none;
        }

        .balance {
            font-size: 32px;
            font-weight: bold;
            color: #22c55e;
        }

        .error {
            color: #f87171;
        }

        .success {
            color: #4ade80;
        }
    </style>
</head>
<body>
<div class="container">

{% if page == "home" %}

<div class="card">
    <h1>Demo Wallet</h1>
    <p>Register or login to continue.</p>
    <a href="/register">Register</a><br><br>
    <a href="/login">Login</a>
</div>

{% elif page == "register" %}

<div class="card">
    <h2>Create Account</h2>

    {% if error %}
        <p class="error">{{ error }}</p>
    {% endif %}

    <form method="POST">
        <input name="username" placeholder="Username" required>
        <input name="
