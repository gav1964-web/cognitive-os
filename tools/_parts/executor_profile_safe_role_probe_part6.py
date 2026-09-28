from __future__ import annotations

def _web_app_source(*, target_file: str, symbol: str, interface: str) -> str:
    input_source = {
        "post_json": (
            "        length = int(environ.get('CONTENT_LENGTH') or 0)\n"
            "        value = json.loads(environ['wsgi.input'].read(length).decode('utf-8'))\n"
        ),
        "get_query": (
            "        values = parse_qs(environ.get('QUERY_STRING', '')).get('input', [])\n"
            "        if len(values) != 1:\n"
            "            raise ValueError('expected one input query value')\n"
            "        value = json.loads(values[0])\n"
        ),
        "header_json": (
            "        if not environ.get('HTTP_X_INPUT'):\n"
            "            raise ValueError('missing X-Input header')\n"
            "        value = json.loads(environ['HTTP_X_INPUT'])\n"
        ),
    }[interface]
    return (
        "import json\n"
        "import sys\n"
        "from urllib.parse import parse_qs\n"
        "from wsgiref.simple_server import make_server\n"
        f"from {Path(target_file).stem} import {symbol}\n\n"
        "def application(environ, start_response):\n"
        "    try:\n"
        + input_source
        + f"        body = json.dumps({symbol}(value), ensure_ascii=False, sort_keys=True).encode('utf-8')\n"
        "        start_response('200 OK', [('Content-Type', 'application/json'), ('Content-Length', str(len(body)))])\n"
        "    except (KeyError, OSError, ValueError) as exc:\n"
        "        body = json.dumps({'error': 'invalid_request', 'detail': str(exc)}, sort_keys=True).encode('utf-8')\n"
        "        start_response('400 Bad Request', [('Content-Type', 'application/json'), ('Content-Length', str(len(body)))])\n"
        "    return [body]\n\n"
        "if __name__ == '__main__':\n"
        "    with make_server('127.0.0.1', int(sys.argv[1]), application) as server:\n"
        "        server.handle_request()\n"
    )


def _provider_adapter_source(*, target_file: str, symbol: str, interface: str) -> str:
    response_source = {
        "data_envelope": "return {} if invalid else {'data': value}",
        "choices_envelope": "return {} if invalid else {'choices': [{'value': value}]}",
        "paged_envelope": "return {} if invalid else {'items': [value], 'next': None}",
    }[interface]
    extraction_source = {
        "data_envelope": "response['data']",
        "choices_envelope": "response['choices'][0]['value']",
        "paged_envelope": "response['items'][0]",
    }[interface]
    return (
        "import json\n"
        "import sys\n"
        f"from {Path(target_file).stem} import {symbol}\n\n"
        "class FixtureProvider:\n"
        "    def __init__(self):\n"
        "        self.calls = 0\n\n"
        "    def request(self, value, *, invalid=False):\n"
        "        self.calls += 1\n"
        f"        {response_source}\n\n"
        "def main(argv=None):\n"
        "    args = list(sys.argv[1:] if argv is None else argv)\n"
        "    invalid = '--invalid' in args\n"
        "    args = [item for item in args if item != '--invalid']\n"
        "    provider = FixtureProvider()\n"
        "    try:\n"
        "        if len(args) != 1:\n"
        "            raise ValueError('expected one JSON request value')\n"
        "        value = json.loads(args[0])\n"
        "        response = provider.request(value, invalid=invalid)\n"
        f"        extracted = {extraction_source}\n"
        f"        result = {symbol}(extracted)\n"
        "    except (IndexError, KeyError, TypeError, ValueError) as exc:\n"
        "        print(f'provider error: {exc}', file=sys.stderr)\n"
        "        return 2\n"
        "    print(json.dumps({'calls': provider.calls, 'result': result}, ensure_ascii=False, sort_keys=True))\n"
        "    return 0\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"
    )


