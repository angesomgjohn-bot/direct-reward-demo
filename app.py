from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import os
import secrets
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "nexa-demo-change-this")

DB = "nexa.db"

PLANS = [
    {
        "id": "A",
        "name": "Plan A",
        "price": 500,
        "tasks": [
            ("Task 1", 20),
            ("Task 2", 25),
            ("Task 3", 25)
        ]
    },
    {
        "id": "B",
        "name": "Plan B",
        "price": 1000,
        "tasks": [
            ("Task 1", 45),
            ("Task 2", 45),
            ("Task 3", 50)
        ]
    },
    {
        "id": "C",
        "name": "Plan C",
        "price": 2000,
        "tasks": [
            ("Task 1", 70),
            ("Task 2", 70),
            ("Task 3", 90)
        ]
    },
    {
        "id": "D",
        "name": "Plan D",
        "price": 5000,
        "tasks": [
            ("Task 1", 120),
            ("Task 2", 120),
            ("Task 3", 160)
        ]
    }
]


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

    conn.commit()
    conn.close()


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


@app.route("/")
def home():
    user = current_user()

    if not user:
        return redirect(url_for("login"))

    conn = db()

    tasks = conn.execute("""
        SELECT *
        FROM tasks
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user["id"],)).fetchall()

    history = conn.execute("""
        SELECT *
        FROM history
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 20
    """, (user["id"],)).fetchall()

    conn.close()

    return render_template(
        "index.html",
        user=user,
        plans=PLANS,
        tasks=tasks,
        history=history
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()
        referral = request.form.get("referral", "").strip()

        if not phone or not password:
            return render_template(
                "index.html",
                register_error="Phone and password are required.",
                plans=PLANS
            )

        referral_code = secrets.token_hex(4).upper()

        conn = db()

        try:
            conn.execute("""
                INSERT INTO users
                (phone, password, referral_code, referred_by, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                phone,
                password,
                referral_code,
                referral or None,
                datetime.utcnow().isoformat()
            ))

            conn.commit()

            user = conn.execute(
                "SELECT * FROM users WHERE phone = ?",
                (phone,)
            ).fetchone()

            session["user_id"] = user["id"]

            conn.execute("""
                INSERT INTO history
                (user_id, action, amount, note, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user["id"],
                "ACCOUNT_CREATED",
                0,
                "NEXA demo account created",
                datetime.utcnow().isoformat()
            ))

            conn.commit()

        except sqlite3.IntegrityError:
            conn.close()
            return render_template(
                "index.html",
                register_error="This phone number is already registered.",
                plans=PLANS
            )

        conn.close()
        return redirect(url_for("home"))

    return render_template("index.html", plans=PLANS)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()

        conn = db()
        user = conn.execute("""
            SELECT *
            FROM users
            WHERE phone = ? AND password = ?
        """, (phone, password)).fetchone()
        conn.close()

        if not user:
            return render_template(
                "index.html",
                login_error="Invalid phone or password.",
                plans=PLANS
            )

        session["user_id"] = user["id"]
        return redirect(url_for("home"))

    return render_template("index.html", plans=PLANS)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/start-plan/<plan_id>", methods=["POST"])
def start_plan(plan_id):
    user = current_user()

    if not user:
        return redirect(url_for("login"))

    plan = next(
        (p for p in PLANS if p["id"] == plan_id),
        None
    )

    if not plan:
        return redirect(url_for("home"))

    conn = db()

    # Demo only:
    # No real payment/deposit is accepted.
    now = datetime.utcnow()

    for task_name, reward in plan["tasks"]:
        conn.execute("""
            INSERT INTO tasks
            (user_id, plan_id, task_name, reward,
             completed, available_at)
            VALUES (?, ?, ?, ?, 0, ?)
        """, (
            user["id"],
            plan["id"],
            task_name,
            reward,
            now.isoformat()
        ))

    conn.execute("""
        INSERT INTO history
        (user_id, action, amount, note, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        user["id"],
        "DEMO_PLAN_STARTED",
        0,
        f"{plan['name']} started in demo mode",
        now.isoformat()
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("home"))


@app.route("/complete-task/<int:task_id>", methods=["POST"])
def complete_task(task_id):
    user = current_user()

    if not user:
        return redirect(url_for("login"))

    conn = db()

    task = conn.execute("""
        SELECT *
        FROM tasks
        WHERE id = ? AND user_id = ?
    """, (task_id, user["id"])).fetchone()

    if not task or task["completed"]:
        conn.close()
        return redirect(url_for("home"))

    available = datetime.fromisoformat(task["available_at"])

    # Each task is available once every 24 hours.
    if datetime.utcnow() < available:
        conn.close()
        return redirect(url_for("home"))

    conn.execute("""
        UPDATE tasks
        SET completed = 1,
            completed_at = ?
        WHERE id = ?
    """, (
        datetime.utcnow().isoformat(),
        task_id
    ))

    # Demo wallet credit only.
    conn.execute("""
        UPDATE users
        SET balance = balance + ?,
            total_earned = total_earned + ?
        WHERE id = ?
    """, (
        task["reward"],
        task["reward"],
        user["id"]
    ))

    conn.execute("""
        INSERT INTO history
        (user_id, action, amount, note, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        user["id"],
        "TASK_REWARD",
        task["reward"],
        f"Demo reward: {task['task_name']}",
        datetime.utcnow().isoformat()
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("home"))


@app.route("/wallet")
def wallet():
    user = current_user()

    if not user:
        return redirect(url_for("login"))

    conn = db()

    history = conn.execute("""
        SELECT *
        FROM history
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user["id"],)).fetchall()

    conn.close()

    return render_template(
        "index.html",
        user=user,
        plans=PLANS,
        history=history,
        wallet_page=True
    )


@app.route("/withdraw", methods=["POST"])
def withdraw():
    user = current_user()

    if not user:
        return redirect(url_for("login"))

    # Real withdrawals are intentionally disabled.
    return render_template(
        "index.html",
        user=user,
        plans=PLANS,
        withdraw_message=(
            "Withdrawals are disabled in this demo version. "
            "No real money is transferred."
        )
    )


@app.route("/referral")
def referral():
    user = current_user()

    if not user:
        return redirect(url_for("login"))

    referral_link = (
        request.host_url.rstrip("/")
        + "/register?ref="
        + user["referral_code"]
    )

    return render_template(
        "index.html",
        user=user,
        plans=PLANS,
        referral_link=referral_link
    )


@app.route("/support")
def support():
    return render_template(
        "index.html",
        user=current_user(),
        plans=PLANS,
        support=True
    )


@app.route("/channel")
def channel():
    return redirect("https://t.me/NexaOfficial_1")


@app.route("/api/status")
def status():
    user = current_user()

    if not user:
        return jsonify({"logged_in": False})

    return jsonify({
        "logged_in": True,
        "balance": user["balance"],
        "total_earned": user["total_earned"]
    })


init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
