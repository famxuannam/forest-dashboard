# Forest Dashboard — hướng dẫn cho Codex/ChatGPT

Đây là tài liệu định hướng cho Codex/ChatGPT làm việc trong repository Forest Dashboard. Repository
là nguồn chân lý: trước khi sửa, đọc phần code liên quan và tài liệu trong `docs/`; chỉ dùng best
practice bên ngoài khi repository không quy định.

## Tổng quan và cách chạy

Forest Dashboard là dashboard Streamlit cá nhân, giao diện tiếng Việt, để xem lại dữ liệu phiên tập
trung từ Forest. Nguồn phụ, đều tuỳ chọn, là lịch Work qua CalDAV/iCloud và tiến độ đọc sách/xem
Gundam từ Apple Reminders. Ứng dụng chỉ hồi cứu dữ liệu, không đặt mục tiêu hay nhắc nhở.

```bash
pip install -r requirements.txt
python3 -c "import ast; ast.parse(open('app.py').read())"
streamlit run app.py
```

`SUPABASE_URL` và `SUPABASE_KEY` là secrets bắt buộc; xem `.streamlit/secrets.toml.example`.
Không có build step, linter hay test suite tự động. Xem `docs/testing.md` khi cần kiểm tra UI/logic
mà không kết nối dịch vụ thật.

## Kiến trúc và ràng buộc

- Toàn bộ ứng dụng nằm trong `app.py`. Không tách frontend/backend hay tạo module component riêng
  trừ khi người dùng yêu cầu rõ ràng; đây là quyết định kiến trúc, không phải technical debt cần tự
  dọn.
- Supabase là nơi lưu trữ duy nhất. Khi thêm bảng hoặc bucket, thêm loader/saver hoặc sync tương ứng,
  cập nhật `supabase_schema.sql`, và rà soát luồng sao lưu/khôi phục/xoá toàn bộ.
- Mọi logic về “hôm nay” dùng `_today_vn()`, không dùng `date.today()` trần.
- Không dùng `st.metric()` vì CSS toàn cục ẩn nó. Khối CSS lớn là string thường, không đổi thành
  f-string.
- `prep_analysis_data()` là điểm chuẩn bị dữ liệu báo cáo trung tâm. Giữ `Dự án gốc`; chỉ dùng dữ
  liệu đã chuẩn bị để báo cáo/gom nhóm, trừ khi có lý do rõ ràng.
- `_health_is_abnormal()` chỉ có hai trạng thái trong/ngoài khoảng tham chiếu. Không tự thêm mức
  “sát ngưỡng”.
- Tab `Hướng dẫn` là nội dung người dùng cuối: chỉ cập nhật khi thay đổi có tác động tới cách dùng app.

## Cách làm việc

Với mỗi task: xác định yêu cầu và file liên quan, đọc code/tài liệu đúng scope, nêu kế hoạch ngắn
nếu thay đổi không hiển nhiên, sửa trong phạm vi nhỏ nhất, kiểm tra ảnh hưởng và chạy kiểm tra phù
hợp. Không refactor, đổi style, thêm dependency, hay thay đổi kiến trúc ngoài yêu cầu. Nếu yêu cầu
thật sự mơ hồ và lựa chọn làm thay đổi hành vi, nêu các phương án/trade-off và hỏi trước.

Sau thay đổi `app.py`, luôn chạy kiểm tra cú pháp ở trên. Với thay đổi lớn hơn, xem hướng dẫn harness
giả lập/Playwright trong `docs/testing.md`. Không tự commit, push, mở hoặc merge PR trừ khi người
dùng yêu cầu rõ ràng; xem `docs/git-workflow.md` khi được giao thao tác GitHub.

## Quy ước chính

- Tên bảng/cột Supabase dùng tiếng Anh `snake_case`; DataFrame hiển thị trong app dùng cột tiếng Việt.
- Hàm tầng dữ liệu theo `load_*`, `save_*`, `sync_*`, `delete_*`, `update_*`.
- Loader thường có `@st.cache_data`. Sau ghi dữ liệu, chỉ clear loader/analysis phụ thuộc trực tiếp;
  chỉ Khôi phục và Xoá toàn bộ dữ liệu được clear cache toàn cục.
- Navigation dùng `NAV` + chuỗi dispatch `if/elif`; thứ tự key trong `NAV` là thứ tự hiển thị. State
  và deep-link dùng `st.session_state` cùng `st.query_params`, không tự gán widget state sau khi
  widget đã khởi tạo.
- Thứ tự nội dung các trang báo cáo: Tổng quan → Lịch tháng (nếu có) → Phân bổ → Xu hướng → Nhật
  ký/ghi chú → Bảng số liệu. Bảng số liệu luôn là phần cuối.

## Tài liệu theo phạm vi

- `docs/architecture-navigation.md`: navigation, deep-link, nút Quay lại và `day_picker()`.
- `docs/data-layer.md`: tất cả bảng Supabase, cache, timezone, import/đồng bộ.
- `docs/theming.md`: theme, accent, CSS và biểu đồ.
- `docs/ui-components.md`: chapter layout, bảng, billboard và helpers UI.
- `docs/keyboard-shortcuts.md`: phím tắt JavaScript và iframe ghi chú.
- `docs/testing.md`: kiểm tra bằng fake Supabase/Playwright.
- `docs/git-workflow.md`: quy tắc branch, commit, push và PR.
