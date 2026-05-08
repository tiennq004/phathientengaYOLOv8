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

- Tối ưu hóa trải nghiệm tìm kiếm phòng trọ bằng AI và bản đồ tương tác.

- Kết nối người thuê và người cho thuê trong cùng nền tảng, đảm bảo minh bạch, tiện lợi.

- Tự động gợi ý phòng trọ phù hợp với nhu cầu và vị trí người dùng nhờ hệ thống AI thông minh.

- Tích hợp chatbot tư vấn, so sánh phòng trọ, và tìm người ở ghép để mở rộng trải nghiệm.

⚙️ Thành phần hệ thống

🔹 1. Người thuê (Client)

- Tìm kiếm phòng trọ theo vị trí, giá, tiện nghi, bản đồ tương tác.

- Xem chi tiết, so sánh, đánh giá và lưu phòng yêu thích.

- Giao tiếp trực tiếp với chủ trọ qua tính năng nhắn tin.

- Sử dụng AI chatbot để được gợi ý phòng trọ phù hợp.

- Có thể đăng yêu cầu tìm người ở ghép hoặc xem các bài đăng tương tự.

🔹 2. Người cho thuê (Host)

- Đăng bài cho thuê phòng, quản lý thông tin, cập nhật, xóa bài đăng.

- Quản lý danh sách phòng, xem tin nhắn từ người thuê.

- Cập nhật trạng thái phòng (đã thuê/chưa thuê).

- Quản lý hồ sơ cá nhân và bảo mật tài khoản.

💡 Điểm nổi bật

- 💬 AI Chatbot hỗ trợ người thuê tìm nhà nhanh chóng.

- 🗺️ Tích hợp bản đồ OpenStreetMap & Nominatim API cho phép xem vị trí phòng thực tế.

- 🔒 Bảo mật tài khoản với JWT Authentication.

- 📊 Hệ thống gợi ý thông minh dựa trên dữ liệu hành vi và từ khóa tìm kiếm.

- 💻 Giao diện thân thiện, hiện đại xây dựng bằng React + Bootstrap.

- ⚙️ Hệ thống Backend mạnh mẽ với Node.js + Express + MySQL.

## ⚙️ 2. Công nghệ và công cụ sử dụng

    Frontend (React + Vite)
       ↓
    Backend (Node.js + Express)
       ↓
    Database (MySQL / MariaDB)

🖥️ Frontend

- React 18, Vite, Bootstrap, Axios

- Tích hợp Leaflet + OpenStreetMap để hiển thị vị trí phòng

- Giao diện hiện đại, hỗ trợ AI Chatbot và tìm kiếm nâng cao

💻 Backend

- Node.js + Express.js, MySQL

- JWT Authentication đảm bảo bảo mật

- Tích hợp Google Gemini API và Nominatim API (Geocoding)

- Quản lý người dùng, phòng trọ, tin nhắn, gợi ý AI

🛠️ Công cụ phát triển

- IDE: Visual Studio Code

- Node.js: v14+

- CSDL: MySQL 5.7+ hoặc MariaDB

- API Key: Google Gemini

- Hệ điều hành: Windows / Linux / macOS


---

## 🧩 3. Hình ảnh các chức năng


<p align="center">
  <img src="https://github.com/tiennq004/cds_nha_tro-sinh_vien_ai/blob/main/img/giao_dien_chinh.png" alt="Ảnh 1" width="800"/>
</p> 
<p align="center">
  <em>Hình 1: Giao diện chính của hệ thống  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/cds_nha_tro-sinh_vien_ai/blob/main/img/giao_dien_form_dang_ky.png" alt="Ảnh 2" width="800"/>
</p> 
<p align="center">
  <em>Hình 2: Giao diện form đăng ký  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/cds_nha_tro-sinh_vien_ai/blob/main/img/giao_dien_form_dang_nhap.png" alt="Ảnh 3" width="800"/>
</p> 
<p align="center">
  <em>Hình 3: Giao diện form đăng nhập  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/cds_nha_tro-sinh_vien_ai/blob/main/img/giao_dien_quan_ly_phong_tro.png" alt="Ảnh 4" width="800"/>
</p> 
<p align="center">
  <em>Hình 4: Giao diện quản lý phòng trọ  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/cds_nha_tro-sinh_vien_ai/blob/main/img/so_sanh_phong_tro.png" alt="Ảnh 5" width="800"/>
</p> 
<p align="center">
  <em>Hình 5: So sánh phòng trọ  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/cds_nha_tro-sinh_vien_ai/blob/main/img/them_tt_phong_tro.png" alt="Ảnh 6" width="800"/>
</p> 
<p align="center">
  <em>Hình 6: Thêm thông tin phòng trọ  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/LTM_he_thong_canh_bao_thoi_gian_thuc/blob/main/docs/giao_dien_server.png" alt="Ảnh 7" width="800"/>
</p> 
<p align="center">
  <em>Hình 7: Nhắn tin trao đổi thông tin giữa người thuê và người cho thuê  </em>
</p>

<p align="center">
  <img src="https://github.com/tiennq004/cds_nha_tro-sinh_vien_ai/blob/main/img/xem_tro_tren_ggmap.png" alt="Ảnh 8" width="800"/>
</p> 
<p align="center">
  <em>Hình 8: Xem địa chỉ trọ trên Google Map  </em>
</p>


---

## ⚙️ 4. Các bước cài đặt

1. Các bước cài đặt và chạy chương trình

- Bước 1. Giải nén dự án

    - Giải nén file BTL.zip vào một thư mục bất kỳ.

- Bước 2. Cài đặt môi trường

    - Cài Node.js (phiên bản ≥ 18).

    - Cài MongoDB (nếu dự án sử dụng cơ sở dữ liệu này).

- Bước 3. Cài đặt thư viện

    - Mở Terminal hoặc CMD tại thư mục gốc của dự án và chạy lệnh:

            npm install

    - Sau đó di chuyển vào thư mục client để cài thư viện cho giao diện:

            cd client
    
            npm install


- Bước 4. Cấu hình biến môi trường

    - Tạo file .env trong thư mục chính (nếu chưa có).

    - Điền các thông tin kết nối, ví dụ:

            PORT=5000

            MONGO_URI=mongodb://localhost:27017/tenCSDL

            JWT_SECRET=secret_key

- Bước 5. Chạy chương trình

    - Mở hai cửa sổ terminal:
    
    - Cửa sổ 1 (backend):

            npm start

    - Cửa sổ 2 (frontend):

            cd client

            npm run dev

    - Sau khi khởi chạy, mở trình duyệt và truy cập địa chỉ:

            👉 http://localhost:5173
      
             (hoặc cổng hiển thị trong terminal).

- Bước 6. Kiểm tra hoạt động

    - Đăng ký / Đăng nhập người dùng.

    - Kiểm tra các chức năng chính: thêm, sửa, xóa, tìm kiếm, upload...

## 👥 5. Nhóm thực hiện

- Nhóm 9: Nguyễn Quang Tiến & Hoàng Công Sơn

- Lớp: CNTT 16-03

- Khoa: Công nghệ thông tin

- Trường: Đại học Đại Nam

**Giảng viên hướng dẫn:** ThS. Nguyễn Văn Nhân  

© 2025 – Khoa Công Nghệ Thông Tin, Trường Đại học Đại Nam.
