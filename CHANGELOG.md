# v0.9.0 RC — build Windows x64 e estabilização

- Card de memória agora mostra capacidade disponível/total e frequência configurada dos módulos quando o Windows a informa; sinaliza frequência nominal, mista ou ausente com clareza.
- Minimizar a janela envia o app para a bandeja quando essa opção está ativa; painel ao passar o mouse mostra também o tráfego de rede.
- Compilados `OSReview.exe`, ponte .NET 8 self-contained e instalador Inno Setup em Windows x64.
- Corrigidos os testes de fallback de velocidade, estado de rede sem gateway coletado e leitura UTF-8 do instalador macOS.
- Removida a consulta opcional de hotfixes por WMI que provocou falha nativa no Python 3.14 deste ambiente.
- Removida da interface de FPS a orientação para o usuário executar script de build.
- Criado registro verificável da validação e das pendências de distribuição.

# v0.8.1 — Instalação sem dependências e assistente gráfico

- Removidos inicializadores `.bat` da raiz; usuários finais executam binários nativos.
- Motor de sensores .NET 8 self-contained; Python incorporado no PyInstaller.
- Inno Setup com pasta configurável, atalho e login opcionais; sem downloads do runtime.
- Instalador macOS nativo AppKit com seleção da pasta, atalho da Mesa e LaunchAgent opcionais.
- Distinção explícita entre código-fonte e instaladores finais não assinados.
- Atualizado workflow de distribuição para v0.8.1.

# v0.8.0 — Distribuição multiplataforma e opções de instalação

- Instalador Inno Setup para Windows x64, com escolha do destino, atalhos e inicialização no login opcionais.
- Compilador Python + .NET 8 da ponte de sensores e captura de FPS, mantendo SHA-256 da ponte e PresentMon.
- Empacotamento do `.app` macOS em DMG para Intel x86_64 e Apple Silicon ARM64.
- Instalador `.command` para Mac: escolhe pasta gravável, atalho Mesa e LaunchAgent de login opcionais.
- Opção "Iniciar com o sistema" no painel funciona tanto no Windows quanto no Mac.
- Ícones .ico e .icns; metadados de versão do aplicativo atualizados para 0.8.0.
- GitHub Actions compila os três pacotes em runners de OS/arquitetura respectivos, sem publicar código automaticamente.
- Componentes mantêm créditos/licenças e assinatura é explicitamente dependente de certificados próprios do editor.

# OSReview v0.7.5
- 8 novos cards no dashboard principal, incluindo consumo por domínio e energia geral com indicação honesta de indisponibilidade.
- Filtro explícito de limites de temperatura NVMe e margens para TjMax: não tratados como leituras atuais.
- Correção do falso SSD 89 °C (limite crítico); sensor real Composite Temperature foi 37 °C no relatório analisado.
- Tela Diagnóstico reformulada com status, gravidade, leitura de CPU integrada ao motor LHM e interpretação de SSD/potência, rolagem preservada.
- Tela Energia aprimorada: cartões energéticos, sensor de origem, medição maior com proveniência, seletores de detalhes e atualização sem reset de posição.
- Inventário e exportação distinguem temperaturas medidas de referências; versão de exportação sincronizada.
- 113 testes automatizados aprovados.

# v0.7.4
- Rolagem dos cards preservada mesmo com atualizações.
- Detalhes congelados por padrão; medidores ao vivo.
- Explorador de sensores independente e filtrável; atualização manual.
- Interpretação do relatório e aviso sobre zero watt não confiável.
- Exportação técnica enriquecida e normalização de capacidade de bateria em mWh.
- Testes automatizados e teste gráfico do explorador.

# CHANGELOG

## v0.7.2 — Exportação de log dos sensores e diagnóstico de energia
- Novo botão **Exportar log dos sensores** na aba Energia: JSON criado localmente, após confirmação.
- Ponte C# mantém catálogo de hardware e sensores enumerados sem valor, além de leituras válidas.
- Recolhimento de falhas e stderr do coletor sem bloquear a comunicação.
- Botão **Reiniciar motor**: reinicia apenas a ponte local; não altera drivers/serviços.
- Diagnóstico por componente e indicações de sensores faltantes no dashboard.
- Alternativa WMI passiva e opcional para Open Hardware Monitor original já ativo (créditos no painel).
- Sanitização de informações pessoais comuns no relatório e testes de regressão.
- Sensores ausentes continuam como indisponíveis; nenhuma potência total da fonte é inventada.

# Histórico de versões — OSReview

## v0.7.1 — revisão de temperaturas, FPS e identificação do provedor

- Sensores agrupados prioritariamente pelo `HardwareType` informado pelo LibreHardwareMonitorLib (CPU, GpuIntel/GpuAmd/GpuNvidia, Storage, Memory, Motherboard/SuperIO).
- Quadro de cobertura com total por **tipo de sensor**: Temperature, Clock, Load, Voltage etc. Um motor com 51 sensores ativos não é necessariamente um motor com temperatura disponível.
- Leitura adicional de **zonas térmicas ACPI** do Windows (se o fabricante as expuser). Uma zona ACPI é exibida como temperatura **geral do sistema**, nunca como temperatura real da CPU.
- Quarto medidor térmico **Geral**; inspeção dos sensores classificados como Outros e visualização do dispositivo/hardware de origem.
- Indicação de execução elevada ou padrão (somente leitura). Nenhuma elevação de privilégios, exclusão de antivírus ou instalação de driver automática.
- FPS: seleção dos processos com janelas visíveis, botão Atualizar lista, referência especial a `dwm.exe` e leitura da taxa configurada do monitor em Hz (não corresponde a FPS real).
- Rede: identificação **opcional** da organização / ASN do IP público usando HTTPS ipapi.co, com consentimento/ação explícita (também iniciada por escolha voluntária dos testes externos). A informação pode divergir do nome comercial do contrato, especialmente sob VPN/proxy/CGNAT.
- Inicialização Windows: pula a reinstalação via pip quando as dependências já estiverem presentes. Avisos sobre PATH são explicados como informativos.
- Testes de regressão atualizados e novas verificações para as melhorias.

## v0.7.0 — sensores persistentes, FPS e identidade visual

- Integração preparada com LibreHardwareMonitorLib; motor de FPS baseado no Intel PresentMon; identidade OSReview.

## v0.7.3 — Correção emergencial de inicialização e diagnóstico de sensores
- Tratamento de exceções durante a criação da interface e registro de erros Tk e threads.
- Arquivos de falha persistentes em `%LOCALAPPDATA%\OSReview\logs` no Windows.
- Script `Diagnosticar_Inicializacao.bat`, capaz de gerar ZIP sem abrir a interface.
- Script `Iniciar_Modo_Seguro.bat` para isolar coletores opcionais e bandeja.
- Botão **Pacote de suporte (.zip)** na área Energia e temperaturas.
- Motor de sensores pode tentar reconectar após ausência de ponte ou fim do processo.
- Log periódico de contagem de sensores, temperaturas e potência (sem enviar valores ou dados pela Internet).
- Proteção adicional contra erros de renderização de sensores na tela.
