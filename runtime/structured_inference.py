"""Whole-document JSON contracts and bounded pre-parse response evidence."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import re


def with_response_contract(config, properties, required=None):
    from .local_inference import LocalInferenceConfig
    return replace(config or LocalInferenceConfig.from_env(), strict_json=True,
                   response_schema={'type': 'object', 'properties': properties,
                                    'required': list(properties if required is None else required)})


def check_config(config):
    from .local_inference import LocalInferenceError
    if type(config.strict_json) is not bool:
        raise LocalInferenceError('invalid structured response mode')
    if type(config.response_format) is not bool and not isinstance(config.response_format, dict):
        raise LocalInferenceError('invalid response_format')
    if type(config.raw_response_limit_bytes) is not int or not 1 <= config.raw_response_limit_bytes <= 1048576:
        raise LocalInferenceError('invalid raw response limit')
    schema = config.response_schema
    if schema is not None:
        try:
            import jsonschema
            if not isinstance(schema, dict):
                raise ValueError('schema must be object')
            # Do not allow validation to fetch an external resource.
            def local_refs(value):
                if isinstance(value, dict):
                    for key, child in value.items():
                        if key in {'$ref', '$dynamicRef'} and isinstance(child, str) and not child.startswith('#'):
                            raise ValueError('external schema reference')
                        local_refs(child)
                elif isinstance(value, list):
                    for child in value:
                        local_refs(child)
            local_refs(schema)
            jsonschema.validators.validator_for(schema).check_schema(schema)
        except Exception as exc:
            raise LocalInferenceError('invalid response schema') from exc


def parse_document(content, schema=None):
    from .local_inference import LocalInferenceError
    if not isinstance(content, str):
        raise LocalInferenceError('structured response must be text')
    text = content.strip()
    fence = re.fullmatch(r'```(?:json)?\s*\n([\s\S]*?)\n```', text, flags=re.IGNORECASE)
    if fence:
        text = fence.group(1)
    def invalid_constant(value):
        raise ValueError('non-JSON constant')
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    try:
        result = json.loads(text, parse_constant=invalid_constant, object_pairs_hook=unique_pairs)
        if not isinstance(result, dict):
            raise ValueError('not an object')
    except (ValueError, TypeError) as exc:
        raise LocalInferenceError('structured response is not a complete JSON object') from exc
    if schema is not None:
        try:
            import jsonschema
            jsonschema.validate(result, schema)
        except Exception as exc:
            raise LocalInferenceError('structured response does not match schema') from exc
    return result


def capture_response(config, payload):
    """No credentials, prompt or hidden reasoning; callbacks persist before parsing."""
    if not (config.strict_json or config.response_schema is not None
            or isinstance(config.response_format, dict) or config.raw_response_sink):
        return None
    choices = payload.get('choices')
    choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    message = choice.get('message')
    content = message.get('content') if isinstance(message, dict) else None
    encoded = content.encode('utf-8') if isinstance(content, str) else b''
    limit = config.raw_response_limit_bytes
    record = {'requested_model': config.model, 'model': payload.get('model'),
              'content': encoded[:limit].decode('utf-8', errors='ignore') if isinstance(content, str) else None,
              'content_bytes': len(encoded), 'content_sha256': hashlib.sha256(encoded).hexdigest(),
              'truncated': len(encoded) > limit, 'finish_reason': choice.get('finish_reason')}
    if config.raw_response_sink:
        try:
            config.raw_response_sink(deepcopy(record))
        except Exception as exc:
            from .local_inference import LocalInferenceError
            raise LocalInferenceError('raw response evidence could not be saved') from exc
    return record
