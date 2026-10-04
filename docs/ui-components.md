# Component & quy ước UI dùng lại

Đối tượng đọc: Claude Code cần thêm 1 mục/trang báo cáo mới, hoặc chỉnh sửa layout 1 trang hiện có.

## Quy ước đánh số `sec_chapter(anchor, num, title, tight_top=False, badge=None)`

Các trang báo cáo (Tổng quan/Tuần/Tháng/Năm/Dự án, Chi tiết Sách/Gundam) được dựng từ 1
chuỗi lời gọi `sec_chapter(anchor, num, ...)` đánh số thứ tự (KHÔNG phải `st.expander` — mỗi
chương luôn mở sẵn, cuộn dọc bình thường). Đây là quy ước UI có chủ đích, không phải đặt tên tuỳ
tiện. **Khi thêm, xoá, hoặc đổi chỗ 1 mục giữa chuỗi, phải đánh số lại toàn bộ các mục phía sau
trong cùng trang** (cả tham số `num` truyền vào `sec_chapter` lẫn chuỗi TOC chip truyền cho
`render_period_billboard(...)` ngay phía trên) — để số thứ tự luôn liên tục 1, 2, 3... không nhảy
cóc, và chip mục lục luôn khớp đúng chương nó trỏ tới.

Ngoại lệ: mục có điều kiện hiển thị (ví dụ mục "Nhật ký đọc" chỉ hiện khi Dự án đang xem khớp 1
cuốn sách) truyền `num=None`, để giữ nguyên số của các mục cố định khác dù mục điều kiện có hiện
hay không.

## Thứ tự chương chuẩn cho trang báo cáo (đã chốt qua đợt tái cấu trúc UX)

Mọi trang họ Báo cáo/Sách/Gundam/Dự án theo cùng 1 thứ tự luồng, xem thêm ở `CLAUDE.md`:
**Tổng quan → Lịch tháng (nếu trang có, luôn vị trí 2; ở Năm chương này tên "Lịch") → Phân bổ Danh mục/Dự án → Xu hướng theo
thời gian → Nhật ký/ghi chú → Bảng số liệu (luôn cuối cùng)**. Chương "Lịch tháng" (trước gọi "Biểu
đồ lịch") hiện chỉ còn ở Báo cáo Tháng/Năm — đã bỏ khỏi Tổng quan (xác nhận với người dùng: trang
tổng hợp toàn thời gian không cần 1 lịch tháng đơn lẻ). 2 hệ quả cụ thể khi thêm/sửa 1 trang kiểu
này:

- Nếu trang đã có 1 chương "Phân bổ Danh mục/Dự án" riêng (vd `frag_category_bars`/
  `render_year_category_bars`), chương Tổng quan **không** cần thêm Top-3 Danh mục/Dự án nữa — 2
  nơi cùng hiện 1 dữ liệu là dư (xem `show_top3=False` ở Tuần, đã bỏ ở Tháng/Năm).
- 2 (hoặc nhiều) chương "xu hướng theo thời gian" khác trục (vd theo tuần/theo ngày/theo khung
  giờ) nên gộp thành 1 chương dùng `st.segmented_control` chọn góc nhìn, thay vì tách rời nhiều
  chương liền kề (xem "Xu hướng" ở Báo cáo Tổng quan/Tháng/Dự án).

## Tránh lặp hero với billboard (`render_stat_panel(hero_items=...)`)

`render_period_billboard()` đã show 1 con số to (`big_num`) + vài chip số liệu ở cột phải — chương
đầu tiên ngay dưới nó (thường dùng `render_stat_panel`) **không được lặp lại đúng chỉ số đó làm
hero**, chỉ nên thêm chỉ số MỚI (trung bình/so sánh/chuỗi ngày...). Cách xử lý tuỳ trường hợp:
- Bỏ hẳn item hero bị trùng, giữ `hero_items=[]` nếu billboard đã đủ (Báo cáo Dự án, Sách/Gundam
  Chi tiết).
- Trùng chỉ ở 1 trong 2 trang dùng chung hàm: tham số hoá theo `page_name` (Gundam Tổng quan bỏ
  hero "Tổng giờ" vì billboard "Phòng chiếu" show tổng giờ toàn thời gian, nhưng Sách vẫn giữ vì
  billboard Sách chỉ show giờ NĂM NAY — không trùng phạm vi).
