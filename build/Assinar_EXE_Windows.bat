@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0\.."
if not exist "dist\OSReview\OSReview.exe" (
  echo ERRO: compile primeiro usando Gerar_EXE_Windows.bat.
  exit /b 1
)
where signtool.exe >nul 2>&1
if errorlevel 1 (
  echo ERRO: SignTool.exe nao encontrado. Instale o Windows SDK oficial.
  exit /b 1
)
if not defined OSREVEW_SIGN_CERT_SHA1 (
  echo Certificado nao informado. Configure OSREVEW_SIGN_CERT_SHA1 com o thumbprint
  echo de um certificado de assinatura de codigo valido e de titularidade do editor.
  echo Nenhuma assinatura foi aplicada.
  exit /b 1
)
echo Assinando arquivos executaveis publicados pelo projeto...
if exist "dist\OSReview\_internal\sensor_bridge\SensorBridge.exe" (
  signtool sign /sha1 "%OSREVEW_SIGN_CERT_SHA1%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "dist\OSReview\_internal\sensor_bridge\SensorBridge.exe"
  if errorlevel 1 exit /b 1
  signtool verify /pa "dist\OSReview\_internal\sensor_bridge\SensorBridge.exe"
  if errorlevel 1 exit /b 1
  if exist "dist\OSReview\_internal\sensor_bridge\SensorBridge.exe.sha256" (
    ".venv\Scripts\python.exe" -c "import hashlib,pathlib;p=pathlib.Path('dist/OSReview/_internal/sensor_bridge/SensorBridge.exe');p.with_suffix('.exe.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n',encoding='ascii')"
    if errorlevel 1 exit /b 1
  )
)
signtool sign /sha1 "%OSREVEW_SIGN_CERT_SHA1%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "dist\OSReview\OSReview.exe"
if errorlevel 1 exit /b 1
signtool verify /pa /v "dist\OSReview\OSReview.exe"
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -c "import hashlib,pathlib; p=pathlib.Path('dist/OSReview/OSReview.exe'); p.with_suffix('.exe.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n',encoding='ascii')"
if errorlevel 1 exit /b 1
echo Assinatura validada. Isso NAO garante ausencia de alertas do SmartScreen ou antivirus.
exit /b 0
