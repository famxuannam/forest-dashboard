# Tầng dữ liệu: Supabase, timezone, và luồng đồng bộ

Đối tượng đọc: AI agent cần thêm 1 nguồn dữ liệu mới, sửa logic tổng hợp, hoặc chạm vào bất kỳ chỗ
nào đọc/ghi Supabase.

## Quy tắc bất biến: Supabase là nơi lưu trữ DUY NHẤT

Không có chế độ CSV cục bộ, không cache dữ liệu người dùng xuống đĩa lâu dài. Mọi bảng có đúng 1
cặp hàm:

| Bảng               | load                  | save/sync                          | Nguồn dữ liệu                    |
|--------------------|-----------------------|-------------------------------------|-----------------------------------|
| `sessions`         | `load_db()`           | `save_db()`                        | CSV xuất từ Forest               |
| `mapping`          | `load_mapping()`      | `save_mapping()`                   | Người dùng gán tay trong app      |
| `deleted_sessions` | `load_deleted()`      | `add_deleted()`                    | Nội bộ (khi xoá phiên trong app)  |
| `notes`            | `load_notes()`        | (lưu trong hàm render ghi chú)     | Người dùng gõ trong app           |
| `quick_notes`      | `load_quick_notes()`  | (Shortcut iOS tự INSERT qua REST API) · `update_quick_note()`/`delete_quick_note()` (sửa/xoá lẻ trong app) · `save_quick_notes_bulk()` (ghi đè toàn bộ, chỉ dùng khi Khôi phục) | Shortcut iOS (không qua app) |
| `work_calendar`    | `load_work_calendar()`| `sync_work_calendar()`             | CalDAV (Apple Calendar "Work")    |
| `reading_log`      | `load_reading_log()`  | `save_reading_log_bulk()`          | File Shortcut xuất Apple Reminders|
| `settings`         | `load_settings()`     | (upsert trực tiếp trong nơi dùng)  | Nội bộ (màu accent...)            |
| `health_metrics`   | `load_health_metrics()` | `save_health_metrics_bulk()` (upsert, nhập tay/import JSON) · `save_health_metrics_raw_bulk()` (ghi đè toàn bộ, chỉ dùng khi Khôi phục) | Người dùng nhập tay hoặc dán JSON (trang Sức khoẻ) |
| `kindle_highlights` | `load_kindle_highlights()` | `save_kindle_highlights_bulk()` (insert-nếu-mới theo `dedupe_hash` tự tính lại từ file, ignore_duplicates -- dùng cho import) · `save_kindle_highlights_raw_bulk()` (ghi đè đúng `dedupe_hash`/`parent_hash` có sẵn, chỉ dùng khi Khôi phục) · `update_kindle_highlight_content()`/`delete_kindle_highlight()`/`add_kindle_note()` (sửa/xoá/thêm ghi chú trong app) | File `My Clippings.txt` xuất từ Kindle + người dùng sửa/thêm trong app |
| `kindle_book_map`  | `load_kindle_book_map()` | `save_kindle_book_map_upsert()` (upsert theo `kindle_title`, cộng dồn) | Người dùng xác nhận trong UI import Kindle |
| `deleted_kindle_highlights` | `load_deleted_kindle()` | `add_deleted_kindle()` (cộng dồn) · `save_deleted_kindle()` (ghi đè toàn bộ, chỉ dùng khi Khôi phục) | Nội bộ (khi xoá trích dẫn Kindle trong app) |
| `gundam_overrides` | `load_gundam_overrides()` (trả `dict {date: series}`) | `save_gundam_override()`/`delete_gundam_override()` (gán/bỏ gán 1 ngày trong app) · `save_gundam_overrides_bulk()` (ghi đè toàn bộ, chỉ dùng khi Khôi phục) | Người dùng sửa tay ở trang Gundam → "Sửa gán series tự động" |

Mỗi `load_*` bọc 1 lần đọc bảng Supabase, cache bằng `@st.cache_data`; `save_*`/`sync_*` tương ứng
ghi xong rồi **bắt buộc** gọi `st.cache_data.clear()` — quên bước này là bug kinh điển (UI hiện dữ
liệu cũ sau khi lưu thành công).

