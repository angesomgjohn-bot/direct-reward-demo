from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os, secrets
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DB = os.environ.get("DB_PATH", "nexa.db")
BANK_NAME = os.environ.get("BANK_NAME", "Commercial Bank of Ethiopia (CBE)")
BANK_ACCOUNT_NAME = os.environ.get("BANK_ACCOUNT_NAME", "")
BANK_ACCOUNT_NUMBER = os.environ.get("BANK_ACCOUNT_NUMBER", "")
OFFICIAL_TELEGRAM_URL = os.environ.get("OFFICIAL_TELEGRAM_URL", "https://t.me/NexaOfficial_1")
CUSTOMER_SERVICE_URL = os.environ.get("CUSTOMER_SERVICE_URL", "https://t.me/NexaSupport11")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
WITHDRAWAL_FEE = 0.10

PLANS = [
    {"id": "A", "name": "Plan A", "price": 500, "daily_reward": 100},
    {"id": "B", "name": "Plan B", "price": 1000, "daily_reward": 200},
    {"id": "C", "name": "Plan C", "price": 2000, "daily_reward": 400},
    {"id": "D", "name": "Plan D", "price": 5000, "daily_reward": 1000},
    {"id": "E", "name": "Plan E", "price": 10000, "daily_reward": 2000},
    {"id": "F", "name": "Plan F", "price": 20000, "daily_reward": 4000},
]


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = db()
    c.executescript("""
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
        UNIQUE(user_id, reference)
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
        reviewed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        amount REAL NOT NULL DEFAULT 0,
        note TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        plan_id TEXT NOT NULL,
        task_name TEXT NOT NULL,
        reward REAL NOT NULL,
        completed INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        completed_at TEXT
    );
    """)
    c.commit()
    c.close()


def get_user():
    uid = session.get("user_id")
    if not uid:
        return None
    c = db()
    u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    c.close()
    return u


def add_history(c, uid, action, amount=0, note=""):
    c.execute(
        """INSERT INTO history(user_id,action,amount,note,created_at)
           VALUES(?,?,?,?,?)""",
        (uid, action, amount, note, datetime.utcnow().isoformat()),
    )


def page_context(u):
    c = db()
    tasks = []
    history = []
    deposits = []
    withdrawals = []

    if u:
        tasks = c.execute(
            "SELECT * FROM tasks WHERE user_id=? ORDER BY id DESC",
            (u["id"],),
        ).fetchall()
        history = c.execute(
            "SELECT * FROM history WHERE user_id=? ORDER BY id DESC LIMIT 30",
            (u["id"],),
        ).fetchall()
        deposits = c.execute(
            "SELECT * FROM deposits WHERE user_id=? ORDER BY id DESC",
            (u["id"],),
        ).fetchall()
        withdrawals = c.execute(
            "SELECT * FROM withdrawals WHERE user_id=? ORDER BY id DESC",
            (u["id"],),
        ).fetchall()

    c.close()
    return dict(
        user=u,
        plans=PLANS,
        tasks=tasks,
        history=history,
        deposits=deposits,
        withdrawals=withdrawals,
        bank_name=BANK_NAME,
        bank_account_name=BANK_ACCOUNT_NAME,
        bank_account_number=BANK_ACCOUNT_NUMBER,
        official_telegram_url=OFFICIAL_TELEGRAM_URL,
        customer_service_url=CUSTOMER_SERVICE_URL,
    )


@app.route("/")
def home():
    return render_template("index.html", **page_context(get_user()))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        ref = request.form.get("referral", "").strip() or None

        if not phone or not password:
            flash("Phone and password are required.", "error")
            return redirect(url_for("register"))

        c = db()
        try:
            referral_code = secrets.token_hex(4).upper()
            cur = c.execute(
                """INSERT INTO users
                   (phone,password_hash,referral_code,referred_by,created_at)
                   VALUES(?,?,?,?,?)""",
                (
                    phone,
                    generate_password_hash(password),
                    referral_code,
                    ref,
                    datetime.utcnow().isoformat(),
                ),
            )
            add_history(c, cur.lastrowid, "ACCOUNT_CREATED")
            c.commit()
            session["user_id"] = cur.lastrowid
            c.close()
            return redirect(url_for("home"))
        except sqlite3.IntegrityError:
            c.rollback()
            c.close()
            flash("This phone number is already registered.", "error")
            return redirect(url_for("register"))

    return render_template("index.html", **page_context(None))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        c = db()
        u = c.execute(
            "SELECT * FROM users WHERE phone=?", (phone,)
        ).fetchone()
        c.close()

        if not u or not check_password_hash(u["password_hash"], password):
            flash("Invalid phone or password.", "error")
            return redirect(url_for("login"))

        session["user_id"] = u["id"]
        return redirect(url_for("home"))

    return render_template("index.html", **page_context(None))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/deposit", methods=["POST"])
