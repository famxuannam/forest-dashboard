# 🌲 Forest Dashboard

Bảng điều khiển (dashboard) trực quan hoá dữ liệu tập trung từ ứng dụng **Forest** —
giúp bạn nhìn lại mình đã dành thời gian cho việc gì, vào lúc nào, đều đặn ra sao.

Ứng dụng đọc file CSV bạn xuất ra từ Forest, tự phân tích và hiển thị thành các biểu đồ,
bảng số liệu theo nhiều góc nhìn (tổng quan, theo tháng, theo tuần, theo dự án).
Giao diện theo phong cách iOS/macOS: tối giản, dùng thẻ kính mờ và tông xanh `#007aff`.

---

## Mục lục

- [Khái niệm cốt lõi](#khái-niệm-cốt-lõi)
- [Các chỉ số & biểu đồ nghĩa là gì](#các-chỉ-số--biểu-đồ-nghĩa-là-gì)
- [Hướng dẫn sử dụng theo từng trang](#hướng-dẫn-sử-dụng-theo-từng-trang)
- [Quy trình bắt đầu nhanh](#quy-trình-bắt-đầu-nhanh)
- [Thiết lập Supabase (bắt buộc)](#thiết-lập-supabase-bắt-buộc)
- [Đăng nhập Google (tuỳ chọn)](#đăng-nhập-google-tuỳ-chọn)
- [Đồng bộ lịch & đọc sách (tuỳ chọn)](#đồng-bộ-lịch--đọc-sách-tuỳ-chọn)
- [Tuỳ chỉnh giao diện (tuỳ chọn)](#tuỳ-chỉnh-giao-diện-tuỳ-chọn)
- [Cài đặt & chạy ứng dụng](#cài-đặt--chạy-ứng-dụng)
- [Câu hỏi thường gặp](#câu-hỏi-thường-gặp)

---

## Khái niệm cốt lõi

Hiểu 4 khái niệm này là dùng được toàn bộ ứng dụng:

| Khái niệm | Ý nghĩa |
|-----------|---------|
| **Phiên / Cây** | Mỗi lần bạn trồng cây thành công trong Forest là **một phiên tập trung**. Trong dashboard, *“số cây”* chính là **số phiên**. Một cây = một lần tập trung. |
| **Dự án** | Nhãn (tag) bạn gắn cho mỗi phiên trong Forest, ví dụ *Toán*, *Lập trình*, *Đọc sách*. Đây là đơn vị nhỏ nhất. |
| **Danh mục (Nhóm)** | Tập hợp nhiều **Dự án** liên quan thành một **nhóm lớn**, ví dụ nhóm *Học tập* gồm *Toán* + *Lập trình*. Bạn tự định nghĩa các nhóm này trong tab **Chuẩn bị dữ liệu**. Dự án nào chưa được gán nhóm thì mặc định tự đứng thành một nhóm trùng tên. |
| **Thời lượng** | Số phút của mỗi phiên (tính từ *Thời gian bắt đầu* đến *Thời gian kết thúc*). Trong các biểu đồ, thời lượng thường được quy đổi sang **giờ**. |

**Một vài quy ước về thời gian** (áp dụng nhất quán toàn app):

- **Tuần** tính theo chuẩn ISO: **bắt đầu từ Thứ Hai và kết thúc Chủ Nhật**. Đường kẻ
  nét đứt trên các biểu đồ theo ngày chính là ranh giới giữa các tuần.
- **Ngày của một phiên** được tính theo *thời gian bắt đầu*.
- Các chỉ số *“trung bình/ngày”* chỉ chia cho **những ngày bạn thực sự có hoạt động**
  (ngày không trồng cây nào không bị tính vào mẫu số), nên con số phản ánh đúng
  “khi có làm thì làm bao nhiêu”.

---

## Các chỉ số & biểu đồ nghĩa là gì

### Thẻ số liệu trong phần “Tổng quan”

- **Tổng thời gian** — tổng số giờ đã tập trung trong phạm vi đang xem.
- **Số cây đã trồng** — tổng số phiên (số cây).
- **Thời gian / ngày** — trung bình số giờ mỗi *ngày có hoạt động*.
- **Số cây / ngày** — trung bình số phiên mỗi *ngày có hoạt động*.
- **Thời gian / tuần**, **Số cây / tuần** *(tab Báo cáo theo dự án)* — trung bình theo
  số *tuần có hoạt động*.
- **Thời gian / phiên** — độ dài bình quân của mỗi phiên (tổng thời gian ÷ số phiên), tính
  bằng **phút**. Phản ánh *độ sâu* mỗi lần tập trung: bạn làm nhiều phiên ngắn hay ít phiên
  sâu. Ở **Báo cáo tháng/tuần** chỉ số này cũng có 2 dòng so sánh như các thẻ khác.
- **Cập nhật gần nhất** *(tab Thống kê chung)* — thời điểm phiên gần nhất kết thúc, kèm
  khoảng cách so với hiện tại (ví dụ *“1 ngày 3 giờ trước”*).

Ở **Báo cáo tháng** và **Báo cáo tuần**, mỗi thẻ còn có 2 dòng so sánh:

- **vs Tháng trước / vs Tuần trước** — chênh lệch so với kỳ liền trước.
- **vs Trung bình** — chênh lệch so với mức trung bình của tất cả các kỳ khác.

> Màu **xanh lá** nghĩa là cao hơn (tốt hơn), **đỏ** nghĩa là thấp hơn.

Ở **Thống kê chung / Báo cáo tháng / Báo cáo tuần**, phần Tổng quan còn có **Top 3 Danh
mục / Dự án** — ba nhóm hoặc dự án bạn dành nhiều giờ nhất trong kỳ.

Ở **Báo cáo theo dự án**, phần Tổng quan gom mọi chỉ số của nhóm/dự án đang chọn thành các
nhóm gọn (mỗi nhóm một hàng): **Trung bình** (giờ & cây theo ngày/tuần), **Tuần này** (nổi
bật màu xanh, chỉ hiện khi tuần này có hoạt động), **Chuỗi ngày** (tổng / dài nhất / hiện
tại), **Theo thứ** (thứ mạnh nhất & yếu nhất), và **Mốc thời gian** (ngày đầu tiên, ngày
gần nhất).

### Phân bố độ dài phiên

Có hai cách nhìn về độ dài phiên, đều ở phần đầu mỗi tab:

- **Trong mục Tổng quan** — một **thanh phân bố** chia phiên thành 5 nhóm **Tối thiểu** (= 10′,
  mức sàn của Forest) / **Ngắn** (< 25′) / **Trung bình** (25–<50′) / **Dài** (50–<90′) /
  **Rất Dài** (≥ 90′), kèm tỉ lệ % và số phiên mỗi nhóm. Ranh giới là *nửa mở*: phiên đúng
  25′ thuộc Trung bình, đúng 50′ thuộc Dài, đúng 90′ thuộc Rất Dài. Các mốc 25 / 50 / 90 neo theo **Pomodoro**
  (1 pomodoro = 25 phút tập trung) và ngưỡng deep-work ~90 phút.
- **Mục “Phân bố độ dài phiên”** (ngay trước Bảng số liệu) — một **biểu đồ histogram** đếm số phiên
  theo từng khoảng 5 phút, từ **10 phút** (mức tối thiểu của Forest) đến 60, phần dài hơn gộp
  vào **≥ 60′**. Histogram cho thấy đúng *hình dạng* thói quen của bạn (ví dụ phần lớn phiên
  dồn ở 10–15 phút) mà các nhóm cố định không thể hiện được. Trên biểu đồ, **đường chấm** là các
  mốc 25 / 50 / 90′, **đường gạch** là độ dài trung bình mỗi phiên.

### Các biểu đồ

- **Xu hướng theo thời gian** — cột chồng thể hiện số giờ theo thời gian, điều chỉnh bằng 3
  lựa chọn: *Khoảng thời gian*, *gộp theo* **Ngày / Tuần / Tháng**, và tô màu *phân loại
  theo* **Danh mục / Dự án**. Khi gộp theo **Ngày**, biểu đồ phủ thêm **đường trung bình
  động 7 ngày** (đường chấm) để cắt nhiễu hằng ngày, cho thấy xu hướng đang lên hay xuống.
- **Phân bổ thời gian** — biểu đồ tròn cho thấy tỉ trọng thời gian giữa các nhóm/dự án
  trong kỳ.
- **Xu hướng tập trung theo khung giờ** — số giờ cộng dồn theo **khung giờ (0h - 23h)**,
  giúp nhận ra bạn tập trung tốt vào buổi sáng, chiều hay tối. Đường xanh là **tổng cộng**.
- **Giờ tập trung theo thứ** — bản đồ nhiệt **7 thứ × 24 giờ**: mỗi ô là một khung giờ của
  một thứ, ô càng **xanh đậm** thì trung bình giờ/ngày ở khung giờ đó càng cao. Trả lời câu
  hỏi “tập trung tốt nhất vào sáng / chiều / tối thứ mấy”.
- **Biểu đồ lịch** (kiểu “đóng góp” của GitHub) — mỗi ô là một ngày; ô càng **xanh đậm**
  thì ngày đó càng nhiều giờ. Kèm theo 3 chỉ số chuỗi:
  - **Tổng cộng** — tổng số ngày có hoạt động.
  - **Chuỗi dài nhất** — số ngày liên tiếp dài nhất từng đạt được.
  - **Chuỗi hiện tại** — số ngày liên tiếp tính đến hôm nay (chỉ còn hiệu lực nếu hôm nay
    hoặc hôm qua bạn có hoạt động).

### Bảng số liệu

- Ở **Thống kê chung**: bảng dạng **ma trận** *Danh mục / Dự án × kỳ (Tuần/Tháng)*, ô càng
  xanh càng nhiều giờ, cột **Tổng** ở cuối. Ô có dấu **▾ đỏ** là kỳ đó **giảm mạnh** (trên
  60%) so với kỳ liền trước — giúp phát hiện nhóm/dự án đang bị bỏ bê.
- Ở **Báo cáo tháng / tuần**: bảng **chi tiết** từng Danh mục/Dự án trong kỳ, kèm cột **Tỉ
  trọng** (% thời gian trên tổng kỳ).
- Ở **Báo cáo theo dự án**: vì chỉ xem một nhóm/dự án nên bảng được tối ưu thành dạng
  **theo kỳ** — mỗi dòng là một Tuần/Tháng với *Số giờ*, *Số cây*, *Số ngày*, kèm dòng **Tổng**.

### Bộ lọc & điều hướng dùng chung

- **Khoảng thời gian**: `30 ngày · 90 ngày · 6 tháng · 1 năm · Tất cả` — lọc nhanh phạm vi
  dữ liệu (tính lùi từ ngày gần nhất). Ở **Thống kê chung**, mỗi mục (Biểu đồ lịch, Xu
  hướng theo thời gian, theo khung giờ, theo thứ, Bảng số liệu) có **bộ lọc khoảng thời
  gian riêng**, điều chỉnh độc lập với nhau.
- **Chọn kỳ** (tab tháng/tuần): nút **◀ ▶** để lùi/tiến từng kỳ, ô thả xuống để nhảy nhanh,
  và nút lịch 🗓️ để **về thẳng kỳ hiện tại**.
- **Mọi mục đều gập/mở được**: bấm vào tiêu đề mục để thu gọn hoặc mở rộng. Trong các trang
  báo cáo, **mặc định chỉ mở sẵn mục _Tổng quan_** (và _Nhật ký_/_Ghi chú ngày_ nếu có) cho gọn
  gàng; các mục còn lại đóng sẵn, mở khi cần.

---

## Hướng dẫn sử dụng theo từng trang

Thanh điều hướng nằm ngay dưới tiêu đề, gồm 7 trang:

### 1. 📊 Thống kê chung
Cái nhìn tổng thể toàn bộ dữ liệu.
1. **Tổng quan** — các thẻ số liệu chính + cập nhật gần nhất + thanh phân bố độ dài phiên + Top 3.
2. **Biểu đồ lịch** — lịch nhiệt + chuỗi ngày.
3. **Xu hướng theo thời gian** — chọn khoảng thời gian, cách gộp và cách phân loại (kèm
   đường TB động 7 ngày khi xem theo ngày).
4. **Xu hướng tập trung theo khung giờ** — bạn tập trung mạnh vào giờ nào.
5. **Giờ tập trung theo thứ** — bản đồ nhiệt 7 thứ × 24 giờ.
6. **Phân bố độ dài phiên** — histogram độ dài phiên (xem mục trên).
7. **Bảng số liệu** — ma trận Danh mục/Dự án theo Tuần hoặc Tháng.

### 2. 🗓️ Báo cáo tháng
Phân tích sâu **một tháng cụ thể** (chọn ở thanh điều hướng kỳ): Tổng quan (kèm so sánh) →
**Nhật ký** → Phân bổ thời gian → Xu hướng theo thời gian → Xu hướng tập trung theo khung giờ →
Giờ tập trung theo thứ → Phân bố độ dài phiên → Bảng số liệu. Mục **Nhật ký** liệt kê (chỉ đọc)
mỗi ngày trong tháng có ít nhất 1 trong 3 nguồn — theo thứ tự cố định **chip lịch (Đồng bộ
lịch) → chip phần đọc sách/Gundam (Tải lên từ Reminder) → ghi chú** (xem
[Ghi chú theo ngày](#4--báo-cáo-ngày)).

### 3. 🗓️ Báo cáo tuần
Tương tự báo cáo tháng nhưng cho **một tuần cụ thể** (cũng có mục **Nhật ký** của các ngày
trong tuần).

### 4. 📅 Báo cáo ngày
Xem lại **một ngày cụ thể**. Vì dữ liệu nạp thủ công (không thời gian thực) nên trọng tâm là
*ôn lại các ngày đã qua*.
- **Chọn ngày**: nút **◀ ▶** nhảy tới ngày **có hoạt động** liền kề (bỏ qua ngày trống), **lịch
  chọn ngày** để nhảy thẳng tới bất kỳ ngày nào, và nút **"Ngày gần nhất"**. Ngày trống sẽ báo
  rõ và gợi ý dùng ◀ ▶.
- **Tổng quan ngày**: gói gọn mọi thứ về ngày đó trong một mục —
  - Tổng giờ · Số phiên · Độ dài/phiên, kèm **So sánh** với *cùng thứ tuần trước* và *trung
    bình các ngày cùng thứ* (hợp với lịch theo tuần), Mốc trong ngày (phiên đầu/cuối, trải
    dài) và phân bổ theo buổi.
  - **Top 3 Danh mục** và **Top 3 Dự án** trong ngày (hiện toàn bộ nếu chưa đủ 3).
  - **Phân bố độ dài phiên** (thanh theo 5 nhóm 10/25/50/90′).
  - **Dòng thời gian trong ngày**: trục 0–24h, mỗi phiên là một khối tô màu theo dự án, nền
    dải buổi; phủ thêm **lớp mờ "khung giờ điển hình của thứ này"** để thấy hôm đó lệch nhịp ra sao.
- **Ghi chú ngày** (nhật ký): bố cục 2 cột (Thứ/ngày trái, nội dung phải), không còn khung viền
  quanh thẻ. Cột phải theo thứ tự cố định: **chip lịch** (kèm nhãn nhỏ "Lịch", từ Đồng bộ lịch)
  → **chip phần đọc sách/Gundam** (nhóm theo tên sách/series nếu có nhiều cuốn cùng ngày, từ
  Tải lên từ Reminder) → **ghi chú**. Mặc định chỉ hiện **ghi chú đã lưu** (hoặc trạng thái
  trống) kèm nút **Thêm ghi chú**/**Sửa ghi chú**; bấm nút mới mở **trình soạn thảo** ngay
  trong trang với **Cập nhật** / **Huỷ** / **Xoá**. Trình soạn (Quill) có thanh công cụ và
  **phím tắt quen thuộc** (⌘/Ctrl+B đậm, I nghiêng, U gạch chân; **Tab** thụt lề bullet):
  đậm/nghiêng/gạch chân, màu chữ & tô nền, danh sách + thụt lề nhiều cấp, liên kết. Mỗi ngày
  **một ghi chú**, lưu **độc lập với phiên** (ngày không có hoạt động vẫn ghi được; import/xoá
  phiên không làm mất ghi chú), và **hiện lại** ở mục *Nhật ký* của tuần/tháng tương ứng.
- **Phân bổ thời gian** (biểu đồ tròn) và **Danh sách phiên** (STT · Bắt đầu – Kết thúc · Độ dài · Danh mục).
- **Ngày này năm trước**: khớp **cùng ngày/tháng ở các năm trước** (gộp từ cả phiên lẫn ghi chú);
  mỗi năm hiện số liệu nhanh (Giờ · Số phiên · TB) và ghi chú nếu có. Mục này dày dần theo thời gian.

### 5. 🗂️ Báo cáo theo dự án
Tập trung vào **một Nhóm (Danh mục) hoặc một Dự án** chọn ở ô thả xuống.
Trong danh sách, mỗi lựa chọn được ghi rõ *“· Nhóm”* hay *“· Dự án”*, dự án con thụt vào
dưới nhóm cha. Gồm: Tổng quan → (Nhật ký đọc, nếu khớp 1 cuốn sách đã đồng bộ Reminders) →
Biểu đồ lịch → Xu hướng theo thời gian → Phân bố độ dài phiên → Bảng số liệu.

Mục **“Nhật ký đọc”** chỉ hiện khi Dự án đang chọn khớp tên với 1 cuốn sách đã có dữ liệu từ
Apple Reminders (so tên Dự án với phần “Tên sách” trong “Tác giả - Tên sách”) — hiện trọn lịch
sử phần/chương đã đọc của đúng cuốn đó, một dòng mỗi ngày (Thứ/ngày bên trái, tên các phần đã
đọc bên phải), bấm vào Thứ/ngày để nhảy sang đúng Báo cáo ngày hôm đó. Xem mục
[Đồng bộ lịch & đọc sách](#đồng-bộ-lịch--đọc-sách-tuỳ-chọn) để thiết lập.

### 6. 📚 Nhật ký đọc sách
Trang riêng dành cho việc đọc sách **theo trình tự, đọc dở rồi đọc tiếp**, **gộp 2 nguồn dữ
liệu**: phiên tập trung Forest (mặc định gom mọi Dự án thuộc nhóm `Reading`) và phần/chương đã
đọc nạp từ **Apple Reminders**. Một cuốn sách chỉ cần có mặt ở **một trong hai nguồn** là
đủ để lên trang — cột thuộc nguồn còn thiếu hiện dấu **“—”**. Reminder List tên bắt đầu bằng
“Gundam” không tính vào trang này (xem mục 7). Mỗi cuốn là một dòng *Bắt đầu / Gần nhất / Số
ngày / Ngày đọc / Tổng giờ / Số phiên / Giờ·tuần / Số phần đã đọc / Phần gần nhất / Trạng
thái* — cột **Số ngày** luôn tính được kể cả với cuốn chỉ theo dõi qua Reminders (chưa bấm giờ
Forest), kèm **timeline trình tự đọc** và tóm tắt (số cuốn, số phần đã đọc, TB giờ & ngày mỗi
cuốn, cuốn ngốn nhiều giờ nhất…). Trạng thái *“Đang đọc / Đã xong”* suy ra tự động từ độ mới
của hoạt động gần nhất (phiên Forest **hoặc** phần Reminders hoàn thành, lấy mốc gần hơn).
Tên nhóm và các dự án cần loại trừ (vd `The Economist`, `Gundam`) khai báo ở đầu `app.py`
(`BOOKS_GROUP`, `BOOKS_EXCLUDE`). Trang này **chỉ tính toán để hiển thị, không tạo hay sửa dữ
liệu Forest** (dữ liệu Reminders được ghi khi tải file ở mục Chuẩn bị dữ liệu, không phải ở
trang này) nên không ảnh hưởng tới sao lưu/khôi phục theo cách khác các trang khác đang có.

Ngoài trang riêng này, phần/chương đã đọc còn hiện xen kẽ ở mục **Nhật ký** của **Báo cáo
ngày/tuần/tháng** — xem mục 2-4 ở trên.

### 7. 🤖 Gundam
Y hệt cấu trúc trang **Nhật ký đọc sách** (mục 6) nhưng cho các series anime Gundam đang xem,
đổi chữ cho đúng ngữ cảnh (“series” thay “cuốn sách”, “xem”/“tập” thay “đọc”/“phần”). Nguồn dữ
liệu: Reminder List tên **“Gundam - Tên series”** (mỗi list = 1 series) + phiên Forest gắn tag
**“Gundam”**. Vì Forest không tách Dự án riêng theo từng series, app tự **suy ra series đang
xem của mỗi ngày có phiên Gundam** bằng cách ghép với lần hoàn thành reminder (ở bất kỳ series
nào) **gần ngày đó nhất** (trước hoặc sau) — nên số giờ mỗi series chỉ mang tính tương đối,
chính xác nhất khi xem lần lượt từng series thay vì xen kẽ nhiều series trong cùng vài ngày.

### 8. ⚙️ Chuẩn bị dữ liệu
Nơi bạn nạp và quản lý dữ liệu:
1. **Dữ liệu đầu vào** — 2 nguồn dữ liệu, gộp chung một mục:
   - **Tải lên từ Forest**: tải file CSV xuất từ Forest. Ứng dụng tự nhận diện cột, chỉ giữ
     các phiên *thành công*, tự tính thời lượng và **bỏ qua các phiên trùng** (theo thời gian
     bắt đầu/kết thúc). Sau khi chọn file, app **xem trước** ("Đọc được N phiên hợp lệ — bỏ X
     thất bại, Y unset…") rồi mới cần bấm **Xác nhận cập nhật dữ liệu**; xong sẽ báo tóm tắt
     *"Đã thêm N phiên mới…"*. Nhờ vậy bạn có thể tải lại nhiều lần mà không sợ nhân đôi.
   - **Đồng bộ lịch** *(tuỳ chọn)*: kéo appointment từ 1 lịch Apple Calendar cụ thể (qua
     CalDAV) về app, hiện kèm giờ bắt đầu ở Báo cáo ngày và Nhật ký.
   - **Tải lên từ Reminder** *(tuỳ chọn)*: nạp tiến độ đọc sách/xem Gundam từ Apple Reminders
     — tải lên file do 1 Shortcut trên iPhone/Mac xuất ra (không cần CalDAV/iCloud). Mỗi
     Reminder List là 1 cuốn sách/series, mỗi Reminder hoàn thành là 1 phần/tập đã đọc/xem.
     Xem mục [Đồng bộ lịch & đọc sách](#đồng-bộ-lịch--đọc-sách-tuỳ-chọn) để thiết lập.
2. **Phân loại** — gán **Dự án → Nhóm (Danh mục)** ngay trong **một bảng duy nhất**: chọn
   nhóm cho từng dự án ở cột *Nhóm*, gõ tên ở ô **"Tạo nhóm mới"** để thêm lựa chọn, để
   trống nghĩa là bỏ phân loại, rồi bấm **Lưu phân loại**. Phía trên có cảnh báo *"Còn N dự
   án chưa phân loại…"* (hoặc báo đã gán hết) để biết còn gì cần làm.
3. **Dữ liệu làm việc hiện tại** — bảng tương tác toàn bộ phiên đang lưu: **bấm tiêu đề cột
   để sắp xếp**, **tích chọn nhiều dòng rồi xoá** từng phiên rác. Phiên đã xoá được ghi nhớ
   và **không bị nạp lại** khi tải file Forest mới (kể cả khi file đó vẫn còn phiên này).
4. **Quản lý hệ thống** — **Sao lưu** (một nút *Tải bản sao lưu* → file `.zip` gồm dữ liệu,
   phân loại, danh sách đã xoá, ghi chú **và appointment lịch**), **Khôi phục** (nạp lại
   từ chính file `.zip` đó, có xem trước nội dung + cảnh báo ghi đè), **Làm mới** (xoá toàn bộ
   dữ liệu — cần tích xác nhận).

### 9. ❓ Hướng dẫn
Trang **Hướng dẫn & Giải thích** ngay trong app: giải thích chi tiết **mọi số liệu, biểu đồ và
tính năng** (Số liệu tổng quan, các biểu đồ, Dòng thời gian trong ngày, Ghi chú, Nhật ký đọc sách,
Gundam, Chuẩn bị dữ liệu…), **kèm ảnh minh hoạ** cho từng phần và hộp **Mẹo** gợi ý cách dùng
hữu ích. Ảnh minh hoạ nằm trong `assets/help/`.

---

## Quy trình bắt đầu nhanh

1. **Xuất dữ liệu từ Forest**: trong app Forest, vào phần xuất dữ liệu và lấy file CSV
   (có các cột *Tag/Project*, *Start Time*, *End Time*, *Is Success*).
2. Mở dashboard → tab **Chuẩn bị dữ liệu** → mục **1. Dữ liệu đầu vào** → phần **Tải lên từ
   Forest** → chọn file → bấm **Xác nhận cập nhật dữ liệu**.
3. Sang mục **2. Phân loại** để gom các dự án vào nhóm (ví dụ *Toán*, *Lập trình* → *Học tập*):
   chọn nhóm cho từng dự án trong bảng rồi bấm **Lưu phân loại**. Bước này không bắt buộc,
   nhưng giúp các báo cáo theo nhóm có ý nghĩa hơn.
4. Quay lại **Thống kê chung** và khám phá. Định kỳ xuất CSV mới từ Forest rồi tải lên lại
   để cập nhật — dữ liệu cũ vẫn được giữ, phần trùng tự loại bỏ, phiên bạn đã xoá không quay lại.
5. Thỉnh thoảng vào **Quản lý hệ thống → Tải bản sao lưu** để lấy file `.zip` phòng khi cần.

> 💡 Dữ liệu được lưu trên **Supabase** (Postgres ngoài, miễn phí) — bền vững qua các lần
> khởi động lại/redeploy, xem được từ nhiều máy/điện thoại qua cùng một URL. App **bắt buộc**
> phải cấu hình Supabase mới chạy được (xem mục [Thiết lập Supabase](#thiết-lập-supabase-bắt-buộc)
> bên dưới) — không còn chế độ lưu file CSV cục bộ. Mục **Sao lưu** vẫn đóng gói toàn bộ dữ
> liệu (`database.csv`, `mapping.csv`, `deleted.csv`, `notes.csv`) thành một file `.zip` để
> tải về phòng khi cần, dù dữ liệu gốc nằm trên Supabase.

---

## Thiết lập Supabase (bắt buộc)

App cần một project Supabase (Postgres miễn phí) để lưu dữ liệu. Làm 1 lần duy nhất, mất
khoảng 5 phút, không cần biết lập trình:

1. Vào **[supabase.com](https://supabase.com)** → **Start your project** → đăng nhập bằng
   GitHub (nhanh nhất) hoặc email.
2. Bấm **New project**: đặt tên bất kỳ (vd `forest-dashboard`), đặt **database password**
   (Supabase tự sinh cũng được, chỉ cần lưu lại — không phải khoá dùng trong app), chọn
   **Region** gần bạn nhất, gói **Free**. Bấm **Create new project**, đợi khoảng 1-2 phút để
   khởi tạo.
3. Vào **SQL Editor** (biểu tượng ở sidebar trái) → **New query** → dán toàn bộ nội dung file
   [`supabase_schema.sql`](supabase_schema.sql) → bấm **Run**. Xong bước này là có đủ 4 bảng
   dữ liệu.
4. Vào **Project Settings** (bánh răng ở sidebar) → **API** → copy 2 giá trị:
   - **Project URL** (dạng `https://xxxx.supabase.co`)
   - Khoá **anon public** (trong mục "Project API keys" — **không lấy** `service_role`)
5. Sao chép `.streamlit/secrets.toml.example` thành `.streamlit/secrets.toml`, điền 2 giá trị
   trên vào `SUPABASE_URL` / `SUPABASE_KEY` (file này đã có trong `.gitignore`, không commit
   lên git).

> ⚠️ Mặc định app không có lớp đăng nhập, ai có URL app cũng xem/sửa được dữ liệu — chỉ nên
> chia sẻ URL app với người bạn tin tưởng, hoặc bật đăng nhập Google ở mục
> [Đăng nhập Google (tuỳ chọn)](#đăng-nhập-google-tuỳ-chọn) bên dưới. Project Supabase free
> tier cũng tự "ngủ" (pause) sau khoảng 7 ngày không có hoạt động API; mở app lên gặp lỗi kết
> nối thì vào dashboard Supabase bấm un-pause (không mất dữ liệu, mất khoảng 1 phút).

### Deploy lên Streamlit Community Cloud (miễn phí)

1. Push code lên GitHub.
2. Vào [share.streamlit.io](https://share.streamlit.io), tạo app mới trỏ vào `app.py` của repo.
3. Ở phần **Secrets** của app, dán `SUPABASE_URL` và `SUPABASE_KEY` (nội dung giống file
   `secrets.toml` ở bước 5 phía trên). Streamlit Cloud tự cài `requirements.txt`, không cần
   cấu hình gì thêm.

---

## Đăng nhập Google (tuỳ chọn)

App vốn không có lớp đăng nhập — nếu bạn không phiền việc "ai có URL cũng vào được" thì có thể
bỏ qua mục này. Nếu muốn khoá app chỉ cho đúng 1 tài khoản Google của bạn (khuyến nghị khi deploy
lên Streamlit Cloud, vì URL là công khai), làm theo các bước sau — khoảng 10 phút, không cần biết
lập trình:

1. Vào **[console.cloud.google.com](https://console.cloud.google.com)** → đăng nhập bằng Gmail
   của bạn → tạo project mới (đặt tên bất kỳ, vd `forest-dashboard`).
2. Vào **APIs & Services → OAuth consent screen**: chọn **User Type = External** → điền App
   name/support email/developer email (đều dùng Gmail của bạn) → Save qua các bước còn lại. Ở
   mục **Test users**, bấm **Add users** → thêm đúng Gmail của bạn. App ở trạng thái "Testing"
   (chưa submit Google duyệt công khai) nên **chỉ email trong danh sách Test users mới đăng
   nhập được** — đây là lớp khoá chính, người khác dù biết URL app cũng không đăng nhập được.
3. Vào **Credentials → Create Credentials → OAuth client ID**: Application type = **Web
   application**. Ở **Authorized redirect URIs**, thêm đúng:
   `https://<tên-app-của-bạn>.streamlit.app/oauth2callback` (thêm cả
   `http://localhost:8501/oauth2callback` nếu có chạy thử ở máy local). Bấm **Create** → copy
   **Client ID** và **Client secret** hiện ra (chỉ xem được 1 lần lúc này).
4. Điền vào `.streamlit/secrets.toml` (xem `.streamlit/secrets.toml.example`):
   ```toml
   ALLOWED_EMAIL = "gmail-cua-ban@gmail.com"

   [auth]
   redirect_uri = "https://<tên-app-của-bạn>.streamlit.app/oauth2callback"
   cookie_secret = "một chuỗi ngẫu nhiên dài, tự nghĩ ra, dùng để ký cookie phiên đăng nhập"
   client_id = "<Client ID vừa copy>"
   client_secret = "<Client secret vừa copy>"
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
   ```
   Nếu deploy Streamlit Cloud, dán y hệt các dòng trên vào phần **Secrets** của app trên đó.
5. Mở lại app: sẽ hiện màn hình "Đăng nhập bằng Google" trước khi vào được nội dung. Đăng xuất ở
   nút cuối mục **"5. Quản lý hệ thống"** (tab Tuỳ biến).

Không điền mục `[auth]` này thì app chạy như cũ, không có cổng đăng nhập nào.

---

## Đồng bộ lịch & đọc sách (tuỳ chọn)

Mục **"1. Dữ liệu đầu vào"** (tab Chuẩn bị dữ liệu) có 2 tính năng tuỳ chọn, **độc lập nhau**
— bỏ qua tính năng nào không dùng, phần còn lại của app vẫn hoạt động bình thường:

- **Đồng bộ lịch**: kéo appointment từ 1 lịch cụ thể trong Apple Calendar (mặc định tên
  `Work`) về app qua **CalDAV**, hiện kèm giờ bắt đầu ở Báo cáo ngày và Nhật ký. Mỗi lần đồng
  bộ cũng dọn sạch appointment đã bị xoá trên Apple Calendar khỏi app (không chỉ thêm mới).
  Cần tạo App-Specific Password + điền secrets (xem bên dưới).
- **Tải lên từ Reminder**: nạp tiến độ đọc sách/xem Gundam từ Apple Reminders — mỗi
  **Reminder List** là 1 cuốn sách/series, mỗi **Reminder đã tick hoàn thành** trong list đó
  là 1 phần/tập đã đọc/xem. **Không dùng CalDAV** (Reminder List lưu "Trên iPhone của tôi",
  cục bộ không đồng bộ iCloud, sẽ không bao giờ thấy được qua CalDAV) — thay vào đó dùng 1
  **Shortcut** trên iPhone/Mac đọc thẳng dữ liệu Reminders trên máy rồi xuất ra file tải lên
  tay, thấy được cả list cục bộ lẫn iCloud. Không cần App-Specific Password/secrets gì thêm.

### Đồng bộ lịch (CalDAV)

1. Vào **appleid.apple.com** → đăng nhập → **Sign-In and Security** → **App-Specific
   Passwords** → tạo mới, đặt tên bất kỳ (vd `forest-dashboard`). Copy chuỗi mật khẩu hiện ra
   (dạng `xxxx-xxxx-xxxx-xxxx`) — **đây không phải mật khẩu Apple ID thật**, chỉ dùng riêng cho
   kết nối này, có thể thu hồi bất kỳ lúc nào mà không ảnh hưởng tài khoản chính.
2. Chạy đoạn SQL `create table work_calendar...` trong file
   [`supabase_schema.sql`](supabase_schema.sql) (nếu đã chạy cả file lúc thiết lập Supabase thì
   bảng này đã có sẵn, không cần chạy lại).
3. Thêm 3 giá trị vào `.streamlit/secrets.toml` (local) và Secrets của app trên Streamlit
   Cloud (production):
   ```toml
   ICLOUD_USERNAME = "your_apple_id@example.com"
   ICLOUD_APP_PASSWORD = "xxxx-xxxx-xxxx-xxxx"   # mật khẩu ứng dụng vừa tạo ở bước 1
   ICLOUD_WORK_CALENDAR = "Work"                  # đổi nếu lịch bạn đặt tên khác
   ```
4. Mở app → tab **Chuẩn bị dữ liệu** → mục **"1. Dữ liệu đầu vào"** → phần **"Đồng bộ lịch"**
   → chọn khoảng ngày → bấm **"Đồng bộ ngay"**.

> ⚠️ Mật khẩu ứng dụng chỉ nên dùng cho đúng mục đích này. Nếu nghi ngờ bị lộ, thu hồi ngay
> tại appleid.apple.com và tạo mật khẩu mới, không ảnh hưởng gì tới tài khoản Apple ID chính.

### Tải lên từ Reminder (đọc sách / Gundam)

1. Chạy đoạn SQL `create table reading_log...` trong
   [`supabase_schema.sql`](supabase_schema.sql) (nếu chưa có, tương tự bước trên).
2. Đặt tên từng Reminder List theo đúng quy ước để app nhận diện được:
   - Sách: `"Tác giả - Tên sách"` (vd `"George R. R. Martin - A Game of Thrones"`).
   - Series Gundam (hiện ở tab **Gundam** riêng, không tính vào tab Sách): `"Gundam - Tên
     series"` (vd `"Gundam - Gundam Wing"`).
3. Tạo 1 Shortcut trên **iPhone/Mac** (ứng dụng Shortcuts) đọc thẳng dữ liệu Reminders trên máy
   (thấy được cả list "Trên iPhone của tôi" lẫn iCloud):
   - Thêm action **"Find Reminders"**: để trống bộ lọc List (lấy tất cả danh sách), thêm điều
     kiện lọc **Completed = Yes** (chỉ lấy reminder đã hoàn thành).
   - **Repeat with Each** trên kết quả trên. Trong vòng lặp: lấy **List**, **Title**,
     **Completion Date** của từng reminder (action "Get Details of Reminders"), định dạng
     Completion Date thành text bằng action **"Format Date"** (Custom Format: `yyyy-MM-dd
     HH:mm:ss`), rồi ghép 3 giá trị thành 1 dòng dạng `List|Title|CompletionDate` (dấu `|`,
     không phải dấu phẩy) và gom vào 1 biến danh sách (action "Add to Variable").
   - Sau vòng lặp: nối dòng header `list|title|completed_date` lên đầu, rồi **Combine Text**
     toàn bộ (Separator: New Line) thành 1 file text.
   - **Save File** (Files app) hoặc **Share** (AirDrop/gửi email cho chính mình) để lấy file đó
     ra máy tính.
4. Mở app → tab **Chuẩn bị dữ liệu** → mục **"1. Dữ liệu đầu vào"** → phần **"Tải lên từ
   Reminder"** → chọn file vừa xuất → xem trước → **"Xác nhận nạp dữ liệu"** (thay thế toàn bộ
   dữ liệu Đọc sách/Gundam hiện có bằng nội dung file này — chạy lại Shortcut và tải lên bất cứ
   khi nào Reminders có thay đổi).

---

## Tuỳ chỉnh giao diện (tuỳ chọn)

Mục **"5. Giao diện"** (tab Tuỳ biến) cho phép chọn 1 trong 8 màu accent (thay cho màu teal mặc
định) — áp dụng ngay cho nút, biểu đồ đơn sắc và bảng nhiệt trên toàn app. Lựa chọn được lưu vào
bảng `settings` mới trong Supabase.

1. Chạy đoạn SQL `create table settings...` trong [`supabase_schema.sql`](supabase_schema.sql)
   (nếu đã chạy cả file lúc thiết lập Supabase thì bảng này đã có sẵn, không cần chạy lại).
2. Mở app → tab **Tuỳ biến** → mục **"5. Giao diện"** → bấm 1 màu để áp dụng ngay.

Tính năng này hoàn toàn tuỳ chọn: nếu bảng `settings` chưa tồn tại hoặc Supabase gặp lỗi, app tự
rơi về màu teal mặc định thay vì báo lỗi.

---

## Cài đặt & chạy ứng dụng

Yêu cầu: **Python 3.9+** và đã hoàn tất [Thiết lập Supabase](#thiết-lập-supabase-bắt-buộc) ở trên.

```bash
# 1. Cài thư viện
pip install -r requirements.txt

# 2. Chạy ứng dụng
streamlit run app.py
```

Ứng dụng sẽ mở trong trình duyệt (mặc định `http://localhost:8501`). Nếu chưa cấu hình
`.streamlit/secrets.toml`, app sẽ báo lỗi rõ ràng ngay khi mở thay vì crash khó hiểu.

Thư viện sử dụng (xem `requirements.txt`): **Streamlit**, **pandas**, **Plotly**, **Altair**,
**supabase-py**, **caldav** (chỉ dùng khi bật đồng bộ lịch/đọc sách). Cấu hình giao diện (màu
nền, màu nhấn, font) nằm ở `.streamlit/config.toml`.

---

## Câu hỏi thường gặp

**“Số cây” khác gì “số giờ”?**
Số cây là *số lần* tập trung (số phiên); số giờ là *tổng thời lượng*. Một ngày có thể trồng
nhiều cây ngắn hoặc ít cây dài.

**Vì sao trung bình/ngày trông cao hơn dự kiến?**
Vì mẫu số chỉ gồm những ngày *có hoạt động*, không tính các ngày trống.

**Tải cùng một file nhiều lần có bị nhân đôi không?**
Không. Các phiên trùng (cùng thời gian bắt đầu và kết thúc) sẽ được tự loại bỏ.

**Tôi đã xoá một phiên, nhưng file Forest mới vẫn còn nó — tải lên có bị thêm lại không?**
Không. Khi bạn xoá một phiên ở mục **Dữ liệu làm việc hiện tại**, app ghi nhớ phiên đó và
sẽ **bỏ qua nó** ở những lần tải file sau. Khi nạp, app báo rõ *"… N phiên đã xoá trước
đó"*. (Muốn nhận lại tất cả thì dùng **Làm mới** để xoá sạch rồi nạp lại từ đầu.)

**Tôi xoá một Tag trong Forest cho dự án đã kết thúc — có mất nhãn cũ không?**
Không, miễn là phiên đó **đã được nạp vào app lúc còn tag**. Khi tag bị xoá trong Forest,
các phiên đó thành *Unset*; lúc nạp file mới, app **bỏ qua phiên Unset** và **giữ nguyên
nhãn cũ** đã lưu. Nên bạn có thể yên tâm dọn bớt Tag trong Forest.

**Dự án chưa gán nhóm thì sao?**
Nó vẫn xuất hiện bình thường và được coi như một nhóm độc lập trùng tên với dự án đó.

**Tuần bắt đầu từ thứ mấy?**
Thứ Hai, kết thúc Chủ Nhật (chuẩn ISO).

**Làm sao xoá sạch để bắt đầu lại?**
Vào **Chuẩn bị dữ liệu → Quản lý hệ thống → Làm mới**, tích xác nhận rồi xoá (thao tác này
cũng xoá danh sách phiên đã xoá). Nên bấm **Tải bản sao lưu** trước khi xoá.
