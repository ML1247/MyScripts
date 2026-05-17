# -*- coding: utf-8 -*-
"""
时光机文件浏览器 
"""

import maya.cmds as cmds
import maya.mel as mel
import os
import sys

# Python 2/3 兼容性处理
if sys.version_info[0] >= 3:
    unicode = str

# ==== 1. 内嵌的"时光机"主脚本 ====

TIME_MACHINE_SCRIPT = r'''#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Maya时光机文件浏览器

import maya.cmds as cmds
import maya.mel as mel
import os
import json
import sys
import time
from datetime import datetime

try:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
    from PySide2.QtCore import Qt, Signal
    HAS_QT = True
except ImportError:
    try:
        from PySide6 import QtWidgets, QtCore, QtGui
        from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
        from PySide6.QtCore import Qt, Signal
        HAS_QT = True
    except ImportError:
        from PyQt5 import QtWidgets, QtCore, QtGui
        from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
        from PyQt5.QtCore import Qt, pyqtSignal as Signal
        HAS_QT = True
    except ImportError:
        HAS_QT = False

CONFIG_PATH = os.path.join(cmds.internalVar(userAppDir=True), "TimeMachineConfig.json")
DEFAULT_CONFIG = {
    "favorite_folders": [],
    "recent_files": []
}

def normalize_path(path):
    """统一路径格式：将反斜杠转换为正斜杠，确保路径一致性"""
    if not path:
        return path
    return path.replace('\\', '/')

def load_config():
    try:
        if sys.version_info[0] >= 3:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            with open(CONFIG_PATH, 'r') as f:
                data = json.load(f)

        for k, v in DEFAULT_CONFIG.items():
            if k not in data:
                data[k] = v
        
        for fav in data.get("favorite_folders", []):
            if "path" in fav:
                fav["path"] = normalize_path(fav["path"])
        data["recent_files"] = [normalize_path(f) for f in data.get("recent_files", []) if f]
        
        return data
    except:
        return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        for fav in config.get("favorite_folders", []):
            if "path" in fav:
                fav["path"] = normalize_path(fav["path"])
        config["recent_files"] = [normalize_path(f) for f in config.get("recent_files", []) if f]
        
        if sys.version_info[0] >= 3:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        else:
            with open(CONFIG_PATH, 'w') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
    except:
        pass

def get_current_file_dir():
    """获取当前打开文件的目录路径"""
    current_file = cmds.file(q=True, sceneName=True)
    if current_file and os.path.exists(current_file):
        return normalize_path(os.path.dirname(current_file))
    else:
        return normalize_path(cmds.workspace(q=True, rd=True))

def get_parent(path):
    if path and os.path.isdir(path):
        return normalize_path(os.path.dirname(path.rstrip(os.sep)))
    else:
        return ""

def get_desktop():
    """获取桌面路径"""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(255)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0, None, 0, buf)
        return buf.value.replace('\\', '/')
    except:
        return normalize_path(os.path.join(os.path.expanduser("~"), "Desktop"))

def get_autosave():
    """获取 Maya 自动保存目录路径"""
    try:
        enabled = cmds.autoSave(q=True, enable=True)
        
        if enabled:
            save_dir = cmds.autoSave(q=True, destinationFolder=True)
            
            if save_dir:
                save_dir = normalize_path(save_dir)
                
                if os.path.exists(save_dir):
                    return save_dir
                else:
                    try:
                        os.makedirs(save_dir)
                        return save_dir
                    except:
                        pass
            else:
                project_dir = normalize_path(cmds.workspace(q=True, rd=True))
                default_dir = normalize_path(os.path.join(project_dir, "autosave"))
                if not os.path.exists(default_dir):
                    try:
                        os.makedirs(default_dir)
                    except:
                        pass
                return default_dir
        
        return get_current_file_dir()
        
    except Exception as e:
        return get_current_file_dir()

def natural_sort(items, key=None):
    import re
    if key is None:
        convert = lambda t: int(t) if t.isdigit() else t.lower()
        return sorted(items, key=lambda x: [convert(c) for c in re.split('([0-9]+)', x)])
    else:
        convert = lambda t: int(t) if t.isdigit() else t.lower()
        return sorted(items, key=lambda x: [convert(c) for c in re.split('([0-9]+)', key(x))])

def format_file_size(size_bytes):
    """将字节转换为人类可读的文件大小"""
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.1f} {units[i]}"

def format_date(timestamp):
    """格式化日期时间"""
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return "----/--/-- --:--"

def create_folder_icon():
    pixmap = QtGui.QPixmap(16, 16)
    pixmap.fill(QtGui.QColor(0, 0, 0, 0))
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setBrush(QtGui.QColor("#e8b84b"))
    painter.setPen(QtGui.QColor("#c49a30"))
    painter.drawRect(1, 4, 14, 11)
    painter.setBrush(QtGui.QColor("#e8b84b"))
    painter.drawRect(1, 2, 7, 3)
    painter.end()
    return QtGui.QIcon(pixmap)

def create_file_icon():
    pixmap = QtGui.QPixmap(16, 16)
    pixmap.fill(QtGui.QColor(0, 0, 0, 0))
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setBrush(QtGui.QColor("#7eb8da"))
    painter.setPen(QtGui.QColor("#5a9cc5"))
    points = [QtCore.QPointF(3, 1), QtCore.QPointF(11, 1), QtCore.QPointF(14, 4), QtCore.QPointF(14, 15), QtCore.QPointF(3, 15)]
    painter.drawPolygon(points)
    painter.setBrush(QtGui.QColor("#a0d4f0"))
    tri = [QtCore.QPointF(11, 1), QtCore.QPointF(11, 4), QtCore.QPointF(14, 4)]
    painter.drawPolygon(tri)
    painter.end()
    return QtGui.QIcon(pixmap)

_folder_icon = None
_file_icon = None

def get_folder_icon():
    global _folder_icon
    if _folder_icon is None:
        _folder_icon = create_folder_icon()
    return _folder_icon

def get_file_icon():
    global _file_icon
    if _file_icon is None:
        _file_icon = create_file_icon()
    return _file_icon

class FileTableWidget(QTableWidget):
    fileDoubleClicked = Signal(int)

    def __init__(self, parent=None):
        super(FileTableWidget, self).__init__(parent)
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels([u"名称", u"修改日期", u"大小"])
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionsMovable(False)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.setColumnWidth(1, 120)
        self.setColumnWidth(2, 65)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(22)
        self.setShowGrid(True)
        self.cellDoubleClicked.connect(lambda row, col: self.fileDoubleClicked.emit(row))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHorizontalStretch(1)
        self.setSizePolicy(sizePolicy)

    def set_data(self, data_list):
        self.setRowCount(0)
        self.setRowCount(len(data_list))
        for row, (icon, name, date_str, size_str) in enumerate(data_list):
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.UserRole, name)
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            name_item.setToolTip(name)
            if icon == "📂":
                name_item.setIcon(get_folder_icon())
                name_item.setForeground(QtGui.QColor("#ffcc66"))
            else:
                name_item.setIcon(get_file_icon())
            self.setItem(row, 0, name_item)
            
            date_item = QTableWidgetItem(date_str)
            date_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.setItem(row, 1, date_item)
            
            size_item = QTableWidgetItem(size_str)
            size_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.setItem(row, 2, size_item)

    def get_selected_name(self, row):
        item = self.item(row, 0)
        if item:
            return item.data(Qt.UserRole)
        return None

class FavTableWidget(QTableWidget):
    favDoubleClicked = Signal(int)

    def __init__(self, parent=None):
        super(FavTableWidget, self).__init__(parent)
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels([u"常用目录"])
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(20)
        self.setShowGrid(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setVisible(False)
        self.setStyleSheet("font-size: 13px;")
        self.cellDoubleClicked.connect(lambda row, col: self.favDoubleClicked.emit(row))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setVerticalStretch(1)
        self.setSizePolicy(sizePolicy)

    def set_data(self, names):
        self.setRowCount(0)
        self.setRowCount(len(names))
        for row, name in enumerate(names):
            item = QTableWidgetItem(name)
            item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.setItem(row, 0, item)

class TimeMachineWindow:
    _instance = None

    def __init__(self):
        self.config = load_config()
        self.current_path = get_current_file_dir()
        self.recent_files_data = []
        self.last_entered_folder = None

        if not HAS_QT:
            self.build_basic_ui()
            return

        self.create_qt_window()
        QtWidgets.QApplication.instance().processEvents()
        QtCore.QTimer.singleShot(100, self.refresh_all)

    def create_qt_window(self):
        try:
            import maya.OpenMayaUI as omui
            from shiboken2 import wrapInstance
            ptr = omui.MQtUtil.mainWindow()
            parent = wrapInstance(int(ptr), QtWidgets.QMainWindow)
        except:
            parent = None

        self.win = QtWidgets.QMainWindow(parent)
        self.win.setWindowTitle(u"时光机")
        self.win.setMinimumSize(800, 450)
        self.win.resize(950, 550)

        central_widget = QtWidgets.QWidget()
        self.win.setCentralWidget(central_widget)

        main_vbox = QtWidgets.QVBoxLayout(central_widget)
        main_vbox.setContentsMargins(5, 5, 5, 5)
        main_vbox.setSpacing(3)

        top_toolbar = QtWidgets.QHBoxLayout()
        top_toolbar.setSpacing(3)

        btn_refresh = QtWidgets.QPushButton(u"⟳")
        btn_refresh.setFixedWidth(30)
        btn_refresh.setToolTip(u"刷新")
        btn_refresh.clicked.connect(self.refresh_file_list)

        btn_browse = QtWidgets.QPushButton("...")
        btn_browse.setFixedWidth(30)
        btn_browse.setToolTip(u"浏览")
        btn_browse.clicked.connect(self.select_folder)

        self.path_label = QtWidgets.QLabel("")
        self.path_label.setStyleSheet("QLabel { background-color: #3c3c3c; color: #ffffff; padding: 3px; border-radius: 3px; }")
        self.path_label.setMinimumHeight(24)

        btn_add_fav = QtWidgets.QPushButton("+")
        btn_add_fav.setFixedWidth(30)
        btn_add_fav.setToolTip(u"添加收藏")
        btn_add_fav.clicked.connect(self.add_fav)

        btn_open = QtWidgets.QPushButton("O")
        btn_open.setFixedWidth(30)
        btn_open.setToolTip(u"打开文件夹")
        btn_open.clicked.connect(self.open_folder)

        btn_close = QtWidgets.QPushButton("X")
        btn_close.setFixedWidth(30)
        btn_close.setToolTip(u"关闭")
        btn_close.clicked.connect(self.close_window)

        top_toolbar.addWidget(btn_refresh)
        top_toolbar.addWidget(btn_browse)
        top_toolbar.addWidget(self.path_label, 1)
        top_toolbar.addWidget(btn_add_fav)
        top_toolbar.addWidget(btn_open)
        top_toolbar.addWidget(btn_close)

        main_vbox.addLayout(top_toolbar)

        content_hbox = QtWidgets.QHBoxLayout()
        content_hbox.setSpacing(3)

        left_panel = QtWidgets.QWidget()
        left_panel.setMinimumWidth(150)
        left_panel.setMaximumWidth(200)
        left_vbox = QtWidgets.QVBoxLayout(left_panel)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(3)

        btn_current = QtWidgets.QPushButton(u"当前文件")
        btn_current.setMinimumHeight(24)
        btn_current.clicked.connect(self.go_current_file)

        btn_recent = QtWidgets.QPushButton(u"最近打开")
        btn_recent.setMinimumHeight(24)
        btn_recent.clicked.connect(self.show_recent)

        btn_desktop = QtWidgets.QPushButton(u"桌面目录")
        btn_desktop.setMinimumHeight(24)
        btn_desktop.clicked.connect(self.go_desktop)

        btn_autosave = QtWidgets.QPushButton(u"自动保存")
        btn_autosave.setMinimumHeight(24)
        btn_autosave.clicked.connect(self.go_autosave)

        fav_header = QtWidgets.QHBoxLayout()
        fav_header.setSpacing(3)
        fav_label = QtWidgets.QLabel(u"常用目录")
        fav_label.setStyleSheet("font-weight: bold;")
        spacer = QtWidgets.QSpacerItem(20, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)

        btn_fav_add = QtWidgets.QPushButton("+")
        btn_fav_add.setFixedSize(26, 22)
        btn_fav_add.clicked.connect(self.add_fav)

        btn_fav_del = QtWidgets.QPushButton("-")
        btn_fav_del.setFixedSize(26, 22)
        btn_fav_del.clicked.connect(self.del_fav)

        fav_header.addWidget(fav_label)
        fav_header.addItem(spacer)
        fav_header.addWidget(btn_fav_add)
        fav_header.addWidget(btn_fav_del)

        self.fav_table = FavTableWidget()
        self.fav_table.setMinimumHeight(200)
        self.fav_table.itemClicked.connect(self._on_fav_item_clicked)

        left_vbox.addWidget(btn_current)
        left_vbox.addWidget(btn_recent)
        left_vbox.addWidget(btn_desktop)
        left_vbox.addWidget(btn_autosave)
        left_vbox.addLayout(fav_header)
        left_vbox.addWidget(self.fav_table, 1)

        content_hbox.addWidget(left_panel)
        content_hbox.setStretchFactor(left_panel, 0)

        right_panel = QtWidgets.QWidget()
        right_vbox = QtWidgets.QVBoxLayout(right_panel)
        right_vbox.setContentsMargins(0, 0, 0, 0)
        right_vbox.setSpacing(3)

        filter_bar = QtWidgets.QHBoxLayout()
        filter_bar.setSpacing(5)

        self.ma_chk = QtWidgets.QCheckBox("ma")
        self.ma_chk.setChecked(True)
        self.ma_chk.stateChanged.connect(self.on_filter_change)

        self.mb_chk = QtWidgets.QCheckBox("mb")
        self.mb_chk.setChecked(True)
        self.mb_chk.stateChanged.connect(self.on_filter_change)

        self.fbx_chk = QtWidgets.QCheckBox("fbx")
        self.fbx_chk.setChecked(False)
        self.fbx_chk.stateChanged.connect(self.on_filter_change)

        self.rev_chk = QtWidgets.QCheckBox(u"倒序")
        self.rev_chk.stateChanged.connect(self.on_filter_change)

        spacer = QtWidgets.QSpacerItem(40, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)

        btn_parent = QtWidgets.QPushButton(u"上层目录")
        btn_parent.setMinimumWidth(80)
        btn_parent.clicked.connect(self.go_parent)

        filter_bar.addWidget(self.ma_chk)
        filter_bar.addWidget(self.mb_chk)
        filter_bar.addWidget(self.fbx_chk)
        filter_bar.addWidget(self.rev_chk)
        filter_bar.addItem(spacer)
        filter_bar.addWidget(btn_parent)

        self.file_table = FileTableWidget()
        self.file_table.setMinimumHeight(300)
        self.file_table.cellDoubleClicked.connect(self._on_file_cell_double_clicked)
        self.file_table.horizontalHeader().sectionResized.connect(self.on_column_resized)

        right_vbox.addLayout(filter_bar)
        right_vbox.addWidget(self.file_table, 1)

        content_hbox.addWidget(right_panel, 1)
        content_hbox.setStretchFactor(right_panel, 1)

        main_vbox.addLayout(content_hbox)
        main_vbox.setStretchFactor(content_hbox, 1)

        bottom_bar = QtWidgets.QHBoxLayout()
        self.count_txt = QtWidgets.QLabel("")
        bottom_bar.addWidget(self.count_txt)
        bottom_bar.addStretch()

        main_vbox.addLayout(bottom_bar)

        self.apply_stylesheet(central_widget)
        self.win.show()
        QtCore.QTimer.singleShot(50, self.refresh_all)

    def close_window(self):
        if self.win:
            self.win.close()

    def apply_stylesheet(self, widget):
        style = """
        QWidget {
            background-color: #484848;
            color: #cccccc;
        }
        QPushButton {
            background-color: #595959;
            border: 1px solid #3d3d3d;
            border-radius: 2px;
            padding: 4px 8px;
            min-height: 24px;
            color: #cccccc;
        }
        QPushButton:hover {
            background-color: #666666;
        }
        QPushButton:pressed {
            background-color: #404040;
        }
        QCheckBox {
            spacing: 5px;
            color: #cccccc;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border: 2px solid #888888;
            background-color: #383838;
            border-radius: 3px;
        }
        QCheckBox::indicator:hover {
            border-color: #aaaaaa;
        }
        QCheckBox::indicator:checked {
            background-color: #2196F3;
            border-color: #2196F3;
        }
        QTableWidget {
            background-color: #383838;
            alternate-background-color: #3d3d3d;
            gridline-color: #505050;
            border: 1px solid #3d3d3d;
            color: #cccccc;
        }
        QTableWidget::item {
            padding: 1px 4px;
        }
        QTableWidget::item:selected {
            background-color: #094771;
            color: #ffffff;
        }
        QHeaderView::section {
            background-color: #4a4a4a;
            color: #cccccc;
            padding: 3px 5px;
            border: none;
            border-right: 1px solid #3d3d3d;
            border-bottom: 1px solid #3d3d3d;
            font-weight: bold;
        }
        QHeaderView::section:hover {
            background-color: #555555;
        }
        QScrollBar:vertical {
            background-color: #383838;
            width: 6px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background-color: #595959;
            border-radius: 3px;
            min-height: 18px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #707070;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar:horizontal {
            background-color: #383838;
            height: 6px;
            margin: 0px;
        }
        QScrollBar::handle:horizontal {
            background-color: #595959;
            border-radius: 3px;
            min-width: 18px;
        }
        QScrollBar::handle:horizontal:hover {
            background-color: #707070;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }
        QLabel {
            color: #cccccc;
        }
        """
        widget.setStyleSheet(style)

    def on_column_resized(self, col_index, old_size, new_size):
        pass

    def _on_fav_item_clicked(self, item):
        if item:
            clicked_name = item.text()
            for fav in self.config["favorite_folders"]:
                if fav["name"] == clicked_name:
                    self.current_path = fav["path"]
                    self.recent_files_data = []
                    self.refresh_file_list()
                    break

    def _on_fav_cell_double_clicked(self, row, col):
        if 0 <= row < len(self.config["favorite_folders"]):
            item = self.fav_table.item(row, 0)
            if item:
                clicked_name = item.text()
                for fav in self.config["favorite_folders"]:
                    if fav["name"] == clicked_name:
                        self.current_path = fav["path"]
                        self.recent_files_data = []
                        self.refresh_file_list()
                        break

    def _on_file_cell_double_clicked(self, row, col):
        name = self.file_table.get_selected_name(row)
        if not name:
            return

        full = normalize_path(os.path.join(self.current_path, name))

        if self.recent_files_data and row < len(self.recent_files_data):
            recent_full = self.recent_files_data[row]
            if not os.path.exists(full) and os.path.exists(recent_full):
                full = recent_full
            if os.path.isdir(recent_full) and not os.path.isdir(full):
                full = recent_full

        if os.path.isdir(full):
            self.last_entered_folder = os.path.basename(full)
            self.current_path = full
            self.recent_files_data = []
            self.refresh_file_list()
            return

        if full.lower().endswith((".ma", ".mb")):
            if cmds.file(q=True, modified=True):
                result = cmds.confirmDialog(
                    title=u"保存场景",
                    message=u"当前场景已修改，是否保存？",
                    button=[u"保存", u"不保存", u"取消"],
                    defaultButton=u"保存",
                    cancelButton=u"取消",
                    dismissString=u"取消"
                )
                if result == u"保存":
                    cmds.file(save=True)
                elif result == u"取消":
                    return

            try:
                cmds.file(full, open=True, force=True)

                if full in self.config["recent_files"]:
                    self.config["recent_files"].remove(full)
                self.config["recent_files"].insert(0, full)
                self.config["recent_files"] = self.config["recent_files"][:20]
                save_config(self.config)
            except Exception as e:
                cmds.warning(u"时光机：打开文件失败 - " + str(e))

        elif full.lower().endswith(".fbx"):
            if cmds.file(q=True, modified=True):
                result = cmds.confirmDialog(
                    title=u"保存场景",
                    message=u"当前场景已修改，是否保存？",
                    button=[u"保存", u"不保存", u"取消"],
                    defaultButton=u"保存",
                    cancelButton=u"取消",
                    dismissString=u"取消"
                )
                if result == u"保存":
                    cmds.file(save=True)
                elif result == u"取消":
                    return

            try:
                cmds.file(new=True, force=True)
                cmds.file(full, i=True, type="FBX", ignoreVersion=True)
            except Exception as e:
                cmds.warning(u"时光机：导入FBX失败 - " + str(e))

        if os.path.dirname(full):
            self.current_path = normalize_path(os.path.dirname(full))

        self.recent_files_data = []
        self.refresh_file_list()

    def build_basic_ui(self):
        cmds.warning("TimeMachineBrowser: 使用基础UI模式，部分功能不可用")

    def on_filter_change(self, *args):
        """当勾选框状态改变时，自动刷新文件列表"""
        self.refresh_file_list()

    def refresh_file_list(self, *args):
        path = self.current_path
        if not path or not os.path.isdir(path):
            path = normalize_path(cmds.workspace(q=True, rd=True))
            self.current_path = path

        if HAS_QT and hasattr(self, 'path_label'):
            self.path_label.setText(path)
        elif hasattr(self, 'path_edit'):
            cmds.textField(self.path_edit, edit=True, text=path)

        exts = []
        if HAS_QT and hasattr(self, 'ma_chk'):
            if self.ma_chk.isChecked():
                exts.append(".ma")
            if self.mb_chk.isChecked():
                exts.append(".mb")
            if self.fbx_chk.isChecked():
                exts.append(".fbx")
            reverse = self.rev_chk.isChecked()
        elif hasattr(self, 'ma_chk'):
            if cmds.checkBox(self.ma_chk, q=True, value=True):
                exts.append(".ma")
            if cmds.checkBox(self.mb_chk, q=True, value=True):
                exts.append(".mb")
            if cmds.checkBox(self.fbx_chk, q=True, value=True):
                exts.append(".fbx")
            reverse = cmds.checkBox(self.rev_chk, q=True, value=True)
        else:
            exts = [".ma", ".mb"]
            reverse = False

        folders = []
        files = []

        try:
            items = os.listdir(path)
            for item in items:
                full = os.path.join(path, item)
                if os.path.isdir(full):
                    try:
                        mtime = os.path.getmtime(full)
                        date_str = format_date(mtime)
                        size_str = "--"
                        folders.append(("📂", item, date_str, size_str))
                    except:
                        folders.append(("📂", item, "----/--/-- --:--", "--"))
                else:
                    name_low = item.lower()
                    for e in exts:
                        if name_low.endswith(e.lower()):
                            try:
                                mtime = os.path.getmtime(full)
                                size = os.path.getsize(full)
                                date_str = format_date(mtime)
                                size_str = format_file_size(size)
                                files.append(("📄", item, date_str, size_str))
                            except:
                                files.append(("📄", item, "----/--/-- --:--", "? B"))
                            break
        except:
            pass

        folders = natural_sort(folders, key=lambda x: x[1])
        files = natural_sort(files, key=lambda x: x[1])
        if reverse:
            folders = folders[::-1]
            files = files[::-1]

        if HAS_QT and hasattr(self, 'file_table'):
            self.file_table.set_data(folders + files)
            self.count_txt.setText(f"文件夹：{len(folders)}  文件：{len(files)}")
            if hasattr(self, 'last_entered_folder') and self.last_entered_folder:
                target = self.last_entered_folder
                self.last_entered_folder = None
                for r in range(self.file_table.rowCount()):
                    item = self.file_table.item(r, 0)
                    if item and item.data(Qt.UserRole) == target:
                        self.file_table.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)
                        self.file_table.selectRow(r)
                        break
        elif hasattr(self, 'file_list'):
            cmds.textScrollList(self.file_list, edit=True, removeAll=True)
            all_items = folders + files
            if all_items:
                cmds.textScrollList(self.file_list, edit=True, append=all_items)
            if hasattr(self, 'count_txt'):
                txt = f"文件夹：{len(folders)}  文件：{len(files)}"
                cmds.text(self.count_txt, edit=True, label=txt)

    def refresh_all(self):
        self.refresh_fav()
        self.refresh_file_list()

    def go_current_file(self, *args):
        self.recent_files_data = []
        self.current_path = get_current_file_dir()
        self.refresh_file_list()

    def select_folder(self, *args):
        self.recent_files_data = []
        path = cmds.fileDialog2(fileMode=3,
                                startingDirectory=self.current_path)
        if path:
            self.current_path = normalize_path(path[0])
            self.refresh_file_list()

    def go_parent(self, *args):
        parent = get_parent(self.current_path)
        if parent:
            self.last_entered_folder = os.path.basename(self.current_path)
            self.current_path = parent
            self.recent_files_data = []
            self.refresh_file_list()

    def open_folder(self, *args):
        if os.path.isdir(self.current_path):
            os.startfile(self.current_path)

    def go_desktop(self, *args):
        self.recent_files_data = []
        self.current_path = get_desktop()
        self.refresh_file_list()

    def go_autosave(self, *args):
        self.recent_files_data = []
        self.current_path = get_autosave()
        self.refresh_file_list()

    def show_recent(self, *args):
        rec_files = self.config["recent_files"]

        valid_files = []
        for f in rec_files:
            if f and os.path.exists(f):
                valid_files.append(f)

        if len(valid_files) != len(rec_files):
            self.config["recent_files"] = valid_files
            save_config(self.config)

        data_list = []
        self.recent_files_data = []
        for f in valid_files:
            try:
                mtime = os.path.getmtime(f)
                date_str = format_date(mtime)
                size = os.path.getsize(f)
                size_str = format_file_size(size)
                data_list.append(("📄", os.path.basename(f), date_str, size_str))
            except:
                data_list.append(("📄", os.path.basename(f), "----/--/-- --:--", "? B"))
            self.recent_files_data.append(f)

        if HAS_QT and hasattr(self, 'file_table'):
            self.file_table.set_data(data_list)
            if data_list:
                self.count_txt.setText(f"最近打开文件：{len(data_list)}")
            else:
                self.count_txt.setText("暂无最近打开的文件")
        elif hasattr(self, 'file_list'):
            cmds.textScrollList(self.file_list, edit=True, removeAll=True)
            if data_list:
                cmds.textScrollList(self.file_list, edit=True, append=data_list)
                txt = f"最近打开文件：{len(data_list)}"
                if hasattr(self, 'count_txt'):
                    cmds.text(self.count_txt, edit=True, label=txt)
            else:
                if hasattr(self, 'count_txt'):
                    cmds.text(self.count_txt, edit=True, label="暂无最近打开的文件")

    def open_selected(self, *args):
        sel = cmds.textScrollList(self.file_list, q=True, selectItem=True)
        if not sel:
            return
        
        selected_text = sel[0]
        # 提取纯文件名（去除图标和后面的日期大小信息）
        # 格式: "📄 文件名\t\t\t日期\t大小"
        # 先分离图标
        no_icon = selected_text.replace("📄 ", "").replace("📂 ", "").strip()
        # 再按制表符分割，取第一部分就是文件名
        clean_name = no_icon.split('\t')[0].strip()
        
        if clean_name and self.recent_files_data:
            idx = cmds.textScrollList(self.file_list, q=True, selectIndexedItem=True)[0] - 1
            if idx < len(self.recent_files_data):
                full = self.recent_files_data[idx]
                if not os.path.exists(full):
                    cmds.warning("时光机：文件不存在 - " + full)
                    return
            else:
                return
        else:
            full = normalize_path(os.path.join(self.current_path, clean_name))
        
        if os.path.isdir(full):
            self.current_path = full
            self.refresh_file_list()
            return
        
        if full.lower().endswith((".ma", ".mb")):
            if cmds.file(q=True, modified=True):
                result = cmds.confirmDialog(
                    title="保存场景",
                    message="当前场景已修改，是否保存？",
                    button=["保存", "不保存", "取消"],
                    defaultButton="保存",
                    cancelButton="取消",
                    dismissString="取消"
                )
                if result == "保存":
                    cmds.file(save=True)
                elif result == "取消":
                    return
            
            try:
                cmds.file(full, open=True, force=True)
                
                if full in self.config["recent_files"]:
                    self.config["recent_files"].remove(full)
                self.config["recent_files"].insert(0, full)
                self.config["recent_files"] = self.config["recent_files"][:20]
                save_config(self.config)
            except Exception as e:
                cmds.warning("时光机：打开文件失败 - " + str(e))
            
        elif full.lower().endswith(".fbx"):
            if cmds.file(q=True, modified=True):
                result = cmds.confirmDialog(
                    title="保存场景",
                    message="当前场景已修改，是否保存？",
                    button=["保存", "不保存", "取消"],
                    defaultButton="保存",
                    cancelButton="取消",
                    dismissString="取消"
                )
                if result == "保存":
                    cmds.file(save=True)
                elif result == "取消":
                    return
            
            try:
                cmds.file(new=True, force=True)
                cmds.file(full, i=True, type="FBX", ignoreVersion=True)
            except Exception as e:
                cmds.warning("时光机：导入FBX失败 - " + str(e))
        
        if os.path.dirname(full):
            self.current_path = normalize_path(os.path.dirname(full))
        
        self.recent_files_data = []
        self.refresh_file_list()

    def add_fav(self, *args):
        res = cmds.promptDialog(
            title="添加收藏",
            message="输入名称：",
            button=["确定", "取消"],
            defaultButton="确定",
            cancelButton="取消",
            dismissString="取消"
        )
        if res == "确定":
            name = cmds.promptDialog(q=True, text=True).strip()
            if name and self.current_path:
                exists = False
                for fav in self.config["favorite_folders"]:
                    if fav["name"] == name:
                        exists = True
                        break
                if exists:
                    cmds.warning("时光机：已存在同名收藏 '" + name + "'")
                else:
                    self.config["favorite_folders"].append(
                        {"name": name, "path": self.current_path}
                    )
                    save_config(self.config)
                    self.refresh_fav()

    def del_fav(self, *args):
        if HAS_QT and hasattr(self, 'fav_table'):
            sel = self.fav_table.selectedItems()
            if not sel:
                return
            row = self.fav_table.row(sel[0])
            if 0 <= row < len(self.config["favorite_folders"]):
                del self.config["favorite_folders"][row]
                save_config(self.config)
                self.refresh_fav()
        elif hasattr(self, 'fav_list'):
            sel = cmds.textScrollList(self.fav_list, q=True, selectIndexedItem=True)
            if not sel:
                return
            idx = sel[0] - 1
            if 0 <= idx < len(self.config["favorite_folders"]):
                del self.config["favorite_folders"][idx]
                save_config(self.config)
                self.refresh_fav()

    def refresh_fav(self):
        names = [x["name"] for x in self.config["favorite_folders"]]
        if HAS_QT and hasattr(self, 'fav_table'):
            self.fav_table.set_data(names)
            try:
                self.fav_table.itemClicked.disconnect()
            except:
                pass
            self.fav_table.itemClicked.connect(self._on_fav_item_clicked)
        elif hasattr(self, 'fav_list'):
            cmds.textScrollList(self.fav_list, edit=True, removeAll=True)
            if names:
                cmds.textScrollList(self.fav_list, edit=True, append=names)

    def on_fav_select(self, *args):
        if HAS_QT and hasattr(self, 'fav_table'):
            sel = self.fav_table.selectedItems()
            if not sel:
                return
            row = self.fav_table.row(sel[0])
            if 0 <= row < len(self.config["favorite_folders"]):
                self.current_path = self.config["favorite_folders"][row]["path"]
                self.recent_files_data = []
                self.refresh_file_list()
        elif hasattr(self, 'fav_list'):
            sel = cmds.textScrollList(self.fav_list, q=True, selectIndexedItem=True)
            if not sel:
                return
            idx = sel[0] - 1
            if 0 <= idx < len(self.config["favorite_folders"]):
                self.current_path = self.config["favorite_folders"][idx]["path"]
                self.refresh_file_list()

_time_machine_window = None

def launch():
    global _time_machine_window
    if HAS_QT:
        if _time_machine_window is not None and hasattr(_time_machine_window, 'win'):
            try:
                _time_machine_window.win.close()
            except:
                pass
        _time_machine_window = TimeMachineWindow()
    else:
        TimeMachineWindow()

if __name__ == "__main__":
    launch()'''


