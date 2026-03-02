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
from zoneinfo import ZoneInfo
import plotly.graph_objects as go
from supabase import create_client, Client


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
USER_DATA_DIR = os.path.join(DATA_DIR, "users")

DEFAULT_DATA = {
    "events": [],
    "archives": [],
    "moods": {},
    "pomodoro_records": [],
    "pomodoro_state": {"running": False, "start": None, "duration": 0},
    "word_books": {},
    "habits": [],
    "forum_posts": [],
    "forum_comments": [],
}

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
    data.setdefault("pomodoro_state", {"running": False, "start": None, "duration": 0})
    data.setdefault("word_books", {})
    data.setdefault("habits", [])
    data.setdefault("forum_posts", [])
    data.setdefault("forum_comments", [])
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


def _set_supabase_unavailable(exc: Exception | None = None) -> None:
    st.session_state.storage_mode = "local"
    if exc is not None:
        st.session_state.supabase_error = str(exc)


def get_storage_mode() -> str:
    cached = st.session_state.get("storage_mode")
    if cached in {"supabase", "local"}:
        return cached
    client = get_supabase_client()
    if not client:
        st.session_state.storage_mode = "local"
        return "local"
    try:
        client.table("user_accounts").select("id").limit(1).execute()
    except Exception as exc:
        _set_supabase_unavailable(exc)
        return "local"
    st.session_state.storage_mode = "supabase"
    return "supabase"


def db_get_user(username: str):
    client = get_supabase_client()
    if not client:
        return None
    try:
        res = client.table("user_accounts").select("id, username, salt, hash").eq("username", username).limit(1).execute()
    except Exception as exc:
        _set_supabase_unavailable(exc)
        return None
    return res.data[0] if res.data else None


def db_create_user(username: str, password: str):
    client = get_supabase_client()
    if not client:
        return None
    salt = uuid.uuid4().hex
    hashed = hash_password(password, salt)
    try:
        user_res = client.table("user_accounts").insert({"username": username, "salt": salt, "hash": hashed}).execute()
    except Exception as exc:
        _set_supabase_unavailable(exc)
        return None
    user = user_res.data[0] if user_res.data else None
    if user:
        try:
            client.table("user_data").upsert({"user_id": user["id"], "data": DEFAULT_DATA}).execute()
        except Exception as exc:
            _set_supabase_unavailable(exc)
            return None
    return user


def db_update_user_password(username: str, password: str) -> bool:
    client = get_supabase_client()
    if not client:
        return False
    salt = uuid.uuid4().hex
    hashed = hash_password(password, salt)
    try:
        res = client.table("user_accounts").update({"salt": salt, "hash": hashed}).eq("username", username).execute()
    except Exception as exc:
        _set_supabase_unavailable(exc)
        return False
    return bool(res.data)


def local_update_user_password(username: str, password: str) -> bool:
    users = load_users()
    if username not in users:
        return False
    salt = uuid.uuid4().hex
    users[username] = {"salt": salt, "hash": hash_password(password, salt)}
    save_users(users)
    return True


def db_load_user_data(user_id: str):
    client = get_supabase_client()
    if not client:
        return DEFAULT_DATA.copy()
    try:
        res = client.table("user_data").select("data").eq("user_id", user_id).limit(1).execute()
    except Exception as exc:
        _set_supabase_unavailable(exc)
        return DEFAULT_DATA.copy()
    if res.data:
        data = res.data[0].get("data") or {}
    else:
        try:
            client.table("user_data").upsert({"user_id": user_id, "data": DEFAULT_DATA}).execute()
        except Exception as exc:
            _set_supabase_unavailable(exc)
            return DEFAULT_DATA.copy()
        data = DEFAULT_DATA.copy()
    data.setdefault("events", [])
    data.setdefault("archives", [])
    data.setdefault("moods", {})
    data.setdefault("pomodoro_records", [])
    data.setdefault("pomodoro_state", {"running": False, "start": None, "duration": 0})
    data.setdefault("word_books", {})
    data.setdefault("habits", [])
    data.setdefault("forum_posts", [])
    data.setdefault("forum_comments", [])
    return data


def db_save_user_data(user_id: str, data: dict):
    client = get_supabase_client()
    if not client:
        return
    try:
        client.table("user_data").upsert({"user_id": user_id, "data": data}).execute()
    except Exception as exc:
        _set_supabase_unavailable(exc)
        return


def test_supabase_connection() -> tuple[bool, str]:
    client = get_supabase_client()
    if not client:
        return False, "未找到 SUPABASE_URL/SUPABASE_KEY"
    try:
        client.table("user_accounts").select("id").limit(1).execute()
    except Exception as exc:
        return False, str(exc)
    return True, "连接正常"


def _normalize_timestamp(value: str | None) -> str:
    if not value:
        return ""
    return value


