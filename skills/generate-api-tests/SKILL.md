---
name: generate-api-tests
description: 针对 Java 服务的代码改动生成 pytest 接口自动化测试用例的主流程，按阶段编排改动分析、场景设计、mock 与框架造数、用例生成、执行修复，每阶段暂停等用户确认。当用户要为某次代码改动测试接口、生成接口自动化用例、或提到被测 operation 加两个分支时使用。
---

# 接口测试用例生成（主流程）

按阶段编排五个子 skill，全程人机协同：每个阶段产出一份 md，停下来等用户确认后才进入下一阶段。

先读 [CONVENTIONS.md](CONVENTIONS.md)，其中的红线全程生效。

## 加载 vendor 适配

每次调用主编排时，**在收集输入之前**先按下面顺序读一次 vendor 配置：

1. `<产物目录所在项目根>/.api-test-skills.yaml`
2. `~/.api-test-skills.yaml`
3. 若都不存在，vendor 视为 `none`。

配置文件格式：

```yaml
vendor: <vendor-name>
```

`<vendor-name>` 是已安装的适配包名（如各公司自己的适配包）；未安装任何适配包时值填 `none`
或省略配置文件。配置用 CLI 写入：

```bash
npx api-test-skills use <vendor-name>
npx api-test-skills use <vendor-name> --project
npx api-test-skills use none
npx api-test-skills status
```

若用户没有配置文件又想启用适配，引导他执行 `npx api-test-skills use <vendor-name>`，
不要让他手工 echo 写文件。

读到 vendor（非 none）后，各阶段的 skill 调用规则变为：

| 阶段 | 核心 skill | 追加调用（若 vendor 有对应适配） |
|---|---|---|
| 2 | `analyze-change-scenarios` | 无 |
| 3 | `prepare-mock-data` | `prepare-mock-data-<vendor>` |
| 4 | `prepare-framework-data` | `prepare-framework-data-<vendor>` |
| 5 | `write-pytest-cases` | `write-pytest-cases-<vendor>` |
| 6 | `run-and-fix-tests` | 无 |

主编排的操作顺序是「先调核心讲方法论，再调适配讲工具细节」，两者共同产出该阶段的 md。

如果 vendor 声明为某个具体名字但对应的适配 skill 未安装，主编排必须**停下报错**：

> vendor=`<vendor-name>` 但未找到 `prepare-mock-data-<vendor-name>` skill，请检查安装。

不静默降级到纯核心。

vendor 为 `none` 时纯核心运行；阶段 3（mock）若无核心方法论就能落地的方案，允许跳过
（在 `03-mock-plan.md` 里注明「本环境不使用 mock」）。

## 阶段流水线

阶段 1、2 全量做一次；阶段 3 到 6 按批次循环。

| 阶段 | 核心子 skill | vendor 适配（若有） | 产出 | 粒度 |
|---|---|---|---|---|
| 1 | 本 skill 收集输入 | — | `docs/00-context.md` | 全量 |
| 2 | `analyze-change-scenarios` | — | `docs/01-change-analysis.md`、`docs/02-scenarios.md` | 全量 |
| 3 | `prepare-mock-data` | `prepare-mock-data-<vendor>` | `docs/batch<N>/03-mock-plan.md` | 按批 |
| 4 | `prepare-framework-data` | `prepare-framework-data-<vendor>` | `docs/batch<N>/04-framework-data.md` | 按批 |
| 5 | `write-pytest-cases` | `write-pytest-cases-<vendor>` | 用例代码、`docs/batch<N>/05-case-design.md` | 按批 |
| 6 | `run-and-fix-tests` | — | `docs/batch<N>/06-run-report.md` | 按批 |

```
阶段 1 收集输入            ── 全量，一次
阶段 2 改动分析与场景设计    ── 全量，一次，产出含「批次」列的场景清单
  ┌── 对每个批次循环 ──────────────────┐
  │ 阶段 3 mock 方案（仅本批次场景）      │
  │ 阶段 4 框架造数（仅本批次场景）        │
  │ 阶段 5 用例生成（仅本批次场景）        │
  │ 阶段 6 执行与修复（仅本批次用例）      │
  │ 本批次收尾汇报 → 用户确认后进下一批    │
  └────────────────────────────────┘
```

批次划分在阶段 2 完成，规则见 `analyze-change-scenarios`。要点：**batch1 固定是主流程
（冒烟，1–5 条场景），剩余场景默认全部塞进 batch2，只有超过 30 条才继续拆**。

**用户明确要求不分批时**退化为单批：主流程和其他场景全部归 batch1，目录结构不变。
除此之外不要自作主张跳过分批或多拆批次。

## 流程

### 1. 收集输入

> 收集输入前，先读并汇报 vendor 配置（见「加载 vendor 适配」）。若 vendor 未配置，
> 提示用户是否需要启用适配。

