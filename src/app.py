import os
import sys
import time
from datetime import datetime

os.environ["PYMUPDF_SUGGEST_LAYOUT_ANALYZER"] = "0"

try:
    import pymupdf
    sys.modules['fitz'] = pymupdf
    if hasattr(pymupdf, 'no_recommend_layout'):
        pymupdf.no_recommend_layout()
except ImportError:
    pass

import tempfile
import streamlit as st
import pandas as pd
import importlib
import core.ocr_engine
import core.exporters
importlib.reload(core.ocr_engine)
importlib.reload(core.exporters)
from core.ocr_engine import OCREngine, HAS_PYMUPDF, HAS_PDF2DOCX
from core.exporters import ZipPackageExporter

# Cấu hình giao diện
st.set_page_config(
    page_title="PDF Vision OCR - Đa Năng",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS tương thích 100% Dark Mode & Inter/Geist Typography
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Geist:wght@300;400;500;600;700;800&display=swap');

    *, html, body, [class*="css"], [data-testid="stAppViewContainer"], [data-testid="stSidebar"], 
    .stMarkdown, .stText, p, span, h1, h2, h3, h4, h5, h6, 
    button, input, textarea, select, label, .stSelectbox, .stRadio, .stSlider {
        font-family: 'Inter', 'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    /* Ẩn các nút thừa của Streamlit */
    #MainMenu, footer, header, .stDeployButton {
        display: none !important;
    }

    /* Tiêu đề ứng dụng */
    .app-header {
        padding: 1.2rem 0 0.8rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 1.5rem;
    }
    .app-title {
        font-size: 1.9rem;
        font-weight: 800;
        color: #F8FAFC;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .app-title span {
        color: #3B82F6;
    }
    .app-desc {
        color: #94A3B8;
        font-size: 0.95rem;
        margin-top: 0.25rem;
    }

    /* Hộp thông báo nhận diện */
    .alert-box {
        padding: 0.85rem 1.1rem;
        border-radius: 10px;
        margin-bottom: 1.2rem;
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 0.92rem;
        line-height: 1.5;
    }
    .alert-digital {
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.3);
        color: #34D399;
    }
    .alert-scanned {
        background: rgba(59, 130, 246, 0.12);
        border: 1px solid rgba(59, 130, 246, 0.3);
        color: #60A5FA;
    }
    .alert-batch {
        background: rgba(139, 92, 246, 0.12);
        border: 1px solid rgba(139, 92, 246, 0.3);
        color: #C084FC;
    }

    /* Thẻ thống kê KPI */
    .kpi-container {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        margin: 1.2rem 0;
    }
    .kpi-container-4 {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
        margin: 1.2rem 0;
    }
    @media (max-width: 768px) {
        .kpi-container-4 {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    .kpi-card {
        background: #111827;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        border-top: 3px solid #3B82F6;
    }
    .kpi-num {
        font-size: 1.7rem;
        font-weight: 800;
        color: #F8FAFC;
    }
    .kpi-title {
        font-size: 0.78rem;
        font-weight: 600;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.25rem;
    }

    /* Tinh chỉnh nút Primary */
    button[kind="primary"] {
        background-color: #2563EB !important;
        border: none !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
        padding: 0.6rem 1.5rem !important;
    }
    button[kind="primary"]:hover {
        background-color: #1D4ED8 !important;
    }
</style>
""", unsafe_allow_html=True)

# Khởi tạo engine
def get_ocr_engine(lang: str = "vi"):
    return OCREngine(lang=lang, use_angle_cls=True)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### ⚙️ Chế độ & Ngôn ngữ")
    
    conversion_mode = st.selectbox(
        "Chế độ chuyển đổi:",
        options=["auto", "digital", "ocr"],
        format_func=lambda x: {
            "auto": "⚡ Tự động (Smart Hybrid)",
            "digital": "📑 Giữ nguyên bản (100% có dấu)",
            "ocr": "🤖 Quét quang học (PaddleOCR)"
        }[x],
        index=0,
        help="Tự động: Giữ 100% dấu & bảng biểu nếu file có text layer, tự chuyển OCR nếu là ảnh scan."
    )
    
    lang_choice = st.selectbox(
        "Ngôn ngữ nhận diện OCR:",
        options=["vi", "en"],
        format_func=lambda x: "Tiếng Việt (vi)" if x == "vi" else "English (en)",
        index=0
    )
    
    engine = get_ocr_engine(lang=lang_choice)

    st.markdown("---")
    st.markdown("### 📦 Định dạng đầu ra")
    
    selected_formats = st.multiselect(
        "Chọn định dạng xuất:",
        options=["docx", "xlsx", "pdf", "md"],
        default=["docx"],
        format_func=lambda x: {
            "docx": "📄 Word (.docx)",
            "xlsx": "📊 Excel (.xlsx)",
            "pdf": "🔍 Searchable PDF (.pdf)",
            "md": "📝 Markdown (.md)"
        }[x],
        help="Có thể chọn nhiều định dạng cùng lúc để tải về trọn bộ."
    )
    if not selected_formats:
        selected_formats = ["docx"]
    
    st.markdown("---")
    st.markdown("### 🖼️ Tiền xử lý ảnh (OpenCV)")
    
    deskew = st.toggle(
        "Tự động xoay thẳng (Deskew)",
        value=False,
        help="Phát hiện và xoay thẳng văn bản nếu tài liệu scan/chụp bị nghiêng góc."
    )
    
    remove_shadow = st.toggle(
        "Khử bóng râm & Tẩy nền",
        value=False,
        help="Loại bỏ bóng tay, bóng tối khi chụp tài liệu bằng camera điện thoại."
    )
    
    enhance_contrast = st.toggle(
        "Tăng tương phản nét chữ",
        value=False,
        help="Tăng độ đậm nét cho chữ mờ hoặc mực nhạt bằng thuật toán CLAHE."
    )

    st.markdown("---")
    st.markdown("### 📐 Cấu hình trang & Dàn dòng")
    
    dpi_option = st.select_slider(
        "Độ phân giải quét (DPI):",
        options=[150, 200, 300],
        value=200,
        help="150: Nhanh | 200: Chuẩn | 300: Sắc nét cho tài liệu mờ"
    )
    
    merge_paragraphs = st.toggle(
        "Gom dòng thành đoạn văn",
        value=True,
        help="Tự động nối các dòng liền kề để Word không bị gãy dòng vụn."
    )
    
    page_mode = st.radio(
        "Phạm vi trang (áp dụng file đơn):",
        options=["Tất cả", "Trang chỉ định"],
        index=0
    )
    
    custom_pages = ""
    if page_mode == "Trang chỉ định":
        custom_pages = st.text_input(
            "Số trang (ví dụ: 1-3, 5):",
            placeholder="1-3, 5"
        )

    st.markdown("---")
    with st.expander("✨ Vision AI (Google Gemini)", expanded=False):
        gemini_api_key = st.text_input(
            "Gemini API Key:",
            type="password",
            placeholder="AIzaSy...",
            help="Cung cấp API Key để xử lý chữ viết tay & tài liệu siêu khó (Giai đoạn tiếp theo)."
        )
        st.markdown("[🔑 Lấy Google Gemini API Key miễn phí](https://aistudio.google.com/app/apikey)")
        if gemini_api_key:
            st.success("🟢 Đã nạp Gemini Key (Sẵn sàng)")
        else:
            st.caption("Chế độ hiện tại: Offline Local Engine (PaddleOCR & PyMuPDF)")

    st.markdown("---")
    if st.button("🔄 Đặt lại toàn bộ (Reset)", use_container_width=True, help="Xóa mọi tệp tải lên và làm mới trạng thái"):
        st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
        st.session_state["single_result"] = None
        st.session_state["batch_results"] = None
        st.session_state["last_uploaded_keys"] = []
        st.rerun()

    st.caption("⚡ **Render:** PyMuPDF | 📊 **Excel:** openpyxl")
    st.caption("🤖 **OCR:** PaddleOCR 2.7.3")

# --- MAIN CONTENT ---
st.markdown("""
<div class="app-header">
    <h1 class="app-title">⚡ PDF Vision <span>OCR & Multi-Export</span></h1>
    <div class="app-desc">Bảo toàn 100% tiếng Việt có dấu, phục hồi nguyên vẹn bảng biểu sang Word, Excel, Searchable PDF và Markdown. Hỗ trợ xử lý hàng loạt.</div>
</div>
""", unsafe_allow_html=True)

# Khung tải tệp (cho phép chọn nhiều file)
uploader_key = f"uploader_{st.session_state.get('uploader_key', 0)}"
uploaded_files = st.file_uploader(
    "Chọn hoặc kéo thả một hoặc nhiều file PDF vào đây (Batch Upload):",
    type=["pdf"],
    accept_multiple_files=True,
    key=uploader_key
)

# Kiểm tra thay đổi tệp để reset session state
if uploaded_files:
    current_keys = [f"{f.name}_{f.size}" for f in uploaded_files]
    if st.session_state.get("last_uploaded_keys") != current_keys:
        st.session_state["last_uploaded_keys"] = current_keys
        st.session_state["single_result"] = None
        st.session_state["batch_results"] = None
else:
    st.session_state["last_uploaded_keys"] = []
    st.session_state["single_result"] = None
    st.session_state["batch_results"] = None

# Nếu chưa có file nào
if not uploaded_files:
    st.markdown("""
    <div style="background: rgba(17, 24, 39, 0.6); border: 1px dashed rgba(255, 255, 255, 0.15); border-radius: 12px; padding: 2.5rem 1.5rem; text-align: center; margin-top: 1rem;">
        <div style="font-size: 2.5rem; margin-bottom: 0.6rem;">📄 ➔ 📊 📄 🔍 📝</div>
        <h3 style="color: #F8FAFC; margin-bottom: 0.4rem; font-weight: 700;">Chưa có tài liệu nào được chọn</h3>
        <p style="color: #94A3B8; font-size: 0.95rem; max-width: 620px; margin: 0 auto; line-height: 1.6;">
            Bạn có thể tải lên <b>1 file đơn lẻ</b> hoặc <b>nhiều file PDF cùng lúc</b> (Batch Processing).<br>
            Hệ thống sẽ tự động phân tích cấu trúc, giữ 100% dấu tiếng Việt và xuất sang các định dạng bạn cần.
        </p>
    </div>
    """, unsafe_allow_html=True)

# -------------------------------------------------------------
# CASE 1: XỬ LÝ 1 FILE DUY NHẤT (GIAO DIỆN CHUYÊN SÂU 2 CỘT)
# -------------------------------------------------------------
elif len(uploaded_files) == 1:
    uploaded_file = uploaded_files[0]
    
    with tempfile.TemporaryDirectory() as temp_dir:
        input_pdf_path = os.path.join(temp_dir, "uploaded.pdf")
        output_docx_path = os.path.join(temp_dir, "result.docx")
        
        with open(input_pdf_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        total_pages = OCREngine.get_pdf_page_count(input_pdf_path)

        # Tính danh sách trang
        if page_mode == "Trang chỉ định" and custom_pages.strip():
            target_page_indices = OCREngine.parse_page_selection(custom_pages, total_pages)
        else:
            target_page_indices = list(range(total_pages))

        # Phân tích loại tài liệu
        has_digital, char_count, _ = OCREngine.check_has_digital_text(input_pdf_path, target_page_indices)
        
        if has_digital:
            st.markdown(f"""
            <div class="alert-box alert-digital">
                <span style="font-size: 1.3rem;">🎯</span>
                <div>
                    <strong>Phát hiện tài liệu điện tử (Digital PDF):</strong> Có sẵn ~{char_count:,} ký tự. 
                    Hệ thống sẽ giữ <strong>100% tiếng Việt có dấu</strong> và <strong>nguyên vẹn bảng biểu</strong> khi xuất Word/Excel.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="alert-box alert-scanned">
                <span style="font-size: 1.3rem;">📷</span>
                <div>
                    <strong>Phát hiện tài liệu dạng ảnh scan:</strong> Không tìm thấy lớp text số. 
                    Hệ thống sẽ áp dụng <strong>PaddleOCR Vision</strong> kết hợp bộ lọc xử lý ảnh.
                </div>
            </div>
            """, unsafe_allow_html=True)

        col_preview, col_action = st.columns([1, 1], gap="medium")

        with col_preview:
            st.markdown("##### 👁️ Xem trước trang")
            
            cp1, cp2 = st.columns([1, 1])
            with cp1:
                st.caption(f"📁 **File:** `{uploaded_file.name}`")
                st.caption(f"💾 **Size:** `{round(len(uploaded_file.getbuffer()) / 1024, 1)} KB`")
            with cp2:
                preview_page = st.number_input(
                    "Chọn trang:",
                    min_value=1,
                    max_value=max(total_pages, 1),
                    value=1,
                    step=1
                )

            preview_imgs = engine.render_pdf_to_images(
                pdf_path=input_pdf_path,
                dpi=120,
                page_indices=[preview_page - 1],
                deskew=deskew,
                remove_shadow=remove_shadow,
                enhance_contrast=enhance_contrast
            )
            if preview_imgs:
                st.image(
                    preview_imgs[0][1],
                    caption=f"Trang {preview_page} / {total_pages}",
                    use_column_width=True
                )

        with col_action:
            st.markdown("##### 🚀 Tiến hành xử lý & Xuất file")
            
            pages_count = len(target_page_indices)
            st.write(f"Số trang được chọn: **{pages_count}** / {total_pages} trang.")
            
            format_labels = [f".{fmt.upper()}" for fmt in selected_formats]
            st.info(f"Định dạng xuất: **{', '.join(format_labels)}**")

            # Nút bấm chuyển đổi & Đặt lại
            col_b1, col_b2 = st.columns([3, 1])
            with col_b1:
                start_btn = st.button("🚀 Bắt đầu chuyển đổi ngay", type="primary", use_container_width=True)
            with col_b2:
                if st.button("🔄 Đặt lại", use_container_width=True, help="Hủy bỏ file và làm mới"):
                    st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
                    st.session_state["single_result"] = None
                    st.session_state["batch_results"] = None
                    st.session_state["last_uploaded_keys"] = []
                    st.rerun()

            if start_btn:
                progress_bar = st.progress(0)
                status_placeholder = st.empty()

                def on_progress(current, total, msg=""):
                    if total > 0:
                        progress_bar.progress(current / total)
                    status_placeholder.info(f"⏳ {msg}")

                with st.spinner("Đang xử lý tài liệu và khởi tạo các định dạng xuất..."):
                    try:
                        result = engine.convert_pdf_to_word(
                            pdf_path=input_pdf_path,
                            output_word_path=output_docx_path,
                            mode=conversion_mode,
                            dpi=dpi_option,
                            page_indices=target_page_indices,
                            merge_paragraphs=merge_paragraphs,
                            export_formats=selected_formats,
                            deskew=deskew,
                            remove_shadow=remove_shadow,
                            enhance_contrast=enhance_contrast,
                            progress_callback=on_progress
                        )
                        
                        # Đọc bytes vào RAM để lưu vào session state
                        exported_bytes = {}
                        for fmt, fpath in result.get("output_files", {}).items():
                            if os.path.exists(fpath):
                                with open(fpath, "rb") as rf:
                                    exported_bytes[fmt] = rf.read()
                        result["file_bytes"] = exported_bytes
                        result["base_name"] = uploaded_file.name.rsplit(".", 1)[0]
                        st.session_state["single_result"] = result

                        status_placeholder.empty()
                        progress_bar.progress(1.0)
                    except Exception as e:
                        status_placeholder.empty()
                        st.error(f"❌ Có lỗi xảy ra trong quá trình xử lý: {str(e)}")

            # Hiển thị kết quả từ session state
            saved_result = st.session_state.get("single_result")
            if saved_result:
                mode_title = "Trích xuất số (100% có dấu & giữ bảng)" if saved_result.get("mode_used") == "digital" else "PaddleOCR Vision"
                st.success(f"🎉 **Hoàn thành!** Phương thức: {mode_title}")

                # Thẻ KPI
                st.markdown(f"""
                <div class="kpi-container">
                    <div class="kpi-card">
                        <div class="kpi-num">{saved_result['total_pages_processed']}</div>
                        <div class="kpi-title">Trang xử lý</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-num">{saved_result['overall_confidence']}%</div>
                        <div class="kpi-title">Độ tin cậy</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-num">{saved_result['elapsed_seconds']}s</div>
                        <div class="kpi-title">Thời gian</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # KHU VỰC TẢI XUỐNG CÁC ĐỊNH DẠNG
                st.markdown("##### 📥 Tải xuống kết quả:")
                file_bytes = saved_result.get("file_bytes", {})
                base_name = saved_result.get("base_name", "converted_document")

                # Nút tải gói ZIP nếu có nhiều file
                if "zip" in file_bytes:
                    st.download_button(
                        label="📦 TẢI TRỌN BỘ TẤT CẢ ĐỊNH DẠNG (.ZIP)",
                        data=file_bytes["zip"],
                        file_name=f"{base_name}_bundle.zip",
                        mime="application/zip",
                        type="primary",
                        use_container_width=True
                    )
                    st.markdown("<br>", unsafe_allow_html=True)

                # Các nút tải riêng theo định dạng
                dl_col1, dl_col2 = st.columns(2)
                
                if "docx" in file_bytes:
                    dl_col1.download_button(
                        label="📄 Tải file Word (.docx)",
                        data=file_bytes["docx"],
                        file_name=f"{base_name}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )

                if "xlsx" in file_bytes:
                    dl_col2.download_button(
                        label="📊 Tải bảng tính Excel (.xlsx)",
                        data=file_bytes["xlsx"],
                        file_name=f"{base_name}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

                if "pdf" in file_bytes:
                    dl_col1.download_button(
                        label="🔍 Tải Searchable PDF (.pdf)",
                        data=file_bytes["pdf"],
                        file_name=f"{base_name}_searchable.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )

                if "md" in file_bytes:
                    dl_col2.download_button(
                        label="📝 Tải tài liệu Markdown (.md)",
                        data=file_bytes["md"],
                        file_name=f"{base_name}.md",
                        mime="text/markdown",
                        use_container_width=True
                    )

                # Tabs xem trước nội dung
                tab_text, tab_meta = st.tabs(["📝 Xem trước văn bản", "📊 Chi tiết trang"])

                with tab_text:
                    for page in saved_result.get("pages", []):
                        page_txt = "\n\n".join(page.get("paragraphs", []))
                        with st.expander(f"📄 Trang {page['page_num']} ({len(page.get('paragraphs', []))} đoạn, độ tin cậy {page.get('avg_confidence', 0)}%)", expanded=True):
                            st.text_area(
                                f"Nội dung trang {page['page_num']}",
                                value=page_txt if page_txt else "(Không tìm thấy văn bản)",
                                height=180,
                                key=f"text_page_{page['page_num']}"
                            )

                with tab_meta:
                    df_stats = pd.DataFrame([{
                        "Trang": f"Trang {p['page_num']}",
                        "Số dòng": p.get("line_count", 0),
                        "Số đoạn": p.get("paragraph_count", 0),
                        "Độ tin cậy": f"{p.get('avg_confidence', 0)}%"
                    } for p in saved_result.get("pages", [])])
                    st.dataframe(df_stats, use_container_width=True)

# -------------------------------------------------------------
# CASE 2: XỬ LÝ HÀNG LOẠT (BATCH PROCESSING MULTIPLE FILES)
# -------------------------------------------------------------
else:
    total_batch_files = len(uploaded_files)
    total_batch_size_mb = sum(len(f.getbuffer()) for f in uploaded_files) / (1024 * 1024)
    
    st.markdown(f"""
    <div class="alert-box alert-batch">
        <span style="font-size: 1.4rem;">📦</span>
        <div>
            <strong>Chế độ xử lý hàng loạt (Batch Mode):</strong> Đã chọn <strong>{total_batch_files} tệp PDF</strong> 
            (Tổng dung lượng: {total_batch_size_mb:.2f} MB).
            Hệ thống sẽ xử lý tuần tự từng tài liệu và tự động đóng gói Master ZIP trọn bộ.
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_batch_info, col_batch_run = st.columns([1, 1], gap="medium")

    with col_batch_info:
        st.markdown("##### 🔍 Kiểm tra & Xem trước tệp trong danh sách")
        
        selected_inspect_idx = st.selectbox(
            "Chọn file cần xem trước:",
            options=list(range(total_batch_files)),
            format_func=lambda i: f"#{i+1}: {uploaded_files[i].name} ({round(len(uploaded_files[i].getbuffer()) / 1024, 1)} KB)"
        )
        
        inspect_file = uploaded_files[selected_inspect_idx]
        with tempfile.TemporaryDirectory() as inspect_dir:
            temp_inspect_path = os.path.join(inspect_dir, "inspect.pdf")
            with open(temp_inspect_path, "wb") as f:
                f.write(inspect_file.getbuffer())
            
            file_page_count = OCREngine.get_pdf_page_count(temp_inspect_path)
            is_dig, char_cnt, _ = OCREngine.check_has_digital_text(temp_inspect_path, [0])

            badge_text = "🟢 Digital PDF (100% tiếng Việt)" if is_dig else "🔵 Scanned Image (Cần OCR)"
            st.caption(f"**Trạng thái:** {badge_text} | **Số trang:** {file_page_count} trang")

            insp_imgs = engine.render_pdf_to_images(
                pdf_path=temp_inspect_path,
                dpi=100,
                page_indices=[0],
                deskew=deskew,
                remove_shadow=remove_shadow,
                enhance_contrast=enhance_contrast
            )
            if insp_imgs:
                st.image(insp_imgs[0][1], caption=f"Trang 1 của {inspect_file.name}", use_column_width=True)

    with col_batch_run:
        st.markdown("##### 🚀 Cấu hình & Chạy hàng loạt")
        
        format_labels = [f".{fmt.upper()}" for fmt in selected_formats]
        st.info(f"Định dạng xuất cho mỗi file: **{', '.join(format_labels)}**")

        batch_scope = st.radio(
            "Phạm vi trang xử lý:",
            options=["all_pages", "first_page_only"],
            format_func=lambda x: "Tất cả các trang của mỗi file" if x == "all_pages" else "Chỉ trang đầu tiên (Kiểm tra tốc độ nhanh)",
            index=0
        )

        col_bb1, col_bb2 = st.columns([3, 1])
        with col_bb1:
            batch_start_btn = st.button(
                f"🚀 Bắt đầu chuyển đổi hàng loạt ({total_batch_files} file)",
                type="primary",
                use_container_width=True
            )
        with col_bb2:
            if st.button("🔄 Đặt lại", key="batch_reset_btn", use_container_width=True, help="Hủy danh sách file và làm mới"):
                st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
                st.session_state["single_result"] = None
                st.session_state["batch_results"] = None
                st.session_state["last_uploaded_keys"] = []
                st.rerun()

        if batch_start_btn:
            batch_progress_bar = st.progress(0)
            batch_status_placeholder = st.empty()
            
            batch_results_list = []
            batch_file_maps = []
            overall_start_time = time.time()

            with tempfile.TemporaryDirectory() as master_temp_dir:
                for idx, u_file in enumerate(uploaded_files):
                    file_name = u_file.name
                    base_name = file_name.rsplit(".", 1)[0]
                    batch_status_placeholder.info(f"⏳ Đang xử lý file {idx + 1}/{total_batch_files}: **{file_name}**...")
                    
                    file_input_pdf = os.path.join(master_temp_dir, f"in_{idx}.pdf")
                    file_out_docx = os.path.join(master_temp_dir, f"{base_name}.docx")
                    
                    with open(file_input_pdf, "wb") as f:
                        f.write(u_file.getbuffer())

                    total_pgs = OCREngine.get_pdf_page_count(file_input_pdf)
                    target_indices = [0] if batch_scope == "first_page_only" else list(range(total_pgs))

                    try:
                        f_result = engine.convert_pdf_to_word(
                            pdf_path=file_input_pdf,
                            output_word_path=file_out_docx,
                            mode=conversion_mode,
                            dpi=dpi_option,
                            page_indices=target_indices,
                            merge_paragraphs=merge_paragraphs,
                            export_formats=selected_formats,
                            deskew=deskew,
                            remove_shadow=remove_shadow,
                            enhance_contrast=enhance_contrast,
                            progress_callback=None
                        )

                        # Lưu file bytes
                        file_bytes_map = {}
                        archive_subfolder_files = {}
                        
                        for fmt, fpath in f_result.get("output_files", {}).items():
                            if os.path.exists(fpath):
                                with open(fpath, "rb") as rf:
                                    content = rf.read()
                                    file_bytes_map[fmt] = content
                                if fmt != "zip":
                                    archive_subfolder_files[os.path.basename(fpath)] = fpath

                        batch_file_maps.append({
                            "folder_name": base_name,
                            "files": archive_subfolder_files
                        })

                        batch_results_list.append({
                            "name": file_name,
                            "base_name": base_name,
                            "size_kb": round(len(u_file.getbuffer()) / 1024, 1),
                            "pages_processed": len(target_indices),
                            "mode_used": f_result.get("mode_used", "unknown"),
                            "confidence": f_result.get("overall_confidence", 0),
                            "elapsed": f_result.get("elapsed_seconds", 0),
                            "file_bytes": file_bytes_map,
                            "pages": f_result.get("pages", []),
                            "status": "Thành công"
                        })
                    except Exception as err:
                        batch_results_list.append({
                            "name": file_name,
                            "base_name": base_name,
                            "size_kb": round(len(u_file.getbuffer()) / 1024, 1),
                            "pages_processed": 0,
                            "mode_used": "error",
                            "confidence": 0,
                            "elapsed": 0,
                            "file_bytes": {},
                            "pages": [],
                            "status": f"Lỗi: {str(err)}"
                        })

                    batch_progress_bar.progress((idx + 1) / total_batch_files)

                # Tạo Master ZIP
                master_zip_path = os.path.join(master_temp_dir, "master_batch.zip")
                summary_report = f"BÁO CÁO XỬ LÝ HÀNG LOẠT (PDF VISION OCR)\n"
                summary_report += f"Thời gian thực hiện: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                summary_report += f"Tổng số file: {total_batch_files}\n"
                summary_report += f"Các định dạng xuất: {', '.join(selected_formats)}\n\n"
                for res in batch_results_list:
                    summary_report += f"- {res['name']}: {res['status']} | Số trang: {res['pages_processed']} | Mode: {res['mode_used']} | Độ tin cậy: {res['confidence']}%\n"

                ZipPackageExporter.create_batch_archive(batch_file_maps, master_zip_path, summary_report)
                
                master_zip_bytes = b""
                if os.path.exists(master_zip_path):
                    with open(master_zip_path, "rb") as zf:
                        master_zip_bytes = zf.read()

                batch_total_time = round(time.time() - overall_start_time, 2)
                st.session_state["batch_results"] = {
                    "results": batch_results_list,
                    "master_zip_bytes": master_zip_bytes,
                    "total_time": batch_total_time
                }

                batch_status_placeholder.empty()
                batch_progress_bar.progress(1.0)

    # Hiển thị kết quả xử lý hàng loạt
    batch_data = st.session_state.get("batch_results")
    if batch_data:
        b_results = batch_data["results"]
        total_time = batch_data["total_time"]
        success_count = sum(1 for r in b_results if r["status"] == "Thành công")
        total_pages_all = sum(r["pages_processed"] for r in b_results)
        valid_confs = [r["confidence"] for r in b_results if r["status"] == "Thành công" and r["confidence"] > 0]
        avg_batch_conf = round(sum(valid_confs) / len(valid_confs), 1) if valid_confs else 100.0

        st.markdown("---")
        st.success(f"🎉 **Đã hoàn thành xử lý hàng loạt!** Thành công {success_count}/{total_batch_files} file.")

        # Thẻ KPI Hàng loạt
        st.markdown(f"""
        <div class="kpi-container-4">
            <div class="kpi-card">
                <div class="kpi-num">{success_count} / {total_batch_files}</div>
                <div class="kpi-title">File thành công</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-num">{total_pages_all}</div>
                <div class="kpi-title">Tổng số trang</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-num">{avg_batch_conf}%</div>
                <div class="kpi-title">Độ tin cậy TB</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-num">{total_time}s</div>
                <div class="kpi-title">Tổng thời gian</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Nút tải trọn bộ Master ZIP
        if batch_data.get("master_zip_bytes"):
            st.download_button(
                label=f"📦 TẢI TRỌN BỘ TẤT CẢ FILE ({success_count} FILE ĐÃ XỬ LÝ) (.ZIP)",
                data=batch_data["master_zip_bytes"],
                file_name=f"pdf_vision_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True
            )
            st.markdown("<br>", unsafe_allow_html=True)

        # Bảng thống kê chi tiết
        st.markdown("##### 📋 Danh sách kết quả từng file:")
        df_batch = pd.DataFrame([{
            "Tên file": r["name"],
            "Dung lượng": f"{r['size_kb']} KB",
            "Số trang": r["pages_processed"],
            "Phương thức": "Digital" if r["mode_used"] == "digital" else ("OCR Vision" if r["mode_used"] == "ocr" else r["mode_used"]),
            "Độ tin cậy": f"{r['confidence']}%",
            "Thời gian": f"{r['elapsed']}s",
            "Trạng thái": r["status"]
        } for r in b_results])
        st.dataframe(df_batch, use_container_width=True)

        # Accordion tải từng file riêng
        st.markdown("##### 📁 Tải về hoặc xem trước từng file lẻ:")
        for res in b_results:
            b_name = res["base_name"]
            with st.expander(f"📄 {res['name']} — Trạng thái: {res['status']} ({res['pages_processed']} trang)", expanded=False):
                if res["status"] == "Thành công":
                    fb = res["file_bytes"]
                    bc1, bc2, bc3, bc4 = st.columns(4)
                    
                    if "docx" in fb:
                        bc1.download_button(
                            label="📄 Word (.docx)",
                            data=fb["docx"],
                            file_name=f"{b_name}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_docx_{b_name}",
                            use_container_width=True
                        )
                    if "xlsx" in fb:
                        bc2.download_button(
                            label="📊 Excel (.xlsx)",
                            data=fb["xlsx"],
                            file_name=f"{b_name}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_xlsx_{b_name}",
                            use_container_width=True
                        )
                    if "pdf" in fb:
                        bc3.download_button(
                            label="🔍 Searchable PDF",
                            data=fb["pdf"],
                            file_name=f"{b_name}_searchable.pdf",
                            mime="application/pdf",
                            key=f"dl_pdf_{b_name}",
                            use_container_width=True
                        )
                    if "md" in fb:
                        bc4.download_button(
                            label="📝 Markdown (.md)",
                            data=fb["md"],
                            file_name=f"{b_name}.md",
                            mime="text/markdown",
                            key=f"dl_md_{b_name}",
                            use_container_width=True
                        )

                    # Xem trước text nếu có
                    if res.get("pages"):
                        st.caption("Xem trước nội dung trích xuất:")
                        sample_txt = "\n\n".join(res["pages"][0].get("paragraphs", []))
                        st.text_area(
                            f"Trang 1 của {res['name']}",
                            value=sample_txt[:1000] + ("..." if len(sample_txt) > 1000 else ""),
                            height=120,
                            key=f"txt_prev_{b_name}"
                        )
                else:
                    st.error(res["status"])
