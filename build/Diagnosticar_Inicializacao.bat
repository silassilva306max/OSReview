@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (set "PY=py -3") else (set "PY=python")
echo Gerando diagnostico sem abrir interface e sem executar sensores...
%PY% run.py --diagnostico
if errorlevel 1 (echo ERRO AO GERAR RELATORIO. & pause & exit /b 1)
echo.
echo Relatorio salvo em OSReview_suporte_inicializacao.zip
pause
