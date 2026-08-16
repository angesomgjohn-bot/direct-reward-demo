from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import secrets
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DB = os.environ.get("DB_PATH", "nexa.db")
BANK_NAME = os.environ.get("BANK_NAME", "Commercial Bank of Ethiopia (CBE)")
BANK_ACCOUNT_NAME = os.environ.get("BANK_ACCOUNT_NAME", "")
BANK_ACCOUNT_NUMBER = os.environ.get("BANK_ACCOUNT_NUMBER", "")
OFFICIAL_TELEGRAM_URL = os.environ.get("OFFICIAL_TELEGRAM_URL", "")
CUSTOMER_SERVICE_URL = os.environ.get("CUSTOMER_SERVICE_URL", "")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")

WITHDRAWAL_FEE_RATE = 0.10

PLANS = [
    {"id": "A", "name": "Plan A", "price": 500, "tasks": [("Task 1", 20), ("Task 2", 25), ("Task 3", 25)]},
    {"id": "B", "name": "Plan B", "price": 1000, "tasks": [("Task 1", 45), ("Task 2", 45), ("Task 3", 50)]},
    {"id": "C", "name": "Plan C", "price": 2000, "tasks": [("Task 1", 70), ("Task 2", 70), ("Task 3", 90)]},
    {"id": "D", "name": "Plan D", "price": 5000, "tasks": [("Task 1", 120), ("Task 2", 120), ("Task 3", 160)]},
    {"id": "E", "name": "Plan E", "price": 10000, "tasks": [("Task 1", 250), ("Task 2", 250), ("Task 3", 300)]},
    {"id": "F", "name": "Plan F", "price": 20000, "tasks": [("Task 1", 500), ("Task 2", 500), ("Task 3", 600)]},
]

