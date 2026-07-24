# Component & quy ước UI dùng lại

Đối tượng đọc: AI agent cần thêm 1 mục/trang báo cáo mới, hoặc chỉnh sửa layout 1 trang hiện có.

## Quy ước đánh số `sec_chapter(anchor, num, title, tight_top=False, badge=None)`

Các trang báo cáo (Tổng quan/Tuần/Tháng/Năm/Dự án, Chi tiết Sách/Gundam, Sức khoẻ) được dựng từ 1
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

Mọi trang họ Báo cáo/Sách/Gundam/Dự án theo cùng 1 thứ tự luồng, xem thêm ở CLAUDE.md mục 5:
**Tổng quan → Lịch tháng (nếu trang có, luôn vị trí 2) → Phân bổ Danh mục/Dự án → Xu hướng theo
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

Cả 2 chỗ gọi PHẢI bọc trong `st.container(border=True, key="jcard_...")` (key chứa tiền tố
`jcard_` để ăn theo rule CSS card nền/viền gộp chung, xem bẫy `st.container(border=True)` ở
`theming.md`) — thiếu bước này lịch sẽ trong suốt, không có nền/viền như mọi chương khác trên
trang (bug thật đã gặp). Key mới thêm dạng `jcard_..._cal` phải được thêm vào rule
`padding-bottom: 32px` cạnh `jcard_sach_journal`/`jcard_gundam_journal` trong khối CSS chính (bù hụt
chiều cao Streamlit tự đo với `.rlcal-grid`, xem comment tại chỗ rule đó) — không thêm sẽ bị cắt
hàng ngày cuối tháng gần sát viền đáy card.

## Bẫy: `st.metric` bị CSS ẩn đi — xem `theming.md`

Đừng dùng `st.metric()` cho số liệu đơn giản; xem phần "Bẫy: `st.metric` bị ẩn toàn cục" trong
`theming.md` để biết cách thay thế đúng.

## Trang "Trợ giúp" (key nav `"Hướng dẫn"`): tour cuộn dọc, helpers `help_*`

Trang Trợ giúp là 1 trang cuộn dọc theo hành trình sử dụng (hero + mục lục chip anchor + 9
chương), KHÔNG dùng screenshot — mọi minh hoạ vẽ thuần HTML/CSS bằng token màu nên tự đúng theme.
Helpers (đều nằm cạnh nhau trong `app.py`, CSS namespace `help-` trong khối CSS chính):

- `help_chapter(anchor, num, kicker, title, lead=None)` — header 1 chương, `anchor` khớp chip mục
  lục `#help-chN` ở hero.
- `help_block(html)` — 1 thẻ nội dung `.help-card`; `html` phải là chuỗi liền mạch (không dòng
  trống giữa khối, markdown parser sẽ cắt).
- `help_table(headers, rows)` / `help_kbd(*keys)` — bảng cheat-sheet và dãy phím keycap, trả về
  string HTML để nhúng vào `help_block()`.
- `help_faq_item(question, answer_md)` — 1 câu hỏi FAQ dạng `st.expander` (không đánh số).
- `render_help_changelog(entries)` — timeline "Nhật ký phát triển", `entries` là list dict
  `HELP_CHANGELOG` khai báo ngay trong nhánh dispatch. **Quy ước 1 ngày = 1 mục** (xác nhận với
  người dùng): mọi PR có ảnh hưởng thấy được tới người dùng merge trong CÙNG 1 ngày dương lịch phải
  gộp chung vào đúng 1 dict, dù các PR đó thuộc nhiều đợt việc khác nhau — không tách nhiều mục cho
  cùng 1 ngày. Nếu ngày đang viết mục đã có 1 mục tồn tại (mục đầu `entries`, vì list xếp mới nhất
  lên đầu), SỬA mục đó (nối thêm `pr`, viết lại `title`/`bullets` cho gọn, không chỉ nối câu) thay
  vì thêm dict mới; chỉ thêm dict mới khi sang ngày khác. `pr` liệt kê ĐỦ mọi số PR thật của ngày đó
  (dạng `"223,224"`/`"185-192"`) — không đoán số trước khi PR tồn tại. 2 khoá số liệu tuỳ chọn hiện
  thành chip, tra tay tại thời điểm viết mục — KHÔNG tự tính lại lúc runtime: `total_lines` = tổng
  số dòng `app.py` tại commit merge PR **sau cùng trong ngày** (`git show <commit>:app.py | wc -l`),
  `pr_lines` = số dòng đổi (additions+deletions, tra qua GitHub API) của riêng PR sau cùng đó —
  không cộng dồn qua nhiều PR trong ngày.

