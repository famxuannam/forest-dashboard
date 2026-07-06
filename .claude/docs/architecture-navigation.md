# Điều hướng & dispatch trang

Đối tượng đọc: AI agent chưa từng thấy `app.py`, cần biết cách 1 lượt click nav biến thành 1 trang
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
`st.session_state["nav"]` (và/hoặc `st.query_params`) rồi `st.rerun()`, đúng pattern đã dùng ở các
chỗ điều hướng bằng phím tắt (`goUploadTab` trong JS, xem `keyboard-shortcuts.md`).

## Cấp điều hướng thứ 2: `BAOCAO_SUBS` và `day_picker()`

- Trang "Báo cáo" có sub-nav riêng: list `BAOCAO_SUBS = [Tổng quan, Tuần, Tháng, Năm, Dự án]`,
  seed/ghi lại qua `?sub=` — **cùng 1 pattern hệt `NAV`/`?nav=`**, kể cả nếu bạn không đọc lại code
  chi tiết, áp y hệt cách suy luận.
- `day_picker()` (dùng ở trang "Hôm nay") làm điều tương tự với `?day=` cho việc chọn ngày cụ thể.
- Phím tắt `Shift+1`..`Shift+5` nhảy sub-tab Báo cáo theo **index trong `BAOCAO_SUBS`** — đổi thứ
  tự list này tự động đổi luôn phím tắt tương ứng, không cần sửa gì ở JS (xem
  `keyboard-shortcuts.md`).

## Việc cần làm khi thêm 1 trang/sub-tab mới

1. Thêm key vào `NAV` (hoặc item vào `BAOCAO_SUBS`) ở đúng vị trí hiển thị mong muốn.
2. Thêm nhánh `elif` xử lý render — vị trí trong chuỗi if/elif không quan trọng, chỉ cần tồn tại.
3. Nếu trang mới cần tham số riêng qua URL, làm theo đúng pattern seed-từ-query-param → ghi lại
   vào `session_state`/`query_params` — không tự chế cơ chế state khác.
4. Cập nhật tab "Hướng dẫn" (`guide_item()`) nếu trang có ý nghĩa với người dùng cuối — xem
   `ui-components.md`.
