import streamlit as st
import pandas as pd
import os
import time
import plotly.express as px
import plotly.graph_objects as go
import altair as alt
import colorsys
from html import escape as html_escape
from datetime import date, timedelta

# --- CẤU HÌNH ---
DB_FILE = "database.csv"
MAPPING_FILE = "mapping.csv"

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
    
    tieng_viet_days = {"Monday": "Thứ 2", "Tuesday": "Thứ 3", "Wednesday": "Thứ 4", "Thursday": "Thứ 5", "Friday": "Thứ 6", "Saturday": "Thứ 7", "Sunday": "Chủ Nhật"}
    db['Thứ'] = db['Thời gian bắt đầu'].dt.day_name().map(tieng_viet_days)
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


def render_trend_fig(grouped, time_col, color_col, view, ma_df=None, cat_order=None, x_title=None):
    """Biểu đồ xu hướng theo Kiểu xem: Cột chồng / Tỉ trọng % / Đường.
    grouped: đã group theo [time_col, color_col], có cột 'Số giờ'.
    ma_df: nếu truyền (chỉ khi trục là ngày) -> phủ đường TB động 7 ngày ở chế độ Cột chồng.
    cat_order: thứ tự hạng mục cho trục x (vd các thứ trong tuần)."""
    is_day = time_col == "Ngày"
    co = {time_col: cat_order} if cat_order else None
    if view == "Đường":
        fig = px.line(grouped, x=time_col, y='Số giờ', color=color_col, color_discrete_map=COLOR_MAP, category_orders=co)
    else:
        fig = px.bar(grouped, x=time_col, y='Số giờ', color=color_col, color_discrete_map=COLOR_MAP, category_orders=co)
        if view == "Tỉ trọng %":
            fig.update_layout(barnorm='percent')  # barnorm là thuộc tính layout, không phải tham số của px.bar

    if is_day:
        fig = add_week_dividers(fig, grouped[time_col])
        if view == "Cột chồng" and ma_df is not None:
            fig = add_ma_overlay(fig, ma_df, 7)
    elif view == "Cột chồng":
        fig = add_total_labels(fig, grouped, time_col, 'Số giờ')

    ytitle = "Tỉ trọng (%)" if view == "Tỉ trọng %" else "Số giờ"
    fig.update_layout(xaxis_title=x_title or time_col, yaxis_title=ytitle)
    fig = format_plotly_fig(fig)
    if view == "Tỉ trọng %":
        fig.update_traces(hovertemplate='<b>%{data.name}</b><br>%{y:.1f}%<extra></extra>')
    return fig

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


def render_top_3(df, col_name, title, week_key=None):
    if df.empty:
        html_list = "<p style='color:#86868b; font-size: 14px;'>Không có dữ liệu</p>"
    else:
        top3 = df.groupby(col_name)['Thời lượng (Phút)'].sum().sort_values(ascending=False).head(3)
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


def _session_hour_dist(scope_df, color_col):
    """Trải thời lượng MỖI phiên ra các khung giờ mà nó thực sự đi qua (thay vì dồn
    hết vào giờ bắt đầu). Trả về DataFrame (Khung giờ, color_col, giờ)."""
    out = []
    for s, e, c in zip(scope_df['Thời gian bắt đầu'], scope_df['Thời gian kết thúc'], scope_df[color_col]):
        if pd.isna(s) or pd.isna(e) or e <= s:
            continue
        cur = s
        while cur < e:
            nxt = cur.floor('h') + pd.Timedelta(hours=1)
            seg_end = e if e < nxt else nxt
            out.append((int(cur.hour), c, (seg_end - cur).total_seconds() / 3600.0))
            cur = seg_end
    return pd.DataFrame(out, columns=['Khung giờ', color_col, 'giờ'])


def render_hourly_chart(scope_df, color_col, x_title="Khung giờ"):
    if scope_df.empty:
        return
    num_days = scope_df['Ngày'].nunique() or 1
    dist = _session_hour_dist(scope_df, color_col)
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


