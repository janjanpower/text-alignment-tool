"""圖片資源管理模組"""

import os
import logging
from typing import Dict, Optional, Tuple
from PIL import Image, ImageTk
import tkinter as tk

class ImageManager:
    """圖片資源管理類別，提供統一的圖片資源管理和大小調整功能"""

    def __init__(self, root_dir: Optional[str] = None):
        """
        初始化圖片管理器
        :param root_dir: 圖片資源根目錄，如不指定則使用預設路徑
        """
        self.logger = logging.getLogger(self.__class__.__name__)

        # 設置圖片根目錄
        if root_dir is None:
            # 預設的圖片資源目錄
            self.root_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "assets", "buttons"
            )
        else:
            self.root_dir = root_dir

        # 圖片緩存
        self.images: Dict[str, ImageTk.PhotoImage] = {}
        self.pil_images: Dict[str, Image.Image] = {}  # 保存 PIL 圖片對象

        # 按鈕圖片配置 - 正常和按下狀態的圖片
        self.button_images = {
            'load_srt': ('ImportSRT.png', 'ImportedSRT.png'),
            'import_audio': ('ImportMP3.png', 'ImportedMP3.png'),
            'load_word': ('ImportWORD.png', 'ImportedWORD.png'),
            'adjust_time': ('TimeLess.png', 'TimeFull.png'),
            'export_srt': ('ExportSRT.png', 'ExportedSRT.png')
        }

        self.logger.debug(f"圖片資源目錄: {self.root_dir}")

    def load_button_images(self, width=None, height=None) -> None:
        """
        預載入所有按鈕圖片
        :param width: 指定寬度，如不指定則使用原始寬度
        :param height: 指定高度，如不指定則使用原始高度
        """
        try:
            for button_id, (normal_img, pressed_img) in self.button_images.items():
                self.get_image(normal_img, f"{button_id}_normal", width, height)
                self.get_image(pressed_img, f"{button_id}_pressed", width, height)
            self.logger.info(f"成功預載入 {len(self.button_images) * 2} 張按鈕圖片")
        except Exception as e:
            self.logger.error(f"預載入按鈕圖片時出錯: {e}")

    def get_image(self, image_name: str, cache_key: Optional[str] = None,
                  width: Optional[int] = None, height: Optional[int] = None) -> Optional[ImageTk.PhotoImage]:
        """
        獲取圖片，可選擇調整大小，如果已經緩存則直接返回緩存的圖片
        :param image_name: 圖片文件名
        :param cache_key: 緩存鍵值，如不指定則使用文件名
        :param width: 指定寬度，如不指定則使用原始寬度
        :param height: 指定高度，如不指定則使用原始高度
        :return: PhotoImage 對象，如果加載失敗則返回 None
        """
        # 構建緩存鍵
        key = cache_key or image_name
        if width or height:
            key = f"{key}_{width}x{height}"

        # 如果已經緩存，直接返回
        if key in self.images:
            return self.images[key]

        try:
            # 構建完整的圖片路徑
            image_path = os.path.join(self.root_dir, image_name)
            if not os.path.exists(image_path):
                self.logger.error(f"圖片文件不存在: {image_path}")
                return None

            # 使用 PIL 載入圖片，以便調整大小
            pil_image = Image.open(image_path)
            self.pil_images[image_name] = pil_image

            # 調整大小（如有需要）
            if width or height:
                # 計算新的尺寸，保持縱橫比
                if width and height:
                    new_size = (width, height)
                elif width:
                    ratio = width / pil_image.width
                    new_size = (width, int(pil_image.height * ratio))
                else:  # height
                    ratio = height / pil_image.height
                    new_size = (int(pil_image.width * ratio), height)

                pil_image = pil_image.resize(new_size, Image.LANCZOS)

            # 轉換為 Tkinter 可用的圖片
            tk_image = ImageTk.PhotoImage(pil_image)
            self.images[key] = tk_image
            return tk_image

        except Exception as e:
            self.logger.error(f"載入圖片 {image_name} 失敗: {e}")
            return None

    def get_button_images(self, button_id: str, width=None, height=None) -> Tuple[Optional[ImageTk.PhotoImage], Optional[ImageTk.PhotoImage]]:
        """
        獲取按鈕的正常和按下狀態圖片
        :param button_id: 按鈕 ID
        :param width: 指定寬度
        :param height: 指定高度
        :return: 元組 (正常狀態圖片, 按下狀態圖片)
        """
        if button_id not in self.button_images:
            self.logger.warning(f"未找到按鈕 ID: {button_id}")
            return None, None

        normal_img, pressed_img = self.button_images[button_id]
        normal_key = f"{button_id}_normal"
        pressed_key = f"{button_id}_pressed"

        # 載入圖片（如果尚未載入）
        normal_photo = self.get_image(normal_img, normal_key, width, height)
        pressed_photo = self.get_image(pressed_img, pressed_key, width, height)

        return normal_photo, pressed_photo

    def resize_image(self, image_name: str, width: int, height: int, cache_key: Optional[str] = None) -> Optional[ImageTk.PhotoImage]:
        """
        調整圖片大小
        :param image_name: 圖片文件名或緩存鍵
        :param width: 新寬度
        :param height: 新高度
        :param cache_key: 新的緩存鍵，如不指定則自動生成
        :return: 調整大小後的圖片
        """
        # 構建緩存鍵
        key = cache_key or f"{image_name}_{width}x{height}"

        # 如果已經緩存，直接返回
        if key in self.images:
            return self.images[key]

        try:
            # 先檢查是否已經載入原始 PIL 圖片
            if image_name in self.pil_images:
                pil_image = self.pil_images[image_name]
            else:
                # 嘗試載入圖片
                image_path = os.path.join(self.root_dir, image_name)
                if not os.path.exists(image_path):
                    self.logger.error(f"圖片文件不存在: {image_path}")
                    return None
                pil_image = Image.open(image_path)
                self.pil_images[image_name] = pil_image

            # 調整大小
            resized_image = pil_image.resize((width, height), Image.LANCZOS)

            # 轉換為 Tkinter 可用的圖片
            tk_image = ImageTk.PhotoImage(resized_image)
            self.images[key] = tk_image
            return tk_image

        except Exception as e:
            self.logger.error(f"調整圖片 {image_name} 大小時出錯: {e}")
            return None