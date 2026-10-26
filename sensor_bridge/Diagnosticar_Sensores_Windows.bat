@echo off
setlocal
cd /d "%~dp0\.."
title OSReview - Diagnostico da ponte de sensores
if not exist "sensor_bridge\SensorBridge.exe" (
 echo ERRO: motor de sensores ainda nao compilado.
 echo Execute sensor_bridge\Preparar_Motor_Sensores_Windows.bat com .NET SDK 8 instalado.
 pause
 exit /b 1
)
if not exist "sensor_bridge\SensorBridge.exe.sha256" (
 echo ERRO: manifesto SHA256 do motor ausente.
 pause
 exit /b 1
)
where py >nul 2>&1
if not errorlevel 1 (set "PY=py -3") else (set "PY=python")
%PY% -c "from osreview.services.bridge_integrity import find_trusted_bridge; e,s=find_trusted_bridge(); print('INTEGRIDADE:',s); assert e is not None, 'Motor recusado'"
if errorlevel 1 (echo Falha na verificacao de integridade.&pause&exit /b 1)
echo Fazendo uma unica leitura local do sensor (sem envio pela internet)...
"sensor_bridge\SensorBridge.exe" >"sensor_bridge\resultado_sensores_local.json" 2>"sensor_bridge\erro_sensores_local.txt"
if errorlevel 1 (
 echo Motor executou com erro. Consulte sensor_bridge\erro_sensores_local.txt
) else (
 echo Resultado salvo em sensor_bridge\resultado_sensores_local.json
 echo Confira se existe o campo "sensors" com valores no arquivo.
)
echo ATENCAO: este relatorio pode conter nomes de componentes da maquina.
echo Nao compartilhe o arquivo completo em lugares publicos.
pause
