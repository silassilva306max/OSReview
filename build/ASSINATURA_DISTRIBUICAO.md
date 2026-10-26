# Assinatura e validação — OSReview 0.8.0

## Windows x64

Os arquivos compilados localmente **não têm assinatura** até o responsável possuir
certificado de assinatura de código emitido por autoridade confiável.

1. Faça o build do aplicativo (`dist/OSReview/OSReview.exe`) e sensor bridge.
2. Assine com Microsoft SignTool os binários de autoria do OSReview, em especial
   `OSReview.exe` e `SensorBridge.exe`, usando o certificado do editor e timestamp.
3. Gere instalador via ISCC e assine o instalador com o mesmo certificado.
4. Verifique as assinaturas com `signtool verify /pa /v <arquivo>`.
5. Valide executável, instalador e desinstalador em máquina limpa com Defender/Avast
   **habilitados**. Nunca crie exceção global para PowerShell nem ignore driver bloqueado.

Para instalar sem certificado, o instalador deve ser identificado explicitamente
como **NÃO ASSINADO**. O código de assinatura não fabrica identidades de editor.

## macOS

Para distribuir sem alertas de desenvolvedor desconhecido, requer Apple Developer
Program, `Developer ID Application` e notarização. Gere `.app` no Mac, assine
com runtime protegido, verifique `codesign --verify --deep --strict --verbose=2`;
crie DMG, envie pelo `xcrun notarytool submit ... --wait`, e anexe ticket pelo
`xcrun stapler staple <DMG>`.

Assinatura local ad hoc NÃO equivale a Developer ID/notarização.

## Integridade e privacidade

O setup Windows usa Inno Setup; no macOS o DMG contém `.app` e
`Instalar_OSReview.command`. Todos os downloads de dependências devem vir de
fornecedores oficiais (NuGet, GitHub PresentMon com SHA256 pinado). Os scripts
não removem proteções, não instalam serviços persistentes privilegiados e não
prometem telemetria física onde APIs não a fornecem.
