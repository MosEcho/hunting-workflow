"""Command-line workflows. Every command is local and performs no target requests."""
import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .assets import export_inventory, normalize, read_rows
from .cases import inspect_case
from .io import WorkflowError, new_directory, write_json
from .render import build_case, export_bundle


def demo(output, examples=None):
    if examples is None:
        examples = Path(__file__).resolve().parent.parent / "examples"
    else:
        examples = Path(examples)
    required = [examples / "assets.csv", examples / "complete-case/case.json", examples / "missing-case/case.json"]
    if not all(x.is_file() for x in required):
        raise WorkflowError("找不到示例，请从完整仓库运行或传 --examples / Examples missing; use a full clone")
    # Verify expectations before writing: a broken demo should never report success.
    _, full = inspect_case(required[1])
    _, missing = inspect_case(required[2])
    if not full["materials_complete"] or full["ready_for_manual_submission_review"] or missing["materials_complete"]:
        raise WorkflowError("演示预期失败 / Demo expectations failed")
    output = new_directory(output)
    inventory = normalize(read_rows(required[0]))
    export_inventory(inventory, output / "assets")
    build_case(required[1], output / "complete")
    build_case(required[2], output / "missing")
    export_bundle(output / "complete", output / "complete-review.zip")
    result = {"synthetic_only": True, "target_requests": 0, "inventory": inventory["summary"],
              "complete_case": {"materials_complete": True, "real_submission_allowed": False},
              "missing_case": {"materials_complete": False, "missing_rules":
                  [x["id"] for x in missing["rules"] if x["state"] == "missing"]}}
    write_json(output / "demo-summary.json", result)
    (output / "START-HERE.md").write_text(
        "# 离线演示完成\n\n全部数据为合成演示，未访问目标。\n\n"
        "1. assets/review.md：归一化与统计局限。\n"
        "2. complete/report.html：可直接用浏览器打开的完整示例。\n"
        "3. complete/checklist.md：材料完整，但演示数据阻止真实报送。\n"
        "4. missing/checklist.md：缺项及下一步。\n"
        "5. complete-review.zip：实体附件与 SHA-256 清单。\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("打开 / Open: " + str(output / "START-HERE.md"))
    return 0


def parser():
    root = argparse.ArgumentParser(prog="hunting-workflow", description="离线资产整理与证据驱动材料准备 / Offline research workflows")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    d = commands.add_parser("demo", help="无账号、无网络的合成演示 / Offline synthetic demo")
    d.add_argument("--output", type=Path, default=Path("out/demo"))
    d.add_argument("--examples", type=Path)
    assets = commands.add_parser("assets").add_subparsers(dest="action", required=True)
    a = assets.add_parser("normalize")
    a.add_argument("input", type=Path)
    a.add_argument("--output", required=True, type=Path)
    cases = commands.add_parser("case").add_subparsers(dest="action", required=True)
    check = cases.add_parser("check")
    check.add_argument("input", type=Path)
    check.add_argument("--json", action="store_true")
    build = cases.add_parser("build")
    build.add_argument("input", type=Path)
    build.add_argument("--output", required=True, type=Path)
    export = cases.add_parser("export")
    export.add_argument("source", type=Path)
    export.add_argument("--output", required=True, type=Path)
    return root


def main(argv=None):
    # Redirected Windows terminals may default to a legacy code page. The CLI's
    # machine-readable JSON and bilingual messages use UTF-8 on every platform.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = parser().parse_args(argv)
    try:
        if args.command == "demo":
            return demo(args.output, args.examples)
        if args.command == "assets":
            result = normalize(read_rows(args.input))
            export_inventory(result, args.output)
            print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
            # Rejected data produces useful output and an explicit partial-success status.
            return 2 if result["rejected"] else 0
        if args.action == "check":
            _, review = inspect_case(args.input)
            if args.json:
                print(json.dumps(review, ensure_ascii=False, indent=2))
            else:
                print("materials_complete:", review["materials_complete"])
                print("ready_for_manual_submission_review:", review["ready_for_manual_submission_review"])
                for rule in review["rules"]:
                    print(f"[{rule['state']}] {rule['id']}: {rule['detail']}")
            return 0 if review["ready_for_manual_submission_review"] else 2
        if args.action == "build":
            review = build_case(args.input, args.output)
            print("草稿已生成 / Draft built:", args.output)
            print("materials_complete:", review["materials_complete"])
            print("ready_for_manual_submission_review:", review["ready_for_manual_submission_review"])
            return 0  # Successful draft generation is distinct from successful readiness checks.
        count = export_bundle(args.source, args.output)
        print(f"已导出 {count} 个实体文件 / Exported files: {args.output}")
        return 0
    except (WorkflowError, OSError, UnicodeError) as exc:
        print("错误 / Error: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