def deposit():
    u = get_user()
    if not u:
        return redirect(url_for("login"))

    try:
        amount = float(request.form.get("amount", "0"))
    except ValueError:
        amount = 0

    reference = request.form.get("reference", "").strip()

    if amount <= 0 or not reference:
        flash("Enter amount and transaction/reference number.", "error")
        return redirect(url_for("home"))

    c = db()
    try:
        c.execute(
            """INSERT INTO deposits(user_id,amount,reference,created_at)
               VALUES(?,?,?,?)""",
            (u["id"], amount, reference, datetime.utcnow().isoformat()),
        )
        add_history(
            c,
            u["id"],
            "DEPOSIT_SUBMITTED",
            amount,
            "Reference: " + reference,
        )
        c.commit()
        flash("Deposit submitted for verification.", "success")
    except sqlite3.IntegrityError:
        c.rollback()
        flash("That reference was already submitted.", "error")
    c.close()
    return redirect(url_for("home"))


@app.route("/start-plan/<plan_id>", methods=["POST"])
def start_plan(plan_id):
    u = get_user()
    if not u:
        return redirect(url_for("login"))

    plan = next((p for p in PLANS if p["id"] == plan_id), None)
    if not plan:
        flash("Plan not found.", "error")
        return redirect(url_for("home"))

    c = db()
    cur = c.execute(
        """SELECT id FROM tasks
           WHERE user_id=? AND plan_id=? AND completed=0
           LIMIT 1""",
        (u["id"], plan_id),
    ).fetchone()

    if cur:
        c.close()
        flash("You already have an active task for this plan.", "error")
        return redirect(url_for("home"))

    c.execute(
        """INSERT INTO tasks
           (user_id,plan_id,task_name,reward,created_at)
           VALUES(?,?,?,?,?)""",
        (
            u["id"],
            plan["id"],
            f'{plan["name"]} Daily Task',
            plan["daily_reward"],
            datetime.utcnow().isoformat(),
        ),
    )
    add_history(
        c,
        u["id"],
        "PLAN_SELECTED",
        plan["price"],
        f'{plan["name"]} selected',
    )
    c.commit()
    c.close()

    flash(f'{plan["name"]} task created.', "success")
    return redirect(url_for("home"))


@app.route("/complete-task/<int:task_id>", methods=["POST"])
def complete_task(task_id):
    u = get_user()
    if not u:
        return redirect(url_for("login"))

    c = db()
    task = c.execute(
        """SELECT * FROM tasks
           WHERE id=? AND user_id=? AND completed=0""",
        (task_id, u["id"]),
    ).fetchone()

    if not task:
        c.close()
        flash("Task not found or already completed.", "error")
        return redirect(url_for("home"))

    c.execute(
        """UPDATE tasks
           SET completed=1, completed_at=?
           WHERE id=? AND user_id=? AND completed=0""",
        (datetime.utcnow().isoformat(), task_id, u["id"]),
    )

    if c.total_changes != 1:
        c.rollback()
        c.close()
        flash("Task could not be completed.", "error")
        return redirect(url_for("home"))

    c.execute(
        """UPDATE users
           SET balance=balance+?, total_earned=total_earned+?
           WHERE id=?""",
        (task["reward"], task["reward"], u["id"]),
    )

    add_history(
        c,
        u["id"],
        "TASK_COMPLETED",
        task["reward"],
        task["task_name"],
    )
    c.commit()
    c.close()

    flash(
        f'Task completed. {task["reward"]:.2f} ETB added to your wallet.',
        "success",
    )
    return redirect(url_for("home"))


