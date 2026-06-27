import streamlit as st
import pandas as pd
import os
import time
import plotly.express as px
import plotly.graph_objects as go
import altair as alt
from html import escape as html_escape
from datetime import date

# --- CẤU HÌNH ---
DB_FILE = "database.csv"
MAPPING_FILE = "mapping.csv"

# Bảng màu phong cách Apple / Latte sáng
MAC_COLORS = [
    "#007aff", # Blue (Primary)
    "#34c759", # Green
    "#ff9500", # Orange
    "#ff2d55", # Red
    "#5856d6", # Pink
    "#af52de", # Purple
    "#5ac8fa", # Indigo
    "#ffcc00", # Yellow
    "#32ade6", # Cyan
    "#a2845e"  # Brown
]
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
    db['Tuần'] = db['Thời gian bắt đầu'].dt.strftime('%Y-W%U') # Bắt đầu Chủ Nhật
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

# --- CÁC HÀM RENDER UI GLASSMORPHISM ---
def render_glass_metric(title, value, delta_prev=None, delta_prev_label="", delta_avg=None, delta_avg_label=""):
    html = f"""
    <div class="glass-card" style="height: 100%;">
        <p style="margin: 0; font-size: 13px; color: #86868b; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">{title}</p>
        <h3 style="margin: 8px 0; font-size: 32px; color: #1d1d1f; font-weight: 600; letter-spacing: -0.5px;">{value}</h3>
    """
    if delta_prev is not None:
        c1 = "#34c759" if delta_prev > 0 else "#ff3b30" if delta_prev < 0 else "#86868b"
        s1 = "+" if delta_prev > 0 else ""
        html += f"<p style='margin: 0; font-size: 14px; font-weight: 500; color: {c1};'> {s1}{delta_prev:.1f} {delta_prev_label}</p>"
    if delta_avg is not None:
        c2 = "#34c759" if delta_avg > 0 else "#ff3b30" if delta_avg < 0 else "#86868b"
        s2 = "+" if delta_avg > 0 else ""
        html += f"<p style='margin: 4px 0 0 0; font-size: 14px; font-weight: 500; color: {c2};'> {s2}{delta_avg:.1f} {delta_avg_label}</p>"
    
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def render_top_3(df, col_name, title):
    if df.empty: 
        html_list = "<p style='color:#86868b; font-size: 14px;'>Không có dữ liệu</p>"
    else:
        top3 = df.groupby(col_name)['Thời lượng (Phút)'].sum().sort_values(ascending=False).head(3)
        html_list = "<ul style='margin:0; padding-left: 20px; color: #1d1d1f; font-size: 15px; line-height: 1.6;'>"
        for k, v in top3.items():
            html_list += f"<li><span style='font-weight:600;'>{html_escape(str(k))}</span>: {v/60:.1f}h</li>"
        html_list += "</ul>"
    
    html = f"""
    <div class="glass-card" style="height: 100%;">
        <p style="margin: 0 0 12px 0; font-size: 13px; color: #86868b; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">{title}</p>
        {html_list}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_hourly_chart(scope_df, color_col, x_title="Khung giờ"):
    hr_group = scope_df.groupby(['Khung giờ', color_col])['Thời lượng (Phút)'].sum().reset_index()
    hr_group['Số giờ'] = hr_group['Thời lượng (Phút)'] / 60
    fig = px.bar(hr_group, x='Khung giờ', y='Số giờ', color=color_col, color_discrete_map=COLOR_MAP)

    tot = scope_df.groupby('Khung giờ')['Thời lượng (Phút)'].sum().reset_index()
    tot['Số giờ'] = tot['Thời lượng (Phút)'] / 60
    fig.add_trace(go.Scatter(
        x=tot['Khung giờ'], y=tot['Số giờ'], mode='lines+text',
        text=tot['Số giờ'].round(1).astype(str), textposition='top center', textfont=dict(color="#1d1d1f", size=13),
        name='Tổng cộng', line=dict(color=MAC_COLORS[0], width=2.5)
    ))
    y_max = tot['Số giờ'].max() if not tot.empty else 1
    fig.update_layout(width=CHART_WIDTH, xaxis_title=x_title, yaxis_title="Số giờ", yaxis=dict(range=[0, y_max * 1.2]))
    fig = format_plotly_fig(fig)
    st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)


def render_calendar_streak(scope_df, full_df):
    min_date = scope_df['Ngày'].min()
    max_date = full_df['Ngày'].max()
    all_dates = pd.date_range(start=min_date, end=max_date)
    cal_data = pd.DataFrame({'Ngày': all_dates})

    cal_data['Tuần_Bắt_Đầu'] = cal_data['Ngày'] - pd.to_timedelta((cal_data['Ngày'].dt.dayofweek + 1) % 7, unit='D')
    days_map = {"Monday": "Thứ 2", "Tuesday": "Thứ 3", "Wednesday": "Thứ 4", "Thursday": "Thứ 5", "Friday": "Thứ 6", "Saturday": "Thứ 7", "Sunday": "Chủ Nhật"}
    cal_data['Thứ'] = cal_data['Ngày'].dt.day_name().map(days_map)
    cal_data['Ngày_str'] = cal_data['Ngày'].dt.date

    grp = scope_df.groupby('Ngày')['Thời lượng (Phút)'].sum().reset_index()
    cal_data = cal_data.merge(grp, left_on='Ngày_str', right_on='Ngày', how='left').fillna({'Thời lượng (Phút)': 0})
    cal_data['Số giờ'] = (cal_data['Thời lượng (Phút)'] / 60).round(1)
    cal_data['day'] = cal_data['Ngày_x'].dt.day if 'Ngày_x' in cal_data else pd.to_datetime(cal_data['Ngày_str']).dt.day

    vmax_cal = float(cal_data['Số giờ'].max()) or 1.0
    enc_x = alt.X('yearmonthdate(Tuần_Bắt_Đầu):O', title='',
                  axis=alt.Axis(labelAngle=0, orient='top', tickSize=0, domain=False,
                                labelExpr="month(datum.value) != month(datum.value - 7*24*60*60*1000) ? 'Th' + (month(datum.value)+1) : ''"))
    enc_y = alt.Y('Thứ:O', sort=DAYS_ORDER, title='', scale=alt.Scale(domain=DAYS_ORDER), axis=alt.Axis(tickSize=0, domain=False))
    base = alt.Chart(cal_data).encode(x=enc_x, y=enc_y)
    rect = base.mark_rect(cornerRadius=3).encode(
        color=alt.Color('Số giờ:Q', scale=alt.Scale(domain=[0, vmax_cal], range=['#e5e5ea', '#34c759']), legend=None),
        tooltip=[alt.Tooltip('Ngày_str:T', format='%d-%m-%Y', title='Ngày'), alt.Tooltip('Số giờ:Q', format='.1f', title='Giờ')]
    )
    text = base.mark_text(baseline='middle', fontSize=10).encode(
        text='day:Q',
        color=alt.condition(f"datum['Số giờ'] > {vmax_cal * 0.55}", alt.value('#ffffff'), alt.value('#a7a7ac'))
    )
    chart = (rect + text).properties(width=alt.Step(34), height=alt.Step(34)).configure_view(strokeWidth=0)
    st.altair_chart(chart, width='content')

    unique_dates = pd.to_datetime(scope_df['Ngày'].dropna().unique())
    unique_dates = unique_dates.sort_values()
    today = pd.Timestamp(date.today())
    if len(unique_dates) > 0:
        total_days = len(unique_dates)
        diffs = unique_dates.to_series().diff().dt.days
        streak_id = (diffs > 1).cumsum()
        streak_counts = streak_id.value_counts()
        longest_streak = streak_counts.max()
        # Chuỗi hiện tại tính theo hôm nay: chỉ còn hiệu lực nếu lần gần nhất là hôm nay hoặc hôm qua
        current_streak = streak_counts[streak_id.iloc[-1]] if (today - unique_dates.max()).days <= 1 else 0
    else:
        total_days = longest_streak = current_streak = 0

    st.markdown(f"""
    <div class="glass-card" style='display: flex; width: 100%; max-width: 900px; margin: 0 auto; justify-content: center; align-items: center; padding: 25px;'>
        <div style='flex: 1; text-align: center; border-right: 1px solid rgba(0,0,0,0.1);'>
            <h3 style='margin:0; font-size: 32px;'>{total_days} ngày</h3>
            <p style='margin:5px 0 0 0; color:#86868b; font-size: 15px; font-weight:500;'>Tổng cộng</p>
        </div>
        <div style='flex: 1; text-align: center; border-right: 1px solid rgba(0,0,0,0.1);'>
            <h3 style='margin:0; font-size: 32px;'>{longest_streak} ngày</h3>
            <p style='margin:5px 0 0 0; color:#86868b; font-size: 15px; font-weight:500;'>Chuỗi dài nhất</p>
        </div>
        <div style='flex: 1; text-align: center;'>
            <h3 style='margin:0; font-size: 32px;'>{current_streak} ngày</h3>
            <p style='margin:5px 0 0 0; color:#86868b; font-size: 15px; font-weight:500;'>Chuỗi hiện tại</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


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
st.set_page_config(page_title="Forest Dashboard", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
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

    /* ===== Tinh chỉnh riêng cho điện thoại (không ảnh hưởng desktop) ===== */
    @media (max-width: 640px) {
        h1 { font-size: 1.9rem !important; line-height: 1.15 !important; }
        h2, [data-testid="stHeading"] h2 { font-size: 1.35rem !important; }
        h3 { font-size: 1.1rem !important; }
        .block-container { padding-left: 0.8rem !important; padding-right: 0.8rem !important; padding-top: 1rem !important; }

        /* Thẻ gọn lại, bớt khoảng trống thừa (height:auto để không bị kéo giãn khi xếp dọc) */
        .glass-card { padding: 14px !important; height: auto !important; }
        .glass-card h3 { font-size: 26px !important; margin: 4px 0 !important; }
        /* Khi cột xếp dọc trên mobile, bỏ giãn đều chiều cao */
        [data-testid="stHorizontalBlock"] { align-items: flex-start !important; }

        /* Biểu đồ: bớt đệm để rộng hơn */
        [data-testid="stPlotlyChart"], [data-testid="stVegaLiteChart"] { padding: 6px !important; }
        /* Lịch (Vega) rộng -> cho cuộn ngang trong thẻ thay vì tràn */
        [data-testid="stVegaLiteChart"] { overflow-x: auto !important; justify-content: flex-start !important; }

        /* Bảng số liệu: chữ nhỏ & đệm sát để chứa nhiều cột hơn */
        .dtbl th, .dtbl td { padding: 3px 6px !important; font-size: 11px !important; }
        .dtbl-wrap { max-height: 70vh !important; }

        /* Thẻ streak: xếp dọc cho dễ đọc */
        .glass-card[style*="display: flex"] { flex-direction: column !important; gap: 14px !important; }
        .glass-card[style*="display: flex"] > div { border-right: none !important; }
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Bảng theo dõi thời gian")

tab_thong_ke, tab_thang, tab_tuan, tab_nhom, tab_chuan_bi = st.tabs([
    "Thống kê chung", "Báo cáo tháng", "Báo cáo tuần", "Báo cáo theo nhóm", "Chuẩn bị dữ liệu"
])

df = prep_analysis_data()
DAYS_ORDER = ["Chủ Nhật", "Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"]

# Bản đồ màu cố định: mỗi Danh mục/Dự án luôn giữ một màu xuyên suốt mọi biểu đồ/tab
if not df.empty:
    _all_names = sorted(set(df['Danh mục'].dropna().unique()) | set(df['Dự án'].dropna().unique()))
    COLOR_MAP = {name: MAC_COLORS[i % len(MAC_COLORS)] for i, name in enumerate(_all_names)}
else:
    COLOR_MAP = {}

# ==========================================
# TAB THỐNG KÊ CHUNG
# ==========================================
with tab_thong_ke:
    if not df.empty:
        st.header("1. Tổng quan")
        total_hrs = df['Thời lượng (Phút)'].sum() / 60
        total_trees = len(df)
        num_days = df['Ngày'].nunique() or 1
        
        c1, c2, c3, c4 = st.columns(4)
        with c1: render_glass_metric("Tổng thời gian", f"{total_hrs:.1f}h")
        with c2: render_glass_metric("Thời gian TB/ngày", f"{total_hrs/num_days:.1f}h")
        with c3: render_glass_metric("Số cây đã trồng", f"{total_trees}")
        with c4: render_glass_metric("Số cây TB/ngày", f"{total_trees/num_days:.1f}")
        
        st.write("")
        c_top1, c_top2 = st.columns(2)
        with c_top1: render_top_3(df, 'Danh mục', 'Top 3 Danh mục')
        with c_top2: render_top_3(df, 'Dự án', 'Top 3 Dự án')

        st.header("2. Xu hướng theo thời gian")
        r_col1, r_col2 = st.columns(2)
        with r_col1:
            time_col_2 = st.radio("Cơ sở dữ liệu biểu đồ:", ["Ngày", "Tuần", "Tháng"], horizontal=True, key="time_tab2")
        with r_col2:
            color_col_2 = st.radio("Phân loại dữ liệu biểu đồ theo:", ["Danh mục", "Dự án"], horizontal=True, key="rad_tab2")
        
        trend_group = df.groupby([time_col_2, color_col_2])['Thời lượng (Phút)'].sum().reset_index()
        trend_group['Số giờ'] = trend_group['Thời lượng (Phút)'] / 60
        if time_col_2 == "Ngày":
            trend_group['Ngày'] = pd.to_datetime(trend_group['Ngày'])
        fig1 = px.bar(trend_group, x=time_col_2, y='Số giờ', color=color_col_2, color_discrete_map=COLOR_MAP)

        if time_col_2 in ["Tuần", "Tháng"]:
            fig1 = add_total_labels(fig1, trend_group, time_col_2, 'Số giờ')
        else:
            fig1 = add_week_dividers(fig1, trend_group['Ngày'])

        fig1.update_layout(width=CHART_WIDTH, xaxis_title=time_col_2, yaxis_title="Số giờ")
        fig1 = format_plotly_fig(fig1)
        st.plotly_chart(fig1, width='stretch', config=PLOTLY_CONFIG)

        st.header("3. Xu hướng làm việc theo khung giờ")
        render_hourly_chart(df, color_col_2, x_title="Khung giờ (0h - 23h)")

        st.header("4. Biểu đồ lịch tổng quan")
        render_calendar_streak(df, df)

        st.header("5. Bảng số liệu")
        view_opt = st.radio("Xem theo:", ["Tuần", "Tháng"], horizontal=True)
        time_col = 'Tuần' if view_opt == "Tuần" else 'Tháng'
        render_data_table(df, time_col)
    else:
        st.info("Chưa có dữ liệu hệ thống. Vui lòng sang tab 'Chuẩn bị dữ liệu' để tải file lên.")

# ==========================================
# TAB BÁO CÁO THÁNG
# ==========================================
with tab_thang:
    if not df.empty:
        months = sorted(df['Tháng'].unique())
        selected_month = st.selectbox("Chọn Tháng", months, index=len(months)-1, key="sel_thang")
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
            st.header("1. Tổng quan")
            c1, c2, c3, c4 = st.columns(4)
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

            with c1: render_glass_metric("Tổng thời gian", f"{curr_hrs:.1f}h", delta1_hr, "h (vs Tháng trước)", delta2_hr, "h (vs Trung bình)")
            with c2: render_glass_metric("Thời gian TB/ngày", f"{curr_hrs_day:.1f}h", delta1_hrd, "h (vs Tháng trước)", delta2_hrd, "h (vs Trung bình)")
            with c3: render_glass_metric("Số cây đã trồng", f"{curr_trees}", delta1_tr, "cây (vs Tháng trước)", delta2_tr, "cây (vs Trung bình)")
            with c4: render_glass_metric("Số cây TB/ngày", f"{curr_trees_day:.1f}", delta1_trd, "cây (vs Tháng trước)", delta2_trd, "cây (vs Trung bình)")
            
            st.write("")
            c_top1, c_top2 = st.columns(2)
            with c_top1: render_top_3(df_m, 'Danh mục', 'Top 3 Danh mục Tháng')
            with c_top2: render_top_3(df_m, 'Dự án', 'Top 3 Dự án Tháng')
            
            st.header("2. Xu hướng theo thời gian")
            color_col_3 = st.radio("Phân loại dữ liệu biểu đồ theo:", ["Danh mục", "Dự án"], horizontal=True, key="rad_tab3")
            t_m = df_m.groupby(['Ngày', color_col_3])['Thời lượng (Phút)'].sum().reset_index()
            t_m['Số giờ'] = t_m['Thời lượng (Phút)'] / 60
            t_m['Ngày'] = pd.to_datetime(t_m['Ngày'])
            fig_m = px.bar(t_m, x='Ngày', y='Số giờ', color=color_col_3, color_discrete_map=COLOR_MAP)
            fig_m.update_layout(width=CHART_WIDTH, xaxis_title="Ngày trong tháng", yaxis_title="Số giờ")
            fig_m = add_total_labels(fig_m, t_m, 'Ngày', 'Số giờ')
            fig_m = add_week_dividers(fig_m, t_m['Ngày'])
            fig_m = format_plotly_fig(fig_m)
            st.plotly_chart(fig_m, width='stretch', config=PLOTLY_CONFIG)
            
            st.header("3. Phân bổ thời gian")
            pc_m = df_m.groupby(color_col_3)['Thời lượng (Phút)'].sum().reset_index()
            pc_m['Số giờ'] = pc_m['Thời lượng (Phút)'] / 60
            fig_p_m = px.pie(pc_m, values='Số giờ', names=color_col_3, color=color_col_3, color_discrete_map=COLOR_MAP)
            fig_p_m.update_layout(width=CHART_WIDTH)
            fig_p_m = format_plotly_fig(fig_p_m, is_pie=True)
            st.plotly_chart(fig_p_m, width='stretch', config=PLOTLY_CONFIG)
            
            st.header("4. Bảng chi tiết (Giờ)")
            render_detail_table(df_m)
            
            st.header("5. Xu hướng làm việc theo khung giờ")
            render_hourly_chart(df_m, color_col_3)

# ==========================================
# TAB BÁO CÁO TUẦN
# ==========================================
with tab_tuan:
    if not df.empty:
        weeks = sorted(df['Tuần'].unique())
        selected_week = st.selectbox("Chọn Tuần", weeks, index=len(weeks)-1, key="sel_tuan")
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
        prev_week_key = (week_anchor - pd.Timedelta(days=7)).strftime('%Y-W%U') if pd.notna(week_anchor) else None
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
            st.header("1. Tổng quan")
            c1, c2, c3, c4 = st.columns(4)
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

            with c1: render_glass_metric("Tổng thời gian", f"{curr_hrs_w:.1f}h", d1_hr_w, "h (vs Tuần trước)", d2_hr_w, "h (vs Trung bình)")
            with c2: render_glass_metric("Thời gian TB/ngày", f"{curr_hrs_day_w:.1f}h", d1_hrd_w, "h (vs Tuần trước)", d2_hrd_w, "h (vs Trung bình)")
            with c3: render_glass_metric("Số cây đã trồng", f"{curr_trees_w}", d1_tr_w, "cây (vs Tuần trước)", d2_tr_w, "cây (vs Trung bình)")
            with c4: render_glass_metric("Số cây TB/ngày", f"{curr_trees_day_w:.1f}", d1_trd_w, "cây (vs Tuần trước)", d2_trd_w, "cây (vs Trung bình)")
            
            st.write("")
            c_top1, c_top2 = st.columns(2)
            with c_top1: render_top_3(df_w, 'Danh mục', 'Top 3 Danh mục Tuần')
            with c_top2: render_top_3(df_w, 'Dự án', 'Top 3 Dự án Tuần')
            
            st.header("2. Xu hướng theo thời gian")
            color_col_4 = st.radio("Phân loại dữ liệu biểu đồ theo:", ["Danh mục", "Dự án"], horizontal=True, key="rad_tab4")
            t_w = df_w.groupby(['Thứ', color_col_4])['Thời lượng (Phút)'].sum().reset_index()
            t_w['Số giờ'] = t_w['Thời lượng (Phút)'] / 60
            fig_w = px.bar(t_w, x='Thứ', y='Số giờ', color=color_col_4, category_orders={"Thứ": DAYS_ORDER}, color_discrete_map=COLOR_MAP)
            fig_w.update_layout(width=CHART_WIDTH, xaxis_title="Thứ trong tuần", yaxis_title="Số giờ")
            fig_w = add_total_labels(fig_w, t_w, 'Thứ', 'Số giờ')
            fig_w = format_plotly_fig(fig_w)
            st.plotly_chart(fig_w, width='stretch', config=PLOTLY_CONFIG)
            
            st.header("3. Phân bổ thời gian")
            pc_w = df_w.groupby(color_col_4)['Thời lượng (Phút)'].sum().reset_index()
            pc_w['Số giờ'] = pc_w['Thời lượng (Phút)'] / 60
            fig_p_w = px.pie(pc_w, values='Số giờ', names=color_col_4, color=color_col_4, color_discrete_map=COLOR_MAP)
            fig_p_w.update_layout(width=CHART_WIDTH)
            fig_p_w = format_plotly_fig(fig_p_w, is_pie=True)
            st.plotly_chart(fig_p_w, width='stretch', config=PLOTLY_CONFIG)
            
            st.header("4. Bảng chi tiết (Giờ)")
            render_detail_table(df_w)
            
            st.header("5. Xu hướng làm việc theo khung giờ")
            render_hourly_chart(df_w, color_col_4)

# ==========================================
# TAB BÁO CÁO THEO NHÓM
# ==========================================
with tab_nhom:
    if not df.empty:
        all_groups = sorted(set(list(df['Danh mục'].unique()) + list(df['Dự án'].unique())))
        sel_grp = st.selectbox("Chọn Danh mục hoặc Dự án:", all_groups)
        
        df_g = df[(df['Danh mục'] == sel_grp) | (df['Dự án'] == sel_grp)]
        
        st.header("1. Tổng quan")
        c1, c2, c3, c4 = st.columns(4)
        curr_hrs_g = df_g['Thời lượng (Phút)'].sum() / 60
        curr_trees_g = len(df_g)
        num_days_g = df_g['Ngày'].nunique() or 1
        
        with c1: render_glass_metric("Tổng thời gian", f"{curr_hrs_g:.1f}h")
        with c2: render_glass_metric("Thời gian TB/ngày", f"{curr_hrs_g/num_days_g:.1f}h")
        with c3: render_glass_metric("Số cây đã trồng", f"{curr_trees_g}")
        with c4: render_glass_metric("Số cây TB/ngày", f"{curr_trees_g/num_days_g:.1f}")
        
        st.header("2. Xu hướng theo thời gian")
        time_col_5 = st.radio("Cơ sở dữ liệu biểu đồ:", ["Ngày", "Tuần", "Tháng"], horizontal=True, key="time_tab5")
        t_g = df_g.groupby(time_col_5)['Thời lượng (Phút)'].sum().reset_index()
        t_g['Số giờ'] = t_g['Thời lượng (Phút)'] / 60
        
        if time_col_5 == "Ngày":
            t_g['Ngày'] = pd.to_datetime(t_g['Ngày'])
            fig_g = px.line(t_g, x=time_col_5, y='Số giờ', color_discrete_sequence=[MAC_COLORS[0]])
            fig_g.update_traces(fill='tozeroy', fillcolor="rgba(0,122,255,0.1)")
            fig_g = add_week_dividers(fig_g, t_g['Ngày'])
        else:
            fig_g = px.bar(t_g, x=time_col_5, y='Số giờ', color_discrete_sequence=[MAC_COLORS[0]])
            fig_g = add_total_labels(fig_g, t_g, time_col_5, 'Số giờ')
            
        fig_g.update_layout(width=CHART_WIDTH, xaxis_title=time_col_5, yaxis_title="Số giờ")
        fig_g = format_plotly_fig(fig_g)
        st.plotly_chart(fig_g, width='stretch', config=PLOTLY_CONFIG)
        
        st.header("3. Biểu đồ lịch")
        render_calendar_streak(df_g, df)

# ==========================================
# TAB CHUẨN BỊ DỮ LIỆU
# ==========================================
with tab_chuan_bi:
    st.header("1. Tải lên từ Forest")
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

    st.divider()
    st.header("2. Phân loại")
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

    st.divider()
    st.header("3. Dữ liệu làm việc hiện tại")
    if not db_current.empty:
        disp_db = db_current.copy()
        disp_db['Thời gian bắt đầu'] = pd.to_datetime(disp_db['Thời gian bắt đầu']).dt.strftime('%Y-%m-%d %H:%M')
        disp_db['Thời gian kết thúc'] = pd.to_datetime(disp_db['Thời gian kết thúc']).dt.strftime('%Y-%m-%d %H:%M')
        if 'Note' in disp_db.columns: disp_db = disp_db.drop(columns=['Note'])
        disp_db = disp_db.reset_index(drop=True)
        disp_db.index = disp_db.index + 1
        render_plain_table(disp_db, num_cols={'Thời lượng (Phút)'})
    
    st.divider()
    st.header("4. Quản lý hệ thống")
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
