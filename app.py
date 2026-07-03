import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import os
import io
import json
import time
import zipfile
import plotly.express as px
import plotly.graph_objects as go
import altair as alt
import colorsys
import re
from itertools import groupby
from html import escape as html_escape
from datetime import date, datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo
from streamlit_quill import st_quill
from supabase import create_client
from caldav import DAVClient

# Thanh công cụ cho ô soạn ghi chú (Quill): đậm/nghiêng/gạch chân, màu chữ & nền,
# danh sách + thụt lề, liên kết, xoá định dạng. (Không bật chèn ảnh để tránh phình notes.csv.)
NOTE_TOOLBAR = [
    ["bold", "italic", "underline"],
    [{"color": []}, {"background": []}],
    [{"list": "ordered"}, {"list": "bullet"}, {"indent": "-1"}, {"indent": "+1"}],
    ["link"],
    ["clean"],
]

# Quill (ô soạn ghi chú) chạy trong iframe riêng nên CSS của app không chạm tới được.
# Bộ CSS dưới đây được bơm vào *bên trong* iframe để ô soạn hợp tông app:
# - chữ to & rõ hơn (mặc định Quill chỉ 13px), font Apple, dòng thoáng;
# - thu hẹp mỗi bậc thụt lề (Tab) từ 3em mặc định xuống 1.6em — cho cả đoạn văn lẫn
#   mục danh sách; selector :not(.ql-direction-rtl) để khớp đúng độ ưu tiên của Quill;
# - bo góc, màu chỉ dẫn (placeholder) nhạt, con trỏ & nút đang bật theo màu accent #00a3ad.
QUILL_CSS = """
.ql-toolbar.ql-snow { border-color:#e2e2e7; border-top-left-radius:10px; border-top-right-radius:10px; background:#fafafa; }
.ql-container.ql-snow { border-color:#e2e2e7; border-bottom-left-radius:10px; border-bottom-right-radius:10px;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; font-size:15px; }
.ql-editor { line-height:1.65; padding:14px 16px; color:#1d1d1f; min-height:150px; caret-color:#00a3ad; }
.ql-editor.ql-blank::before { color:#aeaeb2; font-style:normal; left:16px; right:16px; }
.ql-editor .ql-indent-1:not(.ql-direction-rtl){padding-left:1.6em;}
.ql-editor .ql-indent-2:not(.ql-direction-rtl){padding-left:3.2em;}
.ql-editor .ql-indent-3:not(.ql-direction-rtl){padding-left:4.8em;}
.ql-editor .ql-indent-4:not(.ql-direction-rtl){padding-left:6.4em;}
.ql-editor li.ql-indent-1:not(.ql-direction-rtl){padding-left:3.1em;}
.ql-editor li.ql-indent-2:not(.ql-direction-rtl){padding-left:4.7em;}
.ql-editor li.ql-indent-3:not(.ql-direction-rtl){padding-left:6.3em;}
.ql-editor li.ql-indent-4:not(.ql-direction-rtl){padding-left:7.9em;}
.ql-snow.ql-toolbar button:hover .ql-stroke, .ql-snow.ql-toolbar button.ql-active .ql-stroke,
.ql-snow .ql-toolbar button:hover .ql-stroke, .ql-snow.ql-toolbar .ql-picker-label:hover .ql-stroke { stroke:#00a3ad; }
.ql-snow.ql-toolbar button:hover .ql-fill, .ql-snow.ql-toolbar button.ql-active .ql-fill { fill:#00a3ad; }
.ql-snow.ql-toolbar button:hover, .ql-snow.ql-toolbar button.ql-active { color:#00a3ad; }
"""


def style_quill():
    """Bơm QUILL_CSS vào trong iframe của Quill (cùng origin). Lặp lại định kỳ vì mỗi
    lần Streamlit rerun, iframe bị tạo lại và mất style. Chỉ gọi khi đang mở ô soạn."""
    js = (
        "<script>\n"
        "const CSS = " + json.dumps(QUILL_CSS.replace("#00a3ad", ACCENT)) + ";\n"
        "function applyQuillCss(){\n"
        "  try{\n"
        "    const frames = window.parent.document.querySelectorAll('iframe');\n"
        "    frames.forEach(function(f){\n"
        "      let d; try{ d = f.contentDocument; }catch(e){ return; }\n"
        "      if(!d || !d.querySelector('.ql-editor')) return;\n"
        "      if(d.getElementById('app-quill-css')) return;\n"
        "      const s = d.createElement('style'); s.id='app-quill-css'; s.textContent=CSS;\n"
        "      d.head.appendChild(s);\n"
        "    });\n"
        "  }catch(e){}\n"
        "}\n"
        "applyQuillCss();\n"
        "setInterval(applyQuillCss, 400);\n"
        "</script>"
    )
    components.html(js, height=0)


def _note_is_empty(html):
    """Ghi chú coi như rỗng nếu sau khi bỏ thẻ HTML chỉ còn khoảng trắng (Quill để '<p><br></p>')."""
    if not html:
        return True
    txt = re.sub(r"<[^>]+>", "", str(html)).replace("&nbsp;", " ").replace(" ", " ")
    return txt.strip() == ""

# --- CẤU HÌNH ---
# Tên file dùng làm tên thành viên bên trong .zip Sao lưu/Khôi phục (mục "Quản lý hệ thống")
# -- dữ liệu thật luôn nằm trên Supabase, các tên này không còn là đường dẫn đọc/ghi local.
DB_FILE = "database.csv"
MAPPING_FILE = "mapping.csv"
DELETED_FILE = "deleted.csv"  # khoá thời gian của các phiên đã xoá -> không nạp lại
NOTES_FILE = "notes.csv"  # ghi chú/nhật ký theo ngày
WORK_CALENDAR_FILE = "work_calendar.csv"  # appointment đồng bộ từ lịch Work
READING_LOG_FILE = "reading_log.csv"  # phần sách/Gundam đã đọc/xem, nạp từ Apple Reminders
SETTINGS_FILE = "settings.csv"  # cấu hình tuỳ chỉnh (hiện dùng cho màu accent)

@st.cache_resource
def _get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# "Nhật ký đọc sách": chỉ hiện cho nhóm sách đọc tuần tự (sửa tên ở đây nếu khác).
# BOOKS_EXCLUDE = các dự án định kỳ (vd tạp chí) hoặc không phải sách (vd Gundam, xem tab riêng)
# -> không tính như một cuốn sách.
BOOKS_GROUP = "Reading"
BOOKS_EXCLUDE = {"The Economist", "Gundam"}

# Tag Dự án trên Forest khi bấm giờ xem Gundam -- không có Dự án riêng theo từng series, chỉ 1
# tag chung này; xem _assign_gundam_sessions() để biết cách suy ra series đang xem theo ngày.
GUNDAM_TAG = "Gundam"

# render_reading_log() dùng chung cho tab "Nhật ký đọc sách" (mặc định) và tab "Gundam" (truyền
# labels=GUNDAM_LABELS) -- chỉ khác nhau ở CHỮ hiển thị, không khác logic tính toán. Tên cột nội
# bộ trong DataFrame (vd 'Cuốn sách', 'Trạng thái') giữ nguyên bất kể labels nào đang dùng.
READING_LABELS = dict(
    item_col="Cuốn sách", count_label="Số cuốn", days_label="Ngày đọc",
    parts_label="Số phần đã đọc", part_recent_label="Phần gần nhất", part_word="phần",
    verb="đọc", ongoing="Đang đọc", empty_msg="Chưa có dữ liệu sách trong nhóm này.",
    detail_label="Chi tiết từng cuốn", timeslot_label="Khung giờ đọc",
    timeslot_best="Hay đọc nhất", streak_label="Chuỗi đọc", pace_days_label="Số ngày đọc",
    pace_pct_label="% ngày có đọc", avg_hr_label="TB giờ/cuốn", avg_days_label="TB ngày/cuốn",
    fastest_label="Đọc nhanh nhất",
)
GUNDAM_LABELS = dict(
    READING_LABELS, item_col="Series", count_label="Số series", days_label="Ngày xem",
    parts_label="Số tập đã xem", part_recent_label="Tập gần nhất", part_word="tập",
    verb="xem", ongoing="Đang xem", empty_msg="Chưa có dữ liệu Gundam trong nhóm này.",
    detail_label="Chi tiết từng series", timeslot_label="Khung giờ xem",
    timeslot_best="Hay xem nhất", streak_label="Chuỗi xem", pace_days_label="Số ngày xem",
    pace_pct_label="% ngày có xem", avg_hr_label="TB giờ/series", avg_days_label="TB ngày/series",
    fastest_label="Xem nhanh nhất",
)

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


# 14 lựa chọn màu accent (tab Tuỳ biến → "1. Giao diện"), người dùng tự chọn từ bản mockup --
# xếp theo thứ tự hue tăng dần (đỏ/cam/vàng -> xanh lá -> xanh dương -> tím) cho có thứ tự hợp
# lý khi hiện thành lưới, riêng "Than chì" (gần như xám) xếp cuối vì không thuộc dải màu nào.
# Lưu ý: 3 màu đầu (Hồng đào/Cam cháy/Vàng nắng) CỐ Ý trùng vùng tông app đang dùng cho cảnh báo
# (cam, NUDGE_TONES "warn") / chuỗi đứt (đỏ, "neutral") -- người dùng đã xác nhận muốn có nhóm
# màu này dù biết sẽ trông gần giống 2 trạng thái đó nếu chọn làm accent.
ACCENT_PRESETS = {
    "Hồng đào": "#e25a66",
    "Cam cháy": "#dc6018",
    "Vàng nắng": "#e7bf23",
    "Xanh lá (Green)": "#34c759",
    "Ngọc lục bảo (Jade)": "#00b386",
    "Bạc hà đậm": "#0a7671",
    "Xanh ngọc (Teal)": "#00a3ad",      # mặc định, giữ NGUYÊN màu hiện tại
    "Xanh lơ (Cyan)": "#32ade6",
    "Xanh dương (Blue)": "#007aff",
    "Navy đậm": "#203a6f",
    "Chàm (Indigo)": "#5856d6",
    "Tím than": "#2d2768",
    "Tím (Purple)": "#af52de",
    "Than chì": "#6c737a",
}


def _hsl_hex(h, s, l):
    """(hue, saturation, lightness) trong [0,1] -> mã màu hex."""
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return f"#{int(round(r * 255)):02x}{int(round(g * 255)):02x}{int(round(b * 255)):02x}"


def _hex_hue(hexcode):
    """Mã hex -> hue [0,1] (colorsys.rgb_to_hls) -- suy TEAL_HUE động từ accent đang chọn."""
    h = hexcode.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    hue, _, _ = colorsys.rgb_to_hls(r, g, b)
    return hue


def _hex_rgb_str(hexcode):
    h = hexcode.lstrip("#")
    return f"{int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)}"


def _darken(hexcode, factor=0.72):
    """Bản đậm hơn (giữ hue/saturation, giảm lightness) -- dùng cho chữ/icon trên nền accent
    nhạt (NUDGE_TONES "good", chip .tw). factor=0.72 khớp #00767d hiện có khi input #00a3ad."""
    h = hexcode.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    hue, l, s = colorsys.rgb_to_hls(r, g, b)
    return _hsl_hex(hue, s, l * factor)


def _readable_text(hexcode):
    """Chữ trắng hay đen đọc rõ hơn trên nền màu này (độ chói YIQ) -- dùng cho tên màu hiện
    ngay trên nút accent (mục "1. Giao diện"), tự thích ứng khi thêm/bớt preset sau này."""
    h = hexcode.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#1d1d1f" if luminance > 0.6 else "#ffffff"


def load_settings():
    """Đọc bảng settings (key/value) -> dict. Trả {} nếu lỗi/chưa cấu hình Supabase/chưa tạo
    bảng -- tính năng optional, KHÔNG được làm crash app. Hàm này chạy Ở CẤP MODULE, rất sớm
    (trước cả st.set_page_config()/cổng kiểm tra secrets bên dưới) vì ACCENT/TEAL_HUE phải có
    giá trị trước khi _teal_shades() được gọi lần đầu (SESSION_BUCKETS) -- nên phải tự bọc lỗi
    ở đây, không được dựa vào cổng secrets đã chạy trước nó."""
    try:
        res = _get_supabase().table("settings").select("key,value").execute()
        return {r["key"]: r["value"] for r in (res.data or [])}
    except Exception:
        return {}


@st.cache_data
def _cached_settings():
    return load_settings()


def save_setting(key, value):
    try:
        _get_supabase().table("settings").upsert({"key": key, "value": value}, on_conflict="key").execute()
        st.cache_data.clear()
        return True
    except Exception:
        return False


# Accent (màu nhấn) đang chọn -- fallback Teal mặc định nếu chưa từng chọn hoặc lỗi. PHẢI tính
# TRƯỚC _SESSION_COLORS = _teal_shades(5) (dưới đây) vì đó là câu lệnh cấp module chạy ngay khi
# import, sớm hơn cả st.set_page_config()/cổng kiểm tra secrets Supabase.
_accent_hex = _cached_settings().get("accent_hex", "#00a3ad")
if _accent_hex not in ACCENT_PRESETS.values():   # giá trị lạ (hỏng/ghi tay) -> fallback an toàn
    _accent_hex = "#00a3ad"
ACCENT = _accent_hex
ACCENT_RGB = _hex_rgb_str(ACCENT)
ACCENT_DARK = _darken(ACCENT)
TEAL_HUE = _hex_hue(ACCENT)  # giữ tên biến cũ -- mọi nơi đang dùng TEAL_HUE không cần sửa


def _teal_shades(n, l_lo=0.90, l_hi=0.26):
    """Sinh n sắc độ teal (cùng hue với accent #00a3ad) từ nhạt (l_lo) đến đậm (l_hi)
    -> dùng chung cho các bảng nhiệt (Biểu đồ lịch, Giờ tập trung theo thứ, thanh Phân bổ
    độ dài phiên) để đồng bộ một họ màu thay vì mỗi nơi một tông riêng."""
    return [_hsl_hex(TEAL_HUE, 0.75, l_lo + (l_hi - l_lo) * i / (n - 1)) for i in range(n)]


def build_color_map(names):
    """Gán màu cố định cho từng tên (Danh mục/Dự án). Ưu tiên bảng màu cơ sở;
    nếu nhiều hơn số màu sẵn có thì sinh thêm màu phân biệt bằng góc vàng
    (golden angle) để không bao giờ bị trùng màu, vẫn ổn định theo tên."""
    colors = list(MAC_COLORS)
    for k in range(len(names) - len(colors)):
        h = (0.61 + (k + 1) * 0.6180339887) % 1.0  # rải đều sắc độ
        colors.append(_hsl_hex(h, 0.62, 0.55))
    return {name: colors[i] for i, name in enumerate(names)}
PLOTLY_CONFIG = {'scrollZoom': False, 'displayModeBar': False, 'responsive': True}

# --- CÁC HÀM XỬ LÝ DỮ LIỆU (đọc/ghi qua Supabase) ---
# save_* dùng ngữ nghĩa "ghi đè toàn bộ" (xoá hết rồi insert lại) để khớp hành vi các nơi gọi.
def _fmt_ts(v):
    """Chuẩn hoá 1 giá trị giờ (chuỗi hoặc Timestamp, có/không giây lẻ) về đúng 1 định dạng
    cố định "YYYY-MM-DD HH:MM:SS" (bỏ giây lẻ) trước khi ghi vào Supabase -- các nguồn ghi
    khác nhau (nạp CSV mới cho ra Timestamp có giây lẻ, dữ liệu cũ đã là chuỗi không giây lẻ)
    nếu không chuẩn hoá sẽ lệch định dạng nhau, làm hỏng bước đọc lại (xem load_db)."""
    return pd.Timestamp(v).strftime("%Y-%m-%d %H:%M:%S")

@st.cache_data
def load_db():
    sb = _get_supabase()
    res = sb.table("sessions").select("start_time,end_time,project,duration_min").execute()
    cols = ["Thời gian bắt đầu", "Thời gian kết thúc", "Dự án", "Thời lượng (Phút)"]
    if not res.data:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(res.data).rename(columns={
        "start_time": "Thời gian bắt đầu", "end_time": "Thời gian kết thúc",
        "project": "Dự án", "duration_min": "Thời lượng (Phút)"})
    # Chuẩn hoá chuỗi giờ Supabase trả về (ISO 8601) về đúng dạng "YYYY-MM-DD HH:MM:SS"
    # như trước đây -> mọi chỗ parse/so khớp chuỗi phía sau không cần đổi gì. format='ISO8601'
    # (thay vì để pandas tự đoán 1 định dạng cố định từ vài dòng đầu) vì dữ liệu cũ có thể có
    # dòng có/không giây lẻ lẫn nhau -- suy đoán 1 định dạng chung sẽ lỗi ở dòng lệch định dạng.
    for c in ["Thời gian bắt đầu", "Thời gian kết thúc"]:
        df[c] = pd.to_datetime(df[c], format='ISO8601').dt.strftime("%Y-%m-%d %H:%M:%S")
    return df[cols]

def _sb_delete_all(table, not_null_col):
    """Xoá toàn bộ 1 bảng Supabase. Postgrest yêu cầu delete() phải kèm điều kiện lọc ->
    dùng "not_null_col IS NOT NULL" (luôn đúng vì cột đó là NOT NULL) làm điều kiện chắc chắn
    khớp mọi dòng, không phụ thuộc kiểu dữ liệu/giá trị cụ thể của bảng."""
    _get_supabase().table(table).delete().not_.is_(not_null_col, "null").execute()

def save_db(df):
    sb = _get_supabase()
    _sb_delete_all("sessions", "id")
    recs = [
        {"start_time": _fmt_ts(r["Thời gian bắt đầu"]), "end_time": _fmt_ts(r["Thời gian kết thúc"]),
         "project": str(r["Dự án"]), "duration_min": int(r["Thời lượng (Phút)"])}
        for r in df.to_dict("records")
    ]
    for i in range(0, len(recs), 500):  # chèn theo lô, tránh request quá lớn
        sb.table("sessions").insert(recs[i:i + 500]).execute()
    st.cache_data.clear()

@st.cache_data
def load_mapping():
    sb = _get_supabase()
    res = sb.table("mapping").select("project,category").execute()
    cols = ["Dự án", "Danh mục"]
    if not res.data:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(res.data).rename(columns={"project": "Dự án", "category": "Danh mục"})[cols]

def save_mapping(df):
    sb = _get_supabase()
    _sb_delete_all("mapping", "project")
    if not df.empty:
        recs = [{"project": str(r["Dự án"]), "category": str(r["Danh mục"])} for r in df.to_dict("records")]
        sb.table("mapping").insert(recs).execute()
    st.cache_data.clear()

@st.cache_data
def load_deleted():
    """Danh sách phiên đã xoá (theo khoá thời gian bắt đầu + kết thúc, dạng chuỗi)."""
    sb = _get_supabase()
    res = sb.table("deleted_sessions").select("start_time,end_time").execute()
    cols = ["Thời gian bắt đầu", "Thời gian kết thúc"]
    if not res.data:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(res.data).rename(columns={"start_time": "Thời gian bắt đầu", "end_time": "Thời gian kết thúc"})
    for c in cols:
        df[c] = pd.to_datetime(df[c], format='ISO8601').dt.strftime("%Y-%m-%d %H:%M:%S")
    return df[cols].astype(str)

def add_deleted(keys_df):
    """Gộp thêm các khoá thời gian vào danh sách đã xoá (keys_df có 2 cột thời gian)."""
    keys = keys_df[["Thời gian bắt đầu", "Thời gian kết thúc"]]
    sb = _get_supabase()
    recs = [{"start_time": _fmt_ts(r["Thời gian bắt đầu"]), "end_time": _fmt_ts(r["Thời gian kết thúc"])}
            for r in keys.to_dict("records")]
    if recs:
        sb.table("deleted_sessions").upsert(recs, on_conflict="start_time,end_time").execute()
    st.cache_data.clear()

def save_deleted(df):
    """Ghi đè toàn bộ danh sách đã xoá (dùng khi Khôi phục từ bản sao lưu)."""
    sb = _get_supabase()
    _sb_delete_all("deleted_sessions", "start_time")
    if not df.empty:
        recs = [{"start_time": _fmt_ts(r["Thời gian bắt đầu"]), "end_time": _fmt_ts(r["Thời gian kết thúc"])}
                for r in df.to_dict("records")]
        for i in range(0, len(recs), 500):
            sb.table("deleted_sessions").insert(recs[i:i + 500]).execute()
    st.cache_data.clear()

@st.cache_data
def load_notes():
    """Ghi chú/nhật ký theo ngày: cột Ngày (YYYY-MM-DD) + Ghi chú (text)."""
    sb = _get_supabase()
    res = sb.table("notes").select("note_date,note").execute()
    cols = ["Ngày", "Ghi chú"]
    if not res.data:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(res.data).rename(columns={"note_date": "Ngày", "note": "Ghi chú"})[cols].astype(str)

def get_note(day):
    nd = load_notes()
    m = nd[nd['Ngày'].astype(str) == str(day)]
    return str(m.iloc[0]['Ghi chú']) if not m.empty else ""

def save_note(day, text):
    """Lưu/sửa ghi chú của một ngày; nội dung rỗng = xoá ghi chú ngày đó."""
    key = str(day)
    text = "" if _note_is_empty(text) else str(text).strip()
    sb = _get_supabase()
    if text:
        sb.table("notes").upsert({"note_date": key, "note": text}, on_conflict="note_date").execute()
    else:
        sb.table("notes").delete().eq("note_date", key).execute()
    st.cache_data.clear()

def save_notes_bulk(df):
    """Ghi đè toàn bộ ghi chú (dùng khi Khôi phục từ bản sao lưu)."""
    sb = _get_supabase()
    _sb_delete_all("notes", "note_date")
    if not df.empty:
        recs = [{"note_date": str(r["Ngày"]), "note": str(r["Ghi chú"])} for r in df.to_dict("records")
                if str(r["Ghi chú"]).strip()]
        if recs:
            sb.table("notes").insert(recs).execute()
    st.cache_data.clear()


def save_settings_bulk(df):
    """Ghi đè toàn bộ settings (dùng khi Khôi phục từ bản sao lưu)."""
    sb = _get_supabase()
    _sb_delete_all("settings", "key")
    if not df.empty:
        recs = [{"key": str(r["key"]), "value": str(r["value"])} for r in df.to_dict("records")]
        if recs:
            sb.table("settings").insert(recs).execute()
    st.cache_data.clear()


# --- ĐỒNG BỘ LỊCH WORK (Apple Calendar qua CalDAV) ---
# Tính năng phụ, không bắt buộc: thiếu ICLOUD_* trong secrets thì mục "Đồng bộ lịch Work" báo
# lỗi cấu hình khi bấm nút, phần còn lại của app vẫn chạy bình thường (khác SUPABASE_* là bắt
# buộc cho toàn app ngay từ đầu).
APP_TZ = ZoneInfo("Asia/Ho_Chi_Minh")  # cố định múi giờ hiển thị, không phụ thuộc múi giờ server

def _has_icloud_secrets():
    try:
        return bool(st.secrets.get("ICLOUD_USERNAME")) and bool(st.secrets.get("ICLOUD_APP_PASSWORD"))
    except Exception:
        return False

@st.cache_resource
def _get_caldav_client():
    return DAVClient(url="https://caldav.icloud.com/",
                      username=st.secrets["ICLOUD_USERNAME"],
                      password=st.secrets["ICLOUD_APP_PASSWORD"])

def _find_work_calendar():
    name = st.secrets.get("ICLOUD_WORK_CALENDAR", "Work")
    for cal in _get_caldav_client().principal().calendars():
        if cal.name == name:
            return cal
    return None

