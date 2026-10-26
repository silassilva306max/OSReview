# Validação OSReview v0.7.5

- 113 testes Python aprovados, incluindo 10 novos casos de limites NVMe e domínios de energia.
- Execução gráfica Linux/Tkinter: 21 seções; foram exercitadas Dashboard, Energia, Diagnóstico e alternância de temas.
- No snapshot de diagnóstico enviado pelo usuário para Intel i5-1235U, ADATA NVMe, Intel UHD: CPU Package 53 °C, SSD Composite 37 °C, limites NVMe Warning 82 °C/Critical 89 °C (metadata), CPU Package 11,67 W, CPU Platform 21,13 W e GPU power 0,02 W. A leitura geral validada tornou-se 53 °C, com origem indicada (CPU Core Max).
- A captura gráfica foi gerada em Linux com monitoramento local em execução e injeção somente dos valores de sensor reportados no JSON fornecido pelo usuário. Outros números dos cards (CPU, RAM, disco, rede) são os do ambiente virtual de teste, **não do computador do usuário**.
- Sensor de temperatura da Intel UHD não estava no relatório. Mantido como indisponível.
- Consumo total do computador/fonte não é inferido somando CPU Package, CPU Platform e GPU.
- Ainda não testado: binário `.exe` Windows e sensores físicos com a ponte .NET na máquina do usuário. Não há garantia de execução sem alertas de antivírus nem binário assinado.
