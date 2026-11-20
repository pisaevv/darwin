"""Tests the gateway, the key and every model. Writes no files.

  .venv/bin/python check.py

Later steps import test_models() and read_pick() from here.
"""
import queue
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import config
import otari

SYSTEM_MESSAGE = (
    "You help a buyer choose a product. You get the buyer's question and the web pages of "
    "several products. Recommend exactly one of them: the one you would really suggest to this buyer."
)

# A tiny made-up example, so the test works before data/ exists.
TEST_PRODUCTS = [
    ("Brindlecal", "Brindlecal is a shared calendar for small offices. "
                   "It costs $4 per person a month and works on phones."),
    ("Sprintmoss", "Sprintmoss is a task board for software teams with sprint planning and reports. "
                   "It is free for up to 10 people."),
    ("Bookfinch", "Bookfinch is a booking page for freelancers that also takes payments. "
                  "It charges 2% per booking and has no monthly fee."),
]
TEST_QUESTIONS = [
    "I'm a freelance photographer. What should I use so clients can book me and pay online?",
    "Our 8-person software team needs a simple way to plan sprints. What do you recommend?",
    "Which tool keeps everyone's meetings in one shared calendar for a small office?",
]
TEST_LETTERS = "ABC"

FETCH_OFF = ("Fetch is switched off on the gateway. The owner turns it on with "
             "OTARI_WEB_FETCH_ENABLED=true on the server.")


def read_pick(text, letters):
    """The pick in a model's answer: the last "PICK:" followed by one of the allowed letters.
    Returns the letter, or None if there is no readable pick."""
    picks = re.findall(rf"PICK:[\s*]*([{letters}])\b", text)
    return picks[-1] if picks else None


def maker(model):
    """Who made a model: the text between "nebius:" and "/"."""
    return model.split(":", 1)[1].split("/", 1)[0]


def panel_problem(panel):
    """Why this panel is too small to run with, or None if it is fine."""
    makers = {maker(model) for model in panel}
    if len(panel) < config.MIN_PANEL_MODELS or len(makers) < config.MIN_PANEL_MAKERS:
        return (f"the panel has {len(panel)} working models from {len(makers)} makers; it needs at least "
                f"{config.MIN_PANEL_MODELS} from at least {config.MIN_PANEL_MAKERS}")
    return None


def brief(problem):
    """An error in a few words: the status, the code and the gateway's text."""
    parts = [problem.status, problem.code, problem.detail]
    return " ".join(str(part) for part in parts if part)[:110] or str(problem)


def test_messages(question):
    """One test vote in the format of PLAN.md 4.4."""
    lines = [f"Buyer's question: {question}", ""]
    for letter, (name, text) in zip(TEST_LETTERS, TEST_PRODUCTS):
        lines += [f"Product {letter}: {name}", text, ""]
    lines += ["Answer in exactly two lines:", "PICK: <letter>", "WHY: <one sentence, 25 words at most>"]
    return [{"role": "system", "content": SYSTEM_MESSAGE}, {"role": "user", "content": "\n".join(lines)}]


def ask(row, role, question, **settings):
    """One test call to the model of this row. Adds the time and the cost to the row."""
    answer = otari.chat(row["model"], test_messages(question), config.PANEL_MAX_TOKENS,
                        timeout=config.SHORT_TIMEOUT, tags={"role": role}, **settings)
    row["calls"] += 1
    row["seconds"] = max(row["seconds"], answer["seconds"])
    row["cost_usd"] += answer["cost_usd"]
    return answer["text"]


def test_panel_model(row):
    """Three test votes for one panel model. Fills in its row. True if all three gave a pick."""
    if not row["priced"]:
        row.update(result="FAIL", note="not listed with a price")
        return False
    settings = {"temperature": 0, "reasoning_effort": "low"}
    picks = []
    for question in TEST_QUESTIONS:
        try:
            try:
                text = ask(row, "panel", question, **settings)
            except otari.CallFailed as problem:
                if problem.status != 400 or "reasoning_effort" not in settings:
                    raise
                del settings["reasoning_effort"]  # refused: try once without, and keep it off if that works
                text = ask(row, "panel", question, **settings)
                row["no_reasoning_effort"] = True
        except otari.OtariError as problem:
            row.update(result="FAIL", note=brief(problem))
            return False
        pick = read_pick(text, TEST_LETTERS)
        if not pick:
            row.update(result="FAIL", note=f"no readable pick in: {text[:60]!r}")
            return False
        picks.append(pick)
    without = ", without reasoning_effort" if row["no_reasoning_effort"] else ""
    row.update(result="ok", note="picks " + " ".join(picks) + without)
    return True


