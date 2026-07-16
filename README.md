# Forest Dashboard

Dashboard cá nhân trực quan hoá dữ liệu tập trung từ app Forest — nhìn lại đã dành thời gian
cho việc gì, vào lúc nào, đều đặn ra sao. Đọc dữ liệu phiên tập trung xuất từ Forest, cộng
thêm 2 nguồn tuỳ chọn (lịch hẹn Work qua CalDAV, tiến độ đọc sách/xem Gundam qua Apple
Reminders). Toàn bộ mang tính hồi cứu (retrospective) — không đặt mục tiêu, không nhắc nhở,
Forest đã làm việc đó rồi.

Hướng dẫn sử dụng và giải thích từng tính năng nằm trong chính app, ở tab **Hướng dẫn**
(bao gồm sub-tab "Nhịp làm việc" — cách đưa app vào nhịp ngày/tuần/tháng thực tế). README này
không lặp lại nội dung đó, chỉ ghi lại vài điểm kiến trúc cho bản thân sau này đọc lại.

## Công nghệ

- **Streamlit** — giao diện + server, gói gọn trong một file `app.py`.
- **Supabase** (Postgres) — nơi lưu trữ duy nhất, không còn chế độ CSV cục bộ.
- **pandas** cho xử lý dữ liệu; **Plotly** + **Altair** cho biểu đồ.
- **streamlit-quill** cho ô ghi chú; **Authlib** cho đăng nhập Google (tuỳ chọn); **caldav**
  cho đồng bộ lịch Work và đọc tiến độ Reminders (tuỳ chọn).

## Cấu trúc

- `app.py` — toàn bộ ứng dụng.
- `supabase_schema.sql` — schema các bảng (`sessions`, `mapping`, `deleted_sessions`, `notes`,
  `work_calendar`, `reading_log`, `settings`).
- `.streamlit/config.toml` — theme sáng/tối; `.streamlit/secrets.toml.example` — mẫu các biến
  cần điền (chỉ `SUPABASE_URL`/`SUPABASE_KEY` là bắt buộc, còn lại đều tuỳ chọn).

## Lưu ý

App không có lớp bảo vệ nào theo mặc định (ai có URL đều xem/sửa được dữ liệu) trừ khi bật
đăng nhập Google qua mục `[auth]` trong secrets. Dữ liệu bền vững trên Supabase qua các lần
khởi động lại/redeploy; mục Sao lưu trong app (Tuỳ biến → Quản lý hệ thống) vẫn nên dùng định
kỳ như lớp an toàn thứ hai.
