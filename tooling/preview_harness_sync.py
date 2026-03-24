#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from harness_profile_lib import ValidationError, dump_json, load_json, make_state, resolve_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview the effective harness resolution for a profile.")
    parser.add_argument("--profile", required=True, help="Path to HARNESS_PROFILE.json")
    parser.add_argument("--registry", required=True, help="Path to BOOTSTRAP_ARCHETYPE_REGISTRY.json")
    parser.add_argument("--write-state", help="Optional path for docs/assistant/runtime/BOOTSTRAP_STATE.json")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")
    args = parser.parse_args()

    profile = load_json(args.profile)
    registry = load_json(args.registry)

    try:
        plan = resolve_plan(profile, registry)
    except ValidationError as exc:
        print(f"Cannot resolve harness plan: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    else:
        print(f"Project: {plan['project']}")
        print(f"Archetype: {plan['archetype']}")
        print(f"Mode: {plan['mode']}")
        print("Modules:")
        for module in plan["modules"]:
            print(f"  - {module}")
        print("Outputs:")
        for output in plan["outputs"]:
            print(f"  - {output}")
        if plan["starter_files"]:
            print("Starter files:")
            for starter in plan["starter_files"]:
                print(f"  - {starter}")
        if plan["notes"]:
            print("Notes:")
            for note in plan["notes"]:
                print(f"  - {note}")

    if args.write_state:
        state = make_state(profile, registry)
        dump_json(state, args.write_state)
        if not args.json:
            print(f"Wrote bootstrap state to {args.write_state}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
