from runtime.contract_archetype_inference import contract_archetype_for_target


def test_device_protocol_and_media_contract_archetypes():
    cases = {
        "aiomqtt/_client.py:publish": "mqtt_client_operation_boundary",
        "mobly/controllers/android_device_lib/apk_utils.py:_execute_adb_install": "device_command_execution_boundary",
        "draft/_script_file_template.py:replace_material_by_name": "media_template_material_replacement",
        "core/mouse_hook_linux.py:_find_mouse_device": "hid_device_discovery_boundary",
    }
    for target, expected in cases.items():
        contract = contract_archetype_for_target(target)
        assert contract["contract_archetype"] == expected
        assert contract["input_contract"] and contract["output_contract"]


def test_device_protocol_archetypes_require_domain_paths():
    specialized = {"mqtt_client_operation_boundary", "device_command_execution_boundary", "media_template_material_replacement", "hid_device_discovery_boundary"}
    for target in ("release.py:publish", "runtime.py:process_timerange", "device.py:hid_runtime_state"):
        assert contract_archetype_for_target(target).get("contract_archetype") not in specialized