Nội dung trang Trợ giúp là tài liệu người dùng cuối, không phải code phụ trợ — chỉ sửa khi thay
đổi thực sự ảnh hưởng tới trải nghiệm người dùng, không sửa như tác dụng phụ của 1 việc khác. Khi
sửa, thêm nội dung vào đúng chương theo hành trình (buổi sáng → trong ngày → cuối ngày → review →
nguồn phụ → đồng bộ → tuỳ biến → FAQ → changelog) thay vì mở chương mới.

## Icon: `_mi(name, size=13)` thay EMOJI, không dùng cả 2 kiểu lẫn nhau

Mọi nhãn/câu MỚI thêm dùng icon Material Symbols Rounded qua `_mi('material_icon_name')` (chèn
`<span style="font-family:'Material Symbols Rounded';...">` vào chuỗi HTML tĩnh) -- KHÔNG dùng
emoji. Font này Streamlit đã tự load sẵn cho icon `:material/x:` của chính nó nên không cần nhúng
thêm. Áp dụng cho toàn bộ code mới, không riêng 1 trang nào.

## `render_period_billboard(...)`: khi nào dùng chung key mặc định `"bc_billboard"` được

Hầu hết nơi gọi (Báo cáo mọi sub-tab, Sách/Gundam Tổng quan, Dự án, Tuỳ biến, cả 3 sub-tab Sức
khoẻ) **không cần truyền `key=` riêng** -- an toàn vì mỗi nav/sub-tab dispatch qua 1 chuỗi
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
dụ: mọi widget trang Sức khoẻ đặt key tiền tố `hm_` (`hm_chart_cat`, `hm_hist_year`,
`hm_entry_date`...) → 1 rule `[class*="st-key-hm_"] [data-testid="stWidgetLabel"] p { font-weight:
700 !important; }` áp dụng đồng bộ cho nhãn mọi widget trong đó. Đặt tên key nhất quán tiền tố
theo trang/feature ngay từ đầu để tận dụng được trick này về sau, không cần refactor lại.

## Popup xác nhận/tra cứu: `@st.dialog("Tiêu đề")`

Nội dung phá huỷ dữ liệu (Tuỳ biến → Khôi phục/Xoá toàn bộ) hoặc chỉ tra cứu/copy khi cần (Sức
khoẻ → Dữ liệu đầu vào → "Xem định dạng JSON mẫu") đặt trong hàm lồng bên trong hàm render, đánh
dấu `@st.dialog("Tiêu đề")`; nút bên ngoài chỉ có nhiệm vụ GỌI hàm đó (`if st.button(...):
_xxx_dialog()`), không tự vẽ nội dung — tránh nội dung phụ (ít dùng, hoặc cần xác nhận trước khi
phá huỷ) chiếm không gian cố định trên trang.

## Chuyển sub-tab bằng code (không phải người dùng click): cờ chờ xử lý, KHÔNG set trực tiếp session_state của widget

`st.segmented_control(..., key="X_picker")` dùng pattern chung: đọc/ghi qua 1 key riêng
(`st.session_state["X"]`) tách biệt khỏi key CỦA WIDGET (`"X_picker"`) -- xem `bc_sub`/`hm_sub` ở
`architecture-navigation.md`. Muốn nhảy sang sub-tab khác từ 1 nút bấm ở NƠI KHÁC trong cùng lượt
chạy (vd nút "Sửa lần khám này" ở Dữ liệu đầu vào nhảy sang Lịch sử) — TUYỆT ĐỐI không set
`st.session_state["X_picker"] = "..."` ngay tại nút bấm đó: nếu widget `segmented_control` đã
instantiate TRƯỚC nút bấm này trong CÙNG lượt chạy (thường vậy, vì nó luôn nằm ở đầu hàm dispatch
trang), Streamlit raise `StreamlitAPIException: cannot be modified after the widget... is
instantiated` (bug thật đã gặp). Cách đúng: nút bấm chỉ ghi 1 cờ tạm (`st.session_state["_X_jump"]
= "Lịch sử"`) rồi `st.rerun()`; xử lý cờ đó ở ĐẦU hàm dispatch, TRƯỚC dòng gọi
`segmented_control` (`if "_X_jump" in st.session_state: ... st.session_state["X_picker"] = ...`) --
lúc đó là lượt chạy MỚI, set trước khi widget instantiate nên hợp lệ.

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
  độc lập, không nhóm cha/con: `render_health_full_table`, `render_health_log_table`,
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
tính màu 1 ô, dùng bởi `render_data_table()`/`render_detail_table()`/`render_period_table()`/
`render_health_log_table()` — mỗi hàm ứng với 1 kiểu bảng (theo kỳ/theo dự án/theo ngày sức khoẻ)
nhưng cùng chung style/cơ chế tô màu này. Màu heat cell lấy theo hue suy ra từ `ACCENT` (xem
`theming.md`) — không hardcode thang màu riêng cho bảng mới, tái dùng cùng cơ chế hue để đổi
accent tự động đổi luôn bảng.
