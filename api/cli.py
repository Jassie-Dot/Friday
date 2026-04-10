from __future__ import annotations

import argparse
import asyncio
import json

import uvicorn

from core.config import get_settings
from core.models import ObjectiveRequest
from core.runtime import FridayRuntime


async def _run_objective(objective: str) -> None:
    runtime = FridayRuntime(get_settings())
    await runtime.start()
    try:
        record = await runtime.orchestrator.run(ObjectiveRequest(objective=objective))
        print(json.dumps(record.model_dump(mode="json"), indent=2))
    finally:
        await runtime.stop()


async def _search_memory(query: str) -> None:
    runtime = FridayRuntime(get_settings())
    try:
        hits = runtime.memory.query(query, limit=5)
        print(json.dumps([item.model_dump() for item in hits], indent=2))
    finally:
        await runtime.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="FRIDAY local operating system")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Start the FRIDAY backend API.")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)

    run_parser = subparsers.add_parser("run", help="Run a single objective immediately.")
    run_parser.add_argument("objective")

    memory_parser = subparsers.add_parser("memory", help="Search long-term memory.")
    memory_parser.add_argument("query")

    args = parser.parse_args()
    settings = get_settings()

    if args.command == "serve":
        uvicorn.run("api.main:app", host=args.host or settings.host, port=args.port or settings.port, reload=False)
        return
    if args.command == "run":
        asyncio.run(_run_objective(args.objective))
        return
    if args.command == "memory":
        asyncio.run(_search_memory(args.query))


if __name__ == "__main__":
    main()
