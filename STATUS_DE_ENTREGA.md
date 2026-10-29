# Estado da entrega — 29/10/2026

## Versão 0.9.1 RC4 — busca web de eventos e temas completos

- Eventos do Windows selecionados podem ser pesquisados sem token de IA em Google, Bing, DuckDuckGo ou Brave Search, no navegador padrão ou em navegador instalado. A URL contém apenas ID, origem e resumo local do erro; a mensagem original permanece local.
- Armadura, Máquina de Combate, ROG, Grafite e Ciber agora mudam superfícies, barra lateral, cartões, bordas, gráficos, indicadores e janelas auxiliares nos modos claro/escuro. Menus de tempo do benchmark e da rede têm texto e lista com contraste corrigido.
- Removido `PROMPT_MESTRE_CODEX.md`, cópia idêntica de `AGENTS.md`. `METODOLOGIA_BENCHMARK.md` foi mantido para explicar os resultados e permitir sua interpretação.
- Suíte local: **156 testes aprovados, 1 ignorado**. Teste da interface em dez combinações de temas e 21 telas em quatro resoluções passou. Pacote Windows validado estaticamente; o executável RC4 ainda aguarda a análise final do Avast antes da execução local.
- A restauração NuGet local não respondeu neste ambiente. O pacote RC4 foi montado com a ponte de sensores já compilada e verificada pelo SHA-256, sem alteração no código C#; o GitHub Actions fará o build completo. Setup local SHA-256 `2dcf0f57cf5c7dfd37c2b198dd237667b0aa151376d90a4df18e9033ee18462d`; portátil `c15e121ae45544b483a650afcdf8749b2a43185fd37b218411e1327cd63bebd1`.

## Versão 0.9.1 RC3 — eventos, rede e interface

- Release pública: https://github.com/silassilva306max/OSReview/releases/tag/v0.9.1-rc.3. Contém Setup e ZIP portátil Windows x64, DMGs macOS Intel e Apple Silicon e quatro arquivos SHA-256. O workflow `40552101286` concluiu os três builds e a publicação; os hashes dos arquivos SHA-256 conferem com os digests publicados pelo GitHub.
- Corrigida a leitura de erros e eventos críticos do Windows: a consulta local retornou oito registros reais no teste. Os cartões e a lista de eventos podem ser ampliados em tela cheia; o layout das 21 telas foi verificado em 980×600, 1024×768, 1280×720 e 1600×900.
- Medidores de download e upload têm escala inicial de 0 a 1000 Mbps e medição selecionável de 10 ou 20 segundos por sentido. A interface principal é separada dos avisos de adaptadores secundários. Neste PC, o Windows informa Ethernet ativa com link negociado em 100 Mbps; não foi realizado teste de vazão real de 1 Gb/s.
- O instalador oferece UAC opcional ao abrir o app, desmarcado por padrão. A interface não mostra a origem dos downloads de atualização, preservando a verificação de HTTPS, origem e SHA-256.
- Suíte local: **148 testes aprovados, 1 ignorado**; build local Windows compilado. O usuário confirmou a análise pelo Avast do Setup local final. O executável empacotado passou em `--diagnostico`, abriu a janela principal e permaneceu ativo durante a checagem curta. A automação de captura visual do Windows não conectou ao desktop nesta sessão.
- O Setup local tem SHA-256 `20d839e8e634086b3c8ade396159b54ebd721199763a3fd7e29c7ad6faad1a57`. O Setup do GitHub Actions tem hash diferente por ter sido compilado em outro ambiente; seu SHA-256 está publicado e conferido na Release.

## Versão 0.9.1 RC2 — instaladores Windows e macOS

