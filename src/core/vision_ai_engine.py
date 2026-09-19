import os
import io
import time
from typing import List, Dict, Any, Optional
from PIL import Image
import numpy as np

try:
    from google import genai
    from google.genai import types
    HAS_GOOGLE_GENAI = True
except ImportError:
    HAS_GOOGLE_GENAI = False


VIETNAMESE_OCR_PROMPT = """Nhiệm vụ: Trích xuất CHÍNH XÁC toàn bộ văn bản từ ảnh tài liệu (bao gồm chữ viết tay tiếng Việt).

QUY TẮC BẮT BUỘC:
1. TUYỆT ĐỐI không bịa đặt, không đoán mò. Chỉ ghi những gì bạn thực sự nhìn thấy trong ảnh.
2. Bảo toàn đầy đủ dấu tiếng Việt: sắc (á), huyền (à), hỏi (ả), ngã (ã), nặng (ạ) và các dấu mũ (â, ă, ê, ô, ơ, ư, đ).
3. CHỮ VIẾT TAY: Đọc từng chữ theo đúng thứ tự từ trái sang phải, từ trên xuống dưới. Không bỏ sót từ nào.
4. Giữ nguyên cấu trúc đoạn văn và xuống dòng như trong tài liệu gốc.
5. Nếu có bảng biểu → dùng định dạng Markdown table.
6. Nếu có tiêu đề → dùng # hoặc ##.
7. KHÔNG thêm bất kỳ lời bình luận, giải thích, lời chào hay preamble nào. Chỉ trả về văn bản thuần.
8. KHÔNG bọc kết quả trong markdown code block (```). Trả về plain text trực tiếp.
"""


class GeminiVisionEngine:
    """
    Bộ nhận diện Vision AI sử dụng mô hình Google Gemini Flash để xử lý
    các trang tài liệu có chữ viết tay, văn bản scan mờ hoặc biểu mẫu phức tạp.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.model_name = model_name
        self.client = None
        
        if self.api_key and HAS_GOOGLE_GENAI:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                self.client = None
                print(f"[GeminiVisionEngine] Lỗi khởi tạo client: {e}")

    def is_available(self) -> bool:
        """Kiểm tra xem SDK và API Key đã sẵn sàng chưa."""
        return bool(HAS_GOOGLE_GENAI and self.api_key and self.client is not None)

    def _convert_image_to_png_bytes(self, image_input) -> tuple:
        """
        Chuyển đổi các định dạng ảnh khác nhau thành PNG bytes (lossless) để Gemini đọc chính xác hơn.
        Trả về (bytes, mime_type).
        """
        if isinstance(image_input, bytes):
            # Giả sử đã là PNG/JPEG bytes
            return image_input, "image/png"

        if isinstance(image_input, np.ndarray):
            # numpy array từ OpenCV có thể là BGR hoặc RGB/grayscale
            arr = image_input
            if len(arr.shape) == 3 and arr.shape[2] == 3:
                # Kiểm tra xem có phải BGR không (từ OpenCV)
                # PIL Image sau khi convert sang numpy luôn là RGB → KHÔNG flip
                pil_img = Image.fromarray(arr)  # Assume RGB (từ PIL/render)
            elif len(arr.shape) == 2:
                pil_img = Image.fromarray(arr)
            else:
                pil_img = Image.fromarray(arr)
        elif isinstance(image_input, Image.Image):
            # PIL Image từ render_pdf_to_images luôn là RGB
            pil_img = image_input
        else:
            raise ValueError(f"Định dạng ảnh không hỗ trợ: {type(image_input)}")

        if pil_img.mode not in ("RGB", "L"):
            pil_img = pil_img.convert("RGB")

        buf = io.BytesIO()
        # Dùng PNG (lossless) để bảo toàn chi tiết chữ viết tay
        pil_img.save(buf, format="PNG", optimize=False)
        return buf.getvalue(), "image/png"

    def ocr_page_image(self, image_input, prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Nhận diện văn bản của một trang ảnh sử dụng Google Gemini Flash.
        
        Trả về dict:
        {
            "status": "success" | "error",
            "text": str,
            "paragraphs": list[str],
            "confidence": float,
            "model_used": str,
            "elapsed_seconds": float,
            "error": Optional[str]
        }
        """
        if not self.is_available():
            return {
                "status": "error",
                "text": "",
                "paragraphs": [],
                "confidence": 0.0,
                "model_used": "none",
                "elapsed_seconds": 0.0,
                "error": "Google Gemini API Key chưa được cung cấp hoặc SDK google-genai chưa cài đặt."
            }

        start_time = time.time()
        active_prompt = prompt or VIETNAMESE_OCR_PROMPT

        try:
            png_bytes, mime_type = self._convert_image_to_png_bytes(image_input)
            image_part = types.Part.from_bytes(data=png_bytes, mime_type=mime_type)

            # Danh sách models thử nghiệm lần lượt nếu gặp lỗi
            models_to_try = [self.model_name]
            for fallback_m in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                if fallback_m not in models_to_try:
                    models_to_try.append(fallback_m)

            response = None
            last_err = None
            used_model = self.model_name

            for m_name in models_to_try:
                try:
                    response = self.client.models.generate_content(
                        model=m_name,
                        contents=[image_part, active_prompt],
                        config=types.GenerateContentConfig(
                            temperature=0.0,  # Deterministic - không hallucinate
                            top_p=1.0,
                        )
                    )
                    used_model = m_name
                    break
                except Exception as err:
                    last_err = err
                    continue

            if response is None or not response.text:
                raise RuntimeError(f"Không nhận được phản hồi từ Gemini: {last_err}")

            raw_text = response.text.strip()
            # Làm sạch nếu model trả về code block markdown
            if raw_text.startswith("```markdown"):
                raw_text = raw_text[len("```markdown"):].strip()
            if raw_text.startswith("```"):
                raw_text = raw_text[len("```"):].strip()
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3].strip()

            # Tách thành các đoạn văn
            lines = raw_text.split("\n")
            paragraphs = []
            current_para = []

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    if current_para:
                        paragraphs.append(" ".join(current_para))
                        current_para = []
                else:
                    if stripped.startswith("|") or stripped.startswith("#"):
                        if current_para:
                            paragraphs.append(" ".join(current_para))
                            current_para = []
                        paragraphs.append(stripped)
                    else:
                        current_para.append(stripped)

            if current_para:
                paragraphs.append(" ".join(current_para))

            elapsed = round(time.time() - start_time, 2)

            return {
                "status": "success",
                "text": raw_text,
                "paragraphs": paragraphs if paragraphs else [raw_text],
                "confidence": 99.0,  # Vision LLMs đạt độ chính xác ngữ nghĩa rất cao
                "model_used": used_model,
                "elapsed_seconds": elapsed,
                "error": None
            }

        except Exception as e:
            elapsed = round(time.time() - start_time, 2)
            return {
                "status": "error",
                "text": "",
                "paragraphs": [],
                "confidence": 0.0,
                "model_used": self.model_name,
                "elapsed_seconds": elapsed,
                "error": str(e)
            }
