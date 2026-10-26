@echo off
setlocal
cd /d "%~dp0"
set "OSREVIEW_SAFE_MODE=1"
echo MODO SEGURO: sem bandeja, verificacoes automaticas de sensores, drivers ou eventos.
echo Ainda e possivel clicar manualmente em Atualizar sensores e exportar o pacote.
where py >nul 2>&1
if not errorlevel 1 (set "PY=py -3") else (set "PY=python")
%PY% -u run.py
echo Encerramento. Veja %%LOCALAPPDATA%%\OSReview\logs se houve falha.
pause
