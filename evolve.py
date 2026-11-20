"""The main run. It measures how often the panel recommends our product with its page as it is
today (generation 0). Then a strong model rewrites the page, generation after generation, two checks
drop rewrites that break the facts, the panel scores the rest, and the best page is kept.

  .venv/bin/python evolve.py                     12 generations, or fewer if the money runs low
  .venv/bin/python evolve.py --generations 2
  .venv/bin/python evolve.py --until-refused     goes on until Otari refuses (shows the cap working)

Reads data/. Writes runs/<run_id>/: run.json, progress.json, votes.jsonl, children.jsonl and pages/*.md.
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import check
import config
import otari
import panel
import research
import rewrite

RUNS = Path(__file__).parent / "runs"
SETS = [("train", "train"), ("heldout", "held-out")]  # a list's name in the files, and in what is printed


def read_data():
    """The frozen inputs: our product's name and category, the two lists of questions, the competitor
    pages as (name, page text) pairs in file order, our page and the fact sheet.
    Stops with a plain message if something is wrong."""
    data = research.DATA
    try:
        product = json.loads((data / "product.json").read_text(encoding="utf-8"))
        name, category = product["name"], product["category"]
        facts = (data / "facts.md").read_text(encoding="utf-8")
        questions = json.loads((data / "questions.json").read_text(encoding="utf-8"))
        page = (data / "page_gen0.md").read_text(encoding="utf-8")
    except FileNotFoundError as problem:
        sys.exit(f"Stopped: {problem.filename} is missing.")
    competitors = [(path.stem, path.read_text(encoding="utf-8")) for path in sorted((data / "competitors").glob("*.md"))]
    low, high = config.FEWEST_COMPETITOR_PAGES, config.COMPETITOR_PAGES
    if not low <= len(competitors) <= high:
        sys.exit(f"Stopped: data/competitors/ holds {len(competitors)} .md files. It needs {low} to {high}.")
    for label, text in [("data/page_gen0.md", page), ("data/facts.md", facts)] + [(f"data/competitors/{n}.md", text) for n, text in competitors]:
        if not text.strip():
            sys.exit(f"Stopped: {label} is empty.")
    for set_name, shown in SETS:
        if not questions.get(set_name):
            sys.exit(f'Stopped: data/questions.json has no questions in its list "{set_name}".')
    for question in questions["train"]:
        if question in questions["heldout"]:
            sys.exit(f"Stopped: this question is in both lists of data/questions.json: {question}")
    return name, category, {set_name: questions[set_name] for set_name, shown in SETS}, competitors, page, facts


def score_page(run, scores, variant, page, gen, sets=("train", "heldout")):
    """Scores one page on the lists of questions named in sets and prints one line per list.
    The results are kept in scores[variant], as {"train": result, "heldout": result}
    (a result is what panel.score returns). A result is kept only when its whole list was asked."""
    for set_name in sets:
        started = time.monotonic()
        result = panel.score(run, variant, page, set_name, run["questions"][set_name], gen)
        scores.setdefault(variant, {})[set_name] = result
        print(f"  {variant}, {dict(SETS)[set_name]}: {len(result['votes'])} votes "
              f"in {time.monotonic() - started:.0f} seconds")
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


def write_progress(folder, progress):
    """The one place that writes the file the chart page reads. The page never meets half a file:
    the text goes into a second file first, which then takes the place of the old one."""
    temporary = folder / "progress.json.tmp"
    temporary.write_text(json.dumps(progress, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, folder / "progress.json")


def read_lines(path):
    """The lines of votes.jsonl or children.jsonl as dictionaries. An empty list if the file is not there."""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def budget_of(cap):
    return {key: cap[key] for key in ("limit_usd", "used_usd", "remaining_usd")}


def per_cent(share):
    return "n/a" if share is None else f"{share:.0%}"


def ranking(scores):
    """The variants that have a full training score, best share first. Among equal shares the
    older one comes first. The first of the ranking is the best page."""
    return sorted(scores, key=lambda variant: -(scores[variant]["train"]["share"] or 0))


def add_entry(run, folder, progress, gen, made, children):
    """Adds one generation to the progress: the best page at its end, with that page's stored numbers.
    The cost and the no-votes are counted from the files."""
    best = ranking(run["scores"])[0]
    heldout = run["scores"][best].get("heldout")
    votes = [vote for vote in read_lines(folder / "votes.jsonl") if vote["gen"] == gen and vote["set"] != "final"]
    writers = [child["rewriter_model"] for child in children if child["rewriter_model"]]
    entry = {
        "gen": gen,
        "champion": best,
        "train_share": run["scores"][best]["train"]["share"],
        "heldout_share": heldout["share"] if heldout else None,
        "children_made": made,
        "children_dropped": made - sum(child["train"] is not None for child in children),
        "no_votes": sum(not vote["pick"] for vote in votes),
        "cost_usd": round(sum(vote["cost_usd"] for vote in votes) + sum(child["cost_usd"] for child in children), 6),
        "rewriter_model": writers[0] if writers else None,
        "per_model_heldout": heldout["per_model"] if heldout else None,
    }
    progress["generations"].append(entry)
    progress["champion_page"] = f"pages/{best}.md"
    return entry


def close_generation(run, folder, progress, entry, new, started):
    """Reads the budget (nothing is in flight), writes progress.json and prints the generation's line."""
    left = otari.require_cap()
    progress["budget"] = budget_of(left)
    write_progress(folder, progress)
    best = run["scores"][entry["champion"]]
    heldout = share_text(best["heldout"]) if "heldout" in best else "not measured"
    print(f"gen {entry['gen']} | best {entry['champion']}{' (new)' if new else ''} | train {share_text(best['train'])} "
          f"| held-out {heldout} | children {entry['children_made']}, dropped {entry['children_dropped']} "
          f"| no-votes {entry['no_votes']} | cost ${entry['cost_usd']:.2f} | left ${left['remaining_usd']:.2f} "
          f"| {time.monotonic() - started:.0f} s")


