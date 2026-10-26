# PROMPT MESTRE — OSReview | Codex no VS Code

Você será o **engenheiro principal, arquiteto de software, especialista em Windows/macOS, observabilidade, telemetria de hardware, segurança de aplicações, interfaces desktop e distribuição de software** do projeto **OSReview**.

## MISSÃO E REGRA PRINCIPAL

Quero que você **trabalhe diretamente no código do projeto aberto no VS Code e entregue software funcional**, não apenas uma proposta ou mockup. O repositório-base é **OSReview v0.8.1**, evoluído historicamente desde OSRevew v0.1.0 (nome antigo). Nome oficial e definitivo: **OSReview**. Crie a próxima versão incremental **v0.9.0 (release candidate)**; só classifique como 1.0 após validação real de instalação e diagnóstico.

**Não recomece do zero** nem substitua a aplicação por um protótipo sem as funções existentes. Faça primeiro uma auditoria do repositório, preserve seu histórico e todos os módulos úteis, corrija problemas e implemente as lacunas. Se for indispensável refatorar a interface, faça migração progressiva e sem perda de funcionalidade. Não declare recursos “funcionais” sem teste, não invente dados de sensores, não mascare falhas e não confunda testes simulados com validação em máquina real.

O usuário final não deve precisar executar `.bat`, PowerShell, Terminal, instalar Python ou .NET SDK/runtime à parte. O resultado esperado é um aplicativo com interface profissional e instaladores nativos de fácil utilização.

## 0. AÇÕES OBRIGATÓRIAS AO INICIAR

1. Confirme a presença dos arquivos do OSReview v0.8.1 no workspace. Se o workspace estiver vazio, oriente apenas a extrair/abrir a pasta do ZIP original; não gere um sistema incompatível sem a base.
2. Inspecione `README.md`, `CHANGELOG.md`, `GUIA_INSTALACAO.md`, `SEGURANCA_E_PRIVACIDADE.md`, `requirements.txt`, `run.py`, `osreview/`, `sensor_bridge/`, `fps_engine/`, `installer/`, `build/`, `tests/` e `.github/workflows/`.
3. Examine riscos de bugs, bloqueios de GUI, permissões, comandos de shell, dependências, arquitetura multiplataforma, dados duplicados, contradições nas telas e falhas de empacotamento.
4. Inicialize Git, se necessário, e preserve uma referência `baseline-v0.8.1`. Crie um branch para v0.9.0. Não apague históricos, testes, licenças nem artefatos de diagnóstico.
5. Rode os testes existentes e registre o resultado inicial. A última validação do projeto-base reportou **125 testes Python aprovados**, mas reexecute-os no seu ambiente.
6. Crie `PLANO_DE_IMPLEMENTACAO.md`, `STATUS_DE_ENTREGA.md` e `CRITERIOS_DE_ACEITE.md`. Trabalhe por etapas e registre resultados verificáveis. Não se limite a escrever o plano: **implemente as alterações**.
7. Evite perguntas desnecessárias; tome decisões técnicas razoáveis, deixando claras as limitações e as permissões de segurança que requerem intervenção legítima do usuário.

## 1. ARQUITETURA A PRESERVAR E MELHORAR

Base existente:
- Desktop Python/Tkinter com módulos separados e `psutil`, `platformdirs`, `pywin32` no Windows e `pystray` para bandeja.
- Ponte Windows **C#/.NET 8** usando **LibreHardwareMonitorLib 0.9.6** (biblioteca de terceiros MPL 2.0), processo persistente, manifesto SHA-256 e coleta de sensores.
- Captura de FPS no Windows preparada com **Intel PresentMon** (código aberto, MIT), sem exigir que o usuário abra outro aplicativo.
- WMI/COM, Event Log e APIs oficiais Windows; fontes nativas macOS quando disponíveis.
- PyInstaller `--onedir` para aplicativo com Python incorporado; sensor bridge .NET **self-contained**; Inno Setup no Windows; `.app` e instalador gráfico no macOS; GitHub Actions para os três ambientes.

