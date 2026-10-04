# Kế hoạch làm mới Forest Dashboard (10/2026)

Đối tượng đọc: phiên Claude Code (Sonnet 5.5) được giao thực hiện. Kế hoạch này do một phiên
phân tích viết ngày 04/10/2026, dựa trên `main` tại commit `9bfc851` (#331). Người dùng đã chốt
phạm vi; phần "Quyết định đã chốt" bên dưới không cần hỏi lại.

## Bối cảnh

Người dùng bỏ app khoảng 5 tuần (commit cuối 29/08/2026) và muốn quay lại. Các thay đổi gần nhất
chủ yếu là thêm lựa chọn giao diện (20 màu accent, 20 nền, 20 font…). Mục tiêu đợt này **không
phải** thêm tuỳ chọn giao diện, mà là:

1. Trải nghiệm quay lại sau thời gian nghỉ dễ chịu, không gây cảm giác bị trách.
2. Giảm ma sát nhập dữ liệu (lý do bỏ app là lười).
3. Cho người dùng thấy điều mới về chính dữ liệu của họ.

Triết lý app giữ nguyên: **chỉ hồi cứu, không đặt mục tiêu, không nhắc nhở.** Huy hiệu và nhận xét
là ghi nhận những gì đã xảy ra, không phải chỉ tiêu.

## Quyết định đã chốt với người dùng

- Làm cả 4 giai đoạn bên dưới, theo đúng thứ tự.
- Tự đồng bộ khi mở app (giữ nút tròn đồng bộ tay).
- Biểu đồ "Rừng của bạn" đặt ở **Báo cáo › Tháng**, trong chương 1 "Tổng quan".
- Ngưỡng "nghỉ dài" mặc định là **14 ngày** (một hằng số, dễ chỉnh).

## Ngoài phạm vi (không làm)

- Thư tuần viết bằng AI/Claude API (cần dependency mới, API key, và gửi ghi chú cá nhân ra ngoài;
  người dùng chưa quyết).
- Dùng `st.metric` (kể cả bản có sparkline): CSS toàn cục đang ẩn nó, xem `docs/theming.md`.
- Thay cơ chế đồng bộ `?nav=`/`?sub=` bằng tham số `bind="query-params"` mới. Code hiện tại đúng,
  việc này chỉ là dọn dẹp và có rủi ro phá deep-link.
- Thêm bảng Supabase mới. Mọi tính năng dưới đây tính từ dữ liệu sẵn có. Nếu thấy buộc phải thêm
  bảng, dừng lại và hỏi người dùng.

---

## Quy tắc chung (đọc trước khi code)

Đọc `CLAUDE.md` và các file trong `docs/` liên quan tới từng giai đoạn. Những điểm hay bị vi phạm:

- Mọi logic "hôm nay" dùng `_today_vn()`, không dùng `date.today()`.
- Khối CSS lớn (`_MAIN_CSS`, `RLCAL_CSS`…) là string thường, **không** đổi thành f-string. CSS
  mới thêm vào đúng khối đó, dùng `var(--token)` thay vì mã màu cứng (`docs/theming.md`).
- Icon trong HTML dùng `_mi('material_icon_name')`, **không dùng emoji** (`docs/ui-components.md`).
  Icon cho widget Streamlit dùng cú pháp `:material/x:`.
- Card mới bọc trong `st.container(border=True, key="jcard_<tên>")` để ăn style card chung (xem bẫy
  `st.container(border=True)` trong `docs/theming.md`).
- Không tự gán state của widget sau khi widget đã khởi tạo. Chuyển trạng thái bằng callback
  `on_click` hoặc cờ `_..._jump` + `st.rerun()` (`docs/ui-components.md`, mục cuối).
- Thêm/xoá/đổi chỗ chương `sec_chapter()` thì phải đánh số lại cả chương phía sau lẫn chip mục
  lục của billboard. Các việc dưới đây đều được thiết kế để **không** phải đánh số lại. Nếu buộc
  phải làm, tuân thủ quy ước đó.
- Số dòng trong kế hoạch là tại commit `9bfc851` và sẽ lệch dần. Luôn tìm theo tên hàm.
- Không refactor ngoài phạm vi, không đổi style code xung quanh. Comment/docstring tiếng Việt,
  độ dày tương đương code xung quanh.
- Sau mỗi lần sửa `app.py`: `python3 -c "import ast; ast.parse(open('app.py').read())"`.

### Ràng buộc của `st.echarts_chart` (Streamlit ≥ 1.64), đã kiểm tra trên 1.65.0

- `spec` chỉ nhận JSON. **Không** dùng được callback JS (`formatter` dạng hàm, `renderItem`), nên
  **không** có series `custom`, map/geo hay 3D. Tooltip dùng formatter dạng chuỗi (vd `"{b}"`) và
  gắn sẵn chuỗi hiển thị vào `name` của từng data item.
- Không có sự kiện click/selection, nên không điều hướng được từ biểu đồ.
- Dùng `theme=None` và tự đặt `backgroundColor: "transparent"`, màu chữ `PLOT_TEXT`, màu series từ
  `COLOR_MAP`/`_teal_shades()`. CSS variable không chạm được vào canvas (giống Plotly).
- Truyền `alt="..."` mô tả ngắn bằng tiếng Việt.

### Kiểm tra (bắt buộc cho mỗi giai đoạn)

1. Kiểm tra cú pháp ở trên.
2. Chạy `FOREST_LOCAL_DEV=1 streamlit run app.py --server.address localhost --server.port 8599
   --server.headless true` bằng tham số chạy nền của tool Bash (xem `docs/testing.md`, mục 5 lỗi
   hay gặp). Cài `pip install -r requirements.txt playwright` nếu thiếu.
3. Lái bằng Playwright (`executable_path='/opt/pw-browsers/chromium'`). Quét mọi trang nav chính
   (Hôm nay, Báo cáo đủ 5 sub-tab, Sách, Gundam, Tìm kiếm, Tuỳ biến) không có
   `[data-testid="stException"]` hay "Traceback". Chụp ảnh phần vừa sửa ở desktop (1400px) và
   mobile (390px), và **ở cả theme sáng lẫn tối**. Viewport cao 2600–3200px để chụp hết trang dài.
4. Dữ liệu mẫu `local_dev_data.py` chỉ có vài ngày gần đây. Để thử khoảng nghỉ dài, nhiều tháng,
   v.v. thì tạo bản scratch (không commit) theo `docs/testing.md`, hoặc viết script Python thuần
   gọi thẳng hàm tính toán với DataFrame giả (mục "Bước 3" của `docs/testing.md`). **Mọi hàm tính
   toán mới có từ 3 nhánh trở lên phải có script kiểm tra kiểu này.**
5. Dọn file scratch, ảnh chụp, `__pycache__` trước khi commit.

### Git

- Mỗi giai đoạn là một commit/PR riêng, theo `docs/git-workflow.md` (squash-merge, làm sạch nhánh
  từ `origin/main` trước khi bắt đầu giai đoạn kế).
- Commit + push lên nhánh được giao. **Chỉ mở PR khi người dùng yêu cầu.**
- Cập nhật tài liệu `docs/` trong cùng commit với thay đổi code (mỗi giai đoạn ghi rõ file nào).

---

## Giai đoạn 1: Quay lại

Không cần API Streamlit mới. Không đổi `requirements.txt`.

### 1.1 Lời nhắc chuỗi bị đứt: đổi sang giọng nhẹ nhàng

**Hiện trạng.** `_streak_nudge()` (~`app.py:2628`) trả về câu "Chuỗi gần nhất đã dừng lại {gap}
ngày trước…" với tone `"neutral"`, mà tone này thực chất là nền và chữ **đỏ** (`NUDGE_TONES`,
~`app.py:2617`). Câu này hiện ở Báo cáo › Tổng quan (billboard) và Báo cáo › Dự án.

