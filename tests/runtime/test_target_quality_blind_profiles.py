from __future__ import annotations

from runtime.target_quality import semantic_target_quality_report


def test_semantic_target_quality_accepts_profiled_blind_redteam_contracts():
    cases = [
        "conan/api/subapi/workspace.py:_parse_module",
        "src/cryptography/hazmat/asn1/asn1.py:_normalize_field_type",
        "domains/cpp/__init__.py:_resolve_xref_inner",
        "upgrade_extension.py:update_extension",
        "celery/app/trace.py:build_tracer",
        "src/click/core.py:_parse_decls",
        "src/requests/sessions.py:resolve_redirects",
        "src/_pytest/_py/path.py:make_numbered_dir",
        "src/marshmallow/schema.py:_deserialize",
        "typer/rich_utils.py:rich_format_help",
        "dev/clint/src/clint/linter.py:lint_file",
        "src/werkzeug/serving.py:run_wsgi",
        "bootstrap.py:_async_resolve_domains_and_preload",
        "yarl/_url.py:build",
        "channels/auth.py:login",
        "uvloop/__init__.py:__getattr__",
        "numba/core/analysis.py:dead_branch_prune",
        "bandit/formatters/custom.py:report",
        "tornado/template.py:_parse",
        "_src/jaxpr_util.py:jaxpr_to_html",
        "zstandard/backend_cffi.py:train_dictionary",
        "rustworkx/visualization/matplotlib.py:draw_edge_labels",
        "client/commands/analyze.py:create_analyze_arguments",
        "pyright-internal/src/typeServer/protocol/generate_json.py:_parse_enums",
        "src/msgspec/_utils.py:get_class_annotations",
        "src/apscheduler/datastores/mongodb.py:acquire_jobs",
        "limits/aio/storage/memcached/emcache.py:incr",
        "arrow/arrow.py:dehumanize",
        "bottle.py:add",
        "authlib/jose/rfc7516/jwe.py:serialize_json",
        "boltons/debugutils.py:wrap_trace",
        "src/webargs/pyramidparser.py:use_args",
        "src/engineio/async_client.py:_connect_websocket",
        "src/socketio/async_client.py:connect",
        "src/flask_principal.py:init_app",
        "pyramid/config/routes.py:add_route",
        "graphene/types/schema.py:create_fields_for_type",
        "jwt/api_jwt.py:_validate_claims",
        "src/cattrs/gen/typeddicts.py:make_dict_structure_fn",
        "annotation.py:_resolve_evaled_type",
    ]
    for target in cases:
        report = semantic_target_quality_report(
            target,
            ranked_candidates=[target],
            source_evidence=[target],
            selection_reason="deterministic parser/normalizer/validator shape",
        )
        assert report["status"] == "strong", target
        assert report["score"] >= 92, target
        assert report["profiled_contract_family"] is True, target
