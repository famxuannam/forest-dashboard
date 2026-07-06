# Component & quy ước UI dùng lại

Đối tượng đọc: AI agent cần thêm 1 mục/trang báo cáo mới, hoặc chỉnh sửa layout 1 trang hiện có.

## Quy ước đánh số `st.expander("N. Tên mục", ...)`

Các trang báo cáo (Tổng quan/Tuần/Tháng/Năm/Dự án, Chi tiết Sách/Gundam) được dựng từ 1 chuỗi
`st.expander("N. Tên mục", ...)` đánh số thứ tự. Đây là quy ước UI có chủ đích, không phải đặt tên
tuỳ tiện. **Khi thêm hoặc xoá 1 mục giữa chuỗi, phải đánh số lại toàn bộ các mục phía sau trong
cùng trang** — để số thứ tự luôn liên tục 1, 2, 3... không nhảy cóc.

Ngoại lệ: mục có điều kiện hiển thị (ví dụ mục "Nhật ký đọc" chỉ hiện khi Dự án đang xem khớp 1
cuốn sách) KHÔNG đánh số, để giữ nguyên số của các mục cố định khác dù mục điều kiện có hiện hay
không.

## `render_stat_panel(hero_items, sections, footer, groups, card_style)`

Component dùng chung cho gần như mọi trang báo cáo: khối "số liệu hero lớn + các hàng chip nhãn
nhỏ bên dưới". Khi cần 1 khối tổng quan số liệu mới, **mở rộng component này** (thêm tham số nếu
cần) thay vì tự viết 1 layout card mới từ đầu — tự viết riêng sẽ lệch style so với phần còn lại của
app. Dùng tham số `card_style` cho các chỉnh sửa margin/width chỉ áp dụng ở 1 nơi gọi — không sửa
giá trị mặc định của hàm vì điều đó ảnh hưởng TẤT CẢ nơi đang gọi nó.

## Bẫy: `st.metric` bị CSS ẩn đi — xem `theming.md`

Đừng dùng `st.metric()` cho số liệu đơn giản; xem phần "Bẫy: `st.metric` bị ẩn toàn cục" trong
`theming.md` để biết cách thay thế đúng.

## Tab "Hướng dẫn": `guide_item()` và `guide_update()`

- `guide_item(image, title, markdown_body, where=..., tip=...)` — 1 mục giải thích tính năng, có
  ảnh minh hoạ (từ `assets/help/`), dùng cho nội dung "cách dùng" ổn định lâu dài.
- `guide_update(pr_no, title, bullets)` — 1 mục trong sub-tab "Cập nhật", không có ảnh (vì UI đổi
  nhanh qua nhiều bản nhỏ, chụp ảnh sẽ lỗi thời ngay), chỉ tiêu đề + số PR + gạch đầu dòng. Thêm 1
  mục mới ở đây khi thay đổi có ảnh hưởng thấy được tới người dùng — số `pr_no` phải khớp đúng số
  PR thật trên GitHub sau khi merge (không đoán số trước khi PR tồn tại).

Nội dung tab "Hướng dẫn" là tài liệu người dùng cuối, không phải code phụ trợ — chỉ sửa khi thay
đổi thực sự ảnh hưởng tới trải nghiệm người dùng, không sửa như tác dụng phụ của 1 việc khác.

## `DTBL` (bảng số liệu dạng heat table)

Style + hàm dựng bảng số liệu có tô màu theo giá trị (heat cell), dùng ở các mục "Bảng số liệu
theo ngày/kỳ". Màu heat cell lấy theo hue suy ra từ `ACCENT` (xem `theming.md`) — không hardcode
thang màu riêng cho bảng mới, tái dùng cùng cơ chế hue để đổi accent tự động đổi luôn bảng.
