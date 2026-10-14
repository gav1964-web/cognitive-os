from plugins.project_map_report.src.doc_purpose import docs_text, purpose_heading, purpose_sentence


def test_docs_text_excludes_dependency_manifests_and_hidden_caches() -> None:
    files = {
        "files": [
            {"path": "requirements.txt", "text": "fastapi\nuvicorn\npytest"},
            {"path": ".pytest_cache/README.md", "text": "pytest cache"},
            {"path": "docs/overview.md", "text": "# Gateway\n\nRoutes chat requests to providers."},
        ]
    }

    assert docs_text(files) == "# Gateway\n\nRoutes chat requests to providers."


def test_docs_text_prefers_canonical_root_readme_before_topic_readmes() -> None:
    files = {
        "files": [
            {"path": "README.dialects.rst", "text": "Developing new Dialects\n========================"},
            {"path": "README.rst", "text": "SQLAlchemy\n==========\n\nThe Python SQL Toolkit and Object Relational Mapper"},
        ]
    }

    docs = docs_text(files)

    assert docs.startswith("SQLAlchemy")
    assert purpose_sentence(docs) == "The Python SQL Toolkit and Object Relational Mapper"


def test_purpose_sentence_skips_not_included_section() -> None:
    docs = """# Offline Kursk Map Package

## Quick Start

1. Run `INSTALL.bat`.

## What Is Not Included

The package intentionally excludes:

- huge source files
"""

    assert purpose_sentence(docs) == ""
    assert purpose_heading(docs) == "Offline Kursk Map Package"


def test_purpose_sentence_uses_intro_before_second_level_sections_only() -> None:
    docs = """# Demo Service

Short service description.

## Usage

Run `python app.py`.
"""

    assert purpose_sentence(docs) == "Short service description."


def test_purpose_sentence_does_not_use_usage_instructions_as_purpose() -> None:
    docs = """# Offline Kursk Map Package

## Quick Start

1. Run `INSTALL.bat`.

## Updating Incidents

Put new RTF files into `indoc/`, then run:
"""

    assert purpose_sentence(docs) == ""
    assert purpose_heading(docs) == "Offline Kursk Map Package"


def test_purpose_sentence_reads_common_overview_section() -> None:
    docs = """# Zarr

## What is it?

Zarr implements compressed, chunked, N-dimensional arrays for parallel computing.

## Main Features

- Create arrays.
"""

    assert purpose_sentence(docs) == "Zarr implements compressed, chunked, N-dimensional arrays for parallel computing."


def test_purpose_sentence_skips_sponsor_pitch_before_product_description() -> None:
    docs = """PythonInquirer
==============

Nominate contributors for GitHub Sponsors using this form.

PyInquirer is a collection of common interactive command line user interfaces.
"""

    assert purpose_sentence(docs) == "PyInquirer is a collection of common interactive command line user interfaces."


def test_purpose_heading_does_not_treat_badges_before_blank_line_as_rst_heading() -> None:
    docs = """.. image:: https://example.test/banner.png

|build-status| |coverage| |license|

:Version: 1.0
"""

    assert purpose_heading(docs) == ""
