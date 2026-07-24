# Kiểm thử: không có test suite, dùng harness giả lập

Đối tượng đọc: Claude Code cần xác minh 1 thay đổi có chạy đúng không, trong môi trường sandbox thường
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

**5 lỗi hay gặp khi dựng/dùng harness:**
- `streamlit`/`playwright` KHÔNG có sẵn trong sandbox trần dù `python3` có sẵn -- `pip install -r
  requirements.txt` rồi `pip install playwright` trước, đừng giả định môi trường đã cài sẵn. Có thể
  gặp lỗi uninstall `PyJWT` do Debian quản lý (`RECORD file not found`) -- thêm cờ `--ignore-installed
  pyjwt` vào lệnh `pip install -r requirements.txt` là qua.
- `@st.cache_data` trên các hàm `load_*()` cache theo TIẾN TRÌNH streamlit, không theo session/
  browser tab -- nếu sửa dữ liệu giả lập (thêm bảng mới vào `_FAKE_STORE`, sửa file fixture JSON)
  SAU KHI đã gọi qua hàm đó ít nhất 1 lần trong tiến trình đang chạy, kết quả cũ vẫn bị trả về dù
  mở tab mới/reload trang -- phải `pkill` + chạy lại `streamlit run` (tiến trình mới, cache trống)
  chứ sửa fixture xong reload trang KHÔNG đủ.
- Chạy `streamlit run` bằng `nohup ... & disown` lồng trong 1 lời gọi Bash duy nhất KHÔNG đáng tin
  — process có thể bị dọn ngay khi lời gọi đó trả về, trước cả khi server kịp sẵn sàng. Luôn chạy
  bằng tham số nền riêng của tool Bash (`run_in_background: true`) thành 1 lời gọi tách biệt, rồi
  `curl` kiểm tra ở 1 lời gọi SAU đó.
- `pkill -f "streamlit run <scratch>.py"` để dọn dẹp LUÔN kèm 1 thông báo nền dạng "failed with
  exit code 144" cho tiến trình streamlit vừa bị kill — đây là HỆ QUẢ ĐÚNG DỰ KIẾN của chính lệnh
  pkill đó (128+16=144, SIGTERM), không phải lỗi thật, không cần điều tra thêm.
- Screenshot `full_page=True` của 1 trang RẤT DÀI (nhiều chương) có thể bị CẮT NGANG đúng bằng
  chiều cao viewport đã set — Streamlit render nội dung trong 1 container cuộn riêng, không phải
  cuộn `<body>` bình thường, nên Playwright không tự "cuộn hết rồi chụp" được như trang web thường.
  Set `viewport height` đủ lớn (vd 2600-3200px) để chứa hết nội dung thay vì dựa vào `full_page`.

## Bước 3: với logic nhiều nhánh, viết thêm 1 script Python thuần

Với bất kỳ hàm nào có hơn 2-3 nhánh logic (so sánh ngày tháng, chọn template, parse CSV), viết 1
script ngắn import/exec thẳng hàm đó với `pandas` DataFrame giả — nhanh hơn nhiều so với vòng qua
Streamlit + Playwright cho lỗi logic thuần, không liên quan UI.

## Dọn dẹp bắt buộc trước khi commit

Xoá mọi file scratch (`scratch_app.py`, `.streamlit/secrets.toml` giả, `database.csv`,
`mapping.csv`, `notes.csv`, `__pycache__`, screenshot test) — đây là sản phẩm phụ của quá trình
test cục bộ, không phải output của app, không được lẫn vào commit.
