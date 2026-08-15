from flask import Flask, request, redirect, session, render_template_string
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "demo-wallet-secret")

DB = "database.db"


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance REAL DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


HTML = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Demo Wallet</title>

<style>
*{box-sizing:border-box}
body{
    margin:0;
    font-family:Arial,sans-serif;
    background:#101827;
    color:white;
}
.container{
    max-width:430px;
    margin:auto;
    padding:22px;
}
.card{
    background:#202b3d;
    border-radius:24px;
    padding:25px;
    margin-top:25px;
}
h1{
    text-align:center;
    font-size:38px;
    margin:10px 0;
}
h2{
    text-align:center;
}
input{
    width:100%;
    padding:16px;
    margin:8px 0;
    border:0;
    border-radius:12px;
    font-size:16px;
}
button,.btn{
    width:100%;
    padding:16px;
    margin-top:10px;
    border:0;
    border-radius:12px;
    background:#2864e8;
    color:white;
    font-size:17px;
    text-decoration:none;
    display:block;
    text-align:center;
}
.red{background:#e5252a}
.green{color:#20d45b}
.balance{
    text-align:center;
    font-size:48px;
    font-weight:bold;
    color:#20d45b;
    margin:15px 0;
}
.small{
    text-align:center;
    color:#bbb;
}
.nav{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:10px;
    margin-top:20px;
}
.item{
    background:#172235;
    padding:18px;
    border-radius:15px;
    text-align:center;
}
.tx{
    background:#172235;
    padding:13px;
    border-radius:12px;
    margin:8px 0;
}
.error{
    background:#8d2020;
    padding:12px;
    border-radius:10px;
    text-align:center;
}
</style>
</head>

<body>
<div class="container">

{% if page == "home" %}

<div class="card">
    <h1>💰 Demo Wallet</h1>
    <p class="small">Deposit • Balance • Withdraw</p>

    <a class="btn" href="/register">Register</a>
    <a class="btn" href="/login">Login</a>
</div>

{% elif page == "register" %}

<div class="card">
<h2>Create Account</h2>

{% if error %}
<div class="error">{{error}}</div>
{% endif %}

<form method="post">
<input name="username" placeholder="Username" required>
<input type="password" name="password" placeholder="Password" required>
<input type="password" name="confirm" placeholder="Confirm Password" required>
<button>Create Account</button>
</form>

<a class="btn" href="/login">Already have an account? Login</a>
<a class="btn red" href="/">Back</a>
</div>

{% elif page == "login" %}

<div class="card">
<h2>Login</h2>

{% if error %}
<div class="error">{{error}}</div>
{% endif %}

<form method="post">
<input name="username" placeholder="Username" required>
<input type="password" name="password" placeholder="Password" required>
<button>Login</button>
</form>

<a class="btn" href="/register">Create Account</a>
<a class="btn red" href="/">Back</a>
</div>

{% elif page == "dashboard" %}

<div class="card">
<h2>Dashboard</h2>

<p class="small">
Welcome, <b>{{user["username"]}}</b>
</p>

<div class="balance">
$%.2f
</div>

<p class="small">Current Balance</p>

<div class="nav">
<a class="btn" href="/deposit">💵 Deposit</a>
<a class="btn" href="/withdraw">💸 Withdraw</a>
<a class="btn" href="/transactions">📊 History</a>
<a class="btn" href="/profile">👤 My</a>
</div>

<a class="btn red" href="/logout">Logout</a>
</div>

{% elif page == "deposit" %}

<div class="card">
<h2>💵 Deposit</h2>

<p class="small">
Demo mode — no real payment is processed.
</p>

<form method="post">
<input type="number" name="amount"
       placeholder="Enter amount"
       min="1" step="0.01" required>
<button>Add Demo Balance</button>
</form>

<a class="btn red" href="/dashboard">Back</a>
</div>

{% elif page == "withdraw" %}

<div class="card">
<h2>💸 Withdraw</h2>

<p class="small">
Available: $%.2f
</p>

<form method="post">
<input type="number" name="amount"
       placeholder="Enter amount"
       min="1" step="0.01" required>
<button>Withdraw</button>
</form>

<a class="btn red" href="/dashboard">Back</a>
</div>

{% elif page == "transactions" %}

<div class="card">
<h2>📊 Transactions</h2>

{% for tx in transactions %}
<div class="tx">
<b>{{tx["type"]}}</b><br>
$%.2f<br>
<small>{{tx["created_at"]}}</small>
</div>
{% else %}
<p class="small">No transactions yet.</p>
{% endfor %}

<a class="btn red" href="/dashboard">Back</a>
</div>

{% elif page == "profile" %}

<div class="card">
<h2>👤 My Profile</h2>

<div class="item">
Username<br>
<b>{{user["username"]}}</b>
</div>

<div class="item" style="margin-top:10px">
Balance<br>
<b class="green">$%.2f</b>
</div>

<a class="btn red" href="/dashboard">Back</a>
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
        confirm = request.form["confirm"]

        if password != confirm:
            error = "Passwords do not match."
        elif len(password) < 4:
            error = "Password must be at least 4 characters."
        else:
            try:
                conn = db()
                conn.execute(
                    "INSERT INTO users(username,password) VALUES(?,?)",
                    (username, generate_password_hash(password))
                )
                conn.commit()
                conn.close()
                return redirect("/login")
            except sqlite3.IntegrityError:
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

        conn = db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect("/dashboard")

        error = "Invalid username or password."

    return render_template_string(
        HTML,
        page="login",
        error=error
    )


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    conn = db()
    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()
    conn.close()

    return render_template_string(
        HTML,
        page="dashboard",
        user=user
    )


@app.route("/deposit", methods=["GET", "POST"])
def deposit():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        amount = float(request.form["amount"])

        if amount > 0:
            conn = db()

            conn.execute(
                "UPDATE users SET balance=balance+? WHERE id=?",
                (amount, session["user_id"])
            )

            conn.execute(
                "INSERT INTO transactions(user_id,type,amount) VALUES(?,?,?)",
                (session["user_id"], "DEPOSIT", amount)
            )

            conn.commit()
            conn.close()

            return redirect("/dashboard")

    return render_template_string(
        HTML,
        page="deposit"
    )


@app.route("/withdraw", methods=["GET", "POST"])
def withdraw():
    if "user_id" not in session:
        return redirect("/login")

    conn = db()

    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    if request.method == "POST":
        amount = float(request.form["amount"])

        if amount > 0 and amount <= user["balance"]:

            conn.execute(
                "UPDATE users SET balance=balance-? WHERE id=?",
                (amount, session["user_id"])
            )

            conn.execute(
                "INSERT INTO transactions(user_id,type,amount) VALUES(?,?,?)",
                (session["user_id"], "WITHDRAW", amount)
            )

            conn.commit()
            conn.close()

            return redirect("/dashboard")

    conn.close()

    return render_template_string(
        HTML,
        page="withdraw",
        user=user
    )


@app.route("/transactions")
def transactions():
    if "user_id" not in session:
        return redirect("/login")

    conn = db()

    transactions = conn.execute(
        "SELECT * FROM transactions WHERE user_id=? "
        "ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template_string(
        HTML,
        page="transactions",
        transactions=transactions
    )


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/login")

    conn = db()

    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    conn.close()

    return render_template_string(
        HTML,
        page="profile",
        user=user
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
