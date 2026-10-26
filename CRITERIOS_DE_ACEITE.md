# Critérios de aceite — 0.9.0 RC

## Windows x64

- A suíte de testes passa sem falhas.
- `build/validar_pacote_windows.py` confirma `OSReview.exe`, `SensorBridge.exe`, manifesto SHA-256 e PresentMon, sem scripts de execução no pacote.
- O executável empacotado gera relatório com `--diagnostico` e abre a janela principal.
- O Inno Setup gera um único `OSReview-Setup-0.9.0-Windows-x64-NAO-ASSINADO.exe` e seu SHA-256.
- Antes da versão 1.0, testar instalação, atalhos, abertura e desinstalação numa máquina Windows 10/11 x64 limpa, sem Python/.NET instalados.

## Telemetria e segurança

- Limites `Warning/Critical Temperature` de NVMe e `Distance to TjMax` não entram na maior temperatura medida.
- Potências de domínios sobrepostos não são somadas como consumo total da fonte.
- Falhas de coleta são mostradas como indisponibilidade, sem valores fabricados.
- Não há elevação automática nem contorno de antivírus ou UAC.

## GitHub e macOS

- Código no branch de release candidate e artefato Windows publicado com hash verificável.
- Jobs macOS Intel e ARM compilam e passam nos respectivos runners antes de anunciar suporte binário.
