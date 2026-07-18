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
- **Chỉ số sức khoẻ (`_health_is_abnormal`) chỉ nhị phân trong/ngoài khoảng tham chiếu** — KHÔNG
  thêm mức "sát ngưỡng"/cảnh báo sớm nào (đã xác nhận với người dùng 2 lần, ở cả trang Lịch sử và
  Báo cáo của Sức khoẻ): mức đó cần tự đặt 1 ngưỡng % không có cơ sở dữ liệu thật. Nếu 1 mockup
  sau này lại vẽ mức thứ 3 kiểu vậy, hỏi lại chứ không tự thêm.
- **Thứ tự chương chuẩn cho mọi trang báo cáo** (Báo cáo mọi sub-tab, Sách/Gundam, Dự án — đã áp
  dụng nhất quán qua đợt tái cấu trúc UX, xác nhận với người dùng): Tổng quan → Biểu đồ lịch (luôn
  đúng vị trí 2 nếu trang có) → Phân bổ Danh mục/Dự án → Xu hướng theo thời gian → Nhật ký/ghi chú
  định tính → Bảng số liệu (LUÔN là chương cuối cùng). Hero của chương Tổng quan KHÔNG được lặp lại
  đúng con số billboard đã hiện phía trên (xem `hero_items=[]` hoặc hero rút gọn ở Dự án/Sách/Gundam
  Chi tiết/Gundam Tổng quan trong `ui-components.md`) — chỉ giữ số liệu bổ sung. Đổi thứ tự này ở 1
  trang cụ thể cần hỏi lại trước, vì mục tiêu là nhất quán xuyên suốt mọi trang cùng họ.

## 6. Tài liệu bổ sung

- [`.claude/docs/architecture-navigation.md`](.claude/docs/architecture-navigation.md) — dispatch
  trang theo `st.query_params`, cấu trúc `NAV`/`BAOCAO_SUBS`, `day_picker()`.
- [`.claude/docs/data-layer.md`](.claude/docs/data-layer.md) — cặp `load_*`/`save_*` từng bảng,
  timezone, `prep_analysis_data()`, luồng "Đồng bộ nhanh" qua Supabase Storage.
- [`.claude/docs/theming.md`](.claude/docs/theming.md) — CSS custom properties, `IS_DARK`, cách
  màu accent lan sang biểu đồ và iframe ghi chú.
- [`.claude/docs/ui-components.md`](.claude/docs/ui-components.md) — quy ước đánh số `sec_chapter()`,
  thứ tự chương chuẩn của trang báo cáo, `render_stat_panel()`, bẫy `st.metric`, bộ helper `help_*`
  của trang Trợ giúp.
- [`.claude/docs/keyboard-shortcuts.md`](.claude/docs/keyboard-shortcuts.md) — blob JS phím tắt
  toàn cục và phím tắt riêng trong iframe ghi chú.
- [`.claude/docs/testing.md`](.claude/docs/testing.md) — harness giả lập Supabase + Playwright để
  kiểm thử không cần mạng thật.
- [`.claude/docs/git-workflow.md`](.claude/docs/git-workflow.md) — nhánh làm việc theo phiên, quy
  trình PR squash-merge, cách làm sạch nhánh sau mỗi lần merge.

## 7. Karpathy Skills — nguyên tắc hành vi khi code

Nguồn: [andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills). Bổ sung
cho mục 5 (không thay thế) — thiên về cẩn trọng hơn tốc độ; với việc nhỏ/hiển nhiên thì dùng
judgement, không cần áp cứng nhắc.

### 7.1 Think Before Coding

Đừng giả định. Đừng giấu chỗ chưa rõ. Nêu rõ trade-off.

- Nói rõ giả định đang đặt ra trước khi code. Nếu không chắc, hỏi lại.
- Nếu có nhiều cách hiểu yêu cầu, trình bày cả các cách hiểu đó — không tự chọn 1 rồi im lặng làm.
- Nếu có cách đơn giản hơn, nói ra. Phản biện lại yêu cầu khi thấy cần.
- Nếu có điểm chưa rõ, dừng lại, nêu đúng chỗ đang vướng, rồi hỏi.

### 7.2 Simplicity First

Viết lượng code tối thiểu đủ giải quyết vấn đề. Không viết gì mang tính suy đoán trước.

- Không thêm tính năng ngoài yêu cầu.
- Không tạo abstraction cho code chỉ dùng 1 lần.
- Không thêm "linh hoạt"/"tuỳ biến" nếu không ai yêu cầu.
- Không xử lý lỗi cho tình huống không thể xảy ra.
- Nếu viết 200 dòng mà có thể rút về 50, viết lại.

Tự hỏi: "1 kỹ sư senior nhìn vào có thấy đang làm phức tạp hoá không?" — nếu có, đơn giản lại.

### 7.3 Surgical Changes

Chỉ đụng vào đúng phần cần đụng. Chỉ dọn rác do chính mình tạo ra.

- Không "cải thiện" code/comment/format ở những dòng không liên quan.
- Không refactor những chỗ không hỏng.
- Theo đúng style code đã có, dù cá nhân có thể làm khác.
- Nếu thấy dead code không liên quan, nêu ra — không tự xoá.
- Khi thay đổi của mình làm phát sinh phần thừa (import/biến/hàm không còn dùng do CHÍNH thay đổi
  đó), thì xoá phần thừa đó. Không xoá dead code có từ trước nếu không được yêu cầu.

Bài kiểm: mỗi dòng thay đổi phải truy được thẳng về yêu cầu của người dùng.

### 7.4 Goal-Driven Execution

Định nghĩa rõ tiêu chí hoàn thành. Lặp lại tới khi xác minh được.

Biến yêu cầu mơ hồ thành mục tiêu kiểm chứng được, ví dụ:
- "Thêm validation" → "Viết test cho input không hợp lệ, rồi làm cho test đó pass"
- "Sửa bug này" → "Viết 1 test tái hiện đúng bug, rồi làm cho test đó pass"
- "Refactor X" → "Đảm bảo test pass cả trước và sau khi refactor"

Với việc nhiều bước, nêu ngắn 1 kế hoạch dạng:
```
1. [Bước] → xác minh: [cách kiểm tra]
2. [Bước] → xác minh: [cách kiểm tra]
3. [Bước] → xác minh: [cách kiểm tra]
```

Tiêu chí thành công rõ ràng giúp tự lặp độc lập được; tiêu chí mơ hồ ("làm cho nó chạy được") sẽ
cần hỏi lại liên tục.

**4 nguyên tắc này đang phát huy hiệu quả nếu:** diff bớt hẳn thay đổi không cần thiết, ít phải viết
lại vì làm phức tạp hoá, và câu hỏi làm rõ xuất hiện TRƯỚC khi code thay vì SAU khi đã lỡ sai.