- Hero có deltas (so kỳ trước/so trung bình) không tính là trùng thật dù giá trị tuyệt đối giống
  billboard — deltas là thông tin mới (xem `_render_period_overview_hero`, dùng chung cho Tuần/
  Tháng/Năm, KHÔNG cần trim).

## `render_stat_panel(hero_items, sections, footer, groups, card_style)`

Component dùng chung cho gần như mọi trang báo cáo: khối "số liệu hero lớn + các hàng chip nhãn
nhỏ bên dưới". Khi cần 1 khối tổng quan số liệu mới, **mở rộng component này** (thêm tham số nếu
cần) thay vì tự viết 1 layout card mới từ đầu — tự viết riêng sẽ lệch style so với phần còn lại của
app. Dùng tham số `card_style` cho các chỉnh sửa margin/width chỉ áp dụng ở 1 nơi gọi — không sửa
giá trị mặc định của hàm vì điều đó ảnh hưởng TẤT CẢ nơi đang gọi nó.

## Lịch tháng dạng lưới: `_render_reading_calendar_month()` / `_render_report_calendar_month()`

2 hàm SONG SONG, cùng dùng chung khung `.rlcal-cell`/`.rlcal-grid`/`.rlcal-tip` (CSS `RLCAL_CSS`) —
1 ô = 1 ngày trong tháng, tô nền heat theo `_reading_cal_lvl(mins)` (6 bậc giờ CỐ ĐỊNH, không co
giãn riêng theo tháng đang xem), hover/chạm hiện tooltip, cả ô là link nhảy sang "Hôm nay" của đúng
ngày đó (qua `_day_link_href()`, xem `architecture-navigation.md`):

- `_render_reading_calendar_month(ns, rl_df, sessions_df, kh_df, empty_noun)` — mục "Nhật ký đọc"/
  "Nhật ký xem" (Sách/Gundam → Tổng quan). Mỗi ô: chip thời gian đọc/xem + tối đa 2 chip tên phần đã
  hoàn thành (`.rlcal-done`/`.rlcal-donechip`) + 1 dòng icon số trích dẫn (`.rlcal-quote`, chỉ icon +
  số, KHÔNG có nhãn chữ "trích dẫn").
- `_render_report_calendar_month(cur_y, cur_m, df_all, wc_df, rl_df, notes_df)` — chương "Lịch
  tháng" của Báo cáo Tổng quan/Tháng/Năm (xem mục thứ tự chương chuẩn ở trên). Adapt từ hàm trên:
  chip thời gian đổi thành TỔNG thời gian tập trung cả ngày (mọi Dự án, không riêng đọc/xem), tối đa
  2 chip là Dự án nhiều giờ nhất/nhì trong ngày (tái dùng nguyên `.rlcal-done`/`.rlcal-donechip`,
  chỉ 1 chip nếu ngày đó có đúng 1 dự án), và 1 hàng icon RIÊNG LUÔN HIỆN (`REPCAL_CSS`,
  `.repcal-icons`/`.repcal-ic` — khác `.rlcal-counts` của hàm trên CHỈ hiện ở mobile): số lịch hẹn/
  số phần sách đã đọc/số phần Gundam đã xem/số từ Ghi chú chính, ẩn từng icon nếu bằng 0. KHÔNG tự
  điều hướng tháng — `(cur_y, cur_m)` do caller truyền vào.
- `frag_report_calendar_month(ns, df_all, wc_df, rl_df, notes_df, lo_ym=None, hi_ym=None,
  default_ym=None)` — bản có stepper tháng (‹/mặc định/›, session_state khoá `repcal_ym_<ns>`) bọc
  quanh hàm trên, dùng cho Tổng quan (bó biên theo khoảng dữ liệu thật, kẹp trên bởi tháng hiện tại)
  và Năm (bó biên trong ĐÚNG năm đang xem qua `lo_ym`/`hi_ym` truyền tay). Nhánh Tháng của Báo cáo
  gọi THẲNG `_render_report_calendar_month()` (không qua bản có stepper) vì đã có `period_stepper()`
  riêng chọn tháng ở đầu trang — thêm 1 bộ điều hướng tháng thứ 2 là dư thừa.

