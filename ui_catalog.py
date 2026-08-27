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

# Bảng màu cố định cho biểu đồ phân loại (cột theo Nhóm/Dự án, xem build_color_map())
# -- hệ "Vintage bản đồ": cân bằng nóng/lạnh (đỏ gạch/vàng/mận xen xanh dương/xanh lá/xanh ngọc),
# đã qua kiểm tra màu (chroma, phân biệt mù màu, tương phản) -- xem mockup đã chọn với người dùng,
# thay cho bảng "Sổ Tay" cũ (quá xỉn, vài cặp cạnh nhau khó phân biệt, không đạt kiểm tra). KHÔNG
# đổi theo accent đang chọn (khác heatmap/lịch, xem _teal_shades()) -- giữ luôn dễ phân biệt dù
# người dùng chọn accent nào.
CHART_COLORS = ["#c1440e", "#2f8f5e", "#3a5a9e", "#c9932a", "#8a3b8f", "#1f9caf", "#c94f70", "#6fa02e"]


# 20 lựa chọn màu accent (tab Tuỳ biến → "4. Giao diện"), người dùng tự chọn, render 4 hàng x 5
# cột (xem per_row=5 ở lời gọi _tb_axis_grid() trong app.py). Mở rộng từ bộ 8 màu "jewel-tone" cũ
# (giữ NGUYÊN 8 mã hex cũ để không phá lựa chọn người dùng đã lưu) bằng cách chèn thêm 12 hue mới
# vào đúng khoảng trống lớn nhất quanh vòng màu của 8 hue cũ (đặc biệt dải vàng-lục gần như trống
# hẳn, từ ~42° đến ~161°) -- 12 hue mới tính bằng colorsys theo cùng công thức HSL nhất quán (S/L
# hiệu chỉnh riêng theo dải hue để giữ độ rực + tương phản chữ trắng tương đương bộ cũ), KHÔNG
# random/hand-pick tự do. Cả 20 màu xếp theo ĐÚNG thứ tự hue tăng dần (0°→360°) trong dict này để
# lưới 4x5 đọc như 1 dải cầu vồng liền mạch, không nhảy cóc. Contrast chữ trắng thấp nhất trong bộ
# mới là "Vàng chanh" (~2.98:1) -- vẫn cao hơn mức đã chấp nhận của "Vàng hổ phách" bộ cũ (~2.45:1)
# vì vàng bão hoà cao luôn khó đạt AA 4.5:1 với chữ trắng (xem lý do gốc ở lần đổi bộ màu trước).
# Bảng này TÁCH RIÊNG khỏi CHART_COLORS (bảng màu biểu đồ Nhóm/Dự án, hệ "Vintage bản đồ", không đổi).
ACCENT_PRESETS = {
    "Đỏ cam": "#d51710",
    "Cam rực": "#e0630a",
    "Vàng hổ phách": "#d99a06",
    "Vàng chanh": "#9c9a11",
    "Lục chanh": "#73931a",
    "Lục cỏ": "#4f8b1d",
    "Lục rêu": "#318321",
    "Lục thông": "#1b7e26",
    "Lục ngọc": "#158441",
    "Lục bích": "#12946b",
    "Ngọc lam": "#119793",
    "Lam ngọc bích": "#0f7ea3",
    "Xanh dương": "#285fbd",
    "Chàm điện": "#4f4dc4",       # mặc định
    "Chàm tím": "#6c49c5",
    "Tím thạch anh": "#8a3fc9",
    "Tím hoa cà": "#bb36c9",
    "Hồng cánh sen": "#c62fa3",
    "Hồng mẫu đơn": "#d13a7a",
    "Đỏ ruby": "#c81452",
}

