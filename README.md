# Inibsa Smart Demand Signals — F1 Replenishment Intelligence

**Hackathon:** Interhack BCN 2026  
**Domain:** B2B medical/dental consumables wholesale (Inibsa, Spain)  
**Task:** Predict which clients need replenishment calls in the next 4 weeks

---

## 项目结构

```
Interbcn/
├── README.md
├── notebook_data/          # 原始数据（不可修改）
│   ├── Ventas.csv          # 交易记录 162,546 条
│   ├── Productos.csv       # 产品信息 25 个 SKU
│   ├── Potencial.csv       # 客户商业潜力 33,093 条
│   ├── Clientes.csv        # 客户主数据 11,031 条
│   └── Campañas.csv        # 促销活动 10 条
├── src/
│   ├── stage0_preprocessing.py   # 数据预处理与周面板构建
│   ├── stage1_baseline.py        # 季节性统计基线
│   └── stage2_gru.py             # GRU 深度学习模型
├── output/
│   ├── env.txt                   # 运行环境版本快照
│   ├── stage0/                   # Stage 0 产出
│   ├── stage1/                   # Stage 1 产出
│   └── stage2/                   # Stage 2 产出
└── docs/
    └── inibsa-dataset-eda.ipynb  # 探索性分析 notebook
```

---

## 数据概况

| 维度 | 数值 |
|---|---|
| 时间范围 | 2021-01-04 → 2025-12-29 |
| 总交易条数（清洗后） | 162,546 |
| 活跃客户数 | 8,095 |
| SKU 数 | 25 |
| 产品族 | 4（Familia C1/C2/T1/T2） |
| 冷启动客户（有潜力、无订单） | 2,940 |

**产品分类：**

| 代码 | 业务名称（假设映射，待赞助商确认） | 类型 |
|---|---|---|
| Familia C1 | Anestesia（麻醉品） | Commodity → F1 目标 |
| Familia C2 | Bioseguridad（生物安全/PPE） | Commodity → F1 目标 |
| Familia T1 | Biomateriales（生物材料） | Técnico → F2 |
| Familia T2 | Biomateriales（生物材料） | Técnico → F2 |

> ⚠️ C1→Anestesia、C2→Bioseguridad 的映射为假设，需与赞助商核实。

---

## 运行方法

每个 Stage 独立运行，依次执行：

```bash
cd /path/to/Interbcn

python src/stage0_preprocessing.py   # ~30s
python src/stage1_baseline.py        # ~20s
python src/stage2_gru.py             # ~7min (CPU)
```

依赖：`pandas>=2.0`, `numpy`, `torch>=2.0`, `scikit-learn`, `pyarrow`

---

## Stage 0 — 数据预处理

**脚本：** `src/stage0_preprocessing.py`

### 主要步骤

1. **列名规范化** — 统一所有表的字段名（client_id / product_id / date 等）
2. **销售清洗** — 标记退货行（`is_return=True`，保留不删除），去重，过滤单价 > 10,000€ 的异常行
3. **主表合并** — Ventas LEFT JOIN Productos LEFT JOIN Clientes，不在 Clientes 的客户标记 `province=Unknown`
4. **周面板构建** — 聚合至 `client_id × product_family × week_start`（ISO 周一），**显式补零填充缺失周**，确保所有 pair 的时间轴连续
5. **促销标记** — 每周打 `campaign_active` 标记
6. **冷启动识别** — 单独输出仅在 Potencial 中出现的客户

### 产出文件

| 文件 | 行数 | 说明 |
|---|---|---|
| `output/stage0/df_master.parquet` | 163,052 | 交易级主表 |
| `output/stage0/df_weekly.parquet` | 2,891,786 | 周面板（15,047 pairs × 261 周，含补零） |
| `output/stage0/df_potential.parquet` | 33,093 | 客户潜力查找表 |
| `output/stage0/df_cold_clients.parquet` | 2,940 | 冷启动客户（F3 输入） |
| `output/stage0/preprocessing_report.md` | — | 数据清洗报告 |

---

