import sys
import os
import json
import subprocess
import winreg
import psutil
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QPushButton, QLabel, QLineEdit, 
    QFileDialog, QCheckBox, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon

CONFIG_FILE = "boot_config.json"
REG_APP_NAME = "Mir4_GameBootloader_PhamHung"


def get_current_exe_path():
    """Lấy đường dẫn chính xác của file app đang chạy"""
    if getattr(sys, 'frozen', False):
        return sys.executable
    return os.path.abspath(__file__)


def is_process_running_by_path(target_path):
    """Kiểm tra xem file chạy có đang hoạt động trong danh sách tiến trình Windows không"""
    if not target_path or not os.path.exists(target_path):
        return False
    
    target_name = os.path.basename(target_path).lower()
    target_abs = os.path.abspath(target_path).lower()

    try:
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                # So khớp bằng đường dẫn tuyệt đối hoặc tên file thực thi
                p_exe = proc.info.get('exe')
                if p_exe and os.path.abspath(p_exe).lower() == target_abs:
                    return True
                p_name = proc.info.get('name')
                if p_name and p_name.lower() == target_name:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return False


class BootloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Game Bootloader Hub - Auto Launch & Watchdog [PHAMHUNG]")
        self.setFixedSize(680, 530)
        self.setStyleSheet("background-color: #121214; color: #ececed; font-family: Segoe UI, sans-serif;")

        if os.path.exists("app_icon.ico"):
            self.setWindowIcon(QIcon("app_icon.ico"))

        self.config = {
            "qt_path": "",
            "tinker_path": "",
            "auto_start_apps": False,
            "auto_restart_crash": True,
            "delay_seconds": 3
        }
        self.load_config()

        self.init_ui()

        # Timer kiểm tra và tự phục hồi khi crash (Chạy mỗi 5 giây)
        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.timeout.connect(self.check_and_recover_apps)
        self.watchdog_timer.start(5000)

        # Kiểm tra tự động chạy 2 app khi vừa mở app lên
        if self.config.get("auto_start_apps", False):
            delay_ms = self.config.get("delay_seconds", 3) * 1000
            self.status_label.setText(f"Tự động chạy sau {self.config.get('delay_seconds', 3)}s...")
            QTimer.singleShot(delay_ms, self.launch_both_apps)

        # Kiểm tra trạng thái ngay lập tức
        QTimer.singleShot(1000, self.check_app_status_ui)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(12)

        header = QLabel("HỆ THỐNG ĐIỀU KHIỂN & TỰ ĐỘNG PHỤC HỒI KHI CRASH")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("color: #ff7b00; font-size: 15px; font-weight: bold; letter-spacing: 1px;")
        main_layout.addWidget(header)

        # ================= KHUNG ĐƯỜNG DẪN 2 PHẦN MỀM =================
        box_frame = QFrame()
        box_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a1e;
                border: 1px solid #2e2e38;
                border-radius: 8px;
            }
        """)
        box_layout = QVBoxLayout(box_frame)
        box_layout.setContentsMargins(15, 12, 15, 12)
        box_layout.setSpacing(10)

        # 1. Phần mềm QT
        h_qt_title = QHBoxLayout()
        lbl_qt = QLabel("1. Phần mềm QT:")
        lbl_qt.setStyleSheet("border: none; font-weight: bold; color: #00e5ff;")
        h_qt_title.addWidget(lbl_qt)
        
        self.status_qt_badge = QLabel("⚪ Đang kiểm tra...")
        self.status_qt_badge.setStyleSheet("border: none; font-size: 11px; font-weight: bold; color: #888;")
        h_qt_title.addWidget(self.status_qt_badge)
        h_qt_title.addStretch()
        box_layout.addLayout(h_qt_title)

        h_qt = QHBoxLayout()
        self.txt_qt = QLineEdit(self.config["qt_path"])
        self.txt_qt.setPlaceholderText("Đường dẫn file QT (.exe)...")
        self.txt_qt.setStyleSheet("background-color: #242429; color: white; border: 1px solid #444; border-radius: 4px; padding: 6px;")
        h_qt.addWidget(self.txt_qt)

        btn_browse_qt = QPushButton("Chọn file...")
        btn_browse_qt.setFixedHeight(30)
        btn_browse_qt.setStyleSheet("background-color: #383842; color: white; border-radius: 4px; padding: 0 10px;")
        btn_browse_qt.clicked.connect(lambda: self.browse_file(self.txt_qt))
        h_qt.addWidget(btn_browse_qt)

        btn_run_qt = QPushButton("Chạy QT")
        btn_run_qt.setFixedHeight(30)
        btn_run_qt.setStyleSheet("background-color: #007acc; color: white; font-weight: bold; border-radius: 4px; padding: 0 12px;")
        btn_run_qt.clicked.connect(lambda: self.launch_single(self.txt_qt.text(), "QT"))
        h_qt.addWidget(btn_run_qt)
        box_layout.addLayout(h_qt)

        # 2. Phần mềm TINKER
        h_tinker_title = QHBoxLayout()
        lbl_tinker = QLabel("2. Phần mềm TINKER:")
        lbl_tinker.setStyleSheet("border: none; font-weight: bold; color: #00e676;")
        h_tinker_title.addWidget(lbl_tinker)

        self.status_tinker_badge = QLabel("⚪ Đang kiểm tra...")
        self.status_tinker_badge.setStyleSheet("border: none; font-size: 11px; font-weight: bold; color: #888;")
        h_tinker_title.addWidget(self.status_tinker_badge)
        h_tinker_title.addStretch()
        box_layout.addLayout(h_tinker_title)

        h_tinker = QHBoxLayout()
        self.txt_tinker = QLineEdit(self.config["tinker_path"])
        self.txt_tinker.setPlaceholderText("Đường dẫn file TINKER (.exe)...")
        self.txt_tinker.setStyleSheet("background-color: #242429; color: white; border-radius: 4px; border: 1px solid #444; padding: 6px;")
        h_tinker.addWidget(self.txt_tinker)

        btn_browse_tinker = QPushButton("Chọn file...")
        btn_browse_tinker.setFixedHeight(30)
        btn_browse_tinker.setStyleSheet("background-color: #383842; color: white; border-radius: 4px; padding: 0 10px;")
        btn_browse_tinker.clicked.connect(lambda: self.browse_file(self.txt_tinker))
        h_tinker.addWidget(btn_browse_tinker)

        btn_run_tinker = QPushButton("Chạy Tinker")
        btn_run_tinker.setFixedHeight(30)
        btn_run_tinker.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; border-radius: 4px; padding: 0 12px;")
        btn_run_tinker.clicked.connect(lambda: self.launch_single(self.txt_tinker.text(), "TINKER"))
        h_tinker.addWidget(btn_run_tinker)
        box_layout.addLayout(h_tinker)

        main_layout.addWidget(box_frame)

        # ================= TÙY CHỌN TỰ ĐỘNG & BẢO VỆ =================
        options_vbox = QVBoxLayout()
        options_vbox.setSpacing(6)

        h_opts1 = QHBoxLayout()
        self.chk_windows_startup = QCheckBox("Tự khởi động cùng Windows")
        self.chk_windows_startup.setChecked(self.is_startup_enabled())
        self.chk_windows_startup.setStyleSheet("color: #ffffff; font-weight: bold;")
        self.chk_windows_startup.stateChanged.connect(self.toggle_startup)
        h_opts1.addWidget(self.chk_windows_startup)

        self.chk_auto_launch_tools = QCheckBox("Tự bật 2 Tool khi mở App")
        self.chk_auto_launch_tools.setChecked(self.config["auto_start_apps"])
        self.chk_auto_launch_tools.setStyleSheet("color: #ffffff; font-weight: bold;")
        self.chk_auto_launch_tools.stateChanged.connect(self.save_settings)
        h_opts1.addWidget(self.chk_auto_launch_tools)
        options_vbox.addLayout(h_opts1)

        # Tùy chọn tự phục hồi khi crash
        self.chk_auto_restart = QCheckBox("🛡️ Giám sát & Tự động bật lại khi phần mềm bị Tắt / Crash")
        self.chk_auto_restart.setChecked(self.config.get("auto_restart_crash", True))
        self.chk_auto_restart.setStyleSheet("color: #ffaa00; font-weight: bold; font-size: 13px;")
        self.chk_auto_restart.stateChanged.connect(self.save_settings)
        options_vbox.addWidget(self.chk_auto_restart)

        main_layout.addLayout(options_vbox)

        # NÚT KHỞI CHẠY CẢ 2 TOOL
        self.btn_launch_all = QPushButton("🚀 KHỞI CHẠY CẢ 2 PHẦN MỀM NGAY")
        self.btn_launch_all.setFixedHeight(40)
        self.btn_launch_all.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff6600, stop:1 #ff8533);
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover { background: #ff944d; }
        """)
        self.btn_launch_all.clicked.connect(self.launch_both_apps)
        main_layout.addWidget(self.btn_launch_all)

        self.status_label = QLabel("Hệ thống giám sát đang hoạt động.")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #00e676; font-size: 12px; font-weight: bold;")
        main_layout.addWidget(self.status_label)

        # ================= BANNER QUẢNG CÁO PHẠM HƯNG =================
        ad_banner = QFrame()
        ad_banner.setFixedHeight(65)
        ad_banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #18090a, stop:0.5 #200f12, stop:1 #18090a);
                border: 2px solid #ff2a2a;
                border-radius: 6px;
            }
        """)
        ad_layout = QHBoxLayout(ad_banner)
        ad_layout.setContentsMargins(15, 4, 15, 4)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(1)
        info_layout.addWidget(QLabel("<span style='color:#00e5ff; font-weight:bold;'>Design by: PHAMHUNG</span> | <span style='color:#ffe600;'>ZALO: 0392771558</span>"))
        info_layout.addWidget(QLabel("<span style='color:#ffffff;'>FB: Phạm Văn Hưng</span>"))
        ad_layout.addLayout(info_layout)
        ad_layout.addStretch()

        badge = QLabel("BUY / SELL GOLD MIR4")
        badge.setStyleSheet("""
            background: #d32f2f; color: #ffeb3b; font-weight: bold; 
            padding: 4px 12px; border: 1px solid #ffe600; border-radius: 4px;
        """)
        ad_layout.addWidget(badge)
        main_layout.addWidget(ad_banner)

    # ================= LOGIC XỬ LÝ & BẢO VỆ =================

    def browse_file(self, target_line_edit):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file chương trình", "", "Executable Files (*.exe *.bat *.py);;All Files (*.*)"
        )
        if file_path:
            target_line_edit.setText(file_path)
            self.save_settings()
            self.check_app_status_ui()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config.update(json.load(f))
            except Exception:
                pass

    def save_settings(self):
        self.config["qt_path"] = self.txt_qt.text().strip()
        self.config["tinker_path"] = self.txt_tinker.text().strip()
        self.config["auto_start_apps"] = self.chk_auto_launch_tools.isChecked()
        self.config["auto_restart_crash"] = self.chk_auto_restart.isChecked()
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def launch_single(self, path, name):
        self.save_settings()
        if not path or not os.path.exists(path):
            return False
        try:
            app_dir = os.path.dirname(path)
            subprocess.Popen(path, cwd=app_dir, shell=True)
            self.status_label.setText(f"Đã gọi {name} thành công.")
            QTimer.singleShot(1500, self.check_app_status_ui)
            return True
        except Exception as e:
            self.status_label.setText(f"Lỗi khởi chạy {name}: {str(e)}")
            return False

    def launch_both_apps(self):
        self.launch_single(self.txt_qt.text(), "QT")
        self.launch_single(self.txt_tinker.text(), "TINKER")

    def check_app_status_ui(self):
        """Cập nhật huy hiệu trạng thái xanh/đỏ cho từng tool"""
        qt_running = is_process_running_by_path(self.txt_qt.text().strip())
        if qt_running:
            self.status_qt_badge.setText("🟢 ĐANG CHẠY (ONLINE)")
            self.status_qt_badge.setStyleSheet("border: none; font-size: 11px; font-weight: bold; color: #00e676;")
        else:
            self.status_qt_badge.setText("🔴 ĐÃ DỪNG (OFFLINE)")
            self.status_qt_badge.setStyleSheet("border: none; font-size: 11px; font-weight: bold; color: #ff5252;")

        tinker_running = is_process_running_by_path(self.txt_tinker.text().strip())
        if tinker_running:
            self.status_tinker_badge.setText("🟢 ĐANG CHẠY (ONLINE)")
            self.status_tinker_badge.setStyleSheet("border: none; font-size: 11px; font-weight: bold; color: #00e676;")
        else:
            self.status_tinker_badge.setText("🔴 ĐÃ DỪNG (OFFLINE)")
            self.status_tinker_badge.setStyleSheet("border: none; font-size: 11px; font-weight: bold; color: #ff5252;")

        return qt_running, tinker_running

    def check_and_recover_apps(self):
        """Hàm Watchdog chạy định kỳ để tự khởi động lại khi phát hiện tool bị tắt"""
        qt_path = self.txt_qt.text().strip()
        tinker_path = self.txt_tinker.text().strip()

        qt_on, tinker_on = self.check_app_status_ui()

        # Nếu không bật chế độ tự phục hồi thì chỉ xem trạng thái
        if not self.chk_auto_restart.isChecked():
            return

        # Kiểm tra và bật lại QT nếu bị tắt
        if qt_path and os.path.exists(qt_path) and not qt_on:
            self.status_label.setText("Phát hiện QT bị tắt! Đang tự động bật lại...")
            self.launch_single(qt_path, "QT")

        # Kiểm tra và bật lại TINKER nếu bị tắt
        if tinker_path and os.path.exists(tinker_path) and not tinker_on:
            self.status_label.setText("Phát hiện TINKER bị tắt! Đang tự động bật lại...")
            self.launch_single(tinker_path, "TINKER")

    # ================= REGISTRY STARTUP =================

    def is_startup_enabled(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, REG_APP_NAME)
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def toggle_startup(self, state):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if state == Qt.Checked:
                exe_path = f'"{get_current_exe_path()}"'
                winreg.SetValueEx(key, REG_APP_NAME, 0, winreg.REG_SZ, exe_path)
                self.status_label.setText("Đã kích hoạt tự khởi động cùng Windows.")
            else:
                try:
                    winreg.DeleteValue(key, REG_APP_NAME)
                except FileNotFoundError:
                    pass
                self.status_label.setText("Đã tắt tự khởi động cùng Windows.")
            winreg.CloseKey(key)
        except Exception as e:
            QMessageBox.warning(self, "Lỗi Registry", f"Không thể thiết lập khởi động cùng Windows: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BootloaderApp()
    window.show()
    sys.exit(app.exec_())