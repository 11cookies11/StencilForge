# 开口规则与焊锡体积计算规格

## 目标

这套功能的目标是：

- 让客户先配置基础工艺参数，例如钢网厚度、转印系数、默认策略
- 由体积计算器自动生成推荐开口规则
- 允许用户在推荐规则基础上继续手动自定义
- 所有最终参与生成的规则，都要能够导入、导出、复现

## 核心思路

推荐流程是：

1. 读取 PCB 焊盘几何
2. 计算焊盘面积
3. 根据工艺参数估算推荐焊锡体积
4. 由目标体积反推目标开口面积
5. 把目标开口面积转换成规则参数
6. 应用规则后得到最终开口
7. 由最终开口反算最终焊锡体积

最终关系可以简化成：

```text
焊盘面积 -> 推荐目标体积 -> 开口规则 -> 最终开口 -> 最终焊锡体积
```

## 规则载体

开口规则建议使用 JSON 作为唯一交换格式。

推荐文件结构如下：

```json
{
  "schema_version": 1,
  "profile_name": "default",
  "description": "Default stencil aperture profile",
  "process": {
    "stencil_thickness_mm": 0.12,
    "transfer_ratio": 1.0,
    "default_strategy": "balanced",
    "min_aperture_mm": 0.1,
    "max_aperture_mm": 10.0,
    "allow_asymmetric": false
  },
  "rules": [],
  "generated": {
    "source": "calculator",
    "generated_at": "2026-04-30T16:00:00+08:00",
    "target_volume_mm3": 12.5
  }
}
```

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `schema_version` | integer | 是 | 格式版本号 |
| `profile_name` | string | 是 | 规则集名称 |
| `description` | string | 否 | 说明 |
| `process` | object | 是 | 工艺参数 |
| `rules` | array | 是 | 规则列表 |
| `generated` | object | 否 | 生成信息 |

## 工艺参数

`process` 负责描述客户配置的基础参数。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `stencil_thickness_mm` | number | 是 | - | 钢网厚度 |
| `transfer_ratio` | number | 否 | `1.0` | 焊锡转印系数 |
| `default_strategy` | string | 否 | `balanced` | 推荐策略 |
| `min_aperture_mm` | number | 否 | `0` | 最小开口限制 |
| `max_aperture_mm` | number | 否 | `0` | 最大开口限制，`0` 表示不限制 |
| `allow_asymmetric` | boolean | 否 | `false` | 是否允许非对称开口 |

### 策略枚举

- `balanced`
- `conservative`
- `aggressive`

## 规则结构

每条规则建议包含以下字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `id` | string | 是 | 稳定唯一标识 |
| `name` | string | 是 | 规则名称 |
| `enabled` | boolean | 否 | 是否启用 |
| `priority` | integer | 否 | 优先级，越大越优先 |
| `match` | object | 是 | 匹配条件 |
| `action` | object | 是 | 开口调整动作 |

### `match` 建议字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `package` | string | 封装名，例如 `QFN` |
| `layer` | string | 层，例如 `top` |
| `pad_type` | string | 焊盘类型，例如 `smd` |
| `pad_name` | string | 焊盘名称 |
| `footprint` | string | footprint 名称 |
| `pad_size_mm` | object | 尺寸区间匹配 |

### `pad_size_mm` 子字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `min_x` | number | 最小 X 尺寸 |
| `max_x` | number | 最大 X 尺寸 |
| `min_y` | number | 最小 Y 尺寸 |
| `max_y` | number | 最大 Y 尺寸 |

### `action` 建议字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `delta_mm` | number | 四周等量扩缩 |
| `scale_x` | number | X 方向缩放 |
| `scale_y` | number | Y 方向缩放 |
| `offset_x_mm` | number | X 方向偏移 |
| `offset_y_mm` | number | Y 方向偏移 |

## 优先级规则

建议采用以下顺序：

1. `enabled = false` 的规则跳过
2. `match` 不成立的规则跳过
3. 按 `priority` 从大到小排序
4. `priority` 相同时，匹配更具体的规则优先
5. 如果仍然相同，按定义顺序处理

第一版建议每个焊盘只采用一条最终规则，不做规则叠加。

## 体积计算

推荐使用这个基础公式：

```text
焊锡体积 = 最终开口面积 × 钢网厚度 × 转印系数
```

如果要做推荐值估算，可以继续乘上封装因子和策略因子：

```text
推荐目标体积 = 焊盘面积 × 钢网厚度 × 转印系数 × 封装修正 × 策略修正
```

## 焊盘面积到目标体积

目标体积建议由焊盘面积推导，而不是手工固定输入。

推荐链路是：

```text
焊盘面积 -> 推荐目标体积 -> 目标开口面积 -> 开口规则
```

第一版可以先支持：

- 矩形焊盘
- 对称缩放
- 四周等量扩缩
- 单条规则输出

## 反推规则算法

### 对称缩放

适合多数矩形或近似矩形焊盘。

```text
s = sqrt(目标开口面积 / 原始开口面积)
scale_x = s
scale_y = s
```

### 四周等量扩缩

适合用户更习惯按毫米调节的情况。

```text
(w + 2d) × (h + 2d) = 目标开口面积
```

解出 `d` 后即可生成 `delta_mm`。

## 生成器输出

建议生成器返回这些字段：

| 字段 | 说明 |
|---|---|
| `generated_rule` | 生成的规则 |
| `target_volume_mm3` | 目标焊锡体积 |
| `target_open_area_mm2` | 目标开口面积 |
| `estimated_volume_mm3` | 实际估算体积 |
| `difference_mm3` | 体积偏差 |
| `difference_ratio` | 偏差比例 |
| `status` | `ok` / `warning` / `clamped` |
| `reason` | 可读说明 |

## UI 和后端分工

### UI

- 输入基础工艺参数
- 展示推荐体积
- 展示生成规则
- 允许用户手动编辑和恢复默认

### 后端

- 计算焊盘面积
- 推导推荐目标体积
- 生成开口规则
- 应用规则并输出最终体积

## 第一版建议范围

第一版建议只做最小可用集：

- 规则 JSON 导入和导出
- 基础工艺参数
- 推荐目标体积估算
- 对称缩放和四周等量扩缩
- 单条规则生成
- 最终体积预览

后续再扩展：

- 更复杂的匹配条件
- 非对称规则
- 多规则模板
- 更细的封装经验库
