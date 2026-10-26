# OSReview v0.9.0 RC — Instalação GUI sem Python e sem Terminal

## USUÁRIO FINAL (somente binários compilados)

### Windows 10/11 x64

1. Duplo clique em **OSReview-Setup-0.9.0-Windows-x64-NAO-ASSINADO.exe**.
2. Escolha a pasta em que o OSReview será instalado (padrão: AppData do usuário).
3. Marque, se desejar, **Criar atalho na área de trabalho** e/ou **Iniciar com o Windows**.
4. Conclua o assistente. Abra o app por **OSReview.exe**, atalho ou menu Iniciar.

**Não exige Python ou .NET SDK/runtime instalados no computador final.**
O Python está empacotado no programa (PyInstaller `--onedir`). O motor de sensores
foi publicado como **.NET 8 self-contained** e acompanha o pacote. Isto é melhor
que baixar o runtime durante a instalação: funciona offline, sem instaladores
adicionais e sem PowerShell. Atualizações de segurança do runtime embutido
necessitam nova versão do aplicativo distribuída pelo editor.

Alguns sensores podem ficar indisponíveis sem privilégios administrativos. Esta
versão não eleva automaticamente a ponte de sensores. O OSReview não desativa
UAC, Defender, Avast nem integridade de memória para contornar bloqueios.

### macOS Intel ou Apple Silicon

1. Abra o `.dmg` apropriado à arquitetura do seu Mac.
2. Abra **Instalar OSReview.app** (instalador nativo, não `.command`).
3. Escolha a pasta de destino e marque, opcionalmente, atalho na Mesa, login e
   abertura após instalação.
4. Clique **Instalar**. O OSReview.app será copiado para o local selecionado.

Não é necessário Python no Mac final. A captura PresentMon e o LibreHardwareMonitor
são exclusivos de Windows; macOS mantém as métricas que o SO expõe.
Para distribuição pública fora da App Store, assinar com Developer ID e notarizar
pela Apple, sem instruir o usuário a desativar Gatekeeper.

## DESENVOLVEDOR / BUILD (os usuários não precisam fazer isso)

### Windows build x64
Pré-requisitos apenas no computador de compilação / CI: Python 3.12 x64,
.NET SDK 8, Inno Setup 6. A execução de `build/Gerar_Instalador_Windows_x64.bat`
compila a ponte self-contained, verifica integridade do motor FPS, empacota
Python e demais dependências, e cria o Inno Setup final na pasta `release/`.
O instalador **não copia** código-fonte nem scripts de desenvolvimento.

### macOS build
Em Mac Intel/ARM, `build/Gerar_Instalador_macOS.sh` empacota o programa,
compila a interface nativa AppKit com `swiftc`, e cria um DMG com
**Instalar OSReview.app**. Esse comando é apenas para o desenvolvedor.

### Automatização
O workflow `.github/workflows/build-distribuicao.yml` permite compilar nos
runners Windows x64, macOS Intel e macOS Apple Silicon por **Run workflow**.
O resultado são 3 artefatos de instalação, após compilação bem-sucedida.
Não são assinados/notarizados automaticamente sem certificados do editor.

### Limites da validação nesta versão
O executável e o instalador foram compilados no Windows 11 x64. O executável
passou no modo de diagnóstico e abriu a janela principal. A instalação e
desinstalação em um Windows limpo sem Python e .NET continuam pendentes, assim
como os builds macOS Intel/ARM. Consulte `STATUS_DE_ENTREGA.md`.
