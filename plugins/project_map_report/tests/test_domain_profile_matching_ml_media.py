from __future__ import annotations

from plugins.project_map_report.src.domain_profile import infer_domain_profile
from plugins.project_map_report.src.runtime_readiness import minimal_extraction_plan

def test_domain_profile_recognizes_neural_network_training_pipeline():
    profile = infer_domain_profile(
        {"root": "F:/tmp/neural_lab", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [{"path": "README.md", "text": "Train a neural network with stochastic gradient descent and backpropagation."}]},
        {"files": [{"path": "network.py", "functions": [{"name": "backprop", "calls": []}]}]},
        [],
        {"numpy"},
    )
    assert profile["kind"] == "neural_network_training_pipeline"
    assert "gradients and updated parameters" in profile["output_summary"]


def test_domain_profile_prefers_reinforcement_learning_over_generic_scientific_compute():
    profile = infer_domain_profile(
        {"root": "F:/tmp/policy-lab", "frameworks": [], "entrypoints": ["train.py"], "routes": 0},
        {
            "files": [
                {
                    "path": "README.md",
                    "text": "Train fair policies with cooperative multi-agent reinforcement learning and policy networks.",
                },
                {
                    "path": "common/utils.py",
                    "text": "import numpy as np\ndef discount_rewards(rewards, gamma): return rewards\n",
                },
            ]
        },
        {
            "files": [
                {"path": "common/utils.py", "functions": [{"name": "discount_rewards", "calls": ["np.asarray"]}]}
            ],
            "imports": ["numpy", "tensorflow"],
        },
        [],
        {"numpy", "tensorflow"},
    )

    assert profile["kind"] == "reinforcement_learning_training_pipeline"
    assert "observations, actions, rewards" in profile["purpose_summary"]


def test_rl_domain_markers_promote_reward_math_into_extraction_window():
    plan = minimal_extraction_plan(
        {
            "pure_transform_candidates": [
                {"path": "common/env.py", "name": "neighbors", "loc": 2, "calls": []},
                {
                    "path": "common/utils.py",
                    "name": "discount_rewards",
                    "loc": 8,
                    "calls": ["np.zeros_like"],
                },
            ]
        },
        [],
        [],
        domain_profile={"target_markers": ["discount_rewards", "eligibility_traces"]},
    )

    assert plan["capabilities_to_extract"][0]["capability"] == "common/utils.py:discount_rewards"
    assert plan["capabilities_to_extract"][0]["candidate_level"] == "domain_preferred"


def test_atomistic_toolkit_is_not_reclassified_by_optional_database_surface():
    profile = infer_domain_profile(
        {
            "root": "F:/tmp/ase-abacus",
            "frameworks": [],
            "entrypoints": ["ase/__init__.py"],
            "routes": 0,
        },
        {
            "files": [
                {
                    "path": "README.rst",
                    "text": "Tools for atomistic simulations using NumPy and SciPy; an optional database web-interface is available.",
                },
                {
                    "path": "ase/atoms.py",
                    "text": "def string2vector(value): return value\n# atomic positions and chemical symbols",
                },
            ]
        },
        {
            "files": [
                {"path": "ase/atoms.py", "functions": [{"name": "string2vector", "calls": []}]},
                {"path": "ase/db/core.py", "functions": [{"name": "connect", "calls": []}]},
            ],
            "imports": ["numpy", "sqlite3"],
        },
        [],
        {"numpy", "sqlite3"},
    )

    assert profile["kind"] == "atomistic_simulation_toolkit"
    assert "string2vector" in profile["target_markers"]


def test_model_inference_api_wins_over_incidental_web_framework_shape():
    profile = infer_domain_profile(
        {
            "root": "F:/tmp/object-detection-inference-api",
            "frameworks": ["FastAPI"],
            "entrypoints": ["api.py"],
            "routes": 6,
        },
        {
            "files": [
                {
                    "path": "README.md",
                    "text": "Object detection inference API using TensorFlow pretrained models. Send images and predict detections.",
                },
                {"path": "api.py", "text": "def predict(image): return model.predict(image)"},
            ]
        },
        {"files": [{"path": "api.py", "functions": [{"name": "predict", "calls": ["model.predict"]}]}]},
        [{"path": "/predict", "function": "predict"}],
        {"fastapi", "tensorflow"},
    )

    assert profile["kind"] == "model_inference_api"
    assert "predict" in profile["target_markers"]


