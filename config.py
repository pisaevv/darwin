"""Every setting in one place. Later steps add their own settings here."""
import os
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(ENV_PATH, override=True)  # .env wins over the shell (PLAN.md section 3, point 1)

OTARI_BASE_URL = os.environ.get("OTARI_BASE_URL", "").rstrip("/")
OTARI_API_KEY = os.environ.get("OTARI_API_KEY", "")

# Models (PLAN.md 4.3). The "nebius:" prefix pins a model to Nebius.
PANEL = [
    "nebius:openai/gpt-oss-120b",
    "nebius:google/gemma-3-27b-it",
    "nebius:Qwen/Qwen3-235B-A22B-Instruct-2507",
    "nebius:zai-org/GLM-5.3-Flash",
    "nebius:MiniMaxAI/MiniMax-M3.1-Flash",
    "nebius:deepseek-ai/DeepSeek-V4.1-Flash-1017",
]
RESERVES = [
    "nebius:nvidia/Nemotron-3_5-Lightning",
    "nebius:thinkingmachines/Inkling-2-Small",
    "nebius:reflection/beam",
    "nebius:Qwen/Qwen3-30B-A3B-Instruct-2507",
]
REWRITER = "nebius:moonshotai/Kimi-K3.1-Pro"
REWRITER_RESERVE = "nebius:zai-org/GLM-5.3"
CHECKER = "nebius:deepseek-ai/DeepSeek-V4-Pro-0813"
CHECKER_RESERVE = "nebius:zai-org/GLM-5.3"

MIN_PANEL_MODELS = 5
MIN_PANEL_MAKERS = 4

REQUESTS_IN_FLIGHT = 12
PANEL_MAX_TOKENS = 600

# Time limits, in seconds
PANEL_TIMEOUT = 120
REWRITER_TIMEOUT = 300
SHORT_TIMEOUT = 60  # test calls, search, fetch

# When the gateway answers 429 (too many requests)
RATE_LIMIT_TRIES = 3
RATE_LIMIT_WAIT = 5  # seconds, when the answer has no Retry-After

TAVILY_PRICE = 0.008  # dollars per search

# Research (Step 2, research.py)
COMPETITOR_PAGES = 5
FEWEST_COMPETITOR_PAGES = 4  # with fewer, research.py writes nothing
SPARE_PAGES = 2
CANDIDATES_TO_ASK = 10  # products the model is asked to list
PAGE_MIN_WORDS = 150
PAGE_MAX_WORDS = 600
SEARCH_RESULTS = 8  # the four main searches: results each
SEARCH_TOKENS = 400  # and tokens per result
FALLBACK_RESULTS = 5  # the search on one product's own site, when its page cannot be fetched
FALLBACK_TOKENS = 1500
FETCH_MAX_CHARS = 30000
FACTS_MIN = 15
FACTS_MAX = 40
FACTS_SOURCE_WORDS = 3000  # most words of one source page given to the facts call
RESEARCH_MAX_TOKENS = 4000  # for the two model calls; thinking counts against it
# Sites shared by many products. A page there is not "the product's own website".
SHARED_SITES = [
    "github.com", "github.io", "gitlab.com", "pypi.org", "npmjs.com", "huggingface.co",
    "readthedocs.io", "medium.com", "substack.com", "reddit.com", "wikipedia.org",
    "youtube.com", "linkedin.com", "x.com", "twitter.com", "g2.com", "producthunt.com",
]
