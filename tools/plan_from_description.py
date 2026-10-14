"""Carry explicitly reviewed product claims into Analyzer, Architect and SpecWriter."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.product_context import make_product_context
from runtime.role_project_analysis import analyze_role_project
from runtime.architecture_decision_builder import build_architecture_decision
from runtime.technical_spec_builder import build_technical_spec


def plan(report, review, task, goal):
    context = make_product_context(report, accepted_claim_ids=review['accepted_claim_ids'],
        reviewer=review['reviewer'], notes=review.get('notes'), constraints=review.get('constraints'),
        review_proposals=review.get('review_proposals'), review_decisions=review.get('review_decisions'))
    analysis = analyze_role_project(root=ROOT, project_dir=Path(context['project_root']),
        goal=goal, task_contract=task, product_context=context)['project_map_report']
    architecture = build_architecture_decision(goal=goal, project_report=analysis)
    specification = build_technical_spec(architecture_decision=architecture)
    return {'schema_version': 'product_understanding_plan.v1', 'goal': goal,
            'analysis': analysis, 'architecture': architecture, 'specification': specification,
            'execution_authorized': False, 'source_application': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--description', required=True)
    parser.add_argument('--review', required=True, help='Explicit reviewer and accepted_claim_ids; caller attestation')
    parser.add_argument('--task', required=True, help='Existing upstream_task_contract.v1')
    parser.add_argument('--goal', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    read = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))
    result = plan(read(args.description), read(args.review), read(args.task), args.goal)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(target), 'execution_authorized': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
