# CLAUDE.md

Tài liệu định hướng cho AI agent làm việc trên mã nguồn Forest Dashboard. File này là **mục lục
tầng cao** — chi tiết kỹ thuật chuyên sâu nằm trong `.claude/docs/` (xem mục 6), không lặp lại ở
đây. Nếu bạn chưa từng thấy codebase này, đọc hết file này trước, rồi mở đúng file doc liên quan
tới việc đang làm trước khi sửa code.

## 1. Tổng quan dự án

Forest Dashboard là dashboard Streamlit cá nhân (single-user, giao diện tiếng Việt), trực quan hoá
dữ liệu phiên tập trung xuất từ app **Forest**, cộng 2 nguồn phụ tuỳ chọn: lịch hẹn công việc (qua
CalDAV/iCloud) và tiến độ đọc sách/xem phim (qua file Apple Reminders xuất bằng Shortcuts). Ứng
dụng thuần hồi cứu (retrospective) — không có tính năng đặt mục tiêu hay nhắc nhở, chỉ hiển thị lại
dữ liệu Forest đã ghi nhận.

## 2. Tech Stack

- Python 3.11+ (repo không pin version cụ thể).
- Streamlit `>=1.58,<2` — toàn bộ UI + server nằm gọn trong `app.py`, không có frontend riêng.
- Supabase (Postgres) qua `supabase-py>=2,<3` — nơi lưu trữ dữ liệu **duy nhất**, không có chế độ
  CSV cục bộ.
- `pandas>=2.2,<4` xử lý dữ liệu; `plotly>=6,<7` + `altair>=5,<7` vẽ biểu đồ.
- `streamlit-quill` cho ô ghi chú rich-text; `Authlib>=1.3.2,<2` cho đăng nhập Google (tuỳ chọn);
  `caldav>=3,<4` cho đồng bộ lịch Work qua CalDAV (tuỳ chọn).
- Không có bundler/transpiler/build step nào — `streamlit run app.py` là toàn bộ quy trình chạy.

## 3. Lệnh phát triển

```bash
# Cài dependency
pip install -r requirements.txt

# Kiểm tra cú pháp sau MỌI lần sửa app.py — rẻ, bắt lỗi gõ nhầm trước khi chạy thật
python3 -c "import ast; ast.parse(open('app.py').read())"

# Chạy app dev (cần .streamlit/secrets.toml điền SUPABASE_URL/SUPABASE_KEY, xem secrets.toml.example)
streamlit run app.py
```

Không có bước build production riêng biệt, không có linter/test suite trong repo. Sandbox thường
không có mạng ra Supabase/iCloud thật — quy trình kiểm thử bằng harness giả lập được mô tả chi tiết
ở [`.claude/docs/testing.md`](.claude/docs/testing.md).

## 4. Tóm tắt Logic cốt lõi

Codebase này **không có** nghiệp vụ tính trọng số (weight calculation) nào tồn tại — mọi kết quả
tìm được cho từ khoá "weight" trong `app.py` chỉ là CSS `font-weight`. Phép tính nghiệp vụ trung
tâm thực tế là **gộp thời lượng phiên theo kỳ**: `prep_analysis_data()` là điểm nối dữ liệu duy
nhất, join `sessions` với `mapping` (Dự án → Danh mục), sinh thêm cột kỳ (`Tuần`/`Tháng`/`Năm`/
`Thứ`) từ cột giờ bắt đầu. Mọi trang báo cáo (Tổng quan/Tuần/Tháng/Năm/Dự án) đọc từ DataFrame này
rồi `groupby` + `sum()` cột `Thời lượng (Phút)` theo Dự án/Danh mục/kỳ. Chi tiết đầy đủ (bao gồm
timezone và luồng đồng bộ dữ liệu) ở [`.claude/docs/data-layer.md`](.claude/docs/data-layer.md).

## 5. Ràng buộc trọng yếu

Các quy tắc dưới đây là bất biến của dự án — **không tự ý thay đổi hay giả định khác đi** khi chưa
xác nhận với người dùng:

- **Kiến trúc 1 file**: toàn bộ app nằm trong `app.py` (~7800 dòng). Không tách frontend/backend,
  không tạo module component riêng — đây là quyết định kiến trúc đã chốt, không phải nợ kỹ thuật
  cần dọn.
- **Giờ luôn qua `_today_vn()`**, không bao giờ `date.today()` trần — server có thể chạy UTC, lệch
  7 tiếng so với giờ Việt Nam đã từng gây bug thật đã ghi nhận.
- **Supabase là nơi lưu trữ dữ liệu duy nhất**: không thêm chế độ CSV cục bộ. Mọi bảng/bucket mới
  bắt buộc có cặp `load_*()`/`save_*()` tương ứng **và** cập nhật `supabase_schema.sql` (nguồn
  chân lý schema duy nhất).
- **`st.metric` bị ẩn toàn cục bằng CSS** (`[data-testid="stMetric"] { display: none; }`) — dùng
  widget này sẽ render ra khoảng trắng vô hình, không có lỗi hay warning nào cảnh báo. Không dùng
  `st.metric()`; xem cách thay thế ở
  [`.claude/docs/ui-components.md`](.claude/docs/ui-components.md).
- **Khối CSS chính là string thường, không phải f-string** — không tự ý đổi kiểu (hàng trăm dấu
  `{`/`}` literal trong CSS sẽ vỡ cú pháp Python).
- **Không tự ý mở hoặc merge Pull Request** khi chưa được yêu cầu rõ ràng — commit + push lên
  nhánh làm việc được giao rồi dừng lại chờ xác nhận.
- **Tab "Hướng dẫn" là nội dung cho người dùng cuối, không phải code phụ trợ** — không viết lại nội
  dung tab này như tác dụng phụ của 1 thay đổi không liên quan tới trải nghiệm người dùng.

## 6. Tài liệu bổ sung

- [`.claude/docs/architecture-navigation.md`](.claude/docs/architecture-navigation.md) — dispatch
  trang theo `st.query_params`, cấu trúc `NAV`/`BAOCAO_SUBS`, `day_picker()`.
- [`.claude/docs/data-layer.md`](.claude/docs/data-layer.md) — cặp `load_*`/`save_*` từng bảng,
  timezone, `prep_analysis_data()`, luồng "Đồng bộ nhanh" qua Supabase Storage.
- [`.claude/docs/theming.md`](.claude/docs/theming.md) — CSS custom properties, `IS_DARK`, cách
  màu accent lan sang biểu đồ và iframe ghi chú.
- [`.claude/docs/ui-components.md`](.claude/docs/ui-components.md) — quy ước `st.expander` đánh
  số, `render_stat_panel()`, bẫy `st.metric`, bộ helper `help_*` của trang Trợ giúp.
- [`.claude/docs/keyboard-shortcuts.md`](.claude/docs/keyboard-shortcuts.md) — blob JS phím tắt
  toàn cục và phím tắt riêng trong iframe ghi chú.
- [`.claude/docs/testing.md`](.claude/docs/testing.md) — harness giả lập Supabase + Playwright để
  kiểm thử không cần mạng thật.
- [`.claude/docs/git-workflow.md`](.claude/docs/git-workflow.md) — nhánh làm việc theo phiên, quy
  trình PR squash-merge, cách làm sạch nhánh sau mỗi lần merge.
