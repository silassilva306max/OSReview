# Build do desenvolvedor — OSReview v0.9.1 RC5

- Windows x64: `build/Gerar_Instalador_Windows_x64.bat`, precisa de Python 3.12,
  .NET SDK 8 e Inno Setup 6 **na máquina de compilação, nunca no PC do usuário**.
- macOS Intel/ARM: `build/Gerar_Instalador_macOS.sh`, precisa de Xcode Command
  Line Tools e Python 3.12 **no computador de compilação**.
- GitHub Actions: `.github/workflows/build-distribuicao.yml` compila Windows x64,
  macOS Intel e macOS Apple Silicon. Pode ser iniciado manualmente para validar
  os três builds; ao receber a tag desta versão, só publica a Release depois
  que os três jobs tiverem êxito.
- Artefatos finais: `OSReview-Setup-0.9.1-rc.5-Windows-x64-*.exe`,
  `OSReview-Portable-0.9.1-rc.5-Windows-x64.zip` e
  `OSReview-0.9.1-rc.5-macOS-{x86_64,arm64}-*.dmg`.

O gerador inclui no Windows o `SensorBridge.exe` **publicado self-contained** com
`IncludeNativeLibrariesForSelfExtract=true` e manifesto SHA-256. O instalador
Inno Setup copia somente `dist/OSReview/**`, sem `.bat`, Python ou SDK do sistema.
Os binários finais precisam de testes reais, assinatura e notarização adequada.
