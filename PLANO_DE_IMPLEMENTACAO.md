# Plano de implementação — OSReview 0.9.0 RC

1. Importar e preservar a base 0.8.1. **Concluído:** commit inicial e tag `baseline-v0.8.1`.
2. Reexecutar testes e corrigir falhas reproduzidas. **Concluído:** resultado em `STATUS_DE_ENTREGA.md`.
3. Compilar ponte .NET self-contained, motor PresentMon verificado, executável PyInstaller e instalador Inno Setup. **Concluído no Windows x64.**
4. Validar inicialização e distribuição. **Parcial:** modo de diagnóstico e janela principal abriram; falta instalação/desinstalação em ambiente limpo.
5. Publicar código e artefatos no GitHub. **Pendente:** criar repositório na conta indicada com acesso autenticado.
6. Evoluir os demais requisitos do prompt mestre (helper elevado com IPC autenticado, inventário aprofundado, melhorias de rede e UI, builds macOS). **Pendente**, sujeito a implementação e testes próprios antes de serem anunciados como disponíveis.

Cada etapa deve preservar coleta somente leitura e distinguir leituras reais de limites de sensor ou estimativas.
