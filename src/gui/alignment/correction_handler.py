"""校正處理模組"""

import logging
import csv
import os

class CorrectionHandler:
    """處理文本校正相關功能"""

    def __init__(self, parent):
        """
        初始化校正處理器
        :param parent: 父物件 (AlignmentGUI 實例)
        """
        self.parent = parent
        self.logger = logging.getLogger(self.__class__.__name__)

    def load_corrections(self):
        """載入校正數據庫"""
        corrections = {}
        if self.parent.current_project_path:
            corrections_file = os.path.join(self.parent.current_project_path, "corrections.csv")
            if os.path.exists(corrections_file):
                try:
                    with open(corrections_file, 'r', encoding='utf-8-sig') as file:
                        reader = csv.reader(file)
                        next(reader)  # 跳過標題行
                        for row in reader:
                            if len(row) >= 2:
                                error, correction = row
                                corrections[error] = correction
                except Exception as e:
                    self.logger.error(f"載入校正數據庫失敗: {e}")
        return corrections

    def correct_text(self, text, corrections):
        """
        根據校正數據庫修正文本
        :param text: 原始文本
        :param corrections: 校正對照表
        :return: 校正後的文本
        """
        corrected_text = text
        for error, correction in corrections.items():
            if error in corrected_text:  # 只在完全符合時替換
                corrected_text = corrected_text.replace(error, correction)
        return corrected_text

    def check_text_correction(self, text, corrections):
        """
        檢查文本是否需要校正並返回相關信息
        :param text: 要檢查的文本
        :param corrections: 校正對照表
        :return: (需要校正, 原始文本, 校正後文本)
        """
        corrected_text = text
        needs_correction = False

        for error, correction in corrections.items():
            if error in text:
                corrected_text = corrected_text.replace(error, correction)
                needs_correction = True

        return needs_correction, text, corrected_text

    def check_text_for_correction(self, text, corrections):
        """
        檢查文本是否需要校正，並返回校正資訊
        :param text: 要檢查的文本
        :param corrections: 校正對照表
        :return: (需要校正?, 校正後文本, 原始文本, 實際校正部分列表)
        """
        corrected_text = text
        actual_corrections = []

        for error, correction in corrections.items():
            if error in text:
                corrected_text = corrected_text.replace(error, correction)
                actual_corrections.append((error, correction))

        needs_correction = len(actual_corrections) > 0 and corrected_text != text
        return needs_correction, corrected_text, text, actual_corrections

    def process_subtitle_item(self, sub, corrections):
        """
        處理單個字幕項目，安全地處理索引
        :param sub: 字幕項目
        :param corrections: 校正對照表
        :return: 處理後的值元組或None
        """
        try:
            # 確保所有必要屬性存在
            if not hasattr(sub, 'index') or not hasattr(sub, 'start') or \
               not hasattr(sub, 'end') or not hasattr(sub, 'text'):
                self.logger.warning(f"字幕項目缺少必要屬性: {sub}")
                return None

            # 確保 index 是有效的整數
            try:
                index = int(sub.index)
            except (ValueError, TypeError):
                self.logger.warning(f"無效的字幕索引: {sub.index}")
                return None

            # 轉換文本
            from utils.text_utils import simplify_to_traditional
            traditional_text = simplify_to_traditional(sub.text)
            corrected_text = traditional_text
            has_corrections = False
            correction_details = None

            # 檢查校正
            for error, correction in corrections.items():
                if error in traditional_text:
                    corrected_text = corrected_text.replace(error, correction)
                    has_corrections = True
                    correction_details = (error, correction)
                    break

            # 準備基本值
            base_values = [
                index,                    # 索引
                str(sub.start),          # 開始時間
                str(sub.end),            # 結束時間
                corrected_text,          # 文本
                '✅' if has_corrections else ''  # 校正標記
            ]

            # 根據顯示模式添加額外值
            if self.parent.display_mode == "audio_srt":
                values = ["▶"] + base_values
            else:
                values = base_values

            # 如果有校正，保存校正狀態
            if has_corrections and correction_details:
                error, correction = correction_details
                self.parent.correction_state_manager.add_correction_state(
                    str(index),
                    traditional_text,
                    corrected_text,
                    'correct'
                )

            return tuple(values)

        except Exception as e:
            self.logger.error(f"處理字幕項目時出錯: {str(e)}", exc_info=True)
            return None