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
from gui.custom_messagebox import show_error, show_warning
from utils.time_utils import parse_time, format_time
from services.text_processing.segmentation_service import SegmentationService


class TextEditDialog(simpledialog.Dialog):
    def __init__(self, parent: tk.Tk, title: str, initial_text: str = "",
             start_time: str = "", end_time: str = "",
             column_index: int = 4, display_mode: str = "srt", fps: int = 30,
             word_text: str = "", edit_mode: str = "srt"):
        self.display_mode = display_mode
        self.initial_text = str(initial_text)
        self.word_text = str(word_text)
        self.edit_mode = edit_mode
        self.start_time = format_time(parse_time(start_time)) if start_time else start_time
        self.end_time = format_time(parse_time(end_time)) if end_time else end_time
        self.column_index = column_index
        self.fps = fps
        self.result = None
        self.segmentation_service = SegmentationService()

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
        style.configure("TextEdit.TLabel", background="#334D6D", foreground="white",font=("Arial", 10))
        style.configure("TextEdit.TButton", padding=5)

    def create_widgets(self, master, show_word_edit=False):
        # 創建標題列
        self.title_bar = tk.Frame(self, bg='#334D6D', relief='raised', bd=0)
        self.title_bar.pack(fill=tk.X)

        # 標題標籤 - 注意這裡使用 tk.Label 而不是 ttk.Label
        self.title_label = tk.Label(
            self.title_bar,
            text=self.title(),
            bg="#334D6D",  # 設置背景色
            fg="white",    # 設置前景色
            font=("Arial", 10)
        )
        self.title_label.pack(side=tk.LEFT, pady=5, padx=5)

        # 關閉按鈕
        self.close_button = tk.Button(
            self.title_bar,
            text="×",
            command=self.cancel,
            bg="#334D6D",
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
        """創建對話框按鈕區域"""
        # 初始化按鈕管理器
        from gui.components.button_manager import ButtonManager
        self.button_manager = ButtonManager(self)

        # 按鈕框架
        button_frame = ttk.Frame(self.main_frame, style="TextEdit.TFrame")
        button_frame.pack(side=tk.BOTTOM, pady=5)

        # 使用按鈕管理器創建按鈕
        button_configs = [
            {
                'id': 'ok',
                'normal_icon': 'ok_icon.png',
                'hover_icon': 'ok_hover.png',
                'command': self.ok,
                'tooltip': '確認修改',
                'side': tk.LEFT,
                'padx': 5
            },
            {
                'id': 'cancel',
                'normal_icon': 'cancel_icon.png',
                'hover_icon': 'cancel_hover.png',
                'command': self.cancel,
                'tooltip': '取消修改',
                'side': tk.LEFT,
                'padx': 5
            }
        ]

        # 創建按鈕
        self.dialog_buttons = self.button_manager.create_button_set(button_frame, button_configs)

        # 綁定回車鍵和 ESC 鍵
        self.bind("<Escape>", self.cancel)

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

    def bind_events(self):
        """綁定事件"""
        # 儲存所有綁定的事件標識符
        self.event_bindings = []

        # 綁定各種事件並儲存標識符
        id1 = self.bind('<Return>', self.ok)
        id2 = self.bind('<Escape>', self.cancel)

        self.event_bindings.extend([id1, id2])

        # 其他事件綁定...

    def unbind_all_events(self):
        """清除所有事件綁定"""
        try:
            # 如果窗口已存在，才執行解綁
            if hasattr(self, 'winfo_exists') and self.winfo_exists():
                # 清除已知的事件綁定
                for binding_id in getattr(self, 'event_bindings', []):
                    self.unbind(binding_id)

                # 清除常見事件
                self.unbind('<Return>')
                self.unbind('<Escape>')

                # 如果有子控件也需要清理，可以在這裡處理
        except tk.TclError:
            # 窗口可能已關閉
            pass

    def ok(self, event=None):
        """確定按鈕事件"""
        try:
            if self.validate():
                self.apply()
                if self.parent:
                    self.grab_release()
                self.destroy()
        except tk.TclError:
            # 窗口可能已關閉
            pass

    def cancel(self, event=None):
        """取消按鈕事件"""
        try:
            self.result = None
            if self.parent:
                self.grab_release()
            self.destroy()
        except tk.TclError:
            # 窗口可能已關閉
            pass

    def generate_time_segments(self, lines):
        """
        根據文本行生成對應的時間戳
        :param lines: 文本行列表
        :return: 包含文本、開始時間、結束時間的列表
        """
        # 忽略空行
        valid_lines = [line for line in lines if line.strip()]
        if not valid_lines:
            return []

        # 解析時間
        start_time = parse_time(str(self.start_time))
        end_time = parse_time(str(self.end_time))
        total_duration = (end_time.ordinal - start_time.ordinal)

        # 計算總字符數（只考慮非空行）
        total_chars = sum(len(line.strip()) for line in valid_lines)

        # 至少要有一個字符
        if total_chars == 0:
            total_chars = 1

        # 記錄結果
        results = []
        current_time = start_time

        for i, line in enumerate(valid_lines):
            line_text = line.strip()
            if not line_text:
                continue

            # 計算該行的時間比例
            if i == len(valid_lines) - 1:
                # 最後一行直接用到結束時間
                next_time = end_time
            else:
                # 根據字符比例計算時間
                line_proportion = len(line_text) / total_chars
                time_duration = int(total_duration * line_proportion)
                next_time = pysrt.SubRipTime.from_ordinal(current_time.ordinal + time_duration)

            # 保存結果
            results.append((
                line_text,                  # 文本
                format_time(current_time),  # 開始時間
                format_time(next_time)      # 結束時間
            ))

            # 更新當前時間為下一行的開始時間
            current_time = next_time

        return results

    def apply(self):
        """處理確定按鈕事件，根據編輯模式生成結果"""
        try:
            # 檢查是否為 Word 編輯且需要分割
            if self.edit_mode == 'word' and hasattr(self, 'word_text_widget') and self.word_text_widget:
                word_text = self.word_text_widget.get("1.0", tk.END).strip()
                return self._process_word_edit(word_text)

            # 處理普通 SRT 編輯
            text = self.text_widget.get("1.0", tk.END).strip()
            return self._process_srt_edit(text)

        except Exception as e:
            error_msg = f"處理文本時出錯：{str(e)}"
            logging.error(error_msg, exc_info=True)
            show_error("錯誤", error_msg, self.parent)
            self.result = None

    def _process_word_edit(self, word_text):
        """處理 Word 文本編輯"""
        # 檢查是否需要分割 Word 文本
        if '\n' in word_text:
            lines = [line.strip() for line in word_text.split('\n') if line.strip()]
            if len(lines) > 1:
                # 使用核心服務生成分割結果
                is_valid, error_msg = self.segmentation_service.validate_time_range(
                    self.start_time, self.end_time
                )

                if not is_valid:
                    show_error("錯誤", error_msg, self.parent)
                    return

                self.result = self.segmentation_service.generate_time_segments(
                    lines, self.start_time, self.end_time
                )
                return
            else:
                self.result = word_text
                return
        else:
            self.result = word_text
            return

    def _process_srt_edit(self, text):
        """處理 SRT 文本編輯"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # 基本驗證
        if not lines:
            show_error("錯誤", "文本不能為空", self.parent)
            return

        # 如果只有一行文本，不需要拆分，直接返回文本字符串
        if len(lines) == 1 and '\n' not in text:
            self.result = text
            return

        # 時間範圍驗證
        is_valid, error_msg = self.segmentation_service.validate_time_range(
            self.start_time, self.end_time
        )

        if not is_valid:
            show_error("錯誤", error_msg, self.parent)
            return

        # 使用核心服務生成分割結果
        segments = self.segmentation_service.generate_time_segments(
            lines, self.start_time, self.end_time
        )

        self.result = segments

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
        try:
            self.wait_window()
            return self.result
        except tk.TclError:
            # 窗口已被破壞，可能是用戶關閉了窗口
            return None
