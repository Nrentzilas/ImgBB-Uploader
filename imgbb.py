from PyQt6.QtWidgets import (
    QApplication, QLabel, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout,
    QWidget, QTextEdit, QLineEdit, QFormLayout
)
from PyQt6.QtGui import QPixmap, QDesktopServices
from PyQt6.QtCore import Qt, QUrl
import sys
import requests

class ImgBBUploader(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.imgbb_api_key = None  

    def init_ui(self):
        self.setWindowTitle("ImgBB Uploader By Nrentzilas")
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
            }
            QPushButton:hover {
                background-color: #3d3bbd;
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
        self.copy_btn.clicked.connect(self.copy_link)
        self.copy_btn.setDisabled(True)


        bottom_layout = QHBoxLayout()

        self.api_key_link = QLabel('<a href="https://api.imgbb.com/" style="color: #4f46e4;">Get your ImgBB API Key</a>')
        self.api_key_link.setOpenExternalLinks(True)
        self.api_key_link.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.github_icon = QLabel()
        self.github_icon.setPixmap(QPixmap("assets/github.png").scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio))
        self.github_icon.setOpenExternalLinks(True)
        self.github_icon.setStyleSheet("cursor: pointer;")
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
            pixmap = QPixmap(file_path)
            scaled_pixmap = pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            
            try:
                link = self.upload_to_imgbb(file_path)
                self.link_display.setText(link)
                self.copy_btn.setDisabled(False)  
            except Exception as e:
                self.link_display.setText(f"Error: {e}")
                self.copy_btn.setDisabled(True)

    def upload_to_imgbb(self, file_path):
        url = "https://api.imgbb.com/1/upload"
        with open(file_path, 'rb') as img_file:
            files = {'image': img_file.read()}
            response = requests.post(url, params={'key': self.imgbb_api_key}, files=files)
        
        if response.status_code == 200:
            return response.json()['data']['url']
        else:
            raise Exception(f"Failed to upload image: {response.status_code} {response.text}")

    def copy_link(self):
        # Copy the link to the clipboard
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
