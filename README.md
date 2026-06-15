# tool-agent-eval

A LangGraph agent with three real tools — **web search**, **file reading**, and a
**calculator** — plus an evaluation harness that measures whether the agent routes to
the right tool(s), returns the right answer, and at what cost (latency + tokens). It runs
on the same LangGraph + Groq stack as my live support-agent demo.

**Live agent (same stack):** https://huggingface.co/spaces/agarwalkush/Agentic_chat_support_system

## Why this exists

Most "I built an agent" projects have no numbers behind them. This one does. `eval.py`
runs **15 fixed test cases against two models** and, for each case, checks two things —
*did the agent call the tool(s) it was supposed to?* and *does the final answer contain
the expected text?* — while recording latency and token usage. The cases aren't all easy:
they include a question that should use **no tool**, a **missing-file** case where the
agent must admit failure instead of inventing contents, a **routing-discipline** case
(trivial arithmetic it could answer from memory but should still send to the calculator),
and two **multi-tool chaining** cases. All tables below are from a real run on
**2026-06-15**, not mock-ups — re-run `python eval.py` to regenerate them.

## Results — model comparison

| Model | Passed | Avg latency | Total tokens | Est. cost* |
|-------|--------|-------------|--------------|------------|
| `openai/gpt-oss-120b` | **15 / 15** | 2282 ms | 14,500 | $0.0027 |
| `llama-3.3-70b-versatile` | **9 / 15** | 716 ms | 10,335 | $0.0062 |

