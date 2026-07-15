-- Chạy 1 lần trong Supabase Dashboard -> SQL Editor -> New query -> Run.
-- Tạo 4 bảng lưu dữ liệu app (sessions/mapping/deleted_sessions/notes), cộng RLS mở
-- (app không có đăng nhập, chỉ dựa vào URL không công khai).

-- Lưu ý: dùng "timestamp" (KHÔNG timezone), không phải "timestamptz". Dữ liệu xuất từ Forest
-- là giờ theo đồng hồ treo tường (wall-clock), không mang thông tin múi giờ -- app coi chuỗi
-- giờ là "thô", không quy đổi UTC. Nếu dùng timestamptz, Postgres sẽ ngầm định giờ nhập vào là
-- UTC rồi tự quy đổi khi đọc ra theo múi giờ session, làm lệch giờ hiển thị so với Forest gốc.
-- "timestamp" giữ nguyên chuỗi giờ, an toàn tuyệt đối.
create table if not exists sessions (
  id bigint generated always as identity primary key,
  start_time timestamp not null,
  end_time timestamp not null,
  project text not null,
  duration_min integer not null,
  unique (start_time, end_time)
);

create table if not exists mapping (
  project text primary key,
  category text not null
);

create table if not exists deleted_sessions (
  start_time timestamp not null,
  end_time timestamp not null,
  primary key (start_time, end_time)
);

create table if not exists notes (
  note_date date primary key,
  note text not null
);

-- Ghi chú nhanh từ Shortcut iOS (mục "Ghi chú nhanh" trong tab Hướng dẫn) -- Shortcut chỉ INSERT
-- thẳng 1 row thô qua REST API (KHÔNG đụng tới bảng notes/HTML Quill), app tự đọc bảng này và
-- gộp thủ công vào notes khi người dùng bấm nút "Gộp vào Ghi chú chính" trong trình soạn ngày.
-- "ts" do chính Shortcut tự format và gửi lên (KHÔNG dùng "default now()") -- server Supabase
-- chạy UTC, lệch múi giờ Việt Nam, nên phải để Shortcut tự lấy giờ máy rồi gửi nguyên chuỗi
-- thô, giống quy ước "timestamp" thô ở đầu file này.
create table if not exists quick_notes (
  id bigint generated always as identity primary key,
  ts timestamp not null,
  note_text text not null
);

-- Appointment đồng bộ từ lịch "Work" (Apple Calendar) qua CalDAV -- xem mục "Đồng bộ lịch
-- Work" trong tab Chuẩn bị dữ liệu. Khoá theo (uid, start_time) chứ không chỉ uid, vì 1 sự
-- kiện lặp lại (recurring) sau khi khai triển có nhiều lần xuất hiện cùng uid khác start_time.
create table if not exists work_calendar (
  uid text not null,
  start_time timestamp not null,
  title text not null,
  primary key (uid, start_time)
);

-- Phần sách đã đọc, đồng bộ từ Apple Reminders qua CalDAV (VTODO) -- mỗi Reminder List = 1
-- cuốn sách ("Tác giả - Tên sách"), mỗi Reminder đã hoàn thành trong list đó = 1 phần/chương
-- đã đọc. Khoá theo (uid, completed_date): 1 reminder chỉ hoàn thành 1 lần trong thực tế
-- nhưng dùng khoá kép cho nhất quán với work_calendar (đề phòng cùng uid xuất hiện lại nếu
-- reminder bị bỏ tick rồi tick lại ở ngày khác).
create table if not exists reading_log (
  uid text not null,
  completed_date timestamp not null,
  book text not null,
  title text not null,
  primary key (uid, completed_date)
);

-- Trích dẫn/ghi chú Kindle, nạp từ file "My Clippings.txt" (xem parse_kindle_clippings() trong
-- app.py) -- mỗi dòng là 1 highlight/note gốc. Khoá theo dedupe_hash (băm từ tên sách + vị trí +
-- nội dung, tính lại được y hệt từ dữ liệu thô) thay vì (uid, ...) như work_calendar/reading_log,
-- vì Kindle KHÔNG có id ổn định cho từng entry, và file xuất luôn chứa TOÀN BỘ lịch sử cộng dồn
-- (cũ + mới) mỗi lần export -- import lặp lại nhiều lần (hoặc từ nhiều thiết bị Kindle khác nhau)
-- chỉ upsert thêm dòng thật sự mới, không cần xoá sạch trước như reading_log.
create table if not exists kindle_highlights (
  dedupe_hash text primary key,
  kindle_title text not null,  -- tên sách GHI NGUYÊN VĂN dòng đầu mỗi entry trong Clippings.txt
  author text,
  kind text not null,          -- 'highlight' | 'note' (Bookmark bị bỏ qua lúc parse, không có nội dung)
  content text not null,
  location text,                -- vị trí/trang Kindle, giữ nguyên chuỗi gốc (vd "183-185")
  added_at timestamp,
  parent_hash text             -- xem alter table ngay dưới đây (cột thêm sau, không nằm trong
                                -- create table gốc)
);

