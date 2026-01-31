import json
import os
import uuid
import math
import random
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog

APP_TITLE = "王俊腾的家"
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATA_FILE = os.path.join(DATA_DIR, "storage.json")

CATEGORIES = ["生活", "学习", "班团事务", "运动", "其他"]
CATEGORY_COLORS = {
    "生活": "#CFE8FF",
    "学习": "#DFF2D8",
    "班团事务": "#FFE6CC",
    "运动": "#D9F5D6",
    "其他": "#E8E0FF",
}

APP_BG = "#EEF5FF"
BUTTON_BG = "#D6EBFF"
BUTTON_BG_ACTIVE = "#C5E2FF"
BUTTON_BG_PRESSED = "#B6D8FF"
TAB_BG = "#B9D7FF"
TAB_BG_ACTIVE = "#A9CFFF"
TAB_BG_SELECTED = "#95C2FF"

THEMES = {
    "light": {
        "app_bg": "#EEF5FF",
        "panel_bg": "#E3EFFF",
        "fg": "#1F3B57",
        "button_bg": "#D6EBFF",
        "button_bg_active": "#C5E2FF",
        "button_bg_pressed": "#B6D8FF",
        "tab_bg": "#B9D7FF",
        "tab_bg_active": "#A9CFFF",
        "tab_bg_selected": "#95C2FF",
        "canvas_bg": "#FFFFFF",
        "grid_line": "#EFEFEF",
        "highlight": "#DADADA",
        "scroll_trough": "#EAF2FF",
        "scroll_thumb": "#C6DEFF",
        "list_bg": "#FFFFFF",
        "tree_alt": "#F6FAFF",
        "month_date_bg": "#F4F8FF",
        "month_date_border": "#C9DBF2",
    },
    "dark": {
        "app_bg": "#1D2430",
        "panel_bg": "#252D3A",
        "fg": "#E7EDF7",
        "button_bg": "#2E3A4C",
        "button_bg_active": "#37465C",
        "button_bg_pressed": "#2A3444",
        "tab_bg": "#2B384B",
        "tab_bg_active": "#324258",
        "tab_bg_selected": "#3A4D66",
        "canvas_bg": "#202735",
        "grid_line": "#2E394A",
        "highlight": "#3A3F48",
        "scroll_trough": "#2A3445",
        "scroll_thumb": "#3C4C62",
        "list_bg": "#202735",
        "tree_alt": "#242D3C",
        "month_date_bg": "#2A3445",
        "month_date_border": "#3A4A5F",
    },
}

TIME_START = 6
TIME_END = 22


@dataclass
class Event:
    id: str
    title: str
    date: str  # YYYY-MM-DD
    start: str  # HH:MM
    end: str  # HH:MM
    category: str
    notes: str = ""


@dataclass
class ArchiveItem:
    id: str
    date: str  # YYYY-MM-DD
    category: str
    text: str
    media: list


