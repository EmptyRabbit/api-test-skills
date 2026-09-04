# 06-run-report.md 模板

```markdown
> 阶段：batch1/06-执行修复
> 状态：待确认
> 上游：05-case-design.md
> 更新时间：YYYY-MM-DD HH:MM

# 执行与修复记录

## 一、结论

**一句话**：跑了两轮，7/8 通过，剩下 `test_paid_order_notified` 是**疑似被测代码 bug**
（PAID 订单没触发通知，见第四节），需要开发确认。

- 用例总数：8
- 通过：7（第 1 轮修好用例代码笔误后到 7 条）
- 失败：1（疑似缺陷，未修改用例）
- 环境问题：无

## 二、前置确认

| 项 | 状态 |
|---|---|
| config.yaml 连接信息已填 | 是 |
| mock CASE-01 / CASE-02 已配置 | 是 |
| 配置项 abtEnabled = false | 是 |
| Pod 10.121.100.90 已部署 feature 分支 | 是 |

## 三、执行轮次

### 第 1 轮

```
pytest tests/test_testProcessorChain.py -v
6 passed, 2 failed
```

| 失败用例 | 实际 | 预期 | 归因 | 日志 | 处理 |
|---|---|---|---|---|---|
| `test_cid_empty` | 20003 | 20006 | 用例代码问题 | `logs/test_cid_empty.md` | 已改，重跑通过 |

### 第 2 轮

```
7 passed, 1 failed
```

`test_paid_order_notified` 仍失败，维持疑似缺陷判定，不再修改。

## 四、疑似被测代码缺陷

### 缺陷 1：已支付订单未发出 order.notified 消息

**请求**

```json
{"orderId": "demo_test_10001", "scenario": "NOTIFY"}
```

**实际响应**

```json
{"success": true, "orderStatus": "PAID"}
```

**预期结果**

`orderStatus` 应为 `NOTIFIED`，且发出 order.notified 消息。

**依据**

`OrderNotifyProcessor.java:142` 在 status 已为 PAID 时提前 return，
未执行通知逻辑；PRD 第 4.1 节写明已支付订单必须触发通知。

**判断**：代码逻辑和 PRD 明确对不上，倾向 bug 而不是理解偏差。请开发看下 line 142 的
提前 return 是不是漏了 case，或者 PRD 需要修订。

## 五、遗留问题

- [ ] 缺陷 1 待开发确认。确认前该用例保持失败，**不改断言让它变绿**。

## 下一批

本批次已确认后，下一批计划覆盖：batch2（边界与回归，N 个场景）。
```
