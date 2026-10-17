# 资产整理工作流

输入已有 CSV、JSON 对象数组或一行一个地址的 TXT。运行时不查询 DNS、测绘 API 或目标服务。

```sh
python3 run.py assets normalize examples/assets.csv --output out/inventory
```

## 输入

每行至少提供 `url`、`host`、`ip`、`domain` 中一个字段，按此顺序选择首个非空值。
可选 `protocol`、`port`、`vendor`、`product`、`organization`、`source`。
显式 URL 的协议优先；缺省协议为 HTTP。URL 中的凭据会被拒绝，拒绝日志不回显原值。

```json
[
  {"host": "console.example.invalid", "protocol": "https", "port": "443", "product": "Example Console", "source": "synthetic export"}
]
```

## 处理规则

- 主机小写、去除末尾句点、国际化域名转 IDNA；支持 IPv4/IPv6。
- 保留协议和端口；显式默认端口与省略默认端口合并。
- 去除路径、查询参数及片段，按服务入口去重。
- 同一服务的来源行、厂商、产品和组织声明合并为列表，不用单值覆盖冲突。
- CSV 中的列表用 JSON 字符串编码；JSON 输出保留原数组。

输出：`assets.json`、`assets.csv`、`review.md`。存在拒绝行时仍输出结果，并返回退出码 2。

## 统计解释

`declared_organizations` 只统计输入声明的名称，不代表已确认的不同使用单位。
`verified_affected_instances` 保持 `null`：资产整理没有验证漏洞，也不把输入中的状态标签升级为影响证明。
同一服务的多个路径可以保留在原始来源中，后续做端点研究时另行整理，不能用服务去重数量代替接口数量。

本首版提供可追溯导入契约；测绘平台和资产系统可将导出转换为上述字段，不需要绑定某个平台账号。