Reorganize em camadas claras: `UI → application/controllers → diagnóstico/correlação → adapters de plataforma → coletores → modelos normalizados/histórico`. Proponha e implemente contratos tipados para medições: `valor`, `unidade`, `tipo de componente`, `sensor`, `origem`, `timestamp`, `estado`, `confiabilidade`, `limite`, `permissão necessária`. Uma falha de um coletor nunca deve derrubar a interface. Faça polling em threads/async workers e atualize widgets somente pela thread gráfica. Trate timeouts e limitação de taxa; impeça várias varreduras ou benchmarks simultâneos por engano.

**Mac não é Windows**: não tente usar WMI, LibreHardwareMonitor Windows ou PresentMon Windows no macOS. Implemente adaptadores nativos equivalentes para o que o macOS realmente expõe e indique `Indisponível neste sistema` onde não houver API confiável. Não simule recursos exclusivos do Windows no Mac.

## 2. IDENTIDADE VISUAL E EXPERIÊNCIA DE USO

Usar o nome **OSReview**, ícone original do projeto (arquivos `.ico`, `.icns`, `.png` em `assets/`), identidade consistente em janela, barra de tarefas, bandeja, instalador e atalho. Dashboard profissional de diagnóstico em tema **escuro/claro**, com tipografia responsiva, contraste acessível, estados por cores discretas e aparência inspirada nos dashboards técnicos modernos de benchmark — sem copiar identidade visual de outro fabricante.

A interface deve ter barra lateral fixa e navegação por módulos, cards superiores em tempo real e duas camadas de explicação: **modo Simples** (linguagem clara para leigos, consequência e solução) e **modo Avançado** (processo, PID, sensor exato, métricas e evidências). Ofereça **modo completo**, **janela compacta** e **mini-popup ao passar o mouse no ícone da bandeja** no Windows, com CPU, RAM, temperatura e rede. Notificações configuráveis; opção de desativar; inicia com sistema somente por escolha do usuário.

**PROBLEMA REAL JÁ IDENTIFICADO:** a tela Energia/Temperaturas reconstruía conteúdo a cada atualização e a rolagem retornava ao início. Corrija definitivamente: atualização incremental apenas dos valores, sem recriar cards e widgets, mantendo seleção, filtros e rolagem. Mantenha um explorador de sensores independente, congelamento opcional dos detalhes, captura manual, busca, filtros por componente/tipo e atualização dos medidores principais em tempo real.

Cards obrigatórios no Dashboard principal, clicáveis para módulo detalhado: CPU (uso, frequência, temperatura); RAM (usada/total, pressão); armazenamento (capacidade, atividade, saúde); GPU/VRAM; rede (download/upload instantâneos); temperatura CPU; GPU; SSD; maior temperatura **real medida e sua origem**; potência medida CPU; potência medida GPU; energia/bateria; potência total da fonte **somente se houver sensor digital compatível**; saúde geral/alertas. Nunca invente watts totais da fonte. Exiba último horário de coleta e estado da fonte de cada métrica. Dashboard e tela Diagnóstico devem consumir **a mesma fonte normalizada** de sensores, evitando avisos contraditórios.

Telas/módulos: Dashboard; Diagnóstico e recomendações; Inventário de hardware; Placa-mãe/BIOS; Temperaturas/Energia; Rede/Internet; Scanner de IPs; Processos; Atividades de fundo; Logs/Eventos e interpretação; Segurança; Atualizações; Central de Soluções; Benchmark; FPS/Frametime; Histórico; Perguntas à IA; Configurações; Fontes e integridade; Sobre/Créditos. Preserve outras seções existentes.

## 3. HARDWARE — INVENTÁRIO FÍSICO COMPLETO

**CPU:** nome exato, fabricante, família/geração, núcleos físicos/lógicos, P/E cores quando possível, arquitetura, socket quando confiável, clocks base/atuais/turbo documentados, frequências por núcleo, carga, consumo e temperatura se reportados.

**GPU:** detecção independente de NVIDIA (não depender apenas de `nvidia-smi`), Intel UHD/Iris Xe integrada, AMD Radeon integrada/dedicada, NVIDIA dedicada; driver, versão, estado, memória dedicada/compartilhada separadas, VRAM, carga, clock, tensão, potência, temperatura quando disponíveis. Informar claramente o dispositivo dono do sensor.

**RAM:** total e por pente/slot, fabricante, modelo/part number, DDR4/DDR5, frequência real/configurada e SPD quando permitido, timings disponíveis, utilização/paginação e diagnóstico de pressão de memória. Não inferir defeito da RAM apenas por uso elevado.

