from runtime.first_slice_viability import first_slice_viability


def _context(text: str, *, mutation: bool = False, binding: str = "method_symbol") -> dict:
    return {
        "snippet": {
            "target_binding": binding,
            "text": text,
            "structural_contract": {
                "source_body_complete": True,
                "state_mutation": mutation,
            },
        }
    }


def test_complete_read_only_receiver_uses_source_isolated_fixture():
    result = first_slice_viability(
        "pkg/model.py:Model.render",
        _context("def render(self, value): return self.prefix + value"),
    )

    assert result["status"] == "eligible"
    assert result["reselection_required"] is False
    assert result["receiver_fixture_status"] == "source_isolated_ready"
    assert any(
        row["rule_id"] == "source_isolated_receiver_fixture"
        for row in result["matched_rules"]
    )


def test_complete_mutating_receiver_still_requires_reselection():
    context = _context("def update(self, value): self.value = value", mutation=True)
    context["side_effects"] = ["memory_state"]

    result = first_slice_viability("pkg/model.py:Model.update", context)

    assert result["reselection_required"] is True
    assert result["receiver_fixture_status"] == "state_mutation"


def test_receiver_calling_framework_runtime_requires_specialized_fixture():
    result = first_slice_viability(
        "model/stage.py:Stage.encode",
        _context(
            "def encode(self, value):\n"
            "    value = self.prepare(value)\n"
            "    return tf.convert_to_tensor(value)"
        ),
    )

    assert result["reselection_required"] is True
    assert result["receiver_fixture_status"] == "runtime_dependency"


def test_stateless_method_calling_framework_runtime_requires_specialized_fixture():
    context = _context("def resolve_book(self, info): return BookService.get_book(id=info['id'])")
    context["dependency_readiness"] = {"status": "ready"}
    result = first_slice_viability(
        "api.py:Query.resolve_book",
        context,
    )

    assert result["reselection_required"] is True
    assert result["runtime_call_scope"] == "external_global"


def test_static_method_calling_scalar_parameter_is_fixture_ready():
    result = first_slice_viability(
        "response.py:Response.format_items",
        _context(
            "def format_items(content): return tuple(item.strip() for item in content.split(','))"
        ),
    )

    assert result["reselection_required"] is False
    assert result["runtime_call_scope"] == "receiver_or_builtin"


def test_super_delegating_instance_method_still_requires_receiver_fixture():
    result = first_slice_viability(
        "pkg/widgets.py:PasswordEntry.show_line",
        _context("def show_line(self, value): return super().show_line(value)"),
    )

    assert result["status"] == "deferred"
    assert result["reselection_required"] is True
    assert result["receiver_fixture_status"] == "unsupported_inheritance"


def test_ambiguous_method_requires_class_qualified_receiver_fixture():
    result = first_slice_viability(
        "pkg/widgets.py:show_line",
        _context(
            "def show_line(self, value): return self.render(value)",
            binding="ambiguous_method_symbol",
        ),
    )

    assert result["reselection_required"] is True
    assert result["receiver_fixture_status"] == "ambiguous_owner"
