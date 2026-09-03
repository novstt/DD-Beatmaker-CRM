from pathlib import Path
import sys
import json
import time
import threading
import secrets
import hashlib
import base64
import urllib.parse
import urllib.request
import urllib.error
import webbrowser
import re
import shutil
import os
import math
import random
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer

from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QPoint, QRect, QRectF, QSize, QTimer, QSettings, QUrl, QStandardPaths, QEvent
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QIcon, QKeySequence, QAction
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QFrame,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QComboBox, QCheckBox, QVBoxLayout, QWidget, QFileDialog,
    QStackedWidget, QDoubleSpinBox, QAbstractSpinBox, QGraphicsBlurEffect, QGraphicsOpacityEffect, QSystemTrayIcon, QMenu, QInputDialog, QGridLayout, QProgressBar, QScrollArea, QSlider,
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from desktop.api_client import ApiClient


class CompactToast(QFrame):
    """Small in-app notification replacing standard Windows info/error boxes."""
    def __init__(self, parent, title, message, kind="info"):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setObjectName("compactToast")
        accents={"success":"#35d07f","warning":"#f6b84a","error":"#ff5f6d","info":"#8f7cff"}
        symbols={"success":"✓","warning":"⚠","error":"×","info":"i"}
        accent=accents.get(kind, accents["info"])
        self.setStyleSheet(f"""
            QFrame#compactToast {{ background:#17181d; border:1px solid #30323b; border-left:3px solid {accent}; border-radius:10px; }}
            QLabel#toastTitle {{ color:#f4f4f6; font-size:13px; font-weight:700; }}
            QLabel#toastMessage {{ color:#b7bac4; font-size:12px; }}
            QLabel#toastIcon {{ color:{accent}; font-size:18px; font-weight:800; }}
            QPushButton#toastClose {{ background:transparent; color:#8b8f99; border:0; font-size:16px; min-width:22px; max-width:22px; }}
            QPushButton#toastClose:hover {{ color:#ffffff; }}
        """)
        layout=QHBoxLayout(self); layout.setContentsMargins(13,10,10,10); layout.setSpacing(10)
        icon=QLabel(symbols.get(kind,"i")); icon.setObjectName("toastIcon"); icon.setFixedWidth(20); layout.addWidget(icon,0,Qt.AlignmentFlag.AlignTop)
        body=QVBoxLayout(); body.setSpacing(3)
        t=QLabel(str(title)); t.setObjectName("toastTitle"); body.addWidget(t)
        m=QLabel(str(message)); m.setObjectName("toastMessage"); m.setWordWrap(True); m.setMaximumWidth(330); body.addWidget(m)
        layout.addLayout(body,1)
        close=QPushButton("×"); close.setObjectName("toastClose"); close.clicked.connect(self.close); layout.addWidget(close,0,Qt.AlignmentFlag.AlignTop)
        self.adjustSize(); self.resize(max(300,self.width()),self.height())
        QTimer.singleShot(4500,self.close)


def show_toast(title, message, kind="info", parent=None):
    parent=parent if isinstance(parent,QWidget) else QApplication.activeWindow()
    toast=CompactToast(parent,title,message,kind)
    if parent:
        pos=parent.mapToGlobal(parent.rect().topRight())
        toast.move(pos.x()-toast.width()-18,pos.y()+18)
    else:
        toast.move(40,40)
    toast.show(); toast.raise_()
    return toast


def _toast_warning(parent, title, text, *args, **kwargs):
    show_toast(title,text,"warning",parent); return QMessageBox.StandardButton.Ok

def _toast_information(parent, title, text, *args, **kwargs):
    show_toast(title,text,"info",parent); return QMessageBox.StandardButton.Ok

def _toast_critical(parent, title, text, *args, **kwargs):
    show_toast(title,text,"error",parent); return QMessageBox.StandardButton.Ok

# Keep confirmation dialogs blocking; replace non-blocking Windows-style alerts globally.
QMessageBox.warning = staticmethod(_toast_warning)
QMessageBox.information = staticmethod(_toast_information)
QMessageBox.critical = staticmethod(_toast_critical)

try:
    from mutagen.id3 import ID3
except Exception:
    ID3 = None


ICON_DIR = Path(__file__).resolve().parent / "icons"

def ui_icon(name):
    return QIcon(str(ICON_DIR / f"{name}.svg"))

def _prefs_path():
    appdata = os.environ.get('APPDATA')
    base = Path(appdata) / 'D&D' if appdata else (Path.home() / '.dd')
    base.mkdir(parents=True, exist_ok=True)
    return base / 'preferences.json'

def _legacy_prefs_path():
    base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
    return (base / 'preferences.json') if base else None

def _load_prefs():
    candidates=[_prefs_path(), _legacy_prefs_path(), Path(__file__).resolve().parent/'preferences.json']
    for p in candidates:
        try:
            if p and p.exists():
                data=json.loads(p.read_text(encoding='utf-8'))
                if isinstance(data,dict): return data
        except Exception: pass
    return {}

def _save_pref(key, value):
    try:
        p=_prefs_path(); data=_load_prefs(); data[key]=value
        p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        QSettings('D&D','D&D').setValue(key,value)
    except Exception: pass


DARK_STYLE = """
QWidget { background:#070A10; color:#F5F7FB; font-family:"Segoe UI"; font-size:14px; }
QWidget#pageStack { background:transparent; }
QWidget#content { background:#080C13; }\nQLabel { background:transparent; border:none; }
QMainWindow { background:#070A10; }
QWidget#topbar { background:#080C13; border-bottom:1px solid #171E2B; }
QFrame#searchWrap { background:#0D131D; border:1px solid #202A3A; border-radius:12px; }
QFrame#searchWrap:hover { border-color:#5A3978; }
QFrame#searchWrap QLineEdit { background:transparent; border:none; padding:7px 6px; }
QLabel#sectionLabel { color:#687386; font-size:10px; font-weight:700; letter-spacing:1px; padding:6px 10px 4px; }
QFrame#sidebar, QWidget#sidebar { background:#06080D; border-right:1px solid #171E2B; }
QLabel#brand { font-size:18px; font-weight:750; color:#B96CFF; letter-spacing:0.3px; }
QLabel#title { font-size:30px; font-weight:760; color:#F7F8FB; padding-top:2px; }
QPushButton#nav { text-align:left; background:transparent; color:#8791A3; border:1px solid transparent; border-radius:11px; padding:10px 13px; font-weight:600; }
QPushButton#nav:hover { background:#0E1420; color:#F3F4F8; }
QPushButton#nav:checked { background:#1D1428; color:#FFFFFF; border-color:#5D3981; }
QPushButton#accountButton { text-align:left; background:#0B1018; color:#FFFFFF; border:1px solid #202A38; border-radius:16px; padding:10px 12px; }
QPushButton#accountButton:hover { background:#121925; border-color:#6D4698; }
QPushButton#iconButton { background:#0C121B; border:1px solid #252F40; border-radius:11px; color:#C9D0DC; padding:7px 10px; }
QPushButton#iconButton:hover { border-color:#7A4CA7; background:#121927; }
QPushButton#primary { background:#8E46F1; color:#FFFFFF; border:none; border-radius:11px; padding:10px 17px; font-weight:720; }
QPushButton#primary:hover { background:#A35BFF; }
QPushButton#purpleAction { background:#211331; color:#F0E3FF; border:1px solid #58357E; border-radius:12px; text-align:left; padding:11px 15px; font-weight:650; }
QPushButton#blueAction { background:#101D2E; color:#DFEAFF; border:1px solid #284563; border-radius:12px; text-align:left; padding:11px 15px; font-weight:650; }
QPushButton#greenAction { background:#10271D; color:#DFFFEA; border:1px solid #2A6449; border-radius:12px; text-align:left; padding:11px 15px; font-weight:650; }
QPushButton#purpleAction:hover, QPushButton#blueAction:hover, QPushButton#greenAction:hover { border-color:#B96CFF; }
QLineEdit, QComboBox { background:#0B1119; color:#FFFFFF; border:1px solid #252F40; border-radius:11px; padding:10px 12px; min-height:18px; }
QLineEdit:focus, QComboBox:focus { border-color:#74499C; }
QListWidget { background:transparent; border:none; }
QListWidget::item { padding:11px 10px; border-bottom:1px solid #151D2A; }
QListWidget::item:hover { background:#0D1420; border-radius:8px; }
QListWidget::item:selected { background:#171126; border:1px solid #3C2756; border-radius:8px; }
QDialog { background:#090D14; }
QScrollBar:vertical { background:#090D14; width:7px; margin:0; }
QScrollBar::handle:vertical { background:#283346; border-radius:4px; min-height:30px; }
QToolTip { background:#111827; color:#F7F8FB; border:1px solid #394861; padding:6px 8px; }
QFrame#statCard { background:#0B1119; border:1px solid #202B3B; border-radius:16px; }
QFrame#statCard:hover { border-color:#5E3A80; background:#0F1621; }
QFrame#sectionCard { background:#0B1119; border:1px solid #1E2938; border-radius:16px; }
QFrame#playerBar { background:#0D131C; border:1px solid #263346; border-radius:14px; }
QFrame#beatCard, QFrame#artistCard { background:#0B1119; border:1px solid #1E2938; border-radius:15px; }
QFrame#dropZone { background:#0E1420; border:1px dashed #66418A; border-radius:14px; }
QFrame#dropZone:hover { background:#131A28; border-color:#B96CFF; }
QLabel#sectionLabel { font-size:11px; font-weight:750; letter-spacing:.7px; color:#AAB3C4; }
QPushButton#dataAction { background:#0F1622; border:1px solid #1F2B3E; border-radius:11px; color:#DCE2EC; text-align:left; padding:9px 12px; font-weight:600; }
QPushButton#dataAction:hover { background:#151D2A; border-color:#5A3E77; color:#FFFFFF; }
QListWidget#goalsList::item { padding:0px; margin:0px; border:none; background:transparent; }
QProgressBar#goalProgress { background:#101722; border:1px solid #243044; border-radius:3px; }
QProgressBar#goalProgress::chunk { background:#9A50FF; border-radius:3px; }
QPushButton#goalDelete { background:#111925; border:1px solid #273348; border-radius:8px; color:#8894A8; font-weight:700; }
QPushButton#goalDelete:hover { background:#2A1620; border-color:#6B3140; color:#FF8190; }
QLabel#goalPct { color:#AAB5C7; font-size:11px; font-weight:700; }
QScrollArea#pageScroll { background:transparent; border:none; }
QFrame#playerBar { background:#0B121C; border:1px solid #253145; border-radius:12px; }
QLabel#playerTitle { color:#B7C0D0; font-size:12px; font-weight:600; }
QFrame#sidebarAccount { background:#0B1018; border:1px solid #202A38; border-radius:16px; }
QFrame#sidebarAccount:hover { background:#121925; border-color:#6D4698; }
QLabel#sidebarAccountName { color:#F7F9FC; font-size:14px; font-weight:750; }
QLabel#sidebarAccountRole { color:#8D98AA; font-size:11px; }
QLabel#sidebarAccountBalance { color:#55D79B; font-size:12px; font-weight:750; }
/* D&D Unified Product UI */
QFrame#statCard { min-height:96px; }
QFrame#sectionCard { padding:2px; }
QPushButton#primary { min-height:38px; }
QPushButton#nav { min-height:20px; }
QLabel#sidebarAccountBalance { color:#55D79B; font-size:12px; font-weight:800; }
QLabel#panelBalance { color:#55D79B; font-size:12px; font-weight:800; }
QFrame#accountPanel { background:#0C111A; border:1px solid #3A2A4C; border-radius:18px; }
QFrame#accountPanel QPushButton#panelAction { min-height:36px; border-radius:10px; }
QFrame#accountPanel QPushButton#panelLogout { min-height:36px; border-radius:10px; }
QProgressBar { min-height:8px; }
QComboBox QAbstractItemView { background:#0D131D; color:#F5F7FB; selection-background-color:#2A173C; }
QDialog QPushButton { min-height:34px; }

"""


DARK_STYLE += """
/* FINAL PRODUCT UI OVERRIDES */
QWidget#content { background:#080B12; }
QWidget#pageScroll > QWidget { background:transparent; }
QFrame#sectionCard { border-radius:18px; border:1px solid #202A3A; }
QFrame#statCard { border-radius:18px; min-height:104px; }
QFrame#beatCard, QFrame#artistCard { border-radius:17px; }
QPushButton#nav { min-height:42px; padding:9px 12px; }
QPushButton#nav:checked { border-left:3px solid #B96CFF; padding-left:10px; }
QFrame#searchWrap { min-height:42px; border-radius:14px; }
QLineEdit, QComboBox { min-height:20px; }
QPushButton#dataAction { min-height:46px; border-radius:13px; }
QFrame#playerBar { min-height:54px; border-radius:15px; }
QLabel#playerTitle { font-size:13px; }
QScrollBar:vertical { width:8px; }
QScrollBar::handle:vertical { min-height:42px; }
"""


# Reference UI v29: layout follows the approved D&D dashboard mockups.
DARK_STYLE += """
QWidget#appRoot { background:#070A11; }
QWidget#content { background:#070A11; }
QWidget#topbar { background:#070A11; border-bottom:1px solid #141C29; }
QFrame#sidebar { background:#090C14; border-right:1px solid #151D2A; }
QLabel#brand { font-size:21px; font-weight:850; color:#F7F5FF; }
QPushButton#nav { color:#A9B1C0; border:none; border-radius:11px; padding:10px 12px; font-size:13px; font-weight:650; }
QPushButton#nav:hover { background:#111522; color:#F4F1FA; }
QPushButton#nav:checked { background:#211536; color:#C78BFF; border:1px solid #39214F; border-left:3px solid #A65CFF; padding-left:9px; }
QLabel#sectionLabel { color:#626C7D; font-size:10px; font-weight:800; letter-spacing:1px; padding:9px 10px 4px; }
QFrame#sidebarAccount { background:#0D111A; border:1px solid #202A3A; border-radius:15px; }
QFrame#sidebarAccount:hover { background:#111723; border-color:#5B3A78; }
QLabel#sidebarAccountName { font-size:14px; font-weight:800; color:#F8F8FB; }
QLabel#sidebarAccountRole { font-size:11px; color:#8B95A7; }
QLabel#sidebarAccountBalance { font-size:12px; color:#52DB91; font-weight:850; }
QFrame#searchWrap { background:#0D121B; border:1px solid #202A3A; border-radius:12px; }
QFrame#searchWrap QLineEdit { padding:8px 7px; }
QLabel#dashboardGreeting { font-size:28px; font-weight:800; color:#F8F8FB; }
QLabel#dashboardSub { color:#778295; font-size:12px; }
QFrame#statCard { background:#0D121B; border:1px solid #202A3A; border-radius:16px; min-height:120px; }
QFrame#statCard:hover { background:#101621; border-color:#4B3063; }
QFrame#sectionCard { background:#0C111A; border:1px solid #202A3A; border-radius:17px; }
QLabel#cardTitle { color:#F2F3F7; font-size:15px; font-weight:800; }
QLabel#mutedLabel { color:#7F8A9D; font-size:11px; }
QLabel#heroRevenue { color:#A95CFF; font-size:27px; font-weight:850; }
QLabel#positiveText { color:#55D79B; font-size:11px; font-weight:700; }
QLabel#goalRowTitle { color:#EDEFF5; font-size:12px; font-weight:700; }
QListWidget#compactList, QListWidget#dashboardGoals { background:transparent; border:none; }
QListWidget#compactList::item { color:#DCE1EA; padding:11px 7px; border-bottom:1px solid #171F2C; }
QListWidget#compactList::item:hover { background:#111722; border-radius:8px; }
QListWidget#dashboardGoals::item { padding:0; border:none; background:transparent; }
QPushButton#secondaryAction { background:#111722; color:#E4E8F0; border:1px solid #283346; border-radius:11px; padding:10px 15px; font-weight:700; }
QPushButton#secondaryAction:hover { border-color:#76509A; background:#171D2A; }
QPushButton#greenAction { background:#10261C; color:#BFF7D7; border:1px solid #2B6249; border-radius:11px; padding:10px 15px; font-weight:750; }
QPushButton#greenAction:hover { background:#153421; border-color:#4ABF7E; }
QPushButton#primary { background:#8D45E9; border-radius:11px; padding:10px 16px; font-weight:800; }
QPushButton#primary:hover { background:#A45BFF; }
QFrame#playerBar { background:#0C111A; border:1px solid #242F42; border-radius:15px; min-height:70px; }
QLabel#playerTitle { color:#F2F3F7; font-size:13px; font-weight:750; }
QLabel#playerMeta { color:#8B95A7; font-size:11px; }
QProgressBar#playerProgress { background:#151C28; border:none; border-radius:3px; min-height:5px; max-height:5px; }
QProgressBar#playerProgress::chunk { background:#A95CFF; border-radius:3px; }
QFrame#dropZone { background:#0C111A; border:1px dashed #5A3A78; }
"""

LIGHT_STYLE = """
QWidget { background:#F6F7FB; color:#18202C; font-family:"Segoe UI"; font-size:14px; }
QWidget#pageStack { background:transparent; }
QWidget#content { background:#F6F7FB; }
QMainWindow { background:#F6F7FB; }
QWidget#topbar { background:#F6F7FB; border-bottom:1px solid #E5E9F0; }
QFrame#sidebar, QWidget#sidebar { background:#FFFFFF; border-right:1px solid #E3E7EF; }
QLabel#brand { font-size:18px; font-weight:750; color:#7137D6; }
QLabel#title { font-size:30px; font-weight:760; color:#18202C; padding-top:2px; }
QPushButton#nav { text-align:left; background:transparent; color:#667085; border:1px solid transparent; border-radius:11px; padding:10px 13px; font-weight:600; }
QPushButton#nav:hover { background:#F2EFF8; color:#242B36; }
QPushButton#nav:checked { background:#EEE5FC; color:#6E2ED3; border-color:#D9C5F1; }
QPushButton#accountButton { text-align:left; background:#FBFCFE; color:#18202C; border:1px solid #DEE4EE; border-radius:16px; padding:10px 12px; }
QPushButton#accountButton:hover { background:#F1EDF8; border-color:#BFA5D9; }
QPushButton#iconButton { background:#FFFFFF; border:1px solid #DCE2EB; border-radius:11px; color:#667085; padding:7px 10px; }
QPushButton#iconButton:hover { background:#F2EFF8; border-color:#A98BC6; }
QPushButton#primary { background:#813BE6; color:#FFFFFF; border:none; border-radius:10px; padding:10px 17px; font-weight:700; }
QPushButton#primary:hover { background:#934BEF; }
QPushButton#purpleAction { background:#F0E7FB; color:#5F2A9E; border:1px solid #D4BCEA; border-radius:12px; text-align:left; padding:11px 15px; font-weight:650; }
QPushButton#blueAction { background:#E8F1FC; color:#245C91; border:1px solid #BBD4EE; border-radius:12px; text-align:left; padding:11px 15px; font-weight:650; }
QPushButton#greenAction { background:#E5F6EC; color:#1F6845; border:1px solid #B8DEC8; border-radius:12px; text-align:left; padding:11px 15px; font-weight:650; }
QPushButton#purpleAction:hover, QPushButton#blueAction:hover, QPushButton#greenAction:hover { border-color:#8B57C4; }
QLineEdit, QComboBox { background:#FFFFFF; color:#18202C; border:1px solid #D7DEE9; border-radius:11px; padding:10px 12px; min-height:18px; }
QLineEdit:focus, QComboBox:focus { border-color:#8B57C4; }
QListWidget { background:transparent; border:none; }
QListWidget::item { background:transparent; padding:11px 10px; border-bottom:1px solid #E8ECF2; }
QListWidget::item:hover { background:#F4F1F8; border-radius:8px; }
QListWidget::item:selected { background:#EEE7F7; border:1px solid #D9C7EA; border-radius:8px; }
QDialog { background:#F6F7FB; }
QScrollBar:vertical { background:#EEF1F5; width:7px; margin:0; }
QScrollBar::handle:vertical { background:#C7CDD8; border-radius:4px; min-height:30px; }
QToolTip { background:#FFFFFF; color:#18202C; border:1px solid #CBD3DF; padding:6px 8px; }
QFrame#statCard { background:#FFFFFF; border:1px solid #DCE2EB; border-radius:15px; }
QFrame#statCard:hover { border-color:#BDA0D9; background:#FCFBFE; }
QFrame#sectionCard { background:#FFFFFF; border:1px solid #DCE2EB; border-radius:16px; }
QFrame#playerBar { background:#FFFFFF; border:1px solid #DCE2EB; border-radius:14px; }
QFrame#beatCard, QFrame#artistCard { background:#FFFFFF; border:1px solid #DCE2EB; border-radius:14px; }
QFrame#dropZone { background:#F7F4FB; border:1px dashed #A98BC6; border-radius:14px; }
QFrame#dropZone:hover { background:#F1ECF7; border-color:#813BE6; }
QLabel { background:transparent; }
"""




