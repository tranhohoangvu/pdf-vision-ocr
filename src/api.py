"""
PDF Vision OCR – REST API Backend (FastAPI)
==========================================
Khởi chạy:
    uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload

Endpoints:
    GET  /api/v1/health   - Kiểm tra trạng thái hệ thống
    POST /api/v1/inspect  - Phân tích nhanh file PDF
    POST /api/v1/convert  - Chuyển đổi PDF sang các định dạng khác
"""

import os
import sys

# Đảm bảo thư mục src/ luôn nằm trong sys.path dù chạy từ project root
# hay từ bên trong src/ (uvicorn src.api:app hoặc python api.py)
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import uuid
import shutil
import tempfile
from typing import List, Optional

os.environ["PYMUPDF_SUGGEST_LAYOUT_ANALYZER"] = "0"

try:
    import pymupdf
    sys.modules["fitz"] = pymupdf
    if hasattr(pymupdf, "no_recommend_layout"):
        pymupdf.no_recommend_layout()
except ImportError:
    pass

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from core.ocr_engine import OCREngine, HAS_PYMUPDF, HAS_PDF2DOCX

# ─────────────────────────────────────────────────────────
# App khởi tạo
# ─────────────────────────────────────────────────────────

app = FastAPI(
    title="PDF Vision OCR API",
    description=(
        "## 🔍 PDF Vision OCR – Chuyển đổi PDF thành văn bản số\n\n"
        "API chuyên nghiệp để:\n"
        "- Chuyển **PDF kỹ thuật số** (có text-layer) sang Word, Excel, Markdown.\n"
        "- Chuyển **PDF scan / chữ viết tay** bằng PaddleOCR hoặc **Google Gemini Vision AI**.\n"
        "- Xuất đa định dạng: `.docx`, `.xlsx`, `.md`, Searchable `.pdf`, hoặc trọn bộ `.zip`.\n\n"
        "### Xác thực\n"
        "Không cần token xác thực ở phiên bản hiện tại. "
        "Để dùng Gemini Vision AI, truyền `gemini_api_key` trong form body.\n\n"
        "### Rate Limits\n"
        "Không giới hạn theo phiên bản mặc định. Cấu hình qua reverse proxy nếu cần.\n"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "tranhohoangvu",
        "url": "https://github.com/tranhohoangvu/pdf-vision-ocr",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# CORS – cho phép tất cả origin (điều chỉnh khi deploy production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Engine singleton dùng chung
_engine = OCREngine()


# ─────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = Field(..., example="ok")
    version: str = Field(..., example="1.0.0")
    pymupdf_available: bool = Field(..., description="PyMuPDF (fitz) đã sẵn sàng")
    pdf2docx_available: bool = Field(..., description="pdf2docx đã sẵn sàng")
    ocr_engine: str = Field(..., example="PaddleOCR (vi)")


class InspectResponse(BaseModel):
    filename: str
    total_pages: int
    has_digital_text: bool = Field(..., description="PDF có text-layer hay là ảnh scan thuần")
    char_count: int = Field(..., description="Số ký tự phát hiện trên toàn bộ file")
    sample_text: str = Field(..., description="Đoạn văn bản mẫu (tối đa 200 ký tự)")
    recommended_mode: str = Field(
        ...,
        description="Phương thức chuyển đổi được khuyến nghị: 'digital', 'ocr', hoặc 'gemini'",
        example="digital",
    )


class ConvertResponse(BaseModel):
    filename: str
    mode_used: str
    total_pages_processed: int
    overall_confidence: float
    elapsed_seconds: float
    output_formats: List[str]
    download_url: str = Field(
        ...,
        description="URL tải file kết quả. Nếu nhiều định dạng sẽ là file .zip.",
    )


# ─────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────

def _cleanup_dir(path: str):
    """Xóa thư mục tạm sau khi response đã gửi xong."""
    try:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def _save_upload(upload: UploadFile, dest_dir: str) -> str:
    """Lưu UploadFile vào thư mục tạm, trả về đường dẫn đầy đủ."""
    safe_name = os.path.basename(upload.filename or "upload.pdf")
    dest_path = os.path.join(dest_dir, safe_name)
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return dest_path


# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────

@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    summary="Kiểm tra trạng thái hệ thống",
    tags=["System"],
)
def health_check():
    """
    Trả về trạng thái hoạt động của API và các thành phần phụ thuộc.

    Sử dụng endpoint này để:
    - Kiểm tra API đang chạy ổn định.
    - Xác nhận PyMuPDF và pdf2docx đã được cài đặt.
    - Tích hợp với health-check của Docker / Kubernetes.
    """
    return HealthResponse(
        status="ok",
        version=app.version,
        pymupdf_available=HAS_PYMUPDF,
        pdf2docx_available=HAS_PDF2DOCX,
        ocr_engine="PaddleOCR (vi)",
    )


@app.post(
    "/api/v1/inspect",
    response_model=InspectResponse,
    summary="Phân tích nhanh file PDF",
    tags=["Analysis"],
)
async def inspect_pdf(
    file: UploadFile = File(..., description="File PDF cần phân tích"),
):
    """
    Phân tích nhanh một file PDF và trả về thông tin cấu trúc.

    **Kết quả gồm:**
    - Tổng số trang
    - Có text-layer kỹ thuật số hay là ảnh scan thuần túy
    - Số ký tự phát hiện và đoạn văn bản mẫu
    - Khuyến nghị phương thức chuyển đổi tối ưu (`digital` / `ocr` / `gemini`)

    **Không lưu file** – file được xử lý trong bộ nhớ tạm và xóa ngay.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file PDF (.pdf).")

    tmp_dir = tempfile.mkdtemp(prefix="ocr_inspect_")
    try:
        pdf_path = _save_upload(file, tmp_dir)

        total_pages = _engine.get_pdf_page_count(pdf_path)
        has_digital, char_count, sample_text = _engine.check_has_digital_text(pdf_path)

        if has_digital and HAS_PDF2DOCX:
            recommended_mode = "digital"
        elif char_count == 0:
            recommended_mode = "gemini"
        else:
            recommended_mode = "ocr"

        return InspectResponse(
            filename=file.filename,
            total_pages=total_pages,
            has_digital_text=has_digital,
            char_count=char_count,
            sample_text=sample_text[:200] if sample_text else "",
            recommended_mode=recommended_mode,
        )
    finally:
        _cleanup_dir(tmp_dir)


@app.post(
    "/api/v1/convert",
    summary="Chuyển đổi PDF sang các định dạng văn bản",
    tags=["Conversion"],
    responses={
        200: {
            "description": "File kết quả (docx/xlsx/pdf/md/zip) được trả về dưới dạng stream.",
            "content": {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
                "application/pdf": {},
                "text/markdown": {},
                "application/zip": {},
            },
        },
        400: {"description": "Tham số không hợp lệ"},
        422: {"description": "Lỗi validation dữ liệu đầu vào"},
        500: {"description": "Lỗi xử lý nội bộ"},
    },
)
async def convert_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File PDF cần chuyển đổi"),
    mode: str = Form(
        default="auto",
        description=(
            "Phương thức OCR:\n"
            "- `auto`: Tự động phát hiện (Digital → digital, Scan → PaddleOCR)\n"
            "- `digital`: Ưu tiên trích xuất text-layer gốc, giữ bảng biểu hoàn hảo\n"
            "- `ocr`: Bắt buộc dùng PaddleOCR dù file có text-layer\n"
            "- `gemini`: Dùng Google Gemini Vision AI (cần `gemini_api_key`)"
        ),
    ),
    export_formats: str = Form(
        default="docx",
        description=(
            "Danh sách định dạng xuất, phân tách bởi dấu phẩy.\n"
            "Ví dụ: `docx,xlsx,md,pdf` hoặc `docx`.\n"
            "Nếu chọn nhiều hơn 1 định dạng, kết quả trả về là file `.zip`."
        ),
    ),
    pages: Optional[str] = Form(
        default=None,
        description="Phạm vi trang, ví dụ: `1-3,5`. Mặc định: toàn bộ trang.",
    ),
    dpi: int = Form(
        default=200,
        ge=72,
        le=400,
        description="Độ phân giải render (DPI). Khuyến nghị: 200 (chuẩn), 300 (chữ viết tay/mờ).",
    ),
    deskew: bool = Form(default=False, description="Tự động nắn thẳng trang bị nghiêng."),
    remove_shadow: bool = Form(default=False, description="Xóa bóng đổ và ố vàng trước OCR."),
    enhance_contrast: bool = Form(default=False, description="Tăng độ tương phản bằng CLAHE."),
    gemini_api_key: Optional[str] = Form(
        default=None,
        description="Google Gemini API Key (bắt buộc khi `mode=gemini`). Lấy miễn phí tại https://aistudio.google.com/app/apikey",
    ),
):
    """
    Chuyển đổi file PDF sang một hoặc nhiều định dạng văn bản.

    ### Ví dụ cURL

    **Chuyển đổi tự động sang Word:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/convert" \\
         -F "file=@document.pdf" \\
         -F "mode=auto" \\
         -F "export_formats=docx" \\
         --output result.docx
    ```

    **Chuyển đổi với Gemini AI, xuất trọn bộ ZIP:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/convert" \\
         -F "file=@scan.pdf" \\
         -F "mode=gemini" \\
         -F "gemini_api_key=YOUR_KEY_HERE" \\
         -F "export_formats=docx,xlsx,md,pdf" \\
         -F "dpi=300" \\
         --output result.zip
    ```

    ### Ví dụ Python

    ```python
    import requests

    with open("document.pdf", "rb") as f:
        response = requests.post(
            "http://localhost:8000/api/v1/convert",
            files={"file": ("document.pdf", f, "application/pdf")},
            data={"mode": "auto", "export_formats": "docx"},
        )

    with open("result.docx", "wb") as out:
        out.write(response.content)
    ```
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file PDF (.pdf).")

    valid_modes = {"auto", "digital", "ocr", "gemini"}
    if mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"mode không hợp lệ. Chọn một trong: {', '.join(sorted(valid_modes))}",
        )

    if mode == "gemini" and not (gemini_api_key and gemini_api_key.strip()):
        raise HTTPException(
            status_code=400,
            detail="Cần cung cấp `gemini_api_key` khi sử dụng mode='gemini'.",
        )

    # Parse export formats
    fmt_list = [f.strip().lower() for f in export_formats.split(",") if f.strip()]
    valid_fmts = {"docx", "xlsx", "md", "pdf"}
    invalid_fmts = set(fmt_list) - valid_fmts
    if invalid_fmts:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng không hợp lệ: {', '.join(invalid_fmts)}. Hợp lệ: {', '.join(sorted(valid_fmts))}",
        )
    if not fmt_list:
        fmt_list = ["docx"]

    # Tạo thư mục làm việc tạm
    job_id = uuid.uuid4().hex[:12]
    tmp_dir = tempfile.mkdtemp(prefix=f"ocr_convert_{job_id}_")

    try:
        pdf_path = _save_upload(file, tmp_dir)
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_docx_path = os.path.join(tmp_dir, f"{base_name}.docx")

        total_pages = _engine.get_pdf_page_count(pdf_path)
        page_indices = (
            _engine.parse_page_selection(pages, total_pages)
            if pages
            else list(range(total_pages))
        )

        result = _engine.convert_pdf_to_word(
            pdf_path=pdf_path,
            output_word_path=output_docx_path,
            mode=mode,
            gemini_api_key=gemini_api_key,
            dpi=dpi,
            page_indices=page_indices,
            export_formats=fmt_list,
            deskew=deskew,
            remove_shadow=remove_shadow,
            enhance_contrast=enhance_contrast,
        )

        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Xử lý thất bại, vui lòng thử lại.")

        output_files = result.get("output_files", {})

        # Quyết định file trả về
        if "zip" in output_files and os.path.exists(output_files["zip"]):
            return_path = output_files["zip"]
            media_type = "application/zip"
            filename_out = f"{base_name}_bundle.zip"
        elif len(fmt_list) == 1:
            fmt = fmt_list[0]
            if fmt in output_files and os.path.exists(output_files[fmt]):
                return_path = output_files[fmt]
                media_types = {
                    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "pdf": "application/pdf",
                    "md": "text/markdown; charset=utf-8",
                }
                media_type = media_types.get(fmt, "application/octet-stream")
                extensions = {"docx": ".docx", "xlsx": ".xlsx", "pdf": ".pdf", "md": ".md"}
                filename_out = f"{base_name}{extensions.get(fmt, '')}"
            else:
                raise HTTPException(status_code=500, detail="Không tạo được file đầu ra.")
        else:
            # Nhiều file nhưng không có zip (không thể xảy ra với logic hiện tại)
            raise HTTPException(status_code=500, detail="Lỗi nội bộ khi đóng gói kết quả.")

        # Lên lịch xóa thư mục tạm sau khi response hoàn tất
        background_tasks.add_task(_cleanup_dir, tmp_dir)

        return FileResponse(
            path=return_path,
            media_type=media_type,
            filename=filename_out,
            headers={
                "X-OCR-Mode": result.get("mode_used", mode),
                "X-OCR-Pages": str(result.get("total_pages_processed", 0)),
                "X-OCR-Confidence": str(result.get("overall_confidence", 0)),
                "X-OCR-Elapsed": str(result.get("elapsed_seconds", 0)),
            },
        )

    except HTTPException:
        _cleanup_dir(tmp_dir)
        raise
    except Exception as exc:
        _cleanup_dir(tmp_dir)
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý: {str(exc)}") from exc


# ─────────────────────────────────────────────────────────
# Entry point (chạy trực tiếp)
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