**Việc cần làm.**

- Thêm tone `"calm"` vào `NUDGE_TONES`: nền `f"rgba({ACCENT_RGB},0.07)"`, chữ `"var(--text-2)"`
  (inline style chấp nhận CSS var). Kiểm tra cả light lẫn dark.
- Nhánh `gap >= 2` (hiện là `return (..., "neutral")`):
  - `2 <= gap < COMEBACK_MIN_GAP`: "Lần gần nhất có phiên là {gap} ngày trước."
  - `gap >= COMEBACK_MIN_GAP`: "Bạn đã tạm nghỉ {gap} ngày. Mọi dữ liệu cũ vẫn ở đây."
  - Cả hai dùng tone `"calm"`.
- Thêm hằng `COMEBACK_MIN_GAP = 14` cạnh `RECORD_MIN_DAYS` (~`app.py:199`), kèm comment ngắn.
- Nếu sau khi sửa `"neutral"` không còn nơi nào dùng (grep `"neutral"`), xoá entry đó khỏi
  `NUDGE_TONES`.
- Giữ nguyên nhánh `gap == 0` và `gap == 1`.

**Đạt khi.** Không còn chỗ nào hiện nền/chữ đỏ cho chuỗi bị đứt. Câu chữ đúng 2 mức gap.

### 1.2 Thẻ "Chào mừng trở lại" trên trang Hôm nay

**Vị trí.** `render_day_report()` (~`app.py:9973`), ngay sau `_render_today_billboard(...)` và
trước `sec_chapter("today-ch1", ...)` ở **cả hai** nhánh (`day_df.empty` và có phiên). Thẻ không
phải một chương nên không đánh số và không thêm chip mục lục.

**Hàm mới** `_render_welcome_back(df, sel, day_df)`:

