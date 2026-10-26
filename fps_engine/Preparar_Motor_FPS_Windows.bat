@echo off
setlocal
cd /d "%~dp0\.."
where py >nul 2>&1
if not errorlevel 1 (py -3 fps_engine\preparar_motor_fps.py) else (python fps_engine\preparar_motor_fps.py)
if errorlevel 1 (echo Falha na obtencao ou verificacao do motor FPS.&pause&exit /b 1)
echo PresentMon CLI oficial incluido, com SHA-256 verificado.
pause
