"""校正狀態管理器"""

import os
import logging
from typing import Dict, Optional, Tuple, List, Any
import tkinter as tk
from tkinter import ttk

class CorrectionStateManager:
    """校正狀態管理器，使用組合模式集成增強的狀態管理能力"""

    def __init__(self, tree, enhanced_state_manager=None):
        """
        初始化校正狀態管理器

        :param tree: 樹視圖控件
        :param enhanced_state_manager: 可選的增強狀態管理器實例
        """
        self.tree = tree
        self.enhanced_state_manager = enhanced_state_manager
        self.logger = logging.getLogger(self.__class__.__name__)

        # 核心資料結構
        self.correction_states = {}  # 記錄校正狀態
        self.original_texts = {}     # 原始文字
        self.corrected_texts = {}    # 校正後文字

        # 圖標定義
        self.icons = {
            'correct': '✅',
            'error': '❌'
        }

    def _save_toggle_operation(self, index, old_state, new_state):
        """保存狀態切換操作到增強狀態管理器"""
        if not self.enhanced_state_manager:
            return

        # 獲取當前應用狀態
        current_app_state = None
        if hasattr(self.enhanced_state_manager.gui, 'get_current_state'):
            current_app_state = self.enhanced_state_manager.gui.get_current_state()

        # 獲取當前校正狀態
        current_correction_state = self.serialize_state()

        # 構建操作信息
        operation_info = {
            'type': 'toggle_correction',
            'description': f'切換校正狀態: {index} ({old_state} -> {new_state})',
            'index': index,
            'old_state': old_state,
            'new_state': new_state
        }

        # 保存狀態
        if current_app_state:
            self.enhanced_state_manager.save_state(
                current_app_state,
                operation_info,
                current_correction_state
            )

    def handle_icon_click(self, index, tree_item):
        """處理圖標點擊事件"""
        try:
            if index not in self.correction_states or \
            index not in self.original_texts or \
            index not in self.corrected_texts:
                return

            # 獲取當前項目的值和標籤
            values = list(self.tree.item(tree_item)['values'])
            tags = list(self.tree.item(tree_item, 'tags') or ())
            current_state = self.correction_states[index]

            # 根據不同的顯示模式確定 SRT Text 和 V/X 欄位的索引
            # 分析 tree 的 columns 確定正確的索引
            columns = self.tree["columns"]

            # 找出 SRT Text 和 V/X 欄位的索引
            srt_text_idx = -1
            vx_idx = -1

            for i, col in enumerate(columns):
                if col == "SRT Text":
                    srt_text_idx = i
                elif col == "V/X":
                    vx_idx = i

            if srt_text_idx == -1 or vx_idx == -1:
                self.logger.warning(f"找不到 SRT Text 或 V/X 欄位: columns={columns}")
                return

            # 切換狀態和更新顯示
            if current_state == 'correct':
                # 從"已校正"狀態切換到"未校正"狀態
                self.correction_states[index] = 'error'
                values[vx_idx] = self.icons['error']  # 更新為 ❌

                # 如果存在校正前的原始文本，顯示原始文本
                if index in self.original_texts:
                    values[srt_text_idx] = self.original_texts[index]
            else:
                # 從"未校正"狀態切換到"已校正"狀態
                self.correction_states[index] = 'correct'
                values[vx_idx] = self.icons['correct']  # 更新為 ✅

                # 顯示校正後的文本
                if index in self.corrected_texts:
                    values[srt_text_idx] = self.corrected_texts[index]

            # 更新樹狀圖項目
            self.tree.item(tree_item, values=tuple(values))

            # 記錄操作
            self.logger.debug(f"校正狀態已切換: 索引={index}, 狀態={self.correction_states[index]}")

        except Exception as e:
            self.logger.error(f"處理圖標點擊時出錯: {e}")
            import traceback
            traceback.print_exc()

    def check_text_for_correction(self, text: str, corrections: dict) -> tuple[bool, str, str, list]:
        """
        檢查文本是否需要校正，並返回校正資訊

        Args:
            text: 要檢查的文本
            corrections: 校正對照表

        Returns:
            tuple: (需要校正?, 校正後文本, 原始文本, 實際校正部分列表)
        """
        corrected_text = text
        actual_corrections = []

        for error, correction in corrections.items():
            if error in text:
                corrected_text = corrected_text.replace(error, correction)
                actual_corrections.append((error, correction))

        needs_correction = len(actual_corrections) > 0 and corrected_text != text
        return needs_correction, corrected_text, text, actual_corrections

    def transfer_correction_states(self, old_mode: str, new_mode: str):
        """
        在模式切換時轉移校正狀態
        :param old_mode: 原始模式
        :param new_mode: 新模式
        """
        # 保存當前所有狀態
        temp_states = self.correction_states.copy()
        temp_original = self.original_texts.copy()
        temp_corrected = self.corrected_texts.copy()

        # 清除當前狀態
        self.correction_states.clear()
        self.original_texts.clear()
        self.corrected_texts.clear()

        # 遍歷原始狀態並根據不同模式的索引格式轉換
        for index in temp_states:
            # 保留原來的狀態
            state = temp_states[index]
            original = temp_original.get(index, "")
            corrected = temp_corrected.get(index, "")

            # 添加到新的狀態結構中
            self.correction_states[index] = state
            self.original_texts[index] = original
            self.corrected_texts[index] = corrected


    def add_correction_state(self, index: str, original_text: str, corrected_text: str, state: str = 'correct') -> None:
        """
        添加或更新校正狀態
        """
        # 只有當原文和校正文本不同時才添加狀態
        if original_text != corrected_text:
            self.correction_states[index] = state
            self.original_texts[index] = original_text
            self.corrected_texts[index] = corrected_text
        else:
            # 如果文本相同，清除該索引的校正狀態
            self.remove_correction_state(index)

    def remove_correction_state(self, index: str) -> None:
        """
        移除指定索引的校正狀態
        """
        if index in self.correction_states:
            del self.correction_states[index]
        if index in self.original_texts:
            del self.original_texts[index]
        if index in self.corrected_texts:
            del self.corrected_texts[index]

    def should_have_icon(self, text: str, corrections: dict) -> bool:
        """
        檢查文本是否應該有校正圖標
        """
        for error in corrections:
            if error in text:
                return True
        return False

    def update_correction_states_after_split(self, original_index: str, new_texts: list[str], corrections: dict) -> None:
        """
        文本拆分後更新校正狀態

        Args:
            original_index: 原始文本的索引
            new_texts: 拆分後的文本列表
            corrections: 校正對照表
        """
        # 清除原始索引的狀態
        self.remove_correction_state(original_index)

        # 檢查每個新文本段落
        for i, text in enumerate(new_texts):
            new_index = f"{original_index}_{i}"
            needs_correction, corrected, original, _ = self.check_text_for_correction(text, corrections)

            if needs_correction:
                self.add_correction_state(new_index, original, corrected, 'correct')

    def get_icon_for_text(self, text: str, corrections: dict) -> str:
        """
        根據文本內容返回適當的圖標
        """
        return self.icons['correct'] if self.should_have_icon(text, corrections) else ''

    def get_current_state(self, index: str) -> str:
        """獲取當前狀態"""
        return self.correction_states.get(index, 'correct')

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

    def clear_correction_states(self) -> None:
        """清除所有校正狀態"""
        self.correction_states.clear()
        self.original_texts.clear()
        self.corrected_texts.clear()


    def toggle_correction_state(self, index: str) -> str:
        """切換校正狀態

        Args:
            index: 項目索引字符串

        Returns:
            新的狀態 ('correct' 或 'error')
        """
        if index in self.correction_states:
            # 切換狀態
            current_state = self.correction_states[index]
            # 在 correct 和 error 之間切換
            new_state = 'error' if current_state == 'correct' else 'correct'
            self.correction_states[index] = new_state

            # 如果有增強狀態管理器，記錄這個操作
            if self.enhanced_state_manager:
                self._save_toggle_operation(index, current_state, new_state)

            return new_state
        else:
            # 如果沒有現有狀態，但有原始文本和校正文本，則創建一個新的狀態
            if index in self.original_texts and index in self.corrected_texts:
                # 默認為 correct 狀態
                self.correction_states[index] = 'correct'
                return 'correct'

        # 如果沒有相關數據，返回空字符串表示無法切換
        return ''