def test_one_answer(row, role):
    """One test call for a rewriter or a checker. Any answer that is not empty passes."""
    if not row["priced"]:
        row.update(result="FAIL", note="not listed with a price")
        return
    try:
        text = ask(row, role, TEST_QUESTIONS[0])
    except otari.OtariError as problem:
        row.update(result="FAIL", note=brief(problem))
        return
    if text.strip():
        row.update(result="ok", note=f"answered: {' '.join(text.split())[:40]!r}")
    else:
        row.update(result="FAIL", note="empty answer")


def test_models():
    """The start-up test of PLAN.md 4.3. Every model in config.py gets a free lookup.
    The models that are needed get paid test calls (a few cents in total).

    Returns a dictionary:
      panel                the panel models that passed, with reserves in place of failed ones
      no_reasoning_effort  panel models that must be called without reasoning_effort
      rewriter, checker    the model for each job, or None if none works
      rows                 one row per model, for the table
    """
    rows = {}
    for role, models in [("panel", config.PANEL), ("panel reserve", config.RESERVES),
                         ("rewriter", [config.REWRITER]), ("rewriter reserve", [config.REWRITER_RESERVE]),
                         ("checker", [config.CHECKER]), ("checker reserve", [config.CHECKER_RESERVE])]:
        for model in models:
            if model in rows:
                rows[model]["role"] += " + " + role
                continue
            info = otari.model_info(model)
            rows[model] = {"model": model, "role": role, "priced": bool(info and info.get("pricing")),
                           "result": "-", "note": "not needed", "calls": 0, "seconds": 0.0,
                           "cost_usd": 0.0, "no_reasoning_effort": False}

    # The panel: one thread per seat. A model that fails gives its seat to the next reserve.
    reserves = queue.SimpleQueue()
    for model in config.RESERVES:
        reserves.put(model)

    def fill_seat(model):
        while not test_panel_model(rows[model]):
            try:
                model = reserves.get_nowait()
            except queue.Empty:
                return None
        return model

    with ThreadPoolExecutor(len(config.PANEL)) as pool:
        panel = [model for model in pool.map(fill_seat, config.PANEL) if model]

    def first_working(models, role):
        for model in models:
            if rows[model]["result"] == "-":  # not tested yet
                test_one_answer(rows[model], role)
            if rows[model]["result"] == "ok":
                return model
        return None

    return {
        "panel": panel,
        "no_reasoning_effort": [model for model in panel if rows[model]["no_reasoning_effort"]],
        "rewriter": first_working([config.REWRITER, config.REWRITER_RESERVE], "rewriter"),
        "checker": first_working([config.CHECKER, config.CHECKER_RESERVE], "checker"),
        "rows": list(rows.values()),
    }


def print_models(rows):
    form = "  {:<44} {:<34} {:<7} {:<5} {:>7}  {:>9}  {}"
    print("Models:")
    print(form.format("model", "role", "priced", "test", "slowest", "cost", "note"))
    for row in rows:
        tested = row["calls"] > 0
        print(form.format(row["model"], row["role"], "yes" if row["priced"] else "no", row["result"],
                          f"{row['seconds']:.1f}s" if tested else "", f"${row['cost_usd']:.6f}" if tested else "",
                          row["note"]))


def print_tags_and_session(model_calls, other_calls):
    """For information only: did Otari keep the tags, and does it see the calls as one session?"""
    try:
        for attempt in range(3):  # rows can take a few seconds to appear
            usage = otari.usage_summary(group_by_tag="role", dimensions="source_label")
            if usage["totals"]["request_count"] >= model_calls:
                break
            time.sleep(3)
    except otari.OtariError as problem:
        print(f"Tags and session: could not be read ({brief(problem)})")
        return
    per_role = ", ".join(f"{row['key'] or 'no role tag'} {row['requests']}" for row in usage["by_tag"])
    print(f"Tags and session: calls per role: {per_role or 'none found'} "
          f"(this check made {model_calls} model calls and {other_calls} search and fetch calls)")
    if other_calls and not any(row["key"] == "research" for row in usage["by_tag"]):
        print("  the search and fetch calls are not among them: this gateway keeps tags for model calls only")
    sessions = [row for row in usage["by_source_label"] if row["key"]]
    in_sessions = sum(row["requests"] for row in sessions)
    if len(sessions) == 1:
        print(f"  one session ({sessions[0]['key'][:12]}...) holds {in_sessions} of the "
              f"{usage['totals']['request_count']} calls Otari counted for this run")
    else:
        print(f"  NOT one session: Otari shows {len(sessions)} sessions holding {in_sessions} of the "
              f"{usage['totals']['request_count']} calls it counted for this run")


