"""Bound replay environment metadata carried by native failure evidence."""
import re


def replay_settings(value):
    if value is None:
        return {'pytest_plugins': [], 'timeout_seconds': 20}
    if not isinstance(value, dict) or set(value) != {'pytest_plugins', 'timeout_seconds'}:
        raise ValueError('native_replay_settings_schema')
    plugins, timeout = value['pytest_plugins'], value['timeout_seconds']
    if (not isinstance(plugins, list) or len(plugins) > 4
            or any(not isinstance(p, str) or not re.fullmatch(r'[A-Za-z_]\w*(?:\.\w+)*', p) for p in plugins)
            or type(timeout) is not int or not 1 <= timeout <= 120):
        raise ValueError('native_replay_settings_bounds')
    return {'pytest_plugins': list(plugins), 'timeout_seconds': timeout}


def policy_replay_settings(policy):
    intake = policy.get('native_failure_intake') or {}
    plugins = intake.get('nested_pytest_plugins') or []
    timeout = intake.get('targeted_timeout_seconds', 20)
    return replay_settings({'pytest_plugins': plugins, 'timeout_seconds': timeout})
