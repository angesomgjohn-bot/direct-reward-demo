from flask import Flask, request, redirect, url_for, session, render_template_string, flash
import sqlite3
import os
import secrets
from datetime import datetime
from urllib.parse import quote
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "CHANGE_THIS_SECRET_KEY")
DB = os.environ.get("DB_PATH", "nexa.db")

# ============================================================
# NEXA SETTINGS
# Put real values in Render Environment Variables.
# ============================================================
BANK_NAME = os.environ.get("BANK_NAME", "Commercial Bank of Ethiopia (CBE)")
BANK_ACCOUNT_NAME = os.environ.get("BANK_ACCOUNT_NAME", "YOUR ACCOUNT NAME")
BANK_ACCOUNT_NUMBER = os.environ.get("BANK_ACCOUNT_NUMBER", "YOUR ACCOUNT NUMBER")

OFFICIAL_TELEGRAM_URL = os.environ.get(
    "OFFICIAL_TELEGRAM_URL", "https://t.me/NexaOfficial_1"
)
CUSTOMER_SERVICE_URL = os.environ.get(
    "CUSTOMER_SERVICE_URL", OFFICIAL_TELEGRAM_URL
)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "CHANGE_ADMIN_PASSWORD")

MIN_DEPOSIT = float(os.environ.get("MIN_DEPOSIT", "10"))
MIN_WITHDRAWAL = 200.0

# These are the plans already present in the original app.py.
PLANS = [
    {
        "id": "A", "name": "Plan A", "price": 500,
        "tasks": [("Task 1", 20), ("Task 2", 25), ("Task 3", 25)]
    },
    {
        "id": "B", "name": "Plan B", "price": 1000,
        "tasks": [("Task 1", 45), ("Task 2", 45), ("Task 3", 50)]
    },
    {
        "id": "C", "name": "Plan C", "price": 2000,
        "tasks": [("Task 1", 70), ("Task 2", 70), ("Task 3", 90)]
    },
    {
        "id": "D", "name": "Plan D", "price": 5000,
        "tasks": [("Task 1", 120), ("Task 2", 120), ("Task 3", 160)]
    }
]


# ============================================================
# DATABASE
# Compatible with the original users/tasks/history tables.
# ============================================================
def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def utcnow():
    return datetime.utcnow().isoformat(timespec="seconds")


def init_db():
    conn = db()

    # Original tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            referral_code TEXT UNIQUE NOT NULL,
            referred_by TEXT,
            balance REAL DEFAULT 0,
            total_earned REAL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_id TEXT NOT NULL,
            task_name TEXT NOT NULL,
            reward REAL NOT NULL,
            completed INTEGER DEFAULT 0,
            available_at TEXT NOT NULL,
            completed_at TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            amount REAL DEFAULT 0,
            note TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # New tables for verified deposits / withdrawals / plans
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            transaction_id TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            note TEXT,
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            reviewed_by TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_id TEXT NOT NULL,
            plan_name TEXT NOT NULL,
            price REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            bank_name TEXT NOT NULL,
            account_name TEXT NOT NULL,
            account_number TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            note TEXT,
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            reviewed_by TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


# ============================================================
# HELPERS
# ============================================================
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None

    conn = db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (uid,)
    ).fetchone()
    conn.close()
    return user


def is_admin():
    return session.get("admin") is True


def money(x):
    return f"{float(x):,.2f}"


