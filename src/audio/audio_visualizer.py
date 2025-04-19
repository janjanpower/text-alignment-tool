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

    def __init__(self, parent: tk.Widget, width: int = 100, height: int = 45):
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
            highlightthickness=0,
            bd=0  # 無邊框
        )

        # 波形相關變數
        self.waveform_image = None
        self.waveform_photo = None
        self.selection_start = 0
        self.selection_end = 0
        self.audio_duration = 0.0  # 初始化音頻持續時間（秒）

        # 調試日誌
        self.logger.debug(f"AudioVisualizer 初始化完成: width={width}, height={height}")

    def create_waveform(self, audio_segment: AudioSegment) -> None:
        """
        創建音頻波形圖
        :param audio_segment: 音頻段落
        """
        try:
            # 確保音頻段落有效
            if not audio_segment or len(audio_segment) == 0:
                self.logger.error("音頻段落為空或無效")
                return

            # 設置音頻持續時間（秒）
            self.audio_duration = len(audio_segment) / 1000.0
            self.logger.debug(f"音頻持續時間: {self.audio_duration}秒")

            # 獲取音頻數據
            samples = audio_segment.get_array_of_samples()
            self.logger.debug(f"音頻樣本數: {len(samples)}, 通道數: {audio_segment.channels}")

            # 轉換為 numpy 數組
            samples_array = np.frombuffer(samples, dtype=np.int16)

            # 確保正確的數據轉換
            if audio_segment.channels == 2:
                # 確保能整除2
                if len(samples_array) % 2 != 0:
                    samples_array = samples_array[:-1]
                # 重塑為立體聲
                samples_array = samples_array.reshape((-1, 2))
                # 轉換為單聲道
                samples_array = samples_array.mean(axis=1)

            # 正規化到 -1 到 1 之間
            if samples_array.max() > 0:
                samples_array = samples_array.astype(np.float32) / 32768.0
            else:
                self.logger.warning("音頻數據中沒有有效振幅")
                samples_array = np.zeros_like(samples_array)

            # 降采樣到適合顯示的寬度
            if len(samples_array) > self.width:
                # 使用更穩定的降采樣方法
                samples_per_pixel = len(samples_array) / self.width
                downsampled = []

                for i in range(self.width):
                    start_idx = int(i * samples_per_pixel)
                    end_idx = int((i + 1) * samples_per_pixel)
                    if end_idx > start_idx:
                        # 取該區間內的最大絕對值
                        value = np.max(np.abs(samples_array[start_idx:end_idx]))
                        downsampled.append(value)
                    else:
                        downsampled.append(0)

                samples_array = np.array(downsampled)

            # 創建圖像
            img = Image.new('RGBA', (self.width, self.height), (30, 30, 30, 255))
            draw = ImageDraw.Draw(img)

            # 繪製中心線
            center_y = self.height // 2
            draw.line([(0, center_y), (self.width, center_y)], fill=(70, 70, 70, 255))

            # 繪製波形
            for x in range(min(len(samples_array), self.width)):
                sample = samples_array[x]

                # 計算波形高度
                wave_height = int(sample * (self.height // 2 - 2))

                # 確保至少有一些可見的波形
                if abs(wave_height) < 1 and abs(sample) > 0.005:
                    wave_height = 1 if sample > 0 else -1

                # 計算波形的頂部和底部位置
                top_y = center_y - abs(wave_height)
                bottom_y = center_y + abs(wave_height)

                # 繪製波形線條 - 使用較粗的線條使波形更明顯
                draw.line([(x, top_y), (x, bottom_y)], fill=(100, 210, 255, 255), width=2)

            # 保存為 PhotoImage
            self.waveform_image = img
            self.waveform_photo = ImageTk.PhotoImage(img)

            # 在畫布上顯示
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)

            # 強制更新畫布
            self.canvas.update_idletasks()

            self.logger.debug(f"波形創建完成，樣本點數：{len(samples_array)}")

        except Exception as e:
            self.logger.error(f"創建波形圖時出錯: {e}")
            self.logger.exception(e)

    def update_selection(self, start_ms: int, end_ms: int) -> None:
        """
        更新選擇區域
        :param start_ms: 開始時間（毫秒）
        :param end_ms: 結束時間（毫秒）
        """
        try:
            # 檢查波形是否存在
            if not self.waveform_image:
                self.logger.error("波形圖像不存在")
                return

            # 檢查音頻持續時間是否已設置
            if self.audio_duration <= 0:
                self.logger.error(f"音頻持續時間未設置或無效: {self.audio_duration}")
                return

            self.logger.debug(f"收到選擇區域: {start_ms}ms-{end_ms}ms")

            # 計算在圖像上的像素位置
            total_ms = self.audio_duration * 1000

            if total_ms > 0:
                start_x = int((start_ms / total_ms) * self.width)
                end_x = int((end_ms / total_ms) * self.width)
            else:
                self.logger.error("音頻總時長為0")
                return

            # 確保在範圍內
            start_x = max(0, min(start_x, self.width))
            end_x = max(0, min(end_x, self.width))

            self.logger.debug(f"計算出像素位置: {start_x}px-{end_x}px")

            # 更新選擇區域
            self.selection_start = start_x
            self.selection_end = end_x

            # 重繪波形和選擇區域
            self._redraw_with_selection()

            # 強制更新畫布
            self.canvas.update_idletasks()

        except Exception as e:
            self.logger.error(f"更新選擇區域時出錯: {e}")
            self.logger.exception(e)

    def _redraw_with_selection(self):
        """重繪波形並突出顯示選擇區域"""
        try:
            if not self.waveform_image:
                return

            # 創建新圖像
            img = self.waveform_image.copy()

            # 如果有選擇區域，繪製高亮
            if self.selection_start != self.selection_end:
                overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)

                # 繪製半透明的選擇區域
                overlay_draw.rectangle(
                    [(self.selection_start, 0), (self.selection_end, self.height)],
                    fill=(79, 195, 247, 100)  # 藍色半透明
                )

                # 合併圖層
                img = Image.alpha_composite(img.convert('RGBA'), overlay)
                draw = ImageDraw.Draw(img)

                # 繪製邊緣線
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
        try:
            self.logger.debug("調用 show() 方法")

            # 直接使用 place 方法顯示，避免使用 pack 導致的佈局問題
            self.canvas.place(x=0, y=0, width=self.width, height=self.height)

            # 確保容器尺寸正確
            self.canvas.config(width=self.width, height=self.height)

            # 先更新父容器再更新自己
            if self.parent and self.parent.winfo_exists():
                self.parent.update_idletasks()

            # 更新畫布
            self.canvas.update_idletasks()

            # 確保圖像顯示正確
            if self.waveform_photo:
                self.canvas.delete("all")
                self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)

            # 檢查畫布狀態
            self.logger.debug(f"畫布狀態 - exists: {self.canvas.winfo_exists()}, viewable: {self.canvas.winfo_viewable()}, mapped: {self.canvas.winfo_ismapped()}")
            self.logger.debug(f"畫布尺寸: {self.canvas.winfo_width()}x{self.canvas.winfo_height()}")

        except Exception as e:
            self.logger.error(f"顯示波形容器時出錯: {e}")
            self.logger.exception(e)

    def hide(self) -> None:
        """隱藏波形容器"""
        try:
            if self.canvas and self.canvas.winfo_exists():
                self.canvas.place_forget()
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
            self.audio_duration = 0.0  # 重置音頻持續時間

        except tk.TclError:
            pass
        except Exception as e:
            self.logger.error(f"清除波形圖時出錯: {e}")