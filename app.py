import streamlit as st
import pandas as pd
import os
import io
import time
import zipfile
import plotly.express as px
import plotly.graph_objects as go
import altair as alt
import colorsys
import re
from html import escape as html_escape
from datetime import date, timedelta
from streamlit_quill import st_quill

# Thanh công cụ cho ô soạn ghi chú (Quill): đậm/nghiêng/gạch chân, màu chữ & nền,
# danh sách + thụt lề, liên kết, xoá định dạng. (Không bật chèn ảnh để tránh phình notes.csv.)
NOTE_TOOLBAR = [
    ["bold", "italic", "underline"],
    [{"color": []}, {"background": []}],
    [{"list": "ordered"}, {"list": "bullet"}, {"indent": "-1"}, {"indent": "+1"}],
    ["link"],
    ["clean"],
]

def _note_is_empty(html):
    """Ghi chú coi như rỗng nếu sau khi bỏ thẻ HTML chỉ còn khoảng trắng (Quill để '<p><br></p>')."""
    if not html:
        return True
    txt = re.sub(r"<[^>]+>", "", str(html)).replace("&nbsp;", " ").replace(" ", " ")
    return txt.strip() == ""

# --- CẤU HÌNH ---
DB_FILE = "database.csv"
MAPPING_FILE = "mapping.csv"
DELETED_FILE = "deleted.csv"  # khoá thời gian của các phiên đã xoá -> không nạp lại
NOTES_FILE = "notes.csv"  # ghi chú/nhật ký theo ngày

# "Nhật ký đọc sách": chỉ hiện cho nhóm sách đọc tuần tự (sửa tên ở đây nếu khác).
# BOOKS_EXCLUDE = các dự án định kỳ (vd tạp chí) -> không tính như một cuốn sách.
BOOKS_GROUP = "Reading"
BOOKS_EXCLUDE = {"The Economist"}

# Tên thứ tiếng Việt (dùng chung mọi nơi)
VN_DAYS = {"Monday": "Thứ 2", "Tuesday": "Thứ 3", "Wednesday": "Thứ 4", "Thursday": "Thứ 5",
           "Friday": "Thứ 6", "Saturday": "Thứ 7", "Sunday": "Chủ Nhật"}

# Bảng màu phong cách Apple / Latte sáng
MAC_COLORS = [
    "#007aff", # Blue (Primary)
    "#34c759", # Green
    "#ff9500", # Orange
    "#ff2d55", # Red
    "#5856d6", # Indigo
    "#af52de", # Purple
    "#5ac8fa", # Light Blue
    "#ffcc00", # Yellow
    "#32ade6", # Cyan
    "#a2845e", # Brown
    "#ff6482", # Rose
    "#30b0c7", # Teal
    "#00c7be", # Mint
    "#bf5af2", # Violet
    "#ff7b54", # Coral
    "#8e8e93", # Gray
]


def _hsl_hex(h, s, l):
    """(hue, saturation, lightness) trong [0,1] -> mã màu hex."""
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return f"#{int(round(r * 255)):02x}{int(round(g * 255)):02x}{int(round(b * 255)):02x}"


def build_color_map(names):
    """Gán màu cố định cho từng tên (Danh mục/Dự án). Ưu tiên bảng màu cơ sở;
    nếu nhiều hơn số màu sẵn có thì sinh thêm màu phân biệt bằng góc vàng
    (golden angle) để không bao giờ bị trùng màu, vẫn ổn định theo tên."""
    colors = list(MAC_COLORS)
    for k in range(len(names) - len(colors)):
        h = (0.61 + (k + 1) * 0.6180339887) % 1.0  # rải đều sắc độ
        colors.append(_hsl_hex(h, 0.62, 0.55))
    return {name: colors[i] for i, name in enumerate(names)}
CHART_WIDTH = 1120
PLOTLY_CONFIG = {'scrollZoom': False, 'displayModeBar': False, 'responsive': True}

# --- CÁC HÀM XỬ LÝ DỮ LIỆU ---
@st.cache_data
def load_db():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        rename_dict = {'Start Time': 'Thời gian bắt đầu', 'End Time': 'Thời gian kết thúc', 'Project': 'Dự án', 'Tag': 'Dự án', 'Duration (Min)': 'Thời lượng (Phút)'}
        df.rename(columns={k: v for k, v in rename_dict.items() if k in df.columns}, inplace=True)
        return df
    return pd.DataFrame(columns=["Thời gian bắt đầu", "Thời gian kết thúc", "Dự án", "Thời lượng (Phút)"])

def save_db(df):
    df.to_csv(DB_FILE, index=False)
    st.cache_data.clear()

@st.cache_data
def load_mapping():
    if os.path.exists(MAPPING_FILE):
        df = pd.read_csv(MAPPING_FILE)
        rename_dict = {'Project': 'Dự án', 'Tag': 'Dự án', 'Category': 'Danh mục'}
        df.rename(columns={k: v for k, v in rename_dict.items() if k in df.columns}, inplace=True)
        return df
    return pd.DataFrame(columns=["Dự án", "Danh mục"])

def save_mapping(df):
    df.to_csv(MAPPING_FILE, index=False)
    st.cache_data.clear()

@st.cache_data
def load_deleted():
    """Danh sách phiên đã xoá (theo khoá thời gian bắt đầu + kết thúc, dạng chuỗi)."""
    if os.path.exists(DELETED_FILE):
        return pd.read_csv(DELETED_FILE, dtype=str)
    return pd.DataFrame(columns=["Thời gian bắt đầu", "Thời gian kết thúc"])

def add_deleted(keys_df):
    """Gộp thêm các khoá thời gian vào danh sách đã xoá (keys_df có 2 cột thời gian)."""
    keys = keys_df[["Thời gian bắt đầu", "Thời gian kết thúc"]].astype(str)
    both = pd.concat([load_deleted(), keys]).drop_duplicates()
    both.to_csv(DELETED_FILE, index=False)
    st.cache_data.clear()

@st.cache_data
def load_notes():
    """Ghi chú/nhật ký theo ngày: cột Ngày (YYYY-MM-DD) + Ghi chú (text)."""
    if os.path.exists(NOTES_FILE):
        return pd.read_csv(NOTES_FILE, dtype=str).fillna("")
    return pd.DataFrame(columns=["Ngày", "Ghi chú"])

def get_note(day):
    nd = load_notes()
    m = nd[nd['Ngày'].astype(str) == str(day)]
    return str(m.iloc[0]['Ghi chú']) if not m.empty else ""

def save_note(day, text):
    """Lưu/sửa ghi chú của một ngày; nội dung rỗng = xoá ghi chú ngày đó."""
    key = str(day)
    nd = load_notes()
    nd = nd[nd['Ngày'].astype(str) != key]
    text = "" if _note_is_empty(text) else str(text).strip()
    if text:
        nd = pd.concat([nd, pd.DataFrame([{"Ngày": key, "Ghi chú": text}])], ignore_index=True)
    nd.to_csv(NOTES_FILE, index=False)
    st.cache_data.clear()


def parse_forest_csv(uploaded):
    """Đọc & chuẩn hoá CSV xuất từ Forest. Trả về (df_sạch, stats, missing_cols).
    stats gồm: raw (tổng dòng), failed (phiên thất bại), unset (unset/rỗng), valid (hợp lệ)."""
    df = pd.read_csv(uploaded).rename(columns={
        'Tag': 'Dự án', 'Project': 'Dự án',
        'Start Time': 'Thời gian bắt đầu', 'End Time': 'Thời gian kết thúc'})
    stats = {'raw': len(df), 'failed': 0, 'unset': 0, 'valid': 0}
    if 'Is Success' in df.columns:
        stats['failed'] = int((df['Is Success'] != True).sum())
        df = df[df['Is Success'] == True]
    missing = [c for c in ['Dự án', 'Thời gian bắt đầu', 'Thời gian kết thúc'] if c not in df.columns]
    if missing:
        return None, stats, missing
    df = df.dropna(subset=['Dự án'])
    df['Thời gian bắt đầu'] = pd.to_datetime(df['Thời gian bắt đầu'], errors='coerce')
    df['Thời gian kết thúc'] = pd.to_datetime(df['Thời gian kết thúc'], errors='coerce')
    df = df.dropna(subset=['Thời gian bắt đầu', 'Thời gian kết thúc'])
    _n = len(df)
    df = df[~df['Dự án'].astype(str).str.strip().str.lower().isin(['unset', ''])]
    stats['unset'] = _n - len(df)
    df['Thời lượng (Phút)'] = ((df['Thời gian kết thúc'] - df['Thời gian bắt đầu']).dt.total_seconds() / 60).round().astype(int)
    df = df[['Thời gian bắt đầu', 'Thời gian kết thúc', 'Dự án', 'Thời lượng (Phút)']]
    stats['valid'] = len(df)
    return df, stats, []


@st.cache_data
def prep_analysis_data():
    db = load_db().copy()
    mapping = load_mapping()
    if db.empty: return pd.DataFrame()
    
    if not mapping.empty:
        db = db.merge(mapping, on='Dự án', how='left')
        db['Danh mục'] = db['Danh mục'].fillna(db['Dự án'])
    else:
        db['Danh mục'] = db['Dự án']
        
    db['Thời gian bắt đầu'] = pd.to_datetime(db['Thời gian bắt đầu'], errors='coerce')
    db['Thời gian kết thúc'] = pd.to_datetime(db['Thời gian kết thúc'], errors='coerce')
    db['Ngày'] = db['Thời gian bắt đầu'].dt.date
    db['Tháng'] = db['Thời gian bắt đầu'].dt.strftime('%Y-%m')
    db['Tuần'] = db['Thời gian bắt đầu'].dt.strftime('%G-W%V') # Tuần ISO, bắt đầu Thứ Hai
    db['Khung giờ'] = db['Thời gian bắt đầu'].dt.hour
    
    db['Thứ'] = db['Thời gian bắt đầu'].dt.day_name().map(VN_DAYS)
    return db

def add_total_labels(fig, df, x_col, y_col):
    totals = df.groupby(x_col)[y_col].sum().reset_index()
    fig.add_trace(go.Scatter(
        x=totals[x_col], y=totals[y_col], mode='text', text=totals[y_col].round(1).astype(str),
        textposition='top center', showlegend=False, hoverinfo='skip', textfont=dict(color="#1d1d1f", size=13)
    ))
    fig.update_layout(yaxis=dict(range=[0, totals[y_col].max() * 1.15]))
    return fig


def add_ma_overlay(fig, scope_df, window=7):
    """Phủ đường trung bình động (theo ngày dương lịch, kể cả ngày trống) của
    tổng giờ/ngày -> cắt nhiễu, cho thấy đang lên hay xuống."""
    if scope_df.empty:
        return fig
    daily = scope_df.groupby('Ngày')['Thời lượng (Phút)'].sum() / 60
    daily.index = pd.to_datetime(daily.index)
    daily = daily.reindex(pd.date_range(daily.index.min(), daily.index.max()), fill_value=0.0)
    ma = daily.rolling(window, min_periods=1).mean()
    fig.add_trace(go.Scatter(
        x=list(ma.index), y=list(ma.values), mode='lines',
        line=dict(color='#1d1d1f', width=2.5, dash='dot'),
        name=f'TB động {window} ngày'
    ))
    return fig


def render_trend_fig(grouped, time_col, color_col, ma_df=None, cat_order=None, x_title=None):
    """Biểu đồ xu hướng dạng cột chồng theo thời gian.
    grouped: đã group theo [time_col, color_col], có cột 'Số giờ'.
    ma_df: nếu truyền (chỉ khi trục là ngày) -> phủ đường TB động 7 ngày.
    cat_order: thứ tự hạng mục cho trục x (vd các thứ trong tuần)."""
    co = {time_col: cat_order} if cat_order else None
    fig = px.bar(grouped, x=time_col, y='Số giờ', color=color_col, color_discrete_map=COLOR_MAP, category_orders=co)
    if time_col == "Ngày":
        fig = add_week_dividers(fig, grouped[time_col])
        if ma_df is not None:
            fig = add_ma_overlay(fig, ma_df, 7)
    else:
        fig = add_total_labels(fig, grouped, time_col, 'Số giờ')
    fig.update_layout(xaxis_title=x_title or time_col, yaxis_title="Số giờ")
    return format_plotly_fig(fig)

def add_week_dividers(fig, dates):
    """Kẻ đường nét đứt giữa Chủ Nhật và Thứ Hai (ranh giới tuần) cho biểu đồ theo ngày."""
    s = pd.to_datetime(pd.Series(list(dates)), errors='coerce').dropna()
    if s.empty:
        return fig
    dmin, dmax = s.min().normalize(), s.max().normalize()
    first_mon = dmin + pd.Timedelta(days=(0 - dmin.dayofweek) % 7)  # Thứ Hai đầu tiên
    d = first_mon
    while d <= dmax + pd.Timedelta(days=1):
        fig.add_vline(x=(d - pd.Timedelta(hours=12)), line_width=1, line_dash="dash", line_color="rgba(0,0,0,0.18)")
        d += pd.Timedelta(days=7)
    fig.update_xaxes(tickformat="%d/%m")  # Việt hoá: ngày/tháng dạng số, bỏ tên tháng tiếng Anh
    return fig

def format_plotly_fig(fig, is_pie=False):
    fig.update_layout(
        dragmode=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="-apple-system, BlinkMacSystemFont, sans-serif", color="#1d1d1f"),
        # Legend nằm ngang phía trên biểu đồ (giống app Xcode) -> không bị cắt khi co hẹp
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0, xanchor='left', title_text=''),
        margin=dict(t=10)
    )
    if is_pie:
        fig.update_traces(hovertemplate='<b>%{label}</b><br>%{value:.1f} giờ<extra></extra>')
    else:
        fig.update_traces(hovertemplate='<b>%{data.name}</b><br>%{y:.1f} giờ<extra></extra>')
    return fig

RANGE_OPTS = {"30 ngày": 30, "90 ngày": 90, "6 tháng": 182, "1 năm": 365, "Tất cả": None}

def filter_by_range(df_all, label):
    """Lọc df theo nhãn khoảng thời gian (mốc tính từ ngày mới nhất)."""
    days = RANGE_OPTS.get(label)
    if days is None or df_all.empty:
        return df_all
    cutoff = (pd.Timestamp(df_all['Ngày'].max()) - pd.Timedelta(days=days - 1)).date()
    return df_all[df_all['Ngày'] >= cutoff]

def range_radio(df_all, key, label="Khoảng thời gian"):
    """Segmented control chọn khoảng thời gian, trả về df đã lọc."""
    rl = st.segmented_control(label, list(RANGE_OPTS.keys()), default="90 ngày", key=key)
    return filter_by_range(df_all, rl or "90 ngày")

def fmt_month(m):
    y, mm = m.split('-')
    return f"Tháng {int(mm)}/{y}"

def fmt_week(w):
    y, wk = int(w[:4]), int(w.split('W')[1])
    mon = date.fromisocalendar(y, wk, 1)
    sun = mon + timedelta(days=6)
    return f"{mon:%d/%m} – {sun:%d/%m/%Y}"

def period_stepper(periods, key, fmt, current=None):
    """Chọn kỳ: nút lùi/tiến + selectbox nhảy nhanh + nút về kỳ hiện tại (icon Material)."""
    pk = f"{key}_pick"
    if pk not in st.session_state or st.session_state[pk] not in periods:
        st.session_state[pk] = periods[-1]
    cur_i = periods.index(st.session_state[pk])
    today_target = current if current in periods else periods[-1]

    def _step(delta):
        i = periods.index(st.session_state[pk]) if st.session_state[pk] in periods else len(periods) - 1
        st.session_state[pk] = periods[max(0, min(len(periods) - 1, i + delta))]

    def _today():
        st.session_state[pk] = today_target

    with st.container(key=f"stepper_{key}"):
        cprev, cmid, cnext, ctoday = st.columns([1, 7, 1, 1], vertical_alignment="center")
        with cprev:
            st.button("", icon=":material/chevron_left:", key=f"{key}_prev", on_click=_step, args=(-1,),
                      disabled=cur_i == 0, use_container_width=True)
        with cmid:
            st.selectbox("Kỳ", periods, key=pk, label_visibility="collapsed", format_func=fmt)
        with cnext:
            st.button("", icon=":material/chevron_right:", key=f"{key}_next", on_click=_step, args=(1,),
                      disabled=cur_i == len(periods) - 1, use_container_width=True)
        with ctoday:
            st.button("", icon=":material/today:", key=f"{key}_today", on_click=_today,
                      help="Về kỳ hiện tại", disabled=st.session_state[pk] == today_target,
                      use_container_width=True)
    return st.session_state[pk]