def add_history(conn, user_id, action, amount=0, note=""):
    conn.execute("""
        INSERT INTO history(user_id, action, amount, note, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, action, amount, note, utcnow()))


def get_plan(plan_id):
    return next((p for p in PLANS if p["id"] == plan_id), None)


def referral_link(user):
    return request.host_url.rstrip("/") + "/register?ref=" + quote(
        user["referral_code"]
    )


# ============================================================
# SELF-CONTAINED UI
# This removes the old dependency on a missing templates folder.
# ============================================================
SHELL = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NEXA Rewards</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#f4f7fb;color:#172033;font-family:Arial,sans-serif}
nav{background:#101828;color:white;padding:12px 14px;position:sticky;top:0;z-index:20}
.nav{max-width:1100px;margin:auto;display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.brand{font-size:25px;font-weight:900}
nav a{color:white;text-decoration:none;margin:4px 6px;font-size:13px}
.wrap{max-width:1100px;margin:20px auto;padding:0 13px}
.hero{background:linear-gradient(135deg,#111827,#294777);color:white;padding:25px;border-radius:20px;margin-bottom:18px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:15px}
.card{background:white;border-radius:18px;padding:20px;margin-bottom:17px;box-shadow:0 5px 22px rgba(16,24,40,.07)}
.balance{font-size:30px;font-weight:900}
.small{font-size:13px;color:#667085}
.btn,button{display:inline-block;background:#175cd3;color:white;border:0;border-radius:9px;padding:11px 15px;text-decoration:none;cursor:pointer}
.green{background:#079455}.red{background:#d92d20}.gray{background:#667085}
input,select,textarea{width:100%;padding:12px;border:1px solid #d0d5dd;border-radius:9px;margin:6px 0 13px;font-size:15px}
.notice{padding:12px;border-radius:10px;background:#eef4ff;margin:10px 0}
.success{background:#dcfae6}.error{background:#fee4e2}
.bank{border-left:5px solid #175cd3;background:#eef7ff}
.plan{border:1px solid #e4e7ec}
.badge{display:inline-block;padding:5px 9px;border-radius:20px;background:#eef4ff;font-size:12px}
.pending{background:#fff4cc}.approved{background:#dcfae6}.rejected{background:#fee4e2}
table{width:100%;border-collapse:collapse}
th,td{padding:10px;border-bottom:1px solid #eaecf0;text-align:left;vertical-align:top}
.tablewrap{overflow-x:auto}
.actionform{display:inline-block;margin:2px}
@media(max-width:650px){.card{padding:16px}.balance{font-size:26px}nav a{font-size:12px}}
</style>
</head>
<body>
<nav>
<div class="nav">
<div class="brand">NEXA</div>
<div>
{% if admin %}
<a href="{{ url_for('admin') }}">Admin</a>
<a href="{{ url_for('admin_logout') }}">Logout</a>
{% elif user %}
<a href="{{ url_for('home') }}">Dashboard</a>
<a href="{{ url_for('plans') }}">Plans</a>
<a href="{{ url_for('deposit') }}">Deposit</a>
<a href="{{ url_for('withdraw') }}">Withdraw</a>
<a href="{{ url_for('referral') }}">Referral</a>
<a href="{{ url_for('history') }}">History</a>
<a href="{{ url_for('support') }}">Customer Service</a>
<a href="{{ url_for('channel') }}">Telegram</a>
<a href="{{ url_for('logout') }}">Logout</a>
{% else %}
<a href="{{ url_for('login') }}">Login</a>
<a href="{{ url_for('register') }}">Register</a>
<a href="{{ url_for('support') }}">Customer Service</a>
<a href="{{ url_for('channel') }}">Telegram</a>
{% endif %}
</div>
</div>
</nav>
<div class="wrap">
{% with messages=get_flashed_messages(with_categories=true) %}
{% for category,message in messages %}
<div class="notice {% if category=='success' %}success{% elif category=='error' %}error{% endif %}">{{message}}</div>
{% endfor %}
{% endwith %}
{{ content|safe }}
</div>
</body>
</html>
"""


def render_page(content):
    return render_template_string(
        SHELL,
        content=content,
        user=current_user(),
        admin=is_admin()
    )


# ============================================================
# HOME / AUTH
# ============================================================
@app.route("/")
def home():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = db()
    tasks = conn.execute("""
        SELECT * FROM tasks
        WHERE user_id=?
        ORDER BY id DESC
    """, (user["id"],)).fetchall()

    active_plans = conn.execute("""
        SELECT * FROM user_plans
        WHERE user_id=? AND status='active'
        ORDER BY id DESC
    """, (user["id"],)).fetchall()

    history_rows = conn.execute("""
        SELECT * FROM history
        WHERE user_id=?
        ORDER BY id DESC LIMIT 20
    """, (user["id"],)).fetchall()
    conn.close()

    plans_html = "".join(
        f"""<tr><td>{p['plan_name']}</td><td>{money(p['price'])} ETB</td>
        <td><span class="badge approved">Active</span></td>
        <td>{p['created_at']}</td></tr>"""
        for p in active_plans
    ) or "<tr><td colspan='4'>No active plans yet.</td></tr>"

    tasks_html = "".join(
        f"""<tr>
        <td>{t['plan_id']}</td>
        <td>{t['task_name']}</td>
        <td>{money(t['reward'])} ETB</td>
        <td>{'<span class="badge approved">Completed</span>' if t['completed'] else
        f'<form method="post" action="/complete-task/{t["id"]}"><button class="green">Complete</button></form>'}</td>
        </tr>"""
        for t in tasks
    ) or "<tr><td colspan='4'>No tasks yet. Activate a plan first.</td></tr>"

    hist_html = "".join(
        f"<tr><td>{h['created_at']}</td><td>{h['action']}</td><td>{money(h['amount'])}</td><td>{h['note'] or ''}</td></tr>"
        for h in history_rows
    ) or "<tr><td colspan='4'>No history yet.</td></tr>"

    return render_page(f"""
    <div class="grid">
      <div class="card"><div class="small">Wallet balance</div>
      <div class="balance">{money(user['balance'])} ETB</div></div>
      <div class="card"><div class="small">Total earned</div>
      <div class="balance">{money(user['total_earned'])} ETB</div></div>
      <div class="card"><div class="small">Referral code</div>
      <div class="balance" style="font-size:22px">{user['referral_code']}</div></div>
    </div>

    <div class="grid">
      <a class="card" style="text-decoration:none;color:inherit" href="/plans">
        <h2>📦 Plans</h2><p>View Plan A, B, C and D.</p>
      </a>
      <a class="card" style="text-decoration:none;color:inherit" href="/deposit">
        <h2>💳 Deposit</h2><p>Send money to the bank account and submit the transaction ID.</p>
      </a>
      <a class="card" style="text-decoration:none;color:inherit" href="/withdraw">
        <h2>💸 Withdraw</h2><p>Minimum withdrawal is 200 ETB.</p>
      </a>
      <a class="card" style="text-decoration:none;color:inherit" href="/referral">
        <h2>🔗 Referral</h2><p>Share your personal referral link.</p>
      </a>
      <a class="card" style="text-decoration:none;color:inherit" href="/support">
        <h2>🎧 Customer Service</h2><p>Get help from customer service.</p>
      </a>
      <a class="card" style="text-decoration:none;color:inherit" href="/channel">
        <h2>📢 Official Telegram</h2><p>Open the official channel.</p>
      </a>
    </div>

    <div class="card">
      <h2>Active Plans</h2>
      <div class="tablewrap"><table>
      <tr><th>Plan</th><th>Price</th><th>Status</th><th>Date</th></tr>
      {plans_html}
      </table></div>
    </div>

    <div class="card">
      <h2>Your Tasks</h2>
      <div class="tablewrap"><table>
      <tr><th>Plan</th><th>Task</th><th>Reward</th><th>Action</th></tr>
      {tasks_html}
      </table></div>
    </div>

    <div class="card">
      <h2>Recent History</h2>
      <div class="tablewrap"><table>
      <tr><th>Date</th><th>Action</th><th>Amount</th><th>Note</th></tr>
      {hist_html}
      </table></div>
    </div>
    """)


@app.route("/register", methods=["GET", "POST"])
def register():
    referral = request.args.get("ref", "").strip()

    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()
        referral = request.form.get("referral", "").strip()

        if not phone or not password:
            flash("Phone/username and password are required.", "error")
            return redirect(url_for("register"))

        referral_code = secrets.token_hex(4).upper()
        conn = db()
        try:
            conn.execute("""
                INSERT INTO users
                (phone,password,referral_code,referred_by,created_at)
                VALUES (?,?,?,?,?)
            """, (
                phone,
                generate_password_hash(password),
                referral_code,
                referral or None,
                utcnow()
            ))
            conn.commit()

            user = conn.execute(
                "SELECT * FROM users WHERE phone=?",
                (phone,)
            ).fetchone()

            add_history(
                conn, user["id"], "ACCOUNT_CREATED", 0,
                "NEXA account created"
            )
            conn.commit()
            conn.close()

            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("home"))

        except sqlite3.IntegrityError:
            conn.close()
            flash("This phone/username is already registered.", "error")

    return render_page(f"""
    <div class="card">
      <h2>Create NEXA account</h2>
      <form method="post">
        <label>Phone / Username</label>
        <input name="phone" required>
        <label>Password</label>
        <input name="password" type="password" minlength="4" required>
        <label>Referral code (optional)</label>
        <input name="referral" value="{referral}">
        <button>Register</button>
      </form>
    </div>
    """)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        conn = db()
        user = conn.execute(
            "SELECT * FROM users WHERE phone=?",
            (phone,)
        ).fetchone()
        conn.close()

        valid = False
        if user:
            # Supports BOTH old plaintext passwords and new hashed passwords.
            stored = user["password"]
            try:
                valid = check_password_hash(stored, password)
            except Exception:
                valid = stored == password

        if valid:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("home"))

        flash("Invalid phone/username or password.", "error")

    return render_page("""
    <div class="card">
      <h2>Login</h2>
      <form method="post">
        <label>Phone / Username</label>
        <input name="phone" required>
        <label>Password</label>
        <input name="password" type="password" required>
        <button>Login</button>
      </form>
    </div>
    """)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ============================================================
