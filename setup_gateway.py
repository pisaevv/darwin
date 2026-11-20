"""One-time gateway setup. The only file that uses the master key.

  .venv/bin/python setup_gateway.py init                   add what is missing on the gateway
  .venv/bin/python setup_gateway.py key <name> <dollars>   make the key darwin-<name> with a spending cap
  .venv/bin/python setup_gateway.py use <name>             make a kept key the key in use

A name may hold letters, digits and dashes.
"""
import os
import re
import sys

import httpx
from dotenv import dotenv_values, set_key

import config

KEY_SCOPES = ["inference:run", "web:search", "web:fetch", "usage:read"]
NEBIUS_API_BASE = "https://api.tokenfactory.nebius.com/v1/"  # PLAN.md section 11
SECRET_NAMES = ["OTARI_MASTER_KEY", "NEBIUS_API_KEY", "TAVILY_API_KEY"]


class GatewayRefused(Exception):
    """The gateway answered with an error."""


def refusal(answer):
    """The gateway's own error message, without anything that could hold a key."""
    try:
        detail = answer.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, list):  # a field error: say where and what, never the value that was sent
        detail = "; ".join(f"{d.get('loc')}: {d.get('msg')}" for d in detail)
    text = f"status {answer.status_code}: {detail}"
    for name in SECRET_NAMES:
        if os.environ.get(name):
            text = text.replace(os.environ[name], "[hidden]")
    return text


def call(method, path, body=None, key=None, **params):
    """One call to the gateway. Uses the master key unless another key is given."""
    answer = httpx.request(
        method,
        config.OTARI_BASE_URL + path,
        json=body,
        params=params,
        headers={"Authorization": "Bearer " + (key or os.environ["OTARI_MASTER_KEY"])},
        timeout=60,
    )
    if answer.status_code >= 300:
        raise GatewayRefused(f"{method} {path} gave {refusal(answer)}")
    return answer.json() if answer.content else None


def same_money(a, b):
    return a is not None and abs(a - b) < 0.000001


def tavily_catalog_price():
    for tool in call("GET", "/search-tools/catalog")["data"]:
        if tool["id"] == "tavily":
            return tool["price_per_call"]
    return None


def init():
    providers = [p["name"] for p in call("GET", "/hosted-providers")["data"]]
    if "nebius" in providers:
        print("Nebius provider: already there")
    else:
        body = {"provider": "nebius", "api_key": os.environ["NEBIUS_API_KEY"]}
        try:
            call("POST", "/hosted-providers", body)
        except GatewayRefused:
            # PLAN.md section 11: if the plain form fails, name the Nebius address
            call("POST", "/hosted-providers", {**body, "api_base": NEBIUS_API_BASE})
        print("Nebius provider: created")

    tools = [t["name"] for t in call("GET", "/search-tools")["stored"]]
    if "tavily" in tools:
        print("tavily search tool: already there")
    else:
        made = call("POST", "/search-tools", {
            "name": "tavily",
            "provider": "tavily",
            "api_key": os.environ["TAVILY_API_KEY"],
            "options": {"include_raw_content": True},
        })
        print("tavily search tool: created")
        if made.get("notice"):
            print("  the gateway says:", made["notice"])

    rows = call("GET", "/pricing/current", limit=200)["data"]
    priced = {(row["kind"], row["model_key"]) for row in rows}

    if ("search", "tavily") in priced:
        print("tavily price: already there")
    else:
        price = config.TAVILY_PRICE
        # The gateway refuses a price without output_price_per_million (PLAN.md leaves it out).
        call("POST", "/pricing", {"model_key": "tavily", "kind": "search",
                                  "input_price_per_million": round(price * 1_000_000),
                                  "output_price_per_million": 0})
        shown = tavily_catalog_price()
        note = ""
        if not same_money(shown, price):
            first = shown
            call("POST", "/pricing", {"model_key": "tavily", "kind": "search", "price_per_request": price})
            shown = tavily_catalog_price()
            note = f" (the first form gave {first}, so it was sent again as price_per_request)"
        if not same_money(shown, price):
            sys.exit(f"tavily price: sent, but the gateway shows {shown} per call, not {price}{note}")
        print(f"tavily price: created, ${shown} per call{note}")

    if ("fetch", "builtin_fetch") in priced:
        print("builtin_fetch price: already there")
    else:
        call("POST", "/pricing", {"model_key": "builtin_fetch", "kind": "fetch",
                                  "input_price_per_million": 0, "output_price_per_million": 0})
        print("builtin_fetch price: created, $0 per call")


