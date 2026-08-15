from flask import Flask, request, redirect, session, render_template_string
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


init_db()


HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Demo Wallet</title>

    <style>
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #111827;
            color: white;
        }

        .container {
            max-width: 430px;
            margin: 40px auto;
            padding: 20px;
        }

        .card {
            background: #1f2937;
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 20px;
        }

        h1, h2 {
            text-align: center;
        }

        input {
            width: 100%;
            box-sizing: border-box;
            padding: 14px;
            margin: 8px 0;
            border: none;
            border-radius: 8px;
            font-size: 16px;
        }

        button {
            width: 100%;
            padding: 14px;
            margin-top: 10px;
            border: none;
            border-radius: 8px;
            background: #22c55e;
            color: white;
            font-size: 16px;
            font-weight: bold;
        }

        .btn {
            display: block;
            text-align: center;
            padding: 14px;
            margin-top: 10px;
            border-radius: 8px;
            background: #2563eb;
            color: white;
            text-decoration: none;
        }

        .danger {
            background: #dc2626;
        }

        .balance {
            font-size: 32px;
            text-align: center;
            color: #22c55e;
            font-weight: bold;
        }

        .error {
            background: #7f1d1d;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 10px;
        }

        .success {
            background: #166534;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 10px;
        }
    </style>
</head>

<body>

<div class="container">

    {% if message %}
        <div class="{{ message_type }}">
            {{ message }}
        </div>
    {% endif %}

    {{ content|safe }}

</div>

</body>
</html>
"""


@app.route("/")
def home():
    if "user_id" in session:
        return redirect("/dashboard")

    content = """
    <div class="card">
        <h1>💰 Demo Wallet</h1>
        <p style="text-align:center;">
            Deposit • Balance • Withdraw
        </p>

        <a class="btn" href="/register">Register</a>
        <a class="btn" href="/login">Login</a>
    </div>
    """

    return render_template_string(
        HTML,
        content=content,
        message=None,
        message_type="error"
    )


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template_string(
                HTML,
                content=register_form(),
                message="Username and password are required.",
                message_type="error"
            )

        password_hash = generate_password_hash(password)

        conn = get_db()

        try:
            conn.execute(
                "INSERT INTO users (username, password, balance) VALUES (?, ?, 0)",
                (username, password_hash)
            )

            conn.commit()
            conn.close()

            return redirect("/login")

        except sqlite3.IntegrityError:
            conn.close()

            return render_template_string(
                HTML,
                content=register_form(),
                message="Username already exists.",
                message_type="error"
            )

    return render_template_string(
        HTML,
        content=register_form(),
        message=None,
        message_type="error"
    )


def register_form():
    return """
    <div class="card">
        <h2>Create Account</h2>

        <form method="POST">

            <input
                type="text"
                name="username"
                placeholder="Username"
                required
            >

            <input
                type="password"
                name="password"
                placeholder="Password"
                required
            >

            <button type="submit">
                Register
            </button>

        </form>

        <a class="btn" href="/login">
            Already have an account? Login
        </a>

        <a class="btn danger" href="/">
            Home
        </a>
    </div>
    """


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):

            session["user_id"] = user["id"]
            session["username"] = user["username"]

            return redirect("/dashboard")

        return render_template_string(
            HTML,
            content=login_form(),
            message="Invalid username or password.",
            message_type="error"
        )

    return render_template_string(
        HTML,
        content=login_form(),
        message=None,
        message_type="error"
    )


def login_form():
    return """
    <div class="card">
        <h2>Login</h2>

        <form method="POST">

            <input
                type="text"
                name="username"
                placeholder="Username"
                required
            >

            <input
                type="password"
                name="password"
                placeholder="Password"
                required
            >

            <button type="submit">
                Login
            </button>

        </form>

        <a class="btn" href="/register">
            Create Account
        </a>

        <a class="btn danger" href="/">
            Home
        </a>
    </div>
    """


@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    conn.close()

    if not user:
        session.clear()
        return redirect("/login")

    content = f"""
    <div class="card">

        <h1>Dashboard</h1>

        <p style="text-align:center;">
            Welcome, <b>{user["username"]}</b>
        </p>

        <div class="balance">
            ${user["balance"]:.2f}
        </div>

        <p style="text-align:center;">
            Current Balance
        </p>

        <a class="btn" href="/deposit">
            💵 Deposit
        </a>

        <a class="btn" href="/withdraw">
            💸 Withdraw
        </a>

        <a class="btn danger" href="/logout">
            Logout
        </a>

    </div>
    """

    return render_template_string(
        HTML,
        content=content,
        message=None,
        message_type="error"
    )


@app.route("/deposit", methods=["GET", "POST"])
def deposit():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            amount = 0

        if amount <= 0:
            return render_template_string(
                HTML,
                content=deposit_form(),
                message="Enter a valid amount.",
                message_type="error"
            )

        conn = get_db()

        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?",
            (amount, session["user_id"])
        )

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template_string(
        HTML,
        content=deposit_form(),
        message=None,
        message_type="error"
    )


def deposit_form():
    return """
    <div class="card">
        <h2>Deposit</h2>

        <p style="text-align:center;">
            Demo deposit
        </p>

        <form method="POST">

            <input
                type="number"
                name="amount"
                step="0.01"
                min="0.01"
                placeholder="Amount"
                required
            >

            <button type="submit">
                Add Balance
            </button>

        </form>

        <a class="btn" href="/dashboard">
            Back to Dashboard
        </a>
    </div>
    """


@app.route("/withdraw", methods=["GET", "POST"])
def withdraw():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            amount = 0

        if amount <= 0:
            return render_template_string(
                HTML,
                content=withdraw_form(),
                message="Enter a valid amount.",
                message_type="error"
            )

        conn = get_db()

        user = conn.execute(
            "SELECT balance FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()

        if not user or user["balance"] < amount:
            conn.close()

            return render_template_string(
                HTML,
                content=withdraw_form(),
                message="Insufficient balance.",
                message_type="error"
            )

        conn.execute(
            "UPDATE users SET balance = balance - ? WHERE id = ?",
            (amount, session["user_id"])
        )

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template_string(
        HTML,
        content=withdraw_form(),
        message=None,
        message_type="error"
    )


def withdraw_form():
    return """
    <div class="card">
        <h2>Withdraw</h2>

        <p style="text-align:center;">
            Demo withdrawal
        </p>

        <form method="POST">

            <input
                type="number"
                name="amount"
                step="0.01"
                min="0.01"
                placeholder="Amount"
                required
            >

            <button type="submit">
                Withdraw
            </button>

        </form>

        <a class="btn" href="/dashboard">
            Back to Dashboard
        </a>
    </div>
    """


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


@app.route("/health")
def health():
    return "OK"


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )
