@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0\.."
title OSReview - Preparar motor integrado LibreHardwareMonitorLib
if not exist "sensor_bridge\SensorBridge.csproj" (
 echo ERRO: extraia completamente o ZIP.
 pause
 exit /b 1
)
where dotnet >nul 2>&1
if errorlevel 1 (
 echo O SDK .NET 8 ou superior nao foi encontrado.
 echo Instale pela pagina OFICIAL: https://dotnet.microsoft.com/download/dotnet/8.0
 echo Isto serve apenas para construir a ponte; nao instale nenhum monitor de terceiros.
 pause
 exit /b 1
)
echo.
echo Biblioteca de TERCEIROS: LibreHardwareMonitorLib 0.9.6
 echo Direitos: LibreHardwareMonitor e contribuidores - licenca MPL 2.0.
echo Fonte oficial: https://www.nuget.org/packages/LibreHardwareMonitorLib/0.9.6
echo OSReview e independente; confira licenses\NOTICE-LIBREHARDWAREMONITOR.txt.
echo.
echo [1/3] Obtendo dependencias declaradas somente da fonte NuGet.org via HTTPS...
dotnet restore "sensor_bridge\SensorBridge.csproj" --source "https://api.nuget.org/v3/index.json" -r win-x64
if errorlevel 1 goto :erro
echo [2/3] Compilando ponte local, integrada ao OSReview...
dotnet publish "sensor_bridge\SensorBridge.csproj" -c Release -r win-x64 --self-contained true --no-restore -p:PublishSingleFile=true -p:PublishTrimmed=false -o "sensor_bridge\publish"
if errorlevel 1 goto :erro
if not exist "sensor_bridge\publish\SensorBridge.exe" goto :erro
copy /Y "sensor_bridge\publish\SensorBridge.exe" "sensor_bridge\SensorBridge.exe" >nul
if errorlevel 1 goto :erro
echo [3/3] Conferindo hash SHA-256 do arquivo local...
where py >nul 2>&1
if not errorlevel 1 (
 py -3 -c "import hashlib,pathlib; p=pathlib.Path('sensor_bridge/SensorBridge.exe'); p.with_suffix('.exe.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n',encoding='ascii')"
) else (
 python -c "import hashlib,pathlib; p=pathlib.Path('sensor_bridge/SensorBridge.exe'); p.with_suffix('.exe.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n',encoding='ascii')"
)
if errorlevel 1 goto :erro
echo.
echo Motor integrado preparado. Abra o OSReview e clique Atualizar sensores.
echo A ponte foi compilada localmente; ela NAO possui assinatura digital ate ser assinada com certificado legitimo.
echo Nao adicione excecoes no antivirus. Se houver bloqueio, consulte o motivo antes de permitir o arquivo.
pause
exit /b 0
:erro
echo ERRO ao preparar a ponte. Nenhuma configuracao de seguranca foi alterada.
pause
exit /b 1
