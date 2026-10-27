# OSReview v0.9.1 RC2

Sistema de diagnóstico de hardware, processos, sensores, rede, eventos, energia e FPS.

Na versão 0.9.1 RC2, a interface oferece cinco paletas nos modos claro e escuro,
benchmarks locais de CPU/RAM com gráfico e histórico, e controles confirmados de
processos e serviços de terceiros. A metodologia dos testes está em
`METODOLOGIA_BENCHMARK.md`.

No Windows, o aplicativo verifica novas Releases públicas do OSReview ao abrir,
se essa preferência estiver ativada. A tela Atualizações baixa o instalador
somente por escolha do usuário, confere tamanho e SHA-256 e abre o assistente
após confirmação de que o Avast terminou sua análise. A instalação anterior é
atualizada na mesma pasta pelo mesmo AppId do Inno Setup. Cópias portáteis não
são sobrescritas por esse instalador. Quem usa 0.9.0 precisa instalar 0.9.1 RC2
uma vez para receber os próximos avisos no aplicativo.

## Distribuição para usuário final

**Não executar `.bat` ou instalar Python.** A distribuição real usa instalador
nativo para Windows e `.app` em `.dmg` para macOS. Python é empacotado dentro
da aplicação, e a ponte de sensores .NET 8 no Windows é *self-contained*.
O usuário não precisa baixar .NET 8 durante a instalação.

Veja **GUIA_INSTALACAO.md** para opções de destino, atalhos e início automático.

## Segurança

O instalador final não contém scripts `.bat`, nem tenta abrir PowerShell.
O sensor LibreHardwareMonitorLib é biblioteca de terceiros, com licença MPL 2.0
e créditos na interface. A presença de assinatura válida deve ser verificada
por Authenticode (Windows), Developer ID e notarização (Mac).

**Disponibilidade:** a Release `v0.9.1-rc.2` contém instalador Windows x64,
ZIP portátil e DMGs macOS para Intel e Apple Silicon, com arquivos SHA-256.
Os três builds passaram nos runners nativos do GitHub Actions. A instalação
interativa em Mac físico ainda precisa de validação. Sensores exclusivos do
Windows e FPS PresentMon não são oferecidos como recursos nativos do Mac.

Consulte `STATUS_DE_ENTREGA.md` para testes e limitações.

Leia: `SEGURANCA_E_PRIVACIDADE.md`, `GUIA_INSTALACAO.md` e `CHANGELOG.md`.