**Armazenamento:** todos os discos e volumes, modelo, capacidade, serial mascarado no suporte, SSD NVMe vs SSD SATA vs HDD, barramento, RPM somente em HDD quando informado, saúde SMART/NVMe, percentual de desgaste, bytes escritos/lidos, temperatura, horas, erros, desempenho e volumes. Dispositivos USB/removíveis, tipo, modelo e capacidade. Cards por peça, jamais JSON bruto no painel comum.

**Placa-mãe e BIOS:** fabricante/modelo/revisão, chipset quando identificado com confiança, UEFI/BIOS, versão/data, opção de abrir fontes oficiais e compatibilidade de CPU, RAM e GPU. Compatibilidade precisa considerar modelo exato, revisão, BIOS mínima, suporte elétrico/térmico, firmware e documentação do fabricante: não decidir só pelo socket. Recomendações de atualização de BIOS por importância, correções de segurança, changelog oficial, relatos comunitários datados e links verificáveis; nunca afirmar “versão mais estável” sem evidências nem executar flash automaticamente.

## 4. TEMPERATURAS, VOLTAGENS, POTÊNCIA E FONTE — PRIORIDADE MÁXIMA

Integrar plenamente **LibreHardwareMonitorLib**, bibliotecas oficiais e interfaces nativas, preservando créditos do autor e licença. Garantir ponte persistente, diagnóstico de permissões, tratamento de bloqueios de driver/antivírus, hash e assinatura quando disponível, logs detalhados e reconhecimento de tipo de sensor/hardware. Usar a biblioteca legitimamente, sem instalar componentes suspeitos, liberar drivers vulneráveis, desligar Defender/Avast/UAC/Memory Integrity ou burlar antivírus.

**Histórico concreto reproduzido neste projeto:** no notebook Dell, Intel Core i5-1235U, Intel UHD, SSD NVMe ADATA, a coleta sem permissão elevada trouxe **51 sensores válidos, 33 sem valor, 0 temperaturas**; com execução administrativa autorizada passou a **135 leituras válidas, 8 dispositivos, 28 temperaturas e 0 leituras ausentes**. Isso demonstra a importância de privilegiar apenas o coletor, mediante UAC legítimo quando realmente necessário, mantendo a UI como usuário normal. Implementar arquitetura segura de **helper de sensores separado**, com elevação opcional, verificação de assinatura/integridade, IPC local autenticado, sem shell textual nem PowerShell oculto. Oferecer operação parcial sem privilégios quando o usuário recusar.

**BUG CRÍTICO HISTÓRICO (testar obrigatoriamente):** SSD `SM2P41C3Q ADATA 512GB` teve `Composite Temperature=37 °C`, `Temperature #1=36,85 °C`, `Temperature #2=39,85 °C`, `Warning Temperature=82 °C` e `Critical Temperature=89 °C`. O app anterior mostrava erroneamente 89 °C como temperatura real do SSD e do sistema. `Warning`/`Critical` são **limites**, não leituras correntes. Exibir separadamente e excluir do cálculo da maior temperatura. Para CPU, `Distance to TjMax` é margem térmica, não temperatura atual: também excluir do máximo. CPU Package real no log = **53 °C**. Maior temperatura medida nesse instante = 53 °C (CPU).

Energia já observada: CPU Package=**11,67 W** e CPU Platform=**21,13 W** em domínios possivelmente sobrepostos; **não somá-los** para representar a potência do computador. Na Intel UHD o sensor GPU Power apresentou **0,02 W** nessa amostra; zeros ou leituras insuficientes exigem contexto, não afirmar “placa sem consumo”. Fonte ATX comum não reporta potência total nem tensões reais ao Windows. Se não houver sensor digital, mostrar `Não medida`; oferecer calculadora de capacidade recomendada (W) como **estimativa** com margem, CPU/GPU, discos e uso pretendido, sem simular consumo real.

Bateria Dell: valores `42009` (projeto) e `40698` (carga completa) são geralmente **mWh** nas APIs Windows, equivalentes a aprox. 42,01 e 40,70 Wh quando aplicável. Mostrar desgaste (~3,12%), tensão e corrente quando reportadas, distinguindo mWh/Wh, W e A. Criar monitor de bateria com dados reais; não misturar com fonte ATX.

