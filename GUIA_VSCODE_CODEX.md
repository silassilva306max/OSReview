# OSReview — Como continuar com o Codex no Visual Studio Code

1. Extraia `OSReview_PACOTE_PARA_CODEX_VSCODE.zip` em uma pasta de projetos, por exemplo `C:\Projetos\OSReview`.
2. Abra o Visual Studio Code e selecione **Arquivo > Abrir Pasta**; escolha a pasta `OSReview` extraída.
3. Abra o Codex no VS Code com a pasta do projeto ativa. O repositório tem `AGENTS.md` com as instruções de desenvolvimento e `PROMPT_MESTRE_CODEX.md` com o escopo integral.
4. Cole no chat do Codex: 

> Leia integralmente `AGENTS.md` e `PROMPT_MESTRE_CODEX.md` na raiz do workspace. Este é o projeto OSReview v0.8.1. Implemente agora o plano da v0.9.0 diretamente no código existente, começando pela auditoria e pelos testes de regressão. Continue por etapas, executando testes e registrando `STATUS_DE_ENTREGA.md`. Não recomece do zero nem declare que compilou instaladores sem produzí-los. Se este ambiente não for o adequado para um build nativo, configure e execute a automação do repositório em runners compatíveis quando possível.

5. Para inspecionar manualmente o prompt, abra `PROMPT_MESTRE_CODEX.md` ou use a cópia avulsa fornecida com o chat.
6. Para obter Windows e macOS **instaláveis**, é necessário executar os builds em ambientes nativos correspondentes, por exemplo pelo GitHub Actions configurado no projeto. Esses binários ainda não estão incluídos no pacote.

**Importante:** `AGENTS.md` é destinado ao agente de desenvolvimento e os scripts de build pertencem somente ao ambiente de compilação. O usuário final deve receber um instalador gráfico `.exe` ou `.dmg` e não precisar de Python/PowerShell/Terminal.
