"""時間軸滑桿控制器模組"""

import logging
import tkinter as tk
from tkinter import ttk

from audio.audio_visualizer import AudioVisualizer
from audio.visualization_range_manager import VisualizationRangeManager
from utils.time_utils import parse_time, milliseconds_to_time, time_to_milliseconds


class TimeSliderState:
    """滑桿狀態管理類"""

    def __init__(self):
        self.active = False
        self.target = None
        self.frame = None
        self.slider = None
        self.visualizer = None
        self.range_manager = None
        self.audio_segment = None
        self.hide_in_progress = False

    def clear(self):
        """清除狀態"""
        self.active = False
        self.target = None
        self.frame = None
        self.slider = None
        self.visualizer = None
        self.range_manager = None
        self.audio_segment = None
        self.hide_in_progress = False


class TimeSliderController:
    """時間軸滑桿控制器類別，處理時間調整滑桿的顯示和控制"""

    def __init__(self, parent, tree_view, callback_manager):
        """
        初始化時間滑桿控制器
        :param parent: 父視窗
        :param tree_view: 樹狀視圖
        :param callback_manager: 回調函數管理器
        """
        self.parent = parent
        self.tree = tree_view
        self.callbacks = callback_manager
        self.logger = logging.getLogger(self.__class__.__name__)

        # 初始化狀態物件 - 這是必要的修改
        self.state = TimeSliderState()

        # 保持與原來程式碼的兼容性
        self.slider_active = False
        self.slider_target = None
        self.slider_frame = None
        self.time_slider = None
        self.audio_visualizer = None
        self.audio_segment = None
        self._hide_time_slider_in_progress = False
        self.range_manager = None  # 增加此屬性

        # 自定義樣式
        self._setup_slider_style()

    def show_slider(self, event, item, column, column_name):
        """顯示時間調整滑桿"""
        try:
            # 獲取欄位信息
            column_info = self._get_column_info(item, column, column_name)
            if not column_info:
                return

            # 解析時間值
            time_values = self._parse_time_values(column_info)
            if not self._validate_time_values(time_values):
                return

            # 準備滑桿參數
            slider_params = self._prepare_slider_params(column_info, time_values)

            # 創建UI元素
            self._create_slider_ui(column_info['bbox'], slider_params)

            # 設置音頻可視化（如果有音頻）
            if self.audio_segment:  # 改用 self.audio_segment 而不是 self.state.audio_segment
                self._setup_audio_visualization(slider_params)

        except Exception as e:
            self.logger.error(f"顯示滑桿時出錯: {e}")
            self.logger.exception(e)

    def _get_column_info(self, item, column, column_name):
        """獲取欄位相關信息"""
        bbox = self.tree.bbox(item, column)
        if not bbox:
            return None

        values = self.tree.item(item, "values")
        all_items = list(self.tree.get_children())
        item_index = all_items.index(item) if item in all_items else -1

        if item_index == -1:
            return None

        # 根據顯示模式確定索引位置
        display_mode = self.callbacks.get_display_mode() if hasattr(self.callbacks, 'get_display_mode') else None

        if display_mode in ["all", "audio_srt"]:
            index_pos = 1
            start_pos = 2
            end_pos = 3
        else:
            index_pos = 0
            start_pos = 1
            end_pos = 2

        return {
            'bbox': bbox,
            'values': values,
            'all_items': all_items,
            'item_index': item_index,
            'index_pos': index_pos,
            'start_pos': start_pos,
            'end_pos': end_pos,
            'column_name': column_name  # 確保包含列名
        }

    def _parse_time_values(self, column_info):
        """解析時間值"""
        values = column_info['values']
        start_pos = column_info['start_pos']
        end_pos = column_info['end_pos']

        def safe_parse_time(time_str):
            try:
                parsed_time = parse_time(str(time_str))
                return time_to_milliseconds(parsed_time)
            except Exception as e:
                self.logger.error(f"解析時間失敗: {time_str}, 錯誤: {e}")
                return None

        item_start_time = safe_parse_time(values[start_pos]) if len(values) > start_pos else 0
        item_end_time = safe_parse_time(values[end_pos]) if len(values) > end_pos else 10000

        return {
            'start_time': item_start_time,
            'end_time': item_end_time
        }

    def _validate_time_values(self, time_values):
        """驗證時間值是否有效"""
        if (time_values['start_time'] is None or
            time_values['end_time'] is None):
            self.logger.warning("時間解析失敗")
            return False

        # 確保結束時間大於開始時間
        if time_values['end_time'] <= time_values['start_time']:
            time_values['end_time'] = time_values['start_time'] + 200

        return True

    def _prepare_slider_params(self, column_info, time_values):
        """準備滑桿參數"""
        column_name = column_info['column_name']

        if column_name == "Start":
            is_adjusting_start = True
            fixed_point = time_values['end_time']
            current_value = time_values['start_time']
        else:  # End column
            is_adjusting_start = False
            fixed_point = time_values['start_time']
            current_value = time_values['end_time']

        return {
            'item': column_info['all_items'][column_info['item_index']],
            'column_name': column_name,
            'is_adjusting_start': is_adjusting_start,
            'fixed_point': fixed_point,
            'current_value': current_value,
            'item_start_time': time_values['start_time'],
            'item_end_time': time_values['end_time'],
            'item_index': column_info['item_index'],
            'all_items': column_info['all_items'],
            'index_pos': column_info['index_pos'],
            'start_pos': column_info['start_pos'],
            'end_pos': column_info['end_pos']
        }

    def _create_slider_ui(self, bbox, slider_params):
        """創建滑桿UI"""
        x, y, width, height = bbox

        # 清除現有滑桿
        self.hide_slider()

        # 創建框架
        self.slider_frame = self._create_slider_frame(x, y, width, height)

        # 創建時間標籤
        self._create_time_label(self.slider_frame, slider_params)

        # 創建滑桿控件
        self.time_slider = self._create_slider_control(self.slider_frame, slider_params)

        # 設置狀態
        self.slider_active = True
        self.slider_target = slider_params

        # 綁定事件
        self.parent.bind("<Button-1>", self.check_slider_focus)


    def _create_slider_frame(self, x, y, width, height):
        """創建滑桿框架"""
        # 定義常量
        LABEL_HEIGHT = 20
        AUDIO_HEIGHT = 40
        SLIDER_HEIGHT = 30
        PADDING = 5

        # 計算總高度
        total_height = LABEL_HEIGHT + PADDING + SLIDER_HEIGHT + PADDING
        if self.audio_segment:  # 改用 self.audio_segment 而不是 self.state.audio_segment
            total_height += AUDIO_HEIGHT + PADDING

        # 創建框架
        frame = tk.Frame(
            self.tree,
            bg="#1E1E1E",
            bd=0,
            relief="flat"
        )

        frame_width = 300
        frame.place(
            x=x + width,
            y=y + height + 5,
            width=frame_width,
            height=total_height
        )

        # 更新狀態
        self.state.frame = frame  # 新增 - 保存框架到狀態
        return frame

    def _create_time_label(self, frame, slider_params):
        """創建時間標籤"""
        time_range_label = tk.Label(
            frame,
            text=self._format_time_range(
                slider_params['item_start_time'],
                slider_params['item_end_time']
            ),
            font=("Noto Sans TC", 10),
            bg="#1E1E1E",
            fg="#4FC3F7",
            height=1
        )
        time_range_label.place(x=0, y=5, width=300, height=20)
        return time_range_label

    def _create_slider_control(self, frame, slider_params):
        """創建滑桿控件"""
        # 計算滑桿範圍
        min_value, max_value = self._calculate_slider_range(slider_params)

        # 確保範圍有效
        if min_value >= max_value:
            self.logger.warning(f"滑桿範圍無效: min={min_value}, max={max_value}")
            min_value = max(0, slider_params['current_value'] - 5000)
            max_value = slider_params['current_value'] + 5000
            self.logger.debug(f"使用替代範圍: {min_value} - {max_value}")

        # 確保當前值在範圍內
        current_value = slider_params['current_value']
        current_value = max(min_value, min(current_value, max_value))
        slider_params['current_value'] = current_value

        # 計算滑桿位置
        slider_y = 25  # 基本位置
        if self.audio_segment:  # 改用 self.audio_segment 而不是 self.state.audio_segment
            slider_y += 45  # 音頻視圖下方

        # 創建滑桿容器
        slider_container = tk.Frame(frame, bg="#1E1E1E", height=30)
        slider_container.place(x=5, y=slider_y, width=290, height=30)

        # 創建滑桿
        slider = ttk.Scale(
            slider_container,
            from_=min_value,
            to=max_value,
            orient=tk.HORIZONTAL,
            value=slider_params['current_value'],
            command=self.on_slider_change,
            style="TimeSlider.Horizontal.TScale"
        )
        slider.pack(fill=tk.X, expand=True, pady=5)

        # 更新狀態
        self.state.slider = slider  # 新增 - 保存滑桿到狀態
        return slider

    def _setup_audio_visualization(self, slider_params):
        """設置音頻可視化"""
        if not self.audio_segment:
            self.logger.warning("無音頻數據可供顯示")
            return

        try:
            # 創建音頻可視化容器
            visualizer_container = tk.Frame(self.slider_frame, bg="#1E1E1E")
            visualizer_container.place(x=5, y=30, width=290, height=40)

            # 創建可視化器
            self.audio_visualizer = AudioVisualizer(
                visualizer_container,
                width=280,
                height=30
            )
            self.audio_visualizer.show()

            # 關鍵：確保音頻段落正確設置
            self.audio_visualizer.set_audio_segment(self.audio_segment)

            # 等待一小段時間確保資源準備完成
            self.slider_frame.update_idletasks()

            # 計算初始視圖範圍
            start_time = slider_params['item_start_time']
            end_time = slider_params['item_end_time']
            duration = end_time - start_time
            center_time = (start_time + end_time) / 2

            # 設置視圖寬度
            if duration < 500:
                view_width = 2000
            elif duration < 2000:
                view_width = duration * 3
            else:
                view_width = duration * 2

            view_start = max(0, center_time - view_width / 2)
            view_end = min(len(self.audio_segment), center_time + view_width / 2)

            # 確保視圖範圍包含選擇區域
            if start_time < view_start:
                view_start = max(0, start_time - 200)
            if end_time > view_end:
                view_end = min(len(self.audio_segment), end_time + 200)

            # 創建初始波形 - 使用更新後的方法
            self.audio_visualizer.update_waveform_and_selection(
                (view_start, view_end),
                (start_time, end_time)
            )

            # 更新滑桿目標
            if self.slider_target:
                self.slider_target.update({
                    'view_start': view_start,
                    'view_end': view_end
                })

        except Exception as e:
            self.logger.error(f"設置音頻可視化時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def on_slider_change(self, value):
        """滑桿值變化時的處理"""
        try:
            if not self.slider_active or not self.slider_target:
                return

            # 獲取新時間值
            new_value = float(value)

            # 更新樹狀視圖並獲取新的時間範圍
            time_range = self._update_tree_values(new_value)

            # 檢查時間範圍是否有效
            if time_range:
                start_time, end_time = time_range

                # 確保時間範圍有效
                if end_time <= start_time:
                    self.logger.warning(f"調整後的時間範圍無效: {start_time} - {end_time}")
                    # 修正時間範圍
                    if self.slider_target["column_name"] == "Start":
                        start_time = min(new_value, self.slider_target["fixed_point"] - 100)
                        end_time = self.slider_target["fixed_point"]
                    else:
                        start_time = self.slider_target["fixed_point"]
                        end_time = max(new_value, self.slider_target["fixed_point"] + 100)

                # 更新時間標籤
                self._update_time_label((start_time, end_time))

                # 更新音頻可視化
                if self.audio_visualizer and self.audio_segment:
                    self._update_audio_visualization((start_time, end_time))

            # 強制更新界面
            self.tree.update()
            if self.slider_frame:
                self.slider_frame.update()

        except Exception as e:
            self.logger.error(f"滑桿值變化處理時出錯: {e}")
            self.logger.exception(e)

    def _update_tree_values(self, new_value):
        """更新樹狀視圖的值"""
        item = self.slider_target["item"]  # 使用 self.slider_target 而不是 self.state.target
        column_name = self.slider_target["column_name"]
        values = list(self.tree.item(item, "values"))

        new_time = milliseconds_to_time(new_value)
        fixed_point = self.slider_target.get("fixed_point", 0)

        if column_name == "Start":
            start_time = min(new_value, fixed_point - 10)
            end_time = fixed_point
            values[self.slider_target["start_pos"]] = str(new_time)

            # 更新上一行
            item_index = self.slider_target["item_index"]
            if item_index > 0:
                prev_item = self.slider_target["all_items"][item_index - 1]
                prev_values = list(self.tree.item(prev_item, "values"))
                prev_values[self.slider_target["end_pos"]] = str(new_time)
                self.tree.item(prev_item, values=tuple(prev_values))
        else:  # End column
            start_time = fixed_point
            end_time = max(new_value, fixed_point + 10)
            values[self.slider_target["end_pos"]] = str(new_time)

            # 更新下一行
            item_index = self.slider_target["item_index"]
            if item_index < len(self.slider_target["all_items"]) - 1:
                next_item = self.slider_target["all_items"][item_index + 1]
                next_values = list(self.tree.item(next_item, "values"))
                next_values[self.slider_target["start_pos"]] = str(new_time)
                self.tree.item(next_item, values=tuple(next_values))

        self.tree.item(item, values=tuple(values))

        # 更新滑桿目標
        self.slider_target.update({
            "item_start_time": start_time,
            "item_end_time": end_time
        })

        return start_time, end_time

    def _update_time_label(self, time_range):
        """更新時間標籤"""
        start_time, end_time = time_range

        for widget in self.slider_frame.winfo_children():  # 使用 self.slider_frame 而不是 self.state.frame
            if isinstance(widget, tk.Label) and widget.cget('fg') == "#4FC3F7":
                widget.config(text=self._format_time_range(start_time, end_time))
                break

    def _update_audio_visualization(self, time_range):
        """更新音頻可視化"""
        try:
            start_time, end_time = time_range

            # 確保時間範圍有效
            if end_time <= start_time:
                self.logger.warning(f"無效的時間範圍: {start_time} - {end_time}")
                # 修正時間範圍
                start_time, end_time = min(start_time, end_time), max(start_time, end_time)
                if end_time <= start_time:
                    end_time = start_time + 100  # 至少100毫秒的範圍

            if not hasattr(self, 'audio_visualizer') or not self.audio_visualizer:
                return

            # 根據新的時間範圍調整視圖
            duration = end_time - start_time
            center_time = (start_time + end_time) / 2

            # 計算適當的視圖寬度
            if duration < 500:  # 小於0.5秒
                view_width = 2000
            elif duration < 2000:  # 小於2秒
                view_width = duration * 3
            else:
                view_width = duration * 2

            # 確保視圖範圍合理
            view_start = max(0, center_time - view_width / 2)
            view_end = min(len(self.audio_segment), center_time + view_width / 2)

            # 檢查視圖範圍是否有效
            if view_end <= view_start:
                self.logger.warning(f"計算出的視圖範圍無效: {view_start} - {view_end}")
                view_start = max(0, center_time - 1000)
                view_end = center_time + 1000
                if view_end <= view_start:
                    view_start = 0
                    view_end = 2000

            # 確保視圖包含選擇區域
            if start_time < view_start:
                view_start = max(0, start_time - 200)
            if end_time > view_end:
                view_end = min(len(self.audio_segment), end_time + 200)

            # 最終檢查
            if view_end <= view_start:
                self.logger.error(f"最終視圖範圍仍然無效: {view_start} - {view_end}")
                view_start = 0
                view_end = min(2000, len(self.audio_segment))

            # 更新波形
            self.audio_visualizer.update_waveform_and_selection(
                (view_start, view_end),
                (start_time, end_time)
            )

            # 更新滑桿目標
            if self.slider_target:
                self.slider_target.update({
                    "view_start": view_start,
                    "view_end": view_end
                })

        except Exception as e:
            self.logger.error(f"更新音頻可視化時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _update_slider_audio_view(self, start_ms, end_ms):
        """更新音頻視圖顯示，確保正確顯示所有文本的時間範圍"""
        try:
            # 確保音頻段落和可視化器存在
            if not self.audio_segment or not self.audio_visualizer:
                return

            # 關鍵修正：檢查並交換顛倒的時間
            if start_ms > end_ms:
                self.logger.warning(f"時間範圍顛倒: {start_ms} - {end_ms}，自動交換")
                start_ms, end_ms = end_ms, start_ms

            # 確保時間範圍有效
            audio_length = len(self.audio_segment) if hasattr(self, 'audio_segment') and self.audio_segment else 100000
            start_ms = max(0, min(start_ms, audio_length))
            end_ms = max(start_ms + 100, min(end_ms, audio_length))    # 確保至少100ms的時間範圍

            # 修正：確保時間範圍有效
            if end_ms <= start_ms:
                self.logger.warning(f"計算出的視圖範圍無效: {start_ms} - {end_ms}")
                # 根據開始時間創建合理的結束時間
                end_ms = min(start_ms + 2000, audio_length)  # 至少顯示2秒

            # 計算視圖範圍，保持選擇區域在中間
            duration = end_ms - start_ms
            center_time = (start_ms + end_ms) / 2

            # 動態調整視圖寬度，確保合適的上下文
            view_width = max(duration * 3, 2000)  # 至少顯示2秒或時間範圍的3倍
            display_start = max(0, center_time - view_width / 2)
            display_end = min(audio_length, center_time + view_width / 2)

            # 確保視圖寬度符合預期
            if display_end - display_start < view_width:
                # 如果範圍受到音頻長度限制，調整起點確保寬度
                if display_end == audio_length:
                    display_start = max(0, audio_length - view_width)
                # 或者調整終點確保寬度
                else:
                    display_end = min(audio_length, display_start + view_width)

            # 確保視圖範圍始終有效
            if display_end <= display_start:
                self.logger.warning(f"無法創建有效的視圖範圍: {display_start} - {display_end}")
                display_start = 0
                display_end = min(2000, audio_length)  # 默認顯示前2秒或全部內容

            # 更新波形和選擇區域
            self.audio_visualizer.update_waveform_and_selection(
                (display_start, display_end),
                (start_ms, end_ms)
            )

        except Exception as e:
            self.logger.error(f"更新音頻視圖時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _calculate_slider_range(self, slider_params):
        """計算滑桿範圍"""
        column_name = slider_params['column_name']
        item_index = slider_params['item_index']
        all_items = slider_params['all_items']
        start_pos = slider_params['start_pos']
        end_pos = slider_params['end_pos']
        current_value = slider_params['current_value']

        min_value = 0
        max_value = 100000  # 默認最大值

        if column_name == "Start":
            # 獲取當前項的結束時間作為最大值
            values = self.tree.item(all_items[item_index], "values")
            if len(values) > end_pos:
                try:
                    end_time = parse_time(values[end_pos])
                    end_ms = time_to_milliseconds(end_time)
                    max_value = max(end_ms, current_value + 1000)  # 確保最大值至少比當前值大
                except Exception as e:
                    self.logger.error(f"解析結束時間時出錯: {e}")
                    max_value = current_value + 10000

            # 獲取上一項的結束時間作為最小值
            if item_index > 0:
                prev_values = self.tree.item(all_items[item_index - 1], "values")
                if len(prev_values) > end_pos:
                    try:
                        prev_end_time = parse_time(prev_values[end_pos])
                        prev_end_ms = time_to_milliseconds(prev_end_time)
                        min_value = min(prev_end_ms, current_value - 1000)  # 確保最小值至少比當前值小
                        min_value = max(0, min_value)  # 確保不小於0
                    except Exception as e:
                        self.logger.error(f"解析前一項結束時間時出錯: {e}")
                        min_value = 0
        else:  # End column
            # 獲取當前項的開始時間作為最小值
            values = self.tree.item(all_items[item_index], "values")
            if len(values) > start_pos:
                try:
                    start_time = parse_time(values[start_pos])
                    start_ms = time_to_milliseconds(start_time)
                    min_value = min(start_ms, current_value - 1000)  # 確保最小值至少比當前值小
                    min_value = max(0, min_value)  # 確保不小於0
                except Exception as e:
                    self.logger.error(f"解析開始時間時出錯: {e}")
                    min_value = max(0, current_value - 10000)

            # 獲取下一項的開始時間作為最大值
            if item_index < len(all_items) - 1:
                next_values = self.tree.item(all_items[item_index + 1], "values")
                if len(next_values) > start_pos:
                    try:
                        next_start_time = parse_time(next_values[start_pos])
                        next_start_ms = time_to_milliseconds(next_start_time)
                        max_value = max(next_start_ms, current_value + 1000)  # 確保最大值至少比當前值大
                    except Exception as e:
                        self.logger.error(f"解析下一項開始時間時出錯: {e}")
                        max_value = current_value + 10000

        # 最終檢查：確保範圍有效
        if min_value >= max_value:
            self.logger.warning(f"計算出的滑桿範圍無效: min={min_value}, max={max_value}")
            # 強制修正範圍
            if column_name == "Start":
                min_value = max(0, current_value - 5000)
                max_value = current_value + 5000
            else:
                min_value = current_value - 5000
                max_value = current_value + 10000

        self.logger.debug(f"滑桿範圍計算結果: {min_value} - {max_value}")
        return min_value, max_value

    def set_audio_segment(self, audio_segment):
        """設置要可視化的音頻段落"""
        if audio_segment is not None and len(audio_segment) > 0:
            self.audio_segment = audio_segment  # 設置實例屬性
            self.state.audio_segment = audio_segment  # 同時更新狀態
            if audio_segment:
                self.range_manager = VisualizationRangeManager(len(audio_segment))
                self.state.range_manager = self.range_manager  # 更新狀態中的範圍管理器
            self.logger.debug(f"設置音頻段落，長度: {len(audio_segment)} ms")
        else:
            self.audio_segment = None
            self.state.audio_segment = None
            self.range_manager = None
            self.state.range_manager = None
            self.logger.warning("設置的音頻段落為空或無效")

    def hide_slider(self):
        """隱藏時間調整滑桿"""
        if hasattr(self, '_hide_time_slider_in_progress') and self._hide_time_slider_in_progress:
            return

        try:
            self._hide_time_slider_in_progress = True

            # 應用時間變更
            if self.slider_active and self.time_slider:
                self.apply_time_change()

            # 清理音頻可視化
            if self.audio_visualizer:
                try:
                    if self.audio_visualizer.canvas and self.audio_visualizer.canvas.winfo_exists():
                        self.audio_visualizer.clear_waveform()
                except tk.TclError:
                    pass
                self.audio_visualizer = None
                self.state.visualizer = None  # 清除狀態中的視覺化器

            # 清理滑桿界面
            if self.slider_frame:
                try:
                    if self.slider_frame.winfo_exists():
                        self.slider_frame.place_forget()
                        self.slider_frame.destroy()
                except tk.TclError:
                    pass
                self.slider_frame = None
                self.state.frame = None  # 清除狀態中的框架

            if self.time_slider:
                self.time_slider = None
                self.state.slider = None  # 清除狀態中的滑桿

            self.slider_active = False
            self.slider_target = None
            self.state.target = None  # 清除狀態中的目標

            # 解除綁定
            try:
                if self.parent and hasattr(self.parent, 'bind'):
                    self.parent.unbind("<Button-1>")
            except Exception as e:
                self.logger.debug(f"解除綁定時出錯: {e}")

        except Exception as e:
            self.logger.error(f"隱藏滑桿時出錯: {e}")
        finally:
            self._hide_time_slider_in_progress = False

    def check_slider_focus(self, event):
        """檢查點擊是否在滑桿外部"""
        try:
            if not self.slider_active or not self.slider_frame:  # 使用實例屬性檢查
                return

            # 獲取點擊位置
            region = self.tree.identify_region(event.x, event.y)
            column = self.tree.identify_column(event.x)

            # 如果點擊在時間欄位，不隱藏
            if region == "cell" and column:
                column_idx = int(column[1:]) - 1
                if column_idx < len(self.tree["columns"]):
                    column_name = self.tree["columns"][column_idx]
                    if column_name in ["Start", "End"]:
                        return

            # 獲取滑桿框架的位置
            slider_x = self.slider_frame.winfo_rootx()
            slider_y = self.slider_frame.winfo_rooty()
            slider_width = self.slider_frame.winfo_width()
            slider_height = self.slider_frame.winfo_height()

            # 檢查點擊是否在滑桿區域外
            if (event.x_root < slider_x or event.x_root > slider_x + slider_width or
                event.y_root < slider_y or event.y_root > slider_y + slider_height):
                self.apply_time_change()
                self.hide_slider()
        except Exception as e:
            self.logger.error(f"檢查滑桿焦點時出錯: {e}")
            self.hide_slider()

    def apply_time_change(self):
        """應用時間變更"""
        if not self.slider_active:  # 使用實例屬性檢查
            return

        try:
            # 調用回調函數更新 SRT 和音頻
            if hasattr(self.callbacks, 'on_time_change'):
                self.callbacks.on_time_change()
        except Exception as e:
            self.logger.error(f"應用時間變更時出錯: {e}")


    def _format_time_range(self, start_time, end_time):
        """格式化並顯示時間範圍"""
        start_sec = int(start_time / 1000)
        start_ms = int(start_time % 1000)
        end_sec = int(end_time / 1000)
        end_ms = int(end_time % 1000)
        return f"{start_sec}:{start_ms:03d} → {end_sec}:{end_ms:03d}"

    def _setup_slider_style(self):
        """設置滑桿自定義樣式"""
        style = ttk.Style()

        # 設置更現代的配色和樣式
        style.configure("TimeSlider.Horizontal.TScale",
                        background="#1E1E1E",  # 深色背景
                        troughcolor="#333333",  # 軌道深灰色
                        thickness=15,          # 軌道厚度
                        sliderlength=20,       # 滑鈕長度
                        sliderrelief="flat")   # 扁平滑鈕

        # 如果平台支持，設置滑鈕顏色
        try:
            style.map("TimeSlider.Horizontal.TScale",
                    background=[("active", "#1E1E1E")],
                    troughcolor=[("active", "#444444")],
                    sliderthickness=[("active", 15)],
                    foreground=[("active", "#4FC3F7")],
                    bordercolor=[("active", "#4FC3F7")],
                    lightcolor=[("active", "#4FC3F7")],
                    darkcolor=[("active", "#334D6D")])
        except Exception as e:
            self.logger.debug(f"設置滑鈕顏色時出錯，可能是平台不支持: {e}")