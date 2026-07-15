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

## Trang "Trợ giúp" (key nav `"Hướng dẫn"`): tour cuộn dọc, helpers `help_*`

Trang Trợ giúp là 1 trang cuộn dọc theo hành trình sử dụng (hero + mục lục chip anchor + 9
chương), KHÔNG dùng screenshot — mọi minh hoạ vẽ thuần HTML/CSS bằng token màu nên tự đúng theme.
Helpers (đều nằm cạnh nhau trong `app.py`, CSS namespace `help-` trong khối CSS chính):

- `help_chapter(anchor, num, kicker, title, lead=None)` — header 1 chương, `anchor` khớp chip mục
  lục `#help-chN` ở hero.
- `help_block(html)` — 1 thẻ nội dung `.help-card`; `html` phải là chuỗi liền mạch (không dòng
  trống giữa khối, markdown parser sẽ cắt).
- `help_table(headers, rows)` / `help_kbd(*keys)` — bảng cheat-sheet và dãy phím keycap, trả về
  string HTML để nhúng vào `help_block()`.
- `help_faq_item(question, answer_md)` — 1 câu hỏi FAQ dạng `st.expander` (không đánh số).
- `render_help_changelog(entries)` — timeline "Nhật ký phát triển", `entries` là list dict
  `HELP_CHANGELOG` khai báo ngay trong nhánh dispatch. Thêm 1 mục mới (lên đầu list) khi thay đổi
  có ảnh hưởng thấy được tới người dùng — `pr` phải khớp đúng số PR thật trên GitHub sau khi merge
  (không đoán số trước khi PR tồn tại). 2 khoá số liệu tuỳ chọn hiện thành chip, tra tay tại thời
  điểm viết mục — KHÔNG tự tính lại lúc runtime: `total_lines` = tổng số dòng `app.py` tại commit
  merge PR mới nhất trong cụm (`git show <commit>:app.py | wc -l`), `pr_lines` = số dòng đổi
  (additions+deletions, tra qua GitHub API) của riêng PR mới nhất đó.

Nội dung trang Trợ giúp là tài liệu người dùng cuối, không phải code phụ trợ — chỉ sửa khi thay
đổi thực sự ảnh hưởng tới trải nghiệm người dùng, không sửa như tác dụng phụ của 1 việc khác. Khi
sửa, thêm nội dung vào đúng chương theo hành trình (buổi sáng → trong ngày → cuối ngày → review →
nguồn phụ → đồng bộ → tuỳ biến → FAQ → changelog) thay vì mở chương mới.

## Bảng số liệu dạng heat table (`DTBL_CSS`)

Style (`DTBL_CSS`) + các hàm dựng bảng số liệu có tô màu theo giá trị (heat cell): `_heat_cell()`
tính màu 1 ô, dùng bởi `render_data_table()`/`render_detail_table()`/`render_period_table()`/
`render_health_log_table()` — mỗi hàm ứng với 1 kiểu bảng (theo kỳ/theo dự án/theo ngày sức khoẻ)
nhưng cùng chung style/cơ chế tô màu này. Màu heat cell lấy theo hue suy ra từ `ACCENT` (xem
`theming.md`) — không hardcode thang màu riêng cho bảng mới, tái dùng cùng cơ chế hue để đổi
accent tự động đổi luôn bảng.