class Storage:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data = {"events": [], "archives": [], "moods": {}, "pomodoro_records": []}
        self._ensure()
        self.load()

    def _ensure(self):
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)

    def load(self):
        with open(self.file_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        if "events" not in self.data:
            self.data["events"] = []
        if "archives" not in self.data:
            self.data["archives"] = []
        if "moods" not in self.data:
            self.data["moods"] = {}
        if "pomodoro_records" not in self.data:
            self.data["pomodoro_records"] = []

    def save(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def add_event(self, event: Event):
        self.data["events"].append(asdict(event))
        self.save()

    def update_event(self, event: Event):
        for i, item in enumerate(self.data["events"]):
            if item["id"] == event.id:
                self.data["events"][i] = asdict(event)
                self.save()
                return

    def delete_event(self, event_id: str):
        self.data["events"] = [e for e in self.data["events"] if e["id"] != event_id]
        self.save()

    def add_archive(self, item: ArchiveItem):
        self.data["archives"].append(asdict(item))
        self.save()

    def delete_archive(self, item_id: str):
        self.data["archives"] = [a for a in self.data["archives"] if a["id"] != item_id]
        self.save()

    def set_mood(self, date_str: str, emoji: str):
        self.data.setdefault("moods", {})[date_str] = emoji
        self.save()

    def add_pomodoro_record(self, record: dict):
        self.data.setdefault("pomodoro_records", []).append(record)
        self.save()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.theme_name = self._auto_theme_name()
        self.theme = THEMES[self.theme_name]
        self.title(APP_TITLE)
        self.geometry("1100x720")
        self.configure(bg=self.theme["app_bg"])

        self._setup_fonts()

        self.storage = Storage(DATA_FILE)
        self.selected_day = date.today()
        self.week_start = self._week_start(date.today())
        self.day_list_ids = []
        self.archive_list_ids = []
        self.highlight_day = None
        self.highlight_active = False
        self.week_grid = None
        self.week_col_rects = []
        self._pomodoro_after_id = None
        self.pomodoro_start_ts = None
        self.pomodoro_total_seconds = 0
        self.pomodoro_records = self.storage.data.get("pomodoro_records", [])
        self.pomodoro_records_seconds = [r.get("seconds", 0) for r in self.pomodoro_records]

        self._build_ui()
        self._apply_theme()
        self._schedule_theme_check()
        self._refresh_all()

    def _setup_fonts(self):
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="Microsoft YaHei", size=11)
        for name in ["TkTextFont", "TkFixedFont", "TkMenuFont", "TkHeadingFont"]:
            tkfont.nametofont(name).configure(family="Microsoft YaHei", size=11)
        self.option_add("*Font", default_font)
        self.option_add("*Listbox.Font", ("Microsoft YaHei", 11))
        self.option_add("*Text.Font", ("Microsoft YaHei", 11))

    def _build_ui(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background=self.theme["app_bg"])
        self.style.configure("TLabel", background=self.theme["app_bg"], foreground=self.theme["fg"])
        self.style.configure(
            "TButton",
            padding=(8, 4),
            font=("Microsoft YaHei", 11),
            background=self.theme["button_bg"],
            foreground=self.theme["fg"],
            borderwidth=1,
            relief="flat",
        )
        self.style.map(
            "TButton",
            background=[("active", self.theme["button_bg_active"]), ("pressed", self.theme["button_bg_pressed"])],
        )
        self.style.configure("TLabel", font=("Microsoft YaHei", 11), foreground=self.theme["fg"])
        self.style.configure("TEntry", font=("Microsoft YaHei", 11))
        self.style.configure("TCombobox", font=("Microsoft YaHei", 11))
        self.style.configure(
            "Mini.TButton",
            padding=(4, 2),
            font=("Microsoft YaHei", 10),
            background=self.theme["button_bg"],
            foreground=self.theme["fg"],
            borderwidth=1,
            relief="flat",
        )
        self.style.map(
            "Mini.TButton",
            background=[("active", self.theme["button_bg_active"]), ("pressed", self.theme["button_bg_pressed"])],
        )
        self.style.configure(
            "Weekday.TButton",
            padding=(6, 4),
            font=("Microsoft YaHei", 11),
            background=self.theme["button_bg"],
            foreground=self.theme["fg"],
            borderwidth=1,
            relief="flat",
        )
        self.style.map(
            "Weekday.TButton",
            background=[("active", self.theme["button_bg_active"]), ("pressed", self.theme["button_bg_pressed"])],
        )
        self.style.configure("TNotebook", background=self.theme["app_bg"], borderwidth=0)
        self.style.configure(
            "TNotebook.Tab",
            background=self.theme["tab_bg"],
            padding=(14, 6),
            font=("Microsoft YaHei", 11),
            foreground=self.theme["fg"],
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", self.theme["tab_bg_selected"]), ("active", self.theme["tab_bg_active"])],
            foreground=[("selected", self.theme["fg"]), ("active", self.theme["fg"]), ("!disabled", self.theme["fg"])],
        )
        self.style.layout(
            "Vertical.TScrollbar",
            [
                (
                    "Vertical.Scrollbar.trough",
                    {"children": [("Vertical.Scrollbar.thumb", {"sticky": "nswe"})], "sticky": "ns"},
                )
            ],
        )
        self.style.configure(
            "Vertical.TScrollbar",
            troughcolor=self.theme["scroll_trough"],
            background=self.theme["scroll_thumb"],
            bordercolor=self.theme["scroll_trough"],
            lightcolor=self.theme["scroll_thumb"],
            darkcolor=self.theme["scroll_thumb"],
            relief="flat",
        )
        self.style.layout(
            "Slim.Vertical.TScrollbar",
            [
                (
                    "Vertical.Scrollbar.trough",
                    {"children": [("Vertical.Scrollbar.thumb", {"sticky": "nswe"})], "sticky": "ns"},
                )
            ],
        )
        self.style.configure(
            "Slim.Vertical.TScrollbar",
            width=14,
            arrowsize=0,
            troughcolor="#EAF2FF",
            background="#B8D6FF",
            bordercolor="#EAF2FF",
            lightcolor="#B8D6FF",
            darkcolor="#B8D6FF",
            relief="flat",
        )
        self.style.configure(
            "Archive.Treeview",
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
            foreground="#1F3B57",
            rowheight=34,
            borderwidth=0,
        )
        self.style.configure(
            "Archive.Treeview.Heading",
            background="#DCEBFF",
            foreground="#1F3B57",
            font=("SimSun", 11, "bold"),
        )

        header = ttk.Frame(self)
        header.pack(fill="x", padx=16, pady=10)

        ttk.Label(header, text=APP_TITLE, font=("Microsoft YaHei", 16, "bold")).pack(side="left")
        ttk.Button(header, text="+ 添加日程", command=self._open_add_event).pack(side="right")

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=16, pady=8)

        self.week_tab = ttk.Frame(self.tabs)
        self.month_tab = ttk.Frame(self.tabs)
        self.stats_tab = ttk.Frame(self.tabs)
        self.pomodoro_tab = ttk.Frame(self.tabs)
        self.archive_tab = ttk.Frame(self.tabs)

        self.tabs.add(self.week_tab, text="周视图")
        self.tabs.add(self.month_tab, text="月视图")
        self.tabs.add(self.stats_tab, text="统计")
        self.tabs.add(self.pomodoro_tab, text="番茄钟")
        self.tabs.add(self.archive_tab, text="往期回顾")

        self._build_week_tab()
        self._build_month_tab()
        self._build_stats_tab()
        self._build_pomodoro_tab()
        self._build_archive_tab()

        self.status_bar = ttk.Frame(self, style="Status.TFrame")
        self.status_bar.pack(side="bottom", fill="x")
        self.status_spacer = ttk.Frame(self.status_bar)
        self.status_spacer.pack(side="left", expand=True, fill="x")
        self.theme_toggle_btn = ttk.Button(self.status_bar, text="🌙 深色模式", command=self._toggle_theme)
        self.theme_toggle_btn.pack(side="right", padx=10, pady=6)

        self.after(100, self._show_mood_prompt)

    # ---------- Week Tab ----------
    def _build_week_tab(self):
        top = ttk.Frame(self.week_tab)
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="周历选择：").pack(side="left")
        self.week_selector = ttk.Combobox(top, state="readonly", width=28)
        self.week_selector.pack(side="left", padx=6)
        self.week_selector.bind("<<ComboboxSelected>>", self._on_week_change)

        self.week_range_label = ttk.Label(top, text="")
        self.week_range_label.pack(side="left", padx=10)

        body = ttk.Frame(self.week_tab)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        self.week_canvas = tk.Canvas(body, bg=self.theme["canvas_bg"], highlightthickness=0)
        self.week_canvas.pack(side="left", fill="both", expand=True)

        self.week_scroll = ttk.Scrollbar(body, orient="vertical", command=self.week_canvas.yview)
        self.week_scroll.pack(side="left", fill="y")
        self.week_canvas.configure(yscrollcommand=self.week_scroll.set)

        self.week_inner = tk.Frame(self.week_canvas, bg=self.theme["canvas_bg"])
        self.week_window_id = self.week_canvas.create_window((0, 0), window=self.week_inner, anchor="nw")
        self.week_inner.bind("<Configure>", lambda e: self.week_canvas.configure(scrollregion=self.week_canvas.bbox("all")))

        self.day_detail = ttk.Frame(body, width=260)
        self.day_detail.pack(side="left", fill="y", padx=10)

        ttk.Label(self.day_detail, text="当天计划", font=("Microsoft YaHei", 11, "bold")).pack(anchor="w", pady=(2, 6))
        self.day_label = ttk.Label(self.day_detail, text="")
        self.day_label.configure(font=("Microsoft YaHei", 13, "bold"))
        self.day_label.pack(anchor="w", pady=(0, 8))

        self.day_list = tk.Listbox(
            self.day_detail,
            height=20,
            bg=self.theme["list_bg"],
            fg=self.theme["fg"],
            relief="flat",
            font=("Microsoft YaHei", 13),
        )
        self.day_list.pack(fill="both", expand=True)

        btns = ttk.Frame(self.day_detail)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="编辑", command=self._edit_selected_event).pack(side="left", padx=4)
        ttk.Button(btns, text="删除", command=self._delete_selected_event).pack(side="left", padx=4)

    def _populate_week_selector(self):
        options = []
        today = date.today()
        for i in range(0, 53):
            start = self._week_start(today + timedelta(weeks=i))
            end = start + timedelta(days=6)
            label = f"{start.isocalendar().year} 第{start.isocalendar().week}周 ({start.strftime('%m/%d')}-{end.strftime('%m/%d')})"
            options.append(label)
        self.week_selector["values"] = options
        self.week_selector.current(0)

    def _on_week_change(self, _event=None):
        index = self.week_selector.current()
        self.week_start = self._week_start(date.today() + timedelta(weeks=index))
        self._refresh_week()

    def _refresh_week(self):
        self.week_range_label.configure(text=self._week_range_text(self.week_start))
        self._render_week_grid()
        self._select_day(self.selected_day)

    def _render_week_grid(self):
        for child in self.week_inner.winfo_children():
            child.destroy()

        min_col_width = 70
        row_height = 40
        left_margin = 70
        top_margin = 10

        available_width = self.week_canvas.winfo_width()
        if available_width <= 1:
            available_width = 900
        col_width = max(min_col_width, int((available_width - left_margin) / 7))
        total_width = left_margin + col_width * 7

        if self.week_window_id is not None:
            self.week_canvas.itemconfig(self.week_window_id, width=total_width)

        header = ttk.Frame(self.week_inner)
        header.pack(fill="x")
        header.configure(width=total_width)
        header.pack_propagate(False)

        header.grid_columnconfigure(0, minsize=left_margin, weight=0)
        for i in range(1, 8):
            header.grid_columnconfigure(i, minsize=col_width, weight=0)

        ttk.Label(header, text="时间", anchor="center").grid(row=0, column=0, sticky="nsew")
        for i in range(7):
            day = self.week_start + timedelta(days=i)
            btn = ttk.Button(
                header,
                text=f"{day.strftime('%A')}\n{day.strftime('%m/%d')}",
                style="Weekday.TButton",
                command=lambda d=day: self._select_day(d),
            )
            btn.grid(row=0, column=i + 1, sticky="nsew")

        grid = tk.Canvas(self.week_inner, bg=self.theme["canvas_bg"], height=680, width=total_width, highlightthickness=0)
        grid.pack(fill="both", expand=True)
        self.week_grid = grid

        grid.configure(scrollregion=(0, 0, total_width + 20, (TIME_END - TIME_START) * row_height + 40))

        highlight_color = self.theme["highlight"]
        normal_color = self.theme["canvas_bg"]
        self.week_col_rects = []
        for i in range(7):
            x1 = left_margin + i * col_width
            x2 = x1 + col_width
            fill = normal_color
            if self.highlight_active and self.highlight_day:
                if self.week_start <= self.highlight_day <= self.week_start + timedelta(days=6):
                    if i == (self.highlight_day - self.week_start).days:
                        fill = highlight_color
            rect_id = grid.create_rectangle(
                x1,
                top_margin,
                x2,
                top_margin + (TIME_END - TIME_START) * row_height,
                fill=fill,
                outline="",
            )
            self.week_col_rects.append(rect_id)

        for hour in range(TIME_START, TIME_END + 1):
            y = top_margin + (hour - TIME_START) * row_height
            grid.create_text(left_margin - 10, y, text=f"{hour:02d}:00", anchor="e", fill=self.theme["fg"])
            grid.create_line(left_margin, y, left_margin + col_width * 7, y, fill=self.theme["grid_line"])

        for i in range(7):
            x = left_margin + i * col_width
            grid.create_line(x, top_margin, x, top_margin + (TIME_END - TIME_START) * row_height, fill=self.theme["grid_line"])

        week_events = self._events_in_week(self.week_start)
        events_by_day = {i: [] for i in range(7)}
        for event in week_events:
            d = datetime.strptime(event["date"], "%Y-%m-%d").date()
            day_index = (d - self.week_start).days
            if 0 <= day_index <= 6:
                events_by_day[day_index].append(event)

        for day_index, events in events_by_day.items():
            layouts = self._layout_day_events(events)
            for layout in layouts:
                event = layout["event"]
                start_minutes = self._to_minutes(event["start"])
                end_minutes = self._to_minutes(event["end"])
                duration = max(end_minutes - start_minutes, 30)
                start_y = top_margin + (start_minutes / 60 - TIME_START) * row_height
                end_y = start_y + (duration / 60) * row_height
                total_width = col_width - 8
                gap = 4
                slot_width = (total_width - gap * (layout["cols"] - 1)) / layout["cols"]
                x1 = left_margin + day_index * col_width + 4 + layout["col"] * (slot_width + gap)
                x2 = x1 + slot_width
                color = CATEGORY_COLORS.get(event["category"], "#E8E8E8")
                rect = self._create_rounded_rect(grid, x1, start_y, x2, end_y, 8, color, "#C2D6EE")
                text_id = grid.create_text(x1 + 6, start_y + 6, anchor="nw", text=event["title"], fill="#000000")
                grid.tag_bind(rect, "<Button-1>", lambda _e, eid=event["id"]: self._select_event_by_id(eid))
                grid.tag_bind(text_id, "<Button-1>", lambda _e, eid=event["id"]: self._select_event_by_id(eid))

    # ---------- Month Tab ----------
    def _build_month_tab(self):
        top = ttk.Frame(self.month_tab)
        top.pack(fill="x", padx=8, pady=8)

        self.month_label = ttk.Label(top, text="", font=("SimSun", 11, "bold"))
        self.month_label.pack(side="left")

        ttk.Button(top, text="上月", command=lambda: self._shift_month(-1)).pack(side="right", padx=4)
        ttk.Button(top, text="下月", command=lambda: self._shift_month(1)).pack(side="right", padx=4)

        self.month_frame = ttk.Frame(self.month_tab)
        self.month_frame.pack(fill="both", expand=True, padx=8, pady=6)

        self.current_month = date.today().replace(day=1)

    # ---------- Stats Tab ----------
    def _build_stats_tab(self):
        top = ttk.Frame(self.stats_tab)
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="周历选择：").pack(side="left")
        self.stats_selector = ttk.Combobox(top, state="readonly", width=28)
        self.stats_selector.pack(side="left", padx=6)
        self.stats_selector.bind("<<ComboboxSelected>>", self._on_stats_week_change)

        self.stats_range_label = ttk.Label(top, text="")
        self.stats_range_label.pack(side="left", padx=10)

        self.stats_canvas = tk.Canvas(self.stats_tab, bg=self.theme["canvas_bg"], highlightthickness=0)
        self.stats_canvas.pack(fill="both", expand=True, padx=8, pady=6)

        self.stats_week_start = self._week_start(date.today())
        self._populate_stats_selector()
        self._render_stats()

    def _populate_stats_selector(self):
        options = []
        today = date.today()
        for i in range(0, 53):
            start = self._week_start(today + timedelta(weeks=i))
            end = start + timedelta(days=6)
            label = f"{start.isocalendar().year} 第{start.isocalendar().week}周 ({start.strftime('%m/%d')}-{end.strftime('%m/%d')})"
            options.append(label)
        self.stats_selector["values"] = options
        self.stats_selector.current(0)
        self.stats_week_start = self._week_start(today)
        self.stats_range_label.configure(text=self._week_range_text(self.stats_week_start))

    def _on_stats_week_change(self, _event=None):
        index = self.stats_selector.current()
        self.stats_week_start = self._week_start(date.today() + timedelta(weeks=index))
        self.stats_range_label.configure(text=self._week_range_text(self.stats_week_start))
        self._render_stats()

    def _render_stats(self):
        canvas = self.stats_canvas
        canvas.delete("all")
        canvas.configure(bg=self.theme["canvas_bg"])

        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width <= 1:
            width = 900
        if height <= 1:
            height = 420

        padding = 50
        footer_h = int(height * 0.25)
        chart_w = width - padding * 2
        chart_h = height - padding * 2 - footer_h

        totals = {c: 0 for c in CATEGORIES}
        end = self.stats_week_start + timedelta(days=6)
        for e in self.storage.data["events"]:
            d = datetime.strptime(e["date"], "%Y-%m-%d").date()
            if not (self.stats_week_start <= d <= end):
                continue
            start_m = self._to_minutes(e["start"])
            end_m = self._to_minutes(e["end"])
            totals[e["category"]] += max(0, end_m - start_m)

        max_minutes = max(totals.values()) if totals else 0
        max_minutes = max(max_minutes, 60)

        left_w = int(chart_w * 0.55)
        right_w = chart_w - left_w

        bar_count = len(CATEGORIES)
        bar_gap = 14
        bar_w = max(24, int((left_w - bar_gap * (bar_count - 1)) / bar_count))

        for i, cat in enumerate(CATEGORIES):
            value = totals.get(cat, 0)
            bar_h = int((value / max_minutes) * chart_h)
            x = padding + i * (bar_w + bar_gap)
            y = padding + (chart_h - bar_h)

            color = CATEGORY_COLORS.get(cat, "#88AADD")
            shadow = "#9FB7D1" if self.theme_name == "light" else "#3A4759"

            canvas.create_rectangle(x + 5, y - 5, x + bar_w + 5, y + bar_h - 5, fill=shadow, outline="")
            canvas.create_rectangle(x, y, x + bar_w, y + bar_h, fill=color, outline="")
            canvas.create_polygon(
                x, y,
                x + 5, y - 5,
                x + bar_w + 5, y - 5,
                x + bar_w, y,
                fill=color,
                outline="",
            )

            canvas.create_text(x + bar_w / 2, padding + chart_h + 18, text=cat, fill=self.theme["fg"])
            hours = value / 60
            canvas.create_text(x + bar_w / 2, y - 18, text=f"{hours:.1f}h", fill=self.theme["fg"])

        # Pie chart on the right
        pie_x0 = padding + left_w + 20
        pie_y0 = padding + 10
        pie_x1 = padding + left_w + right_w - 20
        pie_y1 = padding + chart_h - 10
        pie_size = min(pie_x1 - pie_x0, pie_y1 - pie_y0)
        pie_x1 = pie_x0 + pie_size
        pie_y1 = pie_y0 + pie_size

        total_minutes = sum(totals.values())
        if total_minutes <= 0:
            canvas.create_oval(pie_x0, pie_y0, pie_x1, pie_y1, fill=self.theme["button_bg"], outline="")
            canvas.create_text((pie_x0 + pie_x1) / 2, (pie_y0 + pie_y1) / 2, text="暂无数据", fill=self.theme["fg"])
        else:
            start_angle = 90
            for cat in CATEGORIES:
                value = totals.get(cat, 0)
                if value <= 0:
                    continue
                extent = value / total_minutes * 360
                color = CATEGORY_COLORS.get(cat, "#88AADD")
                canvas.create_arc(
                    pie_x0,
                    pie_y0,
                    pie_x1,
                    pie_y1,
                    start=start_angle,
                    extent=-extent,
                    fill=color,
                    outline=self.theme["canvas_bg"],
                )
                percent = value / total_minutes * 100
                angle_rad = (start_angle - extent / 2) * 3.14159 / 180
                label_r = pie_size * 0.35
                label_x = (pie_x0 + pie_x1) / 2 + label_r * math.cos(angle_rad)
                label_y = (pie_y0 + pie_y1) / 2 - label_r * math.sin(angle_rad)
                # percent label should remain black for readability
                canvas.create_text(label_x, label_y, text=f"{percent:.0f}%", fill="#000000")
                start_angle -= extent

    # ---------- Pomodoro Tab ----------
    def _build_pomodoro_tab(self):
        self.pomodoro_running = False
        self.pomodoro_remaining = 0
        self.pomodoro_preset_canvases = []

        wrap = ttk.Frame(self.pomodoro_tab)
        wrap.pack(fill="both", expand=True, padx=16, pady=16)

        # left: record list (scrollable, no title)
        record_panel = ttk.Frame(wrap, width=260)
        record_panel.pack(side="left", fill="y", padx=(0, 16))
        record_panel.pack_propagate(False)

        self.pomodoro_record_list = tk.Listbox(
            record_panel,
            height=18,
            bg=self.theme["list_bg"],
            fg=self.theme["fg"],
            relief="flat",
            font=("Microsoft YaHei", 11),
        )
        self.pomodoro_record_list.pack(side="left", fill="both", expand=True)
        record_scroll = ttk.Scrollbar(record_panel, orient="vertical", command=self.pomodoro_record_list.yview)
        record_scroll.pack(side="left", fill="y")
        self.pomodoro_record_list.configure(yscrollcommand=record_scroll.set)

        # right: timer UI
        timer_panel = ttk.Frame(wrap)
        timer_panel.pack(side="left", fill="both", expand=True)

        self.pomodoro_focus_label = ttk.Label(
            timer_panel,
            text="你已专注\n了0小时0分钟",
            font=("Microsoft YaHei", 14, "bold"),
            anchor="e",
            justify="right",
        )
        self.pomodoro_focus_label.place(relx=1.0, rely=0.0, anchor="ne", x=-8, y=6)

        center_panel = ttk.Frame(timer_panel)
        center_panel.place(relx=0.5, rely=0.5, anchor="center")

        self.pomodoro_canvas = tk.Canvas(center_panel, width=320, height=320, bg=self.theme["app_bg"], highlightthickness=0, bd=0)
        self.pomodoro_canvas.pack(pady=(10, 20))

        self.pomodoro_time_text = self.pomodoro_canvas.create_text(
            160,
            160,
            text="00:00:00",
            font=("Microsoft YaHei", 28, "bold"),
            fill=self.theme["fg"],
        )
        self._draw_pomodoro_ring()

        presets_row1 = [(15, "15:00"), (30, "30:00"), (60, "01:00:00")]
        presets_row2 = [(1, "01:00"), (5, "05:00"), (10, "10:00")]
        btn_row1 = ttk.Frame(center_panel)
        btn_row1.pack()
        for minutes, label in presets_row1:
            self._create_pomodoro_preset(btn_row1, minutes, label)

        btn_row2 = ttk.Frame(center_panel)
        btn_row2.pack(pady=(8, 0))
        for minutes, label in presets_row2:
            self._create_pomodoro_preset(btn_row2, minutes, label)

        # cancel button at bottom-right of this tab
        controls = ttk.Frame(center_panel)
        controls.pack(fill="both", expand=True)
        cancel_btn = ttk.Button(controls, text="取消", command=self._cancel_pomodoro)
        cancel_btn.pack(side="right", padx=16, pady=8)

        # populate history and focus summary
        for rec in self.pomodoro_records:
            start_text = rec.get("start", "")
            total_text = self._format_seconds(rec.get("seconds", 0))
            if start_text:
                self.pomodoro_record_list.insert("end", f"{start_text}  {total_text}")
        self._update_pomodoro_focus_summary()

    def _draw_pomodoro_ring(self):
        # draw outer black stroke, then blue ring, then inner fill
        self.pomodoro_canvas.delete("ring")
        center = 160
        radius = 120
        # outer white ring (drawn as white disc minus a gap so it appears as a ring)
        outer_white_r = radius + 28
        gap_r = radius + 12
        self.pomodoro_canvas.create_oval(
            center - outer_white_r,
            center - outer_white_r,
            center + outer_white_r,
            center + outer_white_r,
            fill=self.theme["canvas_bg"],
            outline="",
            tags="ring",
        )
        # draw a gap (background) to make the outer white disc appear as a ring
        self.pomodoro_canvas.create_oval(
            center - gap_r,
            center - gap_r,
            center + gap_r,
            center + gap_r,
            fill=self.theme["app_bg"],
            outline="",
            tags="ring",
        )

        # blue ring
        self.pomodoro_canvas.create_oval(
            center - radius,
            center - radius,
            center + radius,
            center + radius,
            fill=self.theme["canvas_bg"],
            outline=self.theme["button_bg"],
            width=10,
            tags="ring",
        )
        # 确保时间文本在最上层
        if hasattr(self, "pomodoro_time_text"):
            try:
                self.pomodoro_canvas.tag_raise(self.pomodoro_time_text)
            except Exception:
                pass

    def _create_pomodoro_preset(self, parent, minutes: int, label: str):
        size = 90
        canvas = tk.Canvas(parent, width=size, height=size, bg=self.theme["app_bg"], highlightthickness=0)
        canvas.pack(side="left", padx=12)
        canvas.create_oval(8, 8, size - 8, size - 8, fill=self.theme["canvas_bg"], outline=self.theme["button_bg"], width=2)
        canvas.create_text(size / 2, size / 2, text=label, fill=self.theme["fg"], font=("Microsoft YaHei", 12, "bold"))

        def _on_click(_event):
            self._start_pomodoro(minutes * 60)

        canvas.bind("<Button-1>", _on_click)
        self.pomodoro_preset_canvases.append((canvas, label))

    def _start_pomodoro(self, seconds: int):
        self.pomodoro_remaining = seconds
        self.pomodoro_total_seconds = seconds
        self.pomodoro_start_ts = datetime.now()
        self.pomodoro_running = True
        self._update_pomodoro_display()
        # cancel previous scheduled tick if any
        if getattr(self, "_pomodoro_after_id", None):
            try:
                self.after_cancel(self._pomodoro_after_id)
            except Exception:
                pass
            self._pomodoro_after_id = None
        self._tick_pomodoro()

    def _cancel_pomodoro(self):
        # stop and clear the current pomodoro
        self.pomodoro_running = False
        self._maybe_log_pomodoro()
        self.pomodoro_remaining = 0
        if getattr(self, "_pomodoro_after_id", None):
            try:
                self.after_cancel(self._pomodoro_after_id)
            except Exception:
                pass
            self._pomodoro_after_id = None
        self._update_pomodoro_display()

    def _tick_pomodoro(self):
        if not self.pomodoro_running:
            return
        if self.pomodoro_remaining <= 0:
            self.pomodoro_running = False
            self._update_pomodoro_display()
            self._maybe_log_pomodoro()
            messagebox.showinfo("提示", random.choice([
                "时间到啦，休息一下吧",
                "时间到啦，你做到了吗",
                "时间到啦，辛苦了",
            ]))
            # clear any scheduled after
            if getattr(self, "_pomodoro_after_id", None):
                try:
                    self.after_cancel(self._pomodoro_after_id)
                except Exception:
                    pass
                self._pomodoro_after_id = None
            return
        self.pomodoro_remaining -= 1
        self._update_pomodoro_display()
        self._pomodoro_after_id = self.after(1000, self._tick_pomodoro)

    def _maybe_log_pomodoro(self):
        if not self.pomodoro_start_ts or self.pomodoro_total_seconds <= 0:
            return
        elapsed = self.pomodoro_total_seconds - max(0, self.pomodoro_remaining)
        if elapsed < int(self.pomodoro_total_seconds * 0.8):
            return
        start_text = self.pomodoro_start_ts.strftime("%Y-%m-%d %H:%M:%S")
        total_text = self._format_seconds(self.pomodoro_total_seconds)
        record = {"start": start_text, "seconds": int(self.pomodoro_total_seconds)}
        self.pomodoro_records.append(record)
        self.pomodoro_records_seconds.append(self.pomodoro_total_seconds)
        self.storage.add_pomodoro_record(record)
        if hasattr(self, "pomodoro_record_list"):
            self.pomodoro_record_list.insert("end", f"{start_text}  {total_text}")
        self._update_pomodoro_focus_summary()
        # avoid duplicate logging for same session
        self.pomodoro_start_ts = None
        self.pomodoro_total_seconds = 0

    def _update_pomodoro_focus_summary(self):
        total_seconds = sum(self.pomodoro_records_seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        text = f"你已专注\n了{hours}小时{minutes}分钟"
        if hasattr(self, "pomodoro_focus_label"):
            self.pomodoro_focus_label.config(text=text)

    def _format_seconds(self, total: int) -> str:
        total = max(0, int(total))
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _update_pomodoro_display(self):
        total = max(0, self.pomodoro_remaining)
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        text = f"{h:02d}:{m:02d}:{s:02d}"
        if hasattr(self, "pomodoro_canvas"):
            self.pomodoro_canvas.itemconfig(self.pomodoro_time_text, text=text, fill=self.theme["fg"])

    # ---------- Mood Prompt ----------
    def _show_mood_prompt(self):
        today_key = date.today().strftime("%Y-%m-%d")

        # 创建覆盖层（overlay），覆盖整个主窗口内容区域
        overlay = tk.Frame(self, bg=self.theme["panel_bg"])
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift(aboveThis=None)
        try:
            overlay.grab_set()
        except Exception:
            pass

        container = ttk.Frame(overlay)
        container.place(relx=0.5, rely=0.48, anchor="center")

        ttk.Label(container, text="欢迎回家，今天的心情怎样？", font=("Microsoft YaHei", 14, "bold"))
        ttk.Label(container, text="欢迎回家，今天的心情怎样？", font=("Microsoft YaHei", 14, "bold")).pack(pady=(8, 8))

        grid = ttk.Frame(container)
        grid.pack()

        moods = [
            "开心 😄", "平静 😌", "感恩 🙏", "充满希望 🌈",
            "自豪 😎", "期待 🤩", "专注 🔍", "高效 ⚡",
            "动力十足 🔥", "创造 💡", "学习 📚", "挑战 🧗",
            "被爱 🥰", "合作愉快 🤝", "收到启发 ✨", "治愈 🌿",
            "健康 🏃", "庆祝 🎉", "纪念 🎂", "家庭时光 👨‍👩‍👧",
            "压力大 😰", "无聊 😐",
            "混乱 😵", "犹豫 🤔", "拖延 🐌", "孤独 🏝️",
            "想念 🌙", "生气 😠", "失望 😔", "焦虑 😟",
        ]

        def animate_dismiss():
            # 释放 grab 并向上滑动销毁 overlay
            try:
                overlay.grab_release()
            except Exception:
                pass

            def step():
                info = overlay.place_info()
                rely = float(info.get("rely", 0))
                rely -= 0.06
                overlay.place_configure(rely=rely)
                if rely > -1.2:
                    overlay.after(12, step)
                else:
                    try:
                        overlay.destroy()
                    except Exception:
                        pass

            step()

        def select_mood(mood_text: str):
            emoji = mood_text.split(" ")[-1]
            self.storage.set_mood(today_key, emoji)
            self._render_month()
            animate_dismiss()

        for i, mood in enumerate(moods):
            # 在深色模式下将文字（和 emoji）设为白色；浅色模式不强制前景以保留彩色 emoji
            btn_kwargs = {"width": 12, "relief": "raised", "bd": 0, "bg": self.theme["button_bg"], "command": (lambda m=mood: select_mood(m))}
            if self.theme_name == "dark":
                btn_kwargs["fg"] = self.theme["fg"]
            b = tk.Button(grid, text=mood, **btn_kwargs)
            b.grid(row=i // 8, column=i % 8, padx=6, pady=6, sticky="nsew")

        for r in range(4):
            grid.grid_rowconfigure(r, weight=1)
        for c in range(8):
            grid.grid_columnconfigure(c, weight=1)

        # 右下角灰色小“跳过”按钮
        skip_btn = tk.Button(overlay, text="跳过", bg="#9E9E9E", fg="#FFFFFF", relief="flat", command=animate_dismiss)
        skip_btn.place(relx=0.98, rely=0.94, anchor="se")
        skip_btn.lift()

    def _shift_month(self, delta):
        year = self.current_month.year + (self.current_month.month + delta - 1) // 12
        month = (self.current_month.month + delta - 1) % 12 + 1
        self.current_month = date(year, month, 1)
        self._render_month()

    def _render_month(self):
        for child in self.month_frame.winfo_children():
            child.destroy()

        self.month_label.configure(text=self.current_month.strftime("%Y年 %m月"))

        headers = ["一", "二", "三", "四", "五", "六", "日"]
        header_frame = ttk.Frame(self.month_frame)
        header_frame.pack(fill="x")
        for i, h in enumerate(headers):
            ttk.Label(header_frame, text=h, width=12, anchor="center").grid(row=0, column=i, sticky="nsew")

        cal = ttk.Frame(self.month_frame)
        cal.pack(fill="both", expand=True)

        first_weekday = (self.current_month.weekday() + 1) % 7  # Monday=0
        days_in_month = (self._next_month(self.current_month) - timedelta(days=1)).day

        total_slots = 42
        start_offset = (first_weekday - 1) % 7

        day_cursor = 1
        for slot in range(total_slots):
            row = slot // 7
            col = slot % 7

            cell = ttk.Frame(cal, relief="ridge")
            cell.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
            cell.grid_propagate(False)

            if slot < start_offset or day_cursor > days_in_month:
                continue

            current = self.current_month.replace(day=day_cursor)
            date_chip = tk.Frame(
                cell,
                bg=self.theme["month_date_bg"],
                highlightbackground=self.theme["month_date_border"],
                highlightthickness=1,
            )
            date_chip.pack(anchor="nw", padx=4, pady=4)
            mood = self.storage.data.get("moods", {}).get(current.strftime("%Y-%m-%d"), "")
            label_text = f"{day_cursor} {mood}" if mood else str(day_cursor)
            tk.Label(date_chip, text=label_text, bg=self.theme["month_date_bg"], fg=self.theme["fg"]).pack(padx=4, pady=1)

            events_wrap = ttk.Frame(cell)
            events_wrap.pack(fill="x", padx=4, pady=(2, 4))

            items = self._events_on_day(current)
            for ev in items[:2]:
                color = CATEGORY_COLORS.get(ev["category"], "#E8E8E8")
                self._create_rounded_event_tag(events_wrap, ev["title"], color)

            btn = ttk.Button(cell, text="查看", style="Mini.TButton", width=4, command=lambda d=current: self._open_day_from_month(d))
            btn.place(relx=1.0, rely=1.0, anchor="se", x=-6, y=-6)

            day_cursor += 1

        for i in range(7):
            cal.grid_columnconfigure(i, weight=1, uniform="month")
        for r in range(6):
            cal.grid_rowconfigure(r, weight=1, uniform="month")

    def _next_month(self, d: date):
        if d.month == 12:
            return date(d.year + 1, 1, 1)
        return date(d.year, d.month + 1, 1)

    # ---------- Archive Tab ----------
    def _build_archive_tab(self):
        top = ttk.Frame(self.archive_tab)
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="筛选：").pack(side="left")
        self.archive_filter = ttk.Combobox(top, state="readonly", values=["全部"] + CATEGORIES)
        self.archive_filter.current(0)
        self.archive_filter.pack(side="left", padx=6)
        self.archive_filter.bind("<<ComboboxSelected>>", lambda _e: self._refresh_archive())

        ttk.Button(top, text="+ 新建收藏", command=self._open_add_archive).pack(side="right")
        ttk.Button(top, text="查看实况", command=self._open_selected_archive_media).pack(side="right", padx=6)
        ttk.Button(top, text="删除", command=self._delete_selected_archive).pack(side="right", padx=6)

        list_wrap = ttk.Frame(self.archive_tab)
        list_wrap.pack(fill="both", expand=True, padx=8, pady=6)

        self.archive_list = ttk.Treeview(
            self.archive_tab,
            columns=("date", "summary"),
            show="headings",
            style="Archive.Treeview",
        )
        self.archive_list.heading("date", text="日期")
        self.archive_list.heading("summary", text="内容")
        self.archive_list.column("date", width=140, anchor="center")
        self.archive_list.column("summary", width=640, anchor="w")
        self.archive_list.pack(in_=list_wrap, side="left", fill="both", expand=True)

        archive_scroll = ttk.Scrollbar(list_wrap, orient="vertical", command=self.archive_list.yview)
        archive_scroll.pack(side="left", fill="y")
        self.archive_list.configure(yscrollcommand=archive_scroll.set)
        self.archive_list.bind("<Button-1>", self._toggle_archive_selection, add=True)
        self.archive_list.bind("<Double-1>", self._open_archive_detail, add=True)

        scroll_btns = ttk.Frame(self.archive_tab)
        scroll_btns.pack(fill="x", padx=8, pady=(0, 8))
        self._create_triangle_button(
            scroll_btns,
            direction="up",
            command=lambda: self.archive_list.yview_scroll(-3, "units"),
        ).pack(side="left", padx=6)
        self._create_triangle_button(
            scroll_btns,
            direction="down",
            command=lambda: self.archive_list.yview_scroll(3, "units"),
        ).pack(side="left", padx=6)

    # ---------- Event CRUD ----------
    def _open_add_event(self):
        self._open_event_dialog()

    def _edit_selected_event(self):
        selection = self.day_list.curselection()
        if not selection:
            messagebox.showinfo("提示", "请选择要编辑的日程")
            return
        if selection[0] >= len(self.day_list_ids):
            return
        event_id = self.day_list_ids[selection[0]]
        ev = self._get_event_by_id(event_id)
        if ev:
            self._open_event_dialog(ev)

    def _delete_selected_event(self):
        selection = self.day_list.curselection()
        if not selection:
            messagebox.showinfo("提示", "请选择要删除的日程")
            return
        if selection[0] >= len(self.day_list_ids):
            return
        event_id = self.day_list_ids[selection[0]]
        if messagebox.askyesno("确认", "确定删除该日程？"):
            self.storage.delete_event(event_id)
            self._refresh_all()

    def _open_event_dialog(self, event=None):
        dialog = tk.Toplevel(self)
        dialog.title("添加日程" if event is None else "编辑日程")
        dialog.geometry("520x520")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(True, True)
        dialog.configure(bg=self.theme["app_bg"])

        inner = self._create_scrollable_dialog(dialog)

        ttk.Label(inner, text="名称").pack(anchor="w", padx=12, pady=(12, 2))
        title_var = tk.StringVar(value=event["title"] if event else "")
        ttk.Entry(inner, textvariable=title_var).pack(fill="x", padx=12)

        ttk.Label(inner, text="日期").pack(anchor="w", padx=12, pady=(10, 2))
        date_var = tk.StringVar(value=event["date"] if event else self.selected_day.strftime("%Y-%m-%d"))
        ttk.Entry(inner, textvariable=date_var).pack(fill="x", padx=12)

        ttk.Label(inner, text="开始时间").pack(anchor="w", padx=12, pady=(10, 2))
        start_hour_var, start_min_var, start_row = self._build_time_picker(
            inner,
            event["start"] if event else "09:00",
        )
        start_row.pack(fill="x", padx=12)

        ttk.Label(inner, text="结束时间").pack(anchor="w", padx=12, pady=(10, 2))
        end_hour_var, end_min_var, end_row = self._build_time_picker(
            inner,
            event["end"] if event else "10:00",
        )
        end_row.pack(fill="x", padx=12)

        ttk.Label(inner, text="类型").pack(anchor="w", padx=12, pady=(10, 2))
        cat_var = tk.StringVar(value=event["category"] if event else CATEGORIES[0])
        ttk.Combobox(inner, state="readonly", values=CATEGORIES, textvariable=cat_var, height=4).pack(fill="x", padx=12)

        ttk.Label(inner, text="备注").pack(anchor="w", padx=12, pady=(10, 2))
        notes_box = tk.Text(inner, height=6, wrap="word")
        notes_box.pack(fill="both", padx=12)
        if event and event.get("notes"):
            notes_box.insert("1.0", event.get("notes", ""))

        def on_save():
            try:
                datetime.strptime(date_var.get(), "%Y-%m-%d")
                self._validate_time(self._merge_time(start_hour_var, start_min_var))
                self._validate_time(self._merge_time(end_hour_var, end_min_var))
            except ValueError:
                messagebox.showerror("错误", "日期或时间格式不正确")
                return

            if self._find_overlaps(
                date_var.get(),
                self._merge_time(start_hour_var, start_min_var),
                self._merge_time(end_hour_var, end_min_var),
                event["id"] if event else None,
            ):
                messagebox.showwarning("提示", "该时间段与已有日程重叠，将并排显示")

            new_event = Event(
                id=event["id"] if event else str(uuid.uuid4()),
                title=title_var.get().strip() or "未命名",
                date=date_var.get(),
                start=self._merge_time(start_hour_var, start_min_var),
                end=self._merge_time(end_hour_var, end_min_var),
                category=cat_var.get(),
                notes=notes_box.get("1.0", "end").strip(),
            )

            if event:
                self.storage.update_event(new_event)
            else:
                self.storage.add_event(new_event)

            dialog.destroy()
            self._refresh_all()

        ttk.Button(inner, text="保存", command=on_save).pack(pady=16)

    # ---------- Archive CRUD ----------
    def _open_add_archive(self):
        dialog = tk.Toplevel(self)
        dialog.title("新建收藏")
        dialog.geometry("540x560")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(True, True)
        dialog.configure(bg=self.theme["app_bg"])

        inner = self._create_scrollable_dialog(dialog)

        ttk.Label(inner, text="日期").pack(anchor="w", padx=12, pady=(12, 2))
        date_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        ttk.Entry(inner, textvariable=date_var).pack(fill="x", padx=12)

        ttk.Label(inner, text="类型").pack(anchor="w", padx=12, pady=(10, 2))
        cat_var = tk.StringVar(value=CATEGORIES[0])
        ttk.Combobox(inner, state="readonly", values=CATEGORIES, textvariable=cat_var, height=4, width=18).pack(anchor="w", padx=12)

        ttk.Label(inner, text="说说你的想法").pack(anchor="w", padx=12, pady=(10, 2))
        text_box = tk.Text(inner, height=10, wrap="word")
        text_box.pack(fill="both", padx=12)

        media_paths = []
        media_label = ttk.Label(inner, text="已添加媒体：0")
        media_label.pack(anchor="w", padx=12, pady=(8, 2))

        def add_media():
            paths = filedialog.askopenfilenames(title="选择图片或视频")
            if paths:
                media_paths.extend(paths)
                media_label.config(text=f"已添加媒体：{len(media_paths)}")

        ttk.Button(inner, text="添加实况", command=add_media).pack(anchor="w", padx=12)

        def on_save():
            try:
                datetime.strptime(date_var.get(), "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("错误", "日期格式不正确")
                return

            item = ArchiveItem(
                id=str(uuid.uuid4()),
                date=date_var.get(),
                category=cat_var.get(),
                text=text_box.get("1.0", "end").strip(),
                media=media_paths,
            )
            self.storage.add_archive(item)
            dialog.destroy()
            self._refresh_archive()

        ttk.Button(inner, text="保存", command=on_save).pack(pady=14)

    def _create_scrollable_dialog(self, dialog):
        container = ttk.Frame(dialog)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg=self.theme["app_bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_configure(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", _on_configure)

        def _bind_mousewheel(_event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(_event):
            canvas.unbind_all("<MouseWheel>")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        return inner

    def _delete_selected_archive(self):
        selection = self.archive_list.selection()
        if not selection:
            messagebox.showinfo("提示", "请选择要删除的收藏")
            return
        item_id = selection[0]
        if messagebox.askyesno("确认", "确定删除该收藏？"):
            self.storage.delete_archive(item_id)
            self._refresh_archive()

    def _open_selected_archive_media(self):
        self._open_archive_detail()

    def _open_archive_detail(self, event=None):
        item_id = None
        if event is not None:
            row = self.archive_list.identify_row(event.y)
            if row:
                item_id = row
        if not item_id:
            selection = self.archive_list.selection()
            if selection:
                item_id = selection[0]
        if not item_id:
            messagebox.showinfo("提示", "请选择要打开的收藏")
            return

        item = None
        for a in self.storage.data["archives"]:
            if a["id"] == item_id:
                item = a
                break
        if not item:
            return

        dialog = tk.Toplevel(self)
        dialog.title("收藏详情")
        dialog.geometry("560x560")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=self.theme["app_bg"])

        inner = self._create_scrollable_dialog(dialog)

        ttk.Label(inner, text=f"日期：{item['date']}").pack(anchor="w", padx=12, pady=(12, 6))
        ttk.Label(inner, text="内容：").pack(anchor="w", padx=12)
        content_box = tk.Text(inner, height=8, wrap="word", bg=self.theme["list_bg"], fg=self.theme["fg"])
        content_box.pack(fill="both", padx=12, pady=(4, 8))
        content_box.insert("1.0", item.get("text", ""))
        content_box.configure(state="disabled")

        media = item.get("media", [])
        ttk.Label(inner, text=f"实况文件：{len(media)}").pack(anchor="w", padx=12, pady=(6, 4))
        media_list = tk.Listbox(inner, height=6, bg=self.theme["list_bg"], fg=self.theme["fg"], relief="flat")
        media_list.pack(fill="both", padx=12)
        for path in media:
            media_list.insert(tk.END, path)

        def open_all():
            if not media:
                messagebox.showinfo("提示", "该收藏没有媒体文件")
                return
            missing = []
            for path in media:
                if os.path.exists(path):
                    os.startfile(path)
                else:
                    missing.append(path)
            if missing:
                messagebox.showwarning("提示", "部分媒体文件不存在或已移动")

        def open_selected(_event):
            selection = media_list.curselection()
            if not selection:
                return
            path = media_list.get(selection[0])
            if os.path.exists(path):
                os.startfile(path)
            else:
                messagebox.showwarning("提示", "媒体文件不存在或已移动")

        media_list.bind("<Double-1>", open_selected)
        ttk.Button(inner, text="同步播放", command=open_all).pack(anchor="w", padx=12, pady=8)

    # ---------- Helpers ----------
    def _refresh_all(self):
        self._populate_week_selector()
        self._refresh_week()
        self._render_month()
        if hasattr(self, "stats_canvas"):
            self._render_stats()
        self._refresh_archive()

    def _refresh_archive(self):
        for item in self.archive_list.get_children():
            self.archive_list.delete(item)
        selected = self.archive_filter.get()
        items = self.storage.data["archives"]
        if selected and selected != "全部":
            items = [a for a in items if a["category"] == selected]
        items = sorted(items, key=lambda x: x["date"], reverse=True)
        for index, item in enumerate(items):
            title = item["text"].strip().replace("\n", " ")[:40] or "（无文字）"
            tag = "even" if index % 2 == 0 else "odd"
            self.archive_list.insert(
                "",
                "end",
                iid=item["id"],
                values=(item["date"], title),
                tags=(tag,),
            )
        self.archive_list.tag_configure("even", background=self.theme["tree_alt"])
        self.archive_list.tag_configure("odd", background=self.theme["list_bg"])

    def _apply_theme(self):
        self.configure(bg=self.theme["app_bg"])
        self.style.configure("TFrame", background=self.theme["app_bg"])
        self.style.configure("TLabel", background=self.theme["app_bg"], foreground=self.theme["fg"])
        self.style.configure(
            "TButton",
            background=self.theme["button_bg"],
            foreground=self.theme["fg"],
        )
        self.style.map(
            "TButton",
            background=[("active", self.theme["button_bg_active"]), ("pressed", self.theme["button_bg_pressed"])],
        )
        self.style.configure(
            "Mini.TButton",
            background=self.theme["button_bg"],
            foreground=self.theme["fg"],
        )
        self.style.map(
            "Mini.TButton",
            background=[("active", self.theme["button_bg_active"]), ("pressed", self.theme["button_bg_pressed"])],
        )
        self.style.configure(
            "Weekday.TButton",
            background=self.theme["button_bg"],
            foreground=self.theme["fg"],
        )
        self.style.map(
            "Weekday.TButton",
            background=[("active", self.theme["button_bg_active"]), ("pressed", self.theme["button_bg_pressed"])],
        )
        self.style.configure("TNotebook", background=self.theme["app_bg"])
        self.style.configure(
            "TNotebook.Tab",
            background=self.theme["tab_bg"],
            foreground=self.theme["fg"],
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", self.theme["tab_bg_selected"]), ("active", self.theme["tab_bg_active"])],
            foreground=[("selected", self.theme["fg"]), ("active", self.theme["fg"]), ("!disabled", self.theme["fg"])],
        )
        self.style.configure(
            "Vertical.TScrollbar",
            troughcolor=self.theme["scroll_trough"],
            background=self.theme["scroll_thumb"],
            bordercolor=self.theme["scroll_trough"],
            lightcolor=self.theme["scroll_thumb"],
            darkcolor=self.theme["scroll_thumb"],
            relief="flat",
        )
        self.style.configure(
            "Archive.Treeview",
            background=self.theme["list_bg"],
            fieldbackground=self.theme["list_bg"],
            foreground=self.theme["fg"],
        )
        self.style.configure(
            "Archive.Treeview.Heading",
            background=self.theme["button_bg"],
            foreground=self.theme["fg"],
        )
        self.style.configure("Status.TFrame", background=self.theme["panel_bg"])

        if hasattr(self, "day_list"):
            self.day_list.configure(bg=self.theme["list_bg"], fg=self.theme["fg"])
        if hasattr(self, "stats_canvas"):
            self.stats_canvas.configure(bg=self.theme["canvas_bg"])
        if hasattr(self, "pomodoro_canvas"):
            self.pomodoro_canvas.configure(bg=self.theme["canvas_bg"])
            self._draw_pomodoro_ring()
            self._update_pomodoro_display()
        if hasattr(self, "pomodoro_preset_canvases"):
            for canvas, label in self.pomodoro_preset_canvases:
                canvas.configure(bg=self.theme["app_bg"])
                canvas.delete("all")
                canvas.create_oval(8, 8, 90 - 8, 90 - 8, fill=self.theme["canvas_bg"], outline=self.theme["button_bg"], width=2)
                canvas.create_text(90 / 2, 90 / 2, text=label, fill=self.theme["fg"], font=("Microsoft YaHei", 12, "bold"))
        if hasattr(self, "status_bar"):
            self.status_bar.configure(style="Status.TFrame")
        if hasattr(self, "theme_toggle_btn"):
            self._update_theme_button_text()

        self._render_week_grid()
        self._render_month()
        self._render_stats()
        self._refresh_archive()

    def _update_theme_button_text(self):
        if self.theme_name == "dark":
            self.theme_toggle_btn.configure(text="☀️ 浅色模式")
        else:
            self.theme_toggle_btn.configure(text="🌙 深色模式")

    def _toggle_theme(self):
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.theme = THEMES[self.theme_name]
        self._apply_theme()

    def _auto_theme_name(self):
        hour = datetime.now().hour
        return "dark" if (hour >= 23 or hour < 6) else "light"

    def _schedule_theme_check(self):
        auto_name = self._auto_theme_name()
        if auto_name != self.theme_name:
            self.theme_name = auto_name
            self.theme = THEMES[self.theme_name]
            self._apply_theme()
        self.after(10 * 60 * 1000, self._schedule_theme_check)

    def _select_day(self, d: date):
        self.selected_day = d
        self.day_label.config(text=d.strftime("%Y-%m-%d"))
        self.day_list.delete(0, tk.END)
        self.day_list_ids = []
        for event in self._events_on_day(d):
            self.day_list_ids.append(event["id"])
            notes = event.get("notes", "").strip()
            display = f"{event['title']}（{notes}）" if notes else event["title"]
            self.day_list.insert(tk.END, display)

    def _select_event_by_id(self, event_id: str):
        ev = self._get_event_by_id(event_id)
        if not ev:
            return
        d = datetime.strptime(ev["date"], "%Y-%m-%d").date()
        self._select_day(d)
        for i, eid in enumerate(self.day_list_ids):
            if eid == event_id:
                self.day_list.selection_clear(0, tk.END)
                self.day_list.selection_set(i)
                self.day_list.activate(i)
                break

    def _open_day_from_month(self, d: date):
        self.week_start = self._week_start(d)
        self.selected_day = d
        self.tabs.select(self.week_tab)
        self._refresh_week()
        self._flash_day_highlight(d)

    def _events_on_day(self, d: date):
        return sorted(
            [e for e in self.storage.data["events"] if e["date"] == d.strftime("%Y-%m-%d")],
            key=lambda x: x["start"],
        )

    def _events_in_week(self, start: date):
        end = start + timedelta(days=6)
        return [
            e for e in self.storage.data["events"]
            if start <= datetime.strptime(e["date"], "%Y-%m-%d").date() <= end
        ]

    def _get_event_by_id(self, event_id: str):
        for e in self.storage.data["events"]:
            if e["id"] == event_id:
                return e
        return None

    def _week_start(self, d: date):
        return d - timedelta(days=d.weekday())

    def _week_range_text(self, start: date):
        end = start + timedelta(days=6)
        return f"{start.strftime('%Y/%m/%d')} - {end.strftime('%Y/%m/%d')}"

    def _to_minutes(self, time_str: str):
        h, m = map(int, time_str.split(":"))
        return h * 60 + m

    def _validate_time(self, time_str: str):
        datetime.strptime(time_str, "%H:%M")

    def _build_time_picker(self, parent, time_value: str):
        hours = [f"{h:02d}" for h in range(6, 23)]
        minutes = [f"{m:02d}" for m in range(0, 60, 10)]
        try:
            h, m = time_value.split(":")
        except ValueError:
            h, m = "09", "00"
        if h not in hours:
            h = "09"
        if m not in minutes:
            m = "00"

        row = ttk.Frame(parent)
        hour_var = tk.StringVar(value=h)
        min_var = tk.StringVar(value=m)
        ttk.Combobox(row, state="readonly", values=hours, width=4, textvariable=hour_var, height=6).pack(side="left")
        ttk.Label(row, text=":").pack(side="left", padx=4)
        ttk.Combobox(row, state="readonly", values=minutes, width=4, textvariable=min_var, height=6).pack(side="left")
        return hour_var, min_var, row

    def _merge_time(self, hour_var, min_var):
        return f"{hour_var.get()}:{min_var.get()}"

    def _flash_day_highlight(self, d: date):
        self.highlight_day = d

        def _set(state):
            self.highlight_active = state
            self._update_day_highlight()

        _set(True)
        self.after(500, lambda: _set(False))
        self.after(1000, lambda: _set(True))
        self.after(1500, lambda: _set(False))

    def _create_triangle_button(self, parent, direction: str, command):
        size = 24
        color = "#6AA8FF"
        canvas = tk.Canvas(parent, width=size, height=size, bg=self.theme["app_bg"], highlightthickness=0)
        if direction == "up":
            points = (size / 2, 6, 6, size - 6, size - 6, size - 6)
        else:
            points = (6, 6, size - 6, 6, size / 2, size - 6)
        canvas.create_polygon(points, fill=color, outline=color)

        def _on_click(_event):
            command()

        canvas.bind("<Button-1>", _on_click)
        return canvas

    def _update_day_highlight(self):
        if not getattr(self, "week_col_rects", None):
            return
        highlight_color = self.theme["highlight"]
        normal_color = self.theme["canvas_bg"]
        for i, rect_id in enumerate(self.week_col_rects):
            fill = normal_color
            if self.highlight_active and self.highlight_day:
                if self.week_start <= self.highlight_day <= self.week_start + timedelta(days=6):
                    if i == (self.highlight_day - self.week_start).days:
                        fill = highlight_color
            if self.week_grid:
                self.week_grid.itemconfig(rect_id, fill=fill)

    def _create_rounded_rect(self, canvas, x1, y1, x2, y2, radius, fill, outline):
        radius = min(radius, abs(x2 - x1) / 2, abs(y2 - y1) / 2)
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, fill=fill, outline=outline)

    def _toggle_archive_selection(self, event):
        row = self.archive_list.identify_row(event.y)
        if not row:
            return
        selection = self.archive_list.selection()
        if row in selection:
            self.archive_list.selection_remove(row)
            return "break"

    def _layout_day_events(self, events):
        if not events:
            return []
        items = []
        for ev in events:
            start = self._to_minutes(ev["start"])
            end = self._to_minutes(ev["end"])
            items.append({"event": ev, "start": start, "end": end})
        items.sort(key=lambda x: (x["start"], x["end"]))

        active = []
        columns = []
        layouts = []
        cluster = []
        cluster_max_cols = 0

        def finalize_cluster():
            if not cluster:
                return
            for entry in cluster:
                entry["cols"] = cluster_max_cols
                layouts.append(entry)

        for item in items:
            current_start = item["start"]
            active = [a for a in active if a["end"] > current_start]
            if not active:
                finalize_cluster()
                cluster = []
                cluster_max_cols = 0
                columns = []

            used = {a["col"] for a in active}
            col = 0
            while col in used:
                col += 1

            entry = {"event": item["event"], "start": item["start"], "end": item["end"], "col": col, "cols": 1}
            active.append(entry)
            cluster.append(entry)
            cluster_max_cols = max(cluster_max_cols, col + 1)

        finalize_cluster()
        return layouts

    def _find_overlaps(self, date_str: str, start: str, end: str, exclude_id=None):
        start_min = self._to_minutes(start)
        end_min = self._to_minutes(end)
        overlaps = []
        for e in self.storage.data["events"]:
            if e["date"] != date_str:
                continue
            if exclude_id and e["id"] == exclude_id:
                continue
            e_start = self._to_minutes(e["start"])
            e_end = self._to_minutes(e["end"])
            if max(start_min, e_start) < min(end_min, e_end):
                overlaps.append(e)
        return overlaps

    def _create_rounded_event_tag(self, parent, text: str, color: str):
        canvas = tk.Canvas(parent, height=24, bg=self.theme["app_bg"], highlightthickness=0)
        canvas.pack(fill="x", pady=2)

        def _draw(_event=None):
            canvas.delete("all")
            width = max(canvas.winfo_width(), 80)
            height = 22
            radius = 8
            x1, y1, x2, y2 = 2, 2, width - 2, height
            canvas.create_oval(x1, y1, x1 + radius * 2, y1 + radius * 2, fill=color, outline="")
            canvas.create_oval(x2 - radius * 2, y1, x2, y1 + radius * 2, fill=color, outline="")
            canvas.create_oval(x1, y2 - radius * 2, x1 + radius * 2, y2, fill=color, outline="")
            canvas.create_oval(x2 - radius * 2, y2 - radius * 2, x2, y2, fill=color, outline="")
            canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=color, outline="")
            canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=color, outline="")
            canvas.create_text(10, height / 2, anchor="w", text=text, fill="#000000")

        canvas.bind("<Configure>", _draw)
        _draw()


if __name__ == "__main__":
    app = App()
    app.mainloop()