- **Báo cáo → Năm có thêm góc nhìn "Cả năm"**: chương 2 của Năm tên "Lịch" (không còn "Lịch tháng"; số
  chương và chip mục lục `"2 · Lịch"` giữ nguyên) mở đầu bằng
  `st.segmented_control("Xem theo", ["Cả năm", "Từng tháng"], key="bc_nam_cal_view")`. "Từng tháng" là
  đúng code lịch lưới ở trên (`frag_report_calendar_month`, card `jcard_bcnam_cal`); "Cả năm" là
  `render_year_heatmap(df_y, year)` (card `jcard_bcnam_heat`) -- xem mục "Biểu đồ ECharts" bên dưới.

Cả 2 chỗ gọi PHẢI bọc trong `st.container(border=True, key="jcard_...")` (key chứa tiền tố
`jcard_` để ăn theo rule CSS card nền/viền gộp chung, xem bẫy `st.container(border=True)` ở
`theming.md`) — thiếu bước này lịch sẽ trong suốt, không có nền/viền như mọi chương khác trên
trang (bug thật đã gặp). Key mới thêm dạng `jcard_..._cal` phải được thêm vào rule
`padding-bottom: 32px` cạnh `jcard_sach_journal`/`jcard_gundam_journal` trong khối CSS chính (bù hụt
chiều cao Streamlit tự đo với `.rlcal-grid`, xem comment tại chỗ rule đó) — không thêm sẽ bị cắt
hàng ngày cuối tháng gần sát viền đáy card.

## Biểu đồ mới ở Báo cáo (Giai đoạn 3): rừng tháng, lịch nhiệt năm, các giai đoạn

- **"Khu rừng tháng này"** — `render_month_forest(df_m, y, m)` (card `jcard_bcthang_forest`), Báo cáo →
  Tháng, chương 1 "Tổng quan" ngay sau `render_month_highlights()` (không đổi số chương). ECharts scatter:
  mỗi phiên 1 cây (`_FOREST_TREE_PATH`, `path://`), x = ngày trong tháng (đủ 1..N, nhãn ở 1 và mỗi bội số
  của 5), y = thứ tự phiên trong ngày theo giờ bắt đầu, 1 series/Nhóm màu `COLOR_MAP` (đặt
  `itemStyle.opacity=1` vì scatter mặc định 0.8 làm cây nhạt hơn màu Nhóm ở chương "Phân bổ nhóm"),
  cỡ cây theo căn bậc hai số phút (10–24px, `_forest_symbol_size`), cao `clamp(180+22*phiên/ngày tối đa,
  220, 440)`. Dựng spec ở `_forest_spec()` (thuần dict JSON, kiểm tra được bằng script).
- **Lịch nhiệt cả năm** — `render_year_heatmap(df_y, year)` (card `jcard_bcnam_heat`), `_year_heatmap_spec()`:
  ECharts `calendar` + `heatmap`, thang `piecewise` dùng ĐÚNG 5 bậc có giờ của `_reading_cal_lvl()`
  (`_YEAR_HEAT_PIECES`) và `_teal_shades(6)[1:]` để khớp mọi lịch khác; ngày 0 giờ không có data item.
  **Hướng DỌC** (7 cột thứ × ~54 hàng tuần, cao 800px) cho mọi khổ: hướng ngang 53 cột ở 390px chỉ ~4.6px/ô
  và nhãn tháng chồng nhau; Python không phát hiện được độ rộng màn hình nên không chọn theo khổ.
- **"Theo giai đoạn"** — lựa chọn thứ 3 của `bc_tq_trend_view` (Báo cáo → Tổng quan, chương 2 "Xu hướng"),
  `render_eras(df)`: `_compute_eras(df, today)` (`@st.cache_data`) chia lịch sử thành "mùa" (Nhóm nhiều
  giờ nhất từng tháng, gộp tháng liền cùng Nhóm) và "khoảng nghỉ" (`ERA_BREAK_DAYS` = 21 ngày, kể cả
  khoảng nghỉ kéo tới hôm nay); tháng đơn lẻ mà Nhóm dẫn đầu < `ERA_NOISE_SHARE` (40%) giờ tháng đó bị
  nhập vào mùa trước (cùng đoạn hoạt động, không nhập qua khoảng nghỉ). Hiển thị: dải ngang Plotly 1
  hàng (`_eras_fig`; dùng Plotly vì ECharts không có series `custom`, và `format_plotly_fig` gắn
  customdata theo trục y nên được ghi đè lại sau đó) + bảng `.dtbl` mới nhất lên đầu. Plotly bọc trong
  `[data-testid="stPlotlyChart"]` có padding 14px + `overflow:hidden`, cắt ~30px đáy svg -- nên fig này
  chừa `margin b=56` để nhãn trục x không bị cắt.

