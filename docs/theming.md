# Theming: CSS custom properties, không phải 2 bộ stylesheet

Đối tượng đọc: Claude Code cần thêm UI mới, sửa màu sắc, hoặc đụng vào khối CSS lớn trong `app.py`.

## Theme Gundam: 1 lựa chọn quyết định tất cả

Giao diện chỉ còn **1 setting** `theme` (bảng `settings`), chọn ở Tuỳ biến → sub-page "Giao diện"
(`_render_tuybien_giao_dien()`). Danh sách theme là `GUNDAM_THEMES` trong `ui_catalog.py`, đặt
tên theo tông màu Gundam (RX-78-2, Zaku II của Char, Nu, Unicorn, Strike Freedom, Kyrios, Barbatos,
Aerial, Banshee Norn, Sinanju, Exia, Dynames). Key đầu tiên (`DEFAULT_THEME` = "RX-78-2") là mặc
định; giá trị lạ/key cũ đã bỏ rơi về mặc định, không crash. 6 trục cũ (accent, bảng màu nền, hoạ tiết
nền, kiểu thẻ, font, độ rộng nội dung) đã BỎ hẳn theo yêu cầu người dùng; các key setting cũ còn sót
trong bảng `settings` bị bỏ qua. Độ rộng nội dung cố định 1500px.

Mỗi theme khai báo: `mode` (`light`/`dark`), các màu `bg/card/chip/border/text..text-4/accent/
on-accent/trim/trim2`, `chart` (8 màu biểu đồ), `font` (key của `BODY_FONTS`), `pattern` (key của
`THEME_PATTERNS`), `cut`/`radius` (góc thẻ), `name`/`era`/`note` (hiển thị). Thêm theme mới: thêm 1
entry đủ các khoá trên, kiểm tra tương phản (`text-3` trên `card` và `on-accent` trên `accent` ≥ 4.5:1),
và tránh trùng tông với theme có sẵn (đã bỏ Wing Zero/Sazabi/Destiny vì quá giống theme khác).

## `IS_DARK` + `--token` CSS variables

`IS_DARK = THEME["mode"] == "dark"`: tông sáng/tối **thuộc về theme**, không còn đọc
`st.context.theme.type`/chế độ của trình duyệt. Token CSS dựng bằng `theme_tokens(THEME)` (1 giá
trị/token, không còn cặp light/dark) rồi bơm vào `:root{...}`: `--bg`, `--card`, `--card-tl`,
`--border`, `--divider`, `--divider-2`, `--divider-on-bg`, `--chip`, `--text`, `--text-2/3/4`,
`--text-on-bg(-2)` (trùng `--text(-2)` vì thẻ và nền cùng tông), `--on-accent` (chữ trên nền
accent — dùng thay cho `#fff` cứng, vì accent sáng như Banshee/Exia/Dynames cần chữ tối), `--trim`,
`--trim2`, cùng `--accent`, `--accent-rgb`, `--accent-dark`. **Mọi UI mới nên dùng `var(--token)`
thay vì mã màu cứng.**

`.streamlit/config.toml` chỉ còn 1 bộ `[theme]` sáng (tông RX-78-2), không có `[theme.dark]`.

## Khối CSS chính là string thường — KHÔNG chuyển thành f-string

Khối CSS lớn nhất trong `app.py` được viết là 1 string Python bình thường, không phải f-string, dù
phần lớn code khác trong file dùng f-string thoải mái. Lý do: hàng trăm dấu `{`/`}` literal trong
cú pháp CSS (`{ }` bao mỗi rule) sẽ đều bị Python hiểu nhầm là placeholder nếu đổi sang f-string,
phải escape thành `{{`/`}}` ở mọi chỗ — không đáng đổi. Nếu cần chèn 1 giá trị Python động vào CSS,
dùng `.format()`/nối chuỗi cho đúng đúng đoạn cần, không đổi kiểu cả khối.

## Màu accent: 1 giá trị, lan ra 3 cơ chế khác nhau

`ACCENT` (= `THEME["accent"]`) không chỉ đổi màu qua CSS — nó lan ra 3 nơi bằng 3 cơ chế khác nhau,
phải nhớ cả 3 khi thêm 1 UI element có màu accent:

