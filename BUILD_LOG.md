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

## Step 2

Written at the end of Step 2, 2026-11-20. `research.py` ran and the data check says PASS. The data is not frozen yet: the owner's checkpoint comes first.

### What later steps must know about the data

- A competitor's name is its file name without `.md`. Step 3 reads `data/competitors/*.md`, sorted by file name. The tool never reads `data/spare/` or `data/sources.json`.
- A page file holds the page text and nothing else: no heading, address or name is added. Every file is UTF-8 and ends with one line break.
- A word is what `text.split()` gives. `research.words(text)` counts this way.
- `data/facts.md` has one fact per line, as `N. text`. The numbering can have gaps after the owner's corrections.
- Step 4's check "every number in the page also appears in `facts.md`" must take the list numbers off first (`re.sub(r"^\d+\.\s*", "", line)`), or every small number passes. With today's files, `page_gen0.md` holds three numbers that no fact holds: `5` (from "in 5 minutes") and `4` and `6` (from the model name `claude-sonnet-4-6`). A rewrite that keeps them would be dropped by that check, unless the owner adds a fact.
- `research.py` can be imported without anything happening. Useful to later steps: `words(text)`, `numbers(text)` (every run of digits, with `.` or `,` allowed between digits), `key_word(name)` (a name's first run of letters and digits, in small letters), `clean(text)` and `cut(text, limit)`.
- `.venv/bin/python research.py` with the data in place changes nothing and costs nothing. It prints the data check: a table and `RESULT: PASS` or `FAIL`. Its exit code is 0 for PASS and 1 for FAIL.

### What later steps must know about the strong models

This matters most for Step 4.

- Without `reasoning_effort`, the strong models think for about 10,000 tokens before they answer, and thinking counts against `max_tokens`. With `max_tokens` 4000, `GLM-5.3` and `DeepSeek-V4-Pro-0813` both used all 4,000 tokens and gave no answer. PLAN.md gives the rewriter 3000 and the checker 1500. Called the way this step calls them, they would give nothing.
- One answer took 2 to 3.5 minutes and cost 5 to 15 cents (table below). PLAN.md section 10 counts on 4 rewrites and 4 checks per generation, at about $0.33 and 2 minutes for the whole generation.
- Not tried on the strong models: `reasoning_effort: "low"` with a real task. Step 1's test called `GLM-5.3` and `DeepSeek-V4-Pro-0813` without it, on a tiny prompt with `max_tokens` 600, and they answered in 9 to 30 seconds. So how long they think depends on the task.
- `nebius:moonshotai/Kimi-K3.1-Pro` (the plan's rewriter) can be used now. At 14:07 the gateway had no price for it. At 14:14 it had one: $2 per million tokens in, $10 out, with the source "configured", so it was set by hand on the gateway and not by this step. It is the dearest of the three.
- `usage.reasoning_tokens` says how many tokens were thinking. `GLM-5.3` reports it. `Kimi-K3.1-Pro` does not.

| Call | Model | `max_tokens` | Seconds | Tokens in | Tokens out | Cost | Result |
|---|---|---|---|---|---|---|---|
| Run 1, candidates | `GLM-5.3` | 4000 | 38 | 14,656 | 4,000 | $0.0381 | no answer, cut off |
| Run 1, candidates | `DeepSeek-V4-Pro-0813` | 4000 | 31 | 14,804 | 4,000 | $0.0354 | no answer, cut off |
| Test call, facts | `GLM-5.3` | 12000 | 161 | 2,575 | 11,147 (10,198 thinking) | $0.0527 | 40 facts, none with a strange number |
| Run 2, candidates | `Kimi-K3.1-Pro` | 16000 | 129 | 14,277 | 11,922 | $0.1477 | 10 products |
| Run 2, facts | `Kimi-K3.1-Pro` | 16000 | 197 | 2,622 | 11,011 | $0.1152 | 40 facts, none dropped |

The data on disk comes from run 2, so `Kimi-K3.1-Pro` did the research: both calls.

### What the probe showed about search

Three searches for `Helicone AI gateway`, 5 results, 1,500 tokens per result.

- **Does `snippet` hold the page's text?** Yes. It is the start of the page text Tavily returns (`raw_content`), as Markdown with blank lines, links and pictures. It is not the short excerpt.
- **How many words for 1,500 tokens?** The text is cut at 6,000 characters, 4 for each token. That gave 487 and 790 words. Shorter pages came whole: 296, 569 and 621 words. For the main searches (400 tokens), 31 results gave 6,100 words in all.
- **Are all results from the site asked for?** This is where the gateway differs from PROMPT_2.md. `otari.search(…, domains=["helicone.ai"])` gave **0 results**. Tavily's own answer (asked for with `include_raw`) held 5 results, all from other sites (`docs.litellm.ai`, `github.com`, `tavily.com`, `promptfoo.dev`, `ai-sdk.dev`). So the gateway does not pass `search_domain_filter` on to Tavily. Tavily searches everywhere and the gateway then removes the results from other sites.
- Tavily's own filter does work through the gateway: the body field `provider_options: {"include_domains": ["helicone.ai"]}` gave 5 results, all from `www.helicone.ai` and `docs.helicone.ai`. The front page was not among them: three blog posts and two documentation pages. `otari.search` cannot send this field, and `otari.py` was not changed.
- What this means: the search fallback in `research.py` is built as PROMPT_2.md describes, with `domains`. On this gateway it finds a page only if the product's own site is among Tavily's first 5 results for `"<name> <category>"`. In run 2 it was never needed: all seven pages were read by fetch. It has only run against a made-up gateway.

### Differences from PLAN.md and PROMPT_2.md

The points D1 to D13 of PROMPT_2.md were followed. New ones:

1. **`max_tokens` for the two model calls is 16000, not 4000** (`config.RESEARCH_MAX_TOKENS`). With 4000 no strong model answered (above). The timeout stays `config.REWRITER_TIMEOUT`.
2. **One run cost $0.29, not 10 to 15 cents.** The two model calls are $0.26 of it.
3. **`domains` does not reach Tavily** (above).
4. **`research.py` has 511 lines, not about 250.** 90 are empty and 45 are the two prompts. It has no cache, no resume, no threads and no option but `--force`.
5. `data/sources.json` names two models, `model_candidates` and `model_facts`, because the two calls can end up with different models. In run 2 both are the same.
6. `moved` is also true for a page read by search, when its address is not the one asked for.
7. The "seen before" test also looks at the site a kept page was really read from, not only at the address the model gave.
8. A new setting, `config.FEWEST_COMPETITOR_PAGES = 4`: with fewer, nothing is written.
9. A line of the model's list that starts with `|` (a table row) is read too.
10. The key's used amount is asked a second time just before the files are written, not after. So "Stopped: …" always means that nothing was written.
11. Fetch gives `content_type` `text/markdown` for some sites (here `cloudflare.com`, `openrouter.ai`, `aws.amazon.com`): a version of the page written for AI agents.

No prompt was changed. Both are worded as in PROMPT_2.md section 6.6.

### Tried and not tried

- Tried for real: run 1 (stopped at the first model call, wrote nothing), run 2 (PASS), the refusing run (changes nothing, costs nothing).
- Tried only against a made-up gateway, with made-up texts, at no cost: `--force` replacing old output, `--force` leaving old output alone when the run fails, the search fallback, a failed model call handing over to the next model, every reason for skipping a candidate, dropped facts, a cut-off facts answer, "too few competitors", and the cap running out in the middle.

### What this step cost

- On `darwin-dev`: **$0.4770** (from $0.0224 to $0.4995 used; $2.5005 is left of $3.00).
  - 3 probe searches: $0.0240
  - run 1: $0.1055 (4 searches, 2 model calls without an answer)
  - the test call: $0.0527
  - run 2: $0.2949 (4 searches, 2 model calls). The answers' own costs and the rise of the key's used amount agreed to the cent.
- Tavily: 11 searches, so 11 credits.
- Full runs: 2 of the 3 allowed. The step's limit was $0.50, so there was no room for a third.
