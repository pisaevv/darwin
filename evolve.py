"""The main run. So far it measures generation 0 only: how often does the panel
recommend our product today, with its page as it is?

  .venv/bin/python evolve.py --generations 0

Reads data/. Writes runs/<run_id>/: run.json, votes.jsonl and pages/g0.md.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import check
import config
import otari
import panel
import research

RUNS = Path(__file__).parent / "runs"
SETS = [("train", "train"), ("heldout", "held-out")]  # a list's name in the files, and in what is printed


def read_data():
    """The frozen inputs: our product's name, the two lists of questions, the competitor pages
    as (name, page text) pairs in file order, and our page. Stops with a plain message if something is wrong."""
    data = research.DATA
    try:
        name = json.loads((data / "product.json").read_text(encoding="utf-8"))["name"]
        questions = json.loads((data / "questions.json").read_text(encoding="utf-8"))
        page = (data / "page_gen0.md").read_text(encoding="utf-8")
    except FileNotFoundError as problem:
        sys.exit(f"Stopped: {problem.filename} is missing.")
    competitors = [(path.stem, path.read_text(encoding="utf-8")) for path in sorted((data / "competitors").glob("*.md"))]
    low, high = config.FEWEST_COMPETITOR_PAGES, config.COMPETITOR_PAGES
    if not low <= len(competitors) <= high:
        sys.exit(f"Stopped: data/competitors/ holds {len(competitors)} .md files. It needs {low} to {high}.")
    for label, text in [("data/page_gen0.md", page)] + [(f"data/competitors/{n}.md", text) for n, text in competitors]:
        if not text.strip():
            sys.exit(f"Stopped: {label} is empty.")
    for set_name, shown in SETS:
        if not questions.get(set_name):
            sys.exit(f'Stopped: data/questions.json has no questions in its list "{set_name}".')
    for question in questions["train"]:
        if question in questions["heldout"]:
            sys.exit(f"Stopped: this question is in both lists of data/questions.json: {question}")
    return name, {set_name: questions[set_name] for set_name, shown in SETS}, competitors, page


def score_page(run, scores, variant, page, gen):
    """Scores one page on both lists of questions and prints one line per list.
    The results are kept in scores[variant], as {"train": result, "heldout": result}
    (a result is what panel.score returns)."""
    scores[variant] = {}
    for set_name, shown in SETS:
        started = time.monotonic()
        result = panel.score(run, variant, page, set_name, run["questions"][set_name], gen)
        scores[variant][set_name] = result
        print(f"  {variant}, {shown}: {len(result['votes'])} votes in {time.monotonic() - started:.0f} seconds")
    return scores[variant]


def pair(result):
    return f"{result['for_us']}/{result['valid']}"


def share_text(result):
    """Votes for us / valid votes, and the per cent."""
    return f"{pair(result)} = " + ("n/a" if result["share"] is None else f"{result['share']:.0%}")


def print_tables(run, results):
    """Three small tables about one page's votes: by model, by question, by product."""
    votes = {set_name: results[set_name]["votes"] for set_name, shown in SETS}
    everything = votes["train"] + votes["heldout"]

    print(f"{'By model':<46} {'train':>6} {'held-out':>9} {'no-votes':>9} {'slowest':>8}")
    for model in run["panel"]:
        mine = [vote for vote in everything if vote["model"] == model]
        counts = [f"{for_us}/{valid}" for for_us, valid in (results[s]["per_model"][model] for s, shown in SETS)]
        print(f"  {model:<44} {counts[0]:>6} {counts[1]:>9} {sum(not vote['pick'] for vote in mine):>9} "
              f"{max(vote['seconds'] for vote in mine):>7.1f}s")

    print(f"{'By question':<68} {'for us':>6}")
    for set_name, shown in SETS:
        for q, question in enumerate(run["questions"][set_name]):
            valid = [vote for vote in votes[set_name] if vote["q"] == q and vote["pick"]]
            text = question if len(question) <= 50 else question[:49] + "…"
            for_us = f"{sum(vote['for_us'] for vote in valid)}/{len(valid)}"
            print(f"  {shown + ' ' + str(q + 1):<12} {text:<53} {for_us:>6}")

    print(f"{'By product':<46} {'train':>6} {'held-out':>9}")
    rows = []
    for name in [run["ours"]] + [name for name, text in run["competitors"]]:
        got = [sum(vote["picked"] == name for vote in votes[set_name]) for set_name, shown in SETS]
        rows.append((name + (" (ours)" if name == run["ours"] else ""), got))
    for label, got in sorted(rows, key=lambda row: -sum(row[1])):
        print(f"  {label:<44} {got[0]:>6} {got[1]:>9}")


