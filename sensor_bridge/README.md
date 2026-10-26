# Ponte de sensores interna — OSReview

A ponte SensorBridge foi desenvolvida para o OSReview e **utiliza como
biblioteca de terceiros** o projeto `LibreHardwareMonitorLib`, versão 0.9.6.
Não é uma versão modificada do aplicativo de interface LibreHardwareMonitor.

- Créditos: LibreHardwareMonitor e contribuidores
- Licença da biblioteca: MPL 2.0
- Repositório oficial: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor
- NuGet: https://www.nuget.org/packages/LibreHardwareMonitorLib/0.9.6
- Aviso de terceiros: `../licenses/NOTICE-LIBREHARDWAREMONITOR.txt`

A compilação para Windows usa o .NET SDK 8+ e restaura a biblioteca
pelo NuGet oficial via TLS. A ponte é um executável local que devolve
JSON ao OSReview. Não transmite dados de hardware pela Internet.
Alguns sensores requerem permissões de administrador e/ou drivers
compatíveis. Não desative antivírus para habilitá-los.

## Log v0.7.2

A saída JSON inclui `hardware` (componentes reconhecidos), `unavailable`
(sensores sem valor), `missingCount`, `warnings` e `sensors` válidos.

A coleta não altera temperaturas, tensões ou controles da placa-mãe. Sensores
ausentes podem resultar de modelo não suportado, permissões ou bloqueio de
driver pelo Windows/antivírus. O relatório do painel ajuda a distinguir essas
causas, mas não substitui medição elétrica e não exige desativar proteções.
