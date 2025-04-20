"""時間軸滑桿控制器模組"""

import logging
import time
import tkinter as tk
from tkinter import ttk

from audio.waveform_zoom_manager import WaveformVisualization
from utils.time_utils import parse_time, milliseconds_to_time, time_to_milliseconds

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

        # 狀態變數 - 使用單一變數集
        self.slider_active = False
        self.slider_target = None
        self.slider_frame = None
        self.time_slider = None
        self.audio_visualizer = None
        self.audio_segment = None
        self._hide_in_progress = False
        self._last_update_time = 0

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
            if self.audio_segment:
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
        if self.audio_segment:
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
        # 使用相對寬度，而不是固定像素值
        time_range_label.place(x=5, y=5, relwidth=0.97, height=20)
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
        if self.audio_segment:
            slider_y += 45  # 音頻視圖下方

        # 創建滑桿容器
        slider_container = tk.Frame(frame, bg="#1E1E1E", height=30)
        # 使用相對寬度
        slider_container.place(x=5, y=slider_y, relwidth=0.97, height=30)

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

        return slider

    def _setup_audio_visualization(self, slider_params):
        """設置音頻可視化"""
        if not self.audio_segment:
            self.logger.warning("無音頻數據可供顯示")
            return

        try:
            # 創建音頻可視化容器
            visualizer_container = tk.Frame(self.slider_frame, bg="#1E1E1E")
            visualizer_container.place(x=5, y=30, relwidth=0.97, height=40)

            # 重要：先確保容器已經完成布局
            self.slider_frame.update_idletasks()

            # 計算實際可用寬度
            container_width = visualizer_container.winfo_width()
            # 確保寬度至少為 100 像素
            visual_width = max(100, container_width - 10)

            # 創建可視化器，使用計算的實際寬度
            self.audio_visualizer = WaveformVisualization(
                visualizer_container,
                width=visual_width,
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

            # 獲取適當的視圖範圍
            view_start, view_end = self.audio_visualizer.get_optimal_view_range((start_time, end_time))

            # 確保視圖範圍包含選擇區域
            if start_time < view_start:
                view_start = max(0, start_time - 200)
            if end_time > view_end:
                view_end = min(len(self.audio_segment), end_time + 200)

            # 創建初始波形
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
        """滑桿值變化時的處理 - 即時更新視圖"""
        try:
            if not self.slider_active or not self.slider_target:
                return

            # 檢查 Tkinter 組件是否仍然有效
            try:
                if not self.slider_frame or not self.slider_frame.winfo_exists():
                    return
            except tk.TclError:
                return  # 應用已被銷毀，直接返回

            # 獲取新時間值
            new_value = float(value)

            # 安全檢查 - 確保 slider_target 包含所有必要的鍵
            if not isinstance(self.slider_target, dict):
                self.logger.error(f"slider_target 不是字典: {type(self.slider_target)}")
                return

            if "column_name" not in self.slider_target:
                self.logger.error("slider_target 缺少 column_name 鍵")
                return

            if "fixed_point" not in self.slider_target:
                self.logger.error("slider_target 缺少 fixed_point 鍵")
                return

            # 更新時間範圍
            if self.slider_target["column_name"] == "Start":
                # 調整開始時間
                start_time = min(new_value, self.slider_target["fixed_point"] - 10)
                end_time = self.slider_target["fixed_point"]
            else:
                # 調整結束時間
                start_time = self.slider_target["fixed_point"]
                end_time = max(new_value, self.slider_target["fixed_point"] + 10)

            # 確保時間範圍有效
            if end_time <= start_time:
                if self.slider_target["column_name"] == "Start":
                    start_time = self.slider_target["fixed_point"] - 100
                else:
                    end_time = self.slider_target["fixed_point"] + 100

            # 檢查是否有有效的項目
            if "item" not in self.slider_target or not self.slider_target["item"]:
                self.logger.error("slider_target 缺少有效的 item")
                return

            # 檢查樹項目是否存在
            item = self.slider_target["item"]
            if not self.tree.exists(item):
                self.logger.error(f"樹項目不存在: {item}")
                return

            # 檢查 start_pos 和 end_pos 是否存在
            if "start_pos" not in self.slider_target or "end_pos" not in self.slider_target:
                self.logger.error("slider_target 缺少 start_pos 或 end_pos 鍵")
                return

            # 獲取當前值
            values = list(self.tree.item(item, 'values'))

            # 根據調整的是開始還是結束時間來更新相應的值
            new_time = milliseconds_to_time(new_value)

            # 檢查索引是否在範圍內
            start_pos = self.slider_target["start_pos"]
            end_pos = self.slider_target["end_pos"]

            if start_pos >= len(values) or end_pos >= len(values):
                self.logger.error(f"索引超出範圍: start_pos={start_pos}, end_pos={end_pos}, values長度={len(values)}")
                return

            if self.slider_target["column_name"] == "Start":
                values[start_pos] = str(new_time)
            else:
                values[end_pos] = str(new_time)

            # 更新滑桿目標中的時間範圍
            self.slider_target.update({
                "item_start_time": start_time,
                "item_end_time": end_time
            })

            # 設置限流更新
            current_time = time.time()
            if not hasattr(self, '_last_update_time'):
                self._last_update_time = 0

            # 限制更新頻率，避免閃爍（每50毫秒最多一次更新）
            if current_time - self._last_update_time > 0.05:

                # 更新時間標籤
                self._update_time_label((start_time, end_time))

                # 更新音頻視圖
                if self.audio_visualizer and self.audio_segment:
                    self._update_audio_visualization((start_time, end_time))

                # 更新時間戳
                self._last_update_time = current_time

            # 延遲更新樹視圖值
            self.tree.item(item, values=tuple(values))

            # 更新相鄰項目
            self._update_adjacent_items(item, new_value, new_time)

        except Exception as e:
            self.logger.error(f"滑桿值變化處理時出錯: {e}")
            self.logger.exception(e)

    def _update_adjacent_items(self, item, new_value, new_time):
        """更新相鄰項目 - 簡化版本"""
        if not self.slider_target:
            return

        item_index = self.slider_target.get("item_index")
        column_name = self.slider_target.get("column_name")
        all_items = self.slider_target.get("all_items", [])

        if not all_items or item_index is None:
            return

        # 更新相鄰行
        if column_name == "Start" and item_index > 0:
            # 更新上一行結束時間
            prev_item = all_items[item_index - 1]
            if self.tree.exists(prev_item):
                prev_values = list(self.tree.item(prev_item, "values"))
                if len(prev_values) > self.slider_target["end_pos"]:
                    prev_values[self.slider_target["end_pos"]] = str(new_time)
                    self.tree.item(prev_item, values=tuple(prev_values))

        elif column_name == "End" and item_index < len(all_items) - 1:
            # 更新下一行開始時間
            next_item = all_items[item_index + 1]
            if self.tree.exists(next_item):
                next_values = list(self.tree.item(next_item, "values"))
                if len(next_values) > self.slider_target["start_pos"]:
                    next_values[self.slider_target["start_pos"]] = str(new_time)
                    self.tree.item(next_item, values=tuple(next_values))

    def _update_time_label(self, time_range):
        """更新時間標籤"""
        start_time, end_time = time_range

        for widget in self.slider_frame.winfo_children():
            if isinstance(widget, tk.Label) and widget.cget('fg') == "#4FC3F7":
                widget.config(text=self._format_time_range(start_time, end_time))
                break

    def _update_audio_visualization(self, time_range):
        """更新音頻可視化，根據選擇時間範圍動態調整視圖縮放"""
        try:
            # 檢查音頻段落和可視化器存在
            if not self.audio_segment or not self.audio_visualizer:
                return

            start_time, end_time = time_range

            # 確保時間範圍有效
            if start_time >= end_time:
                self.logger.warning(f"無效的時間範圍: {start_time} - {end_time}")
                # 修正時間範圍
                if self.slider_target["column_name"] == "Start":
                    start_time = min(start_time, self.slider_target["fixed_point"] - 100)
                    end_time = self.slider_target["fixed_point"]
                else:
                    start_time = self.slider_target["fixed_point"]
                    end_time = max(end_time, self.slider_target["fixed_point"] + 100)

            # 獲取最佳視圖範圍
            view_start, view_end = self.audio_visualizer.get_optimal_view_range((start_time, end_time))

            # 更新波形視圖 - 一次性更新，不使用動畫
            self.audio_visualizer.update_waveform_and_selection(
                (view_start, view_end),
                (start_time, end_time)
            )

        except Exception as e:
            self.logger.error(f"更新音頻可視化時出錯: {e}")

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
                    max_value = max(end_ms - 10, current_value)  # 確保最大值大於當前值
                except Exception as e:
                    self.logger.error(f"解析結束時間時出錯: {e}")
                    max_value = current_value + 10000

            # 獲取上一項的結束時間作為最小值（如果有）
            if item_index > 0:
                prev_values = self.tree.item(all_items[item_index - 1], "values")
                if len(prev_values) > end_pos:
                    try:
                        prev_end_time = parse_time(prev_values[end_pos])
                        prev_end_ms = time_to_milliseconds(prev_end_time)
                        min_value = min(prev_end_ms, current_value - 1000)  # 確保最小值比當前值小
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
                    min_value = max(start_ms + 10, current_value - 10000)  # 確保最小值適當
                except Exception as e:
                    self.logger.error(f"解析開始時間時出錯: {e}")
                    min_value = max(0, current_value - 10000)

            # 獲取下一項的開始時間作為最大值（如果有）
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

        # 確保範圍有效
        if min_value >= max_value:
            min_value = max(0, current_value - 5000)
            max_value = current_value + 5000

        return min_value, max_value

    def set_audio_segment(self, audio_segment):
        """設置要可視化的音頻段落"""
        self.audio_segment = audio_segment
        self.logger.debug(f"設置音頻段落: {'有效' if audio_segment else '無效'}")

    def hide_slider(self):
        """隱藏時間調整滑桿"""
        if self._hide_in_progress:
            return

        try:
            self._hide_in_progress = True

            # 檢查主視窗是否仍然有效
            try:
                if hasattr(self, 'parent') and self.parent and not self.parent.winfo_exists():
                    return  # 主視窗已經不存在
            except tk.TclError:
                return  # 應用已被銷毀

            # 應用時間變更
            if self.slider_active and self.time_slider:
                try:
                    self.apply_time_change()
                except Exception as e:
                    self.logger.error(f"應用時間變更時出錯: {e}")

            # 清理音頻可視化
            if self.audio_visualizer:
                try:
                    self.audio_visualizer.clear_waveform()
                    self.audio_visualizer.hide()
                except Exception:
                    pass
                self.audio_visualizer = None

            # 清理滑桿界面
            if self.slider_frame:
                try:
                    if self.slider_frame.winfo_exists():
                        self.slider_frame.place_forget()
                        self.slider_frame.destroy()
                except tk.TclError:
                    pass
                self.slider_frame = None

            # 清理狀態
            self.time_slider = None
            self.slider_active = False
            self.slider_target = None

            # 解除綁定
            try:
                if self.parent and hasattr(self.parent, 'bind'):
                    self.parent.unbind("<Button-1>")
            except Exception as e:
                self.logger.debug(f"解除綁定時出錯: {e}")

        except Exception as e:
            self.logger.error(f"隱藏滑桿時出錯: {e}")
        finally:
            self._hide_in_progress = False

    def check_slider_focus(self, event):
        """檢查點擊是否在滑桿外部"""
        try:
            if not self.slider_active or not self.slider_frame:
                return

            # 獲取滑桿框架的位置和尺寸
            slider_x = self.slider_frame.winfo_rootx()
            slider_y = self.slider_frame.winfo_rooty()
            slider_width = self.slider_frame.winfo_width()
            slider_height = self.slider_frame.winfo_height()

            # 檢查點擊是否在滑桿區域外
            if (event.x_root < slider_x or event.x_root > slider_x + slider_width or
                event.y_root < slider_y or event.y_root > slider_y + slider_height):

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

                self.apply_time_change()
                self.hide_slider()
        except Exception as e:
            self.logger.error(f"檢查滑桿焦點時出錯: {e}")
            self.hide_slider()

    def apply_time_change(self):
        """應用時間變更"""
        if not self.slider_active:
            return

        try:
            # 調用回調函數更新 SRT 和音頻
            if hasattr(self.callbacks, 'on_time_change'):
                self.callbacks.on_time_change()
        except Exception as e:
            self.logger.error(f"應用時間變更時出錯: {e}")

    def _format_time_range(self, start_time, end_time):
        """格式化並顯示時間範圍，精確到毫秒"""
        start_sec = int(start_time / 1000)
        start_ms = int(start_time % 1000)
        end_sec = int(end_time / 1000)
        end_ms = int(end_time % 1000)

        # 計算持續時間
        duration = end_time - start_time

        # 當持續時間非常短時，顯示更精確的毫秒
        if duration < 100:
            return f"{start_sec}:{start_ms:03d} → {end_sec}:{end_ms:03d} (共 {duration:.1f} ms)"
        else:
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