def _state_adapter_source(*, target_file: str, symbol: str, interface: str) -> str:
    operation = {
        "insert_read": (
            f"        result = {symbol}(value)\n"
            "        with connection:\n"
            "            connection.execute('INSERT INTO records(value) VALUES (?)', (json.dumps(result),))\n"
        ),
        "update_read": (
            "        with connection:\n"
            "            cursor = connection.execute('INSERT INTO records(value) VALUES (?)', (json.dumps(value),))\n"
            f"            result = {symbol}(value)\n"
            "            connection.execute('UPDATE records SET value = ? WHERE id = ?', (json.dumps(result), cursor.lastrowid))\n"
        ),
        "transaction_read": (
            f"        result = {symbol}(value)\n"
            "        connection.execute('BEGIN')\n"
            "        connection.execute('INSERT INTO records(value) VALUES (?)', (json.dumps(result),))\n"
            "        connection.commit()\n"
        ),
    }[interface]
    return (
        "import json\n"
        "import sqlite3\n"
        "import sys\n"
        f"from {Path(target_file).stem} import {symbol}\n\n"
        "def main(argv=None):\n"
        "    args = list(sys.argv[1:] if argv is None else argv)\n"
        "    invalid = '--invalid' in args\n"
        "    args = [item for item in args if item != '--invalid']\n"
        "    connection = sqlite3.connect(':memory:')\n"
        "    connection.execute('CREATE TABLE records(id INTEGER PRIMARY KEY, value TEXT NOT NULL)')\n"
        "    try:\n"
        "        if len(args) != 1:\n"
        "            raise ValueError('expected one JSON state value')\n"
        "        value = json.loads(args[0])\n"
        "        if invalid:\n"
        "            with connection:\n"
        "                connection.execute('INSERT INTO records(value) VALUES (?)', (None,))\n"
        + operation
        + "        stored = connection.execute('SELECT value FROM records').fetchone()\n"
        "    except (sqlite3.Error, TypeError, ValueError) as exc:\n"
        "        count = connection.execute('SELECT COUNT(*) FROM records').fetchone()[0]\n"
        "        print(json.dumps({'error': type(exc).__name__, 'row_count': count}, sort_keys=True))\n"
        "        return 2\n"
        "    print(json.dumps({'result': json.loads(stored[0]), 'row_count': 1}, ensure_ascii=False, sort_keys=True))\n"
        "    return 0\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"
    )


def _async_adapter_source(*, target_file: str, symbol: str, interface: str) -> str:
    operation = {
        "await_once": "    result = await transform(value)\n",
        "gather_batch": "    result = (await asyncio.gather(transform(value)))[0]\n",
        "queue_worker": (
            "    queue = asyncio.Queue()\n"
            "    await queue.put(value)\n"
            "    item = await queue.get()\n"
            "    result = await transform(item)\n"
            "    queue.task_done()\n"
            "    await queue.join()\n"
        ),
    }[interface]
    return (
        "import asyncio\n"
        "import json\n"
        "import sys\n"
        f"from {Path(target_file).stem} import {symbol}\n\n"
        "async def transform(value):\n"
        "    await asyncio.sleep(0)\n"
        f"    return {symbol}(value)\n\n"
        "async def run(value, *, force_timeout=False):\n"
        "    if force_timeout:\n"
        "        await asyncio.wait_for(asyncio.sleep(0.05), timeout=0.001)\n"
        + operation
        + "    return {'result': result, 'tasks': 1}\n\n"
        "def main(argv=None):\n"
        "    args = list(sys.argv[1:] if argv is None else argv)\n"
        "    force_timeout = '--timeout' in args\n"
        "    args = [item for item in args if item != '--timeout']\n"
        "    try:\n"
        "        if len(args) != 1:\n"
        "            raise ValueError('expected one JSON async value')\n"
        "        value = json.loads(args[0])\n"
        "        output = asyncio.run(run(value, force_timeout=force_timeout))\n"
        "    except (asyncio.TimeoutError, TypeError, ValueError) as exc:\n"
        "        print(f'async error: {type(exc).__name__}', file=sys.stderr)\n"
        "        return 2\n"
        "    print(json.dumps(output, ensure_ascii=False, sort_keys=True))\n"
        "    return 0\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"
    )


def _io_adapter_source(*, target_file: str, symbol: str, interface: str) -> str:
    imports = ""
    operation = {
        "file_roundtrip": (
            "        path = Path('value.json')\n"
            "        if invalid:\n"
            "            path = Path('missing.json')\n"
            "            result = json.loads(path.read_text(encoding='utf-8'))\n"
            f"        result = {symbol}(value)\n"
            "        path.write_text(json.dumps(result), encoding='utf-8')\n"
            "        result = json.loads(path.read_text(encoding='utf-8'))\n"
        ),
        "subprocess_pipe": (
            f"        result = {symbol}(value)\n"
            "        child = subprocess.run(\n"
            "            [sys.executable, '-c', 'import sys; data=sys.stdin.read(); print(data)'],\n"
            "            input=json.dumps(result), capture_output=True, text=True, encoding='utf-8', check=True,\n"
            "        )\n"
            "        if invalid:\n"
            "            subprocess.run([sys.executable, '-c', 'raise SystemExit(3)'], check=True)\n"
            "        result = json.loads(child.stdout)\n"
        ),
        "zip_archive": (
            f"        result = {symbol}(value)\n"
            "        with zipfile.ZipFile('value.zip', 'w') as archive:\n"
            "            archive.writestr('value.json', json.dumps(result))\n"
            "        with zipfile.ZipFile('value.zip') as archive:\n"
            "            result = json.loads(archive.read('missing.json' if invalid else 'value.json'))\n"
        ),
    }[interface]
    if interface == "subprocess_pipe":
        imports += "import subprocess\n"
    if interface == "zip_archive":
        imports += "import zipfile\n"
    exceptions = {
        "file_roundtrip": "OSError, TypeError, ValueError",
        "subprocess_pipe": "OSError, subprocess.CalledProcessError, TypeError, ValueError",
        "zip_archive": "KeyError, OSError, TypeError, ValueError, zipfile.BadZipFile",
    }[interface]
    return (
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        + imports
        + f"from {Path(target_file).stem} import {symbol}\n\n"
        "def main(argv=None):\n"
        "    args = list(sys.argv[1:] if argv is None else argv)\n"
        "    invalid = '--invalid' in args\n"
        "    args = [item for item in args if item != '--invalid']\n"
        "    try:\n"
        "        if len(args) != 1:\n"
        "            raise ValueError('expected one JSON I/O value')\n"
        "        value = json.loads(args[0])\n"
        + operation
        + f"    except ({exceptions}) as exc:\n"
        "        print(f'I/O error: {type(exc).__name__}', file=sys.stderr)\n"
        "        return 2\n"
        "    print(json.dumps({'operations': 1, 'result': result}, ensure_ascii=False, sort_keys=True))\n"
        "    return 0\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"
    )


