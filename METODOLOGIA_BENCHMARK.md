# Benchmark local do OSReview 0.9.0 RC

O usuário escolhe CPU (um núcleo) ou cópia de RAM e duração de 3, 5 ou 10 minutos.
Nenhum teste começa automaticamente. É possível interromper a execução.

## Como a pontuação é calculada

- CPU: um worker conta números primos em uma faixa fixa. Cada amostra apresenta
  primos por segundo de tempo decorrido.
- RAM: um worker copia repetidamente um bloco de 32, 64 ou 128 MB entre dois
  buffers. Cada amostra apresenta MB por segundo do tempo de cópia; a alocação
  dos buffers ocorre antes do cronômetro.
- A pontuação é a mediana das amostras. A estabilidade é
  `máximo(0, 100 × (1 − desvio_padrão / mediana))`. Mínimo, máximo, amostras e
  duração são armazenados no histórico local. Uma janela final inferior a
  0,75 segundo é descartada da pontuação para evitar distorção.

Compare resultados apenas entre testes do mesmo tipo, tamanho de bloco, duração
e versão do OSReview. O teste de RAM mede a cópia feita por Python e pelo sistema
operacional; não mede a frequência física da memória. Não há pontuação
compatível com PassMark, Geekbench ou outros produtos. O resultado não é um
diagnóstico de defeito ou teste de estabilidade prolongado.

Inspirado pela separação de subtestes e exibição de resultados do
[PassMark PerformanceTest](https://www.passmark.com/products/performancetest/v12/help/2-Benchmarks/1-CPU-Mark/cpu-benchmark-help.php)
e pela escolha explícita da duração em ferramentas como
[OCCT](https://www.ocbase.com/support/stability-testing-configuration-duration).
O algoritmo e a escala aqui descritos são próprios do OSReview.
