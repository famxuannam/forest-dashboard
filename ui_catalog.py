"""Catalogue dữ liệu tĩnh cho giao diện Forest Dashboard."""

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

# Bảng màu phong cách Apple / Latte sáng -- KHÔNG dùng cho biểu đồ Nhóm/Dự án nữa (xem
# dải "chart" của GUNDAM_THEMES bên dưới), vẫn giữ cho vài chỗ vẽ đường/marker đơn sắc cũ (vd biểu đồ xu hướng
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

# Theme giao diện (tab Tuỳ biến -> sub-page "Giao diện") -- 1 lựa chọn DUY NHẤT, đặt tên theo tông
# màu của các Gundam nổi tiếng (yêu cầu người dùng, thay hẳn 6 trục cũ: accent/bảng màu nền/hoạ
# tiết nền/kiểu thẻ/font/độ rộng nội dung). Mỗi theme quyết định TOÀN BỘ:
# - "mode": tông sáng/tối CỐ ĐỊNH của theme (không theo chế độ sáng/tối của trình duyệt/hệ điều
#   hành -- app.py suy IS_DARK từ đây, xem theming.md).
# - màu: bg/card/chip/border/text..text-4/accent/on-accent (chữ trên nền accent)/trim/trim2 (2 màu
#   phụ, dùng cho dải 3 màu nhỏ kiểu "tricolor" và vạch "bây giờ" trên dòng thời gian).
# - "chart": dải màu biểu đồ phân loại Nhóm/Dự án (build_color_map() trong app.py) -- đã thay
#   CHART_COLORS cố định cũ, biểu đồ đổi màu theo theme.
# - "font": 1 key của BODY_FONTS (font thân chữ, đã có sẵn file trong static/fonts/).
# - "pattern": 1 key của THEME_PATTERNS (hoạ tiết nền trang).
# - "cut" > 0: góc thẻ VÁT kiểu giáp (góc trên-trái/dưới-phải, qua CSS corner-shape: bevel --
#   trình duyệt chưa hỗ trợ corner-shape tự rơi về góc bo tròn cùng bán kính); cut == 0: bo tròn
#   "radius" px.
# Thứ tự trong dict là thứ tự hiển thị trong lưới chọn; key đầu tiên ("RX-78-2") là mặc định.
# Đã bỏ các theme quá giống nhau (Wing Zero ~ Strike Freedom, Sazabi ~ Sinanju, Destiny ~ Exia).
GUNDAM_THEMES = {
    "RX-78-2": {
        "name": "Gundam", "era": "UC 0079", "mode": "light", "font": "Hanken Grotesk",
        "pattern": "panel", "cut": 12, "radius": 0,
        "bg": "#eef0f4", "card": "#ffffff", "chip": "#e3e7ef", "border": "#d3d9e4",
        "text": "#121722", "text-2": "#3d4656", "text-3": "#5b6577", "text-4": "#a3abb8",
        "accent": "#1f4fa8", "on-accent": "#ffffff", "trim": "#c8262b", "trim2": "#f2b705",
        "chart": ["#1f4fa8", "#c8262b", "#d49a00", "#2e8b6f", "#6b4fa8", "#5b6577", "#3e8fd9", "#a0522d"],
        "note": "Giáp trắng, thân xanh, khiên đỏ, chữ V vàng.",
    },
    "MS-06S": {
        "name": "Zaku II của Char", "era": "UC 0079", "mode": "light", "font": "Work Sans",
        "pattern": "panel", "cut": 10, "radius": 0,
        "bg": "#f8eeec", "card": "#fffbfa", "chip": "#f1dedb", "border": "#e8cdc9",
        "text": "#2a1416", "text-2": "#5a3a3d", "text-3": "#77525a", "text-4": "#c4a5a3",
        "accent": "#b83c48", "on-accent": "#ffffff", "trim": "#e8958e", "trim2": "#3b2d2f",
        "chart": ["#b83c48", "#e08a82", "#4a3a3c", "#3f7f8c", "#c9932a", "#6d5a9e", "#7c8f3e", "#8a2c3a"],
        "note": "Hồng cá hồi phối đỏ sẫm.",
    },
    "RX-93": {
        "name": "Nu Gundam", "era": "UC 0093", "mode": "light", "font": "IBM Plex Sans",
        "pattern": "grid", "cut": 8, "radius": 0,
        "bg": "#ececea", "card": "#ffffff", "chip": "#e0e0dc", "border": "#d2d2ce",
        "text": "#141414", "text-2": "#3e3e3c", "text-3": "#5f5f5b", "text-4": "#a8a8a3",
        "accent": "#1e1e20", "on-accent": "#ffffff", "trim": "#e2ae00", "trim2": "#8a8a85",
        "chart": ["#1e1e20", "#e2ae00", "#8a8a85", "#2f5daa", "#b5452e", "#3e8a6a", "#6e4fa0", "#c47a1e"],
        "note": "Trắng và đen tương phản, fin funnel vàng.",
    },
    "RX-0": {
        "name": "Unicorn", "era": "UC 0096", "mode": "light", "font": "Plus Jakarta Sans",
        "pattern": "dots", "cut": 0, "radius": 14,
        "bg": "#f4f3f6", "card": "#ffffff", "chip": "#ece9f0", "border": "#dcd8e2",
        "text": "#17151b", "text-2": "#45414d", "text-3": "#645f6d", "text-4": "#aca7b4",
        "accent": "#c81e37", "on-accent": "#ffffff", "trim": "#ff6b7d", "trim2": "#b8b3c1",
        "chart": ["#c81e37", "#4a4650", "#2c5e9e", "#e58a97", "#c9932a", "#2f8f6e", "#6b4fa8", "#9a95a3"],
        "note": "Giáp trắng, psycho-frame đỏ khi vào NT-D.",
    },
    "ZGMF-X20A": {
        "name": "Strike Freedom", "era": "C.E. 74", "mode": "light", "font": "Public Sans",
        "pattern": "hex", "cut": 0, "radius": 10,
        "bg": "#f1f3f8", "card": "#ffffff", "chip": "#e4e8f2", "border": "#d3d9e8",
        "text": "#10152a", "text-2": "#3a4260", "text-3": "#59617e", "text-4": "#a5abc0",
        "accent": "#22348f", "on-accent": "#ffffff", "trim": "#c9a030", "trim2": "#8fa4d8",
        "chart": ["#22348f", "#c9a030", "#8fa4d8", "#b8343b", "#2f8a6e", "#6b4fa8", "#4a5170", "#d07a2e"],
        "note": "Trắng, xanh thẫm, khớp cánh vàng kim.",
    },
    "GN-003": {
        "name": "Kyrios", "era": "A.D. 2307", "mode": "light", "font": "Source Sans 3",
        "pattern": "hex", "cut": 10, "radius": 0,
        "bg": "#f6f2ee", "card": "#ffffff", "chip": "#efe6dd", "border": "#e2d6ca",
        "text": "#1e1a17", "text-2": "#4a423b", "text-3": "#6b6158", "text-4": "#b4aaa0",
        "accent": "#b04f0e", "on-accent": "#ffffff", "trim": "#f39a3d", "trim2": "#3c4250",
        "chart": ["#b04f0e", "#3c4250", "#f0a04b", "#2f6fa8", "#8a9099", "#2e8b6f", "#b53a46", "#6b4fa8"],
        "note": "Cam và trắng, khung xám thép, cánh tiêm kích.",
    },
    "ASW-G-08": {
        "name": "Barbatos", "era": "P.D. 323", "mode": "light", "font": "Bitter",
        "pattern": "panel", "cut": 14, "radius": 0,
        "bg": "#ece8df", "card": "#f8f6f1", "chip": "#e1dcd0", "border": "#d3ccbc",
        "text": "#1e1b16", "text-2": "#4a443a", "text-3": "#655d4f", "text-4": "#aea596",
        "accent": "#2e4d7a", "on-accent": "#ffffff", "trim": "#b23a2e", "trim2": "#d6a92a",
        "chart": ["#2e4d7a", "#b23a2e", "#d6a92a", "#6b7f4a", "#8c6d4f", "#4f7f99", "#7a4a6e", "#a9a08e"],
        "note": "Trắng bám bụi sao Hoả, xanh thép, đỏ và vàng.",
    },
    "XVX-016": {
        "name": "Aerial", "era": "A.S. 122", "mode": "light", "font": "Nunito Sans",
        "pattern": "dots", "cut": 0, "radius": 18,
        "bg": "#edf3fa", "card": "#ffffff", "chip": "#dfe9f6", "border": "#cddbec",
        "text": "#0f1c2e", "text-2": "#3a4a60", "text-3": "#56677e", "text-4": "#a2b0c2",
        "accent": "#2a6fc4", "on-accent": "#ffffff", "trim": "#f2c33e", "trim2": "#9cc3f0",
        "chart": ["#2a6fc4", "#9cc3f0", "#e8a92a", "#3d9a8b", "#e0708a", "#6c5bc0", "#56677e", "#c26a2e"],
        "note": "Trắng, xanh lam nhạt, điểm vàng.",
    },
    "RX-0[N]": {
        "name": "Banshee Norn", "era": "UC 0096", "mode": "dark", "font": "Inter",
        "pattern": "grid", "cut": 12, "radius": 0,
        "bg": "#0a0b0e", "card": "#14151a", "chip": "#1f2127", "border": "#2a2c33",
        "text": "#ededf0", "text-2": "#b9bbc3", "text-3": "#8d909a", "text-4": "#52555e",
        "accent": "#d6ae4e", "on-accent": "#14100a", "trim": "#e39a3b", "trim2": "#5c5f68",
        "chart": ["#d6ae4e", "#8d909a", "#e39a3b", "#6fa8dc", "#d0707e", "#7fc29b", "#a78bda", "#e8e8ec"],
        "note": "Giáp đen, psycho-frame vàng kim.",
    },
    "MSN-06S": {
        "name": "Sinanju", "era": "UC 0096", "mode": "dark", "font": "Source Serif 4",
        "pattern": "diamond", "cut": 0, "radius": 4,
        "bg": "#120f12", "card": "#1c181c", "chip": "#28222a", "border": "#352e37",
        "text": "#f2ece4", "text-2": "#cdc3b6", "text-3": "#9f9587", "text-4": "#5e5650",
        "accent": "#e0505e", "on-accent": "#1c0a0c", "trim": "#cfa54c", "trim2": "#5a2a30",
        "chart": ["#e0505e", "#cfa54c", "#9a7c88", "#6fa0c8", "#7fb58a", "#b78fd0", "#e5875a", "#cdc3b6"],
        "note": "Đỏ thẫm, hoa văn viền vàng kim.",
    },
    "GN-001": {
        "name": "Exia", "era": "A.D. 2307", "mode": "dark", "font": "Noto Sans",
        "pattern": "hex", "cut": 10, "radius": 0,
        "bg": "#0c1424", "card": "#132037", "chip": "#1c2c48", "border": "#26385a",
        "text": "#e8eef8", "text-2": "#b6c3d9", "text-3": "#8a9bb8", "text-4": "#4f5f7c",
        "accent": "#4d8dff", "on-accent": "#06101f", "trim": "#3fe0a0", "trim2": "#dce3ee",
        "chart": ["#4d8dff", "#3fe0a0", "#dce3ee", "#f2b84b", "#e86a7a", "#a98bf0", "#5fc8e8", "#8a9bb8"],
        "note": "Xanh lam, trắng, hạt GN xanh lục.",
    },
    "GN-002": {
        "name": "Dynames", "era": "A.D. 2307", "mode": "dark", "font": "Open Sans",
        "pattern": "grid", "cut": 10, "radius": 0,
        "bg": "#0d1612", "card": "#15211b", "chip": "#1e2d25", "border": "#2a3d33",
        "text": "#e8f0ea", "text-2": "#b5c6ba", "text-3": "#8aa093", "text-4": "#4f6257",
        "accent": "#5fc27e", "on-accent": "#08140d", "trim": "#e3b95a", "trim2": "#e8ece6",
        "chart": ["#5fc27e", "#e8ece6", "#e3b95a", "#5aa9e6", "#d9776a", "#a48bd8", "#3fc9b8", "#8aa093"],
        "note": "Xanh rừng thẫm, trắng, ống ngắm bắn tỉa.",
    },
}
DEFAULT_THEME = "RX-78-2"