def _format_timestamp(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(LOCAL_TZ).strftime("%m-%d %H:%M")
    except Exception:
        return str(value)


def _forum_snippet(text: str, limit: int = 24) -> str:
    compact = " ".join(text.strip().split())
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "..."


def forum_list_posts(storage_mode: str, data_ref: dict | None = None) -> list[dict]:
    if storage_mode == "supabase":
        client = get_supabase_client()
        if not client:
            return []
        try:
            res = (
                client.table("forum_posts")
                .select("id, user_id, username, content, created_at, updated_at, deleted")
                .order("created_at", desc=True)
                .limit(80)
                .execute()
            )
        except Exception as exc:
            _set_supabase_unavailable(exc)
            return []
        posts = res.data or []
        return [p for p in posts if not p.get("deleted")]

    data_ref = data_ref or {}
    posts = [p for p in data_ref.get("forum_posts", []) if not p.get("deleted")]
    return sorted(posts, key=lambda x: x.get("created_at", ""), reverse=True)


def forum_list_comments(storage_mode: str, post_id: str, data_ref: dict | None = None) -> list[dict]:
    if storage_mode == "supabase":
        client = get_supabase_client()
        if not client:
            return []
        try:
            res = (
                client.table("forum_comments")
                .select("id, post_id, user_id, username, content, created_at, updated_at, deleted")
                .eq("post_id", post_id)
                .order("created_at", desc=False)
                .execute()
            )
        except Exception as exc:
            _set_supabase_unavailable(exc)
            return []
        comments = res.data or []
        return [c for c in comments if not c.get("deleted")]

    data_ref = data_ref or {}
    comments = [
        c for c in data_ref.get("forum_comments", [])
        if c.get("post_id") == post_id and not c.get("deleted")
    ]
    return sorted(comments, key=lambda x: x.get("created_at", ""))


def forum_create_post(storage_mode: str, content: str, user_id: str, username: str, data_ref: dict | None = None) -> bool:
    created_at = now_local().isoformat()
    if storage_mode == "supabase":
        client = get_supabase_client()
        if not client:
            return False
        payload = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "username": username,
            "content": content,
            "created_at": created_at,
            "updated_at": None,
            "deleted": False,
        }
        try:
            res = client.table("forum_posts").insert(payload).execute()
        except Exception as exc:
            _set_supabase_unavailable(exc)
            return False
        return bool(res.data)

    if data_ref is None:
        return False
    data_ref.setdefault("forum_posts", [])
    data_ref["forum_posts"].append({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "username": username,
        "content": content,
        "created_at": created_at,
        "updated_at": None,
        "deleted": False,
    })
    return True


def forum_update_post(storage_mode: str, post_id: str, content: str, data_ref: dict | None = None) -> bool:
    updated_at = now_local().isoformat()
    if storage_mode == "supabase":
        client = get_supabase_client()
        if not client:
            return False
        try:
            res = (
                client.table("forum_posts")
                .update({"content": content, "updated_at": updated_at})
                .eq("id", post_id)
                .execute()
            )
        except Exception as exc:
            _set_supabase_unavailable(exc)
            return False
        return bool(res.data)

    if data_ref is None:
        return False
    for item in data_ref.get("forum_posts", []):
        if item.get("id") == post_id:
            item["content"] = content
            item["updated_at"] = updated_at
            return True
    return False


def forum_delete_post(storage_mode: str, post_id: str, data_ref: dict | None = None) -> bool:
    if storage_mode == "supabase":
        client = get_supabase_client()
        if not client:
            return False
        try:
            res = client.table("forum_posts").delete().eq("id", post_id).execute()
        except Exception as exc:
            _set_supabase_unavailable(exc)
            return False
        return bool(res.data)

    if data_ref is None:
        return False
    original = data_ref.get("forum_posts", [])
    remaining = [item for item in original if item.get("id") != post_id]
    if len(remaining) == len(original):
        return False
    data_ref["forum_posts"] = remaining
    return True


def forum_create_comment(
    storage_mode: str,
    post_id: str,
    content: str,
    user_id: str,
    username: str,
    data_ref: dict | None = None,
) -> bool:
    created_at = now_local().isoformat()
    if storage_mode == "supabase":
        client = get_supabase_client()
        if not client:
            return False
        payload = {
            "id": str(uuid.uuid4()),
            "post_id": post_id,
            "user_id": user_id,
            "username": username,
            "content": content,
            "created_at": created_at,
            "updated_at": None,
            "deleted": False,
        }
        try:
            res = client.table("forum_comments").insert(payload).execute()
        except Exception as exc:
            _set_supabase_unavailable(exc)
            return False
        return bool(res.data)

    if data_ref is None:
        return False
    data_ref.setdefault("forum_comments", [])
    data_ref["forum_comments"].append({
        "id": str(uuid.uuid4()),
        "post_id": post_id,
        "user_id": user_id,
        "username": username,
        "content": content,
        "created_at": created_at,
        "updated_at": None,
        "deleted": False,
    })
    return True


def forum_update_comment(storage_mode: str, comment_id: str, content: str, data_ref: dict | None = None) -> bool:
    updated_at = now_local().isoformat()
    if storage_mode == "supabase":
        client = get_supabase_client()
        if not client:
            return False
        try:
            res = (
                client.table("forum_comments")
                .update({"content": content, "updated_at": updated_at})
                .eq("id", comment_id)
                .execute()
            )
        except Exception as exc:
            _set_supabase_unavailable(exc)
            return False
        return bool(res.data)

    if data_ref is None:
        return False
    for item in data_ref.get("forum_comments", []):
        if item.get("id") == comment_id:
            item["content"] = content
            item["updated_at"] = updated_at
            return True
    return False


def forum_delete_comment(storage_mode: str, comment_id: str, data_ref: dict | None = None) -> bool:
    if storage_mode == "supabase":
        client = get_supabase_client()
        if not client:
            return False
        try:
            res = client.table("forum_comments").delete().eq("id", comment_id).execute()
        except Exception as exc:
            _set_supabase_unavailable(exc)
            return False
        return bool(res.data)

    if data_ref is None:
        return False
    original = data_ref.get("forum_comments", [])
    remaining = [item for item in original if item.get("id") != comment_id]
    if len(remaining) == len(original):
        return False
    data_ref["forum_comments"] = remaining
    return True


def iso_week_start(d: date):
    return d - timedelta(days=d.weekday())


def month_start(d: date):
    return d.replace(day=1)

def next_month(d: date):
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)

