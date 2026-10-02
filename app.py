"""
CustomerCare - Final Edition
Run:  streamlit run app.py
"""
import os
import hashlib
import sqlite3
import re
from datetime import datetime
import streamlit as st

# ---------- CONFIG ----------
st.set_page_config(
    page_title="CustomerCare",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------- DATABASE ----------
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "customer_care.db")
os.makedirs(os.path.dirname(DB), exist_ok=True)


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON;")
    return c


@st.cache_resource
def init_db():
    """Create tables once (cached)."""
    c = conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Submitted',
            support_response TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    c.commit()
    c.close()
    return True


init_db()

# ---------- AUTH ----------
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^[0-9]{10}$")


def hash_pw(p):
    s = os.urandom(16).hex()
    return f"{s}${hashlib.sha256((s + p).encode()).hexdigest()}"


def verify_pw(p, stored):
    try:
        s, h = stored.split("$")
        return hashlib.sha256((s + p).encode()).hexdigest() == h
    except Exception:
        return False


def get_user(email):
    c = conn()
    try:
        r = c.execute("SELECT * FROM users WHERE email=?", (email.lower(),)).fetchone()
        return dict(r) if r else None
    finally:
        c.close()


def register(name, email, phone, pw, confirm):
    if not name.strip():   return False, "Full name is required."
    if not email.strip():  return False, "Email is required."
    if not phone.strip():  return False, "Phone number is required."
    if not pw:             return False, "Password is required."
    if not confirm:        return False, "Please confirm your password."
    if not EMAIL_RE.match(email.strip()):
        return False, "Please enter a valid email address."
    if not PHONE_RE.match(phone.strip()):
        return False, "Phone number must be exactly 10 digits."
    if len(pw) < 6:
        return False, "Password must be at least 6 characters."
    if pw != confirm:
        return False, "Passwords do not match."

    try:
        if get_user(email):
            return False, "An account with this email already exists."
        c = conn()
        c.execute(
            "INSERT INTO users (full_name,email,phone,password_hash,created_at) VALUES (?,?,?,?,?)",
            (name.strip(), email.lower().strip(), phone.strip(),
             hash_pw(pw), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        c.commit()
        c.close()
        return True, "Account created successfully. Please sign in."
    except sqlite3.Error as e:
        return False, f"Database error: {e}"


def login(email, pw):
    u = get_user(email)
    if not u:
        return False, "No account found with this email."
    if not verify_pw(pw, u["password_hash"]):
        return False, "Incorrect password."
    return True, u

# ---------- COMPLAINTS ----------
CATS  = ["Product Issue", "Service Issue", "Payment Issue", "Delivery Issue",
         "Technical Issue", "Account Issue", "Other"]
PRIOS = ["Low", "Medium", "High", "Urgent"]
STATS = ["Submitted", "In Progress", "Resolved", "Rejected"]


def new_cid():
    now_str = datetime.now().strftime("%Y%m%d")
    prefix = f"CCH-{now_str}-"
    c = conn()
    try:
        n = c.execute("SELECT COUNT(*) FROM complaints WHERE complaint_id LIKE ?",
                      (prefix + "%",)).fetchone()[0]
    finally:
        c.close()
    return f"{prefix}{n + 1:04d}"


def add_complaint(uid, cat, subj, desc, prio):
    try:
        cid = new_cid()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c = conn()
        c.execute("""INSERT INTO complaints
            (complaint_id, user_id, category, subject, description, priority,
             status, support_response, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'Submitted', NULL, ?, ?)""",
            (cid, uid, cat, subj, desc, prio, now, now))
        c.commit()
        c.close()
        return True, cid
    except sqlite3.Error as e:
        return False, f"Could not save: {e}"


def my_complaints(uid, filt="All"):
    c = conn()
    try:
        if filt and filt != "All":
            rows = c.execute(
                "SELECT * FROM complaints WHERE user_id=? AND status=? ORDER BY created_at DESC",
                (uid, filt)).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM complaints WHERE user_id=? ORDER BY created_at DESC",
                (uid,)).fetchall()
    finally:
        c.close()
    return [dict(r) for r in rows]


def get_one(cid, uid):
    c = conn()
    try:
        r = c.execute(
            "SELECT * FROM complaints WHERE complaint_id=? AND user_id=?",
            (cid, uid)).fetchone()
    finally:
        c.close()
    return dict(r) if r else None


def get_stats(uid):
    c = conn()
    try:
        total = c.execute("SELECT COUNT(*) FROM complaints WHERE user_id=?",
                          (uid,)).fetchone()[0]
        rows = c.execute(
            "SELECT status, COUNT(*) FROM complaints WHERE user_id=? GROUP BY status",
            (uid,)).fetchall()
    finally:
        c.close()
    s = {"total": total, "Submitted": 0, "In Progress": 0, "Resolved": 0, "Rejected": 0}
    for status_name, cnt in rows:
        if status_name in s:
            s[status_name] = cnt
    return s

# ---------- SESSION STATE ----------
DEFAULTS = {
    "logged_in": False,
    "user_id": None,
    "user_email": None,
    "user_name": None,
    "page": "Dashboard",
    "viewing": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------- CSS ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap');
:root{--cream:#FAF6F0;--cream2:#F5EFE6;--paper:#FFF;--ink:#1F1A17;--ink2:#4A413C;
--muted:#8A7F76;--line:#E8DFD3;--terra:#C8633C;--terraD:#A54F2D;--terraS:#FBE9DF;
--sage:#7C8B6F;--sageS:#EDF1E7;--gold:#D9A441;--goldS:#FBF2DC;--rose:#B14A56;--roseS:#FBE5E7;}
*{font-family:'Inter',sans-serif;}
header,footer,#MainMenu{visibility:hidden!important;}
[data-testid="stToolbar"],[data-testid="stSidebar"]{display:none!important;}
.stApp{background:var(--cream);}
.block-container{max-width:1240px;padding:1.5rem 2rem 3rem!important;}

.stButton>button{background:var(--terra)!important;color:#FFF!important;border:none!important;
  border-radius:10px!important;font-weight:600!important;font-size:14px!important;
  padding:10px 18px!important;min-height:42px!important;transition:all .15s!important;}
.stButton>button:hover{background:var(--terraD)!important;transform:translateY(-1px);}
.stButton>button[kind="secondary"]{background:var(--paper)!important;color:var(--ink)!important;
  border:1px solid var(--line)!important;}
.stDownloadButton>button{background:var(--paper)!important;color:var(--ink)!important;
  border:1px solid var(--line)!important;border-radius:10px!important;font-weight:600!important;
  width:100%!important;min-height:38px!important;}
.stDownloadButton>button:hover{border-color:var(--terra)!important;color:var(--terra)!important;}

.stTextInput input,.stTextArea textarea,.stSelectbox>div>div{background:var(--paper)!important;
  border:1px solid var(--line)!important;border-radius:10px!important;color:var(--ink)!important;
  font-size:14px!important;padding:12px 14px!important;}
.stTextInput input:focus,.stTextArea textarea:focus{border-color:var(--terra)!important;
  box-shadow:0 0 0 3px rgba(200,99,60,.12)!important;}
.stTextInput label,.stTextArea label,.stSelectbox label{color:var(--ink2)!important;
  font-size:13px!important;font-weight:600!important;}

.stTabs [data-baseweb="tab-list"]{gap:4px!important;background:var(--cream2)!important;
  padding:5px!important;border-radius:10px!important;border:1px solid var(--line)!important;}
.stTabs [data-baseweb="tab"]{height:40px!important;background:transparent!important;
  border-radius:7px!important;color:var(--muted)!important;font-weight:600!important;padding:0 18px!important;}
.stTabs [aria-selected="true"]{background:var(--paper)!important;color:var(--terra)!important;}
.stExpander{background:var(--paper)!important;border:1px solid var(--line)!important;border-radius:10px!important;}

.hero{background:linear-gradient(120deg,#FFF6EE 0%,#FAF6F0 100%);border:1px solid var(--line);
  border-radius:16px;padding:28px 32px;margin-bottom:22px;position:relative;overflow:hidden;}
.hero::before{content:"";position:absolute;right:-40px;top:-40px;width:180px;height:180px;
  background:radial-gradient(circle,rgba(200,99,60,.10) 0%,transparent 70%);border-radius:50%;}
.hero .eyebrow{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;
  color:var(--terra);margin-bottom:8px;}
.hero h1{font-family:'Instrument Serif',serif;font-weight:400;font-size:32px;line-height:1.2;
  margin:0 0 8px 0;color:var(--ink);letter-spacing:-.01em;}
.hero h1 em{font-style:italic;color:var(--terra);}
.hero p{font-size:14px;color:var(--ink2);margin:0;max-width:540px;}

.topbar{display:flex;justify-content:space-between;align-items:center;padding:14px 20px;
  background:var(--paper);border:1px solid var(--line);border-radius:14px;margin-bottom:18px;}
.tb-left{display:flex;align-items:center;gap:12px;}
.tb-logo{width:40px;height:40px;background:var(--terra);border-radius:11px;display:flex;
  align-items:center;justify-content:center;color:#FFF;font-size:20px;}
.tb-title{font-size:17px;font-weight:800;color:var(--ink);letter-spacing:-.02em;}
.tb-sub{font-size:12px;color:var(--muted);}
.uchip{display:flex;align-items:center;gap:10px;padding:6px 12px 6px 6px;background:var(--cream2);
  border:1px solid var(--line);border-radius:999px;}
.uav{width:32px;height:32px;background:var(--terra);border-radius:50%;display:flex;
  align-items:center;justify-content:center;color:#FFF;font-weight:700;font-size:13px;}
.uname{font-size:13px;font-weight:600;color:var(--ink);}
.uemail{font-size:11px;color:var(--muted);}

.tile{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:20px;
  transition:all .2s;}
.tile:hover{border-color:var(--terra);transform:translateY(-2px);box-shadow:0 6px 20px rgba(31,26,23,.06);}
.tile-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;}
.tile-label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted);}
.tile-badge{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;
  justify-content:center;font-size:16px;}
.bg-terra{background:var(--terraS);color:var(--terra);}
.bg-gold{background:var(--goldS);color:var(--gold);}
.bg-sage{background:var(--sageS);color:var(--sage);}
.bg-rose{background:var(--roseS);color:var(--rose);}
.tile-val{font-size:32px;font-weight:800;color:var(--ink);line-height:1;margin:0 0 4px;letter-spacing:-.03em;}
.tile-sub{font-size:12px;color:var(--muted);}

.panel{background:var(--paper);border:1px solid var(--line);border-radius:14px;
  padding:22px 24px;margin-bottom:18px;}
.panel-head{display:flex;justify-content:space-between;align-items:center;
  margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid var(--line);}
.panel-head h3{font-size:15px;font-weight:700;margin:0;}
.panel-head .hint{font-size:12px;color:var(--muted);}

.crow{display:grid;grid-template-columns:40px 1fr 130px 110px 90px 40px;
  align-items:center;gap:12px;padding:14px 12px;border-radius:10px;
  border-bottom:1px solid var(--line);transition:all .15s;}
.crow:hover{background:var(--cream2);}
.crow .cicon{width:36px;height:36px;background:var(--terraS);border-radius:10px;
  display:flex;align-items:center;justify-content:center;color:var(--terra);font-size:16px;}
.crow .ctitle{font-size:14px;font-weight:600;color:var(--ink);margin:0 0 3px;line-height:1.3;}
.crow .cid{font-family:Consolas,monospace;font-size:11px;color:var(--muted);}
.crow .ccat{font-size:12px;color:var(--ink2);font-weight:500;}
.crow .cdate{font-size:12px;color:var(--muted);}

.pill{display:inline-block;font-size:11px;font-weight:700;text-transform:uppercase;
  letter-spacing:.5px;padding:4px 11px;border-radius:999px;white-space:nowrap;}
.p-sub{background:var(--terraS);color:var(--terraD);}
.p-prog{background:var(--goldS);color:#8A6815;}
.p-res{background:var(--sageS);color:#4F5B41;}
.p-rej{background:var(--roseS);color:#8A3B44;}
.p-low{background:#EEE;color:#555;}
.p-med{background:var(--sageS);color:#4F5B41;}
.p-high{background:var(--goldS);color:#8A6815;}
.p-urg{background:var(--roseS);color:#8A3B44;}

.empty{text-align:center;padding:56px 24px;background:var(--paper);
  border:1px dashed var(--line);border-radius:14px;}
.empty .ei{font-size:44px;margin-bottom:10px;opacity:.5;}
.empty .et{font-family:'Instrument Serif',serif;font-size:22px;color:var(--ink);margin:0 0 6px;}
.empty .es{font-size:13px;color:var(--muted);margin:0;}

.stepper{display:flex;justify-content:space-between;position:relative;padding:0 6px;margin:24px 0 8px;}
.stepper::before{content:"";position:absolute;top:15px;left:6%;right:6%;height:2px;
  background:var(--line);z-index:0;}
.step{display:flex;flex-direction:column;align-items:center;gap:8px;position:relative;z-index:1;flex:1;}
.step .sd{width:32px;height:32px;border-radius:50%;background:var(--paper);
  border:2px solid var(--line);display:flex;align-items:center;justify-content:center;
  font-size:13px;font-weight:700;color:var(--muted);}
.step.done .sd{background:var(--terra);border-color:var(--terra);color:#FFF;}
.step.active .sd{background:var(--paper);border-color:var(--terra);color:var(--terra);
  box-shadow:0 0 0 4px var(--terraS);}
.step .sl{font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.8px;}
.step.done .sl,.step.active .sl{color:var(--ink);}

.dgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-bottom:20px;}
.ditem{background:var(--cream2);border:1px solid var(--line);border-radius:10px;padding:14px 16px;}
.ditem .dl{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;
  color:var(--muted);margin-bottom:6px;}
.ditem .dv{font-size:14px;font-weight:600;color:var(--ink);word-break:break-word;}
.dbody{background:var(--cream2);border:1px solid var(--line);border-radius:10px;
  padding:18px 20px;font-size:14px;color:var(--ink2);line-height:1.75;white-space:pre-wrap;}
.dresp{background:var(--sageS);border:1px solid #D5DEC6;border-radius:10px;padding:18px 20px;
  font-size:14px;color:#4F5B41;line-height:1.75;white-space:pre-wrap;}
.dresp.em{background:var(--cream2);border-color:var(--line);color:var(--muted);font-style:italic;}

.success{background:linear-gradient(120deg,#FFF1E6 0%,#FBE9DF 100%);border:1px solid #F0D4C0;
  border-radius:14px;padding:28px;margin:20px 0;text-align:center;}
.success .bi{font-size:42px;margin-bottom:10px;}
.success .st{font-family:'Instrument Serif',serif;font-size:24px;color:var(--ink);margin:0 0 6px;}
.success .ss{font-size:13px;color:var(--ink2);margin:0 0 16px;}
.success .tag{display:inline-block;background:var(--paper);border:1px solid var(--terra);
  color:var(--terra);padding:8px 18px;border-radius:10px;font-family:Consolas,monospace;
  font-size:15px;font-weight:700;letter-spacing:1px;}

.footer{text-align:center;padding:28px 0 10px;color:var(--muted);font-size:12px;
  border-top:1px solid var(--line);margin-top:36px;}
.footer .brand{font-family:'Instrument Serif',serif;font-size:15px;color:var(--ink);margin-bottom:4px;}

.auth-hero{background:linear-gradient(160deg,#C8633C 0%,#A54F2D 60%,#7C3A20 100%);
  border-radius:20px;padding:44px 40px;color:#FFF;min-height:560px;position:relative;overflow:hidden;}
.auth-hero::before{content:"";position:absolute;top:-60px;right:-60px;width:220px;height:220px;
  background:rgba(255,255,255,.08);border-radius:50%;}
.auth-hero::after{content:"";position:absolute;bottom:-80px;left:-40px;width:260px;height:260px;
  background:rgba(255,255,255,.06);border-radius:50%;}
.auth-hero .inner{position:relative;z-index:1;}
.abrand{display:flex;align-items:center;gap:12px;}
.abrand .ic{width:44px;height:44px;background:rgba(255,255,255,.18);border-radius:12px;
  display:flex;align-items:center;justify-content:center;font-size:22px;
  border:1px solid rgba(255,255,255,.25);}
.abrand .nm{font-size:19px;font-weight:800;}
.ahead{font-family:'Instrument Serif',serif;font-size:40px;line-height:1.15;color:#FFF;
  margin:52px 0 16px;font-weight:400;}
.ahead em{font-style:italic;color:#FFE6D5;}
.asub{font-size:15px;line-height:1.7;color:rgba(255,255,255,.88);max-width:380px;margin:0;}
.afeat{display:flex;flex-direction:column;gap:12px;margin-top:26px;}
.afeat>div{display:flex;align-items:center;gap:12px;font-size:14px;color:rgba(255,255,255,.9);}
.afeat .dot{width:24px;height:24px;background:rgba(255,255,255,.18);border-radius:50%;
  display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;}
.aquote{font-family:'Instrument Serif',serif;font-style:italic;font-size:16px;
  color:rgba(255,255,255,.78);border-left:2px solid rgba(255,255,255,.35);
  padding-left:14px;margin-top:30px;}
</style>
""", unsafe_allow_html=True)


# ---------- HELPERS ----------
def status_pill(s):
    m = {"Submitted": "p-sub", "In Progress": "p-prog",
         "Resolved": "p-res", "Rejected": "p-rej"}
    return f'<span class="pill {m.get(s, "p-sub")}">{s}</span>'


def prio_pill(p):
    m = {"Low": "p-low", "Medium": "p-med", "High": "p-high", "Urgent": "p-urg"}
    return f'<span class="pill {m.get(p, "p-med")}">{p}</span>'


def topbar():
    ini = st.session_state.user_name[0].upper() if st.session_state.user_name else "U"
    st.markdown(f"""
    <div class="topbar">
        <div class="tb-left">
            <div class="tb-logo">🛡️</div>
            <div><div class="tb-title">CustomerCare</div>
                 <div class="tb-sub">Complaint Management Console</div></div>
        </div>
        <div class="uchip">
            <div class="uav">{ini}</div>
            <div><div class="uname">{st.session_state.user_name}</div>
                 <div class="uemail">{st.session_state.user_email}</div></div>
        </div>
    </div>""", unsafe_allow_html=True)


def nav():
    items = [("📊", "Dashboard"), ("✍️", "New Complaint"), ("📋", "My Complaints"),
             ("📥", "Receipts"), ("⏱️", "Activity")]
    cols = st.columns(len(items) + 1)
    for i, (ic, lb) in enumerate(items):
        with cols[i]:
            active = st.session_state.page == lb
            if st.button(f"{ic}  {lb}", key=f"nav_{lb}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.page = lb
                st.session_state.viewing = None
                st.rerun()
    with cols[-1]:
        if st.button("🚪  Logout", key="logout_btn", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.user_email = None
            st.session_state.user_name = None
            st.session_state.viewing = None
            st.session_state.page = "Dashboard"
            st.rerun()


# ---------- AUTH SCREEN ----------
if not st.session_state.logged_in:
    st.markdown(
        "<style>.block-container{max-width:1100px!important;padding-top:3rem!important;}</style>",
        unsafe_allow_html=True)

    L, R = st.columns([1.1, 1], gap="large")

    # ----- LEFT: Brand panel -----
    with L:
        st.markdown("""
        <div class="auth-hero">
          <div class="inner">
            <div class="abrand"><div class="ic">🛡️</div><div class="nm">CustomerCare</div></div>
            <div class="ahead">Your voice <em>matters.</em><br>We're here to help.</div>
            <p class="asub">A modern complaint management platform that lets you raise issues,
               track progress, and hear back from our support team — all in one place.</p>
            <div class="afeat">
              <div><div class="dot">✓</div>Raise complaints in seconds</div>
              <div><div class="dot">✓</div>Track every status update</div>
              <div><div class="dot">✓</div>Read support responses directly</div>
            </div>
            <div class="aquote">"Every complaint is a chance for us to serve you better."</div>
          </div>
        </div>""", unsafe_allow_html=True)

    # ----- RIGHT: Sign in / Create account -----
    with R:
        tab = st.radio("", ["Sign in", "Create account"], horizontal=True,
                       label_visibility="collapsed", key="atab")

        if tab == "Sign in":
            st.markdown("""<h3 style="font-size:24px;font-weight:800;margin:12px 0 6px;color:#1F1A17;">Welcome back</h3>
                <p style="font-size:14px;color:#8A7F76;margin:0 0 22px;">Sign in to manage your complaints.</p>""",
                unsafe_allow_html=True)
            with st.form("lf"):
                em = st.text_input("Email address", placeholder="you@example.com")
                pw = st.text_input("Password", type="password", placeholder="••••••••")
                ok = st.form_submit_button("Sign in →", use_container_width=True)
            if ok:
                if em and pw:
                    s, r = login(em, pw)
                    if s:
                        st.session_state.logged_in = True
                        st.session_state.user_id = r["id"]
                        st.session_state.user_email = r["email"]
                        st.session_state.user_name = r["full_name"]
                        st.session_state.page = "Dashboard"
                        st.rerun()
                    else:
                        st.error(r)
                else:
                    st.warning("Please fill in both fields.")
        else:
            st.markdown("""<h3 style="font-size:24px;font-weight:800;margin:12px 0 6px;color:#1F1A17;">Create your account</h3>
                <p style="font-size:14px;color:#8A7F76;margin:0 0 22px;">A few details and you're set.</p>""",
                unsafe_allow_html=True)
            with st.form("rf"):
                nm = st.text_input("Full Name", placeholder="e.g. Priya Sharma")
                em = st.text_input("Email address", placeholder="you@example.com")
                ph = st.text_input("Phone Number", placeholder="10-digit mobile number")
                pw = st.text_input("Password", type="password", placeholder="Minimum 6 characters")
                cf = st.text_input("Confirm Password", type="password", placeholder="Re-enter password")
                ok = st.form_submit_button("Create account →", use_container_width=True)
            if ok:
                s, m = register(nm, em, ph, pw, cf)
                if s:
                    st.success(m)
                    st.info("Switch to the **Sign in** tab to continue.")
                else:
                    st.error(m)

    st.markdown(
        '<div class="footer"><div class="brand">CustomerCare</div>'
        '© 2025 · Built with Python & Streamlit</div>',
        unsafe_allow_html=True)

# ---------- MAIN APP ----------
else:
    topbar()
    nav()
    page = st.session_state.page

    # ----- DASHBOARD -----
    if page == "Dashboard":
        s = get_stats(st.session_state.user_id)
        st.markdown(f"""<div class="hero">
            <div class="eyebrow">Your Dashboard</div>
            <h1>Welcome back, <em>{st.session_state.user_name}.</em></h1>
            <p>Here's an overview of everything happening with your complaints.</p>
        </div>""", unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        tiles = [
            (c1, "Total",       s["total"],       "All complaints",  "bg-terra", "📁"),
            (c2, "Submitted",   s["Submitted"],   "Awaiting review", "bg-gold",  "📤"),
            (c3, "In Progress", s["In Progress"], "Being handled",   "bg-sage",  "⚡"),
            (c4, "Resolved",    s["Resolved"],    "Closed",          "bg-rose",  "✅"),
        ]
        for col, lab, val, sub, bg, ic in tiles:
            with col:
                st.markdown(f"""<div class="tile">
                    <div class="tile-head"><div class="tile-label">{lab}</div>
                    <div class="tile-badge {bg}">{ic}</div></div>
                    <div class="tile-val">{val}</div><div class="tile-sub">{sub}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
        col_main, col_side = st.columns([2, 1], gap="large")

        with col_main:
            st.markdown('<div class="panel"><div class="panel-head"><h3>Recent Complaints</h3>'
                        '<div class="hint">Latest 5</div></div>', unsafe_allow_html=True)
            recent = my_complaints(st.session_state.user_id)[:5]
            if recent:
                for c in recent:
                    st.markdown(f"""<div class="crow">
                        <div class="cicon">📄</div>
                        <div><div class="ctitle">{c['subject'][:70]}</div>
                             <div class="cid">{c['complaint_id']}</div></div>
                        <div class="ccat">{c['category']}</div>
                        <div>{status_pill(c['status'])}</div>
                        <div class="cdate">{c['created_at'][:10]}</div><div></div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.markdown('<div class="empty"><div class="ei">📭</div>'
                            '<div class="et">No complaints yet</div>'
                            '<div class="es">Click "New Complaint" to submit your first issue.</div></div>',
                            unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with col_side:
            st.markdown('<div class="panel"><div class="panel-head"><h3>Quick Actions</h3></div>',
                        unsafe_allow_html=True)
            if st.button("✍️  Submit a Complaint", key="qa1", use_container_width=True):
                st.session_state.page = "New Complaint"
                st.rerun()
            if st.button("📋  View All Complaints", key="qa2", use_container_width=True):
                st.session_state.page = "My Complaints"
                st.rerun()
            if st.button("📥  Download Receipts", key="qa3", use_container_width=True):
                st.session_state.page = "Receipts"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # ----- NEW COMPLAINT -----
    elif page == "New Complaint":
        st.markdown("""<div class="hero">
            <div class="eyebrow">File a Complaint</div>
            <h1>Tell us what went wrong. <em>We'll take it from here.</em></h1>
            <p>Provide as much detail as you can so our team can resolve your issue quickly.</p>
        </div>""", unsafe_allow_html=True)

        cF, cT = st.columns([2, 1], gap="large")
        with cF:
            st.markdown('<div class="panel"><div class="panel-head"><h3>Complaint Details</h3></div>',
                        unsafe_allow_html=True)
            with st.form("nf"):
                cat = st.selectbox("Complaint Category", CATS)
                subj = st.text_input("Subject", placeholder="Short title for your issue")
                desc = st.text_area("Description", height=160,
                                    placeholder="Describe your issue in detail (min 15 chars)")
                prio = st.selectbox("Priority", PRIOS, index=1)
                ok = st.form_submit_button("Submit Complaint →", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

            if ok:
                errs = []
                if not subj.strip():
                    errs.append("Subject is required.")
                elif len(subj.strip()) < 5:
                    errs.append("Subject must be at least 5 characters.")
                if not desc.strip():
                    errs.append("Description is required.")
                elif len(desc.strip()) < 15:
                    errs.append("Description must be at least 15 characters.")
                if errs:
                    for e in errs:
                        st.error(e)
                else:
                    s, r = add_complaint(st.session_state.user_id, cat,
                                         subj.strip(), desc.strip(), prio)
                    if s:
                        st.markdown(f"""<div class="success">
                            <div class="bi">🎉</div>
                            <div class="st">Complaint submitted successfully.</div>
                            <div class="ss">Save your Complaint ID below to track progress.</div>
                            <div class="tag">{r}</div>
                        </div>""", unsafe_allow_html=True)
                        cc1, cc2 = st.columns(2)
                        with cc1:
                            if st.button("📋  Go to My Complaints", use_container_width=True):
                                st.session_state.page = "My Complaints"
                                st.rerun()
                        with cc2:
                            if st.button("✍️  File Another", use_container_width=True):
                                st.rerun()
                    else:
                        st.error(f"❌ {r}")

        with cT:
            st.markdown("""<div class="panel">
                <div class="panel-head"><h3>Tips for Faster Resolution</h3></div>
                <div style="font-size:13px;color:#4A413C;line-height:1.9;">
                    <div><b style="color:#C8633C;">1.</b> Use a clear, specific subject.</div>
                    <div><b style="color:#C8633C;">2.</b> Include dates and order numbers.</div>
                    <div><b style="color:#C8633C;">3.</b> Set priority honestly.</div>
                    <div><b style="color:#C8633C;">4.</b> Check back for responses.</div>
                </div></div>""", unsafe_allow_html=True)

    # ----- MY COMPLAINTS -----
    elif page == "My Complaints":
        if st.session_state.viewing:
            c = get_one(st.session_state.viewing, st.session_state.user_id)
            if not c:
                st.error("Complaint not found.")
                if st.button("← Back", use_container_width=True):
                    st.session_state.viewing = None
                    st.rerun()
            else:
                colb, _ = st.columns([1, 4])
                with colb:
                    if st.button("← Back", key="bk", use_container_width=True):
                        st.session_state.viewing = None
                        st.rerun()

                st.markdown(f"""<div class="hero">
                    <div class="eyebrow">Complaint Details</div>
                    <h1>{c['subject']}</h1>
                    <p style="font-family:Consolas,monospace;font-size:12px;color:#8A7F76;">{c['complaint_id']}</p>
                </div>""", unsafe_allow_html=True)

                order = ["Submitted", "In Progress", "Resolved"]
                idx = order.index(c["status"]) if c["status"] in order else 0
                if c["status"] == "Rejected":
                    idx = 1

                def cls(i):
                    if c["status"] == "Rejected":
                        return "done" if i == 0 else ("active" if i == 1 else "")
                    return "done" if i < idx else ("active" if i == idx else "")

                steps = "".join([
                    f'<div class="step {cls(i)}">'
                    f'<div class="sd">{"✓" if cls(i) == "done" else i + 1}</div>'
                    f'<div class="sl">{lab}</div></div>'
                    for i, lab in enumerate(order)
                ])
                st.markdown(f'<div class="stepper">{steps}</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div style="text-align:center;margin:12px 0 22px;">'
                    f'{status_pill(c["status"])}</div>',
                    unsafe_allow_html=True)

                st.markdown(f"""<div class="dgrid">
                    <div class="ditem"><div class="dl">Complaint ID</div>
                        <div class="dv" style="font-family:Consolas,monospace;">{c['complaint_id']}</div></div>
                    <div class="ditem"><div class="dl">Category</div><div class="dv">{c['category']}</div></div>
                    <div class="ditem"><div class="dl">Priority</div><div class="dv">{prio_pill(c['priority'])}</div></div>
                    <div class="ditem"><div class="dl">Created</div><div class="dv">{c['created_at']}</div></div>
                    <div class="ditem"><div class="dl">Last Updated</div><div class="dv">{c['updated_at']}</div></div>
                    <div class="ditem"><div class="dl">Status</div><div class="dv">{status_pill(c['status'])}</div></div>
                </div>""", unsafe_allow_html=True)

                st.markdown('<h3>Description</h3>', unsafe_allow_html=True)
                st.markdown(f'<div class="dbody">{c["description"]}</div>',
                            unsafe_allow_html=True)
                st.markdown('<h3 style="margin-top:20px;">Support Response</h3>',
                            unsafe_allow_html=True)
                if c["support_response"]:
                    st.markdown(f'<div class="dresp">{c["support_response"]}</div>',
                                unsafe_allow_html=True)
                else:
                    st.markdown('<div class="dresp em">No response yet — our team will update you soon.</div>',
                                unsafe_allow_html=True)
        else:
            st.markdown("""<div class="hero">
                <div class="eyebrow">Complaint History</div>
                <h1>All your complaints, <em>one place.</em></h1>
                <p>Filter, review, and check the status of everything you've raised.</p>
            </div>""", unsafe_allow_html=True)

            cf1, _ = st.columns([1, 3])
            with cf1:
                filt = st.selectbox("Filter by Status", ["All"] + STATS, index=0)
            items = my_complaints(st.session_state.user_id, filt)

            st.markdown(f'<div class="panel"><div class="panel-head"><h3>Complaints ({len(items)})</h3>'
                        f'<div class="hint">Newest first</div></div>', unsafe_allow_html=True)

            if not items:
                st.markdown('<div class="empty"><div class="ei">🔍</div>'
                            '<div class="et">Nothing to show here</div>'
                            '<div class="es">Try a different filter, or submit a new complaint.</div></div>',
                            unsafe_allow_html=True)
            else:
                for c in items:
                    cR, cB = st.columns([10, 1])
                    with cR:
                        st.markdown(f"""<div class="crow">
                            <div class="cicon">📄</div>
                            <div><div class="ctitle">{c['subject'][:75]}</div>
                                 <div class="cid">{c['complaint_id']}</div></div>
                            <div class="ccat">{c['category']}</div>
                            <div>{status_pill(c['status'])}</div>
                            <div class="cdate">{c['created_at'][:10]}</div><div></div>
                        </div>""", unsafe_allow_html=True)
                    with cB:
                        if st.button("→", key=f"o_{c['complaint_id']}", help="View"):
                            st.session_state.viewing = c["complaint_id"]
                            st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # ----- RECEIPTS -----
    elif page == "Receipts":
        st.markdown("""<div class="hero">
            <div class="eyebrow">Downloads</div>
            <h1>Export your <em>complaint receipts.</em></h1>
            <p>Download a plain-text summary for each of your complaints.</p>
        </div>""", unsafe_allow_html=True)

        items = my_complaints(st.session_state.user_id)
        if not items:
            st.markdown('<div class="empty"><div class="ei">📥</div>'
                        '<div class="et">No receipts yet</div>'
                        '<div class="es">Submit a complaint first.</div></div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="panel"><div class="panel-head"><h3>Available Receipts</h3>'
                        '<div class="hint">.txt format</div></div>', unsafe_allow_html=True)
            for c in items:
                cI, cD = st.columns([5, 1])
                with cI:
                    st.markdown(f"""<div class="crow" style="grid-template-columns:40px 1fr 150px 100px;">
                        <div class="cicon">📄</div>
                        <div><div class="ctitle">{c['subject'][:80]}</div>
                             <div class="cid">{c['complaint_id']}</div></div>
                        <div>{status_pill(c['status'])}</div>
                        <div class="cdate">{c['created_at'][:10]}</div>
                    </div>""", unsafe_allow_html=True)
                with cD:
                    txt = (
                        f"CustomerCare - Complaint Receipt\n{'=' * 40}\n"
                        f"Complaint ID : {c['complaint_id']}\n"
                        f"User         : {st.session_state.user_name}\n"
                        f"Email        : {st.session_state.user_email}\n"
                        f"Category     : {c['category']}\n"
                        f"Subject      : {c['subject']}\n"
                        f"Priority     : {c['priority']}\n"
                        f"Status       : {c['status']}\n"
                        f"Created      : {c['created_at']}\n"
                        f"Updated      : {c['updated_at']}\n{'-' * 40}\n"
                        f"Description:\n{c['description']}\n\n"
                        f"Support Response:\n{c['support_response'] or 'No response yet.'}\n"
                    )
                    st.download_button("⬇ Download", txt,
                                       file_name=f"{c['complaint_id']}.txt",
                                       key=f"dl_{c['complaint_id']}",
                                       use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # ----- ACTIVITY -----
    elif page == "Activity":
        st.markdown("""<div class="hero">
            <div class="eyebrow">Activity Log</div>
            <h1>Your support <em>timeline.</em></h1>
            <p>A chronological view of everything you've raised with us.</p>
        </div>""", unsafe_allow_html=True)

        s = get_stats(st.session_state.user_id)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""<div class="tile"><div class="tile-head">
                <div class="tile-label">Account</div><div class="tile-badge bg-terra">👤</div></div>
                <div class="tile-val" style="font-size:18px;">{st.session_state.user_name}</div>
                <div class="tile-sub">{st.session_state.user_email}</div></div>""",
                unsafe_allow_html=True)
        with c2:
            st.markdown(f"""<div class="tile"><div class="tile-head">
                <div class="tile-label">Total Activity</div><div class="tile-badge bg-gold">⏱️</div></div>
                <div class="tile-val">{s['total']}</div>
                <div class="tile-sub">Complaints raised</div></div>""",
                unsafe_allow_html=True)
        with c3:
            st.markdown(f"""<div class="tile"><div class="tile-head">
                <div class="tile-label">Resolved</div><div class="tile-badge bg-sage">✅</div></div>
                <div class="tile-val">{s['Resolved']}</div>
                <div class="tile-sub">Completed</div></div>""",
                unsafe_allow_html=True)

        st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)
        st.markdown('<div class="panel"><div class="panel-head"><h3>Recent Activity</h3></div>',
                    unsafe_allow_html=True)
        recent = my_complaints(st.session_state.user_id)[:10]
        if recent:
            for c in recent:
                st.markdown(f"""<div class="crow" style="grid-template-columns:40px 1fr 200px 130px;">
                    <div class="cicon">🕒</div>
                    <div><div class="ctitle">{c['subject'][:80]}</div>
                         <div class="cid">{c['complaint_id']} · {c['category']}</div></div>
                    <div>{status_pill(c['status'])}</div>
                    <div class="cdate">{c['created_at']}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty"><div class="ei">📭</div>'
                        '<div class="et">No activity yet</div>'
                        '<div class="es">Submit complaints to see them here.</div></div>',
                        unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(f"""<div class="footer">
        <div class="brand">CustomerCare</div>
        © {datetime.now().year} · Built with Python, Streamlit &amp; SQLite
    </div>""", unsafe_allow_html=True)