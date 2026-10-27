# Auditoria da publicação pública — 27/10/2026

## Escopo e verificações

- Repositório público `silassilva306max/OSReview`: 13 commits e 209 objetos de arquivo únicos no histórico examinado. A busca em arquivos de texto não encontrou chave privada, token GitHub, chave AWS/OpenAI ou atribuição de senha/chave com os padrões verificados. Os cinco endereços de e-mail encontrados nos arquivos de teste usam domínios de exemplo. Isso é uma verificação por padrões, não prova de ausência de qualquer segredo.
- Dez imagens de prévia removidas da versão atual continuam no histórico. A inspeção visual não mostrou usuários, números de série ou credenciais. Algumas telas revelam modelo de CPU, temperaturas e outras métricas do dispositivo de desenvolvimento.
- O ZIP Windows 0.9.0 rastreado no Git continha um caminho de compilação com o nome do usuário Windows dentro de `SensorBridge.exe`. Ele foi retirado da árvore atual, mas continua recuperável no histórico já publicado. O endereço de e-mail usado como autor dos commits antigos também continua visível nos metadados Git. Os próximos commits locais usam o endereço `noreply` do GitHub.
- O ZIP público 0.9.1 RC1 foi baixado, teve SHA-256 conferido com a API do GitHub e teve seus 1024 itens inspecionados sem executar código. Não foi encontrado o nome do usuário Windows, chave privada ou token GitHub. Um padrão genérico `sk-` encontrado no binário de terceiros tem 746 caracteres e é idêntico nos dois builds; seu tamanho indica falso positivo da varredura binária, não uma chave identificável.
- Release `v0.9.1-rc.1`: pública, pré-lançamento, quatro anexos (instalador, ZIP e respectivos SHA-256). O instalador público foi baixado separadamente e passou na verificação de SHA-256. A Release `v0.9.0-rc.1` foi corrigida para pré-lançamento; ela não contém anexos.

## Configuração de segurança

- Varredura de segredos, proteção contra push de credenciais, alertas de dependências, atualizações de segurança do Dependabot e relato privado de vulnerabilidades: ativados e verificados pela API autenticada do GitHub. Nenhum alerta aberto de segredos ou Dependabot foi retornado no momento da consulta; a varredura recém-habilitada pode produzir alertas posteriormente.
- Permissões padrão do `GITHUB_TOKEN`: somente leitura. O workflow passa a reservar `contents: write` apenas para o job de publicação; build e testes não recebem essa permissão. As Actions usadas pelo workflow estão fixadas por SHA de commit. Atualizações de dependências e Actions geram propostas semanais, sem merge automático.
- A branch padrão deve bloquear force push e exclusão. Esta proteção não substitui revisão de código, assinatura de commits nem segurança da conta GitHub.

## Limitações e ações pendentes

- O repositório é público: código, histórico Git, logs de Actions e imagens antigas podem ser copiados por terceiros. Remover arquivos da árvore atual não elimina cópias nem objetos históricos. A reescrita do histórico para remover metadados pessoais exigiria operação coordenada com substituição de tags e avaliação da Release existente.
- O instalador não tem assinatura Authenticode. O hash da Release não prova a identidade do editor nem ausência de malware. O fluxo completo de instalação e atualização ainda depende da análise do Avast e de validação manual em Windows.
- Dependências Python usam intervalos de versão, o NuGet usa uma versão fixa e o Inno Setup é instalado via Chocolatey no CI. Ainda não há lockfile com hashes de todas as dependências de build.
- Os jobs macOS da execução 0.9.1 falharam; nenhum DMG foi publicado. O job Windows e sua publicação foram concluídos.
- O repositório não declara licença própria. Publicar código não concede automaticamente permissão de reutilização; a escolha de licença cabe ao proprietário. Avisos e licenças dos componentes de terceiros estão em `licenses/`.

**Conclusão:** nenhuma credencial ativa foi identificada nos arquivos examinados. A publicação não pode receber garantia de segurança de 100%; os limites acima permanecem relevantes para quem baixa e para o proprietário do repositório.