Sensores desejados: CPU pacote/núcleos, GPU, SSD/HDD, VRM, placa-mãe, chipset, RAM, ventoinhas (RPM), tensões, potência, baterias e fonte digital. Sempre mostrar `Indisponível` com motivo, sem estimativas falsas; usar leitura alternativa de `MSFT_StorageReliabilityCounter`, dados ACPI claramente identificados como zonas do sistema (não temperaturas da CPU) e APIs AMD/NVIDIA/Intel oficialmente suportadas quando útil. Expor valores atual/mínimo/máximo e gráfico temporal com reset de máximos/mínimos voluntário; limites térmicos com classificação por componente/dispositivo e origem.

## 5. DIAGNÓSTICO INTELIGENTE E GARGALOS

O OSReview deve explicar **o que está lento, quando começou, quais processos/serviços podem contribuir, evidência e ações seguras sugeridas**. Correlacionar histórico de CPU, RAM, paginação, disco, latência de armazenamento, atividade de rede, sensores térmicos, possível throttling, eventos do Windows e atualizações/instalações em segundo plano. Diferenciar coincidência, hipótese, evidência e falha física comprovada.

Exibir status `Normal`, `Informativo`, `Atenção`, `Crítico`, `Indisponível` com horário de última análise e fonte. Botão Nova Verificação e snapshot/histórico. Não informar “sensor de CPU indisponível” quando a tela de Energia já tem CPU Package real.

Listar **todos os processos acessíveis** de modo semelhante ao Gerenciador de Tarefas: PID, nome, usuário, CPU, memória, disco, rede quando medível, caminho seguro, pesquisa/ordenação/filtros e atualização sem saltar a rolagem. Sinalizar processos de Windows Update/TrustedInstaller/TiWorker, MSI/msiexec, Microsoft Store, WinGet, indexação, Defender, OneDrive e instaladores em segundo plano, relacionando seu consumo real com lentidão; distinguir tarefa confirmada de processo apenas presente. Nunca encerrar automaticamente tarefas críticas.

**Eventos Windows:** consultar Event Log com APIs nativas, filtrar principalmente erros e críticos recentes (sistema, aplicativo, WHEA-Logger, Kernel-Power 41, Disk/NVMe/NTFS, Display/GPU, drivers e Service Control Manager), com contagem, data, origem, ID, descrição, tradução simples, explicação técnica e ação recomendada. Não transformar Kernel-Power 41 automaticamente em diagnóstico de fonte defeituosa. Permitir pesquisa online voluntária, com referências e privacidade.

**Segurança:** estado de Windows Defender/antivírus registrados, Firewall, alertas relevantes e integridade quando APIs permitirem; recomendações prudentes, link oficial do Microsoft Defender/Windows Security como padrão quando aplicável e alternativas com fontes. Não instalar antivírus sem consentimento.

**Drivers e softwares:** detectar estados problemáticos, versões instaladas, updates Windows Update Agent e WinGet/softwares/navegadores, links oficiais, criticidade e correções relacionadas à falha diagnosticada. Não dizer que driver está obsoleto somente porque sua data é antiga. Atualizações, especialmente BIOS e drivers críticos, são opt-in e têm pré-validação/rollback quando viável.

**Central de Soluções:** cards vindos diretamente dos diagnósticos; ações seguras como abrir configurações nativas, verificar atualização, recomendar limpeza de `temp` e cache de navegador sem apagar senhas/cookies/perfis nem dados abertos. Sempre: prévia do impacto/tamanho, confirmação, execução visível, registro/resultado; não executar alterações arriscadas silenciosamente.

## 6. REDE, INTERNET, DNS E SCANNER

Inventário separado de Hardware: interfaces Ethernet/Wi-Fi, estado físico/lógico, IPv4/IPv6, MAC mascarável, velocidade negociada, gateway, DHCP, DNS, tráfego e erros. Detectar **APIPA 169.254.x.x** como possível falha na obtenção de IPv4 via DHCP, sem dizer “rede normal” só porque outro adaptador está ativo. Separar conectividade de rede local, DNS, gateway e Internet pública; explicação acessível das causas e recomendações.

Testes voluntários de latência, jitter e perda de pacotes, resolução DNS, conectividade HTTPS/TCP, download/upload com **medidores semicirculares animados** em Mbps, progresso, provedor/serviço usado, horários e histórico. Corrigir o histórico de **HTTP 403 Forbidden**: fallback entre serviços confiáveis, erro diagnosticado e resultados parciais, nunca transformar bloqueio do endpoint em “Internet defeituosa” ou inventar velocidade. Testes precisam ter timeout, cancelamento, limite de consumo de dados e autorização explícita.

