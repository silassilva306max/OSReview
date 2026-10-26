"""Per-question Gemini opt-in API, optional Google Search grounding.
No keys persisted, no automatic hardware/log uploads; direct HTTPS only on user click."""
from __future__ import annotations
import json
import urllib.error
import urllib.request

URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'

def ask_gemini(key: str, question: str, context: str = '', online_search: bool = False) -> dict:
    if not key.strip():
        raise ValueError('É necessária uma chave de API Gemini fornecida pelo usuário.')
    question = question.strip()
    if len(question) < 4 or len(question) > 4500:
        raise ValueError('Pergunta deve ter entre 4 e 4500 caracteres.')
    if len(context) > 3000:
        raise ValueError('Contexto excede limite permitido.')
    system = ('Responda em português brasileiro como consultor de diagnóstico de PCs. Distinga medição, hipótese e fato. '
              'Dê orientação segura em passos curtos e informe quando não houver confirmação. '
              'Para BIOS/CPU/RAM, compatibilidade só pode ser confirmada em listas oficiais específicas por modelo, revisão e BIOS; '
              'relatos comunitários são indícios, não garantia. Não recomende flash automático nem drivers de sites não oficiais. '
              'Quando usar busca na web, cite URLs de origem e diferencie sites oficiais e relatos.')
    payload = {'contents':[{'role':'user','parts':[{'text':question + ('\nContexto autorizado pelo usuário: '+context if context else '')}]}],
               'systemInstruction':{'parts':[{'text':system}]},
               'generationConfig':{'maxOutputTokens':1100}}
    if online_search:
        payload['tools'] = [{'google_search':{}}]
    request = urllib.request.Request(URL, data=json.dumps(payload).encode('utf-8'), method='POST',
                                     headers={'x-goog-api-key':key.strip(), 'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=50) as result:
            response = json.load(result)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Gemini respondeu HTTP {exc.code}; confirme chave, quota, modelo e cobrança de busca.') from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError('Não foi possível acessar a API Gemini. Verifique internet, proxy e firewall.') from exc
    answers, urls = [], []
    for candidate in response.get('candidates', []):
        for part in candidate.get('content', {}).get('parts', []):
            if isinstance(part.get('text'), str):
                answers.append(part['text'])
        for chunk in candidate.get('groundingMetadata', {}).get('groundingChunks', []):
            web = chunk.get('web') or {}
            uri = web.get('uri')
            if isinstance(uri,str) and uri.startswith('https://'):
                urls.append({'title':web.get('title','Fonte'), 'url':uri})
    if not answers:
        raise RuntimeError('A API não retornou uma resposta em texto. Verifique os filtros e disponibilidade do modelo.')
    return {'answer':'\n'.join(answers), 'sources':urls[:12], 'grounding_requested':online_search,
            'warning':'Resposta de IA pode conter erros; valide suporte de CPU/BIOS com lista oficial e revisão do equipamento. A disponibilidade de busca gratuita depende do plano e das quotas da API.'}
