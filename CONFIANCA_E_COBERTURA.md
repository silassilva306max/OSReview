# OSReview — Fontes, proteção e limites

## Resultado da verificação documental (23/10/2026)

**LibreHardwareMonitor**: projeto aberto amplamente adotado com repositório oficial em https://github.com/LibreHardwareMonitor/LibreHardwareMonitor e biblioteca https://www.nuget.org/packages/LibreHardwareMonitorLib/0.9.6. Suporta diversas CPUs, GPUs, placas-mãe e unidades de armazenamento. Não garante todos os sensores; algumas leituras usam driver e privilégios.

**Microsoft Windows**: WMI, COM, APIs de eventos e Performance Counters são métodos oficiais para coleta de dados de hardware e sistema. Exemplo de contingência para SSD: https://learn.microsoft.com/en-us/windows-hardware/drivers/storage/msft-storagereliabilitycounter.

**PowerShell**: é um componente legítimo do Windows e integra o AMSI. Porém, a ocorrência de uma detecção heurística com `-EncodedCommand` justifica remover esse padrão de uso do OSReview. Não é necessário reintroduzi-lo porque as APIs nativas preservam os dados fundamentais. Qualquer consulta complementar deve ser auditável, com parâmetros fixos, e não tentar evitar inspeção da proteção.

## Modelo de confiança

1. Bibliotecas de origem conhecida e versão controlada; download HTTPS nas fontes oficiais.
2. Coleta por APIs locais do SO antes de componentes que acessam diretamente hardware.
3. Para sensor bridge: verificar SHA-256 contra manifesto local ANTES de executar. Isto previne alteração acidental/tampering isolado, não é validação da identidade do fornecedor.
4. Para distribuição: assinar EXE principal e EXE de sensores com certificado comercial/serviço de assinatura vinculado a editor verificado. Verificar com `signtool verify /pa /v`. Não declarar que um arquivo sem assinatura foi autenticado.
5. Manter antivírus/SmartScreen/AMSI e não adicionar exceções gerais. Detectou? Quarentena e investigação. Falsos positivos devem ser enviados à Avast: https://www.avast.com/pt-br/submit-a-sample.
6. Não transmitir dados pessoais do inventário automaticamente: perguntas para IA são opt-in.
7. Registrar cobertura da coleta; ausência de fonte = "indisponível", não = zero.

## Matriz de cobertura

| Dado | Fonte prioritária | Reserva | Limite |
|---|---|---|---|
| CPU, frequência | psutil/WinAPI | WMI Win32_Processor | Clock instantâneo pode ser aproximado |
| RAM | psutil | WMI Win32_PhysicalMemory | SPD/temporizações profundas podem não ser expostas |
| GPU identificada | WMI Win32_VideoController | NVIDIA SMI / system_profiler macOS | Uso/VRAM Intel pode necessitar contadores específicos |
| Discos/tecnologia | MSFT_PhysicalDisk + Win32_DiskDrive | psutil volumes | Bus/RPM podem faltar |
| Temperatura disco | LibreHardwareMonitorLib | MSFT_StorageReliabilityCounter | Depende de firmware/controlador |
| VRM / temperatura CPU | LibreHardwareMonitorLib | psutil quando SO fornece | Alguns chips sem acesso público |
| GPU NVIDIA | LibreHardwareMonitorLib | nvidia-smi | Somente GPU NVIDIA compatível |
| Fonte ATX watts totais | Sensor da PSU se existir | Estimativa de orçamento identificada | Sem medidor físico não é medição real |
| Logs | Windows Event Log API | Win32 via WMI quando aplicável | Acesso sujeito a permissões |
| Atualizações | Windows Update COM | processos, eventos e serviços | Atividade parcial não confirma instalação |
| macOS bateria/energia | IOKit | psutil para bateria | Nem todo Mac fornece tensão/corrente |

## Assinaturas e reputação

Documentação oficial Microsoft: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation. Uma assinatura confiável ajuda a verificar editor e integridade, mas a reputação SmartScreen ainda depende de histórico. Uma versão recém-compilada pode ser alertada mesmo que assinada.

**Sem garantias absolutas:** não é possível prometer 100% de ausência de falsos positivos, nem 100% de sensores disponíveis para todos os dispositivos Windows/macOS.
