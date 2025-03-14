"""用戶界面事件處理模組"""

import logging
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Optional, Any, Callable, Dict, List, Tuple

from gui.custom_messagebox import show_info, show_warning, show_error, ask_question
from gui.text_edit_dialog import TextEditDialog


class UIEventHandler:
    """處理用戶界面事件的類別"""

    def __init__(self, parent):
        """
        初始化UI事件處理器

        Args:
            parent: 父級元件引用，即AlignmentGUI實例
        """
        self.parent = parent
        self.logger = logging.getLogger(self.__class__.__name__)
        self.last_mouse_x = 0
        self.last_mouse_y = 0

        # 時間滑桿相關變數
        self.time_slider = None
        self.slider_active = False
        self.slider_target = None
        self.slider_start_value = 0

        # 合併句子相關
        self.current_selected_items = []
        self.merge_symbol = None

        # 建立合併符號但不顯示
        self._create_merge_symbol()

    def _create_merge_symbol(self):
        """創建但不立即顯示合併符號"""
        self.merge_symbol = tk.Label(
            self.parent.tree,
            text="+",
            font=("Arial", 16, "bold"),
            bg="#4CAF50",
            fg="white",
            width=2,
            height=1,
            relief="raised"
        )
        # 綁定點擊事件
        self.merge_symbol.bind('<Button-1>', self.combine_sentences)

    def bind_all_events(self):
        """綁定所有事件"""
        # 綁定視窗關閉事件
        self.parent.master.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 綁定全域快捷鍵
        self.parent.master.bind_all('<Control-s>', lambda e: self.parent.save_srt())
        self.parent.master.bind_all('<Control-o>', lambda e: self.parent.load_srt())
        self.parent.master.bind_all('<Control-z>', lambda e: self.parent.undo())
        self.parent.master.bind_all('<Control-y>', lambda e: self.parent.redo())

        # 綁定 Treeview 特定事件
        self.parent.tree.bind('<Button-1>', self.on_tree_click)
        self.parent.tree.bind('<Double-1>', self._handle_double_click)
        self.parent.tree.bind("<<TreeviewSelect>>", self.on_treeview_select)

        # 滑鼠移動事件，用於更新合併符號位置
        self.parent.master.bind("<Motion>", self.remember_mouse_position)

    def remember_mouse_position(self, event):
        """記錄當前滑鼠位置"""
        self.last_mouse_x = event.x_root - self.parent.tree.winfo_rootx()
        self.last_mouse_y = event.y_root - self.parent.tree.winfo_rooty()

    def on_tree_click(self, event):
        """處理樹狀圖的點擊事件"""
        try:
            region = self.parent.tree.identify("region", event.x, event.y)
            column = self.parent.tree.identify_column(event.x)
            item = self.parent.tree.identify_row(event.y)

            if not (region and column and item):
                return

            # 獲取列名
            column_idx = int(column[1:]) - 1
            if column_idx >= len(self.parent.tree["columns"]):
                return

            column_name = self.parent.tree["columns"][column_idx]

            # 隱藏合併符號
            if hasattr(self, 'merge_symbol'):
                self.merge_symbol.place_forget()

            # 隱藏時間滑桿（如果有）
            self.hide_time_slider()

            # 處理時間欄位的點擊
            if column_name in ["Start", "End"] and region == "cell":
                self.show_time_slider(event, item, column, column_name)
                return

            # 獲取值
            values = list(self.parent.tree.item(item)["values"])
            if not values:
                return

            # 處理 Word Text 列點擊 - 切換使用 Word 文本
            if column_name == "Word Text" and self.parent.display_mode in [
                    self.parent.DISPLAY_MODE_SRT_WORD,
                    self.parent.DISPLAY_MODE_ALL
                ]:
                self._handle_word_text_click(item, values)
                return

            # 處理 V/X 列點擊
            if column_name == "V/X":
                self._handle_correction_click(item, values)
                return

            # 處理音頻播放列的點擊
            elif column_name == 'V.O' and self.parent.audio_imported:
                self._handle_audio_click(values)

        except Exception as e:
            self.logger.error(f"處理樹狀圖點擊事件時出錯: {e}", exc_info=True)

    def _handle_word_text_click(self, item, values):
        """處理 Word Text 列點擊"""
        # 檢查項目是否依然存在
        if not self.parent.tree.exists(item):
            return

        # 保存當前標籤和校正狀態，避免丟失
        current_tags = list(self.parent.tree.item(item, "tags") or tuple())

        # 識別校正狀態相關的標籤
        correction_tags = [tag for tag in current_tags if tag.startswith("correction_")]

        # 檢查當前是否已經使用 Word 文本
        using_word_text = "use_word_text" in current_tags

        # 切換狀態
        if using_word_text:
            # 如果已使用 Word 文本，則取消
            self.parent.use_word_text[item] = False
            if "use_word_text" in current_tags:
                current_tags.remove("use_word_text")

            # 如果文本不匹配，添加 mismatch 標籤
            if self.parent.display_mode == self.parent.DISPLAY_MODE_ALL:
                srt_text_idx = 4  # SRT Text 在 ALL 模式下的索引
                word_text_idx = 5  # Word Text 在 ALL 模式下的索引
            else:  # SRT_WORD 模式
                srt_text_idx = 3  # SRT Text 在 SRT_WORD 模式下的索引
                word_text_idx = 4  # Word Text 在 SRT_WORD 模式下的索引

            # 只有當兩個文本不同時才添加 mismatch 標籤
            if srt_text_idx < len(values) and word_text_idx < len(values):
                srt_text = values[srt_text_idx]
                word_text = values[word_text_idx]
                if srt_text != word_text and "mismatch" not in current_tags:
                    current_tags.append("mismatch")
        else:
            # 如果未使用 Word 文本，則開始使用
            self.parent.use_word_text[item] = True
            if "use_word_text" not in current_tags:
                current_tags.append("use_word_text")

            # 移除 mismatch 標籤
            if "mismatch" in current_tags:
                current_tags.remove("mismatch")

        # 確保校正標籤被保留
        for tag in correction_tags:
            if tag not in current_tags:
                current_tags.append(tag)

        # 更新標籤
        self.parent.tree.item(item, tags=tuple(current_tags))

        # 確保標籤樣式已設置
        self.parent.tree.tag_configure('use_word_text', background='#00BFFF')  # 淺藍色背景
        self.parent.tree.tag_configure('mismatch', background='#FFDDDD')  # 淺紅色背景

        # 保存當前狀態
        if hasattr(self.parent, 'state_manager'):
            self.parent.state_manager.save_state(self.parent.get_current_state())

    def _handle_correction_click(self, item, values):
        """處理校正標記點擊"""
        # 獲取當前項目的索引
        if self.parent.display_mode == self.parent.DISPLAY_MODE_ALL:
            display_index = str(values[1])
            text_index = 4
        elif self.parent.display_mode == self.parent.DISPLAY_MODE_AUDIO_SRT:
            display_index = str(values[1])
            text_index = 4
        elif self.parent.display_mode == self.parent.DISPLAY_MODE_SRT_WORD:
            display_index = str(values[0])
            text_index = 3
        else:  # SRT 模式
            display_index = str(values[0])
            text_index = 3

        # 先檢查最後一列的值是否為空，如果為空代表沒有校正需求
        correction_mark = values[-1]
        if correction_mark == "":
            # 該項目不含錯誤字，不響應點擊
            return

        # 檢查是否有校正狀態
        if display_index in self.parent.correction_state_manager.correction_states:
            current_state = self.parent.correction_state_manager.correction_states[display_index]
            original_text = self.parent.correction_state_manager.original_texts[display_index]
            corrected_text = self.parent.correction_state_manager.corrected_texts[display_index]

            # 切換狀態和文本
            if current_state == 'correct':
                self.parent.correction_state_manager.correction_states[display_index] = 'error'
                values[text_index] = original_text
                values[-1] = '❌'
            else:
                self.parent.correction_state_manager.correction_states[display_index] = 'correct'
                values[text_index] = corrected_text
                values[-1] = '✅'

            # 更新樹狀圖顯示
            self.parent.tree.item(item, values=tuple(values))

            # 保存當前狀態
            self.parent.state_manager.save_state(self.parent.get_current_state())

    def _handle_audio_click(self, values):
        """處理音頻播放點擊"""
        try:
            if self.parent.display_mode == self.parent.DISPLAY_MODE_ALL:
                index = int(values[1])
            elif self.parent.display_mode == self.parent.DISPLAY_MODE_AUDIO_SRT:
                index = int(values[1])
            else:
                index = int(values[0])

            self.parent.play_audio_segment(index)
        except (ValueError, IndexError) as e:
            self.logger.error(f"處理音頻播放時出錯: {e}")
            show_warning("警告", "無法播放音頻段落", self.parent.master)

    def on_treeview_select(self, event=None):
        """處理樹狀視圖選擇變化"""
        selected_items = self.parent.tree.selection()

        # 隱藏合併符號
        self.merge_symbol.place_forget()

        # 檢查是否選擇了至少兩個項目
        if len(selected_items) >= 2:
            # 使用最後記錄的滑鼠位置來放置合併符號
            if hasattr(self, 'last_mouse_x') and hasattr(self, 'last_mouse_y'):
                x = self.last_mouse_x + 15  # 游標右側 15 像素
                y = self.last_mouse_y

                # 確保符號在可視範圍內
                tree_width = self.parent.tree.winfo_width()
                tree_height = self.parent.tree.winfo_height()

                x = min(x, tree_width - 30)  # 避免超出右邊界
                y = min(y, tree_height - 30)  # 避免超出下邊界
                y = max(y, 10)  # 避免超出上邊界

                # 顯示合併符號
                self.merge_symbol.place(x=x, y=y)

                # 儲存目前選中的項目，用於之後的合併操作
                self.current_selected_items = selected_items
            else:
                # 如果沒有滑鼠位置記錄，退化為使用第一個選中項的位置
                item = selected_items[0]
                bbox = self.parent.tree.bbox(item)
                if bbox:
                    self.merge_symbol.place(x=bbox[0] + bbox[2] + 5, y=bbox[1])
                    # 儲存目前選中的項目
                    self.current_selected_items = selected_items
        else:
            # 如果選中項目少於2個，清除儲存的選中項
            self.current_selected_items = []

    def _handle_double_click(self, event):
        """處理雙擊事件，防止編輯 V/X 欄位"""
        region = self.parent.tree.identify("region", event.x, event.y)
        column = self.parent.tree.identify_column(event.x)

        # 如果點擊的是最後一列（Correction），則阻止編輯
        if column == f"#{len(self.parent.tree['columns'])}":
            return "break"

        # 其他列正常處理
        if region == "cell":
            self.on_double_click(event)

    def on_double_click(self, event):
        """處理雙擊編輯事件"""
        try:
            # 先獲取點擊的區域和列
            region = self.parent.tree.identify("region", event.x, event.y)
            if region != "cell":
                return

            # 獲取點擊的列
            column = self.parent.tree.identify_column(event.x)
            if not column:
                return

            # 獲取列索引
            column_idx = int(column[1:]) - 1
            column_name = self.parent.tree["columns"][column_idx]

            # 獲取選中的項目
            selected_items = self.parent.tree.selection()
            if not selected_items:
                return

            # 檢查項目是否依然存在
            item = selected_items[0]
            if not self.parent.tree.exists(item):
                return

            values = list(self.parent.tree.item(item, 'values'))
            if not values:
                return

            # 根據不同模式處理
            if self.parent.display_mode == self.parent.DISPLAY_MODE_ALL:
                self._handle_all_mode_edit(item, values, column_name, column_idx)
            elif self.parent.display_mode == self.parent.DISPLAY_MODE_SRT_WORD:
                self._handle_srt_word_mode_edit(item, values, column_name, column_idx)
            else:  # SRT 或 AUDIO_SRT 模式
                self._handle_standard_mode_edit(item, values, column_name, column_idx)

        except Exception as e:
            self.logger.error(f"處理雙擊事件時出錯: {e}", exc_info=True)
            show_error("錯誤", f"編輯文本失敗: {str(e)}", self.parent.master)

        finally:
            # 確保焦點回到主視窗
            self.parent.master.focus_force()

    def _handle_all_mode_edit(self, item, values, column_name, column_idx):
        """處理ALL模式的編輯"""
        srt_index = int(values[1])
        start_time = values[2]
        end_time = values[3]

        # 根據點擊的列決定編輯哪個文本
        if column_name == "SRT Text":
            edit_text = values[4]
            self._show_edit_dialog("編輯 SRT 文本", edit_text, start_time, end_time,
                                 column_idx, srt_index, item, 'srt')
        elif column_name == "Word Text":
            edit_text = values[5]
            self._show_edit_dialog("編輯 Word 文本", edit_text, start_time, end_time,
                                 column_idx, srt_index, item, 'word')

    def _handle_srt_word_mode_edit(self, item, values, column_name, column_idx):
        """處理SRT_WORD模式的編輯"""
        srt_index = int(values[0])
        start_time = values[1]
        end_time = values[2]

        # 根據點擊的列決定編輯哪個文本
        if column_name == "SRT Text":
            edit_text = values[3]
            self._show_edit_dialog("編輯 SRT 文本", edit_text, start_time, end_time,
                                 column_idx, srt_index, item, 'srt')
        elif column_name == "Word Text":
            edit_text = values[4]
            self._show_edit_dialog("編輯 Word 文本", edit_text, start_time, end_time,
                                 column_idx, srt_index, item, 'word')

    def _handle_standard_mode_edit(self, item, values, column_name, column_idx):
        """處理SRT或AUDIO_SRT模式的編輯"""
        if self.parent.display_mode == self.parent.DISPLAY_MODE_AUDIO_SRT:
            current_index = int(values[1])
            start_time = values[2]
            end_time = values[3]
            initial_text = values[4]
        else:  # SRT 模式
            current_index = int(values[0])
            start_time = values[1]
            end_time = values[2]
            initial_text = values[3]

        self._show_edit_dialog("編輯文本", initial_text, start_time, end_time,
                            column_idx, current_index, item, 'srt')

    def _show_edit_dialog(self, title, text, start_time, end_time, column_idx,
                       srt_index, item, edit_mode):
        """顯示編輯對話框並處理結果"""
        dialog = TextEditDialog(
            parent=self.parent.master,
            title=title,
            initial_text=text,
            start_time=start_time,
            end_time=end_time,
            column_index=column_idx,
            display_mode=self.parent.display_mode,
            edit_mode=edit_mode
        )

        # 處理編輯結果
        if dialog.result:
            if edit_mode == 'srt':
                self.parent.process_srt_edit_result(dialog.result, item, srt_index,
                                               start_time, end_time)
            else:  # word
                self.parent.process_word_edit_result(dialog.result, item, srt_index)

    def show_time_slider(self, event, item, column, column_name):
        """顯示時間調整滑桿"""
        # 獲取單元格的位置和大小
        bbox = self.parent.tree.bbox(item, column)
        if not bbox:
            return

        x, y, width, height = bbox

        # 獲取當前值和相關項目
        values = self.parent.tree.item(item, "values")

        # 獲取樹狀視圖中的所有項目
        all_items = self.parent.tree.get_children()
        item_index = all_items.index(item)

        # 根據不同模式確定索引、開始時間和結束時間的位置
        if self.parent.display_mode in [
                self.parent.DISPLAY_MODE_ALL,
                self.parent.DISPLAY_MODE_AUDIO_SRT
            ]:
            index_pos = 1
            start_pos = 2
            end_pos = 3
        else:  # SRT 或 SRT_WORD 模式
            index_pos = 0
            start_pos = 1
            end_pos = 2

        # 創建滑桿控件
        self.create_time_slider(
            x, y, width, height,
            item, column_name,
            values, item_index, all_items,
            index_pos, start_pos, end_pos
        )

    def create_time_slider(self, x, y, width, height, item, column_name, values,
                        item_index, all_items, index_pos, start_pos, end_pos):
        """創建時間調整滑桿"""
        # 創建滑桿框架
        slider_frame = tk.Frame(self.parent.tree, bg="lightgray", bd=1, relief="raised")
        slider_frame.place(x=x + width, y=y, width=150, height=height)

        # 獲取當前時間值
        current_time_str = values[start_pos if column_name == "Start" else end_pos]
        current_time = self.parent.parse_time(current_time_str)

        # 計算滑桿範圍
        if column_name == "Start":
            min_value = 0
            max_value = self.parent.time_to_seconds(
                            self.parent.parse_time(values[end_pos])) * 1000

            # 如果有上一行，則最小值是上一行的結束時間
            if item_index > 0:
                prev_item = all_items[item_index - 1]
                prev_values = self.parent.tree.item(prev_item, "values")
                prev_end_time = self.parent.parse_time(prev_values[end_pos])
                min_value = self.parent.time_to_milliseconds(prev_end_time)
        else:  # End 欄位
            min_value = self.parent.time_to_milliseconds(
                            self.parent.parse_time(values[start_pos]))
            max_value = min_value + 10000  # 增加10秒

            # 如果有下一行，則最大值是下一行的開始時間
            if item_index < len(all_items) - 1:
                next_item = all_items[item_index + 1]
                next_values = self.parent.tree.item(next_item, "values")
                next_start_time = self.parent.parse_time(next_values[start_pos])
                max_value = self.parent.time_to_milliseconds(next_start_time)

        # 當前值
        current_value = self.parent.time_to_milliseconds(current_time)

        # 創建滑桿
        self.slider_active = True
        self.slider_target = {
            "item": item,
            "column": column_name,
            "index": values[index_pos],
            "item_index": item_index,
            "all_items": all_items,
            "index_pos": index_pos,
            "start_pos": start_pos,
            "end_pos": end_pos
        }
        self.slider_start_value = current_value

        # 創建滑桿和確認按鈕
        self.time_slider = ttk.Scale(
            slider_frame,
            from_=min_value,
            to=max_value,
            orient=tk.HORIZONTAL,
            value=current_value,
            command=self.on_slider_change
        )
        self.time_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # 綁定事件，點擊其他區域時隱藏滑桿
        self.parent.master.bind("<Button-1>", self.check_slider_focus)

    def on_slider_change(self, value):
        """滑桿值變化時更新時間顯示"""
        if not self.slider_active or not self.slider_target:
            return

        # 獲取新的時間值（毫秒）
        new_value = float(value)

        # 將毫秒轉換為 SubRipTime 對象
        new_time = self.parent.milliseconds_to_time(new_value)

        # 更新樹狀視圖中的顯示
        item = self.slider_target["item"]
        column_name = self.slider_target["column"]
        values = list(self.parent.tree.item(item, "values"))

        # 更新相應的值
        if column_name == "Start":
            values[self.slider_target["start_pos"]] = str(new_time)

            # 如果有上一行，同時更新上一行的結束時間
            item_index = self.slider_target["item_index"]
            if item_index > 0:
                prev_item = self.slider_target["all_items"][item_index - 1]
                prev_values = list(self.parent.tree.item(prev_item, "values"))
                prev_values[self.slider_target["end_pos"]] = str(new_time)
                self.parent.tree.item(prev_item, values=tuple(prev_values))
        else:  # End 欄位
            values[self.slider_target["end_pos"]] = str(new_time)

            # 如果有下一行，同時更新下一行的開始時間
            item_index = self.slider_target["item_index"]
            if item_index < len(self.slider_target["all_items"]) - 1:
                next_item = self.slider_target["all_items"][item_index + 1]
                next_values = list(self.parent.tree.item(next_item, "values"))
                next_values[self.slider_target["start_pos"]] = str(new_time)
                self.parent.tree.item(next_item, values=tuple(next_values))

        # 更新當前項目的值
        self.parent.tree.item(item, values=tuple(values))

    def apply_time_change(self):
        """應用時間變更並隱藏滑桿"""
        if not self.slider_active:
            return

        # 保存當前校正狀態
        correction_states = {}
        for index, state in self.parent.correction_state_manager.correction_states.items():
            correction_states[index] = {
                'state': state,
                'original': self.parent.correction_state_manager.original_texts.get(index, ''),
                'corrected': self.parent.correction_state_manager.corrected_texts.get(index, '')
            }

        # 更新 SRT 數據以反映變更
        self.parent.update_srt_data_from_treeview()

        # 恢復校正狀態
        for index, data in correction_states.items():
            self.parent.correction_state_manager.correction_states[index] = data['state']
            self.parent.correction_state_manager.original_texts[index] = data['original']
            self.parent.correction_state_manager.corrected_texts[index] = data['corrected']

        # 如果有音頻，更新音頻段落
        if self.parent.audio_imported and hasattr(self.parent, 'audio_player'):
            self.parent.audio_player.segment_audio(self.parent.srt_data)

        # 保存狀態
        self.parent.state_manager.save_state(self.parent.get_current_state(), {
            'type': 'time_adjust',
            'description': '調整時間軸'
        })

        # 隱藏滑桿
        self.hide_time_slider()

    def check_slider_focus(self, event):
        """檢查點擊是否在滑桿外部，如果是則隱藏滑桿"""
        if not self.slider_active or not self.time_slider:
            return

        # 獲取滑桿的位置
        slider_x = self.time_slider.winfo_rootx()
        slider_y = self.time_slider.winfo_rooty()
        slider_width = self.time_slider.winfo_width()
        slider_height = self.time_slider.winfo_height()

        # 檢查點擊是否在滑桿區域外
        if (event.x_root < slider_x or event.x_root > slider_x + slider_width or
            event.y_root < slider_y or event.y_root > slider_y + slider_height):
            # 應用變更並隱藏滑桿
            self.apply_time_change()

    def hide_time_slider(self):
        """隱藏時間調整滑桿"""
        if hasattr(self, 'time_slider') and self.time_slider:
            # 獲取滑桿的父框架
            parent = self.time_slider.master
            parent.place_forget()
            parent.destroy()
            self.time_slider = None

        self.slider_active = False
        self.slider_target = None

        # 解除綁定
        try:
            self.parent.master.unbind("<Button-1>")
        except:
            pass

    def combine_sentences(self, event=None):
        """合併字幕"""
        try:
            # 檢查是否有儲存的選中項
            if not hasattr(self, 'current_selected_items') or len(self.current_selected_items) < 2:
                show_warning("警告", "請選擇至少兩個字幕項目", self.parent.master)
                return

            # 保存操作前的狀態供撤銷使用
            original_state = self.parent.get_current_state()
            self.logger.debug(f"合併前狀態包含 {len(original_state)} 項目")

            try:
                # 使用所有選中的項目進行合併
                selected_items = self.current_selected_items

                # 根據索引排序項目
                sorted_items = sorted(selected_items, key=self.parent.tree.index)

                # 第一個項目作為基礎
                base_item = sorted_items[0]
                base_values = list(self.parent.tree.item(base_item, 'values'))
                base_tags = self.parent.tree.item(base_item, 'tags')

                # 根據顯示模式確定正確的列索引
                if self.parent.display_mode == self.parent.DISPLAY_MODE_SRT:
                    # [Index, Start, End, SRT Text, V/X]
                    index_index = 0
                    start_index = 1
                    end_index = 2
                    text_index = 3
                    vx_index = 4
                    vo_index = None
                    word_text_index = None
                    match_index = None
                elif self.parent.display_mode == self.parent.DISPLAY_MODE_SRT_WORD:
                    # [Index, Start, End, SRT Text, Word Text, Match, V/X]
                    index_index = 0
                    start_index = 1
                    end_index = 2
                    text_index = 3
                    word_text_index = 4
                    match_index = 5
                    vx_index = 6
                    vo_index = None
                elif self.parent.display_mode == self.parent.DISPLAY_MODE_AUDIO_SRT:
                    # [V.O, Index, Start, End, SRT Text, V/X]
                    vo_index = 0
                    index_index = 1
                    start_index = 2
                    end_index = 3
                    text_index = 4
                    vx_index = 5
                    word_text_index = None
                    match_index = None
                else:  # self.parent.DISPLAY_MODE_ALL
                    # [V.O, Index, Start, End, SRT Text, Word Text, Match, V/X]
                    vo_index = 0
                    index_index = 1
                    start_index = 2
                    end_index = 3
                    text_index = 4
                    word_text_index = 5
                    match_index = 6
                    vx_index = 7

                # 收集所有項目的校正狀態信息
                correction_items = []
                original_texts = []
                corrected_texts = []
                has_any_uncorrected = False  # 標記是否有任何一個項目處於未校正狀態

                for item in sorted_items:
                    item_values = self.parent.tree.item(item, 'values')
                    if len(item_values) <= index_index:
                        continue  # 跳過無效的數據

                    item_index = str(item_values[index_index])

                    # 檢查項目是否有校正狀態
                    if item_index in self.parent.correction_state_manager.correction_states:
                        state = self.parent.correction_state_manager.correction_states[item_index]
                        original = self.parent.correction_state_manager.original_texts.get(item_index, '')
                        corrected = self.parent.correction_state_manager.corrected_texts.get(item_index, '')

                        # 只標記未校正狀態
                        if state == 'error':
                            has_any_uncorrected = True

                        correction_items.append({
                            'index': item_index,
                            'state': state,
                            'original': original,
                            'corrected': corrected
                        })

                        # 收集原始文本和校正文本
                        if original:
                            original_texts.append(original)
                        if corrected:
                            corrected_texts.append(corrected)

                # 載入校正數據庫
                corrections = self.parent.load_corrections()

                # 合併文本
                combined_text = base_values[text_index] if text_index < len(base_values) else ""
                combined_word_text = ""
                combined_match = ""

                # 初始化 Word 文本和 Match 相關變數
                if word_text_index is not None and word_text_index < len(base_values):
                    combined_word_text = base_values[word_text_index]
                if match_index is not None and match_index < len(base_values):
                    combined_match = base_values[match_index]

                # 使用最後一個項目的結束時間
                last_item_values = self.parent.tree.item(sorted_items[-1], 'values')
                if end_index < len(last_item_values):
                    end_time = last_item_values[end_index]
                else:
                    # 如果找不到結束時間，使用基礎項目的結束時間
                    end_time = base_values[end_index] if end_index < len(base_values) else ""

                # 合併所有選中項的文本
                for item in sorted_items[1:]:
                    item_values = self.parent.tree.item(item, 'values')
                    # 合併文本
                    if text_index < len(item_values) and item_values[text_index].strip():  # 只有當文本不為空白時才合併
                        combined_text += f" {item_values[text_index]}"

                    # 合併 Word 文本 (如果存在)
                    if word_text_index is not None and word_text_index < len(item_values) and item_values[word_text_index].strip():
                        combined_word_text += f" {item_values[word_text_index]}"

                    # 合併 Match 狀態 (如果存在)
                    if match_index is not None and match_index < len(item_values):
                        current_match = item_values[match_index]
                        if current_match and combined_match:
                            combined_match += f" | {current_match}"
                        elif current_match:
                            combined_match = current_match

                # 檢查合併後的文本是否需要校正
                needs_correction = False
                for error_word, correction_word in corrections.items():
                    if error_word in combined_text:
                        needs_correction = True
                        break

                # 新的值設置部分
                new_values = list(base_values)
                new_values[end_index] = end_time  # 使用最後一項的結束時間
                new_values[text_index] = combined_text  # 合併後的文本

                # 處理特定欄位
                if vo_index is not None:
                    new_values[vo_index] = self.parent.PLAY_ICON  # 確保播放圖標存在

                if word_text_index is not None:
                    new_values[word_text_index] = combined_word_text  # 合併後的 Word 文本

                if match_index is not None:
                    new_values[match_index] = combined_match  # 合併後的比對狀態

                # 初始化校正狀態圖標為空
                new_values[vx_index] = ''

                # 檢查是否有任一項使用 Word 文本
                use_word_text = False
                for item in sorted_items:
                    if self.parent.use_word_text.get(item, False):
                        use_word_text = True
                        break

                # 刪除所有原始項目
                insert_position = self.parent.tree.index(sorted_items[0])
                for item in sorted_items:
                    self.parent.tree.delete(item)

                # 插入新合併項目
                new_item = self.parent.tree_manager.insert_item('', insert_position, values=tuple(new_values))

                # 確保 new_item_index 被定義
                if self.parent.display_mode in [self.parent.DISPLAY_MODE_ALL, self.parent.DISPLAY_MODE_AUDIO_SRT]:
                    new_item_index = str(new_values[1])
                else:
                    new_item_index = str(new_values[0])

                # 設置標籤
                if base_tags:
                    self.parent.tree.item(new_item, tags=base_tags)

                # 設置 use_word_text 狀態
                if use_word_text:
                    self.parent.use_word_text[new_item] = True
                    current_tags = list(self.parent.tree.item(new_item, "tags") or ())
                    if "use_word_text" not in current_tags:
                        current_tags.append("use_word_text")
                    if "mismatch" in current_tags:
                        current_tags.remove("mismatch")
                    self.parent.tree.item(new_item, tags=tuple(current_tags))

                # 保存校正狀態處理
                if needs_correction or has_any_uncorrected:
                    # 準備校正後的文本
                    corrected_text = combined_text
                    for error_word, correction_word in corrections.items():
                        corrected_text = corrected_text.replace(error_word, correction_word)

                    # 只有在有未校正的項目時才顯示圖標
                    if has_any_uncorrected:
                        # 更新顯示的圖標為未校正狀態
                        new_values_list = list(new_values)
                        new_values_list[vx_index] = '❌'  # 顯示未校正圖標
                        self.parent.tree.item(new_item, values=tuple(new_values_list))

                        # 保存校正狀態為未校正
                        self.parent.correction_state_manager.add_correction_state(
                            new_item_index,
                            combined_text,  # 原始文本
                            corrected_text,  # 校正後文本
                            'error'  # 未校正狀態
                        )
                    else:
                        # 已校正狀態 - 不顯示圖標，也不保存校正狀態
                        # 什麼都不做，保持 vx_index 位置為空字串
                        pass

                # 更新項目編號
                self.parent.renumber_items()

                # 更新 SRT 數據
                self.parent.update_srt_data_from_treeview()

                # 如果有音頻，處理音頻段落
                if self.parent.audio_imported and hasattr(self.parent, 'audio_player'):
                    # 更新音頻段落
                    self.parent.audio_player.segment_audio(self.parent.srt_data)
                    self.logger.info(f"已重新分割全部音頻段落，確保與 SRT 同步")

                # 保存操作後的狀態
                current_state = self.parent.get_current_state()

                # 保存狀態，包含完整的操作信息
                operation_info = {
                    'type': 'combine_sentences',
                    'description': '合併字幕',
                    'original_state': original_state,
                    'items': [item for item in sorted_items],
                    'is_first_operation': len(self.parent.state_manager.states) <= 1
                }

                self.logger.debug(f"正在保存合併操作狀態: 原狀態項數={len(original_state)}, 新狀態項數={len(current_state)}")
                self.parent.state_manager.save_state(current_state, operation_info)

                # 選中新合併的項目
                self.parent.tree.selection_set(new_item)
                self.parent.tree.see(new_item)

                # 隱藏合併符號
                if hasattr(self, 'merge_symbol'):
                    self.merge_symbol.place_forget()

                self.parent.update_status("已合併所選字幕")

            except Exception as e:
                self.logger.error(f"合併字幕時出錯: {e}", exc_info=True)
                show_error("錯誤", f"合併字幕失敗: {str(e)}", self.parent.master)

        except Exception as e:
            self.logger.error(f"合併字幕時出錯: {e}", exc_info=True)
            show_error("錯誤", f"合併字幕失敗: {str(e)}", self.parent.master)

    def on_closing(self):
        """處理視窗關閉事件"""
        try:
            # 先清理所有子視窗
            for widget in self.parent.master.winfo_children():
                if isinstance(widget, tk.Toplevel):
                    widget.destroy()

            # 停止音頻播放
            if hasattr(self.parent, 'audio_player'):
                self.parent.audio_player.cleanup()

            # 保存當前狀態
            if hasattr(self.parent, 'state_manager'):
                self.parent.state_manager.save_state(self.parent.get_current_state())

            # 執行清理
            self.parent.cleanup()

            # 確保處理完所有待處理的事件
            self.parent.master.update_idletasks()

            # 關閉主視窗
            self.parent.master.destroy()
            import sys
            sys.exit(0)
        except Exception as e:
            self.logger.error(f"關閉視窗時出錯: {e}")
            self.parent.master.destroy()
            import sys
            sys.exit(1)

    def clean_resources(self):
        """清理資源"""
        try:
            # 隱藏合併符號
            if hasattr(self, 'merge_symbol'):
                self.merge_symbol.place_forget()

            # 清理滑桿
            self.hide_time_slider()

        except Exception as e:
            self.logger.error(f"清理 UI 資源時出錯: {e}")