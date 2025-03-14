"""樹視圖管理模組"""

import tkinter as tk
from tkinter import ttk
import logging
from gui.components.columns import ColumnConfig

class TreeManager:
    """處理樹視圖的創建、配置和數據管理"""

    def __init__(self, parent):
        """
        初始化樹視圖管理器
        :param parent: 父物件 (AlignmentGUI 實例)
        """
        self.parent = parent
        self.logger = logging.getLogger(self.__class__.__name__)
        self.tree = None
        self.column_config = ColumnConfig()

    def create_treeview(self, frame, columns):
        """
        創建樹視圖
        :param frame: 放置樹視圖的框架
        :param columns: 列名列表
        :return: 創建的樹視圖物件
        """
        self.tree = ttk.Treeview(frame)
        self.setup_treeview_columns(columns)
        self.setup_treeview_scrollbars(frame)

        # 配置標籤樣式
        self.tree.tag_configure('mismatch', background='#FFDDDD')  # 淺紅色背景標記不匹配項目
        self.tree.tag_configure('use_word_text', background='#00BFFF')  # 淺藍色背景標記使用 Word 文本的項目

        return self.tree

    def setup_treeview_columns(self, columns):
        """
        設置樹視圖列配置
        :param columns: 列名列表
        """
        try:
            # 設置列
            self.tree["columns"] = columns
            self.tree['show'] = 'headings'

            # 配置每一列
            for col in columns:
                config = self.column_config.COLUMNS.get(col, {
                    'width': 100,
                    'stretch': True if col in ['SRT Text', 'Word Text'] else False,
                    'anchor': 'w' if col in ['SRT Text', 'Word Text'] else 'center'
                })

                self.tree.column(col,
                    width=config['width'],
                    stretch=config['stretch'],
                    anchor=config['anchor'])
                self.tree.heading(col, text=col, anchor='center')

            self.logger.debug(f"樹視圖列配置完成，列: {columns}")

        except Exception as e:
            self.logger.error(f"設置樹狀視圖列時出錯: {str(e)}")

    def setup_treeview_scrollbars(self, frame):
        """
        設置樹視圖卷軸
        :param frame: 放置樹視圖的框架
        """
        # 垂直卷軸
        scrollbar = ttk.Scrollbar(
            frame,
            orient='vertical',
            command=self.tree.yview
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 配置 Treeview 的卷軸命令
        self.tree['yscrollcommand'] = scrollbar.set

        # 將 Treeview 放入框架
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.logger.debug("Treeview 卷軸設置完成")

    def insert_item(self, parent, position, values):
        """
        安全地插入樹視圖項目
        :param parent: 父項目ID，通常為空字符串表示根級
        :param position: 插入位置，可以是索引或'end'
        :param values: 要插入的值元組
        :return: 插入項目的ID
        """
        try:
            item_id = self.tree.insert(parent, position, values=values)
            return item_id
        except Exception as e:
            self.logger.error(f"插入項目時出錯: {e}")
            raise

    def clear_tree(self):
        """清除樹視圖所有項目"""
        try:
            if self.tree:
                for item in self.tree.get_children():
                    self.tree.delete(item)
            self.logger.info("已清空樹視圖所有項目")
        except Exception as e:
            self.logger.error(f"清空樹視圖時出錯: {e}")

    def refresh_structure(self, columns):
        """
        刷新樹視圖結構 (用於改變顯示模式時)
        :param columns: 新的列名列表
        """
        try:
            # 保存當前數據
            items_data = []
            for item in self.tree.get_children():
                values = self.tree.item(item, 'values')
                tags = self.tree.item(item, 'tags')
                items_data.append((values, tags))

            # 清空樹狀視圖
            self.clear_tree()

            # 設置新列
            self.setup_treeview_columns(columns)

            # 返回保存的數據以供外部恢復
            return items_data

        except Exception as e:
            self.logger.error(f"刷新樹視圖結構時出錯: {e}")
            return []

    def get_selected_items(self):
        """
        獲取選中的項目
        :return: 選中項目的ID列表
        """
        try:
            return self.tree.selection()
        except Exception as e:
            self.logger.error(f"獲取選中項目時出錯: {e}")
            return []

    def get_item_values(self, item_id):
        """
        獲取項目的值
        :param item_id: 項目ID
        :return: 項目的值列表
        """
        try:
            if not self.tree.exists(item_id):
                return None
            return self.tree.item(item_id, 'values')
        except Exception as e:
            self.logger.error(f"獲取項目值時出錯: {e}")
            return None

    def set_item_values(self, item_id, values):
        """
        設置項目的值
        :param item_id: 項目ID
        :param values: 新的值列表
        :return: 是否成功
        """
        try:
            if not self.tree.exists(item_id):
                return False
            self.tree.item(item_id, values=values)
            return True
        except Exception as e:
            self.logger.error(f"設置項目值時出錯: {e}")
            return False

    def set_item_tags(self, item_id, tags):
        """
        設置項目的標籤
        :param item_id: 項目ID
        :param tags: 標籤元組或列表
        :return: 是否成功
        """
        try:
            if not self.tree.exists(item_id):
                return False
            self.tree.item(item_id, tags=tags)
            return True
        except Exception as e:
            self.logger.error(f"設置項目標籤時出錯: {e}")
            return False

    def get_item_tags(self, item_id):
        """
        獲取項目的標籤
        :param item_id: 項目ID
        :return: 標籤元組或None
        """
        try:
            if not self.tree.exists(item_id):
                return None
            return self.tree.item(item_id, 'tags')
        except Exception as e:
            self.logger.error(f"獲取項目標籤時出錯: {e}")
            return None

    def get_all_items(self):
        """
        獲取所有項目
        :return: 所有項目的ID列表
        """
        try:
            return self.tree.get_children()
        except Exception as e:
            self.logger.error(f"獲取所有項目時出錯: {e}")
            return []

    def get_item_index(self, item_id):
        """
        獲取項目的索引
        :param item_id: 項目ID
        :return: 項目在樹視圖中的索引或None
        """
        try:
            if not self.tree.exists(item_id):
                return None
            return self.tree.index(item_id)
        except Exception as e:
            self.logger.error(f"獲取項目索引時出錯: {e}")
            return None