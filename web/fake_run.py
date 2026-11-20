"""Writes made-up runs for testing web/chart.html. Nothing in them is a result.

Run:  .venv/bin/python web/fake_run.py          (removes and rewrites the nine fixed runs)
      .venv/bin/python web/fake_run.py --live   (writes runs/fake-live step by step, about 45 s)

It writes only into runs/fake-<name>/ and imports nothing from this project.
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

RUNS = Path(__file__).resolve().parent.parent / "runs"

PANEL = [
    "nebius:openai/gpt-oss-120b",
    "nebius:google/gemma-3-27b-it",
    "nebius:Qwen/Qwen3-235B-A22B-Instruct-2507",
    "nebius:zai-org/GLM-5.3-Flash",
    "nebius:MiniMaxAI/MiniMax-M3.1-Flash",
    "nebius:deepseek-ai/DeepSeek-V4.1-Flash-1017",
]

# gen, best page, training for us, valid, held-out for us, valid, children made, dropped, no-votes, cost
TIMELINE = [
    (0, "g0", 4, 36, 5, 48, 0, 0, 0, 0.09),
    (1, "g1_c2", 7, 36, 8, 48, 4, 1, 2, 0.31),
    (2, "g1_c2", 7, 36, 8, 48, 4, 0, 0, 0.36),
    (3, "g3_c1", 10, 36, 12, 48, 4, 2, 1, 0.27),
    (4, "g3_c1", 10, 36, 12, 48, 4, 4, 0, 0.05),
    (5, "g5_c4", 13, 36, 10, 48, 4, 1, 3, 0.33),
    (6, "g5_c4", 13, 36, 10, 48, 4, 0, 0, 0.35),
    (7, "g7_c3", 15, 36, 15, 47, 4, 1, 1, 0.32),
    (8, "g7_c3", 15, 36, 15, 47, 4, 1, 0, 0.28),
    (9, "g7_c3", 15, 36, 15, 47, 4, 0, 2, 0.34),
    (10, "g10_c1", 17, 36, 17, 48, 4, 2, 0, 0.29),
    (11, "g10_c1", 17, 36, 17, 48, 4, 1, 1, 0.30),
    (12, "g12_c2", 18, 36, 18, 48, 4, 0, 0, 0.37),
]

# Held-out votes for us per model, in PANEL's order, for each best page.
FOR_US = {
    "g0": [1, 0, 2, 0, 1, 1],
    "g1_c2": [2, 0, 3, 0, 2, 1],
    "g3_c1": [3, 1, 3, 0, 4, 1],
    "g5_c4": [3, 0, 2, 1, 3, 1],
    "g7_c3": [4, 1, 3, 0, 5, 2],
    "g10_c1": [5, 1, 4, 0, 5, 2],
    "g12_c2": [5, 1, 4, 0, 6, 2],
}
# Valid held-out votes per model: 8 each, except one model with 7 for g7_c3.
VALID = {"g7_c3": [8, 8, 8, 7, 8, 8]}

ORIGINAL = """# Example Widget

Example Widget is an invented product. It exists only so that the chart page has a text to show while it is being tested. Nothing in this text describes a real product, a real company or a real price.

The widget is said to sort made-up parcels by colour and by weight. Its makers, who do not exist, claim that it does so quietly and that it fits on a small desk in a small office.

- Sorts up to 40 made-up parcels a minute
- Comes in grey and in a slightly different grey
- Needs no manual, because there is none

This line must show as text: <b>not bold</b> <script>document.title = "BROKEN"</script>
"""

BEST = """# Made-up text of {best}

This is the made-up text of the page {best}. A real run shows here the page that the rewriter wrote and that the panel liked best. This text was typed into web/fake_run.py and comes from no model.

For small offices that drown in parcels, the invented widget sorts them by colour and by weight before the first coffee is cold. It is quiet, it fits on a desk, and it asks for nothing but a socket.

- Up to 40 made-up parcels a minute, sorted without a sound
- Two colours to choose from, both of them grey
- Nothing to learn: plug it in and it sorts