# PLANS
# ============================================================
@app.route("/plans")
def plans():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    cards = ""
    for p in PLANS:
        rewards = sum(r for _, r in p["tasks"])
        tasks = "".join(
            f"<li>{name}: <b>{money(reward)} ETB</b></li>"
            for name, reward in p["tasks"]
        )
        cards += f"""
        <div class="card plan">
          <h2>{p['name']}</h2>
          <div class="balance">{money(p['price'])} ETB</div>
          <p>Total task rewards: <b>{money(rewards)} ETB</b></p>
          <ul>{tasks}</ul>
          <form method="post" action="/start-plan/{p['id']}">
            <button>Activate {p['name']}</button>
          </form>
        </div>
        """

    return render_page(f"""
    <div class="hero">
      <h1>Plans</h1>
      <p>Verified deposit balance is required to activate a plan.</p>
    </div>
    <div class="grid">{cards}</div>
    """)


@app.post("/start-plan/<plan_id>")
def start_plan(plan_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    plan = get_plan(plan_id)
    if not plan:
        flash("Plan not found.", "error")
        return redirect(url_for("plans"))

    conn = db()

    existing = conn.execute("""
        SELECT id FROM user_plans
        WHERE user_id=? AND plan_id=? AND status='active'
    """, (user["id"], plan_id)).fetchone()

    if existing:
        conn.close()
        flash("This plan is already active.", "error")
        return redirect(url_for("plans"))

    current = conn.execute(
        "SELECT balance FROM users WHERE id=?",
        (user["id"],)
    ).fetchone()

    if current["balance"] < plan["price"]:
        conn.close()
        flash(
            f"You need {money(plan['price'])} ETB in verified balance first.",
            "error"
        )
        return redirect(url_for("deposit"))

    # Deduct plan price from wallet.
    conn.execute(
        "UPDATE users SET balance=balance-? WHERE id=?",
        (plan["price"], user["id"])
    )

    cur = conn.execute("""
        INSERT INTO user_plans
        (user_id,plan_id,plan_name,price,status,created_at)
        VALUES (?,?,?,?,?,?)
    """, (
        user["id"], plan["id"], plan["name"],
        plan["price"], "active", utcnow()
    ))
    plan_row_id = cur.lastrowid

    for task_name, reward in plan["tasks"]:
        conn.execute("""
            INSERT INTO tasks
            (user_id,plan_id,task_name,reward,completed,available_at)
            VALUES (?,?,?,?,0,?)
        """, (
            user["id"], plan["id"], task_name, reward, utcnow()
        ))

    add_history(
        conn, user["id"], "PLAN_ACTIVATED",
        -plan["price"], f"{plan['name']} activated"
    )

    conn.commit()
    conn.close()

    flash(f"{plan['name']} activated successfully.", "success")
    return redirect(url_for("home"))


@app.post("/complete-task/<int:task_id>")
def complete_task(task_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = db()
    task = conn.execute("""
        SELECT * FROM tasks
        WHERE id=? AND user_id=?
    """, (task_id, user["id"])).fetchone()

    if not task or task["completed"]:
        conn.close()
        flash("Task not found or already completed.", "error")
        return redirect(url_for("home"))

    # Original app used available_at; keep that behavior.
    available = datetime.fromisoformat(task["available_at"])
    if datetime.utcnow() < available:
        conn.close()
        flash("This task is not available yet.", "error")
        return redirect(url_for("home"))

    conn.execute("""
        UPDATE tasks
        SET completed=1, completed_at=?
        WHERE id=?
    """, (utcnow(), task_id))

    conn.execute("""
        UPDATE users
        SET balance=balance+?, total_earned=total_earned+?
        WHERE id=?
    """, (task["reward"], task["reward"], user["id"]))

    add_history(
        conn, user["id"], "TASK_REWARD",
        task["reward"], f"Completed {task['task_name']}"
    )

    conn.commit()
    conn.close()

    flash(
        f"{money(task['reward'])} ETB reward added to your wallet.",
        "success"
    )
    return redirect(url_for("home"))


# ============================================================
# DEPOSIT
# ============================================================
@app.route("/deposit", methods=["GET", "POST"])
def deposit():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", "0"))
        except ValueError:
            amount = 0

        transaction_id = request.form.get(
            "transaction_id", ""
        ).strip()
        note = request.form.get("note", "").strip()

        if amount < MIN_DEPOSIT:
            flash(
                f"Minimum deposit is {money(MIN_DEPOSIT)} ETB.",
                "error"
            )
            return redirect(url_for("deposit"))

        if not transaction_id:
            flash("Transaction/reference number is required.", "error")
            return redirect(url_for("deposit"))

        conn = db()
        try:
            conn.execute("""
                INSERT INTO deposits
                (user_id,amount,transaction_id,status,note,created_at)
                VALUES (?,?,?,?,?,?)
            """, (
                user["id"], amount, transaction_id,
                "pending", note, utcnow()
            ))
            conn.commit()
            flash(
                "Deposit submitted. Admin must verify it before your wallet is credited.",
                "success"
            )
        except sqlite3.IntegrityError:
            flash(
                "This transaction/reference number has already been submitted.",
                "error"
            )
        finally:
            conn.close()

        return redirect(url_for("deposit"))

    conn = db()
    rows = conn.execute("""
        SELECT * FROM deposits
        WHERE user_id=? ORDER BY id DESC LIMIT 30
    """, (user["id"],)).fetchall()
    conn.close()

    html = "".join(
        f"""<tr>
        <td>{money(d['amount'])} ETB</td>
        <td>{d['transaction_id']}</td>
        <td><span class="badge {d['status']}">{d['status']}</span></td>
        <td>{d['created_at']}</td>
        </tr>"""
        for d in rows
    ) or "<tr><td colspan='4'>No deposits submitted yet.</td></tr>"

    return render_page(f"""
    <div class="card bank">
      <h2>💳 Deposit</h2>
      <p><b>Bank:</b> {BANK_NAME}</p>
      <p><b>Account name:</b> {BANK_ACCOUNT_NAME}</p>
      <p><b>Account number:</b> {BANK_ACCOUNT_NUMBER}</p>
      <hr>
      <p>1. Send money to the account above.</p>
      <p>2. Keep the bank receipt/reference number.</p>
      <p>3. Enter the amount and transaction/reference number below.</p>
      <p><b>Your balance is credited only after admin verification.</b></p>
    </div>

    <div class="card">
      <h2>Submit Deposit</h2>
      <form method="post">
        <label>Amount (ETB)</label>
        <input name="amount" type="number" min="{MIN_DEPOSIT}" step="0.01" required>
        <label>Transaction / Reference Number</label>
        <input name="transaction_id" required>
        <label>Note (optional)</label>
        <textarea name="note"></textarea>
        <button>Submit Deposit</button>
      </form>
    </div>

    <div class="card">
      <h2>My Deposit Requests</h2>
      <div class="tablewrap"><table>
      <tr><th>Amount</th><th>Reference</th><th>Status</th><th>Date</th></tr>
      {html}
      </table></div>
    </div>
    """)


# ============================================================
# WITHDRAWAL
# ============================================================
@app.route("/withdraw", methods=["GET", "POST"])
def withdraw():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", "0"))
        except ValueError:
            amount = 0

        bank_name = request.form.get("bank_name", "").strip()
        account_name = request.form.get("account_name", "").strip()
        account_number = request.form.get("account_number", "").strip()
        note = request.form.get("note", "").strip()

        if amount < MIN_WITHDRAWAL:
            flash("Minimum withdrawal is 200 ETB.", "error")
            return redirect(url_for("withdraw"))

        if not bank_name or not account_name or not account_number:
            flash(
                "Bank name, account name and account number are required.",
                "error"
            )
            return redirect(url_for("withdraw"))

        conn = db()
        current = conn.execute(
            "SELECT balance FROM users WHERE id=?",
            (user["id"],)
        ).fetchone()

        if current["balance"] < amount:
            conn.close()
            flash("Insufficient wallet balance.", "error")
            return redirect(url_for("withdraw"))

        # Reserve the amount while the request is pending.
        conn.execute("""
            UPDATE users SET balance=balance-? WHERE id=?
        """, (amount, user["id"]))

        conn.execute("""
            INSERT INTO withdrawals
            (user_id,amount,bank_name,account_name,account_number,status,note,created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            user["id"], amount, bank_name, account_name,
            account_number, "pending", note, utcnow()
        ))

        add_history(
            conn, user["id"], "WITHDRAWAL_PENDING",
            -amount, "Withdrawal request submitted"
        )

        conn.commit()
        conn.close()

        flash(
            "Withdrawal request submitted for admin review.",
            "success"
        )
        return redirect(url_for("withdraw"))

    conn = db()
    rows = conn.execute("""
        SELECT * FROM withdrawals
        WHERE user_id=? ORDER BY id DESC LIMIT 30
    """, (user["id"],)).fetchall()
    conn.close()

    html = "".join(
        f"""<tr>
        <td>{money(w['amount'])} ETB</td>
        <td>{w['bank_name']}<br>{w['account_name']}<br>{w['account_number']}</td>
        <td><span class="badge {w['status']}">{w['status']}</span></td>
        <td>{w['created_at']}</td>
        </tr>"""
        for w in rows
    ) or "<tr><td colspan='4'>No withdrawal requests yet.</td></tr>"

    return render_page(f"""
    <div class="card">
      <h2>💸 Withdraw</h2>
      <div class="notice">
        <b>Minimum withdrawal: 200 ETB</b><br>
        Available balance: {money(user['balance'])} ETB
      </div>
      <form method="post">
        <label>Amount (ETB)</label>
        <input name="amount" type="number" min="200" step="0.01" required>
        <label>Bank name</label>
        <input name="bank_name" required>
        <label>Account name</label>
        <input name="account_name" required>
        <label>Account number</label>
        <input name="account_number" required>
        <label>Note (optional)</label>
        <textarea name="note"></textarea>
        <button>Submit Withdrawal</button>
      </form>
    </div>

    <div class="card">
      <h2>My Withdrawals</h2>
      <div class="tablewrap"><table>
      <tr><th>Amount</th><th>Destination</th><th>Status</th><th>Date</th></tr>
      {html}
      </table></div>
    </div>
    """)


# ============================================================
# REFERRAL / CUSTOMER SERVICE / TELEGRAM
# ============================================================
@app.route("/referral")
def referral():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    link = referral_link(user)
    return render_page(f"""
    <div class="card">
      <h2>🔗 Referral</h2>
      <p>Your referral code:</p>
      <h1>{user['referral_code']}</h1>
      <p>Your referral link:</p>
      <input value="{link}" readonly onclick="this.select()">
      <a class="btn" target="_blank"
         href="https://t.me/share/url?url={quote(link)}&text={quote('Join NEXA Rewards')}">
         Share on Telegram
      </a>
    </div>
    """)


@app.route("/support")
def support():
    return render_page(f"""
    <div class="card">
      <h2>🎧 Customer Service</h2>
      <p>For deposit, plan, task or withdrawal support, contact customer service.</p>
      <a class="btn" href="{CUSTOMER_SERVICE_URL}" target="_blank">
        Contact Customer Service
      </a>
    </div>
    <div class="card">
      <h2>📢 Official Telegram Channel</h2>
      <p>Follow the official NEXA channel for announcements and updates.</p>
      <a class="btn" href="{OFFICIAL_TELEGRAM_URL}" target="_blank">
        Open Official Telegram
      </a>
    </div>
    """)


@app.route("/channel")
def channel():
    return redirect(OFFICIAL_TELEGRAM_URL)


@app.route("/history")
def history():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = db()
    rows = conn.execute("""
        SELECT * FROM history
        WHERE user_id=? ORDER BY id DESC LIMIT 100
    """, (user["id"],)).fetchall()
    conn.close()

    html = "".join(
        f"<tr><td>{h['created_at']}</td><td>{h['action']}</td><td>{money(h['amount'])}</td><td>{h['note'] or ''}</td></tr>"
        for h in rows
    ) or "<tr><td colspan='4'>No history yet.</td></tr>"

    return render_page(f"""
    <div class="card">
      <h2>Transaction History</h2>
      <div class="tablewrap"><table>
      <tr><th>Date</th><th>Action</th><th>Amount</th><th>Note</th></tr>
      {html}
      </table></div>
    </div>
    """)


# ============================================================
# ADMIN
# ============================================================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.clear()
            session["admin"] = True
            return redirect(url_for("admin"))

        flash("Invalid admin credentials.", "error")

    return render_page("""
    <div class="card">
      <h2>Admin Login</h2>
      <form method="post">
        <label>Admin username</label>
        <input name="username" required>
        <label>Admin password</label>
        <input name="password" type="password" required>
        <button>Login</button>
      </form>
    </div>
    """)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin")
def admin():
    if not is_admin():
        return redirect(url_for("admin_login"))

    conn = db()

    deposits = conn.execute("""
        SELECT d.*,u.phone
        FROM deposits d JOIN users u ON u.id=d.user_id
        WHERE d.status='pending'
        ORDER BY d.id ASC
    """).fetchall()

    withdrawals = conn.execute("""
        SELECT w.*,u.phone
        FROM withdrawals w JOIN users u ON u.id=w.user_id
        WHERE w.status='pending'
        ORDER BY w.id ASC
    """).fetchall()

    users = conn.execute("""
        SELECT id,phone,balance,total_earned,referral_code,created_at
        FROM users ORDER BY id DESC
    """).fetchall()

    conn.close()

    dhtml = "".join(
        f"""<tr>
        <td>{d['id']}</td><td>{d['phone']}</td>
        <td>{money(d['amount'])} ETB</td>
        <td>{d['transaction_id']}</td><td>{d['created_at']}</td>
        <td>
          <form class="actionform" method="post" action="/admin/deposit/{d['id']}/approve">
            <button class="green">Approve</button>
          </form>
          <form class="actionform" method="post" action="/admin/deposit/{d['id']}/reject">
            <button class="red">Reject</button>
          </form>
        </td>
        </tr>"""
        for d in deposits
    ) or "<tr><td colspan='6'>No pending deposits.</td></tr>"

    whtml = "".join(
        f"""<tr>
        <td>{w['id']}</td><td>{w['phone']}</td>
        <td>{money(w['amount'])} ETB</td>
        <td>{w['bank_name']}<br>{w['account_name']}<br>{w['account_number']}</td>
        <td>{w['created_at']}</td><td>
          <form class="actionform" method="post" action="/admin/withdraw/{w['id']}/approve">
            <button class="green">Approve</button>
          </form>
          <form class="actionform" method="post" action="/admin/withdraw/{w['id']}/reject">
            <button class="red">Reject</button>
          </form>
        </td></tr>"""
        for w in withdrawals
    ) or "<tr><td colspan='6'>No pending withdrawals.</td></tr>"

    uhtml = "".join(
        f"""<tr>
        <td>{u['id']}</td><td>{u['phone']}</td>
        <td>{money(u['balance'])} ETB</td>
        <td>{money(u['total_earned'])} ETB</td>
        <td>{u['referral_code']}</td>
        <td>{u['created_at']}</td>
        </tr>"""
        for u in users
    )

    return render_page(f"""
    <div class="hero">
      <h1>NEXA Admin Panel</h1>
      <p>Verify deposits and review withdrawal requests.</p>
    </div>

    <div class="card">
      <h2>Pending Deposits</h2>
      <div class="tablewrap"><table>
      <tr><th>ID</th><th>User</th><th>Amount</th><th>Reference</th><th>Date</th><th>Action</th></tr>
      {dhtml}
      </table></div>
    </div>

    <div class="card">
      <h2>Pending Withdrawals</h2>
      <div class="tablewrap"><table>
      <tr><th>ID</th><th>User</th><th>Amount</th><th>Destination</th><th>Date</th><th>Action</th></tr>
      {whtml}
      </table></div>
    </div>

    <div class="card">
      <h2>Users</h2>
      <div class="tablewrap"><table>
      <tr><th>ID</th><th>User</th><th>Balance</th><th>Earned</th><th>Referral</th><th>Created</th></tr>
      {uhtml}
      </table></div>
    </div>
    """)


@app.post("/admin/deposit/<int:deposit_id>/approve")
def approve_deposit(deposit_id):
    if not is_admin():
        return redirect(url_for("admin_login"))

    conn = db()
    d = conn.execute(
        "SELECT * FROM deposits WHERE id=?",
        (deposit_id,)
    ).fetchone()

    if not d or d["status"] != "pending":
        conn.close()
        flash("Deposit not found or already reviewed.", "error")
        return redirect(url_for("admin"))

    conn.execute("""
        UPDATE deposits
        SET status='approved',reviewed_at=?,reviewed_by=?
        WHERE id=?
    """, (utcnow(), ADMIN_USERNAME, deposit_id))

    conn.execute("""
        UPDATE users SET balance=balance+?
        WHERE id=?
    """, (d["amount"], d["user_id"]))

    add_history(
        conn, d["user_id"], "DEPOSIT_APPROVED",
        d["amount"], f"Verified transaction: {d['transaction_id']}"
    )

    conn.commit()
    conn.close()

    flash("Deposit approved and wallet credited.", "success")
    return redirect(url_for("admin"))


@app.post("/admin/deposit/<int:deposit_id>/reject")
def reject_deposit(deposit_id):
    if not is_admin():
        return redirect(url_for("admin_login"))

    conn = db()
    d = conn.execute(
        "SELECT * FROM deposits WHERE id=?",
        (deposit_id,)
    ).fetchone()

    if d and d["status"] == "pending":
        conn.execute("""
            UPDATE deposits
            SET status='rejected',reviewed_at=?,reviewed_by=?
            WHERE id=?
        """, (utcnow(), ADMIN_USERNAME, deposit_id))

        add_history(
            conn, d["user_id"], "DEPOSIT_REJECTED",
            0, f"Rejected transaction: {d['transaction_id']}"
        )
        conn.commit()
        flash("Deposit rejected.", "success")
    else:
        flash("Deposit not found or already reviewed.", "error")

    conn.close()
    return redirect(url_for("admin"))


@app.post("/admin/withdraw/<int:withdrawal_id>/approve")
def approve_withdrawal(withdrawal_id):
    if not is_admin():
        return redirect(url_for("admin_login"))

    conn = db()
    w = conn.execute(
        "SELECT * FROM withdrawals WHERE id=?",
        (withdrawal_id,)
    ).fetchone()

    if not w or w["status"] != "pending":
        conn.close()
        flash("Withdrawal not found or already reviewed.", "error")
        return redirect(url_for("admin"))

    conn.execute("""
        UPDATE withdrawals
        SET status='approved',reviewed_at=?,reviewed_by=?
        WHERE id=?
    """, (utcnow(), ADMIN_USERNAME, withdrawal_id))

    add_history(
        conn, w["user_id"], "WITHDRAWAL_APPROVED",
        -w["amount"],
        "Admin approved withdrawal; bank transfer must be completed."
    )

    conn.commit()
    conn.close()

    flash(
        "Withdrawal approved. Complete the bank transfer manually.",
        "success"
    )
    return redirect(url_for("admin"))


@app.post("/admin/withdraw/<int:withdrawal_id>/reject")
def reject_withdrawal(withdrawal_id):
    if not is_admin():
        return redirect(url_for("admin_login"))

    conn = db()
    w = conn.execute(
        "SELECT * FROM withdrawals WHERE id=?",
        (withdrawal_id,)
    ).fetchone()

    if w and w["status"] == "pending":
        conn.execute("""
            UPDATE withdrawals
            SET status='rejected',reviewed_at=?,reviewed_by=?
            WHERE id=?
        """, (utcnow(), ADMIN_USERNAME, withdrawal_id))

        # Return the reserved amount to the user's wallet.
        conn.execute("""
            UPDATE users SET balance=balance+?
            WHERE id=?
        """, (w["amount"], w["user_id"]))

        add_history(
            conn, w["user_id"], "WITHDRAWAL_REJECTED_REFUNDED",
            w["amount"], "Withdrawal rejected; amount returned to wallet."
        )

        conn.commit()
        flash("Withdrawal rejected and amount returned.", "success")
    else:
        flash("Withdrawal not found or already reviewed.", "error")

    conn.close()
    return redirect(url_for("admin"))


# ============================================================
# API / HEALTH
# ============================================================
@app.route("/api/status")
def status():
    user = current_user()
    if not user:
        return {"logged_in": False}

    return {
        "logged_in": True,
        "balance": user["balance"],
        "total_earned": user["total_earned"],
        "referral_code": user["referral_code"]
    }


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