**Thêm 1 bảng mới bắt buộc phải làm cả 2 việc**: viết cặp `load_*`/`save_*` VÀ cập nhật
`supabase_schema.sql` (file này là nguồn chân lý duy nhất cho schema — kể cả bucket Storage, xem
phần dưới). Thiếu 1 trong 2 là coi như chưa xong việc.

`work_calendar` và `reading_log` là nguồn phụ tuỳ chọn — code chạm vào 2 bảng này phải tự chịu được
trường hợp bảng rỗng/chưa cấu hình (trả DataFrame rỗng đúng cột, KHÔNG crash), vì người dùng thật
có thể chưa từng bật CalDAV hay chưa từng tải file Reminder.

## `health_metrics`: ngoại lệ duy nhất CÓ nhập liệu tay (trang Sức khoẻ)

Toàn bộ phần còn lại của app thuần hồi cứu (đọc lại dữ liệu Forest/CalDAV/Reminders), nhưng không có
nguồn tự động nào xuất được kết quả xét nghiệm máu ra file -- người dùng chụp ảnh phiếu xét nghiệm,
nhờ Claude đọc rồi dán JSON, hoặc gõ tay trực tiếp trong app. Vài điểm khác biệt so với các bảng
khác cần nhớ khi sửa:

- **Long format, không phải 1 cột/chỉ số**: mỗi dòng là 1 chỉ số của 1 lần xét nghiệm (`test_date`,
  `category`, `indicator`, `value`...) -- panel xét nghiệm đổi qua các năm (đổi lab/máy) không đòi
  hỏi sửa schema, chỉ cần lưu thêm dòng.
- **Khoảng tham chiếu lưu KÈM mỗi dòng** (`ref_raw`/`ref_low`/`ref_high`), không tách bảng riêng --
  vì khoảng "bình thường" có thể đổi theo thời gian (đổi máy xét nghiệm), tách riêng sẽ làm sai lệch
  dữ liệu lịch sử khi tra cứu lại các lần đo cũ. `_parse_ref_range()` parse chuỗi gốc (`"a - b"`,
  `"< x"`, `"> x"`) về `(ref_low, ref_high)` dạng số, dùng để tô vùng biểu đồ + phát hiện bất thường.
- **2 hàm ghi khác ngữ nghĩa**: `save_health_metrics_bulk(panels)` là **upsert** theo khoá
  `(test_date, category, indicator)`, dùng cho nhập liệu thường ngày (form nhập nhanh, import JSON,
  sửa 1 panel ở mục Lịch sử -- mục Lịch sử tự xoá cả panel trước khi gọi lại hàm này để phản ánh
  đúng việc xoá/đổi tên chỉ số qua `st.data_editor`). `save_health_metrics_raw_bulk(df)` là **ghi đè
  toàn bộ** (xoá sạch rồi chèn lại), CHỈ dùng trong luồng Khôi phục từ bản sao lưu ở tab Tuỳ biến.
- Có mặt trong cả 3 thao tác ở tab Tuỳ biến (Sao lưu/Khôi phục/Làm mới) -- thêm bảng Supabase mới
  nào có ý nghĩa tồn tại lâu dài cũng nên soát lại 3 chỗ này, không chỉ viết `load_*`/`save_*`.

## `kindle_highlights`/`kindle_book_map`/`deleted_kindle_highlights`: khoá theo băm nội dung, sửa/xoá được trong app

Kindle không có id ổn định cho từng highlight/note, và `My Clippings.txt` luôn xuất TOÀN BỘ lịch sử
cộng dồn (cũ + mới) mỗi lần export — khác `work_calendar`/`reading_log` (khoá theo uid nguồn gốc).
Giải pháp: `_kindle_dedupe_hash(kindle_title, location, content)` băm SHA-256 làm khoá chính
(`dedupe_hash`) LÚC TẠO/IMPORT. **Sau khi có tính năng Sửa nội dung, hash này KHÔNG còn tính lại
được từ dữ liệu hiện tại nữa** — nội dung có thể đã khác bản gốc lúc băm — nên mọi thao tác
sửa/xoá/gắn ghi chú phải dùng đúng cột `dedupe_hash` đọc từ `load_kindle_highlights()`, tuyệt đối
không gọi lại `_kindle_dedupe_hash()` để suy ngược khoá từ nội dung đang hiển thị.

