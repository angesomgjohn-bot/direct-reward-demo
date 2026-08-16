from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os, secrets
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
DB = os.environ.get('DB_PATH', 'nexa.db')

BANK_NAME = os.environ.get('BANK_NAME', 'Commercial Bank of Ethiopia (CBE)')
BANK_ACCOUNT_NAME = os.environ.get('BANK_ACCOUNT_NAME', '')
BANK_ACCOUNT_NUMBER = os.environ.get('BANK_ACCOUNT_NUMBER', '')
CUSTOMER_SERVICE_URL = os.environ.get('CUSTOMER_SERVICE_URL', 'https://t.me/NexaSupport11')
OFFICIAL_TELEGRAM_URL = os.environ.get('OFFICIAL_TELEGRAM_URL', 'https://t.me/NexaOfficial_1')
ADMIN_KEY = os.environ.get('ADMIN_KEY', '')

MIN_WITHDRAWAL = 200.0
WITHDRAWAL_FEE = 0.10
PLANS = [
    {'id':'A','name':'Plan A','price':500,'daily_reward':100},
    {'id':'B','name':'Plan B','price':1000,'daily_reward':200},
    {'id':'C','name':'Plan C','price':2000,'daily_reward':400},
    {'id':'D','name':'Plan D','price':5000,'daily_reward':1000},
    {'id':'E','name':'Plan E','price':10000,'daily_reward':2000},
    {'id':'F','name':'Plan F','price':20000,'daily_reward':4000},
]

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def add_col(c, table, col, definition):
    cols={r['name'] for r in c.execute(f'PRAGMA table_info({table})')}
    if col not in cols: c.execute(f'ALTER TABLE {table} ADD COLUMN {col} {definition}')

