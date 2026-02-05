import streamlit as st
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None
import json
import os
import uuid
import time
import math
import hashlib
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
from supabase import create_client, Client


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
USER_DATA_DIR = os.path.join(DATA_DIR, "users")

DEFAULT_DATA = {"events": [], "archives": [], "moods": {}, "pomodoro_records": [], "word_books": {}}

CATEGORIES = ["生活", "学习", "班团事务", "运动", "其他"]
CATEGORY_COLORS = {
    "生活": "#CFE8FF",
    "学习": "#DFF2D8",
    "班团事务": "#FFE6CC",
    "运动": "#D9F5D6",
    "其他": "#E8E0FF",
}

WEEKDAY_SHORT_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

MOODS = [
    "开心 😄", "平静 😌", "感恩 🙏", "充满希望 🌈",
    "自豪 😎", "期待 🤩", "专注 🔍", "高效 ⚡",
    "动力十足 🔥", "创造 💡", "学习 📚", "挑战 🧗",
    "被爱 🥰", "合作愉快 🤝", "收到启发 ✨", "治愈 🌿",
    "健康 🏃", "庆祝 🎉", "纪念 🎂", "家庭时光 👨‍👩‍👧",
    "压力大 😰", "无聊 😐",
    "混乱 😵", "犹豫 🤔", "拖延 🐌", "孤独 🏝️",
    "想念 🌙", "生气 😠", "失望 😔", "焦虑 😟",
]

BAD_MOOD_TEXTS = {"压力大", "混乱", "犹豫", "拖延", "孤独", "想念", "生气", "失望", "焦虑"}


def split_mood(entry: str):
    if " " not in entry:
        return entry, ""
    text, emoji = entry.rsplit(" ", 1)
    return text, emoji


MOOD_LABELS = {}
BAD_MOOD_EMOJIS = set()
for _entry in MOODS:
    _text, _emoji = split_mood(_entry)
    if _emoji:
        MOOD_LABELS[_emoji] = _text
        if _text in BAD_MOOD_TEXTS:
            BAD_MOOD_EMOJIS.add(_emoji)

MOOD_GOOD_BG = "#E7F7E8"
MOOD_BAD_BG = "#FBE7E7"


def ensure_data_file(file_path: str):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_DATA, f, ensure_ascii=False, indent=2)