- Chỉ chạy khi `sel == _today_vn()`.
- `prev_days` = các ngày có phiên `< _today_vn()`. Không có thì return.
- `last_day = prev_days[-1]`, `gap = (_today_vn() - last_day).days`. Nếu
  `gap < COMEBACK_MIN_GAP` thì return.
- **Trường hợp A: hôm nay chưa có phiên** (`day_df.empty`). Vẽ card
  `st.container(border=True, key="jcard_welcome")` gồm:
  - Tiêu đề "Chào mừng trở lại" và dòng phụ "Lần gần nhất: {_day_link_html(last_day)} · {gap} ngày
    trước".
  - Khối "Tuần cuối trước khi nghỉ" (các phiên trong `[last_day - 6 ngày, last_day]`): tổng giờ
    (`_fmt_hours_short`), số phiên, tối đa 3 Dự án nhiều giờ nhất, mỗi tên dùng
    `_entity_link_html(name, _proj_link_kind(nhom, name))`.
  - "Đang đọc/xem dở": cuốn sách và series Gundam có hoạt động gần nhất trước khi nghỉ. Tái dùng
    đúng logic chọn của `_sidebar_recent_activity_html()` (~`app.py:9400`). Nên tách phần "tìm
    tên có hoạt động mới nhất" thành hàm nhỏ dùng chung thay vì copy. Link qua `_entity_link_html`
    kind `book`/`gundam`. Ẩn nếu không có.
  - "Ghi chú gần nhất": ngày có ghi chú chính gần nhất trước hôm nay (`load_notes()`), đoạn trích
    văn bản thuần khoảng 240 ký tự (`_note_plain_text`) kèm link ngày. Ẩn nếu không có.
  - Mọi icon dùng `_mi()`. Bố cục và style tái dùng class sẵn có (`.rl-book`, `.jchip`…). Chỉ thêm
    CSS mới nếu thật cần, đặt vào `_MAIN_CSS`.
- **Trường hợp B: hôm nay đã có phiên và khoảng cách tới ngày có phiên trước đó ≥ 14.** Không vẽ
  card. Thay vào đó truyền `footer=(text, bg, fg)` vào lời gọi `render_stat_panel(...)` của chương
  "Tổng quan ngày" (hiện đang không truyền footer). Nội dung: "Phiên đầu tiên sau {gap} ngày nghỉ.
  Chào mừng trở lại." Màu: `"rgba(var(--accent-rgb),0.10)"`, `"var(--accent-dark)"` (giống
  `_DIGEST_CELEBRATE` trong `_smart_digest`).
- **Toast.** Lần đầu trong session thấy trường hợp A hoặc B thì gọi
  `st.toast(..., icon=":material/waving_hand:")` (cờ `st.session_state["_welcome_toasted"]`).
  Chỉ một lần mỗi session.

**Đạt khi.** Với dữ liệu scratch có phiên cuối cách hôm nay 30 ngày: trang Hôm nay hiện card A.
Thêm một phiên hôm nay thì card biến mất và footer B hiện. Với `gap < 14`: không có gì thay đổi so
với hiện tại. Xem ngày khác hôm nay: không hiện.

### 1.3 Tự đồng bộ khi mở app

**Hiện trạng.** File Forest/Reminder được Shortcut iOS đẩy lên bucket Supabase Storage. App chỉ
hiện nút tròn (`_render_nav_sync_fab()`, ~`app.py:1439`) khi `_has_pending_forest_sync()` thấy file
mới. Người dùng phải bấm thì `_do_quick_sync()` mới nạp.

**Việc cần làm.** Hàm mới `_auto_sync_on_open()`, gọi **ngay trước** `df = prep_analysis_data()`
(~`app.py:9113`), sau cổng đăng nhập Google (~`app.py:7005`). Như vậy `df` của lượt chạy này đã có
dữ liệu mới, không cần rerun thêm.

- Chỉ chạy một lần mỗi session: cờ `st.session_state["_auto_sync_checked"]`, đặt `True` ngay đầu
  hàm, trước mọi việc khác.
- Gọi bản **không cache** `_list_sync_files()` (một lần mỗi session nên chấp nhận được) rồi
  `_latest_sync_file(files, "forest")`. Bỏ qua nếu:
  - không có file, hoặc
  - tên file trùng setting `last_synced_forest_file` (đã nạp), hoặc
  - tên file trùng setting mới `auto_sync_failed_file` (đã tự thử và lỗi, tránh mỗi session mới
    lại thử và toast lỗi lặp đi lặp lại). Lưu ý mọi link `target=_self` trong app đều mở session
    mới, nên điều kiện này quan trọng.
