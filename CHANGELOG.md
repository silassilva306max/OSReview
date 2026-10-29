# v0.9.1 RC4 — pesquisa de eventos no navegador

- Um erro ou evento crítico selecionado pode ser pesquisado diretamente na web, sem token de IA, pela tela normal ou ampliada de Eventos.
- A busca oferece Google, Bing, DuckDuckGo e Brave Search, com navegador padrão, Edge, Chrome, Opera, Firefox ou Brave quando instalado.
- Apenas ID, origem e interpretação resumida entram na URL da pesquisa; a mensagem original do log fica no dispositivo.
- Os cinco temas escuros agora usam cores próprias em todas as superfícies, navegação, gráficos e estados; as versões claras mantêm fundos e bordas levemente tingidos e texto legível.
- Menus suspensos de tempo de benchmark e de velocidade, incluindo a lista de opções, mostram texto com contraste adequado em todos os temas.
- Removida a cópia redundante do prompt de desenvolvimento; a metodologia de benchmark foi preservada como documentação técnica.

# v0.9.1 RC3 — gráficos e janelas adaptáveis

- Gráficos de CPU/RAM e benchmark são redesenhados ao mudar o tamanho da janela. A visão geral e o benchmark rolam verticalmente quando necessário.
- Todas as telas passam a oferecer rolagem vertical do conteúdo completo. Tabelas e controles largos mantêm acesso por rolagem horizontal quando a janela é estreita.
- Os medidores de temperatura, ações de Rede, controles de FPS, opções de aparência e cards superiores se reorganizam para larguras menores.
- Janela inicial e tamanho mínimo foram ajustados para resoluções menores, mantendo o modo compacto e os temas claro/escuro.
- Corrigida a coleta nativa de erros e eventos críticos do Windows, com recuperação independente dos logs Sistema e Aplicativo.
- Tabela de eventos e cartões detalhados podem ser ampliados em tela cheia; textos se ajustam à largura disponível.
- Medidores de rede usam escala inicial 0–1000 Mbps e teste de 10 ou 20 segundos por sentido. Interface principal e velocidade negociada aparecem separadas de avisos de Wi-Fi e outros adaptadores.
- Instalador Windows oferece elevação persistente e opcional via UAC. A interface de atualizações oculta a origem do download, mantendo as verificações de integridade.

# v0.9.1 RC2 — rolagem por mouse e revisão da publicação pública

- A roda do mouse passa a rolar o painel ou a lista da página ativa quando o ponteiro está sobre títulos, botões e cards. A navegação lateral também rola sem apontar para a barra.
- O repositório público recebeu varredura de segredos, proteção contra push de credenciais, Dependabot, CodeQL, relato privado de vulnerabilidades e proteção do branch padrão. Os binários 0.9.0 saíram da árvore atual do Git; o histórico antigo foi mantido conforme escolha do proprietário.
- O workflow da Release fixa Actions por SHA e concede escrita ao GitHub somente no job de publicação. A Release reúne o instalador Windows x64 e os DMGs macOS Intel e Apple Silicon após os três builds concluírem.

# v0.9.1 RC1 — atualizações do OSReview pelo GitHub

- Verificação de Releases oficiais em segundo plano ao abrir no Windows, com opção de desligar e de incluir ou excluir versões de teste.
- Aviso de nova versão na interface, download iniciado pelo usuário, progresso, conferência de tamanho e SHA-256 e nova verificação antes de abrir o instalador.
- Confirmação explícita de que o Avast terminou a análise; o assistente Inno Setup atualiza a instalação anterior na mesma pasta. Cópias portáteis recebem um aviso de que não serão substituídas automaticamente.
- Workflow Windows prepara instalador e ZIP portátil e publica os arquivos na Release correspondente quando a tag `v0.9.1-rc.1` é enviada ao GitHub.
- A versão 0.9.0 precisa ser atualizada manualmente uma vez para receber esse recurso.

# v0.9.0 RC — build Windows x64 e estabilização

- Interface com cinco paletas de cores em modos escuro e claro, barras de rolagem atualizadas, medidores de download/upload redesenhados e botão **Sair do OSReview** na tela principal.
- Benchmark de CPU e RAM com duração selecionável de 3, 5 ou 10 minutos, gráfico de amostras, pontuação interna, estabilidade e histórico local. A pontuação é comparável apenas ao mesmo método do OSReview.
- Cards de CPU/GPU mostram frequência atual e a faixa observada da CPU; potência de GPU medida em zero continua visível como `0.00 W`.
- Telas de Processos e Windows/Serviços oferecem fechamento de janela, encerramento explícito, reabertura do último executável após sua saída e início/parada de serviços de terceiros, com confirmação e bloqueio de itens protegidos. A tela de serviços inclui atalho para aplicativos e processos.
- Reduzida a frequência de varredura de processos quando a tela está oculta; gráficos e tabelas só redesenham enquanto visíveis. Pré-visualizações antigas sem uso foram removidas de `assets/`.
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
