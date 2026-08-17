# app.py
import os
import sqlite3
import secrets
from datetime import datetime, time
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "CHANGE_THIS_SECRET_KEY")

DB_PATH = os.getenv("DATABASE_PATH", "nexa.db")

ADMIN_KEY = os.getenv("ADMIN_KEY", "NEXA_ADMIN")
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "CHANGE_THIS_ADMIN_SECRET")

CUSTOMER_SERVICE_URL = os.getenv(
    "CUSTOMER_SERVICE_URL",
    "https://t.me/NexaSupport11"
)

CHANNEL_URL = os.getenv(
    "CHANNEL_URL",
    "https://t.me/NexaOfficial_1"
)

BANK_NAME = os.getenv("BANK_NAME", "Commercial Bank of Ethiopia (CBE)")
BANK_ACCOUNT_NAME = os.getenv("BANK_ACCOUNT_NAME", "")
BANK_ACCOUNT_NUMBER = os.getenv("BANK_ACCOUNT_NUMBER", "")

MIN_DEPOSIT = 500
MIN_WITHDRAW = 200
WITHDRAW_FEE = 0.10

PLANS = {
    "A": {"amount": 500, "daily": 100},
    "B": {"amount": 1000, "daily": 200},
    "C": {"amount": 2000, "daily": 400},
    "D": {"amount": 5000, "daily": 1000},
    "E": {"amount": 10000, "daily": 2000},
    "F": {"amount": 20000, "daily": 4000},
}


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        referral_code TEXT UNIQUE NOT NULL,
        referred_by INTEGER,
        balance REAL DEFAULT 0,
        reserved_balance REAL DEFAULT 0,
        total_deposit REAL DEFAULT 0,
        total_earned REAL DEFAULT 0,
        total_withdrawn REAL DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS bank_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        bank_name TEXT NOT NULL,
        account_name TEXT NOT NULL,
        account_number TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS deposits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        reference TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING',
        created_at TEXT NOT NULL,
        reviewed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        fee REAL NOT NULL,
        receive_amount REAL NOT NULL,
        bank_name TEXT NOT NULL,
        account_name TEXT NOT NULL,
        account_number TEXT NOT NULL,
        status TEXT DEFAULT 'PROCESSING',
        created_at TEXT NOT NULL,
        processed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        plan_code TEXT NOT NULL,
        amount REAL NOT NULL,
        daily_profit REAL NOT NULL,
        status TEXT DEFAULT 'ACTIVE',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        amount REAL NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS referral_commissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        source_user_id INTEGER NOT NULL,
        level INTEGER NOT NULL,
        amount REAL NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()


init_db()


def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


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


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("index"))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper


def generate_referral():
    while True:
        code = secrets.token_hex(4).upper()
        conn = db()
        exists = conn.execute(
            "SELECT id FROM users WHERE referral_code = ?", (code,)
        ).fetchone()
        conn.close()

        if not exists:
            return code


def get_referral_url(code):
    base = request.url_root.rstrip("/")
    return f"{base}/register?ref={code}"


def add_transaction(conn, user_id, tx_type, amount, description):
    conn.execute(
        """
        INSERT INTO transactions
        (user_id, type, amount, description, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, tx_type, amount, description, now())
    )


def distribute_referral_commission(conn, user_id, base_amount):
    percentages = {
        1: 0.25,
        2: 0.03,
        3: 0.02
    }

    current_id = user_id

    for level in range(1, 4):
        parent = conn.execute(
            "SELECT referred_by FROM users WHERE id = ?",
            (current_id,)
        ).fetchone()

        if not parent or not parent["referred_by"]:
            break

        parent_id = parent["referred_by"]
        commission = round(base_amount * percentages[level], 2)

        if commission > 0:
            conn.execute(
                """
                UPDATE users
                SET balance = balance + ?,
                    total_earned = total_earned + ?
                WHERE id = ?
                """,
                (commission, commission, parent_id)
            )

            add_transaction(
                conn,
                parent_id,
                "REFERRAL",
                commission,
                f"Level {level} referral commission"
            )

            conn.execute(
                """
                INSERT INTO referral_commissions
                (user_id, source_user_id, level, amount, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    parent_id,
                    user_id,
                    level,
                    commission,
                    now()
                )
            )

        current_id = parent_id


