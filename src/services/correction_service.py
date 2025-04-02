"""文本校正服務模組"""

import csv
import logging
import os
import time
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

    def correct_text(self, text: str, corrections: Optional[Dict[str, str]] = None) -> Tuple[bool, str, str]:
        """
        根據校正對照表修正文本中的錯誤字

        Args:
            text: 原始文本
            corrections: 校正對照表，如果為 None 則使用內部的校正表

        Returns:
            tuple: (是否需要校正, 校正後的文本, 原始文本)
        """
        # 如果未提供校正表，使用內部儲存的
        if corrections is None:
            corrections = self.corrections

        corrected_text = text
        needs_correction = False

        for error_char, correction_char in corrections.items():
            if error_char in corrected_text:
                corrected_text = corrected_text.replace(error_char, correction_char)
                needs_correction = True

        return needs_correction, corrected_text, text

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


    # 在 correction_service.py 中修改 handle_text_split 方法
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


    def add_correction_state(self, index: str, original_text: str, corrected_text: str, state: str = 'correct') -> None:
        """
        添加項目的校正狀態 (set_correction_state 的別名)
        :param index: 項目索引
        :param original_text: 原始文本
        :param corrected_text: 校正後文本
        :param state: 校正狀態 ('correct' 或 'error')
        """
        return self.set_correction_state(index, original_text, corrected_text, state)

    def toggle_correction_icon(self, item: str, index: str, text: str) -> None:
        """
        切換校正圖標狀態

        Args:
            item: 樹狀視圖項目ID
            index: 項目索引
            text: 當前文本
        """
        try:
            self.logger.debug(f"切換校正圖標開始: 索引={index}, 項目ID={item}")

            # 保存操作前的狀態
            original_state = self.get_current_state()
            original_correction = self.correction_service.serialize_state()

            # 記錄切換前的校正狀態
            before_state = self.correction_service.get_correction_state(index)
            self.logger.debug(f"切換前校正狀態: {before_state}")

            # 獲取當前項目的值
            values = list(self.tree.item(item, "values"))
            if not values:
                self.logger.warning(f"項目 {item} 沒有值，無法切換校正狀態")
                return

            # 檢查文本是否需要校正
            needs_correction, corrected_text, original_text, _ = self.correction_service.check_text_for_correction(text)

            if not needs_correction:
                self.logger.debug(f"文本不需要校正，不做任何更改: {text}")
                return

            # 獲取當前校正圖標
            correction_mark = values[-1] if values else ''

            # 切換校正狀態
            if correction_mark == '✅':
                # 從已校正切換到未校正
                values[-1] = '❌'

                # 獲取文本位置索引
                text_index = None
                if self.display_mode == self.DISPLAY_MODE_ALL:
                    text_index = 4
                elif self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
                    text_index = 4
                elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
                    text_index = 3
                else:  # SRT 模式
                    text_index = 3

                # 更新顯示文本為原始文本
                if text_index is not None and text_index < len(values):
                    values[text_index] = original_text

                # 更新校正狀態
                self.correction_service.set_correction_state(
                    index,
                    original_text,
                    corrected_text,
                    'error'  # 設置為未校正狀態
                )
            else:  # correction_mark == '❌' 或空白
                # 從未校正或無狀態切換到已校正
                values[-1] = '✅'

                # 獲取文本位置索引
                text_index = None
                if self.display_mode == self.DISPLAY_MODE_ALL:
                    text_index = 4
                elif self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
                    text_index = 4
                elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
                    text_index = 3
                else:  # SRT 模式
                    text_index = 3

                # 更新顯示文本為校正後文本
                if text_index is not None and text_index < len(values):
                    values[text_index] = corrected_text

                # 更新校正狀態
                self.correction_service.set_correction_state(
                    index,
                    original_text,
                    corrected_text,
                    'correct'  # 設置為已校正狀態
                )

            # 更新樹狀圖顯示
            self.tree.item(item, values=tuple(values))

            # 記錄切換後的校正狀態
            after_state = self.correction_service.get_correction_state(index)
            self.logger.debug(f"切換後校正狀態: {after_state}")

            # 更新 SRT 數據
            self.update_srt_data_from_treeview()

            # 保存當前狀態，包含完整的操作信息和校正狀態
            current_state = self.get_current_state()
            current_correction = self.correction_service.serialize_state()

            # 創建操作信息
            operation_info = {
                'type': 'toggle_correction',
                'description': '切換校正狀態',
                'item_id': item,
                'index': index,
                'before_state': before_state,
                'after_state': after_state,
                'original_state': original_state,
                'original_correction': original_correction
            }

            # 保存到狀態管理器
            self.state_manager.save_state(current_state, operation_info, current_correction)

            self.logger.debug(f"校正圖標切換完成: 索引={index}, 項目ID={item}")

        except Exception as e:
            self.logger.error(f"切換校正圖標時出錯: {e}", exc_info=True)

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