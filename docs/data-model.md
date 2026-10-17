# 数据契约与状态

[案例 Schema](../hunting_workflow/resources/schemas/case.schema.json) 和 [资产输入 Schema](../hunting_workflow/resources/schemas/asset.schema.json) 使用 JSON Schema Draft 2020-12。
内置验证器只实现这两份 Schema 使用的子集，遇到未知规则会报错；也可用完整 JSON Schema 验证器检查结构。

## 案例字段

| 字段 | 含义 |
|---|---|
| `schema_version`、`id`、`synthetic` | 契约版本、案例标识、是否合成；三项必须显式填写 |
| `vendor`、`product`、`affected_versions` | 产品与有证据的版本声明；每个版本关联版本证据 |
| `description`、`trigger_conditions`、`impact`、`location` | 描述、身份/功能前提、影响及精确定位 |
| `evidence` | ID、案例内路径、类型和 SHA-256；拒绝越界路径及软链接 |
| `claims` | 断言、verified/static/unverified 状态与引用 |
| `scope` | 输入声明的范围来源、授权目标与验证目标；工具检查记录对应，不判定授权真实有效 |
| `verification` | 步骤、预期/实际、证据、人工复核及清理记录 |
| `affected_instances` | 有独立引用的实例记录；不从资产数量自动填入 |
| `originality` | 检索来源、查询、时间、结果与人工比较；无命中不自动证明原创 |
| `severity` | 自评等级与依据；工具不计算最终等级 |
| `remediation` | 缓解、根治与修复后验证建议 |
| `contacts` | 联系人完整性；格式和平台差异留给当前页面确认 |
| `limitations` | 未验证的范围、环境依赖和其他限制 |
| `platform_review` | 当前字段映射的人工确认日期与说明 |

额外未知顶层字段会作为结构错误报告，避免悄悄忽略误拼字段。
少量必填字段只保证记录可识别；材料所需的内容由语义检查分别列出缺项。

## 证据

证据类型包括 `request`、`response`、`control_response`、`product_version`、`authorization`、`screenshot`、`search_record`。
请求/响应需要在验证记录中关联；截图不能代替原文。原始内容不由生成器改写，报告导出会复制校验通过的文件并记录新路径。
SHA-256 检查证明字节一致，不证明记录来自真实运行。示例中的 `verified` 模拟的是已完成人工记录的结构，全部受合成标记约束。

## 状态

- `schema_valid`：数据结构符合版本契约。
- `materials_complete`：本地准备所需字段、引用和记录齐备。
- `ready_for_manual_submission_review`：材料齐备、不是已标记的合成数据，且记录了当前平台字段的人工核对。
- `platform_acceptance`：固定为 `not_assessed`，由平台回执另行记录。

只把 `synthetic` 改为 false 不能消除示例证据中的显式合成标记；检查器会指出不一致。
这项保护识别本项目夹具，不是通用的证据真伪鉴别器。

## 字节与路径

文件和 CLI 输出使用 UTF-8；输入 JSON 也接受 UTF-8 BOM。证据路径相对 `case.json` 所在目录。
示例证据禁止 Git 自动转换行尾，以保持 Windows、macOS 和 Linux 上的摘要一致。
产物目录必须不存在。实体 ZIP 使用清单内的相对路径，不接受用户指定的越界或链接证据。
工具不加载 Python 配置、不执行模板代码，也不根据输入发起网络请求。
