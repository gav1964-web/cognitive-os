from plugins.project_map_report.src.domain_profile import infer_domain_profile
from runtime.contract_archetype_inference import contract_archetype_for_target
from runtime.project_architecture_knowledge import load_architecture_knowledge, match_architecture_rule


def test_har_recorder_profile_and_architecture_are_proxy_specific():
    text = "mitmproxy.tools.main.run mitmdump hardump start recording traffic in HAR format"
    profile = infer_domain_profile(
        {"root": "/work/har-recorder", "frameworks": [], "entrypoints": ["main.py"], "routes": 0},
        {"files": [{"path": "main.py", "text": text}]},
        {"files": [{"path": "main.py", "functions": [{"name": "runproxy", "calls": []}]}]},
        [],
        {"mitmproxy"},
    )
    facts = {
        "root": "/work/har-recorder",
        "frameworks": [],
        "task": profile["purpose_summary"],
        "domain_profile": profile,
        "central": ["src/recorder/main.py:runproxy"],
        "process_boundary": ["src/recorder/main.py:runproxy"],
        "capabilities": ["src/recorder/main.py:start", "src/recorder/main.py:stop"],
    }

    match = match_architecture_rule(facts, load_architecture_knowledge())

    assert profile["kind"] == "har_recording_proxy_cli"
    assert match["rule"]["rule_id"] == "har_recording_proxy_cli"
    assert match["rule"]["first_slice"]["name"] == "proxy_recorder_lifecycle_slice"


def test_iteration10_contract_families_are_profiled():
    dynamic_import = contract_archetype_for_target("django_auth/views.py:_import_object")
    plot = contract_archetype_for_target("scientific/read_band_data.py:read_and_plot_bands")
    model = contract_archetype_for_target("exonet.py:forward")
    profiler = contract_archetype_for_target("utils.py:time_profiler")
    recorder = contract_archetype_for_target("src/gitlabrecorder/main.py:runproxy")

    assert dynamic_import["contract_family"] == "django_framework_operation_boundary"
    assert plot["contract_family"] == "visualization_render_boundary"
    assert model["contract_family"] == "model_inference_transform_boundary"
    assert profiler["contract_family"] == "profiling_decorator_boundary"
    assert recorder["contract_family"] == "traffic_recording_proxy_boundary"
