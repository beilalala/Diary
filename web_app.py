import streamlit as st
import json
import os
import uuid
import time
import math
import hashlib
from datetime import datetime, date, timedelta
import plotly.graph_objects as go


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
USER_DATA_DIR = os.path.join(DATA_DIR, "users")

CATEGORIES = ["生活", "学习", "班团事务", "运动", "其他"]
CATEGORY_COLORS = {
    "生活": "#CFE8FF",
    "学习": "#DFF2D8",
    "班团事务": "#FFE6CC",
    "运动": "#D9F5D6",
    "其他": "#E8E0FF",
}

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


def ensure_data_file(file_path: str):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({"events": [], "archives": [], "moods": {}, "pomodoro_records": []}, f, ensure_ascii=False, indent=2)


def load_data(file_path: str):
    ensure_data_file(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("events", [])
    data.setdefault("archives", [])
    data.setdefault("moods", {})
    data.setdefault("pomodoro_records", [])
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
.event-card { background: #FFFFFF; border-radius: 10px; padding: 8px 10px; margin: 6px 0; border: 1px solid #E2EAF5; font-size: 14px; }
.event-time { font-weight: 700; color: #1F3B57; margin-right: 6px; }
.stButton > button { width: 100%; border: 1px solid #C9DBF2; border-radius: 10px; padding: 10px 8px; background: #F7FAFF; color: #1F3B57; }
.stButton > button:hover { border-color: #9CB4E0; background: #EEF5FF; }
.day-timeline { position: relative; height: 640px; border: 1px solid #E2EAF5; border-radius: 12px; background: #FFFFFF; background-image: repeating-linear-gradient(to bottom, #EEF2F7 0, #EEF2F7 1px, transparent 1px, transparent 40px); }
.event-block { position: absolute; padding: 6px 8px; border-radius: 10px; border: 1px solid transparent; font-size: 12px; color: #1F3B57; overflow: hidden; }
.event-block-time { font-weight: 700; }
</style>
""",
    unsafe_allow_html=True,
)

if "user" not in st.session_state:
    st.markdown("<div class='title'>My Diary</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle'>打造属于自我的舒适之家</div>", unsafe_allow_html=True)

    login_tab, register_tab = st.tabs(["登录", "注册"])

    with login_tab:
        st.markdown("#### 登录")
        login_user = st.text_input("用户名", key="login_user")
        login_pass = st.text_input("密码", type="password", key="login_pass")
        if st.button("登录", key="login_btn"):
            users = load_users()
            info = users.get(login_user)
            if not info:
                st.error("用户不存在")
            else:
                if verify_password(login_pass, info["salt"], info["hash"]):
                    st.session_state.user = login_user
                    st.experimental_rerun()
                else:
                    st.error("密码错误")

    with register_tab:
        st.markdown("#### 注册")
        reg_user = st.text_input("用户名", key="reg_user")
        reg_pass = st.text_input("密码", type="password", key="reg_pass")
        reg_pass2 = st.text_input("确认密码", type="password", key="reg_pass2")
        if st.button("注册", key="reg_btn"):
            users = load_users()
            if not reg_user.strip():
                st.error("请输入用户名")
            elif reg_user in users:
                st.error("用户名已存在")
            elif len(reg_pass) < 6:
                st.error("密码至少 6 位")
            elif reg_pass != reg_pass2:
                st.error("两次密码不一致")
            else:
                salt = uuid.uuid4().hex
                users[reg_user] = {"salt": salt, "hash": hash_password(reg_pass, salt)}
                save_users(users)
                user_file = os.path.join(USER_DATA_DIR, f"{reg_user}.json")
                ensure_data_file(user_file)
                st.success("注册成功，请登录")
    st.stop()

user_data_file = os.path.join(USER_DATA_DIR, f"{st.session_state.user}.json")
data = load_data(user_data_file)

st.markdown("<div class='title'>My Diary</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>打造属于自我的舒适之家</div>", unsafe_allow_html=True)

today_key = date.today().strftime("%Y-%m-%d")
if not data["moods"].get(today_key) and not st.session_state.get("mood_skipped"):
    st.markdown("<div class='section-title'>欢迎回家，今天的心情怎样？</div>", unsafe_allow_html=True)
    cols = st.columns(8)
    for i, mood in enumerate(MOODS):
        with cols[i % 8]:
            if st.button(mood, key=f"mood_{i}"):
                emoji = mood.split(" ")[-1]
                data["moods"][today_key] = emoji
                save_data(data, user_data_file)
                st.experimental_rerun()
    if st.button("跳过"):
        st.session_state.mood_skipped = True
        st.experimental_rerun()
    st.stop()


PAGES = ["周视图", "月视图", "番茄钟", "统计", "往期回顾"]
if "page" not in st.session_state:
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
if "last_page" not in st.session_state:
    st.session_state.last_page = st.session_state.page

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

nav_cols = st.columns(len(PAGES))
for i, name in enumerate(PAGES):
    with nav_cols[i]:
        btn_type = "primary" if st.session_state.page == name else "secondary"
        if st.button(name, key=f"nav_{name}", type=btn_type):
            st.session_state.page = name
            if name != "周视图":
                st.session_state.sidebar_collapsed = True
            st.experimental_rerun()

selected_page = st.session_state.page

if not st.session_state.sidebar_collapsed:
    with st.sidebar:
        close_row = st.columns([8, 1])
        with close_row[1]:
            if st.button("×", key="collapse_sidebar"):
                st.session_state.sidebar_collapsed = True
                st.experimental_rerun()
        st.markdown("### 添加日程")
        with st.form("add_event"):
            t = st.text_input("名称", value="新日程")
            d = st.date_input("日期", value=date.today())
            start = st.time_input("开始时间", value=datetime.strptime("09:00", "%H:%M").time())
            end = st.time_input("结束时间", value=datetime.strptime("10:00", "%H:%M").time())
            cat = st.selectbox("类型", CATEGORIES)
            notes = st.text_area("备注（可选）")
            submitted = st.form_submit_button("保存")
            if submitted:
                new = {
                    "id": str(uuid.uuid4()),
                    "title": t.strip() or "未命名",
                    "date": d.strftime("%Y-%m-%d"),
                    "start": start.strftime("%H:%M"),
                    "end": end.strftime("%H:%M"),
                    "category": cat,
                    "notes": notes.strip(),
                }
                data["events"].append(new)
                save_data(data, user_data_file)
                st.success("已保存")


if selected_page == "周视图":
    st.markdown("<div class='section-title'>周视图</div>", unsafe_allow_html=True)
    picked = st.date_input("选择周中的任意日期", value=date.today(), key="week_pick")
    week_start = iso_week_start(picked)
    st.markdown(f"**周：{week_start.strftime('%Y/%m/%d')} - {(week_start + timedelta(days=6)).strftime('%Y/%m/%d')}**")

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
            card_class = "week-day-card flash-on" if is_flash else "week-day-card"
            st.markdown(
                f"<div class='{card_class}'>"
                f"<div><strong>{d.strftime('%a')}</strong> {d.strftime('%m/%d')}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if not events:
                st.caption("无日程")
            else:
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
        st.experimental_rerun()
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

    for row in range(6):
        cols = st.columns(7)
        for col in range(7):
            slot = row * 7 + col
            with cols[col]:
                if slot < start_offset or day_cursor > days_in_month:
                    st.write(" ")
                    continue
                current = m_start.replace(day=day_cursor)
                mood = data["moods"].get(current.strftime("%Y-%m-%d"), "")
                label = f"{day_cursor} {mood}" if mood else f"{day_cursor}"
                clicked = st.button(label, key=f"month_day_{current.strftime('%Y%m%d')}", use_container_width=True)
                if clicked:
                    st.session_state.pending_page = "周视图"
                    st.session_state.week_pick = current
                    st.session_state.week_flash_target = current.strftime("%Y-%m-%d")
                    st.session_state.week_flash_step = 0
                    st.session_state.week_flash_on = True
                    st.experimental_rerun()
                day_cursor += 1

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
                    st.experimental_rerun()

        if st.button("取消"):
            if st.session_state.pomodoro_running:
                elapsed = int(time.time() - st.session_state.pomodoro_start)
                if elapsed >= int(st.session_state.pomodoro_duration * 0.8):
                    rec = {
                        "start": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "seconds": st.session_state.pomodoro_duration,
                    }
                    data["pomodoro_records"].append(rec)
                    save_data(data, user_data_file)
            st.session_state.pomodoro_running = False
            st.session_state.pomodoro_start = None
            st.session_state.pomodoro_duration = 0
            st.experimental_rerun()

        if st.session_state.pomodoro_running:
            if remaining <= 0:
                rec = {
                    "start": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "seconds": st.session_state.pomodoro_duration,
                }
                data["pomodoro_records"].append(rec)
                save_data(data, user_data_file)
                st.session_state.pomodoro_running = False
                st.session_state.pomodoro_start = None
                st.session_state.pomodoro_duration = 0
                st.experimental_rerun()
            else:
                time.sleep(1)
                st.experimental_rerun()

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
            save_data(data, user_data_file)
            st.success("已保存")

    for item in sorted(data.get("archives", []), key=lambda x: x["date"], reverse=True):
        with st.expander(f"{item['date']} · {item.get('category', '-')}"):
            st.write(item.get("text", ""))
            if st.button("删除", key=f"del_arc_{item['id']}"):
                data["archives"] = [a for a in data["archives"] if a["id"] != item["id"]]
                save_data(data, user_data_file)
                st.experimental_rerun()