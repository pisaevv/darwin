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

## Step 3

Written at the end of Step 3, 2026-11-20. `panel.py` and `evolve.py` exist, generation 0 ran twice, and every line of the check in PROMPT_3.md section 7 passed. Nothing from section 8 was needed: no setting was changed, `check.py` and `otari.py` were not touched.

### What later steps must know about the code

**`panel.py`** reads no files and does nothing when imported. It calls the gateway as `otari.chat(...)`.

- `product_order(question, q, model, seat, order_no, competitors, ours)`: the product names in the order one vote shows them.
- `vote_messages(question, products)`: the two messages of one vote. `products` are (name, page text) pairs in the order shown.
- `read_why(text)`: the reason in an answer.
- `one_vote(run, variant, page, set_name, q, question, model, order_no, gen)`: one call, returns one vote dictionary.
- `score(run, variant, page, set_name, questions, gen, order_nos=(0,))`: the scoring function. Step 4 calls it for every child.
  - `run` is a dictionary of what stays the same during a run: `run_id`, `votes_path`, `panel`, `no_reasoning_effort`, `ours` (our product's name), `competitors` (a list of (name, page text) pairs in file order). `evolve.py` also puts `questions` in it (`{"train": [...], "heldout": [...]}`); `panel.py` does not read that.
  - It returns `variant`, `set`, `votes` (in the order asked: order number, then question, then model), `for_us`, `valid`, `no_votes`, `share` (`for_us / valid`, or `None`), `cost_usd`, and `per_model` (`{model: [for_us, valid]}`).
  - Each vote is added to `votes.jsonl` as it comes back, by the main thread. In the file the votes are therefore in the order they came back, not the order asked.
  - `otari.BudgetExceeded` and `otari.SetupProblem` stop the sending (a stop flag that every job looks at before its call), the calls in flight finish and are written, then the error is raised. Any other exception in a job (a bug) sets the same flag, so a bug cannot pay for the rest of the list.

**A line of `votes.jsonl`** has these fields, in this order: `run`, `gen`, `set` (`"train"` or `"heldout"`; Step 4 adds `"final"`), `q` (from 0), `question`, `model` (with `nebius:`), `variant` (`"g0"`), `order_no`, `order` (the names as shown; the first is Product A), `ours` (our letter), `pick`, `picked`, `for_us` (all three `null` for a no-vote), `why`, `no_vote` (`null`, or `"empty answer"`, `"no readable pick"`, or the error as `check.brief` puts it), `answer`, `finish`, `tokens_in`, `tokens_out`, `tokens_thinking`, `cost_usd`, `seconds`, `time`.

**The order rule, in one sentence:** the competitors are shuffled with a seed made of the question, the model and the order number, and our product is put at place `(q + seat + 2 × order_no) mod (number of products)`, so the variant plays no part and every place comes up equally often. Step 4's final check gets its three orders by calling `score` with `order_nos=(0, 1, 2)`. With today's data our product is in each of the six places 6 times on the training list and 8 times on the held-out list.

**`evolve.py`**

- `score_page(run, scores, variant, page, gen)` scores one page on both lists, prints one line per list, and keeps the two results in `scores[variant]` as `{"train": result, "heldout": result}`. It returns that dictionary. Step 4 scores children on the training list only: it can call `panel.score` directly for those, or give `score_page` a list of set names.
- `read_data()` returns the product's name, the questions, the competitors and our page, or stops with a plain message.
- `print_tables(run, results)` prints the three tables for one page.
- `main(run_id, folder, name, questions, competitors, page)` is the run. The option, the data and the run folder are handled under `if __name__ == "__main__":`, before any call.
- `run.json` holds `run_id`, `started`, `product`, `panel`, `no_reasoning_effort`, `rewriter`, `checker`, `competitors` (names, in file order), `questions` (both lists, copied in), `settings` (`max_tokens`, `temperature`, `reasoning_effort`, `requests_in_flight`), `budget_at_start` (`limit_usd`, `used_usd`, `remaining_usd`) and `startup_test_cost_usd`. It is written once, after the start-up test.
- `config.py` has three new settings: `GENERATIONS` 12, `NO_VOTE_LIMIT` 0.10, `COST_GAP_LIMIT` 0.01.

**Which reasons the rewriter may be given later:** the `why` of votes with `set` equal to `"train"` and `for_us` equal to `false`. Never anything from `"heldout"`.

### The real numbers

Two full runs, 84 votes each, plus the small test of 6 votes. All 174 answers had a readable pick and the finish reason `stop`. The panel was the six models of `config.PANEL` both times; no reserve was needed.

| Model | Tokens in, one vote | Tokens out: usual, most | Of those thinking: usual, most | Cost of one vote, run 1 | Cost of one vote, run 2 | Seconds: usual | Seconds: slowest |
|---|---|---|---|---|---|---|---|
| `gpt-oss-120b` | 5,767 to 5,784 | 112 to 114, 167 | not reported | $0.00093 | $0.00093 | 0.6 | 0.9 |
| `gemma-3-27b-it` | 6,145 to 6,166 | 34, 40 | not reported | $0.00063 | $0.00063 | 3.3 to 6.6 | 9.2 |
| `Qwen3-235B-A22B-Instruct-2507` | 5,921 to 5,940 | 38, 45 | not reported | $0.00121 | $0.00121 | 0.9 to 1.6 | 3.5 |
| `GLM-5.3-Flash` | 5,766 to 5,785 | 42 to 47, 85 | 1 to 8, 43 | $0.00084 | $0.00074 | 1.1 | 6.9 |
| `MiniMax-M3.1-Flash` | 5,866 to 5,883 | 100 to 108, 169 | 64 to 68, 129 | $0.00088 | $0.00017 | 1.1 | 3.3 |
| `DeepSeek-V4.1-Flash-1017` | 5,883 to 5,902 | 348 to 396, **600** | 310 to 360, 547 | $0.00206 | $0.00049 | 2.9 to 3.4 | 6.0 |

"Usual" is the middle value of a run's 14 votes; where two numbers are given they are run 1 and run 2.

| | Run 1 (`20261120-1431`) | Run 2 (`20261120-1432`) |
|---|---|---|
| Seconds for the 36 training votes | 12 | 9 |
| Seconds for the 48 held-out votes | 10 | 7 |
| Cost of generation 0 (84 votes) | $0.0915 | $0.0583 |
| Cost of the start-up test (20 calls) | $0.0044 | $0.0035 |
| The key's used amount rose by | $0.0960 | $0.0619 |

**For Step 4's budget rule:** the same 84 votes cost a third less the second time. The reason is the lower price for prompt text a model has seen a moment before: `MiniMax-M3.1-Flash` and `DeepSeek-V4.1-Flash-1017` cost a fifth and a quarter of their first price in run 2, `GLM-5.3-Flash` a little less, the other three the same. So plan with the first-time price: about $0.0011 a vote, $0.092 for 84 votes. A new child page changes the prompt from our product's place on, so its votes will be somewhere between the two prices; nobody has measured that.

### The answers to the "not checked" questions

1. **Tokens and cost of a real vote.** 5,770 to 6,170 tokens in, depending on the model (PLAN.md and PROMPT_3.md expected about 5,000; the user message has 3,324 words). One vote costs $0.0006 to $0.0021 at the first-time price, $0.0011 on average.
2. **Are 600 tokens enough?** Yes, for all 174 answers. But `DeepSeek-V4.1-Flash-1017` has no room left: it thinks for 115 to 547 tokens before a 40-token answer, and one answer in run 1 used exactly 600 tokens (547 of them thinking) and still ended with `stop` and a pick. A little more thinking and that vote is a no-vote. The other five stay under 170 tokens. `PANEL_MAX_TOKENS` was left at 600, because section 8 of PROMPT_3.md allows 1200 only after a no-vote with the finish reason `length`, and there was none. This is the owner's call before Step 4.
3. **Time.** Most votes take 1 to 3 seconds. `gemma-3-27b-it` is the slowest (3 to 7 seconds, 9.2 at most). 84 votes took 22 seconds in run 1 and 16 in run 2, with 12 requests in flight. No `429`, no time-out, no retry was seen.
4. **Fields of a chat answer.** `choices[0].finish_reason`, `usage.prompt_tokens`, `usage.completion_tokens` (thinking included), `usage.total_tokens`, `usage.cost_usd`, `usage.pricing_source`, `usage.tool_cost_usd`. The thinking count is in two places: `GLM-5.3-Flash` and `MiniMax-M3.1-Flash` give `usage.reasoning_tokens`; `DeepSeek-V4.1-Flash-1017` gives only `usage.completion_tokens_details.reasoning_tokens`. `panel.py` reads the first and, if it is missing, the second. `gpt-oss-120b`, `gemma-3-27b-it` and `Qwen3-235B-A22B-Instruct-2507` report no count (`tokens_thinking` is `null`), though `gpt-oss-120b` does think: its message has a `reasoning` text and its answers use about 110 tokens for two short lines. Some models also give `usage.prompt_tokens_details.cached_tokens`.
5. **How much the votes change between two runs.** 5 of 84 picks differed (6%): 3 from `gpt-oss-120b`, 1 from `gemma-3-27b-it`, 1 from `Qwen3-235B-A22B-Instruct-2507`. All 5 were on held-out questions (numbers 1, 4, 4, 5, 5). 3 of the 5 changed between "for us" and "not for us" (two away from us, one to us). The 36 training picks were the same in both runs. Both runs showed every product in the same order.

### The two generation lines

```
gen 0 | train 11/36 = 31% | held-out 15/48 = 31% | no-votes 0 | cost $0.09 | left $2.40
gen 0 | train 11/36 = 31% | held-out 14/48 = 29% | no-votes 0 | cost $0.06 | left $2.34
```

What stands behind them (the same in both runs unless said):

- Training question 6 (coding agents) went to our product 6 times out of 6; each of the other five training questions once. Held-out question 6 (web search and tools) also 6 of 6.
- `gemma-3-27b-it` picked our product in 4 of 6 training votes; the models `GLM-5.3-Flash`, `MiniMax-M3.1-Flash` and `DeepSeek-V4.1-Flash-1017` in 1 of 6 (question 6 only).
- LiteLLM got 48 of 84 votes in run 1 and 50 in run 2, our product 26 and 25, Bifrost 9 and 7, Kong AI Gateway 1 and 1, Portkey 0 and 1, Cloudflare AI Gateway 0 and 0.
- By the place our product had (run 1, votes for us out of 14): A 5, B 5, C 6, D 4, E 4, F 2.

Otari's own count (usage grouped by the tag `set`) agreed with the files for both runs: 36 requests under `train`, 48 under `heldout`, 20 without a set (the start-up test), and a total cost equal to the answers' own costs ($0.095958 and $0.061898).

### Differences from PLAN.md and PROMPT_3.md

The points D1 to D11 of PROMPT_3.md were followed. New ones:

1. The thinking count is read from two places (answer 4 above). PROMPT_3.md names only `usage.reasoning_tokens`.
2. A vote's prompt has about 5,900 tokens, not 5,000 (answer 1).
3. A second run within minutes is cheaper because of the price for repeated prompt text (above). PROMPT_3.md expected about 10 cents for each run.
4. `nebius:moonshotai/Kimi-K3.1-Pro` passed the start-up test both times, so `run.json` names it as the rewriter (Step 1's log has `GLM-5.3`). The checker is `nebius:deepseek-ai/DeepSeek-V4-Pro-0813`. The start-up test now makes 20 calls and costs under half a cent.
5. In `panel.score` every exception in a job sets the stop flag, not only the two that PROMPT_3.md names.
6. When the two cost totals differ by more than `COST_GAP_LIMIT` and agree on the second reading, `evolve.py` prints one plain line saying so. PROMPT_3.md describes only the `NOTE:` line for the other case. Neither has been printed yet: the totals agreed at once.
7. The stops for bad data and for a panel that is too small use `sys.exit("Stopped: ...")`: the message goes to the error output and the exit code is 1.
8. `panel.py` has 141 lines (about 100 were asked for) and `evolve.py` 190.

### Tried and not tried

- Tried for real: the small test (6 votes), two full runs, both refusals of `--generations` (none and 2), the "run id exists already" stop.
- Tried only against a made-up gateway or on a copy of `data/`, at no cost: every kind of no-vote (empty answer, no pick, a failed call, a letter not in use), two `PICK:` lines, the budget running out in the middle (19 votes kept, 20 calls made, not 120), a reserve taking a seat, a panel that is too small, and each stop of `read_data`.
- Not tried at all: a real `429`, a real time-out, a real `budget_exceeded`.

### What this step cost

- On `darwin-dev`: **$0.1647** (from $0.4995 to $0.6642 used; $2.3358 is left of $3.00).
  - the small test: $0.0069
  - run 1: $0.0960
  - run 2: $0.0619
- Full runs: 2 of the 4 allowed.
- The commits are on the branch `step-3`.

## Step 5 (chart page, built while Steps 2 to 4 were still running)

Written 2026-11-20. Everything here was tried with made-up data only. No real run has a `progress.json` yet, so the page has never shown a real result. This step called nothing that costs money.

### How to see the page

- In a terminal of its own: `.venv/bin/python web/serve.py`. Then open `http://127.0.0.1:8010`. Without a run in the address the page lists the runs to click on. A run's own address is `http://127.0.0.1:8010/web/chart.html?run=<run_id>`.
- Never `python -m http.server` in this folder (D2 of PROMPT_5.md). It hands out every file here, `.env` with the keys included, to every computer on the same wifi. `web/serve.py` answers only this laptop (`127.0.0.1`) and only for `web/` and `runs/`. Tried: `/.env`, `/config.py`, `/web/../.env`, `/web/%2e%2e/%2eenv`, `/web/%2e%2e/config.py`, `/runs/%2e%2e/%2eenv` and `/BUILD_LOG.md` all give 404.
- Files: `web/chart.html` (the page, one file), `web/chart.umd.js` (Chart.js 4.6.1, unchanged, SHA-256 `338399fb…f67fbf`), `web/serve.py`, `web/fake_run.py`.

### The file the page reads (for Steps 4 and 6)

The page reads `runs/<run_id>/progress.json` every 2 seconds, and the two page files it names. Nothing else. The shape is the one in PLAN.md section 8. How the page treats each field:

| Field | What the page does with it | If missing, `null` or unusable |
|---|---|---|
| `run_id` | Shown in the top line. | The id from the address is shown. Listed at the bottom. |
| `product` | The big name; also used in three sentences. | "our product". Listed. |
| `status` | `running`, `finished`, `stopped_low_budget`, `stopped_by_budget` are put into words. Any other word is shown as it is. | "status unknown". Listed. |
| `panel` | A list of model names. Gives the order of the per-model bars and the number in "from 6 open models". | The models are taken from `per_model_heldout`. Listed. |
| `budget` | Needs `limit_usd` (above 0) and `used_usd`. `remaining_usd` is not read. | The budget part says "not in the file". Listed as `budget`, `budget.limit_usd` or `budget.used_usd`. |
| `spend_by_role` | Cuts the filled part of the bar into one piece per role, in the file's order, with a line of labels. If the roles add up to at least a cent less than `used_usd`, a grey piece "other". | The bar has one piece. Not listed. |
| `generations` | One entry per finished generation, generation 0 first. | Same as an empty list: "Waiting for the first result." Listed only if it is not a list. |
| `gen` | The generation's number on the chart and in the table. | The entry's place in the list. Listed. |
| `champion` | The id of the best page at the end of that generation. | Shown as "?". Counts as a new page for the held-out rule below. Listed. |
| `train_share`, `heldout_share` | A fraction from 0 to 1. | No point; the table says "n/a" (but see the held-out rule). Listed. A value above 1 or below 0 is treated the same way. |
| `children_made`, `children_dropped`, `no_votes`, `cost_usd` | Shown in the table. | "n/a". Listed. |
| `rewriter_model` | A "written by" column, shown only if at least one generation has one. | "–" in that row. Not listed. |
| `per_model_heldout` | For each model a pair `[votes for us, valid votes]`. The **last** generation's pairs make the per-model bars ("5 of 8"). The sum of the second numbers is the number of votes in the sentence about luck. | "not measured for this page". Listed. A pair that is not two numbers with the first no larger than the second is left out and listed. |
| `original_page`, `champion_page` | A path counted from the run's folder. Used only if it has no `..`, no `:` and no `/` at its start. The original is fetched once, the best page again when the path changes. | That column says "not in the file" (or "cannot read <path>" if the file is not there). Listed. |
| `final` | `original_share`, `champion_share`, `votes_each`. When all three are usable, they become the two big numbers. | `null` or missing: no final check yet, not listed. Present but incomplete: treated as no final check, and the bad field is listed (`final.votes_each`). |

The held-out rule (D5): a generation's held-out value is its `heldout_share`. If that is `null` and its `champion` is the same as the generation before, the value of the generation before is used (the line stays level). If the `champion` is new and has no number, there is no value and the thick line stops.

Numbers may arrive as text (`"0.09"`); only finite numbers are accepted. A missing or wrong field never stops the page. The grey line at the very bottom, "Not found in progress.json: …", names every field the page wanted and did not get. **After Step 4's first real run, read that line.** If it is not there, the file fits.

What the page needs from the program that writes the file (`evolve.py`). `web/fake_run.py` behaves this way:

1. The whole file is written anew each time: under another name in the same folder, then renamed onto `progress.json` (`os.replace`). The page then never meets half a file.
2. It is written for the first time as soon as the run folder exists: `status` `running`, an empty `generations` list, the budget of that moment, both page paths `pages/g0.md`. Then after every generation, and a last time with the final status. Without the first write the page can only say "No progress.json … yet" in the first minutes.
3. Shares are fractions from 0 to 1, or `null` if there was no valid vote. Not per cent.
4. Every entry of `generations` describes the best page at the end of that generation. If the best page did not change, its stored numbers are written again (or `heldout_share` is `null` and `champion` is the same id; the page then keeps the line level).
5. A page file exists before a `progress.json` that names it is written.
6. Numbers are JSON numbers.
7. The last write carries the final status. A run stopped by hand keeps saying `running`; the page shows when the file last changed ("last update 14:32:07 (35 s ago)"), which tells the truth.

### For Step 6

The page already shows `spend_by_role` (the pieces of the budget bar) and `rewriter_model` (the "written by" column) when the file has them, and hides both when it does not. Step 6 writes the two fields into `progress.json` and does not need to edit the page. `rewriter_model` is shown as written; a `nebius:` in front is not removed there.

### Made-up data

- Everything was tried with made-up runs written by `web/fake_run.py` into `runs/fake-…`. git ignores `runs/`, so they are not committed. Their product name is "Made-up test data", and the page shows a yellow band "MADE-UP TEST DATA. Not a real run." on every run whose id starts with `fake-`.
- Make them again: `.venv/bin/python web/fake_run.py` (nine fixed runs; two starts give the same files, byte for byte). A run that moves: `.venv/bin/python web/fake_run.py --live`, then open `?run=fake-live`; it takes about 45 seconds and writes half a file once on purpose.
- Remove them: `rm -r runs/fake-*`. Do this before the demo, so that no made-up run is in the list.
- The two real run folders of today (`20261120-1431`, `20261120-1432`) were made by Step 3 and have no `progress.json`. The page says so for them ("No progress.json in runs/20261120-1432/ yet. Waiting for it. …") and shows nothing else. Line 10 of the check had no real file to look at.

### What was checked

All of PROMPT_5.md section 7, with headless Chrome: the server's answers; the nine made-up runs; twelve addresses looked at once each (text and picture); one moving run watched for 54 seconds without a reload (waiting, then rows growing from 0 to 6, the "Cannot read progress.json right now. Showing the last good state." line while half a file was on disk, the right-hand text changing with the best page, then "finished"); no `innerHTML` and no outside address in the page; no JavaScript error in any look; the page asked only `127.0.0.1` for files. The wifi was not switched off (D3).

### Differences from PLAN.md and PROMPT_5.md

D1 to D11 of PROMPT_5.md section 4 are built as written there. On top of those:

1. **A header on every view** with the name Darwin and one sentence on what the tool does ("Rewrites a product page generation after generation, with its facts kept fixed, and measures how often a panel of open AI models recommends the product."). The owner asked for it. It claims no result.
2. **The sentence about luck takes its number of votes from the generation the right-hand big number comes from** (the last generation that has a held-out value), not always from the last generation. The two agree unless the newest page was never measured. In that case (`fake-refused`) the page now says "about 48 votes each … about 20 points" in place of "few votes", which describes the two numbers on screen.
3. **With one generation there is one big number**, so the sentence is "The number above rests on about 48 votes. A difference under about 20 points can be luck." Before the first generation the sentence is left out, because there is no number above it.
4. The "(35 s ago)" keeps counting while the file cannot be read. Otherwise it would freeze at a young age exactly when the file is stale.
5. The chart has a title on the up axis ("share of votes"), and the points do not sit on the frame's edge. The thin line is drawn on top of the thick one, so that its small points stay visible where the two meet (generation 0).
6. A `final` with a missing part counts as no final check and is listed at the bottom (PROMPT_5.md did not say).
7. PROMPT_5.md section 3 says there is no `evolve.py` and no `runs/` folder. Both existed when this step ran (Step 3 had finished). It changed nothing.
8. Sizes: `chart.html` 379 lines, `serve.py` 37 (as given, unchanged), `fake_run.py` 182 (about 150 was asked; the timeline and the two texts take the room).

### Not tried

- A real `progress.json`: none exists yet.
- A real projector. The pictures were taken at 1,300 pixels wide. On a 1,920 by 1,080 screen the header, the two big numbers and most of the chart fit in the first view; the rest needs scrolling.
- Browsers other than Chrome 157.
