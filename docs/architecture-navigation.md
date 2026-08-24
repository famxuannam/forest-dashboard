# Điều hướng & dispatch trang

Đối tượng đọc: Claude Code chưa từng thấy `app.py`, cần biết cách 1 lượt click nav biến thành 1 trang
render ra sao, và cách thêm/sửa 1 trang mà không phá deep-link.

## Cơ chế: 1 dict + 1 chuỗi if/elif, không router riêng

- `NAV` là dict phẳng `{"Tên trang": "material_icon_name", ...}`. Đây là toàn bộ "route table" của
  app — không có class Route, không có framework điều hướng nào khác.
- Trang thực sự được vẽ bởi 1 chuỗi `if nav == "Hôm nay": ... elif nav == "Báo cáo": ...` nằm gần
  cuối `app.py`. Đây KHÔNG phải chỗ quyết định thứ tự hiển thị trên thanh nav — thứ tự đó do vị trí
  key trong dict `NAV` quyết định (cụ thể hơn: vị trí trong `_NAV_GROUP_A`/`_NAV_GROUP_B`, xem mục
  dưới). Khi thêm 1 trang mới: thêm key vào `NAV` (và vào đúng 1 trong 2 group) ở đúng vị trí muốn
  hiện, rồi thêm 1 nhánh `elif nav == "Tên trang mới":` bất kỳ đâu trong chuỗi dispatch — không cần
  khớp thứ tự.
- Nav chính KHÔNG còn là 1 `st.segmented_control` DUY NHẤT render trọn 8 mục (khác thiết kế ban
  đầu) — vì sub-nav của Báo cáo/Tuỳ biến/Nhật ký đọc sách/Gundam phải chèn NGAY SAU nút
  của đúng trang cha (xác nhận với người dùng, xem mục "Cấp điều hướng thứ 2" dưới), 1 radiogroup
  duy nhất không cho phép chèn phần tử HTML rời vào giữa các nút. Nav chính giờ RẢI RÁC thành nhiều
  `segmented_control` nhỏ (`_render_nav_segment()`), số lượng và ranh giới thay đổi tuỳ trang đang
  active.

## Nguồn sự thật của "đang ở trang nào" là `st.session_state`, không phải widget

`st.session_state["nav"]` được seed đúng 1 lần mỗi phiên từ `st.query_params["nav"]`, rồi mọi thay
đổi (do người dùng click nav) được ghi ngược lại vào `st.query_params`. Đây là cơ chế duy nhất giúp
deep-link kiểu `?nav=Hôm nay&day=2026-07-04` hoạt động qua reload trang — nếu chỉ dựa vào giá trị
widget trả về, link chia sẻ sẽ không mở đúng trang. Khác NHIỀU widget khác trong app (vd `bc_sub`),
`"nav"` KHÔNG còn là key CỦA 1 widget cụ thể — nav chính đã chẻ thành nhiều `segmented_control` con
(xem mục dưới), mỗi con có key riêng (`navseg_<group>_<full|pre|post>_<slug>`); `"nav"` thuần là 1
biến trạng thái logic mà các đoạn đó cùng đọc/ghi qua, giống hệt cách `bc_sub`/`tb_sub`
tách khỏi key widget `bc_sub_picker`/`tb_sub_picker` của chúng.

Hệ quả khi sửa code: đừng gán trực tiếp vào biến widget để "chuyển trang" bằng tay — mọi thay đổi
trang PHẢI đi qua `_commit_nav(new_nav)` (set `st.session_state["nav"]` + `st.query_params["nav"]`
+ reset "Hôm nay" về đúng ngày hôm nay nếu cần + `st.rerun()` NGAY). Rerun là BẮT BUỘC ở đây (khác
nhiều nơi khác trong app): các đoạn nav_*/sub-nav trong CÙNG lượt chạy đã render dựa theo `nav` CŨ
(đọc 1 lần ở đầu lượt chạy) — đổi `session_state["nav"]` giữa chừng không tự vẽ lại phần đã render
phía trên, phải rerun để lượt chạy MỚI chẻ nhóm nav lại đúng theo trang mới. Phím tắt điều hướng
(JS, xem `keyboard-shortcuts.md`) đi theo hướng khác: tự bấm (`.click()`) đúng nút nav đã có sẵn
trong DOM qua `clickNavByLabel()`, tận dụng lại toàn bộ cơ chế `_commit_nav()`/query_params này
thay vì tự set trực tiếp từ phía JS.

