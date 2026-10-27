# OSReview v0.6.2 — Segurança e transparência

## Investigação do aviso do Avast

A v0.6.1 usava `powershell.exe -EncodedCommand` para obter informações WMI/CIM.
Execuções repetidas desse padrão podem aumentar a suspeita de sistemas de proteção comportamental.
**Não é possível afirmar, com base apenas na captura de tela, se a detecção partiu do OSReview.**

A v0.6.2 substitui as consultas comuns por WMI/COM (pacote pywin32), Event Log e Windows Update Agent.
Nenhum comando do PowerShell é iniciado pelo aplicativo Python nesta versão. Não há rotina para
contornar, desligar, criar exceções ou alterar o antivírus. A ferramenta opcional `SensorBridge.exe`
usa LibreHardwareMonitorLib e executa localmente, sem instalar drivers por conta própria.

### Antes de executar novamente

1. Não desative o Avast, não restaure o arquivo bloqueado e não inclua `powershell.exe` na lista de exceções.
2. No Avast, abra **Ver detalhes** e registre data/hora, caminho do arquivo e comando/processo relacionado.
3. Faça uma verificação completa do computador e inspecione os registros no Avast.
4. Execute a v0.6.2 **somente após** revisar o código-fonte, compilar na sua máquina e validar o hash.
5. Se houver nova detecção, interrompa o teste e submeta o arquivo à revisão oficial do Avast.

Portal oficial para envio de falso positivo: https://www.avast.com/pt-br/submit-a-sample

## O que não pode ser garantido

- Um projeto ainda em desenvolvimento não pode ser certificado como seguro por simples alteração de código.
- Análises automatizadas e compilação não substituem auditoria de segurança independente.
- Hash SHA-256 comprova integridade apenas em relação a um hash conhecido e confiável; não comprova que o arquivo é benigno.
- Assinatura de código com certificado válido comprova identidade e integridade, mas não garante ausência de alertas.
- Sem certificado de editor verificado não é possível aplicar autenticamente a assinatura de outro desenvolvedor.
- No macOS, é necessário assinar com **Developer ID** e enviar para notarização Apple antes da distribuição pública.

## Práticas implementadas

- Telemetria é local e não exige uma conta.
- Coletas via WMI/COM e Event Log são somente leitura.
- Testes de velocidade e descoberta de rede são iniciados pelo usuário.
- Atualizações de software e Windows Update não são instaladas automaticamente.
- No Windows, a verificação opcional de novas versões do OSReview faz uma requisição HTTPS à API pública de Releases do GitHub na abertura. Ela informa ao GitHub o endereço IP da conexão e a versão do OSReview no cabeçalho User-Agent; não envia métricas de hardware, histórico ou logs.
- O download do instalador exige ação do usuário. O aplicativo confere origem, tamanho e SHA-256 publicado pela Release, mas o instalador continua sem assinatura Authenticode nesta RC. A instalação abre o assistente após confirmação do usuário e da análise do Avast.
- O acesso remoto de IA continua opcional, mediante ação do usuário e chave de API própria.
- Informações de energia ausentes permanecem "Indisponível".
- Build Windows PyInstaller `--onedir` sem extração completa a cada execução.
- Auditoria estática opcional: `python tools/audit_security.py`.
- Script de verificação/assinatura disponibilizado para certificado real de titularidade do editor.

## Sobre LibreHardwareMonitor

Projeto: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor
Biblioteca: LibreHardwareMonitorLib, licencia MPL-2.0. Distribuições que incluam a biblioteca devem
respeitar os avisos de terceiros e as condições de redistribuição da licença.
O SensorBridge compila localmente com o SDK .NET 8 e NuGet; o Windows pode exigir permissões especiais para alguns sensores.

## Mac e energia

O macOS não disponibiliza publicamente a maioria das temperaturas internas em todos os modelos.
O OSReview consulta sensores expostos por `psutil` e leituras da bateria via IOKit (`ioreg`) quando disponíveis.
Potência calculada com tensão × corrente da bateria **não mede toda a fonte de alimentação**.
Não são solicitadas permissões elevadas para coletar esses dados, e leituras não disponíveis são sinalizadas.
