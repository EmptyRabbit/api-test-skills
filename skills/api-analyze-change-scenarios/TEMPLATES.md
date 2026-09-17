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
| C3 | ProductTypeEnum.java 等 6 个类 | 见下方「依据」 | 修改（共享/跨链） | 是 |

不在调用链上的改动（本接口测不到）：C2 —— 定时任务，需另行覆盖。

## 三、改动点行为差异

改动点描述必须是人话，类名只放进「依据」（红线见 CONVENTIONS.md）。

### C1 XxxProcessor#handle

- **改前**：cityId 为空时直接返回失败。
- **改后**：cityId 为空时走兜底逻辑，按 prdType 取默认城市。
- **进入条件**：scenario = T0_INSTALL 且 userContext.cid 非空。
- **依据**：`XxxProcessor.java:88-120` / PRD 第 3.2 节。

### C3 新增产品类型取值（共享改动，影响面广）

- **改前 / 改后**：产品类型新增取值 `OTHER`，各处按枚举穷举实现的 switch/EnumMap/
  配置映射（日志上报、排序候选组装、渲染投递）都多了一个原逻辑未覆盖的分支。
- **对测试意味着什么**：针对每个分支处理点补一条覆盖 `OTHER` 的场景，验证会不会
  静默丢字段或错误落到默认兜底。
- **依据**：`ProductTypeEnum`、`HotelReRankingCandidate`、`ChannelDeliveryCommand` 等
  6 个类的 switch/EnumMap 分支改动（完整清单见 `git diff` 附录）。

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

> 按批次分段产出：先只写场景总览表 + 批次安排（骨架），暂停确认；确认后从 batch1
> 开始逐批补全该批次的场景详情（预期产出表），每批写完都暂停确认。下面是**全部批次
> 都确认完**之后的最终形态；产出过程中的中间状态只包含骨架，或骨架 + 已确认批次的
> 详情，状态头的「批次进度」行标出当前进度（写法见 CONVENTIONS.md「md 状态头」）。

```markdown
> 阶段：02-测试场景
> 状态：待确认
> 批次进度：骨架已确认；batch1 已确认；batch2 已确认
> 上游：01-change-analysis.md
> 更新时间：YYYY-MM-DD HH:MM

# 测试场景清单

## 场景总览

| 场景 ID | 标题 | 对应改动点 | 类型 | 优先级 | 批次 |
|---|---|---|---|---|---|
| S1 | 有卖点+有城市+机票 | C1 | 正常 | 高 | batch1 |
| S2 | 有卖点+无城市+机票兜底 | C1 | 边界 | 高 | batch2 |
| R1 | 常规主流程回归 | 非改动点，建议但可删 | 回归 | 低 | batch2 |

## 覆盖检查

| 改动点 | 覆盖场景 | 是否有遗漏 |
|---|---|---|
| C1 | S1、S2 | 否 |
| C2 | 无 | 是——C2 不在本接口调用链上，测不到，见 01 的「不在调用链上的改动」 |

## 批次安排

| 批次 | 场景数 | 覆盖重点 |
|---|---|---|
| batch1 | 1 | 主流程：核心成功路径 |
| batch2 | 2 | 边界与回归 |

## S1 有卖点+有城市+机票

- **为什么设这条**：C1 主流程正向路径（对应改动点已在总览表标出），所有下游字段
  都要走一遍，跑通它才代表链路是通的。
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
