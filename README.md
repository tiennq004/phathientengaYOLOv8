<h2 align="center">
    <a href="https://dainam.edu.vn/vi/khoa-cong-nghe-thong-tin">
    🎓 Faculty of Information Technology (DaiNam University)
    </a>
</h2>

<h2 align="center">  
   XÂY DỰNG HỆ THỐNG PHÁT HIỆN TÉ NGÃ TRONG KHU VỰC
</h2>

<div align="center">
    <p align="center">
        <img src="https://github.com/tiennq004/cds_nha_tro-sinh_vien_ai/blob/main/img/aiotlab_logo.png" alt="AIoTLab Logo" width="170"/>
        <img src="https://github.com/tiennq004/cds_nha_tro-sinh_vien_ai/blob/main/img/fitdnu_logo.png" alt="FIT DNU Logo" width="180"/>
        <img src="https://github.com/tiennq004/cds_nha_tro-sinh_vien_ai/blob/main/img/dnu_logo.png" alt="DaiNam University Logo" width="200"/>
    </p>

[![AIoTLab](https://img.shields.io/badge/AIoTLab-green?style=for-the-badge)](https://www.facebook.com/DNUAIoTLab)
[![Faculty of Information Technology](https://img.shields.io/badge/Faculty%20of%20Information%20Technology-blue?style=for-the-badge)](https://dainam.edu.vn/vi/khoa-cong-nghe-thong-tin)
[![DaiNam University](https://img.shields.io/badge/DaiNam%20University-orange?style=for-the-badge)](https://dainam.edu.vn)
</div>

---


## 1. Mục tiêu của hệ thống

  Hệ thống được xây dựng nhằm phát hiện hành vi té ngã của con người trong khu vực giám sát bằng kỹ thuật thị giác máy tính (Computer Vision), phân tích tư thế cơ thể (Pose Estimation) và mô hình AI để đưa ra cảnh báo theo thời gian thực.

  Hệ thống có khả năng hoạt động với camera trực tiếp hoặc video có sẵn, hỗ trợ nhận diện trạng thái bất thường của con người, từ đó gửi cảnh báo nhanh chóng tới người dùng nhằm giảm thiểu rủi ro khi xảy ra sự cố té ngã.

### 🎯 Các mục tiêu chính

- **Phát hiện té ngã thời gian thực**  
  Hệ thống sử dụng video hoặc camera để theo dõi chuyển động cơ thể, nhận diện hành vi té ngã dựa trên tư thế người và sự thay đổi vị trí cơ thể theo thời gian.

- **Phân tích tư thế cơ thể chính xác**  
  Ứng dụng MediaPipe Pose để nhận diện các điểm khớp trên cơ thể người (body landmarks), kết hợp mô hình AI nhằm phân tích tư thế đứng, ngồi hoặc té ngã.

- **Cảnh báo đa phương thức**  
  Khi phát hiện té ngã, hệ thống có thể:
  - Gửi Email cảnh báo tới người dùng.
  - Gửi tín hiệu HTTP tới thiết bị IoT ESP32 để kích hoạt LED/Buzzer cảnh báo.
  - Hiển thị trạng thái phát hiện trên giao diện Web Dashboard.

- **Lưu trữ và theo dõi dữ liệu sự kiện**  
  Các sự kiện té ngã có thể được ghi lại để phục vụ giám sát, đánh giá hoặc kiểm tra sau này.

### ⚙️ Thành phần hệ thống

### 🔹 1. Module xử lý hình ảnh & AI

**Pose Estimation (MediaPipe Pose)**  
- Trích xuất các điểm khớp trên cơ thể người.
- Phân tích tư thế đứng, ngồi hoặc té ngã.
- Hỗ trợ nhận diện chuyển động theo thời gian thực.

**Computer Vision (OpenCV)**  
- Đọc video hoặc camera.
- Hiển thị khung hình phát hiện.
- Khoanh vùng đối tượng và hiển thị trạng thái hệ thống.

**Mô hình AI phát hiện té ngã**  
- Phân tích dữ liệu tư thế.
- Dự đoán trạng thái bình thường hoặc té ngã.
- Giảm nhiễu và tăng độ chính xác nhận diện.

### 🔹 2. Module cảnh báo & IoT

**Email Alert System**  
- Gửi Email cảnh báo tự động.
- Hỗ trợ gửi hình ảnh khi phát hiện té ngã.

**IoT ESP32 Alert**  
- Máy tính gửi HTTP request tới ESP32 trong mạng LAN.
- ESP32 kích hoạt LED và buzzer để tạo cảnh báo vật lý.

**Web Dashboard**  
- Hiển thị giao diện đăng nhập người dùng.
- Theo dõi trạng thái hệ thống.
- Kiểm tra kết nối ESP32 và quản lý hoạt động phát hiện.

### 💡 Điểm nổi bật của hệ thống

- 🚨 Cảnh báo đa nền tảng: Web + Email + IoT ESP32.
- ⚡ Phát hiện theo thời gian thực từ video/camera.
- 🔒 Quản lý cấu hình an toàn bằng file `.env`.
- 🌐 Có giao diện Web Dashboard hỗ trợ quản trị.
- 🧠 Ứng dụng AI và kỹ thuật thị giác máy tính trong thực tế.
- 💻 Có thể triển khai trên máy tính cá nhân với chi phí thấp.

---

## ⚙️ 2. Công nghệ và công cụ sử dụng

```text
Input (Camera / Video)
        ↓
OpenCV + MediaPipe Pose + AI Model
        ↓
Fall Detection
        ↓
Email Alert + ESP32 IoT + Web Dashboard
```

### 🖥️ Công nghệ xử lý chính

#### Python 3.x
Ngôn ngữ lập trình chính của toàn bộ hệ thống.

#### OpenCV
- Đọc camera/video.
- Xử lý khung hình.
- Hiển thị kết quả phát hiện thời gian thực.

#### MediaPipe Pose
- Nhận diện các điểm khớp trên cơ thể.
- Phân tích tư thế người.

#### NumPy
- Tính toán dữ liệu số học.
- Hỗ trợ xử lý tọa độ và dữ liệu tư thế.

#### Scikit-learn
- Huấn luyện mô hình AI phục vụ phát hiện té ngã.
- Phân loại trạng thái cơ thể.

### 🌐 Web Application

#### Flask
- Xây dựng Web Dashboard.
- Quản lý đăng nhập người dùng.
- Điều khiển trạng thái hệ thống.

#### HTML / CSS / JavaScript
- Thiết kế giao diện người dùng.
- Hiển thị dữ liệu trực quan.

### 📡 Công nghệ cảnh báo

#### SMTP Gmail
- Gửi Email cảnh báo tự động.

#### HTTP LAN → ESP32
- Gửi tín hiệu cảnh báo tới thiết bị IoT.

#### Python-dotenv
- Quản lý cấu hình hệ thống bằng biến môi trường.

### 🛠️ Công cụ phát triển

- IDE: Visual Studio Code / PyCharm
- Arduino IDE (lập trình ESP32)
- Git & GitHub (quản lý mã nguồn)
- Windows / Linux / macOS

---

## 🧩 3. Hình ảnh các chức năng
<p align="center">
  <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/so_do_kien_truc_he_thong.png" alt="Ảnh 1" width="800"/>
</p> 
<p align="center">
  <em>Hình 1: Sơ đồ kiến trúc hệ thống  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/giao_dien_trang_dang_nhap.png" alt="Ảnh 2" width="800"/>
</p> 
<p align="center">
  <em>Hình 2: Giao diện trang đăng nhập  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/giao_dien_admin_1.png" alt="Ảnh 3" width="800"/>
</p> 
<p align="center">
  <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/giao_dien_admin_2.png" alt="Ảnh 4" width="800"/>
</p> 
<p align="center">
  <em>Hình 3: Giao diện Admin  </em>
    
</p>
<p align="center">
  <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/giao_dien_nguoi_dung_1.png" alt="Ảnh 5" width="800"/>
</p> 
<p align="center">
  <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/giao_dien_nguoi_dung_2.png" alt="Ảnh 6" width="800"/>
</p> 
<p align="center">
  <em>Hình 4: Giao người dùng  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/ket_noi_esp32_phat_hien_canh_bao.png" alt="Ảnh 7" width="800"/>
</p> 
<p align="center">
  <em>Hình 5: Kết nối Esp32 phát hiện té ngã để nhận cảnh báo  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/so_do_he_thong_IoT_khi_chua_phat_hien_te_nga.jpg" alt="Ảnh 8" width="800"/>
</p> 
<p align="center">
  <em>Hình 6: Sơ dồ hệ thống IoT khi chưa phát hiện té ngã  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/so_do_he_thong_IoT_khi_phat_hien_te_nga.jpg" alt="Ảnh 9" width="800"/>
</p> 
<p align="center">
  <em>Hình 7: Sơ dồ hệ thống IoT khi chưa phát hiện té ngã  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/phat_hien_nguoi_te_nga.jpg" alt="Ảnh 10" width="800"/>
</p> 
<p align="center">
  <em>Hình 8: Hệ thống hiển thị cảnh báo người bị té ngã  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/led_lcd_hien_thi_so_lan_canh_bao.jpg" alt="Ảnh 11" width="800"/>
</p> 
<p align="center">
  <em>Hình 9: Led LCD hiển thị số lần cảnh báo  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/gui_canh_bao_ve_email.png" alt="Ảnh 12" width="800"/>
</p> 
<p align="center">
  <em>Hình 10: Cảnh báo gửi về gmail   </em>
</p>
## ⚙️ 4. Các bước cài đặt

### Bước 1. Clone project

```bash
git clone https://github.com/tiennq004/phathientengaYOLOv8.git
cd phathientengaYOLOv8
```

### Bước 2. Cài đặt môi trường

Cài đặt Python phiên bản từ **3.9 trở lên**.

Khuyến khích tạo môi trường ảo:

```bash
python -m venv venv
```

Kích hoạt môi trường:

Windows:

```bash
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

### Bước 3. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

### Bước 4. Cấu hình biến môi trường

Tạo file `.env` từ `.env.example`

Ví dụ:

```env
SMTP_USER=your_email@gmail.com
SMTP_APP_PASSWORD=your_app_password
ALERT_TO_EMAIL=receiver@gmail.com

IOT_ENABLED=true
ESP32_ALERT_URL=http://192.168.1.50/alert
```

### Bước 5. Chạy Web Dashboard

```bash
python web_app.py
```

Mặc định truy cập:

```text
http://127.0.0.1:5000
```

### Bước 6. Chạy hệ thống phát hiện té ngã

Sử dụng Webcam:

```bash
python fall_live.py --camera 0
```

Hoặc chạy bằng video:

```bash
python fall_live.py --video video_test.mp4
```

### Bước 7. Kiểm tra hoạt động

Khi hệ thống phát hiện té ngã:

- Hiển thị cảnh báo trên màn hình.
- Gửi Email cảnh báo.
- Gửi tín hiệu tới ESP32.
- Dashboard cập nhật trạng thái.

---

## 👥 5. Thực hiện

**Sinh viên thực hiện:** Nguyễn Quang Tiến

**Lớp:** CNTT 16-03

**Khoa:** Công nghệ Thông tin

**Trường:** Đại học Đại Nam

**Giảng viên hướng dẫn:** ThS. Nguyễn Văn Nhân

© 2026 – Khoa Công Nghệ Thông Tin, Trường Đại học Đại Nam