缺哪项问哪项，全部问齐后写入 `00-context.md`：

| 项 | 必填 | 说明 |
|---|---|---|
| operation 名 | 必填 | 被测接口，如 `api/testProcessorChain` |
| 发布环境 | 必填 | 如 `fat0` |
| Pod IP | 必填 | 直连指定实例，避免打到未部署新代码的节点；格式如 `10.32.xxx.xxx` |
| 代码仓库本地路径 | 必填 | 不在本地时请用户自行 clone，不要代劳；必须是本机可访问的绝对路径 |
| base 分支 | 必填 | 用于 diff，如 `master` |
| feature 分支 | 必填 | 用于 diff，如 `feature/xxx` |
| 产物目录 | 必填 | 生成物落地位置 |
| appid | vendor 相关 | 有应用编号体系的 vendor 下必填；vendor=none 时不需要 |
| 相关文档 | 可选 | 飞书链接 / 本地 md / 口头描述，可为空 |

**必填项缺失处理（红线）**：

- 用户未提供、或提供的值明显不是有效值（占位符 `xxx`、空字符串、`TBD`、`?`），必须停下来
  一次性列出**所有**缺失项让用户补齐，不许边猜边跑。
- 不允许用默认值、示例值、上一次会话记忆里的值代填。特别是 Pod IP、仓库路径、
  base/feature 分支这类环境相关值，错一次会导致整条链路白跑。
- 提问格式：先一句话说明"以下是必填输入，缺哪项请补齐"，再按清单列出缺项和用途，
  用户答齐前不进入阶段 2。
- 有值但可疑（例如仓库路径填了但本地不存在、分支名填了但 `git rev-parse` 解不出）时，
  当场校验并回问用户，别默默继续。

### 2. 断点续跑

每次被调用时，先扫 `<产物目录>/docs/` 根目录和各 `docs/batch<N>/` 子目录下 md 的状态头，
向用户报告进度，格式是「第 N 批的第 M 阶段」。从第一个非 `已确认` 的阶段继续，不要重头再来。

判断当前批次的方法：批次号最大的那个 `docs/batch<N>/` 目录就是进行中的批次；
它下面 `06-run-report.md` 已确认，说明该批次做完了，下一步是开新批次。

### 3. 逐阶段调度

每个阶段：调用子 skill → 产出 md → **暂停**，请用户 review → 用户确认（或直接改 md）
→ 把状态头改成 `已确认` → 进入下一阶段。

一个批次的阶段 6 确认后，先做本批次收尾汇报，再开下一批次目录。开新批次前不要提前
生成下一批的 mock 或用例。

允许跳过阶段。例如某批次所有依赖都不走 mock 时跳过阶段 3，但要在该批次的
`03-mock-plan.md` 里写明"本批次不使用 mock"并说明原因，保持链路可追溯。

每个阶段的具体动作：

1. 主编排调用核心子 skill，得到该阶段的方法论指引；
2. 若当前 vendor 有对应适配 skill，主编排追加调用它，让它把工具细节写进同一份 md；
3. 产出 md → **暂停**，请用户 review → 用户确认后进入下一阶段。

### 4. 收尾

每批阶段 6 结束后汇报：本批用例覆盖了哪些场景、哪些场景需要人工前置操作、
有没有疑似被测代码缺陷、下一批打算覆盖什么。疑似缺陷要单独列出来，
这是本流程最重要的产出之一。

全部批次跑完后再做一次总汇报，按批次汇总通过率与疑似缺陷清单。

## 暂停点纪律

暂停不是走过场。每次暂停按下面三句话向用户汇报，不要复述整份 md：

1. **这一步做完了什么**：一两句结论。例："改动集中在空城市兜底分支，围绕它设了 6 条场景。"
2. **还欠什么**：存疑点，逐条列，让用户知道回答哪些他就能放行。
3. **需要他做什么**：人工动作，比如"去 mock 平台配 CASE-01/02 并把 CaseId 填回 md 顶部"。

三句话讲完就停，等用户回复。他没明确说"可以进下一步"或者直接改 md 之前，不要往前走。

**反面示范**（不要这样写）：

> 本阶段已完成 mock 方案的设计，包括决策矩阵、mock 报文、CaseId 回填表、遗留数据需求
> 等内容，方案已经过一致性校验，请您审阅确认后进入下一阶段。

**正面示范**：

> batch1 的 mock 方案定了：`queryUserCoin` 走 mock（FAT 造不出空返回），`queryCityInfo`
> 直连（228 城市 FAT 里有）。CASE-01/02 的 JSON 我写好了，你去平台建完把 CaseId 填到
> 表格最后一列。有一个存疑点：`userType` 字段取值范围我没查到，NEW 是我按代码猜的，
> 你确认下。
