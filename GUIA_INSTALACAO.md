# OSReview v0.9.1 RC4 — Instalação GUI sem Python e sem Terminal

## USUÁRIO FINAL (somente binários compilados)

### Windows 10/11 x64

1. Duplo clique em **OSReview-Setup-0.9.1-rc.4-Windows-x64-NAO-ASSINADO.exe**.
2. Escolha a pasta em que o OSReview será instalado (padrão: AppData do usuário).
3. Marque, se desejar, **Criar atalho na área de trabalho**, **Iniciar com o Windows** e/ou **Sempre solicitar permissão de administrador**. Esta última opção mostra o UAC a cada abertura e pode ser alterada ao reinstalar.
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

### Atualizar a instalação existente

Na primeira passagem de 0.9.0 para 0.9.1 RC4, baixe e execute o novo instalador
manualmente: a versão antiga ainda não sabe verificar atualizações. A partir
de 0.9.1 RC1, a tela **Atualizações** consulta as Releases públicas do GitHub
quando o app abre (opção configurável). Se houver versão nova, escolha **Baixar
atualização**, aguarde a conferência de SHA-256 e a análise do Avast, e então
clique em **Instalar agora**. O assistente do Inno Setup usa a pasta instalada
anteriormente e substitui os arquivos da versão antiga; histórico e preferências
do usuário ficam fora da pasta do aplicativo.

O fluxo não executa o instalador silenciosamente. Se estiver usando uma cópia
portátil, o assistente cria ou atualiza uma instalação separada: a pasta portátil
não é substituída automaticamente.

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
