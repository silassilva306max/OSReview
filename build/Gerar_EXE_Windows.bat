@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0\.."
title OSReview 0.7.5 - Compilacao transparente
if not exist "run.py" (
  echo ERRO: extraia o ZIP completamente e execute na pasta do projeto.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>&1
  if not errorlevel 1 (py -3 -m venv .venv) else (python -m venv .venv)
  if errorlevel 1 goto :erro
)
set "PY=.venv\Scripts\python.exe"
echo [1/5] Instalando bibliotecas declaradas no requirements.txt...
"%PY%" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :erro

echo [2/5] Executando testes de regressao...
"%PY%" -m pip install pytest
if errorlevel 1 goto :erro
"%PY%" -m pytest -q
if errorlevel 1 goto :erro

echo [3/5] Compilando ponte de sensores do LibreHardwareMonitor (SDK .NET 8+)...
set "SENSOR_BUNDLE="
where dotnet >nul 2>&1
if errorlevel 1 (
 echo SDK .NET 8 nao encontrado. Compilacao interrompida para EVITAR distribuir app sem sensores. Instale: https://dotnet.microsoft.com/download/dotnet/8.0
 goto :erro
) else (
 dotnet restore "sensor_bridge\SensorBridge.csproj" --source "https://api.nuget.org/v3/index.json" -r win-x64
 if errorlevel 1 goto :erro
 dotnet publish "sensor_bridge\SensorBridge.csproj" -c Release -r win-x64 --self-contained true --no-restore -p:PublishSingleFile=true -p:PublishTrimmed=false -o "sensor_bridge\publish"
 if errorlevel 1 goto :erro
 if exist "sensor_bridge\publish\SensorBridge.exe" (
   copy /Y "sensor_bridge\publish\SensorBridge.exe" "sensor_bridge\SensorBridge.exe" >nul
   "%PY%" -c "import hashlib,pathlib; p=pathlib.Path('sensor_bridge/SensorBridge.exe'); p.with_suffix('.exe.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n',encoding='ascii')"
   if errorlevel 1 goto :erro
   set "SENSOR_BUNDLE=--add-binary sensor_bridge\SensorBridge.exe;sensor_bridge --add-data sensor_bridge\SensorBridge.exe.sha256;sensor_bridge"
 )
)

echo [4/5] Preparando motor FPS oficial opcional (MIT, download HTTPS e SHA256)...
"%PY%" fps_engine\preparar_motor_fps.py
if errorlevel 1 goto :erro
set "FPS_BUNDLE=--add-binary fps_engine\PresentMon.exe;fps_engine --add-data fps_engine\AVISO_DE_TERCEIROS.md;fps_engine"
echo Gerando distribuicao em pasta (menos extracao temporaria que onefile)...
"%PY%" -m PyInstaller --noconfirm --clean --onedir --windowed --name "OSReview" --icon "assets\osreview.ico" --version-file "build\version_info.txt" --add-data "assets\osreview.png;assets" --add-data "licenses\NOTICE-LIBREHARDWAREMONITOR.txt;licenses" --add-data "licenses\MPL-2.0.txt;licenses" --hidden-import pystray._win32 %SENSOR_BUNDLE% %FPS_BUNDLE% run.py
if errorlevel 1 goto :erro
if not exist "dist\OSReview\OSReview.exe" goto :erro

echo [5/5] Gerando manifesto de integridade SHA256...
"%PY%" -c "import hashlib,pathlib; p=pathlib.Path('dist/OSReview/OSReview.exe'); q=p.with_suffix('.exe.sha256'); q.write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n',encoding='ascii'); print('SHA256:',hashlib.sha256(p.read_bytes()).hexdigest())"
if errorlevel 1 goto :erro

echo.
echo EXE GERADO: dist\OSReview\OSReview.exe
echo ATENCAO: o binario esta SEM assinatura digital.
echo Para assinatura autenticada, use o script Assinar_EXE_Windows.bat com certificado de editor valido.
echo Distribua a pasta inteira dist\OSReview, nao apenas o .exe.
pause
exit /b 0
:erro
echo ERRO: compilacao interrompida; nenhum resultado pode ser considerado validado.
pause
exit /b 1
