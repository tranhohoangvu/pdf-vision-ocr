# ⚡ PDF Vision OCR - Chuyển đổi & Trích xuất PDF Đa Định Dạng

![PDF Vision OCR](assets/thumbnail.png)

Ứng dụng nhận diện ký tự quang học (OCR) thông minh, chuyển đổi tài liệu PDF tiếng Việt (kể cả PDF scan & chụp ảnh) sang **Word (.docx)**, **Excel (.xlsx)**, **Searchable PDF (.pdf)** và **Markdown (.md)** với khả năng bảo toàn 100% tiếng Việt có dấu và cấu trúc bảng biểu.

Cung cấp **hai giao diện song song**:
- 🖥️ **Web UI** – Giao diện Streamlit Dark Mode trực quan, dễ dùng.
- 🔌 **REST API** – FastAPI backend chuẩn doanh nghiệp, tích hợp Swagger UI.

---

## ✨ Tính năng nổi bật

- **Bảo toàn 100% tiếng Việt có dấu & Bảng biểu**: Tự động phát hiện Digital PDF và chuyển đổi giữ nguyên cấu trúc bảng và toàn bộ dấu tiếng Việt từ tài liệu gốc.
- **Tích hợp Vision AI (Google Gemini Flash)**: Nhận diện chữ viết tay, hóa đơn mờ hoặc tài liệu phức tạp với mô hình Google Gemini 2.5 Flash, tự động fallback về PaddleOCR nếu mất mạng/hết quota.
- **Xử lý hàng loạt (Batch Processing & Master ZIP)**: Tải lên nhiều file PDF cùng lúc, đóng gói toàn bộ kết quả vào một Master ZIP kèm báo cáo tổng kết (`batch_summary.txt`).
- **Tiền xử lý ảnh thông minh (OpenCV)**:
  - **Tự động xoay thẳng (Auto-Deskew)**: Phát hiện góc nghiêng và chỉnh thẳng văn bản.
  - **Khử bóng râm & Tẩy nền (Shadow Removal)**: Triệt tiêu bóng tay khi chụp bằng điện thoại.
  - **Tăng tương phản nét chữ (CLAHE)**: Làm rõ chữ mờ hoặc mực nhạt.
- **Xuất đa định dạng (Multi-Format Export)**:
  - 📄 **Word (.docx)** · 📊 **Excel (.xlsx)** · 🔍 **Searchable PDF (.pdf)** · 📝 **Markdown (.md)** · 📦 **Gói ZIP (.zip)**
- **REST API chuẩn doanh nghiệp (FastAPI)**: Swagger UI tại `/docs`, hỗ trợ tích hợp hệ thống qua HTTP.
- **Không phụ thuộc Poppler ngoài**: Sử dụng PyMuPDF render trực tiếp trong RAM.

---

## 🚀 Cài đặt & Chạy cục bộ

### Yêu cầu hệ thống
- Python 3.10, 3.11 hoặc 3.12 (khuyên dùng 64-bit).

### 1. Khởi tạo môi trường ảo
```powershell
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Cài đặt thư viện
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Chạy Streamlit Web UI
```bash
streamlit run src/app.py
```
Mở trình duyệt: `http://localhost:8501`

### 4. Chạy FastAPI REST Backend
```bash
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## 🔌 REST API – Hướng dẫn sử dụng

### `GET /api/v1/health` — Kiểm tra trạng thái

```bash
curl http://localhost:8000/api/v1/health
```

```json
{
  "status": "ok",
  "version": "1.0.0",
  "pymupdf_available": true,
  "pdf2docx_available": true,
  "ocr_engine": "PaddleOCR (vi)"
}
```

---

### `POST /api/v1/inspect` — Phân tích nhanh file PDF

```bash
curl -X POST "http://localhost:8000/api/v1/inspect" \
     -F "file=@document.pdf"
```

```json
{
  "filename": "document.pdf",
  "total_pages": 5,
  "has_digital_text": true,
  "char_count": 3821,
  "sample_text": "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM...",
  "recommended_mode": "digital"
}
```

---

### `POST /api/v1/convert` — Chuyển đổi PDF

**Chuyển đổi tự động sang Word (cURL):**
```bash
curl -X POST "http://localhost:8000/api/v1/convert" \
     -F "file=@document.pdf" \
     -F "mode=auto" \
     -F "export_formats=docx" \
     --output result.docx
