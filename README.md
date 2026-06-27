# 🌲 Forest Dashboard

Bảng điều khiển (dashboard) trực quan hoá dữ liệu tập trung từ ứng dụng **Forest** —
giúp bạn nhìn lại mình đã dành thời gian cho việc gì, vào lúc nào, đều đặn ra sao.

Ứng dụng đọc file CSV bạn xuất ra từ Forest, tự phân tích và hiển thị thành các biểu đồ,
bảng số liệu theo nhiều góc nhìn (tổng quan, theo tháng, theo tuần, theo nhóm).
Giao diện theo phong cách iOS/macOS: tối giản, dùng thẻ kính mờ và tông xanh `#007aff`.

---

## Mục lục

- [Khái niệm cốt lõi](#khái-niệm-cốt-lõi)
- [Các chỉ số & biểu đồ nghĩa là gì](#các-chỉ-số--biểu-đồ-nghĩa-là-gì)
- [Hướng dẫn sử dụng theo từng trang](#hướng-dẫn-sử-dụng-theo-từng-trang)
- [Quy trình bắt đầu nhanh](#quy-trình-bắt-đầu-nhanh)
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
- **Thời gian TB/ngày** — trung bình số giờ mỗi *ngày có hoạt động*.
- **Số cây TB/ngày** — trung bình số phiên mỗi *ngày có hoạt động*.
- **Thời gian TB/tuần**, **Số cây TB/tuần** *(tab Báo cáo theo nhóm)* — trung bình theo
  số *tuần có hoạt động*.
- **Cập nhật gần nhất** *(tab Thống kê chung)* — thời điểm phiên gần nhất kết thúc, kèm
  khoảng cách so với hiện tại (ví dụ *“1 ngày 3 giờ trước”*).

Ở **Báo cáo tháng** và **Báo cáo tuần**, mỗi thẻ còn có 2 dòng so sánh:

- **vs Tháng trước / vs Tuần trước** — chênh lệch so với kỳ liền trước.
- **vs Trung bình** — chênh lệch so với mức trung bình của tất cả các kỳ khác.

> Màu **xanh lá** nghĩa là cao hơn (tốt hơn), **đỏ** nghĩa là thấp hơn.

Ở **Báo cáo theo nhóm**, phần Tổng quan còn có:

- **Mốc thời gian**: *Ngày đầu tiên*, *Ngày gần nhất*, *Số ngày có hoạt động* của nhóm/dự án.
- **Tuần này** (làm nổi bật màu xanh): thời gian và số cây của nhóm/dự án trong tuần hiện
  tại — chỉ hiện khi tuần này có hoạt động.

- **Top 3 Danh mục / Dự án** — ba nhóm hoặc dự án bạn dành nhiều giờ nhất.

### Các biểu đồ

- **Xu hướng theo thời gian** — cột (hoặc đường) thể hiện số giờ theo thời gian. Bạn có
  thể *gộp theo* **Ngày / Tuần / Tháng** và tô màu *phân loại theo* **Danh mục / Dự án**.
- **Phân bổ thời gian** — biểu đồ tròn cho thấy tỉ trọng thời gian giữa các nhóm/dự án
  trong kỳ.
- **Xu hướng làm việc theo khung giờ** — số giờ cộng dồn theo **giờ trong ngày (0h–23h)**,
  giúp nhận ra bạn tập trung tốt vào buổi sáng, chiều hay tối. Đường xanh là **tổng cộng**.
- **Biểu đồ lịch** (kiểu “đóng góp” của GitHub) — mỗi ô là một ngày; ô càng **xanh đậm**
  thì ngày đó càng nhiều giờ. Kèm theo 3 chỉ số chuỗi:
  - **Tổng cộng** — tổng số ngày có hoạt động.
  - **Chuỗi dài nhất** — số ngày liên tiếp dài nhất từng đạt được.
  - **Chuỗi hiện tại** — số ngày liên tiếp tính đến hôm nay (chỉ còn hiệu lực nếu hôm nay
    hoặc hôm qua bạn có hoạt động).
- **Lịch trồng cây theo giờ** *(tab Báo cáo tuần)* — trục ngang là các thứ trong tuần,
  trục dọc là giờ 0–24; mỗi thanh (“cây nến”) là một phiên, đặt đúng vào khung giờ thực
  tế và tô màu theo Danh mục. Đây là “thời khoá biểu” thực tế của tuần.

### Bảng số liệu

- Ở các tab tổng hợp: bảng dạng **ma trận** *Danh mục / Dự án × kỳ (Tuần/Tháng)*, ô càng
  xanh càng nhiều giờ, cột **Tổng** ở cuối.
- Ở **Báo cáo theo nhóm**: vì chỉ xem một nhóm/dự án nên bảng được tối ưu thành dạng
  **theo kỳ** — mỗi dòng là một Tuần/Tháng với *Số giờ*, *Số cây*, *Số ngày*, kèm dòng **Tổng**.

### Bộ lọc & điều hướng dùng chung

- **Khoảng thời gian**: `30 ngày · 90 ngày · 6 tháng · 1 năm · Tất cả` — lọc nhanh phạm vi
  dữ liệu (tính lùi từ ngày gần nhất). Phần *Xu hướng* và *Biểu đồ lịch* có bộ lọc riêng.
- **Chọn kỳ** (tab tháng/tuần): nút **◀ ▶** để lùi/tiến từng kỳ, ô thả xuống để nhảy nhanh,
  và nút lịch 🗓️ để **về thẳng kỳ hiện tại**.
- **Mọi mục đều gập/mở được**: bấm vào tiêu đề mục để thu gọn hoặc mở rộng.

---

## Hướng dẫn sử dụng theo từng trang

Thanh điều hướng nằm ngay dưới tiêu đề, gồm 5 trang:

### 1. 📊 Thống kê chung
Cái nhìn tổng thể toàn bộ dữ liệu.
1. **Tổng quan** — các thẻ số liệu chính + cập nhật gần nhất + Top 3.
2. **Biểu đồ lịch tổng quan** — lịch nhiệt + chuỗi ngày.
3. **Xu hướng theo thời gian** — chọn khoảng thời gian, cách gộp và cách phân loại.
4. **Xu hướng làm việc theo khung giờ** — bạn tập trung mạnh vào giờ nào.
5. **Bảng số liệu** — ma trận Danh mục/Dự án theo Tuần hoặc Tháng.

### 2. 🗓️ Báo cáo tháng
Phân tích sâu **một tháng cụ thể** (chọn ở thanh điều hướng kỳ): Tổng quan (kèm so sánh) →
Phân bổ thời gian → Xu hướng theo ngày trong tháng → Khung giờ → Bảng số liệu.

### 3. 🗓️ Báo cáo tuần
Tương tự báo cáo tháng nhưng cho **một tuần**, và có thêm mục **Lịch trồng cây theo giờ**
(thời khoá biểu thực tế của tuần).

### 4. 🗂️ Báo cáo theo nhóm
Tập trung vào **một Nhóm (Danh mục) hoặc một Dự án** chọn ở ô thả xuống.
Trong danh sách, mỗi lựa chọn được ghi rõ *“· Nhóm”* hay *“· Dự án”*, dự án con thụt vào
dưới nhóm cha. Gồm: Tổng quan → Biểu đồ lịch → Xu hướng theo thời gian → Bảng số liệu.

### 5. ⚙️ Chuẩn bị dữ liệu
Nơi bạn nạp và quản lý dữ liệu:
1. **Tải lên từ Forest** — tải file CSV xuất từ Forest. Ứng dụng tự nhận diện cột, chỉ giữ
   các phiên *thành công*, tự tính thời lượng và **bỏ qua các phiên trùng** (theo thời gian
   bắt đầu/kết thúc) nên bạn có thể tải lại nhiều lần mà không sợ nhân đôi.
2. **Phân loại** — tạo quy tắc gán **Dự án → Danh mục** (gom dự án vào nhóm). Có thể thêm/xoá
   quy tắc; bảng quy tắc hiện tại hiển thị bên cạnh.
3. **Dữ liệu làm việc hiện tại** — xem toàn bộ phiên đang lưu.
4. **Quản lý hệ thống** — **Tải về** (sao lưu file dữ liệu & quy tắc), **Khôi phục** (nạp lại
   từ file sao lưu), **Làm mới** (xoá toàn bộ dữ liệu — cần tích xác nhận).

---

## Quy trình bắt đầu nhanh

1. **Xuất dữ liệu từ Forest**: trong app Forest, vào phần xuất dữ liệu và lấy file CSV
   (có các cột *Tag/Project*, *Start Time*, *End Time*, *Is Success*).
2. Mở dashboard → tab **Chuẩn bị dữ liệu** → mục **1. Tải lên từ Forest** → chọn file →
   bấm **Xác nhận cập nhật dữ liệu**.
3. Sang mục **2. Phân loại** để gom các dự án vào nhóm (ví dụ *Toán*, *Lập trình* → *Học tập*).
   Bước này không bắt buộc, nhưng giúp các báo cáo theo nhóm có ý nghĩa hơn.
4. Quay lại **Thống kê chung** và khám phá. Định kỳ xuất CSV mới từ Forest rồi tải lên lại
   để cập nhật — dữ liệu cũ vẫn được giữ, phần trùng tự loại bỏ.
5. Thỉnh thoảng vào **Quản lý hệ thống → Tải về** để sao lưu phòng khi cần.

> 💡 Dữ liệu được lưu cục bộ trong các file `database.csv` (các phiên) và `mapping.csv`
> (quy tắc phân loại) ở thư mục chạy ứng dụng.

---

## Cài đặt & chạy ứng dụng

Yêu cầu: **Python 3.9+**.

```bash
# 1. Cài thư viện
pip install -r requirements.txt

# 2. Chạy ứng dụng
streamlit run app.py
```

Ứng dụng sẽ mở trong trình duyệt (mặc định `http://localhost:8501`).

Thư viện sử dụng (xem `requirements.txt`): **Streamlit**, **pandas**, **Plotly**, **Altair**.
Cấu hình giao diện (màu nền, màu nhấn, font) nằm ở `.streamlit/config.toml`.

---

## Câu hỏi thường gặp

**“Số cây” khác gì “số giờ”?**
Số cây là *số lần* tập trung (số phiên); số giờ là *tổng thời lượng*. Một ngày có thể trồng
nhiều cây ngắn hoặc ít cây dài.

**Vì sao trung bình/ngày trông cao hơn dự kiến?**
Vì mẫu số chỉ gồm những ngày *có hoạt động*, không tính các ngày trống.

**Tải cùng một file nhiều lần có bị nhân đôi không?**
Không. Các phiên trùng (cùng thời gian bắt đầu và kết thúc) sẽ được tự loại bỏ.

**Dự án chưa gán nhóm thì sao?**
Nó vẫn xuất hiện bình thường và được coi như một nhóm độc lập trùng tên với dự án đó.

**Tuần bắt đầu từ thứ mấy?**
Thứ Hai, kết thúc Chủ Nhật (chuẩn ISO).

**Làm sao xoá sạch để bắt đầu lại?**
Vào **Chuẩn bị dữ liệu → Quản lý hệ thống → Làm mới**, tích xác nhận rồi xoá. Nên **Tải về**
sao lưu trước khi xoá.
