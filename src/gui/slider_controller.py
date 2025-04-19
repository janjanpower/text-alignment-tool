"""時間軸滑桿控制器模組"""

import logging
import tkinter as tk
from tkinter import ttk
from typing import Dict, Callable, Any, Optional

from utils.time_utils import parse_time, milliseconds_to_time, time_to_milliseconds
from audio.audio_visualizer import AudioVisualizer
import pysrt


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
                        thickness=10,          # 軌道厚度
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

            # 創建滑桿控件
            self._create_slider(
                x, y, width, height,
                item, column_name,
                values, item_index, all_items,
                index_pos, start_pos, end_pos
            )
        except Exception as e:
            self.logger.error(f"顯示滑桿時出錯: {e}")

    def set_audio_segment(self, audio_segment):
            """設置要可視化的音頻段落"""
            self.audio_segment = audio_segment

    def _create_slider(self, x, y, width, height, item, column_name, values,
                  item_index, all_items, index_pos, start_pos, end_pos):
        """創建時間調整滑桿"""
        try:
            # 如果已有滑桿，先清除
            self.hide_slider()

            # 創建滑桿框架
            self.slider_frame = tk.Frame(self.tree, bg="#1E1E1E", bd=0, relief="flat")

            # 根據是否有音頻決定框架高度
            frame_height = height + 4  # 基本高度
            if self.audio_segment:
                frame_height += 50  # 額外的高度給音頻可視化

            self.slider_frame.place(x=x + width, y=y, width=100, height=frame_height)

            # 創建一個容器添加內邊距
            container = tk.Frame(self.slider_frame, bg="#1E1E1E", bd=0)
            container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

            # 如果有音頻段落，創建音頻可視化
            if self.audio_segment:
                try:
                    self.audio_visualizer = AudioVisualizer(container, width=92, height=40)
                    self.audio_visualizer.create_waveform(self.audio_segment)
                    self.audio_visualizer.show()
                except Exception as e:
                    self.logger.error(f"創建音頻可視化時出錯: {e}")
                    self.audio_visualizer = None
            else:
                self.audio_visualizer = None

            # 獲取當前時間值
            current_time_str = values[start_pos if column_name == "Start" else end_pos]
            current_time = None

            # 解析時間
            try:
                if hasattr(self.callbacks, 'parse_time') and callable(self.callbacks.parse_time):
                    current_time = self.callbacks.parse_time(current_time_str)
                if not current_time:
                    current_time = parse_time(current_time_str)
            except Exception as e:
                self.logger.error(f"解析時間值失敗: {e}")
                self.hide_slider()
                return

            if not current_time:
                self.logger.error("無法獲取或解析當前時間值")
                self.hide_slider()
                return

            # 計算滑桿範圍
            min_value, max_value = self._calculate_slider_range(
                column_name, values, item_index, all_items, end_pos, start_pos
            )

            # 當前值
            current_value = time_to_milliseconds(current_time)

            # 初始化音頻可視化的選擇區域
            if self.audio_visualizer:
                if column_name == "Start":
                    start_time = current_value
                    end_time_str = values[end_pos]
                    try:
                        end_time = time_to_milliseconds(parse_time(end_time_str))
                    except:
                        end_time = max_value
                else:  # End column
                    start_time_str = values[start_pos]
                    try:
                        start_time = time_to_milliseconds(parse_time(start_time_str))
                    except:
                        start_time = min_value
                    end_time = current_value

                self.audio_visualizer.update_selection(start_time, end_time)

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

            # 創建滑桿
            self.time_slider = ttk.Scale(
                container,
                from_=min_value,
                to=max_value,
                orient=tk.HORIZONTAL,
                value=current_value,
                command=self.on_slider_change,
                style="TimeSlider.Horizontal.TScale"
            )

            # 調整滑桿位置
            if self.audio_visualizer:
                self.time_slider.pack(fill=tk.X, expand=True, pady=(5, 0))
            else:
                self.time_slider.pack(fill=tk.BOTH, expand=True)  # 無音頻時完全填充

            # 添加頂部和底部分隔線模擬陰影效果
            top_line = tk.Frame(self.slider_frame, bg="#4FC3F7", height=1)
            top_line.place(x=0, y=0, relwidth=1)

            bottom_line = tk.Frame(self.slider_frame, bg="#0D1F32", height=1)
            bottom_line.place(x=0, rely=1, relwidth=1)

            # 綁定事件，點擊其他區域時隱藏滑桿
            self.parent.bind("<Button-1>", self.check_slider_focus)
        except Exception as e:
            self.logger.error(f"創建滑桿時出錯: {e}")
            self.hide_slider()

    def _calculate_slider_range(self, column_name, values, item_index, all_items, end_pos, start_pos):
        """計算滑桿範圍的私有方法"""
        # 這個方法從原來的 _create_slider 中提取出來，方便維護
        # 內容與原來相同
        if column_name == "Start":
            min_value = 0

            # 解析終止時間
            end_time_str = values[end_pos]
            end_time = None
            try:
                # 首先嘗試使用 callback
                if hasattr(self.callbacks, 'parse_time') and callable(self.callbacks.parse_time):
                    end_time = self.callbacks.parse_time(end_time_str)

                # 如果失敗，直接使用導入的函數
                if not end_time:
                    end_time = parse_time(end_time_str)

                max_value = time_to_milliseconds(end_time)
            except Exception as e:
                self.logger.error(f"解析終止時間失敗: {e}")
                # 設置默認值，避免中斷
                max_value = time_to_milliseconds(current_time) + 10000  # 默認增加10秒

            # 如果有上一行，則最小值是上一行的結束時間
            if item_index > 0:
                prev_item = all_items[item_index - 1]
                prev_values = self.tree.item(prev_item, "values")
                prev_end_str = prev_values[end_pos]
                try:
                    # 首先嘗試使用 callback
                    prev_end_time = None
                    if hasattr(self.callbacks, 'parse_time') and callable(self.callbacks.parse_time):
                        prev_end_time = self.callbacks.parse_time(prev_end_str)

                    # 如果失敗，直接使用導入的函數
                    if not prev_end_time:
                        prev_end_time = parse_time(prev_end_str)

                    min_value = time_to_milliseconds(prev_end_time)
                except Exception as e:
                    self.logger.error(f"解析上一行終止時間失敗: {e}")
                    # 保持默認值
        else:  # End 欄位
            # 解析開始時間
            start_time_str = values[start_pos]
            start_time = None
            try:
                # 首先嘗試使用 callback
                if hasattr(self.callbacks, 'parse_time') and callable(self.callbacks.parse_time):
                    start_time = self.callbacks.parse_time(start_time_str)

                # 如果失敗，直接使用導入的函數
                if not start_time:
                    start_time = parse_time(start_time_str)

                min_value = time_to_milliseconds(start_time)
            except Exception as e:
                self.logger.error(f"解析開始時間失敗: {e}")
                # 設置默認值
                min_value = time_to_milliseconds(current_time) - 10000  # 默認減少10秒
                if min_value < 0:
                    min_value = 0

            max_value = min_value + 10000  # 增加10秒

            # 如果有下一行，則最大值是下一行的開始時間
            if item_index < len(all_items) - 1:
                next_item = all_items[item_index + 1]
                next_values = self.tree.item(next_item, "values")
                next_start_str = next_values[start_pos]
                try:
                    # 首先嘗試使用 callback
                    next_start_time = None
                    if hasattr(self.callbacks, 'parse_time') and callable(self.callbacks.parse_time):
                        next_start_time = self.callbacks.parse_time(next_start_str)

                    # 如果失敗，直接使用導入的函數
                    if not next_start_time:
                        next_start_time = parse_time(next_start_str)

                    max_value = time_to_milliseconds(next_start_time)
                except Exception as e:
                    self.logger.error(f"解析下一行開始時間失敗: {e}")
                    # 保持默認值

        return min_value, max_value

    def on_slider_change(self, value):
        """
        滑桿值變化時更新時間顯示
        :param value: 滑桿值
        """
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

            # 更新音頻可視化的選擇區域
            if self.audio_visualizer:
                if column_name == "Start":
                    end_time_str = values[self.slider_target["end_pos"]]
                    try:
                        end_time = time_to_milliseconds(parse_time(end_time_str))
                    except:
                        end_time = new_value + 10000  # default to 10 seconds after start
                    self.audio_visualizer.update_selection(new_value, end_time)
                else:  # End column
                    start_time_str = values[self.slider_target["start_pos"]]
                    try:
                        start_time = time_to_milliseconds(parse_time(start_time_str))
                    except:
                        start_time = max(0, new_value - 10000)  # default to 10 seconds before end
                    self.audio_visualizer.update_selection(start_time, new_value)

            # 更新相應的值
            if column_name == "Start":
                values[self.slider_target["start_pos"]] = str(new_time)

                # 如果有上一行，同時更新上一行的結束時間
                item_index = self.slider_target["item_index"]
                if item_index > 0:
                    prev_item = self.slider_target["all_items"][item_index - 1]
                    prev_values = list(self.tree.item(prev_item, "values"))
                    prev_values[self.slider_target["end_pos"]] = str(new_time)
                    self.tree.item(prev_item, values=tuple(prev_values))
            else:  # End 欄位
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
        except Exception as e:
            self.logger.error(f"滑桿值變化處理時出錯: {e}")


    def check_slider_focus(self, event):
        """
        檢查點擊是否在滑桿外部，如果是則隱藏滑桿
        :param event: 事件對象
        """
        try:
            if not self.slider_active or not self.slider_frame:
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