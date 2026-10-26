# Arquitetura atual

- `run.py` inicia logging, modo de diagnóstico e interface Tkinter.
- `osreview/app.py` e `osreview/enhanced_app.py` implementam a interface e orquestram trabalhos em threads.
- `osreview/services/` contém coletores, normalização, diagnóstico, rede, histórico e relatório de suporte.
- `sensor_bridge/` é um processo .NET 8 separado que fornece leituras LibreHardwareMonitorLib no Windows. A interface verifica um manifesto SHA-256 antes de iniciá-lo; isso não equivale a assinatura de editor.
- `fps_engine/` prepara o motor PresentMon, verificado por SHA-256 durante o build.
- `installer/windows/` contém a definição Inno Setup que empacota a pasta `dist/OSReview`.

O fluxo de dados de temperatura passa por `energy_sensors.py` e `sensor_analysis.py`. Metadados térmicos NVMe e margens para TjMax são excluídos da maior temperatura medida. A UI e o diagnóstico consomem o mesmo snapshot de energia. O helper com elevação seletiva e IPC autenticado ainda é uma evolução pendente.
