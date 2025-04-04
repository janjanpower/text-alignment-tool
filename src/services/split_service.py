"""文本拆分服務模組，負責處理字幕拆分相關操作"""

import logging
import time

import pysrt
from utils.time_utils import parse_time
from utils.text_utils import simplify_to_traditional
from services.correction_service import CorrectionService
from gui.custom_messagebox import (
    show_info,
    show_warning,
    show_error,
    ask_question
)


class SplitService:
    """字幕拆分服務，處理文本拆分相關操作"""

    def __init__(self, alignment_gui):
        """
        初始化拆分服務
        :param alignment_gui: 對齊工具實例，用於訪問必要的GUI元素
        """
        self.gui = alignment_gui
        self.logger = logging.getLogger(self.__class__.__name__)
        self.last_split_operation = None

        self.correction_service = CorrectionService

    def process_srt_edit_result(self, result, item, srt_index, start_time, end_time):
        """
        處理 SRT 文本編輯結果
        :param result: 編輯結果
        :param item: 樹項目 ID
        :param srt_index: SRT 索引
        :param start_time: 開始時間
        :param end_time: 結束時間
        """
        try:
            # 保存全局樹狀態，用於後續復原
            original_tree_state = []
            for tree_item in self.gui.tree_manager.get_all_items():
                original_tree_state.append({
                    'id': tree_item,
                    'values': self.gui.tree.item(tree_item, 'values'),
                    'tags': self.gui.tree.item(tree_item, 'tags'),
                    'position': self.gui.tree.index(tree_item),
                    'use_word': self.gui.use_word_text.get(tree_item, False)
                })

            # 保存 SRT 數據的快照
            original_srt_data = []
            if hasattr(self.gui, 'srt_data'):
                for sub in self.gui.srt_data:
                    original_srt_data.append({
                        'index': sub.index,
                        'start': str(sub.start),
                        'end': str(sub.end),
                        'text': sub.text
                    })

            # 保存操作前的狀態供撤銷使用
            original_state = self.gui.get_current_state()
            original_correction = self.gui.correction_service.serialize_state() if hasattr(self.gui, 'correction_service') else None

            # 保存原始樹狀視圖項目的完整信息
            original_item_info = {
                'id': item,
                'values': self.gui.tree_manager.get_item_values(item),
                'tags': self.gui.tree_manager.get_item_tags(item),
                'position': self.gui.tree_manager.get_item_position(item),
                'use_word': self.gui.use_word_text.get(item, False)
            }

            # 在檢測到文本拆分結果後的處理部分
            if isinstance(result, list) and len(result) > 0 and isinstance(result[0], tuple):
                # 這是文本拆分結果 - 處理文本拆分和時間軸分配
                self.logger.debug(f"檢測到文本拆分結果，共 {len(result)} 個片段")
                # 記錄這是一次分割操作

                # 獲取原始文本和時間信息
                original_text = original_item_info['values'][3 if self.gui.display_mode in [self.gui.DISPLAY_MODE_SRT, self.gui.DISPLAY_MODE_SRT_WORD] else 4]

                # 獲取Word文本（如果存在）
                original_word_text = ""
                if self.gui.display_mode in [self.gui.DISPLAY_MODE_ALL, self.gui.DISPLAY_MODE_SRT_WORD]:
                    word_text_index = 5 if self.gui.display_mode == self.gui.DISPLAY_MODE_ALL else 4
                    if len(original_item_info['values']) > word_text_index:
                        original_word_text = original_item_info['values'][word_text_index]

                self.last_split_operation = {
                    'timestamp': time.time(),
                    'srt_index': srt_index,
                    'split_result': result,
                    'original_text': original_text,
                    'original_start': start_time,
                    'original_end': end_time,
                    'display_mode': self.gui.display_mode,
                    'original_correction_state': self.gui.correction_service.serialize_state() if hasattr(self.gui, 'correction_service') else {},
                    'original_word_text': original_word_text  # 保存Word文本
                }

                # 保存在狀態管理器中
                if hasattr(self.gui, 'state_manager') and hasattr(self.gui.state_manager, 'last_split_operation'):
                    self.gui.state_manager.last_split_operation = self.last_split_operation

                # 記錄該項目的原始校正狀態
                if hasattr(self.gui, 'correction_service'):
                    index_to_check = str(srt_index)
                    if index_to_check in self.gui.correction_service.correction_states:
                        self.last_split_operation['original_item_correction'] = {
                            'state': self.gui.correction_service.correction_states[index_to_check],
                            'original': self.gui.correction_service.original_texts.get(index_to_check, ''),
                            'corrected': self.gui.correction_service.corrected_texts.get(index_to_check, '')
                        }

                # 載入校正數據庫
                corrections = self.gui.load_corrections()

                # 先檢查項目是否存在
                if not self.gui.tree.exists(item):
                    self.logger.error(f"項目 {item} 不存在")
                    return

                # 保存當前標籤狀態和刪除位置
                try:
                    tags = self.gui.tree_manager.get_item_tags(item)
                    delete_position = self.gui.tree_manager.get_item_position(item)
                    values = self.gui.tree.item(item)['values']

                    # 獲取當前 Word 文本和 Match 狀態（如果有）
                    word_text = ""
                    match_status = ""

                    if self.gui.display_mode in [self.gui.DISPLAY_MODE_SRT_WORD, self.gui.DISPLAY_MODE_ALL]:
                        word_text_index = 5 if self.gui.display_mode == self.gui.DISPLAY_MODE_ALL else 4
                        match_index = 6 if self.gui.display_mode == self.gui.DISPLAY_MODE_ALL else 5

                        if len(values) > word_text_index:
                            word_text = values[word_text_index]
                        if len(values) > match_index:
                            match_status = values[match_index]

                    # 檢查原始項目的校正狀態
                    # 獲取 V/X 欄位的值
                    correction_state = ''
                    if self.gui.display_mode == self.gui.DISPLAY_MODE_ALL and len(values) > 7:
                        correction_state = values[7]
                    elif self.gui.display_mode == self.gui.DISPLAY_MODE_SRT_WORD and len(values) > 6:
                        correction_state = values[6]
                    elif self.gui.display_mode == self.gui.DISPLAY_MODE_AUDIO_SRT and len(values) > 5:
                        correction_state = values[5]
                    elif len(values) > 4:  # SRT 模式
                        correction_state = values[4]

                    # 判斷是否為未校正狀態
                    is_uncorrected = (correction_state == '❌')

                except Exception as e:
                    self.logger.error(f"獲取項目信息失敗: {e}")
                    return

                # 準備新的時間列表
                new_start_times = []
                new_end_times = []

                # 將結果轉換為列表，避免 tuple 可能引起的問題
                result_list = list(result)

                # 刪除原始項目 - 在刪除後不再使用 item 引用
                try:
                    self.gui.tree_manager.delete_item(item)
                except Exception as e:
                    self.logger.error(f"刪除項目失敗: {e}")
                    return

                # 創建 ID 映射表
                id_mapping = {'original': item}
                new_items = []

                # 處理每個分割後的文本段落
                for i, (text, new_start, new_end) in enumerate(result_list):
                    # 收集新的時間
                    new_start_times.append(new_start)
                    new_end_times.append(new_end)

                    try:
                        # 為新段落準備值
                        new_srt_index = srt_index + i if i > 0 else srt_index

                        # 檢查文本是否需要校正
                        needs_correction, corrected_text, original_text, _ = self.gui.correction_service.check_text_for_correction(text)

                        # 根據原始校正狀態決定圖標和顯示文本
                        if needs_correction:
                            if is_uncorrected:
                                correction_icon = '❌'
                                display_text = text  # 未校正狀態顯示原始文本
                            else:
                                correction_icon = '✅'
                                display_text = corrected_text  # 已校正狀態顯示校正後文本
                        else:
                            correction_icon = ''
                            display_text = text

                        # 根據顯示模式構建值列表
                        if self.gui.display_mode == self.gui.DISPLAY_MODE_ALL:
                            # [V.O, Index, Start, End, SRT Text, Word Text, Match, V/X]
                            values = [
                                self.gui.PLAY_ICON,
                                str(new_srt_index),
                                new_start,
                                new_end,
                                display_text,
                                i == 0 and word_text or "",  # 只有第一個段落保留 Word 文本
                                i == 0 and match_status or "",  # 只有第一個段落保留 Match 狀態
                                correction_icon     # V/X 根據校正需要設置
                            ]
                        elif self.gui.display_mode == self.gui.DISPLAY_MODE_SRT_WORD:
                            # [Index, Start, End, SRT Text, Word Text, Match, V/X]
                            values = [
                                str(new_srt_index),
                                new_start,
                                new_end,
                                display_text,
                                i == 0 and word_text or "",  # 只有第一個段落保留 Word 文本
                                i == 0 and match_status or "",  # 只有第一個段落保留 Match 狀態
                                correction_icon     # V/X 根據校正需要設置
                            ]
                        elif self.gui.display_mode == self.gui.DISPLAY_MODE_AUDIO_SRT:
                            # [V.O, Index, Start, End, SRT Text, V/X]
                            values = [
                                self.gui.PLAY_ICON,
                                str(new_srt_index),
                                new_start,
                                new_end,
                                display_text,
                                correction_icon   # V/X 根據校正需要設置
                            ]
                        else:  # SRT 模式
                            # [Index, Start, End, SRT Text, V/X]
                            values = [
                                str(new_srt_index),
                                new_start,
                                new_end,
                                display_text,
                                correction_icon   # V/X 根據校正需要設置
                            ]

                        # 使用安全的插入方法
                        pos = delete_position + i
                        new_item = self.gui.insert_item('', pos, values=tuple(values))
                        new_items.append(new_item)

                        # 保存 ID 映射
                        id_mapping[f'part_{i}'] = new_item
                        if i == 0:
                            id_mapping['first_new'] = new_item

                        # 如果有標籤，應用到新項目，但移除不需要的標籤如 'mismatch'
                        if tags:
                            clean_tags = tuple(tag for tag in tags if tag != 'mismatch')
                            self.gui.tree.item(new_item, tags=clean_tags)

                        # 如果需要校正，保存校正狀態
                        if needs_correction:
                            state = 'error' if is_uncorrected else 'correct'
                            self.gui.correction_service.set_correction_state(
                                str(new_srt_index),
                                original_text,
                                corrected_text,
                                state
                            )

                        # 更新 SRT 數據以反映變化
                        if i == 0:
                            # 更新原有項目
                            if srt_index - 1 < len(self.gui.srt_data):
                                self.gui.srt_data[srt_index - 1].text = display_text
                                self.gui.srt_data[srt_index - 1].start = parse_time(new_start)
                                self.gui.srt_data[srt_index - 1].end = parse_time(new_end)
                        else:
                            # 創建新的 SRT 項目
                            new_srt_item = pysrt.SubRipItem(
                                index=new_srt_index,
                                start=parse_time(new_start),
                                end=parse_time(new_end),
                                text=display_text
                            )
                            # 插入到 SRT 數據中
                            if srt_index < len(self.gui.srt_data):
                                self.gui.srt_data.insert(srt_index + i - 1, new_srt_item)
                            else:
                                self.gui.srt_data.append(new_srt_item)

                    except Exception as e:
                        self.logger.error(f"插入新項目失敗: {e}")
                        continue

                # 如果有音頻，更新音頻段落
                if self.gui.audio_imported and hasattr(self.gui, 'audio_player'):  # 修改這一行
                    # 首先嘗試使用單個區域切分方法
                    self.gui.audio_player.segment_single_audio(
                        start_time,
                        end_time,
                        new_start_times,
                        new_end_times,
                        srt_index
                    )

                    # 然後重新對整個 SRT 數據進行分割以確保一致性
                    self.gui.audio_player.segment_audio(self.gui.srt_data)
                    self.logger.info(f"已重新分割全部音頻段落，確保與 SRT 同步")

                # 重新編號
                self.gui.renumber_items()

                # 更新音頻段落的索引
                if self.gui.audio_imported:
                    self.gui.update_audio_segments()

                # 選中新創建的項目
                if new_items:
                    self.gui.tree_manager.set_selection(new_items[0])
                    self.gui.tree_manager.select_and_see(new_items[0])

                # 保存完整的操作狀態，包含所有復原所需的信息
                full_operation_info = {
                    'type': 'split_srt',
                    'description': '拆分 SRT 文本',
                    'original_tree_state': original_tree_state,  # 完整樹狀態
                    'original_srt_data': original_srt_data,  # 完整SRT數據
                    'original_item_info': original_item_info,  # 被拆分項目的信息
                    'original_state': original_state,
                    'original_correction': original_correction,
                    'split_result': result,  # 拆分結果
                    'new_items': new_items,  # 新創建的項目
                    'id_mapping': id_mapping,  # ID 映射
                    'srt_index': srt_index,
                    'start_time': start_time,
                    'end_time': end_time,
                    'is_split_operation': True,  # 標記這是分割操作
                    'target_item_id': new_items[0] if new_items else None  # 目標恢復位置
                }

                # 保存狀態
                if hasattr(self.gui, 'state_manager'):
                    # 使用當前狀態和完整的操作信息保存
                    current_state = self.gui.get_current_state()
                    current_correction = self.gui.correction_service.serialize_state() if hasattr(self.gui, 'correction_service') else None
                    self.gui.state_manager.save_state(current_state, full_operation_info, current_correction)

                # 重新綁定事件
                self.gui.bind_all_events()

                # 更新介面
                self.gui.update_status("已更新並拆分文本")

            else:
                # 處理單一文本編輯（非拆分）結果的部分保持不變
                # 這是單一文本字串結果
                text = result
                if isinstance(text, list):
                    if len(text) > 0:
                        text = str(text[0])
                    else:
                        text = ""

                # 確保文本是字串類型
                text = str(text)

                # 獲取當前值
                values = list(self.gui.tree_manager.get_item_values(item))

                # 更新 SRT 文本
                if self.gui.display_mode == self.gui.DISPLAY_MODE_ALL:
                    values[4] = text
                elif self.gui.display_mode == self.gui.DISPLAY_MODE_SRT_WORD:
                    values[3] = text
                elif self.gui.display_mode == self.gui.DISPLAY_MODE_AUDIO_SRT:
                    values[4] = text
                else:  # SRT 模式
                    values[3] = text

                # 更新 SRT 數據
                if 0 <= srt_index - 1 < len(self.gui.srt_data):
                    self.gui.srt_data[srt_index - 1].text = text

                # 更新樹狀視圖，保留原有標籤
                self.gui.tree.item(item, values=tuple(values), tags=self.gui.tree_manager.get_item_tags(item))

                # 標記 SRT 欄位被編輯
                i = srt_index - 1
                if i not in self.gui.edited_text_info:
                    self.gui.edited_text_info[i] = {'edited': []}

                if 'srt' not in self.gui.edited_text_info[i]['edited']:
                    self.gui.edited_text_info[i]['edited'].append('srt')

                # 更新音頻段落
                if self.gui.audio_imported and hasattr(self.gui, 'audio_player'):
                    # 即使只修改了文本，也重新同步音頻段落，以確保一致性
                    self.gui.audio_player.segment_audio(self.gui.srt_data)
                    self.logger.debug("文本編輯後更新音頻段落")

                # 保存當前狀態
                self.gui.save_operation_state(
                    'edit_text',
                    '編輯文本',
                    {
                        'original_state': original_state,
                        'original_correction': original_correction,
                        'item_id': item,
                        'srt_index': srt_index,
                        'old_text': original_item_info['values'][3 if self.gui.display_mode in [self.gui.DISPLAY_MODE_SRT, self.gui.DISPLAY_MODE_SRT_WORD] else 4],
                        'new_text': text
                    }
                )

                # 更新狀態
                self.gui.update_status("已更新 SRT 文本")
                self.gui.update_srt_data_from_treeview()

        except Exception as e:
            self.logger.error(f"處理 SRT 編輯結果時出錯: {e}", exc_info=True)
            show_error("錯誤", f"更新文本失敗: {str(e)}")

    def restore_from_split_operation(self, operation):
        """從拆分操作恢復狀態 - 基於完整原始狀態的復原"""
        try:
            # 清除當前狀態
            self.gui.clear_current_treeview()

            # 1. 從保存的原始樹狀態還原
            if 'original_tree_state' in operation:
                original_items = operation.get('original_tree_state', [])
                # 按照原始順序重建樹狀視圖
                for item_info in original_items:
                    values = item_info.get('values', [])
                    position = item_info.get('position', 0)
                    tags = item_info.get('tags')
                    use_word = item_info.get('use_word', False)

                    # 插入項目
                    new_id = self.gui.insert_item('', position, values=tuple(values))

                    # 恢復標籤
                    if tags:
                        self.gui.tree.item(new_id, tags=tags)

                    # 恢復使用 Word 文本標記
                    if use_word:
                        self.gui.use_word_text[new_id] = True

            # 2. 從保存的原始 SRT 數據還原
            if 'original_srt_data' in operation:
                self.gui.srt_data = pysrt.SubRipFile()
                for item in operation.get('original_srt_data', []):
                    sub = pysrt.SubRipItem(
                        index=item['index'],
                        start=parse_time(item['start']),
                        end=parse_time(item['end']),
                        text=item['text']
                    )
                    self.gui.srt_data.append(sub)

            # 3. 還原校正狀態
            if 'original_correction_state' in operation:
                original_correction = operation.get('original_correction_state')
                if hasattr(self.gui, 'correction_service') and original_correction:
                    self.gui.correction_service.clear_correction_states()
                    self.gui.correction_service.deserialize_state(original_correction)

            # 4. 更新界面狀態
            self.gui.update_status("已撤銷拆分操作")

            # 5. 如果有音頻，更新音頻段落
            if self.gui.audio_imported and hasattr(self.gui, 'audio_player'):
                self.gui.audio_player.segment_audio(self.gui.srt_data)

        except Exception as e:
            self.logger.error(f"從拆分操作恢復狀態時出錯: {e}", exc_info=True)
            # 嘗試普通恢復作為備選方案
            try:
                if 'original_srt_data' in operation:
                    # 通過 SRT 數據重建界面
                    self.rebuild_from_srt_data(operation.get('original_srt_data', []))
                else:
                    show_error("錯誤", "無法執行撤銷操作: 找不到原始數據")
            except Exception as e2:
                self.logger.error(f"備選恢復方案也失敗: {e2}", exc_info=True)
                show_error("錯誤", f"撤銷操作徹底失敗: {str(e2)}")

    def rebuild_from_srt_data(self, srt_data_list):
        """從 SRT 數據列表重建界面"""
        try:
            # 清除當前樹狀視圖
            self.gui.clear_current_treeview()

            # 重建 SRT 數據
            self.gui.srt_data = pysrt.SubRipFile()
            for item in srt_data_list:
                sub = pysrt.SubRipItem(
                    index=item['index'],
                    start=parse_time(item['start']),
                    end=parse_time(item['end']),
                    text=item['text']
                )
                self.gui.srt_data.append(sub)

            # 重建樹狀視圖
            self.refresh_treeview_from_srt()

            # 更新音頻段落
            if self.gui.audio_imported and hasattr(self.gui, 'audio_player'):
                self.gui.audio_player.segment_audio(self.gui.srt_data)

            self.logger.debug("已從 SRT 數據重建界面")
        except Exception as e:
            self.logger.error(f"從 SRT 數據重建界面時出錯: {e}")
            raise

    def refresh_treeview_from_srt(self):
        """從 SRT 數據重新填充樹狀視圖"""
        try:
            # 確保樹狀視圖已清空
            self.gui.tree_manager.clear_all()

            # 載入校正數據
            corrections = self.gui.load_corrections()

            # 從 SRT 數據填充樹狀視圖
            for sub in self.gui.srt_data:
                # 檢查文本是否需要校正
                needs_correction, corrected_text, original_text, _ = self.gui.correction_service.check_text_for_correction(text)

                # 創建樹項目的值
                values = self.create_tree_item_values_from_sub(sub, needs_correction)

                # 插入到樹狀視圖
                item_id = self.gui.insert_item('', 'end', values=tuple(values))

                # 如果需要校正，設置校正狀態
                if needs_correction:
                    self.gui.correction_service.set_correction_state(
                        str(sub.index),
                        original_text,
                        corrected_text,
                        'correct'  # 默認為已校正狀態
                    )

            self.logger.debug(f"樹狀視圖從 SRT 數據重建完成，項目數: {len(self.gui.srt_data)}")
        except Exception as e:
            self.logger.error(f"從 SRT 數據重新填充樹狀視圖時出錯: {e}")
            raise

    def create_tree_item_values_from_sub(self, sub, needs_correction):
        """從SRT項目創建樹節點的值"""
        correction_icon = '✅' if needs_correction else ''

        if self.gui.display_mode == self.gui.DISPLAY_MODE_ALL:
            values = [
                self.gui.PLAY_ICON,
                str(sub.index),
                str(sub.start),
                str(sub.end),
                sub.text,
                "",  # Word文本
                "",  # Match
                correction_icon
            ]
        elif self.gui.display_mode == self.gui.DISPLAY_MODE_SRT_WORD:
            values = [
                str(sub.index),
                str(sub.start),
                str(sub.end),
                sub.text,
                "",  # Word文本
                "",  # Match
                correction_icon
            ]
        elif self.gui.display_mode == self.gui.DISPLAY_MODE_AUDIO_SRT:
            values = [
                self.gui.PLAY_ICON,
                str(sub.index),
                str(sub.start),
                str(sub.end),
                sub.text,
                correction_icon
            ]
        else:  # SRT模式
            values = [
                str(sub.index),
                str(sub.start),
                str(sub.end),
                sub.text,
                correction_icon
            ]

        return values

    def prepare_values_for_split_item(self, text, new_start, new_end, srt_index, part_index):
        """
        為拆分項目準備值列表

        Args:
            text: 拆分後的文本
            new_start: 開始時間
            new_end: 結束時間
            srt_index: 原始 SRT 索引
            part_index: 拆分後的部分索引

        Returns:
            tuple: 值列表，適用於當前顯示模式
        """
        try:
            # 處理索引值 - 第一個部分保持原索引，其他部分則增加
            new_srt_index = srt_index + part_index if part_index > 0 else srt_index

            # 載入校正數據庫
            corrections = self.gui.load_corrections()

            # 檢查文本是否需要校正
            needs_correction, corrected_text, original_text, _ = self.gui.correction_service.check_text_for_correction(text)
            correction_icon = '✅' if needs_correction else ''

            # 按照當前顯示模式準備值
            if self.gui.display_mode == self.gui.DISPLAY_MODE_ALL:
                # [V.O, Index, Start, End, SRT Text, Word Text, Match, V/X]
                values = [
                    self.gui.PLAY_ICON,
                    str(new_srt_index),
                    new_start,
                    new_end,
                    text,  # 保持原始文本，校正狀態由圖標表示
                    part_index == 0 and self.gui.word_processor.get_paragraph_text(srt_index - 1) or "",  # 第一個部分保留 Word 文本
                    "",  # 匹配資訊清空
                    correction_icon
                ]
            elif self.gui.display_mode == self.gui.DISPLAY_MODE_SRT_WORD:
                # [Index, Start, End, SRT Text, Word Text, Match, V/X]
                values = [
                    str(new_srt_index),
                    new_start,
                    new_end,
                    text,
                    part_index == 0 and self.gui.word_processor.get_paragraph_text(srt_index - 1) or "",  # 第一個部分保留 Word 文本
                    "",  # 匹配資訊清空
                    correction_icon
                ]
            elif self.gui.display_mode == self.gui.DISPLAY_MODE_AUDIO_SRT:
                # [V.O, Index, Start, End, SRT Text, V/X]
                values = [
                    self.gui.PLAY_ICON,
                    str(new_srt_index),
                    new_start,
                    new_end,
                    text,
                    correction_icon
                ]
            else:  # SRT 模式
                # [Index, Start, End, SRT Text, V/X]
                values = [
                    str(new_srt_index),
                    new_start,
                    new_end,
                    text,
                    correction_icon
                ]

            # 如果需要校正，設置校正狀態
            if needs_correction:
                self.gui.correction_service.set_correction_state(
                    str(new_srt_index),
                    original_text,
                    corrected_text,
                    'correct'  # 默認為已校正狀態
                )

            return values

        except Exception as e:
            self.gui.logger.error(f"準備拆分項目值時出錯: {e}", exc_info=True)
            # 返回簡單的備選值，避免完全失敗
            return [str(new_srt_index), new_start, new_end, text, ""]


    def prepare_and_insert_subtitle_item(self, sub, corrections=None, tags=None, use_word=False):
        """
        準備並插入字幕項目到樹狀視圖

        Args:
            sub: 字幕項目
            corrections: 校正對照表，如果為 None 則自動載入
            tags: 要應用的標籤
            use_word: 是否使用 Word 文本

        Returns:
            新插入項目的 ID
        """
        try:
            # 如果未提供校正表，自動載入
            if corrections is None:
                corrections = self.gui.load_corrections()

            # 轉換文本為繁體中文
            text = simplify_to_traditional(sub.text.strip()) if sub.text else ""

            # 檢查校正需求
            needs_correction, corrected_text, original_text, _ = self.gui.correction_service.check_text_for_correction(text)

            # 獲取 Word 文本和匹配狀態（僅在相關模式下）
            word_text = ""
            match_status = ""

            if self.gui.display_mode in [self.gui.DISPLAY_MODE_SRT_WORD, self.gui.DISPLAY_MODE_ALL] and self.gui.word_imported:
                # 從 word_comparison_results 獲取對應結果
                if hasattr(self.gui, 'word_comparison_results') and sub.index in self.gui.word_comparison_results:
                    result = self.gui.word_comparison_results[sub.index]
                    word_text = result.get('word_text', '')
                    match_status = result.get('difference', '')

            # 根據顯示模式準備值
            if self.gui.display_mode == self.gui.DISPLAY_MODE_ALL:
                values = [
                    self.gui.PLAY_ICON,
                    str(sub.index),
                    str(sub.start),
                    str(sub.end),
                    corrected_text if needs_correction else text,
                    word_text,
                    match_status,
                    '✅' if needs_correction else ''
                ]
            elif self.gui.display_mode == self.gui.DISPLAY_MODE_SRT_WORD:
                values = [
                    str(sub.index),
                    str(sub.start),
                    str(sub.end),
                    corrected_text if needs_correction else text,
                    word_text,
                    match_status,
                    '✅' if needs_correction else ''
                ]
            elif self.gui.display_mode == self.gui.DISPLAY_MODE_AUDIO_SRT:
                values = [
                    self.gui.PLAY_ICON,
                    str(sub.index),
                    str(sub.start),
                    str(sub.end),
                    corrected_text if needs_correction else text,
                    '✅' if needs_correction else ''
                ]
            else:  # SRT 模式
                values = [
                    str(sub.index),
                    str(sub.start),
                    str(sub.end),
                    corrected_text if needs_correction else text,
                    '✅' if needs_correction else ''
                ]

            # 確認 values 已正確賦值
            self.logger.debug(f"準備插入項目 {sub.index}，值: {values}")

            # 插入項目
            item_id = self.gui.insert_item('', 'end', values=tuple(values))

            # 應用標籤
            if tags:
                self.gui.tree.item(item_id, tags=tags)

            # 設置使用 Word 文本標記
            if use_word:
                self.gui.use_word_text[item_id] = True

                # 確保標籤中有 use_word_text
                current_tags = list(self.gui.tree.item(item_id, "tags") or ())
                if "use_word_text" not in current_tags:
                    current_tags.append("use_word_text")
                    self.gui.tree.item(item_id, tags=tuple(current_tags))

            # 如果需要校正，設置校正狀態
            if needs_correction:
                self.gui.correction_service.set_correction_state(
                    str(sub.index),
                    original_text,
                    corrected_text,
                    'correct'  # 默認為已校正狀態
                )

            return item_id

        except Exception as e:
            self.logger.error(f"準備並插入字幕項目時出錯: {e}", exc_info=True)
            return None

    def process_srt_entries(self, srt_data, corrections):
        """處理 SRT 條目"""
        self.logger.debug(f"開始處理 SRT 條目，數量: {len(srt_data) if srt_data else 0}")

        if not srt_data:
            self.logger.warning("SRT 數據為空，無法處理")
            return

        for sub in srt_data:
            self.prepare_and_insert_subtitle_item(sub, corrections)


    def _update_srt_for_undo_split(self, srt_index, text, start, end):
            """
            為拆分撤銷更新SRT數據
            """
            try:
                # 將所有大於等於srt_index+1的項目從SRT數據中刪除，但保留原始索引
                i = 0
                while i < len(self.srt_data):
                    if self.srt_data[i].index > srt_index:
                        self.srt_data.pop(i)
                    else:
                        i += 1

                # 更新或新增拆分還原的項目
                if srt_index <= len(self.srt_data):
                    # 更新現有項目
                    sub = self.srt_data[srt_index - 1]
                    sub.text = text
                    sub.start = parse_time(start)
                    sub.end = parse_time(end)
                else:
                    # 新增項目
                    sub = pysrt.SubRipItem(
                        index=srt_index,
                        start=parse_time(start),
                        end=parse_time(end),
                        text=text
                    )
                    self.srt_data.append(sub)

            except Exception as e:
                self.logger.error(f"更新SRT數據時出錯: {e}", exc_info=True)
                raise

    def _create_restored_values(self, text, start, end, srt_index):
        """
        為拆分還原創建值列表
        """
        # 檢查文本是否需要校正
        needs_correction, corrected_text, original_text, _ = self.gui.correction_service.check_text_for_correction(text)
        correction_icon = '✅' if needs_correction else ''

        # 根據顯示模式準備值
        if self.gui.display_mode == self.gui.DISPLAY_MODE_ALL:
            values = [
                self.gui.PLAY_ICON,
                str(srt_index),
                start,
                end,
                text,
                "",  # Word文本
                "",  # Match
                correction_icon
            ]
        elif self.gui.display_mode == self.gui.DISPLAY_MODE_SRT_WORD:
            values = [
                str(srt_index),
                start,
                end,
                text,
                "",  # Word文本
                "",  # Match
                correction_icon
            ]
        elif self.gui.display_mode == self.gui.DISPLAY_MODE_AUDIO_SRT:
            values = [
                self.gui.PLAY_ICON,
                str(srt_index),
                start,
                end,
                text,
                correction_icon
            ]
        else:  # SRT模式
            values = [
                str(srt_index),
                start,
                end,
                text,
                correction_icon
            ]

        # 如果需要校正，設置校正狀態
        if needs_correction:
            self.gui.correction_service.set_correction_state(
                str(srt_index),
                original_text,
                corrected_text,
                'correct'  # 默認為已校正狀態
            )

        return values


    def _create_restored_values_with_correction(self, display_text, original_text, corrected_text,
                                      start, end, srt_index, correction_icon, needs_correction, word_text=""):
        """
        為拆分還原創建值列表，包含校正狀態和Word文本
        """
        # 根據顯示模式準備值
        if self.display_mode == self.DISPLAY_MODE_ALL:
            values = [
                self.PLAY_ICON,
                str(srt_index),
                start,
                end,
                display_text,
                word_text,  # 使用傳入的Word文本
                "",  # Match
                correction_icon
            ]
        elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
            values = [
                str(srt_index),
                start,
                end,
                display_text,
                word_text,  # 使用傳入的Word文本
                "",  # Match
                correction_icon
            ]
        elif self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
            values = [
                self.PLAY_ICON,
                str(srt_index),
                start,
                end,
                display_text,
                correction_icon
            ]
        else:  # SRT模式
            values = [
                str(srt_index),
                start,
                end,
                display_text,
                correction_icon
            ]

        return values