- Nếu cần nạp: `with st.spinner("Đang nạp dữ liệu mới từ Forest…"):` gọi `_do_quick_sync()`.
  - Thành công: `st.toast(msg, icon=":material/cloud_done:")`.
  - Lỗi (`has_err`): `save_setting("auto_sync_failed_file", <tên file>)` và toast cảnh báo
    `icon=":material/warning:"`.
- Sau khi sync gọi `_list_sync_files_cached.clear()` để nút tròn ẩn đúng ngay lượt này.
  `save_setting()` đã tự clear `_cached_settings`.
- Nút tròn bấm tay giữ nguyên hành vi. Bấm tay thành công thì `last_synced_forest_file` đổi, nên
  `auto_sync_failed_file` tự hết tác dụng; không cần xoá.
- Local dev (`FOREST_LOCAL_DEV`): `LocalDevSupabase` không có `.storage`, `_list_sync_files()` đã
  bắt exception và trả `[]`, nên hàm tự bỏ qua. Xác nhận lại bằng cách chạy.
- `sync_from_storage()` còn đồng bộ CalDAV ±90 ngày (có thể chậm vài giây). Chấp nhận được vì chỉ
  chạy khi có file Forest mới.

**Kiểm tra.** Dùng harness scratch có fake `.storage.from_(bucket).list()/.download()/.remove()`
theo `docs/testing.md`. Thử 3 kịch bản: có file mới hợp lệ (nạp, toast, nút tròn ẩn); file lỗi
cột (toast lỗi, mở session mới không thử lại); không có file (không làm gì, không spinner).

**Tài liệu.** Cập nhật mục Đồng bộ nhanh trong `docs/data-layer.md`: mô tả tự đồng bộ và setting
`auto_sync_failed_file`. Thêm `auto_sync_failed_file` vào bất kỳ chỗ nào liệt kê các key settings
(grep `last_synced_forest_file` để tìm).

---

## Giai đoạn 2: Khám phá

Bắt đầu dùng API mới, nên đổi `requirements.txt`: `streamlit>=1.65,<2`.

### 2.1 Tìm kiếm hiện kết quả khi đang gõ

`render_search()` (~`app.py:5054`): thêm `live="300ms"` vào
`st.text_input("Từ khoá", key="search_q", ...)`. Kiểm tra CSS ô nhập không vỡ, và gõ nhanh không
gây giật (mỗi lần commit là một rerun toàn trang; dữ liệu đều đã cache). Nếu thấy giật rõ thì tăng
lên `"500ms"`.

### 2.2 Ngăn kéo "Một ngày ngẫu nhiên"

**Mục đích.** Gặp lại một ngày cũ một cách tình cờ (ghi chú Day One, phiên, trích dẫn) mà không
rời trang đang xem.

**Điểm vào.** Một nút trong sidebar, đặt ngay **sau** khối `st.markdown(_bottom_html, ...)` trong
khối `with st.sidebar:` thứ hai (~`app.py:9436`, chỉ khi `not df.empty`):
`st.button("Một ngày ngẫu nhiên", icon=":material/casino:", key="sb_peek_btn",
use_container_width=True)`. Style cho hợp với các khối `.sb-widget` xung quanh (thêm CSS vào
`_MAIN_CSS` theo key `st-key-sb_peek_btn`).

**Chọn ngày** — hàm `_peek_pool(df)`:

- Gồm các ngày có ít nhất một trong: phiên Forest, ghi chú chính có ≥ 40 ký tự văn bản thuần,
  trích dẫn Kindle (`Ngày thêm`).
- Loại 7 ngày gần nhất (tính theo `_today_vn()`).
- Trọng số: ngày có ghi chú ×2.
- Chọn bằng `random.Random()` không seed. Không lặp lại đúng ngày đang hiện.

**Dialog.** `@st.dialog("Một ngày trong quá khứ", position="right", width="medium")`, định nghĩa ở
cấp module (dialog là fragment). Ngày đang xem lưu ở `st.session_state["peek_day"]`. Nội dung theo
thứ tự:

1. Ngày ("Thứ Ba, 12/03/2024"), khoảng cách tương đối ("2 năm 7 tháng trước"), và link
   `_day_link_html(d, "Mở trang ngày này")` (link `target=_self` sẽ đóng dialog vì mở session mới,
   đúng ý).
2. Chip kỷ lục/huy hiệu: `_record_chips_html(_compute_alltime_records(df)["day_badges"].get(d))`.
3. Số liệu phiên nếu có: tổng giờ, số phiên, tối đa 3 Dự án (link).
4. Chip đọc sách/Gundam: `_book_chips_html(...)` với reading_log lọc đúng ngày (xem cách
   `render_note_editor()` gọi hàm này để truyền đúng tham số).
5. Ghi chú nhanh: `_quick_note_chips_html(_quick_notes_on(load_quick_notes(), d))`.
6. Ghi chú chính: hiển thị HTML **giống hệt** cách `render_notes_journal()` hiển thị ghi chú (tìm
   class `.note-html`), không tự sanitize theo cách khác. Ngắn hơn 1200 ký tự văn bản thuần thì
   hiện đủ, dài hơn thì cắt và để link "Mở trang ngày này" lo phần còn lại.