# Hoạ tiết nền trang cho theme -- (background-image, background-size), vẽ bằng var(--divider-on-bg)
# lên var(--bg). Chỉ áp cho nền trang (.stApp), không lan vào thẻ/biểu đồ/bảng.
THEME_PATTERNS = {
    "panel": {
        "label": "Panel line",
        "image": "linear-gradient(var(--divider-on-bg) 1px, transparent 1px), "
                 "linear-gradient(90deg, var(--divider-on-bg) 1px, transparent 1px)",
        "size": "176px 112px",
    },
    "grid": {
        "label": "Lưới kỹ thuật",
        "image": "linear-gradient(var(--divider-on-bg) 1px, transparent 1px), "
                 "linear-gradient(90deg, var(--divider-on-bg) 1px, transparent 1px)",
        "size": "24px 24px",
    },
    "dots": {
        "label": "Chấm mịn",
        "image": "radial-gradient(1.4px 1.4px at 1px 1px, var(--divider-on-bg), transparent)",
        "size": "18px 18px",
    },
    "hex": {
        "label": "Lưới tam giác",
        "image": "repeating-linear-gradient(60deg, var(--divider-on-bg) 0 1px, transparent 1px 32px), "
                 "repeating-linear-gradient(-60deg, var(--divider-on-bg) 0 1px, transparent 1px 32px)",
        "size": "auto",
    },
    "diamond": {
        "label": "Hoa văn thoi",
        "image": "repeating-linear-gradient(45deg, var(--divider-on-bg) 0 1px, transparent 1px 26px), "
                 "repeating-linear-gradient(-45deg, var(--divider-on-bg) 0 1px, transparent 1px 26px)",
        "size": "auto",
    },
}


