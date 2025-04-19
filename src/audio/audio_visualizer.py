import os
import logging
import tkinter as tk
from tkinter import ttk
from typing import Optional, Tuple
import numpy as np
from PIL import Image, ImageTk, ImageDraw
from pydub import AudioSegment


class AudioVisualizer:
    """音頻可視化類別"""


    def __init__(self, parent: tk.Widget, width: int = 100, height: int = 50):
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

    def _preprocess_audio(self, audio_segment):
        """預處理音頻數據，只處理一次"""
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

        return samples

    def set_audio_segment(self, audio_segment: AudioSegment) -> None:
        """設置音頻段落並預處理"""
        if audio_segment is None or len(audio_segment) == 0:
            self._create_empty_waveform("無效的音頻段落")
            return

        self.original_audio = audio_segment
        self.audio_duration = len(audio_segment)
        # 預處理並緩存音頻數據
        self.samples_cache = self._preprocess_audio(audio_segment)
        self.logger.debug(f"音頻預處理完成，樣本數: {len(self.samples_cache)}")

    def update_waveform_and_selection(self, view_range: Tuple[int, int], selection_range: Tuple[int, int]) -> None:
        """即時更新波形和選擇區域"""
        try:
            if self.samples_cache is None:
                self._create_empty_waveform("未設置音頻數據")
                return

            # 確保範圍有效
            view_start, view_end = view_range
            sel_start, sel_end = selection_range

            view_start = max(0, view_start)
            view_end = min(self.audio_duration, view_end)

            if view_end <= view_start:
                self._create_empty_waveform("無效的視圖範圍")
                return

            # 計算樣本範圍
            start_sample = int(view_start * len(self.samples_cache) / self.audio_duration)
            end_sample = int(view_end * len(self.samples_cache) / self.audio_duration)

            # 獲取顯示區域的樣本
            display_samples = self.samples_cache[start_sample:end_sample]

            if len(display_samples) == 0:
                self._create_empty_waveform("沒有可顯示的數據")
                return

            # 降採樣
            samples_per_pixel = max(1, len(display_samples) // self.width)
            downsampled = []

            for i in range(self.width):
                start_idx = i * samples_per_pixel
                end_idx = min(start_idx + samples_per_pixel, len(display_samples))

                if start_idx < len(display_samples) and end_idx > start_idx:
                    segment = display_samples[start_idx:end_idx]
                    downsampled.append(np.max(np.abs(segment)))
                else:
                    downsampled.append(0)

            downsampled = np.array(downsampled)

            # 創建圖像
            img = Image.new('RGBA', (self.width, self.height), (30, 30, 30, 255))
            draw = ImageDraw.Draw(img)

            # 繪製中心線
            center_y = self.height // 2
            draw.line([(0, center_y), (self.width, center_y)], fill=(70, 70, 70, 255), width=1)

            # 繪製波形
            for x in range(self.width):
                if x < len(downsampled):
                    amplitude = downsampled[x]
                    wave_height = int(amplitude * (self.height // 2 - 4))
                    y1 = center_y - wave_height
                    y2 = center_y + wave_height
                    draw.line([(x, y1), (x, y2)], fill=(100, 210, 255, 255), width=2)

            # 計算選擇區域在視圖中的位置
            view_duration = view_end - view_start
            if view_duration > 0 and sel_end > view_start and sel_start < view_end:
                # 計算相對位置
                relative_start = max(0, (sel_start - view_start) / view_duration)
                relative_end = min(1, (sel_end - view_start) / view_duration)

                # 轉換為像素位置
                start_x = int(relative_start * self.width)
                end_x = int(relative_end * self.width)

                # 確保有最小寬度
                if end_x - start_x < 2:
                    end_x = min(start_x + 2, self.width)

                # 繪製高亮區域
                overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)

                # 半透明藍色高亮
                overlay_draw.rectangle(
                    [(start_x, 0), (end_x, self.height)],
                    fill=(79, 195, 247, 100)  # 調整透明度
                )

                # 合併圖層
                img = Image.alpha_composite(img.convert('RGBA'), overlay)
                draw = ImageDraw.Draw(img)

                # 繪製邊界線
                draw.line([(start_x, 0), (start_x, self.height)], fill=(79, 195, 247, 255), width=2)
                draw.line([(end_x, 0), (end_x, self.height)], fill=(79, 195, 247, 255), width=2)

            # 更新顯示
            self.waveform_image = img
            self.waveform_photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)

            # 保存當前狀態
            self.current_view_range = view_range
            self.current_selection_range = selection_range

            # 強制立即更新顯示
            self.canvas.update()

        except Exception as e:
            self.logger.error(f"更新波形時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self._create_empty_waveform(f"錯誤: {str(e)}")

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

    def create_waveform(self, audio_segment: AudioSegment, initial_selection: Optional[Tuple[int, int]] = None) -> None:
        """
        創建音頻波形圖（初始化時使用）
        :param audio_segment: 音頻段落
        :param initial_selection: 初始選擇範圍 (start_ms, end_ms)
        """
        self.set_audio_segment(audio_segment)

        if self.original_audio is None:
            return

        if initial_selection is None:
            initial_selection = (0, len(self.original_audio))

        # 創建默認視圖（完整音頻）
        self.create_waveform_with_selection((0, len(self.original_audio)), initial_selection)

    def update_selection(self, start_ms: int, end_ms: int) -> None:
        """更新選擇區域（保持現有視圖範圍）"""
        if self.original_audio is None:
            return

        # 如果選擇區域改變，重新繪製
        if (start_ms, end_ms) != self.current_selection_range:
            self.create_waveform_with_selection(self.current_view_range, (start_ms, end_ms))

    def create_waveform_with_selection(self, view_range: Tuple[int, int], selection_range: Tuple[int, int]) -> None:
        """
        創建帶有選擇區域的波形圖
        :param view_range: 視圖範圍 (start_ms, end_ms)
        :param selection_range: 選擇範圍 (start_ms, end_ms)
        """
        try:
            if self.original_audio is None:
                self._create_empty_waveform("未設置音頻")
                return

            # 確保視圖範圍有效
            view_start, view_end = view_range
            view_start = max(0, min(view_start, self.audio_duration))
            view_end = max(view_start, min(view_end, self.audio_duration))

            # 確保範圍不為零
            if view_end <= view_start:
                self._create_empty_waveform("無效的視圖範圍")
                return

            # 切割音頻段
            display_audio = self.original_audio[view_start:view_end]

            # 檢查音頻段是否為空
            if len(display_audio) == 0:
                self._create_empty_waveform("音頻段為空")
                return

            # 獲取音頻樣本
            samples = np.array(display_audio.get_array_of_samples(), dtype=np.float32)

            # 檢查樣本是否為空
            if len(samples) == 0:
                self._create_empty_waveform("音頻樣本為空")
                return

            # 處理立體聲
            if display_audio.channels == 2:
                samples = samples.reshape((-1, 2)).mean(axis=1)

            # 正規化
            max_abs = np.max(np.abs(samples))
            if max_abs > 0:
                samples = samples / max_abs
            else:
                samples = np.zeros_like(samples)

            # 降採樣 - 修正部分
            samples_per_pixel = max(1, len(samples) // self.width)
            downsampled = []

            for i in range(self.width):
                start_idx = i * samples_per_pixel
                end_idx = min(start_idx + samples_per_pixel, len(samples))

                if start_idx < len(samples) and end_idx > start_idx:
                    segment = samples[start_idx:end_idx]
                    if len(segment) > 0:
                        downsampled.append(np.max(np.abs(segment)))
                    else:
                        downsampled.append(0)
                else:
                    downsampled.append(0)

            downsampled = np.array(downsampled)

            # 確保降採樣數組不為空
            if len(downsampled) == 0:
                self._create_empty_waveform("降採樣失敗")
                return

            # 創建圖像
            img = Image.new('RGBA', (self.width, self.height), (30, 30, 30, 255))
            draw = ImageDraw.Draw(img)

            # 繪製中心線
            center_y = self.height // 2
            draw.line([(0, center_y), (self.width, center_y)], fill=(70, 70, 70, 255), width=1)

            # 繪製波形
            for x in range(self.width):
                if x < len(downsampled):
                    amplitude = downsampled[x]
                    wave_height = int(amplitude * (self.height // 2 - 4))
                    y1 = center_y - wave_height
                    y2 = center_y + wave_height
                    draw.line([(x, y1), (x, y2)], fill=(100, 210, 255, 255), width=2)

            # 計算選擇區域在視圖中的相對位置
            sel_start, sel_end = selection_range
            view_duration = view_end - view_start

            if view_duration > 0 and sel_end > view_start and sel_start < view_end:
                # 計算相對位置
                relative_start = max(0, (sel_start - view_start) / view_duration)
                relative_end = min(1, (sel_end - view_start) / view_duration)

                # 轉換為像素位置
                start_x = int(relative_start * self.width)
                end_x = int(relative_end * self.width)

                # 確保有一定寬度
                if end_x - start_x < 2:
                    end_x = min(start_x + 2, self.width)

                # 創建高亮覆蓋層
                overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)

                # 繪製半透明藍色高亮區域
                overlay_draw.rectangle(
                    [(start_x, 0), (end_x, self.height)],
                    fill=(79, 195, 247, 128)  # 50% 透明度
                )

                # 合併圖層
                img = Image.alpha_composite(img.convert('RGBA'), overlay)
                draw = ImageDraw.Draw(img)

                # 繪製邊界線
                draw.line([(start_x, 0), (start_x, self.height)], fill=(79, 195, 247, 255), width=2)
                draw.line([(end_x, 0), (end_x, self.height)], fill=(79, 195, 247, 255), width=2)

            # 更新顯示
            self.waveform_image = img
            self.waveform_photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)

            # 保存當前狀態
            self.current_view_range = (view_start, view_end)
            self.current_selection_range = selection_range

            # 強制更新顯示
            self.canvas.update_idletasks()

        except Exception as e:
            self.logger.error(f"創建波形圖時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self._create_empty_waveform(f"錯誤: {str(e)}")

    def _show_zoomed_view(self, start_ms: int, end_ms: int) -> None:
        """
        顯示選擇區域的放大視圖
        :param start_ms: 開始時間（毫秒）
        :param end_ms: 結束時間（毫秒）
        """
        try:
            # 在選擇區域上方顯示一個放大的視圖框
            # 這裡只是示意，實際實現需要根據需求細化
            pass
        except Exception as e:
            self.logger.error(f"顯示放大視圖時出錯: {e}")

    def _redraw_with_selection(self) -> None:
        """重繪波形並突出顯示選擇區域"""
        try:
            if not self.waveform_image:
                return

            # 創建新圖像
            img = self.waveform_image.copy()
            draw = ImageDraw.Draw(img)

            # 繪製選擇區域（使用半透明高亮）
            if self.selection_start != self.selection_end:
                overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)
                overlay_draw.rectangle(
                    [(self.selection_start, 0), (self.selection_end, self.height)],
                    fill=(79, 195, 247, 100)  # 藍色半透明
                )
                img = Image.alpha_composite(img, overlay)

                # 在選擇區域的邊緣繪製線
                draw = ImageDraw.Draw(img)
                draw.line([(self.selection_start, 0), (self.selection_start, self.height)],
                         fill=(79, 195, 247, 255), width=2)
                draw.line([(self.selection_end, 0), (self.selection_end, self.height)],
                         fill=(79, 195, 247, 255), width=2)

            # 更新顯示
            self.waveform_photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)

        except Exception as e:
            self.logger.error(f"重繪波形時出錯: {e}")

    def show(self) -> None:
        """顯示波形容器"""
        self.canvas.pack(side=tk.TOP, pady=(2, 0))

    def hide(self) -> None:
        """隱藏波形容器"""
        try:
            if self.canvas and self.canvas.winfo_exists():
                self.canvas.pack_forget()
        except tk.TclError:
            pass
        except Exception as e:
            self.logger.error(f"隱藏波形容器時出錯: {e}")

    def clear_waveform(self) -> None:
        """清除波形圖"""
        try:
            if self.canvas and self.canvas.winfo_exists():
                self.canvas.delete("all")

            self.waveform_image = None
            self.waveform_photo = None

        except tk.TclError:
            pass
        except Exception as e:
            self.logger.error(f"清除波形圖時出錯: {e}")