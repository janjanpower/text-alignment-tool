import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

class CorrectionColumn:
    """校正圖標列類"""
    def __init__(self, tree: ttk.Treeview):
        self.tree = tree
        self.icons = {}
        self.icon_references = {}  # 保持圖標引用
        self.load_icons()

    def load_icons(self) -> None:
        """載入圖標"""
        try:
            # 獲取圖標目錄路徑
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            icons_dir = os.path.join(project_root, "icons")

            print(f"載入圖標，路徑: {icons_dir}")

            # 載入所需圖標
            icon_files = {
                "correct": "replacement_correct.png",
                "error": "replacement_error.png"
            }

            for name, filename in icon_files.items():
                path = os.path.join(icons_dir, filename)
                if os.path.exists(path):
                    image = Image.open(path)
                    # 設置合適的圖標大小
                    image = image.resize((20, 20), Image.Resampling.LANCZOS)
                    self.icons[name] = ImageTk.PhotoImage(image)
                    print(f"成功載入圖標: {filename}")
                else:
                    print(f"找不到圖標文件: {path}")

        except Exception as e:
            print(f"載入圖標時出錯: {str(e)}")
            self.icons = {}

    def create_icon_button(self, item_id: str, column: str,
                          is_corrected: bool = True) -> None:
        """在指定單元格創建圖標按鈕"""
        icon = self.icons.get("correct" if is_corrected else "error")
        if icon:
            # 使用 Label 顯示圖標
            label = tk.Label(self.tree, image=icon, bg='white', cursor='hand2')

            # 保存引用以防止垃圾回收
            self.icon_references[item_id] = {
                'label': label,
                'icon': icon,
                'is_corrected': is_corrected
            }

            # 將標籤放入樹狀圖中
            self.tree.update()
            bbox = self.tree.bbox(item_id, column)
            if bbox:
                x, y, width, height = bbox
                # 調整位置使圖標居中
                label.place(x=x + (width-20)//2, y=y + (height-20)//2)

                # 綁定點擊事件
                label.bind('<Button-1>', lambda e,
                         id=item_id: self.toggle_icon(id))

    def toggle_icon(self, item_id: str) -> None:
        """切換圖標狀態"""
        if item_id in self.icon_references:
            ref = self.icon_references[item_id]
            is_corrected = not ref['is_corrected']

            # 更新圖標
            new_icon = self.icons.get("correct" if is_corrected else "error")
            if new_icon:
                ref['label'].configure(image=new_icon)
                ref['icon'] = new_icon
                ref['is_corrected'] = is_corrected

    def clear_icons(self) -> None:
        """清除所有圖標"""
        for ref in self.icon_references.values():
            if 'label' in ref:
                ref['label'].destroy()
        self.icon_references.clear()