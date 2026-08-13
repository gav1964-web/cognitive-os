from unittest.mock import Mock, patch

from tools.role_foundation_field_trial import _configure_stdout


def test_cli_configures_stdout_for_unicode_reports():
    stdout = Mock()

    with patch("tools.role_foundation_field_trial.sys.stdout", stdout):
        _configure_stdout()

    stdout.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")