def _rgba(hexcode, a):
    h = hexcode.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def theme_tokens(theme):
    """Bộ token CSS (tên không có tiền tố --) của 1 theme trong GUNDAM_THEMES -- đủ mọi token mà
    CSS/HTML trong app.py đang đọc qua var(--...). text-on-bg/-2 trùng text/-2 vì thẻ và nền trang
    cùng tông (khác bộ "nền đậm, thẻ sáng" cũ)."""
    dark = theme["mode"] == "dark"
    ink = "#ffffff" if dark else theme["text"]
    return {
        "bg": theme["bg"],
        "card": theme["card"],
        "card-tl": _rgba(theme["card"], 0.85),
        "border": theme["border"],
        "divider": _rgba(ink, 0.12 if dark else 0.11),
        "divider-2": _rgba(ink, 0.18 if dark else 0.17),
        "divider-on-bg": _rgba(ink, 0.05 if dark else 0.07),
        "chip": theme["chip"],
        "text": theme["text"],
        "text-2": theme["text-2"],
        "text-3": theme["text-3"],
        "text-4": theme["text-4"],
        "text-on-bg": theme["text"],
        "text-on-bg-2": theme["text-2"],
        "on-accent": theme["on-accent"],
        "trim": theme["trim"],
        "trim2": theme["trim2"],
    }


