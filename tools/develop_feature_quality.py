"""Opt-in plugin-owned quality checks and autonomous bounded role repair."""
import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.feature_acceptance import save
from runtime.feature_inference import FeatureChat
from runtime.feature_quality import run_quality_development
from runtime.llm_gateway_bootstrap import ensure_llm_gateway_for_url
from runtime.role_inference import role_model_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir', required=True)
    parser.add_argument('--goal', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--model', required=True)
    parser.add_argument('--budget-limit', type=int, default=1000000)
    parser.add_argument('--budget-authorization')
    series = parser.add_mutually_exclusive_group()
    series.add_argument('--carry-ledger')
    series.add_argument('--new-series', action='store_true',
                        help='Explicitly start a separately authorized series; never use to reset a continuation')
    parser.add_argument('--max-calls', type=int, default=40)
    parser.add_argument('--max-cycles', type=int, default=4)
    parser.add_argument('--require-rejected-candidate-witness', action='store_true',
                        help='Require new acceptance to expose a reviewed behavioral defect before paid audit')
    args = parser.parse_args()
    out = Path(args.output).resolve()
    if out.exists() or not 1 <= args.max_calls <= 80:
        parser.error('fresh output and max-calls1..80 required')
    configs = {r: replace(role_model_config(r), model=args.model, fallbacks=(),
                         timeout_seconds=480, max_output_tokens=32768)
               for r in ('analyzer', 'architect', 'spec_writer')}
    receipt = ensure_llm_gateway_for_url(Path.cwd(), configs['analyzer'].base_url)
    if receipt['status'] not in ('started', 'already_running'):
        raise RuntimeError('quality_gateway_not_ready')
    out.mkdir(parents=True)
    save(out / 'gateway.json', receipt)
    carry = args.carry_ledger
    chat = FeatureChat(out, max_calls=args.max_calls, max_input_bytes=100000,
        carry=carry, budget_limit=args.budget_limit, budget_authorization=args.budget_authorization,
        start_new_series=args.new_series)
    save(out / 'request.json', vars(args))
    result = run_quality_development(project=args.project_dir, work=out / 'run', goal=args.goal,
        python=Path(args.python), chat=chat, configs=configs, max_cycles=args.max_cycles,
        require_rejected_candidate_witness=args.require_rejected_candidate_witness)
    print(json.dumps({k: result.get(k) for k in ('status', 'reason', 'checkpoint', 'autonomy')}, ensure_ascii=True))
    return 0 if result['status'] == 'verified' else 1


if __name__ == '__main__':
    raise SystemExit(main())
