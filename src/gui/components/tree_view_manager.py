"""TreeView 管理器模組，負責處理所有 TreeView 操作"""

import logging
from tkinter import ttk
from typing import Dict, List, Tuple


class TreeViewManager:
    """處理 TreeView 的所有操作，如項目插入、刪除、更新等"""

    def __init__(self, tree: ttk.Treeview):
        """
        初始化 TreeView 管理器
        :param tree: 要操作的 TreeView 控件
        """
        self.tree = tree
        self.logger = logging.getLogger(self.__class__.__name__)

    def insert_item(self, parent: str, position: str, values: tuple) -> str:
        """
        插入項目到 TreeView
        :param parent: 父項目的 ID
        :param position: 插入位置 ('', 'end' 等)
        :param values: 要插入的值的元組
        :return: 插入項目的 ID
        """
        try:
            item_id = self.tree.insert(parent, position, values=values)
            return item_id
        except Exception as e:
            self.logger.error(f"插入項目時出錯: {e}")
            raise

    def update_item(self, item, **kwargs):
        """
        更新項目
        :param item: 項目ID
        :param kwargs: 項目屬性
        :return: 是否成功
        """
        try:
            if not self.tree.exists(item):
                return False

            # 如果提供了 values 參數，確保它是一個元組
            if 'values' in kwargs and not isinstance(kwargs['values'], tuple):
                kwargs['values'] = tuple(kwargs['values'])

            self.tree.item(item, **kwargs)
            return True
        except Exception as e:
            self.logger.error(f"更新項目時出錯: {e}")
            return False

    def delete_items(self, items: List[str]) -> None:
        """
        刪除多個 TreeView 項目
        :param items: 項目 ID 列表
        """
        try:
            for item_id in items:
                if self.tree.exists(item_id):
                    self.tree.delete(item_id)
        except Exception as e:
            self.logger.error(f"刪除多個項目時出錯: {e}")

    def delete_item(self, item_id: str) -> bool:
        """
        刪除 TreeView 項目
        :param item_id: 項目 ID
        :return: 是否成功刪除
        """
        try:
            if self.tree.exists(item_id):
                self.tree.delete(item_id)
                return True
            else:
                self.logger.warning(f"嘗試刪除不存在的項目: {item_id}")
                return False
        except Exception as e:
            self.logger.error(f"刪除項目時出錯: {e}")
            return False

    def set_item_tags(self, item_id: str, tags: tuple) -> None:
        """設置項目的標籤"""
        if self.tree.exists(item_id):
            self.tree.item(item_id, tags=tags)

    def set_selection(self, items) -> None:
        """設置選中的項目"""
        self.tree.selection_set(items)

    def is_selected(self, item_id: str) -> bool:
        """檢查項目是否被選中"""
        return item_id in self.tree.selection()

    def make_visible(self, item_id: str) -> None:
        """確保項目可見"""
        if self.tree.exists(item_id):
            self.tree.see(item_id)

    def select_and_see(self, item_id: str) -> None:
        """選中項目並確保它可見"""
        if self.tree.exists(item_id):
            self.tree.selection_set(item_id)
            self.tree.see(item_id)

    def clear_all(self) -> None:
        """清空 TreeView 中的所有項目"""
        try:
            for item in self.tree.get_children():
                self.tree.delete(item)
        except Exception as e:
            self.logger.error(f"清空所有項目時出錯: {e}")

    def get_all_items(self) -> List[str]:
        """獲取所有項目 ID"""
        return self.tree.get_children()

    def get_item_values(self, item):
        """
        獲取樹項目的值
        :param item: 項目ID
        :return: 項目值列表 (不是元組)
        """
        try:
            if not self.tree.exists(item):
                return []
            return list(self.tree.item(item)['values'])  # 轉換為列表再返回
        except Exception as e:
            self.logger.error(f"獲取項目值時出錯: {e}")
            return []

    def get_item_tags(self, item_id: str) -> Tuple:
        """獲取指定項目的標籤"""
        if self.tree.exists(item_id):
            return self.tree.item(item_id, 'tags')
        return tuple()

    def get_item_position(self, item_id: str) -> int:
        """獲取項目在 TreeView 中的位置"""
        if self.tree.exists(item_id):
            return self.tree.index(item_id)
        return -1

    def select_item(self, item_id: str) -> None:
        """選擇指定項目"""
        if self.tree.exists(item_id):
            self.tree.selection_set(item_id)
            self.tree.see(item_id)

    def get_selected_items(self) -> List[str]:
        """獲取所有選中的項目 ID"""
        return self.tree.selection()

    def is_item_selected(self, item_id: str) -> bool:
        """檢查項目是否被選中"""
        selected = self.tree.selection()
        return item_id in selected

    def set_column_config(self, column: str, width: int = None, stretch: bool = None, anchor: str = None) -> None:
        """設置列配置"""
        kwargs = {}
        if width is not None:
            kwargs['width'] = width
        if stretch is not None:
            kwargs['stretch'] = stretch
        if anchor is not None:
            kwargs['anchor'] = anchor

        if kwargs:
            self.tree.column(column, **kwargs)

    def set_heading(self, column: str, text: str, anchor: str = 'center') -> None:
        """設置列標題"""
        self.tree.heading(column, text=text, anchor=anchor)

    def configure_columns(self, columns: List[str], width_map: Dict[str, int] = None,
                      stretch_map: Dict[str, bool] = None, anchor_map: Dict[str, str] = None) -> None:
        """
        一次性配置多個列
        :param columns: 列名列表
        :param width_map: 列寬映射
        :param stretch_map: 列可拉伸映射
        :param anchor_map: 列對齊方式映射
        """
        # 設置 TreeView 的列
        self.tree["columns"] = columns
        self.tree['show'] = 'headings'

        for col in columns:
            # 設置預設值
            width = 100
            stretch = False
            anchor = 'center'

            # 從映射中獲取自定義值
            if width_map and col in width_map:
                width = width_map[col]
            if stretch_map and col in stretch_map:
                stretch = stretch_map[col]
            if anchor_map and col in anchor_map:
                anchor = anchor_map[col]

            # 配置列
            self.set_column_config(col, width=width, stretch=stretch, anchor=anchor)
            self.set_heading(col, text=col)