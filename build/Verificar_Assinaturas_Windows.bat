@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0\.."
if not exist "dist\OSReview\OSReview.exe" (
  echo ERRO: EXE nao encontrado. Execute primeiro Gerar_EXE_Windows.bat
  exit /b 1
)
where signtool.exe >nul 2>&1
if errorlevel 1 (
  echo Signtool do Windows SDK nao encontrado. Resultado: identidade do editor NAO VALIDADA.
  exit /b 2
)
echo Verificando assinatura do executavel principal...
signtool verify /pa /v "dist\OSReview\OSReview.exe"
if errorlevel 1 (
  echo Assinatura AUSENTE ou INVALIDA: distribuicao nao pode ser marcada como autenticada.
  exit /b 1
)
if exist "dist\OSReview\_internal\sensor_bridge\SensorBridge.exe" (
  echo Verificando assinatura da ponte de sensores...
  signtool verify /pa /v "dist\OSReview\_internal\sensor_bridge\SensorBridge.exe"
  if errorlevel 1 (
    echo Assinatura da ponte AUSENTE ou INVALIDA: nao distribuir como assinada.
    exit /b 1
  )
  if exist "dist\OSReview\_internal\sensor_bridge\SensorBridge.exe.sha256" (
    if not exist ".venv\Scripts\python.exe" (
      echo Python do projeto indisponivel para conferir SHA-256.
      exit /b 2
    )
    ".venv\Scripts\python.exe" -c "from pathlib import Path;from osreview.services.bridge_integrity import inspect_bridge;p=Path('dist/OSReview/_internal/sensor_bridge/SensorBridge.exe');i=inspect_bridge(p,platform_name='Windows');print(i['integrity']);raise SystemExit(0 if i['allowed'] else 1)"
    if errorlevel 1 exit /b 1
  )
)
echo OK: assinaturas verificadas com politica padrao Authenticode.
echo ATENCAO: assinatura NAO equivale a exame antivírus ou ausencia de malware.
exit /b 0
