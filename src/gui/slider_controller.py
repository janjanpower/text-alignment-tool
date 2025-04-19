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
                    troughcolor=[("active", "#333333")],
                    sliderthickness=[("active", 12)],  # 活動時略微增大
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
        顯示時間調整滑桿
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

            # 確保音頻段落已設置
            if not self.audio_segment:
                self.logger.warning("音頻段落未設置，無法顯示音頻視圖")
                # 即使沒有音頻，也繼續創建滑桿

            # 創建滑桿控件
            self._create_slider(
                x, y, width, height,
                item, column_name,
                values, item_index, all_items,
                index_pos, start_pos, end_pos
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
        """創建時間調整滑桿，音頻可視化顯示選取區域前後1秒"""
        try:
            # 如果已有滑桿，先清除
            self.hide_slider()

            # 固定高度設置
            LABEL_HEIGHT = 20  # 時間標籤固定高度
            AUDIO_HEIGHT = 60  # 音波視圖固定高度
            SLIDER_HEIGHT = 50  # 滑桿固定高度
            PADDING = 5  # 組件間距

            # 計算總高度
            total_height = LABEL_HEIGHT + PADDING
            if self.audio_segment:
                total_height += AUDIO_HEIGHT + PADDING
            total_height += SLIDER_HEIGHT + PADDING

            # 創建滑桿框架
            self.slider_frame = tk.Frame(self.tree, bg="#1E1E1E", bd=0, relief="flat")
            frame_width = 200  # 固定寬度

            # 確保在有效範圍內放置滑桿框架
            tree_width = self.tree.winfo_width()
            tree_height = self.tree.winfo_height()

            # 調整位置以確保框架在樹狀視圖內部
            place_x = min(max(0, x + width), tree_width - frame_width)
            place_y = min(max(0, y + height + 5), tree_height - total_height)

            # 解析當前時間值
            current_time_str = values[start_pos if column_name == "Start" else end_pos]
            try:
                current_time = self.callbacks.parse_time(current_time_str) if hasattr(self.callbacks, 'parse_time') else parse_time(current_time_str)
                current_value = time_to_milliseconds(current_time)
            except Exception as e:
                self.logger.error(f"解析時間值失敗: {e}")
                self.hide_slider()
                return

            # 計算開始和結束時間
            if column_name == "Start":
                start_time = current_value
                end_time_str = values[end_pos]
                try:
                    end_time_obj = parse_time(end_time_str)
                    end_time = time_to_milliseconds(end_time_obj)
                except Exception as e:
                    self.logger.error(f"解析結束時間失敗: {e}")
                    end_time = start_time + 10000
            else:  # End column
                end_time = current_value
                start_time_str = values[start_pos]
                try:
                    start_time_obj = parse_time(start_time_str)
                    start_time = time_to_milliseconds(start_time_obj)
                except Exception as e:
                    self.logger.error(f"解析開始時間失敗: {e}")
                    start_time = max(0, end_time - 10000)

            # 計算滑桿範圍
            min_value, max_value = self._calculate_slider_range(
                column_name, values, item_index, all_items, end_pos, start_pos, current_value
            )

            # 放置滑桿框架
            self.slider_frame.place(
                x=place_x,
                y=place_y,
                width=frame_width,
                height=total_height
            )

            # 創建時間範圍標籤（固定高度和位置）
            time_range_label = tk.Label(
                self.slider_frame,
                text=self._format_time_range(start_time, end_time),
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

            # 累計 y 位置
            current_y = PADDING + LABEL_HEIGHT + PADDING

            # 設置音頻可視化（如果有音頻）
            if self.audio_segment:
                try:
                    self.logger.debug("===== 開始創建音頻可視化 =====")
                    self.logger.debug(f"音頻段落長度: {len(self.audio_segment)} ms")

                    # 創建音頻可視化容器
                    visualizer_container = tk.Frame(self.slider_frame, bg="#1E1E1E")
                    visualizer_container.place(
                        x=5,
                        y=current_y,
                        width=frame_width-10,
                        height=AUDIO_HEIGHT
                    )
                    visualizer_container.update_idletasks()

                    self.logger.debug(f"可視化容器創建完成: visible={visualizer_container.winfo_viewable()}")
                    self.logger.debug(f"容器尺寸: {visualizer_container.winfo_width()}x{visualizer_container.winfo_height()}")

                    # 創建音頻可視化器
                    self.audio_visualizer = AudioVisualizer(
                        visualizer_container,
                        width=frame_width-20,
                        height=AUDIO_HEIGHT-10
                    )

                    self.logger.debug("音頻可視化器已創建")

                    # 確保可視化器立即顯示
                    self.audio_visualizer.show()

                    # 更新一次界面確保容器正確初始化
                    self.slider_frame.update()
                    visualizer_container.update()

                    # 計算顯示的音頻範圍（前後各加1秒）
                    display_start = max(0, min(start_time, end_time) - 1000)  # 前1秒
                    display_end = max(start_time, end_time) + 1000  # 後1秒

                    # 確保不超過音頻總長度
                    total_duration = len(self.audio_segment)
                    display_end = min(display_end, total_duration)

                    self.logger.debug(f"顯示範圍: {display_start}ms - {display_end}ms, 總長度: {total_duration}ms")

                    # 提取指定範圍的音頻段落
                    if display_end > display_start:
                        # 提取指定範圍的音頻段落
                        segment_start = max(0, display_start)
                        segment_end = min(total_duration, display_end)

                        if segment_end > segment_start:
                            extended_segment = self.audio_segment[segment_start:segment_end]
                            self.logger.debug(f"準備創建波形 - 段落長度: {len(extended_segment)} ms")

                            # 創建波形
                            self.audio_visualizer.create_waveform(extended_segment)

                            # 確保顯示
                            self.audio_visualizer.show()

                            # 設置高亮區域
                            highlight_start = start_time - display_start
                            highlight_end = end_time - display_start
                            self.audio_visualizer.update_selection(highlight_start, highlight_end)

                            # 強制更新所有組件
                            self.slider_frame.update()
                            visualizer_container.update()
                            if self.audio_visualizer.canvas:
                                self.audio_visualizer.canvas.update()

                            self.logger.debug("音頻可視化創建完成")
                            self.logger.debug(f"最終狀態檢查 - 畫布可見: {self.audio_visualizer.canvas.winfo_viewable()}")
                            self.logger.debug(f"畫布尺寸: {self.audio_visualizer.canvas.winfo_width()}x{self.audio_visualizer.canvas.winfo_height()}")
                        else:
                            self.logger.error(f"無效的音頻範圍: {segment_start}ms - {segment_end}ms")
                    else:
                        self.logger.error(f"無效的顯示範圍: {display_start}ms - {display_end}ms")

                    current_y += AUDIO_HEIGHT + PADDING

                except Exception as e:
                    self.logger.error(f"創建音頻可視化時出錯: {e}")
                    self.logger.exception(e)
                    self.audio_visualizer = None

            # 設置滑桿狀態
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

            # 創建滑桿（固定高度和位置）
            slider_container = tk.Frame(self.slider_frame, bg="#1E1E1E", height=SLIDER_HEIGHT)
            slider_container.place(
                x=5,
                y=current_y,
                width=frame_width-10,
                height=SLIDER_HEIGHT
            )

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

            # 綁定事件，點擊其他區域時隱藏滑桿
            self.parent.bind("<Button-1>", self.check_slider_focus)

            # 確保整個滑桿框架可見
            self.slider_frame.lift()  # 將框架提升到最前
            self.slider_frame.update_idletasks()

            # 強制更新界面確保即時顯示
            self.parent.update()

        except Exception as e:
            self.logger.error(f"創建滑桿時出錯: {e}")
            self.logger.exception(e)
            self.hide_slider()

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

            # 更新音頻可視化高亮區域
            if hasattr(self, 'audio_visualizer') and self.audio_visualizer and hasattr(self, 'current_display_range'):
                # 暫停自動更新以防止閃爍
                self.parent.update_idletasks()

                # 計算高亮區域在擴展視圖中的相對位置
                highlight_start = int(start_time - display_start)
                highlight_end = int(end_time - display_start)

                # 確保高亮區域在合理範圍內
                if highlight_start < 0:
                    self.logger.debug(f"調整高亮開始位置從 {highlight_start} 到 0")
                    highlight_start = 0

                if highlight_end < 0:
                    self.logger.debug(f"調整高亮結束位置從 {highlight_end} 到 0")
                    highlight_end = 0

                # 如果音頻段落存在，檢查是否超出範圍
                if self.audio_segment:
                    segment_duration = len(self.audio_segment)
                    if highlight_start > segment_duration:
                        highlight_start = segment_duration
                    if highlight_end > segment_duration:
                        highlight_end = segment_duration

                # 更新高亮區域
                self.audio_visualizer.update_selection(highlight_start, highlight_end)

                # 確保可視化器保持可見
                if self.audio_visualizer.canvas:
                    self.audio_visualizer.canvas.lift()

            # 強制更新界面確保即時顯示
            self.tree.update_idletasks()
            if hasattr(self, 'slider_frame'):
                self.slider_frame.update_idletasks()

        except Exception as e:
            self.logger.error(f"滑桿值變化處理時出錯: {e}")

    def _format_time_range(self, start_time, end_time):
        """格式化並顯示時間範圍"""
        start_sec = int(start_time / 1000)
        start_ms = int(start_time % 1000)
        end_sec = int(end_time / 1000)
        end_ms = int(end_time % 1000)
        return f"{start_sec}:{start_ms:03d} → {end_sec}:{end_ms:03d}"


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
            # 獲取當前滑桿值
            current_value = self.time_slider.get() if hasattr(self, 'time_slider') else 0

            # 記錄相關信息，用於日誌
            item = self.slider_target["item"] if self.slider_target else None
            column = self.slider_target["column"] if self.slider_target else None
            self.logger.debug(f"應用時間變更: 項目={item}, 列={column}, 值={current_value}")

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