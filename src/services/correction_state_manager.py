"""校正狀態管理器"""

import os
from typing import Dict, Optional, Tuple
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

class CorrectionStateManager:
    def __init__(self, tree):
        self.tree = tree
        self.correction_states = {}  # 記錄校正狀態
        self.original_texts = {}     # 原始文字
        self.corrected_texts = {}    # 校正後文字
        self.icons = {
            'correct': '✅',
            'error': '❌'
        }

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
            return new_state
        else:
            # 如果沒有現有狀態，但有原始文本和校正文本，則創建一個新的狀態
            if index in self.original_texts and index in self.corrected_texts:
                # 默認為 correct 狀態
                self.correction_states[index] = 'correct'
                return 'correct'

        # 如果沒有相關數據，返回空字符串表示無法切換
        return ''
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
                print(f"找不到 SRT Text 或 V/X 欄位: columns={columns}")
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
            print(f"校正狀態已切換: 索引={index}, 狀態={self.correction_states[index]}")

        except Exception as e:
            print(f"處理圖標點擊時出錯: {e}")
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