None of this is true, and none of it is a result.
"""


def generation(row, step6=False):
    gen, best, train, train_valid, held, held_valid, made, dropped, no_votes, cost = row
    entry = {"gen": gen, "champion": best, "train_share": train / train_valid, "heldout_share": held / held_valid,
             "children_made": made, "children_dropped": dropped, "no_votes": no_votes, "cost_usd": cost}
    if step6:
        entry["rewriter_model"] = None if gen == 0 else "Qwen/Qwen3.8-27B" if gen >= 11 else "zai-org/GLM-5.3"
    entry["per_model_heldout"] = {m: [f, v] for m, f, v in zip(PANEL, FOR_US[best], VALID.get(best, [8] * 6))}
    return entry


def generations(last, step6=False):
    return [generation(row, step6) for row in TIMELINE[: last + 1]]


def run_data(name, gens, status, limit, used, final=None):
    best = gens[-1]["champion"] if gens else "g0"
    return {"run_id": name, "product": "Made-up test data", "status": status, "panel": PANEL,
            "budget": {"limit_usd": limit, "used_usd": used, "remaining_usd": round(limit - used, 3)},
            "generations": gens, "original_page": "pages/g0.md", "champion_page": f"pages/{best}.md",
            "final": final and {"original_share": final[0] / 144, "champion_share": final[1] / 144, "votes_each": 144}}


def fresh(name):
    folder = RUNS / ("fake-" + name)
    shutil.rmtree(folder, ignore_errors=True)
    (folder / "pages").mkdir(parents=True)
    return folder


def write_json(folder, text):
    """Under another name first, then renamed: a reader never meets half a file."""
    (folder / "progress.json.tmp").write_text(text)
    os.replace(folder / "progress.json.tmp", folder / "progress.json")


def write(folder, data, broken=False):
    """The page files first, then progress.json. broken=True writes only the first half, on purpose."""
    (folder / "pages" / "g0.md").write_text(ORIGINAL)
    best = Path(data["champion_page"]).stem
    if best != "g0":
        (folder / "pages" / (best + ".md")).write_text(BEST.format(best=best))
    text = json.dumps(data, indent=2) + "\n"
    if broken:
        (folder / "progress.json").write_text(text[: len(text) // 2])
    else:
        write_json(folder, text)


def fixed():
    finished = run_data("fake-finished", generations(12, step6=True), "finished", 5.00, 3.87, (16, 53))
    finished["spend_by_role"] = {"panel": 2.80, "rewriter": 0.78, "checker": 0.14}
    low = run_data("fake-low-budget", generations(8), "stopped_low_budget", 3.00, 2.57, (17, 46))
    for gen in (2, 4, 6, 8):
        low["generations"][gen]["heldout_share"] = None
    cut = {"gen": 2, "champion": "g2_c3", "train_share": 9 / 36, "heldout_share": None,
           "children_made": 4, "children_dropped": 1, "no_votes": 0, "cost_usd": 0.21}
    runs = [
        ("finished", finished),
        ("running", run_data("fake-running", generations(4), "running", 5.00, 1.08)),
        ("gen0", run_data("fake-gen0", generations(0), "running", 5.00, 0.09)),
        ("start", run_data("fake-start", [], "running", 5.00, 0.01)),
        ("low-budget", low),
        ("refused", run_data("fake-refused", generations(1) + [cut], "stopped_by_budget", 1.00, 1.003)),
    ]
    for name, data in runs:
        write(fresh(name), data)
        print(f"wrote runs/fake-{name}: {len(data['generations'])} generations, {data['status']}")

    folder = fresh("sparse")
    (folder / "pages").rmdir()
    write_json(folder, '{"status": "running", "generations": [{"gen": 0, "train_share": 0.11}]}\n')
    print("wrote runs/fake-sparse: almost every field is missing")
    write(fresh("broken"), runs[1][1], broken=True)
    print("wrote runs/fake-broken: progress.json is half a file, not JSON")
    (fresh("nofile") / "pages" / "g0.md").write_text(ORIGINAL)
    print("wrote runs/fake-nofile: a page file, no progress.json")


def live():
    folder = fresh("live")

    def step(last, wait, status="running", final=None, broken=False):
        gens = generations(last)
        used = round(sum(g["cost_usd"] for g in gens), 2) if gens else 0.01
        write(folder, run_data("fake-live", gens, status, 5.00, used, final), broken)
        what = "half a file, on purpose" if broken else f"{len(gens)} generations, {status}"
        print(f"runs/fake-live: {what}; waiting {wait} s", flush=True)
        time.sleep(wait)

    step(-1, 8)
    for last in (0, 1, 2):
        step(last, 4)
    step(3, 11, broken=True)
    for last in (3, 4, 5):
        step(last, 4)
    step(5, 0, "finished", (17, 33))


if __name__ == "__main__":
    live() if "--live" in sys.argv else fixed()
