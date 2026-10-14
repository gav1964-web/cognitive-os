"""Persist a final deterministic Reviewer decision before reassessment."""
from __future__ import annotations

import json
from pathlib import Path

from .review_findings_builder import build_review_findings
from .role_pipeline_stages import artifact_by_type
from .native_failure_acceptance import FORMAT as NATIVE_FORMAT
from .narrow_type_evidence_binding import content_digest
from .stage_finalization_workspace import inventory


def attach_final_review(experiment: dict, *, artifacts: dict, test_result: dict,
                        native_verification: dict, policy: dict) -> dict:
    complete_result = {**test_result, 'project_native_verification': native_verification,
                       'executor_test_result_path': experiment.get('test_result_path')}
    acceptance = dict(test_result.get('executable_acceptance_result') or {})
    if acceptance.get('format') == NATIVE_FORMAT:
        expected = acceptance.get('patched_inventory_digest')
        try:
            actual = content_digest(inventory(Path(experiment['sandbox_project'])))
        except (OSError, ValueError, TypeError):
            actual = None
        complete_result['post_regression_source_check'] = {
            'status': 'passed' if expected and expected == actual else 'failed',
            'accepted_inventory_digest': expected, 'current_inventory_digest': actual,
        }
    review = build_review_findings(
        technical_spec=artifact_by_type(artifacts, 'TechnicalSpec'),
        implementation_plan=artifact_by_type(artifacts, 'ImplementationPlan'),
        test_plan=artifact_by_type(artifacts, 'TestPlan'), test_result=complete_result,
    )
    accepted = (review.get('conformance_status') == 'passed'
                and review.get('recommendation') in
                set(policy['execution_policy']['allowed_review_recommendations']))
    experiment['checks']['final_review_accepts_patch'] = accepted
    experiment['status'] = 'verified' if all(experiment['checks'].values()) else 'failed'
    experiment['final_review'] = review
    directory = Path(experiment['execution_dir'])
    review_path, test_path = directory / 'final_review.json', directory / 'native_test_result.json'
    for path, content in ((review_path, review), (test_path, complete_result)):
        path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding='utf-8')
    experiment['final_review_path'] = str(review_path)
    experiment['test_result_path'] = str(test_path)
    return complete_result
