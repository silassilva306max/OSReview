# OSReview 0.9.1 RC3 — gráficos e layout adaptável

- Corrigida a exibição dos gráficos de CPU, RAM e benchmark após trocar de tela ou redimensionar a janela.
- Visão geral, benchmark e demais páginas podem ser rolados quando o conteúdo ultrapassa a altura disponível. Tabelas largas também têm rolagem horizontal.
- Medidores de temperatura e controles de Rede, FPS e Configurações foram reorganizados para janelas menores. Os cards superiores ajustam a quebra do texto.
- Corrigida a leitura nativa de eventos críticos e erros do Windows. A falha de um log não apaga os registros acessíveis do outro; a tabela agora pode ser ampliada em tela cheia.
- Cartões extensos ganharam botão **Ampliar cartões**, rolagem e ajuste de texto à largura da janela.
- Medidores de download/upload começam na escala de 0 a 1000 Mbps. O teste oferece 10 ou 20 segundos por sentido, mostra progresso e usa amostras adicionais; a conexão Ethernet ativa aparece separada dos avisos de adaptadores desconectados.
- O instalador Windows oferece a opção desmarcada **Sempre solicitar permissão de administrador**. O Windows pedirá UAC a cada abertura quando ela for escolhida.
- A interface de atualização não mostra a origem do download; a verificação de HTTPS, origem oficial, tamanho e SHA-256 continua ativa.
- Validado o layout das 21 telas em janelas de 980×600, 1024×768, 1280×720 e 1600×900. A suíte automatizada passou em Windows; os builds nativos são validados pelo GitHub Actions.

Pré-lançamento. O Setup Windows x64 não tem assinatura Authenticode, e os DMGs macOS não têm notarização Apple. Sensores exclusivos do Windows não funcionam no Mac. Aguarde a análise do Avast antes de executar um novo instalador Windows.