## Huy hiệu ghi nhận sau, "Phát hiện" và "Ôn hôm nay" (Giai đoạn 4)

Cả ba chỉ **ghi nhận/hồi cứu** điều đã xảy ra, không đặt mục tiêu hay nhắc nhở.

- **Huy hiệu** — `_compute_milestones(df)` (`@st.cache_data`, chỉ phụ thuộc `df`, không lấy nguồn sách/
  Kindle) trả list `{date, kind, icon, title, detail}` theo ngày: tổng giờ, số cây, giờ theo Dự án, phiên
  dài (phiên ĐẦU TIÊN đạt ngưỡng), chuỗi ngày (ngày đầu tiên một chuỗi đạt N) và "Quay lại" (mỗi khoảng
  nghỉ >= `COMEBACK_MIN_GAP`). Ngưỡng là các tuple `MILESTONE_*` cạnh `RECORD_MIN_DAYS`. Phiên sắp theo
  `Thời gian bắt đầu` trước khi cộng dồn; 1 phiên vượt nhiều ngưỡng thì ghi nhận đủ từng ngưỡng.
  - **Gắn vào hệ chip "Kỷ lục"**: `_compute_alltime_records()` thêm mỗi mốc vào `day_badges` dạng
    `{"kind": "milestone", "title", "icon"}` và trả thêm key `"milestones"`. `_record_chips_html()` render
    `<span class='jchip rec ms'>` (class `ms` tắt icon cúp mặc định của `.jchip.rec::before` vì huy hiệu
    có icon `_mi()` riêng) và đổi nhãn hàng thành "Kỷ lục & huy hiệu" CHỈ khi có ít nhất 1 huy hiệu --
    nên ghi chú ngày, Nhật ký, "Ngày này năm trước/tuần trước" và ngăn kéo "Một ngày ngẫu nhiên" tự hiện
    huy hiệu. Hệ quả: ngày có huy hiệu cũng thành 1 dòng ở Nhật ký Tuần/Tháng (như ngày giữ kỷ lục).
    Thêm 1 `kind` mới vào `day_badges` thì `_record_chips_html()` là nơi DUY NHẤT đọc `b["kind"]`.
  - **Thẻ "Huy hiệu"** (`_render_badges_card`, card `jcard_badges`) ở Báo cáo → Tổng quan, chương 1 sau
    `render_top_3`: 8 huy hiệu mới nhất + nút "Xem tất cả (N)" mở `_badges_dialog()`
    (`@st.dialog("Huy hiệu", position="right")`, nhóm theo năm, mới nhất trước). Ẩn khi chưa có huy hiệu.
  - **Toast** `_toast_today_milestones(df)` (gọi ngay sau `prep_analysis_data()`): có huy hiệu ghi nhận
    đúng `_today_vn()` thì toast 1 lần mỗi session (`_milestone_toasted`, đặt ngay lần kiểm tra đầu),
    thường ngay sau khi `_auto_sync_on_open()` nạp dữ liệu mới.
- **"Phát hiện"** — `_compute_insights(df, wc, rl, notes, today)` (`@st.cache_data`) trả list
  `(icon, html_sentence)`, hiển thị ở card `jcard_insights` ngay sau thẻ Huy hiệu (`_render_insights_card`).
  4 nhận xét (lịch hẹn ↔ giờ tập trung T2–T6, đọc sách ↔ giờ tập trung ngoài đọc sách, ghi chú ↔ tổng giờ,
  buổi có phiên dài nhất), mỗi cái có ngưỡng mẫu tối thiểu (8–15 ngày/phiên) và chênh lệch tương đối
  >= 15% (20% với buổi); không đạt thì BỎ HẲN (không có câu "chưa đủ dữ liệu"); nguồn phụ rỗng/None không
  crash; cả card ẩn nếu không có nhận xét nào. Cuối card luôn có câu "tương quan, không phải quan hệ
  nhân quả". Câu chữ trung tính + có số liệu, không khuyên bảo.
