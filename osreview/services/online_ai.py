"""Optional direct API call using per-session credentials. No automatic uploads."""
from __future__ import annotations
import json
import urllib.error
import urllib.request
from typing import Any

API_URL = 'https://api.openai.com/v1/responses'


def build_sanitized_event_payload(event: dict[str, Any]) -> str:
    """No raw event Message, machine name, paths, usernames or IP addresses are sent."""
    return json.dumps({
        'event_id': int(event.get('id') or 0),
        'provider': str(event.get('provider') or '')[:120],
        'log': str(event.get('log') or '')[:40],
        'local_interpretation': str(event.get('title') or '')[:160],
    }, ensure_ascii=False)


def analyze_event(api_key: str, event: dict[str, Any], model: str = 'gpt-5-mini') -> str:
    if not api_key.strip():
        raise ValueError('Informe uma chave de API válida. Ela será usada apenas nesta sessão.')
    payload = build_sanitized_event_payload(event)
    prompt = (
        'Você é um analista de eventos do Windows. Responda em português brasileiro, com: '
        'significado provável; outras causas possíveis; verificações seguras; quando procurar assistência. '
        'Nunca afirme defeito apenas por um evento isolado. Não instrua desabilitar antivírus, serviços críticos '
        'ou baixar drivers de fontes não oficiais. Os dados são limitados, reconheça incerteza. Evento: ' + payload)
    request_body = json.dumps({'model': model, 'input': prompt, 'max_output_tokens': 600}).encode('utf-8')
    req = urllib.request.Request(API_URL, data=request_body, method='POST', headers={
        'Authorization': 'Bearer ' + api_key.strip(), 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=35) as r:
            obj = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'API retornou HTTP {exc.code}. Confira chave, acesso ao modelo e saldo.') from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError('Não foi possível contactar o serviço de IA. Verifique internet e firewall.') from exc
    content = []
    for item in obj.get('output', []):
        if item.get('type') == 'message':
            for part in item.get('content', []):
                if part.get('type') == 'output_text':
                    content.append(part.get('text', ''))
    return '\n'.join(content).strip() or 'A API não retornou texto interpretável.'