# Kiểu nền trang (áp cho .stApp, xem rule CSS dùng var(--bg-image)/var(--bg-size)/var(--bg-position))
# -- "image"/"size"/"position" là giá trị CSS thô ghép thẳng vào background-image/size/position
# qua biến CSS, dùng var(--divider) để tự đổi theo IS_DARK như mọi hoạ tiết khác trong app. "Trơn"
# dùng image:none (hợp lệ) thay vì bỏ hẳn cặp thuộc tính, để 1 cơ chế var() duy nhất áp cho mọi
# lựa chọn, không cần nhánh riêng trong CSS chính. "position" mặc định "0 0" nếu không khai báo.
#
# Đợt đổi mới thứ 2 (xác nhận với người dùng: đã nhìn quen bộ chủ đề "rừng/nhịp thời gian" -- Sương
# mai/Vòng tuổi/Vân gỗ/Lá rơi/Đường mòn/Giọt sương/Núi xa -- muốn 1 bộ "hoàn toàn khác"). Đổi hẳn
# sang chủ đề "hình học tối giản": Lưới điểm/Chấm tròn (2 mật độ chấm khác nhau, giống cặp Sương
# mai/Giọt sương cũ nhưng dựng bằng 1 lớp duy nhất TĨNH đều tăm tắp thay vì rải rác tự nhiên) + Ô
# vuông/Kẻ ngang/Kẻ chéo/Kim cương/Vân lưới (đều dựng từ (repeating-)linear-gradient kẻ thẳng,
# KHÔNG còn radial-gradient rải rác kiểu hữu cơ như bộ trước) -- 2 nhóm kỹ thuật hoàn toàn khác bộ
# cũ (bộ cũ chủ yếu radial-gradient rải rác + vài lớp lệch góc nhẹ mô phỏng vân tự nhiên). "Lưới
# điểm" là mặc định mới, thay "Sương mai" -- xem fallback BG_STYLE bên dưới.
BG_PRESETS = {
    "Trơn": {
        "image": "none",
        "size": "auto",
    },
    "Lưới điểm": {
        # 1 lớp radial-gradient duy nhất, chấm nhỏ đều tăm tắp theo lưới vuông -- khác hẳn "Sương
        # mai" cũ (5 lớp chấm rải rác không đều).
        "image": "radial-gradient(1.4px 1.4px at 1px 1px, var(--divider-on-bg), transparent)",
        "size": "22px 22px",
    },
    "Chấm tròn": {
        # Cùng công thức "Lưới điểm" nhưng chấm to hơn + ô thưa hơn hẳn -- cặp mật độ khác nhau,
        # cùng vai trò 2 mức "chấm bi" như Sương mai/Giọt sương cũ nhưng đều tăm tắp thay vì rải rác.
        "image": "radial-gradient(2.6px 2.6px at 1px 1px, var(--divider-on-bg), transparent)",
        "size": "46px 46px",
    },
    "Ô vuông": {
        # 2 lớp linear-gradient kẻ dọc + ngang mảnh -> lưới ô vuông kiểu giấy kẻ ly, công thức CSS
        # "graph paper" kinh điển, KHÔNG có trong bộ cũ (bộ cũ toàn hoạ tiết chấm/kẻ chéo/vòng tròn).
        "image": ("linear-gradient(var(--divider-on-bg) 1px, transparent 1px), "
                   "linear-gradient(90deg, var(--divider-on-bg) 1px, transparent 1px)"),
        "size": "42px 42px",
    },
    "Kẻ ngang": {
        # 1 lớp repeating-linear-gradient ngang (0deg mặc định) -> vạch kẻ ngang mảnh đều, kiểu
        # "giấy kẻ dòng" -- khác hẳn mọi hoạ tiết chéo/chấm/tròn ở cả 2 bộ trước.
        "image": "repeating-linear-gradient(var(--divider-on-bg) 0 1px, transparent 1px 17px)",
        "size": "auto",
    },
    "Kẻ chéo": {
        # 1 lớp vạch chéo 60deg mảnh, chu kỳ thưa (26px) -- góc/chu kỳ khác hẳn "Đường mòn" cũ
        # (45deg, đoạn đứt 8px) để không lặp lại cảm giác cũ dù cùng kỹ thuật repeating-linear.
        "image": "repeating-linear-gradient(60deg, var(--divider-on-bg) 0 1px, transparent 1px 26px)",
        "size": "auto",
    },
    "Kim cương": {
        # 2 lớp linear-gradient chéo 45/-45deg giao nhau -> lưới hình thoi (kim cương/argyle mảnh),
        # công thức khác hẳn "Núi xa" cũ (Núi xa dùng 2 lớp CÙNG chiều lệch để tạo răng cưa, không
        # giao nhau thành ô kín).
        "image": ("linear-gradient(45deg, var(--divider-on-bg) 1px, transparent 1px), "
                   "linear-gradient(-45deg, var(--divider-on-bg) 1px, transparent 1px)"),
        "size": "34px 34px",
    },
    "Vân lưới": {
        # 3 lớp repeating-linear-gradient mảnh ở 0/60/120deg giao nhau -> lưới tam giác/lục giác
        # mặt phẳng (công thức "triangular grid" kinh điển), phức tạp/dày đặc hơn hẳn "Kim cương"
        # (chỉ 2 lớp) -- hoạ tiết dày nhất trong bộ mới, giữ vai trò "hoạ tiết đậm nhất" như "Núi
        # xa" cũ nhưng bằng kỹ thuật kẻ thẳng thay vì mảng phủ.
        "image": ("repeating-linear-gradient(0deg, var(--divider-on-bg) 0 1px, transparent 1px 30px), "
                   "repeating-linear-gradient(60deg, var(--divider-on-bg) 0 1px, transparent 1px 30px), "
                   "repeating-linear-gradient(120deg, var(--divider-on-bg) 0 1px, transparent 1px 30px)"),
        "size": "auto",
    },
}

