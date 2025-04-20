"""音頻波形可視化模組 - 整合 WaveformVisualization 功能"""

import logging
import tkinter as tk
from typing import Optional, Tuple
import numpy as np
from PIL import Image, ImageTk, ImageDraw
from pydub import AudioSegment

from audio.audio_range_manager import AudioRangeManager


class AudioVisualizer:
    """整合了 WaveformVisualization 功能的音頻可視化類別"""

    def __init__(self, parent: tk.Widget, width: int = 100, height: int = 50):
        """初始化音頻可視化器"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.parent = parent
        self.width = width
        self.height = height

        # 創建畫布 - 使用深藍色背景 (從 WaveformVisualization 保留)
        self.canvas = tk.Canvas(
            parent,
            width=width,
            height=height,
            bg="#233A68",  # 使用更好看的深藍背景
            highlightthickness=0
        )

        # 波形相關變數
        self.waveform_image = None
        self.waveform_photo = None
        self.audio_duration = 0

        # 保存原始音頻數據用於動態縮放
        self.original_audio = None
        self.current_view_range = (0, 0)
        self.current_selection_range = (0, 0)
        self.samples_cache = None  # 緩存音頻樣本數據

        # 範圍管理器 - 新增整合
        self.range_manager = None

        # 增強的視圖配置 (從 WaveformVisualization)
        self.min_view_width = 500     # 最小視圖寬度（毫秒）
        self.max_view_width = 10000   # 最大視圖寬度（毫秒）
        self.min_selection_width = 100  # 最小選擇區域寬度（毫秒）

        # 初始狀態設置為空白波形
        self._create_empty_waveform("等待音頻...")

    def set_audio_segment(self, audio_segment: AudioSegment) -> None:
        """設置音頻段落並預處理"""
        try:
            if audio_segment is None or len(audio_segment) == 0:
                self._create_empty_waveform("無效的音頻段落")
                return

            self.original_audio = audio_segment
            self.audio_duration = len(audio_segment)

            # 創建範圍管理器
            self.range_manager = AudioRangeManager(self.audio_duration)

            # 預處理並緩存音頻數據
            self.samples_cache = self._preprocess_audio(audio_segment)
            self.logger.debug(f"音頻段落設置完成，總時長: {self.audio_duration}ms, 樣本數: {len(self.samples_cache)}")

            # 初始化視圖為整個音頻段落
            initial_view = (0, min(5000, self.audio_duration))
            self.current_view_range = initial_view

            # 重要：設置音頻後立即創建完整波形視圖
            self.update_waveform_and_selection(initial_view, (0, min(1000, self.audio_duration)))
        except Exception as e:
            self.logger.error(f"設置音頻段落時出錯: {e}")
            self._create_empty_waveform(f"錯誤: {str(e)}")

    def update_waveform_and_selection(self, view_range: Tuple[int, int], selection_range: Tuple[int, int], zoom_level: float = None) -> None:
        """
        即時更新波形和選擇區域，支持縮放級別 (整合 WaveformVisualization 的增強功能)

        Args:
            view_range: 視圖範圍 (view_start, view_end)
            selection_range: 選擇範圍 (sel_start, sel_end)
            zoom_level: 縮放級別 (可選)，None表示使用默認計算
        """
        try:
            if self.samples_cache is None or self.original_audio is None:
                self._create_empty_waveform("未設置音頻數據")
                return

            # 使用範圍管理器獲取最佳視圖範圍 (如果需要)
            if self.range_manager and view_range == self.current_view_range:
                # 視圖範圍沒有變化，可能是只更新了選擇區域
                view_start, view_end = self.range_manager.get_optimal_view_range(selection_range)
            else:
                # 使用提供的視圖範圍，但仍進行驗證
                view_start, view_end = view_range
                # 確保視圖範圍有效
                if view_start >= view_end and self.range_manager:
                    view_start, view_end = self.range_manager.get_optimal_view_range(selection_range)

            # 獲取選擇區域
            sel_start, sel_end = selection_range

            # 更新當前狀態
            self.current_view_range = (view_start, view_end)
            self.current_selection_range = (sel_start, sel_end)

            # 使用縮放級別繪製增強波形
            self._draw_waveform_with_zoom(zoom_level)

        except Exception as e:
            self.logger.error(f"更新波形時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self._create_empty_waveform(f"錯誤: {str(e)}")

    def _draw_waveform_with_zoom(self, zoom_level=None):
        """
        根據縮放級別繪製波形 (從 WaveformVisualization 整合)
        增強版本支持動態縮放和更美觀的視覺效果
        """
        try:
            # 獲取當前視圖和選擇範圍
            view_start, view_end = self.current_view_range
            sel_start, sel_end = self.current_selection_range

            # 計算視圖持續時間和選擇持續時間
            view_duration = view_end - view_start
            selection_duration = sel_end - sel_start

            # 如果未提供縮放級別，根據視圖和選擇範圍計算默認縮放級別
            if zoom_level is None:
                # 根據選擇範圍大小計算縮放級別
                if selection_duration < 100:  # 非常短的區間
                    zoom_level = 3.0
                elif selection_duration < 500:  # 較短的區間
                    zoom_level = 2.0
                elif selection_duration < 2000:  # 中等區間
                    zoom_level = 1.5
                else:  # 較長區間
                    zoom_level = 1.0

            # 計算顯示的樣本起始和結束索引
            sample_rate = len(self.samples_cache) / self.audio_duration if self.audio_duration > 0 else 44100
            start_sample = int(view_start * sample_rate)
            end_sample = int(view_end * sample_rate)

            # 確保樣本範圍有效
            start_sample = max(0, start_sample)
            end_sample = min(len(self.samples_cache), end_sample)

            # 再次檢查樣本範圍有效性
            if start_sample >= end_sample - 10:  # 確保至少有10個樣本
                start_sample = 0
                end_sample = min(1000, len(self.samples_cache))

            # 獲取顯示區域的樣本
            display_samples = self.samples_cache[start_sample:end_sample]

            # 初始化降採樣列表
            downsampled = []

            # 根據縮放級別調整採樣策略
            # 縮放級別越高，採樣越精細，波形越詳細
            samples_per_pixel = max(1, int(len(display_samples) / (self.width * zoom_level)))

            # 使用平滑的降採樣方法
            if len(display_samples) > 0:
                # 計算每個像素的峰值和RMS值
                for i in range(self.width):
                    start_idx = min(len(display_samples)-1, i * samples_per_pixel)
                    end_idx = min(len(display_samples), start_idx + samples_per_pixel)

                    if start_idx < end_idx:
                        segment = display_samples[start_idx:end_idx]

                        # 計算段落的峰值和RMS值
                        if len(segment) > 0:
                            peak = np.max(np.abs(segment))
                            rms = np.sqrt(np.mean(np.square(segment)))

                            # 使用加權混合值 - 根據縮放級別調整權重
                            # 縮放級別越高，越偏向使用峰值以顯示更細節的變化
                            peak_weight = min(0.9, 0.6 + (zoom_level - 1.0) * 0.1)
                            rms_weight = 1.0 - peak_weight

                            value = peak * peak_weight + rms * rms_weight
                            downsampled.append(value)
                        else:
                            downsampled.append(0)
                    else:
                        downsampled.append(0)

            # 標準化波形
            if len(downsampled) > 0:
                max_value = max(max(downsampled), 0.01)  # 避免除以零
                downsampled = [d / max_value for d in downsampled]

            # 創建圖像 - 使用深色背景
            bg_color = (35, 58, 104, 255)  # 深色背景
            img = Image.new('RGBA', (self.width, self.height), bg_color)
            draw = ImageDraw.Draw(img)

            # 繪製中心線
            center_y = self.height // 2
            draw.line([(0, center_y), (self.width, center_y)], fill=(70, 70, 70, 255), width=0)

            # 使用反鋸齒技術繪製平滑波形
            if len(downsampled) > 0:
                # 選擇區域中使用更明亮的顏色
                sel_start_pixel = int((sel_start - view_start) / view_duration * self.width) if view_duration > 0 else 0
                sel_end_pixel = int((sel_end - view_start) / view_duration * self.width) if view_duration > 0 else self.width

                # 限制在有效範圍內
                sel_start_pixel = max(0, min(sel_start_pixel, self.width))
                sel_end_pixel = max(0, min(sel_end_pixel, self.width))

                # 繪製平滑波形，使用線段代替單點
                for x in range(len(downsampled)):
                    amplitude = downsampled[x]

                    # 根據縮放級別和選擇區域持續時間計算波形高度
                    # 選擇區域越短或縮放級別越高，波形顯示越大
                    selection_duration = sel_end - sel_start
                    if selection_duration < 100:  # 非常短的區間 (<100ms)
                        # 極度放大波形
                        height_factor = max(2.0, zoom_level * 1.2)
                    elif selection_duration < 500:  # 較短的區間 (<500ms)
                        # 顯著放大波形
                        height_factor = max(1.8, zoom_level * 1.0)
                    elif selection_duration < 2000:  # 中等區間 (<2s)
                        # 適度放大波形
                        height_factor = max(1.5, zoom_level * 0.8)
                    else:  # 較長區間 (>=2s)
                        # 標準放大
                        height_factor = max(1.0, zoom_level * 0.5)

                    # 計算最終波形高度，確保在視圖範圍內
                    max_height = self.height // 2 - 2  # 最大允許高度
                    wave_height = int(amplitude * max_height * height_factor)
                    wave_height = min(wave_height, max_height)  # 確保不超出界限

                    y1 = center_y - wave_height
                    y2 = center_y + wave_height

                    # 根據位置和縮放級別選擇不同的顏色和線寬
                    if sel_start_pixel <= x <= sel_end_pixel:
                        # 選擇區域內用亮藍色
                        blue = min(255, int(150 + zoom_level * 25))  # 縮放越大藍色越亮
                        line_color = (120, 230, blue, 255)
                        line_width = min(3, int(1 + zoom_level / 2))  # 縮放越大線條越粗
                    else:
                        # 選擇區域外用標準藍色
                        line_color = (100, 200, 255, 255)
                        line_width = 1  # 標準線條

                    draw.line([(x, y1), (x, y2)], fill=line_color, width=line_width)

            # 繪製選擇區域高亮
            if view_duration > 0:
                # 確保選擇區與視圖範圍有交集
                if sel_end >= view_start and sel_start <= view_end:
                    # 計算相對位置
                    display_sel_start = max(sel_start, view_start)
                    display_sel_end = min(sel_end, view_end)

                    # 計算相對於當前視圖的比例位置
                    relative_start = (display_sel_start - view_start) / view_duration
                    relative_end = (display_sel_end - view_start) / view_duration

                    # 轉換為像素位置
                    start_x = int(relative_start * self.width)
                    end_x = int(relative_end * self.width)

                    # 確保至少有一個像素的寬度
                    if end_x - start_x < 1:
                        end_x = start_x + 1

                    start_x = max(0, start_x)
                    end_x = min(self.width, end_x)

                    if start_x < end_x:  # 確保有效的選擇區域
                        # 繪製高亮區域 - 使用半透明覆蓋
                        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
                        overlay_draw = ImageDraw.Draw(overlay)

                        # 繪製漸變填充
                        alpha_base = min(160, int(120 + zoom_level * 15))  # 縮放越大越透明
                        for x in range(start_x, end_x):
                            # 距離邊緣的相對位置
                            rel_pos = min(x - start_x, end_x - x) / max(1, (end_x - start_x) / 2)
                            # 計算透明度
                            alpha = int(alpha_base * min(1.0, rel_pos + 0.3))
                            overlay_draw.line([(x, 0), (x, self.height)], fill=(79, 195, 247, alpha), width=1)

                        # 合併圖層
                        img = Image.alpha_composite(img, overlay)
                        draw = ImageDraw.Draw(img)

                        # 繪製邊界線
                        edge_width = max(1, min(3, int(zoom_level)))  # 縮放越大邊界線越粗
                        draw.line([(start_x, 0), (start_x, self.height)], fill=(79, 195, 247, 255), width=edge_width)
                        draw.line([(end_x, 0), (end_x, self.height)], fill=(79, 195, 247, 255), width=edge_width)

            # 更新顯示
            self.waveform_image = img
            self.waveform_photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)

            # 減少更新頻率，避免閃爍
            self.canvas.update_idletasks()

        except Exception as e:
            self.logger.error(f"根據縮放級別繪製波形時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _preprocess_audio(self, audio_segment):
        """預處理音頻數據，只處理一次"""
        try:
            samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)

            # 處理立體聲
            if audio_segment.channels == 2:
                samples = samples.reshape((-1, 2)).mean(axis=1)

            # 正規化
            max_abs = np.max(np.abs(samples))
            if max_abs > 0:
                samples = samples / max_abs
            else:
                samples = np.zeros_like(samples)

            self.logger.debug(f"音頻預處理完成: 樣本數={len(samples)}, 最大振幅={max_abs}")
            return samples
        except Exception as e:
            self.logger.error(f"音頻預處理失敗: {e}")
            return np.zeros(1000)  # 返回空數組作為後備

    def _create_empty_waveform(self, message="等待音頻..."):
        """創建空白波形圖"""
        try:
            img = Image.new('RGBA', (self.width, self.height), (30, 30, 30, 255))
            draw = ImageDraw.Draw(img)

            center_y = self.height // 2
            draw.line([(0, center_y), (self.width, center_y)], fill=(70, 70, 70, 255), width=1)
            draw.text((10, center_y - 7), message, fill=(180, 180, 180, 255))

            self.waveform_image = img
            self.waveform_photo = ImageTk.PhotoImage(img)

            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)
            self.canvas.update()

        except Exception as e:
            self.logger.error(f"創建空白波形出錯: {e}")

    def show(self):
        """顯示波形容器"""
        self.canvas.pack(side=tk.TOP, pady=(2, 0))

    def hide(self):
        """隱藏波形容器"""
        try:
            if self.canvas and self.canvas.winfo_exists():
                self.canvas.pack_forget()
        except tk.TclError:
            pass
        except Exception as e:
            self.logger.error(f"隱藏波形容器時出錯: {e}")

    def clear_waveform(self):
        """清除波形圖"""
        try:
            if self.canvas and self.canvas.winfo_exists():
                self.canvas.delete("all")

            self.waveform_image = None
            self.waveform_photo = None

            # 創建空白波形，避免顯示空白
            self._create_empty_waveform("等待音頻...")

        except tk.TclError:
            pass
        except Exception as e:
            self.logger.error(f"清除波形圖時出錯: {e}")