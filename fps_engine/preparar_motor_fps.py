"""Opt-in fixed official PresentMon CLI download, with pinned upstream SHA-256.
Only the official GitHub 2.6.0 release is accepted. No silent installer or service.
"""
import hashlib
import os
from pathlib import Path
from urllib.request import Request, urlopen

VERSION = '2.6.0'
URL = 'https://github.com/GameTechDev/PresentMon/releases/download/v2.6.0/PresentMon-2.6.0-x64.exe'
SHA256 = 'b2a706bc6ad475749e3b7e3409263aa1e6906d45bdcf993f6dbc0f660188f1af'
DEST = Path(__file__).resolve().parent / 'PresentMon.exe'

def install():
    if DEST.exists() and hashlib.sha256(DEST.read_bytes()).hexdigest() == SHA256:
        print('Motor FPS oficial já instalado e hash verificado:', DEST)
        return DEST
    print('Baixando PresentMon v'+VERSION+' da publicação oficial GameTechDev/Intel...')
    tmp = DEST.with_suffix('.download')
    digest = hashlib.sha256()
    try:
        with urlopen(Request(URL, headers={'User-Agent':'OSReview/0.7.1'}), timeout=30) as resp, tmp.open('wb') as out:
            if resp.geturl().split(':')[0] != 'https':
                raise RuntimeError('Redirecionamento HTTPS inválido.')
            while True:
                chunk = resp.read(65536)
                if not chunk: break
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != SHA256:
            raise RuntimeError('SHA-256 não corresponde ao digest publicado no GitHub. Arquivo rejeitado.')
        os.replace(tmp, DEST)
        print('Motor FPS incluído no projeto; não é necessário instalar a GUI PresentMon.')
        return DEST
    finally:
        if tmp.exists(): tmp.unlink()

if __name__ == '__main__':
    install()