def sync_work_calendar(start_date, end_date):
    """Kéo appointment lịch Work trong [start_date, end_date) (kể cả sự kiện lặp lại, tự khai
    triển qua expand=True), chuẩn hoá giờ về naive local wall-clock theo APP_TZ. Mỗi lần đồng bộ
    THAY THẾ toàn bộ appointment trong đúng khoảng đã kéo về (xoá cũ trong khoảng đó rồi chèn lại
    từ CalDAV) thay vì chỉ upsert -- nhờ vậy appointment bạn đã xoá trên Apple Calendar cũng biến
    mất khỏi app ở lần đồng bộ tiếp theo, không còn tồn đọng mãi. Dùng đúng 2 mốc giờ
    (win_start/win_end) cho cả date_search() lẫn filter xoá để phạm vi xoá khớp chính xác phạm vi
    đã kéo về. Trả về (số dòng đã đồng bộ, thông báo lỗi hoặc None)."""
    if not _has_icloud_secrets():
        return 0, "Chưa cấu hình ICLOUD_USERNAME/ICLOUD_APP_PASSWORD trong secrets."
    try:
        cal = _find_work_calendar()
    except Exception as e:
        return 0, f"Không kết nối được tới iCloud: {e}"
    if cal is None:
        return 0, f"Không tìm thấy lịch '{st.secrets.get('ICLOUD_WORK_CALENDAR', 'Work')}' trong tài khoản."
    win_start = datetime.combine(start_date, datetime.min.time())
    win_end = datetime.combine(end_date, datetime.min.time())
    events = cal.date_search(start=win_start, end=win_end, expand=True)
    # Dedupe theo (uid, start_time) TRƯỚC khi ghi -- với khoảng ngày dài, CalDAV có thể trả trùng
    # lặp cho sự kiện lặp lại (vd sự kiện gốc và occurrence đã sửa cùng rơi vào 1 mốc giờ sau khi
    # chuẩn hoá), nếu chèn thô sẽ vỡ khoá chính (uid, start_time) ngay trong cùng 1 lô insert.
    seen = set()
    recs = []
    for ev in events:
        comp = ev.icalendar_component
        dtstart = comp.get('DTSTART').dt
        if isinstance(dtstart, datetime) and dtstart.tzinfo is not None:
            dtstart = dtstart.astimezone(APP_TZ).replace(tzinfo=None)
        title = str(comp.get('SUMMARY', '')).strip()
        if not title:
            continue
        uid, start_s = str(comp.get('UID')), _fmt_ts(dtstart)
        key = (uid, start_s)
        if key in seen:
            continue
        seen.add(key)
        recs.append({"uid": uid, "start_time": start_s, "title": title})
    sb = _get_supabase()
    # Xoá TRƯỚC khi chèn -- nếu chèn trước rồi mới xoá theo khoảng thì sẽ xoá luôn dòng vừa chèn.
    sb.table("work_calendar").delete() \
        .gte("start_time", _fmt_ts(win_start)).lt("start_time", _fmt_ts(win_end)).execute()
    # upsert (không phải insert thô) -- lớp an toàn bổ sung phòng khi vẫn còn sót dòng trùng
    # khoá chính do lệch thời điểm xoá/chèn (đồng bộ 2 lần gần nhau, v.v.).
    for i in range(0, len(recs), 500):
        sb.table("work_calendar").upsert(recs[i:i + 500], on_conflict="uid,start_time").execute()
    st.cache_data.clear()
    return len(recs), None

@st.cache_data
def load_work_calendar():
    sb = _get_supabase()
    res = sb.table("work_calendar").select("start_time,title").execute()
    cols = ["Thời gian bắt đầu", "Tiêu đề"]
    if not res.data:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(res.data).rename(columns={"start_time": "Thời gian bắt đầu", "title": "Tiêu đề"})
    df["Thời gian bắt đầu"] = pd.to_datetime(df["Thời gian bắt đầu"], format='ISO8601')
    return df[cols]

def save_work_calendar_bulk(df):
    """Ghi đè toàn bộ (dùng khi Khôi phục từ bản sao lưu). File sao lưu không có cột uid gốc
    (load_work_calendar() không xuất uid) nên sinh uid tạm theo thứ tự dòng -- lần "Đồng bộ lịch
    Work" thật tiếp theo sẽ tự chèn lại đúng uid gốc từ CalDAV bên cạnh các dòng phục hồi này;
    chấp nhận đánh đổi này vì Khôi phục là thao tác hiếm, không phải luồng chính."""
    sb = _get_supabase()
    _sb_delete_all("work_calendar", "uid")
    if not df.empty:
        recs = [{"uid": f"restored-{i}", "start_time": _fmt_ts(r["Thời gian bắt đầu"]), "title": str(r["Tiêu đề"])}
                for i, r in enumerate(df.to_dict("records")) if str(r["Tiêu đề"]).strip()]
        for i in range(0, len(recs), 500):
            sb.table("work_calendar").insert(recs[i:i + 500]).execute()
    st.cache_data.clear()


# --- ĐỌC SÁCH / GUNDAM (từ Apple Reminders qua Shortcuts, xem parse_reading_log_shortcut_csv) ---
# Mỗi Reminder List = 1 cuốn sách/series (tên "Tác giả - Tên sách" hoặc "Gundam - Tên series"),
# mỗi Reminder đã hoàn thành trong list đó = 1 phần/chương/tập đã đọc/xem. Trước đây thử đồng bộ
# thẳng qua CalDAV nhưng Reminder List lưu "Trên iPhone của tôi" (không nằm iCloud) sẽ không bao
# giờ thấy được qua CalDAV -- đã bỏ hẳn nhánh đó, chỉ còn tải file Shortcut xuất (đọc thẳng dữ
# liệu trên máy nên thấy đủ, không phân biệt iCloud/cục bộ).

def _book_title(list_name):
    """"Tác giả - Tên sách" -> "Tên sách": tách theo '-' ĐẦU TIÊN, ưu tiên " - " (có khoảng
    trắng, đúng quy ước người dùng), fallback '-' trần nếu list đặt tên không chuẩn. Không có
    dấu '-' nào -> coi cả tên là tiêu đề. Cũng dùng cho list Gundam ("Gundam - Tên series" ->
    "Tên series")."""
    s = str(list_name).strip()
    if ' - ' in s:
        return s.split(' - ', 1)[1].strip()
    if '-' in s:
        return s.split('-', 1)[1].strip()
    return s


def _is_gundam_list(list_name):
    """Reminder List series Gundam (không phải sách) được đặt tên "Gundam - Tên series" theo
    quy ước -- nhận diện qua tiền tố "gundam" (không phân biệt hoa/thường) để loại khỏi tab
    Sách và đưa vào tab Gundam riêng."""
    return str(list_name).strip().lower().startswith('gundam')


@st.cache_data
def load_reading_log():
    sb = _get_supabase()
    res = sb.table("reading_log").select("uid,completed_date,book,title").execute()
    cols = ["Ngày hoàn thành", "Sách (gốc)", "Tiêu đề phần"]
    if not res.data:
        return pd.DataFrame(columns=cols + ["Cuốn sách"])
    df = pd.DataFrame(res.data).rename(columns={
        "completed_date": "Ngày hoàn thành", "book": "Sách (gốc)", "title": "Tiêu đề phần"})
    df["Ngày hoàn thành"] = pd.to_datetime(df["Ngày hoàn thành"], format='ISO8601')
    df["Cuốn sách"] = df["Sách (gốc)"].map(_book_title)
    return df[cols + ["Cuốn sách"]]

def save_reading_log_bulk(df):
    """Ghi đè toàn bộ (dùng khi Khôi phục từ bản sao lưu, hoặc khi tải file Shortcut ở mục "Tải
    lên từ Reminder") -- y hệt save_work_calendar_bulk: sinh uid tạm theo thứ tự dòng."""
    sb = _get_supabase()
    _sb_delete_all("reading_log", "uid")
    if not df.empty:
        recs = [{"uid": f"restored-{i}", "completed_date": _fmt_ts(r["Ngày hoàn thành"]),
                 "book": str(r["Sách (gốc)"]), "title": str(r["Tiêu đề phần"])}
                for i, r in enumerate(df.to_dict("records")) if str(r["Tiêu đề phần"]).strip()]
        for i in range(0, len(recs), 500):
            sb.table("reading_log").insert(recs[i:i + 500]).execute()
    st.cache_data.clear()


def parse_reading_log_shortcut_csv(uploaded):
    """Đọc file do Shortcut "Xuất tiến độ đọc" (xem tab Hướng dẫn) tạo ra -- đây là nguồn DUY
    NHẤT để nạp dữ liệu Đọc sách/Gundam vào app (không còn nhánh CalDAV, vì CalDAV chỉ đọc được
    Reminder List đã lưu trong iCloud, còn Shortcuts đọc thẳng dữ liệu trên máy nên thấy đủ cả
    list "Trên iPhone của tôi"). Định dạng: mỗi dòng "list|title|completed_date" (dấu '|'), dòng đầu là
    header đúng 3 tên cột trên. KHÔNG dùng pd.read_csv(sep='|') vì tiêu đề reminder (vd tiêu đề
    copy nguyên từ 1 video YouTube) có thể tự chứa dấu '|' -- 1 dòng dữ liệu thật đã gặp đúng ca
    này (link ...FULL MOVIE | Daniel Defoe | Classic Literature Adventure - YouTube) khiến
    read_csv 'Expected 3 fields, saw 6' và crash cả file. Tách thủ công: '|' ĐẦU tiên tách
    "list" (tên list tự đặt, không chứa '|'), '|' CUỐI tách "completed_date" (định dạng ngày
    giờ cố định, không chứa '|'), phần CÒN LẠI ở giữa luôn là "title" dù có bao nhiêu dấu '|'.
    Trả về (df, stats, missing_cols) cùng khuôn cột (Ngày hoàn thành, Sách (gốc), Tiêu đề phần)
    mà save_reading_log_bulk() cần -- gọi thẳng hàm đó sau khi người dùng xác nhận, y hệt luồng
    Khôi phục từ bản sao lưu."""
    raw = uploaded.read() if hasattr(uploaded, 'read') else uploaded
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    lines = raw.splitlines()
    cols = ['Ngày hoàn thành', 'Sách (gốc)', 'Tiêu đề phần']
    need = ['list', 'title', 'completed_date']
    if not lines:
        return pd.DataFrame(columns=cols), {'raw': 0, 'valid': 0}, need
    header = [h.strip() for h in lines[0].split('|')]
    missing = [c for c in need if c not in header]
    if missing:
        return pd.DataFrame(columns=cols), {'raw': len(lines) - 1, 'valid': 0}, missing
    rows = []
    for line in lines[1:]:
        if not line.strip() or line.count('|') < 2:
            continue
        book, rest = line.split('|', 1)
        title, completed = rest.rsplit('|', 1)
        rows.append({'Sách (gốc)': book, 'Tiêu đề phần': title, 'Ngày hoàn thành': completed})
    stats = {'raw': len(lines) - 1}
    df = pd.DataFrame(rows, columns=['Sách (gốc)', 'Tiêu đề phần', 'Ngày hoàn thành'])
    df['Ngày hoàn thành'] = pd.to_datetime(df['Ngày hoàn thành'], format='ISO8601', errors='coerce')
    df = df[df['Ngày hoàn thành'].notna() & df['Sách (gốc)'].astype(str).str.strip().ne('')
            & (df['Tiêu đề phần'].astype(str).str.strip() != '')]
    stats['valid'] = len(df)
    return df[cols].reset_index(drop=True), stats, []


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
    # KHÔNG early-return pd.DataFrame() khi db rỗng: load_db() đã tự đảm bảo db rỗng vẫn CÓ
    # cột (['Thời gian bắt đầu','Thời gian kết thúc','Dự án','Thời lượng (Phút)']), nên để hàm
    # chạy tiếp bình thường trên db rỗng-có-cột (merge/to_datetime/.dt an toàn trên Series rỗng)
    # -> kết quả rỗng nhưng vẫn đủ cột, tránh KeyError ở các trang đọc df['Dự án']/df['Danh mục']
    # ngay cả khi người dùng chưa từng tải CSV Forest (vd chỉ có dữ liệu đọc sách từ Reminders).
    
    if not mapping.empty:
        db = db.merge(mapping, on='Dự án', how='left')
        # Cờ "có phân loại thật" (trước khi fillna) -> phân biệt với trường hợp tên
        # Danh mục trùng tên Dự án. Không suy ra bằng so sánh tên ở nơi hiển thị.
        db['Có danh mục'] = db['Danh mục'].notna() & (db['Danh mục'].astype(str).str.strip() != '')
        db['Danh mục'] = db['Danh mục'].fillna(db['Dự án'])
    else:
        db['Có danh mục'] = False
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
        # r=28: chừa chỗ cho nhãn trục hoành CUỐI (vd '28/06') -> không bị tràn/cắt chữ ở
        # mép phải canvas, vì nhãn căn giữa cột cuối nên phần nửa sau dễ vượt khỏi biên vẽ.
        margin=dict(t=10, r=28),
        xaxis=dict(automargin=True),
    )
    if is_pie:
        # Đường viền trắng phân tách các miếng cho gọn (bóng cả vòng thêm bằng CSS g.pielayer)
        fig.update_traces(marker=dict(line=dict(color='#ffffff', width=2)),
                          hovertemplate='<b>%{label}</b><br>%{value:.1f} giờ<extra></extra>')
    else:
        fig.update_traces(hovertemplate='<b>%{data.name}</b><br>%{y:.1f} giờ<extra></extra>')
        # Bo góc TRÊN cột (góc dưới phẳng ở trục); cliponaxis=False để bóng (CSS g.barlayer)
        # không bị cắt ở đỉnh cột. Chỉ áp cho trace cột, line/scatter không ảnh hưởng.
        fig.update_traces(marker_cornerradius=6, cliponaxis=False, selector=dict(type='bar'))
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

def period_label(key, multiyear=False):
    """Nhãn cột/dòng kỳ gọn cho bảng số liệu: '2026-W14' -> 'W14'; '2026-05' -> 'Th5'.
    Khi multiyear=True (danh sách kỳ đang hiển thị trải hơn 1 năm dương lịch), thêm hậu tố
    năm 2 số (vd 'Th1 ’26') để không nhầm giữa các kỳ trùng số nhưng khác năm -- cùng kiểu
    hậu tố '’YY' đã dùng ở trục timeline đọc sách (rtl-yr)."""
    key = str(key)
    suffix = f" ’{key.split('-')[0][-2:]}" if multiyear else ""
    if 'W' in key:                       # '2026-W14' -> 'W14'
        return 'W' + key.split('W')[-1] + suffix
    parts = key.split('-')               # '2026-05'  -> 'Th5'
    return f"Th{int(parts[-1])}{suffix}" if len(parts) >= 2 else key


def _periods_multiyear(keys):
    """True nếu danh sách khoá kỳ (vd '2026-05', '2026-W14') trải hơn 1 năm dương lịch
    -> period_label() cần thêm năm để tránh nhầm lẫn (vd hai 'Th1' của hai năm khác nhau)."""
    return len({str(k).split('-')[0] for k in keys}) > 1

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
    """Chọn ngày: ◀ ▶ nhảy tới ngày CÓ hoạt động liền kề + lịch chọn ngày + nút ngày gần nhất.
    Đọc query param ?day=YYYY-MM-DD 1 lần khi session mới (giống hệt cách "nav" đã làm ở
    st.query_params["nav"]) -- cho phép link từ Nhật ký (tuần/tháng) nhảy thẳng tới đúng ngày."""
    pk = "day_pick"
    lo, hi = active_days[0], active_days[-1]
    if pk not in st.session_state:
        _qd = st.query_params.get("day")
        _parsed = None
        if _qd:
            try:
                _parsed = date.fromisoformat(_qd)
            except ValueError:
                _parsed = None
        st.session_state[pk] = _parsed if _parsed else hi
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


