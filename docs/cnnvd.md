# CNNVD 材料准备工作流

本模块把已经形成的研究记录映射成字段草稿与附件，不登录平台、不提交 API，也不自动生成研究结论。

## 步骤

1. 从 [空模板](../templates/case.json) 建立私有案例，填写产品、准确版本、前提、定位和影响。
2. 保存原始请求、响应、版本依据、范围来源与必要对照；添加证据 ID 和 SHA-256。
3. 将每个已验证断言关联到证据；静态推断或未验证的部分保留状态。
4. 保存原创性检索及人工比较记录，补齐人工复现、修复建议和验证边界。
5. 运行 `case check`；根据缺项补证，再生成草稿。
6. 对照当前 CNNVD 页面核对字段、分类编码、联系人、附件设置和字数限制。
7. 选择并审阅材料后手工报送，另行保存回执与修订记录。

```sh
python3 run.py case check examples/complete-case/case.json --json
python3 run.py case build examples/complete-case/case.json --output out/cnnvd-draft
python3 run.py case export out/cnnvd-draft --output out/cnnvd-review.zip
```

## 输出解释

- `form-fields.json` / `form-fields.md`：按常见字段组织的草稿，不是官方导入协议。
- `report.md` / `report.html`：报告、步骤、实际/预期结果、证据原文及局限；HTML 可由浏览器阅读或打印。
- `checklist.md` / `readiness.json`：缺项、人工核对项与状态。
- `evidence-index.json` / `evidence/`：校验过的实体副本。
- `manifest.json`：本次产物的 SHA-256；导出前重新核对，篡改或丢失时拒绝导出。

文字材料用于审阅与人工填写。首版没有 Word/PDF 转换、录像制作、平台字段编码自动匹配或自动提交。
需要这些格式时，应根据当前平台要求另行转换、审阅，不能只更改扩展名。

## 规则与时效性

[平台草稿配置](../hunting_workflow/resources/profiles/cnnvd.json) 明确记录来源及核查局限。
2026-10-17 官方 SPA 入口可达，但本次工具没有取得可解析的当前表单内容，因而 `live_field_verification` 为 `null`。
参考字数用于本地写作提示，不作为已经确认的官方硬限制。

固定案例数量、资本门槛、等级与发证条件不由工具推断。一个有证据的本地实例可形成材料结构演示，这不证明符合任何平台的最终受理条件。
CNVD 与 CNNVD 应分别核对，不能共享未经确认的门槛配置。

`platform_review` 是使用者人工核对的记录。填写它只会改变进入人工审阅的标志，不产生平台受理或证书结论。

来源入口见 [sources.md](sources.md)。