@app.context_processor
def inject_globals():
    user = current_user()

    return {
        "current_user": user,
        "plans": PLANS,
        "channel_url": CHANNEL_URL,
        "customer_service_url": CUSTOMER_SERVICE_URL
    }


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    referral = request.args.get("ref", "")
    return render_template("index.html", referral=referral)


@app.route("/register", methods=["GET", "POST"])
def register():
    referral = request.args.get("ref", "")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        referral = request.form.get("referral", "").strip().upper()

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("index.html", referral=referral)

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("index.html", referral=referral)

        if len(password) < 6:
            flash("Password must contain at least 6 characters.", "error")
            return render_template("index.html", referral=referral)

        conn = db()

        exists = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if exists:
            conn.close()
            flash("Username already exists.", "error")
            return render_template("index.html", referral=referral)

        referred_by = None

        if referral:
            ref_user = conn.execute(
                "SELECT id FROM users WHERE referral_code = ?",
                (referral,)
            ).fetchone()

            if ref_user:
                referred_by = ref_user["id"]

        code = generate_referral()

        conn.execute(
            """
            INSERT INTO users
            (username, password, referral_code, referred_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                username,
                generate_password_hash(password),
                code,
                referred_by,
                now()
            )
        )

        conn.commit()

        user = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        conn.close()

        session["user_id"] = user["id"]

        flash("NEXA account created successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("index.html", referral=referral)


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    conn = db()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    conn.close()

    if not user or not check_password_hash(user["password"], password):
        flash("Invalid username or password.", "error")
        return redirect(url_for("index"))

    session["user_id"] = user["id"]
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()

    conn = db()

    active_plans = conn.execute(
        """
        SELECT * FROM plans
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user["id"],)
    ).fetchall()

    recent_transactions = conn.execute(
        """
        SELECT * FROM transactions
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 10
        """,
        (user["id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "index.html",
        page="dashboard",
        active_plans=active_plans,
        recent_transactions=recent_transactions,
        referral_url=get_referral_url(user["referral_code"])
    )


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", "0"))
        except ValueError:
            amount = 0

        reference = request.form.get("reference", "").strip()

        if amount < MIN_DEPOSIT:
            flash(f"Minimum deposit is {MIN_DEPOSIT} ETB.", "error")
            return redirect(url_for("deposit"))

        if not reference:
            flash("Transaction/reference number is required.", "error")
            return redirect(url_for("deposit"))

        conn = db()

        duplicate = conn.execute(
            "SELECT id FROM deposits WHERE reference = ?",
            (reference,)
        ).fetchone()

        if duplicate:
            conn.close()
            flash("This transaction/reference has already been submitted.", "error")
            return redirect(url_for("deposit"))

        conn.execute(
            """
            INSERT INTO deposits
            (user_id, amount, reference, status, created_at)
            VALUES (?, ?, ?, 'PENDING', ?)
            """,
            (
                current_user()["id"],
                amount,
                reference,
                now()
            )
        )

        conn.commit()
        conn.close()

        flash("Deposit submitted. Waiting for admin verification.", "success")
        return redirect(url_for("wallet"))

    return render_template(
        "index.html",
        page="deposit",
        bank_name=BANK_NAME,
        bank_account_name=BANK_ACCOUNT_NAME,
        bank_account_number=BANK_ACCOUNT_NUMBER
    )


@app.route("/buy-plan/<plan_code>", methods=["GET", "POST"])
@login_required
def buy_plan(plan_code):
    plan_code = plan_code.upper()

    if plan_code not in PLANS:
        flash("Invalid plan.", "error")
        return redirect(url_for("dashboard"))

    plan = PLANS[plan_code]

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", "0"))
        except ValueError:
            amount = 0

        reference = request.form.get("reference", "").strip()

        if amount != plan["amount"]:
            flash(
                f"Payment amount must be exactly {plan['amount']} ETB.",
                "error"
            )
            return redirect(url_for("buy_plan", plan_code=plan_code))

        if not reference:
            flash("Transaction/reference number is required.", "error")
            return redirect(url_for("buy_plan", plan_code=plan_code))

        conn = db()

        duplicate = conn.execute(
            "SELECT id FROM deposits WHERE reference = ?",
            (reference,)
        ).fetchone()

        if duplicate:
            conn.close()
            flash("This reference number has already been used.", "error")
            return redirect(url_for("buy_plan", plan_code=plan_code))

        conn.execute(
            """
            INSERT INTO deposits
            (user_id, amount, reference, status, created_at)
            VALUES (?, ?, ?, 'PENDING', ?)
            """,
            (
                current_user()["id"],
                amount,
                reference,
                now()
            )
        )

        conn.commit()
        conn.close()

        flash(
            "Plan payment submitted. Admin verification is required.",
            "success"
        )

        return redirect(url_for("wallet"))

    return render_template(
        "index.html",
        page="payment",
        selected_plan=plan_code,
        plan=plan,
        bank_name=BANK_NAME,
        bank_account_name=BANK_ACCOUNT_NAME,
        bank_account_number=BANK_ACCOUNT_NUMBER
    )


@app.route("/wallet")
@login_required
def wallet():
    user = current_user()

    conn = db()

    deposits = conn.execute(
        """
        SELECT * FROM deposits
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user["id"],)
    ).fetchall()

    withdrawals = conn.execute(
        """
        SELECT * FROM withdrawals
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user["id"],)
    ).fetchall()

    transactions = conn.execute(
        """
        SELECT * FROM transactions
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user["id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "index.html",
        page="wallet",
        deposits=deposits,
        withdrawals=withdrawals,
        transactions=transactions
    )


@app.route("/bank-bind", methods=["GET", "POST"])
@login_required
def bank_bind():
    user = current_user()

    conn = db()

    existing = conn.execute(
        "SELECT * FROM bank_accounts WHERE user_id = ?",
        (user["id"],)
    ).fetchone()

    if request.method == "POST":
        bank_name = request.form.get("bank_name", "").strip()
        account_name = request.form.get("account_name", "").strip()
        account_number = request.form.get("account_number", "").strip()

        if not bank_name or not account_name or not account_number:
            conn.close()
            flash("All bank details are required.", "error")
            return redirect(url_for("bank_bind"))

        if existing:
            conn.execute(
                """
                UPDATE bank_accounts
                SET bank_name = ?, account_name = ?, account_number = ?
                WHERE user_id = ?
                """,
                (
                    bank_name,
                    account_name,
                    account_number,
                    user["id"]
                )
            )
        else:
            conn.execute(
                """
                INSERT INTO bank_accounts
                (user_id, bank_name, account_name, account_number, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user["id"],
                    bank_name,
                    account_name,
                    account_number,
                    now()
                )
            )

        conn.commit()
        conn.close()

        flash("Bank account saved successfully.", "success")
        return redirect(url_for("bank_bind"))

    conn.close()

    return render_template(
        "index.html",
        page="bank",
        bank_account=existing
    )


@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():
    user = current_user()

    conn = db()

    bank = conn.execute(
        "SELECT * FROM bank_accounts WHERE user_id = ?",
        (user["id"],)
    ).fetchone()

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", "0"))
        except ValueError:
            amount = 0

        if amount < MIN_WITHDRAW:
            conn.close()
            flash(
                f"Minimum withdrawal is {MIN_WITHDRAW} ETB.",
                "error"
            )
            return redirect(url_for("withdraw"))

        if amount > user["balance"]:
            conn.close()
            flash("Insufficient available balance.", "error")
            return redirect(url_for("withdraw"))

        current_time = datetime.now().time()

        if not (
            time(9, 0) <= current_time <= time(17, 0)
        ):
            conn.close()
            flash(
                "Withdrawals are available only from 9:00 AM to 5:00 PM.",
                "error"
            )
            return redirect(url_for("withdraw"))

        if not bank:
            conn.close()
            flash("Please bind your bank account first.", "error")
            return redirect(url_for("bank_bind"))

        fee = round(amount * WITHDRAW_FEE, 2)
        receive_amount = round(amount - fee, 2)

        conn.execute(
            """
            UPDATE users
            SET balance = balance - ?,
                reserved_balance = reserved_balance + ?
            WHERE id = ?
            """,
            (amount, amount, user["id"])
        )

        conn.execute(
            """
            INSERT INTO withdrawals
            (
                user_id,
                amount,
                fee,
                receive_amount,
                bank_name,
                account_name,
                account_number,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'PROCESSING', ?)
            """,
            (
                user["id"],
                amount,
                fee,
                receive_amount,
                bank["bank_name"],
                bank["account_name"],
                bank["account_number"],
                now()
            )
        )

        add_transaction(
            conn,
            user["id"],
            "WITHDRAWAL",
            -amount,
            f"Withdrawal request. Fee: {fee:.2f} ETB"
        )

        conn.commit()
        conn.close()

        flash(
            f"Withdrawal submitted. You will receive {receive_amount:.2f} ETB after the 10% fee.",
            "success"
        )

        return redirect(url_for("wallet"))

    conn.close()

    return render_template(
        "index.html",
        page="withdraw",
        bank_account=bank
    )


@app.route("/team")
@login_required
def team():
    user = current_user()

    conn = db()

    level1 = conn.execute(
        """
        SELECT id, username, referral_code, created_at
        FROM users
        WHERE referred_by = ?
        ORDER BY id DESC
        """,
        (user["id"],)
    ).fetchall()

    level1_ids = [row["id"] for row in level1]

    level2 = []
    level3 = []

    if level1_ids:
        placeholders = ",".join("?" * len(level1_ids))

        level2 = conn.execute(
            f"""
            SELECT id, username, referral_code, created_at
            FROM users
            WHERE referred_by IN ({placeholders})
            ORDER BY id DESC
            """,
            level1_ids
        ).fetchall()

        level2_ids = [row["id"] for row in level2]

        if level2_ids:
            placeholders2 = ",".join("?" * len(level2_ids))

            level3 = conn.execute(
                f"""
                SELECT id, username, referral_code, created_at
                FROM users
                WHERE referred_by IN ({placeholders2})
                ORDER BY id DESC
                """,
                level2_ids
            ).fetchall()

    conn.close()

    return render_template(
        "index.html",
        page="team",
        referral_code=user["referral_code"],
        referral_url=get_referral_url(user["referral_code"]),
        level1=level1,
        level2=level2,
        level3=level3
    )


@app.route("/support")
@login_required
def support():
    return redirect(CUSTOMER_SERVICE_URL)


@app.route("/channel")
@login_required
def channel():
    return redirect(CHANNEL_URL)


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        key = request.form.get("admin_key", "")
        secret = request.form.get("admin_secret", "")

        if key == ADMIN_KEY and secret == ADMIN_SECRET:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin credentials.", "error")

    return render_template("admin.html", page="login")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    conn = db()

    users = conn.execute(
        "SELECT * FROM users ORDER BY id DESC"
    ).fetchall()

    pending_deposits = conn.execute(
        """
        SELECT deposits.*, users.username
        FROM deposits
        JOIN users ON users.id = deposits.user_id
        WHERE deposits.status = 'PENDING'
        ORDER BY deposits.id DESC
        """
    ).fetchall()

    withdrawals = conn.execute(
        """
        SELECT withdrawals.*, users.username
        FROM withdrawals
        JOIN users ON users.id = withdrawals.user_id
        WHERE withdrawals.status = 'PROCESSING'
        ORDER BY withdrawals.id DESC
        """
    ).fetchall()

    recent_deposits = conn.execute(
        """
        SELECT deposits.*, users.username
        FROM deposits
        JOIN users ON users.id = deposits.user_id
        ORDER BY deposits.id DESC
        LIMIT 50
        """
    ).fetchall()

    recent_withdrawals = conn.execute(
        """
        SELECT withdrawals.*, users.username
        FROM withdrawals
        JOIN users ON users.id = withdrawals.user_id
        ORDER BY withdrawals.id DESC
        LIMIT 50
        """
    ).fetchall()

    stats = {
        "users": conn.execute(
            "SELECT COUNT(*) c FROM users"
        ).fetchone()["c"],
        "pending_deposits": conn.execute(
            "SELECT COUNT(*) c FROM deposits WHERE status='PENDING'"
        ).fetchone()["c"],
        "processing_withdrawals": conn.execute(
            "SELECT COUNT(*) c FROM withdrawals WHERE status='PROCESSING'"
        ).fetchone()["c"],
        "total_deposits": conn.execute(
            "SELECT COALESCE(SUM(amount),0) s FROM deposits WHERE status='APPROVED'"
        ).fetchone()["s"],
        "total_withdrawals": conn.execute(
            "SELECT COALESCE(SUM(amount),0) s FROM withdrawals WHERE status='PAID'"
        ).fetchone()["s"]
    }

    conn.close()

    return render_template(
        "admin.html",
        page="dashboard",
        users=users,
        pending_deposits=pending_deposits,
        withdrawals=withdrawals,
        recent_deposits=recent_deposits,
        recent_withdrawals=recent_withdrawals,
        stats=stats
    )


@app.route("/admin/deposit/<int:deposit_id>/approve", methods=["POST"])
@admin_required
def approve_deposit(deposit_id):
    conn = db()

    deposit = conn.execute(
        "SELECT * FROM deposits WHERE id = ?",
        (deposit_id,)
    ).fetchone()

    if not deposit or deposit["status"] != "PENDING":
        conn.close()
        flash("Deposit is no longer pending.", "error")
        return redirect(url_for("admin_dashboard"))

    conn.execute(
        """
        UPDATE deposits
        SET status='APPROVED', reviewed_at=?
        WHERE id=?
        """,
        (now(), deposit_id)
    )

    conn.execute(
        """
        UPDATE users
        SET balance = balance + ?,
            total_deposit = total_deposit + ?
        WHERE id = ?
        """,
        (
            deposit["amount"],
            deposit["amount"],
            deposit["user_id"]
        )
    )

    add_transaction(
        conn,
        deposit["user_id"],
        "DEPOSIT",
        deposit["amount"],
        f"Deposit approved. Reference: {deposit['reference']}"
    )

    conn.commit()
    conn.close()

    flash("Deposit approved and balance credited.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/deposit/<int:deposit_id>/reject", methods=["POST"])
@admin_required
def reject_deposit(deposit_id):
    conn = db()

    deposit = conn.execute(
        "SELECT * FROM deposits WHERE id = ?",
        (deposit_id,)
    ).fetchone()

    if not deposit or deposit["status"] != "PENDING":
        conn.close()
        flash("Deposit is no longer pending.", "error")
        return redirect(url_for("admin_dashboard"))

    conn.execute(
        """
        UPDATE deposits
        SET status='REJECTED', reviewed_at=?
        WHERE id=?
        """,
        (now(), deposit_id)
    )

    conn.commit()
    conn.close()

    flash("Deposit rejected.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/withdraw/<int:withdrawal_id>/paid", methods=["POST"])
@admin_required
def mark_withdrawal_paid(withdrawal_id):
    conn = db()

    withdrawal = conn.execute(
        "SELECT * FROM withdrawals WHERE id = ?",
        (withdrawal_id,)
    ).fetchone()

    if not withdrawal or withdrawal["status"] != "PROCESSING":
        conn.close()
        flash("Withdrawal is no longer processing.", "error")
        return redirect(url_for("admin_dashboard"))

    conn.execute(
        """
        UPDATE users
        SET reserved_balance = reserved_balance - ?,
            total_withdrawn = total_withdrawn + ?
        WHERE id = ?
        """,
        (
            withdrawal["amount"],
            withdrawal["receive_amount"],
            withdrawal["user_id"]
        )
    )

    conn.execute(
        """
        UPDATE withdrawals
        SET status='PAID', processed_at=?
        WHERE id=?
        """,
        (now(), withdrawal_id)
    )

    add_transaction(
        conn,
        withdrawal["user_id"],
        "WITHDRAWAL_PAID",
        withdrawal["receive_amount"],
        "Withdrawal marked PAID by admin"
    )

    conn.commit()
    conn.close()

    flash("Withdrawal marked as PAID.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/withdraw/<int:withdrawal_id>/reject", methods=["POST"])
@admin_required
def reject_withdrawal(withdrawal_id):
    conn = db()

    withdrawal = conn.execute(
        "SELECT * FROM withdrawals WHERE id = ?",
        (withdrawal_id,)
    ).fetchone()

    if not withdrawal or withdrawal["status"] != "PROCESSING":
        conn.close()
        flash("Withdrawal is no longer processing.", "error")
        return redirect(url_for("admin_dashboard"))

    conn.execute(
        """
        UPDATE users
        SET balance = balance + ?,
            reserved_balance = reserved_balance - ?
        WHERE id = ?
        """,
        (
            withdrawal["amount"],
            withdrawal["amount"],
            withdrawal["user_id"]
        )
    )

    conn.execute(
        """
        UPDATE withdrawals
        SET status='REJECTED', processed_at=?
        WHERE id=?
        """,
        (now(), withdrawal_id)
    )

    add_transaction(
        conn,
        withdrawal["user_id"],
        "WITHDRAWAL_REJECTED",
        withdrawal["amount"],
        "Withdrawal rejected; reserved balance returned"
    )

    conn.commit()
    conn.close()

    flash("Withdrawal rejected and reserved balance returned.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/plan/<int:deposit_id>/activate", methods=["POST"])
@admin_required
def activate_plan(deposit_id):
    conn = db()

    deposit = conn.execute(
        """
        SELECT * FROM deposits
        WHERE id = ? AND status = 'APPROVED'
        """,
        (deposit_id,)
    ).fetchone()

    if not deposit:
        conn.close()
        flash("Approved deposit not found.", "error")
        return redirect(url_for("admin_dashboard"))

    plan_code = request.form.get("plan_code", "").upper()

    if plan_code not in PLANS:
        conn.close()
        flash("Invalid plan.", "error")
        return redirect(url_for("admin_dashboard"))

    plan = PLANS[plan_code]

    conn.execute(
        """
        INSERT INTO plans
        (user_id, plan_code, amount, daily_profit, status, created_at)
        VALUES (?, ?, ?, ?, 'ACTIVE', ?)
        """,
        (
            deposit["user_id"],
            plan_code,
            plan["amount"],
            plan["daily"],
            now()
        )
    )

    distribute_referral_commission(
        conn,
        deposit["user_id"],
        deposit["amount"]
    )

    conn.commit()
    conn.close()

    flash("Plan activated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/api/me")
@login_required
def api_me():
    user = current_user()

    return jsonify({
        "username": user["username"],
        "balance": user["balance"],
        "reserved_balance": user["reserved_balance"],
        "total_deposit": user["total_deposit"],
        "total_earned": user["total_earned"],
        "total_withdrawn": user["total_withdrawn"],
        "referral_code": user["referral_code"]
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=False
    )
