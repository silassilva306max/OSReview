"""Optional native tray for Windows. UI communication exclusively via Queue."""
from __future__ import annotations

from queue import Queue
import platform
import threading


class TrayController:
    def __init__(self, commands: Queue):
        self.commands = commands
        self.icon = None
        self.available = False
        self._thread = None
        if platform.system() == "Windows":
            try:
                import pystray  # noqa: F401
                from PIL import Image  # noqa: F401
                self.available = True
            except ImportError:
                pass

    def start(self) -> bool:
        if not self.available:
            return False
        try:
            import pystray
            from PIL import Image, ImageDraw
            im = Image.new("RGBA", (64, 64), (18, 20, 26, 255))
            dr = ImageDraw.Draw(im)
            dr.rounded_rectangle((5, 5, 59, 59), radius=14, fill=(234, 82, 76, 255))
            dr.line([(12, 34), (23, 34), (29, 19), (37, 45), (43, 31), (52, 31)],
                    fill=(255, 255, 255, 255), width=5, joint="curve")
            menu = pystray.Menu(
                pystray.MenuItem("Abrir OSReview", lambda _icon, _item: self.commands.put(("show",)), default=True),
                pystray.MenuItem("Desativar alertas", lambda _icon, _item: self.commands.put(("toggle_alerts",))),
                pystray.MenuItem("Sair", lambda _icon, _item: self.commands.put(("exit",))),
            )
            self.icon = pystray.Icon("OSReview", im, "OSReview • Diagnóstico", menu)
            # Windows backend of pinned pystray 0.19.x exposes notification event
            # handlers. Hook WM_MOUSEMOVE without replacing normal click/menu code.
            # This is an optional enhancement: failure leaves the tray functional.
            try:
                from pystray._util import win32
                handler = self.icon._message_handlers[win32.WM_NOTIFY]
                def on_notify(wparam, lparam):
                    if lparam == 0x0200:  # WM_MOUSEMOVE over the tray icon
                        self.commands.put(("tray-hover",))
                    elif lparam in (0x0202, 0x0205):  # clicks dismiss popup
                        self.commands.put(("tray-hide-popup",))
                    return handler(wparam, lparam)
                self.icon._message_handlers[win32.WM_NOTIFY] = on_notify
            except (ImportError, AttributeError, KeyError):
                pass
            self._thread = threading.Thread(target=self.icon.run, daemon=True, name="osreview-tray")
            self._thread.start()
            return True
        except Exception:
            self.available = False
            return False

    def notify(self, title: str, message: str) -> bool:
        if not self.icon or not self.available:
            return False
        try:
            if self.icon.HAS_NOTIFICATION:
                self.icon.notify(message, title)
                return True
        except Exception:
            pass
        return False

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
