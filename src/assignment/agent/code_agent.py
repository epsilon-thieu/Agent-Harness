"""The Part 1 coding agent: fix a software issue and submit a git patch."""

from __future__ import annotations

import json
from typing import Any

from assignment.agent.base import (
    DEFAULT_COMPACTION_KEEP_RECENT_STEPS,
    DEFAULT_COMPACTION_MAX_TOKENS,
    Agent,
    format_tool_output,
)
from assignment.agent.tools import EXECUTE_TOOL, SEND_MESSAGE_TOOL
from assignment.env import Environment

class CodeAgent(Agent):
    """An agent that fixes a software issue and submits a git patch."""

    def __init__(
        self,
        task: str,
        environment: Environment,
        model: str | None = None,
        logs_save_path: str | None = None,
        step_limit: int = 100,
        skills_path: str | None = None,
        auto_stop_environment: bool = True,
        compact_threshold_tokens: int | None = None,
        compaction_keep_recent_steps: int = DEFAULT_COMPACTION_KEEP_RECENT_STEPS,
        compaction_max_tokens: int = DEFAULT_COMPACTION_MAX_TOKENS,
    ):
        super().__init__(
            environment=environment,
            model=model,
            logs_save_path=logs_save_path,
            step_limit=step_limit,
            skills_path=skills_path,
            auto_stop_environment=auto_stop_environment,
            compact_threshold_tokens=compact_threshold_tokens,
            compaction_keep_recent_steps=compaction_keep_recent_steps,
            compaction_max_tokens=compaction_max_tokens,
        )
        self.task = task
        self.submitted_patch = ""

        # TODO(Part 1.3): Make the `execute` and `send_message` tools available
        self.tools.extend([EXECUTE_TOOL, SEND_MESSAGE_TOOL])

        info = {
            "machine": self.env.machine,
            "release": self.env.release,
            "system": self.env.system,
            "version": self.env.version,
        }
        parts = [
            "You are an expert software engineer working in a Linux terminal sandbox. "
            "The repository to fix is located at /testbed.",
            "<system_information>\n"
            f"{json.dumps(info, indent=2)}\n"
            "</system_information>",
            "Tools:\n"
            "- `execute`: run a bash command (`command`, optional `cwd`, `timeout`, `env`). "
            "Every command runs in a fresh subshell, so `cd` and exports do not carry over; "
            "use `cwd`/`env`. Files you write persist.\n"
            "- `send_message`: send a message (`summary`) to the user.",
            "Workflow: explore the repository, reproduce the issue, fix the source code "
            "(do not modify tests), then re-run your reproduction to verify the fix.",
        ]
        if self.skills:
            catalog = "\n".join(s["metadata"] for s in self.skills.values())
            parts.append(
                "Available skills:\n" + catalog + "\n\n"
                                                  "Call `invoke_skill` with a skill's name to read its full instructions."
            )
        self.system_prompt = "\n\n".join(parts)

        self.task_prompt = (
            "Resolve the following issue in the repository at /testbed.\n\n"
            f"<issue>\n{self.task}\n</issue>"
        )


    def execute_tool_calls(self, tool_calls):
        results = []
        for call in tool_calls:
            call_id = call.get("id", "")
            function = call.get("function") or {}
            name = function.get("name")
            try:
                args = json.loads(function.get("arguments") or "{}")
                if not isinstance(args, dict):
                    raise ValueError("arguments must be a JSON object")
            except (json.JSONDecodeError, ValueError) as exc:
                results.append(self._tool_msg(call_id, f"Error: invalid tool arguments: {exc}"))
                continue

            if name == "execute":
                content = self._run_execute(args)
            elif name == "send_message":
                content = self._run_send_message(args)
            elif name == "invoke_skill" and self.skills:
                content = self._run_invoke_skill(args)
            else:
                content = f"Error: unknown tool {name!r}"
            results.append(self._tool_msg(call_id, content))
        return results

    def _tool_msg(self, call_id, content):
        return {"role":"tool", "tool_call_id":call_id, "content":content}

    def _run_execute(self, args: dict) -> str:
        command = args.get("command")
        if not command:
            return "Error: `command` is required."
        kwargs = {k: args[k] for k in ("shell", "cwd", "timeout", "env")
                  if args.get(k) is not None}
        try:
            output = self.env.execute(command, **kwargs)
        except Exception as exc:
            return f"Error: command could not be run: {type(exc).__name__}: {exc}"
        return format_tool_output(output)

    def _run_invoke_skill(self, args: dict) -> str:
        name = args.get("name")
        skill = self.skills.get(name) if isinstance(name, str) else None
        if skill is None:
            return f"Error: unknown skill {name!r}. Available: {', '.join(sorted(self.skills))}"
        return skill["content"]

    def _run_send_message(self, args: dict) -> str:
        summary = args.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            return "Error: `summary` must be a non-empty string."
        # send_message is the submission step: the run ends here.
        self.finished = True
        return "Message sent. The task is submitted."
