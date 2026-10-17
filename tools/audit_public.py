#!/usr/bin/env python3
"""Audit only this repository's publication candidates; never scan the parent workspace."""
import argparse
import hashlib
import ipaddress
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOTS = {".github", "hunting_workflow", "docs", "examples", "templates", "tests", "tools"}
ALLOWED_TOP = {"README.md", "README.en.md", "LICENSE", "NOTICE.md", "SECURITY.md", "CONTRIBUTING.md",
               "CHANGELOG.md", "AGENTS.md", "pyproject.toml", "run.py", ".gitignore", ".gitattributes", "RELEASE-MANIFEST.json"}
IGNORED = {".git", "out", "dist", "build", "__pycache__", ".venv"}
EXAMPLE_NETS = [ipaddress.ip_network(value) for value in
                ["192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32"]]
PATTERNS = {
    "token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{20,})\b"),
    "private-key": re.compile("-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "personal-path": re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+/"),
    "secret-assignment": re.compile(r'''(?i)(?:api[_-]?key|password|appsecret|access[_-]?token)\s*["']?\s*[:=]\s*["']([A-Za-z0-9_+./=-]{16,})["']'''),
}
EMAIL = re.compile(r"\b[A-Za-z0-9_.+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")


def candidate_files(root):
    if (root / ".git").exists():
        result = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                                check=True, stdout=subprocess.PIPE)
        return sorted(set(x.decode("utf-8") for x in result.stdout.split(b"\0") if x))
    result = []
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if name not in IGNORED and not name.endswith(".egg-info")]
        for name in dirs:
            path = Path(directory) / name
            if path.is_symlink():
                result.append(str(path.relative_to(root)))
        result.extend(str((Path(directory) / name).relative_to(root)).replace("\\", "/") for name in names)
    return sorted(result)


def example_domain(domain):
    domain = domain.lower()
    return domain in {"example.com", "example.net", "example.org"} or domain.endswith((".invalid", ".example", ".test"))


def scan_text(text):
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        for label, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append((label, number))
        if any(not example_domain(match.group(1)) for match in EMAIL.finditer(line)):
            findings.append(("non-example-email", number))
        if PHONE.search(line):
            findings.append(("possible-personal-phone", number))
        for match in IPV4.finditer(line):
            try:
                address = ipaddress.ip_address(match.group(0))
            except ValueError:
                continue
            if not address.is_loopback and not any(address.version == net.version and address in net for net in EXAMPLE_NETS):
                findings.append(("non-example-ip", number))
    return sorted(set(findings))


def audit(root=ROOT):
    root = Path(root).resolve()
    errors, manifest = [], []
    for relative in candidate_files(root):
        path = root / relative
        parts = Path(relative).parts
        if not parts or (len(parts) == 1 and relative not in ALLOWED_TOP) or (len(parts) > 1 and parts[0] not in ALLOWED_ROOTS):
            errors.append({"path": relative, "kind": "outside-public-allowlist"})
            continue
        if path.is_symlink() or any((root / Path(*parts[:i])).is_symlink() for i in range(1, len(parts))):
            errors.append({"path": relative, "kind": "symlink"})
            continue
        if not path.resolve().is_relative_to(root) or not path.is_file():
            errors.append({"path": relative, "kind": "missing-or-outside-root"})
            continue
        if path.name.endswith(".secret.json") or path.name in {".env", "jwt.key"}:
            errors.append({"path": relative, "kind": "credential-file"})
            continue
        if path.stat().st_size > 2 * 1024 * 1024:
            errors.append({"path": relative, "kind": "unexpected-large-file"})
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            errors.append({"path": relative, "kind": "unexpected-binary"})
            continue
        errors.extend({"path": relative, "kind": kind, "line": line} for kind, line in scan_text(text))
        manifest.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
    return {"ok": not errors, "files_checked": len(manifest), "findings": errors, "manifest": manifest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    result = audit()
    if args.manifest:
        args.manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps({key: value for key, value in result.items() if key != "manifest"}, ensure_ascii=False, indent=2))
    else:
        print("PASS" if result["ok"] else "FAIL", "publication candidates:", result["files_checked"])
        for item in result["findings"]:
            print(item["kind"], item["path"], "line", item.get("line", "-"))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