Consulta opcional de IP público, ISP/organização/ASN por HTTPS após consentimento (pode não ser o nome comercial por CGNAT/VPN). Comparador DNS sob demanda: Cloudflare **1.1.1.1/1.0.0.1**, Google **8.8.8.8/8.8.4.4**, Quad9 **9.9.9.9/149.112.112.112**; mostrar latência, perdas e diferenças de privacidade/segurança. Não modificar automaticamente DNS; avisar que DNS não corrige APIPA/DHCP.

Scanner de LAN **apenas em sub-rede privada diretamente conectada e autorizado pelo usuário**, limitado a até **254 IPs utilizáveis numa /24** (não “255 computadores”); opções 64/128/254, cancelar, progresso, descoberta por ARP/ping, hostname via DNS reverso/NetBIOS quando possível, IP, MAC, latência e estado. Diferenciar resposta real de registro cacheado, não fazer varredura de portas e não escanear redes públicas arbitrárias. Resultados em tabela/cards legíveis, exportáveis, não JSON bruto.

## 7. BENCHMARK E MODO GAMER/CRIAÇÃO

Benchmarks de CPU, RAM, armazenamento e GPU quando o backend suportar: execução voluntária com modo leve/avançado, carga e duração configuráveis, progresso, interrupção efetiva, resultados comparáveis apenas sob condições definidas e histórico. Não chamar benchmark superficial de “teste de defeito comprovado”, não sobreaquecer máquinas sem confirmação e limites.

**FPS/Frametime Windows:** motor PresentMon licenciado e integrado ao instalador, sem exigir outra interface de aplicativo de terceiros; seleção dos aplicativos/jogos com janela em execução, ativar/desativar, FPS real, frametime em ms, 1% lows quando houver dados suficientes, gráfico, CPU/GPU/VRAM e overlay pequeno opcional. Não injetar DLLs nos jogos, não contornar anti-cheat, não chamar taxa de atualização do monitor (60/144 Hz) de FPS real. Explicar `dwm.exe` (compositor) vs FPS por processo, `explorer.exe` (shell). Janela sobreposta pode não aparecer em tela cheia exclusiva; informe isso. Módulo macOS só se houver backend legítimo e validado; caso contrário, ocultar ou informar indisponível.

## 8. ASSISTENTE IA E CONSULTAS EXTERNAS

Campo **Perguntas ao Assistente** dentro do aplicativo. Interface de provedor desacoplada para Gemini API ou outro serviço legalmente permitido; **não pressupor acesso gratuito ilimitado**. Pesquisa online e interpretação de logs somente com ativação explícita, chave API fornecida pelo usuário armazenada no cofre do SO, nunca gravada em texto claro ou incluída em logs. Minimizar/redigir dados sensíveis antes de transmissão, mostrar quais dados serão enviados, oferecer análise local sem rede e referências com links oficiais. Responder em duas camadas: explicação simples e análise avançada com nível de confiança. Citar documentação oficial e distinguir opiniões de comunidade de fatos verificados.

## 9. SEGURANÇA, PRIVACIDADE E CRÉDITOS

Aplicativo **local-first e somente leitura por padrão**. Não executar PowerShell `-EncodedCommand`, shell oculto de coleta, `curl | bash`, drivers não verificados, downloads arbitrários, exceções amplas no Avast/Defender ou modificação de serviços de segurança. Elevação UAC apenas para helper mínimo, em ação explícita/autorizada; assinatura/manifesto e IPC seguro. Integridade SHA-256 não substitui assinatura de editor nem auditoria de segurança. Recolher exceções, logs estruturados e diagnóstico de bloqueios sem repetição infinita que dispare antivírus.

Criar **Sobre / Componentes de Terceiros** e créditos nos módulos relevantes: LibreHardwareMonitor/LibreHardwareMonitorLib, autores/contribuidores e **MPL 2.0**, com link `https://github.com/LibreHardwareMonitor/LibreHardwareMonitor`; Intel PresentMon, contribuidores, licença **MIT**, link `https://github.com/GameTechDev/PresentMon`; componentes adicionais com licenças próprias. Conferir obrigações concretas de redistribuição e preservar notices/licenças. HWMonitor CPUID e HWiNFO são referências funcionais, **não copiar biblioteca proprietária sem licença**. Open Hardware Monitor original só usar nos termos corretos.