LOCAL_TZ = ZoneInfo("Asia/Shanghai")

def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)

def today_local() -> date:
    return now_local().date()


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
#theme-toggle-anchor + div { position: fixed; right: 160px; bottom: 24px; z-index: 999; width: auto; }
#theme-toggle-anchor + div .stButton { width: auto; }
#theme-toggle-anchor + div .stButton > button { width: 96px; text-align: center; border: 1px solid #C9DBF2; border-radius: 10px; padding: 6px 10px; background: #F7FAFF; color: #1F3B57; font-weight: 600; font-size: 12px; }
#theme-toggle-anchor + div .stButton > button:hover { border-color: #9CB4E0; background: #EEF5FF; }
.event-card { background: #FFFFFF; border-radius: 10px; padding: 8px 10px; margin: 6px 0; border: 1px solid #E2EAF5; font-size: 14px; }
.event-time { font-weight: 700; color: #1F3B57; margin-right: 6px; }
.stButton > button { width: 100%; border: 1px solid #C9DBF2; border-radius: 10px; padding: 10px 8px; background: #F7FAFF; color: #1F3B57; }
.stButton > button:hover { border-color: #9CB4E0; background: #EEF5FF; }
.day-timeline { position: relative; height: 640px; border: 1px solid #E2EAF5; border-radius: 12px; background: #FFFFFF; background-image: repeating-linear-gradient(to bottom, #EEF2F7 0, #EEF2F7 1px, transparent 1px, transparent 40px); }
.event-block { position: absolute; padding: 4px 8px 6px; border-radius: 10px; border: 1px solid transparent; font-size: 12px; color: #1F3B57; overflow: hidden; }
.event-block-time { font-weight: 700; }
.event-block-time { margin-top: -2px; }
.event-delete { position: absolute; top: 4px; right: 6px; font-size: 12px; color: #6B7C93; }
.week-day-title { font-family: "Segoe Script", "Bradley Hand", "Comic Sans MS", cursive; font-weight: 700; }
.month-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; }
.month-cell { display: block; padding: 10px 8px; border-radius: 10px; border: 1px solid #C9DBF2; background: #F7FAFF; text-align: center; color: #1F3B57; text-decoration: none; font-weight: 600; }
.month-cell.good { background: #E7F7E8; }
.month-cell.bad { background: #FBE7E7; }
.month-cell:hover { border-color: #9CB4E0; }
.month-weekday { font-weight: 700; text-align: center; color: #51729B; }
.detail-card { background: #FFFFFF; border-radius: 12px; padding: 10px 12px; border: 1px solid #E2EAF5; margin: 8px 0; }
.habit-card .stButton > button { background: #F9F9F9; border: 1px solid #E2EAF5; border-radius: 10px; padding: 18px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); min-height: 220px; display: flex; flex-direction: column; justify-content: space-between; text-align: left; font-size: 18px; line-height: 1.25; }
.habit-card .stButton > button:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.10); transform: translateY(-1px); }
.habit-card.complete .stButton > button { background: #E7F7E8; border-color: #BFE8C6; }
.habit-record { padding: 8px 10px; border-radius: 8px; border: 1px solid #E2EAF5; margin: 6px 0; }
</style>
""",
    unsafe_allow_html=True,
)

storage_mode = get_storage_mode()
if storage_mode == "local" and st.session_state.get("supabase_error"):
    st.warning("Supabase 连接失败，已切换到本地存储。请检查 Secrets 里的 SUPABASE_URL/SUPABASE_KEY。")

if "user" not in st.session_state:
    st.markdown("<div class='title'>My Diary</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle'>打造属于自我的舒适之家</div>", unsafe_allow_html=True)

    with st.expander("Supabase 连接测试"):
        st.caption(f"当前存储模式：{storage_mode}")
        if st.button("开始测试", key="supabase_test_btn"):
            ok, msg = test_supabase_connection()
            st.session_state.supabase_test_ok = ok
            st.session_state.supabase_test_msg = msg
        if "supabase_test_msg" in st.session_state:
            if st.session_state.get("supabase_test_ok"):
                st.success(st.session_state.supabase_test_msg)
            else:
                st.error(st.session_state.supabase_test_msg)
        st.markdown("#### 账号自检")
        check_user = st.text_input("要检查的用户名", key="supabase_check_user")
        if st.button("查询账号", key="supabase_check_btn"):
            info = db_get_user(check_user.strip()) if check_user.strip() else None
            st.session_state.supabase_check_result = info is not None
        if "supabase_check_result" in st.session_state:
            if st.session_state.supabase_check_result:
                st.success("该账号在 Supabase 中存在")
            else:
                st.error("未找到该账号（或当前连接失败）")
        st.markdown("#### 管理员重置密码")
        admin_code = st.secrets.get("ADMIN_CODE")
        if not admin_code:
            st.info("未配置 ADMIN_CODE，无法进行管理员重置")
        else:
            with st.form("admin_reset_form"):
                reset_user = st.text_input("要重置的用户名", key="admin_reset_user")
                reset_pass = st.text_input("新密码", type="password", key="admin_reset_pass")
                admin_input = st.text_input("管理员口令", type="password", key="admin_reset_code")
                submitted = st.form_submit_button("重置密码")
                if submitted:
                    if admin_input != admin_code:
                        st.error("管理员口令错误")
                    elif not reset_user.strip() or len(reset_pass) < 6:
                        st.error("用户名不能为空，且密码至少 6 位")
                    else:
                        if storage_mode == "supabase":
                            ok = db_update_user_password(reset_user.strip(), reset_pass)
                        else:
                            ok = local_update_user_password(reset_user.strip(), reset_pass)
                        if ok:
                            st.success("密码已重置")
                        else:
                            st.error("重置失败：账号不存在或连接异常")

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

header_cols = st.columns([2, 2, 2])
with header_cols[0]:
    st.markdown("<div class='title'>My Diary</div>", unsafe_allow_html=True)
with header_cols[1]:
    bjt_time = now_local().strftime("%H:%M")
    st.markdown(
        f"<div style='text-align:center; font-size:20px; color:#1F3B57; font-weight:700;'>北京时间 {bjt_time}</div>",
        unsafe_allow_html=True,
    )
st.markdown("<div class='subtitle'>打造属于自我的舒适之家</div>", unsafe_allow_html=True)
try:
    _build_stamp = datetime.fromtimestamp(os.path.getmtime(__file__)).strftime("%Y-%m-%d %H:%M")
    st.caption(f"版本 3.0 · 更新于：{_build_stamp}")
except Exception:
    pass

today_key = today_local().strftime("%Y-%m-%d")
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


PAGES = ["本周计划", "习惯养成", "番茄钟", "心情", "单词学习", "统计", "树洞"]
if "page" not in st.session_state:
    st.session_state.page = "本周计划"
if st.session_state.page not in PAGES:
    st.session_state.page = "本周计划"
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
    st.session_state.event_date = today_local()
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
if "selected_habit_id" not in st.session_state:
    st.session_state.selected_habit_id = None
if "habit_delete_confirm" not in st.session_state:
    st.session_state.habit_delete_confirm = False
if "forum_edit_post_id" not in st.session_state:
    st.session_state.forum_edit_post_id = None
if "forum_edit_comment_id" not in st.session_state:
    st.session_state.forum_edit_comment_id = None
if "forum_delete_post_id" not in st.session_state:
    st.session_state.forum_delete_post_id = None
if "forum_delete_comment_id" not in st.session_state:
    st.session_state.forum_delete_comment_id = None
if "forum_new_post" not in st.session_state:
    st.session_state.forum_new_post = ""
if "forum_post_feedback" not in st.session_state:
    st.session_state.forum_post_feedback = None
if "forum_comment_feedback" not in st.session_state:
    st.session_state.forum_comment_feedback = {}

if "jump_day" in st.query_params:
    jump_value = st.query_params.get("jump_day")
    try:
        jump_day = datetime.strptime(jump_value, "%Y-%m-%d").date()
        st.session_state.pending_page = "本周计划"
        st.session_state.week_pick = jump_day
        st.session_state.week_flash_target = jump_day.strftime("%Y-%m-%d")
        st.session_state.week_flash_step = 0
        st.session_state.week_flash_on = True
        st.query_params.clear()
        safe_rerun()
    except Exception:
        st.query_params.clear()

if st.session_state.page != st.session_state.last_page:
    if st.session_state.page == "本周计划":
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
html, body, .stApp, header, footer,
div[data-testid="stAppViewContainer"],
div[data-testid="stHeader"],
div[data-testid="stToolbar"],
section[data-testid="stSidebar"] ~ main,
section[data-testid="stSidebar"] ~ div { background-color: #1D2430 !important; }
.block-container { background-color: #1D2430 !important; }
section[data-testid="stSidebar"] { background-color: #252D3A; }
.title, .subtitle, .section-title, .stMarkdown, .stCaption,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5, .stMarkdown h6,
.stMarkdown p, .stMarkdown div,
label, .stTextInput label, .stSelectbox label, .stDateInput label,
.stTimeInput label, .stTextArea label { color: #E7EDF7 !important; }
.card, .detail-panel { background: #252D3A; border-color: #3A4A5F; color: #E7EDF7; }
.stButton > button { background: #2A3450; border-color: #3A4A5F; color: #E7EDF7; }
.stButton > button:hover { background: #33405C; }
.month-cell { background: #2A3445; border-color: #3A4A5F; color: #E7EDF7; }
.month-weekday { color: #9FB3C8; }
.event-card, .detail-event-btn .stButton > button { background: #202735; border-color: #3A4A5F; color: #E7EDF7; }
.event-block { color: #1F3B57; }
input, textarea, select { background-color: #202735 !important; color: #E7EDF7 !important; border-color: #3A4A5F !important; }
div[data-testid="stAppViewContainer"] .event-block {
    background: #C7D2E6 !important;
    border-color: #C7D2E6 !important;
    color: #0B0F14 !important;
}
div[data-testid="stAppViewContainer"] .event-block * { color: #0B0F14 !important; }
div[data-testid="stExpander"] > details > summary,
div[data-testid="stExpander"] > details > summary * { color: #E7EDF7 !important; }
div[data-testid="stExpander"] div[data-testid="stMarkdownContainer"],
div[data-testid="stExpander"] .stMarkdown { color: #E7EDF7 !important; }
#theme-toggle-anchor + div .stButton > button { background: #2A3450; border-color: #3A4A5F; color: #E7EDF7; }
#theme-toggle-anchor + div .stButton > button:hover { background: #33405C; }
.stSidebar svg, .stSidebar [data-testid="stSelectbox"] svg,
.stSidebar [data-testid="stDateInput"] svg, .stSidebar [data-testid="stTimeInput"] svg,
.stSidebar [data-testid="stTextInput"] svg, .stSidebar [data-testid="stTextArea"] svg,
main svg, main [data-testid="stSelectbox"] svg, main [data-testid="stDateInput"] svg,
main [data-testid="stTimeInput"] svg, main [data-testid="stTextInput"] svg, main [data-testid="stTextArea"] svg {
    color: #2A3450 !important;
    fill: #2A3450 !important;
    stroke: #2A3450 !important;
}
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
            if name != "本周计划":
                st.session_state.sidebar_collapsed = True
            safe_rerun()

selected_page = st.session_state.page

if not st.session_state.dark_mode:
    page_bg_map = {
        "本周计划": "#EAF2FF",
        "习惯养成": "#EEF9F1",
        "番茄钟": "#FFF3E6",
        "心情": "#F4F0FF",
        "单词学习": "#EAF8FF",
        "统计": "#F8F5E8",
        "树洞": "#FCEFF4",
    }
    page_bg = page_bg_map.get(selected_page, "#EEF5FF")
    st.markdown(
        f"""
<style>
body, .stApp, .block-container,
div[data-testid="stAppViewContainer"],
div[data-testid="stHeader"],
div[data-testid="stToolbar"],
section[data-testid="stSidebar"] ~ main,
section[data-testid="stSidebar"] ~ div {{ background-color: {page_bg} !important; }}
.card, .detail-panel, .event-card, .detail-card, .habit-record,
.week-day-card, .month-cell, .day-timeline {{ background: {page_bg} !important; }}
</style>
""",
        unsafe_allow_html=True,
    )

def _reset_event_form():
    st.session_state.event_title = "新日程"
    st.session_state.event_date = today_local()
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
    today_key = today_local().strftime("%Y-%m-%d")
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
        confirm_cols = st.columns(2)
        with confirm_cols[0]:
            if st.button("确认删除", key="confirm_delete"):
                data["events"] = [e for e in data["events"] if e["id"] != target["id"]]
                persist_data(data)
                if st.session_state.editing_event_id == target["id"]:
                    st.session_state.editing_event_id = None
                    _reset_event_form()
                st.session_state.delete_target_id = None
                safe_rerun()
        with confirm_cols[1]:
            if st.button("取消", key="cancel_delete"):
                st.session_state.delete_target_id = None
                safe_rerun()
    else:
        st.session_state.delete_target_id = None

        pass


if selected_page == "本周计划":
    st.markdown("<div class='section-title'>本周计划</div>", unsafe_allow_html=True)
    picked = st.date_input("选择周中的任意日期", value=today_local(), key="week_pick")
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
                    st.session_state.sidebar_collapsed = False
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
                            st.session_state.sidebar_collapsed = False
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



if selected_page == "心情":
    st.markdown("<div class='section-title'>心情</div>", unsafe_allow_html=True)
    today = today_local()
    year_options = list(range(today.year - 2, today.year + 3))
    month_options = list(range(1, 13))
    month_cols = st.columns(2)
    with month_cols[0]:
        pick_year = st.selectbox("选择年份", year_options, index=year_options.index(today.year), key="month_pick_year")
    with month_cols[1]:
        pick_month = st.selectbox("选择月份", month_options, index=month_options.index(today.month), key="month_pick_month")
    m_start = date(pick_year, pick_month, 1)
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

if selected_page == "习惯养成":
    st.markdown("<div class='section-title'>习惯养成·21天打卡</div>", unsafe_allow_html=True)

    def _count_habit_days(habit: dict) -> int:
        return sum(1 for r in habit.get("records", []) if r.get("completed"))

    def _ensure_habit_completed(habit: dict) -> bool:
        if habit.get("completed"):
            return False
        if _count_habit_days(habit) >= 21:
            habit["completed"] = True
            return True
        return False

    habits = data.get("habits", [])

    if st.session_state.selected_habit_id is None:
        with st.popover("➕ 新建习惯"):
            with st.form("new_habit_form", clear_on_submit=True):
                habit_name = st.text_input("习惯名称")
                submitted = st.form_submit_button("创建")
                if submitted:
                    if not habit_name.strip():
                        st.error("习惯名称不能为空")
                    else:
                        habits.append({
                            "id": str(uuid.uuid4()),
                            "name": habit_name.strip(),
                            "created": today_local().isoformat(),
                            "completed": False,
                            "records": [],
                        })
                        data["habits"] = habits
                        persist_data(data)
                        st.success("已创建习惯")
                        safe_rerun()

        if not habits:
            st.info("还没有习惯，先新建一个吧")
        else:
            updated = False
            for habit in habits:
                if _ensure_habit_completed(habit):
                    updated = True
            if updated:
                persist_data(data)

            cols = st.columns(2)
            for idx, habit in enumerate(habits):
                col = cols[idx % 2]
                days_done = _count_habit_days(habit)
                last_date = ""
                if habit.get("records"):
                    last_date = sorted(habit["records"], key=lambda x: x.get("date", ""))[-1].get("date", "")
                status_text = "✅ 已完成" if habit.get("completed") else ""
                label_lines = [habit.get("name", "未命名"), f"第 {days_done} 天 / 21 天"]
                if last_date:
                    label_lines.append(f"最近打卡：{last_date}")
                if status_text:
                    label_lines.append(status_text)
                card_label = "\n".join(label_lines)
                card_class = "habit-card complete" if habit.get("completed") else "habit-card"
                with col:
                    st.markdown(f"<div class='{card_class}'>", unsafe_allow_html=True)
                    if st.button(card_label, key=f"habit_{habit['id']}", use_container_width=True):
                        st.session_state.selected_habit_id = habit["id"]
                        safe_rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
    else:
        selected = next((h for h in habits if h.get("id") == st.session_state.selected_habit_id), None)
        if not selected:
            st.session_state.selected_habit_id = None
            st.session_state.habit_delete_confirm = False
            safe_rerun()

        if st.button("← 返回习惯列表", key="back_habit_list"):
            st.session_state.selected_habit_id = None
            st.session_state.habit_delete_confirm = False
            safe_rerun()

        st.markdown(f"### {selected.get('name', '未命名')}")
        delete_cols = st.columns([1, 5])
        with delete_cols[0]:
            if st.button("删除习惯", key="delete_habit"):
                st.session_state.habit_delete_confirm = True
        if st.session_state.habit_delete_confirm:
            confirm_cols = st.columns(2)
            with confirm_cols[0]:
                if st.button("确认删除", key="confirm_delete_habit"):
                    data["habits"] = [h for h in habits if h.get("id") != selected.get("id")]
                    persist_data(data)
                    st.session_state.selected_habit_id = None
                    st.session_state.habit_delete_confirm = False
                    st.success("已删除习惯")
                    safe_rerun()
            with confirm_cols[1]:
                if st.button("取消", key="cancel_delete_habit"):
                    st.session_state.habit_delete_confirm = False
        today = today_local().isoformat()
        today_display = today_local().strftime("%Y年%m月%d日")
        records = selected.get("records", [])
        updated = _ensure_habit_completed(selected)
        if updated:
            persist_data(data)

        if selected.get("completed"):
            st.success("恭喜！该习惯已养成")
        else:
            st.markdown(f"**今日：{today_display}**")
            already = next((r for r in records if r.get("date") == today), None)
            done_today = bool(already and already.get("completed"))
            note_today = already.get("note", "") if already else ""
            done_flag = st.checkbox("今天完成了吗？", value=done_today, disabled=already is not None)
            note_text = st.text_input("留下一句话…", value=note_today, disabled=already is not None)
            if st.button("提交打卡", key="submit_habit", disabled=already is not None):
                if already is not None:
                    st.warning("今天已经打卡过了")
                else:
                    records.append({"date": today, "completed": bool(done_flag), "note": note_text.strip()})
                    selected["records"] = records
                    if _ensure_habit_completed(selected):
                        selected["completed"] = True
                    persist_data(data)
                    st.toast("打卡成功")
                    safe_rerun()

        st.markdown("#### 历史打卡记录")
        if not records:
            st.info("暂无打卡记录")
        else:
            for idx, rec in enumerate(sorted(records, key=lambda x: x.get("date", ""), reverse=True)):
                bg = "#F7FAFF" if idx % 2 == 0 else "#FFFFFF"
                status = "✅" if rec.get("completed") else "❌"
                note = rec.get("note", "").strip()
                note_text = f"“{note}”" if note else "—"
                st.markdown(
                    f"<div class='habit-record' style='background:{bg};'>"
                    f"<strong>{rec.get('date', '')}</strong> {status} {note_text}"
                    "</div>",
                    unsafe_allow_html=True,
                )

def _set_forum_post_feedback(level: str, message: str) -> None:
    st.session_state.forum_post_feedback = {"level": level, "message": message}


def _consume_forum_post_feedback() -> None:
    payload = st.session_state.pop("forum_post_feedback", None)
    if not payload:
        return
    level = payload.get("level", "info")
    message = payload.get("message", "")
    if not message:
        return
    if level == "success":
        st.success(message)
    elif level == "warning":
        st.warning(message)
    elif level == "error":
        st.error(message)
    else:
        st.info(message)


def _set_forum_comment_feedback(post_id: str, level: str, message: str) -> None:
    feedback = st.session_state.get("forum_comment_feedback") or {}
    feedback[post_id] = {"level": level, "message": message}
    st.session_state.forum_comment_feedback = feedback


def _consume_forum_comment_feedback(post_id: str) -> None:
    feedback = st.session_state.get("forum_comment_feedback") or {}
    payload = feedback.pop(post_id, None)
    st.session_state.forum_comment_feedback = feedback
    if not payload:
        return
    level = payload.get("level", "info")
    message = payload.get("message", "")
    if not message:
        return
    if level == "success":
        st.success(message)
    elif level == "warning":
        st.warning(message)
    elif level == "error":
        st.error(message)
    else:
        st.info(message)


def _submit_forum_post(storage_mode: str, data_ref: dict, user_id: str, username: str) -> None:
    content = st.session_state.get("forum_new_post", "").strip()
    if not content:
        _set_forum_post_feedback("warning", "内容不能为空")
        return
    if forum_create_post(storage_mode, content, user_id, username, data_ref):
        if storage_mode != "supabase":
            persist_data(data_ref)
        st.session_state.forum_new_post = ""
        _set_forum_post_feedback("success", "已发布")
    else:
        _set_forum_post_feedback("error", "发布失败，请稍后再试")


def _submit_forum_comment(
    post_id: str,
    comment_key: str,
    storage_mode: str,
    data_ref: dict,
    user_id: str,
    username: str,
) -> None:
    content = st.session_state.get(comment_key, "").strip()
    if not content:
        _set_forum_comment_feedback(post_id, "warning", "评论不能为空")
        return
    if forum_create_comment(storage_mode, post_id, content, user_id, username, data_ref):
        if storage_mode != "supabase":
            persist_data(data_ref)
        st.session_state[comment_key] = ""
        _set_forum_comment_feedback(post_id, "success", "评论已发布")
    else:
        _set_forum_comment_feedback(post_id, "error", "评论失败，请稍后再试")

if selected_page == "树洞":
    st.markdown("<div class='section-title'>树洞</div>", unsafe_allow_html=True)
    st.caption("聊聊最近的事情？")

    current_user = st.session_state.user
    current_user_id = st.session_state.get("user_id") or current_user

    st.markdown("#### 发布新帖")
    st.text_area("内容", key="forum_new_post", height=120)
    st.button(
        "发布",
        key="forum_submit_post",
        on_click=_submit_forum_post,
        args=(storage_mode, data, current_user_id, current_user),
    )
    _consume_forum_post_feedback()

    st.markdown("#### 最新帖子")
    posts = forum_list_posts(storage_mode, data)
    if not posts:
        st.info("暂无帖子")
    else:
        for post in posts:
            author = post.get("username") or "匿名"
            created = _format_timestamp(_normalize_timestamp(post.get("created_at")))
            updated = _format_timestamp(_normalize_timestamp(post.get("updated_at")))
            label = f"{author} · {created} · {_forum_snippet(post.get('content', ''))}"
            with st.expander(label, expanded=False):
                deleted = bool(post.get("deleted"))
                if deleted:
                    st.info("该帖子已被删除")
                else:
                    if st.session_state.forum_edit_post_id == post.get("id"):
                        edit_key = f"forum_edit_post_{post['id']}"
                        st.text_area("编辑内容", value=post.get("content", ""), key=edit_key, height=120)
                        edit_cols = st.columns(2)
                        with edit_cols[0]:
                            if st.button("保存修改", key=f"forum_save_post_{post['id']}"):
                                new_text = st.session_state.get(edit_key, "").strip()
                                if not new_text:
                                    st.warning("内容不能为空")
                                else:
                                    if forum_update_post(storage_mode, post["id"], new_text, data):
                                        if storage_mode != "supabase":
                                            persist_data(data)
                                        st.session_state.forum_edit_post_id = None
                                        st.success("已更新")
                                        safe_rerun()
                                    else:
                                        st.error("更新失败")
                        with edit_cols[1]:
                            if st.button("取消", key=f"forum_cancel_post_{post['id']}"):
                                st.session_state.forum_edit_post_id = None
                                safe_rerun()
                    else:
                        st.write(post.get("content", ""))
                        if updated:
                            st.caption(f"编辑于 {updated}")

                    if post.get("user_id") == current_user_id:
                        action_cols = st.columns(2)
                        with action_cols[0]:
                            if st.button("编辑", key=f"forum_edit_post_btn_{post['id']}"):
                                st.session_state.forum_edit_post_id = post["id"]
                                safe_rerun()
                        with action_cols[1]:
                            if st.button("删除", key=f"forum_del_post_btn_{post['id']}"):
                                st.session_state.forum_delete_post_id = post["id"]
                                safe_rerun()

                if st.session_state.forum_delete_post_id == post.get("id"):
                    st.warning("确认删除该帖子？")
                    confirm_cols = st.columns(2)
                    with confirm_cols[0]:
                        if st.button("确认删除", key=f"forum_confirm_del_post_{post['id']}"):
                            if forum_delete_post(storage_mode, post["id"], data):
                                if storage_mode != "supabase":
                                    persist_data(data)
                                st.session_state.forum_delete_post_id = None
                                st.success("已删除")
                                safe_rerun()
                            else:
                                st.error("删除失败")
                    with confirm_cols[1]:
                        if st.button("取消", key=f"forum_cancel_del_post_{post['id']}"):
                            st.session_state.forum_delete_post_id = None
                            safe_rerun()

                st.markdown("##### 评论")
                comments = forum_list_comments(storage_mode, post["id"], data)
                _consume_forum_comment_feedback(post["id"])
                if not comments:
                    st.caption("暂无评论")
                else:
                    for comment in comments:
                        c_author = comment.get("username") or "匿名"
                        c_created = _format_timestamp(_normalize_timestamp(comment.get("created_at")))
                        c_updated = _format_timestamp(_normalize_timestamp(comment.get("updated_at")))
                        if comment.get("deleted"):
                            st.caption(f"{c_author} · {c_created} · 评论已删除")
                            continue

                        if st.session_state.forum_edit_comment_id == comment.get("id"):
                            edit_key = f"forum_edit_comment_{comment['id']}"
                            st.text_area(
                                f"编辑评论 · {c_author} {c_created}",
                                value=comment.get("content", ""),
                                key=edit_key,
                                height=80,
                            )
                            edit_cols = st.columns(2)
                            with edit_cols[0]:
                                if st.button("保存", key=f"forum_save_comment_{comment['id']}"):
                                    new_text = st.session_state.get(edit_key, "").strip()
                                    if not new_text:
                                        st.warning("内容不能为空")
                                    else:
                                        if forum_update_comment(storage_mode, comment["id"], new_text, data):
                                            if storage_mode != "supabase":
                                                persist_data(data)
                                            st.session_state.forum_edit_comment_id = None
                                            st.success("已更新")
                                            safe_rerun()
                                        else:
                                            st.error("更新失败")
                            with edit_cols[1]:
                                if st.button("取消", key=f"forum_cancel_comment_{comment['id']}"):
                                    st.session_state.forum_edit_comment_id = None
                                    safe_rerun()
                        else:
                            st.markdown(f"**{c_author}** · {c_created}")
                            st.write(comment.get("content", ""))
                            if c_updated:
                                st.caption(f"编辑于 {c_updated}")

                            if comment.get("user_id") == current_user_id:
                                action_cols = st.columns(2)
                                with action_cols[0]:
                                    if st.button("编辑", key=f"forum_edit_comment_btn_{comment['id']}"):
                                        st.session_state.forum_edit_comment_id = comment["id"]
                                        safe_rerun()
                                with action_cols[1]:
                                    if st.button("删除", key=f"forum_del_comment_btn_{comment['id']}"):
                                        st.session_state.forum_delete_comment_id = comment["id"]
                                        safe_rerun()

                        if st.session_state.forum_delete_comment_id == comment.get("id"):
                            st.warning("确认删除该评论？")
                            confirm_cols = st.columns(2)
                            with confirm_cols[0]:
                                if st.button("确认删除", key=f"forum_confirm_del_comment_{comment['id']}"):
                                    if forum_delete_comment(storage_mode, comment["id"], data):
                                        if storage_mode != "supabase":
                                            persist_data(data)
                                        st.session_state.forum_delete_comment_id = None
                                        st.success("已删除")
                                        safe_rerun()
                                    else:
                                        st.error("删除失败")
                            with confirm_cols[1]:
                                if st.button("取消", key=f"forum_cancel_del_comment_{comment['id']}"):
                                    st.session_state.forum_delete_comment_id = None
                                    safe_rerun()

                if not deleted:
                    comment_key = f"forum_comment_{post['id']}"
                    st.text_area("写评论", key=comment_key, height=80)
                    st.button(
                        "发表评论",
                        key=f"forum_submit_comment_{post['id']}",
                        on_click=_submit_forum_comment,
                        args=(post["id"], comment_key, storage_mode, data, current_user_id, current_user),
                    )

footer_label = "深色模式" if not st.session_state.dark_mode else "浅色模式"
st.markdown("<div id='theme-toggle-anchor'></div>", unsafe_allow_html=True)
if st.button(footer_label, key="toggle_theme"):
    st.session_state.dark_mode = not st.session_state.dark_mode
    safe_rerun()

if selected_page == "番茄钟":
    st.markdown("<div class='section-title'>番茄钟</div>", unsafe_allow_html=True)
    left, right = st.columns([1, 2])

    with left:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        if not data["pomodoro_records"]:
            st.caption("暂无记录")
        record_indices = list(range(len(data["pomodoro_records"])))
        for idx in record_indices[-50:][::-1]:
            rec = data["pomodoro_records"][idx]
            row_cols = st.columns([6, 1])
            with row_cols[0]:
                st.write(f"{rec['start']}  {format_seconds(rec['seconds'])}")
            with row_cols[1]:
                if st.button("删除", key=f"pomodoro_delete_{idx}"):
                    data["pomodoro_records"].pop(idx)
                    persist_data(data)
                    safe_rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        if "pomodoro_running" not in st.session_state:
            state = data.get("pomodoro_state") or {}
            st.session_state.pomodoro_running = bool(state.get("running"))
            st.session_state.pomodoro_start = state.get("start")
            st.session_state.pomodoro_duration = int(state.get("duration") or 0)

        remaining = 0
        if st.session_state.pomodoro_running:
            start_ts = st.session_state.pomodoro_start
            duration = int(st.session_state.pomodoro_duration or 0)
            if not start_ts or duration <= 0:
                st.session_state.pomodoro_running = False
                st.session_state.pomodoro_start = None
                st.session_state.pomodoro_duration = 0
                data["pomodoro_state"] = {"running": False, "start": None, "duration": 0}
                persist_data(data)
            else:
                elapsed = int(time.time() - start_ts)
                remaining = max(0, duration - elapsed)
                if remaining == 0:
                    rec = {
                        "start": now_local().strftime("%Y-%m-%d %H:%M:%S"),
                        "seconds": duration,
                    }
                    data["pomodoro_records"].append(rec)
                    data["pomodoro_state"] = {"running": False, "start": None, "duration": 0}
                    persist_data(data)
                    st.session_state.pomodoro_running = False
                    st.session_state.pomodoro_start = None
                    st.session_state.pomodoro_duration = 0

        total_seconds = sum(r.get("seconds", 0) for r in data["pomodoro_records"])
        if st.session_state.pomodoro_running and st.session_state.pomodoro_start:
            elapsed = int(time.time() - st.session_state.pomodoro_start)
            elapsed = max(0, min(elapsed, int(st.session_state.pomodoro_duration or 0)))
            total_seconds += elapsed
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        st.markdown(f"<div class='focus-text'>你已专注了{h}小时{m}分钟</div>", unsafe_allow_html=True)

        st.markdown(f"<div class='timer-text'>{format_seconds(remaining)}</div>", unsafe_allow_html=True)

        preset_rows = [st.columns(3) for _ in range(3)]
        presets = [
            (120, "120:00"),
            (90, "90:00"),
            (60, "60:00"),
            (45, "45:00"),
            (30, "30:00"),
            (15, "15:00"),
            (10, "10:00"),
            (5, "05:00"),
            (1, "01:00"),
        ]
        for i, (mins, label) in enumerate(presets):
            row = preset_rows[i // 3]
            with row[i % 3]:
                if st.button(label, key=f"preset_{mins}"):
                    st.session_state.pomodoro_running = True
                    start_ts = time.time()
                    st.session_state.pomodoro_start = start_ts
                    st.session_state.pomodoro_duration = mins * 60
                    data["pomodoro_state"] = {
                        "running": True,
                        "start": start_ts,
                        "duration": mins * 60,
                    }
                    persist_data(data)
                    safe_rerun()

        if st.button("取消"):
            if st.session_state.pomodoro_running:
                elapsed = int(time.time() - st.session_state.pomodoro_start)
                if elapsed >= int(st.session_state.pomodoro_duration * 0.8):
                    rec = {
                        "start": now_local().strftime("%Y-%m-%d %H:%M:%S"),
                        "seconds": st.session_state.pomodoro_duration,
                    }
                    data["pomodoro_records"].append(rec)
                data["pomodoro_state"] = {"running": False, "start": None, "duration": 0}
                persist_data(data)
            st.session_state.pomodoro_running = False
            st.session_state.pomodoro_start = None
            st.session_state.pomodoro_duration = 0
            safe_rerun()

        if st.session_state.pomodoro_running and remaining > 0:
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
        a_date = st.date_input("日期", value=today_local(), key="archive_date")
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