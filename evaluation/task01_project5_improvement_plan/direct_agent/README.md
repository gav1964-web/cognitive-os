# Direct Agent Route

## Executor

- Tool: Codex direct repository/project inspection
- Model: GPT-5 Codex session
- Date: 2026-07-10

## Run Summary

Direct inspection treats `F:\ubuntu\test\5` as an LLM Gateway / FastAPI service that provides a unified API over several LLM providers.

Main supported scenarios found:

- `POST /chat` and `POST /v1/chat/completions` request handling.
- provider/model routing through aliases and routing profiles.
- provider adapters for OpenAI-compatible, Gemini and GigaChat backends.
- local/provider cache lookup and persistence.
- health, model list, stats and arena-style multi-provider calls.
- optional local LLM process startup/check/pruning during application lifespan.

Important entrypoints and flow:

- `app/api/server.py` creates the FastAPI app and registers endpoints.
- `lifespan()` loads `config/providers.yaml`, starts/prunes local LLMs, builds provider instances and semaphores.
- `/chat` delegates to `app/api/handlers_chat.py:handle_chat_endpoint`.
- direct provider calls and routed OpenAI-compatible calls converge into `_handle_chat_request()`.
- `_handle_chat_request()` normalizes provider/model names, checks cooldowns, performs cache read/write, calls the provider adapter, maps OpenAI/provider errors and returns `ProviderResult` plus route metadata.

Core logic vs interfaces:

- Core: provider adapters, provider factory, config parsing, cache key generation, routing/cooldown logic, error normalization.
- Interfaces/adapters: FastAPI endpoints, OpenAI compatibility schemas, GigaChat/OpenAI/Gemini adapter classes.
- State and side effects: JSON cache files, provider cooldowns, local process table, provider semaphores, environment-secret resolution, subprocess startup for local LLMs.
- Tests: HTTP/API contract tests, provider usage tests, retry policy tests, config tests and live-provider tests.
- Context/noise: scratch scripts, manual tools, generated cache files and large runtime logs.

Improvement proposals:

1. Split `app/api/server.py` further. It still mixes app assembly, lifecycle, local process management, endpoint registration, provider call orchestration, cache behavior and error mapping.
2. Move local LLM process startup/check/stop into a dedicated process-boundary service with explicit timeout, quarantine and resume semantics.
3. Treat `_handle_chat_request()` as a hidden orchestrator and decompose it into smaller capabilities: provider lookup, model normalization, cooldown check, cache read, provider call, error mapping, cache write and metadata assembly.
4. Keep `app/core/cache.py:LLMCache.build_key` as a good first reusable capability candidate because it is deterministic, narrow and has a clear input/output contract.
5. Add explicit idempotency/replay policy for cache writes and provider calls. A retry after partial failure can currently mix external side effects and local cache state.
6. Strengthen dependency/config safety: `requirements.txt` is only partially pinned, provider credentials are resolved from environment/config, and optional live-provider tests need clear quarantine policy.
7. Separate generated/runtime artifacts from source evidence. Cache files and scratch/manual scripts should not influence first extraction or core-logic scoring.
8. Add contract tests around OpenAI-compatible response/error shapes and route headers so provider-specific drift is caught outside live-provider tests.

## Artifacts

- Output: this README section.
- Tests: not executed for direct route.
- Logs: shell inspection of project files, docs and key source snippets.

## Notes

This route used the original prompt without Cognitive OS artifact APIs. It relied on direct source/document inspection and did not modify the source project.