# ==== 2. 安装函数 ====

def install_timemachine():
    tool_module = "TimeMachineBrowser"
    tool_display_name = u"时光机"
    tool_description = u"时光机文件浏览器"

    maya_app_dir = cmds.internalVar(userAppDir=True)
    scripts_dir = os.path.join(maya_app_dir, "scripts")

    if not os.path.exists(scripts_dir):
        os.makedirs(scripts_dir)

    main_script_path = os.path.join(scripts_dir, tool_module + ".py")

    try:
        if sys.version_info[0] >= 3:
            with open(main_script_path, "w", encoding="utf-8") as f:
                f.write(TIME_MACHINE_SCRIPT)
        else:
            with open(main_script_path, "w") as f:
                f.write(TIME_MACHINE_SCRIPT)
        print(u"时光机脚本已保存到: " + main_script_path)
    except Exception as e:
        cmds.warning(u"保存时光机脚本失败: " + str(e))
        return False

    cache_dir = os.path.join(scripts_dir, "__pycache__")
    if os.path.exists(cache_dir):
        import shutil
        try:
            shutil.rmtree(cache_dir)
        except:
            pass

    try:
        current_shelf = mel.eval("tabLayout -q -selectTab $gShelfTopLevel;")
        if not current_shelf:
            current_shelf = "Custom"

        button_command = """import maya.cmds as cmds
try:
    import {name}
    try:
        reload({name})
    except NameError:
        import importlib
        importlib.reload({name})
    {name}.launch()
except Exception as e:
    cmds.warning(u"启动时光机失败: " + str(e))
""".format(name=tool_module)

        icon_path = "menuIconFile.png"

        btn = cmds.shelfButton(
            parent=current_shelf,
            label=tool_display_name,
            annotation=tool_description,
            image=icon_path,
            command=button_command,
            sourceType="python",
            style="iconOnly"
        )
        print(u"工具架按钮已创建: " + btn)
    except Exception as e:
        cmds.warning(u"创建工具架按钮失败: " + str(e))
        return False

    cmds.confirmDialog(
        title=u"安装完成",
        message=u"时光机工具安装成功！\n\n脚本路径:\n{0}".format(main_script_path),
        button=[u"确定"],
        defaultButton=u"确定"
    )

    return True

def onMayaDroppedPythonFile(*args):
    main()

def main():
    print(u"开始安装时光机文件浏览器...")
    ok = install_timemachine()
    if ok:
        print(u"安装完成，可以点击工具架按钮打开。")
    else:
        print(u"安装失败，请检查 Script Editor 输出。")

if __name__ == "__main__":
    main()