"""時間軸滑桿控制器模組"""

import logging
import time
import tkinter as tk
from tkinter import ttk

from audio.audio_range_manager import AudioRangeManager
from utils.time_utils import parse_time, milliseconds_to_time, time_to_milliseconds
from audio.audio_visualizer import AudioVisualizer

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
        self.hide_in_progress = False  # 初始化為 False

    def clear(self):
        """清除狀態"""
        self.active = False
        self.target = None
        self.frame = None
        self.slider = None
        self.visualizer = None
        self.range_manager = None
        self.audio_segment = None
        self.hide_in_progress = False  # 重置為 False
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

        # 初始化狀態物件
        self.state = TimeSliderState()

        # 保持與原來程式碼的兼容性
        self.slider_active = False
        self.slider_target = None
        self.slider_frame = None
        self.time_slider = None
        self.audio_visualizer = None
        self.audio_segment = None

        # 這裡確保有這個屬性
        self._hide_time_slider_in_progress = False

        # 使用新的統一範圍管理器，將在設置音頻段落時初始化
        self.range_manager = None

        # 視圖範圍記錄
        self.last_view_range = None
        self.last_selection_range = None

        # 自定義樣式
        self._setup_slider_style()

        # 初始化必要的屬性 - 新增加
        self.dark_mode = True              # 默認使用深色模式
        self.throttle_updates = True       # 默認限流更新
        self.high_quality_mode = True      # 默認高品質
        self.enable_animations = True      # 默認啟用動畫
        self.show_audio_visualizer = True  # 默認顯示音頻可視化
        self.update_throttle_ms = 50       # 更新間隔毫秒

    def set_waveform_update_callback(self, callback):
        """設置音波更新回調函數"""
        self.waveform_update_callback = callback

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
        """創建滑桿框架 - 智能位置版本"""
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
            bg="#404040",
            bd=2,
            relief="flat"
        )

        # 獲取樹視圖的尺寸
        tree_width = self.tree.winfo_width()
        tree_height = self.tree.winfo_height()

        # 設置較合理的滑桿寬度
        frame_width = min(250, max(150, tree_width // 3))

        # 計算最佳位置 - 避免被遮擋
        # 預設為右側
        best_x = x + width

        # 如果右側空間不足，考慮放在左側
        if best_x + frame_width > tree_width - 20:
            if x > frame_width + 20:  # 左側空間足夠
                best_x = max(10, x - frame_width)
            else:  # 左右都不夠，則置中
                best_x = max(10, (tree_width - frame_width) // 2)

        # 計算最佳垂直位置
        best_y = y + height + 5

        # 檢查下方空間
        if best_y + total_height > tree_height - 10:
            # 如果下方空間不夠，則嘗試放在上方
            if y > total_height + 10:
                best_y = max(5, y - total_height)
            else:
                # 上下都不夠，則嘗試放在中間位置
                best_y = max(5, (tree_height - total_height) // 2)

        # 放置框架
        frame.place(
            x=best_x,
            y=best_y,
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
            bg="#404040",
            fg="#4FC3F7",
            height=1
        )
        # 使用相對寬度，而不是固定像素值
        time_range_label.place(x=5, y=5, relwidth=0.97, height=20)
        return time_range_label

    def _create_slider_control(self, frame, slider_params):
        """創建滑桿控件 - 優化版本"""
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
        slider_container = tk.Frame(frame, bg="#404040", height=30)
        # 使用相對寬度
        slider_container.place(x=5, y=slider_y, relwidth=0.97, height=30)

        # 創建滑桿
        slider = ttk.Scale(
            slider_container,
            from_=min_value,
            to=max_value,
            orient=tk.HORIZONTAL,
            value=current_value,
            command=self.on_slider_change,
            style="TimeSlider.Horizontal.TScale"
        )
        slider.pack(fill=tk.X, expand=True, pady=5)

        # 根據調整的欄位，設置滑桿的初始位置
        if slider_params['column_name'] == "Start":
            # 對於 START 欄位，設置滑桿初始位置為當前開始時間
            slider.set(slider_params['item_start_time'])
            slider_params['current_value'] = slider_params['item_start_time']
        else:  # End 欄位
            # 對於 END 欄位，設置滑桿初始位置為當前結束時間
            slider.set(slider_params['item_end_time'])
            slider_params['current_value'] = slider_params['item_end_time']

        # 立即觸發一次滑桿更新，確保視圖和值同步
        self.on_slider_change(slider.get())

        return slider

    def _setup_audio_visualization(self, slider_params):
        """設置音頻可視化 - 完全優化版本，支持狀態恢復"""
        if not self.audio_segment:
            self.logger.warning("無音頻數據可供顯示")
            return

        try:
            # 創建音頻可視化容器
            visualizer_container = tk.Frame(self.slider_frame, bg="#233A68")
            visualizer_container.place(x=5, y=30, relwidth=0.97, height=40)

            # 確保容器已經完成布局
            self.slider_frame.update_idletasks()

            # 計算實際可用寬度
            container_width = visualizer_container.winfo_width()
            # 確保寬度至少為 100 像素
            visual_width = max(100, container_width - 10)

            # 使用新的 AudioVisualizer 類創建可視化器
            self.audio_visualizer = AudioVisualizer(
                visualizer_container,
                width=visual_width,
                height=30
            )

            # 設置深色主題和高品質
            self.audio_visualizer.set_theme(dark_mode=True)
            self.audio_visualizer.set_quality(
                high_quality=True,
                enable_animation=True  # 啟用動畫
            )

            self.audio_visualizer.show()

            # 設置音頻段落
            self.audio_visualizer.set_audio_segment(self.audio_segment)

            # 等待確保資源準備完成
            self.slider_frame.update_idletasks()

            # 從 slider_params 獲取基本數據
            start_time = slider_params['item_start_time']
            end_time = slider_params['item_end_time']
            item_id = slider_params['item']
            column_name = slider_params['column_name']

            # 檢查是否有該項目的保存狀態
            has_saved_state = (
                hasattr(self, '_item_waveform_states') and
                item_id in self._item_waveform_states
            )

            if has_saved_state:
                # 使用保存的狀態
                item_state = self._item_waveform_states[item_id]
                view_start, view_end = item_state['view_range']
                saved_zoom_level = item_state.get('zoom_level')

                # 更新范圍確保包含當前選擇
                if start_time < view_start:
                    view_start = max(0, start_time - 200)
                if end_time > view_end:
                    view_end = min(len(self.audio_segment), end_time + 200)

            else:
                # 沒有保存狀態，根據調整的欄位計算最佳視圖範圍
                duration = end_time - start_time

                if column_name == "Start":
                    # 對於開始時間調整，視圖範圍向前擴展
                    view_width = max(5000, duration * 4)
                    view_start = max(0, start_time - view_width * 0.5)
                    view_end = min(len(self.audio_segment), start_time + view_width * 0.5)
                else:  # End 欄位
                    # 對於結束時間調整，視圖範圍向後擴展
                    view_width = max(5000, duration * 4)
                    view_start = max(0, end_time - view_width * 0.75)
                    view_end = min(len(self.audio_segment), end_time + view_width * 0.25)

                saved_zoom_level = None  # 沒有保存的縮放級別

            # 更新滑桿目標，添加原始時間值（用於撤銷）
            if self.slider_target:
                self.slider_target.update({
                    'view_start': view_start,
                    'view_end': view_end,
                    'original_start_time': start_time,
                    'original_end_time': end_time
                })

            # 更新波形視圖
            self.audio_visualizer.update_waveform_and_selection(
                (view_start, view_end),
                (start_time, end_time),
                zoom_level=saved_zoom_level,  # 使用保存的縮放級別（如果有）
                animate=False  # 初始顯示不使用動畫
            )

        except Exception as e:
            self.logger.error(f"設置音頻可視化時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def on_slider_change(self, value):
        """滑桿值變化時的處理 - 完全優化版本"""
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

            # 安全檢查
            if not isinstance(self.slider_target, dict):
                self.logger.error(f"slider_target 不是字典: {type(self.slider_target)}")
                return

            required_keys = ["column_name", "fixed_point", "item"]
            for key in required_keys:
                if key not in self.slider_target:
                    self.logger.error(f"slider_target 缺少 {key} 鍵")
                    return

            # 確保 item 存在且有效
            target_item = self.slider_target["item"]
            if not self.tree.exists(target_item):
                self.logger.error(f"樹項目不存在: {target_item}")
                return

            # 更新時間範圍
            if self.slider_target["column_name"] == "Start":
                # 調整開始時間 - 確保不超過結束時間減去最小持續時間
                min_duration = 100  # 最小持續時間（毫秒）
                start_time = min(new_value, self.slider_target["fixed_point"] - min_duration)
                end_time = self.slider_target["fixed_point"]
            else:
                # 調整結束時間 - 確保不小於開始時間加上最小持續時間
                min_duration = 100  # 最小持續時間（毫秒）
                start_time = self.slider_target["fixed_point"]
                end_time = max(new_value, self.slider_target["fixed_point"] + min_duration)

            # 確保時間範圍有效
            if end_time <= start_time:
                if self.slider_target["column_name"] == "Start":
                    start_time = end_time - min_duration
                else:
                    end_time = start_time + min_duration

            # 獲取當前值
            values = list(self.tree.item(target_item, 'values'))

            # 檢查 start_pos 和 end_pos 是否存在
            if "start_pos" not in self.slider_target or "end_pos" not in self.slider_target:
                self.logger.error("slider_target 缺少 start_pos 或 end_pos 鍵")
                return

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
                if hasattr(self, 'audio_visualizer') and self.audio_visualizer and self.audio_segment:
                    self._update_slider_audio_view(start_time, end_time)

                # 更新時間戳
                self._last_update_time = current_time

            # 更新樹視圖值
            self.tree.item(target_item, values=tuple(values))

            # 更新相鄰項目
            self._update_adjacent_items(target_item, new_value, new_time)

        except Exception as e:
            self.logger.error(f"滑桿值變化處理時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _update_adjacent_items(self, target_item, new_value, new_time):
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

            # 使用範圍管理器計算視圖範圍（如果可用）
            if self.range_manager:
                view_start, view_end = self.range_manager.get_optimal_view_range((start_time, end_time))
            else:
                # 回退到旧方法以防 range_manager 不可用
                view_width = self._calculate_dynamic_view_width(duration)
                center_time = (start_time + end_time) / 2
                view_start = max(0, center_time - view_width / 2)
                view_end = min(len(self.audio_segment), view_start + view_width)

            # 更新波形視圖 - 一次性更新，不使用動畫
            self.audio_visualizer.update_waveform_and_selection(
                (view_start, view_end),
                (start_time, end_time)
            )

        except Exception as e:
            self.logger.error(f"更新音頻可視化時出錯: {e}")

    def _update_slider_audio_view(self, start_ms, end_ms):
        """更新滑桿音頻可視化視圖 - 修正版本"""
        try:
            if not hasattr(self, 'audio_visualizer') or not self.audio_visualizer:
                return

            # 確保音頻段落有效
            if not self.audio_segment or len(self.audio_segment) == 0:
                return

            # 節流更新頻率，避免過度渲染
            current_time = time.time() * 1000  # 轉換為毫秒
            if hasattr(self, '_last_visualizer_update') and current_time - self._last_visualizer_update < 50:  # 50ms 節流
                return
            self._last_visualizer_update = current_time

            # 計算選擇區域持續時間
            duration = end_ms - start_ms

            # 計算視圖範圍 - 基於選擇區域的大小動態調整
            if self.range_manager:
                # 使用範圍管理器計算最佳視圖範圍
                try:
                    view_start, view_end = self.range_manager.get_optimal_view_range((start_ms, end_ms))
                    # 計算適合的縮放級別
                    zoom_level = self.range_manager.calculate_zoom_level((start_ms, end_ms))
                except Exception as e:
                    # 如果範圍管理器調用失敗，使用後備方法
                    self.logger.debug(f"範圍管理器調用失敗，使用後備方法: {e}")
                    # 自適應視圖寬度計算
                    if duration < 100:
                        view_width = duration * 10
                        zoom_level = 5.0
                    elif duration < 500:
                        view_width = duration * 6
                        zoom_level = 3.0
                    elif duration < 2000:
                        view_width = duration * 4
                        zoom_level = 2.0
                    else:
                        view_width = duration * 2.5
                        zoom_level = 1.0

                    # 確保視圖寬度在合理範圍內
                    view_width = max(1000, min(15000, view_width))

                    # 計算視圖中心並生成範圍
                    center = (start_ms + end_ms) / 2
                    view_start = max(0, center - view_width / 2)
                    view_end = min(len(self.audio_segment), view_start + view_width)
            else:
                # 自適應視圖寬度計算
                if duration < 100:
                    view_width = duration * 10
                    zoom_level = 5.0
                elif duration < 500:
                    view_width = duration * 6
                    zoom_level = 3.0
                elif duration < 2000:
                    view_width = duration * 4
                    zoom_level = 2.0
                else:
                    view_width = duration * 2.5
                    zoom_level = 1.0

                # 確保視圖寬度在合理範圍內
                view_width = max(1000, min(15000, view_width))

                # 計算視圖中心並生成範圍
                center = (start_ms + end_ms) / 2
                view_start = max(0, center - view_width / 2)
                view_end = min(len(self.audio_segment), view_start + view_width)

            # 僅在範圍有實質變化時更新波形視圖
            threshold = 10  # 毫秒閾值，避免微小變化觸發重繪
            range_changed = (
                not hasattr(self, 'last_view_range') or
                not hasattr(self, 'last_selection_range') or
                self.last_view_range is None or
                self.last_selection_range is None or
                abs(self.last_view_range[0] - view_start) > threshold or
                abs(self.last_view_range[1] - view_end) > threshold or
                abs(self.last_selection_range[0] - start_ms) > threshold or
                abs(self.last_selection_range[1] - end_ms) > threshold
            )

            if range_changed:
                # 檢測是持續縮放還是選擇範圍的單次變化
                continuous_change = (
                    hasattr(self, 'last_selection_range') and
                    self.last_selection_range is not None and
                    (abs(self.last_selection_range[0] - start_ms) < 300 or
                    abs(self.last_selection_range[1] - end_ms) < 300)
                )

                # 針對連續變化和單次變化使用不同的動畫策略
                animate = hasattr(self, 'enable_animations') and self.enable_animations
                if continuous_change:
                    # 連續變化使用較少的動畫步數提高響應速度
                    self.audio_visualizer.update_waveform_and_selection(
                        (view_start, view_end),
                        (start_ms, end_ms),
                        zoom_level=zoom_level,
                        animate=False  # 連續變化時禁用動畫以提高響應性
                    )
                else:
                    # 單次較大變化使用完整動畫提供良好的視覺過渡
                    self.audio_visualizer.update_waveform_and_selection(
                        (view_start, view_end),
                        (start_ms, end_ms),
                        zoom_level=zoom_level,
                        animate=animate
                    )

                # 記錄最後的範圍
                self.last_view_range = (view_start, view_end)
                self.last_selection_range = (start_ms, end_ms)

                # 更新提示，如果持續時間變化較大
                if hasattr(self, 'last_duration'):
                    duration_change = abs(duration - self.last_duration)
                    if duration_change > 500:  # 超過500毫秒的變化
                        # 可以添加視覺或音頻提示
                        pass
                self.last_duration = duration

        except Exception as e:
            self.logger.error(f"更新滑桿音頻視圖時出錯: {e}")
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
        """設置要可視化的音頻段落，同時初始化範圍管理器"""
        if audio_segment is not None and len(audio_segment) > 0:
            self.audio_segment = audio_segment
            self.state.audio_segment = audio_segment

            # 使用新的 AudioRangeManager 初始化範圍管理器
            if audio_segment:
                self.range_manager = AudioRangeManager(len(audio_segment))
                self.state.range_manager = self.range_manager

            self.logger.debug(f"設置音頻段落，長度: {len(audio_segment)} ms")
        else:
            self.audio_segment = None
            self.state.audio_segment = None
            self.range_manager = None
            self.state.range_manager = None
            self.logger.warning("設置的音頻段落為空或無效")

    def set_visualization_options(self, high_quality=True, enable_animations=True, dark_mode=True, show_visualizer=True):
        """設置音頻可視化選項"""
        self.high_quality_mode = high_quality
        self.enable_animations = enable_animations
        self.dark_mode = dark_mode
        self.show_audio_visualizer = show_visualizer

        # 如果已經有可視化器，更新其設置
        if hasattr(self, 'audio_visualizer') and self.audio_visualizer:
            self.audio_visualizer.set_theme(dark_mode=dark_mode)
            self.audio_visualizer.set_quality(
                high_quality=high_quality,
                enable_animation=enable_animations
            )

    def hide_slider(self):
        """隱藏時間調整滑桿 - 完全優化版本"""
        # 使用統一的防重入標誌
        if getattr(self, '_hide_in_progress', False):
            return

        try:
            # 設置防重入標誌
            self._hide_in_progress = True

            # 檢查主視窗是否仍然有效
            try:
                if hasattr(self, 'parent') and self.parent and not self.parent.winfo_exists():
                    return  # 主視窗已經不存在，直接返回
            except tk.TclError:
                return  # 應用已被銷毀，直接返回

            # 應用時間變更前先記錄當前狀態（用於恢復）
            if self.slider_active and self.slider_target:
                # 保存當前的調整項目和時間資訊
                self._last_slider_item = self.slider_target.get('item', None)
                self._last_slider_column = self.slider_target.get('column_name', None)
                self._last_slider_start_time = self.slider_target.get('item_start_time', None)
                self._last_slider_end_time = self.slider_target.get('item_end_time', None)

                try:
                    # 應用時間變更
                    self.apply_time_change()
                except Exception as e:
                    self.logger.error(f"應用時間變更時出錯: {e}")

            # 清理音頻可視化
            if hasattr(self, 'audio_visualizer') and self.audio_visualizer:
                try:
                    self.audio_visualizer.clear_waveform()
                except Exception:
                    pass
                self.audio_visualizer = None

            # 清理滑桿界面
            if hasattr(self, 'slider_frame') and self.slider_frame:
                try:
                    if self.slider_frame.winfo_exists():
                        self.slider_frame.place_forget()
                        self.slider_frame.destroy()
                except tk.TclError:
                    pass
                self.slider_frame = None

            if hasattr(self, 'time_slider'):
                self.time_slider = None

            # 重置狀態
            self.slider_active = False
            self.slider_target = None

            # 解除綁定
            try:
                if hasattr(self, 'parent') and self.parent and hasattr(self.parent, 'bind'):
                    self.parent.unbind("<Button-1>")
            except Exception as e:
                self.logger.debug(f"解除綁定時出錯: {e}")

        except Exception as e:
            self.logger.error(f"隱藏滑桿時出錯: {e}")
        finally:
            # 重置防重入標誌
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
        """應用時間變更 - 增強版本"""
        if not self.slider_active or not self.slider_target:
            return

        try:
            # 獲取當前調整的數據
            item = self.slider_target.get('item')
            column_name = self.slider_target.get('column_name')
            start_time = self.slider_target.get('item_start_time')
            end_time = self.slider_target.get('item_end_time')

            # 添加日誌
            self.logger.debug(f"應用時間變更: 項目={item}, 欄位={column_name}, 開始={start_time}ms, 結束={end_time}ms")

            # 創建時間變更記錄（用於撤銷/重做）
            time_change_record = {
                'item': item,
                'column': column_name,
                'original_start': self.slider_target.get('original_start_time'),
                'original_end': self.slider_target.get('original_end_time'),
                'new_start': start_time,
                'new_end': end_time,
                'timestamp': time.time()
            }

            # 保存變更記錄
            if not hasattr(self, 'time_change_history'):
                self.time_change_history = []
            self.time_change_history.append(time_change_record)

            # 限制歷史記錄長度
            if len(self.time_change_history) > 20:
                self.time_change_history = self.time_change_history[-20:]

            # 調用回調函數更新 SRT 和音頻
            if hasattr(self.callbacks, 'on_time_change'):
                self.callbacks.on_time_change()

            # 更新波形視圖狀態
            self._update_waveform_state_after_change()

        except Exception as e:
            self.logger.error(f"應用時間變更時出錯: {e}")

    def _update_waveform_state_after_change(self):
        """更新並保存波形視圖狀態，便於下次打開時恢復"""
        try:
            if hasattr(self, 'audio_visualizer') and self.audio_visualizer:
                # 保存最後的視圖範圍和選擇範圍
                self._last_view_range = self.audio_visualizer.current_view_range
                self._last_selection_range = self.audio_visualizer.current_selection_range
                self._last_zoom_level = getattr(self.audio_visualizer, '_last_zoom_level', None)

                # 保存針對特定項目的狀態
                if self.slider_target and 'item' in self.slider_target:
                    item_id = self.slider_target['item']

                    if not hasattr(self, '_item_waveform_states'):
                        self._item_waveform_states = {}

                    # 為每個項目保存最佳視圖狀態
                    self._item_waveform_states[item_id] = {
                        'view_range': self._last_view_range,
                        'selection_range': self._last_selection_range,
                        'zoom_level': self._last_zoom_level,
                        'timestamp': time.time()
                    }

                    # 限制保存的項目數
                    if len(self._item_waveform_states) > 50:
                        # 移除最舊的項目
                        oldest_item = min(
                            self._item_waveform_states.keys(),
                            key=lambda k: self._item_waveform_states[k]['timestamp']
                        )
                        del self._item_waveform_states[oldest_item]

        except Exception as e:
            self.logger.error(f"更新波形視圖狀態時出錯: {e}")

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
                        background="#404040",  # 深色背景
                        troughcolor="#333333",  # 軌道深灰色
                        thickness=15,          # 軌道厚度
                        sliderlength=20,       # 滑鈕長度
                        sliderrelief="flat")   # 扁平滑鈕

        # 如果平台支持，設置滑鈕顏色
        try:
            style.map("TimeSlider.Horizontal.TScale",
                    background=[("active", "#404040")],
                    troughcolor=[("active", "#444444")],
                    sliderthickness=[("active", 15)],
                    foreground=[("active", "#4FC3F7")],
                    bordercolor=[("active", "#4FC3F7")],
                    lightcolor=[("active", "#4FC3F7")],
                    darkcolor=[("active", "#334D6D")])
        except Exception as e:
            self.logger.debug(f"設置滑鈕顏色時出錯，可能是平台不支持: {e}")