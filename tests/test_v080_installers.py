"""Static integration checks for distribution configuration; not binary acceptance tests."""
from pathlib import Path
import plistlib
import re
from unittest.mock import patch

from osreview import __version__
from osreview.services import configuration

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_icons():
    assert __version__ == '0.9.1-rc.3'
    assert (ROOT/'assets/osreview.ico').is_file()
    assert (ROOT/'assets/osreview.icns').is_file()


def test_windows_tasks_install_directory():
    content = (ROOT/'installer/windows/OSReview.iss').read_text(encoding='utf-8')
    assert 'DisableDirPage=no' in content
    assert 'PrivilegesRequired=lowest' in content
    assert 'Name: "desktopicon"' in content
    assert 'Name: "autostart"' in content
    assert "WizardIsTaskSelected('autostart')" in content
    assert "RegWriteStringValue(HKCU" in content
    assert '{#AppExe}' in content


def test_mac_optional_install_choices():
    content = (ROOT/'installer/macos/NativeInstaller/main.swift').read_text(encoding='utf-8')
    assert 'NSOpenPanel()' in content
    assert 'checkboxWithTitle: "Criar atalho' in content
    assert 'Iniciar OSReview ao entrar no macOS' in content
    assert 'LaunchAgents' in content
    assert 'createSymbolicLink' in content
    assert 'copyItem(at: appSource, to: temp)' in content
    assert 'sudo ' not in content
    assert 'Process(' not in content


def test_ci_architectures():
    workflow=(ROOT/'.github/workflows/build-distribuicao.yml').read_text(encoding='utf8')
    assert 'windows-2022' in workflow
    assert 'macos-15-intel' in workflow
    assert 'runs-on: macos-15\n' in workflow
    assert 'workflow_dispatch' in workflow
    assert re.search(r'actions/upload-artifact@[0-9a-f]{40} # v4', workflow)
    assert 'needs: [windows-x64, macos-intel, macos-apple-silicon]' in workflow
    assert workflow.count('contents: write') == 1


def test_macos_login_agent_created_and_unregistered(tmp_path):
    fake_exe = tmp_path/'OSReview.app'/'Contents'/'MacOS'/'OSReview'
    fake_exe.parent.mkdir(parents=True)
    fake_exe.write_text('placeholder')
    with patch.object(configuration.platform,'system',return_value='Darwin'), \
         patch.object(configuration,'_mac_agent_path',return_value=tmp_path/'LaunchAgents'/'com.osreview.diagnostics.login.plist'), \
         patch.object(configuration.sys,'frozen',True,create=True), \
         patch.object(configuration.sys,'executable',str(fake_exe)):
        good,msg=configuration.configure_macos_startup(True)
        assert good, msg
        agent=configuration._mac_agent_path()
        data=plistlib.loads(agent.read_bytes())
        assert data['Label']=='com.osreview.diagnostics.login'
        assert data['RunAtLoad'] is True
        assert data['ProgramArguments']==[str(fake_exe)]
        assert configuration.get_macos_startup_status()
        good,_=configuration.configure_macos_startup(False)
        assert good
        assert not agent.exists()


def test_mac_python_source_cannot_register_startup(tmp_path):
    with patch.object(configuration.platform,'system',return_value='Darwin'), \
         patch.object(configuration,'_mac_agent_path',return_value=tmp_path/'test.plist'), \
         patch.object(configuration.sys,'frozen',False,create=True):
        good,msg=configuration.configure_macos_startup(True)
        assert not good and 'Instale' in msg


def test_mac_build_rejects_non_mac():
    text = (ROOT/'build/Gerar_Instalador_macOS.sh').read_text()
    assert '"$(uname -s)" != "Darwin"' in text
    assert '--osx-bundle-identifier' in text
