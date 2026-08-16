from flask import Flask, request, redirect, url_for, session, render_template_string, flash
import sqlite3
import os
import secrets
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

DB = os.environ.get("DB_PATH", "nexa.db")

# =========================
# SETTINGS
# =========================
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-admin-password")

BANK_NAME = os.environ.get("BANK_NAME", "Commercial Bank of Ethiopia (CBE)")
BANK_ACCOUNT_NAME = os.environ.get("BANK_ACCOUNT_NAME", "YOUR ACCOUNT NAME")
BANK_ACCOUNT_NUMBER = os.environ.get("BANK_ACCOUNT_NUMBER", "YOUR ACCOUNT NUMBER")

MIN_DEPOSIT = float(os.environ.get("MIN_DEPOSIT", "10"))
MIN_WITHDRAWAL = float(os.environ.get("MIN_WITHDRAWAL", "10"))

PLANS = [
    {"id": "A", "name": "Plan A", "price": 500, "tasks": [("Task 1", 20), ("Task 2", 25), ("Task 3", 25)]},
    {"id": "B", "name": "Plan B", "price": 1000, "tasks": [("Task 1", 45), ("Task 2", 45), ("Task 3", 50)]},
    {"id": "C", "name": "Plan C", "price": 2000, "tasks": [("Task 1", 70), ("Task 2", 70), ("Task 3", 90)]},
    {"id": "D", "name": "Plan D", "price": 5000, "tasks": [("Task 1", 120), ("Task 2", 120), ("Task 3", 160)]},
]

# =========================
# DATABASE
# =========================
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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            transaction_id TEXT UNIQUE NOT NULL,
            note TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            reviewed_by TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            account_name TEXT NOT NULL,
            account_number TEXT NOT NULL,
            bank_name TEXT NOT NULL,
            note TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            reviewed_by TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# =========================
# HELPERS
# =========================
def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    return user

def login_required():
    return current_user() is not None

def is_admin():
    return session.get("admin") is True

def money(v):
    return f"{float(v):,.2f}"

