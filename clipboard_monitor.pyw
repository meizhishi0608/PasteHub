# -*- coding: utf-8 -*-
"""
剪贴板记录应用 v3 —— 紧凑布局 + 日历选日
记录每天复制到剪贴板的文本与截图，数据保存在 D:\jianjieban\data。
日历点击某一天查看当天记录；双击记录可重新复制。
"""
import ctypes
import ctypes.wintypes as wintypes
import hashlib
import io
import json
import os
import struct
import sys
import tkinter as tk
from calendar import monthrange
from datetime import datetime
from tkinter import ttk, font as tkfont

from PIL import Image, ImageTk

# ---------------- Windows API ----------------
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.restype = wintypes.BOOL
user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
user32.RegisterClipboardFormatW.restype = wintypes.UINT
user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
user32.SetWindowTextW.restype = wintypes.BOOL
user32.GetDpiForSystem.restype = ctypes.c_uint

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalSize.restype = ctypes.c_size_t
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE

CF_UNICODETEXT = 13
CF_DIB = 8
CF_DIBV5 = 17
GMEM_MOVEABLE = 0x0002
ERROR_ALREADY_EXISTS = 183
APP_TITLE = '剪贴板记录'
MUTEX_NAME = 'Local\\ClipboardRecorder_Jianjieban'

# ---------------- 配色与字体（Apple 风格） ----------------
COL_PAGE = '#f5f5f7'
COL_CARD = '#ffffff'
COL_BORDER = '#e9e9ee'
COL_TEXT = '#1d1d1f'
COL_SUB = '#6e6e73'
COL_ACCENT = '#0071e3'
COL_ACCENT_HOVER = '#0077ed'
COL_ACCENT_PRESS = '#0062c4'
COL_HOVER = '#f2f2f7'
COL_SELECT = '#e8f0fe'
COL_OK = '#34c759'
COL_WARN = '#ff9f0a'
FONT = 'Microsoft YaHei UI'
FONT_LATIN = 'Segoe UI'
FONT_TITLE = 'Segoe UI Semibold'


def _info(text):
    user32.MessageBoxW(None, text, APP_TITLE, 0x40)


def _warn(text):
    user32.MessageBoxW(None, text, APP_TITLE, 0x30)


def _ask_yes_no(text):
    return user32.MessageBoxW(None, text, APP_TITLE, 0x24) == 6


