"""Local crash and startup diagnostics for OSReview (no network calls).

Logs remain on the user's machine. A separate explicit action exports a redacted
support bundle. Fatal crash handling is best-effort: OS or AV termination cannot
always be captured by the Python runtime.
"""
from __future__ import annotations

import faulthandler
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading
import traceback

LOG = logging.getLogger('osreview')
_fatal_file = None
_installed = False


def log_dir() -> Path:
    custom = os.environ.get('OSREVIEW_LOG_DIR')
    if custom:
        root = Path(custom)
    elif os.name == 'nt':
        root = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'OSReview' / 'logs'
    elif sys.platform == 'darwin':
        root = Path.home() / 'Library' / 'Logs' / 'OSReview'
    else:
        root = Path.home() / '.local' / 'share' / 'OSReview' / 'logs'
    root.mkdir(parents=True, exist_ok=True)
    return root


def init_logging() -> Path:
    global _installed, _fatal_file
    folder = log_dir()
    if _installed:
        return folder
    LOG.setLevel(logging.INFO)
    LOG.propagate = False
    writer = RotatingFileHandler(folder / 'osreview.log', maxBytes=2_000_000,
                                 backupCount=3, encoding='utf-8')
    writer.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s'))
    LOG.addHandler(writer)
    _fatal_file = open(folder / 'fatal_python.log', 'a', encoding='utf-8', buffering=1)
    try:
        faulthandler.enable(file=_fatal_file, all_threads=True)
    except (OSError, RuntimeError):
        pass

    def uncaught(t, v, tb):
        LOG.critical('Excecao Python nao tratada: %s: %s\n%s',
                     t.__name__, v, ''.join(traceback.format_exception(t, v, tb)))
        sys.__excepthook__(t, v, tb)

    sys.excepthook = uncaught

    def thread_uncaught(info):
        LOG.error('Falha thread %s: %s', getattr(info.thread, 'name', 'desconhecida'),
                  ''.join(traceback.format_exception(info.exc_type, info.exc_value, info.exc_traceback)))
    threading.excepthook = thread_uncaught
    _installed = True
    LOG.info('Iniciando OSReview | Python %s | sys.platform %s | PID %s',
             sys.version.split()[0], sys.platform, os.getpid())
    return folder


def log_tk_error(exc, value, tb) -> None:
    LOG.error('Falha em callback da interface: %s', ''.join(traceback.format_exception(exc, value, tb)))