```

**Chuyển đổi với Gemini AI, xuất trọn bộ ZIP (cURL):**
```bash
curl -X POST "http://localhost:8000/api/v1/convert" \
     -F "file=@scan.pdf" \
     -F "mode=gemini" \
     -F "gemini_api_key=YOUR_KEY_HERE" \
     -F "export_formats=docx,xlsx,md,pdf" \
     -F "dpi=300" \
     -F "deskew=true" \
     --output result.zip
```

**Ví dụ Python `requests`:**
```python
import requests

with open("document.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/v1/convert",
        files={"file": ("document.pdf", f, "application/pdf")},
        data={
            "mode": "auto",          # auto | digital | ocr | gemini
            "export_formats": "docx,xlsx",
            "dpi": 200,
            "deskew": False,
        },
    )

# Lưu kết quả (ZIP nếu nhiều định dạng)
with open("result.zip", "wb") as out:
    out.write(response.content)
```

**Tham số `convert` đầy đủ:**

| Tham số | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `file` | file | bắt buộc | File PDF cần xử lý |
| `mode` | string | `auto` | `auto` / `digital` / `ocr` / `gemini` |
| `export_formats` | string | `docx` | Phân tách bởi dấu phẩy: `docx,xlsx,md,pdf` |
| `pages` | string | (tất cả) | Phạm vi trang, ví dụ: `1-3,5` |
| `dpi` | int | `200` | 72–400. Khuyến nghị 300 cho chữ viết tay |
| `deskew` | bool | `false` | Tự động nắn thẳng trang nghiêng |
| `remove_shadow` | bool | `false` | Xóa bóng đổ trước OCR |
| `enhance_contrast` | bool | `false` | Tăng tương phản CLAHE |
| `gemini_api_key` | string | _(rỗng)_ | Bắt buộc khi `mode=gemini` |

---

## 🐳 Docker

### Chạy đơn lẻ

```bash
# Build image
docker build -t pdf-vision-ocr .

# Chạy Web UI (Streamlit)
docker run -d -p 8501:8501 -e APP_MODE=web pdf-vision-ocr

# Chạy REST API (FastAPI)
docker run -d -p 8000:8000 -e APP_MODE=api pdf-vision-ocr

# Với Gemini API Key
docker run -d -p 8000:8000 \
  -e APP_MODE=api \
  -e GEMINI_API_KEY=your_key_here \
  pdf-vision-ocr
```

### Chạy với Docker Compose

```bash
# Chỉ Web UI
docker compose --profile web up -d

# Chỉ REST API
docker compose --profile api up -d

# Cả hai cùng lúc
docker compose --profile full up -d

# Với Gemini Key (tạo file .env trước)
echo "GEMINI_API_KEY=your_key_here" > .env
docker compose --profile full up -d
```

---

## 📂 Cấu trúc thư mục

```text
pdf-vision-ocr/
├── .streamlit/
│   └── config.toml                # Cấu hình giao diện & upload Streamlit
├── assets/
│   └── thumbnail.png              # Ảnh chụp giao diện ứng dụng
├── src/
│   ├── core/
│   │   ├── exporters.py           # Xuất DOCX, XLSX, Searchable PDF, Markdown, TXT, ZIP
│   │   ├── image_preprocessor.py  # Deskew (xoay thẳng), khử bóng, tăng tương phản (CLAHE)
│   │   ├── ocr_engine.py          # Bộ điều phối: Digital, PaddleOCR, Gemini Vision AI
│   │   └── vision_ai_engine.py    # Tích hợp Google Gemini Flash Vision API
│   ├── api.py                     # FastAPI REST API Backend
│   └── app.py                     # Streamlit Web UI Frontend
├── docker-compose.yml             # Docker Compose orchestration (profiles: web, api, full)
├── docker-entrypoint.sh           # Entrypoint script chuyển đổi linh hoạt Web/API
├── Dockerfile                     # Dockerfile dual-mode cho cả Web và API
├── requirements.txt               # Danh sách phụ thuộc Python
└── README.md                      # Tài liệu hướng dẫn sử dụng
```

---

## 💡 Mẹo tối ưu hóa kết quả OCR

1. **Tài liệu mờ, chữ nhỏ**: Chọn **300 DPI** và bật **Tăng tương phản (CLAHE)**.
2. **Tài liệu chụp nghiêng bằng điện thoại**: Bật **Auto-Deskew** + **Khử bóng**.
3. **Chữ viết tay hoặc scan siêu khó**: Chọn chế độ **✨ Google Gemini Flash (Vision AI)**, dán API Key miễn phí từ [Google AI Studio](https://aistudio.google.com/app/apikey) và dùng 300 DPI.
4. **Nhiều file cùng lúc**: Dùng tab **Batch** trên Web UI hoặc gọi API `/convert` nhiều lần song song.
