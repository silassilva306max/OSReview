"""Static red-flag check. It is NOT a malware scanner or security certification."""
from __future__ import annotations
from pathlib import Path
import re
import sys

project = Path(__file__).resolve().parents[1]
checks = [
    (re.compile(r'-EncodedCommand', re.I), 'PowerShell encoded-command syntax'),
    (re.compile(r'\b(?:powershell|pwsh)\.exe\b', re.I), 'PowerShell executable invocation'),
    (re.compile(r'subprocess\.(?:run|Popen)\s*\(\s*\[\s*[\'\"](?:powershell|pwsh)', re.I), 'PowerShell subprocess'),
]
failures=[]
for src in (project / 'osreview').rglob('*.py'):
    content=src.read_text(encoding='utf-8')
    for regex,label in checks:
        if regex.search(content):
            failures.append((str(src.relative_to(project)),label))
if failures:
    for file,label in failures:print('ALERTA:',file, label)
    sys.exit(1)
print('PASS: nenhum padrao proibido de inicializacao do PowerShell nos arquivos Python do aplicativo.')
print('NOTA: isso nao comprova ausencia de malware, nem garante aceite por antivirus.')
