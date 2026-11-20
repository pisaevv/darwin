"""Every call made with the run's key goes through this file.

Call start(run_id) first. Then use health, model_info, chat, search, fetch,
key_budget, require_cap, search_catalog and usage_summary.
Errors follow the table in PLAN.md 4.8 and come as one of three types (below).
"""
import threading
import time
from urllib.parse import quote

import httpx

import config


class OtariError(Exception):
    """A call to Otari did not work. Keeps the status, the gateway's code and its detail text."""

    def __init__(self, message, status=None, code=None, detail=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.detail = detail


class CallFailed(OtariError):
    """This one call failed, after the tries it gets. The caller decides what that means."""


class BudgetExceeded(OtariError):
    """The key's spending cap is used up (403 with the code budget_exceeded)."""


class SetupProblem(OtariError):
    """Something is set up wrong: the key, a model, a price, a provider. Trying again does not help."""


NO_CAP = "This key has no spending cap. Run: .venv/bin/python setup_gateway.py key dev 3"

_client = httpx.Client()
_run_id = "unnamed"
_cap_seen = False
_cap_lock = threading.Lock()


def start(run_id):
    """Name this program run. Every call is labelled with it."""
    global _run_id
    _run_id = run_id


def _error_parts(answer):
    """The code and the detail text of an error answer."""
    try:
        data = answer.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return answer.headers.get("Otari-Error-Code"), answer.text[:200]
    detail = data.get("detail")
    if isinstance(detail, list):  # a field error: say where and what
        detail = "; ".join(f"{d.get('loc')}: {d.get('msg')}" for d in detail)
    return data.get("code") or answer.headers.get("Otari-Error-Code"), str(detail)


def _wait_seconds(answer):
    try:
        return float(answer.headers["Retry-After"])
    except (KeyError, ValueError):
        return config.RATE_LIMIT_WAIT


def _request(method, path, body=None, params=None, tags=None, timeout=config.SHORT_TIMEOUT, model=None):
    """One request with the run's key, the labels, and the error table of PLAN.md 4.8."""
    all_tags = {"app": "darwin", "run": _run_id, **(tags or {})}
    headers = {
        "Authorization": "Bearer " + config.OTARI_API_KEY,
        "User-Agent": "darwin/0.1",
        "Otari-Conversation-Id": "darwin-" + _run_id,
        "Otari-Tags": ",".join(f"{quote(str(k), safe='')}={quote(str(v), safe='')}" for k, v in all_tags.items()),
    }
    what = f"{method} {path}" + (f" for {model}" if model else "")
    rate_limit_tries = 0
    tried_again = False
    while True:
        try:
            answer = _client.request(method, config.OTARI_BASE_URL + path, json=body, params=params,
                                     headers=headers, timeout=timeout)
        except httpx.TransportError as problem:  # no answer in time, or no connection
            if tried_again:
                why = f"no answer ({type(problem).__name__})"
                raise CallFailed(f"{what}: {why}", detail=why)
            tried_again = True
            continue

        status = answer.status_code
        if status < 300:
            return answer
        code, detail = _error_parts(answer)
        message = f"{what}: status {status}" + (f", code {code}" if code else "") + f": {detail}"

        if status == 429:
            rate_limit_tries += 1
            if rate_limit_tries >= config.RATE_LIMIT_TRIES:
                raise CallFailed(message, status, code, detail)
            time.sleep(_wait_seconds(answer))
        elif status in (500, 502, 503, 504):
            if tried_again:
                raise CallFailed(message, status, code, detail)
            tried_again = True
        elif status == 403 and code == "budget_exceeded":
            raise BudgetExceeded(message, status, code, detail)
        elif status in (401, 402, 403, 404, 422, 424):
            raise SetupProblem(message, status, code, detail)
        else:
            if status == 400:
                print(f"Otari refused a request. {message}")
            raise CallFailed(message, status, code, detail)


def health():
    """True if the gateway says it is healthy."""
    return _request("GET", "/health").json().get("status") == "healthy"


def model_info(model):
    """What the gateway knows about one model, or None if it does not have it.
    A model that can be used has a "pricing" entry."""
    try:
        return _request("GET", "/models/" + model, model=model).json()
    except SetupProblem as problem:
        if problem.status == 404:
            return None
        raise


def key_budget():
    """The key's budget as Otari reports it: budgets_enforced, remaining_usd and limits."""
    return _request("GET", "/key/budget").json()


def require_cap():
    """Raise SetupProblem unless the key in use has a spending cap.
    Returns the cap: a dictionary with limit_usd, used_usd and remaining_usd."""
    global _cap_seen
    try:
        budget = key_budget()
    except SetupProblem as problem:
        if problem.status == 403:  # the key may not even read its own budget
            raise SetupProblem(NO_CAP, problem.status, problem.code, problem.detail)
        raise
    caps = [x for x in budget.get("limits", []) if x.get("scope") == "api_token" and x.get("limit_usd") is not None]
    if budget.get("budgets_enforced") is not True or not caps:
        raise SetupProblem(NO_CAP)
    _cap_seen = True
    return caps[0]


def _cap_guard():
    """No paid call without a cap. Asks the gateway once per program run."""
    with _cap_lock:
        if not _cap_seen:
            require_cap()


def chat(model, messages, max_tokens, timeout=config.PANEL_TIMEOUT, tags=None, **settings):
    """One chat call. max_tokens must be given. settings are more body fields, such as
    temperature=0 or reasoning_effort="low".
    Returns text, cost_usd, headers, seconds and raw (the whole answer)."""
    _cap_guard()
    body = {"model": model, "messages": messages, "max_tokens": max_tokens,
            "session_label": "darwin-" + _run_id, **settings}
    started = time.monotonic()
    answer = _request("POST", "/chat/completions", body=body, tags=tags, timeout=timeout, model=model)
    raw = answer.json()
    message = (raw.get("choices") or [{}])[0].get("message") or {}
    return {
        "text": message.get("content") or "",
        "cost_usd": float((raw.get("usage") or {}).get("cost_usd") or 0),
        "headers": answer.headers,
        "seconds": time.monotonic() - started,
        "raw": raw,
    }


def search(query, max_results, max_tokens_per_page=None, domains=None, tags=None):
    """One web search with the tool named tavily. Returns the gateway's answer
    (results with title, url, snippet) plus cost_usd."""
    _cap_guard()
    body = {"query": query, "max_results": max_results}
    if max_tokens_per_page:
        body["max_tokens_per_page"] = max_tokens_per_page
    if domains:
        body["search_domain_filter"] = domains
    answer = _request("POST", "/search/tavily", body=body, tags=tags)
    return {**answer.json(), "cost_usd": float(answer.headers.get("Otari-Cost-USD") or 0)}


def fetch(url, max_chars, tags=None):
    """Read one web page with Otari's built-in reader. Returns the gateway's answer
    (text, final_url, truncated, content_type) plus cost_usd."""
    _cap_guard()
    answer = _request("POST", "/fetch", body={"url": url, "max_chars": max_chars}, tags=tags)
    return {**answer.json(), "cost_usd": float(answer.headers.get("Otari-Cost-USD") or 0)}


def search_catalog():
    """The search tools this key may use, each with its price_per_call."""
    return _request("GET", "/search-tools/catalog").json()["data"]


def usage_summary(**params):
    """This key's usage in this run. params are more query fields, for example
    group_by_tag="role", dimensions="none"."""
    return _request("GET", "/key/usage/summary", params={"tag": "run:" + _run_id, **params}).json()
