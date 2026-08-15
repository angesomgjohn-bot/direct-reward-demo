import os
import sqlite3
import secrets
from datetime import datetime
from functools import wraps

from flask import Flask, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "CHANGE_THIS_SECRET_KEY"
)

DB = "nexa.db"

WITHDRAWAL_FEE = 0.12
MIN_WITHDRAWAL = 200


# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            referral_code TEXT UNIQUE NOT NULL,
            referred_by INTEGER,
            balance REAL DEFAULT 0,
            total_earned REAL DEFAULT 0,
            bank_name TEXT DEFAULT '',
            account_name TEXT DEFAULT '',
            account_number TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT NOT NULL,
            daily_profit REAL DEFAULT 0,
            days INTEGER DEFAULT 0,
            total_income REAL DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'completed',
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            fee REAL NOT NULL,
            net_amount REAL NOT NULL,
            bank_name TEXT NOT NULL,
            account_name TEXT NOT NULL,
            account_number TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS plans_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
    """)

    count = conn.execute(
        "SELECT COUNT(*) AS c FROM plans"
    ).fetchone()["c"]

    if count == 0:

        plans = [
            (
                "Plan A",
                500,
                "Basic service package",
                70,
                165,
                11550
            ),
            (
                "Plan B",
                1000,
                "Standard service package",
                0,
                30,
                0
            ),
            (
                "Plan C",
                2500,
                "Professional service package",
                0,
                30,
                0
            ),
            (
                "Plan D",
                5000,
                "Advanced service package",
                0,
                30,
                0
            ),
            (
                "Plan E",
                10000,
                "Business service package",
                0,
                30,
                0
            ),
            (
                "Plan F",
                25000,
                "Premium service package",
                0,
                30,
                0
            ),
            (
                "Plan G",
                50000,
                "Enterprise service package",
                0,
                30,
                0
            )
        ]

        conn.executemany("""
            INSERT INTO plans
            (
                name,
                price,
                description,
                daily_profit,
                days,
                total_income
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, plans)

    conn.commit()
    conn.close()


init_db()


# =========================================================
# HELPERS
# =========================================================

def money(value):
    return f"{float(value):,.2f} ETB"


def get_user():

    if "user_id" not in session:
        return None

    conn = db()

    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    conn.close()

    return user


