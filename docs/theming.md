# Theming: CSS custom properties, không phải 2 bộ stylesheet

Đối tượng đọc: Claude Code cần thêm UI mới, sửa màu sắc, hoặc đụng vào khối CSS lớn trong `app.py`.

## `IS_DARK` + `--token` CSS variables

`IS_DARK` được suy ra 1 lần từ `st.context.theme.type` ngay khi module load — không tính lại giữa
chừng trang. Một khối `--token` (`--bg`, `--card`, `--text`, `--text-2/3/4`, `--border`,
`--divider`, `--accent`, `--accent-rgb`, `--accent-dark`) được bơm vào `:root{...}`, giá trị chọn
theo `IS_DARK`. **Mọi UI mới nên dùng `var(--token)` thay vì mã màu cứng** — 1 mã hex mới thêm vào
gần như chắc chắn là 1 bug dark-mode đang chờ xảy ra (đúng ở light mode, sai/không đọc được ở dark
mode hoặc ngược lại).

## Khối CSS chính là string thường — KHÔNG chuyển thành f-string

Khối CSS lớn nhất trong `app.py` được viết là 1 string Python bình thường, không phải f-string, dù
phần lớn code khác trong file dùng f-string thoải mái. Lý do: hàng trăm dấu `{`/`}` literal trong
cú pháp CSS (`{ }` bao mỗi rule) sẽ đều bị Python hiểu nhầm là placeholder nếu đổi sang f-string,
phải escape thành `{{`/`}}` ở mọi chỗ — không đáng đổi. Nếu cần chèn 1 giá trị Python động vào CSS,
dùng `.format()`/nối chuỗi cho đúng đúng đoạn cần, không đổi kiểu cả khối.

## Màu accent: 1 giá trị, lan ra 3 cơ chế khác nhau

`ACCENT` (chọn từ `ACCENT_PRESETS`, lưu bền trong bảng `settings`) không chỉ đổi màu qua CSS — nó
lan ra 3 nơi bằng 3 cơ chế khác nhau, phải nhớ cả 3 khi thêm 1 UI element có màu accent:

1. **CSS** — qua `var(--accent)`, `var(--accent-rgb)`, `var(--accent-dark)` — tự động, không cần
   làm gì thêm nếu UI mới style bằng CSS class có sẵn.
2. **Biểu đồ Altair/Plotly** — CSS variable KHÔNG chạm tới được canvas biểu đồ. Dùng hằng số
   Python `ACCENT_RGB`/`ACCENT_DARK` (hoặc giá trị hue suy ra từ accent, dùng để xoay toàn bộ dải
   màu đơn sắc của biểu đồ nhiệt/lịch) truyền trực tiếp vào tham số màu của Plotly/Altair.
3. **Iframe ô ghi chú (Quill)** — chạy trong 1 `<iframe>` là 1 document HTML riêng biệt, CSS của
   trang chính (kể cả `:root` var) KHÔNG lan vào được. App tự tiêm 1 đoạn `<style>` riêng vào BÊN
   TRONG iframe đó (lặp lại theo interval để chống Streamlit dựng lại iframe làm mất style).

## 7 trục cá nhân hoá (tab Tuỳ biến → sub-page "Giao diện")

"Giao diện" là 1 sub-page riêng của tab Tuỳ biến (`TUYBIEN_SUBS`, query param `?tsub=`, xem
`architecture-navigation.md`) -- KHÔNG còn là 1 chương trong chuỗi cuộn dọc "Tổng quan" như trước.
Khác bố cục 2 cột của mockup gốc "Tuỳ Chỉnh Giao Diện.dc.html" -- xác nhận với người dùng đổi lại
theo ĐÚNG khuôn chuẩn mọi sub-tab khác trong app (Báo cáo/Sách/Gundam): billboard mở đầu (đóng
LUÔN vai trò "xem trước trực tiếp" -- chip hiển thị tên đang chọn của cả 7 trục, số to bên trái là
"7" ("trục cá nhân hoá", số THẬT chứ không bịa số liệu giờ/phiên giả như bản mockup gốc, vì app
thuần hồi cứu) + chip TOC nhảy neo xuống từng chương, rồi tới hàng 2 nút "Đặt lại mặc định"/"Ngẫu
nhiên" (random hoá cả 7 setting cùng lúc), rồi 7 chương `sec_chapter()` bên dưới (mỗi chương 1 thẻ
`st.container(border=True)` dựng qua helper dùng chung `_tb_axis_grid()`). Billboard KHÔNG mô
phỏng token bằng state/JS riêng như bản `.dc.html` gốc, chỉ đọc thẳng `var(--token)`/`ACCENT`/
`BG_PALETTE`... hiện hành vì toàn trang đã tự re-render đúng lựa chọn mới sau mỗi `st.rerun()`.

