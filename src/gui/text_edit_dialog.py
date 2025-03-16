"""文字編輯對話框模組"""
import os
import sys

# 添加項目根目錄到 Python 路徑
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import logging
import tkinter as tk
from tkinter import ttk, simpledialog

import pysrt
from gui.custom_messagebox import show_error
from utils.time_utils import parse_time,format_time


class TextEditDialog(simpledialog.Dialog):
    def __init__(self, parent: tk.Tk, title: str, initial_text: str = "",
             start_time: str = "", end_time: str = "",
             column_index: int = 4, display_mode: str = "srt", fps: int = 30,
             word_text: str = "", edit_mode: str = "srt"):  # 增加 word_text 和 edit_mode 參數
        self.display_mode = display_mode
        self.initial_text = str(initial_text)
        self.word_text = str(word_text)  # 保存 Word 文本
        self.edit_mode = edit_mode       # 編輯模式：'srt', 'word', 'both'
        self.start_time = format_time(parse_time(start_time)) if start_time else start_time
        self.end_time = format_time(parse_time(end_time)) if end_time else end_time
        self.column_index = column_index
        self.fps = fps
        self.result = None

        # 檢查是否為允許編輯的欄位
        if self.display_mode == "audio_srt" and column_index not in [4, 5]:
            return
        elif self.display_mode == "srt" and column_index not in [3, 4]:
            return
        elif self.display_mode in ["srt_word", "all"] and column_index not in [3, 4, 5]:
            return

        super().__init__(parent, title)

    def set_focus(self):
        """設置焦點到文字編輯器"""
        if hasattr(self, 'word_text_widget') and self.word_text_widget and self.edit_mode == 'word':
            self.word_text_widget.focus_force()
            self.word_text_widget.mark_set("insert", "1.0")
        else:
            self.text_widget.focus_force()
            self.text_widget.mark_set("insert", "1.0")


    def body(self, master):
        self.setup_styles()

        # 初始化 word_text_widget 為 None，確保屬性始終存在
        self.word_text_widget = None

        # 判斷是否顯示 Word 文本編輯區
        show_word_edit = self.display_mode in ["srt_word", "all"] and self.word_text and self.edit_mode in ['word', 'both']

        self.create_widgets(master, show_word_edit)
        self.overrideredirect(True)

        # 設置焦點到文字編輯器
        self.after(100, self.set_focus)

        return self.text_widget

    def setup_styles(self):
        style = ttk.Style()
        style.configure("TextEdit.TFrame")
        style.configure("TextEdit.TLabel", background="#404040", foreground="white",font=("Arial", 10))
        style.configure("TextEdit.TButton", padding=5)

    def create_widgets(self, master, show_word_edit=False):
        # 創建標題列
        self.title_bar = tk.Frame(self, bg='#404040', relief='raised', bd=0)
        self.title_bar.pack(fill=tk.X)

        # 標題標籤 - 注意這裡使用 tk.Label 而不是 ttk.Label
        self.title_label = tk.Label(
            self.title_bar,
            text=self.title(),
            bg="#404040",  # 設置背景色
            fg="white",    # 設置前景色
            font=("Arial", 10)
        )
        self.title_label.pack(side=tk.LEFT, pady=5, padx=5)

        # 關閉按鈕
        self.close_button = tk.Button(
            self.title_bar,
            text="×",
            command=self.cancel,
            bg="#404040",
            fg="white",
            bd=0,
            font=("Arial", 12),
            width=3,
            cursor="hand2"
        )
        self.close_button.pack(side=tk.RIGHT)

        # 綁定拖曳事件
        self.title_bar.bind("<Button-1>", self.start_move)
        self.title_bar.bind("<B1-Motion>", self.do_move)

        # 主要內容框架
        self.main_frame = ttk.Frame(master, padding="10", style="TextEdit.TFrame")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 根據是否顯示 Word 編輯區決定佈局
        if show_word_edit:
            # 使用 PanedWindow 或 Frame+Frame 組合來分隔兩個編輯區
            self.edit_container = ttk.PanedWindow(self.main_frame, orient=tk.VERTICAL)
            self.edit_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            # SRT 編輯區
            srt_frame = ttk.LabelFrame(self.edit_container, text="SRT 文本")
            self.edit_container.add(srt_frame, weight=1)

            # 文本編輯器
            self.text_widget = tk.Text(
                srt_frame,
                wrap=tk.WORD,
                font=("Arial", 12),
                undo=True,
                padx=5,
                pady=5,
                bg="white",
                relief="solid",
                state=tk.NORMAL if self.edit_mode in ['srt', 'both'] else tk.DISABLED
            )
            self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # SRT 卷軸
            srt_scrollbar = ttk.Scrollbar(
                srt_frame,
                orient=tk.VERTICAL,
                command=self.text_widget.yview
            )
            srt_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.text_widget.configure(yscrollcommand=srt_scrollbar.set)

            # 插入初始文本
            self.text_widget.insert("1.0", self.initial_text)

            # Word 編輯區
            word_frame = ttk.LabelFrame(self.edit_container, text="Word 文本")
            self.edit_container.add(word_frame, weight=1)

            # Word 文本編輯器
            self.word_text_widget = tk.Text(
                word_frame,
                wrap=tk.WORD,
                font=("Arial", 12),
                undo=True,
                padx=5,
                pady=5,
                bg="white",
                relief="solid",
                state=tk.NORMAL if self.edit_mode in ['word', 'both'] else tk.DISABLED
            )
            self.word_text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # Word 卷軸
            word_scrollbar = ttk.Scrollbar(
                word_frame,
                orient=tk.VERTICAL,
                command=self.word_text_widget.yview
            )
            word_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.word_text_widget.configure(yscrollcommand=word_scrollbar.set)

            # 插入 Word 文本
            self.word_text_widget.insert("1.0", self.word_text)
        else:
            # 原有的單一編輯區佈局
            editor_frame = ttk.Frame(self.main_frame, style="TextEdit.TFrame")
            editor_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            # 文本編輯器
            self.text_widget = tk.Text(
                editor_frame,
                wrap=tk.WORD,
                font=("Arial", 12),
                undo=True,
                padx=5,
                pady=5,
                bg="white",
                relief="solid"
            )
            self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # 卷軸
            scrollbar = ttk.Scrollbar(
                editor_frame,
                orient=tk.VERTICAL,
                command=self.text_widget.yview
            )
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.text_widget.configure(yscrollcommand=scrollbar.set)

            # 插入初始文本
            self.text_widget.insert("1.0", self.initial_text)

        # 時間資訊框架
        info_frame = ttk.Frame(self.main_frame, style="TextEdit.TFrame")
        info_frame.pack(fill=tk.X, padx=5, pady=5)

        # 時間資訊標籤
        ttk.Label(
            info_frame,
            text=f"時間範圍: {self.start_time} - {self.end_time}",
            style="TextEdit.TLabel",
            background="#f0f0f0",
            foreground="black",
            font=("Arial", 12)
        ).pack(pady=2)
    def buttonbox(self):
        button_frame = ttk.Frame(self.main_frame, style="TextEdit.TFrame")
        button_frame.pack(side=tk.BOTTOM, pady=5)
        ok_button = ttk.Button(button_frame, text="確定", command=self.ok, style="TextEdit.TButton", width=10)
        ok_button.pack(side=tk.LEFT, padx=5)
        cancel_button = ttk.Button(button_frame, text="取消", command=self.cancel, style="TextEdit.TButton", width=10)
        cancel_button.pack(side=tk.LEFT, padx=5)

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

    def generate_time_segments(self, lines):
        """
        根據文本行生成對應的時間戳
        :param lines: 文本行列表
        :return: 包含文本、開始時間、結束時間的列表
        """
        start_time = parse_time(str(self.start_time))
        end_time = parse_time(str(self.end_time))
        total_duration = (end_time.ordinal - start_time.ordinal)
        total_chars = sum(len(line) for line in lines)

        current_time = start_time
        results = []

        for i, line in enumerate(lines):
            if not line.strip():
                continue

            # 計算該行的時間比例
            if i == len(lines) - 1:
                next_time = end_time
            else:
                line_proportion = len(line) / total_chars
                time_duration = int(total_duration * line_proportion)
                next_time = pysrt.SubRipTime.from_ordinal(current_time.ordinal + time_duration)

            results.append((
                line.strip(),                # 文本
                format_time(current_time),   # 開始時間
                format_time(next_time)       # 結束時間
            ))
            current_time = next_time

        return results

    def apply(self):
        """處理確定按鈕事件，根據編輯模式生成結果"""
        try:
            # 檢查是否為 Word 編輯且需要分割
            if self.edit_mode == 'word' and hasattr(self, 'word_text_widget') and self.word_text_widget:
                word_text = self.word_text_widget.get("1.0", tk.END).strip()

                # 檢查是否需要分割 Word 文本
                if '\n' in word_text:
                    lines = [line.strip() for line in word_text.split('\n') if line.strip()]
                    if len(lines) > 1:
                        # 使用與 SRT 相同的邏輯生成分割結果
                        self.result = self.generate_time_segments(lines)
                        return
                    else:
                        self.result = word_text
                        return
                else:
                    self.result = word_text
                    return

            # 檢查是否為分離式編輯
            elif hasattr(self, 'word_text_widget') and self.word_text_widget and self.display_mode in ["srt_word", "all"]:
                # 分離式編輯結果包含兩部分
                srt_text = self.text_widget.get("1.0", tk.END).strip()
                word_text = self.word_text_widget.get("1.0", tk.END).strip()

                # 記錄哪個文本被編輯了
                edited_parts = []
                if self.edit_mode in ['srt', 'both'] and srt_text != self.initial_text:
                    edited_parts.append('srt')
                if self.edit_mode in ['word', 'both'] and word_text != self.word_text:
                    edited_parts.append('word')

                # 設置結果
                self.result = {
                    'srt_text': srt_text,
                    'word_text': word_text,
                    'edited': edited_parts,
                    'split': False  # 不拆分文本
                }
                return

            # 處理普通 SRT 編輯
            text = self.text_widget.get("1.0", tk.END).strip()

            lines = [line.strip() for line in text.split('\n') if line.strip()]

            # 基本驗證
            if not lines:
                show_error("錯誤", "文本不能為空", self.parent)
                return

            # 如果只有一行文本，不需要拆分，直接返回文本字符串
            if len(lines) == 1 and '\n' not in text:
                self.result = text
                return

            # 以下是多行文本的拆分處理邏輯
            if not self.start_time or not self.end_time:
                show_error("錯誤", "開始時間或結束時間無效", self.parent)
                return

            # 解析時間
            try:
                start_time = parse_time(str(self.start_time))
                end_time = parse_time(str(self.end_time))
                total_duration = (end_time.ordinal - start_time.ordinal)

                if total_duration <= 0:
                    show_error("錯誤", "結束時間必須大於開始時間", self.parent)
                    return

            except ValueError as e:
                show_error("錯誤", f"時間格式解析錯誤：{str(e)}", self.parent)
                return

            # 計算時間分配
            total_chars = sum(len(line) for line in lines)
            if total_chars == 0:
                show_error("錯誤", "文本內容無效", self.parent)
                return

            # 生成時間分段
            self.result = self.generate_time_segments(lines)

        except Exception as e:
            error_msg = f"處理文本時出錯：{str(e)}"
            logging.error(error_msg, exc_info=True)
            show_error("錯誤", error_msg, self.parent)
            self.result = None

    def split_text_by_frames(self, lines):
        """按幀數拆分文本"""
        try:
            # 解析幀數
            start_frame = int(float(self.start_time))
            end_frame = int(float(self.end_time))
            total_frames = end_frame - start_frame

            if total_frames <= 0:
                show_error("錯誤", "結束時間必須大於開始時間", None)
                return None

            # 計算總字符數
            total_chars = sum(len(line) for line in lines)
            if total_chars == 0:
                show_error("錯誤", "文本不能為空", None)
                return None

            # 拆分處理
            current_frame = start_frame
            results = []

            for i, line in enumerate(lines):
                if not line.strip():
                    continue

                # 計算該行應占用的幀數
                if i == len(lines) - 1:
                    next_frame = end_frame
                else:
                    line_proportion = len(line) / total_chars
                    frame_count = int(total_frames * line_proportion)
                    next_frame = min(current_frame + frame_count, end_frame)

                results.append((line, str(current_frame), str(next_frame)))
                current_frame = next_frame

            return results

        except Exception as e:
            show_error("錯誤", f"拆分文本時出錯：{str(e)}", None)
            return None

    def split_text_by_time(self, lines):
        """按時間拆分文本"""
        try:
            # 解析時間
            start_time = parse_time(str(self.start_time))
            end_time = parse_time(str(self.end_time))
            total_duration = (end_time.ordinal - start_time.ordinal)

            # 計算總字符數
            total_chars = sum(len(line) for line in lines)
            if total_chars == 0:
                show_error("錯誤", "文本不能為空", None)
                return None

            # 拆分處理
            current_time = start_time
            results = []

            for i, line in enumerate(lines):
                if not line.strip():
                    continue

                # 計算該行的時間比例
                if i == len(lines) - 1:
                    next_time = end_time
                else:
                    line_proportion = len(line) / total_chars
                    time_duration = int(total_duration * line_proportion)
                    next_time = pysrt.SubRipTime.from_ordinal(current_time.ordinal + time_duration)

                # 只返回文本和時間信息
                results.append((
                    line.strip(),                # 文本
                    format_time(current_time),   # 開始時間
                    format_time(next_time)       # 結束時間
                ))
                current_time = next_time

            return results

        except Exception as e:
            show_error("錯誤", f"拆分文本時出錯：{str(e)}", None)
            return None

    def split_sentence(self, event):
        cursor_pos = self.text_widget.index(tk.INSERT)
        self.text_widget.insert(cursor_pos, '\n')
        return 'break'

    def show(self):
        self.wait_window()
        return self.result