7. Tối đa 3 trích dẫn Kindle `Loại == 'highlight'` có `Ngày thêm` đúng ngày đó (chỉ đọc, style
   như trích dẫn ở billboard, không cần nút ⭐).
8. Nút "Ngày khác" (`icon=":material/shuffle:"`): chọn ngày mới vào `peek_day`, rồi
   `st.rerun(scope="fragment")`.

Tách phần dựng HTML thành `_day_peek_html(d, df)` (thuần, dễ test) và phần widget trong dialog.

**Kiểm tra.**

- Dialog mở dạng ngăn kéo bên phải trên desktop, và không vỡ trên mobile 390px.
- Theme sáng/tối và bảng màu nền đậm (vd "Lam thẳm") đều đọc được. Rule CSS dialog sẵn có ở
  ~`app.py:7458` có thể cần mở rộng cho dạng drawer.
- Bấm "Ngày khác" nhiều lần không lỗi.
- Bấm link "Mở trang ngày này" mở đúng ngày.

**Tài liệu.** Thêm mục "Ngăn kéo xem nhanh ngày" vào `docs/ui-components.md`, cạnh mục
`@st.dialog`.

---

## Giai đoạn 3: Hình ảnh mới

Dùng `st.echarts_chart` (có sẵn trong Streamlit, không phải dependency mới). Đọc lại mục
"Ràng buộc của `st.echarts_chart`" ở trên.

### 3.1 "Rừng của bạn" ở Báo cáo › Tháng

**Vị trí.** Nhánh `bc_sub == "Tháng"`, chương 1 "Tổng quan", ngay sau
`render_month_highlights(...)` (~`app.py:10566`), trước `sec_chapter("bc-thang-ch2", ...)`. Không
đổi số chương.

**Hàm mới** `render_month_forest(df_m, y, m)`, bọc trong
`st.container(border=True, key="jcard_bcthang_forest")`. Có tiêu đề nhỏ "Khu rừng tháng này" dùng
class `.rl-book` (giống "Dòng thời gian trong ngày" ở `render_day_timeline`).

- Mỗi phiên là một cây. Trục x là ngày trong tháng (category `1..days_in_month`; tháng hiện tại vẫn
  vẽ đủ trục, ngày tương lai để trống). Trục y là thứ tự phiên trong ngày theo giờ bắt đầu (0, 1,
  2…). Ẩn trục y và lưới.
- Một series `scatter` cho mỗi **Nhóm** (để legend theo Nhóm), màu `COLOR_MAP[nhóm]`.
- `symbol`: một `"path://..."` hình cây lá kim đơn giản (tự vẽ path SVG, viewBox nhỏ, có thân).
  Toàn bộ series dùng chung path.
- `symbolSize` theo từng data item: căn bậc hai của số phút, kẹp trong khoảng 10–24 px (10 phút →
  10 px, ≥ 180 phút → 24 px).
- Data item:
  `{"value": [ngày_idx, thứ_tự], "name": "dd/mm · {Dự án} · {phút}′ · HH:MM", "symbolSize": s}`.
  Tooltip `{"trigger": "item", "formatter": "{b}"}`.
- `backgroundColor: "transparent"`, `textStyle.color = PLOT_TEXT`, legend ở dưới, nhãn trục x mỗi
  5 ngày (`axisLabel.interval`).
- Chiều cao: `clamp(180 + 22 * max_phiên_trong_ngày, 220, 440)`.
- `theme=None`, `alt="Khu rừng tháng: mỗi cây là một phiên tập trung"`.
- Caption nhỏ dưới biểu đồ (màu `var(--text-3)`): "Mỗi cây là một phiên; cây càng to, phiên càng
  dài."

**Kiểm tra.** Tháng nhiều phiên và tháng ít phiên, desktop và mobile (31 cột ở 390px: chấp nhận
cây chồng nhẹ, không tràn ngang), sáng/tối. Màu cây cùng Nhóm phải khớp màu Nhóm đó ở chương
"Phân bổ nhóm" ngay dưới.

### 3.2 Lịch nhiệt cả năm ở Báo cáo › Năm

**Vị trí.** Nhánh `bc_sub == "Năm"`, chương 2 (~`app.py:10651`). Đổi tiêu đề chương từ
"Lịch tháng" thành "Lịch", ở **cả** `sec_chapter("bc-nam-ch2", 2, ...)` lẫn chip mục lục
`("bc-nam-ch2", "2 · Lịch")` của billboard. Số chương giữ nguyên.

- Đầu chương thêm
  `st.segmented_control("Xem theo", ["Cả năm", "Từng tháng"], default="Cả năm",
  key="bc_nam_cal_view", label_visibility="collapsed")`, cùng pattern với `bc_tq_trend_view`.