def _dayhour_dist(scope_df):
    """Trải thời lượng mỗi phiên ra (thứ, khung giờ). Thứ lấy theo thời điểm bắt đầu phiên."""
    out = []
    for s, e, wd in zip(scope_df['Thời gian bắt đầu'], scope_df['Thời gian kết thúc'], scope_df['Thứ']):
        if pd.isna(s) or pd.isna(e) or e <= s:
            continue
        cur = s
        while cur < e:
            nxt = cur.floor('h') + pd.Timedelta(hours=1)
            seg_end = e if e < nxt else nxt
            out.append((wd, int(cur.hour), (seg_end - cur).total_seconds() / 3600.0))
            cur = seg_end
    return pd.DataFrame(out, columns=['Thứ', 'Khung giờ', 'giờ'])


def render_dayhour_heatmap(scope_df):
    """Bản đồ nhiệt 7 thứ × 24 giờ: ô càng đậm = trung bình giờ/ngày ở khung giờ đó
    của thứ đó càng cao -> nhận ra 'tập trung tốt nhất vào sáng thứ mấy'."""
    if scope_df.empty:
        return
    d = _dayhour_dist(scope_df)
    if d.empty:
        return
    days_map = {"Monday": "Thứ 2", "Tuesday": "Thứ 3", "Wednesday": "Thứ 4", "Thursday": "Thứ 5",
                "Friday": "Thứ 6", "Saturday": "Thứ 7", "Sunday": "Chủ Nhật"}
    span = pd.date_range(pd.Timestamp(scope_df['Ngày'].min()), pd.Timestamp(scope_df['Ngày'].max()))
    wd_count = pd.Series(span.day_name()).map(days_map).value_counts()

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
    days_map = {"Monday": "Thứ 2", "Tuesday": "Thứ 3", "Wednesday": "Thứ 4", "Thursday": "Thứ 5",
                "Friday": "Thứ 6", "Saturday": "Thứ 7", "Sunday": "Chủ Nhật"}
    wd_count = pd.Series(pd.date_range(mn, mx).day_name()).map(days_map).value_counts()
    by = scope_df.groupby('Thứ')['Thời lượng (Phút)'].sum() / 60
    return (by / wd_count).reindex(DAYS_ORDER).dropna()


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
    days_map = {"Monday": "Thứ 2", "Tuesday": "Thứ 3", "Wednesday": "Thứ 4", "Thursday": "Thứ 5", "Friday": "Thứ 6", "Saturday": "Thứ 7", "Sunday": "Chủ Nhật"}
    cal_data['Thứ'] = cal_data['Ngày'].dt.day_name().map(days_map)
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