- **"Ôn hôm nay"** — `_render_kindle_review(kh)` (card `jcard_kqreview`) đầu sub-tab Sách → "Trích dẫn":
  5 highlight chọn bằng `random.Random(f"{hôm nay}|{kq_review_salt}")` (cố định trong ngày, "Bộ khác" tăng
  salt qua `on_click`), trọng số Yêu thích x3, không trùng, loại trích dẫn đang hiện ở billboard Hôm nay.
  Chỉ số trích dẫn billboard được TÍNH LẠI theo seed (hoặc đọc `kq_daily_idx` nếu đã có cho đúng hôm nay)
  mà KHÔNG gọi `_kindle_quote_of_day()` -- hàm đó ghi `kq_daily_*` vào session_state và sẽ lệch trạng thái
  billboard. Mỗi câu là `_render_kindle_quote_row(..., key_suffix="kqreview_")` (khoá riêng, không đụng
  `fav_` của danh sách bên dưới). Dưới 6 highlight thì ẩn khối.

## Bẫy: `st.metric` bị CSS ẩn đi — xem `theming.md`

Đừng dùng `st.metric()` cho số liệu đơn giản; xem phần "Bẫy: `st.metric` bị ẩn toàn cục" trong
`theming.md` để biết cách thay thế đúng.

## Icon: `_mi(name, size=13)` thay EMOJI, không dùng cả 2 kiểu lẫn nhau

Mọi nhãn/câu MỚI thêm dùng icon Material Symbols Rounded qua `_mi('material_icon_name')` (chèn
`<span style="font-family:'Material Symbols Rounded';...">` vào chuỗi HTML tĩnh) -- KHÔNG dùng
emoji. Font này Streamlit đã tự load sẵn cho icon `:material/x:` của chính nó nên không cần nhúng
thêm. Áp dụng cho toàn bộ code mới, không riêng 1 trang nào.

## `render_period_billboard(...)`: khi nào dùng chung key mặc định `"bc_billboard"` được

Hầu hết nơi gọi (Báo cáo mọi sub-tab, Sách/Gundam Tổng quan, Dự án, Tuỳ biến)
**không cần truyền `key=` riêng** -- an toàn vì mỗi nav/sub-tab dispatch qua 1 chuỗi
`if/elif` (xem `architecture-navigation.md`), nên tại 1 lượt chạy chỉ ĐÚNG 1 nhánh thực thi, không
có 2 billboard nào cùng vẽ. Chỉ cần key riêng khi 2 lời gọi CÓ THỂ cùng nằm trong 1 lượt chạy --
ca thật duy nhất là Sách/Gundam "Chi tiết" dùng `st.tabs()` (Streamlit render TOÀN BỘ nội dung mọi
tab, không chỉ tab active), nên phải đặt `key="bc_billboard_detail"` khác `key` mặc định của
"Tổng quan". Đặt `key` mới nào cũng phải thêm vào ĐỦ mọi rule CSS liệt kê key (`.st-key-
today_billboard, .st-key-bc_billboard, ...` -- khớp CHÍNH XÁC chuỗi, không dùng substring chung vì
"..._detail" không còn chứa nguyên vẹn "billboard" gốc).

## Style riêng 1 khu vực bằng tiền tố `key=` chung, không cần bọc container

Mọi widget đặt `key=` đều tự có class `st-key-<key>` trên chính element đó (không chỉ
`st.container(key=...)` mới có) -- nên style riêng MỌI widget trong 1 trang/feature mà không cần
bọc thêm container nào, chỉ cần **cùng 1 tiền tố key** rồi CSS `[class*="st-key-<tiền tố>_"]`. Ví
dụ: mọi widget trang Tuỳ biến đã đặt sẵn key tiền tố `tb_` (`tb_backup_card`, `tb_restore_card`,
`tb_wipe_card`...) -- nếu cần style riêng chung cho cả nhóm, chỉ cần 1 rule
`[class*="st-key-tb_"] ... { ... }` là áp dụng đồng bộ cho mọi widget trong đó, không cần bọc thêm
container. Đặt tên key nhất quán tiền tố
theo trang/feature ngay từ đầu để tận dụng được trick này về sau, không cần refactor lại.

