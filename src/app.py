import os
import sys

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
importlib.reload(core.ocr_engine)
from core.ocr_engine import OCREngine, HAS_PYMUPDF, HAS_PDF2DOCX

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

    /* Thẻ thống kê KPI */
    .kpi-container {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        margin: 1.2rem 0;
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
        "Phạm vi trang:",
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
    st.caption("⚡ **Render:** PyMuPDF | 📊 **Excel:** openpyxl")
    st.caption("🤖 **OCR:** PaddleOCR 2.7.3")

# --- MAIN CONTENT ---
st.markdown("""
<div class="app-header">
    <h1 class="app-title">⚡ PDF Vision <span>OCR & Multi-Export</span></h1>
    <div class="app-desc">Bảo toàn 100% tiếng Việt có dấu, phục hồi nguyên vẹn bảng biểu sang Word, Excel, Searchable PDF và Markdown.</div>
</div>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "Chọn hoặc kéo thả file PDF vào đây",
    type=["pdf"]
)

if uploaded_file is not None:
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

            # Nút bấm chuyển đổi
            start_btn = st.button("🚀 Bắt đầu chuyển đổi ngay", type="primary", use_container_width=True)

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
                        
                        status_placeholder.empty()
                        progress_bar.progress(1.0)
                        
                        mode_title = "Trích xuất số (100% có dấu & giữ bảng)" if result.get("mode_used") == "digital" else "PaddleOCR Vision"
                        st.success(f"🎉 **Hoàn thành!** Phương thức: {mode_title}")

                        # Thẻ KPI
                        st.markdown(f"""
                        <div class="kpi-container">
                            <div class="kpi-card">
                                <div class="kpi-num">{result['total_pages_processed']}</div>
                                <div class="kpi-title">Trang xử lý</div>
                            </div>
                            <div class="kpi-card">
                                <div class="kpi-num">{result['overall_confidence']}%</div>
                                <div class="kpi-title">Độ tin cậy</div>
                            </div>
                            <div class="kpi-card">
                                <div class="kpi-num">{result['elapsed_seconds']}s</div>
                                <div class="kpi-title">Thời gian</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        # KHU VỰC TẢI XUỐNG CÁC ĐỊNH DẠNG
                        st.markdown("##### 📥 Tải xuống kết quả:")
                        output_files = result.get("output_files", {})
                        base_file_name = uploaded_file.name.rsplit(".", 1)[0]

                        # Nút tải gói ZIP nếu có nhiều file
                        if "zip" in output_files and os.path.exists(output_files["zip"]):
                            with open(output_files["zip"], "rb") as zf:
                                st.download_button(
                                    label="📦 TẢI TRỌN BỘ TẤT CẢ ĐỊNH DẠNG (.ZIP)",
                                    data=zf.read(),
                                    file_name=f"{base_file_name}_bundle.zip",
                                    mime="application/zip",
                                    type="primary",
                                    use_container_width=True
                                )
                            st.markdown("<br>", unsafe_allow_html=True)

                        # Các nút tải riêng theo định dạng
                        dl_col1, dl_col2 = st.columns(2)
                        
                        if "docx" in output_files and os.path.exists(output_files["docx"]):
                            with open(output_files["docx"], "rb") as f:
                                dl_col1.download_button(
                                    label="📄 Tải file Word (.docx)",
                                    data=f.read(),
                                    file_name=f"{base_file_name}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    use_container_width=True
                                )

                        if "xlsx" in output_files and os.path.exists(output_files["xlsx"]):
                            with open(output_files["xlsx"], "rb") as f:
                                dl_col2.download_button(
                                    label="📊 Tải bảng tính Excel (.xlsx)",
                                    data=f.read(),
                                    file_name=f"{base_file_name}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True
                                )

                        if "pdf" in output_files and os.path.exists(output_files["pdf"]):
                            with open(output_files["pdf"], "rb") as f:
                                dl_col1.download_button(
                                    label="🔍 Tải Searchable PDF (.pdf)",
                                    data=f.read(),
                                    file_name=f"{base_file_name}_searchable.pdf",
                                    mime="application/pdf",
                                    use_container_width=True
                                )

                        if "md" in output_files and os.path.exists(output_files["md"]):
                            with open(output_files["md"], "rb") as f:
                                dl_col2.download_button(
                                    label="📝 Tải tài liệu Markdown (.md)",
                                    data=f.read(),
                                    file_name=f"{base_file_name}.md",
                                    mime="text/markdown",
                                    use_container_width=True
                                )

                        # Tabs xem trước nội dung
                        tab_text, tab_meta = st.tabs(["📝 Xem trước văn bản", "📊 Chi tiết trang"])

                        with tab_text:
                            for page in result["pages"]:
                                page_txt = "\n\n".join(page["paragraphs"])
                                with st.expander(f"📄 Trang {page['page_num']} ({len(page['paragraphs'])} đoạn, độ tin cậy {page['avg_confidence']}%)", expanded=True):
                                    st.text_area(
                                        f"Nội dung trang {page['page_num']}",
                                        value=page_txt if page_txt else "(Không tìm thấy văn bản)",
                                        height=180,
                                        key=f"text_page_{page['page_num']}"
                                    )

                        with tab_meta:
                            df_stats = pd.DataFrame([{
                                "Trang": f"Trang {p['page_num']}",
                                "Số dòng": p["line_count"],
                                "Số đoạn": p["paragraph_count"],
                                "Độ tin cậy": f"{p['avg_confidence']}%"
                            } for p in result["pages"]])
                            st.dataframe(df_stats, use_container_width=True)

                    except Exception as e:
                        status_placeholder.empty()
                        st.error(f"❌ Có lỗi xảy ra trong quá trình xử lý: {str(e)}")