Manter histórico e telemetria local sem envio automático. Exportar relatório de suporte ZIP/JSON com data, versão do app/motor, versão do sistema, permissões, dispositivos, leituras com fonte/unidade, sensores faltantes, exceções, erros de inicialização/threads e logs da ponte. Redigir caminhos pessoais, IP, MAC e outros identificadores reconhecidos, deixando revisão manual antes de compartilhar. Ferramenta de modo seguro para abrir a UI sem coletores automáticos.

## 10. INSTALADORES NATIVOS E DISTRIBUIÇÃO — ENTREGA OBRIGATÓRIA

**Windows 10/11 x64:** compilar `OSReview.exe` com Python incorporado (`PyInstaller --onedir` ou alternativa comprovada). `SensorBridge.exe` deve ser `.NET 8 self-contained`, sem download de .NET no PC final, com todas as bibliotecas necessárias e integridade verificada. PresentMon deve ser incluído legalmente após verificação de procedência/hash/licença. Empacotar em **`OSReview-Setup-<versão>-Windows-x64.exe`** usando Inno Setup: assistente moderno em português, pasta de instalação configurável, atalho de área de trabalho opcional, atalho de menu Iniciar, iniciar com Windows opcional e desmarcado por padrão, abrir após instalação opcional, desinstalador e limpeza da regra de login ao remover. Aplicativo abre diretamente por `.exe`, **sem BAT/CMD/PowerShell, Python, pip ou terminal no PC do usuário**. Instalação preferencial por usuário sem administrador; helper elevado separado mediante UAC para sensores especiais.

**macOS:** gerar `OSReview.app` para **Intel x86_64** e **Apple Silicon ARM64**, com ícone `.icns`, Python incorporado, `.dmg` com instalador gráfico nativo/AppKit ou fluxo Apple suportado; permitir selecionar destino gravável, atalho na Mesa opcional, inicialização no login opcional e abertura após instalar. Não exigir que o usuário execute `.command`, terminal ou instale Python. Respeitar Gatekeeper, assinaturas Developer ID e notarização. Não dizer que um Mac Intel e Apple Silicon são a mesma arquitetura; produzir/validar ambos separadamente.

**Automação:** revisar `.github/workflows/build-distribuicao.yml` para jobs Windows x64, macOS Intel e ARM; instalar dependências somente nos runners de build, executar testes, gerar 3 artefatos finais, anexar SHA-256 e relatórios, impedir publicação se faltar binário, library, manifest, licença ou ocorrer falha de smoke test. Corrigir caminhos de PyInstaller `onedir` e recursos em `_internal`. Scripts `.bat` podem existir **apenas para desenvolvedores/CI**, nunca no pacote distribuído. Suporte a assinatura Windows Authenticode e Apple Developer ID/notarização via secrets de CI sem colocar certificados privados no repositório. Se certificados não estiverem disponíveis, gerar builds **claramente não assinados** e não afirmar que Windows/macOS os reconhecem como oficiais.

Corrigir definitivamente o erro histórico `Python was not found` causado por inicialização da fonte via `.bat` em vez do aplicativo empacotado. Garantir que não apareça prompt de pip, PowerShell ou SDK no uso final. Preferir distribuição offline; se algum download for indispensável durante build, obter somente de fonte oficial sobre HTTPS com integridade verificável. Implementar atualizações futuras com origem/assinatura verificadas e consentimento, sem updates silenciosos inseguros.

## 11. HISTÓRICO, LOGS E ESTABILIDADE

Registrar em SQLite/JSON conforme apropriado: snapshots temporais, máximos/mínimos válidos, alertas, eventos e benchmark, com política de retenção definida, botão apagar/exportar e limites de tamanho. Logs de crash de GUI e de threads devem sobreviver a fechamento inesperado. Telas de diagnóstico e energia não devem congelar nem resetar scroll/filtros sob polling. Teste de rede e scanner devem executar em workers canceláveis. Tratamento para ferramentas/permissions ausentes, ausência de Internet, proteção antivírus, usuário não admin e hardware sem sensores. Nunca exibir erro cru como única explicação para leigos; fornecer detalhes técnicos expandíveis.