def test_model_inference_api_requires_explicit_project_identity_signal():
    profile = infer_domain_profile(
        {"root": "F:/tmp/confusion-matrix", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [{"path": "README.md", "text": "Scientific metrics for predicted and actual class labels."}]},
        {"files": [{"path": "metrics.py", "functions": [{"name": "score", "calls": []}]}], "imports": ["numpy"]},
        [],
        {"numpy"},
    )

    assert profile["kind"] != "model_inference_api"


def test_confusion_matrix_library_is_not_treated_as_web_or_inference_runtime():
    profile = infer_domain_profile(
        {"root": "F:/tmp/pycm", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [{"path": "README.md", "text": "Multi-class confusion matrix with class statistics and overall statistics."}]},
        {"files": [{"path": "pycm.py", "functions": [{"name": "confusion_matrix", "calls": []}]}]},
        [],
        set(),
    )

    assert profile["kind"] == "classification_metrics_library"
    assert "confusion_matrix" in profile["target_markers"]


def test_ood_detector_library_prefers_prediction_scores_over_image_training():
    profile = infer_domain_profile(
        {"root": "F:/tmp/pytorch-ood", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [{"path": "README.md", "text": "PyTorch out-of-distribution detection with pretrained detectors and logits."}]},
        {
            "files": [
                {
                    "path": "src/pytorch_ood/detector/energy.py",
                    "functions": [
                        {"name": "predict_features", "calls": []},
                        {"name": "score", "calls": []},
                    ],
                }
            ]
        },
        [],
        {"torch"},
    )

    assert profile["kind"] == "out_of_distribution_detection_library"
    assert profile["target_markers"][0] == "predict_features"


def test_streaming_dataset_library_is_not_treated_as_worker_queue():
    profile = infer_domain_profile(
        {"root": "F:/tmp/mosaicml__streaming", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [{"path": "README.md", "text": "Cloud-native Streaming Dataset with Mosaic Dataset Shard and MDSWriter."}]},
        {
            "files": [
                {
                    "path": "streaming/base/format/mds/encodings.py",
                    "functions": [
                        {"name": "mds_encode", "calls": []},
                        {"name": "mds_decode", "calls": []},
                    ],
                }
            ]
        },
        [],
        {"torch"},
    )

    assert profile["kind"] == "streaming_dataset_library"
    assert profile["target_markers"][:3] == ["mds_encode", "mds_decode", "infer_dataframe_schema"]


def test_automlops_is_pipeline_generation_not_dataframe_etl():
    profile = infer_domain_profile(
        {"root": "F:/tmp/GoogleCloudPlatform__automlops", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [{"path": "README.md", "text": "AutoMLOps pipeline generation and deployment orchestration."}]},
        {
            "files": [
                {
                    "path": "utils.py",
                    "functions": [
                        {"name": "git_workflow", "calls": []},
                        {"name": "resources_generation_manifest", "calls": []},
                    ],
                }
            ]
        },
        [],
        set(),
    )

    assert profile["kind"] == "mlops_pipeline_generator"


def test_domain_profile_recognizes_blender_animation_addon():
    profile = infer_domain_profile(
        {"root": "F:/tmp/animtoolbox", "frameworks": [], "entrypoints": [], "routes": 0},
        {"files": [{"path": "README.md", "text": "Animation and rigging tools for Blender."}]},
        {
            "files": [
                {
                    "path": "BakeToCtrl.py",
                    "functions": [{"name": "constraint_add", "calls": ["bpy.ops.pose.constraint_add"]}],
                }
            ]
        },
        [],
        {"bpy"},
    )

    assert profile["kind"] == "blender_animation_addon"
    assert len(profile["scenario_summary"]) >= 3