def theme_card_vars(theme):
    """Token kiểu thẻ (--card-radius/--card-corner-shape/--card-border-w/--card-shadow) của theme.
    Thẻ không viền: tách lớp bằng nền + bóng nhẹ (sáng) hoặc 1 đường viền trong mờ (tối)."""
    if theme["cut"]:
        radius, shape = f"{theme['cut']}px 3px", "bevel"
    else:
        radius, shape = f"{theme['radius']}px", "round"
    if theme["mode"] == "dark":
        shadow = "inset 0 0 0 1px rgba(255,255,255,0.06)"
    else:
        shadow = f"0 1px 2px {_rgba(theme['text'], 0.05)}, 0 10px 28px -16px {_rgba(theme['text'], 0.2)}"
    return {"radius": radius, "corner_shape": shape, "border_w": "0px", "shadow": shadow}

# Font thân chữ (tab Tuỳ biến -> sub-page "Giao diện") -- trục độc lập, CHỈ áp cho vai trò "thân/
# nhãn/nút" (html/body/.stApp + iframe Quill, xem _BODY_FONT_FACE/style_quill()) -- KHÔNG áp cho
# font bảng số liệu (IBM Plex Mono, _TABLE_FONT_FACE) hay font trích dẫn (Cormorant Garamond,
# _QUOTE_FONT_FACE), vì 2 font đó được chọn có chủ đích riêng theo vai trò nội dung, không phải
# "giao diện chung" (xác nhận với người dùng).
# "file_prefix" khớp tên file trong assets/fonts/ (vd Inter-Variable-latin.woff2), "family" là tên
# CSS font-family thật.
#
# Đợt đổi mới thứ 3 (xác nhận với người dùng: bộ 8 font trước -- Inter/Archivo/Epilogue/Unbounded/
# Fraunces/Newsreader/Bitter/Big Shoulders Text -- có nhiều lựa chọn quá cách điệu/khó đọc, muốn về
# lại các font truyền thống, readability cao). Rút còn 5 font, bỏ hẳn 4 lựa chọn cách điệu/display
# (Archivo, Epilogue, Unbounded, Big Shoulders Text) và Fraunces (serif tương phản cao, cũng thiên
# về trang trí hơn là đọc dài); giữ Inter (sans trung tính, MẶC ĐỊNH) và Newsreader/Bitter (đã có
# sẵn, đọc tốt); thêm Source Sans 3 (sans nhân văn cổ điển) và Literata (serif thiết kế riêng cho
# đọc dài, từng có trong bộ font đầu tiên của app -- không ngại trùng lựa chọn cũ). Đã xác minh cả 5
# đều có bản variable phủ đủ wght 200-800 trong 1 file và đủ 3 subset latin/latin-ext/vietnamese.
#
# Đợt mở rộng thứ 4 (5 -> 20 font, xếp lưới 4x5, xác nhận với người dùng: CHỈ chọn font readability
# cao -- tiếp tục đúng tiêu chí đã chốt ở đợt 3, không quay lại font cách điệu/display). Thêm 15 font
# mới, TOÀN BỘ đều là sans-serif nhân văn/trung tính hoặc serif thiết kế riêng cho đọc dài (không
# font display/trang trí), đã xác minh TỪNG font có bản variable 1 file phủ đủ dải wght rộng VÀ đủ
# 3 subset latin/latin-ext/vietnamese trước khi tải (một số ứng viên phổ biến bị loại vì THIẾU hẳn
# subset vietnamese dù variable tốt -- Lato, Karla, PT Serif, Rubik, DM Sans, Figtree, Sora, Albert
# Sans, Zilla Slab, Libre Baskerville -- không đưa vào danh sách):
# - 10 sans-serif: Roboto (wght 200-800, hệ thống Android/Material, đọc rất tốt), Open Sans
#   (300-800, 1 trong các sans phổ biến/dễ đọc nhất Google Fonts), Noto Sans (200-800, thiết kế cho
#   khả năng đọc đa ngôn ngữ), Work Sans (200-800, nhân văn hiện đại), IBM Plex Sans (200-700, hệ
#   thống IBM, tối ưu đọc màn hình), Public Sans (200-800, font chuẩn USWDS thiết kế riêng cho
#   readability), Mulish (200-800, sans trung tính gọn), Nunito Sans (200-900, bo mềm dễ đọc), Plus
#   Jakarta Sans (200-800, nhân văn hiện đại), Hanken Grotesk (300-900, grotesk trung tính rõ ràng).
# - 5 serif: Merriweather (300-900, thiết kế RIÊNG cho đọc trên màn hình, rất phổ biến cho nội
#   dung dài), Source Serif 4 (200-800, cùng họ Source Sans 3 đã có, đối trọng serif của Adobe),
#   Lora (400-700, serif cân bằng cổ điển/hiện đại được dùng rộng rãi cho đọc dài), Crimson Pro
#   (200-800, lấy cảm hứng từ font in sách cổ điển, tối ưu đọc), Noto Serif (200-800, cùng họ Noto
#   Sans, đọc đa ngôn ngữ tốt).
#
# QUAN TRỌNG: "Manrope" (font khung vỏ CỐ ĐỊNH cho sidebar/date-picker, xem _UI_FONT trong app.py)
# KHÔNG còn là 1 key trong dict này -- đã tách riêng khỏi trục "Font thân chữ" (đọc thẳng
# "Manrope-Variable" qua _body_font_b64(), không tra cứu qua BODY_FONTS[_UI_FONT] nữa) để các lựa
# chọn ở đây có thể thay hẳn mà không phá khung vỏ cố định. File Manrope-Variable-*.woff2 trong
# assets/fonts/ VẪN GIỮ NGUYÊN (đang dùng cho khung vỏ), dù không còn hiện trong danh sách lựa
# chọn này.
BODY_FONTS = {
    "Inter": {"family": "Inter", "file_prefix": "Inter-Variable"},          # mặc định
    "Roboto": {"family": "Roboto", "file_prefix": "Roboto-Variable"},
    "Open Sans": {"family": "Open Sans", "file_prefix": "OpenSans-Variable"},
    "Noto Sans": {"family": "Noto Sans", "file_prefix": "NotoSans-Variable"},
    "Work Sans": {"family": "Work Sans", "file_prefix": "WorkSans-Variable"},
    "Source Sans 3": {"family": "Source Sans 3", "file_prefix": "SourceSans3-Variable"},
    "IBM Plex Sans": {"family": "IBM Plex Sans", "file_prefix": "IBMPlexSans-Variable"},
    "Public Sans": {"family": "Public Sans", "file_prefix": "PublicSans-Variable"},
    "Mulish": {"family": "Mulish", "file_prefix": "Mulish-Variable"},
    "Nunito Sans": {"family": "Nunito Sans", "file_prefix": "NunitoSans-Variable"},
    "Plus Jakarta Sans": {"family": "Plus Jakarta Sans", "file_prefix": "PlusJakartaSans-Variable"},
    "Hanken Grotesk": {"family": "Hanken Grotesk", "file_prefix": "HankenGrotesk-Variable"},
    "Newsreader": {"family": "Newsreader", "file_prefix": "Newsreader-Variable"},
    "Literata": {"family": "Literata", "file_prefix": "Literata-Variable"},
    "Bitter": {"family": "Bitter", "file_prefix": "Bitter-Variable"},
    "Merriweather": {"family": "Merriweather", "file_prefix": "Merriweather-Variable"},
    "Source Serif 4": {"family": "Source Serif 4", "file_prefix": "SourceSerif4-Variable"},
    "Lora": {"family": "Lora", "file_prefix": "Lora-Variable"},
    "Crimson Pro": {"family": "Crimson Pro", "file_prefix": "CrimsonPro-Variable"},
    "Noto Serif": {"family": "Noto Serif", "file_prefix": "NotoSerif-Variable"},
}

