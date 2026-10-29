"""Release selection and installer integrity without internet or execution."""
from __future__ import annotations

import hashlib
import io
import json
import threading

import pytest

from osreview.services.app_updates import (
    API_URL, OWNER, REPO, ReleaseInfo, UpdateCancelled, UpdateError, _SafeRedirects, check_for_updates,
    download_installer, verify_installer,
)


class Response:
    def __init__(self, content: bytes, url: str):
        self.stream = io.BytesIO(content)
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.stream.close()

    def read(self, size=-1):
        return self.stream.read(size)

    def geturl(self):
        return self.url


class Client:
    def __init__(self, content: bytes, url: str):
        self.content = content
        self.url = url

    def open(self, _request, timeout):
        assert timeout > 0
        return Response(self.content, self.url)


def release_json(tag: str, content: bytes, *, prerelease=True, digest=True):
    filename = f'OSReview-Setup-{tag[1:]}-Windows-x64-NAO-ASSINADO.exe'
    url = f'https://github.com/{OWNER}/{REPO}/releases/download/{tag}/{filename}'
    return {'tag_name': tag, 'name': tag, 'draft': False,
            'prerelease': prerelease, 'assets': [{
                'name': filename, 'state': 'uploaded', 'size': len(content),
                'digest': 'sha256:' + hashlib.sha256(content).hexdigest() if digest else None,
                'browser_download_url': url,
            }]}


def test_newer_release_selected_and_prerelease_setting_respected():
    content = b'MZ' + b'a' * 2048
    releases = [release_json('v0.9.1-rc.5', content), release_json('v0.9.1', content, prerelease=False)]
    def open_api(_request, timeout):
        assert timeout > 0
        return Response(json.dumps(releases).encode(), API_URL)
    result = check_for_updates(True, open_api)
    assert result.release.tag == 'v0.9.1'
    assert result.release.sha256 == hashlib.sha256(content).hexdigest()
    assert check_for_updates(False, open_api).release.tag == 'v0.9.1'
    releases.pop()
    assert check_for_updates(False, open_api).release is None
    assert check_for_updates(True, open_api).release.tag == 'v0.9.1-rc.5'


def test_newer_release_without_verified_asset_is_not_offered():
    content = b'MZ' + b'b' * 2048
    releases = [release_json('v0.9.2', content, digest=False)]
    result = check_for_updates(opener=lambda *_args, **_kwargs:
                               Response(json.dumps(releases).encode(), API_URL))
    assert result.release is None
    assert 'SHA-256' in result.warning


def test_download_checks_hash_size_and_official_host(tmp_path):
    content = b'MZ' + b'c' * 4096
    item = release_json('v0.9.2', content, prerelease=False)
    asset = item['assets'][0]
    release = ReleaseInfo(item['tag_name'], 'Teste', '', asset['browser_download_url'],
                          asset['name'], asset['size'], hashlib.sha256(content).hexdigest(), False)
    updates = []
    path = download_installer(release, lambda done, total: updates.append((done, total)),
                              tmp_path, Client(content, release.asset_url))
    assert verify_installer(path, release)
    assert updates[-1] == (len(content), len(content))
    path.unlink()
    with pytest.raises(UpdateError, match='SHA-256'):
        download_installer(release, cache_dir=tmp_path,
                           opener=Client(b'MZ' + b'd' * 4096, release.asset_url))
    assert not list(tmp_path.glob('*.part'))
    with pytest.raises(UpdateError, match='origem oficial'):
        download_installer(release, cache_dir=tmp_path,
                           opener=Client(content, 'https://evil.example/setup.exe'))


def test_redirect_to_untrusted_host_is_blocked():
    handler = _SafeRedirects()
    with pytest.raises(UpdateError):
        handler.redirect_request(None, None, 302, 'redirect', {}, 'http://example.com/setup.exe')


def test_cancelled_download_does_not_start_network(tmp_path):
    content = b'MZ' + b'e' * 2048
    item = release_json('v0.9.2', content)
    asset = item['assets'][0]
    release = ReleaseInfo(item['tag_name'], 'Teste', '', asset['browser_download_url'],
                          asset['name'], len(content), hashlib.sha256(content).hexdigest(), True)
    stop = threading.Event()
    stop.set()
    with pytest.raises(UpdateCancelled):
        download_installer(release, cache_dir=tmp_path,
                           opener=Client(content, release.asset_url), stop=stop)
    assert not list(tmp_path.iterdir())
