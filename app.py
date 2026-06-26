import streamlit as st
import pandas as pd
import os
import time
import plotly.express as px
import plotly.graph_objects as go
import altair as alt
from datetime import datetime, timedelta
import calendar

# ==========================================
# CẤU HÌNH HỆ THỐNG & BIẾN TOÀN CỤC
# ==========================================
DB_FILE = "database.csv"
MAPPING_FILE = "mapping.csv"

# Bảng màu phong cách Apple (Cupertino)
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
CHART_WIDTH = 1200 
PLOTLY_CONFIG = {'scrollZoom': False, 'displayModeBar': False}
DAYS_ORDER = ["Chủ Nhật", "Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"]

# ==========================================
# CÁC HÀM XỬ LÝ DỮ LIỆU CỐT LÕI
# ==========================================
def load_db():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        rename_dict = {'Start Time': 'Thời gian bắt đầu', 'End Time': 'Thời gian kết thúc', 'Project': 'Dự án', 'Tag': 'Dự án', 'Duration (Min)': 'Thời lượng (Phút)'}
        df.rename(columns={k: v for k, v in rename_dict.items() if k in df.columns}, inplace=True)
        return df
    return pd.DataFrame(columns=["Thời gian bắt đầu", "Thời gian kết thúc", "Dự án", "Thời lượng (Phút)"])

def save_db(df):
    df.to_csv(DB_FILE, index=False)

def load_mapping():
    if os.path.exists(MAPPING_FILE):
        df = pd.read_csv(MAPPING_FILE)
        rename_dict = {'Project': 'Dự án', 'Tag': 'Dự án', 'Category': 'Danh mục'}
        df.rename(columns={k: v for k, v in rename_dict.items() if k in df.columns}, inplace=True)
        return df
    return pd.DataFrame(columns=["Dự án", "Danh mục"])

def save_mapping(df):
    df.to_csv(MAPPING_FILE, index=False)

def prep_analysis_data():
    db = load_db()
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
    db['Tuần'] = db['Thời gian bắt đầu'].dt.strftime('%Y-W%U') # %U: Tuần bắt đầu từ Chủ Nhật
    db['Khung giờ'] = db['Thời gian bắt đầu'].dt.hour
    
    tieng_viet_days = {"Monday": "Thứ 2", "Tuesday": "Thứ 3", "Wednesday": "Thứ 4", "Thursday": "Thứ 5", "Friday": "Thứ 6", "Saturday": "Thứ 7", "Sunday": "Chủ Nhật"}
    db['Thứ'] = db['Thời gian bắt đầu'].dt.day_name().map(tieng_viet_days)
    return db

def get_pivot_with_totals(df, time_col):
    cat_tot = df.groupby(['Danh mục', time_col])['Thời lượng (Phút)'].sum().reset_index()
    cat_tot['Dự án'] = ' TỔNG NHÓM'
    proj_tot = df.groupby(['Danh mục', 'Dự án', time_col])['Thời lượng (Phút)'].sum().reset_index()
    comb = pd.concat([cat_tot, proj_tot])
    pivot = comb.groupby(['Danh mục', 'Dự án', time_col])['Thời lượng (Phút)'].sum().unstack(fill_value=0)
    return (pivot / 60).round(1)

def get_table_with_totals(df):
    cat_tot = df.groupby('Danh mục')['Thời lượng (Phút)'].sum().reset_index()
    cat_tot['Dự án'] = ' TỔNG NHÓM'
    proj_tot = df.groupby(['Danh mục', 'Dự án'])['Thời lượng (Phút)'].sum().reset_index()
    comb = pd.concat([cat_tot, proj_tot])
    comb['Số giờ'] = (comb['Thời lượng (Phút)'] / 60).round(1)
    comb = comb.sort_values(by=['Danh mục', 'Dự án'])
    return comb.set_index(['Danh mục', 'Dự án'])[['Số giờ']]

# ==========================================
# CÁC HÀM VẼ BIỂU ĐỒ & UI COMPONENT
# ==========================================
def format_plotly_fig(fig, is_pie=False):
    """Định dạng font chữ Apple và loại bỏ nền"""
    fig.update_layout(
        dragmode=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="-apple-system, BlinkMacSystemFont, sans-serif", color="#1d1d1f"),
        margin=dict(t=30, b=30, l=10, r=10)
    )
    if is_pie:
        fig.update_traces(
            hovertemplate='<b>%{label}</b><br>%{value:.1f} giờ<extra></extra>',
            marker=dict(line=dict(color='#ffffff', width=0.5)) # Viền siêu mảnh 0.5px
        )
    else:
        fig.update_traces(
            hovertemplate='<b>%{data.name}</b><br>%{y:.1f} giờ<extra></extra>',
            marker=dict(line=dict(color='#ffffff', width=0.5)) # Viền siêu mảnh 0.5px
        )
    return fig

def add_total_labels(fig, df, x_col, y_col):
    """Thêm text data label lên đỉnh cột"""
    totals = df.groupby(x_col)[y_col].sum().reset_index()
    fig.add_trace(go.Scatter(
        x=totals[x_col], y=totals[y_col], mode='text', text=totals[y_col].round(1).astype(str),
        textposition='top center', showlegend=False, hoverinfo='skip', textfont=dict(color="#1d1d1f", size=13)
    ))
    fig.update_layout(yaxis=dict(range=[0, totals[y_col].max() * 1.15]))
    return fig

def add_week_dividers(fig, df, time_col):
    """Thêm đường kẻ sọc ngăn cách các tuần (Chủ nhật)"""
    if time_col == "Ngày":
        unique_days = sorted(df['Ngày'].unique())
        for d in unique_days:
            if d.weekday() == 6: # 6 = Chủ nhật
                fig.add_vline(x=d, line_width=1, line_color="rgba(0,0,0,0.2)", line_dash="solid")
    return fig

def add_average_line(fig, avg_value, label):
    """Thêm đường trung bình cắt ngang biểu đồ"""
    fig.add_hline(
        y=avg_value, line_dash="dash", line_color="#ff3b30", line_width=1.5,
        annotation_text=f" TB: {avg_value:.1f}h ", annotation_position="top left",
        annotation_font_color="#ff3b30"
    )
    return fig

def render_glass_metric(title, value, delta_prev=None, delta_prev_label="", delta_avg=None, delta_avg_label=""):
    """Thẻ hiển thị chỉ số mang phong cách Glassmorphism"""
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
    """Thẻ hiển thị danh sách Top 3"""
    if df.empty: 
        html_list = "<p style='color:#86868b; font-size: 14px;'>Không có dữ liệu</p>"
    else:
        top3 = df.groupby(col_name)['Thời lượng (Phút)'].sum().sort_values(ascending=False).head(3)
        html_list = "<ul style='margin:0; padding-left: 20px; color: #1d1d1f; font-size: 15px; line-height: 1.6;'>"
        for k, v in top3.items():
            html_list += f"<li><span style='font-weight:600;'>{k}</span>: {v/60:.1f}h</li>"
        html_list += "</ul>"
    
    html = f"""
    <div class="glass-card" style="height: 100%;">
        <p style="margin: 0 0 12px 0; font-size: 13px; color: #86868b; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">{title}</p>
        {html_list}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ==========================================
# CẤU HÌNH GIAO DIỆN & CSS (MAC CUỘN)
# ==========================================
st.set_page_config(page_title="Forest Dashboard", layout="wide")

st.markdown(
    """
    <style>
    /* 1. Global Font */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    }
    .stApp { background-color: #f5f5f7; }
    .block-container { max-width: 1200px !important; margin: 0 auto !important; padding-top: 2rem !important; }
    
    /* 2. Glassmorphism Blocks */
    .glass-card {
        background: rgba(255, 255, 255, 0.65);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.4);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.03);
    }
    
    /* 3. Streamlit Default Overrides */
    h1, h2, h3 { color: #1d1d1f !important; font-weight: 600 !important; letter-spacing: -0.5px !important; }
    hr { border-color: rgba(0,0,0,0.08) !important; }
    
    /* 4. Tùy chỉnh Nút bấm Primary */
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
        transform: scale(0.98); opacity: 0.9;
    }
    
    /* 5. Nút bấm dạng Link (Dùng cho Pickers) */
    .link-button-container div[data-testid="stButton"] button {
        background: transparent !important;
        border: none !important;
        color: #1d1d1f !important;
        font-weight: 400 !important;
        box-shadow: none !important;
        padding: 0 !important;
        min-height: 0 !important;
    }
    .link-button-container div[data-testid="stButton"] button:hover {
        color: #007aff !important;
        text-decoration: none !important;
        background-color: rgba(0,122,255,0.1) !important;
        border-radius: 6px !important;
    }
    .link-button-container div[data-testid="stButton"] button:disabled {
        color: #d1d1d6 !important;
    }

    /* 6. Form Inputs */
    .stSelectbox > div > div, .stTextInput > div > div > input {
        border-radius: 8px !important;
        border: 1px solid #d1d1d6 !important;
        background-color: rgba(255,255,255,0.8) !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
    }
    
    /* 7. Căn giữa Altair */
    [data-testid="stVegaLiteChart"] { display: flex !important; justify-content: center !important; width: 100% !important; margin: 0 auto !important; }
    [data-testid="stMetric"] { display: none; }
    
    /* Lịch Calendar CSS */
    .cal-day-header { text-align: center; font-size: 12px; color: #86868b; font-weight: 600; margin-bottom: 5px; }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Bảng theo dõi thời gian")

# Sắp xếp Tabs theo yêu cầu
tab_thong_ke, tab_thang, tab_tuan, tab_nhom, tab_chuan_bi = st.tabs([
    "Thống kê chung", "Báo cáo tháng", "Báo cáo tuần", "Báo cáo theo nhóm", "Chuẩn bị dữ liệu"
])

df = prep_analysis_data()

# ==========================================
# TAB 1: THỐNG KÊ CHUNG
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
        with c3: render_glass_metric("Tổng số cây", f"{total_trees}")
        with c4: render_glass_metric("Số cây TB/ngày", f"{total_trees/num_days:.1f}")
        
        st.write("")
        c_top1, c_top2 = st.columns(2)
        with c_top1: render_top_3(df, 'Danh mục', 'Top 3 Danh mục')
        with c_top2: render_top_3(df, 'Dự án', 'Top 3 Dự án')

        st.header("2. Xu hướng theo thời gian")
        r_col1, r_col2 = st.columns(2)
        with r_col1:
            time_col_2 = st.radio("Cơ sở dữ liệu biểu đồ:", ["Ngày", "Tuần", "Tháng"], horizontal=True, key="tk_time")
        with r_col2:
            color_col_2 = st.radio("Phân loại biểu đồ theo:", ["Danh mục", "Dự án"], horizontal=True, key="tk_group")
        
        trend_group = df.groupby([time_col_2, color_col_2])['Thời lượng (Phút)'].sum().reset_index()
        trend_group['Số giờ'] = trend_group['Thời lượng (Phút)'] / 60
        fig1 = px.bar(trend_group, x=time_col_2, y='Số giờ', color=color_col_2, color_discrete_sequence=MAC_COLORS)
        
        if time_col_2 in ["Tuần", "Tháng"]:
            fig1 = add_total_labels(fig1, trend_group, time_col_2, 'Số giờ')
        if time_col_2 == "Ngày":
            fig1 = add_week_dividers(fig1, trend_group, time_col_2)
            
        fig1.update_layout(xaxis_title=time_col_2, yaxis_title="Số giờ")
        st.plotly_chart(format_plotly_fig(fig1), use_container_width=True, config=PLOTLY_CONFIG)

        st.header("3. Xu hướng làm việc theo khung giờ")
        hr_group = df.groupby(['Khung giờ', color_col_2])['Thời lượng (Phút)'].sum().reset_index()
        hr_group['Số giờ'] = hr_group['Thời lượng (Phút)'] / 60
        fig2 = px.bar(hr_group, x='Khung giờ', y='Số giờ', color=color_col_2, color_discrete_sequence=MAC_COLORS)
        
        # Line Tổng cộng (Màu xanh Apple, kèm Text)
        tot_hr = df.groupby('Khung giờ')['Thời lượng (Phút)'].sum().reset_index()
        tot_hr['Số giờ'] = tot_hr['Thời lượng (Phút)'] / 60
        fig2.add_trace(go.Scatter(
            x=tot_hr['Khung giờ'], y=tot_hr['Số giờ'], mode='lines+text', 
            text=tot_hr['Số giờ'].round(1).astype(str), textposition='top center', textfont=dict(color="#007aff", size=13),
            name='Tổng cộng', line=dict(color="#007aff", width=2.5)
        ))
        fig2.update_layout(xaxis_title="Khung giờ (0h - 23h)", yaxis_title="Số giờ", yaxis=dict(range=[0, tot_hr['Số giờ'].max() * 1.2]))
        st.plotly_chart(format_plotly_fig(fig2), use_container_width=True, config=PLOTLY_CONFIG)

        st.header("4. Biểu đồ lịch tổng quan")
        min_date = df['Ngày'].min()
        max_date = df['Ngày'].max() 
        all_dates = pd.date_range(start=min_date, end=max_date)
        cal_data = pd.DataFrame({'Ngày': all_dates})
        
        cal_data['Tuần_Bắt_Đầu'] = cal_data['Ngày'] - pd.to_timedelta((cal_data['Ngày'].dt.dayofweek + 1) % 7, unit='d')
        days_map = {"Monday": "Thứ 2", "Tuesday": "Thứ 3", "Wednesday": "Thứ 4", "Thursday": "Thứ 5", "Friday": "Thứ 6", "Saturday": "Thứ 7", "Sunday": "Chủ Nhật"}
        cal_data['Thứ'] = cal_data['Ngày'].dt.day_name().map(days_map)
        cal_data['Ngày_str'] = cal_data['Ngày'].dt.date
        
        grp = df.groupby('Ngày')['Thời lượng (Phút)'].sum().reset_index()
        cal_data = cal_data.merge(grp, left_on='Ngày_str', right_on='Ngày', how='left').fillna({'Thời lượng (Phút)': 0})
        cal_data['Số giờ'] = (cal_data['Thời lượng (Phút)'] / 60).round(1)
        
        chart = alt.Chart(cal_data).mark_rect(cornerRadius=3).encode(
            x=alt.X('yearmonthdate(Tuần_Bắt_Đầu):O', title='', axis=alt.Axis(format='%b', labelAngle=0, orient='top', tickSize=0, domain=False, labelExpr="month(datum.value) != month(datum.value - 7*24*60*60*1000) ? timeFormat(datum.value, '%b') : ''")),
            y=alt.Y('Thứ:O', sort=DAYS_ORDER, title='', scale=alt.Scale(domain=DAYS_ORDER), axis=alt.Axis(tickSize=0, domain=False)),
            color=alt.Color('Số giờ:Q', scale=alt.Scale(domain=[0, cal_data['Số giờ'].max() if cal_data['Số giờ'].max() > 0 else 1], range=['#e5e5ea', '#34c759']), legend=None),
            tooltip=[alt.Tooltip('Ngày_str:T', format='%d-%m-%Y', title='Ngày'), alt.Tooltip('Số giờ:Q', format='.1f', title='Giờ')]
        ).properties(width=alt.Step(40), height=alt.Step(40)).configure_view(strokeWidth=0)
        st.altair_chart(chart, use_container_width=True)
        
        # Tính Streak
        unique_dates = pd.to_datetime(df['Ngày'].unique()).sort_values()
        if not unique_dates.empty:
            total_days_streak = len(unique_dates)
            diffs = unique_dates.to_series().diff().dt.days
            streak_id = (diffs > 1).cumsum()
            streak_counts = streak_id.value_counts()
            longest_streak = streak_counts.max()
            db_max_date = pd.to_datetime(df['Ngày'].max())
            current_streak = streak_counts[streak_id.iloc[-1]] if (db_max_date - unique_dates.max()).days <= 1 else 0
        else:
            total_days_streak = longest_streak = current_streak = 0

        st.markdown(f"""
        <div class="glass-card" style='display: flex; width: 100%; max-width: 900px; margin: 20px auto; justify-content: center; align-items: center; padding: 25px;'>
            <div style='flex: 1; text-align: center; border-right: 1px solid rgba(0,0,0,0.1);'>
                <h3 style='margin:0; font-size: 32px;'>{total_days_streak} ngày</h3>
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

        st.header("5. Bảng số liệu")
        view_opt = st.radio("Xem theo:", ["Tuần", "Tháng"], horizontal=True, key="tk_view")
        time_col = 'Tuần' if view_opt == "Tuần" else 'Tháng'
        st.dataframe(get_pivot_with_totals(df, time_col), use_container_width=True)
    else:
        st.info("Chưa có dữ liệu hệ thống. Vui lòng sang tab 'Chuẩn bị dữ liệu' để tải file lên.")

# ==========================================
# TAB 2: BÁO CÁO THÁNG
# ==========================================
with tab_thang:
    if not df.empty:
        all_months = sorted(df['Tháng'].unique())
        if 'selected_month' not in st.session_state: st.session_state.selected_month = all_months[-1]
        current_year = st.session_state.selected_month.split('-')[0]
        
        # Lấy danh sách 12 tháng của năm hiện tại
        months_in_year = [f"{current_year}-{str(m).zfill(2)}" for m in range(1, 13)]
        tieng_viet_thang = ["Tháng 1", "Tháng 2", "Tháng 3", "Tháng 4", "Tháng 5", "Tháng 6", "Tháng 7", "Tháng 8", "Tháng 9", "Tháng 10", "Tháng 11", "Tháng 12"]
        
        st.markdown("<div class='glass-card link-button-container'>", unsafe_allow_html=True)
        st.markdown(f"<h3 style='text-align:center; margin-bottom: 15px;'>Năm {current_year}</h3>", unsafe_allow_html=True)
        m_cols = st.columns(12)
        
        for i, m_str in enumerate(months_in_year):
            with m_cols[i]:
                is_avail = m_str in all_months
                if is_avail:
                    # Dùng CSS hack để highlight nút đang chọn
                    if m_str == st.session_state.selected_month:
                        st.markdown("<div class='selected-link'>", unsafe_allow_html=True)
                        st.button(tieng_viet_thang[i], key=f"btn_m_{i}", on_click=lambda m=m_str: st.session_state.update(selected_month=m))
                        st.markdown("</div>", unsafe_allow_html=True)
                    else:
                        st.button(tieng_viet_thang[i], key=f"btn_m_{i}", on_click=lambda m=m_str: st.session_state.update(selected_month=m))
                else:
                    st.button(tieng_viet_thang[i], key=f"btn_m_dis_{i}", disabled=True)
        st.markdown("</div>", unsafe_allow_html=True)

        df_m = df[df['Tháng'] == st.session_state.selected_month]
        
        if not df_m.empty:
            avg_hrs_m = df.groupby('Tháng')['Thời lượng (Phút)'].sum().mean() / 60
            avg_trees_m = df.groupby('Tháng').size().mean()
            
            curr_idx = all_months.index(st.session_state.selected_month)
            prev_hrs_m = df[df['Tháng'] == all_months[curr_idx - 1]]['Thời lượng (Phút)'].sum() / 60 if curr_idx > 0 else None
            prev_trees_m = len(df[df['Tháng'] == all_months[curr_idx - 1]]) if curr_idx > 0 else None
            
            st.header("1. Tổng quan")
            c1, c2, c3, c4 = st.columns(4)
            c_hrs = df_m['Thời lượng (Phút)'].sum() / 60
            c_trees = len(df_m)
            n_days = df_m['Ngày'].nunique() or 1
            
            d1_hr = (c_hrs - prev_hrs_m) if prev_hrs_m is not None else None
            d2_hr = c_hrs - avg_hrs_m
            d1_tr = (c_trees - prev_trees_m) if prev_trees_m is not None else None
            d2_tr = c_trees - avg_trees_m
            
            with c1: render_glass_metric("Tổng thời gian", f"{c_hrs:.1f}h", d1_hr, "h (vs Tháng trước)", d2_hr, "h (vs Trung bình)")
            with c2: render_glass_metric("Thời gian TB/ngày", f"{c_hrs/n_days:.1f}h")
            with c3: render_glass_metric("Số cây đã trồng", f"{c_trees}", d1_tr, "cây (vs Tháng trước)", d2_tr, "cây (vs Trung bình)")
            with c4: render_glass_metric("Số cây TB/ngày", f"{c_trees/n_days:.1f}")
            
            st.write("")
            c_top1, c_top2 = st.columns(2)
            with c_top1: render_top_3(df_m, 'Danh mục', 'Top 3 Danh mục')
            with c_top2: render_top_3(df_m, 'Dự án', 'Top 3 Dự án')
            
            st.header("2. Xu hướng theo thời gian")
            col_m = st.radio("Phân loại biểu đồ theo:", ["Danh mục", "Dự án"], horizontal=True, key="m_rad")
            t_m = df_m.groupby(['Ngày', col_m])['Thời lượng (Phút)'].sum().reset_index()
            t_m['Số giờ'] = t_m['Thời lượng (Phút)'] / 60
            
            fig_m = px.bar(t_m, x='Ngày', y='Số giờ', color=col_m, color_discrete_sequence=MAC_COLORS)
            fig_m = add_week_dividers(fig_m, t_m, "Ngày")
            
            # Thêm Average Line
            avg_per_day = c_hrs / n_days
            fig_m = add_average_line(fig_m, avg_per_day, "TB")
            
            fig_m.update_layout(xaxis_title="Ngày trong tháng", yaxis_title="Số giờ")
            st.plotly_chart(format_plotly_fig(fig_m), use_container_width=True, config=PLOTLY_CONFIG)
            
            st.header("3. Phân bổ thời gian")
            pc_m = df_m.groupby(col_m)['Thời lượng (Phút)'].sum().reset_index()
            pc_m['Số giờ'] = pc_m['Thời lượng (Phút)'] / 60
            fig_p_m = px.pie(pc_m, values='Số giờ', names=col_m, color_discrete_sequence=MAC_COLORS)
            st.plotly_chart(format_plotly_fig(fig_p_m, is_pie=True), use_container_width=True, config=PLOTLY_CONFIG)
            
            st.header("4. Xu hướng làm việc theo khung giờ")
            h_m = df_m.groupby(['Khung giờ', col_m])['Thời lượng (Phút)'].sum().reset_index()
            h_m['Số giờ'] = h_m['Thời lượng (Phút)'] / 60
            fig_hm = px.bar(h_m, x='Khung giờ', y='Số giờ', color=col_m, color_discrete_sequence=MAC_COLORS)
            
            tot_hm = df_m.groupby('Khung giờ')['Thời lượng (Phút)'].sum().reset_index()
            tot_hm['Số giờ'] = tot_hm['Thời lượng (Phút)'] / 60
            fig_hm.add_trace(go.Scatter(
                x=tot_hm['Khung giờ'], y=tot_hm['Số giờ'], mode='lines+text', 
                text=tot_hm['Số giờ'].round(1).astype(str), textposition='top center', textfont=dict(color="#007aff", size=13),
                name='Tổng cộng', line=dict(color="#007aff", width=2.5)
            ))
            fig_hm.update_layout(xaxis_title="Khung giờ", yaxis_title="Số giờ", yaxis=dict(range=[0, tot_hm['Số giờ'].max() * 1.2]))
            st.plotly_chart(format_plotly_fig(fig_hm), use_container_width=True, config=PLOTLY_CONFIG)

# ==========================================
# TAB 3: BÁO CÁO TUẦN
# ==========================================
with tab_tuan:
    if not df.empty:
        all_weeks = sorted(df['Tuần'].unique())
        all_dates = pd.to_datetime(df['Ngày'].unique()).date
        
        if 'cal_month' not in st.session_state: 
            st.session_state.cal_month = pd.to_datetime(all_dates[-1]).replace(day=1)
        if 'selected_week' not in st.session_state: 
            st.session_state.selected_week = all_weeks[-1]
            
        c_year, c_month = st.session_state.cal_month.year, st.session_state.cal_month.month
        
        st.markdown("<div class='glass-card link-button-container'>", unsafe_allow_html=True)
        # Nút điều hướng tháng lịch
        nav1, nav2, nav3 = st.columns([1, 4, 1])
        with nav1:
            if st.button("◀", key="cal_prev"):
                first_day = st.session_state.cal_month
                st.session_state.cal_month = (first_day - timedelta(days=1)).replace(day=1)
                st.rerun()
        with nav2:
            st.markdown(f"<h3 style='text-align:center; margin:0;'>Tháng {c_month} / {c_year}</h3>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center; margin:0; color:#86868b; font-size:14px;'>Chọn một ngày để xem báo cáo tuần chứa ngày đó</p>", unsafe_allow_html=True)
        with nav3:
            if st.button("▶", key="cal_next"):
                next_month = c_month % 12 + 1
                next_year = c_year + (1 if c_month == 12 else 0)
                st.session_state.cal_month = datetime(next_year, next_month, 1).date()
                st.rerun()
                
        st.write("")
        # Vẽ Lịch Grid
        cal_matrix = calendar.monthcalendar(c_year, c_month)
        
        # Header thứ
        days_header = st.columns(7)
        for i, d in enumerate(["T2", "T3", "T4", "T5", "T6", "T7", "CN"]):
            days_header[i].markdown(f"<div class='cal-day-header'>{d}</div>", unsafe_allow_html=True)
            
        for week in cal_matrix:
            cols = st.columns(7)
            for i, day in enumerate(week):
                if day == 0:
                    cols[i].write("")
                else:
                    curr_d = datetime(c_year, c_month, day).date()
                    if curr_d in all_dates:
                        # Find the week string for this date from the dataframe
                        d_str = curr_d.strftime('%Y-%m-%d')
                        w_str = df[df['Ngày'].astype(str) == d_str]['Tuần'].iloc[0]
                        
                        if w_str == st.session_state.selected_week:
                            st.markdown("<div class='selected-link'>", unsafe_allow_html=True)
                            cols[i].button(str(day), key=f"d_{c_month}_{day}", on_click=lambda w=w_str: st.session_state.update(selected_week=w))
                            st.markdown("</div>", unsafe_allow_html=True)
                        else:
                            cols[i].button(str(day), key=f"d_{c_month}_{day}", on_click=lambda w=w_str: st.session_state.update(selected_week=w))
                    else:
                        cols[i].button(str(day), key=f"d_dis_{c_month}_{day}", disabled=True)
        st.markdown("</div>", unsafe_allow_html=True)

        df_w = df[df['Tuần'] == st.session_state.selected_week]
        
        if not df_w.empty:
            avg_hrs_w = df.groupby('Tuần')['Thời lượng (Phút)'].sum().mean() / 60
            avg_trees_w = df.groupby('Tuần').size().mean()
            
            curr_idx = all_weeks.index(st.session_state.selected_week)
            prev_hrs_w = df[df['Tuần'] == all_weeks[curr_idx - 1]]['Thời lượng (Phút)'].sum() / 60 if curr_idx > 0 else None
            prev_trees_w = len(df[df['Tuần'] == all_weeks[curr_idx - 1]]) if curr_idx > 0 else None
            
            st.header(f"Báo cáo Tuần {st.session_state.selected_week.split('-W')[-1]}")
            c1, c2, c3, c4 = st.columns(4)
            c_hrs = df_w['Thời lượng (Phút)'].sum() / 60
            c_trees = len(df_w)
            n_days = df_w['Ngày'].nunique() or 1
            
            d1_hr = (c_hrs - prev_hrs_w) if prev_hrs_w is not None else None
            d2_hr = c_hrs - avg_hrs_w
            d1_tr = (c_trees - prev_trees_w) if prev_trees_w is not None else None
            d2_tr = c_trees - avg_trees_w
            
            with c1: render_glass_metric("Tổng thời gian", f"{c_hrs:.1f}h", d1_hr, "h (vs Tuần trước)", d2_hr, "h (vs Trung bình)")
            with c2: render_glass_metric("Thời gian TB/ngày", f"{c_hrs/n_days:.1f}h")
            with c3: render_glass_metric("Số cây đã trồng", f"{c_trees}", d1_tr, "cây (vs Tuần trước)", d2_tr, "cây (vs Trung bình)")
            with c4: render_glass_metric("Số cây TB/ngày", f"{c_trees/n_days:.1f}")
            
            st.write("")
            c_top1, c_top2 = st.columns(2)
            with c_top1: render_top_3(df_w, 'Danh mục', 'Top 3 Danh mục')
            with c_top2: render_top_3(df_w, 'Dự án', 'Top 3 Dự án')
            
            st.header("2. Xu hướng theo thời gian")
            col_w = st.radio("Phân loại biểu đồ theo:", ["Danh mục", "Dự án"], horizontal=True, key="w_rad")
            t_w = df_w.groupby(['Thứ', col_w])['Thời lượng (Phút)'].sum().reset_index()
            t_w['Số giờ'] = t_w['Thời lượng (Phút)'] / 60
            
            fig_w = px.bar(t_w, x='Thứ', y='Số giờ', color=col_w, category_orders={"Thứ": DAYS_ORDER}, color_discrete_sequence=MAC_COLORS)
            fig_w = add_total_labels(fig_w, t_w, 'Thứ', 'Số giờ')
            fig_w = add_average_line(fig_w, c_hrs / 7, "TB") # Trung bình của 7 ngày trong tuần
            
            fig_w.update_layout(xaxis_title="Thứ trong tuần", yaxis_title="Số giờ")
            st.plotly_chart(format_plotly_fig(fig_w), use_container_width=True, config=PLOTLY_CONFIG)
            
            st.header("3. Phân bổ thời gian")
            pc_w = df_w.groupby(col_w)['Thời lượng (Phút)'].sum().reset_index()
            pc_w['Số giờ'] = pc_w['Thời lượng (Phút)'] / 60
            fig_p_w = px.pie(pc_w, values='Số giờ', names=col_w, color_discrete_sequence=MAC_COLORS)
            st.plotly_chart(format_plotly_fig(fig_p_w, is_pie=True), use_container_width=True, config=PLOTLY_CONFIG)
            
            st.header("4. Xu hướng làm việc theo khung giờ")
            h_w = df_w.groupby(['Khung giờ', col_w])['Thời lượng (Phút)'].sum().reset_index()
            h_w['Số giờ'] = h_w['Thời lượng (Phút)'] / 60
            fig_hw = px.bar(h_w, x='Khung giờ', y='Số giờ', color=col_w, color_discrete_sequence=MAC_COLORS)
            
            tot_hw = df_w.groupby('Khung giờ')['Thời lượng (Phút)'].sum().reset_index()
            tot_hw['Số giờ'] = tot_hw['Thời lượng (Phút)'] / 60
            fig_hw.add_trace(go.Scatter(
                x=tot_hw['Khung giờ'], y=tot_hw['Số giờ'], mode='lines+text', 
                text=tot_hw['Số giờ'].round(1).astype(str), textposition='top center', textfont=dict(color="#007aff", size=13),
                name='Tổng cộng', line=dict(color="#007aff", width=2.5)
            ))
            fig_hw.update_layout(xaxis_title="Khung giờ", yaxis_title="Số giờ", yaxis=dict(range=[0, tot_hw['Số giờ'].max() * 1.2]))
            st.plotly_chart(format_plotly_fig(fig_hw), use_container_width=True, config=PLOTLY_CONFIG)

# ==========================================
# TAB 4: BÁO CÁO THEO NHÓM
# ==========================================
with tab_nhom:
    if not df.empty:
        groups = sorted(list(df['Danh mục'].unique()) + list(df['Dự án'].unique()))
        sel_g = st.selectbox("Chọn Danh mục hoặc Dự án:", groups)
        df_g = df[(df['Danh mục'] == sel_g) | (df['Dự án'] == sel_g)]
        
        st.header("1. Tổng quan")
        c1, c2, c3, c4 = st.columns(4)
        c_hrs_g = df_g['Thời lượng (Phút)'].sum() / 60
        c_trees_g = len(df_g)
        n_days_g = df_g['Ngày'].nunique() or 1
        
        with c1: render_glass_metric("Tổng thời gian", f"{c_hrs_g:.1f}h")
        with c2: render_glass_metric("Thời gian TB/ngày", f"{c_hrs_g/n_days_g:.1f}h")
        with c3: render_glass_metric("Số cây đã trồng", f"{c_trees_g}")
        with c4: render_glass_metric("Số cây TB/ngày", f"{c_trees_g/n_days_g:.1f}")
        
        st.header("2. Xu hướng theo thời gian")
        mode_g = st.radio("Cơ sở dữ liệu biểu đồ:", ["Ngày", "Tuần", "Tháng"], horizontal=True, key="nhom_mode")
        t_g = df_g.groupby(mode_g)['Thời lượng (Phút)'].sum().reset_index()
        t_g['Số giờ'] = t_g['Thời lượng (Phút)'] / 60
        
        if mode_g == "Ngày":
            # Line không có smooth (xiên thẳng)
            fig_g = px.line(t_g, x=mode_g, y='Số giờ', color_discrete_sequence=[MAC_COLORS[0]])
            fig_g.update_traces(fill='tozeroy', fillcolor="rgba(0,122,255,0.1)", line_shape='linear')
            fig_g = add_week_dividers(fig_g, t_g, mode_g)
        else:
            fig_g = px.bar(t_g, x=mode_g, y='Số giờ', color_discrete_sequence=[MAC_COLORS[0]])
            fig_g = add_total_labels(fig_g, t_g, mode_g, 'Số giờ')
            
        fig_g.update_layout(xaxis_title=mode_g, yaxis_title="Số giờ")
        st.plotly_chart(format_plotly_fig(fig_g), use_container_width=True, config=PLOTLY_CONFIG)
        
        st.header("3. Biểu đồ lịch")
        min_date = df_g['Ngày'].min()
        max_date = df['Ngày'].max() 
        all_dates = pd.date_range(start=min_date, end=max_date)
        cal_data = pd.DataFrame({'Ngày': all_dates})
        
        cal_data['Tuần_Bắt_Đầu'] = cal_data['Ngày'] - pd.to_timedelta((cal_data['Ngày'].dt.dayofweek + 1) % 7, unit='d')
        days_map = {"Monday": "Thứ 2", "Tuesday": "Thứ 3", "Wednesday": "Thứ 4", "Thursday": "Thứ 5", "Friday": "Thứ 6", "Saturday": "Thứ 7", "Sunday": "Chủ Nhật"}
        cal_data['Thứ'] = cal_data['Ngày'].dt.day_name().map(days_map)
        cal_data['Ngày_str'] = cal_data['Ngày'].dt.date
        
        grp = df_g.groupby('Ngày')['Thời lượng (Phút)'].sum().reset_index()
        cal_data = cal_data.merge(grp, left_on='Ngày_str', right_on='Ngày', how='left').fillna({'Thời lượng (Phút)': 0})
        cal_data['Số giờ'] = (cal_data['Thời lượng (Phút)'] / 60).round(1)
        
        chart = alt.Chart(cal_data).mark_rect(cornerRadius=3).encode(
            x=alt.X('yearmonthdate(Tuần_Bắt_Đầu):O', title='', axis=alt.Axis(format='%b', labelAngle=0, orient='top', tickSize=0, domain=False, labelExpr="month(datum.value) != month(datum.value - 7*24*60*60*1000) ? timeFormat(datum.value, '%b') : ''")),
            y=alt.Y('Thứ:O', sort=DAYS_ORDER, title='', scale=alt.Scale(domain=DAYS_ORDER), axis=alt.Axis(tickSize=0, domain=False)),
            color=alt.Color('Số giờ:Q', scale=alt.Scale(domain=[0, cal_data['Số giờ'].max() if cal_data['Số giờ'].max() > 0 else 1], range=['#e5e5ea', '#34c759']), legend=None),
            tooltip=[alt.Tooltip('Ngày_str:T', format='%d-%m-%Y', title='Ngày'), alt.Tooltip('Số giờ:Q', format='.1f', title='Giờ')]
        ).properties(width=alt.Step(40), height=alt.Step(40)).configure_view(strokeWidth=0)
        st.altair_chart(chart, use_container_width=True)
        
        unique_dates = pd.to_datetime(df_g['Ngày'].unique()).sort_values()
        if not unique_dates.empty:
            t_days_g = len(unique_dates)
            diffs = unique_dates.to_series().diff().dt.days
            streak_id = (diffs > 1).cumsum()
            s_counts = streak_id.value_counts()
            l_streak_g = s_counts.max()
            db_max_date = pd.to_datetime(df['Ngày'].max())
            c_streak_g = s_counts[streak_id.iloc[-1]] if (db_max_date - unique_dates.max()).days <= 1 else 0
        else:
            t_days_g = l_streak_g = c_streak_g = 0

        st.markdown(f"""
        <div class="glass-card" style='display: flex; width: 100%; max-width: 900px; margin: 20px auto; justify-content: center; align-items: center; padding: 25px;'>
            <div style='flex: 1; text-align: center; border-right: 1px solid rgba(0,0,0,0.1);'>
                <h3 style='margin:0; font-size: 32px;'>{t_days_g} ngày</h3>
                <p style='margin:5px 0 0 0; color:#86868b; font-size: 15px; font-weight:500;'>Tổng cộng</p>
            </div>
            <div style='flex: 1; text-align: center; border-right: 1px solid rgba(0,0,0,0.1);'>
                <h3 style='margin:0; font-size: 32px;'>{l_streak_g} ngày</h3>
                <p style='margin:5px 0 0 0; color:#86868b; font-size: 15px; font-weight:500;'>Chuỗi dài nhất</p>
            </div>
            <div style='flex: 1; text-align: center;'>
                <h3 style='margin:0; font-size: 32px;'>{c_streak_g} ngày</h3>
                <p style='margin:5px 0 0 0; color:#86868b; font-size: 15px; font-weight:500;'>Chuỗi hiện tại</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ==========================================
# TAB 5: CHUẨN BỊ DỮ LIỆU
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
            if 'Dự án' in new_data.columns:
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
            st.dataframe(display_map, use_container_width=True)

    st.divider()
    st.header("3. Dữ liệu làm việc hiện tại")
    if not db_current.empty:
        disp_db = db_current.copy()
        disp_db['Thời gian bắt đầu'] = pd.to_datetime(disp_db['Thời gian bắt đầu']).dt.strftime('%Y-%m-%d %H:%M')
        disp_db['Thời gian kết thúc'] = pd.to_datetime(disp_db['Thời gian kết thúc']).dt.strftime('%Y-%m-%d %H:%M')
        if 'Note' in disp_db.columns: disp_db = disp_db.drop(columns=['Note'])
        disp_db.index = disp_db.index + 1
        st.dataframe(disp_db, use_container_width=True)
    
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
        if st.button("Xoá toàn bộ dữ liệu"):
            if os.path.exists(DB_FILE): os.remove(DB_FILE)
            if os.path.exists(MAPPING_FILE): os.remove(MAPPING_FILE)
            st.success("Đã xoá toàn bộ dữ liệu cục bộ!")
            time.sleep(1)
            st.rerun()
