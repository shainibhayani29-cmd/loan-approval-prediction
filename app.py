import streamlit as st
import joblib
import numpy as np
import sqlite3
import hashlib
import os
import binascii
import re
import matplotlib.pyplot as plt
import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()


# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Loan Approval Prediction",
    page_icon="🏦",
    layout="wide"
)

# ============================================================
# SESSION STATE
# ============================================================
defaults = {
    "page": "welcome",
    "username": None,
    "role": None,
    "last_prediction": None,
    "last_application_id": None,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ============================================================
# DATABASE
# ============================================================
DB_FILE = "users.db"


def get_connection():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            salt TEXT NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            username TEXT PRIMARY KEY,
            salt TEXT NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            applicant_name TEXT,
            account_number TEXT,
            pan_number TEXT,
            applicant_income REAL,
            coapplicant_income REAL,
            loan_amount REAL,
            cibil_score INTEGER,
            employment TEXT,
            ml_result TEXT,
            eligible_banks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migrate older users.db files safely.
    existing_columns = {
        row[1] for row in conn.execute(
            "PRAGMA table_info(applications)"
        ).fetchall()
    }

    migrations = {
        "username": "TEXT",
        "applicant_name": "TEXT",
        "account_number": "TEXT",
        "pan_number": "TEXT",
        "applicant_income": "REAL",
        "coapplicant_income": "REAL",
        "loan_amount": "REAL",
        "cibil_score": "INTEGER",
        "employment": "TEXT",
        "ml_result": "TEXT",
        "eligible_banks": "TEXT",
        "created_at": "TIMESTAMP"
    }

    for column, data_type in migrations.items():
        if column not in existing_columns:
            conn.execute(
                f"ALTER TABLE applications ADD COLUMN {column} {data_type}"
            )

    conn.commit()

    # Default admin account for academic/demo project.
    # Username: admin
    # Password: Admin@123
    existing_admin = conn.execute(
        "SELECT 1 FROM admins WHERE username = ?",
        ("admin",)
    ).fetchone()

    if not existing_admin:
        salt, password_hash = hash_password("Admin@123")
        conn.execute(
            "INSERT INTO admins (username, salt, password_hash) VALUES (?, ?, ?)",
            ("admin", salt, password_hash)
        )
        conn.commit()

    conn.close()


def hash_password(password, salt=None):
    if salt is None:
        salt = binascii.hexlify(os.urandom(16)).decode()

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        100_000
    )

    return salt, binascii.hexlify(password_hash).decode()


def valid_password(password):
    if len(password) < 8 or len(password) > 20:
        return False, "Password must be between 8 and 20 characters."

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least 1 number."

    if not any(c.isupper() for c in password):
        return False, "Password must contain at least 1 uppercase letter."

    return True, ""


