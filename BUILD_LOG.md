# BUILD LOG

## What later steps must know

Written at the end of Step 1, 2026-11-20. Everything here was seen on the real gateway unless it says otherwise.

### Running things

- Run every script as `.venv/bin/python <file>`. Plain `python` on this Mac belongs to another project.
- The gateway address is a public `https://…/api/v1` address, not the `localhost` tunnel of PLAN.md section 6. It is read from `.env` and written in no file.
- The key in use is `darwin-dev`, capped at $3.00. The owner's earlier key (`app-agent`, no cap) is kept in `.env` as `OTARI_KEY_PREVIOUS`.
- The commits are on the branch `step-1`. NOTES.md, PLAN.md and PROMPT_1.md are not committed.

### What the code offers

- `otari.start(run_id)` first. Then `otari.chat`, `search`, `fetch`, `model_info`, `key_budget`, `require_cap`, `search_catalog`, `usage_summary`, `health`.
- `otari.chat(model, messages, max_tokens, timeout=…, tags={"role": "panel"}, temperature=0, …)` returns `text`, `cost_usd`, `headers`, `seconds`, `raw`. `headers` can be read in any letter case (`headers["Otari-Model"]`).
- Three error types: `otari.CallFailed` (this call failed: no-vote or dropped child), `otari.BudgetExceeded` (stop the run), `otari.SetupProblem` (stop with the message). Each has `.status`, `.code`, `.detail`.
- The first chat, search or fetch call of a program reads the key's budget once and raises `SetupProblem` if the key has no cap. No script can skip this.
- `check.test_models()` is the start-up test (returns `panel`, `no_reasoning_effort`, `rewriter`, `checker`, `rows`). `check.read_pick(text, letters)` reads a pick. `check.panel_problem(panel)` says why a panel is too small, or `None`.

### Where the gateway differs from PLAN.md

Listed in PROMPT_1.md and confirmed:

