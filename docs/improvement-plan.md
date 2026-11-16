# Kế hoạch cải tiến Forest Dashboard (11/2026)

Đối tượng đọc: model thực thi (Claude Code). Mỗi **Giai đoạn** là một PR riêng, làm theo đúng thứ
tự, không gộp. Số dòng trong file này tính theo commit `fcc8975`; luôn `grep` lại trước khi sửa.

Quy tắc chung cho mọi giai đoạn:

- Đọc `CLAUDE.md` và tài liệu `docs/` đúng phạm vi trước khi sửa. Không refactor ngoài phạm vi.
- Sau mỗi thay đổi `app.py`: `python3 -c "import ast; ast.parse(open('app.py').read())"`.
- Kiểm tra hồi quy bằng app thật với dữ liệu mẫu:
  `FOREST_LOCAL_DEV=1 python3 -W default -m streamlit run app.py --server.address localhost --server.headless true`
  rồi dùng Playwright mở cả 11 trang (`?nav=` Hôm nay, Báo cáo + `&sub=` Tổng quan/Tuần/Tháng/Năm/Dự
  án, Nhật ký đọc sách, Gundam, Tìm kiếm, Tuỳ biến + `&tsub=` Tổng quan/Giao diện). Điều kiện đạt:
  không trang nào có "Traceback", log server không còn cảnh báo mà giai đoạn đó nhắm tới.
- `local_dev_data.py` (`LocalDevSupabase`) phải được bổ sung mọi method Supabase mới dùng tới, nếu
  không chế độ local sẽ hỏng.
- Cập nhật tài liệu `docs/` tương ứng trong cùng PR. Không commit file scratch.
- Không tự merge PR. Dừng lại báo cáo sau mỗi giai đoạn.

Bối cảnh đã xác nhận với người dùng: làm tất cả nhóm A–D; đăng nhập Google **đang bật**; **không**
làm sao lưu tự động; hai bảng cũ `quick_notes`, `health_metrics` đã được xoá khỏi Supabase.

## Trạng thái (16/11/2026)

| Giai đoạn | Trạng thái |
|---|---|
| 1. Dọn cảnh báo, ghim phiên bản | Xong |
| 2. Thay `st.components.v1.html` | Xong (`_inject_js()` dùng `st.iframe`) |
| 3. An toàn dữ liệu | Xong (+ 8 test) |
| 4. Test, CI, keepalive | Xong; hàm `keepalive()` đã tạo trên Supabase. **Chờ người dùng** thêm secret `SUPABASE_URL`, `SUPABASE_ANON_KEY` vào GitHub |
| 5. Bảo mật Supabase | Code/schema/docs xong. **Chờ người dùng** đổi `SUPABASE_KEY` sang khoá bí mật; sau đó mới áp migration bỏ policy anon (SQL ở cuối file này) |
| 6. U1, U2, U3, O2, F1, F4 | Xong. Thêm: lịch chọn ngày tiếng Việt, Thứ Hai đầu tuần (bộ dịch cũ đã hỏng từ Streamlit 1.67) |
| 6. O1, F2, F3 | Chưa làm (xem lý do trong mục Giai đoạn 6) |

---

## Giai đoạn 1 — Dọn cảnh báo và ghim phiên bản (rủi ro thấp)

1. `import_parsers.py:140`: docstring chứa `\`` gây `SyntaxWarning: invalid escape sequence`. Đổi
   docstring đó thành raw string (`r"""..."""`) hoặc viết lại ký tự, không đổi logic.
2. `app.py:4488`, `app.py:4653`: `Timestamp.dayofweek` → `day_of_week` (pandas 4 sẽ gỡ).
3. 13 chỗ `use_container_width=True` (dòng 1731, 1736, 1740, 1794, 1801, 7373, 9855, 10638, 10680,
   10687, 11540, 11895; dòng 9266 chỉ là chú thích) → `width="stretch"`. Kiểm tra bằng mắt các nút
   ◀ ▶ ở `period_stepper`/`day_picker` và lưới chọn ở Tuỳ biến → Giao diện vẫn rộng như cũ.