def load_data(file_path: str):
    ensure_data_file(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("events", [])
    data.setdefault("archives", [])
    data.setdefault("moods", {})
    data.setdefault("pomodoro_records", [])
    data.setdefault("word_books", {})
    return data


def save_data(data, file_path: str):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_users():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_users(users: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return digest.hex()


def verify_password(password: str, salt: str, stored_hash: str) -> bool:
    return hash_password(password, salt) == stored_hash


def get_supabase_client() -> Client | None:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def get_storage_mode() -> str:
    return "supabase" if get_supabase_client() else "local"


def db_get_user(username: str):
    client = get_supabase_client()
    if not client:
        return None
    res = client.table("user_accounts").select("id, username, salt, hash").eq("username", username).limit(1).execute()
    return res.data[0] if res.data else None


def db_create_user(username: str, password: str):
    client = get_supabase_client()
    if not client:
        return None
    salt = uuid.uuid4().hex
    hashed = hash_password(password, salt)
    user_res = client.table("user_accounts").insert({"username": username, "salt": salt, "hash": hashed}).execute()
    user = user_res.data[0] if user_res.data else None
    if user:
        client.table("user_data").upsert({"user_id": user["id"], "data": DEFAULT_DATA}).execute()
    return user


def db_load_user_data(user_id: str):
    client = get_supabase_client()
    if not client:
        return DEFAULT_DATA.copy()
    res = client.table("user_data").select("data").eq("user_id", user_id).limit(1).execute()
    if res.data:
        data = res.data[0].get("data") or {}
    else:
        client.table("user_data").upsert({"user_id": user_id, "data": DEFAULT_DATA}).execute()
        data = DEFAULT_DATA.copy()
    data.setdefault("events", [])
    data.setdefault("archives", [])
    data.setdefault("moods", {})
    data.setdefault("pomodoro_records", [])
    data.setdefault("word_books", {})
    return data


def db_save_user_data(user_id: str, data: dict):
    client = get_supabase_client()
    if not client:
        return
    client.table("user_data").upsert({"user_id": user_id, "data": data}).execute()


def iso_week_start(d: date):
    return d - timedelta(days=d.weekday())


def month_start(d: date):
    return d.replace(day=1)


def next_month(d: date):
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def to_minutes(time_str: str) -> int:
    h, m = map(int, time_str.split(":"))
    return h * 60 + m


def layout_day_events(events):
    if not events:
        return []
    items = []
    for ev in sorted(events, key=lambda x: x["start"]):
        start = to_minutes(ev["start"])
        end = to_minutes(ev["end"])
        if end <= start:
            end += 24 * 60
        items.append({"event": ev, "start": start, "end": end})

    layouts = []
    cluster = []
    active = []

    def flush_cluster():
        if not cluster:
            return
        max_cols = max(item["col"] for item in cluster) + 1
        for item in cluster:
            item["cols"] = max_cols
            layouts.append(item)

    for item in items:
        active = [a for a in active if a["end"] > item["start"]]
        if not active:
            flush_cluster()
            cluster = []
        used = {a["col"] for a in active}
        col = 0
        while col in used:
            col += 1
        entry = {"event": item["event"], "start": item["start"], "end": item["end"], "col": col, "cols": 1}
        active.append(entry)
        cluster.append(entry)

    flush_cluster()
    return layouts


def format_seconds(total: int) -> str:
    total = max(0, int(total))
    m = total // 60
    s = total % 60
    return f"{m:02d}:{s:02d}"

def safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

def maybe_autorefresh(interval_ms: int, key: str) -> bool:
    if st_autorefresh is not None:
        st_autorefresh(interval=interval_ms, key=key)
        return True
    return False

TIME_START = 6
TIME_END = 22
HOUR_HEIGHT = 40
DAY_HEIGHT = (TIME_END - TIME_START) * HOUR_HEIGHT


st.set_page_config(page_title="My Diary", layout="wide")

st.markdown(
    """
<style>
body { background-color: #EEF5FF; }
.block-container { padding-top: 1.5rem; }
.card { background: #FFFFFF; border-radius: 12px; padding: 12px 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.05); }
.tag { display: inline-block; padding: 4px 8px; border-radius: 10px; margin: 4px 0; font-size: 12px; }
.title { font-size: 28px; font-weight: 700; color: #1F3B57; }
.subtitle { font-size: 16px; color: #51729B; }
.section-title { font-size: 20px; font-weight: 700; color: #1F3B57; margin: 6px 0 12px; }
.timer-text { font-size: 42px; font-weight: 700; text-align: center; color: #1F3B57; }
.focus-text { font-size: 20px; font-weight: 700; color: #1F3B57; text-align: right; }
.week-day-card { padding: 8px 10px; border-radius: 10px; border: 1px solid #C9DBF2; background: #F7FAFF; margin-bottom: 6px; }
.week-day-card.flash-on { background: #C9D6F2; border-color: #9CB4E0; }
.week-day-btn, .week-day-btn * { font-family: "Segoe Script", "Bradley Hand", "Comic Sans MS", cursive !important; }
.week-day-btn .stButton > button,
.week-day-btn .stButton button,
.week-day-btn button { width: 100%; border: 1px solid #C9DBF2; border-radius: 10px; padding: 6px 8px; background: #F7FAFF; color: #1F3B57; font-weight: 700; white-space: pre; line-height: 1.1; min-height: 64px; height: 64px; display: flex; flex-direction: column; justify-content: center; text-align: center; font-size: 13px; overflow: hidden; }
.week-day-btn .stButton > button span,
.week-day-btn .stButton button span,
.week-day-btn button span,
.week-day-btn .stButton > button * { white-space: pre; word-break: keep-all; }
.week-day-btn .stButton > button:hover { border-color: #9CB4E0; background: #EEF5FF; }
.week-day-btn.flash-on .stButton > button { background: #9CB4E0; border-color: #6F8FC7; color: #1F3B57; }
.detail-event-btn .stButton > button { width: 100%; text-align: left; border: 1px solid #E2EAF5; border-radius: 10px; background: #FFFFFF; padding: 8px 10px; }
.detail-event-btn .stButton > button:hover { border-color: #9CB4E0; background: #EEF5FF; }
.detail-panel { background: #FFFFFF; border-radius: 14px; border: 1px solid #E2EAF5; padding: 14px 16px; margin: 8px 0 16px; }
.detail-panel h4 { margin: 4px 0 10px; }
.footer-fixed { position: fixed; right: 16px; bottom: 16px; z-index: 999; }
.footer-fixed a { display: inline-block; width: 88px; text-align: center; border: 1px solid #C9DBF2; border-radius: 10px; padding: 6px 10px; background: #F7FAFF; color: #1F3B57; font-weight: 600; text-decoration: none; font-size: 12px; }
.footer-fixed a:hover { border-color: #9CB4E0; background: #EEF5FF; }
.event-card { background: #FFFFFF; border-radius: 10px; padding: 8px 10px; margin: 6px 0; border: 1px solid #E2EAF5; font-size: 14px; }
.event-time { font-weight: 700; color: #1F3B57; margin-right: 6px; }
.stButton > button { width: 100%; border: 1px solid #C9DBF2; border-radius: 10px; padding: 10px 8px; background: #F7FAFF; color: #1F3B57; }
.stButton > button:hover { border-color: #9CB4E0; background: #EEF5FF; }
.day-timeline { position: relative; height: 640px; border: 1px solid #E2EAF5; border-radius: 12px; background: #FFFFFF; background-image: repeating-linear-gradient(to bottom, #EEF2F7 0, #EEF2F7 1px, transparent 1px, transparent 40px); }
.event-block { position: absolute; padding: 6px 8px; border-radius: 10px; border: 1px solid transparent; font-size: 12px; color: #1F3B57; overflow: hidden; }
.event-block-time { font-weight: 700; }
.event-delete { position: absolute; top: 4px; right: 6px; font-size: 12px; color: #6B7C93; }
.week-day-title { font-family: "Segoe Script", "Bradley Hand", "Comic Sans MS", cursive; font-weight: 700; }
.month-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; }
.month-cell { display: block; padding: 10px 8px; border-radius: 10px; border: 1px solid #C9DBF2; background: #F7FAFF; text-align: center; color: #1F3B57; text-decoration: none; font-weight: 600; }
.month-cell.good { background: #E7F7E8; }
.month-cell.bad { background: #FBE7E7; }
.month-cell:hover { border-color: #9CB4E0; }
.month-weekday { font-weight: 700; text-align: center; color: #51729B; }
.detail-card { background: #FFFFFF; border-radius: 12px; padding: 10px 12px; border: 1px solid #E2EAF5; margin: 8px 0; }
</style>
""",
    unsafe_allow_html=True,
)

storage_mode = get_storage_mode()

if "user" not in st.session_state:
    st.markdown("<div class='title'>My Diary</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle'>打造属于自我的舒适之家</div>", unsafe_allow_html=True)

    login_tab, register_tab = st.tabs(["登录", "注册"])

    with login_tab:
        st.markdown("#### 登录")
        login_user = st.text_input("用户名", key="login_user")
        login_pass = st.text_input("密码", type="password", key="login_pass")
        if st.button("登录", key="login_btn"):
            if storage_mode == "supabase":
                info = db_get_user(login_user)
                if not info:
                    st.error("用户不存在")
                elif verify_password(login_pass, info["salt"], info["hash"]):
                    st.session_state.user = login_user
                    st.session_state.user_id = info["id"]
                    safe_rerun()
                else:
                    st.error("密码错误")
            else:
                users = load_users()
                info = users.get(login_user)
                if not info:
                    st.error("用户不存在")
                else:
                    if verify_password(login_pass, info["salt"], info["hash"]):
                        st.session_state.user = login_user
                        safe_rerun()
                    else:
                        st.error("密码错误")

    with register_tab:
        st.markdown("#### 注册")
        reg_user = st.text_input("用户名", key="reg_user")
        reg_pass = st.text_input("密码", type="password", key="reg_pass")
        reg_pass2 = st.text_input("确认密码", type="password", key="reg_pass2")
        if st.button("注册", key="reg_btn"):
            if not reg_user.strip():
                st.error("请输入用户名")
            elif len(reg_pass) < 6:
                st.error("密码至少 6 位")
            elif reg_pass != reg_pass2:
                st.error("两次密码不一致")
            else:
                if storage_mode == "supabase":
                    existing = db_get_user(reg_user)
                    if existing:
                        st.error("用户名已存在")
                    else:
                        user = db_create_user(reg_user, reg_pass)
                        if user:
                            st.success("注册成功，请登录")
                        else:
                            st.error("注册失败，请稍后重试")
                else:
                    users = load_users()
                    if reg_user in users:
                        st.error("用户名已存在")
                    else:
                        salt = uuid.uuid4().hex
                        users[reg_user] = {"salt": salt, "hash": hash_password(reg_pass, salt)}
                        save_users(users)
                        user_file = os.path.join(USER_DATA_DIR, f"{reg_user}.json")
                        ensure_data_file(user_file)
                        st.success("注册成功，请登录")
    st.stop()

if storage_mode == "supabase":
    if "user_id" not in st.session_state:
        info = db_get_user(st.session_state.user)
        if not info:
            del st.session_state.user
            safe_rerun()
        st.session_state.user_id = info["id"]
    data = db_load_user_data(st.session_state.user_id)
else:
    user_data_file = os.path.join(USER_DATA_DIR, f"{st.session_state.user}.json")
    data = load_data(user_data_file)

def persist_data(payload: dict):
    if storage_mode == "supabase":
        db_save_user_data(st.session_state.user_id, payload)
    else:
        save_data(payload, user_data_file)

st.markdown("<div class='title'>My Diary</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>打造属于自我的舒适之家</div>", unsafe_allow_html=True)
try:
    _build_stamp = datetime.fromtimestamp(os.path.getmtime(__file__)).strftime("%Y-%m-%d %H:%M")
    st.caption(f"版本 3.0 · 更新于：{_build_stamp}")
except Exception:
    pass

today_key = date.today().strftime("%Y-%m-%d")
if not data["moods"].get(today_key) and not st.session_state.get("mood_skipped"):
    st.markdown("<div class='section-title'>欢迎回家，今天的心情怎样？</div>", unsafe_allow_html=True)
    cols = st.columns(8)
    for i, mood in enumerate(MOODS):
        with cols[i % 8]:
            if st.button(mood, key=f"mood_{i}"):
                _, emoji = split_mood(mood)
                data["moods"][today_key] = emoji
                persist_data(data)
                safe_rerun()
    if st.button("跳过"):
        st.session_state.mood_skipped = True
        safe_rerun()
    st.stop()


PAGES = ["周视图", "月视图", "番茄钟", "统计", "单词学习"]
if "page" not in st.session_state:
    st.session_state.page = "周视图"
if st.session_state.page not in PAGES:
    st.session_state.page = "周视图"
if "pending_page" in st.session_state:
    st.session_state.page = st.session_state.pending_page
    del st.session_state.pending_page
if "week_flash_target" not in st.session_state:
    st.session_state.week_flash_target = None
    st.session_state.week_flash_step = 0
    st.session_state.week_flash_on = False
if "sidebar_collapsed" not in st.session_state:
    st.session_state.sidebar_collapsed = False
if "editing_event_id" not in st.session_state:
    st.session_state.editing_event_id = None
if "event_title" not in st.session_state:
    st.session_state.event_title = "新日程"
if "event_date" not in st.session_state:
    st.session_state.event_date = date.today()
if "event_start" not in st.session_state:
    st.session_state.event_start = datetime.strptime("09:00", "%H:%M").time()
if "event_end" not in st.session_state:
    st.session_state.event_end = datetime.strptime("10:00", "%H:%M").time()
if "event_category" not in st.session_state:
    st.session_state.event_category = CATEGORIES[0]
if "event_notes" not in st.session_state:
    st.session_state.event_notes = ""
if "event_form_bound_id" not in st.session_state:
    st.session_state.event_form_bound_id = None
if "delete_target_id" not in st.session_state:
    st.session_state.delete_target_id = None
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
if "word_temp_list" not in st.session_state:
    st.session_state.word_temp_list = []
if "word_test_active" not in st.session_state:
    st.session_state.word_test_active = False
if "word_test_queue" not in st.session_state:
    st.session_state.word_test_queue = []
if "word_test_index" not in st.session_state:
    st.session_state.word_test_index = 0
if "word_test_date" not in st.session_state:
    st.session_state.word_test_date = ""
if "word_test_feedback" not in st.session_state:
    st.session_state.word_test_feedback = ""
if "word_test_show_answer" not in st.session_state:
    st.session_state.word_test_show_answer = False
if "word_temp_feedback" not in st.session_state:
    st.session_state.word_temp_feedback = ""
if "last_page" not in st.session_state:
    st.session_state.last_page = st.session_state.page

if "jump_day" in st.query_params:
    jump_value = st.query_params.get("jump_day")
    try:
        jump_day = datetime.strptime(jump_value, "%Y-%m-%d").date()
        st.session_state.pending_page = "周视图"
        st.session_state.week_pick = jump_day
        st.session_state.week_flash_target = jump_day.strftime("%Y-%m-%d")
        st.session_state.week_flash_step = 0
        st.session_state.week_flash_on = True
        st.query_params.clear()
        safe_rerun()
    except Exception:
        st.query_params.clear()

if "theme" in st.query_params:
    theme_value = str(st.query_params.get("theme")).lower()
    if theme_value in {"dark", "light"}:
        st.session_state.dark_mode = theme_value == "dark"
    st.query_params.clear()
    safe_rerun()



if st.session_state.page != st.session_state.last_page:
    if st.session_state.page == "周视图":
        st.session_state.sidebar_collapsed = False
    else:
        st.session_state.sidebar_collapsed = True
    st.session_state.last_page = st.session_state.page

if st.session_state.sidebar_collapsed:
    st.markdown(
        """
<style>
section[data-testid="stSidebar"] { display: none; }
section.main { margin-left: 0 !important; }
</style>
""",
        unsafe_allow_html=True,
    )

if st.session_state.dark_mode:
    st.markdown(
        """
<style>
body { background-color: #1D2430; color: #E7EDF7; }
.block-container { background-color: #1D2430; }
section[data-testid="stSidebar"] { background-color: #252D3A; }
.title, .subtitle, .section-title, .stMarkdown, .stCaption,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5, .stMarkdown h6,
.stMarkdown p, .stMarkdown div,
label, .stTextInput label, .stSelectbox label, .stDateInput label,
.stTimeInput label, .stTextArea label { color: #E7EDF7 !important; }
.card, .detail-panel { background: #252D3A; border-color: #3A4A5F; color: #E7EDF7; }
.week-day-btn .stButton > button { background: #2E3A4C; border-color: #3A4A5F; color: #E7EDF7; }
.week-day-btn .stButton > button:hover { background: #37465C; }
.month-cell { background: #2A3445; border-color: #3A4A5F; color: #E7EDF7; }
.month-weekday { color: #9FB3C8; }
.event-card, .detail-event-btn .stButton > button { background: #202735; border-color: #3A4A5F; color: #E7EDF7; }
.event-block { color: #1F3B57; }
input, textarea, select { background-color: #202735 !important; color: #E7EDF7 !important; border-color: #3A4A5F !important; }
.footer-fixed a { background: #2E3A4C; border-color: #3A4A5F; color: #E7EDF7; }
.footer-fixed a:hover { background: #37465C; }
</style>
""",
        unsafe_allow_html=True,
    )

nav_cols = st.columns(len(PAGES))
for i, name in enumerate(PAGES):
    with nav_cols[i]:
        btn_type = "primary" if st.session_state.page == name else "secondary"
        if st.button(name, key=f"nav_{name}", type=btn_type):
            st.session_state.page = name
            if name != "周视图":
                st.session_state.sidebar_collapsed = True
            safe_rerun()

selected_page = st.session_state.page

def _reset_event_form():
    st.session_state.event_title = "新日程"
    st.session_state.event_date = date.today()
    st.session_state.event_start = datetime.strptime("09:00", "%H:%M").time()
    st.session_state.event_end = datetime.strptime("10:00", "%H:%M").time()
    st.session_state.event_category = CATEGORIES[0]
    st.session_state.event_notes = ""
    st.session_state.event_form_bound_id = None


def _bind_event_form(ev: dict):
    st.session_state.event_title = ev.get("title", "") or "未命名"
    st.session_state.event_date = datetime.strptime(ev["date"], "%Y-%m-%d").date()
    st.session_state.event_start = datetime.strptime(ev["start"], "%H:%M").time()
    st.session_state.event_end = datetime.strptime(ev["end"], "%H:%M").time()
    cat = ev.get("category", "其他")
    st.session_state.event_category = cat if cat in CATEGORIES else "其他"
    st.session_state.event_notes = ev.get("notes", "")
    st.session_state.event_form_bound_id = ev.get("id")


def _add_word_to_temp():
    word = st.session_state.get("word_input", "").strip()
    meaning = st.session_state.get("meaning_input", "").strip()
    if word and meaning:
        st.session_state.word_temp_list.append({"word": word, "meaning": meaning})
        st.session_state.word_input = ""
        st.session_state.meaning_input = ""
    else:
        st.session_state.word_temp_feedback = "请填写单词与释义"


def _save_temp_to_book(data_ref: dict):
    if not st.session_state.word_temp_list:
        st.session_state.word_temp_feedback = "今日临时列表为空"
        return
    today_key = date.today().strftime("%Y-%m-%d")
    data_ref.setdefault("word_books", {})
    data_ref["word_books"].setdefault(today_key, [])
    data_ref["word_books"][today_key].extend(st.session_state.word_temp_list)
    persist_data(data_ref)
    st.session_state.word_temp_list = []
    st.session_state.word_temp_feedback = "已保存至词库"


def _submit_test_answer():
    queue = st.session_state.word_test_queue
    idx = st.session_state.word_test_index
    if idx >= len(queue):
        return
    current = queue[idx]
    expected = current["meaning"].strip().lower()
    got = st.session_state.get("test_answer", "").strip().lower()
    if got and got == expected:
        st.session_state.word_test_feedback = "正确！"
        st.session_state.word_test_index += 1
        st.session_state.test_answer = ""
        st.session_state.word_test_show_answer = False
    else:
        st.session_state.word_test_feedback = f"正确答案是：{current['meaning']}"
        st.session_state.word_test_show_answer = True


def _next_test_word():
    st.session_state.word_test_index += 1
    st.session_state.word_test_feedback = ""
    st.session_state.word_test_show_answer = False
    st.session_state.test_answer = ""


def _stop_test():
    st.session_state.word_test_active = False
    st.session_state.word_test_queue = []
    st.session_state.word_test_index = 0
    st.session_state.word_test_date = ""
    st.session_state.word_test_feedback = ""
    st.session_state.word_test_show_answer = False
    st.session_state.test_answer = ""


if st.session_state.editing_event_id:
    _editing_event = next((e for e in data["events"] if e["id"] == st.session_state.editing_event_id), None)
    if _editing_event and st.session_state.event_form_bound_id != _editing_event["id"]:
        _bind_event_form(_editing_event)
elif st.session_state.event_form_bound_id is not None:
    _reset_event_form()

if not st.session_state.sidebar_collapsed:
    with st.sidebar:
        edit_mode = st.session_state.editing_event_id is not None
        st.markdown("### 编辑日程" if edit_mode else "### 添加日程")
        with st.form("add_event"):
            t = st.text_input("名称", key="event_title")
            d = st.date_input("日期", key="event_date")
            start = st.time_input("开始时间", key="event_start")
            end = st.time_input("结束时间", key="event_end")
            cat = st.selectbox("类型", CATEGORIES, key="event_category")
            notes = st.text_area("备注（可选）", key="event_notes")

            btn_cols = st.columns(2)
            with btn_cols[0]:
                submitted = st.form_submit_button("保存修改" if edit_mode else "保存")
            with btn_cols[1]:
                canceled = st.form_submit_button("取消编辑" if edit_mode else "重置")

            if canceled:
                st.session_state.editing_event_id = None
                _reset_event_form()
                safe_rerun()

            if submitted:
                payload = {
                    "title": t.strip() or "未命名",
                    "date": d.strftime("%Y-%m-%d"),
                    "start": start.strftime("%H:%M"),
                    "end": end.strftime("%H:%M"),
                    "category": cat,
                    "notes": notes.strip(),
                }
                if edit_mode:
                    for idx, item in enumerate(data["events"]):
                        if item["id"] == st.session_state.editing_event_id:
                            payload["id"] = item["id"]
                            data["events"][idx] = payload
                            break
                    persist_data(data)
                    st.session_state.editing_event_id = None
                    _reset_event_form()
                    st.success("已更新")
                    safe_rerun()
                else:
                    payload["id"] = str(uuid.uuid4())
                    data["events"].append(payload)
                    persist_data(data)
                    st.success("已保存")

        if st.session_state.delete_target_id:
            target = next((e for e in data["events"] if e["id"] == st.session_state.delete_target_id), None)
            if target:
                st.warning("是否删除该日程？")
                st.caption(f"{target.get('start', '')}-{target.get('end', '')} {target.get('title', '')}")
                delete_cols = st.columns(2)
                with delete_cols[0]:
                    if st.button("确认删除", key="confirm_delete"):
                        data["events"] = [e for e in data["events"] if e["id"] != target["id"]]
                        persist_data(data)
                        if st.session_state.editing_event_id == target["id"]:
                            st.session_state.editing_event_id = None
                            _reset_event_form()
                        st.session_state.delete_target_id = None
                        safe_rerun()
                with delete_cols[1]:
                    if st.button("取消", key="cancel_delete"):
                        st.session_state.delete_target_id = None
            else:
                st.session_state.delete_target_id = None


if selected_page == "周视图":
    st.markdown("<div class='section-title'>周视图</div>", unsafe_allow_html=True)
    picked = st.date_input("选择周中的任意日期", value=date.today(), key="week_pick")
    week_start = iso_week_start(picked)
    st.markdown(f"**周：{week_start.strftime('%Y/%m/%d')} - {(week_start + timedelta(days=6)).strftime('%Y/%m/%d')}**")

    if st.session_state.get("day_detail_date"):
        detail_date = st.session_state.day_detail_date
        detail_events = [e for e in data["events"] if e["date"] == detail_date]
        st.markdown("<div class='detail-panel'>", unsafe_allow_html=True)
        st.markdown(f"#### {detail_date} 全部日程")
        close_cols = st.columns([1, 5])
        with close_cols[0]:
            if st.button("关闭", key="close_day_detail"):
                st.session_state.day_detail_date = None
                safe_rerun()
        if not detail_events:
            st.info("暂无日程")
        else:
            for ev in detail_events:
                st.markdown("<div class='detail-event-btn'>", unsafe_allow_html=True)
                if st.button(f"{ev['start']} - {ev['end']}  {ev['title']}", key=f"pick_event_{ev['id']}"):
                    st.session_state.editing_event_id = ev["id"]
                    st.session_state.sidebar_collapsed = False
                    _bind_event_form(ev)
                    safe_rerun()
                st.markdown("</div>", unsafe_allow_html=True)
                st.write(f"类型：{ev.get('category', '其他')}")
                notes = ev.get("notes", "").strip()
                st.write(f"备注：{notes if notes else '无'}")
                if st.button("🗑 删除", key=f"delete_event_{ev['id']}"):
                    st.session_state.delete_target_id = ev["id"]
                    safe_rerun()
                st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    flash_target = st.session_state.week_flash_target
    flash_on = st.session_state.week_flash_on
    flash_step = st.session_state.week_flash_step

    day_cols = st.columns(7)
    for i in range(7):
        d = week_start + timedelta(days=i)
        day_key = d.strftime("%Y-%m-%d")
        events = [e for e in data["events"] if e["date"] == day_key]
        with day_cols[i]:
            is_flash = flash_target == day_key and flash_on
            container_class = "week-day-btn flash-on" if is_flash else "week-day-btn"
            st.markdown(f"<div class='{container_class}'>", unsafe_allow_html=True)
            label_en = WEEKDAY_SHORT_EN[d.weekday()]
            label_cn = WEEKDAY_CN[d.weekday()]
            if st.button(f"{label_en}\n{label_cn} {d.strftime('%m/%d')}", key=f"day_card_{day_key}"):
                st.session_state.day_detail_date = day_key
            st.markdown("</div>", unsafe_allow_html=True)
            if not events:
                st.caption("无日程")
            else:
                for ev in sorted(events, key=lambda x: x["start"]):
                    action_cols = st.columns([8, 1])
                    with action_cols[0]:
                        st.caption(f"{ev['start']}-{ev['end']}  {ev['title']}")
                    with action_cols[1]:
                        if st.button("🗑", key=f"delete_inline_{ev['id']}"):
                            st.session_state.delete_target_id = ev["id"]
                            safe_rerun()
                layouts = layout_day_events(events)
                html_blocks = ["<div class='day-timeline'>"]
                range_start = TIME_START * 60
                range_end = TIME_END * 60
                for item in layouts:
                    ev = item["event"]
                    start = item["start"]
                    end = item["end"]
                    if end <= range_start or start >= range_end:
                        continue
                    start = max(start, range_start)
                    end = min(end, range_end)
                    duration = max(30, end - start)
                    top = int((start - range_start) / (range_end - range_start) * DAY_HEIGHT)
                    height = max(36, int(duration / (range_end - range_start) * DAY_HEIGHT))
                    color = CATEGORY_COLORS.get(ev.get("category", "其他"), "#E8E0FF")
                    left_pct = item["col"] / item["cols"] * 100
                    width_pct = 100 / item["cols"]
                    html_blocks.append(
                        "<div class='event-block' "
                        f"style='top:{top}px; height:{height}px; left:{left_pct}%; width:calc({width_pct}% - 6px); "
                        f"background:{color}; border-color:{color};'>"
                        f"<div class='event-delete'>🗑</div>"
                        f"<div class='event-block-time'>{ev['start']}-{ev['end']}</div>"
                        f"<div>{ev['title']}</div>"
                        "</div>"
                    )
                html_blocks.append("</div>")
                st.markdown("".join(html_blocks), unsafe_allow_html=True)

    if flash_target and flash_step < 4:
        time.sleep(0.25)
        st.session_state.week_flash_on = not flash_on
        st.session_state.week_flash_step = flash_step + 1
        safe_rerun()
    elif flash_target:
        st.session_state.week_flash_target = None
        st.session_state.week_flash_step = 0
        st.session_state.week_flash_on = False



if selected_page == "月视图":
    st.markdown("<div class='section-title'>月视图</div>", unsafe_allow_html=True)
    curr = st.date_input("选择月（选择任意当月日期）", value=date.today(), key="month_pick")
    m_start = month_start(curr)
    st.markdown(f"**{m_start.strftime('%Y年 %m月')}**")
    first_weekday = (m_start.weekday() + 1) % 7
    days_in_month = (next_month(m_start) - timedelta(days=1)).day
    total_slots = 42
    start_offset = (first_weekday - 1) % 7
    day_cursor = 1

    week_headers = ["一", "二", "三", "四", "五", "六", "日"]
    header_cols = st.columns(7)
    for i, h in enumerate(week_headers):
        with header_cols[i]:
            st.markdown(f"<div class='month-weekday'>{h}</div>", unsafe_allow_html=True)

    html_cells = ["<div class='month-grid'>"]
    for slot in range(total_slots):
        if slot < start_offset or day_cursor > days_in_month:
            html_cells.append("<div></div>")
            continue
        current = m_start.replace(day=day_cursor)
        date_key = current.strftime("%Y-%m-%d")
        mood = data["moods"].get(date_key, "")
        mood_text = MOOD_LABELS.get(mood, "")
        mood_short = mood_text[:2] if mood_text else ""
        label = f"{day_cursor} {mood}{mood_short}" if mood else f"{day_cursor}"
        mood_class = "bad" if mood in BAD_MOOD_EMOJIS else ("good" if mood else "")
        html_cells.append(
            f"<a class='month-cell {mood_class}' href='?jump_day={date_key}'>"
            f"{label}"
            f"</a>"
        )
        day_cursor += 1
    html_cells.append("</div>")
    st.markdown("".join(html_cells), unsafe_allow_html=True)

if selected_page == "单词学习":
    st.markdown("<div class='section-title'>单词学习</div>", unsafe_allow_html=True)
    left_col, mid_col, right_col = st.columns([1.1, 1.6, 1.1])

    with mid_col:
        st.markdown("#### 今日任务")
        input_cols = st.columns(2)
        with input_cols[0]:
            word_input = st.text_input("单词", key="word_input")
        with input_cols[1]:
            meaning_input = st.text_input("释义", key="meaning_input")

        add_cols = st.columns([1, 1, 2])
        with add_cols[0]:
            st.button("添加", key="add_word", on_click=_add_word_to_temp)

        with add_cols[1]:
            st.button("保存至词库", key="save_word_book", on_click=_save_temp_to_book, args=(data,))

        st.caption(f"今日已添加：{len(st.session_state.word_temp_list)} 个单词")
        if st.session_state.word_temp_feedback:
            st.info(st.session_state.word_temp_feedback)
            st.session_state.word_temp_feedback = ""
        if st.session_state.word_temp_list:
            for item in st.session_state.word_temp_list:
                st.write(f"• {item['word']} - {item['meaning']}")

    with left_col:
        st.markdown("#### 我的词库")
        book_dates = sorted(data.get("word_books", {}).keys(), reverse=True)
        selected_date = st.selectbox("选择日期", book_dates, key="word_book_date") if book_dates else None

        if selected_date:
            words = data["word_books"].get(selected_date, [])
            st.caption(f"{selected_date} 共 {len(words)} 个单词")
            for item in words:
                st.write(f"• {item['word']} - {item['meaning']}")

            word_options = [f"{w['word']} - {w['meaning']}" for w in words]
            pick_word = st.selectbox("选择要删除的单词", word_options, key="delete_word_pick") if word_options else None
            delete_cols = st.columns(2)
            with delete_cols[0]:
                if st.button("删除此单词", key="delete_one_word") and pick_word:
                    keep = [
                        w for w in words
                        if f"{w['word']} - {w['meaning']}" != pick_word
                    ]
                    data["word_books"][selected_date] = keep
                    persist_data(data)
                    st.success("已删除")
                    safe_rerun()
            with delete_cols[1]:
                if st.button("删除此日期全部", key="delete_date_words"):
                    data["word_books"].pop(selected_date, None)
                    persist_data(data)
                    st.success("已删除全部")
                    safe_rerun()
        else:
            st.info("暂无词库记录")

    with right_col:
        st.markdown("#### 开始背诵")
        test_dates = sorted(data.get("word_books", {}).keys(), reverse=True)
        test_date = st.selectbox("选择词库日期", test_dates, key="test_date") if test_dates else None

        if not st.session_state.word_test_active:
            if st.button("开始背诵", key="start_test"):
                if not test_date:
                    st.info("请先选择日期")
                else:
                    queue = data["word_books"].get(test_date, [])
                    if not queue:
                        st.info("该日期没有单词")
                    else:
                        st.session_state.word_test_active = True
                        st.session_state.word_test_queue = queue
                        st.session_state.word_test_index = 0
                        st.session_state.word_test_date = test_date
                        st.session_state.word_test_feedback = ""
                        st.session_state.word_test_show_answer = False
                        safe_rerun()
        else:
            queue = st.session_state.word_test_queue
            idx = st.session_state.word_test_index
            test_date = st.session_state.word_test_date

            if idx >= len(queue):
                st.success(f"恭喜你！已完成【{test_date}】所有单词的背诵！")
                if st.button("结束背诵", key="finish_test"):
                    st.session_state.word_test_active = False
                    st.session_state.word_test_queue = []
                    st.session_state.word_test_index = 0
                    st.session_state.word_test_date = ""
                    st.session_state.word_test_feedback = ""
                    st.session_state.word_test_show_answer = False
                    safe_rerun()
            else:
                current = queue[idx]
                st.markdown("<div style='text-align:center; font-size:34px; font-weight:700;'>" + current["word"] + "</div>", unsafe_allow_html=True)
                st.text_input("请输入释义", key="test_answer")
                if st.session_state.word_test_feedback:
                    st.info(st.session_state.word_test_feedback)

                action_cols = st.columns(2)
                with action_cols[0]:
                    st.button("提交", key="submit_test", on_click=_submit_test_answer)
                with action_cols[1]:
                    if st.session_state.word_test_show_answer:
                        st.button("下一个", key="next_test", on_click=_next_test_word)
                    st.button("结束背诵", key="stop_test", on_click=_stop_test)

footer_label = "深色模式" if not st.session_state.dark_mode else "浅色模式"
footer_theme = "dark" if not st.session_state.dark_mode else "light"
st.markdown(
    f"<div class='footer-fixed'><a href='?theme={footer_theme}'>{footer_label}</a></div>",
    unsafe_allow_html=True,
)

if selected_page == "番茄钟":
    st.markdown("<div class='section-title'>番茄钟</div>", unsafe_allow_html=True)
    left, right = st.columns([1, 2])

    with left:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        if not data["pomodoro_records"]:
            st.caption("暂无记录")
        for rec in data["pomodoro_records"][-50:][::-1]:
            st.write(f"{rec['start']}  {format_seconds(rec['seconds'])}")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        total_seconds = sum(r.get("seconds", 0) for r in data["pomodoro_records"])
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        st.markdown(f"<div class='focus-text'>你已专注了{h}小时{m}分钟</div>", unsafe_allow_html=True)

        if "pomodoro_running" not in st.session_state:
            st.session_state.pomodoro_running = False
            st.session_state.pomodoro_start = None
            st.session_state.pomodoro_duration = 0

        if st.session_state.pomodoro_running:
            elapsed = int(time.time() - st.session_state.pomodoro_start)
            remaining = max(0, st.session_state.pomodoro_duration - elapsed)
        else:
            remaining = 0

        st.markdown(f"<div class='timer-text'>{format_seconds(remaining)}</div>", unsafe_allow_html=True)

        preset_row1 = st.columns(3)
        preset_row2 = st.columns(3)
        presets = [(15, "15:00"), (30, "30:00"), (60, "60:00"), (1, "01:00"), (5, "05:00"), (10, "10:00")]
        for i, (mins, label) in enumerate(presets):
            cols = preset_row1 if i < 3 else preset_row2
            with cols[i % 3]:
                if st.button(label, key=f"preset_{mins}"):
                    st.session_state.pomodoro_running = True
                    st.session_state.pomodoro_start = time.time()
                    st.session_state.pomodoro_duration = mins * 60
                    safe_rerun()

        if st.button("取消"):
            if st.session_state.pomodoro_running:
                elapsed = int(time.time() - st.session_state.pomodoro_start)
                if elapsed >= int(st.session_state.pomodoro_duration * 0.8):
                    rec = {
                        "start": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "seconds": st.session_state.pomodoro_duration,
                    }
                    data["pomodoro_records"].append(rec)
                    persist_data(data)
            st.session_state.pomodoro_running = False
            st.session_state.pomodoro_start = None
            st.session_state.pomodoro_duration = 0
            safe_rerun()

        if st.session_state.pomodoro_running:
            if remaining <= 0:
                rec = {
                    "start": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "seconds": st.session_state.pomodoro_duration,
                }
                data["pomodoro_records"].append(rec)
                persist_data(data)
                st.session_state.pomodoro_running = False
                st.session_state.pomodoro_start = None
                st.session_state.pomodoro_duration = 0
                safe_rerun()
            else:
                if not maybe_autorefresh(1000, "pomodoro_autorefresh"):
                    st.caption("计时进行中，点击任意按钮或切换页面可更新倒计时。")

if selected_page == "统计":
    st.markdown("<div class='section-title'>统计</div>", unsafe_allow_html=True)
    totals = {c: 0 for c in CATEGORIES}
    for ev in data["events"]:
        try:
            start_dt = datetime.strptime(ev["start"], "%H:%M")
            end_dt = datetime.strptime(ev["end"], "%H:%M")
            minutes = int((end_dt - start_dt).total_seconds() / 60)
            if minutes < 0:
                minutes += 24 * 60
            totals[ev.get("category", "其他")] += minutes
        except Exception:
            continue

    fig_col1, fig_col2 = st.columns(2)
    with fig_col1:
        bar_fig = go.Figure(
            data=[
                go.Bar(
                    x=list(totals.keys()),
                    y=list(totals.values()),
                    marker_color=[CATEGORY_COLORS[c] for c in totals.keys()],
                )
            ]
        )
        bar_fig.update_layout(
            title="本周分类时长",
            yaxis_title="分钟",
            height=360,
            margin=dict(l=40, r=20, t=60, b=40),
            font=dict(family="Microsoft YaHei, SimHei, Arial", size=14),
        )
        st.plotly_chart(bar_fig, use_container_width=True)

    with fig_col2:
        values = [v for v in totals.values() if v > 0]
        labels = [k for k, v in totals.items() if v > 0]
        if values:
            pie_fig = go.Figure(
                data=[
                    go.Pie(
                        labels=labels,
                        values=values,
                        textinfo="percent",
                        insidetextorientation="radial",
                        marker=dict(colors=[CATEGORY_COLORS[k] for k in labels]),
                    )
                ]
            )
        else:
            pie_fig = go.Figure()
            pie_fig.add_annotation(text="暂无数据", x=0.5, y=0.5, showarrow=False)
        pie_fig.update_layout(
            title="分类占比",
            height=360,
            margin=dict(l=20, r=20, t=60, b=40),
            font=dict(family="Microsoft YaHei, SimHei, Arial", size=14),
        )
        st.plotly_chart(pie_fig, use_container_width=True)

if selected_page == "往期回顾":
    st.markdown("<div class='section-title'>往期回顾</div>", unsafe_allow_html=True)
    with st.form("add_archive"):
        a_date = st.date_input("日期", value=date.today(), key="archive_date")
        a_text = st.text_area("说说你的想法")
        a_cat = st.selectbox("类型", CATEGORIES, key="archive_cat")
        submitted = st.form_submit_button("保存")
        if submitted:
            data["archives"].append({
                "id": str(uuid.uuid4()),
                "date": a_date.strftime("%Y-%m-%d"),
                "category": a_cat,
                "text": a_text.strip(),
            })
            persist_data(data)
            st.success("已保存")

    for item in sorted(data.get("archives", []), key=lambda x: x["date"], reverse=True):
        with st.expander(f"{item['date']} · {item.get('category', '-')}"):
            st.write(item.get("text", ""))
            if st.button("删除", key=f"del_arc_{item['id']}"):
                data["archives"] = [a for a in data["archives"] if a["id"] != item["id"]]
                persist_data(data)
                safe_rerun()