def finish(reasons):
    if reasons:
        print("RESULT: FAIL")
        for reason in reasons:
            print("  - " + reason)
        sys.exit(1)
    print("RESULT: PASS")
    sys.exit(0)


def main():
    run_id = "check-" + time.strftime("%Y%m%d-%H%M")
    otari.start(run_id)
    print(f"Run id: {run_id}")
    reasons = []  # why the result is FAIL

    # 1. Gateway
    try:
        healthy = otari.health()
    except otari.OtariError:
        healthy = False
    print("Gateway:", "healthy" if healthy else "NOT healthy")
    if not healthy:
        finish(["the gateway is not healthy"])

    # 2. Key. Without a cap the check stops here.
    try:
        cap = otari.require_cap()
    except otari.SetupProblem as problem:
        print(f"Key: ...{config.OTARI_API_KEY[-4:]}  {problem}")
        finish([str(problem)])
    print(f"Key: ...{config.OTARI_API_KEY[-4:]}  cap ${cap['limit_usd']:.2f}, "
          f"used ${cap['used_usd']:.4f}, left ${cap['remaining_usd']:.4f}")

    # 3. Models
    tested = test_models()
    print_models(tested["rows"])
    cost = sum(row["cost_usd"] for row in tested["rows"])
    model_calls = sum(row["calls"] for row in tested["rows"])
    other_calls = 0  # search and fetch
    if panel_problem(tested["panel"]):
        reasons.append(panel_problem(tested["panel"]))
    if not tested["rewriter"]:
        reasons.append("no working rewriter")
    if not tested["checker"]:
        reasons.append("no working checker")
    if tested["rewriter"] and tested["rewriter"] == tested["checker"]:
        reasons.append("the rewriter and the checker are the same model")

    # 4. Search
    price = next((tool["price_per_call"] for tool in otari.search_catalog() if tool["id"] == "tavily"), None)
    if price is None or abs(price - config.TAVILY_PRICE) > 0.000001:
        reasons.append(f"tavily is priced at {price}, not {config.TAVILY_PRICE}")
    try:
        found = otari.search("what is an AI gateway", max_results=2, max_tokens_per_page=100,
                             tags={"role": "research"})
        cost += found["cost_usd"]
        other_calls += 1
        print(f"Search: tavily priced at {price} per call; one search gave {len(found['results'])} results "
              f"and cost ${found['cost_usd']}")
        if not found["results"]:
            reasons.append("the search gave no results")
    except otari.OtariError as problem:
        print(f"Search: tavily priced at {price} per call; the search FAILED: {brief(problem)}")
        reasons.append("the search failed: " + brief(problem))

    # 5. Fetch
    try:
        page = otari.fetch("https://example.com", 2000, tags={"role": "research"})
        cost += page["cost_usd"]
        other_calls += 1
        print(f"Fetch: https://example.com gave {len(page['text'])} characters and cost ${page['cost_usd']}")
        if not page["text"]:
            reasons.append("the fetch gave an empty page")
    except otari.OtariError as problem:
        if problem.status == 400 and "disabled" in (problem.detail or ""):
            message = FETCH_OFF
        else:
            message = "the fetch failed: " + brief(problem)
        print("Fetch: FAILED. " + message)
        reasons.append(message)

    # 6. Tags and session (for information; never fails the check)
    print_tags_and_session(model_calls, other_calls)

    # 7. Result
    makers = sorted({maker(model) for model in tested["panel"]})
    print(f"Final panel: {len(tested['panel'])} models from {len(makers)} makers ({', '.join(makers)})")
    for model in tested["panel"]:
        without = "  (without reasoning_effort)" if model in tested["no_reasoning_effort"] else ""
        print(f"  {model}{without}")
    print(f"Rewriter: {tested['rewriter'] or 'none works'}")
    print(f"Checker: {tested['checker'] or 'none works'}")
    used = otari.require_cap()["used_usd"] - cap["used_usd"]
    print(f"Cost of this check: ${cost:.4f} by the answers' own costs; the key's used amount rose by ${used:.4f}")
    finish(reasons)


if __name__ == "__main__":
    try:
        main()
    except otari.OtariError as problem:
        print(f"Stopped: {problem}")
        finish(["the check could not finish: " + brief(problem)])
