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


# 8 lựa chọn màu accent (tab Tuỳ biến → "4. Giao diện"), người dùng tự chọn. Bộ thứ 2 (thay hẳn
# bộ "đất/mộc mạc" đồng sắc độ trước đó theo phản hồi trực tiếp của người dùng -- muốn đa dạng hơn
# hẳn, không chỉ xoay quanh vài tông nâu/xanh rêu gần nhau) -- 8 hue trải ĐỀU quanh vòng màu (đỏ ->
# cam -> vàng -> lục -> lam ngọc -> lam biển -> chàm -> hồng cổ) nhưng vẫn giữ cùng dải độ trầm/
# saturation trung bình như trước để không lạc hẳn sang tông "candy-bright" kiểu iOS. Ai đã lưu 1
# màu ở bộ cũ sẽ tự rơi về mặc định mới ở lần tải kế tiếp (xem nhánh fallback _accent_hex bên
# dưới). Bảng này TÁCH RIÊNG khỏi CHART_COLORS (bảng màu biểu đồ Nhóm/Dự án, hệ "Vintage bản đồ").
ACCENT_PRESETS = {
    "Đỏ gạch": "#b23a2f",
    "Cam cháy": "#c96a1f",
    "Vàng nghệ": "#c9971f",
    "Lục bảo": "#3a7d4f",
    "Ngọc lam": "#1f8f8a",
    "Lam biển": "#2f5fa3",       # mặc định
    "Chàm tím": "#5b4b8a",
    "Hồng cổ": "#a3456f",
}

