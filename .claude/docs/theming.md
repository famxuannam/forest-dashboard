# Theming: CSS custom properties, không phải 2 bộ stylesheet

Đối tượng đọc: AI agent cần thêm UI mới, sửa màu sắc, hoặc đụng vào khối CSS lớn trong `app.py`.

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

## 3 trục cá nhân hoá nền/thẻ (tab Tuỳ biến → "4. Giao diện"), tách biệt với accent

Cạnh 2 trục accent/hoạ tiết nền đã có, có thêm 3 trục CSS-variable độc lập, kết hợp tự do với
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
3. **Mật độ bố cục** (`CARD_DENSITY`, setting `card_density`) — 2 token `--card-pad`/`--card-gap`,
   CHỈ áp cho nhóm "thẻ nội dung chung" dùng padding/margin đồng nhất (`16px 18px`/`margin 10px
   0`, ví dụ `.sec-card`). KHÔNG áp cho thẻ có padding tinh chỉnh riêng theo nội dung đặc thù
   (`.quotes-card`, `.help-tl-item`, `.dtl-card`, `.dtl-track`...) — những nơi đó giữ nguyên giá
   trị padding literal.

Cả 3 trục dùng lại đúng pattern fallback an toàn của `ACCENT`/`BG_STYLE` (giá trị lạ/preset cũ đã
bỏ → rơi về mặc định đầu tiên, không crash) và đúng pattern UI nút-preview + `save_setting()` +
`st.rerun()` đã có ở accent/hoạ tiết nền — không phát sinh cơ chế UI mới.

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
