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

Mỗi `load_*` bọc 1 lần đọc bảng Supabase, cache bằng `@st.cache_data`; `save_*`/`sync_*` tương ứng
ghi xong rồi **bắt buộc** gọi `st.cache_data.clear()` — quên bước này là bug kinh điển (UI hiện dữ
liệu cũ sau khi lưu thành công).

**Thêm 1 bảng mới bắt buộc phải làm cả 2 việc**: viết cặp `load_*`/`save_*` VÀ cập nhật
`supabase_schema.sql` (file này là nguồn chân lý duy nhất cho schema — kể cả bucket Storage, xem
phần dưới). Thiếu 1 trong 2 là coi như chưa xong việc.

`work_calendar` và `reading_log` là nguồn phụ tuỳ chọn — code chạm vào 2 bảng này phải tự chịu được
trường hợp bảng rỗng/chưa cấu hình (trả DataFrame rỗng đúng cột, KHÔNG crash), vì người dùng thật
có thể chưa từng bật CalDAV hay chưa từng tải file Reminder.

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