def _enable_dpi():
    """开启系统 DPI 感知，让文字按显示器原生分辨率渲染（更清晰锐利）"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def _dpi_scale():
    try:
        dpi = user32.GetDpiForSystem()
    except Exception:
        dpi = 96
    if not dpi or dpi <= 0:
        dpi = 96
    return max(1.0, min(3.0, dpi / 96.0))
# ---------------- 剪贴板读写 ----------------
def _read_global(h):
    if not h:
        return None
    ptr = kernel32.GlobalLock(h)
    if not ptr:
        return None
    try:
        size = kernel32.GlobalSize(h)
        if size <= 0:
            return None
        buf = ctypes.create_string_buffer(size)
        ctypes.memmove(buf, ptr, size)
        return buf.raw
    finally:
        kernel32.GlobalUnlock(h)


def _alloc_global(data):
    h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not h:
        return None
    ptr = kernel32.GlobalLock(h)
    if not ptr:
        kernel32.GlobalFree(h)
        return None
    try:
        ctypes.memmove(ptr, data, len(data))
    finally:
        kernel32.GlobalUnlock(h)
    return h


def get_clipboard_text():
    """读取剪贴板文本，没有则返回 None"""
    try:
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None
        if not user32.OpenClipboard(None):
            return None
        try:
            raw = _read_global(user32.GetClipboardData(CF_UNICODETEXT))
        finally:
            user32.CloseClipboard()
        if not raw:
            return None
        text = raw.decode('utf-16-le', errors='replace').rstrip('\x00')
        return text or None
    except Exception:
        return None


def get_clipboard_image():
    """读取剪贴板图片，返回 (原始字节, 格式)；格式为 'png' 或 'dib'，没有则 (None, None)"""
    try:
        png_fmt = user32.RegisterClipboardFormatW('PNG')
        if png_fmt and user32.IsClipboardFormatAvailable(png_fmt):
            if user32.OpenClipboard(None):
                try:
                    raw = _read_global(user32.GetClipboardData(png_fmt))
                finally:
                    user32.CloseClipboard()
                if raw and raw[:8] == b'\x89PNG\r\n\x1a\n':
                    return raw, 'png'
        for fmt in (CF_DIBV5, CF_DIB):
            if user32.IsClipboardFormatAvailable(fmt):
                if user32.OpenClipboard(None):
                    try:
                        raw = _read_global(user32.GetClipboardData(fmt))
                    finally:
                        user32.CloseClipboard()
                    if raw and len(raw) > 40:
                        return raw, 'dib'
        return None, None
    except Exception:
        return None, None


def set_clipboard_text(text):
    data = text.encode('utf-16-le') + b'\x00\x00'
    h = _alloc_global(data)
    if not h:
        return False
    if not user32.OpenClipboard(None):
        kernel32.GlobalFree(h)
        return False
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(CF_UNICODETEXT, h):
            kernel32.GlobalFree(h)
            return False
        return True
    finally:
        user32.CloseClipboard()


def pil_to_dib_bytes(img):
    buf = io.BytesIO()
    work = img.convert('RGBA') if img.mode not in ('RGB', 'RGBA') else img
    work.save(buf, 'BMP')
    return buf.getvalue()[14:]  # 去掉 BITMAPFILEHEADER


def set_clipboard_image_pil(img):
    """把图片放回剪贴板：同时写入 PNG 与 DIB 两种格式，方便各种软件粘贴"""
    try:
        png_buf = io.BytesIO()
        img.save(png_buf, 'PNG')
        png = png_buf.getvalue()
        dib = pil_to_dib_bytes(img)
        if not user32.OpenClipboard(None):
            return False
        try:
            user32.EmptyClipboard()
            ok = False
            png_fmt = user32.RegisterClipboardFormatW('PNG')
            if png_fmt:
                h = _alloc_global(png)
                if h:
                    if user32.SetClipboardData(png_fmt, h):
                        ok = True
                    else:
                        kernel32.GlobalFree(h)
            h2 = _alloc_global(dib)
            if h2:
                if user32.SetClipboardData(CF_DIB, h2):
                    ok = True
                else:
                    kernel32.GlobalFree(h2)
            return ok
        finally:
            user32.CloseClipboard()
    except Exception:
        return False


def dib_to_pil(data):
    """把 DIB 位图字节转成 PIL Image，失败返回 None"""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        return img
    except Exception:
        pass
    try:
        if len(data) < 40:
            return None
        bi_size = struct.unpack_from('<I', data, 0)[0]
        if bi_size < 40:
            return None
        width = struct.unpack_from('<i', data, 4)[0]
        height = struct.unpack_from('<i', data, 8)[0]
        bitcount = struct.unpack_from('<H', data, 14)[0]
        compression = struct.unpack_from('<I', data, 16)[0]
        if width <= 0 or height == 0:
            return None
        topdown = height < 0
        height = abs(height)
        if bitcount not in (24, 32) or compression not in (0, 3):
            return None
        stride = ((width * bitcount + 31) // 32) * 4
        px_start = bi_size + (16 if compression == 3 else 0)
        raw = data[px_start:px_start + stride * height]
        if len(raw) < stride * height:
            return None
        mode = 'BGR' if bitcount == 24 else 'BGRA'
        img = Image.frombytes('RGB' if bitcount == 24 else 'RGBA', (width, height), raw, 'raw', mode)
        if not topdown:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        return img
    except Exception:
        return None


# ---------------- 数据存储 ----------------
class Store:
    def __init__(self, data_dir, max_text_len=200000):
        self.data_dir = data_dir
        self.max_text_len = max_text_len
        self.text_dir = os.path.join(data_dir, 'text')
        self.img_dir = os.path.join(data_dir, 'images')
        self.thumb_dir = os.path.join(data_dir, 'thumbs')
        self.index_dir = os.path.join(data_dir, 'index')
        for d in (self.text_dir, self.img_dir, self.thumb_dir, self.index_dir):
            os.makedirs(d, exist_ok=True)

    @staticmethod
    def today():
        return datetime.now().strftime('%Y-%m-%d')

    def index_path(self, date):
        return os.path.join(self.index_dir, date + '.json')

    def load_entries(self, date):
        p = self.index_path(date)
        if not os.path.exists(p):
            return []
        try:
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f).get('entries', [])
        except Exception:
            return []

    def save_entries(self, date, entries):
        tmp = self.index_path(date) + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'date': date, 'entries': entries}, f, ensure_ascii=False)
        os.replace(tmp, self.index_path(date))

    def all_dates(self):
        dates = []
        try:
            for name in os.listdir(self.index_dir):
                if name.endswith('.json'):
                    dates.append(name[:-5])
        except Exception:
            pass
        return sorted(dates)

    def add_text(self, text):
        if len(text) > self.max_text_len:
            text = text[:self.max_text_len] + '\n...[内容过长，已截断]'
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        date = ts[:10]
        sig = hashlib.sha1(text.encode('utf-8', errors='replace')).hexdigest()
        preview = ' '.join(text.split())[:120]
        entry = {
            'date': date, 'ts': ts, 'type': 'text',
            'content': text, 'preview': preview, 'sig': sig,
            'id': hashlib.sha1(('text|' + ts + '|' + sig).encode('utf-8')).hexdigest()[:16],
        }
        entries = self.load_entries(date)
        if entries and entries[-1].get('type') == 'text' and entries[-1].get('sig') == sig:
            return None  # 与上一条相同，跳过
        entries.append(entry)
        self.save_entries(date, entries)
        try:
            with open(os.path.join(self.text_dir, date + '.txt'), 'a', encoding='utf-8') as f:
                f.write('[%s]\n%s\n%s\n\n' % (ts, '-' * 44, text))
        except Exception:
            pass
        return entry

    def add_image(self, raw, kind):
        try:
            if kind == 'png':
                img = Image.open(io.BytesIO(raw))
                img.load()
            else:
                img = dib_to_pil(raw)
            if img is None:
                return None
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            date = ts[:10]
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            h = hashlib.sha1(raw).hexdigest()[:6]
            sig = hashlib.sha1(raw).hexdigest()
            name = '%s_%s.png' % (stamp, h)
            rel_img = 'images/%s/%s' % (date, name)
            rel_thumb = 'thumbs/%s/%s' % (date, name)
            day_img = os.path.join(self.data_dir, rel_img)
            day_thumb = os.path.join(self.data_dir, rel_thumb)
            os.makedirs(os.path.dirname(day_img), exist_ok=True)
            os.makedirs(os.path.dirname(day_thumb), exist_ok=True)
            img.save(day_img, 'PNG')
            thumb = img.copy()
            thumb.thumbnail((520, 520))
            thumb.save(day_thumb, 'PNG')
            entry = {
                'date': date, 'ts': ts, 'type': 'image', 'sig': sig,
                'file': rel_img, 'thumb': rel_thumb,
                'preview': '截图 %dx%d' % (img.width, img.height),
                'id': hashlib.sha1(('image|' + ts + '|' + name).encode('utf-8')).hexdigest()[:16],
            }
            entries = self.load_entries(date)
            if entries and entries[-1].get('type') == 'image' and entries[-1].get('sig') == sig:
                return None  # 与上一条相同，跳过
            entries.append(entry)
            self.save_entries(date, entries)
            return entry
        except Exception:
            return None

    def delete_entry(self, eid, date):
        entries = self.load_entries(date)
        removed = None
        keep = []
        for e in entries:
            if e.get('id') == eid:
                removed = e
            else:
                keep.append(e)
        self.save_entries(date, keep)
        if removed and removed.get('type') == 'image':
            for key in ('file', 'thumb'):
                p = os.path.join(self.data_dir, removed.get(key, ''))
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass

    def clear_day(self, date):
        entries = self.load_entries(date)
        for e in entries:
            if e.get('type') == 'image':
                for key in ('file', 'thumb'):
                    p = os.path.join(self.data_dir, e.get(key, ''))
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception:
                        pass
        try:
            if os.path.exists(self.index_path(date)):
                os.remove(self.index_path(date))
        except Exception:
            pass


# ---------------- 剪贴板监听 ----------------
class Watcher:
    def __init__(self, store, interval_ms=700, on_new=None):
        self.store = store
        self.interval_ms = interval_ms
        self.on_new = on_new
        self.paused = False
        try:
            self.last_seq = user32.GetClipboardSequenceNumber()
        except Exception:
            self.last_seq = 0

    def poll(self):
        try:
            seq = user32.GetClipboardSequenceNumber()
        except Exception:
            return
        if seq != self.last_seq:
            self.last_seq = seq
            self.capture()

    def sync(self):
        """应用自己把内容放回剪贴板后调用，避免被当作新复制重复记录"""
        try:
            self.last_seq = user32.GetClipboardSequenceNumber()
        except Exception:
            pass

    def capture(self):
        if self.paused:
            return
        try:
            text = get_clipboard_text()
            if text:
                t = text.strip()
                if t:
                    entry = self.store.add_text(t)
                    if entry and self.on_new:
                        self.on_new(entry)
        except Exception:
            pass
        try:
            raw, kind = get_clipboard_image()
            if raw:
                entry = self.store.add_image(raw, kind)
                if entry and self.on_new:
                    self.on_new(entry)
        except Exception:
            pass

# ---------------- UI 组件（Apple 风格） ----------------
def _round_rect(canvas, x1, y1, x2, y2, r, **kw):
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, splinesteps=30, **kw)


class AppleButton(tk.Canvas):
    """圆角按钮：带平滑悬停变色与按压缩放效果"""
    KINDS = {
        'primary':   dict(fill=(0, 113, 227), hover=(0, 119, 237), press=(0, 98, 196), text='#ffffff', outline=(0, 113, 227)),
        'secondary': dict(fill=(255, 255, 255), hover=(242, 242, 247), press=(228, 228, 234), text='#1d1d1f', outline=(214, 214, 219)),
        'danger':    dict(fill=(255, 255, 255), hover=(253, 240, 240), press=(251, 227, 227), text='#d70015', outline=(231, 214, 214)),
    }
    DISABLED = dict(fill=(246, 246, 248), hover=(246, 246, 248), press=(246, 246, 248), text='#bbbbc2', outline=(233, 233, 237))

    def __init__(self, master, text, command=None, kind='secondary', height=34, padx=16,
                 font=None, bg=None):
        parent_bg = bg if bg is not None else master.cget('bg')
        super().__init__(master, bg=parent_bg, highlightthickness=0, bd=0, cursor='hand2')
        self.text = text
        self.command = command
        self.kind = kind
        self.height = height
        self.padx = padx
        self.font = font or (FONT_LATIN, 10)
        self.enabled = True
        self._inside = False
        self._pressed = False
        self._job = None
        self._cur = None
        self._tgt = None
        f = tkfont.Font(font=self.font)
        w = int(f.measure(text) + padx * 2 + 2)
        self.configure(width=w, height=height)
        self._rect = _round_rect(self, 0.5, 0.5, w - 0.5, height - 0.5, height / 2 - 0.5,
                                 fill='', outline='', width=1)
        self._txt = self.create_text(w / 2, height / 2, text=text, font=self.font)
        self._set_instant()
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<ButtonPress-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)

    def _colors(self):
        return self.KINDS[self.kind] if self.enabled else self.DISABLED

    def _paint(self, cd):
        self.itemconfigure(self._rect, fill='#%02x%02x%02x' % cd['fill'],
                           outline='#%02x%02x%02x' % cd['outline'])
        self.itemconfigure(self._txt, fill=cd['text'])

    def _set_instant(self):
        c = self._colors()
        self._cur = c['fill']
        self._tgt = c
        self._paint(c)

    def _press_paint(self):
        c = self._colors()
        self._paint(dict(c, fill=c['press']))

    def _animate_to(self, target):
        if self._job:
            self.after_cancel(self._job)
        self._tgt = target
        self._job = self.after(12, self._tick)

    def _tick(self):
        self._job = None
        t = self._tgt['fill']
        c = self._cur if self._cur else t
        new = tuple(round(a + (b - a) * 0.4) for a, b in zip(c, t))
        self._cur = new
        if max(abs(a - b) for a, b in zip(new, t)) <= 1:
            self._cur = t
            self._paint(self._tgt)
        else:
            self._paint(dict(self._tgt, fill=new))
            self._job = self.after(12, self._tick)

    def _on_enter(self, _e):
        self._inside = True
        if self.enabled and not self._pressed:
            self._animate_to(self._colors())

    def _on_leave(self, _e):
        self._inside = False
        if self.enabled and not self._pressed:
            self._animate_to(self._colors())

    def _on_press(self, _e):
        if not self.enabled:
            return
        self._pressed = True
        self._press_paint()

    def _on_release(self, _e):
        if not self.enabled:
            return
        was = self._pressed
        self._pressed = False
        if was and self._inside and self.command:
            self.command()
        self._animate_to(self._colors())

    def set_state(self, enabled):
        self.enabled = enabled
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        self.configure(cursor='hand2' if enabled else 'arrow')
        self._set_instant()

    def set_text(self, text):
        self.text = text
        f = tkfont.Font(font=self.font)
        w = int(f.measure(text) + self.padx * 2 + 2)
        self.configure(width=w)
        self.delete(self._rect)
        self._rect = _round_rect(self, 0.5, 0.5, w - 0.5, self.height - 0.5, self.height / 2 - 0.5,
                                 fill='', outline='', width=1)
        self.itemconfigure(self._txt, text=text)
        self.coords(self._txt, w / 2, self.height / 2)
        self._set_instant()


class AppleCard(tk.Canvas):
    """圆角白色卡片容器"""

    def __init__(self, master, radius=16, fill=COL_CARD, outline=COL_BORDER, pad=16,
                 bg=None, width=None, height=None):
        parent_bg = bg if bg is not None else master.cget('bg')
        super().__init__(master, bg=parent_bg, highlightthickness=0, bd=0)
        self.radius = radius
        self.fill = fill
        self.outline = outline
        self.pad = pad
        self.body = tk.Frame(self, bg=fill)
        self._win = self.create_window(0, 0, anchor='nw', window=self.body)
        if width:
            self.configure(width=width)
        if height:
            self.configure(height=height)
        self.bind('<Configure>', self._redraw)
        self._redraw()

    def _redraw(self, _e=None):
        self.delete('bg')
        w = self.winfo_width()
        h = self.winfo_height()
        if w > 4 and h > 4:
            _round_rect(self, 1, 1, w - 1, h - 1, self.radius,
                        fill=self.fill, outline=self.outline, width=1, tags='bg')
        px = py = self.pad
        self.coords(self._win, px, py)
        self.itemconfigure(self._win, width=max(1, w - 2 * px - 2))
        body_req_h = self.body.winfo_reqheight()
        avail_h = h - 2 * py - 2
        if body_req_h > avail_h + 1:
            self.itemconfigure(self._win, height=body_req_h)
            self.configure(height=body_req_h + 2 * py + 2)
        else:
            self.itemconfigure(self._win, height=max(1, avail_h))


class Toast:
    """底部滑入的复制成功提示"""

    def __init__(self, root):
        self.root = root
        self.cv = None
        self._job = None
        self._step = 0

    def show(self, message):
        if self._job:
            self.root.after_cancel(self._job)
            self._job = None
        if self.cv is None:
            self.cv = tk.Canvas(self.root, bg=COL_PAGE, highlightthickness=0, bd=0)
        f = tkfont.Font(font=(FONT_LATIN, 11))
        w = int(f.measure(message)) + 52
        h = 40
        self.cv.configure(width=w, height=h)
        self.cv.delete('all')
        _round_rect(self.cv, 1, 1, w - 1, h - 1, 20, fill='#333333', outline='#333333')
        self.cv.create_text(w / 2, h / 2, text=message, fill='#ffffff', font=(FONT_LATIN, 11))
        self._step = 0
        self._run()

    def _run(self):
        s = self._step
        if s < 8:
            y = 44 - s * 2
            self._place(y)
            self._job = self.root.after(16, self._run)
        elif s < 22:
            self._place(30)
            self._job = self.root.after(70, self._run)
        elif s < 30:
            y = 30 - (s - 22) * 2
            self._place(y)
            self._job = self.root.after(16, self._run)
        else:
            self.cv.place_forget()
            self._job = None
        self._step += 1

    def _place(self, y):
        try:
            self.cv.place_configure(relx=0.5, y=self.root.winfo_height() - y, anchor='s')
            self.cv.lift()
        except Exception:
            pass


class DayCell(tk.Canvas):
    """日历中的一天：有记录的日期带蓝点，今天带描边，选中日蓝底白字"""

    def __init__(self, master, day, has, is_today, selected, on_click, s=1.0):
        w = int(28 * s)
        h = int(42 * s)
        super().__init__(master, width=w, height=h, bg=COL_CARD, highlightthickness=0, bd=0,
                         cursor='hand2')
        self.day = day
        self._on_click = on_click
        self._has = has
        self._is_today = is_today
        self._selected = selected
        self._s = s
        self._draw()
        self.bind('<Configure>', lambda e: self._draw())
        self.bind('<Button-1>', lambda e: self._on_click(day))

    def _draw(self):
        self.delete('all')
        w = self.winfo_width() or int(28 * self._s)
        h = self.winfo_height() or int(42 * self._s)
        s = self._s
        cx, cy = w / 2, h / 2 - 2
        r = int(11 * s)
        if self._selected:
            _round_rect(self, cx - r, cy - r, cx + r, cy + r, r,
                        fill=COL_ACCENT, outline=COL_ACCENT)
            color = '#ffffff'
            dot = False
        else:
            color = COL_TEXT if self._has else '#c7c7cc'
            if self._is_today:
                _round_rect(self, cx - r, cy - r, cx + r, cy + r, r,
                            outline=COL_ACCENT, width=1)
            dot = self._has
        self.create_text(cx, cy, text=str(self.day), fill=color, font=(FONT, 9))
        if dot:
            d = int(2 * s)
            self.create_oval(cx - d, cy + int(9 * s), cx + d, cy + int(9 * s) + 2 * d,
                             fill=COL_ACCENT, outline='')


class Calendar(tk.Frame):
    """日历：点击日期查看当天记录；有记录的日期带蓝点"""
    WEEK = ['一', '二', '三', '四', '五', '六', '日']

    MIN_YEAR = 2026
    MAX_YEAR = 2099

    def __init__(self, master, on_select, bg=COL_CARD, s=1.0):
        super().__init__(master, bg=bg)
        self.s = s
        self.on_select = on_select
        now = datetime.now()
        self.year = max(self.MIN_YEAR, min(now.year, self.MAX_YEAR))
        self.month = now.month if now.year == self.year else (1 if now.year < self.MIN_YEAR else 12)
        self.selected = None
        self.has_set = set()
        self.today_str = now.strftime('%Y-%m-%d')
        self._cells = {}

        head = tk.Frame(self, bg=bg)
        head.pack(fill='x', pady=(0, int(6 * s)))
        self.btn_prev = tk.Label(head, text=chr(0x2039), bg=bg, fg=COL_ACCENT,
                                 font=(FONT_LATIN, 13, 'bold'), cursor='hand2', padx=int(8 * s))
        self.btn_prev.pack(side='left')
        self.title_lbl = tk.Label(head, text='', bg=bg, fg=COL_TEXT, font=(FONT, 10, 'bold'))
        self.title_lbl.pack(side='left', expand=True)
        self.btn_next = tk.Label(head, text=chr(0x203A), bg=bg, fg=COL_ACCENT,
                                 font=(FONT_LATIN, 13, 'bold'), cursor='hand2', padx=int(8 * s))
        self.btn_next.pack(side='right')
        self.btn_prev.bind('<Button-1>', lambda e: self._shift(-1))
        self.btn_next.bind('<Button-1>', lambda e: self._shift(1))
        self.btn_prev.bind('<Enter>', lambda e: self._nav_hover(self.btn_prev, True))
        self.btn_prev.bind('<Leave>', lambda e: self._update_nav_state())
        self.btn_next.bind('<Enter>', lambda e: self._nav_hover(self.btn_next, True))
        self.btn_next.bind('<Leave>', lambda e: self._update_nav_state())

        self.btn_today = tk.Label(self, text='回到今天', bg=bg, fg=COL_ACCENT, font=(FONT, 9),
                                  cursor='hand2', padx=int(4 * s))
        self.btn_today.pack(anchor='w', pady=(0, int(6 * s)))
        self.btn_today.bind('<Button-1>', lambda e: self._goto_today())
        self.btn_today.bind('<Enter>', lambda e: self.btn_today.configure(fg='#1d1d1f'))
        self.btn_today.bind('<Leave>', lambda e: self.btn_today.configure(fg=COL_ACCENT))

        wrow = tk.Frame(self, bg=bg)
        wrow.pack(fill='x')
        for name in self.WEEK:
            tk.Label(wrow, text=name, bg=bg, fg=COL_SUB, font=(FONT, 9)).pack(side='left', expand=True)

        self.grid_frame = tk.Frame(self, bg=bg)
        self.grid_frame.pack(fill='x')
        self.refresh(self.has_set, self.selected)
        self._update_nav_state()

    def refresh(self, has_set, selected=None, today=None):
        self.has_set = set(has_set or ())
        if today:
            self.today_str = today
        if selected:
            self.selected = selected
        self.title_lbl.configure(text='%d年%d月' % (self.year, self.month))
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self._cells = {}
        first = datetime(self.year, self.month, 1)
        blanks = first.weekday()  # 周一为一周开始
        days_in_month = monthrange(self.year, self.month)[1]
        total = blanks + days_in_month
        num_rows = (total + 6) // 7
        rows = []
        for _ in range(num_rows):
            row = tk.Frame(self.grid_frame, bg=COL_CARD)
            row.pack(fill='x')
            for c in range(7):
                row.columnconfigure(c, weight=1, uniform='cal')
            rows.append(row)
        ri = 0
        col = 0
        for _ in range(blanks):
            tk.Label(rows[ri], bg=COL_CARD).grid(row=0, column=col, sticky='nsew')
            col += 1
        for day in range(1, days_in_month + 1):
            if col == 7:
                ri += 1
                col = 0
            date_str = '%04d-%02d-%02d' % (self.year, self.month, day)
            is_today = date_str == self.today_str
            is_selected = date_str == self.selected
            has = date_str in self.has_set
            cell = DayCell(rows[ri], day, has, is_today, is_selected, self._pick, self.s)
            cell.grid(row=0, column=col, sticky='nsew')
            self._cells[date_str] = cell
            col += 1
        while col < 7:
            tk.Label(rows[ri], bg=COL_CARD).grid(row=0, column=col, sticky='nsew')
            col += 1

    def _can_shift(self, delta):
        m = self.month + delta
        y = self.year
        if m < 1:
            m, y = 12, y - 1
        elif m > 12:
            m, y = 1, y + 1
        return self.MIN_YEAR <= y <= self.MAX_YEAR

    def _nav_hover(self, btn, enter):
        ok = self._can_shift(-1) if btn is self.btn_prev else self._can_shift(1)
        btn.configure(fg='#1d1d1f' if (enter and ok) else (COL_ACCENT if ok else '#d9d9de'))

    def _update_nav_state(self):
        self.btn_prev.configure(fg=COL_ACCENT if self._can_shift(-1) else '#d9d9de')
        self.btn_next.configure(fg=COL_ACCENT if self._can_shift(1) else '#d9d9de')

    def _shift(self, delta):
        if not self._can_shift(delta):
            return
        m = self.month + delta
        y = self.year
        if m < 1:
            m, y = 12, y - 1
        elif m > 12:
            m, y = 1, y + 1
        self.year, self.month = y, m
        self.refresh(self.has_set, self.selected)
        self._update_nav_state()

    def _goto_today(self):
        now = datetime.now()
        if self.MIN_YEAR <= now.year <= self.MAX_YEAR:
            self.year, self.month = now.year, now.month
        self.today_str = now.strftime('%Y-%m-%d')
        self.refresh(self.has_set, self.today_str)
        self._update_nav_state()
        self.on_select(self.today_str)

    def _pick(self, date_str):
        self.selected = date_str
        self.refresh(self.has_set, self.selected)
        self.on_select(date_str)

# ---------------- 应用界面 ----------------
class App:
    def __init__(self, root, store, cfg):
        self.root = root
        self.store = store
        self.cfg = cfg
        self.s = _dpi_scale()
        self.watcher = Watcher(store, int(cfg.get('poll_interval_ms', 700)), self.on_new_entry)
        self.current_date = None
        self.current_entry = None
        self.current_entries = []
        self.iid_map = {}
        self.search_mode = False
        self.search_var = tk.StringVar()
        self._img_refs = []
        self._preview_pil = None
        self._detail_is_image = False
        self._stats_total = 0
        self._stats_days = 0
        self._known_dates = set()
        self._hovered_entry = None
        self.toast = Toast(root)
        self._build_ui()
        try:
            self.root.deiconify()
            self.root.lift()
        except Exception:
            pass
        self.refresh_dates(select_date=None)
        self.root.after(300, self._tick)
        self._fade_in()

    def _fade_in(self, a=0.0):
        try:
            self.root.attributes('-alpha', min(1.0, a + 0.07))
            if a < 0.98:
                self.root.after(16, lambda: self._fade_in(a + 0.07))
        except Exception:
            pass



    def _build_ui(self):
        s = self.s
        self.root.title(APP_TITLE)
        self.root.configure(bg=COL_PAGE)
        self.root.geometry('%dx%d' % (int(1180 * s), int(760 * s)))
        self.root.minsize(int(980 * s), int(620 * s))
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        try:
            hwnd = user32.GetParent(self.root.winfo_id())
            if hwnd:
                user32.SetWindowTextW(hwnd, APP_TITLE)
        except Exception:
            pass

        style = ttk.Style(self.root)
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('Treeview', background=COL_CARD, fieldbackground=COL_CARD, foreground=COL_TEXT,
                        rowheight=int(30 * s), borderwidth=0, font=(FONT, 10))
        style.configure('Treeview.Heading', background=COL_CARD, foreground=COL_SUB,
                        font=(FONT_LATIN, 9, 'bold'), borderwidth=0, relief='flat', padding=(8, int(6 * s)))
        style.map('Treeview', background=[('selected', COL_SELECT)], foreground=[('selected', COL_TEXT)])
        style.configure('TEntry', fieldbackground=COL_CARD, bordercolor=COL_BORDER, lightcolor=COL_BORDER,
                        darkcolor=COL_BORDER, padding=(int(8 * s), int(7 * s)), insertcolor=COL_ACCENT)
        style.configure('Vertical.TScrollbar', background='#e6e6eb', troughcolor=COL_CARD,
                        bordercolor=COL_CARD, arrowcolor='#9a9aa0', width=11)

        # ---------- 顶部一行：标题 + 紧凑搜索 + 按钮 ----------
        header = tk.Frame(self.root, bg=COL_PAGE)
        header.pack(fill='x', padx=int(22 * s), pady=(int(16 * s), int(12 * s)))
        ttl_box = tk.Frame(header, bg=COL_PAGE)
        ttl_box.pack(side='left')
        tk.Label(ttl_box, text=APP_TITLE, bg=COL_PAGE, fg=COL_TEXT,
                 font=(FONT_TITLE, 15)).pack(side='left')
        tk.Label(ttl_box, text='自动记录文本与截图', bg=COL_PAGE, fg=COL_SUB,
                 font=(FONT, 9)).pack(side='left', padx=(int(10 * s), 0), pady=(0, 0))

        # 紧凑搜索条（在标题右侧，不再是大卡片）
        search_box = tk.Frame(header, bg=COL_PAGE)
        search_box.pack(side='left', padx=(int(26 * s), 0))
        tk.Label(search_box, text=chr(0x1F50D), bg=COL_PAGE, fg=COL_SUB,
                 font=('Segoe UI Emoji', 10)).pack(side='left')
        self.search_entry = ttk.Entry(search_box, textvariable=self.search_var, width=24, font=(FONT, 10))
        self.search_entry.pack(side='left', padx=(int(6 * s), int(8 * s)))
        self.search_entry.bind('<Return>', lambda e: self.do_search())
        AppleButton(search_box, text='搜索', kind='primary', command=self.do_search,
                    height=int(30 * s), padx=int(13 * s)).pack(side='left')
        AppleButton(search_box, text='今天', kind='secondary', command=self.show_all,
                    height=int(30 * s), padx=int(12 * s)).pack(side='left', padx=(int(8 * s), 0))

        AppleButton(header, text='退出', kind='secondary', command=self.quit_app,
                    height=int(30 * s), padx=int(13 * s)).pack(side='right', padx=(int(6 * s), 0))
        self.pause_btn = AppleButton(header, text='暂停记录', kind='secondary', command=self.toggle_pause,
                                     height=int(30 * s), padx=int(13 * s))
        self.pause_btn.pack(side='right', padx=(int(6 * s), 0))
        AppleButton(header, text='打开数据文件夹', kind='secondary', command=self.open_data_dir,
                    height=int(30 * s), padx=int(13 * s)).pack(side='right', padx=(int(6 * s), 0))

        # ---------- 主体：左日历 + 右内容区 ----------
        body = tk.Frame(self.root, bg=COL_PAGE)
        body.pack(fill='both', expand=True, padx=int(22 * s), pady=(0, int(14 * s)))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # 左侧：日历卡片
        left = tk.Frame(body, bg=COL_PAGE)
        left.grid(row=0, column=0, sticky='nw', padx=(0, int(14 * s)))
        cal_card = AppleCard(left, width=int(191 * s), pad=int(14 * s))
        cal_card.pack(fill='x')
        self.cal = Calendar(cal_card.body, self.select_calendar_date, s=s)
        self.cal.pack(fill='x')
        self.stats_lbl = tk.Label(cal_card.body, text='', bg=COL_CARD, fg=COL_SUB, font=(FONT, 9))
        self.stats_lbl.pack(anchor='w', pady=(int(10 * s), 0))
        tk.Label(cal_card.body, text='蓝点 = 当天有记录', bg=COL_CARD, fg='#b9b9c0',
                 font=(FONT, 8)).pack(anchor='w', pady=(int(2 * s), 0))

        # 右侧：记录列表（大）+ 详情
        right = tk.Frame(body, bg=COL_PAGE)
        right.grid(row=0, column=1, sticky='nsew')
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=5)
        right.rowconfigure(1, weight=3)

        ent_card = AppleCard(right, pad=int(14 * s))
        ent_card.grid(row=0, column=0, sticky='nsew', pady=(0, int(14 * s)))
        ent_head_frame = tk.Frame(ent_card.body, bg=COL_CARD)
        ent_head_frame.pack(fill='x', pady=(0, int(6 * s)))
        self.ent_head = tk.Label(ent_head_frame, text='', bg=COL_CARD, fg=COL_SUB,
                                 font=(FONT_LATIN, 9, 'bold'))
        self.ent_head.pack(side='left')
        self.btn_clear_day = AppleButton(ent_head_frame, text='清空当天', kind='danger', command=self.clear_day,
                                         height=int(26 * s), padx=int(12 * s))
        self.btn_clear_day.pack(side='right')
        tk.Label(ent_head_frame, text='双击复制 · Ctrl+C', bg=COL_CARD, fg='#b9b9c0',
                 font=(FONT, 8)).pack(side='right', padx=(0, int(10 * s)))
        ent_wrap = tk.Frame(ent_card.body, bg=COL_CARD)
        ent_wrap.pack(fill='both', expand=True)
        self.entry_tree = ttk.Treeview(ent_wrap, columns=('time', 'type', 'preview'),
                                       show='headings', selectmode='browse')
        self.entry_tree.heading('time', text='时间')
        self.entry_tree.heading('type', text='类型')
        self.entry_tree.heading('preview', text='内容预览')
        self.entry_tree.column('time', width=int(132 * s), anchor='w', stretch=False)
        self.entry_tree.column('type', width=int(60 * s), anchor='center', stretch=False)
        self.entry_tree.column('preview', width=int(600 * s), anchor='w')
        self.entry_tree.tag_configure('hover', background=COL_HOVER)
        self.entry_tree.pack(side='left', fill='both', expand=True)
        ev = ttk.Scrollbar(ent_wrap, orient='vertical', command=self.entry_tree.yview)
        ev.pack(side='right', fill='y')
        self.entry_tree.configure(yscrollcommand=ev.set)
        self.entry_tree.bind('<MouseWheel>', self._tree_wheel)
        ev.bind('<MouseWheel>', self._tree_wheel)
        self.entry_tree.bind('<<TreeviewSelect>>', self.on_entry_selected)
        self.entry_tree.bind('<Motion>', lambda e: self._tree_hover(e, self.entry_tree, '_hovered_entry'))
        self.entry_tree.bind('<Leave>', lambda e: self._tree_leave(self.entry_tree, '_hovered_entry'))
        self.entry_tree.bind('<Double-1>', lambda e: self.copy_entry())
        self.entry_tree.bind('<Control-c>', lambda e: self.copy_entry())
        self.entry_tree.bind('<Return>', lambda e: self.copy_entry())

        # 详情卡片
        detail_card = AppleCard(right, pad=int(14 * s))
        detail_card.grid(row=1, column=0, sticky='nsew')
        dc = detail_card.body
        bar2 = tk.Frame(dc, bg=COL_CARD)
        bar2.pack(fill='x', pady=(0, int(10 * s)))
        self.detail_title = tk.Label(bar2, text='选中一条记录，点击“复制这条”或双击列表即可重新复制',
                                     bg=COL_CARD, fg=COL_SUB, font=(FONT, 10))
        self.detail_title.pack(side='left')
        self.btn_del = AppleButton(bar2, text='删除这条', kind='danger', command=self.delete_entry,
                                   height=int(30 * s), padx=int(13 * s))
        self.btn_del.pack(side='right', padx=(int(6 * s), 0))
        self.btn_folder = AppleButton(bar2, text='打开所在文件夹', kind='secondary', command=self.open_folder,
                                      height=int(30 * s), padx=int(13 * s))
        self.btn_folder.pack(side='right', padx=(int(6 * s), 0))
        self.btn_open = AppleButton(bar2, text='打开图片', kind='secondary', command=self.open_image,
                                    height=int(30 * s), padx=int(13 * s))
        self.btn_open.pack(side='right', padx=(int(6 * s), 0))
        self.btn_copy = AppleButton(bar2, text='复制这条', kind='primary', command=self.copy_entry,
                                    height=int(30 * s), padx=int(15 * s))
        self.btn_copy.pack(side='right', padx=(int(6 * s), 0))

        self.detail_body = tk.Frame(dc, bg=COL_CARD)
        self.detail_body.pack(fill='both', expand=True)
        self.detail_body.columnconfigure(0, weight=1)
        self.detail_body.rowconfigure(0, weight=1)
        self.detail_body.bind('<Configure>', self._on_detail_resize)
        self.text_view = tk.Text(self.detail_body, wrap='word', bg=COL_CARD, fg=COL_TEXT, relief='flat',
                                 font=(FONT, 11), padx=int(12 * s), pady=int(12 * s), state='disabled',
                                 highlightthickness=0, bd=0, insertbackground=COL_ACCENT)
        tv = tk.Scrollbar(self.detail_body, command=self.text_view.yview, bd=0, relief='flat',
                          bg=COL_PAGE, troughcolor=COL_CARD, activebackground='#d9d9de', highlightthickness=0)
        tv.grid(row=0, column=1, sticky='ns')
        self.text_view.configure(yscrollcommand=tv.set)
        self.text_view.grid(row=0, column=0, sticky='nsew')
        self.image_view = tk.Label(self.detail_body, bg=COL_CARD, text='', anchor='center')
        self.image_view.grid_remove()

        # ---------- 状态栏 ----------
        status = tk.Frame(self.root, bg=COL_PAGE)
        status.pack(fill='x', padx=int(22 * s), pady=(0, int(12 * s)))
        self.status_dot = tk.Label(status, text=chr(0x25CF), fg=COL_OK, bg=COL_PAGE, font=(FONT_LATIN, 9))
        self.status_dot.pack(side='left')
        self.status_label = tk.Label(status, text='正在记录剪贴板（文本 + 图片）', bg=COL_PAGE, fg=COL_SUB,
                                     font=(FONT, 9))
        self.status_label.pack(side='left', padx=(int(4 * s), 0))
        tk.Label(status, text='关闭窗口 = 最小化到任务栏，后台继续记录', bg=COL_PAGE, fg=COL_SUB,
                 font=(FONT, 9)).pack(side='right', padx=(int(14 * s), 0))
        tk.Label(status, text='数据目录：%s' % self.store.data_dir, bg=COL_PAGE, fg=COL_SUB,
                 font=(FONT, 9)).pack(side='right')

        self._clear_detail()

    # ---------- 数据刷新 ----------
    def refresh_dates(self, select_date=None):
        prev = self.current_date
        today = self.store.today()
        target = select_date or prev or today
        self.current_date = target
        has_set = set(self.store.all_dates())
        self.cal.refresh(has_set, selected=target, today=today)
        self._update_stats(full=True)
        self.load_entries(target)

    def refresh_counts(self, date):
        has_set = set(self.store.all_dates())
        self.cal.refresh(has_set, selected=self.current_date, today=self.store.today())
        if self.search_var.get().strip():
            return
        if date == self.current_date:
            self.load_entries(date)

    def _update_stats(self, full=False):
        if full:
            try:
                dates = self.store.all_dates()
                self._known_dates = set(dates)
                self._stats_days = len(dates)
                self._stats_total = sum(len(self.store.load_entries(d)) for d in dates)
            except Exception:
                pass
        self.stats_lbl.configure(text='共 %d 条记录 · 记录 %d 天' % (self._stats_total, self._stats_days))

    def select_calendar_date(self, date):
        """点击日历某一天：打开当天内容"""
        self.search_var.set('')
        self.search_mode = False
        self.current_date = date
        self.cal.refresh(set(self.store.all_dates()), selected=date, today=self.store.today())
        self.load_entries(date)

    def load_entries(self, date):
        self.current_date = date
        self.search_mode = False
        entries = self.store.load_entries(date)
        entries.sort(key=lambda e: e['ts'], reverse=True)
        self._fill_entries(entries)
        self.ent_head.configure(text='%s  共 %d 条记录' % (date, len(entries)))
        self.btn_clear_day.set_state(len(entries) > 0)
        self._clear_detail()
        if entries:
            first = entries[0]['id']
            self.entry_tree.selection_set(first)
            self.entry_tree.see(first)

    def _fill_entries(self, entries):
        self.entry_tree.delete(*self.entry_tree.get_children())
        self.iid_map = {}
        self.current_entries = entries
        for e in entries:
            iid = e['id']
            self.iid_map[iid] = e
            typ = '文本' if e.get('type') == 'text' else '图片'
            self.entry_tree.insert('', 'end', iid=iid, values=(e['ts'][5:], typ, e.get('preview', '')))

    # ---------- 悬停效果 ----------
    def _tree_hover(self, evt, tree, attr):
        try:
            row = tree.identify_row(evt.y)
        except Exception:
            return
        prev = getattr(self, attr)
        if prev and prev != row:
            tree.item(prev, tags=())
        setattr(self, attr, row)
        sel = tree.selection()
        if row and row not in sel:
            tree.item(row, tags=('hover',))

    def _tree_leave(self, tree, attr):
        prev = getattr(self, attr)
        if prev:
            tree.item(prev, tags=())
        setattr(self, attr, None)

    def _tree_wheel(self, evt):
        self._tree_leave(self.entry_tree, '_hovered_entry')
        delta = -1 if evt.delta > 0 else 1
        self.entry_tree.yview_scroll(delta, 'units')
        return 'break'

    # ---------- 事件 ----------
    def on_entry_selected(self, _evt):
        self._tree_leave(self.entry_tree, '_hovered_entry')
        sel = self.entry_tree.selection()
        if not sel:
            return
        entry = self.iid_map.get(sel[0])
        if not entry:
            return
        self.current_entry = entry
        self.btn_copy.set_state(True)
        self.btn_del.set_state(True)
        if entry.get('type') == 'text':
            self.btn_open.set_state(False)
            self.btn_folder.set_state(False)
            content = entry.get('content', '')
            self.detail_title.configure(text='%s · 文本（%d 字）  ·  双击列表可复制' % (entry['ts'], len(content)))
            self._show_text(content)
        else:
            self.btn_open.set_state(True)
            self.btn_folder.set_state(True)
            self.detail_title.configure(text='%s · 截图  ·  双击列表可复制' % entry['ts'])
            if self._load_image_preview(entry):
                self._show_image()
            else:
                self._show_text('（图片预览加载失败，可点击“打开图片”查看原图）')

    def on_new_entry(self, entry):
        self._stats_total += 1
        if entry['date'] not in self._known_dates:
            self._known_dates.add(entry['date'])
            self._stats_days += 1
        self.refresh_counts(entry['date'])
        self._update_stats()

    def _tick(self):
        self.watcher.poll()
        self.root.after(self.watcher.interval_ms, self._tick)

    # ---------- 详情显示 ----------
    def _show_text(self, content):
        self._detail_is_image = False
        self.image_view.grid_remove()
        self.text_view.grid(row=0, column=0, sticky='nsew')
        self.text_view.configure(state='normal')
        self.text_view.delete('1.0', 'end')
        self.text_view.insert('1.0', content)
        self.text_view.configure(state='disabled')

    def _show_image(self):
        img = self._preview_pil
        if img is None:
            return
        try:
            self.detail_body.update_idletasks()
            w_avail = max(60, self.detail_body.winfo_width())
            h_avail = max(60, self.detail_body.winfo_height())
            target_w = int(w_avail * 0.96)
            target_h = int(h_avail * 0.88)
            iw, ih = img.size
            scale = min(target_w / iw, target_h / ih)
            nw = max(1, int(iw * scale))
            nh = max(1, int(ih * scale))
            if (nw, nh) != img.size:
                img = img.resize((nw, nh), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._img_refs.append(photo)
            if len(self._img_refs) > 12:
                self._img_refs = self._img_refs[-6:]
            self._detail_is_image = True
            self.text_view.grid_remove()
            self.image_view.configure(image=photo, text='')
            self.image_view.grid(row=0, column=0, sticky='nsew')
        except Exception:
            pass

    def _on_detail_resize(self, _e=None):
        if getattr(self, '_detail_is_image', False) and self._preview_pil is not None:
            self._show_image()

    def _load_image_preview(self, entry):
        p = os.path.join(self.store.data_dir, entry.get('file', '') or '')
        if not os.path.exists(p):
            p = os.path.join(self.store.data_dir, entry.get('thumb', '') or '')
        try:
            img = Image.open(p)
            img.load()
            img.thumbnail((int(1600 * self.s), int(1600 * self.s)))
            self._preview_pil = img.copy()
            return True
        except Exception:
            self._preview_pil = None
            return False

    def _clear_detail(self):
        self.current_entry = None
        self.detail_title.configure(text='选中一条记录，点击“复制这条”或双击列表即可重新复制')
        self._show_text('')
        for b in (self.btn_copy, self.btn_open, self.btn_folder, self.btn_del):
            b.set_state(False)

    # ---------- 操作 ----------
    def do_search(self):
        q = self.search_var.get().strip()
        if not q:
            self.show_all()
            return
        results = []
        for date in self.store.all_dates():
            for e in self.store.load_entries(date):
                hay = e.get('preview', '')
                if e.get('type') == 'text':
                    hay = e.get('content', '')[:3000]
                if q.lower() in hay.lower():
                    results.append((date, e))
        results.sort(key=lambda x: x[1]['ts'], reverse=True)
        self.search_mode = True
        self.entry_tree.delete(*self.entry_tree.get_children())
        self.iid_map = {}
        self.current_entries = [e for _, e in results]
        for date, e in results:
            self.iid_map[e['id']] = e
            typ = '文本' if e.get('type') == 'text' else '图片'
            self.entry_tree.insert('', 'end', iid=e['id'], values=(e['ts'][5:], typ, e.get('preview', '')))
        self.ent_head.configure(text='搜索“%s”  共 %d 条' % (q, len(results)))
        self.btn_clear_day.set_state(False)
        self._clear_detail()

    def show_all(self):
        self.search_var.set('')
        self.refresh_dates(select_date=self.store.today())

    def toggle_pause(self):
        self.watcher.paused = not self.watcher.paused
        if self.watcher.paused:
            self.pause_btn.set_text('继续记录')
            self.status_label.configure(text='已暂停记录')
            self.status_dot.configure(fg=COL_WARN, text=chr(0x25A0))
        else:
            self.pause_btn.set_text('暂停记录')
            self.status_label.configure(text='正在记录剪贴板（文本 + 图片）')
            self.status_dot.configure(fg=COL_OK, text=chr(0x25CF))

    def copy_entry(self):
        e = self.current_entry
        if not e:
            return
        try:
            if e.get('type') == 'text':
                ok = set_clipboard_text(e.get('content', ''))
                msg = '已复制文本'
            else:
                p = os.path.join(self.store.data_dir, e.get('file', ''))
                img = Image.open(p)
                img.load()
                ok = set_clipboard_image_pil(img)
                msg = '已复制图片'
            if ok:
                self.watcher.sync()
                self.toast.show('✓ %s · %s' % (msg, e['ts'][5:]))
            else:
                _warn('复制失败，请稍后重试。')
        except Exception:
            _warn('复制失败。')

    def open_image(self):
        e = self.current_entry
        if not e or e.get('type') != 'image':
            return
        p = os.path.join(self.store.data_dir, e.get('file', ''))
        if os.path.exists(p):
            os.startfile(p)

    def open_folder(self):
        e = self.current_entry
        if not e:
            return
        if e.get('type') == 'image':
            p = os.path.join(self.store.data_dir, e.get('file', ''))
            folder = os.path.dirname(p)
        else:
            folder = os.path.join(self.store.data_dir, 'text')
        if os.path.exists(folder):
            os.startfile(folder)

    def delete_entry(self):
        e = self.current_entry
        if not e:
            return
        if not _ask_yes_no('确定删除这条记录吗？\n%s · %s' % (e['ts'], e.get('preview', ''))):
            return
        self.store.delete_entry(e['id'], e['date'])
        self.refresh_dates(select_date=self.current_date)

    def clear_day(self):
        d = self.current_date
        if not d:
            return
        n = len(self.store.load_entries(d))
        if n == 0:
            _info('这一天还没有记录。')
            return
        if not _ask_yes_no('确定清空 %s 的全部 %d 条记录吗？\n文本日志和图片文件都会被删除。' % (d, n)):
            return
        self.store.clear_day(d)
        self.refresh_dates(select_date=self.store.today())

    def open_data_dir(self):
        try:
            os.startfile(self.store.data_dir)
        except Exception:
            pass

    def _on_close(self):
        self.root.iconify()

    def quit_app(self):
        if _ask_yes_no('确定退出剪贴板记录吗？\n退出后将停止记录剪贴板。'):
            self.root.destroy()


# ---------------- 入口 ----------------
def _ensure_single_instance():
    kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        hwnd = user32.FindWindowW(None, APP_TITLE)
        if hwnd:
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
        else:
            user32.MessageBoxW(None, '剪贴板记录已在后台运行。\n请从任务栏打开它的窗口。', APP_TITLE, 0x40)
        return False
    return True


def main():
    _enable_dpi()
    if not _ensure_single_instance():
        return
    base = os.path.dirname(os.path.abspath(__file__))
    cfg = {}
    try:
        with open(os.path.join(base, 'config.json'), 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except Exception:
        pass
    data_dir = (cfg.get('data_dir') or '').strip()
    if not data_dir:
        data_dir = os.path.join(base, 'data')
    elif not os.path.isabs(data_dir):
        data_dir = os.path.join(base, data_dir)
    store = Store(data_dir, int(cfg.get('max_text_len', 200000)))
    root = tk.Tk()
    App(root, store, cfg)
    root.mainloop()


if __name__ == '__main__':
    main()
