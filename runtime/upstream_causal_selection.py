"""Bind native proposal comparison to Analyzer diagnosis and downstream design."""
from copy import deepcopy
from pathlib import Path

from .narrow_type_evidence_binding import content_digest
from .patch_synthesis_policy import load_patch_synthesis_policy
from .programmer_training_repair_patch import training_repair_patch
from .project_failure_causal_diagnosis import infer_causal_hypotheses
from .stage_finalization_workspace import inventory, owned_path
from .upstream_causal_trials import compare_causal_candidates


def validate_diagnosis_proposals(diagnosis: dict, *, project: Path, root: Path,
                                authorized: bool = False) -> dict:
    if not authorized:
        raise ValueError('explicit_training_trial_authorization_required')
    result = deepcopy(diagnosis)
    issues = [r for r in result.get('issues', []) if r.get('failure_specific_reducer_required')]
    recipes = load_patch_synthesis_policy(root / 'config/patch_synthesis_policy.json')['recipes']
    for issue in issues:
        # A declined comparison must not retain earlier template execution authority.
        issue['allowed_operator_ids'] = []
        issue.pop('training_replay_authority', None)
        issue.pop('llm_training_replay', None)
        design = issue.setdefault('repair_design', {})
        design.update(status='proposal_review_required', execution_authority=False)
        comparison = {'status': 'not_compared', 'reason': 'single_failure_issue_required'}
        proposals = []
        try:
            if len(issues) != 1:
                raise ValueError('single_failure_issue_required')
            hypotheses = infer_causal_hypotheses(issue, project_dir=project, workspace_root=root)
            if not 1 <= len(hypotheses) <= 4:
                raise ValueError('one_to_four_matching_training_hypotheses_required')
            hashes = inventory(project)
            packet = issue.get('failure_evidence_packet') or {}
            target = packet.get('target', '')
            path_text, _, symbol = target.partition(':')
            source = owned_path(project, path_text).read_bytes().decode('utf-8')
            for hypothesis in hypotheses:
                proposal = hypothesis['repair_design']
                operator = proposal['proposed_operator_id']
                recipe = recipes.get(operator, {})
                if not recipe.get('enabled') or recipe.get('authority') != 'training_only':
                    raise ValueError('matching_proposal_has_no_supported_training_recipe')
                patch = training_repair_patch(source, symbol=symbol,
                    operation_kind=recipe.get('operation_kind', ''), recipe=recipe)
                if patch is None:
                    raise ValueError('matching_proposal_has_no_supported_source_patch')
                proposals.append({'id': hypothesis['causal_hypothesis']['pattern_id'],
                    'operator_id': operator, 'origin': 'training_rule_proposal',
                    'source_sha256': hashes[path_text], 'replacement_source': patch['source'],
                    'hypothesis': hypothesis, 'recipe_digest': content_digest(recipe),
                    'source_precondition': patch.get('source_precondition'),
                    'affected_symbols': patch.get('affected_symbols', [symbol])})
            comparison = compare_causal_candidates(project=project, packet=packet, candidates=proposals,
                work_dir=root / 'artifacts/causal_proposal_trials', authorized=True)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            comparison = {'status': 'not_compared', 'reason': str(exc), 'source_apply': False}
        issue['causal_comparison'] = comparison
        selected = next((r for r in proposals if r['id'] == comparison.get('selected_candidate_id')), None)
        if comparison['status'] == 'selected_for_regression' and selected:
            issue['causal_hypothesis'] = {**selected['hypothesis']['causal_hypothesis'],
                'status': 'supported_by_targeted_intervention', 'comparison_digest': comparison['comparison_digest'],
                'limitations': 'existing training proposal; recorded failures only; not a unique root-cause proof'}
            issue['repair_design'] = {**selected['hypothesis']['repair_design'],
                'status': 'training_replay_ready', 'execution_authority': 'explicit_training_replay',
                'causal_comparison': comparison,
                'source_precondition': selected['source_precondition'],
                'affected_symbols': selected['affected_symbols'],
                'preservation_evidence': 'targeted tests only; complete native regression and final review required'}
            issue['affected_targets'] = list(issue['repair_design'].get('affected_targets') or [target])
            issue['allowed_operator_ids'] = [selected['operator_id']]
            issue['training_replay_authority'] = {'status': 'explicitly_authorized',
                'scope': 'consumed_training_case_sandbox_only', 'operator_id': selected['operator_id'],
                'source_apply': False, 'promotion_allowed': False}
        issue['causal_feedback'] = {
            'role': 'architect' if selected else 'analyzer',
            'next_action': 'bind_supported_design_and_run_full_regression' if selected else
                           'collect_discriminating_evidence_or_revise_proposals',
            'automatic_retry': False, 'reason': comparison['status']}
    return result
