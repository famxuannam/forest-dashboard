# Forest Dashboard

Dashboard cá nhân trực quan hoá dữ liệu tập trung từ app Forest — nhìn lại đã dành thời gian
cho việc gì, vào lúc nào, đều đặn ra sao. Đọc dữ liệu phiên tập trung xuất từ Forest, cộng
thêm 2 nguồn tuỳ chọn (lịch hẹn Work qua CalDAV, tiến độ đọc sách/xem Gundam qua Apple
Reminders). Toàn bộ mang tính hồi cứu (retrospective) — không đặt mục tiêu, không nhắc nhở,
Forest đã làm việc đó rồi.

README này ghi lại vài điểm kiến trúc cho bản thân sau này đọc lại, không phải hướng dẫn sử
dụng đầy đủ.

## Công nghệ

- **Streamlit** — giao diện + server, gói gọn trong một file `app.py`.
- **Supabase** (Postgres) — nơi lưu trữ duy nhất, không còn chế độ CSV cục bộ.
- **pandas** cho xử lý dữ liệu; **Plotly** + **Altair** cho biểu đồ.
- **streamlit-quill** cho ô ghi chú; **Authlib** cho đăng nhập Google (tuỳ chọn); **caldav**
  cho đồng bộ lịch Work và đọc tiến độ Reminders (tuỳ chọn).

## Cấu trúc

- `app.py` — toàn bộ ứng dụng.
- `local_dev_data.py` — Supabase giả và dữ liệu mẫu, chỉ dùng với `FOREST_LOCAL_DEV=1`.
- `ui_catalog.py` — catalogue màu, nền, font và nhãn UI thuần dữ liệu.
- `import_parsers.py` — parser cho các file import Forest, Reminders, Day One và Kindle.
- `supabase_schema.sql` — schema đầy đủ: `sessions`, `mapping`, `deleted_sessions`, `notes`,
  `quick_notes`, `work_calendar`, `reading_log`, `kindle_highlights`, `kindle_book_map`,
  `deleted_kindle_highlights`, `settings`, `gundam_overrides`, và
  `book_overrides`; đồng thời khai báo bucket Storage `sync-uploads`.
- `.streamlit/config.toml` — theme sáng/tối; `.streamlit/secrets.toml.example` — mẫu các biến
  cần điền (chỉ `SUPABASE_URL`/`SUPABASE_KEY` là bắt buộc, còn lại đều tuỳ chọn).
- `CLAUDE.md` và `docs/` — hướng dẫn phát triển, kiến trúc, data layer, UI và kiểm thử cho
  Claude Code.

## Lưu ý

App không có lớp bảo vệ nào theo mặc định (ai có URL đều xem/sửa được dữ liệu) trừ khi bật
đăng nhập Google qua mục `[auth]` trong secrets. Dữ liệu bền vững trên Supabase qua các lần
khởi động lại/redeploy; mục Sao lưu trong app (Tuỳ biến → Quản lý hệ thống) vẫn nên dùng định
kỳ như lớp an toàn thứ hai.

## Chạy local không đăng nhập

Không cần tạo `.streamlit/secrets.toml`. Dùng lệnh sau để chạy trên localhost với dữ liệu mẫu
trong bộ nhớ và bỏ qua Google OAuth:

```bash
FOREST_LOCAL_DEV=1 streamlit run app.py --server.address localhost
```

`FOREST_LOCAL_DEV` chỉ được chấp nhận khi server bind vào `localhost`, `127.0.0.1` hoặc `::1`.
Nếu bind ra địa chỉ mạng khác, app sẽ dừng thay vì vô tình mở quyền truy cập. Dữ liệu mẫu không
được lưu ra đĩa và mọi thay đổi sẽ mất khi dừng Streamlit.