# =========================
# HTML
# =========================
BASE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEXA</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:Arial,sans-serif;background:#f4f7fb;color:#172033}
nav{background:#101828;color:white;padding:14px 18px;display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
nav a{color:white;text-decoration:none;margin:4px 8px}.brand{font-size:22px;font-weight:800}
.container{max-width:1050px;margin:25px auto;padding:0 15px}
.card{background:white;border-radius:14px;padding:20px;margin-bottom:18px;box-shadow:0 4px 18px #0000000d}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:15px}
input,select,textarea{width:100%;padding:12px;margin:7px 0 13px;border:1px solid #d0d5dd;border-radius:9px;font-size:15px}
button,.btn{border:0;border-radius:9px;padding:11px 16px;background:#175cd3;color:white;text-decoration:none;cursor:pointer;display:inline-block}
.btn-danger{background:#d92d20}.btn-secondary{background:#667085}.btn-success{background:#079455}
.badge{padding:5px 9px;border-radius:20px;background:#eef4ff;font-size:12px}.pending{background:#fff4cc}.approved{background:#dcfae6}.rejected{background:#fee4e2}
.flash{padding:12px;border-radius:9px;background:#eef4ff;margin-bottom:12px}
table{width:100%;border-collapse:collapse}th,td{padding:10px;border-bottom:1px solid #eaecf0;text-align:left;vertical-align:top}
.small{font-size:13px;color:#667085}.balance{font-size:32px;font-weight:800}.bank{background:#eef7ff;border-left:4px solid #175cd3}
</style>
</head>
<body>
<nav>
<div class="brand">NEXA</div>
<div>
{% if user %}
<a href="{{ url_for('dashboard') }}">Dashboard</a>
<a href="{{ url_for('deposit') }}">Deposit</a>
<a href="{{ url_for('withdraw') }}">Withdraw</a>
<a href="{{ url_for('history') }}">History</a>
<a href="{{ url_for('logout') }}">Logout</a>
{% elif admin %}
<a href="{{ url_for('admin') }}">Admin</a>
<a href="{{ url_for('admin_logout') }}">Logout</a>
{% else %}
<a href="{{ url_for('login') }}">Login</a>
<a href="{{ url_for('register') }}">Register</a>
{% endif %}
</div>
</nav>
<div class="container">
{% with messages=get_flashed_messages() %}
{% for m in messages %}<div class="flash">{{m}}</div>{% endfor %}
{% endwith %}
{{ content|safe }}
</div>
</body>
</html>
"""

def page(content, **extra):
    return render_template_string(BASE, content=content, **extra)

# =========================
# AUTH
# =========================
@app.route("/")
def home():
    if current_user():
        return redirect(url_for("dashboard"))
    if is_admin():
        return redirect(url_for("admin"))
    return page("""
    <div class="card">
      <h1>NEXA</h1>
      <p>Deposit, wallet and withdrawal management system.</p>
      <a class="btn" href="/register">Create account</a>
      <a class="btn btn-secondary" href="/login">Login</a>
    </div>
    """)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        phone = request.form.get("phone","").strip()
        password = request.form.get("password","")
        referral = request.form.get("referral","").strip()

        if len(phone) < 3 or len(password) < 4:
            flash("Enter a valid phone/username and a password of at least 4 characters.")
            return redirect(url_for("register"))

        code = secrets.token_hex(4).upper()
        conn = db()
        try:
            conn.execute(
                "INSERT INTO users(phone,password,referral_code,referred_by,created_at) VALUES(?,?,?,?,?)",
                (phone,password,code,referral or None,now())
            )
            conn.commit()
            flash("Registration successful. Please login.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That phone/username is already registered.")
        finally:
            conn.close()

    return page("""
    <div class="card">
    <h2>Create account</h2>
    <form method="post">
      <label>Phone / Username</label><input name="phone" required>
      <label>Password</label><input name="password" type="password" required>
      <label>Referral code (optional)</label><input name="referral">
      <button>Create account</button>
    </form>
    </div>
    """)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        phone = request.form.get("phone","").strip()
        password = request.form.get("password","")
        conn = db()
        user = conn.execute("SELECT * FROM users WHERE phone=? AND password=?", (phone,password)).fetchone()
        conn.close()
        if user:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        flash("Invalid login details.")

    return page("""
    <div class="card">
    <h2>Login</h2>
    <form method="post">
      <label>Phone / Username</label><input name="phone" required>
      <label>Password</label><input name="password" type="password" required>
      <button>Login</button>
    </form>
    </div>
    """)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# =========================
# USER DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = db()
    tasks = conn.execute("SELECT * FROM tasks WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()
    conn.close()

    task_html = "".join(
        f"""<tr><td>{t['plan_id']}</td><td>{t['task_name']}</td>
        <td>{money(t['reward'])} ETB</td><td>{'Completed' if t['completed'] else 'Pending'}</td></tr>"""
        for t in tasks
    ) or "<tr><td colspan='4'>No tasks yet.</td></tr>"

    return page(f"""
    <div class="grid">
      <div class="card"><div class="small">Wallet balance</div><div class="balance">{money(user['balance'])} ETB</div></div>
      <div class="card"><div class="small">Total earned</div><div class="balance">{money(user['total_earned'])} ETB</div></div>
      <div class="card"><div class="small">Referral code</div><div class="balance" style="font-size:22px">{user['referral_code']}</div></div>
    </div>

    <div class="grid">
      <a class="card" style="text-decoration:none;color:inherit" href="/deposit"><h2>💳 Deposit</h2><p>Send money to the bank account and submit your transaction ID.</p></a>
      <a class="card" style="text-decoration:none;color:inherit" href="/withdraw"><h2>💸 Withdraw</h2><p>Request a withdrawal from your available wallet balance.</p></a>
    </div>

    <div class="card">
      <h2>Your tasks</h2>
      <table><tr><th>Plan</th><th>Task</th><th>Reward</th><th>Status</th></tr>{task_html}</table>
    </div>
    """, user=user)

# =========================
# DEPOSIT
# =========================
@app.route("/deposit", methods=["GET","POST"])
def deposit():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount","0"))
        except ValueError:
            amount = 0

        txid = request.form.get("transaction_id","").strip()
        note = request.form.get("note","").strip()

        if amount < MIN_DEPOSIT:
            flash(f"Minimum deposit is {money(MIN_DEPOSIT)} ETB.")
            return redirect(url_for("deposit"))
        if not txid:
            flash("Transaction/reference number is required.")
            return redirect(url_for("deposit"))

        conn = db()
        try:
            conn.execute(
                "INSERT INTO deposits(user_id,amount,transaction_id,note,status,created_at) VALUES(?,?,?,?,?,?)",
                (user["id"],amount,txid,note,"pending",now())
            )
            conn.commit()
            flash("Deposit submitted. It will be credited after admin verification.")
        except sqlite3.IntegrityError:
            flash("This transaction/reference number has already been submitted.")
        finally:
            conn.close()

        return redirect(url_for("deposit"))

    conn = db()
    deposits = conn.execute(
        "SELECT * FROM deposits WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (user["id"],)
    ).fetchall()
    conn.close()

    rows = "".join(
        f"<tr><td>{d['amount']:,.2f}</td><td>{d['transaction_id']}</td>"
        f"<td><span class='badge {d['status']}'>{d['status']}</span></td><td>{d['created_at']}</td></tr>"
        for d in deposits
    ) or "<tr><td colspan='4'>No deposits yet.</td></tr>"

    return page(f"""
    <div class="card bank">
      <h2>Deposit instructions</h2>
      <p><b>Bank:</b> {BANK_NAME}</p>
      <p><b>Account name:</b> {BANK_ACCOUNT_NAME}</p>
      <p><b>Account number:</b> {BANK_ACCOUNT_NUMBER}</p>
      <p>Send the money first, then submit the exact transaction/reference number below.
      Your wallet is credited only after admin verification.</p>
    </div>

    <div class="card">
      <h2>Submit deposit</h2>
      <form method="post">
        <label>Amount (ETB)</label><input name="amount" type="number" min="{MIN_DEPOSIT}" step="0.01" required>
        <label>Transaction / Reference number</label><input name="transaction_id" required>
        <label>Note (optional)</label><textarea name="note"></textarea>
        <button>Submit deposit</button>
      </form>
    </div>

    <div class="card">
      <h2>My deposit requests</h2>
      <table><tr><th>Amount</th><th>Reference</th><th>Status</th><th>Date</th></tr>{rows}</table>
    </div>
    """, user=user)

# =========================
# WITHDRAWAL
# =========================
@app.route("/withdraw", methods=["GET","POST"])
def withdraw():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount","0"))
        except ValueError:
            amount = 0

        account_name = request.form.get("account_name","").strip()
        account_number = request.form.get("account_number","").strip()
        bank_name = request.form.get("bank_name","").strip()
        note = request.form.get("note","").strip()

        if amount < MIN_WITHDRAWAL:
            flash(f"Minimum withdrawal is {money(MIN_WITHDRAWAL)} ETB.")
            return redirect(url_for("withdraw"))
        if amount > float(user["balance"]):
            flash("Insufficient wallet balance.")
            return redirect(url_for("withdraw"))
        if not account_name or not account_number or not bank_name:
            flash("Bank name, account name and account number are required.")
            return redirect(url_for("withdraw"))

        conn = db()
        # Reserve the balance while the request is pending.
        conn.execute("UPDATE users SET balance=balance-? WHERE id=? AND balance>=?", (amount,user["id"],amount))
        if conn.execute("SELECT changes()").fetchone()[0] != 1:
            conn.rollback()
            conn.close()
            flash("Insufficient wallet balance.")
            return redirect(url_for("withdraw"))

        conn.execute(
            """INSERT INTO withdrawals
            (user_id,amount,account_name,account_number,bank_name,note,status,created_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (user["id"],amount,account_name,account_number,bank_name,note,"pending",now())
        )
        conn.execute(
            "INSERT INTO history(user_id,action,amount,note,created_at) VALUES(?,?,?,?,?)",
            (user["id"],"withdrawal_pending",-amount,"Withdrawal request created",now())
        )
        conn.commit()
        conn.close()
        flash("Withdrawal request submitted for admin review.")
        return redirect(url_for("withdraw"))

    conn = db()
    withdrawals = conn.execute(
        "SELECT * FROM withdrawals WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (user["id"],)
    ).fetchall()
    conn.close()

    rows = "".join(
        f"<tr><td>{money(w['amount'])}</td><td>{w['bank_name']}<br>{w['account_name']}<br>{w['account_number']}</td>"
        f"<td><span class='badge {w['status']}'>{w['status']}</span></td><td>{w['created_at']}</td></tr>"
        for w in withdrawals
    ) or "<tr><td colspan='4'>No withdrawal requests yet.</td></tr>"

    return page(f"""
    <div class="card">
      <h2>Withdraw</h2>
      <p class="small">Available balance: {money(user['balance'])} ETB</p>
      <form method="post">
        <label>Amount (ETB)</label><input name="amount" type="number" min="{MIN_WITHDRAWAL}" step="0.01" required>
        <label>Bank name</label><input name="bank_name" required>
        <label>Account name</label><input name="account_name" required>
        <label>Account number</label><input name="account_number" required>
        <label>Note (optional)</label><textarea name="note"></textarea>
        <button>Submit withdrawal</button>
      </form>
    </div>
    <div class="card">
      <h2>My withdrawals</h2>
      <table><tr><th>Amount</th><th>Destination</th><th>Status</th><th>Date</th></tr>{rows}</table>
    </div>
    """, user=user)

# =========================
# HISTORY
# =========================
@app.route("/history")
def history():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = db()
    rows = conn.execute(
        "SELECT * FROM history WHERE user_id=? ORDER BY id DESC LIMIT 100",
        (user["id"],)
    ).fetchall()
    conn.close()

    html = "".join(
        f"<tr><td>{h['created_at']}</td><td>{h['action']}</td><td>{money(h['amount'])}</td><td>{h['note'] or ''}</td></tr>"
        for h in rows
    ) or "<tr><td colspan='4'>No history yet.</td></tr>"

    return page(f"""
    <div class="card"><h2>Transaction history</h2>
    <table><tr><th>Date</th><th>Action</th><th>Amount</th><th>Note</th></tr>{html}</table></div>
    """, user=user)

# =========================
# ADMIN
# =========================
@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username","")
        password = request.form.get("password","")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.clear()
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("Invalid admin credentials.")

    return page("""
    <div class="card">
      <h2>Admin login</h2>
      <form method="post">
        <label>Username</label><input name="username" required>
        <label>Password</label><input name="password" type="password" required>
        <button>Login</button>
      </form>
    </div>
    """, admin=is_admin())

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/admin")
def admin():
    if not is_admin():
        return redirect(url_for("admin_login"))

    conn = db()
    pending_deposits = conn.execute("""
        SELECT d.*, u.phone FROM deposits d
        JOIN users u ON u.id=d.user_id
        WHERE d.status='pending' ORDER BY d.id ASC
    """).fetchall()

    pending_withdrawals = conn.execute("""
        SELECT w.*, u.phone FROM withdrawals w
        JOIN users u ON u.id=w.user_id
        WHERE w.status='pending' ORDER BY w.id ASC
    """).fetchall()

    users = conn.execute("SELECT id,phone,balance,total_earned,referral_code,created_at FROM users ORDER BY id DESC").fetchall()
    conn.close()

    deposits_html = "".join(
        f"""<tr><td>{d['id']}</td><td>{d['phone']}</td><td>{money(d['amount'])}</td>
        <td>{d['transaction_id']}</td><td>{d['note'] or ''}</td><td>{d['created_at']}</td>
        <td>
        <form style="display:inline" method="post" action="/admin/deposit/{d['id']}/approve"><button class="btn-success">Approve</button></form>
        <form style="display:inline" method="post" action="/admin/deposit/{d['id']}/reject"><button class="btn-danger">Reject</button></form>
        </td></tr>"""
        for d in pending_deposits
    ) or "<tr><td colspan='7'>No pending deposits.</td></tr>"

    withdrawals_html = "".join(
        f"""<tr><td>{w['id']}</td><td>{w['phone']}</td><td>{money(w['amount'])}</td>
        <td>{w['bank_name']}<br>{w['account_name']}<br>{w['account_number']}</td>
        <td>{w['created_at']}</td><td>
        <form style="display:inline" method="post" action="/admin/withdraw/{w['id']}/approve"><button class="btn-success">Approve</button></form>
        <form style="display:inline" method="post" action="/admin/withdraw/{w['id']}/reject"><button class="btn-danger">Reject</button></form>
        </td></tr>"""
        for w in pending_withdrawals
    ) or "<tr><td colspan='6'>No pending withdrawals.</td></tr>"

    users_html = "".join(
        f"<tr><td>{u['id']}</td><td>{u['phone']}</td><td>{money(u['balance'])}</td><td>{money(u['total_earned'])}</td><td>{u['referral_code']}</td></tr>"
        for u in users
    )

    return page(f"""
    <div class="card"><h1>Admin panel</h1>
    <p class="small">Approve a deposit only after checking the bank transaction in your own banking records.</p></div>

    <div class="card"><h2>Pending deposits</h2>
    <table><tr><th>ID</th><th>User</th><th>Amount</th><th>Reference</th><th>Note</th><th>Date</th><th>Action</th></tr>{deposits_html}</table></div>

    <div class="card"><h2>Pending withdrawals</h2>
    <table><tr><th>ID</th><th>User</th><th>Amount</th><th>Destination</th><th>Date</th><th>Action</th></tr>{withdrawals_html}</table></div>

    <div class="card"><h2>Users</h2>
    <table><tr><th>ID</th><th>User</th><th>Balance</th><th>Total earned</th><th>Referral</th></tr>{users_html}</table></div>
    """, admin=True)

@app.post("/admin/deposit/<int:deposit_id>/approve")
def approve_deposit(deposit_id):
    if not is_admin():
        return redirect(url_for("admin_login"))

    conn = db()
    deposit = conn.execute("SELECT * FROM deposits WHERE id=?", (deposit_id,)).fetchone()
    if not deposit or deposit["status"] != "pending":
        conn.close()
        flash("Deposit not found or already reviewed.")
        return redirect(url_for("admin"))

    conn.execute("UPDATE deposits SET status='approved',reviewed_at=?,reviewed_by=? WHERE id=?",
                 (now(),ADMIN_USERNAME,deposit_id))
    conn.execute("UPDATE users SET balance=balance+? WHERE id=?", (deposit["amount"],deposit["user_id"]))
    conn.execute("INSERT INTO history(user_id,action,amount,note,created_at) VALUES(?,?,?,?,?)",
                 (deposit["user_id"],"deposit",deposit["amount"],f"Deposit approved: {deposit['transaction_id']}",now()))
    conn.commit()
    conn.close()
    flash("Deposit approved and wallet credited.")
    return redirect(url_for("admin"))

@app.post("/admin/deposit/<int:deposit_id>/reject")
def reject_deposit(deposit_id):
    if not is_admin():
        return redirect(url_for("admin_login"))

    conn = db()
    deposit = conn.execute("SELECT * FROM deposits WHERE id=?", (deposit_id,)).fetchone()
    if deposit and deposit["status"] == "pending":
        conn.execute("UPDATE deposits SET status='rejected',reviewed_at=?,reviewed_by=? WHERE id=?",
                     (now(),ADMIN_USERNAME,deposit_id))
        conn.execute("INSERT INTO history(user_id,action,amount,note,created_at) VALUES(?,?,?,?,?)",
                     (deposit["user_id"],"deposit_rejected",0,f"Deposit rejected: {deposit['transaction_id']}",now()))
        conn.commit()
        flash("Deposit rejected.")
    else:
        flash("Deposit not found or already reviewed.")
    conn.close()
    return redirect(url_for("admin"))

@app.post("/admin/withdraw/<int:withdrawal_id>/approve")
def approve_withdrawal(withdrawal_id):
    if not is_admin():
        return redirect(url_for("admin_login"))

    conn = db()
    w = conn.execute("SELECT * FROM withdrawals WHERE id=?", (withdrawal_id,)).fetchone()
    if not w or w["status"] != "pending":
        conn.close()
        flash("Withdrawal not found or already reviewed.")
        return redirect(url_for("admin"))

    conn.execute("UPDATE withdrawals SET status='approved',reviewed_at=?,reviewed_by=? WHERE id=?",
                 (now(),ADMIN_USERNAME,withdrawal_id))
    conn.execute("INSERT INTO history(user_id,action,amount,note,created_at) VALUES(?,?,?,?,?)",
                 (w["user_id"],"withdrawal", -w["amount"],"Withdrawal approved",now()))
    conn.commit()
    conn.close()
    flash("Withdrawal approved. Send the money manually through your bank and keep the bank confirmation.")
    return redirect(url_for("admin"))

@app.post("/admin/withdraw/<int:withdrawal_id>/reject")
def reject_withdrawal(withdrawal_id):
    if not is_admin():
        return redirect(url_for("admin_login"))

    conn = db()
    w = conn.execute("SELECT * FROM withdrawals WHERE id=?", (withdrawal_id,)).fetchone()
    if w and w["status"] == "pending":
        # Return the reserved amount to the wallet.
        conn.execute("UPDATE withdrawals SET status='rejected',reviewed_at=?,reviewed_by=? WHERE id=?",
                     (now(),ADMIN_USERNAME,withdrawal_id))
        conn.execute("UPDATE users SET balance=balance+? WHERE id=?", (w["amount"],w["user_id"]))
        conn.execute("INSERT INTO history(user_id,action,amount,note,created_at) VALUES(?,?,?,?,?)",
                     (w["user_id"],"withdrawal_refund",w["amount"],"Withdrawal rejected; amount returned",now()))
        conn.commit()
        flash("Withdrawal rejected and amount returned to user balance.")
    else:
        flash("Withdrawal not found or already reviewed.")
    conn.close()
    return redirect(url_for("admin"))

# =========================
# HEALTH / START
# =========================
@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