- "Từng tháng" chạy đúng code hiện tại (`frag_report_calendar_month(...)` trong
  `jcard_bcnam_cal`).
- "Cả năm" gọi hàm mới `render_year_heatmap(df_y, year)` trong
  `st.container(border=True, key="jcard_bcnam_heat")`:
  - ECharts `calendar` với `range = str(year)`, `cellSize: ["auto", 14]`, `dayLabel.firstDay = 1`,
    `dayLabel.nameMap = ["CN","T2","T3","T4","T5","T6","T7"]`,
    `monthLabel.nameMap = ["Th1",…,"Th12"]`, `yearLabel.show = false`, màu chữ `PLOT_TEXT`, viền ô
    mảnh.
  - Series `heatmap` trên `coordinateSystem: "calendar"`. Data item:
    `{"value": ["YYYY-MM-DD", giờ], "name": "dd/mm · 2h15′ · 3 phiên"}`. Tooltip `"{b}"`.
  - `visualMap` dạng `piecewise` dùng **đúng 5 bậc có giờ** của `_reading_cal_lvl()` (<0.5h, <1h,
    <2h, <4h, ≥4h; tính theo giờ), màu `_teal_shades(6)[1:]`, để thang màu khớp mọi lịch khác
    trong app. Ngày 0 giờ không có data item (ô nền trống).
  - Năm hiện tại: ngày tương lai để trống tự nhiên.
- Mobile: 53 cột ở 390px sẽ rất nhỏ. Chụp ảnh kiểm tra. Nếu ô nhỏ hơn khoảng 5px thì đặt
  `orient: "vertical"` với chiều cao lớn hơn cho mọi khổ (không phát hiện được độ rộng màn hình
  từ Python). Ghi lại lựa chọn trong docstring.

**Lưu ý.** `CLAUDE.md` vẫn ghi "Lịch tháng (nếu có)" ở vị trí 2. Không cần sửa vì vị trí và ý
nghĩa vẫn đúng. Cập nhật `docs/ui-components.md` mục "Lịch tháng dạng lưới" để nói Năm có thêm góc
nhìn "Cả năm".

### 3.3 "Các giai đoạn" ở Báo cáo › Tổng quan

**Vị trí.** Nhánh `bc_sub == "Tổng quan"`, chương 2 "Xu hướng" (~`app.py:10416`). Thêm lựa chọn
thứ ba `"Theo giai đoạn"` vào `st.segmented_control(... key="bc_tq_trend_view")`. Không đổi số
chương.

**Hàm tính** `_compute_eras(df)` (`@st.cache_data`, nhận `df` làm tham số như
`_compute_alltime_records`). Trả list dict
`{start, end, kind: "era"|"break", label, nhom, hours, top_projects}`:

1. Khoảng nghỉ: giữa hai ngày có phiên liên tiếp cách nhau ≥ 21 ngày thì tạo `break` từ ngày sau
   ngày trước đến ngày trước ngày sau. Nếu ngày có phiên cuối cách `_today_vn()` ≥ 21 ngày, thêm
   một `break` kéo tới hôm nay.
2. Trong mỗi đoạn hoạt động giữa các khoảng nghỉ: chia theo tháng (cắt theo biên đoạn). Mỗi
   tháng lấy **Nhóm** nhiều giờ nhất (dùng Nhóm, không dùng Dự án, để giai đoạn ổn định hơn).
3. Gộp các tháng liền nhau cùng Nhóm dẫn đầu thành một `era`.
4. Làm mượt: một era chỉ dài 1 tháng mà Nhóm dẫn đầu chiếm < 40% giờ tháng đó thì nhập vào era
   liền trước (nếu có, và cùng đoạn hoạt động).
5. Nhãn: era là `f"Mùa {nhom}"`, break là `f"Khoảng nghỉ · {n} ngày"`. `top_projects` là tối đa 2
   Dự án nhiều giờ nhất trong era.

Viết script Python thuần kiểm tra ít nhất: không có khoảng nghỉ; một khoảng nghỉ giữa; khoảng nghỉ
kéo tới hôm nay; tháng nhiễu bị làm mượt; dữ liệu chỉ 1 tháng.

**Hiển thị** `render_eras(df)`:

- Biểu đồ dải ngang một hàng bằng Plotly (`px.timeline` hoặc `go.Bar` ngang với `base`), màu era
  theo `COLOR_MAP[nhom]`, break màu xám nhạt (từ `PLOT_TEXT` với độ mờ). Đi qua
  `format_plotly_fig` và `PLOTLY_CONFIG` như các biểu đồ Plotly khác. Nhãn chữ trong dải chỉ khi
  đủ rộng.
  - Dùng Plotly ở đây vì ECharts không có series `custom`. Có thể dùng ECharts `bar` xếp chồng nếu
    gọn hơn; tự quyết và ghi lý do trong docstring.