1. **CSS** — qua `var(--accent)`, `var(--accent-rgb)`, `var(--accent-dark)`; chữ đặt trên nền accent
   dùng `var(--on-accent)`.
2. **Biểu đồ Altair/Plotly/ECharts** — CSS variable KHÔNG chạm tới được canvas biểu đồ. Dùng hằng số
   Python `ACCENT`/`ACCENT_DARK`/`PLOT_TEXT` (hoặc hue suy ra từ accent cho dải nhiệt/lịch,
   `_teal_shades()`; accent gần như không màu như Nu Gundam thì dải này lấy hue của `trim`). Màu
   Nhóm/Dự án lấy từ `THEME["chart"]` qua `build_color_map()` (Dự án duy nhất của 1 Nhóm dùng đúng màu
   Nhóm). Mọi `st.plotly_chart` đi qua `_theme_fig(fig)` để ép màu chữ trục/legend theo `PLOT_TEXT`
   (theme "streamlit" của Plotly chỉ biết `textColor` tĩnh trong `config.toml`); 2 lịch Altair dùng
   `.configure_axis(labelColor=PLOT_TEXT, ...)`. Chữ đặt trên thanh màu biểu đồ dùng
   `_readable_text(color)`, không cố định `#fff` (dải `chart` có màu rất sáng).
3. **Iframe ô ghi chú (Quill)** — chạy trong 1 `<iframe>` là 1 document HTML riêng biệt, CSS của
   trang chính (kể cả `:root` var) KHÔNG lan vào được. App tự tiêm 1 đoạn `<style>` riêng vào BÊN
   TRONG iframe đó (lặp lại theo interval để chống Streamlit dựng lại iframe làm mất style).

## Kiểu thẻ và hoạ tiết nền theo theme

- `theme_card_vars(THEME)` -> `--card-radius`, `--card-corner-shape`, `--card-border-w` (luôn `0px`:
  thẻ không viền, tách lớp bằng nền + bóng nhẹ ở theme sáng / 1 đường viền trong mờ ở theme tối),
  `--card-shadow`. Theme có `cut > 0` dùng góc VÁT kiểu giáp: `border-radius: <cut>px 3px` +
  `corner-shape: bevel` (CSS mới, Chromium hỗ trợ; trình duyệt chưa hỗ trợ tự rơi về góc bo tròn).
  **Không dùng `clip-path`** để vát góc: nó cắt mất tooltip `data-tip`/lịch nằm trong thẻ. Mọi rule
  `border-radius: var(--card-radius)` phải đi kèm `corner-shape: var(--card-corner-shape)`.
  `--card-bg-override`/`--card-backdrop`/`--card-border-image` là di sản bộ kiểu thẻ cũ, giờ cố định
  `var(--card)`/`none`/`none`.
- `THEME_PATTERNS[THEME["pattern"]]` -> `--bg-image`/`--bg-size` (panel line, lưới kỹ thuật, chấm,
  lưới tam giác, hoa văn thoi), vẽ bằng `var(--divider-on-bg)`, chỉ áp cho nền trang `.stApp`.
- Billboard (`--billboard-bg`) là 1 thẻ nền ĐẶC phớt accent (`color-mix(... var(--accent) 7%,
  var(--card))`), không còn lớp kính mờ.