1. `GET /models` does not list the pinned names. To ask "is this model there, with a price?" use `otari.model_info("nebius:<name>")`: a dictionary with `pricing` means yes, `None` means no.
2. `nebius:moonshotai/Kimi-K3.1-Pro` (the plan's rewriter) and `nebius:thinkingmachines/Inkling-2-Small` (a reserve) have no price and are not usable. The lookup answers `404` for both.
3. `POST /budgets` answers with `budget_id`, not `id`. Creating a provider or a search tool answers `201`.
4. A fetch answer has `text`, `final_url`, `truncated`, `content_type`, `url`, `published` and `title`. PROMPT_1.md expected no `title`; it is there, but it came back empty for `https://example.com`, so do not rely on it.
5. Search and fetch report their cost only in the answer header `Otari-Cost-USD`. Only chat has `usage.cost_usd` (a string such as `"0.000029"`).
6. An error body is `{"detail": …, "code": …}`. Some refusals have no code, for example the `403` for a missing scope.
7. Nebius was already added as the provider `nebius`. `init` left it alone, so the "add Nebius" lines in `setup_gateway.py` have never run.

Found while building:

8. **`POST /pricing` refuses a body without `output_price_per_million`** (`422`, "Field required"). PLAN.md section 12 leaves it out. `setup_gateway.py` sends it as `0`.
9. **Search and fetch calls keep no tags and belong to no session.** Their usage rows have empty tags and no session. So a usage question with `tag=run:<run_id>` or grouped by `role` never includes research spending. Step 6a ("spend by role") must take the research cost from the answers' own `cost_usd`, or ask the usage summary by endpoint (`/v1/search`, `/v1/fetch`) instead of by tag.
10. **Adding `tavily` changed the gateway's default search tool.** Before, the search catalog showed only the bundled `searxng` (no price) as the default. After `tavily` was added, the catalog shows only `tavily`, marked as default. So a search by any key on this gateway that names no tool would now go to Tavily, at $0.008 a call (not tried). The owner should know; nothing was done about it.
11. `reasoning_effort: "low"` is accepted by all six panel models (see below).
12. The `Otari-Model` answer header gives the model without the `nebius:` prefix, for example `google/gemma-3-27b-it`. `Otari-Provider` is `nebius`. Step 6b should expect that form.
13. In the key's usage summary, a session shows up in `by_source_label` as an id like `s-fb1d0faf…` with no name. The name (`darwin-<run_id>`) is visible only to the master key (`GET /traces`) and in the dashboard.
14. Fetch was switched off this morning and is on now: `https://example.com` gave 171 characters at $0.
15. Answer times vary a lot. Most test votes took under 3 seconds, but single calls took 15 seconds (`GLM-5.3-Flash`, `GLM-5.3`) and 30 seconds (`DeepSeek-V4-Pro-0813`), with no retry involved. `GLM-5.3`, which timed out earlier today, answered in 9 and 15 seconds.

### The four questions PROMPT_1.md could not check

1. **Does `Otari-Conversation-Id` group calls into one session?** Yes. Tried separately: the header alone makes one session named after its value, and the body field `session_label` alone does the same. `otari.py` sends both. The session's "harness" is `darwin`, taken from `User-Agent: darwin/0.1`. This holds for chat calls only (point 9).
2. **Do search and fetch calls keep their `Otari-Tags`?** No (point 9).
3. **How does a model that does not take `reasoning_effort` refuse it?** None did. `gemma-3-27b-it` and `Qwen3-235B-A22B-Instruct-2507` do not list `reasoning` in `supported_parameters`, yet they answered normally with `reasoning_effort: "low"`. The "try once without" path in `check.py` is there but has only been tried against a fake gateway.
4. **Does the price body for `tavily` give 0.008 per call?** Yes, once `output_price_per_million: 0` is added (point 8). The catalog shows `price_per_call` 0.008, and a real search cost $0.008 in the `Otari-Cost-USD` header and in the key's budget.

### Models that run without `reasoning_effort`

None. All six panel models take it.

### Today's test result (run `check-20261120-1342`)

- Panel: all six models of PLAN.md 4.3 passed, from six makers. No reserve was needed. `Qwen3-30B-A3B-Instruct-2507`, `Nemotron-3_5-Lightning` and `reflection/beam` are listed with a price but were not tested.
- Rewriter: `nebius:zai-org/GLM-5.3` (the reserve, because Kimi has no price). Checker: `nebius:deepseek-ai/DeepSeek-V4-Pro-0813`.
- With `GLM-5.3` as the rewriter, the checker has no reserve left: its reserve is also `GLM-5.3`, and the two must be different models.
- One full `check.py` costs about $0.011 and one Tavily credit. The check's own cost total and the change in the key's budget agreed.

## Notes on Step 1

- `setup_gateway.py`, rule "do not lose a key": if `OTARI_KEY_PREVIOUS` already holds a different key, the key being replaced is saved as `OTARI_KEY_PREVIOUS_2` (then `_3`, …) instead of overwriting it. PROMPT_1.md names only `OTARI_KEY_PREVIOUS`.
- Tried only against a fake gateway, not the real one: the clean-up when `key` fails halfway, and most rows of the error table in `otari.py` (`429`, `5xx`, time-outs, `budget_exceeded`). Seen for real: the `422` on the price, and the `403` when the uncapped key asks for its budget.
- `init` needed three runs the first time: the first created the `tavily` tool and stopped at the price (point 8). After the fix it created the price, and the next run said "already there" four times.
- Created on the gateway: the search tool `tavily`, its price, the key `darwin-dev`, the budget `darwin-dev` ($3, no reset), and the link between them. Nothing else was changed or deleted.
- Spent on `darwin-dev`: $0.0224. That is two full checks, plus 6 very small chat calls (run tags `probe-1` to `probe-3`) to answer question 1 and to see real answers, plus one $0 fetch to see its fields. Two Tavily credits used.