## Stage 1 — 季节性统计基线

**脚本：** `src/stage1_baseline.py`

### 算法

针对 Commodity 产品（C1/C2），将补货预测转化为**统计异常检测**：

**核心公式：**
```
seasonal_time_score = max(0, delay / std_used)
delay               = days_since_last_purchase - expected_interval
replenishment_score = seasonal_time_score × value_factor
```

**三级层级回退（解决历史稀疏问题）：**

| 级别 | 分组 | 启用条件 | 置信度 |
|---|---|---|---|
| Level A | 客户 × 产品族 × 季度 | ≥ 3 次购买间隔 | high |
| Level B | 客户 × 产品族 | ≥ 4 次购买间隔 | medium |
| Level C | 产品族 × 季度（全局） | 兜底 | low |

标准差下限 ε = 3 天，防止极规律客户的分数爆炸。

**价值因子：** `log1p(max(潜力值, 历史12月销售额))` 归一化至 [0,1]，过滤低价值噪声。

**优先级分箱**（基于实际分布百分位）：P1=前5%，P2=前20%，P3=前50%，P4=其余。

### 评估结果

| 指标 | 数值 |
|---|---|
| 总评分 pairs | 8,450 |
| 超期预警（score > 0） | 4,570 |
| P1 Critical | 230 |
| P2 High | 689 |
| **P1+P2 合计** | **919** |
| 置信度 high/medium/low | 2,634 / 1,799 / 4,017 |
| 超期客户预期补货间隔（均值） | 143 天 |

### 产出文件

| 文件 | 行数 | 说明 |
|---|---|---|
| `output/stage1/f1_baseline_alerts.parquet` | 8,450 | 全量评分结果，含优先级和原因文本 |
| `output/stage1/f1_baseline_diagnostics.md` | — | 诊断报告 |

---

## Stage 2 — GRU 序列模型

**脚本：** `src/stage2_gru.py`

### 任务定义

```
输入：(client_id, product_family) 的最近 12 周时序特征
输出：未来 4 周内是否下单的概率 ∈ [0, 1]
```

### 特征设计

**序列特征（每个时间步 7 维，lookback L=12 周）：**

| 特征 | 说明 |
|---|---|
| `weekly_units` | 当周购买量 |
| `weekly_value` | 当周欧元销售额 |
| `order_count` | 当周订单数 |
| `days_since_last_purchase` | 距上次购买天数（上限 365） |
| `rolling_mean_units_4w` | 前 4 周滑动均值（shift(1) 防泄露） |
| `campaign_active` | 当周是否有促销 |
| `potential_gap_ratio` | 1 - 年累计销售/潜力值，衡量剩余空间 |

**静态特征（5 维）：** log(潜力值) + segment（target-mean编码） + province（target-mean编码） + 产品族（one-hot）

### 模型结构

```
(batch, 12, 7)
    ↓ GRU(hidden=32, layers=1)
(batch, 32)  ← 最后隐藏态
    ↓ 拼接静态特征
(batch, 37)
    ↓ Linear(64) → ReLU → Dropout(0.3) → Linear(1)
    ↓ BCEWithLogitsLoss(pos_weight=4.57)
参数总量：6,433（< 20k 设计上限）
```

### 数据划分（严格时间序划分，禁止随机 shuffle）

```
Train : window_end ≤ 2024-06-09   578,377 样本
Val   : 2024-07 ~ 2024-12         122,449 样本
Test  : 2025-01 ~ 2025-11         193,956 样本（193k 去重后）
```

同一客户同时出现在三个集合——正确，预测的是已知客户的未来行为，而非泛化到新客户。

### 评估结果

| 指标 | 验证集 | 测试集 |
|---|---|---|
| **AUROC** | **0.7736** | **0.7732** |
| AUPRC | 0.4168 | 0.4419 |
| Brier Score | 0.1867 | 0.1919 |
| Precision@100 | 0.88 | **0.99** |
| Precision@500 | 0.76 | 0.82 |
| Precision@1000 | 0.717 | 0.772 |
| Recall@1000 | 0.036 | 0.023 |

