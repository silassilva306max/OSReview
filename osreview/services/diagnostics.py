"""Conservative heuristics: warnings are not hardware defect diagnoses."""
from dataclasses import dataclass
from typing import Any


@dataclass
class Finding:
    level: str
    title: str
    summary: str
    technical: str
    action: str


class DiagnosticsEngine:
    def analyze(self, sample: dict[str, Any], processes: list[dict[str, Any]],
                health: dict[str, Any] | None = None,
                inventory: dict[str, Any] | None = None,
                event_data: dict[str, Any] | None = None,
                pending_windows_updates: dict[str, Any] | None = None) -> list[Finding]:
        result: list[Finding] = []
        cpu = float(sample.get("cpu_percent") or 0)
        ram = float(sample.get("memory_percent") or 0)
        disk = float(sample.get("disk_percent") or 0)
        swap = float(sample.get("swap_percent") or 0)
        top = processes[0]["name"] if processes else "não identificado"
        if cpu >= 90:
            result.append(Finding("critical", "CPU próxima do limite",
                "O processador está sobrecarregado neste momento; programas podem ficar lentos.",
                f"CPU {cpu:.1f}%, processo de destaque: {top}. Uma amostra isolada não prova gargalo.",
                "Observe por alguns minutos em repouso. Confira os processos antes de fechá-los; não encerre serviços desconhecidos."))
        elif cpu >= 75:
            result.append(Finding("warning", "CPU bastante ocupada",
                "Há uso elevado do processador; pode ser normal durante jogos, edições ou atualizações.",
                f"CPU {cpu:.1f}%. Processo em destaque: {top}.",
                "Confira a lista de processos. Se estiver em repouso, investigue atualização, antivírus ou aplicação pesada."))
        else:
            result.append(Finding("ok", "Uso da CPU sem alerta", "Carga de CPU não elevada no instante da medição.",
                                  f"CPU {cpu:.1f}%.", "Nenhuma intervenção necessária por esta leitura."))
        if ram >= 90:
            result.append(Finding("critical", "Memória RAM quase cheia",
                "O computador pode trocar dados com o armazenamento, ocasionando lentidão.",
                f"RAM {ram:.1f}% e arquivo de paginação/swap em {swap:.1f}% da capacidade reportada.",
                "Feche abas ou programas que não estiver usando. Avalie ampliação de RAM se o problema for recorrente."))
        elif ram >= 78:
            result.append(Finding("warning", "RAM bastante utilizada",
                "Há menos espaço para abrir programas adicionais.", f"RAM {ram:.1f}%.",
                "Veja os programas com maior uso de RAM; evite encerramentos forçados."))
        else:
            result.append(Finding("ok", "RAM dentro da faixa usual", "Há capacidade disponível para outras tarefas.",
                                  f"RAM {ram:.1f}%.", "Sem ação urgente."))
        if disk >= 95:
            result.append(Finding("critical", "Volume de sistema quase sem espaço",
                "Pouco espaço livre pode comprometer instalações, cache e atualizações.",
                f"Volume do usuário: {disk:.1f}% ocupado (não é medição de atividade do disco).",
                "Use Limpeza de Disco ou Configurações > Armazenamento e confirme o que pode ser removido."))
        elif disk >= 85:
            result.append(Finding("warning", "Espaço de armazenamento baixo",
                "O volume principal está ficando cheio.", f"Ocupação do volume monitorado: {disk:.1f}%.",
                "Faça revisão de arquivos e mantenha espaço para atualizações."))
        temp = sample.get("cpu_temp_c")
        if temp is None:
            result.append(Finding("info", "Sensor térmico da CPU indisponível",
                "Este sistema não forneceu temperatura confiável para a CPU.",
                "Leituras variam conforme firmware, controlador e permissões.",
                "Nenhuma temperatura será estimada. Integração avançada com sensores fica para a próxima etapa."))
        elif temp >= 95:
            result.append(Finding("critical", "Temperatura alta da CPU",
                "O processador está muito quente e poderá limitar o desempenho.", f"CPU a {temp:.1f} °C.",
                "Verifique resfriamento, ventilação, poeira e operação de ventoinhas. Limiares variam por modelo."))
        elif temp >= 85:
            result.append(Finding("warning", "CPU aquecida",
                "O processador está trabalhando com temperatura elevada.", f"CPU a {temp:.1f} °C.",
                "Monitore durante o uso real; confira limites térmicos do fabricante."))
        used = sample.get("gpu_memory_used_mb")
        total = sample.get("gpu_memory_total_mb")
        if isinstance(used, (int, float)) and isinstance(total, (int, float)) and total > 0:
            ratio = used / total * 100
            if ratio >= 94:
                result.append(Finding("warning", "VRAM quase esgotada",
                    "Pode ocorrer engasgo em renderizações e jogos.", f"Uso de VRAM {ratio:.1f}%.",
                    "Feche aplicativos gráficos não utilizados ou reduza a qualidade gráfica."))
        if health and health.get("supported"):
            if health.get("pending_reboot") is True:
                result.append(Finding("warning", "Reinicialização pendente no Windows",
                    "Uma atualização ou componente do sistema pode aguardar reinicialização.",
                    "Encontrada sinalização de reinício no registro do Windows.",
                    "Salve seu trabalho e reinicie em momento conveniente; depois confira o Windows Update."))
            if health.get("update_processes"):
                names = ", ".join(x["name"] for x in health["update_processes"][:4])
                result.append(Finding("info", "Processos associados à manutenção do sistema",
                    "Há processos que podem estar instalando atualizações ou programas. Isso não confirma download em andamento.",
                    f"Processos encontrados: {names}.",
                    "Abra Configurações > Windows Update para confirmar. Evite interromper instalações em andamento."))
        if inventory:
            gpu_list = inventory.get('gpus') or []
            generics = [g for g in gpu_list if g.get('type') == 'driver genérico/virtual']
            if generics:
                result.append(Finding('warning', 'Driver gráfico genérico detectado',
                    'O Windows identificou controlador gráfico genérico/virtual. Pode faltar driver do fabricante.',
                    'Controladores: ' + ', '.join(g['name'] for g in generics[:3]),
                    'Abra Hardware / GPUs e consulte o site oficial do fabricante do equipamento antes de instalar um driver.'))
            error_devices = inventory.get('devices_with_errors') or []
            if error_devices:
                result.append(Finding('warning', 'Dispositivos com estado de erro no Windows',
                    'Um ou mais dispositivos foram reportados com problema pelo Plug and Play.',
                    'Dispositivos: ' + ', '.join(x['name'] for x in error_devices[:4]),
                    'Abra Hardware / GPUs e Gerenciador de Dispositivos. Erro PnP não prova driver desatualizado.'))
            defender = inventory.get('defender') or {}
            if defender.get('RealTimeProtectionEnabled') is False and not inventory.get('antivirus'):
                result.append(Finding('warning', 'Proteção antivírus requer verificação',
                    'Defender informa proteção em tempo real desativada e nenhum outro antivírus foi retornado.',
                    'A consulta pode estar incompleta por política corporativa ou permissões.',
                    'Abra Segurança do Windows > Gerenciar provedores para confirmar a proteção ativa.'))
        if event_data and event_data.get('events'):
            important = [e for e in event_data['events'] if e.get('severity') in ('crítico','atenção')]
            if important:
                top = important[:3]
                result.append(Finding('warning', 'Eventos do Windows merecem investigação',
                    f'{len(important)} ocorrência(s) nos logs analisados, sem confirmação automática de defeito.',
                    'Exemplos: ' + '; '.join(f"{e['provider']} #{e['id']}" for e in top),
                    'Abra Eventos / IA, confira recorrência, horário e explicação de cada registro.'))
        if pending_windows_updates and pending_windows_updates.get('ok'):
            critical = [x for x in pending_windows_updates.get('updates', [])
                        if str(x.get('severity', '')).strip().lower() == 'critical']
            if critical:
                result.append(Finding('warning', 'Atualização classificada como crítica disponível',
                    f'O provedor Windows Update ofertou {len(critical)} atualização(ões) com severidade Critical.',
                    'Exemplo: ' + str(critical[0].get('title', 'sem título')),
                    'Abra Atualizações e confira o Windows Update antes de programar a instalação.'))
        return result