## Popup xác nhận/tra cứu: `@st.dialog("Tiêu đề")`

Nội dung phá huỷ dữ liệu (Tuỳ biến → Khôi phục/Xoá toàn bộ) hoặc chỉ tra cứu/copy khi cần đặt
trong hàm lồng bên trong hàm render, đánh
dấu `@st.dialog("Tiêu đề")`; nút bên ngoài chỉ có nhiệm vụ GỌI hàm đó (`if st.button(...):
_xxx_dialog()`), không tự vẽ nội dung — tránh nội dung phụ (ít dùng, hoặc cần xác nhận trước khi
phá huỷ) chiếm không gian cố định trên trang.

## Ngăn kéo xem nhanh ngày: "Một ngày ngẫu nhiên" (`_peek_dialog`)

Nút `st.button(..., key="sb_peek_btn")` trong sidebar (ngay sau khối `.sb-widget`, chỉ khi df không
rỗng và `_peek_pool(df)` có ngày) mở `@st.dialog("Một ngày trong quá khứ", position="right",
width="medium")` -- ngăn kéo bên phải (mobile: gần toàn màn hình) để gặp lại 1 ngày cũ mà không
rời trang đang xem. Cần Streamlit >= 1.65 (`position=`, và `live=` ở ô Tìm kiếm).

- **Dialog định nghĩa ở cấp module** (dialog là fragment) và được GỌI ngoài khối `with st.sidebar:`
  qua cờ `_peek_clicked`, không dựng dialog trong ngữ cảnh sidebar. Ngày đang xem nằm ở
  `st.session_state["peek_day"]`; nút "Ngày khác" (`peek_next_btn`) bốc ngày mới rồi
  `st.rerun(scope="fragment")` để không rerun cả trang.
- **Chọn ngày** (`_peek_pool` / `_pick_peek_day`): ngày có phiên Forest, ghi chú chính >=
  `PEEK_MIN_NOTE_CHARS` (40) ký tự văn bản thuần, hoặc trích dẫn Kindle (`Ngày thêm`, chỉ
  `highlight`); loại `PEEK_RECENT_EXCLUDE_DAYS` (7) ngày gần nhất; ngày có ghi chú trọng số x2;
  `random.Random()` không seed; không lặp lại đúng ngày đang hiện (trừ khi pool chỉ còn 1 ngày).
- **Nội dung** do `_day_peek_html(d, df)` dựng (thuần HTML, theo thứ tự khối của
  `render_note_editor()`): ngày + khoảng cách (`_fmt_ago_ymd`) + link `_day_link_html` → chip Kỷ lục
  → tóm tắt phiên (`_session_summary_chips_html`, dùng chung với thẻ "Chào mừng trở lại") → chip
  sách/Gundam → ghi chú chính (`.note-html`; >= 1200 ký tự thì chỉ hiện đoạn văn
  bản thuần đã escape, không cắt HTML giữa thẻ) → tối đa 3 trích dẫn Kindle. Link
  `target=_self` mở session mới nên đóng dialog -- đúng ý.
- **CSS**: nền modal đã ép `var(--card)` (rule `[data-testid="stDialog"] > div`); chữ trong dialog
  dùng chung font thân chữ qua selector `[data-testid="stDialog"] *` (dialog render ở portal ngoài
  `.stApp`, không thì rơi về Source Sans mặc định).

## Thẻ "Chào mừng trở lại" (trang Hôm nay)

`_render_welcome_back(df, sel, day_df)` ngay dưới billboard: chỉ khi `sel` là hôm nay và đã nghỉ >=
`COMEBACK_MIN_GAP` ngày (`_comeback_info`). Hôm nay chưa có phiên -> card `jcard_welcome` (không phải
chương, không đánh số, không thêm chip mục lục); đã có phiên -> không card, footer của
`render_stat_panel` ở "Tổng quan ngày". Toast một lần mỗi session (`_welcome_toasted`).

