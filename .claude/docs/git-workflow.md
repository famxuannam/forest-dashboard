# Git workflow của repo này

Đối tượng đọc: AI agent chuẩn bị commit/push/mở PR trên repo `famxuannam/forest-dashboard`.

## Nhánh làm việc là theo phiên, không cố định

Mỗi phiên làm việc được giao 1 nhánh cụ thể (khai báo trong system prompt/task instruction của
phiên đó, dạng `claude/<mô-tả-việc>-<mã-ngẫu-nhiên>`) — **không hardcode tên nhánh cụ thể ở đây**,
vì tên đổi theo từng task và sẽ lỗi thời ngay khi ghi cứng. Luôn lấy tên nhánh thật từ chỉ dẫn của
phiên hiện tại, không suy đoán từ lịch sử git hay từ tài liệu này.

## PR được squash-merge từng cái một

- **Không tự ý mở hoặc merge Pull Request khi chưa được yêu cầu rõ ràng** — mặc định chỉ commit +
  push lên nhánh làm việc sau khi đã xác minh, rồi dừng lại chờ.
- Khi được yêu cầu merge: kiểm tra repo có template PR không (`.github/pull_request_template.md`
  hoặc tương đương) trước khi viết mô tả PR; nếu có, theo đúng bố cục đó.
- Vì PR bị squash, lịch sử nhánh làm việc **sẽ lệch khỏi `origin/main`** ngay sau mỗi lần merge.
  Trước khi bắt đầu việc mới (hoặc trước khi commit tiếp, nếu `origin/main` đã đổi), phải làm sạch
  nhánh:
  ```bash
  git fetch origin main
  git checkout -B <tên-nhánh-được-giao> origin/main
  # cherry-pick/áp lại thủ công bất kỳ việc nào chưa merge nếu có
  git push --force-with-lease -u origin <tên-nhánh-được-giao>
  ```

## Trước khi commit

Dọn sạch mọi file sinh ra trong lúc test cục bộ (`database.csv`, `mapping.csv`, `notes.csv`,
`__pycache__`, file scratch app, secrets giả) — chi tiết ở `testing.md`. Chạy lại
`python3 -c "import ast; ast.parse(open('app.py').read())"` lần cuối trước khi commit.