def main(run_id, folder, name, questions, competitors, page):
    # Start: the key and its cap
    otari.start(run_id)
    cap = otari.require_cap()
    print(f"Run {run_id}  key ...{config.OTARI_API_KEY[-4:]}  cap ${cap['limit_usd']:.2f}, "
          f"used ${cap['used_usd']:.4f}, left ${cap['remaining_usd']:.4f}")

    # The start-up test decides the panel of this run
    tested = check.test_models()
    check.print_models(tested["rows"])
    test_cost = sum(row["cost_usd"] for row in tested["rows"])
    if check.panel_problem(tested["panel"]):
        sys.exit("Stopped: " + check.panel_problem(tested["panel"]))
    if not tested["rewriter"] or not tested["checker"]:
        print("Warning: no working rewriter or checker. Generation 0 needs neither, so the run goes on.")

    run = {"run_id": run_id, "votes_path": folder / "votes.jsonl", "panel": tested["panel"],
           "no_reasoning_effort": tested["no_reasoning_effort"], "ours": name, "competitors": competitors,
           "questions": questions}
    record = {
        "run_id": run_id,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "product": name,
        "panel": run["panel"],
        "no_reasoning_effort": run["no_reasoning_effort"],
        "rewriter": tested["rewriter"],
        "checker": tested["checker"],
        "competitors": [competitor for competitor, text in competitors],
        "questions": questions,
        "settings": {"max_tokens": config.PANEL_MAX_TOKENS, "temperature": 0, "reasoning_effort": "low",
                     "requests_in_flight": config.REQUESTS_IN_FLIGHT},
        "budget_at_start": {key: cap[key] for key in ("limit_usd", "used_usd", "remaining_usd")},
        "startup_test_cost_usd": round(test_cost, 6),
    }
    (folder / "run.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (folder / "pages" / "g0.md").write_text(page, encoding="utf-8")

    # Generation 0: the page as it is today
    print("Generation 0:")
    scores = {}
    results = score_page(run, scores, "g0", page, 0)
    train, heldout = results["train"], results["heldout"]
    votes = len(train["votes"]) + len(heldout["votes"])
    no_votes = train["no_votes"] + heldout["no_votes"]
    votes_cost = train["cost_usd"] + heldout["cost_usd"]

    left = otari.require_cap()  # nothing is in flight now
    print(f"gen 0 | train {share_text(train)} | held-out {share_text(heldout)} | no-votes {no_votes} "
          f"| cost ${votes_cost:.2f} | left ${left['remaining_usd']:.2f}")
    print_tables(run, results)
    if no_votes / votes >= config.NO_VOTE_LIMIT:
        print(f"WARNING: {no_votes} of {votes} votes are no-votes ({no_votes / votes:.0%}).")

    own = test_cost + votes_cost
    rose = left["used_usd"] - cap["used_usd"]
    print(f"Cost of this run: ${own:.4f} by the answers' own costs (start-up test ${test_cost:.4f}, "
          f"votes ${votes_cost:.4f}); the key's used amount rose by ${rose:.4f}")
    if abs(own - rose) > config.COST_GAP_LIMIT:
        time.sleep(5)  # Otari may still be writing its rows
        rose = otari.require_cap()["used_usd"] - cap["used_usd"]
        if abs(own - rose) > config.COST_GAP_LIMIT:
            print(f"NOTE: 5 seconds later the key's used amount had risen by ${rose:.4f}. "
                  f"That differs from the answers' own costs by ${abs(own - rose):.4f}.")
        else:
            print(f"5 seconds later the key's used amount had risen by ${rose:.4f}: the two totals agree.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=int, default=config.GENERATIONS)
    if parser.parse_args().generations != 0:
        print("Only generation 0 is built so far (Step 4 adds the rest). "
              "Run: .venv/bin/python evolve.py --generations 0")
        sys.exit(1)
    data = read_data()
    run_id = time.strftime("%Y%m%d-%H%M")
    folder = RUNS / run_id
    if folder.exists():
        sys.exit(f"A run with the id {run_id} exists already. Wait a minute and start again.")
    (folder / "pages").mkdir(parents=True)
    try:
        main(run_id, folder, *data)
    except otari.BudgetExceeded:
        votes_file = folder / "votes.jsonl"
        kept = len(votes_file.read_text(encoding="utf-8").splitlines()) if votes_file.exists() else 0
        print(f"Stopped by Otari: budget exceeded. votes.jsonl holds {kept} votes.")
        sys.exit(1)
    except otari.OtariError as problem:
        print(f"Stopped: {problem}")
        sys.exit(1)
