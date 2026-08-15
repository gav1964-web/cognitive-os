from pathlib import Path

import subprocess

from runtime import project_probe_env
from runtime.project_probe_env import prepare_probe_env, probe_env_readiness


def test_probe_env_readiness_reads_setup_cfg_install_requires(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "setup.cfg").write_text(
        "[options]\n"
        "install_requires =\n"
        "    atpublic\n"
        "    attrs>=24\n",
        encoding="utf-8",
    )
    behavior = {"cases": [{"source": {"status": "error", "reason": "No module named 'public'"}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_candidates"][0]["package"] == "atpublic"
    assert readiness["install_plan"]["allowed_packages"] == ["atpublic"]


def test_probe_env_readiness_maps_attr_module_to_attrs_package(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "setup.cfg").write_text(
        "[options]\n"
        "install_requires =\n"
        "    attrs>=24\n",
        encoding="utf-8",
    )
    behavior = {"cases": [{"source": {"status": "error", "reason": "No module named 'attr'"}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_candidates"][0]["package"] == "attrs"
    assert readiness["install_plan"]["allowed_packages"] == ["attrs"]


def test_probe_env_readiness_allows_declared_execnet(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[project]\n"
        "dependencies = [\"execnet>=2\"]\n",
        encoding="utf-8",
    )
    behavior = {"cases": [{"source": {"status": "error", "reason": "No module named 'execnet'"}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_candidates"][0]["risk"] == "low"
    assert readiness["install_plan"]["allowed_packages"] == ["execnet"]


def test_probe_env_readiness_allows_declared_pytest(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[project]\n"
        "dependencies = [\"pytest>=8\"]\n",
        encoding="utf-8",
    )
    behavior = {"cases": [{"source": {"status": "error", "reason": "No module named 'pytest'"}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_candidates"][0]["declared"] is True
    assert readiness["install_plan"]["allowed_packages"] == ["pytest"]


def test_probe_env_readiness_plans_declared_dependency_stubs(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[project]\n"
        "dependencies = [\"platformdirs>=4\", \"userpath>=1\"]\n",
        encoding="utf-8",
    )
    behavior = {
        "cases": [
            {
                "source": {
                    "status": "ok",
                    "dependency_stubs": ["platformdirs", "userpath", "static_shape_fallback"],
                }
            }
        ]
    }

    readiness = probe_env_readiness(project, behavior)

    assert readiness["missing_modules"] == ["platformdirs", "userpath"]
    assert readiness["install_plan"]["allowed_packages"] == ["platformdirs", "userpath"]


def test_probe_env_readiness_reads_nested_requirements_files(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "requirements").mkdir()
    (project / "requirements" / "default.txt").write_text("amqp >= 5\n", encoding="utf-8")
    behavior = {"cases": [{"source": {"status": "error", "reason": "No module named 'amqp'"}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_candidates"][0]["declared"] is True
    assert readiness["install_plan"]["allowed_packages"] == ["amqp"]


def test_probe_env_readiness_reads_literal_setup_py_install_requires(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "setup.py").write_text(
        "from setuptools import setup\n"
        "setup(install_requires=['sqlalchemy>=2.0.7', 'sanic-routing>=23.12'])\n",
        encoding="utf-8",
    )
    behavior = {
        "cases": [
            {"source": {"status": "error", "reason": "No module named 'sqlalchemy'"}},
            {"source": {"status": "error", "reason": "No module named 'sanic_routing'"}},
        ]
    }

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_plan"]["allowed_packages"] == ["sanic-routing", "sqlalchemy"]


def test_probe_env_readiness_allows_declared_mako_but_not_native_multidict(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "setup.py").write_text(
        "from setuptools import setup\n"
        "setup(install_requires=['Mako', 'multidict>=5'])\n",
        encoding="utf-8",
    )
    behavior = {
        "cases": [
            {"source": {"status": "error", "reason": "No module named 'mako'"}},
            {"source": {"status": "error", "reason": "No module named 'multidict'"}},
        ]
    }

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_plan"]["allowed_packages"] == ["mako"]
    assert readiness["install_plan"]["native_packages"] == []
    assert readiness["install_plan"]["wheel_packages"] == ["multidict"]


def test_probe_env_readiness_allows_declared_pure_python_parser_helpers(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[project]\n"
        "dependencies = [\"boltons\", \"cssselect\", \"jmespath\"]\n",
        encoding="utf-8",
    )
    behavior = {
        "cases": [
            {
                "source": {
                    "status": "ok",
                    "dependency_stubs": ["boltons.iterutils", "cssselect.parser", "jmespath"],
                }
            }
        ]
    }

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_plan"]["allowed_packages"] == ["boltons", "cssselect", "jmespath"]
    assert readiness["install_plan"]["review_packages"] == []


def test_probe_env_readiness_installs_pyyaml_wheel_only(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "requirements.txt").write_text("PyYAML\n", encoding="utf-8")
    behavior = {"cases": [{"source": {"status": "error", "reason": "No module named 'yaml'"}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_candidates"][0]["package"] == "pyyaml"
    assert readiness["install_plan"]["native_packages"] == []
    assert readiness["install_plan"]["wheel_packages"] == ["pyyaml"]


def test_probe_env_readiness_reads_nested_root_requirements_for_wheel_packages(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "guide").mkdir()
    (project / "guide" / "requirements.txt").write_text("msgspec\nlxml>=5\n", encoding="utf-8")
    behavior = {"cases": [{"source": {"status": "ok", "dependency_stubs": ["msgspec", "lxml"]}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_plan"]["wheel_packages"] == ["lxml", "msgspec"]
    assert readiness["install_plan"]["blocked_packages"] == []


def test_probe_env_readiness_installs_declared_httptools_wheel_only(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "setup.py").write_text(
        "from setuptools import setup\n"
        "setup(install_requires=['httptools>=0.6'])\n",
        encoding="utf-8",
    )
    behavior = {"cases": [{"source": {"status": "error", "reason": "No module named 'httptools'"}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_plan"]["wheel_packages"] == ["httptools"]
    assert readiness["install_plan"]["review_packages"] == []


def test_probe_env_readiness_installs_declared_ujson_wheel_only(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "setup.py").write_text(
        "from setuptools import setup\n"
        "setup(install_requires=['ujson>=5'])\n",
        encoding="utf-8",
    )
    behavior = {"cases": [{"source": {"status": "error", "reason": "No module named 'ujson'"}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_plan"]["wheel_packages"] == ["ujson"]
    assert readiness["install_plan"]["native_packages"] == []


def test_probe_env_readiness_reads_setup_py_dependency_alias(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "setup.py").write_text(
        "from setuptools import setup\n"
        "ujson = 'ujson>=5; sys_platform != \"win32\"'\n"
        "requirements = [ujson]\n"
        "setup(install_requires=requirements)\n",
        encoding="utf-8",
    )
    behavior = {"cases": [{"source": {"status": "error", "reason": "No module named 'ujson'"}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_candidates"][0]["declared"] is True
    assert readiness["install_plan"]["wheel_packages"] == ["ujson"]


def test_probe_env_readiness_maps_sass_to_libsass_wheel_only(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "setup.py").write_text(
        "from setuptools import setup\n"
        "setup(install_requires=['libsass'])\n",
        encoding="utf-8",
    )
    behavior = {"cases": [{"source": {"status": "error", "reason": "No module named 'sass'"}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_candidates"][0]["package"] == "libsass"
    assert readiness["install_plan"]["wheel_packages"] == ["libsass"]


def test_probe_env_readiness_allows_declared_websockets(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "setup.py").write_text(
        "from setuptools import setup\n"
        "setup(install_requires=['websockets>=12'])\n",
        encoding="utf-8",
    )
    behavior = {"cases": [{"source": {"status": "error", "reason": "No module named 'websockets'"}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_plan"]["allowed_packages"] == ["websockets"]


def test_probe_env_readiness_maps_sanic_testing_package(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "setup.py").write_text(
        "from setuptools import setup\n"
        "tests_require = ['sanic-testing']\n"
        "setup(tests_require=tests_require)\n",
        encoding="utf-8",
    )
    behavior = {"cases": [{"source": {"status": "error", "reason": "No module named 'sanic_testing'"}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_candidates"][0]["package"] == "sanic-testing"
    assert readiness["install_plan"]["allowed_packages"] == ["sanic-testing"]


def test_probe_env_readiness_allows_low_risk_runtime_install_hint(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    behavior = {
        "cases": [
            {
                "source": {
                    "status": "error",
                    "reason": "RuntimeError: install it with: pip install sanic[ext] or pip install sanic-ext",
                }
            }
        ]
    }

    readiness = probe_env_readiness(project, behavior)

    packages = [row["package"] for row in readiness["install_candidates"]]
    assert "sanic" not in packages
    assert packages == ["sanic-ext", "pydantic"]
    assert readiness["install_candidates"][0]["install_hint"] is True
    assert readiness["install_plan"]["allowed_packages"] == ["pydantic", "sanic-ext"]


def test_probe_env_readiness_maps_frontmatter_to_python_frontmatter(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "requirements.txt").write_text("python-frontmatter\n", encoding="utf-8")
    behavior = {"cases": [{"source": {"status": "error", "reason": "No module named 'frontmatter'"}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_candidates"][0]["package"] == "python-frontmatter"
    assert readiness["install_plan"]["allowed_packages"] == ["python-frontmatter"]


def test_prepare_probe_env_installs_wheel_packages_with_only_binary(tmp_path: Path, monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[:3] == [project_probe_env.sys.executable, "-m", "venv"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(project_probe_env.subprocess, "run", fake_run)
    readiness = {"install_plan": {"wheel_packages": ["pyyaml"]}}

    result = prepare_probe_env(env_dir=tmp_path / "env", readiness=readiness, allow_install=True)

    assert result["status"] == "prepared"
    assert result["wheel_packages"] == ["pyyaml"]
    assert any("--only-binary=:all:" in call for call in calls)
    assert all("--no-deps" in call for call in calls[1:])


def test_prepare_probe_env_reports_pip_timeout(tmp_path: Path, monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[:3] == [project_probe_env.sys.executable, "-m", "venv"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        raise subprocess.TimeoutExpired(args, 240, stderr="network stalled")

    monkeypatch.setattr(project_probe_env.subprocess, "run", fake_run)
    readiness = {"install_plan": {"allowed_packages": ["pytest"]}}

    result = prepare_probe_env(env_dir=tmp_path / "env", readiness=readiness, allow_install=True)

    assert result["status"] == "error"
    assert result["reason"] == "timeout"
    assert result["allowed_packages"] == ["pytest"]