\* *Estimated only.* Token counts are real (from the models' usage metadata); the dollar
figure multiplies them by per-token prices hardcoded at the top of `eval.py`, pulled from
third-party trackers on 2026-06-15. **Verify against https://groq.com/pricing before
quoting.** Note `llama`'s lower average latency is misleading — see the failure analysis.

### `openai/gpt-oss-120b`

| # | Test case | Expected tool | Tool used | Result | Latency (ms) | Tokens |
|---|-----------|---------------|-----------|--------|--------------|--------|
| 1 | What is 47 * 89? | `calculator` | `calculator` | PASS | 1690 | 790 |
| 2 | What is 987 times 654? | `calculator` | `calculator` | PASS | 689 | 798 |
| 3 | Calculate 1024 divided by 8. | `calculator` | `calculator` | PASS | 672 | 796 |
| 4 | What is 3125 plus 6875? | `calculator` | `calculator` | PASS | 953 | 804 |
| 5 | Read the file sample_data/company_faq.txt and tell me who founded the company. | `read_file` | `read_file` | PASS | 1138 | 901 |
| 6 | According to sample_data/company_faq.txt, how much does the Pro plan cost? | `read_file` | `read_file` | PASS | 1509 | 945 |
| 7 | What support email is listed in sample_data/company_faq.txt? | `read_file` | `read_file` | PASS | 1199 | 894 |
| 8 | Search the web: who wrote the novel Pride and Prejudice? | `web_search` | `web_search` | PASS | 4934 | 1067 |
| 9 | Search the web for the capital city of Japan. | `web_search` | `web_search` | PASS | 5861 | 1007 |
| 10 | Search online: in what year did Apollo 11 land on the moon? | `web_search` | `web_search` | PASS | 3216 | 1077 |
| 11 | Hi, what tools do you have access to? | `(none)` | `(none)` | PASS | 714 | 488 |
| 12 | Read sample_data/does_not_exist.txt and summarize it. | `read_file` | `read_file` | PASS | 1150 | 871 |
| 13 | What is 2 + 2? | `calculator` | `calculator` | PASS | 1458 | 788 |
| 14 | Read sample_data/company_faq.txt, find the Pro plan price, and multiply it by 12. | `read_file+calculator` | `read_file, calculator` | PASS | 2286 | 1477 |
| 15 | Search the web for the year Apollo 11 landed on the moon, then add 100 to that year. | `web_search+calculator` | `web_search, calculator` | PASS | 6763 | 1797 |

**15 / 15 passed — avg latency 2282 ms — 14,500 tokens — est. cost $0.0027**

### `llama-3.3-70b-versatile`

| # | Test case | Expected tool | Tool used | Result | Latency (ms) | Tokens |
|---|-----------|---------------|-----------|--------|--------------|--------|
| 1 | What is 47 * 89? | `calculator` | `calculator` | PASS | 1518 | 1172 |
| 2 | What is 987 times 654? | `calculator` | `calculator` | PASS | 558 | 1178 |
| 3 | Calculate 1024 divided by 8. | `calculator` | `calculator` | PASS | 1469 | 1184 |
| 4 | What is 3125 plus 6875? | `calculator` | `calculator` | PASS | 528 | 1180 |
| 5 | Read the file sample_data/company_faq.txt and tell me who founded the company. | `read_file` | `read_file` | PASS | 441 | 1277 |
| 6 | According to sample_data/company_faq.txt, how much does the Pro plan cost? | `read_file` | `read_file` | PASS | 1795 | 1272 |
| 7 | What support email is listed in sample_data/company_faq.txt? | `read_file` | `read_file` | PASS | 1308 | 1274 |
| 8 | Search the web: who wrote the novel Pride and Prejudice? | `web_search` | `(none)` | FAIL | 632 | 0 |
| 9 | Search the web for the capital city of Japan. | `web_search` | `(none)` | FAIL | 330 | 0 |
| 10 | Search online: in what year did Apollo 11 land on the moon? | `web_search` | `(none)` | FAIL | 230 | 0 |
| 11 | Hi, what tools do you have access to? | `(none)` | `(none)` | PASS | 533 | 628 |
| 12 | Read sample_data/does_not_exist.txt and summarize it. | `read_file` | `(none)` | FAIL | 339 | 0 |
| 13 | What is 2 + 2? | `calculator` | `calculator` | PASS | 407 | 1170 |
| 14 | Read sample_data/company_faq.txt, find the Pro plan price, and multiply it by 12. | `read_file+calculator` | `(none)` | FAIL | 338 | 0 |
| 15 | Search the web for the year Apollo 11 landed on the moon, then add 100 to that year. | `web_search+calculator` | `(none)` | FAIL | 321 | 0 |

**9 / 15 passed — avg latency 716 ms — 10,335 tokens — est. cost $0.0062**

## Failure analysis (run of 2026-06-15)

- **`gpt-oss-120b` — 15/15.** It used the right tool on every case: answered the
  "what tools do you have" question with **no tool call**, **owned the missing-file
  error** ("I couldn't find the file… it doesn't exist") without inventing contents,
  still called the calculator for trivial `2 + 2`, and correctly **chained**
  `read_file → calculator` and `web_search → calculator`.
- **`llama-3.3-70b-versatile` — 9/15.** It handled every calculator and standalone
  file-read case and the no-tool case, but failed all three `web_search` cases (8–10)
  and both chained cases (14–15) with a Groq **`400 "Failed to call a function"`** error:
  the model emitted a malformed tool call that Groq's function-call validator rejected.
  The missing-file case (12) hit the same error on this run, though it passed on an
  earlier one — so the error is somewhat intermittent, but `web_search` failed on every
  run.
- **Latency caveat.** `llama`'s lower average (716 ms vs 2282 ms) is misleading: its six
  failed calls returned in ~200–600 ms with **zero tokens** because they errored before
  doing any work. On the cases it actually completed, the two models are comparable;
  `gpt-oss` is slower mainly because it really performs the web searches (~3–6 s each).
- **Cost.** In this run `gpt-oss-120b` was both more reliable **and** cheaper
  (~$0.0027 vs ~$0.0062 estimated), because `llama` has a higher per-token price and
  used more tokens per successful call.

**Takeaway:** for this tool-calling workload on Groq, `openai/gpt-oss-120b` is the clear
choice; `llama-3.3-70b-versatile` is quick on simple tool calls but unreliable at
function-calling for `web_search` and multi-step tasks.

## Architecture

The agent is a single ReAct-style agent built with LangChain's `create_agent`, backed by
a Groq model at temperature 0 (the model id is a parameter — `build_agent(model_name)`).
Three plain Python functions are exposed to the model as LangChain `@tool`s: `web_search`
(DuckDuckGo top-3 results), `read_file` (reads a local file by path), and `calculator`
(safely evaluates an arithmetic expression). On each turn the model reads the user message
plus a system prompt, decides whether a tool is needed, and either calls a tool or answers
directly; any tool result is fed back into the model until it produces a final answer.
`eval.py` drives this loop over 15 fixed cases per model and inspects the returned message
history to see which tools *actually* fired and how many tokens were used — so the score
reflects real routing behaviour, not just the final text.

```
user question
      │
      ▼
┌────────────────┐    needs a tool?     ┌──────────────────────────────┐
│   Groq model   │ ──────────────────▶  │ web_search / read_file /      │
│ (configurable) │ ◀──────────────────  │ calculator                    │
└────────────────┘    tool result       └──────────────────────────────┘
      │ final answer
      ▼
  eval.py  →  checks tool(s) used + answer text + latency + tokens  →  per-model tables
```

## The three tools (`agent.py`)

- **`web_search(query)`** — calls DuckDuckGo via the `ddgs` package (no API key) and
  returns the top 3 results as title + snippet + link.
- **`read_file(path)`** — opens a local text file and returns its contents, or a clear
  "Could not read file" message if it fails. The test cases point it at
  `sample_data/company_faq.txt`.
- **`calculator(expression)`** — parses the expression with Python's `ast` module and
  evaluates it with a small recursive walker that allows **only** numbers and
  `+ - * / // % **`, unary minus, and parentheses. Anything else (function calls, names,
  attribute access) raises, so unlike `eval()` it can't run arbitrary code.

## How the evaluation works (`eval.py`)

Each test case is a dict with `input`, `expected_tool`, and `expected_output_contains`:

- **`expected_tool`** can be `None` (the agent should answer with *no* tool), a single
  tool name, or a **list** (a chained task — every listed tool must fire, order doesn't
  matter).
- **`expected_output_contains`** is text the final answer must include. It can be one
  string, or a **list** meaning "any one of these counts" (used for the missing-file
  case, where several honest-failure phrasings are all acceptable).

For each case the harness times the call, reads the message history to collect every tool
actually called and to sum token usage, then marks **PASS** only if the tool expectation
holds **and** the answer contains the expected text. It runs the whole suite against each
model in `MODELS` and prints one table per model plus a comparison. Matching is
whitespace-, comma- and apostrophe-insensitive, so `4,183` matches `4183` and a
curly-quote `couldn't` matches a straight-quote `couldn't`.

## Run it yourself

```bash
# 1. create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate           # macOS / Linux
# .venv\Scripts\Activate.ps1         # Windows PowerShell

# 2. install dependencies
pip install -r requirements.txt

# 3. set your Groq API key (free at https://console.groq.com)
export GROQ_API_KEY=your_key_here           # macOS / Linux
# $env:GROQ_API_KEY = "your_key_here"         # Windows PowerShell

# 4. run the evaluation
python eval.py
```

## Project layout

```
tool-agent-eval/
├── agent.py                 # the 3 tools + the agent (build_agent / run_agent)
├── eval.py                  # 15 test cases, pass/fail, latency, tokens, cost, 2 models
├── sample_data/
│   └── company_faq.txt      # the file read_file is tested against
├── requirements.txt
└── README.md
```

## Limitations / what I'd improve next

- **Web-search cases need the live internet.** They depend on DuckDuckGo returning a
  relevant snippet; if it rate-limits or changes, those cases can flake. A production
  eval would mock the search results for determinism and test the live path separately.
- **`expected_output_contains` is a substring check, not real grading.** It's good enough
  for these cases but would miss subtler correctness issues. An LLM-as-judge step would
  be the next upgrade.
- **No retry/repair for malformed tool calls.** `llama-3.3-70b`'s failures are Groq
  `400 "failed to call a function"` errors; a real system would catch those and retry or
  repair the tool call rather than giving up.
- **Cost is an estimate.** Prices are hardcoded constants that must be verified against
  current Groq pricing; caching and batch discounts aren't modelled.
- **Single run per model.** Latency and (for `llama`) pass/fail vary between runs;
  averaging several runs would give more stable numbers.

## Stack

Python · LangChain · LangGraph · Groq (`openai/gpt-oss-120b`, `llama-3.3-70b-versatile`) ·
DuckDuckGo (`ddgs`) · `ast` for the safe calculator (standard library)
