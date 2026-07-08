from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from runtime.dialogue_memory import DialogueMemory


def test_dialogue_memory_records_and_recalls_decision(tmp_path):
    memory = DialogueMemory(tmp_path)
    session = memory.create_session(title="Architecture", topic="memory")
    memory.add_turn(session["dialogue_id"], role="user", content="How do we remember topic context?")
    decision = memory.note(
        kind="decision",
        topic="memory",
        dialogue_id=session["dialogue_id"],
        text="Dialog memory stores conversation context but never executes plugins.",
    )

    recall = memory.recall("conversation context plugins")
    summary = memory.summary(dialogue_id=session["dialogue_id"])

    assert recall["recommendation"]["action"] == "CONSIDER_DIALOGUE_CONTEXT"
    assert recall["matches"][0]["record_id"] == decision["record_id"]
    assert summary["active_topic"] == "memory"
    assert summary["decisions"][0]["text"] == decision["text"]


def test_dialogue_memory_switches_topics(tmp_path):
    memory = DialogueMemory(tmp_path)
    session = memory.create_session(title="MVP", topic="foundry")

    switched = memory.switch_topic(session["dialogue_id"], "dialogue-memory")
    reloaded = memory.load_session(session["dialogue_id"])

    assert switched["previous_topic"] == "foundry"
    assert reloaded["active_topic"] == "dialogue-memory"


def test_dialogue_memory_cli_roundtrip(tmp_path):
    root = Path(__file__).resolve().parents[2]
    created = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "dialogue_memory.py"),
            "--root",
            str(tmp_path),
            "create",
            "--title",
            "CLI",
            "--topic",
            "runtime",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    dialogue_id = json.loads(created.stdout)["dialogue_id"]
    subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "dialogue_memory.py"),
            "--root",
            str(tmp_path),
            "note",
            "--kind",
            "principle",
            "--topic",
            "runtime",
            "--dialogue-id",
            dialogue_id,
            "--text",
            "Documentation is the contract and code follows it.",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    recall = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "dialogue_memory.py"),
            "--root",
            str(tmp_path),
            "recall",
            "--query",
            "code documentation contract",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(recall.stdout)
    assert payload["status"] == "ok"
    assert payload["matches"][0]["kind"] == "principle"


def test_goal_run_writes_dialogue_preflight(tmp_path):
    root = Path(__file__).resolve().parents[2]
    memory = DialogueMemory(tmp_path)
    session = memory.create_session(title="Goal context", topic="runtime")
    memory.note(
        kind="principle",
        topic="runtime",
        dialogue_id=session["dialogue_id"],
        text="Known goals still pass through Level 4 and Pipeline DSL validation.",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "goal_run.py"),
            "--root",
            str(tmp_path),
            "--dialogue-id",
            session["dialogue_id"],
            "--goal",
            "help me",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    report = json.loads(Path(payload["report_path"]).read_text(encoding="utf-8"))
    reloaded = memory.load_session(session["dialogue_id"])

    assert payload["dialogue_preflight"]["dialogue_id"] == session["dialogue_id"]
    assert report["dialogue_preflight"]["summary"]["active_topic"] == "runtime"
    assert reloaded["turns"][-1]["content"] == "help me"


def test_dialogue_memory_compacts_session_and_builds_topic_graph(tmp_path):
    memory = DialogueMemory(tmp_path)
    first = memory.create_session(title="Memory design", topic="dialogue-memory")
    second = memory.create_session(title="Runtime memory", topic="runtime-memory")
    for text in [
        "Dialog memory keeps conversation context.",
        "Topic graph should connect related memory threads.",
        "Compaction keeps a compact summary for Level 4.",
        "Raw turns remain durable after compaction.",
    ]:
        memory.add_turn(first["dialogue_id"], role="user", content=text)
    memory.note(kind="principle", topic="runtime-memory", text="Runtime memory and dialogue memory are separate context layers.")

    compact = memory.compact_session(first["dialogue_id"], keep_recent_turns=1)
    summary = memory.summary(dialogue_id=first["dialogue_id"])
    graph = memory.rebuild_topic_graph()

    assert compact["kind"] == "summary"
    assert compact["turn_count"] == 3
    assert summary["compact_summaries"][0]["record_id"] == compact["record_id"]
    assert memory.load_session(first["dialogue_id"])["turns"][0]["content"] == "Dialog memory keeps conversation context."
    assert any(edge["source"] == "dialogue-memory" or edge["target"] == "dialogue-memory" for edge in graph["edges"])
    assert memory.load_session(second["dialogue_id"])["active_topic"] == "runtime-memory"


def test_dialogue_memory_cli_compact_and_topic_graph(tmp_path):
    root = Path(__file__).resolve().parents[2]
    memory = DialogueMemory(tmp_path)
    session = memory.create_session(title="CLI compact", topic="memory")
    memory.add_turn(session["dialogue_id"], role="user", content="Remember decisions about context compression.")
    memory.add_turn(session["dialogue_id"], role="assistant", content="Store compact summaries as derived artifacts.")

    compact = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "dialogue_memory.py"),
            "--root",
            str(tmp_path),
            "compact",
            "--dialogue-id",
            session["dialogue_id"],
            "--keep-recent-turns",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    graph = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "dialogue_memory.py"),
            "--root",
            str(tmp_path),
            "topic-graph",
            "--rebuild",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(compact.stdout)["summary"]["kind"] == "summary"
    assert json.loads(graph.stdout)["status"] == "ok"
