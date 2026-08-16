from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import secrets
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

DB = os.environ.get("DB_PATH", "nexa.db")
BANK_NAME = os.environ.get("BANK_NAME", "Commercial Bank of Ethiopia (CBE)")
BANK_ACCOUNT_NAME = os.environ.get("BANK_ACCOUNT_NAME", "")
BANK_ACCOUNT_NUMBER = os.environ.get("BANK_ACCOUNT_NUMBER", "")
OFFICIAL_TELEGRAM_URL = os.environ.get("OFFICIAL_TELEGRAM_URL", "")
CUSTOMER_SERVICE_URL = os.environ.get("CUSTOMER_SERVICE_URL", "")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
WITHDRAWAL_FEE = 0.10

MIN_WITHDRAWAL = 200
WITHDRAWAL_FEE = 0.10
WITHDRAWAL_START_HOUR = 9
WITHDRAWAL_END_HOUR = 17

PLANS = [
    {"id": "A", "name": "Plan A", "price": 500, "daily_reward": 100},
    {"id": "B", "name": "Plan B", "price": 1000, "daily_reward": 200},
    {"id": "C", "name": "Plan C", "price": 2000, "daily_reward": 400},
    {"id": "D", "name": "Plan D", "price": 5000, "daily_reward": 1000},
    {"id": "E", "name": "Plan E", "price": 10000, "daily_reward": 2000},
    {"id": "F", "name": "Plan F", "price": 20000, "daily_reward": 4000},
]


def now():
    return datetime.utcnow().isoformat(timespec="seconds")


