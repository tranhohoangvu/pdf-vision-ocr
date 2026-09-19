import cv2
import numpy as np


class ImagePreprocessor:
    """
    Bộ tiền xử lý ảnh tài liệu scan / chụp camera bằng OpenCV:
    - Auto-Deskew: Tự động phát hiện góc nghiêng và xoay thẳng
    - Shadow Removal: Khử bóng râm, bóng tay người chụp và chuẩn hóa nền trắng
    - Contrast Enhancement: Tăng độ tương phản (CLAHE) cho chữ mờ, mực nhạt
    """

    @staticmethod
    def auto_deskew(image: np.ndarray, max_angle: float = 45.0) -> tuple:
        """
        Tự động phát hiện góc nghiêng của văn bản và xoay thẳng về 0 độ.
        :param image: Ảnh numpy array (RGB hoặc BGR hoặc Grayscale)
        :param max_angle: Góc nghiêng tối đa xem xét xoay (tránh xoay sai với tài liệu hình vuông)
        :return: (rotated_image: np.ndarray, angle: float)
        """
        if image is None:
            return image, 0.0

        # Chuyển sang Grayscale nếu cần
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image.copy()

        # Ngưỡng hóa nhị phân để lấy vùng có chữ
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]

        # Tìm tọa độ các pixel chữ
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 100:
            return image, 0.0

        # Tính toán góc nghiêng hình chữ nhật bao quanh nhỏ nhất
        angle = cv2.minAreaRect(coords)[-1]

        # Chuẩn hóa góc quay OpenCV
        if angle < -45:
            angle = -(90 + angle)
        elif angle > 45:
            angle = angle - 90
        else:
            angle = -angle

        # Nếu góc quá nhỏ (< 0.5 độ) hoặc quá lớn (> max_angle) thì bỏ qua
        if abs(angle) < 0.5 or abs(angle) > max_angle:
            return image, 0.0

        # Thực hiện phép xoay ma trận quanh tâm
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Điền viền bằng màu trắng nền tài liệu
        border_color = (255, 255, 255) if len(image.shape) == 3 else 255
        rotated = cv2.warpAffine(
            image,
            M,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=border_color
        )
        return rotated, round(angle, 2)

    @staticmethod
    def remove_shadows(image: np.ndarray) -> np.ndarray:
        """
        Khử bóng râm và bóng tay người chụp bằng phép chia hình thái học (Morphological Division).
        """
        if image is None:
            return image

        is_rgb = len(image.shape) == 3
        if is_rgb:
            # Tách các kênh màu
            channels = cv2.split(image)
            norm_channels = []
            for ch in channels:
                # Dilation để tìm lớp sáng nền (background illumination)
                dilated = cv2.dilate(ch, np.ones((7, 7), np.uint8))
                bg = cv2.medianBlur(dilated, 21)
                # Phép chia chuẩn hóa để triệt tiêu bóng tối
                diff = 255 - cv2.absdiff(ch, bg)
                norm = cv2.normalize(diff, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                norm_channels.append(norm)
            return cv2.merge(norm_channels)
        else:
            dilated = cv2.dilate(image, np.ones((7, 7), np.uint8))
            bg = cv2.medianBlur(dilated, 21)
            diff = 255 - cv2.absdiff(image, bg)
            return cv2.normalize(diff, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)

    @staticmethod
    def enhance_contrast(image: np.ndarray) -> np.ndarray:
        """
        Tăng cường độ tương phản cục bộ bằng thuật toán CLAHE.
        """
        if image is None:
            return image

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        if len(image.shape) == 3:
            # Chuyển sang không gian màu LAB để chỉ tăng tương phản trên kênh độ sáng (L)
            lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            l_enhanced = clahe.apply(l)
            lab_enhanced = cv2.merge((l_enhanced, a, b))
            return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)
        else:
            return clahe.apply(image)

    @classmethod
    def process_pipeline(
        cls,
        image: np.ndarray,
        deskew: bool = False,
        remove_shadow: bool = False,
        enhance: bool = False
    ) -> tuple:
        """
        Chạy toàn bộ pipeline tiền xử lý ảnh theo tùy chọn.
        :return: (processed_image, applied_info: dict)
        """
        processed = image.copy()
        info = {"deskew_angle": 0.0, "shadow_removed": False, "enhanced": False}

        if deskew:
            processed, angle = cls.auto_deskew(processed)
            info["deskew_angle"] = angle

        if remove_shadow:
            processed = cls.remove_shadows(processed)
            info["shadow_removed"] = True

        if enhance:
            processed = cls.enhance_contrast(processed)
            info["enhanced"] = True

        return processed, info
