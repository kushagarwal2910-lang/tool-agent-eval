# tool-agent-eval

A small LangGraph agent with three tools (web search, reading a local file, and a calculator), plus a script that actually checks whether it works. The agent itself is nothing special. The part I care about is eval.py, which runs a fixed set of questions against two different models and records, for each one, whether the agent called the right tool and whether the answer was correct, along with how long it took and how many tokens it used.

Same Groq + LangGraph setup as my support agent space: https://huggingface.co/spaces/agarwalkush/Agentic_chat_support_system

## why I made this

I kept seeing "I built an agent" projects that had no proof the thing actually worked, so I wanted mine to keep score. eval.py runs 15 questions against two models and checks two things for each one: did it use the tool it was supposed to, and does the final answer contain the right text. It also times every call and adds up the tokens.

The questions aren't all easy, on purpose. A few are there to catch the ways agents actually break:

- one question that should not use a tool at all (just "what tools do you have")
- a question pointing at a file that does not exist, so the agent has to admit it cannot read it instead of making something up
- a "what is 2 + 2" that should still go through the calculator, to see if routing holds when the model already knows the answer
- two questions that need two tools one after the other

## what I found

I ran the whole thing three times on 2026-06-15. Short version: one model was solid, the other was not.

gpt-oss-120b passed all 15 every single run. It used no tool on the capabilities question, admitted it could not find the missing file instead of inventing an answer, still ran 2 + 2 through the calculator, and handled both two-step questions correctly. It averaged about 3.8 seconds per question (the web searches are the slow part, 4 to 12 seconds each), used roughly 15k tokens total, and cost around $0.003.

llama-3.3-70b-versatile was a mess. It passed 10, then 9, then 7 across the three runs. It was fine on the plain calculator questions, but it failed every single web search question and both of the two-step ones, and it was flaky on the file-reading ones (passing sometimes, failing others).

The interesting part is why it failed, because it was not DuckDuckGo. Every failure was the same thing: the model sent back a malformed tool call that Groq rejected with a 400 "Failed to call a function" error, before any tool even ran. You can tell because the tool used shows nothing and the token count is 0. That is different from a search actually failing. gpt-oss ran every web search all three times and found the right answer, so DuckDuckGo was fine. llama's problem was the function calling itself.

One thing that looks backwards: llama's average latency (around 700 ms) is lower than gpt-oss's, but that is misleading. Its failed calls bailed out in a couple hundred ms doing zero work, which drags the average down. On the questions it actually completed, the two are pretty close.

So for this kind of tool-calling task on Groq, gpt-oss-120b is the obvious pick.

One note on cost: the dollar figures are estimates. The token counts are real, straight from the model's usage data, but I multiply them by per-token prices I hardcoded from a pricing tracker, so check those against groq.com/pricing before trusting the exact number.

## how it works

It is one ReAct-style agent from LangChain's create_agent, running a Groq model at temperature 0. The model name is just an argument to build_agent, which is how eval.py swaps between the two models. The three tools are plain Python functions registered with the @tool decorator. Each turn, the model sees the question and a system prompt and either calls a tool or answers directly, and any tool output gets fed back in until it is done.

The key thing eval.py does is read the message history after each run to see which tools actually fired, instead of just trusting the final answer. That matters because the model could say "I calculated 4183" without ever calling the calculator, and I would not catch that if I only looked at the text.

The three tools:

- web_search: hits DuckDuckGo through the ddgs package (no API key) and returns the top 3 results.
- read_file: opens a text file and returns what is in it, or a "could not read file" message if it fails.
- calculator: this one I did carefully. Instead of using eval() (which would run any Python you hand it), it parses the expression with the ast module and walks the tree, only allowing numbers and + - * / // % **, unary minus, and parentheses. Anything else, like a function call or a variable name, raises an error, so a tool call cannot sneak real code through it.

For the eval itself, each test case is a dict with the input, the expected tool, and some text the answer has to contain. The expected tool can be None (no tool should fire), a single name, or a list (for the two-step questions, where all of them have to fire). The text check ignores whitespace, commas and apostrophes, so 4,183 matches 4183. That last bit was actually a bug I hit: gpt-oss answered one case correctly but with a curly apostrophe, and my checker marked it wrong until I normalized them.

## running it

You need a Groq API key (free at console.groq.com).

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GROQ_API_KEY=your_key_here
python eval.py
```

On Windows, activate with .venv\Scripts\Activate.ps1 and set the key with $env:GROQ_API_KEY="your_key_here".

## files

```
tool-agent-eval/
  agent.py            the 3 tools and the agent
  eval.py             the 15 test cases and the scoring
  sample_data/
    company_faq.txt   the file read_file is tested against
  requirements.txt
  README.md
```

## stuff I would fix or add next

- The web search cases need the live internet, so if DuckDuckGo rate-limits or changes, they can flake. The better way is to mock the search results for the main suite and test the live path on its own.
- The answer check is just a substring match, not real grading. It works for these cases but would miss subtler wrong answers. Adding an LLM-as-judge step would be the real fix.
- There is no retry when a model sends a malformed tool call. A real system would catch llama's 400 errors and retry or repair the call instead of giving up.
- The cost numbers are estimates, since the prices are hardcoded and do not account for caching or batch discounts.
- I only have three runs. gpt-oss was 15/15 every time, but llama moved around (10, 9, 7), and latencies bounce run to run, so more runs would tighten the numbers.

## built with

Python, LangChain, LangGraph, Groq (gpt-oss-120b and llama-3.3-70b-versatile), DuckDuckGo through ddgs, and the standard-library ast module for the calculator.