def _heat_cell(v, ref, extra_cls=""):
    """Một ô số: <0.05 -> dấu chấm mờ; ngược lại tô nền xanh theo tỉ lệ v/ref."""
    cls = extra_cls.strip()
    if v < 0.05:
        return f'<td class="{(cls + " zero").strip()}">·</td>'
    a = min(v / ref, 1.0) * 0.7 if ref > 0 else 0
    bg = f'background:rgba(52,199,89,{a:.2f});' if a > 0.02 else ''
    cls_attr = f' class="{cls}"' if cls else ''
    return f'<td{cls_attr} style="{bg}">{v:.1f}</td>'


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

    head = ''.join(f'<th>{col_label(c)}</th>' for c in cols)
    rows_html = ''
    for c in sorted(cat.index):
        c_vals = cat.loc[c]
        c_total = float(c_vals.sum())
        rows_html += '<tr class="cat">'
        rows_html += f'<td class="lbl">{html_escape(str(c))}</td>'
        rows_html += ''.join(_heat_cell(float(c_vals[col]), vmax_cat) for col in cols)
        rows_html += _heat_cell(c_total, 0, "tot")   # cột Tổng không tô heat cho gọn
        rows_html += '</tr>'

        sub = proj[proj.index.get_level_values(0) == c].sort_index(level=1)
        for idx, row in sub.iterrows():
            p_total = float(row.sum())
            rows_html += '<tr class="proj">'
            rows_html += f'<td class="lbl">{html_escape(str(idx[1]))}</td>'
            rows_html += ''.join(_heat_cell(float(row[col]), vmax_proj) for col in cols)
            rows_html += _heat_cell(p_total, 0, "tot")
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

    rows_html = ''
    for c in sorted(cat.index):
        rows_html += '<tr class="cat">'
        rows_html += f'<td class="lbl">{html_escape(str(c))}</td>'
        rows_html += _heat_cell(float(cat.loc[c]), vmax_cat)
        rows_html += '</tr>'

        sub = proj[proj.index.get_level_values(0) == c].sort_index(level=1)
        for idx, v in sub.items():
            rows_html += '<tr class="proj">'
            rows_html += f'<td class="lbl">{html_escape(str(idx[1]))}</td>'
            rows_html += _heat_cell(float(v), vmax_proj)
            rows_html += '</tr>'

    st.markdown(DTBL_CSS + f"""
<div class="dtbl-wrap"><table class="dtbl">
<thead><tr><th class="lbl">Danh mục / Dự án</th><th>Số giờ</th></tr></thead>
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


def render_plain_table(df, num_cols=()):
    """Bảng liệt kê đơn giản (quy tắc, log) cùng phong cách: cột chữ căn trái, cột số căn phải."""
    if df.empty:
        return
    cols = list(df.columns)
    head = f'<th class="lbl">{html_escape(str(df.index.name or "#"))}</th>'
    for c in cols:
        cls = '' if c in num_cols else ' class="txt"'
        head += f'<th{cls}>{html_escape(str(c))}</th>'
    body = ''
    for i, row in df.iterrows():
        body += '<tr class="prow">'
        body += f'<td class="lbl">{html_escape(str(i))}</td>'
        for c in cols:
            cls = 'num' if c in num_cols else 'txt'
            body += f'<td class="{cls}">{html_escape(str(row[c]))}</td>'
        body += '</tr>'

    st.markdown(DTBL_CSS + f"""
<div class="dtbl-wrap"><table class="dtbl">
<thead><tr>{head}</tr></thead>
<tbody>{body}</tbody>
</table></div>
""", unsafe_allow_html=True)


# --- GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="Forest Dashboard", page_icon=":material/forest:", layout="wide")

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
    "Báo cáo theo nhóm": ":material/category:",
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
                recent_chips.append({"k": "Giờ / ngày", "v": f"{r_avg:.1f}h", "delta": _delta})
            recent_chips.append({"k": "Số ngày hoạt động", "v": f"{r_days}/7"})

            s_stat = _streak_stats(df)
            by_wd = _weekday_avg(df)
            _sections = [
                {"label": "Trung bình (toàn thời gian)", "chips": [
                    {"k": "Thời gian / ngày", "v": f"{base_avg:.1f}h"},
                    {"k": "Số cây / ngày", "v": f"{total_trees/num_days:.1f}"},
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

            st.write("")
            c_top1, c_top2 = st.columns(2)
            _wk_now = date.today().strftime('%G-W%V')
            with c_top1: render_top_3(df, 'Danh mục', 'Top 3 Danh mục', week_key=_wk_now)
            with c_top2: render_top_3(df, 'Dự án', 'Top 3 Dự án', week_key=_wk_now)
        with st.expander("2. Biểu đồ lịch tổng quan", expanded=True):
            df_cal = range_radio(df, key="range_cal")
            render_calendar_grid(df_cal, df_cal)
        with st.expander("3. Xu hướng theo thời gian", expanded=True):
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
            view_2 = st.segmented_control("Kiểu xem", ["Cột chồng", "Tỉ trọng %", "Đường"], default="Cột chồng", key="view_trend2")
            view_2 = view_2 or "Cột chồng"
            df_trend = filter_by_range(df, _rl)

            trend_group = df_trend.groupby([time_col_2, color_col_2])['Thời lượng (Phút)'].sum().reset_index()
            trend_group['Số giờ'] = trend_group['Thời lượng (Phút)'] / 60
            if time_col_2 == "Ngày":
                trend_group['Ngày'] = pd.to_datetime(trend_group['Ngày'])
            fig1 = render_trend_fig(trend_group, time_col_2, color_col_2, view_2,
                                    ma_df=df_trend if time_col_2 == "Ngày" else None)
            fig1.update_layout(width=CHART_WIDTH)
            st.plotly_chart(fig1, width='stretch', config=PLOTLY_CONFIG)
        with st.expander("4. Xu hướng làm việc theo khung giờ", expanded=True):
            st.caption(f"Theo khoảng thời gian đã chọn ở mục 3: {_rl}")
            render_hourly_chart(df_trend, color_col_2, x_title="Khung giờ (0h - 23h)")
        with st.expander("5. Giờ tập trung theo thứ", expanded=True):
            st.caption(f"Trung bình giờ/ngày theo thứ × khung giờ — theo khoảng đã chọn ở mục 3: {_rl}")
            render_dayhour_heatmap(df_trend)
        with st.expander("6. Bảng số liệu", expanded=True):
            st.caption(f"Theo khoảng thời gian đã chọn ở mục 3: {_rl}")
            view_opt = st.segmented_control("Xem theo", ["Tuần", "Tháng"], default="Tuần", key="view_tab1")
            view_opt = view_opt or "Tuần"
            time_col = 'Tuần' if view_opt == "Tuần" else 'Tháng'
            render_data_table(df_trend, time_col)
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
        else:
            avg_hrs_month = avg_trees_month = avg_hrs_day_month = avg_trees_day_month = None

        y, m = map(int, selected_month.split('-'))
        prev_month_key = f"{y - 1:04d}-12" if m == 1 else f"{y:04d}-{m - 1:02d}"
        df_prev_month = df[df['Tháng'] == prev_month_key]
        if not df_prev_month.empty:
            prev_hrs_month = df_prev_month['Thời lượng (Phút)'].sum() / 60
            prev_trees_month = len(df_prev_month)
            prev_days_month = df_prev_month['Ngày'].nunique() or 1
            prev_hrs_day_month = prev_hrs_month / prev_days_month
            prev_trees_day_month = prev_trees_month / prev_days_month
        else:
            prev_hrs_month = prev_trees_month = prev_hrs_day_month = prev_trees_day_month = None
        
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

                render_stat_panel(hero_items=[
                    {"label": "Tổng thời gian", "value": f"{curr_hrs:.1f}h", "deltas": [d for d in [_delta_t(delta1_hr, "h vs Tháng trước"), _delta_t(delta2_hr, "h vs Trung bình")] if d]},
                    {"label": "Thời gian TB/ngày", "value": f"{curr_hrs_day:.1f}h", "deltas": [d for d in [_delta_t(delta1_hrd, "h vs Tháng trước"), _delta_t(delta2_hrd, "h vs Trung bình")] if d]},
                    {"label": "Số cây đã trồng", "value": f"{curr_trees}", "deltas": [d for d in [_delta_t(delta1_tr, "cây vs Tháng trước"), _delta_t(delta2_tr, "cây vs Trung bình")] if d]},
                    {"label": "Số cây TB/ngày", "value": f"{curr_trees_day:.1f}", "deltas": [d for d in [_delta_t(delta1_trd, "cây vs Tháng trước"), _delta_t(delta2_trd, "cây vs Trung bình")] if d]},
                ])

                st.write("")
                c_top1, c_top2 = st.columns(2)
                with c_top1: render_top_3(df_m, 'Danh mục', 'Top 3 Danh mục Tháng')
                with c_top2: render_top_3(df_m, 'Dự án', 'Top 3 Dự án Tháng')
            with st.expander("2. Phân bổ thời gian", expanded=True):
                color_col_3 = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default="Danh mục", key="rad_tab3")
                color_col_3 = color_col_3 or "Danh mục"
                pc_m = df_m.groupby(color_col_3)['Thời lượng (Phút)'].sum().reset_index()
                pc_m['Số giờ'] = pc_m['Thời lượng (Phút)'] / 60
                fig_p_m = px.pie(pc_m, values='Số giờ', names=color_col_3, color=color_col_3, color_discrete_map=COLOR_MAP)
                fig_p_m.update_layout(width=CHART_WIDTH)
                fig_p_m = format_plotly_fig(fig_p_m, is_pie=True)
                st.plotly_chart(fig_p_m, width='stretch', config=PLOTLY_CONFIG)
            with st.expander("3. Xu hướng theo thời gian", expanded=True):
                view_3 = st.segmented_control("Kiểu xem", ["Cột chồng", "Tỉ trọng %", "Đường"], default="Cột chồng", key="view_trend3")
                view_3 = view_3 or "Cột chồng"
                t_m = df_m.groupby(['Ngày', color_col_3])['Thời lượng (Phút)'].sum().reset_index()
                t_m['Số giờ'] = t_m['Thời lượng (Phút)'] / 60
                t_m['Ngày'] = pd.to_datetime(t_m['Ngày'])
                fig_m = render_trend_fig(t_m, 'Ngày', color_col_3, view_3, ma_df=df_m, x_title="Ngày trong tháng")
                fig_m.update_layout(width=CHART_WIDTH)
                st.plotly_chart(fig_m, width='stretch', config=PLOTLY_CONFIG)
            with st.expander("4. Xu hướng làm việc theo khung giờ", expanded=True):
                render_hourly_chart(df_m, color_col_3)
            with st.expander("5. Giờ tập trung theo thứ", expanded=True):
                render_dayhour_heatmap(df_m)
            with st.expander("6. Bảng số liệu", expanded=True):
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
        else:
            avg_hrs_week = avg_trees_week = avg_hrs_day_week = avg_trees_day_week = None

        week_anchor = df_w['Thời gian bắt đầu'].min()
        prev_week_key = (week_anchor - pd.Timedelta(days=7)).strftime('%G-W%V') if pd.notna(week_anchor) else None
        df_prev_week = df[df['Tuần'] == prev_week_key]
        if not df_prev_week.empty:
            prev_hrs_week = df_prev_week['Thời lượng (Phút)'].sum() / 60
            prev_trees_week = len(df_prev_week)
            prev_days_week = df_prev_week['Ngày'].nunique() or 1
            prev_hrs_day_week = prev_hrs_week / prev_days_week
            prev_trees_day_week = prev_trees_week / prev_days_week
        else:
            prev_hrs_week = prev_trees_week = prev_hrs_day_week = prev_trees_day_week = None
        
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

                render_stat_panel(hero_items=[
                    {"label": "Tổng thời gian", "value": f"{curr_hrs_w:.1f}h", "deltas": [d for d in [_delta_t(d1_hr_w, "h vs Tuần trước"), _delta_t(d2_hr_w, "h vs Trung bình")] if d]},
                    {"label": "Thời gian TB/ngày", "value": f"{curr_hrs_day_w:.1f}h", "deltas": [d for d in [_delta_t(d1_hrd_w, "h vs Tuần trước"), _delta_t(d2_hrd_w, "h vs Trung bình")] if d]},
                    {"label": "Số cây đã trồng", "value": f"{curr_trees_w}", "deltas": [d for d in [_delta_t(d1_tr_w, "cây vs Tuần trước"), _delta_t(d2_tr_w, "cây vs Trung bình")] if d]},
                    {"label": "Số cây TB/ngày", "value": f"{curr_trees_day_w:.1f}", "deltas": [d for d in [_delta_t(d1_trd_w, "cây vs Tuần trước"), _delta_t(d2_trd_w, "cây vs Trung bình")] if d]},
                ])

                st.write("")
                c_top1, c_top2 = st.columns(2)
                with c_top1: render_top_3(df_w, 'Danh mục', 'Top 3 Danh mục Tuần')
                with c_top2: render_top_3(df_w, 'Dự án', 'Top 3 Dự án Tuần')
            with st.expander("2. Phân bổ thời gian", expanded=True):
                color_col_4 = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default="Danh mục", key="rad_tab4")
                color_col_4 = color_col_4 or "Danh mục"
                pc_w = df_w.groupby(color_col_4)['Thời lượng (Phút)'].sum().reset_index()
                pc_w['Số giờ'] = pc_w['Thời lượng (Phút)'] / 60
                fig_p_w = px.pie(pc_w, values='Số giờ', names=color_col_4, color=color_col_4, color_discrete_map=COLOR_MAP)
                fig_p_w.update_layout(width=CHART_WIDTH)
                fig_p_w = format_plotly_fig(fig_p_w, is_pie=True)
                st.plotly_chart(fig_p_w, width='stretch', config=PLOTLY_CONFIG)
            with st.expander("3. Xu hướng theo thời gian", expanded=True):
                view_4 = st.segmented_control("Kiểu xem", ["Cột chồng", "Tỉ trọng %", "Đường"], default="Cột chồng", key="view_trend4")
                view_4 = view_4 or "Cột chồng"
                t_w = df_w.groupby(['Thứ', color_col_4])['Thời lượng (Phút)'].sum().reset_index()
                t_w['Số giờ'] = t_w['Thời lượng (Phút)'] / 60
                fig_w = render_trend_fig(t_w, 'Thứ', color_col_4, view_4, cat_order=DAYS_ORDER, x_title="Thứ trong tuần")
                fig_w.update_layout(width=CHART_WIDTH)
                st.plotly_chart(fig_w, width='stretch', config=PLOTLY_CONFIG)
            with st.expander("4. Xu hướng làm việc theo khung giờ", expanded=True):
                render_hourly_chart(df_w, color_col_4)
            with st.expander("5. Giờ tập trung theo thứ", expanded=True):
                render_dayhour_heatmap(df_w)
            with st.expander("6. Bảng số liệu", expanded=True):
                render_detail_table(df_w)
# ==========================================
# TAB BÁO CÁO THEO NHÓM
# ==========================================
elif nav == "Báo cáo theo nhóm":
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
                    {"k": "TG / ngày", "v": f"{curr_hrs_g/num_days_g:.1f}h"},
                    {"k": "TG / tuần", "v": f"{curr_hrs_g/num_weeks_g:.1f}h"},
                    {"k": "Cây / ngày", "v": f"{curr_trees_g/num_days_g:.1f}"},
                    {"k": "Cây / tuần", "v": f"{curr_trees_g/num_weeks_g:.1f}"},
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
        with st.expander("2. Biểu đồ lịch", expanded=True):
            df_g_cal = range_radio(df_g, key="range_grp_cal")
            render_calendar_grid(df_g_cal, df_g_cal)
        with st.expander("3. Xu hướng theo thời gian", expanded=True):
            time_col_5 = st.segmented_control("Gộp theo", ["Ngày", "Tuần", "Tháng"], default="Ngày", key="time_tab5")
            time_col_5 = time_col_5 or "Ngày"
            t_g = df_g.groupby(time_col_5)['Thời lượng (Phút)'].sum().reset_index()
            t_g['Số giờ'] = t_g['Thời lượng (Phút)'] / 60

            if time_col_5 == "Ngày":
                t_g['Ngày'] = pd.to_datetime(t_g['Ngày'])
                fig_g = px.line(t_g, x=time_col_5, y='Số giờ', color_discrete_sequence=[MAC_COLORS[0]])
                fig_g.update_traces(name='Theo ngày', fill='tozeroy', fillcolor="rgba(0,122,255,0.1)")
                fig_g = add_week_dividers(fig_g, t_g['Ngày'])
                fig_g = add_ma_overlay(fig_g, df_g, 7)
            else:
                fig_g = px.bar(t_g, x=time_col_5, y='Số giờ', color_discrete_sequence=[MAC_COLORS[0]])
                fig_g = add_total_labels(fig_g, t_g, time_col_5, 'Số giờ')

            fig_g.update_layout(width=CHART_WIDTH, xaxis_title=time_col_5, yaxis_title="Số giờ")
            fig_g = format_plotly_fig(fig_g)
            st.plotly_chart(fig_g, width='stretch', config=PLOTLY_CONFIG)
        with st.expander("4. Bảng số liệu", expanded=True):
            grp_view = st.segmented_control("Xem theo", ["Tuần", "Tháng"], default="Tháng", key="view_grp")
            grp_view = grp_view or "Tháng"
            render_period_table(df_g, 'Tuần' if grp_view == "Tuần" else 'Tháng')
# ==========================================
# TAB CHUẨN BỊ DỮ LIỆU
# ==========================================
elif nav == "Chuẩn bị dữ liệu":
    with st.expander("1. Tải lên từ Forest", expanded=True):
        forest_file = st.file_uploader("Tải lên file CSV từ máy tính", type=["csv"], key="forest")
        if forest_file:
            if st.button("Xác nhận cập nhật dữ liệu", type="primary"):
                new_data = pd.read_csv(forest_file)
                if 'Tag' in new_data.columns: new_data.rename(columns={'Tag': 'Dự án'}, inplace=True)
                if 'Project' in new_data.columns: new_data.rename(columns={'Project': 'Dự án'}, inplace=True)
                if 'Start Time' in new_data.columns: new_data.rename(columns={'Start Time': 'Thời gian bắt đầu'}, inplace=True)
                if 'End Time' in new_data.columns: new_data.rename(columns={'End Time': 'Thời gian kết thúc'}, inplace=True)
                if 'Is Success' in new_data.columns: new_data = new_data[new_data['Is Success'] == True]
                required = ['Dự án', 'Thời gian bắt đầu', 'Thời gian kết thúc']
                missing = [c for c in required if c not in new_data.columns]
                if not missing:
                    new_data = new_data.dropna(subset=['Dự án'])
                    new_data['Thời gian bắt đầu'] = pd.to_datetime(new_data['Thời gian bắt đầu'], errors='coerce')
                    new_data['Thời gian kết thúc'] = pd.to_datetime(new_data['Thời gian kết thúc'], errors='coerce')
                    new_data['Thời lượng (Phút)'] = ((new_data['Thời gian kết thúc'] - new_data['Thời gian bắt đầu']).dt.total_seconds() / 60).round().astype(int)
                    cols = ['Thời gian bắt đầu', 'Thời gian kết thúc', 'Dự án', 'Thời lượng (Phút)']
                    new_data = new_data[[c for c in cols if c in new_data.columns]]
                    db = load_db()
                    combined_db = pd.concat([db, new_data])
                    combined_db = combined_db.dropna(subset=['Dự án'])
                    combined_db = combined_db[~combined_db['Dự án'].astype(str).str.strip().str.lower().isin(['unset', ''])]
                    combined_db['Thời gian bắt đầu'] = combined_db['Thời gian bắt đầu'].astype(str)
                    combined_db['Thời gian kết thúc'] = combined_db['Thời gian kết thúc'].astype(str)
                    combined_db = combined_db.drop_duplicates(subset=['Thời gian bắt đầu', 'Thời gian kết thúc'], keep='first')
                    save_db(combined_db)
                    st.success("Đã cập nhật dữ liệu thành công!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("File không hợp lệ. Thiếu cột: " + ", ".join(missing) + ". Hãy dùng file CSV xuất từ Forest (Tag/Project, Start Time, End Time).")
    with st.expander("2. Phân loại", expanded=True):
        db_current = load_db()
        mapping_df = load_mapping()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Thêm quy tắc mới")
            all_projs = db_current['Dự án'].unique() if not db_current.empty else []
            mapped_projs = mapping_df['Dự án'].tolist() if not mapping_df.empty else []
            unmapped_projs = [p for p in all_projs if p not in mapped_projs]
            sel_proj = st.selectbox("Chọn Dự án:", unmapped_projs if unmapped_projs else ["Không có Dự án mới"])
            new_cat = st.text_input("Nhập tên nhóm (Danh mục):")
            if st.button("Lưu quy tắc", type="primary") and new_cat and sel_proj != "Không có Dự án mới":
                new_rule = pd.DataFrame({"Dự án": [sel_proj], "Danh mục": [new_cat]})
                mapping_df = pd.concat([mapping_df, new_rule]).drop_duplicates(subset=['Dự án'], keep='last')
                save_mapping(mapping_df)
                st.success("Đã thêm quy tắc phân loại!")
                time.sleep(0.5)
                st.rerun()
            st.subheader("Bỏ quy tắc cũ")
            if not mapping_df.empty:
                rule_to_remove = st.selectbox("Chọn quy tắc muốn xoá:", mapping_df['Dự án'].tolist())
                if st.button("Xoá quy tắc"):
                    mapping_df = mapping_df[mapping_df['Dự án'] != rule_to_remove]
                    save_mapping(mapping_df)
                    st.success("Đã xoá quy tắc phân loại!")
                    time.sleep(0.5)
                    st.rerun()
        with col2:
            st.subheader("Bảng quy tắc hiện tại")
            if not mapping_df.empty:
                display_map = mapping_df.sort_values(by='Danh mục').reset_index(drop=True)
                display_map.index = display_map.index + 1
                render_plain_table(display_map)
    with st.expander("3. Dữ liệu làm việc hiện tại", expanded=True):
        if not db_current.empty:
            disp_db = db_current.copy()
            disp_db['Thời gian bắt đầu'] = pd.to_datetime(disp_db['Thời gian bắt đầu']).dt.strftime('%Y-%m-%d %H:%M')
            disp_db['Thời gian kết thúc'] = pd.to_datetime(disp_db['Thời gian kết thúc']).dt.strftime('%Y-%m-%d %H:%M')
            if 'Note' in disp_db.columns: disp_db = disp_db.drop(columns=['Note'])
            disp_db = disp_db.reset_index(drop=True)
            disp_db.index = disp_db.index + 1
            render_plain_table(disp_db, num_cols={'Thời lượng (Phút)'})
    with st.expander("4. Quản lý hệ thống", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.subheader("Tải về")
            if os.path.exists(DB_FILE):
                with open(DB_FILE, "rb") as f: st.download_button("Tải file Dữ liệu", f, "database.csv", "text/csv")
            if os.path.exists(MAPPING_FILE):
                with open(MAPPING_FILE, "rb") as f: st.download_button("Tải file Quy tắc", f, "mapping.csv", "text/csv")
        with c2:
            st.subheader("Khôi phục")
            res_db = st.file_uploader("Tải lên file Dữ liệu", type=["csv"], key="r_db")
            res_map = st.file_uploader("Tải lên file Quy tắc", type=["csv"], key="r_map")
            if st.button("Xác nhận Khôi phục", type="primary"):
                if res_db: save_db(pd.read_csv(res_db))
                if res_map: save_mapping(pd.read_csv(res_map))
                st.success("Khôi phục hệ thống thành công!")
                time.sleep(1)
                st.rerun()
        with c3:
            st.subheader("Làm mới")
            confirm_delete = st.checkbox("Tôi xác nhận muốn xoá toàn bộ dữ liệu")
            if st.button("Xoá toàn bộ dữ liệu", disabled=not confirm_delete):
                if os.path.exists(DB_FILE): os.remove(DB_FILE)
                if os.path.exists(MAPPING_FILE): os.remove(MAPPING_FILE)
                st.cache_data.clear()
                st.success("Đã xoá toàn bộ dữ liệu cục bộ!")
                time.sleep(1)
                st.rerun()