# Como interpretar a ausência de temperaturas e potência

Este documento acompanha o OSReview v0.7.4 e orienta o diagnóstico de uma situação comum: a ponte LibreHardwareMonitor é executada, mas nem todos os sensores devolvem valores.

## Exemplo analisado nesta revisão

O log recebido mostrava Windows 11, motor ativo e íntegro, seis dispositivos enumerados e 51 leituras válidas de outros tipos. **Nenhuma temperatura foi lida**; 23 sensores térmicos e 10 sensores de frequência estavam enumerados mas sem valor. CPU Package, Core Max e temperaturas de núcleos estavam sem valor. O Windows não reportou a execução como administrador. A motherboard não apresentou sensores válidos. Quatro sensores de potência da CPU e um da GPU informaram 0 W, que não é evidência de consumo nulo.

### Possíveis causas — não conclusões confirmadas

- Limitação de privilégios ou indisponibilidade do acesso de baixo nível necessário ao sensor.
- Driver de acesso ao hardware ausente, incompatível ou bloqueado legitimamente por recursos de segurança.
- Sensor não implementado ou não exposto pelo firmware/controlador do equipamento.
- Outro monitor usa API ou driver diferente e portanto pode exibir uma leitura que o motor atual não consegue obter.

### Verificação recomendada

1. Confirme o hash da ponte em **Fontes e integridade**.
2. Feche outros monitores antes de repetir a coleta, evitando leituras simultâneas conflitantes.
3. Se o software e componentes foram obtidos de fonte confiável e não houver bloqueio do antivírus, experimente executar pontualmente o OSReview como administrador e exporte outro log; compare quantidades de temperatura. Não desative a proteção ou integridade de memória.
4. Inspecione **Segurança do Windows → Segurança do dispositivo → Isolamento do núcleo** e **Visualizador de Eventos → Microsoft → Windows → CodeIntegrity → Operational** apenas para confirmar se houve bloqueio. Um bloqueio pode ser legítimo e deve ser respeitado.
5. Compare com um monitor confiável, como a versão oficial do LibreHardwareMonitor ou uma ferramenta OEM da Dell. O fato de outra ferramenta exibir a temperatura não autoriza instalar drivers sem validação.
6. Compartilhe o JSON exportado pelo OSReview para correlação. Ele contém modelo e identificadores de hardware e deve ser revisado antes do envio.

**Nota elétrica:** capacidade da bateria não é medição de potência total da fonte/charger. Fontes externas de notebook e fontes ATX tradicionais podem não oferecer telemetria digital ao sistema.

Referências oficiais: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor e https://learn.microsoft.com/windows/security/threat-protection/windows-defender-application-control/microsoft-recommended-driver-block-rules
