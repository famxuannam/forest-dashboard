"""Trang Hướng dẫn: nội dung người dùng cuối và bố cục render."""

def render_help_page(*, st, json, health_metrics_json_example, render_period_billboard,
                     sec_chapter, sec_block, sec_kbd, sec_table, help_faq_item,
                     render_help_changelog):
    # Trang Trợ giúp: tour cuộn dọc theo hành trình 1 ngày sử dụng (thay cho 8 sub-tab ngang
    # + screenshot của bản cũ). Toàn bộ minh hoạ vẽ thuần HTML/CSS bằng token màu (var(--accent-rgb),
    # var(--chip)...) nên tự ăn theo dark mode lẫn màu accent đang chọn, không cần chụp lại ảnh
    # theo theme như thời còn assets/help/. Nội dung mỗi chương chỉ giữ phần "luật ngầm" của app
    # (ngữ nghĩa đồng bộ, timezone, cách đọc số) — phần mô tả hiển nhiên nhìn UI là hiểu thì bỏ.
    
    # --- Billboard + mục lục -- render_period_billboard() (KHÔNG phải sec_hero() cũ, đã bỏ) để
    # đồng bộ đúng màu nền/viền "kính mờ" (frosted glass) với billboard mọi trang khác (Hôm nay/
    # Báo cáo/Sách/Gundam/Sức khoẻ/Tuỳ biến) -- xác nhận với người dùng: sec_hero() nền phẳng +
    # viền mảnh trông khác biệt, không còn lý do giữ ngoại lệ riêng cho trang này. Số to bên trái
    # lấy TỪ ĐÚNG entry mới nhất của HELP_CHANGELOG (chương 9 bên dưới) -- 2 giá trị này PHẢI sửa
    # cùng lúc mỗi khi thêm entry mới (đúng quy ước "số tĩnh, điền tay" đã áp dụng cho cả
    # HELP_CHANGELOG, xem docstring render_help_changelog()).
    _help_latest_date, _help_latest_lines = "19/08/2026", 14157
    render_period_billboard(
        "Trợ giúp", str(_help_latest_lines), "dòng mã nguồn", f"Cập nhật gần nhất {_help_latest_date}",
        "<div class='pbill-title'>Xin chào, đây là một lượt dạo qua Forest Dashboard</div>"
        # Rút gọn từ 1 đoạn văn dài ~7 câu xuống 3 câu ngắn (xác nhận với người dùng: billboard
        # cần gọn, không phải nơi đọc văn xuôi) -- giữ đúng 3 ý cốt lõi cũ: (1) app chỉ hồi cứu,
        # không giám sát/thúc ép, (2) hướng dẫn đi theo nhịp 1 ngày rồi mở rộng ra tuần/tháng/năm,
        # (3) đọc nhanh hoặc lướt mục lục vào thẳng phần cần. Nội dung đầy đủ hơn đã có sẵn trong
        # từng chương bên dưới, billboard không cần lặp lại chi tiết.
        "<div class='pbill-sub'>Đây không phải một người giám sát nhắc việc — không mục tiêu, không "
        "thúc ép, chỉ lặng lẽ ghi lại những gì Forest đã lưu để bạn xem lại khi thuận tiện. Hướng dẫn "
        "đi theo đúng nhịp một ngày: sáng định hướng, trong ngày cứ làm việc, tối khép lại — rồi mở "
        "rộng dần ra tuần, tháng, năm. Đọc hết mất chừng một khoảng trà, hoặc lướt mục lục bên phải "
        "để vào thẳng phần đang cần.</div>",
        [("help-ch1", "1 · Buổi sáng"), ("help-ch2", "2 · Trong ngày"),
         ("help-ch3", "3 · Cuối ngày"), ("help-ch4", "4 · Tuần &amp; tháng"),
         ("help-ch5", "5 · Sách · Gundam · Sức khoẻ"), ("help-ch6", "6 · Dữ liệu &amp; đồng bộ"),
         ("help-ch7", "7 · Tuỳ biến"), ("help-ch8", "8 · Câu hỏi thường gặp"),
         ("help-ch9", "9 · Nhật ký phát triển")],
        key="help_billboard")
    
    # ==========================================
    # CHƯƠNG 1: BUỔI SÁNG
    # ==========================================
    sec_chapter(
        "help-ch1", 1, "Buổi sáng — định hướng bằng những gì đã qua",
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
        "<div class='sec-cap'>Mỗi khối màu ứng với một phiên tập trung, được đặt đúng vào vị trí giờ nó "
        "thực sự diễn ra và tô màu theo Nhóm — nhìn qua một lần là biết ngay buổi sáng, chiều hay tối hôm "
        "đó dồn vào việc gì, và có bị ngắt quãng nhiều không, khỏi phải dò từng dòng trong bảng số liệu.</div>")
    sec_block(
        "<h4>Ngày chưa có phiên nào thì nên xem gì</h4>"
        "<ul>"
        "<li><b>Lịch hẹn Work</b> của ngày hôm đó vẫn hiện đầy đủ trong Ghi chú ngày dù chưa có phiên nào — "
        "nhờ vậy bạn biết ngay còn bao nhiêu khung giờ trống để sắp việc vào trước khi bắt tay làm.</li>"
        "<li><b>Trích dẫn hôm nay</b> — một đoạn trích hoặc ghi chú Kindle được chọn ngẫu nhiên, đặt ngay "
        "đầu trang cho buổi sáng có chút không khí văn chương. Câu này được chọn cố định theo <b>ngày "
        "thật</b>: tải lại trang bao nhiêu lần, hay lùi tới tiến lui xem ngày khác, câu vẫn giữ nguyên — "
        "chỉ đổi khi sang một ngày mới, đúng như một tấm lịch để bàn mỗi ngày một câu. Muốn xem câu khác "
        "ngay lúc đó, bấm nút xáo (biểu tượng trộn bài) cạnh nút ⭐ — thay đổi này chỉ tạm thời trong lượt "
        "xem hôm nay, sang ngày mới sẽ lại chọn theo ngày như thường.</li>"
        "<li>Và một điều nhỏ nhưng đáng nhớ: “hôm nay” trong toàn bộ ứng dụng luôn được tính theo "
        "<b>giờ Việt Nam</b>, bất kể máy chủ đang chạy ở múi giờ nào — nhờ vậy ngày của bạn không bao giờ "
        "lệch sớm hoặc muộn mất bảy tiếng so với đồng hồ thật.</li>"
        "</ul>")
    
    # ==========================================
    # CHƯƠNG 2: TRONG NGÀY
    # ==========================================
    sec_chapter(
        "help-ch2", 2, "Trong ngày — cứ để ứng dụng đó, đừng bận tâm mở ra")
    sec_block(
        "<h4>Ghi chú nhanh — một hộp thư nháp mang theo trong túi quần</h4>"
        "Có một Shortcut trên iPhone (gọi qua Siri, Action Button, hay biểu tượng ngoài Màn hình chính, "
        "tuỳ bạn chọn) sẽ hỏi bạn gõ đúng một dòng ý tưởng, rồi lặng lẽ gửi <b>thẳng lên Supabase</b> — "
        "không cần mở trình duyệt, không cần chạm vào ứng dụng một chút nào. Mỗi dòng ghi kèm đúng giờ "
        "lúc bạn gửi (sửa nội dung về sau không làm giờ này đổi theo), rồi nằm chờ sẵn trong Ghi chú ngày "
        "của đúng hôm đó, ngay phía trên nhãn “Ghi chú chính” — như một tờ giấy nhớ dán tạm "
        "chờ được xử lý. Đúng với tinh thần một hộp thư nháp: ghi vội bất cứ lúc nào loé lên một ý, tối "
        "về gom lại thành một đoạn hoàn chỉnh (xem chương 3 để biết cách gộp). Yên tâm là Tìm kiếm cũng "
        "quét được cả nội dung ghi chú nhanh, phòng khi vài hôm bạn chưa kịp gộp vào ghi chú chính.")
    _sc_rows = [
        [sec_kbd("1") + " … " + sec_kbd("7"), "Nhảy thẳng tới từng mục trên thanh điều hướng, theo đúng thứ tự trái sang phải trên màn hình", "Toàn ứng dụng"],
        [sec_kbd("N"), "Mở ngay ô soạn Ghi chú ngày của hôm nay, tự cuộn tới và đặt sẵn con trỏ để gõ", "Toàn ứng dụng"],
        [sec_kbd("/"), "Chuyển sang trang Tìm kiếm (nếu đang ở trang khác) và đặt con trỏ vào ô nhập từ khoá", "Toàn ứng dụng"],
        [sec_kbd("←") + " / " + sec_kbd("→"), "Lùi về hôm qua hoặc tiến tới ngày mai, khỏi cần bấm chuột chọn ngày", "Trang Hôm nay"],
        [sec_kbd("Ctrl/Cmd", "Enter"), "Lưu ngay Ghi chú ngày đang soạn dở, không cần rê chuột tìm nút Cập nhật", "Trong ô ghi chú"],
        [sec_kbd("Esc"), "Huỷ đang soạn ghi chú, hoặc bỏ focus ô Tìm kiếm mà không xoá từ khoá đang gõ", "Theo ngữ cảnh"],
        [sec_kbd("?"), "Bật hoặc tắt bảng tóm tắt toàn bộ phím tắt này, phòng khi quên mất bảng nằm ở đâu", "Toàn ứng dụng"],
    ]
    sec_block(
        "<h4>Bảng phím tắt bàn phím</h4>"
        + sec_table(["Phím", "Tác dụng", "Dùng ở đâu"], _sc_rows)
        + "<div class='sec-cap'>Một điều cần nhớ: mọi phím tắt tự động im lặng khi con trỏ đang nằm "
        "trong một ô nhập liệu bất kỳ (ngoại trừ "
        + sec_kbd("Ctrl/Cmd", "Enter") + " và " + sec_kbd("Esc")
        + " ngay trong ô ghi chú, hai phím này vẫn hoạt động bình thường), và cũng không nhận khi bạn "
        "đang giữ Ctrl/Cmd/Alt — nhờ vậy không xảy ra việc vô tình nhảy trang khi chỉ đang gõ chữ.</div>")
    
    # ==========================================
    # CHƯƠNG 3: CUỐI NGÀY
    # ==========================================
    sec_chapter(
        "help-ch3", 3, "Cuối ngày — năm phút, thói quen đáng giá nhất trong ứng dụng")
    sec_block(
        "<h4>Ba bước nhỏ, làm đúng thứ tự là xong</h4>"
        "<ol>"
        "<li><b>Đồng bộ ngay</b> (nút tròn ⟳ nổi góc dưới màn hình, bấm được từ MỌI trang — hoặc nút "
        "\"Đồng bộ ngay\" đầy đủ ở Tuỳ biến → 1. Dữ liệu đầu vào nếu cần xem chi tiết file đang chờ) — "
        "chỉ một nút bấm mà nạp cả dữ liệu Forest, tiến độ Reminders lẫn lịch Work cùng lúc. Đây là bước "
        "nền của mọi con số khác trong ứng dụng: không đồng bộ thì chẳng có gì để nhìn lại, mọi biểu đồ "
        "sẽ trơ ra như tờ giấy trắng.</li>"
        "<li><b>Xem qua trang Hôm nay chừng một phút</b> — nhìn dòng thời gian trong ngày và chip so sánh "
        "với đúng thứ này tuần trước. Chỉ cần tự hỏi một câu: hôm nay có diễn ra như mình định không? Đây "
        "không phải để tự khen hay tự trách, mà chỉ đơn giản là ghi nhận thật thà những gì đã xảy ra.</li>"
        "<li><b>Dành hai đến ba phút viết Ghi chú ngày</b> — bước ngắn nhất nhưng lại nuôi sống cùng lúc "
        "ba tính năng khác: Nhật ký tuần/tháng, Tìm kiếm, và Ngày này năm trước. Con số chỉ kể được bạn "
        "làm <i>bao nhiêu</i> giờ, còn ghi chú mới kể được bạn làm <i>gì và vì sao</i> — một năm sau nhìn "
        "lại, chính điều thứ hai mới là thứ đáng đọc.</li>"
        "</ol>")
    sec_block(
        "<h4>Nút Gộp của ghi chú nhanh — dòng cũ có mất đi ngay không?</h4>"
        "Bấm <b>Gộp</b> trên một dòng ghi chú nhanh sẽ chèn nguyên nội dung dòng đó vào cuối ô soạn Ghi chú "
        "chính (tự mở ô soạn nếu bạn chưa mở), rồi gạch mờ dòng đó để biết là “đã xử lý” — nhưng dòng đó "
        "chỉ <b>thực sự biến mất sau khi bạn bấm Cập nhật</b> để lưu lại Ghi chú chính. Nếu lỡ tay bấm Gộp "
        "rồi đổi ý, cứ bấm Huỷ (hoặc Xoá ghi chú chính) để bỏ đánh dấu, ghi chú nhanh vẫn còn nguyên, không "
        "mất gì cả. Còn nếu bạn sửa một dòng thành trống rồi bấm Cập nhật, dòng đó cũng bị xoá luôn — đúng "
        "như cách Ghi chú chính vẫn hoạt động, không có gì bất ngờ ở đây.")
    sec_block(
        "<h4>Vì sao ghi chú quan trọng hơn mọi biểu đồ</h4>"
        "Ghi chú là loại dữ liệu <b>duy nhất trong ứng dụng không thể nạp lại được</b> nếu lỡ để trống: "
        "phiên Forest, tiến độ Reminders, hay trích dẫn Kindle đều có thể khôi phục từ file gốc khi cần. "
        "Nhưng ghi chú thì khác, nó chỉ tồn tại trong đầu bạn tại đúng khoảnh khắc đó — bỏ trống một tháng "
        "là mất vĩnh viễn một tháng ký ức, không bản sao lưu nào cứu được. Cho nên nếu chỉ được giữ đúng "
        "một thói quen trong toàn bộ hướng dẫn này, xin hãy chọn: <b>viết ghi chú mỗi tối</b>. Mọi việc "
        "khác có thể bỏ qua vài hôm mà không sao, riêng việc này thì không.")
    
    # ==========================================
    # CHƯƠNG 4: CUỐI TUẦN & CUỐI THÁNG
    # ==========================================
    sec_chapter(
        "help-ch4", 4, "Cuối tuần &amp; cuối tháng — nhìn lại với một câu hỏi trong đầu")
    _q_rows = [
        ["Thời gian đang dồn vào đâu nhiều nhất?", "Phân bổ thời gian (Tháng: biểu đồ tròn · Tuần: Nhóm &amp; dự án dạng thanh xếp hạng)", "Báo cáo → Tháng / Tuần"],
        ["Mình thường tập trung tốt nhất vào lúc mấy giờ?", "Xu hướng theo khung giờ", "Báo cáo → Tổng quan / Tháng"],
        ["Nhịp độ đang tăng lên hay đang chùng xuống?", "Xu hướng và đường trung bình động 7 ngày", "Mọi trang Báo cáo"],
        ["Ngày hôm đó tập trung sâu hay chỉ vụn vặt?", "Thanh phân bố độ dài phiên", "Mọi trang Báo cáo · Sách · Gundam"],
        ["Có việc nào đang bị bỏ quên không?", "Bảng số liệu — chú ý dấu ▾ đỏ", "Báo cáo → Tháng"],
        ["Ngày nào từng đạt kết quả cao nhất?", "Bảng vàng: Ngày nổi bật &amp; Kỷ lục", "Bảng số liệu của từng trang"],
        ["Một việc cụ thể đang tiến triển ra sao?", "Báo cáo → Dự án (lọc riêng một Nhóm hoặc Dự án)", "Báo cáo → Dự án"],
    ]
    sec_block(
        "<h4>Có câu hỏi gì trong đầu, nên mở biểu đồ nào</h4>"
        + sec_table(["Câu hỏi", "Xem biểu đồ", "Tìm ở đâu"], _q_rows))
    _heat_lv = [0, 1, 3, 2, 0, 4, 6, 2, 1, 0, 5, 7, 3, 1,
                2, 0, 1, 4, 5, 2, 0, 3, 6, 1, 2, 4, 0, 2,
                1, 3, 0, 2, 6, 1, 4, 0, 2, 5, 1, 3, 7, 0,
                4, 2, 5, 0, 1, 3, 2, 6, 0, 1, 4, 2, 0, 5]
    _heat = "".join(f"<i class='h{v}'></i>" for v in _heat_lv)
    _bar_h = [35, 55, 20, 70, 45, 4, 12, 60, 80, 50, 30, 65, 40, 92, 55, 25, 70, 45, 60, 35]
    _bars = "".join(f"<i style='height:{h}%'></i>" for h in _bar_h)
    st.markdown(
        "<div class='sec-grid'>"
        "<div class='sec-card'><h4>Biểu đồ lịch — một thang màu cố định, không tự nói dối</h4>"
        f"<div class='sec-heat'>{_heat}</div>"
        "<div class='sec-cap'>Tám bậc màu được neo theo mốc giờ cố định, không co giãn theo dữ liệu đang "
        "xem trên màn hình — nên hai ô “đậm bằng nhau” luôn có nghĩa là hai ngày có số giờ bằng nhau "
        "thật, so sánh được thoải mái giữa tháng này với tháng khác mà không sợ một ngày bất thường "
        "(chẳng hạn một hôm làm liền mười tiếng vì gấp việc) làm lệch cả thang đo.</div></div>"
        "<div class='sec-card'><h4>Xu hướng — đường trung bình ghi nhận thẳng thắn</h4>"
        f"<div class='sec-bars'>{_bars}<span class='avg'></span></div>"
        "<div class='sec-cap'>Đường trung bình động 7 ngày này tính luôn cả những ngày 0 giờ tuyệt đối, "
        "chứ không chỉ đếm ngày có hoạt động rồi bỏ qua phần còn lại — nên nghỉ liền vài hôm sẽ thấy "
        "đường đi xuống rõ ràng ngay, không bị làm mượt đi cho đẹp mắt.</div></div>"
        "</div>", unsafe_allow_html=True)
    sec_block(
        "<h4>Đọc số cho đúng cách — bốn điều nên biết trước</h4>"
        "<ul>"
        "<li><b>Kỳ dở dang luôn được cắt gọn để so sánh công bằng</b> — nếu kỳ đang xem chưa trôi hết (ví "
        "dụ mới qua ba ngày đầu tháng mà đã mở Báo cáo), cả hai mốc so sánh “so với kỳ trước” "
        "và “so với trung bình” đều tự động bị cắt xuống đúng số ngày đã trôi qua, để công bằng "
        "cho cả hai phía; một dòng caption nhỏ phía trên Bảng số liệu sẽ nói rõ khi việc cắt này đang diễn "
        "ra, để bạn khỏi nghi ngờ có điều gì sai lệch. Thiếu bước này, ba ngày đầu tháng đem so với nguyên "
        "cả tháng trước sẽ luôn trông như một cú sụt giảm đáng ngại, dù thực ra không có gì đáng lo.</li>"
        "<li><b>Chênh lệch trong khoảng ±20% là điều bình thường</b>, chưa cần vội lo — chỉ nên thật sự "
        "để tâm khi độ lệch lớn <i>và</i> bạn đã biết rõ nguyên do đằng sau nó.</li>"
        "<li><b>Dấu ▾ đỏ trong Bảng số liệu</b> nghĩa là kỳ đó tụt xuống còn không quá 40% so với kỳ ngay "
        "trước đó — một dấu hiệu đáng dừng lại đôi chút để tự hỏi vì sao. Việc tô đậm ô trong bảng là so "
        "sánh trong <i>toàn bộ bảng</i>, không phải riêng từng hàng; cột Tổng cố tình để trắng, vì đó luôn "
        "là số lớn nhất nên việc tô đậm cũng không nói thêm được điều gì mới.</li>"
        "<li><b>Kỷ lục và Ngày nổi bật là hai khái niệm khác nhau</b> — Ngày nổi bật là những ngày đứng "
        "đầu trong đúng kỳ đang xem (nên kỳ nào cũng có), còn Kỷ lục là những ngày đứng đầu <i>trong toàn "
        "bộ thời gian</i> (tính chung, và tính riêng cho từng Nhóm/Dự án đã có từ năm ngày dữ liệu trở "
        "lên). Chỉ Kỷ lục mới được gắn chip huy chương lên Timeline — vì nếu gắn cả Ngày nổi bật, thứ gần "
        "như kỳ nào cũng có, thì huy chương sẽ mất đi ý nghĩa hiếm có của nó.</li>"
        "</ul>")
    sec_block(
        "<h4>Ba điều nên tránh khi nhìn lại</h4>"
        "<ol>"
        "<li><b>Tối ưu con số thay vì tối ưu công việc thật</b> — bấm trồng cây cho một phiên đọc tin vặt "
        "lan man chỉ để đủ chỉ tiêu giờ trong ngày là đang tự lừa chính mình, bằng chính công cụ vốn sinh "
        "ra để soi lại chính mình. Số giờ chỉ là một thước đo gián tiếp, không phải là mục tiêu tự thân, "
        "đừng để nó thay chỗ mục tiêu thật.</li>"
        "<li><b>Để chuỗi ngày liên tục trở thành một gánh nặng</b> — đứt chuỗi sau một ngày ốm thật hay "
        "một ngày nghỉ đúng nghĩa là điều hoàn toàn bình thường, không có gì phải dằn vặt. Lời nhắc khi "
        "chuỗi đứt được viết theo tông động viên nhẹ nhàng, chứ không phải lời trách móc — xin đọc đúng "
        "với tinh thần đó.</li>"
        "<li><b>Nhìn lại mà trong đầu không có câu hỏi nào</b> — mỗi lần mở ứng dụng nên có sẵn ít nhất "
        "một câu hỏi để trả lời: hôm nay diễn ra thế nào? tuần này có gì lệch khỏi dự tính? tháng này tỉ "
        "trọng ưu tiên đã hợp lý chưa? Không có câu hỏi thì chỉ đang lướt qua số liệu cho vui mắt, chứ "
        "chưa phải đang thực sự nhìn lại.</li>"
        "</ol>")
    
    # ==========================================
    # CHƯƠNG 5: SÁCH, GUNDAM & SỨC KHOẺ
    # ==========================================
    sec_chapter(
        "help-ch5", 5, "Sách, Gundam &amp; Sức khoẻ")
    sec_block(
        "<h4>Quy ước đặt tên trong Apple Reminders</h4>"
        "Mỗi <b>Reminder List</b> trên điện thoại ứng với một cuốn sách hoặc một series, đặt tên theo "
        "khuôn “Tác giả - Tên sách”; mỗi reminder đã được tick hoàn thành là một "
        "phần, chương, hay tập bạn đã đọc hoặc xem xong. Ứng dụng cắt tên hiển thị theo dấu <b>gạch "
        "ngang đầu tiên</b> gặp trong tên list (ưu tiên dạng có khoảng trắng bao quanh “ - ” "
        "cho chắc): phần đứng sau dấu gạch trở thành tên hiển thị, phần đứng trước bị lược bỏ. Nếu tên "
        "list bắt đầu bằng chữ “gundam” (không phân biệt hoa thường), nó sẽ tự động được "
        "xếp sang trang Gundam thay vì trang Sách. Việc này không đổi dù bấm giờ trên Forest theo cách "
        "nào (xem mục dưới) — Reminders luôn là 1 list riêng/cuốn.")
    sec_block(
        "<h4>Bấm giờ trên Forest: sách mới chỉ cần 1 thẻ chung “Reading”</h4>"
        "Trước đây mỗi cuốn sách cần 1 thẻ Forest riêng, tên trùng khớp tuyệt đối tên sách bên "
        "Reminders. Từ nay, sách mới KHÔNG cần tạo thẻ riêng nữa — chỉ cần bấm giờ đọc dưới đúng 1 thẻ "
        "chung <b>“Reading”</b>, giống hệt cách Gundam đã dùng 1 thẻ chung “Gundam” cho mọi series từ "
        "trước tới giờ (xem mục suy luận bên dưới để biết ứng dụng ghép ngày đọc với đúng cuốn nào). "
        "Cuốn nào đã có thẻ riêng từ trước khi đổi cách này thì lịch sử cũ giữ nguyên, đóng băng theo "
        "đúng thẻ cũ đó — không cần đổi gì, chỉ áp dụng cho lần đọc MỚI trở đi.")
    sec_block(
        "<h4>“Số ngày” được tính ra sao khi có hai nguồn dữ liệu cùng lúc</h4>"
        "Mỗi cuốn sách hay series được ghép lại từ tối đa hai nguồn: phiên Forest (khớp tên thẻ cũ, "
        "hoặc suy luận từ thẻ chung “Reading”/“Gundam” — xem mục dưới) và các phần đã tick trong "
        "Reminders. Con số “Số ngày” lấy <b>hợp</b> của cả hai nguồn — tính từ ngày bắt đầu sớm nhất "
        "cho tới ngày kết thúc muộn nhất, gộp cả hai bên lại — nên nếu bạn đổi cách theo dõi giữa chừng "
        "(đang bấm giờ Forest rồi chuyển sang chỉ tick Reminders), khoảng thời gian vẫn không bị cắt cụt "
        "mất phần trước đó. Ô nào thiếu hẳn một nguồn sẽ hiện dấu gạch ngang “—” để báo là thiếu dữ "
        "liệu, thay vì để trống khiến bạn tưởng nhầm là lỗi.")
    sec_block(
        "<h4>Vì sao ứng dụng phải suy luận series/cuốn sách đang đọc</h4>"
        "Vì Forest chỉ có đúng một thẻ chung — “Gundam” cho mọi series, “Reading” cho mọi cuốn sách "
        "mới — không tách riêng từng bộ/cuốn. Bởi vậy, với mỗi ngày có phiên gắn 1 trong 2 thẻ đó, "
        "ứng dụng sẽ tìm lần tick Reminder gần nhất (ở bất kỳ series/cuốn nào, trước hoặc sau ngày đó "
        "đều được tính, miễn là gần về mặt thời gian) rồi gán cả ngày hôm đó cho đúng series/cuốn của "
        "lần tick ấy — một cách suy luận dựa trên dấu vết gần nhất. Nếu bạn chỉ theo dõi đúng một "
        "series/cuốn tại một thời điểm, trường hợp phổ biến nhất, suy luận này hầu như luôn đúng; còn "
        "nếu bạn có thói quen đọc/xem xen kẽ nhiều series/cuốn, hoặc vừa chuyển sang cuốn mới nhưng "
        "chưa tick xong phần đầu tiên, ngày nằm giữa hai lần tick sẽ được gán về phía gần hơn, và đôi "
        "khi đoán sai cũng là điều khó tránh. Gặp trường hợp đó, cứ vào mục <b>“Sửa gán series/sách tự "
        "động”</b> ở cuối trang Gundam/Sách để sửa lại tay — ngày nào đã sửa tay sẽ mang nhãn “Gán "
        "tay” để dễ phân biệt, còn nếu sau này bạn sửa lại đúng trùng với kết quả suy luận tự động, "
        "nhãn đó sẽ tự biến mất.")
    sec_block(
        "<h4>Trích dẫn Kindle — sửa một lần, giữ nguyên mãi</h4>"
        "Mọi thao tác trên trích dẫn (sửa câu chữ, xoá đi, đánh dấu ⭐ Yêu thích, hay thêm ghi chú riêng) "
        "đều được lưu vào Supabase một cách bền vững: dù nạp lại file <code>My Clippings.txt</code> "
        "cũ bao nhiêu lần — vì Kindle luôn xuất cộng dồn toàn bộ lịch sử từ đầu, không chỉ phần mới — nội "
        "dung bạn đã sửa vẫn <b>không bị ghi đè</b>, và trích dẫn đã xoá cũng <b>không tự sống lại</b>. "
        "Nếu bạn hay tô highlight bằng bút cảm ứng, Kindle thường sinh ra nhiều “bản nháp” "
        "trùng lặp (cùng một câu, cách nhau chưa tới hai phút, câu sau chỉ dài hơn câu trước một chút vì "
        "tay kéo thêm) — ứng dụng tự nhận ra và gộp lại, chỉ giữ đúng bản đầy đủ nhất. Trong Nhật ký đọc, "
        "các trích dẫn tự sắp xếp theo <b>Vị trí</b> trong sách — đúng thứ tự bạn đã đọc, không "
        "cần tự tay gán từng câu vào chương nào cả.")
    sec_block(
        "<h4>Sức khoẻ — nhập liệu từ ảnh chụp phiếu xét nghiệm</h4>"
        "Quy trình gợi ý để đỡ mất công gõ tay: chụp lại hai phiếu xét nghiệm (Huyết học và Sinh hoá) mỗi "
        "lần đi khám, đưa ảnh cho ChatGPT đọc và xuất đúng khuôn JSON như bên dưới, rồi dán thẳng vào mục "
        "<b>Import hàng loạt</b> (Sức khoẻ → Dữ liệu đầu vào) — có sẵn một bước Xem trước để "
        "soát lại trước khi bấm Xác nhận lưu, tránh nhập nhầm mà không hay biết. Mỗi lần mở trang Báo cáo "
        "sẽ thấy ngay mục <b>“Chỉ số bất thường”</b> của lần khám gần nhất hiện sẵn, không "
        "cần chọn gì trước — tiện cho việc xem nhanh có điều gì đáng lưu tâm không. Khoảng tham chiếu "
        "(<code>ref_raw</code>) chấp nhận nhiều dạng viết thường gặp trên phiếu xét nghiệm: khoảng đủ "
        "kiểu “4.2 - 5.4”, chỉ có trần trên như “&lt; 5”, hay chỉ có sàn dưới như "
        "“&gt; 10” — dạng khác (chẳng hạn kết quả định tính như “Âm tính”) vẫn lưu "
        "được bình thường, chỉ không vẽ lên biểu đồ xu hướng được.")
    with st.expander("Xem định dạng JSON mẫu để nhờ ChatGPT xuất từ ảnh"):
        st.markdown(
            "Mỗi phần tử trong danh sách là một phiếu (một nhóm chỉ số) của một lần khám — một lần khám "
            "có hai phiếu Huyết học và Sinh hoá thì ra hai phần tử cùng `test_date` khác `category`:")
        st.code(json.dumps(health_metrics_json_example, ensure_ascii=False, indent=2), language="json")
    
    # ==========================================
    # CHƯƠNG 6: NẠP DỮ LIỆU & ĐỒNG BỘ
    # ==========================================
    sec_chapter(
        "help-ch6", 6, "Nạp dữ liệu &amp; đồng bộ — luật chơi của từng nguồn")
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
        "<span class='sec-flow-node'>Bảng điều khiển</span>"
        "</div>"
        "<div class='sec-cap'>Shortcut này chạy ngay từ trình chia sẻ mỗi khi bạn xuất CSV từ ứng dụng "
        "Forest: nó tiện tay lấy luôn file sao lưu Reminders rồi tải cả hai file lên chung một bucket "
        "Supabase Storage (tên file luôn bắt đầu bằng <code>forest</code> hoặc "
        "<code>reminder</code>, chẳng hạn <code>forest_2026-07-06.csv</code>). Về phía "
        "ứng dụng, nút Đồng bộ ngay sẽ tự tìm file mới nhất của mỗi loại, nạp vào theo đúng luật ở bảng "
        "dưới đây, đồng thời kéo luôn lịch Work qua CalDAV trong cùng một lượt, rồi dọn dẹp bớt file cũ "
        "còn sót lại trong bucket. Riêng file <code>My Clippings.txt</code> của Kindle vẫn phải tải tay, "
        "không đi qua đường bucket này — vì Kindle chưa có Shortcut nào tự xuất file được.</div>")
    _sync_rows = [
        ["Forest CSV", "Cộng thêm", "Tự động bỏ qua phiên bị trùng (so theo giờ bắt đầu và kết thúc) và cả "
         "phiên đã từng bị xoá trước đó — nạp lại đúng một file bao nhiêu lần cũng không lo bị nhân đôi"],
        ["Reminders", "<b>Thay thế toàn bộ</b>", "File này phản ánh đúng trạng thái hiện tại của mọi list, "
         "không phải một lát cắt thời gian như CSV — nên ứng dụng ghi đè sạch sẽ thay vì cộng dồn, để "
         "tránh dữ liệu cũ còn sót lại gây sai lệch"],
        ["Kindle My Clippings", "Cộng thêm", "Trích dẫn trùng lặp tự động bị bỏ qua; các bản nháp do bút "
         "cảm ứng sinh ra cũng tự gộp lại; mọi thứ đã sửa, xoá, hay đánh dấu ⭐ ngay trong ứng dụng đều "
         "không bị ghi đè hay hồi sinh trở lại"],
        ["Lịch Work (CalDAV)", "Thay theo khoảng ngày", "Có sẵn các mốc ±30/±90/±180 ngày quanh hôm nay "
         "cho tiện, hoặc tự chọn hai mốc ngày riêng — dùng khoảng rộng hơn khi cần lấp đầy dữ liệu lịch cũ "
         "cho tính năng Ngày này năm trước"],
    ]
    sec_block(
        "<h4>Cộng thêm hay thay thế hoàn toàn — mỗi nguồn một kiểu</h4>"
        + sec_table(["Nguồn dữ liệu", "Kiểu nạp", "Cách chống trùng &amp; lưu ý cần nhớ"], _sync_rows))
    sec_block(
        "<h4>Xoá phiên là một thao tác được ghi nhớ, không phải xoá xong là quên hẳn</h4>"
        "Khi bạn xoá phiên ở mục <b>3. Dữ liệu làm việc hiện tại</b> (nút màu đỏ, bấm là xoá ngay không "
        "hỏi lại), phiên đó được ứng dụng âm thầm ghi nhớ riêng vào một bảng tên là "
        "<code>deleted_sessions</code> — nên về sau nếu bạn nạp lại đúng file CSV cũ có chứa "
        "phiên đó, nó <b>sẽ không tự sống lại</b>, tránh gây hoang mang vì dữ liệu tưởng đã xoá lại xuất "
        "hiện trở lại. Với những cuốn sách hoặc nguồn Kindle gặp lần đầu, ứng dụng sẽ hỏi bạn có muốn "
        "ghép nó với một Dự án đã có sẵn không (gợi ý theo tên gần giống nhất cho đỡ phải gõ) hoặc để nó "
        "đứng riêng thành “Nguồn độc lập” — chỉ cần xác nhận đúng một lần, những lần tải "
        "file sau đó ứng dụng sẽ tự nhớ và không hỏi lại.")
    
    # ==========================================
    # CHƯƠNG 7: TUỲ BIẾN & GIAO DIỆN
    # ==========================================
    sec_chapter(
        "help-ch7", 7, "Tuỳ biến &amp; giao diện")
    sec_block(
        "<h4>Một màu accent duy nhất, lan ra ba nơi bằng ba cơ chế khác nhau</h4>"
        "<ul>"
        "<li><b>Nút bấm, khung viền, chip</b> — đi qua biến CSS <code>--accent</code>, toàn bộ "
        "stylesheet của ứng dụng đều tham chiếu tới biến này thay vì gán cứng một mã màu cố định vào "
        "từng chỗ.</li>"
        "<li><b>Biểu đồ đơn sắc và bảng nhiệt</b> — chỗ này không đi qua CSS mà đi qua Python: màu accent "
        "được quy đổi thành một giá trị <b>sắc độ (hue)</b>, rồi mọi dải màu từ nhạt tới đậm đều tự động "
        "xoay theo sắc độ đó — nên đổi màu accent một lần là đổi luôn mọi biểu đồ, không sót chỗ nào.</li>"
        "<li><b>Ô ghi chú (trình soạn thảo Quill)</b> — chỗ này đặc biệt hơn vì chạy trong một iframe "
        "riêng, CSS của trang chính không chạm tới được. Ứng dụng phải tự tiêm một đoạn kiểu dáng riêng "
        "vào bên trong iframe đó, và lặp lại việc tiêm này định kỳ để không mất màu mỗi khi Streamlit "
        "dựng lại iframe.</li>"
        "</ul>"
        "Chọn một màu là áp dụng ngay lập tức, không cần bấm thêm nút Lưu nào cả — giá trị được ghi thẳng "
        "vào bảng <code>settings</code> trên Supabase. Nếu chẳng may bảng đó chưa được tạo, hoặc giá trị "
        "lưu trong đó bị hỏng, ứng dụng sẽ lặng lẽ trở về màu “Lam biển” mặc định thay vì báo "
        "lỗi hay ngừng hoạt động.")
    sec_block(
        "<h4>Chế độ tối — vì sao không có riêng một nút bật/tắt</h4>"
        "Ứng dụng tự động đổi giữa tối và sáng theo đúng cài đặt hệ thống của thiết bị bạn đang dùng (hoặc "
        "theo lựa chọn thủ công trong menu ⋮ ở góc phải trên cùng của Streamlit, nếu bạn muốn chọn khác "
        "với hệ thống). Lý do không có nút riêng khá đơn giản: Streamlit hiện chưa cho phép mã nguồn tự "
        "đổi kiểu giao diện ngay lúc đang chạy, ứng dụng chỉ đọc được kiểu giao diện hiện tại rồi tô đúng "
        "bộ màu tương ứng — kể cả biểu đồ, bảng nhiệt lẫn ô ghi chú đều được lo liệu đầy đủ, không lệch "
        "tông giữa các phần.")
    sec_block(
        "<h4>Sao lưu — một lớp an toàn dự phòng</h4>"
        "Dữ liệu vốn đã khá bền vững trên Supabase (không mất khi ứng dụng khởi động lại hay triển khai "
        "phiên bản mới), nhưng nút <b>Sao lưu</b> vẫn đóng gói toàn bộ các bảng dữ liệu thành một file "
        ".zip để bạn tải về máy, xem như một lớp an toàn dự phòng — ứng dụng sẽ nhắc nhẹ khi lần sao lưu "
        "gần nhất đã quá 30 ngày. Hai nút <b>Khôi phục</b> và <b>Làm mới</b> đều là thao tác ghi đè hoặc "
        "xoá sạch không thể hoàn tác, nên bắt buộc bạn phải tick vào ô xác nhận trước thì nút mới bật lên "
        "để bấm — cả ba nút này đều tô màu đỏ để nổi bật, khác hẳn tông trung tính của mọi nút khác trong "
        "ứng dụng, như một lời nhắc rằng thao tác này không thể quay lại. Riêng việc gán Dự án vào Nhóm "
        "(mục <b>2. Phân loại</b>) thì nhẹ nhàng hơn — hoàn toàn tuỳ chọn, chỉ để báo cáo gọn "
        "gàng dễ nhìn hơn, Dự án chưa được gán Nhóm vẫn hoạt động bình thường.")
    
    # ==========================================
    # CHƯƠNG 8: CÂU HỎI THƯỜNG GẶP
    # ==========================================
    sec_chapter(
        "help-ch8", 8, "Câu hỏi thường gặp")
    with st.container(key="help_faq"):
        help_faq_item(
            "Nạp lại một file Forest CSV cũ có làm dữ liệu nhân đôi lên không?",
            "Không, cứ an tâm nạp lại. Forest CSV được nạp theo kiểu **cộng thêm có chống trùng sẵn**: phiên "
            "nào trùng khớp giờ bắt đầu và giờ kết thúc với phiên đã có thì ứng dụng tự động bỏ qua, không "
            "thêm lần thứ hai. Có nạp cùng một file này mười lần, kết quả cuối cùng vẫn y nguyên như chỉ nạp "
            "đúng một lần.")
        help_faq_item(
            "Tôi đã lỡ xoá một phiên rồi — nạp lại CSV thì nó có sống lại không?",
            "Không, phiên đó sẽ không sống lại. Mỗi phiên bị xoá đều được ứng dụng ghi nhớ cẩn thận trong một "
            "bảng riêng tên là `deleted_sessions`. Vậy nên mọi lần nạp CSV về sau, kể cả khi file gốc vẫn còn "
            "chứa đúng phiên đó, ứng dụng cũng sẽ tự động bỏ qua, không để nó quay lại làm sai lệch số liệu.")
        help_faq_item(
            "Vì sao tháng này nhìn vào thấy sụt giảm mạnh so với tháng trước, có phải tôi đang lười đi không?",
            "Trước khi lo lắng, hãy kiểm tra một điều đơn giản: tháng này **đã trôi hết chưa**, hay mới vừa "
            "bắt đầu được vài ngày? Với một kỳ chưa kết thúc, ứng dụng sẽ tự động cắt bớt cả hai mốc so sánh "
            "xuống cho khớp đúng số ngày đã trôi qua, và ghi rõ điều này bằng một dòng caption nhỏ ngay phía "
            "trên Bảng số liệu — nếu thấy dòng caption đó, nghĩa là con số so sánh đã được làm công bằng, "
            "không phải bạn đang tệ đi. Còn nếu kỳ đã trọn vẹn mà vẫn thấy lệch, xin nhớ rằng chênh lệch "
            "trong khoảng ±20% vẫn được xem là dao động bình thường — chỉ thực sự đáng bận tâm khi độ lệch "
            "lớn hẳn và bạn đã biết rõ nguyên do.")
        help_faq_item(
            "Hai ngày có cùng tổng số giờ, vì sao cảm giác về chúng lại khác nhau nhiều đến vậy?",
            "Câu trả lời nằm ở **Thanh phân bố độ dài phiên**: cùng là sáu giờ đồng hồ, nhưng một ngày có thể "
            "là bốn phiên tập trung sâu, mỗi phiên kéo dài chín mươi phút liền mạch; ngày kia lại là hai mươi "
            "phiên vụn vặt chỉ mười lăm phút rồi bị ngắt quãng liên tục. Tổng số giờ bằng nhau, nhưng chất "
            "lượng tập trung khác xa nhau — đó là lý do vì sao chỉ nhìn con số tổng là chưa đủ. Muốn đào sâu "
            "hơn, hãy xem thẻ **Độ dài phiên** trong chương Tổng quan (ở Báo cáo → Dự án), rê chuột vào từng "
            "khoảng để xem số phiên chi tiết.")
        help_faq_item(
            "Rốt cuộc thì múi giờ nào quyết định \"hôm nay\" của ứng dụng?",
            "Luôn luôn là giờ Việt Nam, không có ngoại lệ — mọi phép tính liên quan tới ngày tháng trong toàn "
            "bộ ứng dụng đều đi qua đúng một hàm lấy giờ Việt Nam duy nhất. Dù máy chủ chạy ở múi giờ UTC hay "
            "bất kỳ múi giờ nào khác, ngày của bạn cũng sẽ không bao giờ lệch sớm hoặc muộn mất bảy giờ so "
            "với đồng hồ thật.")
        help_faq_item(
            "Trích dẫn hôm nay đổi câu mới vào lúc nào, sao thấy nó cứ y nguyên?",
            "Đúng một lần mỗi ngày, và đổi theo **ngày thật** hôm nay chứ không phải theo ngày bạn đang xem "
            "trên trang (hai điều này có thể khác nhau nếu bạn đang lùi về xem ngày cũ). Tải lại trang bao "
            "nhiêu lần, hay lùi tới tiến lui xem các ngày khác, câu trích dẫn vẫn giữ nguyên — chỉ khi thực "
            "sự sang một ngày mới mới có câu mới xuất hiện, như một tấm lịch để bàn. Câu được chọn hoàn toàn "
            "ngẫu nhiên từ toàn bộ kho trích dẫn Kindle bạn đã nạp vào ứng dụng.\n\n"
            "Muốn xem câu khác ngay, bấm nút xáo (biểu tượng trộn bài) cạnh nút ⭐ Yêu thích — thay đổi này "
            "chỉ tạm thời trong lúc đang xem, sang ngày mới sẽ lại quay về chọn theo ngày như bình thường.")
        help_faq_item(
            "Vừa nạp trích dẫn từ một cuốn sách hoàn toàn mới, chưa từng theo dõi tiến độ đọc — nó có hiện "
            "lên Trích dẫn hôm nay không, hay phải đợi ghép với Dự án trước?",
            "Hiện được ngay, không cần đợi. Khi nạp *My Clippings.txt* ở Tuỳ biến → \"Tải trích dẫn "
            "Kindle\", nếu gặp một cuốn hoặc nguồn hoàn toàn mới, ứng dụng sẽ hỏi bạn xác nhận ghép với một "
            "Dự án đang theo dõi, hoặc để nguyên \"Nguồn độc lập\" kèm một tên tự đặt (hợp cho tạp chí, hay "
            "sách bạn chưa theo dõi qua Reminders) — bước xác nhận này và bước lưu trích dẫn diễn ra cùng "
            "một lúc, chỉ sau đúng một lần bấm nút. Trích dẫn hôm nay chọn ngẫu nhiên trên toàn bộ kho, "
            "không phân biệt cuốn đó đã ghép Dự án hay còn để độc lập — nên ngay từ lần nhập đầu tiên, trích "
            "dẫn của cuốn sách mới đã có cơ hội xuất hiện như mọi trích dẫn khác.\n\n"
            "Một điều cần nhớ: bước xác nhận ghép Dự án hoặc đặt tên đó **chỉ hỏi đúng một lần** cho mỗi tên "
            "sách — nếu lỡ chọn nhầm, hoặc sau này mới bắt đầu theo dõi tiến độ đọc cuốn từng để \"độc "
            "lập\" qua Reminders, hãy vào lại tab \"Tải trích dẫn Kindle\" — ngay dưới ô tải file có sẵn "
            "một bảng **\"Ánh xạ đã lưu\"** liệt kê mọi cuốn hoặc nguồn đã từng ghép, sửa lại Dự án hoặc "
            "tên hiển thị ngay tại đó rồi bấm Lưu, không cần nạp lại file gốc.")
        help_faq_item(
            "Gundam/Sách bị gán nhầm series/cuốn rồi, giờ sửa lại ở đâu?",
            "Hãy tìm tới mục **\"Sửa gán series/sách tự động\"** ở cuối trang Gundam hoặc Sách (mục này "
            "chỉ xuất hiện khi có từ hai series/cuốn trở lên, vì chỉ một thì không cần đoán): chọn lại "
            "đúng series/cuốn cho từng ngày bị gán sai rồi bấm Lưu là xong. Ngày đã sửa tay sẽ được đánh "
            "dấu bằng nhãn \"Gán tay\" để dễ phân biệt với phần ứng dụng tự đoán — còn nếu sau này bạn "
            "sửa lại đúng trùng với kết quả suy luận tự động ban đầu, nhãn đó sẽ tự biến mất.")
        help_faq_item(
            "Đổi màu accent xong, các biểu đồ có tự đổi màu theo không?",
            "Có, và đổi ngay lập tức không cần làm gì thêm — kể cả Biểu đồ lịch, bảng nhiệt, lẫn màu chữ "
            "trong ô ghi chú cũng đổi theo cùng lúc. Lý do là màu accent bạn chọn được quy đổi ngay thành "
            "một giá trị sắc độ duy nhất, rồi mọi dải màu đơn sắc trong toàn bộ ứng dụng đều tự động xoay "
            "theo đúng sắc độ đó — nên không có biểu đồ nào bị bỏ sót, vẫn giữ màu cũ trong khi chỗ khác đã "
            "đổi hết.")
        help_faq_item(
            "Bấm phím tắt hoài mà không thấy chạy gì cả, ứng dụng có bị lỗi không?",
            "Nhiều khả năng không phải lỗi, mà gần như chắc chắn là con trỏ chuột đang nằm sẵn trong một ô "
            "nhập liệu nào đó (như ô ghi chú, ô tìm kiếm...) — mọi phím tắt sẽ tự động im lặng trong tình "
            "huống này, để tránh việc bạn gõ chữ bình thường mà ứng dụng lại hiểu nhầm là đang bấm phím "
            "tắt. Ngoại lệ duy nhất là Ctrl/Cmd+Enter và Esc ngay trong ô ghi chú, hai phím này vẫn hoạt "
            "động dù đang gõ. Cứ bấm `Esc` hoặc nhấp chuột ra khoảng trống bên ngoài rồi thử lại; còn nếu "
            "đang giữ sẵn phím Ctrl/Cmd/Alt, phím tắt cũng sẽ không nhận, vì lúc đó ứng dụng hiểu là bạn "
            "đang dùng một tổ hợp phím khác của trình duyệt.")
        help_faq_item(
            "Ghi chú của tôi có bị mất khi ứng dụng khởi động lại hoặc lên phiên bản mới không?",
            "Không mất, cứ an tâm — toàn bộ dữ liệu đều nằm trên Supabase, không nằm trong bộ nhớ tạm của "
            "ứng dụng, nên hoàn toàn không phụ thuộc vào việc ứng dụng khởi động lại hay không. Tuy vậy, "
            "cần nhớ rằng ghi chú là loại dữ liệu **duy nhất trong ứng dụng không thể nạp lại được từ bất "
            "kỳ nguồn nào khác** nếu chẳng may có sự cố nghiêm trọng xảy ra với Supabase — nên vẫn nên duy "
            "trì thói quen bấm Sao lưu định kỳ (ứng dụng sẽ tự nhắc sau mỗi 30 ngày nếu quên) để có thêm "
            "một lớp an toàn dự phòng.")
    
    # ==========================================
    # CHƯƠNG 9: NHẬT KÝ PHÁT TRIỂN
    # ==========================================
    sec_chapter(
        "help-ch9", 9, "Nhật ký phát triển")
    # Mỗi mục gộp TẤT CẢ PR có ý nghĩa với người dùng cuối merge trong CÙNG 1 ngày thành 1 entry
    # duy nhất (xác nhận với người dùng) -- pr liệt kê đủ mọi số PR của ngày đó, pr_lines/
    # total_lines lấy theo đúng PR merge SAU CÙNG trong ngày (không cộng dồn nhiều PR). pr_lines =
    # tổng insertions+deletions (git --shortstat, MỌI file, không riêng .py) của đúng PR đó.
    # PR thuần nội bộ (đổi tài liệu dev Codex↔Claude Code, refactor không đổi hành vi/giao diện vd
    # tách module app.py) KHÔNG được tính vào "pr" liệt kê hay vào bullets -- không có ý nghĩa với
    # người dùng cuối. Từ sau PR #291 (tách app.py thành nhiều module) total_lines đổi sang đếm
    # TỔNG số dòng MỌI file `.py` trong repo (trước đó chỉ có mỗi app.py nên 2 cách tính trùng
    # nhau) -- không dùng lại "wc -l app.py" đơn thuần nữa vì sẽ hiện 1 cú SỤT dòng giả tạo (code
    # dời sang module khác, không phải bị xoá).
    # date/total_lines của entry ĐẦU (mới nhất) bị TRÙNG với _help_latest_date/_help_latest_lines
    # ở billboard đầu trang (xem elif nav == "Hướng dẫn" phía trên) -- sửa entry mới nhất ở đây thì
    # PHẢI sửa cả 2 biến đó theo, không tự động đồng bộ.
    HELP_CHANGELOG = [
        dict(pr="299", date="19/08/2026", pr_lines=680, total_lines=14157,
             title="Sub-nav Báo cáo/Sức khoẻ/Tuỳ biến chuyển vào sidebar, chèn ngay sau nút trang cha",
             bullets=[
                 "**3 sub-nav \"Chọn kỳ xem\"/\"Xem theo\" (Báo cáo, Sức khoẻ, Tuỳ biến) chuyển từ "
                 "đầu nội dung trang sang sidebar**, đứng ngay dưới nav chính thay vì chiếm 1 hàng "
                 "riêng phía trên billboard mỗi trang.",
                 "**Sub-nav được chèn NGAY SAU nút của đúng trang cha** trong nav chính (vd sub-nav "
                 "của \"Báo cáo\" nằm ngay dưới mục \"Báo cáo\"), không rơi xuống cuối toàn bộ danh "
                 "sách nav — nav chính giờ tự chia nhóm quanh trang đang xem để lồng đúng sub-nav "
                 "vào giữa.",
                 "Không đổi cơ chế deep-link (`?sub=`/`?hsub=`/`?tsub=`) hay các link \"nhảy nhanh\" "
                 "sang 1 sub-tab cụ thể từ nơi khác trong app (vd click biểu đồ Xu hướng nhảy sang "
                 "sub-tab \"Dự án\").",
             ]),
        dict(pr="293-298", date="17/08/2026", pr_lines=42, total_lines=13985,
             title="Chuyển nav sang sidebar, redesign Apple/macOS, bộ chọn ngày/kỳ mới, spacing 14px",
             bullets=[
                 "**Nav chính chuyển sang sidebar trái cố định** (trước đây là 1 hàng ngang trên "
                 "cùng) — thêm palette nền \"Xám hệ thống\", đổi kiểu thẻ mặc định sang \"Nổi mềm\" "
                 "cho người dùng chưa từng lưu tuỳ biến riêng.",
                 "**Redesign billboard theo phong cách Apple/macOS**: badge số tròn thay \"tờ lịch "
                 "xé\", thêm cột mục lục dọc; panel số liệu (Hôm nay/Báo cáo/Sách/Gundam/Sức khoẻ) "
                 "tách thành lưới thẻ hero + 1 thẻ danh sách có gạch ngăn; thanh sub-tab (\"Chọn kỳ "
                 "xem\"/\"Xem theo\"/\"Chọn mục\") căn trái thay vì căn giữa.",
                 "**Bộ chọn ngày/kỳ đổi theo phong cách Apple**: viên thuốc bo góc + icon lịch, lịch "
                 "bắt đầu từ Thứ Hai; font khung vỏ (sidebar + bộ chọn ngày/kỳ) ghìm cố định Manrope, "
                 "tách khỏi trục \"Font thân chữ\" chọn ở Tuỳ biến.",
                 "**Trang Hôm nay**: gộp \"Phiên đầu · Phiên cuối · Trải dài\" thành 1 dòng, bỏ các "
                 "đề mục nhóm cho gọn; ô soạn ghi chú tự focus + đặt con trỏ cuối nội dung ngay khi "
                 "bấm Sửa/Thêm ghi chú.",
                 "**Rút gọn biểu đồ**: \"Dòng thời gian trong ngày\" giảm chiều cao, biểu đồ theo "
                 "Nhóm/Dự án đổi sang 1 thanh xếp chồng + legend chấm màu thay vì mỗi mục 1 hàng "
                 "riêng; tooltip từng thanh của \"Dòng thời gian\" hiện tức thời (không delay), thêm "
                 "Nhóm và thời lượng thật.",
                 "Cùng loạt sửa nhỏ: chuẩn hoá khoảng cách thẻ→thẻ về đúng 14px (trước đó rải rác "
                 "4–26px), thu gọn list-card, sửa vài thẻ lệch bề rộng do sót padding cũ.",
             ]),
        dict(pr="289-290", date="25/07/2026", pr_lines=32, total_lines=13278,
             title="Chia 2 cột Trích dẫn & Ghi chú, sửa spacing thẻ Trích dẫn trên mobile",
             bullets=[
                 "**Chương \"Trích dẫn & Ghi chú\" (Sách → Tổng quan) chia 2 cột cân bằng theo khối "
                 "lượng văn bản** (thuật toán tham lam) trên desktop, tự co về 1 cột trên mobile.",
                 "**\"Trích dẫn hôm nay\" giờ gắn cố định theo NGÀY ĐANG XEM** (seed tất định từ ISO "
                 "ngày đó) thay vì ngày thật hôm nay — đổi ngày ra câu khác, quay lại ngày cũ vẫn ra "
                 "đúng câu cũ, không cần bảng ánh xạ riêng.",
                 "Sửa lỗi spacing không đều (44px thay vì 10px) giữa 2 thẻ Trích dẫn ở ranh giới cột "
                 "khi màn hình co về 1 cột trên mobile.",
             ]),
        dict(pr="281-288", date="24/07/2026", pr_lines=86, total_lines=13236,
             title="Nhập Nhật ký Day One, Lịch tháng mới ở Báo cáo, cập nhật tài liệu phát triển",
             bullets=[
                 "**Nhập Nhật ký Day One** (Tuỳ biến → Dữ liệu đầu vào → Dự phòng) — đọc file JSON "
                 "xuất từ Day One, giữ đúng định dạng **đậm**/*nghiêng*/list (kể cả lồng cấp), bỏ "
                 "ảnh/link nội bộ, gộp nhiều mục cùng ngày, nối vào ghi chú Forest đã có nếu trùng "
                 "ngày thay vì ghi đè. Mở khoá luôn việc chọn/gõ ghi chú cho ngày quá khứ chưa từng "
                 "có phiên Forest nào (trang Hôm nay).",
                 "**\"Biểu đồ lịch\" ở Báo cáo Tháng/Năm đổi thành \"Lịch tháng\" dạng lưới** (cùng "
                 "kiểu component với Nhật ký đọc Sách/Gundam) — mỗi ô ngày hiện tổng thời gian tập "
                 "trung, tối đa 2 chip Dự án nhiều giờ nhất, và 1 hàng icon số lịch hẹn/phần sách/"
                 "phần Gundam/số từ ghi chú chính. Bỏ hẳn khỏi Báo cáo Tổng quan (dư thừa ở trang "
                 "tổng hợp toàn thời gian).",
                 "**Mỗi năm ở \"Ngày này năm trước\" giờ là link nhảy thẳng tới Báo cáo ngày** của "
                 "đúng ngày đó, để sửa lại ghi chú cũ không cần tự tìm lại.",
                 "Cùng vài sửa lỗi: màu phân trang (`st.pagination`) đọc được trên Bảng màu nền đậm ở "
                 "light theme; rà soát lại tài liệu phát triển cho khớp code hiện tại. (Nút \"← Quay "
                 "lại\" cho Báo cáo ngày/Báo cáo → Dự án cũng thử nghiệm trong ngày này nhưng bị bỏ "
                 "ngay sau đó vì phá bố cục trang — không còn xuất hiện ở bản hiện tại.)",
             ]),
        dict(pr="276-280", date="23/07/2026", pr_lines=237, total_lines=12713,
             title="Trục \"Độ rộng nội dung\" cho màn hình lớn, chip Liền mạch, tối ưu backend + dọn lỗi nhỏ",
             bullets=[
                 "**Thêm trục \"Độ rộng nội dung\"** (Tuỳ biến → Giao diện, 4 mức 1100/1300/1500/"
                 "1700px) — màn hình lớn (27\"/32\" 4K–5K) trước đây cột nội dung chỉ chiếm ~23–31% "
                 "chiều ngang; đồng bộ luôn vị trí 2 nút nổi \"Về đầu trang\"/\"Đồng bộ nhanh\" theo "
                 "đúng mép cột mới.",
                 "**Chia 2 cột Trích dẫn/Ghi chú ở độ rộng lớn** (≥1500px) — trang Trích dẫn chia "
                 "theo khối lượng (thuật toán tham lam) thay vì xen kẽ trái-phải cứng nhắc, tránh "
                 "khoảng trống rộng; sửa màu chữ tên sách/tác giả bị lẫn nền trên các Bảng màu nền "
                 "tối cố định.",
                 "**Chip \"Liền mạch\" ở trang Hôm nay** (ngày có ≥2 phiên) — khối tập trung liền "
                 "mạch dài nhất + khoảng nghỉ dài nhất trong ngày, tính từ giờ kết thúc phiên đã có "
                 "sẵn.",
                 "**Tối ưu backend**: mọi lệnh lưu/sửa/xoá giờ chỉ xoá cache đúng bảng liên quan thay "
                 "vì xoá sạch cache cả 14 bảng; thêm cache 60 giây cho việc kiểm tra file Đồng bộ "
                 "nhanh đang chờ (bớt 1 round-trip Supabase Storage mỗi lần tương tác); gộp logic "
                 "merge CSV Forest dùng chung cho Đồng bộ nhanh và tải tay; vectorize 2 chỗ tính theo "
                 "từng dòng dữ liệu.",
                 "Cùng vài sửa nhỏ: lỗi dọn file đồng bộ cũ bị nuốt im lặng giờ báo lại qua kết quả "
                 "đồng bộ, thống nhất màu delta trung tính theo theme, \"Yếu nhất theo thứ\" chỉ xét "
                 "thứ có giờ hoạt động thật.",
             ]),
        dict(pr="264-275", date="22/07/2026", pr_lines=62, total_lines=12539,
             title="Nhật ký đọc/xem đổi sang lịch tháng, thêm bộ lọc theo tuần, tách trang Giao diện riêng, bỏ kicker heading, 5 sửa tương phản/spacing/tooltip/ghi chú nhanh",
             bullets=[
                 "**Sửa lỗi xoá ghi chú nhanh trong lúc đang mở ô soạn Ghi chú chính làm mất/hỏng "
                 "nội dung đang gõ dở** (trang Hôm nay) — xoá 1 dòng phía trên khiến Streamlit dựng "
                 "lại widget soạn thảo (Quill), có thể xoá trắng phần chưa kịp lưu. Giờ chỉ đánh dấu "
                 "\"chờ xoá\" (gạch ngang, có nút Hoàn tác), xoá thật khi bấm Cập nhật/Huỷ — cùng cơ "
                 "chế \"chờ gộp\" đã có, không còn đụng tới ô soạn đang mở.",
                 "**Sửa spacing hẹp bất thường giữa panel số liệu và 2 thẻ \"Theo buổi\"/\"Độ dài "
                 "phiên\" ngay dưới** (desktop, Sách/Gundam → Tổng quan và mọi sub-tab Báo cáo) — "
                 "panel thiếu margin dưới nên khoảng cách này chỉ còn 10px thay vì 24px như mọi cặp "
                 "card khác trong cùng chương.",
                 "**Lịch tháng Sách/Gundam: chạm 1 ô ngày trên mobile giờ hiện tooltip trước, chạm lần "
                 "2 mới nhảy sang trang \"Hôm nay\" của ngày đó** — trước đây chạm là nhảy trang ngay, "
                 "không kịp xem tooltip (tooltip vốn chỉ hiện khi hover, màn cảm ứng không có hover).",
                 "**Sửa tương phản tiêu đề/caption của \"Sửa gán series/sách tự động\"** (Sách/Gundam "
                 "→ Tổng quan) — expander này đứng trực tiếp trên nền trang nên chữ mất tương phản "
                 "trên các Bảng màu nền cố định tông đậm; giờ hiện như 1 thẻ khớp màu nền đang chọn.",
                 "**Sửa spacing hẹp bất thường giữa card \"Dòng thời gian trong ngày\" và \"Theo buổi\"** "
                 "(trang Hôm nay, mobile) — card đầu thiếu margin dưới nên khoảng cách này hẹp hơn hẳn "
                 "mọi cặp card khác trên cùng trang.",
                 "**Bỏ nhãn kicker bên phải tiêu đề mỗi chương** (`sec_chapter`) — trên màn hình mobile "
                 "hẹp, dòng chữ này ép tiêu đề phải xuống dòng nhiều lần; giờ mỗi chương chỉ còn số thứ "
                 "tự + tiêu đề + kẻ ngang.",
                 "**Nhật ký đọc/xem (Sách/Gundam → Tổng quan) đổi từ danh sách phân trang sang lịch "
                 "tháng dạng bản đồ nhiệt** — mỗi ngày là 1 ô trong lưới tháng, đậm nhạt theo thời gian "
                 "đọc/xem, kèm chip phần đã đọc/số trích dẫn, hover xem chi tiết, có nút điều hướng "
                 "tháng trước/sau/Hôm nay.",
                 "**Bộ lọc “theo tuần” cho Nhật ký đọc/xem** — thêm ở cả Nhật ký chương “Nhật ký” của "
                 "Báo cáo Tháng (đỡ phải cuộn cả tháng) lẫn ở trang Chi tiết từng cuốn sách/series "
                 "(tự tính theo đúng khoảng thời gian đọc/xem thật, có nút “Hiện thêm”/“Tất cả” khi "
                 "đọc kéo dài nhiều tháng).",
                 "**Tách trang Tuỳ biến “Giao diện” thành sub-page riêng** theo đúng mockup, cùng loạt "
                 "sửa tương phản chữ/nền còn sót ở các bảng màu nền đậm cố định.",
             ]),
        dict(pr="245-263", date="21/07/2026", pr_lines=148, total_lines=11856,
             title="Tên Dự án/Sách/Gundam click nhảy tới Chi tiết, thêm font thân chữ mới, đồng bộ spacing",
             bullets=[
                 "**Tên Dự án/Nhóm/Sách/Gundam giờ click được để nhảy thẳng tới trang Chi tiết** — áp "
                 "dụng ở bảng số liệu, chip “Ngày nổi bật”, billboard — không cần tự tìm lại trong bộ "
                 "lọc nữa; cùng đợt sửa lại toàn bộ phím tắt điều hướng đã ngưng hoạt động.",
                 "**Nhật ký đọc/xem (Tổng quan) thêm bộ lọc Khoảng thời gian + phân trang**, hiện thêm "
                 "cả những ngày chỉ có phiên Forest chưa tick chương, và đánh dấu ngày kỷ lục ngay trên "
                 "biểu đồ Xu hướng.",
                 "**Thêm 5 font thân chữ mới**, mở rộng Màu nền/Kiểu nền trang/Kiểu thẻ lên 8 lựa chọn "
                 "mỗi mục, cùng vài lượt sửa lạc tông khi đổi bảng màu nền (bộ lọc Nhóm/Dự án, "
                 "expander, nút tải file) và sửa font thân chữ tuỳ chọn trước đó chưa áp dụng hết app.",
                 "**Đồng bộ khoảng cách (spacing) xuyên suốt app** — nav bar, bộ chọn kỳ/ngày, "
                 "sub-tab picker, billboard đều về chung 12px, sửa vài chỗ viền/khoảng cách bị cắt "
                 "hoặc lệch chuẩn do CSS cũ.",
                 "Cùng vài sửa nhỏ: Báo cáo theo Dự án còn lọt series Gundam tag riêng khỏi loại trừ, "
                 "nút trích dẫn Kindle xuống hàng riêng trên mobile, 2 bảng màu nền đậm giữ đúng light "
                 "theme cho card/chữ.",
             ]),
        dict(pr="244", date="20/07/2026", pr_lines=439, total_lines=11102,
             title="Cá nhân hoá giao diện: bảng màu nền, kiểu thẻ, mật độ bố cục, font thân chữ",
             bullets=[
                 "**3 trục cá nhân hoá mới ở Tuỳ biến → “4. Giao diện”** — Bảng màu nền (5 bộ màu "
                 "phối sẵn), Kiểu thẻ (bo góc/độ dày viền/đổ bóng), Mật độ bố cục (khoảng đệm/khoảng "
                 "cách giữa các thẻ) — cả 3 tách biệt và kết hợp tự do với Màu accent/Kiểu nền trang "
                 "đã có từ trước, không trục nào phá trục khác.",
                 "**Font thân chữ tự chọn** — Manrope (mặc định)/Inter/Public Sans, chỉ tải đúng font "
                 "đang chọn để không đội thêm dung lượng trang.",
                 "**8 màu accent đổi sang bộ đa dạng hơn** — trải đều quanh vòng màu thay vì cụm tông "
                 "đất/mộc mạc gần nhau như bộ cũ.",
                 "**Sửa loạt chỗ giao diện “đứng yên” khi đổi Bảng màu nền/Màu accent** — thanh menu "
                 "trên cùng, các thẻ Sao lưu/Khôi phục/Làm mới, khung tải file lên, hộp thoại xác "
                 "nhận, ô tick checkbox — tất cả trước đây vẫn giữ đúng màu mặc định gốc bất kể lựa "
                 "chọn mới, giờ đã theo đúng bảng màu/màu accent đang dùng.",
             ]),
        dict(pr="235-238", date="20/07/2026", pr_lines=168, total_lines=10760,
             title="Sách đổi sang mô hình Gundam: một thẻ chung, tự suy luận đúng cuốn theo ngày",
             bullets=[
                 "**Không cần tạo tag riêng cho từng cuốn sách nữa** — chỉ cần bấm giờ đọc dưới đúng "
                 "1 thẻ Forest chung “Reading”, giống hệt cách Gundam đã dùng 1 thẻ chung cho mọi "
                 "series từ trước tới giờ. Ứng dụng tự suy luận ngày nào đang đọc cuốn nào dựa theo "
                 "lần tick Reminder gần nhất, có mục “Sửa gán sách tự động” ở trang Sách để sửa tay "
                 "khi đoán sai. Sách cũ đã có tag riêng vẫn giữ nguyên lịch sử, không cần đổi gì.",
                 "**Nhóm và Dự án tách bạch rõ ràng xuyên suốt ứng dụng** — chọn xem theo Nhóm "
                 "vẫn gộp chung “Gundam”/“Reading”, nhưng chọn xem theo Dự án giờ hiện đúng tên từng "
                 "series/cuốn sách cụ thể ở mọi nơi (Báo cáo, Bảng vàng, Top 3, biểu đồ lịch, Tìm "
                 "kiếm...), không cần sửa riêng từng trang.",
                 "**The Economist tách khỏi nhóm Sách** — không còn bị loại trừ ngầm, giờ xếp Nhóm "
                 "riêng và hiện như một Dự án bình thường ở Báo cáo.",
                 "**Bỏ hẳn tính năng “Gán Dự án Forest với Cuốn sách”** — không còn tình huống nào "
                 "cần dùng tới sau khi chuyển sang thẻ chung.",
                 "**Nút “Đồng bộ ngay” giờ bấm được từ mọi trang** — một nút tròn nổi cạnh nút “Về "
                 "đầu trang”, không cần mở tab Tuỳ biến mới đồng bộ được nữa.",
                 "Cùng vài chỉnh sửa nhỏ: cột đếm số nguyên hết cảnh “.0” thừa, chip “Ngày nổi bật” ở "
                 "Báo cáo Tháng thêm tên Thứ, bảng màu biểu đồ Nhóm/Dự án đổi sang “Vintage bản "
                 "đồ” rõ ràng hơn, và cách viết giờ phút đổi từ “1h30p” sang “1h30′”.",
             ]),
        dict(pr="223,224", date="18/07/2026", pr_lines=1, total_lines=10352,
             title="Viết lại toàn bộ văn bản trong ứng dụng theo giọng điềm đạm, và sửa lỗi hiển thị trên mobile",
             bullets=[
                 "**Trang Trợ giúp được viết lại toàn bộ** — cả 9 chương, phần Câu hỏi thường gặp, "
                 "và mọi mục Nhật ký phát triển cũ đều đổi sang giọng điềm đạm, mạch lạc hơn, không "
                 "đổi cấu trúc chương hay số liệu.",
                 "**Câu “điểm nhấn” ở Báo cáo Tuần/Tháng/Năm đổi giọng** — trước đây viết theo kiểu "
                 "đùa vui “người làm vườn” (ví dụ ví ổn định là “chủ vườn đáng nể”), giờ chuyển sang "
                 "những nhận xét điềm đạm hơn, vẫn giữ ẩn dụ cây và rừng của Forest nhưng ở mức vừa "
                 "phải, không còn đùa cợt.",
                 "**Thuần Việt hoá một số từ mượn** — “app” đổi thành “ứng dụng” ở mọi nơi hiển thị "
                 "cho người dùng, “billboard” đổi thành “khung tóm lược”, “wordmark” đổi thành “dòng "
                 "chữ hiệu”; cùng một loạt thông báo trạng thái (rỗng, lỗi, thành công) ở Sách, "
                 "Gundam, Sức khoẻ, Tuỳ biến được viết lại cho nhất quán, bỏ dấu chấm than và câu "
                 "mệnh lệnh suồng sã.",
                 "**Sửa lỗi số thứ tự chương vỡ layout trên mobile** — một dòng CSS cũ còn sót lại "
                 "từ bản thiết kế trước (số lớn mờ chồng góc, đã bỏ) ghi đè kích thước ô số thứ tự "
                 "lên 40px trong media query mobile, trong khi ô số hiện tại chỉ rộng 26px, khiến số "
                 "bị tràn ra ngoài và vỡ xuống dòng riêng trên màn hình nhỏ.",
             ]),
        dict(pr="185-192", date="16/07/2026", pr_lines=1784, total_lines=8004,
             title="Khung tóm lược lan khắp ứng dụng, và làm lại toàn bộ trang Trợ giúp",
             bullets=[
                 "**Trang Hôm nay có một khung tóm lược mới** — gộp thẻ “Ngày đang xem”, thẻ trích dẫn "
                 "hôm nay và hàng chip mục lục thành một khối duy nhất, như một tờ lịch xé hằng ngày: số "
                 "ngày lớn bên trái, trích dẫn Kindle bên phải, có gạch dọc ngăn ở giữa và dòng “Cập "
                 "nhật gần nhất” tự cập nhật theo thời gian thực. Bố cục chương cuộn dọc này sau đó lan "
                 "sang cả Báo cáo (Tổng quan/Tuần/Tháng/Năm/Dự án), Sách/Gundam (Chi tiết) và Sức khoẻ "
                 "(Báo cáo) — mọi chương đều hiện sẵn khi cuộn, thay vì phải bấm mở từng mục gập như "
                 "trước.",
                 "**Và đây, chính là trang Trợ giúp bạn đang đọc** — được làm lại hoàn toàn từ đầu, bỏ "
                 "hẳn 58 tấm ảnh chụp màn hình cồng kềnh, đổi từ tám tab ngang sang một trang cuộn dọc kể "
                 "chuyện theo đúng nhịp một ngày sử dụng thật, thêm mấy hình minh hoạ vẽ tay thuần CSS, "
                 "một mục tra cứu nhanh, và cả phần Câu hỏi thường gặp — cùng lúc sửa một lỗi khá đáng "
                 "tiếc khiến tab “Cập nhật” của bản cũ từng trống trơn vì nội dung lỡ đặt nhầm chỗ.",
                 "**Một đợt dọn dẹp diện rộng** — dời mục “Ngày này năm trước” lên ngay sau Ghi chú "
                 "ngày cho hợp lý luồng đọc, bớt vài số liệu và biểu đồ ít được dùng tới ở trang Báo "
                 "cáo, lọc bớt tên sách khỏi danh sách chọn Dự án, sửa lỗi trùng lặp chỉ số ở Sức khoẻ, "
                 "và để trang Tuỳ biến mặc định chỉ mở đúng mục 1 thay vì mở tung cả năm mục.",
                 "**Sửa một lỗi mất nội dung khá khó chịu** — bấm “Gộp” một ghi chú nhanh vào ô soạn "
                 "đang mở sẵn trước đó không đưa được nội dung thật vào ô soạn, giờ đã dựng lại đúng "
                 "lúc để nội dung gộp hiện ra thật sự. Kèm theo một loạt tinh chỉnh nhỏ khác: nút Gộp/"
                 "Sửa/Xoá ở ghi chú nhanh không còn vỡ dòng, khung chọn ngày dịch hẳn sang tiếng Việt, "
                 "và thêm hai màu accent mới (Cam đất, Ô liu).",
             ]),
        dict(pr="181-184", date="15/07/2026", pr_lines=69, total_lines=7690,
             title="Trích dẫn Kindle: thẻ nổi bật, tính năng Yêu thích, và một đợt rà soát đơn giản hoá",
             bullets=[
                 "**Trích dẫn hôm nay được nâng cấp** — thẻ trích dẫn chuyển hẳn lên đầu trang Hôm "
                 "nay, đổi sang nền màu accent đậm, chữ trích dẫn phóng cỡ lớn theo kiểu chữ sách, và "
                 "có thêm tên tác giả đứng cạnh tên sách.",
                 "**Tính năng Yêu thích ra mắt** — bấm dấu ★ trên bất kỳ trích dẫn hay ghi chú Kindle "
                 "nào để đánh dấu lưu lại, rồi xem gộp toàn bộ những gì đã đánh dấu ở sub-tab riêng "
                 "“Yêu thích” trong trang Sách. Việc nhập trích dẫn Kindle cũng thông minh hơn: ứng "
                 "dụng tự nhận diện và gộp các “bản nháp” sinh ra do thói quen tô highlight bằng bút "
                 "cảm ứng, chỉ giữ lại đúng bản đầy đủ nhất.",
                 "**Một đợt rà soát và đơn giản hoá theo phản hồi thực tế** — cắt bỏ vài tính năng hoá "
                 "ra không đáng công sức (khối Top 3 ở Hôm nay/Báo cáo → Tuần, biểu đồ dòng thời gian "
                 "tự vẽ ở Sách/Gundam, vài phím tắt ít dùng); đổi lại thêm nút “Gộp” ghi chú "
                 "nhanh, khả năng sửa tay khi gán series Gundam sai, mục “Chỉ số bất thường” ở Sức "
                 "khoẻ, mở rộng phạm vi Tìm kiếm sang Ghi chú nhanh, và gộp hai giao diện đồng bộ "
                 "CalDAV thành một chỗ duy nhất.",
             ]),
        dict(pr="155-167", date="06/07/2026", pr_lines=79, total_lines=6162,
             title="Đồng bộ nhanh làm mặc định, Bảng vàng, Ghi chú nhanh từ iOS, và logo mới",
             bullets=[
                 "**Đồng bộ nhanh trở thành phương án mặc định** — chỉ một nút bấm là nạp được cả "
                 "Forest, Reminders và lịch Work cùng lúc, thẳng từ file Shortcut đã tải lên sẵn; ba "
                 "cách tải tay kiểu cũ vẫn còn nguyên, chỉ gộp gọn vào một khối “Dự phòng” có thể thu "
                 "lại.",
                 "**Bảng vàng ra đời** — Bảng số liệu ở mỗi trang Báo cáo có thêm mục “Ngày nổi bật” "
                 "và khái niệm **Kỷ lục** tính trên toàn bộ thời gian, gắn thành chip huy chương trên "
                 "Timeline khi xứng đáng.",
                 "**Ghi chú nhanh chính thức có mặt** — một Shortcut trên iPhone cho phép gửi thẳng "
                 "một dòng ý tưởng lên ứng dụng mà không cần mở trình duyệt, tách biệt hoàn toàn khỏi "
                 "Ghi chú chính.",
                 "Cùng với đó là một bộ logo thiết kế mới (tự đổi màu theo accent) và phong cách nút "
                 "bấm gọn gàng, nhất quán hơn cho toàn bộ tab Tuỳ biến.",
             ]),
        dict(pr="125,126,132,133,136,137,139,140,141-146", date="04/07/2026", pr_lines=15, total_lines=5139,
             title="Trang Hôm nay ra đời, Báo cáo Năm, Tìm kiếm, chế độ tối, và phím tắt bàn phím",
             bullets=[
                 "**Trang Hôm nay chính thức ra đời** — tách riêng từ lát cắt “Ngày” vốn từng nằm "
                 "trong Báo cáo, trở thành mục đầu tiên và mặc định trên thanh điều hướng. Cùng lúc, "
                 "bảng màu accent mở rộng thành **14 màu**, và ứng dụng có một logo cùng dòng chữ hiệu "
                 "“Forest Dashboard” hẳn hoi.",
                 "**Báo cáo → Năm ra mắt** — một bản tổng kết trọn vẹn cho một năm cụ thể, gồm số liệu "
                 "nổi bật, Biểu đồ lịch trải dài cả năm, và mục Đọc sách/Gundam trong năm.",
                 "**Trang Tìm kiếm ra đời** — tra từ khoá cùng lúc trên ghi chú, lịch Work, và sách/"
                 "Gundam đã đọc hoặc xem qua, gộp kết quả theo từng ngày.",
                 "**Chế độ tối chính thức có mặt** — toàn bộ giao diện, từ nút bấm đến biểu đồ và ô "
                 "ghi chú, tự động đổi theo cài đặt hệ thống của thiết bị.",
                 "**Phím tắt bàn phím đầu tiên ra mắt** — các phím số 1 tới 7 để nhảy nhanh giữa các "
                 "trang, phím N mở Ghi chú ngày, phím / vào ô Tìm kiếm, và phím Esc để bỏ focus.",
             ]),
    ]
    render_help_changelog(HELP_CHANGELOG)
