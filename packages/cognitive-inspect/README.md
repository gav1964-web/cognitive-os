# Cognitive Inspect

Read-only repository facts extracted from Cognitive OS. Alpha, Python 3.10+;
standard library only. No role planning, architecture scoring or patch execution.

```bash
python -m pip install ./packages/cognitive-inspect
python -m pytest packages/cognitive-inspect/tests -q --import-mode=importlib
```

```python
from cognitive_inspect import scan_project_tree, extract_python_structure

tree = scan_project_tree({"path": "project", "max_files": 5000, "max_depth": 8})
structure = extract_python_structure({"root": "project"})
```

Public API: `scan_project_tree`, `detect_project_stack`,
`extract_python_structure`, `extract_runtime_commands`. Each accepts a payload
dictionary and returns the existing plugin result dictionary. Roots are limited
to the current directory and its parent; use a working directory appropriate to
the repository being inspected. Commands are discovered, never executed.
Budgets, skipped files and parser limitations remain visible in the results.
Heuristic insights are candidates, not a verified understanding of a project.

`cognitive_inspect.ast_navigation` exposes `parent_map(node)` and
`find_top_level_function(tree, name)` for shared neutral AST traversal. They
return original nodes without mutation or file IO. Lookup considers direct
module-level sync/async functions and returns the first matching definition;
it does not search class methods or nested functions. No repair rules live here.
Generic Python syntax is parsed when the host supports it. Python 2 conversion
uses stdlib lib2to3 on Python 3.10–3.12; on 3.13+ those files are reported as skipped
syntax errors. No compatibility converter is bundled.

`src/cognitive_inspect/` owns the implementation. Cognitive OS plugin entrypoints
and the two old runtime utility modules are compatibility aliases. Their schemas
remain in `plugins/*/schemas/` in the monorepo; the Python API needs no registry.

Run installed-distribution checks with `python tools/verify_subprojects.py` from
the monorepo. A published release and independent consumer validation remain pending.
# AST call names

`cognitive_inspect.ast_navigation.call_name(node)` returns the existing syntactic
Name/Attribute spelling without mutation or import resolution. JSON serialization
and remaining helper reducers share this neutral function.

## Read-only JSON CLI

`python -m cognitive_inspect PATH --max-files 5000 --max-depth 8` exposes the
existing tree scanner without importing or executing the inspected project.
JSON is written to stdout; invalid paths/budgets produce an error on stderr and
exit code 2. The current-directory/parent scope restriction is unchanged.
The four dictionary-based Python APIs remain compatible.