def db():
    conn = sqlite3.connect(DB, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
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
        reviewed_at TEXT,
        UNIQUE(user_id, reference),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS bank_accounts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        bank_name TEXT NOT NULL,
        account_name TEXT NOT NULL,
        account_number TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

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
        reviewed_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        amount REAL NOT NULL DEFAULT 0,
        note TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        plan_id TEXT NOT NULL,
        task_name TEXT NOT NULL,
        reward REAL NOT NULL,
        completed INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        completed_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    conn.commit()
    conn.close()


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return user


def add_history(conn, user_id, action, amount=0, note=""):
    conn.execute(
        """INSERT INTO history(user_id, action, amount, note, created_at)
           VALUES(?,?,?,?,?)""",
        (user_id, action, amount, note, now()),
    )


def render_home(user=None, referral_link=None):
    conn = db()
    deposits = withdrawals = history = tasks = []
    if user:
        deposits = conn.execute(
            "SELECT * FROM deposits WHERE user_id=? ORDER BY id DESC",
            (user["id"],)
        ).fetchall()
        withdrawals = conn.execute(
            "SELECT * FROM withdrawals WHERE user_id=? ORDER BY id DESC",
            (user["id"],)
        ).fetchall()
        history = conn.execute(
            "SELECT * FROM history WHERE user_id=? ORDER BY id DESC LIMIT 40",
            (user["id"],)
        ).fetchall()
        tasks = conn.execute(
            "SELECT * FROM tasks WHERE user_id=? ORDER BY id DESC",
            (user["id"],)
        ).fetchall()
    conn.close()

    bank_account = None
    if user:
        c2 = db()
        bank_account = c2.execute(
            "SELECT * FROM bank_accounts WHERE user_id=?", (user["id"],)
        ).fetchone()
        c2.close()

    return render_template(
        "index.html",
        user=user,
        bank_account=bank_account,
        min_withdrawal=MIN_WITHDRAWAL,
        withdrawal_start="9:00 AM",
        withdrawal_end="5:00 PM",
        withdrawal_processing="within 24 hours",
        plans=PLANS,
        deposits=deposits,
        withdrawals=withdrawals,
        history=history,
        tasks=tasks,
        referral_link=referral_link,
        bank_name=BANK_NAME,
        bank_account_name=BANK_ACCOUNT_NAME,
        bank_account_number=BANK_ACCOUNT_NUMBER,
        official_telegram_url=OFFICIAL_TELEGRAM_URL,
        customer_service_url=CUSTOMER_SERVICE_URL,
        withdrawal_fee_percent=int(WITHDRAWAL_FEE * 100),
    )


@app.route("/")
def home():
    return render_home(current_user())


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        referred_by = request.form.get("referral", "").strip() or None

        if len(phone) < 5 or len(password) < 6:
            flash("Phone number and a password of at least 6 characters are required.", "error")
            return redirect(url_for("register"))

        conn = db()
        try:
            code = secrets.token_hex(4).upper()
            cur = conn.execute(
                """INSERT INTO users
                   (phone,password_hash,referral_code,referred_by,created_at)
                   VALUES(?,?,?,?,?)""",
                (phone, generate_password_hash(password), code, referred_by, now()),
            )
            add_history(conn, cur.lastrowid, "ACCOUNT_CREATED")
            conn.commit()
            session["user_id"] = cur.lastrowid
            flash("Account created successfully.", "success")
            return redirect(url_for("home"))
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("This phone number is already registered.", "error")
            return redirect(url_for("register"))
        finally:
            conn.close()

    return render_home(None)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        conn = db()
        user = conn.execute(
            "SELECT * FROM users WHERE phone=?", (phone,)
        ).fetchone()
        conn.close()

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid phone number or password.", "error")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        flash("Welcome back.", "success")
        return redirect(url_for("home"))

    return render_home(None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/deposit", methods=["POST"])
def deposit():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    try:
        amount = float(request.form.get("amount", "0"))
    except ValueError:
        amount = 0

    reference = request.form.get("reference", "").strip()

    if amount <= 0 or not reference:
        flash("Enter a valid deposit amount and transaction/reference number.", "error")
        return redirect(url_for("home"))

    conn = db()
    try:
        conn.execute(
            """INSERT INTO deposits(user_id,amount,reference,status,created_at)
               VALUES(?,?,?,?,?)""",
            (user["id"], amount, reference, "PENDING", now()),
        )
        add_history(
            conn, user["id"], "DEPOSIT_SUBMITTED", amount,
            f"Reference: {reference}"
        )
        conn.commit()
        flash("Deposit submitted. Status: PENDING. Balance changes only after admin approval.", "success")
    except sqlite3.IntegrityError:
        conn.rollback()
        flash("That reference has already been submitted for your account.", "error")
    finally:
        conn.close()

    return redirect(url_for("home"))


@app.route("/start-plan/<plan_id>", methods=["POST"])
def start_plan(plan_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    plan = next((p for p in PLANS if p["id"] == plan_id), None)
    if not plan:
        flash("Plan not found.", "error")
        return redirect(url_for("home"))

    conn = db()
    try:
        # A plan is activated only when the user has enough APPROVED balance.
        # The plan price is reserved/deducted immediately.
        cur = conn.execute(
            """UPDATE users
               SET balance=balance-?
               WHERE id=? AND balance>=?""",
            (plan["price"], user["id"], plan["price"]),
        )
        if cur.rowcount != 1:
            conn.rollback()
            flash("Insufficient available balance. Submit a deposit and wait for admin approval.", "error")
            return redirect(url_for("home"))

        conn.execute(
            """INSERT INTO tasks
               (user_id,plan_id,task_name,reward,completed,created_at)
               VALUES(?,?,?,?,0,?)""",
            (
                user["id"], plan["id"], f"{plan['name']} Daily Task",
                plan["daily_reward"], now()
            ),
        )
        add_history(
            conn, user["id"], "PLAN_ACTIVATED", plan["price"],
            f"{plan['name']} activated"
        )
        conn.commit()
        flash(f"{plan['name']} activated. {plan['price']:.0f} ETB was deducted from your available balance.", "success")
    finally:
        conn.close()

    return redirect(url_for("home"))


@app.route("/complete-task/<int:task_id>", methods=["POST"])
def complete_task(task_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = db()
    try:
        task = conn.execute(
            """SELECT * FROM tasks
               WHERE id=? AND user_id=? AND completed=0""",
            (task_id, user["id"]),
        ).fetchone()

        if not task:
            flash("Task not found or already completed.", "error")
            return redirect(url_for("home"))

        cur = conn.execute(
            """UPDATE tasks
               SET completed=1, completed_at=?
               WHERE id=? AND user_id=? AND completed=0""",
            (now(), task_id, user["id"]),
        )
        if cur.rowcount != 1:
            conn.rollback()
            flash("Task could not be completed.", "error")
            return redirect(url_for("home"))

        conn.execute(
            """UPDATE users
               SET balance=balance+?, total_earned=total_earned+?
               WHERE id=?""",
            (task["reward"], task["reward"], user["id"]),
        )
        add_history(
            conn, user["id"], "TASK_COMPLETED",
            task["reward"], task["task_name"]
        )
        conn.commit()
        flash(f"Task completed. {task['reward']:.2f} ETB added to your wallet.", "success")
    finally:
        conn.close()

    return redirect(url_for("home"))


@app.route("/bind-bank", methods=["POST"])
def bind_bank():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    bank_name = request.form.get("bank_name", "").strip()
    account_name = request.form.get("account_name", "").strip()
    account_number = request.form.get("account_number", "").strip()

    if not bank_name or not account_name or not account_number:
        flash("Please enter bank name, account holder name and account number.", "error")
        return redirect(url_for("home"))

    conn = db()
    try:
        conn.execute(
            """INSERT INTO bank_accounts
               (user_id,bank_name,account_name,account_number,created_at,updated_at)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
                 bank_name=excluded.bank_name,
                 account_name=excluded.account_name,
                 account_number=excluded.account_number,
                 updated_at=excluded.updated_at""",
            (user["id"], bank_name, account_name, account_number, now(), now()),
        )
        conn.commit()
        flash("Bank account saved successfully.", "success")
    finally:
        conn.close()
    return redirect(url_for("home"))


@app.route("/withdraw", methods=["POST"])
def withdraw():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    from datetime import datetime as _dt
    hour = _dt.now().hour
    if hour < WITHDRAWAL_START_HOUR or hour >= WITHDRAWAL_END_HOUR:
        flash("Withdrawals are available only from 9:00 AM to 5:00 PM.", "error")
        return redirect(url_for("home"))

    try:
        amount = float(request.form.get("amount", "0"))
    except ValueError:
        amount = 0

    if amount < MIN_WITHDRAWAL:
        flash(f"Minimum withdrawal amount is {MIN_WITHDRAWAL} ETB.", "error")
        return redirect(url_for("home"))

    conn = db()
    try:
        bank = conn.execute(
            "SELECT * FROM bank_accounts WHERE user_id=?", (user["id"],)
        ).fetchone()

        if not bank:
            flash("Please bind your bank account before requesting a withdrawal.", "error")
            return redirect(url_for("home"))

        fee = round(amount * WITHDRAWAL_FEE, 2)
        net = round(amount - fee, 2)

        cur = conn.execute(
            """UPDATE users
               SET balance=balance-?
               WHERE id=? AND balance>=?""",
            (amount, user["id"], amount),
        )
        if cur.rowcount != 1:
            conn.rollback()
            flash("Insufficient available balance.", "error")
            return redirect(url_for("home"))

        conn.execute(
            """INSERT INTO withdrawals
               (user_id,amount,fee,net_amount,account_number,account_name,status,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                user["id"], amount, fee, net,
                bank["account_number"], bank["account_name"],
                "PENDING", now()
            ),
        )
        add_history(
            conn, user["id"], "WITHDRAWAL_REQUESTED", amount,
            f"{bank['bank_name']} / {bank['account_number']} · Fee: {fee:.2f} ETB · Net: {net:.2f} ETB"
        )
        conn.commit()
        flash("Withdrawal submitted. It will be reviewed within 24 hours.", "success")
    finally:
        conn.close()

    return redirect(url_for("home"))


def admin_ok():
    return bool(ADMIN_KEY) and request.args.get("key", "") == ADMIN_KEY


@app.route("/admin")
def admin():
    if not admin_ok():
        return "Unauthorized", 401

    conn = db()
    pending_deposits = conn.execute(
        """SELECT d.*,u.phone
           FROM deposits d JOIN users u ON u.id=d.user_id
           WHERE d.status='PENDING'
           ORDER BY d.id DESC"""
    ).fetchall()
    pending_withdrawals = conn.execute(
        """SELECT w.*,u.phone
           FROM withdrawals w JOIN users u ON u.id=w.user_id
           WHERE w.status='PENDING'
           ORDER BY w.id DESC"""
    ).fetchall()
    recent_deposits = conn.execute(
        """SELECT d.*,u.phone
           FROM deposits d JOIN users u ON u.id=d.user_id
           WHERE d.status!='PENDING'
           ORDER BY d.id DESC LIMIT 30"""
    ).fetchall()
    recent_withdrawals = conn.execute(
        """SELECT w.*,u.phone
           FROM withdrawals w JOIN users u ON u.id=w.user_id
           WHERE w.status!='PENDING'
           ORDER BY w.id DESC LIMIT 30"""
    ).fetchall()
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    pending_deposit_total = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM deposits WHERE status='PENDING'"
    ).fetchone()[0]
    pending_withdrawal_total = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM withdrawals WHERE status='PENDING'"
    ).fetchone()[0]
    conn.close()

    return render_template(
        "admin.html",
        pending_deposits=pending_deposits,
        pending_withdrawals=pending_withdrawals,
        recent_deposits=recent_deposits,
        recent_withdrawals=recent_withdrawals,
        user_count=user_count,
        pending_deposit_total=pending_deposit_total,
        pending_withdrawal_total=pending_withdrawal_total,
        admin_key=ADMIN_KEY,
    )


@app.post("/admin/deposit/<int:item>/<action>")
def admin_deposit(item, action):
    if not admin_ok():
        return "Unauthorized", 401
    if action not in ("approve", "reject"):
        return "Bad request", 400

    conn = db()
    try:
        deposit = conn.execute(
            "SELECT * FROM deposits WHERE id=? AND status='PENDING'",
            (item,),
        ).fetchone()
        if not deposit:
            flash("Deposit not found or already reviewed.", "error")
            return redirect(url_for("admin", key=ADMIN_KEY))

        status = "APPROVED" if action == "approve" else "REJECTED"

        if status == "APPROVED":
            conn.execute(
                "UPDATE users SET balance=balance+? WHERE id=?",
                (deposit["amount"], deposit["user_id"]),
            )

        add_history(
            conn, deposit["user_id"], f"DEPOSIT_{status}",
            deposit["amount"], f"Reference: {deposit['reference']}"
        )
        conn.execute(
            "UPDATE deposits SET status=?,reviewed_at=? WHERE id=?",
            (status, now(), item),
        )
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("admin", key=ADMIN_KEY))


@app.post("/admin/withdrawal/<int:item>/<action>")
def admin_withdrawal(item, action):
    if not admin_ok():
        return "Unauthorized", 401
    if action not in ("paid", "reject"):
        return "Bad request", 400

    conn = db()
    try:
        withdrawal = conn.execute(
            "SELECT * FROM withdrawals WHERE id=? AND status='PENDING'",
            (item,),
        ).fetchone()
        if not withdrawal:
            flash("Withdrawal not found or already reviewed.", "error")
            return redirect(url_for("admin", key=ADMIN_KEY))

        if action == "paid":
            status = "PAID"
            add_history(
                conn, withdrawal["user_id"], "WITHDRAWAL_PAID",
                withdrawal["net_amount"],
                f"Fee: {withdrawal['fee']:.2f} ETB"
            )
        else:
            status = "REJECTED"
            # Return the reserved gross amount to the user's available balance.
            conn.execute(
                "UPDATE users SET balance=balance+? WHERE id=?",
                (withdrawal["amount"], withdrawal["user_id"]),
            )
            add_history(
                conn, withdrawal["user_id"], "WITHDRAWAL_REJECTED",
                withdrawal["amount"], "Reserved amount returned"
            )

        conn.execute(
            "UPDATE withdrawals SET status=?,reviewed_at=? WHERE id=?",
            (status, now(), item),
        )
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("admin", key=ADMIN_KEY))


@app.route("/referral")
def referral():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    link = request.host_url.rstrip("/") + "/register?ref=" + user["referral_code"]
    return render_home(user, link)


@app.route("/support")
def support():
    if not CUSTOMER_SERVICE_URL:
        return "Customer service URL is not configured.", 503
    return redirect(CUSTOMER_SERVICE_URL)


@app.route("/channel")
def channel():
    if not OFFICIAL_TELEGRAM_URL:
        return "Official channel URL is not configured.", 503
    return redirect(OFFICIAL_TELEGRAM_URL)


@app.get("/health")
def health():
    return {"status": "ok"}


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