def render_stat_panel(hero_items, sections=None, footer=None, groups=None, card_style="padding:20px;"):
    """Bảng tổng quan gọn: 1 thẻ gồm hàng số lớn (hero) + các nhóm 'chip' phụ.

    hero_items: list dict {label, value, deltas?: [(text, color)]}; rỗng -> bỏ hàng hero.
    sections:   list dict {label, chips: [{k, v, delta?: (text, color), hl?: bool}]}
    footer:     (text, bg, fg) -> dòng nhắn nằm cuối thẻ (vd lời nhắc chuỗi)
    groups:     list dict {label?: str, sections: [...]} — nhóm nhiều sections với divider;
                nếu truyền thì sections bị bỏ qua.
    card_style: style inline cho thẻ ngoài (vd thêm margin-top để tách thẻ).
    Toàn bộ HTML viết sát lề trái để Streamlit không hiểu nhầm là code block.
    """
    def _render_sec(sec):
        chips = sec.get('chips') or []
        if not chips:
            return ''
        out = f"<div class='sp-row'><div class='sp-sub'>{sec['label']}</div><div class='sp-chips'>"
        for c in chips:
            cls = "chip tw" if c.get('hl') else "chip"
            out += f"<span class='{cls}'><span class='ck'>{c['k']}</span><span class='cv'>{c['v']}</span>"
            if c.get('delta'):
                dt, dc = c['delta']
                out += f"<span class='cd' style='color:{dc};'>{dt}</span>"
            out += "</span>"
        out += "</div></div>"
        return out

    h = f"<div class='glass-card stat-panel' style='{card_style}'>"
    if hero_items:
        h += "<div class='sp-hero'>"
        for it in hero_items:
            h += f"<div class='sp-hi'><div class='sp-l'>{it['label']}</div><div class='sp-v'>{it['value']}</div>"
            for txt, col in it.get('deltas', []) or []:
                h += f"<div class='sp-d' style='color:{col};'>{txt}</div>"
            h += "</div>"
        h += "</div>"
    if groups is not None:
        first = True
        for grp in groups:
            grp_secs = [s for s in (grp.get('sections') or []) if s.get('chips')]
            if not grp_secs:
                continue
            if not first:
                h += "<div class='sp-divider'></div>"
            first = False
            if grp.get('label'):
                h += f"<div class='sp-glabel'>{grp['label']}</div>"
            for sec in grp_secs:
                h += _render_sec(sec)
    else:
        for sec in (sections or []):
            h += _render_sec(sec)
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
            wsuf = f" <span style='color:{ACCENT}; font-size:13px;'>({wh:.1f}h tuần này)</span>" if wh > 0.05 else ""
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
_SESSION_COLORS = _teal_shades(5)
SESSION_BUCKETS = [
    ("Tối thiểu", "= 10′",  0,   11,    _SESSION_COLORS[0]),
    ("Ngắn",      "< 25′",  11,  25,    _SESSION_COLORS[1]),
    ("Trung bình","25–<50′",25,  50,    _SESSION_COLORS[2]),
    ("Dài",       "50–<90′",50,  90,    _SESSION_COLORS[3]),
    ("Rất Dài",   "≥ 90′",  90,  10**9, _SESSION_COLORS[4]),
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
        fg = "#fff" if col in _SESSION_COLORS[3:] else "#1d1d1f"
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
        marker_cornerradius=6, cliponaxis=False,  # bo góc trên + bóng (CSS) không bị cắt — đồng bộ các cột khác
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
    fig.update_layout(xaxis_title=x_title, yaxis_title="Trung bình giờ/ngày",
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
    """Bản đồ nhiệt 7 thứ × 24 giờ: ô càng đậm = trung bình giờ/ngày (chỉ tính ngày CÓ
    hoạt động ở đúng thứ đó) ở khung giờ đó của thứ đó càng cao -> nhận ra 'tập trung tốt
    nhất vào sáng thứ mấy' mà không bị pha loãng bởi các ngày trống trong khoảng xem."""
    if scope_df.empty:
        return
    d = _explode_session_hours(scope_df, 'Thứ')
    if d.empty:
        return
    wd_count = scope_df.groupby('Thứ')['Ngày'].nunique()

    grp = d.groupby(['Thứ', 'Khung giờ'])['giờ'].sum()
    full = pd.MultiIndex.from_product([DAYS_ORDER, range(24)], names=['Thứ', 'Khung giờ'])
    cell = grp.reindex(full, fill_value=0.0).reset_index(name='giờ')
    cell['TB'] = cell.apply(lambda r: r['giờ'] / max(int(wd_count.get(r['Thứ'], 1)), 1), axis=1)

    # Thứ ra trục ngang (nhãn ở trên), giờ xuống trục dọc (nhãn mỗi 2h) -> lưới cao, hẹp
    # Step rộng hơn (54 thay vì 46) để có chỗ cho chữ trục to hơn mà không bị chật/đè nhau.
    chart = alt.Chart(cell).mark_rect(cornerRadius=2).encode(
        x=alt.X('Thứ:O', sort=DAYS_ORDER, title='',
                axis=alt.Axis(labelAngle=0, orient='top', tickSize=0, domain=False, labelFontSize=12)),
        y=alt.Y('Khung giờ:O', title='Khung giờ (0h - 23h)',
                axis=alt.Axis(values=list(range(0, 24, 2)), tickSize=0, domain=False,
                               labelFontSize=12, titleFontSize=12)),
        # Đầu nhạt lấy từ cùng dải _teal_shades (khớp tông với Biểu đồ lịch) thay vì xám
        # trung tính -> cả dải đều là sắc teal, không bị xỉn/xám ở vùng giá trị thấp.
        color=alt.Color('TB:Q', scale=alt.Scale(range=[_teal_shades(7)[0], _teal_shades(7)[-1]]), legend=None),
        tooltip=[alt.Tooltip('Thứ:N'), alt.Tooltip('Khung giờ:O', title='Giờ'),
                 alt.Tooltip('TB:Q', title='TB giờ/ngày', format='.2f')],
    ).properties(width=alt.Step(54), height=alt.Step(26), background='white').configure_view(strokeWidth=0)
    # width='content' (không 'stretch') -> tôn trọng alt.Step nên ô không bị kéo dài, tự căn giữa thẻ
    # background='white' ở properties(): Vega tự vẽ nền riêng cho SVG (mặc định ăn theo màu nền
    # trang, không phải trắng) -> nếu không ép, phần "ở giữa" (canvas SVG) sẽ lệch tông với phần
    # đệm/viền thẻ trắng bao quanh (CSS chỉ chỉnh được phần đệm, không chỉnh được nền SVG).
    st.altair_chart(chart, width='content')


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


NUDGE_TONES = {"good": (f"rgba({ACCENT_RGB},0.12)", ACCENT_DARK),  # đồng bộ accent
               "warn": ("rgba(255,149,0,0.15)", "#a85d00"),      # cam (giữ nguyên, tránh nhầm với "good")
               "neutral": ("rgba(255,59,48,0.12)", "#c50a00")}   # đỏ (đối lập accent, chuỗi đã đứt)


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
    """Trung bình giờ mỗi ngày theo thứ, chỉ tính những ngày có hoạt động (bỏ ngày trống)."""
    if scope_df.empty:
        return pd.Series(dtype=float)
    wd_count = scope_df.groupby('Thứ')['Ngày'].nunique()
    by = scope_df.groupby('Thứ')['Thời lượng (Phút)'].sum() / 60
    return (by / wd_count).reindex(DAYS_ORDER).dropna()


def _assign_gundam_sessions(gundam_sessions, rl_gundam):
    """Gán mỗi phiên Forest tag GUNDAM_TAG vào đúng series đang xem hôm đó -- Forest không có
    Dự án riêng theo từng series Gundam, chỉ 1 tag chung, nên phải suy ra. Quy tắc: mỗi ngày có
    phiên Gundam, tìm lần hoàn thành reminder (ở BẤT KỲ series nào) GẦN NHẤT về mặt thời gian
    (trước hoặc sau ngày đó) trong rl_gundam, gán cả ngày đó cho series của lần hoàn thành gần
    nhất -- dùng pd.merge_asof(direction='nearest') có sẵn trong pandas. Trả về df cùng khuôn
    cột với gundam_sessions, cột 'Dự án' được GHI ĐÈ thành tên series suy ra được."""
    if gundam_sessions.empty or rl_gundam.empty:
        return gundam_sessions.iloc[0:0]
    # .astype('datetime64[ns]') ép cả 2 vế về CÙNG độ chính xác -- pandas >=3 coi datetime64[s]
    # (từ .dt.normalize()) và datetime64[us]/[ns] (từ pd.to_datetime trên cột date) là 2 kiểu
    # khác nhau, merge_asof() sẽ ném MergeError nếu lệch nhau, không tự nới lỏng như trước.
    marks = (rl_gundam.sort_values('Ngày hoàn thành')
             .assign(_d=lambda d: d['Ngày hoàn thành'].dt.normalize().astype('datetime64[ns]'))
             .drop_duplicates('_d', keep='first')[['_d', 'Cuốn sách']]
             .sort_values('_d'))
    left = gundam_sessions.assign(
        _d=pd.to_datetime(gundam_sessions['Ngày']).astype('datetime64[ns]')).sort_values('_d')
    merged = pd.merge_asof(left, marks, on='_d', direction='nearest')
    merged['Dự án'] = merged['Cuốn sách']
    return merged.drop(columns=['_d', 'Cuốn sách'])


def render_reading_log(df_books, latest_overall, reading_log_df, recency_days=14, labels=READING_LABELS):
    """Bảng + timeline + tóm tắt cho từng cuốn sách (đọc tuần tự), GỘP 2 nguồn: phiên Forest
    (nhóm Danh mục = Reading) và phần đã đọc đồng bộ từ Apple Reminders (reading_log_df). Một
    cuốn sách chỉ cần có mặt ở MỘT trong 2 nguồn là đủ để lên bảng -- cột thuộc nguồn còn thiếu
    hiện '—'. Trạng thái Đang đọc/Đã xong dựa trên hoạt động GẦN NHẤT của CẢ 2 nguồn (lấy max
    của ngày phiên Forest gần nhất và ngày hoàn thành reminder gần nhất).
    Chỉ đọc & tính toán -> không đụng tới dữ liệu lưu trữ.

    Dùng chung cho tab "Nhật ký đọc sách" (labels=READING_LABELS, mặc định) và tab "Gundam"
    (labels=GUNDAM_LABELS) -- chỉ khác CHỮ hiển thị, tên cột nội bộ (vd 'Cuốn sách', 'Trạng
    thái') giữ nguyên bất kể labels nào đang dùng."""
    if df_books.empty and reading_log_df.empty:
        st.info(labels['empty_msg'])
        return

    forest_books = set(df_books['Dự án'].unique()) if not df_books.empty else set()
    rl_books = set(reading_log_df['Cuốn sách'].unique()) if not reading_log_df.empty else set()
    all_books = sorted(forest_books | rl_books)

    rows = []
    for book in all_books:
        g = df_books[df_books['Dự án'] == book] if book in forest_books else df_books.iloc[0:0]
        r = reading_log_df[reading_log_df['Cuốn sách'] == book] if book in rl_books else reading_log_df.iloc[0:0]
        has_forest, has_rl = not g.empty, not r.empty

        f_start = pd.to_datetime(g['Ngày']).min() if has_forest else pd.NaT
        f_last = pd.to_datetime(g['Ngày']).max() if has_forest else pd.NaT
        r_start = r['Ngày hoàn thành'].min() if has_rl else pd.NaT
        r_last = r['Ngày hoàn thành'].max() if has_rl else pd.NaT
        # "Bắt đầu"/"Gần nhất" = hoạt động sớm/muộn nhất theo CẢ 2 nguồn -- bắt buộc vậy để
        # timeline vẽ được thanh cho cả sách chỉ có nguồn Reminders (không có phiên Forest nào).
        start = min(d for d in (f_start, r_start) if pd.notna(d))
        last = max(d for d in (f_last, r_last) if pd.notna(d))

        # Số ngày = khoảng cách Bắt đầu-Gần nhất theo HỢP 2 nguồn (không chỉ has_forest) -- để
        # sách chỉ theo dõi qua Reminders (chưa bấm giờ Forest) cũng tính được số ngày đọc thay
        # vì luôn ra NaN.
        span_days = int((pd.Timestamp(last) - pd.Timestamp(start)).days) + 1
        hrs = g['Thời lượng (Phút)'].sum() / 60 if has_forest else float('nan')
        per_week = (hrs / max(span_days / 7, 1 / 7)) if has_forest else float('nan')
        ongoing = (pd.Timestamp(latest_overall) - last).days <= recency_days if pd.notna(latest_overall) else False
        rows.append({
            'Cuốn sách': book, 'Bắt đầu': start, 'Gần nhất': last,
            'Số ngày': span_days, 'Ngày đọc': g['Ngày'].nunique() if has_forest else float('nan'),
            'Tổng giờ': round(hrs, 1) if has_forest else float('nan'),
            'Số phiên': len(g) if has_forest else float('nan'),
            'Giờ/tuần': round(per_week, 1) if has_forest else float('nan'),
            'Số phần đã đọc': len(r) if has_rl else float('nan'),
            'Phần gần nhất': r.sort_values('Ngày hoàn thành').iloc[-1]['Tiêu đề phần'] if has_rl else None,
            'Trạng thái': labels['ongoing'] if ongoing else 'Đã xong',
        })
    t = pd.DataFrame(rows).sort_values('Bắt đầu').reset_index(drop=True)

    done = t[t['Trạng thái'] == 'Đã xong']
    reading = t[t['Trạng thái'] == labels['ongoing']]

    # Số liệu đầu mục: panel thẻ giống "Tổng quan", chia 3 nhóm dọc
    _today = date.today()
    s_read = _streak_stats(df_books)

    def _period_chips(scope):
        _h = scope['Thời lượng (Phút)'].sum() / 60
        _nd = scope['Ngày'].nunique()
        return [
            {"k": labels['count_label'], "v": f"{scope['Dự án'].nunique()}"},
            {"k": "Số giờ", "v": f"{_h:.1f}h"},
            {"k": "TB giờ/ngày", "v": f"{_h / _nd:.1f}h" if _nd else "—"},
        ]

    def _pace(d):
        """Nhịp đọc gần đây: chia cho số ngày CÓ đọc trong cửa sổ d ngày (không phải d),
        khớp cách tính '7 ngày gần đây' ở bảng tổng quan chính -> không bị pha loãng bởi
        các ngày không đọc trong cửa sổ."""
        _r = df_books[df_books['Ngày'] >= (_today - timedelta(days=d - 1))]
        _ad = _r['Ngày'].nunique()
        return (_r['Thời lượng (Phút)'].sum() / 60 / _ad) if _ad else 0.0

    # df_books rỗng (sách chỉ theo dõi qua Reminders, chưa từng tải CSV Forest) -> NaT arithmetic
    # sẽ lỗi, phải chặn trước (chip "% ngày có đọc" bên dưới đã tự xử "if _span else '—'").
    _span = 0 if df_books.empty else (pd.Timestamp(df_books['Ngày'].max()) - pd.Timestamp(df_books['Ngày'].min())).days + 1

    _hr = _explode_session_hours(df_books, 'Dự án').groupby('Khung giờ')['giờ'].sum()
    _sec_timeslot = {"label": labels['timeslot_label'], "chips": [
        {"k": labels['timeslot_best'], "v": f"{int(_hr.idxmax())}h"},
        {"k": "Buổi mạnh nhất", "v": f"{_hr.groupby(_buoi_of).sum().idxmax()}"},
    ]} if (len(_hr) and _hr.sum() > 0) else {"label": "", "chips": []}

    # Nhóm 1 · Tổng kết: thống kê theo đầu cuốn. done['Tổng giờ']/['Số ngày'] có thể TOÀN NaN
    # (mọi sách "Đã xong" trong kỳ đều chỉ theo dõi qua Reminders, không có phiên Forest nào)
    # -> idxmax()/idxmin() lỗi ValueError trên cột toàn NaN, phải kiểm tra .notna().any() trước.
    _grp_summary = []
    if len(done):
        _has_hrs = done['Tổng giờ'].notna().any()
        _has_days = done['Số ngày'].notna().any()
        _chips_done = [{"k": labels['count_label'], "v": f"{len(done)}"}]
        if _has_hrs:
            _chips_done.append({"k": labels['avg_hr_label'], "v": f"{done['Tổng giờ'].mean():.1f}h"})
        if _has_days:
            _chips_done.append({"k": labels['avg_days_label'], "v": f"{done['Số ngày'].mean():.0f}"})
        _grp_summary.append({"label": "Đã xong", "chips": _chips_done})
        _highlight = []
        if _has_hrs:
            top = done.loc[done['Tổng giờ'].idxmax()]
            _highlight.append({"k": "Nhiều giờ nhất", "v": f"{top['Cuốn sách']} ({top['Tổng giờ']:.1f}h)"})
        if _has_days:
            fast = done.loc[done['Số ngày'].idxmin()]
            _highlight.append({"k": labels['fastest_label'], "v": f"{fast['Cuốn sách']} ({int(fast['Số ngày'])} ngày)"})
        if _highlight:
            _grp_summary.append({"label": "Nổi bật", "chips": _highlight})
    if len(reading):
        _grp_summary.append({"label": labels['ongoing'], "chips": [
            {"k": r['Cuốn sách'],
             "v": f"{r['Tổng giờ']:.1f}h" if pd.notna(r['Tổng giờ']) else f"{int(r['Số phần đã đọc'])} {labels['part_word']}",
             "hl": True}
            for _, r in reading.iterrows()
        ]})

    _tab_overview, _tab_detail = st.tabs([":material/bar_chart: Tổng quan", ":material/search: Chi tiết"],
                                          key="rl_view_tabs")

    with _tab_overview:
        _render_reading_overview(t, df_books, _grp_summary, s_read, _span, _pace, _period_chips,
                                  _sec_timeslot, _today, labels)

    with _tab_detail:
        _render_reading_detail(t, reading_log_df, labels)


def _render_reading_overview(t, df_books, _grp_summary, s_read, _span, _pace, _period_chips,
                              _sec_timeslot, _today, labels):
    """Sub-tab "Tổng quan" của render_reading_log(): 3 thẻ hero/nhóm chip + thanh phân bổ +
    Dòng thời gian trình tự đọc + bảng "Chi tiết từng cuốn" tổng hợp toàn bộ đầu cuốn/series."""
    # Thẻ 1: hero + Tổng kết (theo đầu cuốn)
    render_stat_panel(
        hero_items=[
            {"label": labels['count_label'], "value": f"{len(t)}"},
            {"label": "Tổng giờ", "value": f"{t['Tổng giờ'].sum():.1f}h"},
            {"label": labels['parts_label'], "value": f"{int(t['Số phần đã đọc'].fillna(0).sum())}"},
        ],
        groups=[{"label": "Tổng kết", "sections": _grp_summary}],
    )

    # Thẻ 2: Hoạt động — thẻ độc lập, tách khỏi thẻ trên
    render_stat_panel(
        hero_items=[],
        groups=[{"label": "Hoạt động", "sections": [
            {"label": labels['streak_label'], "chips": [
                {"k": "Tổng số ngày", "v": f"{s_read['total']}"},
                {"k": "Dài nhất", "v": f"{s_read['longest']} ngày"},
                {"k": "Hiện tại", "v": f"{s_read['current']} ngày", "hl": True},
            ]},
            {"label": "Đều đặn", "chips": [
                {"k": labels['pace_days_label'], "v": f"{s_read['total']}"},
                {"k": labels['pace_pct_label'], "v": f"{s_read['total'] / _span * 100:.0f}%" if _span else "—"},
            ]},
            {"label": "Nhịp gần đây", "chips": [
                {"k": "7 ngày", "v": f"{_pace(7):.1f}h/ngày"},
                {"k": "30 ngày", "v": f"{_pace(30):.1f}h/ngày"},
            ]},
        ]}],
        card_style="padding:20px;margin-top:14px;",
    )

    # Thẻ 3: Kỳ này — thẻ độc lập
    render_stat_panel(
        hero_items=[],
        groups=[{"label": "Kỳ này", "sections": [
            {"label": "Tháng này", "chips": _period_chips(df_books[df_books['Tháng'] == _today.strftime('%Y-%m')])},
            {"label": "Tuần này", "chips": _period_chips(df_books[df_books['Tuần'] == _today.strftime('%G-W%V')])},
            _sec_timeslot,
        ]}],
        card_style="padding:20px;margin-top:14px;",
    )

    render_session_bar(df_books)

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

    names_html = ''.join(f'<div class="rtl-name">{html_escape(str(r["Cuốn sách"]))}</div>'
                         for _, r in t.iterrows())

    bars_html = ''
    for _, r in t.iterrows():
        left = _pct(r['Bắt đầu'])
        width = max((pd.Timestamp(r['Gần nhất']) - pd.Timestamp(r['Bắt đầu'])).days + 1, 1) / total * 100
        cls = 'reading' if r['Trạng thái'] == labels['ongoing'] else 'done'
        bars_html += (f'<div class="rtl-track">{grid_html}'
                      f'<div class="rtl-bar {cls}" style="left:{left:.3f}%;width:{width:.3f}%"></div></div>')

    # Cột tên rộng hơn (144 -> 200px) để đỡ cắt bớt tên dài. TÁCH HẲN thành 2 khối cạnh nhau
    # (KHÔNG dùng position:sticky) -- đã test thực nghiệm (isolated HTML + Playwright) xác nhận
    # sticky trên con trực tiếp của display:grid/flex KHÔNG dính khi cuộn ngang trong môi trường
    # Streamlit thật (dù CSS hợp lệ, computed style đúng "sticky", vẫn di chuyển theo scroll --
    # tái hiện được trong isolated test nhưng KHÔNG tái hiện được khi thử lại bên ngoài Streamlit,
    # nên nghi có tương tác lạ với cách Streamlit dựng DOM; không đáng để tiếp tục điều tra sâu).
    # Cột tên đứng NGOÀI vùng cuộn (không có overflow ngang) nên không cần sticky vẫn luôn hiện;
    # chỉ khối track (bên phải) có overflow-x:auto riêng, bề rộng TỐI THIỂU theo số tháng
    # (70px/tháng, tối thiểu 320px) -- càng nhiều tháng càng rộng hơn khung nhìn, tự sinh thanh
    # cuộn ngang thay vì bị nén dẹt khó đọc khi khoảng thời gian dài.
    name_w = 200
    track_min = max(len(months) * 70, 320)
    st.markdown(f"""
<style>
.rtl-card{{background:#fff;border:1px solid #d1d1d6;border-radius:16px;box-shadow:0 1px 1px rgba(0,0,0,0.02);padding:16px 24px;margin-top:14px;}}
.rtl-legend{{display:flex;gap:16px;margin:0 0 10px {name_w + 8}px;font-size:12px;color:#6e6e73;}}
.rtl-legend i{{display:inline-block;width:11px;height:11px;border-radius:3px;vertical-align:-1px;margin-right:5px;}}
.rtl-body{{display:flex;align-items:flex-start;}}
.rtl-names{{flex:0 0 {name_w}px;width:{name_w}px;}}
.rtl-name{{height:32px;display:flex;align-items:center;font-size:13px;font-weight:600;color:#1d1d1f;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:8px;}}
.rtl-scroll{{flex:1 1 auto;overflow-x:auto;min-width:0;}}
.rtl-track{{position:relative;height:32px;min-width:{track_min}px;}}
.rtl-grid{{position:absolute;top:0;bottom:0;width:1px;background:rgba(0,0,0,0.05);}}
.rtl-bar{{position:absolute;top:7px;height:18px;border-radius:6px;min-width:6px;box-shadow:0 1px 3px rgba(0,0,0,0.18);}}
.rtl-bar.done{{background:#aeaeb2;}}
.rtl-bar.reading{{background:{ACCENT};}}
.rtl-ticks{{position:relative;height:16px;min-width:{track_min}px;margin-top:3px;}}
.rtl-tick{{position:absolute;font-size:11px;color:#86868b;white-space:nowrap;}}
.rtl-yr{{color:#c7c7cc;margin-left:1px;}}
</style>
<div class="rtl-card">
<div class="card-label">Dòng thời gian</div>
<div class="rtl-legend"><span><i style="background:{ACCENT};"></i>{labels['ongoing']}</span><span><i style="background:#aeaeb2;"></i>Đã xong</span></div>
<div class="rtl-body">
<div class="rtl-names">{names_html}</div>
<div class="rtl-scroll">
{bars_html}
<div class="rtl-ticks">{axis_html}</div>
</div>
</div>
</div>
""", unsafe_allow_html=True)

    # Bảng số liệu: dùng cùng style (DTBL) với mục 5 "Bảng số liệu". Cột thuộc nguồn Forest
    # (Số ngày/Ngày đọc/Tổng giờ/Số phiên/Giờ tuần) hoặc nguồn Reminders (Số phần đã đọc/Phần
    # gần nhất) có thể NaN nếu sách đó chỉ có 1 trong 2 nguồn -- hiện '—' thay vì để lọt "nan"
    # ra HTML (đặc biệt _heat_cell KHÔNG tự bắt được NaN, phải bọc rõ ràng trước khi gọi).
    def _c(v, fmt='{:.0f}'):
        return fmt.format(v) if pd.notna(v) else '—'

    vmax_h = float(t['Tổng giờ'].max()) if t['Tổng giờ'].notna().any() else 0.0
    rows_html = ''
    for _, r in t.iterrows():
        s_col = ACCENT if r['Trạng thái'] == labels['ongoing'] else '#86868b'
        start_s = pd.to_datetime(r['Bắt đầu']).strftime('%d/%m/%Y')
        last_s = pd.to_datetime(r['Gần nhất']).strftime('%d/%m/%Y')
        rows_html += '<tr class="prow">'
        rows_html += f'<td class="lbl">{html_escape(str(r["Cuốn sách"]))}</td>'
        rows_html += f'<td>{start_s}</td><td>{last_s}</td>'
        rows_html += f'<td>{_c(r["Số ngày"])}</td><td>{_c(r["Ngày đọc"])}</td>'
        rows_html += _heat_cell(float(r['Tổng giờ']), vmax_h) if pd.notna(r['Tổng giờ']) else '<td>—</td>'
        rows_html += f'<td>{_c(r["Số phiên"])}</td><td>{_c(r["Giờ/tuần"], "{:.1f}")}</td>'
        rows_html += f'<td>{_c(r["Số phần đã đọc"])}</td>'
        _pn = html_escape(str(r["Phần gần nhất"])) if pd.notna(r["Phần gần nhất"]) else '—'
        rows_html += f'<td class="txt">{_pn}</td>'
        rows_html += f'<td class="txt" style="color:{s_col};font-weight:600;">{r["Trạng thái"]}</td>'
        rows_html += '</tr>'
    st.markdown(DTBL_CSS + f"""
<div class="dtbl-wrap" style="margin-top:14px;">
<div class="card-label" style="padding:14px 16px 0;margin:0 0 8px;">{labels['detail_label']}</div>
<table class="dtbl">
<thead><tr><th class="lbl">{labels['item_col']}</th><th>Bắt đầu</th><th>Gần nhất</th><th>Số ngày</th><th>{labels['days_label']}</th><th>Tổng giờ</th><th>Số phiên</th><th>Giờ/tuần</th><th>{labels['parts_label']}</th><th class="txt">{labels['part_recent_label']}</th><th class="txt">Trạng thái</th></tr></thead>
<tbody>{rows_html}</tbody>
</table></div>
""", unsafe_allow_html=True)


def _render_reading_detail(t, reading_log_df, labels):
    """Sub-tab "Chi tiết" của render_reading_log(): chọn 1 cuốn/series rồi hiện 4 mục đánh số
    -- 1. Số liệu (hero chip, tái dùng render_stat_panel), 2. Nhật ký đọc (_reading_rows_html),
    3. Biểu đồ lịch (tô theo SỐ PHẦN/tập trong ngày, không phải giờ), 4. Bảng số liệu (từng
    ngày, heat cell theo _heat_cell). Dùng chung được cho cả Sách lẫn Gundam qua labels."""
    _detail_opts = ["— Chọn để xem chi tiết —"] + sorted(t['Cuốn sách'].tolist())
    _detail_sel = st.selectbox(f"Chọn 1 {labels['item_col'].lower()}",
                                _detail_opts, key=f"rl_detail_{labels['item_col']}")
    if _detail_sel == _detail_opts[0]:
        st.info(f"Chọn 1 {labels['item_col'].lower()} ở trên để xem chi tiết.")
        return

    _row = t[t['Cuốn sách'] == _detail_sel].iloc[0]
    _rl_detail = reading_log_df[reading_log_df['Cuốn sách'] == _detail_sel]

    with st.expander("1. Số liệu", expanded=True):
        _secs = [{"label": "Mốc thời gian", "chips": [
            {"k": "Bắt đầu", "v": pd.Timestamp(_row['Bắt đầu']).strftime('%d/%m/%Y')},
            {"k": "Gần nhất", "v": pd.Timestamp(_row['Gần nhất']).strftime('%d/%m/%Y')},
            {"k": "Số ngày", "v": f"{int(_row['Số ngày'])}" if pd.notna(_row['Số ngày']) else "—"},
        ]}]
        _nhip = []
        if pd.notna(_row['Giờ/tuần']):
            _nhip.append({"k": "Giờ/tuần", "v": f"{_row['Giờ/tuần']:.1f}h"})
        if pd.notna(_row['Tổng giờ']) and pd.notna(_row['Số ngày']) and _row['Số ngày']:
            _nhip.append({"k": "TB giờ/ngày", "v": f"{_row['Tổng giờ'] / _row['Số ngày']:.1f}h"})
        if _nhip:
            _secs.append({"label": "Nhịp độ", "chips": _nhip})
        _tt = [{"k": "Hiện tại", "v": _row['Trạng thái'], "hl": _row['Trạng thái'] == labels['ongoing']}]
        if pd.notna(_row['Phần gần nhất']):
            _tt.append({"k": labels['part_recent_label'], "v": str(_row['Phần gần nhất'])})
        _secs.append({"label": "Trạng thái", "chips": _tt})

        render_stat_panel(
            hero_items=[
                {"label": "Tổng giờ", "value": f"{_row['Tổng giờ']:.1f}h" if pd.notna(_row['Tổng giờ']) else "—"},
                {"label": labels['parts_label'], "value": f"{int(_row['Số phần đã đọc'])}" if pd.notna(_row['Số phần đã đọc']) else "—"},
            ],
            sections=_secs,
        )

    with st.expander("2. Nhật ký đọc", expanded=True):
        if not _rl_detail.empty:
            with st.container(border=True, key="jcard_reading_detail"):
                st.markdown(f"<div class='jrows'>{_reading_rows_html(_rl_detail, label_book=False)}</div>",
                            unsafe_allow_html=True)
        else:
            st.caption(f"Chưa có {labels['days_label'].lower()} nào từ Reminders cho mục này.")

    with st.expander("3. Biểu đồ lịch", expanded=False):
        if not _rl_detail.empty:
            render_reading_calendar_grid(_rl_detail, labels)
        else:
            st.caption("Chưa có dữ liệu để vẽ biểu đồ lịch.")

    with st.expander("4. Bảng số liệu", expanded=False):
        if not _rl_detail.empty:
            _day_tbl = (_rl_detail.assign(_d=_rl_detail['Ngày hoàn thành'].dt.normalize())
                        .groupby('_d').size().reset_index(name='n').sort_values('_d', ascending=False))
            _vmax = float(_day_tbl['n'].max()) if not _day_tbl.empty else 0.0
            _rows = ''
            for _, r in _day_tbl.iterrows():
                _wd = VN_DAYS.get(pd.Timestamp(r['_d']).day_name(), '')
                _rows += '<tr class="prow">'
                _rows += f'<td class="lbl">{r["_d"]:%d/%m/%Y}</td><td class="txt">{_wd}</td>'
                _rows += _heat_cell(float(r['n']), _vmax)
                _rows += '</tr>'
            st.markdown(DTBL_CSS + f"""
<div class="dtbl-wrap">
<table class="dtbl">
<thead><tr><th class="lbl">Ngày</th><th class="txt">Thứ</th><th>{labels['parts_label']}</th></tr></thead>
<tbody>{_rows}</tbody>
</table></div>
""", unsafe_allow_html=True)
        else:
            st.caption("Chưa có dữ liệu để hiện bảng.")


def render_reading_calendar_grid(rl_detail_df, labels):
    """Lưới lịch nhiệt kiểu GitHub cho 1 cuốn/series đã chọn (mục "3. Biểu đồ lịch" trong sub-tab
    Chi tiết) -- tô theo SỐ PHẦN/tập đọc/xem trong ngày, khác render_calendar_grid (tô theo giờ
    tập trung): bậc màu nhỏ hơn (0-5) vì số phần/ngày thường là số nguyên nhỏ, không phải giờ."""
    day_counts = rl_detail_df.assign(_d=rl_detail_df['Ngày hoàn thành'].dt.normalize()).groupby('_d').size()
    min_date, max_date = day_counts.index.min(), day_counts.index.max()
    start = min_date - pd.Timedelta(days=min_date.dayofweek)
    end = max_date + pd.Timedelta(days=6 - max_date.dayofweek)
    cal_data = pd.DataFrame({'Ngày': pd.date_range(start=start, end=end)})
    cal_data['Tuần_Bắt_Đầu'] = cal_data['Ngày'] - pd.to_timedelta(cal_data['Ngày'].dt.dayofweek, unit='D')
    cal_data['Thứ'] = cal_data['Ngày'].dt.day_name().map(VN_DAYS)
    cal_data[labels['parts_label']] = cal_data['Ngày'].map(day_counts).fillna(0).astype(int)
    cal_data['day'] = cal_data['Ngày'].dt.day

    def _lvl(n):
        return 0 if n <= 0 else min(int(n), 5)
    cal_data['lvl'] = cal_data[labels['parts_label']].map(_lvl)
    LVL_COLORS = ["#e5e5ea"] + _teal_shades(5)

    enc_x = alt.X('yearmonthdate(Tuần_Bắt_Đầu):O', title='',
                  axis=alt.Axis(labelAngle=0, orient='top', tickSize=0, domain=False,
                                labelExpr="month(datum.value) != month(datum.value - 7*24*60*60*1000) ? 'Th' + (month(datum.value)+1) : ''"))
    enc_y = alt.Y('Thứ:O', sort=DAYS_ORDER, title='', scale=alt.Scale(domain=DAYS_ORDER), axis=alt.Axis(tickSize=0, domain=False))
    cal_tooltip = [alt.Tooltip('Ngày:T', format='%d-%m-%Y', title='Ngày'),
                   alt.Tooltip(f'{labels["parts_label"]}:Q', title=labels['parts_label'])]
    base = alt.Chart(cal_data).encode(x=enc_x, y=enc_y)
    rect = base.mark_rect(cornerRadius=3).encode(
        color=alt.Color('lvl:O', scale=alt.Scale(domain=list(range(6)), range=LVL_COLORS), legend=None),
        tooltip=cal_tooltip
    )
    text = base.mark_text(baseline='middle', fontSize=10).encode(
        text='day:Q',
        color=alt.condition("datum.lvl >= 4", alt.value('#ffffff'), alt.value('#a7a7ac')),
        tooltip=cal_tooltip
    )
    chart = (rect + text).properties(
        width=alt.Step(34), height=alt.Step(34),
        padding={"left": 0, "right": 64, "top": 5, "bottom": 5},
        background='white',
    ).configure_view(strokeWidth=0)
    st.altair_chart(chart, width='content')


def render_day_timeline(day_df, sel, df_all):
    """Dòng thời gian trong ngày (0–24h): khối phiên tô màu theo dự án, kèm lớp mờ
    'khung giờ điển hình của thứ này' để thấy hôm nay lệch nhịp ra sao."""
    if day_df.empty:
        return

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
.dtl-card{{background:#fff;border:1px solid #d1d1d6;border-radius:16px;box-shadow:0 1px 1px rgba(0,0,0,0.02);padding:14px 18px;margin-top:14px;}}
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


@st.fragment
def render_note_editor(day):
    """Thẻ 2 cột cho một ngày: Thứ/ngày bên trái (giống bố cục .jrows của Nhật ký tuần/tháng,
    dù ở đây chỉ có đúng 1 "dòng"), cột phải theo thứ tự cố định: chip lịch (kèm heading nhỏ
    "Lịch") → chip đọc sách/Gundam (tự nhóm+gắn nhãn theo cuốn/series qua _book_chips_html())
    → ghi chú. Mặc định chỉ hiện ghi chú đã lưu (hoặc trạng thái trống) kèm một nút; bấm nút
    mới mở trình soạn (Quill) inline với Cập nhật/Huỷ/Xoá.

    Bọc trong @st.fragment: ô soạn Quill gửi nội dung về server mỗi lần gõ phím, nếu
    không cô lập thì cả trang Báo cáo ngày chạy lại mỗi ký tự -> giao diện giật. Là
    fragment nên mỗi lần gõ chỉ phần ghi chú này vẽ lại; các st.rerun() bên dưới cũng
    chỉ rerun trong fragment (đủ vì không phần nào khác trên trang phụ thuộc ghi chú).

    Cột trái/phải dựng bằng st.columns() thật (không phải HTML tĩnh như .jrows) vì cột phải
    chứa widget Streamlit thật (Quill, nút) không thể nhét vào 1 chuỗi HTML. Bọc trong
    st.container(key="note_row") RIÊNG (không style trực tiếp lên note_card) vì note_card ở
    chế độ soạn còn có 1 st.columns() khác cho 3 nút Cập nhật/Huỷ/Xoá -- style chung theo
    note_card sẽ vô tình kẻ vạch trước nút đó. Thẻ ngoài VẪN có viền/bóng glass-card như Nhật
    ký (border=True) -- yêu cầu "bỏ khung" trước đó chỉ nói tới khung TEAL riêng bao quanh
    NỘI DUNG ghi chú đã lưu (.st-key-note_saved cũ), không phải khung của cả thẻ."""
    cur = get_note(day)
    edit_key = f"note_edit_{day}"
    quill_key = f"note_quill_{day}"

    def _enter_edit():
        # Xoá trạng thái cũ của ô soạn để khởi tạo lại đúng nội dung đang lưu
        st.session_state.pop(quill_key, None)
        st.session_state[edit_key] = True

    with st.container(border=True, key="note_card"):
        with st.container(key="note_row"):
            c_date, c_body = st.columns([1, 5])
            with c_date:
                vn_dow = VN_DAYS.get(pd.Timestamp(day).day_name(), "")
                st.markdown(f"<div class='jdate'><div class='jdowbig'>{vn_dow}</div>"
                            f"<div class='jdm'>{day:%d/%m}</div></div>", unsafe_allow_html=True)
            with c_body:
                wc = load_work_calendar()
                if not wc.empty:
                    day_events = wc[wc['Thời gian bắt đầu'].dt.date == day].sort_values('Thời gian bắt đầu')
                    if not day_events.empty:
                        chips = ''.join(
                            f"<span class='jchip'><span class='ck'>{r['Thời gian bắt đầu']:%H:%M}</span>"
                            f"<span class='cv'>{html_escape(str(r['Tiêu đề']))}</span></span>"
                            for _, r in day_events.iterrows()
                        )
                        st.markdown(f"<div style='margin-bottom:6px;'><span class='rl-book'>Lịch</span>{chips}</div>",
                                    unsafe_allow_html=True)

                rl = load_reading_log()
                if not rl.empty:
                    day_rl = rl[rl['Ngày hoàn thành'].dt.date == day]
                    if not day_rl.empty:
                        st.markdown(_book_chips_html(day_rl), unsafe_allow_html=True)

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
                    style_quill()
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


def render_notes_journal(period_key, kind):
    """Liệt kê (chỉ đọc) ghi chú + appointment lịch + phần đọc sách/Gundam của các ngày thuộc
    một kỳ (tuần/tháng) -- một dòng cho mỗi ngày có ÍT NHẤT 1 trong 3 nguồn (hợp/union), không
    chỉ giới hạn ở ngày đã có ghi chú viết tay. Mỗi dòng theo thứ tự cố định: chip Lịch (kèm
    heading nhỏ "Lịch") → chip đọc sách (tự nhóm+gắn nhãn theo từng cuốn/series qua
    _book_chips_html()) → ghi chú. Không lọc Gundam khỏi nguồn đọc sách ở đây -- đây là nhật ký
    chung của cả app, không riêng tab Sách. Ô Thứ/ngày mỗi dòng là link nhảy sang đúng Báo cáo
    ngày hôm đó.
    Dựng HTML tự thân (1 khối st.markdown duy nhất) thay vì st.columns() lặp lại -> khoảng
    cách quanh mỗi đường kẻ do CSS box model tự nhiên quyết định, không lệ thuộc chiều cao
    hàng do Streamlit tự tính (xem chú thích ở khối CSS .jrows)."""
    def _in_period(dt_series):
        return (dt_series.dt.strftime('%Y-%m') == period_key) if kind == 'month' \
            else (dt_series.dt.strftime('%G-W%V') == period_key)

    nd = load_notes()
    if not nd.empty:
        nd = nd.assign(_d=pd.to_datetime(nd['Ngày'], errors='coerce')).dropna(subset=['_d'])
        nd = nd[_in_period(nd['_d'])]

    wc = load_work_calendar()
    if not wc.empty:
        wc = wc.assign(_d=wc['Thời gian bắt đầu'].dt.normalize())
        wc = wc[_in_period(wc['_d'])]

    rl = load_reading_log()
    if not rl.empty:
        rl = rl.assign(_d=rl['Ngày hoàn thành'].dt.normalize())
        rl = rl[_in_period(rl['_d'])]

    note_days = set(nd['_d']) if not nd.empty else set()
    event_days = set(wc['_d']) if not wc.empty else set()
    reading_days = set(rl['_d']) if not rl.empty else set()
    days = sorted(note_days | event_days | reading_days)
    if not days:
        st.caption("Chưa có ghi chú, lịch hoặc phần đọc sách nào trong kỳ này.")
        return

    rows_html = ''
    for d in days:
        cal_html = ''
        if d in event_days:
            day_events = wc[wc['_d'] == d].sort_values('Thời gian bắt đầu')
            chips = ''.join(
                f"<span class='jchip'><span class='ck'>{r['Thời gian bắt đầu']:%H:%M}</span>"
                f"<span class='cv'>{html_escape(str(r['Tiêu đề']))}</span></span>"
                for _, r in day_events.iterrows()
            )
            cal_html = f"<div style='margin-bottom:6px;'><span class='rl-book'>Lịch</span>{chips}</div>"
        read_html = _book_chips_html(rl[rl['_d'] == d]) if d in reading_days else ''
        note_html = ''
        if d in note_days:
            note_html = f"<div class='note-html'>{str(nd[nd['_d'] == d].iloc[0]['Ghi chú'])}</div>"
        # Thứ/ngày là link nhảy sang đúng Báo cáo ngày hôm đó (đọc bởi initializer "day" mới
        # trong day_picker() -- xem chú thích ở đó).
        _href = f"?nav={quote('Hôm nay')}&day={d:%Y-%m-%d}"
        rows_html += (
            "<div class='jrow'>"
            f"<a class='jdate-link' href='{_href}' target='_self'>"
            f"<div class='jdate'><div class='jdowbig'>{VN_DAYS.get(d.day_name(), '')}</div>"
            f"<div class='jdm'>{d:%d/%m}</div></div></a>"
            f"<div>{cal_html}{read_html}{note_html}</div>"
            "</div>"
        )
    with st.container(border=True, key=f"jcard_journal_{kind}"):
        st.markdown(f"<div class='jrows'>{rows_html}</div>", unsafe_allow_html=True)


def _book_chips_html(day_g):
    """Chip các phần đã đọc trong 1 ngày, nhóm theo cuốn sách/series kèm nhãn tên sách (1 ngày
    có thể có phần từ nhiều cuốn). Sách LUÔN xếp trước Gundam (thứ tự Lịch -> Sách -> Gundam
    người dùng yêu cầu) -- sort ổn định theo is_gundam, giữ nguyên thứ tự gặp trong mỗi nhóm.
    Dùng chung cho render_note_editor, render_notes_journal, _reading_rows_html."""
    out = ''
    groups = list(day_g.groupby('Cuốn sách', sort=False))
    groups.sort(key=lambda kv: _is_gundam_list(kv[1]['Sách (gốc)'].iloc[0]))
    for book, g in groups:
        parts = ''.join(f"<span class='jchip'>{html_escape(str(r['Tiêu đề phần']))}</span>"
                        for _, r in g.sort_values('Ngày hoàn thành').iterrows())
        out += f"<div style='margin-bottom:6px;'><span class='rl-book'>{html_escape(book)}</span>{parts}</div>"
    return out


def _reading_rows_html(rl_df, label_book=True):
    """HTML .jrows cho các phần đã đọc (rl_df đã lọc sẵn theo kỳ/sách cần hiện) -- một dòng cho
    mỗi ngày có ≥1 phần hoàn thành. label_book=False dùng khi caller đã lọc đúng 1 cuốn (Báo
    cáo theo dự án) -- bỏ nhãn tên sách vì thừa."""
    rl = rl_df.assign(_d=rl_df['Ngày hoàn thành'].dt.normalize())
    rows_html = ''
    for d, day_g in rl.groupby('_d'):
        if label_book:
            chips_html = _book_chips_html(day_g)
        else:
            chips_html = ''.join(f"<span class='jchip'>{html_escape(str(r['Tiêu đề phần']))}</span>"
                                 for _, r in day_g.sort_values('Ngày hoàn thành').iterrows())
        _href = f"?nav={quote('Hôm nay')}&day={d:%Y-%m-%d}"
        rows_html += (
            "<div class='jrow'>"
            f"<a class='jdate-link' href='{_href}' target='_self'>"
            f"<div class='jdate'><div class='jdowbig'>{VN_DAYS.get(d.day_name(), '')}</div>"
            f"<div class='jdm'>{d:%d/%m}</div></div></a>"
            f"<div>{chips_html}</div></div>"
        )
    return rows_html


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
    # Lịch (appointment) cùng ngày/tháng ở các năm trước
    events = {}  # year -> DataFrame
    wc = load_work_calendar()
    if not wc.empty:
        wc_m = wc[(wc['Thời gian bắt đầu'].dt.month == m) & (wc['Thời gian bắt đầu'].dt.day == d)
                  & (wc['Thời gian bắt đầu'].dt.year < sel.year)]
        for y, g in wc_m.groupby(wc_m['Thời gian bắt đầu'].dt.year):
            events[int(y)] = g.sort_values('Thời gian bắt đầu')
    # Đọc sách/Gundam cùng ngày/tháng ở các năm trước
    reading = {}  # year -> DataFrame
    rl = load_reading_log()
    if not rl.empty:
        rl_m = rl[(rl['Ngày hoàn thành'].dt.month == m) & (rl['Ngày hoàn thành'].dt.day == d)
                  & (rl['Ngày hoàn thành'].dt.year < sel.year)]
        for y, g in rl_m.groupby(rl_m['Ngày hoàn thành'].dt.year):
            reading[int(y)] = g

    years = sorted(set(stats) | set(notes) | set(events) | set(reading), reverse=True)
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

    # Dựng HTML tự thân (1 khối st.markdown duy nhất) như render_notes_journal -> tránh
    # cơ chế flex/chiều cao tự tính của Streamlit làm khoảng cách quanh đường kẻ lệch nhau.
    rows_html = ''
    for y in years:
        wd = VN_DAYS.get(pd.Timestamp(date(y, m, d)).day_name(), "")
        cal_html = ''
        if y in events:
            _cchips = ''.join(
                f"<span class='jchip'><span class='ck'>{r['Thời gian bắt đầu']:%H:%M}</span>"
                f"<span class='cv'>{html_escape(str(r['Tiêu đề']))}</span></span>"
                for _, r in events[y].iterrows())
            cal_html = f"<div style='margin-bottom:6px;'><span class='rl-book'>Lịch</span>{_cchips}</div>"
        read_html = _book_chips_html(reading[y]) if y in reading else ''
        chips_html = ''
        if y in stats:
            hrs, ss = stats[y]
            avg = (hrs * 60 / ss) if ss else 0
            _chips = _chip("Giờ", f"{hrs:.1f}h") + _chip("Số phiên", f"{ss}") + _chip("TB", f"{avg:.0f}′")
            chips_html = f"<div style='margin-bottom:6px;'>{_chips}</div>"
        note_block = f"<div class='note-html'>{notes[y]}</div>" if notes.get(y) else ''
        rows_html += (
            "<div class='jrow'>"
            f"<div class='jdate'><div class='jyear'>{y}</div>"
            f"<div class='jdow'>{wd}</div><div class='jdm'>{d:02d}/{m:02d}</div></div>"
            f"<div>{cal_html}{read_html}{chips_html}{note_block}</div>"
            "</div>"
        )
    with st.container(border=True, key="jcard_otd"):
        st.markdown(f"<div class='jrows'>{rows_html}</div>", unsafe_allow_html=True)


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

    # Thang màu theo BẬC (0 / <0.5h / 0.5–1h / 1–2h / 2–3h / 3–4h / 4–6h / ≥6h) -> ngày
    # thường không bị một ngày cày khủng làm phẳng hết như thang tuyến tính cũ; nhiều bậc
    # hơn (7 thay vì 4) để phân biệt được các mức độ trung gian rõ hơn.
    def _cal_lvl(h):
        if h <= 0: return 0
        if h < 0.5: return 1
        if h < 1: return 2
        if h < 2: return 3
        if h < 3: return 4
        if h < 4: return 5
        if h < 6: return 6
        return 7
    cal_data['lvl'] = cal_data['Số giờ'].map(_cal_lvl)
    LVL_COLORS = ["#e5e5ea"] + _teal_shades(7)

    enc_x = alt.X('yearmonthdate(Tuần_Bắt_Đầu):O', title='',
                  axis=alt.Axis(labelAngle=0, orient='top', tickSize=0, domain=False,
                                labelExpr="month(datum.value) != month(datum.value - 7*24*60*60*1000) ? 'Th' + (month(datum.value)+1) : ''"))
    enc_y = alt.Y('Thứ:O', sort=DAYS_ORDER, title='', scale=alt.Scale(domain=DAYS_ORDER), axis=alt.Axis(tickSize=0, domain=False))
    cal_tooltip = [alt.Tooltip('Ngày_str:T', format='%d-%m-%Y', title='Ngày'),
                   alt.Tooltip('Số giờ:Q', format='.1f', title='Giờ')]
    base = alt.Chart(cal_data).encode(x=enc_x, y=enc_y)
    rect = base.mark_rect(cornerRadius=3).encode(
        color=alt.Color('lvl:O', scale=alt.Scale(domain=list(range(8)), range=LVL_COLORS), legend=None),
        tooltip=cal_tooltip
    )
    text = base.mark_text(baseline='middle', fontSize=10).encode(
        text='day:Q',
        # lvl 6,7 (2 bậc teal đậm nhất) đã đủ tối để cần chữ trắng, còn lại chữ xám mờ
        color=alt.condition("datum.lvl >= 6", alt.value('#ffffff'), alt.value('#a7a7ac')),
        tooltip=cal_tooltip
    )
    chart = (rect + text).properties(
        width=alt.Step(34), height=alt.Step(34),
        # padding phải bù cho vùng nhãn thứ bên trái -> lưới căn giữa trong thẻ
        padding={"left": 0, "right": 64, "top": 5, "bottom": 5},
        # Vega tự vẽ nền riêng cho SVG (mặc định ăn theo màu nền trang, không phải trắng)
        # -> ép trắng khớp với nền thẻ bọc ngoài, tránh có viền lệch tông quanh lưới.
        background='white',
    ).configure_view(strokeWidth=0)
    st.altair_chart(chart, width='content')


DTBL_CSS = """
<style>
.dtbl-wrap { overflow:auto; max-height:560px; border-radius:16px; border:1px solid #d1d1d6; background:#ffffff; box-shadow:0 1px 1px rgba(0,0,0,0.02); }
.dtbl { border-collapse:collapse; width:100%; font-size:14px; font-family:-apple-system,BlinkMacSystemFont,sans-serif; }
.dtbl th, .dtbl td { padding:4px 9px; text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }
.dtbl thead th { position:sticky; top:0; z-index:2; background:#f5f5f7; color:#86868b; font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.3px; border-bottom:1px solid rgba(0,0,0,0.1); }
.dtbl td.lbl, .dtbl th.lbl { text-align:left; position:sticky; left:0; background:#ffffff; z-index:1; }
.dtbl thead th.lbl { z-index:3; background:#f5f5f7; }
/* Header 2 hàng (khi cột trải nhiều năm): hàng năm (nhóm colspan) đứng trên, hàng nhãn kỳ
   (Tuần/Tháng) đứng dưới -- cả 2 đều "dính" khi cuộn dọc, xếp chồng đúng vị trí bằng top. */
.dtbl thead tr.yr th { top:0; font-size:10px; color:#9a9aa0; background:#eef0f2; border-bottom:1px solid rgba(0,0,0,0.06); }
.dtbl thead tr.wk th { top:22px; }
.dtbl th.yrspan { text-align:center; border-right:1px solid rgba(0,0,0,0.08); }
.dtbl th.yrspan:last-child { border-right:none; }
.dtbl thead tr.yr th.lbl { z-index:3; background:#eef0f2; }
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
    """Một ô số: <0.05 -> dấu chấm mờ; ngược lại tô nền teal theo tỉ lệ v/ref.
    drop=True -> đánh dấu ▾ đỏ (sụt mạnh so với kỳ liền trước)."""
    cls = extra_cls.strip()
    mark = "<span style='color:#ff3b30;font-size:10px;'>▾</span>" if drop else ""
    title = " title='Giảm mạnh so với kỳ trước'" if drop else ""
    if v < 0.05:
        if drop:
            return f'<td class="{cls}"{title}>{mark}</td>'
        return f'<td class="{(cls + " zero").strip()}">·</td>'
    a = min(v / ref, 1.0) * 0.7 if ref > 0 else 0
    bg = f'background:rgba({ACCENT_RGB},{a:.2f});' if a > 0.02 else ''
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

    _my = _periods_multiyear(cols)
    # Nhiều năm -> tách năm ra 1 hàng header phụ (gộp theo colspan) thay vì lặp hậu tố năm
    # ở từng cột -> đỡ rối khi có nhiều cột. period_label(c, False) vì năm đã hiện riêng.
    head = ''.join(f'<th>{period_label(c, False)}</th>' for c in cols)
    if _my:
        yr_groups = [(yr, len(list(g))) for yr, g in groupby(cols, key=lambda c: str(c).split('-')[0])]
        yr_head = ''.join(f'<th class="yrspan" colspan="{n}">{yr}</th>' for yr, n in yr_groups)
        thead_html = (f'<tr class="yr"><th class="lbl"></th>{yr_head}<th></th></tr>'
                      f'<tr class="wk"><th class="lbl">Danh mục / Dự án</th>{head}<th>Tổng</th></tr>')
    else:
        thead_html = f'<tr><th class="lbl">Danh mục / Dự án</th>{head}<th>Tổng</th></tr>'
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
<thead>{thead_html}</thead>
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

    _my = _periods_multiyear(periods)
    rows_html = ''
    for p in periods:
        rows_html += '<tr class="prow">'
        rows_html += f'<td class="lbl">{period_label(p, _my)}</td>'
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


def guide_item(img, title, body_md, tip=None, where=None):
    """Một mục trong trang Hướng dẫn: ảnh minh hoạ + giải thích chi tiết (+ mẹo)."""
    with st.container(border=True, key=f"guide_{img}"):
        if where:
            st.markdown(f"<div style='font-size:11px;font-weight:700;color:#86868b;"
                        f"text-transform:uppercase;letter-spacing:.5px;'>{where}</div>",
                        unsafe_allow_html=True)
        st.markdown(f"#### {title}")
        c1, c2 = st.columns([5, 6], vertical_alignment="top")
        with c1:
            p = os.path.join("assets", "help", img)
            if os.path.exists(p):
                st.image(p, use_container_width=True)
        with c2:
            st.markdown(body_md)
            if tip:
                st.info(tip, icon=":material/lightbulb:")


# --- FRAGMENT: cô lập rerun cho từng mục biểu đồ có bộ điều khiển riêng ---
# Khi đổi bộ lọc bên trong một mục, chỉ mục đó vẽ lại thay vì rerun cả trang
# (nhanh hơn, nhất là trang nhiều dữ liệu/khi xem trên điện thoại).
@st.fragment
def frag_calendar(scope_df, key):
    """Mục Biểu đồ lịch — bộ chọn khoảng thời gian riêng."""
    df_cal = range_radio(scope_df, key=key)
    render_calendar_grid(df_cal, df_cal)


@st.fragment
def frag_trend(scope_df, key_prefix, default_color):
    """Mục Xu hướng theo thời gian — chọn khoảng thời gian / cách gộp / phân loại."""
    o1, o2, o3 = st.columns([5, 3, 2])
    with o1:
        rl = st.segmented_control("Khoảng thời gian", list(RANGE_OPTS.keys()), default="90 ngày", key=f"{key_prefix}_range")
    with o2:
        tcol = st.segmented_control("Gộp theo", ["Ngày", "Tuần", "Tháng"], default="Ngày", key=f"{key_prefix}_time")
    with o3:
        ccol = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default=default_color, key=f"{key_prefix}_color")
    rl = rl or "90 ngày"
    tcol = tcol or "Ngày"
    ccol = ccol or default_color
    dft = filter_by_range(scope_df, rl)
    g = dft.groupby([tcol, ccol])['Thời lượng (Phút)'].sum().reset_index()
    g['Số giờ'] = g['Thời lượng (Phút)'] / 60
    if tcol == "Ngày":
        g['Ngày'] = pd.to_datetime(g['Ngày'])
    fig = render_trend_fig(g, tcol, ccol, ma_df=dft if tcol == "Ngày" else None)
    st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)


@st.fragment
def frag_hourly(scope_df, key_prefix, default_color, with_range=True):
    """Mục Xu hướng tập trung theo khung giờ — bộ điều khiển ĐỘC LẬP của riêng mục
    (khoảng thời gian nếu có + phân loại). Không dùng chung với mục nào khác."""
    if with_range:
        c1, c2 = st.columns([5, 3])
        with c1:
            rl = st.segmented_control("Khoảng thời gian", list(RANGE_OPTS.keys()), default="90 ngày", key=f"{key_prefix}_range")
        with c2:
            ccol = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default=default_color, key=f"{key_prefix}_color")
        scope_df = filter_by_range(scope_df, rl or "90 ngày")
    else:
        ccol = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default=default_color, key=f"{key_prefix}_color")
    render_hourly_chart(scope_df, ccol or default_color)


@st.fragment
def frag_pie(scope_df, key, default_color):
    """Mục Phân bổ thời gian (biểu đồ tròn) — bộ chọn Phân loại riêng."""
    ccol = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default=default_color, key=key) or default_color
    pc = scope_df.groupby(ccol)['Thời lượng (Phút)'].sum().reset_index()
    pc['Số giờ'] = pc['Thời lượng (Phút)'] / 60
    fig = px.pie(pc, values='Số giờ', names=ccol, color=ccol, color_discrete_map=COLOR_MAP)
    fig = format_plotly_fig(fig, is_pie=True)
    st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)


@st.fragment
def frag_period_trend(scope_df, key, default_color, group_col, x_title, cat_order=None):
    """Mục Xu hướng theo thời gian trong một kỳ (tháng -> theo Ngày; tuần -> theo
    Thứ) — bộ chọn Phân loại riêng. MA chỉ áp khi gộp theo Ngày (render_trend_fig)."""
    ccol = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default=default_color, key=key) or default_color
    g = scope_df.groupby([group_col, ccol])['Thời lượng (Phút)'].sum().reset_index()
    g['Số giờ'] = g['Thời lượng (Phút)'] / 60
    if group_col == 'Ngày':
        g['Ngày'] = pd.to_datetime(g['Ngày'])
    fig = render_trend_fig(g, group_col, ccol, ma_df=scope_df, cat_order=cat_order, x_title=x_title)
    st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)


@st.fragment
def frag_heatmap(scope_df, key):
    """Mục Giờ tập trung theo thứ — bộ chọn khoảng thời gian riêng."""
    df_heat = range_radio(scope_df, key=key)
    render_dayhour_heatmap(df_heat)


@st.fragment
def frag_data_table(scope_df, key_prefix):
    """Mục Bảng số liệu (Thống kê chung): khoảng thời gian + xem theo Tuần/Tháng.
    "Xem theo" mặc định thông minh theo Khoảng thời gian đang chọn (30/90 ngày -> Tuần đủ
    chi tiết mà không quá nhiều cột; 6 tháng/1 năm/Tất cả -> Tháng để tránh bảng quá nhiều
    cột hẹp) -- vẫn đổi tay được. Key riêng theo từng khoảng thời gian (không dùng chung 1
    key cố định) để mỗi khoảng nhớ đúng lựa chọn thủ công của khoảng đó, đồng thời khoảng
    mới chưa từng chọn luôn khởi tạo lại đúng mặc định thông minh thay vì kẹt theo lựa chọn
    cũ của khoảng trước."""
    cc1, cc2 = st.columns([5, 2])
    with cc1:
        range_label = st.segmented_control("Khoảng thời gian", list(RANGE_OPTS.keys()),
                                            default="90 ngày", key=f"{key_prefix}_range") or "90 ngày"
        df_tbl = filter_by_range(scope_df, range_label)
    with cc2:
        smart_default = "Tuần" if range_label in ("30 ngày", "90 ngày") else "Tháng"
        view_opt = st.segmented_control("Xem theo", ["Tuần", "Tháng"], default=smart_default,
                                         key=f"{key_prefix}_view_{range_label}")
    view_opt = view_opt or smart_default
    render_data_table(df_tbl, 'Tuần' if view_opt == "Tuần" else 'Tháng')


@st.fragment
def frag_period_table(scope_df, key):
    """Mục Bảng số liệu (Báo cáo theo dự án): xem theo Tuần/Tháng."""
    grp_view = st.segmented_control("Xem theo", ["Tuần", "Tháng"], default="Tháng", key=key)
    grp_view = grp_view or "Tháng"
    render_period_table(scope_df, 'Tuần' if grp_view == "Tuần" else 'Tháng')


# --- GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="Forest Tracker", page_icon=":material/forest:", layout="wide")

try:
    _has_supabase_secrets = bool(st.secrets.get("SUPABASE_URL")) and bool(st.secrets.get("SUPABASE_KEY"))
except Exception:
    _has_supabase_secrets = False
if not _has_supabase_secrets:
    st.error(
        "**Chưa cấu hình Supabase.** App cần `SUPABASE_URL` và `SUPABASE_KEY` trong "
        "`.streamlit/secrets.toml` (xem `.streamlit/secrets.toml.example` và mục "
        "\"Thiết lập Supabase (bắt buộc)\" trong README) để đọc/ghi dữ liệu.")
    st.stop()

st.markdown(
    f"<style>:root{{--accent:{ACCENT};--accent-rgb:{ACCENT_RGB};--accent-dark:{ACCENT_DARK};}}</style>",
    unsafe_allow_html=True,
)

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
        background: #fff;
        border: 1px solid #d1d1d6;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 1px 1px rgba(0,0,0,0.02);
    }
    
    h1, h2, h3 { color: #1d1d1f !important; font-weight: 600 !important; letter-spacing: -0.5px !important; }
    hr { border-color: rgba(0,0,0,0.08) !important; }
    
    div[data-testid="stButton"] button[kind="primary"] {
        background-color: var(--accent) !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: 500 !important;
        padding: 6px 16px !important;
        box-shadow: 0 2px 5px rgba(var(--accent-rgb),0.3) !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        transform: scale(0.98);
        opacity: 0.9;
    }
    
    div[data-testid="stButton"] button[kind="secondary"] {
        background-color: white !important;
        color: var(--accent) !important;
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
        background: #fff;
        border: 1px solid #d1d1d6;
        border-radius: 16px;
        padding: 14px;
        box-shadow: 0 1px 1px rgba(0,0,0,0.02);
    }
    /* Chart Altair width='content' (heatmap, lịch): Streamlit ép cả chuỗi wrapper
       (stElementContainer > stFullScreenFrame > div) về fit-content -> dồn trái.
       Ép chuỗi này full-width để justify-content:center của thẻ vega căn giữa biểu đồ. */
    [data-testid="stElementContainer"]:has([data-testid="stVegaLiteChart"]),
    [data-testid="stElementContainer"]:has([data-testid="stVegaLiteChart"]) [data-testid="stFullScreenFrame"],
    [data-testid="stElementContainer"]:has([data-testid="stVegaLiteChart"]) [data-testid="stFullScreenFrame"] > div { width: 100% !important; }

    /* Đổ bóng CẢ KHỐI cho cột & pie: áp lên cả group (không từng path) -> trong một cột
       các segment kề nhau hợp thành khối đặc nên chỉ ra bóng viền ngoài, không lem bên trong.
       Cần cliponaxis=False (đặt ở figure) để bóng đỉnh cột không bị clip. */
    [data-testid="stPlotlyChart"] g.barlayer { filter: drop-shadow(0 2.5px 2.5px rgba(0,0,0,0.30)); }
    [data-testid="stPlotlyChart"] g.pielayer { filter: drop-shadow(0 3px 4px rgba(0,0,0,0.30)); }

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
    .stat-panel .chip.tw { background: rgba(var(--accent-rgb),0.10); }
    .stat-panel .sp-divider { border-top: 1px solid rgba(0,0,0,0.07); margin: 10px 0 2px; }
    .stat-panel .sp-glabel { font-size: 11px; font-weight: 700; color: var(--accent); text-transform: uppercase; letter-spacing: 0.6px; margin-top: 10px; }
    .stat-panel > .sp-glabel:first-child { margin-top: 0; }
    .stat-panel .chip.tw .ck { color: var(--accent-dark); }
    .stat-panel .chip.tw .cv { color: var(--accent); }
    .section-hd { font-size: 15px; font-weight: 700; color: #1d1d1f; margin: 22px 0 6px; letter-spacing: -0.2px; }
    /* Nhãn nhóm màu xanh đặt BÊN TRONG thẻ (giống .sp-glabel) nhưng dùng độc lập, không cần
       bọc trong .stat-panel -> tái dùng cho các thẻ tự dựng HTML khác (.rtl-card, .dtbl-wrap). */
    .card-label { font-size: 11px; font-weight: 700; color: var(--accent); text-transform: uppercase; letter-spacing: 0.6px; margin: 0 0 12px; }

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
        border-bottom: 2px solid #d1d1d6 !important;
        border-radius: 0 !important;
        transition: color 0.15s ease, border-color 0.15s ease !important;
    }
    [data-testid="stExpander"] summary:hover { border-bottom-color: var(--accent) !important; }
    [data-testid="stExpander"] summary:hover svg,
    [data-testid="stExpander"] summary:hover p { color: var(--accent) !important; }
    /* Mục đang mở: viền dưới + icon chevron chuyển màu accent để dễ nhận biết đang mở dù
       không hover; giữ màu chữ mặc định để không rối mắt khi nhiều mục cùng mở. */
    [data-testid="stExpander"] details[open] > summary { border-bottom-color: var(--accent) !important; }
    [data-testid="stExpander"] details[open] > summary svg { color: var(--accent) !important; }
    [data-testid="stExpander"] summary p {
        font-size: 1.35rem !important;
        font-weight: 600 !important;
        letter-spacing: -0.4px !important;
        color: #1d1d1f !important;
    }
    [data-testid="stExpander"] [data-testid="stExpanderDetails"] { padding-top: 12px !important; }

    /* Thanh chọn trang (segmented control) căn giữa, cách nội dung một chút */
    [data-testid="stButtonGroup"] { margin-bottom: 10px; }
    /* Nút đang chọn trong mọi segmented_control (nav bar + bộ lọc biểu đồ: Khoảng thời gian,
       Phân loại, Xem theo...) -> nền màu accent đặc + chữ/icon trắng + đổ bóng, đồng bộ với
       nút primary. */
    button[kind="segmented_controlActive"] {
        background-color: var(--accent) !important;
        color: #fff !important;
        border-color: var(--accent) !important;
        box-shadow: 0 2px 5px rgba(var(--accent-rgb),0.3) !important;
    }
    /* Riêng thanh điều hướng trang: căn giữa cả hàng nút.
       Element container mặc định co theo nội dung -> ép full width rồi căn giữa. */
    .st-key-nav { width: 100% !important; }
    .st-key-nav [data-testid="stButtonGroup"] { display: flex !important; justify-content: center !important; flex-wrap: wrap !important; width: 100% !important; }

    /* Cùng ý căn giữa như thanh nav chính, áp cho thanh chọn sub-tab "Chọn kỳ xem" (Báo cáo) --
       label đã ẩn (label_visibility="collapsed") nên bố cục giống hệt .st-key-nav ở trên. Đổi
       thêm dáng nút từ pill sang tab gạch chân (giống Tổng quan/Chi tiết ở Sách/Gundam) cho gọn
       và nhất quán, thay vì nền đặc teal như nav chính. */
    .st-key-bc_sub_picker { width: 100% !important; }
    .st-key-bc_sub_picker [data-testid="stButtonGroup"] { display: flex !important; justify-content: center !important; flex-wrap: wrap !important; width: 100% !important; }
    .st-key-bc_sub_picker button {
        background: transparent !important; border: none !important; border-radius: 0 !important;
        border-bottom: 2px solid transparent !important; box-shadow: none !important;
        color: #6e6e73 !important; padding: 8px 4px !important; margin: 0 14px !important;
    }
    .st-key-bc_sub_picker button[kind="segmented_controlActive"] {
        background: transparent !important; color: var(--accent) !important; font-weight: 600 !important;
        border-bottom-color: var(--accent) !important; box-shadow: none !important;
    }
    .st-key-rl_view_tabs [data-baseweb="tab-list"] { justify-content: center !important; }
    /* st.tabs() tự vẽ thêm 1 vạch xám full-width bên dưới toàn bộ hàng tab (data-baseweb=
       "tab-border") -- không có ở "Chọn kỳ xem" (Báo cáo, dùng segmented_control tự dựng, không
       có vạch này) -- ẩn đi cho 2 giao diện đồng nhất. */
    .st-key-rl_view_tabs [data-baseweb="tab-border"] { display: none !important; }

    /* Pagination (bảng phiên) căn giữa: stPagination là flex full-width nhưng justify
       flex-start -> đẩy hàng nút vào giữa */
    .st-key-db_pag [data-testid="stPagination"] { justify-content: center !important; }

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
        /* Lịch/heatmap (Vega) rộng -> cho cuộn ngang trong thẻ thay vì tràn */
        [data-testid="stVegaLiteChart"] { overflow-x: auto !important; justify-content: flex-start !important; }

        /* Bảng số liệu: chữ nhỏ & đệm sát để chứa nhiều cột hơn */
        .dtbl th, .dtbl td { padding: 3px 6px !important; font-size: 11px !important; }
        .dtbl-wrap { max-height: 70vh !important; }

        /* Thẻ dạng flex (vd Cập nhật gần nhất): xếp dọc cho dễ đọc */
        .glass-card[style*="display: flex"] { flex-direction: column !important; gap: 14px !important; }
        .glass-card[style*="display: flex"] > div { border-right: none !important; }
    }

    /* ===== Ghi chú ngày: ghi chú đã lưu hiện PHẲNG (không khung riêng bao quanh), giống hệt
       cách ghi chú hiện trong .jrows của Nhật ký -- chỉ .note-empty (trạng thái trống) mới có
       khung (viền chấm) để phân biệt rõ với có nội dung. ===== */
    .note-empty { font-size: 14px; color: #86868b; background: #f7f7f9;
        border: 1px dashed rgba(0,0,0,0.14); border-radius: 10px; padding: 13px 15px; }

    /* ===== Hiển thị ghi chú dạng HTML (do Quill xuất ra) ===== */
    .note-html, .st-key-note_saved { font-size: 14.5px; line-height: 1.6; color: #1d1d1f; }
    .st-key-note_saved [data-testid="stMarkdownContainer"],
    .st-key-note_saved [data-testid="stMarkdownContainer"] p,
    .st-key-note_saved [data-testid="stMarkdownContainer"] li { font-size: 14.5px !important; line-height: 1.6 !important; }
    .note-html p, .st-key-note_saved p { margin: 4px 0; }
    .note-html ul, .note-html ol, .st-key-note_saved ul, .st-key-note_saved ol { margin: 4px 0; padding-left: 22px; }
    /* Bỏ lề trên/dưới ở phần tử đầu & cuối để ghi chú căn thẳng dòng đầu (không bị lệch khung) */
    .note-html > :first-child, .st-key-note_saved > :first-child { margin-top: 0 !important; }
    .note-html > :last-child, .st-key-note_saved > :last-child { margin-bottom: 0 !important; }
    .note-html a, .st-key-note_saved a { color: var(--accent); }
    /* Thụt lề bullet/đánh số lồng nhau (Quill dùng class ql-indent-N trên <li>) */
    .ql-indent-1 { padding-left: 2.0em; } .ql-indent-2 { padding-left: 4.0em; }
    .ql-indent-3 { padding-left: 6.0em; } .ql-indent-4 { padding-left: 8.0em; }
    .ql-indent-5 { padding-left: 10em; } .ql-indent-6 { padding-left: 12em; }

    /* ===== Container có viền (ghi chú ngày, nhật ký, ngày này năm trước, hướng dẫn) trông
       như glass-card ===== */
    .st-key-note_card, [class*="st-key-jcard"], [class*="st-key-guide"] {
        border-radius: 16px !important;
        border-color: #d1d1d6 !important;
        box-shadow: 0 1px 1px rgba(0,0,0,0.02) !important;
        background: #fff !important;
    }
    /* Box "mẹo" trong tab Hướng dẫn: nền tông teal (accent), thay vì xanh dương mặc định
       của st.info() -> chỉ áp trong các thẻ guide_*, không đụng st.info() ở nơi khác. */
    [class*="st-key-guide"] [data-testid="stAlertContainer"] { background-color: rgba(var(--accent-rgb),0.10) !important; }
    [class*="st-key-guide"] [data-testid="stAlertContentInfo"] * { color: var(--accent-dark) !important; }
    [class*="st-key-guide"] [data-testid="stAlertContentInfo"] svg { fill: var(--accent-dark) !important; }

    /* ===== Nhật ký & Ngày này năm trước: thẻ có kẻ dọc trái/phải =====
       Dựng bằng HTML tự thân (1 khối st.markdown duy nhất mỗi thẻ) thay vì st.columns()
       lặp lại -> tránh hoàn toàn cơ chế flex/chiều cao tự tính của Streamlit (từng làm
       khoảng cách quanh đường kẻ lệch nhau dù CSS đặt padding bằng nhau, do JS tính sẵn
       chiều cao hàng theo layout ban đầu, không cập nhật lại khi nội dung dài tràn khung). */
    .jrows .jrow { display: grid; grid-template-columns: 1fr 5fr; align-items: start;
        column-gap: 10px; padding: 16px 0; border-bottom: 1px solid rgba(0,0,0,0.06); }
    .jrows .jrow:last-child { border-bottom: none; }
    .jrows .jrow > .jdate, .jrows .jrow > a.jdate-link {
        border-right: 1px solid rgba(0,0,0,0.08); padding-right: 10px;
    }
    /* Ô Thứ/ngày trong Nhật ký là link (nhảy sang Báo cáo ngày đúng ngày đó) -> bỏ màu xanh/
       gạch chân mặc định của <a>, giữ nguyên hình thức cũ; không áp cho .jdate trần (dùng ở
       "Ngày này năm trước" và thẻ Ghi chú ngày -- tự link về chính trang đang xem là vô nghĩa). */
    .jrows .jrow > a.jdate-link { display: block; text-decoration: none; color: inherit; cursor: pointer; }
    .jrows .jrow > a.jdate-link:hover .jdowbig { color: var(--accent); }
    @media (max-width: 640px) {
        .jrows .jrow { grid-template-columns: 1fr; row-gap: 6px; }
        .jrows .jrow > .jdate, .jrows .jrow > a.jdate-link { border-right: none; padding-right: 0; }
    }
    .jdate { text-align: center; }
    .jdate .jyear { font-size: 20px; font-weight: 700; color: var(--accent); letter-spacing: -0.5px; line-height: 1; }
    .jdate .jdow { font-size: 15px; font-weight: 700; color: #1d1d1f; margin-top: 6px; }
    .jdate .jdowbig { font-size: 18px; font-weight: 700; color: #1d1d1f; letter-spacing: -0.3px; }
    .jdate .jdm { font-size: 13px; color: #86868b; font-weight: 500; margin-top: 2px; }
    .jchip { display: inline-block; background: #f0f1f4; border-radius: 10px; padding: 5px 11px;
        font-size: 12.5px; margin: 0 6px 6px 0; }
    .jchip .ck { color: #86868b; } .jchip .cv { font-weight: 600; color: #1d1d1f; margin-left: 5px; }
    /* Nhãn tên sách phía trên chip các phần đã đọc (box Đọc sách, Nhật ký đọc sách) -- nhại
       đúng pattern nhãn nhỏ đã dùng cho where= của guide_item và box "Lịch Work" cũ. */
    .rl-book { display: block; font-size: 11px; font-weight: 700; color: #86868b;
        text-transform: uppercase; letter-spacing: .5px; margin: 0 0 4px 2px; }
    /* Ghi chú ngày (Báo cáo ngày): bố cục 2 cột giống .jrows .jrow, nhưng dựng bằng st.columns()
       thật (không phải 1 khối HTML tĩnh) vì bên trong có widget Streamlit thật (Quill, nút) --
       không thể gói trong unsafe_allow_html. [data-testid="stColumn"] là cột do Streamlit tự
       dựng bên trong container key="note_row". */
    .st-key-note_row [data-testid="stColumn"]:first-child { border-right: 1px solid rgba(0,0,0,0.08); }
    @media (max-width: 640px) {
        .st-key-note_row [data-testid="stColumn"]:first-child { border-right: none; }
    }
    /* Top 3 (Báo cáo ngày): tách khỏi bảng số liệu phía trên */
    .st-key-day_top3 { margin-top: 14px; }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    "<h1 style='text-align:center; margin:0 0 0.35em 0; letter-spacing:-0.6px;'>Forest Dashboard</h1>",
    unsafe_allow_html=True,
)

# Thanh điều hướng 1 hàng phẳng (kiểu iOS segmented control), icon Material cho từng trang.
# Key = định danh trang (dùng cho dispatch & deep-link ?nav=); nhãn hiển thị rút gọn ở NAV_SHORT.
NAV = {
    "Hôm nay": ":material/today:",
    "Báo cáo": ":material/summarize:",
    "Nhật ký đọc sách": ":material/menu_book:",
    "Gundam": ":material/shield:",
    "Tuỳ biến": ":material/settings:",
    "Hướng dẫn": ":material/help:",
}
# Nhãn ngắn để các tab vừa 1 hàng (key trang giữ nguyên).
NAV_SHORT = {
    "Hôm nay": "Hôm nay",
    "Báo cáo": "Báo cáo",
    "Nhật ký đọc sách": "Sách",
    "Gundam": "Gundam",
    "Tuỳ biến": "Tuỳ biến",
    "Hướng dẫn": "Trợ giúp",
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

# Khởi tạo nav từ URL (?nav=<trang>) -> deep-link & giữ trang khi F5/refresh.
# Chỉ đặt khi session chưa có để không ghi đè lựa chọn người dùng đang thao tác.
if "nav" not in st.session_state:
    _q = st.query_params.get("nav")
    st.session_state["nav"] = _q if _q in NAV else "Hôm nay"

nav = st.segmented_control(
    "Trang", list(NAV.keys()),
    format_func=lambda x: f"{NAV[x]} {NAV_SHORT[x]}",
    key="nav", label_visibility="collapsed",
)
if not nav:
    nav = "Hôm nay"
# Đồng bộ trang hiện tại lên URL (idempotent -> không gây rerun lặp)
st.query_params["nav"] = nav

# Sub-page của "Báo cáo" (Tổng quan/Tháng/Tuần/Dự án) -- đọc ?sub= 1 lần y hệt cách "nav" ở trên,
# cho phép link "nhảy tới ngày" từ Nhật ký dùng chung 1 cơ chế qua hàng "Chọn kỳ xem" trong trang.
BAOCAO_SUBS = ["Tổng quan", "Tháng", "Tuần", "Dự án"]
BAOCAO_SUB_ICONS_MD = {"Tổng quan": ":material/bar_chart:", "Tháng": ":material/calendar_month:",
                        "Tuần": ":material/calendar_view_week:", "Dự án": ":material/work:"}
if "bc_sub" not in st.session_state:
    _qs = st.query_params.get("sub")
    st.session_state["bc_sub"] = _qs if _qs in BAOCAO_SUBS else "Tổng quan"
if nav == "Báo cáo":
    st.query_params["sub"] = st.session_state["bc_sub"]
elif "sub" in st.query_params:
    del st.query_params["sub"]


def render_day_report(df):
    """Nội dung trang "Hôm nay" -- mục đầu tiên trên nav bar, trang mặc định khi mở app. Tách
    thành hàm riêng (thay vì viết trực tiếp trong khối if nav=="Hôm nay":) vì day-jump link
    (?nav=Hôm nay&day=...) tự nhiên dẫn vào đúng nhánh này, không cần cơ chế bypass riêng nào."""
    if df.empty:
        st.info("Chưa có dữ liệu. Vui lòng sang tab 'Tuỳ biến' để tải file lên.")
        return
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

            bg = (day_df.assign(_b=pd.to_datetime(day_df['Thời gian bắt đầu']).dt.hour.map(_buoi_of))
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
            frag_pie(day_df, "rad_day", "Dự án")

        with st.expander("4. Danh sách phiên", expanded=False):
            rows_html = ''
            for i, (_, r) in enumerate(day_df.sort_values('Thời gian bắt đầu').iterrows(), 1):
                s = pd.to_datetime(r['Thời gian bắt đầu']); e = pd.to_datetime(r['Thời gian kết thúc'])
                cat = r.get('Danh mục')
                cat = str(cat) if (r.get('Có danh mục') and pd.notna(cat)) else '—'
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
# TRANG: HÔM NAY
# ==========================================
if nav == "Hôm nay":
    render_day_report(df)

# ==========================================
# TAB BÁO CÁO THÁNG
# ==========================================
elif nav == "Báo cáo":
    _sub_pick = st.segmented_control(
        "Chọn kỳ xem", BAOCAO_SUBS,
        format_func=lambda x: f"{BAOCAO_SUB_ICONS_MD[x]} {x}",
        default=st.session_state["bc_sub"], key="bc_sub_picker", label_visibility="collapsed")
    if _sub_pick and _sub_pick != st.session_state["bc_sub"]:
        st.session_state["bc_sub"] = _sub_pick
    bc_sub = st.session_state["bc_sub"]
    st.query_params["sub"] = bc_sub

    if bc_sub == "Tổng quan":
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
                frag_calendar(df, "range_cal")
            with st.expander("3. Xu hướng theo thời gian", expanded=False):
                frag_trend(df, "trend_main", "Danh mục")
            with st.expander("4. Xu hướng tập trung theo khung giờ", expanded=False):
                frag_hourly(df, "hour_main", "Danh mục")
            with st.expander("5. Giờ tập trung theo thứ", expanded=False):
                frag_heatmap(df, "range_heat")
            with st.expander("6. Phân bố độ dài phiên", expanded=False):
                render_session_histogram(df)
            with st.expander("7. Bảng số liệu", expanded=False):
                frag_data_table(df, "tbl_main")
        else:
            st.info("Chưa có dữ liệu hệ thống. Vui lòng sang tab 'Tuỳ biến' để tải file lên.")

    elif bc_sub == "Tháng":
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
                    frag_pie(df_m, "rad_tab3", "Danh mục")
                with st.expander("4. Xu hướng theo thời gian", expanded=False):
                    frag_period_trend(df_m, "trend_m_color", "Danh mục", 'Ngày', "Ngày trong tháng")
                with st.expander("5. Xu hướng tập trung theo khung giờ", expanded=False):
                    frag_hourly(df_m, "hour_m", "Danh mục", with_range=False)
                with st.expander("6. Giờ tập trung theo thứ", expanded=False):
                    render_dayhour_heatmap(df_m)
                with st.expander("7. Phân bố độ dài phiên", expanded=False):
                    render_session_histogram(df_m)
                with st.expander("8. Bảng số liệu", expanded=False):
                    render_detail_table(df_m)
    elif bc_sub == "Tuần":
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
                    frag_pie(df_w, "rad_tab4", "Danh mục")
                with st.expander("4. Xu hướng theo thời gian", expanded=False):
                    frag_period_trend(df_w, "trend_w_color", "Danh mục", 'Thứ', "Thứ trong tuần", cat_order=DAYS_ORDER)
                with st.expander("5. Xu hướng tập trung theo khung giờ", expanded=False):
                    frag_hourly(df_w, "hour_w", "Danh mục", with_range=False)
                with st.expander("6. Giờ tập trung theo thứ", expanded=False):
                    render_dayhour_heatmap(df_w)
                with st.expander("7. Phân bố độ dài phiên", expanded=False):
                    render_session_histogram(df_w)
                with st.expander("8. Bảng số liệu", expanded=False):
                    render_detail_table(df_w)
    elif bc_sub == "Dự án":
        if not df.empty:
            # Gom dự án theo nhóm (Danh mục) và phân biệt rõ Nhóm vs Dự án trong dropdown
            proj_to_cat = df.dropna(subset=['Dự án']).groupby('Dự án')['Danh mục'].first()
            # Mục rỗng đứng đầu -- mặc định KHÔNG chọn sẵn nhóm/dự án nào khi mới vào trang,
            # giống hệt selectbox "Chọn 1 cuốn/series" ở sub-tab Chi tiết (Sách/Gundam).
            _placeholder = ("none", "— Chọn để xem chi tiết —")
            _opts, _labels = [_placeholder], {_placeholder: _placeholder[1]}
            for _c in sorted(df['Danh mục'].dropna().unique()):
                _projs = sorted(proj_to_cat[proj_to_cat == _c].index.tolist())
                if _projs == [_c]:  # dự án chưa gán nhóm (nhóm trùng tên dự án) -> coi như một dự án độc lập
                    _o = ("proj", _c); _opts.append(_o); _labels[_o] = f"{_c}  ·  Dự án"
                else:
                    _oc = ("cat", _c); _opts.append(_oc); _labels[_oc] = f"{_c}  ·  Nhóm"
                    for _p in _projs:
                        _op = ("proj", _p); _opts.append(_op); _labels[_op] = f"   {_p}  ·  Dự án"

            sel = st.selectbox("Chọn Nhóm hoặc Dự án:", _opts, format_func=lambda o: _labels[o], key="grp_sel")
            if sel == _opts[0]:
                st.info("Chọn 1 Nhóm hoặc Dự án ở trên để xem chi tiết.")
            else:
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

                if _kind == "proj":
                    # Mục "Nhật ký đọc" chỉ hiện khi Dự án đang xem khớp 1 cuốn sách theo dõi qua
                    # Reminders (so _book_title() của List với tên Dự án) -- KHÔNG đánh số (giữ nguyên
                    # số các mục 1-5 cố định) vì đây là mục điều kiện, đúng tiền lệ "Ghi chú ngày"
                    # không số ở nhánh rỗng-phiên của Báo cáo ngày. Hiện trọn lịch sử phần đã đọc của
                    # đúng cuốn đó, không giới hạn theo kỳ (khác Nhật ký đọc sách ở Báo cáo tuần/tháng).
                    rl_all = load_reading_log()
                    rl_book = rl_all[rl_all['Cuốn sách'] == sel_grp] if not rl_all.empty else rl_all
                    if not rl_book.empty:
                        with st.expander("Nhật ký đọc", expanded=True):
                            with st.container(border=True, key="jcard_reading_proj"):
                                st.markdown(f"<div class='jrows'>{_reading_rows_html(rl_book, label_book=False)}</div>",
                                            unsafe_allow_html=True)

                with st.expander("2. Biểu đồ lịch", expanded=False):
                    frag_calendar(df_g, "range_grp_cal")
                with st.expander("3. Xu hướng theo thời gian", expanded=False):
                    frag_trend(df_g, "trend_grp", "Dự án")
                with st.expander("4. Phân bố độ dài phiên", expanded=False):
                    render_session_histogram(df_g)
                with st.expander("5. Bảng số liệu", expanded=False):
                    frag_period_table(df_g, "view_grp")
elif nav == "Nhật ký đọc sách":
    # KHÔNG bắt buộc df (Forest) khác rỗng nữa -- trang này giờ gộp 2 nguồn, vẫn hoạt động được
    # nếu người dùng chỉ có dữ liệu đọc sách từ Reminders, chưa từng tải CSV Forest (an toàn
    # nhờ đã bỏ early-return columnless ở prep_analysis_data()).
    books_df = df[(df['Danh mục'] == BOOKS_GROUP) & (~df['Dự án'].isin(BOOKS_EXCLUDE))]
    rl_all = load_reading_log()
    # Loại Reminder List Gundam (tên "Gundam - ...") -- có tab riêng, không tính vào tab Sách.
    rl_books = rl_all[~rl_all['Sách (gốc)'].map(_is_gundam_list)] if not rl_all.empty else rl_all
    if books_df.empty and rl_books.empty:
        st.info(f"Chưa có dữ liệu sách trong nhóm '{BOOKS_GROUP}' và chưa có dữ liệu đọc sách từ "
                f"Reminders. Gán Danh mục '{BOOKS_GROUP}' cho các dự án sách ở trang Chuẩn bị "
                f"dữ liệu, hoặc tải file ở mục 'Tải lên từ Reminder'.")
    else:
        # Chuẩn hoá cả 2 ứng viên về pd.Timestamp trước khi so sánh -- max() thô giữa
        # datetime.date (cột 'Ngày' của df) và Timestamp (cột 'Ngày hoàn thành' của rl_books) sẽ
        # lỗi TypeError (pandas không cho so sánh trực tiếp 2 kiểu này).
        _cands = [pd.Timestamp(v) for v in [df['Ngày'].max() if not df.empty else None,
                                            rl_books['Ngày hoàn thành'].max() if not rl_books.empty else None]
                 if v is not None and pd.notna(v)]
        latest_overall = max(_cands) if _cands else None
        render_reading_log(books_df, latest_overall, rl_books)
# ==========================================
# TRANG: GUNDAM
# ==========================================
elif nav == "Gundam":
    # Reminder List Gundam (tên "Gundam - Tên series") + phiên Forest tag GUNDAM_TAG -- Forest
    # không có Dự án riêng theo từng series nên phải suy ra qua _assign_gundam_sessions()
    # (ghép mỗi ngày có phiên Gundam với lần hoàn thành reminder gần nhất, xem docstring hàm đó).
    rl_all_g = load_reading_log()
    rl_gundam = rl_all_g[rl_all_g['Sách (gốc)'].map(_is_gundam_list)] if not rl_all_g.empty else rl_all_g
    gundam_sessions = df[df['Dự án'] == GUNDAM_TAG] if not df.empty else df
    if rl_gundam.empty and gundam_sessions.empty:
        st.info(f"Chưa có dữ liệu Gundam. Đổi tên Reminder List thành \"Gundam - Tên series\" "
                f"rồi tải lên ở mục 'Tải lên từ Reminder', hoặc gán tag \"{GUNDAM_TAG}\" cho "
                f"phiên Forest khi xem.")
    else:
        gundam_df = _assign_gundam_sessions(gundam_sessions, rl_gundam)
        _cands_g = [pd.Timestamp(v) for v in [gundam_df['Ngày'].max() if not gundam_df.empty else None,
                                               rl_gundam['Ngày hoàn thành'].max() if not rl_gundam.empty else None]
                    if v is not None and pd.notna(v)]
        latest_overall_g = max(_cands_g) if _cands_g else None
        render_reading_log(gundam_df, latest_overall_g, rl_gundam, labels=GUNDAM_LABELS)
# ==========================================
# TAB TUỲ BIẾN
# ==========================================
elif nav == "Tuỳ biến":
    with st.expander("1. Giao diện", expanded=True):
        _preset_items = list(ACCENT_PRESETS.items())
        _per_row = 5
        _swatch_css = "<style>"
        for _row_start in range(0, len(_preset_items), _per_row):
            _row_items = _preset_items[_row_start:_row_start + _per_row]
            _cols = st.columns(_per_row)
            for _i, (_name, _hex) in enumerate(_row_items):
                _idx = _row_start + _i
                _key = f"accent_sw_{_idx}"
                _selected = _hex == ACCENT
                _border = "#1d1d1f" if _selected else "transparent"
                _txt_color = _readable_text(_hex)
                _label = f"✓ {_name}" if _selected else _name
                # Selector cần đủ đặc hiệu để thắng rule chung .stButton button[kind="secondary"]
                # (đặt nền trắng !important cho mọi nút phụ trong app) -- .st-key-<key> button đơn
                # thuần thua rule đó (thiếu 1 bậc [data-testid]/[kind]), nên phải khớp lại cấu trúc
                # đầy đủ div[data-testid="stButton"] button[kind="secondary"] bên trong. Tên màu
                # hiện thẳng trên nút (không chỉ tooltip) -- màu chữ tự chọn trắng/đen theo độ
                # chói nền (_readable_text) để luôn đọc rõ với 14 màu khác nhau.
                _swatch_css += (
                    f".st-key-{_key} div[data-testid=\"stButton\"] button[kind=\"secondary\"] {{ "
                    f"background:{_hex} !important; color:{_txt_color} !important; "
                    f"border:3px solid {_border} !important; border-radius:12px !important; "
                    f"width:100% !important; height:auto !important; min-height:48px !important; "
                    f"padding:8px 6px !important; font-weight:600 !important; font-size:13px !important; "
                    f"white-space:normal !important; line-height:1.25 !important; }}")
                with _cols[_i]:
                    if st.button(_label, key=_key, use_container_width=True):
                        if _hex != ACCENT:
                            save_setting("accent_hex", _hex)
                            st.rerun()
        _swatch_css += "</style>"
        st.markdown(_swatch_css, unsafe_allow_html=True)

    with st.expander("2. Dữ liệu đầu vào", expanded=True):
        _tab_forest, _tab_cal, _tab_rem = st.tabs(["Tải lên từ Forest", "Đồng bộ lịch", "Tải lên từ Reminder"])
        with _tab_forest:
            _msg = st.session_state.pop('import_msg', None)
            if _msg:
                st.success(_msg)
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
                        # _fmt_ts (không phải .astype(str) thô) ở CẢ 2 vế -> deleted đã là chuỗi
                        # chuẩn "YYYY-MM-DD HH:MM:SS" (không giây lẻ, từ load_deleted), còn df_new
                        # là Timestamp mới parse (thường CÓ giây lẻ) -- so sánh thô sẽ luôn lệch
                        # nhau nên phiên đã xoá không được nhận ra, bị thêm lại khi nạp lại CSV cũ.
                        del_keys = set(zip(deleted['Thời gian bắt đầu'].map(_fmt_ts),
                                           deleted['Thời gian kết thúc'].map(_fmt_ts)))
                        keep = [(s, e) not in del_keys for s, e in
                                zip(df_new['Thời gian bắt đầu'].map(_fmt_ts), df_new['Thời gian kết thúc'].map(_fmt_ts))]
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
                            # _fmt_ts (không phải .astype(str) thô) -> chuẩn hoá về cùng 1 định dạng
                            # "YYYY-MM-DD HH:MM:SS" bất kể cột đang là chuỗi (từ db cũ) hay Timestamp
                            # (từ df_new mới parse) -> drop_duplicates nhận đúng phiên trùng dù nguồn
                            # gốc có/không giây lẻ, tránh chèn trùng khi nạp lại cùng file Forest.
                            combined['Thời gian bắt đầu'] = combined['Thời gian bắt đầu'].map(_fmt_ts)
                            combined['Thời gian kết thúc'] = combined['Thời gian kết thúc'].map(_fmt_ts)
                            combined = combined.drop_duplicates(subset=['Thời gian bắt đầu', 'Thời gian kết thúc'], keep='first')
                            added = len(combined) - before
                            dup = stats['valid'] - skipped_deleted - added
                            save_db(combined)
                            st.session_state['import_msg'] = (
                                f"Đã thêm {added} phiên mới (bỏ {dup} trùng, {stats['failed']} thất bại, "
                                f"{stats['unset']} unset{_extra}){rng if added else ''}.")
                            st.rerun()

        with _tab_cal:
            sc1, sc2 = st.columns([3, 1])
            with sc1:
                sync_range = st.segmented_control("Khoảng đồng bộ (quanh hôm nay)",
                                                   ["-30 / +30 ngày", "-90 / +90 ngày", "-180 / +180 ngày"],
                                                   default="-90 / +90 ngày", key="wc_range")
            sync_days = {"-30 / +30 ngày": 30, "-90 / +90 ngày": 90, "-180 / +180 ngày": 180}.get(sync_range or "-90 / +90 ngày", 90)
            with sc2:
                st.write("")
                if st.button("Đồng bộ ngay", type="primary", key="wc_sync_btn"):
                    _start = date.today() - timedelta(days=sync_days)
                    _end = date.today() + timedelta(days=sync_days)
                    with st.spinner("Đang kết nối iCloud..."):
                        _n, _err = sync_work_calendar(_start, _end)
                    if _err:
                        st.error(_err)
                    else:
                        st.success(f"Đã đồng bộ {_n} appointment (từ {_start:%d/%m/%Y} đến {_end:%d/%m/%Y}).")
                        time.sleep(1)
                        st.rerun()

            with st.expander("Đồng bộ khoảng ngày khác (nâng cao)", expanded=False):
                st.caption("Dùng khi cần lấp dữ liệu lịch cũ cho mục *Ngày này năm trước* — không "
                           "cần dùng thường xuyên.")
                dc1, dc2, dc3 = st.columns([2, 2, 1])
                with dc1:
                    _adv_start = st.date_input("Từ ngày", value=date.today() - timedelta(days=365 * 2), key="wc_adv_start")
                with dc2:
                    _adv_end = st.date_input("Đến ngày", value=date.today(), key="wc_adv_end")
                with dc3:
                    st.write("")
                    if st.button("Đồng bộ ngay", key="wc_adv_sync_btn"):
                        if _adv_start >= _adv_end:
                            st.error("Từ ngày phải trước Đến ngày.")
                        else:
                            with st.spinner("Đang kết nối iCloud..."):
                                _n2, _err2 = sync_work_calendar(_adv_start, _adv_end)
                            if _err2:
                                st.error(_err2)
                            else:
                                st.success(f"Đã đồng bộ {_n2} appointment (từ {_adv_start:%d/%m/%Y} đến {_adv_end:%d/%m/%Y}).")
                                time.sleep(1)
                                st.rerun()

        with _tab_rem:
            st.caption("Tải file `reading_log.csv` xuất từ Shortcut (xem hướng dẫn tạo Shortcut ở "
                       "tab Hướng dẫn). Mỗi lần tải lên sẽ **thay thế toàn bộ** dữ liệu cũ.")
            rl_file = st.file_uploader("Tải lên file từ Shortcuts (.csv/.txt)", type=["csv", "txt"], key="rl_shortcut_file")
            if rl_file:
                rl_df, rl_stats, rl_missing = parse_reading_log_shortcut_csv(rl_file)
                if rl_missing:
                    st.error("File thiếu cột: " + ", ".join(rl_missing) + " — cần đúng 3 cột "
                              "'list|title|completed_date' (xem hướng dẫn tạo Shortcut trong tab Hướng dẫn).")
                elif rl_df.empty:
                    st.warning("Không đọc được dòng hợp lệ nào trong file.")
                else:
                    st.caption(f"Đọc được **{rl_stats['valid']}**/{rl_stats['raw']} dòng hợp lệ. Xem trước:")
                    _rl_prev = rl_df.head(8).copy()
                    _rl_prev['Ngày hoàn thành'] = _rl_prev['Ngày hoàn thành'].dt.strftime('%Y-%m-%d %H:%M')
                    st.dataframe(_rl_prev, width='stretch', hide_index=True)
                    st.caption("Xác nhận sẽ **thay thế toàn bộ** dữ liệu Đọc sách hiện có bằng nội dung file này.")
                    if st.button("Xác nhận nạp dữ liệu", type="primary", key="rl_shortcut_confirm"):
                        save_reading_log_bulk(rl_df)
                        st.success(f"Đã nạp {rl_df['Sách (gốc)'].nunique()} cuốn sách, {len(rl_df)} phần đã đọc.")
                        time.sleep(1)
                        st.rerun()

    with st.expander("3. Phân loại", expanded=True):
        db_current = load_db()
        mapping_df = load_mapping()
        all_projs = sorted(db_current['Dự án'].dropna().astype(str).unique()) if not db_current.empty else []
        cur_map = dict(zip(mapping_df['Dự án'].astype(str), mapping_df['Danh mục'])) if not mapping_df.empty else {}
        if not all_projs:
            st.info("Chưa có dự án nào. Hãy tải dữ liệu ở mục 2 trước.")
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
            tbl = pd.DataFrame({"Dự án": all_projs, "Nhóm (Danh mục)": [cur_map.get(p) for p in all_projs]})
            edited = st.data_editor(
                tbl, hide_index=True, width='stretch', key="map_editor",
                column_config={
                    "Dự án": st.column_config.TextColumn("Dự án", disabled=True),
                    # Ô trống luôn hiện chữ "None" (canvas riêng của SelectboxColumn, không phải
                    # DOM nên không sửa được bằng CSS/đổi kiểu None->NaN) -> chú thích rõ ý nghĩa
                    # qua tooltip cột thay vì cố "ẩn" nó đi.
                    "Nhóm (Danh mục)": st.column_config.SelectboxColumn(
                        "Nhóm (Danh mục)", options=opts,
                        help="Để trống (hiện 'None') = dự án tự đứng riêng, không thuộc nhóm nào."),
                },
            )
            if st.button("Lưu phân loại", type="primary"):
                nm = edited.rename(columns={"Nhóm (Danh mục)": "Danh mục"})
                nm = nm[nm["Danh mục"].notna() & (nm["Danh mục"].astype(str).str.strip() != "")]
                save_mapping(nm[["Dự án", "Danh mục"]].reset_index(drop=True))
                st.rerun()
    with st.expander("4. Dữ liệu làm việc hiện tại", expanded=True):
        if not db_current.empty:
            db_base = db_current.reset_index(drop=True)
            _dt = pd.to_datetime(db_base['Thời gian bắt đầu'], errors='coerce')
            # Tổng quan: thẻ căn giữa
            st.markdown(
                f"<div class='glass-card' style='padding:10px 18px;margin-bottom:14px;text-align:center;'>"
                f"<span style='font-size:14px;color:#1d1d1f;'>Tổng <b>{len(db_base)}</b> phiên · "
                f"từ {_dt.min():%d/%m/%Y} đến {_dt.max():%d/%m/%Y}</span></div>",
                unsafe_allow_html=True)
            disp_db = db_base.copy()
            disp_db['Thời gian bắt đầu'] = pd.to_datetime(disp_db['Thời gian bắt đầu']).dt.strftime('%Y-%m-%d %H:%M')
            disp_db['Thời gian kết thúc'] = pd.to_datetime(disp_db['Thời gian kết thúc']).dt.strftime('%Y-%m-%d %H:%M')
            if 'Note' in disp_db.columns: disp_db = disp_db.drop(columns=['Note'])

            # Phân trang 100 dòng/trang khi nhiều phiên. Đọc trang từ session_state TRƯỚC để cắt
            # bảng; render widget pagination Ở DƯỚI bảng (cùng key nên vẫn lái được lát cắt qua
            # mỗi lần rerun). Dòng chọn để xoá là vị trí TRONG trang -> cộng _start ra chỉ số tuyệt đối.
            PAGE_SIZE = 100
            n = len(disp_db)
            paged = n > PAGE_SIZE
            _start = 0
            if paged:
                num_pages = (n + PAGE_SIZE - 1) // PAGE_SIZE
                page = min(st.session_state.get("db_page", 1), num_pages)  # clamp khi co lại sau xoá
                st.session_state["db_page"] = page
                _start = (page - 1) * PAGE_SIZE
                page_df = disp_db.iloc[_start:_start + PAGE_SIZE]
            else:
                page_df = disp_db

            ev = st.dataframe(page_df, width='stretch', hide_index=True,
                              on_select="rerun", selection_mode="multi-row", key="db_view")
            sel_rows = [_start + r for r in (list(ev.selection.rows) if ev and ev.selection else [])]
            if sel_rows and st.button(f"Xoá {len(sel_rows)} phiên đã chọn", type="primary"):
                add_deleted(db_base.loc[sel_rows, ['Thời gian bắt đầu', 'Thời gian kết thúc']])
                save_db(db_base.drop(index=sel_rows).reset_index(drop=True))
                st.rerun()

            # Pagination DƯỚI bảng + căn giữa; dòng "Hiển thị phiên" ở dưới cùng, căn giữa.
            if paged:
                with st.container(key="db_pag"):
                    st.pagination(num_pages, key="db_page")
                st.markdown(
                    f"<div style='text-align:center;font-size:13px;color:#86868b;margin-top:2px;'>"
                    f"Hiển thị phiên {_start + 1}–{min(_start + PAGE_SIZE, n)} / {n}</div>",
                    unsafe_allow_html=True)
    with st.expander("5. Quản lý hệ thống", expanded=True):
        c1, c2, c3 = st.columns(3)
        _today = date.today().strftime('%Y-%m-%d')
        with c1:
            st.subheader("Sao lưu")
            db_now = load_db()
            if not db_now.empty:
                _buf = io.BytesIO()
                with zipfile.ZipFile(_buf, "w", zipfile.ZIP_DEFLATED) as _z:
                    _settings_df = pd.DataFrame(list(load_settings().items()), columns=["key", "value"])
                    for _fn, _df in [(DB_FILE, db_now), (MAPPING_FILE, load_mapping()),
                                      (DELETED_FILE, load_deleted()), (NOTES_FILE, load_notes()),
                                      (WORK_CALENDAR_FILE, load_work_calendar()),
                                      (READING_LOG_FILE, load_reading_log()),
                                      (SETTINGS_FILE, _settings_df)]:
                        if not _df.empty:
                            _z.writestr(os.path.basename(_fn), _df.to_csv(index=False))
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
                        if WORK_CALENDAR_FILE in names:
                            parts.append(f"Lịch **{len(pd.read_csv(io.BytesIO(_z.read(WORK_CALENDAR_FILE))))}** appointment")
                        if READING_LOG_FILE in names:
                            parts.append(f"Đọc sách **{len(pd.read_csv(io.BytesIO(_z.read(READING_LOG_FILE))))}** phần")
                        if SETTINGS_FILE in names:
                            parts.append(f"Cài đặt **{len(pd.read_csv(io.BytesIO(_z.read(SETTINGS_FILE))))}** mục")
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
                        save_deleted(pd.read_csv(io.BytesIO(_z.read(DELETED_FILE)), dtype=str))
                    if NOTES_FILE in names:
                        save_notes_bulk(pd.read_csv(io.BytesIO(_z.read(NOTES_FILE)), dtype=str).fillna(""))
                    if WORK_CALENDAR_FILE in names:
                        save_work_calendar_bulk(pd.read_csv(io.BytesIO(_z.read(WORK_CALENDAR_FILE)), dtype=str))
                    if READING_LOG_FILE in names:
                        save_reading_log_bulk(pd.read_csv(io.BytesIO(_z.read(READING_LOG_FILE)), dtype=str))
                    if SETTINGS_FILE in names:
                        save_settings_bulk(pd.read_csv(io.BytesIO(_z.read(SETTINGS_FILE)), dtype=str))
                st.cache_data.clear()
                st.success("Khôi phục hệ thống thành công!")
                time.sleep(1)
                st.rerun()
        with c3:
            st.subheader("Làm mới")
            confirm_delete = st.checkbox("Tôi xác nhận muốn xoá toàn bộ dữ liệu")
            if st.button("Xoá toàn bộ dữ liệu", disabled=not confirm_delete):
                _sb_delete_all("sessions", "id")
                _sb_delete_all("mapping", "project")
                _sb_delete_all("deleted_sessions", "start_time")
                _sb_delete_all("notes", "note_date")
                _sb_delete_all("work_calendar", "uid")
                _sb_delete_all("reading_log", "uid")
                _sb_delete_all("settings", "key")
                st.cache_data.clear()
                st.success("Đã xoá toàn bộ dữ liệu!")
                time.sleep(1)
                st.rerun()

# ==========================================
# TAB HƯỚNG DẪN
# ==========================================
elif nav == "Hướng dẫn":
    st.markdown(
        "<div style='margin-bottom:6px;'>"
        "<div style='font-size:1.9rem;font-weight:700;letter-spacing:-0.5px;'>Hướng dẫn &amp; Giải thích</div>"
        "<div style='font-size:14.5px;color:#86868b;margin-top:2px;'>Mọi số liệu, biểu đồ và tính năng trong "
        "app có ý nghĩa gì, đọc thế nào và dùng để làm gì — kèm ảnh minh hoạ.</div></div>",
        unsafe_allow_html=True)

    st.markdown("### Tổng quan ứng dụng")
    with st.container(border=True, key="guide_intro"):
        st.markdown(
            "Forest Tracker là công cụ **xem lại** (retrospective), không phải công cụ **đặt mục tiêu**: app không "
            "chấm điểm, không nhắc nhở, không đặt KPI — chỉ lấy dữ liệu bạn đã có sẵn từ app **Forest** (mỗi lần trồng "
            "cây thành công = một *phiên tập trung*) rồi trình bày lại dưới nhiều góc nhìn để bạn tự đối chiếu với "
            "chính mình theo thời gian. Toàn bộ dữ liệu chạy **cục bộ trên máy bạn**, không đồng bộ lên đâu cả — vì "
            "vậy mục *Sao lưu* ở trang Chuẩn bị dữ liệu khá quan trọng nếu bạn đổi máy hoặc xoá trình duyệt.\n\n"
            "Thanh điều hướng trên cùng gồm 6 trang:\n\n"
            "- **Thống kê chung** — bức tranh toàn bộ lịch sử, không giới hạn theo kỳ; nơi tốt nhất để nhìn xu hướng dài hạn.\n"
            "- **Báo cáo** — gộp 4 góc nhìn theo kỳ: **Tháng** / **Tuần** / **Ngày** (đào sâu một kỳ cụ thể, có bộ chọn "
            "kỳ riêng, kèm mục *Nhật ký* — ghi chú + lịch + phần đọc sách đã lưu trong kỳ — và ở mục Ngày còn có *Ngày "
            "này năm trước*), và **Dự án** (giống Thống kê chung nhưng lọc theo đúng một Nhóm hoặc Dự án bạn chọn, mặc "
            "định chưa chọn sẵn gì, hữu ích khi muốn soi riêng một môn/kỹ năng đang theo đuổi). Dùng hàng nút **Chọn "
            "kỳ xem** ngay dưới tiêu đề trang để đổi nhanh giữa 4 kỳ, không cần tải lại trang. Bấm vào Thứ/ngày của "
            "1 dòng trong *Nhật ký* sẽ nhảy thẳng sang đúng kỳ **Ngày** của ngày đó.\n"
            "- **Nhật ký đọc sách** — trang riêng cho việc đọc sách tuần tự, chia 2 sub-tab: **Tổng quan** (số liệu "
            "tổng, timeline trình tự đọc, bảng chi tiết mọi cuốn) và **Chi tiết** (chọn đúng 1 cuốn để xem sâu: số "
            "liệu hero, nhật ký đọc, biểu đồ lịch theo số phần/ngày, bảng số liệu từng ngày).\n"
            "- **Gundam** — y hệt Nhật ký đọc sách (cùng 2 sub-tab Tổng quan/Chi tiết) nhưng cho các series anime Gundam đang xem.\n"
            "- **Chuẩn bị dữ liệu** — nơi duy nhất *ghi* dữ liệu: nạp file CSV xuất từ Forest, gán Danh mục cho từng Dự án, "
            "sao lưu/khôi phục/làm mới; mọi trang còn lại đều chỉ *đọc*.\n\n"
            "Trong mỗi trang báo cáo, các mục được xếp trong những khối có thể **mở/thu gọn** (bấm vào tiêu đề để đóng/mở); "
            "mặc định chỉ mở sẵn mục *Tổng quan* (và *Nhật ký* nếu trang đó có) để trang gọn khi mới vào — mục nào đang mở "
            "sẽ có viền dưới và icon mũi tên chuyển sang màu accent để dễ nhận ra. Hầu hết biểu đồ đều có **chú giải khi "
            "di chuột (tooltip)** hiện số liệu chính xác của đúng điểm/ô đang trỏ vào, và nhiều biểu đồ có thanh điều "
            "khiển riêng (khoảng thời gian, cách gộp, phân loại) đặt ngay phía trên — đổi bộ lọc chỉ vẽ lại đúng biểu đồ "
            "đó, không load lại cả trang.")

    st.markdown("### Số liệu tổng quan")
    guide_item(
        "stat_panel.png", "Bảng số liệu tổng quan",
        "Thẻ đầu tiên của mọi trang báo cáo, gói toàn bộ con số quan trọng nhất của kỳ đang xem thành các nhóm chip "
        "nhỏ, đọc lướt là nắm được bức tranh chung mà không cần cuộn xuống biểu đồ:\n\n"
        "- **Tổng thời gian** & **Số cây đã trồng**: tổng giờ tập trung cộng dồn và tổng số phiên hợp lệ trong phạm vi "
        "đang xem (mỗi phiên Forest trồng thành công = một cây, mỗi cây tương ứng đúng một dòng dữ liệu).\n"
        "- **Trung bình (toàn thời gian)**: *Thời gian/ngày* và *Số cây/ngày* chia cho số ngày **có hoạt động** trong "
        "phạm vi đang xem (bỏ qua ngày trống, không bị pha loãng bởi những ngày không trồng cây nào), còn **Thời gian/"
        "phiên** là độ dài bình quân của một lần tập trung — con số này giúp nhận ra thói quen: phiên trung bình 20 "
        "phút khác hẳn ý nghĩa với phiên trung bình 70 phút dù tổng giờ như nhau.\n"
        "- **7 ngày gần đây**: so sánh nhịp *7 ngày vừa qua* với mức trung bình giờ/ngày của *toàn bộ lịch sử đang xem* — "
        "gọi tắt là *thường lệ*. Ví dụ `+18% vs thường lệ` nghĩa là 7 ngày qua bạn tập trung nhiều hơn 18% so với mức "
        "bình quân mọi khi của chính mình (màu xanh lá); số âm (màu đỏ) nghĩa là đang chùng xuống. Đi kèm là **Số ngày "
        "hoạt động** trên 7 (vd 5/7) — biết được có bao nhiêu ngày trong tuần vừa rồi bạn *có* trồng cây, dù chỉ một cây.\n"
        "- **Chuỗi ngày** (streak): *Tổng cộng* là tổng số ngày rời rạc từng có ít nhất một phiên trong toàn bộ lịch sử; "
        "*Dài nhất* là kỷ lục chuỗi ngày liên tiếp có hoạt động (không đứt ngày nào); *Hiện tại* là chuỗi đang giữ tính tới "
        "hôm nay — chuỗi này vẫn còn hiệu lực nếu lần hoạt động gần nhất là **hôm nay hoặc hôm qua** (chưa bấm sang ngày "
        "thứ 2 liên tiếp không có gì), và sẽ về 0 ngay khi đứt quá 1 ngày.\n"
        "- **Theo thứ**: trong 7 thứ của tuần, thứ nào có giờ trung bình mỗi lần hoạt động cao nhất (**Mạnh nhất**) và "
        "thấp nhất (**Yếu nhất**) — trung bình này chỉ tính trên những lần đúng thứ đó có hoạt động (bỏ qua tuần nào "
        "thứ đó bạn nghỉ), hữu ích để nhận ra ví dụ cuối tuần luôn là điểm yếu, hay giữa tuần mới là lúc sung sức nhất.",
        tip="Theo dõi **Chuỗi hiện tại** mỗi ngày để giữ đà — chỉ cần một phiên ngắn cũng đủ giữ chuỗi không đứt. "
            "Ở mục Tuần/Tháng của Báo cáo, các con số này còn kèm mũi tên **▲/▼** so sánh trực tiếp với kỳ liền trước và với "
            "mức trung bình các kỳ, nên đọc nhanh được là kỳ này đang tốt lên hay đi xuống so với chính mình trước đó.",
        where="Mọi trang báo cáo → đầu mục Tổng quan")
    guide_item(
        "session_bar.png", "Thanh phân bố độ dài phiên (gọn)",
        "Một thanh ngang chia nhanh toàn bộ phiên trong phạm vi đang xem thành 5 nhóm theo độ dài, mỗi đoạn dài ngắn "
        "tỉ lệ với số phiên thuộc nhóm đó và có ghi kèm % cùng số phiên cụ thể khi di chuột vào:\n\n"
        "- **Tối thiểu (= 10′)** — đúng ngưỡng tối thiểu Forest công nhận một phiên hợp lệ, thường là phiên bị huỷ giữa "
        "chừng rồi tính lại hoặc chủ đích chỉ tập trung rất ngắn.\n"
        "- **Ngắn (< 25′)**, **Trung bình (25′–<50′)**, **Dài (50′–<90′)**, **Rất Dài (≥ 90′)** — các mốc 25/50/90 phút "
        "không phải ngẫu nhiên: chúng trùng với các đường mốc trong biểu đồ *Phân bố độ dài phiên* chi tiết bên dưới.\n\n"
        "Đọc nhanh: thanh nghiêng hẳn về bên trái (nhiều **Ngắn/Tối thiểu**) cho thấy phiên hay bị ngắt quãng, khó vào "
        "sâu; nghiêng về bên phải (nhiều **Dài/Rất Dài**) cho thấy bạn thường vào được trạng thái tập trung sâu ('deep "
        "work') mỗi khi đã bắt đầu.",
        tip="Đây là bản rút gọn, đặt sẵn ngay trong mục Tổng quan để không phải cuộn xuống mới thấy nhịp phiên dài/ngắn. "
            "Muốn xem chi tiết hơn — số phiên chính xác theo từng khoảng 5 phút, đường trung bình — hãy xem biểu đồ "
            "**Phân bố độ dài phiên** đầy đủ ở mục Các biểu đồ bên dưới.",
        where="Trong mục Tổng quan")

    st.markdown("### Các biểu đồ")
    guide_item(
        "calendar.png", "Biểu đồ lịch",
        "Lưới ô kiểu lịch đóng góp của GitHub: mỗi ô vuông là **một ngày**, xếp thành các cột tuần chạy từ trái "
        "(quá khứ) sang phải (hiện tại), mỗi cột 7 ô theo thứ tự Chủ Nhật → Thứ Bảy. Màu ô càng đậm thì tổng số giờ "
        "tập trung trong ngày đó càng cao, chia theo 7 bậc màu teal đậm dần theo ngưỡng giờ **cố định** (dưới 0.5h, "
        "0.5–1h, 1–2h, 2–3h, 3–4h, 4–6h, từ 6h trở lên) — nhờ vậy một ngày 5h luôn cùng một tông màu dù xem tháng "
        "nào, so được công bằng giữa các khoảng thời gian khác nhau thay vì bị co giãn theo riêng dữ liệu đang lọc.\n\n"
        "- Ô **trắng/nhạt nhất** = ngày hoàn toàn không có phiên nào (kể cả ngày trước khi bạn bắt đầu dùng Forest, "
        "nếu nằm trong phạm vi đang xem, cũng hiện trắng).\n"
        "- Một **dải ô đậm liên tiếp theo chiều dọc hoặc kéo dài nhiều cột** cho thấy chuỗi ngày làm việc đều, ít đứt quãng.\n"
        "- Nhìn toàn cảnh cả lưới giúp phát hiện ngay các *giai đoạn*: một mảng đậm kéo dài vài tuần (đang chăm), xen "
        "kẽ mảng nhạt (đang chùng, có thể trùng kỳ nghỉ/thi cử/ốm) — điều mà nhìn từng con số lẻ khó thấy được.",
        tip="Di chuột vào một ô bất kỳ để xem chú giải hiện chính xác ngày (thứ, ngày/tháng/năm) và tổng số giờ của "
            "ngày đó, kể cả những ngày rất nhạt màu mà mắt thường khó phân biệt với ô trắng hoàn toàn.",
        where="Thống kê chung · Báo cáo → Dự án → Biểu đồ lịch")
    guide_item(
        "trend.png", "Xu hướng theo thời gian",
        "Biểu đồ cột theo trục thời gian: chiều cao mỗi cột là **tổng thời gian tập trung** trong mốc đó, các cột "
        "được tô màu xếp chồng (stacked) theo Danh mục hoặc Dự án để vừa thấy tổng vừa thấy cơ cấu bên trong.\n\n"
        "- Thanh điều khiển ngay phía trên biểu đồ cho chỉnh 3 thứ độc lập: **khoảng thời gian** muốn xem, "
        "**cách gộp** cột theo Ngày/Tuần/Tháng, và **phân loại** màu theo Danh mục (nhóm lớn) hay Dự án (chi tiết từng "
        "tag Forest). Đổi bất kỳ lựa chọn nào chỉ vẽ lại đúng biểu đồ này, không ảnh hưởng phần còn lại của trang.\n"
        "- Khi gộp theo **Ngày**, biểu đồ tự vẽ thêm một **đường trung bình động 7 ngày** (rolling average) đè lên "
        "các cột — đường này làm mượt dao động ngày-qua-ngày (vốn rất nhiễu vì cuối tuần/ngày bận khác hẳn ngày rảnh) "
        "để lộ ra xu hướng thật đang đi lên, đi ngang hay đi xuống.\n"
        "- Đây là biểu đồ trả lời nhanh những câu hỏi kiểu: *'tháng này mình có đang đi lên không so với tháng trước?'*, "
        "*'từ khi thêm dự án mới, thời gian cho dự án cũ có bị co lại không?'*, *'giai đoạn nào tổng thời gian tụt hẳn?'*",
        where="Mọi trang báo cáo → Xu hướng theo thời gian")
    guide_item(
        "hourly.png", "Xu hướng tập trung theo khung giờ",
        "Biểu đồ cột theo 24 khung giờ trong ngày (0h–23h), gộp toàn bộ phạm vi đang xem lại làm một: mỗi cột là "
        "**trung bình số giờ mỗi ngày** bạn có phiên rơi vào đúng khung giờ đó (không phải tổng cộng dồn, nên biểu đồ "
        "không bị lệch chỉ vì phạm vi xem dài hay ngắn), các cột xếp chồng màu theo phân loại; nền biểu đồ chia sẵn 4 "
        "dải Sáng/Chiều/Tối/Khuya để dễ định vị.\n\n"
        "- Cột càng cao = khung giờ bạn tập trung nhiều và đều nhất — có thể gọi là khung giờ 'năng suất' của riêng bạn.\n"
        "- Ngay dưới biểu đồ có một dòng tóm tắt tự động nêu rõ **giờ tập trung nhất** (khung 1 tiếng cao điểm) và "
        "**buổi mạnh nhất** (Sáng/Chiều/Tối/Khuya) trong đúng phạm vi đang xem, khỏi phải tự đọc trục.",
        tip="Biết khung giờ mạnh nhất rồi thì nên chủ động **xếp việc khó/quan trọng nhất vào đúng lúc đó** — đừng để "
            "'giờ vàng' trôi qua với những việc vặt có thể làm vào lúc khác.",
        where="Mọi trang báo cáo → Xu hướng tập trung theo khung giờ")
    guide_item(
        "heatmap.png", "Giờ tập trung theo thứ",
        "Bản đồ nhiệt dạng lưới **7 thứ (trục ngang) × 24 khung giờ (trục dọc)**: mỗi ô nhỏ ứng với đúng một cặp "
        "(thứ, giờ), màu càng đậm thì trung bình số giờ/ngày bạn tập trung vào *đúng khung giờ đó của đúng thứ đó* "
        "càng cao — khác hẳn biểu đồ khung giờ ở trên vốn gộp chung cả 7 ngày trong tuần lại.\n\n"
        "- Dùng để tìm **'khung giờ vàng' riêng theo từng ngày trong tuần** — ví dụ nếu ô sáng sớm Thứ 2 đậm hẳn so "
        "với sáng sớm các thứ khác, có thể vì đầu tuần bạn có thói quen vào việc sớm, còn cuối tuần lại ngủ nướng.\n"
        "- Một **vùng nhạt màu kéo dài theo chiều dọc hoặc ngang** cho thấy khung giờ/ngày đó gần như luôn trống — "
        "đây có thể là khoảng thời gian còn dư địa để tận dụng, hoặc đơn giản là khung giờ không phù hợp với lịch sinh "
        "hoạt (vd giữa đêm) nên không cần cố ép.",
        tip="Khác biểu đồ *Xu hướng tập trung theo khung giờ* (gộp cả tuần thành một con số cho mỗi giờ), bản đồ nhiệt "
            "này **tách riêng theo từng thứ** — rất hữu ích nếu lịch sinh hoạt các ngày trong tuần của bạn khác nhau "
            "rõ rệt (vd đi làm giờ hành chính các ngày thường, nhưng cuối tuần lại rảnh cả buổi sáng).",
        where="Mọi trang báo cáo → Giờ tập trung theo thứ")
    guide_item(
        "histogram.png", "Phân bố độ dài phiên",
        "Biểu đồ cột cho biết bạn thường tập trung theo **phiên ngắn hay phiên dài**, chi tiết hơn nhiều so với "
        "thanh phân bố gọn ở mục Tổng quan. Mỗi cột là **số phiên** có độ dài rơi đúng vào một khoảng 5 phút (vd cột "
        "'25–30′' đếm mọi phiên dài từ 25 đến dưới 30 phút), bắt đầu tính từ **10′** — độ dài tối thiểu để Forest "
        "công nhận một phiên là hợp lệ (phiên ngắn hơn coi như thất bại/huỷ, không có trong dữ liệu).\n\n"
        "- Ba **đường chấm dọc** đặt ở mốc 25′, 50′ và 90′ chính là ranh giới phân chia 4 nhóm Ngắn · Trung bình · "
        "Dài · Rất dài — cùng bộ mốc với thanh phân bố gọn ở Tổng quan, nên hai biểu đồ luôn nhất quán với nhau.\n"
        "- Một **đường gạch đứng** riêng biệt đánh dấu độ dài **trung bình cộng** của toàn bộ phiên trong phạm vi "
        "đang xem — so đường này với hình dạng cột để biết trung bình đang bị kéo lệch bởi số ít phiên rất dài/rất "
        "ngắn hay phản ánh đúng thói quen phổ biến nhất.",
        tip="Cột dồn về **bên phải** (nhiều phiên dài) cho thấy bạn hay vào được trạng thái tập trung sâu ('deep "
            "work') mỗi lần bắt đầu; cột dồn về **bên trái** (nhiều phiên ngắn, sát mốc 10–25′) cho thấy phiên hay bị "
            "ngắt quãng giữa chừng — có thể do môi trường làm việc hay bị gián đoạn.",
        where="Mọi trang báo cáo → Phân bố độ dài phiên")
    guide_item(
        "pie.png", "Phân bổ thời gian",
        "Biểu đồ tròn chia **tỉ trọng tổng thời gian** trong phạm vi đang xem theo Danh mục hoặc Dự án — chọn xem "
        "theo cấp nào bằng nút chuyển ngay trên biểu đồ. Mỗi miếng bánh tương ứng một nhóm/dự án, kèm nhãn phần trăm "
        "và di chuột vào để xem thêm số giờ tuyệt đối.\n\n"
        "- Cách nhanh nhất để trả lời *'trong kỳ này mình dành phần lớn thời gian cho việc gì?'* mà không cần cộng "
        "số thủ công — miếng bánh càng lớn, việc đó càng chiếm ưu thế trong quỹ thời gian tập trung của bạn.\n"
        "- Nếu một Danh mục có nhiều Dự án con nhỏ lẻ, xem ở cấp Danh mục sẽ gọn hơn; muốn biết đích xác dự án nào "
        "trong nhóm đó đang 'ăn' nhiều thời gian nhất thì chuyển sang xem theo Dự án.",
        tip="Đổi qua lại **Danh mục ↔ Dự án** để đi từ cái nhìn tổng quát (bức tranh lớn, ít miếng) tới chi tiết "
            "(nhiều miếng nhỏ, thấy rõ từng đầu việc) mà không cần rời khỏi biểu đồ.",
        where="Báo cáo → Tháng / Tuần / Ngày → Phân bổ thời gian")
    guide_item(
        "table.png", "Bảng số liệu",
        "Một ma trận số liệu dạng bảng: hàng là **Danh mục hoặc Dự án**, cột là các **mốc thời gian** (Tuần hoặc "
        "Tháng, tuỳ trang), mỗi ô giao giữa hàng và cột là tổng số giờ của đúng danh mục/dự án đó trong đúng mốc đó. "
        "Nền mỗi ô được tô đậm/nhạt tương ứng với giá trị (càng nhiều giờ, nền càng đậm) để so sánh nhanh bằng mắt mà "
        "không cần đọc từng con số; cột **Tổng** ở cuối cùng cộng dồn theo hàng.\n\n"
        "- Bảng phù hợp để soi theo chiều **ngang** (một dự án qua nhiều kỳ liên tiếp — đang tăng, giảm hay ổn định?) "
        "hoặc theo chiều **dọc** (trong một kỳ, những dự án nào đang chiếm nhiều thời gian nhất?).\n"
        "- **Dấu ▾ màu đỏ** cạnh một ô đánh dấu kỳ đó **giảm mạnh** — trên 60% — so với kỳ liền trước của cùng dự "
        "án/danh mục đó. Đây là tín hiệu cảnh báo sớm rất hữu ích: một dự án đang bị bỏ bê dần thường xuất hiện dấu "
        "▾ vài kỳ liên tiếp trước khi biến mất hẳn khỏi bảng.",
        tip="Cuộn ngang trong bảng để xem nhiều kỳ hơn cùng lúc; đây là biểu đồ hợp nhất để trả lời câu hỏi 'môn nào "
            "đang tụt dần theo thời gian' vì nó cho thấy toàn bộ lịch sử của từng dự án trên cùng một hàng, thay vì "
            "phải lật qua lại nhiều kỳ riêng lẻ.",
        where="Mọi trang báo cáo → Bảng số liệu")

    st.markdown("### Báo cáo")
    guide_item(
        "day_timeline.png", "Dòng thời gian trong ngày",
        "Một trục ngang trải dài từ 0h đến 24h, tái hiện đúng những gì đã diễn ra trong một ngày cụ thể. Mỗi **khối "
        "đậm màu** là một phiên tập trung thực tế, được tô theo màu của dự án và đặt đúng vị trí giờ nó bắt đầu/kết "
        "thúc; nền phía sau chia sẵn các dải Sáng/Chiều/Tối để dễ định vị thời điểm trong ngày chỉ bằng mắt.\n\n"
        "- **Vùng xám mờ** phủ phía sau các khối màu là khung giờ *điển hình của cùng thứ đó* — tức trung bình cộng "
        "các ngày khác cùng thứ (vd nếu hôm đang xem là Thứ 3, vùng xám phản ánh giờ giấc tập trung thường thấy vào "
        "các Thứ 3 khác trong lịch sử). So khối màu (thực tế hôm nay) với vùng xám (thói quen thường lệ) cho biết "
        "ngay hôm nay bạn vào việc **đúng nhịp** như mọi khi hay **lệch nhịp** hẳn — sớm hơn, muộn hơn, hoặc trống "
        "hẳn một khung giờ vốn hay hoạt động.\n"
        "- Vì mỗi khối tô theo màu dự án, chỉ cần nhìn lướt qua trục là biết trong ngày đã chuyển đổi qua lại giữa "
        "mấy đầu việc, và việc nào chiếm khung giờ nào.",
        tip="Nhiều khối ngắn rải rác khắp trục = ngày bị phân mảnh, hay bị gián đoạn giữa các việc; ngược lại vài "
            "khối dài nằm liền nhau = ngày tập trung sâu, ít bị ngắt quãng. Đây cũng là cách nhanh để phát hiện "
            "'khoảng chết' — những đoạn trục trống hoàn toàn dù vùng xám phía sau cho thấy bình thường hay có hoạt động.",
        where="Báo cáo → Ngày → Tổng quan ngày")
    guide_item(
        "note_editor.png", "Ghi chú ngày (nhật ký)",
        "Thẻ **2 cột**: bên trái là Thứ/ngày, bên phải là appointment lịch (nếu có, đồng bộ từ mục *Dữ liệu đầu "
        "vào*) rồi tới ghi chú — cùng bố cục với mục *Nhật ký* ở mục Tuần/Tháng, dù ở mục Ngày chỉ có "
        "đúng 1 dòng. Mỗi ngày ghi được đúng **một ghi chú** dạng nhật ký tự do — không giới hạn độ dài, không cần "
        "gắn với phiên tập trung nào. Mặc định trang chỉ hiển thị nội dung đã lưu (nếu có) cùng nút **Thêm/Sửa ghi "
        "chú**; bấm vào nút này mới mở ra trình soạn thảo đầy đủ, tránh chiếm chỗ màn hình khi chỉ muốn đọc lại.\n\n"
        "- Trình soạn thảo hỗ trợ **định dạng rich text** đầy đủ: chữ đậm/nghiêng/gạch chân, đổi màu chữ và tô nền, "
        "danh sách gạch đầu dòng hoặc đánh số kèm **thụt lề nhiều cấp**, và chèn liên kết. Vài phím tắt quen thuộc "
        "vẫn dùng được: **⌘/Ctrl + B** để in đậm, **Tab** để thụt lề một mục trong danh sách, **Shift+Tab** để lùi lề.\n"
        "- Ghi chú được lưu **hoàn toàn độc lập với dữ liệu phiên**: một ngày không có phiên tập trung nào vẫn ghi "
        "chú được bình thường (vd để note lý do nghỉ), và việc nạp thêm dữ liệu mới hay xoá phiên trong danh sách đã "
        "xoá **không bao giờ làm mất ghi chú** đã lưu của ngày đó.\n"
        "- Ghi chú (và appointment lịch) của mọi ngày trong kỳ sẽ **tự động hiện lại** gộp thành danh sách ở mục "
        "*Nhật ký* của đúng tuần/tháng chứa ngày đó — không cần mở lại từng ngày để đọc. Bấm vào ô Thứ/ngày của "
        "một dòng bất kỳ trong *Nhật ký* sẽ **nhảy thẳng sang đúng mục Ngày** của trang Báo cáo, đúng ngày đó.",
        tip="Ghi vài dòng ngắn mỗi ngày, kể cả chỉ 1-2 câu, sẽ tích luỹ thành một kho ngữ cảnh rất giá trị: khi xem "
            "lại báo cáo tuần/tháng hay đối chiếu 'Ngày này năm trước', bạn có cả bối cảnh (đang bận gì, tâm trạng "
            "ra sao) đi kèm con số, thay vì chỉ có số giờ trần trụi không nói lên tại sao.",
        where="Báo cáo → Ngày → Ghi chú ngày · Báo cáo → Tháng/Tuần → Nhật ký")
    with st.container(border=True, key="guide_otd"):
        st.markdown(
            "Ngoài dòng thời gian và ghi chú, mục Ngày còn có phần **Ngày này năm trước**: app tự động dò và "
            "khớp **đúng ngày/tháng đó ở tất cả các năm trước** có dữ liệu (vd đang xem 15/3/2026 thì sẽ tìm mọi "
            "15/3 của các năm 2023, 2024, 2025…), gộp lại cả phiên tập trung lẫn ghi chú của những ngày trùng khớp "
            "đó. Với mỗi năm tìm được, mục này hiện nhanh 3 con số (Tổng giờ · Số phiên · Thời gian/phiên trung "
            "bình) và toàn bộ nội dung ghi chú nếu ngày đó bạn có ghi. Nếu năm nào không có dữ liệu (chưa dùng "
            "Forest, hoặc đúng ngày đó bạn không hoạt động), năm đó đơn giản sẽ không xuất hiện trong danh sách. "
            "Mục này càng ngày càng phong phú theo thời gian — dữ liệu tích luỹ càng nhiều năm, càng có nhiều mốc "
            "để so sánh 'năm nay so với đúng ngày này các năm trước thì sao', một dạng hoài niệm có số liệu đi kèm.")

    st.markdown("### Nhật ký đọc sách")
    guide_item(
        "reading_log.png", "Nhật ký đọc sách",
        "Trang riêng dành cho việc đọc các cuốn sách **theo trình tự, đọc dở rồi đọc tiếp**, **gộp 2 nguồn dữ "
        "liệu**: phiên tập trung Forest (mặc định gom mọi Dự án thuộc nhóm `Reading`, khác với các dự án lặp định "
        "kỳ như đọc báo/tạp chí không tính là 'một cuốn') và phần/chương đã đọc nạp từ **Apple Reminders** (xem "
        "mục *Dữ liệu đầu vào*). Một cuốn sách chỉ cần có mặt ở **một trong hai nguồn** là đủ để lên trang — cột "
        "thuộc nguồn còn thiếu hiện dấu **\"—\"**. Reminder List tên bắt đầu bằng \"Gundam\" **không tính vào "
        "trang này** — có tab **Gundam** riêng. Trang gồm 3 phần: số liệu tổng ở trên cùng, một **timeline trình "
        "tự đọc** thể hiện thứ tự các cuốn đã/đang đọc (khối màu xanh teal = đang đọc dở, khối xám = đã đọc "
        "xong), và bảng chi tiết liệt kê từng cuốn với các cột:\n\n"
        "- **Bắt đầu / Gần nhất / Số ngày**: ngày hoạt động sớm nhất/gần nhất và số ngày giữa 2 mốc đó cho cuốn "
        "đó, tính theo **cả 2 nguồn** (phiên Forest hoặc phần Reminders hoàn thành, lấy mốc sớm/muộn hơn) — luôn "
        "tính được kể cả với cuốn chỉ theo dõi qua Reminders, chưa từng bấm giờ Forest.\n"
        "- **Ngày đọc / Tổng giờ / Số phiên / Giờ tuần**: các số liệu theo phiên Forest — hiện \"—\" nếu cuốn đó "
        "chỉ theo dõi qua Reminders, chưa có phiên Forest nào.\n"
        "- **Số phần đã đọc / Phần gần nhất**: số phần/chương đã tick hoàn thành trong Reminders và tên phần gần "
        "nhất — hiện \"—\" nếu cuốn đó chưa có dữ liệu Reminders.\n"
        "- **Trạng thái**: *Đang đọc* nếu có hoạt động (phiên Forest **hoặc** phần Reminders hoàn thành) trong "
        "khoảng ~2 tuần gần nhất, ngược lại tự động chuyển thành *Đã xong* — không cần tự đánh dấu tay.",
        tip="Nếu có dự án đọc định kỳ không phải sách (vd tạp chí, báo hàng ngày) đang bị lẫn vào trang này, loại nó "
            "ra bằng cấu hình `BOOKS_GROUP`/`BOOKS_EXCLUDE` ở đầu file `app.py`. Lưu ý trang này **chỉ đọc, không "
            "ghi** — mọi thao tác chỉnh sửa dữ liệu (phân loại, xoá phiên, nạp lại Reminders…) đều thực hiện ở "
            "trang Chuẩn bị dữ liệu.",
        where="Trang Nhật ký đọc sách")
    guide_item(
        "reading_journal.png", "Đọc sách (Báo cáo → Ngày/Tuần/Tháng/Dự án)",
        "Phần/chương sách (và Gundam) đã đọc/xem (nạp từ Apple Reminders) còn hiện xen kẽ vào các trang báo cáo "
        "khác, gộp chung với ghi chú/lịch Work theo thứ tự cố định **Lịch → Đọc sách → Ghi chú**:\n\n"
        "- **Mục Ngày**: thẻ **Ghi chú ngày** (không còn khung viền quanh thẻ) hiện lần lượt chip lịch (kèm "
        "nhãn nhỏ \"Lịch\"), chip các phần đã đọc trong ngày (nhóm theo tên sách/series nếu đọc nhiều cuốn cùng "
        "ngày), rồi mới tới ghi chú.\n"
        "- **Mục Tuần/Tháng**: gộp thẳng vào thẻ **Nhật ký** (không còn thẻ riêng) — mỗi dòng ngày theo cùng "
        "thứ tự Lịch → Đọc sách → Ghi chú, hiện cho mọi ngày có ít nhất 1 trong 3 nguồn, bấm vào Thứ/ngày để nhảy "
        "sang đúng mục Ngày hôm đó.\n"
        "- **Mục Dự án**: khi Dự án đang xem khớp tên với 1 cuốn sách đã có dữ liệu Reminders (so tên "
        "Dự án với phần \"Tên sách\" trong \"Tác giả - Tên sách\"), thêm mục **Nhật ký đọc** hiện trọn lịch sử "
        "phần đã đọc của đúng cuốn đó.",
        tip="Cần tải file ở mục *Tải lên từ Reminder* (Chuẩn bị dữ liệu → Dữ liệu đầu vào) trước — chưa tải lần "
            "nào thì các mục trên đơn giản không hiện gì, không ảnh hưởng phần còn lại của trang.",
        where="Báo cáo → Ngày → Ghi chú ngày · Báo cáo → Tháng/Tuần → Nhật ký · Báo cáo → Dự án → Nhật ký đọc")
    guide_item(
        "gundam.png", "Gundam",
        "Tab riêng cho việc xem các series anime Gundam, dựng y hệt cấu trúc trang **Nhật ký đọc sách** (số liệu "
        "tổng, timeline trình tự xem, bảng chi tiết từng series) nhưng đổi chữ cho đúng ngữ cảnh (\"series\" thay "
        "\"cuốn sách\", \"xem\"/\"tập\" thay \"đọc\"/\"phần\"). Nguồn dữ liệu:\n\n"
        "- **Reminder List tên \"Gundam - Tên series\"** (vd \"Gundam - Gundam Wing\") — mỗi list là 1 series, "
        "mỗi Reminder đã tick hoàn thành là 1 tập đã xem, nạp qua mục *Tải lên từ Reminder* giống hệt sách.\n"
        "- **Phiên Forest gắn tag \"Gundam\"** — vì không tách Dự án riêng theo từng series, app tự **suy ra series "
        "đang xem của mỗi ngày có phiên Gundam** bằng cách ghép với lần hoàn thành reminder (ở bất kỳ series nào) "
        "**gần ngày đó nhất** (trước hoặc sau). Ví dụ đang xem dở Gundam Wing thì mọi phiên Forest tag Gundam ở "
        "những ngày gần các lần tick hoàn thành tập Gundam Wing sẽ được tính vào series đó.",
        tip="Vì thời gian Forest được SUY RA theo ngày gần nhất chứ không tách chính xác theo series, số giờ mỗi "
            "series chỉ mang tính tương đối — chính xác nhất khi xem lần lượt từng series (không xen kẽ nhiều "
            "series trong cùng vài ngày).",
        where="Trang Gundam")

    st.markdown("### Chuẩn bị dữ liệu")
    guide_item(
        "prep_data_input.png", "Dữ liệu đầu vào",
        "Ba nguồn dữ liệu, gộp chung một mục, mỗi nguồn một tab riêng cho gọn:\n\n"
        "- **Tải lên từ Forest**: nơi duy nhất **nạp dữ liệu phiên tập trung** vào app — tải lên file **CSV xuất "
        "trực tiếp từ app Forest** (mục xuất dữ liệu trong Forest, không cần chỉnh sửa gì trước). App tự nhận diện "
        "các cột cần thiết (Tag/Project tương ứng Dự án, Start Time/End Time để tính thời lượng và ngày giờ, cột "
        "Is Success để lọc), **tự động bỏ qua các phiên thất bại và các dòng gắn tag 'unset'** (không có dự án cụ "
        "thể), rồi gộp toàn bộ phiên hợp lệ vào dữ liệu đang có sẵn theo cơ chế **chống trùng lặp** dựa trên thời "
        "điểm diễn ra của từng phiên. Sau khi tải lên, app báo rõ ràng đã đọc được bao nhiêu phiên hợp lệ và đã bỏ "
        "qua bao nhiêu (thất bại/trùng lặp/unset).\n"
        "- **Đồng bộ lịch** *(tuỳ chọn)*: kéo các appointment (cuộc hẹn/họp) từ lịch **\"Work\"** trong Apple "
        "Calendar về app qua **CalDAV** — kết nối trực tiếp tài khoản iCloud, không cần xuất file thủ công. Sau khi "
        "đồng bộ, appointment hiện dưới dạng chip (giờ bắt đầu + tiêu đề) ngay trong thẻ **Ghi chú ngày** (Báo cáo "
        "ngày) và xen kẽ vào từng dòng ngày ở mục *Nhật ký* (mục Tuần/Tháng của Báo cáo), kể cả ngày không có ghi chú viết "
        "tay. Mỗi lần đồng bộ cũng **dọn sạch appointment đã bị xoá** trên Apple Calendar khỏi app, không chỉ thêm "
        "mới — nên kết quả luôn khớp đúng lịch thật tại thời điểm đồng bộ. Có thêm 1 mục **Đồng bộ khoảng ngày khác "
        "(nâng cao)** thu gọn sẵn — chọn tay Từ ngày/Đến ngày để lấp dữ liệu lịch cũ hơn (vd để phục vụ mục *Ngày "
        "này năm trước*), không cần dùng thường xuyên.\n"
        "- **Tải lên từ Reminder** *(tuỳ chọn)*: nạp tiến độ đọc sách/xem Gundam từ **Apple Reminders** — tải lên "
        "file `list|title|completed_date` do 1 Shortcut trên iPhone/Mac xuất ra (xem mục *Gundam* và *Nhật ký đọc "
        "sách* phía trên để biết quy ước đặt tên list, cách tạo Shortcut xem hướng dẫn cụ thể trong README). Mỗi "
        "**Reminder List** là 1 cuốn sách/series, mỗi **Reminder đã tick hoàn thành** trong list đó là 1 phần/tập "
        "đã đọc/xem. Không cần kết nối iCloud/CalDAV gì — Shortcut đọc thẳng dữ liệu Reminders trên máy nên thấy "
        "được cả list chỉ lưu \"Trên iPhone của tôi\" (cục bộ, không đồng bộ iCloud). Mỗi lần tải file lên sẽ "
        "**thay thế toàn bộ** dữ liệu cũ bằng nội dung file mới — an toàn khi Reminders có thay đổi giữa các lần.",
        tip="Với **Tải lên từ Forest**: cứ xuất CSV mới bất cứ khi nào cần rồi tải lên thẳng, không cần lọc hay cắt "
            "bớt file trước — phiên đã có từ lần tải trước sẽ không bị nhân đôi, và những phiên bạn đã chủ động xoá "
            "cũng sẽ không bị nạp lại. Với **Đồng bộ lịch**: cần tạo **App-Specific Password** tại appleid.apple.com "
            "và điền vào secrets của app trước khi dùng (xem hướng dẫn chi tiết trong README, mục \"Đồng bộ lịch & "
            "đọc sách\"); chưa cấu hình thì mục này chỉ báo lỗi khi bấm nút, không ảnh hưởng phần còn lại của app.",
        where="Chuẩn bị dữ liệu → Dữ liệu đầu vào")
    guide_item(
        "prep_classify.png", "Phân loại",
        "Nơi gán **Danh mục (nhóm lớn)** cho từng **Dự án** (chính là mỗi tag riêng biệt trong Forest). Ví dụ có "
        "thể gộp hai Dự án 'Lập trình' và 'Tiếng Anh' vào chung một Danh mục 'Học tập', trong khi Dự án 'Đọc sách' "
        "lại thuộc Danh mục 'Giải trí' — việc phân nhóm này hoàn toàn tự do theo cách bạn muốn nhìn dữ liệu của mình.\n\n"
        "- Để một Dự án **trống Danh mục** nghĩa là dự án đó tự đứng riêng như một nhóm của chính nó, không gộp "
        "chung với dự án nào khác — phù hợp với các dự án đơn lẻ không cần nhóm.\n"
        "- Việc phân loại này ảnh hưởng tới **mọi** biểu đồ và bảng trong toàn bộ app mỗi khi bạn chọn xem theo "
        "**Danh mục** thay vì Dự án — đổi phân loại ở đây sẽ làm thay đổi cách các biểu đồ đó nhóm cột/miếng bánh/màu "
        "sắc ngay từ lần xem tiếp theo, không cần nạp lại dữ liệu.",
        tip="Đặt nhóm hợp lý ngay từ đầu, trước khi có quá nhiều dự án nhỏ lẻ, sẽ giúp các biểu đồ tổng hợp (như "
            "biểu đồ tròn Phân bổ thời gian hay Xu hướng theo thời gian) gọn gàng và dễ đọc hơn hẳn — quá nhiều "
            "danh mục nhỏ rời rạc sẽ làm biểu đồ rối mắt, khó nhìn ra bức tranh lớn.",
        where="Chuẩn bị dữ liệu → Phân loại")
    guide_item(
        "prep_backup.png", "Sao lưu, khôi phục & làm mới",
        "Mục quản lý toàn bộ vòng đời dữ liệu, gồm 3 thao tác:\n\n"
        "- **Tải bản sao lưu**: đóng gói **toàn bộ** dữ liệu app đang lưu trữ thành **một file .zip** duy nhất — "
        "bao gồm dữ liệu phiên tập trung, bảng phân loại Danh mục/Dự án, danh sách các phiên đã xoá (để tránh nạp "
        "nhầm lại khi tải CSV mới từ Forest), và **toàn bộ ghi chú ngày** đã viết. Tên file tự kèm ngày giờ xuất "
        "để dễ phân biệt giữa nhiều bản sao lưu theo thời gian.\n"
        "- **Khôi phục**: tải một file .zip đã sao lưu trước đó lên để phục hồi lại **đúng nguyên trạng** tại thời "
        "điểm sao lưu — dùng khi chuyển sang máy mới, đổi trình duyệt, hoặc muốn quay lại một mốc dữ liệu cũ.\n"
        "- **Làm mới**: xoá **toàn bộ** dữ liệu app đang lưu trữ để bắt đầu lại từ đầu — thao tác này không thể hoàn "
        "tác nên bắt buộc phải tick ô xác nhận trước khi thực hiện.",
        tip="Dữ liệu được lưu trên Supabase (bền vững qua các lần khởi động lại/redeploy), nhưng vẫn nên tải bản "
            "sao lưu **định kỳ** (vd mỗi lần vừa import dữ liệu mới xong) làm lớp an toàn thứ hai, phòng trường "
            "hợp thao tác nhầm hoặc sự cố ngoài ý muốn.",
        where="Chuẩn bị dữ liệu → Quản lý hệ thống")