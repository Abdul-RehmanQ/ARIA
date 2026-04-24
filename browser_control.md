# Plan: PinchTab Browser Control Integration

Integrate PinchTab via the HTTP API as ARIA's browser backend, expose browser actions as LLM tools, and enforce strict safety defaults for Discord usage with allowlist and private/local target blocking.

I created the plan file at [plan.md](/memories/session/plan.md) and synced it with the plan below.

## Steps

1. Define the browser tool contract first: names, args, and output conventions based on the existing tool pipeline in [brain/llm_router.py](brain/llm_router.py#L29) and the dispatch map in [brain/llm_router.py](brain/llm_router.py#L233).
2. Add PinchTab config and policy variables, including base URL, token, timeout, allowlist, and action caps, and document the defaults. Parallel with step 1.
3. Implement strict Discord safety behavior: deny non-allowlisted domains, block local/private targets, and return clear denial messages, reusing request serialization from [discord_aria.py](discord_aria.py#L261). Depends on step 1.
5. Add a dedicated browser action layer under actions for navigate and text extraction, interactive snapshot, click/type/fill/press, tab/session operations, and screenshot/pdf export.
6. Add robust HTTP handling in browser actions: auth headers, timeout/retry, structured error mapping for 401/404/409/5xx, and user-facing remediation text.Depends on step 4.
1. Add controlled file artifact handling for screenshot/pdf outputs with safe paths and filenames.Depends on step 4.
7. Register all browser tools and schemas in [brain/llm_router.py](brain/llm_router.py#L29) and map them to action functions in [brain/llm_router.py](brain/llm_router.py#L233).Depends on steps 1 and 4.
8. Keep router execution resilient in [brain/llm_router.py](brain/llm_router.py#L300): preserve dedupe and progress behavior, and keep graceful failure paths aligned with fallback behavior in [brain/llm_router.py](brain/llm_router.py#L259).Depends on step 7.
9. Extend [api_validation.py](api_validation.py#L12) with PinchTab health and auth checks plus clear pass/fail output.
Depends on steps 2 and 5.
10. Add sanitized observability logs for browser calls and latency, aligned with the runtime logging style in [discord_aria.py](discord_aria.py#L229). Depends on step 8.
11. Update setup and operations documentation in [README.md](README.md#L1), including Windows server-mode guidance and safety notes. Depends on steps 2, 7, and 9.
12. Validate in two stages: local flow first via [main.py](main.py#L11), then private Discord channel validation via [discord_aria.py](discord_aria.py#L224). Depends on steps 9, 10, and 11.

## Relevant Files

- [brain/llm_router.py](brain/llm_router.py)
- [actions/system_ops.py](actions/system_ops.py)
- [discord_aria.py](discord_aria.py)
- [api_validation.py](api_validation.py)
- [README.md](README.md)
- [main.py](main.py)

## Verification

- Syntax and lint checks on modified Python files.
- Run extended [api_validation.py](api_validation.py#L12) for PinchTab connectivity and auth.
- Execute one forced prompt per new browser tool and confirm schema-valid args and deterministic outputs.
- Validate strict allowlist and private/local block behavior.
- Validate the full browser flow: navigate, snapshot, interact, read text, and tab operations.
- Validate screenshot/pdf artifact generation and safe path behavior.
- Validate Discord authorization, throttling, and per-channel single-flight behavior.
- Simulate PinchTab outage or auth failure and confirm graceful responses.

## Recommendations Captured

- Integration mode: HTTP API only for phase 1.
- Phase-1 scope: all requested capabilities, including navigate/read, interactive actions, tab/session, and screenshot/pdf.
- Safety default: strict allowlist policy.
- Explicitly out of scope for phase 1: CAPTCHA handoff workflows, remote internet-facing PinchTab deployments, and autonomous multi-step browser planners.

If you want, I can now refine this plan into a sprint-style execution checklist with day-by-day effort estimates.