- Dưới biểu đồ: bảng HTML `.dtbl` (theo `DTBL_CSS`, xem `render_period_table` làm mẫu), mỗi giai
  đoạn một dòng, mới nhất lên đầu. Cột: Giai đoạn, Từ–Đến (`_period_link_html` theo tháng), Độ dài,
  Tổng giờ, Dự án chính (link).

---

## Giai đoạn 4: Ghi nhận & phát hiện

### 4.1 Huy hiệu ghi nhận sau

**Tính toán.** Hàm `_compute_milestones(df)` (`@st.cache_data`, chỉ dựa trên `df` đã chuẩn bị).
Trả list dict `{date, kind, icon, title, detail}`, sắp theo ngày. Các loại (hằng số đặt thành tuple
gần `RECORD_MIN_DAYS`):

| Loại | Ngưỡng | Ngày ghi nhận |
|---|---|---|
| Tổng giờ | 10, 50, 100, 250, 500, 1000, 2000, 5000 h | Ngày của phiên làm tổng cộng dồn vượt ngưỡng |
| Số cây | 100, 250, 500, 1000, 2500, 5000 | Ngày của cây thứ N |
| Giờ theo Dự án | 10, 50, 100, 250, 500 h | Như trên, riêng từng Dự án |
| Phiên dài | 90, 120, 180 phút | Phiên đầu tiên đạt ngưỡng |
| Chuỗi ngày | 7, 14, 30, 60, 100 | Ngày đầu tiên một chuỗi đạt N |
| Quay lại | mỗi khoảng nghỉ ≥ `COMEBACK_MIN_GAP` | Ngày đầu tiên có phiên sau khoảng nghỉ ("Quay lại sau 37 ngày") |

- Sắp phiên theo `Thời gian bắt đầu` trước khi cộng dồn. Ngày dùng cột `Ngày`.
- Không lấy nguồn sách/Kindle trong đợt này (giữ hàm chỉ phụ thuộc `df` để cache đơn giản).
- Viết script kiểm tra từng loại với DataFrame giả, gồm cả trường hợp nhiều ngưỡng vượt trong cùng
  một phiên (vd phiên đầu tiên dài 3h vượt cả 90 lẫn 120 lẫn 180 phút: ghi nhận cả 3).

**Gắn vào hệ thống chip "Kỷ lục" sẵn có**, để mọi nơi đang hiện chip kỷ lục (ghi chú ngày, Nhật
ký, Ngày này năm trước, ngăn kéo 2.2) tự hiện huy hiệu mà không phải sửa từng nơi:

- Trong `_compute_alltime_records()` (~`app.py:2779`): gọi `_compute_milestones(df)`, thêm vào
  `day_badges` mỗi mốc dạng `{"kind": "milestone", "title": ..., "icon": ...}`, và trả thêm key
  `"milestones"` (list đầy đủ).
- `_record_chips_html()` (~`app.py:2966`): thêm nhánh `kind == "milestone"`, render
  `<span class='jchip rec'>{_mi(icon)} {title}</span>`. Đổi nhãn hàng chip từ "Kỷ lục" thành
  "Kỷ lục & huy hiệu" **chỉ khi** danh sách có ít nhất một milestone.
- Grep mọi nơi đọc `day_badges` hoặc duyệt badge (`b["kind"]`) để chắc không nơi nào vỡ khi gặp
  kind mới (vd `render_notes_journal`, `render_on_this_day`, `render_same_day_last_week`, Báo cáo ›
  Dự án ~`app.py:10855`).

**Thẻ "Huy hiệu"** ở Báo cáo › Tổng quan, chương 1, sau `render_top_3` (~`app.py:10412`):

- Card `jcard_badges`: tối đa 8 huy hiệu mới nhất, mỗi cái là một hàng icon + tiêu đề + ngày
  (`_day_link_html`).
- Nút "Xem tất cả (N)" mở `@st.dialog("Huy hiệu", position="right")` liệt kê toàn bộ, nhóm theo
  năm, mới nhất trước.

**Toast.** Có milestone đúng ngày `_today_vn()` (thường xảy ra ngay sau khi tự đồng bộ) thì toast
một lần mỗi session `icon=":material/military_tech:"`.

### 4.2 Phát hiện từ nhiều nguồn dữ liệu

**Tính toán.** `_compute_insights(df, wc, rl, notes)` (`@st.cache_data`). Trả list
`(icon, html_sentence)`. Mỗi nhận xét có ngưỡng mẫu tối thiểu; không đạt thì bỏ hẳn, không hiện câu
"chưa đủ dữ liệu".

