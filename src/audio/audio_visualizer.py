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
        """
        初始化音頻可視化器
        :param parent: 父視窗元件
        :param width: 可視化區域寬度
        :param height: 可視化區域高度
        """
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
        self.selection_start = 0
        self.selection_end = 0
        self.audio_duration = 0

    def _create_empty_waveform(self, message="等待音頻..."):
            """創建空白波形圖"""
            try:
                # 確保尺寸有效
                w = max(10, self.width)
                h = max(10, self.height)

                # 創建空白圖像
                img = Image.new('RGBA', (w, h), (30, 30, 30, 255))
                draw = ImageDraw.Draw(img)

                # 繪製中心線
                center_y = h // 2
                draw.line([(0, center_y), (w, center_y)], fill=(70, 70, 70, 255), width=1)

                # 添加文字
                draw.text((10, center_y - 7), message, fill=(180, 180, 180, 255))

                # 更新圖像
                self.waveform_image = img
                self.waveform_photo = ImageTk.PhotoImage(img)

                # 顯示圖像
                self.canvas.delete("all")
                self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)

                # 更新畫布
                self.canvas.update_idletasks()

            except Exception as e:
                self.logger.error(f"創建空白波形出錯: {e}")

    def create_waveform(self, audio_segment: AudioSegment) -> None:
        """
        創建音頻波形圖，添加更嚴格的錯誤檢查
        :param audio_segment: 音頻段落
        """
        try:
            # 更嚴格的輸入驗證
            if audio_segment is None:
                self._create_empty_waveform("音頻段落為 None")
                return

            # 檢查音頻長度
            if len(audio_segment) == 0:
                self._create_empty_waveform("音頻段落為空")
                return

            # 設置音頻持續時間（毫秒）
            self.audio_duration = len(audio_segment)

            # 獲取音頻樣本，確保非空且有效
            try:
                samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
            except Exception as e:
                self.logger.error(f"無法獲取音頻樣本: {e}")
                self._create_empty_waveform(f"樣本獲取失敗: {e}")
                return

            # 處理立體聲
            if audio_segment.channels == 2:
                samples = samples.reshape((-1, 2)).mean(axis=1)

            # 確保樣本非空且有效
            if len(samples) == 0:
                self._create_empty_waveform("音頻樣本為空")
                return

            # 安全的正規化
            try:
                max_abs = np.max(np.abs(samples))
                samples = samples / max_abs if max_abs != 0 else np.zeros_like(samples)
            except Exception as e:
                self.logger.error(f"正規化樣本時出錯: {e}")
                samples = np.zeros_like(samples)

            # 降採樣
            samples_per_pixel = max(1, len(samples) // self.width)
            try:
                downsampled = np.array([
                    np.max(np.abs(samples[i * samples_per_pixel:(i + 1) * samples_per_pixel]))
                    for i in range(self.width)
                ])
            except Exception as e:
                self.logger.error(f"降採樣時出錯: {e}")
                downsampled = np.zeros(self.width)

            # 創建圖像
            img = Image.new('RGBA', (self.width, self.height), (30, 30, 30, 255))
            draw = ImageDraw.Draw(img)

            # 繪製中心線
            center_y = self.height // 2
            draw.line([(0, center_y), (self.width, center_y)], fill=(70, 70, 70, 255), width=1)

            # 繪製波形
            for x in range(self.width):
                amplitude = downsampled[x]
                wave_height = int(amplitude * (self.height // 2 - 4))
                y1 = center_y - wave_height
                y2 = center_y + wave_height
                draw.line([(x, y1), (x, y2)], fill=(100, 210, 255, 255), width=2)

            # 更新圖像
            self.waveform_image = img
            self.waveform_photo = ImageTk.PhotoImage(img)

            # 顯示
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)
            self.canvas.update_idletasks()

        except Exception as e:
            self.logger.error(f"創建波形圖時出錯: {e}")
            self._create_empty_waveform(f"錯誤: {str(e)}")

    def update_selection(self, start_ms: int, end_ms: int) -> None:
        """
        更新選擇區域，添加更嚴格的錯誤檢查
        :param start_ms: 開始時間（毫秒）- 相對於當前波形顯示範圍
        :param end_ms: 結束時間（毫秒）- 相對於當前波形顯示範圍
        """
        try:
            # 確保波形圖像存在
            if self.waveform_image is None:
                return

            # 計算像素位置 - 使用音頻持續時間而不是圖像長度
            if self.audio_duration <= 0:
                return

            # 將毫秒時間轉換為像素位置
            start_x = int((start_ms / self.audio_duration) * self.width)
            end_x = int((end_ms / self.audio_duration) * self.width)

            # 確保在有效範圍內
            start_x = max(0, min(start_x, self.width))
            end_x = max(start_x, min(end_x, self.width))

            # 如果高亮區太窄，至少顯示2像素寬度
            if end_x - start_x < 2:
                end_x = min(start_x + 2, self.width)

            # 創建新圖像
            img = self.waveform_image.copy()

            # 創建透明遮罩來實現半透明效果（50% 透明度）
            overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)

            # 繪製選擇區域（50% 透明藍色）
            overlay_draw.rectangle(
                [(start_x, 0), (end_x, self.height)],
                fill=(79, 195, 247, 128)  # 藍色，128 = 50% 透明度
            )

            # 將遮罩合併到原始圖像
            img = Image.alpha_composite(img.convert('RGBA'), overlay)
            draw = ImageDraw.Draw(img)

            # 繪製邊界（使用更明顯的藍色邊框）
            draw.line(
                [(start_x, 0), (start_x, self.height)],
                fill=(79, 195, 247, 255), width=2  # 完全不透明的藍色邊框
            )
            draw.line(
                [(end_x, 0), (end_x, self.height)],
                fill=(79, 195, 247, 255), width=2  # 完全不透明的藍色邊框
            )

            # 更新顯示
            self.waveform_photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)
            self.canvas.update_idletasks()

        except Exception as e:
            self.logger.error(f"更新選擇區域時出錯: {e}")

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

    def clear_waveform(self) -> None:
        """清除波形圖"""
        try:
            # 檢查控件是否仍然存在
            if self.canvas and self.canvas.winfo_exists():
                self.canvas.delete("all")

            # 清理圖像資源
            self.waveform_image = None
            self.waveform_photo = None

        except tk.TclError:
            # 控件可能已經被銷毀
            pass
        except Exception as e:
            self.logger.error(f"清除波形圖時出錯: {e}")

    def show(self) -> None:
        """顯示波形容器"""
        self.canvas.pack(side=tk.TOP, pady=(2, 0))

    def hide(self) -> None:
        """隱藏波形容器"""
        try:
            if self.canvas and self.canvas.winfo_exists():
                self.canvas.pack_forget()
        except tk.TclError:
            # 控件可能已經被銷毀
            pass
        except Exception as e:
            self.logger.error(f"隱藏波形容器時出錯: {e}")