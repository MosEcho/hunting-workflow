#!/usr/bin/env python3
"""Create a source archive only from audited publication candidates."""
import argparse
import json
import zipfile
from pathlib import Path

from audit_public import ROOT, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit()
    if not result["ok"]:
        for item in result["findings"]:
            print(item["kind"], item["path"], item.get("line", ""))
        return 1
    output = args.output
    if output.exists() or output.is_symlink():
        parser.error("output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = "hunting-workflow-0.1.0/"
    with output.open("xb") as stream:
        try:
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                for item in result["manifest"]:
                    archive.write(ROOT / item["path"], prefix + item["path"])
                archive.writestr(prefix + "RELEASE-MANIFEST.json", json.dumps(
                    {"version": "0.1.0", "files": result["manifest"]}, ensure_ascii=False, indent=2) + "\n")
        except BaseException:
            stream.close()
            output.unlink(missing_ok=True)
            raise
    print("Source archive:", output, "files:", len(result["manifest"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
