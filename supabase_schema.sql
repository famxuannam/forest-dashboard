-- Chạy 1 lần trong Supabase Dashboard -> SQL Editor -> New query -> Run.
-- Tạo 4 bảng tương ứng 4 file CSV hiện tại, cộng RLS mở (app không có đăng nhập).

-- Lưu ý: dùng "timestamp" (KHÔNG timezone), không phải "timestamptz". Dữ liệu xuất từ Forest
-- là giờ theo đồng hồ treo tường (wall-clock), không mang thông tin múi giờ -- app hiện tại
-- (kể cả bản CSV) coi chuỗi giờ là "thô", không quy đổi UTC. Nếu dùng timestamptz, Postgres
-- sẽ ngầm định giờ nhập vào là UTC rồi tự quy đổi khi đọc ra theo múi giờ session, làm lệch
-- giờ hiển thị so với Forest gốc. "timestamp" giữ nguyên chuỗi giờ, an toàn tuyệt đối.
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

-- RLS: bật + cho phép full CRUD qua anon key. Khoá anon chỉ sống ở server-side trong
-- st.secrets (Streamlit không expose ra trình duyệt của người xem), nên mở toàn quyền ở
-- đây là chấp nhận được cho app không có lớp đăng nhập theo lựa chọn đã chốt.
alter table sessions enable row level security;
alter table mapping enable row level security;
alter table deleted_sessions enable row level security;
alter table notes enable row level security;

create policy "anon full access" on sessions for all using (true) with check (true);
create policy "anon full access" on mapping for all using (true) with check (true);
create policy "anon full access" on deleted_sessions for all using (true) with check (true);
create policy "anon full access" on notes for all using (true) with check (true);
