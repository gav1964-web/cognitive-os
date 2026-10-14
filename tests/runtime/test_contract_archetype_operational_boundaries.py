from runtime.contract_archetype_inference import contract_archetype_for_target


def test_installer_and_structured_overlay_boundaries_are_profiled():
    assert contract_archetype_for_target("install.py:main")["contract_family"] == "filesystem_installer_transaction"
    assert contract_archetype_for_target("pkg/toml_support.py:_overlay_item")["contract_family"] == "structured_overlay_transform"


def test_operational_archetypes_cover_network_finance_and_infrastructure():
    cases = {
        "minecraft/networking/connection.py:react": "network_protocol_reactor_boundary",
        "requests_ip_rotator/ip_rotator.py:init_gateway": "managed_api_gateway_lifecycle",
        "backend/app/indicators/pipeline.py:compute_enriched_today": "financial_series_computation_boundary",
        "titan/blueprint.py:_build_resource_graph": "infrastructure_resource_graph_boundary",
    }
    for target, expected in cases.items():
        contract = contract_archetype_for_target(target)
        assert contract["contract_archetype"] == expected
        assert contract["input_contract"] and contract["output_contract"]


def test_operational_archetypes_do_not_match_generic_symbols():
    specialized = {
        "network_protocol_reactor_boundary",
        "managed_api_gateway_lifecycle",
        "financial_series_computation_boundary",
        "infrastructure_resource_graph_boundary",
    }
    for target in ("runtime/loop.py:react", "http/client.py:send", "collection.py:items"):
        assert contract_archetype_for_target(target).get("contract_archetype") not in specialized


def test_data_protocol_and_recovery_contracts_are_profiled():
    cases = {
        "featurewiz/blagging.py:predict_log_proba": "probabilistic_model_inference",
        "asyncmy/replication/row_events.py:_read_column_data": "binary_row_decoder",
        "mqttwarn/services/thingspeak.py:plugin": "outbound_service_plugin_transaction",
        "nsq/writer.py:_on_connection_close": "connection_recovery_callback",
        "mrmr/pandas.py:_ks_classif": "dataframe_feature_scoring",
    }
    for target, expected in cases.items():
        contract = contract_archetype_for_target(target)
        assert contract["contract_archetype"] == expected
        assert contract["input_contract"] and contract["output_contract"]