def db():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        referral_code TEXT UNIQUE NOT NULL,
        referred_by TEXT,
        balance REAL NOT NULL DEFAULT 0,
        total_earned REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS deposits(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        reference TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING',
        created_at TEXT NOT NULL,
        reviewed_at TEXT
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_deposit_reference
        ON deposits(reference);

    CREATE TABLE IF NOT EXISTS withdrawals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        fee REAL NOT NULL,
        net_amount REAL NOT NULL,
        account_number TEXT NOT NULL,
        account_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING',
        created_at TEXT NOT NULL,
        reviewed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS plans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        plan_id TEXT NOT NULL,
        price REAL NOT NULL,
        started_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ACTIVE'
    );

    CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        plan_id TEXT NOT NULL,
        task_name TEXT NOT NULL,
        reward REAL NOT NULL,
        completed INTEGER NOT NULL DEFAULT 0,
        completed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        amount REAL NOT NULL DEFAULT 0,
        note TEXT,
        created_at TEXT NOT NULL
    );
    """)
    conn.commit()
    conn.close()

def now():
    return datetime.utcnow().isoformat(timespec="seconds")

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = db()
    row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return row

def add_history(conn, user_id, action, amount=0, note=""):
    conn.execute(
        "INSERT INTO history(user_id, action, amount, note, created_at) VALUES(?,?,?,?,?)",
        (user_id, action, float(amount), note, now())
    )

def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]

@app.context_processor
def inject_globals():
    return {"csrf_token": csrf_token()}

def check_csrf():
    token = request.form.get("_csrf", "")
    return bool(token) and secrets.compare_digest(token, session.get("csrf", ""))

def admin_ok():
    return bool(ADMIN_KEY) and secrets.compare_digest(
        str(request.args.get("key", "")), str(ADMIN_KEY)
    )

@app.route("/")
def home():
    u = current_user()
    if not u:
        return render_template(
            "index.html",
            user=None,
            login_mode=True,
            plans=PLANS,
            bank_name=BANK_NAME,
            bank_account_name=BANK_ACCOUNT_NAME,
            bank_account_number=BANK_ACCOUNT_NUMBER,
        )

    conn = db()
    deposits = conn.execute(
        "SELECT * FROM deposits WHERE user_id=? ORDER BY id DESC LIMIT 30",
        (u["id"],)
    ).fetchall()
    withdrawals = conn.execute(
        "SELECT * FROM withdrawals WHERE user_id=? ORDER BY id DESC LIMIT 30",
        (u["id"],)
    ).fetchall()
    tasks = conn.execute(
        "SELECT * FROM tasks WHERE user_id=? ORDER BY id DESC LIMIT 50",
        (u["id"],)
    ).fetchall()
    history_rows = conn.execute(
        "SELECT * FROM history WHERE user_id=? ORDER BY id DESC LIMIT 50",
        (u["id"],)
    ).fetchall()
    conn.close()

    return render_template(
        "index.html",
        user=u,
        login_mode=False,
        plans=PLANS,
        deposits=deposits,
        withdrawals=withdrawals,
        tasks=tasks,
        history=history_rows,
        bank_name=BANK_NAME,
        bank_account_name=BANK_ACCOUNT_NAME,
        bank_account_number=BANK_ACCOUNT_NUMBER,
        official_telegram_url=OFFICIAL_TELEGRAM_URL,
        customer_service_url=CUSTOMER_SERVICE_URL,
    )

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not check_csrf():
            flash("Session expired. Please try again.", "error")
            return redirect(url_for("home"))

        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        referral = request.form.get("referral", "").strip() or None

        if len(phone) < 6 or len(password) < 6:
            flash("Enter a valid phone number and a password of at least 6 characters.", "error")
            return redirect(url_for("home"))

        conn = db()
        try:
            code = secrets.token_hex(4).upper()
            cur = conn.execute(
                """INSERT INTO users
                   (phone,password_hash,referral_code,referred_by,created_at)
                   VALUES(?,?,?,?,?)""",
                (phone, generate_password_hash(password), code, referral, now())
            )
            add_history(conn, cur.lastrowid, "ACCOUNT_CREATED")
            conn.commit()
            session["user_id"] = cur.lastrowid
            flash("Account created successfully.", "success")
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("This phone number is already registered.", "error")
        finally:
            conn.close()
        return redirect(url_for("home"))

    return redirect(url_for("home"))

@app.route("/login", methods=["POST"])
def login():
    if not check_csrf():
        flash("Session expired. Please try again.", "error")
        return redirect(url_for("home"))

    phone = request.form.get("phone", "").strip()
    password = request.form.get("password", "")

    conn = db()
    u = conn.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
    conn.close()

    if not u or not check_password_hash(u["password_hash"], password):
        flash("Invalid phone number or password.", "error")
        return redirect(url_for("home"))

    session.clear()
    session["user_id"] = u["id"]
    session["csrf"] = secrets.token_urlsafe(32)
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/deposit", methods=["POST"])
def deposit():
    u = current_user()
    if not u:
        return redirect(url_for("home"))
    if not check_csrf():
        flash("Session expired. Please try again.", "error")
        return redirect(url_for("home"))

    try:
        amount = round(float(request.form.get("amount", "0")), 2)
    except ValueError:
        amount = 0
    reference = request.form.get("reference", "").strip()

    if amount <= 0:
        flash("Enter a valid deposit amount.", "error")
        return redirect(url_for("home"))
    if len(reference) < 3:
        flash("Enter the transaction/reference number.", "error")
        return redirect(url_for("home"))

    conn = db()
    try:
        conn.execute(
            "INSERT INTO deposits(user_id,amount,reference,created_at) VALUES(?,?,?,?)",
            (u["id"], amount, reference, now())
        )
        add_history(conn, u["id"], "DEPOSIT_SUBMITTED", amount, "Reference: " + reference)
        conn.commit()
        flash("Deposit submitted. It will be credited after admin verification.", "success")
    except sqlite3.IntegrityError:
        conn.rollback()
        flash("That transaction/reference number has already been submitted.", "error")
    finally:
        conn.close()
    return redirect(url_for("home"))

@app.route("/withdraw", methods=["POST"])
def withdraw():
    u = current_user()
    if not u:
        return redirect(url_for("home"))
    if not check_csrf():
        flash("Session expired. Please try again.", "error")
        return redirect(url_for("home"))

    try:
        amount = round(float(request.form.get("amount", "0")), 2)
    except ValueError:
        amount = 0

    account_number = request.form.get("account_number", "").strip()
    account_name = request.form.get("account_name", "").strip()

    if amount <= 0 or not account_number or not account_name:
        flash("Enter amount, account number and account name.", "error")
        return redirect(url_for("home"))

    fee = round(amount * WITHDRAWAL_FEE_RATE, 2)
    net = round(amount - fee, 2)

    conn = db()
    try:
        cur = conn.execute(
            "UPDATE users SET balance=balance-? WHERE id=? AND balance>=?",
            (amount, u["id"], amount)
        )
        if cur.rowcount != 1:
            conn.rollback()
            flash("Insufficient available balance.", "error")
            return redirect(url_for("home"))

        conn.execute(
            """INSERT INTO withdrawals
               (user_id,amount,fee,net_amount,account_number,account_name,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (u["id"], amount, fee, net, account_number, account_name, now())
        )
        add_history(
            conn, u["id"], "WITHDRAWAL_REQUESTED", amount,
            f"Fee: {fee:.2f} ETB; Net: {net:.2f} ETB"
        )
        conn.commit()
        flash(f"Withdrawal submitted. Net amount: {net:.2f} ETB.", "success")
    finally:
        conn.close()

    return redirect(url_for("home"))

