from flask import Flask, request, redirect, session, render_template_string
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "nexa-change-this-secret")

DB = "nexa.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -------------------------------------------------
# JOB PLANS
# These are work/task packages, not investment plans.
# -------------------------------------------------

PLANS = [
    {
        "name": "Plan A",
        "price": 500,
        "daily": 70,
        "days": 165,
        "total": 11550,
        "description": "Entry-level digital tasks and assignments."
    },
    {
        "name": "Plan B",
        "price": 1000,
        "daily": 140,
        "days": 165,
        "total": 23100,
        "description": "Standard digital tasks and assignments."
    },
    {
        "name": "Plan C",
        "price": 2500,
        "daily": 350,
        "days": 165,
        "total": 57750,
        "description": "Intermediate task package."
    },
    {
        "name": "Plan D",
        "price": 5000,
        "daily": 700,
        "days": 165,
        "total": 115500,
        "description": "Advanced digital work package."
    },
    {
        "name": "Plan E",
        "price": 10000,
        "daily": 1400,
        "days": 165,
        "total": 231000,
        "description": "Professional task package."
    },
    {
        "name": "Plan F",
        "price": 25000,
        "daily": 3500,
        "days": 165,
        "total": 577500,
        "description": "Large-volume work package."
    },
    {
        "name": "Plan G",
        "price": 50000,
        "daily": 7000,
        "days": 165,
        "total": 1155000,
        "description": "Large business task package."
    }
]


# -------------------------------------------------
# DATABASE
# -------------------------------------------------

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()

    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance REAL DEFAULT 0,
            total_earned REAL DEFAULT 0,
            plan TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            reward REAL NOT NULL,
            status TEXT DEFAULT 'Open'
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            status TEXT DEFAULT 'Pending',
            created_at TEXT NOT NULL
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Demo jobs
    count = con.execute(
        "SELECT COUNT(*) AS c FROM jobs"
    ).fetchone()["c"]

    if count == 0:
        jobs = [
            (
                "Data Entry",
                "Enter and organize provided information.",
                70
            ),
            (
                "Content Review",
                "Review short digital content according to instructions.",
                100
            ),
            (
                "Online Research",
                "Collect information from approved sources.",
                150
            ),
            (
                "Customer Support",
                "Assist customers using provided scripts.",
                200
            )
        ]

        for title, description, reward in jobs:
            con.execute(
                """
                INSERT INTO jobs(title,description,reward)
                VALUES (?,?,?)
                """,
                (title, description, reward)
            )

    con.commit()
    con.close()


init_db()


# -------------------------------------------------
# CSS
# -------------------------------------------------