def env_name(name):
    return "OTARI_KEY_" + name.upper().replace("-", "_")


def set_env(name, value):
    """Change one line of .env and leave the others as they are."""
    set_key(config.ENV_PATH, name, value, quote_mode="never")


def keep_current_key():
    """Never lose a key: Otari shows a key only once. Before OTARI_API_KEY is replaced,
    keep its value as OTARI_KEY_PREVIOUS, unless an OTARI_KEY_ line already holds it."""
    env = dotenv_values(config.ENV_PATH)
    current = env.get("OTARI_API_KEY")
    if not current or any(k.startswith("OTARI_KEY_") and v == current for k, v in env.items()):
        return
    name, number = "OTARI_KEY_PREVIOUS", 2
    while env.get(name):  # that line holds another key: do not overwrite it
        name, number = f"OTARI_KEY_PREVIOUS_{number}", number + 1
    set_env(name, current)
    print(f"Kept the key that was in use (...{current[-4:]}) as {name}")


def key(name, dollars):
    full_name, line = "darwin-" + name, env_name(name)
    how_to_use = f"To use it: .venv/bin/python setup_gateway.py use {name}"

    # 1. Refuse before creating anything. A second key would get a fresh cap.
    if any(k["key_name"] == full_name for k in call("GET", "/keys", limit=1000)):
        sys.exit(f"A key named {full_name} already exists on the gateway. Nothing was created. {how_to_use}")
    if dotenv_values(config.ENV_PATH).get(line):
        sys.exit(f".env already has {line}. Nothing was created. {how_to_use}")

    # 2. Create the budget, the key and the link. 3. Confirm the cap with the new key itself.
    created = []  # what to delete again if anything goes wrong
    try:
        budget_id = call("POST", "/budgets", {"name": full_name, "max_budget": dollars})["budget_id"]
        created.append("/budgets/" + budget_id)
        made = call("POST", "/keys", {"key_name": full_name, "scopes": KEY_SCOPES})
        created.append("/keys/" + made["id"])
        link = call("POST", "/scoped-budgets",
                    {"scope_type": "api_token", "scope_id": made["id"], "budget_id": budget_id})
        created.append("/scoped-budgets/" + link["id"])

        budget = call("GET", "/key/budget", key=made["key"])
        caps = [x["limit_usd"] for x in budget["limits"] if x["scope"] == "api_token"]
        if budget["budgets_enforced"] is not True or not caps or not same_money(caps[0], dollars):
            raise GatewayRefused(f"the new key's cap could not be confirmed (budgets_enforced: "
                                 f"{budget['budgets_enforced']}, caps on the key: {caps})")
    except Exception as problem:
        # 5. A key without a confirmed cap must never become the key in use.
        for path in reversed(created):  # the link, then the key, then the budget
            try:
                call("DELETE", path)
            except Exception as not_deleted:
                print(f"Could not delete {path}: {not_deleted}")
        sys.exit(f"Could not make {full_name}: {problem}\nWhat this run created was deleted. .env was not changed.")

    # 4. Only now write .env.
    keep_current_key()
    set_env(line, made["key"])
    set_env("OTARI_API_KEY", made["key"])
    print(f"{full_name}: capped at ${dollars:.2f}, ends in ...{made['key'][-4:]}, "
          f"saved as {line} and now the key in use")


def use(name):
    line = env_name(name)
    value = dotenv_values(config.ENV_PATH).get(line)
    if not value:
        sys.exit(f".env has no {line} line. Nothing was changed.")
    keep_current_key()
    set_env("OTARI_API_KEY", value)
    print(f"Key in use: {name} ({line}), ends in ...{value[-4:]}")


def main():
    args = sys.argv[1:]
    if len(args) > 1 and not re.fullmatch(r"[A-Za-z0-9-]+", args[1]):
        sys.exit("A name may hold letters, digits and dashes only.")
    if args == ["init"]:
        init()
    elif len(args) == 3 and args[0] == "key":
        try:
            dollars = float(args[2])
        except ValueError:
            sys.exit(__doc__)
        if dollars <= 0:
            sys.exit("The cap must be more than 0 dollars.")
        key(args[1], dollars)
    elif len(args) == 2 and args[0] == "use":
        use(args[1])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    try:
        main()
    except (GatewayRefused, httpx.HTTPError) as problem:
        sys.exit(f"Stopped: {problem}")
