# Auditoria funcional do OSReview 0.9.0 RC — Windows 11 x64

Data: 26/10/2026. A interface é um aplicativo desktop Tkinter empacotado em
`OSReview.exe`; não é uma página web. Alguns botões abrem documentação oficial
no navegador, e recursos online só são usados quando o usuário os solicita.

## Verificação realizada

| Área | Evidência | Resultado |
| --- | --- | --- |
| Inicialização | Executável empacotado abriu a janela nativa no Windows 11 x64; `--diagnostico` terminou com código 0 | Funciona nesta máquina |
| Visão geral e navegação | Telas abertas pela interface, incluindo Energia e Processos | Funciona nesta máquina |
| Processos | 288 processos acessíveis exibidos; busca/ordenação disponíveis; atualização agora preserva seleção e posição e há barra de rolagem | Funciona nesta máquina após correção, sujeito à permissão de cada processo |
| Sensores | `SensorBridge.exe` retornou 6 dispositivos, 50 sensores válidos e 34 sem valor sem elevação; nenhuma temperatura válida | Integração inicia, mas a temperatura não está disponível nesta sessão |
| Energia e explorador de sensores | UI exibiu CPU/GPU/SSD como `Indisponível`, potência sem medição confiável e origem das leituras; explorador abriu | Não inventa temperatura ou watts quando faltam leituras |
| Regras térmicas | Testes automatizados cobrem exclusão de limites de alerta e `Distance to TjMax`; painel compacto passou a usar somente temperatura real e amostra recente | Verificado por testes de regressão, sem temperatura física disponível nesta sessão |
| Suíte Python e pacote | Testes, checagem de dependências, auditoria de segurança e validador do pacote executados | Ver resultados em `STATUS_DE_ENTREGA.md` |

Consultas nativas de WMI, eventos e inventário executadas dentro do sandbox de
desenvolvimento retornaram acesso negado ou dados vazios. Isso **não** comprova
o comportamento dessas telas em uma instalação comum. A UI foi aberta fora
desse isolamento; os coletores individuais ainda precisam de validação em
uma instalação limpa.

## Limites conhecidos

1. **Sensores e privilégios:** nesta execução sem elevação, a ponte não obteve
   temperaturas. Falta o helper separado com elevação UAC opcional e IPC local
   autenticado. O app deve continuar apresentando `Indisponível` ao usuário.
2. **Instalador:** foi compilado, mas instalação e desinstalação ainda não foram
   exercitadas em um Windows x64 limpo sem Python/.NET. Está sem assinatura
   Authenticode e pode exibir aviso do Windows.
3. **FPS:** PresentMon está incluído e seu hash é verificado; captura e overlay
   ainda não foram validados com um jogo real. Alguns jogos podem impedir a
   captura por permissões ou mecanismo gráfico.
4. **Rede:** descoberta de interfaces foi exercitada; teste de velocidade,
   comparação DNS, identificação de provedor e scanner LAN não foram acionados
   nesta auditoria. Dependem de rede, serviços externos ou autorização de
   varredura local. Resultado parcial/erro deve permanecer visível.
5. **IA:** exige chave própria e consentimento para consulta online; não foi
   exercitada. Não participa do diagnóstico local básico.
6. **Inventário, eventos, segurança e atualizações:** há coletores e telas,
   mas não há validação ponta a ponta fora do sandbox para cada fonte WMI/COM.
   As respostas podem variar por versão do Windows e permissões. O log local
   `fatal_python.log` registrou uma exceção nativa de acesso durante uma
   consulta WMI de GPU; embora a janela tenha aberto, essa fonte precisa ser
   isolada e validada antes de uma versão estável.
7. **Processos:** a tabela mostra nome, PID, CPU, RAM e estado. Usuário,
   caminho, I/O de disco e rede por processo ainda não aparecem nela.
8. **Energia:** medidores principais atualizam; os detalhes são congelados por
   padrão, podem ser capturados manualmente ou atualizados automaticamente.
   A renderização dos cards de detalhes ainda recria widgets ao atualizar.
9. **macOS:** não há `.app`/DMG compilado ou validado nesta máquina Windows.

## Próximas evoluções, por prioridade

1. Implementar o helper de sensores opcional com UAC, autenticação local e
   coleta restrita, e validar temperatura/potência com e sem elevação.
2. Fazer teste de instalação, desinstalação, atalhos e inicialização em uma VM
   Windows x64 limpa; assinar os binários com certificado de editor.
3. Isolar consultas WMI/COM potencialmente instáveis da interface e validar
   coletores de eventos, hardware, segurança, rede e FPS fora do sandbox, com
   hardware e jogo reais; corrigir erros encontrados.
4. Atualizar os cards de Energia apenas nos valores para preservar estado e
   reduzir repintura; acrescentar histórico temporal de sensores.
5. Ampliar tabela de processos com usuário/caminho/I/O quando o Windows
   disponibilizar esses campos; melhorar cancelamento e progresso de trabalhos
   longos de rede e benchmark.
6. Compilar e testar a distribuição macOS nos dois tipos de CPU suportados,
   mantendo indisponíveis os sensores exclusivos do Windows.

Esta matriz separa observação no aplicativo, testes automatizados e funções
ainda pendentes de validação. A versão permanece **release candidate**.
