import os
import sys
import time

# windows terminal is cp1252 and chokes on some of the unicode the model returns
sys.stdout.reconfigure(encoding="utf-8")
# Run relative to this file so the sample_data/ paths always resolve.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from agent import build_agent, run_agent


# Models to compare. These are Groq model ids; init_chat_model adds the "groq:" prefix.
MODELS = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile"]

# --- ESTIMATED pricing, USD per 1,000,000 tokens. NOT authoritative. ---
# Pulled from third-party trackers on 2026-06-15. Groq changes prices and offers
# caching/batch discounts, so VERIFY against https://groq.com/pricing before
# quoting these anywhere. Cost numbers below are only as good as these constants.
PRICING_USD_PER_M = {
    "openai/gpt-oss-120b":     {"input": 0.15, "output": 0.60},
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
}


TEST_CASES = [
    # --- calculator (no network, fully deterministic) ---
    {"input": "What is 47 * 89?",
     "expected_tool": "calculator", "expected_output_contains": "4183"},
    {"input": "What is 987 times 654?",
     "expected_tool": "calculator", "expected_output_contains": "645498"},
    {"input": "Calculate 1024 divided by 8.",
     "expected_tool": "calculator", "expected_output_contains": "128"},
    {"input": "What is 3125 plus 6875?",
     "expected_tool": "calculator", "expected_output_contains": "10000"},

    # --- read_file (reads the file in sample_data/, deterministic) ---
    {"input": "Read the file sample_data/company_faq.txt and tell me who founded the company.",
     "expected_tool": "read_file", "expected_output_contains": "Ada Lovelace"},
    {"input": "According to sample_data/company_faq.txt, how much does the Pro plan cost?",
     "expected_tool": "read_file", "expected_output_contains": "49"},
    {"input": "What support email is listed in sample_data/company_faq.txt?",
     "expected_tool": "read_file", "expected_output_contains": "support@acmesearch.io"},

    # --- web_search (live DuckDuckGo, stable-answer questions) ---
    # TODO: mock these so the suite isn't at the mercy of DuckDuckGo being up
    {"input": "Search the web: who wrote the novel Pride and Prejudice?",
     "expected_tool": "web_search", "expected_output_contains": "Austen"},
    {"input": "Search the web for the capital city of Japan.",
     "expected_tool": "web_search", "expected_output_contains": "Tokyo"},
    {"input": "Search online: in what year did Apollo 11 land on the moon?",
     "expected_tool": "web_search", "expected_output_contains": "1969"},

    # --- harder, honest cases ---
    # No tool should fire: a question about the agent's own capabilities.
    {"input": "Hi, what tools do you have access to?",
     "expected_tool": None, "expected_output_contains": "search"},
    # Missing file: read_file errors. A good answer owns the failure instead of
    # inventing contents; passing on any of these phrases means it did.
    {"input": "Read sample_data/does_not_exist.txt and summarize it.",
     "expected_tool": "read_file",
     "expected_output_contains": ["could not", "couldn't", "not found", "no such file",
                                  "does not exist", "doesn't exist", "unable to"]},
    # Routing discipline: trivial enough to answer from memory, but the system
    # prompt says always use the calculator. Tests whether routing holds.
    {"input": "What is 2 + 2?",
     "expected_tool": "calculator", "expected_output_contains": "4"},

    # --- multi-tool chaining (expected_tool is a list; ALL must fire) ---
    {"input": "Read sample_data/company_faq.txt, find the Pro plan price, and multiply it by 12.",
     "expected_tool": ["read_file", "calculator"], "expected_output_contains": "588"},
    # network-dependent: needs a live web_search result (Apollo 11 = 1969) then 1969 + 100.
    {"input": "Search the web for the year Apollo 11 landed on the moon, then add 100 to that year.",
     "expected_tool": ["web_search", "calculator"], "expected_output_contains": "2069"},
]


def normalize(text):
    """Lowercase; drop commas, apostrophes and whitespace so '4,183' matches
    '4183' and a curly-quote "couldn't" matches a straight-quote "couldn't"."""
    text = text.lower().replace(",", "").replace("'", "").replace("’", "")
    return "".join(text.split())


def contains(answer, needle):
    return normalize(needle) in normalize(answer)


def tool_matches(expected, tools_used):
    """expected can be None (no tool fired), a single name, or a list (all must fire)."""
    if expected is None:
        return len(tools_used) == 0
    if isinstance(expected, list):
        return all(name in tools_used for name in expected)
    return expected in tools_used


def output_matches(expected, answer):
    """expected can be a single substring or a list of substrings (any one is enough)."""
    needles = expected if isinstance(expected, list) else [expected]
    return any(contains(answer, n) for n in needles)


def expected_tool_label(expected):
    if expected is None:
        return "(none)"
    if isinstance(expected, list):
        return "+".join(expected)
    return expected


def estimate_cost_usd(model_name, total_input, total_output):
    """ESTIMATED cost from the constants at the top of the file. Not authoritative."""
    price = PRICING_USD_PER_M.get(model_name)
    if not price:
        return None
    return (total_input / 1_000_000) * price["input"] + (total_output / 1_000_000) * price["output"]


def summarise(rows):
    return {
        "passed": sum(r["passed"] for r in rows),
        "total": len(rows),
        "avg_latency": int(sum(r["latency_ms"] for r in rows) / len(rows)) if rows else 0,
        "total_input": sum(r["tokens"]["input"] for r in rows),
        "total_output": sum(r["tokens"]["output"] for r in rows),
        "total_tokens": sum(r["tokens"]["total"] for r in rows),
    }


