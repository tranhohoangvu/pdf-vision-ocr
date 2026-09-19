FROM python:3.12-slim

# ─────────────────────────────────────────────────────────
# Biến môi trường
# APP_MODE=web   → chạy Streamlit  (port 8501)
# APP_MODE=api   → chạy FastAPI    (port 8000)
# ─────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_MODE=web \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    API_HOST=0.0.0.0 \
    API_PORT=8000

WORKDIR /app

# Cài đặt các thư viện hệ thống cần thiết cho OpenCV và MuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Sao chép mã nguồn ứng dụng
COPY src/ ./src/

# Mở cả hai port
EXPOSE 8501 8000

# Script khởi chạy chọn chế độ theo APP_MODE
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