def create_user(username, password):
    username = username.strip()

    if not username:
        return False

    conn = get_connection()

    existing = conn.execute(
        "SELECT 1 FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    if existing:
        conn.close()
        return False

    salt, password_hash = hash_password(password)

    conn.execute(
        "INSERT INTO users (username, salt, password_hash) VALUES (?, ?, ?)",
        (username, salt, password_hash)
    )

    conn.commit()
    conn.close()

    return True


def authenticate_user(username, password):
    conn = get_connection()

    row = conn.execute(
        "SELECT salt, password_hash FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    conn.close()

    if not row:
        return False

    salt, stored_hash = row
    _, computed_hash = hash_password(password, salt)

    return computed_hash == stored_hash


def authenticate_admin(username, password):
    conn = get_connection()

    row = conn.execute(
        "SELECT salt, password_hash FROM admins WHERE username = ?",
        (username,)
    ).fetchone()

    conn.close()

    if not row:
        return False

    salt, stored_hash = row
    _, computed_hash = hash_password(password, salt)

    return computed_hash == stored_hash


init_db()

# ============================================================
# CSS
# ============================================================
st.markdown("""
<style>
/* ==========================================================
   BACKGROUND ONLY — dark navy AI/network style
   ========================================================== */
html, body, #root {
    background: #020817 !important;
}

.stApp {
    position: relative !important;
    background-color: #020817 !important;
    background-image:
        radial-gradient(circle at 50% 48%, rgba(20,72,210,.58) 0%, rgba(7,31,104,.72) 34%, rgba(2,8,23,.98) 82%),
        linear-gradient(135deg, #020817 0%, #061a52 48%, #020817 100%) !important;
    background-attachment: fixed !important;
    background-size: cover !important;
    color: #eaf2ff;
    min-height: 100vh !important;
}

/* Fine constellation dots and thin connecting network lines */
.stApp::before {
    content: "" !important;
    position: fixed !important;
    inset: 0 !important;
    z-index: 0 !important;
    pointer-events: none !important;
    opacity: .78 !important;
    background-image:
        radial-gradient(circle at 6% 15%, rgba(255,255,255,.95) 0 1.4px, transparent 2.5px),
        radial-gradient(circle at 14% 31%, rgba(150,215,255,.9) 0 1.2px, transparent 2.4px),
        radial-gradient(circle at 25% 18%, rgba(255,255,255,.9) 0 1.3px, transparent 2.5px),
        radial-gradient(circle at 36% 27%, rgba(145,215,255,.85) 0 1.2px, transparent 2.4px),
        radial-gradient(circle at 48% 12%, rgba(255,255,255,.92) 0 1.3px, transparent 2.5px),
        radial-gradient(circle at 59% 25%, rgba(145,215,255,.9) 0 1.2px, transparent 2.4px),
        radial-gradient(circle at 70% 16%, rgba(255,255,255,.9) 0 1.3px, transparent 2.5px),
        radial-gradient(circle at 83% 30%, rgba(145,215,255,.85) 0 1.2px, transparent 2.4px),
        radial-gradient(circle at 94% 13%, rgba(255,255,255,.9) 0 1.3px, transparent 2.5px),
        radial-gradient(circle at 9% 66%, rgba(145,215,255,.85) 0 1.2px, transparent 2.4px),
        radial-gradient(circle at 22% 80%, rgba(255,255,255,.9) 0 1.3px, transparent 2.5px),
        radial-gradient(circle at 38% 70%, rgba(145,215,255,.85) 0 1.2px, transparent 2.4px),
        radial-gradient(circle at 54% 86%, rgba(255,255,255,.9) 0 1.3px, transparent 2.5px),
        radial-gradient(circle at 69% 72%, rgba(145,215,255,.85) 0 1.2px, transparent 2.4px),
        radial-gradient(circle at 84% 84%, rgba(255,255,255,.9) 0 1.3px, transparent 2.5px),
        radial-gradient(circle at 95% 67%, rgba(145,215,255,.85) 0 1.2px, transparent 2.4px),
        linear-gradient(145deg, transparent 0 16%, rgba(105,180,255,.25) 16.1% 16.25%, transparent 16.4% 100%),
        linear-gradient(24deg, transparent 0 29%, rgba(105,180,255,.20) 29.1% 29.25%, transparent 29.4% 100%),
        linear-gradient(157deg, transparent 0 43%, rgba(105,180,255,.18) 43.1% 43.25%, transparent 43.4% 100%),
        linear-gradient(35deg, transparent 0 61%, rgba(105,180,255,.20) 61.1% 61.25%, transparent 61.4% 100%),
        linear-gradient(149deg, transparent 0 76%, rgba(105,180,255,.22) 76.1% 76.25%, transparent 76.4% 100%);
    background-size: 100% 100% !important;
}

.stApp::after {
    content: "" !important;
    position: fixed !important;
    inset: 0 !important;
    z-index: 0 !important;
    pointer-events: none !important;
    background:
        radial-gradient(circle at 18% 44%, rgba(115,190,255,.15) 0 1px, transparent 2px),
        radial-gradient(circle at 78% 54%, rgba(115,190,255,.12) 0 1px, transparent 2px),
        radial-gradient(circle at 48% 62%, rgba(255,255,255,.10) 0 1px, transparent 2px);
    background-size: 170px 150px, 220px 180px, 260px 210px;
}

/* Keep all Streamlit content above the background */
.stApp > div {
    position: relative !important;
    z-index: 2 !important;
    background: transparent !important;
}

[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main,
[data-testid="stMain"],
section[data-testid="stMain"] {
    background: transparent !important;
}

/* Always allow the complete app to scroll vertically */
html, body, #root {
    height: auto !important;
    min-height: 100% !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
}

.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main,
[data-testid="stMain"],
section[data-testid="stMain"] {
    height: auto !important;
    min-height: 100vh !important;
    max-height: none !important;
    overflow: visible !important;
}

[data-testid="stAppViewContainer"] > .main > div,
[data-testid="stMainBlockContainer"],
[data-testid="stMainBlockContainer"] > div {
    height: auto !important;
    min-height: 100vh !important;
    max-height: none !important;
    overflow: visible !important;
}

/* Give the browser a real page height so mouse wheel/trackpad scrolling works. */
[data-testid="stVerticalBlock"] {
    overflow: visible !important;
}

[data-testid="stHeader"] {
    background: rgba(2,6,23,.28);
}

[data-testid="stToolbar"] {
    background: transparent;
}

/* Typography */
h1, h2, h3, h4 {
    color: #f5f9ff !important;
}

p, label, .stMarkdown, .stCaption {
    color: #dbeafe !important;
}

/* Cards stay clean so the blue network background remains visible around them */
.glass-card {
    background: rgba(5,18,55,.72);
    backdrop-filter: blur(12px);
    border-radius: 18px;
    border: 1px solid rgba(120,180,255,.28);
    box-shadow: 0 12px 35px rgba(0,0,0,.28), 0 0 25px rgba(0,95,255,.12);
    padding: 25px 30px;
    margin-bottom: 20px;
}

.section-title {
    color: #ffffff;
    font-size: 21px;
    font-weight: 700;
    margin-bottom: 15px;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(90deg, #0759d8, #00a9ff);
    color: white;
    border: 1px solid rgba(130,210,255,.28);
    border-radius: 10px;
    padding: 12px 0;
    font-size: 16px;
    font-weight: 600;
    box-shadow: 0 5px 18px rgba(0,100,255,.22);
}

.stButton > button:hover {
    background: linear-gradient(90deg, #0b66ef, #11b9ff);
    color: white;
}

/* Metrics */
.metric-card {
    background: rgba(5,18,55,.72);
    border: 1px solid rgba(120,180,255,.25);
    border-radius: 16px;
    padding: 18px;
    text-align: center;
}

/* Bank cards */
.bank-card {
    border-radius: 16px;
    padding: 18px;
    margin: 12px 0;
    border: 2px solid;
    backdrop-filter: blur(8px);
}

.criterion {
    display: inline-block;
    padding: 8px 12px;
    border-radius: 9px;
    margin: 4px;
    font-weight: 600;
    font-size: 14px;
}

.criterion-green {
    background: rgba(34,197,94,.18);
    border: 1px solid #22c55e;
    color: #bbf7d0;
}

.criterion-red {
    background: rgba(239,68,68,.18);
    border: 1px solid #ef4444;
    color: #fecaca;
}

.admin-header {
    padding: 22px;
    border-radius: 18px;
    background: linear-gradient(90deg, rgba(0,91,255,.34), rgba(0,198,255,.12));
    border: 1px solid rgba(0,198,255,.30);
    margin-bottom: 22px;
}

.small-note {
    color: #bfdbfe !important;
    font-size: 13px;
}

/* Inputs */
input, textarea {
    color: #0f172a !important;
}

[data-baseweb="select"] * {
    color: #0f172a !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #06133f 0%, #020617 100%);
    border-right: 1px solid rgba(100,160,255,.22);
}

[data-testid="stSidebar"] * {
    color: #eaf2ff !important;
}

/* Tabs */
button[data-baseweb="tab"] {
    color: #dbeafe !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #ffffff !important;
}

/* Alerts */
[data-testid="stAlert"] {
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# BANK CRITERIA
# Academic/demo criteria only
# ============================================================
BANKS = {
    "SBI": {
        "income": 20000,
        "cibil": 650,
        "loan": 500,
        "self_employed_allowed": True
    },
    "HDFC Bank": {
        "income": 15000,
        "cibil": 650,
        "loan": 400,
        "self_employed_allowed": True
    },
    "ICICI Bank": {
        "income": 25000,
        "cibil": 700,
        "loan": 700,
        "self_employed_allowed": False
    },
    "Axis Bank": {
        "income": 10000,
        "cibil": 600,
        "loan": 300,
        "self_employed_allowed": True
    }
}


def check_bank_criteria(applicant_income, cibil_score, loan_amount, self_employed):
    results = []

    for bank_name, criteria in BANKS.items():

        income_match = applicant_income >= criteria["income"]
        cibil_match = cibil_score >= criteria["cibil"]
        loan_match = loan_amount <= criteria["loan"]

        employment_match = (
            criteria["self_employed_allowed"]
            or self_employed == "No"
        )

        all_match = (
            income_match
            and cibil_match
            and loan_match
            and employment_match
        )

        results.append({
            "bank": bank_name,
            "income": income_match,
            "cibil": cibil_match,
            "loan": loan_match,
            "employment": employment_match,
            "all_match": all_match,
            "income_required": criteria["income"],
            "cibil_required": criteria["cibil"],
            "loan_limit": criteria["loan"]
        })

    return results


def save_application(
    username,
    applicant_name,
    account_number,
    pan_number,
    applicant_income,
    coapplicant_income,
    loan_amount,
    cibil_score,
    employment,
    ml_result,
    eligible_banks
):
    conn = get_connection()

    cursor = conn.execute("""
        INSERT INTO applications (
            username,
            applicant_name,
            account_number,
            pan_number,
            applicant_income,
            coapplicant_income,
            loan_amount,
            cibil_score,
            employment,
            ml_result,
            eligible_banks
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        username,
        applicant_name,
        account_number,
        pan_number,
        applicant_income,
        coapplicant_income,
        loan_amount,
        cibil_score,
        employment,
        ml_result,
        ", ".join(eligible_banks) if eligible_banks else "None"
    ))

    conn.commit()
    application_id = cursor.lastrowid
    conn.close()

    return application_id


def save_application_to_firebase(
    username,
    applicant_name,
    account_number,
    pan_number,
    applicant_income,
    coapplicant_income,
    loan_amount,
    cibil_score,
    employment,
    ml_result,
    eligible_banks
):
    try:
        doc_ref = db.collection("loan_applications").document()

        application_data = {
            "username": username,
            "applicant_name": applicant_name,
            "account_number": account_number,
            "pan_number": pan_number,
            "applicant_income": float(applicant_income),
            "coapplicant_income": float(coapplicant_income),
            "loan_amount": float(loan_amount),
            "cibil_score": int(cibil_score),
            "employment": employment,
            "ml_result": ml_result,
            "status": "Pending",
            "eligible_banks": eligible_banks,
            "created_at": firestore.SERVER_TIMESTAMP
        }

        doc_ref.set(application_data)
        return doc_ref.id
    except Exception:
        return None


# ============================================================
# EMI CALCULATOR
# ============================================================
def emi_calculator():

    st.markdown("## 🧮 EMI Calculator")
    st.caption("* An asterisk indicates a required field.")

    col1, col2 = st.columns(2)

    with col1:
        loan_amount = st.number_input(
            "Principal Loan Amount (₹) *",
            min_value=10000,
            max_value=10000000,
            value=500000,
            step=5000,
            key="emi_loan_amount"
        )

        interest_rate = st.number_input(
            "Interest Rate (% p.a) *",
            min_value=0.1,
            max_value=30.0,
            value=8.5,
            step=0.1,
            key="emi_interest"
        )

        tenure_years = st.number_input(
            "Loan Term (Years) *",
            min_value=1,
            max_value=30,
            value=5,
            step=1,
            key="emi_years"
        )

    with col2:
        st.markdown("### 📊 Loan Summary")

        months = int(tenure_years) * 12
        monthly_rate = interest_rate / (12 * 100)

        if monthly_rate == 0:
            preview_emi = loan_amount / months
        else:
            preview_emi = (
                loan_amount
                * monthly_rate
                * (1 + monthly_rate) ** months
            ) / (
                (1 + monthly_rate) ** months - 1
            )

        preview_total = preview_emi * months
        preview_interest = preview_total - loan_amount

        st.metric("Estimated Monthly EMI", f"₹ {preview_emi:,.0f}")
        st.metric("Estimated Total Interest", f"₹ {preview_interest:,.0f}")

    if st.button(
        "🔵 SHOW EMI",
        use_container_width=True,
        key="show_emi"
    ):
        principal = float(loan_amount)
        monthly_rate = float(interest_rate) / (12 * 100)
        months = int(tenure_years) * 12

        if monthly_rate == 0:
            emi = principal / months
        else:
            emi = (
                principal
                * monthly_rate
                * (1 + monthly_rate) ** months
            ) / (
                (1 + monthly_rate) ** months - 1
            )

        total_repayment = emi * months
        total_interest = total_repayment - principal

        st.success("EMI Calculated Successfully! ✅")

        r1, r2, r3 = st.columns(3)

        with r1:
            st.metric(
                "Monthly Payment (EMI)",
                f"₹ {emi:,.0f}"
            )

        with r2:
            st.metric(
                "Total Interest",
                f"₹ {total_interest:,.0f}"
            )

        with r3:
            st.metric(
                "Total Repayment",
                f"₹ {total_repayment:,.0f}"
            )

        st.markdown("### 💰 Total Repayment")
        st.info(
            f"Principal Amount: ₹ {principal:,.0f}\n\n"
            f"Total Interest: ₹ {total_interest:,.0f}\n\n"
            f"**Total Repayment: ₹ {total_repayment:,.0f}**"
        )

        fig, ax = plt.subplots(figsize=(5, 4))
        ax.pie(
            [principal, total_interest],
            labels=["Principal Amount", "Total Interest"],
            autopct="%1.1f%%",
            startangle=90
        )
        ax.set_title("Loan Repayment Breakdown")
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)


# ============================================================
# BANK ELIGIBILITY DISPLAY
# ============================================================
def show_bank_eligibility(
    applicant_income,
    cibil_score,
    loan_amount,
    self_employed
):
    st.markdown("## 🏦 Bank-wise Eligibility")

    st.info(
        "🟢 Green = Criteria Matched   |   🔴 Red = Criteria Not Matched"
    )

    st.caption(
        "Demo criteria created for this academic project. "
        "They are not official bank lending rules."
    )

    bank_results = check_bank_criteria(
        applicant_income,
        cibil_score,
        loan_amount,
        self_employed
    )

    for bank in bank_results:
        status = "🟢 ELIGIBLE" if bank["all_match"] else "🔴 NOT ELIGIBLE"

        if bank["all_match"]:
            st.success(f"🏦 {bank['bank']} — {status}")
        else:
            st.error(f"🏦 {bank['bank']} — {status}")

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            if bank["income"]:
                st.success(f"🟢 Income ≥ ₹{bank['income_required']:,}")
            else:
                st.error(f"🔴 Income ≥ ₹{bank['income_required']:,}")

        with c2:
            if bank["cibil"]:
                st.success(f"🟢 CIBIL ≥ {bank['cibil_required']}")
            else:
                st.error(f"🔴 CIBIL ≥ {bank['cibil_required']}")

        with c3:
            if bank["loan"]:
                st.success(f"🟢 Loan ≤ ₹{bank['loan_limit']}k")
            else:
                st.error(f"🔴 Loan ≤ ₹{bank['loan_limit']}k")

        with c4:
            if bank["employment"]:
                st.success("🟢 Employment")
            else:
                st.error("🔴 Employment")

    return bank_results


# ============================================================
# ADMIN DASHBOARD
# ============================================================
def show_user_history():
    st.markdown("## 📋 My Application History")
    st.caption(f"Logged in as: {st.session_state.username}")

    applications = []

    # Local database history (the same database used when saving predictions)
    try:
        conn = get_connection()
        rows = conn.execute(
            """SELECT id, applicant_name, loan_amount, cibil_score,
                      ml_result, eligible_banks, created_at
               FROM applications
               WHERE username = ?
               ORDER BY id DESC""",
            (st.session_state.username,)
        ).fetchall()
        conn.close()

        for row in rows:
            applications.append({
                "application_id": row[0],
                "applicant_name": row[1],
                "loan_amount": row[2] or 0,
                "cibil_score": row[3],
                "ml_result": row[4],
                "eligible_banks": row[5] or "",
                "status": row[4],
                "created_at": row[6],
                "source": "Local Database"
            })
    except Exception as e:
        st.error(f"Could not read local application history: {e}")

    # Firebase history
    try:
        docs = list(
            db.collection("loan_applications")
            .where("username", "==", st.session_state.username)
            .stream()
        )
        for doc in docs:
            data = doc.to_dict() or {}
            data["application_id"] = doc.id
            data["source"] = "Firebase"
            applications.append(data)
    except Exception as e:
        st.warning(f"Firebase history could not be loaded: {e}")

    if not applications:
        st.info("📭 No applications found yet.")
        st.write(
            "Go to **🏦 Loan Prediction**, complete the form, "
            "and click **🔮 Predict Loan Approval**."
        )
        return

    st.success(f"Found {len(applications)} application record(s).")

    for data in applications:
        application_id = data.get("application_id", "N/A")
        applicant = data.get("applicant_name", "N/A")
        loan_amount = data.get("loan_amount", 0) or 0
        cibil = data.get("cibil_score", "N/A")
        prediction = data.get("ml_result", "N/A")
        status = data.get("status", "Pending")
        banks = data.get("eligible_banks", [])
        created_at = data.get("created_at", "")
        source = data.get("source", "Database")

        if isinstance(banks, str):
            banks = [b.strip() for b in banks.split(",") if b.strip()]

        with st.container(border=True):
            st.markdown(f"### 📄 Application #{application_id}")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.write(f"**Applicant:** {applicant}")
                st.write(f"**Loan Amount:** ₹{float(loan_amount):,.0f}k")
            with c2:
                st.write(f"**CIBIL Score:** {cibil}")
                st.write(f"**Prediction:** {prediction}")
            with c3:
                st.write(f"**Status:** {status}")
                st.write(f"**Source:** {source}")

            st.write(
                "**Eligible Banks:** "
                + (", ".join(banks) if banks else "None")
            )
            if created_at:
                st.caption(f"Created: {created_at}")


def admin_dashboard():

    st.markdown("""
    <div class="admin-header">
        <h1>🛡️ Admin Dashboard</h1>
        <div>Loan Approval Prediction System — Administration Panel</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Admin Logout", key="admin_logout"):
        st.session_state.page = "welcome"
        st.session_state.username = None
        st.session_state.role = None
        st.rerun()

    conn = get_connection()

    total_users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    total_applications = conn.execute(
        "SELECT COUNT(*) FROM applications"
    ).fetchone()[0]

    approved = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE ml_result = 'Approved'"
    ).fetchone()[0]

    rejected = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE ml_result = 'Rejected'"
    ).fetchone()[0]

    conn.close()

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("👥 Total Users", total_users)

    with c2:
        st.metric("📋 Applications", total_applications)

    with c3:
        st.metric("✅ Approved", approved)

    with c4:
        st.metric("❌ Rejected", rejected)

    st.markdown("---")

    tab_users, tab_applications, tab_banks, tab_stats = st.tabs([
        "👥 User Management",
        "📋 Loan Applications",
        "🏦 Bank Criteria",
        "📊 Statistics"
    ])

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------
    with tab_users:

        st.subheader("👥 Registered Users")

        conn = get_connection()

        users = conn.execute("""
            SELECT username FROM users
            ORDER BY username
        """).fetchall()

        conn.close()

        if users:
            for user in users:
                col1, col2 = st.columns([4, 1])

                with col1:
                    st.write(f"👤 **{user[0]}**")

                with col2:
                    if st.button(
                        "Delete",
                        key=f"delete_user_{user[0]}"
                    ):
                        if user[0] == st.session_state.username:
                            st.warning("You cannot delete the currently logged-in admin.")
                        else:
                            conn = get_connection()
                            conn.execute(
                                "DELETE FROM users WHERE username = ?",
                                (user[0],)
                            )
                            conn.commit()
                            conn.close()
                            st.success(f"User {user[0]} deleted.")
                            st.rerun()
        else:
            st.info("No registered users yet.")

    # --------------------------------------------------------
    # APPLICATIONS
    # --------------------------------------------------------
    with tab_applications:

        st.subheader("📋 Loan Applications")

        conn = get_connection()

        applications = conn.execute("""
            SELECT
                id,
                username,
                applicant_name,
                applicant_income,
                loan_amount,
                cibil_score,
                ml_result,
                eligible_banks,
                created_at
            FROM applications
            ORDER BY id DESC
        """).fetchall()

        conn.close()

        if applications:

            for app in applications:

                (
                    app_id,
                    username,
                    applicant_name,
                    income,
                    loan_amount,
                    cibil,
                    result,
                    eligible_banks,
                    created_at
                ) = app

                with st.expander(
                    f"#{app_id} — {applicant_name} — {result}"
                ):

                    st.write(f"**User:** {username}")
                    st.write(f"**Applicant:** {applicant_name}")
                    st.write(f"**Income:** ₹{income:,.0f}")
                    st.write(f"**Loan Amount:** ₹{loan_amount:,.0f}k")
                    st.write(f"**CIBIL:** {cibil}")
                    st.write(f"**ML Result:** {result}")
                    st.write(
                        f"**Eligible Banks:** {eligible_banks}"
                    )
                    st.write(f"**Date:** {created_at}")

        else:
            st.info("No loan applications have been submitted yet.")

    # --------------------------------------------------------
    # BANK CRITERIA
    # --------------------------------------------------------
    with tab_banks:

        st.subheader("🏦 Current Bank Criteria")

        for bank_name, criteria in BANKS.items():

            st.markdown(f"### 🏦 {bank_name}")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.write(
                    f"**Income:** ₹{criteria['income']:,}+"
                )

            with col2:
                st.write(
                    f"**CIBIL:** {criteria['cibil']}+"
                )

            with col3:
                st.write(
                    f"**Loan:** ≤ ₹{criteria['loan']}k"
                )

            with col4:
                employment = (
                    "Self-employed allowed"
                    if criteria["self_employed_allowed"]
                    else "Salaried only"
                )
                st.write(f"**Employment:** {employment}")

            st.markdown("---")

        st.caption(
            "These are academic/demo criteria used by this project."
        )

    # --------------------------------------------------------
    # STATISTICS
    # --------------------------------------------------------
    with tab_stats:

        st.subheader("📊 Application Statistics")

        conn = get_connection()

        bank_rows = conn.execute(
            "SELECT eligible_banks FROM applications"
        ).fetchall()

        conn.close()

        bank_counts = {
            "SBI": 0,
            "HDFC Bank": 0,
            "ICICI Bank": 0,
            "Axis Bank": 0
        }

        for row in bank_rows:
            if row[0]:
                for bank_name in bank_counts:
                    if bank_name in row[0]:
                        bank_counts[bank_name] += 1

        for bank_name, count in bank_counts.items():
            st.metric(
                f"🏦 {bank_name} Eligible Applications",
                count
            )


# ============================================================
# WELCOME PAGE
# ============================================================
if st.session_state.page == "welcome":

    st.markdown(
        """
        <div style="text-align:center; padding:100px 20px 40px 20px;">
            <h1 style="font-size:48px;">🏦 Loan Approval Prediction</h1>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Keep the subtitle as normal Streamlit text so raw HTML can never appear.
    st.markdown(
        "<div style=\"text-align:center; color:#dbeafe; font-size:20px;\">AI-powered loan approval prediction and bank eligibility system</div>",
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        if st.button(
            "Continue →",
            use_container_width=True,
            key="continue"
        ):
            st.session_state.page = "login"
            st.rerun()


# ============================================================
# LOGIN / SIGNUP PAGE
# ============================================================
elif st.session_state.page == "login":

    st.markdown(
        """
        <div class="glass-card" style="max-width:650px;margin:auto;">
            <h2 style="text-align:center;">
                🔐 Loan Approval System Login
            </h2>
            <div style="text-align:center;color:#cbd5e1;">
                Login as a User or Administrator
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:

        tab_user, tab_admin, tab_signup = st.tabs([
            "👤 User Login",
            "🛡️ Admin Login",
            "🆕 Sign Up"
        ])

        # ----------------------------------------------------
        # USER LOGIN
        # ----------------------------------------------------
        with tab_user:

            login_user = st.text_input(
                "Username",
                key="login_user",
                autocomplete="off"
            )

            login_pass = st.text_input(
                "Password",
                type="password",
                key="login_pass",
                autocomplete="current-password"
            )

            if st.button(
                "🔑 User Login",
                use_container_width=True,
                key="user_login_button"
            ):

                if not login_user or not login_pass:
                    st.warning(
                        "Please enter both username and password."
                    )

                elif authenticate_user(login_user, login_pass):

                    st.session_state.page = "form"
                    st.session_state.username = login_user
                    st.session_state.role = "user"

                    st.rerun()

                else:
                    st.error(
                        "Incorrect username or password."
                    )

        # ----------------------------------------------------
        # ADMIN LOGIN
        # ----------------------------------------------------
        with tab_admin:

            st.info(
                "Admin access is separate from normal user accounts."
            )

            admin_user = st.text_input(
                "Admin Username",
                key="admin_user",
                autocomplete="off"
            )

            admin_pass = st.text_input(
                "Admin Password",
                type="password",
                key="admin_pass",
                autocomplete="current-password"
            )

            if st.button(
                "🛡️ Admin Login",
                use_container_width=True,
                key="admin_login_button"
            ):

                if not admin_user or not admin_pass:
                    st.warning(
                        "Please enter admin username and password."
                    )

                elif authenticate_admin(
                    admin_user,
                    admin_pass
                ):

                    st.session_state.page = "admin"
                    st.session_state.username = admin_user
                    st.session_state.role = "admin"

                    st.rerun()

                else:
                    st.error(
                        "Incorrect admin username or password."
                    )

            st.caption(
                "Demo admin: admin / Admin@123"
            )

        # ----------------------------------------------------
        # SIGN UP
        # ----------------------------------------------------
        with tab_signup:

            new_user = st.text_input(
                "Choose a Username",
                key="signup_user",
                autocomplete="off"
            )

            new_pass = st.text_input(
                "Choose a Password",
                type="password",
                key="signup_pass",
                autocomplete="new-password"
            )

            confirm_pass = st.text_input(
                "Confirm Password",
                type="password",
                key="signup_confirm",
                autocomplete="new-password"
            )

            st.caption(
                "Password must be 8–20 characters, with "
                "at least 1 number and 1 uppercase letter."
            )

            if st.button(
                "🆕 Create Account",
                use_container_width=True,
                key="signup_button"
            ):

                if not new_user or not new_pass or not confirm_pass:
                    st.warning(
                        "Please fill in all fields."
                    )

                elif new_pass != confirm_pass:
                    st.error(
                        "Passwords do not match."
                    )

                else:

                    valid, message = valid_password(new_pass)

                    if not valid:
                        st.error(message)

                    elif create_user(new_user, new_pass):
                        st.success(
                            "Account created! "
                            "You can now use User Login."
                        )

                    else:
                        st.error(
                            "That username is already taken."
                        )


# ============================================================
# ADMIN PAGE
# ============================================================
elif st.session_state.page == "admin":

    if st.session_state.role != "admin":
        st.session_state.page = "login"
        st.rerun()

    admin_dashboard()


# ============================================================
# USER DASHBOARD
# ============================================================
elif st.session_state.page == "form":

    if st.session_state.role != "user":
        st.session_state.page = "login"
        st.rerun()

    st.markdown(
        """
        <div class="glass-card">
            <h1>🏦 AI Loan Approval Prediction System</h1>
        </div>
        """,
        unsafe_allow_html=True
    )

    top1, top2 = st.columns([5, 1])

    with top1:
        st.write(
            f"Logged in as **{st.session_state.username}**"
        )

    with top2:
        if st.button("🚪 Logout", key="user_logout"):
            st.session_state.page = "welcome"
            st.session_state.username = None
            st.session_state.role = None
            st.rerun()

    option = st.radio(
        "Choose Service",
        [
            "🏦 Loan Prediction",
            "📋 My History",
            "🧮 EMI Calculator"
        ],
        horizontal=True,
        key="service_choice"
    )

    if option == "🧮 EMI Calculator":
        emi_calculator()
        st.stop()

    if option == "📋 My History":
        show_user_history()
        st.stop()

    # ========================================================
    # LOAN PREDICTION
    # ========================================================
    try:
        model = joblib.load("loan_model.pkl")
        label_encoders = joblib.load("label_encoders.pkl")
        feature_columns = joblib.load("feature_columns.pkl")
    except FileNotFoundError:
        st.error(
            "Model files are missing. Make sure "
            "loan_model.pkl, label_encoders.pkl and "
            "feature_columns.pkl are in the same folder as app.py."
        )
        st.stop()

    col_left, col_right = st.columns(2)

    # ----------------------------------------------------
    # APPLICANT
    # ----------------------------------------------------
    with col_left:

        st.markdown(
            '<div class="glass-card">',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="section-title">👤 Applicant Information</div>',
            unsafe_allow_html=True
        )

        applicant_name = st.text_input(
            "Applicant Name",
            placeholder="Enter full name",
            key="applicant_name"
        )

        account_number = st.text_input(
            "Account Number",
            placeholder="Numbers only",
            key="account_number"
        )

        if account_number and not account_number.isdigit():
            st.error(
                "Account Number must contain numbers only."
            )

        pan_number = st.text_input(
            "PAN Card Number",
            placeholder="ABCDE1234F",
            max_chars=10,
            key="pan_number"
        ).upper()

        if pan_number:
            pan_pattern = r"^[A-Z]{5}[0-9]{4}[A-Z]$"

            if not re.fullmatch(
                pan_pattern,
                pan_number
            ):
                st.warning(
                    "PAN format should be like ABCDE1234F."
                )

        gender = st.selectbox(
            "Gender",
            ["Male", "Female"],
            key="gender"
        )

        married = st.selectbox(
            "Married",
            ["Yes", "No"],
            key="married"
        )

        dependents = st.selectbox(
            "Number of Dependents",
            ["0", "1", "2", "3+"],
            key="dependents"
        )

        education = st.selectbox(
            "Education",
            ["Graduate", "Not Graduate"],
            key="education"
        )

        self_employed = st.selectbox(
            "Self Employed",
            ["Yes", "No"],
            key="self_employed"
        )

        applicant_income = st.slider(
            "Applicant Income",
            0,
            50000,
            5000,
            step=500,
            key="applicant_income"
        )

        coapplicant_income = st.slider(
            "Coapplicant Income",
            0,
            50000,
            0,
            step=500,
            key="coapplicant_income"
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True
        )

    # ----------------------------------------------------
    # LOAN INFO
    # ----------------------------------------------------
    with col_right:

        st.markdown(
            '<div class="glass-card">',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="section-title">🏠 Loan Information</div>',
            unsafe_allow_html=True
        )

        loan_amount = st.slider(
            "Loan Amount (in thousands)",
            0,
            700,
            100,
            step=10,
            key="loan_amount"
        )

        loan_term = st.slider(
            "Loan Duration (days)",
            0,
            480,
            360,
            step=12,
            key="loan_term"
        )

        cibil_score = st.slider(
            "CIBIL Score",
            300,
            900,
            650,
            step=10,
            key="cibil_score"
        )

        st.caption(
            "CIBIL score of 650 or above is treated "
            "as good credit history."
        )

        property_area = st.selectbox(
            "Property Area",
            ["Urban", "Semiurban", "Rural"],
            key="property_area"
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True
        )

    # ----------------------------------------------------
    # PREDICT
    # ----------------------------------------------------
    if st.button(
        "🔮 Predict Loan Approval",
        use_container_width=True,
        key="predict_button"
    ):

        pan_clean = pan_number.strip().upper()
        account_clean = account_number.strip()

        pan_pattern = r"^[A-Z]{5}[0-9]{4}[A-Z]$"

        if not applicant_name.strip():
            st.warning(
                "Please enter Applicant Name."
            )

        elif not account_clean:
            st.warning(
                "Please enter Account Number."
            )

        elif not account_clean.isdigit():
            st.error(
                "Account Number must contain numbers only."
            )

        elif not pan_clean:
            st.warning(
                "Please enter PAN Card Number."
            )

        elif not re.fullmatch(
            pan_pattern,
            pan_clean
        ):
            st.error(
                "Invalid PAN. Use format ABCDE1234F."
            )

        else:

            input_dict = {
                "Gender":
                    label_encoders["Gender"].transform(
                        [gender]
                    )[0],

                "Married":
                    label_encoders["Married"].transform(
                        [married]
                    )[0],

                "Dependents":
                    label_encoders["Dependents"].transform(
                        [dependents]
                    )[0],

                "Education":
                    label_encoders["Education"].transform(
                        [education]
                    )[0],

                "Self_Employed":
                    label_encoders["Self_Employed"].transform(
                        [self_employed]
                    )[0],

                "ApplicantIncome":
                    applicant_income,

                "CoapplicantIncome":
                    coapplicant_income,

                "LoanAmount":
                    loan_amount,

                "Loan_Amount_Term":
                    loan_term,

                "Credit_History":
                    1 if cibil_score >= 650 else 0,

                "Property_Area":
                    label_encoders["Property_Area"].transform(
                        [property_area]
                    )[0]
            }

            input_data = np.array([
                [
                    input_dict[column]
                    for column in feature_columns
                ]
            ])

            prediction = model.predict(input_data)[0]

            result = label_encoders[
                "Loan_Status"
            ].inverse_transform(
                [prediction]
            )[0]

            if result == "Y":
                ml_result = "Approved"
            else:
                ml_result = "Rejected"

            st.markdown(
                f"## Application Summary — {applicant_name}"
            )

            st.write(
                f"**Account Number:** {account_clean}"
            )

            st.write(
                f"**PAN Card Number:** {pan_clean}"
            )

            st.write(
                f"**CIBIL Score:** {cibil_score}"
            )

            if ml_result == "Approved":
                st.success(
                    f"✅ Loan Approved for {applicant_name}!"
                )
            else:
                st.error(
                    f"❌ Loan Not Approved for {applicant_name}"
                )

            # Bank eligibility
            bank_results = show_bank_eligibility(
                applicant_income,
                cibil_score,
                loan_amount,
                self_employed
            )

            eligible_banks = [
                bank["bank"]
                for bank in bank_results
                if bank["all_match"]
            ]

            if eligible_banks:
                st.success(
                    "🎯 Eligible Banks: "
                    + ", ".join(eligible_banks)
                )
            else:
                st.warning(
                    "No bank's demo criteria were fully matched."
                )

            # Save application for admin
            application_id = save_application(
                st.session_state.username,
                applicant_name,
                account_clean,
                pan_clean,
                applicant_income,
                coapplicant_income,
                loan_amount,
                cibil_score,
                self_employed,
                ml_result,
                eligible_banks
            )

            st.info(
                f"Application #{application_id} saved "
                f"for Admin Dashboard."
            )

            firebase_application_id = save_application_to_firebase(
                st.session_state.username,
                applicant_name,
                account_clean,
                pan_clean,
                applicant_income,
                coapplicant_income,
                loan_amount,
                cibil_score,
                self_employed,
                ml_result,
                eligible_banks
            )

            if firebase_application_id:
                st.success("🔥 Application also saved to Firebase!")
            else:
                st.warning("⚠️ Application saved locally, but Firebase save failed.")
