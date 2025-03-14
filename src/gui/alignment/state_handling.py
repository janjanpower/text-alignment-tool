"""狀態處理模組"""

import os
import logging
import tkinter as tk
from tkinter import filedialog

import pysrt
from gui.custom_messagebox import show_info, show_warning, show_error, ask_question

class StateHandling:
    """處理狀態管理、保存和載入等操作"""

    def __init__(self, parent):
        """
        初始化狀態處理器
        :param parent: 父物件 (AlignmentGUI 實例)
        """
        self.parent = parent
        self.logger = logging.getLogger(self.__class__.__name__)

    def save_srt(self, event=None):
        """
        儲存 SRT 文件
        :param event: 事件對象（可選）
        :return: 是否成功儲存
        """
        if not self.parent.srt_file_path:
            return self.save_srt_as()

        try:
            self.save_srt_file(self.parent.srt_file_path)
            self.parent.update_status(f"已儲存文件：{os.path.basename(self.parent.srt_file_path)}")
            return True
        except Exception as e:
            self.logger.error(f"儲存 SRT 檔案時出錯: {e}", exc_info=True)
            show_error("錯誤", f"儲存檔案失敗: {str(e)}", self.parent.master)
            return False

    def save_srt_as(self):
        """
        另存新檔
        :return: 是否成功儲存
        """
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".srt",
                filetypes=[("SRT files", "*.srt")],
                parent=self.parent.master
            )

            if not file_path:
                return False

            self.save_srt_file(file_path)
            self.parent.srt_file_path = file_path
            self.parent.config.add_recent_file(file_path)
            self.parent.update_status(f"已另存新檔：{os.path.basename(file_path)}")
            return True

        except Exception as e:
            self.logger.error(f"另存新檔時出錯: {e}", exc_info=True)
            show_error("錯誤", f"另存新檔失敗: {str(e)}", self.parent.master)
            return False

    def save_srt_file(self, file_path):
        """
        保存 SRT 文件
        :param file_path: 文件路徑
        """
        try:
            # 創建新的 SRT 文件
            new_srt = pysrt.SubRipFile()

            # 載入校正資料庫
            corrections = self.parent.correction_handler.load_corrections()

            # 遍歷所有項目
            for item in self.parent.tree.get_children():
                values = self.parent.tree.item(item)['values']

                # 檢查是否使用 Word 文本
                use_word = self.parent.use_word_text.get(item, False)

                # 根據顯示模式解析值
                if self.parent.display_mode == self.parent.DISPLAY_MODE_AUDIO_SRT:
                    index = int(values[1])
                    start = values[2]
                    end = values[3]
                    text = values[4]  # SRT 文本
                    # 音頻 SRT 模式下沒有 Word 文本
                    word_text = None
                    # 檢查校正狀態 - V/X 列
                    correction_state = values[5] if len(values) > 5 else ""
                elif self.parent.display_mode in [self.parent.DISPLAY_MODE_SRT_WORD, self.parent.DISPLAY_MODE_ALL]:
                    # 對於包含 Word 的模式
                    if self.parent.display_mode == self.parent.DISPLAY_MODE_ALL:
                        index = int(values[1])
                        start = values[2]
                        end = values[3]
                        srt_text = values[4]
                        word_text = values[5]
                        # 檢查校正狀態 - V/X 列
                        correction_state = values[7] if len(values) > 7 else ""
                    else:  # SRT_WORD 模式
                        index = int(values[0])
                        start = values[1]
                        end = values[2]
                        srt_text = values[3]
                        word_text = values[4]
                        # 檢查校正狀態 - V/X 列
                        correction_state = values[6] if len(values) > 6 else ""

                    # 根據標記決定使用哪個文本，不受 mismatch 標記的影響
                    if use_word and word_text:
                        text = word_text  # 使用 Word 文本
                        self.logger.debug(f"項目 {index} 使用 Word 文本: {word_text}")
                    else:
                        text = srt_text  # 使用 SRT 文本
                else:  # SRT 模式
                    index = int(values[0])
                    start = values[1]
                    end = values[2]
                    text = values[3]
                    word_text = None
                    # 檢查校正狀態 - V/X 列
                    correction_state = values[4] if len(values) > 4 else ""

                # 解析時間
                start_time = self.parse_time(start)
                end_time = self.parse_time(end)

                # 根據校正狀態決定是否應用校正
                final_text = text
                if correction_state == "✅":  # 只在有勾選的情況下應用校正
                    final_text = self.parent.correction_handler.correct_text(text, corrections)

                # 創建字幕項
                sub = pysrt.SubRipItem(
                    index=index,
                    start=start_time,
                    end=end_time,
                    text=final_text
                )
                new_srt.append(sub)

            # 保存文件
            new_srt.save(file_path, encoding='utf-8')

            # 更新界面顯示
            self.parent.update_file_info()

        except Exception as e:
            self.logger.error(f"保存 SRT 檔案時出錯: {e}")
            show_error("錯誤", f"保存檔案失敗: {str(e)}", self.parent.master)

    def parse_time(self, time_str):
        """
        解析時間字符串
        :param time_str: 時間字符串
        :return: pysrt.SubRipTime 物件
        """
        from utils.time_utils import parse_time
        return parse_time(time_str)

    def export_srt(self, from_toolbar=False):
        """
        匯出 SRT 檔案
        :param from_toolbar: 是否從工具列呼叫
        """
        try:
            if not self.parent.tree.get_children():
                show_warning("警告", "沒有可匯出的資料！", self.parent.master)
                return

            if from_toolbar:
                # 從工具列呼叫時，使用另存新檔對話框
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".srt",
                    filetypes=[("SubRip 字幕檔", "*.srt")],
                    initialdir=os.path.dirname(self.parent.srt_file_path) if self.parent.srt_file_path else None,
                    title="匯出 SRT 檔案"
                )
                if not file_path:
                    return
            else:
                # 直接更新原始檔案
                if not self.parent.srt_file_path:
                    show_warning("警告", "找不到原始檔案路徑！", self.parent.master)
                    return
                file_path = self.parent.srt_file_path

            # 保存檔案
            self.save_srt_file(file_path)

            # 顯示成功訊息
            if from_toolbar:
                show_info("成功", f"SRT 檔案已匯出至：\n{file_path}", self.parent.master)
            else:
                show_info("成功", "SRT 檔案已更新", self.parent.master)

            return True

        except Exception as e:
            show_error("錯誤", f"匯出 SRT 檔案失敗：{str(e)}", self.parent.master)
            return False

    def update_srt_data_from_treeview(self):
        """從 Treeview 更新 SRT 數據"""
        try:
            # 創建新的 SRT 數據
            new_srt_data = pysrt.SubRipFile()

            for i, item in enumerate(self.parent.tree.get_children(), 1):
                try:
                    values = self.parent.tree.item(item, 'values')

                    # 根據顯示模式獲取索引、時間和文本
                    if self.parent.display_mode == self.parent.DISPLAY_MODE_ALL:
                        try:
                            index = int(values[1]) if values[1].isdigit() else i
                        except (ValueError, TypeError):
                            index = i
                        start_time = values[2]
                        end_time = values[3]
                        text = values[4]
                    elif self.parent.display_mode == self.parent.DISPLAY_MODE_AUDIO_SRT:
                        try:
                            index = int(values[1]) if values[1].isdigit() else i
                        except (ValueError, TypeError):
                            index = i
                        start_time = values[2]
                        end_time = values[3]
                        text = values[4]
                    elif self.parent.display_mode == self.parent.DISPLAY_MODE_SRT_WORD:
                        try:
                            index = int(values[0]) if values[0].isdigit() else i
                        except (ValueError, TypeError):
                            index = i
                        start_time = values[1]
                        end_time = values[2]
                        text = values[3]
                    else:  # SRT 模式
                        try:
                            index = int(values[0]) if values[0].isdigit() else i
                        except (ValueError, TypeError):
                            index = i
                        start_time = values[1]
                        end_time = values[2]
                        text = values[3]

                    # 安全解析時間
                    try:
                        start = self.parse_time(start_time) if isinstance(start_time, str) else start_time
                        end = self.parse_time(end_time) if isinstance(end_time, str) else end_time
                    except ValueError as e:
                        self.logger.warning(f"解析時間失敗: {e}, 使用默認時間")
                        start = pysrt.SubRipTime(0, 0, 0, 0)
                        end = pysrt.SubRipTime(0, 0, 10, 0)  # 默認10秒

                    # 創建 SRT 項目
                    sub = pysrt.SubRipItem(
                        index=i,  # 使用連續的索引
                        start=start,
                        end=end,
                        text=text if text is not None else ""
                    )
                    new_srt_data.append(sub)
                except Exception as e:
                    self.logger.warning(f"處理項目 {i} 時出錯: {e}, 跳過該項目")
                    continue

            # 更新 SRT 數據
            self.parent.srt_data = new_srt_data
            self.logger.info(f"從 Treeview 更新 SRT 數據，共 {len(new_srt_data)} 個項目")

            # 如果有音頻，則更新音頻段落
            if self.parent.audio_imported and hasattr(self.parent, 'audio_player') and self.parent.srt_data:
                self.logger.info("SRT 數據已更新，正在同步音頻段落...")
                # 完全重建音頻段落
                if hasattr(self.parent.audio_player.segment_manager, 'rebuild_segments'):
                    self.parent.audio_player.segment_manager.rebuild_segments(self.parent.srt_data)
                else:
                    # 如果沒有重建方法，則使用標準方法
                    self.parent.audio_player.segment_audio(self.parent.srt_data)

                return True

            return True

        except Exception as e:
            self.logger.error(f"從 Treeview 更新 SRT 數據時出錯: {e}")
            return False

    def get_current_state(self):
        """獲取當前界面狀態，確保保存所有必要信息"""
        state = []
        for item in self.parent.tree.get_children():
            values = self.parent.tree.item(item, 'values')

            # 根據顯示模式獲取索引位置
            index_position = 1 if self.parent.display_mode in [self.parent.DISPLAY_MODE_ALL, self.parent.DISPLAY_MODE_AUDIO_SRT] else 0
            if len(values) <= index_position:
                continue

            try:
                index = str(values[index_position])
                index_num = int(index) - 1  # 0-based index for word_comparison_results
            except (ValueError, IndexError):
                continue

            # 獲取校正狀態
            correction_state = self.parent.correction_state_manager.correction_states.get(index, '')
            original_text = self.parent.correction_state_manager.original_texts.get(index, '')
            corrected_text = self.parent.correction_state_manager.corrected_texts.get(index, '')

            # 獲取 Word 比對信息
            word_match_info = {}
            if hasattr(self.parent, 'word_comparison_results') and index_num in self.parent.word_comparison_results:
                word_match_info = self.parent.word_comparison_results[index_num]

            # 組裝完整狀態信息
            state_info = {
                'values': values,
                'tags': self.parent.tree.item(item, 'tags'),
                'correction_state': correction_state,
                'original_text': original_text,
                'corrected_text': corrected_text,
                'use_word_text': self.parent.use_word_text.get(item, False),
                'word_match_info': word_match_info
            }
            state.append(state_info)

        return state

    def adjust_values_for_mode(self, values, source_mode, target_mode):
        """
        調整值列表以適應不同的顯示模式
        :param values: 原始值列表
        :param source_mode: 原始顯示模式 ("any" 表示自動檢測)
        :param target_mode: 目標顯示模式
        :return: 調整後的值列表
        """
        # 確保 values 是列表
        values = list(values)

        # 如果源模式和目標模式相同，直接返回原始值
        if source_mode == target_mode:
            return values

        # 如果 source_mode 是 "any"，嘗試自動檢測模式
        if source_mode == "any":
            # 根據值的長度嘗試判斷源模式
            length = len(values)
            if length == 5:  # [Index, Start, End, SRT Text, V/X]
                source_mode = self.parent.DISPLAY_MODE_SRT
            elif length == 6:  # [V.O, Index, Start, End, SRT Text, V/X]
                source_mode = self.parent.DISPLAY_MODE_AUDIO_SRT
            elif length == 7:  # [Index, Start, End, SRT Text, Word Text, Match, V/X]
                source_mode = self.parent.DISPLAY_MODE_SRT_WORD
            elif length == 8:  # [V.O, Index, Start, End, SRT Text, Word Text, Match, V/X]
                source_mode = self.parent.DISPLAY_MODE_ALL
            else:
                # 無法檢測，嘗試通用方法
                self.logger.warning(f"無法根據值的長度 ({length}) 檢測源模式，使用通用處理")
                return self._apply_generic_adjustment(values, target_mode)

        # 使用正確的列數填充值列表
        expected_columns = len(self.parent.columns[target_mode])

        # 提取關鍵值用於重建
        extracted = self._extract_key_values(values, source_mode)

        # 根據目標模式重新構建值列表
        rebuilt_values = self._build_values_for_mode(extracted, target_mode)

        # 確保長度正確
        if len(rebuilt_values) > expected_columns:
            rebuilt_values = rebuilt_values[:expected_columns]
        elif len(rebuilt_values) < expected_columns:
            rebuilt_values = list(rebuilt_values) + [''] * (expected_columns - len(rebuilt_values))

        return rebuilt_values

    def _extract_key_values(self, values, mode):
        """從給定模式和值中提取關鍵數據"""
        result = {
            'index': '',
            'start': '',
            'end': '',
            'srt_text': '',
            'word_text': '',
            'match': '',
            'vx': '',
            'vo': self.parent.PLAY_ICON  # 預設的播放圖標
        }

        try:
            if mode == self.parent.DISPLAY_MODE_SRT:
                # [Index, Start, End, SRT Text, V/X]
                if len(values) >= 1: result['index'] = values[0]
                if len(values) >= 2: result['start'] = values[1]
                if len(values) >= 3: result['end'] = values[2]
                if len(values) >= 4: result['srt_text'] = values[3]
                if len(values) >= 5: result['vx'] = values[4]

            elif mode == self.parent.DISPLAY_MODE_SRT_WORD:
                # [Index, Start, End, SRT Text, Word Text, Match, V/X]
                if len(values) >= 1: result['index'] = values[0]
                if len(values) >= 2: result['start'] = values[1]
                if len(values) >= 3: result['end'] = values[2]
                if len(values) >= 4: result['srt_text'] = values[3]
                if len(values) >= 5: result['word_text'] = values[4]
                if len(values) >= 6: result['match'] = values[5]
                if len(values) >= 7: result['vx'] = values[6]

            elif mode == self.parent.DISPLAY_MODE_AUDIO_SRT:
                # [V.O, Index, Start, End, SRT Text, V/X]
                if len(values) >= 1: result['vo'] = values[0]
                if len(values) >= 2: result['index'] = values[1]
                if len(values) >= 3: result['start'] = values[2]
                if len(values) >= 4: result['end'] = values[3]
                if len(values) >= 5: result['srt_text'] = values[4]
                if len(values) >= 6: result['vx'] = values[5]

            elif mode == self.parent.DISPLAY_MODE_ALL:
                # [V.O, Index, Start, End, SRT Text, Word Text, Match, V/X]
                if len(values) >= 1: result['vo'] = values[0]
                if len(values) >= 2: result['index'] = values[1]
                if len(values) >= 3: result['start'] = values[2]
                if len(values) >= 4: result['end'] = values[3]
                if len(values) >= 5: result['srt_text'] = values[4]
                if len(values) >= 6: result['word_text'] = values[5]
                if len(values) >= 7: result['match'] = values[6]
                if len(values) >= 8: result['vx'] = values[7]
        except Exception as e:
            self.logger.error(f"提取關鍵值時出錯: {e}")

        return result

    def _build_values_for_mode(self, extracted, mode):
        """根據提取的關鍵值和目標模式構建值列表"""
        if mode == self.parent.DISPLAY_MODE_SRT:
            # [Index, Start, End, SRT Text, V/X]
            return [
                extracted['index'],
                extracted['start'],
                extracted['end'],
                extracted['srt_text'],
                extracted['vx']
            ]
        elif mode == self.parent.DISPLAY_MODE_SRT_WORD:
            # [Index, Start, End, SRT Text, Word Text, Match, V/X]
            return [
                extracted['index'],
                extracted['start'],
                extracted['end'],
                extracted['srt_text'],
                extracted['word_text'],
                extracted['match'],
                extracted['vx']
            ]
        elif mode == self.parent.DISPLAY_MODE_AUDIO_SRT:
            # [V.O, Index, Start, End, SRT Text, V/X]
            return [
                extracted['vo'],
                extracted['index'],
                extracted['start'],
                extracted['end'],
                extracted['srt_text'],
                extracted['vx']
            ]
        elif mode == self.parent.DISPLAY_MODE_ALL:
            # [V.O, Index, Start, End, SRT Text, Word Text, Match, V/X]
            return [
                extracted['vo'],
                extracted['index'],
                extracted['start'],
                extracted['end'],
                extracted['srt_text'],
                extracted['word_text'],
                extracted['match'],
                extracted['vx']
            ]
        else:
            # 不應該發生，返回空列表
            self.logger.error(f"未知的顯示模式: {mode}")
            return []

    def _apply_generic_adjustment(self, values, target_mode):
        """通用的值調整方法，用於無法確定源模式的情況"""
        # 首先嘗試提取所有可能值
        extracted = {}

        # 根據值的長度和位置嘗試提取
        length = len(values)

        # 提取索引 (通常在第1-2項)
        if length >= 2:
            extracted['index'] = values[0] if not values[0] == self.parent.PLAY_ICON else values[1]
        elif length >= 1:
            extracted['index'] = values[0]
        else:
            extracted['index'] = ""

        # 提取時間 (通常在第2-4項)
        if length >= 4:
            start_idx = 1 if values[0] == self.parent.PLAY_ICON else 0
            extracted['start'] = values[start_idx + 1]
            extracted['end'] = values[start_idx + 2]
        elif length >= 3:
            extracted['start'] = values[1]
            extracted['end'] = values[2]
        else:
            extracted['start'] = ""
            extracted['end'] = ""

        # 提取文本 (通常在索引和時間之後)
        if length >= 5:
            text_idx = 4 if values[0] == self.parent.PLAY_ICON else 3
            extracted['srt_text'] = values[text_idx] if text_idx < length else ""
        elif length >= 4:
            extracted['srt_text'] = values[3]
        else:
            extracted['srt_text'] = ""

        # 檢查是否有Word文本
        if target_mode in [self.parent.DISPLAY_MODE_SRT_WORD, self.parent.DISPLAY_MODE_ALL]:
            extracted['word_text'] = ""
            extracted['match'] = ""

        # 提取校正標記
        extracted['vx'] = values[-1] if values and (values[-1] in ['✅', '❌', '']) else ""

        # 設置播放圖標
        extracted['vo'] = self.parent.PLAY_ICON

        # 根據目標模式構建結果
        result = []

        if target_mode == self.parent.DISPLAY_MODE_SRT:
            result = [extracted.get('index', ''), extracted.get('start', ''),
                    extracted.get('end', ''), extracted.get('srt_text', ''),
                    extracted.get('vx', '')]
        elif target_mode == self.parent.DISPLAY_MODE_SRT_WORD:
            result = [extracted.get('index', ''), extracted.get('start', ''),
                    extracted.get('end', ''), extracted.get('srt_text', ''),
                    extracted.get('word_text', ''), extracted.get('match', ''),
                    extracted.get('vx', '')]
        elif target_mode == self.parent.DISPLAY_MODE_AUDIO_SRT:
            result = [extracted.get('vo', self.parent.PLAY_ICON), extracted.get('index', ''),
                    extracted.get('start', ''), extracted.get('end', ''),
                    extracted.get('srt_text', ''), extracted.get('vx', '')]
        elif target_mode == self.parent.DISPLAY_MODE_ALL:
            result = [extracted.get('vo', self.parent.PLAY_ICON), extracted.get('index', ''),
                    extracted.get('start', ''), extracted.get('end', ''),
                    extracted.get('srt_text', ''), extracted.get('word_text', ''),
                    extracted.get('match', ''), extracted.get('vx', '')]

        # 確保結果長度正確
        expected_len = len(self.parent.columns[target_mode])
        if len(result) > expected_len:
            result = result[:expected_len]
        elif len(result) < expected_len:
            result = result + [''] * (expected_len - len(result))

        return result

    def undo(self, event=None):
        """撤銷操作"""
        try:
            # 調試信息
            self.logger.debug(f"嘗試撤銷: 狀態數量={len(self.parent.state_manager.states)}, 目前索引={self.parent.state_manager.current_state_index}")

            # 獲取操作信息
            previous_operation = None
            if self.parent.state_manager.current_state_index > 0 and self.parent.state_manager.current_state_index < len(self.parent.state_manager.states):
                previous_operation = self.parent.state_manager.states[self.parent.state_manager.current_state_index].operation
                self.logger.debug(f"上一操作類型: {previous_operation.get('type')}")

                # 檢查是否包含原始狀態
                if 'original_state' in previous_operation:
                    self.logger.debug(f"找到原始狀態: {len(previous_operation['original_state'])} 項目")
                else:
                    self.logger.debug("未找到原始狀態!")

            # 呼叫狀態管理器的撤銷方法
            previous_state = self.parent.state_manager.undo()


            if previous_state:
                # 專門處理合併操作
                if previous_operation and previous_operation.get('type') == 'combine_sentences':
                    original_state = previous_operation.get('original_state')
                    if original_state:
                        # 清空當前狀態
                        self.parent.tree.delete(*self.parent.tree.get_children())
                        self.parent.use_word_text.clear()

                        # 清空校正狀態
                        self.parent.correction_state_manager.correction_states.clear()
                        self.parent.correction_state_manager.original_texts.clear()
                        self.parent.correction_state_manager.corrected_texts.clear()

                        # 從原始合併前的狀態恢復
                        for item_data in original_state:
                            values = item_data.get('values', [])
                            if values:
                                item_id = self.parent.tree_manager.insert_item('', 'end', values=tuple(values))

                                # 恢復標籤
                                if 'tags' in item_data and item_data['tags']:
                                    self.parent.tree.item(item_id, tags=item_data['tags'])

                                # 恢復 use_word_text 狀態
                                if item_data.get('use_word_text', False):
                                    self.parent.use_word_text[item_id] = True

                                # 恢復校正狀態
                                index_pos = 1 if self.parent.display_mode in [self.parent.DISPLAY_MODE_ALL, self.parent.DISPLAY_MODE_AUDIO_SRT] else 0
                                if len(values) > index_pos:
                                    index = str(values[index_pos])
                                    state = item_data.get('correction_state', '')
                                    original = item_data.get('original_text', '')
                                    corrected = item_data.get('corrected_text', '')

                                    if state and original and corrected:
                                        self.parent.correction_state_manager.add_correction_state(
                                            index, original, corrected, state
                                        )

                        # 更新 SRT 數據和音頻
                        self.update_srt_data_from_treeview()
                        if self.parent.audio_imported and hasattr(self.parent, 'audio_player'):
                            self.parent.audio_player.segment_audio(self.parent.srt_data)

                        # 嘗試選中之前合併的項目
                        if 'items' in previous_operation and previous_operation['items']:
                            try:
                                items_to_select = []
                                for i, item_id in enumerate(self.parent.tree.get_children()):
                                    if i < len(previous_operation['items']):
                                        items_to_select.append(item_id)

                                if items_to_select:
                                    self.parent.tree.selection_set(items_to_select)
                                    self.parent.tree.see(items_to_select[0])
                            except Exception as select_error:
                                self.logger.warning(f"恢復選擇時出錯: {select_error}")

                        self.parent.update_status("已復原合併字幕操作")
                        return True

                    # 特別處理第一個合併操作
                    elif self.parent.state_manager.current_state_index == 0:
                        self.logger.info("正在處理第一個合併操作的撤銷")
                        # 如果是第一個操作且為合併操作，嘗試恢復到最初狀態
                        initial_state = self.parent.state_manager.states[0].state if self.parent.state_manager.states else None

                        if initial_state:
                            # 清空當前狀態
                            self.parent.tree.delete(*self.parent.tree.get_children())
                            self.parent.use_word_text.clear()

                            # 清空校正狀態
                            self.parent.correction_state_manager.correction_states.clear()
                            self.parent.correction_state_manager.original_texts.clear()
                            self.parent.correction_state_manager.corrected_texts.clear()

                            # 從最初狀態恢復
                            for item_data in initial_state:
                                values = item_data.get('values', [])
                                if values:
                                    item_id = self.parent.tree_manager.insert_item('', 'end', values=tuple(values))

                                    # 恢復標籤
                                    if 'tags' in item_data and item_data['tags']:
                                        self.parent.tree.item(item_id, tags=item_data['tags'])

                                    # 恢復 use_word_text 狀態
                                    if item_data.get('use_word_text', False):
                                        self.parent.use_word_text[item_id] = True

                                    # 恢復校正狀態
                                    index_pos = 1 if self.parent.display_mode in [self.parent.DISPLAY_MODE_ALL, self.parent.DISPLAY_MODE_AUDIO_SRT] else 0
                                    if len(values) > index_pos:
                                        index = str(values[index_pos])
                                        state = item_data.get('correction_state', '')
                                        original = item_data.get('original_text', '')
                                        corrected = item_data.get('corrected_text', '')

                                        if state and original and corrected:
                                            self.parent.correction_state_manager.add_correction_state(
                                                index, original, corrected, state
                                            )

                            # 更新 SRT 數據和音頻
                            self.update_srt_data_from_treeview()
                            if self.parent.audio_imported and hasattr(self.parent, 'audio_player'):
                                self.parent.audio_player.segment_audio(self.parent.srt_data)

                            self.parent.update_status("已恢復到初始狀態")
                            return True

                # 處理斷句操作
                elif previous_operation and previous_operation.get('type') in ['split_srt', 'split_word_text']:
                    original_state = previous_operation.get('original_state')
                    if original_state:
                        # 清空當前狀態
                        self.parent.tree.delete(*self.parent.tree.get_children())
                        self.parent.use_word_text.clear()

                        # 清空校正狀態
                        self.parent.correction_state_manager.correction_states.clear()
                        self.parent.correction_state_manager.original_texts.clear()
                        self.parent.correction_state_manager.corrected_texts.clear()

                        # 完全從原始斷句前的狀態恢復
                        for item_data in original_state:
                            values = item_data.get('values', [])
                            if values:
                                item_id = self.parent.tree_manager.insert_item('', 'end', values=tuple(values))

                                # 恢復標籤
                                if 'tags' in item_data and item_data['tags']:
                                    self.parent.tree.item(item_id, tags=item_data['tags'])

                                # 恢復 use_word_text 狀態
                                if item_data.get('use_word_text', False):
                                    self.parent.use_word_text[item_id] = True

                                # 恢復校正狀態
                                index_pos = 1 if self.parent.display_mode in [self.parent.DISPLAY_MODE_ALL, self.parent.DISPLAY_MODE_AUDIO_SRT] else 0
                                if len(values) > index_pos:
                                    index = str(values[index_pos])
                                    state = item_data.get('correction_state', '')
                                    original = item_data.get('original_text', '')
                                    corrected = item_data.get('corrected_text', '')

                                    if state and original and corrected:
                                        self.parent.correction_state_manager.add_correction_state(
                                            index, original, corrected, state
                                        )

                        # 更新 SRT 數據和音頻
                        self.update_srt_data_from_treeview()
                        if self.parent.audio_imported and hasattr(self.parent, 'audio_player'):
                            self.parent.audio_player.segment_audio(self.parent.srt_data)

                        # 選中相關項目
                        if 'srt_index' in previous_operation:
                            for item_id in self.parent.tree.get_children():
                                item_values = self.parent.tree.item(item_id, 'values')
                                if self.parent.display_mode in [self.parent.DISPLAY_MODE_ALL, self.parent.DISPLAY_MODE_AUDIO_SRT]:
                                    if len(item_values) > 1 and str(item_values[1]) == str(previous_operation['srt_index']):
                                        self.parent.tree.selection_set(item_id)
                                        self.parent.tree.see(item_id)
                                        break
                                else:
                                    if item_values and str(item_values[0]) == str(previous_operation['srt_index']):
                                        self.parent.tree.selection_set(item_id)
                                        self.parent.tree.see(item_id)
                                        break

                        self.parent.update_status(f"已復原{previous_operation.get('description', '拆分操作')}")
                        return True

                # 處理時間調整操作
                elif previous_operation and previous_operation.get('type') == 'align_end_times':
                    original_state = previous_operation.get('original_state')
                    if original_state:
                        # 清空當前狀態
                        self.parent.tree.delete(*self.parent.tree.get_children())
                        self.parent.use_word_text.clear()

                        # 清空校正狀態
                        self.parent.correction_state_manager.correction_states.clear()
                        self.parent.correction_state_manager.original_texts.clear()
                        self.parent.correction_state_manager.corrected_texts.clear()

                        # 從原始狀態恢復
                        for item_data in original_state:
                            values = item_data.get('values', [])
                            if values:
                                item_id = self.parent.tree_manager.insert_item('', 'end', values=tuple(values))

                                # 恢復標籤
                                if 'tags' in item_data and item_data['tags']:
                                    self.parent.tree.item(item_id, tags=item_data['tags'])

                                # 恢復 use_word_text 狀態
                                if item_data.get('use_word_text', False):
                                    self.parent.use_word_text[item_id] = True

                                # 恢復校正狀態
                                index_pos = 1 if self.parent.display_mode in [self.parent.DISPLAY_MODE_ALL, self.parent.DISPLAY_MODE_AUDIO_SRT] else 0
                                if len(values) > index_pos:
                                    index = str(values[index_pos])
                                    state = item_data.get('correction_state', '')
                                    original = item_data.get('original_text', '')
                                    corrected = item_data.get('corrected_text', '')

                                    if state and original and corrected:
                                        self.parent.correction_state_manager.add_correction_state(
                                            index, original, corrected, state
                                        )

                        # 更新 SRT 數據和音頻
                        self.update_srt_data_from_treeview()
                        if self.parent.audio_imported and hasattr(self.parent, 'audio_player'):
                            self.parent.audio_player.segment_audio(self.parent.srt_data)

                        self.parent.update_status("已復原時間調整操作")
                        return True

                # 處理文本編輯操作
                elif previous_operation and previous_operation.get('type') == 'edit_text':
                    original_state = previous_operation.get('original_state')
                    if original_state:
                        # 清空當前狀態
                        self.parent.tree.delete(*self.parent.tree.get_children())
                        self.parent.use_word_text.clear()

                        # 清空校正狀態
                        self.parent.correction_state_manager.correction_states.clear()
                        self.parent.correction_state_manager.original_texts.clear()
                        self.parent.correction_state_manager.corrected_texts.clear()

                        # 從原始狀態恢復
                        for item_data in original_state:
                            values = item_data.get('values', [])
                            if values:
                                item_id = self.parent.tree_manager.insert_item('', 'end', values=tuple(values))

                                # 恢復標籤
                                if 'tags' in item_data and item_data['tags']:
                                    self.parent.tree.item(item_id, tags=item_data['tags'])

                                # 恢復 use_word_text 狀態
                                if item_data.get('use_word_text', False):
                                    self.parent.use_word_text[item_id] = True

                                # 恢復校正狀態
                                index_pos = 1 if self.parent.display_mode in [self.parent.DISPLAY_MODE_ALL, self.parent.DISPLAY_MODE_AUDIO_SRT] else 0
                                if len(values) > index_pos:
                                    index = str(values[index_pos])
                                    state = item_data.get('correction_state', '')
                                    original = item_data.get('original_text', '')
                                    corrected = item_data.get('corrected_text', '')

                                    if state and original and corrected:
                                        self.parent.correction_state_manager.add_correction_state(
                                            index, original, corrected, state
                                        )

                        # 選中編輯過的項目
                        if 'item_id' in previous_operation:
                            target_index = previous_operation.get('item_index')
                            if target_index:
                                for item_id in self.parent.tree.get_children():
                                    item_values = self.parent.tree.item(item_id, 'values')
                                    index_pos = 1 if self.parent.display_mode in [self.parent.DISPLAY_MODE_ALL, self.parent.DISPLAY_MODE_AUDIO_SRT] else 0
                                    if len(item_values) > index_pos and str(item_values[index_pos]) == str(target_index):
                                        self.parent.tree.selection_set(item_id)
                                        self.parent.tree.see(item_id)
                                        break

                        # 更新 SRT 數據和音頻
                        self.update_srt_data_from_treeview()
                        if self.parent.audio_imported and hasattr(self.parent, 'audio_player'):
                            self.parent.audio_player.segment_audio(self.parent.srt_data)

                        self.parent.update_status("已復原文本編輯操作")
                        return True

                # 非特殊操作的標準恢復流程
                self.parent.tree.delete(*self.parent.tree.get_children())
                self.parent.use_word_text.clear()

                # 清空校正狀態
                self.parent.correction_state_manager.correction_states.clear()
                self.parent.correction_state_manager.original_texts.clear()
                self.parent.correction_state_manager.corrected_texts.clear()

                # 從前一個狀態恢復
                for item_data in previous_state:
                    values = item_data.get('values', [])
                    if values:
                        item_id = self.parent.tree_manager.insert_item('', 'end', values=tuple(values))

                        # 恢復標籤
                        if 'tags' in item_data and item_data['tags']:
                            self.parent.tree.item(item_id, tags=item_data['tags'])

                        # 恢復 use_word_text 狀態
                        if item_data.get('use_word_text', False):
                            self.parent.use_word_text[item_id] = True

                        # 恢復校正狀態
                        index_pos = 1 if self.parent.display_mode in [self.parent.DISPLAY_MODE_ALL, self.parent.DISPLAY_MODE_AUDIO_SRT] else 0
                        if len(values) > index_pos:
                            index = str(values[index_pos])
                            state = item_data.get('correction_state', '')
                            original = item_data.get('original_text', '')
                            corrected = item_data.get('corrected_text', '')

                            if state and original and corrected:
                                self.parent.correction_state_manager.add_correction_state(
                                    index, original, corrected, state
                                )

                # 恢復比對結果狀態
                if hasattr(self.parent, 'word_comparison_results') and self.parent.word_comparison_results:
                    self.parent.word_integration.update_display_with_comparison()

                # 更新 SRT 數據和音頻
                self.update_srt_data_from_treeview()
                if self.parent.audio_imported and hasattr(self.parent, 'audio_player'):
                    self.parent.audio_player.segment_audio(self.parent.srt_data)

                self.parent.update_status("已復原上一步操作")
                return True
            else:
                self.parent.update_status("已到達最初狀態，無法再撤銷")
                return False

        except Exception as e:
            self.logger.error(f"撤銷操作時出錯: {e}", exc_info=True)
            show_error("錯誤", f"撤銷失敗: {str(e)}", self.parent.master)
            return False

    def redo(self, event=None):
        """重做操作"""
        try:
            # 獲取下一個狀態
            next_state = self.parent.state_manager.redo()

            if next_state:
                # 獲取下一個操作信息
                next_operation = None
                if hasattr(self.parent.state_manager, 'get_current_operation'):
                    next_operation = self.parent.state_manager.get_current_operation()

                # 清空當前狀態
                self.parent.tree.delete(*self.parent.tree.get_children())
                self.parent.use_word_text.clear()

                # 清空校正狀態
                self.parent.correction_state_manager.correction_states.clear()
                self.parent.correction_state_manager.original_texts.clear()
                self.parent.correction_state_manager.corrected_texts.clear()

                # 從下一個狀態重建
                for item_data in next_state:
                    values = item_data.get('values', [])
                    if values:
                        item_id = self.parent.tree.insert('', 'end', values=tuple(values))

                        # 恢復標籤
                        if 'tags' in item_data and item_data['tags']:
                            self.parent.tree.item(item_id, tags=item_data['tags'])

                        # 恢復 use_word_text 狀態
                        if item_data.get('use_word_text', False):
                            self.parent.use_word_text[item_id] = True

                        # 恢復校正狀態
                        index_pos = 1 if self.parent.display_mode in [self.parent.DISPLAY_MODE_ALL, self.parent.DISPLAY_MODE_AUDIO_SRT] else 0
                        if len(values) > index_pos:
                            index = str(values[index_pos])
                            state = item_data.get('correction_state', '')
                            original = item_data.get('original_text', '')
                            corrected = item_data.get('corrected_text', '')

                            if state and original and corrected:
                                self.parent.correction_state_manager.add_correction_state(
                                    index, original, corrected, state
                                )

                # 恢復比對結果狀態
                self.parent.word_integration.update_display_with_comparison()

                # 更新 SRT 數據和音頻
                self.update_srt_data_from_treeview()
                if self.parent.audio_imported and hasattr(self.parent, 'audio_player'):
                    self.parent.audio_player.segment_audio(self.parent.srt_data)

                self.parent.update_status("已重做操作")
                return True
            else:
                self.parent.update_status("已到達最新狀態，無法再重做")
                return False
        except Exception as e:
            self.logger.error(f"重做操作時出錯: {e}", exc_info=True)
            show_error("錯誤", f"重做失敗: {str(e)}", self.parent.master)
            return False