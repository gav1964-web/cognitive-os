import hashlib
import io
import subprocess

import pytest

from runtime import verified_pypi_wheel


def test_compatible_wheel_selects_supported_universal_tag():
    metadata = {
        "releases": {
            "1.0": [{
                "filename": "demo-1.0-py3-none-any.whl",
                "packagetype": "bdist_wheel",
                "requires_python": ">=3.8",
            }]
        }
    }

    wheel = verified_pypi_wheel._compatible_wheel(metadata)

    assert wheel["filename"] == "demo-1.0-py3-none-any.whl"


def test_compatible_wheel_honors_resolver_selected_version():
    metadata = {
        "releases": {
            "1.0": [{"filename": "demo-1.0-py3-none-any.whl", "packagetype": "bdist_wheel"}],
            "2.0": [{"filename": "demo-2.0-py3-none-any.whl", "packagetype": "bdist_wheel"}],
        }
    }

    wheel = verified_pypi_wheel._compatible_wheel(
        metadata, version=verified_pypi_wheel.Version("1.0"),
    )

    assert wheel["filename"] == "demo-1.0-py3-none-any.whl"


def test_resolved_wheel_versions_uses_pip_selected_version():
    output = "Downloading matplotlib-3.10.9-cp310-cp310-win_amd64.whl (8.2 MB)"

    resolved = verified_pypi_wheel.resolved_wheel_versions(output, ["matplotlib"])

    assert resolved == {"matplotlib": "3.10.9"}


def test_download_verified_checks_hash_and_trusted_host(tmp_path, monkeypatch):
    payload = b"verified wheel bytes"
    response = io.BytesIO(payload)
    response.status = 200
    monkeypatch.setattr(
        verified_pypi_wheel.urllib.request,
        "urlopen",
        lambda *args, **kwargs: response,
    )
    wheel = {
        "url": "https://files.pythonhosted.org/demo.whl",
        "filename": "demo.whl",
        "digests": {"sha256": hashlib.sha256(payload).hexdigest()},
    }
    policy = {"trusted_file_hosts": ["files.pythonhosted.org"], "download_timeout_seconds": 30}

    path = verified_pypi_wheel._download_verified(wheel, tmp_path, policy)

    assert path.read_bytes() == payload


def test_download_verified_rejects_untrusted_host(tmp_path):
    wheel = {
        "url": "https://example.invalid/demo.whl",
        "filename": "demo.whl",
        "digests": {"sha256": "abc"},
    }
    policy = {"trusted_file_hosts": ["files.pythonhosted.org"], "download_timeout_seconds": 30}

    with pytest.raises(RuntimeError, match="not trusted"):
        verified_pypi_wheel._download_verified(wheel, tmp_path, policy)


def test_installer_verifies_version_inside_target_environment(tmp_path, monkeypatch):
    wheel_path = tmp_path / "demo-1.0-py3-none-any.whl"
    wheel_path.write_bytes(b"wheel")
    metadata = {
        "releases": {
            "1.0": [{
                "filename": wheel_path.name,
                "packagetype": "bdist_wheel",
                "url": "https://files.pythonhosted.org/demo.whl",
                "digests": {"sha256": "abc"},
            }]
        }
    }
    monkeypatch.setattr(verified_pypi_wheel, "_package_metadata", lambda *args: metadata)
    monkeypatch.setattr(verified_pypi_wheel, "_download_verified", lambda *args: wheel_path)

    def fake_run(args, **kwargs):
        stdout = "1.0\n" if "importlib.metadata" in args[2] else ""
        return subprocess.CompletedProcess(args, 0, stdout, "")

    monkeypatch.setattr(verified_pypi_wheel.subprocess, "run", fake_run)
    policy = {"enabled": True, "cache_dir_name": "wheels"}

    result = verified_pypi_wheel.install_verified_wheels(
        env_dir=tmp_path / "env",
        packages=["demo"],
        resolved_versions={"demo": "1.0"},
        policy=policy,
        timeout_seconds=30,
    )

    assert result["status"] == "installed"
    assert result["artifacts"][0]["version"] == "1.0"
