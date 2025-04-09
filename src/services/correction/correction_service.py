"""文本校正服務模組"""

import csv
import logging
import os
import time
from typing import Dict, List, Tuple, Optional, Any, Union, Callable

class CorrectionService:
    """文本校正服務類別，處理文本校正相關操作"""

    def __init__(self, database_file: Optional[str] = None, on_correction_change: Optional[Callable] = None):
        """
        初始化校正服務
        :param database_file: 校正資料庫檔案路徑
        :param on_correction_change: 校正資料變化時的回調函數
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.database_file = database_file
        self.corrections: Dict[str, str] = {}
        self.correction_states: Dict[str, str] = {}  # 項目索引 -> 校正狀態 ('correct' 或 'error')
        self.original_texts: Dict[str, str] = {}     # 項目索引 -> 原始文本
        self.corrected_texts: Dict[str, str] = {}    # 項目索引 -> 校正後文本
        self.on_correction_change = on_correction_change

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

            # 觸發回調函數，通知校正資料已更新
            if self.on_correction_change and callable(self.on_correction_change):
                self.on_correction_change()

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

    def add_correction(self, error: str, correction: str, apply_to_existing: bool = False) -> int:
        """
        添加校正對照，並可選擇應用到現有文本

        Args:
            error: 錯誤字
            correction: 校正字
            apply_to_existing: 是否應用到現有文本

        Returns:
            int: 如果 apply_to_existing 為 True，返回更新的項目數量；否則返回 1 表示成功添加，0 表示失敗
        """
        if not error or not correction:
            return 0

        # 添加校正規則
        self.corrections[error] = correction

        # 儲存到資料庫
        if self.database_file:
            self.save_corrections()

        # 如果不需要應用到現有文本，直接返回
        if not apply_to_existing:
            return 1

        # 計數更新的項目
        updated_count = 0

        # 檢查並更新所有現有的文本
        for index in list(self.original_texts.keys()):
            original_text = self.original_texts.get(index, "")

            if error in original_text:
                # 應用新的校正規則
                corrected_text = original_text.replace(error, correction)

                # 只有當校正結果不同時才更新
                if corrected_text != original_text:
                    # 更新校正文本
                    self.corrected_texts[index] = corrected_text

                    # 確保狀態設為 'correct'
                    self.correction_states[index] = 'correct'

                    updated_count += 1

        # 觸發回調函數，通知校正資料已更新
        if self.on_correction_change and callable(self.on_correction_change):
            self.on_correction_change()

        return updated_count

    def remove_correction(self, error: str) -> bool:
        """
        移除校正對照
        :param error: 錯誤字
        :return: 是否成功移除
        """
        if error in self.corrections:
            del self.corrections[error]

            # 儲存到資料庫
            if self.database_file:
                self.save_corrections()

            # 觸發回調函數，通知校正資料已更新
            if self.on_correction_change and callable(self.on_correction_change):
                self.on_correction_change()

            return True
        return False

    def apply_correction_to_text(self, text: str) -> Tuple[bool, str]:
        """
        應用校正規則到指定文本

        Args:
            text: 要校正的文本

        Returns:
            Tuple[bool, str]: (是否已進行校正, 校正後的文本)
        """
        needs_correction, corrected_text, _, _ = self.check_text_for_correction(text)
        return (needs_correction, corrected_text)

    def apply_new_correction(self, error: str, correction: str) -> int:
        """
        應用新添加的校正規則並更新界面

        Args:
            error: 錯誤字
            correction: 校正字
        """
        # 應用新的校正規則，並應用到現有文本
        updated_count = self.add_correction(error, correction, apply_to_existing=True)
        return updated_count

    def update_display_status(self, tree_view, display_mode):
        """
        更新樹視圖中的校正狀態顯示
        :param tree_view: 樹狀視圖控件
        :param display_mode: 當前顯示模式
        """
        try:
            for item in tree_view.get_children():
                values = list(tree_view.item(item, 'values'))

                # 獲取索引位置
                if display_mode in ["all", "audio_srt"]:
                    index_pos = 1
                    text_pos = 4
                else:  # "srt" 或 "srt_word" 模式
                    index_pos = 0
                    text_pos = 3

                # 確保索引位置有效
                if len(values) <= index_pos:
                    continue

                index = str(values[index_pos])

                # 檢查是否有校正狀態
                state = self.get_correction_state(index)

                # 更新圖標和文本
                if state == 'correct' and index in self.corrected_texts:
                    values[-1] = '✅'
                    if text_pos < len(values):
                        values[text_pos] = self.corrected_texts.get(index, values[text_pos])
                elif state == 'error' and index in self.original_texts:
                    values[-1] = '❌'
                    if text_pos < len(values):
                        values[text_pos] = self.original_texts.get(index, values[text_pos])

                # 更新樹狀視圖顯示
                tree_view.item(item, values=tuple(values))
        except Exception as e:
            self.logger.error(f"更新校正狀態顯示時出錯: {e}")

    def correct_text(self, text: str, corrections: Optional[Dict[str, str]] = None) -> Tuple[bool, str, str, List]:
        """
        根據校正對照表修正文本中的錯誤字

        Args:
            text: 原始文本
            corrections: 校正對照表，如果為 None 則使用內部的校正表

        Returns:
            tuple: (是否需要校正, 校正後的文本, 原始文本, 實際應用的校正列表)
        """
        # 如果未提供校正表，使用內部儲存的
        if corrections is None:
            corrections = self.corrections

        corrected_text = text
        needs_correction = False
        actual_corrections = []  # 添加這一行，記錄實際應用的校正

        for error_char, correction_char in corrections.items():
            if error_char in corrected_text:
                corrected_text = corrected_text.replace(error_char, correction_char)
                needs_correction = True
                actual_corrections.append((error_char, correction_char))  # 記錄應用的校正

        return needs_correction, corrected_text, text, actual_corrections  # 返回4個值

    def set_correction_state(self, index: str, original_text: str, corrected_text: str, state: str = 'correct') -> None:
        """
        設定項目的校正狀態
        :param index: 項目索引
        :param original_text: 原始文本
        :param corrected_text: 校正後文本
        :param state: 校正狀態 ('correct', 'error' 或空字符串)
        """
        # 確保索引是字符串
        index = str(index)

        # 確保文本是字符串
        original_text = str(original_text) if original_text is not None else ""
        corrected_text = str(corrected_text) if corrected_text is not None else ""

        # 只有在原文和校正文本不同時才設置狀態
        if original_text != corrected_text:
            self.correction_states[index] = state
            self.original_texts[index] = original_text
            self.corrected_texts[index] = corrected_text
            self.logger.debug(f"設置索引 {index} 的校正狀態為 {state}")
        else:
            # 如果文本相同，則移除校正狀態
            self.remove_correction_state(index)

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
        # 確保索引是字符串
        index = str(index)

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

            # 創建新的校正狀態集合
            new_correction_states = {}
            new_original_texts = {}
            new_corrected_texts = {}

            # 對每個索引重新檢查
            for index in all_indices:
                # 獲取原始文本
                original_text = self.original_texts.get(index, "")
                if not original_text:
                    self.logger.debug(f"索引 {index} 沒有原始文本，跳過")
                    continue

                # 重新檢查是否需要校正
                needs_correction, corrected_text, original_text, _ = self.check_text_for_correction(original_text)

                if needs_correction:
                    # 獲取當前狀態（如果存在）
                    current_state = self.correction_states.get(index, 'correct')

                    # 保存到新狀態中
                    new_correction_states[index] = current_state
                    new_original_texts[index] = original_text
                    new_corrected_texts[index] = corrected_text

                    self.logger.debug(f"索引 {index} 需要校正，狀態為 {current_state}")

            # 用新的狀態替換舊的狀態（這樣可以完全清除不再需要的狀態）
            self.correction_states = new_correction_states
            self.original_texts = new_original_texts
            self.corrected_texts = new_corrected_texts

            self.logger.info(f"校正狀態刷新完成，保留 {len(self.correction_states)} 個有效狀態")
        except Exception as e:
            self.logger.error(f"刷新校正狀態時出錯: {e}")

    def handle_text_split(self, original_index: str, split_texts: List[str], split_indices: List[str] = None) -> List[Tuple[str, str, str]]:
        """
        處理文本拆分時的校正狀態轉移

        Args:
            original_index: 原始文本的索引
            split_texts: 拆分後的文本列表
            split_indices: 拆分後的索引列表（可選）

        Returns:
            List[Tuple[str, str, str]]: 每個新段落的 (索引, 狀態, 圖示)
        """
        results = []

        # 獲取原始校正狀態
        original_state = self.correction_states.get(original_index, '')

        # 如果未提供分割索引，則使用默認計算方式
        if split_indices is None:
            split_indices = [str(int(original_index) + i if i > 0 else original_index) for i in range(len(split_texts))]

        # 檢查每個新文本段落
        for i, (text, new_index) in enumerate(zip(split_texts, split_indices)):
            # 檢查新文本是否需要校正
            needs_correction, corrected_text, _, _ = self.check_text_for_correction(text)

            if needs_correction:
                # 新段落需要校正
                state = 'error'  # 初始為未校正狀態
                icon = '❌'

                # 保存校正狀態
                self.set_correction_state(new_index, text, corrected_text, state)
            else:
                # 新段落不需要校正
                state = ''
                icon = ''

                # 清除可能存在的校正狀態
                self.remove_correction_state(new_index)

            results.append((new_index, state, icon))

        return results

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

    def check_text_for_correction(self, text):
        """檢查文本是否需要校正，並返回校正資訊"""
        try:
            # 添加遞歸保護
            if hasattr(self, '_checking_text') and self._checking_text:
                return False, text, text, []

            self._checking_text = True

            if not text:  # 確保 text 不為空
                return False, "", "", []

            # 確保使用字符串類型
            text = str(text)

            corrected_text = text
            actual_corrections = []

            # 記錄進行了哪些替換
            for error, correction in self.corrections.items():
                if error in text:
                    corrected_text = corrected_text.replace(error, correction)
                    actual_corrections.append((error, correction))

            needs_correction = len(actual_corrections) > 0 and corrected_text != text

            return needs_correction, corrected_text, text, actual_corrections  # 返回4個值
        finally:
            if hasattr(self, '_checking_text'):
                self._checking_text = False

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

    def serialize_state(self) -> Dict[str, Dict[str, Any]]:
        """
        序列化當前校正狀態
        :return: 序列化後的校正狀態
        """
        serialized = {}
        # 確保包含所有相關狀態
        indices = set(list(self.correction_states.keys()) +
                    list(self.original_texts.keys()) +
                    list(self.corrected_texts.keys()))

        for index in indices:
            state = self.correction_states.get(index, '')
            original = self.original_texts.get(index, '')
            corrected = self.corrected_texts.get(index, '')

            # 只有當確實有校正需求時才保存
            if original != corrected:
                serialized[index] = {
                    'state': state,
                    'original': original,
                    'corrected': corrected,
                    'timestamp': time.time()  # 添加時間戳以便追蹤
                }
        return serialized

    def deserialize_state(self, state_data, id_mapping=None):
        """
        從序列化數據恢復校正狀態，支持 ID 映射

        Args:
            state_data: 序列化的校正狀態
            id_mapping: ID 映射表 {原始ID: 新ID}
        """
        # 清除現有狀態
        self.clear_correction_states()

        if not state_data:
            return

        # 恢復校正狀態
        for index, data in state_data.items():
            # 檢查是否需要映射索引
            if id_mapping and index in id_mapping:
                mapped_index = id_mapping[index]
                self.logger.debug(f"應用 ID 映射: {index} -> {mapped_index}")
                index = mapped_index

            state = data.get('state', 'correct')
            original = data.get('original', '')
            corrected = data.get('corrected', '')

            # 確保有實際的校正需求
            if original and corrected and original != corrected:
                self.correction_states[index] = state
                self.original_texts[index] = original
                self.corrected_texts[index] = corrected

        self.logger.info(f"已從序列化數據恢復 {len(self.correction_states)} 個校正狀態")

    def transfer_correction_states(self, index_mapping: Dict[str, str]) -> None:
        """
        在索引變更時轉移校正狀態
        :param index_mapping: 舊索引到新索引的映射 {舊索引: 新索引}
        """
        new_states = {}
        new_original = {}
        new_corrected = {}

        # 記錄處理過的舊索引
        processed_old_indices = set()

        for old_index, new_index in index_mapping.items():
            if old_index in self.correction_states:
                new_states[new_index] = self.correction_states[old_index]
                new_original[new_index] = self.original_texts.get(old_index, '')
                new_corrected[new_index] = self.corrected_texts.get(old_index, '')
                processed_old_indices.add(old_index)

        # 保留未處理的索引
        for index in set(self.correction_states.keys()) - processed_old_indices:
            new_states[index] = self.correction_states[index]
            new_original[index] = self.original_texts.get(index, '')
            new_corrected[index] = self.corrected_texts.get(index, '')

        # 更新狀態
        self.correction_states = new_states
        self.original_texts = new_original
        self.corrected_texts = new_corrected

        self.logger.info(f"已轉移 {len(new_states)} 個項目的校正狀態")

    def toggle_correction_icon(self, tree_view, item: str, index: str, text: str, display_mode: str) -> None:
        """
        切換校正圖標狀態 - 集中處理界面和邏輯

        Args:
            tree_view: 樹狀視圖控件
            item: 樹狀視圖項目ID
            index: 項目索引
            text: 當前文本
            display_mode: 顯示模式
        """
        try:
            self.logger.debug(f"切換校正圖標開始: 索引={index}, 項目ID={item}")

            # 獲取當前校正狀態
            current_state = self.get_correction_state(index)

            # 檢查文本是否需要校正
            needs_correction, corrected_text, original_text, _ = self.check_text_for_correction(text)

            if not needs_correction:
                self.logger.debug(f"文本不需要校正，不做任何更改: {text}")
                return

            # 獲取文本位置索引
            text_index = self._get_text_index_for_mode(display_mode)

            # 獲取當前值
            values = list(tree_view.item(item, "values"))
            if not values:
                self.logger.warning(f"項目 {item} 沒有值，無法切換校正狀態")
                return

            # 切換校正狀態
            new_state = 'error' if current_state == 'correct' else 'correct'

            # 更新顯示
            values[-1] = '❌' if new_state == 'error' else '✅'
            if text_index is not None and text_index < len(values):
                values[text_index] = original_text if new_state == 'error' else corrected_text

            # 更新校正狀態
            self.set_correction_state(index, original_text, corrected_text, new_state)

            # 更新樹狀圖顯示
            tree_view.item(item, values=tuple(values))
        except Exception as e:
            self.logger.error(f"切換校正圖標時出錯: {e}", exc_info=True)

    def _get_text_index_for_mode(self, display_mode: str) -> Optional[int]:
        """獲取特定顯示模式下文本的索引位置"""
        if display_mode in ["all", "audio_srt"]:
            return 4
        elif display_mode in ["srt", "srt_word"]:
            return 3
        return None

    def create_correction_states_for_split_items(self, original_index, texts, new_indices):
        """為拆分後的項目創建校正狀態

        Args:
            original_index: 原始項目索引
            texts: 拆分後的文本列表
            new_indices: 新索引列表

        Returns:
            Dict[str, Dict]: 新的校正狀態
        """
        # 保存原始校正狀態
        original_state = None
        if original_index in self.correction_states:
            original_state = self.correction_states[original_index]

        # 新的校正狀態字典
        new_correction_states = {}

        # 檢查每個文本是否需要校正
        for i, (text, new_index) in enumerate(zip(texts, new_indices)):
            needs_correction, corrected_text, original_text, _ = self.check_text_for_correction(text)

            if needs_correction:
                # 為第一個項目保留原始狀態（如果有）
                if i == 0 and original_state:
                    state = original_state
                else:
                    state = 'error'  # 默認為未校正狀態

                # 設置校正狀態
                self.set_correction_state(
                    new_index,
                    text,  # 原始文本
                    corrected_text,  # 校正後文本
                    state
                )

                # 保存到結果字典
                new_correction_states[new_index] = {
                    'state': state,
                    'original': text,
                    'corrected': corrected_text
                }

        return new_correction_states

    def apply_correction_to_all(self, error: str, correction: str, tree_view, text_position_func, display_mode: str) -> int:
        """
        將校正規則應用到所有項目

        Args:
            error: 錯誤字
            correction: 校正字
            tree_view: 樹狀視圖控件
            text_position_func: 獲取文本位置的函數
            display_mode: 顯示模式

        Returns:
            int: 更新的項目數量
        """
        try:
            # 先添加新規則到校正字典
            self.corrections[error] = correction

            # 保存到資料庫
            if self.database_file:
                self.save_corrections()

            # 應用到所有項目
            updated_count = 0

            # 獲取文本位置索引
            text_index = text_position_func() if callable(text_position_func) else self._get_text_index_for_mode(display_mode)

            if text_index is None:
                self.logger.warning("無法獲取文本位置索引")
                return 0

            # 遍歷所有樹項目
            for item_id in tree_view.get_children():
                values = list(tree_view.item(item_id, "values"))

                # 確保索引有效
                if len(values) <= text_index:
                    continue

                # 獲取文本
                text = values[text_index]

                # 檢查文本是否含有錯誤字
                if error in text:
                    # 獲取當前模式下的索引位置
                    index_pos = 1 if display_mode in ["all", "audio_srt"] else 0
                    item_index = str(values[index_pos]) if len(values) > index_pos else ""

                    # 應用校正
                    corrected_text = text.replace(error, correction)

                    # 更新顯示文本
                    values[text_index] = corrected_text

                    # 設置校正圖標
                    values[-1] = '✅'

                    # 更新樹項目
                    tree_view.item(item_id, values=tuple(values))

                    # 設置校正狀態
                    if item_index:
                        self.set_correction_state(
                            item_index,
                            text,  # 原始文本
                            corrected_text,  # 校正後文本
                            'correct'  # 已校正狀態
                        )

                    updated_count += 1

            return updated_count

        except Exception as e:
            self.logger.error(f"應用校正規則到所有項目時出錯: {e}", exc_info=True)
            return 0

    def export_corrections(self, export_file_path: str) -> bool:
        """
        匯出校正規則到CSV檔案

        Args:
            export_file_path: 要匯出的檔案路徑

        Returns:
            bool: 是否成功匯出
        """
        try:
            with open(export_file_path, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["錯誤字", "校正字"])
                for error, correction in self.corrections.items():
                    writer.writerow([error, correction])

            self.logger.info(f"成功匯出 {len(self.corrections)} 條校正規則至 {export_file_path}")
            return True

        except Exception as e:
            self.logger.error(f"匯出校正規則失敗: {e}")
            return False

    def import_corrections(self, import_file_path: str, merge_mode: str = 'replace') -> Tuple[bool, int]:
        """
        從CSV檔案匯入校正規則

        Args:
            import_file_path: 要匯入的檔案路徑
            merge_mode: 合併模式，'replace'表示替換現有規則，'append'表示追加

        Returns:
            Tuple[bool, int]: (是否成功匯入, 匯入的規則數量)
        """
        try:
            imported_corrections = {}

            with open(import_file_path, 'r', encoding='utf-8-sig') as file:
                reader = csv.reader(file)
                # 嘗試跳過標題行
                try:
                    next(reader)
                except StopIteration:
                    return (True, 0)

                for row in reader:
                    if len(row) >= 2:
                        error, correction = row
                        imported_corrections[error] = correction

            # 根據合併模式處理
            if merge_mode == 'replace':
                self.corrections = imported_corrections
            elif merge_mode == 'append':
                self.corrections.update(imported_corrections)
            else:
                self.logger.warning(f"未知的合併模式: {merge_mode}，使用'replace'模式")
                self.corrections = imported_corrections

            # 保存到資料庫
            if self.database_file:
                self.save_corrections()

            count = len(imported_corrections)
            self.logger.info(f"成功從 {import_file_path} 匯入 {count} 條校正規則")

            # 觸發回調函數，通知校正資料已更新
            if self.on_correction_change and callable(self.on_correction_change):
                self.on_correction_change()

            return (True, count)

        except Exception as e:
            self.logger.error(f"匯入校正規則失敗: {e}")
            return (False, 0)

    def get_all_corrections(self) -> Dict[str, str]:
        """
        獲取所有校正規則

        Returns:
            Dict[str, str]: 所有校正規則的字典 {錯誤字: 校正字}
        """
        return self.corrections.copy()