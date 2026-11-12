import importlib.util
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WORK_DIR = os.path.abspath(os.path.dirname(__file__))
TOOL_PATH = os.path.join(REPO_ROOT, "tools", "course_checks", "r53-t022.py")


def main():
    spec = importlib.util.spec_from_file_location("r53_t022", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    try:
        report = module.run_verification()
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)

    raw_output = report.pop("raw_output", "")
    print(raw_output)
    print(f"Success! {report['executed_passed_tests']} tests executed and passed.")
    print(f"Anchor cases verified: {report['anchor_cases_verified']}")
    print(f"Double-copy comparison: {report['double_copy_diff']}")

    with open(os.path.join(WORK_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    with open(os.path.join(WORK_DIR, "results.log"), "w", encoding="utf-8") as f:
        f.write(raw_output)

    print("Evidence saved in work/R53-T022/results.json and work/R53-T022/results.log")


if __name__ == "__main__":
    main()
