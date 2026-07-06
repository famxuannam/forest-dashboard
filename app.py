import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import os
import io
import json
import base64
import time
import zipfile
import plotly.express as px
import plotly.graph_objects as go
import altair as alt
import colorsys
import hashlib
import re
from itertools import groupby
from html import escape as html_escape, unescape as html_unescape
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
    lần Streamlit rerun, iframe bị tạo lại và mất style. Chỉ gọi khi đang mở ô soạn.
    Iframe không thấy được :root CSS var của trang chính -> ở dark mode phải tự thay thế
    literal + bơm thêm rule riêng (icon toolbar Quill mặc định stroke/fill đen, vô hình
    trên nền tối nếu không override)."""
    _quill_css = QUILL_CSS.replace("#00a3ad", ACCENT)
    if IS_DARK:
        _quill_css = (
            _quill_css.replace("#fafafa", "#2c2c2e")
            .replace("#e2e2e7", "#3a3a3c")
            .replace("#1d1d1f", "#f2f2f7")
            .replace("#aeaeb2", "#636366")
            + "\n.ql-editor { background:#1c1c1e; }"
            + "\n.ql-snow .ql-stroke { stroke:#d1d1d6; }"
            + "\n.ql-snow .ql-fill { fill:#d1d1d6; }"
            + "\n.ql-snow .ql-picker { color:#d1d1d6; }"
        )
    js = (
        "<script>\n"
        "const CSS = " + json.dumps(_quill_css) + ";\n"
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


def _note_plain_text(html_content):
    """Text thuần từ ghi chú Quill: bỏ thẻ HTML + giải mã entity (&nbsp;, &amp;...) -- dùng để
    tìm kiếm/trích đoạn, khác _note_is_empty() chỉ cần biết rỗng hay không nên chưa unescape."""
    return re.sub(r"\s+", " ", html_unescape(re.sub(r"<[^>]+>", " ", str(html_content or "")))).strip()


def _note_snippet(html_content, query, radius=60):
    """Đoạn trích văn bản thuần quanh từ khớp đầu tiên (dùng cho trang Tìm kiếm); không khớp
    hoặc không có query thì trả về 120 ký tự đầu."""
    txt = _note_plain_text(html_content)
    idx = txt.lower().find(query.lower()) if query else -1
    if idx == -1:
        return txt[:120] + ("…" if len(txt) > 120 else "")
    start, end = max(0, idx - radius), min(len(txt), idx + len(query) + radius)
    return ("…" if start > 0 else "") + txt[start:end] + ("…" if end < len(txt) else "")

# --- CẤU HÌNH ---
# Tên file dùng làm tên thành viên bên trong .zip Sao lưu/Khôi phục (mục "Quản lý hệ thống")
# -- dữ liệu thật luôn nằm trên Supabase, các tên này không còn là đường dẫn đọc/ghi local.
DB_FILE = "database.csv"
MAPPING_FILE = "mapping.csv"
DELETED_FILE = "deleted.csv"  # khoá thời gian của các phiên đã xoá -> không nạp lại
NOTES_FILE = "notes.csv"  # ghi chú/nhật ký theo ngày
QUICK_NOTES_FILE = "quick_notes.csv"  # ghi chú nhanh từ Shortcut iOS, đứng độc lập với notes
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

# "Bảng vàng": số ngày có dữ liệu tối thiểu để 1 Dự án/Nhóm đủ điều kiện có kỷ lục riêng (mục
# _compute_alltime_records()) -- ngưỡng để tránh dự án/nhóm mới thử vài ngày đã có "kỷ lục".
RECORD_MIN_DAYS = 5

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


# 14 lựa chọn màu accent (tab Tuỳ biến → "4. Giao diện"), người dùng tự chọn từ bản mockup --
# xếp theo thứ tự hue tăng dần (đỏ/cam/vàng -> xanh lá -> xanh dương -> tím) cho có thứ tự hợp
# lý khi hiện thành lưới, riêng "Than chì" (gần như xám) xếp cuối vì không thuộc dải màu nào.
# Lưu ý: 3 màu đầu (Hồng đào/Cam cháy/Vàng nắng) CỐ Ý trùng vùng tông app đang dùng cho cảnh báo
# (cam, NUDGE_TONES "warn") / chuỗi đứt (đỏ, "neutral") -- người dùng đã xác nhận muốn có nhóm
# màu này dù biết sẽ trông gần giống 2 trạng thái đó nếu chọn làm accent.
ACCENT_PRESETS = {
    "Hồng đào": "#e25a66",
    "Cam cháy": "#dc6018",
    "Vàng nắng": "#e7bf23",
    "Xanh lá": "#34c759",
    "Ngọc lục bảo": "#00b386",
    "Bạc hà đậm": "#0a7671",
    "Xanh ngọc": "#00a3ad",      # mặc định, giữ NGUYÊN màu hiện tại
    "Xanh lơ": "#32ade6",
    "Xanh dương": "#007aff",
    "Xanh hải quân đậm": "#203a6f",
    "Chàm": "#5856d6",
    "Tím than": "#2d2768",
    "Tím": "#af52de",
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


def _brighten(hexcode, target_l=0.68):
    """Bản sáng hơn (giữ hue/saturation, kéo lightness lên tối thiểu target_l) -- đối xứng với
    _darken() nhưng cho DARK MODE: nền tint accent trong dark mode tối hơn nền light, nên
    chữ/icon đặt trên đó cần SÁNG hơn accent gốc để đọc được, thay vì tối hơn."""
    h = hexcode.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    hue, l, s = colorsys.rgb_to_hls(r, g, b)
    return _hsl_hex(hue, s, max(l, target_l))


def _readable_text(hexcode):
    """Chữ trắng hay đen đọc rõ hơn trên nền màu này (độ chói YIQ) -- dùng cho tên màu hiện
    ngay trên nút accent (mục "4. Giao diện"), tự thích ứng khi thêm/bớt preset sau này."""
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


# Cờ dark mode -- đọc st.context.theme.type (Streamlit 1.58+, đã xác nhận có sẵn Ở CẤP MODULE,
# TRƯỚC cả st.set_page_config(), vì được gửi kèm ngay trong request rerun từ trình duyệt, không
# phải lấy lazy). Tự bọc lỗi vì cũng là tính năng optional (bản Streamlit cũ hơn không có
# st.context.theme) -- lỗi/None -> coi là light, không crash app. Caveat CHÍNH THỨC của
# Streamlit (github issue #11920): giá trị có thể sai/None ở LẦN LOAD ĐẦU TIÊN của session, và
# trễ đúng 1 rerun khi người dùng đổi theme qua menu Settings ⋮ -- chấp nhận được (tự đúng lại
# ngay rerun kế tiếp), không có cách nào khắc phục vì Streamlit không có API đổi theme runtime.
try:
    IS_DARK = st.context.theme.type == "dark"
except Exception:
    IS_DARK = False

# Accent (màu nhấn) đang chọn -- fallback Teal mặc định nếu chưa từng chọn hoặc lỗi. PHẢI tính
# TRƯỚC _SESSION_COLORS = _teal_shades(5) (dưới đây) vì đó là câu lệnh cấp module chạy ngay khi
# import, sớm hơn cả st.set_page_config()/cổng kiểm tra secrets Supabase.
_accent_hex = _cached_settings().get("accent_hex", "#00a3ad")
if _accent_hex not in ACCENT_PRESETS.values():   # giá trị lạ (hỏng/ghi tay) -> fallback an toàn
    _accent_hex = "#00a3ad"
ACCENT = _accent_hex
ACCENT_RGB = _hex_rgb_str(ACCENT)
# ACCENT_DARK = "accent tương phản trên nền tint accent nhạt". Ở dark mode, nền tint đó lại
# TỐI hơn nền light -> cần chữ/icon SÁNG hơn accent gốc thay vì tối hơn, nên đổi hàm theo IS_DARK
# (khác bản light-only trước đây luôn gọi _darken). Tên biến/tên CSS var --accent-dark giữ
# nguyên -- mọi nơi đang dùng (chip.tw, guide alert, NUDGE_TONES "good") tự đúng cả 2 chế độ.
ACCENT_DARK = _brighten(ACCENT) if IS_DARK else _darken(ACCENT)
TEAL_HUE = _hex_hue(ACCENT)  # giữ tên biến cũ -- mọi nơi đang dùng TEAL_HUE không cần sửa


def _teal_shades(n, l_lo=None, l_hi=None):
    """Sinh n sắc độ teal (cùng hue với accent #00a3ad) từ nhạt (l_lo) đến đậm (l_hi)
    -> dùng chung cho các bảng nhiệt (Biểu đồ lịch, Giờ tập trung theo thứ, thanh Phân bổ
    độ dài phiên) để đồng bộ một họ màu thay vì mỗi nơi một tông riêng.
    Mặc định (không truyền l_lo/l_hi) ĐẢO CHIỀU ramp khi dark: trên nền tối, teal L thấp
    (đậm ở light) gần như tàng hình còn L cao (nhạt ở light) nổi bật nhất -- nếu giữ nguyên
    chiều, "nhiều giờ" sẽ trông như "ít giờ". Dark dùng dải sáng hơn hẳn (0.22->0.72, mờ tối
    -> sáng rực) thay vì lật ngược y hệt dải light (sẽ ra màu quá tối, khó phân biệt nền)."""
    if l_lo is None:
        l_lo = 0.22 if IS_DARK else 0.90
    if l_hi is None:
        l_hi = 0.72 if IS_DARK else 0.26
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


@st.cache_data(ttl=30)
def load_quick_notes():
    """Ghi chú nhanh (đứng độc lập với Ghi chú chính, không tự gộp), ghi thẳng bởi Shortcut iOS
    qua REST API (KHÔNG qua app, xem guide_item "Ghi chú nhanh"). ttl=30 (khác load_notes() cache
    vô hạn) vì bảng này có thể bị
    thay đổi từ NGOÀI vòng save_*/xoá của app -- vòng đó tự gọi st.cache_data.clear(), nhưng 1
    INSERT từ Shortcut thì không, nên phải tự hết hạn theo thời gian để quick note mới hiện ra
    mà không cần chờ 1 thao tác lưu khác trong app."""
    sb = _get_supabase()
    res = sb.table("quick_notes").select("id,ts,note_text").order("ts").execute()
    cols = ["id", "Thời gian", "Nội dung"]
    if not res.data:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(res.data).rename(columns={"ts": "Thời gian", "note_text": "Nội dung"})[cols]
    df["Thời gian"] = pd.to_datetime(df["Thời gian"])
    return df


def delete_quick_note(note_id):
    """Xoá 1 quick note lẻ (vd gõ nhầm trên Shortcut) -- nút xoá trên từng chip ở render_note_editor()."""
    _get_supabase().table("quick_notes").delete().eq("id", int(note_id)).execute()
    st.cache_data.clear()


def update_quick_note(note_id, text):
    """Sửa nội dung 1 quick note lẻ tại chỗ (không đụng tới giờ "ts" -- giờ là lúc note được tạo,
    không phải lúc sửa). Rỗng (sau khi strip) = xoá luôn dòng đó, nhất quán với hành vi save_note()
    của Ghi chú chính (rỗng = xoá)."""
    text = str(text).strip()
    if not text:
        delete_quick_note(note_id)
        return
    _get_supabase().table("quick_notes").update({"note_text": text}).eq("id", int(note_id)).execute()
    st.cache_data.clear()


def save_quick_notes_bulk(df):
    """Ghi đè toàn bộ quick note (dùng khi Khôi phục từ bản sao lưu)."""
    sb = _get_supabase()
    _sb_delete_all("quick_notes", "id")
    if not df.empty:
        recs = [{"ts": _fmt_ts(r["Thời gian"]), "note_text": str(r["Nội dung"])} for r in df.to_dict("records")]
        if recs:
            sb.table("quick_notes").insert(recs).execute()
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


def _today_vn():
    """"Hôm nay" theo giờ Việt Nam (APP_TZ) -- KHÔNG dùng date.today() trần ở bất kỳ đâu trong
    app: hàm đó trả về ngày theo múi giờ hệ thống máy chủ chạy Streamlit, rất có thể là UTC khi
    deploy production (lệch 7 tiếng so với Việt Nam). Trong khung giờ 17:00-24:00 UTC mỗi ngày
    (đúng 00:00-07:00 giờ Việt Nam hôm sau), date.today() trên server UTC vẫn trả về NGÀY HÔM
    TRƯỚC dù người dùng ở Việt Nam đã sang ngày mới -- y hệt lỗi đã tìm và sửa ở
    format_relative(), áp dụng cho MỌI chỗ cần biết "hôm nay" (mặc định trang Hôm nay, kỳ hiện
    tại của Tuần/Tháng/Năm, nhắc sao lưu...)."""
    return datetime.now(APP_TZ).date()


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


# --- ĐỒNG BỘ NHANH (Shortcut iOS -> Supabase Storage -> 1 nút trong app) ---
# Thay cho việc tải tay 2 file (Forest CSV + Reminder backup) rồi bấm "Đồng bộ lịch" riêng: Shortcut
# ở iOS (chạy từ share sheet khi Export Forest) gộp cả 2 file rồi upload thẳng lên 1 bucket Storage
# qua HTTP request (không cần app can thiệp) -- app chỉ cần quét bucket này, không đọc trực tiếp
# iCloud Drive được vì server chạy từ xa, không có filesystem chung với máy/điện thoại người dùng.

def _sync_bucket_name():
    return st.secrets.get("SUPABASE_SYNC_BUCKET", "sync-uploads")

def _list_sync_files():
    """Liệt kê file trong bucket Storage dùng cho Đồng bộ nhanh, mới nhất trước (theo created_at).
    Trả về [] nếu bucket chưa tạo/chưa cấu hình -- tính năng tuỳ chọn, không chặn phần còn lại của
    tab Dữ liệu đầu vào khi chưa dùng tới."""
    try:
        files = _get_supabase().storage.from_(_sync_bucket_name()).list()
    except Exception:
        return []
    return sorted((f for f in files if f.get("name")), key=lambda f: f.get("created_at") or "", reverse=True)

def _latest_sync_file(files, prefix):
    """files đã sort mới nhất trước (xem _list_sync_files) -> file khớp ĐẦU TIÊN chính là mới nhất."""
    prefix = prefix.lower()
    for f in files:
        if f["name"].lower().startswith(prefix):
            return f
    return None

def sync_from_storage(cal_start, cal_end):
    """Đồng bộ nhanh 1 nút cho luồng Shortcut iOS: lấy file Forest CSV + Reminder backup mới nhất
    (tên bắt đầu bằng "forest"/"reminder") từ bucket Supabase Storage, nạp vào DB y hệt luồng tải
    tay (Forest: cộng thêm + bỏ trùng/đã xoá; Reminder: thay thế toàn bộ), rồi đồng bộ luôn lịch
    Work qua CalDAV. Xoá các file CŨ HƠN cùng loại trong bucket SAU KHI nạp thành công (giữ đúng 1
    file mới nhất mỗi loại) để bucket không phình to qua thời gian -- không xoá nếu file lỗi/thiếu
    cột, để còn nguyên đó cho lần thử lại sau khi đã sửa Shortcut. Trả về dict kết quả để hiển thị,
    không raise ra ngoài UI."""
    result = {"forest": None, "forest_error": None, "reading": None, "reading_error": None,
              "calendar": None, "calendar_error": None, "error": None}
    try:
        bucket = _get_supabase().storage.from_(_sync_bucket_name())
        files = _list_sync_files()
    except Exception as e:
        result["error"] = f"Không kết nối được Supabase Storage: {e}"
        return result

    forest_meta = _latest_sync_file(files, "forest")
    reading_meta = _latest_sync_file(files, "reminder")
    to_delete = []

    if forest_meta:
        try:
            raw = bucket.download(forest_meta["name"])
            df_new, stats, missing = parse_forest_csv(io.BytesIO(raw))
            if missing:
                result["forest_error"] = "Thiếu cột: " + ", ".join(missing)
            elif df_new is None or df_new.empty:
                result["forest"] = 0
            else:
                deleted = load_deleted()
                if not deleted.empty:
                    del_keys = set(zip(deleted['Thời gian bắt đầu'].map(_fmt_ts),
                                       deleted['Thời gian kết thúc'].map(_fmt_ts)))
                    keep = [(s, e) not in del_keys for s, e in
                            zip(df_new['Thời gian bắt đầu'].map(_fmt_ts), df_new['Thời gian kết thúc'].map(_fmt_ts))]
                    df_new = df_new[keep]
                db = load_db()
                before = len(db)
                combined = pd.concat([db, df_new])
                combined['Thời gian bắt đầu'] = combined['Thời gian bắt đầu'].map(_fmt_ts)
                combined['Thời gian kết thúc'] = combined['Thời gian kết thúc'].map(_fmt_ts)
                combined = combined.drop_duplicates(subset=['Thời gian bắt đầu', 'Thời gian kết thúc'], keep='first')
                save_db(combined)
                result["forest"] = len(combined) - before
            if not result["forest_error"]:
                to_delete += [f["name"] for f in files
                              if f["name"].lower().startswith("forest") and f["name"] != forest_meta["name"]]
        except Exception as e:
            result["forest_error"] = str(e)

    if reading_meta:
        try:
            raw = bucket.download(reading_meta["name"])
            rl_df, rl_stats, rl_missing = parse_reading_log_shortcut_csv(io.BytesIO(raw))
            if rl_missing:
                result["reading_error"] = "Thiếu cột: " + ", ".join(rl_missing)
            elif rl_df.empty:
                result["reading"] = 0
            else:
                save_reading_log_bulk(rl_df)
                result["reading"] = len(rl_df)
            if not result["reading_error"]:
                to_delete += [f["name"] for f in files
                              if f["name"].lower().startswith("reminder") and f["name"] != reading_meta["name"]]
        except Exception as e:
            result["reading_error"] = str(e)

    if to_delete:
        try:
            bucket.remove(to_delete)
        except Exception:
            pass

    n_cal, err_cal = sync_work_calendar(cal_start, cal_end)
    result["calendar"] = n_cal
    result["calendar_error"] = err_cal
    return result


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
    db['Năm'] = db['Thời gian bắt đầu'].dt.strftime('%Y')
    db['Khung giờ'] = db['Thời gian bắt đầu'].dt.hour
    
    db['Thứ'] = db['Thời gian bắt đầu'].dt.day_name().map(VN_DAYS)
    return db

def add_total_labels(fig, df, x_col, y_col):
    totals = df.groupby(x_col)[y_col].sum().reset_index()
    _txt = "#f2f2f7" if IS_DARK else "#1d1d1f"
    fig.add_trace(go.Scatter(
        x=totals[x_col], y=totals[y_col], mode='text', text=totals[y_col].round(1).astype(str),
        textposition='top center', showlegend=False, hoverinfo='skip', textfont=dict(color=_txt, size=13)
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
        line=dict(color=("#f2f2f7" if IS_DARK else "#1d1d1f"), width=2.5, dash='dot'),
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
    _line_col = "rgba(255,255,255,0.28)" if IS_DARK else "rgba(0,0,0,0.18)"
    d = first_mon
    while d <= dmax + pd.Timedelta(days=1):
        fig.add_vline(x=(d - pd.Timedelta(hours=12)), line_width=1, line_dash="dash", line_color=_line_col)
        d += pd.Timedelta(days=7)
    fig.update_xaxes(tickformat="%d/%m")  # Việt hoá: ngày/tháng dạng số, bỏ tên tháng tiếng Anh
    return fig

def format_plotly_fig(fig, is_pie=False):
    fig.update_layout(
        dragmode=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        # KHÔNG đặt color tường minh ở đây -- theme="streamlit" (mặc định, mọi call site
        # st.plotly_chart trong app) tự lấy đúng textColor từ config theme đang active
        # ([theme]/[theme.dark]) cho phần chữ KHÔNG bị override tường minh ở nơi khác.
        font=dict(family="-apple-system, BlinkMacSystemFont, sans-serif"),
        # Legend nằm ngang phía trên biểu đồ (giống app Xcode) -> không bị cắt khi co hẹp
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0, xanchor='left', title_text=''),
        # r=28: chừa chỗ cho nhãn trục hoành CUỐI (vd '28/06') -> không bị tràn/cắt chữ ở
        # mép phải canvas, vì nhãn căn giữa cột cuối nên phần nửa sau dễ vượt khỏi biên vẽ.
        margin=dict(t=10, r=28),
        xaxis=dict(automargin=True),
    )
    if is_pie:
        # Đường viền phân tách các miếng cho gọn (bóng cả vòng thêm bằng CSS g.pielayer) -- khớp
        # màu nền thẻ (--card) đổi theo IS_DARK để viền "hoà" vào nền thay vì luôn trắng cứng.
        _pie_line = "#2c2c2e" if IS_DARK else "#ffffff"
        fig.update_traces(marker=dict(line=dict(color=_pie_line, width=2)),
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
    """Chọn ngày: ◀ ▶ nhảy tới ngày CÓ hoạt động liền kề (▶ còn nhảy tới hi/hôm nay ở bước cuối
    nếu hôm nay chưa có phiên -- xem _next_candidates) + lịch chọn ngày. Đọc query param
    ?day=YYYY-MM-DD 1 lần khi session mới (giống hệt cách "nav" đã làm ở st.query_params["nav"])
    -- cho phép link từ Nhật ký (tuần/tháng) nhảy thẳng tới đúng ngày.

    hi lấy max(ngày có phiên gần nhất, HÔM NAY THẬT) -- không chỉ ngày có phiên gần nhất: nếu
    chưa log phiên nào hôm nay (vd mới mở app đầu ngày để xem lịch/tham khảo trước khi lên kế
    hoạch), hôm nay vẫn chưa có trong active_days, nhưng trang "Hôm nay" phải mặc định VÀO ĐÚNG
    hôm nay (đúng tên trang) và lịch chọn ngày phải cho chọn được tới hôm nay, thay vì kẹt ở
    ngày cuối cùng có dữ liệu (có thể là hôm qua hoặc xa hơn).

    Không còn nút "Ngày gần nhất" riêng -- việc "về hôm nay" giờ nằm ở chỗ bấm lại mục "Hôm nay"
    trên nav bar (xem callback gắn ở st.segmented_control(key="nav")), nút riêng trong trang là
    thừa khi đã có lối tắt đó."""
    pk = "day_pick"
    lo, hi = active_days[0], max(active_days[-1], _today_vn())
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

    def _next_candidates(cur):
        # Ngày CÓ hoạt động liền kề như cũ, CỘNG THÊM hi (hôm nay) làm nấc cuối nếu hôm nay
        # chưa có phiên (nên không nằm trong active_days) -- không có bước này thì ▶ sẽ kẹt ở
        # ngày hoạt động gần nhất, không bao giờ tới được hôm nay thật.
        cand = [d for d in active_days if d > cur]
        if hi not in active_days and hi > cur:
            cand.append(hi)
        return cand

    def _prev():
        cand = [d for d in active_days if d < st.session_state[pk]]
        if cand: st.session_state[pk] = cand[-1]

    def _next():
        cand = _next_candidates(st.session_state[pk])
        if cand: st.session_state[pk] = min(cand)

    with st.container(key="day_stepper"):
        c1, c2, c3 = st.columns([1, 8, 1], vertical_alignment="center")
        with c1:
            st.button("", icon=":material/chevron_left:", key="day_prev", on_click=_prev,
                      disabled=not [d for d in active_days if d < sel], use_container_width=True)
        with c2:
            picked = st.date_input("Ngày", value=sel, min_value=lo, max_value=hi,
                                   format="DD/MM/YYYY", label_visibility="collapsed")
        with c3:
            st.button("", icon=":material/chevron_right:", key="day_next", on_click=_next,
                      disabled=not _next_candidates(sel), use_container_width=True)
    if picked != st.session_state[pk]:
        st.session_state[pk] = picked
        st.rerun()
    return st.session_state[pk]

def format_relative(ts):
    """Khoảng cách từ mốc thời gian tới hiện tại, dạng tiếng Việt: '1 ngày 12 giờ trước'.

    ts (Thời gian kết thúc) luôn là naive wall-clock giờ Việt Nam (Forest ghi giờ điện thoại,
    prep_analysis_data không đổi tz) -- TUYỆT ĐỐI không so với pd.Timestamp.now() trần, vì hàm
    đó trả giờ hệ thống máy chủ chạy Streamlit (deploy production rất có thể là UTC, lệch 7 tiếng
    so với giờ Việt Nam) chứ không phải giờ Việt Nam. Đã tự kiểm chứng: trên máy chủ chạy UTC,
    pd.Timestamp.now() ra 15:53 trong khi giờ Việt Nam thực tế là 22:53 -- lệch đúng 7 tiếng,
    khớp triệu chứng "thời gian hiển thị không chính xác". Dùng chung APP_TZ (đã định nghĩa cho
    CalDAV) để tính "bây giờ" luôn theo giờ Việt Nam rồi bỏ tzinfo, khớp đúng kiểu naive của ts."""
    if pd.isna(ts):
        return "—"
    ts = pd.Timestamp(ts)
    # Khớp timezone: dữ liệu Forest có thể có tz (tz-aware, hiếm) hoặc không (naive, phổ biến)
    now = pd.Timestamp.now(tz=ts.tz) if ts.tzinfo is not None else pd.Timestamp.now(tz=APP_TZ).tz_localize(None)
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


def _inject_relative_time_ticker():
    """Tự cập nhật text "X trước" của thẻ <b id='last-update-live' data-epoch='...'> mỗi 30s
    bằng JS phía trình duyệt, không cần Streamlit rerun cả trang chỉ để số đếm nhích lên. So
    Date.now() (epoch UTC thật của trình duyệt) với data-epoch (epoch UTC thật đã tính đúng theo
    APP_TZ ở phía Python, xem render_day_report) -- CẢ HAI đều là epoch UTC tuyệt đối nên phép
    trừ luôn đúng bất kể múi giờ máy chủ hay múi giờ máy người dùng đang ở đâu, tránh đúng loại
    lỗi lệch múi giờ vừa sửa ở format_relative(). Logic format giữ y hệt format_relative() (bỏ
    qua nhánh tz-aware vì epoch đã tự quy về UTC từ đầu)."""
    js = (
        "<script>\n"
        "(function(){\n"
        "  function relText(ms){\n"
        "    if (ms < 60000) return 'vừa xong';\n"
        "    const secs = Math.floor(ms / 1000);\n"
        "    const days = Math.floor(secs / 86400);\n"
        "    const hours = Math.floor((secs % 86400) / 3600);\n"
        "    const mins = Math.floor((secs % 3600) / 60);\n"
        "    if (days > 0) return days + ' ngày ' + hours + ' giờ trước';\n"
        "    if (hours > 0) return hours + ' giờ ' + mins + ' phút trước';\n"
        "    return mins + ' phút trước';\n"
        "  }\n"
        "  function tick(){\n"
        "    const el = window.parent.document.getElementById('last-update-live');\n"
        "    if (!el) return;\n"
        "    const epoch = parseInt(el.getAttribute('data-epoch'), 10);\n"
        "    if (isNaN(epoch)) return;\n"
        "    el.textContent = relText(Date.now() - epoch);\n"
        "  }\n"
        "  tick();\n"
        "  setInterval(tick, 30000);\n"
        "})();\n"
        "</script>"
    )
    components.html(js, height=0)


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


def _period_comparison(df, period_col, selected_key, prev_key, elapsed_mask=None):
    """Baseline so sánh cho hero deltas (Tháng/Tuần/Năm dùng chung) -- (prev_metrics, avg_metrics),
    mỗi cái None hoặc {hrs,trees,hrs_day,trees_day,min_sess}. avg_metrics = trung bình các kỳ
    KHÁC kỳ đang chọn (kỳ liền trước vẫn nằm trong pool trung bình, không loại trừ -- đúng hành
    vi Tháng/Tuần đã có từ trước). elapsed_mask: Series[bool] cùng index df, hoặc None -- khi
    kỳ đang xem CHƯA kết thúc (vd đang xem tháng/tuần/năm hiện tại), truyền mask lọc theo đúng
    phần đã trôi qua (vd "N ngày đầu tháng") áp dụng cho CẢ 2 baseline, để không so kỳ dở dang
    với 1 kỳ đầy đủ (nếu không sẽ ra kiểu "-38h vs Tháng trước" dù mới qua 3/31 ngày, vô nghĩa).
    None nghĩa là kỳ đã khép hẳn, so full-vs-full như hành vi gốc."""
    d = df if elapsed_mask is None else df[elapsed_mask]

    def _metrics(sub):
        if sub.empty:
            return None
        hrs, trees = sub['Thời lượng (Phút)'].sum() / 60, len(sub)
        days = sub['Ngày'].nunique() or 1
        return {"hrs": hrs, "trees": trees, "hrs_day": hrs / days, "trees_day": trees / days,
                "min_sess": (hrs * 60) / trees if trees else None}

    prev_m = _metrics(d[d[period_col] == prev_key])
    others = d[d[period_col] != selected_key]
    if others[period_col].nunique() > 0:
        g = others.groupby(period_col)
        hrs_o, trees_o, days_o = g['Thời lượng (Phút)'].sum() / 60, g.size(), g['Ngày'].nunique()
        avg_m = {"hrs": hrs_o.mean(), "trees": trees_o.mean(), "hrs_day": (hrs_o / days_o).mean(),
                 "trees_day": (trees_o / days_o).mean(), "min_sess": ((hrs_o * 60) / trees_o).mean()}
    else:
        avg_m = None
    return prev_m, avg_m


# Kho câu cho _smart_digest() -- mỗi tình huống 2-3 biến thể, chọn ổn định theo md5(kỳ|tình
# huống) để rerun không đổi câu nhưng 2 kỳ khác nhau cùng tình huống không lặp y hệt một câu.
# Giọng văn: nhận xét tinh tế + một chút hài hước kiểu "người làm vườn", KHÔNG lặp lại số liệu
# đã có ở hero deltas ngay phía trên trừ khi con số là nhân vật chính của câu.
_DIGEST_TEMPLATES = {
    "first": [
        "{kwx_cap} đầu tiên có dữ liệu: <b>{hrs}</b>, <b>{trees} cây</b>. Mọi khu rừng đều bắt đầu từ vài hạt mầm.",
        "Chưa có gì để so sánh — nhưng <b>{hrs}</b> đầu tiên thì đã nằm trong sổ. Khởi đầu được ghi nhận.",
        "Trang đầu tiên của cuốn sổ: <b>{hrs}</b>, <b>{trees} cây</b>. Các {kwx} sau sẽ có thứ để ganh đua.",
    ],
    "record": [
        "Kỷ lục mới: <b>{hrs}</b> — {kwx} năng suất nhất từ trước tới nay. Đỉnh cũ ({best_hrs}) xin phép lùi về nhì.",
        "<b>{hrs}</b> — chưa {kwx} nào chạm tới con số này. Trần cũ ({best_hrs}) vừa được nâng thêm một tầng.",
        "{kw_cap} đi vào lịch sử: <b>{hrs}</b>, vượt mọi {kwx} trước đó. Bảng vàng đã được cập nhật.",
    ],
    "record_progress": [
        "Chưa hết {kwx} mà đã <b>{hrs}</b> — vượt mọi {kwx} trước đó. Phần còn lại chỉ là nới rộng kỷ lục.",
        "Kỷ lục cũ ({best_hrs}) đã bị vượt từ giữa chừng: <b>{hrs}</b> và {kwx} vẫn còn chưa kết thúc.",
        "<b>{hrs}</b> khi {kwx} còn dang dở — các {kwx} cũ nhìn nhau, chưa hiểu chuyện gì vừa xảy ra.",
    ],
    "near_record": [
        "<b>{hrs}</b> — thiếu đúng {gap} nữa là chạm kỷ lục ({best_hrs}). Gần tới mức nghe được tiếng gõ cửa.",
        "Suýt thì lịch sử: <b>{hrs}</b>, kém đỉnh cũ vỏn vẹn {gap}. Lần sau nhớ mang thêm một phiên.",
        "Á quân mọi thời đại: <b>{hrs}</b>, chỉ sau mức {best_hrs}. Ngôi vương bắt đầu thấy không yên.",
    ],
    "comeback": [
        "Sự trở lại: từ <b>{prev_hrs}</b> {prevw} lên <b>{hrs}</b>. Khu rừng xanh lại rồi.",
        "{prevw_cap} gần như im ắng, giờ là <b>{hrs}</b> — hoá ra chỉ là nghỉ giữa hiệp.",
        "Từ <b>{prev_hrs}</b> bật lên <b>{hrs}</b>. Ai bảo nghỉ là mất đà thì xem lại giúp.",
    ],
    "big_up": [
        "Tăng tốc rõ rệt: <b>{hrs}</b>, hơn {prevw} <b>{d}</b>. Đầu tàu {kw}: <b>{proj}</b>.",
        "Vườn {kw} rậm hơn hẳn: <b>+{d}</b> so với {prevw}, phần lớn đổ vào <b>{proj}</b>.",
        "<b>{hrs}</b> — bỏ xa {prevw} {d}. Đà này thì kỷ lục cũng nên bắt đầu lo.",
    ],
    "big_down": [
        "{kw_cap} chậm lại: <b>{hrs}</b>, kém {prevw} {d}. Đất cũng cần nghỉ giữa hai vụ.",
        "Nhịp {kw} nhẹ hơn: <b>{hrs}</b> (−{d} so với {prevw}). Rừng thưa vẫn là rừng.",
        "<b>{hrs}</b>, hụt {d} so với {prevw}. Coi như chương nghỉ giữa truyện — miễn là có chương sau.",
    ],
    "one_day_carry": [
        "Một mình <b>{day}</b> ({day_hrs}) gánh <b>{pct}%</b> cả {kwx}. Đề nghị tuyên dương trước toàn trường.",
        "<b>{day}</b> cân cả {kwx}: <b>{day_hrs}</b> trên tổng {hrs}. Các ngày còn lại có mặt chủ yếu để cổ vũ.",
        "{pct}% thời lượng cả {kwx} dồn vào đúng <b>{day}</b>. Một ngày ra trận, những ngày còn lại dưỡng quân.",
    ],
    "proj_dominates": [
        "<b>{proj}</b> chiếm <b>{pct}%</b> thời gian {kw} — không còn là ưu tiên nữa, mà là mối quan hệ nghiêm túc.",
        "{kw_cap} gần như chỉ có một cái tên: <b>{proj}</b> ({pct}%). Tập trung kiểu này khó chê.",
        "Sân khấu {kw} thuộc về <b>{proj}</b> ({pct}%). Các dự án khác vui lòng giữ trật tự ở hàng ghế khán giả.",
    ],
    "weekend": [
        "<b>{pct}%</b> thời gian {kw} rơi vào cuối tuần ({wk_hrs}). Thứ 7 – Chủ Nhật gửi lời chào tới khái niệm 'nghỉ ngơi'.",
        "Chiến binh cuối tuần: <b>{wk_hrs}</b> trên tổng {hrs} nằm gọn trong Thứ 7 và Chủ Nhật. Ngày thường chỉ là phần khởi động.",
    ],
    "deep_sessions": [
        "Phiên trung bình <b>{sess} phút</b> — dài hơn nếp quen ({avg_sess} phút) thấy rõ. Rễ đang cắm sâu hơn.",
        "{kw_cap} bạn ngồi lì hơn hẳn: <b>{sess} phút/phiên</b> so với nếp cũ {avg_sess}. Chiếc ghế chắc cũng bất ngờ.",
        "Ít mà chất: mỗi phiên {kw} kéo dài <b>{sess} phút</b>, vượt xa nhịp quen {avg_sess} phút.",
    ],
    "shallow_sessions": [
        "Phiên {kw} hơi vụn: <b>{sess} phút/phiên</b>, nếp quen là {avg_sess}. Gom củi nhỏ lại thành đống lửa lớn nhé.",
        "Nhiều phiên ngắn ({sess} phút/phiên so với nếp {avg_sess}). Bonsai cũng là cây — nhưng thử vài phiên dài xem sao.",
    ],
    "iron": [
        "<b>{n_days}/{total_days} ngày</b> đều có mặt — chuyên cần kiểu này thời đi học là có giấy khen.",
        "Gần như không sót ngày nào ({n_days}/{total_days}). Sự đều đặn nhàm chán một cách đáng ngưỡng mộ.",
        "Điểm danh {n_days}/{total_days} ngày. Cái cây nào được tưới đều thế này thì muốn còi cũng khó.",
    ],
    "diverse": [
        "<b>{n_proj} dự án</b> chia đều sân khấu, không ai vượt {pct}%. Một khu vườn đa canh đúng nghĩa.",
        "Thời gian {kw} rải đều cho {n_proj} dự án — đội hình đồng đều, không ngôi sao độc diễn.",
    ],
    "milestone": [
        "Lần đầu tiên một {kwx} vượt mốc <b>{mile}h</b>: {hrs}. Chỗ này mà là cây thật thì đủ gọi là một cánh rừng.",
        "Cột mốc <b>{mile}h</b>/{kwx} lần đầu bị bỏ lại sau lưng ({hrs}). Số giờ này quy ra cây là cả một quả đồi.",
    ],
    "steady": [
        "<b>{hrs}</b> — sát trung bình như đo bằng thước. Ổn định cũng là một loại năng lực.",
        "Không đột biến, không tụt dốc: <b>{hrs}</b>, đúng nhịp quen thuộc. Rừng lâu năm mọc kiểu này đấy.",
        "{kw_cap}: <b>{hrs}</b>, đều tăm tắp so với mọi khi. Biểu đồ nhìn hơi buồn ngủ — chủ vườn thì đáng nể.",
    ],
    "generic": [
        "<b>{hrs}</b> và <b>{trees} cây</b> {kw}. Không có gì giật gân — khu rừng vẫn lặng lẽ mọc thêm.",
        "Sổ {kw} ghi {hrs}, {trees} cây. Bình thường, mà chắc chắn.",
        "{hrs}, {trees} cây, không drama. Có những {kwx} chỉ cần thế là đủ.",
    ],
}

# Tình huống "đáng ăn mừng" -> footer tint accent; còn lại tint chip trung tính.
_DIGEST_CELEBRATE = {"first", "record", "record_progress", "near_record", "comeback", "big_up",
                     "iron", "milestone"}


def _smart_digest(df, period_col, selected_key, df_p, prev_m, avg_m, is_current):
    """1 dòng "điểm nhấn" gắn cuối panel Tổng quan của Tuần/Tháng/Năm: chọn ĐÚNG 1 tín hiệu
    đáng nói nhất của kỳ theo thứ tự ưu tiên (kỷ lục > mốc tròn năm lần đầu vượt > bật lại >
    tăng/giảm mạnh > cơ cấu bất thường: 1 ngày gánh/1 dự án chiếm sóng/dồn cuối tuần/phiên
    sâu-vụn > chuyên cần > đa dạng > ổn định), diễn đạt bằng câu chữ thay vì lặp lại bảng số --
    hero deltas ngay
    trên đã lo phần số liệu. prev_m/avg_m truyền vào là bản ĐÃ cắt theo phần kỳ trôi qua khi
    is_current (từ _period_comparison), nên mọi so sánh ở đây tự công bằng với kỳ dở dang; nhãn
    cũng tự đổi thành "cùng kỳ ... trước" cho khớp. Trả (html, bg, fg) cho footer của
    render_stat_panel, hoặc None nếu kỳ trống."""
    if df_p.empty:
        return None

    word = {"Tuần": "tuần", "Tháng": "tháng", "Năm": "năm"}[period_col]
    kind = {"Tuần": "week", "Tháng": "month", "Năm": "year"}[period_col]

    def _fh(v):
        return f"{v:.0f}h" if abs(v - round(v)) < 0.05 else f"{v:.1f}h"

    hrs = df_p['Thời lượng (Phút)'].sum() / 60
    trees = len(df_p)
    n_days = df_p['Ngày'].nunique()
    sess_min = (hrs * 60) / trees if trees else 0

    F = {"hrs": _fh(hrs), "trees": trees, "kwx": word, "kwx_cap": word.capitalize(),
         "kw": f"{word} này", "kw_cap": f"{word.capitalize()} này",
         "prevw": f"cùng kỳ {word} trước" if is_current else f"{word} trước"}
    F["prevw_cap"] = F["prevw"].capitalize()

    # Bối cảnh dùng chung cho các bộ dò bên dưới
    totals = df.groupby(period_col)['Thời lượng (Phút)'].sum() / 60
    others = totals.drop(selected_key, errors='ignore')
    prev_hrs = prev_m["hrs"] if prev_m else 0.0
    avg_hrs = avg_m["hrs"] if avg_m else None
    abs_big = {"week": 2.0, "month": 5.0, "year": 20.0}[kind]
    _miles = (100, 250, 500, 1000, 2000)
    _mile_cur = max((m for m in _miles if hrs >= m), default=None)
    _mile_best_other = max((m for m in _miles if len(others) and others.max() >= m), default=0)

    by_proj = df_p.dropna(subset=['Dự án']).groupby('Dự án')['Thời lượng (Phút)'].sum()
    top_proj, top_share = (by_proj.idxmax(), by_proj.max() / by_proj.sum()) if not by_proj.empty else (None, 0)
    by_day = df_p.groupby('Ngày')['Thời lượng (Phút)'].sum() / 60
    wk_hrs = df_p[df_p['Thời gian bắt đầu'].dt.dayofweek >= 5]['Thời lượng (Phút)'].sum() / 60
    if kind == "week":
        total_days = _today_vn().isoweekday() if is_current else 7
    elif kind == "month":
        total_days = _today_vn().day if is_current else pd.Period(selected_key).days_in_month
    else:
        total_days = (_today_vn().timetuple().tm_yday if is_current
                      else pd.Timestamp(f"{selected_key}-12-31").dayofyear)

    sit = None
    if prev_m is None and avg_m is None:
        sit = "first"
    elif len(others) >= 2 and hrs > others.max():
        sit = "record_progress" if is_current else "record"
        F["best_hrs"] = _fh(others.max())
    elif not is_current and len(others) >= 2 and others.max() > 0 and hrs >= 0.92 * others.max():
        sit = "near_record"
        F.update(best_hrs=_fh(others.max()), gap=_fh(others.max() - hrs))
    elif kind == "year" and _mile_cur is not None and _mile_cur > _mile_best_other:
        # Chỉ khi LẦN ĐẦU một năm vượt qua mốc tròn cao hơn mọi năm khác -- không lặp lại
        # "vượt mốc 250h" cho mọi năm về sau một khi ai cũng qua mốc đó.
        sit = "milestone"
        F["mile"] = _mile_cur
    elif avg_hrs and avg_hrs >= 1 and prev_hrs < 0.25 * avg_hrs and hrs >= 0.85 * avg_hrs:
        sit = "comeback"
        F["prev_hrs"] = _fh(prev_hrs)
    elif prev_hrs > 0 and hrs - prev_hrs >= abs_big and (hrs - prev_hrs) / prev_hrs >= 0.30:
        sit = "big_up"
        F.update(d=_fh(hrs - prev_hrs), proj=html_escape(str(top_proj)) if top_proj else "nhiều dự án")
    elif prev_hrs >= abs_big and prev_hrs - hrs >= abs_big and (prev_hrs - hrs) / prev_hrs >= 0.30:
        sit = "big_down"
        F["d"] = _fh(prev_hrs - hrs)
    elif kind in ("week", "month") and n_days >= 3 and hrs >= 2 and by_day.max() / hrs >= 0.45:
        sit = "one_day_carry"
        _dmax = by_day.idxmax()
        F.update(day=VN_DAYS.get(pd.Timestamp(_dmax).day_name(), str(_dmax)),
                 day_hrs=_fh(by_day.max()), pct=round(by_day.max() / hrs * 100))
    elif top_proj is not None and len(by_proj) >= 2 and hrs >= 3 and top_share >= 0.60:
        sit = "proj_dominates"
        F.update(proj=html_escape(str(top_proj)), pct=round(top_share * 100))
    elif kind in ("week", "month") and hrs >= 3 and wk_hrs / hrs >= 0.55:
        sit = "weekend"
        F.update(wk_hrs=_fh(wk_hrs), pct=round(wk_hrs / hrs * 100))
    elif avg_m and avg_m.get("min_sess") and sess_min >= avg_m["min_sess"] * 1.3 and sess_min - avg_m["min_sess"] >= 5:
        sit = "deep_sessions"
        F.update(sess=round(sess_min), avg_sess=round(avg_m["min_sess"]))
    elif avg_m and avg_m.get("min_sess") and trees >= 5 and sess_min <= avg_m["min_sess"] * 0.7 and avg_m["min_sess"] - sess_min >= 5:
        sit = "shallow_sessions"
        F.update(sess=round(sess_min), avg_sess=round(avg_m["min_sess"]))
    elif total_days >= 6 and n_days / total_days >= 0.85:
        sit = "iron"
        F.update(n_days=n_days, total_days=total_days)
    elif len(by_proj) >= 4 and hrs >= 3 and top_share <= 0.35:
        sit = "diverse"
        F.update(n_proj=len(by_proj), pct=round(top_share * 100))
    elif avg_hrs and abs(hrs - avg_hrs) <= 0.1 * avg_hrs:
        sit = "steady"
    else:
        sit = "generic"

    variants = _DIGEST_TEMPLATES[sit]
    idx = int(hashlib.md5(f"{selected_key}|{sit}".encode()).hexdigest()[:8], 16) % len(variants)
    text = variants[idx].format(**F)
    if sit in _DIGEST_CELEBRATE:
        return text, "rgba(var(--accent-rgb),0.10)", "var(--accent-dark)"
    return text, "var(--chip)", "var(--text)"


def _clip_card(note):
    """Thẻ nhỏ giải thích khi so sánh kỳ bị cắt vì kỳ đang xem còn dở dang -- cùng khuôn thẻ
    "Cập nhật gần nhất" (glass-card ngang, icon nhỏ + nhãn xám hoa + nội dung), thay vì 1 dòng
    st.caption() trần trụi lạc quẻ giữa các thẻ số liệu. Icon đồng hồ cát (khác icon lịch sử của
    thẻ "Cập nhật gần nhất") vì ý nghĩa gần với "đang tính" hơn."""
    st.markdown(
        f"<div class='glass-card' style='padding:12px 18px; margin-bottom:16px; display:flex; "
        f"align-items:center; flex-wrap:wrap; gap:6px 10px;'>"
        f"<span style='font-size:13px;color:var(--text-2);font-weight:500;text-transform:uppercase;"
        f"letter-spacing:0.5px;white-space:nowrap;'>"
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='14' height='14' "
        f"fill='var(--text-2)' style='vertical-align:-2px;margin-right:5px;'>"
        f"<path d='M6 2v6l4 4-4 4v6h12v-6l-4-4 4-4V2H6zm10 15.5V20H8v-2.5l4-4 4 4zM8 6.5V4h8v2.5l-4 4-4-4z'/>"
        f"</svg>Kỳ chưa kết thúc</span>"
        f"<span style='font-size:14px;color:var(--text);'>{note}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


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
        h += ("<div style='margin-top:16px;padding-top:14px;border-top:1px solid var(--divider);text-align:center;'>"
              f"<span style='background:{f_bg};color:{f_fg};font-size:14px;font-weight:500;padding:7px 16px;border-radius:11px;'>{f_txt}</span></div>")
    h += "</div>"
    st.markdown(h, unsafe_allow_html=True)


def render_top_3(df, col_name, title, week_key=None, n=3):
    if df.empty:
        html_list = "<p style='color:var(--text-2); font-size: 14px;'>Không có dữ liệu</p>"
    else:
        top3 = df.groupby(col_name)['Thời lượng (Phút)'].sum().sort_values(ascending=False).head(n)
        # Thời gian của từng nhóm/dự án trong tuần này (nếu được yêu cầu)
        wk = {}
        if week_key is not None and 'Tuần' in df.columns:
            wk = (df[df['Tuần'] == week_key].groupby(col_name)['Thời lượng (Phút)'].sum() / 60).to_dict()
        html_list = "<ul style='margin:0; padding-left: 20px; color: var(--text); font-size: 15px; line-height: 1.6;'>"
        for k, v in top3.items():
            wh = wk.get(k, 0)
            wsuf = f" <span style='color:{ACCENT}; font-size:13px;'>({wh:.1f}h tuần này)</span>" if wh > 0.05 else ""
            html_list += f"<li><span style='font-weight:600;'>{html_escape(str(k))}</span>: {v/60:.1f}h{wsuf}</li>"
        html_list += "</ul>"

    html = f"""
    <div class="glass-card" style="height: 100%;">
        <p style="margin: 0 0 12px 0; font-size: 13px; color: var(--text-2); font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">{title}</p>
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
        fg = _readable_text(col)
        seg += (f"<div title='{name} ({rng}): {c} phiên' style='width:{pct:.4f}%;background:{col};color:{fg};"
                f"font-size:12px;font-weight:600;display:flex;align-items:center;justify-content:center;'>{lbl}</div>")
    legend = ""
    for (name, rng, lo, hi, col), c in zip(SESSION_BUCKETS, counts):
        legend += (f"<span style='display:inline-flex;align-items:center;gap:5px;margin:0 14px 4px 0;font-size:13px;color:var(--text);'>"
                   f"<span style='display:inline-block;width:11px;height:11px;border-radius:3px;background:{col};'></span>"
                   f"{name} <span style='color:var(--text-2);'>{rng}</span> · <b>{c}</b></span>")
    st.markdown(
        "<div class='glass-card' style='padding:16px 18px;margin-top:14px;'>"
        "<div style='font-size:11px;color:var(--text-2);font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;'>Phân bố độ dài phiên</div>"
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
    _threshold_col = "#6ea8ff" if IS_DARK else "#0a52c4"
    _avg_col = "#f2f2f7" if IS_DARK else "#1d1d1f"
    for t in LEN_THRESHOLDS:
        if start < t <= top:
            fig.add_vline(x=t, line=dict(color=_threshold_col, width=1.5, dash='dot'))
    avg = d.mean()
    if start <= avg <= top + step:
        fig.add_vline(x=avg, line=dict(color=_avg_col, width=2, dash='dash'),
                      annotation_text=f"TB {avg:.0f}′", annotation_position="top right",
                      annotation_font=dict(size=12, color=_avg_col))
    fig.update_layout(
        height=300, margin=dict(l=10, r=10, t=24, b=10), bargap=0.06, showlegend=False,
        xaxis=dict(title='Độ dài phiên (phút)', range=[start - 2, top + step],
                   tickvals=[10, 20, 30, 40, 50, 60],
                   ticktext=['10', '20', '30', '40', '50', '60+'],
                   tickfont=dict(size=12), showgrid=False),
        yaxis=dict(title='Số phiên', tickfont=dict(size=12),
                   gridcolor=("rgba(255,255,255,0.10)" if IS_DARK else "rgba(0,0,0,0.06)")),
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
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
        _lbl = "font-size:13px;color:var(--text-2);font-weight:500;text-transform:uppercase;letter-spacing:0.5px;"
        _val = "font-size:17px;color:var(--text);font-weight:600;"
        st.markdown(
            "<div class='glass-card' style='display:flex;flex-wrap:wrap;justify-content:center;align-items:center;"
            "gap:6px 16px;max-width:900px;margin:8px auto 0 auto;padding:12px 18px;'>"
            f"<span style='{_lbl}'>Giờ tập trung nhất</span>"
            f"<span style='{_val}'>{peak_h}h</span>"
            f"<span style='font-size:13px;color:var(--text-2);'>(TB {tot.max():.1f}h/ngày)</span>"
            "<span style='color:var(--text-4);'>·</span>"
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
    ).properties(width=alt.Step(54), height=alt.Step(26), background='transparent').configure_view(strokeWidth=0)
    # width='content' (không 'stretch') -> tôn trọng alt.Step nên ô không bị kéo dài, tự căn giữa thẻ
    # background='transparent' ở properties(): Vega tự vẽ nền riêng cho SVG (mặc định ăn theo màu
    # nền trang, không phải trong suốt) -> để trong suốt cho nền thẻ bọc ngoài (--card, đổi theo
    # IS_DARK) lộ ra, tránh canvas SVG lệch tông với phần đệm/viền thẻ bao quanh.
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
    gap = int((pd.Timestamp(_today_vn()) - u.max()).days)
    current = int(counts[sid.iloc[-1]]) if gap <= 1 else 0
    return {"total": int(len(u)), "longest": int(counts.max()), "current": current, "gap": gap}


NUDGE_TONES = {
    "good": (f"rgba({ACCENT_RGB},0.12)", ACCENT_DARK),  # đồng bộ accent, tự đúng cả 2 chế độ
    # "warn"/"neutral": nền tint tối hơn + chữ ĐẬM hơn (đọc được trên nền light) không còn đủ
    # tương phản trên nền tối -> dark cần chữ SÁNG hơn thay vì tối hơn (cùng lý do ACCENT_DARK
    # đổi ngữ nghĩa ở trên).
    "warn": (("rgba(255,159,10,0.18)", "#ffb340") if IS_DARK else ("rgba(255,149,0,0.15)", "#a85d00")),
    "neutral": (("rgba(255,69,58,0.16)", "#ff8a80") if IS_DARK else ("rgba(255,59,48,0.12)", "#c50a00")),
}


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


def _weekday_avg(scope_df, min_count=3):
    """Trung bình giờ mỗi ngày theo thứ, chỉ tính những ngày có hoạt động (bỏ ngày trống).

    Bỏ các thứ có QUÁ ÍT lần xuất hiện (< min_count) khỏi kết quả trước khi caller dùng
    idxmax()/idxmin() xếp hạng "Mạnh nhất"/"Yếu nhất" -- nếu không, 1 lần làm đột xuất ngoài lệ
    (vd đúng 1 buổi tối Thứ Ba hiếm hoi, 2 giờ) sẽ thắng trung bình so với 1 thứ được làm đều đặn
    nhiều lần (vd Thứ 6, mỗi lần ngắn hơn nhưng LÀ thói quen thật), cho ra kết quả trái ngược hẳn
    với cảm nhận thực tế khi nhìn Biểu đồ lịch. Dữ liệu quá thưa ở MỌI thứ (không thứ nào đạt
    min_count) thì vẫn trả bản KHÔNG lọc -- có số liệu chưa đủ tin cậy còn hơn ẩn hẳn mục này."""
    if scope_df.empty:
        return pd.Series(dtype=float)
    wd_count = scope_df.groupby('Thứ')['Ngày'].nunique()
    by = scope_df.groupby('Thứ')['Thời lượng (Phút)'].sum() / 60
    avg = (by / wd_count).reindex(DAYS_ORDER).dropna()
    reliable = wd_count.reindex(avg.index) >= min_count
    return avg[reliable] if reliable.any() else avg


def _top_days(df_scope, n=3):
    """Top n ngày nhiều giờ nhất trong df_scope (dùng cho mục "Ngày nổi bật" ở Bảng số liệu
    Tổng quan/Tuần/Tháng/Năm) -- rank(method='min') nên 2 ngày bằng tuyệt đối giờ ở cùng 1 hạng
    thì ĐỒNG HẠNG cả hai (danh sách trả về có thể dài hơn n khi có hoà). Trả về
    list[{"rank", "date", "hours"}] sắp theo giờ giảm dần."""
    if df_scope.empty:
        return []
    daily = df_scope.groupby('Ngày')['Thời lượng (Phút)'].sum().sort_values(ascending=False)
    ranks = daily.rank(method='min', ascending=False)
    top = daily[ranks <= n]
    return [{"rank": int(ranks[d]), "date": d, "hours": h / 60} for d, h in top.items()]


def _top_days_chips(items):
    """Chuyển kết quả _top_days()/overall_top3 thành chips cho render_stat_panel() -- dùng
    chung ở Bảng số liệu Tổng quan/Tuần/Tháng/Năm."""
    return [{"k": f"#{it['rank']}", "v": f"{it['date']:%d/%m/%Y} · {it['hours']:.1f}h"} for it in items]


def _top_days_section(df_scope, label, n=3):
    """1 section "Ngày nổi bật" cho render_stat_panel() (sections=...), hoặc None nếu kỳ chưa
    có ngày nào -- dùng chung ở Bảng số liệu Tuần/Tháng/Năm (Tổng quan tự truyền thẳng
    overall_top3 vì đã tính sẵn cho mục "Kỷ lục" nên không gọi lại _top_days() ở đây)."""
    items = _top_days(df_scope, n)
    return [{"label": label, "chips": _top_days_chips(items)}] if items else None


@st.cache_data
def _compute_alltime_records(df):
    """"Bảng vàng": kỷ lục TOÀN THỜI GIAN -- top 3 ngày nhiều giờ nhất chung (overall_top3, tái
    dùng bởi Bảng số liệu Tổng quan) + kỷ lục #1 riêng theo từng Dự án/Nhóm đủ ngưỡng
    RECORD_MIN_DAYS ngày có dữ liệu (project_records/category_records, dùng bởi Bảng số liệu
    trang Dự án). day_badges là bảng tra ngược ngày -> danh sách badge, dựng sẵn 1 lần để các
    điểm gắn chip trên Timeline (render_note_editor/render_notes_journal/render_on_this_day)
    không phải lặp lại groupby. Cache theo st.cache_data (như prep_analysis_data()) -> tự làm
    mới ngay khi dữ liệu đổi (mọi save_*/xoá dữ liệu đã gọi st.cache_data.clear() sẵn), không
    bao giờ outdate."""
    day_badges = {}

    def _add_badge(d, badge):
        day_badges.setdefault(d, []).append(badge)

    overall_top3 = _top_days(df, 3)
    for item in overall_top3:
        _add_badge(item["date"], {"kind": "overall", "rank": item["rank"]})

    def _group_records(scope_df, col_name):
        recs = {}
        if scope_df.empty:
            return recs
        eligible = scope_df.groupby(col_name)['Ngày'].nunique()
        eligible = eligible[eligible >= RECORD_MIN_DAYS].index
        for name in eligible:
            g = scope_df[scope_df[col_name] == name]
            daily = g.groupby('Ngày')['Thời lượng (Phút)'].sum()
            best_hours = daily.max()
            best_days = daily[daily == best_hours].index  # đồng hạng nếu nhiều ngày hoà kỷ lục
            recs[name] = {"dates": list(best_days), "hours": best_hours / 60}
            for d in best_days:
                _add_badge(d, {"kind": col_name, "name": name})
        return recs

    project_records = _group_records(df, 'Dự án')
    category_records = _group_records(df[df['Có danh mục']], 'Danh mục')

    return {
        "overall_top3": overall_top3,
        "project_records": project_records,
        "category_records": category_records,
        "day_badges": day_badges,
    }


def _chip_row_html(heading, chips_html):
    """1 hàng "heading nhỏ (class .rl-book) + các jchip" -- khuôn dùng chung cho
    _record_chips_html() (chip Kỷ lục) và _book_chips_html() (chip tên sách)."""
    return f"<div style='margin-bottom:6px;'><span class='rl-book'>{heading}</span>{chips_html}</div>"


def _quick_notes_on(qn_df, day):
    """Lọc load_quick_notes() về đúng 1 ngày -- qn_df đã sắp cũ→mới sẵn từ query (.order("ts")),
    lọc bằng boolean mask giữ nguyên thứ tự đó, không cần sort lại."""
    if qn_df.empty:
        return qn_df
    return qn_df[qn_df['Thời gian'].dt.date == day]


def _quick_note_chips_html(qn_day):
    """"Ghi chú nhanh" cho 1 ngày (qn_day = _quick_notes_on() của đúng ngày, đã cũ→mới), CHỈ ĐỌC
    -- mỗi note 1 dòng riêng (không phải chip inline như chip Lịch/Sách): badge giờ nhỏ (class
    .qn-time, chỉ bọc đúng giờ) + chữ ghi chú thường ngoài badge (class .qn-text, cùng cỡ chữ/màu
    với .note-html) để đọc như 1 câu ghi chú thật, không phải nhãn nhỏ. Nút sửa/xoá (tương tác
    thật, cần widget Streamlit) nằm riêng trong render_note_editor(), không lẫn vào chuỗi HTML
    tĩnh này."""
    if qn_day is None or qn_day.empty:
        return ''
    rows = ''.join(
        f"<div class='qn-line'><span class='qn-time'>{r['Thời gian']:%H:%M}</span>"
        f"<span class='qn-text'>{html_escape(str(r['Nội dung']))}</span></div>"
        for _, r in qn_day.iterrows()
    )
    return f"<div style='margin-bottom:6px;'><span class='rl-book'>Ghi chú nhanh</span>{rows}</div>"


def _record_chips_html(badges):
    """Chip "Kỷ lục" cho 1 ngày (badges = day_badges.get(ngày), có thể None/rỗng) -- dùng chung
    _chip_row_html() với _book_chips_html(), 1 chip riêng mỗi badge (không gộp) vì 1 ngày có
    thể vừa giữ hạng chung vừa giữ kỷ lục riêng vài Dự án/Nhóm. Nhãn "Danh mục" ghi
    rõ chữ "Nhóm" (khác "Dự án" giữ nguyên tên) -- nếu không, 1 Nhóm tự đặt trùng tên đúng 1 Dự
    án duy nhất của nó (vd Nhóm "Deep Work" chỉ gồm Dự án "Deep Work") sẽ ra 2 chip đọc y hệt
    nhau "Kỷ lục Deep Work", trông như bị lặp badge dù thực ra là 2 kỷ lục khác khái niệm."""
    if not badges:
        return ''
    _ORD = {1: "Hạng nhất", 2: "Hạng nhì", 3: "Hạng ba"}
    parts = []
    for b in badges:
        if b["kind"] == "overall":
            label = _ORD.get(b["rank"], f"Hạng {b['rank']}") + " mọi thời đại"
        elif b["kind"] == "Danh mục":
            label = f"Kỷ lục Nhóm {b['name']}"
        else:
            label = f"Kỷ lục {b['name']}"
        parts.append(f"<span class='jchip rec'>{html_escape(label)}</span>")
    return _chip_row_html("Kỷ lục", ''.join(parts))


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
    _today = _today_vn()
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
.rtl-card{{background:var(--card);border:1px solid var(--border);border-radius:16px;box-shadow:0 1px 1px rgba(0,0,0,0.02);padding:16px 24px;margin-top:14px;}}
.rtl-legend{{display:flex;gap:16px;margin:0 0 10px {name_w + 8}px;font-size:12px;color:var(--text-2);}}
.rtl-legend i{{display:inline-block;width:11px;height:11px;border-radius:3px;vertical-align:-1px;margin-right:5px;}}
.rtl-body{{display:flex;align-items:flex-start;}}
.rtl-names{{flex:0 0 {name_w}px;width:{name_w}px;}}
.rtl-name{{height:32px;display:flex;align-items:center;font-size:13px;font-weight:600;color:var(--text);
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:8px;}}
.rtl-scroll{{flex:1 1 auto;overflow-x:auto;min-width:0;}}
.rtl-track{{position:relative;height:32px;min-width:{track_min}px;}}
.rtl-grid{{position:absolute;top:0;bottom:0;width:1px;background:var(--divider);}}
.rtl-bar{{position:absolute;top:7px;height:18px;border-radius:6px;min-width:6px;box-shadow:0 1px 3px rgba(0,0,0,0.18);}}
.rtl-bar.done{{background:var(--text-3);}}
.rtl-bar.reading{{background:{ACCENT};}}
.rtl-ticks{{position:relative;height:16px;min-width:{track_min}px;margin-top:3px;}}
.rtl-tick{{position:absolute;font-size:11px;color:var(--text-2);white-space:nowrap;}}
.rtl-yr{{color:var(--text-4);margin-left:1px;}}
</style>
<div class="rtl-card">
<div class="card-label">Dòng thời gian</div>
<div class="rtl-legend"><span><i style="background:{ACCENT};"></i>{labels['ongoing']}</span><span><i style="background:var(--text-3);"></i>Đã xong</span></div>
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
        s_col = ACCENT if r['Trạng thái'] == labels['ongoing'] else 'var(--text-2)'
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
    with st.container(key="rl_detail_select"):
        _detail_sel = st.selectbox(f"Chọn 1 {labels['item_col'].lower()}",
                                    _detail_opts, key=f"rl_detail_{labels['item_col']}",
                                    label_visibility="collapsed")
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
    LVL_COLORS = [("#3a3a3c" if IS_DARK else "#e5e5ea")] + _teal_shades(5)

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
    # Chữ số ngày trắng/xám trên ô đậm/nhạt -- ramp teal ĐẢO CHIỀU khi dark (xem _teal_shades)
    # nên điều kiện sáng/tối của chữ cũng phải đảo theo: dark, lvl cao = ô SÁNG rực -> chữ tối.
    _txt_hi, _txt_lo = ("#1c1c1e", "#98989d") if IS_DARK else ("#ffffff", "#a7a7ac")
    text = base.mark_text(baseline='middle', fontSize=10).encode(
        text='day:Q',
        color=alt.condition("datum.lvl >= 4", alt.value(_txt_hi), alt.value(_txt_lo)),
        tooltip=cal_tooltip
    )
    chart = (rect + text).properties(
        width=alt.Step(34), height=alt.Step(34),
        padding={"left": 0, "right": 64, "top": 5, "bottom": 5},
        background='transparent',
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
.dtl-card{{background:var(--card);border:1px solid var(--border);border-radius:16px;box-shadow:0 1px 1px rgba(0,0,0,0.02);padding:14px 18px;margin-top:14px;}}
.dtl-strip{{position:relative;height:16px;margin-bottom:3px;}}
.dtl-bl{{position:absolute;transform:translateX(-50%);font-size:10px;font-weight:600;letter-spacing:.4px;color:var(--text-3);}}
.dtl-track{{position:relative;height:76px;border-radius:10px;overflow:hidden;border:1px solid var(--divider);background:var(--card);}}
.dtl-typ{{position:absolute;top:0;bottom:0;}}
.dtl-line{{position:absolute;top:0;bottom:0;width:1px;background:var(--divider);}}
.dtl-bar{{position:absolute;top:14px;height:48px;min-width:4px;border-radius:4px;display:flex;align-items:center;justify-content:center;padding:0 6px;color:#fff;font-size:11.5px;font-weight:600;white-space:nowrap;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.18);}}
.dtl-axis{{position:relative;height:16px;margin-top:4px;}}
.dtl-tk{{position:absolute;transform:translateX(-50%);font-size:11px;color:var(--text-2);}}
.dtl-legend{{display:flex;flex-wrap:wrap;gap:14px;margin-top:12px;font-size:12.5px;color:var(--text);}}
.dtl-legend i{{display:inline-block;width:11px;height:11px;border-radius:3px;vertical-align:-1px;margin-right:5px;}}
.dtl-ttl{{font-size:11px;color:var(--text-2);font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px;}}
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
def render_note_editor(day, day_badges=None):
    """Thẻ 2 cột cho một ngày: Thứ/ngày bên trái (giống bố cục .jrows của Nhật ký tuần/tháng,
    dù ở đây chỉ có đúng 1 "dòng"), cột phải theo thứ tự cố định: chip Kỷ lục (nếu ngày này giữ
    kỷ lục -- day_badges do caller truyền vào, xem _compute_alltime_records()) → chip lịch (kèm
    heading nhỏ "Lịch") → chip đọc sách/Gundam (tự nhóm+gắn nhãn theo cuốn/series qua
    _book_chips_html()) → ghi chú nhanh đang chờ (mỗi note 1 hàng badge giờ + chữ + nút Sửa/Xoá
    riêng, KHÔNG có nút gộp -- đứng độc lập vĩnh viễn với ghi chú chính, xem update_quick_note()/
    delete_quick_note()) → nhãn "Ghi chú chính" → ghi chú chính. Mặc định chỉ hiện ghi chú đã lưu
    (hoặc trạng thái trống) kèm một nút; bấm nút mới mở trình soạn (Quill) inline với Cập nhật/
    Huỷ/Xoá.

    Bọc trong @st.fragment: ô soạn Quill gửi nội dung về server mỗi lần gõ phím, nếu
    không cô lập thì cả trang Báo cáo ngày chạy lại mỗi ký tự -> giao diện giật. Là
    fragment nên mỗi lần gõ chỉ phần ghi chú này vẽ lại; các st.rerun() bên dưới cũng
    chỉ rerun trong fragment (đủ vì không phần nào khác trên trang phụ thuộc ghi chú).
    Đúng vì lý do này, day_badges PHẢI được tính sẵn ở caller (ngoài fragment) rồi truyền
    vào dạng list/None đã tra cứu sẵn -- gọi _compute_alltime_records(prep_analysis_data())
    trực tiếp trong này sẽ khiến Streamlit băm lại cả DataFrame phiên mỗi lần gõ phím, đúng
    thứ mà @st.fragment được thêm vào để tránh.

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
                if day_badges:
                    st.markdown(_record_chips_html(day_badges), unsafe_allow_html=True)

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

                qn_day = _quick_notes_on(load_quick_notes(), day)
                if not qn_day.empty:
                    st.markdown("<span class='rl-book'>Ghi chú nhanh</span>", unsafe_allow_html=True)
                    for _, r in qn_day.iterrows():
                        _qid = int(r['id'])
                        qedit_key = f"qnote_edit_{_qid}"
                        with st.container(key=f"qnote_row_{_qid}"):
                            qc1, qc2, qc3 = st.columns([2, 15, 3])
                            with qc1:
                                st.markdown(f"<span class='qn-time'>{r['Thời gian']:%H:%M}</span>",
                                            unsafe_allow_html=True)
                            if st.session_state.get(qedit_key, False):
                                qinput_key = f"qnote_input_{_qid}"
                                with qc2:
                                    st.text_area("Sửa ghi chú nhanh", value=str(r['Nội dung']),
                                                 key=qinput_key, label_visibility="collapsed", height=68)
                                with qc3:
                                    with st.container(horizontal=True, gap="small"):
                                        if st.button("", icon=":material/check:", key=f"qnote_save_{_qid}",
                                                     help="Cập nhật"):
                                            update_quick_note(_qid, st.session_state.get(qinput_key, ""))
                                            st.session_state[qedit_key] = False
                                            st.rerun()
                                        if st.button("", icon=":material/close:",
                                                     key=f"qnote_canceledit_{_qid}", help="Huỷ"):
                                            st.session_state[qedit_key] = False
                                            st.rerun()
                            else:
                                with qc2:
                                    st.markdown(f"<span class='qn-text'>{html_escape(str(r['Nội dung']))}</span>",
                                                unsafe_allow_html=True)
                                with qc3:
                                    with st.container(horizontal=True, gap="small"):
                                        if st.button("", icon=":material/edit:", key=f"qnote_editbtn_{_qid}",
                                                     help="Sửa"):
                                            st.session_state[qedit_key] = True
                                            st.rerun()
                                        if st.button("", icon=":material/delete:", key=f"qnote_del_{_qid}",
                                                     help="Xoá"):
                                            delete_quick_note(_qid)
                                            st.rerun()

                with st.container(key="note_main", gap="small"):
                    with st.container(key="note_label_content", gap="xsmall"):
                        st.markdown("<span class='rl-book'>Ghi chú chính</span>", unsafe_allow_html=True)
                        if not st.session_state.get(edit_key, False):
                            if cur:
                                with st.container(key="note_saved"):
                                    st.markdown(cur, unsafe_allow_html=True)
                            else:
                                st.markdown("<div class='note-empty'>Chưa có ghi chú cho ngày này.</div>",
                                            unsafe_allow_html=True)
                        else:
                            # Chế độ soạn: trình soạn Quill inline
                            content = st_quill(value=cur, html=True, toolbar=NOTE_TOOLBAR,
                                               placeholder="Viết vài dòng về ngày này…", key=quill_key)
                            style_quill()
                            _inject_note_editor_shortcuts()

                    # Hàng nút nằm NGOÀI note_label_content -- 2 container/2 gap tách biệt để
                    # khoảng nhãn↔nội dung (xsmall, sát) và khoảng nội dung↔nút (small, rộng hơn
                    # 1 chút) không bị ép về cùng 1 giá trị (xem chú thích CSS ở trên).
                    if not st.session_state.get(edit_key, False):
                        if cur:
                            if st.button("Sửa ghi chú", icon=":material/edit:", key=f"note_editbtn_{day}"):
                                _enter_edit()
                                st.rerun()
                        else:
                            if st.button("Thêm ghi chú", icon=":material/add:", type="primary",
                                         key=f"note_addbtn_{day}"):
                                _enter_edit()
                                st.rerun()
                    else:
                        with st.container(key="note_actions", horizontal=True, gap="small"):
                            if st.button("Cập nhật", icon=":material/check:", type="primary",
                                         key=f"note_save_{day}"):
                                save_note(day, content if content is not None else st.session_state.get(quill_key, ""))
                                st.session_state[edit_key] = False
                                st.rerun()
                            if st.button("Huỷ", icon=":material/close:", key=f"note_cancel_{day}"):
                                st.session_state[edit_key] = False
                                st.rerun()
                            if cur and st.button("Xoá ghi chú", icon=":material/delete:", key=f"note_del_{day}"):
                                save_note(day, "")
                                st.session_state[edit_key] = False
                                st.rerun()


def render_notes_journal(period_key, kind, df_all):
    """Liệt kê (chỉ đọc) ghi chú + appointment lịch + phần đọc sách/Gundam của các ngày thuộc
    một kỳ (tuần/tháng) -- một dòng cho mỗi ngày có ÍT NHẤT 1 trong 4 nguồn (hợp/union): ghi
    chú, lịch, đọc sách, HOẶC giữ 1 kỷ lục Bảng vàng (xem _compute_alltime_records()) -- nguồn
    thứ 4 này đảm bảo 1 ngày kỷ lục nhưng không có ghi chú/lịch/đọc sách nào vẫn hiện dòng riêng
    để chip 🏆 có chỗ hiện ra, đúng lời hứa "chip Kỷ lục luôn thấy được ở Nhật ký Tuần/Tháng"
    trong tab Hướng dẫn. Mỗi dòng theo thứ tự cố định: chip Kỷ lục (nếu có) → chip Lịch (kèm
    heading nhỏ "Lịch") → chip đọc sách (tự nhóm+gắn nhãn theo từng cuốn/series qua
    _book_chips_html()) → ghi chú nhanh đang chờ (chỉ đọc, xem _quick_note_chips_html()) → nhãn
    "Ghi chú chính" + ghi chú (nhãn chỉ hiện nếu ngày đó có ghi chú). Không lọc Gundam khỏi nguồn
    đọc sách ở đây -- đây là nhật ký chung của cả app, không riêng tab Sách. Ô Thứ/ngày mỗi dòng
    là link nhảy sang đúng Báo cáo ngày hôm đó.
    Dựng HTML tự thân (1 khối st.markdown duy nhất) thay vì st.columns() lặp lại -> khoảng
    cách quanh mỗi đường kẻ do CSS box model tự nhiên quyết định, không lệ thuộc chiều cao
    hàng do Streamlit tự tính (xem chú thích ở khối CSS .jrows)."""
    day_badges = _compute_alltime_records(df_all)["day_badges"]

    def _in_period(dt_series):
        return (dt_series.dt.strftime('%Y-%m') == period_key) if kind == 'month' \
            else (dt_series.dt.strftime('%G-W%V') == period_key)

    def _date_in_period(d):
        return (d.strftime('%Y-%m') == period_key) if kind == 'month' \
            else (d.strftime('%G-W%V') == period_key)

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

    qn = load_quick_notes()
    if not qn.empty:
        qn = qn.assign(_d=qn['Thời gian'].dt.normalize())
        qn = qn[_in_period(qn['_d'])]

    note_days = set(nd['_d']) if not nd.empty else set()
    event_days = set(wc['_d']) if not wc.empty else set()
    reading_days = set(rl['_d']) if not rl.empty else set()
    quick_note_days = set(qn['_d']) if not qn.empty else set()
    record_days = {pd.Timestamp(d) for d in day_badges if _date_in_period(d)}
    days = sorted(note_days | event_days | reading_days | quick_note_days | record_days)
    if not days:
        st.caption("Chưa có ghi chú, lịch hoặc phần đọc sách nào trong kỳ này.")
        return

    rows_html = ''
    for d in days:
        rec_html = _record_chips_html(day_badges.get(d.date()))
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
        qnote_html = _quick_note_chips_html(qn[qn['_d'] == d]) if d in quick_note_days else ''
        note_html = ''
        if d in note_days:
            note_html = (f"<span class='rl-book'>Ghi chú chính</span>"
                         f"<div class='note-html'>{str(nd[nd['_d'] == d].iloc[0]['Ghi chú'])}</div>")
        # Thứ/ngày là link nhảy sang đúng Báo cáo ngày hôm đó (đọc bởi initializer "day" mới
        # trong day_picker() -- xem chú thích ở đó).
        _href = f"?nav={quote('Hôm nay')}&day={d:%Y-%m-%d}"
        rows_html += (
            "<div class='jrow'>"
            f"<a class='jdate-link' href='{_href}' target='_self'>"
            f"<div class='jdate'><div class='jdowbig'>{VN_DAYS.get(d.day_name(), '')}</div>"
            f"<div class='jdm'>{d:%d/%m}</div></div></a>"
            f"<div>{rec_html}{cal_html}{read_html}{qnote_html}{note_html}</div>"
            "</div>"
        )
    with st.container(border=True, key=f"jcard_journal_{kind}"):
        st.markdown(f"<div class='jrows'>{rows_html}</div>", unsafe_allow_html=True)


def render_search():
    """Tìm kiếm theo từ khoá trên CẢ 3 nguồn: ghi chú, lịch (tiêu đề appointment), sách/Gundam
    (tên cuốn/series + tiêu đề phần) -- lọc trực tiếp trong Python trên text thuần, khối lượng
    dữ liệu nhỏ (vài trăm dòng mỗi nguồn cho vài năm dùng app) nên không cần full-text search
    phía Supabase. Kết quả gộp theo NGÀY (đúng 1 dòng cho mỗi ngày có ít nhất 1 nguồn khớp),
    hiện ĐỦ CẢ 3 nguồn của ngày đó (không chỉ riêng phần khớp) để giữ nguyên ngữ cảnh cả ngày --
    đúng khuôn .jrows/.jrow + thứ tự Lịch -> Đọc sách -> Ghi chú đã dùng ở Nhật ký."""
    q = st.text_input("Từ khoá", key="search_q", label_visibility="collapsed")
    if not q or len(q.strip()) < 2:
        return
    qq = q.strip()
    pat = re.escape(qq)

    nd = load_notes()
    if not nd.empty:
        nd = nd.assign(_d=pd.to_datetime(nd['Ngày'], errors='coerce'),
                        _plain=nd['Ghi chú'].map(_note_plain_text)).dropna(subset=['_d'])
    wc = load_work_calendar()
    if not wc.empty:
        wc = wc.assign(_d=wc['Thời gian bắt đầu'].dt.normalize())
    rl = load_reading_log()
    if not rl.empty:
        rl = rl.assign(_d=rl['Ngày hoàn thành'].dt.normalize())

    note_hits = set(nd[nd['_plain'].str.contains(pat, case=False, na=False)]['_d']) if not nd.empty else set()
    cal_hits = set(wc[wc['Tiêu đề'].astype(str).str.contains(pat, case=False, na=False)]['_d']) if not wc.empty else set()
    rl_hits = set(rl[rl['Tiêu đề phần'].astype(str).str.contains(pat, case=False, na=False)
                     | rl['Cuốn sách'].astype(str).str.contains(pat, case=False, na=False)]['_d']) if not rl.empty else set()

    hit_days = sorted(note_hits | cal_hits | rl_hits, reverse=True)
    if not hit_days:
        st.info(f"Không tìm thấy kết quả nào chứa \"{q}\".")
        return

    _search_icon = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='15' height='15' "
                    "fill='var(--text-2)' style='vertical-align:-2px;margin-right:6px;'>"
                    "<path d='M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 "
                    "9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 "
                    "14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z'/></svg>")
    st.markdown(
        "<div class='glass-card' style='padding:12px 18px;margin:0 0 16px;display:flex;align-items:center;'>"
        f"<span style='font-size:14px;color:var(--text-2);'>{_search_icon}Tìm thấy "
        f"<b style='color:var(--text);'>{len(hit_days)}</b> ngày khớp.</span></div>",
        unsafe_allow_html=True)

    rows_html = ''
    for d in hit_days:
        cal_html = ''
        day_events = wc[wc['_d'] == d].sort_values('Thời gian bắt đầu') if not wc.empty else wc
        if not day_events.empty:
            chips = ''.join(
                f"<span class='jchip'><span class='ck'>{r['Thời gian bắt đầu']:%H:%M}</span>"
                f"<span class='cv'>{html_escape(str(r['Tiêu đề']))}</span></span>"
                for _, r in day_events.iterrows())
            cal_html = f"<div style='margin-bottom:6px;'><span class='rl-book'>Lịch</span>{chips}</div>"
        read_html = _book_chips_html(rl[rl['_d'] == d]) if not rl.empty and d in set(rl['_d']) else ''
        note_html = ''
        if not nd.empty and d in set(nd['_d']):
            note_html = f"<div class='note-html'>{html_escape(_note_snippet(nd[nd['_d'] == d].iloc[0]['Ghi chú'], qq))}</div>"
        _href = f"?nav={quote('Hôm nay')}&day={d:%Y-%m-%d}"
        rows_html += (
            "<div class='jrow'>"
            f"<a class='jdate-link' href='{_href}' target='_self'>"
            f"<div class='jdate'><div class='jdowbig'>{VN_DAYS.get(d.day_name(), '')}</div>"
            f"<div class='jdm'>{d:%d/%m/%Y}</div></div></a>"
            f"<div>{cal_html}{read_html}{note_html}</div>"
            "</div>"
        )
    with st.container(border=True, key="jcard_search"):
        st.markdown(f"<div class='jrows'>{rows_html}</div>", unsafe_allow_html=True)


def _book_chips_html(day_g):
    """Chip các phần đã đọc trong 1 ngày, nhóm theo cuốn sách/series kèm nhãn tên sách (1 ngày
    có thể có phần từ nhiều cuốn). Sách LUÔN xếp trước Gundam (thứ tự Lịch -> Sách -> Gundam
    người dùng yêu cầu) -- sort ổn định theo is_gundam, giữ nguyên thứ tự gặp trong mỗi nhóm.
    Mỗi chip gắn thêm class 'book'/'gundam' (icon Material tương ứng, xem CSS .jchip.book/
    .jchip.gundam) để phân biệt nhanh 2 loại không cần đọc chữ.
    Dùng chung cho render_note_editor, render_notes_journal, _reading_rows_html."""
    out = ''
    groups = list(day_g.groupby('Cuốn sách', sort=False))
    groups.sort(key=lambda kv: _is_gundam_list(kv[1]['Sách (gốc)'].iloc[0]))
    for book, g in groups:
        _cls = 'jchip gundam' if _is_gundam_list(g['Sách (gốc)'].iloc[0]) else 'jchip book'
        parts = ''.join(f"<span class='{_cls}'>{html_escape(str(r['Tiêu đề phần']))}</span>"
                        for _, r in g.sort_values('Ngày hoàn thành').iterrows())
        out += _chip_row_html(html_escape(book), parts)
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
            _cls = 'jchip gundam' if _is_gundam_list(day_g['Sách (gốc)'].iloc[0]) else 'jchip book'
            chips_html = ''.join(f"<span class='{_cls}'>{html_escape(str(r['Tiêu đề phần']))}</span>"
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
    mỗi năm hiện vài số liệu trong khung chip + ghi chú (nếu có). Chỉ đọc. Mỗi dòng năm cũng
    theo đúng thứ tự cố định chip Kỷ lục (nếu năm đó rơi đúng ngày giữ kỷ lục, xem
    _compute_alltime_records()) → chip Lịch → chip đọc sách → số liệu phiên → ghi chú nhanh đang
    chờ → nhãn "Ghi chú chính" + ghi chú, nhất quán với render_note_editor()/render_notes_journal()."""
    day_badges = _compute_alltime_records(df_all)["day_badges"]
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
    # Ghi chú nhanh, cùng ngày/tháng ở các năm trước
    quick_notes = {}  # year -> DataFrame
    qn = load_quick_notes()
    if not qn.empty:
        qn_m = qn[(qn['Thời gian'].dt.month == m) & (qn['Thời gian'].dt.day == d)
                  & (qn['Thời gian'].dt.year < sel.year)]
        for y, g in qn_m.groupby(qn_m['Thời gian'].dt.year):
            quick_notes[int(y)] = g

    years = sorted(set(stats) | set(notes) | set(events) | set(reading) | set(quick_notes), reverse=True)
    if not years:
        _cal = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='34' height='34' "
                "fill='var(--text-4)'><path d='M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 "
                "2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2z'/></svg>")
        st.markdown(
            "<div class='glass-card' style='padding:22px 18px;text-align:center;'>"
            f"<div style='margin-bottom:8px;'>{_cal}</div>"
            "<div style='font-size:1.0rem;font-weight:600;color:var(--text);'>"
            f"Chưa có dữ liệu ngày {d:02d}/{m:02d} ở các năm trước</div>"
            "<div style='font-size:13px;color:var(--text-2);margin-top:4px;'>"
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
        rec_html = _record_chips_html(day_badges.get(date(y, m, d)))
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
        qnote_html = _quick_note_chips_html(quick_notes[y]) if y in quick_notes else ''
        note_block = (f"<span class='rl-book'>Ghi chú chính</span><div class='note-html'>{notes[y]}</div>"
                      if notes.get(y) else '')
        rows_html += (
            "<div class='jrow'>"
            f"<div class='jdate'><div class='jyear'>{y}</div>"
            f"<div class='jdow'>{wd}</div><div class='jdm'>{d:02d}/{m:02d}</div></div>"
            f"<div>{rec_html}{cal_html}{read_html}{chips_html}{qnote_html}{note_block}</div>"
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
    LVL_COLORS = [("#3a3a3c" if IS_DARK else "#e5e5ea")] + _teal_shades(7)

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
    # lvl 6,7 (2 bậc teal đậm nhất ở light) đủ tối để cần chữ trắng, còn lại chữ xám mờ. Ramp teal
    # ĐẢO CHIỀU khi dark (xem _teal_shades) -> điều kiện sáng/tối của chữ cũng đảo theo.
    _txt_hi, _txt_lo = ("#1c1c1e", "#98989d") if IS_DARK else ("#ffffff", "#a7a7ac")
    text = base.mark_text(baseline='middle', fontSize=10).encode(
        text='day:Q',
        color=alt.condition("datum.lvl >= 6", alt.value(_txt_hi), alt.value(_txt_lo)),
        tooltip=cal_tooltip
    )
    chart = (rect + text).properties(
        width=alt.Step(34), height=alt.Step(34),
        # padding phải bù cho vùng nhãn thứ bên trái -> lưới căn giữa trong thẻ
        padding={"left": 0, "right": 64, "top": 5, "bottom": 5},
        # Vega tự vẽ nền riêng cho SVG (mặc định ăn theo màu nền trang, không phải trắng) -> để
        # trong suốt cho nền thẻ bọc ngoài (--card, đổi theo IS_DARK) lộ ra, tránh viền lệch tông.
        background='transparent',
    ).configure_view(strokeWidth=0)
    st.altair_chart(chart, width='content')


DTBL_CSS = """
<style>
.dtbl-wrap { overflow:auto; max-height:560px; border-radius:16px; border:1px solid var(--border); background:var(--card); box-shadow:0 1px 1px rgba(0,0,0,0.02); }
.dtbl { border-collapse:collapse; width:100%; font-size:14px; font-family:-apple-system,BlinkMacSystemFont,sans-serif; }
.dtbl th, .dtbl td { padding:4px 9px; text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }
.dtbl thead th { position:sticky; top:0; z-index:2; background:var(--bg); color:var(--text-2); font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.3px; border-bottom:1px solid var(--divider); }
.dtbl td.lbl, .dtbl th.lbl { text-align:left; position:sticky; left:0; background:var(--card); z-index:1; }
.dtbl thead th.lbl { z-index:3; background:var(--bg); }
/* Header 2 hàng (khi cột trải nhiều năm): hàng năm (nhóm colspan) đứng trên, hàng nhãn kỳ
   (Tuần/Tháng) đứng dưới -- cả 2 đều "dính" khi cuộn dọc, xếp chồng đúng vị trí bằng top. */
.dtbl thead tr.yr th { top:0; font-size:10px; color:var(--text-2); background:var(--chip); border-bottom:1px solid var(--divider); }
.dtbl thead tr.wk th { top:22px; }
.dtbl th.yrspan { text-align:center; border-right:1px solid var(--divider); }
.dtbl th.yrspan:last-child { border-right:none; }
.dtbl thead tr.yr th.lbl { z-index:3; background:var(--chip); }
.dtbl tr.cat td { font-weight:700; color:var(--text); border-top:1px solid var(--divider); }
.dtbl tr.cat td.lbl { background:var(--card); }
.dtbl tr.proj td { color:var(--text-2); }
.dtbl tr.proj td.lbl { padding-left:34px; color:var(--text-2); font-weight:400; }
.dtbl td.zero { color:var(--text-4); }
.dtbl td.tot { border-left:1px solid var(--divider); font-weight:600; color:var(--text); }
.dtbl tr.proj td.tot { font-weight:500; color:var(--text-2); }
.dtbl th.txt, .dtbl td.txt { text-align:left; }
.dtbl tr.prow td { color:var(--text); font-weight:400; border-top:1px solid var(--divider); }
.dtbl tr.prow td.lbl { color:var(--text-3); font-weight:500; }
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
    """Một mục trong trang Hướng dẫn: ảnh minh hoạ + giải thích chi tiết (+ mẹo). Key khoá theo cả
    img lẫn title (không chỉ img) -- vài sub-tab cố ý dùng lại cùng 1 ảnh minh hoạ cho 1 góc nhìn
    khác (vd "Nhịp làm việc" tái dùng ảnh heatmap.png/table.png/nam.png đã dùng ở sub-tab khác),
    chỉ khoá theo img sẽ đụng key trùng giữa 2 guide_item khác nhau."""
    _title_slug = re.sub(r'[^a-zA-Z0-9]+', '_', title).strip('_')[:40]
    with st.container(border=True, key=f"guide_{img}_{_title_slug}"):
        if where:
            st.markdown(f"<div style='font-size:11px;font-weight:700;color:var(--text-2);"
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


def guide_update(pr_no, title, bullets):
    """Một mục trong tab "Cập nhật": không có ảnh (đổi UI qua nhiều bản nhỏ nên chụp ảnh sẽ lỗi
    thời rất nhanh) -- chỉ tiêu đề + số PR + danh sách gạch đầu dòng, dùng chung khung thẻ với
    guide_item() qua tiền tố key "guide_" (CSS [class*="st-key-guide"] áp cho cả 2)."""
    with st.container(border=True, key=f"guide_update_{pr_no}"):
        st.markdown(
            f"<div style='font-size:11px;font-weight:700;color:var(--text-2);"
            f"text-transform:uppercase;letter-spacing:.5px;'>PR #{pr_no}</div>",
            unsafe_allow_html=True)
        st.markdown(f"#### {title}")
        st.markdown("\n".join(f"- {b}" for b in bullets))


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


# --- LOGO: mark "vòng tuổi cây" (growth ring) + wordmark, thiết kế nhập từ Claude Design
# (xem Forest_Dashboard_Logo_standalone.html) -- 3 cung tròn đồng tâm đứt khúc nhạt dần ra ngoài,
# gợi ẩn dụ "mỗi vòng là một lần nhìn lại" khớp tinh thần hồi cứu của app; wordmark "Forest" bằng
# font display Instrument Serif + nhãn "Dashboard" nhỏ/nhạt bên cạnh, lặp lại đúng cấu trúc
# "hero to + nhãn phụ nhỏ xám" dùng xuyên suốt UI. Cần dùng được ở CẢ 2 nơi: trang đăng nhập
# (chạy TRƯỚC khối inject :root CSS var) và title chính (chạy SAU) -- nên tự chứa @font-face
# riêng + chọn màu chữ bằng literal Python theo IS_DARK, không phụ thuộc var(--text)/var(--accent).
@st.cache_resource
def _logo_font_b64():
    with open(os.path.join("assets", "fonts", "InstrumentSerif-Regular-latin.woff2"), "rb") as f:
        return base64.b64encode(f.read()).decode()

_LOGO_FONT_FACE = (
    "@font-face { font-family:'Instrument Serif'; font-style:normal; font-weight:400; "
    f"font-display:swap; src:url(data:font/woff2;base64,{_logo_font_b64()}) format('woff2'); "
    "unicode-range:U+0000-00FF,U+2018-201F; }"
)


def _logo_mark_svg(size):
    """SVG mark riêng, tô theo ACCENT đang chọn (không hardcode teal -- tự đổi theo 14 màu accent
    người dùng có thể chọn ở Tuỳ biến). Tỉ lệ bán kính/độ dày/dash giữ đúng bản thiết kế gốc
    (mốc 28px)."""
    s = size / 28
    c = size / 2
    # (bán kính, độ dày nét, dash-on, dash-off, góc xoay, độ đục) -- đúng 3 giá trị thiết kế gốc
    specs = [(4.48, 2.86, 17.45, 10.7, -30, 1), (7.84, 2.21, 24.63, 24.63, 140, 0.7),
             (11.2, 1.56, 49.26, 21.11, 250, 0.45)]
    circles = "".join(
        f"<circle cx='{c:.2f}' cy='{c:.2f}' r='{r * s:.2f}' fill='none' stroke='{ACCENT}' "
        f"stroke-opacity='{op}' stroke-width='{w * s:.2f}' stroke-linecap='round' "
        f"stroke-dasharray='{d1 * s:.2f} {d2 * s:.2f}' transform='rotate({rot} {c:.2f} {c:.2f})'></circle>"
        for r, w, d1, d2, rot, op in specs)
    return f"<svg width='{size}' height='{size}' viewBox='0 0 {size} {size}'>{circles}</svg>"


def _wordmark_html(layout="header"):
    """Mark + wordmark dùng chung cho trang đăng nhập ("login", to, xếp dọc) và title chính
    ("header", nằm ngang -- mark bên trái, cụm chữ Forest/Dashboard xếp dọc bên phải, gọn theo
    chiều cao vì header lặp lại trên MỌI trang, khác login chỉ hiện 1 lần nên giữ xếp dọc to).

    Span "Forest" dùng line-height:1.25 (KHÔNG phải 1) -- Instrument Serif có cap-height/overshoot
    của chữ hoa cao hơn hẳn chữ thường; line-height:1 để lại quá ít khoảng đệm phía trên nên trên
    mobile Safari (đã xác nhận qua ảnh chụp thật) chữ "F" bị cắt cụt phần trên, đọc nhầm thành
    "rorest" -- Chromium desktop không tái hiện được lỗi này (khác biệt engine WebKit/Blink khi xử
    lý half-leading của font có ascent bất thường), nên phải rộng rãi hơn số 1 an toàn thay vì tin
    vào việc test trên Chromium là đủ."""
    _text = "#f2f2f7" if IS_DARK else "#1d1d1f"
    _text2 = "#98989d" if IS_DARK else "#6e6e73"
    if layout == "login":
        mark, forest_sz, dash_sz, gap_outer = 72, 46, 14, 22
        return (
            f"<style>{_LOGO_FONT_FACE}</style>"
            f"<div style='display:flex;flex-direction:column;align-items:center;gap:{gap_outer}px;'>"
            f"{_logo_mark_svg(mark)}"
            "<div style='display:flex;flex-direction:column;align-items:center;gap:4px;'>"
            f"<span style=\"font-family:'Instrument Serif',serif;font-size:{forest_sz}px;"
            f"color:{_text};letter-spacing:0.01em;line-height:1.25;\">Forest</span>"
            f"<span style='font-size:{dash_sz}px;color:{_text2};text-transform:uppercase;"
            "letter-spacing:0.08em;'>Dashboard</span></div></div>"
        )
    mark, forest_sz, dash_sz, gap_outer = 48, 36, 14, 14
    return (
        f"<style>{_LOGO_FONT_FACE}</style>"
        f"<div style='display:flex;flex-direction:row;align-items:center;justify-content:center;"
        f"gap:{gap_outer}px;'>"
        f"{_logo_mark_svg(mark)}"
        "<div style='display:flex;flex-direction:column;gap:2px;'>"
        f"<span style=\"font-family:'Instrument Serif',serif;font-size:{forest_sz}px;"
        f"color:{_text};letter-spacing:0.01em;line-height:1.25;\">Forest</span>"
        f"<span style='font-size:{dash_sz}px;color:{_text2};text-transform:uppercase;"
        "letter-spacing:0.08em;line-height:1;'>Dashboard</span></div></div>"
    )


# --- GIAO DIỆN CHÍNH ---
# page_icon nhận chuỗi SVG thô trực tiếp (Streamlit tự nhận diện qua regex "<svg " ở đầu chuỗi,
# tự thêm xmlns nếu thiếu, rồi encode base64 thành data URI) -- không cần rasterize ra PNG. Icon
# Material trước đây (":material/forest:") luôn ra màu đen bất kể theme (giới hạn đã biết của
# Streamlit với favicon Material icon) -- SVG tự vẽ thì giữ được màu accent thật.
st.set_page_config(page_title="Forest Dashboard", page_icon=_logo_mark_svg(64), layout="wide")

# Đăng nhập Google (tuỳ chọn) -- chỉ bật khi có mục [auth] trong secrets (xem
# .streamlit/secrets.toml.example). Không cấu hình thì app chạy như cũ, không cổng đăng nhập nào
# (tiện cho chạy thử local/mock) -- nhưng NẾU đã cấu hình [auth] thì bắt buộc phải có luôn
# ALLOWED_EMAIL, không được để "đăng nhập được nhưng ai vào cũng lọt" (an toàn theo kiểu mặc định
# chặn khi cấu hình dở dang, thay vì mặc định mở).
try:
    _auth_configured = bool(st.secrets.get("auth", {}).get("client_id"))
except Exception:
    _auth_configured = False
if _auth_configured:
    if not st.secrets.get("ALLOWED_EMAIL"):
        st.error(
            "**Cấu hình đăng nhập chưa đầy đủ.** Đã có mục `[auth]` nhưng thiếu `ALLOWED_EMAIL` "
            "trong secrets -- không xác định được ai được phép vào app. Xem README.")
        st.stop()
    if not st.user.is_logged_in:
        # Màn hình này render TRƯỚC khối inject :root CSS var (nằm sau cổng đăng nhập) -> không
        # dùng var(--text-2) được ở đây (chưa tồn tại trong DOM), phải tự chọn literal theo IS_DARK
        # -- _wordmark_html() đã tự lo việc này (xem định nghĩa), không cần lặp lại ở đây.
        _login_txt2 = "#98989d" if IS_DARK else "#6e6e73"
        st.markdown(
            "<div style='max-width:420px;margin:12vh auto 24px;text-align:center;'>"
            f"<div style='margin-bottom:18px;'>{_wordmark_html('login')}</div>"
            f"<div style='color:{_login_txt2};'>Đăng nhập để tiếp tục.</div></div>",
            unsafe_allow_html=True)
        _login_col = st.columns([1, 1, 1])[1]
        with _login_col:
            st.button("Đăng nhập bằng Google", icon=":material/login:", type="primary",
                       use_container_width=True, on_click=st.login)
        st.stop()
    if st.user.email != st.secrets["ALLOWED_EMAIL"]:
        st.error(f"Tài khoản **{st.user.email}** không có quyền truy cập app này.")
        st.button("Đăng xuất", icon=":material/logout:", on_click=st.logout)
        st.stop()

try:
    _has_supabase_secrets = bool(st.secrets.get("SUPABASE_URL")) and bool(st.secrets.get("SUPABASE_KEY"))
except Exception:
    _has_supabase_secrets = False
if not _has_supabase_secrets:
    st.error(
        "**Chưa cấu hình Supabase.** App cần `SUPABASE_URL` và `SUPABASE_KEY` trong "
        "`.streamlit/secrets.toml` (xem `.streamlit/secrets.toml.example`) để đọc/ghi dữ liệu.")
    st.stop()

# Token ngữ nghĩa cho toàn bộ CSS/HTML tự viết trong app (khối CSS lớn bên dưới + các khối CSS
# con + f-string HTML rải rác) -- (light, dark), bảng dark theo đúng systemGray của Apple (app
# đã tình cờ dùng đúng các mã hex đó ở light: #d1d1d6=gray4, #e5e5ea=gray5, #aeaeb2=gray2,
# #c7c7cc=gray3...) nên có sẵn cặp tương ứng chuẩn, không phải tự chế màu mới.
_TOK = {
    "bg":      ("#f5f5f7", "#1c1c1e"),
    "card":    ("#ffffff", "#2c2c2e"),
    "card-tl": ("rgba(255,255,255,0.8)", "rgba(58,58,60,0.8)"),   # nền input mờ (date/select)
    "text":    ("#1d1d1f", "#f2f2f7"),
    "text-2":  ("#86868b", "#98989d"),   # nhãn phụ (gộp cả #6e6e73/#9a9aa0 cũ)
    "text-3":  ("#aeaeb2", "#636366"),   # nhãn mờ (gộp cả #a7a7ac cũ)
    "text-4":  ("#c7c7cc", "#48484a"),   # rất mờ (gộp cả #cfcfd4/#d2d2d7 cũ)
    "border":  ("#d1d1d6", "#3a3a3c"),
    "chip":    ("#f0f1f4", "#3a3a3c"),   # nền chip (gộp cả #f7f7f9/#eef0f2/#fafafa cũ)
    "divider": ("rgba(0,0,0,0.08)", "rgba(255,255,255,0.12)"),   # gộp mọi rgba(0,0,0,0.05-0.14)
}
_root_vars = "".join(f"--{k}:{v[1] if IS_DARK else v[0]};" for k, v in _TOK.items())
st.markdown(
    f"<style>:root{{--accent:{ACCENT};--accent-rgb:{ACCENT_RGB};--accent-dark:{ACCENT_DARK};"
    f"{_root_vars}}}</style>",
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
        background-color: var(--bg);
    }
    
    .block-container { max-width: 1200px !important; margin: 0 auto !important; padding-top: 2rem !important; }
    
    .glass-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 1px 1px rgba(0,0,0,0.02);
    }

    h1, h2, h3 { color: var(--text) !important; font-weight: 600 !important; letter-spacing: -0.5px !important; }
    hr { border-color: var(--divider) !important; }
    
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
        background-color: var(--card) !important;
        color: var(--accent) !important;
        border-radius: 8px !important;
        border: 1px solid var(--border) !important;
        font-weight: 500 !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
    }
    div[data-testid="stButton"] button { width: 100%; }

    .stSelectbox > div > div, .stTextInput > div > div > input {
        border-radius: 8px !important;
        border: 1px solid var(--border) !important;
        background-color: var(--card-tl) !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
    }

    [data-testid="stPlotlyChart"], [data-testid="stVegaLiteChart"] {
        display: flex !important;
        justify-content: center !important;
        width: 100% !important;
        margin: 0 auto !important;
        background: var(--card);
        border: 1px solid var(--border);
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
    .stat-panel .sp-hi { flex: 1; min-width: 130px; padding: 2px 18px; border-right: 1px solid var(--divider); }
    .stat-panel .sp-hi:first-child { padding-left: 2px; }
    .stat-panel .sp-hi:last-child { border-right: none; }
    .stat-panel .sp-l { font-size: 11px; color: var(--text-2); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    .stat-panel .sp-v { font-size: 32px; font-weight: 600; letter-spacing: -0.5px; line-height: 1.18; color: var(--text); }
    .stat-panel .sp-d { font-size: 13px; font-weight: 500; margin-top: 2px; }
    /* Mỗi nhóm = 1 hàng: nhãn bên trái, các chip cùng hàng -> tiết kiệm chiều cao */
    .stat-panel .sp-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; margin-top: 12px; }
    .stat-panel .sp-sub { font-size: 11px; color: var(--text-2); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin: 0; flex: 0 0 160px; }
    .stat-panel .sp-chips { display: flex; flex-wrap: wrap; gap: 8px; flex: 1 1 auto; }
    @media (max-width: 640px) { .stat-panel .sp-sub { flex-basis: 100%; } }
    /* white-space KHÔNG nowrap (khác vẻ ngoài "viên thuốc" gọn thường thấy) -- vài chip mang giá
       trị tự do dài (vd "Phần gần nhất" là tên chương/tập, không có độ dài cố định) sẽ tràn ra
       ngoài khung thẻ trên màn hẹp nếu ép 1 dòng; max-width + word-break đảm bảo chip luôn co
       vừa bề rộng thẻ, xuống dòng bên TRONG chip thay vì tràn ra ngoài. Chip giá trị ngắn (đa số)
       không bị ảnh hưởng vì nội dung đã ngắn hơn 1 dòng sẵn. */
    .stat-panel .chip { border-radius: 10px; padding: 7px 12px; font-size: 13px; white-space: normal;
        max-width: 100%; overflow-wrap: break-word; word-break: break-word; background: var(--chip); }
    .stat-panel .chip .ck { color: var(--text-2); }
    .stat-panel .chip .cv { font-weight: 600; color: var(--text); margin-left: 5px; }
    .stat-panel .chip .cd { font-weight: 500; margin-left: 6px; }
    .stat-panel .chip.tw { background: rgba(var(--accent-rgb),0.10); }
    .stat-panel .sp-divider { border-top: 1px solid var(--divider); margin: 10px 0 2px; }
    .stat-panel .sp-glabel { font-size: 11px; font-weight: 700; color: var(--accent); text-transform: uppercase; letter-spacing: 0.6px; margin-top: 10px; }
    .stat-panel > .sp-glabel:first-child { margin-top: 0; }
    /* .sp-row có margin-top:12px để tách với .sp-hero phía trên -- khi KHÔNG có hero (vd panel
       "Tham khảo cho lên kế hoạch" chỉ có sections, không hero_items), .sp-row là con đầu tiên
       nên margin đó cộng dồn với padding 20px của card, làm lề trên dày hơn lề dưới rõ rệt. */
    .stat-panel > .sp-row:first-child { margin-top: 0; }
    .stat-panel .chip.tw .ck { color: var(--accent-dark); }
    .stat-panel .chip.tw .cv { color: var(--accent); }
    .section-hd { font-size: 15px; font-weight: 700; color: var(--text); margin: 22px 0 6px; letter-spacing: -0.2px; }
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
        border-bottom: 2px solid var(--border) !important;
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
        color: var(--text) !important;
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
        color: var(--text-2) !important; padding: 8px 4px !important; margin: 0 14px !important;
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

    /* Sub-tab của trang Hướng dẫn -- cùng khuôn Tổng quan/Chi tiết (Sách/Gundam) ở trên, tái
       dùng nguyên 2 rule để 3 nơi trong app nhất quán 1 kiểu "tab gạch chân". Key đặt
       "help_subtabs" (không phải "guide_...") CỐ Ý -- tránh khớp nhầm rule
       [class*="st-key-guide"] bên dưới (khớp theo tiền tố con chuỗi, "guide_tabs" sẽ vô tình
       ăn theo kiểu thẻ card nền trắng của guide_item/guide_update, làm cả thanh tab bị bọc
       khung trắng thay vì để lộ nền xám của trang, như đã xảy ra và cần sửa). */
    .st-key-help_subtabs [data-baseweb="tab-list"] { justify-content: center !important; flex-wrap: wrap !important; }
    .st-key-help_subtabs [data-baseweb="tab-border"] { display: none !important; }

    /* Pagination (bảng phiên) căn giữa: stPagination là flex full-width nhưng justify
       flex-start -> đẩy hàng nút vào giữa */
    .st-key-db_pag [data-testid="stPagination"] { justify-content: center !important; }

    /* Bộ chọn kỳ/ngày (period_stepper key="stepper_x", day_picker key="day_stepper"): luôn 1
       hàng, co vừa cả mobile -- chọn theo substring "stepper" (không phải tiền tố "st-key-
       stepper") để khớp được cả 2 kiểu key, vì "day_stepper" không có "stepper" ngay sau
       "st-key-" như "stepper_x". Thiếu rule này, cột chứa st.date_input (min-width mặc định
       của Streamlit ăn theo nội dung) sẽ bị đẩy xuống dòng riêng trên mobile thay vì co lại
       vừa tỉ lệ cột như st.selectbox của period_stepper. */
    [class*="stepper"] [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 6px !important; }
    [class*="stepper"] [data-testid="stColumn"] { min-width: 0 !important; }

    /* st.date_input (hộp chọn "Ngày" ở Hôm nay, "Từ ngày"/"Đến ngày" ở Đồng bộ lịch nâng cao)
       mặc định mang màu đỏ gốc của theme Streamlit (#FF4B4B) -- không liên quan gì tới accent
       đang chọn, khiến hộp trông lệch tông so với hộp chọn kỳ cạnh nó (period_stepper, dùng
       st.selectbox, viền xám trung tính #d1d1d6/nền trắng mờ). Đồng bộ lại viền/nền theo đúng
       kiểu selectbox, còn màu ngày đang chọn trong lịch bật lên đổi theo accent. Lịch bật lên
       (data-baseweb="calendar") được BaseWeb mount ra ngoài container widget (portal ở cấp
       body), nên phải chọn toàn cục theo [data-baseweb], không scope theo .st-key-... được --
       áp dụng cho MỌI date_input trong app, không riêng "Ngày" ở Hôm nay. */
    div[data-testid="stDateInput"] [data-baseweb="input"] {
        background: var(--card-tl) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        box-shadow: none !important;
    }
    div[data-testid="stDateInput"] [data-baseweb="input"]:focus-within {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 1px var(--accent) !important;
    }
    [data-baseweb="calendar"] [role="gridcell"][aria-label^="Selected"]::after {
        background: var(--accent) !important;
    }
    /* Khung lịch bật lên (data-baseweb="popover") -- dùng outline chứ không phải border: nội
       dung trắng bên trong popover có cùng kích thước với chính nó và vẽ đè lên trên, che mất
       border thường; outline không tham gia box model nên không bị che. Chỉ áp cho popover có
       chứa lịch (:has([data-baseweb="calendar"])) -- tức các ô chọn ngày -- KHÔNG áp cho danh
       sách lựa chọn của st.selectbox thường (cùng dùng data-baseweb="popover" nhưng không có
       lịch bên trong). */
    [data-baseweb="popover"]:has([data-baseweb="calendar"]) {
        outline: 1.5px solid var(--accent) !important;
        outline-offset: -1px;
    }

    /* Mọi hộp thả xuống (st.selectbox) trong app: viền đổi sang màu accent khi đang mở/focus,
       cùng hiệu ứng đã làm cho hộp chọn ngày ở trên -- áp dụng chung 1 lần ở đây cho TẤT CẢ
       selectbox (Kỳ ở period_stepper, "Chọn Nhóm hoặc Dự án", "Chọn để xem chi tiết"...) thay vì
       lặp lại rule riêng cho từng nơi. Hộp bo viền nằm ở div con ĐẦU TIÊN bên trong
       [data-baseweb="select"] (không có data-baseweb riêng để bám vào), nên chọn qua tổ hợp
       :focus-within + > div. */
    div[data-baseweb="select"]:focus-within > div {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 1px var(--accent) !important;
    }

    /* Mọi st.tabs() trong app (Tổng quan/Chi tiết ở Sách & Gundam, "1. Dữ liệu đầu vào" ở Tuỳ
       biến, sub-tab ở Hướng dẫn): tab đang chọn + vạch gạch chân mặc định lấy theo primaryColor
       cứng trong .streamlit/config.toml (#00a3ad) chứ KHÔNG theo accent đang chọn -- override
       lại bằng var(--accent) cho đồng bộ. */
    [data-baseweb="tab"][aria-selected="true"] { color: var(--accent) !important; }
    [data-baseweb="tab-highlight"] { background: var(--accent) !important; }

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

        /* Card "Ngày đang xem" (render_day_report): cố định 1 dòng trên mọi bề rộng, nhưng phần
           chữ nhãn + cụm "Cập nhật gần nhất" (kém thiết yếu hơn ngày/trạng thái đang xem) ẩn hẳn
           trên điện thoại thay vì cố nhét -- tổng độ rộng các phần "không co" (nhãn đủ chữ +
           ngày + trạng thái) đã vượt màn hình hẹp, nếu không ẩn sẽ bị cắt cụt giữa chữ (icon
           nhãn vẫn giữ lại, không mất hẳn ý nghĩa "đây là nhãn"). */
        .dcx-lbltxt, .dcx-upd { display: none !important; }
    }

    /* ===== Ghi chú ngày: ghi chú đã lưu hiện PHẲNG (không khung riêng bao quanh), giống hệt
       cách ghi chú hiện trong .jrows của Nhật ký -- chỉ .note-empty (trạng thái trống) mới có
       khung (viền chấm) để phân biệt rõ với có nội dung. ===== */
    .note-empty { font-size: 14px; color: var(--text-2); background: var(--chip);
        border: 1px dashed var(--divider); border-radius: 10px; padding: 13px 15px; margin-bottom: 12px; }

    /* ===== Hiển thị ghi chú dạng HTML (do Quill xuất ra) ===== */
    .note-html, .st-key-note_saved { font-size: 14.5px; line-height: 1.6; color: var(--text); }
    .st-key-note_saved [data-testid="stMarkdownContainer"],
    .st-key-note_saved [data-testid="stMarkdownContainer"] p,
    .st-key-note_saved [data-testid="stMarkdownContainer"] li { font-size: 14.5px !important; line-height: 1.6 !important; }
    .note-html p, .st-key-note_saved p { margin: 4px 0; }
    .note-html ul, .note-html ol, .st-key-note_saved ul, .st-key-note_saved ol { margin: 4px 0; padding-left: 22px; }
    /* Bỏ lề trên/dưới ở phần tử đầu & cuối để ghi chú căn thẳng dòng đầu (không bị lệch khung) */
    .note-html > :first-child, .st-key-note_saved > :first-child { margin-top: 0 !important; }
    .note-html > :last-child, .st-key-note_saved > :last-child { margin-bottom: 0 !important; }
    .note-html a, .st-key-note_saved a { color: var(--accent); }
    /* Thụt lề bullet/đánh số lồng nhau (Quill dùng class ql-indent-N trên <li>, KHÔNG lồng thật
       <ul><ul>). Dùng margin-left (không phải padding-left): marker gốc trình duyệt
       (list-style, khác Quill tự vẽ marker riêng trong ô soạn) định vị theo mép NGOÀI (margin)
       của <li>, không theo mép đệm (padding) -- padding-left chỉ đẩy CHỮ, để trơ dấu chấm đứng
       yên y hệt cấp 1 (đã xảy ra thực tế, xác nhận qua ảnh chụp). margin-left đẩy cả khối
       marker + chữ. CẦN !important: Streamlit tự đặt sẵn CSS cho <li> bên trong
       [data-testid="stMarkdownContainer"] (độ đặc hiệu (0,1,1), cao hơn 1 class selector đơn
       (0,1,0)) nên rule của ta thường bị đè mất nếu không ép. */
    .ql-indent-1 { margin-left: 2.0em !important; } .ql-indent-2 { margin-left: 4.0em !important; }
    .ql-indent-3 { margin-left: 6.0em !important; } .ql-indent-4 { margin-left: 8.0em !important; }
    .ql-indent-5 { margin-left: 10em !important; } .ql-indent-6 { margin-left: 12em !important; }

    /* ===== Container có viền (ghi chú ngày, nhật ký, ngày này năm trước, hướng dẫn) trông
       như glass-card ===== */
    .st-key-note_card, [class*="st-key-jcard"], [class*="st-key-guide"] {
        border-radius: 16px !important;
        border-color: var(--border) !important;
        box-shadow: 0 1px 1px rgba(0,0,0,0.02) !important;
        background: var(--card) !important;
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
        column-gap: 10px; padding: 16px 0; border-bottom: 1px solid var(--divider); }
    .jrows .jrow:last-child { border-bottom: none; }
    .jrows .jrow > .jdate, .jrows .jrow > a.jdate-link {
        border-right: 1px solid var(--divider); padding-right: 10px;
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
    .jdate .jdow { font-size: 15px; font-weight: 700; color: var(--text); margin-top: 6px; }
    .jdate .jdowbig { font-size: 18px; font-weight: 700; color: var(--text); letter-spacing: -0.3px; }
    .jdate .jdm { font-size: 13px; color: var(--text-2); font-weight: 500; margin-top: 2px; }
    .jchip { display: inline-block; background: var(--chip); border-radius: 10px; padding: 5px 11px;
        font-size: 12.5px; margin: 0 6px 6px 0; }
    .jchip .ck { color: var(--text-2); } .jchip .cv { font-weight: 600; color: var(--text); margin-left: 5px; }
    /* Icon Material Symbols (font Streamlit đã tự load sẵn cho :material/x: của riêng nó, nên
       dùng lại được ở đây không cần nhúng thêm font nào) đặt đầu 1 số jchip -- nhận diện nhanh
       loại chip không cần đọc chữ: 🏆 Kỷ lục (Bảng vàng), sách/gundam phân biệt phần đọc/xem. */
    .jchip.rec::before, .jchip.book::before, .jchip.gundam::before {
        font-family: 'Material Symbols Rounded'; font-size: 13px; vertical-align: -2px; margin-right: 3px;
    }
    /* Chữ (màu/độ đậm/cỡ) của Kỷ lục/Sách/Gundam CỐ Ý giống hệt .cv (chip Lịch) và giống nhau
       giữa 3 loại -- chỉ phân biệt qua icon + nền (riêng Kỷ lục), không qua định dạng chữ, để
       không loại nào trông "nổi" hơn loại khác. */
    .jchip.rec, .jchip.book, .jchip.gundam { font-weight: 600; color: var(--text); }
    .jchip.rec { background: rgba(var(--accent-rgb),0.10); }
    .jchip.rec::before { content: "emoji_events"; }
    .jchip.book::before { content: "menu_book"; }
    .jchip.gundam::before { content: "tv"; }
    /* Nhãn tên sách phía trên chip các phần đã đọc (box Đọc sách, Nhật ký đọc sách) -- nhại
       đúng pattern nhãn nhỏ đã dùng cho where= của guide_item và box "Lịch Work" cũ. */
    .rl-book { display: block; font-size: 11px; font-weight: 700; color: var(--text-2);
        text-transform: uppercase; letter-spacing: .5px; margin: 0 0 4px 2px; }
    /* Ghi chú ngày (Báo cáo ngày): bố cục 2 cột giống .jrows .jrow, nhưng dựng bằng st.columns()
       thật (không phải 1 khối HTML tĩnh) vì bên trong có widget Streamlit thật (Quill, nút) --
       không thể gói trong unsafe_allow_html. Selector dùng ĐÚNG chuỗi con trực tiếp (">"), không
       phải descendant thường ("khoảng trắng") -- cột phải (c_body) còn chứa nhiều st.columns()
       khác lồng sâu hơn (mỗi dòng Ghi chú nhanh, hàng nút Cập nhật/Huỷ/Xoá); nếu dùng descendant
       selector, rule này khớp NHẦM luôn "cột đầu tiên" của các st.columns() lồng bên trong đó,
       kẻ vạch thừa không mong muốn (bug đã gặp thật). ">" giới hạn CHỈ đúng 1 cặp cột ngoài cùng
       (Thứ/ngày | nội dung) của container key="note_row". */
    .st-key-note_row > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] >
        [data-testid="stColumn"]:first-child { border-right: 1px solid var(--divider); }
    @media (max-width: 640px) {
        .st-key-note_row > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] >
            [data-testid="stColumn"]:first-child { border-right: none; }
    }
    /* Top 3 (Báo cáo ngày): tách khỏi bảng số liệu phía trên */
    .st-key-day_top3 { margin-top: 14px; }
    /* Ghi chú nhanh: badge giờ nhỏ (.qn-time) + chữ ghi chú thường NGOÀI badge (.qn-text, cùng
       cỡ/màu .note-html) -- khác .jchip (cả giờ lẫn chữ đều tô nền), vì quick note nay là 1 câu
       đọc như ghi chú thật, không phải 1 nhãn nhỏ. .qn-line dùng ở bản CHỈ ĐỌC (Nhật ký
       Tuần/Tháng, Ngày này năm trước) -- bản có nút sửa/xoá ở Ghi chú ngày dựng bằng
       st.columns() thật nên không cần .qn-line (đã có [class*="st-key-qnote_row_"] lo margin). */
    .qn-time { display: inline-block; font-size: 12px; font-weight: 600; color: var(--text-2);
        background: var(--chip); border-radius: 8px; padding: 4px 9px; font-variant-numeric: tabular-nums;
        margin-right: 10px; vertical-align: middle; }
    .qn-text { font-size: 14.5px; color: var(--text); line-height: 1.5; }
    .qn-line { padding: 4px 0; }
    .qn-line + .qn-line { border-top: 1px solid var(--divider); }
    /* Ghi chú nhanh (Ghi chú ngày, có sửa/xoá): mỗi quick note 1 hàng st.columns() thật (badge
       giờ + text/ô sửa + cụm 2 nút) -- cụm nút dùng st.container(horizontal=True) (không phải
       st.columns() lồng bên trong nữa, tránh lặp lại đúng bug đã gặp: st.columns() lồng sâu bị
       CSS "cột ngoài cùng" ở trên khớp nhầm). [class*=...] khớp mọi container qnote_row_<id>
       cùng lúc (id đổi theo từng note). Ghi đè lại rule chung button[kind="secondary"] (nền/viền)
       giống cách làm ở nút chọn màu accent (Tuỳ biến) -- cần đủ đặc hiệu (kèm !important) mới
       thắng được rule đó. */
    [class*="st-key-qnote_row_"] { margin-bottom: 2px; }
    [class*="st-key-qnote_row_"] [data-testid="stHorizontalBlock"] { align-items: center; }
    [class*="st-key-qnote_row_"] div[data-testid="stButton"] button[kind="secondary"] {
        background: transparent !important; border: none !important; box-shadow: none !important;
        color: var(--text-3) !important; width: auto !important; min-height: 0 !important;
        height: 26px !important; padding: 0 !important;
    }
    [class*="st-key-qnote_row_"] div[data-testid="stButton"] button[kind="secondary"]:hover {
        color: var(--text) !important;
    }
    /* "Sửa ghi chú"/"Thêm ghi chú"/"Cập nhật"/"Huỷ"/"Xoá ghi chú" (Ghi chú ngày): mọi nút thao
       tác của Ghi chú chính đều nhỏ gọn tự co theo chữ, KHÔNG kéo giãn hết chiều rộng cột như
       mặc định (div[data-testid="stButton"] button { width:100% } ở trên) -- to hết cỡ nhìn lệch
       hẳn so với phần còn lại của thẻ (chip nhỏ, chữ ghi chú thường). note_actions (Cập nhật/Huỷ/
       Xoá) dùng st.container(horizontal=True) nên 3 nút tự nằm sát nhau thành 1 cụm, không cần
       st.columns() + use_container_width như trước. QUAN TRỌNG: Streamlit tự đặt sẵn
       min-height:40px cho MỌI nút (kiểm chứng qua getComputedStyle thật trên trình duyệt, không
       thấy được nếu chỉ đọc CSS nguồn) -- chỉ giảm padding/font-size KHÔNG đủ, nút vẫn cao 40px
       vì min-height thắng; phải tự đè min-height ở đây thì nút mới thực sự thấp lại. */
    [class*="st-key-note_editbtn_"] div[data-testid="stButton"] button,
    [class*="st-key-note_addbtn_"] div[data-testid="stButton"] button,
    .st-key-note_actions div[data-testid="stButton"] button {
        width: auto !important; padding: 5px 14px !important; font-size: 13px !important;
        min-height: 0 !important; height: auto !important;
    }
    /* note_label_content (nhãn "Ghi chú chính" + nội dung/Quill, gap="xsmall") tách riêng khỏi
       note_main (gap="small" mặc định) để 2 khoảng cách dọc không bị ép về cùng 1 giá trị: nhãn↔
       nội dung cần sát (xsmall), nhưng nội dung↔hàng nút bên dưới cần rộng hơn 1 chút để không
       dính liền -- gộp chung 1 container/1 gap từng làm cả 2 khoảng cách xích lại y hệt, "sửa
       xong" hoá ra ép nhầm khoảng còn lại quá chật (bug vòng trước). */
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    f"<div style='margin:0 0 0.6em 0;'>{_wordmark_html('header')}</div>",
    unsafe_allow_html=True,
)

# Thanh điều hướng 1 hàng phẳng (kiểu iOS segmented control), icon Material cho từng trang.
# Key = định danh trang (dùng cho dispatch & deep-link ?nav=); nhãn hiển thị rút gọn ở NAV_SHORT.
NAV = {
    "Hôm nay": ":material/today:",
    "Báo cáo": ":material/summarize:",
    "Nhật ký đọc sách": ":material/menu_book:",
    "Gundam": ":material/shield:",
    "Tìm kiếm": ":material/search:",
    "Tuỳ biến": ":material/settings:",
    "Hướng dẫn": ":material/help:",
}
# Nhãn ngắn để các tab vừa 1 hàng (key trang giữ nguyên).
NAV_SHORT = {
    "Hôm nay": "Hôm nay",
    "Báo cáo": "Báo cáo",
    "Nhật ký đọc sách": "Sách",
    "Gundam": "Gundam",
    "Tìm kiếm": "Tìm kiếm",
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

def _reset_today_on_nav_click():
    # Bấm lại mục "Hôm nay" (từ trang khác, hoặc bấm lại chính nó khi đang ở đó -- segmented_control
    # bỏ chọn khi bấm lại pill đang active, giá trị về None, rơi vào nhánh "if not nav" bên dưới
    # nên cũng coi là "Hôm nay") phải luôn đưa về đúng NGÀY HÔM NAY, không giữ ngày đã xem trước
    # đó -- thay cho nút "Ngày gần nhất" đã bỏ trong day_picker(). Chỉ set khi có "day_pick" sẵn
    # (đã từng vào trang Hôm nay) -- nếu chưa, day_picker() sẽ tự khởi tạo đúng hôm nay lúc đó.
    if st.session_state.get("nav") in (None, "Hôm nay") and "day_pick" in st.session_state:
        st.session_state["day_pick"] = _today_vn()

nav = st.segmented_control(
    "Trang", list(NAV.keys()),
    format_func=lambda x: f"{NAV[x]} {NAV_SHORT[x]}",
    key="nav", label_visibility="collapsed",
    on_change=_reset_today_on_nav_click,
)
if not nav:
    nav = "Hôm nay"
# Đồng bộ trang hiện tại lên URL (idempotent -> không gây rerun lặp)
st.query_params["nav"] = nav


def _inject_keyboard_shortcuts():
    """Phím tắt toàn app. Bỏ qua khi đang gõ trong input/textarea (kể cả date picker) hoặc đang
    giữ Ctrl/Cmd/Alt (không đụng shortcut hệ thống/trình duyệt). Không cần lo phím tắt bị bắt
    nhầm khi đang gõ trong ô soạn Quill -- Quill nằm trong 1 iframe RIÊNG (component
    streamlit_quill), keydown ở đó không nổi bọt lên tới document của trang chính nơi listener
    này được gắn (xem _inject_note_editor_shortcuts() cho phím tắt RIÊNG của ô soạn).

    Toàn cục (từ bất kỳ trang nào):
    - 1-7: nhảy tới từng mục nav (đúng thứ tự NAV).
    - Shift+1..5: nhảy tới Báo cáo, chọn đúng 1 trong 5 lát cắt (Tổng quan/Tuần/Tháng/Năm/Dự án).
      Riêng Shift+5 (Dự án) focus sẵn vào ô chọn Nhóm/Dự án -- bấm ↑↓ + Enter để chọn ngay, giống
      hệt cơ chế của ô chọn sách/series ở sub-tab Chi tiết (Sách/Gundam).
    - n: mở nhanh ô soạn Ghi chú ngày của HÔM NAY, tự cuộn trang tới đúng ô soạn (Quill) sau khi
      mở -- ô này thường không nằm ở đầu trang nên cần cuộn hộ, tránh cảm giác "bấm xong không
      thấy gì" khi vẫn đứng ở đầu trang. Cuộn xong tự focus luôn vào ô soạn (Quill nằm trong
      iframe riêng, phải đọc contentDocument của đúng iframe đó rồi .focus() thẳng vào
      .ql-editor) để gõ được ngay phím tiếp theo, không cần bấm chuột vào ô trước.
    - /: focus vào ô Tìm kiếm (đứng sẵn ở đó thì focus luôn, đứng trang khác thì nhảy tới trước).
      Esc trong khi đang focus ô này: bỏ con trỏ ra khỏi ô (blur), KHÔNG đổi/xoá từ khoá đang gõ
      -- đây là ngoại lệ duy nhất được xử lý TRƯỚC bộ lọc input/textarea bên dưới, vì mọi phím
      tắt khác cố tình bị bỏ qua khi đang gõ trong ô nhập liệu.
    - f / r / l: nhảy tới Tuỳ biến → mục 1 → đúng tab (Forest/Reminder/Đồng bộ lịch); f và r bấm
      luôn nút "Browse files" để mở hộp thoại chọn file, l chỉ dừng ở tab (còn phải tự chọn
      khoảng ngày trước khi bấm Đồng bộ). Sau khi chọn xong file (hộp thoại OS, ngoài tầm với
      của JS) và Streamlit render xong bảng xem trước, f/r tự FOCUS SẴN vào nút "Xác nhận" tương
      ứng (không tự bấm hộ) -- chỉ cần Enter là xác nhận luôn, không cần rê chuột tìm nút. Dùng
      MutationObserver (không phải poll hẹn giờ) vì thời gian người dùng chọn file trong hộp
      thoại OS không xác định trước được, có thể vài giây tới vài phút.
    - ?: hiện/ẩn bảng tóm tắt các phím tắt này.

    Theo ngữ cảnh (chỉ có tác dụng khi đang ở đúng trang, không nhảy trang):
    - [ / ]: trang Sách/Gundam -- chuyển giữa sub-tab Tổng quan / Chi tiết. Sang Chi tiết (])
      thì focus sẵn vào ô chọn sách/series -- bấm ↑↓ để duyệt rồi Enter để xem ngay, không cần
      bấm chuột mở dropdown trước.
    - ← / →: trang Hôm nay -- lùi/tiến ngày (bấm hộ nút ◀ ▶ đã có sẵn).

    QUAN TRỌNG -- không dùng window.parent.location để điều hướng: iframe của components.html
    chỉ có sandbox "allow-scripts allow-same-origin ..." (đã xác nhận trực tiếp qua source
    IFrameUtil.*.js của gói streamlit đang cài), KHÔNG có "allow-top-navigation" -- gán
    location.search từ trong iframe này bị trình duyệt chặn thẳng (SecurityError), bất kể có
    phải do phím thật người dùng bấm hay không. Thay vào đó tự bấm (.click()) đúng nút nav/nút
    đã có sẵn trong trang chính -- thao tác trong cùng 1 document (không phải điều hướng
    liên-frame) nên không bị sandbox chặn, và tận dụng lại đúng cơ chế reset-về-hôm-nay đã có
    sẵn ở on_change của nav "Hôm nay" (_reset_today_on_nav_click) thay vì tự làm lại. Mỗi bước
    bấm xong cần CHỜ Streamlit rerun (bất đồng bộ) rồi mới bấm được bước kế tiếp -- runChain()
    nối nhiều bước qua setInterval polling thay vì delay cố định vì thời gian rerun không cố định.

    clickNavByLabel() PHẢI tự kiểm tra "đã đứng sẵn ở đúng trang chưa" trước khi bấm -- bấm lại
    đúng pill đang active sẽ làm segmented_control BỎ CHỌN nó (rơi về "Hôm nay", xem
    _reset_today_on_nav_click) thay vì giữ nguyên trang, sai hoàn toàn ý đồ của các phím tắt
    f/r/l/Shift+số khi người dùng gọi chúng lúc đã đứng sẵn ở trang đích.

    components.html() tạo 1 iframe MỚI mỗi lần rerun, nhưng listener gắn vào
    window.parent.document (document của trang chính, không phải của iframe) nên vẫn tồn tại
    xuyên suốt qua các iframe cũ bị Streamlit xoá đi -- phải tự canh cờ
    window.parent.__appShortcutsInstalled để không gắn trùng listener sau mỗi lần rerun."""
    nav_short_json = json.dumps(list(NAV_SHORT.values()))
    baocao_subs_json = json.dumps(BAOCAO_SUBS)
    _txt = "#f2f2f7" if IS_DARK else "#1d1d1f"
    _txt2 = "#98989d" if IS_DARK else "#6e6e73"
    _bg = "#2c2c2e" if IS_DARK else "#ffffff"
    _border = "#3a3a3c" if IS_DARK else "#d1d1d6"
    js = (
        "<script>\n"
        "(function(){\n"
        "  const w = window.parent;\n"
        "  if (w.__appShortcutsInstalled) return;\n"
        "  w.__appShortcutsInstalled = true;\n"
        "  const NAV_LABELS = " + nav_short_json + ";\n"
        "  const BAOCAO_SUBS = " + baocao_subs_json + ";\n"
        "  function lastLine(el){\n"
        "    const parts = el.innerText.split('\\n').map(function(s){ return s.trim(); }).filter(Boolean);\n"
        "    return parts[parts.length - 1];\n"
        "  }\n"
        "  function activeNavLabel(){\n"
        "    const b = w.document.querySelector('[data-testid=\"stBaseButton-segmented_controlActive\"]');\n"
        "    return b ? lastLine(b) : null;\n"
        "  }\n"
        "  function clickNavByLabel(label){\n"
        "    if (activeNavLabel() === label) return true;\n"
        "    const btns = w.document.querySelectorAll('[data-testid^=\"stBaseButton-segmented_control\"]');\n"
        "    for (const b of btns) { if (lastLine(b) === label) { b.click(); return true; } }\n"
        "    return false;\n"
        "  }\n"
        "  function clickButtonWithText(texts){\n"
        "    const btns = w.document.querySelectorAll('button');\n"
        "    for (const b of btns) { if (texts.indexOf(lastLine(b)) !== -1) { b.click(); return true; } }\n"
        "    return false;\n"
        "  }\n"
        "  function clickWithinKey(key){\n"
        "    const scope = w.document.querySelector('.st-key-' + key);\n"
        "    if (!scope) return false;\n"
        "    const btn = scope.querySelector('button');\n"
        "    if (!btn) return false;\n"
        "    btn.click();\n"
        "    return true;\n"
        "  }\n"
        "  function clickTabByLabel(scopeSel, label){\n"
        "    // st.tabs() với icon inline (vd \":material/x: Chi tiết\") render icon+chữ CÙNG 1\n"
        "    // dòng (khác st.button icon= tách dòng riêng) -- so khớp bằng endsWith thay vì ===.\n"
        "    const scope = scopeSel ? w.document.querySelector(scopeSel) : w.document;\n"
        "    if (!scope) return false;\n"
        "    const tabs = scope.querySelectorAll('button[data-baseweb=\"tab\"]');\n"
        "    for (const t of tabs) { if (t.innerText.trim().endsWith(label)) { t.click(); return true; } }\n"
        "    return false;\n"
        "  }\n"
        "  function clickSegmentedWithinKey(key, label){\n"
        "    const scope = w.document.querySelector('.st-key-' + key);\n"
        "    if (!scope) return false;\n"
        "    const activeBtn = scope.querySelector('[data-testid=\"stBaseButton-segmented_controlActive\"]');\n"
        "    if (activeBtn && lastLine(activeBtn) === label) return true;\n"
        "    const btns = scope.querySelectorAll('button');\n"
        "    for (const b of btns) { if (lastLine(b) === label) { b.click(); return true; } }\n"
        "    return false;\n"
        "  }\n"
        "  function openExpanderByHeader(text){\n"
        "    const summaries = w.document.querySelectorAll('[data-testid=\"stExpander\"] summary');\n"
        "    for (const s of summaries) {\n"
        "      if (s.innerText.trim().indexOf(text) !== -1) {\n"
        "        const details = s.closest('details');\n"
        "        if (details && !details.hasAttribute('open')) s.click();\n"
        "        return true;\n"
        "      }\n"
        "    }\n"
        "    return false;\n"
        "  }\n"
        "  function runChain(steps, triesPerStep){\n"
        "    let i = 0;\n"
        "    function attempt(triesLeft){\n"
        "      if (i >= steps.length) return;\n"
        "      if (steps[i]()) {\n"
        "        i++;\n"
        "        if (i < steps.length) setTimeout(function(){ attempt(triesPerStep); }, 150);\n"
        "        return;\n"
        "      }\n"
        "      if (triesLeft <= 0) return;\n"
        "      setTimeout(function(){ attempt(triesLeft - 1); }, 150);\n"
        "    }\n"
        "    attempt(triesPerStep);\n"
        "  }\n"
        "  function watchAndFocusButton(labelText, timeoutMs){\n"
        "    // Đợi 1 nút xuất hiện trong DOM rồi FOCUS (không tự bấm) -- dùng cho nút Xác nhận\n"
        "    // chỉ hiện SAU khi Streamlit render xong bảng xem trước file vừa chọn. Không thể\n"
        "    // biết trước người dùng chọn file trong hộp thoại OS mất bao lâu (vài giây tới vài\n"
        "    // phút) nên dùng MutationObserver (chờ sự kiện DOM thay đổi) thay vì setInterval\n"
        "    // đếm giờ liên tục -- rẻ hơn nhiều, không tốn CPU khi không có gì thay đổi.\n"
        "    function findBtn(){\n"
        "      const btns = w.document.querySelectorAll('button');\n"
        "      for (const b of btns) { if (lastLine(b) === labelText) return b; }\n"
        "      return null;\n"
        "    }\n"
        "    const already = findBtn();\n"
        "    if (already) { already.focus(); return; }\n"
        "    const obs = new w.MutationObserver(function(){\n"
        "      const btn = findBtn();\n"
        "      if (btn) { btn.focus(); obs.disconnect(); }\n"
        "    });\n"
        "    obs.observe(w.document.body, {childList: true, subtree: true});\n"
        "    w.setTimeout(function(){ obs.disconnect(); }, timeoutMs || 600000);\n"
        "  }\n"
        "  function goUploadTab(tabLabel, browseKey, confirmLabel){\n"
        "    const steps = [\n"
        "      function(){ return clickNavByLabel('Tuỳ biến'); },\n"
        "      function(){ return openExpanderByHeader('Dữ liệu đầu vào'); },\n"
        "      function(){ return openExpanderByHeader('Dự phòng'); },\n"
        "      function(){ return clickTabByLabel(null, tabLabel); },\n"
        "    ];\n"
        "    if (browseKey) steps.push(function(){ return clickWithinKey(browseKey); });\n"
        "    if (confirmLabel) watchAndFocusButton(confirmLabel);\n"
        "    runChain(steps, 30);\n"
        "  }\n"
        "  const HELP_ROWS = [\n"
        "    ['1 – 7', 'Nhảy nhanh tới từng mục nav'],\n"
        "    ['Shift + 1..5', 'Báo cáo: Tổng quan/Tuần/Tháng/Năm/Dự án (5 focus sẵn ô chọn)'],\n"
        "    ['N', 'Mở nhanh Ghi chú ngày hôm nay, cuộn tới và focus sẵn để gõ ngay'],\n"
        "    ['/', 'Focus vào ô Tìm kiếm — Esc để bỏ con trỏ ra khỏi ô'],\n"
        "    ['F', 'Tuỳ biến → Tải lên từ Forest (chọn file xong Enter là xác nhận)'],\n"
        "    ['R', 'Tuỳ biến → Tải lên từ Reminder (chọn file xong Enter là xác nhận)'],\n"
        "    ['L', 'Tuỳ biến → Đồng bộ lịch'],\n"
        "    ['[ / ]', 'Trang Sách/Gundam: Tổng quan / Chi tiết (] focus sẵn ô chọn)'],\n"
        "    ['\\u2190 / \\u2192', 'Trang Hôm nay: ngày trước / sau'],\n"
        "    ['Ctrl/Cmd + Enter', 'Đang soạn ghi chú: Cập nhật'],\n"
        "    ['Esc', 'Đang soạn ghi chú: Huỷ'],\n"
        "    ['?', 'Hiện/ẩn bảng này'],\n"
        "  ];\n"
        "  function buildHelpOverlay(){\n"
        "    const rows = HELP_ROWS.map(function(r){\n"
        "      return \"<div style='display:flex;gap:14px;padding:6px 0;'>\"\n"
        "        + \"<div style='min-width:130px;font-weight:600;color:" + _txt + ";font-family:ui-monospace,monospace;font-size:13px;'>\" + r[0] + \"</div>\"\n"
        "        + \"<div style='color:" + _txt2 + ";font-size:13px;'>\" + r[1] + \"</div></div>\";\n"
        "    }).join('');\n"
        "    const wrap = w.document.createElement('div');\n"
        "    wrap.id = 'app-shortcuts-overlay';\n"
        "    wrap.style.cssText = 'display:none;position:fixed;top:16px;right:16px;z-index:99999;'\n"
        "      + 'background:" + _bg + ";border:1px solid " + _border + ";border-radius:12px;'\n"
        "      + 'box-shadow:0 8px 30px rgba(0,0,0,0.2);padding:16px 20px;max-width:360px;';\n"
        "    wrap.innerHTML = \"<div style='font-weight:700;color:\" + '" + _txt + "' + \";margin-bottom:6px;font-size:14px;'>Phím tắt bàn phím</div>\" + rows;\n"
        "    w.document.body.appendChild(wrap);\n"
        "    return wrap;\n"
        "  }\n"
        "  function toggleHelpOverlay(){\n"
        "    let el = w.document.getElementById('app-shortcuts-overlay');\n"
        "    if (!el) el = buildHelpOverlay();\n"
        "    el.style.display = (el.style.display === 'none') ? 'block' : 'none';\n"
        "  }\n"
        "  function pollUntil(fn, maxTries){\n"
        "    let tries = 0;\n"
        "    const iv = setInterval(function(){\n"
        "      tries++;\n"
        "      if (fn() || tries >= maxTries) clearInterval(iv);\n"
        "    }, 150);\n"
        "  }\n"
        "  w.document.addEventListener('keydown', function(e){\n"
        "    const t = e.target;\n"
        "    const tag = (t.tagName || '').toLowerCase();\n"
        "    if (e.key === 'Escape' && t.matches && t.matches('.st-key-search_q input')) {\n"
        "      e.preventDefault(); t.blur(); return;\n"
        "    }\n"
        "    if (tag === 'input' || tag === 'textarea' || t.isContentEditable) return;\n"
        "    if (e.ctrlKey || e.metaKey || e.altKey) return;\n"
        "    const key = e.key;\n"
        "    if (e.shiftKey && e.code && e.code.indexOf('Digit') === 0) {\n"
        "      const sidx = parseInt(e.code.slice(5), 10) - 1;\n"
        "      if (BAOCAO_SUBS[sidx]) {\n"
        "        e.preventDefault();\n"
        "        runChain([\n"
        "          function(){ return clickNavByLabel('Báo cáo'); },\n"
        "          function(){ return clickSegmentedWithinKey('bc_sub_picker', BAOCAO_SUBS[sidx]); },\n"
        "          function(){\n"
        "            // Sang \"Dự án\" thì focus sẵn ô chọn Nhóm/Dự án, giống hệt ô chọn sách/series\n"
        "            // ở sub-tab Chi tiết (Sách/Gundam) -- bấm ↑/↓ + Enter chọn ngay không cần chuột.\n"
        "            if (BAOCAO_SUBS[sidx] !== 'Dự án') return true;\n"
        "            const inp = w.document.querySelector('.st-key-grp_select input[role=\"combobox\"]');\n"
        "            if (inp) { inp.focus(); return true; }\n"
        "            return false;\n"
        "          },\n"
        "        ], 30);\n"
        "      }\n"
        "      return;\n"
        "    }\n"
        "    const idx = parseInt(key, 10) - 1;\n"
        "    if (!isNaN(idx) && NAV_LABELS[idx]) {\n"
        "      e.preventDefault(); clickNavByLabel(NAV_LABELS[idx]); return;\n"
        "    }\n"
        "    if (key === 'n') {\n"
        "      e.preventDefault();\n"
        "      clickNavByLabel('Hôm nay');\n"
        "      runChain([\n"
        "        function(){\n"
        "          const card = w.document.querySelector('.st-key-note_card');\n"
        "          if (card && card.querySelector('iframe')) return true;\n"
        "          return clickButtonWithText(['Thêm ghi chú', 'Sửa ghi chú']);\n"
        "        },\n"
        "        function(){\n"
        "          const card = w.document.querySelector('.st-key-note_card');\n"
        "          if (card && card.querySelector('iframe')) {\n"
        "            card.scrollIntoView({behavior: 'smooth', block: 'center'});\n"
        "            return true;\n"
        "          }\n"
        "          return false;\n"
        "        },\n"
        "        function(){\n"
        "          // Focus thẳng vào ô soạn Quill (iframe riêng) để gõ được ngay, không cần bấm\n"
        "          // chuột -- contentDocument đọc được vì cùng-origin (allow-same-origin), chỉ cần\n"
        "          // đợi Quill mount xong .ql-editor (mới tạo lại sau rerun nên có thể trễ vài nhịp).\n"
        "          // focus() mặc định đặt con trỏ ở ĐẦU nội dung sẵn có -- dùng Selection/Range của\n"
        "          // CHÍNH iframe đó (không phải window chính) để dời con trỏ về CUỐI, viết tiếp được.\n"
        "          const card = w.document.querySelector('.st-key-note_card');\n"
        "          const ifr = card ? card.querySelector('iframe') : null;\n"
        "          if (!ifr) return false;\n"
        "          let d; try { d = ifr.contentDocument; } catch (err) { return false; }\n"
        "          const ed = d ? d.querySelector('.ql-editor') : null;\n"
        "          if (!ed) return false;\n"
        "          ed.focus();\n"
        "          try {\n"
        "            const range = d.createRange();\n"
        "            range.selectNodeContents(ed);\n"
        "            range.collapse(false);\n"
        "            const sel = ifr.contentWindow.getSelection();\n"
        "            sel.removeAllRanges();\n"
        "            sel.addRange(range);\n"
        "          } catch (err) {}\n"
        "          return true;\n"
        "        },\n"
        "      ], 40);\n"
        "      return;\n"
        "    }\n"
        "    if (key === '/') {\n"
        "      e.preventDefault();\n"
        "      const inp = w.document.querySelector('.st-key-search_q input');\n"
        "      if (inp) { inp.focus(); return; }\n"
        "      clickNavByLabel('Tìm kiếm');\n"
        "      pollUntil(function(){\n"
        "        const inp2 = w.document.querySelector('.st-key-search_q input');\n"
        "        if (inp2) { inp2.focus(); return true; }\n"
        "        return false;\n"
        "      }, 30);\n"
        "      return;\n"
        "    }\n"
        "    if (key === 'f' || key === 'F') { e.preventDefault(); goUploadTab('Tải lên từ Forest', 'forest', 'Xác nhận cập nhật dữ liệu'); return; }\n"
        "    if (key === 'r' || key === 'R') { e.preventDefault(); goUploadTab('Tải lên từ Reminder', 'rl_shortcut_file', 'Xác nhận nạp dữ liệu'); return; }\n"
        "    if (key === 'l' || key === 'L') { e.preventDefault(); goUploadTab('Đồng bộ lịch', null); return; }\n"
        "    if (key === '[' || key === ']') {\n"
        "      const cur = activeNavLabel();\n"
        "      if (cur === 'Sách' || cur === 'Gundam') {\n"
        "        e.preventDefault();\n"
        "        clickTabByLabel('.st-key-rl_view_tabs', key === '[' ? 'Tổng quan' : 'Chi tiết');\n"
        "        if (key === ']') {\n"
        "          // Focus sẵn ô chọn sách/series -- gõ được phím lên/xuống + Enter chọn ngay,\n"
        "          // không cần bấm chuột mở dropdown trước (BaseWeb Select tự mở khi ArrowDown).\n"
        "          pollUntil(function(){\n"
        "            const inp = w.document.querySelector('.st-key-rl_detail_select input[role=\"combobox\"]');\n"
        "            if (inp) { inp.focus(); return true; }\n"
        "            return false;\n"
        "          }, 30);\n"
        "        }\n"
        "      }\n"
        "      return;\n"
        "    }\n"
        "    if (key === 'ArrowLeft' || key === 'ArrowRight') {\n"
        "      if (activeNavLabel() === 'Hôm nay') {\n"
        "        e.preventDefault();\n"
        "        clickWithinKey(key === 'ArrowLeft' ? 'day_prev' : 'day_next');\n"
        "      }\n"
        "      return;\n"
        "    }\n"
        "    if (key === '?') { e.preventDefault(); toggleHelpOverlay(); }\n"
        "  });\n"
        "})();\n"
        "</script>"
    )
    components.html(js, height=0)


def _inject_note_editor_shortcuts():
    """Ctrl/Cmd+Enter -> bấm "Cập nhật", Escape -> bấm "Huỷ", khi con trỏ đang ở trong ô soạn
    Quill. Quill chạy trong iframe RIÊNG (component streamlit_quill) nên keydown gõ trong đó
    KHÔNG nổi bọt lên window.parent.document -- không bắt được bằng listener chung của
    _inject_keyboard_shortcuts(), phải tự tìm đúng iframe (qua .ql-editor, cùng cách
    style_quill() đã làm) rồi gắn thẳng listener vào TRONG nó. Bản thân iframe chứa Quill bị
    Streamlit tạo lại mỗi khi mở/đóng ô soạn (khác iframe của _inject_keyboard_shortcuts() vốn
    gắn ổn định vào window.parent.document xuyên suốt qua các lần rerun) -- nên phải lặp lại
    việc gắn định kỳ, giống hệt cách style_quill() lặp lại applyQuillCss mỗi 400ms; đánh dấu
    qua thuộc tính tự đặt trên chính document của iframe đó để không gắn trùng nhiều listener
    lên cùng 1 iframe còn sống."""
    js = (
        "<script>\n"
        "function bindNoteShortcuts(){\n"
        "  try{\n"
        "    const frames = window.parent.document.querySelectorAll('iframe');\n"
        "    frames.forEach(function(f){\n"
        "      let d; try{ d = f.contentDocument; }catch(e){ return; }\n"
        "      if(!d || !d.querySelector('.ql-editor')) return;\n"
        "      if(d.__noteShortcutsBound) return;\n"
        "      d.__noteShortcutsBound = true;\n"
        "      function lastLine(el){\n"
        "        const parts = el.innerText.split('\\n').map(function(s){ return s.trim(); }).filter(Boolean);\n"
        "        return parts[parts.length - 1];\n"
        "      }\n"
        "      function clickByLabel(label){\n"
        "        const btns = window.parent.document.querySelectorAll('button');\n"
        "        for (const b of btns) { if (lastLine(b) === label) { b.click(); return true; } }\n"
        "        return false;\n"
        "      }\n"
        "      d.addEventListener('keydown', function(e){\n"
        "        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); clickByLabel('Cập nhật'); }\n"
        "        else if (e.key === 'Escape') { e.preventDefault(); clickByLabel('Huỷ'); }\n"
        "      });\n"
        "    });\n"
        "  }catch(e){}\n"
        "}\n"
        "bindNoteShortcuts();\n"
        "setInterval(bindNoteShortcuts, 400);\n"
        "</script>"
    )
    components.html(js, height=0)

# Sub-page của "Báo cáo" (Tổng quan/Tuần/Tháng/Năm/Dự án) -- đọc ?sub= 1 lần y hệt cách "nav" ở trên,
# cho phép link "nhảy tới ngày" từ Nhật ký dùng chung 1 cơ chế qua hàng "Chọn kỳ xem" trong trang.
BAOCAO_SUBS = ["Tổng quan", "Tuần", "Tháng", "Năm", "Dự án"]
BAOCAO_SUB_ICONS_MD = {"Tổng quan": ":material/bar_chart:", "Năm": ":material/celebration:",
                        "Tháng": ":material/calendar_month:", "Tuần": ":material/calendar_view_week:",
                        "Dự án": ":material/work:"}
if "bc_sub" not in st.session_state:
    _qs = st.query_params.get("sub")
    st.session_state["bc_sub"] = _qs if _qs in BAOCAO_SUBS else "Tổng quan"
if nav == "Báo cáo":
    st.query_params["sub"] = st.session_state["bc_sub"]
elif "sub" in st.query_params:
    del st.query_params["sub"]

# Gọi ở đây (chứ không phải ngay sau def) vì cần BAOCAO_SUBS đã được định nghĩa ở trên --
# hàm đọc biến này ngay khi chạy để build JSON cho JS.
_inject_keyboard_shortcuts()


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
    # Tính 1 lần ở đây (ngoài render_note_editor) rồi truyền list badge của đúng "sel" xuống --
    # render_note_editor chạy trong @st.fragment (rerun mỗi lần gõ ghi chú), gọi lại
    # _compute_alltime_records() trong đó sẽ băm lại cả df mỗi phím gõ, mất hết tác dụng cô lập
    # của fragment.
    sel_day_badges = _compute_alltime_records(df)["day_badges"].get(sel)

    _evt = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='14' height='14' fill='var(--text-2)' "
            "style='vertical-align:-2px;margin-right:6px;'><path d='M17 12h-5v5h5v-5zM16 1v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2"
            "L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2h-1V1h-2zm3 18H5V8h14v11z'/></svg>")
    _sub = "không có hoạt động" if day_df.empty else f"ngày hoạt động {active_days.index(sel) + 1}/{len(active_days)}"
    _dot = "<span style='color:var(--border);flex:0 0 auto;'>·</span>"
    # "Cập nhật gần nhất" (toàn thời gian, không phụ thuộc ngày đang xem) từng là 1 thẻ riêng ở
    # Báo cáo -> Tổng quan -- dời về đây làm "đuôi" của card này vì Hôm nay mới là trang mở đầu
    # tiên, Tổng quan giờ không còn là sub-tab mặc định.
    _last_dt = df['Thời gian kết thúc'].max()
    _upd_tail = ''
    if pd.notna(_last_dt):
        _last_ts = pd.Timestamp(_last_dt)
        _abs_str = _last_ts.strftime('%H:%M · %d/%m/%Y')
        # epoch UTC thật (không phải lệch theo múi giờ máy chủ/máy khách) -- localize đúng ts
        # naive (wall-clock giờ Việt Nam) vào APP_TZ rồi lấy timestamp(), dùng cho JS ticker bên
        # dưới tự cập nhật "X trước" mỗi 30s mà không cần rerun Streamlit.
        _epoch_ms = int(_last_ts.tz_localize(APP_TZ).timestamp() * 1000)
        # Giờ phút giây tuyệt đối (_abs_str) dời vào title= (tooltip hover) thay vì hiện luôn
        # trong chữ -- giữ đúng 1 dòng gọn, phần lớn chỉ cần biết "khoảng bao lâu trước", số giờ
        # chính xác là chi tiết tra cứu thêm chứ không phải thông tin ai cũng cần thấy ngay.
        # Cả cụm (dấu chấm + chữ) bọc chung 1 span "dcx-upd" flex riêng -- vừa là 1 flex item
        # DUY NHẤT của hàng ngoài (co dãn/ẩn được nguyên cụm qua class, không lệ thuộc thứ tự
        # nhiều item rời rạc), vừa tự có overflow:hidden riêng để chữ bên trong elipsis đúng chỗ.
        _upd_tail = (
            "<span class='dcx-upd' style='display:flex;align-items:center;gap:9px;min-width:0;"
            "overflow:hidden;flex:1 1 auto;'>"
            f"{_dot}"
            f"<span style='font-size:14.5px;color:var(--text-2);overflow:hidden;text-overflow:ellipsis;"
            f"white-space:nowrap;min-width:0;' title='Cập nhật lúc {_abs_str}'>Cập nhật gần nhất "
            f"<b id='last-update-live' data-epoch='{_epoch_ms}' "
            f"style='color:var(--text);font-weight:600;'>{format_relative(_last_dt)}</b></span></span>"
        )
    # 1 hàng gọn: nhãn thu lại thành thẻ nhỏ bo góc (khác kiểu chữ hoa rời trước đây) + 1 vạch
    # dọc mảnh phân tách, rồi tới nội dung cùng 1 cỡ chữ (14.5px, chỉ khác màu/độ đậm để vẫn
    # phân cấp) -- không còn đủ 3 cỡ chữ chen nhau trên 1 dòng như bản trước. Cụm "Cập nhật gần
    # nhất" (ít quan trọng nhất, dài nhất) được phép co lại + hiện "…" khi màn hẹp vừa phải
    # (flex:1 1 auto), và ẩn hẳn cùng chữ nhãn "Ngày đang xem" (chỉ còn icon) ở mobile thật hẹp
    # (xem rule .dcx-upd/.dcx-lbltxt trong khối @media (max-width: 640px)) -- nếu không, tổng độ
    # rộng các phần "không co" (nhãn đủ chữ + ngày + trạng thái) đã vượt quá màn hình điện thoại,
    # bị cắt cụt giữa chữ thay vì gọn gàng.
    st.markdown(
        "<div class='glass-card' style='padding:12px 18px;margin-bottom:16px;'>"
        "<div style='display:flex;align-items:center;gap:10px;'>"
        "<span style='display:flex;align-items:center;flex:0 0 auto;font-size:11.5px;font-weight:600;"
        "color:var(--text-2);background:var(--bg);border:1px solid var(--border);border-radius:7px;"
        "padding:4px 9px;text-transform:uppercase;letter-spacing:0.4px;white-space:nowrap;'>"
        f"{_evt}<span class='dcx-lbltxt'>Ngày đang xem</span></span>"
        "<span style='width:1px;align-self:stretch;background:var(--divider);flex:0 0 auto;'></span>"
        "<div style='display:flex;align-items:center;gap:9px;min-width:0;overflow:hidden;'>"
        f"<span style='font-size:14.5px;color:var(--text);font-weight:600;white-space:nowrap;flex:0 0 auto;'>"
        f"{vn_dow}, {sel:%d/%m/%Y}</span>"
        f"{_dot}"
        f"<span style='font-size:14.5px;color:var(--text-2);white-space:nowrap;flex:0 0 auto;'>{_sub}</span>"
        f"{_upd_tail}"
        "</div></div></div>",
        unsafe_allow_html=True)
    if _upd_tail:
        _inject_relative_time_ticker()

    if day_df.empty:
        # Tham khảo nhanh cho việc lên kế hoạch đầu ngày (vd Pomodoro Planning đầu ngày trước khi
        # có phiên nào) -- số liệu của CÁC NGÀY KHÁC (cùng thứ tuần trước / trung bình cùng thứ),
        # không phụ thuộc dữ liệu của chính ngày đang xem nên hiện được ngay cả khi ngày này
        # (kể cả hôm nay, chưa trồng cây nào) trống trơn. Không kèm delta so với ngày đang xem
        # (khác nhánh có phiên bên dưới) vì ngày chưa diễn ra thì "0h so với TB 3h" chỉ gây hiểu
        # lầm là đang tụt lại, không phải thông tin tham khảo hữu ích.
        pw = df[df['Ngày'] == (sel - timedelta(days=7))]
        same = df[(pd.to_datetime(df['Ngày']).dt.day_name() == pd.Timestamp(sel).day_name())
                  & (df['Ngày'] != sel)]
        ref_chips = []
        if not pw.empty:
            ref_chips.append({"k": f"{vn_dow} tuần trước",
                               "v": f"{pw['Thời lượng (Phút)'].sum() / 60:.1f}h · {len(pw)} phiên"})
        if same['Ngày'].nunique():
            avg_h = (same.groupby('Ngày')['Thời lượng (Phút)'].sum() / 60).mean()
            ref_chips.append({"k": f"TB các {vn_dow}", "v": f"{avg_h:.1f}h"})
        if ref_chips:
            # margin ngang 16px khớp đúng padding trong của st.expander (16px mỗi bên) để card này
            # rộng bằng đúng note_card bên dưới (vốn co hẹp lại vì nằm trong expander); margin-bottom
            # 20px (thay vì mặc định 0) tạo khoảng cách rõ ràng hơn trước khi vào "Ghi chú ngày".
            render_stat_panel(hero_items=[], sections=[{"label": "Tham khảo cho lên kế hoạch", "chips": ref_chips}],
                               card_style="padding:20px; margin:0 16px 20px;")

        with st.expander("Ghi chú ngày", expanded=True):
            render_note_editor(sel, sel_day_badges)
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
            render_note_editor(sel, sel_day_badges)

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
                # Thẻ "Cập nhật gần nhất" đã dời sang trang Hôm nay (đuôi của card "Ngày đang
                # xem") -- Hôm nay giờ mới là trang mở đầu tiên, không còn hợp lý để card này
                # đứng đầu Tổng quan (sub-tab không mặc định) nữa.
                total_hrs = df['Thời lượng (Phút)'].sum() / 60
                total_trees = len(df)
                num_days = df['Ngày'].nunique() or 1
                base_avg = total_hrs / num_days

                # Phong độ 7 ngày gần đây so với mức trung bình của chính mình
                recent7 = df[df['Ngày'] >= (_today_vn() - timedelta(days=6))]
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
                overall_top3 = _top_days(df, 3)
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
                if overall_top3:
                    _sections.append({"label": "Ngày nổi bật", "chips": _top_days_chips(overall_top3)})
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
                _wk_now = _today_vn().strftime('%G-W%V')
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

    elif bc_sub == "Tuần":
        if not df.empty:
            weeks = sorted(df['Tuần'].unique())
            selected_week = period_stepper(weeks, key="week", fmt=fmt_week, current=_today_vn().strftime('%G-W%V'))
            df_w = df[df['Tuần'] == selected_week]

            week_anchor = df_w['Thời gian bắt đầu'].min()
            prev_week_key = (week_anchor - pd.Timedelta(days=7)).strftime('%G-W%V') if pd.notna(week_anchor) else None

            # Kỳ đang xem CHƯA kết thúc (đang là tuần hiện tại) -> cắt cả 2 baseline so sánh
            # theo đúng phần đã trôi qua (vd "2 ngày đầu tuần"), cùng lý do đã áp dụng cho Tháng.
            # Nhãn delta giữ NGẮN (xem chú thích tương ứng ở nhánh Tháng).
            elapsed_mask_w, lbl_prev_w, lbl_avg_w, _clip_note_w = None, "vs Tuần trước", "vs Trung bình", None
            if selected_week == _today_vn().strftime('%G-W%V'):
                _dow = _today_vn().isoweekday()
                elapsed_mask_w = (df['Thời gian bắt đầu'].dt.dayofweek + 1) <= _dow
                _clip_note_w = f"So sánh chỉ tính {_dow} ngày đầu của Tuần trước/các tuần khác cho công bằng."
            prev_w, avg_w = _period_comparison(df, 'Tuần', selected_week, prev_week_key, elapsed_mask_w)

            if not df_w.empty:
                with st.expander("1. Tổng quan", expanded=True):
                    curr_hrs_w = df_w['Thời lượng (Phút)'].sum() / 60
                    curr_trees_w = len(df_w)
                    num_days_w = df_w['Ngày'].nunique() or 1

                    curr_hrs_day_w = curr_hrs_w / num_days_w
                    curr_trees_day_w = curr_trees_w / num_days_w
                    curr_min_sess_w = _avg_session_min(df_w)

                    def _hd_w(cur_v, key):
                        d1 = (cur_v - prev_w[key]) if prev_w and prev_w.get(key) is not None else None
                        d2 = (cur_v - avg_w[key]) if avg_w and avg_w.get(key) is not None else None
                        return d1, d2

                    d1_hr_w, d2_hr_w = _hd_w(curr_hrs_w, "hrs")
                    d1_hrd_w, d2_hrd_w = _hd_w(curr_hrs_day_w, "hrs_day")
                    d1_tr_w, d2_tr_w = _hd_w(curr_trees_w, "trees")
                    d1_trd_w, d2_trd_w = _hd_w(curr_trees_day_w, "trees_day")
                    d1_ms_w, d2_ms_w = _hd_w(curr_min_sess_w, "min_sess")

                    if _clip_note_w:
                        _clip_card(_clip_note_w)
                    _sections_w = _top_days_section(df_w, "Ngày nổi bật trong tuần")
                    render_stat_panel(hero_items=[
                        {"label": "Tổng thời gian", "value": f"{curr_hrs_w:.1f}h", "deltas": [d for d in [_delta_t(d1_hr_w, f"h {lbl_prev_w}"), _delta_t(d2_hr_w, f"h {lbl_avg_w}")] if d]},
                        {"label": "Thời gian / ngày", "value": f"{curr_hrs_day_w:.1f}h", "deltas": [d for d in [_delta_t(d1_hrd_w, f"h {lbl_prev_w}"), _delta_t(d2_hrd_w, f"h {lbl_avg_w}")] if d]},
                        {"label": "Số cây đã trồng", "value": f"{curr_trees_w}", "deltas": [d for d in [_delta_t(d1_tr_w, f"cây {lbl_prev_w}"), _delta_t(d2_tr_w, f"cây {lbl_avg_w}")] if d]},
                        {"label": "Số cây / ngày", "value": f"{curr_trees_day_w:.1f}", "deltas": [d for d in [_delta_t(d1_trd_w, f"cây {lbl_prev_w}"), _delta_t(d2_trd_w, f"cây {lbl_avg_w}")] if d]},
                        {"label": "Thời gian / phiên", "value": f"{curr_min_sess_w:.0f} phút", "deltas": [d for d in [_delta_t(d1_ms_w, f"phút {lbl_prev_w}"), _delta_t(d2_ms_w, f"phút {lbl_avg_w}")] if d]},
                    ], sections=_sections_w, footer=_smart_digest(df, 'Tuần', selected_week, df_w, prev_w, avg_w, elapsed_mask_w is not None))
                    render_session_bar(df_w)

                    st.write("")
                    c_top1, c_top2 = st.columns(2)
                    with c_top1: render_top_3(df_w, 'Danh mục', 'Top 3 Danh mục Tuần')
                    with c_top2: render_top_3(df_w, 'Dự án', 'Top 3 Dự án Tuần')
                with st.expander("2. Nhật ký", expanded=True):
                    render_notes_journal(selected_week, 'week', df)
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
    elif bc_sub == "Tháng":
        if not df.empty:
            months = sorted(df['Tháng'].unique())
            selected_month = period_stepper(months, key="month", fmt=fmt_month, current=_today_vn().strftime('%Y-%m'))
            df_m = df[df['Tháng'] == selected_month]

            y, m = map(int, selected_month.split('-'))
            prev_month_key = f"{y - 1:04d}-12" if m == 1 else f"{y:04d}-{m - 1:02d}"

            # Kỳ đang xem CHƯA kết thúc (đang là tháng hiện tại) -> cắt cả 2 baseline so sánh
            # theo đúng phần đã trôi qua (vd "3 ngày đầu"), tránh so tổng dở dang với 1 tháng
            # đầy đủ (nếu không sẽ ra kiểu "-38h vs Tháng trước" dù mới qua 3/31 ngày, vô nghĩa).
            # Nhãn delta giữ NGẮN ("vs Tháng trước"/"vs Trung bình") dù có cắt hay không -- số
            # ngày cắt chỉ nói 1 lần qua st.caption() bên dưới, tránh nhắc lại 5 lần (1 lần/hero
            # item) làm chữ dài, tự xuống dòng lem nhem trong cột hẹp.
            elapsed_mask_m, lbl_prev_m, lbl_avg_m, _clip_note_m = None, "vs Tháng trước", "vs Trung bình", None
            if selected_month == _today_vn().strftime('%Y-%m'):
                _d = _today_vn().day
                elapsed_mask_m = df['Thời gian bắt đầu'].dt.day <= _d
                _clip_note_m = f"So sánh chỉ tính {_d} ngày đầu của Tháng trước/các tháng khác cho công bằng."
            prev_m, avg_m = _period_comparison(df, 'Tháng', selected_month, prev_month_key, elapsed_mask_m)

            if not df_m.empty:
                with st.expander("1. Tổng quan", expanded=True):
                    curr_hrs = df_m['Thời lượng (Phút)'].sum() / 60
                    curr_trees = len(df_m)
                    num_days_m = df_m['Ngày'].nunique() or 1

                    curr_hrs_day = curr_hrs / num_days_m
                    curr_trees_day = curr_trees / num_days_m
                    curr_min_sess = _avg_session_min(df_m)

                    def _hd_m(cur_v, key):
                        d1 = (cur_v - prev_m[key]) if prev_m and prev_m.get(key) is not None else None
                        d2 = (cur_v - avg_m[key]) if avg_m and avg_m.get(key) is not None else None
                        return d1, d2

                    delta1_hr, delta2_hr = _hd_m(curr_hrs, "hrs")
                    delta1_hrd, delta2_hrd = _hd_m(curr_hrs_day, "hrs_day")
                    delta1_tr, delta2_tr = _hd_m(curr_trees, "trees")
                    delta1_trd, delta2_trd = _hd_m(curr_trees_day, "trees_day")
                    delta1_ms, delta2_ms = _hd_m(curr_min_sess, "min_sess")

                    if _clip_note_m:
                        _clip_card(_clip_note_m)
                    _sections_m = _top_days_section(df_m, "Ngày nổi bật trong tháng")
                    render_stat_panel(hero_items=[
                        {"label": "Tổng thời gian", "value": f"{curr_hrs:.1f}h", "deltas": [d for d in [_delta_t(delta1_hr, f"h {lbl_prev_m}"), _delta_t(delta2_hr, f"h {lbl_avg_m}")] if d]},
                        {"label": "Thời gian / ngày", "value": f"{curr_hrs_day:.1f}h", "deltas": [d for d in [_delta_t(delta1_hrd, f"h {lbl_prev_m}"), _delta_t(delta2_hrd, f"h {lbl_avg_m}")] if d]},
                        {"label": "Số cây đã trồng", "value": f"{curr_trees}", "deltas": [d for d in [_delta_t(delta1_tr, f"cây {lbl_prev_m}"), _delta_t(delta2_tr, f"cây {lbl_avg_m}")] if d]},
                        {"label": "Số cây / ngày", "value": f"{curr_trees_day:.1f}", "deltas": [d for d in [_delta_t(delta1_trd, f"cây {lbl_prev_m}"), _delta_t(delta2_trd, f"cây {lbl_avg_m}")] if d]},
                        {"label": "Thời gian / phiên", "value": f"{curr_min_sess:.0f} phút", "deltas": [d for d in [_delta_t(delta1_ms, f"phút {lbl_prev_m}"), _delta_t(delta2_ms, f"phút {lbl_avg_m}")] if d]},
                    ], sections=_sections_m, footer=_smart_digest(df, 'Tháng', selected_month, df_m, prev_m, avg_m, elapsed_mask_m is not None))
                    render_session_bar(df_m)

                    st.write("")
                    c_top1, c_top2 = st.columns(2)
                    with c_top1: render_top_3(df_m, 'Danh mục', 'Top 3 Danh mục Tháng')
                    with c_top2: render_top_3(df_m, 'Dự án', 'Top 3 Dự án Tháng')
                with st.expander("2. Nhật ký", expanded=True):
                    render_notes_journal(selected_month, 'month', df)
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
    elif bc_sub == "Năm":
        if not df.empty:
            years = sorted(df['Năm'].unique())
            selected_year = period_stepper(years, key="year", fmt=lambda y: f"Năm {y}", current=str(_today_vn().year))
            df_y = df[df['Năm'] == selected_year]
            prev_year_key = str(int(selected_year) - 1)

            # Kỳ đang xem CHƯA kết thúc (đang là năm hiện tại) -> cắt cả 2 baseline so sánh
            # theo đúng phần đã trôi qua, cùng lý do đã áp dụng cho Tháng/Tuần. Nhãn delta giữ
            # NGẮN (xem chú thích tương ứng ở nhánh Tháng).
            elapsed_mask_y, lbl_prev_y, lbl_avg_y, _clip_note_y = None, "vs Năm trước", "vs Trung bình", None
            if selected_year == str(_today_vn().year):
                _doy = _today_vn().timetuple().tm_yday
                elapsed_mask_y = df['Thời gian bắt đầu'].dt.dayofyear <= _doy
                _clip_note_y = f"So sánh chỉ tính {_doy} ngày đầu của Năm trước/các năm khác cho công bằng."
            prev_y, avg_y = _period_comparison(df, 'Năm', selected_year, prev_year_key, elapsed_mask_y)

            if not df_y.empty:
                with st.expander("1. Tổng quan", expanded=True):
                    curr_hrs_y = df_y['Thời lượng (Phút)'].sum() / 60
                    curr_trees_y = len(df_y)
                    num_days_y = df_y['Ngày'].nunique() or 1
                    curr_hrs_day_y = curr_hrs_y / num_days_y
                    curr_trees_day_y = curr_trees_y / num_days_y
                    curr_min_sess_y = _avg_session_min(df_y)

                    def _hd_y(cur_v, key):
                        d1 = (cur_v - prev_y[key]) if prev_y and prev_y.get(key) is not None else None
                        d2 = (cur_v - avg_y[key]) if avg_y and avg_y.get(key) is not None else None
                        return d1, d2

                    d1_hr_y, d2_hr_y = _hd_y(curr_hrs_y, "hrs")
                    d1_hrd_y, d2_hrd_y = _hd_y(curr_hrs_day_y, "hrs_day")
                    d1_tr_y, d2_tr_y = _hd_y(curr_trees_y, "trees")
                    d1_trd_y, d2_trd_y = _hd_y(curr_trees_day_y, "trees_day")
                    d1_ms_y, d2_ms_y = _hd_y(curr_min_sess_y, "min_sess")

                    if _clip_note_y:
                        _clip_card(_clip_note_y)
                    _sections_y = _top_days_section(df_y, "Ngày nổi bật trong năm")
                    render_stat_panel(hero_items=[
                        {"label": "Tổng thời gian", "value": f"{curr_hrs_y:.1f}h", "deltas": [d for d in [_delta_t(d1_hr_y, f"h {lbl_prev_y}"), _delta_t(d2_hr_y, f"h {lbl_avg_y}")] if d]},
                        {"label": "Thời gian / ngày", "value": f"{curr_hrs_day_y:.1f}h", "deltas": [d for d in [_delta_t(d1_hrd_y, f"h {lbl_prev_y}"), _delta_t(d2_hrd_y, f"h {lbl_avg_y}")] if d]},
                        {"label": "Số cây đã trồng", "value": f"{curr_trees_y}", "deltas": [d for d in [_delta_t(d1_tr_y, f"cây {lbl_prev_y}"), _delta_t(d2_tr_y, f"cây {lbl_avg_y}")] if d]},
                        {"label": "Số cây / ngày", "value": f"{curr_trees_day_y:.1f}", "deltas": [d for d in [_delta_t(d1_trd_y, f"cây {lbl_prev_y}"), _delta_t(d2_trd_y, f"cây {lbl_avg_y}")] if d]},
                        {"label": "Thời gian / phiên", "value": f"{curr_min_sess_y:.0f} phút", "deltas": [d for d in [_delta_t(d1_ms_y, f"phút {lbl_prev_y}"), _delta_t(d2_ms_y, f"phút {lbl_avg_y}")] if d]},
                    ], sections=_sections_y, footer=_smart_digest(df, 'Năm', selected_year, df_y, prev_y, avg_y, elapsed_mask_y is not None))
                    render_session_bar(df_y)

                    st.write("")
                    c_top1_y, c_top2_y = st.columns(2)
                    with c_top1_y: render_top_3(df_y, 'Danh mục', 'Top 3 Danh mục Năm')
                    with c_top2_y: render_top_3(df_y, 'Dự án', 'Top 3 Dự án Năm')

                with st.expander("2. Biểu đồ lịch", expanded=False):
                    # Truyền CÙNG df_y cho cả 2 tham số (không frag_calendar/range_radio) -- đúng
                    # pattern duy nhất đã có trong app (render_calendar_grid(df_cal, df_cal),
                    # app.py frag_calendar) để lưới tự bó gọn theo đúng phạm vi năm đang chọn,
                    # không tự kéo dài tới ngày hiện tại như khi truyền full df làm full_df.
                    render_calendar_grid(df_y, df_y)

                with st.expander("3. Đọc sách & Gundam trong năm", expanded=False):
                    # Chỉ đếm đơn giản (số phần đã đọc, số cuốn/series có hoạt động) -- KHÔNG lặp
                    # lại logic phân loại "Đã xong/Đang đọc" sống trong render_reading_log(), quá
                    # phức tạp để tách ra cho 1 mục tổng kết năm.
                    rl_y = load_reading_log()
                    rl_y = rl_y[rl_y['Ngày hoàn thành'].dt.year == int(selected_year)] if not rl_y.empty else rl_y
                    if rl_y.empty:
                        st.caption("Chưa có phần sách/Gundam nào hoàn thành trong năm này.")
                    else:
                        render_stat_panel(hero_items=[
                            {"label": "Số phần đã đọc", "value": f"{len(rl_y)}"},
                            {"label": "Số cuốn/series có hoạt động", "value": f"{rl_y['Cuốn sách'].nunique()}"},
                        ])

                with st.expander("4. Bảng số liệu", expanded=False):
                    render_detail_table(df_y)
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

            with st.container(key="grp_select"):
                sel = st.selectbox("Chọn Nhóm hoặc Dự án:", _opts, format_func=lambda o: _labels[o],
                                    key="grp_sel", label_visibility="collapsed")
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

                    df_g_thisweek = df_g[df_g['Tuần'] == _today_vn().strftime('%G-W%V')]
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

                    records_g = _compute_alltime_records(df)
                    _rec_g = (records_g["category_records"] if _kind == "cat" else records_g["project_records"]).get(sel_grp)
                    if _rec_g:
                        # Gộp ngày + giờ vào 1 chip "#1 {ngày} · {giờ}h" -- đúng khuôn
                        # _top_days_chips() dùng ở Bảng số liệu Tuần/Tháng/Năm, thay vì 2 chip
                        # "Ngày"/"Giờ" cạnh nhau như trước (trông tách rời, khác kiểu với nơi
                        # khác). Đồng hạng (hiếm) vẫn ra nhiều chip, mỗi ngày 1 chip riêng.
                        _grp_sections.append({"label": "Ngày nổi bật", "chips": [
                            {"k": "#1", "v": f"{d:%d/%m/%Y} · {_rec_g['hours']:.1f}h"} for d in _rec_g['dates']
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
elif nav == "Tìm kiếm":
    render_search()
# ==========================================
# TAB TUỲ BIẾN
# ==========================================
elif nav == "Tuỳ biến":
    with st.expander("1. Dữ liệu đầu vào", expanded=True):
        _qmsg = st.session_state.pop('quick_sync_msg', None)
        if _qmsg:
            (st.success if not st.session_state.pop('quick_sync_has_error', False) else st.warning)(_qmsg)
        _qfiles = _list_sync_files()
        _qf = _latest_sync_file(_qfiles, "forest")
        _qr = _latest_sync_file(_qfiles, "reminder")
        qc1, qc2 = st.columns(2)
        with qc1:
            st.markdown(f"**File Forest mới nhất**  \n{_qf['name'] if _qf else '_— chưa có —_'}")
        with qc2:
            st.markdown(f"**File Reminder mới nhất**  \n{_qr['name'] if _qr else '_— chưa có —_'}")
        if st.button("Đồng bộ ngay", type="primary", key="quick_sync_btn", disabled=not (_qf or _qr)):
            with st.spinner("Đang đồng bộ..."):
                _qres = sync_from_storage(_today_vn() - timedelta(days=90), _today_vn() + timedelta(days=90))
            if _qres["error"]:
                st.session_state['quick_sync_msg'] = _qres["error"]
                st.session_state['quick_sync_has_error'] = True
            else:
                _parts, _has_err = [], False
                if _qres["forest_error"]:
                    _parts.append(f"Forest lỗi ({_qres['forest_error']})"); _has_err = True
                elif _qres["forest"] is not None:
                    _parts.append(f"{_qres['forest']} phiên Forest mới")
                if _qres["reading_error"]:
                    _parts.append(f"Reminder lỗi ({_qres['reading_error']})"); _has_err = True
                elif _qres["reading"] is not None:
                    _parts.append(f"{_qres['reading']} phần đọc/xem")
                if _qres["calendar_error"]:
                    _parts.append(f"lịch lỗi ({_qres['calendar_error']})"); _has_err = True
                elif _qres["calendar"] is not None:
                    _parts.append(f"{_qres['calendar']} appointment lịch")
                st.session_state['quick_sync_msg'] = "Đã đồng bộ: " + ", ".join(_parts) + "." if _parts else "Không có file mới để đồng bộ."
                st.session_state['quick_sync_has_error'] = _has_err
            st.rerun()

        with st.expander("Dự phòng", expanded=False):
            _tab_forest, _tab_cal, _tab_rem = st.tabs(
                ["Tải lên từ Forest", "Đồng bộ lịch", "Tải lên từ Reminder"])
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
                    sync_range = st.segmented_control("Khoảng đồng bộ",
                                                       ["-30 / +30 ngày", "-90 / +90 ngày", "-180 / +180 ngày"],
                                                       default="-90 / +90 ngày", key="wc_range")
                sync_days = {"-30 / +30 ngày": 30, "-90 / +90 ngày": 90, "-180 / +180 ngày": 180}.get(sync_range or "-90 / +90 ngày", 90)
                with sc2:
                    st.write("")
                    if st.button("Đồng bộ ngay", type="primary", key="wc_sync_btn"):
                        _start = _today_vn() - timedelta(days=sync_days)
                        _end = _today_vn() + timedelta(days=sync_days)
                        with st.spinner("Đang kết nối iCloud..."):
                            _n, _err = sync_work_calendar(_start, _end)
                        if _err:
                            st.error(_err)
                        else:
                            st.success(f"Đã đồng bộ {_n} appointment (từ {_start:%d/%m/%Y} đến {_end:%d/%m/%Y}).")
                            time.sleep(1)
                            st.rerun()

                with st.expander("Đồng bộ khoảng ngày khác (nâng cao)", expanded=False):
                    dc1, dc2, dc3 = st.columns([2, 2, 1])
                    with dc1:
                        _adv_start = st.date_input("Từ ngày", value=_today_vn() - timedelta(days=365 * 2), key="wc_adv_start")
                    with dc2:
                        _adv_end = st.date_input("Đến ngày", value=_today_vn(), key="wc_adv_end")
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

            new_cat = st.text_input("Tạo nhóm mới:").strip()
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
    with st.expander("3. Dữ liệu làm việc hiện tại", expanded=True):
        if not db_current.empty:
            db_base = db_current.reset_index(drop=True)
            _dt = pd.to_datetime(db_base['Thời gian bắt đầu'], errors='coerce')
            # Tổng quan: thẻ căn giữa
            st.markdown(
                f"<div class='glass-card' style='padding:10px 18px;margin-bottom:14px;text-align:center;'>"
                f"<span style='font-size:14px;color:var(--text);'>Tổng <b>{len(db_base)}</b> phiên · "
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
                    f"<div style='text-align:center;font-size:13px;color:var(--text-2);margin-top:2px;'>"
                    f"Hiển thị phiên {_start + 1}–{min(_start + PAGE_SIZE, n)} / {n}</div>",
                    unsafe_allow_html=True)
    with st.expander("4. Giao diện", expanded=True):
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
                _border = "var(--text)" if _selected else "transparent"
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

    with st.expander("5. Quản lý hệ thống", expanded=True):
        c1, c2, c3 = st.columns(3)
        _today = _today_vn().strftime('%Y-%m-%d')
        with c1:
            st.subheader("Sao lưu")
            # Nhắc sao lưu: chỉ hiện ngay tại đây (không phải banner toàn app) -- đúng nơi và
            # lúc người dùng hành động được ngay. Chưa từng sao lưu, hoặc lần gần nhất quá 30
            # ngày, thì nhắc nhẹ.
            _last_bk = _cached_settings().get("last_backup_at")
            _days_since_bk = (_today_vn() - date.fromisoformat(_last_bk)).days if _last_bk else None
            if _days_since_bk is None:
                st.caption("Chưa sao lưu lần nào.")
            elif _days_since_bk > 30:
                st.caption(f"Lần sao lưu gần nhất: {_days_since_bk} ngày trước. Nên sao lưu định kỳ.")
            db_now = load_db()
            if not db_now.empty:
                _buf = io.BytesIO()
                with zipfile.ZipFile(_buf, "w", zipfile.ZIP_DEFLATED) as _z:
                    _settings_df = pd.DataFrame(list(load_settings().items()), columns=["key", "value"])
                    for _fn, _df in [(DB_FILE, db_now), (MAPPING_FILE, load_mapping()),
                                      (DELETED_FILE, load_deleted()), (NOTES_FILE, load_notes()),
                                      (QUICK_NOTES_FILE, load_quick_notes()),
                                      (WORK_CALENDAR_FILE, load_work_calendar()),
                                      (READING_LOG_FILE, load_reading_log()),
                                      (SETTINGS_FILE, _settings_df)]:
                        if not _df.empty:
                            _z.writestr(os.path.basename(_fn), _df.to_csv(index=False))
                st.download_button("Tải bản sao lưu", _buf.getvalue(),
                                   f"forest_backup_{_today}.zip", "application/zip",
                                   on_click=lambda: save_setting("last_backup_at", _today))
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
                        if QUICK_NOTES_FILE in names:
                            parts.append(f"Ghi chú nhanh **{len(pd.read_csv(io.BytesIO(_z.read(QUICK_NOTES_FILE))))}** dòng")
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
                    if QUICK_NOTES_FILE in names:
                        save_quick_notes_bulk(pd.read_csv(io.BytesIO(_z.read(QUICK_NOTES_FILE)), dtype=str))
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
                _sb_delete_all("quick_notes", "id")
                _sb_delete_all("work_calendar", "uid")
                _sb_delete_all("reading_log", "uid")
                _sb_delete_all("settings", "key")
                st.cache_data.clear()
                st.success("Đã xoá toàn bộ dữ liệu!")
                time.sleep(1)
                st.rerun()

        if _auth_configured:
            st.divider()
            st.caption(f"Đăng nhập với **{st.user.email}**")
            st.button("Đăng xuất", icon=":material/logout:", on_click=st.logout, key="auth_logout_btn")

# ==========================================
# TAB HƯỚNG DẪN
# ==========================================
elif nav == "Hướng dẫn":
    _guide_tabs = st.tabs([
        ":material/auto_awesome: Tổng quan",
        ":material/self_improvement: Nhịp làm việc",
        ":material/summarize: Hôm nay & Báo cáo",
        ":material/menu_book: Sách & Gundam",
        ":material/tune: Tuỳ biến",
        ":material/new_releases: Cập nhật",
    ], key="help_subtabs")

    # ==========================================
    # SUB-TAB: TỔNG QUAN
    # ==========================================
    with _guide_tabs[0]:
        with st.container(border=True, key="guide_intro"):
            st.markdown("#### Forest Dashboard là gì")
            st.markdown(
                "App này **không đặt mục tiêu và không nhắc nhở** — Forest (app trồng cây trên điện thoại) đã "
                "làm việc đó rồi. Forest Dashboard chỉ làm một việc: lấy dữ liệu phiên tập trung bạn đã có (xuất "
                "CSV từ Forest) cộng thêm 2 nguồn tuỳ chọn (lịch hẹn Work qua CalDAV, tiến độ đọc sách/xem Gundam "
                "qua Apple Reminders), rồi **nhìn lại** — bạn tập trung nhiều nhất vào khung giờ nào, thói quen "
                "đang mạnh lên hay chùng xuống, một cuốn sách mất bao lâu để đọc xong. Toàn bộ app mang tính "
                "**hồi cứu (retrospective)**, không phải một bộ đếm ngược hay thanh tiến độ.\n\n"
                "Thanh điều hướng trên cùng có 7 mục:\n"
                "- **Hôm nay** — trang mặc định khi mở app. Đúng như tên gọi: chỉ 1 ngày, thường là ngày bạn "
                "đang xem đầu tiên mỗi lần mở app.\n"
                "- **Báo cáo** — nhìn theo Tổng quan (toàn bộ lịch sử), Tuần, Tháng, Năm, hoặc theo Dự án.\n"
                "- **Sách** / **Gundam** — nhật ký đọc sách và xem Gundam, ghép từ 2 nguồn dữ liệu khác nhau.\n"
                "- **Tìm kiếm** — tra lại ghi chú/lịch/sách·Gundam cũ theo từ khoá.\n"
                "- **Tuỳ biến** — nơi nạp dữ liệu, phân loại Dự án, đổi màu accent, sao lưu/khôi phục.\n"
                "- **Hướng dẫn** — chính là trang bạn đang xem.\n\n"
                "Nhiều biểu đồ/bảng ở đây (\"Bảng số liệu tổng quan\", \"Biểu đồ lịch\", \"Bảng số liệu\"...) "
                "xuất hiện GIỐNG HỆT nhau ở nhiều trang báo cáo khác nhau — đây là lựa chọn thiết kế có chủ đích: "
                "một bộ \"từ vựng hình ảnh\" dùng chung, để đọc quen 1 biểu đồ ở Hôm nay là đọc được y hệt biểu "
                "đồ đó ở Báo cáo, Sách hay Gundam. Mục này liệt kê từng thành phần dùng chung đó **một lần duy "
                "nhất**; sub-tab kế tiếp chỉ nói về phần khác biệt riêng của từng trang.")

        guide_item(
            "stat_panel.png", "Bảng số liệu tổng quan",
            "Mẫu **hero + nhóm chip** dùng ở gần như mọi trang: 1-2 con số lớn nhất ở trên cùng (vd Tổng giờ, "
            "Số cây), rồi các nhóm số liệu phụ xếp thành hàng chip nhỏ bên dưới, mỗi nhóm có nhãn xám in hoa "
            "(TRUNG BÌNH, 7 NGÀY GẦN ĐÂY, CHUỖI NGÀY...). Triết lý: tách rõ **cái quan trọng nhất** (hero, to, "
            "đập vào mắt trước) khỏi **cái để tra cứu khi cần** (chip, nhỏ, đọc lướt qua vẫn được) — thay vì "
            "một hàng metric phẳng ngang nhau khiến mắt không biết nhìn vào đâu trước.",
            tip="Chip có viền teal đậm (class .tw, dùng đúng màu accent đang chọn) là chip đang \"active\"/nổi "
                "bật — ví dụ trạng thái \"Đang đọc\" của 1 cuốn sách, hoặc chuỗi ngày hiện tại nếu đang giữ "
                "kỷ lục.",
            where="Hôm nay · Mọi trang Báo cáo · Sách · Gundam")

        guide_item(
            "session_bar.png", "Thanh phân bố độ dài phiên",
            "Một thanh ngang chia theo % thời lượng, xếp phiên tập trung vào 5 nhóm theo độ dài: **Tối thiểu** "
            "(≤10 phút — đúng bằng mức tối thiểu Forest cho log 1 phiên), **Ngắn** (dưới 25 phút), **Trung bình** "
            "(25 đến dưới 50 phút), **Dài** (50 đến dưới 90 phút), **Rất Dài** (từ 90 phút trở lên). 5 nhóm tô "
            "bằng 5 sắc độ của **cùng một màu accent** (nhạt → đậm), đúng dải màu cũng dùng cho Biểu đồ lịch và "
            "Giờ tập trung theo thứ bên dưới — chỉ khác cách trình bày (thanh % thay vì lưới ô).",
            tip="Nhãn % chỉ hiện trên đoạn chiếm từ 9% thanh trở lên — đoạn quá mỏng bị ẩn nhãn để tránh chữ "
                "chồng chéo, nhưng đoạn màu vẫn còn đó, di chuột vẫn xem được giá trị.",
            where="Mọi trang Báo cáo · Sách · Gundam (mục Tổng quan)")

        guide_item(
            "calendar.png", "Biểu đồ lịch",
            "Lưới ô kiểu \"contribution graph\", mỗi ô là 1 ngày, càng đậm càng tập trung nhiều giờ. Thang màu "
            "chia **8 bậc cố định theo mốc giờ tuyệt đối** — 0h, dưới 0.5h, 0.5-1h, 1-2h, 2-3h, 3-4h, 4-6h, và từ "
            "6h trở lên — **không** co giãn theo dữ liệu đang xem. Đây là lựa chọn có chủ đích: nếu thang màu "
            "tự co giãn theo max/min của khung thời gian đang xem, một ngày \"cày\" bất thường nhiều giờ sẽ kéo "
            "thang giãn ra, làm mọi ngày bình thường khác trông nhạt đi như nhau — mất khả năng so sánh giữa "
            "các đợt xem khác nhau. Mốc cố định giữ đúng ý nghĩa \"đậm bằng nhau = số giờ bằng nhau\" dù bạn "
            "đang xem tháng nào.",
            where="Báo cáo → Tổng quan · Báo cáo → Dự án")

        guide_item(
            "trend.png", "Xu hướng theo thời gian",
            "Biểu đồ cột theo ngày/tuần/tháng (tuỳ trang), cộng 1 đường chấm đen: **trung bình động 7 ngày**. "
            "Đường này tính trên đúng 7 ngày lịch liên tiếp — kể cả những ngày hoàn toàn không có phiên nào (tính "
            "là 0 giờ trong công thức trung bình), chứ không phải 7 ngày *có hoạt động* gần nhất. Nhờ vậy đường "
            "trung bình phản ánh đúng nhịp độ thực tế theo lịch: nghỉ liền vài ngày sẽ kéo đường đi xuống thấy "
            "rõ, thay vì bị \"làm mượt\" đi vì chỉ đếm ngày có hoạt động. Chỉ xuất hiện ở biểu đồ theo Ngày "
            "(không áp dụng khi nhóm theo Tuần/Tháng, vì lúc đó mỗi cột đã là 1 kỳ dài hơn 7 ngày rồi).",
            where="Mọi trang Báo cáo · Sách · Gundam")

        guide_item(
            "hourly.png", "Xu hướng tập trung theo khung giờ",
            "Biểu đồ đường theo 24 khung giờ trong ngày, cho biết bạn hay tập trung vào lúc nào — sáng sớm, "
            "giữa trưa, hay khuya. Đọc chung với \"Giờ tập trung theo thứ\" bên dưới sẽ ra bức tranh đầy đủ: "
            "biểu đồ này trả lời \"giờ nào\", còn biểu đồ kia trả lời \"giờ nào của thứ nào\".",
            where="Mọi trang Báo cáo · Sách · Gundam")

        guide_item(
            "heatmap.png", "Giờ tập trung theo thứ",
            "Lưới nhiệt 7×24 (7 thứ trong tuần × 24 giờ), càng đậm nghĩa là trung bình càng nhiều giờ tập trung "
            "vào đúng khung giờ đó của đúng thứ đó. **Điểm quan trọng về cách tính trung bình**: mẫu số là số "
            "ngày *có hoạt động* của đúng thứ đó trong khoảng đang xem, không phải tổng số lần thứ đó xuất hiện "
            "trên lịch. Nếu 1 tháng có 4 Chủ Nhật nhưng bạn chỉ tập trung vào 2 trong số đó, trung bình được "
            "chia cho 2 chứ không phải 4 — tránh những thứ ít hoạt động bị \"pha loãng\" trông nhạt hơn thực "
            "tế chỉ vì có nhiều ngày trống xen giữa.",
            where="Mọi trang Báo cáo · Sách · Gundam")

        guide_item(
            "histogram.png", "Phân bố độ dài phiên",
            "Biểu đồ cột chia phiên tập trung thành các khoảng 5 phút một (10-15′, 15-20′... tới 55-60′), cộng "
            "1 cột gộp cho mọi phiên từ 60 phút trở lên. Có 3 đường mốc chấm đứng tại 25′/50′/90′ (đúng 3 ranh "
            "giới của \"Thanh phân bố độ dài phiên\" phía trên, để 2 biểu đồ đọc khớp nhau) và 1 đường gạch "
            "ngang đánh dấu độ dài trung bình.",
            where="Mọi trang Báo cáo · Sách · Gundam")

        guide_item(
            "table.png", "Bảng số liệu",
            "Bảng chi tiết theo từng Danh mục/Dự án qua các kỳ, với ô được tô nền theo cường độ (heat cell) — "
            "càng đậm càng nhiều giờ. Độ đậm tính theo **tỉ lệ giá trị ô đó so với giá trị lớn nhất trong CẢ "
            "BẢNG** (không phải so với giá trị lớn nhất của riêng hàng đó), giới hạn ở mức 70% độ đục tối đa để "
            "ô đậm nhất vẫn còn đọc được số bên trong; ô dưới 0.05 giờ hiện dấu chấm giữa \"·\" thay vì số 0 "
            "cho gọn mắt. Cột \"Tổng\" ở cuối luôn để trắng, không tô — vì cột đó cộng dồn cả kỳ nên tất nhiên "
            "luôn là số lớn nhất hàng, tô đậm nó sẽ không mang thêm thông tin gì. Dấu **▾** đỏ nhỏ cạnh 1 ô nghĩa "
            "là kỳ đó giảm còn ≤40% so với kỳ liền trước (chỉ tính khi kỳ trước đạt ít nhất 1 giờ) — tín hiệu "
            "sụt giảm rõ rệt, không phải dao động ngẫu nhiên.",
            tip="Vì độ đậm so sánh trong TOÀN BẢNG chứ không phải trong từng hàng, một Dự án hoạt động ít vẫn "
                "luôn nhạt màu hơn Dự án hoạt động nhiều — đây là điểm khác so với kiểu heatmap chuẩn hoá theo "
                "hàng, giúp so sánh được độ lớn tuyệt đối giữa các Dự án chứ không chỉ giữa các kỳ trong 1 Dự án.",
            where="Mọi trang Báo cáo · Sách · Gundam")

        guide_item(
            "shortcuts.png", "Phím tắt bàn phím",
            "Dùng được từ bất kỳ trang nào (trừ khi con trỏ đang ở trong 1 ô nhập liệu — gõ số/"
            "chữ bình thường trong ô tìm kiếm hay ghi chú không bị bắt nhầm thành phím tắt). Bấm "
            "**?** bất kỳ lúc nào để hiện/ẩn bảng tóm tắt các phím tắt này ngay trong app.\n\n"
            "**Điều hướng nhanh:**\n"
            "- **1 – 7**: nhảy nhanh tới từng mục trên thanh điều hướng, đúng thứ tự trái sang "
            "phải (1 = Hôm nay, 2 = Báo cáo, ... 7 = Hướng dẫn).\n"
            "- **Shift + 1 .. 5**: nhảy thẳng tới Báo cáo và chọn đúng 1 trong 5 lát cắt — "
            "Shift+1 = Tổng quan, Shift+2 = Tuần, Shift+3 = Tháng, Shift+4 = Năm, Shift+5 = Dự án. "
            "Riêng Shift+5 focus sẵn vào ô chọn Nhóm/Dự án — bấm ↑/↓ + Enter để xem chi tiết "
            "ngay, không cần bấm chuột mở dropdown trước.\n"
            "- **N**: mở ngay ô soạn Ghi chú ngày của **hôm nay** — dù đang ở trang nào, không "
            "cần tự bấm qua Hôm nay rồi tìm nút Thêm/Sửa ghi chú; trang tự cuộn tới đúng ô soạn "
            "và focus sẵn vào đó, gõ được luôn ở phím tiếp theo mà không cần bấm chuột.\n"
            "- **/** (dấu gạch chéo): focus vào ô Tìm kiếm — nếu đang ở trang khác thì tự nhảy "
            "tới Tìm kiếm trước, nếu đã đứng sẵn ở đó thì chỉ focus lại ô nhập. Đang gõ trong ô "
            "này mà muốn thoát ra thì bấm **Esc** — chỉ bỏ con trỏ ra khỏi ô, không xoá từ khoá "
            "đang gõ.\n"
            "- **F / R / L**: nhảy tới Tuỳ biến → mục \"1. Dữ liệu đầu vào\" → đúng tab — F mở "
            "tab Tải lên từ Forest (và bấm luôn nút chọn file), R mở tab Tải lên từ Reminder "
            "(cũng bấm luôn nút chọn file), L mở tab Đồng bộ lịch (chỉ dừng ở đó, còn phải tự "
            "chọn khoảng ngày rồi mới bấm Đồng bộ). Với F/R, sau khi chọn xong file và bảng xem "
            "trước hiện ra, nút \"Xác nhận\" tự được focus sẵn — chỉ cần bấm **Enter** là xong, "
            "không cần rê chuột tìm nút.\n\n"
            "**Theo ngữ cảnh (chỉ có tác dụng ở đúng trang liên quan):**\n"
            "- **[ / ]**: ở trang Sách/Gundam — chuyển qua lại giữa 2 sub-tab Tổng quan/Chi tiết; "
            "sang Chi tiết (]) thì ô chọn sách/series được focus sẵn — bấm ↑/↓ để duyệt rồi Enter "
            "để xem ngay, không cần bấm chuột mở dropdown trước.\n"
            "- **← / →**: ở trang Hôm nay — lùi/tiến 1 ngày (bấm hộ 2 nút ◀ ▶ đã có sẵn).\n"
            "- **Ctrl/Cmd + Enter**: khi đang soạn Ghi chú ngày (con trỏ trong ô Quill) — lưu "
            "ngay, tương đương bấm \"Cập nhật\".\n"
            "- **Esc**: khi đang soạn Ghi chú ngày — huỷ, tương đương bấm \"Huỷ\" (không lưu "
            "thay đổi vừa gõ).",
            tip="Không dùng được khi đang giữ Ctrl/Cmd/Alt (để không đụng phím tắt của hệ điều "
                "hành/trình duyệt). Riêng Ctrl/Cmd+Enter và Esc là ngoại lệ có chủ đích, chỉ hoạt "
                "động khi con trỏ đang ở TRONG ô soạn Quill; mọi phím tắt còn lại đều tự tắt khi "
                "đang gõ trong bất kỳ ô nhập liệu nào (tìm kiếm, ghi chú, ngày...) để không bắt "
                "nhầm chữ/số bạn đang gõ thành lệnh.",
            where="Toàn app")

    # ==========================================
    # SUB-TAB: NHỊP LÀM VIỆC
    # ==========================================
    with _guide_tabs[1]:
        with st.container(border=True, key="guide_workflow_intro"):
            st.markdown("#### Dùng app này bao nhiêu là đủ")
            st.markdown(
                "**App này là cái gương, không phải bàn làm việc.** Thời gian nhìn vào gương không tự nó tạo ra "
                "năng suất — nó chỉ giúp bạn điều chỉnh. Nếu thấy mình mở dashboard nhiều lần trong ngày, đó "
                "thường là dấu hiệu đang trốn việc theo cách trông có vẻ chính đáng.\n\n"
                "Thời gian hợp lý cho nhịp lõi: **~5 phút/ngày, ~15 phút cuối tuần, ~30 phút cuối tháng** — cộng "
                "lại chưa tới 1% thời gian thức mỗi tuần. Bốn mục lõi dưới đây (Hàng ngày → Hàng năm) xếp theo "
                "đúng nhịp đó, từ ngắn/thường xuyên nhất tới dài/hiếm nhất. Mục đầu tiên (Đầu ngày) là **tuỳ "
                "chọn**, không tính vào nhịp ~5 phút/ngày — chỉ dành cho ai có thói quen lên kế hoạch trước khi "
                "bắt tay vào việc, và chỉ mất thêm khoảng 30 giây liếc qua.")

        guide_item(
            "planning_ref.png", "Đầu ngày (tuỳ chọn) — tham khảo trước khi lên kế hoạch",
            "Nếu Pomodoro đầu tiên trong ngày là để lên kế hoạch (vd quyết định việc cần làm trong Things 3 hay "
            "công cụ tương tự) trước khi bấm giờ Forest cho việc gì, mở **Hôm nay** lúc đó vẫn có ích — trang "
            "không còn trống trơn chỉ vì chưa có phiên nào:\n\n"
            "- **Lịch hẹn Work hôm đó** (nếu đã đồng bộ CalDAV) vẫn hiện đầy đủ trong Ghi chú ngày, không phụ "
            "thuộc đã có phiên hay chưa — hữu ích để biết hôm nay còn bao nhiêu khung giờ trống trước khi xếp "
            "việc vào Things 3.\n"
            "- Panel **\"Tham khảo cho lên kế hoạch\"** cho 2 số tính từ lịch sử: tổng giờ + số phiên của đúng "
            "**thứ này tuần trước**, và **trung bình giờ của đúng thứ này** qua mọi tuần đã có dữ liệu — đủ để "
            "cân nhắc \"thứ này thường mình làm được bao nhiêu\" trước khi chốt kế hoạch cho hôm nay.\n\n"
            "Cố ý KHÔNG có số so sánh kiểu \"đã làm X so với TB\" ở đây (khác nhánh có phiên của Hàng ngày bên "
            "dưới) — ngày chưa diễn ra thì một con số delta chỉ gây hiểu lầm là đang tụt lại, không phải thông "
            "tin tham khảo hữu ích.",
            tip="2 số tham chiếu tính theo ĐÚNG THỨ (Thứ 7 so Thứ 7, không phải 7 ngày liền trước) — nhịp làm "
                "việc thường lặp theo thứ trong tuần hơn là theo khoảng cách ngày liên tiếp.",
            where="Hôm nay (khi ngày đang xem chưa có phiên nào)")

        guide_item(
            "note_editor.png", "Hàng ngày — 5 phút, nghi thức đóng ngày",
            "Chọn 1 mốc cố định trong ngày (sau bữa tối, hoặc ngay trước khi tắt máy) — thói quen sống nhờ mốc "
            "neo, không nhờ ý chí:\n\n"
            "1. **Xuất CSV từ Forest và tải lên** (Tuỳ biến → Dữ liệu đầu vào). Mọi giá trị của app phụ thuộc "
            "bước 30 giây này — không tải lên thì không có gì để xem lại.\n"
            "2. **Nhìn Hôm nay 1 phút**: dòng thời gian trong ngày + so sánh \"vs Thứ X tuần trước\". Câu hỏi "
            "duy nhất cần trả lời: hôm nay có đúng như mình định không — không phải để tự khen hay tự trách, "
            "chỉ để ghi nhận.\n"
            "3. **Viết Ghi chú ngày 2-3 phút** — thói quen giá trị nhất trong toàn bộ app, vì nó nuôi cùng lúc 3 "
            "tính năng khác: Nhật ký tuần/tháng, Tìm kiếm, và \"Ngày này năm trước\". Con số nói bạn làm bao "
            "nhiêu, ghi chú nói bạn làm gì và tại sao — một năm sau, cái thứ hai mới là thứ đáng đọc lại.",
            tip="Không nên mở Báo cáo tháng/năm hàng ngày — dữ liệu dài hạn nhìn mỗi ngày chỉ sinh nhiễu, một "
                "ngày xấu không nói lên gì cả.",
            where="Hôm nay")

        guide_item(
            "heatmap.png", "Hàng tuần — 15 phút, review có tác dụng điều chỉnh",
            "Tuần là đơn vị đủ ngắn để sửa và đủ dài để có tín hiệu thật, làm vào sáng Thứ Hai hoặc tối Chủ "
            "Nhật:\n\n"
            "- **Báo cáo → Tuần**: xem tổng giờ vs tuần trước và vs trung bình (app đã tự cắt kỳ dở dang nên số "
            "so sánh công bằng). Chênh lệch ±20% là dao động bình thường — chỉ hành động khi lệch lớn VÀ biết "
            "rõ lý do.\n"
            "- **Đọc lại Nhật ký tuần** (mục 2): lướt lại ghi chú 7 ngày liên tiếp thường lộ ra pattern mà từng "
            "ngày riêng lẻ không thấy được.\n"
            "- **Nhìn Giờ tập trung theo thứ + Biểu đồ lịch** mỗi 2-3 tuần một lần: nếu dữ liệu nói bạn mạnh "
            "nhất 8-11h sáng, xếp việc khó vào đúng khung đó tuần tới — đây là quyết định cụ thể duy nhất mà "
            "biểu đồ này phục vụ.",
            where="Báo cáo → Tuần")

        guide_item(
            "table.png", "Hàng tháng — 30 phút, kiểm tra tỉ trọng ưu tiên",
            "Câu hỏi ở tầm tháng khác hẳn tầm tuần: không phải \"làm đủ giờ chưa\" mà là **tỉ trọng có đúng ưu "
            "tiên không**. Xem Phân bổ thời gian và Bảng số liệu (Báo cáo → Tháng), chú ý dấu ▾ đỏ (nhóm đang bị "
            "bỏ bê) — nếu một việc được gọi là ưu tiên mà chỉ chiếm 5% thời gian, con số đang nói thật hơn bạn.\n\n"
            "Cuối tháng cũng là lúc: xem nhịp đọc sách/xem Gundam có đều không, cuốn nào treo quá lâu; kiểm tra "
            "Dự án mới phát sinh trong tháng đã được gán Nhóm ở mục Phân loại chưa; và bấm Sao lưu nếu app đã "
            "nhắc (tự động nhắc khi quá 30 ngày kể từ lần gần nhất) — đừng bỏ qua lời nhắc đó, chỉ 1 cú bấm.",
            where="Báo cáo → Tháng · Tuỳ biến → Phân loại · Quản lý hệ thống")

        guide_item(
            "nam.png", "Hàng năm & không định kỳ",
            "**Báo cáo → Năm** hợp để đọc vào tuần cuối tháng 12 hoặc dịp sinh nhật — đọc như đọc tổng kết, kèm "
            "lướt \"Ngày này năm trước\" ở vài ngày đáng nhớ.\n\n"
            "**Tìm kiếm** dùng theo nhu cầu chứ không theo lịch — bật lên khi cần trả lời \"lần trước gặp vấn đề "
            "này mình xử lý thế nào?\". Giá trị của nó tỉ lệ thuận với độ chăm viết Ghi chú ngày, vì nó chỉ tìm "
            "được trong những gì bạn đã viết ra.",
            where="Báo cáo → Năm · Tìm kiếm")

        with st.container(border=True, key="guide_workflow_traps"):
            st.markdown("#### Ba cái bẫy cần tránh")
            st.markdown(
                "1. **Tối ưu con số thay vì công việc** — trồng cây cho phiên đọc tin vặt để \"đủ chỉ tiêu giờ\" "
                "là tự lừa mình bằng chính công cụ chống tự lừa. Số giờ là proxy, không phải mục tiêu.\n"
                "2. **Chuỗi ngày (streak) trở thành gông** — chuỗi đứt sau ngày ốm/ngày nghỉ đúng nghĩa là bình "
                "thường. App cố tình đặt lời nhắc chuỗi đứt ở tông khích lệ (\"Hôm nay là lúc tốt để bắt đầu "
                "lại\") — hãy đọc nó đúng tinh thần đó, không phải lời trách.\n"
                "3. **Review mà không có câu hỏi** — mỗi lần mở app nên có sẵn 1 câu hỏi (hôm nay thế nào? / "
                "tuần này lệch gì? / tháng này đúng ưu tiên chưa?). Mở app không có câu hỏi = lướt số liệu giải "
                "trí, không phải nhìn lại có chủ đích.\n\n"
                "Nếu chỉ giữ được một thói quen duy nhất từ toàn bộ mục này: **viết ghi chú mỗi tối**. Mọi thứ "
                "khác của app vẫn hoạt động khi bạn lơ là, nhưng ghi chú bỏ trống một tháng là mất vĩnh viễn một "
                "tháng ký ức — phần duy nhất của app không thể \"tải lên lại\" được.")

    # ==========================================
    # SUB-TAB: HÔM NAY & BÁO CÁO
    # ==========================================
    with _guide_tabs[2]:
        with st.container(border=True, key="guide_hn_intro"):
            st.markdown("#### Hôm nay là gì, Báo cáo là gì")
            st.markdown(
                "**Hôm nay** và **Báo cáo** đều xem cùng 1 nguồn dữ liệu (phiên Forest), chỉ khác **đơn vị thời "
                "gian**: Hôm nay luôn đúng 1 ngày cụ thể, Báo cáo nhìn theo lát cắt rộng hơn — Tổng quan (toàn "
                "bộ lịch sử, không giới hạn kỳ), Tháng, Tuần, hoặc lọc theo 1 Dự án/Nhóm. Trang \"Hôm nay\" "
                "từng là 1 lát cắt bên trong Báo cáo (gọi là \"Ngày\") nhưng đã được tách ra thành mục **đầu "
                "tiên, độc lập** trên thanh điều hướng — lý do rất thực tế: đây là trang được mở đầu tiên mỗi "
                "ngày, tách riêng giúp vào thẳng nó mà không phải đi qua Báo cáo trước.")

        guide_item(
            "day_timeline.png", "Dòng thời gian trong ngày",
            "Dải ngang biểu diễn 24 giờ của ngày đang xem, mỗi phiên tập trung vẽ thành 1 khối tại đúng vị trí "
            "giờ nó diễn ra, tô màu theo Danh mục. Đọc trực quan hơn bảng liệt kê: nhìn một lần biết ngay buổi "
            "sáng/chiều/tối hôm đó dồn vào việc gì, có bị ngắt quãng nhiều không.",
            where="Hôm nay → Tổng quan ngày")

        guide_item(
            "planning_ref.png", "Khi ngày đang xem chưa có phiên nào",
            "Trước khi phiên đầu tiên trong ngày được log — thường gặp nhất là mở app đầu ngày trước khi trồng "
            "cây nào — mục \"1. Tổng quan ngày\" ở trên (dòng thời gian, chip so sánh) chưa có gì để vẽ nên "
            "được thay bằng panel **\"Tham khảo cho lên kế hoạch\"**: tổng giờ + số phiên của đúng thứ này tuần "
            "trước, và trung bình giờ của đúng thứ này qua toàn bộ lịch sử — 2 con số tính từ NGÀY KHÁC nên vẫn "
            "hiện được dù ngày đang xem trống trơn. Ghi chú ngày (kèm chip lịch hẹn Work/sách·Gundam) và \"Ngày "
            "này năm trước\" vẫn hiện bình thường bên dưới, không phụ thuộc gì vào việc đã có phiên hay chưa.",
            where="Hôm nay (ngày đang xem chưa có phiên nào)")

        guide_item(
            "note_editor.png", "Ghi chú ngày (nhật ký)",
            "Thẻ 2 cột: cột trái là Thứ/ngày, cột phải gộp **3 nguồn** cho đúng ngày đó — chip lịch hẹn Work (nếu "
            "đã đồng bộ CalDAV), chip sách/Gundam đã đọc/xem xong hôm đó (kèm icon sách/TV tương ứng ngay đầu "
            "chip để phân biệt nhanh 2 loại không cần đọc chữ), và ô ghi chú tự do dưới nhãn **Ghi chú chính** "
            "(trình soạn thảo Quill, hỗ trợ chữ đậm/nghiêng/danh sách). Nếu ngày đang xem giữ **kỷ lục** (xem "
            "mục \"Bảng vàng\" bên dưới), 1 chip kèm icon huy chương hiện thêm ở đầu, trước cả chip lịch. Nếu có "
            "**ghi chú nhanh** đang chờ (xem mục ngay bên dưới), danh sách đó hiện ngay phía trên nhãn \"Ghi chú "
            "chính\". Cùng 1 bố cục 2 cột này lặp lại ở thẻ **Nhật ký** của Báo cáo → Tháng/Tuần (khi đó là danh "
            "sách nhiều ngày xếp dọc) — nhất quán để không phải học lại cách đọc.",
            tip="Ô ghi chú không có khung viền bao quanh phần soạn thảo — cố ý bỏ khung để phần nhập liệu \"mở\" "
                "hơn, không tạo cảm giác đang điền vào 1 form.",
            where="Hôm nay → Ghi chú ngày · Báo cáo → Tháng/Tuần → Nhật ký")

        guide_item(
            "quick_note.png", "Ghi chú nhanh từ iOS (Shortcuts)",
            "Một Shortcut trên iPhone (Trợ lý Siri, Action Button, hoặc icon Màn hình chính) hỏi bạn gõ 1 dòng "
            "ý tưởng, rồi gửi thẳng lên Supabase — **không đi qua app**, không cần mở trình duyệt. Mỗi lần gửi "
            "tạo 1 quick note mới, gắn kèm giờ máy lúc gửi. Ngày nào có quick note đang chờ, danh sách đó hiện "
            "ngay trong Ghi chú ngày, phía trên nhãn \"Ghi chú chính\" — mỗi dòng là 1 badge **giờ** nhỏ cộng "
            "chữ ghi chú định dạng như ghi chú thường (không phải chip nhỏ), tách biệt hẳn với Ghi chú chính "
            "(không có nút gộp — quick note đứng độc lập, không tự chuyển vào ghi chú chính). Mỗi dòng có 2 "
            "nút riêng: **Sửa** (mở ô nhập ngay tại dòng đó, sửa xong bấm Cập nhật/Huỷ) và **Xoá**. Sửa một "
            "dòng thành trống rồi bấm Cập nhật cũng xoá luôn dòng đó, giống hệt hành vi Ghi chú chính. Nhật ký "
            "Tuần/Tháng và Ngày này năm trước cũng hiện danh sách quick note của mỗi ngày (chỉ đọc, không có "
            "nút Sửa/Xoá ở 2 nơi đó — thao tác quản lý chỉ có tại đúng Ghi chú ngày của ngày đó).",
            tip="Giờ hiện trên badge là lúc quick note được TẠO (Shortcut tự gửi lên) — sửa nội dung không đổi "
                "lại giờ này.",
            where="Hôm nay → Ghi chú ngày · Báo cáo → Tháng/Tuần → Nhật ký · Ngày này năm trước")

        guide_item(
            "otd.png", "Ngày này năm trước",
            "Với ngày đang xem, tìm lại đúng ngày/tháng đó ở **mọi năm trước** và gộp **4 nguồn** cùng lúc: "
            "phiên Forest, ghi chú, lịch hẹn Work, và sách/Gundam đã đọc/xem — năm nào có ít nhất 1 trong 4 "
            "nguồn thì hiện dòng cho năm đó, sắp xếp năm gần nhất lên trên. Không cần năm đó phải có ghi chú mới "
            "hiện — chỉ cần có lịch hẹn hoặc đã đọc xong 1 chương cũng đủ để dòng năm đó xuất hiện. Mục này càng "
            "dùng lâu càng dày dữ liệu, vì mỗi năm trôi qua lại có thêm 1 \"ngày này năm trước\" mới để so sánh. "
            "Năm nào rơi đúng vào ngày giữ kỷ lục cũng hiện chip kèm icon huy chương y hệt Ghi chú ngày.",
            where="Hôm nay → Ngày này năm trước")

        guide_item(
            "bang_vang.png", "Bảng vàng: Ngày nổi bật & Kỷ lục",
            "2 khái niệm tách biệt, cả hai tính thẳng từ dữ liệu phiên mỗi lần tải trang (không lưu riêng nên "
            "không bao giờ lỗi thời):\n\n"
            "- **Ngày nổi bật** — top 1/2/3 ngày nhiều giờ nhất trong đúng phạm vi đang xem (Tổng quan = toàn "
            "bộ lịch sử, Tuần/Tháng/Năm = đúng kỳ đang chọn), hiện như 1 nhóm chip trong **Bảng số liệu** của "
            "trang đó. Đồng hạng nếu 2 ngày bằng tuyệt đối số giờ.\n"
            "- **Kỷ lục** — ngày nhiều giờ nhất **toàn thời gian**, tính chung (top 3, hiện ở Bảng số liệu "
            "Tổng quan) và tính riêng cho từng Nhóm/Dự án đã có từ **5 ngày dữ liệu trở lên** (chỉ giữ đúng 1 "
            "ngày kỷ lục mỗi Nhóm/Dự án — ở Bảng số liệu Báo cáo → Dự án, chip này gộp chung ngày + số giờ và "
            "mang tên \"Ngày nổi bật\" cho đồng bộ hình thức với Tuần/Tháng/Năm, dù vẫn cùng 1 khái niệm kỷ lục). "
            "Mọi ngày giữ 1 trong các kỷ lục "
            "này được gắn thêm 1 chip kèm icon huy chương trên Timeline (Hôm nay, Nhật ký Tuần/Tháng, Ngày này "
            "năm trước) — 1 chip riêng cho mỗi kỷ lục nếu giữ nhiều cùng lúc, luôn xếp đầu tiên trước cả chip "
            "Lịch. Icon này (và icon sách/TV trên chip đọc sách/Gundam cạnh đó) dùng chung font Material Symbols "
            "mà Streamlit đã tự tải sẵn cho mọi icon khác trong app — không phải emoji, nên hiện đồng nhất trên "
            "mọi thiết bị/trình duyệt thay vì tuỳ theo bộ font emoji của từng máy.",
            tip="Chỉ \"Kỷ lục\" (toàn thời gian) mới lên chip Timeline — \"Ngày nổi bật\" theo Tuần/Tháng/Năm cố "
                "tình KHÔNG gắn chip vì gần như tuần/tháng nào cũng có top 3 riêng, gắn hết sẽ mất cảm giác hiếm.",
            where="Báo cáo → Tổng quan/Tuần/Tháng/Năm/Dự án · Hôm nay · Ngày này năm trước")

        guide_item(
            "search.png", "Tìm kiếm",
            "Trang riêng trên thanh điều hướng, tra một từ khoá cùng lúc trên **cả 3 nguồn**: ghi chú, tiêu đề "
            "lịch hẹn Work, và tên/phần sách·Gundam đã đọc·xem. Lọc trực tiếp trên text thuần trong trình duyệt "
            "(không cần dịch vụ tìm kiếm riêng) nên gõ từ khoá xong bấm Enter là ra kết quả ngay.\n\n"
            "Kết quả gộp theo **ngày** — mỗi ngày khớp hiện 1 dòng, nhưng hiện ĐỦ CẢ 3 nguồn của đúng ngày đó "
            "(không chỉ riêng phần vừa khớp), để không mất ngữ cảnh: tìm \"họp nhóm\" ra đúng ngày có lịch hẹn "
            "đó, dòng kết quả cũng hiện luôn ghi chú và sách đã đọc hôm đó nếu có. Bấm vào Thứ/ngày để nhảy "
            "thẳng sang Hôm nay của đúng ngày đó, xem đầy đủ chi tiết.",
            tip="Cần gõ ít nhất 2 ký tự mới bắt đầu tìm, tránh lọc ra gần như cả lịch sử ghi chú chỉ với 1 chữ.",
            where="Tìm kiếm")

        guide_item(
            "baocao_kyxem.png", "Chọn kỳ xem — 5 lát cắt của Báo cáo",
            "Thanh gạch chân ở đầu trang Báo cáo, chọn 1 trong 5 lát cắt:\n\n"
            "- **Tổng quan** — toàn bộ lịch sử đã nạp, không lọc theo kỳ nào; lát cắt mặc định khi vào trang, vì "
            "đây là bức tranh rộng nhất, hợp để bắt đầu.\n"
            "- **Năm** — tổng kết 1 năm cụ thể kiểu \"Year in Review\", xem thêm ở mục riêng ngay bên dưới.\n"
            "- **Tháng** / **Tuần** — 2 lát cắt dùng chung đúng 1 cấu trúc 8 mục đánh số (chỉ khác đơn vị thời "
            "gian nhóm theo), có thêm bộ chọn kỳ cụ thể (tháng nào/tuần nào) và thẻ Nhật ký liệt kê từng ngày "
            "trong kỳ đó.\n"
            "- **Dự án** — lọc toàn bộ báo cáo về đúng 1 Danh mục hoặc 1 Dự án đã chọn, dùng khi muốn xem sâu "
            "riêng 1 việc thay vì cả bức tranh chung.\n\n"
            "Việc Tháng và Tuần dùng chung 1 khuôn 8 mục không phải trùng lặp code cho vui — đây là thiết kế "
            "\"trung lập theo kỳ\" (period-agnostic): cùng 1 bộ biểu đồ áp được cho bất kỳ độ dài kỳ nào, không "
            "cần thiết kế riêng cho từng đơn vị thời gian.\n\n"
            "**Mục \"1. Tổng quan\" của Năm/Tháng/Tuần đều có 2 dòng so sánh nhỏ dưới mỗi số** — \"vs [Năm/"
            "Tháng/Tuần] trước\" (đúng kỳ liền kề) và \"vs Trung bình\" (trung bình mọi kỳ khác, không tính kỳ "
            "đang xem). Nếu kỳ đang xem là kỳ **hiện tại và chưa kết thúc** (vd mới qua 3 ngày đầu tháng), app "
            "tự động cắt CẢ 2 baseline so sánh xuống đúng cùng số ngày đã trôi qua — 1 dòng caption nhỏ phía "
            "trên bảng số liệu sẽ nói rõ khi nào việc cắt này đang diễn ra. Không có bước cắt này, so tổng 3 "
            "ngày với tổng cả tháng trước sẽ luôn ra số âm rất lớn, trông như sụt giảm nghiêm trọng dù thực ra "
            "chỉ vì tháng chưa đi hết.",
            where="Báo cáo")

        guide_item(
            "nam.png", "Báo cáo → Năm",
            "Bản tổng kết 1 năm cụ thể, cố ý gọn hơn hẳn Tháng/Tuần (chỉ 4 mục thay vì 8) vì đây là trang xem "
            "\"để có cảm giác tổng thể\" chứ không cần đào sâu từng biểu đồ:\n\n"
            "1. **Tổng quan** — 5 số hero (Tổng thời gian, Thời gian/ngày, Số cây, Số cây/ngày, Thời gian/phiên) "
            "kèm so sánh với năm trước/trung bình các năm khác, cộng Top 3 Danh mục, Top 3 Dự án, và \"Ngày nổi "
            "bật\" (xem mục \"Bảng vàng\" ở trên) trong năm.\n"
            "2. **Biểu đồ lịch** — lưới nhiệt trọn năm đang chọn, không kéo dài sang năm khác (khác các trang "
            "Báo cáo khác luôn hiện lưới tới tận hôm nay).\n"
            "3. **Đọc sách & Gundam trong năm** — đếm nhanh số phần đã đọc/xem và số cuốn·series có hoạt động "
            "trong năm, không đi sâu phân loại \"Đã xong/Đang đọc\" (xem chi tiết đầy đủ ở tab Sách/Gundam).\n"
            "4. **Bảng số liệu** — bảng chi tiết theo Danh mục/Dự án của riêng năm đó.",
            where="Báo cáo → Năm")

        guide_item(
            "pie.png", "Phân bổ thời gian",
            "Biểu đồ tròn chia % thời lượng theo Danh mục trong đúng kỳ đang xem (Tháng hoặc Tuần) — trả lời "
            "nhanh câu hỏi \"kỳ này thời gian dồn vào đâu nhiều nhất\" mà không cần đọc hết bảng số liệu chi "
            "tiết bên dưới.",
            where="Báo cáo → Tháng · Báo cáo → Tuần")

        guide_item(
            "baocao_duan.png", "Báo cáo theo Dự án",
            "Chọn 1 Nhóm (Danh mục) hoặc 1 Dự án cụ thể từ danh sách thả xuống — mặc định **chưa chọn gì** khi "
            "mới vào trang (không tự động hiện Dự án đầu tiên), buộc phải chủ động chọn để tránh nhầm đang xem "
            "đúng Dự án mình muốn. Sau khi chọn, cấu trúc rút gọn còn 5 mục (bỏ Nhật ký và Phân bổ thời gian vì "
            "không có khái niệm \"kỳ\" ở đây — đây là toàn bộ lịch sử của riêng Dự án đó) — dùng khi muốn theo "
            "dõi tiến triển của 1 việc cụ thể xuyên suốt, ví dụ so Biểu đồ lịch của \"Deep Work\" tháng này với "
            "tháng trước. Nhóm/Dự án đã có từ 5 ngày dữ liệu trở lên còn thêm 1 nhóm chip \"Ngày nổi bật\" (ngày "
            "nhiều giờ nhất toàn thời gian của riêng Nhóm/Dự án đó) trong Bảng số liệu — xem mục \"Bảng vàng\" "
            "ở trên.",
            where="Báo cáo → Dự án")

    # ==========================================
    # SUB-TAB: SÁCH & GUNDAM
    # ==========================================
    with _guide_tabs[3]:
        with st.container(border=True, key="guide_rl_intro"):
            st.markdown("#### 1 Reminder List = 1 cuốn sách/series")
            st.markdown(
                "Sách và Gundam đọc chung **một bảng dữ liệu** (`reading_log`, nạp từ file Apple Reminders xuất "
                "qua Shortcuts) và chạy chung **một hàm hiển thị** — 2 trang tách biệt trên thanh điều hướng chỉ "
                "khác nhau ở một bộ nhãn chữ (đọc/xem, phần/tập, sách/series...), không phải 2 đoạn code riêng.\n\n"
                "Quy ước đặt tên: mỗi **Reminder List** trên điện thoại là 1 cuốn sách/series, đặt tên dạng "
                "\"Tác giả - Tên sách\" (hoặc \"Gundam - Tên series\"); mỗi **Reminder đã tick hoàn thành** "
                "trong list đó là 1 phần/chương/tập đã đọc/xem xong. App tách tên hiển thị bằng cách cắt theo "
                "dấu **\"-\" đầu tiên** trong tên list, ưu tiên dạng có khoảng trắng \" - \" (fallback về dấu "
                "\"-\" liền nếu không có khoảng trắng) — phần **sau** dấu gạch là tên hiển thị, phần **trước** "
                "(tác giả, hoặc chữ \"Gundam\") bị bỏ. List nào có tên bắt đầu bằng chữ \"gundam\" (không "
                "phân biệt hoa/thường) tự động được xếp vào trang Gundam thay vì Sách.")

        guide_item(
            "reading_log.png", "Tổng quan (Sách/Gundam)",
            "Hero + chip theo nhóm (giống \"Bảng số liệu tổng quan\" ở sub-tab Tổng quan phía trước), cộng "
            "thanh phân bố và dòng thời gian liệt kê từng cuốn/series theo tiến độ. Mỗi cuốn/series được ghép "
            "từ **tối đa 2 nguồn**: phiên Forest (nếu tên Dự án Forest trùng khớp tên sách) và các phần đã tick "
            "trong Reminders — 1 cuốn có thể chỉ có 1 trong 2 nguồn, hoặc cả 2 cùng lúc; ô nào thiếu dữ liệu vì "
            "thiếu nguồn hiện dấu gạch ngang \"—\" thay vì để trống hay báo lỗi.",
            where="Sách → Tổng quan · Gundam → Tổng quan")

        guide_item(
            "reading_detail.png", "Chi tiết (Sách/Gundam)",
            "Chọn đúng 1 cuốn/series (mặc định chưa chọn gì) để xem sâu 4 mục: **1. Số liệu** (hero + nhóm chip "
            "Mốc thời gian/Nhịp độ/Trạng thái riêng của cuốn đó), **2. Nhật ký đọc** (từng phần đã hoàn thành, "
            "theo ngày), **3. Biểu đồ lịch** (tô đậm theo số phần đọc/ngày thay vì số giờ, vì \"1 ngày đọc 3 "
            "chương\" có ý nghĩa hơn số giờ với sách chỉ theo dõi qua Reminders), **4. Bảng số liệu theo ngày**.\n\n"
            "**Cách tính \"Số ngày\"** đáng chú ý riêng: lấy **hợp (union)** ngày sớm nhất và muộn nhất giữa CẢ "
            "2 nguồn, không chỉ tính khi có phiên Forest — cuốn chỉ theo dõi qua Reminders vẫn ra đúng \"Số "
            "ngày\" thay vì hiện trống. Cụ thể: nếu chỉ có Forest, lấy khoảng ngày của Forest; nếu chỉ có "
            "Reminders, lấy khoảng ngày của Reminders; nếu có cả 2 (vd đang bấm giờ Forest rồi sau đó chuyển "
            "sang chỉ tick Reminders), lấy ngày bắt đầu SỚM NHẤT và ngày kết thúc MUỘN NHẤT giữa 2 nguồn — trải "
            "dài đúng theo thực tế đọc, không bị cắt cụt vì đổi cách theo dõi giữa chừng.",
            where="Sách → Chi tiết · Gundam → Chi tiết")

        guide_item(
            "gundam.png", "Vì sao Gundam cần \"suy luận\" series",
            "Forest chỉ có đúng 1 tag chung \"Gundam\" — không có Dự án riêng cho từng series như Rừng Na Uy "
            "hay Harry Potter có thể trùng tên 1 Dự án Forest. Vậy khi bạn bấm giờ Forest với tag \"Gundam\", "
            "app không có cách nào biết chắc bạn đang xem series nào **trừ khi suy luận từ dữ liệu Reminders**: "
            "với mỗi ngày có phiên gắn tag Gundam, app tìm lần hoàn thành Reminder (ở BẤT KỲ series Gundam nào) "
            "**gần ngày đó nhất về mặt thời gian** — có thể là trước hoặc sau, miễn là gần nhất — rồi gán cả "
            "ngày đó cho đúng series của lần hoàn thành đó. Nếu bạn chỉ đang xem 1 series tại 1 thời điểm (kịch "
            "bản phổ biến), suy luận này gần như luôn đúng; nếu xem xen kẽ nhiều series cùng lúc, ngày ở giữa 2 "
            "lần hoàn thành sẽ được gán về phía gần hơn.",
            tip="Không có \"không suy luận được\" — ngay cả phiên trước lần hoàn thành Reminder đầu tiên hoặc "
                "sau lần cuối cùng vẫn được gán về mốc gần nhất hiện có (đầu hoặc cuối), không bị bỏ sót.",
            where="Gundam")

    # ==========================================
    # SUB-TAB: TUỲ BIẾN
    # ==========================================
    with _guide_tabs[4]:
        with st.container(border=True, key="guide_tb_intro"):
            st.markdown("#### 5 mục của tab Tuỳ biến")
            st.markdown(
                "Mọi thứ điều khiển \"app trông ra sao\" và \"dữ liệu đến từ đâu\" đều gom về đúng 1 trang, "
                "đánh số 1-5: **Dữ liệu đầu vào** (nạp dữ liệu mới), **Phân loại** (gán Dự án vào Nhóm), "
                "**Dữ liệu làm việc hiện tại** (xem/xoá phiên thô), **Giao diện** (màu accent), **Quản lý hệ "
                "thống** (sao lưu/khôi phục/làm mới). 3 mục đầu và mục cuối đi theo đúng thứ tự thao tác thực tế "
                "khi mới dùng app (nạp → phân loại → kiểm tra lại → sao lưu); riêng Giao diện là tuỳ chỉnh "
                "không liên quan tới luồng dữ liệu đó nên xếp riêng, ngay trước Quản lý hệ thống.")

        guide_item(
            "prep_data_input.png", "1. Dữ liệu đầu vào",
            "**Đồng bộ nhanh** hiện trực tiếp làm phương án mặc định — dành cho Shortcut iOS chạy từ share sheet: "
            "khi Export CSV từ Forest, Shortcut lấy luôn file backup Reminder rồi tải cả 2 lên bucket Supabase "
            "Storage (tên file bắt đầu bằng `forest`/`reminder`, vd `forest_2026-07-06.csv`). Bấm **Đồng bộ "
            "ngay** để app tự tìm file mới nhất mỗi loại, nạp vào DB theo đúng luật của các cách thủ công bên "
            "dưới (Forest cộng thêm, Reminder thay thế toàn bộ), đồng bộ luôn lịch Work qua CalDAV, rồi xoá các "
            "file cũ hơn trong bucket — gộp 3 thao tác thủ công thành 1 nút. Chưa tạo Shortcut/bucket thì mục "
            "này chỉ hiện \"chưa có\", không ảnh hưởng gì tới các cách tải tay bên dưới.\n\n"
            "3 cách còn lại chỉ là phương án dự phòng, gộp chung trong 1 khối thu gọn (\"Dự phòng\") — chỉ "
            "cần mở khi Đồng bộ nhanh chưa dùng được hoặc cần thao tác riêng lẻ:\n"
            "- **Tải lên từ Forest** — nạp file CSV xuất từ app Forest. Mỗi lần tải lên chỉ **thêm dữ liệu mới**, "
            "tự động bỏ qua phiên trùng lặp (so theo giờ bắt đầu/kết thúc) và phiên đã từng bị xoá trước đó — "
            "nạp lại cùng 1 file nhiều lần không sợ bị nhân đôi dữ liệu.\n"
            "- **Đồng bộ lịch** — kéo lịch hẹn từ Apple Calendar (lịch \"Work\") qua CalDAV, khoảng ngày quanh "
            "hôm nay chọn nhanh (±30/±90/±180 ngày). Mục con \"Đồng bộ khoảng ngày khác (nâng cao)\" cho chọn "
            "khoảng ngày tuỳ ý — dùng khi cần lấp dữ liệu lịch cũ cho mục *Ngày này năm trước*, không cần dùng "
            "thường xuyên.\n"
            "- **Tải lên từ Reminder** — nạp file `reading_log.csv` do Shortcut \"Xuất tiến độ đọc\" xuất từ "
            "Apple Reminders, mỗi lần tải lên **thay thế toàn bộ** dữ liệu Sách/Gundam cũ (khác hẳn cách Forest "
            "CSV chỉ cộng thêm) — vì Reminders phản ánh đúng trạng thái hiện tại của toàn bộ list, không phải 1 "
            "lát cắt thời gian như CSV Forest.",
            where="Tuỳ biến → 1. Dữ liệu đầu vào")

        guide_item(
            "prep_classify.png", "2. Phân loại",
            "Gán mỗi Dự án Forest vào 1 Nhóm (Danh mục) — vd Dự án \"Deep Work\"/\"Viết báo cáo\" cùng gán "
            "vào Nhóm \"Công việc\". Nhóm dùng để gộp các biểu đồ/bảng theo cấp cao hơn Dự án đơn lẻ. Dự án "
            "chưa gán Nhóm nào vẫn hoạt động bình thường (tự đứng riêng, không thuộc Nhóm nào) — phân loại là "
            "tuỳ chọn để gọn báo cáo, không bắt buộc để app chạy được.",
            where="Tuỳ biến → 2. Phân loại")

        guide_item(
            "prep_worktable.png", "3. Dữ liệu làm việc hiện tại",
            "Bảng thô liệt kê từng phiên đã nạp (giờ bắt đầu/kết thúc, Dự án, thời lượng), phân trang 100 dòng "
            "mỗi trang khi dữ liệu nhiều. Chọn 1 hoặc nhiều dòng rồi xoá — phiên bị xoá được ghi nhớ riêng (bảng "
            "`deleted_sessions`) để nếu sau này nạp lại đúng file CSV cũ, phiên đó không tự động xuất hiện lại.",
            where="Tuỳ biến → 3. Dữ liệu làm việc hiện tại")

        guide_item(
            "giao_dien.png", "4. Giao diện — màu accent",
            "14 màu để chọn, xếp theo thứ tự sắc độ (đỏ/cam/vàng → xanh lá → xanh dương → tím, cuối cùng là "
            "\"Than chì\" gần như xám) cho dễ dò theo dải cầu vồng thay vì danh sách rối mắt. Bấm 1 màu là áp "
            "dụng **ngay lập tức**, không cần nút \"Lưu\" riêng — màu được ghi vào Supabase (bảng `settings`) "
            "nên vẫn giữ nguyên qua các lần mở lại app.\n\n"
            "**1 màu accent chọn ra lan toả tới 3 nơi khác nhau, bằng 3 cơ chế khác nhau**:\n"
            "- **Nút bấm/khung viền/chip** — qua biến CSS (`:root { --accent: ...; }`), toàn bộ stylesheet tham "
            "chiếu tới biến này thay vì mã màu cứng.\n"
            "- **Biểu đồ đơn sắc/bảng nhiệt** (Biểu đồ lịch, Giờ tập trung theo thứ, Thanh phân bố độ dài phiên, "
            "heat cell của Bảng số liệu) — KHÔNG qua CSS, mà qua Python: màu accent được đổi thành 1 giá trị "
            "**hue** (sắc độ trên vòng thuần sắc), rồi mọi dải màu này tự xoay theo đúng hue đó, giữ nguyên độ "
            "bão hoà và khoảng độ sáng nhạt→đậm — nên đổi màu accent tự động đổi TẤT CẢ biểu đồ đơn sắc cùng "
            "lúc, không cần sửa từng biểu đồ riêng.\n"
            "- **Ô ghi chú (trình soạn thảo Quill)** — chạy trong 1 iframe riêng biệt, CSS của trang chính không "
            "chạm tới được; app tự tiêm 1 đoạn `<style>` khác vào bên trong iframe đó, lặp lại mỗi 400ms để "
            "chống việc Streamlit dựng lại iframe làm mất style đã tiêm.\n\n"
            "Nếu bảng `settings` chưa được tạo trên Supabase, hoặc giá trị lưu trong đó bị hỏng, app **tự rơi "
            "về màu Teal mặc định** thay vì báo lỗi hay crash — tính năng đổi màu hoàn toàn tuỳ chọn, không có "
            "nó app vẫn chạy bình thường với đúng màu gốc từ trước tới nay.\n\n"
            "**Chế độ tối (dark mode)**: app tự đổi giao diện tối/sáng theo đúng cài đặt hệ thống của thiết bị "
            "(hoặc theo lựa chọn thủ công trong menu ⋮ ở góc phải trên cùng của Streamlit, nếu đã tự đổi khác "
            "với hệ thống) — **không có nút bật/tắt riêng trong app**, vì Streamlit chưa cho phép đổi theme "
            "bằng code lúc đang chạy, chỉ đọc được theme hiện tại để tự tô đúng màu theo. Toàn bộ nút, thẻ, "
            "biểu đồ, bảng nhiệt, ô ghi chú đều có phiên bản màu riêng cho chế độ tối; màu accent đang chọn vẫn "
            "giữ nguyên và tự sáng/tối lại cho hợp với nền mới.",
            tip="3 màu đầu tiên (Hồng đào/Cam cháy/Vàng nắng) cố ý gần tông với 2 trạng thái cảnh báo cố định "
                "trong app (cam = chuỗi đang treo, đỏ = chuỗi đã đứt) — nếu chọn 1 trong 3 màu này làm accent, "
                "2 trạng thái cảnh báo đó sẽ trông gần giống màu accent hơn bình thường. Đánh đổi này đã được "
                "chấp nhận để có đủ lựa chọn màu ấm, không phải giới hạn kỹ thuật.",
            where="Tuỳ biến → 4. Giao diện")

        guide_item(
            "prep_backup.png", "5. Quản lý hệ thống",
            "3 thao tác trên toàn bộ dữ liệu:\n\n"
            "- **Sao lưu** — đóng gói mọi bảng (phiên, phân loại, ghi chú, ghi chú nhanh, lịch, "
            "sách/Gundam, cài đặt màu) thành "
            "1 file .zip, tên tự kèm ngày giờ. App tự nhớ **ngày sao lưu gần nhất** (bảng `settings`) — nếu chưa "
            "từng sao lưu, hoặc lần gần nhất đã quá 30 ngày, 1 dòng nhắc nhỏ hiện ngay phía trên nút này.\n"
            "- **Khôi phục** — tải 1 file .zip đã sao lưu để phục hồi đúng nguyên trạng tại thời điểm đó, dùng "
            "khi chuyển máy/trình duyệt hoặc muốn quay lại 1 mốc dữ liệu cũ.\n"
            "- **Làm mới** — xoá sạch toàn bộ dữ liệu để bắt đầu lại, bắt buộc tick ô xác nhận trước khi bấm vì "
            "thao tác không thể hoàn tác.",
            tip="Dữ liệu đã lưu bền vững trên Supabase (không mất khi khởi động lại/redeploy app), nhưng vẫn nên "
                "tải bản sao lưu định kỳ làm lớp an toàn thứ hai — dòng nhắc 30 ngày ở trên chính là để nhớ việc "
                "này, không cần tự đặt lịch riêng.",
            where="Tuỳ biến → 5. Quản lý hệ thống")

    # ==========================================
    # SUB-TAB: CẬP NHẬT
    # ==========================================
    with _guide_tabs[5]:
        st.caption("Các thay đổi tính năng gần đây nhất, mới nhất lên trước.")

        guide_update(152, "Thêm dòng \"điểm nhấn\" cuối panel Tổng quan Tuần/Tháng/Năm", [
            "Cuối thẻ Tổng quan của Báo cáo Tuần/Tháng/Năm giờ có 1 câu nhận xét tự chọn ĐÚNG 1 "
            "tín hiệu đáng nói nhất của kỳ: kỷ lục mới, lần đầu vượt mốc tròn của năm, cú bật lại "
            "sau kỳ im ắng, tăng/giảm rõ rệt, một ngày/một dự án gánh cả kỳ, dồn việc cuối tuần, "
            "phiên sâu hơn hay vụn hơn hẳn nếp quen, chuyên cần gần đủ ngày, rải đều nhiều dự án… "
            "— không lặp lại các con số đã có ở hàng hero phía trên.",
            "Câu chữ có nhiều biến thể cho mỗi tình huống, chọn cố định theo kỳ (xem lại kỳ cũ "
            "luôn thấy đúng 1 câu đó, nhưng 2 kỳ khác nhau cùng tình huống sẽ không lặp y hệt). "
            "Khi kỳ đang xem còn dở dang, mọi so sánh trong câu tự tính theo \"cùng kỳ\" đã trôi "
            "qua của các kỳ trước cho công bằng.",
        ])
        guide_update(141, "Thêm phím tắt bàn phím, gọn trang Tìm kiếm", [
            "Phím tắt toàn app: 1-7 nhảy nhanh giữa các trang, N mở nhanh Ghi chú ngày của hôm "
            "nay, / focus vào ô Tìm kiếm — xem mục \"Phím tắt bàn phím\" ngay bên dưới.",
            "Trang Tìm kiếm gọn lại: bỏ tiêu đề/nhãn/placeholder khi chưa gõ gì, số kết quả "
            "\"Tìm thấy N ngày khớp\" chuyển thành 1 card riêng kèm icon, lề trên/dưới đều nhau.",
        ])
        guide_update(137, "Hiện tham khảo lên kế hoạch khi Hôm nay chưa có phiên", [
            "\"Hôm nay\" trước đây bị kẹt ở ngày cuối cùng có dữ liệu (không phải hôm nay thật) khi chưa log "
            "phiên nào trong ngày — nghĩa là không xem được trang đúng lúc cần nhất: đầu ngày, trước khi lên "
            "kế hoạch. Sửa để trang luôn mặc định đúng hôm nay thật, kể cả khi hôm nay chưa có phiên nào.",
            "Thêm panel \"Tham khảo cho lên kế hoạch\" (đúng thứ này tuần trước, trung bình đúng thứ này) hiện "
            "ngay khi ngày đang xem trống — phục vụ thói quen dùng Pomodoro đầu ngày để lên kế hoạch (vd Things "
            "3) trước khi bấm giờ Forest cho việc gì.",
            "Cập nhật sub-tab \"Nhịp làm việc\" (mục mới \"Đầu ngày\") và \"Hôm nay & Báo cáo\" (mục mới \"Khi "
            "ngày đang xem chưa có phiên nào\") để mô tả cách dùng mới này.",
        ])
        guide_update(136, "Thêm sub-tab \"Nhịp làm việc\" trong Hướng dẫn", [
            "Mục mới, không nói về tính năng mà nói về **cách đưa app vào nhịp làm việc thực tế**: nên dùng "
            "bao nhiêu mỗi ngày/tuần/tháng, xem gì ở mỗi mốc, và 3 cái bẫy thường gặp (tối ưu con số thay vì "
            "công việc, biến chuỗi ngày thành gông, review không có câu hỏi).",
            "Đặt ngay sau sub-tab Tổng quan — đọc trước phần mô tả chi tiết từng trang, vì nó trả lời câu hỏi "
            "\"nên dùng app này thế nào\" trước khi đi vào \"app này có gì\".",
        ])
        guide_update(133, "Thêm chế độ tối (dark mode)", [
            "Toàn bộ giao diện — nút, thẻ, thanh điều hướng, bảng số liệu, ô ghi chú, biểu đồ và bảng nhiệt "
            "(Biểu đồ lịch, Giờ tập trung theo thứ, Thanh phân bố độ dài phiên) — giờ có phiên bản màu riêng "
            "cho chế độ tối, tự chọn theo cài đặt hệ thống/menu ⋮ của Streamlit.",
            "Dải màu teal của các bảng nhiệt tự **đảo chiều độ sáng** ở chế độ tối (nhạt→đậm thay vì "
            "đậm→nhạt) để \"càng nhiều giờ càng nổi bật\" vẫn đúng trên nền tối, thay vì bị đảo ngược ý nghĩa.",
            "Màu accent đang chọn vẫn giữ nguyên và tự đổi sắc độ cho hợp với nền tối/sáng.",
            "Xem thêm giải thích ở mục **4. Giao diện** của tab Tổng quan trong Hướng dẫn.",
        ])
        guide_update(132, "Thêm Báo cáo Năm, sửa so sánh kỳ dở dang, Tìm kiếm, nhắc sao lưu", [
            "**Báo cáo → Năm** (mục mới, giữa Tổng quan và Tháng) — bản tổng kết 1 năm cụ thể kiểu \"Year in "
            "Review\", gồm 4 mục: Tổng quan (kèm so sánh năm trước/trung bình), Biểu đồ lịch trọn năm, Đọc sách "
            "& Gundam trong năm, Bảng số liệu.",
            "**Sửa lỗi so sánh kỳ dở dang** — mục \"1. Tổng quan\" của Năm/Tháng/Tuần trước đây so tổng của kỳ "
            "đang xem (có thể mới qua vài ngày) với TOÀN BỘ kỳ trước, ra những con số âm rất lớn và gây hiểu "
            "lầm. Giờ khi kỳ đang xem là kỳ hiện tại còn dở dang, cả 2 baseline so sánh tự cắt theo đúng phần "
            "đã trôi qua để so sánh công bằng, kèm 1 dòng caption nhỏ giải thích khi việc cắt này đang diễn ra.",
            "**Tìm kiếm** (mục mới trên thanh điều hướng) — tra từ khoá cùng lúc trên ghi chú, tiêu đề lịch hẹn "
            "Work, và tên/phần sách·Gundam đã đọc·xem, gộp kết quả theo ngày kèm đủ ngữ cảnh.",
            "**Nhắc sao lưu** — Tuỳ biến → Quản lý hệ thống tự nhớ ngày sao lưu gần nhất, nhắc nhẹ khi chưa từng "
            "sao lưu hoặc đã quá 30 ngày.",
        ])
        guide_update(126, "Mở rộng bảng màu accent lên 14 màu, hiện tên màu trực tiếp trên nút", [
            "Mục \"1. Giao diện\" chuyển lên **đầu tiên** trong tab Tuỳ biến (trước cả Dữ liệu đầu vào), bỏ "
            "dòng chú thích thừa phía dưới bảng màu.",
            "Bảng màu accent mở rộng từ 8 lên **14 màu**, người dùng tự chọn qua 1 bản xem trước tương tác, xếp "
            "theo thứ tự cầu vồng cho dễ dò.",
            "Tên màu hiện thẳng trên nút bấm (không còn chỉ nằm ở tooltip khi rê chuột), kèm dấu ✓ đánh dấu màu "
            "đang dùng; màu chữ trên nút tự đổi trắng/đen theo độ sáng nền để luôn đọc rõ.",
        ])
        guide_update(125, "Thêm trang \"Hôm nay\", đổi tên tab Dữ liệu, thêm màu accent (bản đầu)", [
            "Trang \"Hôm nay\" ra đời — tách từ lát cắt \"Ngày\" trong Báo cáo, trở thành mục **đầu tiên và "
            "mặc định** trên thanh điều hướng, vì đây là trang được mở đầu tiên mỗi ngày.",
            "\"Tổng quan\" (toàn bộ lịch sử, không giới hạn kỳ) chuyển vào làm lát cắt đầu tiên của Báo cáo, "
            "thay cho vị trí của \"Ngày\" cũ.",
            "Đổi tên tab \"Chuẩn bị dữ liệu\" thành **\"Tuỳ biến\"**.",
            "Thêm bộ chọn màu accent (phiên bản đầu, 8 màu) — áp dụng ngay cho nút, biểu đồ đơn sắc và bảng "
            "nhiệt trên toàn app.",
        ])
        guide_update(124, "Sửa vạch kẻ thừa dưới tab Sách/Gundam", [
            "Bỏ 1 vạch xám kẻ ngang mà Streamlit tự vẽ thêm bên dưới 2 tab \"Tổng quan/Chi tiết\" ở trang Sách "
            "và Gundam, cho khớp đúng kiểu gạch chân đã dùng ở bộ chọn kỳ của Báo cáo (chỉ có 1 vạch ngắn dưới "
            "mục đang chọn, không có vạch dài chạy hết chiều ngang).",
        ])
        guide_update(123, "Gọn bộ chọn kỳ của Báo cáo, đổi icon Gundam/Dự án", [
            "Ẩn nhãn \"Chọn kỳ xem\" phía trên bộ chọn kỳ của Báo cáo cho gọn phần đầu trang.",
            "Đổi kiểu nút của bộ chọn kỳ từ dạng viên thuốc (pill, nền đặc) sang gạch chân (underline tab), khớp "
            "đúng phong cách Tổng quan/Chi tiết đang dùng ở Sách/Gundam.",
            "Đổi icon Gundam từ hình robot sang khiên; đổi icon lát cắt Dự án từ thư mục sang cặp táp.",
        ])
        guide_update(122, "Quay lại thanh điều hướng dạng nút mượt, thêm icon cho Sách/Gundam", [
            "Quay lại dùng thanh điều hướng dạng nút bấm mượt (segmented control) thay cho menu thả xuống khi "
            "hover chuột — menu thả xuống làm cả trang tải lại mỗi lần bấm, bất tiện khi dùng thực tế.",
            "Thêm icon Material cho 2 tab \"Tổng quan/Chi tiết\" ở cả trang Sách và Gundam.",
            "Căn giữa cả 2 thanh chọn lát cắt (Báo cáo và Sách/Gundam) cho khớp với thanh điều hướng chính vốn "
            "đã căn giữa từ trước.",
        ])