@app.route("/withdraw", methods=["POST"])
def withdraw():
    u = get_user()
    if not u:
        return redirect(url_for("login"))

    try:
        amount = float(request.form.get("amount", "0"))
    except ValueError:
        amount = 0

    account_number = request.form.get("account_number", "").strip()
    account_name = request.form.get("account_name", "").strip()

    if amount <= 0 or not account_number or not account_name:
        flash(
            "Enter amount, account number and account name.",
            "error",
        )
        return redirect(url_for("home"))

    fee = round(amount * WITHDRAWAL_FEE, 2)
    net_amount = round(amount - fee, 2)

    c = db()
    c.execute(
        """UPDATE users
           SET balance=balance-?
           WHERE id=? AND balance>=?""",
        (amount, u["id"], amount),
    )

    if c.total_changes != 1:
        c.rollback()
        c.close()
        flash("Insufficient available balance.", "error")
        return redirect(url_for("home"))

    c.execute(
        """INSERT INTO withdrawals
           (user_id,amount,fee,net_amount,account_number,account_name,created_at)
           VALUES(?,?,?,?,?,?,?)""",
        (
            u["id"],
            amount,
            fee,
            net_amount,
            account_number,
            account_name,
            datetime.utcnow().isoformat(),
        ),
    )

    add_history(
        c,
        u["id"],
        "WITHDRAWAL_REQUESTED",
        amount,
        f"Fee: {fee:.2f}; Net: {net_amount:.2f}",
    )
    c.commit()
    c.close()

    flash(
        f"Withdrawal submitted. Fee {fee:.2f} ETB; net {net_amount:.2f} ETB.",
        "success",
    )
    return redirect(url_for("home"))


@app.route("/referral")
def referral():
    u = get_user()
    if not u:
        return redirect(url_for("login"))

    ctx = page_context(u)
    ctx["referral_link"] = (
        request.host_url.rstrip("/")
        + "/register?ref="
        + u["referral_code"]
    )
    return render_template("index.html", **ctx)


@app.route("/support")
def support():
    return redirect(CUSTOMER_SERVICE_URL)


@app.route("/channel")
def channel():
    return redirect(OFFICIAL_TELEGRAM_URL)


@app.route("/admin")
def admin():
    if not ADMIN_KEY or request.args.get("key") != ADMIN_KEY:
        return "Unauthorized", 401

    c = db()
    deposits = c.execute(
        """SELECT d.*,u.phone FROM deposits d
           JOIN users u ON u.id=d.user_id
           WHERE d.status='PENDING' ORDER BY d.id"""
    ).fetchall()
    withdrawals = c.execute(
        """SELECT w.*,u.phone FROM withdrawals w
           JOIN users u ON u.id=w.user_id
           WHERE w.status='PENDING' ORDER BY w.id"""
    ).fetchall()
    c.close()

    return render_template(
        "admin.html",
        deposits=deposits,
        withdrawals=withdrawals,
    )


@app.route("/admin/deposit/<int:item>/<action>")
def admin_deposit(item, action):
    if not ADMIN_KEY or request.args.get("key") != ADMIN_KEY:
        return "Unauthorized", 401
    if action not in ("approve", "reject"):
        return "Bad request", 400

    c = db()
    d = c.execute(
        "SELECT * FROM deposits WHERE id=? AND status='PENDING'",
        (item,),
    ).fetchone()

    if not d:
        c.close()
        return "Deposit not found or already reviewed", 404

    status = "APPROVED" if action == "approve" else "REJECTED"

    if action == "approve":
        c.execute(
            "UPDATE users SET balance=balance+? WHERE id=?",
            (d["amount"], d["user_id"]),
        )

    add_history(
        c,
        d["user_id"],
        "DEPOSIT_" + status,
        d["amount"],
        "Reference: " + d["reference"],
    )

    c.execute(
        "UPDATE deposits SET status=?,reviewed_at=? WHERE id=?",
        (status, datetime.utcnow().isoformat(), item),
    )
    c.commit()
    c.close()

    return redirect(url_for("admin", key=ADMIN_KEY))


@app.route("/admin/withdrawal/<int:item>/<action>")
def admin_withdrawal(item, action):
    if not ADMIN_KEY or request.args.get("key") != ADMIN_KEY:
        return "Unauthorized", 401
    if action not in ("paid", "reject"):
        return "Bad request", 400

    c = db()
    w = c.execute(
        "SELECT * FROM withdrawals WHERE id=? AND status='PENDING'",
        (item,),
    ).fetchone()

    if not w:
        c.close()
        return "Withdrawal not found or already reviewed", 404

    if action == "paid":
        add_history(
            c,
            w["user_id"],
            "WITHDRAWAL_PAID",
            w["net_amount"],
            f'Fee: {w["fee"]:.2f}',
        )
        status = "PAID"
    else:
        c.execute(
            "UPDATE users SET balance=balance+? WHERE id=?",
            (w["amount"], w["user_id"]),
        )
        add_history(
            c,
            w["user_id"],
            "WITHDRAWAL_REJECTED",
            w["amount"],
            "Reserved amount returned",
        )
        status = "REJECTED"

    c.execute(
        "UPDATE withdrawals SET status=?,reviewed_at=? WHERE id=?",
        (status, datetime.utcnow().isoformat(), item),
    )
    c.commit()
    c.close()

    return redirect(url_for("admin", key=ADMIN_KEY))


init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
    )
