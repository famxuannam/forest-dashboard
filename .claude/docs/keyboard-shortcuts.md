# Phím tắt bàn phím: 1 blob JS tiêm vào trang

Đối tượng đọc: AI agent cần thêm/sửa 1 phím tắt, hoặc debug vì sao phím tắt không hoạt động ở 1 chỗ
cụ thể (đặc biệt bên trong ô ghi chú).

## Toàn bộ phím tắt toàn cục sống trong `_inject_keyboard_shortcuts()`

Hàm này gọi `components.html(js, height=0)` với 1 chuỗi JS lớn, xử lý:

- Phím số `1`-`7`: nhảy nav chính (index theo `NAV`).
- `Shift+1`..`Shift+5`: nhảy sub-tab trang Báo cáo, **index theo `BAOCAO_SUBS`** — đổi thứ tự list
  này ở Python thì phím tắt tự đổi theo, KHÔNG cần sửa gì trong JS. Chỉ cần sửa doc/help-text nếu
  thứ tự đổi.
- `n`/`f`/`r`/`l`/`/`/`?`, phím mũi tên, `[`/`]`: các shortcut điều hướng nhanh khác (n = ghi chú
  mới, f/r = mở tab tải Forest/Reminder VÀ bấm luôn nút chọn file, l = mở tab Đồng bộ lịch).
- Các phím tắt này chủ động **bị bỏ qua khi đang gõ trong 1 ô input** (input/textarea đang focus) —
  giữ nguyên hành vi này khi thêm phím mới, tránh phím tắt "nuốt" mất ký tự người dùng đang gõ.

## Ô ghi chú (Quill) cần 1 bộ tiêm JS RIÊNG: `_inject_note_editor_shortcuts()`

Quill chạy trong 1 `<iframe>` — sự kiện `keydown` bên trong iframe **không bubble ra** frame cha, vì
vậy bộ phím tắt toàn cục ở trên không nhận được. Bất kỳ phím tắt nào cần hoạt động khi con trỏ đang
ở trong ô ghi chú phải tiêm riêng qua hàm này, bên trong chính document của iframe.

## Việc cần làm khi thêm 1 phím tắt mới

1. Xác định phím tắt cần hoạt động ở đâu: toàn trang → sửa `_inject_keyboard_shortcuts()`; chỉ khi
   đang gõ ghi chú → sửa `_inject_note_editor_shortcuts()`.
2. Nếu phím tắt điều hướng tới 1 tab/nav mới, tái dùng đúng cơ chế set `session_state`/
   `query_params` rồi `st.rerun()` — xem `architecture-navigation.md`, không tự chế cách điều
   hướng khác bằng JS thuần (ví dụ đổi `window.location` trực tiếp sẽ phá session state).
3. Cập nhật bảng phím tắt trong tab "Hướng dẫn" (sub-tab liệt kê phím tắt) — đây là tài liệu người
   dùng, không tự động sinh ra từ code.
