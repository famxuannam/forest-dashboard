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
import difflib
import random
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
.ql-toolbar.ql-snow { border-color:#ddd3b8; border-top-left-radius:10px; border-top-right-radius:10px; background:#ece4d0; }
.ql-container.ql-snow { border-color:#ddd3b8; border-bottom-left-radius:10px; border-bottom-right-radius:10px;
  font-family:'Manrope',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; font-size:15px; }
.ql-editor { line-height:1.65; padding:14px 16px; color:#211c13; min-height:150px; caret-color:#00a3ad; }
.ql-editor.ql-blank::before { color:#a39877; font-style:normal; left:16px; right:16px; }
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
            _quill_css.replace("#ece4d0", "#322c20")
            .replace("#ddd3b8", "#3c3628")
            .replace("#211c13", "#f1ece0")
            .replace("#a39877", "#857a5f")
            + "\n.ql-editor { background:#262117; }"
            + "\n.ql-snow .ql-stroke { stroke:#b3a688; }"
            + "\n.ql-snow .ql-fill { fill:#b3a688; }"
            + "\n.ql-snow .ql-picker { color:#b3a688; }"
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


def _snippet_around(txt, query, radius=60):
    """Đoạn trích văn bản thuần quanh từ khớp đầu tiên (dùng cho trang Tìm kiếm, cả ghi chú lẫn
    trích dẫn Kindle); không khớp hoặc không có query thì trả về 120 ký tự đầu."""
    idx = txt.lower().find(query.lower()) if query else -1
    if idx == -1:
        return txt[:120] + ("…" if len(txt) > 120 else "")
    start, end = max(0, idx - radius), min(len(txt), idx + len(query) + radius)
    return ("…" if start > 0 else "") + txt[start:end] + ("…" if end < len(txt) else "")


def _note_snippet(html_content, query, radius=60):
    """Đoạn trích văn bản thuần quanh từ khớp đầu tiên trong 1 ghi chú Quill."""
    return _snippet_around(_note_plain_text(html_content), query, radius)


def _highlight(text, query):
    """Escape text rồi bọc phần khớp query (không phân biệt hoa/thường) trong <mark> -- dùng ở
    trang Tìm kiếm để nổi bật ngay từ khớp trong đoạn trích, không chỉ cắt đoạn văn quanh nó."""
    esc = html_escape(str(text))
    if not query:
        return esc
    pat = re.compile(re.escape(html_escape(str(query))), re.IGNORECASE)
    return pat.sub(lambda m: f"<mark>{m.group(0)}</mark>", esc)

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
HEALTH_METRICS_FILE = "health_metrics.csv"  # chỉ số xét nghiệm máu định kỳ (trang Sức khoẻ)
KINDLE_HIGHLIGHTS_FILE = "kindle_highlights.csv"  # trích dẫn/ghi chú Kindle, nạp từ My Clippings.txt
KINDLE_BOOK_MAP_FILE = "kindle_book_map.csv"  # ánh xạ tên sách Kindle -> Dự án/nhãn hiển thị
DELETED_KINDLE_FILE = "deleted_kindle_highlights.csv"  # sổ đen trích dẫn Kindle đã xoá trong app
GUNDAM_OVERRIDES_FILE = "gundam_overrides.csv"  # gán tay ngày -> series Gundam, ghi đè suy luận tự động

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
    streak_label="Chuỗi đọc", pace_days_label="Số ngày đọc",
    pace_pct_label="% ngày có đọc", avg_hr_label="TB giờ/cuốn", avg_days_label="TB ngày/cuốn",
    fastest_label="Đọc nhanh nhất",
)
GUNDAM_LABELS = dict(
    READING_LABELS, item_col="Series", count_label="Số series", days_label="Ngày xem",
    parts_label="Số tập đã xem", part_recent_label="Tập gần nhất", part_word="tập",
    verb="xem", ongoing="Đang xem", empty_msg="Chưa có dữ liệu Gundam trong nhóm này.",
    streak_label="Chuỗi xem", pace_days_label="Số ngày xem",
    pace_pct_label="% ngày có xem", avg_hr_label="TB giờ/series", avg_days_label="TB ngày/series",
    fastest_label="Xem nhanh nhất",
)

# Tên thứ tiếng Việt (dùng chung mọi nơi)
VN_DAYS = {"Monday": "Thứ Hai", "Tuesday": "Thứ Ba", "Wednesday": "Thứ Tư", "Thursday": "Thứ Năm",
           "Friday": "Thứ Sáu", "Saturday": "Thứ Bảy", "Sunday": "Chủ Nhật"}

# Tên tháng tiếng Việt -- CHỈ dùng cho JS dịch popup lịch của st.date_input (xem
# _inject_date_picker_locale()), component BaseWeb nội bộ của Streamlit không có prop locale lộ
# ra qua API Python nên phải dịch text sau khi mount bằng JS. VN_DAYS ở trên không đủ (chỉ có tên
# đầy đủ, popup lịch dùng viết tắt) nên cần thêm bảng viết tắt riêng ngay dưới đây.
VN_MONTHS = {"January": "Tháng 1", "February": "Tháng 2", "March": "Tháng 3", "April": "Tháng 4",
             "May": "Tháng 5", "June": "Tháng 6", "July": "Tháng 7", "August": "Tháng 8",
             "September": "Tháng 9", "October": "Tháng 10", "November": "Tháng 11",
             "December": "Tháng 12"}
VN_DAYS_ABBR = {"Su": "CN", "Mo": "T2", "Tu": "T3", "We": "T4", "Th": "T5", "Fr": "T6", "Sa": "T7",
                "Sun": "CN", "Mon": "T2", "Tue": "T3", "Wed": "T4", "Thu": "T5", "Fri": "T6", "Sat": "T7"}
# Tên tháng viết đầy đủ bằng chữ (khác VN_MONTHS ở trên -- dạng số "Tháng 7", dùng riêng cho JS
# dịch popup lịch). Dùng cho billboard "Hôm nay" (vd "16 Tháng Bảy 2026"). Index 0 = Tháng Một.
VN_MONTHS_WORD = ["Tháng Một", "Tháng Hai", "Tháng Ba", "Tháng Tư", "Tháng Năm", "Tháng Sáu",
                  "Tháng Bảy", "Tháng Tám", "Tháng Chín", "Tháng Mười", "Tháng Mười Một",
                  "Tháng Mười Hai"]

# Bảng màu phong cách Apple / Latte sáng -- KHÔNG dùng cho biểu đồ Danh mục/Dự án nữa (xem
# CHART_COLORS bên dưới), vẫn giữ cho vài chỗ vẽ đường/marker đơn sắc cũ (vd biểu đồ xu hướng
# Nhật ký đọc sách) không thuộc phạm vi đổi hệ màu "Sổ Tay".
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

# Bảng màu cố định cho biểu đồ phân loại (cột/pie theo Danh mục/Dự án, xem build_color_map())
# -- hệ "Sổ Tay": đất nung/nghệ/rêu/chàm biển/chàm/mận + 2 màu bổ sung để đủ phân biệt khi nhiều
# Danh mục/Dự án hơn 6. KHÔNG đổi theo accent đang chọn (khác heatmap/lịch, xem _teal_shades())
# -- giữ luôn dễ phân biệt dù người dùng chọn accent nào.
CHART_COLORS = ["#b5502e", "#c98a1f", "#5f7a41", "#1f6f6a", "#3d4f8f", "#7a3b5e", "#d8674a", "#8a9a6b"]


# 8 lựa chọn màu accent (tab Tuỳ biến → "4. Giao diện"), người dùng tự chọn -- hệ "Sổ Tay": màu
# đất/mộc mạc, không dùng tông "candy-bright" kiểu iOS nữa. Rút gọn từ 14 xuống 6 (xem lịch sử
# git nếu cần bảng cũ) để nhất quán với hướng thiết kế mới; ai đã lưu 1 trong các màu cũ bị bỏ sẽ
# tự rơi về mặc định mới ở lần tải kế tiếp (xem nhánh fallback _accent_hex bên dưới). "Cam đất"/
# "Ô liu" thêm sau đó lấy đúng 2 màu bổ sung đã có sẵn trong CHART_COLORS (biến thể sáng hơn của
# Đất nung/Rêu) -- không bịa màu mới, đảm bảo vẫn cùng 1 hệ tông với 6 màu gốc.
ACCENT_PRESETS = {
    "Đất nung": "#b5502e",
    "Nghệ": "#c98a1f",
    "Rêu": "#5f7a41",
    "Chàm biển": "#1f6f6a",      # mặc định
    "Chàm": "#3d4f8f",
    "Mận": "#7a3b5e",
    "Cam đất": "#d8674a",
    "Ô liu": "#8a9a6b",
}

# Kiểu nền trang (áp cho .stApp, xem rule CSS dùng var(--bg-image)/var(--bg-size)/var(--bg-position))
# -- "image"/"size"/"position" là giá trị CSS thô ghép thẳng vào background-image/size/position
# qua biến CSS, dùng var(--divider) để tự đổi theo IS_DARK như mọi hoạ tiết khác trong app. "Trơn"
# dùng image:none (hợp lệ) thay vì bỏ hẳn cặp thuộc tính, để 1 cơ chế var() duy nhất áp cho mọi
# lựa chọn, không cần nhánh riêng trong CSS chính. "position" mặc định "0 0" nếu không khai báo
# (không đổi gì so với 5 preset gốc, chỉ 2 preset mới cần lệch layer để so le). Đúng 8 kiểu, khớp
# số lượng 8 màu accent (ACCENT_PRESETS) cho cân trong lưới chọn ở Tuỳ biến.
BG_PRESETS = {
    "Chấm bi": {
        "image": "radial-gradient(circle, var(--divider) 1.1px, transparent 1.1px)",
        "size": "20px 20px",
    },
    "Trơn": {
        "image": "none",
        "size": "auto",
    },
    "Kẻ ngang": {
        "image": "repeating-linear-gradient(transparent 0px, transparent 23px, var(--divider) 24px)",
        "size": "auto",
    },
    "Kẻ ô vuông": {
        "image": ("repeating-linear-gradient(0deg, var(--divider) 0px, var(--divider) 1px, transparent 1px, transparent 22px), "
                   "repeating-linear-gradient(90deg, var(--divider) 0px, var(--divider) 1px, transparent 1px, transparent 22px)"),
        "size": "auto",
    },
    "Chấm bi to": {
        "image": "radial-gradient(circle, var(--divider) 1.6px, transparent 1.6px)",
        "size": "28px 28px",
    },
    "Kẻ chấm": {
        # Chấm nhỏ lặp dày theo chiều ngang (6px) nhưng thưa theo chiều dọc (24px) -> tự xếp thành
        # các hàng chấm ngang trông như dòng kẻ chấm chấm, không cần vẽ path riêng.
        "image": "radial-gradient(circle, var(--divider) 1px, transparent 1px)",
        "size": "6px 24px",
    },
    "Ô vuông nhỏ": {
        "image": ("repeating-linear-gradient(0deg, var(--divider) 0px, var(--divider) 1px, transparent 1px, transparent 12px), "
                   "repeating-linear-gradient(90deg, var(--divider) 0px, var(--divider) 1px, transparent 1px, transparent 12px)"),
        "size": "auto",
    },
    "Chấm bi so le": {
        # 2 lớp radial-gradient CÙNG kích thước ô nhưng lệch nhau nửa ô (position layer 2 = 10px
        # 10px) -> chấm xếp so le kiểu viên gạch, khác hẳn lưới thẳng hàng của "Chấm bi" gốc.
        "image": ("radial-gradient(circle, var(--divider) 1.1px, transparent 1.1px), "
                   "radial-gradient(circle, var(--divider) 1.1px, transparent 1.1px)"),
        "size": "20px 20px, 20px 20px",
        "position": "0 0, 10px 10px",
    },
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

# Màu chữ trên biểu đồ Plotly (nhãn tổng, đường TB động, ngưỡng độ dài phiên...) -- khớp token
# --text light/dark (xem _TOK), gom về 1 hằng để không lặp lại literal + IS_DARK ở nhiều nơi.
PLOT_TEXT = "#f1ece0" if IS_DARK else "#211c13"

# Accent (màu nhấn) đang chọn -- fallback "Chàm biển" mặc định nếu chưa từng chọn hoặc lỗi (kể cả
# khi giá trị đã lưu là 1 trong các preset cũ đã bị bỏ lúc rút gọn còn 6 màu -- không crash, chỉ
# lặng lẽ rơi về mặc định mới). PHẢI tính TRƯỚC _SESSION_COLORS = _teal_shades(5) (dưới đây) vì đó
# là câu lệnh cấp module chạy ngay khi import, sớm hơn cả st.set_page_config()/cổng kiểm tra
# secrets Supabase.
_accent_hex = _cached_settings().get("accent_hex", "#1f6f6a")
if _accent_hex not in ACCENT_PRESETS.values():   # giá trị lạ (hỏng/ghi tay/preset cũ đã bỏ) -> fallback an toàn
    _accent_hex = "#1f6f6a"
ACCENT = _accent_hex
ACCENT_RGB = _hex_rgb_str(ACCENT)
# ACCENT_DARK = "accent tương phản trên nền tint accent nhạt". Ở dark mode, nền tint đó lại
# TỐI hơn nền light -> cần chữ/icon SÁNG hơn accent gốc thay vì tối hơn, nên đổi hàm theo IS_DARK
# (khác bản light-only trước đây luôn gọi _darken). Tên biến/tên CSS var --accent-dark giữ
# nguyên -- mọi nơi đang dùng (chip.tw, guide alert, NUDGE_TONES "good") tự đúng cả 2 chế độ.
ACCENT_DARK = _brighten(ACCENT) if IS_DARK else _darken(ACCENT)
TEAL_HUE = _hex_hue(ACCENT)  # giữ tên biến cũ -- mọi nơi đang dùng TEAL_HUE không cần sửa

# Kiểu nền trang đang chọn -- cùng khuôn fallback an toàn với ACCENT ở trên (giá trị lạ/preset cũ
# đã bỏ -> rơi về "Chấm bi" mặc định, không crash).
_bg_style_name = _cached_settings().get("bg_style", "Chấm bi")
if _bg_style_name not in BG_PRESETS:
    _bg_style_name = "Chấm bi"
BG_STYLE = _bg_style_name
BG_IMAGE = BG_PRESETS[BG_STYLE]["image"]
BG_SIZE = BG_PRESETS[BG_STYLE]["size"]
BG_POSITION = BG_PRESETS[BG_STYLE].get("position", "0 0")


def _teal_shades(n, l_lo=None, l_hi=None):
    """Sinh n sắc độ (cùng hue với ACCENT đang chọn -- tên hàm/biến "teal" giữ lại từ thời accent
    mặc định là Xanh ngọc #00a3ad, nay chỉ còn là tên gọi lịch sử) từ nhạt (l_lo) đến đậm (l_hi)
    -> dùng chung cho các bảng nhiệt (Biểu đồ lịch, thanh Phân bổ độ dài phiên) để đồng bộ một
    họ màu thay vì mỗi nơi một tông riêng.
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
    """Gán màu cố định cho từng tên (Danh mục/Dự án). Ưu tiên bảng màu cơ sở (CHART_COLORS,
    CỐ ĐỊNH -- không đổi theo accent đang chọn, để biểu đồ luôn dễ phân biệt dù accent là màu
    gì); nếu nhiều hơn số màu sẵn có thì sinh thêm màu phân biệt bằng góc vàng
    (golden angle) để không bao giờ bị trùng màu, vẫn ổn định theo tên."""
    colors = list(CHART_COLORS)
    for k in range(len(names) - len(colors)):
        h = (0.61 + (k + 1) * 0.6180339887) % 1.0  # rải đều sắc độ
        colors.append(_hsl_hex(h, 0.62, 0.55))
    return {name: colors[i] for i, name in enumerate(names)}
PLOTLY_CONFIG = {'scrollZoom': False, 'displayModeBar': False, 'responsive': True}

# --- CÁC HÀM XỬ LÝ DỮ LIỆU (đọc/ghi qua Supabase) ---
# save_* dùng ngữ nghĩa "ghi đè toàn bộ" (xoá hết rồi insert lại) để khớp hành vi các nơi gọi.
_SB_PAGE_SIZE = 1000  # PostgREST (nền tảng Supabase) mặc định chỉ trả tối đa 1000 dòng/request
# nếu không tự phân trang -- bảng nào vượt ngưỡng này, gọi thẳng .execute() sẽ ÂM THẦM cắt mất
# phần dư (không lỗi, không warning nào cảnh báo). Đã xác nhận bug thật trên work_calendar (1003
# dòng -- thiếu đúng 3 dòng dư ngưỡng, hiện sai lịch ngày hôm đó dù dữ liệu trong Supabase vẫn
# còn nguyên). Mọi bảng có thể phát triển không giới hạn theo thời gian sử dụng (sessions,
# work_calendar, reading_log, deleted_sessions, notes, kindle_highlights, health_metrics,
# mapping, kindle_book_map, deleted_kindle_highlights...) PHẢI đọc qua _sb_select_all() thay vì
# gọi .execute() trực tiếp -- các bảng nhỏ có trần rõ ràng (settings: vài chục key cấu hình cố
# định; children theo đúng 1 parent_hash) không cần vì không bao giờ chạm ngưỡng.


def _sb_select_all(build_query):
    """Chạy 1 PostgREST query, tự phân trang qua .range() cho tới khi hết dữ liệu thay vì gọi
    thẳng .execute() (xem _SB_PAGE_SIZE). build_query là callable KHÔNG tham số, mỗi lần gọi trả
    về 1 query builder MỚI (vd lambda: sb.table("work_calendar").select("start_time,title")) --
    dùng callable (không phải truyền thẳng 1 builder có sẵn) vì cần builder "sạch" cho mỗi trang,
    không có tài liệu nào của supabase-py đảm bảo gọi lại .range() trên 1 builder đã .execute()
    rồi là an toàn. Trả về list dict nối từ mọi trang -- giống hệt res.data nếu bảng vốn dưới
    ngưỡng (vòng lặp dừng ngay sau trang đầu)."""
    all_data = []
    offset = 0
    while True:
        page = build_query().range(offset, offset + _SB_PAGE_SIZE - 1).execute().data or []
        all_data.extend(page)
        if len(page) < _SB_PAGE_SIZE:
            break
        offset += _SB_PAGE_SIZE
    return all_data


def _fmt_ts(v):
    """Chuẩn hoá 1 giá trị giờ (chuỗi hoặc Timestamp, có/không giây lẻ) về đúng 1 định dạng
    cố định "YYYY-MM-DD HH:MM:SS" (bỏ giây lẻ) trước khi ghi vào Supabase -- các nguồn ghi
    khác nhau (nạp CSV mới cho ra Timestamp có giây lẻ, dữ liệu cũ đã là chuỗi không giây lẻ)
    nếu không chuẩn hoá sẽ lệch định dạng nhau, làm hỏng bước đọc lại (xem load_db)."""
    return pd.Timestamp(v).strftime("%Y-%m-%d %H:%M:%S")

@st.cache_data
def load_db():
    sb = _get_supabase()
    # order("id") -- .range() phân trang cần 1 thứ tự ỔN ĐỊNH giữa các trang (Postgres không đảm
    # bảo thứ tự trả về nếu không có ORDER BY), "id" là cột duy nhất chắc chắn không trùng.
    data = _sb_select_all(lambda: sb.table("sessions")
                           .select("id,start_time,end_time,project,duration_min").order("id"))
    cols = ["Thời gian bắt đầu", "Thời gian kết thúc", "Dự án", "Thời lượng (Phút)"]
    if not data:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data).rename(columns={
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

def _load_simple_table(table, select, rename, cols):
    """Khuôn đọc chung cho các bảng phẳng KHÔNG có bước chuẩn hoá kiểu dữ liệu riêng sau rename
    (không datetime, không astype) -- chỉ select -> đổi tên cột EN->VN -> DataFrame rỗng đúng
    cols nếu bảng trống. KHÔNG dùng chung được cho load_db/load_deleted/load_notes/... (có thêm
    bước chuẩn hoá chuỗi giờ ISO8601 hoặc parse datetime ngay sau rename, xem từng hàm đó).

    order() theo cột ĐẦU TIÊN trong select -- cả 3 nơi gọi hàm này (mapping/kindle_book_map/
    deleted_kindle_highlights) đều cố ý liệt kê khoá chính làm cột đầu, nên .range() phân trang
    (xem _sb_select_all()) có thứ tự ổn định giữa các trang mà không cần thêm tham số riêng."""
    sb = _get_supabase()
    order_col = select.split(',')[0].strip()
    data = _sb_select_all(lambda: sb.table(table).select(select).order(order_col))
    if not data:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(data).rename(columns=rename)[cols]

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
    return _load_simple_table("mapping", "project,category",
                               {"project": "Dự án", "category": "Danh mục"}, ["Dự án", "Danh mục"])

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
    data = _sb_select_all(lambda: sb.table("deleted_sessions")
                           .select("start_time,end_time").order("start_time").order("end_time"))
    cols = ["Thời gian bắt đầu", "Thời gian kết thúc"]
    if not data:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data).rename(columns={"start_time": "Thời gian bắt đầu", "end_time": "Thời gian kết thúc"})
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
    data = _sb_select_all(lambda: sb.table("notes").select("note_date,note").order("note_date"))
    cols = ["Ngày", "Ghi chú"]
    if not data:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(data).rename(columns={"note_date": "Ngày", "note": "Ghi chú"})[cols].astype(str)

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
    """Ghi chú nhanh -- "hộp thư nháp" trong ngày, ghi thẳng bởi Shortcut iOS qua REST API (KHÔNG
    qua app, xem chương "Trong ngày" của trang Trợ giúp). Không tự động gộp vào Ghi chú chính, nhưng có nút
    "Gộp" ở render_note_editor() để người dùng chủ động chọn lúc nào tổng hợp (xem docstring hàm
    đó) -- 2 bảng vẫn tách biệt, chỉ có 1 thao tác 1 chiều nối nội dung + xoá quick note gốc.
    ttl=30 (khác load_notes() cache vô hạn) vì bảng này có thể bị thay đổi từ NGOÀI vòng save_*/
    xoá của app -- vòng đó tự gọi st.cache_data.clear(), nhưng 1 INSERT từ Shortcut thì không, nên
    phải tự hết hạn theo thời gian để quick note mới hiện ra mà không cần chờ 1 thao tác lưu khác
    trong app."""
    sb = _get_supabase()
    data = _sb_select_all(lambda: sb.table("quick_notes").select("id,ts,note_text").order("ts").order("id"))
    cols = ["id", "Thời gian", "Nội dung"]
    if not data:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data).rename(columns={"ts": "Thời gian", "note_text": "Nội dung"})[cols]
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
    # order theo cả 2 cột khoá chính (uid, start_time) -- chỉ start_time không đủ (2 sự kiện khác
    # nhau vẫn có thể trùng giờ bắt đầu), .range() phân trang cần thứ tự ổn định tuyệt đối để
    # không lặp/sót dòng giữa các trang (đã xác nhận bug thật thiếu dòng khi bảng qua 1000 dòng,
    # xem _sb_select_all()).
    data = _sb_select_all(lambda: sb.table("work_calendar")
                           .select("start_time,title,uid").order("start_time").order("uid"))
    cols = ["Thời gian bắt đầu", "Tiêu đề"]
    if not data:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data).rename(columns={"start_time": "Thời gian bắt đầu", "title": "Tiêu đề"})
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
    # .order("completed_date").order("uid") ở PHÍA SUPABASE chỉ để .range() phân trang ổn định
    # (xem docstring _sb_select_all) -- KHÔNG dùng để quyết định thứ tự hiển thị cuối cùng, vì
    # "uid" (dạng "restored-N", sinh ở save_reading_log_bulk) là CHUỖI: PostgREST so chuỗi nên
    # "restored-10" < "restored-2", sai thứ tự đọc thật khi 1 ngày có ≥2 phần và tổng số dòng
    # ≥10 (bug thật đã gặp: 1 ngày đọc "Phần 5,6,7,8" hiện lệch thành "6,7,8,5"). Sắp lại đúng
    # bằng khoá SỐ tách từ uid ngay dưới đây, vì "Ngày hoàn thành" tự nó không đủ phân biệt thứ
    # tự trong ngày (Reminders chỉ ghi NGÀY hoàn thành, không có giờ -- xem docstring
    # _render_reading_kindle_days()).
    data = _sb_select_all(lambda: sb.table("reading_log")
                           .select("uid,completed_date,book,title").order("completed_date").order("uid"))
    cols = ["Ngày hoàn thành", "Sách (gốc)", "Tiêu đề phần"]
    if not data:
        return pd.DataFrame(columns=cols + ["Cuốn sách"])
    df = pd.DataFrame(data).rename(columns={
        "completed_date": "Ngày hoàn thành", "book": "Sách (gốc)", "title": "Tiêu đề phần"})
    df["Ngày hoàn thành"] = pd.to_datetime(df["Ngày hoàn thành"], format='ISO8601')
    df["_uid_n"] = df["uid"].astype(str).str.extract(r'(\d+)$')[0].astype(float)
    df = df.sort_values(["Ngày hoàn thành", "_uid_n"], kind="stable").drop(columns=["_uid_n", "uid"])
    df["Cuốn sách"] = df["Sách (gốc)"].map(_book_title)
    return df[cols + ["Cuốn sách"]].reset_index(drop=True)

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


# --- KINDLE: TRÍCH DẪN & GHI CHÚ (từ My Clippings.txt, xem parse_kindle_clippings) ---
# 2 bảng: kindle_highlights (từng đoạn highlight/note gốc) và kindle_book_map (ánh xạ tên sách
# GHI NGUYÊN VĂN trong Clippings.txt -> 1 Dự án đã có, hoặc để trống + tự đặt nhãn nếu là nguồn
# không thuộc Dự án nào, vd tạp chí The Economist -- xem UI xác nhận ở tab "Tải trích dẫn Kindle").
# kindle_book_map lưu 1 lần lúc xác nhận import, các lần sau tự nhớ, không hỏi lại cùng 1 tên sách.

def _kindle_dedupe_hash(kindle_title, location, content):
    """Băm (sách, vị trí, nội dung) làm khoá chống trùng -- Kindle luôn xuất TOÀN BỘ lịch sử cộng
    dồn mỗi lần export (không chỉ phần mới), nên import lặp lại nhiều lần (hoặc từ nhiều thiết bị
    Kindle khác nhau) phải tự nhận ra dòng đã có mà không cần so sánh gì khác ngoài chính nội dung
    -- tính lại được y hệt từ dữ liệu thô, không cần lưu/truyền riêng."""
    # pd.notna, KHÔNG "location or ''" -- float NaN (location thiếu, đọc từ DataFrame) là truthy
    # trong Python, "nan or ''" giữ nguyên NaN chứ không rơi về '' như None/0/'' vẫn làm.
    loc = str(location) if pd.notna(location) else ''
    raw = f"{kindle_title}|{loc}|{content}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


@st.cache_data
def load_kindle_book_map():
    return _load_simple_table(
        "kindle_book_map", "kindle_title,project,label",
        {"kindle_title": "Tên Kindle", "project": "Dự án", "label": "Nhãn"},
        ["Tên Kindle", "Dự án", "Nhãn"])


def save_kindle_book_map_upsert(df):
    """Upsert theo kindle_title -- KHÔNG xoá sạch trước như save_reading_log_bulk(), vì đây là
    bảng CỘNG DỒN theo thời gian (mỗi lần import chỉ thêm ánh xạ cho sách MỚI gặp lần đầu, sách cũ
    đã gán không được đụng tới)."""
    sb = _get_supabase()
    if not df.empty:
        recs = [{"kindle_title": str(r["Tên Kindle"]),
                 "project": (str(r["Dự án"]) if pd.notna(r.get("Dự án")) and str(r["Dự án"]).strip() else None),
                 "label": str(r["Nhãn"])} for r in df.to_dict("records")]
        sb.table("kindle_book_map").upsert(recs, on_conflict="kindle_title").execute()
    st.cache_data.clear()


@st.cache_data
def load_gundam_overrides():
    """Gán tay ngày -> series Gundam, ghi đè kết quả suy luận tự động của
    _assign_gundam_sessions() (nhóm mỗi ngày có phiên Forest tag GUNDAM_TAG với lần hoàn thành
    reminder GẦN NHẤT, có thể đoán sai nếu 2 series xem xen kẽ nhau) -- xem UI "Sửa gán series"
    ở trang Gundam. Khoá theo NGÀY (không phải từng phiên riêng) vì bản thân suy luận tự động
    cũng gán theo ngày, không theo từng phiên. Trả về dict {date: series} để tra cứu O(1)."""
    sb = _get_supabase()
    data = _sb_select_all(lambda: sb.table("gundam_overrides").select("session_date,series").order("session_date"))
    if not data:
        return {}
    return {pd.Timestamp(r["session_date"]).date(): r["series"] for r in data}


def save_gundam_override(day, series):
    """Gán tay 1 ngày cụ thể vào series (upsert theo session_date)."""
    _get_supabase().table("gundam_overrides").upsert(
        {"session_date": day.isoformat(), "series": series}, on_conflict="session_date").execute()
    st.cache_data.clear()


def delete_gundam_override(day):
    """Bỏ gán tay 1 ngày, quay lại dùng suy luận tự động."""
    _get_supabase().table("gundam_overrides").delete().eq("session_date", day.isoformat()).execute()
    st.cache_data.clear()


def save_gundam_overrides_bulk(df):
    """Ghi đè toàn bộ bảng gán tay (dùng khi Khôi phục từ bản sao lưu)."""
    sb = _get_supabase()
    _sb_delete_all("gundam_overrides", "session_date")
    if not df.empty:
        recs = [{"session_date": str(r["Ngày"]), "series": str(r["Series"])} for r in df.to_dict("records")]
        sb.table("gundam_overrides").insert(recs).execute()
    st.cache_data.clear()


@st.cache_data
def load_kindle_highlights():
    """Đọc kindle_highlights rồi JOIN với kindle_book_map để ra cột "Cuốn sách" hiển thị cuối
    cùng: sách đã gán Dự án -> dùng đúng tên Dự án đó (để nối được vào trang "Nhật ký đọc sách" ->
    Chi tiết); sách gán "nguồn độc lập" (Dự án để trống) -> dùng nhãn tự đặt lúc import; sách CHƯA
    qua bước xác nhận map (không có trong kindle_book_map, không nên xảy ra ở luồng bình thường vì
    UI luôn bắt xác nhận trước khi lưu) -> rơi về chính tên gốc trong Clippings.txt, phòng dữ liệu
    bất thường thay vì hiện trống/lỗi.

    Cột "dedupe_hash"/"parent_hash" giữ NGUYÊN VĂN tiếng Anh (không dịch như các cột khác) -- đây
    là khoá kỹ thuật để sửa/xoá/gắn ghi chú (xem update_kindle_highlight_content()/
    delete_kindle_highlight()/add_kindle_note()), không phải dữ liệu hiển thị cho người dùng.
    QUAN TRỌNG: sau khi có tính năng Sửa, dedupe_hash KHÔNG còn tính lại được từ (Tên Kindle, Vị
    trí, Nội dung) hiện tại nữa (nội dung có thể đã bị sửa khác bản gốc lúc băm) -- mọi thao tác
    sửa/xoá/gắn ghi chú PHẢI dùng đúng cột dedupe_hash đọc từ đây, không được gọi lại
    _kindle_dedupe_hash() để suy ngược khoá."""
    sb = _get_supabase()
    data = _sb_select_all(lambda: sb.table("kindle_highlights").select(
        "dedupe_hash,kindle_title,author,kind,content,location,added_at,parent_hash,is_favorite"
    ).order("dedupe_hash"))
    cols = ["Tên Kindle", "Tác giả", "Loại", "Nội dung", "Vị trí", "Ngày thêm", "Cuốn sách", "Dự án",
            "dedupe_hash", "parent_hash", "Yêu thích"]
    if not data:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data).rename(columns={
        "kindle_title": "Tên Kindle", "author": "Tác giả", "kind": "Loại",
        "content": "Nội dung", "location": "Vị trí", "added_at": "Ngày thêm", "is_favorite": "Yêu thích"})
    df["Ngày thêm"] = pd.to_datetime(df["Ngày thêm"], format='ISO8601', errors='coerce')
    df["Yêu thích"] = df["Yêu thích"].fillna(False).astype(bool)
    bm = load_kindle_book_map()
    bm_idx = bm.set_index("Tên Kindle")[["Dự án", "Nhãn"]] if not bm.empty else pd.DataFrame(columns=["Dự án", "Nhãn"])

    def _resolve(t):
        if t in bm_idx.index:
            proj, label = bm_idx.loc[t, "Dự án"], bm_idx.loc[t, "Nhãn"]
            proj = proj if pd.notna(proj) and str(proj).strip() else None
            return pd.Series({"Cuốn sách": proj or label, "Dự án": proj})
        return pd.Series({"Cuốn sách": t, "Dự án": None})

    df = df.join(df["Tên Kindle"].apply(_resolve))
    return df[cols]


def save_kindle_highlights_bulk(df):
    """Upsert theo dedupe_hash (tính từ Tên Kindle/Vị trí/Nội dung GỐC trong file -- đúng ngữ
    nghĩa vì hàm này CHỈ dùng cho luồng import, dữ liệu truyền vào luôn là nội dung thô mới đọc từ
    Clippings.txt, chưa qua sửa) -- KHÔNG xoá sạch trước như save_reading_log_bulk(), vì Kindle
    xuất TOÀN BỘ lịch sử cộng dồn mỗi lần export.

    ignore_duplicates=True (INSERT ... ON CONFLICT DO NOTHING, không phải UPDATE) CỐ Ý thay vì
    upsert thường: nếu 1 dedupe_hash đã tồn tại, dòng import KHÔNG được phép ghi đè nó -- đây
    chính là cơ chế giữ nguyên bản đã Sửa trong app khi tải lại file Clippings.txt cũ (dòng đó vẫn
    còn nguyên trong file gốc nên vẫn tính ra đúng hash cũ, nhưng phải bị bỏ qua thay vì ghi đè nội
    dung đã sửa). Dòng đã bị Xoá trong app (nằm trong deleted_kindle_highlights) phải được LỌC BỎ
    ở phía gọi (UI import) TRƯỚC KHI gọi hàm này -- ignore_duplicates chỉ chặn ghi đè, không chặn
    được việc chèn lại 1 dòng đã xoá hẳn (không còn trong kindle_highlights nên không đụng độ)."""
    sb = _get_supabase()
    if not df.empty:
        recs = [{
            "dedupe_hash": _kindle_dedupe_hash(r["Tên Kindle"], r.get("Vị trí"), r["Nội dung"]),
            "kindle_title": str(r["Tên Kindle"]),
            "author": (str(r["Tác giả"]) if pd.notna(r.get("Tác giả")) and str(r["Tác giả"]).strip() else None),
            "kind": str(r["Loại"]), "content": str(r["Nội dung"]),
            "location": (str(r["Vị trí"]) if pd.notna(r.get("Vị trí")) and str(r["Vị trí"]).strip() else None),
            "added_at": (_fmt_ts(r["Ngày thêm"]) if pd.notna(r.get("Ngày thêm")) else None),
            "parent_hash": None,  # import luôn là entry gốc Kindle, không phải ghi chú tự thêm trong app
        } for r in df.to_dict("records")]
        for i in range(0, len(recs), 500):
            sb.table("kindle_highlights").upsert(
                recs[i:i + 500], on_conflict="dedupe_hash", ignore_duplicates=True).execute()
    st.cache_data.clear()


def save_kindle_highlights_raw_bulk(df):
    """Ghi đè theo ĐÚNG dedupe_hash/parent_hash có sẵn trong df (cột lấy thẳng từ
    load_kindle_highlights(), KHÔNG tính lại từ nội dung) -- CHỈ dùng trong luồng Khôi phục từ bản
    sao lưu, khác save_kindle_highlights_bulk() (dùng cho import My Clippings.txt, ở đó bắt buộc
    TÍNH LẠI hash từ nội dung vì đang đọc file thô, y hệt lý do health_metrics cần 2 hàm ghi riêng
    -- xem data-layer.md). Nếu tính lại hash ở đây, trích dẫn đã Sửa nội dung trước khi sao lưu sẽ
    đổi sang hash MỚI khi khôi phục -- vừa làm gãy tham chiếu parent_hash của ghi chú con, vừa
    khiến lần import file Clippings.txt gốc tiếp theo không nhận ra dòng đó nữa (hash không khớp
    bản gốc), tạo trùng lặp. Gọi SAU khi caller đã _sb_delete_all("kindle_highlights", ...) --
    dùng insert() thẳng, không upsert."""
    sb = _get_supabase()
    if not df.empty:
        recs = [{
            "dedupe_hash": str(r["dedupe_hash"]), "kindle_title": str(r["Tên Kindle"]),
            "author": (str(r["Tác giả"]) if pd.notna(r.get("Tác giả")) and str(r["Tác giả"]).strip() else None),
            "kind": str(r["Loại"]), "content": str(r["Nội dung"]),
            "location": (str(r["Vị trí"]) if pd.notna(r.get("Vị trí")) and str(r["Vị trí"]).strip() else None),
            "added_at": (_fmt_ts(r["Ngày thêm"]) if pd.notna(r.get("Ngày thêm")) else None),
            "parent_hash": (str(r["parent_hash"]) if pd.notna(r.get("parent_hash")) and str(r["parent_hash"]).strip() else None),
            # .get() với mặc định "False" -- bản sao lưu cũ (trước khi có tính năng Yêu thích)
            # không có cột này trong CSV, phải rơi về false thay vì KeyError.
            "is_favorite": str(r.get("Yêu thích", "False")).strip().lower() == "true",
        } for r in df.to_dict("records")]
        for i in range(0, len(recs), 500):
            sb.table("kindle_highlights").insert(recs[i:i + 500]).execute()
    st.cache_data.clear()


def update_kindle_highlight_content(dedupe_hash, content):
    """Sửa nội dung 1 trích dẫn/ghi chú Kindle tại chỗ -- KHÔNG đổi dedupe_hash (khoá chính giữ
    nguyên, tính từ nội dung GỐC lúc tạo/import, không tính lại sau khi sửa). Bỏ qua nếu nội dung
    sau khi strip() rỗng -- không cho sửa thành trống (khác quy ước "sửa thành trống = xoá" của
    Ghi chú nhanh, vì ở đây đã có nút Xoá riêng, rõ ràng hơn là suy luận từ ô trống)."""
    content = content.strip()
    if not content:
        return
    sb = _get_supabase()
    sb.table("kindle_highlights").update({"content": content}).eq("dedupe_hash", dedupe_hash).execute()
    st.cache_data.clear()


def set_kindle_highlight_favorite(dedupe_hash, is_favorite):
    """Bật/tắt đánh dấu Yêu thích cho 1 trích dẫn/ghi chú Kindle -- nút ⭐ ở "Nhật ký đọc" và ở
    thẻ "Trích dẫn hôm nay" gọi thẳng hàm này. Không đụng dedupe_hash/nội dung, chỉ đổi 1 cột."""
    sb = _get_supabase()
    sb.table("kindle_highlights").update({"is_favorite": bool(is_favorite)}).eq("dedupe_hash", dedupe_hash).execute()
    st.cache_data.clear()


def delete_kindle_highlight(dedupe_hash):
    """Xoá 1 trích dẫn/ghi chú Kindle: xoá khỏi kindle_highlights + ghi vào sổ đen
    (deleted_kindle_highlights) để import lại file cũ (vẫn chứa đúng entry này) không hồi sinh nó.
    Cũng xoá + ghi sổ đen luôn các ghi chú BẠN TỰ THÊM gắn với đúng entry này (parent_hash) -- xoá
    quote gốc thì ghi chú trả lời nó không còn ý nghĩa đứng riêng. KHÔNG đụng tới note GỐC TỪ
    KINDLE chỉ đang được lồng hiển thị cạnh entry này qua khớp Vị trí (đó là suy luận HIỂN THỊ lúc
    render, không phải quan hệ cha-con lưu trong DB) -- xoá 1 highlight không kéo theo xoá note
    Kindle độc lập của chính bạn."""
    sb = _get_supabase()
    children = sb.table("kindle_highlights").select("dedupe_hash").eq("parent_hash", dedupe_hash).execute()
    hashes = [dedupe_hash] + [c["dedupe_hash"] for c in (children.data or [])]
    add_deleted_kindle(hashes)
    for h in hashes:
        sb.table("kindle_highlights").delete().eq("dedupe_hash", h).execute()
    st.cache_data.clear()


def add_kindle_note(parent_row, content):
    """Thêm 1 ghi chú CỦA BẠN, gắn với đúng 1 highlight/note đã có (parent_row -- 1 dòng lấy từ
    load_kindle_highlights()) qua parent_hash. Copy NGUYÊN "Vị trí"/"Ngày thêm" của parent thay vì
    dùng giờ hiện tại -- để ghi chú mới luôn rơi đúng vào cùng ngày với quote nó trả lời khi nhóm
    theo ngày trong "Nhật ký đọc" (xem _render_reading_kindle_days()), không bị tách sang ngày bạn
    tình cờ đang gõ ghi chú."""
    content = content.strip()
    if not content:
        return
    sb = _get_supabase()
    new_hash = _kindle_dedupe_hash(parent_row["Tên Kindle"], parent_row.get("Vị trí"), content)
    rec = {
        "dedupe_hash": new_hash, "kindle_title": str(parent_row["Tên Kindle"]),
        "author": (str(parent_row["Tác giả"]) if pd.notna(parent_row.get("Tác giả")) and str(parent_row["Tác giả"]).strip() else None),
        "kind": "note", "content": content,
        "location": (str(parent_row["Vị trí"]) if pd.notna(parent_row.get("Vị trí")) and str(parent_row["Vị trí"]).strip() else None),
        "added_at": (_fmt_ts(parent_row["Ngày thêm"]) if pd.notna(parent_row.get("Ngày thêm")) else None),
        "parent_hash": parent_row["dedupe_hash"],
    }
    sb.table("kindle_highlights").upsert([rec], on_conflict="dedupe_hash").execute()
    st.cache_data.clear()


@st.cache_data
def load_deleted_kindle():
    """Sổ đen dedupe_hash các trích dẫn/ghi chú Kindle đã xoá trong app -- xem delete_kindle_highlight()."""
    return _load_simple_table("deleted_kindle_highlights", "dedupe_hash", {}, ["dedupe_hash"])


def add_deleted_kindle(hashes):
    """Gộp thêm các dedupe_hash vào sổ đen (dùng khi xoá trích dẫn trong app)."""
    sb = _get_supabase()
    recs = [{"dedupe_hash": h} for h in hashes]
    if recs:
        sb.table("deleted_kindle_highlights").upsert(recs, on_conflict="dedupe_hash").execute()
    st.cache_data.clear()


def save_deleted_kindle(df):
    """Ghi đè toàn bộ sổ đen (dùng khi Khôi phục từ bản sao lưu)."""
    sb = _get_supabase()
    _sb_delete_all("deleted_kindle_highlights", "dedupe_hash")
    if not df.empty:
        recs = [{"dedupe_hash": str(h)} for h in df["dedupe_hash"]]
        for i in range(0, len(recs), 500):
            sb.table("deleted_kindle_highlights").insert(recs[i:i + 500]).execute()
    st.cache_data.clear()


def _kindle_location_sort_key(loc):
    """Số đầu tiên trong chuỗi "Vị trí" (vd "1832-1834" -> 1832, "trang 5" -> 5) để sắp quote
    theo đúng trình tự xuất hiện trong sách -- xem lý do chọn cách sắp này (thay vì kéo/thả tay)
    trong docstring _render_reading_kindle_days(). Rỗng/không parse được xếp CUỐI (không phải
    đầu), tránh đẩy quote thiếu dữ liệu lên trước quote có vị trí thật khi sort tăng dần."""
    m = re.search(r'\d+', str(loc)) if pd.notna(loc) else None
    return int(m.group()) if m else float('inf')


HEALTH_METRICS_COLS = ["id", "Ngày lấy mẫu", "Nhóm", "Chỉ số", "Giá trị", "Giá trị (gốc)",
                        "Đơn vị", "Khoảng tham chiếu", "Ref thấp", "Ref cao"]


def _backfill_ref_range(df):
    """Đồng bộ Khoảng tham chiếu của mỗi Chỉ số theo lần khám GẦN NHẤT có ghi nhận giá trị này --
    phiếu xét nghiệm cùng 1 chỉ số qua các lần khám thường lấy chung 1 khoảng tham chiếu (cùng
    máy/lab), lệch nhau chỉ là do cách ghi (thiếu hẳn, hoặc dấu cách khác nhau quanh dấu </≤) chứ
    không phải khoảng tham chiếu thật sự đổi -- áp GHI ĐÈ khoảng của lần gần nhất lên MỌI lần khám
    cũ hơn của cùng (Nhóm, Chỉ số), kể cả những lần đã có sẵn giá trị khác. Không đổi các cột khác
    (Giá trị/Giá trị gốc) -- chỉ chuẩn hoá 3 cột khoảng tham chiếu."""
    if df.empty:
        return df
    df = df.sort_values('Ngày lấy mẫu')
    # CHÚ Ý: không dùng groupby(...).apply(hàm trả nguyên group) -- pandas (>=2.2) âm thầm loại
    # bỏ chính các cột dùng làm khoá group ("Nhóm"/"Chỉ số") khỏi kết quả nối lại trong trường hợp
    # này, làm vỡ mọi chỗ đọc 2 cột đó sau đó (đã bắt lỗi này qua kiểm thử thật, không phải suy
    # đoán). Dùng tail(1) lấy đúng 1 dòng gần nhất có ref mỗi nhóm rồi merge lại là cách an toàn.
    has_ref = df.dropna(subset=['Ref thấp', 'Ref cao'], how='all')
    if has_ref.empty:
        return df
    latest_ref = has_ref.groupby(['Nhóm', 'Chỉ số']).tail(1)[
        ['Nhóm', 'Chỉ số', 'Khoảng tham chiếu', 'Ref thấp', 'Ref cao']]
    merged = df.drop(columns=['Khoảng tham chiếu', 'Ref thấp', 'Ref cao']).merge(
        latest_ref, on=['Nhóm', 'Chỉ số'], how='left')
    return merged[df.columns]


@st.cache_data
def load_health_metrics():
    """Đọc bảng health_metrics (chỉ số xét nghiệm máu định kỳ, xem tab "Sức khoẻ") -- dạng long
    format: mỗi dòng là 1 chỉ số của 1 lần xét nghiệm, không phải 1 cột/chỉ số. Khoảng tham chiếu
    được chuẩn hoá qua _backfill_ref_range() ngay khi đọc (xem docstring hàm đó) -- mọi nơi đọc từ
    hàm này (Báo cáo/Lịch sử/Dữ liệu đầu vào) đều thấy khoảng tham chiếu đã đồng bộ."""
    sb = _get_supabase()
    data = _sb_select_all(lambda: sb.table("health_metrics").select(
        "id,test_date,category,indicator,value,value_raw,unit,ref_raw,ref_low,ref_high"
    ).order("id"))
    if not data:
        return pd.DataFrame(columns=HEALTH_METRICS_COLS)
    df = pd.DataFrame(data).rename(columns={
        "test_date": "Ngày lấy mẫu", "category": "Nhóm", "indicator": "Chỉ số",
        "value": "Giá trị", "value_raw": "Giá trị (gốc)", "unit": "Đơn vị",
        "ref_raw": "Khoảng tham chiếu", "ref_low": "Ref thấp", "ref_high": "Ref cao"})
    df["Ngày lấy mẫu"] = pd.to_datetime(df["Ngày lấy mẫu"], format='ISO8601')
    return _backfill_ref_range(df[HEALTH_METRICS_COLS])


def _parse_ref_range(raw):
    """Parse chuỗi khoảng tham chiếu in trên phiếu xét nghiệm về (thấp, cao) dạng số -- dùng để
    tô vùng bình thường trên biểu đồ + phát hiện giá trị bất thường. Hỗ trợ các dạng thường gặp
    trên phiếu xét nghiệm: "a - b" (khoảng đủ), "< x"/"≤ x" (chỉ có trần trên), ">x"/"≥ x" (chỉ
    có sàn dưới). Trả (None, None) nếu không nhận dạng được (vd kết quả định tính "Âm tính") --
    không raise lỗi, vì không phải chỉ số nào cũng có khoảng tham chiếu dạng số."""
    if not raw:
        return None, None
    s = str(raw).strip().replace(",", ".")
    m = re.match(r'^[<≤]\s*([\d.]+)$', s)
    if m:
        return None, float(m.group(1))
    m = re.match(r'^[>≥]\s*([\d.]+)$', s)
    if m:
        return float(m.group(1)), None
    m = re.match(r'^([\d.]+)\s*-\s*([\d.]+)$', s)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


def _health_is_abnormal(df):
    """Chỉ số nào (theo df có cột 'Giá trị'/'Ref thấp'/'Ref cao', vd health_metrics hoặc lát cắt
    của nó) nằm ngoài khoảng tham chiếu -- logic DÙNG CHUNG cho biểu đồ theo dõi (Báo cáo), bảng
    Lịch sử, và view "Chỉ số bất thường" tổng quan, tránh lặp 3 lần cùng 1 điều kiện. Chỉ số
    không có 'Giá trị' dạng số (kết quả định tính) hoặc không có khoảng tham chiếu -> luôn False
    (không đánh giá được, không phải "bình thường")."""
    return ((df['Ref thấp'].notna() & (df['Giá trị'] < df['Ref thấp'])) |
            (df['Ref cao'].notna() & (df['Giá trị'] > df['Ref cao'])))


def _health_score(df_health):
    """(số chỉ số trong ngưỡng, tổng số chỉ số ĐÁNH GIÁ ĐƯỢC) -- mỗi Chỉ số tính theo giá trị GẦN
    NHẤT của riêng nó (không phải theo 1 lần khám cụ thể), vì 1 lần khám thường chỉ đo 1 phần các
    chỉ số (vd đợt này đo đường huyết, đợt trước đo mỡ máu) -- "Số sức khoẻ" ở billboard cần nhìn
    xuyên suốt MỌI Nhóm/Chỉ số đã từng theo dõi. Chỉ số không có giá trị số hoặc không có khoảng
    tham chiếu nào (không đánh giá được) bị loại khỏi CẢ tử số lẫn mẫu số, không tính là "bất
    thường" oan."""
    latest_per_ind = (df_health.sort_values('Ngày lấy mẫu')
                      .groupby(['Nhóm', 'Chỉ số'], as_index=False).last())
    evaluable = latest_per_ind[latest_per_ind['Giá trị'].notna() &
                                (latest_per_ind['Ref thấp'].notna() | latest_per_ind['Ref cao'].notna())]
    if evaluable.empty:
        return 0, 0
    return int((~_health_is_abnormal(evaluable)).sum()), len(evaluable)


def _health_trend_candidates(df_health, n=4):
    """Chọn tối đa n cặp (Nhóm, Chỉ số) để vẽ mini-card xu hướng (chương "Diễn biến chỉ số",
    _render_health_report()) -- ưu tiên Chỉ số ĐANG bất thường ở lần khám gần nhất (đáng theo dõi
    nhất), sau đó xếp theo số lần đo giảm dần (theo dõi đều/lâu mới đủ điểm vẽ xu hướng). Chỉ xét
    Chỉ số có >=2 giá trị SỐ -- ít hơn thì không có gì để vẽ xu hướng (1 điểm = 1 chấm, không phải
    đường/cột diễn biến)."""
    num = df_health[df_health['Giá trị'].notna()]
    counts = num.groupby(['Nhóm', 'Chỉ số']).size()
    candidates = list(counts[counts >= 2].index)
    if not candidates:
        return []
    latest_date = num['Ngày lấy mẫu'].max()
    latest_panel = num[num['Ngày lấy mẫu'] == latest_date]
    abn_keys = set()
    if not latest_panel.empty:
        abn_mask = _health_is_abnormal(latest_panel)
        abn_keys = set(zip(latest_panel.loc[abn_mask, 'Nhóm'], latest_panel.loc[abn_mask, 'Chỉ số']))
    candidates.sort(key=lambda k: (k not in abn_keys, -counts[k]))
    return candidates[:n]


def _health_trend_caption(vals, dates, ref_low, ref_high, unit):
    """1 câu ngắn tóm tắt xu hướng của 1 chỉ số qua các lần đo đang hiện trong mini-card (vd "Ngưỡng
    ≤ 5.2 — tăng dần 4 kỳ liên tiếp.", "Giảm đều −3.4 kg trong 21 tháng.", "dao động quanh ngưỡng,
    tăng lại kỳ này.") -- quy tắc đơn giản, KHÔNG suy luận xu hướng phức tạp (hồi quy, trung bình
    trượt...): vài điểm rời rạc mỗi vài tháng thì phép tính phức tạp cũng không đáng tin hơn so
    sánh đầu-cuối, mà lại khó hiểu hơn. Riêng trường hợp KHÔNG tăng/giảm đều (n>=3) -- vd
    462→430→418→445 -- so đầu-cuối đơn thuần sẽ ra "giảm" dù kỳ MỚI NHẤT vừa tăng lại, đọc vào dễ
    hiểu lầm là đang cải thiện; báo "dao động" + chiều đổi của riêng kỳ mới nhất trung thực hơn."""
    n = len(vals)
    if n < 2:
        return ""
    ref_txt = f"Ngưỡng ≤ {ref_high:g} — " if pd.notna(ref_high) else (
        f"Ngưỡng ≥ {ref_low:g} — " if pd.notna(ref_low) else "")
    delta = vals[-1] - vals[0]
    months = (dates[-1].year - dates[0].year) * 12 + (dates[-1].month - dates[0].month)
    span_txt = f"{months} tháng" if months >= 1 else f"{n} kỳ"
    increasing = all(vals[i] < vals[i + 1] for i in range(n - 1))
    decreasing = all(vals[i] > vals[i + 1] for i in range(n - 1))
    if abs(delta) < 1e-9:
        return f"{ref_txt}ổn định trong {span_txt}."
    if increasing and n >= 3:
        return f"{ref_txt}tăng dần {n} kỳ liên tiếp."
    if decreasing and n >= 3:
        return f"{ref_txt}giảm đều {abs(delta):.1f} {unit} trong {span_txt}.".replace("  ", " ")
    if n >= 3:
        last_delta = vals[-1] - vals[-2]
        if last_delta == 0:
            return f"{ref_txt}dao động quanh ngưỡng."
        return f"{ref_txt}dao động quanh ngưỡng, {'tăng' if last_delta > 0 else 'giảm'} lại kỳ này."
    verb = "tăng" if delta > 0 else "giảm"
    return f"{ref_txt}{verb} {abs(delta):.1f} {unit} trong {span_txt}.".replace("  ", " ")


def save_health_metrics_bulk(panels):
    """Ghi 1 hoặc nhiều "panel" xét nghiệm vào Supabase -- dùng chung cho cả form nhập nhanh lẫn
    import JSON hàng loạt. panels: list dict {"test_date", "category", "indicators": [{"indicator",
    "value_raw"/"value", "unit"?, "ref_raw"/"ref_range"?}, ...]}. Upsert theo khoá (test_date,
    category, indicator) nên sửa 1 chỉ số đã nhập chỉ cần gọi lại cùng khoá, không cần xoá tay
    trước (khác _sb_delete_all + insert lại như reading_log, vì ở đây ta muốn CỘNG DỒN qua nhiều
    lần nhập chứ không ghi đè toàn bảng mỗi lần lưu)."""
    sb = _get_supabase()
    recs = []
    for p in panels:
        category = str(p["category"]).strip()
        test_date = str(p["test_date"])
        for ind in p.get("indicators", []):
            name = str(ind.get("indicator", "")).strip()
            if not name:
                continue
            value_raw = str(ind.get("value_raw", ind.get("value", ""))).strip()
            value = pd.to_numeric(value_raw.replace(",", "."), errors="coerce")
            ref_raw = ind.get("ref_raw") or ind.get("ref_range") or None
            ref_low, ref_high = _parse_ref_range(ref_raw)
            recs.append({
                "test_date": test_date, "category": category, "indicator": name,
                "value": None if pd.isna(value) else float(value), "value_raw": value_raw,
                "unit": (str(ind["unit"]).strip() if ind.get("unit") else None),
                "ref_raw": ref_raw, "ref_low": ref_low, "ref_high": ref_high,
            })
    if recs:
        for i in range(0, len(recs), 500):
            sb.table("health_metrics").upsert(
                recs[i:i + 500], on_conflict="test_date,category,indicator").execute()
    st.cache_data.clear()


def delete_health_metric_panel(test_date, category):
    """Xoá toàn bộ 1 lần xét nghiệm (mọi chỉ số cùng ngày lấy mẫu + nhóm)."""
    sb = _get_supabase()
    sb.table("health_metrics").delete().eq("test_date", str(test_date)).eq("category", category).execute()
    st.cache_data.clear()


def save_health_metrics_raw_bulk(df):
    """Ghi đè TOÀN BỘ bảng health_metrics từ 1 DataFrame đúng khuôn HEALTH_METRICS_COLS -- dùng
    RIÊNG cho luồng Khôi phục từ bản sao lưu (khác save_health_metrics_bulk là upsert cộng dồn
    dùng cho nhập liệu thường ngày). Y hệt kiểu save_db()/save_reading_log_bulk(): xoá sạch rồi
    chèn lại nguyên trạng, đúng ngữ nghĩa "khôi phục về đúng mốc đã sao lưu"."""
    sb = _get_supabase()
    _sb_delete_all("health_metrics", "id")
    if not df.empty:
        recs = [{
            "test_date": str(pd.Timestamp(r["Ngày lấy mẫu"]).date()), "category": str(r["Nhóm"]),
            "indicator": str(r["Chỉ số"]), "value": None if pd.isna(r["Giá trị"]) else float(r["Giá trị"]),
            "value_raw": str(r["Giá trị (gốc)"]) if pd.notna(r["Giá trị (gốc)"]) else "",
            "unit": (str(r["Đơn vị"]) if pd.notna(r["Đơn vị"]) else None),
            "ref_raw": (str(r["Khoảng tham chiếu"]) if pd.notna(r["Khoảng tham chiếu"]) else None),
            "ref_low": None if pd.isna(r["Ref thấp"]) else float(r["Ref thấp"]),
            "ref_high": None if pd.isna(r["Ref cao"]) else float(r["Ref cao"]),
        } for r in df.to_dict("records")]
        for i in range(0, len(recs), 500):
            sb.table("health_metrics").insert(recs[i:i + 500]).execute()
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


def parse_kindle_clippings(raw):
    """Đọc "My Clippings.txt" (định dạng xuất mặc định của mọi Kindle, xem "Cách xuất Clippings"
    trong tab Hướng dẫn) -- mỗi entry cách nhau bởi 1 dòng đúng 10 dấu "=", gồm: dòng 1 "Tên sách
    (Tác giả)", dòng 2 metadata "- Your Highlight/Note/Bookmark on page X | location Y | Added on
    <ngày giờ>", 1 dòng trống, rồi nội dung (rỗng với Bookmark). Bookmark KHÔNG có nội dung nên bị
    bỏ qua hoàn toàn -- không có gì để hiện làm quote/note. Trả về (df, stats):
    df cột (Tên Kindle, Tác giả, Loại, Nội dung, Vị trí, Ngày thêm); stats = {'raw', 'valid',
    'bookmarks', 'invalid'}."""
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8-sig', errors='replace')
    else:
        raw = raw.lstrip('﻿')
    blocks = [b.strip('\r\n') for b in re.split(r'\r?\n={10}\r?\n?', raw) if b.strip()]
    rows = []
    n_bookmark = n_invalid = 0
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 2:
            n_invalid += 1
            continue
        title_line, meta_line = lines[0].strip(), lines[1].strip()
        content = "\n".join(lines[2:]).strip()
        m = re.match(r'^(.*)\s+\(([^()]+)\)\s*$', title_line)
        title, author = (m.group(1).strip(), m.group(2).strip()) if m else (title_line, None)
        meta_low = meta_line.lower()
        kind = ('highlight' if 'highlight' in meta_low else 'note' if 'note' in meta_low
                else 'bookmark' if 'bookmark' in meta_low else None)
        if kind is None:
            n_invalid += 1
            continue
        if kind == 'bookmark':
            n_bookmark += 1
            continue
        if not content:
            n_invalid += 1
            continue
        loc_m = re.search(r'location\s+([\d\-]+)', meta_line, re.IGNORECASE)
        page_m = re.search(r'page\s+([\d\-]+)', meta_line, re.IGNORECASE)
        location = loc_m.group(1) if loc_m else (f"trang {page_m.group(1)}" if page_m else None)
        added_m = re.search(r'Added on (.+?)$', meta_line, re.IGNORECASE)
        added_at = pd.to_datetime(added_m.group(1), errors='coerce') if added_m else pd.NaT
        rows.append({'Tên Kindle': title, 'Tác giả': author, 'Loại': kind, 'Nội dung': content,
                     'Vị trí': location, 'Ngày thêm': added_at})
    cols = ['Tên Kindle', 'Tác giả', 'Loại', 'Nội dung', 'Vị trí', 'Ngày thêm']
    df = pd.DataFrame(rows, columns=cols)
    df, n_pen_merged = _collapse_kindle_pen_duplicates(df)
    stats = {'raw': len(blocks), 'valid': len(df), 'bookmarks': n_bookmark, 'invalid': n_invalid,
             'pen_merged': n_pen_merged}
    return df, stats


def _collapse_kindle_pen_duplicates(df):
    """Gộp các highlight "nháp" do tô bằng bút cảm ứng (không phải chọn từ nhanh) sinh ra: Kindle
    ghi lại MỖI LẦN đầu bút dịch chuyển như 1 highlight riêng trong My Clippings.txt, cách nhau vài
    giây, nội dung câu sau luôn là PHẦN MỞ RỘNG (tiền tố + thêm chữ) của câu trước -- chỉ có bản
    CUỐI CÙNG (dài/đầy đủ nhất) mới là highlight thật người dùng muốn giữ, 3-4 bản trước chỉ là
    trạng thái trung gian lúc đang kéo bút. Heuristic: cùng sách + cùng Loại 'highlight' + cách
    nhau tối đa 120 giây + nội dung bản trước là TIỀN TỐ (sau khi rstrip khoảng trắng) của bản sau
    -> coi là 1 chuỗi nháp, chỉ giữ bản dài nhất (luôn là bản cuối chuỗi trong thực tế, nhưng lấy
    max() để chắc chắn không phụ thuộc thứ tự). Ghi chú (Loại 'note') KHÔNG áp dụng -- gõ tay 1 lần
    rồi lưu, không có kiểu nháp tăng dần này. Trả về (df đã gộp, số dòng đã bỏ vì là bản nháp)."""
    if df.empty:
        return df, 0
    keep_mask = pd.Series(True, index=df.index)

    def _flush(cluster):
        if len(cluster) < 2:
            return
        longest = max(cluster, key=lambda i: len(str(df.loc[i, 'Nội dung'])))
        for i in cluster:
            if i != longest:
                keep_mask.loc[i] = False

    for _title, g in df[df['Loại'] == 'highlight'].groupby('Tên Kindle'):
        g = g.sort_values('Ngày thêm', kind='stable')
        cluster = []  # index list của chuỗi nháp đang gộp
        prev_i = None
        for i, row in g.iterrows():
            if prev_i is None:
                cluster = [i]
            else:
                prev_row = df.loc[prev_i]
                gap_ok = (pd.notna(row['Ngày thêm']) and pd.notna(prev_row['Ngày thêm'])
                          and (row['Ngày thêm'] - prev_row['Ngày thêm']).total_seconds() <= 120)
                is_extension = str(row['Nội dung']).startswith(str(prev_row['Nội dung']).rstrip())
                if gap_ok and is_extension:
                    cluster.append(i)
                else:
                    _flush(cluster)
                    cluster = [i]
            prev_i = i
        _flush(cluster)
    n_dropped = int((~keep_mask).sum())
    return df[keep_mask].reset_index(drop=True), n_dropped


def _fuzzy_match_project(title, projects):
    """Gợi ý Dự án khớp gần đúng nhất với tên sách Kindle (Kindle thường ghi kèm phụ đề/dấu câu
    khác với tên Dự án Forest tự đặt tay) -- dùng difflib (đủ tốt cho vài chục Dự án, không cần
    thêm thư viện fuzzy ngoài chỉ cho 1 tính năng phụ này). Trả None nếu độ khớp dưới ngưỡng, coi
    như không có gợi ý đáng tin -- người dùng vẫn tự chọn tay được trong UI xác nhận."""
    if not projects:
        return None
    match = difflib.get_close_matches(title, projects, n=1, cutoff=0.55)
    return match[0] if match else None


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
    fig.add_trace(go.Scatter(
        x=totals[x_col], y=totals[y_col], mode='text', text=totals[y_col].map(_fmt_hours_short),
        textposition='top center', showlegend=False, hoverinfo='skip', textfont=dict(color=PLOT_TEXT, size=13)
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
        line=dict(color=PLOT_TEXT, width=2.5, dash='dot'),
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
        # customdata: chuỗi "X giờ Y phút" đã format sẵn -- hovertemplate của Plotly chỉ hỗ trợ
        # d3-format cho %{value}, không tự tách giờ/phút được, nên phải tính trước ở Python.
        for tr in fig.data:
            if tr.values is not None:
                tr.customdata = [[_fmt_hours_long(v)] for v in tr.values]
        fig.update_traces(marker=dict(line=dict(color=_pie_line, width=2)),
                          hovertemplate='<b>%{label}</b><br>%{customdata[0]}<extra></extra>')
    else:
        for tr in fig.data:
            if tr.y is not None:
                tr.customdata = [[_fmt_hours_long(v)] for v in tr.y]
        fig.update_traces(hovertemplate='<b>%{data.name}</b><br>%{customdata[0]}<extra></extra>')
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
    rl = st.segmented_control(label, list(RANGE_OPTS.keys()), default="90 ngày", key=key,
                               label_visibility="collapsed")
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
    năm 2 số (vd 'Th1 ’26') để không nhầm giữa các kỳ trùng số nhưng khác năm."""
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
            _inject_date_picker_locale()
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


def _inject_date_picker_locale():
    """Dịch tháng/thứ trong popup lịch của MỌI st.date_input trên trang sang tiếng Việt bằng JS
    phía trình duyệt -- component BaseWeb bên trong Streamlit không có prop locale lộ ra qua API
    Python (`format=` của st.date_input chỉ đổi định dạng Ô NHẬP TAY, không đụng tới popup lịch),
    nên phải dịch text SAU KHI mount. Popup mount dạng portal ở <body> của trang cha (ngoài mọi
    iframe component, xem comment CSS `[data-baseweb="calendar"]`), không phải trong DOM con của
    component này -- giống hệt cách _inject_relative_time_ticker() ở trên phải quẫy sang
    window.parent.document để chạm được DOM thật.

    Dùng MutationObserver theo dõi window.parent.document.body: mỗi khi popup lịch mở/đổi tháng
    (React re-render lại text bên trong), duyệt lại toàn bộ text node trong `[data-baseweb=
    "calendar"]` rồi thay theo 2 bảng tra VN_MONTHS/VN_DAYS_ABBR (khớp đúng chuỗi, không đoán mò
    bằng regex tách từ -- an toàn hơn khi BaseWeb đổi định dạng header giữa các bản Streamlit).
    Chỉ cần gọi 1 lần cho cả trang (không phải 1 lần mỗi date_input) vì observer theo dõi chung
    toàn bộ <body>."""
    _months_js = json.dumps(VN_MONTHS, ensure_ascii=False)
    _days_js = json.dumps(VN_DAYS_ABBR, ensure_ascii=False)
    js = (
        "<script>\n"
        "(function(){\n"
        f"  const MONTHS = {_months_js};\n"
        f"  const DAYS = {_days_js};\n"
        "  const MONTH_RE = new RegExp('\\\\b(' + Object.keys(MONTHS).join('|') + ')\\\\b', 'g');\n"
        "  function translateNode(node){\n"
        "    for (const child of node.childNodes){\n"
        "      if (child.nodeType === 3){\n"
        "        const t = child.textContent;\n"
        "        const trimmed = t.trim();\n"
        "        if (DAYS[trimmed]){\n"
        "          child.textContent = t.replace(trimmed, DAYS[trimmed]);\n"
        "        } else if (MONTH_RE.test(trimmed)){\n"
        "          MONTH_RE.lastIndex = 0;\n"
        "          child.textContent = t.replace(MONTH_RE, m => MONTHS[m]);\n"
        "        }\n"
        "      } else if (child.nodeType === 1){\n"
        "        translateNode(child);\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "  function run(){\n"
        "    const cals = window.parent.document.querySelectorAll('[data-baseweb=\"calendar\"]');\n"
        "    cals.forEach(translateNode);\n"
        "  }\n"
        "  run();\n"
        "  const obs = new MutationObserver(run);\n"
        "  obs.observe(window.parent.document.body, {childList: true, subtree: true, characterData: true});\n"
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


def _fmt_hours_short(v):
    """Số giờ thập phân (vd 1.5) -> dạng gọn 'XhYYp' cho chỗ hẹp (chip/badge/ô bảng/nhãn biểu
    đồ): 1.5 -> '1h30p', 0.5 -> '30p', 2.0 -> '2h', 0 -> '0p'. Làm tròn tới phút gần nhất, bỏ
    hẳn phần giờ/phút nếu bằng 0 thay vì hiện '0h'/'00p' thừa."""
    total_min = max(round(v * 60), 0)
    h, m = divmod(total_min, 60)
    if h and m:
        return f"{h}h{m:02d}p"
    if h:
        return f"{h}h"
    return f"{m}p"


def _fmt_hours_long(v):
    """Bản đầy đủ của _fmt_hours_short cho chỗ rộng rãi (câu văn, tooltip): 1.5 -> '1 giờ 30
    phút', 0.5 -> '30 phút', 2.0 -> '2 giờ'."""
    total_min = max(round(v * 60), 0)
    h, m = divmod(total_min, 60)
    if h and m:
        return f"{h} giờ {m} phút"
    if h:
        return f"{h} giờ"
    return f"{m} phút"


def _fmt_hours_delta(v):
    """Bản có dấu +/- của _fmt_hours_short cho chênh lệch SỐ GIỜ (vd '+1h30p', '-45p') thay vì
    số thập phân '+1.5'/'−0.8'."""
    sign = "+" if v >= 0 else "-"
    return f"{sign}{_fmt_hours_short(abs(v))}"


def _delta_t_hours(delta, label):
    """Biến thể _delta_t dành riêng cho chênh lệch SỐ GIỜ -- hiện '+1h30p'/'-45p' thay vì số
    thập phân '+1.5'/'−0.8'."""
    if delta is None:
        return None
    c = "#34c759" if delta > 0 else "#ff3b30" if delta < 0 else "#86868b"
    return (f"{_fmt_hours_delta(delta)} {label}", c)


def _period_elapsed_context(selected_key, current_key, pos_series, today_pos, noun):
    """Gộp logic lặp lại 3 lần ở nhánh Tuần/Tháng/Năm (Báo cáo): nếu kỳ đang chọn CHƯA kết thúc
    (đang là kỳ hiện tại), trả elapsed_mask cắt cả 2 baseline so sánh theo đúng phần đã trôi qua
    (vd "2 ngày đầu tuần") + nhãn ngắn tương ứng, dùng cho _period_comparison() và
    _render_period_overview_hero(). Kỳ đã khép hẳn (không phải kỳ hiện tại) -> mask=None,
    _period_comparison() tự so full-vs-full như hành vi gốc. pos_series/today_pos: vị trí trong
    kỳ (vd dayofweek+1/day/dayofyear) của df và của hôm nay -- do CALLER tính (khác nhau theo
    Tuần/Tháng/Năm), hàm này chỉ so sánh <= today_pos, không tự suy ra cách tính vị trí."""
    lbl_prev, lbl_avg = f"vs {noun} trước", "vs Trung bình"
    if selected_key != current_key:
        return None, lbl_prev, lbl_avg, None
    clip_note = f"So sánh chỉ tính {today_pos} ngày đầu của {noun} trước/các {noun.lower()} khác cho công bằng."
    return pos_series <= today_pos, lbl_prev, lbl_avg, clip_note


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
        return _fmt_hours_short(v)

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


def render_stat_panel(hero_items, sections=None, footer=None, groups=None, card_style="padding:18px;"):
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
            wsuf = f" <span style='color:{ACCENT}; font-size:13px;'>({_fmt_hours_short(wh)} tuần này)</span>" if wh > 0.05 else ""
            html_list += f"<li><span style='font-weight:600;'>{html_escape(str(k))}</span>: {_fmt_hours_short(v/60)}{wsuf}</li>"
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

def _avg_session_min(df):
    """Độ dài bình quân mỗi phiên (phút); 0 nếu chưa có phiên."""
    n = len(df)
    return (df['Thời lượng (Phút)'].sum() / n) if n else 0.0

def render_session_bar(df):
    """Thanh phân bố độ dài phiên theo 4 nhóm (mốc 25/50/90) — gọn cho phần Tổng quan. Có nhãn nhỏ
    "Phân bổ độ dài phiên" riêng (đồng bộ với nhãn "Dòng thời gian trong ngày" của
    render_day_timeline) -- thiếu nhãn khiến khối này trông trống trải, không rõ đang xem gì nếu
    tách rời khỏi ngữ cảnh xung quanh (áp dụng chung cho MỌI nơi gọi hàm này, không riêng Hôm nay)."""
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
        "<div class='glass-card' style='padding:14px 18px;margin-top:14px;'>"
        "<span class='rl-book'>Phân bổ độ dài phiên</span>"
        f"<div style='display:flex;height:26px;border-radius:6px;overflow:hidden;'>{seg}</div>"
        f"<div style='margin-top:12px;'>{legend}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

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
        # annotation_position="bottom left" (không phải "top left") -- nhãn buổi đặt SÁT ĐÁY dải
        # màu, tránh đụng độ với legend nằm NGAY TRÊN đỉnh biểu đồ (format_plotly_fig() đặt legend
        # ở y=1.02, quá gần đỉnh vùng vẽ để còn chỗ cho nhãn "top" không bị đè/chen chúc).
        fig.add_vrect(x0=lo, x1=hi, fillcolor=col, opacity=1, layer="below", line_width=0,
                      annotation_text=name.strip(), annotation_position="bottom left",
                      annotation=dict(font_size=11, font_color="#9a9aa0"))

    y_max = float(tot.max()) or 1.0
    fig.update_layout(xaxis_title=x_title, yaxis_title="Trung bình giờ/ngày",
                      yaxis=dict(range=[0, y_max * 1.28]),
                      xaxis=dict(range=[-PAD, 23 + PAD], dtick=2))
    fig = format_plotly_fig(fig)
    fig.update_traces(hovertemplate='<b>%{data.name}</b><br>%{customdata[0]}/ngày<extra></extra>')
    st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)


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
    return [{"k": f"#{it['rank']}", "v": f"{it['date']:%d/%m/%Y} · {_fmt_hours_short(it['hours'])}"} for it in items]


def _top_days_section(df_scope, label, n=3):
    """1 section "Ngày nổi bật" cho render_stat_panel() (sections=...), hoặc None nếu kỳ chưa
    có ngày nào -- dùng chung ở Bảng số liệu Tuần/Tháng/Năm (Tổng quan tự truyền thẳng
    overall_top3 vì đã tính sẵn cho mục "Kỷ lục" nên không gọi lại _top_days() ở đây)."""
    items = _top_days(df_scope, n)
    return [{"label": label, "chips": _top_days_chips(items)}] if items else None


def _render_period_overview_hero(df_period, full_df, period_col, selected_key, prev, avg,
                                  lbl_prev, lbl_avg, clip_note, top_days_label, show_top3,
                                  anchor_prefix, top3_suffix="", show_footer=True):
    """Chương "Tổng quan" (mục 1) ở Báo cáo -> Tuần/Tháng/Năm: 5 hero item (Tổng thời gian/
    Thời gian mỗi ngày/Số cây/Số cây mỗi ngày/Thời gian mỗi phiên), mỗi item tối đa 2 delta (vs
    kỳ trước, vs trung bình) + "Ngày nổi bật" + biểu đồ cột phiên + Top 3 (tuỳ chọn, Tuần không
    có -- xác nhận không cần ở quy mô 1 tuần, xem show_top3=False ở nơi gọi cho Tuần).

    Trước đây đây là 3 bản GẦN NHƯ Y HỆT (closure _hd_w/_hd_m/_hd_y trong 3 nhánh Tuần/Tháng/Năm
    của "Báo cáo", chỉ khác hậu tố biến) -- gộp lại còn 1 bản, tham số hoá đúng phần THỰC SỰ khác
    nhau giữa 3 kỳ (nhãn delta, dòng "kỳ chưa kết thúc" clip_note, có Top3 hay không). period_col
    ('Tuần'/'Tháng'/'Năm') PHẢI khớp đúng cột `_period_comparison()` đã dùng để tính prev/avg --
    dùng làm period_col cho _smart_digest() luôn, không tính lại; cũng dùng làm kicker của chương.
    anchor_prefix ('bc-tuan'/'bc-thang'/'bc-nam') -- tự vẽ chương "1. Tổng quan" (sec_chapter),
    không còn nhận expander đã mở sẵn từ caller như bản cũ (xem CLAUDE.md mục bố cục "chương").

    show_footer=False (Tuần/Tháng/Năm) -- billboard riêng của từng trang (render_period_billboard)
    đã có câu nhận định tự tính bao gồm đúng nội dung của _smart_digest (so kỳ trước) ở cột phải,
    dòng "nhận xét" cuối thẻ ở đây thành thừa/lặp lại nếu giữ cả 2."""
    sec_chapter(f"{anchor_prefix}-ch1", 1, None, "Tổng quan", tight_top=True)
    curr_hrs = df_period['Thời lượng (Phút)'].sum() / 60
    curr_trees = len(df_period)
    num_days = df_period['Ngày'].nunique() or 1
    curr_hrs_day = curr_hrs / num_days
    curr_trees_day = curr_trees / num_days
    curr_min_sess = _avg_session_min(df_period)

    def _hd(cur_v, key):
        d1 = (cur_v - prev[key]) if prev and prev.get(key) is not None else None
        d2 = (cur_v - avg[key]) if avg and avg.get(key) is not None else None
        return d1, d2

    d1_hr, d2_hr = _hd(curr_hrs, "hrs")
    d1_hrd, d2_hrd = _hd(curr_hrs_day, "hrs_day")
    d1_tr, d2_tr = _hd(curr_trees, "trees")
    d1_trd, d2_trd = _hd(curr_trees_day, "trees_day")
    d1_ms, d2_ms = _hd(curr_min_sess, "min_sess")

    if clip_note:
        _clip_card(clip_note)
    render_stat_panel(hero_items=[
        {"label": "Tổng thời gian", "value": _fmt_hours_short(curr_hrs),
         "deltas": [d for d in [_delta_t_hours(d1_hr, lbl_prev), _delta_t_hours(d2_hr, lbl_avg)] if d]},
        {"label": "Thời gian / ngày", "value": _fmt_hours_short(curr_hrs_day),
         "deltas": [d for d in [_delta_t_hours(d1_hrd, lbl_prev), _delta_t_hours(d2_hrd, lbl_avg)] if d]},
        {"label": "Số cây đã trồng", "value": f"{curr_trees}",
         "deltas": [d for d in [_delta_t(d1_tr, f"cây {lbl_prev}"), _delta_t(d2_tr, f"cây {lbl_avg}")] if d]},
        {"label": "Số cây / ngày", "value": f"{curr_trees_day:.1f}",
         "deltas": [d for d in [_delta_t(d1_trd, f"cây {lbl_prev}"), _delta_t(d2_trd, f"cây {lbl_avg}")] if d]},
        {"label": "Thời gian / phiên", "value": f"{curr_min_sess:.0f} phút",
         "deltas": [d for d in [_delta_t(d1_ms, f"phút {lbl_prev}"), _delta_t(d2_ms, f"phút {lbl_avg}")] if d]},
    ], sections=_top_days_section(df_period, top_days_label),
        footer=_smart_digest(full_df, period_col, selected_key, df_period, prev, avg, clip_note is not None)
        if show_footer else None)
    render_session_bar(df_period)
    if show_top3:
        st.write("")
        c_top1, c_top2 = st.columns(2)
        with c_top1: render_top_3(df_period, 'Danh mục', f'Top 3 Danh mục{top3_suffix}')
        with c_top2: render_top_3(df_period, 'Dự án', f'Top 3 Dự án{top3_suffix}')


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


def _mi(name, size=13):
    """1 icon Material Symbols Rounded chèn thẳng vào chuỗi HTML tĩnh (KHÔNG qua tham số
    icon=":material/x:" của widget Streamlit, vì đây là text HTML thô render bằng
    unsafe_allow_html) -- span tự khai font-family riêng, không cần nhúng thêm font nào (Streamlit
    đã tự load sẵn font này cho icon :material/x: của chính nó, xem CSS `.jchip.rec::before`).
    Dùng thay EMOJI ở mọi nhãn/câu mới thêm (vd "🏆 Tuần kỷ lục" -> "{_mi('emoji_events')} Tuần kỷ
    lục") để đồng bộ với quy ước icon Material đã có sẵn trong app, không lẫn 2 kiểu icon."""
    return (f"<span style=\"font-family:'Material Symbols Rounded';font-size:{size}px;"
            f"vertical-align:-2px;\">{name}</span>")


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


def _assign_gundam_sessions(gundam_sessions, rl_gundam, overrides=None):
    """Gán mỗi phiên Forest tag GUNDAM_TAG vào đúng series đang xem hôm đó -- Forest không có
    Dự án riêng theo từng series Gundam, chỉ 1 tag chung, nên phải suy ra. Quy tắc: mỗi ngày có
    phiên Gundam, tìm lần hoàn thành reminder (ở BẤT KỲ series nào) GẦN NHẤT về mặt thời gian
    (trước hoặc sau ngày đó) trong rl_gundam, gán cả ngày đó cho series của lần hoàn thành gần
    nhất -- dùng pd.merge_asof(direction='nearest') có sẵn trong pandas. Trả về df cùng khuôn
    cột với gundam_sessions, cột 'Dự án' được GHI ĐÈ thành tên series suy ra được.

    overrides: dict {date: series} từ load_gundam_overrides() -- ngày nào có trong đây thì dùng
    series gán TAY, GHI ĐÈ lên kết quả suy luận tự động (xem UI "Sửa gán series" ở trang Gundam,
    dành cho trường hợp 2 series xem xen kẽ khiến suy luận theo "lần hoàn thành gần nhất" đoán
    sai)."""
    if gundam_sessions.empty or rl_gundam.empty:
        return gundam_sessions.iloc[0:0]
    # .astype('datetime64[ns]') ép cả 2 vế về CÙNG độ chính xác -- pandas >=3 coi datetime64[s]
    # (từ .dt.normalize()) và datetime64[us]/[ns] (từ pd.to_datetime trên cột date) là 2 kiểu
    # khác nhau, merge_asof() sẽ ném MergeError nếu lệch nhau, không tự nới lỏng như trước.
    marks = (rl_gundam.sort_values('Ngày hoàn thành', kind='stable')
             .assign(_d=lambda d: d['Ngày hoàn thành'].dt.normalize().astype('datetime64[ns]'))
             .drop_duplicates('_d', keep='first')[['_d', 'Cuốn sách']]
             .sort_values('_d'))
    left = gundam_sessions.assign(
        _d=pd.to_datetime(gundam_sessions['Ngày']).astype('datetime64[ns]')).sort_values('_d')
    merged = pd.merge_asof(left, marks, on='_d', direction='nearest')
    merged['Dự án'] = merged['Cuốn sách']
    if overrides:
        _ov = merged['_d'].dt.date.map(overrides)
        merged['Dự án'] = _ov.combine_first(merged['Dự án'])
    return merged.drop(columns=['_d', 'Cuốn sách'])


def _render_gundam_series_override(gundam_sessions, rl_gundam, gundam_df, gundam_overrides):
    """"Sửa gán series tự động" -- chỉ có ý nghĩa khi có TỪ 2 series trở lên (1 series duy nhất
    thì suy luận "lần hoàn thành gần nhất" không thể sai). Không đánh số (mục điều kiện, cùng
    tiền lệ "Nhật ký đọc" ở Báo cáo -> Dự án) và mặc định đóng vì hiếm khi cần tới. CHỈ gọi từ
    sub-tab "Tổng quan" (qua extra_overview= của render_reading_log()) -- không lặp lại ở "Chi
    tiết", phản hồi thực tế là 1 nơi (Tổng quan) đã đủ, không cần thấy 2 lần."""
    _series_opts = sorted(rl_gundam['Cuốn sách'].unique()) if not rl_gundam.empty else []
    if len(_series_opts) <= 1 or gundam_sessions.empty:
        return
    with st.expander("Sửa gán series tự động", expanded=False):
        st.caption(
            "Forest chỉ có 1 tag \"Gundam\" chung, không phân biệt series -- mỗi ngày có "
            "phiên Gundam được tự động gán vào series có lần hoàn thành gần nhất trên "
            "Reminders. Nếu 2 series xem xen kẽ nhau, suy luận này có thể đoán sai; sửa "
            "lại đúng series cho ngày đó rồi bấm Lưu."
        )
        _auto_df = _assign_gundam_sessions(gundam_sessions, rl_gundam)  # KHÔNG override, để so sánh
        _auto_by_day = dict(zip(_auto_df['Ngày'], _auto_df['Dự án']))
        _by_day = (gundam_df.groupby('Ngày')
                   .agg(Giờ=('Thời lượng (Phút)', lambda s: round(s.sum() / 60, 1)),
                        Series=('Dự án', 'first'))
                   .reset_index().sort_values('Ngày', ascending=False))
        _by_day['Gán tay'] = _by_day['Ngày'].isin(gundam_overrides.keys())
        edited_gu = st.data_editor(
            _by_day, hide_index=True, width='stretch', key="gundam_override_editor",
            column_config={
                "Ngày": st.column_config.DateColumn("Ngày", format="DD/MM/YYYY", disabled=True),
                "Giờ": st.column_config.NumberColumn("Giờ", disabled=True),
                "Series": st.column_config.SelectboxColumn("Series", options=_series_opts),
                "Gán tay": st.column_config.CheckboxColumn("Gán tay", disabled=True,
                                                            help="Ngày này đang dùng series gán tay, khác kết quả suy luận tự động"),
            })
        if st.button("Lưu gán series", type="primary", key="tbtn_gundam_override_save"):
            for _, r in edited_gu.iterrows():
                _day, _series = r["Ngày"], r["Series"]
                if _series == _auto_by_day.get(_day):
                    if _day in gundam_overrides:
                        delete_gundam_override(_day)
                else:
                    save_gundam_override(_day, _series)
            st.success("Đã lưu gán series.")
            time.sleep(1)
            st.rerun()


def _render_kindle_favorites_tab():
    """Sub-tab "Yêu thích" (trang Sách, không có ở Gundam -- xem show_favorites ở render_reading_log()):
    duyệt lại mọi trích dẫn/ghi chú Kindle đã đánh dấu ⭐, gộp theo cuốn sách. Đây thuần là 1 cách
    LỌC khác của cùng bảng kindle_highlights (Yêu thích == True), không phải dữ liệu riêng -- tái
    dùng NGUYÊN _render_kindle_quote_row() (cùng Sửa/Xoá/+ Ghi chú/⭐) để sửa/bỏ đánh dấu được
    thẳng tại đây, không cần quay lại "2. Nhật ký đọc" của đúng cuốn đó.

    Thêm 3 bộ lọc/sắp xếp (theo mockup): ô tìm theo nội dung trích dẫn, sắp xếp Mới lưu nhất/Cũ
    nhất (theo "Ngày thêm" -- mốc lưu vào Yêu thích, DÙNG CHUNG với show_added_date ở
    _render_kindle_quote_row(), KHÔNG phải "Vị trí" Kindle như "2. Nhật ký đọc"), và chip lọc theo
    cuốn sách (st.segmented_control, đếm số trích dẫn không đổi theo ô tìm để nhãn chip ổn định
    giữa các lần rerun). Sách nhiều hơn 3 cuốn thu gọn còn 3 cuốn đầu (theo đúng thứ tự sắp xếp
    đang chọn), có nút "Hiện thêm" mở hết -- trạng thái mở lưu ở session_state, KHÔNG reset khi đổi
    tìm/sắp xếp/lọc để tránh giật khi người dùng đang duyệt."""
    kh = load_kindle_highlights()
    favs = kh[kh['Yêu thích']] if not kh.empty else kh
    if favs.empty:
        st.info("Chưa có trích dẫn nào được đánh dấu Yêu thích — bấm ⭐ trên 1 trích dẫn ở mục "
                "\"2. Nhật ký đọc\" (tab Chi tiết) hoặc trên thẻ \"Trích dẫn hôm nay\" ở trang Hôm "
                "nay để lưu lại đây, thỉnh thoảng mở ra đọc lại cho vui.")
        return

    fcol1, fcol2 = st.columns([2, 1])
    with fcol1:
        search = st.text_input("Tìm trong trích dẫn đã lưu", key="fav_search",
                                placeholder="Tìm theo nội dung trích dẫn...")
    with fcol2:
        sort_label = st.selectbox("Sắp xếp", ["Mới lưu nhất", "Cũ nhất"], key="fav_sort")

    book_counts = favs.groupby('Cuốn sách').size()
    chip_opts = [f"Tất cả · {len(favs)}"] + [f"{b} · {n}" for b, n in book_counts.items()]
    chip_pick = st.segmented_control("Lọc theo sách", chip_opts, default=chip_opts[0],
                                      key="fav_book_filter", label_visibility="collapsed")

    view = favs
    if search.strip():
        view = view[view['Nội dung'].str.contains(search.strip(), case=False, na=False)]
    if chip_pick and not chip_pick.startswith("Tất cả · "):
        view = view[view['Cuốn sách'] == chip_pick.rsplit(" · ", 1)[0]]
    if view.empty:
        st.info("Không có trích dẫn nào khớp bộ lọc hiện tại.")
        return

    ascending = (sort_label == "Cũ nhất")
    book_order = (view.groupby('Cuốn sách')['Ngày thêm'].agg('min' if ascending else 'max')
                  .sort_values(ascending=ascending, kind='stable').index.tolist())

    show_more_key = "fav_show_all_books"
    show_all = st.session_state.get(show_more_key, False)
    visible_books = book_order if show_all else book_order[:3]
    hidden_books = [] if show_all else book_order[3:]

    for i, book in enumerate(visible_books):
        grp = view[view['Cuốn sách'] == book]
        author = _reading_author_of(kh, book)
        _mt = "0" if i == 0 else "26px"
        st.markdown(
            f"<div class='fav-book-head' style='margin-top:{_mt}'>"
            f"<div class='fav-book-titles'><span class='pbill-booktitle'>{html_escape(str(book))}</span>"
            + (f"<span class='pbill-author'>{html_escape(str(author))}</span>" if author else "")
            + f"</div><span class='fav-count-badge'>{len(grp)}</span></div>",
            unsafe_allow_html=True)
        for _, r in grp.sort_values('Ngày thêm', ascending=ascending, kind='stable').iterrows():
            _render_kindle_quote_row(r, is_reply=False, key_suffix="fav_", show_added_date=True)

    if hidden_books:
        hidden_n = sum(len(view[view['Cuốn sách'] == b]) for b in hidden_books)
        if st.button(f"Hiện thêm {len(hidden_books)} cuốn · {hidden_n} trích dẫn",
                      key="fav_show_more_btn"):
            st.session_state[show_more_key] = True
            st.rerun()


def render_reading_log(df_books, latest_overall, reading_log_df, recency_days=14, labels=READING_LABELS,
                        show_favorites=True, extra_overview=None):
    """Bảng + timeline + tóm tắt cho từng cuốn sách (đọc tuần tự), GỘP 2 nguồn: phiên Forest
    (nhóm Danh mục = Reading) và phần đã đọc đồng bộ từ Apple Reminders (reading_log_df). Một
    cuốn sách chỉ cần có mặt ở MỘT trong 2 nguồn là đủ để lên bảng -- cột thuộc nguồn còn thiếu
    hiện '—'. Trạng thái Đang đọc/Đã xong dựa trên hoạt động GẦN NHẤT của CẢ 2 nguồn (lấy max
    của ngày phiên Forest gần nhất và ngày hoàn thành reminder gần nhất).
    Chỉ đọc & tính toán -> không đụng tới dữ liệu lưu trữ.

    Dùng chung cho tab "Nhật ký đọc sách" (labels=READING_LABELS, mặc định) và tab "Gundam"
    (labels=GUNDAM_LABELS) -- chỉ khác CHỮ hiển thị, tên cột nội bộ (vd 'Cuốn sách', 'Trạng
    thái') giữ nguyên bất kể labels nào đang dùng.

    show_favorites=False ở trang Gundam (xem nơi gọi) -- sub-tab "Yêu thích" duyệt lại trích dẫn
    Kindle đã đánh dấu ⭐, chỉ có ý nghĩa cho SÁCH (trích dẫn gắn với nội dung sách, không áp dụng
    cho việc xem Gundam).

    extra_overview: callable tuỳ chọn, gọi thêm SAU nội dung chính của sub-tab "Tổng quan" (bên
    trong đúng `with _tab_overview:`) -- dùng cho "Sửa gán series tự động" ở trang Gundam, mục này
    chỉ nên hiện ở Tổng quan (nơi thấy cả bảng series), không cần lặp lại ở Chi tiết. Đặt PARAM ở
    đây thay vì gọi rời sau render_reading_log() ở nơi gọi vì code cũ gọi rời sẽ nằm NGOÀI mọi
    st.tabs() -> hiện cố định dưới cả 2 tab bất kể đang xem tab nào."""
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
            'Phần gần nhất': r.sort_values('Ngày hoàn thành', kind='stable').iloc[-1]['Tiêu đề phần'] if has_rl else None,
            'Trạng thái': labels['ongoing'] if ongoing else 'Đã xong',
        })
    t = pd.DataFrame(rows).sort_values('Bắt đầu').reset_index(drop=True)

    done = t[t['Trạng thái'] == 'Đã xong']
    reading = t[t['Trạng thái'] == labels['ongoing']]

    # Số liệu đầu mục: panel thẻ giống "Tổng quan", chia 3 nhóm dọc
    _today = _today_vn()
    s_read = _streak_stats(df_books)

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

    # Nhóm 1 · Tổng kết: thống kê theo đầu cuốn. done['Tổng giờ']/['Số ngày'] có thể TOÀN NaN
    # (mọi sách "Đã xong" trong kỳ đều chỉ theo dõi qua Reminders, không có phiên Forest nào)
    # -> idxmax()/idxmin() lỗi ValueError trên cột toàn NaN, phải kiểm tra .notna().any() trước.
    _grp_summary = []
    if len(done):
        _has_hrs = done['Tổng giờ'].notna().any()
        _has_days = done['Số ngày'].notna().any()
        _chips_done = [{"k": labels['count_label'], "v": f"{len(done)}"}]
        if _has_hrs:
            _chips_done.append({"k": labels['avg_hr_label'], "v": f"{_fmt_hours_short(done['Tổng giờ'].mean())}"})
        if _has_days:
            _chips_done.append({"k": labels['avg_days_label'], "v": f"{done['Số ngày'].mean():.0f}"})
        _grp_summary.append({"label": "Đã xong", "chips": _chips_done})
        _highlight = []
        if _has_hrs:
            top = done.loc[done['Tổng giờ'].idxmax()]
            _highlight.append({"k": "Nhiều giờ nhất", "v": f"{top['Cuốn sách']} ({_fmt_hours_short(top['Tổng giờ'])})"})
        if _has_days:
            fast = done.loc[done['Số ngày'].idxmin()]
            _highlight.append({"k": labels['fastest_label'], "v": f"{fast['Cuốn sách']} ({int(fast['Số ngày'])} ngày)"})
        if _highlight:
            _grp_summary.append({"label": "Nổi bật", "chips": _highlight})
    if len(reading):
        _grp_summary.append({"label": labels['ongoing'], "chips": [
            {"k": r['Cuốn sách'],
             "v": f"{_fmt_hours_short(r['Tổng giờ'])}" if pd.notna(r['Tổng giờ']) else f"{int(r['Số phần đã đọc'])} {labels['part_word']}",
             "hl": True}
            for _, r in reading.iterrows()
        ]})

    # Key riêng theo show_favorites (không dùng chung 1 key cho Sách/Gundam như trước) -- Sách có
    # 3 tab, Gundam chỉ 2, dùng chung key cho 2 bộ tab khác số lượng dễ vỡ trạng thái tab đang chọn
    # khi chuyển qua lại giữa 2 trang. Thứ tự Tổng quan -> Yêu thích -> Chi tiết (Yêu thích đứng
    # trước Chi tiết theo yêu cầu -- tab hay ghé lại (Yêu thích) gần đầu hơn tab tra cứu sâu 1 cuốn
    # cụ thể (Chi tiết), chỉ Sách mới có Yêu thích nên Gundam không đổi thứ tự 2 tab của mình).
    _tab_labels = [":material/bar_chart: Tổng quan"]
    if show_favorites:
        _tab_labels.append(":material/star: Yêu thích")
    _tab_labels.append(":material/search: Chi tiết")
    _tabs = st.tabs(_tab_labels, key="rl_view_tabs" if show_favorites else "rl_view_tabs_gd")
    _tab_overview = _tabs[0]
    if show_favorites:
        _tab_favorites, _tab_detail = _tabs[1], _tabs[2]
    else:
        _tab_detail = _tabs[1]

    # Tên trang cho hero -- chỉ Sách mới có Yêu thích (show_favorites) nên dùng luôn cờ đó để suy
    # ra thay vì thêm 1 tham số page_name riêng trùng lặp thông tin.
    _page_name = "Sách" if show_favorites else "Gundam"

    with _tab_overview:
        _render_reading_overview(t, df_books, _grp_summary, s_read, _span, _pace,
                                  _today, labels, _page_name, reading_log_df)
        if extra_overview is not None:
            extra_overview()

    if show_favorites:
        with _tab_favorites:
            _render_kindle_favorites_tab()

    with _tab_detail:
        _render_reading_detail(t, reading_log_df, labels, _page_name, df_books)


def _reading_author_of(kh_all, book):
    """Tác giả 1 cuốn/series, tra qua trích dẫn Kindle đã gắn đúng "Cuốn sách" này (cột "Tác giả"
    lấy từ metadata Kindle lúc import) -- None nếu chưa có trích dẫn nào (sách chỉ theo dõi qua
    Forest/Reminders, chưa import Kindle) hoặc "Tác giả" rỗng. Dùng chung cho billboard Tổng quan/
    Chi tiết."""
    if kh_all.empty:
        return None
    m = kh_all[kh_all['Cuốn sách'] == book]['Tác giả'].dropna()
    return m.iloc[0] if len(m) else None


def _rel_day_label(d, today):
    """Nhãn ngày tương đối gọn cho chip billboard Sách ("Hôm nay"/"Hôm qua"/"N ngày trước"/
    "dd/mm" khi đã xa) -- dùng chung cho billboard Tổng quan (_render_reading_billboard) và Chi
    tiết (_render_reading_detail)."""
    delta = (today - pd.Timestamp(d).date()).days
    if delta == 0:
        return "Hôm nay"
    if delta == 1:
        return "Hôm qua"
    if delta < 7:
        return f"{delta} ngày trước"
    return f"{pd.Timestamp(d):%d/%m}"


def _render_reading_billboard(t, df_books, today):
    """Billboard mở đầu Sách -> Tổng quan (render_period_billboard()): số cuốn đã đọc xong TRONG
    NĂM bên trái + sách đang đọc chính (hoạt động gần nhất) bên phải -- đang đọc song song (nếu
    có), "đã đọc N phần" (KHÔNG có mẫu số tổng số chương/phần cả cuốn -- dữ liệu Reminders chỉ ghi
    phần ĐÃ xong, không có tổng số, xác nhận với người dùng bỏ hẳn thanh tiến độ dạng phân số thay
    vì suy đoán hay thêm 1 input nhập tay hoàn toàn mới), phần đọc gần nhất + số trích dẫn đã lưu.
    KHÔNG có đánh giá sao -- xác nhận với người dùng giữ nguyên quyết định "Không cần" đã chốt
    trước đó, mockup có thêm nhưng không áp dụng."""
    kh_all = load_kindle_highlights()
    done_year = t[(t['Trạng thái'] == 'Đã xong') & (pd.to_datetime(t['Gần nhất']).dt.year == today.year)]
    reading_now = t[t['Trạng thái'] == 'Đang đọc'].sort_values('Gần nhất', ascending=False)
    hrs_year = df_books[pd.to_datetime(df_books['Ngày']).dt.year == today.year]['Thời lượng (Phút)'].sum() / 60

    if len(reading_now):
        primary = reading_now.iloc[0]
        book = str(primary['Cuốn sách'])
        author = _reading_author_of(kh_all, book)
        _author_html = f" <span class='pbill-author'>· {html_escape(str(author))}</span>" if author else ""
        chips = []
        if pd.notna(primary['Số phần đã đọc']) and primary['Số phần đã đọc'] > 0:
            chips.append(f"<span class='chip'><span class='ck'>Đã đọc</span>"
                          f"<span class='cv'>{int(primary['Số phần đã đọc'])} phần</span></span>")
        if len(reading_now) > 1:
            other = reading_now.iloc[1]
            _part = f" · {html_escape(str(other['Phần gần nhất']))}" if pd.notna(other['Phần gần nhất']) else ""
            chips.append(f"<span class='chip'><span class='ck'>Cùng lúc</span>"
                          f"<span class='cv'>{html_escape(str(other['Cuốn sách']))}{_part}</span></span>")
        _last_day = pd.Timestamp(primary['Gần nhất'])
        _day_mins = df_books[(df_books['Dự án'] == book) & (df_books['Ngày'] == _last_day.date())]['Thời lượng (Phút)'].sum()
        _dur = f" · {int(_day_mins)}′" if _day_mins > 0 else ""
        chips.append(f"<span class='chip'><span class='ck'>Phần đọc gần nhất</span>"
                      f"<span class='cv'>{_rel_day_label(_last_day, today)}{_dur}</span></span>")
        _n_quotes = len(kh_all[(kh_all['Cuốn sách'] == book) & (kh_all['Loại'] == 'highlight')]) if not kh_all.empty else 0
        if _n_quotes:
            chips.append(f"<span class='chip tw'><span class='cv'>{_n_quotes} trích dẫn đã lưu</span></span>")
        _right = ("<div class='pbill-kicker'>Đang đọc</div>"
                  f"<div class='pbill-booktitle'>{html_escape(book)}{_author_html}</div>"
                  f"<div class='pbill-chips'>{''.join(chips)}</div>")
    else:
        _right = ("<div class='pbill-kicker'>Đang đọc</div>"
                   "<div class='pbill-booktitle'>Chưa có cuốn nào đang đọc dở</div>")

    render_period_billboard(
        f"Tủ sách {today.year}", f"{len(done_year)}", "cuốn đã đọc xong",
        f"{len(reading_now)} đang đọc · {_fmt_hours_short(hrs_year)} đọc năm nay",
        _right,
        [("sach-tq-ch1", "1 · Thống kê"), ("sach-tq-ch2", "2 · Nhật ký đọc"),
         ("sach-tq-ch3", "3 · Trích dẫn & Ghi chú"), ("sach-tq-ch4", "4 · Bảng số liệu")])


def _render_gundam_billboard(t, df_books, reading_log_df, today):
    """Billboard mở đầu Gundam -> Tổng quan (render_period_billboard()), theo mockup Forest
    Dashboard.dc.html ("Phòng chiếu"): số tập ĐÃ XEM của series đang xem bên trái (KHÔNG có mẫu
    số/thanh % -- cùng lý do đã chốt ở billboard Sách, dữ liệu Reminders không có tổng số tập cả
    series, xác nhận với người dùng không thêm bảng nhập tay riêng chỉ để có mẫu số) + series
    đang xem bên phải. Khác billboard Sách (đã xác nhận với người dùng khi làm chương này):
    - KHÔNG có chip "Tiếp theo · Tập N" -- mockup có nhưng đòi suy số tập kế tiếp bằng regex tách
      số cuối trong tiêu đề tự do rồi +1, dễ sai nếu tiêu đề không theo khuôn "Tập N" (vd tên tập
      không có số, hoặc 1 dòng gộp nhiều tập như "Tập 19 – 21") -- bỏ hẳn thay vì suy đoán sai.
    - KHÔNG có đánh giá sao -- không có nguồn dữ liệu nào (cùng quyết định đã chốt ở Sách).
    - Có thêm chip "Nhịp xem" (~N tập/tuần, đếm số lần hoàn thành trong 30 ngày gần nhất của đúng
      series đang xem) -- Sách không có chip tương đương vì đơn vị "phần" đọc sách không đều nhịp
      như 1 tập phim, ít có ý nghĩa để đếm tốc độ theo tuần."""
    reading_now = t[t['Trạng thái'] == 'Đang xem'].sort_values('Gần nhất', ascending=False)
    done_all = t[t['Trạng thái'] == 'Đã xong']
    hrs_all = df_books['Thời lượng (Phút)'].sum() / 60 if not df_books.empty else 0.0

    if len(reading_now):
        primary = reading_now.iloc[0]
        series = str(primary['Cuốn sách'])
        chips = []
        if pd.notna(primary['Số phần đã đọc']) and primary['Số phần đã đọc'] > 0:
            chips.append(f"<span class='chip'><span class='ck'>Đã xem</span>"
                          f"<span class='cv'>{int(primary['Số phần đã đọc'])} tập</span></span>")
        if len(reading_now) > 1:
            other = reading_now.iloc[1]
            chips.append(f"<span class='chip'><span class='ck'>Cùng lúc</span>"
                          f"<span class='cv'>{html_escape(str(other['Cuốn sách']))}</span></span>")
        _last_day = pd.Timestamp(primary['Gần nhất'])
        _rl_series = (reading_log_df[reading_log_df['Cuốn sách'] == series]
                      if not reading_log_df.empty else reading_log_df)
        _n_that_day = len(_rl_series[_rl_series['Ngày hoàn thành'].dt.normalize() == _last_day.normalize()])
        _cnt_s = f" · {_n_that_day} tập" if _n_that_day > 0 else ""
        chips.append(f"<span class='chip'><span class='ck'>Lần xem gần nhất</span>"
                      f"<span class='cv'>{_rel_day_label(_last_day, today)}{_cnt_s}</span></span>")
        _recent = (_rl_series[_rl_series['Ngày hoàn thành'] >= pd.Timestamp(today - timedelta(days=29))]
                   if not _rl_series.empty else _rl_series)
        if len(_recent):
            chips.append(f"<span class='chip'><span class='ck'>Nhịp xem</span>"
                          f"<span class='cv'>~{len(_recent) / (30 / 7):.0f} tập/tuần</span></span>")
        _right = ("<div class='pbill-kicker'>Đang xem</div>"
                  f"<div class='pbill-booktitle'>{html_escape(series)}</div>"
                  f"<div class='pbill-chips'>{''.join(chips)}</div>")
        _big_num = f"{int(primary['Số phần đã đọc'])}" if pd.notna(primary['Số phần đã đọc']) else "0"
    else:
        _right = ("<div class='pbill-kicker'>Đang xem</div>"
                  "<div class='pbill-booktitle'>Chưa có series nào đang xem dở</div>")
        _big_num = "0"

    render_period_billboard(
        "Phòng chiếu", _big_num, "tập đã xem",
        f"{len(done_all)} series đã xem xong · {_fmt_hours_short(hrs_all)} đã xem",
        _right,
        [("gd-tq-ch1", "1 · Thống kê"), ("gd-tq-ch2", "2 · Nhật ký xem"),
         ("gd-tq-ch3", "3 · Bảng số liệu")])


def _render_reading_quotes_teaser(n=3):
    """Chương "Trích dẫn & Ghi chú" (Sách -> Tổng quan): N trích dẫn gần đây nhất (mọi cuốn), kèm
    ghi chú cá nhân lồng dưới nếu có (parent_hash trỏ về, xem add_kindle_note()) -- bản CHỈ ĐỌC
    (không Sửa/Xoá/+ Ghi chú như _render_kindle_day_quotes() ở tab Chi tiết -- tránh trùng key
    widget khi cùng 1 trích dẫn render ở cả 2 nơi cùng lúc)."""
    kh_all = load_kindle_highlights()
    highlights = (kh_all[kh_all['Loại'] == 'highlight'].sort_values('Ngày thêm', ascending=False).head(n)
                  if not kh_all.empty else kh_all)
    if highlights.empty:
        st.caption("Chưa có trích dẫn nào.")
        return
    rows_html = ''
    for _, r in highlights.iterrows():
        notes = kh_all[(kh_all['Loại'] == 'note') & (kh_all['parent_hash'] == r['dedupe_hash'])]
        note_html = ''
        if len(notes):
            note_html = f"<div class='quote-note'>✎ {html_escape(str(notes.iloc[0]['Nội dung']))}</div>"
        rows_html += (
            "<div class='quote-item'>"
            f"<div class='quote-text'>&ldquo;{html_escape(str(r['Nội dung']))} "
            f"<span class='quote-meta'>Vị trí {html_escape(str(r['Vị trí']))} · {html_escape(str(r['Cuốn sách']))}</span></div>"
            f"{note_html}</div>")
    st.markdown(f"<div class='quotes-card'>{rows_html}</div>", unsafe_allow_html=True)


def _render_reading_overview(t, df_books, _grp_summary, s_read, _span, _pace,
                              _today, labels, page_name, reading_log_df):
    """Sub-tab "Tổng quan" của render_reading_log(): 2 thẻ hero/nhóm chip + thanh phân bổ +
    bảng "Chi tiết từng cuốn" tổng hợp toàn bộ đầu cuốn/series. Không có expander nào ở đây
    (đã flat sẵn từ trước). Đã bỏ hẳn thẻ "Kỳ này" (Tháng này/Tuần này/Khung giờ đọc) -- xác nhận
    với người dùng không cần thiết, cũng bỏ luôn _period_chips()/_sec_timeslot() ở render_reading_log
    (chỉ dùng riêng cho thẻ đó, không còn nơi gọi nào khác).

    page_name == "Sách": thêm billboard (_render_reading_billboard) + chương mới (Nhật ký đọc/
    Trích dẫn & Ghi chú, theo mockup Forest Dashboard.dc.html) -- 2 thẻ hero/nhóm chip cũ GIỮ
    NGUYÊN thành chương "1. Thống kê" đứng NGAY DƯỚI billboard, bảng chi tiết cũ TÁCH RIÊNG thành
    chương cuối "4. Bảng số liệu" kèm cột "Trích dẫn" mới (theo thứ tự: Thống kê -> Nhật ký đọc ->
    Trích dẫn & Ghi chú -> Bảng số liệu). Đã BỎ chương "Tủ sách năm nay" (mockup ban đầu có, người
    dùng xem lại thấy trùng lặp thông tin theo-đầu-sách với Bảng số liệu -- dồn cột "Trích dẫn"
    của nó sang bảng chi tiết cho gọn, xem show_quotes=True). Tách vào 2 closure
    _render_stats_cards()/_render_stats_table() để dùng lại được CẢ CHO GUNDAM.

    page_name == "Gundam": billboard riêng (_render_gundam_billboard, "Phòng chiếu") + 3 chương
    Thống kê/Nhật ký xem/Bảng số liệu -- mockup Gundam gốc chỉ có 2 chương ("Nhật ký xem"/"Hành
    trình các series") nhưng bảng "Hành trình các series" đó dựa vào mẫu số tổng số tập + đánh giá
    sao mà dữ liệu hiện có không có (xem docstring _render_gundam_billboard), sau khi bỏ 2 thứ đó
    bảng gần như trùng hệt _render_stats_table() sẵn có -- xác nhận với người dùng dùng khung 3
    chương giống hệt Sách (Thống kê/Nhật ký xem/Bảng số liệu) thay vì dựng 1 bảng mới gần trùng
    lặp. "Nhật ký xem" tái dùng nguyên _reading_rows_html() (cùng cơ chế "Nhật ký đọc" của Sách,
    lọc theo reading_log_df đã là rl_gundam sẵn -- không cần lọc lại theo _is_gundam_list)."""
    def _render_stats_cards():
        # Thẻ 1: hero + Tổng kết (theo đầu cuốn)
        render_stat_panel(
            hero_items=[
                {"label": labels['count_label'], "value": f"{len(t)}"},
                {"label": "Tổng giờ", "value": f"{_fmt_hours_short(t['Tổng giờ'].sum())}"},
                {"label": labels['parts_label'], "value": f"{int(t['Số phần đã đọc'].fillna(0).sum())}"},
            ],
            sections=_grp_summary,
        )

        # Thẻ 2: Hoạt động — thẻ độc lập, tách khỏi thẻ trên
        render_stat_panel(
            hero_items=[],
            sections=[
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
                    {"k": "7 ngày", "v": f"{_fmt_hours_short(_pace(7))}/ngày"},
                    {"k": "30 ngày", "v": f"{_fmt_hours_short(_pace(30))}/ngày"},
                ]},
            ],
            card_style="padding:18px;margin-top:14px;",
        )

        render_session_bar(df_books)

    def _render_stats_table(show_quotes=False):
        # Bảng số liệu: dùng cùng style (DTBL) với mục cuối "Bảng số liệu". Cột thuộc nguồn Forest
        # (Số ngày/Ngày đọc/Tổng giờ/Số phiên/Giờ tuần) hoặc nguồn Reminders (Số phần đã đọc/Phần
        # gần nhất) có thể NaN nếu sách đó chỉ có 1 trong 2 nguồn -- hiện '—' thay vì để lọt "nan"
        # ra HTML (đặc biệt _heat_cell KHÔNG tự bắt được NaN, phải bọc rõ ràng trước khi gọi).
        # show_quotes=True (chỉ Sách -- Gundam không có khái niệm trích dẫn) -- thêm cột "Trích
        # dẫn" (số highlight Kindle đã lưu cho đúng cuốn đó) thay cho chương "Tủ sách năm nay" đã
        # bỏ (người dùng thấy 2 nơi cùng liệt kê theo đầu sách là dư, gộp lại đây cho gọn).
        def _c(v, fmt='{:.0f}'):
            return fmt.format(v) if pd.notna(v) else '—'

        kh_all = load_kindle_highlights() if show_quotes else None
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
            if show_quotes:
                _nq = (len(kh_all[(kh_all['Cuốn sách'] == r['Cuốn sách']) & (kh_all['Loại'] == 'highlight')])
                       if not kh_all.empty else 0)
                rows_html += f'<td>{_nq}</td>'
            rows_html += f'<td class="txt" style="color:{s_col};font-weight:600;">{r["Trạng thái"]}</td>'
            rows_html += '</tr>'
        _quote_th = '<th>Trích dẫn</th>' if show_quotes else ''
        st.markdown(DTBL_CSS + f"""
<div class="dtbl-wrap" style="margin-top:14px;">
<table class="dtbl">
<thead><tr><th class="lbl">{labels['item_col']}</th><th>Bắt đầu</th><th>Gần nhất</th><th>Số ngày</th><th>{labels['days_label']}</th><th>Tổng giờ</th><th>Số phiên</th><th>Giờ/tuần</th><th>{labels['parts_label']}</th><th class="txt">{labels['part_recent_label']}</th>{_quote_th}<th class="txt">Trạng thái</th></tr></thead>
<tbody>{rows_html}</tbody>
</table></div>
""", unsafe_allow_html=True)

    if page_name == "Gundam":
        _render_gundam_billboard(t, df_books, reading_log_df, _today)
        sec_chapter("gd-tq-ch1", 1, None, "Thống kê", tight_top=True)
        _render_stats_cards()
        sec_chapter("gd-tq-ch2", 2, None, "Nhật ký xem")
        _rl_recent_g = (reading_log_df[reading_log_df['Ngày hoàn thành'] >= pd.Timestamp(_today - timedelta(days=13))]
                        if not reading_log_df.empty else reading_log_df)
        with st.container(border=True, key="jcard_gundam_journal"):
            if _rl_recent_g.empty:
                st.caption("Chưa có tập nào hoàn thành trong 14 ngày gần đây.")
            else:
                st.markdown(f"<div class='jrows'>{_reading_rows_html(_rl_recent_g, sort_desc=True)}</div>",
                            unsafe_allow_html=True)
        sec_chapter("gd-tq-ch3", 3, None, "Bảng số liệu")
        _render_stats_table()
        return

    _render_reading_billboard(t, df_books, _today)
    sec_chapter("sach-tq-ch1", 1, None, "Thống kê", tight_top=True)
    _render_stats_cards()
    sec_chapter("sach-tq-ch2", 2, None, "Nhật ký đọc")
    _rl_recent = (reading_log_df[reading_log_df['Ngày hoàn thành'] >= pd.Timestamp(_today - timedelta(days=13))]
                  if not reading_log_df.empty else reading_log_df)
    with st.container(border=True, key="jcard_sach_journal"):
        if _rl_recent.empty:
            st.caption("Chưa có phần nào hoàn thành trong 14 ngày gần đây.")
        else:
            st.markdown(f"<div class='jrows'>{_reading_rows_html(_rl_recent, sort_desc=True)}</div>",
                        unsafe_allow_html=True)
    sec_chapter("sach-tq-ch3", 3, None, "Trích dẫn &amp; Ghi chú")
    _render_reading_quotes_teaser()
    sec_chapter("sach-tq-ch4", 4, None, "Bảng số liệu")
    _render_stats_table(show_quotes=True)


_KINDLE_INDEP_PREFIX = "Nguồn khác — "  # tiền tố phân biệt nguồn Kindle KHÔNG gắn Dự án (vd tạp chí)
# trong ô chọn "Chi tiết" -- xem _render_reading_detail().


def _render_reading_detail(t, reading_log_df, labels, page_name, df_books):
    """Sub-tab "Chi tiết" của render_reading_log(): chọn 1 cuốn/series rồi hiện billboard + 4
    chương đánh số -- 1. Số liệu (hero chip, tái dùng render_stat_panel), 2. Nhật ký đọc
    (_render_reading_kindle_days, có thêm chip "Thời gian"/ghi chú ngày -- xem docstring hàm đó),
    3. Biểu đồ lịch (tô theo SỐ PHẦN/tập trong ngày, không phải giờ), 4. Bảng số liệu (từng
    ngày, heat cell theo _heat_cell). Dùng chung được cho cả Sách lẫn Gundam qua labels. Đã xác
    nhận với người dùng GIỮ NGUYÊN cả 4 chương này (mockup billboard mới chỉ gợi ý 2 chương, không
    áp dụng -- xem AskUserQuestion trong lịch sử phiên).

    Billboard (render_period_billboard()) render SAU khi đã chọn 1 cuốn/series (không phải ngay
    khi vào tab) -- tránh chip mục lục trỏ tới chương chưa tồn tại lúc ô chọn còn để trống, đúng
    quyết định đã chốt khi thiết kế (giống cách "Báo cáo → Dự án" chỉ hiện hero sau khi chọn Nhóm/
    Dự án).

    Ô chọn CŨNG liệt kê thêm các nguồn Kindle KHÔNG gắn Dự án nào (vd tạp chí The Economist --
    project để trống trong kindle_book_map lúc import, xem "Tải trích dẫn Kindle" ở tab Tuỳ biến)
    -- các nguồn này không có tiến độ đọc (không phiên Forest, không phần Reminders) nên chọn vào
    chỉ hiện đúng 1 khối trích dẫn có sửa/xoá, KHÔNG có 4 chương đánh số phía trên (vốn đều dựa
    trên dữ liệu tiến độ mà nguồn độc lập không có) -- và vì vậy CŨNG không có billboard/hero (chỉ
    1 mục duy nhất, không có gì để mục lục chip điều hướng tới; tên nguồn đã hiện sẵn trong ô
    chọn phía trên rồi)."""
    _kh_all = load_kindle_highlights()
    _indep_sources = (sorted(_kh_all[_kh_all['Dự án'].isna()]['Cuốn sách'].dropna().unique())
                       if not _kh_all.empty else [])
    _detail_opts = (["— Chọn để xem chi tiết —"] + sorted(t['Cuốn sách'].tolist())
                     + [f"{_KINDLE_INDEP_PREFIX}{s}" for s in _indep_sources])
    with st.container(key="rl_detail_select"):
        _detail_sel = st.selectbox(f"Chọn 1 {labels['item_col'].lower()}",
                                    _detail_opts, key=f"rl_detail_{labels['item_col']}",
                                    label_visibility="collapsed")
    if _detail_sel == _detail_opts[0]:
        st.info(f"Chọn 1 {labels['item_col'].lower()} ở trên để xem chi tiết.")
        return

    _anchor_ns = "rl-ct" if page_name == "Sách" else "gd-ct"
    _journal_label = "Nhật ký đọc" if page_name == "Sách" else "Nhật ký xem"

    if _detail_sel.startswith(_KINDLE_INDEP_PREFIX):
        _src = _detail_sel[len(_KINDLE_INDEP_PREFIX):]
        _kh_src = _kh_all[_kh_all['Cuốn sách'] == _src]
        sec_chapter(f"{_anchor_ns}-quote", None, None, "Trích dẫn &amp; Ghi chú")
        with st.container(border=True, key="jcard_reading_detail_indep"):
            _render_reading_kindle_days(reading_log_df.iloc[0:0], _kh_src)
        return

    _row = t[t['Cuốn sách'] == _detail_sel].iloc[0]
    _rl_detail = reading_log_df[reading_log_df['Cuốn sách'] == _detail_sel]
    # _kh_all đã tính sẵn ở đầu hàm (dùng chung để liệt kê nguồn độc lập trong ô chọn phía trên),
    # không gọi lại load lần 2 -- _kh_book tính 1 lần ở đây, dùng chung cho cả billboard và mục
    # "2. Nhật ký đọc" phía dưới (trước đây chỉ tính ở mục Nhật ký đọc).
    _kh_book = _kh_all[_kh_all['Cuốn sách'] == _detail_sel] if not _kh_all.empty else _kh_all

    # Billboard: số phần đã đọc bên trái (KHÔNG có mẫu số/thanh tiến độ dạng % -- cùng lý do đã
    # chốt ở billboard Tổng quan: dữ liệu Reminders không có TỔNG số chương/phần cả cuốn, chỉ có
    # số phần ĐÃ xong) + tên sách/tác giả + chip số liệu bên phải (tái dùng .pbill-*/.chip như
    # billboard Tổng quan). KHÔNG có phụ đề sách -- xác nhận với người dùng không thêm dữ liệu mới
    # cho mục này, chỉ hiện tác giả.
    _author_ct = _reading_author_of(_kh_all, _detail_sel)
    _author_html_ct = f" <span class='pbill-author'>· {html_escape(str(_author_ct))}</span>" if _author_ct else ""
    _chips_ct = []
    if pd.notna(_row['Tổng giờ']):
        _chips_ct.append(f"<span class='chip'><span class='ck'>Tổng giờ {labels['verb']}</span>"
                          f"<span class='cv'>{_fmt_hours_short(_row['Tổng giờ'])}</span></span>")
    if pd.notna(_row['Số phần đã đọc']):
        _chips_ct.append(f"<span class='chip'><span class='ck'>{labels['parts_label']}</span>"
                          f"<span class='cv'>{int(_row['Số phần đã đọc'])}</span></span>")
    _n_quotes_ct = len(_kh_book[_kh_book['Loại'] == 'highlight']) if not _kh_book.empty else 0
    if _n_quotes_ct:
        _chips_ct.append(f"<span class='chip'><span class='ck'>Trích dẫn</span>"
                          f"<span class='cv'>{_n_quotes_ct}</span></span>")
    _n_favs_ct = int(_kh_book['Yêu thích'].sum()) if not _kh_book.empty else 0
    if _n_favs_ct:
        _chips_ct.append(f"<span class='chip tw'><span class='cv'>{_n_favs_ct} trích dẫn yêu thích</span></span>")
    _right_ct = (f"<div class='pbill-kicker'>{_row['Trạng thái']}</div>"
                 f"<div class='pbill-booktitle'>{html_escape(str(_detail_sel))}{_author_html_ct}</div>"
                 f"<div class='pbill-chips'>{''.join(_chips_ct)}</div>")
    render_period_billboard(
        _row['Trạng thái'],
        f"{int(_row['Số phần đã đọc'])}" if pd.notna(_row['Số phần đã đọc']) else "—",
        f"{labels['part_word']} đã {labels['verb']}",
        f"bắt đầu {pd.Timestamp(_row['Bắt đầu']):%d/%m} · lần {labels['verb']} gần nhất "
        f"{_rel_day_label(_row['Gần nhất'], _today_vn())}",
        _right_ct,
        [(f"{_anchor_ns}-ch1", "1 · Số liệu"), (f"{_anchor_ns}-ch2", f"2 · {_journal_label}"),
         (f"{_anchor_ns}-ch3", "3 · Biểu đồ lịch"), (f"{_anchor_ns}-ch4", "4 · Bảng số liệu")],
        key="bc_billboard_detail")

    sec_chapter(f"{_anchor_ns}-ch1", 1, None, "Số liệu", tight_top=True)
    _secs = [{"label": "Mốc thời gian", "chips": [
        {"k": "Bắt đầu", "v": pd.Timestamp(_row['Bắt đầu']).strftime('%d/%m/%Y')},
        {"k": "Gần nhất", "v": pd.Timestamp(_row['Gần nhất']).strftime('%d/%m/%Y')},
        {"k": "Số ngày", "v": f"{int(_row['Số ngày'])}" if pd.notna(_row['Số ngày']) else "—"},
    ]}]
    _nhip = []
    if pd.notna(_row['Giờ/tuần']):
        _nhip.append({"k": "Giờ/tuần", "v": f"{_fmt_hours_short(_row['Giờ/tuần'])}"})
    if pd.notna(_row['Tổng giờ']) and pd.notna(_row['Số ngày']) and _row['Số ngày']:
        _nhip.append({"k": "TB giờ/ngày", "v": f"{_fmt_hours_short(_row['Tổng giờ'] / _row['Số ngày'])}"})
    if _nhip:
        _secs.append({"label": "Nhịp độ", "chips": _nhip})
    _tt = [{"k": "Hiện tại", "v": _row['Trạng thái'], "hl": _row['Trạng thái'] == labels['ongoing']}]
    if pd.notna(_row['Phần gần nhất']):
        _tt.append({"k": labels['part_recent_label'], "v": str(_row['Phần gần nhất'])})
    _secs.append({"label": "Trạng thái", "chips": _tt})

    render_stat_panel(
        hero_items=[
            {"label": "Tổng giờ", "value": f"{_fmt_hours_short(_row['Tổng giờ'])}" if pd.notna(_row['Tổng giờ']) else "—"},
            {"label": labels['parts_label'], "value": f"{int(_row['Số phần đã đọc'])}" if pd.notna(_row['Số phần đã đọc']) else "—"},
        ],
        sections=_secs,
    )

    sec_chapter(f"{_anchor_ns}-ch2", 2, None, _journal_label)
    # Trích dẫn/ghi chú Kindle (nếu cuốn/series này đã được ghép qua kindle_book_map, xem
    # "Tải trích dẫn Kindle" ở tab Tuỳ biến) gộp thẳng vào cùng dòng thời gian này, không còn
    # là mục riêng -- xem _render_reading_kindle_days(). _kh_book đã tính sẵn ở trên (dùng chung
    # với billboard).
    if not _rl_detail.empty or not _kh_book.empty:
        with st.container(border=True, key="jcard_reading_detail"):
            _render_reading_kindle_days(_rl_detail, _kh_book, df_books=df_books)
    else:
        st.caption(f"Chưa có {labels['days_label'].lower()} nào từ Reminders cho mục này.")

    sec_chapter(f"{_anchor_ns}-ch3", 3, None, "Biểu đồ lịch")
    if not _rl_detail.empty:
        render_reading_calendar_grid(_rl_detail, labels)
    else:
        st.caption("Chưa có dữ liệu để vẽ biểu đồ lịch.")

    sec_chapter(f"{_anchor_ns}-ch4", 4, None, "Bảng số liệu")
    if not _rl_detail.empty:
        _day_tbl = (_rl_detail.assign(_d=_rl_detail['Ngày hoàn thành'].dt.normalize())
                    .groupby('_d').size().reset_index(name='n').sort_values('_d', ascending=False))
        _vmax = float(_day_tbl['n'].max()) if not _day_tbl.empty else 0.0
        _rows = ''
        for _, r in _day_tbl.iterrows():
            _wd = VN_DAYS.get(pd.Timestamp(r['_d']).day_name(), '')
            _rows += '<tr class="prow">'
            _rows += f'<td class="lbl">{r["_d"]:%d/%m/%Y}</td><td class="txt">{_wd}</td>'
            _rows += _heat_cell(float(r['n']), _vmax, as_hours=False)
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
        padding={"left": 52, "right": 12, "top": 5, "bottom": 5},
        background='transparent',
    ).configure_view(strokeWidth=0)
    st.altair_chart(chart, width='content')


def render_day_timeline(day_df):
    """Dòng thời gian trong ngày (0–24h): khối phiên tô màu theo Dự án, đặt đúng vị trí giờ nó
    thực sự diễn ra, kèm legend màu theo Dự án bên dưới trục giờ."""
    if day_df.empty:
        return

    line_html = ''.join(f'<div class="dtl-line" style="left:{b/24*100:.3f}%;"></div>' for b in (5, 11, 17, 22))
    label_html = ''.join(
        f'<span class="dtl-bl" style="left:{(s + e) / 2 / 24 * 100:.3f}%;">{nm.strip().upper()}</span>'
        for nm, s, e, _ in BUOI_BANDS if (e - s) >= 3)

    _rows = day_df.sort_values('Thời gian bắt đầu').reset_index(drop=True)
    bars_html = ''
    for i, r in _rows.iterrows():
        s = pd.Timestamp(r['Thời gian bắt đầu']); e = pd.Timestamp(r['Thời gian kết thúc'])
        s_min = s.hour * 60 + s.minute
        # Độ rộng = ĐÚNG thời lượng thật, KHÔNG nới lên 1 mức tối thiểu nào cả -- bug thật đã gặp:
        # nới độ rộng phiên rất ngắn lên 1 mức cố định (vd 6 phút) để dễ nhìn/bấm có thể đè lên
        # phiên kế tiếp nếu 2 phiên cách nhau chưa tới mức đó. Vì left/width đều tỉ lệ TUYẾN TÍNH
        # theo đúng mốc giờ thật (không phiên nào chồng giờ thật với phiên khác), width tính từ
        # thời lượng thật KHÔNG BAO GIỜ chồng lấn nhau -- cách duy nhất chắc chắn hết đè, không
        # cần vá thêm logic giới hạn theo phiên kế tiếp hay viền phân tách giữa các thanh.
        left = s_min / 1440 * 100
        width = min(float(r['Thời lượng (Phút)']), 1440 - s_min) / 1440 * 100
        proj = str(r['Dự án'])
        lab = f'<span class="dtl-bar-lbl">{html_escape(proj)}</span>' if width > 5.5 else ''
        bars_html += (f'<div class="dtl-bar" title="{html_escape(proj)}: {s:%H:%M}–{e:%H:%M}" '
                      f'style="left:{left:.3f}%;width:{width:.3f}%;background:{COLOR_MAP.get(proj, "#8e8e93")};">'
                      f'{lab}</div>')

    ticks_html = ''.join(
        f'<span class="dtl-tk" style="left:{h/24*100:.3f}%;">{h}{"h" if h in (0, 24) else ""}</span>'
        for h in range(0, 25, 3))
    projs = list(dict.fromkeys(day_df.sort_values('Thời gian bắt đầu')['Dự án'].astype(str)))
    legend_html = ''.join(
        f'<span><i style="background:{COLOR_MAP.get(p, "#8e8e93")};"></i>{html_escape(p)}</span>' for p in projs)

    st.markdown(f"""
<style>
.dtl-card{{background:var(--card);border:1px solid var(--border);border-radius:10px;box-shadow:0 1px 1px rgba(0,0,0,0.02);padding:14px 18px;margin-top:14px;}}
.dtl-strip{{position:relative;height:16px;margin-bottom:3px;}}
.dtl-bl{{position:absolute;transform:translateX(-50%);font-size:10px;font-weight:600;letter-spacing:.4px;color:var(--text-3);}}
.dtl-track{{position:relative;height:44px;border-radius:6px;overflow:hidden;background:var(--chip);box-shadow:inset 0 1px 3px rgba(0,0,0,0.06);}}
.dtl-line{{position:absolute;top:0;bottom:0;width:1px;background:var(--divider);}}
.dtl-bar{{position:absolute;top:3px;height:38px;min-width:1px;border-radius:4px;display:flex;align-items:center;justify-content:flex-start;padding:0 6px;color:#fff;font-size:11.5px;font-weight:600;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.18);}}
.dtl-bar-lbl{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0;flex:1 1 auto;}}
.dtl-axis{{position:relative;height:16px;margin-top:4px;}}
.dtl-tk{{position:absolute;transform:translateX(-50%);font-size:11px;color:var(--text-2);}}
.dtl-legend{{display:flex;flex-wrap:wrap;gap:14px;margin-top:12px;font-size:12.5px;color:var(--text);}}
.dtl-legend i{{display:inline-block;width:11px;height:11px;border-radius:3px;vertical-align:-1px;margin-right:5px;}}
</style>
<div class="dtl-card">
<span class="rl-book">Dòng thời gian trong ngày</span>
<div class="dtl-strip">{label_html}</div>
<div class="dtl-track">{line_html}{bars_html}</div>
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
    _book_chips_html()) → ghi chú nhanh đang chờ (mỗi note 1 hàng badge giờ + chữ + nút Gộp/Sửa/
    Xoá riêng, xem update_quick_note()/delete_quick_note()) → nhãn "Ghi chú chính" → ghi chú
    chính. Mặc định chỉ hiện ghi chú đã lưu (hoặc trạng thái trống) kèm một nút; bấm nút mới mở
    trình soạn (Quill) inline với Cập nhật/Huỷ/Xoá.

    Nút "Gộp" trên mỗi ghi chú nhanh: đúng quy trình thực tế (ghi chú nhanh suốt ngày qua Siri/
    Shortcut, tối tổng hợp thành ghi chú chính) -- bấm sẽ mở ô soạn (nếu chưa mở) với nội dung
    ghi chú nhanh đó được nối vào CUỐI nội dung đang có (kèm giờ để giữ ngữ cảnh), rồi đánh dấu
    ghi chú nhanh đó "chờ xoá". Chỉ thực sự XOÁ khỏi bảng quick_notes khi người dùng bấm "Cập
    nhật" lưu ghi chú chính (Huỷ/Xoá ghi chú thì bỏ đánh dấu, không xoá) -- tránh mất dữ liệu nếu
    người dùng đổi ý giữa chừng.

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
    quill_gen_key = f"note_quill_gen_{day}"
    content_key = f"note_content_{day}"

    def _enter_edit(base_content=None):
        """base_content=None -> mở soạn từ nội dung ĐÃ LƯU (nút Sửa/Thêm ghi chú); truyền nội
        dung đã nối thêm ghi chú nhanh khi mở qua nút Gộp. Ghi vào content_key (KHÔNG phải đọc
        lại session_state của chính widget Quill, xem _active_quill_key()) -- bug thật đã gặp:
        streamlit-quill là custom component chạy trong iframe, giá trị echo về session_state của
        WIDGET đó chỉ tới sau 1 round-trip bất đồng bộ với trình duyệt, nên bấm Gộp 2 lần liên
        tiếp (trước khi round-trip lần 1 kịp hoàn tất) đọc lại giá trị widget cũ sẽ ra rỗng/cũ,
        làm MẤT nội dung ghi chú nhanh vừa gộp trước đó. content_key do CHÍNH code này ghi/đọc
        đồng bộ (không qua widget) nên luôn đúng, không phụ thuộc round-trip."""
        st.session_state.pop(quill_key, None)
        st.session_state[content_key] = base_content if base_content is not None else cur
        st.session_state[edit_key] = True

    def _active_quill_key():
        """Key thật truyền cho st_quill -- đổi theo "generation" mỗi khi cần ép remount widget
        (bấm Gộp lúc editor ĐÃ mở sẵn). streamlit-quill là component "uncontrolled": value chỉ
        được áp dụng lúc mount đầu tiên, đổi value cho 1 instance đã mount không có tác dụng gì --
        key cố định quill_key là đủ khi editor vừa mở lần đầu (component chưa tồn tại ở lần chạy
        trước nên chắc chắn mount mới), nhưng khi Gộp trong lúc đang mở, component đã tồn tại sẵn
        -> phải đổi key mới ép Streamlit unmount/mount lại instance mới với value merge đã nối."""
        return f"{quill_key}_{st.session_state.get(quill_gen_key, 0)}"

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
                        st.markdown(f"<div style='margin-bottom:14px;'><span class='rl-book'>Lịch</span>{chips}</div>",
                                    unsafe_allow_html=True)

                rl = load_reading_log()
                if not rl.empty:
                    day_rl = rl[rl['Ngày hoàn thành'].dt.date == day]
                    if not day_rl.empty:
                        st.markdown(_book_chips_html(day_rl), unsafe_allow_html=True)

                qn_day = _quick_notes_on(load_quick_notes(), day)
                merge_pending_key = f"note_merge_pending_{day}"
                if not qn_day.empty:
                    st.markdown("<span class='rl-book' style='margin-top:8px;'>Ghi chú nhanh</span>",
                                unsafe_allow_html=True)
                    for _, r in qn_day.iterrows():
                        _qid = int(r['id'])
                        qedit_key = f"qnote_edit_{_qid}"
                        _pending = _qid in st.session_state.get(merge_pending_key, [])
                        with st.container(key=f"qnote_row_{_qid}"):
                            qc1, qc2, qc3 = st.columns([2, 14, 4])
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
                                    _txt_cls = "qn-text qn-merged" if _pending else "qn-text"
                                    st.markdown(f"<span class='{_txt_cls}'>{html_escape(str(r['Nội dung']))}</span>",
                                                unsafe_allow_html=True)
                                with qc3:
                                    with st.container(horizontal=True, gap="small"):
                                        if st.button("", icon=":material/done_all:" if _pending else ":material/merge:",
                                                     key=f"qnote_merge_{_qid}", help="Đã gộp — chờ Lưu" if _pending
                                                     else "Gộp vào ghi chú chính", disabled=_pending):
                                            _was_open = st.session_state.get(edit_key, False)
                                            _base = (st.session_state.get(content_key, cur)
                                                     if _was_open else cur) or ""
                                            _piece = f"<p><strong>{r['Thời gian']:%H:%M}</strong> — {html_escape(str(r['Nội dung']))}</p>"
                                            _new_content = _base + _piece
                                            st.session_state.setdefault(merge_pending_key, [])
                                            st.session_state[merge_pending_key].append(_qid)
                                            if _was_open:
                                                # Editor đã mở sẵn -- component Quill đã mount, đổi
                                                # value không đủ (xem docstring _active_quill_key),
                                                # phải đổi generation để ép remount widget mới.
                                                st.session_state[quill_gen_key] = st.session_state.get(quill_gen_key, 0) + 1
                                            _enter_edit(_new_content)
                                            st.rerun()
                                        if st.button("", icon=":material/edit:", key=f"qnote_editbtn_{_qid}",
                                                     help="Sửa"):
                                            st.session_state[qedit_key] = True
                                            st.rerun()
                                        if st.button("", icon=":material/delete:", key=f"qnote_del_{_qid}",
                                                     help="Xoá"):
                                            delete_quick_note(_qid)
                                            if _qid in st.session_state.get(merge_pending_key, []):
                                                st.session_state[merge_pending_key].remove(_qid)
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
                            # Chế độ soạn: trình soạn Quill inline -- value khởi tạo lấy từ
                            # content_key (do _enter_edit() ghi sẵn: nội dung đã lưu, hoặc đã nối
                            # thêm ghi chú nhanh nếu mở qua nút Gộp). Đồng bộ NGƯỢC lại content_key
                            # mỗi khi widget trả về giá trị khác None (đang gõ/đã echo xong round-
                            # trip) -- content_key luôn là bản MỚI NHẤT đã biết, dùng làm _base cho
                            # lần Gộp kế tiếp thay vì đọc trực tiếp session_state của widget (xem
                            # docstring _enter_edit về race bất đồng bộ của streamlit-quill).
                            content = st_quill(value=st.session_state.get(content_key, cur),
                                               html=True, toolbar=NOTE_TOOLBAR,
                                               placeholder="Viết vài dòng về ngày này…", key=_active_quill_key())
                            if content is not None:
                                st.session_state[content_key] = content
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
                                save_note(day, content if content is not None else st.session_state.get(content_key, ""))
                                # Ghi chú nhanh đã "Gộp" (xem nút ở trên) chỉ thực sự bị xoá TẠI ĐÂY,
                                # sau khi ghi chú chính đã lưu thành công -- Huỷ/Xoá ghi chú bên dưới
                                # chỉ bỏ đánh dấu, không đụng tới bảng quick_notes.
                                for _pid in st.session_state.pop(merge_pending_key, []):
                                    delete_quick_note(_pid)
                                st.session_state[edit_key] = False
                                st.rerun()
                            if st.button("Huỷ", icon=":material/close:", key=f"note_cancel_{day}"):
                                st.session_state.pop(merge_pending_key, None)
                                st.session_state[edit_key] = False
                                st.rerun()
                            if cur and st.button("Xoá ghi chú", icon=":material/delete:", key=f"note_del_{day}"):
                                st.session_state.pop(merge_pending_key, None)
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
            _note_body = f"<div class='note-html'>{str(nd[nd['_d'] == d].iloc[0]['Ghi chú'])}</div>"
            # Nhãn "Ghi chú chính" chỉ cần khi CÒN ghi chú nhanh hiện cùng dòng (phân biệt 2 khối) --
            # không còn ghi chú nhanh nào (đã gộp/xoá hết) thì chỉ 1 khối ghi chú duy nhất, nhãn dư
            # thừa. Khớp đúng cách renderer Tìm kiếm đã làm (không có nhãn, xem _book_chips_html
            # neighbor ở render_search()).
            note_html = (f"<span class='rl-book'>Ghi chú chính</span>{_note_body}" if qnote_html
                         else _note_body)
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


HEALTH_METRICS_JSON_EXAMPLE = [
    {
        "test_date": "2026-07-08",
        "category": "Huyết học",
        "indicators": [
            {"indicator": "Số lượng hồng cầu", "value_raw": "5.03", "unit": "T/L", "ref_raw": "4.2 - 5.4"},
            {"indicator": "Hemoglobin (Hb)", "value_raw": "148", "unit": "g/L", "ref_raw": "130 - 170"},
        ],
    },
    {
        "test_date": "2026-07-08",
        "category": "Sinh hóa",
        "indicators": [
            {"indicator": "Glucose", "value_raw": "5.4", "unit": "mmol/L", "ref_raw": "3.9 - 6.4"},
        ],
    },
]


def _render_health_report(df_health):
    """Sub-tab "Báo cáo": billboard "Số sức khoẻ" (điểm X/Y chỉ số đang trong ngưỡng, xem
    _health_score()) rồi 3 chương đánh số: 1· Chỉ số bất thường (card chi tiết + chip "trong
    ngưỡng" của ĐÚNG lần khám gần nhất) · 2· Diễn biến chỉ số (lưới mini-card xu hướng auto-chọn,
    xem _health_trend_candidates(), CỘNG với bộ chọn Nhóm/Chỉ số + biểu đồ đường đầy đủ giữ nguyên
    từ bản cũ -- xác nhận với người dùng: lưới mini-card là tổng quan nhanh THÊM VÀO, không thay
    thế bộ chọn/biểu đồ chi tiết) · 3· Bảng xét nghiệm đầy đủ (mọi Chỉ số của lần khám gần nhất).

    Mockup có mức đánh giá thứ 3 "Sát ngưỡng" (cam) và chip "Hẹn tái khám" -- CẢ 2 đều bỏ, đã xác
    nhận với người dùng: mức "sát ngưỡng" cần tự đặt 1 ngưỡng % không có cơ sở dữ liệu thật (giữ
    nhị phân trong/ngoài ngưỡng như _health_is_abnormal() đã có, đồng bộ với Lịch sử), "Hẹn tái
    khám" không có trường dữ liệu nào tương ứng trong health_metrics."""
    if df_health.empty:
        st.info("Chưa có dữ liệu xét nghiệm nào — sang tab **Dữ liệu đầu vào** để nhập.")
        return

    _latest_date = pd.Timestamp(df_health['Ngày lấy mẫu'].max())
    _latest_panel = df_health[df_health['Ngày lấy mẫu'] == _latest_date]
    _latest_num = _latest_panel[_latest_panel['Giá trị'].notna()]

    _abn_latest = _latest_num[_health_is_abnormal(_latest_num)] if not _latest_num.empty else _latest_num
    if not _abn_latest.empty:
        # Cùng 1 lần khám đôi khi có 2 dòng cho CÙNG 1 xét nghiệm dưới 2 tên khác nhau (vd tên
        # đầy đủ trên phiếu "Định lượng Glucose [Máu]" VÀ tên gọn "Glucose") -- nguồn nhập liệu
        # ghi cả 2 dòng cho cùng 1 kết quả. Nhận diện trùng qua (Nhóm, Giá trị, Đơn vị, Ref thấp,
        # Ref cao) giống hệt nhau (KHÔNG so tên Chỉ số, vốn khác chữ dù cùng 1 xét nghiệm) -- dùng
        # Ref thấp/Ref cao (đã parse ra số) thay vì chuỗi thô "Khoảng tham chiếu", vì chuỗi thô có
        # thể lệch khoảng trắng giữa 2 dòng cùng nguồn (vd "<3.4" so với "< 3.4") khiến so sánh
        # chuỗi trượt trùng dù cùng 1 kết quả. Chỉ giữ 1 dòng, ưu tiên tên NGẮN hơn (thường là tên
        # gọn thông dụng). Chỉ áp dụng cho billboard/chương 1 (tóm tắt nhanh) -- Lịch sử Sức khoẻ
        # vẫn giữ nguyên mọi dòng đã nhập, không tự ý xoá dữ liệu.
        _abn_latest = (
            _abn_latest.assign(_namelen=_abn_latest['Chỉ số'].str.len())
            .sort_values('_namelen')
            .drop_duplicates(subset=['Nhóm', 'Giá trị', 'Đơn vị', 'Ref thấp', 'Ref cao'], keep='first')
            .drop(columns='_namelen'))
    _ok_latest = _latest_num.drop(_abn_latest.index)

    _toc = [("hm-bc-ch1", "1 · Chỉ số bất thường"), ("hm-bc-ch2", "2 · Diễn biến chỉ số"),
            ("hm-bc-ch3", "3 · Bảng xét nghiệm đầy đủ")]
    _ok_score, _total_score = _health_score(df_health)
    if not _abn_latest.empty:
        _abn_chips = ''
        for _, r in _abn_latest.iterrows():
            arrow = _mi('arrow_upward', 11) if r['Giá trị'] > r['Ref cao'] else _mi('arrow_downward', 11)
            _abn_chips += (f"<span class='jchip abn'><span class='ck'>{html_escape(str(r['Chỉ số']))}</span>"
                           f"<span class='cv'>{r['Giá trị']:g}{arrow}</span></span>")
        _right_html = f"<div class='pbill-kicker'>Cần chú ý</div><div class='pbill-chips'>{_abn_chips}</div>"
    else:
        _right_html = "<div class='pbill-title'>Tất cả chỉ số trong ngưỡng</div>"
    render_period_billboard("Số sức khoẻ", f"{_ok_score}/{_total_score}", "chỉ số trong ngưỡng",
                             f"Lần khám gần nhất {_latest_date:%d/%m/%Y}", _right_html, _toc)

    sec_chapter("hm-bc-ch1", 1, None, "Chỉ số bất thường",
                badge=f"Lần khám {_latest_date:%d/%m/%Y}", tight_top=True)
    if _latest_num.empty:
        st.caption("Lần khám gần nhất chưa có chỉ số dạng số nào để đánh giá.")
    elif _abn_latest.empty:
        st.success(f"Tất cả {len(_latest_num)} chỉ số trong lần khám gần nhất đều trong ngưỡng.")
    else:
        _cards = ''
        for _, r in _abn_latest.iterrows():
            _above = r['Giá trị'] > r['Ref cao'] if pd.notna(r['Ref cao']) else False
            arrow = _mi('arrow_upward', 12) if _above else _mi('arrow_downward', 12)
            _ref_txt = f"trên ngưỡng {r['Ref cao']:g}" if _above else f"dưới ngưỡng {r['Ref thấp']:g}"
            unit = f" {r['Đơn vị']}" if pd.notna(r['Đơn vị']) and str(r['Đơn vị']).strip() else ""
            _cards += (
                "<div class='hmtl-card'>"
                f"<span class='rl-book'>{html_escape(str(r['Chỉ số']))}</span>"
                f"<div class='hbn-value'>{r['Giá trị']:g}<span class='hbn-unit'>{unit}</span></div>"
                f"<div class='hbn-delta'>{arrow} {_ref_txt}</div></div>")
        st.markdown(f"<div class='hbn-grid'>{_cards}</div>", unsafe_allow_html=True)
        if not _ok_latest.empty:
            _ok_chips = ''.join(
                f"<span class='jchip'><span class='ck'>{html_escape(str(r['Chỉ số']))}</span>"
                f"<span class='cv'>{r['Giá trị']:g}</span></span>" for _, r in _ok_latest.iterrows())
            st.markdown(f"<div class='hmtl-grp' style='margin-top:16px;'>"
                        f"<span class='rl-book'>Trong ngưỡng</span>{_ok_chips}</div>", unsafe_allow_html=True)

    sec_chapter("hm-bc-ch2", 2, None, "Diễn biến chỉ số")
    _trend_keys = _health_trend_candidates(df_health, n=4)
    if not _trend_keys:
        st.caption("Chưa có chỉ số nào đủ ít nhất 2 lần đo để vẽ xu hướng.")
    else:
        _trend_cards = ''
        for _nhom, _chiso in _trend_keys:
            _s = (df_health[(df_health['Nhóm'] == _nhom) & (df_health['Chỉ số'] == _chiso)
                             & df_health['Giá trị'].notna()]
                  .sort_values('Ngày lấy mẫu').tail(4).reset_index(drop=True))
            _vals, _dates = list(_s['Giá trị']), list(_s['Ngày lấy mẫu'])
            _abn_flags = list(_health_is_abnormal(_s))
            _vmin, _vmax = min(_vals), max(_vals)
            _bars = ''
            for _v, _d, _a in zip(_vals, _dates, _abn_flags):
                _pct = 50 if _vmax == _vmin else 15 + (_v - _vmin) / (_vmax - _vmin) * 85
                _bars += (f"<div class='htrend-bar-col'><span class='htrend-bar-val{' abn' if _a else ''}'>"
                          f"{_v:g}</span><div class='htrend-bar{' abn' if _a else ''}' "
                          f"style='height:{_pct:.0f}%;'></div><span class='htrend-bar-date'>{_d:%m/%y}</span></div>")
            _unit_vals = _s['Đơn vị'].dropna()
            _unit = _unit_vals.iloc[-1] if not _unit_vals.empty else ""
            _last = _s.iloc[-1]
            _caption = _health_trend_caption(_vals, _dates, _last['Ref thấp'], _last['Ref cao'], _unit)
            _latest_style = "color:#ff3b30;" if _abn_flags[-1] else ""
            _trend_cards += (
                "<div class='hmtl-card htrend-card'><div class='hmtl-head'>"
                f"<span class='htrend-title'>{html_escape(_chiso)} <span class='htrend-unit'>{_unit}</span></span>"
                f"<span style='font-weight:700;{_latest_style}'>{_vals[-1]:g}</span></div>"
                f"<div class='htrend-bars'>{_bars}</div>"
                f"<div class='htrend-caption'>{_caption}</div></div>")
        st.markdown(f"<div class='htrend-grid'>{_trend_cards}</div>", unsafe_allow_html=True)

    st.write("")
    cc1, cc2 = st.columns(2)
    cats = sorted(df_health['Nhóm'].dropna().unique())
    cat_pick = cc1.selectbox("Nhóm", cats, key="hm_chart_cat")
    inds = sorted(df_health.loc[df_health['Nhóm'] == cat_pick, 'Chỉ số'].dropna().unique())
    ind_pick = cc2.selectbox("Chỉ số", inds, key="hm_chart_ind")
    s = (df_health[(df_health['Nhóm'] == cat_pick) & (df_health['Chỉ số'] == ind_pick)]
         .sort_values('Ngày lấy mẫu'))
    s_num = s[s['Giá trị'].notna()].reset_index(drop=True)

    # "Số liệu"/"Biểu đồ theo dõi" là 2 mục CON trong CÙNG chương 2 (không phải chương riêng đánh
    # số như bản cũ) -- dùng .section-hd (tiêu đề phụ nhẹ, không có ô số) vì lưới mini-card phía
    # trên đã là nội dung chính của chương "Diễn biến chỉ số", 2 mục này chỉ là phần "xem sâu 1
    # chỉ số cụ thể" bổ sung, không cần đánh số ngang hàng 3 chương lớn của trang.
    if s_num.empty:
        st.markdown("<div class='section-hd'>Số liệu</div>", unsafe_allow_html=True)
        st.caption("Chỉ số này chưa có giá trị dạng số để thống kê (có thể là kết quả định tính).")
        st.markdown("<div class='section-hd'>Biểu đồ theo dõi</div>", unsafe_allow_html=True)
        st.caption("Chỉ số này chưa có giá trị dạng số để vẽ biểu đồ.")
        return

    _unit_vals = s_num['Đơn vị'].dropna()
    unit = _unit_vals.iloc[-1] if not _unit_vals.empty else ""
    is_abn = _health_is_abnormal(s_num)

    st.markdown("<div class='section-hd'>Số liệu</div>", unsafe_allow_html=True)
    last = s_num.iloc[-1]
    deltas = []
    if len(s_num) > 1:
        d = last['Giá trị'] - s_num.iloc[-2]['Giá trị']
        dc = "#34c759" if d > 0 else "#ff3b30" if d < 0 else "#86868b"
        deltas = [(f"{'+' if d > 0 else ''}{d:.2f} so với lần trước", dc)]
    hero_items = [{"label": f"Gần nhất · {last['Ngày lấy mẫu']:%d/%m/%Y}",
                   "value": f"{last['Giá trị']:g} {unit}".strip(), "deltas": deltas}]
    hi, lo = int(s_num['Giá trị'].idxmax()), int(s_num['Giá trị'].idxmin())
    n_abn = int(is_abn.sum())
    sections = [
        {"label": "Thống kê", "chips": [
            {"k": "Số quan sát", "v": str(len(s_num))},
            {"k": "Khoảng thời gian",
             "v": f"{s_num['Ngày lấy mẫu'].min():%m/%Y} – {s_num['Ngày lấy mẫu'].max():%m/%Y}"},
            {"k": "Trung bình", "v": f"{s_num['Giá trị'].mean():.2f} {unit}".strip()},
            {"k": "Cao nhất", "v": f"{s_num.loc[hi, 'Giá trị']:g} ({s_num.loc[hi, 'Ngày lấy mẫu']:%d/%m/%Y})"},
            {"k": "Thấp nhất", "v": f"{s_num.loc[lo, 'Giá trị']:g} ({s_num.loc[lo, 'Ngày lấy mẫu']:%d/%m/%Y})"},
        ]},
        {"label": "Bất thường", "chips": [
            {"k": "Ngoài khoảng tham chiếu", "v": f"{n_abn}/{len(s_num)}", "hl": n_abn > 0},
        ]},
    ]
    render_stat_panel(hero_items, sections=sections)

    st.markdown("<div class='section-hd'>Biểu đồ theo dõi</div>", unsafe_allow_html=True)
    _band_fill = "rgba(255,255,255,0.10)" if IS_DARK else "rgba(0,0,0,0.06)"
    _band_line = "rgba(255,255,255,0.28)" if IS_DARK else "rgba(0,0,0,0.18)"
    fig = go.Figure()
    if s_num['Ref cao'].notna().any():
        fig.add_trace(go.Scatter(
            x=s_num['Ngày lấy mẫu'], y=s_num['Ref cao'], mode='lines',
            line=dict(color=_band_line, width=1, dash='dot'), connectgaps=True,
            name='Trần tham chiếu', showlegend=False, hoverinfo='skip'))
    if s_num['Ref thấp'].notna().any():
        fig.add_trace(go.Scatter(
            x=s_num['Ngày lấy mẫu'], y=s_num['Ref thấp'], mode='lines',
            line=dict(color=_band_line, width=1, dash='dot'), connectgaps=True,
            fill='tonexty', fillcolor=_band_fill,
            name='Khoảng tham chiếu', showlegend=False, hoverinfo='skip'))
    fig.add_trace(go.Scatter(
        x=s_num['Ngày lấy mẫu'], y=s_num['Giá trị'], mode='lines+markers',
        line=dict(color=ACCENT, width=2.5),
        marker=dict(color=['#ff3b30' if a else ACCENT for a in is_abn], size=9),
        name=ind_pick, customdata=s_num['Khoảng tham chiếu'].fillna(''),
        hovertemplate=f'%{{x|%d/%m/%Y}}<br>%{{y}} {unit}<br>Tham chiếu: %{{customdata}}<extra></extra>',
    ))
    fig.update_layout(
        height=340, margin=dict(l=10, r=10, t=24, b=10), showlegend=False,
        xaxis=dict(title='', tickformat='%d/%m/%y', showgrid=False),
        yaxis=dict(title=unit, gridcolor=("rgba(255,255,255,0.10)" if IS_DARK else "rgba(0,0,0,0.06)")),
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
    )
    st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)
    if is_abn.any():
        st.warning(f"Có {int(is_abn.sum())} lần đo nằm ngoài khoảng tham chiếu.")
    render_health_log_table(s_num, is_abn)

    sec_chapter("hm-bc-ch3", 3, None, "Bảng xét nghiệm đầy đủ", badge=f"Lần khám {_latest_date:%d/%m/%Y}")
    render_health_full_table(_latest_panel)


def _render_health_history(df_health):
    """Sub-tab "Lịch sử": dòng thời gian các lần khám theo năm, 1 thẻ/NGÀY (gộp mọi Nhóm khám
    cùng ngày -- khớp mockup "1 lần khám = 1 thẻ", dữ liệu thật lưu theo (Ngày, Nhóm) riêng nên
    1 ngày có thể có nhiều Nhóm, vd "Huyết học" + "Sinh hóa" cùng ngày). Mỗi Nhóm trong thẻ hiện
    hàng chip chỉ số (đỏ + mũi tên lên/xuống nếu ngoài khoảng tham chiếu, xem _health_is_abnormal).
    Sửa/xoá dữ liệu thật vẫn theo TỪNG Nhóm (khớp khoá test_date+category của
    save_health_metrics_bulk()/delete_health_metric_panel(), gộp sẽ lẫn 2 Nhóm khi lưu) -- gom
    CHUNG vào 1 expander DUY NHẤT ở cuối (chọn lần xét nghiệm cần sửa qua selectbox) thay vì 1
    expander riêng dưới MỖI thẻ như bản đầu: thao tác này ít dùng, mà 1 expander/Nhóm chen giữa
    timeline (kèm đường kẻ ngang phân cách của st.expander) làm vỡ mạch dòng thời gian liên tục,
    lại không đồng bộ hình khối với các thẻ HTML xung quanh.

    Mockup còn có dòng phụ đề "Cơ sở y tế · Gói khám" và ghi chú tự do của bác sĩ, cùng 1 mức
    cảnh báo cam "sát ngưỡng" cạnh mức đỏ "cao" -- CẢ 3 đều không có trong dữ liệu hiện tại (chỉ
    có Ngày/Nhóm/Chỉ số/Giá trị/Đơn vị/Khoảng tham chiếu, không có cơ sở/gói khám/ghi chú, và
    _health_is_abnormal() chỉ nhị phân trong/ngoài khoảng) nên bỏ hẳn, không bịa dữ liệu (đã xác
    nhận với người dùng)."""
    if df_health.empty:
        st.info("Chưa có dữ liệu xét nghiệm nào — sang tab **Dữ liệu đầu vào** để nhập.")
        return
    _years = sorted(df_health['Ngày lấy mẫu'].dt.year.unique(), reverse=True)
    year_sel = st.selectbox("Năm", _years, key="hm_hist_year")
    panels = df_health[df_health['Ngày lấy mẫu'].dt.year == year_sel]
    _dates = sorted(panels['Ngày lấy mẫu'].unique(), reverse=True)

    _panel_keys = []  # [(pdate, pcat, grp), ...] tất cả (Ngày, Nhóm) của năm đang chọn -- gom
                       # 1 lần duy nhất ở đây để dùng lại cho cả timeline lẫn expander sửa/xoá
                       # gộp ở cuối, không lặp lại groupby 2 nơi.
    for pdate in _dates:
        day_df = panels[panels['Ngày lấy mẫu'] == pdate]
        for pcat, grp in sorted(day_df.groupby('Nhóm'), key=lambda kv: kv[0]):
            _panel_keys.append((pd.Timestamp(pdate), pcat, grp))

    for _i, pdate in enumerate(_dates):
        pdate = pd.Timestamp(pdate)
        day_df = panels[panels['Ngày lấy mẫu'] == pdate]
        # Đường nối chỉ vẽ khi CHƯA phải thẻ cuối -- mỗi thẻ render riêng 1 lệnh st.markdown nên
        # ":last-child" trong CSS luôn đúng với chính nó (là con duy nhất trong khối markdown của
        # nó) và sẽ ẨN đường nối ở MỌI thẻ nếu dựa vào CSS -- phải quyết định ở Python theo vị trí
        # trong _dates.
        line_html = "<div class='hmtl-line'></div>" if _i < len(_dates) - 1 else ""
        _day_groups = [(pcat, grp) for pd_, pcat, grp in _panel_keys if pd_ == pdate]
        _n_abn_day = int(_health_is_abnormal(day_df).sum())
        if _n_abn_day:
            dot_cls, badge_html = "hmtl-dot warn", f"<span class='hmtl-badge bad'>{_n_abn_day} chỉ số bất thường</span>"
        else:
            dot_cls, badge_html = "hmtl-dot", "<span class='hmtl-badge ok'>Trong khoảng tham chiếu</span>"

        grp_html = ''
        for pcat, grp in _day_groups:
            _abn = _health_is_abnormal(grp)
            chips = ''
            for (_, r), a in zip(grp.iterrows(), _abn):
                val = f"{r['Giá trị']:g}" if pd.notna(r['Giá trị']) else str(r['Giá trị (gốc)'] or '')
                unit = f" {r['Đơn vị']}" if pd.notna(r['Đơn vị']) and str(r['Đơn vị']).strip() else ""
                arrow = ''
                if a and pd.notna(r['Ref cao']) and r['Giá trị'] > r['Ref cao']:
                    arrow = _mi('arrow_upward', 11)
                elif a and pd.notna(r['Ref thấp']) and r['Giá trị'] < r['Ref thấp']:
                    arrow = _mi('arrow_downward', 11)
                title = f" title='Tham chiếu {html_escape(str(r['Khoảng tham chiếu']))}'" if pd.notna(r['Khoảng tham chiếu']) else ""
                chips += (f"<span class='jchip{' abn' if a else ''}'{title}>"
                          f"<span class='ck'>{html_escape(str(r['Chỉ số']))}</span>"
                          f"<span class='cv'>{html_escape(val)}{unit}{arrow}</span></span>")
            grp_html += f"<div class='hmtl-grp'><span class='rl-book'>{html_escape(str(pcat))}</span>{chips}</div>"

        st.markdown(
            "<div class='hmtl-item'>"
            f"<div class='{dot_cls}'></div>{line_html}"
            "<div class='hmtl-card'>"
            f"<div class='hmtl-head'><span class='hmtl-date'>{pdate:%d/%m/%Y}</span>{badge_html}</div>"
            f"{grp_html}</div></div>", unsafe_allow_html=True)

    # 1 expander DUY NHẤT cho sửa/xoá, đặt SAU cả timeline (không chen giữa từng thẻ) -- chọn
    # đúng 1 lần xét nghiệm (Ngày + Nhóm) qua selectbox rồi mới hiện bảng sửa, xem docstring. Style
    # riêng (container key="hm_hist_edit", xem CSS .st-key-hm_hist_edit) để trông như 1 thẻ hộp
    # khớp .hmtl-card phía trên, thay vì tiêu đề gạch chân kiểu chương báo cáo (mặc định của mọi
    # st.expander khác, xem rule [data-testid="stExpander"]) -- lạc tông với timeline card ngay
    # trên nó. Cùng khuôn với FAQ (Trợ giúp, xem CSS .st-key-help_faq), đã có tiền lệ trong app.
    with st.container(key="hm_hist_edit"):
        with st.expander("Sửa / xoá xét nghiệm đã nhập", icon=":material/edit_note:", expanded=False):
            _opts = [f"{pdate:%d/%m/%Y} · {pcat}" for pdate, pcat, _ in _panel_keys]
            _pick = st.selectbox("Chọn lần xét nghiệm", _opts, key="hm_hist_edit_pick")
            pdate, pcat, grp = _panel_keys[_opts.index(_pick)]
            _ek = f"hm_edit_{pdate:%Y%m%d}_{re.sub(r'[^a-zA-Z0-9]+', '_', pcat)}"
            _abn = _health_is_abnormal(grp)
            grp_disp = grp[["Chỉ số", "Giá trị (gốc)", "Đơn vị", "Khoảng tham chiếu"]].copy()
            grp_disp.insert(1, "Bất thường", ['Có' if a else '' for a in _abn])
            edited = st.data_editor(
                grp_disp, hide_index=True, width='stretch', num_rows="dynamic", key=_ek,
                column_config={"Bất thường": st.column_config.TextColumn(
                    "Bất thường", disabled=True, width="small",
                    help="Tự tính từ Giá trị (gốc)/Khoảng tham chiếu đã lưu, không sửa trực tiếp được ở đây.")})
            ec1, ec2 = st.columns(2)
            if ec1.button("Lưu thay đổi", type="primary", key=f"{_ek}_save"):
                delete_health_metric_panel(pdate.date().isoformat(), pcat)
                _rows = [r for r in edited.to_dict("records") if str(r["Chỉ số"]).strip()]
                if _rows:
                    save_health_metrics_bulk([{
                        "test_date": pdate.date().isoformat(), "category": pcat,
                        "indicators": [{"indicator": r["Chỉ số"], "value_raw": r["Giá trị (gốc)"],
                                        "unit": r["Đơn vị"], "ref_raw": r["Khoảng tham chiếu"]}
                                       for r in _rows]}])
                st.success("Đã lưu thay đổi.")
                time.sleep(1)
                st.rerun()
            if ec2.button("Xoá cả lần xét nghiệm này", key=f"{_ek}_del"):
                delete_health_metric_panel(pdate.date().isoformat(), pcat)
                st.success("Đã xoá.")
                time.sleep(1)
                st.rerun()


def _render_health_input(df_health):
    """Sub-tab "Dữ liệu đầu vào": Import hàng loạt lên TRƯỚC (luồng chính, dùng khi nhờ Claude
    đọc ảnh phiếu xét nghiệm), Nhập kết quả xét nghiệm (nhập tay) xuống sau (luồng phụ/sửa lỗi).

    ĐỔI SANG khuôn "chương" của Hôm nay/Báo cáo (billboard + sec_chapter đánh số) thay vì
    accordion/expander cũ -- xác nhận với người dùng: tab này rất ít vào nên không sợ dài, ưu tiên
    đồng bộ giao diện với phần còn lại của app hơn là gọn bằng cách gập lại. Cả 2 chương LUÔN MỞ
    (không còn st.expander bọc ngoài) vì lý do tương tự.

    Billboard "Lần khám gần nhất" dùng render_period_billboard() -- CÙNG key mặc định "bc_billboard"
    với Báo cáo/Sách/Gundam/Dự án/Tuỳ biến (an toàn vì mỗi nav/sub-tab render độc quyền 1 khối
    if/elif, không có 2 billboard nào cùng vẽ trong 1 lượt chạy ở đây) -- tái dùng thẳng CSS kính
    mờ có sẵn, không cần thêm rule mới. Cột phải dùng lại đúng .pbill-title (câu nhận định) +
    .pbill-chips (chip .jchip/.jchip.abn -- mượn nguyên khuôn từ sub-tab Lịch sử) cho chỉ số. Nút
    "Sửa lần khám này" KHÔNG tự xây bộ sửa/xoá riêng (trùng lặp) mà nhảy sang sub-tab Lịch sử --
    nơi đã có UI sửa/xoá đầy đủ, qua cờ chờ xử lý `_hm_sub_jump` (xem đầu render_health_page(),
    không set trực tiếp session_state của widget segmented_control sau khi nó đã instantiate).

    Mockup còn có nút "Tải lên PDF" (trích số liệu từ file kết quả) -- app không có khả năng đọc
    PDF (luồng chính là dán JSON do Claude đọc ảnh hộ), nên bỏ hẳn, không bịa tính năng chưa làm
    (đã xác nhận với người dùng). Mục "Ngưỡng tham chiếu" (tự đặt ngưỡng cảnh báo riêng, chặt hơn
    mức lab in trên phiếu) cũng bỏ qua -- là tính năng nghiệp vụ MỚI ngoài phạm vi "chỉ sửa giao
    diện" của yêu cầu này, chưa có nơi lưu/logic nào tương ứng."""
    _toc = [("hm-in-ch1", "1 · Import hàng loạt"), ("hm-in-ch2", "2 · Nhập kết quả xét nghiệm")]

    if not df_health.empty:
        _latest_date = pd.Timestamp(df_health['Ngày lấy mẫu'].max())
        _latest_panel = df_health[df_health['Ngày lấy mẫu'] == _latest_date]
        _abn = _health_is_abnormal(_latest_panel)
        _n_abn = int(_abn.sum())
        chips = ''
        for (_, r), a in zip(_latest_panel.iterrows(), _abn):
            val = f"{r['Giá trị']:g}" if pd.notna(r['Giá trị']) else str(r['Giá trị (gốc)'] or '')
            unit = f" {r['Đơn vị']}" if pd.notna(r['Đơn vị']) and str(r['Đơn vị']).strip() else ""
            arrow = ''
            if a and pd.notna(r['Ref cao']) and r['Giá trị'] > r['Ref cao']:
                arrow = _mi('arrow_upward', 11)
            elif a and pd.notna(r['Ref thấp']) and r['Giá trị'] < r['Ref thấp']:
                arrow = _mi('arrow_downward', 11)
            chips += (f"<span class='jchip{' abn' if a else ''}'>"
                      f"<span class='ck'>{html_escape(str(r['Chỉ số']))}</span>"
                      f"<span class='cv'>{html_escape(val)}{unit}{arrow}</span></span>")
        _status_line = (f"{_n_abn} chỉ số ngoài khoảng tham chiếu" if _n_abn
                         else "Tất cả chỉ số trong khoảng tham chiếu")
        _right_html = (f"<div class='pbill-title'>{_status_line}</div>"
                        f"<div class='pbill-chips'>{chips}</div>")
        _vn_dow = VN_DAYS.get(_latest_date.day_name(), "")
        # Nhãn tab CỐ Ý ghi rõ "Lần khám gần nhất" (không phải tháng/năm như Hôm nay/Báo cáo) --
        # chú thích cho biết ngày to bên trái là ngày LẤY MẪU gần nhất, không phải hôm nay, tránh
        # đọc lẫn với khuôn "tờ lịch hôm nay" của billboard Hôm nay (cùng CSS .tbill-date/.pbill-num
        # nên nhìn thoáng qua dễ ngỡ là ngày hiện tại). meta ghi tháng/năm CHỮ ĐẦY ĐỦ (không chỉ số
        # to + thứ ở trên) + số ngày đã trôi qua CHỈ tính theo ngày (không kèm giờ) -- khác
        # format_relative() dùng cho mốc giờ thật (vd đồng bộ dữ liệu), vì health_metrics chỉ lưu
        # NGÀY lấy mẫu, không có giờ, nên hiển thị "X giờ" ở đây là số liệu giả tạo không có thật.
        _tab_label = "Lần khám gần nhất"
        _month_word = f"{VN_MONTHS_WORD[_latest_date.month - 1]} {_latest_date.year}"
        _days_ago = (_today_vn() - _latest_date.date()).days
        _rel = "Hôm nay" if _days_ago == 0 else "Hôm qua" if _days_ago == 1 else f"{_days_ago} ngày trước"
        _meta = f"{_month_word} · {_rel}"
        render_period_billboard(_tab_label, str(_latest_date.day), _vn_dow, _meta, _right_html, _toc)
        _bc1, _bc2 = st.columns([5, 1])
        with _bc2:
            if st.button("Sửa lần khám này", key="hm_input_latest_edit"):
                st.session_state["_hm_sub_jump"] = "Lịch sử"
                st.rerun()

    # ==========================================
    # 1. IMPORT HÀNG LOẠT
    # ==========================================
    @st.dialog("Định dạng JSON mẫu")
    def _hm_json_example_dialog():
        st.code(json.dumps(HEALTH_METRICS_JSON_EXAMPLE, ensure_ascii=False, indent=2), language="json")

    sec_chapter("hm-in-ch1", 1, None, "Import hàng loạt", tight_top=True)
    st.caption("Dán JSON do Claude xuất ra sau khi đọc ảnh phiếu xét nghiệm — dùng để nạp nhanh dữ liệu "
                "nhiều lần khám cũ cùng lúc.")
    # Khối JSON mẫu để trong popup (st.dialog(), cùng khuôn "Khôi phục dữ liệu"/"Xoá toàn bộ dữ
    # liệu" ở Tuỳ biến) thay vì hiện trực tiếp -- xác nhận với người dùng: chỉ để tra cứu/copy khi
    # cần, không nên chiếm không gian mặc định của chương.
    if st.button("Xem định dạng JSON mẫu", key="hm_json_example_btn"):
        _hm_json_example_dialog()
    st.text_area("Dán nội dung JSON vào đây", height=200, key="hm_import_json")
    if st.button("Xem trước", key="hm_import_preview_btn"):
        try:
            parsed = json.loads(st.session_state.get("hm_import_json", "") or "[]")
            if not isinstance(parsed, list) or not parsed:
                raise ValueError("JSON phải là 1 danh sách (list) các lần xét nghiệm.")
            flat_rows = []
            for p in parsed:
                for ind in p.get("indicators", []):
                    flat_rows.append({
                        "Ngày lấy mẫu": p.get("test_date"), "Nhóm": p.get("category"),
                        "Chỉ số": ind.get("indicator"),
                        "Giá trị": ind.get("value_raw", ind.get("value")),
                        "Đơn vị": ind.get("unit"),
                        "Khoảng tham chiếu": ind.get("ref_raw", ind.get("ref_range")),
                    })
            if not flat_rows:
                raise ValueError("Không tìm thấy chỉ số nào trong dữ liệu đã dán.")
            st.session_state["hm_import_preview"] = parsed
            st.session_state["hm_import_preview_df"] = pd.DataFrame(flat_rows)
        except Exception as e:
            st.session_state.pop("hm_import_preview", None)
            st.session_state.pop("hm_import_preview_df", None)
            st.error(f"JSON không hợp lệ: {e}")
    if st.session_state.get("hm_import_preview") is not None:
        _prev_df = st.session_state["hm_import_preview_df"]
        _n_panels = len(st.session_state["hm_import_preview"])
        st.caption(f"Xem trước {len(_prev_df)} chỉ số từ {_n_panels} lần xét nghiệm:")
        st.dataframe(_prev_df, hide_index=True, width='stretch')
        if st.button("Xác nhận lưu", type="primary", key="hm_import_confirm_btn"):
            save_health_metrics_bulk(st.session_state["hm_import_preview"])
            _saved_n = len(_prev_df)
            st.session_state.pop("hm_import_preview", None)
            st.session_state.pop("hm_import_preview_df", None)
            st.session_state.pop("hm_import_json", None)
            st.success(f"Đã lưu {_saved_n} chỉ số từ {_n_panels} lần xét nghiệm.")
            time.sleep(1)
            st.rerun()

    # ==========================================
    # 2. NHẬP KẾT QUẢ XÉT NGHIỆM (nhập tay, 1 lần xét nghiệm mỗi lượt)
    # ==========================================
    sec_chapter("hm-in-ch2", 2, None, "Nhập kết quả xét nghiệm")
    existing_cats = sorted(df_health['Nhóm'].dropna().unique()) if not df_health.empty else []
    cat_options = sorted(set(["Huyết học", "Sinh hóa"]) | set(existing_cats)) + ["+ Nhóm khác..."]
    ic1, ic2 = st.columns(2)
    entry_date = ic1.date_input("Ngày lấy mẫu", value=_today_vn(), format="DD/MM/YYYY", key="hm_entry_date")
    cat_choice = ic2.selectbox("Nhóm", cat_options, key="hm_entry_cat_choice")
    entry_category = (st.text_input("Tên nhóm mới", key="hm_entry_cat_new")
                       if cat_choice == "+ Nhóm khác..." else cat_choice)
    _empty_rows = pd.DataFrame({"Chỉ số": [""] * 6, "Giá trị": [""] * 6,
                                 "Đơn vị": [""] * 6, "Khoảng tham chiếu": [""] * 6})
    entry_df = st.data_editor(
        _empty_rows, hide_index=True, width='stretch', num_rows="dynamic", key="hm_entry_editor",
        column_config={
            "Chỉ số": st.column_config.TextColumn("Chỉ số", width="large"),
            "Giá trị": st.column_config.TextColumn("Giá trị"),
            "Đơn vị": st.column_config.TextColumn("Đơn vị"),
            "Khoảng tham chiếu": st.column_config.TextColumn(
                "Khoảng tham chiếu", help='Vd "4.2 - 5.4", "< 5", "> 10"'),
        })
    if st.button("Lưu vào Supabase", type="primary", key="hm_entry_save"):
        rows = [r for r in entry_df.to_dict("records") if str(r["Chỉ số"]).strip()]
        if not entry_category or not str(entry_category).strip():
            st.error("Chưa chọn/nhập Nhóm.")
        elif not rows:
            st.error("Chưa nhập chỉ số nào.")
        else:
            panel = {"test_date": entry_date.isoformat(), "category": str(entry_category).strip(),
                      "indicators": [{"indicator": r["Chỉ số"], "value_raw": r["Giá trị"],
                                      "unit": r["Đơn vị"], "ref_raw": r["Khoảng tham chiếu"]}
                                     for r in rows]}
            save_health_metrics_bulk([panel])
            st.session_state.pop("hm_entry_editor", None)
            st.success(f"Đã lưu {len(rows)} chỉ số cho lần xét nghiệm {entry_date:%d/%m/%Y}.")
            time.sleep(1)
            st.rerun()


def render_health_page():
    """Trang "Sức khoẻ": theo dõi chỉ số xét nghiệm máu định kỳ. Khác với phần còn lại của app
    (thuần retrospective, đọc lại dữ liệu Forest) -- trang này CÓ nhập liệu tay, vì không có
    nguồn tự động nào xuất dữ liệu xét nghiệm ra file: người dùng chụp ảnh phiếu xét nghiệm, nhờ
    Claude đọc ảnh rồi dán JSON (đúng khuôn HEALTH_METRICS_JSON_EXAMPLE), hoặc gõ tay từng lần
    khám. 3 sub-tab cùng pattern segmented_control+query param với BAOCAO_SUBS (xem khai báo
    SUCKHOE_SUBS): Báo cáo (xem số liệu/biểu đồ) · Lịch sử (sửa/xoá) · Dữ liệu đầu vào (nhập)."""
    df_health = load_health_metrics()

    # Nút "Sửa" ở card "Lần khám gần nhất" (_render_health_input()) nhảy sang sub-tab Lịch sử qua
    # cờ chờ xử lý này -- KHÔNG set trực tiếp st.session_state["hm_sub_picker"] tại nút bấm, vì
    # lúc đó widget segmented_control DƯỚI ĐÂY đã instantiate rồi trong CÙNG lượt chạy (bug thật
    # đã gặp: StreamlitAPIException "cannot be modified after the widget... is instantiated") --
    # phải set key của widget TRƯỚC khi nó được gọi, nên phải xử lý ở đây, đầu trang, trước dòng
    # segmented_control, rồi mới rerun sang lượt chạy mới áp dụng được.
    if "_hm_sub_jump" in st.session_state:
        _jump = st.session_state.pop("_hm_sub_jump")
        st.session_state["hm_sub_picker"] = _jump
        st.session_state["hm_sub"] = _jump

    _sub_pick = st.segmented_control(
        "Xem theo", SUCKHOE_SUBS,
        format_func=lambda x: f"{SUCKHOE_SUB_ICONS_MD[x]} {x}",
        default=st.session_state["hm_sub"], key="hm_sub_picker", label_visibility="collapsed")
    if _sub_pick and _sub_pick != st.session_state["hm_sub"]:
        st.session_state["hm_sub"] = _sub_pick
    hm_sub = st.session_state["hm_sub"]
    st.query_params["hsub"] = hm_sub

    if hm_sub == "Báo cáo":
        _render_health_report(df_health)
    elif hm_sub == "Lịch sử":
        _render_health_history(df_health)
    elif hm_sub == "Dữ liệu đầu vào":
        _render_health_input(df_health)


def render_search():
    """Tìm kiếm theo từ khoá trên CẢ 6 nguồn: ghi chú chính, ghi chú nhanh, lịch (tiêu đề
    appointment), sách/Gundam (tên cuốn/series + tiêu đề phần), phiên Forest (tên Dự án), trích
    dẫn/ghi chú Kindle (nội dung) -- lọc trực tiếp trong Python trên text thuần, khối lượng dữ
    liệu nhỏ (vài trăm-nghìn dòng mỗi nguồn cho vài năm dùng app) nên không cần full-text search
    phía Supabase. Kết quả gộp theo NGÀY (đúng 1 dòng cho mỗi ngày có ít nhất 1 nguồn khớp), hiện
    ĐỦ 4 nguồn đầu của ngày đó (không chỉ riêng phần khớp) để giữ nguyên ngữ cảnh cả ngày -- đúng
    khuôn .jrows/.jrow + thứ tự Lịch -> Đọc sách -> Ghi chú nhanh -> Ghi chú chính đã dùng ở Nhật
    ký; riêng Phiên/Trích dẫn (2 nguồn có thể rất nhiều dòng/ngày) chỉ hiện ĐÚNG các dòng khớp,
    không hiện cả ngày, tránh rối mắt. Ghi chú nhanh cũng tìm được ở đây dù chỉ tồn tại tạm thời
    (chờ gộp vào ghi chú chính, xem render_note_editor()) -- tránh lọt mất nếu vài hôm chưa kịp
    gộp. Từ khớp được tô sáng bằng <mark> (xem _highlight()) trong mọi đoạn trích tự do (ghi chú,
    trích dẫn) -- các chip nguồn khác (lịch/sách) vốn đã ngắn gọn nên không cần tô thêm."""
    q = st.text_input("Từ khoá", key="search_q", label_visibility="collapsed")
    if not q or len(q.strip()) < 2:
        return
    qq = q.strip()
    pat = re.escape(qq)

    nd = load_notes()
    if not nd.empty:
        nd = nd.assign(_d=pd.to_datetime(nd['Ngày'], errors='coerce'),
                        _plain=nd['Ghi chú'].map(_note_plain_text)).dropna(subset=['_d'])
    qn = load_quick_notes()
    if not qn.empty:
        qn = qn.assign(_d=qn['Thời gian'].dt.normalize())
    wc = load_work_calendar()
    if not wc.empty:
        wc = wc.assign(_d=wc['Thời gian bắt đầu'].dt.normalize())
    rl = load_reading_log()
    if not rl.empty:
        rl = rl.assign(_d=rl['Ngày hoàn thành'].dt.normalize())
    db = load_db()
    if not db.empty:
        db = db.assign(_d=pd.to_datetime(db['Thời gian bắt đầu'], format='ISO8601').dt.normalize())
    kh = load_kindle_highlights()
    if not kh.empty:
        kh = kh.assign(_d=kh['Ngày thêm'].dt.normalize())

    note_hits = set(nd[nd['_plain'].str.contains(pat, case=False, na=False)]['_d']) if not nd.empty else set()
    qn_hits = set(qn[qn['Nội dung'].astype(str).str.contains(pat, case=False, na=False)]['_d']) if not qn.empty else set()
    cal_hits = set(wc[wc['Tiêu đề'].astype(str).str.contains(pat, case=False, na=False)]['_d']) if not wc.empty else set()
    rl_hits = set(rl[rl['Tiêu đề phần'].astype(str).str.contains(pat, case=False, na=False)
                     | rl['Cuốn sách'].astype(str).str.contains(pat, case=False, na=False)]['_d']) if not rl.empty else set()
    sess_hits = set(db[db['Dự án'].astype(str).str.contains(pat, case=False, na=False)]['_d']) if not db.empty else set()
    kh_hits = set(kh[kh['Nội dung'].astype(str).str.contains(pat, case=False, na=False)]['_d']) if not kh.empty else set()

    hit_days = sorted(note_hits | qn_hits | cal_hits | rl_hits | sess_hits | kh_hits, reverse=True)
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
        sess_html = ''
        day_sess = (db[(db['_d'] == d) & db['Dự án'].astype(str).str.contains(pat, case=False, na=False)]
                    if not db.empty else db)
        if not day_sess.empty:
            chips = ''.join(
                f"<span class='jchip'><span class='ck'>{pd.to_datetime(r['Thời gian bắt đầu']):%H:%M}</span>"
                f"<span class='cv'>{_highlight(r['Dự án'], qq)}</span></span>"
                for _, r in day_sess.sort_values('Thời gian bắt đầu').iterrows())
            sess_html = _chip_row_html('Phiên', chips)
        read_html = _book_chips_html(rl[rl['_d'] == d]) if not rl.empty and d in set(rl['_d']) else ''
        quote_html = ''
        day_kh = (kh[(kh['_d'] == d) & kh['Nội dung'].astype(str).str.contains(pat, case=False, na=False)]
                  if not kh.empty else kh)
        if not day_kh.empty:
            items = ''.join(
                "<div class='note-html' style='margin-bottom:4px;'>“"
                f"{_highlight(_snippet_around(str(r['Nội dung']), qq), qq)}”"
                f" <span style='color:var(--text-2);font-size:12px;'>— {html_escape(str(r['Cuốn sách']))}</span></div>"
                for _, r in day_kh.iterrows())
            quote_html = _chip_row_html('Trích dẫn', items)
        qn_html = _quick_note_chips_html(qn[qn['_d'] == d]) if not qn.empty and d in set(qn['_d']) else ''
        note_html = ''
        if not nd.empty and d in set(nd['_d']):
            note_html = f"<div class='note-html'>{_highlight(_note_snippet(nd[nd['_d'] == d].iloc[0]['Ghi chú'], qq), qq)}</div>"
        _href = f"?nav={quote('Hôm nay')}&day={d:%Y-%m-%d}"
        rows_html += (
            "<div class='jrow'>"
            f"<a class='jdate-link' href='{_href}' target='_self'>"
            f"<div class='jdate'><div class='jdowbig'>{VN_DAYS.get(d.day_name(), '')}</div>"
            f"<div class='jdm'>{d:%d/%m/%Y}</div></div></a>"
            f"<div>{cal_html}{sess_html}{read_html}{quote_html}{qn_html}{note_html}</div>"
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
                        for _, r in g.sort_values('Ngày hoàn thành', kind='stable').iterrows())
        out += _chip_row_html(html_escape(book), parts)
    return out


def _reading_rows_html(rl_df, label_book=True, sort_desc=False):
    """HTML .jrows cho các phần đã đọc (rl_df đã lọc sẵn theo kỳ/sách cần hiện) -- một dòng cho
    mỗi ngày có ≥1 phần hoàn thành. label_book=False dùng khi caller đã lọc đúng 1 cuốn (Báo
    cáo theo dự án) -- bỏ nhãn tên sách vì thừa. sort_desc=True -> ngày MỚI NHẤT lên đầu (Sách ->
    Tổng quan, mockup xếp "Nhật ký đọc" theo kiểu tin mới lên trên) -- mặc định False (cũ nhất
    trước) giữ nguyên hành vi mọi chỗ gọi khác (đọc tuần tự từ đầu)."""
    rl = rl_df.assign(_d=rl_df['Ngày hoàn thành'].dt.normalize())
    rows_html = ''
    _groups = list(rl.groupby('_d'))
    if sort_desc:
        _groups = _groups[::-1]
    for d, day_g in _groups:
        if label_book:
            chips_html = _book_chips_html(day_g)
        else:
            _cls = 'jchip gundam' if _is_gundam_list(day_g['Sách (gốc)'].iloc[0]) else 'jchip book'
            chips_html = ''.join(f"<span class='{_cls}'>{html_escape(str(r['Tiêu đề phần']))}</span>"
                                 for _, r in day_g.sort_values('Ngày hoàn thành', kind='stable').iterrows())
        _href = f"?nav={quote('Hôm nay')}&day={d:%Y-%m-%d}"
        rows_html += (
            "<div class='jrow'>"
            f"<a class='jdate-link' href='{_href}' target='_self'>"
            f"<div class='jdate'><div class='jdowbig'>{VN_DAYS.get(d.day_name(), '')}</div>"
            f"<div class='jdm'>{d:%d/%m}</div></div></a>"
            f"<div>{chips_html}</div></div>"
        )
    return rows_html


def _render_reading_kindle_days(rl_df, kh_df, df_books=None):
    """Bản CÓ TƯƠNG TÁC của mục "2. Nhật ký đọc" (Sách/Gundam -> Chi tiết) -- CHỈ dùng ở đúng 1
    chỗ gọi này (_render_reading_detail()), khác _reading_rows_html() (HTML tĩnh, dùng ở nhiều nơi
    khác -- Tìm kiếm, Ghi chú ngày... -- không cần sửa/xoá). Mỗi ngày là 1 hàng THẬT
    (st.columns([1,5])), cùng khuôn 2 cột với "Ghi chú ngày" (xem render_note_editor()) vì cột nội
    dung giờ có nút Sửa/Xoá/+ Ghi chú thật (st.button), không thể nhét vào 1 khối HTML tĩnh như
    .jrows nữa.

    Quote/note trong ngày xếp theo "Vị trí" Kindle TĂNG DẦN (_kindle_location_sort_key), KHÔNG
    theo giờ thêm vào và KHÔNG có nút sắp xếp tay -- quyết định đã chốt với người dùng sau khi cân
    nhắc 2 phương án phức tạp hơn (tự suy luận quote thuộc chương nào theo giờ hoàn thành gần
    nhất, và nút ▲▼ sắp tay): Reminders chỉ ghi NGÀY hoàn thành chương (không có giờ), nên không
    có cách nào đáng tin để biết quote thuộc đúng chương nào trong 1 ngày đọc nhiều chương; "Vị
    trí" tăng dần theo đúng thứ tự trang sách lại TỰ NHIÊN phản ánh đúng thứ tự đọc thật (đọc tuần
    tự), nên không cần gán/sắp tay gì thêm mà vẫn ra đúng thứ tự mong muốn.

    df_books (tuỳ chọn): cho phép tính chip "Thời gian" (tổng phút phiên Forest của đúng cuốn này
    trong đúng ngày đó -- KHÔNG phải dữ liệu mới, chỉ cross-reference session Forest đã có). CỐ Ý
    KHÔNG hiện "Ghi chú ngày"/"Ghi chú nhanh" ở đây (khác Nhật ký Báo cáo Tuần/Tháng,
    render_notes_journal()) -- xác nhận với người dùng mục này chỉ cần đúng Phần/Chương đọc + Thời
    gian, không cần kéo thêm ghi chú chung của ngày vào (từng thử thêm rồi bỏ lại theo phản hồi
    thực tế)."""
    rl = rl_df.assign(_d=rl_df['Ngày hoàn thành'].dt.normalize()) if not rl_df.empty else rl_df
    kh = kh_df.copy()
    if not kh.empty:
        kh['_d'] = kh['Ngày thêm'].dt.normalize()
        kh['_loc_key'] = kh['Vị trí'].map(_kindle_location_sort_key)
    rl_days = set(rl['_d'].dropna().unique()) if not rl_df.empty else set()
    kh_days = set(kh['_d'].dropna().unique()) if not kh.empty else set()
    for i, d in enumerate(sorted(rl_days | kh_days)):
        day_rl = rl[rl['_d'] == d] if not rl_df.empty else rl_df.iloc[0:0]
        day_kh = kh[kh['_d'] == d].sort_values('_loc_key') if not kh.empty else kh
        with st.container(key=f"jkq_row_{i}"):
            c_date, c_body = st.columns([1, 5])
            with c_date:
                st.markdown(f"<div class='jdate'><div class='jdowbig'>{VN_DAYS.get(d.day_name(), '')}</div>"
                            f"<div class='jdm'>{d:%d/%m/%Y}</div></div>", unsafe_allow_html=True)
            with c_body:
                if not day_rl.empty:
                    _cls = 'jchip gundam' if _is_gundam_list(day_rl['Sách (gốc)'].iloc[0]) else 'jchip book'
                    chips = ''.join(f"<span class='{_cls}'>{html_escape(str(r['Tiêu đề phần']))}</span>"
                                    for _, r in day_rl.sort_values('Ngày hoàn thành', kind='stable').iterrows())
                    if df_books is not None and not df_books.empty:
                        _book = str(day_rl['Cuốn sách'].iloc[0])
                        _mins = df_books[(df_books['Dự án'] == _book)
                                          & (df_books['Ngày'] == d.date())]['Thời lượng (Phút)'].sum()
                        if _mins > 0:
                            chips += (f"<span class='jchip'><span class='ck'>Thời gian</span>"
                                      f"<span class='cv'>{int(_mins)}′</span></span>")
                    st.markdown(chips, unsafe_allow_html=True)
                if not day_kh.empty:
                    _render_kindle_day_quotes(day_kh)


def _render_kindle_day_quotes(day_kh):
    """Vẽ toàn bộ quote/note Kindle của 1 ngày (day_kh đã lọc + sắp theo _loc_key sẵn) -- lồng ghi
    chú xuống dưới đúng highlight nó thuộc về theo 2 cách: (a) ghi chú BẠN TỰ THÊM trong app (nút
    "+", xem add_kindle_note()) luôn có parent_hash trỏ thẳng về highlight đó -- quan hệ CHẮC CHẮN
    lưu trong DB; (b) ghi chú GỐC TỪ KINDLE (nhập từ Clippings.txt, parent_hash luôn NULL) được
    lồng bằng SUY LUẬN HIỂN THỊ LÚC RENDER: khớp "Vị trí" trùng với 1 highlight cùng ngày -- chỉ
    là cách trình bày, không lưu quan hệ này vào DB (xem delete_kindle_highlight() -- vì lý do
    này, xoá highlight KHÔNG kéo theo xoá note Kindle độc lập chỉ đang lồng hiển thị cạnh nó kiểu
    (b)). Ghi chú không khớp được highlight nào (dù theo cách nào) hiện đứng riêng như 1 dòng bình
    thường theo đúng thứ tự Vị trí, không bị mất."""
    by_hash = {r['dedupe_hash']: r for _, r in day_kh.iterrows()}
    children = {}
    is_child = set()
    for _, r in day_kh.iterrows():
        if r['Loại'] != 'note':
            continue
        ph = r.get('parent_hash')
        if pd.notna(ph) and ph in by_hash:
            children.setdefault(ph, []).append(r)
            is_child.add(r['dedupe_hash'])
        else:
            loc = r['Vị trí']
            if pd.notna(loc):
                _match = day_kh[(day_kh['Loại'] == 'highlight') & (day_kh['Vị trí'] == loc)]
                if not _match.empty:
                    ph2 = _match.iloc[0]['dedupe_hash']
                    children.setdefault(ph2, []).append(r)
                    is_child.add(r['dedupe_hash'])
    for _, r in day_kh.iterrows():
        if r['dedupe_hash'] in is_child:
            continue
        _render_kindle_quote_row(r)
        for child in sorted(children.get(r['dedupe_hash'], []), key=lambda c: str(c.get('Ngày thêm'))):
            _render_kindle_quote_row(child, is_reply=True)


def _render_kindle_quote_row(r, is_reply=False, key_suffix="", show_added_date=False):
    """1 dòng quote/note Kindle + cụm nút Yêu thích/Sửa/Xoá/+ Ghi chú -- cùng bố cục hàng thật
    (st.columns) và cùng phong cách nút (icon nhỏ, nền trong suốt) với hàng "Ghi chú nhanh"
    (qnote_row) trong render_note_editor(): đọc = chữ + icon mờ bám phải; bấm Sửa = textarea +
    ✓ Cập nhật/✕ Huỷ; bấm + = ô nhập ghi chú mới bên dưới + ✓ Lưu/✕ Huỷ. Xoá KHÔNG hỏi xác nhận
    (giống hệt Ghi chú nhanh) -- quyết định đã chốt với người dùng. is_reply=True (ghi chú đang
    lồng dưới 1 highlight) -> thụt lề riêng qua CSS ([class*="st-key-kqreply_"]) + KHÔNG có nút
    "+" (ghi chú không trả lời được ghi chú).

    key_suffix: cùng 1 highlight (dedupe_hash) có thể được vẽ ở HAI nơi khác nhau trong CÙNG 1
    lần chạy trang -- vd 1 trích dẫn Yêu thích của cuốn đang mở ở "Chi tiết" cũng xuất hiện lại ở
    sub-tab "Yêu thích" ngay bên cạnh (st.tabs() vẽ HẾT mọi tab trong 1 lần chạy, không chỉ tab
    đang active). 2 lần gọi cùng dùng key mặc định sẽ đụng khoá (StreamlitDuplicateElementKey) --
    nơi gọi thứ 2 (vd _render_kindle_favorites_tab()) PHẢI truyền key_suffix riêng để tách khoá.
    Chèn NGAY TRƯỚC hash (giữa tiền tố cố định "kqrow_"/"kqreply_"/"kqnew_" và hash) thay vì đặt ở
    đầu toàn bộ key -- giữ nguyên các tiền tố này làm chuỗi con để CSS
    ([class*="st-key-kqrow_"] v.v.) vẫn khớp bất kể key_suffix là gì.

    show_added_date=True (chỉ dùng ở sub-tab "Yêu thích", xem _render_kindle_favorites_tab()) --
    thêm "· lưu DD/MM/YYYY" ngay sau vị trí, dùng ĐÚNG "Ngày thêm" (mốc nhập từ Kindle, KHÔNG phải
    mốc bấm ⭐ Yêu thích thật -- cột đó không tồn tại trong schema, xác nhận với người dùng dùng
    tạm mốc thêm gốc thay vì thêm cột mới) làm proxy cho "mới lưu nhất"."""
    h = r['dedupe_hash']
    edit_key = f"kq_edit_{key_suffix}{h}"
    addnote_key = f"kq_addnote_{key_suffix}{h}"
    with st.container(key=f"kq{'reply' if is_reply else 'row'}_{key_suffix}{h}"):
        rc1, rc2 = st.columns([15, 3])
        if st.session_state.get(edit_key, False):
            with rc1:
                st.text_area("Sửa", value=str(r['Nội dung']), key=f"kq_input_{key_suffix}{h}",
                             label_visibility="collapsed", height=68)
            with rc2:
                with st.container(horizontal=True, gap="small"):
                    if st.button("", icon=":material/check:", key=f"kq_save_{key_suffix}{h}", help="Cập nhật"):
                        update_kindle_highlight_content(h, st.session_state.get(f"kq_input_{key_suffix}{h}", ""))
                        st.session_state[edit_key] = False
                        st.rerun()
                    if st.button("", icon=":material/close:", key=f"kq_canceledit_{key_suffix}{h}", help="Huỷ"):
                        st.session_state[edit_key] = False
                        st.rerun()
        else:
            with rc1:
                _mark = '“' if r['Loại'] == 'highlight' else '✎'
                _style = "font-style:italic;color:var(--text-2);" if r['Loại'] == 'note' else ''
                # "Vị trí" gộp chung 2 dạng gốc từ Kindle (location SỐ, hoặc "trang N" -- xem
                # parse_kindle_clippings()) -- phải PHÂN BIỆT tiền tố hiển thị, không được luôn
                # gán cứng "vị trí" phía trước (bug thật: ra "· vị trí trang 402" cho sách dùng
                # số trang thay vì vị trí Kindle).
                _loc_val = str(r['Vị trí']) if pd.notna(r['Vị trí']) and str(r['Vị trí']).strip() else ""
                _loc_label = _loc_val if _loc_val.lower().startswith('trang ') else (
                    f"vị trí {_loc_val}" if _loc_val else "")
                _loc = f" <span class='kq-loc'>· {_loc_label}</span>" if _loc_label else ""
                _added = (f" <span class='kq-loc'>· lưu {pd.Timestamp(r['Ngày thêm']):%d/%m/%Y}</span>"
                          if show_added_date and pd.notna(r.get('Ngày thêm')) else "")
                st.markdown(
                    f"<div style='font-size:14.5px;line-height:1.6;{_style}'>"
                    f"<span class='kq-mark'>{_mark}</span>{html_escape(str(r['Nội dung']))}{_loc}{_added}</div>",
                    unsafe_allow_html=True)
            with rc2:
                with st.container(horizontal=True, gap="small"):
                    _fav = bool(r.get('Yêu thích', False))
                    if st.button("★" if _fav else "☆",
                                 key=f"kq_favbtn_{'on' if _fav else 'off'}_{key_suffix}{h}",
                                 help="Bỏ Yêu thích" if _fav else "Yêu thích"):
                        set_kindle_highlight_favorite(h, not _fav)
                        st.rerun()
                    if not is_reply:
                        if st.button("", icon=":material/add_comment:", key=f"kq_addbtn_{key_suffix}{h}", help="Thêm ghi chú"):
                            st.session_state[addnote_key] = True
                            st.rerun()
                    if st.button("", icon=":material/edit:", key=f"kq_editbtn_{key_suffix}{h}", help="Sửa"):
                        st.session_state[edit_key] = True
                        st.rerun()
                    if st.button("", icon=":material/delete:", key=f"kq_delbtn_{key_suffix}{h}", help="Xoá"):
                        delete_kindle_highlight(h)
                        st.rerun()
        if not is_reply and st.session_state.get(addnote_key, False):
            with st.container(key=f"kqnew_{key_suffix}{h}"):
                nc1, nc2 = st.columns([15, 3])
                with nc1:
                    st.text_area("Ghi chú mới", key=f"kq_newnote_{key_suffix}{h}", label_visibility="collapsed",
                                 height=60, placeholder="Viết ghi chú của bạn...")
                with nc2:
                    with st.container(horizontal=True, gap="small"):
                        if st.button("", icon=":material/check:", key=f"kq_newsave_{key_suffix}{h}", help="Lưu"):
                            _txt = st.session_state.get(f"kq_newnote_{key_suffix}{h}", "")
                            if _txt.strip():
                                add_kindle_note(r, _txt)
                            st.session_state[addnote_key] = False
                            st.rerun()
                        if st.button("", icon=":material/close:", key=f"kq_newcancel_{key_suffix}{h}", help="Huỷ"):
                            st.session_state[addnote_key] = False
                            st.rerun()


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
            _chips = _chip("Giờ", f"{_fmt_hours_short(hrs)}") + _chip("Số phiên", f"{ss}") + _chip("TB", f"{avg:.0f}′")
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
    cal_data['Giờ_txt'] = cal_data['Số giờ'].map(_fmt_hours_long)
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

    # Nhãn trục (tháng phía trên + Thứ bên trái) theo đúng font/cỡ/màu mockup "Sổ Tay" (IBM Plex
    # Mono 9px, màu mờ text-3) -- Vega không đọc được biến CSS var(--text-3), phải tự chọn literal
    # theo IS_DARK giống cách _txt_hi/_txt_lo bên dưới đã làm.
    _axis_lbl = "#857a5f" if IS_DARK else "#a39877"
    enc_x = alt.X('yearmonthdate(Tuần_Bắt_Đầu):O', title='',
                  scale=alt.Scale(paddingInner=0.06),
                  axis=alt.Axis(labelAngle=0, orient='top', tickSize=0, domain=False,
                                labelFont='IBM Plex Mono', labelFontSize=9, labelColor=_axis_lbl,
                                labelExpr="month(datum.value) != month(datum.value - 7*24*60*60*1000) ? 'Th' + (month(datum.value)+1) : ''"))
    enc_y = alt.Y('Thứ:O', sort=DAYS_ORDER, title='',
                  scale=alt.Scale(domain=DAYS_ORDER, paddingInner=0.06),
                  axis=alt.Axis(tickSize=0, domain=False, labelFont='IBM Plex Mono', labelFontSize=9,
                                labelColor=_axis_lbl))
    cal_tooltip = [alt.Tooltip('Ngày_str:T', format='%d-%m-%Y', title='Ngày'),
                   alt.Tooltip('Giờ_txt:N', title='Giờ')]
    base = alt.Chart(cal_data).encode(x=enc_x, y=enc_y)
    # cornerRadius 5 (không phải 3) -- khớp bo góc ô ngày trong mockup "Sổ Tay", mềm hơn 1 chút so
    # với bản cũ mà vẫn không quá tròn tới mức mất dáng vuông của lưới kiểu GitHub.
    rect = base.mark_rect(cornerRadius=5).encode(
        color=alt.Color('lvl:O', scale=alt.Scale(domain=list(range(8)), range=LVL_COLORS), legend=None),
        tooltip=cal_tooltip
    )
    # lvl 6,7 (2 bậc teal đậm nhất ở light) đủ tối để cần chữ trắng, còn lại chữ xám mờ. Ramp teal
    # ĐẢO CHIỀU khi dark (xem _teal_shades) -> điều kiện sáng/tối của chữ cũng đảo theo.
    _txt_hi, _txt_lo = ("#1c1c1e", "#98989d") if IS_DARK else ("#ffffff", "#a7a7ac")
    text = base.mark_text(baseline='middle', fontSize=10, font='IBM Plex Mono').encode(
        text='day:Q',
        color=alt.condition("datum.lvl >= 6", alt.value(_txt_hi), alt.value(_txt_lo)),
        tooltip=cal_tooltip
    )
    chart = (rect + text).properties(
        width=alt.Step(34), height=alt.Step(34),
        # left=52 chừa đủ chỗ cho nhãn "Thứ" dạng chữ đầy đủ (vd "Chủ Nhật", 8 ký tự) -- để left=0
        # như bản cũ (thời nhãn còn ngắn dạng số/viết tắt) khiến Vega tính thiếu bề rộng trục dọc,
        # nhãn tràn ra ngoài biên trái của SVG và bị cắt chữ (lỗi thật đã gặp, xem ảnh chụp). right
        # nhỏ hơn trái để bù lại, giữ lưới không bị lệch hẳn sang phải trong thẻ.
        padding={"left": 52, "right": 12, "top": 5, "bottom": 5},
        # Vega tự vẽ nền riêng cho SVG (mặc định ăn theo màu nền trang, không phải trắng) -> để
        # trong suốt cho nền thẻ bọc ngoài (--card, đổi theo IS_DARK) lộ ra, tránh viền lệch tông.
        background='transparent',
    ).configure_view(strokeWidth=0)
    st.altair_chart(chart, width='content')


def render_year_month_bars(df_y):
    """Chương "Theo tháng" (Báo cáo -> Năm, mockup): 12 cột Th1-Th12, mỗi cột = tổng giờ tháng đó
    TRONG NĂM ĐANG CHỌN -- tô đậm/nhạt theo tỉ lệ so với tháng cao nhất (cùng thang teal với
    Biểu đồ lịch, xem _teal_shades) để 2 chương liền kề đồng bộ 1 họ màu. Tháng chưa có dữ liệu
    (chưa tới hoặc trống) hiện cột cao 0 (chỉ còn trục nền) -- KHÔNG bỏ hẳn khỏi trục, để vẫn thấy
    đủ 12 tháng như 1 lịch năm, đúng bố cục mockup."""
    hrs_by_month = df_y.groupby(pd.to_datetime(df_y['Ngày']).dt.month)['Thời lượng (Phút)'].sum() / 60
    hrs_by_month = hrs_by_month.reindex(range(1, 13), fill_value=0.0)
    max_hrs = hrs_by_month.max() or 1.0
    shades = _teal_shades(6)
    colors = [shades[min(int(h / max_hrs * 5), 5)] if h > 0 else "rgba(0,0,0,0)" for h in hrs_by_month]
    fig = go.Figure(go.Bar(x=[f"Th{m}" for m in range(1, 13)], y=list(hrs_by_month), marker_color=colors))
    fig = format_plotly_fig(fig)
    fig.update_layout(showlegend=False, yaxis=dict(title="Số giờ"))
    st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)


def render_year_category_bars(df_y, df, prev_year_key, elapsed_mask_y):
    """Chương "Danh mục cả năm" (Báo cáo -> Năm, mockup): thanh ngang xếp hạng theo Danh mục --
    CÙNG khuôn frag_category_bars() (thanh fill dài tỉ lệ theo TỔNG cả năm, màu theo COLOR_MAP)
    nhưng KHÔNG có toggle Danh mục/Dự án (mockup chỉ vẽ Danh mục) và có thêm % so với CÙNG KỲ
    năm trước ngay sau giá trị giờ (elapsed_mask_y -- cùng logic công bằng đã dùng cho billboard/
    Tổng quan, không so năm dở dang với 1 năm đầy đủ)."""
    if df_y.empty:
        st.caption("Chưa có dữ liệu.")
        return
    total_min = df_y['Thời lượng (Phút)'].sum()
    cat_now = df_y.groupby('Danh mục')['Thời lượng (Phút)'].sum().sort_values(ascending=False)
    prev_scope = (df[(df['Năm'] == prev_year_key) & elapsed_mask_y] if elapsed_mask_y is not None
                  else df[df['Năm'] == prev_year_key])
    cat_prev = prev_scope.groupby('Danh mục')['Thời lượng (Phút)'].sum()
    rows_html = ""
    for i, (name, mins) in enumerate(cat_now.items()):
        pct = mins / total_min * 100 if total_min else 0
        color = COLOR_MAP.get(name, MAC_COLORS[i % len(MAC_COLORS)])
        _chg = ""
        _prev_v = cat_prev.get(name)
        if _prev_v and _prev_v > 0:
            _pct_chg = (mins - _prev_v) / _prev_v * 100
            _col = "#34c759" if _pct_chg > 0 else "#ff3b30" if _pct_chg < 0 else "var(--text-2)"
            _chg = f" <span style='color:{_col};font-weight:600;'>{_pct_chg:+.0f}%</span>"
        rows_html += (
            "<div class='catbar-row wide'>"
            f"<span class='catbar-label'>{html_escape(str(name))}</span>"
            f"<span class='catbar-track'><span class='catbar-fill' "
            f"style='width:{pct:.1f}%;background:{color};'></span></span>"
            f"<span class='catbar-val'>{_fmt_hours_short(mins/60)}{_chg}</span></div>")
    st.markdown(
        f"<div class='catbars-card'><div class='catbars'>{rows_html}</div>"
        f"<div class='catbars-top'>% so với cùng kỳ {prev_year_key}</div></div>",
        unsafe_allow_html=True)


def _longest_streak_range(scope_df):
    """Chuỗi liên tiếp DÀI NHẤT trong scope_df -- trả (ngày đầu, ngày cuối, độ dài) hoặc None nếu
    rỗng. Tính lại từ đầu (không tái dùng _streak_stats(), hàm đó chỉ trả SỐ NGÀY của chuỗi HIỆN
    TẠI/DÀI NHẤT, không có ngày đầu/cuối) -- cần cho chip "Chuỗi dài nhất (dd/mm – dd/mm)" ở
    chương "Kỷ lục năm"."""
    u = pd.Series(pd.to_datetime(scope_df['Ngày'].dropna().unique())).sort_values().reset_index(drop=True)
    if len(u) == 0:
        return None
    sid = (u.diff().dt.days > 1).cumsum()
    best_sid = sid.value_counts().idxmax()
    best_run = u[sid == best_sid]
    return best_run.iloc[0].date(), best_run.iloc[-1].date(), len(best_run)


def render_year_highlights(df_y, active_days_y, elapsed_days_y, selected_year):
    """"Kỷ lục năm" (Báo cáo -> Năm): 2 thẻ -- "Kỷ lục {năm}" (ngày dài nhất/chuỗi liên tiếp dài
    nhất kèm khoảng ngày/tuần cao nhất, tất cả tính RIÊNG trong năm đang chọn qua df_y, KHÔNG phải
    kỷ lục toàn thời gian) và "Nhịp cả năm" (ngày hoạt động/elapsed, TB giờ mỗi ngày hoạt động +
    mỗi tuần, thứ năng suất nhất). Không còn là chương riêng -- gộp vào cuối chương "Tổng quan"
    (cùng cách xử lý "Điểm nhấn" ở nhánh Tháng). active_days_y/elapsed_days_y nhận từ billboard
    (đã tính sẵn ở đó, tránh tính lại)."""
    if df_y.empty:
        st.caption("Chưa có dữ liệu.")
        return
    # Cùng pattern ép 2 thẻ cao bằng nhau đã dùng ở "Điểm nhấn" (Báo cáo -> Tháng, xem
    # month-hl-card) -- rule chung align-items:flex-start khiến 2 cột co theo nội dung riêng.
    st.markdown(
        "<style>[data-testid=\"stHorizontalBlock\"]:has(.year-hl-card) "
        "{ align-items: stretch !important; }</style>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        by_day_y = df_y.groupby('Ngày')['Thời lượng (Phút)'].sum()
        _busiest_date = by_day_y.idxmax()
        _busiest_hrs = by_day_y.max() / 60
        _streak_range = _longest_streak_range(df_y)
        _wk_hrs_y = df_y.groupby('Tuần')['Thời lượng (Phút)'].sum()
        _items = [f"{_mi('emoji_events')} Ngày dài nhất · {_busiest_date:%d/%m} · {_fmt_hours_short(_busiest_hrs)}"]
        if _streak_range:
            _s, _e, _n = _streak_range
            _items.append(f"{_mi('local_fire_department')} Chuỗi dài nhất · {_n} ngày ({_s:%d/%m} – {_e:%d/%m})")
        if len(_wk_hrs_y):
            _best_wk = _wk_hrs_y.idxmax()
            _items.append(f"{_mi('calendar_month')} Tuần cao nhất · T{_best_wk.split('-W')[1]} · "
                           f"{_fmt_hours_short(_wk_hrs_y.max()/60)}")
        _items_html = "".join(f"<div class='hlt-item'>{it}</div>" for it in _items)
        st.markdown(
            "<div class='glass-card year-hl-card' style='padding:14px 18px;height:100%;'>"
            f"<span class='rl-book'>Kỷ lục {selected_year}</span>"
            f"<div class='hlt-list'>{_items_html}</div></div>", unsafe_allow_html=True)

    with c2:
        _pct_active = active_days_y / elapsed_days_y * 100 if elapsed_days_y else 0
        _num_weeks_y = df_y['Tuần'].nunique() or 1
        _tb_day = df_y['Thời lượng (Phút)'].sum() / 60 / (active_days_y or 1)
        _tb_week = df_y['Thời lượng (Phút)'].sum() / 60 / _num_weeks_y
        wd_y = _weekday_avg(df_y)
        _items2 = [f"Ngày hoạt động {active_days_y}/{elapsed_days_y} ({_pct_active:.0f}%)",
                   f"TB ngày hoạt động {_fmt_hours_short(_tb_day)} · TB tuần {_fmt_hours_short(_tb_week)}"]
        if len(wd_y) and wd_y.max() > 0:
            _items2.append(f"Thứ năng suất nhất <b>{wd_y.idxmax()}</b> (TB {_fmt_hours_short(wd_y.max())})")
        _items2_html = "".join(f"<div class='hlt-item'>{it}</div>" for it in _items2)
        st.markdown(
            "<div class='glass-card year-hl-card' style='padding:14px 18px;height:100%;'>"
            "<span class='rl-book'>Nhịp cả năm</span>"
            f"<div class='hlt-list'>{_items2_html}</div></div>", unsafe_allow_html=True)


def render_month_week_bars(df_m):
    """Chương "Theo tuần trong tháng" (Báo cáo -> Tháng, mockup): mỗi tuần ISO có chạm tháng đang
    chọn 1 hàng thanh ngang -- nhãn "T{tuần} · {đầu tuần}–{cuối tuần}" (khoảng ISO ĐẦY ĐỦ, có thể
    tràn qua tháng liền kề ở 2 đầu tháng) + giá trị {giờ} · {số phiên} bên phải (CHỈ tính phần
    NẰM TRONG tháng đang chọn, vì df_m đã lọc theo tháng trước khi truyền vào -- 1 tuần giao 2
    tháng sẽ có 2 hàng riêng ở trang của mỗi tháng, mỗi hàng chỉ cộng đúng phần ngày thuộc tháng
    đó). Thanh fill dài tỉ lệ theo TỔNG cả tháng, cùng quy ước với frag_category_bars(). Dùng CSS
    riêng .wkbar-* (KHÔNG tái dùng .catbar-* vì cột nhãn/giá trị ở đó quá hẹp cho text dài "T27 ·
    29/06 – 05/07"/"16h25 · 20 phiên"). Tuần TRÙNG tuần hiện tại (chưa qua hết 7 ngày) có dấu * +
    chú thích cuối bảng, tránh hiểu nhầm số liệu tuần đó đã đầy đủ."""
    if df_m.empty:
        st.caption("Chưa có dữ liệu.")
        return
    total_min = df_m['Thời lượng (Phút)'].sum()
    wk_g = df_m.groupby('Tuần')['Thời lượng (Phút)'].agg(['sum', 'size'])
    wk_g = wk_g.reindex(sorted(wk_g.index))
    _cur_wk = _today_vn().strftime('%G-W%V')
    rows_html = ""
    _has_current = False
    for wk, row in wk_g.iterrows():
        wy, wn = wk.split('-W')
        wk_start = date.fromisocalendar(int(wy), int(wn), 1)
        wk_end = wk_start + timedelta(days=6)
        pct = row['sum'] / total_min * 100 if total_min else 0
        _star = ""
        if wk == _cur_wk:
            _star = "*"
            _has_current = True
        rows_html += (
            "<div class='wkbar-row'>"
            f"<span class='wkbar-label'>T{int(wn)} · {wk_start:%d/%m} – {wk_end:%d/%m}{_star}</span>"
            f"<span class='wkbar-track'><span class='wkbar-fill' style='width:{pct:.1f}%;'></span></span>"
            f"<span class='wkbar-val'>{_fmt_hours_short(row['sum']/60)} · {int(row['size'])} phiên</span></div>")
    _foot = "<div class='catbars-top'>* tuần hiện tại, chưa kết thúc</div>" if _has_current else ""
    st.markdown(f"<div class='catbars-card'><div class='catbars'>{rows_html}</div>{_foot}</div>",
                unsafe_allow_html=True)


def render_month_highlights(df_m, df, prev_month_key, elapsed_mask_m, prev_m):
    """"Điểm nhấn" (Báo cáo -> Tháng): 2 thẻ ngang tóm tắt nhanh -- "Kỷ lục trong tháng" (ngày dài
    nhất/phiên dài nhất kèm tên dự án/chuỗi liên tiếp dài nhất, tất cả tính RIÊNG trong tháng đang
    chọn qua df_m, KHÔNG phải kỷ lục toàn thời gian) và "So với tháng trước" (4 dòng delta: tổng
    giờ/số phiên/danh mục tăng-giảm rõ nhất/TB giờ mỗi ngày hoạt động). Không còn là chương riêng
    (đã gộp vào cuối chương "Tổng quan", xác nhận lại với người dùng) -- chấp nhận vài dòng lặp
    lại thông tin đã có ở billboard/hero (Ngày dài nhất, 3 delta tổng) vì đây là 1 khối "tóm tắt
    nhanh" bổ sung, không bắt buộc tránh lặp hoàn toàn như billboard Dự án."""
    if df_m.empty:
        st.caption("Chưa có dữ liệu.")
        return
    # 2 thẻ cao KHÔNG bằng nhau mặc định (rule chung [data-testid="stHorizontalBlock"]
    # { align-items: flex-start !important; } khiến mỗi cột co theo đúng chiều cao nội dung riêng)
    # -- :has(.month-hl-card) chọn đúng hàng này rồi ép stretch, cùng pattern đã dùng cho 3 thẻ
    # Sao lưu/Khôi phục/Tài khoản ở Tuỳ biến (xem .st-key-tb_backup_card).
    st.markdown(
        "<style>[data-testid=\"stHorizontalBlock\"]:has(.month-hl-card) "
        "{ align-items: stretch !important; }</style>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        by_day_m = df_m.groupby('Ngày')['Thời lượng (Phút)'].sum()
        _busiest_date = by_day_m.idxmax()
        _busiest_hrs = by_day_m.max() / 60
        _longest_sess = df_m.loc[df_m['Thời lượng (Phút)'].idxmax()]
        _longest_sess_ts = pd.Timestamp(_longest_sess['Thời gian bắt đầu'])
        _longest_streak = _streak_stats(df_m)['longest']
        # 4 dòng, khớp số dòng thẻ "So với tháng trước" bên cạnh (cùng hàng, height:100% chỉ ép
        # cao bằng nhau ở KHUNG thẻ, không tự căn giữa nội dung ngắn hơn -- xem yêu cầu người
        # dùng) -- "Ngày nhiều phiên nhất" là kỷ lục THẬT, khác trục với "Ngày dài nhất" (theo số
        # phiên thay vì tổng thời lượng), không phải số lặp lại cho đủ dòng.
        _by_day_cnt_m = df_m.groupby('Ngày').size()
        _busiest_cnt_date = _by_day_cnt_m.idxmax()
        _busiest_cnt = int(_by_day_cnt_m.max())
        st.markdown(
            "<div class='glass-card month-hl-card' style='padding:14px 18px;height:100%;'>"
            "<span class='rl-book'>Kỷ lục trong tháng</span><div class='hlt-list'>"
            f"<div class='hlt-item'>{_mi('emoji_events')} Ngày dài nhất · {_busiest_date:%d/%m} · {_fmt_hours_short(_busiest_hrs)}</div>"
            f"<div class='hlt-item'>{_mi('timer')} Phiên dài nhất · {_longest_sess_ts:%d/%m} · "
            f"{int(_longest_sess['Thời lượng (Phút)'])}′ ({html_escape(str(_longest_sess['Dự án']))})</div>"
            f"<div class='hlt-item'>{_mi('bolt')} Ngày nhiều phiên nhất · {_busiest_cnt_date:%d/%m} · {_busiest_cnt} phiên</div>"
            f"<div class='hlt-item'>{_mi('local_fire_department')} Chuỗi trong tháng · {_longest_streak} ngày liên tiếp</div>"
            "</div></div>", unsafe_allow_html=True)

    with c2:
        _lines = []
        if prev_m and prev_m.get('hrs') is not None:
            _dh = df_m['Thời lượng (Phút)'].sum() / 60 - prev_m['hrs']
            _col = "#34c759" if _dh > 0 else "#ff3b30" if _dh < 0 else "var(--text-2)"
            _arrow = "▲" if _dh > 0 else "▼" if _dh < 0 else "–"
            _lines.append(f"Tổng giờ <span style='color:{_col};font-weight:600;'>"
                           f"{_fmt_hours_delta(_dh)} {_arrow}</span>")
        if prev_m and prev_m.get('trees') is not None:
            _dn = len(df_m) - prev_m['trees']
            _col_n = "#34c759" if _dn > 0 else "#ff3b30" if _dn < 0 else "var(--text-2)"
            _arrow_n = "▲" if _dn > 0 else "▼" if _dn < 0 else "–"
            _lines.append(f"Số phiên <span style='color:{_col_n};font-weight:600;'>"
                           f"{_fmt_delta(_dn)} {_arrow_n}</span>")

        _prev_scope = (df[(df['Tháng'] == prev_month_key) & elapsed_mask_m] if elapsed_mask_m is not None
                        else df[df['Tháng'] == prev_month_key])
        _cat_now = df_m.groupby('Danh mục')['Thời lượng (Phút)'].sum() / 60
        _cat_prev = _prev_scope.groupby('Danh mục')['Thời lượng (Phút)'].sum() / 60
        _cat_idx = _cat_now.index.union(_cat_prev.index)
        _cat_delta = _cat_now.reindex(_cat_idx, fill_value=0) - _cat_prev.reindex(_cat_idx, fill_value=0)
        if len(_cat_delta) and _cat_delta.min() < 0 and _cat_delta.max() > 0:
            _worst, _best = _cat_delta.idxmin(), _cat_delta.idxmax()
            _lines.append(f"{html_escape(str(_worst))} giảm {_fmt_hours_short(abs(_cat_delta[_worst]))} "
                           f"— bù bởi {html_escape(str(_best))}")

        _active_days_now = df_m['Ngày'].nunique() or 1
        _tb_day_now = df_m['Thời lượng (Phút)'].sum() / 60 / _active_days_now
        if prev_m and prev_m.get('hrs_day') is not None:
            _lines.append(f"TB/ngày hoạt động {_fmt_hours_short(_tb_day_now)} so với "
                           f"{_fmt_hours_short(prev_m['hrs_day'])} tháng trước")

        _lines_html = "".join(f"<div class='hlt-item'>{ln}</div>" for ln in _lines)
        st.markdown(
            "<div class='glass-card month-hl-card' style='padding:14px 18px;height:100%;'>"
            "<span class='rl-book'>So với tháng trước</span>"
            f"<div class='hlt-list'>{_lines_html}</div></div>", unsafe_allow_html=True)


DTBL_CSS = """
<style>
.dtbl-wrap { overflow:auto; max-height:560px; border-radius:10px; border:1px solid var(--border); background:var(--card); box-shadow:0 1px 1px rgba(0,0,0,0.02); }
.dtbl { border-collapse:collapse; width:100%; font-size:13.5px; font-family:'Manrope',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
.dtbl th, .dtbl td { padding:4px 9px; text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }
.dtbl thead th { position:sticky; top:0; z-index:2; background:var(--chip); color:var(--text-2); font-weight:600; font-size:11px; padding:5px 9px; text-transform:uppercase; letter-spacing:.3px; border-bottom:1px solid var(--divider); }
.dtbl td.lbl, .dtbl th.lbl { text-align:left; position:sticky; left:0; background:var(--card); z-index:1; }
.dtbl thead th.lbl { z-index:3; background:var(--chip); }
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


def _heat_cell(v, ref, extra_cls="", drop=False, as_hours=True):
    """Một ô số: <0.05 -> dấu chấm mờ; ngược lại tô nền teal theo tỉ lệ v/ref.
    drop=True -> đánh dấu ▾ đỏ (sụt mạnh so với kỳ liền trước). as_hours=True (mặc định, dùng
    cho mọi cột "Số giờ") -> hiện dạng gọn 'XhYYp' thay vì số thập phân; as_hours=False (vd cột
    đếm số phần đọc/xem) giữ nguyên số thập phân 1 chữ số như trước."""
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
    val_txt = _fmt_hours_short(v) if as_hours else f"{v:.1f}"
    return f'<td{cls_attr}{title} style="{bg}">{mark}{val_txt}</td>'


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


def render_period_day_table(df_period, all_days=None):
    """Bảng chi tiết theo NGÀY (Báo cáo -> Tuần, mục "Bảng số liệu") -- mỗi ngày trong kỳ 1 dòng
    (Ngày/Giờ/Phiên/TB mỗi phiên/Dự án nhiều nhất), khác trục hẳn với render_detail_table (theo
    Danh mục/Dự án) -- dùng cho Tuần vì trục Danh mục/Dự án đã có frag_category_bars riêng ở
    chương trước, bảng ở đây bổ sung trục còn thiếu (theo ngày) thay vì lặp lại cùng 1 trục lần
    thứ 2 như Tháng/Năm (những trang đó không có frag_category_bars nên vẫn giữ render_detail_table
    theo Danh mục/Dự án).

    all_days: list[date] đầy đủ của kỳ (vd 7 ngày Thứ Hai->Chủ Nhật) -- truyền vào để bảng hiện ĐỦ
    cả những ngày KHÔNG có phiên nào (dòng "—"), đúng cảm giác "sổ ghi chép cả tuần" thay vì chỉ
    liệt kê ngày có dữ liệu. None -> tự suy ra từ chính df_period (bỏ qua ngày trống, hành vi cũ)."""
    if df_period.empty and not all_days:
        return
    days = sorted(all_days) if all_days else sorted(df_period['Ngày'].unique())
    rows_html = ''
    tot_min, tot_sessions = 0.0, 0
    for d in days:
        day_df = df_period[df_period['Ngày'] == d]
        mins = float(day_df['Thời lượng (Phút)'].sum())
        n = len(day_df)
        avg_min = mins / n if n else 0.0
        top_proj = day_df.groupby('Dự án')['Thời lượng (Phút)'].sum().idxmax() if n else "—"
        vn_dow = VN_DAYS.get(pd.Timestamp(d).day_name(), "")
        rows_html += (
            '<tr class="prow">'
            f'<td class="lbl">{vn_dow} {pd.Timestamp(d):%d/%m}</td>'
            f'<td>{_fmt_hours_short(mins / 60) if n else "—"}</td>'
            f'<td>{n if n else "—"}</td>'
            f'<td>{f"{avg_min:.0f}′" if n else "—"}</td>'
            f'<td class="txt">{html_escape(str(top_proj)) if n else ""}</td></tr>')
        tot_min += mins
        tot_sessions += n
    avg_all = tot_min / tot_sessions if tot_sessions else 0.0
    rows_html += ('<tr class="cat"><td class="lbl">Tổng</td>'
                  f'<td class="tot">{_fmt_hours_short(tot_min / 60)}</td>'
                  f'<td class="tot">{tot_sessions}</td>'
                  f'<td class="tot">{avg_all:.0f}′</td><td class="tot"></td></tr>')
    st.markdown(DTBL_CSS + f"""
<div class="dtbl-wrap"><table class="dtbl">
<thead><tr><th class="lbl">Ngày</th><th>Giờ</th><th>Phiên</th><th>TB / phiên</th>
<th class="txt">Dự án nhiều nhất</th></tr></thead>
<tbody>{rows_html}</tbody>
</table></div>
""", unsafe_allow_html=True)


def render_health_full_table(latest_panel):
    """Bảng đầy đủ MỌI Chỉ số của LẦN KHÁM GẦN NHẤT (mọi Nhóm), chương "Bảng xét nghiệm đầy đủ"
    (_render_health_report()) -- khác render_health_log_table() (lịch sử NHIỀU lần đo của ĐÚNG 1
    Chỉ số): bảng này là 1 lần khám x MỌI Chỉ số, dùng cùng khung .dtbl cho đồng bộ. Cột "Đánh
    giá" chỉ 2 mức Cao/Thấp (đỏ) hoặc Bình thường (xanh) -- KHÔNG có mức "Sát ngưỡng" như mockup,
    xem docstring _health_is_abnormal (đã xác nhận với người dùng giữ nhị phân)."""
    if latest_panel.empty:
        st.caption("Lần khám gần nhất chưa có chỉ số nào.")
        return
    _panel = latest_panel.sort_values(['Nhóm', 'Chỉ số'])
    _abn = _health_is_abnormal(_panel)
    rows_html = ''
    for (_, r), a in zip(_panel.iterrows(), _abn):
        val = f"{r['Giá trị']:g}" if pd.notna(r['Giá trị']) else str(r['Giá trị (gốc)'] or '')
        if a:
            _direction = "Cao" if pd.notna(r['Ref cao']) and r['Giá trị'] > r['Ref cao'] else "Thấp"
            eval_html = f"<span class='heval-bad'>{_direction}</span>"
        elif pd.notna(r['Giá trị']):
            eval_html = "<span class='heval-ok'>Bình thường</span>"
        else:
            eval_html = ''
        rows_html += (
            '<tr class="prow">'
            f'<td class="lbl">{html_escape(str(r["Chỉ số"]))}</td>'
            f'<td>{html_escape(val)}</td>'
            f'<td class="txt">{html_escape(str(r["Khoảng tham chiếu"])) if pd.notna(r["Khoảng tham chiếu"]) else ""}</td>'
            f'<td class="txt">{html_escape(str(r["Đơn vị"])) if pd.notna(r["Đơn vị"]) else ""}</td>'
            f'<td class="txt">{eval_html}</td>'
            '</tr>')
    st.markdown(DTBL_CSS + f"""
<div class="dtbl-wrap"><table class="dtbl">
<thead><tr><th class="lbl">Chỉ số</th><th>Kết quả</th><th class="txt">Ngưỡng</th>
<th class="txt">Đơn vị</th><th class="txt">Đánh giá</th></tr></thead>
<tbody>{rows_html}</tbody>
</table></div>
""", unsafe_allow_html=True)


def render_health_log_table(s_num, is_abn):
    """Bảng từng lần đo của 1 chỉ số, dưới biểu đồ theo dõi (Sức khoẻ -> Báo cáo, mục "2. Biểu đồ
    theo dõi") -- dùng cùng khung .dtbl (viền/nền/header dính) với các bảng Báo cáo Thời gian
    (render_data_table/render_detail_table) thay vì st.dataframe() mặc định, cho đồng bộ giao diện
    toàn app thay vì lạc phong cách ở riêng trang này."""
    _tbl = s_num[['Ngày lấy mẫu', 'Giá trị (gốc)', 'Đơn vị', 'Khoảng tham chiếu']].copy()
    _tbl['Bất thường'] = list(is_abn)
    _tbl = _tbl.sort_values('Ngày lấy mẫu', ascending=False)
    rows_html = ''
    for _, r in _tbl.iterrows():
        _status = "<span style='color:#ff3b30;font-weight:600;'>⚠️ Bất thường</span>" if r['Bất thường'] else ''
        rows_html += (
            '<tr class="prow">'
            f'<td class="lbl">{r["Ngày lấy mẫu"]:%d/%m/%Y}</td>'
            f'<td>{html_escape(str(r["Giá trị (gốc)"]))}</td>'
            f'<td class="txt">{html_escape(str(r["Đơn vị"])) if pd.notna(r["Đơn vị"]) else ""}</td>'
            f'<td class="txt">{html_escape(str(r["Khoảng tham chiếu"])) if pd.notna(r["Khoảng tham chiếu"]) else ""}</td>'
            f'<td class="txt">{_status}</td>'
            '</tr>')
    st.markdown(DTBL_CSS + f"""
<div class="dtbl-wrap"><table class="dtbl">
<thead><tr><th class="lbl">Ngày lấy mẫu</th><th>Giá trị</th><th class="txt">Đơn vị</th>
<th class="txt">Khoảng tham chiếu</th><th class="txt">Trạng thái</th></tr></thead>
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


# --- Helpers trang Trợ giúp: tour cuộn dọc, mọi thẻ/minh hoạ vẽ bằng HTML thuần ---
# Chỉ dùng token màu (var(--...), rgba(var(--accent-rgb),...)) nên tự đúng ở dark mode và mọi
# màu accent. HTML build thành chuỗi liền mạch (không dòng trống giữa khối) -- markdown parser
# của st.markdown cắt khối HTML tại dòng trống. CSS namespace "help-" nằm trong khối CSS chính.

_HELP_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def sec_kbd(*keys):
    """Dãy phím kiểu keycap: sec_kbd("Ctrl/Cmd", "Enter") -> <kbd>Ctrl/Cmd</kbd>+<kbd>Enter</kbd>.
    Trả về string HTML để nhúng vào bảng/đoạn văn khác, không tự render."""
    return "<span class='sec-kplus'>+</span>".join(
        f"<kbd class='sec-kbd'>{k}</kbd>" for k in keys)


def sec_table(headers, rows):
    """Bảng tra nhanh (cheat-sheet). rows: list[list[str]], cell là HTML thô (nhúng được
    sec_kbd()/chip) -- chỉ đưa nội dung tĩnh viết tay vào đây, không đưa dữ liệu người dùng.
    Trả về string HTML (bọc sẵn khối cuộn ngang cho màn hẹp)."""
    _thead = "".join(f"<th>{h}</th>" for h in headers)
    _tbody = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return ("<div class='sec-tblwrap'><table class='sec-tbl'>"
            f"<thead><tr>{_thead}</tr></thead><tbody>{_tbody}</tbody></table></div>")


def sec_chapter(anchor, num, kicker, title, lead=None, tight_top=False, badge=None):
    """Header 1 chương -- dùng chung cho mọi trang cuộn dọc kiểu "chương" (Trợ giúp, và các trang
    báo cáo/nội dung đọc đã chuyển từ accordion sang bố cục này): ô vuông số thứ tự nhỏ + tiêu đề +
    badge tuỳ chọn + kẻ ngang mở + kicker tuỳ chọn, tất cả trên CÙNG 1 hàng canh giữa dọc (đúng
    khuôn mockup hiện hành -- không còn số lớn mờ chồng góc phải của bản trước). anchor là id cho
    chip mục lục nhảy tới (CSS scroll-margin-top của .sec-ch chừa chỗ cho header fixed của
    Streamlit khỏi che tiêu đề).

    num=None -> bỏ hẳn ô số thứ tự (mục không đánh số, dùng cho panel tham khảo không nằm trong 1
    chuỗi đếm thật sự).

    kicker=None/"" -> bỏ hẳn nhãn kicker cuối hàng (dùng khi kicker chỉ lặp lại đúng tên trang
    đang đứng, vd "Hôm nay" ở tiêu đề "Tổng quan ngày" của chính trang Hôm nay -- dư thừa, hero đã
    nói rõ đang ở trang nào rồi; chỉ giữ kicker khi nó bổ sung ngữ cảnh thật sự mới, như "Universal
    Century"/"Dự án → Danh mục" trong mockup). Kicker đứng SAU kẻ ngang (cuối hàng), không phải
    trước tiêu đề.

    tight_top=True -> bỏ margin-top mặc định của .sec-ch. CHỈ dùng cho chương ĐẦU TIÊN ngay sau 1
    sec_hero()/billboard: margin-top đó cộng dồn với margin-bottom sẵn có của hero/billboard + gap
    flex mặc định giữa 2 khối (Streamlit không collapse margin giữa các flex item như block
    thường) tạo khoảng trắng rộng bất thường ngay dưới hero, trong khi giữa các chương với nhau
    (2 trở đi) khoảng cách đó vẫn cần giữ nguyên.

    badge=None/"" -> bỏ hẳn chip nhỏ cạnh tiêu đề (vd "Lần khám 16/07/2026" ở "Chỉ số bất thường"
    của Sức khoẻ) -- tách phần thông tin động (ngày/giá trị cụ thể) ra khỏi CHÍNH văn bản tiêu đề,
    để tiêu đề luôn là 1 cụm cố định ngắn gọn, phần đổi theo dữ liệu hiện dưới dạng chip cạnh bên
    thay vì nối chuỗi vào title. Badge đứng NGAY SAU tiêu đề, trước kẻ ngang."""
    _num_html = f"<span class='sec-ch-num'>{num}</span>" if num is not None else ""
    _badge_html = f"<span class='sec-ch-badge'>{badge}</span>" if badge else ""
    _kicker_html = f"<span class='sec-ch-kicker'>{kicker}</span>" if kicker else ""
    _lead = f"<p class='sec-ch-lead'>{lead}</p>" if lead else ""
    _cls = "sec-ch sec-ch-tight" if tight_top else "sec-ch"
    st.markdown(
        f"<div class='{_cls}' id='{anchor}'>"
        f"<div class='sec-ch-row'>{_num_html}<span class='sec-ch-title'>{title}</span>{_badge_html}"
        f"<span class='sec-ch-rule'></span>{_kicker_html}</div>{_lead}</div>",
        unsafe_allow_html=True)


def sec_block(html):
    """Bọc 1 khối HTML vào thẻ .sec-card (thay cho st.container(border=True) của trang
    Hướng dẫn bản cũ -- không cần key container nên không đụng rule CSS glass-card chung)."""
    st.markdown(f"<div class='sec-card'>{html}</div>", unsafe_allow_html=True)


def sec_hero(kicker, title, sub, chips, meta=None):
    """Khối mở đầu 1 trang cuộn dọc kiểu "chương": kicker + tiêu đề lớn + đoạn tóm tắt ngắn +
    hàng chip nhảy nhanh tới từng chương (chips: list[(anchor, nhãn)]). Factor lại từ khối hero
    viết tay ban đầu của trang Trợ giúp -- dùng chung cho mọi trang chuyển sang bố cục này để
    không lặp lại cùng 1 khối HTML nhiều lần.

    kicker=None/"" -> bỏ hẳn dòng kicker; sub=None/"" -> bỏ hẳn đoạn tóm tắt. Dùng cho các trang
    chỉ cần tiêu đề + chip mục lục, không cần nhãn ngữ cảnh hay câu mô tả thêm (mọi hero ngoài
    Trợ giúp hiện đều gọi kiểu này -- Trợ giúp là ngoại lệ duy nhất còn giữ đủ cả 2, vì đó là nội
    dung hướng dẫn thật cần câu mở đầu giải thích app, không phải phần "dư thừa" như các trang
    khác). chips=[] -> bỏ hẳn hàng chip (không render div rỗng để lại khoảng trắng thừa) -- dùng
    khi sub-tab không có chương/mục nào khác để nhảy tới (vd Sách/Gundam → Tổng quan).

    meta=None/"" -> bỏ hẳn dòng nhỏ dưới tiêu đề. KHÁC bản chất với sub (đoạn mô tả tĩnh đã bị bỏ
    khỏi mọi hero ngoài Trợ giúp) -- meta dành cho 1 dòng dữ liệu SỐNG (vd "Cập nhật lần cuối ...
    trước", đúng khuôn .tbill-meta của billboard Hôm nay), chỉ trang nào thực sự có mốc cập nhật
    đáng theo dõi mới truyền (hiện chỉ Sức khoẻ)."""
    _kicker_html = f"<div class='hh-kicker'>{kicker}</div>" if kicker else ""
    _sub_html = f"<div class='hh-sub'>{sub}</div>" if sub else ""
    _meta_html = f"<div class='hh-meta'>{meta}</div>" if meta else ""
    _toc_html = ""
    if chips:
        _chips_html = "".join(f"<a class='sec-toc-chip' href='#{a}'>{lbl}</a>" for a, lbl in chips)
        _toc_html = f"<div class='sec-toc'>{_chips_html}</div>"
    st.markdown(
        f"<div class='sec-hero'>{_kicker_html}"
        f"<div class='hh-title'>{title}</div>{_sub_html}{_meta_html}{_toc_html}</div>",
        unsafe_allow_html=True)


def render_period_billboard(tab_label, big_num, big_label, meta, right_html, chips, key="bc_billboard"):
    """Billboard mở đầu 1 sub-tab kiểu chương dài (Báo cáo -> Tổng quan/Tuần/Tháng/Năm/Dự án, Sách
    -> Tổng quan/Chi tiết): số to bên trái đóng khung như tờ giấy lịch bàn + nội dung tự do bên
    phải, style (kính mờ/frosted glass) dùng chung y hệt billboard Hôm nay -- xem docstring
    _render_today_billboard() và CSS `.st-key-today_billboard, .st-key-bc_billboard`. Tái dùng
    nguyên khối `.tbill-tab`/`.tbill-meta` (giá trị CSS giống hệt), chỉ thêm `.pbill-*` cho số to/
    nhãn vì cỡ chữ khác billboard Hôm nay (64px so với 76px, do đây là số nhiều chữ số hơn số
    ngày).

    right_html: HTML THÔ cho cột phải -- caller tự dựng (khác nhau khá nhiều giữa các trang: Báo
    cáo dùng tiêu đề+mô tả câu văn (.pbill-title/.pbill-sub), Sách dùng kicker+tên sách/tác giả
    (.pbill-kicker/.pbill-booktitle/.pbill-author) + hàng chip riêng (.pbill-chips) -- tham số hoá
    thẳng bằng HTML thay vì cố nhét đủ loại nội dung vào tham số text/subtitle cố định.

    key: PHẢI đổi khi 1 trang có >1 lời gọi hàm này CÓ THỂ CÙNG NẰM TRONG 1 LẦN CHẠY SCRIPT --
    bug thật đã gặp: st.tabs() render TOÀN BỘ nội dung mọi tab (kể cả tab không active, chỉ ẩn
    bằng CSS), nên Sách "Tổng quan" (_render_reading_billboard) và "Chi tiết"
    (_render_reading_detail) cùng gọi hàm này trong CÙNG 1 lần chạy -> StreamlitDuplicateElementKey
    nếu dùng chung key mặc định. CSS `.st-key-bc_billboard*`/`[class*="st-key-bc_billboard_row"...]`
    phải liệt kê thêm MỌI key mới thêm vào đây (khớp chính xác, không dùng prefix chung vì
    "..._detail_row" không còn chứa nguyên vẹn chuỗi con "billboard_row")."""
    _left_html = (
        "<div class='tbill-date'>"
        f"<div class='tbill-tab'><span class='tbill-tab-label'>{tab_label}</span></div>"
        f"<div class='pbill-num'>{big_num}</div>"
        f"<div class='pbill-label'>{big_label}</div>"
        f"<div class='tbill-meta'>{meta}</div></div>")
    with st.container(key=key, border=True):
        with st.container(key=f"{key}_row"):
            c_left, c_right = st.columns([1, 2], vertical_alignment="center")
            with c_left:
                st.markdown(_left_html, unsafe_allow_html=True)
            with c_right:
                st.markdown(right_html, unsafe_allow_html=True)
        if chips:
            _chips_html = "".join(f"<a class='sec-toc-chip' href='#{a}'>{lbl}</a>" for a, lbl in chips)
            st.markdown(f"<div class='sec-toc' style='margin-top:18px;'>{_chips_html}</div>", unsafe_allow_html=True)


def help_faq_item(question, answer_md):
    """1 câu hỏi FAQ = expander native (đã ăn style expander sẵn có của app). Cố ý KHÔNG đánh
    số như expander trang báo cáo -- FAQ tra theo câu hỏi, không đọc tuần tự."""
    with st.expander(question):
        st.markdown(answer_md)


def render_help_changelog(entries):
    """Timeline "Nhật ký phát triển": mỗi entry là 1 thẻ kiểu .sec-card gắn chấm tròn accent nối
    đường dọc bên trái (xem CSS .help-tl*), header gồm nhãn PR + 3 chip, rồi tiêu đề đậm + bullets
    (hỗ trợ **đậm** kiểu markdown).

    entries: list[dict] khai báo tay, mỗi dict gồm pr / title / bullets / date / pr_lines /
    total_lines. Giữ nguyên ngữ nghĩa 2 chip số liệu của guide_update() bản cũ, cộng thêm 1 chip
    ngày mới:
    - date: ngày merge (dd/mm/yyyy) của PR MỚI NHẤT trong cụm pr, tra qua `pull_request_read` --
      chip nền xám, đứng đầu tiên.
    - total_lines: tổng số dòng CỦA CẢ app.py (wc -l) tại commit merge PR mới nhất trong cụm
      (tra qua `git show <commit>:app.py | wc -l`) -- chip nền xám, đứng giữa.
    - pr_lines: tổng số dòng đổi (additions+deletions, tra qua GitHub API lúc viết mục) của PR
      MỚI NHẤT trong cụm pr (vd pr="182-184" -> số dòng của #184) -- chip nền accent, đứng cuối.
    2 cụm PR "132,133,136,137" và "125,126,139,140" không còn commit gốc riêng trong lịch sử git
    (đã bị squash/rebase gộp) -- dùng tạm số dòng tại commit gần nhất còn truy được (#142); ngày
    merge của cả 2 cụm này tra theo đúng PR mới nhất trong cụm (#137 và #140).
    Cả 3 trường đều KHÔNG tự tính lại lúc runtime (app không gọi GitHub API/git khi chạy) --
    số tĩnh, điền tay khi thêm mục mới."""
    _parts = ["<div class='help-tl'>"]
    for e in entries:
        _chips = ""
        if e.get("date"):
            _chips += f"<span class='help-chip'>{e['date']}</span>"
        if e.get("total_lines") is not None:
            _chips += f"<span class='help-chip'>{e['total_lines']} dòng mã nguồn</span>"
        if e.get("pr_lines") is not None:
            _chips += f"<span class='help-chip help-chip-acc'>{e['pr_lines']} dòng thay đổi</span>"
        _lis = "".join(
            "<li>" + _HELP_BOLD_RE.sub(r"<b>\1</b>", b) + "</li>" for b in e["bullets"])
        _parts.append(
            f"<div class='help-tl-item'><span class='help-tl-dot'></span>"
            f"<div class='help-tl-head'><span class='help-tl-pr'>PR #{e['pr']}</span>{_chips}</div>"
            f"<div class='help-tl-title'>{e['title']}</div>"
            f"<ul class='help-tl-ul'>{_lis}</ul></div>")
    _parts.append("</div>")
    st.markdown("".join(_parts), unsafe_allow_html=True)


# --- FRAGMENT: cô lập rerun cho từng mục biểu đồ có bộ điều khiển riêng ---
# Khi đổi bộ lọc bên trong một mục, chỉ mục đó vẽ lại thay vì rerun cả trang
# (nhanh hơn, nhất là trang nhiều dữ liệu/khi xem trên điện thoại).
@st.fragment
def frag_calendar(scope_df, key):
    """Mục Biểu đồ lịch — bộ chọn khoảng thời gian riêng. Bọc trong container "chartopt_..." (xem
    docstring frag_pie) để thu hẹp khoảng cách dọc xuống biểu đồ ngay dưới."""
    with st.container(key=f"chartopt_{key}"):
        df_cal = range_radio(scope_df, key=key)
        render_calendar_grid(df_cal, df_cal)


@st.fragment
def frag_trend(scope_df, key_prefix, default_color):
    """Mục Xu hướng theo thời gian — chọn khoảng thời gian / cách gộp / phân loại. Bọc trong
    container "chartopt_..." (xem docstring frag_pie) để thu hẹp khoảng cách dọc xuống biểu đồ
    ngay dưới."""
    with st.container(key=f"chartopt_{key_prefix}"):
        o1, o2, o3 = st.columns([5, 3, 2])
        with o1:
            rl = st.segmented_control("Khoảng thời gian", list(RANGE_OPTS.keys()), default="90 ngày",
                                       key=f"{key_prefix}_range", label_visibility="collapsed")
        with o2:
            tcol = st.segmented_control("Gộp theo", ["Ngày", "Tuần", "Tháng"], default="Ngày",
                                         key=f"{key_prefix}_time", label_visibility="collapsed")
        with o3:
            ccol = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default=default_color,
                                         key=f"{key_prefix}_color", label_visibility="collapsed")
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
    (khoảng thời gian nếu có + phân loại). Không dùng chung với mục nào khác. Bọc trong container
    "chartopt_..." (xem docstring frag_pie) để thu hẹp khoảng cách dọc xuống biểu đồ ngay dưới."""
    with st.container(key=f"chartopt_{key_prefix}"):
        if with_range:
            c1, c2 = st.columns([5, 3])
            with c1:
                rl = st.segmented_control("Khoảng thời gian", list(RANGE_OPTS.keys()), default="90 ngày",
                                           key=f"{key_prefix}_range", label_visibility="collapsed")
            with c2:
                ccol = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default=default_color,
                                             key=f"{key_prefix}_color", label_visibility="collapsed")
            scope_df = filter_by_range(scope_df, rl or "90 ngày")
        else:
            ccol = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default=default_color,
                                         key=f"{key_prefix}_color", label_visibility="collapsed")
        render_hourly_chart(scope_df, ccol or default_color)


@st.fragment
def frag_pie(scope_df, key, default_color):
    """Mục Phân bổ thời gian (biểu đồ tròn) — bộ chọn Phân loại riêng. Bọc trong container riêng
    (key="piewrap_...") chỉ để CSS thu hẹp khoảng cách dọc xuống biểu đồ ngay dưới (xem rule
    [class*="st-key-piewrap_"], [class*="st-key-chartopt_"]) mà không đụng margin của mọi
    segmented_control khác trong app."""
    with st.container(key=f"piewrap_{key}"):
        ccol = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default=default_color, key=key,
                                     label_visibility="collapsed") or default_color
        pc = scope_df.groupby(ccol)['Thời lượng (Phút)'].sum().reset_index()
        pc['Số giờ'] = pc['Thời lượng (Phút)'] / 60
        fig = px.pie(pc, values='Số giờ', names=ccol, color=ccol, color_discrete_map=COLOR_MAP)
        fig = format_plotly_fig(fig, is_pie=True)
        st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)


@st.fragment
def frag_category_bars(scope_df, key, default_color):
    """Mục Phân bổ thời gian dạng thanh ngang xếp hạng (thay biểu đồ tròn cũ ở Báo cáo -> Tuần và
    Hôm nay -- Tháng/Năm vẫn giữ frag_pie, chưa đổi) -- toggle Danh mục/Dự án, mỗi hàng nhãn + 1
    thanh fill dài tỉ lệ theo TỔNG cả kỳ (KHÔNG phải theo hàng cao nhất -- đúng theo mockup Forest
    Dashboard.dc.html, xác nhận qua width% mỗi hàng cộng dồn ra khớp tổng giờ cả kỳ) + giá trị bên
    phải, cộng dòng tóm tắt "X nổi bật" liệt kê top 3 trong phạm vi TOGGLE ĐANG CHỌN (mockup vẽ
    tĩnh nên luôn ghi "Dự án nổi bật" dù thanh đang hiện Danh mục -- ở đây đổi nhãn theo đúng toggle
    cho nhất quán, tránh lệch trục giữa thanh và dòng tóm tắt). Bọc trong container "chartopt_..."
    (xem docstring frag_pie) để thu hẹp khoảng cách dọc xuống nội dung ngay dưới."""
    with st.container(key=f"chartopt_{key}"):
        ccol = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default=default_color, key=key,
                                     label_visibility="collapsed") or default_color
        g = scope_df.groupby(ccol)['Thời lượng (Phút)'].sum().sort_values(ascending=False)
        total_min = scope_df['Thời lượng (Phút)'].sum()
        if g.empty or total_min <= 0:
            st.caption("Chưa có dữ liệu.")
            return
        rows_html = ""
        for i, (name, mins) in enumerate(g.items()):
            pct = mins / total_min * 100
            color = COLOR_MAP.get(name, MAC_COLORS[i % len(MAC_COLORS)])
            rows_html += (
                "<div class='catbar-row'>"
                f"<span class='catbar-label'>{html_escape(str(name))}</span>"
                f"<span class='catbar-track'><span class='catbar-fill' "
                f"style='width:{pct:.1f}%;background:{color};'></span></span>"
                f"<span class='catbar-val'>{_fmt_hours_short(mins / 60)}</span></div>")
        top3 = g.head(3)
        noun = "Danh mục nổi bật" if ccol == "Danh mục" else "Dự án nổi bật"
        parts = [(f"<b>{html_escape(str(n))} {_fmt_hours_short(v / 60)}</b>" if i == 0
                   else f"{html_escape(str(n))} {_fmt_hours_short(v / 60)}")
                  for i, (n, v) in enumerate(top3.items())]
        st.markdown(
            f"<div class='catbars-card'><div class='catbars'>{rows_html}</div>"
            f"<div class='catbars-top'>{noun}: {' · '.join(parts)}</div></div>",
            unsafe_allow_html=True)


@st.fragment
def frag_period_trend(scope_df, key, default_color, group_col, x_title, cat_order=None):
    """Mục Xu hướng theo thời gian trong một kỳ (tháng -> theo Ngày; tuần -> theo
    Thứ) — bộ chọn Phân loại riêng. MA chỉ áp khi gộp theo Ngày (render_trend_fig). Bọc trong
    container "chartopt_..." (xem docstring frag_pie) để thu hẹp khoảng cách dọc xuống biểu đồ
    ngay dưới."""
    with st.container(key=f"chartopt_{key}"):
        ccol = st.segmented_control("Phân loại", ["Danh mục", "Dự án"], default=default_color, key=key,
                                     label_visibility="collapsed") or default_color
        g = scope_df.groupby([group_col, ccol])['Thời lượng (Phút)'].sum().reset_index()
        g['Số giờ'] = g['Thời lượng (Phút)'] / 60
        if group_col == 'Ngày':
            g['Ngày'] = pd.to_datetime(g['Ngày'])
        fig = render_trend_fig(g, group_col, ccol, ma_df=scope_df, cat_order=cat_order, x_title=x_title)
        st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)


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
                                            default="90 ngày", key=f"{key_prefix}_range",
                                            label_visibility="collapsed") or "90 ngày"
        df_tbl = filter_by_range(scope_df, range_label)
    with cc2:
        smart_default = "Tuần" if range_label in ("30 ngày", "90 ngày") else "Tháng"
        view_opt = st.segmented_control("Xem theo", ["Tuần", "Tháng"], default=smart_default,
                                         key=f"{key_prefix}_view_{range_label}",
                                         label_visibility="collapsed")
    view_opt = view_opt or smart_default
    render_data_table(df_tbl, 'Tuần' if view_opt == "Tuần" else 'Tháng')


@st.fragment
def frag_period_table(scope_df, key):
    """Mục Bảng số liệu (Báo cáo theo dự án): xem theo Tuần/Tháng."""
    grp_view = st.segmented_control("Xem theo", ["Tuần", "Tháng"], default="Tháng", key=key,
                                     label_visibility="collapsed")
    grp_view = grp_view or "Tháng"
    render_period_table(scope_df, 'Tuần' if grp_view == "Tuần" else 'Tháng')


def render_project_week_trend(df_g, n_weeks=12):
    """Chương "Xu hướng theo tuần" (Báo cáo -> Dự án, mockup): N tuần gần nhất (mặc định 12) của
    dự án/nhóm đang xem, mỗi cột = tổng giờ đúng tuần đó -- tô đậm riêng cột tuần kỷ lục (nhiều
    giờ nhất trong dải N tuần), còn lại đồng 1 màu teal trung bình. Khác thang gradient nhiều bậc
    của "Theo tháng" (Báo cáo -> Năm, xem render_year_month_bars) vì ở đây chỉ cần nổi bật ĐÚNG 1
    tuần nổi bật nhất, không cần phân bậc cả dải."""
    if df_g.empty:
        st.caption("Chưa có dữ liệu.")
        return
    wk_hrs = df_g.groupby('Tuần')['Thời lượng (Phút)'].sum() / 60
    recent_weeks = sorted(wk_hrs.index)[-n_weeks:]
    vals = wk_hrs.reindex(recent_weeks, fill_value=0.0)
    best_week = vals.idxmax() if len(vals) else None
    _light, _mid, _dark = _teal_shades(3)
    colors = [_dark if w == best_week else _mid for w in recent_weeks]
    labels = [f"T{w.split('-W')[1]}" for w in recent_weeks]
    fig = go.Figure(go.Bar(x=labels, y=list(vals), marker_color=colors))
    fig = format_plotly_fig(fig)
    fig.update_layout(showlegend=False, yaxis=dict(title="Số giờ"))
    st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)


def render_project_recent_sessions(df_g, days=30):
    """Chương "Phiên gần đây" (Báo cáo -> Dự án, mockup): MỌI phiên trong N ngày gần nhất (mặc
    định 30) của dự án/nhóm đang xem, mỗi dòng Ngày/Bắt đầu/Độ dài/Buổi (buổi tra qua _buoi_of()
    dùng chung với biểu đồ khung giờ) + 1 dòng tổng cuối bảng (giờ + số phiên trong cửa sổ) --
    khác trục "Bảng số liệu" (frag_period_table, tổng hợp theo Tuần/Tháng) vì đây là danh sách
    PHIÊN THÔ mới nhất, thấy ngay nhịp làm việc gần đây mà không cần mở "Biểu đồ lịch" hay đổi bộ
    lọc kỳ. Phân trang 10 phiên/trang (theo yêu cầu) -- cùng pattern clamp/`st.pagination` đã
    dùng cho bảng "Dữ liệu làm việc hiện tại" ở Tuỳ biến (xem db_page), key riêng "duan_rs_page"."""
    if df_g.empty:
        st.caption("Chưa có phiên nào.")
        return
    cutoff = pd.Timestamp(_today_vn() - timedelta(days=days - 1))
    recent = df_g[pd.to_datetime(df_g['Thời gian bắt đầu']) >= cutoff].sort_values(
        'Thời gian bắt đầu', ascending=False, kind='stable')
    if recent.empty:
        st.caption(f"Chưa có phiên nào trong {days} ngày gần nhất.")
        return

    PAGE_SIZE = 10
    n = len(recent)
    paged = n > PAGE_SIZE
    _start = 0
    if paged:
        num_pages = (n + PAGE_SIZE - 1) // PAGE_SIZE
        page = min(st.session_state.get("duan_rs_page", 1), num_pages)
        st.session_state["duan_rs_page"] = page
        _start = (page - 1) * PAGE_SIZE
        page_df = recent.iloc[_start:_start + PAGE_SIZE]
    else:
        page_df = recent

    rows_html = ""
    for _, r in page_df.iterrows():
        ts = pd.Timestamp(r['Thời gian bắt đầu'])
        rows_html += (f"<tr><td class='txt lbl'>{VN_DAYS.get(ts.day_name(), '')} {ts:%d/%m}</td>"
                      f"<td>{ts:%H:%M}</td><td>{int(r['Thời lượng (Phút)'])}′</td>"
                      f"<td>{_buoi_of(ts.hour)}</td></tr>")
    _tot_hrs = recent['Thời lượng (Phút)'].sum() / 60
    rows_html += (f"<tr style='font-weight:700;'><td class='txt lbl'>Tổng {days} ngày</td><td></td>"
                  f"<td>{_fmt_hours_short(_tot_hrs)}</td><td>{len(recent)} phiên</td></tr>")
    st.markdown(
        DTBL_CSS + "<div class='dtbl-wrap'><table class='dtbl'><thead><tr>"
        "<th class='txt lbl'>Ngày</th><th>Bắt đầu</th><th>Độ dài</th><th>Buổi</th>"
        f"</tr></thead><tbody>{rows_html}</tbody></table></div>",
        unsafe_allow_html=True)

    if paged:
        with st.container(key="duan_rs_pag"):
            st.pagination(num_pages, key="duan_rs_page")
        st.markdown(
            f"<div style='text-align:center;font-size:13px;color:var(--text-2);margin-top:2px;'>"
            f"Hiển thị phiên {_start + 1}–{min(_start + PAGE_SIZE, n)} / {n}</div>",
            unsafe_allow_html=True)


_RHYTHM_TIP_CSS = """
<style>
.rhythm-seg { position: relative; }
.rhythm-seg:hover::after {
    content: attr(data-tip);
    position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%);
    margin-bottom: 7px; background: var(--text); color: var(--card);
    font-size: 12px; font-weight: 600; padding: 5px 9px; border-radius: 6px;
    white-space: nowrap; z-index: 20; pointer-events: none;
}
</style>
"""


def render_project_rhythm(df_g):
    """2 thẻ ngang "Theo buổi"/"Độ dài phiên" (Báo cáo -> Dự án) -- "Theo buổi" (tỉ trọng
    Sáng/Chiều/Tối/Khuya, tô teal đậm/nhạt theo TỈ TRỌNG lớn nhỏ trong đúng dự án/nhóm này, buổi
    chiếm nhiều nhất tô đậm nhất -- khác BUOI_BANDS (màu nền zone của biểu đồ khung giờ, không
    hợp để tô thanh phân bổ đặc)) và "Độ dài phiên" (tái dùng SESSION_BUCKETS/_teal_shades(5) đã
    có, chỉ 1 câu nhận định gọn, không kèm legend chi tiết như render_session_bar()). Không còn
    là chương riêng "Nhịp làm việc" -- gộp vào chương "Tổng quan" (theo yêu cầu người dùng). Mỗi
    ô dùng `data-tip` + CSS `:hover::after` (xem _RHYTHM_TIP_CSS) thay cho `title=` gốc -- tooltip
    hiện ngay khi rê chuột, không có độ trễ ~1s của tooltip trình duyệt mặc định."""
    if df_g.empty:
        st.caption("Chưa có dữ liệu.")
        return
    st.markdown(_RHYTHM_TIP_CSS, unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        buoi_min = (df_g.assign(_b=pd.to_datetime(df_g['Thời gian bắt đầu']).dt.hour.map(_buoi_of))
                    .groupby('_b')['Thời lượng (Phút)'].sum())
        buoi_min = buoi_min.reindex(["Sáng", "Chiều", "Tối", "Khuya"]).dropna().sort_values(ascending=False)
        total_min = buoi_min.sum()
        _n_b = len(buoi_min)
        shades_b = _teal_shades(max(_n_b, 2))[::-1][:_n_b]
        seg1 = ""
        for i, ((b, m), col) in enumerate(zip(buoi_min.items(), shades_b)):
            pct = m / total_min * 100
            lbl = f"{b} {pct:.0f}%" if pct >= 9 else ""
            # Bo góc riêng ô ĐẦU/CUỐI (thay vì overflow:hidden trên cả hàng) -- overflow:hidden sẽ
            # cắt luôn tooltip data-tip (::after) của các ô đè lên mép hàng, xem _RHYTHM_TIP_CSS.
            _rad = ("border-radius:6px 0 0 6px;" if i == 0 else
                    "border-radius:0 6px 6px 0;" if i == _n_b - 1 else "")
            seg1 += (f"<div class='rhythm-seg' data-tip='{b}: {_fmt_hours_long(m/60)}' "
                     f"style='width:{pct:.4f}%;background:{col};{_rad}"
                     f"color:{_readable_text(col)};font-size:12px;font-weight:600;display:flex;"
                     f"align-items:center;justify-content:center;'>{lbl}</div>")
        _dom_buoi, _dom_min = buoi_min.index[0], buoi_min.iloc[0]
        _dom_pct = _dom_min / total_min * 100
        _insight1 = (f"Dự án \"{_dom_buoi.lower()}\" rõ rệt — {_dom_pct:.0f}% thời gian rơi vào buổi này."
                     if _dom_pct >= 50 else "Thời gian trải khá đều giữa các buổi trong ngày.")
        st.markdown(
            "<div class='glass-card' style='padding:14px 18px;height:100%;'>"
            "<span class='rl-book'>Theo buổi</span>"
            f"<div style='display:flex;height:26px;'>{seg1}</div>"
            f"<div style='margin-top:10px;font-size:13px;color:var(--text-2);'>{_insight1}</div>"
            "</div>", unsafe_allow_html=True)

    with c2:
        d = df_g['Thời lượng (Phút)']
        n = len(df_g)
        counts = [int(((d >= lo) & (d < hi)).sum()) for _, _, lo, hi, _ in SESSION_BUCKETS]
        _present = [(name, rng, col, c) for (name, rng, lo, hi, col), c in zip(SESSION_BUCKETS, counts) if c]
        seg2 = ""
        for i, (name, rng, col, c) in enumerate(_present):
            pct = c / n * 100
            lbl = f"{pct:.0f}%" if pct >= 9 else ""
            # Cùng lý do bo góc riêng ô đầu/cuối như "Theo buổi" ở trên -- giữ tooltip không bị cắt.
            _rad = ("border-radius:6px 0 0 6px;" if i == 0 else
                    "border-radius:0 6px 6px 0;" if i == len(_present) - 1 else "")
            seg2 += (f"<div class='rhythm-seg' data-tip='{name} ({rng}): {c} phiên' "
                     f"style='width:{pct:.4f}%;background:{col};{_rad}"
                     f"color:{_readable_text(col)};font-size:12px;font-weight:600;display:flex;"
                     f"align-items:center;justify-content:center;'>{lbl}</div>")
        _best_i = counts.index(max(counts))
        _typical_rng = SESSION_BUCKETS[_best_i][1].replace('–<', '–')
        _insight2 = f"Phiên điển hình {_typical_rng} · TB {_avg_session_min(df_g):.0f}′/phiên"
        st.markdown(
            "<div class='glass-card' style='padding:14px 18px;height:100%;'>"
            "<span class='rl-book'>Độ dài phiên</span>"
            f"<div style='display:flex;height:26px;'>{seg2}</div>"
            f"<div style='margin-top:10px;font-size:13px;color:var(--text-2);'>{_insight2}</div>"
            "</div>", unsafe_allow_html=True)


# --- LOGO: mark "nhịp phiên" (session-rhythm bars) phẳng + wordmark, hệ thiết kế "Sổ Tay" (xem
# design handoff) -- thay bản v2 skeuomorphic (khối bo tròn kiểu iOS 6 phủ gradient/gloss + 3
# vòng tuổi cây khắc chìm): mark mới là 1 khối vuông bo góc TÔ ĐẶC 1 màu ACCENT (không gradient,
# không gloss, không drop-shadow), chứa 5 vạch dọc cao thấp lệch nhau mô phỏng nhịp phiên tập
# trung trong ngày -- ẩn dụ dữ liệu thay cho ẩn dụ "cây". Wordmark "Forest" đổi font display từ
# Instrument Serif -> Source Serif 4 (weight 500), nhãn "Dashboard" nhỏ/nhạt bên cạnh giữ nguyên.
# Cần dùng được ở CẢ 2 nơi: trang đăng nhập (chạy TRƯỚC khối inject :root CSS var) và title chính
# (chạy SAU) -- nên tự chứa @font-face riêng + chọn màu chữ bằng literal Python theo IS_DARK,
# không phụ thuộc var(--text)/var(--accent).
@st.cache_resource
def _logo_font_b64():
    with open(os.path.join("assets", "fonts", "SourceSerif4-Medium-latin.woff2"), "rb") as f:
        return base64.b64encode(f.read()).decode()

_LOGO_FONT_FACE = (
    "@font-face { font-family:'Source Serif 4'; font-style:normal; font-weight:500; "
    f"font-display:swap; src:url(data:font/woff2;base64,{_logo_font_b64()}) format('woff2'); "
    "unicode-range:U+0000-00FF,U+2018-201F; }"
)


def _logo_mark_svg(size):
    """SVG mark phẳng "nhịp phiên" (5 vạch dọc), TỰ ĐỔI theo ACCENT đang chọn -- khối nền tô đặc
    ACCENT (không gradient), viền 1.5px màu ACCENT đậm hơn (_darken factor=0.75, đủ tương phản để
    thấy viền trên nền ACCENT nhạt mà không quá gắt như bản skeuomorphic cũ), 5 vạch trắng-ngà
    (màu {{card}} light -- '#fdfbf5', luôn sáng hơn mọi ACCENT nên không cần đổi theo IS_DARK)
    cao thấp so le. viewBox cố định 0 0 44 44 -- size chỉ đổi width/height, không đổi hình học.
    Toạ độ x/y CĂN GIỮA cả cụm 5 vạch trong khung 44x44 (lề trái/phải đều 7px, lề trên/dưới quanh
    vạch cao nhất đều 10.5px) -- bản gốc copy nguyên từ design handoff bị lệch trái ~2px (lề trái
    9px, lề phải chỉ 5px) do người thiết kế không cân lại toạ độ khi thu nhỏ viewBox, đã phát hiện
    qua phản hồi thực tế nên tính lại đây, KHÔNG đổi tỉ lệ chiều cao so le giữa các vạch (vẫn giữ
    dáng "nhịp phiên" tự nhiên, không phải hình núi đối xứng cứng nhắc)."""
    dark = _darken(ACCENT, 0.75)
    bars = [(7, 22.5, 11), (13.5, 15.5, 18), (20, 10.5, 23), (26.5, 17.5, 16), (33, 24.5, 9)]
    bar_svg = "".join(
        f"<rect x='{x}' y='{y}' width='4' height='{h}' rx='1.5' fill='#fdfbf5'></rect>"
        for x, y, h in bars
    )
    return (
        f"<svg width='{size}' height='{size}' viewBox='0 0 44 44'>"
        f"<rect x='1' y='1' width='42' height='42' rx='9' fill='{ACCENT}' stroke='{dark}' stroke-width='1.5'></rect>"
        f"{bar_svg}</svg>"
    )


def _wordmark_html(layout="header"):
    """Mark + wordmark dùng chung cho trang đăng nhập ("login", to, xếp dọc) và title chính
    ("header", nằm ngang -- mark bên trái, cụm chữ Forest/Dashboard xếp dọc bên phải, gọn theo
    chiều cao vì header lặp lại trên MỌI trang, khác login chỉ hiện 1 lần nên giữ xếp dọc to).

    Span "Forest" vẫn giữ line-height:1.5 (KHÔNG phải 1) + transform:translateZ(0) dù đã đổi font
    từ Instrument Serif sang Source Serif 4 -- workaround này chống lỗi WebKit "xé"/cắt cụt nét
    chữ hoa ở ascent bất thường trên mobile Safari (đã xác nhận qua ảnh chụp thật với Instrument
    Serif, Chromium desktop không tái hiện được vì khác engine xử lý half-leading), giữ phòng ngừa
    tiếp cho Source Serif 4 (cũng là serif có cap-height/overshoot rõ, cùng lớp rủi ro) thay vì bỏ
    workaround rồi phải tìm lại lỗi từ đầu nếu nó tái phát."""
    _text = "#f1ece0" if IS_DARK else "#211c13"
    _text2 = "#b3a688" if IS_DARK else "#6f6650"
    if layout == "login":
        mark, forest_sz, dash_sz, gap_outer = 72, 46, 14, 22
        return (
            f"<style>{_LOGO_FONT_FACE}</style>"
            f"<div style='display:flex;flex-direction:column;align-items:center;gap:{gap_outer}px;'>"
            f"{_logo_mark_svg(mark)}"
            "<div style='display:flex;flex-direction:column;align-items:center;gap:4px;'>"
            f"<span style=\"font-family:'Source Serif 4',serif;font-weight:500;font-size:{forest_sz}px;"
            f"color:{_text};letter-spacing:0.01em;line-height:1.5;-webkit-font-smoothing:antialiased;"
            "transform:translateZ(0);display:inline-block;\">Forest</span>"
            f"<span style='font-size:{dash_sz}px;color:{_text2};text-transform:uppercase;"
            "letter-spacing:0.08em;'>Dashboard</span></div></div>"
        )
    mark, forest_sz, dash_sz, gap_outer = 48, 36, 14, 14
    # Cột chữ (Forest + Dashboard) lệch thấp hơn tâm thị giác của mark khi canh align-items:center
    # theo bounding-box thô: span "Forest" có line-height:1.5 (buộc phải giữ, xem docstring) đệm
    # thêm ~9px KHÔNG THẤY ở phía trên chữ, kéo trọng tâm thị giác của cả cột xuống dưới so với
    # trọng tâm hình học của nó -- lấy margin-top âm trên CHÍNH CỘT (không đụng vào span "Forest"/
    # line-height của nó, tránh đánh thức lại lỗi WebKit đã note trong docstring) để bù lại, canh
    # mark thẳng hàng thật với chữ "Forest" thay vì thẳng hàng với bounding-box cả cột.
    return (
        f"<style>{_LOGO_FONT_FACE}</style>"
        f"<div style='display:flex;flex-direction:row;align-items:center;justify-content:center;"
        f"gap:{gap_outer}px;'>"
        f"{_logo_mark_svg(mark)}"
        "<div style='display:flex;flex-direction:column;gap:2px;margin-top:-8px;'>"
        f"<span style=\"font-family:'Source Serif 4',serif;font-weight:500;font-size:{forest_sz}px;"
        f"color:{_text};letter-spacing:0.01em;line-height:1.5;-webkit-font-smoothing:antialiased;"
        "transform:translateZ(0);display:inline-block;\">Forest</span>"
        # margin-top:-10px (phương án D trong mock up) nhích "DASHBOARD" lên gần "Forest" hơn,
        # cân đối hơn so với khoảng trắng đệm ở trên do line-height:1.5 của "Forest" để lại.
        f"<span style='font-size:{dash_sz}px;color:{_text2};text-transform:uppercase;"
        "letter-spacing:0.08em;line-height:1;margin-top:-10px;'>Dashboard</span></div></div>"
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
        _login_txt2 = "#b3a688" if IS_DARK else "#6f6650"
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

# Font thân/nhãn/nút/điều hướng toàn app -- hệ "Sổ Tay" đổi từ system sans sang Manrope thật
# (tự host, không dùng <link> Google Fonts -- app không tải font qua mạng ở bất kỳ đâu khác).
# Biến trục (variable font, wght 200-800 trong 1 file) thay vì nhiều file tĩnh theo từng
# font-weight -- đỡ payload hơn hẳn vì app dùng nhiều mức đậm nhạt khác nhau (400/500/600/700/800)
# rải khắp label/nút/chip/nav. 3 file riêng theo unicode-range (latin/latin-ext/vietnamese, bỏ
# cyrillic/hy lạp không dùng tới) đúng cách Google Fonts tự chia subset -- BẮT BUỘC có "vietnamese"
# (khác _LOGO_FONT_FACE chỉ cần "latin" vì wordmark "Forest"/"Dashboard" là tiếng Anh) vì font
# này hiển thị toàn bộ nhãn/nút tiếng Việt có dấu của app.
@st.cache_resource
def _body_font_b64():
    out = {}
    for name in ("latin", "latin-ext", "vietnamese"):
        with open(os.path.join("assets", "fonts", f"Manrope-Variable-{name}.woff2"), "rb") as f:
            out[name] = base64.b64encode(f.read()).decode()
    return out

_BODY_FONT_RANGES = {
    "latin": "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
    "latin-ext": "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF",
    "vietnamese": "U+0102-0103,U+0110-0111,U+0128-0129,U+0168-0169,U+01A0-01A1,U+01AF-01B0,U+0300-0301,U+0303-0304,U+0308-0309,U+0323,U+0329,U+1EA0-1EF9,U+20AB",
}
_body_font_b64_cache = _body_font_b64()
_BODY_FONT_FACE = "".join(
    "@font-face { font-family:'Manrope'; font-style:normal; font-weight:200 800; "
    f"font-display:swap; src:url(data:font/woff2;base64,{_body_font_b64_cache[_name]}) format('woff2'); "
    f"unicode-range:{_ranges}; }}"
    for _name, _ranges in _BODY_FONT_RANGES.items()
)

# Font số liệu cho .dtbl (Bảng số liệu) -- hệ "Sổ Tay" đổi từ system sans sang IBM Plex Mono thật
# (tự host, cùng cách 2 font trên), khớp đúng bản mockup gốc (DTBL trong file thiết kế dùng
# 'IBM Plex Mono' cho toàn bảng). KHÔNG phải variable font (IBM Plex Mono không có bản variable
# trên Google Fonts, khác Manrope/Source Serif 4) -- phải tự host riêng 4 mức đậm nhạt đang dùng
# trong DTBL_CSS (400/500/600/700, xem .dtbl thead th/tr.cat/td.tot/tr.proj), mỗi mức 2 subset
# (latin + vietnamese, bỏ latin-ext/cyrillic/hy lạp -- DTBL chỉ có số + nhãn tiếng Việt ngắn,
# không cần phủ ký tự mở rộng như Manrope). Payload nhỏ (~56KB/8 file) vì mono chỉ cần tập ký tự
# hẹp (số + chữ cái, không kern/ligature phức tạp).
@st.cache_resource
def _table_font_b64():
    out = {}
    for weight_name in ("Regular", "Medium", "SemiBold", "Bold"):
        for subset in ("latin", "vietnamese"):
            with open(os.path.join("assets", "fonts", f"IBMPlexMono-{weight_name}-{subset}.woff2"), "rb") as f:
                out[(weight_name, subset)] = base64.b64encode(f.read()).decode()
    return out

_TABLE_FONT_WEIGHTS = {"Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700}
_TABLE_FONT_RANGES = {
    "latin": "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
    "vietnamese": "U+0102-0103,U+0110-0111,U+0128-0129,U+0168-0169,U+01A0-01A1,U+01AF-01B0,U+0300-0301,U+0303-0304,U+0308-0309,U+0323,U+0329,U+1EA0-1EF9,U+20AB",
}
_table_font_b64_cache = _table_font_b64()
_TABLE_FONT_FACE = "".join(
    "@font-face { font-family:'IBM Plex Mono'; font-style:normal; "
    f"font-weight:{_w_num}; font-display:swap; "
    f"src:url(data:font/woff2;base64,{_table_font_b64_cache[(_w_name, _subset)]}) format('woff2'); "
    f"unicode-range:{_ranges}; }}"
    for _w_name, _w_num in _TABLE_FONT_WEIGHTS.items()
    for _subset, _ranges in _TABLE_FONT_RANGES.items()
)

# Font "Trích dẫn hôm nay" (Hôm nay -- .kq-daily-mark/-text/-src, xem _render_daily_quote_card())
# -- Cormorant Garamond, tự host giống 2 font trên. Chọn qua mockup ảnh gửi người dùng duyệt (đã
# thử 6 phương án, chọn phương án "mảnh, cao, trang trọng" này). CHỈ 2 kiểu chữ đang dùng thật
# (SemiBold Italic 600 cho mark+quote text, Bold 700 thường cho tên sách/tác giả) x 2 subset
# (latin + vietnamese -- trích dẫn chỉ tiếng Anh gốc hoặc tiếng Việt dịch, không cần latin-ext/
# cyrillic như Manrope phải phủ rộng cho toàn bộ UI).
@st.cache_resource
def _quote_font_b64():
    out = {}
    for style_name in ("SemiBoldItalic", "Bold"):
        for subset in ("latin", "vietnamese"):
            with open(os.path.join("assets", "fonts", f"CormorantGaramond-{style_name}-{subset}.woff2"), "rb") as f:
                out[(style_name, subset)] = base64.b64encode(f.read()).decode()
    return out

_QUOTE_FONT_STYLES = {"SemiBoldItalic": ("italic", 600), "Bold": ("normal", 700)}
_QUOTE_FONT_RANGES = {
    "latin": "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
    "vietnamese": "U+0102-0103,U+0110-0111,U+0128-0129,U+0168-0169,U+01A0-01A1,U+01AF-01B0,U+0300-0301,U+0303-0304,U+0308-0309,U+0323,U+0329,U+1EA0-1EF9,U+20AB",
}
_quote_font_b64_cache = _quote_font_b64()
_QUOTE_FONT_FACE = "".join(
    "@font-face { font-family:'Cormorant Garamond'; "
    f"font-style:{_style}; font-weight:{_weight}; font-display:swap; "
    f"src:url(data:font/woff2;base64,{_quote_font_b64_cache[(_style_name, _subset)]}) format('woff2'); "
    f"unicode-range:{_ranges}; }}"
    for _style_name, (_style, _weight) in _QUOTE_FONT_STYLES.items()
    for _subset, _ranges in _QUOTE_FONT_RANGES.items()
)

# Token ngữ nghĩa cho toàn bộ CSS/HTML tự viết trong app (khối CSS lớn bên dưới + các khối CSS
# con + f-string HTML rải rác) -- (light, dark). Hệ "Sổ Tay": giấy ấm/ngà thay vì xám hệ thống
# iOS -- không còn đối xứng với bảng systemGray của Apple như bản cũ, mỗi cặp light/dark ở đây
# chọn tay theo đúng bản thiết kế "Sổ Tay" (xem design handoff).
_TOK = {
    "bg":      ("#f3efe4", "#1a1712"),
    "card":    ("#fdfbf5", "#262117"),
    "card-tl": ("rgba(253,251,245,0.85)", "rgba(38,33,23,0.85)"),   # nền input mờ (date/select)
    "text":    ("#211c13", "#f1ece0"),
    "text-2":  ("#6f6650", "#b3a688"),   # nhãn phụ (gộp cả #6e6e73/#9a9aa0 cũ)
    "text-3":  ("#a39877", "#857a5f"),   # nhãn mờ (gộp cả #a7a7ac cũ)
    "text-4":  ("#cabf9d", "#4f483a"),   # rất mờ (gộp cả #cfcfd4/#d2d2d7 cũ)
    "border":  ("#ddd3b8", "#3c3628"),
    "chip":    ("#ece4d0", "#322c20"),   # nền chip (gộp cả #f7f7f9/#eef0f2/#fafafa cũ)
    "divider": ("rgba(33,28,19,0.14)", "rgba(255,255,255,0.12)"),   # gộp mọi rgba(0,0,0,0.05-0.14)
    "divider-2": ("rgba(33,28,19,0.2)", "rgba(255,255,255,0.17)"),  # kẻ ngang mở đầu chương (sec-ch-rule) -- đậm hơn --divider thường
}
_root_vars = "".join(f"--{k}:{v[1] if IS_DARK else v[0]};" for k, v in _TOK.items())
st.markdown(
    f"<style>{_BODY_FONT_FACE}{_TABLE_FONT_FACE}{_QUOTE_FONT_FACE}:root{{--accent:{ACCENT};--accent-rgb:{ACCENT_RGB};--accent-dark:{ACCENT_DARK};"
    f"--bg-image:{BG_IMAGE};--bg-size:{BG_SIZE};--bg-position:{BG_POSITION};"
    f"{_root_vars}}}</style>",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <style>
    /* Đặt font trên html/body để kế thừa xuống; KHÔNG đặt !important rộng
       lên mọi phần tử để tránh đè font của icon Material (Material Symbols). Manrope tự host
       qua _BODY_FONT_FACE (tiêm ở khối <style> ngay phía trên) -- fallback hệ thống giữ nguyên
       phòng trường hợp @font-face lỗi/chưa kịp tải. */
    html, body, .stApp {
        font-family: 'Manrope', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    /* Nền trang hệ "Sổ Tay": kiểu hoạ tiết (chấm bi/trơn/kẻ ngang/kẻ ô vuông/chấm bi to) do người
       dùng chọn ở Tuỳ biến -> "4. Giao diện" (xem BG_PRESETS, lưu setting "bg_style"), truyền
       vào qua 2 biến CSS --bg-image/--bg-size (khối :root phía trên) thay vì literal cố định như
       trước, để đổi qua lại không cần sửa code. CHỈ áp cho .stApp (nền trang) -- KHÔNG được lan
       vào .glass-card/[stPlotlyChart]/[stVegaLiteChart]/.dtbl-wrap, các khối đó phải giữ mặt phẳng
       var(--card) không hoạ tiết để biểu đồ/bảng luôn dễ đọc, cá tính chỉ nằm ở phần lề trang
       xung quanh. */
    .stApp {
        background-color: var(--bg);
        background-image: var(--bg-image);
        background-size: var(--bg-size);
        background-position: var(--bg-position);
    }

    /* padding-top PHẢI đủ lớn để nội dung nằm HẲN dưới [data-testid="stHeader"] của Streamlit --
       thanh đó là position:absolute, height 60px CỐ ĐỊNH, z-index 999990 (rất cao), nền tô ĐẶC
       cùng màu --bg (không trong suốt) -- không phải 1 dải trong suốt vô hại, mà đè hẳn lên phần
       nội dung nằm trong 60px đầu trang, "che" mất (không phải bị cắt bởi overflow) logo/wordmark
       nếu padding-top nhỏ hơn ~60px + đệm an toàn. Đã đo lại bằng Playwright (bounding box thật
       của stHeader) sau khi bị che thật ở cả mobile lẫn desktop hẹp -- ĐỪNG giảm số này xuống dưới
       ~4rem chỉ vì "trông có vẻ dư" trên màn hình rộng, hãy đo lại bounding box stHeader trước. */
    .block-container { max-width: 1200px !important; margin: 0 auto !important; padding-top: 4.5rem !important; }
    /* Khoảng cách GIỮA các thành phần Streamlit xếp dọc -- từng thử 0.6rem (quá sát) rồi 0.9rem
       (trung dung), nay đổi hẳn về 10px theo ĐÚNG mockup hiện hành (mọi trang cuộn dọc kiểu
       chương đều dùng gap:10px cho khối bọc ngoài cùng, xem Forest Dashboard.dc.html) -- yêu cầu
       khớp pixel chính xác, không còn là ước lượng "trung dung" như trước. */
    [data-testid="stVerticalBlock"] { gap: 10px !important; }
    /* Streamlit bọc MỌI st.markdown(html) trong [data-testid="stMarkdownContainer"] có sẵn
       margin-bottom:-16px (bù trừ margin mặc định của <p> cuối cùng trong Markdown thật) -- các
       khối HTML tự viết ở đây đều là <div> thuần, không có <p> nào để bù, nên -16px này ăn thẳng
       vào chiều cao đo được của khối, làm phần tử kế tiếp (theo gap flex của khối cha) trèo lên
       che mất phần nội dung phía dưới cùng (xác nhận qua DevTools: .sec-ch cao 30px thật nhưng
       container cha chỉ đo được 14px). Huỷ margin âm này cho đúng nhóm khối bị ảnh hưởng RÕ RỆT
       (chương ngắn/thẻ đứng cuối 1 container) -- không áp toàn cục vì nhiều nơi khác đã tự xử lý
       việc này qua ":last-child { margin-bottom:0 }" nội bộ, không cần lặp lại. */
    [data-testid="stMarkdownContainer"]:has(> .sec-ch),
    [data-testid="stMarkdownContainer"]:has(> .sec-toc),
    [data-testid="stMarkdownContainer"]:has(> .glass-card),
    [data-testid="stMarkdownContainer"]:has(> .dtl-card),
    [data-testid="stMarkdownContainer"]:has(> .sec-card),
    [data-testid="stMarkdownContainer"]:has(> .catbars-card),
    [data-testid="stMarkdownContainer"]:has(> .quotes-card),
    [data-testid="stMarkdownContainer"]:has(> .hmtl-item) {
        margin-bottom: 0 !important;
    }

    /* Mục "Danh mục & dự án" dạng thanh ngang xếp hạng (frag_category_bars) -- thay biểu đồ tròn
       cũ, style theo mockup Forest Dashboard.dc.html: thẻ padding 16px 18px (khác 14px của thẻ
       biểu đồ Plotly/Vega vì đây là HTML thuần, không tự có card qua rule [data-testid=
       "stPlotlyChart"]), mỗi hàng nhãn 150px + thanh fill co giãn + giá trị 60px canh phải. */
    .catbars-card {
        background: var(--card); border: 1px solid var(--border); border-radius: 10px;
        padding: 16px 18px; box-shadow: 0 1px 1px rgba(0,0,0,0.02);
    }
    .catbars { display: flex; flex-direction: column; gap: 10px; }
    .catbar-row { display: grid; grid-template-columns: 150px 1fr 60px; align-items: center;
        gap: 10px; font-size: 13px; }
    /* Chương "Danh mục cả năm" (Báo cáo -> Năm, mockup, render_year_category_bars()) -- cột giá
       trị rộng hơn (110px so với 60px mặc định) vì có thêm % so với cùng kỳ năm trước cạnh giờ
       (vd "112h +31%"), 60px gốc không đủ chỗ. */
    .catbar-row.wide { grid-template-columns: 150px 1fr 110px; }
    .catbar-label { font-weight: 600; color: var(--text); overflow: hidden; text-overflow: ellipsis;
        white-space: nowrap; }
    .catbar-track { height: 18px; background: var(--chip); border-radius: 5px; overflow: hidden;
        display: block; }
    .catbar-fill { height: 100%; border-radius: 5px; display: block; }
    .catbar-val { text-align: right; font-variant-numeric: tabular-nums; color: var(--text); }
    .catbars-top { font-size: 12.5px; color: var(--text-2); margin-top: 2px; }
    /* Chương "Theo tuần trong tháng" (Báo cáo -> Tháng, mockup, render_month_week_bars()) -- CÙNG
       khuôn thẻ/thanh fill với .catbars-card/.catbar-* ở trên (frag_category_bars) nhưng cột
       nhãn/giá trị RỘNG HƠN hẳn (220px/110px so với 150px/60px) vì text dài hơn nhiều ("T27 ·
       29/06 – 05/07" so với "Học tập"), tách riêng class để không ảnh hưởng .catbar-* gốc. */
    .wkbar-row { display: grid; grid-template-columns: 220px 1fr 110px; align-items: center;
        gap: 10px; font-size: 13px; }
    .wkbar-label { font-weight: 600; color: var(--text); overflow: hidden; text-overflow: ellipsis;
        white-space: nowrap; }
    .wkbar-track { height: 18px; background: var(--chip); border-radius: 5px; overflow: hidden;
        display: block; }
    .wkbar-fill { height: 100%; border-radius: 5px; display: block; background: var(--accent); }
    .wkbar-val { text-align: right; font-variant-numeric: tabular-nums; color: var(--text); }
    /* Chương "Điểm nhấn" (Báo cáo -> Tháng, mockup, render_month_highlights()) -- 2 thẻ ngang,
       mỗi thẻ 1 danh sách dòng gọn (icon/emoji + câu ngắn), KHÔNG dùng .sp-chips (chip pill) vì
       mockup vẽ dạng danh sách dòng trần, không phải chip. */
    .hlt-list { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }
    .hlt-item { font-size: 13.5px; color: var(--text); line-height: 1.5; }

    /* Sub-tab "Lịch sử" (Sức khoẻ, _render_health_history()) -- dòng thời gian các lần khám:
       chấm + đường nối bên trái. Mỗi .hmtl-item tự vẽ đoạn đường của riêng nó, kéo dài quá
       margin-bottom để nối liền sang chấm kế tiếp -- không dùng 1 đường kẻ chung xuyên suốt vì
       giữa các thẻ còn chèn expander sửa/xoá là widget Streamlit thật, không nằm trong cùng khối
       HTML để vẽ đường kẻ liên tục qua được. */
    .hmtl-item { position: relative; padding-left: 26px; margin-bottom: 16px; }
    .hmtl-item:last-child { margin-bottom: 0; }
    .hmtl-dot { position: absolute; left: 2px; top: 5px; width: 11px; height: 11px; border-radius: 50%;
        background: var(--accent); box-shadow: 0 0 0 3px var(--card); z-index: 1; }
    .hmtl-dot.warn { background: #ff3b30; }
    .hmtl-line { position: absolute; left: 7px; top: 16px; bottom: -16px; width: 2px; background: var(--divider); }
    .hmtl-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px;
        padding: 14px 16px; box-shadow: 0 1px 1px rgba(0,0,0,0.02); }
    .hmtl-head { display: flex; align-items: center; justify-content: space-between; gap: 10px;
        flex-wrap: wrap; margin-bottom: 8px; }
    .hmtl-date { font-size: 15px; font-weight: 700; color: var(--text); }
    .hmtl-badge { font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 9px; white-space: nowrap; }
    .hmtl-badge.bad { background: rgba(255,59,48,0.12); color: #ff3b30; }
    .hmtl-badge.ok { background: rgba(52,199,89,0.12); color: #34c759; }
    .hmtl-grp { margin-top: 10px; }
    .hmtl-grp:first-of-type { margin-top: 0; }
    /* Chip chỉ số bất thường (ngoài khoảng tham chiếu) -- tô đỏ, dùng CHUNG khuôn .jchip (đã có
       ck/cv) thêm 1 mũi tên Material lên/xuống tuỳ Giá trị vượt Ref cao hay dưới Ref thấp. */
    .jchip.abn { background: rgba(255,59,48,0.10); }
    .jchip.abn .cv { color: #ff3b30; }
    /* Sub-tab "Báo cáo" (_render_health_report()) -- 2 khối mới theo mockup: card chi tiết chỉ
       số bất thường (chương 1) và lưới mini-card xu hướng (chương 2), CÙNG khuôn .hmtl-card cho
       đồng bộ với các thẻ khác của trang Sức khoẻ (Lịch sử, Dữ liệu đầu vào). */
    .hbn-grid, .htrend-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 12px; margin-top: 10px; }
    .hbn-value { font-size: 28px; font-weight: 800; color: var(--text); margin-top: 4px; line-height: 1; }
    .hbn-value .hbn-unit { font-size: 14px; font-weight: 600; color: var(--text-2); margin-left: 4px; }
    .hbn-delta { font-size: 12.5px; font-weight: 600; color: #ff3b30; margin-top: 6px; }
    .hbn-delta span[style] { vertical-align: -2px; margin-right: 2px; }
    .htrend-card .hmtl-head { margin-bottom: 12px; }
    .htrend-title { font-size: 13.5px; font-weight: 700; color: var(--text); }
    .htrend-title .htrend-unit { font-size: 11.5px; font-weight: 500; color: var(--text-2); }
    .htrend-bars { display: flex; align-items: flex-end; gap: 10px; height: 88px; }
    .htrend-bar-col { flex: 1 1 0; display: flex; flex-direction: column; align-items: center;
        justify-content: flex-end; height: 100%; }
    .htrend-bar-val { font-size: 11px; font-weight: 700; color: var(--text-2); margin-bottom: 4px;
        white-space: nowrap; }
    .htrend-bar-val.abn { color: #ff3b30; }
    .htrend-bar { width: 100%; max-width: 34px; border-radius: 4px 4px 0 0; background: var(--accent); }
    .htrend-bar.abn { background: #ff3b30; }
    .htrend-bar-date { font-size: 10.5px; color: var(--text-2); margin-top: 5px; }
    .htrend-caption { font-size: 12.5px; color: var(--text-2); margin-top: 10px; }
    /* Chương 3 "Bảng xét nghiệm đầy đủ" -- text đánh giá màu theo trạng thái, dùng CHUNG 2 màu
       đỏ/xanh với mọi nơi khác của Sức khoẻ (không có mức "sát ngưỡng" -- xem docstring
       _health_is_abnormal, quyết định giữ nhị phân đã xác nhận với người dùng). */
    .dtbl .heval-bad { color: #ff3b30; font-weight: 600; }
    .dtbl .heval-ok { color: #34c759; font-weight: 600; }
    /* Nhãn widget (Nhóm/Chỉ số/Ngày lấy mẫu/Năm...) trong trang Sức khoẻ -- mặc định Streamlit
       mảnh + nhạt màu, dễ lướt qua khi nhãn chính là nội dung cần đọc trước (chọn ĐÚNG Nhóm/Chỉ
       số muốn xem, không phải phụ chú). Đậm + rõ hơn, chỉ áp dụng trong phạm vi trang Sức khoẻ
       (mọi widget ở đây đặt key tiền tố "hm_") -- không đổi nhãn widget ở các trang khác. */
    [class*="st-key-hm_"] [data-testid="stWidgetLabel"] p {
        font-weight: 700 !important; color: var(--text) !important; font-size: 13.5px !important;
    }
    /* Expander "Sửa / xoá xét nghiệm đã nhập" (_render_health_history()) -- ghi đè riêng trong
       phạm vi container key="hm_hist_edit" để trông như 1 thẻ hộp khớp .hmtl-card phía trên, thay
       vì tiêu đề gạch chân kiểu chương báo cáo (mặc định của [data-testid="stExpander"], xem rule
       phía dưới) sẽ lạc tông với timeline card ngay trên nó. CÙNG khuôn với FAQ (Trợ giúp, key=
       "help_faq") -- tái dùng đúng pattern đã có, không phát sinh style mới. */
    [class*="st-key-hm_hist_edit"] [data-testid="stExpander"] { margin: 14px 0 0 !important; }
    [class*="st-key-hm_hist_edit"] [data-testid="stExpander"] details {
        background: var(--card) !important; border: 1px solid var(--border) !important;
        border-radius: 10px !important; box-shadow: 0 1px 1px rgba(0,0,0,0.02) !important; }
    [class*="st-key-hm_hist_edit"] [data-testid="stExpander"] summary {
        padding: 12px 16px !important; border-bottom: none !important; }
    [class*="st-key-hm_hist_edit"] [data-testid="stExpander"] summary p {
        font-size: 14px !important; font-weight: 600 !important; color: var(--text-2) !important; }
    [class*="st-key-hm_hist_edit"] [data-testid="stExpander"] details[open] > summary {
        border-bottom: 1px solid var(--divider) !important; }
    [class*="st-key-hm_hist_edit"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        padding: 10px 16px 14px !important; }

    .glass-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 1px 1px rgba(0,0,0,0.02);
    }

    h1, h2, h3 { color: var(--text) !important; font-weight: 600 !important; letter-spacing: -0.5px !important; }
    hr { border-color: var(--divider) !important; }
    
    div[data-testid="stButton"] button[kind="primary"] {
        background-color: var(--accent) !important;
        color: white !important;
        border-radius: 7px !important;
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
        border-radius: 7px !important;
        border: 1px solid var(--border) !important;
        font-weight: 500 !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
    }
    div[data-testid="stButton"] button { width: 100%; }

    .stSelectbox > div > div, .stTextInput > div > div > input {
        border-radius: 7px !important;
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
        border-radius: 10px;
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
    .stat-panel .sp-hi { flex: 1; min-width: 130px; padding: 2px 14px; border-right: 1px solid var(--divider); }
    .stat-panel .sp-hi:first-child { padding-left: 2px; }
    .stat-panel .sp-hi:last-child { border-right: none; }
    .stat-panel .sp-l { font-size: 11px; color: var(--text-2); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    .stat-panel .sp-v { font-size: 28px; font-weight: 600; letter-spacing: -0.5px; line-height: 1.18; color: var(--text); font-variant-numeric: tabular-nums; }
    .stat-panel .sp-d { font-size: 13px; font-weight: 500; margin-top: 2px; }
    /* Mỗi nhóm = 1 hàng: nhãn bên trái, các chip cùng hàng -> tiết kiệm chiều cao */
    .stat-panel .sp-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; margin-top: 12px; }
    .stat-panel .sp-sub { font-size: 11px; color: var(--text-2); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin: 0; flex: 0 0 160px; }
    .stat-panel .sp-chips { display: flex; flex-wrap: wrap; gap: 6px; flex: 1 1 auto; }
    @media (max-width: 640px) { .stat-panel .sp-sub { flex-basis: 100%; } }
    /* white-space KHÔNG nowrap (khác vẻ ngoài "viên thuốc" gọn thường thấy) -- vài chip mang giá
       trị tự do dài (vd "Phần gần nhất" là tên chương/tập, không có độ dài cố định) sẽ tràn ra
       ngoài khung thẻ trên màn hẹp nếu ép 1 dòng; max-width + word-break đảm bảo chip luôn co
       vừa bề rộng thẻ, xuống dòng bên TRONG chip thay vì tràn ra ngoài. Chip giá trị ngắn (đa số)
       không bị ảnh hưởng vì nội dung đã ngắn hơn 1 dòng sẵn. */
    /* .maprow .chip: badge Danh mục ở bảng Phân loại tĩnh (Tuỳ biến -> chương "2. Phân loại") --
       tái dùng nguyên class chip/ck/cv của .stat-panel/.pbill-chips, chỉ thêm vào phạm vi scope
       vì không phải billboard/stat-panel. */
    .stat-panel .chip, .pbill-chips .chip, .maprow .chip { border-radius: 9px; padding: 6px 10px; font-size: 12.5px; white-space: normal;
        max-width: 100%; overflow-wrap: break-word; word-break: break-word; background: var(--chip); }
    .stat-panel .chip .ck, .pbill-chips .chip .ck { color: var(--text-2); }
    .stat-panel .chip .cv, .pbill-chips .chip .cv { font-weight: 600; color: var(--text); margin-left: 5px; }
    .stat-panel .chip .cd, .pbill-chips .chip .cd { font-weight: 500; margin-left: 6px; }
    .stat-panel .chip.tw, .pbill-chips .chip.tw { background: rgba(var(--accent-rgb),0.10); }
    /* Hàng chip billboard Sách (Cùng lúc/Phần đọc gần nhất/trích dẫn đã lưu...) -- tái dùng
       nguyên class chip/ck/cv/tw của .stat-panel (giá trị CSS giống hệt mockup), chỉ đổi phạm vi
       scope sang .pbill-chips vì billboard không phải .stat-panel. */
    .pbill-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
    /* Badge trạng thái "Đang hoạt động"/"Không hoạt động" cạnh tên Dự án/Nhóm ở billboard Báo
       cáo -> Dự án (mockup) -- đặt cạnh .pbill-booktitle nên dùng vertical-align để canh giữa
       theo dòng chữ 26px, không lệch lên/xuống. */
    .pbill-status { display: inline-block; font-size: 12.5px; font-weight: 700; padding: 3px 10px;
        border-radius: 20px; margin-left: 10px; vertical-align: middle; }
    .pbill-status.active { background: rgba(var(--accent-rgb),0.10); color: var(--accent-dark); }
    .pbill-status.inactive { background: var(--chip); color: var(--text-3); }
    .stat-panel .sp-divider { border-top: 1px solid var(--divider); margin: 10px 0 2px; }
    .stat-panel .sp-glabel { font-size: 11px; font-weight: 700; color: var(--accent); text-transform: uppercase; letter-spacing: 0.6px; margin-top: 10px; }
    .stat-panel > .sp-glabel:first-child { margin-top: 0; }
    /* .sp-row có margin-top để tách với .sp-hero phía trên -- khi KHÔNG có hero (vd panel
       "Tham khảo cho lên kế hoạch" chỉ có sections, không hero_items), .sp-row là con đầu tiên
       nên margin đó cộng dồn với padding của card, làm lề trên dày hơn lề dưới rõ rệt. */
    .stat-panel > .sp-row:first-child { margin-top: 0; }
    .stat-panel .chip.tw .ck { color: var(--accent-dark); }
    .stat-panel .chip.tw .cv { color: var(--accent); }
    .section-hd { font-size: 14.5px; font-weight: 700; color: var(--text); margin: 18px 0 8px; letter-spacing: -0.2px; }

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
        padding: 6px 2px !important;
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
    /* Cỡ chữ/độ đậm theo đúng mockup "Sổ Tay" (khối "06 · Bảng số liệu"): 17px/700, không kéo
       letter-spacing âm -- bản cũ 1.35rem (21.6px) + letter-spacing -0.4px nặng nề hơn hẳn mockup,
       trông "to bè" thay vì thanh thoát. */
    [data-testid="stExpander"] summary p {
        font-size: 17px !important;
        font-weight: 700 !important;
        color: var(--text) !important;
    }
    /* Streamlit tự tô nền secondaryBackgroundColor (.streamlit/config.toml) lên khối nội dung
       BÊN TRONG expander -- rule "background:transparent" ở [data-testid="stExpander"]/details
       phía trên KHÔNG lan tới đây vì stExpanderDetails là 1 div riêng, tự có màu nền của nó, không
       kế thừa nền "trong suốt" từ cha. Thiếu dòng này, mục mở rộng hiện khối xám lạc tông ngay khi
       bấm mở -- lỗi đã có từ đầu (không phải regression của bản "Sổ Tay"), giờ mới bị chú ý vì nền
       trang đổi từ xám nhạt Apple sang giấy ấm nên độ lệch tông rõ hơn hẳn. */
    [data-testid="stExpander"] [data-testid="stExpanderDetails"] { padding-top: 10px !important; background: transparent !important; }

    /* Thanh chọn trang (segmented control) căn giữa, cách nội dung một chút */
    [data-testid="stButtonGroup"] { margin-bottom: 10px; }
    /* Nút đang chọn trong mọi segmented_control (nav bar + bộ lọc biểu đồ: Khoảng thời gian,
       Phân loại, Xem theo...) -> nền màu accent đặc + chữ/icon trắng + đổ bóng, đồng bộ với
       nút primary. Streamlit >=1.59 đổi hẳn markup nội bộ của segmented_control -- nút không còn
       thuộc tính kind="segmented_controlActive" nữa, "đang chọn" giờ đánh dấu bằng
       data-selected="true" (cùng thuộc tính dùng cho tab đang chọn ở st.tabs(), xem bên dưới) --
       toàn bộ 3 selector kind="segmented_controlActive" trong khối CSS này (nút nav chính, bộ
       lọc biểu đồ, sub-tab Báo cáo/Sức khoẻ) đã CHẾT sau khi nâng cấp Streamlit, chọn lại theo
       thuộc tính mới. */
    button[data-selected="true"] {
        background-color: var(--accent) !important;
        color: #fff !important;
        border-color: var(--accent) !important;
        box-shadow: 0 2px 5px rgba(var(--accent-rgb),0.3) !important;
    }
    /* Theo mockup "Sổ Tay": MỌI segmented_control trong app (nav, bộ lọc biểu đồ "Khoảng thời
       gian"/"Gộp theo"/"Phân loại"/"Xem theo"...) hiện thành các nút RỜI (bo tròn 4 góc + có
       khoảng cách), không phải 1 dải liền khối kiểu mặc định Streamlit/BaseWeb (chỉ bo góc 2 đầu
       dải, nút giữa border-radius:0, margin-right:-1px đè khít viền lên nhau để trông liền mạch).
       QUAN TRỌNG: [data-testid="stButtonGroup"] chỉ là khối BỌC NGOÀI (1 <div> chứa đúng 1 con) --
       flex container THẬT SỰ chứa các <button> là 1 [role="radiogroup"] LỒNG BÊN TRONG nó (đã xác
       nhận qua DOM inspect: gap đặt ở stButtonGroup không có tác dụng gì vì nó không phải cha trực
       tiếp của các nút, dù getComputedStyle vẫn báo "6px" -- giá trị đó chỉ tồn tại trên phần tử
       không quyết định layout). Phải đặt gap/flex-wrap/justify-content lên đúng
       [role="radiogroup"] thì khoảng cách mới thật sự hiện ra. Áp DÙNG CHUNG cho mọi
       [data-testid="stButtonGroup"] -- 2 nơi cố tình khác kiểu (tab gạch chân ở "Chọn kỳ xem"/
       "Xem theo", khối .st-key-bc_sub_picker/.st-key-hm_sub_picker ngay dưới) tự ghi đè lại được
       vì đứng SAU trong stylesheet này, cùng độ đặc hiệu selector nên nguồn sau thắng (xem thêm
       ghi chú "gap:0" ở khối đó). */
    [data-testid="stButtonGroup"] [role="radiogroup"] { gap: 6px !important; }
    /* BaseWeb tự làm TRONG SUỐT cạnh viền giáp nút đang chọn (border-left/right-color:
       transparent) trên 2 nút LÂN CẬN -- di sản từ kiểu dải liền khối cũ (viền đè khít lên
       nhau để trông liền mạch), giờ các nút đã tách rời có khoảng cách nên để lộ ra thành viền
       nửa vời/mất nét ở đúng cạnh giáp nút được chọn (xác nhận qua DOM inspect: border-color
       của nút lân cận trả về "... rgba(0,0,0,0) ..." ở 1 cạnh thay vì đều 4 cạnh). Ép lại đều
       cả 4 cạnh theo đúng var(--border) để huỷ hoàn toàn hành vi cũ đó. */
    [data-testid="stButtonGroup"] button {
        border-radius: 7px !important;
        margin: 0 !important;
    }
    [data-testid="stButtonGroup"] button:not([data-selected="true"]) {
        border-color: var(--border) !important;
    }

    /* Riêng thanh điều hướng trang: căn giữa cả hàng nút.
       Element container mặc định co theo nội dung -> ép full width rồi căn giữa. `width:100%`
       trên chính role="radiogroup" (thử trước đây) KHÔNG ăn -- vẫn ra đúng bề rộng khít nội dung
       (đã đo bounding box xác nhận, không rõ nguyên nhân sâu, có thể do BaseWeb tự tính lại kích
       thước bằng JS). Đổi hướng: KHÔNG ép radiogroup rộng 100% nữa -- để nó tự nhiên rộng vừa nội
       dung (fit-content), rồi biến chính stButtonGroup (khối NGOÀI, vốn đã rộng đủ 100% nav bar)
       thành flex container với justify-content:center để tự căn giữa đứa con fit-content đó. */
    .st-key-nav { width: 100% !important; }
    .st-key-nav [data-testid="stButtonGroup"] { display: flex !important; justify-content: center !important; width: 100% !important; }
    .st-key-nav [data-testid="stButtonGroup"] [role="radiogroup"] { flex-wrap: wrap !important; max-width: 100%; }
    /* Nút CHƯA chọn trên nav chính: nền kem var(--card) khớp màu mọi card bên dưới (mặc định
       Streamlit/BaseWeb không đặt nền riêng cho nút segmented_control chưa chọn, rơi về nền
       trắng/xám trung tính của theme, lệch tông khỏi hệ "Sổ Tay"). Chỉ áp cho nav chính, không
       đụng các segmented_control khác (bộ lọc biểu đồ...) -- những nơi đó chưa có yêu cầu đổi. */
    .st-key-nav [data-testid="stButtonGroup"] button:not([data-selected="true"]) {
        background-color: var(--card) !important;
    }
    /* Giảm khoảng cách dọc xuống Date Picker ngay dưới nav (mặc định 10px margin-bottom của
       stButtonGroup + 10px gap flex chung = 20px, hơi rộng) -- chỉ scope riêng nav chính. Margin
       ÂM (không chỉ về 0) để lấn bớt cả gap flex 10px của khối cha -- 2px rồi 0px vẫn còn rộng
       theo phản hồi thực tế, -6px cho tổng khoảng cách còn ~4px (10px gap - 6px). */
    .st-key-nav [data-testid="stButtonGroup"] { margin-bottom: -6px !important; }
    /* Toggle điều khiển (Khoảng thời gian/Gộp theo/Phân loại...) xuống thẻ biểu đồ ngay dưới, ÁP
       DỤNG CHUNG CHO MỌI BIỂU ĐỒ trong app (frag_pie key="piewrap_...", frag_calendar/frag_trend/
       frag_hourly/frag_period_trend key="chartopt_..." -- mỗi hàm bọc TOÀN BỘ nội dung (hàng
       toggle + biểu đồ) trong 1 container riêng, xem docstring frag_pie). Ghi đè trực tiếp "gap"
       flex của CHÍNH container đó xuống 4px (thay vì 10px chung toàn trang) -- sửa qua margin-
       bottom của stButtonGroup (như nav bar/sub-tab picker ở trên) KHÔNG hiệu quả ở đây vì
       frag_trend/frag_hourly xếp 2-3 toggle cạnh nhau qua st.columns(), margin-bottom của từng
       stButtonGroup lồng trong cột không cộng dồn vào gap flex ngoài cùng như trường hợp 1 toggle
       đơn (piewrap_/nav) -- đo thật bằng Playwright xác nhận marginBottom áp đúng nhưng khoảng
       cách hiển thị không đổi, phải sửa thẳng "gap" của container mới ăn. */
    [class*="st-key-piewrap_"], [class*="st-key-chartopt_"] {
        gap: 4px !important;
    }

    /* Cùng ý căn giữa như thanh nav chính, áp cho thanh chọn sub-tab "Chọn kỳ xem" (Báo cáo) và
       "Xem theo" (Sức khoẻ) -- label đã ẩn (label_visibility="collapsed") nên bố cục giống hệt
       .st-key-nav ở trên. Đổi thêm dáng nút từ pill sang tab gạch chân (giống Tổng quan/Chi tiết
       ở Sách/Gundam) cho gọn và nhất quán, thay vì nền đặc teal như nav chính -- gap:0 để huỷ gap
       chung 6px ở trên (khoảng cách giữa các tab ở đây đến từ margin:0 14px của từng nút bên
       dưới, không phải gap của container, cộng cả 2 sẽ ra khoảng cách quá lớn). */
    .st-key-bc_sub_picker, .st-key-hm_sub_picker { width: 100% !important; }
    .st-key-bc_sub_picker [data-testid="stButtonGroup"], .st-key-hm_sub_picker [data-testid="stButtonGroup"] { display: flex !important; justify-content: center !important; width: 100% !important; }
    .st-key-bc_sub_picker [data-testid="stButtonGroup"] [role="radiogroup"], .st-key-hm_sub_picker [data-testid="stButtonGroup"] [role="radiogroup"] { flex-wrap: wrap !important; max-width: 100%; gap: 0 !important; }
    .st-key-bc_sub_picker button, .st-key-hm_sub_picker button {
        background: transparent !important; border: none !important; border-radius: 0 !important;
        border-bottom: 2px solid transparent !important; box-shadow: none !important;
        color: var(--text-2) !important; padding: 8px 4px !important; margin: 0 14px !important;
    }
    .st-key-bc_sub_picker button[data-selected="true"], .st-key-hm_sub_picker button[data-selected="true"] {
        background: transparent !important; color: var(--accent) !important; font-weight: 600 !important;
        border-bottom-color: var(--accent) !important; box-shadow: none !important;
    }
    /* [class*=...] (substring), KHÔNG phải .st-key-rl_view_tabs (class chính xác) -- Sách dùng
       key "rl_view_tabs", Gundam dùng "rl_view_tabs_gd" (tách riêng để không đụng state tab khi
       chuyển qua lại 2 trang, xem render_reading_log()); chọn theo class chính xác trước đây chỉ
       khớp Sách, khiến tab Gundam mất hẳn 2 rule căn giữa/ẩn vạch xám bên dưới. */
    [class*="st-key-rl_view_tabs"] [role="tablist"] { justify-content: center !important; }
    /* st.tabs() tự vẽ thêm 1 vạch xám full-width bên dưới toàn bộ hàng tab -- ::after của
       [role="tablist"] trong markup Streamlit >=1.59 (trước là 1 element riêng
       data-baseweb="tab-border", đã đổi hẳn) -- không có ở "Chọn kỳ xem" (Báo cáo, dùng
       segmented_control tự dựng, không có vạch này) -- ẩn đi cho 2 giao diện đồng nhất. */
    [class*="st-key-rl_view_tabs"] [role="tablist"]::after { display: none !important; }

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
    /* day_stepper riêng: mockup thu gọn cả hàng ◀ [ngày] ▶ về đúng bề rộng nội dung rồi canh
       giữa trang (KHÔNG kéo giãn full-width như period_stepper của Báo cáo, vốn cần chiếm hết
       hàng ngang cho các lựa chọn kỳ) -- 2 cột nút cố định 44px, cột ngày co theo nội dung
       thay vì flex-grow theo tỉ lệ [1,8,1] mặc định. */
    [class*="st-key-day_stepper"] [data-testid="stHorizontalBlock"] {
        width: fit-content !important; margin: 0 auto !important;
    }
    [class*="st-key-day_stepper"] [data-testid="stColumn"]:first-child,
    [class*="st-key-day_stepper"] [data-testid="stColumn"]:last-child {
        flex: 0 0 44px !important; width: 44px !important;
    }
    [class*="st-key-day_stepper"] [data-testid="stColumn"]:not(:first-child):not(:last-child) {
        flex: 0 0 auto !important; width: auto !important;
    }
    /* Nút ◀/▶ ở day_stepper cao 40px (min-height mặc định Streamlit) trong khi ô st.date_input
       chỉ cao ~36px -- vertical_alignment="center" của st.columns canh giữa theo TÂM mỗi item,
       không kéo chúng về cùng 1 chiều cao, nên 2 nút trông lệch thấp hơn vài px so với ô ngày dù
       đã "canh giữa". Ép cùng 36px cho cả 3 phần tử trên 1 hàng thẳng hàng thật sự. */
    [class*="st-key-day_stepper"] button { height: 36px !important; min-height: 0 !important; }
    /* Cột giữa (chứa st.date_input) cao hơn hẳn 2 cột nút (~50px vs 36px) dù widget bên trong chỉ
       cao 36px -- Streamlit tự dành sẵn 1 khoảng "block" tối thiểu cho mỗi widget (từng chứa
       nhãn) bất kể label_visibility="collapsed" đã ẩn nhãn đi, CỘNG THÊM 1 stElementContainer ẩn
       thứ 2 (thông báo cho screen reader) khiến scrollHeight thật > offsetHeight -- xác nhận qua
       DevTools thật, ảnh chụp người dùng gửi. Vì cột này CAO HƠN nên vertical_alignment="center"
       của st.columns coi nó là chuẩn để so - 2 nút bị đẩy xuống canh giữa theo chiều cao NÀY.
       Thử canh giữa nội dung trong cột (justify-content) KHÔNG ăn -- phần tử ẩn thứ 2 khiến tổng
       nội dung "tràn" ra ngoài khối 50px, trình duyệt rơi về "safe center" (= flex-start) thay vì
       centering thật khi nội dung tổng vượt quá kích thước khối chứa. Ép thẳng khối bọc (và ép
       tràn bị cắt bởi overflow:hidden) về đúng 36px như 2 cột nút -- cả 3 cột bằng nhau thì
       vertical_alignment="center" không còn gì để lệch nữa, không phụ thuộc justify-content. */
    [class*="st-key-day_stepper"] [data-testid="stColumn"] [data-testid="stVerticalBlock"] {
        height: 36px !important;
        min-height: 36px !important;
        max-height: 36px !important;
        overflow: hidden !important;
        flex-grow: 0 !important;
    }
    /* Bộ chọn kỳ (period_stepper key="stepper_week"/"stepper_month"/"stepper_year", Báo cáo ->
       Tuần/Tháng/Năm) thu gọn + canh giữa CÙNG kiểu day_stepper (Hôm nay) -- xem lại thấy đồng bộ
       đẹp hơn để full-width như trước (ghi chú cũ ở rule [class*="stepper"] phía trên vẫn đúng lý
       do LÚC ĐÓ, chỉ là đổi quyết định thẩm mỹ). 4 cột (lùi/chọn kỳ/tiến/về hiện tại) -- 3 cột nút
       cố định 44px (chọn theo :not(:nth-child(2)), không phải :first-child/:last-child như
       day_stepper 3 cột, vì period_stepper có thêm cột nút "về hiện tại" thứ 4), cột selectbox co
       theo nội dung. */
    [class*="st-key-stepper_"] [data-testid="stHorizontalBlock"] {
        width: fit-content !important; margin: 0 auto !important;
    }
    [class*="st-key-stepper_"] [data-testid="stColumn"]:not(:nth-child(2)) {
        flex: 0 0 44px !important; width: 44px !important;
    }
    [class*="st-key-stepper_"] [data-testid="stColumn"]:nth-child(2) {
        flex: 0 0 auto !important; width: auto !important;
    }
    [class*="st-key-stepper_"] button { height: 36px !important; min-height: 0 !important; }
    [class*="st-key-stepper_"] [data-testid="stColumn"] [data-testid="stVerticalBlock"] {
        height: 36px !important;
        min-height: 36px !important;
        max-height: 36px !important;
        overflow: hidden !important;
        flex-grow: 0 !important;
    }

    /* st.date_input (hộp chọn "Ngày" ở Hôm nay, "Từ ngày"/"Đến ngày" ở Đồng bộ lịch -- Khoảng khác…)
       mặc định mang màu đỏ gốc của theme Streamlit (#FF4B4B) -- không liên quan gì tới accent
       đang chọn, khiến hộp trông lệch tông so với hộp chọn kỳ cạnh nó (period_stepper, dùng
       st.selectbox, viền xám trung tính #d1d1d6/nền trắng mờ). Đồng bộ lại viền/nền theo đúng
       kiểu selectbox, còn màu ngày đang chọn trong lịch bật lên đổi theo accent. Lịch bật lên
       (data-baseweb="calendar") được BaseWeb mount ra ngoài container widget (portal ở cấp
       body), nên phải chọn toàn cục theo [data-baseweb], không scope theo .st-key-... được --
       áp dụng cho MỌI date_input trong app, không riêng "Ngày" ở Hôm nay. */
    /* BaseWeb lồng 3 lớp cho input này: [data-baseweb="input"] (khung ngoài) bọc
       [data-baseweb="base-input"] (khung sát input, THỰC SỰ mang nền/viền theo CSS mặc định của
       BaseWeb) bọc <input> thật -- xác nhận qua DevTools thật trên bản deploy (ảnh chụp người
       dùng gửi), khác với giả định ban đầu chỉ có 1 lớp bọc. Bản sửa trước chỉ ép chiều cao cho
       khung ngoài -- không đủ, vì khung base-input bên trong vẫn theo chiều cao mặc định (to hơn
       hẳn 36px của 2 nút ◀▶ cạnh nó), không bị outer's height:36 ràng buộc (overflow mặc định là
       visible). Ép ĐỒNG NHẤT cả 3 lớp về 36px + overflow:hidden ở khung ngoài để chắc chắn cắt
       đúng 36px dù còn sót lớp nào chưa lường hết. */
    div[data-testid="stDateInput"] [data-baseweb="input"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        height: 36px !important;
        min-height: 36px !important;
        box-sizing: border-box !important;
        overflow: hidden !important;
    }
    div[data-testid="stDateInput"] [data-baseweb="base-input"] {
        background: var(--card-tl) !important;
        border: 1px solid var(--border) !important;
        border-radius: 7px !important;
        box-shadow: none !important;
        height: 36px !important;
        min-height: 36px !important;
        box-sizing: border-box !important;
    }
    div[data-testid="stDateInput"] [data-baseweb="input"] input {
        height: 36px !important;
        line-height: 36px !important;
        box-sizing: border-box !important;
        -webkit-appearance: none !important;
        appearance: none !important;
    }
    div[data-testid="stDateInput"] [data-baseweb="input"]:focus-within [data-baseweb="base-input"] {
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
       lại bằng var(--accent) cho đồng bộ. Streamlit >=1.59 đổi hẳn markup nội bộ (không còn
       [data-baseweb="tab"]/"tab-highlight" nữa -- tab dùng role="tab" + aria-selected qua
       data-testid="stTab", vạch gạch chân là 1 div.react-aria-SelectionIndicator riêng, tự định
       vị bằng CSS tuyệt đối theo đúng tab đang chọn) -- chọn lại theo markup mới, KHÔNG scope
       theo key nào vì áp dụng chung cho MỌI st.tabs() kể cả nơi không đặt key (vd "1. Dữ liệu
       đầu vào" -> tab "Tải trích dẫn Kindle"...). */
    [data-testid="stTab"][aria-selected="true"] { color: var(--accent) !important; }
    .react-aria-SelectionIndicator { background: var(--accent) !important; }

    /* ===== Tinh chỉnh riêng cho điện thoại (không ảnh hưởng desktop) ===== */
    @media (max-width: 640px) {
        h1 { font-size: 1.9rem !important; line-height: 1.15 !important; }
        h2, [data-testid="stHeading"] h2 { font-size: 1.35rem !important; }
        h3 { font-size: 1.1rem !important; }
        [data-testid="stExpander"] summary p { font-size: 15px !important; }
        /* padding-top GIỮ NGUYÊN bằng bản desktop (không giảm riêng cho mobile) -- xem chú thích
           đầy đủ ở rule .block-container gốc phía trên: cả 2 breakpoint đều cần đủ khoảng trống
           để lọt qua [data-testid="stHeader"] cố định 60px của Streamlit, mobile không phải
           ngoại lệ. */
        .block-container { padding-left: 0.8rem !important; padding-right: 0.8rem !important; padding-top: 4.5rem !important; }

        /* Thẻ gọn lại, bớt khoảng trống thừa (height:auto để không bị kéo giãn khi xếp dọc) --
           16px (không phải 20px như desktop) vì màn hẹp vẫn cần tiết kiệm bề ngang hơn. */
        .glass-card { padding: 16px !important; height: auto !important; }
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

    /* Khối "Ghi chú chính" (note_main) đứng ngay sau danh sách ghi chú nhanh (qnote_row_) trong
       CÙNG 1 khối cha -- rule gap:5px thu gọn khoảng cách GIỮA CÁC DÒNG ghi chú nhanh (xem CSS
       :has() qnote_row_ ở trên) vô tình áp luôn cho khoảng cách trước "Ghi chú chính", khiến nó
       dính sát ghi chú nhanh cuối cùng (lỗi thật đã gặp, xem ảnh chụp). Bù riêng margin-top ở
       đây -- không đụng gap chung, chỉ tách khối "Ghi chú chính" ra xa hơn đúng 1 chỗ này. */
    .st-key-note_main { margin-top: 12px; }
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

    /* ===== Container có viền (ghi chú ngày, nhật ký, ngày này năm trước) trông
       như glass-card ===== */
    .st-key-note_card, [class*="st-key-jcard"] {
        border-radius: 10px !important;
        border-color: var(--border) !important;
        box-shadow: 0 1px 1px rgba(0,0,0,0.02) !important;
        background: var(--card) !important;
    }
    /* Padding riêng theo mockup: "Ghi chú ngày" (note_card, 1 khối duy nhất, không chia hàng năm)
       rộng rãi hơn 16px 18px; các thẻ nhiều hàng kiểu "jrow" (Ngày này năm trước, Nhật ký...) chỉ
       6px 18px vì bản thân MỖI hàng đã tự có padding dọc riêng (xem .jrows .jrow), viền ngoài chỉ
       cần đệm rất mỏng. Streamlit không có padding mặc định khớp sẵn 2 giá trị này nên phải khai
       báo tay. */
    .st-key-note_card { padding: 16px 18px !important; }
    [class*="st-key-jcard"] { padding: 6px 18px !important; }

    /* ===== Trang Trợ giúp (tour cuộn dọc, namespace help-) =====
       Toàn bộ thẻ/minh hoạ của trang vẽ bằng HTML thuần qua st.markdown, chỉ dùng token màu
       (var(--...), rgba(var(--accent-rgb),...)) nên tự đúng ở cả dark mode lẫn mọi màu accent. */
    /* sec_hero() (Trợ giúp, Sức khoẻ, sub-hero Sách/Gundam...) -- ĐÃ TỪNG cố ý tô gradient phớt
       accent để phân biệt với billboard nền phẳng, nhưng xác nhận lại với người dùng (đối chiếu
       ảnh Trợ giúp thật) là mockup gốc dùng nền PHẲNG var(--card) giống mọi thẻ khác, không có
       gradient -- đổi lại khớp mockup, áp dụng cho MỌI nơi gọi sec_hero(), không riêng Trợ giúp. */
    .sec-hero {
        background: var(--card) !important;
    }
    /* Billboard Hôm nay: hiệu ứng kính mờ (frosted/liquid glass) thật -- nền phớt accent bán
       trong suốt + backdrop-filter blur/saturate làm mờ VÀ rực màu hoạ tiết chấm nền trang đứng
       sau nó (khác bản trước chỉ có rgba phẳng, chấm nền vẫn hiện SẮC NÉT xuyên qua, chưa ra được
       cảm giác "kính" thật). saturate(1.6) bù lại độ nhạt do blur, tránh nền trông xám xịt.
       filter:drop-shadow (không phải box-shadow) giữ nguyên cho bóng "tờ giấy" đổ ra ngoài khung
       kính, 2 filter (backdrop-filter + filter) hoạt động độc lập, không xung đột. -webkit- prefix
       bắt buộc cho Safari (chưa hỗ trợ backdrop-filter không tiền tố ở nhiều bản). */
    .st-key-today_billboard, .st-key-bc_billboard, .st-key-bc_billboard_detail, .st-key-tb_billboard {
        background: rgba(var(--accent-rgb),0.10) !important;
        backdrop-filter: blur(16px) saturate(1.6);
        -webkit-backdrop-filter: blur(16px) saturate(1.6);
        filter: drop-shadow(0 4px 8px rgba(33,28,19,0.16));
    }
    .sec-hero { padding: 20px 28px 16px; border-radius: 12px; border: 1px solid var(--border);
        margin-bottom: 34px; }
    .sec-hero .hh-kicker { font-size: 11px; font-weight: 700; letter-spacing: 1.5px;
        text-transform: uppercase; color: var(--accent-dark); }
    .sec-hero .hh-title { font-size: 30px; font-weight: 800; color: var(--text);
        margin: 6px 0 8px; line-height: 1.2; }
    .sec-hero .hh-sub { font-size: 15px; color: var(--text-2); max-width: 560px; line-height: 1.55; }
    .sec-hero .hh-meta { font-size: 12.5px; color: var(--text-2); margin-top: -2px; }
    /* Billboard sub-tab Báo cáo (render_period_billboard()) -- số to/nhãn cột trái + tiêu đề/mô
       tả cột phải, cỡ chữ riêng khác billboard Hôm nay (xem docstring render_period_billboard). */
    .pbill-num { font-size: 64px; font-weight: 800; line-height: 1; color: var(--accent-dark); }
    .pbill-label { font-size: 16px; font-weight: 700; color: var(--text); margin-top: 5px; }
    .pbill-title { font-size: 30px; font-weight: 800; color: var(--text); line-height: 1.2; }
    .pbill-sub { font-size: 15px; color: var(--text-2); max-width: 560px; line-height: 1.55;
        margin-top: 8px; }
    /* Billboard Sách (Tổng quan) -- cột phải khác Tuần/Báo cáo (kicker "ĐANG ĐỌC" + tên sách/tác
       giả thay vì tiêu đề/mô tả câu văn) -- font tác giả dùng chung Cormorant Garamond với trích
       dẫn Kindle billboard Hôm nay (_QUOTE_FONT_FACE) cho đồng bộ "chữ viết tay" ở mọi nơi trích
       tên riêng/tác giả trong app. */
    .pbill-kicker { font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase;
        color: var(--text-2); }
    .pbill-booktitle { font-size: 26px; font-weight: 800; color: var(--text); line-height: 1.2;
        margin-top: 4px; }
    .pbill-author { font-size: 16px; color: var(--text-2); font-weight: 600;
        font-family: 'Cormorant Garamond', Georgia, serif; font-style: italic; }
    /* Tiêu đề mỗi cuốn sách trong sub-tab "Yêu thích" (_render_kindle_favorites_tab()) -- tái
       dùng .pbill-booktitle/.pbill-author (tên sách + tác giả) kèm đường kẻ đứt ngăn cách + badge
       đếm số trích dẫn, THAY cho nhãn "Chương N" (không hợp ngữ cảnh 1 danh sách trích dẫn đã lưu,
       không phải nội dung tuần tự theo chương). */
    .fav-book-head { display: flex; align-items: baseline; justify-content: space-between;
        gap: 12px; border-bottom: 1px dashed var(--border); padding-bottom: 10px; margin-bottom: 14px; }
    .fav-book-titles { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
    .fav-count-badge { font-size: 12px; font-weight: 700; color: var(--text-2); background: var(--chip);
        border-radius: 20px; padding: 3px 10px; white-space: nowrap; }
    /* Chương "Trích dẫn & Ghi chú" (Sách -> Tổng quan, _render_reading_quotes_teaser()) -- thẻ
       card ngoài dùng chung giá trị nền/viền/bo góc/bóng với các card thanh ngang khác
       (.catbars-card), mỗi trích dẫn 1 mục có đường kẻ ngăn, ghi chú cá nhân lồng dưới thụt lề
       trái có vạch màu (giống nháp tay viết cạnh câu trích). */
    .quotes-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px;
        padding: 6px 18px; box-shadow: 0 1px 1px rgba(0,0,0,0.02); }
    .quote-item { padding: 10px 0; border-bottom: 1px solid var(--divider); }
    .quote-item:last-child { border-bottom: none; }
    .quote-text { font-size: 14.5px; line-height: 1.6; color: var(--text); }
    .quote-meta { font-size: 11.5px; color: var(--text-3); }
    .quote-note { margin-left: 20px; padding-left: 10px; border-left: 2px solid var(--chip);
        margin-top: 6px; font-size: 14.5px; color: var(--text); }
    .sec-toc { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
    .sec-toc-chip { font-size: 12.5px; font-weight: 600; color: var(--text) !important;
        text-decoration: none !important; background: var(--chip); border: 1px solid var(--border);
        border-radius: 999px; padding: 5px 12px; }
    .sec-toc-chip:hover { border-color: var(--accent); color: var(--accent-dark) !important; }
    /* scroll-margin-top: header Streamlit dạng fixed che mất tiêu đề khi nhảy anchor nếu không chừa.
       margin-top 8px khớp đúng mockup hiện hành (khoảng cách giữa các mục trang dựa chủ yếu vào
       gap flex 10px của khối cha, xem [data-testid="stVerticalBlock"] -- 8px này chỉ là phần cộng
       thêm riêng của chương, không phải toàn bộ khoảng cách nhìn thấy). */
    .sec-ch { position: relative; margin: 8px 0 0; scroll-margin-top: 80px; }
    /* Chương ĐẦU TIÊN ngay sau billboard/hero (sec_chapter(..., tight_top=True)): bỏ hẳn margin-top
       riêng của chương (chỉ còn margin-bottom của hero/billboard + gap flex của khối cha) -- có
       margin riêng nữa sẽ cộng dồn vì Streamlit không collapse margin giữa các flex item như
       block thường, tạo khoảng trắng rộng bất thường ngay dưới hero. */
    .sec-ch.sec-ch-tight { margin-top: 0; }
    /* Header chương kiểu mockup hiện hành: 1 hàng ngang canh giữa dọc, không còn số lớn mờ chồng
       góc phải (bản cũ) -- ô vuông teal chứa số nhỏ + tiêu đề + badge tuỳ chọn + kẻ ngang mở
       (flex:1, lấp hết chỗ trống còn lại) + kicker tuỳ chọn (đặt SAU kẻ ngang, không phải trước
       tiêu đề như bản cũ -- xem ví dụ "Universal Century"/"Dự án → Danh mục" trong mockup). */
    .sec-ch-row { display: flex; align-items: center; gap: 10px; }
    .sec-ch-num { flex: none; width: 26px; height: 26px; border-radius: 7px; background: var(--accent);
        color: var(--card); font-size: 13.5px; font-weight: 700; display: flex; align-items: center;
        justify-content: center; }
    .sec-ch-title { font-size: 19px; font-weight: 750; color: var(--text); }
    /* Chip nhỏ cạnh tiêu đề (vd "Lần khám 16/07/2026") -- tách thông tin ĐỘNG theo dữ liệu ra
       khỏi văn bản tiêu đề cố định, xem docstring sec_chapter() tham số badge. */
    .sec-ch-badge { flex: none; font-size: 12.5px; font-weight: 600; color: var(--text-2);
        background: var(--chip); border-radius: 999px; padding: 4px 11px; white-space: nowrap; }
    .sec-ch-rule { flex: 1; height: 1px; background: var(--divider-2); min-width: 24px; }
    .sec-ch-kicker { flex: none; font-size: 11px; font-weight: 700; letter-spacing: 1.2px;
        text-transform: uppercase; color: var(--text-3); }
    .sec-ch-lead { font-size: 14px; color: var(--text-2); margin: 8px 0 0; max-width: 660px; line-height: 1.55; }
    .sec-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px;
        box-shadow: 0 1px 1px rgba(0,0,0,0.02); padding: 16px 18px; margin: 10px 0;
        font-size: 14px; color: var(--text); line-height: 1.6; }
    .sec-card h4 { margin: 0 0 8px; font-size: 15.5px; color: var(--text); }
    .sec-card ul, .sec-card ol { margin: 6px 0 2px; padding-left: 20px; }
    .sec-card li { margin: 4px 0; }
    .sec-cap { font-size: 12px; color: var(--text-3); margin-top: 6px; line-height: 1.5; }
    .sec-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        gap: 12px; margin: 10px 0; }
    .sec-grid .sec-card { margin: 0; }
    .sec-kbd { display: inline-block; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 12px; font-weight: 600; color: var(--text); background: var(--card);
        border: 1px solid var(--border); border-bottom-width: 2.5px; border-radius: 6px;
        padding: 1px 7px; line-height: 1.5; }
    .sec-kplus { color: var(--text-3); font-size: 11px; margin: 0 3px; }
    .sec-tblwrap { overflow-x: auto; }
    .sec-tbl { width: 100%; border-collapse: collapse; font-size: 13.5px; }
    .sec-tbl th { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .5px;
        color: var(--text-2); text-align: left; padding: 6px 10px; border-bottom: 1.5px solid var(--border); }
    .sec-tbl td { padding: 8px 10px; border-bottom: 1px solid var(--divider); color: var(--text);
        vertical-align: top; line-height: 1.5; }
    .sec-tbl tr:last-child td { border-bottom: none; }
    .sec-tbl td:first-child { white-space: nowrap; }
    .help-chip { display: inline-block; font-size: 11px; font-weight: 600; color: var(--text-2);
        background: var(--chip); border-radius: 999px; padding: 2px 9px; }
    .help-chip-acc { color: var(--accent); background: rgba(var(--accent-rgb),0.12); }
    /* Sơ đồ luồng dữ liệu (chương Nạp dữ liệu & đồng bộ) */
    .sec-flow { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin: 12px 0 4px; }
    .sec-flow-node { font-size: 12.5px; font-weight: 600; color: var(--text); background: var(--chip);
        border: 1px solid var(--border); border-radius: 999px; padding: 5px 12px; }
    .sec-flow-hub { border-color: var(--accent); color: var(--accent-dark);
        background: rgba(var(--accent-rgb),0.10); }
    .sec-flow-arr::after { content: "→"; color: var(--text-3); font-size: 14px; padding: 0 2px; }
    .sec-flow-col { display: flex; flex-direction: column; gap: 6px; }
    /* Minh hoạ heatmap thu nhỏ: 8 bậc alpha theo accent, nhại thang màu Biểu đồ lịch thật */
    .sec-heat { display: grid; grid-template-columns: repeat(14, 13px); gap: 3px; margin: 12px 0 4px; }
    .sec-heat i { width: 13px; height: 13px; border-radius: 3px; background: rgba(var(--accent-rgb),0.07); }
    .sec-heat .h1 { background: rgba(var(--accent-rgb),0.18); }
    .sec-heat .h2 { background: rgba(var(--accent-rgb),0.30); }
    .sec-heat .h3 { background: rgba(var(--accent-rgb),0.42); }
    .sec-heat .h4 { background: rgba(var(--accent-rgb),0.55); }
    .sec-heat .h5 { background: rgba(var(--accent-rgb),0.68); }
    .sec-heat .h6 { background: rgba(var(--accent-rgb),0.82); }
    .sec-heat .h7 { background: rgba(var(--accent-rgb),0.95); }
    /* Minh hoạ dòng thời gian trong ngày */
    .sec-daybar { position: relative; height: 28px; border-radius: 7px; background: var(--chip);
        margin: 12px 0 4px; overflow: hidden; }
    .sec-daybar b { position: absolute; top: 4px; bottom: 4px; border-radius: 4px;
        background: rgba(var(--accent-rgb),0.55); }
    .sec-daybar b.d2 { background: rgba(var(--accent-rgb),0.85); }
    .sec-axis { display: flex; justify-content: space-between; font-size: 10px; color: var(--text-3);
        margin-top: 3px; }
    /* Minh hoạ xu hướng + đường trung bình động */
    .sec-bars { position: relative; display: flex; align-items: flex-end; gap: 5px; height: 60px;
        margin: 12px 0 4px; }
    .sec-bars i { width: 9px; border-radius: 2px 2px 0 0; background: rgba(var(--accent-rgb),0.50); }
    .sec-bars .avg { position: absolute; left: 0; right: 0; top: 38%;
        border-top: 2px dashed var(--accent); }
    /* Timeline changelog (chương Nhật ký phát triển) -- mỗi mục là 1 .sec-card thật (cùng nền/
       viền/bo góc/shadow với sec-card ở các chương khác cho đồng bộ), đường dọc + chấm tròn accent
       chạy dọc theo lề trái của toàn khối .help-tl để vẫn giữ cảm giác timeline. */
    .help-tl { margin: 8px 0; padding-left: 24px; border-left: 2px solid var(--divider); }
    .help-tl-item { position: relative; background: var(--card); border: 1px solid var(--border);
        border-radius: 10px; box-shadow: 0 1px 1px rgba(0,0,0,0.02); padding: 14px 16px 16px;
        margin: 0 0 14px; font-size: 14px; color: var(--text); line-height: 1.6; }
    .help-tl-item:last-child { margin-bottom: 0; }
    .help-tl-dot { position: absolute; left: -31px; top: 19px; width: 10px; height: 10px;
        border-radius: 50%; background: var(--accent); border: 2px solid var(--bg); }
    .help-tl-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .help-tl-pr { font-size: 11px; font-weight: 700; letter-spacing: .5px; text-transform: uppercase;
        color: var(--text-2); }
    .help-tl-title { font-size: 15px; font-weight: 700; color: var(--text); margin: 6px 0 2px; }
    .help-tl-ul { margin: 4px 0 0; padding-left: 18px; font-size: 13.5px; color: var(--text);
        line-height: 1.55; }
    .help-tl-ul li { margin: 3px 0; }
    /* FAQ (chương Câu hỏi thường gặp) -- expander native đã có style "tiêu đề gạch chân" dùng
       chung cho expander báo cáo (rule [data-testid="stExpander"] phía trên), nhưng ở đây cố ý
       ghi đè riêng trong phạm vi container key="help_faq" để mỗi câu hỏi trông như 1 sec-card thu
       gọn/mở ra được -- đồng bộ với mọi khối nội dung khác trên trang Trợ giúp, thay vì lạc tông
       kiểu "heading gạch chân" của các trang báo cáo. */
    [class*="st-key-help_faq"] [data-testid="stExpander"] { margin: 0 0 10px !important; }
    [class*="st-key-help_faq"] [data-testid="stExpander"] details {
        background: var(--card) !important; border: 1px solid var(--border) !important;
        border-radius: 10px !important; box-shadow: 0 1px 1px rgba(0,0,0,0.02) !important; }
    [class*="st-key-help_faq"] [data-testid="stExpander"] summary {
        padding: 12px 16px !important; border-bottom: none !important; }
    [class*="st-key-help_faq"] [data-testid="stExpander"] summary p {
        font-size: 14.5px !important; font-weight: 600 !important; }
    [class*="st-key-help_faq"] [data-testid="stExpander"] details[open] > summary {
        border-bottom: 1px solid var(--divider) !important; }
    [class*="st-key-help_faq"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        padding: 10px 16px 14px !important; font-size: 14px !important; line-height: 1.6 !important; }
    @media (max-width: 640px) {
        .sec-hero { padding: 22px 18px; }
        .sec-hero .hh-title { font-size: 26px; }
        .sec-ch-num { font-size: 40px; }
        .sec-flow { flex-direction: column; align-items: flex-start; }
        .sec-flow-arr::after { content: "↓"; padding: 0; }
        .sec-heat { grid-template-columns: repeat(10, 13px); }
    }

    /* ===== Nhật ký & Ngày này năm trước: thẻ có kẻ dọc trái/phải =====
       Dựng bằng HTML tự thân (1 khối st.markdown duy nhất mỗi thẻ) thay vì st.columns()
       lặp lại -> tránh hoàn toàn cơ chế flex/chiều cao tự tính của Streamlit (từng làm
       khoảng cách quanh đường kẻ lệch nhau dù CSS đặt padding bằng nhau, do JS tính sẵn
       chiều cao hàng theo layout ban đầu, không cập nhật lại khi nội dung dài tràn khung). */
    .jrows .jrow { display: grid; grid-template-columns: 1fr 5fr; align-items: start;
        column-gap: 10px; padding: 11px 0; border-bottom: 1px solid var(--divider); }
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
    /* Bảng Phân loại TĨNH (Tuỳ biến -> chương "2. Phân loại") -- badge màu Danh mục không thể vẽ
       trong 1 ô data_editor (SelectboxColumn chỉ nhận text đơn thuần, không chèn được HTML màu),
       nên hiển thị dạng bảng tĩnh khớp mockup; sửa phân loại chuyển sang 1 form riêng bên dưới
       (chọn Dự án + Danh mục + nút Lưu) thay vì sửa ngay trong ô bảng. */
    /* Mọi hàng (kể cả dòng "+N dự án khác" cuối bảng) đều là div.maprow trực tiếp trong .maptbl
       -- :last-child (không phải :last-of-type, vốn so theo TAG chứ không theo class, sẽ khớp
       nhầm nếu dòng cuối mang thêm class phụ) mới chắc chắn khớp đúng div cuối cùng để bỏ viền. */
    .maptbl { display: flex; flex-direction: column; }
    .maprow { display: grid; grid-template-columns: 2fr 2fr 1fr; column-gap: 10px; align-items: center;
        padding: 9px 0; border-bottom: 1px solid var(--divider); font-size: 13.5px; color: var(--text); }
    .maptbl .maprow:last-child { border-bottom: none; }
    .maprow-head { font-size: 11px; font-weight: 700; color: var(--text-2); text-transform: uppercase;
        letter-spacing: 0.4px; }
    .maprow .mp-proj { font-weight: 600; }
    .maprow .mp-n { text-align: right; font-variant-numeric: tabular-nums; }
    .maprow.maprow-extra { grid-template-columns: 1fr; font-size: 12.5px; color: var(--text-2); }
    /* Thẻ st.container(border=True) ở Tuỳ biến (5 chương) mặc định nền TRONG SUỐT (chỉ có viền,
       không có fill) -- khác mọi thẻ .glass-card/.dtl-card khác trong app luôn nền phẳng
       var(--card), nên hoạ tiết chấm bi của .stApp lộ xuyên qua, trông "rỗng"/không giống thẻ
       thật. Ép nền đặc var(--card) cho khớp phần còn lại của app. */
    .st-key-tb_quick_sync_card, .st-key-tb_mapping_card, .st-key-tb_theme_card,
    .st-key-tb_backup_card, .st-key-tb_restore_card, .st-key-tb_wipe_card, .st-key-tb_rawdata_card,
    .st-key-tb_account_card {
        background: var(--card) !important;
    }
    .jdate .jyear { font-size: 20px; font-weight: 700; color: var(--accent); letter-spacing: -0.5px; line-height: 1; }
    .jdate .jdow { font-size: 15px; font-weight: 700; color: var(--text); margin-top: 6px; }
    .jdate .jdowbig { font-size: 18px; font-weight: 700; color: var(--text); letter-spacing: -0.3px; }
    .jdate .jdm { font-size: 13px; color: var(--text-2); font-weight: 500; margin-top: 2px; }
    .jchip { display: inline-block; background: var(--chip); border-radius: 10px; padding: 5px 11px;
        font-size: 12.5px; margin: 0 6px 6px 0; }
    .jchip .ck { color: var(--text-2); } .jchip .cv { font-weight: 600; color: var(--text); margin-left: 5px; }
    /* Từ khớp trong trang Tìm kiếm (xem _highlight()) -- tô theo accent thay vì vàng mặc định
       của trình duyệt, khớp tông "Sổ Tay" thay vì lệch hẳn ra ngoài hệ màu app. */
    mark { background: rgba(var(--accent-rgb),0.18); color: var(--accent-dark); border-radius: 3px;
        padding: 0 2px; }
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
       đúng pattern nhãn nhỏ kiểu eyebrow (in hoa, 11px) đã dùng cho box "Lịch Work" cũ. */
    .rl-book { display: block; font-size: 11px; font-weight: 700; color: var(--text-2);
        text-transform: uppercase; letter-spacing: .5px; margin: 0 0 4px 2px; }
    /* Trích dẫn/ghi chú Kindle trong "2. Nhật ký đọc" (Sách/Gundam -> Chi tiết, xem
       _render_kindle_quote_row()): đoạn văn thường (không box/card riêng từng quote, CHỦ Ý theo
       yêu cầu người dùng -- trình bày như "Ghi chú chính" trong Ghi chú ngày) + 1 dấu " màu
       accent đầu highlight / icon ✎ đầu ghi chú để phân biệt nhanh 2 loại không cần đọc chữ. */
    .kq-mark { color: var(--accent); font-weight: 700; margin-right: 2px; }
    .kq-loc { font-size: 11.5px; color: var(--text-3); }
    /* Mỗi quote/note là 1 hàng thật (st.columns, key="kqrow_<hash>"/"kqreply_<hash>") để có nút
       Sửa/Xoá/+ Ghi chú -- cùng phong cách icon nhỏ/nền trong suốt với hàng Ghi chú nhanh
       (qnote_row) phía trên, xem chú thích ở đó để biết vì sao cần ép min-width/flex-wrap. */
    [class*="st-key-kqrow_"], [class*="st-key-kqreply_"] { margin-bottom: 2px; }
    [class*="st-key-kqrow_"] [data-testid="stHorizontalBlock"],
    [class*="st-key-kqreply_"] [data-testid="stHorizontalBlock"],
    [class*="st-key-kqnew_"] [data-testid="stHorizontalBlock"] {
        align-items: flex-start; flex-wrap: nowrap !important;
    }
    [class*="st-key-kqrow_"] [data-testid="stColumn"],
    [class*="st-key-kqreply_"] [data-testid="stColumn"],
    [class*="st-key-kqnew_"] [data-testid="stColumn"] { min-width: 0 !important; }
    [class*="st-key-kqrow_"] [data-testid="stColumn"]:last-child,
    [class*="st-key-kqreply_"] [data-testid="stColumn"]:last-child,
    [class*="st-key-kqnew_"] [data-testid="stColumn"]:last-child {
        flex: 0 0 auto !important; width: auto !important;
    }
    [class*="st-key-kqrow_"] div[data-testid="stButton"] button[kind="secondary"],
    [class*="st-key-kqreply_"] div[data-testid="stButton"] button[kind="secondary"],
    [class*="st-key-kqnew_"] div[data-testid="stButton"] button[kind="secondary"] {
        background: transparent !important; border: none !important; box-shadow: none !important;
        color: var(--text-3) !important; width: auto !important; min-height: 0 !important;
        height: 26px !important; padding: 0 4px !important;
    }
    [class*="st-key-kqrow_"] div[data-testid="stButton"] button[kind="secondary"]:hover,
    [class*="st-key-kqreply_"] div[data-testid="stButton"] button[kind="secondary"]:hover,
    [class*="st-key-kqnew_"] div[data-testid="stButton"] button[kind="secondary"]:hover { color: var(--text) !important; }
    /* Icon ⭐ Yêu thích dùng chung font Material Symbols của Streamlit KHÔNG hỗ trợ trục biến FILL
       (đã kiểm chứng qua Playwright: ép font-variation-settings 'FILL' 1 không đổi hình dạng icon) --
       ":material/star:" và ":material/star_outline:" hiển thị giống hệt nhau (đều nét viền rỗng),
       nên phân biệt trạng thái đã đánh dấu bằng MÀU accent thay vì hình dạng. Key nút đã gắn hậu tố
       "_on_"/"_off_" ngay sau "kq_favbtn_"/"kq_daily_favbtn_" đúng theo trạng thái để chọn được. */
    [class*="st-key-kq_favbtn_on_"] div[data-testid="stButton"] button[kind="secondary"] {
        color: var(--accent) !important;
    }
    /* Ghi chú lồng dưới highlight (is_reply=True) -- thụt lề + vạch trái mảnh, phân biệt rõ với
       hàng highlight cha phía trên. */
    [class*="st-key-kqreply_"] { margin-left: 20px; padding-left: 10px; border-left: 2px solid var(--chip); }
    /* Sub-tab "Yêu thích" (trang Sách, xem _render_kindle_favorites_tab()): mỗi trích dẫn bọc
       trong 1 thẻ nền riêng -- giống .dtl-card (thẻ dòng thời gian ở Báo cáo Ngày/Tuần/Tháng) --
       thay vì chỉ là hàng chữ trần như ở "2. Nhật ký đọc". Chỉ khớp key_suffix="fav_" (khớp
       "kqrow_fav_", KHÔNG khớp "kqrow_" trơn của "2. Nhật ký đọc") nên không ảnh hưởng nơi khác.
       Đặt SAU rule margin-bottom:2px chung ở trên để thắng theo thứ tự (cùng độ đặc hiệu). */
    [class*="st-key-kqrow_fav_"] {
        background: var(--card); border: 1px solid var(--border); border-radius: 10px;
        box-shadow: 0 1px 1px rgba(0,0,0,0.02); padding: 16px 18px; margin-bottom: 10px !important;
    }
    [class*="st-key-kqrow_fav_"]:last-child { margin-bottom: 0 !important; }
    /* Trích dẫn nhiều dòng (thường gặp -- trích dẫn dài hơn 1 dòng ở bề rộng cột chữ ~83%): cột
       chữ (rc1) là 1 flex item lồng nhiều lớp bên trong hàng cột (rc1/rc2 icon) -- đã xác minh qua
       DevTools rằng khi chữ tự xuống dòng, Chromium tính sai chiều cao "auto" của các lớp bọc
       trung gian (kẹt ở chiều cao ứng với 1 dòng dù chữ đã xuống 2+ dòng thật), khiến dòng cuối ăn
       lẹm gần hết phần đệm dưới lẽ ra phải có (đo qua DevTools: từ ~16px dự kiến tụt còn ~1px thật
       tế). Không sửa được triệt để bằng cách ép display/height lên các lớp bọc đó (đã thử nhiều
       cách, kể cả tách cụm nút ra khỏi flex row bằng position:absolute -- đều làm vỡ vị trí cụm
       nút bên phải) -- tăng riêng padding-bottom (16px -> 30px, bù thêm gần 1 dòng chữ) là cách an
       toàn nhất, không đụng cấu trúc layout đang hoạt động ổn định ở mọi nơi khác. Không tuyệt đối
       hoàn hảo cho trích dẫn dài 3+ dòng, nhưng đã kiểm tra: cải thiện rõ rệt cho ca 1-2 dòng phổ
       biến, không làm ca 1 dòng (không có bug) trông mất cân đối rõ rệt. */
    [class*="st-key-kqrow_fav_"] { padding-bottom: 30px; }
    /* Mỗi ngày trong "2. Nhật ký đọc" (Sách/Gundam -> Chi tiết) là 1 st.container(key="jkq_row_N")
       THẬT (không phải .jrows/.jrow HTML tĩnh -- xem _render_reading_kindle_days()), nên không tự
       có padding/đường kẻ phân tách như .jrows .jrow ở nơi khác -- chỉ dựa vào gap mặc định giữa
       các khối xếp dọc, quá sát khi Thứ/ngày xếp chồng ngay trên nhau qua nhiều ngày liền. Thêm
       padding dọc + đường kẻ dưới cùng KHUÔN với .jrows .jrow để 2 nơi trông nhất quán. */
    /* Lần sửa trước tăng padding-TOP (10->18px), nhưng phản hồi thực tế xác nhận đây SAI phía:
       đường kẻ đáy của CHÍNH hàng đó vẫn sát ngay dưới ngày/chip của hàng đó (padding-bottom
       chưa đổi, vẫn 10px) -- không phải khoảng cách TỚI hàng kế tiếp như đoán ban đầu. Tăng đều
       cả 2 phía lên 16px thay vì đoán riêng 1 phía, để chắc chắn phần đệm NGAY TRÊN đường kẻ
       (giữa nội dung hàng và đường kẻ đáy của chính hàng đó) cũng nới ra rõ rệt. */
    [class*="st-key-jkq_row_"] { padding: 16px 0; border-bottom: 1px solid var(--divider); }
    /* :last-child đặt ngay trên chính div key KHÔNG có tác dụng -- Streamlit bọc mỗi container
       trong 1 lớp [data-testid="stLayoutWrapper"] riêng, nên div key luôn là con DUY NHẤT (và do
       đó luôn là last-child) của chính wrapper của nó, khiến rule khớp với MỌI hàng chứ không chỉ
       hàng cuối (bug thật đã gặp, phát hiện qua getComputedStyle(): border-bottom trả về "0px
       none" ở tất cả các hàng, kể cả hàng đầu). Phải nhắm :last-child vào wrapper (con của khối
       cha xếp dọc chung, nơi các wrapper mới thực sự là anh em) rồi mới chọn xuống div key bên
       trong. */
    [data-testid="stLayoutWrapper"]:last-child > [class*="st-key-jkq_row_"] { border-bottom: none; }
    /* "Trích dẫn hôm nay" -- xem _render_daily_quote_card()/_kindle_quote_of_day(). Nền phớt màu
       accent (khác var(--card) trung tính của mọi thẻ khác trên trang) để mắt dừng lại ngay, đúng
       mục tiêu không bị lướt qua như bản cũ (từng chôn ở cuối trang, cùng màu mọi thẻ số liệu
       khác). Nền dùng color-mix() (KHÔNG phải rgba(...,0.07) như bản trước) -- rgba trong suốt để
       lộ hoạ tiết chấm nền (.stApp) xuyên qua thẻ, phản hồi thực tế là "nhìn không giống thẻ thật".
       color-mix() trộn ra 1 màu ĐẶC, vẫn tự đổi đúng theo theme sáng/tối vì var(--card) đổi theo
       IS_DARK. st.container(border=True, key="kq_daily_card") tự có viền/bo góc/bóng qua rule
       [data-testid="stVerticalBlockBorderWrapper"] chung của Streamlit -- ghi đè nền/viền/padding/
       margin ở đây, không cần định nghĩa lại toàn bộ khung. margin ngang 16px (thay vì full-width)
       để khớp đúng bề rộng card số liệu bên dưới (xem docstring _render_daily_quote_card()). */
    /* Nền phẳng var(--card) + đổ bóng filter:drop-shadow (xem rule màu/bóng riêng phía trên) --
       khung/padding/bo góc/margin khai báo tiếp ở đây, tách khỏi rule màu để không lặp lại toàn
       bộ khối mỗi lần chỉnh 1 trong 2 nhóm thuộc tính. */
    .st-key-today_billboard, .st-key-bc_billboard, .st-key-bc_billboard_detail, .st-key-tb_billboard {
        border-color: var(--border) !important;
        padding: 20px 28px 16px !important;
        border-radius: 12px !important;
        margin: 0 0 6px !important;
    }
    /* Cột trong HÀNG NGOÀI CÙNG (ngày/trích dẫn, container key="tbill_daterow") mặc định STRETCH
       hết chiều cao hàng (flex align-items: stretch của Streamlit) -- ép align-self: center để
       mỗi cột co lại đúng chiều cao nội dung riêng rồi canh giữa so với cột kia (giống grid
       align-items:center của mockup). Scope CHỈ ĐÚNG "tbill_daterow" (không phải mọi
       stHorizontalBlock trong billboard nói chung) -- billboard còn 1 hàng ngang LỒNG BÊN TRONG
       nữa (kq_daily_srcrow, hàng tên sách + nút xáo/yêu thích). Chuỗi chọn phải đi qua
       [data-testid="stLayoutWrapper"] -- Streamlit chèn thêm 1 lớp div trung gian giữa container
       key và stHorizontalBlock, thiếu bước này chuỗi ">" đứt gãy và cả rule (align-self, padding
       cột phải) LẶNG LẼ không áp dụng (không lỗi console, chỉ đơn giản không match) -- bug thật đã
       gặp, phát hiện qua getComputedStyle() DOM. Đã thử thêm nền/viền/bóng đóng khung cột trái như
       1 tờ giấy riêng -- xem lại thấy phẳng như bản gốc đẹp hơn nên bỏ, chỉ giữ canh giữa. */
    [class*="st-key-tbill_daterow"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
    [class*="st-key-bc_billboard_row"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
    [class*="st-key-bc_billboard_detail_row"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
    [class*="st-key-tb_billboard_row"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        align-self: center !important;
    }
    /* Cột phải (tiêu đề/mô tả) billboard Báo cáo -- đệm trái 24px khớp mockup (grid-template-
       columns:1fr 2fr;padding-left:24px), billboard Hôm nay không cần vì cột phải là trích dẫn
       đã tự có mark "" làm khoảng đệm thị giác riêng. */
    [class*="st-key-bc_billboard_row"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child,
    [class*="st-key-bc_billboard_detail_row"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child,
    [class*="st-key-tb_billboard_row"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {
        padding-left: 24px !important;
    }
    /* Cột ngày (số to + Thứ/ngày/tháng chữ + meta) -- canh giữa CẢ ngang lẫn dọc trong cột, đúng
       cảm giác 1 tờ lịch bàn xé hằng ngày. vertical_alignment="center" của st.columns cha đã canh
       khối này theo tâm so với cột trích dẫn cao hơn bên cạnh; text-align lo phần ngang. */
    .tbill-date { text-align: center; padding: 16px 16px 14px; }
    /* "Tab lịch xé" -- thanh accent bo góc trên + 2 chấm tròn màu nền trang (giả lỗ đục lịch bàn)
       nằm NGAY TRÊN số ngày to, hiện tháng/năm dạng nhãn nhỏ in hoa (mockup billboard Hôm nay). */
    .tbill-tab { position: relative; background: var(--accent); border-radius: 8px 8px 0 0;
        padding: 8px 0 7px; margin-bottom: 8px; }
    .tbill-tab::before, .tbill-tab::after { content: ''; position: absolute; top: 6px;
        width: 9px; height: 9px; border-radius: 50%; background: var(--bg);
        box-shadow: inset 0 1px 2px rgba(0,0,0,0.35); }
    .tbill-tab::before { left: 22px; }
    .tbill-tab::after { right: 22px; }
    .tbill-tab-label { font-size: 11px; font-weight: 700; letter-spacing: 2px;
        text-transform: uppercase; color: var(--card); }
    .tbill-num { font-size: 76px; font-weight: 800; line-height: 1; color: var(--accent-dark); }
    .tbill-dow { font-size: 16px; font-weight: 700; color: var(--text); margin-top: 5px; }
    .tbill-meta { font-size: 12.5px; color: var(--text-2); margin-top: 10px; line-height: 1.7; }
    /* Nút ⭐ đặt cạnh tên sách (hàng cuối, xem docstring _render_today_billboard()) -- nền chip
       phớt accent LUÔN CÓ (kể cả chưa Yêu thích) để nút có 1 "điểm neo" hình khối rõ ràng, không
       còn là icon trôi nổi giữa nền thẻ như bản đặt ở góc trên phải trước đó. Label nút là ký tự
       "★"/"☆" thật (xem docstring -- không phải icon Material nữa) nên CSS nhắm vào <p> chứa chữ
       (div[data-testid="stMarkdownContainer"] p bên trong button), KHÔNG phải
       span[data-testid="stIconMaterial"] như trước. */
    .st-key-today_billboard div[data-testid="stButton"] button[kind="secondary"] {
        background: rgba(var(--accent-rgb),0.12) !important; border: none !important; box-shadow: none !important;
        width: 30px !important; height: 30px !important;
        min-height: 0 !important; border-radius: 999px !important; padding: 0 !important;
    }
    .st-key-today_billboard div[data-testid="stButton"] button[kind="secondary"] p {
        font-size: 18px !important; line-height: 1 !important; color: var(--text-3) !important;
    }
    /* Nút xáo (icon Material "shuffle", KHÁC nút Yêu thích ở trên -- vẫn dùng icon font vì không
       có ký tự đơn thay thế hợp lý như "★"/"☆") -- màu nhạt var(--text-3) khớp mockup, cỡ 16px. */
    .st-key-today_billboard div[data-testid="stButton"] button[kind="secondary"] span[data-testid="stIconMaterial"] {
        font-size: 16px !important; color: var(--text-3) !important;
    }
    /* Đã Yêu thích -> chữ "★" màu accent (hình dạng đặc/rỗng đã đủ phân biệt, màu chỉ để nhấn
       thêm) -- xem chú thích [class*="st-key-kq_favbtn_on_"] phía trên cho lý do đổi hẳn sang ký
       tự chữ thay vì icon font. */
    [class*="st-key-kq_daily_favbtn_on"] div[data-testid="stButton"] button[kind="secondary"] p {
        color: var(--accent) !important;
    }
    /* Hàng "tên sách + nút ⭐" (st.container key="kq_daily_srcrow") -- canh 2 cột theo baseline
       chung để chữ và nút trông "cùng 1 hàng" thay vì nút trôi lên/xuống lệch dòng chữ. margin-top
       dương nhẹ (KHÔNG âm như bản trước) -- bản âm (-6px) làm nút ⭐ chạm/đè lên dòng cuối chữ
       trích dẫn khi trích dẫn dài đủ 2-3 dòng, phản hồi thực tế là "trông không đẹp". */
    [class*="st-key-kq_daily_srcrow"] { margin-top: 10px; }
    [class*="st-key-kq_daily_srcrow"] [data-testid="stHorizontalBlock"] { align-items: center !important; gap: 10px !important; }
    /* 2 cột nút (xáo/yêu thích) mặc định rộng theo tỉ lệ st.columns([9,1,1]) -- mỗi cột ~60-70px
       trong khi nút chỉ 30px, khiến 2 nút trông cách nhau rất xa (đo thật ~34px, mockup chỉ 10px).
       Ép cột nút co đúng 30px (khớp width nút), cột tên sách giãn nốt phần còn lại -- gap 10px của
       hàng ngang (rule trên) trở thành khoảng cách DUY NHẤT giữa 2 nút, khớp mockup. */
    [class*="st-key-kq_daily_srcrow"] [data-testid="stColumn"]:first-child {
        flex: 1 1 auto !important; width: auto !important;
    }
    [class*="st-key-kq_daily_srcrow"] [data-testid="stColumn"]:not(:first-child) {
        flex: 0 0 30px !important; width: 30px !important; min-width: 30px !important;
    }
    /* Font Cormorant Garamond (xem _QUOTE_FONT_FACE) -- chọn qua mockup ảnh gửi duyệt, cỡ chữ
       chỉnh LỚN HƠN bản Manrope cũ (mark 52->58px, text 21->23px, src 16.5->17.5px) vì đây là
       kiểu chữ mảnh/cao ("mảnh, cao, trang trọng"), cùng cỡ px trông NHỎ HƠN Manrope (sans-serif
       đậm/vuông vức) nếu giữ nguyên số cũ. */
    .kq-daily-mark { font-size: 58px; line-height: 1; color: var(--accent);
        font-family: 'Cormorant Garamond', Georgia, serif; font-weight: 600; font-style: italic;
        opacity: .5; margin-bottom: -14px; }
    .kq-daily-text { font-size: 23px; line-height: 1.45; font-weight: 600; color: var(--text);
        font-family: 'Cormorant Garamond', Georgia, serif; font-style: italic; white-space: pre-wrap; }
    .kq-daily-src { margin: 0; font-size: 17.5px; color: var(--text); font-weight: 700;
        font-family: 'Cormorant Garamond', Georgia, serif; text-align: right; }
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
    /* Ghi chú nhanh: badge giờ nhỏ (.qn-time) + chữ ghi chú thường NGOÀI badge (.qn-text, cùng
       cỡ/màu .note-html) -- khác .jchip (cả giờ lẫn chữ đều tô nền), vì quick note nay là 1 câu
       đọc như ghi chú thật, không phải 1 nhãn nhỏ. .qn-line dùng ở bản CHỈ ĐỌC (Nhật ký
       Tuần/Tháng, Ngày này năm trước) -- bản có nút sửa/xoá ở Ghi chú ngày dựng bằng
       st.columns() thật nên không cần .qn-line (đã có [class*="st-key-qnote_row_"] lo margin). */
    .qn-time { display: inline-block; font-size: 12px; font-weight: 600; color: var(--text-2);
        background: var(--chip); border-radius: 7px; padding: 4px 9px; font-variant-numeric: tabular-nums;
        margin-right: 10px; vertical-align: middle; white-space: nowrap; }
    .qn-text { font-size: 14.5px; color: var(--text); line-height: 1.5; }
    /* .qn-merged: ghi chú nhanh đã bấm "Gộp", đang chờ Cập nhật ghi chú chính mới thực sự xoá --
       gạch ngang + nhạt màu để phân biệt với các dòng chưa xử lý, không cần xoá khỏi UI ngay. */
    .qn-merged { text-decoration: line-through; color: var(--text-3); }
    .qn-line { padding: 4px 0; }
    .qn-line + .qn-line { border-top: 1px solid var(--divider); }
    /* Ghi chú nhanh (Ghi chú ngày, có sửa/xoá): mỗi quick note 1 hàng st.columns() thật (badge
       giờ + text/ô sửa + cụm 2 nút) -- cụm nút dùng st.container(horizontal=True) (không phải
       st.columns() lồng bên trong nữa, tránh lặp lại đúng bug đã gặp: st.columns() lồng sâu bị
       CSS "cột ngoài cùng" ở trên khớp nhầm). [class*=...] khớp mọi container qnote_row_<id>
       cùng lúc (id đổi theo từng note). Ghi đè lại rule chung button[kind="secondary"] (nền/viền)
       giống cách làm ở nút chọn màu accent (Tuỳ biến) -- cần đủ đặc hiệu (kèm !important) mới
       thắng được rule đó. */
    [class*="st-key-qnote_row_"] { margin-bottom: 0 !important; }
    /* Khoảng cách dọc thật giữa các dòng ghi chú nhanh không tới từ margin-bottom trên (chỉ 2px)
       mà chủ yếu từ gap flex mặc định (0.9rem = 14.4px) giữa các item của khối cha (mỗi dòng là 1
       flex item riêng, margin không cộng dồn/thu hẹp được gap đó) -- tổng ~16px, người dùng thấy
       quá rộng so với 1 danh sách ghi chú ngắn. Ép thẳng gap của khối cha (nhận diện qua :has()
       tìm đúng khối chứa các dòng qnote_row_) xuống 5px (phương án B trong 5 mock up đã chọn),
       gọn hẳn so với cỡ mặc định của Streamlit. */
    [data-testid="stVerticalBlock"]:has(> [data-testid="stLayoutWrapper"] > [class*="st-key-qnote_row_"]) {
        gap: 5px !important;
    }
    [class*="st-key-qnote_row_"] [data-testid="stHorizontalBlock"] { align-items: center; }
    /* 3 cột (giờ / nội dung / nút) LUÔN giữ 1 hàng ngang, kể cả màn hẹp -- Streamlit tự đặt
       min-width: calc(100% - 24px) cho MỌI cột dưới 1 ngưỡng rộng màn hình (ép mỗi cột chiếm
       trọn hàng riêng, dùng cho layout cố ý xếp dọc trên mobile), nhưng hàng ghi chú nhanh này
       cố ý muốn giữ ngang ở mọi kích thước màn hình -- không có 3 rule dưới đây, xem trên điện
       thoại dọc sẽ vỡ thành 3 dòng (giờ/chữ/nút mỗi thứ 1 dòng); xem ngang thì cột giờ quá hẹp
       (theo % cố định) khiến "02:53" bị bẻ dòng giữa số dù đã có white-space:nowrap ở .qn-time
       (bẻ dòng vì chính CỘT chứa nó quá hẹp, không phải vì chữ tự xuống dòng).
       Cột 1 (giờ) và cột 3 (nút) đặt CHIỀU RỘNG CỐ ĐỊNH (đủ cho "23:59" và 2 icon) thay vì
       "flex-basis: auto" co theo nội dung -- đã thử co theo nội dung nhưng Streamlit tự đo và
       gán width bằng px (inline style, qua ResizeObserver) cho các div bọc bên TRONG mỗi cột
       (stVerticalBlock/stElementContainer...) lúc mount theo tỉ lệ % CŨ rồi giữ nguyên, khiến
       phép tính "auto" của trình duyệt vẫn chốt theo con số cũ rất hẹp (~14px) dù đã xoá mọi
       ràng buộc auto khác -- ép width cứng (không phải auto) ở mọi tầng mới thắng được số đo cũ
       đó. Không có các rule này, cột co nhỏ hơn hẳn nội dung (badge giờ/cụm nút) trong khi chữ
       vẫn hiện to hơn khung chứa (overflow:visible) -> nhìn như đè chồng lên cột giữa. */
    [class*="st-key-qnote_row_"] [data-testid="stColumn"] { min-width: 0 !important; }
    [class*="st-key-qnote_row_"] [data-testid="stColumn"]:first-child { flex: 0 0 52px !important; }
    /* 108px (không phải 64px cũ) -- đủ chỗ cho CẢ 3 nút (Gộp/Sửa/Xoá) cùng 1 hàng ở chế độ xem;
       64px chỉ đủ ~2 nút nên nút thứ 3 bị đẩy xuống dòng, đội chiều cao mỗi hàng ghi chú nhanh
       lên trông như cách nhau xa dù margin-bottom (dòng dưới) đã rất sát. */
    [class*="st-key-qnote_row_"] [data-testid="stColumn"]:last-child { flex: 0 0 108px !important; }
    [class*="st-key-qnote_row_"] [data-testid="stColumn"]:first-child *,
    [class*="st-key-qnote_row_"] [data-testid="stColumn"]:last-child * {
        width: 100% !important; min-width: 0 !important;
    }
    /* Badge giờ (.qn-time) là inline-block nên mặc định bám lề TRÁI trong khối 52px cha (đã ép
       width:100% ở trên) -- text-align:center để chữ số nằm giữa khung, không lệch trái. */
    [class*="st-key-qnote_row_"] [data-testid="stColumn"]:first-child p { text-align: center; }
    [class*="st-key-qnote_row_"] [data-testid="stColumn"]:nth-child(2) { flex: 1 1 0 !important; }
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
       vì min-height thắng; phải tự đè min-height ở đây thì nút mới thực sự thấp lại. Cùng 1 rule
       áp luôn cho "st-key-tbtn_*" -- tiền tố dùng chung cho MỌI nút thao tác đơn lẻ trong tab Tuỳ
       biến (Đồng bộ ngay, Xác nhận cập nhật/nạp dữ liệu, Lưu phân loại, Xoá phiên đã chọn, Tải
       bản sao lưu, Xác nhận Khôi phục, Xoá toàn bộ dữ liệu, Đăng xuất) để đồng bộ 1 kiểu nút nhỏ
       gọn xuyên suốt app -- KHÔNG áp cho nút chọn màu accent (tự có style ô màu vuông riêng, xem
       _swatch_css) hay nút bước ngày/kỳ (mũi tên trái/phải, vốn đã là 1 thanh điều khiển đều
       nhau, không phải nút hành động đơn lẻ). "Tải bản sao lưu" là st.download_button() -- DOM
       khác st.button() (div data-testid="stDownloadButton", không phải "stButton"), phải khớp
       thêm selector riêng, không thì lọt lưới rule chỉ nhắm "stButton". */
    [class*="st-key-note_editbtn_"] div[data-testid="stButton"] button,
    [class*="st-key-note_addbtn_"] div[data-testid="stButton"] button,
    .st-key-note_actions div[data-testid="stButton"] button,
    [class*="st-key-tbtn_"] div[data-testid="stButton"] button,
    [class*="st-key-tbtn_"] div[data-testid="stDownloadButton"] button {
        width: auto !important; padding: 5px 14px !important; font-size: 13px !important;
        min-height: 0 !important; height: auto !important;
    }
    /* note_label_content (nhãn "Ghi chú chính" + nội dung/Quill, gap="xsmall") tách riêng khỏi
       note_main (gap="small" mặc định) để 2 khoảng cách dọc không bị ép về cùng 1 giá trị: nhãn↔
       nội dung cần sát (xsmall), nhưng nội dung↔hàng nút bên dưới cần rộng hơn 1 chút để không
       dính liền -- gộp chung 1 container/1 gap từng làm cả 2 khoảng cách xích lại y hệt, "sửa
       xong" hoá ra ép nhầm khoảng còn lại quá chật (bug vòng trước). */

    /* Nút tròn nổi "về đầu trang" (tạo bằng JS ở _inject_scroll_to_top_button(), không phải
       st.button -- xem docstring hàm đó). Ẩn mặc định (opacity 0 + pointer-events none), JS gắn
       class "show" khi cuộn quá ngưỡng; z-index thấp hơn overlay bảng phím tắt (99999) để không
       che nhau nếu cùng hiện 1 lúc. */
    #app-scroll-top-btn {
        position: fixed; right: 22px; bottom: 22px; z-index: 99980;
        width: 44px; height: 44px; border-radius: 50%;
        background: var(--accent); color: #fff; border: none;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 4px 14px rgba(var(--accent-rgb),0.38);
        cursor: pointer; opacity: 0; transform: translateY(12px) scale(0.9);
        pointer-events: none; transition: opacity 0.2s ease, transform 0.2s ease;
    }
    #app-scroll-top-btn.show { opacity: 1; transform: translateY(0) scale(1); pointer-events: auto; }
    #app-scroll-top-btn:hover { opacity: 0.9; transform: scale(1.05); }
    #app-scroll-top-btn svg { width: 20px; height: 20px; }
    @media (max-width: 640px) {
        #app-scroll-top-btn { right: 14px; bottom: 14px; width: 40px; height: 40px; }
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    f"<div style='margin:0 0 1.8em 0;'>{_wordmark_html('header')}</div>",
    unsafe_allow_html=True,
)

# Thanh điều hướng 1 hàng phẳng (kiểu iOS segmented control), icon Material cho từng trang.
# Key = định danh trang (dùng cho dispatch & deep-link ?nav=); nhãn hiển thị rút gọn ở NAV_SHORT.
NAV = {
    "Hôm nay": ":material/wb_sunny:",
    "Báo cáo": ":material/bar_chart:",
    "Nhật ký đọc sách": ":material/menu_book:",
    "Gundam": ":material/shield:",
    "Sức khoẻ": ":material/monitor_heart:",
    "Tìm kiếm": ":material/search:",
    "Tuỳ biến": ":material/tune:",
    "Hướng dẫn": ":material/help:",
}
# Nhãn ngắn để các tab vừa 1 hàng (key trang giữ nguyên).
NAV_SHORT = {
    "Hôm nay": "Hôm nay",
    "Báo cáo": "Báo cáo",
    "Nhật ký đọc sách": "Sách",
    "Gundam": "Gundam",
    "Sức khoẻ": "Sức khoẻ",
    "Tìm kiếm": "Tìm kiếm",
    "Tuỳ biến": "Tuỳ biến",
    "Hướng dẫn": "Trợ giúp",
}

df = prep_analysis_data()
DAYS_ORDER = list(VN_DAYS.values())  # đúng thứ tự Thứ Hai..Chủ Nhật vì VN_DAYS khai báo sẵn theo thứ tự này -- giữ 1 nguồn duy nhất thay vì lặp lại chuỗi chữ ở đây, tránh lệch nếu VN_DAYS đổi cách viết sau này

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
    - n: mở nhanh ô soạn Ghi chú ngày của HÔM NAY, tự cuộn trang tới đúng ô soạn (Quill) sau khi
      mở -- ô này thường không nằm ở đầu trang nên cần cuộn hộ, tránh cảm giác "bấm xong không
      thấy gì" khi vẫn đứng ở đầu trang. Cuộn xong tự focus luôn vào ô soạn (Quill nằm trong
      iframe riêng, phải đọc contentDocument của đúng iframe đó rồi .focus() thẳng vào
      .ql-editor) để gõ được ngay phím tiếp theo, không cần bấm chuột vào ô trước.
    - /: focus vào ô Tìm kiếm (đứng sẵn ở đó thì focus luôn, đứng trang khác thì nhảy tới trước).
      Esc trong khi đang focus ô này: bỏ con trỏ ra khỏi ô (blur), KHÔNG đổi/xoá từ khoá đang gõ
      -- đây là ngoại lệ duy nhất được xử lý TRƯỚC bộ lọc input/textarea bên dưới, vì mọi phím
      tắt khác cố tình bị bỏ qua khi đang gõ trong ô nhập liệu.
    - ?: hiện/ẩn bảng tóm tắt các phím tắt này.

    Theo ngữ cảnh (chỉ có tác dụng khi đang ở đúng trang, không nhảy trang):
    - ← / →: trang Hôm nay -- lùi/tiến ngày (bấm hộ nút ◀ ▶ đã có sẵn).

    (Đã bỏ Shift+1..5, f/r/l, [ / ] -- xác nhận qua rà soát thực tế là ít dùng, không đáng độ
    phức tạp JS phải duy trì để hỗ trợ chúng.)

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
    _reset_today_on_nav_click) thay vì giữ nguyên trang, sai hoàn toàn ý đồ của phím số khi người
    dùng gọi nó lúc đã đứng sẵn ở trang đích.

    components.html() tạo 1 iframe MỚI mỗi lần rerun, nhưng listener gắn vào
    window.parent.document (document của trang chính, không phải của iframe) nên vẫn tồn tại
    xuyên suốt qua các iframe cũ bị Streamlit xoá đi -- phải tự canh cờ
    window.parent.__appShortcutsInstalled để không gắn trùng listener sau mỗi lần rerun."""
    nav_short_json = json.dumps(list(NAV_SHORT.values()))
    # Overlay được append thẳng vào window.parent.document (không phải iframe riêng như Quill)
    # nên dùng được var(--*) của trang chính, không cần literal theo IS_DARK.
    _txt = "var(--text)"
    _txt2 = "var(--text-2)"
    _bg = "var(--card)"
    _border = "var(--border)"
    js = (
        "<script>\n"
        "(function(){\n"
        "  const w = window.parent;\n"
        "  if (w.__appShortcutsInstalled) return;\n"
        "  w.__appShortcutsInstalled = true;\n"
        "  const NAV_LABELS = " + nav_short_json + ";\n"
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
        "  const HELP_ROWS = [\n"
        "    ['1 – 7', 'Nhảy nhanh tới từng mục nav'],\n"
        "    ['N', 'Mở nhanh Ghi chú ngày hôm nay, cuộn tới và focus sẵn để gõ ngay'],\n"
        "    ['/', 'Focus vào ô Tìm kiếm — Esc để bỏ con trỏ ra khỏi ô'],\n"
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
        "      + 'background:" + _bg + ";border:1px solid " + _border + ";border-radius:10px;'\n"
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
BAOCAO_SUB_ICONS_MD = {"Tổng quan": ":material/dashboard:", "Năm": ":material/calendar_view_month:",
                        "Tháng": ":material/calendar_month:", "Tuần": ":material/view_week:",
                        "Dự án": ":material/folder:"}
if "bc_sub" not in st.session_state:
    _qs = st.query_params.get("sub")
    st.session_state["bc_sub"] = _qs if _qs in BAOCAO_SUBS else "Tổng quan"
if nav == "Báo cáo":
    st.query_params["sub"] = st.session_state["bc_sub"]
elif "sub" in st.query_params:
    del st.query_params["sub"]

# Sub-page của "Sức khoẻ" (Báo cáo/Lịch sử/Dữ liệu đầu vào) -- CÙNG 1 pattern hệt BAOCAO_SUBS ở
# trên (segmented_control + query param riêng), không dùng st.tabs() -- khác tab Hướng dẫn (nội
# dung tĩnh, không cần deep-link) ở chỗ đây là trang thao tác, cần chia sẻ được link/nhảy sang
# đúng sub-tab bằng code (vd sau khi Lưu ở "Dữ liệu đầu vào" có thể tự chuyển sang "Báo cáo").
# Query param riêng "hsub" (không dùng chung "sub" với Báo cáo) để 2 trang không giẫm state.
SUCKHOE_SUBS = ["Báo cáo", "Lịch sử", "Dữ liệu đầu vào"]
SUCKHOE_SUB_ICONS_MD = {"Báo cáo": ":material/monitoring:", "Lịch sử": ":material/history:",
                        "Dữ liệu đầu vào": ":material/edit_note:"}
if "hm_sub" not in st.session_state:
    _qs_hm = st.query_params.get("hsub")
    st.session_state["hm_sub"] = _qs_hm if _qs_hm in SUCKHOE_SUBS else "Báo cáo"
if nav == "Sức khoẻ":
    st.query_params["hsub"] = st.session_state["hm_sub"]
elif "hsub" in st.query_params:
    del st.query_params["hsub"]

_inject_keyboard_shortcuts()


def _inject_scroll_to_top_button():
    """Nút tròn nổi góc dưới-phải "về đầu trang" -- ẩn tới khi cuộn xuống quá 1 ngưỡng mới hiện,
    bấm cuộn mượt về đầu. Tạo bằng JS (components.html) y hệt bảng phím tắt ở
    _inject_keyboard_shortcuts(): gắn thẳng vào window.parent.document để nút không bị Streamlit
    xoá/tạo lại mỗi lần rerun (iframe của components.html có bị dựng lại cũng không sao, nút đã
    sống sẵn trong document cha) -- canh cờ w.__scrollTopBtnInstalled để không tạo trùng nút sau
    mỗi rerun.

    Nghe sự kiện 'scroll' ở PHA CAPTURE (tham số thứ 3 của addEventListener = true) thay vì chỉ
    trên window: tuỳ layout, phần thật sự cuộn có thể là 1 div con của Streamlit thay vì window,
    mà sự kiện scroll KHÔNG tự nổi bọt lên -- nghe ở capture bắt được cả 2 trường hợp mà không
    cần biết trước phần tử nào mới thực sự là vùng cuộn. Khi bấm, cuộn cả window LẪN gọi
    scrollIntoView() trên .block-container cho chắc, cùng lý do."""
    js = (
        "<script>\n"
        "(function(){\n"
        "  const w = window.parent;\n"
        "  if (w.__scrollTopBtnInstalled) return;\n"
        "  w.__scrollTopBtnInstalled = true;\n"
        "  const btn = w.document.createElement('button');\n"
        "  btn.id = 'app-scroll-top-btn';\n"
        "  btn.type = 'button';\n"
        "  btn.setAttribute('aria-label', 'Về đầu trang');\n"
        "  btn.title = 'Về đầu trang';\n"
        "  btn.innerHTML = '<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" "
        "stroke-width=\"2.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\">"
        "<path d=\"M12 19V5M5 12l7-7 7 7\"/></svg>';\n"
        "  btn.addEventListener('click', function(){\n"
        "    w.scrollTo({top: 0, behavior: 'smooth'});\n"
        "    const bc = w.document.querySelector('.block-container');\n"
        "    if (bc) bc.scrollIntoView({behavior: 'smooth', block: 'start'});\n"
        "  });\n"
        "  w.document.body.appendChild(btn);\n"
        "  function onScroll(e){\n"
        "    const t = e.target;\n"
        "    let y = w.scrollY || 0;\n"
        "    if (t && typeof t.scrollTop === 'number') y = Math.max(y, t.scrollTop);\n"
        "    btn.classList.toggle('show', y > 400);\n"
        "  }\n"
        "  w.document.addEventListener('scroll', onScroll, true);\n"
        "})();\n"
        "</script>"
    )
    components.html(js, height=0)


_inject_scroll_to_top_button()


def _kindle_quote_of_day():
    """Chọn 1 trích dẫn/ghi chú Kindle ngẫu nhiên nhưng CỐ ĐỊNH trong ngày -- seed theo ngày THẬT
    hôm nay (_today_vn(), không phải "sel", ngày đang xem trên trang Hôm nay) nên tải lại trang hay
    lùi/tiến xem ngày khác vẫn ra đúng 1 câu suốt cả ngày hôm nay, đúng cảm giác "quote of the
    day" thật -- chỉ đổi khi sang ngày mới (hoặc người dùng tự bấm nút xáo -- xem
    _shuffle_daily_quote()). Trả None nếu chưa import trích dẫn nào (tính năng tuỳ chọn, không
    chặn phần còn lại của trang).

    Chỉ số đang chọn (kq_daily_idx) lưu trong session_state để nút xáo có chỗ ghi đè -- ngày đổi
    (kq_daily_date lệch _today_vn()) thì tính lại theo seed như cũ, đè mất lựa chọn xáo tay của
    ngày hôm trước (đúng ý "quote of the day" -- xáo tay chỉ có tác dụng trong ngày đang xem).

    CHỈ chọn trong các dòng Loại == 'highlight' -- bug thật đã gặp: không lọc thì có thể rơi vào
    1 dòng 'note' (ghi chú cá nhân gắn dưới 1 highlight), khiến card "Trích dẫn hôm nay" (có dấu
    ngoặc kép lớn, xem _render_today_billboard()) hiện ra một ghi chú thay vì trích dẫn thật."""
    kh = load_kindle_highlights()
    kh = kh[kh['Loại'] == 'highlight'] if not kh.empty else kh
    if kh.empty:
        return None
    today_iso = _today_vn().isoformat()
    if st.session_state.get("kq_daily_date") != today_iso:
        st.session_state["kq_daily_date"] = today_iso
        st.session_state["kq_daily_idx"] = random.Random(today_iso).randrange(len(kh))
    # modulo phòng trường hợp kh co lại (xoá bớt trích dẫn) khiến idx cũ vượt quá độ dài mới.
    idx = st.session_state["kq_daily_idx"] % len(kh)
    return kh.iloc[idx]


def _shuffle_daily_quote():
    """Đổi trích dẫn hôm nay sang 1 trích dẫn NGẪU NHIÊN KHÁC (không lặp lại đúng câu đang hiện
    nếu có từ 2 trích dẫn trở lên) -- callback của nút xáo bên cạnh nút ⭐ Yêu thích, xem
    _render_today_billboard(). Chỉ ghi vào session_state, _kindle_quote_of_day() ở lần rerun kế
    tiếp sẽ đọc lại đúng chỉ số này. Đếm/random CÙNG phạm vi Loại == 'highlight' như
    _kindle_quote_of_day(), không tính dòng 'note' -- giữ 2 hàm luôn đồng bộ đúng 1 danh sách."""
    kh = load_kindle_highlights()
    kh = kh[kh['Loại'] == 'highlight'] if not kh.empty else kh
    n = len(kh)
    if n <= 1:
        return
    cur = st.session_state.get("kq_daily_idx")
    new_idx = cur
    while new_idx == cur:
        new_idx = random.randrange(n)
    st.session_state["kq_daily_idx"] = new_idx


def _render_today_billboard(sel, vn_dow, active_days, day_df, df, kq, hero_chips):
    """Billboard đầu trang Hôm nay: gộp card "Ngày đang xem" + "Trích dẫn hôm nay" + chip mục lục
    (trước đây là 3 khối rời -- header glass-card, kq_daily_card, sec_hero) vào 1 khối duy nhất,
    đập vào mắt ngay khi vừa mở trang thay vì rải rác. Cột trái là "tờ lịch xé hằng ngày": số ngày
    to + Thứ/ngày/tháng chữ đầy đủ + 2 dòng meta (ngày hoạt động, cập nhật gần nhất), canh giữa cả
    ngang (CSS text-align) lẫn dọc (vertical_alignment="center" của st.columns, canh theo tâm so
    với cột phải cao hơn). Cột phải là trích dẫn Kindle hôm nay -- vắng mặt hẳn (chưa import trích
    dẫn nào) thì cột ngày chiếm trọn bề rộng, không chia cột.

    Nút ⭐ Yêu thích vẫn là widget Streamlit thật (không nhét được vào chuỗi HTML tĩnh) -- xem lý
    do chọn ký tự "★"/"☆" thay vì icon Material trong lịch sử đổi của hàm _render_daily_quote_card
    cũ (đã gộp vào đây)."""
    _sub = "không có hoạt động" if day_df.empty else f"ngày hoạt động {active_days.index(sel) + 1}/{len(active_days)}"
    _last_dt = df['Thời gian kết thúc'].max()
    _upd_line = ''
    if pd.notna(_last_dt):
        _last_ts = pd.Timestamp(_last_dt)
        _abs_str = _last_ts.strftime('%H:%M · %d/%m/%Y')
        # epoch UTC thật (không lệch theo múi giờ máy chủ/máy khách) cho JS ticker tự cập nhật
        # "X trước" mỗi 30s -- xem _inject_relative_time_ticker().
        _epoch_ms = int(_last_ts.tz_localize(APP_TZ).timestamp() * 1000)
        _upd_line = (f"Cập nhật gần nhất <b id='last-update-live' data-epoch='{_epoch_ms}' "
                     f"title='Cập nhật lúc {_abs_str}'>{format_relative(_last_dt)}</b>")

    _tab_label = f"{VN_MONTHS_WORD[sel.month - 1]} {sel.year}"
    _date_html = (
        "<div class='tbill-date'>"
        f"<div class='tbill-tab'><span class='tbill-tab-label'>{_tab_label}</span></div>"
        f"<div class='tbill-num'>{sel.day}</div>"
        f"<div class='tbill-dow'>{vn_dow}</div>"
        f"<div class='tbill-meta'>{_sub}" + (f"<br>{_upd_line}" if _upd_line else "") + "</div></div>")

    with st.container(key="today_billboard", border=True):
        if kq is not None:
            with st.container(key="tbill_daterow"):
                c_date, c_quote = st.columns([1, 2], vertical_alignment="center")
                with c_date:
                    st.markdown(_date_html, unsafe_allow_html=True)
                with c_quote:
                    st.markdown(
                        "<div class='kq-daily-mark'>“</div>"
                        f"<div class='kq-daily-text'>{html_escape(str(kq['Nội dung']))}</div>",
                        unsafe_allow_html=True)
                    with st.container(key="kq_daily_srcrow"):
                        _kh_all = load_kindle_highlights()
                        _kh_count = len(_kh_all[_kh_all['Loại'] == 'highlight']) if not _kh_all.empty else 0
                        c_src, c_shuffle, c_fav = st.columns([9, 1, 1])
                        with c_src:
                            _author = kq.get('Tác giả')
                            # Tên tác giả đứng TRƯỚC tên sách (khớp quy ước trích dẫn văn học
                            # thường gặp "Tác giả, Tên sách") -- trước đây để sách trước, tác giả
                            # sau, phản hồi thực tế là ngược thứ tự mong muốn.
                            _src_txt = (f"{html_escape(str(_author))} · " if pd.notna(_author)
                                        and str(_author).strip() else "") + html_escape(str(kq['Cuốn sách']))
                            st.markdown(f"<div class='kq-daily-src'>— {_src_txt}</div>", unsafe_allow_html=True)
                        with c_shuffle:
                            if _kh_count > 1 and st.button("", icon=":material/shuffle:", key="kq_daily_shufflebtn",
                                                            help="Đổi trích dẫn khác"):
                                _shuffle_daily_quote()
                                st.rerun()
                        with c_fav:
                            _fav = bool(kq.get('Yêu thích', False))
                            if st.button("★" if _fav else "☆",
                                         key=f"kq_daily_favbtn_{'on' if _fav else 'off'}",
                                         help="Bỏ Yêu thích" if _fav else "Yêu thích"):
                                set_kindle_highlight_favorite(kq['dedupe_hash'], not _fav)
                                st.rerun()
        else:
            st.markdown(_date_html, unsafe_allow_html=True)

        _chips_html = "".join(f"<a class='sec-toc-chip' href='#{a}'>{lbl}</a>" for a, lbl in hero_chips)
        st.markdown(f"<div class='sec-toc' style='margin-top:20px;'>{_chips_html}</div>", unsafe_allow_html=True)

    if _upd_line:
        _inject_relative_time_ticker()


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

    # Billboard đầu trang: gộp "Ngày đang xem" + "Trích dẫn hôm nay" + chip mục lục vào 1 khối
    # duy nhất (xem docstring _render_today_billboard()). Bộ chip khác nhau tuỳ ngày trống hay có
    # phiên (2 mục không đánh số vs 5 mục đánh số 1-5, xem 2 nhánh bên dưới).
    # "Ngày này năm trước" dời XUỐNG CUỐI (chương 5, sau "Danh sách phiên") -- xác nhận với người
    # dùng đổi lại khỏi vị trí "ngay sau Ghi chú ngày" của lần dọn dẹp trước (xem Nhật ký phát
    # triển), giờ chỉ còn là mục tham khảo phụ đọc thêm cuối trang, không còn ở đầu.
    _hero_chips = ([("today-ch1", "1 · Ghi chú ngày"), ("today-ch2", "2 · Ngày này năm trước")]
                   if day_df.empty else
                   [("today-ch1", "1 · Tổng quan ngày"), ("today-ch2", "2 · Ghi chú ngày"),
                    ("today-ch3", "3 · Phân bổ thời gian"), ("today-ch4", "4 · Danh sách phiên"),
                    ("today-ch5", "5 · Ngày này năm trước")])
    _render_today_billboard(sel, vn_dow, active_days, day_df, df, _kindle_quote_of_day(), _hero_chips)

    if day_df.empty:
        sec_chapter("today-ch1", 1, None, "Ghi chú ngày", tight_top=True)
        render_note_editor(sel, sel_day_badges)
        sec_chapter("today-ch2", 2, None, "Ngày này năm trước")
        render_on_this_day(sel, df)
    else:
        sec_chapter("today-ch1", 1, None, "Tổng quan ngày", tight_top=True)
        d_hrs = day_df['Thời lượng (Phút)'].sum() / 60
        d_sess = len(day_df)
        d_avg = _avg_session_min(day_df)

        cmp_chips = []
        pw = df[df['Ngày'] == (sel - timedelta(days=7))]
        if not pw.empty:
            pw_h, pw_s = pw['Thời lượng (Phút)'].sum() / 60, len(pw)
            _c = "#34c759" if d_hrs > pw_h else "#ff3b30" if d_hrs < pw_h else "#86868b"
            cmp_chips.append({"k": f"vs {vn_dow} tuần trước", "v": f"{_fmt_hours_short(pw_h)}",
                              "delta": (f"{_fmt_hours_delta(d_hrs - pw_h)} · {_fmt_delta(d_sess - pw_s)} phiên", _c)})
        else:
            cmp_chips.append({"k": f"vs {vn_dow} tuần trước", "v": "không có"})
        same = df[(pd.to_datetime(df['Ngày']).dt.day_name() == pd.Timestamp(sel).day_name())
                  & (df['Ngày'] != sel)]
        if same['Ngày'].nunique():
            avg_h = (same.groupby('Ngày')['Thời lượng (Phút)'].sum() / 60).mean()
            _c = "#34c759" if d_hrs > avg_h else "#ff3b30" if d_hrs < avg_h else "#86868b"
            cmp_chips.append({"k": f"vs TB các {vn_dow}", "v": f"{_fmt_hours_short(avg_h)}",
                              "delta": (f"{_fmt_hours_delta(d_hrs - avg_h)}", _c)})

        t0 = pd.to_datetime(day_df['Thời gian bắt đầu']).min()
        t1 = pd.to_datetime(day_df['Thời gian kết thúc']).max()
        _sp = t1 - t0
        span_str = f"{int(_sp.total_seconds() // 3600)}h{int((_sp.total_seconds() % 3600) // 60):02d}"

        bg = (day_df.assign(_b=pd.to_datetime(day_df['Thời gian bắt đầu']).dt.hour.map(_buoi_of))
                    .groupby('_b')['Thời lượng (Phút)'].sum() / 60)
        buoi_chips = [{"k": b, "v": f"{_fmt_hours_short(bg[b])}"} for b in ["Sáng", "Chiều", "Tối", "Khuya"] if bg.get(b, 0) > 0]

        _secs = [{"label": "So sánh", "chips": cmp_chips},
                 {"label": "Mốc trong ngày", "chips": [
                     {"k": "Phiên đầu", "v": f"{t0:%H:%M}"},
                     {"k": "Phiên cuối", "v": f"{t1:%H:%M}"},
                     {"k": "Trải dài", "v": span_str}]}]
        if buoi_chips:
            _secs.append({"label": "Theo buổi", "chips": buoi_chips})
        render_stat_panel(hero_items=[
            {"label": "Tổng thời gian", "value": f"{_fmt_hours_short(d_hrs)}"},
            {"label": "Số phiên", "value": f"{d_sess}"},
            {"label": "Độ dài / phiên", "value": f"{d_avg:.0f} phút"},
        ], sections=_secs)

        # Dòng thời gian đứng NGAY SAU stat panel -- theo đúng bố cục "Sổ Tay": nhìn được nhịp
        # phiên trong ngày trước khi đọc số liệu tổng hợp bên dưới. Bỏ lớp mờ "khung giờ điển
        # hình của thứ này" (không cần thiết, gây rối) -- chỉ còn khối phiên + legend theo Dự
        # án. KHÔNG có Top 3 Danh mục/Dự án ở đây (khác Báo cáo theo kỳ) -- 1 ngày thường chỉ
        # 2-4 phiên, đã thấy rõ hết trong dòng thời gian ngay phía trên, xếp hạng top 3 chỉ lặp
        # lại thông tin.
        render_day_timeline(day_df)

        render_session_bar(day_df)

        sec_chapter("today-ch2", 2, None, "Ghi chú ngày")
        render_note_editor(sel, sel_day_badges)

        sec_chapter("today-ch3", 3, None, "Phân bổ thời gian")
        frag_category_bars(day_df, "rad_day", "Dự án")

        sec_chapter("today-ch4", 4, None, "Danh sách phiên")
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

        sec_chapter("today-ch5", 5, None, "Ngày này năm trước")
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
            # Thẻ "Cập nhật gần nhất" đã dời sang trang Hôm nay (đuôi của card "Ngày đang
            # xem") -- Hôm nay giờ mới là trang mở đầu tiên, không còn hợp lý để card này
            # đứng đầu Tổng quan (sub-tab không mặc định) nữa.
            total_hrs = df['Thời lượng (Phút)'].sum() / 60
            total_trees = len(df)
            num_days = df['Ngày'].nunique() or 1
            base_avg = total_hrs / num_days
            n_cats = df['Danh mục'].nunique()
            n_projs = df['Dự án'].nunique()

            render_period_billboard(
                "Toàn bộ dữ liệu", _fmt_hours_short(total_hrs), "tổng thời gian đã trồng",
                f"{num_days} ngày · {n_cats} danh mục · {n_projs} dự án",
                "<div class='pbill-title'>Nhìn lại tất cả thời gian đã trồng</div>"
                "<div class='pbill-sub'>Số liệu tổng hợp từ ngày đầu dùng Forest tới nay.</div>",
                [("bc-tq-ch1", "1 · Tổng quan"), ("bc-tq-ch2", "2 · Biểu đồ lịch"),
                 ("bc-tq-ch3", "3 · Xu hướng"), ("bc-tq-ch4", "4 · Bảng số liệu")])
            sec_chapter("bc-tq-ch1", 1, None, "Tổng quan", tight_top=True)

            s_stat = _streak_stats(df)
            by_wd = _weekday_avg(df)
            overall_top3 = _top_days(df, 3)
            _sections = [
                {"label": "Trung bình (toàn thời gian)", "chips": [
                    {"k": "Thời gian / ngày", "v": f"{_fmt_hours_short(base_avg)}"},
                    {"k": "Số cây / ngày", "v": f"{total_trees/num_days:.1f}"},
                    {"k": "Thời gian / phiên", "v": f"{_avg_session_min(df):.0f} phút"},
                ]},
                {"label": "Chuỗi ngày", "chips": [
                    {"k": "Tổng cộng", "v": f"{s_stat['total']} ngày"},
                    {"k": "Dài nhất", "v": f"{s_stat['longest']} ngày"},
                    {"k": "Hiện tại", "v": f"{s_stat['current']} ngày", "hl": True},
                ]},
            ]
            if len(by_wd) and by_wd.max() > 0:
                _sections.append({"label": "Theo thứ", "chips": [
                    {"k": "Mạnh nhất", "v": f"{by_wd.idxmax()} ({_fmt_hours_short(by_wd.max())})"},
                    {"k": "Yếu nhất", "v": f"{by_wd.idxmin()} ({_fmt_hours_short(by_wd.min())})"},
                ]})
            if overall_top3:
                _sections.append({"label": "Ngày nổi bật", "chips": _top_days_chips(overall_top3)})
            _nud = _streak_nudge(s_stat)
            _footer = (_nud[0],) + NUDGE_TONES[_nud[1]] if _nud else None

            render_stat_panel(
                hero_items=[
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

            sec_chapter("bc-tq-ch2", 2, None, "Biểu đồ lịch")
            frag_calendar(df, "range_cal")
            sec_chapter("bc-tq-ch3", 3, None, "Xu hướng")
            _tq_trend_view = st.segmented_control(
                "Xem theo", ["Theo thời gian", "Theo khung giờ"], default="Theo thời gian",
                key="bc_tq_trend_view", label_visibility="collapsed") or "Theo thời gian"
            if _tq_trend_view == "Theo thời gian":
                frag_trend(df, "trend_main", "Danh mục")
            else:
                frag_hourly(df, "hour_main", "Danh mục")
            sec_chapter("bc-tq-ch4", 4, None, "Bảng số liệu")
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
            # theo đúng phần đã trôi qua (vd "2 ngày đầu tuần"), cùng lý do đã áp dụng cho Tháng
            # (xem docstring _period_elapsed_context, hàm dùng chung cho cả 3 nhánh Tuần/Tháng/Năm).
            elapsed_mask_w, lbl_prev_w, lbl_avg_w, _clip_note_w = _period_elapsed_context(
                selected_week, _today_vn().strftime('%G-W%V'),
                df['Thời gian bắt đầu'].dt.dayofweek + 1, _today_vn().isoweekday(), "Tuần")
            prev_w, avg_w = _period_comparison(df, 'Tuần', selected_week, prev_week_key, elapsed_mask_w)

            if not df_w.empty:
                # Billboard số to + câu nhận định (mockup) -- bộ chương đã khác hẳn Tháng theo
                # mockup riêng của Tuần: bỏ "Xu hướng tập trung theo khung giờ", đổi "Phân bổ
                # thời gian" (pie) -> "Danh mục & dự án" (thanh ngang xếp hạng, frag_category_bars),
                # đổi Bảng số liệu sang trục theo NGÀY (render_period_day_table) thay vì Danh mục/
                # Dự án (đã có ở chương thanh ngang rồi, không lặp lại trục), và đổi tên chương
                # "Xu hướng theo thời gian" -> "Theo ngày" (giữ đúng thứ tự mockup: Theo ngày đứng
                # trước Danh mục & dự án). Tháng đã có billboard + "Lịch tháng"/"Phân bổ danh mục"
                # riêng (xem nhánh Tháng) nhưng vẫn giữ "Xu hướng theo thời gian"/"Xu hướng khung
                # giờ"/"Bảng số liệu" cũ -- không đủ giống Tuần để gộp chung. Năm CHƯA đối chiếu
                # mockup riêng -- vẫn giữ nguyên sec_hero cũ, không đụng tới.
                _wy, _wk = selected_week.split('-W')
                _week_start = date.fromisocalendar(int(_wy), int(_wk), 1)
                _week_end = _week_start + timedelta(days=6)
                _active_days_w = df_w['Ngày'].nunique()
                _curr_hrs_w = df_w['Thời lượng (Phút)'].sum() / 60
                _by_day_w = df_w.groupby('Ngày')['Thời lượng (Phút)'].sum()
                _busiest_date_w = _by_day_w.idxmax()
                _busiest_dow_w = VN_DAYS.get(pd.Timestamp(_busiest_date_w).day_name(), "")
                _streak_cur_w = _streak_stats(df)['current']

                _delta_txt_w = ""
                if prev_w and prev_w.get('hrs') is not None:
                    _dh_w = _curr_hrs_w - prev_w['hrs']
                    if abs(_dh_w) >= (1 / 60):
                        _delta_txt_w = f"{'Hơn' if _dh_w > 0 else 'Kém'} tuần trước {_fmt_hours_short(abs(_dh_w))}. "
                _expected_days_w = (_today_vn().isoweekday()
                                     if selected_week == _today_vn().strftime('%G-W%V') else 7)
                _gap_txt_w = ("không ngày nào trống" if _active_days_w >= _expected_days_w
                              else f"{_expected_days_w - _active_days_w} ngày trống")
                _streak_txt_w = f" — chuỗi giữ mạch {_streak_cur_w} ngày" if _streak_cur_w > 0 else ""
                _pbill_sub_w = f"{_delta_txt_w}{_busiest_dow_w} là ngày dày nhất; {_gap_txt_w}{_streak_txt_w}."

                if prev_w and prev_w.get('hrs') is not None and _curr_hrs_w > prev_w['hrs']:
                    _pbill_title_w = "Một tuần tăng tốc"
                elif prev_w and prev_w.get('hrs') is not None and _curr_hrs_w < prev_w['hrs']:
                    _pbill_title_w = "Một tuần chững lại"
                elif _active_days_w >= _expected_days_w:
                    _pbill_title_w = "Một tuần nhịp đều"
                else:
                    _pbill_title_w = "Một tuần vừa qua"

                render_period_billboard(
                    f"Tuần {int(_wk)} · {_wy}", _fmt_hours_short(_curr_hrs_w), "tổng thời gian tuần này",
                    f"{_week_start:%d/%m} – {_week_end:%d/%m} · hoạt động {_active_days_w}/7 ngày",
                    f"<div class='pbill-title'>{_pbill_title_w}</div><div class='pbill-sub'>{_pbill_sub_w}</div>",
                    [("bc-tuan-ch1", "1 · Tổng quan"), ("bc-tuan-ch2", "2 · Danh mục & dự án"),
                     ("bc-tuan-ch3", "3 · Theo ngày"), ("bc-tuan-ch4", "4 · Nhật ký"),
                     ("bc-tuan-ch5", "5 · Bảng số liệu")])
                # KHÔNG có Top 3 Danh mục/Dự án ở Tuần (khác Tổng quan/Tháng/Năm) -- xác nhận
                # không cần thiết ở quy mô 1 tuần, tránh lặp thông tin đã có ở chương "Danh mục &
                # dự án" bên dưới.
                _render_period_overview_hero(df_w, df, 'Tuần', selected_week, prev_w, avg_w,
                                              lbl_prev_w, lbl_avg_w, _clip_note_w,
                                              "Ngày nổi bật trong tuần", show_top3=False,
                                              anchor_prefix="bc-tuan", show_footer=False)
                sec_chapter("bc-tuan-ch2", 2, None, "Danh mục & dự án")
                frag_category_bars(df_w, "rad_tab4", "Danh mục")
                sec_chapter("bc-tuan-ch3", 3, None, "Theo ngày")
                frag_period_trend(df_w, "trend_w_color", "Danh mục", 'Thứ', "Thứ trong tuần", cat_order=DAYS_ORDER)
                sec_chapter("bc-tuan-ch4", 4, None, "Nhật ký")
                render_notes_journal(selected_week, 'week', df)
                sec_chapter("bc-tuan-ch5", 5, None, "Bảng số liệu")
                render_period_day_table(df_w, all_days=[_week_start + timedelta(days=i) for i in range(7)])
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
            # item) làm chữ dài, tự xuống dòng lem nhem trong cột hẹp. Logic dùng chung với
            # Tuần/Năm qua _period_elapsed_context (xem docstring).
            elapsed_mask_m, lbl_prev_m, lbl_avg_m, _clip_note_m = _period_elapsed_context(
                selected_month, _today_vn().strftime('%Y-%m'),
                df['Thời gian bắt đầu'].dt.day, _today_vn().day, "Tháng")
            prev_m, avg_m = _period_comparison(df, 'Tháng', selected_month, prev_month_key, elapsed_mask_m)

            if not df_m.empty:
                # Billboard số to + câu nhận định (mockup, theo đúng pattern Tuần đã làm trước --
                # xem chú thích ở nhánh Tuần) -- cột phải là câu nhận định tự tính (KHÔNG phải
                # hàng chip "vs Tháng trước"/"Danh mục dẫn đầu"/... như bản mockup vẽ tĩnh, vì các
                # số đó ĐÃ có trong chương "Tổng quan" giữ nguyên bên dưới -- hero item deltas +
                # Top 3 Danh mục/Dự án -- lặp lại ở billboard sẽ dư thừa).
                _curr_hrs_m = df_m['Thời lượng (Phút)'].sum() / 60
                _active_days_m = df_m['Ngày'].nunique()
                _by_day_m = df_m.groupby('Ngày')['Thời lượng (Phút)'].sum()
                _busiest_date_m = _by_day_m.idxmax()
                _busiest_hrs_m = _by_day_m.max() / 60
                _streak_cur_m = _streak_stats(df)['current']
                _is_current_month_m = (selected_month == _today_vn().strftime('%Y-%m'))
                _days_in_month_m = pd.Period(f"{y:04d}-{m:02d}").days_in_month
                _elapsed_days_m = _today_vn().day if _is_current_month_m else _days_in_month_m

                _delta_txt_m = ""
                if prev_m and prev_m.get('hrs') is not None:
                    _dh_m = _curr_hrs_m - prev_m['hrs']
                    if abs(_dh_m) >= (1 / 60):
                        _delta_txt_m = f"{'Hơn' if _dh_m > 0 else 'Kém'} tháng trước {_fmt_hours_short(abs(_dh_m))}. "
                _gap_txt_m = ("không ngày nào trống" if _active_days_m >= _elapsed_days_m
                              else f"{_elapsed_days_m - _active_days_m} ngày trống")
                _streak_txt_m = f" — chuỗi giữ mạch {_streak_cur_m} ngày" if _streak_cur_m > 0 else ""
                _pbill_sub_m = (f"{_delta_txt_m}Ngày {_busiest_date_m:%d/%m} là ngày dày nhất "
                                 f"({_fmt_hours_short(_busiest_hrs_m)}); {_gap_txt_m}{_streak_txt_m}.")

                if prev_m and prev_m.get('hrs') is not None and _curr_hrs_m > prev_m['hrs']:
                    _pbill_title_m = "Một tháng tăng tốc"
                elif prev_m and prev_m.get('hrs') is not None and _curr_hrs_m < prev_m['hrs']:
                    _pbill_title_m = "Một tháng chững lại"
                elif _active_days_m >= _elapsed_days_m:
                    _pbill_title_m = "Một tháng nhịp đều"
                else:
                    _pbill_title_m = "Một tháng vừa qua"

                render_period_billboard(
                    f"{VN_MONTHS_WORD[m - 1]} {y}", _fmt_hours_short(_curr_hrs_m),
                    (f"trong {_elapsed_days_m} ngày đầu tháng" if _is_current_month_m
                     else "tổng thời gian tháng này"),
                    f"{_active_days_m} ngày hoạt động · {len(df_m)} phiên",
                    f"<div class='pbill-title'>{_pbill_title_m}</div><div class='pbill-sub'>{_pbill_sub_m}</div>",
                    [("bc-thang-ch1", "1 · Tổng quan"), ("bc-thang-ch2", "2 · Lịch tháng"),
                     ("bc-thang-ch3", "3 · Phân bổ danh mục"), ("bc-thang-ch4", "4 · Xu hướng"),
                     ("bc-thang-ch5", "5 · Nhật ký"), ("bc-thang-ch6", "6 · Bảng số liệu")])
                _render_period_overview_hero(df_m, df, 'Tháng', selected_month, prev_m, avg_m,
                                              lbl_prev_m, lbl_avg_m, _clip_note_m,
                                              "Ngày nổi bật trong tháng", show_top3=False,
                                              anchor_prefix="bc-thang", top3_suffix=" Tháng",
                                              show_footer=False)
                # "Điểm nhấn" gộp vào chương Tổng quan (không còn là chương riêng) -- 2 thẻ
                # Kỷ lục trong tháng/So với tháng trước bổ sung ngay dưới hero+Top3 cũ.
                render_month_highlights(df_m, df, prev_month_key, elapsed_mask_m, prev_m)

                sec_chapter("bc-thang-ch2", 2, None, "Lịch tháng")
                # Truyền CÙNG df_m cho cả 2 tham số -- đúng pattern lịch năm đã có
                # (render_calendar_grid(df_y, df_y) ở nhánh Năm), lưới tự bó gọn theo đúng phạm vi
                # tháng đang chọn, không kéo dài tới ngày hiện tại như khi truyền full df.
                render_calendar_grid(df_m, df_m)

                sec_chapter("bc-thang-ch3", 3, None, "Phân bổ danh mục")
                frag_category_bars(df_m, "rad_tab3", "Danh mục")

                sec_chapter("bc-thang-ch4", 4, None, "Xu hướng")
                _thang_trend_view = st.segmented_control(
                    "Xem theo", ["Theo tuần", "Theo ngày", "Theo khung giờ"], default="Theo tuần",
                    key="bc_thang_trend_view", label_visibility="collapsed") or "Theo tuần"
                if _thang_trend_view == "Theo tuần":
                    render_month_week_bars(df_m)
                elif _thang_trend_view == "Theo ngày":
                    frag_period_trend(df_m, "trend_m_color", "Danh mục", 'Ngày', "Ngày trong tháng")
                else:
                    frag_hourly(df_m, "hour_m", "Danh mục", with_range=False)

                sec_chapter("bc-thang-ch5", 5, None, "Nhật ký")
                render_notes_journal(selected_month, 'month', df)
                sec_chapter("bc-thang-ch6", 6, None, "Bảng số liệu")
                render_detail_table(df_m)
    elif bc_sub == "Năm":
        if not df.empty:
            years = sorted(df['Năm'].unique())
            selected_year = period_stepper(years, key="year", fmt=lambda y: f"Năm {y}", current=str(_today_vn().year))
            df_y = df[df['Năm'] == selected_year]
            prev_year_key = str(int(selected_year) - 1)

            # Kỳ đang xem CHƯA kết thúc (đang là năm hiện tại) -> cắt cả 2 baseline so sánh
            # theo đúng phần đã trôi qua, cùng lý do đã áp dụng cho Tháng/Tuần qua
            # _period_elapsed_context (xem docstring). Nhãn delta giữ NGẮN (xem chú thích tương
            # ứng ở nhánh Tháng).
            elapsed_mask_y, lbl_prev_y, lbl_avg_y, _clip_note_y = _period_elapsed_context(
                selected_year, str(_today_vn().year),
                df['Thời gian bắt đầu'].dt.dayofyear, _today_vn().timetuple().tm_yday, "Năm")
            prev_y, avg_y = _period_comparison(df, 'Năm', selected_year, prev_year_key, elapsed_mask_y)

            if not df_y.empty:
                # Billboard số to + câu nhận định (mockup, theo đúng pattern Tuần/Tháng đã làm --
                # xem chú thích ở nhánh Tháng). Cột phải là câu nhận định tự tính (KHÔNG phải hàng
                # chip "vs năm trước"/"Dự án của năm"/... như mockup vẽ tĩnh -- các số đó ĐÃ có ở
                # chương "Tổng quan" giữ nguyên bên dưới, lặp lại ở billboard sẽ dư thừa).
                _curr_hrs_y = df_y['Thời lượng (Phút)'].sum() / 60
                _active_days_y = df_y['Ngày'].nunique()
                _by_month_y = df_y.groupby(pd.to_datetime(df_y['Ngày']).dt.month)['Thời lượng (Phút)'].sum()
                _busiest_month_y = _by_month_y.idxmax()
                _busiest_month_hrs_y = _by_month_y.max() / 60
                _streak_cur_y = _streak_stats(df)['current']
                _is_current_year_y = (selected_year == str(_today_vn().year))
                _days_in_year_y = pd.Timestamp(int(selected_year), 12, 31).dayofyear
                _elapsed_days_y = _today_vn().timetuple().tm_yday if _is_current_year_y else _days_in_year_y

                _delta_txt_y = ""
                if prev_y and prev_y.get('hrs') is not None:
                    _dh_y = _curr_hrs_y - prev_y['hrs']
                    if abs(_dh_y) >= (1 / 60):
                        _delta_txt_y = f"{'Hơn' if _dh_y > 0 else 'Kém'} năm trước {_fmt_hours_short(abs(_dh_y))}. "
                _gap_txt_y = ("không ngày nào trống" if _active_days_y >= _elapsed_days_y
                              else f"{_elapsed_days_y - _active_days_y} ngày trống")
                _streak_txt_y = f" — chuỗi giữ mạch {_streak_cur_y} ngày" if _streak_cur_y > 0 else ""
                _pbill_sub_y = (f"{_delta_txt_y}Tháng {_busiest_month_y} là tháng cao nhất "
                                 f"({_fmt_hours_short(_busiest_month_hrs_y)}); {_gap_txt_y}{_streak_txt_y}.")

                if prev_y and prev_y.get('hrs') is not None and _curr_hrs_y > prev_y['hrs']:
                    _pbill_title_y = "Một năm tăng tốc"
                elif prev_y and prev_y.get('hrs') is not None and _curr_hrs_y < prev_y['hrs']:
                    _pbill_title_y = "Một năm chững lại"
                elif _active_days_y >= _elapsed_days_y:
                    _pbill_title_y = "Một năm nhịp đều"
                else:
                    _pbill_title_y = "Một năm nhìn lại"

                render_period_billboard(
                    f"Năm {selected_year}", _fmt_hours_short(_curr_hrs_y),
                    (f"tính đến {_today_vn():%d/%m}" if _is_current_year_y else "tổng thời gian năm này"),
                    f"{_active_days_y} ngày hoạt động / {_elapsed_days_y} · {len(df_y)} phiên",
                    f"<div class='pbill-title'>{_pbill_title_y}</div><div class='pbill-sub'>{_pbill_sub_y}</div>",
                    [("bc-nam-ch1", "1 · Tổng quan"), ("bc-nam-ch2", "2 · Biểu đồ lịch"),
                     ("bc-nam-ch3", "3 · Danh mục cả năm"), ("bc-nam-ch4", "4 · Theo tháng"),
                     ("bc-nam-ch5", "5 · Bảng số liệu")])
                _render_period_overview_hero(df_y, df, 'Năm', selected_year, prev_y, avg_y,
                                              lbl_prev_y, lbl_avg_y, _clip_note_y,
                                              "Ngày nổi bật trong năm", show_top3=False,
                                              anchor_prefix="bc-nam", top3_suffix=" Năm",
                                              show_footer=False)
                # "Kỷ lục năm" gộp vào chương Tổng quan (không còn là chương riêng) -- cùng cách
                # xử lý "Điểm nhấn" ở nhánh Tháng, xác nhận với người dùng.
                render_year_highlights(df_y, _active_days_y, _elapsed_days_y, selected_year)

                # Nhánh Năm có bộ mục 2-5 khác Tuần/Tháng (Biểu đồ lịch/Danh mục cả năm/Theo
                # tháng thay vì Nhật ký/Phân bổ/Xu hướng/Khung giờ/Độ dài phiên) -- không đủ giống
                # để viết chung 1 hàm với Tháng, giữ riêng ở đây.
                sec_chapter("bc-nam-ch2", 2, None, "Biểu đồ lịch")
                # Truyền CÙNG df_y cho cả 2 tham số (không frag_calendar/range_radio) -- cùng
                # pattern với chương "Lịch tháng" ở nhánh Tháng (render_calendar_grid(df_m, df_m))
                # để lưới tự bó gọn theo đúng phạm vi năm đang chọn,
                # không tự kéo dài tới ngày hiện tại như khi truyền full df làm full_df.
                render_calendar_grid(df_y, df_y)

                sec_chapter("bc-nam-ch3", 3, None, "Danh mục cả năm")
                render_year_category_bars(df_y, df, prev_year_key, elapsed_mask_y)

                sec_chapter("bc-nam-ch4", 4, None, "Theo tháng")
                render_year_month_bars(df_y)

                sec_chapter("bc-nam-ch5", 5, None, "Bảng số liệu")
                render_detail_table(df_y)
    elif bc_sub == "Dự án":
        if not df.empty:
            # Gom dự án theo nhóm (Danh mục) và phân biệt rõ Nhóm vs Dự án trong dropdown
            proj_to_cat = df.dropna(subset=['Dự án']).groupby('Dự án')['Danh mục'].first()
            # Dự án nào ĐÃ là 1 cuốn sách theo dõi ở trang Sách (đúng điều kiện books_df ở nhánh
            # "Nhật ký đọc sách" bên dưới: Danh mục == BOOKS_GROUP, KHÔNG nằm trong BOOKS_EXCLUDE)
            # thì bỏ khỏi danh sách chọn ở đây -- xem số liệu qua trang Sách (đủ ngữ cảnh sách/tác
            # giả/tiến độ đọc), không cần lặp lại tuỳ chọn ở Báo cáo → Dự án nữa. Gundam/The
            # Economist (nằm trong BOOKS_EXCLUDE) vẫn giữ nguyên -- không "đã có trong phần Sách".
            _book_projects = set(
                df[(df['Danh mục'] == BOOKS_GROUP) & (~df['Dự án'].isin(BOOKS_EXCLUDE))]['Dự án'].dropna().unique())
            # Mục rỗng đứng đầu -- mặc định KHÔNG chọn sẵn nhóm/dự án nào khi mới vào trang,
            # giống hệt selectbox "Chọn 1 cuốn/series" ở sub-tab Chi tiết (Sách/Gundam).
            _placeholder = ("none", "— Chọn để xem chi tiết —")
            _opts, _labels = [_placeholder], {_placeholder: _placeholder[1]}
            for _c in sorted(df['Danh mục'].dropna().unique()):
                _projs = [p for p in sorted(proj_to_cat[proj_to_cat == _c].index.tolist())
                          if p not in _book_projects]
                if not _projs:
                    continue
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

                # Mục "Nhật ký đọc" chỉ hiện khi Dự án đang xem khớp 1 cuốn sách theo dõi qua
                # Reminders (so _book_title() của List với tên Dự án) -- KHÔNG đánh số (giữ nguyên
                # số các mục 1-5 cố định) vì đây là mục điều kiện, đúng tiền lệ "Ghi chú ngày"
                # không số ở nhánh rỗng-phiên của Hôm nay. Hiện trọn lịch sử phần đã đọc của đúng
                # cuốn đó, không giới hạn theo kỳ (khác Nhật ký đọc sách ở Báo cáo tuần/tháng). Tính
                # TRƯỚC hero để biết có cần thêm chip mục lục cho mục này hay không -- load_reading_
                # log() có @st.cache_data nên gọi ở đây không tốn thêm truy vấn thật.
                _rl_book = pd.DataFrame()
                if _kind == "proj":
                    _rl_all = load_reading_log()
                    _rl_book = _rl_all[_rl_all['Cuốn sách'] == sel_grp] if not _rl_all.empty else _rl_all

                # Billboard số to + hồ sơ (mockup) -- KHÁC billboard Tuần/Tháng/Năm (câu nhận
                # định động về 1 KỲ thời gian): đây là hồ sơ 1 THỰC THỂ (Dự án/Nhóm) nên cột phải
                # theo đúng khuôn Sách/Gundam (.pbill-kicker/.pbill-booktitle + .pbill-chips).
                # Đã rà soát bỏ những gì TRÙNG với panel "Tổng quan" chi tiết hơn giữ nguyên bên
                # dưới: KHÔNG có chip "Phiên gần nhất"/"bắt đầu MM-YYYY" trong meta (đã có "Ngày
                # gần nhất"/"Ngày đầu tiên" ở mục Mốc thời gian, cùng 1 sự thật, billboard lặp lại
                # sẽ dư), thay vào đó chuyển câu NHẬN ĐỊNH CHUỖI (trước là footer của panel Tổng
                # quan) lên đây -- billboard là nơi hợp lý hơn cho 1 câu "động lực" ngắn, tránh
                # 2 nơi cùng nói về chuỗi (panel còn giữ số liệu THÔ: Tổng cộng/Dài nhất/Hiện tại).
                curr_hrs_g = df_g['Thời lượng (Phút)'].sum() / 60
                curr_trees_g = len(df_g)
                num_days_g = df_g['Ngày'].nunique() or 1
                num_weeks_g = df_g['Tuần'].nunique() or 1

                _first_day_ts = pd.Timestamp(df_g['Ngày'].min()) if pd.notna(df_g['Ngày'].min()) else None
                _last_day_ts = pd.Timestamp(df_g['Ngày'].max()) if pd.notna(df_g['Ngày'].max()) else None
                first_day = _first_day_ts.strftime('%d/%m/%Y') if _first_day_ts is not None else "—"
                last_day = _last_day_ts.strftime('%d/%m/%Y') if _last_day_ts is not None else "—"

                # Ngưỡng 14 ngày -- khớp recency_days=14 mặc định của render_reading_log()
                # ("Đang đọc"/"Đã xong"), đồng bộ ngữ nghĩa "hoạt động gần đây" xuyên app.
                _is_active_g = _last_day_ts is not None and (_today_vn() - _last_day_ts.date()).days <= 14
                _status_html_g = (f"<span class='pbill-status {'active' if _is_active_g else 'inactive'}'>"
                                   f"{'Đang hoạt động' if _is_active_g else 'Không hoạt động'}</span>")

                _recent28_g = df_g[pd.to_datetime(df_g['Ngày']) >= pd.Timestamp(_today_vn() - timedelta(days=27))]
                _tb_4w_hrs_g = _recent28_g['Thời lượng (Phút)'].sum() / 60 / 4
                _wk_hrs_g = df_g.groupby('Tuần')['Thời lượng (Phút)'].sum()

                s_g = _streak_stats(df_g)
                _nud_g = _streak_nudge(s_g)
                _nudge_html_g = ""
                if _nud_g:
                    _nud_bg_g, _nud_fg_g = NUDGE_TONES[_nud_g[1]]
                    _nudge_html_g = (f"<div class='pbill-sub' style='color:{_nud_fg_g};margin-top:10px;'>"
                                      f"{_nud_g[0]}</div>")

                _chips_g_bb = []
                if _kind == "proj":
                    _cat_of_proj = proj_to_cat.get(sel_grp)
                    if pd.notna(_cat_of_proj):
                        _chips_g_bb.append({"k": "Danh mục", "v": html_escape(str(_cat_of_proj))})
                else:
                    _chips_g_bb.append({"k": "Số dự án", "v": f"{df_g['Dự án'].nunique()}"})
                _chips_g_bb.append({"k": "TB / tuần (4 tuần)", "v": _fmt_hours_short(_tb_4w_hrs_g)})
                if len(_wk_hrs_g):
                    _best_wk_key_g = _wk_hrs_g.idxmax()
                    _chips_g_bb.append({"k": f"{_mi('emoji_events')} Tuần kỷ lục",
                                         "v": f"T{_best_wk_key_g.split('-W')[1]} · "
                                              f"{_fmt_hours_short(_wk_hrs_g.max()/60)}"})
                _chips_html_g = ''.join(
                    f"<span class='chip'><span class='ck'>{c['k']}</span><span class='cv'>{c['v']}</span></span>"
                    for c in _chips_g_bb)
                _right_html_g = (f"<div class='pbill-kicker'>{'DỰ ÁN' if _kind == 'proj' else 'NHÓM'}</div>"
                                  f"<div class='pbill-booktitle'>{html_escape(str(sel_grp))}{_status_html_g}</div>"
                                  f"<div class='pbill-chips'>{_chips_html_g}</div>{_nudge_html_g}")

                render_period_billboard(
                    "Hồ sơ dự án", _fmt_hours_short(curr_hrs_g), "tổng thời gian đã trồng",
                    f"{curr_trees_g} phiên",
                    _right_html_g,
                    [("bc-duan-ch1", "1 · Tổng quan")]
                    + ([("bc-duan-chrl", "Nhật ký đọc")] if not _rl_book.empty else [])
                    + [("bc-duan-ch2", "2 · Biểu đồ lịch"), ("bc-duan-ch3", "3 · Xu hướng"),
                       ("bc-duan-ch4", "4 · Phiên gần đây"), ("bc-duan-ch5", "5 · Bảng số liệu")])

                sec_chapter("bc-duan-ch1", 1, None, "Tổng quan", tight_top=True)
                wd_g = _weekday_avg(df_g)

                _grp_sections = [
                    {"label": "Trung bình", "chips": [
                        {"k": "Thời gian / ngày", "v": f"{_fmt_hours_short(curr_hrs_g/num_days_g)}"},
                        {"k": "Thời gian / tuần", "v": f"{_fmt_hours_short(curr_hrs_g/num_weeks_g)}"},
                        {"k": "Số cây / ngày", "v": f"{curr_trees_g/num_days_g:.1f}"},
                        {"k": "Số cây / tuần", "v": f"{curr_trees_g/num_weeks_g:.1f}"},
                        {"k": "Thời gian / phiên", "v": f"{_avg_session_min(df_g):.0f} phút"},
                    ]},
                ]

                df_g_thisweek = df_g[df_g['Tuần'] == _today_vn().strftime('%G-W%V')]
                if not df_g_thisweek.empty:
                    _grp_sections.append({"label": "Tuần này", "chips": [
                        {"k": "Thời gian", "v": f"{_fmt_hours_short(df_g_thisweek['Thời lượng (Phút)'].sum()/60)}", "hl": True},
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
                        {"k": "Mạnh nhất", "v": f"{wd_g.idxmax()} ({_fmt_hours_short(wd_g.max())})"},
                        {"k": "Yếu nhất", "v": f"{wd_g.idxmin()} ({_fmt_hours_short(wd_g.min())})"},
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
                        {"k": "#1", "v": f"{d:%d/%m/%Y} · {_fmt_hours_short(_rec_g['hours'])}"} for d in _rec_g['dates']
                    ]})

                render_stat_panel(
                    hero_items=[
                        {"label": "Số cây đã trồng", "value": f"{curr_trees_g}"},
                    ],
                    sections=_grp_sections,
                )
                # 2 thẻ "Theo buổi"/"Độ dài phiên" (trước ở chương riêng "Nhịp làm việc") dời lên
                # đây -- cùng chương Tổng quan, không còn là chương riêng (theo yêu cầu người dùng).
                render_project_rhythm(df_g)

                if not _rl_book.empty:
                    sec_chapter("bc-duan-chrl", None, None, "Nhật ký đọc")
                    with st.container(border=True, key="jcard_reading_proj"):
                        st.markdown(f"<div class='jrows'>{_reading_rows_html(_rl_book, label_book=False)}</div>",
                                    unsafe_allow_html=True)

                sec_chapter("bc-duan-ch2", 2, None, "Biểu đồ lịch")
                frag_calendar(df_g, "range_grp_cal")

                sec_chapter("bc-duan-ch3", 3, None, "Xu hướng")
                _duan_trend_view = st.segmented_control(
                    "Xem theo", ["12 tuần gần nhất", "Toàn thời gian"], default="12 tuần gần nhất",
                    key="bc_duan_trend_view", label_visibility="collapsed") or "12 tuần gần nhất"
                if _duan_trend_view == "12 tuần gần nhất":
                    render_project_week_trend(df_g)
                else:
                    frag_trend(df_g, "trend_grp", "Dự án")

                sec_chapter("bc-duan-ch4", 4, "30 ngày gần nhất", "Phiên gần đây")
                render_project_recent_sessions(df_g)
                sec_chapter("bc-duan-ch5", 5, None, "Bảng số liệu")
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
        # 10 ngày (không phải 14 mặc định) -- xác nhận với người dùng: sách ít hoạt động hơn
        # Gundam (đọc chậm hơn xem), 14 ngày để quá lâu mới chuyển "Đang đọc" -> "Đã xong".
        # CHỈ đổi riêng Sách, Gundam vẫn giữ mặc định 14 (không được yêu cầu đổi).
        render_reading_log(books_df, latest_overall, rl_books, recency_days=10)
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
        gundam_overrides = load_gundam_overrides()
        gundam_df = _assign_gundam_sessions(gundam_sessions, rl_gundam, gundam_overrides)
        _cands_g = [pd.Timestamp(v) for v in [gundam_df['Ngày'].max() if not gundam_df.empty else None,
                                               rl_gundam['Ngày hoàn thành'].max() if not rl_gundam.empty else None]
                    if v is not None and pd.notna(v)]
        latest_overall_g = max(_cands_g) if _cands_g else None
        render_reading_log(
            gundam_df, latest_overall_g, rl_gundam, labels=GUNDAM_LABELS, show_favorites=False,
            extra_overview=lambda: _render_gundam_series_override(
                gundam_sessions, rl_gundam, gundam_df, gundam_overrides))
# ==========================================
# TRANG: SỨC KHOẺ
# ==========================================
elif nav == "Sức khoẻ":
    render_health_page()
elif nav == "Tìm kiếm":
    render_search()
# ==========================================
# TAB TUỲ BIẾN
# ==========================================
elif nav == "Tuỳ biến":
    # Hero + 5 chương (chuyển từ 5 expander đánh số cũ, xác nhận với người dùng giữ NGUYÊN mọi
    # luồng nạp dữ liệu/xử lý bên trong, chỉ đổi vỏ ngoài theo mockup Forest Dashboard.dc.html).
    # Chương "5. Dữ liệu làm việc hiện tại" (bảng phiên thô + xoá hàng loạt) KHÔNG có trong mockup
    # (mockup chỉ vẽ 4 chương) -- xác nhận với người dùng giữ làm chương riêng thứ 5, đặt SAU
    # "4. Quản lý hệ thống" (xem cuối khối này).
    # Billboard (render_period_billboard(), KHÔNG phải sec_hero()) để khớp đúng style Hôm nay/Báo
    # cáo/Sách/Gundam đã chuyển trước đó -- sec_hero() là mẫu cũ hơn, thiếu khung "tờ lịch" số to
    # bên trái nên trông lệch tông so với phần còn lại của app đã đồng bộ hết sang billboard.
    _n_sessions_tb = len(load_db())
    _last_sync_tb = _cached_settings().get("last_quick_sync_at")
    _last_bk_tb = _cached_settings().get("last_backup_at")
    _tb_meta_parts = []
    if _last_sync_tb:
        _ls_dt_tb = pd.Timestamp(_last_sync_tb)
        _ls_label_tb = (f"hôm nay, {_ls_dt_tb:%H:%M}" if _ls_dt_tb.date() == _today_vn()
                         else f"{_ls_dt_tb:%d/%m/%Y, %H:%M}")
        _tb_meta_parts.append(f"Đồng bộ gần nhất {_ls_label_tb}")
    if _last_bk_tb:
        _tb_meta_parts.append(f"Sao lưu gần nhất {pd.Timestamp(_last_bk_tb):%d/%m/%Y}")
    _tb_meta = " · ".join(_tb_meta_parts) if _tb_meta_parts else "Chưa đồng bộ/sao lưu lần nào"
    render_period_billboard(
        "Tuỳ biến", str(_n_sessions_tb), "phiên trong hệ thống", _tb_meta,
        "<div class='pbill-title'>Dữ liệu &amp; giao diện của bạn</div>"
        "<div class='pbill-sub'>Nạp dữ liệu, gán phân loại, chỉnh màu sắc hoạ tiết và sao lưu — "
        "tất cả ở một nơi.</div>",
        [("tb-ch1", "1 · Dữ liệu đầu vào"), ("tb-ch2", "2 · Phân loại"),
         ("tb-ch3", "3 · Giao diện"), ("tb-ch4", "4 · Quản lý hệ thống"),
         ("tb-ch5", "5 · Dữ liệu làm việc hiện tại")],
        key="tb_billboard")

    sec_chapter("tb-ch1", 1, None, "Dữ liệu đầu vào", tight_top=True)
    with st.container(border=True, key="tb_quick_sync_card"):
        _qmsg = st.session_state.pop('quick_sync_msg', None)
        if _qmsg:
            (st.success if not st.session_state.pop('quick_sync_has_error', False) else st.warning)(_qmsg)
        _qfiles = _list_sync_files()
        _qf = _latest_sync_file(_qfiles, "forest")
        _qr = _latest_sync_file(_qfiles, "reminder")
        _last_sync_raw = _cached_settings().get("last_quick_sync_at")
        _last_sync_summary = _cached_settings().get("last_quick_sync_summary")
        if _last_sync_raw:
            _ls_dt = pd.Timestamp(_last_sync_raw)
            _ls_label = (f"hôm nay, {_ls_dt:%H:%M}" if _ls_dt.date() == _today_vn()
                         else f"{_ls_dt:%d/%m/%Y, %H:%M}")
            _qsub = f"Lần gần nhất: {_ls_label}" + (f" · {_last_sync_summary}" if _last_sync_summary else "")
        else:
            _qsub = "Chưa đồng bộ lần nào."
        # Chữ trái + nút phải trên CÙNG 1 hàng (khớp mockup) -- st.columns() mặc định
        # align-items:stretch nên 2 cột cao bằng nhau nhưng nội dung neo TRÊN; ép align-items:center
        # qua CSS descendant selector (KHÔNG dùng ">") để nút "Đồng bộ ngay" canh giữa theo chiều dọc
        # với khối chữ 2 dòng bên trái dù cao hơn 1 dòng của nút.
        st.markdown(
            "<style>.st-key-tb_quick_sync_row [data-testid=\"stHorizontalBlock\"] "
            "{ align-items: center; }</style>", unsafe_allow_html=True)
        with st.container(key="tb_quick_sync_row"):
            qc1, qc2 = st.columns([3, 1])
            with qc1:
                st.markdown(
                    f"<div style='font-size:14.5px;font-weight:700;color:var(--text);'>"
                    f"Đồng bộ nhanh từ Forest</div>"
                    f"<div style='font-size:13px;color:var(--text-2);margin-top:2px;'>{_qsub}</div>",
                    unsafe_allow_html=True)
            with qc2:
                _qclicked = st.button("Đồng bộ ngay", type="primary", key="tbtn_quick_sync",
                                      disabled=not (_qf or _qr), use_container_width=True)
        if _qclicked:
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
                save_setting("last_quick_sync_at", datetime.now(APP_TZ).strftime('%Y-%m-%d %H:%M:%S'))
                save_setting("last_quick_sync_summary", ", ".join(_parts) if _parts else "không có gì mới")
                st.session_state['quick_sync_msg'] = "Đã đồng bộ: " + ", ".join(_parts) + "." if _parts else "Không có file mới để đồng bộ."
                st.session_state['quick_sync_has_error'] = _has_err
            st.rerun()

        with st.expander("Dự phòng", expanded=False):
            _tab_forest, _tab_cal, _tab_rem, _tab_kindle = st.tabs(
                ["Tải lên từ Forest", "Đồng bộ lịch", "Tải lên từ Reminder", "Tải trích dẫn Kindle"])
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
                            if st.button("Xác nhận cập nhật dữ liệu", type="primary", key="tbtn_import_confirm"):
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
                # 1 bộ preset + tuỳ chọn "Khoảng khác…" ngay trong cùng hàng (không tách expander
                # "nâng cao" riêng nữa) -- trước đây có 2 bộ điều khiển + 2 nút "Đồng bộ ngay" cho
                # cùng 1 hàm sync_work_calendar(), giờ chỉ còn 1 nút duy nhất.
                _wc_presets = {"-30 / +30 ngày": 30, "-90 / +90 ngày": 90, "-180 / +180 ngày": 180}
                sync_range = st.segmented_control(
                    "Khoảng đồng bộ", list(_wc_presets.keys()) + ["Khoảng khác…"],
                    default="-90 / +90 ngày", key="wc_range", label_visibility="collapsed") or "-90 / +90 ngày"
                if sync_range == "Khoảng khác…":
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        _adv_start = st.date_input("Từ ngày", value=_today_vn() - timedelta(days=365 * 2), key="wc_adv_start")
                    with dc2:
                        _adv_end = st.date_input("Đến ngày", value=_today_vn(), key="wc_adv_end")
                if st.button("Đồng bộ ngay", type="primary", key="tbtn_wc_sync"):
                    if sync_range == "Khoảng khác…":
                        _start, _end = _adv_start, _adv_end
                        _valid = _start < _end
                        if not _valid:
                            st.error("Từ ngày phải trước Đến ngày.")
                    else:
                        _days = _wc_presets[sync_range]
                        _start = _today_vn() - timedelta(days=_days)
                        _end = _today_vn() + timedelta(days=_days)
                        _valid = True
                    if _valid:
                        with st.spinner("Đang kết nối iCloud..."):
                            _n, _err = sync_work_calendar(_start, _end)
                        if _err:
                            st.error(_err)
                        else:
                            st.success(f"Đã đồng bộ {_n} appointment (từ {_start:%d/%m/%Y} đến {_end:%d/%m/%Y}).")
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
                        if st.button("Xác nhận nạp dữ liệu", type="primary", key="tbtn_rl_confirm"):
                            save_reading_log_bulk(rl_df)
                            st.success(f"Đã nạp {rl_df['Sách (gốc)'].nunique()} cuốn sách, {len(rl_df)} phần đã đọc.")
                            time.sleep(1)
                            st.rerun()

            with _tab_kindle:
                _kmsg = st.session_state.pop('kindle_import_msg', None)
                if _kmsg:
                    st.success(_kmsg)
                kindle_file = st.file_uploader("Tải lên My Clippings.txt", type=["txt"], key="kindle_file")
                if kindle_file:
                    k_df, k_stats = parse_kindle_clippings(kindle_file.read())
                    if k_df.empty:
                        st.warning("Không đọc được trích dẫn/ghi chú hợp lệ nào trong file.")
                    else:
                        _extra_parts = []
                        if k_stats['bookmarks']:
                            _extra_parts.append(f"{k_stats['bookmarks']} bookmark không có nội dung")
                        if k_stats['invalid']:
                            _extra_parts.append(f"{k_stats['invalid']} dòng không nhận dạng được")
                        if k_stats['pen_merged']:
                            _extra_parts.append(f"{k_stats['pen_merged']} bản nháp bút cảm ứng đã gộp lại")
                        _extra = f" (bỏ {', '.join(_extra_parts)})" if _extra_parts else ""
                        st.caption(f"Đọc được **{k_stats['valid']}** trích dẫn/ghi chú hợp lệ từ "
                                   f"**{k_df['Tên Kindle'].nunique()}** cuốn/nguồn{_extra}. Xem trước:")
                        _kprev = k_df.head(8).copy()
                        _kprev['Nội dung'] = _kprev['Nội dung'].apply(lambda s: s if len(s) <= 120 else s[:120] + '…')
                        _kprev['Ngày thêm'] = _kprev['Ngày thêm'].apply(
                            lambda d: d.strftime('%Y-%m-%d %H:%M') if pd.notna(d) else '—')
                        st.dataframe(_kprev, width='stretch', hide_index=True)

                        existing_map = load_kindle_book_map()
                        known_titles = set(existing_map["Tên Kindle"]) if not existing_map.empty else set()
                        new_titles = sorted(t for t in k_df["Tên Kindle"].unique() if t not in known_titles)

                        db_all = load_db()
                        projects = sorted(db_all['Dự án'].dropna().astype(str).unique()) if not db_all.empty else []
                        _INDEP = "— Nguồn độc lập (không phải Dự án) —"

                        _confirm_edited = pd.DataFrame(columns=["Tên Kindle", "Ghép với Dự án", "Nhãn hiển thị (nếu độc lập)"])
                        if new_titles:
                            st.markdown(
                                f"**{len(new_titles)} cuốn/nguồn mới** cần xác nhận trước khi lưu — ghép với 1 "
                                f"Dự án đã có, hoặc để nguyên \"{_INDEP}\" và tự đặt tên hiển thị (vd tạp chí đọc "
                                "định kỳ). Các cuốn/nguồn đã từng xác nhận trước đây tự động dùng lại, không hỏi lại.")
                            _sugg = {t: (_fuzzy_match_project(t, projects) or _INDEP) for t in new_titles}
                            _confirm_tbl = pd.DataFrame({
                                "Tên Kindle": new_titles,
                                "Ghép với Dự án": [_sugg[t] for t in new_titles],
                                "Nhãn hiển thị (nếu độc lập)": new_titles,
                            })
                            _confirm_edited = st.data_editor(
                                _confirm_tbl, hide_index=True, width='stretch', key="kindle_map_editor",
                                column_config={
                                    "Tên Kindle": st.column_config.TextColumn("Tên Kindle", disabled=True),
                                    "Ghép với Dự án": st.column_config.SelectboxColumn(
                                        "Ghép với Dự án", options=[_INDEP] + projects,
                                        help="Chọn đúng Dự án nếu đây là 1 cuốn sách bạn đang theo dõi; để "
                                             f"nguyên \"{_INDEP}\" nếu không (vd tạp chí)."),
                                    "Nhãn hiển thị (nếu độc lập)": st.column_config.TextColumn(
                                        "Nhãn hiển thị (nếu độc lập)",
                                        help="Chỉ dùng khi để \"Nguồn độc lập\" — tên sẽ hiện trong app."),
                                },
                            )
                        else:
                            st.caption("Mọi cuốn/nguồn trong file này đã từng được ghép từ trước.")

                        if st.button("Xác nhận nạp dữ liệu Kindle", type="primary", key="tbtn_kindle_confirm"):
                            if not _confirm_edited.empty:
                                _is_indep = _confirm_edited["Ghép với Dự án"] == _INDEP
                                _map_rows = pd.DataFrame({
                                    "Tên Kindle": _confirm_edited["Tên Kindle"],
                                    "Dự án": _confirm_edited["Ghép với Dự án"].where(~_is_indep, None),
                                    "Nhãn": _confirm_edited["Nhãn hiển thị (nếu độc lập)"].where(
                                        _is_indep, _confirm_edited["Ghép với Dự án"]),
                                })
                                save_kindle_book_map_upsert(_map_rows)
                            # existing_hashes ĐỌC THẲNG cột dedupe_hash đã lưu (KHÔNG tính lại từ
                            # Tên Kindle/Vị trí/Nội dung hiện có) -- 1 dòng đã bị Sửa trong app có
                            # nội dung khác bản gốc trong file, tính lại hash sẽ ra kết quả khác
                            # với khoá thật đang lưu, làm sai lệch số liệu "trùng"/"mới" bên dưới
                            # (xem chú thích trong load_kindle_highlights()).
                            existing_kh = load_kindle_highlights()
                            existing_hashes = set(existing_kh['dedupe_hash']) if not existing_kh.empty else set()
                            deleted_hashes = set(load_deleted_kindle()['dedupe_hash'])
                            new_hashes = k_df.apply(
                                lambda r: _kindle_dedupe_hash(r["Tên Kindle"], r["Vị trí"], r["Nội dung"]), axis=1)
                            n_skipped_deleted = int(new_hashes.isin(deleted_hashes).sum())
                            k_df_import = k_df[~new_hashes.isin(deleted_hashes)]
                            _import_hashes = new_hashes[~new_hashes.isin(deleted_hashes)]
                            n_new = int((~_import_hashes.isin(existing_hashes)).sum())
                            n_dup = len(k_df_import) - n_new
                            save_kindle_highlights_bulk(k_df_import)
                            _msg = f"Đã thêm {n_new} trích dẫn/ghi chú mới (bỏ {n_dup} trùng đã có từ trước"
                            _msg += f", {n_skipped_deleted} đã xoá trước đó" if n_skipped_deleted else ""
                            st.session_state['kindle_import_msg'] = _msg + ")."
                            st.rerun()

                # Sửa lại ánh xạ ĐÃ xác nhận trước đây -- lần xác nhận lúc import chỉ hỏi 1 LẦN
                # DUY NHẤT cho mỗi tên sách mới gặp (xem "known_titles" ở trên), không có đường
                # quay lại sửa nếu lỡ ghép nhầm Dự án, hoặc nếu 1 nguồn từng để "Nguồn độc lập"
                # nay mới thực sự bắt đầu theo dõi tiến độ đọc qua Reminders. Luôn hiện (không phụ
                # thuộc có vừa tải file mới hay không) để sửa được bất cứ lúc nào.
                _kmap_all = load_kindle_book_map()
                if not _kmap_all.empty:
                    st.markdown("---")
                    _kmap_msg = st.session_state.pop('kindle_map_save_msg', None)
                    if _kmap_msg:
                        st.success(_kmap_msg)
                    st.markdown(f"**Ánh xạ đã lưu ({len(_kmap_all)} cuốn/nguồn)** — sửa lại nếu lỡ ghép nhầm "
                                "Dự án lúc xác nhận, hoặc 1 nguồn từng để độc lập nay đã bắt đầu theo dõi tiến "
                                "độ đọc thật qua Reminders.")
                    _db_kmap = load_db()
                    _projs_kmap = sorted(_db_kmap['Dự án'].dropna().astype(str).unique()) if not _db_kmap.empty else []
                    _INDEP_KMAP = "— Nguồn độc lập (không phải Dự án) —"
                    _kmap_tbl = _kmap_all.copy()
                    _kmap_tbl["Dự án"] = _kmap_tbl["Dự án"].fillna(_INDEP_KMAP)
                    _kmap_edited = st.data_editor(
                        _kmap_tbl, hide_index=True, width='stretch', key="kindle_map_edit_existing",
                        column_config={
                            "Tên Kindle": st.column_config.TextColumn("Tên Kindle", disabled=True),
                            "Dự án": st.column_config.SelectboxColumn(
                                "Dự án", options=[_INDEP_KMAP] + _projs_kmap,
                                help="Chọn đúng Dự án nếu đây là 1 cuốn sách bạn đang theo dõi; để nguyên "
                                     f"\"{_INDEP_KMAP}\" nếu không (vd tạp chí)."),
                            "Nhãn": st.column_config.TextColumn(
                                "Nhãn hiển thị (nếu độc lập)",
                                help="Chỉ dùng khi để \"Nguồn độc lập\" — tên sẽ hiện trong app."),
                        },
                    )
                    if st.button("Lưu thay đổi ánh xạ", key="tbtn_kindle_map_save"):
                        _is_indep_kmap = _kmap_edited["Dự án"] == _INDEP_KMAP
                        _kmap_save = pd.DataFrame({
                            "Tên Kindle": _kmap_edited["Tên Kindle"],
                            "Dự án": _kmap_edited["Dự án"].where(~_is_indep_kmap, None),
                            "Nhãn": _kmap_edited["Nhãn"].where(_is_indep_kmap, _kmap_edited["Dự án"]),
                        })
                        save_kindle_book_map_upsert(_kmap_save)
                        st.session_state['kindle_map_save_msg'] = "Đã lưu ánh xạ mới."
                        st.rerun()

    sec_chapter("tb-ch2", 2, None, "Phân loại")
    with st.container(border=True, key="tb_mapping_card"):
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

            # Bảng TĨNH (badge màu Danh mục, khớp mockup) -- data_editor cũ không vẽ được badge
            # màu trong ô (SelectboxColumn chỉ nhận text đơn thuần), nên sửa chuyển xuống form
            # riêng bên dưới bảng (xem "Sửa phân loại"). Sắp theo số phiên giảm dần, cắt bớt nếu
            # danh sách dài (khớp mockup "+N dự án khác") -- form sửa vẫn chọn được MỌI dự án qua
            # selectbox riêng, không phụ thuộc dự án đó có đang hiện trong bảng hay không.
            _proj_sessions = db_current['Dự án'].astype(str).value_counts()
            _cat_colors = build_color_map(existing_cats) if existing_cats else {}
            _rows_sorted = sorted(all_projs, key=lambda p: -_proj_sessions.get(p, 0))
            _MAP_SHOW = 8
            _show_rows = _rows_sorted[:_MAP_SHOW]
            _extra_n = len(_rows_sorted) - len(_show_rows)

            _rows_html = "<div class='maprow maprow-head'><span>Dự án</span><span>Danh mục</span><span style='text-align:right;'>Phiên</span></div>"
            for p in _show_rows:
                _cat = cur_map.get(p)
                _cat = str(_cat) if pd.notna(_cat) and str(_cat).strip() else None
                if _cat:
                    _dot = _cat_colors.get(_cat, "var(--accent)")
                    _badge = (f"<span class='chip' style='display:inline-flex;align-items:center;'>"
                              f"<i style='display:inline-block;width:9px;height:9px;border-radius:3px;"
                              f"margin-right:6px;background:{_dot};'></i>{html_escape(_cat)}</span>")
                else:
                    _badge = "<span style='color:var(--text-2);font-size:12.5px;'>— chưa phân loại —</span>"
                _n = int(_proj_sessions.get(p, 0))
                _rows_html += (f"<div class='maprow'><span class='mp-proj'>{html_escape(p)}</span>"
                               f"<span class='mp-cat'>{_badge}</span>"
                               f"<span class='mp-n'>{_n}</span></div>")
            if _extra_n > 0:
                _rows_html += f"<div class='maprow maprow-extra'>+ {_extra_n} dự án khác · sửa phân loại bên dưới</div>"
            st.markdown(f"<div class='maptbl'>{_rows_html}</div>", unsafe_allow_html=True)

            st.markdown("<div style='margin-top:16px;font-size:13px;font-weight:600;"
                        "color:var(--text-2);'>Sửa phân loại</div>", unsafe_allow_html=True)
            new_cat = st.text_input("Tạo nhóm mới:").strip()
            opts = sorted(set(existing_cats) | ({new_cat} if new_cat else set()))
            fc1, fc2, fc3 = st.columns([2, 2, 1])
            with fc1:
                edit_proj = st.selectbox("Dự án", all_projs, key="map_edit_proj")
            with fc2:
                _cur_val = cur_map.get(edit_proj)
                _cur_idx = opts.index(_cur_val) if _cur_val in opts else None
                edit_cat = st.selectbox("Danh mục", opts, index=_cur_idx, key="map_edit_cat",
                                        placeholder="— Chọn danh mục —")
            with fc3:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                if st.button("Lưu", type="primary", key="tbtn_save_mapping", use_container_width=True):
                    if edit_cat:
                        nm = (mapping_df[mapping_df['Dự án'].astype(str) != edit_proj]
                              if not mapping_df.empty else pd.DataFrame(columns=["Dự án", "Danh mục"]))
                        nm = pd.concat([nm, pd.DataFrame([{"Dự án": edit_proj, "Danh mục": edit_cat}])],
                                       ignore_index=True)
                        save_mapping(nm[["Dự án", "Danh mục"]].reset_index(drop=True))
                        st.rerun()
    sec_chapter("tb-ch3", 3, None, "Giao diện")
    with st.container(border=True, key="tb_theme_card"):
        st.markdown("<div style='font-size:15px;font-weight:700;text-transform:uppercase;"
                    "letter-spacing:0.5px;color:var(--text);margin-bottom:14px;'>"
                    "Màu accent</div>", unsafe_allow_html=True)
        _preset_items = list(ACCENT_PRESETS.items())
        _per_row = 4  # 8 màu / 4 mỗi hàng -> đúng 2 hàng đều, không lẻ hàng cuối như 5/hàng cũ
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
                # chói nền (_readable_text) để luôn đọc rõ với 6 màu khác nhau.
                _swatch_css += (
                    f".st-key-{_key} div[data-testid=\"stButton\"] button[kind=\"secondary\"] {{ "
                    f"background:{_hex} !important; color:{_txt_color} !important; "
                    f"border:2px solid {_border} !important; border-radius:10px !important; "
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

        st.markdown("<div style='margin-top:2px;font-size:15px;font-weight:700;text-transform:uppercase;"
                    "letter-spacing:0.5px;color:var(--text);margin-bottom:14px;'>"
                    "Kiểu nền trang</div>", unsafe_allow_html=True)
        _bg_items = list(BG_PRESETS.items())
        _bg_per_row = 4  # 8 kiểu / 4 mỗi hàng -> đúng 2 hàng đều, khớp bố cục màu accent ở trên
        _bg_css = "<style>"
        for _bg_row_start in range(0, len(_bg_items), _bg_per_row):
            _bg_row_items = _bg_items[_bg_row_start:_bg_row_start + _bg_per_row]
            _bg_cols = st.columns(_bg_per_row)
            for _bg_i, (_bg_name, _bg_cfg) in enumerate(_bg_row_items):
                _idx = _bg_row_start + _bg_i
                _bg_key = f"bg_sw_{_idx}"
                _bg_selected = _bg_name == BG_STYLE
                _bg_border = "var(--accent)" if _bg_selected else "var(--border)"
                _bg_label = f"✓ {_bg_name}" if _bg_selected else _bg_name
                _bg_position = _bg_cfg.get("position", "0 0")
                # Nút xem trước dùng ĐÚNG background-image/size/position của preset (không phải
                # màu đặc như accent) -- người dùng thấy được hoạ tiết thật trước khi chọn.
                _bg_css += (
                    f".st-key-{_bg_key} div[data-testid=\"stButton\"] button[kind=\"secondary\"] {{ "
                    f"background-color: var(--card-tl) !important; "
                    f"background-image: {_bg_cfg['image']} !important; background-size: {_bg_cfg['size']} !important; "
                    f"background-position: {_bg_position} !important; "
                    f"color: var(--text) !important; border:2px solid {_bg_border} !important; "
                    f"border-radius:10px !important; width:100% !important; height:auto !important; "
                    f"min-height:64px !important; padding:8px 6px !important; font-weight:600 !important; "
                    f"font-size:12.5px !important; white-space:normal !important; line-height:1.25 !important; }}")
                with _bg_cols[_bg_i]:
                    if st.button(_bg_label, key=_bg_key, use_container_width=True):
                        if _bg_name != BG_STYLE:
                            save_setting("bg_style", _bg_name)
                            st.rerun()
        _bg_css += "</style>"
        st.markdown(_bg_css, unsafe_allow_html=True)

    sec_chapter("tb-ch4", 4, None, "Quản lý hệ thống")
    # 3 thẻ rút gọn về ĐÚNG 1 nhãn + 1 nút (không còn help text/checkbox lộ ngay trên thẻ, theo
    # phản hồi thực tế) -- 2 thao tác phá huỷ dữ liệu (Khôi phục ghi đè toàn bộ, Làm mới xoá sạch
    # toàn bộ) chuyển hết phần xác nhận (upload/preview/checkbox/nút xác nhận cuối) vào popup
    # riêng qua st.dialog(), nút trên thẻ chỉ có nhiệm vụ MỞ popup đó. Sao lưu không phá huỷ gì
    # nên giữ nguyên 1 nút tải trực tiếp, không cần popup.
    @st.dialog("Khôi phục dữ liệu")
    def _tb_restore_dialog():
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
                    if HEALTH_METRICS_FILE in names:
                        parts.append(f"Sức khoẻ **{len(pd.read_csv(io.BytesIO(_z.read(HEALTH_METRICS_FILE))))}** chỉ số")
                    if KINDLE_HIGHLIGHTS_FILE in names:
                        parts.append(f"Kindle **{len(pd.read_csv(io.BytesIO(_z.read(KINDLE_HIGHLIGHTS_FILE))))}** trích dẫn/ghi chú")
                    if DELETED_KINDLE_FILE in names:
                        parts.append(f"Kindle đã xoá **{len(pd.read_csv(io.BytesIO(_z.read(DELETED_KINDLE_FILE))))}** mục")
                    if GUNDAM_OVERRIDES_FILE in names:
                        parts.append(f"Gundam gán tay **{len(pd.read_csv(io.BytesIO(_z.read(GUNDAM_OVERRIDES_FILE))))}** ngày")
                if parts:
                    ok_zip = True
                    st.caption("Bản sao lưu gồm — " + " · ".join(parts) + ".")
                else:
                    st.caption("File .zip không chứa dữ liệu hợp lệ.")
            except Exception:
                st.caption("Không đọc được file — cần đúng bản .zip xuất từ app.")
        confirm_restore = False
        if ok_zip:
            st.warning("Khôi phục sẽ **ghi đè** toàn bộ dữ liệu hiện tại bằng nội dung bản sao lưu.")
            confirm_restore = st.checkbox("Tôi xác nhận muốn ghi đè toàn bộ dữ liệu hiện tại",
                                           key="cb_restore_confirm")
        if st.button("Xác nhận Khôi phục", type="primary", disabled=not (ok_zip and confirm_restore),
                     key="tbtn_restore_confirm"):
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
                if HEALTH_METRICS_FILE in names:
                    # KHÔNG dtype=str -- khác các bảng trên, bảng này có cột số thực (Giá trị/Ref thấp/Ref
                    # cao) cần pandas tự suy kiểu để pd.isna() nhận diện đúng ô trống.
                    save_health_metrics_raw_bulk(pd.read_csv(io.BytesIO(_z.read(HEALTH_METRICS_FILE))))
                # kindle_book_map/kindle_highlights dùng save_*upsert() (CỘNG DỒN, khác save_db()
                # kiểu xoá-sạch-rồi-chèn) -- Khôi phục cần đúng ngữ nghĩa "ghi đè toàn bộ" nên xoá
                # sạch 2 bảng trước, RỒI mới upsert nội dung từ file .zip vào, thay vì gọi thẳng.
                if KINDLE_BOOK_MAP_FILE in names or KINDLE_HIGHLIGHTS_FILE in names:
                    _sb_delete_all("kindle_highlights", "dedupe_hash")
                    _sb_delete_all("kindle_book_map", "kindle_title")
                if KINDLE_BOOK_MAP_FILE in names:
                    save_kindle_book_map_upsert(pd.read_csv(io.BytesIO(_z.read(KINDLE_BOOK_MAP_FILE)), dtype=str))
                if KINDLE_HIGHLIGHTS_FILE in names:
                    # save_kindle_highlights_RAW_bulk (KHÔNG phải _bulk thường) -- giữ nguyên
                    # đúng dedupe_hash/parent_hash đã lưu, không tính lại từ nội dung (nội
                    # dung có thể đã bị Sửa khác bản gốc lúc băm, xem docstring hàm đó).
                    save_kindle_highlights_raw_bulk(pd.read_csv(io.BytesIO(_z.read(KINDLE_HIGHLIGHTS_FILE)), dtype=str))
                if DELETED_KINDLE_FILE in names:
                    save_deleted_kindle(pd.read_csv(io.BytesIO(_z.read(DELETED_KINDLE_FILE)), dtype=str))
                if GUNDAM_OVERRIDES_FILE in names:
                    save_gundam_overrides_bulk(pd.read_csv(io.BytesIO(_z.read(GUNDAM_OVERRIDES_FILE)), dtype=str))
            st.cache_data.clear()
            st.success("Khôi phục hệ thống thành công!")
            time.sleep(1)
            st.rerun()

    @st.dialog("Xoá toàn bộ dữ liệu")
    def _tb_wipe_dialog():
        st.warning("Thao tác này **xoá vĩnh viễn** toàn bộ dữ liệu trên hệ thống, không thể hoàn tác.")
        confirm_delete = st.checkbox("Tôi xác nhận muốn xoá toàn bộ dữ liệu", key="cb_wipe_confirm")
        if st.button("Xoá toàn bộ dữ liệu", type="primary", disabled=not confirm_delete, key="tbtn_wipe_all"):
            _sb_delete_all("sessions", "id")
            _sb_delete_all("mapping", "project")
            _sb_delete_all("deleted_sessions", "start_time")
            _sb_delete_all("notes", "note_date")
            _sb_delete_all("quick_notes", "id")
            _sb_delete_all("work_calendar", "uid")
            _sb_delete_all("reading_log", "uid")
            _sb_delete_all("settings", "key")
            _sb_delete_all("health_metrics", "id")
            _sb_delete_all("kindle_highlights", "dedupe_hash")
            _sb_delete_all("kindle_book_map", "kindle_title")
            _sb_delete_all("deleted_kindle_highlights", "dedupe_hash")
            _sb_delete_all("gundam_overrides", "session_date")
            st.cache_data.clear()
            st.success("Đã xoá toàn bộ dữ liệu!")
            time.sleep(1)
            st.rerun()

    # 3 thẻ cao KHÔNG bằng nhau mặc định -- rule chung [data-testid="stHorizontalBlock"]
    # { align-items: flex-start !important; } (nơi khác trong file) khiến mỗi cột co theo đúng
    # chiều cao nội dung riêng. :has() chọn ĐÚNG hàng chứa 3 thẻ này (không cần bọc thêm
    # st.container(key=...) ngoài, tránh phải thụt lề lại cả khối) rồi ép stretch + 3 thẻ
    # height:100% để cao bằng nhau dù nhãn/nút dài ngắn khác nhau.
    st.markdown(
        "<style>"
        "[data-testid=\"stHorizontalBlock\"]:has([class*=\"st-key-tb_backup_card\"]) "
        "{ align-items: stretch !important; }"
        ".st-key-tb_backup_card, .st-key-tb_restore_card, .st-key-tb_wipe_card, "
        ".st-key-tb_account_card { height: 100%; }"
        # Nút phá huỷ dữ liệu (xoá sạch/ghi đè toàn bộ, giờ nằm trong popup st.dialog()) dùng màu
        # cảnh báo riêng (đỏ #ff3b30, cùng tông đỏ dùng cho delta âm/chỉ số bất thường trong app)
        # thay vì màu nút thường -- tín hiệu thị giác phân biệt mức độ nguy hiểm. key vẫn giữ
        # nguyên (tbtn_wipe_all/tbtn_restore_confirm) dù đổi chỗ vào dialog, CSS này không cần đổi.
        ".st-key-tbtn_wipe_all div[data-testid=\"stButton\"] button[kind=\"primary\"],"
        ".st-key-tbtn_restore_confirm div[data-testid=\"stButton\"] button[kind=\"primary\"] {"
        "background-color:#ff3b30 !important;color:#fff !important;"
        "border-color:#ff3b30 !important;box-shadow:none !important;}"
        # Nút 4 thẻ Sao lưu/Khôi phục/Làm mới/Tài khoản: nhỏ gọn, KHÔNG full-width (khớp mockup --
        # nút chỉ rộng vừa chữ, neo trái dưới nhãn+help text, không kéo hết bề ngang thẻ).
        ".st-key-tb_backup_card div[data-testid=\"stButton\"] button,"
        ".st-key-tb_restore_card div[data-testid=\"stButton\"] button,"
        ".st-key-tb_wipe_card div[data-testid=\"stButton\"] button,"
        ".st-key-tb_account_card div[data-testid=\"stButton\"] button {"
        "padding:5px 14px !important;font-size:13px !important;border-radius:7px !important;"
        "font-weight:500 !important;min-height:auto !important;}"
        "</style>", unsafe_allow_html=True)
    # Thẻ "Tài khoản" (Đăng nhập với .../Đăng xuất) chỉ thêm khi có cấu hình đăng nhập Google
    # (_auth_configured) -- xếp CÙNG hàng 1x4 với 3 thẻ kia (không phải khối riêng dưới divider
    # như bản trước) để đồng nhất khuôn nhãn+help text+nút, theo lựa chọn của người dùng. Thẻ
    # Tài khoản rộng hơn 3 thẻ kia (tỉ lệ 1:1:1:2, không chia đều 1:1:1:1) -- help text của nó là
    # "Đăng nhập với <email>" luôn dài hơn hẳn 3 câu help text kia (vd "Chưa sao lưu lần nào."),
    # chia đều 4 cột sẽ xuống 2 dòng và làm thẻ này CAO HƠN 3 thẻ còn lại dù đã ép height:100%.
    _sysmgmt_cols = st.columns([1, 1, 1, 2] if _auth_configured else [1, 1, 1])
    c1, c2, c3 = _sysmgmt_cols[:3]
    _today = _today_vn().strftime('%Y-%m-%d')
    _sysrow_label_css = "font-size:15px;font-weight:700;color:var(--text);margin-bottom:6px;"
    _sysrow_help_css = "font-size:13px;color:var(--text-2);margin-bottom:10px;"
    with c1:
        with st.container(border=True, key="tb_backup_card"):
            _last_bk = _cached_settings().get("last_backup_at")
            _bk_help = (f"Lần gần nhất: {pd.Timestamp(_last_bk):%d/%m/%Y}" if _last_bk
                        else "Chưa sao lưu lần nào.")
            st.markdown(f"<div style='{_sysrow_label_css}'>Sao lưu</div>"
                        f"<div style='{_sysrow_help_css}'>{_bk_help}</div>", unsafe_allow_html=True)
            db_now = load_db()
            _buf = io.BytesIO()
            if not db_now.empty:
                with zipfile.ZipFile(_buf, "w", zipfile.ZIP_DEFLATED) as _z:
                    _settings_df = pd.DataFrame(list(load_settings().items()), columns=["key", "value"])
                    for _fn, _df in [(DB_FILE, db_now), (MAPPING_FILE, load_mapping()),
                                      (DELETED_FILE, load_deleted()), (NOTES_FILE, load_notes()),
                                      (QUICK_NOTES_FILE, load_quick_notes()),
                                      (WORK_CALENDAR_FILE, load_work_calendar()),
                                      (READING_LOG_FILE, load_reading_log()),
                                      (SETTINGS_FILE, _settings_df),
                                      (HEALTH_METRICS_FILE, load_health_metrics()),
                                      (KINDLE_HIGHLIGHTS_FILE, load_kindle_highlights()),
                                      (KINDLE_BOOK_MAP_FILE, load_kindle_book_map()),
                                      (DELETED_KINDLE_FILE, load_deleted_kindle()),
                                      (GUNDAM_OVERRIDES_FILE, pd.DataFrame(
                                          [{"Ngày": k, "Series": v} for k, v in load_gundam_overrides().items()]))]:
                        if not _df.empty:
                            _z.writestr(os.path.basename(_fn), _df.to_csv(index=False))
            st.download_button("Tải bản sao lưu", _buf.getvalue(),
                               f"forest_backup_{_today}.zip", "application/zip", key="tbtn_download_backup",
                               disabled=db_now.empty,
                               on_click=lambda: save_setting("last_backup_at", _today))
    with c2:
        with st.container(border=True, key="tb_restore_card"):
            st.markdown(f"<div style='{_sysrow_label_css}'>Khôi phục</div>"
                        f"<div style='{_sysrow_help_css}'>Tải lên bản sao lưu (.zip)</div>",
                        unsafe_allow_html=True)
            if st.button("Khôi phục", key="tbtn_restore_open"):
                _tb_restore_dialog()
    with c3:
        with st.container(border=True, key="tb_wipe_card"):
            # Help text NGẮN hơn "Xoá toàn bộ dữ liệu — cần xác nhận" (bản trước) -- cột hẹp lại
            # (tỉ lệ [1,1,1,2] để nhường chỗ cho thẻ Tài khoản) khiến câu dài xuống 2 dòng, làm
            # thẻ này cao hơn 3 thẻ còn lại dù đã ép height:100%.
            st.markdown(f"<div style='{_sysrow_label_css}'>Làm mới</div>"
                        f"<div style='{_sysrow_help_css}'>Không thể hoàn tác.</div>",
                        unsafe_allow_html=True)
            if st.button("Xoá toàn bộ dữ liệu", key="tbtn_wipe_open"):
                _tb_wipe_dialog()
    if _auth_configured:
        with _sysmgmt_cols[3]:
            with st.container(border=True, key="tb_account_card"):
                st.markdown(f"<div style='{_sysrow_label_css}'>Tài khoản</div>"
                            f"<div style='{_sysrow_help_css}'>Đăng nhập với {html_escape(st.user.email)}</div>",
                            unsafe_allow_html=True)
                st.button("Đăng xuất", icon=":material/logout:", on_click=st.logout, key="tbtn_logout")

    # Chương "5. Dữ liệu làm việc hiện tại" -- KHÔNG có trong mockup (chỉ vẽ 4 chương), xác nhận
    # với người dùng giữ làm chương riêng cuối cùng thay vì gộp vào "1. Dữ liệu đầu vào" (xem
    # đầu khối "elif nav == "Tuỳ biến":").
    sec_chapter("tb-ch5", 5, None, "Dữ liệu làm việc hiện tại")
    with st.container(border=True, key="tb_rawdata_card"):
        # Nút xoá hàng loạt cũng dùng màu cảnh báo -- xem chú thích ở "4. Quản lý hệ thống".
        st.markdown(
            "<style>.st-key-tbtn_delete_selected div[data-testid=\"stButton\"] button[kind=\"primary\"] {"
            "background-color:#ff3b30 !important;color:#fff !important;"
            "border-color:#ff3b30 !important;box-shadow:none !important;}</style>",
            unsafe_allow_html=True)
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
            if sel_rows and st.button(f"Xoá {len(sel_rows)} phiên đã chọn", type="primary", key="tbtn_delete_selected"):
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

# ==========================================
# TAB HƯỚNG DẪN
# ==========================================
elif nav == "Hướng dẫn":
    # Trang Trợ giúp: tour cuộn dọc theo hành trình 1 ngày sử dụng (thay cho 8 sub-tab ngang
    # + screenshot của bản cũ). Toàn bộ minh hoạ vẽ thuần HTML/CSS bằng token màu (var(--accent-rgb),
    # var(--chip)...) nên tự ăn theo dark mode lẫn màu accent đang chọn, không cần chụp lại ảnh
    # theo theme như thời còn assets/help/. Nội dung mỗi chương chỉ giữ phần "luật ngầm" của app
    # (ngữ nghĩa đồng bộ, timezone, cách đọc số) — phần mô tả hiển nhiên nhìn UI là hiểu thì bỏ.

    # --- Hero + mục lục ---
    sec_hero(
        "Trợ giúp", "Chào bạn, đây là một vòng Forest Dashboard",
        "Nói trước cho yên tâm: app này là cái gương để soi lại, không phải "
        "ông sếp đứng sau lưng nhắc việc — không đặt mục tiêu, không hối thúc, không có thanh "
        "tiến độ nào réo gọi bạn cả. Nó chỉ lặng lẽ ghi lại những gì Forest đã ghi, rồi chờ bạn "
        "quay lại nhìn khi nào rảnh. Vì vậy hướng dẫn này cũng không bắt bạn học thuộc từng trang "
        "một cách khô khan, mà kể theo đúng nhịp một ngày bình thường của bạn: sáng liếc qua để "
        "lên kế hoạch, cả ngày kệ app đó mà làm việc, tối dành 5 phút đóng lại ngày hôm đó — rồi "
        "cứ thế phóng to dần ra thành tuần, tháng, năm. Đọc từ đầu tới cuối chắc mất khoảng một "
        "tách trà; đọc lướt qua mục lục bên dưới rồi nhảy thẳng vào chỗ đang cần cũng tốt không kém.",
        [("help-ch1", "1 · Buổi sáng"), ("help-ch2", "2 · Trong ngày"),
         ("help-ch3", "3 · Cuối ngày"), ("help-ch4", "4 · Tuần &amp; tháng"),
         ("help-ch5", "5 · Sách · Gundam · Sức khoẻ"), ("help-ch6", "6 · Dữ liệu &amp; đồng bộ"),
         ("help-ch7", "7 · Tuỳ biến"), ("help-ch8", "8 · Câu hỏi thường gặp"),
         ("help-ch9", "9 · Nhật ký phát triển")])

    # ==========================================
    # CHƯƠNG 1: BUỔI SÁNG
    # ==========================================
    sec_chapter(
        "help-ch1", 1, "Hôm nay · trước phiên đầu tiên", "Buổi sáng — lên kế hoạch bằng lịch sử",
        tight_top=True)
    # Minh hoạ dòng thời gian trong ngày: mỗi khối là 1 phiên đặt đúng vị trí giờ nó diễn ra
    _daybar = "".join(
        f"<b style='left:{l}%;width:{w}%' class='{c}'></b>"
        for l, w, c in [(9, 7, ""), (17, 5, "d2"), (24, 3, ""), (38, 8, "d2"),
                        (48, 4, ""), (60, 6, ""), (68, 3, "d2"), (83, 7, "")])
    sec_block(
        "<h4>Dòng thời gian trong ngày</h4>"
        f"<div class='sec-daybar'>{_daybar}</div>"
        "<div class='sec-axis'><span>0h</span><span>6h</span><span>12h</span><span>18h</span><span>24h</span></div>"
        "<div class='sec-cap'>Mỗi khối màu là 1 phiên tập trung, được đặt đúng vào vị trí giờ nó "
        "thực sự diễn ra và tô màu theo Nhóm — nhìn một cái là biết ngay buổi sáng/chiều/tối hôm đó "
        "dồn hết vào việc gì, và có bị ngắt quãng lung tung không. Đỡ phải dò từng dòng trong bảng.</div>")
    sec_block(
        "<h4>Ngày chưa có phiên nào thì xem gì cho đỡ trống trải</h4>"
        "<ul>"
        "<li><b>Lịch hẹn Work</b> của ngày hôm đó vẫn hiện đầy đủ trong Ghi chú ngày dù chưa có phiên nào — "
        "nhờ vậy bạn biết ngay còn bao nhiêu khung giờ trống để nhét việc vào trước khi bắt tay làm.</li>"
        "<li><b>Trích dẫn hôm nay</b> — một highlight hoặc ghi chú Kindle được chọn ngẫu nhiên, nằm ngay đầu "
        "trang cho có chút không khí văn chương buổi sáng. Câu này chọn cố định theo <b>ngày thật</b>: có "
        "tải lại trang bao nhiêu lần, hay lùi tới/tiến lui xem ngày khác, câu vẫn y nguyên — chỉ đổi khi "
        "sang một ngày mới mà thôi, đúng tinh thần “quote of the day”. Muốn xem câu khác ngay lúc đó thì "
        "bấm nút xáo (biểu tượng trộn bài) cạnh nút ⭐ — chỉ đổi tạm trong phiên xem hôm nay, sang ngày mới "
        "vẫn quay lại chọn theo ngày như bình thường.</li>"
        "<li>Và một điều nhỏ nhưng quan trọng: “hôm nay” trong toàn bộ app luôn được tính theo <b>giờ Việt "
        "Nam</b>, bất kể server đang chạy ở múi giờ nào trên thế giới — để ngày của bạn không bao giờ tự "
        "dưng nhảy sớm hoặc muộn mất 7 tiếng so với đồng hồ thật.</li>"
        "</ul>")

    # ==========================================
    # CHƯƠNG 2: TRONG NGÀY
    # ==========================================
    sec_chapter(
        "help-ch2", 2, "Ghi chú nhanh · phím tắt", "Trong ngày — cứ để app đó, đừng mở ra")
    sec_block(
        "<h4>Ghi chú nhanh — cái hộp thư nháp sống trong túi quần</h4>"
        "Có một Shortcut trên iPhone (gọi qua Siri, Action Button, hay icon ngoài Màn hình chính, tuỳ bạn "
        "thích kiểu nào) sẽ hỏi bạn gõ đúng 1 dòng ý tưởng, rồi lặng lẽ gửi <b>thẳng lên Supabase</b> — "
        "không cần mở trình duyệt, không cần chạm vào app một chút nào. Mỗi dòng ghi kèm đúng giờ lúc bạn "
        "gửi (sửa nội dung về sau không làm giờ này đổi theo) và nằm chờ sẵn trong Ghi chú ngày của đúng "
        "hôm đó, ngay phía trên nhãn “Ghi chú chính” — như một tờ giấy nhớ dán tạm chờ bạn "
        "xử lý. Đúng tinh thần một hộp thư nháp: ghi vội bất cứ lúc nào loé lên ý tưởng trong ngày, tối "
        "về gom lại thành một đoạn hoàn chỉnh (xem chương 3 để biết cách gộp). Yên tâm là Tìm kiếm cũng "
        "quét được cả nội dung ghi chú nhanh, phòng khi vài hôm bạn lười chưa kịp gộp vào ghi chú chính.")
    _sc_rows = [
        [sec_kbd("1") + " … " + sec_kbd("7"), "Nhảy thẳng tới từng mục trên thanh điều hướng, đúng thứ tự trái sang phải như trên màn hình", "Toàn app"],
        [sec_kbd("N"), "Mở ngay ô soạn Ghi chú ngày của hôm nay, tự cuộn tới và focus sẵn con trỏ cho bạn gõ luôn", "Toàn app"],
        [sec_kbd("/"), "Nhảy sang trang Tìm kiếm (nếu đang ở trang khác) và focus luôn vào ô nhập từ khoá", "Toàn app"],
        [sec_kbd("←") + " / " + sec_kbd("→"), "Lùi về hôm qua / tiến tới ngày mai, khỏi cần bấm chuột chọn ngày", "Trang Hôm nay"],
        [sec_kbd("Ctrl/Cmd", "Enter"), "Lưu ngay Ghi chú ngày đang soạn dở, không cần rê chuột đi tìm nút Cập nhật", "Trong ô ghi chú"],
        [sec_kbd("Esc"), "Huỷ đang soạn ghi chú, hoặc bỏ focus ô Tìm kiếm mà không xoá mất từ khoá đang gõ", "Theo ngữ cảnh"],
        [sec_kbd("?"), "Bật/tắt ngay bảng tóm tắt toàn bộ phím tắt này, phòng khi quên mất bảng này nằm ở đâu", "Toàn app"],
    ]
    sec_block(
        "<h4>Bảng phím tắt bàn phím — dán mắt nhớ luôn cho tiện</h4>"
        + sec_table(["Phím", "Bấm vào thì sao", "Dùng ở đâu"], _sc_rows)
        + "<div class='sec-cap'>Một lưu ý nhỏ tránh hoang mang: mọi phím tắt tự động im lặng khi con trỏ "
        "đang nằm trong một ô nhập liệu bất kỳ (ngoại trừ "
        + sec_kbd("Ctrl/Cmd", "Enter") + " và " + sec_kbd("Esc")
        + " ngay trong ô ghi chú, hai phím này vẫn hoạt động bình thường), và cũng không nhận khi bạn "
        "đang giữ Ctrl/Cmd/Alt — để khỏi vô tình nhảy trang lúc chỉ đang gõ chữ.</div>")

    # ==========================================
    # CHƯƠNG 3: CUỐI NGÀY
    # ==========================================
    sec_chapter(
        "help-ch3", 3, "Nghi thức đóng ngày", "Cuối ngày — 5 phút, thói quen đáng giá nhất cả app")
    sec_block(
        "<h4>Ba bước nhỏ, làm đúng thứ tự là xong</h4>"
        "<ol>"
        "<li><b>Đồng bộ ngay</b> (ở Tuỳ biến → 1. Dữ liệu đầu vào) — chỉ một nút bấm mà nạp cả dữ liệu "
        "Forest, tiến độ Reminder lẫn lịch Work cùng lúc. Đây là bước nền của mọi con số khác trong app: "
        "không đồng bộ thì chẳng có gì để mà nhìn lại cả, mọi biểu đồ sẽ trơ ra như tờ giấy trắng.</li>"
        "<li><b>Liếc qua trang Hôm nay chừng 1 phút</b> — nhìn dòng thời gian trong ngày và chip so sánh với "
        "đúng thứ này tuần trước. Chỉ cần tự hỏi đúng một câu: hôm nay có diễn ra như mình định không? "
        "Không phải để tự khen hay tự trách bản thân đâu, chỉ đơn giản là ghi nhận thật thà những gì đã xảy ra.</li>"
        "<li><b>Dành 2–3 phút viết Ghi chú ngày</b> — bước ngắn nhất nhưng lại nuôi sống cùng lúc ba tính "
        "năng khác của app: Nhật ký tuần/tháng, Tìm kiếm, và Ngày này năm trước. Con số chỉ kể được bạn làm "
        "<i>bao nhiêu</i> giờ, còn ghi chú mới kể được bạn làm <i>gì và vì sao</i> — một năm sau nhìn lại, "
        "cái thứ hai mới là thứ đáng đọc, chứ không ai ngồi gặm nhấm con số cũ cả.</li>"
        "</ol>")
    sec_block(
        "<h4>Nút Gộp của ghi chú nhanh — bấm rồi mà vẫn hồi hộp không biết đã xoá chưa?</h4>"
        "Bấm <b>Gộp</b> trên một dòng ghi chú nhanh sẽ chèn nguyên nội dung dòng đó vào cuối ô soạn Ghi chú "
        "chính (tự mở ô soạn luôn nếu bạn chưa mở) rồi gạch mờ dòng đó đi cho biết là “đã xử lý” — nhưng yên "
        "tâm, dòng đó chỉ <b>thực sự biến mất sau khi bạn bấm Cập nhật</b> để lưu lại Ghi chú chính. Nếu lỡ "
        "tay bấm Gộp rồi đổi ý, cứ bấm Huỷ (hoặc Xoá ghi chú chính) là bỏ đánh dấu, ghi chú nhanh vẫn còn "
        "nguyên xi không mất gì cả. Còn nếu bạn sửa một dòng thành trống trơn rồi bấm Cập nhật, dòng đó cũng "
        "bị xoá luôn — giống y hệt cách Ghi chú chính hoạt động, không có gì bất ngờ ở đây.")
    sec_block(
        "<h4>Vì sao ghi chú lại quan trọng hơn mọi biểu đồ đẹp đẽ khác</h4>"
        "Ghi chú là loại dữ liệu <b>duy nhất trong cả app không thể nạp lại được</b> nếu lỡ để trống: phiên "
        "Forest, tiến độ Reminders, hay trích dẫn Kindle — tất cả đều có thể khôi phục lại từ file gốc nếu "
        "cần. Nhưng ghi chú thì khác, nó chỉ tồn tại trong đầu bạn tại đúng khoảnh khắc đó — bỏ trống một "
        "tháng là mất vĩnh viễn một tháng ký ức, không có bản sao lưu nào cứu được. Cho nên nếu chỉ được "
        "chọn giữ đúng một thói quen từ toàn bộ trang hướng dẫn dài dòng này, hãy chọn: <b>viết ghi chú mỗi "
        "tối</b>. Mọi thứ khác đều có thể bỏ qua vài hôm mà không sao, riêng cái này thì không.")

    # ==========================================
    # CHƯƠNG 4: CUỐI TUẦN & CUỐI THÁNG
    # ==========================================
    sec_chapter(
        "help-ch4", 4, "Báo cáo · Tuần / Tháng / Năm", "Cuối tuần &amp; cuối tháng — review có mang theo câu hỏi")
    _q_rows = [
        ["Thời gian đang dồn vào đâu nhiều nhất?", "Phân bổ thời gian (Tháng: biểu đồ tròn · Tuần: Danh mục &amp; dự án dạng thanh xếp hạng)", "Báo cáo → Tháng / Tuần"],
        ["Mình hay tập trung sung sức nhất lúc mấy giờ?", "Xu hướng theo khung giờ", "Báo cáo → Tổng quan / Tháng"],
        ["Nhịp độ đang lên hay đang chùng xuống?", "Xu hướng + đường trung bình động 7 ngày", "Mọi trang Báo cáo"],
        ["Ngày hôm đó làm sâu hay chỉ vụn vặt cho có?", "Thanh phân bố độ dài phiên", "Mọi trang Báo cáo · Sách · Gundam"],
        ["Có việc nào đang âm thầm bị bỏ rơi không?", "Bảng số liệu — nhìn kỹ dấu ▾ đỏ", "Báo cáo → Tháng"],
        ["Ngày nào đỉnh nhất từ trước tới giờ?", "Bảng vàng: Ngày nổi bật &amp; Kỷ lục", "Bảng số liệu của từng trang"],
        ["Một việc cụ thể đang tiến triển ra sao?", "Báo cáo → Dự án (lọc riêng đúng 1 Nhóm/Dự án)", "Báo cáo → Dự án"],
    ]
    sec_block(
        "<h4>Đang thắc mắc điều gì — thì nên nhìn vào biểu đồ nào</h4>"
        + sec_table(["Câu hỏi trong đầu bạn", "Mở biểu đồ này lên", "Tìm ở đâu"], _q_rows))
    _heat_lv = [0, 1, 3, 2, 0, 4, 6, 2, 1, 0, 5, 7, 3, 1,
                2, 0, 1, 4, 5, 2, 0, 3, 6, 1, 2, 4, 0, 2,
                1, 3, 0, 2, 6, 1, 4, 0, 2, 5, 1, 3, 7, 0,
                4, 2, 5, 0, 1, 3, 2, 6, 0, 1, 4, 2, 0, 5]
    _heat = "".join(f"<i class='h{v}'></i>" for v in _heat_lv)
    _bar_h = [35, 55, 20, 70, 45, 4, 12, 60, 80, 50, 30, 65, 40, 92, 55, 25, 70, 45, 60, 35]
    _bars = "".join(f"<i style='height:{h}%'></i>" for h in _bar_h)
    st.markdown(
        "<div class='sec-grid'>"
        "<div class='sec-card'><h4>Biểu đồ lịch — thang màu tuyệt đối, không nói dối</h4>"
        f"<div class='sec-heat'>{_heat}</div>"
        "<div class='sec-cap'>8 bậc màu được neo cứng theo mốc giờ cố định, không hề co giãn theo đúng dữ "
        "liệu đang xem trên màn hình — nên “đậm bằng nhau” luôn có nghĩa là “số giờ bằng "
        "nhau” thật, so sánh được thoải mái giữa tháng này với tháng khác mà không sợ một ngày "
        "bất thường làm lệch cả thang đo, kiểu như hồi bạn cày liền 10 tiếng vì deadline dí.</div></div>"
        "<div class='sec-card'><h4>Xu hướng — đường trung bình thẳng thắn, không tô hồng</h4>"
        f"<div class='sec-bars'>{_bars}<span class='avg'></span></div>"
        "<div class='sec-cap'>Đường trung bình động 7 ngày này tính luôn cả những ngày 0 giờ tuyệt đối, "
        "chứ không chỉ đếm ngày có hoạt động rồi lờ đi phần còn lại — nên nghỉ liền vài hôm sẽ thấy đường "
        "đi xuống rõ ràng ngay, không có chuyện bị làm mượt cho đẹp mắt.</div></div>"
        "</div>", unsafe_allow_html=True)
    sec_block(
        "<h4>Đọc số cho đúng cách — bốn luật ngầm nên biết trước khi hoảng</h4>"
        "<ul>"
        "<li><b>Kỳ dở dang luôn được cắt gọn để so sánh công bằng</b> — nếu kỳ đang xem chưa đi hết (ví dụ "
        "mới qua 3 ngày đầu tháng mà đã tò mò mở Báo cáo), cả 2 mốc so sánh “vs kỳ trước” "
        "và “vs Trung bình” đều tự động bị cắt xuống đúng cùng số ngày đã trôi qua, công bằng "
        "cho cả hai bên; một dòng caption nhỏ phía trên Bảng số liệu sẽ nói rõ khi nào việc cắt này đang "
        "diễn ra, để bạn khỏi nghi ngờ có gì đó sai sai. Không có bước này thì 3 ngày đầu tháng đem so với "
        "nguyên cả tháng trước sẽ luôn trông như một cú sụt giảm thảm hại, dù thực ra chẳng có gì đáng lo cả.</li>"
        "<li><b>Chênh lệch trong khoảng ±20% là chuyện đời thường</b>, đừng vội hoảng — chỉ nên thực sự hành "
        "động khi độ lệch lớn <i>và</i> bạn đã biết rõ lý do đằng sau nó là gì.</li>"
        "<li><b>Dấu ▾ đỏ trong Bảng số liệu</b> nghĩa là kỳ đó tụt xuống còn ≤40% so với kỳ ngay trước đó — "
        "một tín hiệu đáng dừng lại vài giây để tự hỏi tại sao. Việc tô đậm ô trong bảng là so sánh trong "
        "<i>toàn bộ bảng</i> chứ không phải riêng từng hàng một; còn cột Tổng thì cố tình để trắng không tô "
        "gì cả, vì nó luôn là số lớn nhất nên tô đậm cũng chẳng nói thêm được điều gì mới.</li>"
        "<li><b>Kỷ lục và Ngày nổi bật là hai khái niệm khác nhau</b>, đừng nhầm — Ngày nổi bật là top ngày "
        "chỉ trong đúng kỳ đang xem thôi (nên tuần nào cũng có), còn Kỷ lục là top <i>toàn thời gian</i> "
        "(tính chung, và tính riêng cho từng Nhóm/Dự án đã có từ 5 ngày dữ liệu trở lên). Chỉ Kỷ lục mới "
        "được vinh dự gắn chip huy chương lên Timeline — vì nếu gắn cả Ngày nổi bật (thứ gần như tuần nào "
        "cũng có) thì cảm giác hiếm có sẽ mất sạch, huy chương phát tràn lan thì còn gì là huy chương nữa.</li>"
        "</ul>")
    sec_block(
        "<h4>Ba cái bẫy dễ sa vào nhất — cẩn thận kẻo dính</h4>"
        "<ol>"
        "<li><b>Tối ưu con số thay vì tối ưu công việc thật</b> — bấm trồng cây cho một phiên đọc tin vặt lan "
        "man chỉ để đủ chỉ tiêu giờ trong ngày là đang tự lừa chính mình, bằng chính cái công cụ vốn sinh ra "
        "để chống tự lừa — nghe hài hước nhưng lại rất dễ mắc phải. Số giờ chỉ là một thước đo gián tiếp, "
        "không phải là mục tiêu tự thân, đừng để nó cầm nhầm vai trò.</li>"
        "<li><b>Để chuỗi ngày liên tục biến thành cái gông đeo cổ</b> — đứt chuỗi sau một ngày ốm thật hay "
        "một ngày nghỉ đúng nghĩa là chuyện hoàn toàn bình thường, không có gì phải dằn vặt. Lời nhắc khi "
        "chuỗi đứt được app cố tình viết theo tông động viên nhẹ nhàng, chứ không phải lời trách móc — hãy "
        "đọc đúng với tinh thần đó, đừng tự biến nó thành áp lực.</li>"
        "<li><b>Review mà trong đầu chẳng có câu hỏi nào cả</b> — mỗi lần mở app nên có sẵn ít nhất một câu "
        "hỏi để trả lời: hôm nay diễn ra thế nào? tuần này có gì lệch khỏi dự tính? tháng này tỉ trọng ưu "
        "tiên đã đúng chưa? Không có câu hỏi thì chỉ đang lướt số liệu cho vui mắt thôi, chứ không phải "
        "đang thực sự nhìn lại.</li>"
        "</ol>")

    # ==========================================
    # CHƯƠNG 5: SÁCH, GUNDAM & SỨC KHOẺ
    # ==========================================
    sec_chapter(
        "help-ch5", 5, "Nguồn dữ liệu phụ", "Sách, Gundam &amp; Sức khoẻ")
    sec_block(
        "<h4>Quy ước đặt tên trong Apple Reminders — nhớ đặt đúng kẻo app đoán sai</h4>"
        "Mỗi <b>Reminder List</b> trên điện thoại tương ứng với 1 cuốn sách hoặc 1 series, đặt tên theo "
        "khuôn “Tác giả - Tên sách”; còn mỗi reminder đã được tick hoàn thành là 1 "
        "phần/chương/tập bạn đã đọc/xem xong. App sẽ cắt tên hiển thị theo dấu <b>“-” đầu "
        "tiên</b> gặp được trong tên list (ưu tiên dạng có khoảng trắng bao quanh “ - ” cho chắc "
        "ăn): phần đứng sau dấu gạch trở thành tên hiển thị, phần đứng trước bị lược bỏ đi. Còn nếu tên list "
        "bắt đầu bằng chữ “gundam” (viết hoa hay thường đều được, app không khó tính), nó sẽ tự "
        "động được xếp sang trang Gundam thay vì trang Sách.")
    sec_block(
        "<h4>“Số ngày” được tính kiểu gì khi có tận 2 nguồn dữ liệu cùng lúc</h4>"
        "Mỗi cuốn sách hay series được ghép lại từ tối đa 2 nguồn: phiên Forest (khi tên Dự án trùng khớp "
        "với tên sách) và các phần đã tick trong Reminders. Con số “Số ngày” sẽ lấy <b>hợp</b> "
        "của cả 2 nguồn — tức từ ngày bắt đầu sớm nhất cho tới ngày kết thúc muộn nhất, gộp cả hai bên lại "
        "— nên nếu bạn đổi cách theo dõi giữa chừng (đang bấm giờ Forest rồi chuyển sang chỉ tick Reminders "
        "cho tiện) thì khoảng thời gian vẫn không bị cắt cụt mất phần trước đó. Ô nào thiếu hẳn một nguồn sẽ "
        "hiện dấu gạch ngang “—” cho biết là thiếu dữ liệu, thay vì để trống trơn khiến bạn tưởng lỗi.")
    sec_block(
        "<h4>Gundam: vì sao app phải “đoán mò” xem bạn đang xem series nào</h4>"
        "Vì Forest chỉ có đúng 1 tag chung chung là “Gundam” cho mọi series, chứ không tách "
        "riêng từng bộ như Sách. Cho nên với mỗi ngày có phiên gắn tag đó, app sẽ đi tìm lần tick Reminder "
        "gần nhất (ở bất kỳ series Gundam nào, trước hoặc sau ngày đó đều tính, miễn là gần về mặt thời "
        "gian) rồi gán cả ngày hôm đó cho đúng series của lần tick ấy — kiểu như một thám tử nhỏ suy luận "
        "dựa trên dấu vết gần nhất. Nếu bạn chỉ xem đúng 1 series tại 1 thời điểm (trường hợp phổ biến "
        "nhất) thì suy luận này gần như luôn đúng; còn nếu bạn có thói quen xem xen kẽ nhiều series cùng "
        "lúc thì ngày nằm giữa 2 lần tick sẽ được gán về phía gần hơn, và đôi khi đoán sai cũng là chuyện "
        "bình thường. Đoán sai thì cũng đừng lo, cứ vào expander <b>“Sửa gán series tự động”</b> ở cuối "
        "trang Gundam mà sửa lại tay — ngày nào đã sửa tay sẽ mang dấu “Gán tay” cho dễ phân "
        "biệt, còn nếu sau này bạn sửa lại trùng đúng với kết quả suy luận tự động thì dấu đó tự động biến "
        "mất, coi như huề cả làng.")
    sec_block(
        "<h4>Trích dẫn Kindle — sửa một lần là ăn chắc, không sợ mất lại</h4>"
        "Mọi thao tác bạn làm trên trích dẫn (sửa câu chữ, xoá đi, đánh dấu ⭐ Yêu thích, hay thêm ghi chú "
        "riêng của mình) đều được lưu hẳn vào Supabase một cách nghiêm túc: có nạp lại file "
        "<code>My Clippings.txt</code> cũ bao nhiêu lần đi nữa — vì Kindle luôn xuất cộng dồn toàn bộ lịch "
        "sử từ đầu chứ không chỉ phần mới — thì nội dung bạn đã sửa vẫn <b>không bị ghi đè</b> và trích dẫn "
        "đã xoá cũng <b>không tự nhiên sống lại</b> làm bạn giật mình. Nếu bạn hay tô highlight bằng bút "
        "cảm ứng, Kindle thường sinh ra khá nhiều “bản nháp” trùng lặp (cùng một câu, cách "
        "nhau chưa tới 2 phút, câu sau chỉ dài hơn câu trước một chút vì tay bạn kéo thêm) — app tự nhận ra "
        "và gộp lại, chỉ giữ đúng bản đầy đủ nhất, không làm phiền bạn bằng cả đống bản nháp. Trong Nhật ký "
        "đọc, các trích dẫn tự sắp xếp theo <b>Vị trí</b> trong sách — đúng thứ tự bạn đọc thật, không cần "
        "tự tay gán từng câu vào đúng chương nào cả.")
    sec_block(
        "<h4>Sức khoẻ — nhập liệu bằng ảnh chụp phiếu, nhờ Claude làm hộ phần khó</h4>"
        "Quy trình gợi ý cho đỡ mất công gõ tay: chụp lại 2 phiếu xét nghiệm (Huyết học và Sinh hóa) mỗi lần "
        "đi khám, đưa ảnh vào Claude và nhờ đọc rồi xuất đúng khuôn JSON như bên dưới, sau đó dán thẳng vào "
        "mục <b>Import hàng loạt</b> (Sức khoẻ → Dữ liệu đầu vào) — có hẳn một bước Xem trước để soát lại "
        "trước khi bấm Xác nhận lưu, tránh nhập nhầm mà không hay biết. Mỗi lần mở trang Báo cáo là thấy "
        "ngay expander <b>“Chỉ số bất thường”</b> của lần khám gần nhất hiện sẵn ra, không cần "
        "phải chọn gì trước cả — tiện cho việc liếc nhanh xem có gì đáng lo không. Khoảng tham chiếu "
        "(<code>ref_raw</code>) chấp nhận khá nhiều dạng viết thường gặp trên phiếu xét nghiệm: khoảng đủ "
        "kiểu “4.2 - 5.4”, chỉ có trần trên như “&lt; 5”, hay chỉ có sàn dưới như "
        "“&gt; 10” — còn dạng khác (ví dụ kết quả định tính như “Âm tính”) vẫn "
        "lưu được bình thường, chỉ là không vẽ lên biểu đồ xu hướng được thôi.")
    with st.expander("Xem định dạng JSON mẫu để nhờ Claude xuất từ ảnh"):
        st.markdown(
            "Mỗi phần tử trong list là 1 phiếu (1 nhóm chỉ số) của 1 lần khám — 1 lần khám có 2 phiếu "
            "Huyết học + Sinh hóa thì ra 2 phần tử cùng `test_date` khác `category`:")
        st.code(json.dumps(HEALTH_METRICS_JSON_EXAMPLE, ensure_ascii=False, indent=2), language="json")

    # ==========================================
    # CHƯƠNG 6: NẠP DỮ LIỆU & ĐỒNG BỘ
    # ==========================================
    sec_chapter(
        "help-ch6", 6, "Tuỳ biến → 1. Dữ liệu đầu vào", "Nạp dữ liệu &amp; đồng bộ — luật chơi của từng nguồn")
    sec_block(
        "<h4>Đường đi của dữ liệu — từ điện thoại tới màn hình bạn đang xem</h4>"
        "<div class='sec-flow'>"
        "<span class='sec-flow-col'><span class='sec-flow-node'>Forest CSV</span>"
        "<span class='sec-flow-node'>Reminders</span></span>"
        "<span class='sec-flow-arr'></span>"
        "<span class='sec-flow-node'>Shortcut iOS</span>"
        "<span class='sec-flow-arr'></span>"
        "<span class='sec-flow-node'>Bucket Storage</span>"
        "<span class='sec-flow-arr'></span>"
        "<span class='sec-flow-node sec-flow-hub'>Đồng bộ ngay</span>"
        "<span class='sec-flow-arr'></span>"
        "<span class='sec-flow-node'>Dashboard</span>"
        "</div>"
        "<div class='sec-cap'>Cái Shortcut này chạy ngay từ share sheet mỗi khi bạn Export CSV từ app "
        "Forest: nó tiện tay lấy luôn file backup Reminder rồi tải cả 2 file lên chung một bucket Supabase "
        "Storage (tên file luôn bắt đầu bằng <code>forest</code> hoặc <code>reminder</code>, "
        "kiểu như <code>forest_2026-07-06.csv</code>). Về phía app, nút Đồng bộ ngay sẽ tự tìm file mới "
        "nhất của mỗi loại, nạp vào theo đúng luật ở bảng dưới đây, kéo luôn thể cả lịch Work qua CalDAV "
        "trong cùng một cú bấm cho đỡ phải làm nhiều bước, rồi dọn dẹp bớt file cũ còn sót lại trong bucket. "
        "Riêng file <code>My Clippings.txt</code> của Kindle thì phải tải tay, không đi qua đường bucket "
        "này — vì Kindle chưa có Shortcut nào tự động xuất file được.</div>")
    _sync_rows = [
        ["Forest CSV", "Cộng thêm", "Tự động bỏ qua phiên bị trùng (so theo giờ bắt đầu/kết thúc) và cả phiên "
         "đã từng bị bạn xoá trước đó — nạp lại đúng 1 file bao nhiêu lần cũng không lo bị nhân đôi dữ liệu"],
        ["Reminders", "<b>Thay thế toàn bộ</b>", "File này phản ánh đúng trạng thái hiện tại của mọi list, "
         "chứ không phải một lát cắt thời gian như CSV — nên app ghi đè sạch sẽ thay vì cộng dồn, để tránh "
         "dữ liệu cũ còn sót lại làm sai lệch"],
        ["Kindle My Clippings", "Cộng thêm", "Trích dẫn trùng lặp tự động bị bỏ qua; các bản nháp do bút "
         "cảm ứng sinh ra cũng tự gộp lại; mọi thứ bạn đã sửa/xoá/đánh dấu ⭐ ngay trong app đều không bị "
         "ghi đè hay hồi sinh trở lại"],
        ["Lịch Work (CalDAV)", "Thay theo khoảng ngày", "Có sẵn các preset ±30/±90/±180 ngày quanh hôm nay "
         "cho tiện, hoặc tự chọn 2 mốc ngày riêng — dùng khoảng rộng hơn khi cần lấp đầy dữ liệu lịch cũ "
         "cho tính năng Ngày này năm trước"],
    ]
    sec_block(
        "<h4>Cộng thêm hay thay thế hoàn toàn — mỗi nguồn một kiểu, đừng nhầm lẫn</h4>"
        + sec_table(["Nguồn dữ liệu", "Kiểu nạp", "Cách chống trùng &amp; lưu ý cần nhớ"], _sync_rows))
    sec_block(
        "<h4>Xoá phiên là một kiểu xoá có trí nhớ dai, không phải xoá xong là quên luôn</h4>"
        "Khi bạn xoá phiên ở mục <b>3. Dữ liệu làm việc hiện tại</b> (nút màu đỏ, bấm là xoá ngay không hỏi "
        "lại lần nào), phiên đó được app âm thầm ghi nhớ riêng vào một bảng tên là "
        "<code>deleted_sessions</code> — nên về sau nếu bạn lỡ nạp lại đúng file CSV cũ có chứa phiên đó, "
        "nó <b>sẽ không tự nhiên sống dậy</b> làm bạn hoang mang không hiểu sao dữ liệu đã xoá lại xuất hiện "
        "trở lại. Còn với những cuốn sách hoặc nguồn Kindle mới gặp lần đầu tiên, app sẽ hỏi bạn có muốn "
        "ghép nó với 1 Dự án đã có sẵn không (gợi ý sẵn theo tên gần giống nhất cho đỡ phải gõ) hoặc để nó "
        "đứng riêng thành “Nguồn độc lập” — chỉ cần xác nhận đúng 1 lần duy nhất, những lần tải "
        "file sau đó app sẽ tự nhớ và không hỏi lại nữa.")

    # ==========================================
    # CHƯƠNG 7: TUỲ BIẾN & GIAO DIỆN
    # ==========================================
    sec_chapter(
        "help-ch7", 7, "Màu · dark mode · sao lưu", "Tuỳ biến &amp; giao diện")
    sec_block(
        "<h4>Một màu accent duy nhất, lan ra ba nơi khác nhau, bằng ba cơ chế khác nhau</h4>"
        "<ul>"
        "<li><b>Nút bấm / khung viền / chip</b> — đi qua biến CSS <code>--accent</code>, toàn bộ stylesheet "
        "của app đều tham chiếu tới biến này thay vì gõ cứng một mã màu cố định vào từng chỗ.</li>"
        "<li><b>Biểu đồ đơn sắc và bảng nhiệt</b> — chỗ này không đi qua CSS mà đi qua tận Python: màu accent "
        "được quy đổi thành một giá trị <b>hue</b> (sắc độ), rồi mọi dải màu từ nhạt tới đậm đều tự động "
        "xoay theo hue đó — nên đổi màu accent một cái là đổi luôn tất cả biểu đồ cùng lúc, không sót chỗ nào.</li>"
        "<li><b>Ô ghi chú (trình soạn thảo Quill)</b> — chỗ này hơi đặc biệt vì nó chạy trong một iframe "
        "riêng biệt, CSS của trang chính không thể chạm tới được. Nên app phải tự tiêm một đoạn style riêng "
        "vào bên trong iframe đó, và lặp lại việc tiêm này định kỳ để không bị mất màu mỗi khi Streamlit "
        "dựng lại iframe (chuyện này xảy ra thường xuyên hơn bạn nghĩ).</li>"
        "</ul>"
        "Chọn một màu là áp dụng ngay lập tức, không cần bấm thêm nút Lưu nào cả — giá trị được ghi thẳng "
        "vào bảng <code>settings</code> trên Supabase. Nếu chẳng may bảng đó chưa được tạo, hoặc giá trị "
        "lưu trong đó bị hỏng vì lý do gì đó, app sẽ lặng lẽ rơi về màu “Chàm biển” mặc định "
        "thay vì báo lỗi đỏ lòm hay sập luôn — một cách xử lý khá lịch sự.")
    sec_block(
        "<h4>Dark mode — vì sao lại không có mỗi cái nút bật/tắt cho tiện</h4>"
        "App tự động đổi giữa tối và sáng theo đúng cài đặt hệ thống của thiết bị bạn đang dùng (hoặc theo "
        "lựa chọn thủ công trong menu ⋮ ở góc phải trên cùng của Streamlit, nếu bạn muốn tự chọn khác với "
        "hệ thống). Lý do không có nút riêng trong app khá đơn giản: Streamlit hiện chưa cho phép code tự "
        "đổi theme ngay lúc đang chạy, app chỉ đọc được theme hiện tại là gì rồi tô đúng bộ màu tương ứng "
        "theo đó thôi — kể cả biểu đồ, bảng nhiệt lẫn ô ghi chú đều được lo liệu đầy đủ, không sợ bị "
        "lệch tông giữa các phần.")
    sec_block(
        "<h4>Sao lưu — lớp an toàn thứ hai, phòng khi lớp thứ nhất cũng có ngày trở chứng</h4>"
        "Dữ liệu vốn đã khá bền vững trên Supabase rồi (không hề mất khi app khởi động lại hay redeploy), "
        "nhưng nút <b>Sao lưu</b> vẫn đóng gói toàn bộ mọi bảng dữ liệu thành 1 file .zip để bạn tải về máy, "
        "coi như một lớp an toàn thứ hai phòng hờ — app sẽ tự nhắc nhở nhẹ nhàng khi lần sao lưu gần nhất "
        "đã quá 30 ngày rồi, đừng lơ là lời nhắc đó. Hai nút <b>Khôi phục</b> và <b>Làm mới</b> đều là những "
        "thao tác ghi đè hoặc xoá sạch không thể hoàn tác được, nên bắt buộc bạn phải tick vào ô xác nhận "
        "trước thì nút mới chịu bật sáng lên cho bấm — cả 3 nút này đều cố tình tô màu đỏ để nổi bật hẳn "
        "lên, khác hẳn tông màu trung tính của mọi nút khác trong app, như một lời cảnh báo ngầm rằng "
        "“bấm là không quay đầu được đâu nhé”. Riêng việc gán Dự án vào Nhóm (mục "
        "<b>2. Phân loại</b>) thì nhẹ nhàng hơn nhiều — hoàn toàn tuỳ chọn, chỉ để báo cáo gọn gàng dễ nhìn "
        "hơn thôi, Dự án nào chưa được gán Nhóm vẫn hoạt động bình thường không thiếu sót gì cả.")

    # ==========================================
    # CHƯƠNG 8: CÂU HỎI THƯỜNG GẶP
    # ==========================================
    sec_chapter(
        "help-ch8", 8, "FAQ", "Câu hỏi thường gặp")
    with st.container(key="help_faq"):
        help_faq_item(
            "Nạp lại một file Forest CSV cũ có làm dữ liệu nhân đôi lên không?",
            "Không đâu, cứ yên tâm nạp lại thoải mái. Forest CSV được nạp theo kiểu **cộng thêm có chống trùng "
            "sẵn**: phiên nào trùng khớp giờ bắt đầu và giờ kết thúc với phiên đã có rồi thì app tự động bỏ qua, "
            "không thêm lần thứ hai. Có nạp cùng 1 file này mười lần đi nữa, kết quả cuối cùng vẫn y nguyên như "
            "chỉ nạp đúng 1 lần.")
        help_faq_item(
            "Tôi đã lỡ xoá 1 phiên rồi — giờ nạp lại CSV thì nó có \"sống lại\" làm phiền tôi không?",
            "Không, nó sẽ không hồi sinh đâu. Mỗi phiên bị xoá đều được app ghi nhớ cẩn thận trong một bảng "
            "riêng tên là `deleted_sessions` — có thể gọi đây là kiểu \"xoá có trí nhớ dai\". Vậy nên mọi lần "
            "nạp CSV về sau, kể cả khi file gốc vẫn còn chứa đúng phiên đó, app cũng sẽ tự động bỏ qua nó, "
            "không để nó lén quay lại làm số liệu của bạn sai lệch.")
        help_faq_item(
            "Vì sao tháng này nhìn vào thấy sụt giảm mạnh so với tháng trước, có phải tôi đang lười đi không?",
            "Trước khi hoảng, hãy kiểm tra một điều đơn giản: tháng này **đã đi hết chưa**, hay mới chỉ vừa bắt "
            "đầu được vài ngày? Với một kỳ chưa kết thúc, app sẽ tự động cắt bớt cả hai mốc so sánh (baseline) "
            "xuống cho khớp đúng số ngày đã trôi qua, và ghi rõ điều này bằng một dòng caption nhỏ ngay phía "
            "trên Bảng số liệu — nếu thấy dòng caption đó xuất hiện, nghĩa là con số so sánh bạn đang xem đã "
            "được làm công bằng rồi, không phải bạn đang tệ đi đâu. Còn nếu kỳ đã trọn vẹn hoàn toàn mà vẫn "
            "thấy lệch, thì nhớ là chênh lệch trong khoảng ±20% vẫn được xem là dao động rất bình thường của "
            "cuộc sống — chỉ thực sự đáng bận tâm khi độ lệch lớn hẳn và bạn đã biết rõ lý do vì sao.")
        help_faq_item(
            "Hai ngày có cùng tổng số giờ y hệt nhau, vì sao \"cảm giác\" về chúng lại khác nhau một trời một vực?",
            "Câu trả lời nằm ở **Thanh phân bố độ dài phiên**: cùng là 6 tiếng đồng hồ, nhưng một ngày có thể là "
            "4 phiên tập trung sâu, mỗi phiên kéo dài 90 phút liền mạch; còn ngày kia lại là 20 phiên vụn vặt "
            "chỉ 15 phút rồi bị ngắt quãng liên tục. Tổng số giờ bằng nhau tuyệt đối, nhưng chất lượng tập "
            "trung thì khác xa nhau — đây chính là lý do vì sao chỉ nhìn mỗi con số tổng thôi là chưa đủ. Muốn "
            "đào sâu hơn nữa thì xem thẻ **Độ dài phiên** trong chương Tổng quan (ở Báo cáo → Dự án), rê chuột "
            "vào từng khoảng để xem số phiên chi tiết.")
        help_faq_item(
            "Rốt cuộc thì múi giờ nào quyết định \"hôm nay\" của app là ngày nào?",
            "Luôn luôn là giờ Việt Nam, không có ngoại lệ nào cả — mọi phép tính liên quan tới ngày tháng trong "
            "toàn bộ app đều đi qua đúng một hàm lấy giờ Việt Nam duy nhất. Nên dù server chạy ở múi giờ UTC "
            "hay bất kỳ múi giờ nào khác trên thế giới, ngày của bạn cũng sẽ không bao giờ tự dưng bị lệch sớm "
            "hoặc muộn mất 7 tiếng đồng hồ so với đồng hồ thật bạn đang đeo trên tay.")
        help_faq_item(
            "Trích dẫn hôm nay đổi câu mới vào lúc nào vậy, sao thấy nó cứ y nguyên hoài?",
            "Đúng 1 lần mỗi ngày thôi, và đổi theo **ngày thật** hôm nay chứ không phải theo ngày bạn đang xem "
            "trên trang (hai cái này có thể khác nhau nếu bạn đang lùi về xem ngày cũ). Có tải lại trang bao "
            "nhiêu lần, hay lùi tới/tiến lui xem các ngày khác nhau đi nữa, câu trích dẫn vẫn giữ nguyên y hệt "
            "— chỉ khi thực sự sang một ngày mới thì mới có câu mới xuất hiện, giữ đúng cảm giác \"quote of the "
            "day\" như một cuốn lịch để bàn. Câu được chọn hoàn toàn ngẫu nhiên từ toàn bộ kho trích dẫn Kindle "
            "bạn đã nạp vào app.\n\n"
            "Muốn xem câu khác ngay lập tức thì bấm nút xáo (biểu tượng trộn bài) cạnh nút ⭐ Yêu thích — chỉ "
            "đổi tạm trong lúc đang xem, sang ngày mới thì lại quay về chọn theo ngày như bình thường, không "
            "giữ lại lựa chọn xáo tay của hôm trước.")
        help_faq_item(
            "Vừa nạp trích dẫn từ 1 cuốn sách hoàn toàn mới, chưa từng theo dõi tiến độ đọc — nó có hiện lên "
            "Trích dẫn hôm nay không, hay phải đợi ghép với Dự án trước đã?",
            "Hiện được ngay, không cần đợi gì cả. Lúc nạp *My Clippings.txt* ở Tuỳ biến → \"Tải trích dẫn "
            "Kindle\", nếu app gặp 1 cuốn/nguồn hoàn toàn mới, nó sẽ bắt bạn xác nhận ghép với 1 Dự án đang "
            "theo dõi, hoặc để nguyên \"Nguồn độc lập\" kèm 1 cái tên tự đặt (hợp cho tạp chí, hay sách bạn "
            "chưa track qua Reminders) — nhưng bước xác nhận này và bước lưu trích dẫn thật sự diễn ra CÙNG "
            "một lúc, chỉ sau đúng 1 lần bấm nút. Trích dẫn hôm nay chọn ngẫu nhiên trên toàn bộ kho, không "
            "quan tâm cuốn đó đã ghép Dự án hay còn để độc lập — nên ngay từ lần import đầu tiên, trích dẫn "
            "của cuốn sách mới đã có cơ hội xuất hiện y hệt mọi trích dẫn khác.\n\n"
            "Có 1 điều cần nhớ: bước xác nhận ghép Dự án/đặt tên đó **chỉ hỏi đúng 1 lần** cho mỗi tên sách — "
            "nếu lỡ chọn nhầm, hoặc sau này mới thật sự bắt đầu theo dõi tiến độ đọc cuốn từng để \"độc lập\" "
            "qua Reminders, vào lại đúng tab \"Tải trích dẫn Kindle\" đó — ngay dưới ô tải file luôn có sẵn "
            "1 bảng **\"Ánh xạ đã lưu\"** liệt kê mọi cuốn/nguồn đã từng ghép, sửa lại Dự án hoặc tên hiển thị "
            "ngay tại đó rồi bấm Lưu, không cần nạp lại file gốc.")
        help_faq_item(
            "Gundam bị gán nhầm series rồi, giờ sửa lại ở đâu cho đúng?",
            "Cứ tìm tới expander **\"Sửa gán series tự động\"** nằm ở tít cuối trang Gundam (mục này chỉ xuất "
            "hiện khi bạn có từ 2 series trở lên, vì có 1 series thì chẳng cần đoán làm gì): chọn lại đúng "
            "series cho từng ngày bị gán sai rồi bấm nút Lưu gán series là xong. Ngày nào bạn đã sửa tay sẽ "
            "được đánh dấu bằng nhãn \"Gán tay\" cho dễ phân biệt với phần app tự đoán — còn nếu "
            "sau này bạn sửa lại đúng trùng khớp với kết quả suy luận tự động ban đầu, cái nhãn đó sẽ tự động "
            "biến mất, coi như quay về trạng thái tự động như chưa từng có chuyện gì xảy ra.")
        help_faq_item(
            "Đổi màu accent xong, mấy cái biểu đồ có tự đổi màu theo không hay phải làm gì thêm?",
            "Có chứ, và đổi ngay lập tức không cần bạn làm gì thêm cả — kể cả Biểu đồ lịch, bảng nhiệt, lẫn màu "
            "chữ trong ô ghi chú cũng đổi theo luôn một lượt. Lý do là vì màu accent bạn chọn được quy đổi ngay "
            "thành một giá trị hue duy nhất, rồi mọi dải màu đơn sắc trong toàn bộ app đều tự động xoay theo "
            "đúng hue đó — nên sẽ không có chuyện một biểu đồ nào đó bị \"bỏ sót\" vẫn giữ màu cũ trong khi chỗ "
            "khác đã đổi hết rồi.")
        help_faq_item(
            "Sao bấm phím tắt hoài mà không thấy chạy gì cả, app có bị lỗi không?",
            "Nhiều khả năng không phải lỗi đâu, mà gần như chắc chắn là con trỏ chuột của bạn đang nằm sẵn "
            "trong một ô nhập liệu nào đó (như ô ghi chú, ô tìm kiếm...) — mọi phím tắt sẽ tự động im lặng khi "
            "rơi vào tình huống này, để tránh việc bạn gõ chữ bình thường mà app lại tưởng nhầm là đang bấm "
            "phím tắt rồi nhảy lung tung trang. Ngoại lệ duy nhất là Ctrl/Cmd+Enter và Esc ngay trong ô ghi "
            "chú, hai phím này vẫn hoạt động dù đang gõ. Cứ bấm `Esc` hoặc click chuột ra khoảng trống bên "
            "ngoài rồi thử lại là được; còn nếu đang giữ sẵn phím Ctrl/Cmd/Alt thì phím tắt cũng sẽ không nhận, "
            "vì lúc đó app nghĩ bạn đang định làm một tổ hợp phím khác của trình duyệt.")
        help_faq_item(
            "Ghi chú của tôi có bị mất khi app khởi động lại hoặc được redeploy lên phiên bản mới không?",
            "Không mất đâu, cứ an tâm — toàn bộ dữ liệu đều nằm trên Supabase chứ không nằm trong bộ nhớ tạm "
            "của app, nên nó hoàn toàn không phụ thuộc vào vòng đời sống chết của app cả. Tuy vậy, cần nhớ rằng "
            "ghi chú là loại dữ liệu **duy nhất trong cả app không thể nạp lại được từ bất kỳ nguồn ngoài nào** "
            "nếu chẳng may có sự cố gì đó thực sự nghiêm trọng xảy ra với Supabase — nên vẫn nên duy trì thói "
            "quen bấm Sao lưu định kỳ (app sẽ tự nhắc bạn sau mỗi 30 ngày nếu quên) để có thêm một lớp an toàn "
            "thứ hai, phòng xa cho chắc.")

    # ==========================================
    # CHƯƠNG 9: NHẬT KÝ PHÁT TRIỂN
    # ==========================================
    sec_chapter(
        "help-ch9", 9, "Changelog", "Nhật ký phát triển")
    HELP_CHANGELOG = [
        dict(pr="192", date="16/07/2026", pr_lines=1784, total_lines=8004,
             title="Billboard đầu trang cho Hôm nay/Báo cáo/Sách/Gundam/Sức khoẻ + một loạt sửa lỗi vặt",
             bullets=[
                 "**Trang Hôm nay có một tấm billboard mới** — gộp thẻ “Ngày đang xem”, thẻ trích dẫn "
                 "hôm nay và hàng chip mục lục thành một khối duy nhất, kiểu tờ lịch xé hằng ngày: số "
                 "ngày to bên trái, trích dẫn Kindle bên phải, có gạch dọc ngăn ở giữa và dòng “Cập nhật "
                 "gần nhất” tự nhích theo thời gian thực.",
                 "**Bố cục “chương cuộn dọc” của trang Trợ giúp giờ lan sang cả app** — Báo cáo (Tổng "
                 "quan/Tuần/Tháng/Năm/Dự án), Sách/Gundam (Chi tiết) và Sức khoẻ (Báo cáo) đều đổi từ "
                 "các mục gập (expander) đánh số sang billboard + chip mục lục nhảy nhanh, chương nào "
                 "cũng hiện sẵn khi cuộn thay vì phải bấm mở từng mục.",
                 "**Tinh chỉnh lại billboard sau vài vòng xem thử** — bỏ dòng kicker in hoa và câu mô "
                 "tả thừa ở mọi billboard (trừ đúng trang Trợ giúp), nới khoảng cách xuống nội dung bên "
                 "dưới, và bỏ hẳn billboard ở những sub-tab chỉ có một khối nội dung, không có gì để "
                 "mục lục chip trỏ tới (Sách/Gundam → Tổng quan). Sức khoẻ có thêm dòng “Cập nhật lần "
                 "cuối X trước”.",
                 "**Sửa một bug mất nội dung khá khó chịu** — bấm “Gộp” một ghi chú nhanh vào ô soạn "
                 "đang mở sẵn trước đó không đưa được nội dung thật vào ô soạn (component soạn thảo "
                 "không tự vẽ lại), giờ đã remount đúng lúc để nội dung gộp hiện ra thật sự.",
                 "**Một loạt tinh chỉnh nhỏ khác** — nút Gộp/Sửa/Xoá ở ghi chú nhanh không còn vỡ xuống "
                 "dòng, popup chọn ngày dịch hẳn sang tiếng Việt, dòng thời gian trong ngày đổi sang "
                 "style minh hoạ có chú giải theo Nhóm, Báo cáo Tuần/Tháng ẩn heading “Ghi chú chính” "
                 "khi không còn ghi chú nhanh đi kèm, tab Sách đổi thứ tự Tổng quan/Yêu thích/Chi tiết, "
                 "và thêm 2 màu accent mới (Cam đất, Ô liu).",
             ]),
        dict(pr="185-190", date="16/07/2026", pr_lines=1606, total_lines=7820,
             title="Dọn dẹp bloat, sửa lỗi vặt, và làm lại toàn bộ trang Trợ giúp bạn đang đọc",
             bullets=[
                 "**Sửa một lỗi khá xấu hổ** — tab “Cập nhật” của trang Trợ giúp (phiên bản cũ) "
                 "từng bị trống trơn mỗi khi mở lên, vì nội dung lỡ bị đặt nhầm vào đúng chỉ số của tab "
                 "“Tuỳ biến” phía trên thay vì tab “Cập nhật” thật sự — coi như suốt một "
                 "thời gian, những dòng nhật ký này đã âm thầm nằm sai chỗ mà không ai nhận ra. Nhân tiện "
                 "sửa luôn, cũng đổi font cho thẻ Trích dẫn hôm nay sang Cormorant Garamond tự host, đọc có "
                 "không khí sách vở hơn hẳn.",
                 "**Một đợt dọn dẹp diện rộng** — dời mục “Ngày này năm trước” lên ngay sau Ghi "
                 "chú ngày cho hợp lý luồng đọc, bớt vài số liệu và biểu đồ ít ai thực sự dùng tới ở trang "
                 "Báo cáo, lọc bớt tên sách ra khỏi danh sách chọn Dự án (vì nó đã có chỗ riêng ở trang "
                 "Sách rồi), sửa lỗi trùng lặp chỉ số trong thẻ “Ngoài khoảng tham chiếu” của "
                 "Sức khoẻ, và để trang Tuỳ biến mặc định chỉ mở đúng mục 1 thay vì mở tung hết cả 5 mục "
                 "gây rối mắt.",
                 "**Vài lượt sửa lỗi giao diện nhỏ khác** — nhãn buổi trong biểu đồ khung giờ tập trung "
                 "không còn đè lên chú giải, khử trùng lặp chỉ số Bilirubin ở Sức khoẻ, khoảng tham chiếu "
                 "tự điền sẵn cho đỡ gõ tay, và thẻ trích dẫn ở tab Yêu thích không còn bị chữ dòng cuối ăn "
                 "lẹm vào lề dưới.",
                 "**Dọn mã nguồn phía sau hậu trường** — gộp hai khối logic gần như giống hệt nhau (cách "
                 "tính phần trăm thời gian đã trôi qua trong kỳ, và cách nạp vài bảng dữ liệu dạng phẳng) "
                 "thành 2 hàm dùng chung, giúp mã nguồn gọn hơn một chút mà không đổi bất kỳ tính năng nào "
                 "người dùng nhìn thấy. Kèm theo là một đợt rà soát để sửa vài chỗ tài liệu nội bộ đã lỡ "
                 "ghi sai lệch so với code thật.",
                 "**Và đây, chính là trang Trợ giúp bạn đang đọc** — được làm lại hoàn toàn từ đầu, bỏ hẳn "
                 "58 tấm screenshot cồng kềnh, đổi từ 8 tab ngang sang một trang cuộn dọc kể chuyện theo "
                 "đúng nhịp một ngày sử dụng thật, thêm mấy hình minh hoạ vẽ tay thuần CSS, một mục cheat-"
                 "sheet tra nhanh, và cả phần Câu hỏi thường gặp này nữa — hy vọng đọc vào thấy dễ chịu hơn "
                 "hẳn bản cũ.",
             ]),
        dict(pr="182-184", date="15/07/2026", pr_lines=69, total_lines=7690,
             title="Trích dẫn Kindle: thẻ nổi bật + Yêu thích + gộp bản nháp bút cảm ứng",
             bullets=[
                 "**Trích dẫn hôm nay được lên đời** — thẻ trích dẫn này được chuyển hẳn lên đầu trang Hôm "
                 "nay, nằm ngay dưới thẻ “Ngày đang xem” cho dễ thấy ngay khi vừa mở app, đổi "
                 "sang nền màu accent đậm đà, chữ trích dẫn được phóng cỡ lớn theo kiểu chữ sách cho có "
                 "không khí văn chương hơn, và có thêm tên tác giả đứng cạnh tên sách để biết ngay câu này "
                 "trích từ đâu.",
                 "**Tính năng Yêu thích ra mắt** — giờ đây bạn có thể bấm dấu ★ trên bất kỳ trích dẫn hay "
                 "ghi chú Kindle nào để đánh dấu lưu lại, rồi xem gộp toàn bộ những gì đã đánh dấu ở một "
                 "sub-tab riêng tên là “Yêu thích” (nằm trong trang Sách) — mỗi trích dẫn được đặt "
                 "trong một thẻ nền riêng biệt cho dễ đọc và dễ phân biệt, thay vì trước đây chỉ là những "
                 "hàng chữ trần trụi xếp chồng lên nhau.",
                 "**Việc import Kindle trở nên thông minh hơn hẳn** — app giờ tự nhận diện và gộp lại các "
                 "“bản nháp” sinh ra do thói quen tô highlight bằng bút cảm ứng (những dòng gần "
                 "giống hệt nhau, cách nhau chỉ vài giây, câu sau luôn dài hơn câu trước một chút do tay "
                 "kéo thêm), rồi chỉ giữ lại đúng bản đầy đủ nhất — thay vì trước kia mỗi lần tô một "
                 "highlight lại vô tình sinh ra cả chục trích dẫn trùng lặp gây rối mắt.",
                 "Ngoài ra còn kèm theo một số việc dọn dẹp nhỏ: sửa lỗi giao diện khiến tab Gundam bị mất "
                 "kiểu dáng, sửa nút ★ bị chồng đè lên chữ trông rối mắt, dọn bớt các dòng heading dư thừa "
                 "ở nhiều bảng số liệu cho gọn gàng hơn, và đổi cách hiển thị Thứ trong Nhật ký từ dạng số "
                 "sang chữ đầy đủ (ghi “Thứ Tư” thay vì chỉ “Thứ 4” cộc lốc, đọc tự nhiên hơn hẳn).",
             ]),
        dict(pr="181", date="15/07/2026", pr_lines=960, total_lines=7448,
             title="Rà soát & đơn giản hoá theo phản hồi thực tế",
             bullets=[
                 "Sau một thời gian dùng thật, một số tính năng hoá ra không đáng công sức bằng ban đầu "
                 "tưởng nên đã được cắt bỏ để app gọn nhẹ hơn: khối Top 3 Danh mục/Dự án ở trang Hôm nay và "
                 "Báo cáo → Tuần, biểu đồ Gantt tự vẽ ở trang Sách/Gundam → Tổng quan (đẹp nhưng ít ai nhìn "
                 "tới), và vài phím tắt ít khi được dùng đến (Shift+1 tới 5, dấu ngoặc vuông, các phím "
                 "f/r/l).",
                 "Đổi lại, có khá nhiều thứ hữu ích được thêm vào: nút “Gộp” để chuyển thẳng "
                 "ghi chú nhanh vào ghi chú chính chỉ với một cú bấm, khả năng sửa tay khi việc gán series "
                 "Gundam tự động lỡ đoán sai, một view mới tên “Chỉ số bất thường” hiện ngay ở lần "
                 "khám Sức khoẻ gần nhất, phạm vi tìm kiếm của trang Tìm kiếm được mở rộng sang cả Ghi chú "
                 "nhanh, thêm ô checkbox xác nhận bắt buộc trước khi bấm “Khôi phục” cho an toàn "
                 "hơn, và gộp hai giao diện đồng bộ CalDAV vốn tách rời nhau thành một chỗ duy nhất cho đỡ "
                 "rối.",
             ]),
        dict(pr="158-165", date="06/07/2026", pr_lines=46, total_lines=6115,
             title="Bảng vàng (Ngày nổi bật & Kỷ lục) + Ghi chú nhanh từ iOS",
             bullets=[
                 "**Bảng vàng ra đời** — Bảng số liệu ở mỗi trang Báo cáo giờ có thêm mục “Ngày nổi "
                 "bật” (hiện top những ngày có nhiều giờ tập trung nhất trong đúng kỳ đang xem), cộng "
                 "thêm khái niệm **Kỷ lục** tính trên toàn bộ thời gian (cả tính chung lẫn tính riêng theo "
                 "từng Nhóm/Dự án), được gắn hẳn thành một chip hình huy chương nổi bật trên Timeline mỗi "
                 "khi ngày đó xứng đáng.",
                 "**Ghi chú nhanh chính thức có mặt** — giờ có một Shortcut ngay trên iPhone cho phép gửi "
                 "thẳng một dòng ý tưởng thoáng qua lên app, không cần mở trình duyệt hay chạm vào máy "
                 "tính chút nào; mỗi dòng ghi chú như vậy có thể sửa hoặc xoá riêng lẻ, hoàn toàn tách biệt "
                 "khỏi Ghi chú chính để khỏi lẫn lộn.",
                 "Kèm theo đó là một số việc nhỏ: gọn lại bố cục hiển thị trên điện thoại di động, và sửa "
                 "lỗi chip trong Bảng số liệu bị tràn ra ngoài khung khi giá trị hiển thị quá dài.",
             ]),
        dict(pr="166-167", date="06/07/2026", pr_lines=79, total_lines=6162,
             title="Logo mới, đồng bộ phong cách nút gọn toàn app",
             bullets=[
                 "Đổi sang một bộ logo thiết kế hoàn toàn mới, và điểm hay ho là nó tự động đổi màu theo "
                 "đúng màu accent bạn đang chọn, thay vì bị khoá cứng vào một màu cố định như trước.",
                 "Đồng bộ lại phong cách nút bấm cho gọn gàng hơn (ôm sát theo chữ bên trong, không còn cao "
                 "lêu nghêu quá khổ như trước) cho toàn bộ các nút nằm trong tab Tuỳ biến, nhìn nhất quán "
                 "hơn hẳn.",
             ]),
        dict(pr="155,157", date="06/07/2026", pr_lines=338, total_lines=5654,
             title="Đồng bộ nhanh làm phương án mặc định",
             bullets=[
                 "Tab “1. Dữ liệu đầu vào” giờ ưu tiên đưa **Đồng bộ nhanh** lên hàng đầu — chỉ "
                 "cần một nút bấm duy nhất là nạp được cả Forest, Reminder và lịch Work cùng một lúc, thẳng "
                 "từ file mà Shortcut đã tải lên sẵn, thay vì trước đây phải làm tay từng bước một trong 3 "
                 "lượt riêng lẻ khá mất công.",
                 "Ba cách tải tay kiểu cũ vẫn còn nguyên đó, không bị bỏ đi đâu cả, chỉ là được gộp gọn vào "
                 "trong một khối có thể thu lại tên là “Dự phòng” — dùng tới khi nào thực sự cần "
                 "thao tác riêng lẻ từng nguồn một thôi.",
             ]),
        dict(pr="132,133,136,137", date="04/07/2026", pr_lines=79, total_lines=5089,
             title="Báo cáo Năm, Tìm kiếm, chế độ tối, Nhịp làm việc",
             bullets=[
                 "**Báo cáo → Năm ra mắt** — một bản tổng kết trọn vẹn cho 1 năm cụ thể, gồm khối hero số "
                 "liệu nổi bật, Biểu đồ lịch trải dài cả năm, mục Đọc sách & Gundam trong năm, và Bảng số "
                 "liệu chi tiết.",
                 "**Trang Tìm kiếm ra đời** — một trang hoàn toàn riêng để tra từ khoá cùng lúc trên ghi "
                 "chú, lịch hẹn Work, và cả sách/Gundam đã đọc hoặc xem qua, rồi gộp toàn bộ kết quả lại "
                 "theo từng ngày cho dễ theo dõi ngữ cảnh.",
                 "**Chế độ tối chính thức có mặt** — toàn bộ giao diện, từ nút bấm, biểu đồ, bảng nhiệt, cho "
                 "tới ô ghi chú, đều được thiết kế thêm một phiên bản màu riêng dành cho chế độ tối, tự "
                 "động chọn theo đúng cài đặt hệ thống của thiết bị bạn đang dùng.",
                 "**Nhịp làm việc trở thành mục mới trong Hướng dẫn** — nội dung tập trung dạy cách dùng app "
                 "theo đúng nhịp ngày/tuần/tháng thực tế, thay vì chỉ đơn thuần liệt kê mô tả từng tính năng "
                 "một cách rời rạc như trước.",
             ]),
        dict(pr="141-146", date="04/07/2026", pr_lines=15, total_lines=5139,
             title="Thêm phím tắt bàn phím cho toàn app",
             bullets=[
                 "Bộ phím tắt đầu tiên của app chính thức ra mắt: các phím số 1 tới 7 để nhảy nhanh giữa "
                 "các trang, phím N để mở nhanh Ghi chú ngày của hôm nay và focus thẳng vào ô soạn cho gõ "
                 "luôn, phím / để focus vào ô Tìm kiếm, và phím Esc để bỏ focus khỏi ô đang gõ mà không làm "
                 "mất từ khoá đã nhập.",
                 "Muốn xem đầy đủ toàn bộ danh sách phím tắt hiện có, cứ ghé qua chương “Trong "
                 "ngày” ngay phía trên trong trang Trợ giúp này.",
             ]),
        dict(pr="125,126,139,140", date="04/07/2026", pr_lines=6, total_lines=5089,
             title="Trang Hôm nay, 14 màu accent, logo & wordmark",
             bullets=[
                 "**Trang Hôm nay chính thức ra đời** — được tách riêng ra từ lát cắt “Ngày” vốn "
                 "từng nằm bên trong Báo cáo, trở thành mục đầu tiên và cũng là mục mặc định trên thanh "
                 "điều hướng, vì xét cho cùng đây chính là trang được mở nhiều nhất mỗi ngày, xứng đáng có "
                 "một vị trí trang trọng riêng.",
                 "Bảng màu accent được mở rộng hẳn lên thành **14 màu** để chọn, xem trước trực tiếp qua một "
                 "bản xem trước tương tác ngay khi rê chuột qua, và áp dụng ngay lập tức cho toàn bộ nút "
                 "bấm, biểu đồ và bảng nhiệt trên khắp app.",
                 "Thêm một logo và dòng chữ wordmark “Forest Dashboard” hẳn hoi, thay cho cái "
                 "tiêu đề chữ trơn khô khan hồi trước.",
             ]),
    ]
    render_help_changelog(HELP_CHANGELOG)