def enough_left(run, folder, progress, gen):
    """The budget rule: is there money for one more generation and the final check?"""
    left = otari.require_cap()["remaining_usd"]
    past = [entry["cost_usd"] for entry in progress["generations"] if entry["gen"] > 0]
    one_generation = max(past) * config.ESTIMATE_MARGIN if past else config.FIRST_GENERATION_ESTIMATE
    votes = read_lines(folder / "votes.jsonl")
    final_votes = 2 * config.FINAL_ORDERS * len(run["questions"]["heldout"]) * len(run["panel"])
    final = final_votes * sum(vote["cost_usd"] for vote in votes) / len(votes) * config.ESTIMATE_MARGIN
    if left < one_generation + final:
        print(f"Stopped before generation {gen}: ${left:.2f} is left; one more generation and the final check "
              f"may cost ${one_generation + final:.2f}.")
        return False
    return True


def generation(run, folder, progress, gen):
    """One generation: four rewrites, the two checks, the training votes of the children that passed,
    and the held-out votes of the best page if it is new."""
    started = time.monotonic()
    order = ranking(run["scores"])
    parents = [order[0] if k <= config.CHILDREN // 2 else order[min(1, len(order) - 1)]
               for k in range(1, config.CHILDREN + 1)]
    print(f"Generation {gen}:")
    with ThreadPoolExecutor(config.CHILDREN) as pool:
        futures = [pool.submit(rewrite.make_child, run, gen, k, parents[k - 1], (gen + k - 2) % 4 + 1)
                   for k in range(1, config.CHILDREN + 1)]
    children, refused = [], None
    for future in futures:
        try:
            children.append(future.result())
        except (otari.BudgetExceeded, otari.SetupProblem) as problem:
            refused = refused or problem

    try:
        for child in children:
            if child["page"]:  # saved even if the child is dropped
                (folder / "pages" / f"{child['variant']}.md").write_text(child["page"] + "\n", encoding="utf-8")
                run["pages"][child["variant"]] = child["page"]
            times = "".join(f", {label} {child[key]:.0f} s" for label, key in
                            [("rewrite", "rewrite_seconds"), ("check", "check_seconds")] if child[key] is not None)
            print(f"  {child['variant']} from {child['parent']}, instruction {child['instruction']}: "
                  f"{child['words']} words{times}: " + (f"dropped ({child['dropped']})" if child["dropped"] else "passed"))
        if refused:
            raise refused
        for child in children:
            if not child["dropped"]:
                result = score_page(run, run["scores"], child["variant"], child["page"], gen, ["train"])["train"]
                child["train"] = [result["for_us"], result["valid"]]
    finally:  # also when Otari cuts the generation: the children that came back are written down
        with open(folder / "children.jsonl", "a", encoding="utf-8") as file:
            for child in children:
                line = {"run": run["run_id"], **{key: value for key, value in child.items() if key != "page"},
                        "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
                file.write(json.dumps(line, ensure_ascii=False) + "\n")

    best = ranking(run["scores"])[0]
    new = best != order[0]
    if new:
        try:
            score_page(run, run["scores"], best, run["pages"][best], gen, ["heldout"])
        except otari.BudgetExceeded:
            # The best page is known and only its held-out result is missing: the generation is written.
            add_entry(run, folder, progress, gen, config.CHILDREN, children)
            raise
    entry = add_entry(run, folder, progress, gen, config.CHILDREN, children)
    close_generation(run, folder, progress, entry, new, started)


def final_check(run, folder, progress):
    """The original page against the best page on the held-out questions, in three product orders each."""
    best = ranking(run["scores"])[0]
    if best == "g0":
        print("No rewritten page beat the original page on the training questions. No final check.")
        return
    gen = progress["generations"][-1]["gen"]
    orders = tuple(range(config.FINAL_ORDERS))
    print("Final check:")
    original, champion = [panel.score(run, variant, run["pages"][variant], "final", run["questions"]["heldout"],
                                      gen, order_nos=orders) for variant in ("g0", best)]
    votes_each = min(original["valid"], champion["valid"])
    progress["final"] = {"original_share": original["share"], "champion_share": champion["share"],
                         "votes_each": votes_each}
    print(f"final check | original g0 {share_text(original)} | best {best} {share_text(champion)} "
          f"| no-votes {original['no_votes'] + champion['no_votes']} "
          f"| cost ${original['cost_usd'] + champion['cost_usd']:.2f}")
    print(f"held-out: {per_cent(original['share'])} → {per_cent(champion['share'])} ({votes_each} votes each)")


def evolution(run, folder, progress, cap, generations, until_refused):
    """Everything between the first progress.json and the last: the start-up test, generation 0,
    the generations and the final check. Returns the status."""
    # The start-up test decides the panel of this run
    tested = check.test_models()
    check.print_models(tested["rows"])
    run["test_cost"] = sum(row["cost_usd"] for row in tested["rows"])
    problem = check.panel_problem(tested["panel"])
    if not problem and generations > 0:
        if not tested["rewriter"]:
            problem = "no rewriter works"
        elif not tested["checker"]:
            problem = "no checker works"
        elif tested["rewriter"] == tested["checker"]:
            problem = "the rewriter and the checker are the same model"
    if problem:
        raise otari.SetupProblem(problem)

    run.update(panel=tested["panel"], no_reasoning_effort=tested["no_reasoning_effort"],
               rewriter=tested["rewriter"], checker=tested["checker"],
               rewriter_effort=config.REWRITER_EFFORT, rewriter_max_tokens=config.REWRITER_MAX_TOKENS,
               checker_effort=config.CHECKER_EFFORT, checker_max_tokens=config.CHECKER_MAX_TOKENS)
    record = {
        "run_id": run["run_id"],
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "product": run["ours"],
        "panel": run["panel"],
        "no_reasoning_effort": run["no_reasoning_effort"],
        "rewriter": run["rewriter"],
        "checker": run["checker"],
        "competitors": [competitor for competitor, text in run["competitors"]],
        "questions": run["questions"],
        "settings": {"max_tokens": config.PANEL_MAX_TOKENS, "temperature": 0, "reasoning_effort": "low",
                     "requests_in_flight": config.REQUESTS_IN_FLIGHT, "generations": generations,
                     "until_refused": until_refused, "rewriter_effort": config.REWRITER_EFFORT,
                     "rewriter_max_tokens": config.REWRITER_MAX_TOKENS, "checker_effort": config.CHECKER_EFFORT,
                     "checker_max_tokens": config.CHECKER_MAX_TOKENS, "children": config.CHILDREN},
        "budget_at_start": budget_of(cap),
        "startup_test_cost_usd": round(run["test_cost"], 6),
    }
    (folder / "run.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    progress["panel"] = run["panel"]
    write_progress(folder, progress)

    # Generation 0: the page as it is today
    print("Generation 0:")
    started = time.monotonic()
    results = score_page(run, run["scores"], "g0", run["pages"]["g0"], 0)
    close_generation(run, folder, progress, add_entry(run, folder, progress, 0, 0, []), False, started)
    print_tables(run, results)

    status = "finished"
    for gen in range(1, generations + 1):
        if not until_refused and not enough_left(run, folder, progress, gen):
            status = "stopped_low_budget"
            break
        generation(run, folder, progress, gen)
    if generations > 0:
        final_check(run, folder, progress)
    return status


def main(run_id, folder, name, category, questions, competitors, page, facts, generations, until_refused):
    """The whole run, into the folder (which exists, with pages/ in it). Returns the status."""
    (folder / "pages" / "g0.md").write_text(page, encoding="utf-8")

    # Start: the key and its cap
    otari.start(run_id)
    cap = otari.require_cap()
    print(f"Run {run_id}  key ...{config.OTARI_API_KEY[-4:]}  cap ${cap['limit_usd']:.2f}, "
          f"used ${cap['used_usd']:.4f}, left ${cap['remaining_usd']:.4f}")
    progress = {"run_id": run_id, "product": name, "status": "running", "panel": config.PANEL,
                "budget": budget_of(cap), "generations": [], "original_page": "pages/g0.md",
                "champion_page": "pages/g0.md", "final": None}
    write_progress(folder, progress)
    run = {"run_id": run_id, "votes_path": folder / "votes.jsonl", "panel": config.PANEL, "no_reasoning_effort": [],
           "ours": name, "category": category, "facts": facts, "competitors": competitors, "questions": questions,
           "pages": {"g0": page}, "scores": {}, "test_cost": 0.0}

    # The one place that handles a refusal or a setup problem, so that the last write always happens
    try:
        status = evolution(run, folder, progress, cap, generations, until_refused)
    except otari.BudgetExceeded as problem:
        status = "stopped_by_budget"
        print(f"Stopped by Otari: budget exceeded. votes.jsonl holds {len(read_lines(folder / 'votes.jsonl'))} votes.")
        print(f"  Otari's words: {problem}")
    except otari.OtariError as problem:
        status = "stopped_error"
        print(f"Stopped: {problem}")

    # The end
    try:
        progress["budget"] = budget_of(otari.require_cap())
    except otari.OtariError:
        pass  # the last numbers stay
    progress["status"] = status
    write_progress(folder, progress)
    print(f"Status: {status}")

    votes = read_lines(folder / "votes.jsonl")
    children = read_lines(folder / "children.jsonl")
    no_votes = sum(not vote["pick"] for vote in votes)
    if votes and no_votes / len(votes) >= config.NO_VOTE_LIMIT:
        print(f"WARNING: {no_votes} of {len(votes)} votes are no-votes ({no_votes / len(votes):.0%}).")
    amounts = [run["test_cost"], sum(vote["cost_usd"] for vote in votes),
               sum(child["rewrite_cost_usd"] for child in children), sum(child["check_cost_usd"] for child in children)]
    own = sum(amounts)
    rose = progress["budget"]["used_usd"] - cap["used_usd"]
    print("Cost of this run: ${:.4f} by the answers' own costs (start-up test ${:.4f}, votes ${:.4f}, "
          "rewriter ${:.4f}, checker ${:.4f}); the key's used amount rose by ${:.4f}".format(own, *amounts, rose))
    if abs(own - rose) > config.COST_GAP_LIMIT:
        time.sleep(5)  # Otari may still be writing its rows
        try:
            rose = otari.require_cap()["used_usd"] - cap["used_usd"]
        except otari.OtariError:
            pass
        if abs(own - rose) > config.COST_GAP_LIMIT:
            print(f"NOTE: 5 seconds later the key's used amount had risen by ${rose:.4f}. "
                  f"That differs from the answers' own costs by ${abs(own - rose):.4f}.")
        else:
            print(f"5 seconds later the key's used amount had risen by ${rose:.4f}: the two totals agree.")
    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=int, default=config.GENERATIONS)
    parser.add_argument("--until-refused", action="store_true")
    options = parser.parse_args()
    data = read_data()
    run_id = time.strftime("%Y%m%d-%H%M")
    folder = RUNS / run_id
    if folder.exists():
        sys.exit(f"A run with the id {run_id} exists already. Wait a minute and start again.")
    (folder / "pages").mkdir(parents=True)
    try:
        status = main(run_id, folder, *data, options.generations, options.until_refused)
    except otari.OtariError as problem:  # before the run could start: the key or its cap
        print(f"Stopped: {problem}")
        sys.exit(1)
    sys.exit(1 if status == "stopped_error" else 0)