- `save_kindle_highlights_bulk(df)` — dùng cho **import** (df là nội dung THÔ vừa đọc từ
  `parse_kindle_clippings()`, tự tính `dedupe_hash` từ đó): `upsert(..., ignore_duplicates=True)`
  = INSERT, bỏ qua nếu trùng khoá (KHÔNG update) — đây chính là cơ chế giữ nguyên bản đã Sửa khi
  import lại cùng file: dòng đó vẫn tính ra đúng hash cũ nhưng bị bỏ qua thay vì ghi đè. Dòng đã
  bị Xoá (`dedupe_hash` nằm trong `deleted_kindle_highlights`) phải được UI import tự lọc bỏ TRƯỚC
  khi gọi hàm này — `ignore_duplicates` chỉ chặn ghi đè, không chặn việc chèn lại 1 dòng đã xoá hẳn
  (không còn trong bảng nên không đụng độ khoá).
- `save_kindle_highlights_raw_bulk(df)` — **CHỈ dùng khi Khôi phục từ bản sao lưu** (df đọc từ CSV
  backup, đã có sẵn cột `dedupe_hash`/`parent_hash` gốc): insert thẳng theo đúng khoá cũ, KHÔNG
  tính lại — y hệt lý do `health_metrics` cần 2 hàm ghi riêng (raw vs upsert thường), xem mục dưới.
- `update_kindle_highlight_content()`/`delete_kindle_highlight()`/`add_kindle_note()` — sửa/xoá/
  thêm ghi chú trực tiếp trong app (mục "2. Nhật ký đọc" ở Sách/Gundam → Chi tiết). `delete_*` vừa
  xoá khỏi `kindle_highlights` vừa ghi `dedupe_hash` vào sổ đen `deleted_kindle_highlights` (cùng
  vai trò `deleted_sessions`, ngăn import lại file cũ hồi sinh dòng đã xoá) + cascade xoá các ghi
  chú BẠN TỰ THÊM gắn với nó qua `parent_hash`. `add_kindle_note(parent_row, content)` tạo 1 dòng
  `kind='note'` mới với `parent_hash` trỏ về đúng highlight/note cha, COPY nguyên "Vị trí"/"Ngày
  thêm" của cha (để luôn nhóm đúng ngày khi hiển thị, xem `_render_reading_kindle_days()` trong
  app.py).
- `parent_hash` CHỈ có giá trị ở ghi chú tạo qua `add_kindle_note()` — ghi chú GỐC từ Kindle (nhập
  thẳng từ Clippings.txt) luôn có `parent_hash = NULL`; lúc RENDER, app tự lồng loại ghi chú này
  xuống dưới 1 highlight cùng ngày có `location` trùng khớp (suy luận hiển thị, không lưu quan hệ
  vào DB) — xem `_render_kindle_day_quotes()`.
- `is_favorite` (cột boolean, mặc định `false`) đánh dấu 1 trích dẫn/ghi chú "Yêu thích" — bật/tắt
  qua `set_kindle_highlight_favorite(dedupe_hash, is_favorite)`, cũng khoá theo `dedupe_hash` như
  mọi thao tác sửa/xoá khác ở trên. Đọc lại qua cột `Yêu thích` do `load_kindle_highlights()` rename
  ra. `save_kindle_highlights_bulk()` (import) CỐ Ý không đụng tới cột này (`ignore_duplicates=True`
  không ghi đè dòng đã có, cột mới insert dùng default `false` của Postgres) — favorite không bao
  giờ bị mất khi import lại cùng file. `save_kindle_highlights_raw_bulk()` (Khôi phục) có đọc/ghi lại
  `is_favorite` từ CSV backup như các cột khác. UI dùng cột này ở 2 chỗ: nút ⭐ trên mỗi dòng ở
  "2. Nhật ký đọc" (`_render_kindle_quote_row()`) và sub-tab "Yêu thích" riêng (trang Sách, không có
  ở Gundam — `_render_kindle_favorites_tab()`, lọc `Yêu thích == True` rồi group theo `Cuốn sách`).