# Kiểu nền trang (áp cho .stApp, xem rule CSS dùng var(--bg-image)/var(--bg-size)/var(--bg-position))
# -- "image"/"size"/"position" là giá trị CSS thô ghép thẳng vào background-image/size/position
# qua biến CSS, dùng var(--divider) để tự đổi theo IS_DARK như mọi hoạ tiết khác trong app. "Trơn"
# dùng image:none (hợp lệ) thay vì bỏ hẳn cặp thuộc tính, để 1 cơ chế var() duy nhất áp cho mọi
# lựa chọn, không cần nhánh riêng trong CSS chính. "position" mặc định "0 0" nếu không khai báo.
#
# Đợt đổi mới (xác nhận với người dùng: lấy nguyên 8 kiểu từ mockup "Tuỳ Chỉnh Giao Diện.dc.html",
# thay hẳn bộ "Chấm bi/Vũ trụ/Tartan/Argyle/Chevron/Quatrefoil/Xương cá" trước đó) -- chủ đề rừng/
# nhịp thời gian: Sương mai/Vòng tuổi/Vân gỗ/Lá rơi/Đường mòn/Giọt sương/Núi xa, cộng "Trơn" giữ
# nguyên. Mockup viết công thức bằng placeholder "INK" (màu mực suy theo độ sáng bảng màu nền tại
# thời điểm render) -- dịch thẳng sang var(--divider) sẵn có của app (cùng vai trò, tự đổi theo
# IS_DARK). "Sương mai" là mặc định mới (khớp state.pattern mặc định trong mockup), thay "Chấm bi"
# cũ -- xem fallback BG_STYLE bên dưới.
BG_PRESETS = {
    "Trơn": {
        "image": "none",
        "size": "auto",
    },
    "Sương mai": {
        # 5 lớp radial-gradient chấm nhỏ rải rác trong 1 ô 90x80 -> sương sớm lấm tấm, thưa hơn hẳn
        # "Vũ trụ" cũ.
        "image": ("radial-gradient(1.6px 1.6px at 12px 18px, var(--divider-on-bg), transparent), "
                   "radial-gradient(1.4px 1.4px at 55px 62px, var(--divider-on-bg), transparent), "
                   "radial-gradient(2.2px 2.2px at 78px 24px, var(--divider-on-bg), transparent), "
                   "radial-gradient(1.4px 1.4px at 30px 70px, var(--divider-on-bg), transparent), "
                   "radial-gradient(1.8px 1.8px at 68px 46px, var(--divider-on-bg), transparent)"),
        "size": "90px 80px",
    },
    "Vòng tuổi": {
        # 1 lớp repeating-radial-gradient tâm giữa ô -> các vòng tròn đồng tâm lặp lại, gợi vòng
        # năm của cây.
        "image": "repeating-radial-gradient(circle at 50% 50%, transparent 0 10px, var(--divider-on-bg) 10px 12px, transparent 12px 24px)",
        "size": "64px 64px",
    },
    "Vân gỗ": {
        # 2 lớp repeating-linear-gradient gần ngang, lệch góc rất nhẹ (0.8deg/-1.4deg) và chu kỳ
        # khác nhau -> thớ gỗ mộc mạc, không đều tăm tắp như kẻ ngang thường.
        "image": ("repeating-linear-gradient(0.8deg, var(--divider-on-bg) 0 1.5px, transparent 1.5px 11px), "
                   "repeating-linear-gradient(-1.4deg, var(--divider-on-bg) 0 1px, transparent 1px 17px)"),
        "size": "auto",
    },
    "Lá rơi": {
        # 5 lớp radial-gradient chấm cỡ lớn hơn "Sương mai", rải rác trong ô 130x110 -> lá rụng rải
        # rác cuối thu.
        "image": ("radial-gradient(3.4px 3.4px at 20px 30px, var(--divider-on-bg), transparent), "
                   "radial-gradient(2.8px 2.8px at 90px 80px, var(--divider-on-bg), transparent), "
                   "radial-gradient(4px 4px at 112px 36px, var(--divider-on-bg), transparent), "
                   "radial-gradient(3px 3px at 54px 96px, var(--divider-on-bg), transparent), "
                   "radial-gradient(2.6px 2.6px at 66px 12px, var(--divider-on-bg), transparent)"),
        "size": "130px 110px",
    },
    "Đường mòn": {
        # 1 lớp vạch chéo 45deg lặp lại, chu kỳ thưa (20px) -> lối đi trong rừng, mảnh/thưa hơn hẳn
        # "Argyle" cũ.
        "image": "repeating-linear-gradient(45deg, var(--divider-on-bg) 0 8px, transparent 8px 20px)",
        "size": "34px 34px",
    },
    "Giọt sương": {
        # 2 chấm nhỏ lệch nhau trong 1 ô 32x32 -> lưới hơi nước trên lá, thưa hơn "Chấm bi" cũ.
        "image": ("radial-gradient(2.2px 2.2px at 8px 8px, var(--divider-on-bg), transparent), "
                   "radial-gradient(2.2px 2.2px at 24px 24px, var(--divider-on-bg), transparent)"),
        "size": "32px 32px",
    },
    "Núi xa": {
        # 2 lớp linear-gradient góc 135/225 tạo hình răng cưa lặp lại -> đường chân trời xa, cùng
        # công thức gốc với "Chevron" cũ (chỉ 2 lớp thay vì 4, không cần lệch "position" riêng).
        # Phủ ~25% diện tích ô -> pha loãng còn 70% qua color-mix() như Chevron cũ để không đậm hơn
        # hẳn 7 hoạ tiết chấm/kẻ thưa còn lại.
        "image": ("linear-gradient(135deg, color-mix(in srgb, var(--divider-on-bg) 70%, transparent) 25%, transparent 25%), "
                   "linear-gradient(225deg, color-mix(in srgb, var(--divider-on-bg) 70%, transparent) 25%, transparent 25%)"),
        "size": "56px 30px",
    },
}