4. `requirements.txt`: thu hẹp dải phiên bản về đúng bản đang chạy tốt trên Streamlit Cloud
   (log deploy 16/11/2026: streamlit 1.67.0, pandas 3.1.1, plotly 6.9.0, altair 6.3.0,
   streamlit-quill 0.0.3, supabase 2.34.1, caldav 3.7.0, Authlib 1.9.6, Python 3.14). Dùng dải
   theo bản vá, ví dụ `streamlit>=1.67,<1.68`, `supabase>=2.34,<2.35`; riêng pandas dùng
   `>=3.0,<3.2` (máy Python 3.13 chỉ cài được 3.0.x). Thêm `pyarrow>=24,<25` vì Streamlit Cloud
   đang phải tự hạ pyarrow 26.0.1 do lỗi segfault. Xác minh `pip install -r requirements.txt` sạch.

Đạt khi: log khởi động không còn `SyntaxWarning`, `Pandas4Warning`.

## Giai đoạn 2 — Thay `st.components.v1.html` (bắt buộc, đã quá hạn gỡ bỏ)

Streamlit 1.67 cảnh báo: "`st.components.v1.html` will be removed after 2026-06-01. Please replace
with `st.iframe`". Có 8 lời gọi, tất cả là tiêm JS với `height=0`, đều thao tác trên
`window.parent.document`: dòng 113 (`style_quill`), 1477 (`_render_nav_sync_fab`), 1868
(`_inject_relative_time_ticker`), 1985 (`_inject_date_picker_locale`), 10095
(`_inject_keyboard_shortcuts`), 10140 (`_inject_reading_calendar_tap_tip`), 10203
(`_inject_note_editor_shortcuts`), 10254 (`_inject_scroll_to_top_button`).

Cách làm:

1. Tạo MỘT helper `_inject_js(html)` trong `app.py` và cho cả 8 nơi gọi qua nó.
2. Trong helper, ưu tiên `st.iframe(html, height=<nhỏ nhất được phép>)`: docstring của `st.iframe`
   (1.67) xác nhận chuỗi HTML được nhúng trong iframe "allows JavaScript execution and same-origin
   access to the Streamlit app", tức `window.parent` vẫn dùng được. Tự kiểm tra `height=0` có được
   chấp nhận không; nếu không, dùng `height=1` và ẩn bằng CSS.
3. Khối CSS quanh dòng 7666 đang ẩn khung chứa iframe của `components.html(height=0)`. Kiểm tra
   `data-testid`/class của phần tử `st.iframe` trong DOM và cập nhật selector để không để lại
   khoảng trống trên trang.
4. Phương án dự phòng nếu `st.iframe` không dùng được: `st.html(html, unsafe_allow_javascript=True)`
   (không có iframe, khi đó `window.parent === window` nên script vẫn chạy). Lưu ý script có thể
   không chạy lại ở rerun nếu nội dung không đổi; phải thử kỹ nút đồng bộ nổi.
5. Bỏ `import streamlit.components.v1 as components` nếu không còn dùng. Kiểm tra log xem
   `streamlit_quill` (component bên thứ ba) có cảnh báo gỡ bỏ nào không; nếu có, chỉ báo cáo.

Kiểm tra bằng Playwright (bắt buộc từng mục): phím tắt chuyển trang và ←/→ đổi ngày; bảng phím
tắt; nút "Về đầu trang" xuất hiện khi cuộn; nút đồng bộ nổi ẩn/hiện đúng; ô chọn ngày hiển thị
tiếng Việt; nhãn thời gian tương đối tự cập nhật; phím tắt trong ô ghi chú và toolbar Quill đúng
style; tip khi chạm lịch đọc sách. Log không còn dòng `st.components.v1.html`.
Cập nhật `docs/keyboard-shortcuts.md` và các docstring nhắc tới `components.html`.

