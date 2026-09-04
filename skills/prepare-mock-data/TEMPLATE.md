# 03-mock-plan.md 模板

```markdown
> 阶段：batch1/03-mock 方案
> 状态：待确认
> 上游：02-scenarios.md
> 更新时间：YYYY-MM-DD HH:MM

# Mock 方案

本文件只覆盖 batch1 的场景。

## 一、决策矩阵

「理由」列必须能立住脚，不接受"构造成本高""接口简单"这种一句话糊过去的写法。
参考下面的填法：

| 场景 | 依赖接口 | 是否被调用 | 需要的返回 | 是否 mock | 理由 |
|---|---|---|---|---|---|
| S1 | queryUserCoin | 是 | 一条 10% off 券 | 是 | FAT 库里都是有券用户，临时清账号影响其他人的用例 |
| S1 | queryCityInfo | 是 | cityId=228 的城市信息 | 否 | 228 城市 FAT 已有，直连一次比配 mock 快 |
| S2 | queryUserCoin | 是 | 空券列表 | 是 | 同上，FAT 造不出空返回 |

## 二、Mock Case 配置清单

用户按此清单去 mock 平台逐个配置。

### CASE-01（覆盖场景 S1）

**接口 queryUserCoin**

```json
{
  "success": true,
  "coinList": [
    {"coinId": "C1001", "title": "10% off", "userType": "NEW"}
  ]
}
```

**接口 queryPromotion**

```json
{
  "success": true,
  "promotionList": []
}
```

### CASE-02（覆盖场景 S2）

**接口 queryUserCoin**

```json
{
  "success": true,
  "coinList": []
}
```

## 三、CaseId 回填表

配置完成后把平台生成的 CaseId 填入最后一列。

| Case 编号 | 覆盖场景 | 包含接口 | 平台 CaseId |
|---|---|---|---|
| CASE-01 | S1 | queryUserCoin, queryPromotion | *（待回填）* |
| CASE-02 | S2 | queryUserCoin | *（待回填）* |

未回填的场景视为"本次不使用 mock"，需与用户确认。

## 四、遗留数据需求（交给 prepare-framework-data）

不走 mock 的接口，要让它返回期望数据所需的真实环境准备：

| 场景 | 接口 | 期望返回 | 需要准备的数据 |
|---|---|---|---|
| S1 | queryCityInfo | cityId=228 的城市信息 | 确认 FAT 城市库存在 228，无需造数 |
| S3 | queryOrder | 一条已支付订单 | 需在 order_db.orders 造一条 status=PAID 的记录 |

## 五、存疑点

- [ ] queryUserCoin 返回中 `userType` 的取值范围未确认。
```
