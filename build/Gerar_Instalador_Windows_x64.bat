@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0\.."
title OSReview 0.8.1 - Windows x64
if not exist "run.py" (echo ERRO: extraia os arquivos. & exit /b 1)
if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>&1
  if not errorlevel 1 (py -3.12 -m venv .venv 2>nul)
  if not exist ".venv\Scripts\python.exe" python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (echo ERRO: instale Python 3.12 x64. & exit /b 1)
set "PY=.venv\Scripts\python.exe"
echo [1/6] Dependencias Python...
"%PY%" -m pip install -r requirements.txt pyinstaller pytest
if errorlevel 1 exit /b 1
echo [2/6] Testes locais...
"%PY%" -m pytest -q
if errorlevel 1 exit /b 1
where dotnet >nul 2>&1
if errorlevel 1 (echo ERRO: requer SDK .NET 8 x64, para nao perder sensores. & exit /b 1)
echo [3/6] Motor LibreHardwareMonitorLib oficial, Win64...
dotnet restore sensor_bridge\SensorBridge.csproj -r win-x64
if errorlevel 1 exit /b 1
dotnet publish sensor_bridge\SensorBridge.csproj -c Release -r win-x64 --self-contained true --no-restore -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:PublishTrimmed=false -o sensor_bridge\publish
if errorlevel 1 exit /b 1
copy /Y sensor_bridge\publish\SensorBridge.exe sensor_bridge\SensorBridge.exe >nul
"%PY%" -c "import pathlib,hashlib;p=pathlib.Path('sensor_bridge/SensorBridge.exe');p.with_suffix('.exe.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n',encoding='ascii')"
if errorlevel 1 exit /b 1
echo [4/6] Motor de FPS oficial, SHA-256 fixo...
"%PY%" fps_engine\preparar_motor_fps.py
if errorlevel 1 exit /b 1
echo [5/6] Gerando aplicativo nativo OSReview.exe...
"%PY%" -m PyInstaller --noconfirm --clean --onedir --windowed --name OSReview --icon assets\osreview.ico --version-file build\version_info.txt --add-data "assets\osreview.png;assets" --add-data "licenses\NOTICE-LIBREHARDWAREMONITOR.txt;licenses" --add-data "licenses\MPL-2.0.txt;licenses" --add-data "fps_engine\AVISO_DE_TERCEIROS.md;fps_engine" --add-binary "sensor_bridge\SensorBridge.exe;sensor_bridge" --add-data "sensor_bridge\SensorBridge.exe.sha256;sensor_bridge" --add-binary "fps_engine\PresentMon.exe;fps_engine" --hidden-import pystray._win32 run.py
if errorlevel 1 exit /b 1
if not exist "dist\OSReview\OSReview.exe" (echo ERRO: faltando executavel. & exit /b 1)
"%PY%" build\validar_pacote_windows.py
if errorlevel 1 exit /b 1
set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (echo ERRO: instale Inno Setup 6, https://jrsoftware.org/isinfo.php & exit /b 1)
echo [6/6] Criando instalador Inno Setup, destino configuravel...
"%ISCC%" "installer\windows\OSReview.iss"
if errorlevel 1 exit /b 1
"%PY%" -c "import hashlib,pathlib;p=next(pathlib.Path('release').glob('OSReview-Setup-0.8.1-Windows-x64-*.exe'));h=hashlib.sha256(p.read_bytes()).hexdigest();p.with_suffix('.exe.sha256').write_text(h+'  '+p.name+'\n');print('SAIDA:',p,'SHA256:',h)"
echo CONCLUIDO: instalador GUI em release. O usuario final NAO necessita Python, .NET, scripts ou Terminal.
echo NAO ASSINADO: assinatura Authenticode e testes Windows sao necessarios.
exit /b 0
