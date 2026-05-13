<h2 align="center">
    <a href="https://dainam.edu.vn/vi/khoa-cong-nghe-thong-tin">
    🎓 Faculty of Information Technology (DaiNam University)
    </a>
</h2>

<h2 align="center">  
   XÂY DỰNG HỆ THỐNG PHÁT HIỆN TÉ NGÃ CỦA CON NGƯỜI TỪ DỮ LIỆU VIDEO DỰ TRÊN KỸ THUẬT THỊ GIÁC MÁY TÍNH VÀ PHÂN TÍCH TƯ THẾ CƠ THỂ
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

- Phát hiện té ngã thời gian thực: Sử dụng camera giám sát hoặc dữ liệu video để nhận diện hành vi té ngã của con người một cách tự động.

- Phân tích tư thế chính xác: Kết hợp kỹ thuật Pose Estimation (MediaPipe) và HOG Descriptor để trích xuất khung xương, phân tích góc nghiêng thân người và tỉ lệ khung hình.

- Cảnh báo tức thời: Tự động gửi thông báo qua Email kèm hình ảnh và video ghi lại khoảnh khắc té ngã để người thân/nhân viên y tế kịp thời ứng phó.

- Giảm thiểu báo động giả: Sử dụng các thuật toán lọc chuyển động (Motion Filtering) và kiểm tra sự thay đổi đột ngột của trọng tâm (Drop threshold).

⚙️ Thành phần hệ thống

🔹 1. Modul sử lí hình ảnh

- Pose Estimator: Sử dụng MediaPipe để nhận diện 17 điểm chốt trên cơ thể, tính toán góc nghiêng của thân (torso angle).

- HOG Detector: Nhận diện người trong khung hình làm phương án dự phòng khi Pose Estimator bị che khuất.

- Motion Tracker: Phân tích sự thay đổi vị trí theo trục dọc (Y) để xác định vận tốc rơi.

🔹 2. Modul cảnh báo & Lưu trữ

- Email Alert: Tích hợp giao thức SMTP để gửi mail tự động qua Gmail (hỗ trợ đính kèm ảnh và clip mp4).

- Local Logger: Lưu trữ video clip các vụ té ngã vào thư mục outputs/falls để làm bằng chứng đối chiếu.

💡 Điểm nổi bật

- 💬 Cảnh báo đa phương thức: Gửi email ảnh ngay lập tức và video clip ngay sau khi sự cố kết thúc.

- 🏃 Xử lý luồng tối ưu: Hỗ trợ đa luồng (threading) cho việc gửi email, không gây giật lag luồng xử lý ảnh chính.

- 🔒 Bảo mật: Quản lý thông tin nhạy cảm (Email, Password) qua biến môi trường .env.

- 💻 Tương thích cao: Hoạt động tốt trên cả Webcam trực tiếp và các file video định dạng phổ biến (mp4, avi).

## ⚙️ 2. Công nghệ và công cụ sử dụng

    Input (Camera / Video File)
       ↓
    Processing (OpenCV + MediaPipe + HOG)
       ↓
    Alert (SMTP Service + Threading)

🖥️ Công nghệ xử lý chính

 - Python 3.x: Ngôn ngữ lập trình chính.

 - OpenCV: Xử lý khung hình, vẽ bounding box và ghi video.

 - MediaPipe: Trích xuất tọa độ các điểm chốt cơ thể (landmarks).

 - NumPy: Tính toán đại số tuyến tính và góc hình học.

💻 Dịch vụ và giao thức

 - SMTP (Gmail): Gửi thông báo khẩn cấp.

 - Python-dotenv: Quản lý cấu hình hệ thống.

 - Argparse: Cung cấp giao diện dòng lệnh linh hoạt.

🛠️ Công cụ phát triển

 - IDE: Visual Studio Code / PyCharm.

 - Thư viện yêu cầu: opencv-python, mediapipe, python-dotenv, numpy.

 - Hệ điều hành: Windows / Linux / macOS.
---

## 🧩 3. Hình ảnh các chức năng


<p align="center">
  <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/ket_qua_huan_luyen_du_lieu.jpg" alt="Ảnh 1" width="800"/>
</p> 
<p align="center">
  <em>Hình 1: Kết quả sau khi huấn luyện dữ liệu  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/video_2_not_fall.png" alt="Ảnh 2" width="800"/>
    <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/video_1_not_fall.png" alt="Ảnh 3" width="800"/>
</p> 
<p align="center">
  <em>Hình 2: Sau khi chạy code, khi chưa bị té ngã  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/video_2_falled.png" alt="Ảnh 4" width="800"/>
    <img src="https://github.com/tiennq004/phathientengaYOLOv8/blob/main/img/video_1_falled.png" alt="Ảnh 5" width="800"/>
</p> 
<p align="center">
  <em>Hình 3: Khi té ngã  </em>
</p>
---

## ⚙️ 4. Các bước cài đặt

 - Các bước cài đặt và chạy chương trình

Bước 1. Giải nén dự án

 - Giải nén mã nguồn vào một thư mục trên máy tính.

Bước 2. Cài đặt môi trường

 - Cài đặt Python (phiên bản ≥ 3.9).

 - Tạo môi trường ảo (khuyến khích): python -m venv venv.

Bước 3. Cài đặt thư viện

 - Chạy lệnh cài đặt các thư viện cần thiết:

        pip install -r requirements.txt

Bước 4. Cấu hình biến môi trường

 - Tạo file .env từ file .env.example.

 - Điền thông tin Gmail App Password để hệ thống có quyền gửi mail:

        SMTP_USER=your_email@gmail.com
        
        SMTP_APP_PASSWORD=your_app_password
        
        ALERT_TO_EMAIL=recipient_email@gmail.com

Bước 5. Chạy chương trình

 - Chạy với Webcam:

        python fall_live.py --camera 0
 
 - Chạy với tệp video có sẵn:

        python fall_live.py --video video_test.mp4

Bước 6. Kiểm tra hoạt động

 - Khi có người té ngã, màn hình sẽ hiển thị dòng chữ "FALL DETECTED" màu đỏ.

 - Kiểm tra hộp thư đến của Email để nhận cảnh báo.

## 👥 5. Thực hiện

- Nguyễn Quang Tiến

- Lớp: CNTT 16-03

- Khoa: Công nghệ thông tin

- Trường: Đại học Đại Nam

**Giảng viên hướng dẫn:** Ths. Lê Trung Hiếu  

© 2025 – Khoa Công Nghệ Thông Tin, Trường Đại học Đại Nam.