def day_picker(active_days):
    """Chọn ngày: ◀ ▶ nhảy tới ngày CÓ hoạt động liền kề + lịch chọn ngày + nút ngày gần nhất."""
    pk = "day_pick"
    lo, hi = active_days[0], active_days[-1]
    if pk not in st.session_state:
        st.session_state[pk] = hi
    st.session_state[pk] = min(max(st.session_state[pk], lo), hi)
    sel = st.session_state[pk]

    def _prev():
        cand = [d for d in active_days if d < st.session_state[pk]]
        if cand: st.session_state[pk] = cand[-1]

    def _next():
        cand = [d for d in active_days if d > st.session_state[pk]]
        if cand: st.session_state[pk] = cand[0]

    def _latest():
        st.session_state[pk] = hi

    with st.container(key="day_stepper"):
        c1, c2, c3, c4 = st.columns([1, 6, 1, 2], vertical_alignment="center")
        with c1:
            st.button("", icon=":material/chevron_left:", key="day_prev", on_click=_prev,
                      disabled=not [d for d in active_days if d < sel], use_container_width=True)
        with c2:
            picked = st.date_input("Ngày", value=sel, min_value=lo, max_value=hi,
                                   format="DD/MM/YYYY", label_visibility="collapsed")
        with c3:
            st.button("", icon=":material/chevron_right:", key="day_next", on_click=_next,
                      disabled=not [d for d in active_days if d > sel], use_container_width=True)
        with c4:
            st.button("Ngày gần nhất", icon=":material/keyboard_double_arrow_down:", key="day_latest",
                      on_click=_latest, disabled=sel == hi, use_container_width=True)
    if picked != st.session_state[pk]:
        st.session_state[pk] = picked
        st.rerun()
    return st.session_state[pk]

