from runtime.project_architecture_knowledge import load_architecture_knowledge, match_architecture_rule


def test_domain_profile_rule_beats_generic_config_parser_text_match():
    facts = {
        "root": "SyncOnelapToXoss",
        "domain_profile": {"kind": "protocol_api_client"},
        "inputs": ["configuration", "external API responses"],
        "central": ["client.py:login_browser"],
        "capabilities": ["client.py:login_browser", "client.py:download_fit_file"],
        "scenarios": ["Use the protocol/API client public API."],
        "weak_contracts": ["retry response parser"],
    }

    match = match_architecture_rule(facts, load_architecture_knowledge())

    assert match["rule"]["rule_id"] == "protocol_api_client"


def test_document_cleanup_rule_beats_generic_structured_converter_text_match():
    facts = {
        "root": "notoriouslab_doc-cleaner",
        "domain_profile": {"kind": "desktop_gui_ide"},
        "inputs": ["local files", "configuration"],
        "central": ["cleaner.py:parse_file", "cleaner.py:process_file"],
        "capabilities": ["parsers/pdf.py:extract_text_with_tables", "output/epub.py:create_epub_archive"],
        "scenarios": ["Convert documents to clean structured markdown."],
        "weak_contracts": ["parser failure", "validation", "output collision"],
    }

    match = match_architecture_rule(facts, load_architecture_knowledge())

    assert match["rule"]["rule_id"] == "document_cleanup_conversion_pipeline"


def test_virtualenv_rule_beats_generic_configuration_parser_text_match():
    facts = {
        "root": "pypa_virtualenv",
        "domain_profile": {"kind": "docs_site_generator"},
        "inputs": ["configuration", "target directory", "interpreter"],
        "central": ["src/virtualenv/create/creator.py:validate_dest"],
        "capabilities": [
            "src/virtualenv/run/plugin/creators.py:for_interpreter",
            "src/virtualenv/activation/via_template.py:instantiate_template",
        ],
        "scenarios": ["Create a virtualenv with seed packages and activation scripts."],
        "weak_contracts": ["creator", "activator", "seed", "configuration"],
    }

    match = match_architecture_rule(facts, load_architecture_knowledge())

    assert match["rule"]["rule_id"] == "python_virtual_environment_builder"


def test_release_automation_rule_beats_generic_structured_converter_text_match():
    facts = {
        "root": "python-semantic-release",
        "domain_profile": {"kind": "desktop_gui_ide"},
        "inputs": ["configuration", "git tags", "commit messages"],
        "central": ["src/semantic_release/cli/commands/version.py:version"],
        "capabilities": [
            "src/semantic_release/version/algorithm.py:next_version",
            "src/semantic_release/commit_parser/util.py:parse_paragraphs",
        ],
        "scenarios": ["Detect and publish the next semantic release version."],
        "weak_contracts": ["tags_and_versions", "next_version", "commit parser"],
    }

    match = match_architecture_rule(facts, load_architecture_knowledge())

    assert match["rule"]["rule_id"] == "semantic_release_version_planning"


def test_api_client_sources_do_not_match_generic_configuration_parser():
    facts = {
        "root": "gkeepapi",
        "domain_profile": {"kind": "docs_site_generator"},
        "inputs": ["configuration", "external dependency responses"],
        "central": ["src/gkeepapi/__init__.py:_parseNodes", "src/gkeepapi/__init__.py:send"],
        "capabilities": ["src/gkeepapi/__init__.py:login", "src/gkeepapi/node.py:_load"],
        "weak_contracts": ["parser", "key", "configuration"],
    }

    match = match_architecture_rule(facts, load_architecture_knowledge())

    assert match["rule"]["rule_id"] == "protocol_api_client"


def test_async_database_sources_do_not_match_generic_configuration_parser():
    facts = {
        "root": "aredis",
        "domain_profile": {"kind": "docs_site_generator"},
        "inputs": ["configuration", "connection", "transaction"],
        "central": ["aredis/client.py:execute_command", "aredis/commands/cluster.py:parse_cluster_nodes"],
        "capabilities": ["aredis/pipeline.py:_execute_transaction"],
        "weak_contracts": ["parser", "key", "configuration"],
    }

    match = match_architecture_rule(facts, load_architecture_knowledge())

    assert match["rule"]["rule_id"] == "async_database_access_library"
    assert match["rule"]["architect_consumable"] is True


def test_rest_api_sdk_does_not_match_async_database_without_database_sources():
    facts = {
        "root": "client-python",
        "domain_profile": {"kind": "protocol_api_client"},
        "inputs": ["query parameters", "connection options"],
        "central": ["massive/rest/base.py:_get", "massive/websocket/__init__.py:connect"],
        "capabilities": ["massive/rest/base.py:_get_params", "massive/rest/models/snapshot.py:from_dict"],
        "scenarios": ["Request market data from a remote API."],
        "weak_contracts": ["response parser"],
    }

    match = match_architecture_rule(facts, load_architecture_knowledge())

    assert match["rule"]["rule_id"] == "protocol_api_client"
    assert match["rule"]["architect_consumable"] is True


def test_confident_bioinformatics_profile_beats_incidental_database_text():
    facts = {
        "root": "BEREN",
        "domain_profile": {
            "kind": "bioinformatics_sequence_toolkit",
            "confidence": 0.63,
            "evidence": ["matched FASTA and nucleotide markers"],
        },
        "inputs": ["FASTA records"],
        "central": ["pipeline.py:database_setup", "pipeline.py:recover_contig_id"],
        "capabilities": ["pipeline.py:recover_contig_id"],
        "scenarios": ["Analyze nucleotide sequences and database-backed marker files."],
    }

    match = match_architecture_rule(facts, load_architecture_knowledge())

    assert match["rule"]["rule_id"] == "bioinformatics_sequence_toolkit"


def test_structured_converter_rule_is_architect_consumable():
    facts = {
        "root": "json_query_cli",
        "domain_profile": {"kind": "generic"},
        "inputs": ["unstructured JSON", "structured values"],
        "central": ["query/lib.py:create_json", "query/lib.py:_schema_gen"],
        "capabilities": ["convert structured values", "generate schema"],
    }

    match = match_architecture_rule(facts, load_architecture_knowledge())

    assert match["rule"]["rule_id"] == "structured_data_converter_library"
    assert match["rule"]["architect_consumable"] is True


def test_scientific_compute_rule_is_architect_consumable():
    facts = {
        "root": "proteinsolver",
        "domain_profile": {"kind": "scientific_compute_library"},
        "inputs": ["protein sequence graph", "trained model", "tensor"],
        "central": ["proteinsolver/utils/protein_design.py:design_sequence"],
        "capabilities": ["design protein sequence", "predict amino acid probabilities"],
    }

    match = match_architecture_rule(facts, load_architecture_knowledge())

    assert match["rule"]["rule_id"] == "scientific_compute_library"
    assert match["rule"]["architect_consumable"] is True


def test_scientific_domain_profile_beats_generic_converter_markers():
    facts = {
        "root": "equation_solver",
        "domain_profile": {"kind": "scientific_compute_library"},
        "inputs": ["structured tensor", "boundary conditions"],
        "central": ["math/derivative.py:derivative_stack"],
        "capabilities": ["validate structured domain", "solve differential equation"],
    }

    match = match_architecture_rule(facts, load_architecture_knowledge())

    assert match["rule"]["rule_id"] == "scientific_compute_library"