-- Cột thêm sau khi bảng đã tồn tại thật (không nằm trong create table gốc ở trên vì "create
-- table if not exists" không tự thêm cột mới cho bảng ĐÃ có sẵn) -- "alter table add column if
-- not exists" an toàn để chạy lại nhiều lần. parent_hash: chỉ có giá trị ở ghi chú BẠN TỰ THÊM
-- trong app (nút "+ thêm ghi chú" ở 1 quote cụ thể, xem add_kindle_note() trong app.py) -- trỏ
-- về đúng dedupe_hash của highlight/note nó là câu trả lời, để hiện lồng đúng dưới quote đó
-- trong "Nhật ký đọc". NULL với mọi entry nhập thẳng từ Clippings.txt (kể cả note gốc Kindle --
-- note đó được LỒNG HIỂN THỊ dưới highlight cùng "Vị trí" bằng suy luận lúc render, không phải
-- quan hệ lưu trong DB, nên không cần parent_hash).
alter table kindle_highlights add column if not exists parent_hash text;

-- Đánh dấu "Yêu thích" 1 trích dẫn/ghi chú Kindle -- nút ⭐ ở "Nhật ký đọc" và ở thẻ "Trích dẫn
-- hôm nay" (trang Hôm nay), gộp lại xem ở sub-tab "Yêu thích" (trang Sách, không có ở Gundam).
-- default false để mọi dòng cũ (import từ trước khi có tính năng này) không tự nhiên thành yêu
-- thích hết.
alter table kindle_highlights add column if not exists is_favorite boolean not null default false;

-- Sổ đen các trích dẫn/ghi chú Kindle đã xoá trong app (nút Xoá, xem delete_kindle_highlight()
-- trong app.py) -- cùng vai trò với deleted_sessions nhưng riêng cho Kindle: My Clippings.txt
-- luôn xuất TOÀN BỘ lịch sử cộng dồn, nên nếu chỉ xoá khỏi kindle_highlights mà không ghi nhớ ở
-- đây, lần import file cũ tiếp theo sẽ vô tình chèn lại y hệt dòng vừa xoá.
create table if not exists deleted_kindle_highlights (
  dedupe_hash text primary key
);

-- Ánh xạ tên sách Kindle (kindle_title, khớp NGUYÊN VĂN với kindle_highlights.kindle_title) sang
-- 1 Dự án đã có trong bảng mapping, hoặc để trống (project = NULL) kèm nhãn tự đặt nếu là nguồn
-- không thuộc Dự án nào (vd tạp chí đọc định kỳ) -- xem UI xác nhận lúc import trong app.py. Lưu 1
-- lần lúc xác nhận, các lần import sau tự nhớ theo đúng kindle_title, không hỏi lại.
create table if not exists kindle_book_map (
  kindle_title text primary key,
  project text,   -- NULL = nguồn độc lập, không gắn Dự án nào
  label text not null
);

-- Cài đặt app dạng key/value (hiện dùng cho màu accent, xem mục "Giao diện" trong tab Tuỳ
-- biến) -- optional: nếu bảng này chưa tồn tại hoặc Supabase lỗi, app tự rơi về mặc định
-- (Teal), không crash (xem load_settings() trong app.py).
create table if not exists settings (
  key text primary key,
  value text not null
);

-- Chỉ số xét nghiệm máu định kỳ (tab "Sức khoẻ") -- dạng "long format": mỗi dòng là 1 chỉ số
-- của 1 lần xét nghiệm (không phải 1 cột/chỉ số), vì panel xét nghiệm có thể đổi qua các năm
-- (đổi lab, đổi máy, thêm/bớt chỉ số). Khoảng tham chiếu (ref_raw/ref_low/ref_high) lưu KÈM
-- theo từng dòng, không tách bảng riêng -- vì khoảng "bình thường" có thể đổi theo thời gian
-- (đổi máy xét nghiệm/đổi lab), lưu tách riêng sẽ sai lệch dữ liệu lịch sử.
create table if not exists health_metrics (
  id bigint generated always as identity primary key,
  test_date date not null,
  category text not null,   -- "Huyết học" / "Sinh hóa" / ... (mở rộng tự do, không enum cứng)
  indicator text not null,  -- tên chỉ số, vd "Hemoglobin", "Glucose"
  value numeric,            -- giá trị số, dùng để vẽ biểu đồ (NULL nếu kết quả định tính)
  value_raw text not null,  -- chuỗi gốc y hệt trên phiếu, vd "148", "Âm tính"
  unit text,
  ref_raw text,             -- khoảng tham chiếu gốc y hệt trên phiếu, vd "130 - 170", "< 5"
  ref_low numeric,          -- parse từ ref_raw (xem _parse_ref_range trong app.py), NULL nếu không parse được
  ref_high numeric,
  unique (test_date, category, indicator)
);

-- Gán tay ngày -> series Gundam, ghi đè kết quả suy luận tự động của _assign_gundam_sessions()
-- trong app.py (Forest chỉ có 1 tag "Gundam" chung, không phân biệt series -- suy luận theo
-- "lần hoàn thành reminder gần nhất" có thể đoán sai nếu 2 series xem xen kẽ nhau). Khoá theo
-- NGÀY (không phải từng phiên) vì bản thân suy luận tự động cũng gán theo ngày.
create table if not exists gundam_overrides (
  session_date date primary key,
  series text not null
);

-- RLS: bật + cho phép full CRUD qua anon key. Khoá anon chỉ sống ở server-side trong
-- st.secrets (Streamlit không expose ra trình duyệt của người xem), nên mở toàn quyền ở
-- đây là chấp nhận được cho app không có lớp đăng nhập theo lựa chọn đã chốt.
alter table sessions enable row level security;
alter table mapping enable row level security;
alter table deleted_sessions enable row level security;
alter table notes enable row level security;
alter table quick_notes enable row level security;
alter table work_calendar enable row level security;
alter table reading_log enable row level security;
alter table settings enable row level security;
alter table health_metrics enable row level security;
alter table kindle_highlights enable row level security;
alter table kindle_book_map enable row level security;
alter table deleted_kindle_highlights enable row level security;
alter table gundam_overrides enable row level security;

create policy "anon full access" on sessions for all using (true) with check (true);
create policy "anon full access" on mapping for all using (true) with check (true);
create policy "anon full access" on deleted_sessions for all using (true) with check (true);
create policy "anon full access" on notes for all using (true) with check (true);
create policy "anon full access" on quick_notes for all using (true) with check (true);
create policy "anon full access" on work_calendar for all using (true) with check (true);
create policy "anon full access" on reading_log for all using (true) with check (true);
create policy "anon full access" on settings for all using (true) with check (true);
create policy "anon full access" on health_metrics for all using (true) with check (true);
create policy "anon full access" on kindle_highlights for all using (true) with check (true);
create policy "anon full access" on kindle_book_map for all using (true) with check (true);
create policy "anon full access" on deleted_kindle_highlights for all using (true) with check (true);
create policy "anon full access" on gundam_overrides for all using (true) with check (true);

-- Bucket Storage cho tab "Đồng bộ nhanh" (mục 1. Dữ liệu đầu vào, tab Tuỳ biến) -- nơi Shortcut
-- iOS tải file Forest CSV + Reminder backup lên qua HTTP request (share sheet), app quét bucket
-- này để nạp dữ liệu thay vì đọc trực tiếp iCloud Drive (server chạy từ xa, không có filesystem
-- chung với điện thoại). "public = false" vì file chỉ cần đọc/ghi qua API bằng anon key (đã có
-- trong secrets), không cần truy cập qua URL công khai không xác thực. Đổi tên 'sync-uploads' ở
-- CẢ 2 chỗ dưới đây nếu bạn đặt SUPABASE_SYNC_BUCKET khác trong secrets.toml.
insert into storage.buckets (id, name, public)
values ('sync-uploads', 'sync-uploads', false)
on conflict (id) do nothing;

-- storage.objects đã bật RLS sẵn từ phía Supabase -- chỉ cần thêm policy, không cần "alter
-- table ... enable row level security" (khác các bảng tự tạo ở trên). Cùng lý do "mở toàn
-- quyền qua anon key" như các bảng khác: app không có lớp đăng nhập theo lựa chọn đã chốt.
create policy "anon full access sync-uploads" on storage.objects for all
  using (bucket_id = 'sync-uploads') with check (bucket_id = 'sync-uploads');
