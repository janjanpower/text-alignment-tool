"""時間軸滑桿控制器模組"""

import logging
import tkinter as tk
from tkinter import ttk

from audio.audio_visualizer import AudioVisualizer
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

        # 滑桿狀態變數
        self.slider_active = False
        self.slider_target = None
        self.slider_start_value = 0
        self.time_slider = None
        self.slider_frame = None
        self._hide_time_slider_in_progress = False

        # 音頻可視化
        self.audio_visualizer = None
        self.audio_segment = None

        # 自定義樣式
        self._setup_slider_style()

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
                    troughcolor=[("active", "#444444")],  # 更明顯的軌道顏色
                    sliderthickness=[("active", 15)],  # 活動時略微增大
                    foreground=[("active", "#4FC3F7")],  # 活動時的亮藍色
                    bordercolor=[("active", "#4FC3F7")],
                    lightcolor=[("active", "#4FC3F7")],
                    darkcolor=[("active", "#334D6D")])
        except Exception as e:
            self.logger.debug(f"設置滑鈕顏色時出錯，可能是平台不支持: {e}")

        # 為 tk.Frame 設置圓角和邊框效果
        style.configure("TimeSlider.TFrame",
                        background="#1E1E1E",
                        relief="flat")

    def show_slider(self, event, item, column, column_name):
        """
        顯示時間調整滑桿，並確保正確處理音頻視圖
        :param event: 事件對象
        :param item: 樹視圖項目
        :param column: 列
        :param column_name: 列名稱
        """
        try:
            # 獲取單元格的位置和大小
            bbox = self.tree.bbox(item, column)
            if not bbox:
                return

            x, y, width, height = bbox

            # 獲取當前值和相關項目
            values = self.tree.item(item, "values")

            # 獲取樹狀視圖中的所有項目
            all_items = []
            for child in self.tree.get_children():
                all_items.append(child)
            item_index = all_items.index(item) if item in all_items else -1

            if item_index == -1:
                return

            # 根據不同模式確定索引、開始時間和結束時間的位置
            display_mode = self.callbacks.get_display_mode() if hasattr(self.callbacks, 'get_display_mode') else None

            if display_mode in ["all", "audio_srt"]:
                index_pos = 1
                start_pos = 2
                end_pos = 3
            else:  # SRT 或 SRT_WORD 模式
                index_pos = 0
                start_pos = 1
                end_pos = 2

            # 安全的時間解析函數
            def safe_parse_time(time_str):
                try:
                    from utils.time_utils import parse_time, time_to_milliseconds
                    parsed_time = parse_time(str(time_str))
                    return time_to_milliseconds(parsed_time)
                except Exception as e:
                    self.logger.error(f"解析時間失敗: {time_str}, 錯誤: {e}")
                    return None

            # 解析當前文本項目的時間範圍
            item_start_time = safe_parse_time(values[start_pos]) if len(values) > start_pos else 0
            item_end_time = safe_parse_time(values[end_pos]) if len(values) > end_pos else 10000

            # 檢查時間解析是否成功
            if item_start_time is None or item_end_time is None:
                self.logger.warning(f"時間解析失敗，使用默認值")
                item_start_time = item_start_time or 0
                item_end_time = item_end_time or 10000

            # 創建滑桿控件
            self._create_slider(
                x, y, width, height,
                item, column_name,
                values, item_index, all_items,
                index_pos, start_pos, end_pos
            )

            # 確保音頻段落已設置
            if self.audio_segment is None:
                self.logger.warning("音頻段落未設置，無法顯示音頻視圖")
                return

            # 創建或更新音頻可視化並確保初始的高亮區域正確
            if hasattr(self, 'audio_visualizer') and self.audio_visualizer:
                # 計算合適的視圖範圍 - 確保高亮區域居中且有足夠上下文
                duration = item_end_time - item_start_time
                center_time = (item_start_time + item_end_time) / 2

                # 動態調整視圖寬度 - 較小的時間範圍需要更大的上下文
                min_width = max(1000, duration * 2)  # 至少1秒或時間範圍的2倍
                view_width = min(len(self.audio_segment), min_width)

                # 計算起止點，確保高亮區域在視圖中居中顯示
                display_start = max(0, center_time - view_width / 2)
                display_end = min(len(self.audio_segment), display_start + view_width)

                # 確保不超出邊界
                if display_end > len(self.audio_segment):
                    display_start = max(0, len(self.audio_segment) - view_width)
                    display_end = len(self.audio_segment)

                # 更新音頻視圖顯示 - 確保高亮區域正確顯示
                self.audio_visualizer.update_waveform_and_selection(
                    (display_start, display_end),
                    (item_start_time, item_end_time)
                )

        except Exception as e:
            self.logger.error(f"顯示滑桿時出錯: {e}")
            self.logger.exception(e)

    def set_audio_segment(self, audio_segment):
        """設置要可視化的音頻段落"""
        if audio_segment is not None and len(audio_segment) > 0:
            self.audio_segment = audio_segment
            self.logger.debug(f"設置音頻段落，長度: {len(audio_segment)} ms")

            # 如果已經有可視化器，更新其內容
            if hasattr(self, 'audio_visualizer') and self.audio_visualizer:
                try:
                    self.audio_visualizer.create_waveform(audio_segment)
                except Exception as e:
                    self.logger.error(f"更新音頻可視化器時出錯: {e}")
        else:
            self.audio_segment = None
            self.logger.warning("設置的音頻段落為空或無效")

    def _create_slider(self, x, y, width, height, item, column_name, values,
               item_index, all_items, index_pos, start_pos, end_pos):
        """創建滑桿"""
        try:
            # 如果已有滑桿，先清除
            self.hide_slider()

            # 固定高度設置
            LABEL_HEIGHT = 20  # 時間標籤固定高度
            AUDIO_HEIGHT = 60  # 音波視圖固定高度
            SLIDER_HEIGHT = 50  # 滑桿固定高度
            PADDING = 5  # 組件間距

            # 計算總高度 - 根據是否有音頻來調整
            if self.audio_segment:
                total_height = (
                    LABEL_HEIGHT + PADDING +
                    AUDIO_HEIGHT + PADDING +
                    SLIDER_HEIGHT + PADDING
                )
            else:
                total_height = (
                    LABEL_HEIGHT + PADDING +
                    SLIDER_HEIGHT + PADDING
                )

            # 創建滑桿框架
            self.slider_frame = tk.Frame(
                self.tree,
                bg="#1E1E1E",
                bd=0,
                relief="flat"
            )
            frame_width = 300  # 增加寬度以顯示更多波形細節

            # 放置滑桿框架
            self.slider_frame.place(
                x=x + width,
                y=y + height + 5,
                width=frame_width,
                height=total_height
            )

            # 安全的時間解析函數
            def safe_parse_time(time_str):
                try:
                    from utils.time_utils import parse_time, time_to_milliseconds
                    parsed_time = parse_time(str(time_str))
                    return time_to_milliseconds(parsed_time)
                except Exception as e:
                    self.logger.error(f"解析時間失敗: {time_str}, 錯誤: {e}")
                    return None

            # 確保解析成功，使用默認值作為備選方案
            item_start_time = safe_parse_time(values[start_pos]) if len(values) > start_pos else 0
            item_end_time = safe_parse_time(values[end_pos]) if len(values) > end_pos else 10000

            # 檢查時間解析是否成功
            if item_start_time is None or item_end_time is None:
                self.logger.warning(f"時間解析失敗，使用默認值")
                item_start_time = item_start_time or 0
                item_end_time = item_end_time or 10000

            # 根據列名決定滑桿的初始值和調整的時間邊界
            if column_name == "Start":
                current_value = item_start_time
                self.is_adjusting_start = True  # 標記正在調整開始時間
            else:  # End column
                current_value = item_end_time
                self.is_adjusting_start = False  # 標記正在調整結束時間

            # 創建時間範圍標籤 - 顯示當前文本的完整時間範圍
            time_range_label = tk.Label(
                self.slider_frame,
                text=self._format_time_range(item_start_time, item_end_time),
                font=("Noto Sans TC", 10),
                bg="#1E1E1E",
                fg="#4FC3F7",
                height=1
            )
            time_range_label.place(
                x=0,
                y=PADDING,
                width=frame_width,
                height=LABEL_HEIGHT
            )

            # 如果有音頻，立即顯示音頻可視化
            if hasattr(self, 'audio_segment') and self.audio_segment:
                # 創建音頻可視化容器
                visualizer_container = tk.Frame(self.slider_frame, bg="#1E1E1E")
                visualizer_container.place(
                    x=5,
                    y=LABEL_HEIGHT + PADDING * 2,
                    width=frame_width-10,
                    height=AUDIO_HEIGHT
                )

                # 創建音頻可視化器
                self.audio_visualizer = AudioVisualizer(
                    visualizer_container,
                    width=frame_width-20,
                    height=AUDIO_HEIGHT-10
                )

                # 顯示音頻可視化
                self.audio_visualizer.show()

                # 設置音頻段落
                self.audio_visualizer.set_audio_segment(self.audio_segment)

                # 計算初始視圖範圍 - 關鍵修改：提供足夠上下文
                duration = item_end_time - item_start_time
                center_time = (item_start_time + item_end_time) / 2

                # 動態調整視圖寬度 - 較小的時間範圍需要更大的上下文
                min_width = max(2000, duration * 3)  # 至少2秒或時間範圍的3倍
                view_width = min(len(self.audio_segment), min_width)

                # 計算起止點，確保高亮區域在視圖中居中顯示
                view_start = max(0, center_time - view_width / 2)
                view_end = min(len(self.audio_segment), view_start + view_width)

                # 確保不超出邊界
                if view_end > len(self.audio_segment):
                    view_start = max(0, len(self.audio_segment) - view_width)
                    view_end = len(self.audio_segment)

                # 立即創建初始波形視圖 - 關鍵修改：確保音波視圖立即顯示
                self.audio_visualizer.create_waveform_with_selection(
                    (view_start, view_end),
                    (item_start_time, item_end_time)
                )

            # 創建滑桿容器
            slider_container = tk.Frame(
                self.slider_frame,
                bg="#1E1E1E",
                height=SLIDER_HEIGHT
            )

            # 根據是否有音頻調整滑桿位置
            if hasattr(self, 'audio_segment') and self.audio_segment:
                slider_y = LABEL_HEIGHT + AUDIO_HEIGHT + PADDING * 2
            else:
                slider_y = LABEL_HEIGHT + PADDING

            slider_container.place(
                x=5,
                y=slider_y,
                width=frame_width-10,
                height=SLIDER_HEIGHT
            )

            # 計算滑桿範圍
            min_value, max_value = self._calculate_slider_range(
                column_name, values, item_index, all_items, end_pos, start_pos, current_value
            )

            # 創建滑桿
            self.time_slider = ttk.Scale(
                slider_container,
                from_=min_value,
                to=max_value,
                orient=tk.HORIZONTAL,
                value=current_value,
                command=self.on_slider_change,
                style="TimeSlider.Horizontal.TScale"
            )
            self.time_slider.pack(fill=tk.X, expand=True, pady=5)

            # 設置滑桿狀態
            self.slider_active = True
            self.slider_target = {
                "item": item,
                "column": column_name,
                "index": values[index_pos] if len(values) > index_pos else "",
                "item_index": item_index,
                "all_items": all_items,
                "index_pos": index_pos,
                "start_pos": start_pos,
                "end_pos": end_pos,
                "item_start_time": item_start_time,  # 保存原始文本開始時間
                "item_end_time": item_end_time,      # 保存原始文本結束時間
                # 添加以下字段以便於後續更新
                "view_start": view_start if 'view_start' in locals() else 0,
                "view_end": view_end if 'view_end' in locals() else 0
            }

            # 綁定外部點擊事件
            self.parent.bind("<Button-1>", self.check_slider_focus)

            # 強制更新界面
            self.slider_frame.update_idletasks()

        except Exception as e:
            self.logger.error(f"創建滑桿時出現異常: {e}", exc_info=True)
            self.hide_slider()

    def _update_audio_visualization(self, new_value, column_name):
        """以平滑方式更新音頻視覺化"""
        if not self.audio_visualizer:
            return

        try:
            values = list(self.tree.item(self.slider_target["item"], "values"))

            if column_name == "Start":
                end_time_str = values[self.slider_target["end_pos"]]
                try:
                    end_time = time_to_milliseconds(parse_time(end_time_str))
                except:
                    end_time = new_value + 10000
                self.audio_visualizer.update_selection(new_value, end_time)
            else:  # End column
                start_time_str = values[self.slider_target["start_pos"]]
                try:
                    start_time = time_to_milliseconds(parse_time(start_time_str))
                except:
                    start_time = max(0, new_value - 10000)
                self.audio_visualizer.update_selection(start_time, new_value)
        except Exception as e:
            self.logger.error(f"更新音頻視覺化時出錯: {e}")


    def _calculate_slider_range(self, column_name, values, item_index, all_items, end_pos, start_pos, current_value=None):
        """計算滑桿範圍的私有方法"""
        min_value = 0
        max_value = 100000  # 默認最大值

        if column_name == "Start":
            # 解析終止時間
            end_time_str = values[end_pos]
            try:
                if hasattr(self.callbacks, 'parse_time') and callable(self.callbacks.parse_time):
                    end_time = self.callbacks.parse_time(end_time_str)
                else:
                    end_time = parse_time(end_time_str)
                max_value = time_to_milliseconds(end_time)
            except Exception as e:
                self.logger.error(f"解析終止時間失敗: {e}")
                # 使用當前值加上一個合理的間隔
                if current_value is not None:
                    max_value = current_value + 10000

            # 如果有上一行，則最小值是上一行的結束時間
            if item_index > 0:
                prev_item = all_items[item_index - 1]
                prev_values = self.tree.item(prev_item, "values")
                prev_end_str = prev_values[end_pos]
                try:
                    if hasattr(self.callbacks, 'parse_time') and callable(self.callbacks.parse_time):
                        prev_end_time = self.callbacks.parse_time(prev_end_str)
                    else:
                        prev_end_time = parse_time(prev_end_str)
                    min_value = time_to_milliseconds(prev_end_time)
                except Exception as e:
                    self.logger.error(f"解析上一行終止時間失敗: {e}")
        else:  # End 欄位
            # 解析開始時間
            start_time_str = values[start_pos]
            try:
                if hasattr(self.callbacks, 'parse_time') and callable(self.callbacks.parse_time):
                    start_time = self.callbacks.parse_time(start_time_str)
                else:
                    start_time = parse_time(start_time_str)
                min_value = time_to_milliseconds(start_time)
            except Exception as e:
                self.logger.error(f"解析開始時間失敗: {e}")
                # 使用當前值減去一個合理的間隔
                if current_value is not None:
                    min_value = max(0, current_value - 10000)

            # 如果有下一行，則最大值是下一行的開始時間
            if item_index < len(all_items) - 1:
                next_item = all_items[item_index + 1]
                next_values = self.tree.item(next_item, "values")
                next_start_str = next_values[start_pos]
                try:
                    if hasattr(self.callbacks, 'parse_time') and callable(self.callbacks.parse_time):
                        next_start_time = self.callbacks.parse_time(next_start_str)
                    else:
                        next_start_time = parse_time(next_start_str)
                    max_value = time_to_milliseconds(next_start_time)
                except Exception as e:
                    self.logger.error(f"解析下一行開始時間失敗: {e}")
                    # 使用當前值加上一個合理的間隔
                    if current_value is not None:
                        max_value = current_value + 10000

        return min_value, max_value

    def on_slider_change(self, value):
        """滑桿值變化時更新時間顯示和音頻可視化"""
        try:
            if not self.slider_active or not self.slider_target:
                return

            # 獲取新的時間值（毫秒）
            new_value = float(value)

            # 將毫秒轉換為 SubRipTime 對象
            from utils.time_utils import milliseconds_to_time
            new_time = milliseconds_to_time(new_value)

            # 更新樹狀視圖中的顯示
            item = self.slider_target["item"]
            column_name = self.slider_target["column"]
            values = list(self.tree.item(item, "values"))

            # 更新時間範圍
            start_time = None
            end_time = None

            if column_name == "Start":
                start_time = new_value
                end_time_str = values[self.slider_target["end_pos"]]
                try:
                    from utils.time_utils import parse_time, time_to_milliseconds
                    end_time_obj = parse_time(end_time_str)
                    end_time = time_to_milliseconds(end_time_obj)
                except:
                    end_time = new_value + 10000

                # 更新開始時間
                values[self.slider_target["start_pos"]] = str(new_time)

                # 如果有上一行，同時更新上一行的結束時間
                item_index = self.slider_target["item_index"]
                if item_index > 0:
                    prev_item = self.slider_target["all_items"][item_index - 1]
                    prev_values = list(self.tree.item(prev_item, "values"))
                    prev_values[self.slider_target["end_pos"]] = str(new_time)
                    self.tree.item(prev_item, values=tuple(prev_values))

            else:  # End column
                end_time = new_value
                start_time_str = values[self.slider_target["start_pos"]]
                try:
                    from utils.time_utils import parse_time, time_to_milliseconds
                    start_time_obj = parse_time(start_time_str)
                    start_time = time_to_milliseconds(start_time_obj)
                except:
                    start_time = max(0, new_value - 10000)

                # 更新結束時間
                values[self.slider_target["end_pos"]] = str(new_time)

                # 如果有下一行，同時更新下一行的開始時間
                item_index = self.slider_target["item_index"]
                if item_index < len(self.slider_target["all_items"]) - 1:
                    next_item = self.slider_target["all_items"][item_index + 1]
                    next_values = list(self.tree.item(next_item, "values"))
                    next_values[self.slider_target["start_pos"]] = str(new_time)
                    self.tree.item(next_item, values=tuple(next_values))

            # 更新當前項目的值
            self.tree.item(item, values=tuple(values))

            # 更新時間範圍標籤
            for widget in self.slider_frame.winfo_children():
                if isinstance(widget, tk.Label) and widget.cget('fg') == "#4FC3F7":
                    widget.config(text=self._format_time_range(start_time, end_time))
                    break

            # 更新音頻可視化 - 關鍵修改：根據調整的是開始時間還是結束時間來不同處理視圖縮放
            if hasattr(self, 'audio_visualizer') and self.audio_visualizer and hasattr(self, 'audio_segment') and self.audio_segment:
                if start_time is not None and end_time is not None:
                    duration = end_time - start_time
                    center_time = (start_time + end_time) / 2

                    # 根據是調整開始還是結束時間來決定視圖縮放方向
                    if self.is_adjusting_start:
                        # 調整開始時間時，保持原視圖右邊界不變，左邊界根據需要調整
                        current_view_start, current_view_end = self.slider_target.get("view_start", 0), self.slider_target.get("view_end", 0)
                        view_width = current_view_end - current_view_start

                        # 如果當前視圖不夠大，擴大視圖
                        min_width = max(duration * 3, 2000)
                        if view_width < min_width:
                            view_width = min_width

                        # 調整視圖邊界，保持右邊界，確保高亮區域在合適位置
                        new_view_start = max(0, center_time - view_width / 2)
                        new_view_end = min(len(self.audio_segment), new_view_start + view_width)

                        # 如果超出範圍，調整視圖
                        if new_view_end > len(self.audio_segment):
                            new_view_start = max(0, len(self.audio_segment) - view_width)
                            new_view_end = len(self.audio_segment)
                    else:
                        # 調整結束時間時，保持原視圖左邊界不變，右邊界根據需要調整
                        current_view_start, current_view_end = self.slider_target.get("view_start", 0), self.slider_target.get("view_end", 0)
                        view_width = current_view_end - current_view_start

                        # 如果當前視圖不夠大，擴大視圖
                        min_width = max(duration * 3, 2000)
                        if view_width < min_width:
                            view_width = min_width

                        # 調整視圖邊界，保持左邊界，確保高亮區域在合適位置
                        new_view_end = min(len(self.audio_segment), center_time + view_width / 2)
                        new_view_start = max(0, new_view_end - view_width)

                        # 如果超出範圍，調整視圖
                        if new_view_start < 0:
                            new_view_start = 0
                            new_view_end = min(len(self.audio_segment), view_width)

                    # 更新滑桿目標中的視圖範圍
                    self.slider_target["view_start"] = new_view_start
                    self.slider_target["view_end"] = new_view_end

                    # 更新波形視圖
                    self.audio_visualizer.update_waveform_and_selection(
                        (new_view_start, new_view_end),
                        (start_time, end_time)
                    )

            # 強制更新界面確保即時顯示
            self.tree.update()
            if hasattr(self, 'slider_frame') and self.slider_frame:
                self.slider_frame.update()

        except Exception as e:
            self.logger.error(f"滑桿值變化處理時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _format_time_range(self, start_time, end_time):
        """格式化並顯示時間範圍"""
        start_sec = int(start_time / 1000)
        start_ms = int(start_time % 1000)
        end_sec = int(end_time / 1000)
        end_ms = int(end_time % 1000)
        return f"{start_sec}:{start_ms:03d} → {end_sec}:{end_ms:03d}"

    def _format_time_display(self, milliseconds):
        """格式化毫秒為友好的時間顯示 (秒:毫秒)"""
        seconds = int(milliseconds / 1000)
        ms = int(milliseconds % 1000)
        return f"{seconds}:{ms:03d}"

    def _update_slider_audio_view(self, start_time, end_time):
        """更新音頻視圖顯示，確保正確顯示所有文本的時間範圍"""
        try:
            # 確保音頻段落和可視化器存在
            if not self.audio_segment or not self.audio_visualizer:
                return

            # 計算視圖範圍，保持選擇區域在中間
            duration = end_time - start_time
            center_time = (start_time + end_time) / 2

            # 動態調整視圖寬度，確保合適的上下文
            view_width = max(duration * 3, 2000)  # 至少顯示2秒或時間範圍的3倍
            display_start = max(0, center_time - view_width / 2)
            display_end = min(len(self.audio_segment), center_time + view_width / 2)

            # 確保視圖範圍足夠寬
            if display_end - display_start < 1000:  # 至少顯示1秒
                if display_start == 0:
                    display_end = min(len(self.audio_segment), 1000)
                else:
                    display_start = max(0, display_end - 1000)

            # 更新波形和選擇區域
            self.audio_visualizer.update_waveform_and_selection(
                (display_start, display_end),
                (start_time, end_time)
            )

        except Exception as e:
            self.logger.error(f"更新音頻視圖時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _update_time_range_label(self, start_time, end_time):
        """顯示時間範圍標籤（無論是否有音頻）"""
        try:
            # 格式化時間
            start_sec = int(start_time / 1000)
            start_ms = int(start_time % 1000)
            end_sec = int(end_time / 1000)
            end_ms = int(end_time % 1000)
            time_range = f"{start_sec}:{start_ms:03d} → {end_sec}:{end_ms:03d}"

            # 創建或更新時間範圍標籤
            if not hasattr(self, 'range_label') or self.range_label is None:
                self.range_label = tk.Label(
                    self.slider_frame,
                    text=time_range,
                    font=("Noto Sans TC", 10),
                    bg="#1E1E1E",
                    fg="#4FC3F7"
                )
                # 計算位置：在滑桿下方
                y_pos = 25
                if hasattr(self, 'audio_visualizer') and self.audio_visualizer:
                    y_pos = 75  # 音頻可視化下方
                self.range_label.place(x=5, y=y_pos)
            else:
                self.range_label.config(text=time_range)

            # 強制刷新顯示
            if hasattr(self, 'slider_frame'):
                self.slider_frame.update_idletasks()
        except Exception as e:
            self.logger.error(f"更新時間範圍標籤時出錯: {e}")

    def check_slider_focus(self, event):
        """
        檢查點擊是否在滑桿外部，如果是則隱藏滑桿
        :param event: 事件對象
        """
        try:
            if not self.slider_active or not self.slider_frame:
                return

            # 獲取點擊位置相對於樹狀視圖的區域
            region = self.tree.identify_region(event.x, event.y)
            column = self.tree.identify_column(event.x)
            item = self.tree.identify_row(event.y)

            # 如果點擊在時間欄位（Start 或 End），允許切換滑桿，不隱藏
            if region == "cell" and column:
                column_idx = int(column[1:]) - 1
                if column_idx < len(self.tree["columns"]):
                    column_name = self.tree["columns"][column_idx]
                    if column_name in ["Start", "End"]:
                        # 不隱藏滑桿，讓 on_tree_click 處理新滑桿的顯示
                        return

            # 獲取滑桿框架的位置
            slider_x = self.slider_frame.winfo_rootx()
            slider_y = self.slider_frame.winfo_rooty()
            slider_width = self.slider_frame.winfo_width()
            slider_height = self.slider_frame.winfo_height()

            # 檢查點擊是否在滑桿區域外
            if (event.x_root < slider_x or event.x_root > slider_x + slider_width or
                event.y_root < slider_y or event.y_root > slider_y + slider_height):
                # 應用變更並隱藏滑桿
                self.apply_time_change()
                self.hide_slider()
        except Exception as e:
            self.logger.error(f"檢查滑桿焦點時出錯: {e}")
            self.hide_slider()

    def apply_time_change(self):
        """應用時間變更並同步音頻段落"""
        if not self.slider_active:
            return

        try:
            # 如果沒有活動的滑桿，直接返回
            if not self.slider_active:
                return

            # 安全地獲取滑桿值
            current_value = 0
            if hasattr(self, 'time_slider') and self.time_slider is not None:
                try:
                    current_value = self.time_slider.get()
                except Exception:
                    # 如果獲取值失敗，使用預設值
                    current_value = 0

            # 記錄相關信息
            item = self.slider_target.get("item") if hasattr(self, 'slider_target') else None
            column = self.slider_target.get("column") if hasattr(self, 'slider_target') else None

            # 調用回調函數更新 SRT 和音頻
            if hasattr(self.callbacks, 'on_time_change') and callable(self.callbacks.on_time_change):
                self.callbacks.on_time_change()

        except Exception as e:
            self.logger.error(f"應用時間變更時出錯: {e}")

    def hide_slider(self):
        """隱藏時間調整滑桿，並確保音頻段落同步更新"""
        # 避免遞歸調用
        if hasattr(self, '_hide_time_slider_in_progress') and self._hide_time_slider_in_progress:
            return

        try:
            self._hide_time_slider_in_progress = True

            # 在隱藏滑桿前，確保時間變更已應用
            if self.slider_active and hasattr(self, 'time_slider'):
                # 應用時間變更
                self.apply_time_change()

            # 清理時間標籤
            if hasattr(self, 'time_label') and self.time_label:
                try:
                    self.time_label.destroy()
                except tk.TclError:
                    pass
                self.time_label = None

            # 清理時間範圍標籤
            if hasattr(self, 'range_label') and self.range_label:
                try:
                    self.range_label.destroy()
                except tk.TclError:
                    pass
                self.range_label = None

            # 清理音頻可視化
            if hasattr(self, 'audio_visualizer') and self.audio_visualizer:
                try:
                    if self.audio_visualizer.canvas and self.audio_visualizer.canvas.winfo_exists():
                        self.audio_visualizer.clear_waveform()
                except tk.TclError:
                    # 控件可能已經被銷毀
                    pass
                self.audio_visualizer = None

            # 清理滑桿界面
            if hasattr(self, 'slider_frame') and self.slider_frame:
                try:
                    if self.slider_frame.winfo_exists():
                        self.slider_frame.place_forget()
                        self.slider_frame.destroy()
                except tk.TclError:
                    # 控件可能已經被銷毀
                    pass
                self.slider_frame = None

            if hasattr(self, 'time_slider') and self.time_slider:
                self.time_slider = None

            self.slider_active = False
            self.slider_target = None

            # 解除綁定（使用更安全的方法）
            try:
                # 檢查父組件是否存在且是否有綁定
                if self.parent and hasattr(self.parent, 'bind'):
                    self.parent.unbind("<Button-1>")
            except Exception as e:
                self.logger.debug(f"解除綁定時出錯: {e}")

        except Exception as e:
            self.logger.error(f"隱藏滑桿時出錯: {e}")
        finally:
            self._hide_time_slider_in_progress = False