def login_required(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if not get_user():
            return redirect(url_for("login"))

        return func(*args, **kwargs)

    return wrapper


# =========================================================
# STYLE
# =========================================================

STYLE = """
<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #f4f6fa;
    color: #172033;
    font-family: Arial, sans-serif;
}

.header {
    background: #122c70;
    color: white;
    padding: 18px;
    text-align: center;
}

.logo {
    font-size: 36px;
    font-weight: 900;
}

.tag {
    background: #ffd95a;
    color: #111;
    padding: 8px;
    margin-top: 8px;
    font-weight: bold;
}

.container {
    max-width: 720px;
    margin: auto;
    padding: 18px;
    padding-bottom: 90px;
}

.card {
    background: white;
    border-radius: 22px;
    padding: 22px;
    margin-bottom: 18px;
    box-shadow: 0 5px 20px rgba(0,0,0,.07);
}

.balance {
    background: #17233b;
    color: white;
    border-radius: 25px;
    padding: 28px;
    text-align: center;
}

.balance-number {
    color: #25dc72;
    font-size: 40px;
    font-weight: 900;
    margin: 12px 0;
}

.grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}

.btn {
    display: block;
    width: 100%;
    padding: 15px;
    border: none;
    border-radius: 13px;
    background: #2867e5;
    color: white;
    text-align: center;
    text-decoration: none;
    font-size: 16px;
    font-weight: bold;
    cursor: pointer;
}

.green {
    background: #13a657;
}

.red {
    background: #df3037;
}

.dark {
    background: #182b5e;
}

.channel {
    background: #e9f0ff;
    color: #1747a8;
}

input {
    width: 100%;
    padding: 14px;
    border: 1px solid #d6dbe4;
    border-radius: 12px;
    margin: 7px 0 14px;
    font-size: 16px;
}

label {
    font-weight: bold;
}

.plan {
    border: 1px solid #e0e4eb;
    border-radius: 20px;
    padding: 20px;
    margin: 15px 0;
}

.plan-name {
    font-size: 24px;
    font-weight: 900;
    color: #173a80;
}

.price {
    font-size: 32px;
    font-weight: 900;
    margin: 10px 0;
}

.info {
    background: #f1f4f8;
    border-radius: 12px;
    padding: 12px;
    margin: 9px 0;
}

.flash {
    background: #fff0bf;
    border-radius: 12px;
    padding: 13px;
    margin-bottom: 15px;
}

.small {
    color: #667085;
    font-size: 14px;
}

.nav {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: white;
    border-top: 1px solid #ddd;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    padding: 8px 2px;
}

.nav a {
    text-align: center;
    text-decoration: none;
    color: #687185;
    font-size: 12px;
    padding: 7px;
}

</style>
"""


# =========================================================
# PAGE
# =========================================================

def page(title, body, active="home"):

    messages = ""

    for category, message in session.pop("_flashes", []):

        messages += f"""
        <div class="flash">
            {message}
        </div>
        """

    nav = ""

    if get_user():

        nav = f"""
        <div class="nav">

            <a href="/"
               class="{'active' if active == 'home' else ''}">
                🏠<br>Home
            </a>

            <a href="/wallet"
               class="{'active' if active == 'wallet' else ''}">
                💰<br>Wallet
            </a>

            <a href="/history"
               class="{'active' if active == 'history' else ''}">
                📊<br>History
            </a>

            <a href="/my"
               class="{'active' if active == 'my' else ''}">
                👤<br>My
            </a>

        </div>
        """

    return f"""
    <!DOCTYPE html>

    <html>

    <head>

        <meta charset="UTF-8">

        <meta name="viewport"
              content="width=device-width, initial-scale=1">

        <title>Nexa - {title}</title>

        {STYLE}

    </head>

    <body>

        <div class="header">

            <div class="logo">
                NEXA
            </div>

            <div class="tag">
                WORK & SERVICES PLATFORM
            </div>

        </div>

        <div class="container">

            {messages}

            {body}

        </div>

        {nav}

    </body>

    </html>
    """


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    user = get_user()

    if not user:

        body = """
        <div class="card" style="text-align:center">

            <h1>Welcome to NEXA</h1>

            <p>
                Work & Services Platform
            </p>

            <br>

            <a class="btn" href="/register">
                Register
            </a>

            <br>

            <a class="btn dark" href="/login">
                Login
            </a>

        </div>
        """

        return page("Welcome", body)

    conn = db()

    plans = conn.execute(
        "SELECT * FROM plans ORDER BY price"
    ).fetchall()

    conn.close()

    plans_html = ""

    for p in plans:

        total = (
            money(p["total_income"])
            if p["total_income"] > 0
            else "According to completed services"
        )

        plans_html += f"""
        <div class="plan">

            <div class="plan-name">
                {p["name"]}
            </div>

            <div class="price">
                {money(p["price"])}
            </div>

            <p>
                {p["description"]}
            </p>

            <div class="info">
                Daily target:
                <b>{money(p["daily_profit"])}</b>
            </div>

            <div class="info">
                Period:
                <b>{p["days"]} days</b>
            </div>

            <div class="info">
                Total income:
                <b>{total}</b>
            </div>

            <a class="btn"
               href="/plan/{p["id"]}">
                View Plan
            </a>

        </div>
        """

    body = f"""

    <div class="balance">

        <div>
            Available Balance
        </div>

        <div class="balance-number">
            {money(user["balance"])}
        </div>

        <div>
            Total Earned:
            {money(user["total_earned"])}
        </div>

    </div>

    <br>

    <div class="grid">

        <a class="btn" href="/wallet">
            💰 Wallet
        </a>

        <a class="btn green" href="/withdraw">
            💵 Withdraw
        </a>

        <a class="btn channel"
           href="/channel">
            📢 Official Channel
        </a>

        <a class="btn dark"
           href="/support">
            🎧 Nexa Support
        </a>

    </div>

    <br>

    <div class="card">

        <h2>
            Available Plans
        </h2>

        {plans_html}

    </div>
    """

    return page("Home", body)


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        phone = request.form.get(
            "phone", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        referral = request.form.get(
            "referral", ""
        ).strip()

        if not phone or not password:

            flash(
                "Phone and password are required."
            )

            return redirect(
                url_for("register")
            )

        conn = db()

        exists = conn.execute(
            "SELECT id FROM users WHERE phone=?",
            (phone,)
        ).fetchone()

        if exists:

            conn.close()

            flash(
                "This phone number is already registered."
            )

            return redirect(
                url_for("login")
            )

        referred_by = None

        if referral:

            ref = conn.execute(
                """
                SELECT id
                FROM users
                WHERE referral_code=?
                """,
                (referral,)
            ).fetchone()

            if ref:
                referred_by = ref["id"]

        code = secrets.token_hex(5).upper()

        conn.execute(
            """
            INSERT INTO users
            (
                phone,
                password,
                referral_code,
                referred_by,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                phone,
                generate_password_hash(password),
                code,
                referred_by,
                datetime.utcnow().isoformat()
            )
        )

        conn.commit()
        conn.close()

        flash(
            "Registration successful. Please login."
        )

        return redirect(
            url_for("login")
        )

    body = """

    <div class="card">

        <h1>
            Create Account
        </h1>

        <form method="post">

            <label>
                Phone Number
            </label>

            <input
                name="phone"
                placeholder="09xxxxxxxx"
                required
            >

            <label>
                Password
            </label>

            <input
                type="password"
                name="password"
                required
            >

            <label>
                Referral Code
            </label>

            <input
                name="referral"
                placeholder="Optional"
            >

            <button class="btn"
                    type="submit">
                Register
            </button>

        </form>

        <br>

        <a href="/login">
            Already have an account? Login
        </a>

    </div>
    """

    return page("Register", body)


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        phone = request.form.get(
            "phone", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        conn = db()

        user = conn.execute(
            "SELECT * FROM users WHERE phone=?",
            (phone,)
        ).fetchone()

        conn.close()

        if (
            not user
            or not check_password_hash(
                user["password"],
                password
            )
        ):

            flash(
                "Incorrect phone number or password."
            )

            return redirect(
                url_for("login")
            )

        session["user_id"] = user["id"]

        return redirect(
            url_for("home")
        )

    body = """

    <div class="card">

        <h1>
            Login
        </h1>

        <form method="post">

            <label>
                Phone Number
            </label>

            <input
                name="phone"
                required
            >

            <label>
                Password
            </label>

            <input
                type="password"
                name="password"
                required
            >

            <button class="btn"
                    type="submit">
                Login
            </button>

        </form>

        <br>

        <a href="/register">
            Create account
        </a>

    </div>
    """

    return page("Login", body)


# =========================================================
# WALLET
# =========================================================

@app.route("/wallet")
@login_required
def wallet():

    user = get_user()

    body = f"""

    <div class="balance">

        <div>
            Wallet Balance
        </div>

        <div class="balance-number">
            {money(user["balance"])}
        </div>

        <div>
            Total Earned:
            {money(user["total_earned"])}
        </div>

    </div>

    <br>

    <div class="card">

        <a class="btn green"
           href="/withdraw">
            💵 Withdraw
        </a>

        <br>

        <a class="btn"
           href="/plans">
            📦 View Plans
        </a>

    </div>
    """

    return page(
        "Wallet",
        body,
        "wallet"
    )


# =========================================================
# PLANS
# =========================================================

@app.route("/plans")
@login_required
def plans():

    return redirect(url_for("home"))


@app.route("/plan/<int:plan_id>")
@login_required
def plan(plan_id):

    conn = db()

    p = conn.execute(
        "SELECT * FROM plans WHERE id=?",
        (plan_id,)
    ).fetchone()

    conn.close()

    if not p:

        flash("Plan not found.")

        return redirect(url_for("home"))

    total = (
        money(p["total_income"])
        if p["total_income"] > 0
        else "According to completed services"
    )

    body = f"""

    <div class="card">

        <h1>
            {p["name"]}
        </h1>

        <div class="price">
            {money(p["price"])}
        </div>

        <p>
            {p["description"]}
        </p>

        <div class="info">
            Daily target:
            <b>{money(p["daily_profit"])}</b>
        </div>

        <div class="info">
            Days:
            <b>{p["days"]}</b>
        </div>

        <div class="info">
            Total income:
            <b>{total}</b>
        </div>

        <p class="small">
            Earnings depend on completed work/services
            and are not guaranteed.
        </p>

        <form method="post"
              action="/plan/{p["id"]}/request">

            <button class="btn"
                    type="submit">
                Request Plan
            </button>

        </form>

    </div>
    """

    return page(
        p["name"],
        body
    )


@app.route(
    "/plan/<int:plan_id>/request",
    methods=["POST"]
)
@login_required
def request_plan(plan_id):

    user = get_user()

    conn = db()

    p = conn.execute(
        "SELECT * FROM plans WHERE id=?",
        (plan_id,)
    ).fetchone()

    if not p:

        conn.close()

        flash("Plan not found.")

        return redirect(url_for("home"))

    conn.execute(
        """
        INSERT INTO plans_orders
        (
            user_id,
            plan_id,
            amount,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user["id"],
            p["id"],
            p["price"],
            "pending",
            datetime.utcnow().isoformat()
        )
    )

    conn.commit()
    conn.close()

    flash(
        f'{p["name"]} request submitted.'
    )

    return redirect(
        url_for("history")
    )


# =========================================================
# WITHDRAW
# =========================================================

@app.route(
    "/withdraw",
    methods=["GET", "POST"]
)
@login_required
def withdraw():

    user = get_user()

    if request.method == "POST":

        try:
            amount = float(
                request.form.get(
                    "amount",
                    "0"
                )
            )
        except ValueError:
            amount = 0

        bank = request.form.get(
            "bank_name",
            ""
        ).strip()

        account_name = request.form.get(
            "account_name",
            ""
        ).strip()

        account_number = request.form.get(
            "account_number",
            ""
        ).strip()

        if amount < MIN_WITHDRAWAL:

            flash(
                "Minimum withdrawal amount is 200 ETB."
            )

            return redirect(
                url_for("withdraw")
            )

        fee = round(
            amount * WITHDRAWAL_FEE,
            2
        )

        net = round(
            amount - fee,
            2
        )

        if amount > user["balance"]:

            flash(
                "Insufficient balance."
            )

            return redirect(
                url_for("withdraw")
            )

        if not bank or not account_name or not account_number:

            flash(
                "Please complete your bank details."
            )

            return redirect(
                url_for("withdraw")
            )

        conn = db()

        conn.execute(
            """
            UPDATE users
            SET
                balance = balance - ?,
                bank_name = ?,
                account_name = ?,
                account_number = ?
            WHERE id=?
            """,
            (
                amount,
                bank,
                account_name,
                account_number,
                user["id"]
            )
        )

        conn.execute(
            """
            INSERT INTO withdrawals
            (
                user_id,
                amount,
                fee,
                net_amount,
                bank_name,
                account_name,
                account_number,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                amount,
                fee,
                net,
                bank,
                account_name,
                account_number,
                "pending",
                datetime.utcnow().isoformat()
            )
        )

        conn.execute(
            """
            INSERT INTO transactions
            (
                user_id,
                type,
                amount,
                description,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                "withdrawal",
                amount,
                f"Withdrawal request - fee {money(fee)}",
                "pending",
                datetime.utcnow().isoformat()
            )
        )

        conn.commit()
        conn.close()

        flash(
            f"Withdrawal submitted. "
            f"Fee: {money(fee)} | "
            f"Net amount: {money(net)} | "
            f"Processing: within 24 hours."
        )

        return redirect(
            url_for("history")
        )

    fee_percent = int(
        WITHDRAWAL_FEE * 100
    )

    body = f"""

    <div class="card">

        <h1>
            Withdraw
        </h1>

        <div class="info">
            Available Balance:
            <b>{money(user["balance"])}</b>
        </div>

        <div class="info">
            Minimum Withdrawal:
            <b>{MIN_WITHDRAWAL} ETB</b>
        </div>

        <div class="info">
            Withdrawal Fee:
            <b>{fee_percent}%</b>
        </div>

        <div class="info">
            Processing:
            <b>Within 24 hours</b>
        </div>

        <form method="post">

            <label>
                Withdrawal Amount
            </label>

            <input
                id="amount"
                name="amount"
                type="number"
                min="200"
                step="0.01"
                placeholder="200"
                required
                oninput="calculateFee()"
            >

            <div class="info">

                Fee:
                <b id="fee">
                    0.00 ETB
                </b>

                <br><br>

                You Receive:
                <b id="net">
                    0.00 ETB
                </b>

            </div>

            <label>
                Bank / Payment Provider
            </label>

            <input
                name="bank_name"
                value="{user["bank_name"] or ""}"
                required
            >

            <label>
                Account Name
            </label>

            <input
                name="account_name"
                value="{user["account_name"] or ""}"
                required
            >

            <label>
                Account Number
            </label>

            <input
                name="account_number"
                value="{user["account_number"] or ""}"
                required
            >

            <button class="btn green"
                    type="submit">
                Submit Withdrawal
            </button>

        </form>

    </div>

    <script>

    function calculateFee() {{

        let amount =
            parseFloat(
                document.getElementById("amount").value
            ) || 0;

        let fee =
            amount * 0.12;

        let net =
            amount - fee;

        document.getElementById("fee")
            .innerText =
            fee.toFixed(2) + " ETB";

        document.getElementById("net")
            .innerText =
            net.toFixed(2) + " ETB";
    }}

    </script>
    """

    return page(
        "Withdraw",
        body
    )


# =========================================================
# HISTORY
# =========================================================

@app.route("/history")
@login_required
def history():

    user = get_user()

    conn = db()

    withdrawals = conn.execute(
        """
        SELECT *
        FROM withdrawals
        WHERE user_id=?
        ORDER BY id DESC
        """,
        (user["id"],)
    ).fetchall()

    orders = conn.execute(
        """
        SELECT
            plans_orders.*,
            plans.name
        FROM plans_orders
        JOIN plans
        ON plans.id = plans_orders.plan_id
        WHERE plans_orders.user_id=?
        ORDER BY plans_orders.id DESC
        """,
        (user["id"],)
    ).fetchall()

    conn.close()

    wh = ""

    for w in withdrawals:

        wh += f"""
        <div class="info">

            💵 Withdrawal:
            <b>{money(w["amount"])}</b>

            <br>

            Fee:
            {money(w["fee"])}

            <br>

            You Receive:
            <b>{money(w["net_amount"])}</b>

            <br>

            Status:
            <b>{w["status"]}</b>

        </div>
        """

    oh = ""

    for o in orders:

        oh += f"""
        <div class="info">

            📦 {o["name"]}

            <br>

            Amount:
            {money(o["amount"])}

            <br>

            Status:
            <b>{o["status"]}</b>

        </div>
        """

    body = f"""

    <div class="card">

        <h1>
            History
        </h1>

        <h3>
            Withdrawals
        </h3>

        {wh or "<p>No withdrawals yet.</p>"}

        <h3>
            Plans
        </h3>

        {oh or "<p>No plan requests yet.</p>"}

    </div>
    """

    return page(
        "History",
        body,
        "history"
    )


# =========================================================
# MY ACCOUNT / INVITE
# =========================================================

@app.route("/my")
@login_required
def my():

    user = get_user()

    referral_link = (
        request.host_url.rstrip("/")
        + "/register?ref="
        + user["referral_code"]
    )

    conn = db()

    invited = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM users
        WHERE referred_by=?
        """,
        (user["id"],)
    ).fetchone()["c"]

    conn.close()

    body = f"""

    <div class="card">

        <h1>
            My Account
        </h1>

        <div class="info">
            Phone:
            <b>{user["phone"]}</b>
        </div>

        <div class="info">
            Balance:
            <b>{money(user["balance"])}</b>
        </div>

        <h2>
            👥 Invite Friends
        </h2>

        <p>
            Share your referral link with friends.
        </p>

        <input
            value="{referral_link}"
            readonly
            onclick="this.select()"
        >

        <div class="info">
            Referral Code:
            <b>{user["referral_code"]}</b>
        </div>

        <div class="info">
            Invited Users:
            <b>{invited}</b>
        </div>

        <br>

        <a class="btn"
           href="/invite">
            🔗 Invite Friends
        </a>

        <br>

        <a class="btn dark"
           href="/profile">
            🏦 Bank Details
        </a>

        <br>

        <a class="btn channel"
           href="/channel">
            📢 Nexa Official Channel
        </a>

        <br>

        <a class="btn green"
           href="/support">
            🎧 Nexa Customer Service
        </a>

        <br>

        <a class="btn red"
           href="/logout">
            Logout
        </a>

    </div>
    """

    return page(
        "My Account",
        body,
        "my"
    )


@app.route("/invite")
@login_required
def invite():

    user = get_user()

    link = (
        request.host_url.rstrip("/")
        + "/register?ref="
        + user["referral_code"]
    )

    body = f"""

    <div class="card"
         style="text-align:center">

        <h1>
            👥 Invite Friends
        </h1>

        <p>
            Invite people to join Nexa.
        </p>

        <input
            id="ref"
            value="{link}"
            readonly
        >

        <button
            class="btn"
            onclick="copyLink()">
            📋 Copy Referral Link
        </button>

        <br>

        <div class="info">
            Your Referral Code:
            <b>{user["referral_code"]}</b>
        </div>

    </div>

    <script>

    function copyLink() {{

        let input =
            document.getElementById("ref");

        input.select();

        navigator.clipboard
            .writeText(input.value);

        alert("Referral link copied.");
    }}

    </script>
    """

    return page(
        "Invite Friends",
        body,
        "my"
    )


# =========================================================
# BANK DETAILS
# =========================================================

@app.route(
    "/profile",
    methods=["GET", "POST"]
)
@login_required
def profile():

    user = get_user()

    if request.method == "POST":

        bank = request.form.get(
            "bank_name",
            ""
        ).strip()

        account_name = request.form.get(
            "account_name",
            ""
        ).strip()

        account_number = request.form.get(
            "account_number",
            ""
        ).strip()

        conn = db()

        conn.execute(
            """
            UPDATE users
            SET
                bank_name=?,
                account_name=?,
                account_number=?
            WHERE id=?
            """,
            (
                bank,
                account_name,
                account_number,
                user["id"]
            )
        )

        conn.commit()
        conn.close()

        flash(
            "Bank details saved."
        )

        return redirect(
            url_for("my")
        )

    body = f"""

    <div class="card">

        <h1>
            🏦 Bank Details
        </h1>

        <form method="post">

            <label>
                Bank / Payment Provider
            </label>

            <input
                name="bank_name"
                value="{user["bank_name"] or ""}"
                placeholder="Bank name"
                required
            >

            <label>
                Account Name
            </label>

            <input
                name="account_name"
                value="{user["account_name"] or ""}"
                required
            >

            <label>
                Account Number
            </label>

            <input
                name="account_number"
                value="{user["account_number"] or ""}"
                required
            >

            <button class="btn"
                    type="submit">
                Save Details
            </button>

        </form>

    </div>
    """

    return page(
        "Bank Details",
        body,
        "my"
    )


# =========================================================
# OFFICIAL CHANNEL
# =========================================================

@app.route("/channel")
@login_required
def channel():

    body = """

    <div class="card"
         style="text-align:center">

        <div style="font-size:55px;">
            📢
        </div>

        <h1>
            Nexa Official Channel
        </h1>

        <p>
            Follow the official Nexa channel
            for announcements and updates.
        </p>

        <!-- CHANGE THIS LINK -->
        <a
            class="btn channel"
            href="https://t.me/YOUR_NEXA_CHANNEL"
            target="_blank">

            📢 Open Nexa Official Channel

        </a>

    </div>

    """

    return page(
        "Official Channel",
        body,
        "my"
    )


# =========================================================
# NEXA CUSTOMER SERVICE
# =========================================================

@app.route("/support")
@login_required
def support():

    body = """

    <div class="card"
         style="text-align:center">

        <div style="font-size:60px;">
            🎧
        </div>

        <h1>
            Nexa Customer Service
        </h1>

        <p>
            Welcome to Nexa Customer Service.
        </p>

        <div class="info">
            Support:
            <b>Nexa Support Team</b>
        </div>

        <div class="info">
            Availability:
            <b>24 Hours</b>
        </div>

        <!-- CHANGE THIS USERNAME -->
        <a
            class="btn dark"
            href="https://t.me/YOUR_NEXA_SUPPORT"
            target="_blank">

            💬 Contact Nexa Support

        </a>

    </div>

    """

    return page(
        "Nexa Customer Service",
        body,
        "my"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    ) 