## Giai đoạn 3 — An toàn dữ liệu

### 3a. Bỏ kiểu ghi "xoá sạch rồi chèn lại" ở luồng thường ngày

Hiện `save_db()` (dòng 543) xoá toàn bộ `sessions` rồi chèn lại theo lô 500; được gọi ở mỗi lần
đồng bộ (`_merge_forest_into_db`, kể cả tự đồng bộ khi mở app) và khi xoá phiên (dòng 12150). Lỗi
mạng giữa chừng làm mất dữ liệu. `grep -n "save_db(\|save_mapping(\|save_reading_log_bulk("` để
liệt kê mọi nơi gọi trước khi sửa.

- `_merge_forest_into_db(df_new)`: chỉ chèn dòng mới bằng
  `upsert(recs, on_conflict="start_time,end_time", ignore_duplicates=True)` theo lô 500, không xoá
  gì. Số trả về = số khoá của `df_new` chưa có trong `load_db()`. Sau đó `load_db.clear()` +
  `prep_analysis_data.clear()`.
- Thêm `delete_sessions(keys_df)`: xoá đúng từng phiên theo `(start_time, end_time)` (đã `_fmt_ts`).
  Nút "Xoá N phiên đã chọn" gọi `add_deleted()` trước, rồi `delete_sessions()`.
- `save_db()` chỉ còn dùng cho Khôi phục; ghi rõ trong docstring.
- `save_mapping(df)`: upsert theo `project` trước, sau đó mới xoá các `project` không còn trong `df`.
- `save_reading_log_bulk(df)` (thay thế toàn bộ theo thiết kế): chèn bộ mới TRƯỚC với tiền tố uid
  mới (vd `r<epoch>-<i>`, vẫn kết thúc bằng số thứ tự vì `load_reading_log()` sắp theo `(\d+)$`),
  chèn xong mới xoá các dòng uid không mang tiền tố đó.

### 3b. Khôi phục từ bản sao lưu (dòng 11956–11995)

Đọc và kiểm tra TẤT CẢ file CSV trong .zip thành DataFrame trước (thiếu cột → báo lỗi, chưa xoá
gì), sau đó mới ghi. Bọc phần ghi trong `try/except`: nếu lỗi, `st.cache_data.clear()` và hiện
`st.error` nói rõ bảng nào đang ghi dở và đề nghị chạy lại Khôi phục với cùng file.

### 3c. Lỗi kết nối Supabase

- `_sb_select_all()` (dòng 474): thử lại tối đa 2 lần (chờ 1s, 2s) khi `.execute()` ném lỗi.
- Quanh `_auto_sync_on_open()` / `df = prep_analysis_data()` (dòng 9386–9387): bắt Exception, hiện
  thẻ lỗi ngắn tiếng Việt ("Không kết nối được cơ sở dữ liệu. Project Supabase có thể đang tạm dừng
  hoặc khởi động lại."), chi tiết lỗi rút gọn trong expander, nút "Thử lại" (xoá cache rồi
  `st.rerun()`), rồi `st.stop()`. Không in traceback.
- Lỗi thật: `load_settings()` (dòng 289) nuốt lỗi và trả `{}`, còn `_cached_settings()` cache luôn
  kết quả rỗng đó vô thời hạn, nên nếu Supabase lỗi đúng lúc khởi động thì giao diện rơi về mặc
  định cho tới khi cache bị xoá. Sửa để không cache kết quả lỗi (để lỗi ném ra trong hàm có cache,
  bắt ở lớp ngoài và trả `{}` không cache).

