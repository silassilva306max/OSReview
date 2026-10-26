"""Stable OSReview entry point: preserve crash logs even when GUI will not open."""
import os
import platform
import sys

from osreview.services.startup_logging import LOG, init_logging


def main():
    folder = init_logging()
    if '--diagnostico' in sys.argv or '--diagnose' in sys.argv:
        from osreview.services.support_bundle import export_support_zip
        from pathlib import Path
        target = Path.cwd() / 'OSReview_suporte_inicializacao.zip'
        export_support_zip(target)
        print('Diagnóstico salvo em:', target)
        print('Logs locais em:', folder)
        return 0
    if platform.system() == 'Windows':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('OSReview.Diagnostics')
        except (OSError, AttributeError) as exc:
            LOG.warning('Ícone/AppUserModelID indisponível: %s', exc)
    try:
        LOG.info('Carregando janela principal')
        from osreview.enhanced_app import OSReviewAppV5
        app = OSReviewAppV5()
        LOG.info('Janela principal criada com sucesso')
        app.mainloop()
        LOG.info('Loop grafico encerrado; encerramento normal se o usuario solicitou')
        return 0
    except Exception:
        LOG.exception('Falha ao abrir ou manter o OSReview')
        print('\nERRO ao abrir OSReview. Logs em:', folder, file=sys.stderr)
        # Do not require Tk availability to report a Tk failure.
        try:
            from tkinter import messagebox
            messagebox.showerror('OSReview - erro de inicialização',
                'Não foi possível iniciar o OSReview. Consulte a pasta de logs:\n' + str(folder))
        except Exception:
            pass
        return 1


if __name__ == '__main__':
    sys.exit(main())
