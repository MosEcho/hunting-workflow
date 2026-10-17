"""Produce reviewable local drafts and self-contained evidence exports."""
import html
import json
import re
import shutil
import zipfile
from pathlib import Path

from .cases import inspect_case
from .io import WorkflowError, inside_file, load_json, new_directory, sha256, write_json


def display(value):
    if value is None or value == "" or value == []:
        return "[待补 / MISSING]"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def cell(value):
    return html.escape(display(value)).replace("|", "\\|").replace("\n", "<br>")


def block(text):
    fence = "`" * max(3, max((len(x) + 1 for x in re.findall(r"`+", text)), default=3))
    return fence + "text\n" + text.rstrip() + "\n" + fence


def build_case(case_path, output):
    case_path = Path(case_path)
    case, review = inspect_case(case_path)
    if not review["schema_valid"]:
        raise WorkflowError("结构错误，先运行 case check / Invalid structure; run case check first")
    # No output directory is created until all evidence paths have been checked.
    attachments = []
    for item in case.get("evidence", []):
        try:
            path = inside_file(case_path.parent, item["path"])
            if sha256(path) == item["sha256"]:
                attachments.append((item, path))
        except WorkflowError:
            pass
    output = new_directory(output)
    (output / "evidence").mkdir()
    exported = []
    for index, (item, path) in enumerate(attachments, 1):
        # Use tool-generated filenames instead of accepting arbitrary archive paths or IDs.
        suffix = path.suffix.lower()
        safe_suffix = suffix if re.fullmatch(r"\.[a-z0-9]{1,8}", suffix) else ".bin"
        name = f"evidence/{index:03d}{safe_suffix}"
        shutil.copyfile(path, output / name)
        exported.append({**item, "path": name, "sha256": sha256(output / name)})
    fields = {
        "漏洞名称": case.get("title", ""), "厂商": case.get("vendor", ""),
        "产品": case.get("product", ""), "版本范围": case.get("affected_versions", []),
        "受影响产品描述": case.get("product_description", ""),
        "漏洞类型": case.get("vulnerability_types", []),
        "漏洞自评级": case.get("severity", {}).get("level", "unrated"),
        "漏洞描述或简介": case.get("description", ""), "网络资产探测指纹": case.get("fingerprint", ""),
        "漏洞触发条件": case.get("trigger_conditions", ""), "漏洞影响描述": case.get("impact", ""),
        "漏洞定位": case.get("location", ""),
        "本地记录实例数_需核对平台统计口径": len(case.get("affected_instances", [])),
        "联系人": case.get("contacts", {}),
        "_draft_metadata": {"profile": "cnnvd-draft-1", "synthetic": review["synthetic"],
                            "platform_acceptance": "not_assessed", "live_field_mapping_required": True},
    }
    write_json(output / "form-fields.json", fields)
    write_json(output / "readiness.json", review)
    write_json(output / "evidence-index.json", exported)
    lines = ["# " + cell(case.get("title")), "",
             "**SYNTHETIC DEMO / 合成演示，不能真实报送。**" if review["synthetic"]
             else "**研究材料草稿 / Research draft — 需人工确认与平台研判。**", "",
             "## 产品与版本", "", f"- 厂商：{cell(case.get('vendor'))}",
             f"- 产品：{cell(case.get('product'))}", "", block(display(case.get("affected_versions"))),
             "", "## 缺陷、前提与影响", ""]
    for key, title in [("description", "描述"), ("trigger_conditions", "触发条件"),
                       ("impact", "影响"), ("location", "定位"), ("fingerprint", "检索指纹")]:
        lines += ["### " + title, "", block(display(case.get(key))), ""]
    lines += ["## 验证过程", "", block(display(case.get("verification"))), "",
              "## 实例记录（输入声明，工具不判断实际受影响）", "",
              block(display(case.get("affected_instances"))), "", "## 断言与证据", "",
              block(display(case.get("claims"))), "", "## 原创性记录", "",
              block(display(case.get("originality"))), "", "## 自评级依据", "",
              block(display(case.get("severity"))), "", "## 修复建议", "",
              block(display(case.get("remediation"))), "", "## 局限", "",
              block(display(case.get("limitations"))), "", "## 证据原文", ""]
    for item in exported:
        lines += ["### " + cell(item["id"]) + " · " + cell(item["kind"]), "",
                  f"文件：[{item['path']}]({item['path']})", "", "SHA-256: `" + item["sha256"] + "`", ""]
        if item["kind"] in {"request", "response", "control_response", "product_version", "authorization", "search_record"}:
            content = (output / item["path"]).read_text(encoding="utf-8", errors="replace")
            lines += [block(content), ""]
    report = "\n".join(lines) + "\n"
    (output / "report.md").write_text(report, encoding="utf-8")
    # A self-contained printable view: all untrusted text is escaped, with no remote resources.
    document = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Research draft</title><style>body{max-width:1000px;margin:40px auto;padding:0 24px;'
        'font:15px/1.7 system-ui,sans-serif;color:#18212b}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        '@media print{body{margin:0;max-width:none}pre{font-size:10pt}}</style>'
        '<body><pre>' + html.escape(report) + '</pre></body></html>')
    (output / "report.html").write_text(document, encoding="utf-8")
    form_lines = ["# CNNVD 字段草稿", "", "按当前页面人工核对；字段编码、限额、公开情况及附件设置不自动猜测。", ""]
    for key, value in fields.items():
        form_lines += ["## " + key, "", block(display(value)), ""]
    (output / "form-fields.md").write_text("\n".join(form_lines), encoding="utf-8")
    checks = ["# 材料缺项与审阅清单", "", f"材料结构完整：{review['materials_complete']}",
              f"可进入真实报送前人工审阅：{review['ready_for_manual_submission_review']}",
              "平台受理/评级/发证：未评估", "", "| 项目 | 状态 | 说明 |", "|---|---|---|"]
    checks += [f"| {cell(x['id'])} | {x['state']} | {cell(x['detail'])} |" for x in review["rules"]]
    (output / "checklist.md").write_text("\n".join(checks) + "\n", encoding="utf-8")
    write_json(output / "manifest.json", {"format": "hunting-review-bundle-1", "synthetic": review["synthetic"],
        "files": [{"path": str(p.relative_to(output)).replace("\\", "/"), "sha256": sha256(p)}
                  for p in sorted(output.rglob("*")) if p.is_file()]})
    return review


