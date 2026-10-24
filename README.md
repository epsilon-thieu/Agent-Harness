# Agent Harness: ReAct Agents for Code Repair and Chess

A from-scratch implementation of an LLM agent harness based on the
[ReAct](https://arxiv.org/abs/2210.03629) framework. The harness lets a language
model observe and act in an environment through tool calls: it reasons, calls a
tool, reads the result, and repeats until the task is done.

The same generic loop powers two different agents:

- **CodeAgent**: works in a sandboxed Linux terminal to fix real software issues
  (a bug in a chess web app and a Django issue from SWE-bench) and submits a git patch.
- **ChessAgent**: plays chess against a rule-based bot through an HTTP API, and can
  write Python programs that search for a good move before playing it.

## Architecture

```text
src/assignment/
├── agent/
│   ├── base.py          # ReAct loop and context compaction
│   ├── code_agent.py    # terminal agent for fixing code
│   ├── chess_agent.py   # chess-playing agent
│   ├── chess_tools.py
│   └── tools.py
├── env.py               # Modal sandbox
├── chess_sandbox.py
├── cli.py
└── prompts.py
tasks/
artifacts/
```

### Key components

- **ReAct loop**: build prompt, query the model, execute tool calls, append linked
  observations, repeat. Handles malformed arguments, unknown tools, text-only
  replies, and a step limit.
- **Context compaction**: when the prompt exceeds a token threshold, old steps are
  summarized by the model into a working memory, while the system/task messages
  and the most recent tool step stay verbatim.
- **Skills**: reusable instructions in `SKILL.md` files. Only a short description
  is in the prompt; the model loads the full text with `invoke_skill`.
- **Chess tools**: `play_move` commits a move; `simulate_move` explores a position
  without changing the game; `run_python` runs model-written search code in the
  sandbox, calling those two tools as ordinary functions.

## Setup

Requirements: [uv](https://docs.astral.sh/uv/), a [Modal](https://modal.com/) account,
and an OpenAI-compatible LLM endpoint.

```bash
uv sync
uv run modal setup
cp .env.example .env     # then fill in OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL
make doctor              # validates configuration without starting a sandbox
```


## Usage

```bash
make test                                  

#fix the chess app bug
make run-code-agent
make check-part1

#SWE-bench task with context compaction
make run-swebench-agent INSTANCE=django__django-15368
make check-swebench INSTANCE=django__django-15368

#play chess
make run-chess-agent
uv run assignment-play-chess --patch artifacts/fix.patch \
  --programmatic-tools --skills-path tasks/chess-skills \
  --trajectory artifacts/part3-python-skill-trajectory.json
```

Runs that use Modal or an LLM API are billable. Check for leftover sandboxes with
`uv run modal container list`.

## Experiments

- **Compaction vs. full context**: token usage comparison on a SWE-bench task
  (`artifacts/token-usage-analysis.md`).
- **Observation ablation**: chess agent with and without legal moves in the
  observation, across two models (`artifacts/observation-experiment.md`).

## Notes

- Model-written code never runs in the agent process; it runs inside the sandbox.
- The agent loop is domain-agnostic: adding a new domain means supplying a system
  prompt, tools, and a tool executor.