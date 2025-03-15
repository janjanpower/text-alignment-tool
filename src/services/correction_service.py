"""文本校正服務模組"""

import csv
import logging
import os
from typing import Dict, List, Tuple, Optional, Any

class CorrectionService:
    """文本校正服務類別，處理文本校正相關操作"""

    def __init__(self, database_file: Optional[str] = None):
        """
        初始化校正服務
        :param database_file: 校正資料庫檔案路徑
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.database_file = database_file
        self.corrections: Dict[str, str] = {}
        self.correction_states: Dict[str, str] = {}  # 項目索引 -> 校正狀態 ('correct' 或 'error')
        self.original_texts: Dict[str, str] = {}     # 項目索引 -> 原始文本
        self.corrected_texts: Dict[str, str] = {}    # 項目索引 -> 校正後文本

        # 如果提供了資料庫檔案路徑，立即載入校正資料
        if database_file and os.path.exists(database_file):
            self.load_corrections()

    def load_corrections(self) -> Dict[str, str]:
        """
        載入校正資料庫
        :return: 校正對照表 {錯誤字: 校正字}
        """
        self.corrections.clear()

        if not self.database_file or not os.path.exists(self.database_file):
            self.logger.warning(f"校正資料庫檔案不存在: {self.database_file}")
            return self.corrections

        try:
            with open(self.database_file, 'r', encoding='utf-8-sig') as file:
                reader = csv.reader(file)
                # 嘗試跳過標題行
                try:
                    next(reader)
                except StopIteration:
                    # 檔案為空，直接返回空字典
                    return self.corrections

                for row in reader:
                    if len(row) >= 2:
                        error, correction = row
                        self.corrections[error] = correction

            self.logger.info(f"成功從 {self.database_file} 載入 {len(self.corrections)} 條校正規則")

        except Exception as e:
            self.logger.error(f"載入校正資料庫失敗: {e}")

        return self.corrections

    def save_corrections(self, corrections: Optional[Dict[str, str]] = None) -> bool:
        """
        儲存校正資料庫
        :param corrections: 校正對照表，如果為 None 則使用當前的校正表
        :return: 是否成功儲存
        """
        if not self.database_file:
            self.logger.error("未設定校正資料庫檔案路徑")
            return False

        try:
            # 確保目錄存在
            os.makedirs(os.path.dirname(self.database_file), exist_ok=True)

            # 使用傳入的校正表或當前校正表
            correction_data = corrections if corrections is not None else self.corrections

            with open(self.database_file, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["錯誤字", "校正字"])
                for error, correction in correction_data.items():
                    writer.writerow([error, correction])

            self.logger.info(f"成功儲存 {len(correction_data)} 條校正規則至 {self.database_file}")
            return True

        except Exception as e:
            self.logger.error(f"儲存校正資料庫失敗: {e}")
            return False

    def set_database_file(self, database_file: str) -> None:
        """
        設定校正資料庫檔案路徑
        :param database_file: 校正資料庫檔案路徑
        """
        self.database_file = database_file
        if os.path.exists(database_file):
            self.load_corrections()

    def add_correction(self, error: str, correction: str) -> bool:
        """
        添加校正對照
        :param error: 錯誤字
        :param correction: 校正字
        :return: 是否成功添加
        """
        if not error or not correction:
            return False

        self.corrections[error] = correction
        return True

    def remove_correction(self, error: str) -> bool:
        """
        移除校正對照
        :param error: 錯誤字
        :return: 是否成功移除
        """
        if error in self.corrections:
            del self.corrections[error]
            return True
        return False

    def correct_text(self, text: str) -> Tuple[bool, str, List[Tuple[str, str]]]:
        """
        校正文本，返回校正結果
        :param text: 原始文本
        :return: (是否需要校正, 校正後文本, 實際校正部分列表)
        """
        if not text or not self.corrections:
            return False, text, []

        corrected_text = text
        applied_corrections = []

        for error, correction in self.corrections.items():
            if error in text:
                corrected_text = corrected_text.replace(error, correction)
                applied_corrections.append((error, correction))

        needs_correction = len(applied_corrections) > 0 and corrected_text != text
        return needs_correction, corrected_text, applied_corrections

    def set_correction_state(self, index: str, original_text: str, corrected_text: str, state: str = 'correct') -> None:
        """
        設定項目的校正狀態
        :param index: 項目索引
        :param original_text: 原始文本
        :param corrected_text: 校正後文本
        :param state: 校正狀態 ('correct', 'error' 或空字符串)
        """
        # 檢查是否需要校正
        if original_text != corrected_text:
            # 有校正需求，設置狀態
            self.correction_states[index] = state
            self.original_texts[index] = original_text
            self.corrected_texts[index] = corrected_text
            self.logger.debug(f"設置索引 {index} 的校正狀態為 {state}, 原文: {original_text}, 校正後: {corrected_text}")
        else:
            # 沒有校正需求，移除校正狀態
            if index in self.correction_states:
                del self.correction_states[index]
            if index in self.original_texts:
                del self.original_texts[index]
            if index in self.corrected_texts:
                del self.corrected_texts[index]
            self.logger.debug(f"索引 {index} 不需要校正，移除校正狀態")

    def toggle_correction_state(self, index: str) -> str:
        """
        切換校正狀態
        :param index: 項目索引
        :return: 新的狀態 ('correct' 或 'error' 或空字符串)
        """
        if index in self.correction_states:
            # 切換狀態
            current_state = self.correction_states[index]
            # 在 correct 和 error 之間切換
            new_state = 'error' if current_state == 'correct' else 'correct'
            self.correction_states[index] = new_state
            self.logger.debug(f"切換索引 {index} 的校正狀態: {current_state} -> {new_state}")
            return new_state
        else:
            # 如果沒有現有狀態，但有原始文本和校正文本，則創建一個新的狀態
            if index in self.original_texts and index in self.corrected_texts:
                # 默認為 correct 狀態
                self.correction_states[index] = 'correct'
                self.logger.debug(f"為索引 {index} 創建新的校正狀態: correct")
                return 'correct'
            else:
                # 沒有足夠的信息來設置校正狀態
                self.logger.warning(f"無法切換索引 {index} 的校正狀態: 缺少原始文本或校正文本")

        # 如果沒有相關數據，返回空字符串表示無法切換
        return ''

    def get_correction_state(self, index: str) -> str:
        """
        獲取項目的校正狀態
        :param index: 項目索引
        :return: 校正狀態 ('correct', 'error' 或空字符串)
        """
        if index in self.correction_states:
            return self.correction_states[index]
        else:
            # 如果索引不存在但有校正需求，嘗試檢查是否需要校正
            if index in self.original_texts and index in self.corrected_texts:
                # 比較原始文本和校正文本
                if self.original_texts[index] != self.corrected_texts[index]:
                    self.logger.info(f"索引 {index} 有校正需求但沒有狀態，設置為 'correct'")
                    self.correction_states[index] = 'correct'
                    return 'correct'
            return ''

    def get_text_for_display(self, index: str) -> str:
        """
        依據校正狀態獲取要顯示的文本
        :param index: 項目索引
        :return: 根據校正狀態返回原始文本或校正後文本
        """
        if index in self.correction_states:
            state = self.correction_states[index]

            if state == 'correct':
                return self.corrected_texts.get(index, '')
            else:  # state == 'error'
                return self.original_texts.get(index, '')

        return ''

    def refresh_all_correction_states(self) -> None:
        """
        重新檢查和更新所有項目的校正狀態
        """
        try:
            # 保存當前所有索引
            all_indices = list(set(list(self.correction_states.keys()) +
                                list(self.original_texts.keys()) +
                                list(self.corrected_texts.keys())))

            self.logger.info(f"開始刷新所有校正狀態，共 {len(all_indices)} 個索引")

            # 對每個索引重新檢查
            for index in all_indices:
                # 獲取原始文本
                original_text = self.original_texts.get(index, "")
                if not original_text:
                    self.logger.debug(f"索引 {index} 沒有原始文本，跳過")
                    continue

                # 重新檢查是否需要校正
                needs_correction, corrected_text, _, _ = self.check_text_for_correction(original_text)

                if needs_correction:
                    # 更新校正狀態，保持原有的校正狀態類型（已校正或未校正）
                    current_state = self.correction_states.get(index, 'correct')
                    self.logger.debug(f"索引 {index} 需要校正，設置狀態為 {current_state}")
                    self.set_correction_state(index, original_text, corrected_text, current_state)
                else:
                    # 移除不需要校正的項目
                    self.logger.debug(f"索引 {index} 不需要校正，移除校正狀態")
                    self.remove_correction_state(index)

            self.logger.info("校正狀態刷新完成")
        except Exception as e:
            self.logger.error(f"刷新校正狀態時出錯: {e}")



    def remove_correction_state(self, index: str) -> None:
        """
        移除項目的校正狀態
        :param index: 項目索引
        """
        if index in self.correction_states:
            del self.correction_states[index]
        if index in self.original_texts:
            del self.original_texts[index]
        if index in self.corrected_texts:
            del self.corrected_texts[index]

    def clear_correction_states(self) -> None:
        """清除所有校正狀態"""
        self.correction_states.clear()
        self.original_texts.clear()
        self.corrected_texts.clear()

    def check_text_for_correction(self, text: str) -> Tuple[bool, str, str, List[Tuple[str, str]]]:
        """
        檢查文本是否需要校正，並返回校正資訊
        :param text: 要檢查的文本
        :return: (需要校正?, 校正後文本, 原始文本, 實際校正部分列表)
        """
        if not text:
            return False, "", "", []

        # 確保使用字符串類型
        text = str(text)

        # 檢查是否有載入校正數據
        if not hasattr(self, 'corrections') or not self.corrections:
            self.logger.debug("無校正數據，重新載入")
            self.load_corrections()

        if not self.corrections:
            self.logger.debug("沒有校正規則可用")
            return False, text, text, []

        corrected_text = text
        actual_corrections = []

        # 記錄進行了哪些替換
        for error, correction in self.corrections.items():
            if error in text:
                corrected_text = corrected_text.replace(error, correction)
                actual_corrections.append((error, correction))
                self.logger.debug(f"找到需要校正的文本: '{error}' -> '{correction}'")

        needs_correction = len(actual_corrections) > 0 and corrected_text != text

        # 記錄結果
        if needs_correction:
            self.logger.debug(f"文本需要校正: 原文='{text}', 校正後='{corrected_text}', 替換數={len(actual_corrections)}")
        else:
            self.logger.debug(f"文本無需校正: '{text}'")

        return needs_correction, corrected_text, text, actual_corrections

    def update_correction_states_after_split(self, original_index: str, new_texts: List[str]) -> None:
        """
        文本拆分後更新校正狀態
        :param original_index: 原始文本的索引
        :param new_texts: 拆分後的文本列表
        """
        # 清除原始索引的狀態
        self.remove_correction_state(original_index)

        # 檢查每個新文本段落
        for i, text in enumerate(new_texts):
            new_index = f"{original_index}_{i}"
            needs_correction, corrected, original, _ = self.check_text_for_correction(text)

            if needs_correction:
                self.set_correction_state(new_index, original, corrected, 'correct')

    def serialize_state(self) -> Dict[str, Dict[str, str]]:
        """
        序列化校正狀態，便於儲存和恢復
        :return: 可序列化的校正狀態字典
        """
        serialized = {}
        for index in self.correction_states:
            serialized[index] = {
                'state': self.correction_states.get(index, ''),
                'original': self.original_texts.get(index, ''),
                'corrected': self.corrected_texts.get(index, '')
            }

        return serialized

    def deserialize_state(self, state_data: Dict[str, Dict[str, str]]) -> None:
        """
        從序列化數據恢復校正狀態
        :param state_data: 序列化的校正狀態字典
        """
        self.clear_correction_states()

        for index, data in state_data.items():
            self.correction_states[index] = data.get('state', 'correct')
            self.original_texts[index] = data.get('original', '')
            self.corrected_texts[index] = data.get('corrected', '')

        self.logger.info(f"已恢復 {len(state_data)} 個項目的校正狀態")


    def transfer_correction_states(self, old_indices: Dict[str, str]) -> None:
        """
        在索引變更時轉移校正狀態
        :param old_indices: 舊索引到新索引的映射 {舊索引: 新索引}
        """
        new_states = {}
        new_original = {}
        new_corrected = {}

        for old_index, new_index in old_indices.items():
            if old_index in self.correction_states:
                new_states[new_index] = self.correction_states[old_index]
                new_original[new_index] = self.original_texts.get(old_index, '')
                new_corrected[new_index] = self.corrected_texts.get(old_index, '')

        # 更新狀態
        self.correction_states = new_states
        self.original_texts = new_original
        self.corrected_texts = new_corrected

        self.logger.info(f"已轉移 {len(new_states)} 個項目的校正狀態")

    def add_correction_state(self, index: str, original_text: str, corrected_text: str, state: str = 'correct') -> None:
        """
        添加項目的校正狀態 (set_correction_state 的別名)
        :param index: 項目索引
        :param original_text: 原始文本
        :param corrected_text: 校正後文本
        :param state: 校正狀態 ('correct' 或 'error')
        """
        return self.set_correction_state(index, original_text, corrected_text, state)