def run_suite(model_name):
    """Run all test cases against one model. Returns a list of result rows."""
    print(f"\n>>> {len(TEST_CASES)} cases on {model_name}\n")
    try:
        agent = build_agent(model_name)
    except Exception as e:
        print(f"!! could not build agent for {model_name}: {e}")
        return []

    rows = []
    for i, case in enumerate(TEST_CASES, 1):
        start = time.time()
        try:
            answer, tools_used, tokens = run_agent(agent, case["input"])
            error = None
        except Exception as e:
            answer, tools_used = "", []
            tokens = {"input": 0, "output": 0, "total": 0}
            error = str(e)
        latency_ms = int((time.time() - start) * 1000)

        if error:
            passed = False
        else:
            passed = (tool_matches(case["expected_tool"], tools_used)
                      and output_matches(case["expected_output_contains"], answer))

        rows.append({
            "n": i,
            "input": case["input"],
            "expected_tool": expected_tool_label(case["expected_tool"]),
            "tool_used": ", ".join(tools_used) if tools_used else "(none)",
            "passed": passed,
            "latency_ms": latency_ms,
            "tokens": tokens,
            "error": error,
        })

        mark = "PASS" if passed else "FAIL"
        print(f"[{i:>2}] {mark}  {rows[-1]['tool_used']:<24} {latency_ms:>6} ms  "
              f"{tokens['total']:>5} tok  {case['input'][:50]}")
        if error:
            print(f"      ERROR: {error[:160]}")
        elif not passed:
            print(f"      wanted tool '{expected_tool_label(case['expected_tool'])}', "
                  f"got [{rows[-1]['tool_used']}]; answer should contain "
                  f"{case['expected_output_contains']!r}")
            print(f"      answer was: {answer[:200]}")

        time.sleep(1)  # be gentle with the free DuckDuckGo endpoint

    return rows


def print_console_table(model_name, rows):
    if not rows:
        print(f"\n(no results for {model_name})")
        return
    s = summarise(rows)
    cost = estimate_cost_usd(model_name, s["total_input"], s["total_output"])
    cost_str = f"${cost:.6f}" if cost is not None else "n/a"
    print("\n" + "=" * 94)
    print(f"RESULTS — {model_name}")
    print("=" * 94)
    print(f"{'#':>2}  {'Test case':<46} {'Tool used':<22} {'Res':<4} {'ms':>6} {'tok':>6}")
    print("-" * 94)
    for r in rows:
        q = r["input"] if len(r["input"]) <= 46 else r["input"][:43] + "..."
        print(f"{r['n']:>2}  {q:<46} {r['tool_used']:<22} "
              f"{'PASS' if r['passed'] else 'FAIL':<4} {r['latency_ms']:>6} {r['tokens']['total']:>6}")
    print("-" * 94)
    print(f"{s['passed']}/{s['total']} passed  |  avg latency {s['avg_latency']} ms  |  "
          f"total tokens {s['total_tokens']}  |  est. cost {cost_str}")
    print("=" * 94)


def print_markdown_table(model_name, rows):
    """Print a Markdown table you can paste straight into the README."""
    if not rows:
        return
    s = summarise(rows)
    cost = estimate_cost_usd(model_name, s["total_input"], s["total_output"])
    cost_str = f"${cost:.6f}" if cost is not None else "n/a"
    print(f"\n--- Markdown for README — {model_name} ---\n")
    print(f"### `{model_name}`\n")
    print("| # | Test case | Expected tool | Tool used | Result | Latency (ms) | Tokens |")
    print("|---|-----------|---------------|-----------|--------|--------------|--------|")
    for r in rows:
        result = "PASS" if r["passed"] else "FAIL"
        print(f"| {r['n']} | {r['input']} | `{r['expected_tool']}` | `{r['tool_used']}` | "
              f"{result} | {r['latency_ms']} | {r['tokens']['total']} |")
    print(f"\n**{s['passed']}/{s['total']} passed — avg latency {s['avg_latency']} ms — "
          f"{s['total_tokens']} tokens — est. cost {cost_str} (estimated, unverified pricing)**")


def print_comparison(all_results):
    print("\n" + "=" * 94)
    print("MODEL COMPARISON")
    print("=" * 94)
    print(f"{'Model':<28} {'Passed':<10} {'Avg ms':<10} {'Tokens':<10} {'Est. cost':<12}")
    print("-" * 94)
    for model, rows in all_results.items():
        if not rows:
            print(f"{model:<28} (no results)")
            continue
        s = summarise(rows)
        cost = estimate_cost_usd(model, s["total_input"], s["total_output"])
        cost_str = f"${cost:.6f}" if cost is not None else "n/a"
        passed_str = f"{s['passed']}/{s['total']}"
        print(f"{model:<28} {passed_str:<10} {s['avg_latency']:<10} "
              f"{s['total_tokens']:<10} {cost_str:<12}")
    print("=" * 94)
    print("Cost is ESTIMATED from unverified per-token constants — see top of eval.py.")


if __name__ == "__main__":
    all_results = {}
    for model in MODELS:
        rows = run_suite(model)
        all_results[model] = rows
        print_console_table(model, rows)
    for model in MODELS:
        print_markdown_table(model, all_results[model])
    print_comparison(all_results)