## Chuyển sub-tab bằng code (không phải người dùng click): cờ chờ xử lý, KHÔNG set trực tiếp session_state của widget

`st.segmented_control(..., key="X_picker")` dùng pattern chung: đọc/ghi qua 1 key riêng
(`st.session_state["X"]`) tách biệt khỏi key CỦA WIDGET (`"X_picker"`) -- xem `bc_sub`/`tb_sub` ở
`architecture-navigation.md`. Muốn nhảy sang sub-tab khác từ 1 nút bấm ở NƠI KHÁC trong cùng lượt
chạy (vd click biểu đồ Xu hướng nhảy sang sub-tab Dự án) — TUYỆT ĐỐI không set
`st.session_state["X_picker"] = "..."` ngay tại nút bấm đó: nếu widget `segmented_control` đã
instantiate TRƯỚC nút bấm này trong CÙNG lượt chạy, Streamlit raise `StreamlitAPIException: cannot
be modified after the widget... is instantiated` (bug thật đã gặp). Cách đúng: nút bấm chỉ ghi 1 cờ
tạm (`st.session_state["_X_jump"] = "Dự án"`) rồi `st.rerun()`; xử lý cờ đó TRƯỚC dòng gọi
`segmented_control` (`if "_X_jump" in st.session_state: ... st.session_state["X_picker"] = ...`) --
lúc đó là lượt chạy MỚI, set trước khi widget instantiate nên hợp lệ. Với `bc_sub_picker`/
`tb_sub_picker` (render trong `st.sidebar`, ngay sau khi `nav` được xác định, xem
`architecture-navigation.md`) widget instantiate RẤT SỚM trong lượt chạy -- cờ `_bc_sub_jump`
vì vậy phải xử lý ở module-level ngay cạnh khai báo `BAOCAO_SUBS`/`TUYBIEN_SUBS`,
KHÔNG phải trong hàm render trang (trang được dispatch/gọi MUỘN hơn nhiều so với lúc widget sidebar
đã render xong).

## Tooltip tức thời cho thanh phân bổ HTML: `data-tip` + CSS `:hover::after`, không dùng `title=`

Các thanh phân bổ tự dựng bằng `<div>` xếp cạnh nhau (vd `render_project_rhythm`, `render_session_bar`)
trước đây dùng `title='...'` (tooltip mặc định của trình duyệt — có độ trễ ~1s, kiểu chữ theo OS,
không theo theme app). Muốn tooltip hiện NGAY khi rê chuột và đúng theme: đặt `class='rhythm-seg'`
(hoặc class tương tự) + `data-tip='...'` lên mỗi ô, rồi 1 CSS rule dùng chung `.rhythm-seg:hover::after
{ content: attr(data-tip); ... }` (xem `_RHYTHM_TIP_CSS`). **Lưu ý bẫy overflow:hidden**: nếu hàng chứa các ô
đang dùng `overflow:hidden` để bo góc cả hàng, tooltip (định vị `position:absolute` bên trong ô) sẽ
bị cắt mất — thay bằng bo góc RIÊNG ô đầu/ô cuối (`border-radius` khác nhau theo vị trí trong loop)
thay vì bọc `overflow:hidden` quanh cả hàng.

## Phân trang bảng dài: `TABLE_PAGE_SIZE` + 3 helper dùng chung (`_table_page_slice`/`_paginate_row_blocks`/`_render_table_pagination`)

**Mọi bảng `.dtbl` trong app tối đa `TABLE_PAGE_SIZE` = 15 dòng dữ liệu/trang** (không tính dòng
đề mục/tiêu đề/Tổng — xác nhận với người dùng, áp dụng đồng loạt cho MỌI bảng, kể cả bảng đã có
phân trang từ trước với ngưỡng khác). Không tự viết lại code cắt lát/pagination ở nơi gọi mới — 3
helper định nghĩa cạnh `DTBL_CSS` đã lo đủ:

- `_table_page_slice(n, key, page_size=TABLE_PAGE_SIZE)` — dùng cho bảng PHẲNG (mỗi dòng dữ liệu
  độc lập, không nhóm cha/con:
  `render_period_table`, `render_project_recent_sessions`, bảng "Danh sách phiên" ở Hôm nay, bảng
  "Dữ liệu làm việc hiện tại" ở Tuỳ biến...). Trả `(start, end, num_pages, paged)`, tự **clamp**
  `st.session_state[key]` về `num_pages` hợp lệ (phòng khi dữ liệu co lại sau xoá) — gọi TRƯỚC khi
  cắt lát DataFrame/list.
