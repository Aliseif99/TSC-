import streamlit as st
import pandas as pd
import sqlite3
import os
import qrcode
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import hashlib
from datetime import datetime
import json

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

for folder in [IMG_DIR, QR_DIR]:
    os.makedirs(folder, exist_ok=True)

# ===== قاعدة البيانات =====
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    
    # جدول المستخدمين
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, 
                  role TEXT, permissions TEXT, created_at TEXT)''')
    
    # جدول القطع
    c.execute('''CREATE TABLE IF NOT EXISTS inventory
                 (code TEXT PRIMARY KEY, name TEXT, description TEXT, location TEXT, 
                  img_path TEXT, qr_path TEXT, created_by TEXT, created_at TEXT, updated_at TEXT)''')
    
    # جدول السجلات
    c.execute('''CREATE TABLE IF NOT EXISTS logs
                 (id INTEGER PRIMARY KEY, user TEXT, action TEXT, part_code TEXT, timestamp TEXT)''')
    
    conn.commit()
    return conn

conn = init_db()
c = conn.cursor()

# إنشاء حساب المدير الأساسي
def create_admin():
    hashed_pwd = hashlib.sha256("9/9/2021".encode()).hexdigest()
    try:
        c.execute("INSERT INTO users VALUES (NULL, ?, ?, ?, ?, ?)",
                  ("ALI SEIF", hashed_pwd, "admin", 
                   json.dumps({"add": True, "edit": True, "delete": True, "view": True, "manage_users": True}),
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except:
        pass

create_admin()

# ===== دوال مساعدة =====
def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def verify_password(pwd, hashed):
    return hashlib.sha256(pwd.encode()).hexdigest() == hashed

def img_to_b64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

def get_logo_b64():
    return img_to_b64(LOGO_PATH)

def log_action(user, action, part_code=""):
    c.execute("INSERT INTO logs VALUES (NULL, ?, ?, ?, ?)",
              (user, action, part_code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def get_user_permissions(username):
    c.execute("SELECT permissions FROM users WHERE username=?", (username,))
    result = c.fetchone()
    if result:
        return json.loads(result[0])
    return {}

def get_all_users():
    c.execute("SELECT id, username, role FROM users")
    return c.fetchall()

def add_user(username, password, role, permissions):
    hashed = hash_password(password)
    try:
        c.execute("INSERT INTO users VALUES (NULL, ?, ?, ?, ?, ?)",
                  (username, hashed, role, json.dumps(permissions), 
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    except:
        return False

def delete_user(user_id):
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()

# ===== CSS احترافي =====
logo_data = get_logo_b64()
logo_src = f"data:image/jpeg;base64,{logo_data}" if logo_data else ""

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');

* {{ font-family: 'Cairo', sans-serif !important; }}

/* خلفية عامة */
.main .block-container {{ padding-top: 1rem; }}
[data-testid="stAppViewContainer"] {{ background: linear-gradient(135deg, #f0f2f5 0%, #e8eef7 100%); }}

/* الشريط الجانبي */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%) !important;
    border-right: 4px solid #00ad00;
}}
[data-testid="stSidebar"] * {{ color: #e2e8f0 !important; }}
[data-testid="stSidebar"] .stRadio label {{ 
    font-size: 16px; padding: 10px 0; font-weight: 600;
    transition: all 0.3s ease;
}}
[data-testid="stSidebar"] .stRadio label:hover {{
    color: #00ad00 !important;
    padding-left: 10px;
}}

/* هيدر الشركة */
.company-header {{
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #00ad00 100%);
    padding: 24px 32px;
    border-radius: 16px;
    display: flex;
    align-items: center;
    gap: 24px;
    margin-bottom: 32px;
    box-shadow: 0 8px 32px rgba(0,173,0,0.2);
    border: 2px solid #00ad00;
}}
.company-header img {{
    height: 80px;
    border-radius: 12px;
    background: white;
    padding: 6px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}}
.company-header .title-block h1 {{
    color: white !important;
    margin: 0;
    font-size: 28px;
    font-weight: 900;
    letter-spacing: 2px;
    border: none;
    padding: 0;
}}
.company-header .title-block p {{
    color: #00ff00;
    margin: 4px 0 0 0;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 1px;
}}
.company-header .user-info {{
    margin-left: auto;
    text-align: right;
    color: white;
}}
.company-header .user-info .username {{
    font-size: 14px;
    color: #00ad00;
    font-weight: 700;
}}
.company-header .user-info .role {{
    font-size: 12px;
    color: #cbd5e1;
}}

/* بطاقة القطعة */
.part-card {{
    background: white;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    border-top: 5px solid #00ad00;
    margin-bottom: 20px;
    transition: all 0.3s ease;
    overflow: hidden;
}}
.part-card:hover {{
    transform: translateY(-6px);
    box-shadow: 0 12px 40px rgba(0,173,0,0.25);
    border-top-color: #00ff00;
}}
.part-code {{
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
}}
.part-name {{
    font-size: 18px;
    font-weight: 800;
    color: #1e293b;
    margin-bottom: 6px;
}}
.part-desc {{
    font-size: 14px;
    color: #475569;
    margin-bottom: 10px;
    line-height: 1.5;
    padding: 8px;
    background: #f8fafc;
    border-right: 3px solid #00ad00;
    border-radius: 4px;
}}
.part-loc {{
    font-size: 13px;
    color: #64748b;
    margin-bottom: 12px;
}}
.part-loc span {{
    background: linear-gradient(90deg, #e0f2e0, #f0fff0);
    padding: 4px 12px;
    border-radius: 16px;
    color: #1e7e1e;
    font-weight: 700;
    border: 1px solid #00ad00;
}}

/* زر */
.stButton>button {{
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
}}
.stButton>button:hover {{
    background: linear-gradient(90deg, #00ff00, #00dd00) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 20px rgba(0,173,0,0.5) !important;
}}
.stButton>button:active {{
    transform: translateY(0) !important;
}}

/* Form */
.stForm {{
    background: white;
    border-radius: 16px;
    padding: 28px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    border: 2px solid #e2e8f0;
    border-top: 5px solid #00ad00;
}}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{
    background-color: #f8fafc;
    border-bottom: 3px solid #e2e8f0;
    border-radius: 12px;
}}
.stTabs [aria-selected="true"] {{
    border-bottom: 4px solid #00ad00 !important;
    color: #00ad00 !important;
    font-weight: 700 !important;
}}

/* Metric cards */
.metric-box {{
    background: white;
    border-radius: 14px;
    padding: 24px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    border-left: 5px solid #00ad00;
    text-align: center;
    transition: all 0.3s ease;
}}
.metric-box:hover {{
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0,173,0,0.2);
}}
.m-num {{ font-size: 40px; font-weight: 900; color: #00ad00; }}
.m-lbl {{ font-size: 15px; color: #64748b; font-weight: 600; margin-top: 8px; }}

/* Login Form */
.login-container {{
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
}}
.login-box {{
    background: white;
    border-radius: 20px;
    padding: 48px 40px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    max-width: 420px;
    width: 90%;
    text-align: center;
    border: 3px solid #00ad00;
}}
.login-box h1 {{
    color: #1e293b;
    font-size: 28px;
    font-weight: 900;
    margin-bottom: 8px;
}}
.login-box p {{
    color: #64748b;
    font-size: 14px;
    margin-bottom: 32px;
}}
.login-logo {{
    height: 100px;
    margin-bottom: 24px;
    border-radius: 12px;
}}

/* تنبيهات */
.stAlert {{
    border-radius: 12px !important;
    border: 2px solid !important;
    font-weight: 600 !important;
}}

/* جدول */
.dataframe {{
    border-radius: 12px !important;
    overflow: hidden !important;
}}
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
        st.markdown(f"""
        <div class="login-box">
            {'<img src="' + logo_src + '" class="login-logo">' if logo_src else ''}
            <h1>🔐 TCS Inventory</h1>
            <p>نظام إدارة المخزن الذكي</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        username = st.text_input("👤 اسم المستخدم", placeholder="أدخل اسم المستخدم")
        password = st.text_input("🔑 كلمة المرور", type="password", placeholder="أدخل كلمة المرور")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col_login, col_space = st.columns([2, 1])
        with col_login:
            if st.button("🚀 دخول", use_container_width=True):
                c.execute("SELECT role, permissions FROM users WHERE username=?", (username,))
                user = c.fetchone()
                
                if user:
                    c.execute("SELECT password FROM users WHERE username=?", (username,))
                    pwd_hash = c.fetchone()[0]
                    
                    if verify_password(password, pwd_hash):
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.session_state.role = user[0]
                        log_action(username, "تسجيل دخول")
                        st.rerun()
                    else:
                        st.error("❌ كلمة المرور غير صحيحة!")
                else:
                    st.error("❌ اسم المستخدم غير موجود!")

# ===== التطبيق الرئيسي =====
else:
    # الهيدر مع معلومات المستخدم
    logo_data = get_logo_b64()
    logo_src = f"data:image/jpeg;base64,{logo_data}" if logo_data else ""
    
    st.markdown(f"""
    <div class="company-header">
        {'<img src="' + logo_src + '" alt="TCS Logo">' if logo_src else ''}
        <div class="title-block">
            <h1>🏢 TANK CONTAINER SERVICES</h1>
            <p>📦 نظام إدارة المخزن الذكي | Smart QR Inventory System</p>
        </div>
        <div class="user-info">
            <div class="username">👤 {st.session_state.username}</div>
            <div class="role">🎖️ {st.session_state.role}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
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
            st.info("✅ نظام شغال بسلاسة وجاهز للعمل!")
            
            # آخر المضافة
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
    
    # ===== إضافة/تعديل قطعة =====
    elif menu == "➕ إضافة/تعديل قطعة" and (perms.get("add") or perms.get("edit")):
        st.subheader("➕ إدارة القطع والأصناف")
        
        tab1, tab2 = st.tabs(["🆕 إضافة قطعة جديدة", "✏️ تعديل قطعة موجودة"])
        
        with tab1:
            with st.form("add_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    code = st.text_input("🔖 كود القطعة (مثال: SP-VALVE-001)")
                    name = st.text_input("🔩 اسم القطعة (مثال: صمام نحاسي)")
                
                with col2:
                    location = st.text_input("📍 موقع التخزين (مثال: الرف 4، الصندوق B3)")
                    file = st.file_uploader("📷 صورة القطعة", type=['jpg','png','jpeg'])
                
                description = st.text_area("📝 وصف مفصل للقطعة", height=100)
                
                submit = st.form_submit_button("💾 حفظ وتوليد QR", use_container_width=True)
                
                if submit:
                    if code and file and name:
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
                        c.execute("""INSERT OR REPLACE INTO inventory 
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
                    else:
                        st.error("⚠️ يرجى ملء جميع الحقول المطلوبة (الكود، الاسم، الصورة)!")
        
        with tab2:
            df = pd.read_sql_query("SELECT code, name FROM inventory", conn)
            if not df.empty:
                selected_code = st.selectbox("🔍 اختر القطعة للتعديل", df['code'].tolist())
                
                if selected_code:
                    c.execute("SELECT * FROM inventory WHERE code=?", (selected_code,))
                    item = c.fetchone()
                    
                    with st.form("edit_form"):
                        col1, col2 = st.columns(2)
                        with col1:
                            new_name = st.text_input("🔩 اسم القطعة", value=item[1])
                            new_location = st.text_input("📍 موقع التخزين", value=item[3])
                        with col2:
                            new_desc = st.text_area("📝 الوصف", value=item[2], height=100)
                            new_file = st.file_uploader("📷 صورة جديدة (اختياري)", type=['jpg','png','jpeg'])
                        
                        if st.form_submit_button("✅ حفظ التعديلات", use_container_width=True):
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
            else:
                st.warning("لا توجد قطع للتعديل!")
    
    # ===== الجرد والبحث =====
    elif menu == "📋 الجرد والبحث" and perms.get("view"):
        st.subheader("📋 جرد المخزن")
        
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
                    img_b64 = img_to_b64(row['img_path']) if os.path.exists(row['img_path']) else None
                    qr_b64 = img_to_b64(row['qr_path']) if os.path.exists(row['qr_path']) else None
                    img_src = f"data:image/jpeg;base64,{img_b64}" if img_b64 else ""
                    qr_src = f"data:image/png;base64,{qr_b64}" if qr_b64 else ""
                    
                    st.markdown(f"""
                    <div class="part-card">
                        <div class="part-code">{row['code']}</div>
                        <div class="part-name">{row['name']}</div>
                        <div class="part-desc">📝 {row['description'][:80]}...</div>
                        <div class="part-loc">📍 <span>{row['location']}</span></div>
                        {'<img src="' + img_src + '" style="width:100%;border-radius:8px;margin-bottom:8px;">' if img_src else ''}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if qr_src:
                        st.image(row['qr_path'], width=120, caption="QR Code")
                    
                    # زر الطباعة
                    if st.button(f"🖨️ طباعة {row['code']}", use_container_width=True, key=f"print_{row['code']}"):
                        print_html = f"""
<!DOCTYPE html>
<html dir="rtl">
<head>
<meta charset="UTF-8">
<title>طباعة - {row['code']}</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: white; }}
  .header {{ text-align: center; border-bottom: 3px solid #00ad00; padding-bottom: 15px; margin-bottom: 20px; }}
  .header h2 {{ color: #1e293b; margin: 0; font-size: 20px; }}
  .header p {{ color: #00ad00; margin: 5px 0 0 0; font-size: 12px; font-weight: bold; }}
  .body {{ display: flex; gap: 20px; align-items: flex-start; margin: 20px 0; }}
  .info {{ flex: 1; }}
  .info table {{ width: 100%; border-collapse: collapse; }}
  .info td {{ padding: 12px; border: 1px solid #e2e8f0; font-size: 14px; }}
  .info td:first-child {{ background: #f8fafc; font-weight: bold; color: #1e293b; width: 35%; }}
  .part-img {{ max-width: 200px; border-radius: 8px; margin: 10px 0; }}
  .qr-section {{ text-align: center; }}
  .qr-img {{ width: 150px; margin: 10px 0; }}
  .footer {{ text-align: center; font-size: 11px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 10px; margin-top: 20px; }}
</style>
</head>
<body>
<div class="header">
  <h2>TANK CONTAINER SERVICES</h2>
  <p>نظام إدارة المخزن الذكي | Smart QR Inventory System</p>
</div>
<div class="body">
  <div class="info">
    <table>
      <tr><td>🔖 كود القطعة</td><td><strong style="color:#00ad00;font-size:16px;">{row['code']}</strong></td></tr>
      <tr><td>🔩 اسم القطعة</td><td>{row['name']}</td></tr>
      <tr><td>📝 الوصف</td><td>{row['description']}</td></tr>
      <tr><td>📍 موقع التخزين</td><td><strong style="color:#00ad00;">{row['location']}</strong></td></tr>
      <tr><td>👤 أضافها</td><td>{row['created_by']}</td></tr>
    </table>
    {'<img src="' + img_src + '" class="part-img">' if img_src else ''}
  </div>
  <div class="qr-section">
    <p style="font-weight:bold;color:#1e293b;">امسح الكود للتحقق</p>
    {'<img src="' + qr_src + '" class="qr-img">' if qr_src else ''}
    <p style="font-size:12px;color:#64748b;">{row['code']}</p>
  </div>
</div>
<div class="footer">© 2025 Tank Container Services | نظام إدارة المخزن الذكي</div>
<script>window.onload=function(){{window.print();}}</script>
</body>
</html>
"""
                        print_b64 = base64.b64encode(print_html.encode()).decode()
                        st.markdown(f'<a href="data:text/html;base64,{print_b64}" download="TCS_{row["code"]}.html" target="_blank" style="display:block;text-align:center;background:#00ad00;color:white;padding:10px;border-radius:8px;text-decoration:none;font-weight:bold;">💾 تحميل PDF</a>', unsafe_allow_html=True)
                    
                    # زر الحذف
                    if perms.get("delete") and st.button(f"🗑️ حذف {row['code']}", use_container_width=True, key=f"del_{row['code']}"):
                        c.execute("DELETE FROM inventory WHERE code=?", (row['code'],))
                        conn.commit()
                        log_action(st.session_state.username, "حذف قطعة", row['code'])
                        st.success(f"✅ تم حذف {row['code']}")
                        st.rerun()
    
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
                        else:
                            st.error("❌ اسم المستخدم موجود بالفعل!")
        
        with tab2:
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
                        delete_user(user_id)
                        log_action(st.session_state.username, "حذف مستخدم", user_to_delete)
                        st.success("✅ تم الحذف!")
                        st.rerun()
            else:
                st.warning("لا توجد مستخدمين!")
    
    # ===== التقارير =====
    elif menu == "📊 التقارير والسجلات" and st.session_state.role == "admin":
        st.subheader("📊 التقارير والسجلات")
        
        tab1, tab2 = st.tabs(["📈 تقارير المخزن", "📋 سجل العمليات"])
        
        with tab1:
            df = pd.read_sql_query("SELECT * FROM inventory", conn)
            
            if not df.empty:
                st.write(f"**إجمالي الأصناف:** {len(df)}")
                
                # بيانات موجزة
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**أصناف حسب الموقع:**")
                    location_counts = df['location'].value_counts()
                    st.bar_chart(location_counts)
                
                with col2:
                    st.write("**آخر التحديثات:**")
                    df_sorted = df.sort_values('updated_at', ascending=False).head(10)
                    st.dataframe(df_sorted[['code', 'name', 'updated_at']], use_container_width=True)
        
        with tab2:
            logs = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp DESC", conn)
            if not logs.empty:
                st.dataframe(logs, use_container_width=True)
            else:
                st.info("لا توجد سجلات بعد!")
    
    # ===== تسجيل الخروج =====
    elif menu == "🚪 تسجيل الخروج":
        log_action(st.session_state.username, "تسجيل خروج")
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.role = None
        st.success("✅ تم تسجيل الخروج بنجاح!")
        st.rerun()