## Cấp điều hướng thứ 2: `BAOCAO_SUBS`/`TUYBIEN_SUBS` và `day_picker()`

- Trang "Báo cáo" có sub-nav riêng: list `BAOCAO_SUBS = [Tổng quan, Tuần, Tháng, Năm, Dự án]`,
  seed/ghi lại qua `?sub=` — **cùng 1 pattern hệt `NAV`/`?nav=`**, kể cả nếu bạn không đọc lại code
  chi tiết, áp y hệt cách suy luận. Trang "Tuỳ biến" có `TUYBIEN_SUBS = [Tổng quan, Giao diện]`
  qua `?tsub=`, cùng khuôn -- "Giao diện" (6 trục cá nhân hoá, billboard mở đầu đóng luôn vai trò
  xem trước trực tiếp, xem `theming.md`) tách hẳn khỏi chuỗi chương "Tổng quan" thành 1 sub-page
  riêng để có billboard/chip-TOC/hàng nút Reset-Ngẫu nhiên của riêng nó, dù bố cục bên trong (billboard
  + chuỗi `sec_chapter()`) vẫn dùng ĐÚNG khuôn chung với "Tổng quan"/Báo cáo/Sách/Gundam. Trang
  "Nhật ký đọc sách"/"Gundam" (dùng chung `render_reading_log()`) có `SACH_SUBS = [Tổng quan, Trích
  dẫn, Chi tiết]`/`GUNDAM_SUBS = [Tổng quan, Chi tiết]` — KHÔNG có query param riêng lưu tên sub-tab
  (khác 3 trang trên) vì link nhảy tới 1 cuốn/series cụ thể dùng `?book=`/`?series=` (đọc lại trong
  `_render_reading_detail()`), chỉ để quyết định sub-tab KHỞI ĐẦU là "Chi tiết" hay không.
