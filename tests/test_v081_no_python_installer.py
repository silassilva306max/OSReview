"""Contract checks: released payload does not require Python, .NET install or shell."""
from pathlib import Path
import hashlib
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validate_payload',ROOT/'build/validar_pacote_windows.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def test_windows_installer_only_packs_compiled_bundle():
    script = (ROOT/'installer/windows/OSReview.iss').read_text(encoding='utf-8')
    assert 'Source: "..\\..\\dist\\OSReview\\*"' in script
    assert 'DisableDirPage=no' in script
    assert 'WizardIsTaskSelected' in script
    assert 'powershell' not in script.casefold()
    assert 'Filename: "{app}\\{#AppExe}"' in script


def test_dotnet_selfcontained_compiled_only_on_builder():
    build = (ROOT/'build/Gerar_Instalador_Windows_x64.bat').read_text(encoding='cp1252')
    assert '--self-contained true' in build
    assert '-p:PublishSingleFile=true' in build
    assert '-p:IncludeNativeLibrariesForSelfExtract=true' in build
    assert 'validar_pacote_windows.py' in build
    assert '--onedir' in build and '--windowed' in build


def test_mac_installer_native_not_terminal():
    src = (ROOT/'installer/macos/NativeInstaller/main.swift').read_text()
    build = (ROOT/'build/Gerar_Instalador_macOS.sh').read_text()
    assert 'NSOpenPanel()' in src
    assert 'NSAlert()' in src
    assert 'createSymbolicLink' in src
    assert 'Instalar_OSReview.command' not in build
    assert 'Instalar OSReview.app' in build
    assert 'swiftc' in build


def test_payload_rejects_missing_binaries(tmp_path):
    failures = checker.validate(tmp_path)
    assert any('OSReview.exe' in x for x in failures)
    assert any('sensor' in x for x in failures)


def test_payload_accepts_valid_mock_pe_binaries(tmp_path):
    base = tmp_path/'dist/OSReview'
    internal = base/'_internal'
    sensor = internal/'sensor_bridge/SensorBridge.exe'
    sensor.parent.mkdir(parents=True)
    app = base/'OSReview.exe'
    app.write_bytes(b'MZ' + b'0'*120_000)
    sensor.write_bytes(b'MZ' + b'1'*200)
    sensor.with_suffix('.exe.sha256').write_text(hashlib.sha256(sensor.read_bytes()).hexdigest()+'  '+sensor.name+'\n')
    fps = internal/'fps_engine/PresentMon.exe'
    fps.parent.mkdir(parents=True)
    fps.write_bytes(b'MZ' + b'2'*100)
    assert checker.validate(tmp_path) == []
    (base/'start_windows.bat').write_text('echo unsafe')
    assert 'Scripts' in ' '.join(checker.validate(tmp_path))
