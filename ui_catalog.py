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
#
# Đợt mở rộng thứ 3 (8 -> 20 kiểu, xếp lưới 4x5, cùng đợt với ACCENT_PRESETS/BG_PALETTES 8/9->20):
# giữ NGUYÊN 8 kiểu gốc, thêm 12 kiểu mới CÙNG 4 kỹ thuật CSS đã có (radial-gradient chấm/
# (repeating-)linear-gradient kẻ 1 lớp/lưới 2 lớp/lưới tam giác 3 lớp), chỉ đổi mật độ/góc/chu kỳ
# để lấp đủ biến thể còn thiếu của mỗi kỹ thuật (KHÔNG thêm kỹ thuật CSS mới) -- xếp theo nhóm
# trong dict để lưới 4x5 đọc mượt theo hàng: hàng 1 = họ chấm (Trơn + 4 mật độ), hàng 2 = họ kẻ
# ngang/dọc, hàng 3 = họ kẻ chéo + Ô vuông, hàng 4 = họ lưới 2-3 lớp còn lại.
BG_PRESETS = {
    "Trơn": {
        "image": "none",
        "size": "auto",
    },
    "Chấm li ti": {
        # Cùng công thức radial-gradient của "Lưới điểm" nhưng chấm nhỏ hơn + ô dày hơn -- mật độ
        # dày nhất trong họ chấm.
        "image": "radial-gradient(0.9px 0.9px at 1px 1px, var(--divider-on-bg), transparent)",
        "size": "14px 14px",
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
    "Chấm thưa": {
        # Cùng công thức, chấm to nhất + ô thưa nhất trong họ chấm -- mật độ đối lập "Chấm li ti".
        "image": "radial-gradient(3.4px 3.4px at 1px 1px, var(--divider-on-bg), transparent)",
        "size": "64px 64px",
    },
    "Kẻ ngang": {
        # 1 lớp repeating-linear-gradient ngang (0deg mặc định) -> vạch kẻ ngang mảnh đều, kiểu
        # "giấy kẻ dòng" -- khác hẳn mọi hoạ tiết chéo/chấm/tròn ở cả 2 bộ trước.
        "image": "repeating-linear-gradient(var(--divider-on-bg) 0 1px, transparent 1px 17px)",
        "size": "auto",
    },
    "Kẻ ngang thưa": {
        # Cùng "Kẻ ngang" (0deg), chu kỳ gấp đôi -- mật độ thưa hơn.
        "image": "repeating-linear-gradient(var(--divider-on-bg) 0 1px, transparent 1px 34px)",
        "size": "auto",
    },
    "Kẻ dọc": {
        # Cùng công thức "Kẻ ngang" nhưng xoay 90deg -- cặp hướng ngang/dọc như "Ô vuông" đã ghép 2
        # lớp, ở đây tách riêng từng hướng làm 2 lựa chọn độc lập.
        "image": "repeating-linear-gradient(90deg, var(--divider-on-bg) 0 1px, transparent 1px 17px)",
        "size": "auto",
    },
    "Kẻ dọc thưa": {
        # Cùng "Kẻ dọc", chu kỳ gấp đôi -- mật độ thưa hơn.
        "image": "repeating-linear-gradient(90deg, var(--divider-on-bg) 0 1px, transparent 1px 34px)",
        "size": "auto",
    },
    "Kẻ chéo": {
        # 1 lớp vạch chéo 60deg mảnh, chu kỳ thưa (26px) -- góc/chu kỳ khác hẳn "Đường mòn" cũ
        # (45deg, đoạn đứt 8px) để không lặp lại cảm giác cũ dù cùng kỹ thuật repeating-linear.
        "image": "repeating-linear-gradient(60deg, var(--divider-on-bg) 0 1px, transparent 1px 26px)",
        "size": "auto",
    },
    "Kẻ chéo trái": {
        # Cùng "Kẻ chéo" nhưng lật hướng (-60deg) -- cặp chéo phải/trái như Kẻ ngang/dọc ở trên.
        "image": "repeating-linear-gradient(-60deg, var(--divider-on-bg) 0 1px, transparent 1px 26px)",
        "size": "auto",
    },
    "Kẻ chéo 45": {
        # Cùng kỹ thuật, góc 45deg (dốc hơn 60deg) -- 1 góc chéo khác trong họ kẻ chéo.
        "image": "repeating-linear-gradient(45deg, var(--divider-on-bg) 0 1px, transparent 1px 24px)",
        "size": "auto",
    },
    "Kẻ chéo 30": {
        # Cùng kỹ thuật, góc 30deg (thoải hơn 60deg) -- góc chéo còn lại của họ, hoàn thiện đủ 3
        # mức góc (30/45/60deg) cho hoạ tiết kẻ chéo.
        "image": "repeating-linear-gradient(30deg, var(--divider-on-bg) 0 1px, transparent 1px 20px)",
        "size": "auto",
    },
    "Ô vuông": {
        # 2 lớp linear-gradient kẻ dọc + ngang mảnh -> lưới ô vuông kiểu giấy kẻ ly, công thức CSS
        # "graph paper" kinh điển, KHÔNG có trong bộ cũ (bộ cũ toàn hoạ tiết chấm/kẻ chéo/vòng tròn).
        "image": ("linear-gradient(var(--divider-on-bg) 1px, transparent 1px), "
                   "linear-gradient(90deg, var(--divider-on-bg) 1px, transparent 1px)"),
        "size": "42px 42px",
    },
    "Ô vuông nhỏ": {
        # Cùng công thức "Ô vuông", ô dày hơn hẳn -- mật độ lưới vuông khác.
        "image": ("linear-gradient(var(--divider-on-bg) 1px, transparent 1px), "
                   "linear-gradient(90deg, var(--divider-on-bg) 1px, transparent 1px)"),
        "size": "24px 24px",
    },
    "Ô chữ nhật": {
        # Cùng công thức "Ô vuông" nhưng kích thước ô KHÔNG đều 2 trục (24x48) -- lưới chữ nhật
        # thay vì vuông, biến thể duy nhất đổi tỉ lệ ô thay vì chỉ đổi mật độ đều.
        "image": ("linear-gradient(var(--divider-on-bg) 1px, transparent 1px), "
                   "linear-gradient(90deg, var(--divider-on-bg) 1px, transparent 1px)"),
        "size": "24px 48px",
    },
    "Kim cương": {
        # 2 lớp linear-gradient chéo 45/-45deg giao nhau -> lưới hình thoi (kim cương/argyle mảnh),
        # công thức khác hẳn "Núi xa" cũ (Núi xa dùng 2 lớp CÙNG chiều lệch để tạo răng cưa, không
        # giao nhau thành ô kín).
        "image": ("linear-gradient(45deg, var(--divider-on-bg) 1px, transparent 1px), "
                   "linear-gradient(-45deg, var(--divider-on-bg) 1px, transparent 1px)"),
        "size": "34px 34px",
    },
    "Kim cương nhỏ": {
        # Cùng công thức "Kim cương", ô dày hơn -- mật độ lưới thoi khác.
        "image": ("linear-gradient(45deg, var(--divider-on-bg) 1px, transparent 1px), "
                   "linear-gradient(-45deg, var(--divider-on-bg) 1px, transparent 1px)"),
        "size": "20px 20px",
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
    "Vân lưới thưa": {
        # Cùng công thức "Vân lưới", chu kỳ gấp rưỡi -- mật độ thưa hơn cho lưới tam giác.
        "image": ("repeating-linear-gradient(0deg, var(--divider-on-bg) 0 1px, transparent 1px 50px), "
                   "repeating-linear-gradient(60deg, var(--divider-on-bg) 0 1px, transparent 1px 50px), "
                   "repeating-linear-gradient(120deg, var(--divider-on-bg) 0 1px, transparent 1px 50px)"),
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
# khác", kể cả bảng mặc định). 9 bảng dựng theo 1 CÔNG THỨC HSL nhất quán (khác cách hand-pick tự
# do trước đây) để đảm bảo tương phản/hài hoà mà không cần tinh chỉnh từng mã hex riêng lẻ -- 5
# bảng "nền nhạt" giữ nguyên hue xuyên suốt bg/card/border/chip (bg: S34% L87.5%/8.4%, card: S40%
# L96.5%/13.5%, border: S28% L72%/22%, chip: S30% L79%/17.5%), 4 bảng "nền đậm cố định" dùng công
# thức riêng (bg S~24-36% L16-20% CỐ ĐỊNH cả 2 cột, card/border/chip theo công thức riêng sáng hơn,
# text-on-bg S24% L93%/text-on-bg-2 S17% L71% CỐ ĐỊNH cả 2 cột).
#
# Đợt mở rộng thứ 3 (9 -> 20 bảng, xếp lưới 4x5, xác nhận với người dùng -- cùng đợt với
# ACCENT_PRESETS 8->20): thêm 5 hue cho "nền nhạt" (Hồng đào/Xanh cốm/Lá mạ/Ngọc bích/Tím chàm) và
# 6 hue cho "nền đậm cố định" (Ô liu/Lục rừng/Lục bảo/Chàm than/Tím than/Rượu vang) vào ĐÚNG khoảng
# trống lớn nhất quanh vòng màu của mỗi nhóm 9 hue cũ, dùng LẠI Y HỆT 2 công thức HSL trên (chỉ đổi
# hue) -- KHÔNG đổi hue/công thức của 9 bảng gốc để không phá lựa chọn người dùng đã lưu.
#
# text/text-2/3/4: LUÔN là màu chữ dùng BÊN TRONG thẻ/card (nền var(--card)) -- cả 20 bảng đều dùng
# thẻ SÁNG + chữ TỐI (yêu cầu trực tiếp của người dùng, giữ nguyên từ đợt trước: "các card vẫn có
# màu sáng và chữ màu tối" kể cả ở bảng nền đậm), nên dùng chung đúng 1 cặp chữ tối/sáng
# (#211c13/#f1ece0 v.v., KHÔNG đổi -- vẫn là hằng số gốc của app, độc lập với bảng màu nền đang
# chọn) cho MỌI bảng, không có khác biệt riêng theo bảng.
#
# text-on-bg/text-on-bg-2: token MỚI, chỉ dùng cho phần chữ nằm TRỰC TIẾP trên nền trang
# (var(--bg), NGOÀI mọi card) -- ví dụ wordmark "Forest/Dashboard" ở header (_wordmark_html()), text
# phụ ở màn đăng nhập (_login_txt2). 10 bảng "nền nhạt" dùng LUÔN cặp text/text-2 (không có gì khác
# biệt). 10 bảng "nền đậm cố định" có var(--bg) đậm CỐ ĐỊNH bất kể IS_DARK nên cần cặp text-on-bg/
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
    # 5 bảng "nền nhạt" MỚI (đợt mở rộng 9 -> 20 màu, xếp lưới 4x5) -- CÙNG ĐÚNG công thức HSL của
    # 5 bảng nền nhạt trên (bg: S34.4%/L87.5% sáng, S34.9%/L8.4% tối; card: S41.2%/L96.7% sáng,
    # S24.6%/L13.5% tối; border: S28.2%/L72.2% sáng, S28.6%/L22% tối; chip: S30.8%/L79% sáng,
    # S25.8%/L17.5% tối; divider/divider-2 = nền tối HSL(hue, 49%, 10%) ở cột sáng, trắng cố định ở
    # cột tối), CHỈ đổi hue -- 5 hue mới chọn để lấp đúng khoảng trống lớn nhất giữa 5 hue cũ (166°
    # Bạc hà/204° Xanh da trời/276° Tím oải hương/344° Hồng phấn/48° Vàng bơ) quanh vòng màu, đưa
    # tổng 10 bảng nhạt về gần đều 36°/hue (giống cách ACCENT_PRESETS đã mở rộng 8→20).
    "Hồng đào": {
        "bg":        ("#ead4d4", "#1d0e0e"),
        "card":      ("#faf3f3", "#2b1a1a"),
        "card-tl":   ("rgba(250,243,243,0.85)", "rgba(43,26,26,0.85)"),
        "border":    ("#cca4a4", "#482828"),
        "divider":   ("rgba(38,13,13,0.14)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(38,13,13,0.2)", "rgba(255,255,255,0.17)"),
        "chip":      ("#dab9b9", "#382121"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#211c13", "#f1ece0"),
        "text-on-bg-2": ("#6f6650", "#b3a688"),
    },
    "Xanh cốm": {
        "bg":        ("#e6ead4", "#1a1d0e"),
        "card":      ("#f9faf3", "#282b1a"),
        "card-tl":   ("rgba(249,250,243,0.85)", "rgba(40,43,26,0.85)"),
        "border":    ("#c4cca4", "#424828"),
        "divider":   ("rgba(33,38,13,0.14)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(33,38,13,0.2)", "rgba(255,255,255,0.17)"),
        "chip":      ("#d3dab9", "#343821"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#211c13", "#f1ece0"),
        "text-on-bg-2": ("#6f6650", "#b3a688"),
    },
    "Lá mạ": {
        "bg":        ("#d9ead4", "#111d0e"),
        "card":      ("#f5faf3", "#1d2b1a"),
        "card-tl":   ("rgba(245,250,243,0.85)", "rgba(29,43,26,0.85)"),
        "border":    ("#accca4", "#2e4828"),
        "divider":   ("rgba(18,38,13,0.14)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(18,38,13,0.2)", "rgba(255,255,255,0.17)"),
        "chip":      ("#c0dab9", "#263821"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#211c13", "#f1ece0"),
        "text-on-bg-2": ("#6f6650", "#b3a688"),
    },
    "Ngọc bích": {
        "bg":        ("#d4eadd", "#0e1d14"),
        "card":      ("#f3faf6", "#1a2b21"),
        "card-tl":   ("rgba(243,250,246,0.85)", "rgba(26,43,33,0.85)"),
        "border":    ("#a4ccb4", "#284835"),
        "divider":   ("rgba(13,38,23,0.14)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(13,38,23,0.2)", "rgba(255,255,255,0.17)"),
        "chip":      ("#b9dac6", "#21382a"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#211c13", "#f1ece0"),
        "text-on-bg-2": ("#6f6650", "#b3a688"),
    },
    "Tím chàm": {
        "bg":        ("#d9d4ea", "#110e1d"),
        "card":      ("#f5f3fa", "#1d1a2b"),
        "card-tl":   ("rgba(245,243,250,0.85)", "rgba(29,26,43,0.85)"),
        "border":    ("#aca4cc", "#2e2848"),
        "divider":   ("rgba(18,13,38,0.14)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(18,13,38,0.2)", "rgba(255,255,255,0.17)"),
        "chip":      ("#c0b9da", "#262138"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#211c13", "#f1ece0"),
        "text-on-bg-2": ("#6f6650", "#b3a688"),
    },
    # 4 bảng dưới đây: "nền đậm cố định" -- bg ĐẬM ở CẢ 2 cột (khác 10 bảng "nền nhạt" trên -- bg chỉ
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
    # 6 bảng "nền đậm cố định" MỚI (đợt mở rộng 9 -> 20 màu) -- CÙNG ĐÚNG công thức HSL của 4 bảng
    # trên (bg: S35.8%/L15.9% cố định cả 2 cột; card: S25%/L96.9% sáng, S21.4%/L11% tối; border:
    # S16.9%/L84.9% sáng, S19.6%/L18% tối; chip: S22%/L92% sáng, S22.4%/L13.1% tối; divider/
    # divider-2 = HSL(hue, 51.2%, 8%) ở cột sáng, trắng cố định ở cột tối; text-on-bg: HSL(hue,
    # 22.2%, 92.9%) cố định cả 2 cột; text-on-bg-2: HSL(hue, 17.6%, 71%) cố định cả 2 cột), CHỈ đổi
    # hue -- 6 hue mới lấp khoảng trống giữa 4 hue cũ (195° Lam thẳm/25° Nâu hạt dẻ/220° Xám than -
    # gam xám trung tính/15° Đất nung) để 10 bảng đậm cũng phủ gần đều quanh vòng màu như 10 bảng
    # nhạt ở trên.
    "Ô liu": {
        "bg":        ("#31371a", "#31371a"),
        "card":      ("#f8f9f5", "#202216"),
        "card-tl":   ("rgba(248,249,245,0.85)", "rgba(32,34,22,0.85)"),
        "border":    ("#dcdfd2", "#333725"),
        "divider":   ("rgba(27,31,10,0.13)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(27,31,10,0.19)", "rgba(255,255,255,0.2)"),
        "chip":      ("#edefe6", "#26291a"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#eff1e9", "#eff1e9"),
        "text-on-bg-2": ("#bdc2a8", "#bdc2a8"),
    },
    "Lục rừng": {
        "bg":        ("#20371a", "#20371a"),
        "card":      ("#f6f9f5", "#182216"),
        "card-tl":   ("rgba(246,249,245,0.85)", "rgba(24,34,22,0.85)"),
        "border":    ("#d5dfd2", "#293725"),
        "divider":   ("rgba(14,31,10,0.13)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(14,31,10,0.19)", "rgba(255,255,255,0.2)"),
        "chip":      ("#e8efe6", "#1d291a"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#eaf1e9", "#eaf1e9"),
        "text-on-bg-2": ("#adc2a8", "#adc2a8"),
    },
    "Lục bảo": {
        "bg":        ("#1a3726", "#1a3726"),
        "card":      ("#f5f9f7", "#16221b"),
        "card-tl":   ("rgba(245,249,247,0.85)", "rgba(22,34,27,0.85)"),
        "border":    ("#d2dfd7", "#25372c"),
        "divider":   ("rgba(10,31,18,0.13)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(10,31,18,0.19)", "rgba(255,255,255,0.2)"),
        "chip":      ("#e6efea", "#1a2920"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#e9f1ec", "#e9f1ec"),
        "text-on-bg-2": ("#a8c2b2", "#a8c2b2"),
    },
    "Chàm than": {
        "bg":        ("#201a37", "#201a37"),
        "card":      ("#f6f5f9", "#181622"),
        "card-tl":   ("rgba(246,245,249,0.85)", "rgba(24,22,34,0.85)"),
        "border":    ("#d5d2df", "#292537"),
        "divider":   ("rgba(14,10,31,0.13)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(14,10,31,0.19)", "rgba(255,255,255,0.2)"),
        "chip":      ("#e8e6ef", "#1d1a29"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#eae9f1", "#eae9f1"),
        "text-on-bg-2": ("#ada8c2", "#ada8c2"),
    },
    "Tím than": {
        "bg":        ("#311a37", "#311a37"),
        "card":      ("#f8f5f9", "#201622"),
        "card-tl":   ("rgba(248,245,249,0.85)", "rgba(32,22,34,0.85)"),
        "border":    ("#dcd2df", "#332537"),
        "divider":   ("rgba(27,10,31,0.13)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(27,10,31,0.19)", "rgba(255,255,255,0.2)"),
        "chip":      ("#ede6ef", "#261a29"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#efe9f1", "#efe9f1"),
        "text-on-bg-2": ("#bda8c2", "#bda8c2"),
    },
    "Rượu vang": {
        "bg":        ("#371a2b", "#371a2b"),
        "card":      ("#f9f5f7", "#22161d"),
        "card-tl":   ("rgba(249,245,247,0.85)", "rgba(34,22,29,0.85)"),
        "border":    ("#dfd2da", "#372530"),
        "divider":   ("rgba(31,10,22,0.13)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(31,10,22,0.19)", "rgba(255,255,255,0.2)"),
        "chip":      ("#efe6eb", "#291a23"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#f1e9ee", "#f1e9ee"),
        "text-on-bg-2": ("#c2a8b8", "#c2a8b8"),
    },
}

# 10 bảng "nền đậm cố định" (bg đậm ở CẢ 2 cột, xem chú thích trong BG_PALETTES) -- billboard
# (render_period_billboard()/_render_today_billboard()) PHẢI đọc nền SÁNG + chữ TỐI như 1 thẻ
# thật, KHÔNG hoà theo màu nền trang đậm phía sau (xác nhận với người dùng: billboard vẫn là
# "light theme" y hệt các bảng nền nhạt, chỉ có nền NGOÀI thẻ/billboard mới được phép đậm) -- xem
# _billboard_bg/_billboard_backdrop ngay dưới _root_vars.
BG_PALETTES_DARK_BG = {"Lam thẳm", "Nâu hạt dẻ", "Xám than", "Đất nung",
                        "Ô liu", "Lục rừng", "Lục bảo", "Chàm than", "Tím than", "Rượu vang"}

# divider-on-bg: token riêng cho hoạ tiết nền (BG_PRESETS, vẽ trực tiếp lên var(--bg) qua
# --bg-image) -- KHÔNG dùng chung "divider" được nữa vì "divider" thiết kế cho viền/kẻ BÊN TRONG
# card (thẻ luôn sáng, xem chú thích trên BG_PALETTES), cột "light" của nó là mực TỐI. Với 10 bảng
# BG_PALETTES_DARK_BG, var(--bg) luôn ĐẬM bất kể IS_DARK -- dùng nguyên "divider" ở light theme sẽ
# ra mực tối vẽ trên nền đậm, hoạ tiết gần như vô hình (bug thật, ảnh chụp người dùng gửi ở bảng
# nền đậm cố định thời bộ cũ). Lấy nguyên cột "dark" của divider (đã là màu sáng, tương phản tốt
# trên nền đậm) cho CẢ 2 cột. 10 bảng "nền nhạt" còn lại giữ y hệt divider gốc -- không đổi hành vi cũ.
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
#
# Đợt mở rộng thứ 3 (8 -> 20 kiểu, xếp lưới 4x5, cùng đợt với ACCENT_PRESETS/BG_PALETTES/BG_PRESETS
# 8/9->20): giữ NGUYÊN 8 kiểu gốc (kể cả "Hào quang nhấn" mặc định), thêm 12 kiểu mới VẪN dùng
# ĐÚNG 6 khoá cơ chế cũ (radius/border_w/shadow + bg_override/backdrop/border_image tuỳ chọn),
# KHÔNG thêm khoá/CSS mới -- mỗi kiểu mới lấp 1 khoảng trống rõ ràng trong không gian phối hợp
# radius/viền/bóng/nền mà 8 kiểu gốc chưa chạm tới (góc vuông tuyệt đối, viền dày, bóng nhẹ/rất
# sâu, viền đôi qua box-shadow ring, viền gradient hướng khác, nền chip/nền gradient thay nền
# trắng, kính mờ THẬT có backdrop-filter -- token này có sẵn từ đầu nhưng CHƯA kiểu nào dùng tới,
# bóng khối phẳng kiểu neubrutalism, viền nổi/bevel).
#
# Đợt bổ sung thứ 4 (20 -> 21 kiểu, KHÔNG còn khớp lưới 4x5 đều -- hàng cuối chỉ 1 ô, chấp nhận
# vì đây là bổ sung 1 kiểu đơn lẻ theo yêu cầu người dùng, không phải đợt mở rộng tròn số như 3
# đợt trước): "Vạch đỉnh" lấy cảm hứng từ 1 mockup người dùng duyệt qua `/design` (thẻ có vạch màu
# mảnh phía trên) -- dựng bằng ĐÚNG token "shadow" sẵn có (inset box-shadow lệch xuống, kỹ thuật
# "border qua box-shadow" kinh điển), không thêm khoá/cơ chế mới.
CARD_STYLES = {
    "Phẳng lì": {
        "radius": "4px",
        "border_w": "0px",
        "shadow": "none",
    },
    "Vuông nhọn": {
        # Góc vuông TUYỆT ĐỐI (radius 0, khác "Phẳng lì" vẫn còn bo 4px), có viền mảnh -- 1 đầu
        # thái cực khác trong trục "độ bo góc" mà bộ gốc chưa chạm tới.
        "radius": "0px",
        "border_w": "1px",
        "shadow": "none",
    },
    "Bo vừa": {
        # Mức bo góc TRUNG GIAN (8px) giữa "Phẳng lì" (4px) và "Viên thuốc" (24px), kèm bóng rất
        # nhẹ -- lấp khoảng trống giữa 2 thái cực bo góc của bộ gốc.
        "radius": "8px",
        "border_w": "1px",
        "shadow": "0 1px 3px rgba(0,0,0,0.05)",
    },
    "Viên thuốc": {
        "radius": "24px",
        "border_w": "1px",
        "shadow": "0 1px 2px rgba(0,0,0,0.04)",
    },
    "Viền dày": {
        # border_w 3px (dày gấp 3 mọi kiểu có viền khác trong bộ gốc, tối đa trước đó là 2px ở
        # "Viền nhấn") -- nhấn viền bằng ĐỘ DÀY thay vì màu/gradient.
        "radius": "6px",
        "border_w": "3px",
        "shadow": "none",
    },
    "Bóng sâu": {
        "radius": "14px",
        "border_w": "0px",
        "shadow": "0 12px 32px rgba(0,0,0,0.16)",
    },
    "Bóng nhẹ": {
        # 1 lớp shadow đơn NHẸ hơn hẳn "Bóng sâu" -- lấp mức "hơi nổi" còn thiếu giữa "Phẳng lì"
        # (không bóng) và "Bóng sâu" (bóng đậm).
        "radius": "12px",
        "border_w": "0px",
        "shadow": "0 2px 8px rgba(0,0,0,0.07)",
    },
    "Lơ lửng": {
        # Bóng đơn lớn/đậm hơn CẢ "Bóng sâu" -- thái cực "nổi cao nhất" trong trục độ sâu bóng.
        "radius": "18px",
        "border_w": "0px",
        "shadow": "0 24px 48px rgba(0,0,0,0.22)",
    },
    "Viền nhấn": {
        "radius": "10px",
        "border_w": "2px",
        "shadow": "none",
        "border_image": "linear-gradient(var(--accent), var(--accent)) 1",
    },
    "Viền chuyển sắc": {
        # border_image dùng dải gradient Accent -> trong suốt (khác "Viền nhấn" ĐẶC 1 màu, và khác
        # hẳn "Viền gradient" đã retired ở bộ 2 -- hướng 135deg + điểm dừng transparent riêng, chưa
        # dùng ở đợt nào trước).
        "radius": "12px",
        "border_w": "2px",
        "shadow": "none",
        "border_image": "linear-gradient(135deg, var(--accent), transparent) 1",
    },
    "Viền đôi": {
        # Ring viền kép dựng thuần bằng box-shadow (2 lớp 0-blur offset khác bán kính) -- viền
        # NGOÀI border_w gốc còn có 1 vòng viền phụ tách rời bằng khe hở var(--card), hiệu ứng
        # CHƯA kiểu nào trong bộ gốc dùng box-shadow để vẽ viền thay vì đổ bóng.
        "radius": "10px",
        "border_w": "1px",
        "shadow": "0 0 0 4px var(--card), 0 0 0 5px var(--border)",
    },
    "Nền mờ nhẹ": {
        "radius": "14px",
        "border_w": "1px",
        "shadow": "0 4px 16px rgba(0,0,0,0.06)",
        "bg_override": "var(--card-tl)",
    },
    "Kính mờ": {
        # bg_override var(--card-tl) GIỐNG "Nền mờ nhẹ" nhưng BẬT THÊM backdrop-filter blur+saturate
        # -- token "backdrop" tồn tại sẵn trong cơ chế 3+3 từ đầu nhưng CHƯA kiểu nào trong 8 kiểu
        # gốc thực sự dùng tới, đây là hiệu ứng kính mờ THẬT (frosted glass) đầu tiên của bộ 3.
        "radius": "14px",
        "border_w": "1px",
        "shadow": "0 4px 16px rgba(0,0,0,0.08)",
        "bg_override": "var(--card-tl)",
        "backdrop": "blur(12px) saturate(1.4)",
    },
    "Nền chip": {
        # bg_override var(--chip) -- thay nền thẻ bằng đúng tông "chip" (đậm hơn card 1 bậc) thay
        # vì lớp bán trong suốt (--card-tl) như 2 kiểu trên -- 1 bề mặt ĐẶC khác màu, không phải
        # hiệu ứng trong suốt/kính.
        "radius": "10px",
        "border_w": "1px",
        "shadow": "none",
        "bg_override": "var(--chip)",
    },
    "Nền chuyển sắc": {
        # bg_override nhận thẳng 1 gradient (background là shorthand, chấp nhận gradient) thay vì
        # 1 màu/token đơn -- card -> card-tl chéo 160deg, hiệu ứng bề mặt 2 tông CHƯA kiểu nào
        # trong 2 bộ trước dùng.
        "radius": "12px",
        "border_w": "1px",
        "shadow": "none",
        "bg_override": "linear-gradient(160deg, var(--card) 0%, var(--card-tl) 100%)",
    },
    "Đổ tầng": {
        "radius": "10px",
        "border_w": "1px",
        "shadow": "0 1px 1px rgba(0,0,0,0.05), 0 4px 8px rgba(0,0,0,0.05), 0 12px 24px rgba(0,0,0,0.05)",
    },
    "Bóng khối": {
        # Shadow offset PHẲNG không blur (kiểu "neubrutalism"/sticker) thay vì mọi shadow mờ dần
        # trong bộ gốc -- cạnh sắc, cảm giác thẻ "dán chồng" lên 1 khối đặc phía sau.
        "radius": "8px",
        "border_w": "1px",
        "shadow": "3px 3px 0 var(--border)",
    },
    "Khắc chìm": {
        "radius": "10px",
        "border_w": "0px",
        "shadow": "inset 0 1px 4px rgba(0,0,0,0.18), inset 0 -1px 1px rgba(255,255,255,0.35)",
    },
    "Viền nổi": {
        # 1 lớp inset sáng mảnh (bevel/highlight cạnh trên) + 1 lớp shadow đổ ngoài nhẹ -- kết hợp
        # NGƯỢC "Khắc chìm" (khắc chìm dùng 2 lớp inset, không lớp nào đổ RA ngoài) -- cảm giác nổi
        # nhẹ có viền sáng thay vì lõm.
        "radius": "10px",
        "border_w": "1px",
        "shadow": "inset 0 1px 0 rgba(255,255,255,0.5), 0 2px 4px rgba(0,0,0,0.08)",
    },
    "Hào quang nhấn": {          # mặc định
        "radius": "12px",
        "border_w": "1px",
        "shadow": "0 0 0 1px var(--border), 0 10px 28px rgba(var(--accent-rgb),0.18)",
    },
    # Đợt bổ sung thứ 4 (20 -> 21 kiểu, lấy cảm hứng từ 1 mockup người dùng gửi -- trang tham khảo
    # có mỗi thẻ 1 vạch màu mảnh phía trên). "Vạch đỉnh" dựng vạch đó bằng inset box-shadow lệch
    # xuống 4px, blur=0 (kỹ thuật CSS kinh điển "border qua box-shadow") -- CHỈ dùng ĐÚNG token
    # "shadow" đã có, KHÔNG thêm khoá/cơ chế mới. Dùng var(--accent) (không phải màu cố định) để
    # vạch đổi màu theo đúng accent đang chọn, nhất quán với "Hào quang nhấn" cũng tô theo accent.
    "Vạch đỉnh": {
        "radius": "10px",
        "border_w": "1px",
        "shadow": "inset 0 4px 0 0 var(--accent), 0 1px 2px rgba(0,0,0,0.05)",
    },
}

# Trục "Mật độ bố cục" (CARD_DENSITY) đã BỎ theo yêu cầu người dùng -- --card-pad/--card-gap giờ
# là 2 hằng số CSS cố định (khớp đúng giá trị "Vừa" cũ) khai báo thẳng trong _card_style_vars ở
# app.py, không còn setting/UI chọn lựa. Xem lịch sử ở git nếu cần khôi phục.

# Độ rộng cột nội dung (tab Tuỳ biến -> "4. Giao diện") -- trục độc lập, áp qua --content-max-w cho
# .block-container (xem _MAIN_CSS). "Rộng" là mặc định. 5 mức cách đều 200px (xác nhận với người
# dùng: 1100/1300/1500/1700/1900 -- thêm "Cực rộng" 1900 nối tiếp đúng cấp số cộng 200px đã có,
# phục vụ thêm màn hình 5K/ultrawide). Từ khi NAV chuyển sang sidebar trái (Phase 4 hướng B), 2 nút
# nổi "về đầu trang"/"Đồng bộ nhanh" không còn định vị theo mép cột nội dung nữa (bám thẳng mép phải
# viewport, xem CSS #app-scroll-top-btn/#app-sync-fab-btn) -- --content-half-w đã bỏ.
CONTENT_WIDTHS = {
    "Hẹp": 1100,
    "Vừa": 1300,
    "Rộng": 1500,
    "Rất rộng": 1700,
    "Cực rộng": 1900,
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

