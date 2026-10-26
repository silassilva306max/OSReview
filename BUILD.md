# Build do desenvolvedor — OSReview v0.9.0 RC

- Windows x64: `build/Gerar_Instalador_Windows_x64.bat`, precisa de Python 3.12,
  .NET SDK 8 e Inno Setup 6 **na máquina de compilação, nunca no PC do usuário**.
- macOS Intel/ARM: `build/Gerar_Instalador_macOS.sh`, precisa de Xcode Command
  Line Tools e Python 3.12 **no computador de compilação**.
- GitHub Actions: `.github/workflows/build-distribuicao.yml` automatiza ambos.
- Artefatos finais: `OSReview-Setup-0.9.0-Windows-x64-*.exe` e
  `OSReview-0.9.0-macOS-{x86_64,arm64}-*.dmg`.

O gerador inclui no Windows o `SensorBridge.exe` **publicado self-contained** com
`IncludeNativeLibrariesForSelfExtract=true` e manifesto SHA-256. O instalador
Inno Setup copia somente `dist/OSReview/**`, sem `.bat`, Python ou SDK do sistema.
Os binários finais precisam de testes reais, assinatura e notarização adequada.
