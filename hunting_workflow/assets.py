"""Normalize existing inventory without DNS lookup, scanning, or API queries."""
import csv
import ipaddress
import json
from pathlib import Path
from urllib.parse import urlsplit

from .io import WorkflowError, load_json, new_directory, write_json


def endpoint(value, protocol="", port=""):
    value = str(value or "").strip()
    if not value:
        raise WorkflowError("缺少 url/host/ip/domain / Missing endpoint")
    if any(char.isspace() for char in value):
        raise WorkflowError("主机中含空白字符 / Whitespace in endpoint")
    # Bare IPv6 literals must not be mistaken for host:port.
    if "://" not in value:
        try:
            address = ipaddress.ip_address(value)
            value = "[" + address.compressed + "]" if address.version == 6 else str(address)
        except ValueError:
            pass
    scheme = str(protocol or "http").strip().lower()
    try:
        parsed = urlsplit(value if "://" in value else scheme + "://" + value)
    except ValueError as exc:
        raise WorkflowError("无效 URL / Invalid URL") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise WorkflowError("仅接受 HTTP(S) 资产标识 / Expected HTTP(S) endpoint")
    if parsed.username is not None or parsed.password is not None:
        raise WorkflowError("URL 含凭据，请移除 / Remove credentials from URL")
    host = parsed.hostname.rstrip(".").lower()
    try:
        host = ipaddress.ip_address(host).compressed
    except ValueError:
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise WorkflowError("无效主机名 / Invalid hostname") from exc
        if not host or any(char in host for char in "<>\\/%"):
            raise WorkflowError("无效主机名 / Invalid hostname")
    try:
        explicit = parsed.port
        field_port = int(port) if str(port).strip() else None
        if explicit is not None and field_port is not None and explicit != field_port:
            raise WorkflowError("URL 与 port 字段冲突 / Conflicting ports")
        number = explicit if explicit is not None else field_port
        number = number if number is not None else (443 if parsed.scheme == "https" else 80)
        if not 1 <= number <= 65535:
            raise WorkflowError("端口超出范围 / Port out of range")
    except ValueError as exc:
        raise WorkflowError("无效端口 / Invalid port") from exc
    shown_host = "[" + host + "]" if ":" in host else host
    default = 443 if parsed.scheme == "https" else 80
    key = parsed.scheme + "://" + shown_host + ("" if number == default else ":" + str(number))
    return {"service": key, "host": host, "protocol": parsed.scheme, "port": number}


def read_rows(path):
    path = Path(path)
    try:
        if path.suffix.lower() == ".json":
            value = load_json(path)
            if not isinstance(value, list) or not all(isinstance(x, dict) for x in value):
                raise WorkflowError("资产 JSON 应为对象数组 / Expected an array of objects")
            return value
        if path.suffix.lower() == ".csv":
            with path.open(encoding="utf-8-sig", newline="") as stream:
                return list(csv.DictReader(stream))
        return [{"host": line.strip()} for line in path.read_text(encoding="utf-8-sig").splitlines()
                if line.strip() and not line.lstrip().startswith("#")]
    except (OSError, UnicodeError, csv.Error) as exc:
        raise WorkflowError(f"资产文件读取失败 / Cannot read inventory: {exc}") from exc


def normalize(rows):
    grouped, rejected = {}, []
    for index, row in enumerate(rows, 1):
        try:
            value = next((row.get(k) for k in ("url", "host", "ip", "domain") if row.get(k)), "")
            normalized = endpoint(value, row.get("protocol", ""), row.get("port", ""))
        except WorkflowError as exc:
            rejected.append({"row": index, "reason": str(exc)})
            continue
        key = normalized["service"]
        item = grouped.setdefault(key, {**normalized, "source_rows": [], "vendors": [],
                 "products": [], "declared_organizations": [], "evidence_status": "indexed_only",
                 "source_refs": []})
        item["source_rows"].append(index)
        for field, dest in [("vendor", "vendors"), ("product", "products"),
                            ("organization", "declared_organizations"), ("source", "source_refs")]:
            value = str(row.get(field, "") or "").strip()
            if value and value not in item[dest]:
                item[dest].append(value)
    assets = sorted(grouped.values(), key=lambda x: x["service"])
    declared = {org for item in assets for org in item["declared_organizations"]}
    return {"schema_version": "1.0", "assets": assets, "rejected": rejected,
            "summary": {"input_rows": len(rows), "services": len(assets),
                        "duplicate_rows": sum(len(x["source_rows"]) - 1 for x in assets),
                        "unique_hosts": len({x["host"] for x in assets}),
                        "declared_organizations": len(declared),
                        "verified_affected_instances": None,
                        "rejected_rows": len(rejected)},
            "limitations": ["主机数不等于单位数 / Hosts are not organizations",
                            "导入不证明受影响或授权 / Imported rows prove neither impact nor authorization",
                            "厂商/产品/组织字段来自输入，未由工具核实 / Identity fields are input claims"]}


def export_inventory(result, output):
    output = new_directory(output)
    write_json(output / "assets.json", result)
    fields = ["service", "host", "protocol", "port", "vendors", "products",
              "declared_organizations", "source_rows", "evidence_status", "source_refs"]
    with (output / "assets.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in result["assets"]:
            row = {key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
                   for key, value in item.items()}
            # A CSV opened in a spreadsheet must not execute user-supplied formula cells.
            for key, value in row.items():
                if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                    row[key] = "'" + value
            writer.writerow(row)
    summary = result["summary"]
    lines = ["# 资产整理结果 / Inventory review", "", "本流程未访问目标或执行 DNS 查询。", "",
             "| 指标 | 数量 |", "|---|---:|"]
    lines += [f"| {key} | {value if value is not None else '未验证 / not verified'} |"
              for key, value in summary.items()]
    lines += ["", "## 局限", ""] + ["- " + item for item in result["limitations"]]
    if result["rejected"]:
        lines += ["", "## 拒绝的行（不回显潜在凭据）", ""]
        lines += [f"- row {x['row']}: {x['reason']}" for x in result["rejected"]]
    (output / "review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output
