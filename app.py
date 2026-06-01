import streamlit as st
import pandas as pd
import sqlite3
import os
import qrcode
from PIL import Image
import io
import base64
import hashlib
from datetime import datetime
import json
import logging

# ===== إعدادات Logging =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== إعدادات الصفحة =====
st.set_page_config(
    page_title="TCS Smart QR Inventory",
    layout="wide",
    page_icon="📦",
    initial_sidebar_state="expanded"
)

# ===== إعدادات المجلدات =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "logo.jpg")
IMG_DIR = os.path.join(BASE_DIR, "images")
QR_DIR = os.path.join(BASE_DIR, "qrcodes")
DB_PATH = os.path.join(BASE_DIR, "tcs_data.db")

# إنشاء المجلدات
for folder in [IMG_DIR, QR_DIR]:
    os.makedirs(folder, exist_ok=True)

# ===== دالة الاتصال بقاعدة البيانات =====
@st.cache_resource
def get_db_connection():
    """الاتصال الآمن بقاعدة البيانات"""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=20.0)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    except Exception as e:
        logger.error(f"خطأ في الاتصال بقاعدة البيانات: {e}")
        st.error("❌ خطأ في الاتصال بقاعدة البيانات")
        st.stop()

conn = get_db_connection()

# ===== إنشاء جداول قاعدة البيانات =====
def init_db():
    """إنشاء جداول قاعدة البيانات"""
    try:
        c = conn.cursor()
        
        # جدول المستخدمين
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      username TEXT UNIQUE NOT NULL, 
                      password TEXT NOT NULL, 
                      role TEXT NOT NULL, 
                      permissions TEXT NOT NULL, 
                      created_at TEXT NOT NULL)''')
        
        # جدول القطع
        c.execute('''CREATE TABLE IF NOT EXISTS inventory
                     (code TEXT PRIMARY KEY, 
                      name TEXT NOT NULL, 
                      description TEXT, 
                      location TEXT, 
                      img_path TEXT, 
                      qr_path TEXT, 
                      created_by TEXT NOT NULL, 
                      created_at TEXT NOT NULL, 
                      updated_at TEXT NOT NULL)''')
        
        # جدول السجلات
        c.execute('''CREATE TABLE IF NOT EXISTS logs
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      user TEXT NOT NULL, 
                      action TEXT NOT NULL, 
                      part_code TEXT, 
                      timestamp TEXT NOT NULL)''')
        
        conn.commit()
        logger.info("✅ تم إنشاء جداول قاعدة البيانات بنجاح")
    except Exception as e:
        logger.error(f"خطأ في إنشاء الجداول: {e}")

init_db()

# ===== إنشاء حساب المدير الأساسي =====
def create_admin():
    """إنشاء حساب المدير الافتراضي"""
    try:
        c = conn.cursor()
        hashed_pwd = hashlib.sha256("9/9/2021".encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, role, permissions, created_at) VALUES (?, ?, ?, ?, ?)",
                  ("ALI SEIF", hashed_pwd, "admin", 
                   json.dumps({"add": True, "edit": True, "delete": True, "view": True, "manage_users": True}),
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        logger.info("✅ تم إنشاء حساب المدير بنجاح")
    except sqlite3.IntegrityError:
        logger.info("ℹ️ حساب المدير موجود بالفعل")
    except Exception as e:
        logger.error(f"خطأ في إنشاء حساب المدير: {e}")

create_admin()

# ===== دوال مساعدة =====
def hash_password(pwd):
    """تشفير كلمة المرور"""
    return hashlib.sha256(pwd.encode()).hexdigest()

def verify_password(pwd, hashed):
    """التحقق من كلمة المرور"""
    return hashlib.sha256(pwd.encode()).hexdigest() == hashed

def img_to_b64(path):
    """تحويل الصورة إلى Base64"""
    try:
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
    except Exception as e:
        logger.error(f"خطأ في تحويل الصورة: {e}")
    return None

def log_action(user, action, part_code=""):
    """تسجيل العملية في السجل"""
    try:
        c = conn.cursor()
        c.execute("INSERT INTO logs (user, action, part_code, timestamp) VALUES (?, ?, ?, ?)",
                  (user, action, part_code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except Exception as e:
        logger.error(f"خطأ في تسجيل العملية: {e}")

def get_user_permissions(username):
    """الحصول على صلاحيات المستخدم"""
    try:
        c = conn.cursor()
        c.execute("SELECT permissions FROM users WHERE username=?", (username,))
        result = c.fetchone()
        if result:
            return json.loads(result[0])
    except Exception as e:
        logger.error(f"خطأ في الحصول على الصلاحيات: {e}")
    return {}

def get_all_users():
    """الحصول على جميع المستخدمين"""
    try:
        c = conn.cursor()
        c.execute("SELECT id, username, role FROM users")
        return c.fetchall()
    except Exception as e:
        logger.error(f"خطأ في جلب المستخدمين: {e}")
        return []

def add_user(username, password, role, permissions):
    """إضافة مستخدم جديد"""
    try:
        c = conn.cursor()
        hashed = hash_password(password)
        c.execute("INSERT INTO users (username, password, role, permissions, created_at) VALUES (?, ?, ?, ?, ?)",
                  (username, hashed, role, json.dumps(permissions), 
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        logger.info(f"✅ تم إضافة المستخدم: {username}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"⚠️ المستخدم موجود بالفعل: {username}")
        return False
    except Exception as e:
        logger.error(f"خطأ في إضافة المستخدم: {e}")
        return False

def delete_user(user_id):
    """حذف مستخدم"""
    try:
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
        logger.info(f"✅ تم حذف المستخدم: {user_id}")
        return True
    except Exception as e:
        logger.error(f"خطأ في حذف المستخدم: {e}")
        return False

# ===== CSS احترافي =====
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');

* { font-family: 'Cairo', sans-serif !important; }

/* خلفية عامة */
.main .block-container { padding-top: 1rem; }
[data-testid="stAppViewContainer"] { background: linear-gradient(135deg, #f0f2f5 0%, #e8eef7 100%); }

/* الشريط الجانبي */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%) !important;
    border-right: 4px solid #00ad00;
}
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] .stRadio label { 
    font-size: 16px; padding: 10px 0; font-weight: 600;
    transition: all 0.3s ease;
}
[data-testid="stSidebar"] .stRadio label:hover {
    color: #00ad00 !important;
    padding-left: 10px;
}

/* هيدر الشركة */
.company-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #00ad00 100%);
    padding: 24px 32px;
    border-radius: 16px;
    display: flex;
    align-items: center;
    gap: 24px;
    margin-bottom: 32px;
    box-shadow: 0 8px 32px rgba(0,173,0,0.2);
    border: 2px solid #00ad00;
}
.company-header img {
    height: 80px;
    border-radius: 12px;
    background: white;
    padding: 6px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}
.company-header .title-block h1 {
    color: white !important;
    margin: 0;
    font-size: 28px;
    font-weight: 900;
    letter-spacing: 2px;
}
.company-header .title-block p {
    color: #00ff00;
    margin: 4px 0 0 0;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 1px;
}
.company-header .user-info {
    margin-left: auto;
    text-align: right;
    color: white;
}
.company-header .user-info .username {
    font-size: 14px;
    color: #00ad00;
    font-weight: 700;
}
.company-header .user-info .role {
    font-size: 12px;
    color: #cbd5e1;
}

/* بطاقة القطعة */
.part-card {
    background: white;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    border-top: 5px solid #00ad00;
    margin-bottom: 20px;
    transition: all 0.3s ease;
    overflow: hidden;
}
.part-card:hover {
    transform: translateY(-6px);
    box-shadow: 0 12px 40px rgba(0,173,0,0.25);
    border-top-color: #00ff00;
}
.part-code {
    background: linear-gradient(90deg, #0f172a, #1e293b);
    color: #00ad00 !important;
    padding: 6px 16px;
    border-radius: 24px;
    font-size: 13px;
    font-weight: 800;
    display: inline-block;
    margin-bottom: 12px;
    font-family: monospace !important;
    letter-spacing: 1.5px;
    border: 2px solid #00ad00;
}
.part-name {
    font-size: 18px;
    font-weight: 800;
    color: #1e293b;
    margin-bottom: 6px;
}
.part-desc {
    font-size: 14px;
    color: #475569;
    margin-bottom: 10px;
    line-height: 1.5;
    padding: 8px;
    background: #f8fafc;
    border-right: 3px solid #00ad00;
    border-radius: 4px;
}
.part-loc {
    font-size: 13px;
    color: #64748b;
    margin-bottom: 12px;
}
.part-loc span {
    background: linear-gradient(90deg, #e0f2e0, #f0fff0);
    padding: 4px 12px;
    border-radius: 16px;
    color: #1e7e1e;
    font-weight: 700;
    border: 1px solid #00ad00;
}

/* زر */
.stButton>button {
    background: linear-gradient(90deg, #00ad00, #009900) !important;
    color: white !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    border: none !important;
    padding: 10px 20px !important;
    width: 100%;
    font-size: 14px !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 12px rgba(0,173,0,0.3) !important;
}
.stButton>button:hover {
    background: linear-gradient(90deg, #00ff00, #00dd00) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 20px rgba(0,173,0,0.5) !important;
}
.stButton>button:active {
    transform: translateY(0) !important;
}

/* Form */
.stForm {
    background: white;
    border-radius: 16px;
    padding: 28px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    border: 2px solid #e2e8f0;
    border-top: 5px solid #00ad00;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background-color: #f8fafc;
    border-bottom: 3px solid #e2e8f0;
    border-radius: 12px;
}
.stTabs [aria-selected="true"] {
    border-bottom: 4px solid #00ad00 !important;
    color: #00ad00 !important;
    font-weight: 700 !important;
}

/* Metric cards */
.metric-box {
    background: white;
    border-radius: 14px;
    padding: 24px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    border-left: 5px solid #00ad00;
    text-align: center;
    transition: all 0.3s ease;
}
.metric-box:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0,173,0,0.2);
}
.m-num { font-size: 40px; font-weight: 900; color: #00ad00; }
.m-lbl { font-size: 15px; color: #64748b; font-weight: 600; margin-top: 8px; }

/* Login Form */
.login-container {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
}
.login-box {
    background: white;
    border-radius: 20px;
    padding: 48px 40px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    max-width: 420px;
    width: 90%;
    text-align: center;
    border: 3px solid #00ad00;
}
.login-box h1 {
    color: #1e293b;
    font-size: 28px;
    font-weight: 900;
    margin-bottom: 8px;
}
.login-box p {
    color: #64748b;
    font-size: 14px;
    margin-bottom: 32px;
}
.login-logo {
    height: 100px;
    margin-bottom: 24px;
    border-radius: 12px;
    object-fit: contain;
}

/* تنبيهات */
.stAlert {
    border-radius: 12px !important;
    border: 2px solid !important;
    font-weight: 600 !important;
}

/* جدول */
.dataframe {
    border-radius: 12px !important;
    overflow: hidden !important;
}

/* Input fields */
.stTextInput input, .stPasswordInput input, .stSelectbox select {
    border: 2px solid #e2e8f0 !important;
    border-radius: 8px !important;
}

.stTextInput input:focus, .stPasswordInput input:focus {
    border: 2px solid #00ad00 !important;
    box-shadow: 0 0 0 3px rgba(0,173,0,0.1) !important;
}
</style>
""", unsafe_allow_html=True)

# ===== التحكم في الجلسات =====
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None

# ===== صفحة تسجيل الدخول =====
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div class="login-box">
        """, unsafe_allow_html=True)
        
        # عرض اللوجو إذا موجودة
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=150, use_column_width=False)
        else:
            st.markdown("<p style='text-align:center;color:#999;'>🏢</p>", unsafe_allow_html=True)
        
        st.markdown("""
            <h1 style='text-align:center;color:#1e293b;font-size:28px;font-weight:900;margin-bottom:8px;'>
            🔐 TCS Inventory
            </h1>
            <p style='text-align:center;color:#64748b;font-size:14px;margin-bottom:32px;'>
            نظام إدارة المخزن الذكي
            </p>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        username = st.text_input("👤 اسم المستخدم", placeholder="أدخل اسم المستخدم", key="login_username")
        password = st.text_input("🔑 كلمة المرور", type="password", placeholder="أدخل كلمة المرور", key="login_password")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("🚀 دخول", use_container_width=True):
            if not username or not password:
                st.error("❌ يرجى ملء جميع الحقول!")
            else:
                try:
                    c = conn.cursor()
                    c.execute("SELECT role, permissions, password FROM users WHERE username=?", (username,))
                    user = c.fetchone()
                    
                    if user:
                        if verify_password(password, user[2]):
                            st.session_state.logged_in = True
                            st.session_state.username = username
                            st.session_state.role = user[0]
                            log_action(username, "تسجيل دخول")
                            st.success("✅ تم التسجيل بنجاح!")
                            st.rerun()
                        else:
                            st.error("❌ كلمة المرور غير صحيحة!")
                    else:
                        st.error("❌ اسم المستخدم غير موجود!")
                except Exception as e:
                    logger.error(f"خطأ في تسجيل الدخول: {e}")
                    st.error("❌ حدث خطأ أثناء تسجيل الدخول!")
        
        st.markdown("</div>", unsafe_allow_html=True)

# ===== التطبيق الرئيسي =====
else:
    # الهيدر مع معلومات المستخدم
    st.markdown("""
    <div class="company-header">
    """, unsafe_allow_html=True)
    
    col_logo, col_title, col_user = st.columns([1, 3, 1.2])
    
    with col_logo:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=80, use_column_width=False)
        else:
            st.markdown("<div style='text-align:center;font-size:60px;'>🏢</div>", unsafe_allow_html=True)
    
    with col_title:
        st.markdown("""
        <div style='padding:15px 0;'>
            <h1 style='color:white;margin:0;font-size:28px;font-weight:900;letter-spacing:2px;'>
            🏢 TANK CONTAINER SERVICES
            </h1>
            <p style='color:#00ff00;margin:4px 0 0 0;font-size:14px;font-weight:700;letter-spacing:1px;'>
            📦 نظام إدارة المخزن الذكي | Smart QR Inventory System
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col_user:
        st.markdown(f"""
        <div style='text-align:right;color:white;padding:15px 0;'>
            <div style='font-size:14px;color:#00ad00;font-weight:700;'>👤 {st.session_state.username}</div>
            <div style='font-size:12px;color:#cbd5e1;margin-top:4px;'>🎖️ {st.session_state.role}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # الشريط الجانبي
    st.sidebar.markdown("---")
    st.sidebar.title("☰ القائمة الرئيسية")
    
    perms = get_user_permissions(st.session_state.username)
    
    menu_options = ["🏠 لوحة التحكم"]
    if perms.get("add") or perms.get("edit"):
        menu_options.append("➕ إضافة/تعديل قطعة")
    if perms.get("view"):
        menu_options.append("📋 الجرد والبحث")
    if perms.get("manage_users") and st.session_state.role == "admin":
        menu_options.append("👥 إدارة الحسابات")
    if st.session_state.role == "admin":
        menu_options.append("📊 التقارير والسجلات")
    
    menu_options.append("🚪 تسجيل الخروج")
    
    menu = st.sidebar.radio("اختر القسم", menu_options, label_visibility="collapsed")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    <div style='text-align:center;color:#94a3b8;font-size:12px;'>
    <p>🔒 نظام آمن للمخازن</p>
    <p>© 2025 Tank Container Services</p>
    </div>
    """, unsafe_allow_html=True)
    
    # ===== لوحة التحكم =====
    if menu == "🏠 لوحة التحكم":
        st.subheader("📊 لوحة التحكم والإحصائيات")
        
        try:
            c = conn.cursor()
            df = pd.read_sql_query("SELECT * FROM inventory", conn)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"""
                <div class="metric-box">
                    <div class="m-num">{len(df)}</div>
                    <div class="m-lbl">إجمالي الأصناف</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                c.execute("SELECT COUNT(*) FROM users")
                users_count = c.fetchone()[0]
                st.markdown(f"""
                <div class="metric-box">
                    <div class="m-num">{users_count}</div>
                    <div class="m-lbl">عدد المستخدمين</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                c.execute("SELECT COUNT(*) FROM logs")
                logs_count = c.fetchone()[0]
                st.markdown(f"""
                <div class="metric-box">
                    <div class="m-num">{logs_count}</div>
                    <div class="m-lbl">عدد العمليات</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                c.execute("SELECT COUNT(DISTINCT location) FROM inventory WHERE location IS NOT NULL AND location != ''")
                locations = c.fetchone()[0]
                st.markdown(f"""
                <div class="metric-box">
                    <div class="m-num">{locations}</div>
                    <div class="m-lbl">مواقع التخزين</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            if not df.empty:
                st.info("✅ النظام يعمل بكفاءة!")
                
                st.subheader("🆕 آخر الأصناف المضافة")
                df_recent = df.tail(5)
                
                for idx, row in df_recent.iterrows():
                    with st.expander(f"📦 {row['code']} - {row['name']}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**الوصف:** {row['description']}")
                            st.write(f"**الموقع:** {row['location']}")
                            st.write(f"**أضافها:** {row['created_by']}")
                        with col2:
                            if os.path.exists(row['img_path']):
                                st.image(row['img_path'], width=150)
            else:
                st.warning("⚠️ لا توجد أصناف مسجلة بعد. ابدأ بإضافة أصناف جديدة!")
        except Exception as e:
            logger.error(f"خطأ في لوحة التحكم: {e}")
            st.error("❌ حدث خطأ في تحميل البيانات")
    
    # ===== إضافة/تعديل قطعة =====
    elif menu == "➕ إضافة/تعديل قطعة" and (perms.get("add") or perms.get("edit")):
        st.subheader("➕ إدارة القطع والأصناف")
        
        tab1, tab2 = st.tabs(["🆕 إضافة قطعة جديدة", "✏️ تعديل قطعة موجودة"])
        
        with tab1:
            with st.form("add_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    code = st.text_input("🔖 كود القطعة", placeholder="مثال: SP-VALVE-001")
                    name = st.text_input("🔩 اسم القطعة", placeholder="مثال: صمام نحاسي")
                
                with col2:
                    location = st.text_input("📍 موقع التخزين", placeholder="مثال: الرف 4، الصندوق B3")
                    file = st.file_uploader("📷 صورة القطعة", type=['jpg','png','jpeg'])
                
                description = st.text_area("📝 وصف مفصل للقطعة", height=100)
                
                submit = st.form_submit_button("💾 حفظ وتوليد QR", use_container_width=True)
                
                if submit:
                    if not code or not file or not name:
                        st.error("⚠️ يرجى ملء جميع الحقول المطلوبة (الكود، الاسم، الصورة)!")
                    else:
                        try:
                            # حفظ الصورة
                            img_path = os.path.join(IMG_DIR, f"{code}.jpg")
                            qr_path = os.path.join(QR_DIR, f"{code}.png")
                            
                            img = Image.open(file).convert("RGB")
                            img.save(img_path)
                            
                            # توليد QR Code
                            qr_data = f"CODE: {code}\nNAME: {name}\nDESC: {description[:50]}\nLOC: {location}"
                            qr_img = qrcode.make(qr_data)
                            qr_img.save(qr_path)
                            
                            # حفظ في قاعدة البيانات
                            c = conn.cursor()
                            c.execute("""INSERT OR REPLACE INTO inventory 
                                       (code, name, description, location, img_path, qr_path, created_by, created_at, updated_at)
                                       VALUES (?,?,?,?,?,?,?,?,?)""",
                                      (code, name, description, location, img_path, qr_path, 
                                       st.session_state.username, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                       datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                            conn.commit()
                            
                            log_action(st.session_state.username, "إضافة قطعة", code)
                            
                            st.success(f"✅ تم تسجيل القطعة **{code}** بنجاح!")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.image(img_path, caption="صورة القطعة", use_column_width=True)
                            with col2:
                                st.image(qr_path, caption="QR Code", use_column_width=True)
                        except Exception as e:
                            logger.error(f"خطأ في إضافة القطعة: {e}")
                            st.error("❌ حدث خطأ أثناء إضافة القطعة!")
        
        with tab2:
            try:
                df = pd.read_sql_query("SELECT code, name FROM inventory", conn)
                if not df.empty:
                    selected_code = st.selectbox("🔍 اختر القطعة للتعديل", df['code'].tolist())
                    
                    if selected_code:
                        c = conn.cursor()
                        c.execute("SELECT * FROM inventory WHERE code=?", (selected_code,))
                        item = c.fetchone()
                        
                        if item:
                            with st.form("edit_form"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    new_name = st.text_input("🔩 اسم القطعة", value=item[1])
                                    new_location = st.text_input("📍 موقع التخزين", value=item[3])
                                with col2:
                                    new_desc = st.text_area("📝 الوصف", value=item[2], height=100)
                                    new_file = st.file_uploader("📷 صورة جديدة (اختياري)", type=['jpg','png','jpeg'])
                                
                                if st.form_submit_button("✅ حفظ التعديلات", use_container_width=True):
                                    try:
                                        img_path = item[4]
                                        if new_file:
                                            img = Image.open(new_file).convert("RGB")
                                            img.save(img_path)
                                        
                                        c.execute("""UPDATE inventory SET name=?, description=?, location=?, updated_at=?
                                                   WHERE code=?""",
                                                  (new_name, new_desc, new_location, 
                                                   datetime.now().strftime("%Y-%m-%d %H:%M:%S"), selected_code))
                                        conn.commit()
                                        
                                        log_action(st.session_state.username, "تعديل قطعة", selected_code)
                                        st.success("✅ تم التحديث بنجاح!")
                                    except Exception as e:
                                        logger.error(f"خطأ في تعديل القطعة: {e}")
                                        st.error("❌ حدث خطأ أثناء التعديل!")
                else:
                    st.warning("لا توجد قطع للتعديل!")
            except Exception as e:
                logger.error(f"خطأ في تحميل القطع: {e}")
                st.error("❌ حدث خطأ في تحميل البيانات")
    
    # ===== الجرد والبحث =====
    elif menu == "📋 الجرد والبحث" and perms.get("view"):
        st.subheader("📋 جرد المخزن")
        
        try:
            df = pd.read_sql_query("SELECT * FROM inventory", conn)
            
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                search_query = st.text_input("🔍 بحث بالكود أو الاسم أو الموقع:")
            with col2:
                sort_by = st.selectbox("🔀 ترتيب حسب", ["الكود", "الاسم", "التاريخ"])
            with col3:
                if st.button("🔄 تحديث"):
                    st.rerun()
            
            if search_query:
                mask = (
                    df['code'].str.contains(search_query, case=False, na=False) |
                    df['name'].str.contains(search_query, case=False, na=False) |
                    df['location'].str.contains(search_query, case=False, na=False) |
                    df['description'].str.contains(search_query, case=False, na=False)
                )
                df = df[mask]
            
            if sort_by == "الاسم":
                df = df.sort_values('name')
            elif sort_by == "التاريخ":
                df = df.sort_values('created_at', ascending=False)
            else:
                df = df.sort_values('code')
            
            if df.empty:
                st.warning("❌ لا توجد نتائج مطابقة!")
            else:
                cols = st.columns(3)
                for idx, row in df.iterrows():
                    with cols[idx % 3]:
                        st.markdown("""
                        <div class="part-card">
                        """, unsafe_allow_html=True)
                        
                        st.markdown(f"""
                        <div class="part-code">{row['code']}</div>
                        <div class="part-name">{row['name']}</div>
                        <div class="part-desc">📝 {row['description'][:80] if row['description'] else 'بدون وصف'}...</div>
                        <div class="part-loc">📍 <span>{row['location'] if row['location'] else 'غير محدد'}</span></div>
                        """, unsafe_allow_html=True)
                        
                        if os.path.exists(row['img_path']):
                            st.image(row['img_path'], use_column_width=True)
                        
                        if os.path.exists(row['qr_path']):
                            st.image(row['qr_path'], width=120, caption="QR Code")
                        
                        if st.button(f"🖨️ طباعة", use_container_width=True, key=f"print_{row['code']}"):
                            st.info("💡 استخدم خيار الطباعة من المتصفح (Ctrl+P)")
                        
                        if perms.get("delete") and st.button(f"🗑️ حذف", use_container_width=True, key=f"del_{row['code']}"):
                            try:
                                c = conn.cursor()
                                c.execute("DELETE FROM inventory WHERE code=?", (row['code'],))
                                conn.commit()
                                log_action(st.session_state.username, "حذف قطعة", row['code'])
                                st.success(f"✅ تم حذف {row['code']}")
                                st.rerun()
                            except Exception as e:
                                logger.error(f"خطأ في حذف القطعة: {e}")
                                st.error("❌ حدث خطأ أثناء الحذف!")
                        
                        st.markdown("</div>", unsafe_allow_html=True)
        except Exception as e:
            logger.error(f"خطأ في الجرد والبحث: {e}")
            st.error("❌ حدث خطأ في تحميل البيانات")
    
    # ===== إدارة الحسابات =====
    elif menu == "👥 إدارة الحسابات" and st.session_state.role == "admin":
        st.subheader("👥 إدارة حسابات المستخدمين")
        
        tab1, tab2 = st.tabs(["➕ إضافة مستخدم جديد", "📋 قائمة المستخدمين"])
        
        with tab1:
            with st.form("add_user_form"):
                col1, col2 = st.columns(2)
                with col1:
                    new_username = st.text_input("👤 اسم المستخدم")
                    new_password = st.text_input("🔑 كلمة المرور", type="password")
                with col2:
                    new_role = st.selectbox("🎖️ الدور", ["viewer", "operator", "admin"])
                    confirm_pwd = st.text_input("🔐 تأكيد كلمة المرور", type="password")
                
                st.write("**الصلاحيات:**")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    perm_view = st.checkbox("👁️ عرض", value=True)
                with col2:
                    perm_add = st.checkbox("➕ إضافة")
                with col3:
                    perm_edit = st.checkbox("✏️ تعديل")
                with col4:
                    perm_delete = st.checkbox("🗑️ حذف")
                
                if st.form_submit_button("💾 إضافة المستخدم", use_container_width=True):
                    if not new_username or not new_password:
                        st.error("❌ يرجى ملء جميع الحقول!")
                    elif new_password != confirm_pwd:
                        st.error("❌ كلمات المرور غير متطابقة!")
                    else:
                        perms = {
                            "view": perm_view,
                            "add": perm_add,
                            "edit": perm_edit,
                            "delete": perm_delete,
                            "manage_users": new_role == "admin"
                        }
                        
                        if add_user(new_username, new_password, new_role, perms):
                            log_action(st.session_state.username, "إضافة مستخدم", new_username)
                            st.success(f"✅ تم إضافة المستخدم **{new_username}** بنجاح!")
                            st.rerun()
                        else:
                            st.error("❌ اسم المستخدم موجود بالفعل!")
        
        with tab2:
            try:
                users = get_all_users()
                if users:
                    df_users = pd.DataFrame(users, columns=["ID", "اسم المستخدم", "الدور"])
                    st.dataframe(df_users, use_container_width=True)
                    
                    st.write("**حذف مستخدم:**")
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        user_to_delete = st.selectbox("اختر المستخدم للحذف", 
                                                      [u[1] for u in users if u[1] != "ALI SEIF"])
                    with col2:
                        if st.button("🗑️ حذف", use_container_width=True):
                            user_id = next(u[0] for u in users if u[1] == user_to_delete)
                            if delete_user(user_id):
                                log_action(st.session_state.username, "حذف مستخدم", user_to_delete)
                                st.success("✅ تم الحذف!")
                                st.rerun()
                else:
                    st.warning("لا توجد مستخدمين!")
            except Exception as e:
                logger.error(f"خطأ في إدارة الحسابات: {e}")
                st.error("❌ حدث خطأ في تحميل البيانات")
    
    # ===== التقارير =====
    elif menu == "📊 التقارير والسجلات" and st.session_state.role == "admin":
        st.subheader("📊 التقارير والسجلات")
        
        tab1, tab2 = st.tabs(["📈 تقارير المخزن", "📋 سجل العمليات"])
        
        with tab1:
            try:
                df = pd.read_sql_query("SELECT * FROM inventory", conn)
                
                if not df.empty:
                    st.write(f"**إجمالي الأصناف:** {len(df)}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**أصناف حسب الموقع:**")
                        location_counts = df['location'].value_counts()
                        st.bar_chart(location_counts)
                    
                    with col2:
                        st.write("**آخر التحديثات:**")
                        df_sorted = df.sort_values('updated_at', ascending=False).head(10)
                        st.dataframe(df_sorted[['code', 'name', 'updated_at']], use_container_width=True)
                else:
                    st.info("ℹ️ لا توجد بيانات بعد!")
            except Exception as e:
                logger.error(f"خطأ في التقارير: {e}")
                st.error("❌ حدث خطأ في تحميل البيانات")
        
        with tab2:
            try:
                logs = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 100", conn)
                if not logs.empty:
                    st.dataframe(logs, use_container_width=True)
                else:
                    st.info("ℹ️ لا توجد سجلات بعد!")
            except Exception as e:
                logger.error(f"خطأ في السجلات: {e}")
                st.error("❌ حدث خطأ في تحميل البيانات")
    
    # ===== تسجيل الخروج =====
    elif menu == "🚪 تسجيل الخروج":
        try:
            log_action(st.session_state.username, "تسجيل خروج")
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.role = None
            st.success("✅ تم تسجيل الخروج بنجاح!")
            st.rerun()
        except Exception as e:
            logger.error(f"خطأ في تسجيل الخروج: {e}")
            st.error("❌ حدث خطأ أثناء تسجيل الخروج!")