# Bảng màu nền (tab Tuỳ biến -> "4. Giao diện"), người dùng tự chọn -- mỗi entry bundle ĐỦ 13
# token (light, dark) dùng để dựng _TOK (xem khối :root gần cuối file): bg/card/card-tl/border/
# divider/divider-2/chip/text/text-2/text-3/text-4/text-on-bg/text-on-bg-2. Bundle cùng lúc (không
# cho đổi rời từng token) để tránh nền mới "đọ màu" với viền/chip/chữ cũ.
#
# Đợt đổi mới thứ 2 (xác nhận với người dùng: đã nhìn quen 8 bảng "Giấy ấm/Rượu vang/Đêm tía/Lá
# non/Hoàng hôn/Sương tím/Bầu trời sao/Rừng đêm" + "Xám hệ thống" thêm sau -- muốn 1 bộ "hoàn toàn
# khác", kể cả bảng mặc định). 9 bảng mới dựng theo 1 CÔNG THỨC HSL nhất quán (khác cách hand-pick
# tự do trước đây) để đảm bảo tương phản/hài hoà mà không cần tinh chỉnh từng mã hex riêng lẻ -- 5
# bảng "nền nhạt" giữ nguyên hue xuyên suốt bg/card/border/chip (bg: S34% L87.5%/8.4%, card: S40%
# L96.5%/13.5%, border: S28% L72%/22%, chip: S30% L79%/17.5%, cùng khuôn "Lá non"/"Hoàng hôn" cũ đã
# đo lại), 4 bảng "nền đậm cố định" dùng khuôn "Rừng đêm"/"Rượu vang" cũ đã đo lại (bg S~24-36%
# L16-20% CỐ ĐỊNH cả 2 cột, card/border/chip theo công thức riêng sáng hơn, text-on-bg S24% L93%/
# text-on-bg-2 S17% L71% CỐ ĐỊNH cả 2 cột). 5 hue mới (lam ngọc/lam nhạt/hồng/vàng bơ/tím oải hương)
# và 4 hue mới (lam thẳm/nâu hạt dẻ/xám than/đất nung) đều KHÔNG trùng hue nào ở bộ cũ.
#
# text/text-2/3/4: LUÔN là màu chữ dùng BÊN TRONG thẻ/card (nền var(--card)) -- cả 9 bảng đều dùng
# thẻ SÁNG + chữ TỐI (yêu cầu trực tiếp của người dùng, giữ nguyên từ đợt trước: "các card vẫn có
# màu sáng và chữ màu tối" kể cả ở bảng nền đậm), nên dùng chung đúng 1 cặp chữ tối/sáng
# (#211c13/#f1ece0 v.v., KHÔNG đổi -- vẫn là hằng số gốc của app, độc lập với bảng màu nền đang
# chọn) cho MỌI bảng, không có khác biệt riêng theo bảng.
#
# text-on-bg/text-on-bg-2: token MỚI, chỉ dùng cho phần chữ nằm TRỰC TIẾP trên nền trang
# (var(--bg), NGOÀI mọi card) -- ví dụ wordmark "Forest/Dashboard" ở header (_wordmark_html()), text
# phụ ở màn đăng nhập (_login_txt2). 5 bảng "nền nhạt" dùng LUÔN cặp text/text-2 (không có gì khác
# biệt). 4 bảng "nền đậm cố định" có var(--bg) đậm CỐ ĐỊNH bất kể IS_DARK nên cần cặp text-on-bg/
# text-on-bg-2 SÁNG cố định riêng (không đổi theo IS_DARK) để chữ trên nền đậm luôn đọc được, tách
# biệt hẳn khỏi cặp text/text-2 tối dùng cho bên trong card.
BG_PALETTES = {
    "Bạc hà": {
        "bg":        ("#d4eae5", "#0e1d19"),
        "card":      ("#f3faf8", "#1a2b27"),
        "card-tl":   ("rgba(243,250,248,0.85)", "rgba(26,43,39,0.85)"),
        "border":    ("#a4ccc2", "#284840"),
        "divider":   ("rgba(13,38,32,0.14)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(13,38,32,0.2)", "rgba(255,255,255,0.17)"),
        "chip":      ("#b9dad1", "#213832"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#211c13", "#f1ece0"),
        "text-on-bg-2": ("#6f6650", "#b3a688"),
    },
    "Xanh da trời": {
        "bg":        ("#d4e1ea", "#0e171d"),
        "card":      ("#f3f7fa", "#1a242b"),
        "card-tl":   ("rgba(243,247,250,0.85)", "rgba(26,36,43,0.85)"),
        "border":    ("#a4bbcc", "#283b48"),
        "divider":   ("rgba(13,28,38,0.14)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(13,28,38,0.2)", "rgba(255,255,255,0.17)"),
        "chip":      ("#b9ccda", "#212e38"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#211c13", "#f1ece0"),
        "text-on-bg-2": ("#6f6650", "#b3a688"),
    },
    "Hồng phấn": {
        "bg":        ("#ead4da", "#1d0e12"),
        "card":      ("#faf3f4", "#2b1a1e"),
        "card-tl":   ("rgba(250,243,244,0.85)", "rgba(43,26,30,0.85)"),
        "border":    ("#cca4ae", "#482830"),
        "divider":   ("rgba(38,13,19,0.14)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(38,13,19,0.2)", "rgba(255,255,255,0.17)"),
        "chip":      ("#dab9c1", "#382127"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#211c13", "#f1ece0"),
        "text-on-bg-2": ("#6f6650", "#b3a688"),
    },
    "Vàng bơ": {
        "bg":        ("#eae6d4", "#1d1a0e"),
        "card":      ("#faf8f3", "#2b281a"),
        "card-tl":   ("rgba(250,248,243,0.85)", "rgba(43,40,26,0.85)"),
        "border":    ("#ccc4a4", "#484228"),
        "divider":   ("rgba(38,33,13,0.14)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(38,33,13,0.2)", "rgba(255,255,255,0.17)"),
        "chip":      ("#dad3b9", "#383321"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#211c13", "#f1ece0"),
        "text-on-bg-2": ("#6f6650", "#b3a688"),
    },
    "Tím oải hương": {
        "bg":        ("#e1d4ea", "#170e1d"),
        "card":      ("#f7f3fa", "#241a2b"),
        "card-tl":   ("rgba(247,243,250,0.85)", "rgba(36,26,43,0.85)"),
        "border":    ("#bba4cc", "#3b2848"),
        "divider":   ("rgba(28,13,38,0.14)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(28,13,38,0.2)", "rgba(255,255,255,0.17)"),
        "chip":      ("#ccb9da", "#2e2138"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#211c13", "#f1ece0"),
        "text-on-bg-2": ("#6f6650", "#b3a688"),
    },
    # 4 bảng dưới đây: "nền đậm cố định" -- bg ĐẬM ở CẢ 2 cột (khác 5 bảng "nền nhạt" trên -- bg chỉ
    # đậm khi IS_DARK), card/border/chip/divider theo công thức riêng (thẻ sáng/tối theo IS_DARK
    # như mọi bảng khác), text-on-bg/text-on-bg-2 SÁNG CỐ ĐỊNH cả 2 cột (bg luôn đậm nên chữ trên
    # nền luôn cần sáng) -- xem BG_PALETTES_DARK_BG ngay dưới.
    "Lam thẳm": {
        "bg":        ("#1a3037", "#1a3037"),
        "card":      ("#f5f8f9", "#161f22"),
        "card-tl":   ("rgba(245,248,249,0.85)", "rgba(22,31,34,0.85)"),
        "border":    ("#d2dcdf", "#253237"),
        "divider":   ("rgba(10,26,31,0.13)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(10,26,31,0.19)", "rgba(255,255,255,0.2)"),
        "chip":      ("#e6edef", "#1a2529"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#e9eff1", "#e9eff1"),
        "text-on-bg-2": ("#a8bbc2", "#a8bbc2"),
    },
    "Nâu hạt dẻ": {
        "bg":        ("#37261a", "#37261a"),
        "card":      ("#f9f7f5", "#221b16"),
        "card-tl":   ("rgba(249,247,245,0.85)", "rgba(34,27,22,0.85)"),
        "border":    ("#dfd8d2", "#372c25"),
        "divider":   ("rgba(31,19,10,0.13)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(31,19,10,0.19)", "rgba(255,255,255,0.2)"),
        "chip":      ("#efeae6", "#29201a"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#f1ece9", "#f1ece9"),
        "text-on-bg-2": ("#c2b3a8", "#c2b3a8"),
    },
    "Xám than": {
        "bg":        ("#2e3138", "#2e3138"),
        "card":      ("#f5f7f9", "#161a22"),
        "card-tl":   ("rgba(245,247,249,0.85)", "rgba(22,26,34,0.85)"),
        "border":    ("#d2d7df", "#252b37"),
        "divider":   ("rgba(10,17,31,0.13)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(10,17,31,0.19)", "rgba(255,255,255,0.2)"),
        "chip":      ("#e6e9ef", "#1a1f29"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#e9ecf1", "#e9ecf1"),
        "text-on-bg-2": ("#a8b1c2", "#a8b1c2"),
    },
    "Đất nung": {
        "bg":        ("#37211a", "#37211a"),
        "card":      ("#f9f6f5", "#221916"),
        "card-tl":   ("rgba(249,246,245,0.85)", "rgba(34,25,22,0.85)"),
        "border":    ("#dfd5d2", "#372925"),
        "divider":   ("rgba(31,15,10,0.13)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(31,15,10,0.19)", "rgba(255,255,255,0.2)"),
        "chip":      ("#efe8e6", "#291d1a"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#f1ebe9", "#f1ebe9"),
        "text-on-bg-2": ("#c2afa8", "#c2afa8"),
    },
}

# 4 bảng "nền đậm cố định" (bg đậm ở CẢ 2 cột, xem chú thích trong BG_PALETTES) -- billboard
# (render_period_billboard()/_render_today_billboard()) PHẢI đọc nền SÁNG + chữ TỐI như 1 thẻ
# thật, KHÔNG hoà theo màu nền trang đậm phía sau (xác nhận với người dùng: billboard vẫn là
# "light theme" y hệt các bảng nền nhạt, chỉ có nền NGOÀI thẻ/billboard mới được phép đậm) -- xem
# _billboard_bg/_billboard_backdrop ngay dưới _root_vars.
BG_PALETTES_DARK_BG = {"Lam thẳm", "Nâu hạt dẻ", "Xám than", "Đất nung"}

# divider-on-bg: token riêng cho hoạ tiết nền (BG_PRESETS, vẽ trực tiếp lên var(--bg) qua
# --bg-image) -- KHÔNG dùng chung "divider" được nữa vì "divider" thiết kế cho viền/kẻ BÊN TRONG
# card (thẻ luôn sáng, xem chú thích trên BG_PALETTES), cột "light" của nó là mực TỐI. Với 4 bảng
# BG_PALETTES_DARK_BG, var(--bg) luôn ĐẬM bất kể IS_DARK -- dùng nguyên "divider" ở light theme sẽ
# ra mực tối vẽ trên nền đậm, hoạ tiết gần như vô hình (bug thật, ảnh chụp người dùng gửi ở bảng
# nền đậm cố định thời bộ cũ). Lấy nguyên cột "dark" của divider (đã là màu sáng, tương phản tốt
# trên nền đậm) cho CẢ 2 cột. 5 bảng "nền nhạt" còn lại giữ y hệt divider gốc -- không đổi hành vi cũ.
for _pal_name, _pal in BG_PALETTES.items():
    _pal["divider-on-bg"] = ((_pal["divider"][1], _pal["divider"][1]) if _pal_name in BG_PALETTES_DARK_BG
                              else _pal["divider"])

# Kiểu thẻ (tab Tuỳ biến -> "4. Giao diện") -- trục độc lập với bảng màu nền ở trên, áp dụng chung
# lên MỌI bảng màu qua 3 token CSS --card-radius/--card-border-w/--card-shadow, cộng 3 KHOÁ TUỲ
# CHỌN "bg_override"/"backdrop"/"border_image" (mặc định var(--card)/none/none nếu không khai báo,
# xem _card_style_vars) cho 2 hiệu ứng cần hơn 3 token gốc (đổi background-image/backdrop-filter,
# không chỉ radius/border/shadow) -- áp qua 1 rule CSS gộp DUY NHẤT (xem rule ngay sau
# _card_style_vars), đặt SAU mọi rule gốc trong cascade nên tự thắng mà không cần sửa từng nơi.
#
# Đợt đổi mới thứ 2 (xác nhận với người dùng: đã nhìn quen 8 kiểu cũ -- Bo mềm/Vuông viền đậm/Nổi
# khối/Viền kép/Nổi mềm/Đóng dấu/Kính mờ/Viền gradient -- muốn 1 bộ "hoàn toàn khác", kể cả kiểu
# mặc định). 8 kiểu mới vẫn dùng ĐÚNG cơ chế 3+3 token trên (không đổi kiến trúc), chỉ đổi công
# thức cụ thể: "Phẳng lì" (không viền/không bóng -- CHƯA có kiểu nào trong 2 bộ trước hoàn toàn
# phẳng), "Viên thuốc" (bo tròn 24px kiểu capsule, khác hẳn mọi mức bo tròn cũ tối đa 16px), "Bóng
# sâu" (bóng đơn lớn/đậm hơn "Nổi khối" cũ), "Viền nhấn" (viền ĐẶC màu Accent qua border_image
# 1-màu, khác "Viền gradient" cũ luôn có dải chuyển màu), "Nền mờ nhẹ" (bg_override var(--card-tl)
# GIỐNG "Kính mờ" cũ nhưng KHÔNG bật backdrop-filter -- phẳng/trong suốt thay vì hiệu ứng kính mờ
# thật), "Đổ tầng" (3 lớp box-shadow chồng xa dần, khác mọi shadow đơn lớp trước đó), "Khắc chìm"
# (2 lớp inset tạo cảm giác khắc/chạm nổi ngược, khác "Đóng dấu" cũ chỉ 1 lớp inset), "Hào quang
# nhấn" (viền mảnh + quầng sáng màu Accent lan toả quanh thẻ, hiệu ứng CHƯA từng có ở 2 bộ trước).
CARD_STYLES = {
    "Phẳng lì": {
        "radius": "4px",
        "border_w": "0px",
        "shadow": "none",
    },
    "Viên thuốc": {
        "radius": "24px",
        "border_w": "1px",
        "shadow": "0 1px 2px rgba(0,0,0,0.04)",
    },
    "Bóng sâu": {
        "radius": "14px",
        "border_w": "0px",
        "shadow": "0 12px 32px rgba(0,0,0,0.16)",
    },
    "Viền nhấn": {
        "radius": "10px",
        "border_w": "2px",
        "shadow": "none",
        "border_image": "linear-gradient(var(--accent), var(--accent)) 1",
    },
    "Nền mờ nhẹ": {
        "radius": "14px",
        "border_w": "1px",
        "shadow": "0 4px 16px rgba(0,0,0,0.06)",
        "bg_override": "var(--card-tl)",
    },
    "Đổ tầng": {
        "radius": "10px",
        "border_w": "1px",
        "shadow": "0 1px 1px rgba(0,0,0,0.05), 0 4px 8px rgba(0,0,0,0.05), 0 12px 24px rgba(0,0,0,0.05)",
    },
    "Khắc chìm": {
        "radius": "10px",
        "border_w": "0px",
        "shadow": "inset 0 1px 4px rgba(0,0,0,0.18), inset 0 -1px 1px rgba(255,255,255,0.35)",
    },
    "Hào quang nhấn": {          # mặc định
        "radius": "12px",
        "border_w": "1px",
        "shadow": "0 0 0 1px var(--border), 0 10px 28px rgba(var(--accent-rgb),0.18)",
    },
}

# Mật độ bố cục thẻ (tab Tuỳ biến -> "4. Giao diện") -- trục độc lập, áp qua --card-pad/--card-gap
# CHỈ cho nhóm "thẻ nội dung chung" dùng padding/margin đồng nhất (xem các vị trí đã đổi sang
# var() cạnh --card-radius) -- KHÔNG áp cho thẻ có padding tinh chỉnh riêng theo nội dung đặc thù
# (.quotes-card, .dtl-track...). "Vừa" PHẢI giữ đúng giá trị gốc hiện tại. "Rất thoáng" thêm vào
# sau để 4 mức (đồng bộ với trục "Độ rộng nội dung" cũng 4 mức), tiếp tục đúng cấp số cộng đã có
# giữa 3 mức gốc (+4px/+6px pad, +4px gap mỗi bước).
CARD_DENSITY = {
    "Gọn": {"pad": "12px 14px", "gap": "6px 0"},
    "Vừa": {"pad": "16px 18px", "gap": "10px 0"},
    "Thoáng": {"pad": "20px 24px", "gap": "14px 0"},
    "Rất thoáng": {"pad": "24px 30px", "gap": "18px 0"},
}

# Độ rộng cột nội dung (tab Tuỳ biến -> "4. Giao diện") -- trục độc lập, áp qua --content-max-w cho
# .block-container (xem _MAIN_CSS). "Rộng" là mặc định. 4 mức cách đều 200px (xác nhận với người
# dùng: 1100/1300/1500/1700). Từ khi NAV chuyển sang sidebar trái (Phase 4 hướng B), 2 nút nổi "về
# đầu trang"/"Đồng bộ nhanh" không còn định vị theo mép cột nội dung nữa (bám thẳng mép phải
# viewport, xem CSS #app-scroll-top-btn/#app-sync-fab-btn) -- --content-half-w đã bỏ.
CONTENT_WIDTHS = {
    "Hẹp": 1100,
    "Vừa": 1300,
    "Rộng": 1500,
    "Rất rộng": 1700,
}

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
# QUAN TRỌNG: "Manrope" (font khung vỏ CỐ ĐỊNH cho sidebar/date-picker, xem _UI_FONT trong app.py)
# KHÔNG còn là 1 key trong dict này -- đã tách riêng khỏi trục "Font thân chữ" (đọc thẳng
# "Manrope-Variable" qua _body_font_b64(), không tra cứu qua BODY_FONTS[_UI_FONT] nữa) để các lựa
# chọn ở đây có thể thay hẳn mà không phá khung vỏ cố định. File Manrope-Variable-*.woff2 trong
# assets/fonts/ VẪN GIỮ NGUYÊN (đang dùng cho khung vỏ), dù không còn hiện trong danh sách lựa
# chọn này.
BODY_FONTS = {
    "Inter": {"family": "Inter", "file_prefix": "Inter-Variable"},          # mặc định
    "Source Sans 3": {"family": "Source Sans 3", "file_prefix": "SourceSans3-Variable"},
    "Newsreader": {"family": "Newsreader", "file_prefix": "Newsreader-Variable"},
    "Literata": {"family": "Literata", "file_prefix": "Literata-Variable"},
    "Bitter": {"family": "Bitter", "file_prefix": "Bitter-Variable"},
}

