import streamlit as st
import json
import os
import uuid
from datetime import datetime, date, timedelta


def require_password():
    password = st.secrets.get("APP_PASSWORD", "")
    if "password_ok" not in st.session_state:
        st.session_state.password_ok = False

    if st.session_state.password_ok:
        return

    st.title("轻量日程管理 — 访问验证")
    st.text_input("请输入访问密码", type="password", key="password_input")
    if st.button("进入"):
        if st.session_state.password_input == password and password:
            st.session_state.password_ok = True
            st.experimental_rerun()
        else:
            st.error("密码错误")
    st.stop()

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATA_FILE = os.path.join(DATA_DIR, "storage.json")

CATEGORIES = ["生活", "学习", "班团事务", "其他"]
CATEGORY_COLORS = {
    "生活": "#CFE8FF",
    "学习": "#DFF2D8",
    "班团事务": "#FFE6CC",
    "其他": "#E8E0FF",
}

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"events": [], "archives": []}, f, ensure_ascii=False, indent=2)


def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def iso_week_start(d: date):
    return d - timedelta(days=d.weekday())


st.set_page_config(page_title="轻量日程管理（Web）", layout="wide")
require_password()

st.title("轻量日程管理 — Web 版（示例）")

data = load_data()

col1, col2 = st.columns([3, 1])

with col1:
    view = st.radio("视图", ["周视图", "月视图"], index=0, horizontal=True)

    if view == "周视图":
        picked = st.date_input("选择周中的任意日期", value=date.today())
        week_start = iso_week_start(picked)
        st.subheader(f"周：{week_start.strftime('%Y/%m/%d')} - {(week_start + timedelta(days=6)).strftime('%Y/%m/%d')}")

        for i in range(7):
            d = week_start + timedelta(days=i)
            st.markdown(f"### {d.strftime('%a %Y-%m-%d')}")
            events = [e for e in data["events"] if e["date"] == d.strftime("%Y-%m-%d")]
            if not events:
                st.write("无日程")
            else:
                for ev in sorted(events, key=lambda x: x["start"]):
                    c = CATEGORY_COLORS.get(ev.get("category", "其他"), "#EEE")
                    st.markdown(f"<div style='background:{c};padding:8px;border-radius:6px'>**{ev['start']}-{ev['end']}**  {ev['title']}</div>", unsafe_allow_html=True)

    else:
        curr = st.date_input("选择月（选择任意当月日期）", value=date.today())
        month_start = curr.replace(day=1)
        st.subheader(f"{month_start.strftime('%Y年 %m月')}")
        days_in_month = (month_start.replace(month=month_start.month % 12 + 1, day=1) - timedelta(days=1)).day
        for day in range(1, days_in_month + 1):
            d = month_start.replace(day=day)
            events = [e for e in data["events"] if e["date"] == d.strftime("%Y-%m-%d")]
            if events:
                st.markdown(f"**{d.day}日** — {len(events)} 项")
                for ev in events[:3]:
                    c = CATEGORY_COLORS.get(ev.get("category", "其他"), "#EEE")
                    st.markdown(f"<div style='background:{c};padding:6px;border-radius:4px'>{ev['start']}-{ev['end']} {ev['title']}</div>", unsafe_allow_html=True)

with col2:
    st.sidebar.title("添加日程")
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
            save_data(data)
            st.success("已保存，向下刷新以查看")

st.markdown("---")

st.subheader("管理现有日程")

for ev in sorted(data.get("events", []), key=lambda x: (x["date"], x["start"])):
    c = CATEGORY_COLORS.get(ev.get("category", "其他"), "#EEE")
    cols = st.columns([6, 1, 1])
    with cols[0]:
        st.markdown(f"<div style='background:{c};padding:8px;border-radius:6px'>{ev['date']} {ev['start']}-{ev['end']} — **{ev['title']}**</div>", unsafe_allow_html=True)
    with cols[1]:
        if st.button("删除", key=f"del_{ev['id']}"):
            data["events"] = [x for x in data["events"] if x["id"] != ev["id"]]
            save_data(data)
            st.experimental_rerun()
    with cols[2]:
        st.write(ev.get("category", "-"))

st.markdown("---")
st.caption("说明：此为示例 Web 版，保存在本地 `data/storage.json`，部署到云端前请考虑隐私与存储方式。欢迎提出功能扩展需求，我可继续完善并协助部署。")