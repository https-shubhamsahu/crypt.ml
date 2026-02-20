from __future__ import annotations

import argparse
import subprocess
import sys
from urllib import error, request


DEFAULT_MODEL = "phi3.5"
DEFAULT_ENDPOINT = "http://localhost:11434/api/tags"


def check_ollama(endpoint: str) -> bool:
    try:
        with request.urlopen(endpoint, timeout=5) as resp:
            return resp.status == 200
    except (error.URLError, OSError):
        return False


def pull_model(model: str) -> int:
    cmd = ["ollama", "pull", model]
    process = subprocess.run(cmd, check=False)
    return process.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local Ollama and optionally pull a model.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model to pull (default: phi3.5)")
    parser.add_argument("--skip-pull", action="store_true", help="Only check Ollama health")
    args = parser.parse_args()

    print("Checking local Ollama service...")
    if not check_ollama(DEFAULT_ENDPOINT):
        print("Ollama is not reachable at http://localhost:11434.")
        print("Install/start Ollama first, then rerun this script.")
        return 1

    print("Ollama is running.")
    if args.skip_pull:
        print("Skipping model pull as requested.")
        return 0

    print(f"Pulling model: {args.model}")
    code = pull_model(args.model)
    if code != 0:
        print("Model pull failed. Ensure `ollama` CLI is installed and available in PATH.")
        return code

    print("Model pull completed successfully.")
    print("Set environment variables before running app:")
    print("  $env:AEGIS_LLM_ENABLED='true'")
    print(f"  $env:AEGIS_LLM_MODEL='{args.model}'")
    print("  $env:AEGIS_LLM_ENDPOINT='http://localhost:11434/api/generate'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
