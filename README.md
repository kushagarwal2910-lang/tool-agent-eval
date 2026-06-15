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
and two **multi-tool chaining** cases. Numbers are from **one representative run of three**
(all run on **2026-06-15**); per-case results were consistent across the three runs except
where the failure analysis notes otherwise. Nothing here is a mock-up — re-run
`python eval.py` to regenerate the numbers.

## Results — model comparison

| Model | Passed | Avg latency | Total tokens | Est. cost* |
|-------|--------|-------------|--------------|------------|
| `openai/gpt-oss-120b` | **15 / 15** | 3826 ms | 15,344 | $0.0029 |
| `llama-3.3-70b-versatile` | **9 / 15** | 704 ms | 10,275 | $0.0061 |

Across the three runs the pass counts were **gpt-oss-120b 15 / 15 / 15** (rock-solid) and
**llama-3.3-70b-versatile 10 / 9 / 7** — see the failure analysis for which cases are
consistent vs intermittent.

\* *Estimated only.* Token counts are real (from the models' usage metadata); the dollar
figure multiplies them by per-token prices hardcoded at the top of `eval.py`, pulled from
third-party trackers on 2026-06-15. **Verify against https://groq.com/pricing before
quoting.** Note `llama`'s lower average latency is misleading — see the failure analysis.

### `openai/gpt-oss-120b`

| # | Test case | Expected tool | Tool used | Result | Latency (ms) | Tokens |
|---|-----------|---------------|-----------|--------|--------------|--------|
| 1 | What is 47 * 89? | `calculator` | `calculator` | PASS | 1602 | 790 |
| 2 | What is 987 times 654? | `calculator` | `calculator` | PASS | 3806 | 798 |
| 3 | Calculate 1024 divided by 8. | `calculator` | `calculator` | PASS | 838 | 796 |
| 4 | What is 3125 plus 6875? | `calculator` | `calculator` | PASS | 1094 | 804 |
| 5 | Read the file sample_data/company_faq.txt and tell me who founded the company. | `read_file` | `read_file` | PASS | 1512 | 901 |
| 6 | According to sample_data/company_faq.txt, how much does the Pro plan cost? | `read_file` | `read_file` | PASS | 1045 | 898 |
| 7 | What support email is listed in sample_data/company_faq.txt? | `read_file` | `read_file` | PASS | 4735 | 894 |
| 8 | Search the web: who wrote the novel Pride and Prejudice? | `web_search` | `web_search, web_search` | PASS | 10811 | 2030 |
| 9 | Search the web for the capital city of Japan. | `web_search` | `web_search` | PASS | 11967 | 1007 |
| 10 | Search online: in what year did Apollo 11 land on the moon? | `web_search` | `web_search` | PASS | 4097 | 1062 |
| 11 | Hi, what tools do you have access to? | `(none)` | `(none)` | PASS | 1095 | 488 |
| 12 | Read sample_data/does_not_exist.txt and summarize it. | `read_file` | `read_file` | PASS | 1012 | 871 |
| 13 | What is 2 + 2? | `calculator` | `calculator` | PASS | 1149 | 788 |
| 14 | Read sample_data/company_faq.txt, find the Pro plan price, and multiply it by 12. | `read_file+calculator` | `read_file, calculator` | PASS | 4729 | 1477 |
| 15 | Search the web for the year Apollo 11 landed on the moon, then add 100 to that year. | `web_search+calculator` | `web_search, calculator` | PASS | 7909 | 1740 |

**15 / 15 passed — avg latency 3826 ms — 15,344 tokens — est. cost $0.0029**

### `llama-3.3-70b-versatile`

| # | Test case | Expected tool | Tool used | Result | Latency (ms) | Tokens |
|---|-----------|---------------|-----------|--------|--------------|--------|
| 1 | What is 47 * 89? | `calculator` | `calculator` | PASS | 1139 | 1172 |
| 2 | What is 987 times 654? | `calculator` | `calculator` | PASS | 637 | 1178 |
| 3 | Calculate 1024 divided by 8. | `calculator` | `calculator` | PASS | 1044 | 1184 |
| 4 | What is 3125 plus 6875? | `calculator` | `calculator` | PASS | 596 | 1180 |
| 5 | Read the file sample_data/company_faq.txt and tell me who founded the company. | `read_file` | `(none)` | FAIL | 783 | 0 |
| 6 | According to sample_data/company_faq.txt, how much does the Pro plan cost? | `read_file` | `read_file` | PASS | 839 | 1272 |
| 7 | What support email is listed in sample_data/company_faq.txt? | `read_file` | `read_file` | PASS | 762 | 1274 |
| 8 | Search the web: who wrote the novel Pride and Prejudice? | `web_search` | `(none)` | FAIL | 307 | 0 |
| 9 | Search the web for the capital city of Japan. | `web_search` | `(none)` | FAIL | 480 | 0 |
| 10 | Search online: in what year did Apollo 11 land on the moon? | `web_search` | `(none)` | FAIL | 487 | 0 |
| 11 | Hi, what tools do you have access to? | `(none)` | `(none)` | PASS | 368 | 628 |
| 12 | Read sample_data/does_not_exist.txt and summarize it. | `read_file` | `read_file` | PASS | 772 | 1217 |
| 13 | What is 2 + 2? | `calculator` | `calculator` | PASS | 1278 | 1170 |
| 14 | Read sample_data/company_faq.txt, find the Pro plan price, and multiply it by 12. | `read_file+calculator` | `(none)` | FAIL | 535 | 0 |
| 15 | Search the web for the year Apollo 11 landed on the moon, then add 100 to that year. | `web_search+calculator` | `(none)` | FAIL | 542 | 0 |

**9 / 15 passed — avg latency 704 ms — 10,275 tokens — est. cost $0.0061**

## Failure analysis (3 runs, 2026-06-15)

I ran the full suite three times. Pass counts: `gpt-oss-120b` **15 / 15** every run;
`llama-3.3-70b-versatile` **10 / 9 / 7**. Classifying each case by how often it passed:

- **`gpt-oss-120b` — consistent 15/15 (45/45 case-runs).** It used the right tool on every
  case, every run: answered "what tools do you have" with **no tool call**, **owned the
  missing-file error** ("I couldn't find the file… it doesn't exist") without inventing
  contents, still called the calculator for trivial `2 + 2`, and correctly **chained**
  `read_file → calculator` and `web_search → calculator`.
- **`llama-3.3-70b-versatile` — mixed:**
  - *Consistent pass (3/3):* the four calculator cases (1–4), the `2 + 2` routing case
    (13), and the no-tool case (11).
  - *Consistent fail (0/3):* all three `web_search` cases (8, 9, 10) and the
    `web_search → calculator` chain (15).
  - *Intermittent:* the three `read_file` cases (5 passed 1/3; 6 and 7 passed 2/3), the
    missing-file case (12, passed 2/3), and the `read_file → calculator` chain (14, passed
    1/3). Its pass rate also drifted down across the three runs (10 → 9 → 7).
- **Every llama failure had the same cause — and it is *not* DuckDuckGo.** All 19 failed
  case-runs returned a Groq **`400 "Failed to call a function"`** error: the model emitted
  a malformed tool call that Groq's validator rejected before any tool ran (tool used =
  `(none)`, 0 tokens). That is a different failure from a search problem (where `web_search`
  *runs* but DuckDuckGo returns nothing or rate-limits). **No case failed due to
  DuckDuckGo** in any run — `gpt-oss` completed every `web_search` (cases 8, 9, 10, 15) all
  three times and found the expected text each time. So llama's web failures are a
  function-calling problem, not a search problem.
