import ast
import operator

from ddgs import DDGS
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langchain.agents import create_agent


@tool
def web_search(query: str) -> str:
    """Search the web with DuckDuckGo and return the top 3 results.

    Use this when the user asks you to look something up online, or asks a
    factual question that needs outside information.
    """
    try:
        results = DDGS().text(query, max_results=3)
    except Exception as e:
        return f"Search failed: {e}"
    if not results:
        return "No results found."
    blocks = []
    for i, r in enumerate(results, 1):
        blocks.append(f"{i}. {r.get('title', '')}\n{r.get('body', '')}\n{r.get('href', '')}")
    return "\n\n".join(blocks)


@tool
def read_file(path: str) -> str:
    """Read a local text file and return its contents. The input is the file path."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Could not read file: {e}"


# arithmetic for the calculator, done with ast instead of eval() so a tool call
# can't run arbitrary python. only these ops are allowed, anything else raises.
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_node(node):
    """Evaluate a parsed expression node, allowing only numbers, the operators
    above, unary +/-, and parentheses (grouping needs no special handling)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("only numbers and + - * / // % ** are allowed")


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic math expression, e.g. '12 * (3 + 4)'."""
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_eval_node(tree.body))
    except Exception as e:
        return f"Could not evaluate '{expression}': {e}"


SYSTEM_PROMPT = (
    "You are a helpful assistant with three tools: web_search, read_file and calculator.\n"
    "- Use calculator for any arithmetic, even simple sums.\n"
    "- Use read_file whenever the user refers to a file path.\n"
    "- Use web_search when the user asks you to search the web, or asks a factual "
    "question that needs outside information. Do not answer those from memory.\n"
    "- If no tool fits (for example a question about your own capabilities), just "
    "answer directly without calling a tool.\n"
    "- If a tool reports an error, say so plainly; never invent the result.\n"
    "Always give a short, direct final answer."
)


def build_agent(model_name="openai/gpt-oss-120b"):
    """Build the agent for a given Groq model. Reads GROQ_API_KEY from the environment."""
    model = init_chat_model(f"groq:{model_name}", temperature=0)
    return create_agent(model=model, tools=[web_search, read_file, calculator],
                        system_prompt=SYSTEM_PROMPT)


def _content_to_text(content):
    """The final content is usually a string, but some models return a list of
    content blocks. Join the text parts so the substring checks don't crash."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(block.get("text", ""))
            else:
                parts.append(getattr(block, "text", "") or "")
        return "".join(parts)
    return str(content)


def run_agent(agent, question: str):
    """Run the agent on one question.

    Returns (answer, tools_used, tokens):
      - answer     : the final answer text
      - tools_used : list of tool names the agent actually called
      - tokens     : {"input", "output", "total"} summed over the whole run
    """
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    messages = result["messages"]

    tools_used = []
    tokens = {"input": 0, "output": 0, "total": 0}
    for m in messages:
        for call in getattr(m, "tool_calls", None) or []:
            tools_used.append(call["name"])
        usage = getattr(m, "usage_metadata", None)
        if usage:
            tokens["input"] += usage.get("input_tokens", 0)
            tokens["output"] += usage.get("output_tokens", 0)
            tokens["total"] += usage.get("total_tokens", 0)

    answer = _content_to_text(messages[-1].content)
    return answer, tools_used, tokens


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    a = build_agent()
    ans, tools, tokens = run_agent(a, "What is 47 * 89?")
    print("tools used:", tools)
    print("tokens:", tokens)
    print("answer:", ans)