`kindle_book_map` ánh xạ `kindle_title` (tên sách GHI NGUYÊN VĂN trong Clippings.txt, có thể khác
tên Dự án Forest tự đặt tay ở dấu câu/phụ đề) sang 1 Dự án đã có (`project`), hoặc để `NULL` kèm
`label` tự đặt nếu là nguồn không thuộc Dự án nào (vd tạp chí đọc định kỳ). `_fuzzy_match_project()`
(dùng `difflib`, không thêm thư viện fuzzy ngoài) chỉ GỢI Ý trong UI import — người dùng luôn xác
nhận/sửa tay trước khi lưu, và chỉ hỏi 1 lần cho mỗi `kindle_title` mới gặp (đã có trong
`kindle_book_map` thì các lần import sau tự nhớ). `load_kindle_highlights()` JOIN 2 bảng này ở
THỜI ĐIỂM ĐỌC (không lưu tên hiển thị trực tiếp trong `kindle_highlights`) để đổi ánh xạ sau này tự
áp dụng lại cho toàn bộ lịch sử, không cần sửa từng dòng.

`kindle_book_map` dùng save-function kiểu **upsert cộng dồn** (không phải "xoá sạch rồi chèn lại"
như đa số bảng khác), nên luồng Khôi phục từ bản sao lưu phải tự gọi `_sb_delete_all()` cho cả
`kindle_highlights` lẫn `kindle_book_map` TRƯỚC KHI gọi `save_kindle_book_map_upsert()`/
`save_kindle_highlights_raw_bulk()`, để giữ đúng ngữ nghĩa "ghi đè toàn bộ" của Khôi phục (xem
khối `elif nav == "Tuỳ biến"` → mục "5. Quản lý hệ thống" → nút "Xác nhận Khôi phục" trong app.py).

Mục "2. Nhật ký đọc" (Sách/Gundam → Chi tiết) là nơi DUY NHẤT trong app vẽ quote/note Kindle bằng
`st.columns()` thật (không phải HTML tĩnh `.jrows` như mọi nơi khác dùng `_reading_rows_html()`) —
vì cột nội dung cần nút Sửa/Xoá/+ Ghi chú thật (`st.button`), không nhét vào 1 chuỗi HTML được. Xem
`_render_reading_kindle_days()`/`_render_kindle_day_quotes()`/`_render_kindle_quote_row()` trong
app.py, cùng khuôn 2 cột + icon nút nhỏ với hàng "Ghi chú nhanh" (`qnote_row`) trong
`render_note_editor()`. Quote/note trong 1 ngày xếp theo **"Vị trí" Kindle tăng dần**
(`_kindle_location_sort_key()`), KHÔNG theo giờ và KHÔNG có nút sắp xếp tay — quyết định đã chốt
với người dùng: Reminders chỉ ghi NGÀY hoàn thành chương (không có giờ) nên không thể suy luận
đáng tin quote thuộc chương nào trong 1 ngày đọc nhiều chương, còn "Vị trí" tăng dần theo trang
sách lại tự nhiên đúng thứ tự đọc thật (đọc tuần tự).

## `quick_notes`: "hộp thư nháp" trong ngày, gộp tay vào `notes`

Ghi thẳng bởi Shortcut iOS qua REST API (KHÔNG qua app) — quy trình thực tế: ghi chú nhanh suốt
ngày qua Siri/Shortcut, tối tổng hợp thành Ghi chú chính (`notes`) rồi xoá. `render_note_editor()`
có nút "Gộp" trên mỗi dòng quick note: chèn nội dung vào cuối ô soạn Quill đang mở (hoặc mở ô soạn
nếu chưa mở), đánh dấu dòng đó "chờ xoá" trong `session_state`; chỉ THỰC SỰ gọi `delete_quick_note()`
sau khi người dùng bấm "Cập nhật" lưu ghi chú chính thành công (Huỷ/Xoá ghi chú thì chỉ bỏ đánh
dấu, không đụng bảng) — tránh mất ghi chú nhanh nếu đổi ý giữa chừng trước khi lưu. 2 bảng vẫn tách
biệt hoàn toàn, không có quan hệ khoá ngoại nào được lưu.

## `gundam_overrides`: gán tay ngày → series, ghi đè suy luận tự động

