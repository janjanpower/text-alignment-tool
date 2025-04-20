"""音頻波形可視化模組 - 高效能版本"""

import logging
import tkinter as tk
from typing import Optional, Tuple, Union, Dict
import numpy as np
from PIL import Image, ImageTk, ImageDraw
from pydub import AudioSegment

class AudioVisualizer:
    """高效能音頻波形可視化類別，提供穩定、清晰的波形顯示"""

    def __init__(self, parent: tk.Widget, width: int = 100, height: int = 50):
        """初始化音頻可視化器"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.parent = parent
        self.width = width
        self.height = height

        # 創建畫布 - 使用深藍色背景
        self.canvas = tk.Canvas(
            parent,
            width=width,
            height=height,
            bg="#233A68",  # 深藍背景
            highlightthickness=0
        )

        # 波形相關變數
        self.waveform_image = None
        self.waveform_photo = None
        self.audio_duration = 0

        # 原始音頻數據
        self.original_audio = None
        self.current_view_range = (0, 0)
        self.current_selection_range = (0, 0)
        self.samples_cache = None      # 緩存音頻樣本數據
        self.waveform_cache = {}       # 緩存已渲染的波形圖像

        # 範圍控制參數
        self.min_view_width = 500      # 最小視圖寬度（毫秒）
        self.max_view_width = 10000    # 最大視圖寬度（毫秒）
        self.min_selection_width = 100 # 最小選擇區域寬度（毫秒）

        # 動畫和過渡效果參數
        self.enable_animation = True
        self.animation_active = False
        self.animation_steps = 8       # 動畫步數
        self.target_view_range = (0, 0)
        self.target_selection_range = (0, 0)
        self.prev_waveform_image = None

        # 渲染品質控制
        self.high_quality = True       # 高品質模式默認開啟
        self.antialias = True          # 抗鋸齒
        self.max_samples_per_pixel = 20  # 每像素最大樣本數，控制詳細度

        # 視覺樣式設置
        self.colors = {
            'background': "#233A68",    # 背景色
            'center_line': "#454545",   # 中心線顏色
            'wave_normal': (100, 200, 255, 255),   # 普通波形顏色
            'wave_selected': (120, 230, 255, 255), # 選中區域波形顏色
            'selection_fill': (79, 195, 247, 160), # 選中區域填充顏色
            'selection_border': (79, 195, 247, 255) # 選中區域邊框顏色
        }

        # 初始狀態設置為空白波形
        self._create_empty_waveform("等待音頻...")

    def set_audio_segment(self, audio_segment: AudioSegment) -> None:
        """設置音頻段落並預處理"""
        try:
            if audio_segment is None or len(audio_segment) == 0:
                self._create_empty_waveform("無效的音頻段落")
                return

            # 保存原始音頻數據
            self.original_audio = audio_segment
            self.audio_duration = len(audio_segment)

            # 清空舊的緩存
            self.waveform_cache = {}

            # 預處理並緩存音頻數據
            self.samples_cache = self._preprocess_audio(audio_segment)
            self.logger.debug(f"音頻段落設置完成，總時長: {self.audio_duration}ms, 樣本數: {len(self.samples_cache)}")

            # 初始化視圖為整個音頻段落
            initial_view = (0, min(5000, self.audio_duration))
            self.current_view_range = initial_view

            # 設置音頻後立即創建完整波形視圖
            self.update_waveform_and_selection(initial_view, (0, min(1000, self.audio_duration)))
        except Exception as e:
            self.logger.error(f"設置音頻段落時出錯: {e}")
            self._create_empty_waveform(f"錯誤: {str(e)}")

    def update_waveform_and_selection(self,
                                     view_range: Tuple[int, int],
                                     selection_range: Tuple[int, int],
                                     zoom_level: float = None,
                                     animate: bool = True) -> None:
        """
        更新波形和選擇區域，支持平滑過渡動畫

        Args:
            view_range: 視圖範圍 (view_start, view_end)
            selection_range: 選擇範圍 (sel_start, sel_end)
            zoom_level: 縮放級別 (可選)，None表示使用默認計算
            animate: 是否啟用動畫過渡效果
        """
        try:
            if self.samples_cache is None or self.original_audio is None:
                self._create_empty_waveform("未設置音頻數據")
                return

            # 驗證並調整範圍
            view_start, view_end = self._validate_range(view_range, min_width=self.min_view_width)
            sel_start, sel_end = self._validate_range(selection_range, min_width=self.min_selection_width)

            # 確保選擇區域在視圖範圍內
            sel_start = max(sel_start, view_start)
            sel_end = min(sel_end, view_end)

            # 保存目標範圍，用於動畫
            self.target_view_range = (view_start, view_end)
            self.target_selection_range = (sel_start, sel_end)

            # 計算自適應縮放級別
            if zoom_level is None:
                zoom_level = self._calculate_adaptive_zoom_level(sel_start, sel_end)

            # 動畫過渡或直接更新
            if animate and self.enable_animation and not self.animation_active:
                self._animate_transition(view_start, view_end, sel_start, sel_end, zoom_level)
            else:
                # 直接繪製最終波形
                self._draw_waveform(view_start, view_end, sel_start, sel_end, zoom_level)

        except Exception as e:
            self.logger.error(f"更新波形時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self._create_empty_waveform(f"錯誤: {str(e)}")

    def _animate_transition(self, view_start, view_end, sel_start, sel_end, zoom_level):
        """實現平滑的動畫過渡效果"""
        self.animation_active = True

        # 保存源範圍
        source_view_start, source_view_end = self.current_view_range
        source_sel_start, source_sel_end = self.current_selection_range

        # 緩存當前圖像
        self.prev_waveform_image = self.waveform_image

        # 定義遞歸的動畫幀函數
        def animate_frame(step=0):
            if step >= self.animation_steps:
                # 最後一幀，直接顯示目標波形
                self._draw_waveform(view_start, view_end, sel_start, sel_end, zoom_level)
                self.animation_active = False
                return

            # 計算當前幀的插值位置 (使用緩入緩出的效果)
            progress = self._ease_in_out(step / self.animation_steps)

            # 計算當前幀的範圍
            current_view_start = source_view_start + (view_start - source_view_start) * progress
            current_view_end = source_view_end + (view_end - source_view_end) * progress
            current_sel_start = source_sel_start + (sel_start - source_sel_start) * progress
            current_sel_end = source_sel_end + (sel_end - source_sel_end) * progress

            # 繪製當前幀
            self._draw_waveform(
                current_view_start, current_view_end,
                current_sel_start, current_sel_end,
                zoom_level, is_animation_frame=True
            )

            # 安排下一幀
            self.parent.after(10, lambda: animate_frame(step + 1))

        # 開始動畫
        animate_frame()

    def _ease_in_out(self, t):
        """緩入緩出的動畫曲線函數，使動畫更自然"""
        return 0.5 - 0.5 * np.cos(np.pi * t)

    def _validate_range(self, range_tuple, min_width=100):
        """驗證並修正範圍，確保寬度和邊界合法"""
        start, end = range_tuple

        # 確保不為負值
        start = max(0, start)
        end = max(0, end)

        # 確保開始時間不大於結束時間
        if start > end:
            start, end = end, start

        # 確保最小寬度
        if end - start < min_width:
            # 保持中心點不變，擴展到最小寬度
            center = (start + end) / 2
            half_width = min_width / 2
            start = max(0, center - half_width)
            end = min(self.audio_duration, center + half_width)

            # 如果達到了邊界，再次調整以確保最小寬度
            if end - start < min_width:
                if start == 0:
                    end = min(self.audio_duration, min_width)
                elif end == self.audio_duration:
                    start = max(0, self.audio_duration - min_width)

        # 確保不超出音頻最大長度
        end = min(end, self.audio_duration)

        return start, end

    def _calculate_adaptive_zoom_level(self, sel_start, sel_end):
        """根據選擇範圍大小計算自適應縮放級別"""
        duration = sel_end - sel_start

        # 縮放級別隨著選擇區域縮小而增加
        if duration < 50:          # 極短範圍 (<50ms)
            return 5.0             # 極度放大
        elif duration < 100:       # 非常短時間 (<100ms)
            return 4.0             # 非常高縮放
        elif duration < 250:       # 較短範圍 (<250ms)
            return 3.0             # 高縮放
        elif duration < 500:       # 短範圍 (<500ms)
            return 2.5             # 中高縮放
        elif duration < 1000:      # 中短範圍 (<1s)
            return 2.0             # 中等縮放
        elif duration < 2000:      # 中等範圍 (<2s)
            return 1.5             # 低縮放
        else:                      # 長範圍 (>=2s)
            return 1.0             # 標準縮放

    def _draw_waveform(self, view_start, view_end, sel_start, sel_end, zoom_level, is_animation_frame=False):
        """
        繪製波形圖 - 優化版本

        Args:
            view_start, view_end: 視圖範圍（毫秒）
            sel_start, sel_end: 選擇區域（毫秒）
            zoom_level: 縮放級別，控制波形高度和細節
            is_animation_frame: 是否為動畫幀（降低過渡幀的渲染品質以提高性能）
        """
        try:
            # 更新當前範圍
            self.current_view_range = (view_start, view_end)
            self.current_selection_range = (sel_start, sel_end)

            # 檢查緩存中是否已有當前參數組合的波形
            cache_key = f"{view_start:.0f}_{view_end:.0f}_{sel_start:.0f}_{sel_end:.0f}_{zoom_level:.1f}"
            if not is_animation_frame and cache_key in self.waveform_cache:
                # 使用緩存的波形圖像
                self.waveform_image = self.waveform_cache[cache_key]
                self.waveform_photo = ImageTk.PhotoImage(self.waveform_image)
                self.canvas.delete("all")
                self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)
                self.canvas.update_idletasks()
                return

            # 確定繪製品質 - 動畫幀使用較低品質以提高性能
            quality_factor = 0.5 if is_animation_frame else 1.0
            use_antialias = self.antialias and not is_animation_frame

            # 創建背景圖層
            bg_color = self.colors['background']
            img = Image.new('RGBA', (self.width, self.height), bg_color)
            draw = ImageDraw.Draw(img)

            # 繪製中心線
            center_y = self.height // 2
            draw.line([(0, center_y), (self.width, center_y)],
                      fill=self.colors['center_line'], width=1)

            # 計算波形數據
            waveform_data = self._calculate_waveform_data(
                view_start, view_end,
                self.width,
                zoom_level,
                quality_factor
            )

            # 繪製選擇區域背景
            if sel_start != sel_end:
                self._draw_selection_area(draw, view_start, view_end, sel_start, sel_end)

            # 繪製波形線條 - 分層繪製提高視覺質量
            center_y = self.height // 2
            max_height = (self.height // 2) - 2  # 最大振幅高度

            # 計算視圖持續時間和像素比例
            view_duration = view_end - view_start
            pixel_duration = view_duration / self.width if self.width > 0 else 1

            # 選擇區域範圍（像素）
            sel_start_px = int((sel_start - view_start) / pixel_duration) if pixel_duration > 0 else 0
            sel_end_px = int((sel_end - view_start) / pixel_duration) if pixel_duration > 0 else self.width
            sel_start_px = max(0, min(sel_start_px, self.width))
            sel_end_px = max(0, min(sel_end_px, self.width))

            # 先繪製非選擇區域波形
            self._draw_waveform_section(
                draw, waveform_data, 0, sel_start_px, center_y, max_height,
                zoom_level, self.colors['wave_normal']
            )
            self._draw_waveform_section(
                draw, waveform_data, sel_end_px, self.width, center_y, max_height,
                zoom_level, self.colors['wave_normal']
            )

            # 再繪製選擇區域波形（使其疊加在上方）
            self._draw_waveform_section(
                draw, waveform_data, sel_start_px, sel_end_px, center_y, max_height,
                zoom_level, self.colors['wave_selected'], line_width=2
            )

            # 儲存最終圖像並顯示
            self.waveform_image = img
            self.waveform_photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)

            # 非動畫幀時緩存結果
            if not is_animation_frame:
                self.waveform_cache[cache_key] = img

                # 限制緩存大小，超過100項時清理最早的緩存
                if len(self.waveform_cache) > 100:
                    keys = list(self.waveform_cache.keys())
                    for old_key in keys[:20]:  # 一次清理20個
                        if old_key in self.waveform_cache:
                            del self.waveform_cache[old_key]

            # 強制更新
            self.canvas.update_idletasks()

        except Exception as e:
            self.logger.error(f"繪製波形時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _draw_selection_area(self, draw, view_start, view_end, sel_start, sel_end):
        """繪製選擇區域的高亮背景"""
        # 計算視圖持續時間和像素比例
        view_duration = view_end - view_start
        pixel_duration = view_duration / self.width if self.width > 0 else 1

        # 選擇區域範圍（像素）
        sel_start_px = int((sel_start - view_start) / pixel_duration) if pixel_duration > 0 else 0
        sel_end_px = int((sel_end - view_start) / pixel_duration) if pixel_duration > 0 else self.width
        sel_start_px = max(0, min(sel_start_px, self.width))
        sel_end_px = max(0, min(sel_end_px, self.width))

        # 確保至少有1像素寬度
        if sel_end_px - sel_start_px < 1:
            sel_end_px = sel_start_px + 1

        # 創建半透明的覆蓋層
        for x in range(sel_start_px, sel_end_px):
            # 漸變透明度 - 邊緣透明度較低
            alpha = self.colors['selection_fill'][3]
            if sel_end_px - sel_start_px > 10:
                # 計算到邊緣的距離
                dist_to_edge = min(x - sel_start_px, sel_end_px - x)
                edge_factor = min(1.0, dist_to_edge / 5.0)
                alpha = int(alpha * edge_factor)

            # 使用透明度繪製垂直線
            color = self.colors['selection_fill'][:3] + (alpha,)
            draw.line([(x, 0), (x, self.height)], fill=color, width=1)

        # 繪製邊界線
        draw.line([(sel_start_px, 0), (sel_start_px, self.height)],
                  fill=self.colors['selection_border'], width=2)
        draw.line([(sel_end_px, 0), (sel_end_px, self.height)],
                  fill=self.colors['selection_border'], width=2)

    def _draw_waveform_section(self, draw, waveform_data, start_px, end_px, center_y, max_height,
                              zoom_level, color, line_width=1):
        """繪製波形的特定區域段落，支持增強的視覺效果"""
        if start_px >= end_px or start_px >= len(waveform_data) or start_px >= self.width:
            return

        # 限制結束位置
        end_px = min(end_px, self.width, len(waveform_data))

        # 根據縮放級別調整波形高度
        height_factor = zoom_level

        # 使用Path對象創建平滑的波形路徑
        points = []
        for x in range(start_px, end_px):
            if x < len(waveform_data):
                amplitude = waveform_data[x]
                # 應用高度因子
                wave_height = int(amplitude * max_height * height_factor)
                wave_height = min(wave_height, max_height)  # 確保不超出邊界

                # 上下兩個點
                y1 = center_y - wave_height
                y2 = center_y + wave_height

                # 繪製線條
                draw.line([(x, y1), (x, y2)], fill=color, width=line_width)

    def _calculate_waveform_data(self, view_start, view_end, width, zoom_level, quality_factor=1.0):
        """計算指定視圖範圍的波形數據 - 優化版本"""
        # 如果沒有樣本或寬度為0，返回空數組
        if self.samples_cache is None or width <= 0:
            return np.zeros(width)

        # 計算視圖範圍內的樣本
        sample_rate = len(self.samples_cache) / self.audio_duration
        start_sample = int(view_start * sample_rate)
        end_sample = int(view_end * sample_rate)

        # 調整樣本範圍
        start_sample = max(0, start_sample)
        end_sample = min(len(self.samples_cache), end_sample)

        # 如果樣本範圍無效，返回空波形
        if end_sample <= start_sample:
            return np.zeros(width)

        # 提取樣本數據
        samples = self.samples_cache[start_sample:end_sample]

        # 根據品質因子調整降採樣
        target_width = int(width * quality_factor)
        target_width = max(10, target_width)  # 確保至少10個點

        # 計算每個像素的樣本數
        samples_per_pixel = len(samples) / target_width

        # 防止值過大，導致計算過慢
        max_samples = min(samples_per_pixel, self.max_samples_per_pixel)
        effective_samples_per_pixel = max(1, int(samples_per_pixel))

        # 初始化結果數組
        result = np.zeros(target_width)

        # 使用高效的向量化操作計算振幅
        # 針對不同的samples_per_pixel使用不同的策略
        if effective_samples_per_pixel <= 1:
            # 樣本少於像素，使用插值
            indices = np.linspace(0, len(samples)-1, target_width).astype(int)
            result = np.abs(samples[indices])
        else:
            # 樣本多於像素，使用峰值檢測
            for i in range(target_width):
                start_idx = min(len(samples)-1, int(i * samples_per_pixel))
                end_idx = min(len(samples), int((i+1) * samples_per_pixel))

                if start_idx < end_idx:
                    segment = samples[start_idx:end_idx]

                    # 計算峰值和均方根的加權平均
                    if len(segment) > 0:
                        peak = np.max(np.abs(segment))
                        rms = np.sqrt(np.mean(np.square(segment)))

                        # 縮放級別影響峰值權重
                        peak_weight = min(0.9, 0.6 + (zoom_level - 1.0) * 0.1)
                        rms_weight = 1.0 - peak_weight

                        result[i] = peak * peak_weight + rms * rms_weight

        # 標準化結果
        max_val = np.max(result)
        if max_val > 0:
            result = result / max_val

        # 如果目標寬度小於請求寬度，進行插值擴展
        if target_width < width:
            indices = np.linspace(0, target_width-1, width).astype(int)
            result = result[indices]

        return result

    def _preprocess_audio(self, audio_segment):
        """預處理音頻數據，提取樣本並規範化"""
        try:
            # 獲取樣本數據
            samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)

            # 將立體聲轉換為單聲道（如果需要）
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
            img = Image.new('RGBA', (self.width, self.height), self.colors['background'])
            draw = ImageDraw.Draw(img)

            center_y = self.height // 2
            draw.line([(0, center_y), (self.width, center_y)],
                      fill=self.colors['center_line'], width=1)

            # 繪製文字
            text_color = (180, 180, 180, 255)
            draw.text((10, center_y - 7), message, fill=text_color)

            self.waveform_image = img
            self.waveform_photo = ImageTk.PhotoImage(img)

            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)
            self.canvas.update()

        except Exception as e:
            self.logger.error(f"創建空白波形出錯: {e}")

    def set_size(self, width, height):
        """動態調整波形視圖大小"""
        if width != self.width or height != self.height:
            self.width = width
            self.height = height

            # 調整畫布大小
            self.canvas.config(width=width, height=height)

            # 清除緩存並重新繪製
            self.waveform_cache = {}

            # 如果有音頻數據，重新繪製波形
            if self.original_audio:
                self.update_waveform_and_selection(
                    self.current_view_range,
                    self.current_selection_range,
                    animate=False
                )
            else:
                self._create_empty_waveform()

    def set_theme(self, dark_mode=True):
        """設置顏色主題"""
        if dark_mode:
            # 深色主題
            self.colors = {
                'background': "#233A68",      # 深藍背景
                'center_line': "#454545",     # 中心線顏色
                'wave_normal': (80, 180, 240, 255),   # 普通波形顏色
                'wave_selected': (120, 230, 255, 255), # 選中區域波形顏色
                'selection_fill': (79, 195, 247, 150), # 選中區域填充顏色
                'selection_border': (79, 195, 247, 255) # 選中區域邊框顏色
            }
        else:
            # 淺色主題
            self.colors = {
                'background': "#E8F0FE",      # 淺藍背景
                'center_line': "#AAAAAA",     # 中心線顏色
                'wave_normal': (50, 150, 220, 255),   # 普通波形顏色
                'wave_selected': (30, 120, 220, 255), # 選中區域波形顏色
                'selection_fill': (79, 195, 247, 120), # 選中區域填充顏色
                'selection_border': (79, 195, 247, 220) # 選中區域邊框顏色
            }

        # 更新畫布背景色
        self.canvas.config(bg=self.colors['background'])

        # 重新繪製當前波形
        if self.original_audio:
            self.update_waveform_and_selection(
                self.current_view_range,
                self.current_selection_range,
                animate=False
            )
        else:
            self._create_empty_waveform()

    def set_quality(self, high_quality=True, enable_animation=True):
        """設置渲染品質選項"""
        changed = (self.high_quality != high_quality or
                   self.enable_animation != enable_animation)

        self.high_quality = high_quality
        self.enable_animation = enable_animation
        self.antialias = high_quality

        # 如果設置變更且有音頻數據，重新繪製
        if changed and self.original_audio:
            # 清除緩存
            self.waveform_cache = {}

            # 重新繪製
            self.update_waveform_and_selection(
                self.current_view_range,
                self.current_selection_range,
                animate=False
            )

    def show(self):
        """顯示波形容器"""
        self.canvas.pack(side=tk.TOP, pady=(2, 0), fill=tk.BOTH, expand=True)

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
            self.waveform_cache = {}

            # 創建空白波形，避免顯示空白
            self._create_empty_waveform("等待音頻...")

        except tk.TclError:
            pass
        except Exception as e:
            self.logger.error(f"清除波形圖時出錯: {e}")

    def zoom_to_selection(self, selection_range=None, animate=True):
        """縮放視圖以最佳顯示選擇區域"""
        if selection_range is None:
            selection_range = self.current_selection_range

        sel_start, sel_end = self._validate_range(selection_range, min_width=self.min_selection_width)

        # 計算合適的視圖範圍
        selection_duration = sel_end - sel_start

        # 視圖寬度是選擇區域的3-5倍，根據選擇區域大小動態調整
        if selection_duration < 200:
            view_width = selection_duration * 5  # 非常小的選擇區域，給予更多上下文
        elif selection_duration < 1000:
            view_width = selection_duration * 4  # 小選擇區域
        elif selection_duration < 3000:
            view_width = selection_duration * 3  # 中等選擇區域
        else:
            view_width = selection_duration * 2  # 大選擇區域

        # 確保視圖寬度在有效範圍內
        view_width = max(self.min_view_width, min(self.max_view_width, view_width))

        # 計算中心點，使選擇區域居中
        center = (sel_start + sel_end) / 2

        # 計算視圖範圍
        view_start = max(0, center - view_width / 2)
        view_end = min(self.audio_duration, view_start + view_width)

        # 如果視圖碰到邊界，調整起點
        if view_end == self.audio_duration:
            view_start = max(0, self.audio_duration - view_width)

        # 更新波形
        self.update_waveform_and_selection(
            (view_start, view_end),
            selection_range,
            animate=animate
        )

    def get_sample_at(self, position_ms):
        """獲取指定時間點的樣本值"""
        if self.samples_cache is None or self.audio_duration == 0:
            return 0

        # 確保位置在有效範圍內
        position_ms = max(0, min(position_ms, self.audio_duration))

        # 計算樣本索引
        sample_rate = len(self.samples_cache) / self.audio_duration
        sample_index = int(position_ms * sample_rate)

        # 確保索引有效
        if 0 <= sample_index < len(self.samples_cache):
            return self.samples_cache[sample_index]

        return 0

    def export_waveform_image(self, filename, width=None, height=None):
        """導出當前波形圖像為文件"""
        try:
            # 如果指定了新的尺寸，創建相應大小的新圖像
            if width is not None and height is not None and (width != self.width or height != self.height):
                # 保存原始尺寸
                orig_width, orig_height = self.width, self.height

                # 臨時修改尺寸
                self.width, self.height = width, height

                # 使用高品質設置渲染新圖像
                old_quality = self.high_quality
                self.high_quality = True

                # 重新渲染
                self._draw_waveform(
                    self.current_view_range[0],
                    self.current_view_range[1],
                    self.current_selection_range[0],
                    self.current_selection_range[1],
                    self._calculate_adaptive_zoom_level(
                        self.current_selection_range[0],
                        self.current_selection_range[1]
                    )
                )

                # 保存圖像
                if self.waveform_image:
                    self.waveform_image.save(filename)

                # 恢復原始尺寸和設置
                self.width, self.height = orig_width, orig_height
                self.high_quality = old_quality

                # 重新渲染原始大小的圖像
                self._draw_waveform(
                    self.current_view_range[0],
                    self.current_view_range[1],
                    self.current_selection_range[0],
                    self.current_selection_range[1],
                    self._calculate_adaptive_zoom_level(
                        self.current_selection_range[0],
                        self.current_selection_range[1]
                    )
                )
            else:
                # 直接保存當前圖像
                if self.waveform_image:
                    self.waveform_image.save(filename)

            return True

        except Exception as e:
            self.logger.error(f"導出波形圖像時出錯: {e}")
            return False