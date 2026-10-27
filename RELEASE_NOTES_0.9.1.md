# OSReview 0.9.1 RC1 — atualização pelo aplicativo

- Ao abrir no Windows, o OSReview consulta as Releases públicas do projeto em segundo plano e avisa quando há versão mais nova. A consulta pode ser desligada nas Configurações.
- A tela Atualizações permite verificar novamente, baixar o instalador e acompanhar o progresso. O download só começa por escolha do usuário.
- O instalador é aceito apenas da Release oficial, com tamanho e SHA-256 publicados pelo GitHub. O aplicativo confere o arquivo outra vez antes de abri-lo.
- Após a análise do Avast e confirmação do usuário, o assistente Inno Setup abre e reaproveita a pasta da instalação anterior. A versão portátil é identificada e não é substituída automaticamente.
- O processo preserva configurações e histórico locais, não executa instalação silenciosa e não desativa proteções do Windows.

**Pré-lançamento Windows x64, sem assinatura Authenticode.** A instalação em um Windows limpo e o fluxo completo de atualização real permanecem para validação com uma Release publicada. Nenhum DMG macOS foi validado neste Windows.