CSS = """
<style>
*{box-sizing:border-box}

body{
    margin:0;
    font-family:Arial,sans-serif;
    background:#f1f4f8;
    color:#182238;
}

.top{
    background:#10245e;
    color:#fff;
    padding:18px;
    text-align:center;
    font-size:27px;
    font-weight:900;
}

.badge{
    display:block;
    text-align:center;
    background:#ffdf72;
    color:#493700;
    padding:6px;
    font-size:12px;
    font-weight:bold;
}

.wrap{
    max-width:760px;
    margin:auto;
    padding:16px;
}

.card{
    background:#fff;
    border-radius:18px;
    padding:20px;
    margin-bottom:16px;
    box-shadow:0 4px 18px rgba(0,0,0,.07);
}

.hero{
    background:linear-gradient(135deg,#10245e,#3567d7);
    color:#fff;
    border-radius:20px;
    padding:28px 20px;
    text-align:center;
    margin-bottom:16px;
}

.hero h1{
    margin:0 0 8px;
    font-size:34px;
}

.balance{
    background:#172238;
    color:#fff;
    text-align:center;
    border-radius:20px;
    padding:22px;
    margin-bottom:16px;
}

.balance .num{
    color:#25d66c;
    font-size:40px;
    font-weight:900;
    margin:8px 0;
}

.grid{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:10px;
}

button,.btn{
    display:block;
    width:100%;
    border:0;
    border-radius:12px;
    padding:14px;
    margin:7px 0;
    background:#2865e8;
    color:#fff;
    font-size:16px;
    text-decoration:none;
    text-align:center;
    cursor:pointer;
}

.green{background:#159b52}
.red{background:#df2935}
.gray{background:#657083}

input,select,textarea{
    width:100%;
    padding:14px;
    border:1px solid #d9dde5;
    border-radius:10px;
    margin:7px 0;
    font-size:16px;
}

.plan{
    border:1px solid #e0e4ec;
    border-radius:18px;
    padding:18px;
    margin:14px 0;
}

.plan h3{
    margin-top:0;
    color:#12255f;
}

.price{
    font-size:26px;
    font-weight:bold;
}

.stat{
    background:#f2f5fa;
    padding:12px;
    border-radius:10px;
    margin:8px 0;
}

.notice{
    background:#eef3ff;
    padding:13px;
    border-radius:10px;
    margin:10px 0;
}

.error{
    background:#ffe4e4;
    color:#8c1111;
}

.success{
    background:#e1f8ea;
    color:#126b36;
}

.job{
    border:1px solid #e0e4ec;
    padding:17px;
    border-radius:15px;
    margin:12px 0;
}

.menu{
    display:block;
    background:#fff;
    padding:16px;
    margin:8px 0;
    border-radius:12px;
    color:#182238;
    text-decoration:none;
    box-shadow:0 2px 8px rgba(0,0,0,.05);
}

.small{
    color:#777;
    font-size:13px;
}

.center{text-align:center}
</style>
"""