# Bảng màu nền (tab Tuỳ biến -> "4. Giao diện"), người dùng tự chọn -- mỗi entry bundle ĐỦ 13
# token (light, dark) dùng để dựng _TOK (xem khối :root gần cuối file): bg/card/card-tl/border/
# divider/divider-2/chip/text/text-2/text-3/text-4/text-on-bg/text-on-bg-2. Bundle cùng lúc (không
# cho đổi rời từng token) để tránh nền mới "đọ màu" với viền/chip/chữ cũ. 5 bảng gốc GIỮ ĐÚNG 4
# token chữ gốc (#211c13/#f1ece0 v.v., trước đây là hằng số riêng ngoài bundle) để không đổi gì cho
# người dùng chưa từng chọn. "Giấy ấm" PHẢI giữ đúng giá trị gốc.
#
# text/text-2/3/4: LUÔN là màu chữ dùng BÊN TRONG thẻ/card (nền var(--card)) -- cả 8 bảng đều dùng
# thẻ SÁNG + chữ TỐI (yêu cầu trực tiếp của người dùng: "ở các màu nền tối như bầu trời sao hay
# rừng đêm, tôi muốn nó vẫn là light theme, các card vẫn có màu sáng và chữ màu tối"), nên 8 bảng
# đều dùng chung đúng 1 cặp chữ tối/sáng theo IS_DARK như 5 bảng gốc -- không còn khác biệt riêng
# cho 3 bảng mới ở nhóm token này nữa (bản trước đây từng để "card"/"text" của Bầu trời sao/Rừng
# đêm tối theo màu nền, đã đổi lại theo phản hồi này).
#
# text-on-bg/text-on-bg-2: token MỚI, chỉ dùng cho phần chữ nằm TRỰC TIẾP trên nền trang
# (var(--bg), NGOÀI mọi card) -- ví dụ wordmark "Forest/Dashboard" ở header (_wordmark_html()), text
# phụ ở màn đăng nhập (_login_txt2). 6 bảng "nền nhạt" (Giấy ấm/Trắng tinh/Đá xanh/Lá non/Hoàng
# hôn/Sương tím) dùng LUÔN cặp text/text-2 (không có gì khác biệt). "Bầu trời sao"/"Rừng đêm" có
# var(--bg) đậm CỐ ĐỊNH bất kể
# IS_DARK (ý tưởng người dùng đề xuất: "ngay cả trong light theme vẫn dùng màu nền đậm hơn tạo
# tương phản") nên 2 bảng này cần cặp text-on-bg/text-on-bg-2 SÁNG cố định riêng (không đổi theo
# IS_DARK, y hệt cặp "text" cũ của 2 bảng này trước khi đổi sang light theme ở trên) để chữ trên nền
# đậm luôn đọc được, tách biệt hẳn khỏi cặp text/text-2 tối giờ dùng cho bên trong card.
BG_PALETTES = {
    "Giấy ấm": {
        "bg":        ("#f3efe4", "#1a1712"),
        "card":      ("#fdfbf5", "#262117"),
        "card-tl":   ("rgba(253,251,245,0.85)", "rgba(38,33,23,0.85)"),
        "border":    ("#ddd3b8", "#3c3628"),
        "divider":   ("rgba(33,28,19,0.14)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(33,28,19,0.2)", "rgba(255,255,255,0.17)"),
        "chip":      ("#ece4d0", "#322c20"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#211c13", "#f1ece0"),
        "text-on-bg-2": ("#6f6650", "#b3a688"),
    },
    # "Rượu vang"/"Đêm tía" thay "Trắng tinh"/"Đá xanh" (xác nhận với người dùng: 2 bảng nền đậm
    # cố định -- Bầu trời sao/Rừng đêm -- là hơi ít, cần thêm 2 tông đậm khác biệt hẳn về hue thay
    # cho 2 bảng nhạt). Cùng công thức "nền đậm cố định" với Bầu trời sao/Rừng đêm: bg ĐẬM ở CẢ 2
    # cột (khác 6 bảng "nền nhạt" -- bg chỉ đậm khi IS_DARK), card/border/chip/divider theo ĐÚNG
    # công thức bảng "nền nhạt" bình thường (thẻ sáng/tối theo IS_DARK như mọi bảng khác), còn
    # text-on-bg/text-on-bg-2 SÁNG CỐ ĐỊNH cả 2 cột (bg luôn đậm nên chữ trên nền luôn cần sáng).
    "Rượu vang": {
        "bg":        ("#3a1620", "#220c12"),
        "card":      ("#faf5f6", "#2d181c"),
        "card-tl":   ("rgba(250,245,246,0.85)", "rgba(45,24,28,0.85)"),
        "border":    ("#e3c9d0", "#492932"),
        "divider":   ("rgba(36,10,17,0.13)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(36,10,17,0.19)", "rgba(255,255,255,0.2)"),
        "chip":      ("#eddde1", "#3b2027"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#f5eaed", "#f5eaed"),
        "text-on-bg-2": ("#dbb3be", "#dbb3be"),
    },
    "Đêm tía": {
        "bg":        ("#2a1a3d", "#160d21"),
        "card":      ("#f8f5fc", "#21182d"),
        "card-tl":   ("rgba(248,245,252,0.85)", "rgba(33,24,45,0.85)"),
        "border":    ("#ddd0ef", "#372949"),
        "divider":   ("rgba(22,10,36,0.13)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(22,10,36,0.19)", "rgba(255,255,255,0.2)"),
        "chip":      ("#e9e1f5", "#2c203b"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#efeaf5", "#efeaf5"),
        "text-on-bg-2": ("#c5b3db", "#c5b3db"),
    },
    # 2 bảng dưới đây (Lá non/Hoàng hôn) + "Sương tím" (kế tiếp) lấy ĐÚNG bg/card/border từ mockup
    # "Tuỳ Chỉnh Giao Diện.dc.html" (xác nhận với người dùng thay hẳn bộ bảng cũ). Mockup chỉ cho
    # 1 mã màu/token (không phân biệt sáng/tối theo IS_DARK như app) -- biến thể "dark" (cột thứ 2
    # mỗi tuple) do agent tự suy ra bằng cách làm tối cùng tông (giữ nguyên hue, hạ độ sáng) theo
    # đúng công thức 5 bảng gốc đã áp dụng, xác nhận với người dùng chọn cách này thay vì dùng
    # nguyên 1 mã cho cả 2 chế độ.
    "Lá non": {
        "bg":        ("#e0ead4", "#161d0e"),
        "card":      ("#f8faf0", "#292d18"),
        "card-tl":   ("rgba(248,250,240,0.85)", "rgba(41,45,24,0.85)"),
        "border":    ("#bccca4", "#3d4929"),
        "divider":   ("rgba(27,38,13,0.13)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(27,38,13,0.19)", "rgba(255,255,255,0.17)"),
        "chip":      ("#ccdaba", "#333b20"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#211c13", "#f1ece0"),
        "text-on-bg-2": ("#6f6650", "#b3a688"),
    },
    "Hoàng hôn": {
        "bg":        ("#f3e0cb", "#1d160e"),
        "card":      ("#fdf5ec", "#2d2318"),
        "card-tl":   ("rgba(253,245,236,0.85)", "rgba(45,35,24,0.85)"),
        "border":    ("#dfbe9c", "#493a29"),
        "divider":   ("rgba(40,26,11,0.13)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(40,26,11,0.19)", "rgba(255,255,255,0.17)"),
        "chip":      ("#e8cdb1", "#3b2e20"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#211c13", "#f1ece0"),
        "text-on-bg-2": ("#6f6650", "#b3a688"),
    },
    "Sương tím": {
        "bg":        ("#e7e1f0", "#140e1d"),
        "card":      ("#faf8fd", "#20182d"),
        "card-tl":   ("rgba(250,248,253,0.85)", "rgba(32,24,45,0.85)"),
        "border":    ("#c8bbdd", "#362949"),
        "divider":   ("rgba(23,13,38,0.13)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(23,13,38,0.19)", "rgba(255,255,255,0.17)"),
        "chip":      ("#d6cce6", "#2b203b"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#211c13", "#f1ece0"),
        "text-on-bg-2": ("#6f6650", "#b3a688"),
    },
    # "Bầu trời sao"/"Rừng đêm": var(--bg) đậm CỐ ĐỊNH bất kể IS_DARK (ý tưởng người dùng), nhưng
    # card/border/divider/chip/text dùng công thức LIGHT THEME chuẩn (thẻ sáng, chữ tối) giống 5
    # bảng gốc -- chỉ text-on-bg/text-on-bg-2 (chữ nằm trực tiếp trên nền, ngoài card) mới cần cặp
    # sáng cố định riêng để đọc được trên nền đậm. Cả 2 bảng này TRÙNG KHỚP mockup sẵn (bg/card/
    # border cùng mã hex), không cần đổi gì.
    "Bầu trời sao": {
        "bg":        ("#232a4d", "#0d1024"),
        "card":      ("#f5f6fc", "#161a35"),
        "card-tl":   ("rgba(245,246,252,0.85)", "rgba(22,26,53,0.85)"),
        "border":    ("#d7dbf0", "#242a4a"),
        "divider":   ("rgba(20,24,45,0.12)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(20,24,45,0.18)", "rgba(255,255,255,0.2)"),
        "chip":      ("#e7e9f7", "#1a1f3c"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#eef0fb", "#eef0fb"),
        "text-on-bg-2": ("#b7bcdf", "#b7bcdf"),
    },
    "Rừng đêm": {
        "bg":        ("#1f3327", "#0d160f"),
        "card":      ("#f5f9f6", "#16211a"),
        "card-tl":   ("rgba(245,249,246,0.85)", "rgba(22,33,26,0.85)"),
        "border":    ("#d3e0d8", "#25382c"),
        "divider":   ("rgba(20,30,24,0.12)", "rgba(255,255,255,0.12)"),
        "divider-2": ("rgba(20,30,24,0.18)", "rgba(255,255,255,0.2)"),
        "chip":      ("#e5efe8", "#1a2a20"),
        "text":      ("#211c13", "#f1ece0"),
        "text-2":    ("#6f6650", "#b3a688"),
        "text-3":    ("#a39877", "#857a5f"),
        "text-4":    ("#cabf9d", "#4f483a"),
        "text-on-bg":   ("#eaf2ec", "#eaf2ec"),
        "text-on-bg-2": ("#a9c2b2", "#a9c2b2"),
    },
}

# 4 bảng "nền đậm cố định" (bg đậm ở CẢ 2 cột, xem chú thích trong BG_PALETTES) -- billboard
# (render_period_billboard()/_render_today_billboard()) PHẢI đọc nền SÁNG + chữ TỐI như 1 thẻ
# thật, KHÔNG hoà theo màu nền trang đậm phía sau (xác nhận với người dùng: billboard vẫn là
# "light theme" y hệt các bảng nền nhạt, chỉ có nền NGOÀI thẻ/billboard mới được phép đậm) -- xem
# _billboard_bg/_billboard_backdrop ngay dưới _root_vars.
BG_PALETTES_DARK_BG = {"Bầu trời sao", "Rừng đêm", "Rượu vang", "Đêm tía"}

# divider-on-bg: token riêng cho hoạ tiết nền (BG_PRESETS, vẽ trực tiếp lên var(--bg) qua
# --bg-image) -- KHÔNG dùng chung "divider" được nữa vì "divider" thiết kế cho viền/kẻ BÊN TRONG
# card (thẻ luôn sáng, xem chú thích trên BG_PALETTES), cột "light" của nó là mực TỐI. Với 4 bảng
# BG_PALETTES_DARK_BG, var(--bg) luôn ĐẬM bất kể IS_DARK -- dùng nguyên "divider" ở light theme sẽ
# ra mực tối vẽ trên nền đậm, hoạ tiết gần như vô hình (bug thật, ảnh chụp người dùng gửi ở "Đêm
# tía"). Lấy nguyên cột "dark" của divider (đã là màu sáng, tương phản tốt trên nền đậm) cho CẢ 2
# cột. 6 bảng "nền nhạt" còn lại giữ y hệt divider gốc -- không đổi hành vi cũ.
for _pal_name, _pal in BG_PALETTES.items():
    _pal["divider-on-bg"] = ((_pal["divider"][1], _pal["divider"][1]) if _pal_name in BG_PALETTES_DARK_BG
                              else _pal["divider"])

# Kiểu thẻ (tab Tuỳ biến -> "4. Giao diện") -- trục độc lập với bảng màu nền ở trên, áp dụng chung
# lên MỌI bảng màu qua 3 token CSS --card-radius/--card-border-w/--card-shadow. "Bo mềm" PHẢI giữ
# đúng công thức gốc (10px / 1px / box-shadow nhạt hiện tại) để không đổi gì cho người chưa chọn.
#
# 3 lựa chọn gốc chỉ cần đúng 3 token trên. 5 lựa chọn mới (xác nhận với người dùng qua mockup)
# thêm 3 KHOÁ TUỲ CHỌN "bg_override"/"backdrop"/"border_image" (mặc định var(--card)/none/none nếu
# không khai báo, xem _card_style_vars) -- 2 hiệu ứng "Kính mờ" (kính mờ thật, backdrop-filter +
# nền bán trong suốt card-tl có sẵn) và "Viền gradient" (viền đổi màu theo Accent) KHÔNG áp được
# chỉ qua radius/border_w/shadow (hàng chục nơi rải rác trong app tự viết riêng "border: var(
# --card-border-w) solid var(--border); background: var(--card);" theo TỪNG khối, không có 1 điểm
# nối chung để đổi border-style/background-image) -- xử lý bằng 1 rule CSS gộp DUY NHẤT, liệt kê
# lại đúng danh sách selector card đã rà soát (xem rule ngay sau _card_style_vars), đặt SAU mọi
# rule gốc trong cascade nên tự thắng mà không cần sửa từng nơi. Mặc định var(--card)/none/none
# khiến rule gộp này vô hại (không đổi gì) với 6 kiểu còn lại.
CARD_STYLES = {
    "Bo mềm": {
        "radius": "10px",
        "border_w": "1px",
        "shadow": "0 1px 1px rgba(0,0,0,0.02)",
    },
    "Vuông viền đậm": {
        "radius": "3px",
        "border_w": "1.5px",
        "shadow": "none",
    },
    "Nổi khối": {
        "radius": "12px",
        "border_w": "0.5px",
        "shadow": "0 6px 18px rgba(0,0,0,0.12)",
    },
    "Viền kép": {
        "radius": "6px",
        "border_w": "1px",
        "shadow": "0 0 0 3px var(--card), 0 0 0 4px var(--border)",
    },
    "Nổi mềm": {
        "radius": "16px",
        "border_w": "0px",
        "shadow": "0 2px 4px rgba(0,0,0,0.04), 0 14px 28px rgba(0,0,0,0.09)",
    },
    "Đóng dấu": {
        "radius": "10px",
        "border_w": "0px",
        "shadow": "inset 0 2px 6px rgba(0,0,0,0.15)",
    },
    "Kính mờ": {
        "radius": "14px",
        "border_w": "1px",
        "shadow": "0 8px 28px rgba(0,0,0,0.10)",
        "bg_override": "var(--card-tl)",
        "backdrop": "blur(14px)",
    },
    "Viền gradient": {
        "radius": "12px",
        "border_w": "2px",
        "shadow": "none",
        "border_image": "linear-gradient(135deg, var(--accent), transparent 75%) 1",
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
# dùng: 1100/1300/1500/1700). 2 nút nổi "về đầu trang"/"Đồng bộ nhanh" định vị theo --content-half-w
# (nửa giá trị đang chọn) để luôn bám đúng mép cột bất kể mức nào đang được chọn.
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
# "giao diện chung" (xác nhận với người dùng). 8 lựa chọn LẤY NGUYÊN từ mockup "Tuỳ Chỉnh Giao
# Diện.dc.html" (đủ dáng chữ khác biệt: sans nhân văn/hình học/bo tròn, serif, slab-serif, sans nén
# cao -- xem chú thích đầy đủ ở khai báo BODY_FONTS/_body_font_b64()).
# "file_prefix" khớp tên file trong assets/fonts/ (vd Manrope-Variable-latin.woff2), "family" là
# tên CSS font-family thật. "Manrope" PHẢI là mặc định (giữ nguyên hiện trạng cho người chưa từng
# chọn).
# Đợt đổi mới (xác nhận với người dùng: lấy nguyên 8 font từ mockup "Tuỳ Chỉnh Giao Diện.dc.html",
# thay hẳn "Inter"/"Public Sans"/"JetBrains Mono"/"Roboto" bằng "Be Vietnam Pro"/"Lora"/
# "Roboto Slab"/"Oswald" -- 4 font còn lại (Manrope/Plus Jakarta Sans/Nunito/Literata) TRÙNG với
# bộ cũ nên giữ nguyên file .woff2 sẵn có). "weights": Be Vietnam Pro KHÔNG có bản variable trên
# Google Fonts (chỉ có file tĩnh từng mức đậm riêng, khác 7 font còn lại) -- key này báo
# _body_font_b64()/_BODY_FONT_FACE nhúng NHIỀU file tĩnh (400/600/800, mỗi mức đủ 3 subset) thay
# vì 1 file biến trục duy nhất, để vẫn giữ được phân cấp đậm/nhạt (label/nút thường 400-600, tiêu
# đề/số liệu nhấn 700-800) -- trình duyệt tự chọn file GẦN NHẤT với font-weight CSS thực tế đang
# yêu cầu (không có nội suy liên tục như font biến trục, nhưng vẫn có 3 mức rõ rệt thay vì 1 mức
# phẳng lì). File đặt tên `<file_prefix>-<weight>-<subset>.woff2` (khác quy ước
# `<file_prefix>-<subset>.woff2` của font biến trục).
BODY_FONTS = {
    "Manrope": {"family": "Manrope", "file_prefix": "Manrope-Variable"},
    "Be Vietnam Pro": {"family": "Be Vietnam Pro", "file_prefix": "BeVietnamPro", "weights": (400, 600, 800)},
    "Plus Jakarta Sans": {"family": "Plus Jakarta Sans", "file_prefix": "PlusJakartaSans-Variable"},
    "Nunito": {"family": "Nunito", "file_prefix": "Nunito-Variable"},
    "Literata": {"family": "Literata", "file_prefix": "Literata-Variable"},
    "Lora": {"family": "Lora", "file_prefix": "Lora-Variable"},
    "Roboto Slab": {"family": "Roboto Slab", "file_prefix": "RobotoSlab-Variable"},
    "Oswald": {"family": "Oswald", "file_prefix": "Oswald-Variable"},
}

