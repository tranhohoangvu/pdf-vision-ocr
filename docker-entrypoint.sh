#!/bin/sh
# docker-entrypoint.sh – Khởi chạy ứng dụng theo biến APP_MODE

set -e

case "$APP_MODE" in
  api)
    echo "▶  Starting FastAPI REST API on port ${API_PORT}..."
    exec uvicorn src.api:app \
        --host "${API_HOST}" \
        --port "${API_PORT}" \
        --workers 2
    ;;
  web|*)
    echo "▶  Starting Streamlit Web UI on port ${STREAMLIT_SERVER_PORT}..."
    exec streamlit run src/app.py \
        --server.address="${STREAMLIT_SERVER_ADDRESS}" \
        --server.port="${STREAMLIT_SERVER_PORT}" \
        --server.headless=true
    ;;
esac
