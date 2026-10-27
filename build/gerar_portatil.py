"""Build a reproducible Windows portable ZIP and its SHA-256 file."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from osreview import __version__


source = root / 'dist' / 'OSReview'
release = root / 'release'
if not (source / 'OSReview.exe').is_file():
    raise SystemExit('OSReview.exe ausente da distribuição portátil.')
release.mkdir(exist_ok=True)
destination = release / f'OSReview-Portable-{__version__}-Windows-x64.zip'
temporary = destination.with_suffix('.zip.part')
try:
    with ZipFile(temporary, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sorted(source.rglob('*')):
            if file.is_file():
                archive.write(file, Path('OSReview') / file.relative_to(source))
    temporary.replace(destination)
finally:
    temporary.unlink(missing_ok=True)
hasher = hashlib.sha256()
with destination.open('rb') as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        hasher.update(block)
digest = hasher.hexdigest()
destination.with_suffix('.zip.sha256').write_text(
    f'{digest}  {destination.name}\n', encoding='ascii')
print(f'Portátil: {destination} SHA256: {digest}')