- `_paginate_row_blocks(blocks, page_size=TABLE_PAGE_SIZE)` — dùng cho bảng có NHÓM cha/con (1
  Danh mục + các Dự án con của nó phải nằm trọn 1 trang, không tách rời — `render_data_table`,
  `render_detail_table`). `blocks` là `list[(html, n_rows)]` theo đúng thứ tự muốn hiển thị; trả
  `list[str]` (mỗi phần tử là `<tbody>` HTML của 1 trang) — đơn vị phân trang là NGUYÊN 1 block, 1
  block tự vượt `page_size` (nhóm quá nhiều dòng con) thì vẫn để riêng 1 trang, chấp nhận vượt nhẹ
  ngưỡng thay vì tách nhóm.
- `_render_table_pagination(num_pages, key, caption)` — vẽ `st.pagination(num_pages, key=key)`
  trong `st.container(key=key + "_pag")` NGAY DƯỚI bảng (không phải trên) + 1 dòng `caption` căn
  giữa ngay dưới đó. `caption` tự soạn ở nơi gọi: bảng phẳng dùng "Hiển thị <đơn vị> X–Y / N", bảng
  theo nhóm (không có "1 dòng = 1 gì" rõ ràng) dùng "Trang X/Y".

CSS căn giữa/margin áp dụng qua **quy ước đặt tên**, không cần thêm rule mỗi khi có bảng mới: mọi
key container pagination phải có hậu tố `_pag` (đã tự đúng nếu gọi qua `_render_table_pagination`),
khớp rule dùng chung `[class*="st-key-"][class*="_pag"]` trong khối CSS chính.

## Ép 2+ thẻ ngang cao bằng nhau: class đánh dấu + `:has()` + `align-items:stretch`

Rule chung `[data-testid="stHorizontalBlock"] { align-items: flex-start !important; }` (khối CSS
chính) khiến MỌI hàng `st.columns()` mặc định co mỗi cột theo đúng chiều cao nội dung riêng — 2 thẻ
cạnh nhau có số dòng nội dung khác nhau sẽ lệch cao. Cách ép cao bằng nhau mà không cần bọc thêm
`st.container(key=...)` ngoài mỗi cột: gắn 1 class dùng chung (vd `month-hl-card`, `year-hl-card`,
hoặc dùng key riêng như `tb_backup_card`) lên chính div bên trong mỗi cột, rồi:
```css
[data-testid="stHorizontalBlock"]:has(.month-hl-card) { align-items: stretch !important; }
.month-hl-card { height: 100%; }
```
Lưu ý: `align-items:stretch` chỉ ép KHUNG thẻ cao bằng nhau, không tự lấp nội dung ngắn hơn — nếu 2
thẻ lệch hẳn SỐ DÒNG nội dung (vd 1 thẻ 3 dòng, 1 thẻ 4 dòng), khung vẫn bằng cao nhưng nhìn lệch
khoảng trắng cuối thẻ ngắn. Xử lý đúng là thêm/bớt 1 dòng nội dung thật cho khớp số dòng (xem "Ngày
nhiều phiên nhất" thêm vào thẻ "Kỷ lục trong tháng" để khớp 4 dòng với thẻ "So với tháng trước" bên
cạnh), không chỉ dựa vào CSS.

## Bảng số liệu dạng heat table (`DTBL_CSS`)

Style (`DTBL_CSS`) + các hàm dựng bảng số liệu có tô màu theo giá trị (heat cell): `_heat_cell()`
tính màu 1 ô, dùng bởi `render_data_table()`/`render_detail_table()`/`render_period_table()`
— mỗi hàm ứng với 1 kiểu bảng (theo kỳ/theo dự án/theo ngày)
nhưng cùng chung style/cơ chế tô màu này. Màu heat cell lấy theo hue suy ra từ `ACCENT` (xem
`theming.md`) — không hardcode thang màu riêng cho bảng mới, tái dùng cùng cơ chế hue để đổi
accent tự động đổi luôn bảng.