Kiểm tra: viết script Python thuần với client giả ném lỗi ở lần chèn thứ 2 để chứng minh dữ liệu cũ
còn nguyên; thử tắt/bật lỗi trong `LocalDevSupabase` để xem thẻ lỗi và nút Thử lại.
Cập nhật `docs/data-layer.md` (bảng load/save và mô tả `_merge_forest_into_db`).

## Giai đoạn 4 — Vận hành tự động

1. **Test + CI**: thêm `requirements-dev.txt` (`pytest`), thư mục `tests/`:
   - test cho 4 parser trong `import_parsers.py` với dữ liệu mẫu nhỏ nhúng trong test;
   - test khói bằng `streamlit.testing.v1.AppTest.from_file("app.py", default_timeout=60)` với
     `FOREST_LOCAL_DEV=1`, chạy qua từng `nav`/`sub`, khẳng định `not at.exception`.
   - `.github/workflows/ci.yml` chạy trên PR và push `main`: cài đặt, `ast.parse`,
     `python -W error -c "import import_parsers, ui_catalog, local_dev_data"`, `pytest`.
   Cập nhật `CLAUDE.md` và `docs/testing.md` (hiện ghi "không có test suite").
2. **Chống Supabase tạm dừng** (gói Free tạm dừng sau ~7 ngày ít hoạt động):
   `.github/workflows/keepalive.yml`, cron 2 lần/tuần, gọi `POST $SUPABASE_URL/rest/v1/rpc/keepalive`
   bằng khoá publishable/anon lấy từ GitHub Secrets (`SUPABASE_URL`, `SUPABASE_ANON_KEY`). Hàm
   `public.keepalive()` (trả `1`, cấp `execute` cho `anon`) được tạo ở Giai đoạn 5 và ghi vào
   `supabase_schema.sql`. Ghi chú trong README: GitHub tự tắt workflow theo lịch nếu repo công khai
   không có hoạt động 60 ngày. Người dùng phải tự thêm 2 secret vào repo.

## Giai đoạn 5 — Bảo mật Supabase (cần người dùng thao tác, làm theo đúng thứ tự)

Hiện trạng: mọi bảng có policy "anon full access" (`for all using (true)`), app và Shortcut iOS
dùng chung khoá anon. Mục tiêu: app dùng khoá bí mật phía server; khoá anon chỉ còn tải file lên
bucket `sync-uploads` và gọi `keepalive()`.

1. Người dùng: Supabase Dashboard → Settings → API Keys → tạo/lấy **secret key** (`sb_secret_…`;
   nếu `supabase-py` 2.34 không nhận thì dùng khoá `service_role` cũ — model thực thi kiểm tra tài
   liệu hiện hành trước khi hướng dẫn). Dán vào `SUPABASE_KEY` trong Streamlit Cloud → Settings →
   Secrets, Reboot app, xác nhận app chạy bình thường. **Chưa đổi gì ở database trước bước này.**
2. Sau khi người dùng xác nhận bước 1, áp một migration:
   - `drop policy "anon full access" on <bảng>` cho cả 12 bảng (RLS vẫn bật, không policy = anon
     bị chặn; secret key bỏ qua RLS);
   - thay policy Storage bằng INSERT-only:
     `create policy "anon upload sync-uploads" on storage.objects for insert to anon with check (bucket_id = 'sync-uploads');`
   - tạo `public.keepalive()` như Giai đoạn 4.
3. Người dùng chạy Shortcut iOS một lần để xác nhận vẫn tải file lên được (nếu Shortcut dùng chế
   độ ghi đè `x-upsert` thì cần thêm quyền; tên file có timestamp nên thường không cần). Mở app,
   xác nhận tự đồng bộ nạp được file mới.
4. Cập nhật `supabase_schema.sql`, `.streamlit/secrets.toml.example`, `README.md`,
   `docs/data-layer.md` cho đúng mô hình quyền mới. Chạy lại security advisor của Supabase.

## Giai đoạn 6 — Giao diện, tính năng, tối ưu (CHỜ người dùng chọn mục, chưa làm)

