"""Chess tool implementations, decoupled from the agent that registers them.

Every function here takes the HTTP client explicitly instead of reading it off
an agent, so the same code can run in the agent process or inside the sandbox
beside the server it talks to.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx

CHESS_PORT = 8000


def _request_state(
    client: httpx.Client, method: str, endpoint: str, **kwargs: Any
) -> dict[str, Any]:
    """Make one chess API request and validate its JSON response."""

    response = client.request(method, endpoint, **kwargs)
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Chess server returned non-JSON ({response.status_code})."
        ) from exc
    if response.status_code >= 400:
        detail = (
            payload.get("detail", payload) if isinstance(payload, dict) else payload
        )
        raise ValueError(str(detail))
    if not isinstance(payload, dict):
        raise RuntimeError("Chess server response must be a JSON object.")
    return payload

def _chess_error(message: str) -> str:
    return f"<chess_error>{message}</chess_error>"


def _parse_arguments(arguments: Any) -> dict[str, Any]:
    try:
        args = json.loads(arguments)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Malformed JSON arguments: {exc}") from exc
    if not isinstance(args, dict):
        raise ValueError("Arguments must be a JSON object.")
    return args

def _simulate_move(client: httpx.Client, arguments: str) -> str:
    try:
        args = _parse_arguments(arguments)
        fen = args.get("fen")
        if not isinstance(fen, str) or not fen.strip():
            raise ValueError("'fen' must be a non-empty string (six-field FEN).")
        payload: dict[str, Any] = {"fen": fen.strip()}
        move = args.get("move")
        if move is not None:
            if not isinstance(move, str):
                raise ValueError("'move' must be a string in UCI notation.")
            payload["move"] = move
        return json.dumps(_request_state(client, "POST", "/api/simulate", json=payload))
    except httpx.HTTPError as exc:
        return _chess_error(f"Transport failure: {exc}")
    except Exception as exc:
        return _chess_error(str(exc))


def _play_move(client: httpx.Client, arguments: str) -> str:
    try:
        args = _parse_arguments(arguments)
        move = args.get("move")
        if not isinstance(move, str) or not move.strip():
            raise ValueError("'move' must be a non-empty string in UCI notation, e.g. e2e4.")
        state = _request_state(client, "POST", "/api/move", json={"move": move.strip()})
        return json.dumps(state)
    except httpx.HTTPError as exc:
        return _chess_error(f"Transport failure: {exc}")
    except Exception as exc:
        return _chess_error(str(exc))


def _run_python(env: Any, port: int, arguments: str) -> str:
    try:
        args = _parse_arguments(arguments)
        code = args.get("code")
        if not isinstance(code, str) or not code.strip():
            raise ValueError("'code' must be a non-empty string of Python source.")
        encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
        result = env.execute(
            f"python /opt/assignment/sandbox_python.py {int(port)} {encoded}"
        )
        if result.get("returncode", 0) != 0:
            raise RuntimeError(
                result.get("exception_info")
                or result.get("stderr")
                or result.get("output")
                or "sandbox runner failed"
            )
        stdout = result.get("stdout", "")
        json.loads(stdout)  # runner phải in đúng 1 JSON object, nếu không -> chess_error
        return stdout
    except Exception as exc:
        return _chess_error(str(exc))


def _invoke_skill(skills: dict[str, dict[str, str]], arguments: str) -> str:
    try:
        args = _parse_arguments(arguments)
        name = args.get("name")
        if not isinstance(name, str):
            raise ValueError("'name' must be a string.")
        if name not in skills:
            raise ValueError(f"Unknown skill {name!r}. Available: {', '.join(sorted(skills))}")
        return skills[name]["content"]
    except Exception as exc:
        return _chess_error(str(exc))


def _game_state(client: httpx.Client, reset: bool = False) -> dict:
    """Read the live game, or start a new one and read the opening position."""

    method, endpoint = ("POST", "/api/reset") if reset else ("GET", "/api/state")
    return _request_state(client, method, endpoint)