def page(content, title="NEXA"):
    return f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport"
              content="width=device-width,initial-scale=1">
        <title>{title}</title>
        {CSS}
    </head>
    <body>
        <div class="top">NEXA</div>
        <div class="badge">JOBS & SERVICES PLATFORM</div>
        <div class="wrap">
            {content}
        </div>
    </body>
    </html>
    """


def user():
    uid = session.get("user_id")

    if not uid:
        return None

    con = db()
    u = con.execute(
        "SELECT * FROM users WHERE id=?",
        (uid,)
    ).fetchone()
    con.close()

    return u


# -------------------------------------------------
# HOME
# -------------------------------------------------

@app.route("/")
def home():

    return page("""
    <div class="hero">
        <h1>NEXA</h1>
        <p>Jobs • Tasks • Earnings • Wallet</p>
    </div>

    <div class="card">
        <h2>Find Work & Complete Tasks</h2>
        <p>
            Create an account, find available work,
            complete tasks and track your earnings.
        </p>

        <a class="btn" href="/register">Create Account</a>
        <a class="btn gray" href="/login">Login</a>
    </div>

    <div class="card">
        <h2>Work Packages</h2>

        <p class="small">
            Packages describe task/work access and
            are not investment products.
        </p>
    </div>
    """)

# -------------------------------------------------
# REGISTER
# -------------------------------------------------

@app.route("/register", methods=["GET","POST"])
def register():

    error = ""

    if request.method == "POST":

        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        confirm = request.form.get("confirm","")

        if not username or not password:
            error = "Fill all fields."

        elif password != confirm:
            error = "Passwords do not match."

        else:
            con = db()

            try:
                con.execute(
                    """
                    INSERT INTO users
                    (username,password,created_at)
                    VALUES (?,?,?)
                    """,
                    (
                        username,
                        generate_password_hash(password),
                        datetime.now().isoformat()
                    )
                )

                con.commit()
                con.close()

                return redirect("/login")

            except sqlite3.IntegrityError:
                con.close()
                error = "Username already exists."

    return page(f"""
    <div class="card">
        <h2>Create NEXA Account</h2>

        {"<div class='notice error'>"+error+"</div>" if error else ""}

        <form method="post">

            <input name="username"
                   placeholder="Username"
                   required>

            <input type="password"
                   name="password"
                   placeholder="Password"
                   required>

            <input type="password"
                   name="confirm"
                   placeholder="Confirm password"
                   required>

            <button>Register</button>
        </form>

        <a class="btn gray" href="/login">Login</a>
    </div>
    """)


# -------------------------------------------------
# LOGIN
# -------------------------------------------------

@app.route("/login", methods=["GET","POST"])
def login():

    error = ""

    if request.method == "POST":

        username = request.form.get("username","")
        password = request.form.get("password","")

        con = db()

        u = con.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        con.close()

        if u and check_password_hash(
            u["password"], password
        ):
            session["user_id"] = u["id"]
            return redirect("/dashboard")

        error = "Invalid login details."

    return page(f"""
    <div class="card">
        <h2>Login</h2>

        {"<div class='notice error'>"+error+"</div>" if error else ""}

        <form method="post">

            <input name="username"
                   placeholder="Username"
                   required>

            <input type="password"
                   name="password"
                   placeholder="Password"
                   required>

            <button>Login</button>
        </form>

        <a class="btn gray" href="/register">
            Register
        </a>
    </div>
    """)


# -------------------------------------------------
# DASHBOARD
# -------------------------------------------------

@app.route("/dashboard")
def dashboard():

    u = user()

    if not u:
        return redirect("/login")

    plans_html = ""

    for p in PLANS:

        plans_html += f"""
        <div class="plan">

            <h3>{p["name"]}</h3>

            <div class="price">
                {p["price"]:,} ETB
            </div>

            <p>{p["description"]}</p>

            <div class="stat">
                Daily task target:
                <b>{p["daily"]:,} ETB</b>
            </div>

            <div class="stat">
                Duration:
                <b>{p["days"]} days</b>
            </div>

            <div class="stat">
                Maximum task value:
                <b>{p["total"]:,} ETB</b>
            </div>

            <a class="btn"
               href="/plans/{p['name'].replace(' ','-')}">
               View Plan
            </a>

        </div>
        """

    return page(f"""
    <div class="balance">

        <div>Available Wallet Balance</div>

        <div class="num">
            {u["balance"]:,.2f} ETB
        </div>

        <div>
            Total earned:
            {u["total_earned"]:,.2f} ETB
        </div>

    </div>

    <div class="grid">

        <a class="btn" href="/jobs">💼 Jobs</a>
        <a class="btn" href="/wallet">💰 Wallet</a>
        <a class="btn" href="/withdraw">💸 Withdraw</a>
        <a class="btn" href="/my">👤 My</a>

    </div>

    <div class="card">
        <h2>Plans</h2>
        <p class="small">
            Work/task packages
        </p>

        {plans_html}
    </div>

    <a class="btn red" href="/logout">Logout</a>
    """)


# -------------------------------------------------
# PLAN DETAILS
# -------------------------------------------------

@app.route("/plans/<plan_name>")
def plan_details(plan_name):

    u = user()

    if not u:
        return redirect("/login")

    selected = None

    for p in PLANS:
        if p["name"].replace(" ","-") == plan_name:
            selected = p
            break

    if not selected:
        return redirect("/dashboard")

    return page(f"""
    <div class="card">

        <h2>{selected["name"]}</h2>

        <div class="price">
            {selected["price"]:,} ETB
        </div>

        <p>
            {selected["description"]}
        </p>

        <div class="stat">
            Daily task target:
            <b>{selected["daily"]:,} ETB</b>
        </div>

        <div class="stat">
            Duration:
            <b>{selected["days"]} days</b>
        </div>

        <div class="stat">
            Maximum task value:
            <b>{selected["total"]:,} ETB</b>
        </div>

        <div class="notice">
            Earnings depend on completed and approved work.
            They are not guaranteed investment returns.
        </div>

        <a class="btn" href="/jobs">
            Find Jobs
        </a>

        <a class="btn gray" href="/dashboard">
            Back
        </a>

    </div>
    """)


# -------------------------------------------------
# JOBS
# -------------------------------------------------

@app.route("/jobs")
def jobs():

    u = user()

    if not u:
        return redirect("/login")

    con = db()

    jobs = con.execute(
        "SELECT * FROM jobs ORDER BY id DESC"
    ).fetchall()

    con.close()

    html = ""

    for j in jobs:

        html += f"""
        <div class="job">

            <h3>{j["title"]}</h3>

            <p>{j["description"]}</p>

            <div class="stat">
                Task value:
                <b>{j["reward"]:,.2f} ETB</b>
            </div>

            <a class="btn"
               href="/apply/{j['id']}">
               Apply
            </a>

        </div>
        """

    return page(f"""
    <div class="card">
        <h2>💼 Available Jobs</h2>
        {html}
        <a class="btn gray" href="/dashboard">Back</a>
    </div>
    """)


# -------------------------------------------------
# APPLY
# -------------------------------------------------

@app.route("/apply/<int:job_id>")
def apply(job_id):

    u = user()

    if not u:
        return redirect("/login")

    con = db()

    job = con.execute(
        "SELECT * FROM jobs WHERE id=?",
        (job_id,)
    ).fetchone()

    if job:

        con.execute(
            """
            INSERT INTO applications
            (user_id,job_id,created_at)
            VALUES (?,?,?)
            """,
            (
                u["id"],
                job_id,
                datetime.now().isoformat()
            )
        )

        con.execute(
            """
            INSERT INTO messages
            (user_id,message,created_at)
            VALUES (?,?,?)
            """,
            (
                u["id"],
                "Your job application is pending review.",
                datetime.now().isoformat()
            )
        )

        con.commit()

    con.close()

    return redirect("/jobs")


# -------------------------------------------------
# WALLET
# -------------------------------------------------

@app.route("/wallet")
def wallet():

    u = user()

    if not u:
        return redirect("/login")

    return page(f"""
    <div class="card">

        <h2>💰 Wallet</h2>

        <div class="balance">
            <div>Balance</div>
            <div class="num">
                {u["balance"]:,.2f} ETB
            </div>
        </div>

        <div class="stat">
            Total earned:
            <b>{u["total_earned"]:,.2f} ETB</b>
        </div>

        <a class="btn" href="/transactions">
            Transaction History
        </a>

        <a class="btn green" href="/withdraw">
            Withdraw
        </a>

        <a class="btn gray" href="/dashboard">
            Back
        </a>

    </div>
    """)


# -------------------------------------------------
# WITHDRAW
# -------------------------------------------------

@app.route("/withdraw", methods=["GET","POST"])
def withdraw():

    u = user()

    if not u:
        return redirect("/login")

    message = ""

    if request.method == "POST":

        try:
            amount = float(
                request.form.get("amount",0)
            )
        except ValueError:
            amount = 0

        bank = request.form.get("bank","").strip()
        account = request.form.get("account","").strip()

        if amount < 200:
            message = "Minimum withdrawal amount is 200 ETB."

        elif amount > u["balance"]:
            message = "Insufficient available balance."

        elif not bank or not account:
            message = "Enter bank and account details."

        else:

            con = db()

            con.execute(
                """
                UPDATE users
                SET balance=balance-?
                WHERE id=?
                """,
                (amount,u["id"])
            )

            con.execute(
                """
                INSERT INTO transactions
                (user_id,kind,amount,status,note,created_at)
                VALUES (?,?,?,?,?,?)
                """,
                (
                    u["id"],
                    "Withdrawal",
                    amount,
                    "Pending",
                    f"{bank} / {account}",
                    datetime.now().isoformat()
                )
            )

            con.commit()
            con.close()

            message = (
                "Withdrawal request submitted. "
                "It is pending review."
            )

    return page(f"""
    <div class="card">

        <h2>💸 Withdraw</h2>

        <div class="notice">
            Minimum withdrawal amount:
            <b>200 ETB</b>
        </div>

        {"<div class='notice success'>"+message+"</div>"
         if message else ""}

        <form method="post">

            <input
                type="number"
                name="amount"
                min="200"
                step="0.01"
                placeholder="Withdrawal amount"
                required
            >

            <input
                name="bank"
                placeholder="Bank name"
                required
            >

            <input
                name="account"
                placeholder="Account number / wallet"
                required
            >

            <button class="green">
                Submit Withdrawal
            </button>

        </form>

        <p class="small">
            Requests are reviewed according to the platform's
            payment policy.
        </p>

        <a class="btn gray" href="/wallet">
            Back
        </a>

    </div>
    """)


# -------------------------------------------------
# TRANSACTIONS
# -------------------------------------------------

@app.route("/transactions")
def transactions():

    u = user()

    if not u:
        return redirect("/login")

    con = db()

    rows = con.execute(
        """
        SELECT * FROM transactions
        WHERE user_id=?
        ORDER BY id DESC
        """,
        (u["id"],)
    ).fetchall()

    con.close()

    html = ""

    for r in rows:

        html += f"""
        <div class="job">
            <b>{r["kind"]}</b><br>
            Amount:
            {r["amount"]:,.2f} ETB<br>
            Status:
            <b>{r["status"]}</b><br>
            <span class="small">
                {r["created_at"]}
            </span>
        </div>
        """

    if not html:
        html = "<p>No transactions yet.</p>"

    return page(f"""
    <div class="card">
        <h2>📊 Transactions</h2>

        {html}

        <a class="btn gray" href="/wallet">
            Back
        </a>
    </div>
    """)


# -------------------------------------------------
# MY
# -------------------------------------------------

@app.route("/my")
def my():

    u = user()

    if not u:
        return redirect("/login")

    return page(f"""
    <div class="card">

        <h2>👤 My Account</h2>

        <div class="stat">
            Username:
            <b>{u["username"]}</b>
        </div>

        <div class="stat">
            Balance:
            <b>{u["balance"]:,.2f} ETB</b>
        </div>

        <div class="stat">
            Total earned:
            <b>{u["total_earned"]:,.2f} ETB</b>
        </div>

        <a class="menu" href="/messages">
            💬 Messages
        </a>

        <a class="menu" href="/jobs">
            💼 My Jobs
        </a>

        <a class="menu" href="/transactions">
            📊 Income / Transaction Details
        </a>

        <a class="menu" href="/withdraw">
            💸 Withdrawal Details
        </a>

        <a class="menu" href="/about">
            ℹ️ About NEXA
        </a>

        <a class="btn gray" href="/dashboard">
            Dashboard
        </a>

        <a class="btn red" href="/logout">
            Logout
        </a>

    </div>
    """)


# -------------------------------------------------
# MESSAGES
# -------------------------------------------------

@app.route("/messages")
def messages():

    u = user()

    if not u:
        return redirect("/login")

    con = db()

    rows = con.execute(
        """
        SELECT * FROM messages
        WHERE user_id=?
        ORDER BY id DESC
        """,
        (u["id"],)
    ).fetchall()

    con.close()

    html = ""

    for r in rows:
        html += f"""
        <div class="notice">
            {r["message"]}
            <br>
            <span class="small">
                {r["created_at"]}
            </span>
        </div>
        """

    if not html:
        html = """
        <div class="notice">
            No messages yet.
        </div>
        """

    return page(f"""
    <div class="card">

        <h2>💬 Messages</h2>

        {html}

        <a class="btn gray" href="/my">
            Back
        </a>

    </div>
    """)


# -------------------------------------------------
# ABOUT
# -------------------------------------------------

@app.route("/about")
def about():

    return page("""
    <div class="card">

        <h2>About NEXA</h2>

        <p>
            NEXA is a jobs and digital services platform
            designed to connect users with work opportunities.
        </p>

        <p>
            Earnings are connected to completed and approved
            work or services.
        </p>

        <a class="btn gray" href="/my">
            Back
        </a>

    </div>
    """)


# -------------------------------------------------
# LOGOUT
# -------------------------------------------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# -------------------------------------------------
# RUN
# -------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
