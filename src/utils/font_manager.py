"""字型管理模組，負責統一管理應用程式中的字型設定"""

import logging
import tkinter.font as tkfont
from tkinter import ttk
from typing import List, Tuple, Optional

from services.config.config_manager import ConfigManager


class FontManager:
    """字型管理類別，提供統一的字型設定和管理"""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        初始化字型管理器
        :param config_manager: 配置管理器實例
        """
        # 設置日誌
        self.logger = logging.getLogger(self.__class__.__name__)

        # 根據配置管理器獲取字型設定
        self.config = config_manager

        # 默認字型設定
        self.default_family = "Noto Sans TC"  # 微軟正黑體，適合繁體中文
        self.default_size = 10
        self.default_weight = "normal"

        # 緩存已創建的字型
        self.fonts = {}

        # 從配置文件加載設定
        self.load_from_config()

        self.logger.debug(f"字型管理器初始化完成，默認字型：{self.default_family}, 大小：{self.default_size}")

    def load_from_config(self) -> None:
        """從配置加載字型設定"""
        try:
            if self.config:
                display_config = self.config.get_display_config()
                self.default_family = display_config.get('font_family', self.default_family)
                self.default_size = display_config.get('font_size', self.default_size)
                self.logger.debug(f"從配置加載字型設定: {self.default_family}, 大小: {self.default_size}")
        except Exception as e:
            self.logger.error(f"從配置加載字型設定時出錯: {e}")

    def get_font(self, size: Optional[int] = None, family: Optional[str] = None,
                weight: Optional[str] = None) -> Tuple[str, int, str]:
        """
        獲取指定參數的字型，如果未指定則使用默認值

        :param size: 字型大小
        :param family: 字型家族
        :param weight: 字型粗細
        :return: 字型元組
        """
        font_family = family or self.default_family
        font_size = size or self.default_size
        font_weight = weight or self.default_weight

        # 構建字型索引鍵
        key = f"{font_family}_{font_size}_{font_weight}"

        # 如果已經緩存，直接返回
        if key in self.fonts:
            return self.fonts[key]

        # 創建新字型
        font = (font_family, font_size, font_weight)
        self.fonts[key] = font

        return font

    def apply_to_widget(self, widget, size=None, family=None, weight=None):
        """
        將字型應用到指定控制項，更具防禦性的實現
        """
        try:
            font = self.get_font(size, family, weight)
            widget.configure(font=font)
        except Exception as e:
            # 出錯時使用直接設置
            try:
                widget.configure(font=("Microsoft JhengHei", 11))
            except Exception as inner_e:
                self.logger.error(f"無法設置字型: {inner_e}")

    def apply_to_style(self, style: ttk.Style, style_name: str, size: Optional[int] = None,
                      family: Optional[str] = None, weight: Optional[str] = None) -> None:
        """
        將字型應用到指定樣式

        :param style: 樣式對象
        :param style_name: 樣式名稱
        :param size: 字型大小
        :param family: 字型家族
        :param weight: 字型粗細
        """
        try:
            font = self.get_font(size, family, weight)
            style.configure(style_name, font=font)
        except Exception as e:
            self.logger.error(f"將字型應用到樣式時出錯: {e}")

    def get_clear_fonts(self) -> List[str]:
        """
        獲取系統上較清晰的適合中文顯示的字體列表
        :return: 字體列表
        """
        clear_fonts = [
            "Microsoft JhengHei",  # 微軟正黑體
            "Microsoft YaHei",     # 微軟雅黑
            "PingFang TC",         # 蘋方繁體中文
            "Noto Sans TC",        # Google Noto Sans 繁體中文
            "Heiti TC",            # 黑體繁體中文
            "Arial Unicode MS",    # 具有完整 Unicode 支持的 Arial
            "Tahoma",              # 較清晰的通用字體
            "Segoe UI"             # Windows 默認 UI 字體
        ]

        # 獲取系統可用字體
        available_fonts = []
        try:
            system_fonts = list(tkfont.families())
            for font in clear_fonts:
                if font in system_fonts:
                    available_fonts.append(font)

            if not available_fonts:
                # 如果沒有找到推薦字型，使用系統默認
                self.logger.warning("找不到推薦的清晰字型，使用系統默認字型")
                return ["TkDefaultFont"]

            return available_fonts

        except Exception as e:
            self.logger.error(f"獲取清晰字型列表時出錯: {e}")
            return ["TkDefaultFont"]  # 如果出錯，使用 Tk 默認字型

    def save_settings(self, family: str, size: int) -> bool:
        """
        保存字型設定到配置文件

        :param family: 字型家族
        :param size: 字型大小
        :return: 是否成功保存
        """
        try:
            if not self.config:
                self.logger.warning("無法保存字型設定：配置管理器未初始化")
                return False

            # 更新配置
            self.config.set('display.font_family', family)
            self.config.set('display.font_size', size)
            self.config.save_config()

            # 更新當前設定
            self.default_family = family
            self.default_size = size

            # 清除緩存
            self.fonts = {}

            self.logger.info(f"字型設定已保存：{family}, 大小：{size}")
            return True

        except Exception as e:
            self.logger.error(f"保存字型設定時出錯: {e}")
            return False