Cạnh 2 trục accent/hoạ tiết nền đã có, có thêm 4 trục CSS-variable độc lập, kết hợp tự do với
nhau và với accent:

1. **Bảng màu nền** (`BG_PALETTES`, setting `bg_palette`) — bundle ĐỦ 7 token `(light, dark)`
   dùng để dựng `_TOK`: `bg`/`card`/`card-tl`/`border`/`divider`/`divider-2`/`chip`. Bundle đủ 7
   token cùng lúc (không cho đổi rời) để tránh nền mới "đọ màu" với viền/chip cũ. `text`/`text-2`/
   `text-3`/`text-4` CHỦ Ý không nằm trong bundle này — giữ cố định, tách biệt như accent.
2. **Kiểu thẻ** (`CARD_STYLES`, setting `card_style`) — 3 token CSS `--card-radius`/
   `--card-border-w`/`--card-shadow`, áp dụng chung lên MỌI bảng màu nền. Bất kỳ CSS mới nào vẽ 1
   "thẻ nội dung" (nền `var(--card)` + viền `var(--border)` + bo góc + đổ bóng nhẹ) PHẢI dùng 3
   token này thay vì hard-code `border-radius:10px`/`border:1px solid var(--border)`/
   `box-shadow:0 1px 1px rgba(0,0,0,0.02)` — nếu không, thẻ đó sẽ "quên" đổi khi người dùng chọn
   kiểu thẻ khác. KHÔNG áp cho radius/border có ngôn ngữ hình khác cố ý (badge `999px`/`6-9px`,
   avatar tròn `50%`, input/button `7px`).
3. **Độ rộng nội dung** (`CONTENT_WIDTHS`, setting `content_width`) — 4 mức 1100/1300/1500/1700px
   (mặc định "Rộng" = 1500px), áp trực tiếp vào 2 token `--content-max-w`/`--content-half-w`. 2 token
   này quyết định CẢ `max-width` của `.block-container` LẪN vị trí 2 nút nổi "về đầu trang"/"Đồng bộ
   nhanh" (`right: max(22px, calc(50vw - var(--content-half-w) + 22px))`) — đổi mức mới hoặc thêm 1
   phần tử định vị theo mép cột nội dung PHẢI đọc lại 2 token này, không hardcode `600px`/`850px`.
4. **Mật độ bố cục** (`CARD_DENSITY`, setting `card_density`) — 2 token `--card-pad`/`--card-gap`,
   CHỈ áp cho nhóm "thẻ nội dung chung" dùng padding/margin đồng nhất (`16px 18px`/`margin 10px
   0`, ví dụ `.sec-card`). KHÔNG áp cho thẻ có padding tinh chỉnh riêng theo nội dung đặc thù
   (`.quotes-card`, `.help-tl-item`, `.dtl-card`, `.dtl-track`...) — những nơi đó giữ nguyên giá
   trị padding literal.

