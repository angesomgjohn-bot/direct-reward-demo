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
        <input name="password" type="password" placeholder="Password" required>
        <button type="submit">Register</button>
    </form>

    <p>Already have an account?
        <a href="/login">Login</a>
    </p>
</div>

{% elif page == "login" %}

<div class="card">
    <h2>Login</h2>

    {% if error %}
        <p class="error">{{ error }}</p>
    {% endif %}

    <form method="POST">
        <input name="username" placeholder="Username" required>
        <input name="password" type="password" placeholder="Password" required>
        <button type="submit">Login</button>
    </form>

    <p>No account?
        <a href="/register">Register</a>
    </p>
</div>

{% elif page == "dashboard" %}

<div class="card">
    <h2>Welcome, {{ username }}</h2>

    <p>Your demo balance:</p>
    <div class="balance">{{ "%.2f"|format(balance) }}</div>
</div>

<div class="card">
    <h3>Deposit Demo</h3>

    <form method="POST" action="/deposit">
        <input
            name="amount"
            type="number"
            step="0.01"
            min="1"
            placeholder="Amount"
            required
        >
        <button type="submit">Deposit</button>
    </form>
</div>

<div class="card">
    <h3>Withdraw Demo</h3>

    <form method="POST" action="/withdraw">
        <input
            name="amount"
            type="number"
            step="0.01"
            min="1"
            placeholder="Amount"
            required
        >
        <button type="submit">Withdraw</button>
    </form>
</div>

<div class="card">
    <h3>Game</h3>
    <p>This is a demo game area.</p>
    <a href="/game">Open Game</a>
</div>

<div class="card">
    <a href="/logout">Logout</a>
</div>

{% elif page == "game" %}

<div class="card">
    <h2>Demo Game</h2>
    <p>This game is for testing only.</p>

    <p>Your balance:</p>
    <div class="balance">{{ "%.2f"|format(balance) }}</div>

    <form method="POST" action="/game">
        <button type="submit">Play Demo Round</button>
    </form>

    <br>
    <a href="/dashboard">Back to Dashboard</a>
</div>

{% endif %}

</div>
</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(HTML, page="home")


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if len(username) < 3:
            error = "Username must be at least 3 characters."
            return render_template_string(
                HTML, page="register", error=error
            )

        if len(password) < 4:
            error = "Password must be at least 4 characters."
            return render_template_string(
                HTML, page="register", error=error
            )

        conn = get_db()

        try:
            conn.execute(
                "INSERT INTO users (username, password, balance) VALUES (?, ?, ?)",
                (
                    username,
                    generate_password_hash(password),
                    0
                )
            )

            conn.commit()
            conn.close()

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            conn.close()
            error = "Username already exists."

    return render_template_string(
        HTML,
        page="register",
        error=error
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]

            return redirect(url_for("dashboard"))

        error = "Invalid username or password."

    return render_template_string(
        HTML,
        page="login",
        error=error
    )


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    conn.close()

    if not user:
        session.clear()
        return redirect(url_for("login"))

    return render_template_string(
        HTML,
        page="dashboard",
        username=user["username"],
        balance=user["balance"]
    )


@app.route("/deposit", methods=["POST"])
def deposit():
    if "user_id" not in session:
        return redirect(url_for("login"))

    try:
        amount = float(request.form["amount"])
    except ValueError:
        return redirect(url_for("dashboard"))

    if amount <= 0:
        return redirect(url_for("dashboard"))

    conn = get_db()

    conn.execute(
        "UPDATE users SET balance = balance + ? WHERE id = ?",
        (amount, session["user_id"])
    )

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


@app.route("/withdraw", methods=["POST"])
def withdraw():
    if "user_id" not in session:
        return redirect(url_for("login"))

    try:
        amount = float(request.form["amount"])
    except ValueError:
        return redirect(url_for("dashboard"))

    if amount <= 0:
        return redirect(url_for("dashboard"))

    conn = get_db()

    user = conn.execute(
        "SELECT balance FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if user and user["balance"] >= amount:
        conn.execute(
            "UPDATE users SET balance = balance - ? WHERE id = ?",
            (amount, session["user_id"])
        )
        conn.commit()

    conn.close()

    return redirect(url_for("dashboard"))


@app.route("/game", methods=["GET", "POST"])
def game():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    conn.close()

    return render_template_string(
        HTML,
        page="game",
        balance=user["balance"]
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    init_db()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
            )
