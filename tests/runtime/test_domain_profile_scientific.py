from plugins.project_map_report.src.domain_profile import infer_domain_profile


def _profile(root: str, readme: str, extra_file: dict, function: dict):
    return infer_domain_profile(
        {"root": root, "frameworks": [], "entrypoints": [function["path"]], "routes": 0},
        {"files": [{"path": "README.md", "text": readme}, extra_file]},
        {"files": [function]},
        [],
        {"tensorflow", "torch"},
    )


def test_scientific_widget_helpers_do_not_imply_desktop_gui():
    profile = _profile(
        "F:/tmp/proteinsolver",
        "Protein sequence design with tensors, graph solvers, and amino acid prediction.",
        {"path": "notebooks/widget_helpers.py", "text": "def create_widget(): pass"},
        {
            "path": "proteinsolver/utils/protein_design.py",
            "functions": [{"name": "design_sequence", "calls": ["predict"]}],
        },
    )

    assert profile["kind"] == "scientific_compute_library"


def test_scientific_solver_outranks_documentation_noise():
    profile = _profile(
        "F:/tmp/equation_solver",
        "Neural network differential equation solver with boundary conditions and TensorFlow.",
        {"path": "docs/conf.py", "text": "Sphinx documentation with Markdown pages."},
        {"path": "solver.py", "functions": [{"name": "solve", "calls": ["derivative"]}]},
    )

    assert profile["kind"] == "scientific_compute_library"
