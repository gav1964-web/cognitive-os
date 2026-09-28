"""Research one explicit, owner-bound documentation question through its role model."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from runtime.role_inference import role_model_config
    from runtime.role_research import validate_request, research_question, persist_research
    from runtime.llm_gateway_bootstrap import ensure_llm_gateway_for_url
    from runtime.stage_finalization_workspace import owned_path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    parser.add_argument('--request', required=True, help='Workspace-relative research request JSON')
    parser.add_argument('--output', required=True, help='Workspace-relative receipt JSON')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    source = owned_path(root, args.request)
    target = owned_path(root, args.output)
    if (source.name == 'config.json' or source.name.startswith('.env')
            or source.stat().st_size > 100_000 or target.exists()):
        parser.error('unsafe input or existing output; preserve previous receipts')
    request = validate_request(json.loads(source.read_text(encoding='utf-8')), root)
    config = role_model_config(request['role'])
    if ensure_llm_gateway_for_url(root, config.base_url)['status'] == 'failed':
        parser.error('gateway readiness failed')
    result = research_question(request, config=config, root=root)
    result['receipt'] = persist_research(result, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'checked_claims': len(result['checked_claims']),
        'search_usage': result['search_usage'], 'admission': result['admission'],
        'receipt': result['receipt']}, ensure_ascii=False))
    return 0 if result['status'] == 'evidence_checked' else 2


if __name__ == '__main__':
    raise SystemExit(main())
