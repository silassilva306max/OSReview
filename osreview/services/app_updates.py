"""OSReview release discovery and verified Windows installer downloads.

Only the official public repository is queried. Nothing is installed by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlparse
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from packaging.version import Version
from platformdirs import user_cache_dir

from osreview import __version__


OWNER = 'silassilva306max'
REPO = 'OSReview'
API_URL = f'https://api.github.com/repos/{OWNER}/{REPO}/releases?per_page=20'
MAX_METADATA_BYTES = 1024 * 1024
MAX_INSTALLER_BYTES = 200 * 1024 * 1024
TAG_RE = re.compile(r'^v\d+\.\d+\.\d+(?:-(?:rc|beta|alpha)(?:[.-]?\d+)?)?$', re.I)
DIGEST_RE = re.compile(r'^sha256:([0-9a-f]{64})$', re.I)


class UpdateError(Exception):
    """Release is unavailable or cannot be verified safely."""


class UpdateCancelled(UpdateError):
    """Download was cancelled by the user."""


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    title: str
    page_url: str
    asset_url: str
    asset_name: str
    size: int
    sha256: str
    prerelease: bool


@dataclass(frozen=True)
class UpdateCheck:
    release: ReleaseInfo | None
    warning: str | None = None


def _trusted_release_url(url: str, tag: str, filename: str) -> bool:
    parsed = urlparse(url)
    return (parsed.scheme == 'https' and parsed.hostname == 'github.com' and
            parsed.port in (None, 443) and parsed.username is None and
            parsed.password is None and not parsed.query and not parsed.fragment and
            parsed.path == f'/{OWNER}/{REPO}/releases/download/{tag}/{filename}')


def _trusted_download_host(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or '').lower()
    return (parsed.scheme == 'https' and parsed.port in (None, 443) and
            parsed.username is None and parsed.password is None
            and (host == 'github.com' or host.endswith('.githubusercontent.com')))


class _SafeRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _trusted_download_host(newurl):
            raise UpdateError('Redirecionamento fora da origem oficial bloqueado.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _release_from_json(data: dict) -> ReleaseInfo | None:
    tag = str(data.get('tag_name') or '')
    if not TAG_RE.fullmatch(tag):
        return None
    filename = f'OSReview-Setup-{tag[1:]}-Windows-x64-NAO-ASSINADO.exe'
    for asset in data.get('assets') or []:
        if not isinstance(asset, dict) or asset.get('name') != filename or asset.get('state') != 'uploaded':
            continue
        digest = DIGEST_RE.fullmatch(str(asset.get('digest') or ''))
        url = str(asset.get('browser_download_url') or '')
        size = asset.get('size')
        if (not digest or not isinstance(size, int) or isinstance(size, bool) or
                not 1024 <= size <= MAX_INSTALLER_BYTES or
                not _trusted_release_url(url, tag, filename)):
            return None
        return ReleaseInfo(tag, str(data.get('name') or tag)[:120],
                           f'https://github.com/{OWNER}/{REPO}/releases/tag/{tag}',
                           url, filename, size, digest.group(1).lower(),
                           bool(data.get('prerelease')))
    return None


def check_for_updates(include_prerelease: bool = True, opener=urlopen) -> UpdateCheck:
    """Read up to 20 published GitHub releases; never executes remote content."""
    request = Request(API_URL, headers={'Accept': 'application/vnd.github+json',
                                        'User-Agent': f'OSReview/{__version__}'})
    try:
        with opener(request, timeout=12) as response:
            if urlparse(response.geturl()).hostname != 'api.github.com':
                raise UpdateError('Resposta recebida de origem inesperada.')
            payload = response.read(MAX_METADATA_BYTES + 1)
    except HTTPError as exc:
        if exc.code == 404:
            raise UpdateError('Não há Releases públicas disponíveis para este repositório.') from exc
        if exc.code == 403:
            raise UpdateError('O serviço de atualizações limitou temporariamente as consultas. Tente mais tarde.') from exc
        raise UpdateError(f'O serviço de atualizações retornou HTTP {exc.code}.') from exc
    if len(payload) > MAX_METADATA_BYTES:
        raise UpdateError('Catálogo de versões excedeu o limite permitido.')
    try:
        releases = json.loads(payload)
    except (ValueError, UnicodeDecodeError) as exc:
        raise UpdateError('Catálogo de versões inválido.') from exc
    if not isinstance(releases, list):
        raise UpdateError('Resposta inesperada do serviço de atualizações.')
    current = Version(__version__)
    candidates: list[tuple[Version, dict]] = []
    for data in releases:
        if not isinstance(data, dict) or data.get('draft'):
            continue
        if data.get('prerelease') and not include_prerelease:
            continue
        tag = str(data.get('tag_name') or '')
        if not TAG_RE.fullmatch(tag):
            continue
        version = Version(tag[1:])
        if version > current:
            candidates.append((version, data))
    if not candidates:
        return UpdateCheck(None)
    _, newest = max(candidates, key=lambda item: item[0])
    release = _release_from_json(newest)
    if release is None:
        return UpdateCheck(None, 'Há uma versão nova, mas falta um instalador Windows x64 com SHA-256 verificável na Release.')
    return UpdateCheck(release)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verify_installer(path: Path, release: ReleaseInfo) -> bool:
    return (path.is_file() and path.name == release.asset_name and
            path.stat().st_size == release.size and _hash_file(path) == release.sha256)


def download_installer(release: ReleaseInfo, progress=None, cache_dir: Path | None = None,
                       opener=None, stop: threading.Event | None = None) -> Path:
    """Download to user cache, then verify exact size and GitHub asset digest."""
    if not _trusted_release_url(release.asset_url, release.tag, release.asset_name):
        raise UpdateError('Endereço do instalador não pertence à Release oficial.')
    if not DIGEST_RE.fullmatch('sha256:' + release.sha256):
        raise UpdateError('SHA-256 da Release inválido.')
    if not 1024 <= release.size <= MAX_INSTALLER_BYTES:
        raise UpdateError('Tamanho do instalador fora do limite permitido.')
    if stop is not None and stop.is_set():
        raise UpdateCancelled('Download cancelado.')
    folder = cache_dir or Path(user_cache_dir('OSReview', 'OSReview')) / 'updates'
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / release.asset_name
    if verify_installer(destination, release):
        if progress:
            progress(release.size, release.size)
        return destination
    temporary = folder / (release.asset_name + '.part')
    if temporary.exists():
        temporary.unlink()
    client = opener or build_opener(_SafeRedirects())
    request = Request(release.asset_url, headers={'User-Agent': f'OSReview/{__version__}'})
    total = 0
    digest = hashlib.sha256()
    deadline = time.monotonic() + 15 * 60
    try:
        with client.open(request, timeout=30) as response:
            if not _trusted_download_host(response.geturl()):
                raise UpdateError('Download saiu da origem oficial esperada.')
            with temporary.open('wb') as output:
                while True:
                    if stop is not None and stop.is_set():
                        raise UpdateCancelled('Download cancelado.')
                    if time.monotonic() > deadline:
                        raise UpdateError('Tempo limite excedido durante o download.')
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    total += len(block)
                    if total > release.size or total > MAX_INSTALLER_BYTES:
                        raise UpdateError('Download excedeu o tamanho informado pela Release.')
                    digest.update(block)
                    output.write(block)
                    if progress:
                        progress(total, release.size)
        if total != release.size or digest.hexdigest() != release.sha256:
            raise UpdateError('Instalador incompleto ou SHA-256 diferente do valor oficial publicado.')
        temporary.replace(destination)
        return destination
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
