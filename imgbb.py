from PyQt6.QtWidgets import (
    QApplication, QLabel, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout, QWidget, QTextEdit, QLineEdit, QFormLayout, 
    QProgressBar, QTabWidget, QListWidget, QListWidgetItem, QMenu, QMessageBox, QSlider, QCheckBox, QComboBox, 
    QSplitter, QMainWindow, QStatusBar, QToolBar, QDialog, QDialogButtonBox, QSpinBox, QScrollArea
)
from PyQt6.QtGui import QPixmap, QDesktopServices, QDragEnterEvent, QDropEvent, QKeySequence, QImage, QAction, QIcon
from PyQt6.QtCore import Qt, QUrl, QSettings, QSize, QTemporaryFile, QDir, pyqtSignal, QThread, QByteArray, QBuffer, QIODevice
import sys
import requests
import logging
import webbrowser
import json
import os
import time
import base64
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Union
import asyncio
import aiohttp
from cryptography.fernet import Fernet

APP_NAME = "ImgBBUploader"
APP_AUTHOR = "Nrentzilas"
VERSION = "1.1.0"
MAX_IMAGE_SIZE = 32 * 1024 * 1024
DEFAULT_THEME = "dark"
HISTORY_FILE = "upload_history.json"

class APIKeyError(Exception):
    pass

class ImageSizeError(Exception):
    pass

class NetworkError(Exception):
    pass

