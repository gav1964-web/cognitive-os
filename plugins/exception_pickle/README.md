# Exception pickle competency

Owner of the exception-constructor reconstruction mechanism. This plugin contains
the active pattern catalog, boundary profile, source contrast, active-profile
overlay, strict source-to-source patch generator and constructor sample inference.
The active catalog was moved
without changing its evidence or admission state; registration is not a new
certification of general repair quality.

`src/main.py:run` accepts the versioned manifest/schema contract:

| Operation | Result |
|---|---|
| `boundary_profiles` | Owned raw boundary profiles |
| `source_contrasts` | Owned source contrasts with their original provenance |
| `patterns` | Active/absent reconstruction catalog |
| `decorate_profile` | Active overlay for the owned profile |
| `propose_patch` | Source proposal or `not_applicable`; never applies a patch |
| `sample_values` | Ordered sample descriptors for names, optionally informed by source text and object contracts; `null` for unknown shapes |
| `constructor_call` | Positional/keyword argument descriptors from source text and explicit samples |
| `validate_patterns` | Validate a supplied catalog document, preserving its data; never reads it from a path or promotes it |
| `prepare_promotion` | Prepare and validate a candidate catalog from explicit documents/timestamp; returns `prepared`, never writes or grants approval |

Version 0.4.0 moves the promotion-document builder into the owner. Inputs are
`readiness`, `evaluator`, `holdout` (objects) and `generated_at` (string).
The candidate retains the previous serialized fields, including the intended
`active` state and promotion-authority label; these are draft data, not evidence
that a transaction ran. The envelope is `status: prepared`.
`runtime.exception_pickle_promotion_contract` calls this read-only operation.
The governance transaction retains all nine authorization/evidence/regression
gates and invokes preparation only after they pass. It owns serialization,
atomic write and reload checks. No registry refresh occurs automatically.
See `docs/architecture/pickle_promotion_20260915.md` for the exact boundary.

Version 0.3.0 separates installed knowledge from supplied research documents.
`patterns` reads the registered installation's KB. `validate_patterns` accepts
`document` (object, or null for absent) and returns the checked catalog with
`status: ok`. This validates the existing schema/operator/safety constraints;
it does not certify provenance, independent evaluation or an `active` claim.
The pure validator is shared by installed loading and document validation.
`runtime.exception_pickle_catalog_contract` exposes `read_installed_patterns`,
`read_research_patterns(path)` and `validate_research_patterns(document)`.
Research consumers retain explicit roots and missing-file behavior; config doctor
reads the installed catalog through registry. All routes check validator identity;
no private-call fallback or automatic registration occurs. Full ownership notes:
`docs/architecture/pickle_catalogs_20260915.md`.

Version 0.2.0 adds the two sample operations. `sample_values` takes `names` and
optional `object_contracts`; when `source` is supplied, `class_name` is required.
`constructor_call` takes `source`, `class_name`, `required` and `samples`.
Both return `status: ok`; this reports completion of inference, not successful
replay or admission of knowledge. Source is text, never a project file path.
Sample inference does not read project files or execute their code. The runtime
client `exception_pickle_sample_contract` owns file reads and registry admission;
Research / Replay retains descriptor materialization and subprocess execution.
Legacy constructor/source sample modules are compatibility aliases only.
See `docs/architecture/pickle_samples_20260915.md` for consumers and evidence.

Version 0.1.1 requires the recipe's `required_constructor_inputs` to cover every
declared constructor parameter, including defaults and keyword-only parameters.
Used variadic or omitted named inputs are `not_applicable`; ignored variadics retain
the existing supported shape. Direct locals/vars/eval/exec capture also blocks
variadic omission. These are bounded AST checks, not a proof against arbitrary
reflection. The plugin does not silently
extend an authorized recipe. A fully covered stored default retains the existing
replay strategy; keyword-only reconstruction still requires its explicit flag.
This closes the observed omitted-default loss. It is not a general guarantee
for arbitrary post-construction attributes, custom object protocols or slots;
native tests must still verify the full requested behavior.

The generic registry route validates schemas, lifecycle and the hash covering code,
schemas and local KB. Local KB reads are uncached and return fresh objects. A KB
change invalidates registry identity; it requires the normal verified registration
step. Imported code changes require a fresh process rather than silently reusing
old Python modules. Hash registration itself does not promote knowledge or change
source-application authority.

The four working patch consumers (authorized implementation, active application,
static risk and autonomous shadow) use
`runtime.exception_pickle_contract.propose_exception_pickle_patch`. This typed
client calls the registered `propose_patch` operation, checks its response and
returns the unchanged proposal dictionary or `None` for `not_applicable`.
Registry/schema errors propagate without a direct-call fallback. Its
`competency_root` denotes the COS installation, independently of the target
project or research corpus root. Admission checks cover the installed mechanism;
they do not promote an experimental recipe or grant source-application authority.

Typed owner APIs remain available for internal/plugin and compatibility callers:
`src.knowledge.load_exception_pickle_patterns(path)` for an explicit research
catalog, and `src.patch.exception_pickle_reconstruction_patch(...)` for a pure
proposal. These library calls do not perform registry admission. Working runtime
catalog and patch consumers now use registered clients; research reads retain
their explicit input paths. The temporary
`runtime/programmer_exception_pickle_patch.py` alias now delegates to the same
registered client; remove it when downstream compatibility imports retire.
Runtime callers retain their existing authorization, native replay and review
checks. The remaining owner/API map is in
`docs/architecture/pickle_consumers_20260915.md`.

Research orchestration, independent evaluation, materializer/import experiments
and promotion transactions remain under `runtime/exception_pickle_*.py` for this
pilot. They are not all part of the callable plugin. Promotion writes the owner's
catalog at the new path and retains its approval/evidence checks. It does not
automatically update plugin registration. Their further separation is queued.
The source-analysis and base-sample algorithms now live here; object-contract
classification remains in Research with a direct sample-client dependency.

Tests: `plugins/exception_pickle/tests`, `tests/runtime/test_competency_knowledge.py`,
`tests/runtime/test_programmer_exception_pickle_patch.py` and existing boundary,
application and promotion regressions. Runtime declarations/static lint are not an
OS sandbox for untrusted plugins.
