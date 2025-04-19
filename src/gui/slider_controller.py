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
        self.current_display_range = (0, 0)

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
        try:
            if audio_segment is not None and len(audio_segment) > 0:
                self.audio_segment = audio_segment
                self.logger.debug(f"設置音頻段落，長度: {len(audio_segment)} ms")
            else:
                self.audio_segment = None
                self.logger.warning("設置的音頻段落為空或無效")
        except Exception as e:
            self.logger.error(f"設置音頻段落時出錯: {e}")
            self.audio_segment = None

    def _create_slider(self, x, y, width, height, item, column_name, values,
                      item_index, all_items, index_pos, start_pos, end_pos):
        """完全重構的時間調整滑桿創建方法"""
        try:
            # 清除現有滑桿
            self.hide_slider()

            # 確保有足夠的數據進行處理
            if not values or len(values) <= max(start_pos, end_pos):
                self.logger.error(f"項目值不足: {values}")
                return

            # === 常數定義 ===
            FRAME_WIDTH = 200  # 框架寬度
            LABEL_HEIGHT = 20  # 時間標籤高度
            AUDIO_HEIGHT = 60  # 音頻視圖高度
            SLIDER_HEIGHT = 50  # 滑桿高度
            PADDING = 5  # 內邊距

            # === 1. 解析時間值 ===
            try:
                # 獲取當前時間
                current_time_str = values[start_pos if column_name == "Start" else end_pos]
                current_time = self.callbacks.parse_time(current_time_str) if hasattr(self.callbacks, 'parse_time') else parse_time(current_time_str)
                current_value = time_to_milliseconds(current_time)

                # 計算對應的開始和結束時間
                if column_name == "Start":
                    start_time = current_value
                    end_time_str = values[end_pos]
                    try:
                        end_time = time_to_milliseconds(parse_time(end_time_str))
                    except:
                        end_time = start_time + 10000
                else:  # End column
                    end_time = current_value
                    start_time_str = values[start_pos]
                    try:
                        start_time = time_to_milliseconds(parse_time(start_time_str))
                    except:
                        start_time = max(0, end_time - 10000)
            except Exception as e:
                self.logger.error(f"解析時間值失敗: {e}")
                return

            # === 2. 計算滑桿範圍 ===
            min_value, max_value = self._calculate_slider_range(
                column_name, values, item_index, all_items, end_pos, start_pos, current_value
            )

            # === 3. 計算總高度 ===
            total_height = LABEL_HEIGHT + PADDING  # 時間標籤高度
            if self.audio_segment:
                total_height += AUDIO_HEIGHT + PADDING  # 音頻視圖高度
            total_height += SLIDER_HEIGHT + PADDING  # 滑桿高度

            # === 4. 創建主框架 ===
            # 創建一個新的頂層窗口作為滑桿容器，避免佈局問題
            self.slider_frame = tk.Toplevel(self.parent)
            self.slider_frame.overrideredirect(True)  # 無邊框
            self.slider_frame.configure(bg="#1E1E1E")

            # 計算位置 - 確保在屏幕範圍內
            frame_x = self.tree.winfo_rootx() + x + width
            frame_y = self.tree.winfo_rooty() + y + height + 5

            # 設置位置和尺寸
            self.slider_frame.geometry(f"{FRAME_WIDTH}x{total_height}+{frame_x}+{frame_y}")

            # 強制更新確保位置正確
            self.slider_frame.update_idletasks()

            # === 5. 創建時間標籤 ===
            time_label = tk.Label(
                self.slider_frame,
                text=self._format_time_range(start_time, end_time),
                font=("Noto Sans TC", 10),
                bg="#1E1E1E",
                fg="#4FC3F7"
            )
            time_label.pack(pady=PADDING)

            # === 6. 創建音頻視圖（如果有音頻） ===
            current_y = LABEL_HEIGHT + PADDING

            if self.audio_segment:
                try:
                    # 創建容器
                    audio_frame = tk.Frame(
                        self.slider_frame,
                        bg="#1E1E1E",
                        width=FRAME_WIDTH-10,
                        height=AUDIO_HEIGHT
                    )
                    audio_frame.pack(pady=PADDING)
                    audio_frame.pack_propagate(False)  # 固定尺寸

                    # 更新確保框架已創建
                    audio_frame.update_idletasks()

                    # 創建可視化器
                    self.audio_visualizer = AudioVisualizer(
                        audio_frame,
                        width=FRAME_WIDTH-10,
                        height=AUDIO_HEIGHT
                    )

                    # 使用pack佈局，確保填滿容器
                    self.audio_visualizer.pack(fill=tk.BOTH, expand=True)

                    # 強制更新以確保尺寸正確
                    audio_frame.update_idletasks()

                    # 計算顯示範圍
                    display_start = max(0, min(start_time, end_time) - 1000)  # 前1秒
                    display_end = max(start_time, end_time) + 1000  # 後1秒

                    # 如果有音頻段落，創建波形
                    if self.audio_segment and len(self.audio_segment) > 0:
                        # 確保範圍在音頻長度內
                        total_duration = len(self.audio_segment)
                        display_end = min(display_end, total_duration)

                        if display_end > display_start:
                            # 提取指定範圍的音頻
                            extended_segment = self.audio_segment[display_start:display_end]

                            # 創建波形
                            self.audio_visualizer.create_waveform(extended_segment)

                            # 計算選擇區域位置
                            highlight_start = max(0, start_time - display_start)
                            highlight_end = max(highlight_start, end_time - display_start)

                            # 更新選擇區域
                            self.audio_visualizer.update_selection(highlight_start, highlight_end)

                            # 保存顯示範圍
                            self.current_display_range = (display_start, display_end)

                    current_y += AUDIO_HEIGHT + PADDING

                except Exception as e:
                    self.logger.error(f"創建音頻視圖時出錯: {e}", exc_info=True)
                    self.audio_visualizer = None

            # === 7. 創建滑桿 ===
            slider_frame = tk.Frame(self.slider_frame, bg="#1E1E1E")
            slider_frame.pack(fill=tk.X, padx=5, pady=PADDING)

            self.time_slider = ttk.Scale(
                slider_frame,
                from_=min_value,
                to=max_value,
                orient=tk.HORIZONTAL,
                value=current_value,
                command=self.on_slider_change,
                style="TimeSlider.Horizontal.TScale"
            )
            self.time_slider.pack(fill=tk.X, expand=True)

            # === 8. 設置狀態變數 ===
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

            # === 9. 綁定事件 ===
            # 綁定事件，點擊其他區域時隱藏滑桿
            self.parent.bind("<Button-1>", self.check_slider_focus)

            # 在窗口中綁定鍵盤事件，按ESC關閉
            self.slider_frame.bind("<Escape>", lambda e: self.hide_slider())

        except Exception as e:
            self.logger.error(f"創建滑桿時出錯: {e}", exc_info=True)
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
        """滑桿值變化處理 - 修改版"""
        try:
            if not self.slider_active or not self.slider_target:
                return

            # 獲取新值（毫秒）
            new_value = float(value)

            # 轉換為時間對象
            new_time = milliseconds_to_time(new_value)

            # 獲取目標項和欄位
            item = self.slider_target["item"]
            column_name = self.slider_target["column"]

            # 獲取項目當前值
            values = list(self.tree.item(item, "values"))

            # 計算時間範圍
            if column_name == "Start":
                # 更新開始時間
                start_time = new_value
                values[self.slider_target["start_pos"]] = str(new_time)

                # 獲取結束時間
                try:
                    end_time_str = values[self.slider_target["end_pos"]]
                    end_time = time_to_milliseconds(parse_time(end_time_str))
                except:
                    end_time = start_time + 10000

                # 同時更新上一項的結束時間
                item_index = self.slider_target["item_index"]
                if item_index > 0:
                    prev_item = self.slider_target["all_items"][item_index - 1]
                    prev_values = list(self.tree.item(prev_item, "values"))
                    prev_values[self.slider_target["end_pos"]] = str(new_time)
                    self.tree.item(prev_item, values=tuple(prev_values))

            else:  # End column
                # 更新結束時間
                end_time = new_value
                values[self.slider_target["end_pos"]] = str(new_time)

                # 獲取開始時間
                try:
                    start_time_str = values[self.slider_target["start_pos"]]
                    start_time = time_to_milliseconds(parse_time(start_time_str))
                except:
                    start_time = max(0, end_time - 10000)

                # 同時更新下一項的開始時間
                item_index = self.slider_target["item_index"]
                if item_index < len(self.slider_target["all_items"]) - 1:
                    next_item = self.slider_target["all_items"][item_index + 1]
                    next_values = list(self.tree.item(next_item, "values"))
                    next_values[self.slider_target["start_pos"]] = str(new_time)
                    self.tree.item(next_item, values=tuple(next_values))

            # 更新項目值
            self.tree.item(item, values=tuple(values))

            # 更新時間標籤
            for widget in self.slider_frame.winfo_children():
                if isinstance(widget, tk.Label) and widget.cget('fg') == "#4FC3F7":
                    widget.config(text=self._format_time_range(start_time, end_time))
                    break

            # 更新音頻視圖選擇區域
            if hasattr(self, 'audio_visualizer') and self.audio_visualizer and hasattr(self, 'current_display_range'):
                try:
                    display_start, display_end = self.current_display_range

                    # 計算相對位置
                    highlight_start = start_time - display_start
                    highlight_end = end_time - display_start

                    # 確保在有效範圍內
                    highlight_start = max(0, highlight_start)
                    highlight_end = max(highlight_start, highlight_end)

                    # 更新選擇區域
                    self.audio_visualizer.update_selection(highlight_start, highlight_end)
                except Exception as e:
                    self.logger.error(f"更新音頻視圖選擇區域時出錯: {e}")

            # 強制更新界面
            self.tree.update_idletasks()
            if hasattr(self, 'slider_frame'):
                self.slider_frame.update_idletasks()

        except Exception as e:
            self.logger.error(f"滑桿值變化處理時出錯: {e}", exc_info=True)

    def _format_time_range(self, start_time, end_time):
        """格式化並顯示時間範圍"""
        start_sec = int(start_time / 1000)
        start_ms = int(start_time % 1000)
        end_sec = int(end_time / 1000)
        end_ms = int(end_time % 1000)
        return f"{start_sec}:{start_ms:03d} → {end_sec}:{end_ms:03d}"

    def check_slider_focus(self, event):
        """檢查點擊是否在滑桿外部，如果是則隱藏滑桿 - 修改版"""
        try:
            if not self.slider_active or not self.slider_frame:
                return

            # 處理點擊在時間欄位的特殊情況
            if event.widget == self.tree:
                region = self.tree.identify_region(event.x, event.y)
                column = self.tree.identify_column(event.x)

                if region == "cell" and column:
                    column_idx = int(column[1:]) - 1
                    if column_idx < len(self.tree["columns"]):
                        column_name = self.tree["columns"][column_idx]
                        if column_name in ["Start", "End"]:
                            # 不隱藏滑桿，讓 on_tree_click 處理
                            return

            # 獲取滑桿框架的屏幕位置
            try:
                frame_x = self.slider_frame.winfo_rootx()
                frame_y = self.slider_frame.winfo_rooty()
                frame_width = self.slider_frame.winfo_width()
                frame_height = self.slider_frame.winfo_height()

                # 檢查點擊是否在框架外部
                if (event.x_root < frame_x or event.x_root > frame_x + frame_width or
                    event.y_root < frame_y or event.y_root > frame_y + frame_height):
                    # 應用變更並隱藏滑桿
                    self.apply_time_change()
                    self.hide_slider()
            except tk.TclError:
                # 框架可能已經被銷毀
                self.slider_active = False

        except Exception as e:
            self.logger.error(f"檢查滑桿焦點時出錯: {e}")
            self.hide_slider()

    def apply_time_change(self):
        """應用時間變更並同步音頻段落 - 修改版"""
        if not self.slider_active:
            return

        try:
            # 獲取當前滑桿值
            if hasattr(self, 'time_slider') and self.time_slider:
                current_value = self.time_slider.get()

                # 調用回調函數更新 SRT 和音頻
                if hasattr(self.callbacks, 'on_time_change') and callable(self.callbacks.on_time_change):
                    self.callbacks.on_time_change()

        except Exception as e:
            self.logger.error(f"應用時間變更時出錯: {e}")

    def hide_slider(self):
        """隱藏時間調整滑桿 - 修改版"""
        # 避免遞歸調用
        if hasattr(self, '_hide_time_slider_in_progress') and self._hide_time_slider_in_progress:
            return

        try:
            self._hide_time_slider_in_progress = True

            # 應用時間變更
            if self.slider_active:
                self.apply_time_change()

            # 清理音頻可視化器
            if hasattr(self, 'audio_visualizer') and self.audio_visualizer:
                try:
                    self.audio_visualizer.destroy()
                except:
                    pass
                self.audio_visualizer = None

            # 清理滑桿框架
            if hasattr(self, 'slider_frame') and self.slider_frame:
                try:
                    if self.slider_frame.winfo_exists():
                        self.slider_frame.destroy()
                except:
                    pass
                self.slider_frame = None

            # 重置狀態
            self.slider_active = False
            self.slider_target = None
            self.time_slider = None

            # 解除綁定
            try:
                if self.parent and hasattr(self.parent, 'bind'):
                    self.parent.unbind("<Button-1>")
            except:
                pass

        except Exception as e:
            self.logger.error(f"隱藏滑桿時出錯: {e}")
        finally:
            self._hide_time_slider_in_progress = False

    def _ensure_visualizer_visible(self):
        """確保音頻可視化器可見"""
        if hasattr(self, 'audio_visualizer') and self.audio_visualizer:
            try:
                # 檢查框架是否創建成功
                parent_frame = self.audio_visualizer.frame.master
                if parent_frame and parent_frame.winfo_exists():
                    parent_frame.update_idletasks()

                    # 獲取實際尺寸
                    actual_width = parent_frame.winfo_width()
                    actual_height = parent_frame.winfo_height()

                    # 如果尺寸不符預期，重新調整
                    if actual_width < 10 or actual_height < 10:
                        self.logger.warning(f"可視化器容器尺寸異常: {actual_width}x{actual_height}")
                        # 設置固定尺寸確保可見
                        parent_frame.configure(width=180, height=50)
                        parent_frame.update_idletasks()

                    # 重新配置可視化器尺寸
                    self.audio_visualizer.width = max(10, parent_frame.winfo_width())
                    self.audio_visualizer.height = max(10, parent_frame.winfo_height())
                    self.audio_visualizer.canvas.configure(
                        width=self.audio_visualizer.width,
                        height=self.audio_visualizer.height
                    )

                    # 刷新顯示
                    self.audio_visualizer.show()
            except Exception as e:
                self.logger.error(f"確保可視化器可見時出錯: {e}")

    def recreate_audio_visualizer(self, parent_frame, audio_segment=None):
        """重新創建音頻可視化器"""
        try:
            # 清除舊的可視化器
            if hasattr(self, 'audio_visualizer') and self.audio_visualizer:
                try:
                    self.audio_visualizer.destroy()
                except:
                    pass
                self.audio_visualizer = None

            # 確保父容器有效
            if not parent_frame or not parent_frame.winfo_exists():
                return False

            # 確保容器尺寸有效
            width = max(10, parent_frame.winfo_width())
            height = max(10, parent_frame.winfo_height())

            if width <= 0 or height <= 0:
                width = 180
                height = 50
                parent_frame.configure(width=width, height=height)
                parent_frame.update_idletasks()

            # 創建新的可視化器
            self.audio_visualizer = AudioVisualizer(
                parent_frame,
                width=width,
                height=height
            )

            # 使用 pack 以確保填滿容器
            self.audio_visualizer.pack(fill=tk.BOTH, expand=True)

            # 如果提供了音頻段落，創建波形
            if audio_segment is not None and len(audio_segment) > 0:
                self.audio_visualizer.create_waveform(audio_segment)
                return True

            return False

        except Exception as e:
            self.logger.error(f"重新創建音頻可視化器時出錯: {e}")
            return False

    def _format_time_display(self, milliseconds):
        """格式化毫秒為友好的時間顯示 (秒:毫秒)"""
        seconds = int(milliseconds / 1000)
        ms = int(milliseconds % 1000)
        return f"{seconds}:{ms:03d}"

    def _update_time_range_label(self, start_time, end_time):
        """顯示時間範圍標籤"""
        try:
            # 格式化時間
            start_sec = int(start_time / 1000)
            start_ms = int(start_time % 1000)
            end_sec = int(end_time / 1000)
            end_ms = int(end_time % 1000)
            time_range = f"{start_sec}:{start_ms:03d} → {end_sec}:{end_ms:03d}"

            # 在滑桿框架中查找並更新時間標籤
            if hasattr(self, 'slider_frame') and self.slider_frame:
                for widget in self.slider_frame.winfo_children():
                    if isinstance(widget, tk.Label) and widget.cget('fg') == "#4FC3F7":
                        widget.config(text=time_range)
                        break

            # 強制更新顯示
            if hasattr(self, 'slider_frame'):
                self.slider_frame.update_idletasks()
        except Exception as e:
            self.logger.error(f"更新時間範圍標籤時出錯: {e}")