import json
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)


def parse_payload(payload):
    return {"name": payload.get("name", "").strip()}


def call_provider(data):
    return {"greeting": "hello " + data["name"]}


def write_audit(record):
    Path("audit.log").write_text(json.dumps(record), encoding="utf-8")


@app.route("/process", methods=["POST"])
def process_request():
    try:
        payload = request.get_json() or {}
        parsed = parse_payload(payload)
        if not parsed["name"]:
            return jsonify({"error": "missing name"}), 400
        provider_result = call_provider(parsed)
        write_audit(provider_result)
        return jsonify(provider_result)
    except Exception as exc:
        write_audit({"error": str(exc)})
        return jsonify({"error": "failed"}), 500
