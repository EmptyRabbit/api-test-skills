# 05-case-design.md 模板

```markdown
> 阶段：batch1/05-用例设计
> 状态：待确认
> 上游：batch1/02-scenarios.md、batch1/03-mock-plan.md、batch1/04-framework-data.md
> 更新时间：YYYY-MM-DD HH:MM

**一句话结论**：本批 4/5 个场景生成了用例（R1 已确认删除），映射见下表；执行前还有
3 项人工待办（回填 CaseId、配连接信息、确认配置项）。

# 用例设计说明

## 一、工程结构

```
cases2/
├── frame/            复制自 template，含 request_log.py
├── tests/
│   ├── env_config.py                  环境常量
│   ├── test_processor_chain_gray.py   实验分流
│   └── test_processor_chain_content.py 内容渲染
├── logs/             每个用例的操作日志（传参与结果），自动生成，不入 git
├── conftest.py       通用 fixture + 本次造数 fixture + 日志 fixture
├── config.yaml       DB / Redis 配置
├── .gitignore
└── requirements.txt
```

## 二、场景与用例映射

| 场景 ID | 用例文件 | 用例函数 | 对应改动点 | mock Case | 造数 fixture |
|---|---|---|---|---|---|
| S1 | `test_processor_chain_recall.py` | `test_sp_flight_with_city` | C1 | CASE-01 | 无 |
| S2 | `test_processor_chain_recall.py` | `test_sp_hotel_no_city` | C1 | CASE-02 | 无 |
| S3 | `test_processor_chain_content.py` | `test_paid_order_notified` | C2 | 无 | `paid_order` |
| S5 | `test_processor_chain_entry.py` | `test_cid_empty` | C1 | 无 | 无 |

未生成用例的场景及原因：

| 场景 ID | 原因 |
|---|---|
| R1 | 用户确认删除，非改动点 |

## 三、fixture 说明

| fixture | 作用 | 清理方式 |
|---|---|---|
| `paid_order` | 在 order_db.orders 造一条 PAID 订单 | yield 后 DELETE |

## 四、执行前置清单

跑用例前需要人工完成：

- [ ] 在 `config.yaml` 填写 order_db 连接信息
- [ ] 在 mock 平台配置 CASE-01、CASE-02，并把 CaseId 回填到
      `tests/test_testProcessorChain.py` 的 `MOCK_IDS`
- [ ] 确认配置项 `t0-install-abt-config.json` 的 `abtEnabled` 为 false
- [ ] 确认 Pod IP 10.121.100.90 已部署 feature 分支代码

测试完成后需要还原：

- [ ] 无（本次未修改配置项）

## 五、执行方式

```bash
cd <产物目录>
pytest tests/test_testProcessorChain.py -v
```

## 六、失败先看哪里

用例失败时**先打开 `logs/<用例函数名>.md`**，里面按调用顺序列出这次真实的 HTTP / DB /
Redis / MQ 传参和结果。pytest 的 assert 摘要只告诉你哪个字段错了，看不出是 mock 没配上、还是入参
造错了、还是被测代码真的有问题——这三种要走的处理路径完全不同，翻日志是分清它们最快的
办法。

## 七、存疑点

- [ ] 无
```