@app.route("/start-plan/<plan_id>", methods=["POST"])
def start_plan(plan_id):
    u = current_user()
    if not u:
        return redirect(url_for("home"))
    if not check_csrf():
        flash("Session expired. Please try again.", "error")
        return redirect(url_for("home"))

    plan = next((p for p in PLANS if p["id"] == plan_id), None)
    if not plan:
        flash("Plan not found.", "error")
        return redirect(url_for("home"))

    conn = db()
    active = conn.execute(
        "SELECT 1 FROM plans WHERE user_id=? AND plan_id=? AND status='ACTIVE'",
        (u["id"], plan_id)
    ).fetchone()
    if active:
        conn.close()
        flash("You already have this plan.", "error")
        return redirect(url_for("home"))

    # A plan is started only when the wallet has enough balance.
    cur = conn.execute(
        "UPDATE users SET balance=balance-? WHERE id=? AND balance>=?",
        (plan["price"], u["id"], plan["price"])
    )
    if cur.rowcount != 1:
        conn.rollback()
        conn.close()
        flash("Insufficient balance to start this plan.", "error")
        return redirect(url_for("home"))

    conn.execute(
        "INSERT INTO plans(user_id,plan_id,price,started_at) VALUES(?,?,?,?)",
        (u["id"], plan_id, plan["price"], now())
    )
    for task_name, reward in plan["tasks"]:
        conn.execute(
            "INSERT INTO tasks(user_id,plan_id,task_name,reward) VALUES(?,?,?,?)",
            (u["id"], plan_id, task_name, reward)
        )
    add_history(conn, u["id"], "PLAN_STARTED", plan["price"], plan["name"])
    conn.commit()
    conn.close()
    flash(f"{plan['name']} started successfully.", "success")
    return redirect(url_for("home"))

@app.route("/complete-task/<int:task_id>", methods=["POST"])
def complete_task(task_id):
    u = current_user()
    if not u:
        return redirect(url_for("home"))
    if not check_csrf():
        flash("Session expired. Please try again.", "error")
        return redirect(url_for("home"))

    conn = db()
    task = conn.execute(
        "SELECT * FROM tasks WHERE id=? AND user_id=? AND completed=0",
        (task_id, u["id"])
    ).fetchone()
    if not task:
        conn.close()
        flash("Task not found or already completed.", "error")
        return redirect(url_for("home"))

    conn.execute(
        "UPDATE tasks SET completed=1, completed_at=? WHERE id=?",
        (now(), task_id)
    )
    conn.execute(
        "UPDATE users SET balance=balance+?, total_earned=total_earned+? WHERE id=?",
        (task["reward"], task["reward"], u["id"])
    )
    add_history(conn, u["id"], "TASK_COMPLETED", task["reward"], task["task_name"])
    conn.commit()
    conn.close()
    flash(f"Task completed. {task['reward']:.2f} ETB added to your wallet.", "success")
    return redirect(url_for("home"))