Forest chỉ có 1 tag `GUNDAM_TAG` chung cho mọi phiên xem Gundam, không phân biệt được đang xem
series nào — `_assign_gundam_sessions()` suy luận bằng cách gán mỗi NGÀY có phiên Gundam vào series
có lần hoàn thành reminder GẦN NHẤT (`pd.merge_asof(direction='nearest')`). Suy luận này có thể sai
nếu 2 series được xem xen kẽ nhau. `gundam_overrides` (khoá theo `session_date`, KHÔNG theo từng
phiên — vì bản thân suy luận tự động cũng gán theo ngày) cho phép ghi đè tay; `_assign_gundam_sessions()`
nhận thêm tham số `overrides` (dict `{date: series}` từ `load_gundam_overrides()`), áp dụng SAU
`merge_asof` nên override luôn thắng. UI sửa nằm ở trang Gundam → expander "Sửa gán series tự động"
(chỉ hiện khi có từ 2 series trở lên — 1 series duy nhất thì suy luận không thể sai).

## `prep_analysis_data()`: điểm nối dữ liệu DUY NHẤT cho mọi trang báo cáo

Hàm này join `sessions` với `mapping` (Dự án → Danh mục), sinh thêm cột kỳ (`Tuần`/`Tháng`/`Năm`/
`Thứ`) từ `Thời gian bắt đầu`. Toàn bộ trang Báo cáo (Tổng quan/Tuần/Tháng/Năm/Dự án) đọc từ
DataFrame này rồi tự `groupby`. Hàm PHẢI trả về đúng bộ cột ngay cả khi rỗng (không early-return
DataFrame trống trơn) — nhiều trang gọi `df['Dự án']` v.v. mà không kiểm tra `df.empty` trước.

## Timezone: `_today_vn()`, không bao giờ `date.today()` trần

`APP_TZ = ZoneInfo("Asia/Ho_Chi_Minh")` cố định bất kể múi giờ server (Streamlit Cloud chạy UTC).
`date.today()` trên server UTC lệch 1 ngày so với giờ Việt Nam trong khung 00:00–07:00 giờ VN mỗi
ngày (= 17:00–24:00 UTC hôm trước) — đây là bug thật đã xảy ra và được sửa. Bất kỳ chỗ nào cần biết
"hôm nay" (ngày mặc định, kiểm tra "có phải kỳ hiện tại", đếm ngày nhắc sao lưu...) phải gọi
`_today_vn()`, không được viết `date.today()` mới.

## Luồng "Đồng bộ nhanh": Supabase Storage thay cho đọc trực tiếp iCloud Drive

App chạy trên server từ xa (không có filesystem chung với điện thoại người dùng), nên không thể
đọc trực tiếp thư mục iCloud Drive. Giải pháp: 1 Shortcut iOS chạy từ share sheet (khi Export CSV
từ Forest) tự gộp thêm file backup Reminders rồi POST cả 2 lên 1 bucket Supabase Storage qua HTTP
request; app chỉ cần quét bucket đó.

- `_sync_bucket_name()` — tên bucket, mặc định `"sync-uploads"`, đổi được qua secret tuỳ chọn
  `SUPABASE_SYNC_BUCKET`.
- `_list_sync_files()` / `_latest_sync_file(files, prefix)` — liệt kê + tìm file mới nhất theo
  tiền tố tên file (`forest`/`reminder`, KHÔNG phân biệt hoa/thường). Quy ước đặt tên file do
  Shortcut tải lên là hợp đồng duy nhất giữa app và Shortcut — đổi 1 bên phải đổi bên kia.
- `sync_from_storage(cal_start, cal_end)` — hàm điều phối: tải file Forest mới nhất → nạp qua
  `parse_forest_csv()` (cộng thêm + bỏ trùng/đã xoá, y hệt luồng tải tay); tải file Reminder mới
  nhất → nạp qua `parse_reading_log_shortcut_csv()` (**thay thế toàn bộ**, không cộng dồn); gọi
  `sync_work_calendar()`; cuối cùng xoá các file CŨ HƠN cùng loại trong bucket (giữ đúng 1 file mới
  nhất mỗi loại) — **chỉ xoá sau khi nạp thành công**, để file lỗi/thiếu cột còn nguyên cho lần thử
  lại. Không raise exception ra UI — mọi lỗi trả về trong dict kết quả để hiển thị.
- Bucket + RLS policy tạo bằng SQL trong `supabase_schema.sql` (đoạn cuối file), cùng khuôn "anon
  full access" như các bảng khác — app không có lớp đăng nhập theo lựa chọn đã chốt.
