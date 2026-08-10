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