def export_bundle(source, output):
    source, output = Path(source).resolve(), Path(output)
    manifest_path = inside_file(source, "manifest.json")
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict) or manifest.get("format") != "hunting-review-bundle-1":
        raise WorkflowError("不是已生成的材料包 / Not a generated review bundle")
    if not isinstance(manifest.get("files"), list):
        raise WorkflowError("材料清单应为数组 / Manifest files must be an array")
    if output.exists() or output.is_symlink():
        raise WorkflowError("ZIP 已存在 / ZIP already exists")
    validated = []
    names = set()
    for item in manifest.get("files", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
            raise WorkflowError("材料清单条目无效 / Invalid manifest entry")
        if item["path"] in names:
            raise WorkflowError("材料清单重复 / Duplicate manifest entry")
        names.add(item["path"])
        path = inside_file(source, item["path"])
        if sha256(path) != item["sha256"]:
            raise WorkflowError("材料包内容已变更，请重新生成 / Bundle changed; rebuild it")
        validated.append((item["path"], path))
    if not validated:
        raise WorkflowError("材料清单为空 / Empty manifest")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        try:
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, path in validated:
                    archive.write(path, name)
                archive.write(source / "manifest.json", "manifest.json")
        except BaseException:
            stream.close()
            output.unlink(missing_ok=True)
            raise
    return len(validated) + 1
