import logging
import tkinter as tk
from tkinter import ttk
from typing import Optional, Tuple
import numpy as np
from PIL import Image, ImageTk, ImageDraw
from pydub import AudioSegment


class AudioVisualizer:
    """音頻可視化類別 - 重構版本"""

    def __init__(self, parent, width=100, height=45):
        """
        初始化音頻可視化器
        :param parent: 父容器
        :param width: 可視化區域寬度
        :param height: 可視化區域高度
        """
        # 基本設定
        self.logger = logging.getLogger("AudioVisualizer")
        self.parent = parent
        self.width = max(10, width)  # 確保最小寬度
        self.height = max(10, height)  # 確保最小高度

        # 確保父容器已準備好
        self.parent.update_idletasks()

        # 直接使用 Frame 作為主容器，避免在複雜佈局中的問題
        self.frame = tk.Frame(
            parent,
            bg="#1E1E1E",
            width=self.width,
            height=self.height
        )
        self.frame.pack_propagate(False)  # 防止被子元素影響尺寸

        # 創建畫布
        self.canvas = tk.Canvas(
            self.frame,
            width=self.width,
            height=self.height,
            bg="#1E1E1E",
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 波形相關變數
        self.waveform_image = None
        self.waveform_photo = None
        self.selection_start = 0
        self.selection_end = 0
        self.audio_duration = 0

        # 創建初始空白波形
        self._create_empty_waveform("等待音頻數據...")

        # 調試日誌
        self.logger.debug(f"AudioVisualizer 初始化完成: {self.width}x{self.height}")

    def create_waveform(self, audio_segment: AudioSegment) -> None:
        """
        創建音頻波形圖
        :param audio_segment: 音頻段落
        """
        try:
            # 檢查輸入參數
            if audio_segment is None or len(audio_segment) == 0:
                self.logger.warning("無效的音頻段落")
                self._create_empty_waveform("無效音頻數據")
                return

            # 設置音頻持續時間
            self.audio_duration = len(audio_segment)
            self.logger.debug(f"音頻長度: {self.audio_duration}ms")

            # 確保畫布尺寸正確
            actual_width = max(10, self.frame.winfo_width())
            actual_height = max(10, self.frame.winfo_height())

            if actual_width != self.width or actual_height != self.height:
                self.logger.debug(f"調整尺寸: {self.width}x{self.height} -> {actual_width}x{actual_height}")
                self.width = actual_width
                self.height = actual_height
                self.canvas.config(width=self.width, height=self.height)

            # 獲取音頻樣本
            samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)

            # 處理立體聲
            if audio_segment.channels == 2:
                if len(samples) % 2 == 0:
                    samples = samples.reshape((-1, 2)).mean(axis=1)
                else:
                    samples = samples[:-1].reshape((-1, 2)).mean(axis=1)

            # 正規化
            if len(samples) > 0 and samples.max() != 0:
                samples = samples / np.max(np.abs(samples))
            else:
                self.logger.warning("音頻樣本無效或為靜音")
                samples = np.zeros(100, dtype=np.float32)  # 靜音時顯示平直線

            # 降採樣到視圖寬度
            if len(samples) > self.width:
                # 計算每像素對應的樣本數
                samples_per_pixel = max(1, len(samples) // self.width)
                downsampled = []

                for i in range(self.width):
                    start_idx = min(i * samples_per_pixel, len(samples) - 1)
                    end_idx = min((i + 1) * samples_per_pixel, len(samples))

                    if start_idx < end_idx:
                        # 取該段樣本的最大絕對值作為振幅
                        chunk = samples[start_idx:end_idx]
                        amplitude = np.max(np.abs(chunk)) if len(chunk) > 0 else 0
                        downsampled.append(amplitude)
                    else:
                        downsampled.append(0)

                samples = np.array(downsampled)

            # 創建圖像
            img = Image.new('RGBA', (self.width, self.height), (30, 30, 30, 255))
            draw = ImageDraw.Draw(img)

            # 繪製中心線
            center_y = self.height // 2
            draw.line([(0, center_y), (self.width, center_y)], fill=(70, 70, 70, 255), width=1)

            # 繪製波形
            for x in range(min(len(samples), self.width)):
                amplitude = samples[x]
                # 確保至少有1像素的高度
                wave_height = max(1, int(amplitude * (self.height // 2 - 4)))

                # 繪製波形線
                y1 = center_y - wave_height
                y2 = center_y + wave_height
                draw.line([(x, y1), (x, y2)], fill=(100, 210, 255, 255), width=2)

            # 保存為PhotoImage並顯示
            self.waveform_image = img
            self.waveform_photo = ImageTk.PhotoImage(img)

            # 更新畫布
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo, tags="waveform")

            # 重置選擇區域
            self.selection_start = 0
            self.selection_end = 0

            # 強制更新
            self.canvas.update_idletasks()
            self.logger.debug("波形創建成功")

        except Exception as e:
            self.logger.error(f"創建波形圖出錯: {e}", exc_info=True)
            self._create_empty_waveform(f"錯誤: {str(e)[:20]}...")

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
            try:
                draw.text((10, center_y - 7), message, fill=(180, 180, 180, 255))
            except Exception:
                # 如果文字繪製出錯，使用簡單的線條表示
                for i in range(0, w, 10):
                    draw.line([(i, center_y - 3), (i + 5, center_y + 3)], fill=(180, 180, 180, 255), width=1)

            # 更新圖像
            self.waveform_image = img
            self.waveform_photo = ImageTk.PhotoImage(img)

            # 顯示圖像
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo, tags="empty")

            # 更新畫布
            self.canvas.update_idletasks()

        except Exception as e:
            self.logger.error(f"創建空白波形出錯: {e}")

    def update_selection(self, start_ms: int, end_ms: int) -> None:
        """
        更新選擇區域
        :param start_ms: 開始時間（毫秒）
        :param end_ms: 結束時間（毫秒）
        """
        try:
            # 確保波形圖已創建
            if self.waveform_image is None:
                return

            # 確保音頻持續時間有效
            if self.audio_duration <= 0:
                return

            # 確保值有效
            start_ms = max(0, int(start_ms))
            end_ms = max(start_ms, int(end_ms))

            # 限制在音頻範圍內
            start_ms = min(start_ms, self.audio_duration)
            end_ms = min(end_ms, self.audio_duration)

            # 計算像素位置
            start_x = int((start_ms / self.audio_duration) * self.width)
            end_x = int((end_ms / self.audio_duration) * self.width)

            # 確保在畫布範圍內
            start_x = max(0, min(start_x, self.width - 1))
            end_x = max(start_x, min(end_x, self.width - 1))

            # 更新存儲的選擇區域
            self.selection_start = start_x
            self.selection_end = end_x

            # 重繪帶選擇區域的波形
            self._redraw_with_selection()

        except Exception as e:
            self.logger.error(f"更新選擇區域出錯: {e}")

    def _redraw_with_selection(self):
        """重繪波形並標記選擇區域"""
        try:
            if self.waveform_image is None:
                return

            # 複製原始波形圖像
            img = self.waveform_image.copy()

            # 如果有選擇區域
            if self.selection_start < self.selection_end:
                # 創建新的圖層
                overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(overlay)

                # 繪製選擇區域
                draw.rectangle(
                    [(self.selection_start, 0), (self.selection_end, self.height)],
                    fill=(79, 195, 247, 80)  # 藍色半透明
                )

                # 繪製邊框
                draw.line(
                    [(self.selection_start, 0), (self.selection_start, self.height)],
                    fill=(79, 195, 247, 200), width=2
                )
                draw.line(
                    [(self.selection_end, 0), (self.selection_end, self.height)],
                    fill=(79, 195, 247, 200), width=2
                )

                # 合併圖層
                img = Image.alpha_composite(img, overlay)

            # 更新顯示
            self.waveform_photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)

            # 更新畫布
            self.canvas.update_idletasks()

        except Exception as e:
            self.logger.error(f"重繪選擇區域出錯: {e}")

    def place(self, **kwargs):
        """設置可視化器位置"""
        self.frame.place(**kwargs)
        # 更新容器後重新設置畫布尺寸
        self.frame.update_idletasks()
        actual_width = self.frame.winfo_width()
        actual_height = self.frame.winfo_height()
        if actual_width > 0 and actual_height > 0:
            self.width = actual_width
            self.height = actual_height
            self.canvas.config(width=self.width, height=self.height)
            # 如果已有波形，重新繪製
            if self.waveform_image is not None:
                self._redraw_with_selection()

    def pack(self, **kwargs):
        """使用pack佈局管理器"""
        self.frame.pack(**kwargs)
        self.frame.update_idletasks()
        self._update_dimensions()

    def grid(self, **kwargs):
        """使用grid佈局管理器"""
        self.frame.grid(**kwargs)
        self.frame.update_idletasks()
        self._update_dimensions()

    def _update_dimensions(self):
        """更新尺寸和重繪波形"""
        try:
            self.frame.update_idletasks()
            w = self.frame.winfo_width()
            h = self.frame.winfo_height()

            if w > 0 and h > 0:
                self.width = w
                self.height = h
                self.canvas.config(width=w, height=h)

                # 如果已有波形，需要重新創建以匹配新尺寸
                if self.waveform_image is not None:
                    self._create_empty_waveform("調整尺寸中...")
        except Exception as e:
            self.logger.error(f"更新尺寸時出錯: {e}")

    def show(self):
        """顯示可視化器"""
        try:
            # 如果使用了place，確保正確顯示
            if not self.frame.winfo_ismapped():
                info = self.frame.place_info()
                if info:  # 如果有place信息
                    self.frame.place(info)
                else:  # 否則使用默認位置
                    self.frame.place(x=0, y=0, width=self.width, height=self.height)

            # 確保畫布尺寸正確
            self.canvas.config(width=self.width, height=self.height)

            # 如果有波形，確保顯示
            if self.waveform_photo:
                self.canvas.delete("all")
                self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)

            # 強制更新
            self.frame.update_idletasks()
            self.canvas.update_idletasks()

        except Exception as e:
            self.logger.error(f"顯示可視化器時出錯: {e}")

    def hide(self):
        """隱藏可視化器"""
        try:
            self.frame.place_forget()
        except Exception as e:
            self.logger.error(f"隱藏可視化器時出錯: {e}")

    def clear(self):
        """清除波形"""
        try:
            self.canvas.delete("all")
            self.waveform_image = None
            self.waveform_photo = None
            self.audio_duration = 0
            self.selection_start = 0
            self.selection_end = 0
        except Exception as e:
            self.logger.error(f"清除波形時出錯: {e}")

    def destroy(self):
        """銷毀可視化器"""
        try:
            # 清理資源
            self.clear()
            # 銷毀畫布和框架
            self.canvas.destroy()
            self.frame.destroy()
        except Exception as e:
            self.logger.error(f"銷毀可視化器時出錯: {e}")