1. **Lịch hẹn và giờ tập trung.** Chỉ xét ngày Thứ Hai–Thứ Sáu nằm trong khoảng `wc` có dữ liệu
   (min..max ngày của `work_calendar`) và `<= _today_vn()`. Nhóm "nhiều lịch" có ≥ 3 lịch hẹn,
   nhóm "ít lịch" có 0–1. Chỉ số: giờ tập trung trung bình mỗi ngày (ngày 0 giờ tính là 0). Cần
   ≥ 8 ngày mỗi nhóm và chênh lệch tương đối ≥ 15%.
2. **Đọc sách và tập trung.** Trong các ngày có phiên: ngày có ≥ 1 dòng reading_log không phải
   Gundam so với ngày không có. Chỉ số: giờ tập trung **không tính** Nhóm `BOOKS_GROUP` và
   `GUNDAM_TAG` (tránh tự cộng giờ đọc). Cần ≥ 10 ngày mỗi nhóm, chênh ≥ 15%.
3. **Ghi chú và tập trung.** Trong các ngày có phiên: ngày có ghi chú chính và ngày không có.
   Chỉ số: tổng giờ. Cần ≥ 10 ngày mỗi nhóm, chênh ≥ 15%.
4. **Buổi cho phiên dài nhất.** Độ dài phiên trung bình theo `_buoi_of()`. Buổi nào có ≥ 15 phiên
   và dài hơn trung bình chung ≥ 20% thì nêu tên buổi đó.

Câu chữ trung tính và có số liệu, ví dụ: "Ngày có từ 3 lịch hẹn trở lên, bạn tập trung trung bình
1h20′, so với 2h45′ ở ngày ít lịch." Không dùng giọng khuyên bảo.

**Hiển thị.** Card `jcard_insights` "Phát hiện" ở Báo cáo › Tổng quan, chương 1, ngay sau thẻ Huy
hiệu. Mỗi nhận xét một dòng có icon `_mi()`. Cuối card có một dòng nhỏ `var(--text-3)`: "Đây là
tương quan trong dữ liệu của bạn, không phải quan hệ nhân quả." Không có nhận xét nào đạt ngưỡng
thì ẩn cả card.

Viết script kiểm tra đủ các nhánh đạt/không đạt ngưỡng, và trường hợp `wc`/`rl`/`notes` rỗng
(phải trả list rỗng, không crash; xem yêu cầu "nguồn phụ tuỳ chọn" trong `docs/data-layer.md`).

### 4.3 Ôn trích dẫn

**Vị trí.** Sách › sub-tab "Trích dẫn", đầu `_render_kindle_quotes_tab()` (~`app.py:3116`), trước
các bộ lọc hiện có.

- Khối "Ôn hôm nay" (card `jcard_kqreview`): 5 highlight (`Loại == 'highlight'`) chọn bằng
  `random.Random(f"{_today_vn().isoformat()}|{salt}")`, có trọng số: Yêu thích ×3, còn lại ×1.
  Không trùng nhau. Loại trích dẫn đang hiện ở billboard Hôm nay của ngày hôm nay (so theo
  `dedupe_hash` với `_kindle_quote_of_day(_today_vn())`). Lưu ý hàm này đọc/ghi
  `kq_daily_*` trong session_state; nếu gọi ở đây làm lệch trạng thái billboard thì tính lại chỉ số
  theo seed mà không chạm session_state.
- Mỗi câu render bằng `_render_kindle_quote_row(r, key_suffix="kqreview")` để có sẵn ⭐/Sửa/Xoá.
  Kiểm tra key widget không trùng với danh sách bên dưới.
- Nút "Bộ khác" (`icon=":material/shuffle:"`): tăng `st.session_state["kq_review_salt"]` qua
  `on_click`.
- Có dưới 6 highlight thì ẩn khối.

---

## Thứ tự làm và bàn giao

| Giai đoạn | Nội dung | `requirements.txt` | Tài liệu cần cập nhật |
|---|---|---|---|
| 1 | 1.1, 1.2, 1.3 | không đổi | `docs/data-layer.md` |
| 2 | 2.1, 2.2 | `streamlit>=1.65,<2` | `docs/ui-components.md` |
| 3 | 3.1, 3.2, 3.3 | không đổi thêm | `docs/ui-components.md`, `docs/theming.md` (mục ECharts) |
| 4 | 4.1, 4.2, 4.3 | không đổi thêm | `docs/ui-components.md` |

Cuối mỗi giai đoạn, báo cáo cho người dùng:

- Đã làm gì.
- Ảnh chụp trước/sau của phần thay đổi (desktop + mobile).
- Kết quả các script kiểm tra.
- Mọi chỗ đã phải lệch khỏi kế hoạch này, và lý do.

Gặp điều kế hoạch không lường trước mà ảnh hưởng hành vi (vd buộc phải đánh số lại chương, cần
bảng mới, API Streamlit chạy khác mô tả), dừng lại hỏi người dùng thay vì tự quyết.
