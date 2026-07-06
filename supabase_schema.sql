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

-- Ghi chú nhanh từ Shortcut iOS (mục "Ghi chú nhanh" trong tab Hướng dẫn) -- gọi qua REST API
-- dạng RPC (POST .../rest/v1/rpc/append_note_bullet), KHÔNG đi qua app: Shortcut tự đọc note
-- hiện có của đúng ngày, chèn 1 bullet mới vào CUỐI danh sách <ul> gần nhất (hoặc tạo <ul> mới
-- nếu ghi chú đang trống/chưa có danh sách), rồi ghi đè lại -- tất cả trong 1 lệnh, tránh race
-- condition nếu gọi 2 lần liên tiếp nhanh (đọc-sửa-ghi làm trong đúng 1 transaction của hàm,
-- không tách thành 2 request riêng như get-rồi-patch). Escape "&/</>" tối thiểu (ĐÚNG thứ tự,
-- & trước) vì note là HTML (Quill) -- chèn thẳng text thô sẽ vỡ cấu trúc HTML nếu người dùng
-- gõ ký tự đặc biệt.
create or replace function append_note_bullet(p_date date, p_text text)
returns void
language plpgsql
as $$
declare
  v_escaped text;
  v_current text;
  v_trimmed text;
  v_new text;
begin
  v_escaped := replace(replace(replace(p_text, '&', '&amp;'), '<', '&lt;'), '>', '&gt;');
  select note into v_current from notes where note_date = p_date;
  -- rtrim() thô CHỈ cắt dấu cách (space), không cắt newline/tab -- Quill có thể để lại 1 dòng
  -- trắng cuối note, khiến so khớp "</ul>" ở cuối chuỗi trật (đã tự kiểm chứng bằng test cục
  -- bộ). regexp_replace cắt MỌI loại khoảng trắng cuối chuỗi mới đúng.
  v_trimmed := regexp_replace(coalesce(v_current, ''), '\s+$', '');

  if v_trimmed = '' then
    v_new := '<ul><li>' || v_escaped || '</li></ul>';
  elsif v_trimmed like '%</ul>' then
    v_new := left(v_trimmed, length(v_trimmed) - 5) || '<li>' || v_escaped || '</li></ul>';
  else
    v_new := v_trimmed || '<ul><li>' || v_escaped || '</li></ul>';
  end if;

  insert into notes (note_date, note) values (p_date, v_new)
  on conflict (note_date) do update set note = excluded.note;
end;
$$;

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

-- Cài đặt app dạng key/value (hiện dùng cho màu accent, xem mục "Giao diện" trong tab Tuỳ
-- biến) -- optional: nếu bảng này chưa tồn tại hoặc Supabase lỗi, app tự rơi về mặc định
-- (Teal), không crash (xem load_settings() trong app.py).
create table if not exists settings (
  key text primary key,
  value text not null
);

-- RLS: bật + cho phép full CRUD qua anon key. Khoá anon chỉ sống ở server-side trong
-- st.secrets (Streamlit không expose ra trình duyệt của người xem), nên mở toàn quyền ở
-- đây là chấp nhận được cho app không có lớp đăng nhập theo lựa chọn đã chốt.
alter table sessions enable row level security;
alter table mapping enable row level security;
alter table deleted_sessions enable row level security;
alter table notes enable row level security;
alter table work_calendar enable row level security;
alter table reading_log enable row level security;
alter table settings enable row level security;

create policy "anon full access" on sessions for all using (true) with check (true);
create policy "anon full access" on mapping for all using (true) with check (true);
create policy "anon full access" on deleted_sessions for all using (true) with check (true);
create policy "anon full access" on notes for all using (true) with check (true);
create policy "anon full access" on work_calendar for all using (true) with check (true);
create policy "anon full access" on reading_log for all using (true) with check (true);
create policy "anon full access" on settings for all using (true) with check (true);

-- Cho phép gọi append_note_bullet() qua REST API bằng anon key (giống mọi bảng ở trên) --
-- hàm chạy dưới quyền người GỌI (mặc định, không security definer), nên vẫn cần policy "anon
-- full access" trên notes ở trên để tự đọc/ghi được bên trong hàm.
grant execute on function append_note_bullet(date, text) to anon;

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