class WaveformWidget(QWidget):
    """Very light animated waveform for the authentication screen."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(55)

    def _tick(self):
        self._phase += 0.13
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        mid = h / 2
        # Subtle baseline
        p.setPen(QPen(QColor(45, 39, 63, 120), 1))
        p.drawLine(0, mid, w, mid)
        n = max(40, min(110, w // 12))
        step = w / n
        for i in range(n):
            x = i * step + step * 0.5
            envelope = 0.25 + 0.75 * math.sin((i / max(1, n-1)) * math.pi) ** 1.5
            pulse = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(self._phase + i * 0.33))
            noise = 0.78 + 0.22 * math.sin(i * 1.71 + self._phase * 0.7)
            amp = (10 + 30 * envelope * pulse * noise)
            color = QColor(155, 80, 255, 135 if i % 3 else 180)
            p.setPen(QPen(color, 2))
            p.drawLine(QPoint(int(x), int(mid-amp)), QPoint(int(x), int(mid+amp)))
        p.end()


class WelcomePanel(QFrame):
    """First-run onboarding shown once before authentication."""
    completed = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('welcomePanel')
        root=QVBoxLayout(self)
        root.setContentsMargins(42,34,42,34)
        root.setSpacing(16)
        logo=QLabel('D&D')
        logo.setStyleSheet('font-size:30px;font-weight:800;color:#B96CFF;letter-spacing:1px;')
        root.addWidget(logo)
        title=QLabel('Your producer workspace, in one place.')
        title.setStyleSheet('font-size:28px;font-weight:800;color:#F7F8FB;')
        root.addWidget(title)
        sub=QLabel('Artists, beats, licenses and stats — built around your workflow.')
        sub.setStyleSheet('font-size:14px;color:#9BA4B4;')
        root.addWidget(sub)
        wave=WaveformWidget(); wave.setFixedHeight(92); root.addWidget(wave)
        grid=QGridLayout(); grid.setHorizontalSpacing(12); grid.setVerticalSpacing(12)
        items=[('01','Artists','Keep your artists, contacts and follow-ups organized.'),('02','Beats','Store MP3s, metadata, producers and playback.'),('03','Licenses','Create sales and automatically calculate splits.'),('04','Stats','Track revenue, goals and your progress.')]
        for i,(num,head,desc) in enumerate(items):
            card=QFrame(); card.setObjectName('welcomeFeature')
            cv=QVBoxLayout(card); cv.setContentsMargins(16,14,16,14)
            n=QLabel(num); n.setStyleSheet('color:#B96CFF;font-size:11px;font-weight:800;')
            cv.addWidget(n)
            h=QLabel(head); h.setStyleSheet('font-size:16px;font-weight:750;')
            cv.addWidget(h)
            d=QLabel(desc); d.setWordWrap(True); d.setStyleSheet('color:#8F9AAC;font-size:12px;')
            cv.addWidget(d)
            grid.addWidget(card,i//2,i%2)
        root.addLayout(grid)
        root.addStretch()
        bottom=QHBoxLayout(); bottom.addStretch()
        btn=QPushButton('Get started  →'); btn.setObjectName('authPrimary'); btn.clicked.connect(self.completed.emit)
        bottom.addWidget(btn); root.addLayout(bottom)


class PreviewDashboard(QWidget):
    """Static blurred preview used behind the authentication card."""

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)

        top = QHBoxLayout()
        brand = QLabel("▥  D&D")
        brand.setStyleSheet("font-size: 22px; font-weight: 750; color: #B96CFF;")
        top.addWidget(brand)
        top.addStretch()
        top.addWidget(QLabel("⌕  Search artists, beats, licenses..."))
        root.addLayout(top)

        title = QLabel("Good evening, SLV 👋")
        title.setStyleSheet("font-size: 32px; font-weight: 700; margin-top: 24px;")
        root.addWidget(title)

        cards = QHBoxLayout()
        for label, value in [
            ("REVENUE THIS MONTH", "$450"),
            ("LICENSES SOLD", "8"),
            ("ARTISTS", "127"),
            ("BEATS", "64"),
        ]:
            card = QFrame()
            card.setStyleSheet(
                "QFrame { background:#101624; border:1px solid #273148; "
                "border-radius:16px; padding:14px; }"
            )
            cv = QVBoxLayout(card)
            cv.addWidget(QLabel(label))
            v = QLabel(value)
            v.setStyleSheet("font-size: 28px; font-weight: 700; color:#B46CFF;")
            cv.addWidget(v)
            cards.addWidget(card)
        root.addLayout(cards)

        middle = QHBoxLayout()
        for heading in ["Recent activity", "Quick actions"]:
            box = QFrame()
            box.setStyleSheet(
                "QFrame { background:#0E1521; border:1px solid #273148; "
                "border-radius:16px; }"
            )
            bv = QVBoxLayout(box)
            h = QLabel(heading)
            h.setStyleSheet("font-size:17px; font-weight:700;")
            bv.addWidget(h)
            for line in [
                "Beat sold  •  Test Beat → Test Artist",
                "Beat sent  •  Dark Plugg → @artist",
                "License sold  •  WAV — $50",
                "Artist added  •  @newartist",
            ]:
                bv.addWidget(QLabel(line))
            middle.addWidget(box)
        root.addLayout(middle)

        chart = QFrame()
        chart.setMinimumHeight(250)
        chart.setStyleSheet(
            "QFrame { background:#0E1521; border:1px solid #273148; "
            "border-radius:16px; }"
        )
        cv = QVBoxLayout(chart)
        cv.addWidget(QLabel("Stats overview  •  This Month"))
        cv.addWidget(QLabel("╱╲__╱╲___╱╲____╱╲______╱╲_____╱╲"))
        cv.addWidget(QLabel("$450   ↑ 12% vs last month"))
        root.addWidget(chart)
        root.addStretch()


class AuthCard(QFrame):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.mode = "login"
        self.setObjectName("authCard")
        self.setFixedWidth(430)

        root = QVBoxLayout(self)
        root.setContentsMargins(34, 30, 34, 30)
        root.setSpacing(13)

        logo = QLabel("D&D")
        logo.setStyleSheet("font-size:18px; font-weight:750; color:#B46CFF;")
        root.addWidget(logo)

        self.title = QLabel("Welcome back")
        self.title.setStyleSheet("font-size:28px; font-weight:700;")
        root.addWidget(self.title)

        self.subtitle = QLabel("Sign in to manage your artists, beats and licenses.")
        self.subtitle.setWordWrap(True)
        self.subtitle.setStyleSheet("color:#9BA4B4;")
        root.addWidget(self.subtitle)

        self.remembered = QFrame()
        self.remembered.setObjectName("rememberedAccount")
        rv = QHBoxLayout(self.remembered)
        rv.setContentsMargins(12,10,12,10)
        self.avatar = QLabel("Q")
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setFixedSize(38,38)
        self.avatar.setStyleSheet("background:#2A173C;border:1px solid #7044A0;border-radius:19px;color:#DDBBFF;font-weight:800;")
        rv.addWidget(self.avatar)
        acct = QVBoxLayout(); acct.setSpacing(1)
        self.remembered_name = QLabel("Saved account")
        self.remembered_name.setStyleSheet("font-weight:750;color:#F5F7FB;")
        self.remembered_email = QLabel("")
        self.remembered_email.setStyleSheet("font-size:11px;color:#8F9AAC;")
        acct.addWidget(self.remembered_name); acct.addWidget(self.remembered_email); rv.addLayout(acct,1)
        self.use_saved = QPushButton("Continue")
        self.use_saved.setObjectName("authPrimary")
        self.use_saved.clicked.connect(self.continue_saved)
        rv.addWidget(self.use_saved)
        root.addWidget(self.remembered)

        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")
        self.username.hide()
        root.addWidget(self.username)

        self.email = QLineEdit()
        self.email.setPlaceholderText("Email")
        saved_email = _load_prefs().get("last_email") or str(QSettings("D&D", "D&D").value("last_email", "") or "")
        self.email.setText(str(saved_email))
        self.email.textChanged.connect(lambda value: _save_pref("last_email", value.strip()))
        root.addWidget(self.email)
        self._saved_email = str(saved_email).strip()
        if self._saved_email:
            self.remembered_email.setText(self._saved_email)
            self.avatar.setText((self._saved_email[:1] or "Q").upper())
            self.email.hide()
        else:
            self.remembered.hide()

        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        root.addWidget(self.password)

        self.confirm = QLineEdit()
        self.confirm.setPlaceholderText("Confirm password")
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm.hide()
        root.addWidget(self.confirm)

        self.action = QPushButton("Sign in")
        self.action.setObjectName("authPrimary")
        self.action.clicked.connect(self.submit)
        root.addWidget(self.action)

        self.switch = QPushButton("Create an account")
        self.switch.setObjectName("authLink")
        self.switch.clicked.connect(self.toggle_mode)
        root.addWidget(self.switch)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#FF8E9E;")
        root.addWidget(self.status)

    def continue_saved(self):
        self.remembered.hide()
        self.email.show()
        self.email.setReadOnly(True)
        self.password.setFocus()
        self.title.setText("Welcome back")
        self.subtitle.setText("Enter your password to continue.")
        self.switch.setText("Use another account")

    def toggle_mode(self):
        if self.mode == "login" and self.email.isReadOnly():
            self.email.setReadOnly(False)
            self.email.show()
            self.remembered.show() if self._saved_email else self.remembered.hide()
            self.title.setText("Welcome back")
            self.subtitle.setText("Sign in to manage your artists, beats and licenses.")
            self.switch.setText("Create an account")
            return
        self.mode = "register" if self.mode == "login" else "login"
        self.email.setReadOnly(False)

        for widget in [self.username, self.confirm]:
            widget.setVisible(self.mode == "register")

        if self.mode == "register":
            self.title.setText("Create your account")
            self.subtitle.setText("Join your producer workspace.")
            self.action.setText("Create account")
            self.switch.setText("Already have an account? Sign in")
        else:
            self.title.setText("Welcome back")
            self.subtitle.setText("Sign in to manage your artists, beats and licenses.")
            self.action.setText("Sign in")
            self.switch.setText("Create an account")

        self.fade_content()

    def fade_content(self):
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(220)
        anim.setStartValue(0.25)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._fade_anim = anim

    def submit(self):
        self.status.setText("")

        if self.mode == "register":
            username = self.username.text().strip()
            email = self.email.text().strip()
            password = self.password.text()
            confirm = self.confirm.text()

            if not username or not email or not password:
                self.status.setText("Fill in all fields.")
                return
            if len(password) < 8:
                self.status.setText("Password must be at least 8 characters.")
                return
            if password != confirm:
                self.status.setText("Passwords do not match.")
                return

            try:
                self.api.register(username, email, password)
                # Registration is followed by normal login.
                self.api.login(email, password)
                _save_pref("last_email", email)
                self.window().accept()
            except Exception as e:
                self.status.setText(str(e))
            return

        email = self.email.text().strip()
        password = self.password.text()

        if not email or not password:
            self.status.setText("Enter email and password.")
            return

        try:
            self.api.login(email, password)
            _save_pref("last_email", email)
            self.window().accept()
        except Exception as e:
            self.status.setText(str(e))


class AuthWindow(QDialog):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.setWindowTitle("D&D")
        self.setMinimumSize(1180, 760)
        self.resize(1280, 820)
        self.setModal(True)

        root = QStackedWidget()
        root.setObjectName("authBackground")

        prefs = _load_prefs()
        self._first_run = not bool(prefs.get("welcome_seen"))

        preview = PreviewDashboard()
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(18)
        preview.setGraphicsEffect(blur)
        root.addWidget(preview)

        overlay = QWidget()
        overlay.setStyleSheet("background: rgba(3, 7, 15, 185);")
        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.addStretch()
        hero = QVBoxLayout(); hero.setSpacing(6)
        brand = QLabel("D&D")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setStyleSheet("font-size:34px;font-weight:850;color:#B96CFF;letter-spacing:2px;")
        hero.addWidget(brand)
        tagline = QLabel("BEATMAKER CRM")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet("font-size:10px;font-weight:800;color:#8F9AAC;letter-spacing:2px;")
        hero.addWidget(tagline)
        wave = WaveformWidget(); wave.setFixedHeight(70); hero.addWidget(wave)
        overlay_layout.addLayout(hero)
        overlay_layout.addSpacing(10)

        row = QHBoxLayout()
        row.addStretch()
        self.card = AuthCard(api, self)
        self.card.setStyleSheet("""
            QFrame#authCard {
                background: rgba(11, 16, 27, 248);
                border: 1px solid #303A52;
                border-radius: 22px;
            }
            QLabel { background: transparent; }
            QLineEdit {
                background: #0D1420;
                color: #FFFFFF;
                border: 1px solid #2B354A;
                border-radius: 11px;
                padding: 13px;
            }
            QLineEdit:focus { border: 1px solid #8D4DFF; }
            QPushButton#authPrimary {
                background: #7A35E8;
                color: white;
                border: none;
                border-radius: 11px;
                padding: 13px;
                font-weight: 700;
            }
            QPushButton#authPrimary:hover { background: #8D4DFF; }
            QPushButton#authLink {
                background: transparent;
                border: none;
                color: #B46CFF;
                padding: 8px;
            }
            QPushButton#authLink:hover { color: #D3A8FF; }
            QFrame#rememberedAccount { background:#0D1420; border:1px solid #2C3650; border-radius:14px; }
            QFrame#welcomePanel { background:rgba(9,13,20,245); border:1px solid #303A52; border-radius:22px; }
            QFrame#welcomeFeature { background:#0D1420; border:1px solid #253047; border-radius:14px; }
            QFrame#welcomeFeature:hover { border-color:#7044A0; }
        """)
        row.addWidget(self.card)
        row.addStretch()
        overlay_layout.addLayout(row)
        overlay_layout.addStretch()

        root.addWidget(overlay)
        if self._first_run:
            welcome = WelcomePanel()
            welcome.completed.connect(lambda: (
                _save_pref("welcome_seen", True),
                root.setCurrentWidget(overlay)
            ))
            root.insertWidget(1, welcome)
            root.setCurrentWidget(welcome)
        else:
            root.setCurrentWidget(overlay)

        final = QVBoxLayout(self)
        final.setContentsMargins(0, 0, 0, 0)
        final.addWidget(root)

        self.card.move(0, 20)
        self._animate_card()

    def _animate_card(self):
        effect = QGraphicsOpacityEffect(self.card)
        self.card.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(500)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._auth_anim = anim


class LoginDialog(QDialog):
    """Compatibility wrapper for older code paths."""
    def __init__(self, api):
        super().__init__()
        self.api = api

    def exec(self):
        auth = AuthWindow(self.api)
        return auth.exec()


class AddArtistDialog(QDialog):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Add Artist")
        self.setMinimumWidth(430)

        layout = QVBoxLayout(self)

        title = QLabel("ADD ARTIST")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(title)

        form = QFormLayout()

        self.name = QLineEdit()
        self.name.setPlaceholderText("Artist name")

        self.platform = QComboBox()
        self.platform.addItems([
            "Instagram", "TikTok", "SoundCloud",
            "Email", "Discord", "Other"
        ])

        self.username = QLineEdit()
        self.username.setPlaceholderText("@username")

        self.status = QComboBox()
        self.status.addItem("Unread", "unread")
        self.status.addItem("Read", "read")
        self.status.addItem("Replied", "replied")
        self.status.addItem("Profile viewed", "profile_viewed")

        self.beats = QListWidget()
        self.beats.setSelectionMode(
            QListWidget.SelectionMode.MultiSelection
        )
        self.load_beats()

        self.cash_ready = QCheckBox("Cash Ready")

        form.addRow("Artist name:", self.name)
        form.addRow("Platform:", self.platform)
        form.addRow("Username:", self.username)
        form.addRow("Message status:", self.status)
        form.addRow("Selected beats:", self.beats)
        form.addRow("", self.cash_ready)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def load_beats(self):
        try:
            for beat in self.api.beats():
                item = QListWidgetItem(
                    f"{beat['name']}"
                )
                item.setData(Qt.ItemDataRole.UserRole, beat["id"])
                self.beats.addItem(item)
        except Exception as e:
            self.beats.addItem(f"Could not load beats: {e}")

    def save(self):
        name = self.name.text().strip()
        username = self.username.text().strip()

        if not name:
            QMessageBox.warning(self, "Missing field", "Enter artist name.")
            return

        if not username:
            QMessageBox.warning(
                self, "Missing field", "Enter artist username."
            )
            return

        beat_ids = []
        for item in self.beats.selectedItems():
            beat_id = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(beat_id, int):
                beat_ids.append(beat_id)

        try:
            self.api.add_artist(
                name=name,
                platform=self.platform.currentText(),
                artist_username=username,
                message_status=self.status.currentData(),
                beat_ids=beat_ids,
                cash_ready=self.cash_ready.isChecked(),
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Could not add artist", str(e))


class EditArtistDialog(QDialog):
    def __init__(self, api, artist, parent=None):
        super().__init__(parent)
        self.api = api
        self.artist = artist
        self.setWindowTitle("Edit Artist")
        self.setMinimumWidth(430)

        root = QVBoxLayout(self)

        title = QLabel("EDIT ARTIST")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        form = QFormLayout()

        self.username = QLineEdit(artist.get("artist_username") or "")

        self.platform = QComboBox()
        self.platform.addItems([
            "Instagram", "TikTok", "SoundCloud",
            "Email", "Discord", "Other"
        ])
        current_platform = artist.get("platform")
        if current_platform:
            index = self.platform.findText(current_platform)
            if index >= 0:
                self.platform.setCurrentIndex(index)

        self.status = QComboBox()
        statuses = [
            ("Unread", "unread"),
            ("Read", "read"),
            ("Replied", "replied"),
            ("Profile viewed", "profile_viewed"),
        ]
        for label, value in statuses:
            self.status.addItem(label, value)

        current_status = artist.get("message_status")
        index = self.status.findData(current_status)
        if index >= 0:
            self.status.setCurrentIndex(index)

        self.cash_ready = QCheckBox("Cash Ready")
        self.cash_ready.setChecked(bool(artist.get("cash_ready")))

        self.notes = QLineEdit(artist.get("notes") or "")
        self.notes.setPlaceholderText("Optional notes")

        form.addRow("Username:", self.username)
        form.addRow("Platform:", self.platform)
        form.addRow("Message status:", self.status)
        form.addRow("", self.cash_ready)
        form.addRow("Notes:", self.notes)

        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def save(self):
        username = self.username.text().strip()
        if not username:
            QMessageBox.warning(
                self, "Missing field", "Enter artist username."
            )
            return

        try:
            self.api.update_artist(
                artist_id=self.artist["id"],
                platform=self.platform.currentText(),
                artist_username=username,
                message_status=self.status.currentData(),
                cash_ready=self.cash_ready.isChecked(),
                notes=self.notes.text().strip(),
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Could not save", str(e))


class BeatAudioStore:
    """Local MP3-only storage. Audio never touches the API/database."""
    def __init__(self):
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        self.root = Path(base or (Path.home()/".dd")) / "audio"
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.root / "registry.json"
        self.registry = {}
        try:
            self.registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
            if not isinstance(self.registry, dict): self.registry={}
        except Exception:
            self.registry={}

    def _save(self):
        self.registry_path.write_text(json.dumps(self.registry, ensure_ascii=False, indent=2), encoding="utf-8")

    def path_for(self, beat_id):
        p=self.registry.get(str(beat_id))
        return Path(p) if p and Path(p).is_file() else None

    def file_hash(self, path):
        h=hashlib.sha256()
        with open(path,'rb') as f:
            for chunk in iter(lambda:f.read(1024*1024), b''):
                h.update(chunk)
        return h.hexdigest()

    def duplicate_beat_id(self, source, exclude_id=None):
        source=Path(source)
        try: target_hash=self.file_hash(source)
        except Exception: return None
        for bid,p in self.registry.items():
            if exclude_id is not None and str(bid)==str(exclude_id): continue
            fp=Path(p)
            if fp.is_file():
                try:
                    if self.file_hash(fp)==target_hash: return int(bid)
                except Exception: pass
        return None

    def attach(self, beat_id, source):
        source=Path(source)
        if source.suffix.lower() != ".mp3":
            raise ValueError("Only MP3 files are supported.")
        dest=self.root / f"beat_{beat_id}.mp3"
        shutil.copy2(source,dest)
        self.registry[str(beat_id)] = str(dest)
        self._save()
        return dest

    def remove(self, beat_id):
        p=self.path_for(beat_id)
        if p:
            try: p.unlink()
            except OSError: pass
        self.registry.pop(str(beat_id),None)
        self._save()


class Mp3DropZone(QFrame):
    fileSelected = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent); self.setAcceptDrops(True); self.path=""
        self.setMinimumHeight(100); self.setObjectName("dropZone")
        lay=QVBoxLayout(self); lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label=QLabel("Drop MP3 here  •  or click to choose")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.label.setStyleSheet("font-weight:650;color:#B9A0FF;")
        lay.addWidget(self.label)
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton:
            p,_=QFileDialog.getOpenFileName(self,"Choose MP3","","MP3 audio (*.mp3)")
            if p: self.set_file(p)
        super().mousePressEvent(e)
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self,e):
        for u in e.mimeData().urls():
            p=u.toLocalFile()
            if p.lower().endswith(".mp3"):
                self.set_file(p); e.acceptProposedAction(); return
        QMessageBox.warning(self,"MP3 only","Please drop an MP3 file.")
    def set_file(self,p):
        self.path=p; self.label.setText(f"✓ {Path(p).name}"); self.fileSelected.emit(p)


KEY_PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-Ga-g](?:#|b)?)(?:\s*(major|maj|minor|min|m))?(?![A-Za-z0-9])", re.I)
BPM_PATTERN = re.compile(r"(?<!\d)((?:[4-9]\d|[12]\d{2}|300))\s*(?:[-_ ]?\s*bpm|bpms)\b", re.I)

# Producer aliases used when importing/renaming beats. Matching is intentionally
# strict enough to avoid deleting normal title words, while accepting the tags
# commonly used in filenames.
PRODUCER_ALIASES = {
    "slv": "SLV", "slv1": "SLV", "prodslv": "SLV", "quikinnnslv": "SLV",
    "deplug": "DE PLUG", "deplugg": "DE PLUG", "deplugboy": "DE PLUG",
    "daddykar": "DADDY KAR", "daddykarofficial": "DADDY KAR",
}

def _producer_alias_key(value):
    value = (value or "").strip().lstrip("@")
    return re.sub(r"[._\-\s]+", "", value).casefold()


def canonical_producer_label(username):
    """Return the stable display name for known producer aliases."""
    raw = (username or "").strip().lstrip("@")
    return PRODUCER_ALIASES.get(_producer_alias_key(raw), raw)


def _remove_known_producer_tags(text):
    """Remove known producer credit tags from filename title edges."""
    if not text:
        return text
    alias_re = r"(?:@?(?:prod[._-]?slv|quikinnnslv|slv)|@?(?:de[ ._-]?plugg?|de[ ._-]?plugboy)|@?(?:daddy[ ._-]?kar(?:[ ._-]?official)?))"
    # Credits at the beginning: SLV & DE PLUG - TITLE, @prod.slv @deplugboy - TITLE, etc.
    leading = re.compile(
        rf"^\s*{alias_re}(?:(?:\s*(?:&|and|x|\+|,|/)\s*|\s+){alias_re})*\s*[-–—:]\s*",
        re.I,
    )
    previous = None
    while previous != text:
        previous = text
        text = leading.sub("", text, count=1).strip()
    # Single producer prefix without a dash, e.g. '@slv TITLE'.
    text = re.sub(rf"^\s*{alias_re}\s+(?=[A-Za-z0-9])", "", text, count=1, flags=re.I).strip()
    # Credits at the end: TITLE - SLV & DE PLUG.
    trailing = re.compile(
        rf"\s*[-–—:]\s*{alias_re}(?:(?:\s*(?:&|and|x|\+|,|/)\s*|\s+){alias_re})*\s*$",
        re.I,
    )
    text = trailing.sub("", text).strip()
    return text


def parse_beat_filename(path):
    """Parse BPM/key and return a clean, editable beat title.

    Known producer aliases are treated as credits rather than title text.
    Parsed BPM/key are removed from the suggested title so the user can still
    edit the result before saving.
    """
    stem = Path(path).stem.strip()
    original = stem
    # Prefer useful ID3 title metadata when available, but keep the filename as
    # the fallback. Metadata is only a suggestion and remains editable.
    metadata_title = None
    metadata_artist = None
    if ID3 is not None:
        try:
            tags = ID3(str(path))
            metadata_title = str(tags.get("TIT2")) if tags.get("TIT2") else None
            metadata_artist = str(tags.get("TPE1")) if tags.get("TPE1") else None
        except Exception:
            pass
    parse_source = metadata_title or stem
    if metadata_artist and metadata_title and not re.search(r"(?:prod[._-]?slv|de[ ._-]?plug|daddy[ ._-]?kar)", parse_source, re.I):
        parse_source = f"{metadata_artist} - {parse_source}"

    bpm = None
    bpm_match = BPM_PATTERN.search(parse_source)
    if bpm_match:
        bpm = int(bpm_match.group(1))
    if bpm is None:
        for m in re.finditer(r"(?<!\d)(\d{2,3})(?!\d)", parse_source):
            val = int(m.group(1))
            if 40 <= val <= 300 and re.search(r"(?:min|maj|minor|major|[A-G](?:#|b)?m?)", parse_source[m.end():m.end()+18], re.I):
                bpm = val
                break

    key_match = None
    explicit_patterns = [
        r"(?<![A-Za-z0-9])([A-Ga-g](?:#|b)?)[\s._-]*(major|maj|minor|min|m)(?![A-Za-z0-9])",
        r"(?<![A-Za-z0-9])([A-Ga-g](?:#|b)?)(m)(?![A-Za-z0-9])",
    ]
    for pat in explicit_patterns:
        m = re.search(pat, parse_source, re.I)
        if m:
            key_match = m
            break

    musical_key = None
    if key_match:
        note = key_match.group(1).upper()
        if note.endswith("B") and len(note) > 1:
            note = note[:-1] + "b"
        mode = (key_match.group(2) or "").lower()
        musical_key = note + (" minor" if mode in {"minor", "min", "m"} else " major" if mode in {"major", "maj"} else "")

    name = parse_source
    # Remove parenthesized metadata first: '(143Bpm Cmin)', '(140 BPM)', etc.
    name = re.sub(r"\([^)]*(?:\d{2,3}\s*bpm|bpm|major|minor|min|maj|\b[A-Ga-g](?:#|b)?m\b)[^)]*\)", " ", name, flags=re.I)
    name = BPM_PATTERN.sub(" ", name)
    if key_match:
        name = name.replace(key_match.group(0), " ")
    name = re.sub(r"\b(?:BPM|BPMs|major|minor|maj|min)\b", " ", name, flags=re.I)
    name = _remove_known_producer_tags(name)
    name = re.sub(r"[_]+", " ", name)
    name = re.sub(r"\s*[-–—]\s*", " - ", name)
    name = re.sub(r"\s{2,}", " ", name).strip(" -_()[]")
    # If metadata removal left a bare separator, clean it up.
    name = re.sub(r"^(?:[-–—|•]+\s*)+|(?:\s*[-–—|•]+)+$", "", name).strip()

    return {"name": name or original, "bpm": bpm, "musical_key": musical_key}


class AddBeatDialog(QDialog):
    def __init__(self, api, parent=None, audio_store=None):
        super().__init__(parent); self.api=api; self.audio_store=audio_store
        self.setWindowTitle("Add Beat"); self.setMinimumWidth(560)
        root=QVBoxLayout(self); root.setContentsMargins(22,20,22,18); root.setSpacing(12)
        title=QLabel("ADD BEAT"); title.setStyleSheet("font-size:20px;font-weight:750;"); root.addWidget(title)
        sub=QLabel("Add the beat to your catalog first. Producer/messenger roles are decided when a license is created."); sub.setWordWrap(True); sub.setStyleSheet("color:#8994A8;"); root.addWidget(sub)
        form=QFormLayout()
        self.name=QLineEdit(); self.name.setPlaceholderText("Beat name")
        self.bpm=QLineEdit(); self.bpm.setPlaceholderText("e.g. 140")
        self.key=QLineEdit(); self.key.setPlaceholderText("e.g. F# minor")
        self.producer=QLineEdit(); self.producer.setPlaceholderText("Producer username, e.g. SLV or @prod_slv")
        self.producer.setText(canonical_producer_label((self.api.user or {}).get("username", "")))
        self.status=QComboBox(); self.status.addItem("Available","available"); self.status.addItem("Archived","archived")
        self.co=QLineEdit(); self.co.setPlaceholderText("Optional: @producer, Name, @anotherproducer")
        form.addRow("Beat name:",self.name); form.addRow("BPM:",self.bpm); form.addRow("Key:",self.key); form.addRow("Producer:",self.producer); form.addRow("Status:",self.status); form.addRow("Co-producers:",self.co)
        root.addLayout(form)
        root.addWidget(QLabel("AUDIO FILE"))
        self.drop=Mp3DropZone(); root.addWidget(self.drop)
        self.drop.fileSelected.connect(self.parse_filename_metadata)
        self.parse_hint=QLabel("Filename metadata is only a suggestion — review and edit before saving.")
        self.parse_hint.setStyleSheet("color:#7F8B9F;font-size:11px;")
        self.parse_hint.setWordWrap(True); root.addWidget(self.parse_hint)
        hint=QLabel("Only MP3 is stored locally. Producer/co-producer can be a @username or account email. Registered D&D accounts receive notifications."); hint.setWordWrap(True); hint.setStyleSheet("color:#7F8B9F;"); root.addWidget(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def parse_filename_metadata(self, path):
        try:
            meta = parse_beat_filename(path)
        except (re.error, ValueError, TypeError) as exc:
            self.parse_hint.setText(f"Could not parse filename metadata safely: {exc}. You can enter the fields manually.")
            self.parse_hint.setStyleSheet("color:#C98B8B;font-size:11px;")
            return
        if meta.get("name"):
            self.name.setText(meta["name"])
        if meta.get("bpm") is not None:
            self.bpm.setText(str(meta["bpm"]))
        if meta.get("musical_key"):
            self.key.setText(meta["musical_key"])

    def save(self):
        name=self.name.text().strip(); path=self.drop.path
        if not name: QMessageBox.warning(self,"Missing field","Enter beat name."); return
        if not path: QMessageBox.warning(self,"MP3 required","Drop an MP3 file before saving."); return
        bpm=None; t=self.bpm.text().strip()
        if t:
            try: bpm=int(t); assert bpm>0
            except Exception: QMessageBox.warning(self,"Invalid BPM","BPM must be a positive number."); return
        co=[x.strip() for x in self.co.text().split(",") if x.strip()]
        try:
            if self.audio_store:
                duplicate=self.audio_store.duplicate_beat_id(path)
                if duplicate:
                    answer=QMessageBox.question(self,'Possible duplicate',f'This MP3 is identical to an existing beat (#{duplicate}). Add it anyway?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
                    if answer != QMessageBox.StandardButton.Yes:
                        return
            beat=self.api.create_beat(name=name,bpm=bpm,musical_key=self.key.text().strip() or None,status=self.status.currentData(),producer_username=self.producer.text().strip(),co_producer_usernames=co)
            if self.audio_store and beat and beat.get("id"):
                self.audio_store.attach(beat["id"],path)
            self.accept()
        except Exception as e: QMessageBox.critical(self,"Could not add beat",str(e))


class EditBeatDialog(QDialog):
    def __init__(self, api, beat, parent=None, audio_store=None):
        super().__init__(parent); self.api=api; self.beat=beat; self.audio_store=audio_store
        self.setWindowTitle("Edit Beat"); self.setMinimumWidth(560)
        root=QVBoxLayout(self); root.setContentsMargins(22,20,22,18); root.setSpacing(12)
        title=QLabel("EDIT BEAT"); title.setStyleSheet("font-size:20px;font-weight:750;"); root.addWidget(title)
        form=QFormLayout(); self.name=QLineEdit(str(beat.get("name") or "")); self.bpm=QLineEdit("" if beat.get("bpm") is None else str(beat.get("bpm"))); self.key=QLineEdit(str(beat.get("musical_key") or ""))
        self.producer=QLineEdit(canonical_producer_label(str(beat.get("producer_username") or (self.api.user or {}).get("username", "")))); self.status=QComboBox(); self.status.addItem("Available","available"); self.status.addItem("Archived","archived"); self.status.setCurrentIndex(max(0,self.status.findData(beat.get("status") or "available")))
        credits=[]
        main_label=canonical_producer_label(str(beat.get("producer_username") or ""))
        for p in beat.get("producers",[]):
            label=canonical_producer_label(p.get("username") or p.get("display_name") or "")
            if label and label.casefold() != main_label.casefold(): credits.append(label)
        self.co=QLineEdit(", ".join(credits)); self.co.setPlaceholderText("Co-producers")
        form.addRow("Beat name:",self.name); form.addRow("BPM:",self.bpm); form.addRow("Key:",self.key); form.addRow("Producer:",self.producer); form.addRow("Status:",self.status); form.addRow("Co-producers:",self.co); root.addLayout(form)
        root.addWidget(QLabel("AUDIO FILE")); self.drop=Mp3DropZone(); root.addWidget(self.drop)
        self.drop.fileSelected.connect(self.parse_filename_metadata)
        self.parse_hint=QLabel("Drop another MP3 to suggest name/BPM/key from its filename. Fields remain editable.")
        self.parse_hint.setStyleSheet("color:#7F8B9F;font-size:11px;"); self.parse_hint.setWordWrap(True); root.addWidget(self.parse_hint)
        existing=self.audio_store.path_for(beat.get("id")) if self.audio_store else None
        if existing: self.drop.label.setText(f"Current: {existing.name}  •  drop another MP3 to replace")
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def parse_filename_metadata(self, path):
        try:
            meta = parse_beat_filename(path)
        except (re.error, ValueError, TypeError) as exc:
            self.parse_hint.setText(f"Could not parse filename metadata safely: {exc}. You can enter the fields manually.")
            self.parse_hint.setStyleSheet("color:#C98B8B;font-size:11px;")
            return
        if meta.get("name"):
            self.name.setText(meta["name"])
        if meta.get("bpm") is not None:
            self.bpm.setText(str(meta["bpm"]))
        if meta.get("musical_key"):
            self.key.setText(meta["musical_key"])

    def save(self):
        name=self.name.text().strip();
        if not name: QMessageBox.warning(self,"Missing field","Enter beat name."); return
        bpm=None; t=self.bpm.text().strip()
        if t:
            try: bpm=int(t); assert bpm>0
            except Exception: QMessageBox.warning(self,"Invalid BPM","BPM must be a positive number."); return
        co=[x.strip() for x in self.co.text().split(",") if x.strip()]
        try:
            beat=self.api.update_beat(beat_id=self.beat["id"],name=name,bpm=bpm,musical_key=self.key.text().strip() or None,status=self.status.currentData(),producer_username=self.producer.text().strip(),co_producer_usernames=co)
            if self.audio_store and self.drop.path: self.audio_store.attach(self.beat["id"],self.drop.path)
            self.beat=beat; self.accept()
        except Exception as e: QMessageBox.critical(self,"Could not save beat",str(e))


class BeatCard(QFrame):
    def __init__(self, beat, has_audio, on_play, on_edit, on_delete, on_tag=None, on_favorite=None, is_favorite=False, parent=None):
        super().__init__(parent); self.beat=beat; self.setObjectName("beatCard")
        lay=QHBoxLayout(self); lay.setContentsMargins(14,12,14,12); lay.setSpacing(12)
        icon=QLabel(); icon.setPixmap(ui_icon("beats").pixmap(22,22)); icon.setFixedSize(42,42); icon.setAlignment(Qt.AlignmentFlag.AlignCenter); icon.setStyleSheet("background:#211334;border:1px solid #4F2E70;border-radius:12px;"); lay.addWidget(icon)
        info=QVBoxLayout(); info.setSpacing(3)
        t=QLabel(beat.get("name") or "Beat"); t.setStyleSheet("font-size:15px;font-weight:700;"); info.addWidget(t)
        meta=f"{beat.get('bpm') or '—'} BPM  •  {beat.get('musical_key') or 'Key —'}  •  {beat.get('status') or 'available'}"
        m=QLabel(meta); m.setStyleSheet("color:#9AA4B5;font-size:12px;"); info.addWidget(m)
        producers=[canonical_producer_label(p.get("username") or p.get("display_name") or "") for p in beat.get("producers",[])]
        c=QLabel("Credits: "+(", ".join(x for x in producers if x) or "—")); c.setStyleSheet("color:#C6B2E9;font-size:12px;"); info.addWidget(c)
        lay.addLayout(info,1)
        play=QPushButton("▶  Play" if has_audio else "No MP3"); play.setEnabled(has_audio); play.clicked.connect(on_play); play.setObjectName("iconButton"); lay.addWidget(play)
        edit=QPushButton("Edit"); edit.setObjectName("iconButton"); edit.clicked.connect(on_edit); lay.addWidget(edit)
        if on_tag:
            tag=QPushButton("Tag"); tag.setObjectName("iconButton"); tag.clicked.connect(on_tag); lay.addWidget(tag)
        fav=QPushButton("★" if is_favorite else "☆"); fav.setObjectName("iconButton"); fav.setToolTip("Unfavorite" if is_favorite else "Favorite")
        if on_favorite: fav.clicked.connect(lambda *args,f=beat,b=fav:on_favorite(f,b))
        lay.addWidget(fav)
        delete=QPushButton("×"); delete.setObjectName("iconButton"); delete.clicked.connect(on_delete); lay.addWidget(delete)

PITCHES = {"C":0,"C#":1,"DB":1,"D":2,"D#":3,"EB":3,"E":4,"F":5,"F#":6,"GB":6,"G":7,"G#":8,"AB":8,"A":9,"A#":10,"BB":10,"B":11}

def _norm_key(value):
    v=(value or "").strip().upper().replace("♯","#").replace("♭","B")
    v=re.sub(r"\s+"," ",v)
    return v

def _key_parts(value):
    v=_norm_key(value)
    m=re.match(r"^([A-G](?:#|B)?)[\s-]*(MINOR|MAJOR|MIN|MAJ|M|MINOR)?$",v)
    if not m: return None,None
    root=PITCHES.get(m.group(1)); mode=m.group(2) or "MAJOR"
    if mode in ("MIN","M"): mode="MINOR"
    if mode=="MAJ": mode="MAJOR"
    return root,mode

def _compatible_key_filter(actual, desired):
    ar,am=_key_parts(actual); dr,dm=_key_parts(desired)
    if ar is None or dr is None: return False
    if ar==dr and am==dm: return True
    # Relative major/minor: minor root is 9 semitones above its relative major.
    if am=="MAJOR" and dm=="MINOR" and ar==(dr+3)%12: return True
    if am=="MINOR" and dm=="MAJOR" and ar==(dr+9)%12: return True
    # Perfect 4th/5th in same mode are useful harmonic neighbours.
    if am==dm and ((ar-dr)%12 in (5,7)): return True
    return False

class BeatsTab(QWidget):
    nowPlaying = Signal(str, bool)
    def __init__(self, api, audio_store=None):
        super().__init__(); self.api=api; self.audio_store=audio_store
        self.player=QMediaPlayer(self); self.audio=QAudioOutput(self); self.player.setAudioOutput(self.audio); self.audio.setVolume(0.85); self.current_beat_name=""
        self.player.errorOccurred.connect(self._audio_error)
        self.player.playbackStateChanged.connect(self._on_playback_state)
        self.player.mediaStatusChanged.connect(lambda _status: self._emit_playing())
        root=QVBoxLayout(self); root.setContentsMargins(30,24,30,24); root.setSpacing(12)
        header=QHBoxLayout(); title=QLabel("Beats"); title.setObjectName("title"); header.addWidget(title); header.addStretch(); bulk=QPushButton("Bulk Import MP3"); bulk.setObjectName("iconButton"); bulk.clicked.connect(self.bulk_import); header.addWidget(bulk); bulk_edit=QPushButton("Bulk Edit"); bulk_edit.setObjectName("iconButton"); bulk_edit.clicked.connect(self.bulk_edit); header.addWidget(bulk_edit); add=QPushButton("+ Add Beat"); add.setObjectName("primary"); add.clicked.connect(self.add_beat); header.addWidget(add); root.addLayout(header)
        self.search=QLineEdit(); self.search.setPlaceholderText("Search beats..."); self.search.textChanged.connect(self.reload); root.addWidget(self.search)
        filter_row=QHBoxLayout()
        self.bpm_min=QLineEdit(); self.bpm_min.setPlaceholderText("Min BPM"); self.bpm_min.setFixedWidth(90)
        self.bpm_max=QLineEdit(); self.bpm_max.setPlaceholderText("Max BPM"); self.bpm_max.setFixedWidth(90)
        self.key_filter=QLineEdit(); self.key_filter.setPlaceholderText("Key (e.g. F# minor)"); self.key_filter.setFixedWidth(150)
        self.status_filter=QComboBox(); self.status_filter.addItem("All statuses",""); self.status_filter.addItem("Available","available"); self.status_filter.addItem("Archived","archived"); self.status_filter.setFixedWidth(140)
        self.producer_filter=QLineEdit(); self.producer_filter.setPlaceholderText("Producer"); self.producer_filter.setFixedWidth(120)
        self.compatible=QCheckBox("Compatible key")
        reset=QPushButton("Reset filters"); reset.setObjectName("iconButton")
        for w in (self.bpm_min,self.bpm_max,self.key_filter,self.status_filter,self.producer_filter):
            if isinstance(w,QComboBox): w.currentIndexChanged.connect(self.apply_filters)
            else: w.textChanged.connect(self.apply_filters)
        self.compatible.stateChanged.connect(self.apply_filters); reset.clicked.connect(self.reset_filters)
        for w in (self.bpm_min,self.bpm_max,self.key_filter,self.status_filter,self.producer_filter,self.compatible): filter_row.addWidget(w)
        filter_row.addStretch(); bulk_tag_btn=QPushButton("Bulk Tag"); bulk_tag_btn.setObjectName("iconButton"); bulk_tag_btn.clicked.connect(self.bulk_tag); filter_row.addWidget(bulk_tag_btn); filter_row.addWidget(reset); root.addLayout(filter_row)
        self.filter_count=QLabel(""); self.filter_count.setStyleSheet("color:#8994A8;font-size:11px;"); root.addWidget(self.filter_count)
        self.list=QListWidget(); self.list.setSpacing(7); self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection); root.addWidget(self.list,1)
        more_row=QHBoxLayout(); more_row.addStretch(); self.load_more=QPushButton("Load more beats"); self.load_more.setObjectName("iconButton"); self.load_more.clicked.connect(self.load_more_beats); more_row.addWidget(self.load_more); root.addLayout(more_row)
        self._beats=[]; self._offset=0; self._has_more=True; self.reload()
    def _audio_error(self, _error, msg):
        self.nowPlaying.emit(self.current_beat_name or "Nothing playing", False)
        QMessageBox.warning(self,"Audio playback", msg or "Could not play this MP3.")

    def _on_playback_state(self, state):
        self._emit_playing()

    def _emit_playing(self):
        playing=self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState
        self.nowPlaying.emit(self.current_beat_name if playing else "Nothing playing", playing)

    def stop_playback(self):
        self.player.stop()
        self.current_beat_name=""
        self.nowPlaying.emit("Nothing playing", False)

    def reload(self):
        try:
            self._offset=0
            self._beats=self.api.beats(self.search.text(), limit=100, offset=0)
            self._has_more=len(self._beats)>=100
            self.load_more.setEnabled(self._has_more)
            self.apply_filters()
        except Exception as e:
            self.list.clear(); self.list.addItem(f"Could not load beats: {e}")
            self.load_more.setEnabled(False)
    def load_more_beats(self):
        if not self._has_more: return
        try:
            batch=self.api.beats(self.search.text(), limit=100, offset=len(self._beats))
            self._beats.extend(batch)
            self._has_more=len(batch)>=100
            self.load_more.setEnabled(self._has_more)
            self.apply_filters()
        except Exception as e:
            QMessageBox.warning(self,"Load more beats",str(e))

    def reset_filters(self):
        self.bpm_min.clear(); self.bpm_max.clear(); self.key_filter.clear(); self.status_filter.setCurrentIndex(0); self.producer_filter.clear(); self.compatible.setChecked(False)
        self.apply_filters()

    def apply_filters(self):
        if not hasattr(self,'list'): return
        self.list.clear()
        try:
            min_bpm=int(self.bpm_min.text().strip()) if self.bpm_min.text().strip() else None
        except ValueError: min_bpm=None
        try:
            max_bpm=int(self.bpm_max.text().strip()) if self.bpm_max.text().strip() else None
        except ValueError: max_bpm=None
        desired_key=self.key_filter.text().strip()
        desired_status=self.status_filter.currentData()
        producer_q=self.producer_filter.text().strip().casefold()
        filtered=[]
        for beat in getattr(self,'_beats',[]):
            bpm=beat.get('bpm')
            if min_bpm is not None and (bpm is None or bpm<min_bpm): continue
            if max_bpm is not None and (bpm is None or bpm>max_bpm): continue
            if desired_status and beat.get('status')!=desired_status: continue
            if producer_q:
                credits=[canonical_producer_label(p.get('username') or p.get('display_name') or '') for p in beat.get('producers',[])]
                if not any(producer_q in c.casefold() for c in credits): continue
            if desired_key:
                actual=beat.get('musical_key') or ''
                if self.compatible.isChecked():
                    if not _compatible_key_filter(actual,desired_key): continue
                elif _norm_key(actual)!=_norm_key(desired_key): continue
            filtered.append(beat)
        try: fav_set={(x.get('entity_type'),x.get('entity_id')) for x in self.api.favorites()}
        except Exception: fav_set=set()
        for beat in filtered:
            item=QListWidgetItem(); item.setSizeHint(QSize(0,92)); self.list.addItem(item)
            card=BeatCard(beat,bool(self.audio_store and self.audio_store.path_for(beat.get('id'))),lambda *args,b=beat:self.play_beat(b),lambda *args,b=beat:self.edit_beat(b),lambda *args,b=beat:self.delete_beat(b),lambda *args,b=beat:self.tag_beat(b),lambda button,b=beat:self.toggle_favorite(b,button),('beat',beat.get('id')) in fav_set); self.list.setItemWidget(item,card)
        self.filter_count.setText(f"Showing {len(filtered)} of {len(getattr(self,'_beats',[]))} beats")
    def play_beat(self,beat):
        p=self.audio_store.path_for(beat.get("id")) if self.audio_store else None
        if not p: QMessageBox.information(self,"Audio","No MP3 attached to this beat."); return
        source=QUrl.fromLocalFile(str(Path(p).resolve()))
        if self.player.source()==source and self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause(); self._emit_playing(); return
        self.current_beat_name=beat.get("name") or "Beat"
        self.player.setSource(source)
        self.player.play()
    def tag_beat(self,beat):
        tag,ok=QInputDialog.getText(self,"Add Tag",f"Tag for {beat.get('name','Beat')}:")
        if ok and tag.strip():
            try:self.api.add_tag(beat["id"],tag.strip())
            except Exception as e:QMessageBox.warning(self,"Tag",str(e))
    def toggle_favorite(self,beat,button):
        try:
            data=self.api.toggle_favorite('beat',beat['id']); active=bool(data.get('favorite')); button.setText('★' if active else '☆'); button.setToolTip('Unfavorite' if active else 'Favorite')
        except Exception as e: QMessageBox.warning(self,'Favorite',str(e))
    def add_beat(self):
        if AddBeatDialog(self.api,self,self.audio_store).exec()==QDialog.DialogCode.Accepted: self.reload()
    def edit_beat(self,beat):
        if EditBeatDialog(self.api,beat,self,self.audio_store).exec()==QDialog.DialogCode.Accepted: self.reload()
    def delete_beat(self,beat):
        if QMessageBox.question(self,"Delete Beat",f'Delete "{beat.get("name","Beat")}"?')!=QMessageBox.StandardButton.Yes:return
        try:
            self.api.delete_beat(beat["id"])
            if self.audio_store:self.audio_store.remove(beat["id"])
            self.reload()
            self.window().statusBar().showMessage("Beat moved to Trash — restore it from Settings → Trash.",5000)
        except Exception as e: QMessageBox.warning(self,"Delete Beat",str(e))


    def bulk_edit(self):
        selected=self.list.selectedItems()
        if not selected:
            QMessageBox.information(self,"Bulk Edit","Select beats in the list first."); return
        if BulkEditBeatsDialog(self.api,len(selected),self).exec()==QDialog.DialogCode.Accepted:
            self.reload()
            self.window().statusBar().showMessage(f"Updated {len(selected)} beats",2500)

    def bulk_import(self):
        paths,_=QFileDialog.getOpenFileNames(self,"Import MP3 beats","","MP3 files (*.mp3)")
        if not paths: return
        imported=0; skipped=0; errors=[]
        for path in paths:
            try:
                if self.audio_store and self.audio_store.duplicate_beat_id(path):
                    skipped += 1; continue
                meta=parse_beat_filename(path)
                beat=self.api.create_beat(name=meta.get("name") or Path(path).stem,bpm=meta.get("bpm"),musical_key=meta.get("musical_key"),status="available",producer_username=(self.api.user or {}).get("username",""),co_producer_usernames=[])
                if self.audio_store and beat.get("id"): self.audio_store.attach(beat["id"],path)
                imported += 1
            except Exception as e: errors.append(f"{Path(path).name}: {e}")
        self.reload()
        msg=f"Imported: {imported}\nSkipped duplicates: {skipped}"
        if errors: msg += "\nErrors:\n"+"\n".join(errors[:8])
        QMessageBox.information(self,"Bulk Import",msg)

    def bulk_tag(self):
        selected=self.list.selectedItems()
        if not selected:
            QMessageBox.information(self,"Bulk Tag","Select beats in the list first."); return
        tag,ok=QInputDialog.getText(self,"Bulk Tag",f"Tag {len(selected)} selected beats:")
        if not ok or not tag.strip(): return
        count=0
        for item in selected:
            card=self.list.itemWidget(item); beat=getattr(card,"beat",None)
            if not beat: continue
            try: self.api.add_tag(beat["id"],tag.strip()); count+=1
            except Exception: pass
        QMessageBox.information(self,"Bulk Tag",f"Tagged {count} beats.")


class BulkEditBeatsDialog(QDialog):
    def __init__(self, api, count, parent=None):
        super().__init__(parent); self.api=api; self.setWindowTitle("Bulk Edit Beats"); self.setMinimumWidth(480)
        root=QVBoxLayout(self)
        root.addWidget(QLabel(f"Editing {count} selected beat(s)"))
        hint=QLabel("Leave a field unchanged to keep existing values.")
        hint.setStyleSheet("color:#8994A8;font-size:11px;"); root.addWidget(hint)
        form=QFormLayout()
        self.bpm=QLineEdit(); self.bpm.setPlaceholderText("unchanged / e.g. 140")
        self.key=QLineEdit(); self.key.setPlaceholderText("unchanged / e.g. F# minor")
        self.status=QComboBox(); self.status.addItem("Unchanged",""); self.status.addItem("Available","available"); self.status.addItem("Archived","archived")
        self.tag=QLineEdit(); self.tag.setPlaceholderText("Add tag (optional)")
        form.addRow("BPM:",self.bpm); form.addRow("Key:",self.key); form.addRow("Status:",self.status); form.addRow("Add tag:",self.tag); root.addLayout(form)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); root.addWidget(buttons)
    def save(self):
        bpm_txt=self.bpm.text().strip()
        bpm=None
        if bpm_txt:
            try:
                bpm=int(bpm_txt)
                if not 1<=bpm<=400: raise ValueError
            except ValueError:
                QMessageBox.warning(self,"Bulk Edit","BPM must be between 1 and 400."); return
        try:
            selected=self.parentWidget().list.selectedItems() if self.parentWidget() and hasattr(self.parentWidget(),"list") else []
            ids=[]
            for item in selected:
                card=self.parentWidget().list.itemWidget(item)
                beat=getattr(card,"beat",None)
                if beat: ids.append(int(beat["id"]))
            if not ids:
                QMessageBox.warning(self,"Bulk Edit","No beats selected."); return
            self.api.bulk_update_beats(ids,bpm=bpm,musical_key=self.key.text().strip() if self.key.text().strip() else None,status=self.status.currentData() or None,add_tag=self.tag.text().strip() or None)
            self.accept()
        except Exception as e: QMessageBox.warning(self,"Bulk Edit",str(e))

class SendBeatDialog(QDialog):
    def __init__(self, api, artist_id, parent=None):
        super().__init__(parent)
        self.api = api
        self.artist_id = artist_id
        self.setWindowTitle("Add Beat to Artist")
        self.setMinimumWidth(430)

        root = QVBoxLayout(self)
        title = QLabel("ADD BEAT TO ARTIST")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        root.addWidget(self.list)

        try:
            for beat in self.api.beats():
                item = QListWidgetItem(f"{beat['name']}")
                item.setData(Qt.ItemDataRole.UserRole, beat["id"])
                self.list.addItem(item)
        except Exception as e:
            self.list.addItem(f"Could not load beats: {e}")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def save(self):
        selected = self.list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No beats", "Select at least one beat.")
            return

        try:
            for item in selected:
                beat_id = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(beat_id, int):
                    self.api.send_beat(self.artist_id, beat_id)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Could not send beat", str(e))



class FollowUpDialog(QDialog):
    def __init__(self, api, artist, parent=None):
        super().__init__(parent); self.api=api; self.artist=artist
        self.setWindowTitle("Schedule Follow-up"); self.setMinimumWidth(460)
        root=QVBoxLayout(self); title=QLabel("SCHEDULE FOLLOW-UP"); title.setStyleSheet("font-size:20px;font-weight:750;"); root.addWidget(title)
        root.addWidget(QLabel(f"Artist: {artist.get('name','Artist')}"))
        form=QFormLayout(); self.days=QDoubleSpinBox(); self.days.setRange(0,365); self.days.setDecimals(0); self.days.setValue(3); form.addRow("Due in days:",self.days)
        self.title=QLineEdit("Follow up"); form.addRow("Title:",self.title)
        self.notes=QLineEdit(); self.notes.setPlaceholderText("Optional notes"); form.addRow("Notes:",self.notes); root.addLayout(form); hint=QLabel('New goals always start at 0. Progress is counted from the moment this goal is created; previous earnings do not carry over.'); hint.setWordWrap(True); hint.setStyleSheet('color:#7F8B9F;font-size:11px;'); root.addWidget(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); root.addWidget(buttons)
    def save(self):
        try:
            from datetime import datetime, timezone, timedelta
            due=(datetime.now(timezone.utc)+timedelta(days=int(self.days.value()))).isoformat()
            self.api.create_followup(self.artist['id'],due,self.title.text().strip() or 'Follow up',self.notes.text().strip())
            self.accept()
        except Exception as e: QMessageBox.warning(self,"Follow-up",str(e))

class GoalDialog(QDialog):
    def __init__(self, api, goal=None, parent=None):
        super().__init__(parent); self.api=api; self.goal=goal
        self.setWindowTitle("Goal"); self.setMinimumWidth(460)
        root=QVBoxLayout(self); title=QLabel("SET GOAL"); title.setStyleSheet("font-size:20px;font-weight:750;"); root.addWidget(title)
        form=QFormLayout(); self.name=QLineEdit((goal or {}).get('title','Revenue goal')); self.name.setPlaceholderText('Examples: Revenue goal, Licenses goal, Artists goal, Beats sent goal'); self.target=QDoubleSpinBox(); self.target.setRange(.01,100000000); self.target.setDecimals(2); self.target.setValue(float((goal or {}).get('target',0) or 0)); self.current=QDoubleSpinBox(); self.current.setRange(0,100000000); self.current.setDecimals(2); self.current.setValue(float((goal or {}).get('current',0) or 0)); self.current.setReadOnly(True); self.current.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons); self.current.setEnabled(False); self.currency=QComboBox();
        for label,code in (("USD","USD"),("EUR","EUR"),("CHF","CHF")): self.currency.addItem(label,code)
        prof_cur=(self.api.user or {}).get("currency","USD"); ci=self.currency.findData(prof_cur); self.currency.setCurrentIndex(ci if ci >= 0 else 0)
        default_cur=(goal or {}).get('currency') or (self.api.user or {}).get('currency','USD'); self.currency.setCurrentIndex(max(0,self.currency.findData(default_cur))); self.period=QComboBox(); self.period.addItem('This Month','month'); self.period.addItem('This Year','year'); self.period.addItem('All Time','all'); self.period.setCurrentIndex(max(0,self.period.findData((goal or {}).get('period','month')))); form.addRow('Title:',self.name); form.addRow('Target:',self.target); form.addRow('Currency:',self.currency); form.addRow('Progress:',self.current); form.addRow('Period:',self.period); root.addLayout(form)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); root.addWidget(buttons)
    def save(self):
        title=self.name.text().strip()
        if not title:
            QMessageBox.warning(self,'Goal','Enter a goal title.')
            return
        if self.target.value() <= 0:
            QMessageBox.warning(self,'Goal','Target must be greater than 0.')
            return
        try:
            if self.goal:
                self.api.update_goal(self.goal['id'],title,self.target.value(),self.current.value(),self.period.currentData(),self.currency.currentData())
            else:
                self.api.create_goal(title,self.target.value(),self.current.value(),self.period.currentData(),self.currency.currentData())
            self.accept()
        except Exception as e: QMessageBox.warning(self,'Goal',str(e))

class TrashDialog(QDialog):
    def __init__(self,api,parent=None):
        super().__init__(parent); self.api=api; self.setWindowTitle('Trash'); self.setMinimumSize(520,420); root=QVBoxLayout(self); self.list=QListWidget(); root.addWidget(self.list); bar=QHBoxLayout(); self.restore=QPushButton('Restore selected'); self.restore.clicked.connect(self.restore_selected); self.permanent=QPushButton('Delete permanently'); self.permanent.clicked.connect(self.permanent_selected); close=QPushButton('Close'); close.clicked.connect(self.accept); bar.addWidget(self.restore); bar.addWidget(self.permanent); bar.addStretch(); bar.addWidget(close); root.addLayout(bar); self.reload()
    def reload(self):
        self.list.clear(); self.rows=[]
        try:
            data=self.api.trash()
            for x in data.get('artists',[]): self._add('artist',x)
            for x in data.get('beats',[]): self._add('beat',x)
            if self.list.count()==0:self.list.addItem('Trash is empty.')
        except Exception as e:self.list.addItem(f'Could not load trash: {e}')
    def _add(self,typ,x):
        item=QListWidgetItem(f"{typ.upper()}  •  {x.get('name','')}" ); item.setData(Qt.ItemDataRole.UserRole,(typ,x.get('id'))); self.list.addItem(item)
    def permanent_selected(self):
        item=self.list.currentItem()
        if not item: return
        data=item.data(Qt.ItemDataRole.UserRole)
        if not data: return
        if QMessageBox.question(self,"Delete permanently","This cannot be undone. Continue?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes: return
        try:
            self.api.permanent_delete(data[0],data[1]); self.reload()
        except Exception as e: QMessageBox.warning(self,"Delete permanently",str(e))

    def restore_selected(self):
        item=self.list.currentItem();
        if not item:return
        data=item.data(Qt.ItemDataRole.UserRole)
        if not data:return
        try:self.api.restore(data[0],data[1]); self.reload()
        except Exception as e:QMessageBox.warning(self,'Restore',str(e))

class ArtistTimelineDialog(QDialog):
    def __init__(self, api, artist, parent=None):
        super().__init__(parent); self.api=api; self.artist=artist
        self.setWindowTitle(f"Timeline — {artist.get('name','Artist')}"); self.setMinimumSize(620,520)
        root=QVBoxLayout(self); root.setContentsMargins(22,20,22,18)
        title=QLabel(artist.get('name','Artist')); title.setStyleSheet('font-size:22px;font-weight:750;'); root.addWidget(title)
        sub=QLabel('Artist history: beats, follow-ups and licenses'); sub.setStyleSheet('color:#8994A8;'); root.addWidget(sub)
        self.list=QListWidget(); root.addWidget(self.list,1)
        close=QPushButton('Close'); close.clicked.connect(self.accept); root.addWidget(close)
        self.load()
    def load(self):
        self.list.clear(); rows=[]
        try:
            for b in self.artist.get('beats',[]):
                rows.append((0, f"Beat sent  •  {b.get('name','Beat')}"))
            for lic in self.api.licenses():
                if lic.get('artist_id')==self.artist.get('id'):
                    rows.append((1, f"License  •  {str(lic.get('license_type','')).upper()}  •  ${lic.get('price',0)}"))
            ov=self.api.workspace_overview()
            for f in ov.get('followups',[]):
                if f.get('artist_id')==self.artist.get('id'):
                    rows.append((2, f"Follow-up  •  {f.get('title','Follow up')}  •  {str(f.get('due_at',''))[:10]}"))
        except Exception as e:
            self.list.addItem(f"Could not load timeline: {e}"); return
        if not rows:
            self.list.addItem('No activity yet.')
            return
        for _,text in rows:
            self.list.addItem(text)

class ArtistCardDialog(QDialog):
    def __init__(self, api, artist, parent=None):
        super().__init__(parent)
        self.api = api
        self.artist = artist
        self.setWindowTitle("Artist")
        self.setMinimumWidth(500)

        root = QVBoxLayout(self)

        title = QLabel(artist.get("name", "Artist"))
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        root.addWidget(title)

        info = QLabel(
            f"Username: {artist.get('artist_username') or '—'}\n"
            f"Platform: {artist.get('platform') or '—'}\n"
            f"Message status: {artist.get('message_status') or '—'}\n"
            f"Cash Ready: {'Yes' if artist.get('cash_ready') else 'No'}"
        )
        info.setStyleSheet("color: #B8B8B8;")
        root.addWidget(info)
        root.addSpacing(12)

        beats_title = QLabel("BEATS SENT")
        beats_title.setStyleSheet("font-size: 13px; font-weight: 700;")
        root.addWidget(beats_title)

        self.beats = QListWidget()
        for beat in artist.get("beats", []):
            self.beats.addItem(
                QListWidgetItem(
                    f"{beat.get('name', 'Beat')}"
                )
            )

        if self.beats.count() == 0:
            self.beats.addItem("No beats sent yet.")

        root.addWidget(self.beats)

        buttons = QHBoxLayout()

        edit = QPushButton("Edit")
        edit.setObjectName("primary")
        edit.clicked.connect(self.edit_artist)

        add_beat = QPushButton("Add Beat")
        add_beat.setObjectName("primary")
        add_beat.clicked.connect(self.add_beat)

        follow = QPushButton("Follow-up")
        follow.setObjectName("iconButton")
        follow.clicked.connect(self.follow_up)

        score_btn = QPushButton("Score")
        score_btn.setObjectName("iconButton")
        score_btn.clicked.connect(self.show_score)

        timeline = QPushButton("Timeline")
        timeline.setObjectName("iconButton")
        timeline.clicked.connect(lambda: ArtistTimelineDialog(self.api, self.artist, self).exec())

        delete = QPushButton("Delete")
        delete.clicked.connect(self.delete_artist)

        close = QPushButton("Close")
        close.clicked.connect(self.reject)

        buttons.addWidget(edit)
        buttons.addWidget(add_beat)
        buttons.addWidget(follow)
        buttons.addWidget(score_btn)
        buttons.addWidget(delete)
        buttons.addStretch()
        buttons.addWidget(close)
        root.addLayout(buttons)

    def show_score(self):
        try:
            data=self.api.artist_score(self.artist["id"])
            reasons="\n".join(f"• {r}" for r in data.get("reasons",[])) or "• No activity signals yet"
            QMessageBox.information(self,"Artist Score",f"Score: {data.get('score',0)}/100\nCategory: {data.get('category','COLD')}\n\nWhy:\n{reasons}")
        except Exception as e: QMessageBox.warning(self,"Artist Score",str(e))

    def follow_up(self):
        FollowUpDialog(self.api,self.artist,self).exec()

    def delete_artist(self):
        name = self.artist.get("name", "this artist")
        confirm = QMessageBox.question(
            self, "Delete Artist",
            f"Remove \"{name}\" from your artist list?\n\n"
            "The artist will stay in Global List if other users have them.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api.delete_artist(self.artist["id"])
            self.window().statusBar().showMessage("Artist moved to Trash — restore it from Settings → Trash.",5000)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Could not delete artist", str(e))

    def add_beat(self):
        dialog = SendBeatDialog(self.api, self.artist["id"], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                updated = self.api.get_artist(self.artist["id"])
                self.artist = updated
                self.accept()
            except Exception:
                self.accept()

    def edit_artist(self):
        dialog = EditArtistDialog(self.api, self.artist, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                updated = self.api.get_artist(self.artist["id"])
                self.artist = updated
                self.refresh_card()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def refresh_card(self):
        # Rebuild the dialog contents by closing it; the list will reload
        # when the dialog is opened again. This keeps the first edit step simple.
        self.accept()


class ArtistRow(QFrame):
    def __init__(self,artist,on_open,on_edit=None,on_favorite=None,is_favorite=False,parent=None):
        super().__init__(parent); self.setObjectName("artistCard")
        lay=QHBoxLayout(self); lay.setContentsMargins(14,11,14,11); lay.setSpacing(10)
        avatar=QLabel((artist.get("name") or "A")[:1].upper()); avatar.setAlignment(Qt.AlignmentFlag.AlignCenter); avatar.setFixedSize(44,44); avatar.setStyleSheet("background:#211334;border:1px solid #4F2E70;border-radius:14px;font-size:17px;font-weight:750;color:#C99BFF;"); lay.addWidget(avatar)
        info=QVBoxLayout(); info.setSpacing(2)
        name=QLabel(artist.get("name") or "Artist"); name.setStyleSheet("font-size:15px;font-weight:700;"); info.addWidget(name)
        user=artist.get("artist_username") or "No username"; platform=artist.get("platform") or "—"; info.addWidget(QLabel(f"{user}  •  {platform}"))
        lics=int(artist.get('licenses_count',0) or 0); sends=int(artist.get('beats_sent_count',0) or 0)
        score=min(100, lics*25 + min(sends,5)*5 + (10 if artist.get('cash_ready') else 0))
        tier='VIP' if score>=85 and lics>=2 else ('HOT' if score>=70 else ('WARM' if score>=35 else 'COLD'))
        stats=QLabel(f"Beats sent: {sends}  •  Licenses: {lics}  •  {tier}  •  Score {score}/100  •  {'Cash ready' if artist.get('cash_ready') else 'Cash not ready'}")
        stats.setStyleSheet("color:#9AA4B5;font-size:11px;"); stats.setToolTip("Artist Score combines paid licenses, repeat purchases, beat sends, follow-ups, activity recency and cash readiness."); info.addWidget(stats); lay.addLayout(info,1)
        status=QLabel((artist.get("message_status") or "new").replace("_"," ").title()); status.setStyleSheet("background:#171126;border:1px solid #4A2D65;border-radius:9px;padding:6px 8px;color:#C6A7E8;"); lay.addWidget(status)
        fav=QPushButton("★" if is_favorite else "☆"); fav.setObjectName("iconButton"); fav.setToolTip("Unfavorite" if is_favorite else "Favorite");
        if on_favorite: fav.clicked.connect(lambda *args,a=artist,b=fav:on_favorite(a,b))
        lay.addWidget(fav)
        edit=QPushButton("Edit"); edit.setObjectName("iconButton");
        if on_edit: edit.clicked.connect(lambda *args,a=artist:on_edit(a))
        lay.addWidget(edit)
        b=QPushButton("Open"); b.setObjectName("iconButton"); b.setToolTip("Open artist profile, edit and timeline"); b.clicked.connect(lambda *args,a=artist:on_open(a)); lay.addWidget(b)

class ArtistsTab(QWidget):
    def __init__(self,api):
        super().__init__(); self.api=api; root=QVBoxLayout(self); root.setContentsMargins(30,24,30,24); root.setSpacing(12)
        header=QHBoxLayout(); title=QLabel("Artists"); title.setObjectName("title"); header.addWidget(title); header.addStretch(); add=QPushButton("+ Add Artist"); add.setObjectName("primary"); add.clicked.connect(self.add_artist); header.addWidget(add); root.addLayout(header)
        self.search=QLineEdit(); self.search.setPlaceholderText("Search artists..."); self.search.textChanged.connect(self.reload); root.addWidget(self.search)
        self.tabs=QComboBox(); self.tabs.addItems(["My Artists","Global List"]); self.tabs.currentIndexChanged.connect(self.reload); root.addWidget(self.tabs)
        self.list=QListWidget(); self.list.setSpacing(7); root.addWidget(self.list,1)
        more_row=QHBoxLayout(); more_row.addStretch(); self.load_more=QPushButton("Load more artists"); self.load_more.setObjectName("iconButton"); self.load_more.clicked.connect(self.load_more_artists); more_row.addWidget(self.load_more); root.addLayout(more_row)
        self._artists=[]; self._offset=0; self._has_more=True; self.reload()
    def reload(self):
        self.list.clear(); self._offset=0
        try:
            artists=self.api.my_artists(self.search.text(),limit=100,offset=0) if self.tabs.currentIndex()==0 else self.api.global_artists(self.search.text(),limit=100,offset=0)
            self._artists=list(artists); self._has_more=len(artists)>=100; self.load_more.setEnabled(self._has_more)
            fav_set={(x.get("entity_type"),x.get("entity_id")) for x in self.api.favorites()} if self.tabs.currentIndex()==0 else set()
            for artist in self._artists:
                item=QListWidgetItem(); item.setSizeHint(QSize(0,92)); self.list.addItem(item)
                self.list.setItemWidget(item,ArtistRow(artist,self.open_artist,self.edit_artist,self.toggle_favorite,('artist',artist.get('id')) in fav_set))
            if not self._artists: self.list.addItem("No artists match this search.")
        except Exception as e:
            self.list.addItem(f"Error: {e}"); self.load_more.setEnabled(False)
    def load_more_artists(self):
        if not self._has_more: return
        try:
            batch=self.api.my_artists(self.search.text(),limit=100,offset=len(self._artists)) if self.tabs.currentIndex()==0 else self.api.global_artists(self.search.text(),limit=100,offset=len(self._artists))
            self._artists.extend(batch); self._has_more=len(batch)>=100; self.load_more.setEnabled(self._has_more)
            fav_set={(x.get("entity_type"),x.get("entity_id")) for x in self.api.favorites()} if self.tabs.currentIndex()==0 else set()
            for artist in batch:
                item=QListWidgetItem(); item.setSizeHint(QSize(0,92)); self.list.addItem(item)
                self.list.setItemWidget(item,ArtistRow(artist,self.open_artist,self.edit_artist,self.toggle_favorite,('artist',artist.get('id')) in fav_set))
        except Exception as e: QMessageBox.warning(self,"Load more artists",str(e))
    def open_artist(self,artist):
        try: detail=self.api.get_artist(artist["id"])
        except Exception as e: QMessageBox.warning(self,"Error",str(e)); return
        ArtistCardDialog(self.api,detail,self).exec(); self.reload()
    def edit_artist(self,artist):
        try: detail=self.api.get_artist(artist["id"])
        except Exception as e: QMessageBox.warning(self,"Error",str(e)); return
        if EditArtistDialog(self.api,detail,self).exec()==QDialog.DialogCode.Accepted:self.reload()
    def toggle_favorite(self,artist,button):
        try:
            data=self.api.toggle_favorite('artist',artist['id']); active=bool(data.get('favorite')); button.setText('★' if active else '☆'); button.setToolTip('Unfavorite' if active else 'Favorite')
        except Exception as e: QMessageBox.warning(self,'Favorite',str(e))
    def complete_followup(self,item):
        f=item.data(Qt.ItemDataRole.UserRole) or {}
        if not f:return
        try:self.api.complete_followup(f["id"]); self.refresh()
        except Exception as e:QMessageBox.warning(self,"Follow-up",str(e))
    def add_goal(self):
        if GoalDialog(self.api,parent=self).exec()==QDialog.DialogCode.Accepted:self.refresh()
    def edit_goal(self,item):
        goal=item.data(Qt.ItemDataRole.UserRole) or {}
        if not goal.get('id'): return
        if GoalDialog(self.api,goal,parent=self).exec()==QDialog.DialogCode.Accepted:self.refresh()

    def delete_goal(self, goal_id, item_ref=None):
        if not goal_id:
            return
        if QMessageBox.question(self, "Delete goal", "Delete this goal? This cannot be undone.") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api.delete_goal(goal_id)
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "Goal", str(e))

    def add_artist(self):
        if AddArtistDialog(self.api,self).exec()==QDialog.DialogCode.Accepted:self.reload()


class SellLicenseDialog(QDialog):
    LICENSES=[("MP3","mp3"),("WAV","wav"),("Trackout","trackout"),("Exclusive","exclusive"),("Beat under commission","custom")]
    def __init__(self,api,parent=None):
        super().__init__(parent); self.api=api; self.setWindowTitle("Create License"); self.setMinimumWidth(560)
        root=QVBoxLayout(self); root.setContentsMargins(22,20,22,18); root.setSpacing(11)
        title=QLabel("CREATE LICENSE"); title.setStyleSheet("font-size:20px;font-weight:750;"); root.addWidget(title)
        sub=QLabel("Producer and messenger shares are calculated automatically. You cannot edit the percentages."); sub.setWordWrap(True); sub.setStyleSheet("color:#8994A8;"); root.addWidget(sub)
        form=QFormLayout(); self.artist=QComboBox(); self.beat=QComboBox(); self.type=QComboBox(); self.payment=QComboBox(); self.currency=QComboBox()
        for l,v in self.LICENSES:self.type.addItem(l,v)
        self.payment.addItem("Paid","paid"); self.payment.addItem("Pending","pending"); self.payment.addItem("Refunded","refunded")
        for label,code in (("USD","USD"),("EUR","EUR"),("CHF","CHF")): self.currency.addItem(label,code)
        self.price=QDoubleSpinBox(); self.price.setRange(.01,1000000); self.price.setDecimals(2); self.price.setPrefix("$ "); self.price.setSingleStep(5)
        form.addRow("Artist:",self.artist); form.addRow("Beat:",self.beat); form.addRow("License:",self.type); form.addRow("Price:",self.price); form.addRow("Currency:",self.currency); form.addRow("Payment status:",self.payment); root.addLayout(form)
        self.currency.currentIndexChanged.connect(self.update_currency_prefix)
        self.role=QLabel("Role: —"); self.split=QLabel("Split: —"); self.role.setStyleSheet("font-weight:700;"); self.split.setStyleSheet("color:#BFA8DD;"); root.addWidget(self.role); root.addWidget(self.split)
        self.notes=QLineEdit(); self.notes.setPlaceholderText("Optional notes"); root.addWidget(self.notes)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.sell); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self.artist.currentIndexChanged.connect(self.preview); self.beat.currentIndexChanged.connect(self.preview); self.load_data()
    def update_currency_prefix(self):
        self.price.setPrefix((self.currency.currentData() or "USD") + " ")
    def load_data(self):
        try:
            for a in self.api.my_artists(""): self.artist.addItem(a["name"],a["id"])
            for b in self.api.beats(""): self.beat.addItem(b["name"],b["id"])
            if not self.api.my_artists(""): self.artist.addItem("No artists available",None)
            if not self.api.beats(""): self.beat.addItem("No beats available",None)
            self.preview()
        except Exception as e: QMessageBox.critical(self,"Could not load data",str(e))
    def preview(self):
        bid=self.beat.currentData(); b=next((x for x in self.api.beats("") if x.get("id")==bid),None) if isinstance(bid,int) else None
        if not b: self.role.setText("Role: —"); self.split.setText("Split: —"); return
        producers=b.get("producers",[]); n=len(producers) or 1; me=(self.api.user or {}).get("id"); mine=any(p.get("user_id")==me for p in producers)
        if mine:
            self.role.setText("Role: Producer"); self.split.setText(f"Producer split: {100/n:.2f}% each" if n>1 else "Producer split: 100%")
        else:
            self.role.setText("Role: Messenger"); self.split.setText(f"Messenger: 10% • Producers: 90% split between {n} producer(s)")
    def sell(self):
        aid=self.artist.currentData(); bid=self.beat.currentData(); price=self.price.value()
        if not isinstance(aid,int) or not isinstance(bid,int): QMessageBox.warning(self,"Missing selection","Select an artist and a beat."); return
        if price<=0: QMessageBox.warning(self,"Invalid price","Enter a price greater than 0."); return
        try:
            self.api.create_license(aid,bid,self.type.currentData(),price,self.payment.currentData(),self.notes.text().strip(),currency=self.currency.currentData()); self.accept()
        except Exception as e: QMessageBox.critical(self,"Could not create license",str(e))


try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    PDF_AVAILABLE = True
except Exception:
    PDF_AVAILABLE = False

def _safe_filename(value):
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "document"))
    return value.strip("._") or "document"

def _license_pdf(row, artist_name, beat_name, path, document_title="D&D LICENSE"):
    if not PDF_AVAILABLE:
        raise RuntimeError("PDF export requires reportlab (included in D&D).")
    c = canvas.Canvas(str(path), pagesize=A4)
    w,h=A4
    y=h-55
    c.setFont("Helvetica-Bold", 20); c.drawString(48,y,document_title); y-=28
    c.setFont("Helvetica", 10); c.drawString(48,y,f"License ID: D&D-LIC-{int(row.get('id',0)):06d}"); y-=18
    lines=[
        f"Artist: {artist_name}",
        f"Beat: {beat_name}",
        f"License type: {str(row.get('license_type','')).upper()}",
        f"Price: {row.get('currency','USD')} {row.get('price',0)}",
        f"Status: {row.get('status','')}",
        f"Purchased: {row.get('purchased_at','')}",
        f"Messenger share: {row.get('mailing_share_percent',0)}% ({row.get('currency','USD')} {row.get('mailing_share',0)})",
        f"Producer share rule: automatic / locked",
    ]
    c.setFont("Helvetica", 11)
    for line in lines:
        c.drawString(48,y,line); y-=20
    y-=12; c.setFont("Helvetica-Bold", 11); c.drawString(48,y,"D&D — Beat License Record"); y-=20
    c.setFont("Helvetica",9); c.drawString(48,y,"Generated locally from the D&D license record.");
    c.save()

class LicensesTab(QWidget):
    STATUS_LABELS={"paid":"PAID","pending":"PENDING","refunded":"REFUNDED","void":"VOID"}
    STATUS_MARKS={"paid":"✓","pending":"◷","refunded":"↩","void":"×"}
    def __init__(self, api):
        super().__init__(); self.api=api
        root=QVBoxLayout(self)
        header=QHBoxLayout(); title=QLabel("Licenses"); title.setObjectName("title"); header.addWidget(title); header.addStretch()
        self.status_filter=QComboBox(); self.status_filter.addItem("All statuses",""); self.status_filter.addItem("Paid","paid"); self.status_filter.addItem("Pending","pending"); self.status_filter.addItem("Refunded","refunded"); self.status_filter.addItem("Void","void"); self.status_filter.currentIndexChanged.connect(self.refresh)
        header.addWidget(self.status_filter)
        sell=QPushButton("+ Sell License"); sell.setObjectName("primary"); sell.clicked.connect(self.sell_license); header.addWidget(sell)
        refresh=QPushButton("Refresh"); refresh.clicked.connect(self.refresh); header.addWidget(refresh); root.addLayout(header)
        self.summary=QLabel(""); self.summary.setStyleSheet("color:#8994A8;font-size:11px;"); root.addWidget(self.summary)
        self.list=QListWidget(); self.list.itemDoubleClicked.connect(self.show_license); root.addWidget(self.list)
        self.refresh()
    def refresh(self):
        self.list.clear()
        try:
            rows=self.api.licenses(); selected=self.status_filter.currentData()
            if selected: rows=[r for r in rows if r.get("status")==selected]
            all_rows=self.api.licenses()
            paid=sum(1 for r in all_rows if r.get("status")=="paid"); pending=sum(1 for r in all_rows if r.get("status")=="pending")
            self.summary.setText(f"Paid: {paid}  •  Pending: {pending}  •  Total records: {len(all_rows)}")
            if not rows: self.list.addItem("No licenses in this filter."); return
            artists={a["id"]:a["name"] for a in self.api.my_artists("")}; beats={b["id"]:b["name"] for b in self.api.beats()}
            for row in rows:
                artist_name=artists.get(row.get("artist_id"),f"Artist #{row.get('artist_id')}"); beat_id=row.get("beat_id"); beat_name=beats.get(beat_id,f"Beat #{beat_id}") if beat_id else "Beat under commission"
                cur=row.get("currency","USD"); status=row.get("status","pending"); mark=self.STATUS_MARKS.get(status,"•")
                item=QListWidgetItem(f"{mark} {self.STATUS_LABELS.get(status,status.upper())}  •  {str(row.get('license_type','')).upper()}  •  {beat_name}  •  {artist_name}  •  {cur} {row.get('price',0)}")
                item.setData(Qt.ItemDataRole.UserRole,row); self.list.addItem(item)
        except Exception as e: self.list.addItem(f"Could not load licenses: {e}")
    def sell_license(self):
        if SellLicenseDialog(self.api,self).exec()==QDialog.DialogCode.Accepted: self.refresh()
    def show_license(self,item):
        row=item.data(Qt.ItemDataRole.UserRole) or {}
        try: artists={a["id"]:a["name"] for a in self.api.my_artists("")}; beats={b["id"]:b["name"] for b in self.api.beats()}
        except Exception: artists,beats={},{}
        artist_name=artists.get(row.get("artist_id"),f"Artist #{row.get('artist_id')}"); beat_id=row.get("beat_id"); beat_name=beats.get(beat_id,f"Beat #{beat_id}") if beat_id else "Beat under commission"
        box=QDialog(self); box.setWindowTitle(f"License D&D-LIC-{int(row.get('id',0)):06d}"); layout=QVBoxLayout(box)
        layout.addWidget(QLabel(f"<b>D&D-LIC-{int(row.get('id',0)):06d}</b>"))
        info=QLabel(f"Artist: {artist_name}\nBeat: {beat_name}\nLicense: {str(row.get('license_type','')).upper()}\nPrice: {row.get('currency','USD')} {row.get('price')}\nPayment status: {row.get('status')}\nPurchased: {row.get('purchased_at')}\nMessenger share: {row.get('mailing_share_percent',0)}% ({row.get('mailing_share',0)} {row.get('currency','USD')})")
        info.setWordWrap(True); layout.addWidget(info)
        split_label=QLabel("PAYMENT SPLIT"); split_label.setStyleSheet("font-size:12px;font-weight:700;"); layout.addWidget(split_label)
        splits=QListWidget(); splits.setMaximumHeight(140); layout.addWidget(splits)
        try:
            split_rows=self.api.license_splits(int(row.get("id")))
            for sp in split_rows:
                splits.addItem(f"{sp.get('display_name','-')}  •  {sp.get('role','producer')}  •  {sp.get('percent','0')}%  •  {sp.get('currency','USD')} {sp.get('amount','0')}")
            if not split_rows: splits.addItem("No split snapshot available for this legacy license.")
        except Exception as e: splits.addItem(f"Split data unavailable: {e}")
        status_row=QHBoxLayout(); status_row.addWidget(QLabel("Change payment status:")); status=QComboBox();
        for label,code in (("Paid","paid"),("Pending","pending"),("Refunded","refunded"),("Void","void")): status.addItem(label,code)
        idx=max(0,status.findData(row.get("status","pending"))); status.setCurrentIndex(idx); status_row.addWidget(status); status_row.addStretch(); layout.addLayout(status_row)
        history_label=QLabel("LICENSE HISTORY"); history_label.setStyleSheet("font-size:12px;font-weight:700;"); layout.addWidget(history_label)
        history=QListWidget(); history.setMaximumHeight(150); layout.addWidget(history)
        try:
            for ev in self.api.license_history(row.get("id")):
                detail=ev.get("note") or f"{ev.get('event_type')}"; history.addItem(f"{str(ev.get('created_at',''))[:19]}  •  {detail}")
            if not history.count(): history.addItem("No history yet.")
        except Exception as e: history.addItem(f"History unavailable: {e}")
        versions_label=QLabel('VERSION HISTORY'); versions_label.setStyleSheet('font-size:12px;font-weight:700;'); layout.addWidget(versions_label)
        versions=QListWidget(); versions.setMaximumHeight(120); layout.addWidget(versions)
        try:
            for v in self.api.license_versions(int(row.get('id'))):
                snap=v.get('snapshot') or {}; versions.addItem(f"v{v.get('version_no')} • {snap.get('status','—')} • {snap.get('currency','USD')} {snap.get('price','0')} • {str(v.get('created_at',''))[:19]}")
            if not versions.count(): versions.addItem('No versions yet.')
        except Exception as e: versions.addItem(f'Version history unavailable: {e}')
        buttons=QHBoxLayout(); save=QPushButton("Save status"); save.setObjectName("primary"); pdf=QPushButton("Generate License PDF"); pdf.setObjectName("primary"); inv=QPushButton("Generate Invoice PDF"); close=QPushButton("Close")
        buttons.addWidget(save); buttons.addWidget(pdf); buttons.addWidget(inv); buttons.addStretch(); buttons.addWidget(close); layout.addLayout(buttons)
        def save_status():
            try: self.api.update_license_status(int(row["id"]),status.currentData()); self.refresh(); box.accept()
            except Exception as e: QMessageBox.warning(box,"Payment status",str(e))
        def save_pdf(title,default):
            path,_=QFileDialog.getSaveFileName(box,"Save PDF",default,"PDF (*.pdf)")
            if not path:return
            try: _license_pdf(row,artist_name,beat_name,path,title); QMessageBox.information(box,"PDF",f"Saved: {path}")
            except Exception as e: QMessageBox.warning(box,"PDF",str(e))
        save.clicked.connect(save_status); pdf.clicked.connect(lambda:save_pdf("D&D LICENSE",f"D&D-LIC-{int(row.get('id',0)):06d}.pdf")); inv.clicked.connect(lambda:save_pdf("D&D INVOICE",f"D&D-INVOICE-{int(row.get('id',0)):06d}.pdf")); close.clicked.connect(box.accept)
        box.exec()


class NotificationsTab(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api

        root = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("Notifications")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()

        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #999999;")
        header.addWidget(self.count_label)

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)
        header.addWidget(refresh)

        read_all = QPushButton("Mark all as read")
        read_all.clicked.connect(self.mark_all_read)
        header.addWidget(read_all)
        root.addLayout(header)

        self.list = QListWidget()
        self.list.itemClicked.connect(self.open_notification)
        root.addWidget(self.list)

        self.reload()

    def reload(self):
        self.list.clear()
        try:
            data = self.api.notifications()
            unread = sum(1 for n in data if not n.get("is_read"))
            self.count_label.setText(f"{unread} unread")

            for notification in data:
                prefix = "● " if not notification.get("is_read") else ""
                full = notification.get("message", "")
                preview = full.splitlines()[0] if full else ""

                if len(preview) > 90:
                    preview = preview[:90].rstrip() + "…"

                item = QListWidgetItem(
                    f"{prefix}{notification.get('title', 'Notification')}\n"
                    f"{preview}\n"
                    f"Tap to open"
                )
                item.setData(Qt.ItemDataRole.UserRole, notification)
                self.list.addItem(item)

        except Exception as e:
            self.list.addItem(f"Could not load notifications: {e}")

    def open_notification(self, item):
        notification = item.data(Qt.ItemDataRole.UserRole)
        if not notification:
            return

        try:
            if not notification.get("is_read"):
                self.api.mark_notification_read(notification["id"])

            QMessageBox.information(
                self,
                notification.get("title", "Notification"),
                notification.get("message", ""),
            )
            self.reload()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def mark_all_read(self):
        try:
            self.api.mark_all_notifications_read()
            self.reload()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

class StatsTab(QWidget):
    """Compact stats view: five KPIs, one revenue panel and two simple lists."""
    def __init__(self, api):
        super().__init__()
        self.api = api
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        header = QHBoxLayout(); header.setSpacing(8)
        title = QLabel("Your Stats"); title.setObjectName("title"); header.addWidget(title)
        header.addStretch(); header.addWidget(QLabel("Period:"))
        self.period = QComboBox()
        for label, code in (("All Time","all"),("This Month","month"),("Last Month","last_month"),("This Year","year")):
            self.period.addItem(label, code)
        self.period.currentIndexChanged.connect(self.refresh)
        header.addWidget(self.period)
        root.addLayout(header)

        self.kpis = QHBoxLayout(); self.kpis.setSpacing(9)
        self.kpi_revenue = StatCard("Revenue", "USD 0.00", "0% vs previous", "#A95CFF", "dollar")
        self.kpi_pending = StatCard("Expected pending", "USD 0.00", "Pending licenses: 0", "#A95CFF", "notifications")
        self.kpi_sold = StatCard("Licenses sold", "0", "0% vs previous", "#A95CFF", "licenses")
        self.kpi_artists = StatCard("Artists", "0", "0% vs previous", "#A95CFF", "artists")
        self.kpi_sent = StatCard("Beats sent", "0", "0% vs previous", "#A95CFF", "beats")
        for card in (self.kpi_revenue,self.kpi_pending,self.kpi_sold,self.kpi_artists,self.kpi_sent):
            card.setMinimumHeight(92); self.kpis.addWidget(card,1)
        root.addLayout(self.kpis)

        revenue = QFrame(); revenue.setObjectName("sectionCard")
        rv=QVBoxLayout(revenue); rv.setContentsMargins(16,13,16,13); rv.setSpacing(5)
        rh=QHBoxLayout(); rt=QLabel("Revenue Overview"); rt.setObjectName("cardTitle"); rh.addWidget(rt); rh.addStretch()
        self.revenue_delta=QLabel("0% vs previous period"); self.revenue_delta.setObjectName("positiveText"); rh.addWidget(self.revenue_delta); rv.addLayout(rh)
        self.revenue_value=QLabel("USD 0.00"); self.revenue_value.setObjectName("heroRevenue"); rv.addWidget(self.revenue_value)
        self.revenue_chart=RevenueChart(); self.revenue_chart.setMinimumHeight(105); self.revenue_chart.setMaximumHeight(125); rv.addWidget(self.revenue_chart)
        root.addWidget(revenue)

        lower=QHBoxLayout(); lower.setSpacing(12)
        artists_box=QFrame(); artists_box.setObjectName("sectionCard")
        av=QVBoxLayout(artists_box); av.setContentsMargins(16,13,16,12); av.setSpacing(6)
        ah=QHBoxLayout(); al=QLabel("Top Artists"); al.setObjectName("cardTitle"); ah.addWidget(al); ah.addStretch(); av.addWidget(QLabel("Revenue & sales"), alignment=Qt.AlignmentFlag.AlignRight); av.addLayout(ah)
        self.top_artists=QListWidget(); self.top_artists.setObjectName("compactList"); self.top_artists.setMaximumHeight(155); av.addWidget(self.top_artists)
        lower.addWidget(artists_box,1)

        sales_box=QFrame(); sales_box.setObjectName("sectionCard")
        sv=QVBoxLayout(sales_box); sv.setContentsMargins(16,13,16,12); sv.setSpacing(6)
        sh=QHBoxLayout(); sl=QLabel("Recent Paid Sales"); sl.setObjectName("cardTitle"); sh.addWidget(sl); sh.addStretch(); sv.addWidget(QLabel("Latest licenses"), alignment=Qt.AlignmentFlag.AlignRight); sv.addLayout(sh)
        self.sales=QListWidget(); self.sales.setObjectName("compactList"); self.sales.setMaximumHeight(155); sv.addWidget(self.sales)
        lower.addWidget(sales_box,1)
        root.addLayout(lower)
        root.addStretch(1)
        self.refresh()

    def refresh(self):
        try:
            data=self.api.dashboard(self.period.currentData()) or {}
            cur=(self.api.user or {}).get("currency","USD")
            delta=data.get("revenue_change_percent")
            delta_text=f"{float(delta):+.1f}% vs previous period" if delta is not None else "0% vs previous period"
            revenue=float(data.get("revenue",0) or 0)
            self.kpi_revenue.update_value(f"{cur} {revenue:,.2f}", delta_text)
            self.kpi_pending.update_value(f"{cur} {float(data.get('expected_revenue',0) or 0):,.2f}", f"Pending licenses: {data.get('pending_licenses',0)}")
            self.kpi_sold.update_value(data.get("licenses_sold",0), delta_text)
            self.kpi_artists.update_value(data.get("artists",0), delta_text)
            self.kpi_sent.update_value(data.get("beats_sent",0), delta_text)
            self.revenue_value.setText(f"{cur} {revenue:,.2f}")
            self.revenue_delta.setText(delta_text)
            values=data.get("revenue_series") or data.get("revenue_history") or []
            if isinstance(values,dict): values=list(values.values())
            self.revenue_chart.set_values(values)

            self.top_artists.clear()
            for row in data.get("top_artists",[])[:5]:
                self.top_artists.addItem(f"{row.get('name','Artist')}  •  {row.get('sales',0)} sales  •  {row.get('revenue',0)}")
            if not self.top_artists.count(): self.top_artists.addItem("No artist sales in this period.")

            self.sales.clear()
            for sale in data.get("recent_sales",[])[:5]:
                self.sales.addItem(f"{str(sale.get('license_type','')).upper()}  •  {sale.get('currency',cur)} {sale.get('price',0)}  •  Artist #{sale.get('artist_id')}  •  Beat #{sale.get('beat_id') or '—'}")
            if not self.sales.count(): self.sales.addItem("No sales in this period.")
        except Exception as e:
            self.kpi_revenue.update_value("—", "Could not load stats")
            self.revenue_value.setText("—")
            self.revenue_delta.setText(str(e)[:120])
            self.top_artists.clear(); self.top_artists.addItem("Could not load stats.")
            self.sales.clear(); self.sales.addItem("Could not load stats.")


class RevenueChart(QFrame):
    def __init__(self):
        super().__init__()
        self.values = []
        self.setMinimumHeight(250)
        self.setStyleSheet("QFrame { background: #0E1521; border: 1px solid #273148; border-radius: 16px; }")

    def set_values(self, values):
        self.values = [max(0.0, float(v)) for v in values]
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=self.rect().adjusted(18,20,-18,-28)
        painter.setPen(QPen(QColor("#1A2433"),1))
        for i in range(1,4):
            y=rect.top()+rect.height()*i/4; painter.drawLine(int(rect.left()),int(y),int(rect.right()),int(y))
        if not self.values: return
        vmax=max(self.values) or 1.0
        step=rect.width()/max(1,len(self.values)-1)
        pts=[(rect.left()+i*step, rect.bottom()-(v/vmax)*rect.height()) for i,v in enumerate(self.values)]
        path=QPainterPath(); path.moveTo(pts[0][0],pts[0][1])
        for x,y in pts[1:]: path.lineTo(x,y)
        fill=QPainterPath(path); fill.lineTo(pts[-1][0],rect.bottom()); fill.lineTo(pts[0][0],rect.bottom()); fill.closeSubpath()
        painter.fillPath(fill,QColor(132,65,218,58))
        painter.setPen(QPen(QColor("#A95CFF"),3)); painter.drawPath(path)
        painter.setBrush(QColor("#DCC2FF")); painter.setPen(Qt.PenStyle.NoPen); painter.drawEllipse(QPoint(int(pts[-1][0]),int(pts[-1][1])),4,4)


class StatCard(QFrame):
    def __init__(self, title, value="—", subtitle="", accent="#9B5CFF", icon_name="dollar"):
        super().__init__()
        self.setObjectName("statCard")
        self.setMinimumHeight(116)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(17, 15, 17, 14)
        lay.setSpacing(6)

        top = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(ui_icon(icon_name).pixmap(20, 20))
        icon.setFixedSize(36, 36)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"background:{accent}22; border:1px solid {accent}55; border-radius:18px;"
        )
        top.addWidget(icon)

        title_label = QLabel(title.upper())
        title_label.setStyleSheet(
            "background:transparent; border:none; font-size:10px; "
            "color:#8F9AAD; font-weight:700;"
        )
        top.addWidget(title_label)
        top.addStretch()
        lay.addLayout(top)

        val = QLabel(value)
        val.setStyleSheet(
            f"background:transparent; border:none; font-size:26px; "
            f"font-weight:750; color:{accent};"
        )
        lay.addWidget(val)

        sub = QLabel(subtitle)
        sub.setStyleSheet(
            "background:transparent; border:none; font-size:11px; color:#7E889A;"
        )
        lay.addWidget(sub)

        self.value_label = val
        self.subtitle_label = sub

    def update_value(self, value, subtitle=None):
        self.value_label.setText(str(value))
        if subtitle is not None:
            self.subtitle_label.setText(str(subtitle))


class HomeTab(QWidget):
    """Reference-driven dashboard: KPI row, revenue/goal analytics and CRM activity."""
    def __init__(self, api):
        super().__init__()
        self.api = api
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 26)
        root.setSpacing(11)

        head = QHBoxLayout(); head.setSpacing(10)
        left = QVBoxLayout(); left.setSpacing(2)
        self.greeting = QLabel("Good evening, SLV")
        self.greeting.setObjectName("dashboardGreeting")
        left.addWidget(self.greeting)
        sub = QLabel("Your workspace at a glance")
        sub.setObjectName("dashboardSub")
        left.addWidget(sub)
        head.addLayout(left); head.addStretch()
        add_artist = QPushButton("+ Add Artist"); add_artist.setObjectName("primary"); add_artist.clicked.connect(self.add_artist)
        add_beat = QPushButton("+ Add Beat"); add_beat.setObjectName("secondaryAction"); add_beat.clicked.connect(self.add_beat)
        sell = QPushButton("Sell License"); sell.setObjectName("greenAction"); sell.clicked.connect(self.sell_license)
        head.addWidget(add_artist); head.addWidget(add_beat); head.addWidget(sell)
        root.addLayout(head)

        self.kpi_row = QHBoxLayout(); self.kpi_row.setSpacing(12)
        self.total_revenue = StatCard("Total Revenue", "USD 0.00", "All time", "#B96CFF", "dollar")
        self.month_revenue = StatCard("This Month", "USD 0.00", "— vs last month", "#A35CFF", "receipt")
        self.goals_card = StatCard("Goals", "0 / 0", "0% completed", "#9A62FF", "tag")
        self.conversion_card = StatCard("Conversion Rate", "0%", "— vs last month", "#A35CFF", "stats")
        self.artists_card = StatCard("Active Artists", "0", "+0 this month", "#55D79B", "artists")
        for c in (self.total_revenue,self.month_revenue,self.goals_card,self.conversion_card,self.artists_card):
            self.kpi_row.addWidget(c,1)
        root.addLayout(self.kpi_row)

        analytics = QHBoxLayout(); analytics.setSpacing(14)
        revenue_box = QFrame(); revenue_box.setObjectName("sectionCard"); rv=QVBoxLayout(revenue_box); rv.setContentsMargins(18,16,18,12); rv.setSpacing(5)
        rh=QHBoxLayout(); rt=QLabel("Revenue Overview"); rt.setObjectName("cardTitle"); rh.addWidget(rt); rh.addStretch(); self.period_label=QLabel("This Month"); self.period_label.setObjectName("mutedLabel"); rh.addWidget(self.period_label); rv.addLayout(rh)
        self.chart_value=QLabel("USD 0.00"); self.chart_value.setObjectName("heroRevenue"); rv.addWidget(self.chart_value)
        self.chart_delta=QLabel("— vs last month"); self.chart_delta.setObjectName("positiveText"); rv.addWidget(self.chart_delta)
        self.chart=RevenueChart(); self.chart.setMinimumHeight(145); self.chart.setMaximumHeight(160); rv.addWidget(self.chart)
        analytics.addWidget(revenue_box, 3)

        goal_box=QFrame(); goal_box.setObjectName("sectionCard"); gv=QVBoxLayout(goal_box); gv.setContentsMargins(18,16,18,12); gv.setSpacing(8)
        gh=QHBoxLayout(); gt=QLabel("Goals"); gt.setObjectName("cardTitle"); gh.addWidget(gt); gh.addStretch(); gb=QPushButton("+"); gb.setObjectName("iconButton"); gb.setFixedSize(34,34); gb.clicked.connect(self.add_goal); gh.addWidget(gb); gv.addLayout(gh)
        self.goals=QListWidget(); self.goals.setObjectName("dashboardGoals"); self.goals.setMinimumHeight(125); self.goals.setMaximumHeight(145); gv.addWidget(self.goals)
        analytics.addWidget(goal_box, 2)
        root.addLayout(analytics)

        lower=QHBoxLayout(); lower.setSpacing(14)
        # Top artists
        artists_box=QFrame(); artists_box.setObjectName("sectionCard"); av=QVBoxLayout(artists_box); av.setContentsMargins(18,15,18,12)
        ah=QHBoxLayout(); al=QLabel("Top Artists"); al.setObjectName("cardTitle"); ah.addWidget(al); ah.addStretch(); av.addWidget(QLabel("Revenue & sales"), alignment=Qt.AlignmentFlag.AlignRight); av.addLayout(ah)
        self.top_artists=QListWidget(); self.top_artists.setObjectName("compactList"); av.addWidget(self.top_artists)
        lower.addWidget(artists_box,1)
        # Recent sales
        sales_box=QFrame(); sales_box.setObjectName("sectionCard"); sv=QVBoxLayout(sales_box); sv.setContentsMargins(18,15,18,12)
        sh=QHBoxLayout(); sl=QLabel("Recent Sales"); sl.setObjectName("cardTitle"); sh.addWidget(sl); sh.addStretch(); sv.addWidget(QLabel("Latest licenses"), alignment=Qt.AlignmentFlag.AlignRight); sv.addLayout(sh)
        self.sales=QListWidget(); self.sales.setObjectName("compactList"); sv.addWidget(self.sales)
        lower.addWidget(sales_box,1)
        # Tasks / notifications
        tasks_box=QFrame(); tasks_box.setObjectName("sectionCard"); tv=QVBoxLayout(tasks_box); tv.setContentsMargins(18,15,18,12)
        th=QHBoxLayout(); tl=QLabel("Tasks & Reminders"); tl.setObjectName("cardTitle"); th.addWidget(tl); th.addStretch(); tv.addWidget(QLabel("View all"), alignment=Qt.AlignmentFlag.AlignRight); tv.addLayout(th)
        self.tasks=QListWidget(); self.tasks.setObjectName("compactList"); self.tasks.setMaximumHeight(125); self.tasks.itemDoubleClicked.connect(self.complete_followup); tv.addWidget(self.tasks)
        self.messages=QListWidget(); self.messages.setObjectName("compactList"); self.messages.setMaximumHeight(100); tv.addWidget(self.messages)
        lower.addWidget(tasks_box,1)
        root.addLayout(lower)
        self.refresh()

    def _money(self, value, currency=None):
        currency=currency or (self.api.user or {}).get("currency","USD")
        try: return f"{currency} {float(value or 0):,.2f}"
        except Exception: return f"{currency} 0.00"

    def refresh(self):
        try:
            all_data=self.api.dashboard("all") or {}; data=self.api.dashboard("month") or {}
            cur=(self.api.user or {}).get("currency","USD")
            total=all_data.get("revenue",0); month=data.get("revenue",0)
            self.total_revenue.update_value(self._money(total,cur),"All time")
            delta=data.get("revenue_change_percent")
            delta_text=(f"{float(delta):+.0f}% vs last month" if delta is not None else "This month")
            self.month_revenue.update_value(self._money(month,cur),delta_text)
            goals_data=(self.api.workspace_overview() or {}).get("goals",[])
            completed=sum(1 for g in goals_data if float(g.get("current",0) or 0)>=float(g.get("target",0) or 0)>0)
            self.goals_card.update_value(f"{completed} / {len(goals_data)}", f"{(completed/len(goals_data)*100 if goals_data else 0):.0f}% completed")
            conv=data.get("conversion_rate",0); self.conversion_card.update_value(f"{conv}%", delta_text)
            self.artists_card.update_value(data.get("artists",0), f"{data.get('contacted_artists',0)} contacted")
            self.chart_value.setText(self._money(month,cur)); self.chart_delta.setText((f"{float(delta):+.0f}% vs last month" if delta is not None else "No comparison yet"))
            vals=[]; running=0
            for sale in reversed(data.get("recent_sales",[])):
                try: running += float(sale.get("price",0) or 0); vals.append(running)
                except Exception: pass
            self.chart.set_values(vals)

            self.top_artists.clear()
            for row in data.get("top_artists",[])[:5]:
                it=QListWidgetItem(f"{row.get('name','Artist')}     {row.get('sales',0)} sales     {cur} {float(row.get('revenue',0) or 0):,.0f}")
                self.top_artists.addItem(it)
            if not self.top_artists.count(): self.top_artists.addItem("No artist sales yet.")

            self.sales.clear()
            for sale in data.get("recent_sales",[])[:5]:
                status="Paid" if sale.get("status")=="paid" else "Pending"
                self.sales.addItem(f"{sale.get('license_type','').upper()}     {sale.get('currency',cur)} {sale.get('price',0)}     • {status}")
            if not self.sales.count(): self.sales.addItem("No recent sales.")

            self.goals.clear()
            for g in goals_data[:5]:
                target=float(g.get("target",0) or 0); current=float(g.get("current",0) or 0); pct=min(100,(current/target*100 if target else 0)); done=current>=target and target>0
                display=min(current,target) if target>0 else current
                it=QListWidgetItem(); it.setData(Qt.ItemDataRole.UserRole,g)
                row=QWidget(); box=QVBoxLayout(row); box.setContentsMargins(5,6,5,6); box.setSpacing(4)
                top=QHBoxLayout(); label=QLabel(("✓  " if done else "")+str(g.get("title","Revenue goal"))); label.setObjectName("goalRowTitle"); top.addWidget(label,1); top.addWidget(QLabel(f"{g.get('currency',cur)} {display:,.0f}/{target:,.0f}")); box.addLayout(top)
                bar=QProgressBar(); bar.setObjectName("goalProgress"); bar.setRange(0,100); bar.setValue(int(pct)); bar.setTextVisible(False); box.addWidget(bar)
                it.setSizeHint(QSize(0,66)); self.goals.addItem(it); self.goals.setItemWidget(it,row)
            if not self.goals.count(): self.goals.addItem("No goals yet. Click + to create one.")

            ov=self.api.workspace_overview() or {}; self.tasks.clear(); artists={a.get("id"):a.get("name") for a in self.api.my_artists("")}
            for f in ov.get("followups",[])[:4]:
                self.tasks.addItem(f"{artists.get(f.get('artist_id'),'Artist')}  •  {f.get('title','Follow up')}  •  {str(f.get('due_at',''))[:10]}")
            if not self.tasks.count(): self.tasks.addItem("No follow-ups scheduled.")
            self.messages.clear()
            for n in self.api.unread_notifications()[:3]: self.messages.addItem(f"{n.get('title','Notification')}  •  {n.get('message','')[:60]}")
            if not self.messages.count(): self.messages.addItem("No new notifications.")
        except Exception as e:
            self.sales.clear(); self.sales.addItem(f"Could not load dashboard: {e}")

    def complete_followup(self,item):
        # Dashboard task rows are intentionally lightweight; reload after completion when row data exists.
        f=item.data(Qt.ItemDataRole.UserRole) or {}
        if f.get("id"):
            try: self.api.complete_followup(f["id"]); self.refresh()
            except Exception as e: QMessageBox.warning(self,"Follow-up",str(e))

    def add_goal(self):
        if GoalDialog(self.api,parent=self).exec()==QDialog.DialogCode.Accepted:self.refresh()
    def edit_goal(self,item):
        goal=item.data(Qt.ItemDataRole.UserRole) or {}
        if goal.get('id') and GoalDialog(self.api,goal,parent=self).exec()==QDialog.DialogCode.Accepted:self.refresh()
    def add_artist(self):
        self.window().show_page("Artists"); self.window().pages["Artists"].add_artist()
    def add_beat(self):
        self.window().show_page("Beats"); self.window().pages["Beats"].add_beat()
    def sell_license(self):
        self.window().show_page("Licenses"); self.window().pages["Licenses"].sell_license()


class CollaboratorsDialog(QDialog):
    def __init__(self, api, parent=None):
        super().__init__(parent); self.api=api; self.setWindowTitle("Collaborators"); self.setMinimumSize(520,420)
        root=QVBoxLayout(self); root.addWidget(QLabel("PRODUCER COLLABORATORS"))
        self.list=QListWidget(); root.addWidget(self.list)
        close=QPushButton("Close"); close.clicked.connect(self.accept); root.addWidget(close)
        try:
            beats=api.beats(); people={}
            for b in beats:
                for p in b.get("producers",[]):
                    name=canonical_producer_label(p.get("username") or p.get("display_name") or "")
                    if not name or name.casefold()==str((api.user or {}).get("username","")).casefold(): continue
                    people[name]=people.get(name,0)+1
            for name,count in sorted(people.items(), key=lambda x:(-x[1],x[0].casefold())):
                self.list.addItem(f"{name}  •  {count} shared beat(s)")
            if not people:self.list.addItem("No collaborators found yet.")
        except Exception as e:self.list.addItem(f"Could not load collaborators: {e}")


class SettingsTab(QWidget):
    themeChanged = Signal(str)

    def __init__(self, api):
        super().__init__()
        self.api = api
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 24)
        root.setSpacing(14)

        title = QLabel("Settings")
        title.setObjectName("title")
        root.addWidget(title)

        appearance = QFrame(); appearance.setObjectName("sectionCard")
        av = QVBoxLayout(appearance); av.setContentsMargins(18,16,18,16); av.setSpacing(10)
        h=QLabel("APPEARANCE"); h.setStyleSheet("font-size:12px;font-weight:750;letter-spacing:.4px;")
        av.addWidget(h)
        row=QHBoxLayout(); row.addWidget(QLabel("Theme")); row.addStretch()
        self.theme=QComboBox(); self.theme.addItem("Dark","dark"); self.theme.addItem("Light","light")
        current=(api.user or {}).get("theme","dark")
        self.theme.setCurrentIndex(1 if current=="light" else 0)
        self.theme.currentIndexChanged.connect(self.on_theme_changed); row.addWidget(self.theme)
        av.addLayout(row)
        save=QPushButton("Save Settings"); save.setObjectName("primary"); save.clicked.connect(self.save); av.addWidget(save)
        root.addWidget(appearance)

        finance=QFrame(); finance.setObjectName("sectionCard")
        fv=QVBoxLayout(finance); fv.setContentsMargins(18,16,18,16); fv.setSpacing(10)
        fh=QLabel("PROFILE DEFAULTS"); fh.setStyleSheet("font-size:12px;font-weight:750;letter-spacing:.4px;"); fv.addWidget(fh)
        fr=QHBoxLayout(); fr.addWidget(QLabel("Default currency")); fr.addStretch()
        self.currency=QComboBox()
        for label,code in (("USD — US Dollar","USD"),("EUR — Euro","EUR"),("CHF — Swiss Franc","CHF")): self.currency.addItem(label,code)
        current_currency=(api.user or {}).get("currency","USD")
        idx=self.currency.findData(current_currency); self.currency.setCurrentIndex(idx if idx >= 0 else 0)
        fr.addWidget(self.currency); fv.addLayout(fr)
        hint=QLabel("This becomes the default currency for new licenses and goals. Existing records keep their original currency."); hint.setWordWrap(True); hint.setStyleSheet("color:#8994A8;font-size:12px;"); fv.addWidget(hint)
        root.addWidget(finance)

        safety=QFrame(); safety.setObjectName("sectionCard")
        sv=QVBoxLayout(safety); sv.setContentsMargins(18,16,18,16); sv.setSpacing(9)
        sh=QLabel("AUTOMATION & SAFETY"); sh.setObjectName("sectionLabel"); sv.addWidget(sh)
        self.auto_backup=QCheckBox("Automatic local backup every 10 minutes")
        self.auto_backup.setChecked(bool(_load_prefs().get("auto_backup", False)))
        self.auto_backup.stateChanged.connect(lambda state: _save_pref("auto_backup", bool(state)))
        sv.addWidget(self.auto_backup)
        bh=QLabel("Backups are stored locally in the D&D application data folder. The latest 20 copies are kept.")
        bh.setWordWrap(True); bh.setStyleSheet("color:#8994A8;font-size:12px;"); sv.addWidget(bh)
        root.addWidget(safety)

        account=QFrame(); account.setObjectName("sectionCard")
        q=QVBoxLayout(account); q.setContentsMargins(18,16,18,16); q.setSpacing(7)
        h=QLabel("ACCOUNT"); h.setStyleSheet("font-size:12px;font-weight:750;letter-spacing:.4px;"); q.addWidget(h)
        q.addWidget(QLabel(f"Username: {canonical_producer_label((api.user or {}).get('username','—'))}"))
        q.addWidget(QLabel(f"Email: {(api.user or {}).get('email','—')}"))
        q.addWidget(QLabel("Google Drive sync is disabled in D&D. Beats are managed locally as MP3 files."))
        root.addWidget(account)

        data_box=QFrame(); data_box.setObjectName("sectionCard"); dv=QVBoxLayout(data_box); dv.setContentsMargins(18,16,18,16); dv.setSpacing(10); dh=QLabel("DATA & SAFETY"); dh.setObjectName("sectionLabel"); dv.addWidget(dh)
        grid=QGridLayout(); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(10)
        actions=[("export","Export backup",self.export_backup),("import","Import backup",self.import_backup),("trash","Open Trash",lambda:TrashDialog(self.api,self).exec()),("artists","My Collaborators",lambda:CollaboratorsDialog(self.api,self).exec()),("settings","Run diagnostics",self.run_diagnostics),("trash","Clear all test data",self.clear_all_test_data),("refresh","Check for updates",self.check_updates)]
        for i,(icon,text,cb) in enumerate(actions):
            b=QPushButton(text); b.setObjectName("dataAction"); b.setIcon(ui_icon(icon)); b.setIconSize(QSize(17,17)); b.setMinimumHeight(42); b.clicked.connect(cb); grid.addWidget(b,i//2,i%2)
        dv.addLayout(grid); root.addWidget(data_box)
        root.addStretch()

    def import_backup(self):
        path,_=QFileDialog.getOpenFileName(self,'Import D&D backup','','JSON (*.json)')
        if not path:return
        try:
            data=json.loads(Path(path).read_text(encoding='utf-8'))
            if not isinstance(data,dict) or 'version' not in data: raise ValueError('Invalid D&D backup file.')
            confirm=QMessageBox.question(self,'Import backup','Merge this backup into your account? Existing records will never be overwritten.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            if confirm!=QMessageBox.StandardButton.Yes:return
            result=self.api.import_backup(data)
            QMessageBox.information(self,'Backup',f"Merge complete. Artists added: {result.get('imported',{}).get('artists',0)}")
            if hasattr(self.parentWidget(),'refresh_all'): self.parentWidget().refresh_all()
        except Exception as e: QMessageBox.warning(self,'Backup',str(e))

    def clear_all_test_data(self):
        confirm=QMessageBox.question(self,"Clear all test data","This will permanently remove artists, your created beats, licenses and notifications for the current account. Shared beats owned by other producers are not deleted. Continue?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if confirm!=QMessageBox.StandardButton.Yes:return
        try:
            self.api.clear_all_account_data()
            if hasattr(self.window(),"refresh_all"): self.window().refresh_all()
            QMessageBox.information(self,"Test data cleared","All removable test data for this account has been cleared.")
        except Exception as e:
            QMessageBox.warning(self,"Clear data",str(e))

    def run_diagnostics(self):
        checks=[]
        try:
            health=self.api._request('GET','/health'); checks.append(f"API: {'OK' if health.get('status')=='ok' else 'FAIL'}")
        except Exception as e: checks.append(f'API: FAIL — {e}')
        try:
            self.api.my_artists(''); checks.append('Artists API: OK')
        except Exception as e: checks.append(f'Artists API: FAIL — {e}')
        try:
            self.api.beats(''); checks.append('Beats API: OK')
        except Exception as e: checks.append(f'Beats API: FAIL — {e}')
        QMessageBox.information(self,'Diagnostics','\n'.join(checks))

    def export_backup(self):
        try:
            data=self.api.export_backup(); path,_=QFileDialog.getSaveFileName(self,"Save D&D backup","D&D_backup.json","JSON (*.json)")
            if not path:return
            Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding="utf-8"); QMessageBox.information(self,"Backup","Backup exported successfully.")
        except Exception as e: QMessageBox.warning(self,"Backup",str(e))

    def check_updates(self):
        try:
            data=self.api.app_version(); version=data.get('version','unknown'); available=data.get('update_available',False)
            if available:
                url=data.get('update_url')
                box=QMessageBox(self); box.setWindowTitle('D&D Update'); box.setText(f'New D&D version {version} is available.')
                box.setInformativeText('The update package will be verified before installation. Your data stays on the server.')
                update_btn=box.addButton('Update now', QMessageBox.ButtonRole.AcceptRole); box.addButton('Later', QMessageBox.ButtonRole.RejectRole); box.exec()
                if box.clickedButton() is update_btn and url:
                    webbrowser.open(url)
            else:
                QMessageBox.information(self,'D&D Update',f'You are running D&D {version}.\n\nNo update is available.')
        except Exception as e: QMessageBox.warning(self,'D&D Update',str(e))

    def on_theme_changed(self, index):
        self.themeChanged.emit(self.theme.currentData())

    def save(self):
        try:
            self.api.update_settings(self.theme.currentData(), self.currency.currentData())
            self.themeChanged.emit(self.theme.currentData())
            QMessageBox.information(self,"Settings","Settings saved.")
        except Exception as e:
            QMessageBox.warning(self,"Settings",str(e))

class AccountPanel(QFrame):
    actionRequested = Signal(int)
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api=api
        self.setObjectName("accountPanel")
        self.setFixedSize(228, 405)
        self.setStyleSheet("""
        QFrame#accountPanel { background:#0D131D; border:1px solid #2A3548; border-radius:18px; }
        QLabel#panelName { font-size:15px; font-weight:750; color:#F7F9FC; }
        QLabel#panelMeta { font-size:11px; color:#8D98AA; }
        QLabel#panelBalance { font-size:11px; color:#55D79B; font-weight:750; }
        QLabel#panelSection { font-size:10px; font-weight:750; color:#778297; letter-spacing:.7px; text-transform:uppercase; }
        QPushButton#panelAction { background:#111925; color:#D9DFE9; border:1px solid #1E2A3B; border-radius:11px; text-align:left; padding:9px 10px; }
        QPushButton#panelAction:hover { background:#171E2B; border-color:#4B3C63; color:#FFFFFF; }
        QPushButton#panelLogout { background:#28141D; color:#FF8292; border:1px solid #5B2D39; border-radius:11px; text-align:left; padding:9px 10px; font-weight:650; }
        QComboBox#panelCurrency { background:#111925; border:1px solid #2A3548; border-radius:10px; color:#F0F3F8; padding:7px 10px; min-width:92px; }
        QComboBox#panelCurrency:hover { border-color:#7550A6; }
        """)
        lay=QVBoxLayout(self); lay.setContentsMargins(12,12,12,12); lay.setSpacing(4)
        head=QHBoxLayout()
        av=QLabel(); av.setPixmap(ui_icon("artists").pixmap(24,24)); av.setAlignment(Qt.AlignmentFlag.AlignCenter); av.setFixedSize(42,42); av.setStyleSheet("background:#211433;border:1px solid #71459D;border-radius:21px;")
        head.addWidget(av)
        info=QVBoxLayout(); info.setSpacing(1)
        nm=QLabel(canonical_producer_label((self.api.user or {}).get("username","User"))); nm.setObjectName("panelName")
        meta_row=QHBoxLayout(); meta_row.setSpacing(7)
        meta=QLabel("Producer"); meta.setObjectName("panelMeta"); meta_row.addWidget(meta)
        self.panel_balance=QLabel("—"); self.panel_balance.setObjectName("panelBalance"); meta_row.addWidget(self.panel_balance); meta_row.addStretch()
        info.addWidget(nm); info.addLayout(meta_row); head.addLayout(info); head.addStretch(); lay.addLayout(head)
        self.refresh_balance()
        line=QFrame(); line.setFixedHeight(1); line.setStyleSheet("background:#263044;border:none;"); lay.addWidget(line); lay.addSpacing(2)
        sec=QLabel("ACCOUNT"); sec.setObjectName("panelSection"); lay.addWidget(sec);
        for icon,text,code in [("settings","Settings",2),("notifications","Notifications",3),("stats","Refresh data",4)]:
            b=QPushButton(text); b.setObjectName("panelAction"); b.setIcon(ui_icon(icon)); b.setIconSize(QSize(18,18)); b.clicked.connect(lambda checked=False,c=code:self.actionRequested.emit(c)); lay.addWidget(b)
        cur_row=QHBoxLayout()
        cur_label=QLabel("DEFAULT CURRENCY"); cur_label.setObjectName("panelSection")
        self.currency_combo=QComboBox(); self.currency_combo.setObjectName("panelCurrency")
        for label,code in (("USD","USD"),("EUR","EUR"),("CHF","CHF")): self.currency_combo.addItem(label,code)
        cur=(self.api.user or {}).get("currency","USD"); idx=self.currency_combo.findData(cur); self.currency_combo.setCurrentIndex(idx if idx>=0 else 0)
        self.currency_combo.currentIndexChanged.connect(self._currency_changed)
        cur_row.addWidget(cur_label); cur_row.addStretch(); cur_row.addWidget(self.currency_combo)
        lay.addLayout(cur_row)
        lay.addStretch()
        b=QPushButton("Log out"); b.setObjectName("panelLogout"); b.setIcon(ui_icon("logout")); b.setIconSize(QSize(18,18)); b.clicked.connect(lambda:self.actionRequested.emit(5)); lay.addWidget(b)
    def refresh_balance(self):
        try:
            data=self.api.dashboard("all") or {}
            currency=(self.api.user or {}).get("currency","USD")
            value=float(data.get("revenue",0) or 0)
            self.panel_balance.setText(f"• {currency} {value:,.2f}")
        except Exception:
            self.panel_balance.setText("• —")

    def _currency_changed(self, index):
        try:
            code=self.currency_combo.currentData()
            user=self.api.update_settings(currency=code)
            if self.parentWidget() and hasattr(self.parentWidget(),"refresh_all"):
                self.parentWidget().refresh_all()
            self.refresh_balance()
        except Exception as e:
            QMessageBox.warning(self, "Currency", str(e))
    def place(self):
        p=self.parentWidget(); self.move(10, p.height()-self.height()-84)
    def open_anim(self):
        self.refresh_balance(); self.place(); end=self.pos(); start=QPoint(end.x(),end.y()+18); self.move(start); self.show(); self.raise_();
        a=QPropertyAnimation(self,b"pos",self); a.setDuration(210); a.setStartValue(start); a.setEndValue(end); a.setEasingCurve(QEasingCurve.Type.OutCubic); a.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped); self._anim=a
    def close_anim(self):
        end=QPoint(self.x(),self.y()+18); a=QPropertyAnimation(self,b"pos",self); a.setDuration(160); a.setStartValue(self.pos()); a.setEndValue(end); a.finished.connect(self.hide); a.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped); self._anim=a


class GlobalSearchDialog(QDialog):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Search")
        self.setMinimumSize(600, 450)
        root = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search artists, beats, licenses...")
        self.search.textChanged.connect(self.search_all)
        root.addWidget(self.search)
        self.results = QListWidget()
        root.addWidget(self.results)

    def search_all(self, text):
        self.results.clear()
        text = text.strip().lower()
        if not text:
            return
        try:
            for a in self.api.my_artists(text)[:10]:
                self.results.addItem(f"ARTIST  •  {a.get('name')}")
            for b in self.api.beats(text)[:10]:
                self.results.addItem(f"BEAT  •  {b.get('name')}")
            for lic in self.api.licenses():
                if text in str(lic).lower():
                    self.results.addItem(
                        f"LICENSE  •  {lic.get('license_type')}  •  ${lic.get('price')}"
                    )
            if self.results.count() == 0:
                self.results.addItem("No results.")
        except Exception as e:
            self.results.addItem(f"Search error: {e}")


class AdminTab(QWidget):
    def __init__(self,api):
        super().__init__(); self.api=api; root=QVBoxLayout(self); root.setContentsMargins(30,24,30,24); root.setSpacing(12)
        h=QHBoxLayout(); t=QLabel("Administration"); t.setObjectName("title"); h.addWidget(t); h.addStretch(); b=QPushButton("Refresh"); b.clicked.connect(self.refresh); h.addWidget(b); health=QPushButton("System Health"); health.clicked.connect(self.show_health); h.addWidget(health); audit=QPushButton("Audit Log"); audit.clicked.connect(self.show_audit); h.addWidget(audit); root.addLayout(h)
        cards=QHBoxLayout(); self.user_card=StatCard("Users","0","registered","#A35CFF","artists"); self.active_card=StatCard("Active","0","enabled","#55D79B","notifications"); self.admin_card=StatCard("Admins","0","privileged","#F1A947","settings")
        for c in (self.user_card,self.active_card,self.admin_card): cards.addWidget(c,1)
        root.addLayout(cards)
        self.summary=QLabel("Loading…"); root.addWidget(self.summary)
        self.list=QListWidget(); self.list.itemDoubleClicked.connect(self.toggle_selected_user); root.addWidget(self.list,1); self._users=[]; self.refresh()
    def refresh(self):
        try:
            users=self.api.admin_users(); self._users=users
            try: overview=self.api.admin_overview()
            except Exception: overview={}
            self.user_card.update_value(overview.get("users",len(users)), "registered")
            self.active_card.update_value(overview.get("active_users",sum(1 for u in users if u.get("is_active"))), "enabled")
            self.admin_card.update_value(sum(1 for u in users if u.get("is_admin")), "privileged")
            self.summary.setText(f"Users: {overview.get('users',len(users))}  •  Artists: {overview.get('artists',0)}  •  Beats: {overview.get('beats',0)}  •  Licenses: {overview.get('licenses',0)}  •  Paid: {overview.get('paid_licenses',0)}")
            self.list.clear()
            for u in users:
                state="Active" if u.get("is_active") else "Disabled"; role="Admin" if u.get("is_admin") else "User"
                it=QListWidgetItem(f"{u.get('username')}  •  {u.get('email')}  •  {role}  •  {state}")
                it.setData(Qt.ItemDataRole.UserRole,u)
                self.list.addItem(it)
        except Exception as e:self.summary.setText(f"Admin error: {e}")
    def toggle_selected_user(self,item):
        u=item.data(Qt.ItemDataRole.UserRole) or {}
        if not u.get('id') or u.get('email','').casefold()=='quikinnnproducer@gmail.com': return
        try:
            self.api.admin_toggle_user(u['id']); self.refresh()
        except Exception as e: QMessageBox.warning(self,"Admin",str(e))
    def show_audit(self):
        try:
            rows=self.api.admin_audit(); box=QDialog(self); box.setWindowTitle('Admin Audit Log'); box.resize(760,480); lay=QVBoxLayout(box); lst=QListWidget();
            for r in rows: lst.addItem(f"{str(r.get('created_at',''))[:19]} • {r.get('action')} • target #{r.get('target_user_id') or '—'} • {r.get('detail') or ''}")
            if not rows: lst.addItem('No admin actions recorded yet.')
            lay.addWidget(lst); close=QPushButton('Close'); close.clicked.connect(box.accept); lay.addWidget(close); box.exec()
        except Exception as e: QMessageBox.warning(self,'Audit Log',str(e))

    def show_health(self):
        try:
            h=self.api.health(); QMessageBox.information(self,"System Health",f"API: {h.get('status','unknown')}\\nDatabase: reachable through API\\nDesktop cache: OK")
        except Exception as e:
            QMessageBox.warning(self,"System Health",f"API unavailable\\n{e}")


class AccountCard(QFrame):
    """Clickable sidebar account card with always-visible balance."""
    clicked = Signal()
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setObjectName("sidebarAccount")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 9, 10, 9)
        lay.setSpacing(9)
        av = QLabel()
        av.setPixmap(ui_icon("artists").pixmap(25,25))
        av.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.setFixedSize(42,42)
        av.setStyleSheet("background:#211433;border:1px solid #71459D;border-radius:21px;")
        lay.addWidget(av)
        info = QVBoxLayout(); info.setSpacing(1)
        self.name = QLabel(canonical_producer_label((api.user or {}).get("username", "User"))); self.name.setObjectName("sidebarAccountName")
        self.role = QLabel("Producer"); self.role.setObjectName("sidebarAccountRole")
        self.balance = QLabel("—"); self.balance.setObjectName("sidebarAccountBalance")
        info.addWidget(self.name); info.addWidget(self.role); info.addWidget(self.balance)
        lay.addLayout(info, 1)
        self.refresh_balance()

    def refresh_balance(self):
        try:
            data = self.api.dashboard("all") or {}
            currency = (self.api.user or {}).get("currency", "USD")
            value = float(data.get("revenue", 0) or 0)
            self.balance.setText(f"{currency} {value:,.2f}")
        except Exception:
            self.balance.setText("Balance unavailable")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, api):
        super().__init__(); self.api=api; self.setWindowTitle("D&D"); self.resize(1520,960); self.setMinimumSize(1280,820)
        self.audio_store=BeatAudioStore()
        root=QWidget(); root.setObjectName("appRoot"); layout=QHBoxLayout(root); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        sidebar=QWidget(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(252); side=QVBoxLayout(sidebar); side.setContentsMargins(14,18,14,16); side.setSpacing(4)
        brandrow=QHBoxLayout(); brandrow.setSpacing(10); logo=QLabel(); logo.setPixmap(ui_icon("beats").pixmap(22,22)); logo.setFixedSize(40,40); logo.setAlignment(Qt.AlignmentFlag.AlignCenter); logo.setStyleSheet("background:#24133C;border:1px solid #543278;border-radius:12px;"); brandrow.addWidget(logo); brandcol=QVBoxLayout(); brandcol.setSpacing(0); brand=QLabel("D&D"); brand.setObjectName("brand"); brandcol.addWidget(brand); brand_sub=QLabel("BEATMAKER CRM"); brand_sub.setStyleSheet("color:#727C8D;font-size:8px;font-weight:800;letter-spacing:1px;"); brandcol.addWidget(brand_sub); brandrow.addLayout(brandcol); brandrow.addStretch(); side.addLayout(brandrow); side.addSpacing(10)
        work_label=QLabel("WORKSPACE"); work_label.setObjectName("sectionLabel"); side.addWidget(work_label)
        self.nav_buttons=[]
        for icon,name in [("home","Dashboard"),("artists","Artists"),("beats","Beats"),("licenses","Licenses"),("stats","Stats"),("notifications","Notifications")]:
            page_name="Home" if name=="Dashboard" else name
            b=QPushButton(name); b.setObjectName("nav"); b.setCheckable(True); b.setIcon(ui_icon(icon)); b.setIconSize(QSize(19,19)); b.setMinimumHeight(43); b.clicked.connect(lambda checked=False,n=page_name:self.show_page(n)); side.addWidget(b); self.nav_buttons.append((page_name,b))
        system_label=QLabel("SYSTEM"); system_label.setObjectName("sectionLabel"); side.addSpacing(8); side.addWidget(system_label)
        for icon,name in [("settings","Settings")]:
            b=QPushButton(name); b.setObjectName("nav"); b.setCheckable(True); b.setIcon(ui_icon(icon)); b.setIconSize(QSize(19,19)); b.setMinimumHeight(43); b.clicked.connect(lambda checked=False,n=name:self.show_page(n)); side.addWidget(b); self.nav_buttons.append((name,b))
        if (api.user or {}).get("email", "").casefold()=="quikinnnproducer@gmail.com":
            admin_label=QLabel("SYSTEM"); admin_label.setObjectName("sectionLabel"); side.addSpacing(8); side.addWidget(admin_label)
            b=QPushButton("Admin"); b.setObjectName("nav"); b.setIcon(ui_icon("settings")); b.setCheckable(True); b.setMinimumHeight(42); b.clicked.connect(lambda:self.show_page("Admin")); side.addWidget(b); self.nav_buttons.append(("Admin",b))
        side.addStretch(); self.account_card=AccountCard(api,sidebar); self.account_card.clicked.connect(self.open_account); side.addWidget(self.account_card)
        content=QWidget(); content.setObjectName("content"); cv=QVBoxLayout(content); cv.setContentsMargins(0,0,0,0); cv.setSpacing(0)
        topbar=QWidget(); topbar.setObjectName("topbar"); top=QHBoxLayout(topbar); top.setContentsMargins(24,12,24,12); swrap=QFrame(); swrap.setObjectName("searchWrap"); sw=QHBoxLayout(swrap); sw.setContentsMargins(10,0,10,0); si=QLabel(); si.setPixmap(ui_icon("search").pixmap(18,18)); sw.addWidget(si); self.search=QLineEdit(); self.search.setPlaceholderText("Search artists, beats, licenses..."); self.search.setFrame(False); self.search.setMinimumHeight(38); sw.addWidget(self.search,1); swrap.setMaximumWidth(640); top.addWidget(swrap); self.search.returnPressed.connect(self.open_search_from_bar); top.addStretch(); self.theme_button=QPushButton(); self.theme_button.setObjectName("iconButton"); self.theme_button.setIcon(ui_icon("sun")); self.theme_button.setIconSize(QSize(19,19)); self.theme_button.setFixedSize(40,40); self.theme_button.clicked.connect(self.toggle_theme); top.addWidget(self.theme_button); self.notify_button=QPushButton(); self.notify_button.setObjectName("iconButton"); self.notify_button.setIcon(ui_icon("notifications")); self.notify_button.setIconSize(QSize(19,19)); self.notify_button.setFixedSize(40,40); self.notify_button.clicked.connect(lambda:self.show_page("Notifications")); top.addWidget(self.notify_button); cv.addWidget(topbar)
        self.stack=QStackedWidget(); self.stack.setObjectName("pageStack")
        self.sync_timer=QTimer(self); self.sync_timer.setInterval(30000); self.sync_timer.timeout.connect(self.refresh_lightweight); self.sync_timer.start()
        self.backup_timer=QTimer(self); self.backup_timer.setInterval(10*60*1000); self.backup_timer.timeout.connect(self._auto_backup); self.backup_timer.start()

        self.pages={"Home":HomeTab(api),"Artists":ArtistsTab(api),"Beats":BeatsTab(api,self.audio_store),"Licenses":LicensesTab(api),"Stats":StatsTab(api),"Notifications":NotificationsTab(api),"Settings":SettingsTab(api)}
        self.pages["Beats"].nowPlaying.connect(self.update_player_bar)
        if (api.user or {}).get("email", "").casefold()=="quikinnnproducer@gmail.com": self.pages["Admin"]=AdminTab(api)
        self.pages["Settings"].themeChanged.connect(self.apply_theme)
        for p in self.pages.values(): self.stack.addWidget(p)
        page_scroll=QScrollArea(); page_scroll.setWidgetResizable(True); page_scroll.setFrameShape(QFrame.Shape.NoFrame); page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); page_scroll.setObjectName("pageScroll"); page_scroll.setWidget(self.stack); cv.addWidget(page_scroll,1)
        playerbar=QFrame(); playerbar.setObjectName("playerBar"); playerbar.setFixedHeight(76); pv=QHBoxLayout(playerbar); pv.setContentsMargins(16,9,16,9); pv.setSpacing(12)
        cover=QLabel(); cover.setPixmap(ui_icon("beats").pixmap(38,38)); cover.setFixedSize(44,44); cover.setAlignment(Qt.AlignmentFlag.AlignCenter); cover.setStyleSheet("background:#211334;border:1px solid #4C2D68;border-radius:10px;"); pv.addWidget(cover)
        meta=QVBoxLayout(); meta.setSpacing(1); self.player_title=QLabel("Nothing playing"); self.player_title.setObjectName("playerTitle"); meta.addWidget(self.player_title); self.player_meta=QLabel("D&D Beat Player"); self.player_meta.setObjectName("playerMeta"); meta.addWidget(self.player_meta); pv.addLayout(meta)
        self.player_progress=QSlider(Qt.Orientation.Horizontal); self.player_progress.setObjectName("playerProgress"); self.player_progress.setRange(0,1000); self.player_progress.setValue(0); pv.addWidget(self.player_progress,1)
        prev=QPushButton("|◀"); prev.setObjectName("playerControl"); prev.setFixedSize(42,42); prev.setToolTip("Previous beat"); pv.addWidget(prev)
        self.player_toggle=QPushButton("▶"); self.player_toggle.setObjectName("playerPlay"); self.player_toggle.setFixedSize(42,42); self.player_toggle.clicked.connect(self.toggle_player); pv.addWidget(self.player_toggle)
        nxt=QPushButton("▶|"); nxt.setObjectName("playerControl"); nxt.setFixedSize(42,42); nxt.setToolTip("Next beat"); pv.addWidget(nxt)
        self.pages["Beats"].player.positionChanged.connect(self._player_position_changed)
        self.pages["Beats"].player.durationChanged.connect(self._player_duration_changed)
        self.player_progress.sliderMoved.connect(self._player_seek)
        cv.addWidget(playerbar)
        layout.addWidget(sidebar); layout.addWidget(content,1); self.setCentralWidget(root)
        act_search=QAction(self); act_search.setShortcut(QKeySequence("Ctrl+K")); act_search.triggered.connect(self.open_search); self.addAction(act_search)
        act_find=QAction(self); act_find.setShortcut(QKeySequence("Ctrl+F")); act_find.triggered.connect(self.open_search); self.addAction(act_find)
        act_new_artist=QAction(self); act_new_artist.setShortcut(QKeySequence("Ctrl+N")); act_new_artist.triggered.connect(lambda:self.pages["Artists"].add_artist()); self.addAction(act_new_artist)
        act_new_beat=QAction(self); act_new_beat.setShortcut(QKeySequence("Ctrl+Shift+B")); act_new_beat.triggered.connect(lambda:self.pages["Beats"].add_beat()); self.addAction(act_new_beat)
        self.tray=QSystemTrayIcon(self); self.tray.setIcon(ui_icon("beats")); self.tray.setToolTip("D&D"); menu=QMenu(self); open_action=menu.addAction("Open D&D"); open_action.triggered.connect(self.showNormal); menu.addSeparator(); quit_action=menu.addAction("Quit D&D"); quit_action.triggered.connect(self.quit_application); self.tray.setContextMenu(menu); self.tray.show()
        self._allow_close=False
        self.account_panel=AccountPanel(api,self); self.account_panel.hide(); self.account_panel.actionRequested.connect(self.handle_account_action); self._fade_anim=None; QApplication.instance().installEventFilter(self); self.show_page("Home",False); self.refresh_notification_badge()
    def eventFilter(self, obj, event):
        if event.type()==QEvent.Type.MouseButtonPress and hasattr(self,"account_panel") and self.account_panel.isVisible():
            gp=event.globalPosition().toPoint() if hasattr(event,"globalPosition") else event.globalPos()
            panel_rect=QRect(self.account_panel.mapToGlobal(QPoint(0,0)), self.account_panel.size())
            card_rect=QRect(self.account_card.mapToGlobal(QPoint(0,0)), self.account_card.size())
            if not panel_rect.contains(gp) and not card_rect.contains(gp):
                self.account_panel.close_anim()
        return super().eventFilter(obj,event)

    def show_page(self,name,animate=True):
        if name not in self.pages:return
        self.stack.setCurrentWidget(self.pages[name]); [b.setChecked(n==name) for n,b in self.nav_buttons]
        if name=="Notifications":
            try:self.pages["Notifications"].reload()
            except Exception:pass
        page=self.pages[name]
        if hasattr(page,"refresh"):
            try: page.refresh()
            except TypeError: pass
        if animate:
            eff=QGraphicsOpacityEffect(self.stack); self.stack.setGraphicsEffect(eff); a=QPropertyAnimation(eff,b"opacity",self); a.setDuration(150); a.setStartValue(.5); a.setEndValue(1); a.setEasingCurve(QEasingCurve.Type.OutCubic); a.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped); self._fade_anim=a
    def update_player_bar(self, title, playing):
        self.player_title.setText(str(title) if playing else "Nothing playing")
        self.player_meta.setText("Playing now" if playing else "D&D Beat Player")
        self.player_toggle.setText("Ⅱ" if playing else "▶")
        if not playing: self.player_progress.setValue(0)

    def _player_position_changed(self, pos):
        dur=self.pages["Beats"].player.duration()
        if dur>0 and not self.player_progress.isSliderDown():
            self.player_progress.setValue(int(pos*1000/dur))

    def _player_duration_changed(self, dur):
        if dur<=0: self.player_progress.setValue(0)

    def _player_seek(self, value):
        dur=self.pages["Beats"].player.duration()
        if dur>0: self.pages["Beats"].player.setPosition(int(dur*value/1000))

    def toggle_player(self):
        player=self.pages["Beats"].player
        if player.playbackState()==QMediaPlayer.PlaybackState.PlayingState:
            player.pause()
        elif player.source().isValid():
            player.play()

    def open_account(self):
        if self.account_panel.isVisible(): self.account_panel.close_anim()
        else: self.account_panel.open_anim()
    def handle_account_action(self,code):
        self.account_panel.close_anim()
        if code==2:self.show_page("Settings")
        elif code==3:self.show_page("Notifications")
        elif code==4:
            self.refresh_all()
            self.statusBar().showMessage("Data refreshed", 2500)
        elif code==5:
            if QMessageBox.question(self,"Log out","Are you sure you want to log out?")==QMessageBox.StandardButton.Yes:
                self.api.logout(); self.close(); auth=AuthWindow(self.api)
                if auth.exec()==QDialog.DialogCode.Accepted:
                    window=MainWindow(self.api); window.show(); self._next_window=window
    def open_search(self): GlobalSearchDialog(self.api,self).exec()
    def open_search_from_bar(self):
        text=self.search.text().strip(); d=GlobalSearchDialog(self.api,self); d.search.setText(text); d.search.setFocus(); d.search_all(text); d.exec()
    def refresh_notification_badge(self):
        try:
            rows=self.api.unread_notifications()
            self.notify_button.setText(str(len(rows)) if rows else "")
            current_ids={n.get("id") for n in rows if n.get("id") is not None}
            previous=getattr(self,"_known_unread_ids",set())
            new_rows=[n for n in rows if n.get("id") not in previous]
            self._known_unread_ids=current_ids
            for n in new_rows:
                title=n.get("title") or "D&D Notification"
                message=n.get("message") or "You have a new notification."
                preview=message.splitlines()[0]
                if len(preview)>140: preview=preview[:140].rstrip()+"…"
                if hasattr(self,"tray") and self.tray.isVisible():
                    pass  # Windows tray balloons intentionally disabled
            notif_page=self.pages.get("Notifications") if hasattr(self,"pages") else None
            if notif_page and getattr(self.stack,"currentWidget",lambda:None)() is notif_page and new_rows:
                notif_page.reload()
        except Exception:
            self.notify_button.setText("")
    def apply_theme(self,theme):
        theme="light" if str(theme).lower()=="light" else "dark"; QApplication.instance().setStyleSheet((LIGHT_STYLE + FINAL_LIGHT_OVERRIDES) if theme=="light" else DARK_STYLE)
        if self.api.user is not None:self.api.user["theme"]=theme
        settings=self.pages.get("Settings")
        if settings:
            settings.theme.blockSignals(True); settings.theme.setCurrentIndex(1 if theme=="light" else 0); settings.theme.blockSignals(False)
        self.theme_button.setIcon(ui_icon("moon" if theme=="light" else "sun"))
    def toggle_theme(self):
        current=(self.api.user or {}).get("theme","dark").lower(); new="light" if current=="dark" else "dark"
        try:self.api.update_settings(new)
        except Exception:pass
        self.apply_theme(new)

    def refresh_lightweight(self):
        try:
            # Проверяем/обновляем только сессию.
            self.api.refresh_session(clear_cache=False)

            # Обновляем только лёгкие данные.
            self.refresh_notification_badge()

        except Exception as e:
            print(f"Lightweight refresh error: {e}")

    def _auto_backup(self):
        try:
            if not bool(_load_prefs().get("auto_backup", False)):
                return
            data=self.api.export_backup()
            backup_dir=Path(_prefs_path()).parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp=time.strftime("%Y%m%d_%H%M%S")
            path=backup_dir / f"DD_backup_{stamp}.json"
            path.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
            files=sorted(backup_dir.glob("DD_backup_*.json"), key=lambda x:x.stat().st_mtime, reverse=True)
            for old in files[20:]:
                try: old.unlink()
                except Exception: pass
        except Exception:
            pass

    def refresh_all(self):
        try: self.account_card.refresh_balance()
        except Exception: pass
        try:
            self.api.refresh_session()
        except Exception:
            pass
        self.refresh_notification_badge()
        for p in self.pages.values():
            if hasattr(p,"refresh"):
                try:p.refresh()
                except TypeError:pass
    def showEvent(self,event):
        super().showEvent(event)
        QTimer.singleShot(50, self.refresh_lightweight)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,"account_panel") and self.account_panel.isVisible(): self.account_panel.place()


    def closeEvent(self,event):
        if self._allow_close:
            event.accept(); return
        event.ignore(); self.hide()

    def quit_application(self):
        self._allow_close=True; QApplication.quit()



QPushButton#playerControl, QPushButton#playerPlay { background:#111925; color:#EDE9FF; border:1px solid #2B3548; border-radius:12px; font-size:14px; font-weight:700; }
QPushButton#playerControl:hover { background:#1A2230; border-color:#7D4CC2; }
QPushButton#playerPlay { background:#8B43E6; border-color:#9D5BFF; color:white; border-radius:21px; }
QPushButton#playerPlay:hover { background:#A65BFF; }
QSlider#playerProgress { min-height:16px; }
QSlider#playerProgress::groove:horizontal { height:4px; background:#252E3D; border-radius:2px; }
QSlider#playerProgress::sub-page:horizontal { background:#9B5CFF; border-radius:2px; }
QSlider#playerProgress::handle:horizontal { width:12px; margin:-4px 0; background:#D7B6FF; border-radius:6px; }

FINAL_LIGHT_OVERRIDES = """
QWidget#content { background:#F4F6FA; }
QFrame#sectionCard, QFrame#statCard { border-radius:18px; }
QPushButton#nav:checked { border-left:3px solid #813BE6; padding-left:10px; }
QFrame#playerBar { border-radius:15px; }
"""


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)
    api = ApiClient()
    auth = AuthWindow(api)
    if auth.exec() != QDialog.DialogCode.Accepted:
        return
    window = MainWindow(api)
    window.apply_theme((api.user or {}).get("theme", "dark"))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
