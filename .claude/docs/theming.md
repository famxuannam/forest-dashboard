# Theming: CSS custom properties, không phải 2 bộ stylesheet

Đối tượng đọc: AI agent cần thêm UI mới, sửa màu sắc, hoặc đụng vào khối CSS lớn trong `app.py`.

## `IS_DARK` + `--token` CSS variables

`IS_DARK` được suy ra 1 lần từ `st.context.theme.type` ngay khi module load — không tính lại giữa
chừng trang. Một khối `--token` (`--bg`, `--card`, `--text`, `--text-2/3/4`, `--border`,
`--divider`, `--accent`, `--accent-rgb`, `--accent-dark`) được bơm vào `:root{...}`, giá trị chọn
theo `IS_DARK`. **Mọi UI mới nên dùng `var(--token)` thay vì mã màu cứng** — 1 mã hex mới thêm vào
gần như chắc chắn là 1 bug dark-mode đang chờ xảy ra (đúng ở light mode, sai/không đọc được ở dark
mode hoặc ngược lại).

## Khối CSS chính là string thường — KHÔNG chuyển thành f-string

Khối CSS lớn nhất trong `app.py` được viết là 1 string Python bình thường, không phải f-string, dù
phần lớn code khác trong file dùng f-string thoải mái. Lý do: hàng trăm dấu `{`/`}` literal trong
cú pháp CSS (`{ }` bao mỗi rule) sẽ đều bị Python hiểu nhầm là placeholder nếu đổi sang f-string,
phải escape thành `{{`/`}}` ở mọi chỗ — không đáng đổi. Nếu cần chèn 1 giá trị Python động vào CSS,
dùng `.format()`/nối chuỗi cho đúng đúng đoạn cần, không đổi kiểu cả khối.

## Màu accent: 1 giá trị, lan ra 3 cơ chế khác nhau

`ACCENT` (chọn từ `ACCENT_PRESETS`, lưu bền trong bảng `settings`) không chỉ đổi màu qua CSS — nó
lan ra 3 nơi bằng 3 cơ chế khác nhau, phải nhớ cả 3 khi thêm 1 UI element có màu accent:

1. **CSS** — qua `var(--accent)`, `var(--accent-rgb)`, `var(--accent-dark)` — tự động, không cần
   làm gì thêm nếu UI mới style bằng CSS class có sẵn.
2. **Biểu đồ Altair/Plotly** — CSS variable KHÔNG chạm tới được canvas biểu đồ. Dùng hằng số
   Python `ACCENT_RGB`/`ACCENT_DARK` (hoặc giá trị hue suy ra từ accent, dùng để xoay toàn bộ dải
   màu đơn sắc của biểu đồ nhiệt/lịch) truyền trực tiếp vào tham số màu của Plotly/Altair.
3. **Iframe ô ghi chú (Quill)** — chạy trong 1 `<iframe>` là 1 document HTML riêng biệt, CSS của
   trang chính (kể cả `:root` var) KHÔNG lan vào được. App tự tiêm 1 đoạn `<style>` riêng vào BÊN
   TRONG iframe đó (lặp lại theo interval để chống Streamlit dựng lại iframe làm mất style).

## Bẫy: `st.metric` bị ẩn toàn cục bằng CSS

Có 1 rule CSS `[data-testid="stMetric"] { display: none; }` trong khối CSS chính — **mọi lời gọi
`st.metric()` ở bất kỳ đâu trong app đều render ra khoảng trắng vô hình**, không có lỗi, không có
warning, rất khó phát hiện khi review nhanh (đã từng gây bug thật lúc thêm UI mới). Không dùng
`st.metric()`. Thay thế:

- Dùng `render_stat_panel()` nếu là dạng "số liệu hero + chip nhãn" (xem `ui-components.md`).
- Dùng `st.markdown(f"**Nhãn**  \n{giá trị}")` (2 dòng cách nhau bằng 2 khoảng trắng cuối dòng đầu
  + xuống dòng) cho trường hợp đơn giản, không cần style phức tạp.
