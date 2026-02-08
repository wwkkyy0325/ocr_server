# -*- coding: utf-8 -*-
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QImage

class ClipboardWatcher(QObject):
    """
    Monitors system clipboard for new images
    """
    image_captured = pyqtSignal(QImage)

    def __init__(self):
        super().__init__()
        self.clipboard = QApplication.clipboard()
        # Connect to dataChanged signal
        self.clipboard.dataChanged.connect(self.on_clipboard_changed)
        self.is_listening = False
        
        # Debounce timer to prevent locking clipboard/conflicts
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(200) # 200ms delay
        self.timer.timeout.connect(self._process_clipboard)

    def start(self):
        self.is_listening = True

    def stop(self):
        self.is_listening = False

    def on_clipboard_changed(self):
        if not self.is_listening:
            return
        # Restart timer (debounce)
        self.timer.start()
        
    def _process_clipboard(self):
        if not self.is_listening:
            return

        try:
            # Process
            mime_data = self.clipboard.mimeData()
            if mime_data.hasImage():
                image = self.clipboard.image()
                if not image.isNull():
                    self.image_captured.emit(image)
        except Exception as e:
            print(f"Error reading clipboard: {e}")