- **Latency caveat.** `llama`'s lower average (704 ms vs 3826 ms) is misleading: its failed
  calls returned in ~200–600 ms with **zero tokens** because they errored before doing any
  work. On the cases it actually completed, the two models are comparable; `gpt-oss` is
  slower mainly because it really performs the web searches (~4–12 s each).
- **Cost.** `gpt-oss-120b` was both more reliable **and** cheaper in every run (~$0.0029
  vs ~$0.0061 estimated for the representative run), because `llama` has a higher per-token
  price and uses more tokens per successful call.

**Takeaway:** for this tool-calling workload on Groq, `openai/gpt-oss-120b` is the clear
choice — it passed all 15 cases on all three runs. `llama-3.3-70b-versatile` is fine for
plain calculator calls but **consistently fails every `web_search` case** and is
**intermittently unreliable** on `read_file` and multi-step chains (7–10 / 15 across runs),
with every failure being a Groq malformed-function-call error.

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
- **Results confirmed across three runs.** `gpt-oss-120b` passed 15/15 on every run;
  `llama`'s pass count varied (10 / 9 / 7) with intermittent `read_file`/chain failures,
  as detailed above. Latencies still vary run-to-run, so averaging more runs would tighten
  the numbers further.

## Stack

Python · LangChain · LangGraph · Groq (`openai/gpt-oss-120b`, `llama-3.3-70b-versatile`) ·
DuckDuckGo (`ddgs`) · `ast` for the safe calculator (standard library)
