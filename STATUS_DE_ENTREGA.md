# Estado da entrega — 27/10/2026

## Implementado e testado localmente

- Base 0.8.1 importada sem remover os módulos existentes. Git inicializado, tag `baseline-v0.8.1`, branch `release/v0.9.0-rc`.
- Versão 0.9.0 RC aplicada ao aplicativo, metadados do executável e instaladores.
- Suíte inicial: **121 aprovados, 3 falhas, 1 ignorado** em Python 3.14.6 / Windows 11 x64. Uma consulta opcional WMI gerou exceção nativa no teste inicial.
- Suíte após auditoria e correções: **128 aprovados, 1 ignorado**, sem falhas.
- Revisão de interface e controles em 27/10: **134 aprovados, 1 ignorado**. Os novos testes cobrem duração/resultado de CPU e RAM, interrupção, relógios medidos, zero watt real, cinco paletas e bloqueio de serviços protegidos. Compilação Python e `git diff --check` passaram.
- Cinco paletas em temas escuro/claro; botão Sair na tela principal; novos medidores de rede; benchmark CPU/RAM com durações 3/5/10 minutos, gráfico, estabilidade e histórico. Metodologia em `METODOLOGIA_BENCHMARK.md`.
- Processos e serviços: fechamento de janela, encerramento forçado, reabertura do último executável, início/parada de serviços de terceiros com confirmação. Ações reais de alteração do sistema não foram automatizadas nos testes.
- Coleta de processos oculta reduzida; gráficos/tabelas redesenhados apenas na tela ativa. Dez imagens de prévia sem referências foram removidas de `assets/`; ícones e artefatos de diagnóstico foram preservados.
- `SensorBridge.exe` compilado como .NET 8 self-contained com LibreHardwareMonitorLib 0.9.6 da cache NuGet local.
- PresentMon 2.6.0 obtido da publicação oficial e aceito pelo SHA-256 fixado em `fps_engine/preparar_motor_fps.py`.
- `build/validar_pacote_windows.py`: aprovado; pacote PyInstaller inclui executável, ponte, manifesto, motor FPS e nenhum `.bat`, `.cmd` ou `.ps1`.
- `dist/OSReview/OSReview.exe --diagnostico`: exit code 0; ZIP de diagnóstico gerado.
- Janela principal do executável empacotado abriu em Windows 11 x64 e respondeu. Foram observadas as telas de Energia, explorador de sensores e Processos. O primeiro teste dentro do sandbox falhou porque o Tcl nativo não conseguia resolver caminhos virtualizados; a leitura e a abertura funcionaram fora desse isolamento.
- Ponte de sensores real, sem elevação: 6 dispositivos, 50 leituras válidas, 34 ausentes e nenhuma temperatura válida. A interface exibiu `Indisponível` para temperaturas não medidas.
- Corrigidos rolagem/seleção da tabela de processos e seleção de temperatura real/recente no painel compacto. Auditoria detalhada em `AUDITORIA_FUNCIONAL.md`.
- Card de RAM passou a mostrar memória disponível/total e frequência configurada da memória, usando `psutil` e inventário `Win32_PhysicalMemory`. Os coletores isolados reportaram 6,43/15,69 GB e 3200 MHz nesta máquina; o último build ainda não teve inspeção visual após análise do Avast.
- Instalador Inno Setup recompilado após a revisão de proteção: `release/OSReview-Setup-0.9.0-Windows-x64-NAO-ASSINADO.exe` (41.822.846 bytes). SHA-256: `b45e552d04dcb5ab3ac5accf456370b0fc26b8233933a635aa7ce9d5eb6ff337`.
- Pasta portátil recompilada em `release/OSReview-Portable-0.9.0-Windows-x64.zip` (54.876.293 bytes). SHA-256: `08052bce68df77fbaf7cba4a65ee54c1fcc5edafcc9be1eefb2ffedc9683f5f9`.

## Pendente

- Criar o novo repositório GitHub e enviar o branch e os binários. O conector GitHub segue indisponível ao modelo; não há credencial Git local, GitHub CLI ou GitHub Desktop, nem superfície de navegador conectada. O repositório local está independente e sem remoto.
- Confirmar no Avast o fim da análise dos executáveis de 27/10 antes de abrir o novo build e verificar visualmente temas, benchmark, controles, card de RAM e bandeja. O novo executável não foi iniciado.
- Testar instalação e desinstalação em Windows x64 limpo sem Python e .NET instalados. O build local não prova esse cenário.
- Assinatura Authenticode: nenhum certificado de editor foi fornecido. O instalador gerado está claramente marcado **NAO-ASSINADO**.
- Validar sensores em hardware real com e sem privilégios; o helper elevado opcional com IPC autenticado ainda não está implementado.
- Isolar consultas WMI/COM do processo gráfico: o log local registrou exceção nativa de acesso durante consulta de GPU, apesar da janela ter aberto.
- Compilar e validar macOS Intel e Apple Silicon em runners nativos. Nenhum DMG foi gerado neste Windows.
- Validar visualmente todos os módulos e concluir as melhorias funcionais extensas do prompt mestre antes de chamar a versão de 1.0.