## 12. TESTES, CRITÉRIOS DE ACEITAÇÃO E EVIDÊNCIAS

Reexecute os **125 testes legados** e acrescente testes unitários, de integração, de interface e embalagem. Em particular, use fixtures dos dois logs reais do Dell (um sem admin e outro com admin), sanitizados:
- sem admin: CPU i5-1235U / Intel UHD, **51 leituras válidas, 33 sem valor, temperatura indisponível**;
- com admin: **135 leituras válidas, 28 temperaturas, 8 dispositivos**; CPU Package **53 °C**, SSD Composite **37 °C**, NVMe Warning **82 °C** e Critical **89 °C**, CPU Package Power **11,67 W**, CPU Platform **21,13 W**;
- no dashboard a maior temperatura real = **53 °C**, nunca 89 °C; GPU sem sensor térmico => `Indisponível`, não “GPU defeituosa”.

Aceite mínimo:
1. Dashboard e Diagnóstico usam a mesma fonte de sensores; não mostram estados contraditórios.
2. A rolagem, filtros e seleção permanecem estáveis por vários ciclos de atualização.
3. CPU/GPU/SSD/fonte nunca têm leituras fabricadas; limites NVMe não são temperaturas reais; bateria mWh/Wh correta.
4. Detecção Intel UHD/AMD/NVIDIA; processos completos; eventos filtrados; atualizações de fundo e ações seguras; rede/APIPA e HTTP 403 tratados corretamente; scanner até 254 IPs locais com hostname quando identificável.
5. Em Windows sem Python/.NET instalado, o instalador final funciona sem prompt; cria atalhos e login somente se escolhidos; desinstala corretamente.
6. Em Mac Intel/ARM, os `.app` e `.dmg` abrem e respeitam o sistema; limitações de sensores/FPS ficam explícitas.
7. Sem scripts de runtime, sem bypass de antivírus, sem chaves de API embutidas, com créditos e licenças acessíveis.
8. Compilação nativa e smoke tests são efetivamente executados nos runners correspondentes. **Se o ambiente atual não permite validar algo, marque como pendente, forneça o comando/workflow e NÃO declare sucesso fictício.**

## 13. PLANO EXECUTÁVEL DE IMPLEMENTAÇÃO

Trabalhe em etapas completas (com commits e testes por etapa):
A. Auditoria, correções arquiteturais e estabilização do código existente.
B. Motor térmico/energético unificado e UI atualizável sem reset, com suporte do helper elevado legitimamente.
C. Inventário completo, processos, eventos e correlação do diagnóstico.
D. Rede, medidores, ISP, DNS, scanner, benchmarks, FPS, manutenção e IA opt-in.
E. Refinamento UI dark/light/compact/tray/alertas, créditos e privacidade.
F. Build/instaladores nativos Windows/macOS, CI, assinatura opcional e testes de aceitação.

Não pare após escrever relatórios ou código parcial se houver ferramentas disponíveis para implementar e testar. A cada etapa: alterar código → executar testes → corrigir falhas → atualizar documentação → registrar commit/status. Não remover recursos difíceis para “fazer os testes passarem”. Se houver decisões arquiteturais de alto impacto, documente a justificativa.

## 14. ENTREGÁVEIS FINAIS

Entregar no workspace: código revisado, testes e fixtures, documentação clara (`README`, `GUIA_INSTALACAO`, `ARQUITETURA`, `SEGURANCA`, `LICENCAS`, `CHANGELOG`, `STATUS_DE_ENTREGA`), build reproduzível, ícones e créditos, logs exportáveis, `.exe` e `.dmg` **quando efetivamente compilados**, SHA-256, e workflow CI. Identificar separadamente `Implementado`, `Testado localmente`, `Validado em Windows`, `Validado em macOS Intel`, `Validado em macOS ARM`, `Pendente` e `Bloqueado por certificado/ambiente`.

Ao finalizar, responda com: 1) resumo das alterações com caminhos dos arquivos; 2) testes executados e resultados; 3) nomes/caminhos reais dos instaladores gerados (sem inventá-los); 4) problemas conhecidos e riscos; 5) instruções objetivas de como baixar/instalar e validar. **Trabalhe a partir do repositório real e avance na implementação imediatamente.**