- Release pública: https://github.com/silassilva306max/OSReview/releases/tag/v0.9.1-rc.2. Contém Setup Windows x64, ZIP portátil, DMG macOS Intel e DMG macOS Apple Silicon, com os quatro respectivos SHA-256.
- Execução definitiva do GitHub Actions `40544925083`: Windows, Mac Intel, Mac Apple Silicon e publicação concluídos com sucesso. Os quatro arquivos SHA-256 foram confrontados com os digests da API do GitHub.
- Corrigidos o teste de serviço Windows executado no Mac, a entrada principal isolada do Swift e a falha intermitente `hdiutil: Resource busy` no runner Intel.
- O teste empacotado `--diagnostico` passou no Windows do GitHub Actions; a suíte local teve 143 testes aprovados e 1 ignorado. A análise local pelo Avast foi confirmada pelo proprietário. A automação visual do Windows ficou indisponível nesta sessão, e a instalação interativa em Mac físico ainda precisa de validação.
- Os instaladores não têm assinatura Authenticode nem notarização Apple. Sensores/FPS exclusivos do Windows não funcionam no Mac.

## Versão 0.9.1 RC1 — atualizador Windows

- Repositório `silassilva306max/OSReview` confirmado público pela API do GitHub em 27/10/2026. Commit `42fefd1` e tag `v0.9.1-rc.1` enviados. Release pública: https://github.com/silassilva306max/OSReview/releases/tag/v0.9.1-rc.1.
- Na abertura do app Windows, verificação opcional de versões em segundo plano. A interface avisa sobre uma versão nova e oferece download iniciado pelo usuário, barra de progresso, cancelamento e abertura confirmada do instalador após a análise do Avast.
- Downloads aceitos apenas da Release oficial do projeto, por HTTPS, com nome esperado, limite de tamanho e SHA-256 informado pela API do GitHub; conferência repetida antes da instalação. Nenhuma credencial é embutida.
- Instalador Inno preserva o AppId anterior, usa a pasta de instalação existente e fecha aplicativos em uso. Cópias portáteis exibem aviso porque não são sobrescritas pelo instalador.
- Testes de código: **140 aprovados, 1 ignorado**. O build local compilou ponte .NET, pacote PyInstaller, instalador Inno e ZIP portável. O validador de pacote passou.
- Instalador: `release/OSReview-Setup-0.9.1-rc.1-Windows-x64-NAO-ASSINADO.exe` (41.863.407 bytes), SHA-256 `17756c7f977d2018382efd45c6be7400070d5cbb15e57f6746e6a09dbcb829e5`.
- Portátil: `release/OSReview-Portable-0.9.1-rc.1-Windows-x64.zip` (54.717.683 bytes), SHA-256 `58ff5692c82d1c1b8c60e33f54a0ea647614442eb35b81294a7f4e7bf8ed3c2c`.
- O job Windows do GitHub Actions `40520331734` terminou com sucesso e publicou o instalador (43.263.954 bytes, SHA-256 `79bbb7a643175e32dcf9c946c56aa64e3ad315eb52d502a180b365633c709758`) e o ZIP portável (57.156.089 bytes, SHA-256 `218c91ef3c6d944fcf8aba860acaebf320a4a75f18b445240308dce5299910b7`). O parser do atualizador leu a Release real, e o download público do instalador terminou com o SHA-256 correto, sem executá-lo.
- Os jobs macOS desse workflow falharam; não há DMG validado nesta versão. O resultado global do workflow pode aparecer como falha apesar do job Windows bem-sucedido.
- Pendente: esperar o Avast concluir a análise dos binários locais, validar visualmente o aplicativo novo e testar o fluxo completo de instalação/atualização em uma instalação existente. O usuário informou que o Avast ainda analisava o novo instalador; nenhum executável novo foi aberto localmente.

## Implementado e testado localmente

