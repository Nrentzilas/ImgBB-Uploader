from PyQt6.QtWidgets import (
    QApplication, QLabel, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout, QWidget, QTextEdit, QLineEdit, QFormLayout, QProgressBar
)
from PyQt6.QtGui import QPixmap, QDesktopServices, QDragEnterEvent, QDropEvent
from PyQt6.QtCore import Qt, QUrl, QSettings
import sys
import requests
import logging
from pathlib import Path

class ImgBBUploader(QWidget):
    MAX_IMAGE_SIZE = 32 * 1024 * 1024 # 32MB size limit

    def __init__(self):
        super().__init__()
        self.settings = QSettings('Nrentzilas', 'ImgBBUploader')
        self.setup_logging()
        self.init_ui()
        self.load_saved_api_key()
        self.setAcceptDrops(True)

    def setup_logging(self):
        logging.basicConfig(
            filename='imgbb_uploader.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def init_ui(self):
        self.setWindowTitle("Nrentzila's ImgBB Uploader")
        self.resize(500, 650)


        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)

        self.setStyleSheet("""
            QWidget {
                background-color: #070e12;
                color: #ffffff;
                font-family: Arial;
                font-size: 14px;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit, QTextEdit {
                background-color: #0c1a20;
                color: #ffffff;
                border: 1px solid #4f46e4;
                padding: 5px;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #4f46e4;
                color: #ffffff;
                padding: 8px;
                border: none;
                border-radius: 5px;
                transition: all 0.3s ease-in-out;
                cursor: pointer;
            }
            QPushButton:hover {
                background-color: #3d3bbd;
                transform: scale(1.05);
            }
            QTextEdit {
                padding: 10px;
            }
            QLabel.link {
                color: #4f46e4;
                text-decoration: underline;
            }
            QLabel.link:hover {
                color: #3d3bbd;
            }
        """)

        api_layout = QFormLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter your ImgBB API Key")
        api_layout.addRow("API Key:", self.api_key_input)

        self.upload_btn = QPushButton("Upload Image")
        self.upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.upload_btn.clicked.connect(self.upload_image)

        image_layout = QVBoxLayout()
        image_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label = QLabel("No Image Selected")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(400, 300)
        self.image_label.setStyleSheet("border: 1px solid #4f46e4; background-color: #0c1a20;")
        image_layout.addWidget(self.image_label)

        self.link_display = QTextEdit()
        self.link_display.setPlaceholderText("The uploaded image link will appear here.")
        self.link_display.setReadOnly(True)

        self.copy_btn = QPushButton("Copy Link")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.clicked.connect(self.copy_link)
        self.copy_btn.setDisabled(True)

        bottom_layout = QHBoxLayout()

        self.api_key_link = QLabel('<a href="https://api.imgbb.com/" style="color: #4f46e4;">Get your ImgBB API Key</a>')
        self.api_key_link.setOpenExternalLinks(True)
        self.api_key_link.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.api_key_link.setCursor(Qt.CursorShape.PointingHandCursor)

        self.github_icon = QLabel()
        self.github_icon.setPixmap(QPixmap("assets/github.png").scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio))
        self.github_icon.setStyleSheet("border: none;")
        self.github_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self.github_icon.mousePressEvent = lambda event: QDesktopServices.openUrl(QUrl("https://github.com/Nrentzilas/ImgBB-Uploader"))

        bottom_layout.addWidget(self.api_key_link)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.github_icon)

        self.main_layout.addLayout(api_layout)
        self.main_layout.addWidget(self.upload_btn)
        self.main_layout.addLayout(image_layout)
        self.main_layout.addWidget(self.link_display)
        self.main_layout.addWidget(self.copy_btn)
        self.main_layout.addLayout(bottom_layout)
        self.setLayout(self.main_layout)

        # Add progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #4f46e4;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4f46e4;
            }
        """)

        # Add tooltips
        self.upload_btn.setToolTip("Click to select and upload an image")
        self.copy_btn.setToolTip("Copy the image URL to clipboard")
        self.api_key_input.setToolTip("Enter your ImgBB API key here")

        # Modify layout
        self.main_layout.insertWidget(4, self.progress_bar)

    def load_saved_api_key(self):
        saved_key = self.settings.value('api_key', '')
        self.api_key_input.setText(saved_key)
        self.imgbb_api_key = saved_key

    def save_api_key(self):
        self.settings.setValue('api_key', self.api_key_input.text().strip())

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for file_path in files:
            if Path(file_path).suffix.lower() in ['.png', '.jpg', '.jpeg', '.bmp']:
                self.handle_image(file_path)
                break

    def handle_image(self, file_path):
        if not self.validate_image_size(file_path):
            self.link_display.setText("Error: Image size exceeds 32MB limit")
            return

        pixmap = QPixmap(file_path)
        scaled_pixmap = pixmap.scaled(
            self.image_label.width(),
            self.image_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)

        try:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(20)
            link = self.upload_to_imgbb(file_path)
            self.link_display.setText(link)
            self.copy_btn.setDisabled(False)
            self.save_api_key()
            logging.info(f"Successfully uploaded image: {file_path}")
        except Exception as e:
            self.link_display.setText(f"Error: {str(e)}")
            self.copy_btn.setDisabled(True)
            logging.error(f"Upload failed: {str(e)}")
        finally:
            self.progress_bar.setVisible(False)

    def validate_image_size(self, file_path):
        return Path(file_path).stat().st_size <= self.MAX_IMAGE_SIZE

    def upload_image(self):
        self.imgbb_api_key = self.api_key_input.text().strip()
        if not self.imgbb_api_key:
            self.link_display.setText("Error: API key is required.")
            self.copy_btn.setDisabled(True)
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )

        if file_path:
            self.handle_image(file_path)

    def upload_to_imgbb(self, file_path):
        url = "https://api.imgbb.com/1/upload"
        try:
            with open(file_path, 'rb') as img_file:
                files = {'image': img_file.read()}
                self.progress_bar.setValue(50)
                response = requests.post(
                    url,
                    params={'key': self.imgbb_api_key},
                    files=files,
                    timeout=30
                )
                self.progress_bar.setValue(90)

            response.raise_for_status()
            data = response.json()

            if 'data' not in data or 'url' not in data['data']:
                raise ValueError("Invalid response format from ImgBB")

            return data['data']['url']
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error: {str(e)}")
        except ValueError as e:
            raise Exception(f"API error: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")

    def copy_link(self):
        clipboard = QApplication.clipboard()
        link = self.link_display.toPlainText()
        clipboard.setText(link)

        if link:
            self.link_display.append("\nLink copied to clipboard!")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ImgBBUploader()
    window.show()
    sys.exit(app.exec())
