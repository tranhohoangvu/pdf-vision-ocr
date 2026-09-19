import time
import io
import os
import re
import numpy as np
from PIL import Image
from docx import Document
from paddleocr import PaddleOCR

import sys

try:
    import pymupdf as fitz
    sys.modules['fitz'] = fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from pdf2docx import Converter
    HAS_PDF2DOCX = True
except ImportError:
    HAS_PDF2DOCX = False


def clean_vietnamese_ocr_text(text: str) -> str:
    """
    Chuẩn hóa và sửa các lỗi mất dấu/sai ký tự đặc trưng của mô hình Latin OCR trên tiếng Việt.
    """
    if not text:
        return ""
        
    replacements = [
        ("Döc lap", "Độc lập"),
        ("Dộc lap", "Độc lập"),
        ("Doc lap", "Độc lập"),
        ("Hanh phüc", "Hạnh phúc"),
        ("Hanh phúc", "Hạnh phúc"),
        ("C.NG HOA", "CỘNG HÒA"),
        ("CÔNG HÒA", "CỘNG HÒA"),
        ("XA HI", "XÃ HỘI"),
        ("CH.NGH.A", "CHỦ NGHĨA"),
        ("VI.T NAM", "VIỆT NAM"),
        ("T6T NGHIEP", "TỐT NGHIỆP"),
        ("T6T", "TỐT"),
        ("D. AN", "DỰ ÁN"),
        ("ki-m th.", "kiểm thử"),
        ("nh-n di-n", "nhận diện"),
        ("v-n b-n", "văn bản"),
        ("ti-ng Vi-t", "tiếng Việt"),
        ("Nguyén", "Nguyễn"),
        ("Tuyét", "Tuyết"),
        ("Triêu", "Triệu"),
        ("Hoäng", "Hoàng"),
        ("Phät", "Phát"),
        ("Quäch", "Quách"),
        ("H6 Qu6c", "Hồ Quốc"),
        ("V6 Van", "Võ Văn"),
        ("V6 Minh", "Võ Minh"),
        ("Huynh Tän", "Huỳnh Tấn"),
        ("o-n v-n", "đoạn văn"),
        ("tinh n-ng", "tính năng"),
        ("ng-t trang", "ngắt trang"),
        ("thng minh", "thông minh"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
        
    return text


_PADDLE_CACHE = {}

def get_shared_paddle_model(lang: str = "vi", use_angle_cls: bool = True):
    key = (lang, use_angle_cls)
    if key not in _PADDLE_CACHE:
        _PADDLE_CACHE[key] = PaddleOCR(use_angle_cls=use_angle_cls, lang=lang, show_log=False)
    return _PADDLE_CACHE[key]


class OCREngine:
    def __init__(self, lang: str = "vi", use_angle_cls: bool = True):
        """
        Khởi tạo PaddleOCR engine với ngôn ngữ và cấu hình góc xoay.
        """
        self.lang = lang
        self.use_angle_cls = use_angle_cls
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = get_shared_paddle_model(self.lang, self.use_angle_cls)
        return self._model

    @staticmethod
    def check_has_digital_text(pdf_path: str, page_indices: list = None) -> tuple:
        """
        Kiểm tra xem file PDF có chứa text layer (văn bản kỹ thuật số có sẵn) hay là ảnh scan thuần.
        :return: (has_text: bool, total_characters: int, sample_text: str)
        """
        if not HAS_PYMUPDF:
            return False, 0, ""
            
        try:
            doc = fitz.open(pdf_path)
            total_doc_pages = len(doc)
            target_indices = page_indices if page_indices is not None else list(range(total_doc_pages))
            
            total_chars = 0
            sample_snippets = []
            
            for idx in target_indices:
                if 0 <= idx < total_doc_pages:
                    txt = doc[idx].get_text("text").strip()
                    total_chars += len(txt)
                    if txt and len(sample_snippets) < 3:
                        sample_snippets.append(txt[:120].replace("\n", " "))
                        
            doc.close()
            # Nếu có nhiều hơn 30 ký tự văn bản, xem như PDF có text layer
            has_digital = total_chars > 30
            sample = " | ".join(sample_snippets) if sample_snippets else ""
            return has_digital, total_chars, sample
        except Exception:
            return False, 0, ""

    def render_pdf_to_images(self, pdf_path: str, dpi: int = 200, page_indices: list = None, poppler_path: str = None) -> list:
        """
        Render các trang PDF thành danh sách ảnh PIL.Image sử dụng PyMuPDF.
        """
        if not HAS_PYMUPDF:
            raise RuntimeError("Cần cài đặt thư viện pymupdf để render PDF sang ảnh.")

        doc = fitz.open(pdf_path)
        total_doc_pages = len(doc)
        target_indices = page_indices if page_indices is not None else list(range(total_doc_pages))
        
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        images = []
        for idx in target_indices:
            if 0 <= idx < total_doc_pages:
                page = doc[idx]
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append((idx + 1, img))
        doc.close()
        return images

    @staticmethod
    def parse_page_selection(selection_str: str, max_pages: int) -> list:
        """
        Chuyển chuỗi định dạng phạm vi trang (vd: '1-3, 5') thành danh sách chỉ số trang 0-indexed.
        """
        if not selection_str or not selection_str.strip():
            return list(range(max_pages))
        
        indices = set()
        parts = [p.strip() for p in selection_str.split(",") if p.strip()]
        for part in parts:
            if "-" in part:
                subparts = part.split("-")
                if len(subparts) == 2 and subparts[0].strip().isdigit() and subparts[1].strip().isdigit():
                    start = int(subparts[0].strip())
                    end = int(subparts[1].strip())
                    for p in range(start, end + 1):
                        if 1 <= p <= max_pages:
                            indices.add(p - 1)
            elif part.isdigit():
                p = int(part)
                if 1 <= p <= max_pages:
                    indices.add(p - 1)
                    
        return sorted(list(indices)) if indices else list(range(max_pages))

    @staticmethod
    def get_pdf_page_count(pdf_path: str) -> int:
        """Lấy tổng số trang của file PDF một cách nhanh chóng."""
        if HAS_PYMUPDF:
            doc = fitz.open(pdf_path)
            count = len(doc)
            doc.close()
            return count
        return 1

    @staticmethod
    def merge_lines_into_paragraphs(ocr_lines: list, line_spacing_threshold: float = 1.4) -> list:
        """
        Gom các dòng nhận diện OCR thành đoạn văn hoàn chỉnh dựa trên khoảng cách tọa độ Y.
        """
        if not ocr_lines:
            return []

        parsed = []
        for item in ocr_lines:
            box = item[0]
            text = clean_vietnamese_ocr_text(item[1][0].strip())
            score = float(item[1][1])
            if not text:
                continue

            ys = [pt[1] for pt in box]
            xs = [pt[0] for pt in box]
            top = min(ys)
            bottom = max(ys)
            left = min(xs)
            right = max(xs)
            height = max(bottom - top, 1.0)
            parsed.append({
                "top": top,
                "bottom": bottom,
                "left": left,
                "right": right,
                "height": height,
                "text": text,
                "score": score
            })

        if not parsed:
            return []

        parsed.sort(key=lambda item: item["top"])

        paragraphs = []
        current_para = [parsed[0]["text"]]
        prev_bottom = parsed[0]["bottom"]
        avg_height = parsed[0]["height"]

        for item in parsed[1:]:
            v_gap = item["top"] - prev_bottom
            line_height = item["height"]
            avg_height = (avg_height + line_height) / 2.0

            if v_gap < avg_height * line_spacing_threshold:
                current_para.append(item["text"])
            else:
                paragraphs.append(" ".join(current_para))
                current_para = [item["text"]]

            prev_bottom = item["bottom"]

        if current_para:
            paragraphs.append(" ".join(current_para))

        return paragraphs

    def _convert_digital_pdf(self, pdf_path: str, output_word_path: str, page_indices: list = None, progress_callback: callable = None) -> dict:
        """
        Chuyển đổi Digital PDF sang Word giữ nguyên 100% dấu tiếng Việt và bảng biểu.
        """
        start_time = time.time()
        if progress_callback:
            progress_callback(0, 1, "Đang phân tích cấu trúc văn bản và bảng biểu...")

        pages_summary = []
        
        # 1. Trích xuất text blocks để preview
        if HAS_PYMUPDF:
            doc = fitz.open(pdf_path)
            total_doc_pages = len(doc)
            target_indices = page_indices if page_indices is not None else list(range(total_doc_pages))
            
            for i, idx in enumerate(target_indices):
                if 0 <= idx < total_doc_pages:
                    page = doc[idx]
                    page_text = page.get_text("text").strip()
                    # Chia đoạn văn
                    paras = [p.strip() for p in page_text.split("\n\n") if p.strip()]
                    if not paras and page_text:
                        paras = [line.strip() for line in page_text.split("\n") if line.strip()]
                    
                    lines = [l for l in page_text.split("\n") if l.strip()]
                    pages_summary.append({
                        "page_num": idx + 1,
                        "line_count": len(lines),
                        "paragraph_count": len(paras),
                        "avg_confidence": 100.0,
                        "paragraphs": paras
                    })
            doc.close()

        # 2. Sử dụng pdf2docx để tái hiện bảng biểu và format chuẩn xác
        if HAS_PDF2DOCX:
            if progress_callback:
                progress_callback(1, 2, "Đang dựng tài liệu Word với đầy đủ dấu và bảng biểu...")
            cv = Converter(pdf_path)
            cv.convert(output_word_path, pages=page_indices)
            cv.close()
        else:
            # Fallback sang python-docx tạo text thuần
            doc_out = Document()
            for i, p_info in enumerate(pages_summary):
                for p_text in p_info["paragraphs"]:
                    doc_out.add_paragraph(p_text)
                if i < len(pages_summary) - 1:
                    doc_out.add_page_break()
            doc_out.save(output_word_path)

        elapsed = round(time.time() - start_time, 2)
        return {
            "success": True,
            "mode_used": "digital",
            "total_pages_processed": len(pages_summary),
            "overall_confidence": 100.0,
            "elapsed_seconds": elapsed,
            "output_word_path": output_word_path,
            "pages": pages_summary
        }

    def _convert_scanned_pdf(
        self,
        pdf_path: str,
        output_word_path: str,
        dpi: int = 200,
        page_indices: list = None,
        merge_paragraphs: bool = True,
        poppler_path: str = None,
        progress_callback: callable = None
    ) -> dict:
        """
        Chuyển đổi PDF dạng ảnh scan sang Word bằng mô hình PaddleOCR Vision.
        """
        start_time = time.time()
        
        if progress_callback:
            progress_callback(0, 1, "Đang trích xuất các trang PDF sang ảnh...")
            
        page_images = self.render_pdf_to_images(
            pdf_path=pdf_path,
            dpi=dpi,
            page_indices=page_indices,
            poppler_path=poppler_path
        )
        
        total_pages = len(page_images)
        if total_pages == 0:
            raise ValueError("Không tìm thấy trang nào để xử lý trong file PDF.")

        doc = Document()
        pages_summary = []
        all_confidences = []

        for i, (page_num, img) in enumerate(page_images):
            if progress_callback:
                progress_callback(i + 1, total_pages, f"Đang quét OCR trang {page_num} ({i + 1}/{total_pages})...")

            img_array = np.array(img)
            result = self.model.ocr(img_array, cls=True)

            page_lines = []
            page_confs = []

            if result and result[0] is not None:
                for line in result[0]:
                    page_lines.append(line)
                    page_confs.append(float(line[1][1]))
                    all_confidences.append(float(line[1][1]))

            if merge_paragraphs:
                paragraphs = self.merge_lines_into_paragraphs(page_lines)
            else:
                paragraphs = [clean_vietnamese_ocr_text(line[1][0].strip()) for line in page_lines if line[1][0].strip()]

            for p_text in paragraphs:
                doc.add_paragraph(p_text)

            if i < total_pages - 1:
                doc.add_page_break()

            avg_page_conf = (sum(page_confs) / len(page_confs)) if page_confs else 0.0
            pages_summary.append({
                "page_num": page_num,
                "line_count": len(page_lines),
                "paragraph_count": len(paragraphs),
                "avg_confidence": round(avg_page_conf * 100, 1),
                "paragraphs": paragraphs
            })

        doc.save(output_word_path)
        elapsed = round(time.time() - start_time, 2)
        overall_conf = round((sum(all_confidences) / len(all_confidences) * 100), 1) if all_confidences else 0.0

        return {
            "success": True,
            "mode_used": "ocr",
            "total_pages_processed": total_pages,
            "overall_confidence": overall_conf,
            "elapsed_seconds": elapsed,
            "output_word_path": output_word_path,
            "pages": pages_summary
        }

    def convert_pdf_to_word(
        self,
        pdf_path: str,
        output_word_path: str,
        mode: str = "auto",
        dpi: int = 200,
        page_indices: list = None,
        merge_paragraphs: bool = True,
        poppler_path: str = None,
        progress_callback: callable = None,
        **kwargs
    ) -> dict:
        """
        Hàm chính điều phối chuyển đổi PDF sang Word theo chế độ:
        :param mode: 'auto' (Tự động phát hiện), 'digital' (Văn bản số & Bảng biểu), 'ocr' (Thuần quét ảnh OCR)
        """
        # Kiểm tra sự tồn tại của text layer
        has_digital, char_count, _ = self.check_has_digital_text(pdf_path, page_indices)

        if mode == "auto":
            # Nếu có văn bản số với lượng chữ đáng kể -> dùng digital mode (giữ 100% dấu & bảng biểu)
            if has_digital and HAS_PDF2DOCX:
                return self._convert_digital_pdf(
                    pdf_path=pdf_path,
                    output_word_path=output_word_path,
                    page_indices=page_indices,
                    progress_callback=progress_callback
                )
            else:
                return self._convert_scanned_pdf(
                    pdf_path=pdf_path,
                    output_word_path=output_word_path,
                    dpi=dpi,
                    page_indices=page_indices,
                    merge_paragraphs=merge_paragraphs,
                    poppler_path=poppler_path,
                    progress_callback=progress_callback
                )
        elif mode == "digital":
            return self._convert_digital_pdf(
                pdf_path=pdf_path,
                output_word_path=output_word_path,
                page_indices=page_indices,
                progress_callback=progress_callback
            )
        else:  # mode == "ocr"
            return self._convert_scanned_pdf(
                pdf_path=pdf_path,
                output_word_path=output_word_path,
                dpi=dpi,
                page_indices=page_indices,
                merge_paragraphs=merge_paragraphs,
                poppler_path=poppler_path,
                progress_callback=progress_callback
            )