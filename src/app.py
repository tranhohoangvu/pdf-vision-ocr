import os
import tempfile
import streamlit as st
import pandas as pd
import importlib
import core.ocr_engine
importlib.reload(core.ocr_engine)
from core.ocr_engine import OCREngine, HAS_PYMUPDF, HAS_PDF2DOCX

# Cấu hình giao diện Streamlit
st.set_page_config(
    page_title="PDF Vision OCR - Chuyển đổi PDF sang Word",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Tùy biến CSS giao diện
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .metric-val {
        font-size: 1.6rem;
        font-weight: 700;
        color: #2563EB;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #64748B;
    }
    .badge-digital {
        background-color: #DCFCE7;
        color: #166534;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# Khởi tạo engine (PaddleOCR model đã được cache tự động bên trong ocr_engine)
def get_ocr_engine(lang: str = "vi"):
    return OCREngine(lang=lang, use_angle_cls=True)

# --- SIDEBAR: CẤU HÌNH ---
with st.sidebar:
    st.header("⚙️ Cấu hình xử lý")
    
    # Chế độ chuyển đổi
    conversion_mode = st.selectbox(
        "Chế độ chuyển đổi:",
        options=["auto", "digital", "ocr"],
        format_func=lambda x: {
            "auto": "⚡ Tự động (Smart Hybrid - Khuyên dùng)",
            "digital": "📑 Văn bản gốc & Bảng biểu (100% có dấu)",
            "ocr": "🤖 Thuần quét ảnh OCR (PaddleOCR)"
        }[x],
        index=0,
        help="⚡ Tự động: Phát hiện văn bản có sẵn để giữ 100% dấu & bảng biểu. Nếu là ảnh scan sẽ tự chuyển sang OCR."
    )
    
    # Lựa chọn ngôn ngữ
    lang_choice = st.selectbox(
        "Ngôn ngữ nhận diện OCR:",
        options=["vi", "en"],
        format_func=lambda x: "Tiếng Việt (vi)" if x == "vi" else "English (en)",
        index=0
    )
    
    # Khởi tạo engine
    engine = get_ocr_engine(lang=lang_choice)
    
    # Cấu hình chất lượng DPI (dành cho chế độ OCR)
    dpi_option = st.select_slider(
        "Độ phân giải ảnh OCR (DPI):",
        options=[150, 200, 300],
        value=200,
        help="150: Nhanh | 200: Cân bằng | 300: Rõ nét cho tài liệu mờ"
    )
    
    # Tùy chọn gom đoạn văn bản
    merge_paragraphs = st.checkbox(
        "Gom dòng thành đoạn văn",
        value=True,
        help="Tự động nối các dòng văn bản liền kề thành đoạn văn hoàn chỉnh, tránh ngắt dòng vụn trong Word."
    )
    
    # Tùy chọn trang cần xử lý
    page_mode = st.radio(
        "Phạm vi trang:",
        options=["Toàn bộ tài liệu", "Trang tùy chọn"],
        index=0
    )
    
    custom_pages = ""
    if page_mode == "Trang tùy chọn":
        custom_pages = st.text_input(
            "Nhập số trang (ví dụ: 1-3, 5):",
            placeholder="1-3, 5"
        )

    st.divider()
    st.caption("⚡ **Bộ dựng PDF:** PyMuPDF")
    st.caption("📊 **Bộ tái tạo Word:** pdf2docx & python-docx")
    st.caption("🤖 **Mô hình OCR:** PaddleOCR 2.7.3")

# --- MAIN CONTENT ---
st.markdown('<div class="main-header">📄 PDF Vision OCR sang Word</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Bảo toàn 100% dấu tiếng Việt và cấu trúc bảng biểu cho tài liệu PDF văn phòng và ảnh scan</div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader("Kéo thả hoặc bấm để chọn file PDF", type=["pdf"])

if uploaded_file is not None:
    # Lưu file tạm để đọc metadata và xử lý
    with tempfile.TemporaryDirectory() as temp_dir:
        input_pdf_path = os.path.join(temp_dir, "uploaded.pdf")
        output_docx_path = os.path.join(temp_dir, "result.docx")
        
        with open(input_pdf_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        total_pages = OCREngine.get_pdf_page_count(input_pdf_path)

        # Tính toán danh sách trang sẽ xử lý
        if page_mode == "Trang tùy chọn" and custom_pages.strip():
            target_page_indices = OCREngine.parse_page_selection(custom_pages, total_pages)
        else:
            target_page_indices = list(range(total_pages))

        # Phân tích loại file PDF (Digital hay Scan)
        has_digital, char_count, sample_txt = OCREngine.check_has_digital_text(input_pdf_path, target_page_indices)
        
        if has_digital:
            st.success(
                f"✅ **Phát hiện:** File PDF có chứa văn bản gốc & bảng biểu (phát hiện ~{char_count} ký tự). "
                f"Chế độ **Tự động** sẽ giữ nguyên **100% tiếng Việt có dấu** và **bảng biểu** ban đầu."
            )
        else:
            st.info(
                "📷 **Phát hiện:** File PDF là dạng ảnh chụp / tài liệu scan (không có lớp chữ số). "
                "Hệ thống sẽ quét bằng mô hình học sâu OCR Vision."
            )

        # Hộp thông tin file và Preview
        with st.expander("👁️ Xem trước trang tài liệu PDF", expanded=False):
            col_info1, col_info2 = st.columns([1, 2])
            with col_info1:
                st.write(f"**Tên file:** `{uploaded_file.name}`")
                st.write(f"**Dung lượng:** `{round(len(uploaded_file.getbuffer()) / 1024, 1)} KB`")
                st.write(f"**Tổng số trang:** `{total_pages}`")
                
                preview_page_num = st.number_input(
                    "Chọn trang xem trước:",
                    min_value=1,
                    max_value=max(total_pages, 1),
                    value=1,
                    step=1
                )
            
            with col_info2:
                preview_images = engine.render_pdf_to_images(
                    pdf_path=input_pdf_path,
                    dpi=100,
                    page_indices=[preview_page_num - 1]
                )
                if preview_images:
                    st.image(preview_images[0][1], caption=f"Trang {preview_page_num}", use_column_width=True)

        pages_to_process_count = len(target_page_indices)
        st.write(f"📌 Đã sẵn sàng xử lý **{pages_to_process_count}** / {total_pages} trang.")

        # Nút bấm bắt đầu chuyển đổi
        if st.button("🚀 Bắt đầu chuyển đổi sang Word", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_placeholder = st.empty()

            def on_progress(current, total, msg=""):
                if total > 0:
                    progress_bar.progress(current / total)
                status_placeholder.info(msg)

            with st.spinner("Đang chuyển đổi tài liệu sang Word..."):
                try:
                    result = engine.convert_pdf_to_word(
                        pdf_path=input_pdf_path,
                        output_word_path=output_docx_path,
                        mode=conversion_mode,
                        dpi=dpi_option,
                        page_indices=target_page_indices,
                        merge_paragraphs=merge_paragraphs,
                        progress_callback=on_progress
                    )
                    
                    status_placeholder.empty()
                    progress_bar.progress(1.0)
                    
                    mode_label = "Trích xuất kỹ thuật số (Bảo toàn 100% dấu & Bảng biểu)" if result.get("mode_used") == "digital" else "PaddleOCR Vision"
                    st.success(f"🎉 Chuyển đổi thành công! Phương thức: **{mode_label}**")

                    # Đọc file Word để chuẩn bị download
                    with open(output_docx_path, "rb") as f:
                        docx_bytes = f.read()

                    # Thống kê nhanh
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-val">{result['total_pages_processed']}</div>
                            <div class="metric-label">Trang đã xử lý</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with c2:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-val">{result['overall_confidence']}%</div>
                            <div class="metric-label">Độ tin cậy văn bản</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with c3:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-val">{result['elapsed_seconds']}s</div>
                            <div class="metric-label">Thời gian hoàn thành</div>
                        </div>
                        """, unsafe_allow_html=True)

                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # Nút Download lớn
                    st.download_button(
                        label="⬇️ Tải xuống file Word (.docx)",
                        data=docx_bytes,
                        file_name=uploaded_file.name.rsplit(".", 1)[0] + ".docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        type="primary",
                        use_container_width=True
                    )

                    # Tabs hiển thị kết quả chi tiết
                    tab_preview, tab_stats = st.tabs(["📝 Xem trước văn bản", "📊 Thống kê từng trang"])

                    with tab_preview:
                        for page in result["pages"]:
                            page_text = "\n\n".join(page["paragraphs"])
                            with st.expander(f"📄 Trang {page['page_num']} ({len(page['paragraphs'])} đoạn/khối, độ tin cậy {page['avg_confidence']}%)", expanded=True):
                                st.text_area(
                                    f"Nội dung trang {page['page_num']}",
                                    value=page_text if page_text else "(Không tìm thấy văn bản)",
                                    height=200,
                                    key=f"text_page_{page['page_num']}"
                                )

                    with tab_stats:
                        stats_data = []
                        for page in result["pages"]:
                            stats_data.append({
                                "Trang": f"Trang {page['page_num']}",
                                "Số dòng phát hiện": page["line_count"],
                                "Số đoạn/khối": page["paragraph_count"],
                                "Độ tin cậy": f"{page['avg_confidence']}%"
                            })
                        st.dataframe(pd.DataFrame(stats_data), use_container_width=True)

                except Exception as e:
                    status_placeholder.empty()
                    st.error(f"❌ Có lỗi xảy ra trong quá trình xử lý: {str(e)}")
