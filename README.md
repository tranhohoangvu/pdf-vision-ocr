# 📄 PDF Vision OCR - Chuyển đổi PDF sang Word

![PDF Vision OCR](assets/thumbnail.png)

Ứng dụng nhận diện ký tự quang học (OCR) thông minh, chuyển đổi tài liệu PDF quét (scanned PDF) và tài liệu dạng ảnh tiếng Việt sang file Microsoft Word (`.docx`) có thể chỉnh sửa được.

---

## ✨ Tính năng nổi bật

- **Nhận diện Tiếng Việt chính xác cao**: Tích hợp mô hình học sâu **PaddleOCR 2.7.3**, hỗ trợ tiếng Việt (`lang='vi'`) và tự động cân chỉnh góc xoay nghiêng (`use_angle_cls=True`).
- **Không phụ thuộc Poppler bên ngoài**: Ứng dụng tích hợp **PyMuPDF** để render trang PDF trực tiếp trong bộ nhớ với tốc độ cao, hoạt động mượt mà trên Windows mà không cần cài đặt phần mềm ngoài.
- **Gom đoạn thông minh (Smart Paragraph Merging)**: Tự động phân tích khoảng cách và lề của các dòng chữ để ghép thành đoạn văn hoàn chỉnh, tránh hiện tượng ngắt dòng vụn vặt khi xuất sang file Word.
- **Giao diện trực quan & Hiện đại**:
  - Xem trước trang tài liệu PDF trực tiếp trên web trước khi chuyển đổi.
  - Tùy chỉnh chất lượng quét (150 DPI - Nhanh, 200 DPI - Cân bằng, 300 DPI - Sắc nét).
  - Lựa chọn phạm vi trang linh hoạt (toàn bộ hoặc dải trang tùy chọn như `1-3, 5`).
  - Xem trước văn bản đã trích xuất theo từng trang kèm bảng thống kê độ tin cậy (confidence score) trước khi tải file Word.
- **Hỗ trợ đóng gói Docker**: Sẵn sàng triển khai nhanh chóng trên server chỉ với một lệnh.

---

## 🚀 Hướng dẫn cài đặt & Chạy cục bộ

### Yêu cầu hệ thống
- Python 3.10, 3.11 hoặc 3.12 (khuyên dùng 64-bit).

### 1. Khởi tạo môi trường ảo
Trên Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Trên Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Cài đặt các thư viện cần thiết
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Khởi chạy ứng dụng Web
```bash
streamlit run src/app.py
```
Sau khi chạy, mở trình duyệt truy cập: `http://localhost:8501`.

---

## 🐳 Khởi chạy bằng Docker

Bạn có thể chạy ứng dụng mà không cần cài đặt môi trường Python cục bộ:

```bash
# Xây dựng Docker image
docker build -t pdf-vision-ocr .

# Chạy container
docker run -d -p 8501:8501 --name pdf-ocr-app pdf-vision-ocr
```
Truy cập giao diện tại: `http://localhost:8501`.

---

## 📂 Cấu trúc thư mục

```text
pdf-vision-ocr/
├── assets/
│   └── thumbnail.png          # Ảnh xem trước giao diện dự án
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   └── ocr_engine.py      # Lõi xử lý: Smart Hybrid (Digital PDF & OCR Vision)
│   ├── app.py                 # Ứng dụng giao diện web Streamlit
│   └── __init__.py
├── requirements.txt           # Danh sách thư viện phụ thuộc
├── Dockerfile                 # Đóng gói container
├── .gitignore
└── README.md                  # Hướng dẫn sử dụng dự án
```

---

## 💡 Mẹo tối ưu hóa kết quả OCR

1. **Đối với tài liệu mờ, chữ nhỏ**: Trong thanh bên (Sidebar), chọn chất lượng **300 DPI** để tăng cường độ nét của ảnh trước khi đưa vào mô hình OCR.
2. **Đối với tài liệu nhiều trang**: Bạn có thể xử lý thử một vài trang đầu (ví dụ nhập `1-2` vào ô "Trang tùy chọn") để kiểm tra độ chính xác trước khi chuyển đổi toàn bộ tài liệu.
