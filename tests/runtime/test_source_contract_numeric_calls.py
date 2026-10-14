from runtime.source_contract_semantics import infer_source_contract
from runtime.target_quality import semantic_target_quality_report


def test_numpy_numeric_expression_has_array_contract():
    evidence = infer_source_contract({
        "signature": {"args": [{"name": "actual"}, {"name": "pred"}]},
        "snippet": (
            "def metric(actual, pred):\n"
            "    return np.sqrt(np.mean(np.square(np.log1p(pred) - np.log1p(actual))))"
        ),
    })

    assert evidence["argument_usage_types"] == {"actual": "ArrayLike", "pred": "ArrayLike"}
    assert evidence["inferred_output_type"] == "ArrayLike"


def test_receiver_layer_call_propagates_array_shape():
    evidence = infer_source_contract({
        "signature": {"args": [{"name": "self"}, {"name": "inputs"}]},
        "snippet": "def call(self, inputs):\n    inputs = tf.identity(inputs)\n    return self.output_layer(inputs)",
    })

    assert evidence["argument_usage_types"] == {"inputs": "ArrayLike"}
    assert evidence["inferred_output_type"] == "ArrayLike"


def test_tensorflow_chain_and_unpacked_receiver_flow_have_array_contracts():
    metric = infer_source_contract({
        "signature": {"args": [{"name": "actual"}, {"name": "pred"}]},
        "snippet": (
            "def metric(actual, pred):\n"
            "    actual = tf.cast(actual, tf.float32)\n"
            "    pred = tf.cast(pred, tf.float32)\n"
            "    return tf.math.sqrt(tf.reduce_mean(tf.math.log1p(pred) - tf.math.log1p(actual)))"
        ),
    })
    model = infer_source_contract({
        "signature": {"args": [{"name": "self"}, {"name": "inputs"}, {"name": "training"}]},
        "snippet": "def call(self, inputs, training=False):\n    left, right = inputs\n    left = tf.identity(left)\n    value = self.layer(left)\n    return value",
    })

    assert metric["argument_usage_types"] == {"actual": "ArrayLike", "pred": "ArrayLike"}
    assert metric["inferred_output_type"] == "ArrayLike"
    assert model["argument_usage_types"] == {"inputs": "ArrayLike"}
    assert model["argument_constraint_types"] == {"training": "bool"}
    assert model["inferred_output_type"] == "ArrayLike"
    quality = semantic_target_quality_report(
        "src/model.py:call", ranked_candidates=["src/model.py:call"], source_evidence=["src/model.py:call"],
        structural_evidence=model, input_contract={"inputs": "ArrayLike", "training": "bool"},
        output_contract={"result": "ArrayLike"}, side_effect_contract={"declared": []},
    )
    assert quality["contract_archetype_ids"] == ["numerical_array_transform_boundary"]
    assert quality["score"] >= 97
