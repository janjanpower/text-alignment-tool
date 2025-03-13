from setuptools import setup, find_packages
import sys

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

# 設定打包參數
setup_kwargs = {
    "name": "text_alignment_tool",
    "version": "1.0.0",
    "author": "Your Name",
    "author_email": "your.email@example.com",
    "description": "文本對齊工具 - 用於編輯和管理字幕檔案",
    "long_description": long_description,
    "long_description_content_type": "text/markdown",
    "url": "https://github.com/yourusername/text_alignment_tool",
    "packages": find_packages(include=["src*"]),  # 更改為您的實際包結構
    "classifiers": [
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Text Processing :: Linguistic",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    "python_requires": ">=3.8",
    "install_requires": requirements,
    "include_package_data": True,
    "package_data": {
        "src": ["assets/*", "icons/*"],  # 根據您的資產位置調整
    },
}

# 在 Windows 上，添加 GUI 應用程式的設定
if sys.platform.startswith('win'):
    from setuptools import setup

    # 添加 windows 選項來創建無控制台視窗的 exe
    setup_kwargs.update({
        "windows": [{
            "script": "src/__main__.py",  # 您的主程式入口點
            "icon_resources": [(1, "icons/app_icon.ico")],  # 應用程式圖標路徑
            "dest_base": "TextAlignmentTool"  # 輸出 exe 名稱
        }],
        "options": {
            "py2exe": {
                "bundle_files": 1,
                "compressed": True,
                "includes": ["tkinter"],  # 確保包含所有必要的依賴
                "packages": ["src"],
                "excludes": ["pyinstaller", "pytest"],
            }
        },
        "zipfile": None,
    })

setup(**setup_kwargs)