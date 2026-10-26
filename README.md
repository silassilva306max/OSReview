# OSReview v0.8.1

Sistema de diagnóstico de hardware, processos, sensores, rede, eventos, energia e FPS.

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

**Disponibilidade:** o pacote-fonte permite gerar executáveis nos runners nativos,
mas não é, por si, um instalador. Sensores exclusivos do Windows e FPS PresentMon
não são oferecidos como recursos nativos do Mac.

Leia: `SEGURANCA_E_PRIVACIDADE.md`, `GUIA_INSTALACAO.md` e `CHANGELOG.md`.