- Base 0.8.1 importada sem remover os módulos existentes. Git inicializado, tag `baseline-v0.8.1`, branch `release/v0.9.0-rc`.
- Versão 0.9.0 RC aplicada ao aplicativo, metadados do executável e instaladores.
- Suíte inicial: **121 aprovados, 3 falhas, 1 ignorado** em Python 3.14.6 / Windows 11 x64. Uma consulta opcional WMI gerou exceção nativa no teste inicial.
- Suíte após auditoria e correções: **128 aprovados, 1 ignorado**, sem falhas.
- Revisão de interface e controles em 27/10: **135 aprovados, 1 ignorado**. Os novos testes cobrem duração/resultado de CPU e RAM, interrupção, relógios medidos, zero watt real, cinco paletas, bloqueio de serviços protegidos e prevenção de reabertura duplicada. Compilação Python e `git diff --check` passaram.
- Cinco paletas em temas escuro/claro; botão Sair na tela principal; novos medidores de rede; benchmark CPU/RAM com durações 3/5/10 minutos, gráfico, estabilidade e histórico. Metodologia em `METODOLOGIA_BENCHMARK.md`.
- Processos e serviços: fechamento de janela, encerramento forçado, reabertura do último executável após sua saída, início/parada de serviços de terceiros com confirmação. A tela de serviços abre diretamente a lista de aplicativos/processos. Ações reais de alteração do sistema não foram automatizadas nos testes.
- Coleta de processos oculta reduzida; gráficos/tabelas redesenhados apenas na tela ativa. Dez imagens de prévia sem referências foram removidas de `assets/`; ícones e artefatos de diagnóstico foram preservados.
- `SensorBridge.exe` compilado como .NET 8 self-contained com LibreHardwareMonitorLib 0.9.6 da cache NuGet local.
- PresentMon 2.6.0 obtido da publicação oficial e aceito pelo SHA-256 fixado em `fps_engine/preparar_motor_fps.py`.
- `build/validar_pacote_windows.py`: aprovado; pacote PyInstaller inclui executável, ponte, manifesto, motor FPS e nenhum `.bat`, `.cmd` ou `.ps1`.
- `dist/OSReview/OSReview.exe --diagnostico`: exit code 0; ZIP de diagnóstico gerado.
- Janela principal do executável empacotado abriu em Windows 11 x64 e respondeu. Foram observadas as telas de Energia, explorador de sensores e Processos. O primeiro teste dentro do sandbox falhou porque o Tcl nativo não conseguia resolver caminhos virtualizados; a leitura e a abertura funcionaram fora desse isolamento.
- Ponte de sensores real, sem elevação: 6 dispositivos, 50 leituras válidas, 34 ausentes e nenhuma temperatura válida. A interface exibiu `Indisponível` para temperaturas não medidas.
- Corrigidos rolagem/seleção da tabela de processos e seleção de temperatura real/recente no painel compacto. Auditoria detalhada em `AUDITORIA_FUNCIONAL.md`.
- Card de RAM passou a mostrar memória disponível/total e frequência configurada da memória, usando `psutil` e inventário `Win32_PhysicalMemory`. Os coletores isolados reportaram 6,43/15,69 GB e 3200 MHz nesta máquina; o último build ainda não teve inspeção visual após análise do Avast.
- Instalador Inno Setup final após a revisão de navegação e reabertura: `release/OSReview-Setup-0.9.0-Windows-x64-NAO-ASSINADO.exe` (41.829.676 bytes). SHA-256: `6acb9076982f90748971f17b82661117f0b98d8d2b8562c675c7c277d3d7b191`.
- Pasta portátil final em `release/OSReview-Portable-0.9.0-Windows-x64.zip` (54.875.686 bytes). SHA-256: `e32ab573a9d5ccd4001099b1010c17d3889e36367f1e0da92735efb0f554b1a0`.

## Pendente após a RC3

- Fazer inspeção visual interativa da RC3 no Windows (temas, benchmark, controles, card de RAM e bandeja); o teste de inicialização não substitui esse percurso.
- Testar instalação e desinstalação em Windows x64 limpo sem Python e .NET instalados. O build local não prova esse cenário.
- Assinatura Authenticode: nenhum certificado de editor foi fornecido. O instalador gerado está claramente marcado **NAO-ASSINADO**.
- Validar sensores em hardware real com e sem privilégios; o helper elevado opcional com IPC autenticado ainda não está implementado.
- Isolar consultas WMI/COM do processo gráfico: o log local registrou exceção nativa de acesso durante consulta de GPU, apesar da janela ter aberto.
- Validar a instalação interativa dos DMGs Intel e Apple Silicon em Macs físicos.
- Validar visualmente todos os módulos e concluir as melhorias funcionais extensas do prompt mestre antes de chamar a versão de 1.0.
