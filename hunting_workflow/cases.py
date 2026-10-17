"""Evidence and preparation checks, separate from platform acceptance or vulnerability validity."""
from datetime import date
from pathlib import Path

from .assets import endpoint
from .io import WorkflowError, inside_file, load_json, sha256
from .schema import resource, validate


def inspect_case(path):
    path = Path(path)
    case = load_json(path)
    errors = validate(case, resource("schemas", "case.schema.json"))
    if errors:
        return case, {"schema_valid": False, "materials_complete": False,
            "ready_for_manual_submission_review": False, "platform_acceptance": "not_assessed",
            "rules": [{"id": "schema", "state": "missing", "category": "requirement",
                       "detail": error} for error in errors]}
    rules = []

    def add(key, good, detail, category="requirement", bad="missing"):
        rules.append({"id": key, "state": "pass" if good else bad,
                      "category": category, "detail": detail})

    for key in ["title", "vendor", "product", "product_description", "description",
                "trigger_conditions", "impact", "location", "fingerprint"]:
        add(key, bool(case.get(key, "").strip()), key + " 必须有明确内容 / Provide explicit content")
    add("versions", bool(case.get("affected_versions")), "填写确有证据的版本 / Supply evidenced versions")
    add("vulnerability_type", bool(case.get("vulnerability_types")), "填写缺陷类型 / Supply vulnerability type")
    evidence = {}
    evidence_errors = []
    synthetic_evidence = False
    for item in case.get("evidence", []):
        ident = item["id"]
        if ident in evidence:
            evidence_errors.append(ident + ": duplicate evidence ID")
            continue
        try:
            file = inside_file(path.parent, item["path"])
            if sha256(file) != item["sha256"]:
                raise WorkflowError("SHA-256 不匹配 / Digest mismatch")
            with file.open("rb") as stream:
                prefix = stream.read(4096)
            if any(marker in prefix for marker in (b"SYNTHETIC DEMO", b"SYNTHETIC PRODUCT RECORD")):
                synthetic_evidence = True
            evidence[ident] = item
        except WorkflowError as exc:
            evidence_errors.append(ident + ": " + str(exc))
    add("evidence_integrity", bool(evidence) and not evidence_errors,
        "; ".join(evidence_errors) or "证据文件与 SHA-256 / Evidence files and digests")
    versions = case.get("affected_versions", [])
    version_refs = all(x.get("evidence_ids") and all(i in evidence for i in x["evidence_ids"])
                       and any(evidence[i]["kind"] == "product_version" for i in x["evidence_ids"] if i in evidence)
                       for x in versions)
    add("version_evidence", bool(versions) and version_refs, "每个版本需关联证据 / Link every version to evidence")
    verify = case.get("verification", {})
    kinds = {evidence[i]["kind"] for i in verify.get("evidence_ids", []) if i in evidence}
    wire_good = {"request", "response"} <= kinds
    all_refs = all(i in evidence for i in verify.get("evidence_ids", []))
    add("wire_evidence", wire_good and all_refs, "验证记录需关联请求和响应原文 / Link request and response")
    add("reproduction", len(verify.get("steps", [])) >= 2 and bool(verify.get("expected", "").strip())
        and bool(verify.get("actual", "").strip()), "提供步骤、预期和实际结果 / Steps, expected and actual result")
    add("human_verification", verify.get("status") == "verified" and verify.get("human_reviewed") is True
        and bool(verify.get("review_note", "").strip()), "记录人工复核及其结论 / Record human review")
    add("cleanup", bool(verify.get("cleanup", "").strip()), "记录变更和清理或无需清理的依据 / Record cleanup")
    claims = case.get("claims", [])
    justified = any(x["status"] == "verified" for x in claims)
    for claim in claims:
        if claim["status"] == "verified":
            justified = justified and bool(claim["evidence_ids"]) and all(i in evidence for i in claim["evidence_ids"])
    add("claim_traceability", justified, "实测断言必须关联存在的证据 / Verified claims need evidence")
    add("claim_limits", all(x["status"] == "verified" for x in claims) and bool(claims),
        "静态或未验证断言保留标记 / Static and unverified claims remain labeled", category="advisory", bad="review")
    scope = case.get("scope", {})
    scope_refs = scope.get("evidence_ids", [])
    scope_good = scope.get("basis") in {"self_hosted_lab", "written_authorization", "program_scope"}
    scope_good = scope_good and bool(scope_refs) and all(i in evidence for i in scope_refs)
    scope_good = scope_good and any(evidence[i]["kind"] == "authorization" for i in scope_refs if i in evidence)
    allowed, requested = set(), set()
    try:
        allowed = {endpoint(x)["service"] for x in scope.get("authorized_targets", [])}
        requested = {endpoint(x)["service"] for x in scope.get("targets", [])}
        scope_good = scope_good and bool(requested) and requested <= allowed
    except WorkflowError:
        scope_good = False
    add("scope_record", scope_good, "范围、来源文件和目标声明需对应 / Match stated scope and evidence")
    instances = case.get("affected_instances", [])
    instance_good = bool(instances)
    for item in instances:
        refs = item["evidence_ids"]
        instance_good = instance_good and bool(refs) and all(i in evidence for i in refs)
        instance_kinds = {evidence[i]["kind"] for i in refs if i in evidence}
        instance_good = instance_good and {"request", "response"} <= instance_kinds
        try:
            instance_good = instance_good and endpoint(item["target"])["service"] in requested
        except WorkflowError:
            instance_good = False
    add("instance_records", instance_good,
        "实例应关联范围和证据，不设固定数量门槛 / Link instances to scope and evidence; no fixed count threshold")
    originality = case.get("originality", {})
    searches = originality.get("searches", [])
    searches_good = bool(searches) and all(x.get("query", "").strip() and x.get("result", "").strip()
                       and x.get("checked_at", "").strip() for x in searches)
    add("originality_record", originality.get("status") == "reviewed_no_match" and searches_good
        and bool(originality.get("review_note", "").strip()),
        "保存检索与人工比较；无命中不自动证明原创 / Record searches and human comparison")
    severity = case.get("severity", {})
    add("self_rating", severity.get("level") not in {None, "unrated"}
        and bool(severity.get("rationale", "").strip()), "自评级需有依据，最终评级由平台决定 / Explain self-rating")
    remediation = case.get("remediation", {})
    add("remediation", all(remediation.get(k, "").strip() for k in ("temporary", "permanent", "verification")),
        "补齐缓解、修复与验证建议 / Mitigation, fix and verification")
    contacts = case.get("contacts", {})
    add("contacts", all(contacts.get(role, {}).get(k, "").strip()
        for role in ("reporter", "supporter") for k in ("name", "email", "phone")),
        "联系人字段仅做完备性检查 / Contact completeness only")
    add("limitations", bool(case.get("limitations")), "说明验证边界与局限 / State limitations")
    is_synthetic = case["synthetic"] or synthetic_evidence
    add("synthetic_label_consistency", case["synthetic"] or not synthetic_evidence,
        "演示证据必须保留合成标记 / Keep synthetic labels on demo evidence")
    add("synthetic_data", not is_synthetic,
        "合成演示禁止真实报送 / Synthetic examples are not real submissions", category="publication", bad="blocked")
    policy = case.get("platform_review", {})
    try:
        reviewed = date.fromisoformat(policy.get("reviewed_at", ""))
        date_good = reviewed <= date.today()
    except (TypeError, ValueError):
        date_good = False
    policy_good = policy.get("field_mapping_confirmed") is True and date_good and bool(policy.get("note", "").strip())
    add("platform_rules", policy_good, "当前表单与规则需人工核实 / Confirm live platform requirements",
        category="publication", bad="review")
    profile = resource("profiles", "cnnvd.json")
    for key, limit in profile["draft_length_guidelines"].items():
        add("length_" + key, len(case.get(key, "")) <= limit,
            f"{key}: 本地草稿参考长度 {limit}，现行限额待核对 / Local guideline, confirm live limits",
            category="advisory", bad="review")
    materials = all(x["state"] == "pass" for x in rules if x["category"] == "requirement")
    publication = all(x["state"] == "pass" for x in rules if x["category"] == "publication")
    return case, {"schema_valid": True, "materials_complete": materials,
                  "ready_for_manual_submission_review": materials and publication,
                  "platform_acceptance": "not_assessed", "synthetic": is_synthetic,
                  "rules": rules}