@app.route("/referral")
def referral():
    u = current_user()
    if not u:
        return redirect(url_for("home"))
    link = request.host_url.rstrip("/") + "/register?ref=" + u["referral_code"]
    return render_template(
        "index.html",
        user=u,
        login_mode=False,
        plans=PLANS,
        deposits=[],
        withdrawals=[],
        tasks=[],
        history=[],
        referral_link=link,
        bank_name=BANK_NAME,
        bank_account_name=BANK_ACCOUNT_NAME,
        bank_account_number=BANK_ACCOUNT_NUMBER,
        official_telegram_url=OFFICIAL_TELEGRAM_URL,
        customer_service_url=CUSTOMER_SERVICE_URL,
    )

@app.route("/support")
def support():
    if CUSTOMER_SERVICE_URL:
        return redirect(CUSTOMER_SERVICE_URL)
    return redirect(url_for("home"))

@app.route("/channel")
def channel():
    if OFFICIAL_TELEGRAM_URL:
        return redirect(OFFICIAL_TELEGRAM_URL)
    return redirect(url_for("home"))

@app.route("/admin")
def admin():
    if not admin_ok():
        return "Unauthorized", 401

    conn = db()
    deposits = conn.execute(
        """SELECT d.*, u.phone
           FROM deposits d JOIN users u ON u.id=d.user_id
           WHERE d.status='PENDING' ORDER BY d.id"""
    ).fetchall()
    withdrawals = conn.execute(
        """SELECT w.*, u.phone
           FROM withdrawals w JOIN users u ON u.id=w.user_id
           WHERE w.status='PENDING' ORDER BY w.id"""
    ).fetchall()
    conn.close()
    return render_template("admin.html", deposits=deposits, withdrawals=withdrawals, admin_key=ADMIN_KEY)

@app.route("/admin/deposit/<int:item>/<action>", methods=["POST"])
def admin_deposit(item, action):
    if not admin_ok() or not check_csrf():
        return "Unauthorized", 401
    if action not in ("approve", "reject"):
        return "Bad request", 400

    conn = db()
    deposit_row = conn.execute(
        "SELECT * FROM deposits WHERE id=? AND status='PENDING'", (item,)
    ).fetchone()
    if not deposit_row:
        conn.close()
        flash("Deposit not found or already reviewed.", "error")
        return redirect(url_for("admin", key=ADMIN_KEY))

    status = "APPROVED" if action == "approve" else "REJECTED"
    if status == "APPROVED":
        conn.execute(
            "UPDATE users SET balance=balance+? WHERE id=?",
            (deposit_row["amount"], deposit_row["user_id"])
        )

    add_history(
        conn, deposit_row["user_id"], "DEPOSIT_" + status,
        deposit_row["amount"], "Reference: " + deposit_row["reference"]
    )
    conn.execute(
        "UPDATE deposits SET status=?, reviewed_at=? WHERE id=?",
        (status, now(), item)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin", key=ADMIN_KEY))

@app.route("/admin/withdrawal/<int:item>/<action>", methods=["POST"])
def admin_withdrawal(item, action):
    if not admin_ok() or not check_csrf():
        return "Unauthorized", 401
    if action not in ("paid", "reject"):
        return "Bad request", 400

    conn = db()
    withdrawal_row = conn.execute(
        "SELECT * FROM withdrawals WHERE id=? AND status='PENDING'", (item,)
    ).fetchone()
    if not withdrawal_row:
        conn.close()
        return "Withdrawal not found or already reviewed", 404

    if action == "paid":
        status = "PAID"
        add_history(
            conn, withdrawal_row["user_id"], "WITHDRAWAL_PAID",
            withdrawal_row["net_amount"],
            f"Fee: {withdrawal_row['fee']:.2f} ETB"
        )
    else:
        status = "REJECTED"
        conn.execute(
            "UPDATE users SET balance=balance+? WHERE id=?",
            (withdrawal_row["amount"], withdrawal_row["user_id"])
        )
        add_history(
            conn, withdrawal_row["user_id"], "WITHDRAWAL_REJECTED",
            withdrawal_row["amount"], "Reserved amount returned"
        )

    conn.execute(
        "UPDATE withdrawals SET status=?, reviewed_at=? WHERE id=?",
        (status, now(), item)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin", key=ADMIN_KEY))

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