训练：epoch 15 早停（best epoch 10），Adam lr=1e-3，CPU 约 7 分钟。

**特征重要性（验证集 permutation AUROC 下降量）：**

| 排名 | 特征 | 重要性 |
|---|---|---|
| 1 | days_since_last_purchase | 0.053 |
| 2 | potential_gap_ratio | 0.037 |
| 3 | weekly_value | 0.029 |
| 4 | rolling_mean_units_4w | 0.015 |
| 5 | weekly_units | 0.012 |
| 6 | order_count | 0.008 |
| 7 | campaign_active | 0.002 |

### 产出文件

| 文件 | 说明 |
|---|---|
| `output/stage2/gru_model.pt` | 最优模型权重（epoch 10） |
| `output/stage2/f1_gru_predictions.parquet` | 8,349 pairs 的截面推断概率 |
| `output/stage2/f1_combined_alerts.parquet` | Stage1 + Stage2 合并预警 4,570 条 |
| `output/stage2/train_val_test_metrics.json` | 完整指标记录 |
| `output/stage2/f1_gru_report.md` | 模型报告 |

---

## 两方法头对头比较

在**相同 test set（193k 样本，正例率 12.3%）**上的公平对比：

| 方法 | AUROC | AUPRC | Precision@1000 |
|---|---|---|---|
| GRU（深度学习） | **0.7732** | **0.4419** | **0.772** |
| 超期天数 × 价值加权（统计代理） | 0.5755 | 0.1500 | 0.138 |
| 滚动均值（近期活跃度代理） | 0.5159 | 0.1249 | 0.119 |
| 纯超期天数 | 0.3575 | 0.0890 | 0.024 |

**关键发现：**

- GRU 在 Precision@1000 上领先统计方法约 **5.6 倍**（0.772 vs 0.138）
- 纯超期天数的 AUROC < 0.5，原因是无法区分"暂时沉睡"与"永久流失"客户，排序方向反转
- 两方法相关系数仅 -0.055，信号几乎正交——统计分捕捉"超期程度"，GRU 捕捉"序列购买模式"
- 当前集成公式（0.5 × rank + 0.5 × GRU）因两信号方向不一致，效果不如单独用 GRU

**统计基线的独特价值（不可被 GRU 替代）：**
- 可解释原因文本（"超出季度正常规律 3.5σ"）
- 冷启动鲁棒：仅需 1 次历史购买即可出分（GRU 需要 ≥ 16 周数据）
- 极端超期警报（如 460σ）对高价值客户是不可忽略的业务信号

---

## 当前进度 & 待办

### 已完成 ✅
- [x] Stage 0：全量数据清洗、周面板构建（含补零）、冷启动识别
- [x] Stage 1：三级层级统计基线，8,450 pairs 全覆盖评分，P1+P2=919 条
- [x] Stage 2：GRU 模型训练（AUROC 0.773），截面推断，特征重要性分析
- [x] 两方法头对头公平对比

### 待完成 / 可改进 🔧
- [ ] **集成优化**：当前 0.5+0.5 线性集成效果差，建议改为"分开展示双视角"或用 Stacking
- [ ] **F2 模块**：Técnico 产品（T1/T2）的低频购买预测（不同于 F1 的逻辑）
- [ ] **冷启动 F3**：2,940 个零历史客户的首次触达策略
- [ ] **产品族映射确认**：C1→Anestesia、C2→Bioseguridad 需赞助商验证
- [ ] **可视化 Dashboard**：销售人员可用的优先级列表界面
- [ ] **Recall 提升**：当前 Recall@1000 仅 2-4%，需扩大有效推荐覆盖范围

---

## 复现说明

```bash
# 固定随机种子：SEED=42 (numpy / random / torch 全部设置)
# 所有 Parquet 文件均可用 pandas 直接读取：
python3 -c "import pandas as pd; print(pd.read_parquet('output/stage1/f1_baseline_alerts.parquet').head())"
```

环境快照见 `output/env.txt`。