- `_THEME_UNIT_TAG_HTML` (`.theme-unit`): nhãn "mã máy" (dải 3 màu accent/trim/trim2 + "RX-78-2 ·
  UC 0079"), dùng ở billboard Hôm nay và nút theme cuối sidebar (link tới Tuỳ biến → Giao diện).

Mọi `st.container(key=..., border=True)` mới PHẢI được liệt kê vào rule CSS nền/viền gộp chung (xem
bẫy `st.container(border=True)` đọc `config.toml` tĩnh bên dưới).

**Bẫy chung: chrome/widget NATIVE của Streamlit đọc `.streamlit/config.toml` TĨNH, không đọc được
`--token` runtime.** `config.toml` chỉ load 1 lần lúc server khởi động, không có cách nào đọc lại
theo `settings` trong Supabase — mọi nơi Streamlit/BaseWeb tự vẽ theo `backgroundColor`/
`secondaryBackgroundColor`/`primaryColor`/`textColor` của file đó sẽ "đứng yên" ở đúng tông
sáng RX-78-2 của file đó (dù đang dùng theme khác, kể cả theme tối) trừ khi có 1
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
  lọc "Phân loại" (Nhóm/Dự án). Nơi tab kiểu gạch chân dưới (`.st-key-bc_sub_picker`,
  "Chọn kỳ xem") CHỦ Ý giữ nền trong suốt — rule riêng của nơi
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
  của `config.toml` — đọc được trên bảng nền nhạt mặc định ("Bạc hà") nhưng gần như biến mất trên
  Bảng màu nền đậm cố định (vd "Lam thẳm") ở light theme vì màu chữ/viền tối gần bằng màu nền đậm (phát hiện qua ảnh chụp
  người dùng gửi). Ép lại `color`/`border-color` qua `var(--text-2)`/`var(--border)` (3 nút thường)
  và `var(--text)`/`var(--chip)`/`var(--text-3)` (nút trang đang chọn) — icon mũi tên `‹`/`›` không
  cần rule riêng, tự ăn theo `color` của nút cha như icon Material khác.

- **Khối "MÀU CHỮ/NỀN WIDGET NATIVE THEO THEME" (cuối `_MAIN_CSS`)** — vì `config.toml` chỉ có
  bộ sáng, theme tối sẽ ra chữ tối trên nền tối ở mọi chữ/ô nhập Streamlit tự tô. Khối này ép
  `color: var(--text)` cho `stMarkdownContainer`/`stWidgetLabel`/`stHeading`/... (KHÔNG
  `!important`, để class riêng của app trên phần tử con vẫn thắng), chữ nút secondary/segmented,
  nền + chữ ô nhập (`stSelectbox`/`stTextInput`/`stDateInputField`/`stNumberInput` — Streamlit
  1.67 không còn `data-baseweb="select"` quanh ô chọn, chọn theo `data-testid`), danh sách thả xuống
  `[role="listbox"]`. Nhãn trong nút (`button [data-testid="stMarkdownContainer"]`) phải `color:
  inherit`, nếu không chữ nút đang chọn mất màu `--on-accent` (bug thật: Nu Gundam chữ đen trên nền
  đen). Widget native mới: kiểm tra bằng ảnh chụp ở 1 theme tối (vd Exia) lẫn 1 theme sáng.

**Giới hạn KHÔNG vá được bằng CSS:** `st.dataframe` (bảng "5. Dữ liệu làm việc hiện tại" ở Tuỳ
biến, `db_view`) vẽ bằng canvas (glide-data-grid) nội bộ của Streamlit, không phải DOM/CSS thường
— màu ô/hàng đọc thẳng từ theme resolution của Streamlit lúc vẽ pixel, `!important` CSS KHÔNG chạm
tới được (đã xác nhận qua screenshot: nền hàng vẫn nguyên tông bảng nền mặc định lúc trang tải dù
mọi thứ xung quanh đã đổi đúng). Muốn bảng này theo đúng Bảng màu nền thì phải thay `st.dataframe` bằng bảng HTML tự
vẽ kiểu `.dtbl` (đã dùng ở mọi bảng số liệu khác trong app, tự theo `var(--token)` đầy đủ) — đổi
kiến trúc thật sự (mất tính năng chọn hàng native qua checkbox, phải tự làm lại bằng cách khác),
không phải 1 rule CSS thêm vào như các mục trên. Chưa làm — cần hỏi người dùng trước vì đổi hẳn
cách hiện thực, không phải fix nhỏ.

## Font thân chữ: theo theme, chỉ áp vai trò "thân/nhãn/nút", KHÔNG áp bảng số liệu/trích dẫn

`BODY_FONT`/`BODY_FONT_NAME` (= `THEME["font"]`, 1 key của `BODY_FONTS`; không còn setting riêng) lan ra
đúng 2 nơi, không hơn — font bảng số liệu (`_TABLE_FONT_FACE`, IBM Plex Mono) và font trích dẫn
(`_QUOTE_FONT_FACE`, Cormorant Garamond) CHỦ Ý đứng ngoài trục này, giữ cố định vì có vai trò nội
dung riêng:

1. **`html, body, .stApp` trong khối CSS chính** — literal `'Manrope'` (placeholder cố định trong
   template CSS, KHÔNG phải font đang chọn -- "Manrope" đã tách khỏi `BODY_FONTS` thành font khung
   vỏ cố định riêng, xem `_UI_FONT`/architecture-navigation.md) bị `.replace()` thay đúng font đang
   chọn ngay trước khi `st.markdown()` inject (khối CSS chính là string thường, xem mục trên —
   không đổi sang f-string, chỉ `.replace()` đúng chỗ cần).
2. **Iframe Quill (`style_quill()`)** — cùng `.replace('Manrope', ...)` trên `QUILL_CSS` trước khi
   tiêm vào iframe, giống hệt cách `ACCENT`/màu dark-mode literal đã làm ở đó.

Font phục vụ dạng file tĩnh: `_font_src(fname)` trả `url('app/static/fonts/<fname>')` (cần
`server.enableStaticServing = true` trong `.streamlit/config.toml`; URL TƯƠNG ĐỐI vì Streamlit Cloud
chạy app dưới đường dẫn con), trình duyệt cache theo ETag thay vì nhận lại base64 ở mỗi session mới.
Tắt static serving thì tự quay về nhúng base64. Chỉ font logo (`_LOGO_FONT_FACE`, nhỏ) vẫn nhúng
base64. `_body_font_b64(file_prefix)` (tên cũ) giờ chỉ trả tên file của đúng 1 font đang chọn — thêm 1 font mới vào `BODY_FONTS` cần: tải 3 file `.woff2` subset
(latin/latin-ext/vietnamese, cùng bộ `unicode-range` trong `_BODY_FONT_RANGES` — đã xác minh Google
Fonts dùng chung range này cho mọi font sans phổ biến) vào `static/fonts/` theo đúng quy ước tên
`<file_prefix>-<subset>.woff2`.

## Biểu đồ ECharts (`st.echarts_chart`, Streamlit >= 1.64)

Dùng cho biểu đồ cần hình dạng riêng (cây trong "Khu rừng tháng này", calendar heatmap năm). Giống
Plotly, CSS variable KHÔNG chạm vào canvas, nên:

- `theme=None`, tự đặt `backgroundColor: "transparent"`, `textStyle.color` và màu chữ trục/legend/
  visualMap = `PLOT_TEXT`; màu series từ `COLOR_MAP` / `_teal_shades()`; ô trống/nền nhạt dựng từ
  `PLOT_TEXT` qua `_hex_rgb_str()` (`rgba(...,0.07)`). Truyền `alt="..."` mô tả tiếng Việt.
- `spec` chỉ nhận JSON: **không** callback JS (`formatter` dạng hàm, `renderItem`), nên không có series
  `custom`, map/geo hay 3D. Tooltip dùng formatter chuỗi `"{b}"` và gắn sẵn chuỗi hiển thị vào `name` của
  từng data item. Không có sự kiện click/selection nên không điều hướng được từ biểu đồ.
- Scatter mặc định `opacity` 0.8 -- đặt `itemStyle.opacity: 1` nếu màu phải khớp đúng màu ở chỗ khác.
- Dựng spec trong hàm riêng trả dict (`_forest_spec`, `_year_heatmap_spec`) để kiểm tra bằng script
  thuần mà không cần Streamlit. Danh sách biểu đồ: xem "Biểu đồ mới ở Báo cáo" ở `ui-components.md`.

## Bẫy: `st.metric` bị ẩn toàn cục bằng CSS

Có 1 rule CSS `[data-testid="stMetric"] { display: none; }` trong khối CSS chính — **mọi lời gọi
`st.metric()` ở bất kỳ đâu trong app đều render ra khoảng trắng vô hình**, không có lỗi, không có
warning, rất khó phát hiện khi review nhanh (đã từng gây bug thật lúc thêm UI mới). Không dùng
`st.metric()`. Thay thế:

- Dùng `render_stat_panel()` nếu là dạng "số liệu hero + chip nhãn" (xem `ui-components.md`).
- Dùng `st.markdown(f"**Nhãn**  \n{giá trị}")` (2 dòng cách nhau bằng 2 khoảng trắng cuối dòng đầu
  + xuống dòng) cho trường hợp đơn giản, không cần style phức tạp.
