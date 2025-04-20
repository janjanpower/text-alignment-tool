"""示範如何在 AudioVisualizer 中整合簡化的 WaveformZoomManager"""

import logging
import tkinter as tk
from typing import Optional, Tuple
import numpy as np
from PIL import Image, ImageTk, ImageDraw
from pydub import AudioSegment

from audio.waveform_zoom_manager import WaveformZoomManager


class AudioVisualizer:
    """整合了簡化版 WaveformZoomManager 的音頻可視化類別"""

    def __init__(self, parent: tk.Widget, width: int = 100, height: int = 100):
        """初始化音頻可視化器"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.parent = parent
        self.width = width
        self.height = height

        # 創建畫布
        self.canvas = tk.Canvas(
            parent,
            width=width,
            height=height,
            bg="#1E1E1E",
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

        # 初始化縮放管理器為 None，將在設置音頻時創建
        self.zoom_manager = None

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

            # 初始化縮放管理器
            self.zoom_manager = WaveformZoomManager(self.audio_duration)

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

    def update_waveform_and_selection(self, view_range: Tuple[int, int], selection_range: Tuple[int, int], zoom_factor: float = 1.0) -> None:
        """
        即時更新波形和選擇區域

        Args:
            view_range: 視圖範圍 (view_start, view_end)
            selection_range: 選擇範圍 (sel_start, sel_end)
            zoom_factor: 縮放因子，控制波形細節程度 (>1.0 顯示更多細節)
        """
        try:
            if self.samples_cache is None or self.original_audio is None:
                self._create_empty_waveform("未設置音頻數據")
                return

            # 使用核心邏輯繪製波形，傳遞縮放因子
            view_start, view_end = view_range
            sel_start, sel_end = selection_range

            # 更新當前狀態
            self.current_view_range = (view_start, view_end)
            self.current_selection_range = (sel_start, sel_end)

            # 使用縮放因子繪製波形
            self._draw_waveform_core(zoom_factor)

        except Exception as e:
            self.logger.error(f"更新波形時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self._create_empty_waveform(f"錯誤: {str(e)}")

    def _draw_waveform_core(self, zoom_factor=1.0):
        """核心波形繪製邏輯 - 支持動態縮放"""
        try:
            # 獲取當前視圖和選擇範圍
            view_start, view_end = self.current_view_range
            sel_start, sel_end = self.current_selection_range

            # 計算視圖持續時間
            view_duration = view_end - view_start
            selection_duration = sel_end - sel_start

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

            # 計算縮放比例 - 考慮傳入的縮放因子
            base_zoom_ratio = view_duration / max(1, selection_duration)
            effective_zoom_ratio = base_zoom_ratio * zoom_factor

            # 根據有效縮放比例和視圖寬度選擇降採樣策略
            if selection_duration < 100 or effective_zoom_ratio > 50:  # 非常短的選擇區域或高縮放
                # 使用最高精度的採樣策略
                samples_per_pixel = max(1, int(len(display_samples) / (self.width * 3)))
            elif selection_duration < 500 or effective_zoom_ratio > 20:  # 較短的選擇區域或中高縮放
                # 使用較高精度的採樣
                samples_per_pixel = max(1, int(len(display_samples) / (self.width * 2)))
            elif effective_zoom_ratio > 10:  # 中等縮放
                # 使用中等精度的採樣
                samples_per_pixel = max(1, int(len(display_samples) / (self.width * 1.5)))
            else:  # 低縮放
                # 標準採樣
                samples_per_pixel = max(1, len(display_samples) // self.width)

            # 使用更平滑的降採樣方法
            if len(display_samples) > 0:
                # 計算每個像素的峰值和RMS值
                for i in range(self.width):
                    start_idx = i * samples_per_pixel
                    end_idx = min(start_idx + samples_per_pixel, len(display_samples))

                    if start_idx < len(display_samples) and end_idx > start_idx:
                        segment = display_samples[start_idx:end_idx]

                        # 計算段落的峰值和RMS值
                        if len(segment) > 0:
                            peak = np.max(np.abs(segment))
                            rms = np.sqrt(np.mean(np.square(segment)))

                            # 使用加權混合值 - 根據縮放因子調整權重
                            # 縮放越大，越偏向使用峰值以顯示更細節的變化
                            peak_weight = min(0.9, 0.6 + (zoom_factor - 1.0) * 0.2)
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

            # 創建圖像 - 根據縮放因子調整顯示效果
            bg_color = (30, 30, 30, 255)  # 默認背景色
            img = Image.new('RGBA', (self.width, self.height), bg_color)
            draw = ImageDraw.Draw(img)

            # 繪製中心線
            center_y = self.height // 2
            draw.line([(0, center_y), (self.width, center_y)], fill=(70, 70, 70, 255), width=1)

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

                    # 根據縮放因子調整波形高度 - 縮放越大，波形越高
                    height_factor = 1.0 + (zoom_factor - 1.0) * 0.3  # 縮放因子影響波形高度
                    wave_height = int(amplitude * (self.height // 2 - 4) * height_factor)
                    wave_height = min(wave_height, self.height // 2 - 4)  # 確保不超出界限

                    y1 = center_y - wave_height
                    y2 = center_y + wave_height

                    # 根據位置和縮放因子選擇不同的顏色和線寬
                    if sel_start_pixel <= x <= sel_end_pixel:
                        # 選擇區域內顏色 - 根據縮放因子調整亮度
                        intensity = int(180 + min(75, (zoom_factor - 1.0) * 50))  # 更高的縮放 = 更亮的顏色
                        line_color = (intensity, 230, 255, 255)
                        line_width = min(3, 1 + int(zoom_factor / 2))  # 縮放越大，線條越粗
                    else:
                        # 選擇區域外顏色
                        intensity = int(100 + min(50, (zoom_factor - 1.0) * 30))
                        line_color = (intensity, 200, 255, 255)
                        line_width = 1  # 標準線條

                    # 繪製波形
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
                        # 繪製高亮區域 - 使用漸變效果增強視覺效果
                        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
                        overlay_draw = ImageDraw.Draw(overlay)

                        # 使用漸變填充
                        for x in range(start_x, end_x):
                            # 計算距離邊緣的相對位置
                            rel_pos = min(x - start_x, end_x - x) / max(1, (end_x - start_x) / 2)
                            # 計算透明度，邊緣較透明
                            alpha = int(128 * min(1.0, rel_pos + 0.3))
                            overlay_draw.line([(x, 0), (x, self.height)], fill=(79, 195, 247, alpha), width=1)

                        # 合併圖層
                        img = Image.alpha_composite(img, overlay)
                        draw = ImageDraw.Draw(img)

                        # 繪製邊界線
                        draw.line([(start_x, 0), (start_x, self.height)], fill=(79, 195, 247, 255), width=2)
                        draw.line([(end_x, 0), (end_x, self.height)], fill=(79, 195, 247, 255), width=2)

            # 更新顯示
            self.waveform_image = img
            self.waveform_photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)

            # 減少更新頻率，避免閃爍
            self.canvas.update_idletasks()

        except Exception as e:
            self.logger.error(f"繪製波形核心邏輯出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

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