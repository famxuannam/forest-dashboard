# Kiểm thử: không có test suite, dùng harness giả lập

Đối tượng đọc: AI agent cần xác minh 1 thay đổi có chạy đúng không, trong môi trường sandbox thường
KHÔNG có mạng ra `*.supabase.co` hay `caldav.icloud.com`.

Không có bước build/lint/test tự động nào trong repo. Quy trình xác minh thay đổi là chạy *chính*
`app.py` thật với 1 Supabase giả lập, rồi lái bằng Playwright.

## Bước 1: tạo scratch app với `_get_supabase()` giả

Copy `app.py` sang 1 file scratch (không commit), rồi thay nội dung hàm `_get_supabase()` (giữ
nguyên decorator `@st.cache_resource` để state giả lập tồn tại xuyên suốt các lần rerun trong 1
session) bằng 1 client giả trong bộ nhớ, hỗ trợ đúng các method thật đang được gọi trong `app.py`:

- `.table(name).select(...).execute()` → trả `.data` là list dict.
- `.table(name).insert(recs)`/`.upsert(recs, on_conflict=...)` → PHẢI trả về 1 object có
  `.execute()` (supabase-py trả builder, gọi `.execute()` mới thật sự chạy) — lỗi hay gặp nhất khi
  viết fake là quên bước này, khiến `AttributeError: '...' object has no attribute 'execute'`.
- `.table(name).delete().not_.is_(col, "null").execute()` → xoá toàn bảng (dùng bởi
  `_sb_delete_all()`).
- `.table(name).delete().gte(col, a).lt(col, b).execute()` → xoá theo khoảng (dùng bởi
  `sync_work_calendar()`).
- `.storage.from_(bucket).list()/.download(name)/.remove([names])` — nếu đang test tính năng
  "Đồng bộ nhanh" (xem `data-layer.md`), cần fake luôn phần Storage, không chỉ `.table()`.

Nếu tính năng đang sửa dùng CalDAV, monkeypatch thêm `_get_caldav_client()`.

Chạy `streamlit run <scratch>.py` từ **thư mục gốc repo** (không phải từ thư mục scratch khác) —
`app.py` load asset bằng đường dẫn tương đối (`assets/...`), chạy sai cwd sẽ crash ngay khi vẽ logo,
che mất lỗi thật đang muốn tìm.

## Bước 2: chạy + lái bằng Playwright

```bash
streamlit run <scratch>.py --server.port <N> --server.headless true
```
chạy nền, rồi dùng Playwright (`p.chromium.launch(executable_path='/opt/pw-browsers/chromium')`)
để: (a) quét `"Traceback" not in page.inner_text('body')` ở mọi trang nav chính như 1 phép hồi quy
nhanh; (b) kiểm tra cụ thể thay đổi đang làm (bounding box, style tính toán, text hiển thị, click
nút rồi đọc lại state).

Regenerate scratch harness mới mỗi phiên làm việc — không giả định 1 file scratch từ phiên trước
còn tồn tại hay còn đúng, vì nó không được commit vào repo.

## Bước 3: với logic nhiều nhánh, viết thêm 1 script Python thuần

Với bất kỳ hàm nào có hơn 2-3 nhánh logic (so sánh ngày tháng, chọn template, parse CSV), viết 1
script ngắn import/exec thẳng hàm đó với `pandas` DataFrame giả — nhanh hơn nhiều so với vòng qua
Streamlit + Playwright cho lỗi logic thuần, không liên quan UI.

## Dọn dẹp bắt buộc trước khi commit

Xoá mọi file scratch (`scratch_app.py`, `.streamlit/secrets.toml` giả, `database.csv`,
`mapping.csv`, `notes.csv`, `__pycache__`, screenshot test) — đây là sản phẩm phụ của quá trình
test cục bộ, không phải output của app, không được lẫn vào commit.
