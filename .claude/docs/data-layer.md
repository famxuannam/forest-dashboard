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
| `work_calendar`    | `load_work_calendar()`| `sync_work_calendar()`             | CalDAV (Apple Calendar "Work")    |
| `reading_log`      | `load_reading_log()`  | `save_reading_log_bulk()`          | File Shortcut xuất Apple Reminders|
| `settings`         | `load_settings()`     | (upsert trực tiếp trong nơi dùng)  | Nội bộ (màu accent...)            |
| `health_metrics`   | `load_health_metrics()` | `save_health_metrics_bulk()` (upsert, nhập tay/import JSON) · `save_health_metrics_raw_bulk()` (ghi đè toàn bộ, chỉ dùng khi Khôi phục) | Người dùng nhập tay hoặc dán JSON (trang Sức khoẻ) |
| `kindle_highlights` | `load_kindle_highlights()` | `save_kindle_highlights_bulk()` (upsert theo `dedupe_hash` tự tính lại, KHÔNG xoá sạch trước) | File `My Clippings.txt` xuất từ Kindle |
| `kindle_book_map`  | `load_kindle_book_map()` | `save_kindle_book_map_upsert()` (upsert theo `kindle_title`, cộng dồn) | Người dùng xác nhận trong UI import Kindle |

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

## `kindle_highlights`/`kindle_book_map`: khoá theo băm nội dung, không theo uid

Kindle không có id ổn định cho từng highlight/note, và `My Clippings.txt` luôn xuất TOÀN BỘ lịch sử
cộng dồn (cũ + mới) mỗi lần export — khác `work_calendar`/`reading_log` (khoá theo uid nguồn gốc).
Giải pháp: `_kindle_dedupe_hash(kindle_title, location, content)` băm SHA-256 làm khoá chính
(`dedupe_hash`), tính lại được y hệt từ chính dữ liệu thô — không cần lưu/truyền riêng. Nhờ vậy
`save_kindle_highlights_bulk()` dùng **upsert cộng dồn** (không `_sb_delete_all` trước như
`reading_log`): import lại cùng file, hoặc file từ nhiều thiết bị Kindle khác nhau, chỉ thêm dòng
thật sự mới, dòng trùng tự bị bỏ qua qua `on_conflict`.

`kindle_book_map` ánh xạ `kindle_title` (tên sách GHI NGUYÊN VĂN trong Clippings.txt, có thể khác
tên Dự án Forest tự đặt tay ở dấu câu/phụ đề) sang 1 Dự án đã có (`project`), hoặc để `NULL` kèm
`label` tự đặt nếu là nguồn không thuộc Dự án nào (vd tạp chí đọc định kỳ). `_fuzzy_match_project()`
(dùng `difflib`, không thêm thư viện fuzzy ngoài) chỉ GỢI Ý trong UI import — người dùng luôn xác
nhận/sửa tay trước khi lưu, và chỉ hỏi 1 lần cho mỗi `kindle_title` mới gặp (đã có trong
`kindle_book_map` thì các lần import sau tự nhớ). `load_kindle_highlights()` JOIN 2 bảng này ở
THỜI ĐIỂM ĐỌC (không lưu tên hiển thị trực tiếp trong `kindle_highlights`) để đổi ánh xạ sau này tự
áp dụng lại cho toàn bộ lịch sử, không cần sửa từng dòng.

Vì 2 bảng này dùng save-function kiểu **upsert cộng dồn** (không phải "xoá sạch rồi chèn lại" như
đa số bảng khác), luồng Khôi phục từ bản sao lưu phải tự gọi `_sb_delete_all()` cho cả 2 bảng
TRƯỚC KHI gọi `save_kindle_book_map_upsert()`/`save_kindle_highlights_bulk()`, để giữ đúng ngữ
nghĩa "ghi đè toàn bộ" của Khôi phục (xem khối `elif nav == "Tuỳ biến"` → mục "5. Quản lý hệ
thống" → nút "Xác nhận Khôi phục" trong app.py).

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