Giao diện (lỗi nhìn thấy khi chạy thử):
- U1. Toast "Huy hiệu mới" (`_toast_today_milestones`, dòng 3017) chỉ chặn lặp theo session, nên
  hiện lại ở mỗi lần tải trang trong ngày và che mục lục/ô chọn ngày. Lưu huy hiệu đã báo vào
  `settings` để mỗi huy hiệu chỉ báo một lần.
- U2. Ô chọn ngày trang Hôm nay bị cắt chữ ("16 / 11 / 2…"), do `width: 170px` ở dòng 8505.
- U3. Trên điện thoại, billboard trang Hôm nay (trích dẫn + 6 mục lục xếp dọc) chiếm trọn màn hình
  đầu; đổi mục lục thành một hàng chip cuộn ngang ở màn hình hẹp.

Tối ưu:
- O1. 18 link nội bộ `target="_self"` tải lại cả trang và mở session mới (~2,5 giây, tải lại
  ~690KB). Thử nghiệm điều hướng không tải lại (JS chặn click → chuyển tín hiệu về Python). Cần
  làm bản thử trước, rủi ro trung bình.
- O2. Lần tải đầu ~690KB, phần lớn là font nhúng base64 trong CSS nên trình duyệt không cache
  được. Chuyển font sang phục vụ dạng file tĩnh (static serving / `[[theme.fontFaces]]`).
  Các lần rerun chỉ ~60KB, không cần tối ưu thêm.

Tính năng (giữ đúng tinh thần hồi cứu):
- F1. Thẻ "Tình trạng dữ liệu" ở Tuỳ biến: lần đồng bộ cuối, số dòng từng bảng, cảnh báo khi file
  Forest mới nhất đã cũ.
- F2. So sánh hai kỳ bất kỳ (tuần/tháng) đặt cạnh nhau.
- F3. Trang tổng kết năm dạng một màn hình, xuất được thành ảnh.
- F4. Xuất toàn bộ nhật ký ra Markdown để lưu trữ ngoài app.

### Ghi chú sau khi làm

- O1 (điều hướng không tải lại trang) chưa làm: Streamlit không có API để JS đổi trang mà không mở
  session mới; cách khả thi duy nhất là JS điền vào 1 widget ẩn để kích hoạt rerun, dễ vỡ khi
  Streamlit đổi markup. Sau O2, mỗi lần tải lại chỉ còn ~210KB thay vì ~690KB nên lợi ích còn lại nhỏ.
- F2 (so sánh 2 kỳ) và F3 (tổng kết năm dạng 1 màn hình) là tính năng giao diện mới, cần người dùng
  chọn bố cục/nội dung trước khi làm.

## Migration Giai đoạn 5 (chỉ chạy SAU KHI app đã chạy được với khoá bí mật)

```sql
drop policy if exists "anon full access" on sessions;
drop policy if exists "anon full access" on mapping;
drop policy if exists "anon full access" on deleted_sessions;
drop policy if exists "anon full access" on notes;
drop policy if exists "anon full access" on work_calendar;
drop policy if exists "anon full access" on reading_log;
drop policy if exists "anon full access" on settings;
drop policy if exists "anon full access" on kindle_highlights;
drop policy if exists "anon full access" on kindle_book_map;
drop policy if exists "anon full access" on deleted_kindle_highlights;
drop policy if exists "anon full access" on gundam_overrides;
drop policy if exists "anon full access" on book_overrides;
drop policy if exists "anon full access sync-uploads" on storage.objects;
create policy "anon upload sync-uploads" on storage.objects for insert to anon
  with check (bucket_id = 'sync-uploads');
```

Hoàn tác (nếu Shortcut/app lỗi): tạo lại các policy `"anon full access" ... for all using (true)
with check (true)` như trong `supabase_schema.sql` ở commit `fcc8975`.