class UploadWorker(QThread):
    upload_progress = pyqtSignal(int)
    upload_complete = pyqtSignal(dict)
    upload_error = pyqtSignal(str)
    
    def __init__(self, api_key: str, file_path: str, options: dict = None):
        super().__init__()
        self.api_key = api_key
        self.file_path = file_path
        self.options = options or {}
        
    def run(self):
        try:
            self.upload_progress.emit(10)
            
            if not self.api_key:
                raise APIKeyError("API key is required")
            
            if Path(self.file_path).stat().st_size > MAX_IMAGE_SIZE:
                raise ImageSizeError(f"Image size exceeds {MAX_IMAGE_SIZE // (1024 * 1024)}MB limit")
            
            url = "https://api.imgbb.com/1/upload"
            
            with open(self.file_path, 'rb') as img_file:
                image_data = img_file.read()
                
            self.upload_progress.emit(30)
            
            if self.options.get('resize', False):
                max_dimension = self.options.get('max_dimension', 1024)
                image_data = self._resize_image(image_data, max_dimension)
                
            self.upload_progress.emit(50)
            
            files = {'image': image_data}
            params = {'key': self.api_key}
            
            if 'expiration' in self.options:
                params['expiration'] = self.options['expiration']
                
            if 'name' in self.options:
                params['name'] = self.options['name']
                
            self.upload_progress.emit(70)
            
            response = requests.post(
                url,
                params=params,
                files=files,
                timeout=30
            )
            
            self.upload_progress.emit(90)
            
            response.raise_for_status()
            data = response.json()
            
            if 'data' not in data or 'url' not in data['data']:
                raise ValueError("Invalid response format from ImgBB")
                
            self.upload_progress.emit(100)
            self.upload_complete.emit(data['data'])
            
        except APIKeyError as e:
            self.upload_error.emit(f"API Key Error: {str(e)}")
        except ImageSizeError as e:
            self.upload_error.emit(f"Image Size Error: {str(e)}")
        except requests.exceptions.RequestException as e:
            self.upload_error.emit(f"Network Error: {str(e)}")
        except ValueError as e:
            self.upload_error.emit(f"API Error: {str(e)}")
        except Exception as e:
            self.upload_error.emit(f"Unexpected Error: {str(e)}")
    
    def _resize_image(self, image_data: bytes, max_dimension: int) -> bytes:
        img = QImage()
        img.loadFromData(image_data)
        
        if img.width() <= max_dimension and img.height() <= max_dimension:
            return image_data
            
        if img.width() > img.height():
            new_width = max_dimension
            new_height = int(img.height() * (max_dimension / img.width()))
        else:
            new_height = max_dimension
            new_width = int(img.width() * (max_dimension / img.height()))
            
        resized = img.scaled(new_width, new_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        resized.save(buffer, "PNG")
        
        return buffer.data().data()

class OptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Upload Options")
        self.resize(400, 300)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("Leave empty for original filename")
        form_layout.addRow("Custom filename:", self.filename_input)
        
        self.expiration_combo = QComboBox()
        self.expiration_combo.addItems(["No expiration", "1 day", "1 week", "1 month", "6 months"])
        form_layout.addRow("Expiration:", self.expiration_combo)
        
        self.resize_check = QCheckBox("Resize large images")
        self.resize_check.setChecked(True)
        
        self.resize_slider = QSlider(Qt.Orientation.Horizontal)
        self.resize_slider.setRange(500, 4000)
        self.resize_slider.setValue(1500)
        self.resize_slider.setTickInterval(500)
        self.resize_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        
        self.resize_label = QLabel(f"Max dimension: {self.resize_slider.value()}px")
        self.resize_slider.valueChanged.connect(lambda v: self.resize_label.setText(f"Max dimension: {v}px"))
        
        resize_layout = QVBoxLayout()
        resize_layout.addWidget(self.resize_check)
        resize_layout.addWidget(self.resize_slider)
        resize_layout.addWidget(self.resize_label)
        
        form_layout.addRow("Resize:", resize_layout)
        
        layout.addLayout(form_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
    def get_options(self):
        options = {}
        
        filename = self.filename_input.text()
        if filename:
            options['name'] = filename
            
        expiration_text = self.expiration_combo.currentText()
        if expiration_text != "No expiration":
            mapping = {
                "1 day": 86400,
                "1 week": 604800,
                "1 month": 2592000,
                "6 months": 15552000
            }
            options['expiration'] = mapping.get(expiration_text)
            
        if self.resize_check.isChecked():
            options['resize'] = True
            options['max_dimension'] = self.resize_slider.value()
            
        return options

class HistoryManager:
    def __init__(self, encryption_key=None):
        self.history_file = Path(QDir.homePath()) / f".{APP_NAME}" / HISTORY_FILE
        self.history_file.parent.mkdir(exist_ok=True)
        self.encryption_key = encryption_key
        self.history = self._load_history()
        
    def _load_history(self):
        if not self.history_file.exists():
            return []
            
        try:
            with open(self.history_file, 'r') as f:
                data = f.read()
                
                if self.encryption_key:
                    fernet = Fernet(self.encryption_key)
                    data = fernet.decrypt(data.encode()).decode()
                    
                return json.loads(data)
        except Exception as e:
            logging.error(f"Error loading history: {str(e)}")
            return []
            
    def save_history(self):
        try:
            data = json.dumps(self.history)
            
            if self.encryption_key:
                fernet = Fernet(self.encryption_key)
                data = fernet.encrypt(data.encode()).decode()
                
            with open(self.history_file, 'w') as f:
                f.write(data)
                
        except Exception as e:
            logging.error(f"Error saving history: {str(e)}")
            
    def add_entry(self, data):
        entry = {
            'timestamp': datetime.now().isoformat(),
            'url': data.get('url'),
            'delete_url': data.get('delete_url'),
            'thumb_url': data.get('thumb', {}).get('url'),
            'filename': data.get('title'),
            'size': data.get('size'),
            'width': data.get('width'),
            'height': data.get('height')
        }
        
        self.history.insert(0, entry)
        
        if len(self.history) > 100:
            self.history = self.history[:100]
            
        self.save_history()
        
    def get_history(self):
        return self.history
        
    def clear_history(self):
        self.history = []
        self.save_history()
        
    def delete_entry(self, index):
        if 0 <= index < len(self.history):
            del self.history[index]
            self.save_history()
            
class ThemeManager:
    def __init__(self):
        self.themes = {
            "dark": {
                "bg_color": "#070e12",
                "widget_bg": "#0c1a20",
                "text_color": "#ffffff",
                "accent_color": "#4f46e4",
                "accent_hover": "#3d3bbd",
                "border_color": "#4f46e4"
            },
            "light": {
                "bg_color": "#f0f2f5",
                "widget_bg": "#ffffff",
                "text_color": "#333333",
                "accent_color": "#4f46e4",
                "accent_hover": "#3d3bbd",
                "border_color": "#d1d5db"
            },
            "high_contrast": {
                "bg_color": "#000000",
                "widget_bg": "#000000",
                "text_color": "#ffffff",
                "accent_color": "#ffff00",
                "accent_hover": "#cccc00",
                "border_color": "#ffffff"
            }
        }
        
    def get_stylesheet(self, theme_name):
        if theme_name not in self.themes:
            theme_name = "dark"
            
        theme = self.themes[theme_name]
        
        return f"""
            QWidget {{
                background-color: {theme["bg_color"]};
                color: {theme["text_color"]};
                font-family: Arial;
                font-size: 14px;
            }}
            QLabel {{
                color: {theme["text_color"]};
            }}
            QLineEdit, QTextEdit, QListWidget, QComboBox, QSpinBox {{
                background-color: {theme["widget_bg"]};
                color: {theme["text_color"]};
                border: 1px solid {theme["border_color"]};
                padding: 5px;
                border-radius: 5px;
            }}
            QPushButton {{
                background-color: {theme["accent_color"]};
                color: #ffffff;
                padding: 8px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
            }}
            QPushButton:hover {{
                background-color: {theme["accent_hover"]};
            }}
            QPushButton:disabled {{
                background-color: #666666;
                color: #999999;
            }}
            QTextEdit {{
                padding: 10px;
            }}
            QTabWidget::pane {{
                border: 1px solid {theme["border_color"]};
                border-radius: 5px;
            }}
            QTabBar::tab {{
                background-color: {theme["bg_color"]};
                color: {theme["text_color"]};
                border: 1px solid {theme["border_color"]};
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                padding: 8px 12px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {theme["accent_color"]};
                color: #ffffff;
            }}
            QProgressBar {{
                border: 1px solid {theme["border_color"]};
                border-radius: 5px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {theme["accent_color"]};
            }}
            QLabel.link {{
                color: {theme["accent_color"]};
                text-decoration: underline;
            }}
            QLabel.link:hover {{
                color: {theme["accent_hover"]};
            }}
            QCheckBox {{
                spacing: 5px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
            }}
            QSlider::groove:horizontal {{
                border: 1px solid {theme["border_color"]};
                height: 8px;
                background: {theme["widget_bg"]};
                margin: 2px 0;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {theme["accent_color"]};
                border: 1px solid {theme["border_color"]};
                width: 18px;
                height: 18px;
                margin: -8px 0;
                border-radius: 9px;
            }}
            QStatusBar {{
                color: {theme["text_color"]};
                background-color: {theme["bg_color"]};
                border-top: 1px solid {theme["border_color"]};
            }}
            QToolBar {{
                background-color: {theme["bg_color"]};
                border: none;
                spacing: 5px;
            }}
        """

class ImgBBUploader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(APP_AUTHOR, APP_NAME)
        self.theme_manager = ThemeManager()
        self.setup_logging()
        
        self.image_path = None
        self.current_theme = self.settings.value('theme', DEFAULT_THEME)
        self.encryption_key = self._get_or_create_encryption_key()
        self.history_manager = HistoryManager(self.encryption_key)
        
        self.init_ui()
        self.load_saved_api_key()
        self.setAcceptDrops(True)
        
    def setup_logging(self):
        log_path = Path(QDir.homePath()) / f".{APP_NAME}"
        log_path.mkdir(exist_ok=True)
        
        logging.basicConfig(
            filename=str(log_path / 'imgbb_uploader.log'),
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
    def _get_or_create_encryption_key(self):
        key = self.settings.value('encryption_key')
        
        if not key:
            key = Fernet.generate_key().decode()
            self.settings.setValue('encryption_key', key)
            
        return key.encode() if isinstance(key, str) else key
        
    def init_ui(self):
        self.setWindowTitle(f"{APP_AUTHOR}'s ImgBB Uploader v{VERSION}")
        self.resize(700, 800)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        self.toolbar = self.addToolBar("Main Toolbar")
        self.toolbar.setMovable(False)
        
        self.theme_action = QAction("Switch Theme", self)
        self.theme_action.triggered.connect(self.toggle_theme)
        self.toolbar.addAction(self.theme_action)
        
        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.show_about)
        self.toolbar.addAction(self.about_action)
        
        self.tab_widget = QTabWidget()
        
        self.upload_tab = QWidget()
        self.upload_layout = QVBoxLayout(self.upload_tab)
        self.upload_layout.setSpacing(15)
        
        api_layout = QFormLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter your ImgBB API Key")
        api_layout.addRow("API Key:", self.api_key_input)
        
        upload_btn_layout = QHBoxLayout()
        
        self.upload_btn = QPushButton("Upload Image")
        self.upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.upload_btn.clicked.connect(self.upload_image)
        
        self.options_btn = QPushButton("Options")
        self.options_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.options_btn.clicked.connect(self.show_options)
        
        upload_btn_layout.addWidget(self.upload_btn)
        upload_btn_layout.addWidget(self.options_btn)
        
        image_layout = QVBoxLayout()
        image_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.image_label = QLabel("No Image Selected")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(500, 350)
        self.image_label.setStyleSheet("border: 1px solid #4f46e4; background-color: #0c1a20;")
        
        self.image_info = QLabel("")
        self.image_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        image_layout.addWidget(self.image_label)
        image_layout.addWidget(self.image_info)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        self.link_display = QTextEdit()
        self.link_display.setPlaceholderText("The uploaded image link will appear here.")
        self.link_display.setReadOnly(True)
        
        btn_layout = QHBoxLayout()
        
        self.copy_btn = QPushButton("Copy Link")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.clicked.connect(self.copy_link)
        self.copy_btn.setDisabled(True)
        
        self.open_btn = QPushButton("Open in Browser")
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn.clicked.connect(self.open_in_browser)
        self.open_btn.setDisabled(True)
        
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addWidget(self.open_btn)
        
        bottom_layout = QHBoxLayout()
        
        self.api_key_link = QLabel('<a href="https://api.imgbb.com/" style="color: #4f46e4;">Get your ImgBB API Key</a>')
        self.api_key_link.setOpenExternalLinks(True)
        self.api_key_link.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.api_key_link.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.github_icon = QLabel()
        self.github_icon.setText("GitHub")
        self.github_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self.github_icon.mousePressEvent = lambda event: QDesktopServices.openUrl(QUrl("https://github.com/Nrentzilas/ImgBB-Uploader"))
        
        bottom_layout.addWidget(self.api_key_link)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.github_icon)
        
        self.upload_layout.addLayout(api_layout)
        self.upload_layout.addLayout(upload_btn_layout)
        self.upload_layout.addLayout(image_layout)
        self.upload_layout.addWidget(self.progress_bar)
        self.upload_layout.addWidget(self.link_display)
        self.upload_layout.addLayout(btn_layout)
        self.upload_layout.addLayout(bottom_layout)
        
        self.history_tab = QWidget()
        self.history_layout = QVBoxLayout(self.history_tab)
        
        self.history_list = QListWidget()
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.show_history_context_menu)
        self.history_list.itemDoubleClicked.connect(self.copy_history_link)
        
        history_btn_layout = QHBoxLayout()
        
        self.refresh_history_btn = QPushButton("Refresh")
        self.refresh_history_btn.clicked.connect(self.refresh_history)
        
        self.clear_history_btn = QPushButton("Clear All")
        self.clear_history_btn.clicked.connect(self.clear_history)
        
        history_btn_layout.addWidget(self.refresh_history_btn)
        history_btn_layout.addWidget(self.clear_history_btn)
        
        self.history_layout.addWidget(self.history_list)
        self.history_layout.addLayout(history_btn_layout)
        
        self.tab_widget.addTab(self.upload_tab, "Upload")
        self.tab_widget.addTab(self.history_tab, "History")
        
        self.main_layout.addWidget(self.tab_widget)
        
        self.upload_btn.setToolTip("Click to select and upload an image")
        self.options_btn.setToolTip("Configure upload options")
        self.copy_btn.setToolTip("Copy the image URL to clipboard")
        self.open_btn.setToolTip("Open the image in your web browser")
        self.api_key_input.setToolTip("Enter your ImgBB API key here")
        
        self.apply_theme(self.current_theme)
        
        self.refresh_history()
        
    def apply_theme(self, theme_name):
        self.current_theme = theme_name
        stylesheet = self.theme_manager.get_stylesheet(theme_name)
        self.setStyleSheet(stylesheet)
        self.settings.setValue('theme', theme_name)
        
    def toggle_theme(self):
        themes = list(self.theme_manager.themes.keys())
        current_index = themes.index(self.current_theme) if self.current_theme in themes else 0
        next_index = (current_index + 1) % len(themes)
        self.apply_theme(themes[next_index])
        
    def load_saved_api_key(self):
        saved_key = self.settings.value('api_key', '')
        self.api_key_input.setText(saved_key)
        
    def save_api_key(self):
        self.settings.setValue('api_key', self.api_key_input.text().strip())
        
    def refresh_history(self):
        self.history_list.clear()
        
        for entry in self.history_manager.get_history():
            timestamp = datetime.fromisoformat(entry['timestamp'])
            formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            filename = entry.get('filename', 'Unnamed Image')
            
            item = QListWidgetItem(f"{formatted_time} - {filename}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.history_list.addItem(item)
            
    def show_history_context_menu(self, position):
        item = self.history_list.itemAt(position)
        
        if item:
            menu = QMenu()
            
            copy_action = menu.addAction("Copy URL")
            open_action = menu.addAction("Open in Browser")
            delete_action = menu.addAction("Delete")
            
            action = menu.exec(self.history_list.mapToGlobal(position))
            
            if action == copy_action:
                self.copy_history_link(item)
            elif action == open_action:
                self.open_history_link(item)
            elif action == delete_action:
                self.delete_history_item(item)
                
    def copy_history_link(self, item):
        entry = item.data(Qt.ItemDataRole.UserRole)
        url = entry.get('url', '')
        
        if url:
            clipboard = QApplication.clipboard()
            clipboard.setText(url)
            self.status_bar.showMessage("Link copied to clipboard", 3000)
            
    def open_history_link(self, item):
        entry = item.data(Qt.ItemDataRole.UserRole)
        url = entry.get('url', '')
        
        if url:
            QDesktopServices.openUrl(QUrl(url))
            
    def delete_history_item(self, item):
        row = self.history_list.row(item)
        self.history_list.takeItem(row)
        self.history_manager.delete_entry(row)
        
    def clear_history(self):
        confirm = QMessageBox.question(
            self,
            "Clear History",
            "Are you sure you want to clear all upload history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            self.history_list.clear()
            self.history_manager.clear_history()
            
    def show_options(self):
        dialog = OptionsDialog(self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.upload_options = dialog.get_options()
            self.status_bar.showMessage("Options updated", 3000)
        else:
            pass

    def show_about(self):

        class AboutDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)

                self.setWindowTitle(f"About {APP_NAME}")
                self.setFixedSize(420, 280)
                self.setWindowIcon(QIcon("icon.png"))

                layout = QVBoxLayout()
                layout.setContentsMargins(20, 20, 20, 15)
                layout.setSpacing(10)

                title_label = QLabel(f"{APP_NAME} <span style='color: #888;'>v{VERSION}</span>")
                title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                title_label.setStyleSheet("""
                    font-size: 25px;
                    font-weight: bold;
                    color: #2c3e50;
                """)
                layout.addWidget(title_label)

                logo_label = QLabel()
                pixmap = QPixmap("logo.png")
                if not pixmap.isNull():
                    logo_label.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    layout.addWidget(logo_label)

                description_label = QLabel(
                    "A simple tool to upload images to ImgBB and manage links."
                )
                description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                description_label.setStyleSheet("""
                    font-size: 14px;
                    color: #555;
                    margin-top: 5px;
                    margin-bottom: 5px;
                """)
                layout.addWidget(description_label)

                author_label = QLabel(f"Developed by: <b>{APP_AUTHOR}</b>")
                author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                author_label.setStyleSheet("""
                    font-size: 16px;
                    color: #444;
                    margin-bottom: 10px;
                """)
                layout.addWidget(author_label)

                layout.addStretch()

                button_layout = QHBoxLayout()

                github_button = QPushButton("Visit GitHub")
                github_button.setIcon(QIcon.fromTheme("internet-services"))
                github_button.clicked.connect(lambda: webbrowser.open("https://github.com/Nrentzilas/ImgBB-Uploader"))

                close_button = QPushButton("Close")
                close_button.clicked.connect(self.close)

                button_layout.addWidget(github_button)
                button_layout.addWidget(close_button)

                layout.addLayout(button_layout)

                self.setLayout(layout)

        dialog = AboutDialog(self)
        dialog.exec()

        
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if Path(file_path).suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                    event.accept()
                    return
        event.ignore()
        
    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for file_path in files:
            if Path(file_path).suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                self.handle_image(file_path)
                break
                
    def paste_from_clipboard(self):
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        
        if mime_data.hasImage():
            image = clipboard.image()
            if not image.isNull():
                temp_file = QTemporaryFile(QDir.tempPath() + "/imgbb_clipboard_XXXXXX.png")
                
                if temp_file.open():
                    temp_path = temp_file.fileName()
                    image.save(temp_path, "PNG")
                    temp_file.close()
                    
                    self.handle_image(temp_path)
                    
                    logging.info(f"Image pasted from clipboard and saved to {temp_path}")
                    self.status_bar.showMessage("Image pasted from clipboard", 3000)
                else:
                    self.status_bar.showMessage("Failed to create temporary file", 3000)
            else:
                self.status_bar.showMessage("No valid image in clipboard", 3000)
        else:
            self.status_bar.showMessage("No image found in clipboard", 3000)
            
    def handle_image(self, file_path):
        try:
            self.image_path = file_path
            
            file_size = Path(file_path).stat().st_size
            if file_size > MAX_IMAGE_SIZE:
                raise ImageSizeError(f"Image size exceeds {MAX_IMAGE_SIZE // (1024 * 1024)}MB limit")
                
            pixmap = QPixmap(file_path)
            scaled_pixmap = pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            
            file_info = Path(file_path)
            size_kb = file_size / 1024
            size_mb = size_kb / 1024
            
            if size_mb >= 1:
                size_str = f"{size_mb:.2f} MB"
            else:
                size_str = f"{size_kb:.2f} KB"
                
            self.image_info.setText(f"{file_info.name} - {pixmap.width()}x{pixmap.height()} - {size_str}")
            
            if self.tab_widget.currentIndex() == 1:
                self.tab_widget.setCurrentIndex(0)
                
            self.link_display.clear()
            self.copy_btn.setDisabled(True)
            self.open_btn.setDisabled(True)
            
            self.status_bar.showMessage(f"Image loaded: {file_info.name}", 3000)
            
        except ImageSizeError as e:
            self.link_display.setText(f"Error: {str(e)}")
            self.status_bar.showMessage(f"Error: {str(e)}", 5000)
            logging.error(f"Image size error: {str(e)}")
        except Exception as e:
            self.link_display.setText(f"Error: Could not load image - {str(e)}")
            self.status_bar.showMessage(f"Error loading image", 3000)
            logging.error(f"Error loading image: {str(e)}")
            
    def upload_image(self):
        if not self.image_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Image",
                "",
                "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
            )
            
            if file_path:
                self.handle_image(file_path)
            else:
                return
                
        api_key = self.api_key_input.text().strip()
        if not api_key:
            self.link_display.setText("Error: API key is required.")
            self.status_bar.showMessage("Error: API key is required", 3000)
            return
            
        self.save_api_key()
        
        options = getattr(self, 'upload_options', {})
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.upload_btn.setDisabled(True)
        self.options_btn.setDisabled(True)
        
        self.upload_worker = UploadWorker(api_key, self.image_path, options)
        self.upload_worker.upload_progress.connect(self.update_progress)
        self.upload_worker.upload_complete.connect(self.handle_upload_success)
        self.upload_worker.upload_error.connect(self.handle_upload_error)
        self.upload_worker.start()
        
    def update_progress(self, value):
        self.progress_bar.setValue(value)
        
    def handle_upload_success(self, data):
        self.link_display.setText(data['url'])
        self.copy_btn.setEnabled(True)
        self.open_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.upload_btn.setEnabled(True)
        self.options_btn.setEnabled(True)
        
        self.history_manager.add_entry(data)
        self.refresh_history()
        
        self.status_bar.showMessage("Upload successful!", 3000)
        logging.info(f"Successfully uploaded image: {self.image_path}")
        
    def handle_upload_error(self, error_message):
        self.link_display.setText(f"Error: {error_message}")
        self.progress_bar.setVisible(False)
        self.upload_btn.setEnabled(True)
        self.options_btn.setEnabled(True)
        
        self.status_bar.showMessage(f"Upload failed: {error_message}", 5000)
        logging.error(f"Upload failed: {error_message}")
        
    def copy_link(self):
        clipboard = QApplication.clipboard()
        link = self.link_display.toPlainText()
        
        if link and not link.startswith("Error:"):
            clipboard.setText(link)
            self.status_bar.showMessage("Link copied to clipboard", 3000)
            
    def open_in_browser(self):
        link = self.link_display.toPlainText()
        
        if link and not link.startswith("Error:"):
            QDesktopServices.openUrl(QUrl(link))
            self.status_bar.showMessage("Opening in browser", 3000)

class BatchUploadDialog(QDialog):
    def __init__(self, parent=None, api_key=""):
        super().__init__(parent)
        self.api_key = api_key
        self.files = []
        self.results = []
        self.upload_options = {}
        
        self.setWindowTitle("Batch Upload")
        self.resize(600, 400)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        self.file_list = QListWidget()
        layout.addWidget(QLabel("Selected Files:"))
        layout.addWidget(self.file_list)
        
        btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("Add Files")
        self.add_btn.clicked.connect(self.add_files)
        
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_files)
        
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self.clear_files)
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.clear_btn)
        
        layout.addLayout(btn_layout)
        
        options_layout = QHBoxLayout()
        
        self.options_btn = QPushButton("Upload Options")
        self.options_btn.clicked.connect(self.show_options)
        
        self.resize_check = QCheckBox("Resize Images")
        self.resize_check.setChecked(True)
        
        options_layout.addWidget(self.options_btn)
        options_layout.addWidget(self.resize_check)
        options_layout.addStretch()
        
        layout.addLayout(options_layout)
        
        layout.addWidget(QLabel("Progress:"))
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        layout.addWidget(QLabel("Results:"))
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        layout.addWidget(self.results_text)
        
        bottom_btn_layout = QHBoxLayout()
        
        self.upload_btn = QPushButton("Start Upload")
        self.upload_btn.clicked.connect(self.start_uploads)
        
        self.save_results_btn = QPushButton("Save Results")
        self.save_results_btn.clicked.connect(self.save_results)
        self.save_results_btn.setEnabled(False)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        
        bottom_btn_layout.addWidget(self.upload_btn)
        bottom_btn_layout.addWidget(self.save_results_btn)
        bottom_btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(bottom_btn_layout)
        
        self.setLayout(layout)
        
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Images",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
        )
        
        if files:
            for file_path in files:
                if file_path not in self.files:
                    self.files.append(file_path)
                    self.file_list.addItem(Path(file_path).name)
            
            self.update_upload_button()
            
    def remove_files(self):
        selected_items = self.file_list.selectedItems()
        
        for item in selected_items:
            row = self.file_list.row(item)
            self.file_list.takeItem(row)
            del self.files[row]
            
        self.update_upload_button()
        
    def clear_files(self):
        self.file_list.clear()
        self.files = []
        self.update_upload_button()
        
    def update_upload_button(self):
        self.upload_btn.setEnabled(len(self.files) > 0)
        
    def show_options(self):
        dialog = OptionsDialog(self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.upload_options = dialog.get_options()
            
    def start_uploads(self):
        if not self.api_key:
            QMessageBox.warning(self, "API Key Required", "Please enter an API key in the main window.")
            return
            
        self.add_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.options_btn.setEnabled(False)
        self.upload_btn.setEnabled(False)
        
        self.results_text.clear()
        self.results = []
        
        asyncio.create_task(self.perform_uploads())
        
    async def perform_uploads(self):
        total_files = len(self.files)
        successful = 0
        failed = 0
        
        self.progress_bar.setRange(0, total_files)
        self.progress_bar.setValue(0)
        
        async with aiohttp.ClientSession() as session:
            for i, file_path in enumerate(self.files):
                try:
                    self.progress_bar.setValue(i)
                    self.results_text.append(f"Uploading {Path(file_path).name}...")
                    
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                        
                    if self.resize_check.isChecked() and 'resize' in self.upload_options:
                        pass
                        
                    url = "https://api.imgbb.com/1/upload"
                    payload = aiohttp.FormData()
                    payload.add_field('image', file_data)
                    
                    async with session.post(url, data=payload, params={'key': self.api_key}) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if 'data' in data and 'url' in data['data']:
                                url = data['data']['url']
                                self.results.append({
                                    'filename': Path(file_path).name,
                                    'url': url,
                                    'success': True
                                })
                                self.results_text.append(f"✓ Success: {url}\n")
                                successful += 1
                            else:
                                raise ValueError("Invalid API response")
                        else:
                            error_text = await response.text()
                            raise Exception(f"HTTP Error {response.status}: {error_text}")
                                
                except Exception as e:
                    self.results.append({
                        'filename': Path(file_path).name,
                        'error': str(e),
                        'success': False
                    })
                    self.results_text.append(f"✗ Failed: {str(e)}\n")
                    failed += 1
                    
        self.progress_bar.setValue(total_files)
        
        self.results_text.append(f"\nUpload Summary:\n"
                                 f"Total: {total_files}\n"
                                 f"Successful: {successful}\n"
                                 f"Failed: {failed}")
                                 
        self.add_btn.setEnabled(True)
        self.remove_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.options_btn.setEnabled(True)
        self.upload_btn.setEnabled(True)
        self.save_results_btn.setEnabled(True)
        
    def save_results(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Results",
            "",
            "Text Files (*.txt)"
        )
        
        if file_path:
            with open(file_path, 'w') as f:
                for result in self.results:
                    if result.get('success', False):
                        f.write(f"✓ {result['filename']} - {result['url']}\n")
                    else:
                        f.write(f"✗ {result['filename']} - {result['error']}\n")
                        
            QMessageBox.information(self, "Results Saved", "Results have been saved to the specified file.")

def main():
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    window = ImgBBUploader()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ImgBBUploader()
    window.show()
    sys.exit(app.exec())
