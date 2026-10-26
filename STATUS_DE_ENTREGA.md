# Estado da entrega — 26/10/2026

## Implementado e testado localmente

- Base 0.8.1 importada sem remover os módulos existentes. Git inicializado, tag `baseline-v0.8.1`, branch `release/v0.9.0-rc`.
- Versão 0.9.0 RC aplicada ao aplicativo, metadados do executável e instaladores.
- Suíte inicial: **121 aprovados, 3 falhas, 1 ignorado** em Python 3.14.6 / Windows 11 x64. Uma consulta opcional WMI gerou exceção nativa no teste inicial.
- Suíte após auditoria e correções: **128 aprovados, 1 ignorado**, sem falhas.
- `SensorBridge.exe` compilado como .NET 8 self-contained com LibreHardwareMonitorLib 0.9.6 da cache NuGet local.
- PresentMon 2.6.0 obtido da publicação oficial e aceito pelo SHA-256 fixado em `fps_engine/preparar_motor_fps.py`.
- `build/validar_pacote_windows.py`: aprovado; pacote PyInstaller inclui executável, ponte, manifesto, motor FPS e nenhum `.bat`, `.cmd` ou `.ps1`.
- `dist/OSReview/OSReview.exe --diagnostico`: exit code 0; ZIP de diagnóstico gerado.
- Janela principal do executável empacotado abriu em Windows 11 x64 e respondeu. Foram observadas as telas de Energia, explorador de sensores e Processos. O primeiro teste dentro do sandbox falhou porque o Tcl nativo não conseguia resolver caminhos virtualizados; a leitura e a abertura funcionaram fora desse isolamento.
- Ponte de sensores real, sem elevação: 6 dispositivos, 50 leituras válidas, 34 ausentes e nenhuma temperatura válida. A interface exibiu `Indisponível` para temperaturas não medidas.
- Corrigidos rolagem/seleção da tabela de processos e seleção de temperatura real/recente no painel compacto. Auditoria detalhada em `AUDITORIA_FUNCIONAL.md`.
- Card de RAM passou a mostrar memória disponível/total e frequência configurada da memória, usando `psutil` e inventário `Win32_PhysicalMemory`. Os coletores isolados reportaram 6,43/15,69 GB e 3200 MHz nesta máquina; o último build ainda não teve inspeção visual após análise do Avast.
- Instalador Inno Setup recompilado: `release/OSReview-Setup-0.9.0-Windows-x64-NAO-ASSINADO.exe` (41.790.862 bytes). SHA-256: `48cef14beebf5755237f31348ed8a2a44eda3fc9b19bed960f530d3cbe42dbb4`.
- Pasta portátil recompilada em `release/OSReview-Portable-0.9.0-Windows-x64.zip` (54.826.528 bytes). SHA-256: `1024f0e5143c96f3afed55faab4415780ed744238cb7b36fdbcd8554e24752df`.

## Pendente

- Criar o novo repositório GitHub e enviar o branch e os binários. O conector GitHub recusou as chamadas, não há credencial Git local e o controle do Chrome foi interrompido por não conseguir confirmar a URL atual.
- Confirmar no Avast o fim da análise dos novos executáveis antes de abrir o último build e verificar visualmente o card de RAM e o fluxo da bandeja.
- Testar instalação e desinstalação em Windows x64 limpo sem Python e .NET instalados. O build local não prova esse cenário.
- Assinatura Authenticode: nenhum certificado de editor foi fornecido. O instalador gerado está claramente marcado **NAO-ASSINADO**.
- Validar sensores em hardware real com e sem privilégios; o helper elevado opcional com IPC autenticado ainda não está implementado.
- Isolar consultas WMI/COM do processo gráfico: o log local registrou exceção nativa de acesso durante consulta de GPU, apesar da janela ter aberto.
- Compilar e validar macOS Intel e Apple Silicon em runners nativos. Nenhum DMG foi gerado neste Windows.
- Validar visualmente todos os módulos e concluir as melhorias funcionais extensas do prompt mestre antes de chamar a versão de 1.0.
