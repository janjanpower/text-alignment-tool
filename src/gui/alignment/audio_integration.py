"""音頻集成模組"""

import os
import logging
import tkinter as tk
from tkinter import filedialog

import pysrt
from audio.audio_player import AudioPlayer
from gui.custom_messagebox import show_info, show_warning, show_error
from utils.text_utils import simplify_to_traditional

class AudioIntegration:
    """處理音頻相關功能的集成"""

    def __init__(self, parent):
        """
        初始化音頻集成
        :param parent: 父物件 (AlignmentGUI 實例)
        """
        self.parent = parent
        self.logger = logging.getLogger(self.__class__.__name__)

        # 初始化音頻播放器
        self.initialize_audio_player()

    def initialize_audio_player(self):
        """初始化音頻播放器"""
        self.parent.audio_player = AudioPlayer(self.parent.main_frame)
        self.parent.master.bind("<<AudioLoaded>>", self.handle_audio_loaded)

    def handle_audio_loaded(self, event=None):
        """處理音頻載入事件"""
        try:
            if not self.parent.audio_imported:  # 避免重複處理
                self.parent.audio_imported = True
                self.parent.audio_file_path = self.parent.audio_player.audio_file

                # 保存當前數據狀態
                old_mode = self.parent.display_mode
                self.logger.info(f"音頻已載入，匯入前顯示模式: {old_mode}")

                # 保存當前樹視圖數據
                current_data = []
                for item in self.parent.tree.get_children():
                    values = self.parent.tree.item(item, 'values')
                    tags = self.parent.tree.item(item, 'tags')
                    use_word = self.parent.use_word_text.get(item, False)

                    # 獲取索引位置
                    index_pos = 1 if old_mode in [self.parent.DISPLAY_MODE_ALL, self.parent.DISPLAY_MODE_AUDIO_SRT] else 0

                    if values and len(values) > index_pos:
                        index = str(values[index_pos])
                        # 檢查是否有校正狀態
                        correction_info = None
                        if index in self.parent.correction_state_manager.correction_states:
                            correction_info = {
                                'state': self.parent.correction_state_manager.correction_states[index],
                                'original': self.parent.correction_state_manager.original_texts.get(index, ''),
                                'corrected': self.parent.correction_state_manager.corrected_texts.get(index, '')
                            }

                    current_data.append({
                        'values': values,
                        'tags': tags,
                        'use_word': use_word,
                        'correction': correction_info
                    })

                # 先清空當前樹狀視圖
                for item in self.parent.tree.get_children():
                    self.parent.tree.delete(item)

                # 更新顯示模式
                self.parent.update_display_mode()

                # 更新文件信息
                self.parent.update_file_info()

                # 如果有 SRT 數據，更新音頻段落
                if hasattr(self.parent, 'srt_data') and self.parent.srt_data:
                    self.parent.audio_player.segment_audio(self.parent.srt_data)
                    self.logger.info("已根據 SRT 數據分割音頻段落")

                # 重要：根據舊數據重新填充樹狀視圖
                new_mode = self.parent.display_mode
                for item_data in current_data:
                    values = item_data['values']
                    # 轉換值以適應新的顯示模式
                    adjusted_values = self.parent.state_handling.adjust_values_for_mode(values, old_mode, new_mode)

                    # 插入到樹狀視圖
                    new_item = self.parent.tree_manager.insert_item('', 'end', values=tuple(adjusted_values))

                    # 恢復標籤
                    if item_data['tags']:
                        self.parent.tree.item(new_item, tags=item_data['tags'])

                    # 恢復 use_word_text 狀態
                    if item_data['use_word']:
                        self.parent.use_word_text[new_item] = True

                    # 恢復校正狀態
                    if 'correction' in item_data and item_data['correction']:
                        correction = item_data['correction']

                        # 獲取新的索引位置
                        index_pos = 1 if new_mode in [self.parent.DISPLAY_MODE_ALL, self.parent.DISPLAY_MODE_AUDIO_SRT] else 0
                        if len(adjusted_values) > index_pos:
                            new_index = str(adjusted_values[index_pos])

                            # 恢復校正狀態
                            self.parent.correction_state_manager.correction_states[new_index] = correction['state']
                            self.parent.correction_state_manager.original_texts[new_index] = correction['original']
                            self.parent.correction_state_manager.corrected_texts[new_index] = correction['corrected']

                # 如果已加載 Word 文檔，檢查是否需要執行自動比對
                if self.parent.word_imported and hasattr(self.parent, 'word_processor'):
                    # 檢查是否需要重新執行比對
                    if old_mode != self.parent.display_mode:
                        self.logger.info("顯示模式已變更，正在重新執行 Word 比對")
                        self.parent.compare_word_with_srt()
                    else:
                        self.logger.info("顯示模式未變更，保持現有 Word 比對結果")

                # 通知使用者（如果尚未顯示過通知）
                if not self.parent.audio_notification_shown:
                    show_info("成功", f"已成功載入音頻檔案：\n{os.path.basename(self.parent.audio_file_path)}", self.parent.master)
                    self.parent.audio_notification_shown = True

        except Exception as e:
            self.logger.error(f"處理音頻載入事件時出錯: {e}")
            show_error("錯誤", f"處理音頻載入失敗: {str(e)}", self.parent.master)

    def load_srt(self, event=None, file_path=None):
        """載入 SRT 文件"""
        try:
            if file_path is None:
                file_path = filedialog.askopenfilename(
                    filetypes=[("SRT files", "*.srt")],
                    parent=self.parent.master
                )

            if not file_path:
                return

            # 清除當前數據
            self.parent.clear_current_data()
            self.parent.srt_file_path = file_path

            # 載入 SRT 數據
            try:
                srt_data = pysrt.open(file_path, encoding='utf-8')
                if not srt_data:
                    raise ValueError("SRT文件為空或格式無效")
                self.parent.srt_data = srt_data
            except Exception as e:
                show_error("錯誤", f"讀取 SRT 檔案失敗: {str(e)}", self.parent.master)
                return

            # 設置 SRT 已匯入標誌
            self.parent.srt_imported = True

            # 更新顯示模式
            self.parent.update_display_mode()

            # 載入校正數據庫
            corrections = self.parent.correction_handler.load_corrections()

            # 處理每個字幕項目
            self.process_srt_entries(srt_data, corrections)

            # 更新界面和音頻
            self.parent.update_file_info()

            # 如果有音頻檔案，更新音頻段落
            if self.parent.audio_imported and hasattr(self.parent, 'audio_player'):
                self.parent.audio_player.segment_audio(self.parent.srt_data)

            # 如果有 Word 檔案，執行比對
            if self.parent.word_imported and hasattr(self.parent, 'word_processor'):
                self.parent.compare_word_with_srt()

            # 重要：在載入完成後立即保存初始狀態
            if hasattr(self.parent, 'state_manager'):
                self.parent.state_manager.save_state(self.parent.state_handling.get_current_state(), {
                    'type': 'load_srt',
                    'description': f'Loaded SRT file: {os.path.basename(file_path)}'
                })
                self.logger.info(f"已保存 SRT 載入後的初始狀態")

            show_info("成功", f"已成功載入SRT檔案：\n{os.path.basename(self.parent.srt_file_path)}", self.parent.master)

            return True

        except Exception as e:
            self.logger.error(f"載入 SRT 檔案時出錯: {e}", exc_info=True)
            show_error("錯誤", f"無法載入 SRT 檔案: {str(e)}", self.parent.master)
            return False

    def process_srt_entries(self, srt_data, corrections):
        """處理 SRT 條目"""
        for sub in srt_data:
            # 轉換文本為繁體中文
            text = simplify_to_traditional(sub.text.strip())

            # 檢查校正需求
            corrected_text = self.parent.correction_handler.correct_text(text, corrections)
            needs_correction = corrected_text != text

            # 準備值
            values = [
                str(sub.index),
                str(sub.start),
                str(sub.end),
                corrected_text if needs_correction else text,
                '✅' if needs_correction else ''
            ]

            # 如果已經有音頻，在開頭加入播放圖標
            if self.parent.audio_imported:
                values.insert(0, self.parent.PLAY_ICON)

            # 插入到樹狀視圖
            self.parent.tree_manager.insert_item('', 'end', values=tuple(values))

            # 如果需要校正，保存校正狀態
            if needs_correction:
                self.parent.correction_state_manager.add_correction_state(
                    str(sub.index),
                    text,
                    corrected_text,
                    'correct'
                )

    def import_audio(self):
        """匯入音頻檔案"""
        try:
            # 檢查是否已匯入 SRT
            if not self.parent.srt_imported:
                show_warning("警告", "請先匯入 SRT 文件", self.parent.master)
                return

            if not hasattr(self.parent, 'audio_player'):
                self.initialize_audio_player()

            file_path = filedialog.askopenfilename(
                filetypes=[("Audio files", "*.mp3 *.wav")],
                parent=self.parent.master
            )

            if not file_path:
                return

            # 保存當前狀態以便後續參考或恢復
            old_mode = self.parent.display_mode
            self.logger.info(f"即將匯入音頻檔案，匯入前顯示模式: {old_mode}")

            # 保存當前樹狀視圖的狀態（如需要）
            current_state = None
            if old_mode != self.parent.DISPLAY_MODE_SRT and old_mode != self.parent.DISPLAY_MODE_AUDIO_SRT:
                current_state = self.parent.state_handling.get_current_state()

            # 載入音頻文件
            if self.parent.audio_player.load_audio(file_path):
                self.parent.audio_imported = True
                self.parent.audio_file_path = file_path
                self.logger.info(f"成功載入音頻檔案: {file_path}")

                # 更新顯示模式
                self.parent.update_display_mode()

                # 檢查顯示模式是否已正確更新
                new_mode = self.parent.display_mode
                if new_mode != old_mode:
                    self.logger.info(f"顯示模式已更新: {old_mode} -> {new_mode}")

                # 如果有 SRT 數據，更新音頻段落
                if hasattr(self.parent, 'srt_data') and self.parent.srt_data:
                    self.parent.audio_player.segment_audio(self.parent.srt_data)
                    self.logger.info("已根據 SRT 數據分割音頻段落")

                # 更新文件信息和界面
                self.parent.update_file_info()

                # 通知使用者
                if not self.parent.audio_notification_shown:
                    show_info("成功", f"已成功載入音頻檔案：\n{os.path.basename(file_path)}", self.parent.master)
                    self.parent.audio_notification_shown = True

                return True

            else:
                show_error("錯誤", "無法載入音頻檔案", self.parent.master)
                return False

        except Exception as e:
            self.logger.error(f"匯入音頻文件時出錯: {e}", exc_info=True)
            show_error("錯誤", f"無法匯入音頻文件: {str(e)}", self.parent.master)
            return False

    def play_audio_segment(self, index):
        """播放指定的音頻段落"""
        try:
            if not self.parent.audio_imported or not hasattr(self.parent, 'audio_player'):
                show_warning("警告", "未加載音頻或播放器未初始化", self.parent.master)
                return

            # 檢查音頻段落是否存在
            if not hasattr(self.parent.audio_player.segment_manager, 'audio_segments') or not self.parent.audio_player.segment_manager.audio_segments:
                self.logger.warning("音頻段落為空")

                # 如果音頻段落為空，嘗試重新分段
                if hasattr(self.parent, 'srt_data') and self.parent.srt_data:
                    self.logger.info("嘗試重新分割音頻段落...")
                    self.parent.audio_player.segment_audio(self.parent.srt_data)

                    # 再次檢查分割是否成功
                    if not self.parent.audio_player.segment_manager.audio_segments:
                        # 如果仍然為空，設置一個預設段落
                        if self.parent.audio_player.audio:
                            self.logger.info("分割失敗，設置預設段落")
                            self.parent.audio_player.segment_manager.audio_segments[index] = self.parent.audio_player.audio
                        else:
                            show_warning("警告", "無法播放音頻：音頻段落創建失敗", self.parent.master)
                            return
                else:
                    show_warning("警告", "無法獲取字幕數據", self.parent.master)
                    return

            # 獲取項目的文本
            item = None
            for child in self.parent.tree.get_children():
                if self.parent.display_mode == self.parent.DISPLAY_MODE_ALL or self.parent.display_mode == self.parent.DISPLAY_MODE_AUDIO_SRT:
                    if int(self.parent.tree.item(child, 'values')[1]) == index:
                        item = child
                        break
                else:
                    if int(self.parent.tree.item(child, 'values')[0]) == index:
                        item = child
                        break

            if not item:
                self.logger.warning(f"找不到索引為 {index} 的項目")
                # 嘗試找到最接近的索引
                valid_indices = list(self.parent.audio_player.segment_manager.audio_segments.keys())
                if valid_indices:
                    closest_index = min(valid_indices, key=lambda x: abs(x - index))
                    self.logger.info(f"使用最接近的索引 {closest_index}")
                    self.parent.audio_player.play_segment(closest_index)
                else:
                    show_warning("警告", f"找不到索引為 {index} 的音頻段落", self.parent.master)
                return

            # 播放音頻段落
            self.parent.audio_player.play_segment(index)

            return True

        except Exception as e:
            self.logger.error(f"播放音頻段落時出錯: {e}")
            show_error("錯誤", f"播放音頻段落失敗: {str(e)}", self.parent.master)
            return False