- Cả 4 widget picker (`bc_sub_picker`/`tb_sub_picker`/`rl_view_tabs_picker`/
  `rl_view_tabs_gd_picker`) render trong `st.sidebar`, NGAY SAU nút của đúng trang cha trong nav
  chính (Báo cáo/Tuỳ biến/Nhật ký đọc sách/Gundam), thay vì đứng ở đầu nội dung trang HAY
  rơi xuống cuối toàn bộ nav chính (xác nhận với người dùng qua NHIỀU lượt đổi kiến trúc điều
  hướng liên tiếp — lượt 1 dời cả sub-nav lẫn nav chính vào sidebar nhưng để sub-nav render sau
  TOÀN BỘ nav chính; lượt 2 chèn xen kẽ đúng vị trí cho Báo cáo/Tuỳ biến; lượt 3 mới bắt
  kịp 2 sub-nav còn sót của Nhật ký đọc sách/Gundam, trước đó vẫn đứng ở đầu nội dung trang do cơ
  chế của chúng nằm TRONG `render_reading_log()` thay vì ở dispatch chính nên bị bỏ sót khi đổi
  kiến trúc lần đầu). Cơ chế (`_render_nav_group()`, `_render_nav_segment()`,
  `_render_active_subnav()`, `_NAV_SUBNAV`, `_NAV_GROUP_A`/`_NAV_GROUP_B`, `_NAV_SLUG`) nằm ngay
  sau khi `NAV`/`NAV_SHORT` được khai báo, đầu `app.py`:
  - `_NAV_GROUP_A`/`_NAV_GROUP_B` là 2 cụm nav chính cố định (cách nhau bởi 1 `<div
    class="sidebar-nav-divider">` tường minh, KHÔNG còn dựng bằng CSS `nth-child` như bản đầu
    tiên vì số radiogroup thực tế trên trang giờ thay đổi theo `nav`).
  - `_NAV_SUBNAV` map trang → `(subs, icons, state_key, widget_key, query_param, label_widget)` —
    trang nào có mặt trong dict này thì có sub-nav. `query_param` có thể là `None` (Nhật ký đọc
    sách/Gundam, xem trên) — `_render_active_subnav()` chỉ ghi `st.query_params[qparam]` khi
    `qparam` truthy.
  - `_render_nav_group(items, group_key)`: nếu `nav` nằm trong cụm này VÀ có trong `_NAV_SUBNAV`,
    chẻ cụm thành đoạn `pre` (tới hết nút của `nav`) + đoạn `post` (phần còn lại), chèn
    `_render_active_subnav()` xen giữa; nếu không, render nguyên cụm thành 1 đoạn `full`.
  - Key của mỗi đoạn (`navseg_<group>_<full|pre|post>_<slug trang, xem _NAV_SLUG>`) LUÔN gắn thêm
    slug ASCII của `nav` hiện tại — **QUAN TRỌNG, đừng bỏ qua khi sửa**: 1 đoạn "full" (không chẻ)
    được TÁI SỬ DỤNG cho nhiều trang khác nhau tuỳ lúc (vd cụm A dạng full dùng chung cho cả "Hôm
    nay" lẫn "Tìm kiếm"), nếu 2 trang khác nhau dùng CHUNG 1 key thì lựa chọn hiển
    thị của lượt trước có thể "dính" sai khi đổi sang trang khác cũng dùng key đó (vì `default=`
    của `segmented_control` chỉ được đọc đúng 1 LẦN ĐẦU TIÊN 1 key tồn tại trong session, các lần
    sau bị bỏ qua). Gắn slug trang vào key khiến mỗi (cụm, biến thể, trang) có key RIÊNG, luôn
    đúng ngay từ `default=`.
  - **Bẫy đã gặp thật, đừng lặp lại**: TUYỆT ĐỐI không tự `st.session_state[key] = ...` để "ép"
    đúng lựa chọn hiển thị ngay TRƯỚC khi gọi `st.segmented_control(..., key=key)` của 1 đoạn nav_*
    trên MỌI lượt chạy (khác hẳn cờ `_bc_sub_jump`, chỉ set 1 lần có điều kiện) — làm
    vậy sẽ GHI ĐÈ lên đúng giá trị Streamlit vừa nhận từ cú click thật của người dùng (Streamlit đã
    set `session_state[key]` đó TRƯỚC khi script chạy lại), khiến MỌI cú click coi như không xảy ra,
    pill nav không bao giờ đổi được (bug thật đã gặp khi thử cách này trước khi đổi sang đặt key
    riêng theo slug trang ở trên).
  - Dispatch nội dung trang (chuỗi if/elif chính, và `render_reading_log()` cho Sách/Gundam) chỉ
    ĐỌC lại `st.session_state["bc_sub"]`/`"tb_sub"`/`"rl_view_tabs"`/`"rl_view_tabs_gd"`
    đã đồng bộ sẵn ở sidebar, không tự render lại widget picker.
- Cờ chờ xử lý kiểu `_bc_sub_jump` (nhảy sang 1 sub-tab khác BẰNG CODE) PHẢI được
  set/pop TRƯỚC khối render nav trong sidebar (tức là ở phần khai báo `BAOCAO_SUBS`/`TUYBIEN_SUBS`
  đầu `app.py`, không phải trong hàm render trang như trước khi dời sang sidebar) — xem gotcha
  `StreamlitAPIException` ở `ui-components.md`, giờ áp dụng chặt hơn vì widget instantiate sớm hơn
  nhiều trong lượt chạy so với trước.
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

1. Thêm key vào `NAV` (hoặc item vào `BAOCAO_SUBS`) ở đúng vị trí hiển thị mong muốn — với trang
   cấp 1 (nav chính), nhớ thêm luôn vào ĐÚNG 1 trong 2 list `_NAV_GROUP_A`/`_NAV_GROUP_B` (cụm nào
   trang mới thuộc về) VÀ vào `_NAV_SLUG` (slug ASCII riêng, dùng để dựng key widget).
2. Thêm nhánh `elif` xử lý render — vị trí trong chuỗi if/elif không quan trọng, chỉ cần tồn tại.
3. Nếu trang mới cần tham số riêng qua URL, làm theo đúng pattern seed-từ-query-param → ghi lại
   vào `session_state`/`query_params` — không tự chế cơ chế state khác.
4. Nếu trang mới cũng cần sub-nav (như Báo cáo/Tuỳ biến): thêm 1 entry vào `_NAV_SUBNAV`
   (subs/icons/state_key/widget_key/query_param/label) — `_render_nav_group()` sẽ TỰ chèn sub-nav
   ngay sau nút của trang đó, không cần tự viết lại logic chẻ nhóm.
