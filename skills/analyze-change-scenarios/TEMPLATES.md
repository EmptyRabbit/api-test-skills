# 产物模板

## 01-change-analysis.md

```markdown
> 阶段：01-改动分析
> 状态：待确认
> 上游：00-context.md
> 更新时间：YYYY-MM-DD HH:MM

# 代码改动分析

## 一、接口入口

- operation：api/xxx
- 实现类：`com.example.xxx.service.impl.XxxServiceImpl#queryXxx`
- 文件路径：`src/main/java/com/example/xxx/service/impl/XxxServiceImpl.java`
- 调用链：XxxServiceImpl#queryXxx → XxxProcessor#handle → XxxRepository#load

## 二、改动清单

| 编号 | 文件 | 类#方法 | 改动性质 | 是否在本接口调用链上 |
|---|---|---|---|---|
| C1 | XxxProcessor.java | XxxProcessor#handle | 修改 | 是 |
| C2 | YyyJob.java | YyyJob#run | 新增 | 否 |

不在调用链上的改动（本接口测不到）：C2 —— 定时任务，需另行覆盖。

## 三、改动点行为差异

### C1 XxxProcessor#handle

- **改前**：cityId 为空时直接返回失败。
- **改后**：cityId 为空时走兜底逻辑，按 prdType 取默认城市。
- **进入条件**：scenario = T0_INSTALL 且 userContext.cid 非空。
- **依据**：`XxxProcessor.java:88-120` / PRD 第 3.2 节。

## 四、依赖清单

### 外部接口
| 接口 | 调用位置 | 入参要点 | 返回结构要点 |
|---|---|---|---|

### DB
| 库 | 表 | 读/写 | 关键字段 |
|---|---|---|---|

### Redis
| 集群名 | key 格式 | 用途 | TTL |
|---|---|---|---|

### 配置中心
| 文件 | key | 用途 | 当前值（测试环境） |
|---|---|---|---|

### 消息中间件
| subject | 发/收 | 消息结构要点 |
|---|---|---|

## 五、PRD 与代码差异

| 差异点 | PRD 描述 | 代码实现 | 以哪边为准 |
|---|---|---|---|
| 空城市兜底 | 返回失败 | 走兜底 | *（待用户裁决）* |

## 六、存疑点

- [ ] 字段 `hasSellingPoint` 的业务含义未查到，需确认。
```

## 02-scenarios.md

```markdown
> 阶段：02-测试场景
> 状态：待确认
> 上游：01-change-analysis.md
> 更新时间：YYYY-MM-DD HH:MM

# 测试场景清单

## 场景总览

| 场景 ID | 标题 | 对应改动点 | 类型 | 优先级 | 批次 |
|---|---|---|---|---|---|
| S1 | 有卖点+有城市+机票 | C1 | 正常 | 高 | batch1 |
| S2 | 有卖点+无城市+机票兜底 | C1 | 边界 | 高 | batch2 |
| R1 | 常规主流程回归 | 非改动点，建议但可删 | 回归 | 低 | batch2 |

## 批次安排

| 批次 | 场景数 | 覆盖重点 |
|---|---|---|
| batch1 | 1 | 主流程：核心成功路径 |
| batch2 | 2 | 边界与回归 |

## S1 有卖点+有城市+机票

- **对应改动点**：C1
- **为什么设这条**：C1 主流程正向路径，所有下游字段都要走一遍，跑通它才代表链路是通的。
- **触发条件**：scenario=T0_INSTALL，cid=10001，cityId=228，prdType=F
- **前置数据**：`queryUserCoin` 走 mock 返回一条 10% off 券（见 03）
- **预期产出**：

| 阶段 / 处理器 | 关键产出字段 | 期望值 | 值的来源 | 是否随机 |
|---|---|---|---|---|
| 网关入口 | `$.success` | false | 代码常量（通道未配置分支） | 否 |
| 网关入口 | `$.errorCode` | 20011 | 代码常量 | 否 |
| 召回 | `ctx.candidate.prdType` | F | 入参回显 | 否 |
| 召回 | `ctx.candidate.cityId` | 228 | 入参回显 | 否 |
| 渲染 | `creativeItem.contentBaseId` | 11999 | 用户提供（fat 模板库） | 否 |
| 渲染 | `renderVarSnapshot.couponValue` | 10% off | mock 报文（CASE-01 权益返回） | 否 |
| 渲染 | `creativeItem.title` | 非空、不含 `{` | 模板随机文案 | 是 |
| 渲染 | `creativeItem.link` | 含 `cityId=228` 且含 `hotel-theme` | 代码拼接 | 否 |

- **副作用**：无

## 存疑点

- [ ] S2 的兜底城市取值规则需确认。
```