def _framework_adapter_source(*, target_file: str, symbol: str, interface: str) -> str:
    imports = {
        "plugin_hook": "",
        "package_build": "import zipfile\n",
        "code_generation": "import importlib.util\n",
        "docs_render": "import html\n",
    }[interface]
    operation = {
        "plugin_hook": (
            "        callbacks = []\n"
            f"        callbacks.append({symbol})\n"
            "        if invalid:\n"
            "            callbacks.clear()\n"
            "        if not callbacks:\n"
            "            raise RuntimeError('plugin hook is not registered')\n"
            "        result = callbacks[0](value)\n"
        ),
        "package_build": (
            f"        result = {symbol}(value)\n"
            "        Path('dist').mkdir(exist_ok=True)\n"
            "        artifact = Path('dist/demo-1.0-py3-none-any.whl')\n"
            "        with zipfile.ZipFile(artifact, 'w') as wheel:\n"
            "            wheel.writestr('demo-1.0.dist-info/result.json', json.dumps(result))\n"
            "        with zipfile.ZipFile(artifact) as wheel:\n"
            "            member = 'missing.json' if invalid else 'demo-1.0.dist-info/result.json'\n"
            "            result = json.loads(wheel.read(member))\n"
        ),
        "code_generation": (
            f"        result = {symbol}(value)\n"
            "        generated = Path('generated_module.py')\n"
            "        source = 'RESULT = ' + repr(result) + '\\n'\n"
            "        if invalid:\n"
            "            source = 'RESULT = '\n"
            "        generated.write_text(source, encoding='utf-8')\n"
            "        spec = importlib.util.spec_from_file_location('generated_module', generated)\n"
            "        module = importlib.util.module_from_spec(spec)\n"
            "        spec.loader.exec_module(module)\n"
            "        result = module.RESULT\n"
        ),
        "docs_render": (
            f"        result = {symbol}(value)\n"
            "        if invalid:\n"
            "            raise ValueError('template value is missing')\n"
            "        Path('site').mkdir(exist_ok=True)\n"
            "        payload = html.escape(json.dumps(result, ensure_ascii=False))\n"
            "        page = Path('site/index.html')\n"
            "        page.write_text('<main data-result=\"' + payload + '\"></main>', encoding='utf-8')\n"
            "        rendered = page.read_text(encoding='utf-8')\n"
            "        encoded = rendered.split('data-result=\"', 1)[1].split('\"', 1)[0]\n"
            "        result = json.loads(html.unescape(encoded))\n"
        ),
    }[interface]
    return (
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        + imports
        + f"from {Path(target_file).stem} import {symbol}\n\n"
        "def main(argv=None):\n"
        "    args = list(sys.argv[1:] if argv is None else argv)\n"
        "    invalid = '--invalid' in args\n"
        "    args = [item for item in args if item != '--invalid']\n"
        "    try:\n"
        "        if len(args) != 1:\n"
        "            raise ValueError('expected one JSON framework value')\n"
        "        value = json.loads(args[0])\n"
        + operation
        + "    except (AttributeError, KeyError, OSError, RuntimeError, SyntaxError, TypeError, ValueError) as exc:\n"
        "        print(f'framework error: {type(exc).__name__}', file=sys.stderr)\n"
        "        return 2\n"
        "    print(json.dumps({'effects': 1, 'result': result}, ensure_ascii=False, sort_keys=True))\n"
        "    return 0\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"
    )