def format_relative(ts):
    """Khoảng cách từ mốc thời gian tới hiện tại, dạng tiếng Việt: '1 ngày 12 giờ trước'."""
    if pd.isna(ts):
        return "—"
    ts = pd.Timestamp(ts)
    # Khớp timezone: dữ liệu Forest có thể có tz (tz-aware) hoặc không
    now = pd.Timestamp.now(tz=ts.tz) if ts.tzinfo is not None else pd.Timestamp.now()
    secs = (now - ts).total_seconds()
    if secs < 60:
        return "vừa xong"
    days = int(secs // 86400)
    hours = int((secs % 86400) // 3600)
    mins = int((secs % 3600) // 60)
    if days > 0:
        return f"{days} ngày {hours} giờ trước"
    if hours > 0:
        return f"{hours} giờ {mins} phút trước"
    return f"{mins} phút trước"

# --- CÁC HÀM RENDER UI GLASSMORPHISM ---
def _fmt_delta(d):
    """Số nguyên thì bỏ phần thập phân (+5), số lẻ thì giữ 1 chữ số (+1.9)."""
    return f"{d:+.0f}" if abs(d - round(d)) < 1e-9 else f"{d:+.1f}"


def _delta_t(delta, label):
    """Trả về (chuỗi, màu) cho một delta, hoặc None nếu không có."""
    if delta is None:
        return None
    c = "#34c759" if delta > 0 else "#ff3b30" if delta < 0 else "#86868b"
    return (f"{_fmt_delta(delta)} {label}", c)


def render_stat_panel(hero_items, sections=None, footer=None):
    """Bảng tổng quan gọn: 1 thẻ gồm hàng số lớn (hero) + các nhóm 'chip' phụ.

    hero_items: list dict {label, value, deltas?: [(text, color)]}
    sections:   list dict {label, chips: [{k, v, delta?: (text, color), hl?: bool}]}
    footer:     (text, bg, fg) -> dòng nhắn nằm cuối thẻ (vd lời nhắc chuỗi)
    Toàn bộ HTML viết sát lề trái để Streamlit không hiểu nhầm là code block.
    """
    h = "<div class='glass-card stat-panel' style='padding:20px;'><div class='sp-hero'>"
    for it in hero_items:
        h += f"<div class='sp-hi'><div class='sp-l'>{it['label']}</div><div class='sp-v'>{it['value']}</div>"
        for txt, col in it.get('deltas', []) or []:
            h += f"<div class='sp-d' style='color:{col};'>{txt}</div>"
        h += "</div>"
    h += "</div>"
    for sec in (sections or []):
        chips = sec.get('chips') or []
        if not chips:
            continue
        h += f"<div class='sp-row'><div class='sp-sub'>{sec['label']}</div><div class='sp-chips'>"
        for c in chips:
            cls = "chip tw" if c.get('hl') else "chip"
            h += f"<span class='{cls}'><span class='ck'>{c['k']}</span><span class='cv'>{c['v']}</span>"
            if c.get('delta'):
                dt, dc = c['delta']
                h += f"<span class='cd' style='color:{dc};'>{dt}</span>"
            h += "</span>"
        h += "</div></div>"
    if footer:
        f_txt, f_bg, f_fg = footer
        h += ("<div style='margin-top:16px;padding-top:14px;border-top:1px solid rgba(0,0,0,0.07);text-align:center;'>"
              f"<span style='background:{f_bg};color:{f_fg};font-size:14px;font-weight:500;padding:7px 16px;border-radius:11px;'>{f_txt}</span></div>")
    h += "</div>"
    st.markdown(h, unsafe_allow_html=True)


def render_top_3(df, col_name, title, week_key=None, n=3):
    if df.empty:
        html_list = "<p style='color:#86868b; font-size: 14px;'>Không có dữ liệu</p>"
    else:
        top3 = df.groupby(col_name)['Thời lượng (Phút)'].sum().sort_values(ascending=False).head(n)
        # Thời gian của từng nhóm/dự án trong tuần này (nếu được yêu cầu)
        wk = {}
        if week_key is not None and 'Tuần' in df.columns:
            wk = (df[df['Tuần'] == week_key].groupby(col_name)['Thời lượng (Phút)'].sum() / 60).to_dict()
        html_list = "<ul style='margin:0; padding-left: 20px; color: #1d1d1f; font-size: 15px; line-height: 1.6;'>"
        for k, v in top3.items():
            wh = wk.get(k, 0)
            wsuf = f" <span style='color:#007aff; font-size:13px;'>({wh:.1f}h tuần này)</span>" if wh > 0.05 else ""
            html_list += f"<li><span style='font-weight:600;'>{html_escape(str(k))}</span>: {v/60:.1f}h{wsuf}</li>"
        html_list += "</ul>"
    
    html = f"""
    <div class="glass-card" style="height: 100%;">
        <p style="margin: 0 0 12px 0; font-size: 13px; color: #86868b; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">{title}</p>
        {html_list}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# Phân nhóm độ dài phiên (phút): tên, khoảng hiển thị, [lo, hi), màu — mốc cố định
SESSION_BUCKETS = [
    ("Tối thiểu", "= 10′",  0,   11,    "#dce9fb"),
    ("Ngắn",      "< 25′",  11,  25,    "#a9ccf4"),
    ("Trung bình","25–<50′",25,  50,    "#7fb5ff"),
    ("Dài",       "50–<90′",50,  90,    "#2f86ec"),
    ("Rất Dài",   "≥ 90′",  90,  10**9, "#0a52c4"),
]
LEN_THRESHOLDS = (25, 50, 90)  # mốc tham chiếu trên histogram

def _avg_session_min(df):
    """Độ dài bình quân mỗi phiên (phút); 0 nếu chưa có phiên."""
    n = len(df)
    return (df['Thời lượng (Phút)'].sum() / n) if n else 0.0

def render_session_bar(df):
    """Thanh phân bố độ dài phiên theo 4 nhóm (mốc 25/50/90) — gọn cho phần Tổng quan."""
    n = len(df)
    if n == 0:
        return
    d = df['Thời lượng (Phút)']
    counts = [int(((d >= lo) & (d < hi)).sum()) for _, _, lo, hi, _ in SESSION_BUCKETS]
    seg = ""
    for (name, rng, lo, hi, col), c in zip(SESSION_BUCKETS, counts):
        if not c:
            continue
        pct = c / n * 100
        lbl = f"{pct:.0f}%" if pct >= 9 else ""
        fg = "#fff" if col in ("#2f86ec", "#0a52c4") else "#1d1d1f"
        seg += (f"<div title='{name} ({rng}): {c} phiên' style='width:{pct:.4f}%;background:{col};color:{fg};"
                f"font-size:12px;font-weight:600;display:flex;align-items:center;justify-content:center;'>{lbl}</div>")
    legend = ""
    for (name, rng, lo, hi, col), c in zip(SESSION_BUCKETS, counts):
        legend += (f"<span style='display:inline-flex;align-items:center;gap:5px;margin:0 14px 4px 0;font-size:13px;color:#1d1d1f;'>"
                   f"<span style='display:inline-block;width:11px;height:11px;border-radius:3px;background:{col};'></span>"
                   f"{name} <span style='color:#86868b;'>{rng}</span> · <b>{c}</b></span>")
    st.markdown(
        "<div class='glass-card' style='padding:16px 18px;margin-top:14px;'>"
        "<div style='font-size:11px;color:#86868b;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;'>Phân bố độ dài phiên</div>"
        f"<div style='display:flex;height:24px;border-radius:8px;overflow:hidden;'>{seg}</div>"
        f"<div style='margin-top:12px;'>{legend}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

def render_session_histogram(df):
    """Histogram độ dài phiên (bin 5 phút, từ 10′) + đường mốc 25/50/90 và đường trung bình."""
    n = len(df)
    if n == 0:
        st.info("Chưa có phiên nào trong phạm vi này.")
        return
    d = df['Thời lượng (Phút)'].astype(float)
    start, top, step = 10, 60, 5
    edges = list(range(start, top + 1, step))
    counts = [int(((d >= edges[i]) & (d < edges[i + 1])).sum()) for i in range(len(edges) - 1)]
    counts[0] += int((d < start).sum())  # gộp phiên ngắn bất thường (nếu có) vào bin đầu
    counts.append(int((d >= top).sum()))
    centers = [edges[i] + step / 2 for i in range(len(edges) - 1)] + [top + step / 2]
    labels = [f"{edges[i]}–{edges[i + 1]}′" for i in range(len(edges) - 1)] + [f"≥ {top}′"]

    fig = go.Figure(go.Bar(
        x=centers, y=counts, width=step * 0.88, marker_color='#7fb5ff',
        customdata=labels, hovertemplate='%{customdata}: %{y} phiên<extra></extra>',
    ))
    for t in LEN_THRESHOLDS:
        if start < t <= top:
            fig.add_vline(x=t, line=dict(color='#0a52c4', width=1.5, dash='dot'))
    avg = d.mean()
    if start <= avg <= top + step:
        fig.add_vline(x=avg, line=dict(color='#1d1d1f', width=2, dash='dash'),
                      annotation_text=f"TB {avg:.0f}′", annotation_position="top right",
                      annotation_font=dict(size=12, color='#1d1d1f'))
    fig.update_layout(
        height=300, margin=dict(l=10, r=10, t=24, b=10), bargap=0.06, showlegend=False,
        xaxis=dict(title='Độ dài phiên (phút)', range=[start - 2, top + step],
                   tickvals=[10, 20, 30, 40, 50, 60],
                   ticktext=['10', '20', '30', '40', '50', '60+'],
                   tickfont=dict(size=12), showgrid=False),
        yaxis=dict(title='Số phiên', tickfont=dict(size=12), gridcolor='rgba(0,0,0,0.06)'),
        plot_bgcolor='white', paper_bgcolor='white',
    )
    st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)


# Dải buổi trong ngày (nền biểu đồ khung giờ): tên, giờ bắt đầu, giờ kết thúc, màu nền
BUOI_BANDS = [
    ("Khuya", 0, 5, "rgba(88,86,214,0.05)"),
    ("Sáng", 5, 11, "rgba(255,204,0,0.08)"),
    ("Chiều", 11, 17, "rgba(255,149,0,0.06)"),
    ("Tối", 17, 22, "rgba(0,122,255,0.05)"),
    ("Khuya ", 22, 24, "rgba(88,86,214,0.05)"),  # dấu cách để không trùng nhãn với buổi Khuya đầu
]


def _buoi_of(h):
    if 5 <= h < 11: return "Sáng"
    if 11 <= h < 17: return "Chiều"
    if 17 <= h < 22: return "Tối"
    return "Khuya"


def _explode_session_hours(scope_df, key_col):
    """Trải thời lượng MỖI phiên ra các khung giờ nó thực sự đi qua (thay vì dồn hết
    vào giờ bắt đầu). Trả về DataFrame (key_col, Khung giờ, giờ)."""
    out = []
    for s, e, k in zip(scope_df['Thời gian bắt đầu'], scope_df['Thời gian kết thúc'], scope_df[key_col]):
        if pd.isna(s) or pd.isna(e) or e <= s:
            continue
        cur = s
        while cur < e:
            nxt = cur.floor('h') + pd.Timedelta(hours=1)
            seg_end = e if e < nxt else nxt
            out.append((k, int(cur.hour), (seg_end - cur).total_seconds() / 3600.0))
            cur = seg_end
    return pd.DataFrame(out, columns=[key_col, 'Khung giờ', 'giờ'])


def render_hourly_chart(scope_df, color_col, x_title="Khung giờ (0h - 23h)"):
    if scope_df.empty:
        return
    num_days = scope_df['Ngày'].nunique() or 1
    dist = _explode_session_hours(scope_df, color_col)
    if dist.empty:
        return
    dist['giờ'] = dist['giờ'] / num_days  # trung bình mỗi ngày có hoạt động

    hr_group = dist.groupby(['Khung giờ', color_col])['giờ'].sum().reset_index().rename(columns={'giờ': 'Số giờ'})
    fig = px.bar(hr_group, x='Khung giờ', y='Số giờ', color=color_col, color_discrete_map=COLOR_MAP)

    tot = dist.groupby('Khung giờ')['giờ'].sum().reindex(range(24), fill_value=0.0)
    fig.add_trace(go.Scatter(
        x=list(tot.index), y=list(tot.values), mode='lines+markers',
        line=dict(color=MAC_COLORS[0], width=2, shape='spline'),
        marker=dict(size=5, color=MAC_COLORS[0]),
        name='Tổng cộng'
    ))

    # Dải nền theo buổi để dễ đọc "sáng/chiều/tối/khuya".
    # Chừa lề hai bên (PAD) để cột giờ 0 và giờ 23 không bị khung biểu đồ che.
    PAD = 0.7
    _last = len(BUOI_BANDS) - 1
    for i, (name, x0, x1, col) in enumerate(BUOI_BANDS):
        lo = -PAD if i == 0 else x0 - 0.5
        hi = 23 + PAD if i == _last else x1 - 0.5
        fig.add_vrect(x0=lo, x1=hi, fillcolor=col, opacity=1, layer="below", line_width=0,
                      annotation_text=name.strip(), annotation_position="top left",
                      annotation=dict(font_size=11, font_color="#9a9aa0"))

    y_max = float(tot.max()) or 1.0
    fig.update_layout(width=CHART_WIDTH, xaxis_title=x_title, yaxis_title="Trung bình giờ/ngày",
                      yaxis=dict(range=[0, y_max * 1.28]),
                      xaxis=dict(range=[-PAD, 23 + PAD], dtick=2))
    fig = format_plotly_fig(fig)
    fig.update_traces(hovertemplate='<b>%{data.name}</b><br>%{y:.2f} h/ngày<extra></extra>')
    st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)

    # Tự nêu "giờ vàng" + buổi mạnh nhất, đặt trong glass card cho đồng bộ
    if tot.max() > 0:
        peak_h = int(tot.idxmax())
        strong_buoi = tot.groupby(_buoi_of).sum().idxmax()
        _lbl = "font-size:13px;color:#86868b;font-weight:500;text-transform:uppercase;letter-spacing:0.5px;"
        _val = "font-size:17px;color:#1d1d1f;font-weight:600;"
        st.markdown(
            "<div class='glass-card' style='display:flex;flex-wrap:wrap;justify-content:center;align-items:center;"
            "gap:6px 16px;max-width:900px;margin:8px auto 0 auto;padding:12px 18px;'>"
            f"<span style='{_lbl}'>Giờ tập trung nhất</span>"
            f"<span style='{_val}'>{peak_h}h</span>"
            f"<span style='font-size:13px;color:#86868b;'>(TB {tot.max():.1f}h/ngày)</span>"
            "<span style='color:#d2d2d7;'>·</span>"
            f"<span style='{_lbl}'>Buổi mạnh nhất</span>"
            f"<span style='{_val}'>{strong_buoi}</span>"
            "</div>",
            unsafe_allow_html=True,
        )


def render_dayhour_heatmap(scope_df):
    """Bản đồ nhiệt 7 thứ × 24 giờ: ô càng đậm = trung bình giờ/ngày ở khung giờ đó
    của thứ đó càng cao -> nhận ra 'tập trung tốt nhất vào sáng thứ mấy'."""
    if scope_df.empty:
        return
    d = _explode_session_hours(scope_df, 'Thứ')
    if d.empty:
        return
    span = pd.date_range(pd.Timestamp(scope_df['Ngày'].min()), pd.Timestamp(scope_df['Ngày'].max()))
    wd_count = pd.Series(span.day_name()).map(VN_DAYS).value_counts()

    grp = d.groupby(['Thứ', 'Khung giờ'])['giờ'].sum()
    full = pd.MultiIndex.from_product([DAYS_ORDER, range(24)], names=['Thứ', 'Khung giờ'])
    cell = grp.reindex(full, fill_value=0.0).reset_index(name='giờ')
    cell['TB'] = cell.apply(lambda r: r['giờ'] / max(int(wd_count.get(r['Thứ'], 1)), 1), axis=1)

    chart = alt.Chart(cell).mark_rect(cornerRadius=2).encode(
        x=alt.X('Khung giờ:O', title='Khung giờ (0h - 23h)',
                axis=alt.Axis(labelAngle=0, values=list(range(0, 24, 2)), tickSize=0, domain=False)),
        y=alt.Y('Thứ:O', sort=DAYS_ORDER, title='', axis=alt.Axis(tickSize=0, domain=False)),
        color=alt.Color('TB:Q', scale=alt.Scale(range=['#eef0f3', '#1f8f43']), legend=None),
        tooltip=[alt.Tooltip('Thứ:N'), alt.Tooltip('Khung giờ:O', title='Giờ'),
                 alt.Tooltip('TB:Q', title='TB giờ/ngày', format='.2f')],
    ).properties(height=alt.Step(26)).configure_view(strokeWidth=0)
    st.altair_chart(chart, width='stretch')


def _streak_stats(streak_df):
    """Số liệu chuỗi ngày trên toàn lịch sử: tổng số ngày có hoạt động, chuỗi
    dài nhất, chuỗi hiện tại (còn hiệu lực nếu lần gần nhất là hôm nay/hôm qua),
    và gap = số ngày kể từ lần gần nhất."""
    u = pd.Series(pd.to_datetime(streak_df['Ngày'].dropna().unique())).sort_values().reset_index(drop=True)
    if len(u) == 0:
        return {"total": 0, "longest": 0, "current": 0, "gap": None}
    sid = (u.diff().dt.days > 1).cumsum()
    counts = sid.value_counts()
    gap = int((pd.Timestamp(date.today()) - u.max()).days)
    current = int(counts[sid.iloc[-1]]) if gap <= 1 else 0
    return {"total": int(len(u)), "longest": int(counts.max()), "current": current, "gap": gap}


NUDGE_TONES = {"good": ("rgba(52,199,89,0.12)", "#248a3d"),
               "warn": ("rgba(255,149,0,0.15)", "#a85d00"),
               "neutral": ("rgba(0,0,0,0.05)", "#6e6e73")}


def _streak_nudge(s):
    """Lời nhắc chuỗi theo trạng thái -> (text, tone) hoặc None (chỉ theo dõi)."""
    if not s["total"] or s["gap"] is None:
        return None
    gap, cur, lon = s["gap"], s["current"], s["longest"]
    if gap == 0 and cur >= lon:
        return (f"Bạn đang giữ chuỗi {cur} ngày — dài nhất từ trước tới nay. Giữ vững nhé!", "good")
    if gap == 0:
        return (f"Đang có chuỗi {cur} ngày. Còn {lon - cur + 1} ngày nữa là chạm kỷ lục {lon} ngày.", "good")
    if gap == 1:
        return (f"Chuỗi {cur} ngày đang treo — hôm nay chưa có hoạt động. Trồng một cây để giữ mạch!", "warn")
    return (f"Chuỗi gần nhất đã dừng {gap} ngày. Hôm nay là lúc tốt để bắt đầu lại.", "neutral")


def _weekday_avg(scope_df):
    """Trung bình giờ mỗi ngày theo thứ (tính cả ngày trống) trên span của scope_df."""
    if scope_df.empty:
        return pd.Series(dtype=float)
    mn, mx = pd.Timestamp(scope_df['Ngày'].min()), pd.Timestamp(scope_df['Ngày'].max())
    wd_count = pd.Series(pd.date_range(mn, mx).day_name()).map(VN_DAYS).value_counts()
    by = scope_df.groupby('Thứ')['Thời lượng (Phút)'].sum() / 60
    return (by / wd_count).reindex(DAYS_ORDER).dropna()


def render_reading_log(df_books, latest_overall, recency_days=14):
    """Bảng + timeline + tóm tắt cho từng cuốn sách (đọc tuần tự) trong nhóm.
    Chỉ đọc & tính toán -> không đụng tới dữ liệu lưu trữ."""
    if df_books.empty:
        st.info("Chưa có dữ liệu sách trong nhóm này.")
        return
    rows = []
    for book, g in df_books.groupby('Dự án'):
        days = pd.to_datetime(g['Ngày'])
        start, last = days.min(), days.max()
        span_days = int((last - start).days) + 1
        hrs = g['Thời lượng (Phút)'].sum() / 60
        per_week = hrs / max(span_days / 7, 1 / 7)
        ongoing = (pd.Timestamp(latest_overall) - last).days <= recency_days
        rows.append({
            'Cuốn sách': book, 'Bắt đầu': start, 'Gần nhất': last,
            'Số ngày': span_days, 'Ngày đọc': g['Ngày'].nunique(),
            'Tổng giờ': round(hrs, 1), 'Số phiên': len(g), 'Giờ/tuần': round(per_week, 1),
            'Trạng thái': 'Đang đọc' if ongoing else 'Đã xong',
        })
    t = pd.DataFrame(rows).sort_values('Bắt đầu').reset_index(drop=True)

    done = t[t['Trạng thái'] == 'Đã xong']
    reading = t[t['Trạng thái'] == 'Đang đọc']

    # Số liệu đầu mục: panel thẻ giống "Tổng quan"
    _secs = []
    if len(done):
        _secs.append({"label": "Đã xong", "chips": [
            {"k": "Số cuốn", "v": f"{len(done)}"},
            {"k": "TB giờ/cuốn", "v": f"{done['Tổng giờ'].mean():.1f}h"},
            {"k": "TB ngày/cuốn", "v": f"{done['Số ngày'].mean():.0f}"},
        ]})
        top = done.loc[done['Tổng giờ'].idxmax()]
        fast = done.loc[done['Số ngày'].idxmin()]
        _secs.append({"label": "Nổi bật", "chips": [
            {"k": "Nhiều giờ nhất", "v": f"{top['Cuốn sách']} ({top['Tổng giờ']:.1f}h)"},
            {"k": "Đọc nhanh nhất", "v": f"{fast['Cuốn sách']} ({int(fast['Số ngày'])} ngày)"},
        ]})
    if len(reading):
        _secs.append({"label": "Đang đọc", "chips": [
            {"k": r['Cuốn sách'], "v": f"{r['Tổng giờ']:.1f}h", "hl": True}
            for _, r in reading.iterrows()
        ]})
    render_stat_panel(
        hero_items=[
            {"label": "Số cuốn", "value": f"{len(t)}"},
            {"label": "Tổng giờ", "value": f"{t['Tổng giờ'].sum():.1f}h"},
        ],
        sections=_secs,
    )

    # Timeline trình tự đọc — tự vẽ HTML/CSS (trục tháng tiếng Việt, thanh bo tròn)
    tmin = pd.to_datetime(t['Bắt đầu']).min().normalize().replace(day=1)
    tmax = pd.to_datetime(t['Gần nhất']).max().normalize().replace(day=1) + pd.offsets.MonthEnd(1)
    total = max((tmax - tmin).days, 1)
    multiyear = tmin.year != tmax.year

    def _pct(d):
        return (pd.Timestamp(d).normalize() - tmin).days / total * 100

    months = pd.date_range(tmin, tmax, freq='MS')
    grid_html = ''.join(f'<div class="rtl-grid" style="left:{_pct(m):.3f}%"></div>' for m in months)
    axis_html = ''.join(
        f'<span class="rtl-tick" style="left:{_pct(m):.3f}%">Th{m.month}'
        + (f"<span class='rtl-yr'>’{m.year % 100:02d}</span>" if multiyear and m.month == 1 else "")
        + '</span>' for m in months)

    bars_html = ''
    for _, r in t.iterrows():
        left = _pct(r['Bắt đầu'])
        width = max((pd.Timestamp(r['Gần nhất']) - pd.Timestamp(r['Bắt đầu'])).days + 1, 1) / total * 100
        cls = 'reading' if r['Trạng thái'] == 'Đang đọc' else 'done'
        bars_html += (f'<div class="rtl-row"><div class="rtl-name">{html_escape(str(r["Cuốn sách"]))}</div>'
                      f'<div class="rtl-track">{grid_html}'
                      f'<div class="rtl-bar {cls}" style="left:{left:.3f}%;width:{width:.3f}%"></div></div></div>')

    st.markdown(f"""
<style>
.rtl-card{{background:#fff;border:1px solid rgba(0,0,0,0.06);border-radius:14px;box-shadow:0 4px 15px rgba(0,0,0,0.04);padding:16px 18px;margin-top:14px;}}
.rtl-legend{{display:flex;gap:16px;margin:0 0 10px 152px;font-size:12px;color:#6e6e73;}}
.rtl-legend i{{display:inline-block;width:11px;height:11px;border-radius:3px;vertical-align:-1px;margin-right:5px;}}
.rtl-row{{display:grid;grid-template-columns:144px 1fr;align-items:center;height:32px;}}
.rtl-name{{font-size:13px;font-weight:600;color:#1d1d1f;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:8px;}}
.rtl-track{{position:relative;height:32px;}}
.rtl-grid{{position:absolute;top:0;bottom:0;width:1px;background:rgba(0,0,0,0.05);}}
.rtl-bar{{position:absolute;top:7px;height:18px;border-radius:6px;min-width:6px;}}
.rtl-bar.done{{background:#aeaeb2;}}
.rtl-bar.reading{{background:#007aff;}}
.rtl-axis{{display:grid;grid-template-columns:144px 1fr;margin-top:3px;}}
.rtl-ticks{{position:relative;height:16px;}}
.rtl-tick{{position:absolute;font-size:11px;color:#86868b;white-space:nowrap;}}
.rtl-yr{{color:#c7c7cc;margin-left:1px;}}
</style>
<div class="rtl-card">
<div class="rtl-legend"><span><i style="background:#007aff;"></i>Đang đọc</span><span><i style="background:#aeaeb2;"></i>Đã xong</span></div>
{bars_html}
<div class="rtl-axis"><div></div><div class="rtl-ticks">{axis_html}</div></div>
</div>
""", unsafe_allow_html=True)

    # Bảng số liệu: dùng cùng style (DTBL) với mục 5 "Bảng số liệu"
    vmax_h = float(t['Tổng giờ'].max()) if len(t) else 0.0
    rows_html = ''
    for _, r in t.iterrows():
        s_col = '#007aff' if r['Trạng thái'] == 'Đang đọc' else '#86868b'
        start_s = pd.to_datetime(r['Bắt đầu']).strftime('%d/%m/%Y')
        last_s = pd.to_datetime(r['Gần nhất']).strftime('%d/%m/%Y')
        rows_html += '<tr class="prow">'
        rows_html += f'<td class="lbl">{html_escape(str(r["Cuốn sách"]))}</td>'
        rows_html += f'<td>{start_s}</td><td>{last_s}</td>'
        rows_html += f'<td>{int(r["Số ngày"])}</td><td>{int(r["Ngày đọc"])}</td>'
        rows_html += _heat_cell(float(r['Tổng giờ']), vmax_h)
        rows_html += f'<td>{int(r["Số phiên"])}</td><td>{r["Giờ/tuần"]:.1f}</td>'
        rows_html += f'<td class="txt" style="color:{s_col};font-weight:600;">{r["Trạng thái"]}</td>'
        rows_html += '</tr>'
    st.markdown(DTBL_CSS + f"""
<div class="dtbl-wrap"><table class="dtbl">
<thead><tr><th class="lbl">Cuốn sách</th><th>Bắt đầu</th><th>Gần nhất</th><th>Số ngày</th><th>Ngày đọc</th><th>Tổng giờ</th><th>Số phiên</th><th>Giờ/tuần</th><th class="txt">Trạng thái</th></tr></thead>
<tbody>{rows_html}</tbody>
</table></div>
""", unsafe_allow_html=True)


def render_day_timeline(day_df, sel, df_all):
    """Dòng thời gian trong ngày (0–24h): khối phiên tô màu theo dự án, kèm lớp mờ
    'khung giờ điển hình của thứ này' để thấy hôm nay lệch nhịp ra sao."""
    if day_df.empty:
        return
    vn_dow = VN_DAYS.get(pd.Timestamp(sel).day_name(), "")

    # Lớp mờ: khung giờ điển hình của cùng thứ (TB giờ tại mỗi giờ-trong-ngày), trừ ngày đang xem
    same = df_all[(pd.to_datetime(df_all['Ngày']).dt.day_name() == pd.Timestamp(sel).day_name())
                  & (df_all['Ngày'] != sel)]
    n_same = same['Ngày'].nunique()
    typ = {}
    if n_same:
        per_hour = _explode_session_hours(same, 'Ngày').groupby('Khung giờ')['giờ'].sum() / n_same
        mx = float(per_hour.max()) if len(per_hour) else 0.0
        if mx > 0:
            typ = {int(h): v / mx for h, v in per_hour.items()}
    typ_html = ''.join(
        f'<div class="dtl-typ" style="left:{h/24*100:.3f}%;width:{100/24:.3f}%;'
        f'background:rgba(120,120,128,{0.04 + typ.get(h, 0) * 0.20:.3f});"></div>' for h in range(24)) if typ else ''

    line_html = ''.join(f'<div class="dtl-line" style="left:{b/24*100:.3f}%;"></div>' for b in (5, 11, 17, 22))
    label_html = ''.join(
        f'<span class="dtl-bl" style="left:{(s + e) / 2 / 24 * 100:.3f}%;">{nm.strip().upper()}</span>'
        for nm, s, e, _ in BUOI_BANDS if (e - s) >= 3)

    bars_html = ''
    for _, r in day_df.sort_values('Thời gian bắt đầu').iterrows():
        s = pd.Timestamp(r['Thời gian bắt đầu']); e = pd.Timestamp(r['Thời gian kết thúc'])
        s_min = s.hour * 60 + s.minute
        left = s_min / 1440 * 100
        width = min(max(float(r['Thời lượng (Phút)']), 6), 1440 - s_min) / 1440 * 100
        proj = str(r['Dự án'])
        lab = proj if width > 5.5 else ''
        bars_html += (f'<div class="dtl-bar" title="{html_escape(proj)}: {s:%H:%M}–{e:%H:%M}" '
                      f'style="left:{left:.3f}%;width:{width:.3f}%;background:{COLOR_MAP.get(proj, "#8e8e93")};">'
                      f'{html_escape(lab)}</div>')

    ticks_html = ''.join(
        f'<span class="dtl-tk" style="left:{h/24*100:.3f}%;">{h}{"h" if h in (0, 24) else ""}</span>'
        for h in range(0, 25, 3))
    projs = list(dict.fromkeys(day_df.sort_values('Thời gian bắt đầu')['Dự án'].astype(str)))
    legend_html = ''.join(
        f'<span><i style="background:{COLOR_MAP.get(p, "#8e8e93")};"></i>{html_escape(p)}</span>' for p in projs)

    st.markdown(f"""
<style>
.dtl-card{{background:#fff;border:1px solid rgba(0,0,0,0.06);border-radius:14px;box-shadow:0 4px 15px rgba(0,0,0,0.04);padding:14px 18px;margin-top:14px;}}
.dtl-strip{{position:relative;height:16px;margin-bottom:3px;}}
.dtl-bl{{position:absolute;transform:translateX(-50%);font-size:10px;font-weight:600;letter-spacing:.4px;color:#aeaeb2;}}
.dtl-track{{position:relative;height:76px;border-radius:10px;overflow:hidden;border:1px solid rgba(0,0,0,0.06);background:#fcfcfd;}}
.dtl-typ{{position:absolute;top:0;bottom:0;}}
.dtl-line{{position:absolute;top:0;bottom:0;width:1px;background:rgba(0,0,0,0.06);}}
.dtl-bar{{position:absolute;top:14px;height:48px;min-width:4px;border-radius:4px;display:flex;align-items:center;justify-content:center;padding:0 6px;color:#fff;font-size:11.5px;font-weight:600;white-space:nowrap;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.18);}}
.dtl-axis{{position:relative;height:16px;margin-top:4px;}}
.dtl-tk{{position:absolute;transform:translateX(-50%);font-size:11px;color:#86868b;}}
.dtl-legend{{display:flex;flex-wrap:wrap;gap:14px;margin-top:12px;font-size:12.5px;color:#3a3a3c;}}
.dtl-legend i{{display:inline-block;width:11px;height:11px;border-radius:3px;vertical-align:-1px;margin-right:5px;}}
.dtl-ttl{{font-size:11px;color:#86868b;font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px;}}
</style>
<div class="dtl-card">
<div class="dtl-ttl">Dòng thời gian trong ngày</div>
<div class="dtl-strip">{label_html}</div>
<div class="dtl-track">{typ_html}{line_html}{bars_html}</div>
<div class="dtl-axis">{ticks_html}</div>
<div class="dtl-legend">{legend_html}</div>
</div>
""", unsafe_allow_html=True)


def render_note_editor(day):
    """Ghi chú một ngày, gói trong thẻ. Mặc định chỉ hiện ghi chú đã lưu (hoặc trạng thái
    trống) kèm một nút; bấm nút mới mở trình soạn (Quill) inline với Cập nhật/Huỷ/Xoá."""
    cur = get_note(day)
    edit_key = f"note_edit_{day}"
    quill_key = f"note_quill_{day}"

    def _enter_edit():
        # Xoá trạng thái cũ của ô soạn để khởi tạo lại đúng nội dung đang lưu
        st.session_state.pop(quill_key, None)
        st.session_state[edit_key] = True

    with st.container(border=True, key="note_card"):
        if not st.session_state.get(edit_key, False):
            # Chế độ xem: chỉ ghi chú + 1 nút
            if cur:
                with st.container(key="note_saved"):
                    st.markdown(cur, unsafe_allow_html=True)
                if st.button("Sửa ghi chú", icon=":material/edit:", key=f"note_editbtn_{day}"):
                    _enter_edit()
                    st.rerun()
            else:
                st.markdown("<div class='note-empty'>Chưa có ghi chú cho ngày này.</div>",
                            unsafe_allow_html=True)
                if st.button("Thêm ghi chú", icon=":material/add:", type="primary",
                             key=f"note_addbtn_{day}"):
                    _enter_edit()
                    st.rerun()
        else:
            # Chế độ soạn: trình soạn Quill inline + Cập nhật / Huỷ / Xoá
            content = st_quill(value=cur, html=True, toolbar=NOTE_TOOLBAR,
                               placeholder="Viết vài dòng về ngày này…", key=quill_key)
            c1, c2, _, c4 = st.columns([2, 2, 2, 3])
            with c1:
                if st.button("Cập nhật", icon=":material/check:", type="primary",
                             key=f"note_save_{day}", use_container_width=True):
                    save_note(day, content if content is not None else st.session_state.get(quill_key, ""))
                    st.session_state[edit_key] = False
                    st.rerun()
            with c2:
                if st.button("Huỷ", icon=":material/close:", key=f"note_cancel_{day}",
                             use_container_width=True):
                    st.session_state[edit_key] = False
                    st.rerun()
            with c4:
                if cur and st.button("Xoá ghi chú", icon=":material/delete:",
                                     key=f"note_del_{day}", use_container_width=True):
                    save_note(day, "")
                    st.session_state[edit_key] = False
                    st.rerun()
            st.caption("Mẹo: bôi đen rồi ⌘/Ctrl+B để in đậm, Tab để thụt lề. "
                       "Ghi chú lưu theo ngày, độc lập với dữ liệu phiên.")


def render_notes_journal(period_key, kind):
    """Liệt kê (chỉ đọc) ghi chú của các ngày thuộc một kỳ (tuần/tháng)."""
    nd = load_notes()
    if not nd.empty:
        nd = nd.assign(_d=pd.to_datetime(nd['Ngày'], errors='coerce')).dropna(subset=['_d'])
        if kind == 'month':
            nd = nd[nd['_d'].dt.strftime('%Y-%m') == period_key]
        else:
            nd = nd[nd['_d'].dt.strftime('%G-W%V') == period_key]
        nd = nd.sort_values('_d')
    if nd.empty:
        st.caption("Chưa có ghi chú nào trong kỳ này. Thêm ghi chú ở tab **Báo cáo ngày**.")
        return
    with st.container(border=True, key="jcard_journal"):
        for _, r in nd.iterrows():
            d = r['_d']
            c1, c2 = st.columns([1, 5], vertical_alignment="top")
            with c1:
                st.markdown(f"<div class='jdate'><div class='jdowbig'>{VN_DAYS.get(d.day_name(), '')}</div>"
                            f"<div class='jdm'>{d:%d/%m}</div></div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div class='note-html'>{str(r['Ghi chú'])}</div>", unsafe_allow_html=True)


def render_on_this_day(sel, df_all):
    """“Ngày này năm trước”: khớp cùng ngày/tháng ở các năm trước (từ phiên + ghi chú),
    mỗi năm hiện vài số liệu trong khung chip + ghi chú (nếu có). Chỉ đọc."""
    m, d = sel.month, sel.day
    # Số liệu phiên theo từng năm trước (cùng ngày/tháng)
    sess = df_all[df_all['Ngày'].apply(lambda x: x.month == m and x.day == d and x.year < sel.year)]
    stats = {}  # year -> (hours, sessions)
    if not sess.empty:
        for y, g in sess.groupby(sess['Ngày'].apply(lambda x: x.year)):
            stats[int(y)] = (g['Thời lượng (Phút)'].sum() / 60, len(g))
    # Ghi chú cùng ngày/tháng ở các năm trước
    notes = {}  # year -> text
    nd = load_notes()
    if not nd.empty:
        nd = nd.assign(_d=pd.to_datetime(nd['Ngày'], errors='coerce')).dropna(subset=['_d'])
        nd = nd[(nd['_d'].dt.month == m) & (nd['_d'].dt.day == d) & (nd['_d'].dt.year < sel.year)]
        for _, r in nd.iterrows():
            notes[int(r['_d'].year)] = str(r['Ghi chú'])

    years = sorted(set(stats) | set(notes), reverse=True)
    if not years:
        _cal = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='34' height='34' "
                "fill='#c7c7cc'><path d='M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 "
                "2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2z'/></svg>")
        st.markdown(
            "<div class='glass-card' style='padding:22px 18px;text-align:center;'>"
            f"<div style='margin-bottom:8px;'>{_cal}</div>"
            "<div style='font-size:1.0rem;font-weight:600;color:#1d1d1f;'>"
            f"Chưa có dữ liệu ngày {d:02d}/{m:02d} ở các năm trước</div>"
            "<div style='font-size:13px;color:#86868b;margin-top:4px;'>"
            "Mục này sẽ dày dần theo thời gian — cứ ghi chú &amp; tích lũy mỗi ngày.</div></div>",
            unsafe_allow_html=True)
        return

    def _chip(k, v):
        return f"<span class='jchip'><span class='ck'>{k}</span><span class='cv'>{v}</span></span>"

    with st.container(border=True, key="jcard_otd"):
        for y in years:
            wd = VN_DAYS.get(pd.Timestamp(date(y, m, d)).day_name(), "")
            c1, c2 = st.columns([1, 5], vertical_alignment="top")
            with c1:
                st.markdown(f"<div class='jdate'><div class='jyear'>{y}</div>"
                            f"<div class='jdow'>{wd}</div><div class='jdm'>{d:02d}/{m:02d}</div></div>",
                            unsafe_allow_html=True)
            with c2:
                if y in stats:
                    hrs, ss = stats[y]
                    avg = (hrs * 60 / ss) if ss else 0
                    chips = _chip("Giờ", f"{hrs:.1f}h") + _chip("Số phiên", f"{ss}") + _chip("TB", f"{avg:.0f}′")
                else:
                    chips = "<span style='font-size:13px;color:#aeaeb2;'>Không có phiên tập trung</span>"
                st.markdown(f"<div style='margin-bottom:6px;'>{chips}</div>", unsafe_allow_html=True)
                if notes.get(y):
                    st.markdown(f"<div class='note-html'>{notes[y]}</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<span style='font-size:13px;color:#aeaeb2;'>(không có ghi chú)</span>",
                                unsafe_allow_html=True)
        st.markdown(f"<div class='otd-foot'>Khớp theo ngày <b>{d:02d}/{m:02d}</b> ở các năm trước. "
                    "Mục này sẽ dày dần theo thời gian.</div>", unsafe_allow_html=True)


def render_calendar_grid(scope_df, full_df):
    """Chỉ vẽ lưới lịch nhiệt kiểu GitHub (không kèm số liệu chuỗi)."""
    min_date = pd.Timestamp(scope_df['Ngày'].min())
    max_date = pd.Timestamp(full_df['Ngày'].max())
    # Mở rộng ra trọn tuần (Chủ Nhật -> Thứ Bảy) để lưới luôn đầy đủ ô,
    # tránh ô trắng lẻ ở tuần đầu/cuối -> nền đồng nhất như kiểu GitHub.
    start = min_date - pd.Timedelta(days=min_date.dayofweek)
    end = max_date + pd.Timedelta(days=6 - max_date.dayofweek)
    all_dates = pd.date_range(start=start, end=end)
    cal_data = pd.DataFrame({'Ngày': all_dates})

    cal_data['Tuần_Bắt_Đầu'] = cal_data['Ngày'] - pd.to_timedelta(cal_data['Ngày'].dt.dayofweek, unit='D')
    cal_data['Thứ'] = cal_data['Ngày'].dt.day_name().map(VN_DAYS)
    cal_data['Ngày_str'] = cal_data['Ngày'].dt.date

    grp = scope_df.groupby('Ngày')['Thời lượng (Phút)'].sum().reset_index()
    cal_data = cal_data.merge(grp, left_on='Ngày_str', right_on='Ngày', how='left').fillna({'Thời lượng (Phút)': 0})
    cal_data['Số giờ'] = (cal_data['Thời lượng (Phút)'] / 60).round(1)
    cal_data['day'] = cal_data['Ngày_x'].dt.day if 'Ngày_x' in cal_data else pd.to_datetime(cal_data['Ngày_str']).dt.day

    # Thang màu theo BẬC (0 / <1h / 1–2h / 2–4h / >4h) -> ngày thường không bị
    # một ngày cày khủng làm phẳng hết như thang tuyến tính cũ.
    def _cal_lvl(h):
        if h <= 0: return 0
        if h < 1: return 1
        if h < 2: return 2
        if h < 4: return 3
        return 4
    cal_data['lvl'] = cal_data['Số giờ'].map(_cal_lvl)
    LVL_COLORS = ["#e5e5ea", "#ade8bf", "#6fd693", "#34c759", "#1f8f43"]

    enc_x = alt.X('yearmonthdate(Tuần_Bắt_Đầu):O', title='',
                  axis=alt.Axis(labelAngle=0, orient='top', tickSize=0, domain=False,
                                labelExpr="month(datum.value) != month(datum.value - 7*24*60*60*1000) ? 'Th' + (month(datum.value)+1) : ''"))
    enc_y = alt.Y('Thứ:O', sort=DAYS_ORDER, title='', scale=alt.Scale(domain=DAYS_ORDER), axis=alt.Axis(tickSize=0, domain=False))
    cal_tooltip = [alt.Tooltip('Ngày_str:T', format='%d-%m-%Y', title='Ngày'),
                   alt.Tooltip('Số giờ:Q', format='.1f', title='Giờ')]
    base = alt.Chart(cal_data).encode(x=enc_x, y=enc_y)
    rect = base.mark_rect(cornerRadius=3).encode(
        color=alt.Color('lvl:O', scale=alt.Scale(domain=[0, 1, 2, 3, 4], range=LVL_COLORS), legend=None),
        tooltip=cal_tooltip
    )
    text = base.mark_text(baseline='middle', fontSize=10).encode(
        text='day:Q',
        color=alt.condition("datum.lvl >= 3", alt.value('#ffffff'), alt.value('#a7a7ac')),
        tooltip=cal_tooltip
    )
    chart = (rect + text).properties(
        width=alt.Step(34), height=alt.Step(34),
        # padding phải bù cho vùng nhãn thứ bên trái -> lưới căn giữa trong thẻ
        padding={"left": 0, "right": 64, "top": 5, "bottom": 5}
    ).configure_view(strokeWidth=0)
    st.altair_chart(chart, width='content')


DTBL_CSS = """
<style>
.dtbl-wrap { overflow:auto; max-height:560px; border-radius:14px; border:1px solid rgba(0,0,0,0.06); background:#ffffff; box-shadow:0 4px 15px rgba(0,0,0,0.04); }
.dtbl { border-collapse:collapse; width:100%; font-size:14px; font-family:-apple-system,BlinkMacSystemFont,sans-serif; }
.dtbl th, .dtbl td { padding:4px 9px; text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }
.dtbl thead th { position:sticky; top:0; z-index:2; background:#f5f5f7; color:#86868b; font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.3px; border-bottom:1px solid rgba(0,0,0,0.1); }
.dtbl td.lbl, .dtbl th.lbl { text-align:left; position:sticky; left:0; background:#ffffff; z-index:1; }
.dtbl thead th.lbl { z-index:3; background:#f5f5f7; }
.dtbl tr.cat td { font-weight:700; color:#1d1d1f; border-top:1px solid rgba(0,0,0,0.07); }
.dtbl tr.cat td.lbl { background:#ffffff; }
.dtbl tr.proj td { color:#6e6e73; }
.dtbl tr.proj td.lbl { padding-left:34px; color:#86868b; font-weight:400; }
.dtbl td.zero { color:#cfcfd4; }
.dtbl td.tot { border-left:1px solid rgba(0,0,0,0.08); font-weight:600; color:#1d1d1f; }
.dtbl tr.proj td.tot { font-weight:500; color:#6e6e73; }
.dtbl th.txt, .dtbl td.txt { text-align:left; }
.dtbl tr.prow td { color:#3a3a3c; font-weight:400; border-top:1px solid rgba(0,0,0,0.05); }
.dtbl tr.prow td.lbl { color:#aeaeb2; font-weight:500; }
</style>
"""


def _heat_cell(v, ref, extra_cls="", drop=False):
    """Một ô số: <0.05 -> dấu chấm mờ; ngược lại tô nền xanh theo tỉ lệ v/ref.
    drop=True -> đánh dấu ▾ đỏ (sụt mạnh so với kỳ liền trước)."""
    cls = extra_cls.strip()
    mark = "<span style='color:#ff3b30;font-size:10px;'>▾</span>" if drop else ""
    title = " title='Giảm mạnh so với kỳ trước'" if drop else ""
    if v < 0.05:
        if drop:
            return f'<td class="{cls}"{title}>{mark}</td>'
        return f'<td class="{(cls + " zero").strip()}">·</td>'
    a = min(v / ref, 1.0) * 0.7 if ref > 0 else 0
    bg = f'background:rgba(52,199,89,{a:.2f});' if a > 0.02 else ''
    cls_attr = f' class="{cls}"' if cls else ''
    return f'<td{cls_attr}{title} style="{bg}">{mark}{v:.1f}</td>'


def render_data_table(df, time_col):
    if df.empty:
        return
    cols = sorted(df[time_col].unique())
    proj = (df.groupby(['Danh mục', 'Dự án', time_col])['Thời lượng (Phút)'].sum()
              .unstack(fill_value=0).reindex(columns=cols, fill_value=0)) / 60
    cat = (df.groupby(['Danh mục', time_col])['Thời lượng (Phút)'].sum()
             .unstack(fill_value=0).reindex(columns=cols, fill_value=0)) / 60
    # Thang heat riêng cho dòng Danh mục và dòng Dự án để cả hai đều thấy gradient
    vmax_proj = float(proj.values.max()) if proj.size else 0.0
    vmax_cat = float(cat.values.max()) if cat.size else 0.0

    def col_label(key):
        key = str(key)
        if 'W' in key:                       # '2026-W14' -> 'W14'
            return 'W' + key.split('W')[-1]
        parts = key.split('-')               # '2026-05'  -> 'Th5'
        return f"Th{int(parts[-1])}" if len(parts) >= 2 else key

    has_drop = [False]

    def heat_row(values, vmax):
        out = ""
        for i, v in enumerate(values):
            # Sụt mạnh: kỳ trước có ≥1h và kỳ này giảm trên 60%
            d = i >= 1 and values[i - 1] >= 1.0 and v <= values[i - 1] * 0.4
            if d:
                has_drop[0] = True
            out += _heat_cell(v, vmax, drop=d)
        return out

    head = ''.join(f'<th>{col_label(c)}</th>' for c in cols)
    rows_html = ''
    for c in sorted(cat.index):
        c_vals = [float(cat.loc[c][col]) for col in cols]
        rows_html += '<tr class="cat">'
        rows_html += f'<td class="lbl">{html_escape(str(c))}</td>'
        rows_html += heat_row(c_vals, vmax_cat)
        rows_html += _heat_cell(sum(c_vals), 0, "tot")   # cột Tổng không tô heat cho gọn
        rows_html += '</tr>'

        sub = proj[proj.index.get_level_values(0) == c].sort_index(level=1)
        for idx, row in sub.iterrows():
            p_vals = [float(row[col]) for col in cols]
            rows_html += '<tr class="proj">'
            rows_html += f'<td class="lbl">{html_escape(str(idx[1]))}</td>'
            rows_html += heat_row(p_vals, vmax_proj)
            rows_html += _heat_cell(sum(p_vals), 0, "tot")
            rows_html += '</tr>'

    st.markdown(DTBL_CSS + f"""
<div class="dtbl-wrap"><table class="dtbl">
<thead><tr><th class="lbl">Danh mục / Dự án</th>{head}<th>Tổng</th></tr></thead>
<tbody>{rows_html}</tbody>
</table></div>
""", unsafe_allow_html=True)


def render_detail_table(scope_df):
    """Bảng chi tiết một kỳ (Tháng/Tuần): mỗi Danh mục/Dự án một số giờ tổng."""
    if scope_df.empty:
        return
    cat = scope_df.groupby('Danh mục')['Thời lượng (Phút)'].sum() / 60
    proj = scope_df.groupby(['Danh mục', 'Dự án'])['Thời lượng (Phút)'].sum() / 60
    vmax_cat = float(cat.max()) if len(cat) else 0.0
    vmax_proj = float(proj.max()) if len(proj) else 0.0
    total_all = float(cat.sum()) or 1.0

    rows_html = ''
    for c in sorted(cat.index):
        cv = float(cat.loc[c])
        rows_html += '<tr class="cat">'
        rows_html += f'<td class="lbl">{html_escape(str(c))}</td>'
        rows_html += _heat_cell(cv, vmax_cat)
        rows_html += f'<td class="tot">{cv/total_all*100:.0f}%</td>'
        rows_html += '</tr>'

        sub = proj[proj.index.get_level_values(0) == c].sort_index(level=1)
        for idx, v in sub.items():
            pv = float(v)
            rows_html += '<tr class="proj">'
            rows_html += f'<td class="lbl">{html_escape(str(idx[1]))}</td>'
            rows_html += _heat_cell(pv, vmax_proj)
            rows_html += f'<td class="tot">{pv/total_all*100:.0f}%</td>'
            rows_html += '</tr>'

    st.markdown(DTBL_CSS + f"""
<div class="dtbl-wrap"><table class="dtbl">
<thead><tr><th class="lbl">Danh mục / Dự án</th><th>Số giờ</th><th>Tỉ trọng</th></tr></thead>
<tbody>{rows_html}</tbody>
</table></div>
""", unsafe_allow_html=True)


def render_period_table(df, time_col):
    """Bảng theo kỳ cho MỘT nhóm/dự án: mỗi kỳ (Tuần/Tháng) là một dòng,
    các cột Số giờ (tô heat) / Số cây / Số ngày, kèm dòng Tổng."""
    if df.empty:
        return
    g = df.groupby(time_col)
    hrs = g['Thời lượng (Phút)'].sum() / 60
    trees = g.size()
    days = g['Ngày'].nunique()
    periods = sorted(hrs.index)
    vmax = float(hrs.max()) if len(hrs) else 0.0

    def plabel(key):
        key = str(key)
        if 'W' in key:                       # '2026-W14' -> 'W14'
            return 'W' + key.split('W')[-1]
        parts = key.split('-')               # '2026-05'  -> 'Th5'
        return f"Th{int(parts[-1])}" if len(parts) >= 2 else key

    rows_html = ''
    for p in periods:
        rows_html += '<tr class="prow">'
        rows_html += f'<td class="lbl">{plabel(p)}</td>'
        rows_html += _heat_cell(float(hrs[p]), vmax)
        rows_html += f'<td>{int(trees[p])}</td>'
        rows_html += f'<td>{int(days[p])}</td>'
        rows_html += '</tr>'
    rows_html += '<tr class="cat">'
    rows_html += '<td class="lbl">Tổng</td>'
    rows_html += _heat_cell(float(hrs.sum()), 0, "tot")
    rows_html += f'<td class="tot">{int(trees.sum())}</td>'
    rows_html += f'<td class="tot">{int(df["Ngày"].nunique())}</td>'
    rows_html += '</tr>'

    period_name = 'Tuần' if time_col == 'Tuần' else 'Tháng'
    st.markdown(DTBL_CSS + f"""
<div class="dtbl-wrap"><table class="dtbl">
<thead><tr><th class="lbl">{period_name}</th><th>Số giờ</th><th>Số cây</th><th>Số ngày</th></tr></thead>
<tbody>{rows_html}</tbody>
</table></div>
""", unsafe_allow_html=True)


# --- GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="Forest Tracker", page_icon=":material/forest:", layout="wide")

st.markdown(
    """
    <style>
    /* Đặt font trên html/body để kế thừa xuống; KHÔNG đặt !important rộng
       lên mọi phần tử để tránh đè font của icon Material (Material Symbols). */
    html, body, .stApp {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .stApp {
        background-color: #f5f5f7;
    }
    
    .block-container { max-width: 1200px !important; margin: 0 auto !important; padding-top: 2rem !important; }
    
    .glass-card {
        background: rgba(255, 255, 255, 0.65);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.4);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.04);
    }
    
    h1, h2, h3 { color: #1d1d1f !important; font-weight: 600 !important; letter-spacing: -0.5px !important; }
    hr { border-color: rgba(0,0,0,0.08) !important; }
    
    div[data-testid="stButton"] button[kind="primary"] {
        background-color: #007aff !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: 500 !important;
        padding: 6px 16px !important;
        box-shadow: 0 2px 5px rgba(0,122,255,0.3) !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        transform: scale(0.98);
        opacity: 0.9;
    }
    
    div[data-testid="stButton"] button[kind="secondary"] {
        background-color: white !important;
        color: #007aff !important;
        border-radius: 8px !important;
        border: 1px solid #d1d1d6 !important;
        font-weight: 500 !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
    }
    div[data-testid="stButton"] button { width: 100%; }
    
    .stSelectbox > div > div, .stTextInput > div > div > input {
        border-radius: 8px !important;
        border: 1px solid #d1d1d6 !important;
        background-color: rgba(255,255,255,0.8) !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
    }
    
    [data-testid="stPlotlyChart"], [data-testid="stVegaLiteChart"] {
        display: flex !important;
        justify-content: center !important;
        width: 100% !important;
        margin: 0 auto !important;
        background: rgba(255, 255, 255, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.4);
        border-radius: 16px;
        padding: 14px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.04);
    }

    [data-testid="stMetric"] { display: none; }

    /* ===== Bảng tổng quan gọn (hero + chip) ===== */
    .stat-panel .sp-hero { display: flex; flex-wrap: wrap; }
    .stat-panel .sp-hi { flex: 1; min-width: 130px; padding: 2px 18px; border-right: 1px solid rgba(0,0,0,0.07); }
    .stat-panel .sp-hi:first-child { padding-left: 2px; }
    .stat-panel .sp-hi:last-child { border-right: none; }
    .stat-panel .sp-l { font-size: 11px; color: #86868b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    .stat-panel .sp-v { font-size: 32px; font-weight: 600; letter-spacing: -0.5px; line-height: 1.18; color: #1d1d1f; }
    .stat-panel .sp-d { font-size: 13px; font-weight: 500; margin-top: 2px; }
    /* Mỗi nhóm = 1 hàng: nhãn bên trái, các chip cùng hàng -> tiết kiệm chiều cao */
    .stat-panel .sp-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; margin-top: 12px; }
    .stat-panel .sp-sub { font-size: 11px; color: #86868b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin: 0; flex: 0 0 160px; }
    .stat-panel .sp-chips { display: flex; flex-wrap: wrap; gap: 8px; flex: 1 1 auto; }
    @media (max-width: 640px) { .stat-panel .sp-sub { flex-basis: 100%; } }
    .stat-panel .chip { border-radius: 10px; padding: 7px 12px; font-size: 13px; white-space: nowrap; background: #f0f1f4; }
    .stat-panel .chip .ck { color: #86868b; }
    .stat-panel .chip .cv { font-weight: 600; color: #1d1d1f; margin-left: 5px; }
    .stat-panel .chip .cd { font-weight: 500; margin-left: 6px; }
    .stat-panel .chip.tw { background: rgba(0,122,255,0.10); }
    .stat-panel .chip.tw .ck { color: #0067d6; }
    .stat-panel .chip.tw .cv { color: #007aff; }

    /* ===== Mục dạng gập/mở (expander) trông như tiêu đề mục ===== */
    [data-testid="stExpander"] {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        margin: 6px 0 4px 0 !important;
    }
    [data-testid="stExpander"] details {
        border: none !important;
        background: transparent !important;
        border-radius: 0 !important;
    }
    [data-testid="stExpander"] summary {
        padding: 8px 2px !important;
        border-bottom: 2px solid rgba(0,0,0,0.07) !important;
        border-radius: 0 !important;
        transition: color 0.15s ease, border-color 0.15s ease !important;
    }
    [data-testid="stExpander"] summary:hover { border-bottom-color: #007aff !important; }
    [data-testid="stExpander"] summary:hover svg,
    [data-testid="stExpander"] summary:hover p { color: #007aff !important; }
    [data-testid="stExpander"] summary p {
        font-size: 1.35rem !important;
        font-weight: 600 !important;
        letter-spacing: -0.4px !important;
        color: #1d1d1f !important;
    }
    [data-testid="stExpander"] [data-testid="stExpanderDetails"] { padding-top: 12px !important; }

    /* Thanh chọn trang (segmented control) căn giữa, cách nội dung một chút */
    [data-testid="stButtonGroup"] { margin-bottom: 10px; }
    /* Riêng thanh điều hướng trang: căn giữa cả hàng nút.
       Element container mặc định co theo nội dung -> ép full width rồi căn giữa. */
    .st-key-nav { width: 100% !important; }
    .st-key-nav [data-testid="stButtonGroup"] { display: flex !important; justify-content: center !important; flex-wrap: wrap !important; width: 100% !important; }

    /* Bộ chọn kỳ (stepper): luôn 1 hàng, co vừa cả mobile */
    [class*="st-key-stepper"] [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 6px !important; }
    [class*="st-key-stepper"] [data-testid="stColumn"] { min-width: 0 !important; }

    /* ===== Tinh chỉnh riêng cho điện thoại (không ảnh hưởng desktop) ===== */
    @media (max-width: 640px) {
        h1 { font-size: 1.9rem !important; line-height: 1.15 !important; }
        h2, [data-testid="stHeading"] h2 { font-size: 1.35rem !important; }
        h3 { font-size: 1.1rem !important; }
        [data-testid="stExpander"] summary p { font-size: 1.15rem !important; }
        .block-container { padding-left: 0.8rem !important; padding-right: 0.8rem !important; padding-top: 1rem !important; }

        /* Thẻ gọn lại, bớt khoảng trống thừa (height:auto để không bị kéo giãn khi xếp dọc) */
        .glass-card { padding: 14px !important; height: auto !important; }
        .glass-card h3 { font-size: 26px !important; margin: 4px 0 !important; }
        /* Khi cột xếp dọc trên mobile, bỏ giãn đều chiều cao và tạo khoảng cách giữa các ô */
        [data-testid="stHorizontalBlock"] { align-items: flex-start !important; }
        [data-testid="stColumn"] { margin-bottom: 12px !important; }

        /* Bảng tổng quan gọn: hero xếp 2 cột, bỏ vạch ngăn dọc */
        .stat-panel .sp-hi { border-right: none !important; min-width: 45% !important; padding: 6px 8px !important; }
        .stat-panel .sp-v { font-size: 26px !important; }

        /* Biểu đồ: bớt đệm để rộng hơn */
        [data-testid="stPlotlyChart"], [data-testid="stVegaLiteChart"] { padding: 6px !important; }
        /* Lịch (Vega) rộng -> cho cuộn ngang trong thẻ thay vì tràn */
        [data-testid="stVegaLiteChart"] { overflow-x: auto !important; justify-content: flex-start !important; }

        /* Bảng số liệu: chữ nhỏ & đệm sát để chứa nhiều cột hơn */
        .dtbl th, .dtbl td { padding: 3px 6px !important; font-size: 11px !important; }
        .dtbl-wrap { max-height: 70vh !important; }

        /* Thẻ dạng flex (vd Cập nhật gần nhất): xếp dọc cho dễ đọc */
        .glass-card[style*="display: flex"] { flex-direction: column !important; gap: 14px !important; }
        .glass-card[style*="display: flex"] > div { border-right: none !important; }
    }

    /* ===== Ghi chú ngày: hộp hiển thị ghi chú đã lưu / trạng thái trống ===== */
    .st-key-note_saved { background: rgba(0,122,255,0.05); border: 1px solid rgba(0,122,255,0.12);
        border-left: 3px solid #007aff; border-radius: 10px; padding: 2px 14px; }
    .note-empty { font-size: 14px; color: #86868b; background: #f7f7f9;
        border: 1px dashed rgba(0,0,0,0.14); border-radius: 10px; padding: 13px 15px; }

    /* ===== Hiển thị ghi chú dạng HTML (do Quill xuất ra) ===== */
    .note-html, .st-key-note_saved { font-size: 14.5px; line-height: 1.6; color: #1d1d1f; }
    .note-html p, .st-key-note_saved p { margin: 4px 0; }
    .note-html ul, .note-html ol { margin: 4px 0; padding-left: 22px; }
    /* Bỏ lề trên/dưới ở phần tử đầu & cuối để ghi chú căn thẳng dòng đầu (không bị lệch khung) */
    .note-html > :first-child { margin-top: 0 !important; }
    .note-html > :last-child { margin-bottom: 0 !important; }
    .note-html a, .st-key-note_saved a { color: #007aff; }
    /* Thụt lề bullet/đánh số lồng nhau (Quill dùng class ql-indent-N trên <li>) */
    .ql-indent-1 { padding-left: 2.0em; } .ql-indent-2 { padding-left: 4.0em; }
    .ql-indent-3 { padding-left: 6.0em; } .ql-indent-4 { padding-left: 8.0em; }
    .ql-indent-5 { padding-left: 10em; } .ql-indent-6 { padding-left: 12em; }

    /* ===== Container có viền (ghi chú, nhật ký, ngày này năm trước) trông như glass-card ===== */
    .st-key-note_card, [class*="st-key-jcard"] {
        border-radius: 14px !important;
        border-color: rgba(0,0,0,0.06) !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.04) !important;
        background: #fff !important;
    }

    /* ===== Nhật ký & Ngày này năm trước: thẻ có kẻ dọc trái/phải ===== */
    [class*="st-key-jcard"] [data-testid="stHorizontalBlock"] {
        border-bottom: 1px solid rgba(0,0,0,0.06); padding: 12px 0; }
    [class*="st-key-jcard"] [data-testid="stColumn"]:first-child {
        border-right: 1px solid rgba(0,0,0,0.08); }
    .jdate { text-align: center; }
    .jdate .jyear { font-size: 20px; font-weight: 700; color: #007aff; letter-spacing: -0.5px; line-height: 1; }
    .jdate .jdow { font-size: 15px; font-weight: 700; color: #1d1d1f; margin-top: 6px; }
    .jdate .jdowbig { font-size: 18px; font-weight: 700; color: #1d1d1f; letter-spacing: -0.3px; }
    .jdate .jdm { font-size: 13px; color: #86868b; font-weight: 500; margin-top: 2px; }
    .otd-foot { font-size: 12px; color: #86868b; padding-top: 12px; }
    .otd-foot b { color: #1d1d1f; }
    .jchip { display: inline-block; background: #f0f1f4; border-radius: 10px; padding: 5px 11px;
        font-size: 12.5px; margin: 0 6px 6px 0; }
    .jchip .ck { color: #86868b; } .jchip .cv { font-weight: 600; color: #1d1d1f; margin-left: 5px; }
    /* Top 3 (Báo cáo ngày): tách khỏi bảng số liệu phía trên */
    .st-key-day_top3 { margin-top: 14px; }

    @media (max-width: 640px) {
        [class*="st-key-jcard"] [data-testid="stColumn"] { margin-bottom: 0 !important; }
        /* Khi cột xếp dọc trên mobile, bỏ vạch dọc (border-right) cho gọn */
        [class*="st-key-jcard"] [data-testid="stColumn"]:first-child { border-right: none !important; }
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    "<h1 style='text-align:center; margin:0 0 0.35em 0; letter-spacing:-0.6px;'>Forest Dashboard</h1>",
    unsafe_allow_html=True,
)

# Điều hướng dạng menu hamburger (sidebar), kèm icon cho từng trang
NAV = {
    "Thống kê chung": ":material/bar_chart:",
    "Báo cáo tháng": ":material/calendar_month:",
    "Báo cáo tuần": ":material/calendar_view_week:",
    "Báo cáo ngày": ":material/today:",
    "Báo cáo theo dự án": ":material/category:",
    "Chuẩn bị dữ liệu": ":material/settings:",
}

df = prep_analysis_data()
DAYS_ORDER = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]

# Bản đồ màu cố định: mỗi Danh mục/Dự án luôn giữ một màu xuyên suốt mọi biểu đồ/tab.
# Danh mục (mặc định để tô màu) được nhận các màu cơ sở đẹp & tách biệt nhất trước,
# dự án nhận phần còn lại -> biểu đồ theo Danh mục luôn dễ phân biệt.
if not df.empty:
    _cats = sorted(df['Danh mục'].dropna().unique())
    _projs = sorted(set(df['Dự án'].dropna().unique()) - set(_cats))
    COLOR_MAP = build_color_map(_cats + _projs)
else:
    COLOR_MAP = {}

# Thanh chọn trang luôn hiển thị ngay dưới tiêu đề (kiểu iOS segmented control)
nav = st.segmented_control(
    "Trang", list(NAV.keys()),
    format_func=lambda x: f"{NAV[x]} {x}",
    default="Thống kê chung", key="nav", label_visibility="collapsed",
)
if not nav:
    nav = "Thống kê chung"

# ==========================================
# TRANG: THỐNG KÊ CHUNG
# ==========================================
if nav == "Thống kê chung":
    if not df.empty:
        with st.expander("1. Tổng quan", expanded=True):

            last_dt = df['Thời gian kết thúc'].max()
            if pd.notna(last_dt):
                abs_str = pd.Timestamp(last_dt).strftime('%H:%M · %d/%m/%Y')
                st.markdown(
                    f"<div class='glass-card' style='padding:12px 18px; margin-bottom:16px; display:flex; "
                    f"align-items:center; flex-wrap:wrap; gap:6px 12px;'>"
                    f"<span style='font-size:13px;color:#86868b;font-weight:500;text-transform:uppercase;letter-spacing:0.5px;'>"
                    f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='14' height='14' fill='#86868b' style='vertical-align:-2px;margin-right:5px;'><path d='M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z'/></svg>"
                    f"Cập nhật gần nhất</span>"
                    f"<span style='font-size:17px;color:#1d1d1f;font-weight:600;'>{format_relative(last_dt)}</span>"
                    f"<span style='font-size:13px;color:#86868b;'>({abs_str})</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            total_hrs = df['Thời lượng (Phút)'].sum() / 60
            total_trees = len(df)
            num_days = df['Ngày'].nunique() or 1
            base_avg = total_hrs / num_days

            # Phong độ 7 ngày gần đây so với mức trung bình của chính mình
            recent7 = df[df['Ngày'] >= (date.today() - timedelta(days=6))]
            r_days = recent7['Ngày'].nunique()
            recent_chips = []
            if r_days > 0:
                r_avg = (recent7['Thời lượng (Phút)'].sum() / 60) / r_days
                _delta = None
                if base_avg > 0:
                    _pct = (r_avg - base_avg) / base_avg * 100
                    _c = "#34c759" if _pct > 0 else "#ff3b30" if _pct < 0 else "#86868b"
                    _delta = (f"{_pct:+.0f}% vs thường lệ", _c)
                recent_chips.append({"k": "Thời gian / ngày", "v": f"{r_avg:.1f}h", "delta": _delta})
            recent_chips.append({"k": "Số ngày hoạt động", "v": f"{r_days}/7"})

            s_stat = _streak_stats(df)
            by_wd = _weekday_avg(df)
            _sections = [
                {"label": "Trung bình (toàn thời gian)", "chips": [
                    {"k": "Thời gian / ngày", "v": f"{base_avg:.1f}h"},
                    {"k": "Số cây / ngày", "v": f"{total_trees/num_days:.1f}"},
                    {"k": "Thời gian / phiên", "v": f"{_avg_session_min(df):.0f} phút"},
                ]},
                {"label": "7 ngày gần đây", "chips": recent_chips},
                {"label": "Chuỗi ngày", "chips": [
                    {"k": "Tổng cộng", "v": f"{s_stat['total']} ngày"},
                    {"k": "Dài nhất", "v": f"{s_stat['longest']} ngày"},
                    {"k": "Hiện tại", "v": f"{s_stat['current']} ngày", "hl": True},
                ]},
            ]
            if len(by_wd) and by_wd.max() > 0:
                _sections.append({"label": "Theo thứ", "chips": [
                    {"k": "Mạnh nhất", "v": f"{by_wd.idxmax()} ({by_wd.max():.1f}h)"},
                    {"k": "Yếu nhất", "v": f"{by_wd.idxmin()} ({by_wd.min():.1f}h)"},
                ]})
            _nud = _streak_nudge(s_stat)
            _footer = (_nud[0],) + NUDGE_TONES[_nud[1]] if _nud else None

            render_stat_panel(
                hero_items=[
                    {"label": "Tổng thời gian", "value": f"{total_hrs:.1f}h"},
                    {"label": "Số cây đã trồng", "value": f"{total_trees}"},
                ],
                sections=_sections,
                footer=_footer,
            )
            render_session_bar(df)

            st.write("")
            c_top1, c_top2 = st.columns(2)
            _wk_now = date.today().strftime('%G-W%V')
            with c_top1: render_top_3(df, 'Danh mục', 'Top 3 Danh mục', week_key=_wk_now)
            with c_top2: render_top_3(df, 'Dự án', 'Top 3 Dự án', week_key=_wk_now)
        with st.expander("2. Biểu đồ lịch", expanded=False):
            df_cal = range_radio(df, key="range_cal")
            render_calendar_grid(df_cal, df_cal)
        with st.expander("3. Xu hướng theo thời gian", expanded=False):
            o1, o2, o3 = st.columns([5, 3, 2])
            with o1:
                _rl = st.segmented_control("Khoảng thời gian", list(RANGE_OPTS.keys()), default="90 ngày", key="range_trend")
            with o2:
                time_col_2 = st.segmented_control("Gộp theo", ["Ngày", "Tuần", "Tháng"], default="Ngày", key="time_tab2")
            with o3:
                color_col_2 = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default="Danh mục", key="rad_tab2")
            _rl = _rl or "90 ngày"
            time_col_2 = time_col_2 or "Ngày"
            color_col_2 = color_col_2 or "Danh mục"
            df_trend = filter_by_range(df, _rl)

            trend_group = df_trend.groupby([time_col_2, color_col_2])['Thời lượng (Phút)'].sum().reset_index()
            trend_group['Số giờ'] = trend_group['Thời lượng (Phút)'] / 60
            if time_col_2 == "Ngày":
                trend_group['Ngày'] = pd.to_datetime(trend_group['Ngày'])
            fig1 = render_trend_fig(trend_group, time_col_2, color_col_2,
                                    ma_df=df_trend if time_col_2 == "Ngày" else None)
            fig1.update_layout(width=CHART_WIDTH)
            st.plotly_chart(fig1, width='stretch', config=PLOTLY_CONFIG)
        with st.expander("4. Xu hướng tập trung theo khung giờ", expanded=False):
            df_hour = range_radio(df, key="range_hour")
            render_hourly_chart(df_hour, color_col_2)
        with st.expander("5. Giờ tập trung theo thứ", expanded=False):
            df_heat = range_radio(df, key="range_heat")
            render_dayhour_heatmap(df_heat)
        with st.expander("6. Phân bố độ dài phiên", expanded=False):
            render_session_histogram(df)
        with st.expander("7. Bảng số liệu", expanded=False):
            cc1, cc2 = st.columns([5, 2])
            with cc1:
                df_tbl = range_radio(df, key="range_table")
            with cc2:
                view_opt = st.segmented_control("Xem theo", ["Tuần", "Tháng"], default="Tuần", key="view_tab1")
            view_opt = view_opt or "Tuần"
            time_col = 'Tuần' if view_opt == "Tuần" else 'Tháng'
            render_data_table(df_tbl, time_col)
    else:
        st.info("Chưa có dữ liệu hệ thống. Vui lòng sang tab 'Chuẩn bị dữ liệu' để tải file lên.")

# ==========================================
# TAB BÁO CÁO THÁNG
# ==========================================
elif nav == "Báo cáo tháng":
    if not df.empty:
        months = sorted(df['Tháng'].unique())
        selected_month = period_stepper(months, key="month", fmt=fmt_month, current=date.today().strftime('%Y-%m'))
        df_m = df[df['Tháng'] == selected_month]
        
        df_other_months = df[df['Tháng'] != selected_month]
        if df_other_months['Tháng'].nunique() > 0:
            g_om = df_other_months.groupby('Tháng')
            hrs_om = g_om['Thời lượng (Phút)'].sum() / 60
            trees_om = g_om.size()
            days_om = g_om['Ngày'].nunique()
            avg_hrs_month = hrs_om.mean()
            avg_trees_month = trees_om.mean()
            avg_hrs_day_month = (hrs_om / days_om).mean()
            avg_trees_day_month = (trees_om / days_om).mean()
            avg_min_sess_month = ((hrs_om * 60) / trees_om).mean()
        else:
            avg_hrs_month = avg_trees_month = avg_hrs_day_month = avg_trees_day_month = avg_min_sess_month = None

        y, m = map(int, selected_month.split('-'))
        prev_month_key = f"{y - 1:04d}-12" if m == 1 else f"{y:04d}-{m - 1:02d}"
        df_prev_month = df[df['Tháng'] == prev_month_key]
        if not df_prev_month.empty:
            prev_hrs_month = df_prev_month['Thời lượng (Phút)'].sum() / 60
            prev_trees_month = len(df_prev_month)
            prev_days_month = df_prev_month['Ngày'].nunique() or 1
            prev_hrs_day_month = prev_hrs_month / prev_days_month
            prev_trees_day_month = prev_trees_month / prev_days_month
            prev_min_sess_month = (prev_hrs_month * 60) / prev_trees_month if prev_trees_month else None
        else:
            prev_hrs_month = prev_trees_month = prev_hrs_day_month = prev_trees_day_month = prev_min_sess_month = None
        
        if not df_m.empty:
            with st.expander("1. Tổng quan", expanded=True):
                curr_hrs = df_m['Thời lượng (Phút)'].sum() / 60
                curr_trees = len(df_m)
                num_days_m = df_m['Ngày'].nunique() or 1

                curr_hrs_day = curr_hrs / num_days_m
                curr_trees_day = curr_trees / num_days_m

                delta1_hr = (curr_hrs - prev_hrs_month) if prev_hrs_month is not None else None
                delta2_hr = (curr_hrs - avg_hrs_month) if avg_hrs_month is not None else None
                delta1_hrd = (curr_hrs_day - prev_hrs_day_month) if prev_hrs_day_month is not None else None
                delta2_hrd = (curr_hrs_day - avg_hrs_day_month) if avg_hrs_day_month is not None else None

                delta1_tr = (curr_trees - prev_trees_month) if prev_trees_month is not None else None
                delta2_tr = (curr_trees - avg_trees_month) if avg_trees_month is not None else None
                delta1_trd = (curr_trees_day - prev_trees_day_month) if prev_trees_day_month is not None else None
                delta2_trd = (curr_trees_day - avg_trees_day_month) if avg_trees_day_month is not None else None

                curr_min_sess = _avg_session_min(df_m)
                delta1_ms = (curr_min_sess - prev_min_sess_month) if prev_min_sess_month is not None else None
                delta2_ms = (curr_min_sess - avg_min_sess_month) if avg_min_sess_month is not None else None

                render_stat_panel(hero_items=[
                    {"label": "Tổng thời gian", "value": f"{curr_hrs:.1f}h", "deltas": [d for d in [_delta_t(delta1_hr, "h vs Tháng trước"), _delta_t(delta2_hr, "h vs Trung bình")] if d]},
                    {"label": "Thời gian / ngày", "value": f"{curr_hrs_day:.1f}h", "deltas": [d for d in [_delta_t(delta1_hrd, "h vs Tháng trước"), _delta_t(delta2_hrd, "h vs Trung bình")] if d]},
                    {"label": "Số cây đã trồng", "value": f"{curr_trees}", "deltas": [d for d in [_delta_t(delta1_tr, "cây vs Tháng trước"), _delta_t(delta2_tr, "cây vs Trung bình")] if d]},
                    {"label": "Số cây / ngày", "value": f"{curr_trees_day:.1f}", "deltas": [d for d in [_delta_t(delta1_trd, "cây vs Tháng trước"), _delta_t(delta2_trd, "cây vs Trung bình")] if d]},
                    {"label": "Thời gian / phiên", "value": f"{curr_min_sess:.0f} phút", "deltas": [d for d in [_delta_t(delta1_ms, "phút vs Tháng trước"), _delta_t(delta2_ms, "phút vs Trung bình")] if d]},
                ])
                render_session_bar(df_m)

                st.write("")
                c_top1, c_top2 = st.columns(2)
                with c_top1: render_top_3(df_m, 'Danh mục', 'Top 3 Danh mục Tháng')
                with c_top2: render_top_3(df_m, 'Dự án', 'Top 3 Dự án Tháng')
            with st.expander("2. Nhật ký", expanded=True):
                render_notes_journal(selected_month, 'month')
            with st.expander("3. Phân bổ thời gian", expanded=False):
                color_col_3 = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default="Danh mục", key="rad_tab3")
                color_col_3 = color_col_3 or "Danh mục"
                pc_m = df_m.groupby(color_col_3)['Thời lượng (Phút)'].sum().reset_index()
                pc_m['Số giờ'] = pc_m['Thời lượng (Phút)'] / 60
                fig_p_m = px.pie(pc_m, values='Số giờ', names=color_col_3, color=color_col_3, color_discrete_map=COLOR_MAP)
                fig_p_m.update_layout(width=CHART_WIDTH)
                fig_p_m = format_plotly_fig(fig_p_m, is_pie=True)
                st.plotly_chart(fig_p_m, width='stretch', config=PLOTLY_CONFIG)
            with st.expander("4. Xu hướng theo thời gian", expanded=False):
                t_m = df_m.groupby(['Ngày', color_col_3])['Thời lượng (Phút)'].sum().reset_index()
                t_m['Số giờ'] = t_m['Thời lượng (Phút)'] / 60
                t_m['Ngày'] = pd.to_datetime(t_m['Ngày'])
                fig_m = render_trend_fig(t_m, 'Ngày', color_col_3, ma_df=df_m, x_title="Ngày trong tháng")
                fig_m.update_layout(width=CHART_WIDTH)
                st.plotly_chart(fig_m, width='stretch', config=PLOTLY_CONFIG)
            with st.expander("5. Xu hướng tập trung theo khung giờ", expanded=False):
                render_hourly_chart(df_m, color_col_3)
            with st.expander("6. Giờ tập trung theo thứ", expanded=False):
                render_dayhour_heatmap(df_m)
            with st.expander("7. Phân bố độ dài phiên", expanded=False):
                render_session_histogram(df_m)
            with st.expander("8. Bảng số liệu", expanded=False):
                render_detail_table(df_m)
# ==========================================
# TAB BÁO CÁO TUẦN
# ==========================================
elif nav == "Báo cáo tuần":
    if not df.empty:
        weeks = sorted(df['Tuần'].unique())
        selected_week = period_stepper(weeks, key="week", fmt=fmt_week, current=date.today().strftime('%G-W%V'))
        df_w = df[df['Tuần'] == selected_week]
        
        df_other_weeks = df[df['Tuần'] != selected_week]
        if df_other_weeks['Tuần'].nunique() > 0:
            g_ow = df_other_weeks.groupby('Tuần')
            hrs_ow = g_ow['Thời lượng (Phút)'].sum() / 60
            trees_ow = g_ow.size()
            days_ow = g_ow['Ngày'].nunique()
            avg_hrs_week = hrs_ow.mean()
            avg_trees_week = trees_ow.mean()
            avg_hrs_day_week = (hrs_ow / days_ow).mean()
            avg_trees_day_week = (trees_ow / days_ow).mean()
            avg_min_sess_week = ((hrs_ow * 60) / trees_ow).mean()
        else:
            avg_hrs_week = avg_trees_week = avg_hrs_day_week = avg_trees_day_week = avg_min_sess_week = None

        week_anchor = df_w['Thời gian bắt đầu'].min()
        prev_week_key = (week_anchor - pd.Timedelta(days=7)).strftime('%G-W%V') if pd.notna(week_anchor) else None
        df_prev_week = df[df['Tuần'] == prev_week_key]
        if not df_prev_week.empty:
            prev_hrs_week = df_prev_week['Thời lượng (Phút)'].sum() / 60
            prev_trees_week = len(df_prev_week)
            prev_days_week = df_prev_week['Ngày'].nunique() or 1
            prev_hrs_day_week = prev_hrs_week / prev_days_week
            prev_trees_day_week = prev_trees_week / prev_days_week
            prev_min_sess_week = (prev_hrs_week * 60) / prev_trees_week if prev_trees_week else None
        else:
            prev_hrs_week = prev_trees_week = prev_hrs_day_week = prev_trees_day_week = prev_min_sess_week = None
        
        if not df_w.empty:
            with st.expander("1. Tổng quan", expanded=True):
                curr_hrs_w = df_w['Thời lượng (Phút)'].sum() / 60
                curr_trees_w = len(df_w)
                num_days_w = df_w['Ngày'].nunique() or 1

                curr_hrs_day_w = curr_hrs_w / num_days_w
                curr_trees_day_w = curr_trees_w / num_days_w

                d1_hr_w = (curr_hrs_w - prev_hrs_week) if prev_hrs_week is not None else None
                d2_hr_w = (curr_hrs_w - avg_hrs_week) if avg_hrs_week is not None else None
                d1_hrd_w = (curr_hrs_day_w - prev_hrs_day_week) if prev_hrs_day_week is not None else None
                d2_hrd_w = (curr_hrs_day_w - avg_hrs_day_week) if avg_hrs_day_week is not None else None

                d1_tr_w = (curr_trees_w - prev_trees_week) if prev_trees_week is not None else None
                d2_tr_w = (curr_trees_w - avg_trees_week) if avg_trees_week is not None else None
                d1_trd_w = (curr_trees_day_w - prev_trees_day_week) if prev_trees_day_week is not None else None
                d2_trd_w = (curr_trees_day_w - avg_trees_day_week) if avg_trees_day_week is not None else None

                curr_min_sess_w = _avg_session_min(df_w)
                d1_ms_w = (curr_min_sess_w - prev_min_sess_week) if prev_min_sess_week is not None else None
                d2_ms_w = (curr_min_sess_w - avg_min_sess_week) if avg_min_sess_week is not None else None

                render_stat_panel(hero_items=[
                    {"label": "Tổng thời gian", "value": f"{curr_hrs_w:.1f}h", "deltas": [d for d in [_delta_t(d1_hr_w, "h vs Tuần trước"), _delta_t(d2_hr_w, "h vs Trung bình")] if d]},
                    {"label": "Thời gian / ngày", "value": f"{curr_hrs_day_w:.1f}h", "deltas": [d for d in [_delta_t(d1_hrd_w, "h vs Tuần trước"), _delta_t(d2_hrd_w, "h vs Trung bình")] if d]},
                    {"label": "Số cây đã trồng", "value": f"{curr_trees_w}", "deltas": [d for d in [_delta_t(d1_tr_w, "cây vs Tuần trước"), _delta_t(d2_tr_w, "cây vs Trung bình")] if d]},
                    {"label": "Số cây / ngày", "value": f"{curr_trees_day_w:.1f}", "deltas": [d for d in [_delta_t(d1_trd_w, "cây vs Tuần trước"), _delta_t(d2_trd_w, "cây vs Trung bình")] if d]},
                    {"label": "Thời gian / phiên", "value": f"{curr_min_sess_w:.0f} phút", "deltas": [d for d in [_delta_t(d1_ms_w, "phút vs Tuần trước"), _delta_t(d2_ms_w, "phút vs Trung bình")] if d]},
                ])
                render_session_bar(df_w)

                st.write("")
                c_top1, c_top2 = st.columns(2)
                with c_top1: render_top_3(df_w, 'Danh mục', 'Top 3 Danh mục Tuần')
                with c_top2: render_top_3(df_w, 'Dự án', 'Top 3 Dự án Tuần')
            with st.expander("2. Nhật ký", expanded=True):
                render_notes_journal(selected_week, 'week')
            with st.expander("3. Phân bổ thời gian", expanded=False):
                color_col_4 = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default="Danh mục", key="rad_tab4")
                color_col_4 = color_col_4 or "Danh mục"
                pc_w = df_w.groupby(color_col_4)['Thời lượng (Phút)'].sum().reset_index()
                pc_w['Số giờ'] = pc_w['Thời lượng (Phút)'] / 60
                fig_p_w = px.pie(pc_w, values='Số giờ', names=color_col_4, color=color_col_4, color_discrete_map=COLOR_MAP)
                fig_p_w.update_layout(width=CHART_WIDTH)
                fig_p_w = format_plotly_fig(fig_p_w, is_pie=True)
                st.plotly_chart(fig_p_w, width='stretch', config=PLOTLY_CONFIG)
            with st.expander("4. Xu hướng theo thời gian", expanded=False):
                t_w = df_w.groupby(['Thứ', color_col_4])['Thời lượng (Phút)'].sum().reset_index()
                t_w['Số giờ'] = t_w['Thời lượng (Phút)'] / 60
                fig_w = render_trend_fig(t_w, 'Thứ', color_col_4, cat_order=DAYS_ORDER, x_title="Thứ trong tuần")
                fig_w.update_layout(width=CHART_WIDTH)
                st.plotly_chart(fig_w, width='stretch', config=PLOTLY_CONFIG)
            with st.expander("5. Xu hướng tập trung theo khung giờ", expanded=False):
                render_hourly_chart(df_w, color_col_4)
            with st.expander("6. Giờ tập trung theo thứ", expanded=False):
                render_dayhour_heatmap(df_w)
            with st.expander("7. Phân bố độ dài phiên", expanded=False):
                render_session_histogram(df_w)
            with st.expander("8. Bảng số liệu", expanded=False):
                render_detail_table(df_w)
# ==========================================
# TAB BÁO CÁO NGÀY
# ==========================================
elif nav == "Báo cáo ngày":
    if df.empty:
        st.info("Chưa có dữ liệu. Vui lòng sang tab 'Chuẩn bị dữ liệu' để tải file lên.")
    else:
        active_days = sorted(df['Ngày'].dropna().unique())
        sel = day_picker(active_days)
        day_df = df[df['Ngày'] == sel]
        vn_dow = VN_DAYS.get(pd.Timestamp(sel).day_name(), "")

        _evt = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='14' height='14' fill='#86868b' "
                "style='vertical-align:-2px;margin-right:6px;'><path d='M17 12h-5v5h5v-5zM16 1v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2"
                "L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2h-1V1h-2zm3 18H5V8h14v11z'/></svg>")
        _sub = "· không có hoạt động" if day_df.empty else f"· ngày hoạt động {active_days.index(sel) + 1}/{len(active_days)}"
        st.markdown(
            "<div class='glass-card' style='padding:12px 18px;margin-bottom:16px;display:flex;align-items:center;"
            "flex-wrap:wrap;gap:6px 12px;'>"
            "<span style='font-size:13px;color:#86868b;font-weight:500;text-transform:uppercase;letter-spacing:0.5px;'>"
            f"{_evt}Ngày đang xem</span>"
            f"<span style='font-size:17px;color:#1d1d1f;font-weight:600;'>{vn_dow}, {sel:%d/%m/%Y}</span>"
            f"<span style='font-size:13px;color:#86868b;'>{_sub}</span></div>",
            unsafe_allow_html=True)

        if day_df.empty:
            st.info("Ngày này không có phiên tập trung nào. Dùng ◀ ▶ để nhảy tới ngày có hoạt động liền kề.")
            with st.expander("Ghi chú ngày", expanded=True):
                render_note_editor(sel)
            with st.expander("Ngày này năm trước", expanded=False):
                render_on_this_day(sel, df)
        else:
            with st.expander("1. Tổng quan ngày", expanded=True):
                d_hrs = day_df['Thời lượng (Phút)'].sum() / 60
                d_sess = len(day_df)
                d_avg = _avg_session_min(day_df)

                cmp_chips = []
                pw = df[df['Ngày'] == (sel - timedelta(days=7))]
                if not pw.empty:
                    pw_h, pw_s = pw['Thời lượng (Phút)'].sum() / 60, len(pw)
                    _c = "#34c759" if d_hrs > pw_h else "#ff3b30" if d_hrs < pw_h else "#86868b"
                    cmp_chips.append({"k": f"vs {vn_dow} tuần trước", "v": f"{pw_h:.1f}h",
                                      "delta": (f"{_fmt_delta(d_hrs - pw_h)}h · {_fmt_delta(d_sess - pw_s)} phiên", _c)})
                else:
                    cmp_chips.append({"k": f"vs {vn_dow} tuần trước", "v": "không có"})
                same = df[(pd.to_datetime(df['Ngày']).dt.day_name() == pd.Timestamp(sel).day_name())
                          & (df['Ngày'] != sel)]
                if same['Ngày'].nunique():
                    avg_h = (same.groupby('Ngày')['Thời lượng (Phút)'].sum() / 60).mean()
                    _c = "#34c759" if d_hrs > avg_h else "#ff3b30" if d_hrs < avg_h else "#86868b"
                    cmp_chips.append({"k": f"vs TB các {vn_dow}", "v": f"{avg_h:.1f}h",
                                      "delta": (f"{_fmt_delta(d_hrs - avg_h)}h", _c)})

                t0 = pd.to_datetime(day_df['Thời gian bắt đầu']).min()
                t1 = pd.to_datetime(day_df['Thời gian kết thúc']).max()
                _sp = t1 - t0
                span_str = f"{int(_sp.total_seconds() // 3600)}h{int((_sp.total_seconds() % 3600) // 60):02d}"

                def _buoi(h):
                    return "Sáng" if 5 <= h < 11 else "Chiều" if 11 <= h < 17 else "Tối" if 17 <= h < 22 else "Khuya"
                bg = (day_df.assign(_b=pd.to_datetime(day_df['Thời gian bắt đầu']).dt.hour.map(_buoi))
                            .groupby('_b')['Thời lượng (Phút)'].sum() / 60)
                buoi_chips = [{"k": b, "v": f"{bg[b]:.1f}h"} for b in ["Sáng", "Chiều", "Tối", "Khuya"] if bg.get(b, 0) > 0]

                _secs = [{"label": "So sánh", "chips": cmp_chips},
                         {"label": "Mốc trong ngày", "chips": [
                             {"k": "Phiên đầu", "v": f"{t0:%H:%M}"},
                             {"k": "Phiên cuối", "v": f"{t1:%H:%M}"},
                             {"k": "Trải dài", "v": span_str}]}]
                if buoi_chips:
                    _secs.append({"label": "Theo buổi", "chips": buoi_chips})
                render_stat_panel(hero_items=[
                    {"label": "Tổng thời gian", "value": f"{d_hrs:.1f}h"},
                    {"label": "Số phiên", "value": f"{d_sess}"},
                    {"label": "Độ dài / phiên", "value": f"{d_avg:.0f} phút"},
                ], sections=_secs)

                with st.container(key="day_top3"):
                    tc1, tc2 = st.columns(2)
                    with tc1:
                        render_top_3(day_df, 'Danh mục', "Top 3 Danh mục")
                    with tc2:
                        render_top_3(day_df, 'Dự án', "Top 3 Dự án")

                render_session_bar(day_df)
                render_day_timeline(day_df, sel, df)

            with st.expander("2. Ghi chú ngày", expanded=True):
                render_note_editor(sel)

            with st.expander("3. Phân bổ thời gian", expanded=False):
                cc = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default="Dự án", key="rad_day")
                cc = cc or "Dự án"
                pc = day_df.groupby(cc)['Thời lượng (Phút)'].sum().reset_index()
                pc['Số giờ'] = pc['Thời lượng (Phút)'] / 60
                fig_d = px.pie(pc, values='Số giờ', names=cc, color=cc, color_discrete_map=COLOR_MAP)
                fig_d.update_layout(width=CHART_WIDTH)
                fig_d = format_plotly_fig(fig_d, is_pie=True)
                st.plotly_chart(fig_d, width='stretch', config=PLOTLY_CONFIG)

            with st.expander("4. Danh sách phiên", expanded=False):
                rows_html = ''
                for i, (_, r) in enumerate(day_df.sort_values('Thời gian bắt đầu').iterrows(), 1):
                    s = pd.to_datetime(r['Thời gian bắt đầu']); e = pd.to_datetime(r['Thời gian kết thúc'])
                    cat = r.get('Danh mục')
                    cat = str(cat) if pd.notna(cat) and str(cat) != str(r['Dự án']) else '—'
                    rows_html += ('<tr class="prow">'
                                  f'<td class="lbl">{i}</td>'
                                  f'<td class="txt">{html_escape(str(r["Dự án"]))}</td>'
                                  f'<td>{s:%H:%M}</td><td>{e:%H:%M}</td>'
                                  f'<td>{int(r["Thời lượng (Phút)"])}′</td>'
                                  f'<td class="txt">{html_escape(cat)}</td></tr>')
                rows_html += ('<tr class="cat"><td class="lbl"></td><td class="txt">Tổng</td><td></td><td></td>'
                              f'<td class="tot">{int(day_df["Thời lượng (Phút)"].sum())}′</td><td class="tot"></td></tr>')
                st.markdown(DTBL_CSS + f"""
<div class="dtbl-wrap"><table class="dtbl">
<thead><tr><th class="lbl">STT</th><th class="txt">Dự án</th><th>Bắt đầu</th><th>Kết thúc</th><th>Độ dài</th><th class="txt">Danh mục</th></tr></thead>
<tbody>{rows_html}</tbody>
</table></div>
""", unsafe_allow_html=True)

            with st.expander("5. Ngày này năm trước", expanded=False):
                render_on_this_day(sel, df)
# ==========================================
# TAB BÁO CÁO THEO NHÓM
# ==========================================
elif nav == "Báo cáo theo dự án":
    if not df.empty:
        # Gom dự án theo nhóm (Danh mục) và phân biệt rõ Nhóm vs Dự án trong dropdown
        proj_to_cat = df.dropna(subset=['Dự án']).groupby('Dự án')['Danh mục'].first()
        _opts, _labels = [], {}
        for _c in sorted(df['Danh mục'].dropna().unique()):
            _projs = sorted(proj_to_cat[proj_to_cat == _c].index.tolist())
            if _projs == [_c]:  # dự án chưa gán nhóm (nhóm trùng tên dự án) -> coi như một dự án độc lập
                _o = ("proj", _c); _opts.append(_o); _labels[_o] = f"{_c}  ·  Dự án"
            else:
                _oc = ("cat", _c); _opts.append(_oc); _labels[_oc] = f"{_c}  ·  Nhóm"
                for _p in _projs:
                    _op = ("proj", _p); _opts.append(_op); _labels[_op] = f"   {_p}  ·  Dự án"

        sel = st.selectbox("Chọn Nhóm hoặc Dự án:", _opts, format_func=lambda o: _labels[o], key="grp_sel")
        _kind, sel_grp = sel
        df_g = df[df['Danh mục'] == sel_grp] if _kind == "cat" else df[df['Dự án'] == sel_grp]
        
        with st.expander("1. Tổng quan", expanded=True):
            curr_hrs_g = df_g['Thời lượng (Phút)'].sum() / 60
            curr_trees_g = len(df_g)
            num_days_g = df_g['Ngày'].nunique() or 1
            num_weeks_g = df_g['Tuần'].nunique() or 1

            first_day = pd.Timestamp(df_g['Ngày'].min()).strftime('%d/%m/%Y') if pd.notna(df_g['Ngày'].min()) else "—"
            last_day = pd.Timestamp(df_g['Ngày'].max()).strftime('%d/%m/%Y') if pd.notna(df_g['Ngày'].max()) else "—"

            s_g = _streak_stats(df_g)
            wd_g = _weekday_avg(df_g)

            _grp_sections = [
                {"label": "Trung bình", "chips": [
                    {"k": "Thời gian / ngày", "v": f"{curr_hrs_g/num_days_g:.1f}h"},
                    {"k": "Thời gian / tuần", "v": f"{curr_hrs_g/num_weeks_g:.1f}h"},
                    {"k": "Số cây / ngày", "v": f"{curr_trees_g/num_days_g:.1f}"},
                    {"k": "Số cây / tuần", "v": f"{curr_trees_g/num_weeks_g:.1f}"},
                    {"k": "Thời gian / phiên", "v": f"{_avg_session_min(df_g):.0f} phút"},
                ]},
            ]

            df_g_thisweek = df_g[df_g['Tuần'] == date.today().strftime('%G-W%V')]
            if not df_g_thisweek.empty:
                _grp_sections.append({"label": "Tuần này", "chips": [
                    {"k": "Thời gian", "v": f"{df_g_thisweek['Thời lượng (Phút)'].sum()/60:.1f}h", "hl": True},
                    {"k": "Số cây", "v": f"{len(df_g_thisweek)}", "hl": True},
                ]})

            # "Tổng cộng" của chuỗi chính là số ngày hoạt động -> bỏ trùng ở Mốc thời gian
            _grp_sections.append({"label": "Chuỗi ngày", "chips": [
                {"k": "Tổng cộng", "v": f"{s_g['total']} ngày"},
                {"k": "Dài nhất", "v": f"{s_g['longest']} ngày"},
                {"k": "Hiện tại", "v": f"{s_g['current']} ngày", "hl": True},
            ]})
            if len(wd_g) and wd_g.max() > 0:
                _grp_sections.append({"label": "Theo thứ", "chips": [
                    {"k": "Mạnh nhất", "v": f"{wd_g.idxmax()} ({wd_g.max():.1f}h)"},
                    {"k": "Yếu nhất", "v": f"{wd_g.idxmin()} ({wd_g.min():.1f}h)"},
                ]})
            _grp_sections.append({"label": "Mốc thời gian", "chips": [
                {"k": "Ngày đầu tiên", "v": first_day},
                {"k": "Ngày gần nhất", "v": last_day},
            ]})

            _nud_g = _streak_nudge(s_g)
            _footer_g = (_nud_g[0],) + NUDGE_TONES[_nud_g[1]] if _nud_g else None

            render_stat_panel(
                hero_items=[
                    {"label": "Tổng thời gian", "value": f"{curr_hrs_g:.1f}h"},
                    {"label": "Số cây đã trồng", "value": f"{curr_trees_g}"},
                ],
                sections=_grp_sections,
                footer=_footer_g,
            )
            render_session_bar(df_g)
        with st.expander("2. Biểu đồ lịch", expanded=False):
            df_g_cal = range_radio(df_g, key="range_grp_cal")
            render_calendar_grid(df_g_cal, df_g_cal)
        with st.expander("3. Xu hướng theo thời gian", expanded=False):
            g1, g2, g3 = st.columns([5, 3, 2])
            with g1:
                _rlg = st.segmented_control("Khoảng thời gian", list(RANGE_OPTS.keys()), default="90 ngày", key="range_trend_grp")
            with g2:
                time_col_5 = st.segmented_control("Gộp theo", ["Ngày", "Tuần", "Tháng"], default="Ngày", key="time_tab5")
            with g3:
                color_col_5 = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default="Dự án", key="rad_tab5")
            _rlg = _rlg or "90 ngày"
            time_col_5 = time_col_5 or "Ngày"
            color_col_5 = color_col_5 or "Dự án"
            df_g_trend = filter_by_range(df_g, _rlg)

            tg = df_g_trend.groupby([time_col_5, color_col_5])['Thời lượng (Phút)'].sum().reset_index()
            tg['Số giờ'] = tg['Thời lượng (Phút)'] / 60
            if time_col_5 == "Ngày":
                tg['Ngày'] = pd.to_datetime(tg['Ngày'])
            fig_g = render_trend_fig(tg, time_col_5, color_col_5,
                                     ma_df=df_g_trend if time_col_5 == "Ngày" else None)
            fig_g.update_layout(width=CHART_WIDTH)
            st.plotly_chart(fig_g, width='stretch', config=PLOTLY_CONFIG)
        with st.expander("4. Phân bố độ dài phiên", expanded=False):
            render_session_histogram(df_g)
        with st.expander("5. Bảng số liệu", expanded=False):
            grp_view = st.segmented_control("Xem theo", ["Tuần", "Tháng"], default="Tháng", key="view_grp")
            grp_view = grp_view or "Tháng"
            render_period_table(df_g, 'Tuần' if grp_view == "Tuần" else 'Tháng')
        if _kind == "cat" and sel_grp == BOOKS_GROUP:
            books_df = df_g[~df_g['Dự án'].isin(BOOKS_EXCLUDE)]
            if books_df['Dự án'].nunique() >= 1:
                with st.expander("6. Nhật ký đọc sách", expanded=False):
                    render_reading_log(books_df, df['Ngày'].max())
# ==========================================
# TAB CHUẨN BỊ DỮ LIỆU
# ==========================================
elif nav == "Chuẩn bị dữ liệu":
    with st.expander("1. Tải lên từ Forest", expanded=True):
        _msg = st.session_state.pop('import_msg', None)
        if _msg:
            st.success(_msg)
        st.caption("Dùng file CSV xuất từ app Forest — cần các cột Tag/Project, Start Time, End Time, Is Success.")
        forest_file = st.file_uploader("Tải lên file CSV từ máy tính", type=["csv"], key="forest")
        if forest_file:
            df_new, stats, missing = parse_forest_csv(forest_file)
            if missing:
                st.error("File thiếu cột: " + ", ".join(missing) + ". Hãy dùng CSV xuất từ Forest (Tag/Project, Start Time, End Time, Is Success).")
            elif df_new.empty:
                st.warning("Không tìm thấy phiên hợp lệ nào trong file.")
            else:
                deleted = load_deleted()
                skipped_deleted = 0
                if not deleted.empty:
                    del_keys = set(zip(deleted['Thời gian bắt đầu'].astype(str),
                                       deleted['Thời gian kết thúc'].astype(str)))
                    keep = [(s, e) not in del_keys for s, e in
                            zip(df_new['Thời gian bắt đầu'].astype(str), df_new['Thời gian kết thúc'].astype(str))]
                    skipped_deleted = len(df_new) - sum(keep)
                    df_new = df_new[keep]
                _extra = f", {skipped_deleted} phiên đã xoá trước đó" if skipped_deleted else ""
                if df_new.empty:
                    st.info(f"Tất cả {stats['valid']} phiên hợp lệ đều đã nằm trong danh sách đã xoá trước đó — không có gì để thêm.")
                else:
                    st.caption(f"Đọc được **{stats['valid']}** phiên hợp lệ — bỏ {stats['failed']} phiên thất bại, "
                               f"{stats['unset']} phiên unset/rỗng{_extra}. Xem trước:")
                    preview = df_new.head(8).copy()
                    preview['Thời gian bắt đầu'] = preview['Thời gian bắt đầu'].dt.strftime('%Y-%m-%d %H:%M')
                    preview['Thời gian kết thúc'] = preview['Thời gian kết thúc'].dt.strftime('%Y-%m-%d %H:%M')
                    st.dataframe(preview, width='stretch', hide_index=True)
                    if st.button("Xác nhận cập nhật dữ liệu", type="primary"):
                        db = load_db()
                        before = len(db)
                        rng = f" · {df_new['Thời gian bắt đầu'].min():%d/%m/%Y}–{df_new['Thời gian kết thúc'].max():%d/%m/%Y}"
                        combined = pd.concat([db, df_new])
                        combined['Thời gian bắt đầu'] = combined['Thời gian bắt đầu'].astype(str)
                        combined['Thời gian kết thúc'] = combined['Thời gian kết thúc'].astype(str)
                        combined = combined.drop_duplicates(subset=['Thời gian bắt đầu', 'Thời gian kết thúc'], keep='first')
                        added = len(combined) - before
                        dup = stats['valid'] - skipped_deleted - added
                        save_db(combined)
                        st.session_state['import_msg'] = (
                            f"Đã thêm {added} phiên mới (bỏ {dup} trùng, {stats['failed']} thất bại, "
                            f"{stats['unset']} unset{_extra}){rng if added else ''}.")
                        st.rerun()
    with st.expander("2. Phân loại", expanded=True):
        db_current = load_db()
        mapping_df = load_mapping()
        all_projs = sorted(db_current['Dự án'].dropna().astype(str).unique()) if not db_current.empty else []
        cur_map = dict(zip(mapping_df['Dự án'].astype(str), mapping_df['Danh mục'])) if not mapping_df.empty else {}
        if not all_projs:
            st.info("Chưa có dự án nào. Hãy tải dữ liệu ở mục 1 trước.")
        else:
            existing_cats = sorted({str(v) for v in cur_map.values() if pd.notna(v) and str(v).strip()})
            unmapped = [p for p in all_projs if not (cur_map.get(p) and str(cur_map.get(p)).strip())]
            if unmapped:
                _show = ", ".join(unmapped[:8]) + ("…" if len(unmapped) > 8 else "")
                st.warning(f"Còn **{len(unmapped)}** dự án chưa phân loại: {_show}")
            else:
                st.success("Tất cả dự án đã được phân loại.")

            new_cat = st.text_input("Tạo nhóm mới (tuỳ chọn — sẽ xuất hiện trong danh sách chọn ở cột Nhóm):").strip()
            opts = sorted(set(existing_cats) | ({new_cat} if new_cat else set()))
            st.caption("Chọn Nhóm cho từng dự án (gõ ở ô trên để thêm nhóm mới). Để trống = bỏ phân loại.")
            tbl = pd.DataFrame({"Dự án": all_projs, "Nhóm (Danh mục)": [cur_map.get(p) for p in all_projs]})
            edited = st.data_editor(
                tbl, hide_index=True, width='stretch', key="map_editor",
                column_config={
                    "Dự án": st.column_config.TextColumn("Dự án", disabled=True),
                    "Nhóm (Danh mục)": st.column_config.SelectboxColumn("Nhóm (Danh mục)", options=opts),
                },
            )
            if st.button("Lưu phân loại", type="primary"):
                nm = edited.rename(columns={"Nhóm (Danh mục)": "Danh mục"})
                nm = nm[nm["Danh mục"].notna() & (nm["Danh mục"].astype(str).str.strip() != "")]
                save_mapping(nm[["Dự án", "Danh mục"]].reset_index(drop=True))
                st.rerun()
    with st.expander("3. Dữ liệu làm việc hiện tại", expanded=True):
        if not db_current.empty:
            db_base = db_current.reset_index(drop=True)
            _dt = pd.to_datetime(db_base['Thời gian bắt đầu'], errors='coerce')
            st.caption(f"Tổng **{len(db_base)}** phiên · từ {_dt.min():%d/%m/%Y} đến {_dt.max():%d/%m/%Y}. "
                       "Bấm tiêu đề cột để sắp xếp; tích chọn dòng để xoá.")
            disp_db = db_base.copy()
            disp_db['Thời gian bắt đầu'] = pd.to_datetime(disp_db['Thời gian bắt đầu']).dt.strftime('%Y-%m-%d %H:%M')
            disp_db['Thời gian kết thúc'] = pd.to_datetime(disp_db['Thời gian kết thúc']).dt.strftime('%Y-%m-%d %H:%M')
            if 'Note' in disp_db.columns: disp_db = disp_db.drop(columns=['Note'])
            ev = st.dataframe(disp_db, width='stretch', hide_index=True,
                              on_select="rerun", selection_mode="multi-row", key="db_view")
            sel_rows = list(ev.selection.rows) if ev and ev.selection else []
            if sel_rows and st.button(f"Xoá {len(sel_rows)} phiên đã chọn", type="primary"):
                add_deleted(db_base.loc[sel_rows, ['Thời gian bắt đầu', 'Thời gian kết thúc']])
                save_db(db_base.drop(index=sel_rows).reset_index(drop=True))
                st.rerun()
            st.caption("Phiên đã xoá sẽ không bị nạp lại khi tải file Forest mới (kể cả khi file đó vẫn còn phiên này).")
    with st.expander("4. Quản lý hệ thống", expanded=True):
        c1, c2, c3 = st.columns(3)
        _today = date.today().strftime('%Y-%m-%d')
        with c1:
            st.subheader("Sao lưu")
            st.caption("Một file .zip gồm dữ liệu, phân loại, danh sách đã xoá và ghi chú; tên kèm ngày để dễ phân biệt.")
            if os.path.exists(DB_FILE):
                _buf = io.BytesIO()
                with zipfile.ZipFile(_buf, "w", zipfile.ZIP_DEFLATED) as _z:
                    for _fn in [DB_FILE, MAPPING_FILE, DELETED_FILE, NOTES_FILE]:
                        if os.path.exists(_fn):
                            _z.write(_fn, arcname=os.path.basename(_fn))
                st.download_button("Tải bản sao lưu", _buf.getvalue(),
                                   f"forest_backup_{_today}.zip", "application/zip")
            else:
                st.caption("Chưa có dữ liệu để sao lưu.")
        with c2:
            st.subheader("Khôi phục")
            res = st.file_uploader("Tải lên bản sao lưu (.zip)", type=["zip"], key="r_zip")
            ok_zip = False
            if res is not None:
                try:
                    res.seek(0)
                    with zipfile.ZipFile(res) as _z:
                        names = set(_z.namelist())
                        parts = []
                        if DB_FILE in names:
                            _pdb = pd.read_csv(io.BytesIO(_z.read(DB_FILE)))
                            _dt = pd.to_datetime(_pdb.get('Thời gian bắt đầu'), errors='coerce')
                            _rng = f" {_dt.min():%d/%m/%Y}–{_dt.max():%d/%m/%Y}" if _dt.notna().any() else ""
                            parts.append(f"Dữ liệu **{len(_pdb)}** phiên{_rng}")
                        if MAPPING_FILE in names:
                            parts.append(f"Phân loại **{len(pd.read_csv(io.BytesIO(_z.read(MAPPING_FILE))))}** dự án")
                        if DELETED_FILE in names:
                            parts.append(f"Đã xoá **{len(pd.read_csv(io.BytesIO(_z.read(DELETED_FILE))))}** phiên")
                        if NOTES_FILE in names:
                            parts.append(f"Ghi chú **{len(pd.read_csv(io.BytesIO(_z.read(NOTES_FILE))))}** ngày")
                    if parts:
                        ok_zip = True
                        st.caption("Bản sao lưu gồm — " + " · ".join(parts) + ".")
                    else:
                        st.caption("File .zip không chứa dữ liệu hợp lệ.")
                except Exception:
                    st.caption("Không đọc được file — cần đúng bản .zip xuất từ app.")
            if ok_zip:
                st.warning("Khôi phục sẽ **ghi đè** toàn bộ dữ liệu hiện tại bằng nội dung bản sao lưu.")
            if st.button("Xác nhận Khôi phục", type="primary", disabled=not ok_zip):
                res.seek(0)
                with zipfile.ZipFile(res) as _z:
                    names = set(_z.namelist())
                    if DB_FILE in names: save_db(pd.read_csv(io.BytesIO(_z.read(DB_FILE))))
                    if MAPPING_FILE in names: save_mapping(pd.read_csv(io.BytesIO(_z.read(MAPPING_FILE))))
                    if DELETED_FILE in names:
                        with open(DELETED_FILE, "wb") as _f: _f.write(_z.read(DELETED_FILE))
                    if NOTES_FILE in names:
                        with open(NOTES_FILE, "wb") as _f: _f.write(_z.read(NOTES_FILE))
                st.cache_data.clear()
                st.success("Khôi phục hệ thống thành công!")
                time.sleep(1)
                st.rerun()
        with c3:
            st.subheader("Làm mới")
            confirm_delete = st.checkbox("Tôi xác nhận muốn xoá toàn bộ dữ liệu")
            if st.button("Xoá toàn bộ dữ liệu", disabled=not confirm_delete):
                if os.path.exists(DB_FILE): os.remove(DB_FILE)
                if os.path.exists(MAPPING_FILE): os.remove(MAPPING_FILE)
                if os.path.exists(DELETED_FILE): os.remove(DELETED_FILE)
                if os.path.exists(NOTES_FILE): os.remove(NOTES_FILE)
                st.cache_data.clear()
                st.success("Đã xoá toàn bộ dữ liệu cục bộ!")
                time.sleep(1)
                st.rerun()