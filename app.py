from flask import Flask, request, redirect, session, render_template_string
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "nexa-demo-secret-key"

DB = "nexa_demo.db"


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
            balance REAL DEFAULT 0,
            total_income REAL DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


init_db()


CSS = """
<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #101827;
    color: white;
}

.container {
    width: min(430px, 92%);
    margin: 35px auto;
}

.card {
    background: #202c3d;
    border-radius: 28px;
    padding: 28px 22px;
    box-shadow: 0 10px 30px rgba(0,0,0,.25);
}

.logo {
    text-align: center;
    font-size: 38px;
    font-weight: 900;
    margin-bottom: 5px;
}

.demo {
    text-align: center;
    color: #ffcf40;
    font-size: 12px;
    font-weight: bold;
    letter-spacing: 2px;
    margin-bottom: 25px;
}

h1, h2 {
    text-align: center;
}

.subtitle {
    text-align: center;
    font-size: 18px;
    margin-bottom: 25px;
}

.balance {
    text-align: center;
    font-size: 45px;
    font-weight: bold;
    color: #20d45b;
    margin: 12px 0;
}

.label {
    text-align: center;
    color: #ddd;
    margin-bottom: 25px;
}

button, .btn {
    display: block;
    width: 100%;
    padding: 16px;
    margin: 10px 0;
    border: none;
    border-radius: 15px;
    background: #2864e8;
    color: white;
    font-size: 18px;
    text-align: center;
    text-decoration: none;
    cursor: pointer;
}

.btn-red {
    background: #e9232b;
}

.btn-green {
    background: #18a957;
}

input {
    width: 100%;
    padding: 16px;
    margin: 8px 0;
    border: none;
    border-radius: 12px;
    font-size: 16px;
}

.grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}

.info {
    background: #182334;
    padding: 15px;
    border-radius: 15px;
    margin: 10px 0;
}

.info strong {
    display: block;
    font-size: 22px;
    margin-top: 5px;
}

.menu {
    background: #f7f8fa;
    color: #222;
    padding: 15px;
    border-radius: 15px;
    margin: 10px 0;
    text-decoration: none;
    display: block;
    font-size: 17px;
}

.small {
    text-align: center;
    color: #aaa;
    font-size: 13px;
    margin-top: 20px;
}

.alert {
    background: #5b2020;
    padding: 12px;
    border-radius: 10px;
    margin-bottom: 15px;
    text-align: center;
}

.plan {
    background: #182334;
    border-radius: 20px;
    padding: 18px;
    margin: 15px 0;
}

.plan h3 {
    margin-top: 0;
}

.amount {
    font-size: 25px;
    font-weight: bold;
}

table {
    width: 100%;
    border-collapse: collapse;
}

td {
    padding: 10px 4px;
    border-bottom: 1px solid #394456;
    font-size: 13px;
}
</style>
"""


