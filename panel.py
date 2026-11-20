"""Asks the panel and counts votes. Reads no files: evolve.py hands it everything.

What stays the same during a run comes as one dictionary, called run:
  run_id               the run's id
  votes_path           the path of votes.jsonl
  panel                the panel models; a model's seat is its position in this list, from 0
  no_reasoning_effort  panel models that are called without reasoning_effort
  ours                 our product's name
  competitors          (name, page text) pairs, in file order
"""
import json
import random
import re
import string
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import check
import config
import otari


def product_order(question, q, model, seat, order_no, competitors, ours):
    """The product names in the order one vote shows them: the first is Product A.
    The competitors are shuffled, always the same way for one question, model and order number.
    Our product's place takes turns, so every place comes up equally often.
    The variant plays no part, so every variant meets the same orders."""
    others = list(competitors)
    random.Random(f"{question}|{model}|{order_no}").shuffle(others)
    place = (q + seat + 2 * order_no) % (len(others) + 1)
    return others[:place] + [ours] + others[place:]


def vote_messages(question, products):
    """The messages of one vote (PLAN.md 4.4). products are (name, page text) pairs in the order shown."""
    lines = [f"Buyer's question: {question}", ""]
    for letter, (name, text) in zip(string.ascii_uppercase, products):
        lines += [f"Product {letter}: {name}", text.strip(), ""]
    lines += ["Answer in exactly two lines:", "PICK: <letter>", "WHY: <one sentence, 25 words at most>"]
    return [{"role": "system", "content": check.SYSTEM_MESSAGE}, {"role": "user", "content": "\n".join(lines)}]


def read_why(text):
    """The reason in a model's answer: what follows the last "WHY:" on its line."""
    found = re.findall(r"WHY:(.*)", text)
    return found[-1].strip(" *\t\r") if found else ""


def one_vote(run, variant, page, set_name, q, question, model, order_no, gen):
    """Asks one model one question. Returns the vote: one dictionary, later one line of votes.jsonl."""
    names = [name for name, text in run["competitors"]]
    order = product_order(question, q, model, run["panel"].index(model), order_no, names, run["ours"])
    letters = string.ascii_uppercase[:len(order)]
    pages = {**dict(run["competitors"]), run["ours"]: page}
    vote = {"run": run["run_id"], "gen": gen, "set": set_name, "q": q, "question": question, "model": model,
            "variant": variant, "order_no": order_no, "order": order, "ours": letters[order.index(run["ours"])],
            "pick": None, "picked": None, "for_us": None, "why": "", "no_vote": None, "answer": "",
            "finish": None, "tokens_in": None, "tokens_out": None, "tokens_thinking": None, "cost_usd": 0.0}
    settings = {"temperature": 0}
    if model not in run["no_reasoning_effort"]:
        settings["reasoning_effort"] = "low"
    started = time.monotonic()
    try:
        answer = otari.chat(model, vote_messages(question, [(name, pages[name]) for name in order]),
                            config.PANEL_MAX_TOKENS, timeout=config.PANEL_TIMEOUT,
                            tags={"role": "panel", "gen": gen, "set": set_name}, **settings)
    except otari.CallFailed as problem:  # otari.py has already waited and tried again
        vote["no_vote"] = check.brief(problem)
    else:
        usage = answer["raw"].get("usage") or {}
        thinking = usage.get("reasoning_tokens")  # models report it in one of two places, or not at all
        if thinking is None:
            thinking = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        pick = check.read_pick(answer["text"], letters)
        vote.update(answer=answer["text"], why=read_why(answer["text"]), cost_usd=answer["cost_usd"],
                    finish=(answer["raw"].get("choices") or [{}])[0].get("finish_reason"),
                    tokens_in=usage.get("prompt_tokens"), tokens_out=usage.get("completion_tokens"),
                    tokens_thinking=thinking)
        if pick:
            picked = order[letters.index(pick)]
            vote.update(pick=pick, picked=picked, for_us=picked == run["ours"])
        else:
            vote["no_vote"] = "no readable pick" if answer["text"].strip() else "empty answer"
    vote.update(seconds=round(time.monotonic() - started, 2), time=time.strftime("%Y-%m-%dT%H:%M:%S"))
    return vote


def score(run, variant, page, set_name, questions, gen, order_nos=(0,)):
    """Scores one page on one list of questions: every panel model answers every question,
    once per order number. Each vote is added to votes.jsonl as it comes back.

    Returns a dictionary: variant, set, votes (in the order asked), for_us, valid, no_votes,
    share (for_us / valid, or None), cost_usd and per_model ({model: [for_us, valid]}).
    Raises otari.BudgetExceeded or otari.SetupProblem after the calls in flight have finished."""
    # In this order the models take turns, so no model gets all the requests in flight at once.
    jobs = [(q, question, model, order_no)
            for order_no in order_nos for q, question in enumerate(questions) for model in run["panel"]]
    stop = threading.Event()  # set by the first job that cannot go on; no job starts a call after that

    def job(q, question, model, order_no):
        if stop.is_set():
            return None
        try:
            return one_vote(run, variant, page, set_name, q, question, model, order_no, gen)
        except Exception:
            stop.set()
            raise

    votes = [None] * len(jobs)
    first_error = None
    with ThreadPoolExecutor(config.REQUESTS_IN_FLIGHT) as pool, \
            open(run["votes_path"], "a", encoding="utf-8") as file:
        futures = {pool.submit(job, *args): number for number, args in enumerate(jobs)}
        for future in as_completed(futures):
            try:
                vote = future.result()
            except (otari.BudgetExceeded, otari.SetupProblem) as problem:
                first_error = first_error or problem
                continue
            if vote:
                votes[futures[future]] = vote
                file.write(json.dumps(vote, ensure_ascii=False) + "\n")
                file.flush()
    if first_error:
        raise first_error

    valid = [vote for vote in votes if vote["pick"]]
    for_us = [vote for vote in valid if vote["for_us"]]
    return {
        "variant": variant,
        "set": set_name,
        "votes": votes,
        "for_us": len(for_us),
        "valid": len(valid),
        "no_votes": len(votes) - len(valid),
        "share": len(for_us) / len(valid) if valid else None,
        "cost_usd": sum(vote["cost_usd"] for vote in votes),
        "per_model": {model: [sum(vote["model"] == model for vote in for_us),
                              sum(vote["model"] == model for vote in valid)] for model in run["panel"]},
    }
