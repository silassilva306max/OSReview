# Estado da entrega — 26/10/2026

## Implementado e testado localmente

- Base 0.8.1 importada sem remover os módulos existentes. Git inicializado, tag `baseline-v0.8.1`, branch `release/v0.9.0-rc`.
- Versão 0.9.0 RC aplicada ao aplicativo, metadados do executável e instaladores.
- Suíte inicial: **121 aprovados, 3 falhas, 1 ignorado** em Python 3.14.6 / Windows 11 x64. Uma consulta opcional WMI gerou exceção nativa no teste inicial.
- Suíte após correções: **124 aprovados, 1 ignorado**, sem falhas.
- `SensorBridge.exe` compilado como .NET 8 self-contained com LibreHardwareMonitorLib 0.9.6 da cache NuGet local.
- PresentMon 2.6.0 obtido da publicação oficial e aceito pelo SHA-256 fixado em `fps_engine/preparar_motor_fps.py`.
- `build/validar_pacote_windows.py`: aprovado; pacote PyInstaller inclui executável, ponte, manifesto, motor FPS e nenhum `.bat`, `.cmd` ou `.ps1`.
- `dist/OSReview/OSReview.exe --diagnostico`: exit code 0; ZIP de diagnóstico gerado.
- Janela principal do executável empacotado abriu em Windows 11 x64 e respondeu. O primeiro teste dentro do sandbox falhou porque o Tcl nativo não conseguia resolver caminhos virtualizados; a leitura e a abertura funcionaram fora desse isolamento.
- Instalador Inno Setup compilado: `release/OSReview-Setup-0.9.0-Windows-x64-NAO-ASSINADO.exe` (41.776.722 bytes). SHA-256: `ce2a2b24c5e747a61b21fbe79715382725af06fccb056405e6913f3f61e411c8`.
- Pasta portátil do executável empacotada em `release/OSReview-Portable-0.9.0-Windows-x64.zip` (54.821.845 bytes). SHA-256: `f548841d6654fb2be072395ae521c6725d080ad1a021fc94ec89d1e78d024cb4`.

## Pendente

- Criar o novo repositório GitHub e enviar o branch e os binários. O conector GitHub recusou as chamadas, não há credencial Git local e o controle do Chrome foi interrompido por não conseguir confirmar a URL atual.
- Testar instalação e desinstalação em Windows x64 limpo sem Python e .NET instalados. O build local não prova esse cenário.
- Assinatura Authenticode: nenhum certificado de editor foi fornecido. O instalador gerado está claramente marcado **NAO-ASSINADO**.
- Validar sensores em hardware real com e sem privilégios; o helper elevado opcional com IPC autenticado ainda não está implementado.
- Compilar e validar macOS Intel e Apple Silicon em runners nativos. Nenhum DMG foi gerado neste Windows.
- Validar visualmente todos os módulos e concluir as melhorias funcionais extensas do prompt mestre antes de chamar a versão de 1.0.
