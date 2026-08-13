# Điều hướng & dispatch trang

Đối tượng đọc: Claude Code chưa từng thấy `app.py`, cần biết cách 1 lượt click nav biến thành 1 trang
render ra sao, và cách thêm/sửa 1 trang mà không phá deep-link.

## Cơ chế: 1 dict + 1 chuỗi if/elif, không router riêng

- `NAV` là dict phẳng `{"Tên trang": "material_icon_name", ...}`, render bằng
  `st.segmented_control`. Đây là toàn bộ "route table" của app — không có class Route, không có
  framework điều hướng nào khác.
- Trang thực sự được vẽ bởi 1 chuỗi `if nav == "Hôm nay": ... elif nav == "Báo cáo": ...` nằm gần
  cuối `app.py`. Đây KHÔNG phải chỗ quyết định thứ tự hiển thị trên thanh nav — thứ tự đó do vị trí
  key trong dict `NAV` quyết định. Khi thêm 1 trang mới: thêm key vào `NAV` ở đúng vị trí muốn hiện,
  rồi thêm 1 nhánh `elif nav == "Tên trang mới":` bất kỳ đâu trong chuỗi — không cần khớp thứ tự.

## Nguồn sự thật của "đang ở trang nào" là `st.session_state`, không phải widget

`st.session_state["nav"]` được seed đúng 1 lần mỗi phiên từ `st.query_params["nav"]`, rồi mọi thay
đổi (do người dùng click nav) được ghi ngược lại vào `st.query_params`. Đây là cơ chế duy nhất giúp
deep-link kiểu `?nav=Hôm nay&day=2026-07-04` hoạt động qua reload trang — nếu chỉ dựa vào giá trị
widget `st.segmented_control` trả về, link chia sẻ sẽ không mở đúng trang.

Hệ quả khi sửa code: đừng gán trực tiếp vào biến widget để "chuyển trang" bằng tay — phải set
`st.session_state["nav"]` (và/hoặc `st.query_params`) rồi `st.rerun()`. Phím tắt điều hướng (JS,
xem `keyboard-shortcuts.md`) đi theo hướng khác: tự bấm (`.click()`) đúng nút nav đã có sẵn trong
DOM qua `clickNavByLabel()`, tận dụng lại toàn bộ cơ chế session_state/query_params này thay vì tự
set trực tiếp từ phía JS.

## Cấp điều hướng thứ 2: `BAOCAO_SUBS`/`SUCKHOE_SUBS` và `day_picker()`

- Trang "Báo cáo" có sub-nav riêng: list `BAOCAO_SUBS = [Tổng quan, Tuần, Tháng, Năm, Dự án]`,
  seed/ghi lại qua `?sub=` — **cùng 1 pattern hệt `NAV`/`?nav=`**, kể cả nếu bạn không đọc lại code
  chi tiết, áp y hệt cách suy luận. Trang "Sức khoẻ" có `SUCKHOE_SUBS = [Báo cáo, Lịch sử, Dữ liệu
  đầu vào]` qua `?hsub=`, cùng khuôn. Trang "Tuỳ biến" có `TUYBIEN_SUBS = [Tổng quan, Giao diện]`
  qua `?tsub=`, cùng khuôn -- "Giao diện" (6 trục cá nhân hoá, billboard mở đầu đóng luôn vai trò
  xem trước trực tiếp, xem `theming.md`) tách hẳn khỏi chuỗi chương "Tổng quan" thành 1 sub-page
  riêng để có billboard/chip-TOC/hàng nút Reset-Ngẫu nhiên của riêng nó, dù bố cục bên trong (billboard
  + chuỗi `sec_chapter()`) vẫn dùng ĐÚNG khuôn chung với "Tổng quan"/Báo cáo/Sách/Gundam.
- `day_picker(nav_days)` (dùng ở trang "Hôm nay") làm điều tương tự với `?day=` cho việc chọn ngày
  cụ thể — `nav_days` (danh sách ngày lịch/nút `◀`/`▶` được phép tới) quyết định luôn cả biên lo/hi
  lẫn tập ứng viên bước; `render_day_report()` truyền vào hợp của ngày CÓ phiên Forest (`active_days`)
  VÀ ngày CÓ ghi chú (từ `load_notes()`, gồm cả Nhật ký Day One nhập cho các năm trước khi dùng
  Forest) — để mở khoá chọn/gõ ghi chú cho ngày quá khứ chưa từng có phiên nào. `active_days` (hẹp
  hơn) vẫn giữ NGUYÊN cho billboard/nhãn "ngày hoạt động X/Y" — không lẫn 2 khái niệm.
- Muốn nhảy sang 1 sub-tab khác BẰNG CODE (không phải người dùng tự click) — vd 1 nút ở sub-tab A
  chuyển sang sub-tab B — xem gotcha `StreamlitAPIException` + cách fix đúng (cờ chờ xử lý, set
  TRƯỚC khi widget `segmented_control` instantiate) ở `ui-components.md`.

## Link nhảy ngày/Dự án dùng chung 2 helper, không tự ghép chuỗi query riêng

- `_day_link_href(d)` — helper DUY NHẤT dựng href nhảy sang "Hôm nay" của ngày `d`; mọi nơi có
  link nhảy ngày (ô lịch tháng, `.jdate-link` ở Nhật ký/"Ngày này năm trước") PHẢI gọi qua đây,
  không tự ghép chuỗi `?nav=Hôm nay&day=...` riêng nữa.
- `_entity_link_html(name, kind)` — 4 kind `"cat"`/`"proj"` (trỏ sang Báo cáo → Dự án) và
  `"book"`/`"gundam"` (trỏ sang trang Sách/Gundam) — dùng chung cho MỌI nơi hiện tên có thể bấm.

App từng có nút "← Quay lại" (breadcrumb) ở đầu Báo cáo ngày/Báo cáo → Dự án khi tới từ 1 link nội
bộ — đã bỏ vì phá bố cục trang; không còn `from`/`_back_link_html()` trong code.

## Việc cần làm khi thêm 1 trang/sub-tab mới

1. Thêm key vào `NAV` (hoặc item vào `BAOCAO_SUBS`) ở đúng vị trí hiển thị mong muốn.
2. Thêm nhánh `elif` xử lý render — vị trí trong chuỗi if/elif không quan trọng, chỉ cần tồn tại.
3. Nếu trang mới cần tham số riêng qua URL, làm theo đúng pattern seed-từ-query-param → ghi lại
   vào `session_state`/`query_params` — không tự chế cơ chế state khác.
4. Cập nhật trang "Trợ giúp" (thêm nội dung vào chương phù hợp, và/hoặc 1 mục `HELP_CHANGELOG`)
   nếu trang có ý nghĩa với người dùng cuối — xem `ui-components.md`.