Cả 4 trục dùng lại đúng pattern fallback an toàn của `ACCENT`/`BG_STYLE` (giá trị lạ/preset cũ đã
bỏ → rơi về mặc định đầu tiên, không crash) và đúng pattern UI nút-preview + `save_setting()` +
`st.rerun()` đã có ở accent/hoạ tiết nền — không phát sinh cơ chế UI mới. Mọi `st.container(key=...,
border=True)` mới thêm vào sub-page này (kể cả trục mới) PHẢI được liệt kê vào rule CSS nền/viền
gộp chung của tab Tuỳ biến (xem bẫy `st.container(border=True)` đọc `config.toml` tĩnh bên dưới) —
quên bước này khiến thẻ trong suốt khác hẳn 6 thẻ còn lại (bug thật đã gặp với thẻ "Độ rộng nội
dung" lúc mới thêm).

**Bẫy chung: chrome/widget NATIVE của Streamlit đọc `.streamlit/config.toml` TĨNH, không đọc được
`--token` runtime.** `config.toml` chỉ load 1 lần lúc server khởi động, không có cách nào đọc lại
theo `settings` trong Supabase — mọi nơi Streamlit/BaseWeb tự vẽ theo `backgroundColor`/
`secondaryBackgroundColor`/`primaryColor`/`textColor` của file đó sẽ "đứng yên" ở đúng tông "Giấy
ấm"/accent mặc định gốc (dù không còn khớp `ACCENT_PRESETS`/`BG_PALETTES` hiện tại) trừ khi có 1
rule CSS `!important` ép lại bằng `var(--token)` tương ứng. Đã phát hiện + vá ở các nơi sau (agent
sau thêm 1 `st.dialog`/`st.container(border=True)`/widget native mới PHẢI tự kiểm tra lại theo đúng
cách này, không chỉ tin `background` chung là đủ):

- `[data-testid="stHeader"]` (thanh trên cùng "Deploy"/⋮) — ép `background: var(--bg)`.
- `st.container(border=True, key=...)` — viền/bo góc/bóng mặc định đọc theo `config.toml`, KHÔNG tự
  đổi theo `--card-radius`/`--card-border-w`/`--card-shadow`/`--border` dù nền `background` có thể
  ép qua `var(--card)` bình thường. Mọi key container border=True trong app (`.st-key-tb_backup_card`
  và tương tự, xem rule gần `stVerticalBlock`/`st-key-` trong khối CSS chính) phải được liệt kê
  tường minh trong 1 rule ép cả `background`/`border-color`/`border-width`/`border-radius`/
  `box-shadow` qua đúng 4 token trên.
- `[data-testid="stFileUploaderDropzone"]` (dropzone tải file CSV/zip) — ép `background-color:
  var(--chip)`.
- `[data-testid="stDialog"] > div` (khối bề mặt modal thật, `<section role="dialog">` bên trong nó
  tự trong suốt) — ép `background: var(--card)`.
- `[data-testid="stCheckbox"] label[data-selected="true"] > div:nth-child(2)` (ô vuông khi đã tick)
  — mặc định tô `primaryColor` tĩnh, ép lại `var(--accent)`. Y hệt lỗi `st.tabs()`/segmented
  control đã vá trước đó (`[data-testid="stTab"][aria-selected="true"]`,
  `.react-aria-SelectionIndicator`) — cùng 1 nguyên nhân gốc.
- `[data-testid="stButtonGroup"] button:not([data-selected="true"])` (nút CHƯA chọn trong MỌI
  `st.segmented_control`, không riêng nav chính) — mặc định rơi về nền theme trung tính TĨNH, ép
  `background-color: var(--card)`. Bản đầu tiên của rule này CHỈ scope `.st-key-nav` ("chưa có yêu
  cầu đổi" ở nơi khác) — đã tổng quát hoá lên MỌI `stButtonGroup` sau khi phát hiện lệch tông ở bộ
  lọc "Phân loại" (Nhóm/Dự án). 2 nơi tab kiểu gạch chân dưới (`.st-key-bc_sub_picker`/
  `.st-key-hm_sub_picker`, "Chọn kỳ xem"/"Xem theo") CHỦ Ý giữ nền trong suốt — rule riêng của 2 nơi
  đó phải khớp/thắng đúng độ đặc hiệu của rule tổng quát này (2 attribute + 1 tag = `(0,2,1)`) nếu
  sau này đổi lại, không thì nền `var(--card)` sẽ đè nhầm lên kiểu tab gạch chân.
- `[data-testid="stExpander"] summary:hover` VÀ `details[open] > summary` — Streamlit tự tô 2 màu
  nền highlight TĨNH RIÊNG BIỆT (khác nhau, khác cả `secondaryBackgroundColor`) cho trạng thái hover
  và trạng thái đang mở — 2 rule độc lập, sửa 1 KHÔNG tự sửa luôn cái kia (đã từng vá xong hover
  rồi tưởng xong, ảnh chụp thật cho thấy mở expander ra dù không hover vẫn còn dải nền cũ). Phải ép
  `background-color: transparent` (hoặc `var(--token)` khác nếu muốn có màu) trên CẢ 2 selector.
- `div[data-testid="stDownloadButton"] button[kind="secondary"]` (`st.download_button`, "Tải bản
  sao lưu") — DOM khác `st.button` (`stDownloadButton` không phải `stButton`), rule nền/viền
  secondary chung chỉ khớp `div[data-testid="stButton"]` nên lọt lưới — phải thêm selector riêng
  vào CÙNG rule.
- `[data-testid="stFileUploaderDropzone"] button[kind="secondary"]` (nút "Upload" bên trong
  dropzone) — nút này KHÔNG nằm trong `div[data-testid="stButton"]` như mọi nút secondary khác
  trong app (đứng trực tiếp trong dropzone), nên cũng lọt lưới rule chung — cần rule riêng.
- `st.pagination` (nút phân trang mọi bảng `.dtbl`, xem `_render_table_pagination()` ở
  `ui-components.md`) — 4 phần tử `[data-testid="stPaginationPrev"]`/`"stPaginationNext"`/
  `"stPaginationPage"`/`"stPaginationPageActive"` tô `color`/`border-color` TĨNH theo `textColor`
  của `config.toml` — đọc được trên nền "Giấy ấm" gốc nhưng gần như biến mất trên Bảng màu nền đậm
  (vd "Rượu vang") ở light theme vì màu chữ/viền tối gần bằng màu nền đậm (phát hiện qua ảnh chụp
  người dùng gửi). Ép lại `color`/`border-color` qua `var(--text-2)`/`var(--border)` (3 nút thường)
  và `var(--text)`/`var(--chip)`/`var(--text-3)` (nút trang đang chọn) — icon mũi tên `‹`/`›` không
  cần rule riêng, tự ăn theo `color` của nút cha như icon Material khác.

**Giới hạn KHÔNG vá được bằng CSS:** `st.dataframe` (bảng "5. Dữ liệu làm việc hiện tại" ở Tuỳ
biến, `db_view`) vẽ bằng canvas (glide-data-grid) nội bộ của Streamlit, không phải DOM/CSS thường
— màu ô/hàng đọc thẳng từ theme resolution của Streamlit lúc vẽ pixel, `!important` CSS KHÔNG chạm
tới được (đã xác nhận qua screenshot: nền hàng vẫn nguyên tông "Giấy ấm" cũ dù mọi thứ xung quanh
đã đổi đúng). Muốn bảng này theo đúng Bảng màu nền thì phải thay `st.dataframe` bằng bảng HTML tự
vẽ kiểu `.dtbl` (đã dùng ở mọi bảng số liệu khác trong app, tự theo `var(--token)` đầy đủ) — đổi
kiến trúc thật sự (mất tính năng chọn hàng native qua checkbox, phải tự làm lại bằng cách khác),
không phải 1 rule CSS thêm vào như các mục trên. Chưa làm — cần hỏi người dùng trước vì đổi hẳn
cách hiện thực, không phải fix nhỏ.

## Font thân chữ: 1 trục chọn, chỉ áp vai trò "thân/nhãn/nút", KHÔNG áp bảng số liệu/trích dẫn

`BODY_FONT`/`BODY_FONT_NAME` (chọn từ `BODY_FONTS`, setting `body_font`, mặc định "Manrope") lan ra
đúng 2 nơi, không hơn — font bảng số liệu (`_TABLE_FONT_FACE`, IBM Plex Mono) và font trích dẫn
(`_QUOTE_FONT_FACE`, Cormorant Garamond) CHỦ Ý đứng ngoài trục này, giữ cố định vì có vai trò nội
dung riêng:

1. **`html, body, .stApp` trong khối CSS chính** — literal `'Manrope'` bị `.replace()` thay đúng
   font đang chọn ngay trước khi `st.markdown()` inject (khối CSS chính là string thường, xem mục
   trên — không đổi sang f-string, chỉ `.replace()` đúng chỗ cần).
2. **Iframe Quill (`style_quill()`)** — cùng `.replace('Manrope', ...)` trên `QUILL_CSS` trước khi
   tiêm vào iframe, giống hệt cách `ACCENT`/màu dark-mode literal đã làm ở đó.

`_body_font_b64(file_prefix)` CHỈ tải/nhúng base64 đúng 1 font đang chọn (không nhúng sẵn cả 3) để
không đội payload trang — thêm 1 font mới vào `BODY_FONTS` cần: tải 3 file `.woff2` subset
(latin/latin-ext/vietnamese, cùng bộ `unicode-range` trong `_BODY_FONT_RANGES` — đã xác minh Google
Fonts dùng chung range này cho mọi font sans phổ biến) vào `assets/fonts/` theo đúng quy ước tên
`<file_prefix>-<subset>.woff2`.

## Bẫy: `st.metric` bị ẩn toàn cục bằng CSS

Có 1 rule CSS `[data-testid="stMetric"] { display: none; }` trong khối CSS chính — **mọi lời gọi
`st.metric()` ở bất kỳ đâu trong app đều render ra khoảng trắng vô hình**, không có lỗi, không có
warning, rất khó phát hiện khi review nhanh (đã từng gây bug thật lúc thêm UI mới). Không dùng
`st.metric()`. Thay thế:

- Dùng `render_stat_panel()` nếu là dạng "số liệu hero + chip nhãn" (xem `ui-components.md`).
- Dùng `st.markdown(f"**Nhãn**  \n{giá trị}")` (2 dòng cách nhau bằng 2 khoảng trắng cuối dòng đầu
  + xuống dòng) cho trường hợp đơn giản, không cần style phức tạp.
