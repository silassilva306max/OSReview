# OSReview 0.9.1 RC2 — rolagem e revisão de segurança

- A roda do mouse agora rola cards, listas e painéis da página ativa mesmo quando o ponteiro está sobre títulos ou botões. A barra lateral também aceita a roda em toda sua área.
- O atualizador da RC1 pode avisar sobre esta versão, baixar o instalador escolhido pelo usuário e conferir o SHA-256 antes de abri-lo.
- O repositório público passou por auditoria de arquivos, histórico e Releases. Foram ativados proteção contra envio de credenciais, varredura de segredos, Dependabot, CodeQL e relato privado de vulnerabilidades. Os binários antigos saíram da árvore atual do Git; o histórico foi mantido conforme escolha do proprietário.
- O workflow usa Actions fixadas por SHA e isola a permissão de publicação no job de Release. A publicação exige builds concluídos para Windows x64, macOS Intel e macOS Apple Silicon.

**Pré-lançamento sem assinatura Authenticode nem notarização Apple.** Aguarde o Avast terminar a análise antes de executar o instalador Windows. A validação visual da RC2 e o teste de atualização em uma instalação existente ainda dependem de teste manual. O macOS não oferece todas as medições disponíveis no Windows.