def init_db():
    c=db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL, referral_code TEXT UNIQUE NOT NULL,
      referred_by TEXT, balance REAL NOT NULL DEFAULT 0,
      total_earned REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS deposits(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
      amount REAL NOT NULL, reference TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
      created_at TEXT NOT NULL, reviewed_at TEXT);
    CREATE TABLE IF NOT EXISTS withdrawals(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
      amount REAL NOT NULL, fee REAL NOT NULL, net_amount REAL NOT NULL,
      account_number TEXT NOT NULL, account_name TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'PENDING', created_at TEXT NOT NULL, reviewed_at TEXT);
    CREATE TABLE IF NOT EXISTS tasks(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
      plan_id TEXT NOT NULL, task_name TEXT NOT NULL, reward REAL NOT NULL,
      completed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, completed_at TEXT);
    CREATE TABLE IF NOT EXISTS history(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
      action TEXT NOT NULL, amount REAL NOT NULL DEFAULT 0, note TEXT, created_at TEXT NOT NULL);
    ''')
    add_col(c,'users','active_plan_id','TEXT')
    add_col(c,'users','bank_account_name','TEXT')
    add_col(c,'users','bank_account_number','TEXT')
    add_col(c,'deposits','plan_id','TEXT')
    add_col(c,'deposits','plan_name','TEXT')
    c.commit(); c.close()

def current_user():
    uid=session.get('user_id')
    if not uid: return None
    c=db(); u=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone(); c.close(); return u

def plan(pid): return next((p for p in PLANS if p['id']==pid.upper()),None)

def hist(c,uid,action,amount=0,note=''):
    c.execute('INSERT INTO history(user_id,action,amount,note,created_at) VALUES(?,?,?,?,?)',
              (uid,action,amount,note,datetime.utcnow().isoformat()))

def auth_page(msg=None): return render_template('index.html', view='auth', message=msg, plans=PLANS)

def home():
    u=current_user()
    if not u: return redirect(url_for('login'))
    c=db()
    deposits=c.execute('SELECT * FROM deposits WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall()
    withdrawals=c.execute('SELECT * FROM withdrawals WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall()
    tasks=c.execute('SELECT * FROM tasks WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall()
    history=c.execute('SELECT * FROM history WHERE user_id=? ORDER BY id DESC LIMIT 30',(u['id'],)).fetchall()
    c.close()
    return render_template('index.html',view='home',user=u,plans=PLANS,deposits=deposits,
      withdrawals=withdrawals,tasks=tasks,history=history,min_withdrawal=MIN_WITHDRAWAL,
      withdrawal_fee=WITHDRAWAL_FEE,customer_service_url=CUSTOMER_SERVICE_URL)

@app.route('/')
def index(): return home()

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        phone=request.form.get('phone','').strip(); password=request.form.get('password',''); ref=request.form.get('referral','').strip() or None
        if not phone or not password: return auth_page('Phone number and password are required.')
        c=db()
        try:
            cur=c.execute('INSERT INTO users(phone,password_hash,referral_code,referred_by,created_at) VALUES(?,?,?,?,?)',
                (phone,generate_password_hash(password),secrets.token_hex(4).upper(),ref,datetime.utcnow().isoformat()))
            hist(c,cur.lastrowid,'ACCOUNT_CREATED'); c.commit(); session['user_id']=cur.lastrowid
        except sqlite3.IntegrityError:
            c.rollback(); c.close(); return auth_page('That phone number is already registered.')
        c.close(); return redirect(url_for('index'))
    return auth_page()

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        c=db(); u=c.execute('SELECT * FROM users WHERE phone=?',(request.form.get('phone','').strip(),)).fetchone(); c.close()
        if not u or not check_password_hash(u['password_hash'],request.form.get('password','')): return auth_page('Invalid phone number or password.')
        session['user_id']=u['id']; return redirect(url_for('index'))
    return auth_page()

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/pay/<pid>',methods=['GET','POST'])
def pay(pid):
    u=current_user(); p=plan(pid)
    if not u: return redirect(url_for('login'))
    if not p: return 'Plan not found',404
    if request.method=='POST':
        ref=request.form.get('reference','').strip()
        if not ref: flash('Enter the transaction/reference number.','error'); return redirect(url_for('pay',pid=p['id']))
        c=db()
        if c.execute('SELECT id FROM deposits WHERE reference=?',(ref,)).fetchone():
            c.close(); flash('That reference was already submitted.','error'); return redirect(url_for('pay',pid=p['id']))
        c.execute('INSERT INTO deposits(user_id,amount,reference,status,created_at,plan_id,plan_name) VALUES(?,?,?,?,?,?,?)',
                  (u['id'],p['price'],ref,'PENDING',datetime.utcnow().isoformat(),p['id'],p['name']))
        hist(c,u['id'],'PLAN_PAYMENT_SUBMITTED',p['price'],f"{p['name']} | Reference: {ref}")
        c.commit(); c.close(); flash('Payment submitted. It remains PENDING until admin verification.','success'); return redirect(url_for('index'))
    return render_template('index.html',view='payment',user=u,plan=p,bank_name=BANK_NAME,
      bank_account_name=BANK_ACCOUNT_NAME,bank_account_number=BANK_ACCOUNT_NUMBER,
      customer_service_url=CUSTOMER_SERVICE_URL)

@app.route('/bank',methods=['GET','POST'])
def bank():
    u=current_user()
    if not u: return redirect(url_for('login'))
    if request.method=='POST':
        name=request.form.get('account_name','').strip(); number=request.form.get('account_number','').strip()
        if not name or not number: flash('Enter account name and account number.','error'); return redirect(url_for('bank'))
        c=db(); c.execute('UPDATE users SET bank_account_name=?,bank_account_number=? WHERE id=?',(name,number,u['id']))
        hist(c,u['id'],'BANK_ACCOUNT_UPDATED',0,'Withdrawal account updated'); c.commit(); c.close()
        flash('Withdrawal bank account saved.','success'); return redirect(url_for('index'))
    return render_template('index.html',view='bank',user=u)

@app.route('/withdraw',methods=['POST'])
def withdraw():
    u=current_user()
    if not u: return redirect(url_for('login'))
    now=datetime.now()
    if not (9 <= now.hour < 17): flash('Withdrawal time is 9:00 AM - 5:00 PM.','error'); return redirect(url_for('index'))
    try: amount=float(request.form.get('amount','0'))
    except ValueError: amount=0
    if amount < MIN_WITHDRAWAL: flash('Minimum withdrawal amount is 200 ETB.','error'); return redirect(url_for('index'))
    if not u['bank_account_name'] or not u['bank_account_number']: flash('Bind your bank account first.','error'); return redirect(url_for('bank'))
    fee=round(amount*WITHDRAWAL_FEE,2); net=round(amount-fee,2)
    c=db(); changed=c.execute('UPDATE users SET balance=balance-? WHERE id=? AND balance>=?',(amount,u['id'],amount)).rowcount
    if changed!=1: c.rollback(); c.close(); flash('Insufficient available balance.','error'); return redirect(url_for('index'))
    c.execute('INSERT INTO withdrawals(user_id,amount,fee,net_amount,account_number,account_name,created_at) VALUES(?,?,?,?,?,?,?)',
              (u['id'],amount,fee,net,u['bank_account_number'],u['bank_account_name'],datetime.utcnow().isoformat()))
    hist(c,u['id'],'WITHDRAWAL_REQUESTED',amount,f'Fee: {fee:.2f} ETB | Net: {net:.2f} ETB')
    c.commit(); c.close(); flash(f'Withdrawal PENDING. Fee {fee:.2f} ETB; net {net:.2f} ETB. Target: within 24 hours.','success'); return redirect(url_for('index'))

@app.route('/task/<int:task_id>/complete',methods=['POST'])
def complete_task(task_id):
    u=current_user()
    if not u: return redirect(url_for('login'))
    c=db(); t=c.execute('SELECT * FROM tasks WHERE id=? AND user_id=? AND completed=0',(task_id,u['id'])).fetchone()
    if not t: c.close(); flash('Task not found or already completed.','error'); return redirect(url_for('index'))
    c.execute('UPDATE tasks SET completed=1,completed_at=? WHERE id=?',(datetime.utcnow().isoformat(),task_id))
    c.execute('UPDATE users SET balance=balance+?,total_earned=total_earned+? WHERE id=?',(t['reward'],t['reward'],u['id']))
    hist(c,u['id'],'TASK_COMPLETED',t['reward'],t['task_name']); c.commit(); c.close(); return redirect(url_for('index'))

@app.route('/referral')
def referral():
    u=current_user()
    if not u: return redirect(url_for('login'))
    link=request.host_url.rstrip('/')+'/register?referral='+u['referral_code']
    return render_template('index.html',view='referral',user=u,referral_link=link)

@app.route('/support')
def support(): return redirect(CUSTOMER_SERVICE_URL)
@app.route('/channel')
def channel(): return redirect(OFFICIAL_TELEGRAM_URL)

def admin_ok(): return bool(ADMIN_KEY) and request.args.get('key','')==ADMIN_KEY

@app.route('/admin')
def admin():
    if not admin_ok(): return 'Unauthorized',401
    c=db(); deposits=c.execute("SELECT d.*,u.phone FROM deposits d JOIN users u ON u.id=d.user_id WHERE d.status='PENDING' ORDER BY d.id DESC").fetchall()
    withdrawals=c.execute("SELECT w.*,u.phone FROM withdrawals w JOIN users u ON u.id=w.user_id WHERE w.status='PENDING' ORDER BY w.id DESC").fetchall(); c.close()
    return render_template('admin.html',deposits=deposits,withdrawals=withdrawals,admin_key=ADMIN_KEY)

@app.route('/admin/deposit/<int:item>/<action>')
def admin_deposit(item,action):
    if not admin_ok(): return 'Unauthorized',401
    if action not in ('approve','reject'): return 'Bad request',400
    c=db(); d=c.execute("SELECT * FROM deposits WHERE id=? AND status='PENDING'",(item,)).fetchone()
    if not d: c.close(); return 'Deposit not found or already reviewed',404
    status='APPROVED' if action=='approve' else 'REJECTED'
    if action=='approve':
        c.execute('UPDATE users SET balance=balance+?,active_plan_id=? WHERE id=?',(d['amount'],d['plan_id'],d['user_id']))
        p=plan(d['plan_id'] or '')
        if p and c.execute('SELECT COUNT(*) n FROM tasks WHERE user_id=? AND plan_id=?',(d['user_id'],p['id'])).fetchone()['n']==0:
            for i in range(1,4): c.execute('INSERT INTO tasks(user_id,plan_id,task_name,reward,created_at) VALUES(?,?,?,?,?)',(d['user_id'],p['id'],f'Task {i}',round(p['daily_reward']/3,2),datetime.utcnow().isoformat()))
        hist(c,d['user_id'],'DEPOSIT_APPROVED',d['amount'],f"{d['plan_name'] or 'Plan'} approved")
    else: hist(c,d['user_id'],'DEPOSIT_REJECTED',d['amount'],f"Reference: {d['reference']}")
    c.execute('UPDATE deposits SET status=?,reviewed_at=? WHERE id=?',(status,datetime.utcnow().isoformat(),item)); c.commit(); c.close(); return redirect(url_for('admin',key=ADMIN_KEY))

@app.route('/admin/withdrawal/<int:item>/<action>')
def admin_withdrawal(item,action):
    if not admin_ok(): return 'Unauthorized',401
    if action not in ('paid','reject'): return 'Bad request',400
    c=db(); w=c.execute("SELECT * FROM withdrawals WHERE id=? AND status='PENDING'",(item,)).fetchone()
    if not w: c.close(); return 'Withdrawal not found or already reviewed',404
    if action=='paid':
        # Demo only: this changes status; it does not send a bank transfer.
        hist(c,w['user_id'],'WITHDRAWAL_PAID',w['net_amount'],f"Demo payout marked paid | Fee: {w['fee']:.2f}")
        status='PAID'
    else:
        c.execute('UPDATE users SET balance=balance+? WHERE id=?',(w['amount'],w['user_id']))
        hist(c,w['user_id'],'WITHDRAWAL_REJECTED',w['amount'],'Reserved amount returned'); status='REJECTED'
    c.execute('UPDATE withdrawals SET status=?,reviewed_at=? WHERE id=?',(status,datetime.utcnow().isoformat(),item)); c.commit(); c.close(); return redirect(url_for('admin',key=ADMIN_KEY))

init_db()
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT','5000')))
