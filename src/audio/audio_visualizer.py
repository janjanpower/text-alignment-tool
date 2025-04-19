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

    def create_waveform(self, audio_segment: AudioSegment) -> None:
        """
        創建音頻波形圖
        :param audio_segment: 音頻段落
        """
        try:
            # 獲取音頻數據
            samples = np.array(audio_segment.get_array_of_samples())

            # 如果是立體聲，轉換為單聲道
            if audio_segment.channels == 2:
                samples = samples.reshape((-1, 2))
                samples = samples.mean(axis=1)

            # 降采樣以適應顯示寬度
            points_per_pixel = max(1, len(samples) // self.width)
            downsampled = samples[::points_per_pixel]

            # 正規化數據
            if len(downsampled) > 0:
                normalized = downsampled / np.max(np.abs(downsampled))
            else:
                normalized = np.array([0])

            # 創建圖像
            img = Image.new('RGBA', (self.width, self.height), (30, 30, 30, 255))
            draw = ImageDraw.Draw(img)

            # 繪製波形 - 繪製中心線
            center_y = self.height // 2
            draw.line([(0, center_y), (self.width, center_y)], fill=(70, 70, 70, 255))

            # 繪製波形本身 - 使用更平滑的方式
            for x in range(min(len(normalized), self.width)):
                sample = normalized[x]
                y_offset = int(sample * (self.height // 2 - 5))  # 留出一些邊距
                y1 = center_y - y_offset
                y2 = center_y + y_offset

                # 使用漸變效果
                if y_offset > 0:
                    # 上半部分使用漸變藍色
                    for y in range(center_y, y1, -1):
                        alpha = int(255 * (center_y - y) / y_offset)
                        draw.point((x, y), fill=(79, 195, 247, alpha))

                    # 下半部分使用漸變藍色
                    for y in range(center_y, y2):
                        alpha = int(255 * (y - center_y) / y_offset)
                        draw.point((x, y), fill=(79, 195, 247, alpha))
                else:
                    # 如果沒有波形，畫一條垂直線
                    draw.line([(x, center_y - 1), (x, center_y + 1)], fill=(79, 195, 247, 128))

            # 保存為 PhotoImage
            self.waveform_image = img
            self.waveform_photo = ImageTk.PhotoImage(img)

            # 在畫布上顯示
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)

            # 更新音頻持續時間
            self.audio_duration = len(audio_segment) / 1000.0  # 轉換為秒

        except Exception as e:
            self.logger.error(f"創建波形圖時出錯: {e}")

    def update_selection(self, start_ms: int, end_ms: int) -> None:
        """
        更新選擇區域
        :param start_ms: 開始時間（毫秒）
        :param end_ms: 結束時間（毫秒）
        """
        try:
            if not self.waveform_image:
                return

            # 計算在圖像上的像素位置
            total_ms = self.audio_duration * 1000
            if total_ms <= 0:
                return

            start_x = int(start_ms / total_ms * self.width)
            end_x = int(end_ms / total_ms * self.width)

            # 確保在範圍內
            start_x = max(0, min(start_x, self.width))
            end_x = max(0, min(end_x, self.width))

            # 更新選擇區域
            self.selection_start = start_x
            self.selection_end = end_x

            # 重繪波形和選擇區域
            self._redraw_with_selection()

            # 如果選擇區域很小，顯示放大效果
            if abs(end_x - start_x) < 20:  # 如果選擇區域小於20像素
                self._show_zoomed_view(start_ms, end_ms)

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