def page(content):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport"
              content="width=device-width, initial-scale=1">
        <title>Nexa Demo</title>
    </head>
    <body>
        {CSS}
        <div class="container">
            {content}
        </div>
    </body>
    </html>
    """


@app.route("/")
def home():
    return page("""
    <div class="card">
        <div class="logo">NEXA</div>
        <div class="demo">DEMO WALLET • TEST MODE</div>

        <h1>💰 Nexa</h1>

        <div class="subtitle">
            Deposit • Balance • Withdraw
        </div>

        <a class="btn" href="/register">Register</a>
        <a class="btn" href="/login">Login</a>

        <div class="small">
            This is a demonstration website.
        </div>
    </div>
    """)


@app.route("/register", methods=["GET", "POST"])
def register():

    error = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not username or not password:
            error = "Please fill all fields."

        elif password != confirm:
            error = "Passwords do not match."

        else:
            conn = get_db()

            try:
                conn.execute(
                    "INSERT INTO users(username,password) VALUES (?,?)",
                    (username, generate_password_hash(password))
                )
                conn.commit()
                conn.close()

                return redirect("/login")

            except sqlite3.IntegrityError:
                conn.close()
                error = "Username already exists."

    return page(f"""
    <div class="card">
        <div class="logo">NEXA</div>
        <div class="demo">DEMO / TEST MODE</div>

        <h2>Create Account</h2>

        {"<div class='alert'>" + error + "</div>" if error else ""}

        <form method="post">

            <input
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

            <input
                type="password"
                name="confirm"
                placeholder="Confirm password"
                required
            >

            <button type="submit">
                Register
            </button>
        </form>

        <a class="btn" href="/login">Already have an account?</a>
    </div>
    """)


@app.route("/login", methods=["GET", "POST"])
def login():

    error = ""

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):

            session["user_id"] = user["id"]

            return redirect("/dashboard")

        error = "Invalid username or password."

    return page(f"""
    <div class="card">
        <div class="logo">NEXA</div>
        <div class="demo">DEMO / TEST MODE</div>

        <h2>Login</h2>

        {"<div class='alert'>" + error + "</div>" if error else ""}

        <form method="post">

            <input
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

        <a class="btn" href="/register">Create account</a>
    </div>
    """)


def current_user():

    if "user_id" not in session:
        return None

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    conn.close()

    return user


@app.route("/dashboard")
def dashboard():

    user = current_user()

    if not user:
        return redirect("/login")

    return page(f"""
    <div class="card">

        <div class="logo">NEXA</div>
        <div class="demo">DEMO / TEST MODE</div>

        <h1>Dashboard</h1>

        <div class="subtitle">
            Welcome, <strong>{user["username"]}</strong>
        </div>

        <div class="balance">
            {user["balance"]:,.2f} ETB
        </div>

        <div class="label">
            Current Balance
        </div>

        <div class="grid">

            <a class="btn" href="/deposit">
                💵 Deposit
            </a>

            <a class="btn" href="/withdraw">
                💸 Withdraw
            </a>

            <a class="btn" href="/history">
                📊 History
            </a>

            <a class="btn" href="/my">
                👤 My
            </a>

        </div>

        <a class="btn btn-red" href="/logout">
            Logout
        </a>

    </div>
    """)


@app.route("/deposit", methods=["GET", "POST"])
def deposit():

    user = current_user()

    if not user:
        return redirect("/login")

    message = ""

    if request.method == "POST":

        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            amount = 0

        # Demo limit
        if amount < 1:
            message = "Enter a valid demo amount."

        elif amount > 50000:
            message = "Maximum demo deposit is 50,000 ETB."

        else:
            conn = get_db()

            conn.execute(
                """
                UPDATE users
                SET balance = balance + ?
                WHERE id=?
                """,
                (amount, user["id"])
            )

            conn.execute(
                """
                INSERT INTO transactions
                (user_id,type,amount,note)
                VALUES (?,?,?,?)
                """,
                (
                    user["id"],
                    "DEPOSIT",
                    amount,
                    "Demo transaction"
                )
            )

            conn.commit()
            conn.close()

            return redirect("/dashboard")

    return page(f"""
    <div class="card">

        <div class="logo">NEXA</div>
        <div class="demo">DEMO DEPOSIT</div>

        <h2>Deposit</h2>

        {"<div class='alert'>" + message + "</div>" if message else ""}

        <p>
            Demo only. No real money is transferred.
        </p>

        <form method="post">

            <input
                type="number"
                name="amount"
                min="1"
                max="50000"
                step="0.01"
                placeholder="Amount in ETB"
                required
            >

            <button type="submit">
                Add Demo Balance
            </button>

        </form>

        <a class="btn" href="/dashboard">
            Back
        </a>

    </div>
    """)


@app.route("/withdraw", methods=["GET", "POST"])
def withdraw():

    user = current_user()

    if not user:
        return redirect("/login")

    message = ""

    if request.method == "POST":

        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            amount = 0

        if amount < 200:
            message = "Minimum demo withdrawal is 200 ETB."

        elif amount > user["balance"]:
            message = "Insufficient demo balance."

        else:
            conn = get_db()

            conn.execute(
                """
                UPDATE users
                SET balance = balance - ?
                WHERE id=?
                """,
                (amount, user["id"])
            )

            conn.execute(
                """
                INSERT INTO transactions
                (user_id,type,amount,note)
                VALUES (?,?,?,?)
                """,
                (
                    user["id"],
                    "WITHDRAWAL",
                    amount,
                    "Demo withdrawal request"
                )
            )

            conn.commit()
            conn.close()

            return redirect("/history")

    return page(f"""
    <div class="card">

        <div class="logo">NEXA</div>
        <div class="demo">DEMO WITHDRAWAL</div>

        <h2>Withdraw</h2>

        <div class="info">
            Available demo balance
            <strong>{user["balance"]:,.2f} ETB</strong>
        </div>

        {"<div class='alert'>" + message + "</div>" if message else ""}

        <p>
            Minimum withdrawal: <strong>200 ETB</strong>
        </p>

        <p>
            This is a simulated demo request.
        </p>

        <form method="post">

            <input
                type="number"
                name="amount"
                min="200"
                step="0.01"
                placeholder="Amount in ETB"
                required
            >

            <button type="submit">
                Submit Demo Request
            </button>

        </form>

        <a class="btn" href="/dashboard">
            Back
        </a>

    </div>
    """)


@app.route("/history")
def history():

    user = current_user()

    if not user:
        return redirect("/login")

    conn = get_db()

    rows = conn.execute(
        """
        SELECT * FROM transactions
        WHERE user_id=?
        ORDER BY id DESC
        """,
        (user["id"],)
    ).fetchall()

    conn.close()

    table = ""

    if rows:

        table = "<table>"

        for row in rows:

            table += f"""
            <tr>
                <td>
                    <strong>{row["type"]}</strong><br>
                    {row["note"] or ""}
                </td>

                <td>
                    {row["amount"]:,.2f} ETB
                </td>
            </tr>
            """

        table += "</table>"

    else:
        table = "<p>No transactions yet.</p>"

    return page(f"""
    <div class="card">

        <div class="logo">NEXA</div>
        <div class="demo">DEMO HISTORY</div>

        <h2>Transaction History</h2>

        {table}

        <a class="btn" href="/dashboard">
            Back to Dashboard
        </a>

    </div>
    """)


@app.route("/my")
def my():

    user = current_user()

    if not user:
        return redirect("/login")

    return page(f"""
    <div class="card">

        <div class="logo">NEXA</div>
        <div class="demo">DEMO / TEST MODE</div>

        <div class="grid">

            <div class="info">
                Balance
                <strong>
                    {user["balance"]:,.2f}
                </strong>
            </div>

            <div class="info">
                Total income
                <strong>
                    {user["total_income"]:,.2f}
                </strong>
            </div>

        </div>

        <a class="menu" href="/messages">
            💬 Messages
        </a>

        <a class="menu" href="/personal">
            👤 Personal information
        </a>

        <a class="menu" href="/income">
            📅 Income details
        </a>

        <a class="menu" href="/deposit">
            💳 Recharge details
        </a>

        <a class="menu" href="/withdraw">
            💸 Withdrawal details
        </a>

        <a class="menu" href="/about">
            📖 About us
        </a>

        <a class="menu" href="/download">
            ⬇️ Download
        </a>

        <a class="menu" href="/language">
            🌐 Language
        </a>

        <a class="menu" href="/logout">
            🚪 Log out
        </a>

        <a class="btn" href="/dashboard">
            Dashboard
        </a>

    </div>
    """)


@app.route("/messages")
def messages():

    if not current_user():
        return redirect("/login")

    return page("""
    <div class="card">
        <div class="logo">NEXA</div>
        <div class="demo">MESSAGES</div>

        <h2>Messages</h2>

        <div class="info">
            Welcome to Nexa Demo.
        </div>

        <div class="info">
            This website is running in test mode.
        </div>

        <a class="btn" href="/my">Back</a>
    </div>
    """)


@app.route("/personal")
def personal():

    user = current_user()

    if not user:
        return redirect("/login")

    return page(f"""
    <div class="card">

        <div class="logo">NEXA</div>
        <div class="demo">PERSONAL INFORMATION</div>

        <h2>Personal Information</h2>

        <div class="info">
            Username
            <strong>{user["username"]}</strong>
        </div>

        <div class="info">
            Account type
            <strong>Demo</strong>
        </div>

        <a class="btn" href="/my">Back</a>

    </div>
    """)


@app.route("/income")
def income():

    user = current_user()

    if not user:
        return redirect("/login")

    return page(f"""
    <div class="card">

        <div class="logo">NEXA</div>
        <div class="demo">INCOME DETAILS</div>

        <h2>Income Details</h2>

        <div class="info">
            Total demo income
            <strong>
                {user["total_income"]:,.2f} ETB
            </strong>
        </div>

        <p>
            Income figures on this demo are not real earnings.
        </p>

        <a class="btn" href="/my">Back</a>

    </div>
    """)


@app.route("/about")
def about():

    return page("""
    <div class="card">

        <div class="logo">NEXA</div>
        <div class="demo">DEMO WEBSITE</div>

        <h2>About Nexa</h2>

        <p>
            Nexa is a demonstration wallet interface
            created for testing website flows.
        </p>

        <p>
            It does not process real payments or real
            withdrawals.
        </p>

        <a class="btn" href="/my">Back</a>

    </div>
    """)


@app.route("/download")
def download():

    return page("""
    <div class="card">

        <div class="logo">NEXA</div>
        <div class="demo">DEMO</div>

        <h2>Download</h2>

        <p>
            App download is not available in this demo.
        </p>

        <a class="btn" href="/my">Back</a>

    </div>
    """)


@app.route("/language")
def language():

    return page("""
    <div class="card">

        <div class="logo">NEXA</div>
        <div class="demo">LANGUAGE</div>

        <h2>Language</h2>

        <button>English</button>
        <button>አማርኛ</button>

        <a class="btn" href="/my">Back</a>

    </div>
    """)


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )
