import streamlit as st
import pandas as pd
import os
import time
import plotly.express as px
import plotly.graph_objects as go
import altair as alt

# --- CẤU HÌNH ---
DB_FILE = "database.csv"
MAPPING_FILE = "mapping.csv"

# Bảng màu Catppuccin Latte
LATTE_COLORS = [
    "#8839ef", "#1e66f5", "#40a02b", "#df8e1d", "#fe640b",
    "#d20f39", "#179299", "#ea76cb", "#209fb5", "#7287fd"
]
CHART_WIDTH = 1200 
PLOTLY_CONFIG = {'scrollZoom': False, 'displayModeBar': False} # Tắt cuộn và ẩn thanh công cụ

# --- CÁC HÀM XỬ LÝ DỮ LIỆU ---
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
    db['Tuần'] = db['Thời gian bắt đầu'].dt.strftime('%Y-W%U')
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

def add_total_labels(fig, df, x_col, y_col):
    totals = df.groupby(x_col)[y_col].sum().reset_index()
    fig.add_trace(go.Scatter(
        x=totals[x_col], y=totals[y_col], mode='text', text=totals[y_col].round(1).astype(str),
        textposition='top center', showlegend=False, hoverinfo='skip', textfont=dict(color="#4c4f69", size=13)
    ))
    fig.update_layout(yaxis=dict(range=[0, totals[y_col].max() * 1.15]))
    return fig

# Hàm tinh chỉnh Tooltip & Tắt zoom cho biểu đồ Plotly
def format_plotly_fig(fig, is_pie=False):
    fig.update_layout(dragmode=False) # Khóa kéo thả/zoom
    if is_pie:
        fig.update_traces(hovertemplate='<b>%{label}</b><br>%{value:.1f} giờ<extra></extra>')
    else:
        fig.update_traces(hovertemplate='<b>%{data.name}</b><br>%{y:.1f} giờ<extra></extra>')
    return fig

# --- CALLBACK ĐIỀU HƯỚNG ---
def change_period(key, step, options_list):
    curr_idx = options_list.index(st.session_state[key])
    new_idx = curr_idx + step
    if 0 <= new_idx < len(options_list):
        st.session_state[key] = options_list[new_idx]

# --- GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="Bộ theo dõi thời gian", layout="wide")

st.markdown(
    """
    <style>
    .block-container { max-width: 1200px !important; margin: 0 auto !important; padding-top: 2rem !important; }
    
    /* Cấu trúc box trắng bo góc cho Biểu đồ lịch (Altair) */
    .stVegaLiteChart { 
        display: flex !important; justify-content: center !important; margin: 0 auto !important; 
    }
    .chart-container {
        background-color: #ffffff;
        border: 1px solid #e6e9ef;
        border-radius: 12px;
        padding: 40px; /* Căn lề đều 4 phía */
        display: flex;
        justify-content: center;
        margin: 20px auto;
        width: fit-content;
        box-shadow: 0 4px 6px rgba(0,0,0,0.03);
    }
    
    div[data-testid="stButton"] button { width: 100%; }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Bảng theo dõi thời gian")
tabs = st.tabs(["Chuẩn bị dữ liệu", "Thống kê chung", "Báo cáo tháng", "Báo cáo tuần", "Báo cáo theo nhóm"])

# ==========================================
# TAB 1: CHUẨN BỊ DỮ LIỆU
# ==========================================
with tabs[0]:
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
        if st.button("Lưu quy tắc") and new_cat and sel_proj != "Không có Dự án mới":
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
        if st.button("Xác nhận Khôi phục"):
            if res_db: save_db(pd.read_csv(res_db))
            if res_map: save_mapping(pd.read_csv(res_map))
            if 'month_box' in st.session_state: del st.session_state['month_box']
            if 'week_box' in st.session_state: del st.session_state['week_box']
            st.success("Khôi phục hệ thống thành công!")
            time.sleep(1)
            st.rerun()
    with c3:
        st.subheader("Làm mới")
        if st.button("Xoá toàn bộ dữ liệu", type="primary"):
            if os.path.exists(DB_FILE): os.remove(DB_FILE)
            if os.path.exists(MAPPING_FILE): os.remove(MAPPING_FILE)
            if 'month_box' in st.session_state: del st.session_state['month_box']
            if 'week_box' in st.session_state: del st.session_state['week_box']
            st.success("Đã xoá toàn bộ dữ liệu cục bộ!")
            time.sleep(1)
            st.rerun()

df = prep_analysis_data()

# ==========================================
# TAB 2: THỐNG KÊ CHUNG
# ==========================================
with tabs[1]:
    if not df.empty:
        st.header("1. Tổng quan")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Tổng thời gian", f"{df['Thời lượng (Phút)'].sum() / 60:.1f} giờ")
        m2.metric("Số cây đã trồng", f"{len(df)} cây")
        m3.metric("Số lượng nhóm", f"{df['Danh mục'].nunique()} nhóm")
        m4.metric("Số lượng Dự án", f"{df['Dự án'].nunique()} Dự án")

        st.header("2. Xu hướng theo thời gian")
        color_col_2 = st.radio("Phân loại dữ liệu biểu đồ theo:", ["Danh mục", "Dự án"], horizontal=True, key="rad_tab2")
        trend_group = df.groupby(['Ngày', color_col_2])['Thời lượng (Phút)'].sum().reset_index()
        trend_group['Số giờ'] = trend_group['Thời lượng (Phút)'] / 60
        fig1 = px.bar(trend_group, x='Ngày', y='Số giờ', color=color_col_2, color_discrete_sequence=LATTE_COLORS)
        fig1.update_layout(width=CHART_WIDTH, xaxis_title="Ngày", yaxis_title="Số giờ")
        fig1 = format_plotly_fig(fig1)
        st.plotly_chart(fig1, use_container_width=False, config=PLOTLY_CONFIG)

        st.header("3. Xu hướng làm việc theo khung giờ")
        hr_group = df.groupby(['Khung giờ', color_col_2])['Thời lượng (Phút)'].sum().reset_index()
        hr_group['Số giờ'] = hr_group['Thời lượng (Phút)'] / 60
        fig2 = px.bar(hr_group, x='Khung giờ', y='Số giờ', color=color_col_2, color_discrete_sequence=LATTE_COLORS)
        fig2.update_layout(width=CHART_WIDTH, xaxis_title="Khung giờ (0h - 23h)", yaxis_title="Số giờ")
        fig2 = format_plotly_fig(fig2)
        st.plotly_chart(fig2, use_container_width=False, config=PLOTLY_CONFIG)

        st.header("4. Bảng số liệu")
        view_opt = st.radio("Xem theo:", ["Tuần", "Tháng"], horizontal=True)
        time_col = 'Tuần' if view_opt == "Tuần" else 'Tháng'
        st.dataframe(get_pivot_with_totals(df, time_col), width=CHART_WIDTH)
    else:
        st.info("Chưa có dữ liệu hệ thống.")

# ==========================================
# TAB 3: BÁO CÁO THÁNG
# ==========================================
with tabs[2]:
    if not df.empty:
        months = sorted(df['Tháng'].unique())
        if 'month_box' not in st.session_state or st.session_state.month_box not in months:
            st.session_state.month_box = months[-1]
            
        # Căn giữa hoàn hảo bằng vertical_alignment (Yêu cầu Streamlit >= 1.30.0)
        c_prev, c_sel, c_next = st.columns([1, 2, 1], vertical_alignment="center")
        with c_prev:
            st.button("◀ Trước", key="btn_prev_m", on_click=change_period, args=('month_box', -1, months))
        with c_sel:
            st.selectbox("Chọn Tháng", months, key="month_box", label_visibility="collapsed")
        with c_next:
            st.button("Sau ▶", key="btn_next_m", on_click=change_period, args=('month_box', 1, months))

        df_m = df[df['Tháng'] == st.session_state.month_box]
        
        if not df_m.empty:
            st.header("1. Tổng quan")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tổng thời gian", f"{df_m['Thời lượng (Phút)'].sum() / 60:.1f} giờ")
            c2.metric("Số cây đã trồng", f"{len(df_m)} cây")
            c3.metric("Số lượng nhóm", f"{df_m['Danh mục'].nunique()} nhóm")
            c4.metric("Số lượng Dự án", f"{df_m['Dự án'].nunique()} Dự án")
            
            st.header("2. Xu hướng theo thời gian")
            color_col_3 = st.radio("Phân loại dữ liệu biểu đồ theo:", ["Danh mục", "Dự án"], horizontal=True, key="rad_tab3")
            t_m = df_m.groupby(['Ngày', color_col_3])['Thời lượng (Phút)'].sum().reset_index()
            t_m['Số giờ'] = t_m['Thời lượng (Phút)'] / 60
            fig_m = px.bar(t_m, x='Ngày', y='Số giờ', color=color_col_3, color_discrete_sequence=LATTE_COLORS)
            fig_m.update_layout(width=CHART_WIDTH, xaxis_title="Ngày trong tháng", yaxis_title="Số giờ")
            fig_m = add_total_labels(fig_m, t_m, 'Ngày', 'Số giờ') 
            fig_m = format_plotly_fig(fig_m)
            st.plotly_chart(fig_m, use_container_width=False, config=PLOTLY_CONFIG)
            
            st.header("3. Phân bổ thời gian")
            pc_m = df_m.groupby(color_col_3)['Thời lượng (Phút)'].sum().reset_index()
            pc_m['Số giờ'] = pc_m['Thời lượng (Phút)'] / 60
            fig_p_m = px.pie(pc_m, values='Số giờ', names=color_col_3, color_discrete_sequence=LATTE_COLORS)
            fig_p_m.update_layout(width=CHART_WIDTH)
            fig_p_m = format_plotly_fig(fig_p_m, is_pie=True)
            st.plotly_chart(fig_p_m, use_container_width=False, config=PLOTLY_CONFIG)
            
            st.markdown("**Bảng chi tiết (Giờ):**")
            st.dataframe(get_table_with_totals(df_m), width=CHART_WIDTH)
            
            st.header("4. Xu hướng làm việc theo khung giờ")
            h_m = df_m.groupby(['Khung giờ', color_col_3])['Thời lượng (Phút)'].sum().reset_index()
            h_m['Số giờ'] = h_m['Thời lượng (Phút)'] / 60
            fig_hm = px.bar(h_m, x='Khung giờ', y='Số giờ', color=color_col_3, color_discrete_sequence=LATTE_COLORS)
            fig_hm.update_layout(width=CHART_WIDTH, xaxis_title="Khung giờ", yaxis_title="Số giờ")
            fig_hm = format_plotly_fig(fig_hm)
            st.plotly_chart(fig_hm, use_container_width=False, config=PLOTLY_CONFIG)

# ==========================================
# TAB 4: BÁO CÁO TUẦN
# ==========================================
with tabs[3]:
    if not df.empty:
        weeks = sorted(df['Tuần'].unique())
        if 'week_box' not in st.session_state or st.session_state.week_box not in weeks:
            st.session_state.week_box = weeks[-1]
            
        c_prev_w, c_sel_w, c_next_w = st.columns([1, 2, 1], vertical_alignment="center")
        with c_prev_w:
            st.button("◀ Trước", key="btn_prev_w", on_click=change_period, args=('week_box', -1, weeks))
        with c_sel_w:
            st.selectbox("Chọn Tuần", weeks, key="week_box", label_visibility="collapsed")
        with c_next_w:
            st.button("Sau ▶", key="btn_next_w", on_click=change_period, args=('week_box', 1, weeks))

        df_w = df[df['Tuần'] == st.session_state.week_box]
        
        if not df_w.empty:
            st.header("1. Tổng quan")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tổng thời gian", f"{df_w['Thời lượng (Phút)'].sum() / 60:.1f} giờ")
            c2.metric("Số cây đã trồng", f"{len(df_w)} cây")
            c3.metric("Số lượng nhóm", f"{df_w['Danh mục'].nunique()} nhóm")
            c4.metric("Số lượng Dự án", f"{df_w['Dự án'].nunique()} Dự án")
            
            st.header("2. Xu hướng theo thời gian")
            color_col_4 = st.radio("Phân loại dữ liệu biểu đồ theo:", ["Danh mục", "Dự án"], horizontal=True, key="rad_tab4")
            days_order = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
            t_w = df_w.groupby(['Thứ', color_col_4])['Thời lượng (Phút)'].sum().reset_index()
            t_w['Số giờ'] = t_w['Thời lượng (Phút)'] / 60
            fig_w = px.bar(t_w, x='Thứ', y='Số giờ', color=color_col_4, category_orders={"Thứ": days_order}, color_discrete_sequence=LATTE_COLORS)
            fig_w.update_layout(width=CHART_WIDTH, xaxis_title="Thứ trong tuần", yaxis_title="Số giờ")
            fig_w = add_total_labels(fig_w, t_w, 'Thứ', 'Số giờ')
            fig_w = format_plotly_fig(fig_w)
            st.plotly_chart(fig_w, use_container_width=False, config=PLOTLY_CONFIG)
            
            st.header("3. Phân bổ thời gian")
            pc_w = df_w.groupby(color_col_4)['Thời lượng (Phút)'].sum().reset_index()
            pc_w['Số giờ'] = pc_w['Thời lượng (Phút)'] / 60
            fig_p_w = px.pie(pc_w, values='Số giờ', names=color_col_4, color_discrete_sequence=LATTE_COLORS)
            fig_p_w.update_layout(width=CHART_WIDTH)
            fig_p_w = format_plotly_fig(fig_p_w, is_pie=True)
            st.plotly_chart(fig_p_w, use_container_width=False, config=PLOTLY_CONFIG)
            
            st.markdown("**Bảng chi tiết (Giờ):**")
            st.dataframe(get_table_with_totals(df_w), width=CHART_WIDTH)
            
            st.header("4. Xu hướng làm việc theo khung giờ")
            h_w = df_w.groupby(['Khung giờ', color_col_4])['Thời lượng (Phút)'].sum().reset_index()
            h_w['Số giờ'] = h_w['Thời lượng (Phút)'] / 60
            fig_hw = px.bar(h_w, x='Khung giờ', y='Số giờ', color=color_col_4, color_discrete_sequence=LATTE_COLORS)
            fig_hw.update_layout(width=CHART_WIDTH, xaxis_title="Khung giờ", yaxis_title="Số giờ")
            fig_hw = format_plotly_fig(fig_hw)
            st.plotly_chart(fig_hw, use_container_width=False, config=PLOTLY_CONFIG)

# ==========================================
# TAB 5: BÁO CÁO THEO NHÓM
# ==========================================
with tabs[4]:
    if not df.empty:
        all_groups = list(df['Danh mục'].unique()) + list(df['Dự án'].unique())
        sel_grp = st.selectbox("Chọn Danh mục hoặc Dự án:", list(set(all_groups)))
        
        df_g = df[(df['Danh mục'] == sel_grp) | (df['Dự án'] == sel_grp)]
        
        st.header("1. Tổng quan")
        c1, c2 = st.columns(2)
        c1.metric("Tổng thời gian", f"{df_g['Thời lượng (Phút)'].sum() / 60:.1f} giờ")
        c2.metric("Số cây đã trồng", f"{len(df_g)} cây")
        
        st.header("2. Xu hướng theo thời gian")
        t_g = df_g.groupby('Ngày')['Thời lượng (Phút)'].sum().reset_index()
        t_g['Số giờ'] = t_g['Thời lượng (Phút)'] / 60
        fig_g = px.bar(t_g, x='Ngày', y='Số giờ', color_discrete_sequence=[LATTE_COLORS[0]])
        fig_g.update_layout(width=CHART_WIDTH, xaxis_title="Ngày", yaxis_title="Số giờ")
        fig_g = format_plotly_fig(fig_g)
        st.plotly_chart(fig_g, use_container_width=False, config=PLOTLY_CONFIG)
        
        st.header("3. Biểu đồ lịch")
        
        min_date = df_g['Ngày'].min()
        max_date = df['Ngày'].max() 
        all_dates = pd.date_range(start=min_date, end=max_date)
        cal_data = pd.DataFrame({'Ngày': all_dates})
        cal_data['Tuần_Bắt_Đầu'] = cal_data['Ngày'] - pd.to_timedelta(cal_data['Ngày'].dt.dayofweek, unit='d')
        
        days_map = {"Monday": "Thứ 2", "Tuesday": "Thứ 3", "Wednesday": "Thứ 4", "Thursday": "Thứ 5", "Friday": "Thứ 6", "Saturday": "Thứ 7", "Sunday": "Chủ Nhật"}
        cal_data['Thứ'] = cal_data['Ngày'].dt.day_name().map(days_map)
        cal_data['Ngày_str'] = cal_data['Ngày'].dt.date
        
        grp = df_g.groupby('Ngày')['Thời lượng (Phút)'].sum().reset_index()
        cal_data = cal_data.merge(grp, left_on='Ngày_str', right_on='Ngày', how='left').fillna({'Thời lượng (Phút)': 0})
        cal_data['Số giờ'] = (cal_data['Thời lượng (Phút)'] / 60).round(1)
        
        days_order = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
        
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        chart = alt.Chart(cal_data).mark_rect(cornerRadius=3).encode(
            x=alt.X('yearmonthdate(Tuần_Bắt_Đầu):O', 
                    title='', 
                    axis=alt.Axis(format='%b', labelAngle=0, orient='top', tickSize=0, domain=False,
                                  labelExpr="month(datum.value) != month(datum.value - 7*24*60*60*1000) ? timeFormat(datum.value, '%b') : ''")),
            y=alt.Y('Thứ:O', sort=days_order, title='', scale=alt.Scale(domain=days_order), axis=alt.Axis(tickSize=0, domain=False)),
            color=alt.Color('Số giờ:Q', scale=alt.Scale(domain=[0, cal_data['Số giờ'].max() if cal_data['Số giờ'].max() > 0 else 1], range=['#e6e9ef', '#40a02b']), legend=None),
            # Tinh chỉnh Tooltip cho Altair hiển thị số gọn gàng 1 chữ số thập phân
            tooltip=[alt.Tooltip('Ngày_str:T', format='%d-%m-%Y', title='Ngày'), alt.Tooltip('Số giờ:Q', format='.1f', title='Giờ')]
        ).properties(width=alt.Step(40), height=alt.Step(40)).configure_view(strokeWidth=0)
        
        st.altair_chart(chart, use_container_width=False)
        st.markdown('</div>', unsafe_allow_html=True)
        
        unique_dates = pd.to_datetime(df_g['Ngày'].unique()).sort_values()
        if not unique_dates.empty:
            total_days = len(unique_dates)
            diffs = unique_dates.to_series().diff().dt.days
            streak_id = (diffs > 1).cumsum()
            streak_counts = streak_id.value_counts()
            longest_streak = streak_counts.max()
            db_max_date = pd.to_datetime(df['Ngày'].max())
            proj_max_date = unique_dates.max()
            current_streak = streak_counts[streak_id.iloc[-1]] if (db_max_date - proj_max_date).days <= 1 else 0
        else:
            total_days = longest_streak = current_streak = 0

        st.markdown(f"""
        <div style='display: flex; width: 100%; max-width: 900px; margin: 0 auto; justify-content: center; align-items: center; border: 1px solid #e6e9ef; border-radius: 8px; padding: 25px; margin-top: 15px; background-color: #ffffff; box-shadow: 0 2px 4px rgba(0,0,0,0.02);'>
            <div style='flex: 1; text-align: center; border-right: 1px solid #dce0e8;'>
                <h3 style='margin:0; color:#4c4f69; font-size: 28px; font-weight: 600;'>{total_days} ngày</h3>
                <p style='margin:5px 0 0 0; color:#8c8fa1; font-size: 15px;'>Tổng cộng</p>
            </div>
            <div style='flex: 1; text-align: center; border-right: 1px solid #dce0e8;'>
                <h3 style='margin:0; color:#4c4f69; font-size: 28px; font-weight: 600;'>{longest_streak} ngày</h3>
                <p style='margin:5px 0 0 0; color:#8c8fa1; font-size: 15px;'>Chuỗi dài nhất</p>
            </div>
            <div style='flex: 1; text-align: center;'>
                <h3 style='margin:0; color:#4c4f69; font-size: 28px; font-weight: 600;'>{current_streak} ngày</h3>
                <p style='margin:5px 0 0 0; color:#8c8fa1; font-size: 15px;'>Chuỗi hiện tại</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
