# Smart Demand Signals 项目背景与问题描述

---

## 1. 项目背景

Inibsa 是一家面向牙科与医疗领域的制药和医疗产品企业，业务对象主要包括牙科诊所等 B2B 客户。该项目来自 Interhack BCN 2026 的 Inibsa challenge，主题是 **Smart Demand Signals**，即希望通过数据分析与智能系统，将客户的历史购买行为转化为可执行的商业信号。该挑战与企业的可持续增长、商业效率提升以及资源优化相关，目标不仅是提高销售执行效率，也包括更合理地安排销售人员时间、减少无效触达、提升供应链与商业运营效率。

Inibsa 拥有大约 6000 家牙科诊所客户，并积累了超过五年的客户与产品层级销售历史数据。这使得企业具备条件从历史交易数据中分析客户购买模式，并进一步识别潜在的补货需求、客户流失风险以及尚未被充分捕获的商业机会。

该项目的核心问题是：**如何从客户的购买历史中识别出需要商业干预的信号，并将这些信号转化为销售团队可以理解、可以排序、可以行动的提醒。**

换句话说，系统最终需要回答：

```
哪个客户需要被关注？
与哪个产品家族有关？
为什么需要关注？
应该什么时候联系？
优先级有多高？
```

---

## 2. 业务问题描述

Inibsa 的销售数据中存在两类明显不同的产品购买模式。

第一类是 **commodity products**，即标准化、重复购买频率较高的耗材类产品，例如麻醉、针头、消毒或生物安全相关产品。这类产品通常与诊所的日常消耗相关，客户购买行为相对稳定，适合分析补货周期、购买频率和需求缺口。不同客户对 Inibsa 的依赖程度并不相同：有些客户只是偶尔或少量购买，有些客户主要从 Inibsa 采购，还有一些客户可能在 Inibsa 和竞争对手之间分散采购。对于这类产品，关键问题是识别客户的真实需求与实际购买之间是否存在差距，并判断何时是联系客户、争取更多需求的合适时间。

第二类是 **technical products**，即技术型产品。这类产品的购买行为更加不规律，可能受到临床病例类型、医生专业方向、诊所业务结构以及竞争对手渗透情况的影响。对于这类产品，重点不只是预测下一次补货，而是识别客户购买行为是否出现持续恶化，例如购买频率下降、购买量下降、长期没有复购，或者相对于该客户历史模式出现异常活动。

因此，该 challenge 并不是简单地预测“客户是否会购买”，而是要区分不同产品类型下不同的商业含义：

```
对 commodity products：
关注补货需求、未满足需求、竞争对手分流机会。

对 technical products：
关注客户是否正在减少购买、停止购买或存在流失风险。
```

一个重要约束是，Inibsa 并不能直接观察客户是否购买了竞争对手产品，也无法完整看到客户通过间接渠道采购的情况。因此，系统不能简单判断“客户买少了就是流失”或“客户没有购买就是转向竞争对手”。相反，系统需要基于客户历史购买模式、产品类型、购买潜力和上下文信息进行间接推断。

---

## 3. 项目目标

该项目的目标是设计一个分析型解决方案，能够以每日更新的方式，在 **客户—产品家族—时间点** 的粒度上识别商业干预信号。也就是说，系统需要判断某个客户在某个产品家族上是否出现了值得销售团队采取行动的情况，并给出合适的联系时机。

该解决方案需要输出可解释、可行动的商业提醒，而不是单纯输出一个模型分数或概率。每条提醒至少应该包括：

```
客户
产品家族
提醒原因
建议联系时间
优先级
建议触达渠道
```

同时，系统需要具备可追溯性，即能够解释为什么某条提醒被生成，涉及哪些变量、规则或数据特征。

项目还要求考虑提醒之后的实际商业流程，例如：提醒由谁处理、在什么时间范围内处理、处理结果如何记录。这意味着该系统不仅是一个数据分析工具，也需要服务于真实销售流程。

---

## 4. 原始数据集概况

项目提供的数据主要由五类表组成，覆盖交易历史、产品信息、客户信息、客户潜力以及促销活动信息。整体数据粒度支持按客户、产品和时间进行分析。

### 4.1 Ventas：销售交易数据

`Ventas` 是核心交易表，记录客户在不同日期购买不同产品的历史交易信息。主要字段包括：

```
Num.Fact        发票或订单编号
Fecha           交易日期
Id. Cliente     客户 ID
Id. Producto    产品 ID
Unidades        购买数量
Valores_H       销售金额
```

该表是构建客户购买时间序列的基础。通过该表可以分析客户在不同产品上的购买频率、购买数量、购买金额、最后一次购买时间以及历史购买周期。

需要注意的是，销售数据中可能存在负数数量或负数金额，这通常对应退货、退款、调整或替换等情况。因此，负数交易不应被简单视为普通购买行为。

---

### 4.2 Productos：产品信息表

`Productos` 表描述产品层级结构和产品类型。主要字段包括：

```
Id.Prod             产品 ID
Bloque analítico    产品分析类型
Categoria_H         产品类别
Familia_H           产品家族
```

该表用于将交易中的单个 SKU 映射到更高层级的产品家族，并区分产品属于 commodity products 还是 technical products。

在该项目中，产品家族是非常重要的分析单位。虽然原始交易发生在 SKU 层级，但商业提醒通常需要在产品家族层级生成，因为销售团队更关注某一类产品整体的购买变化，而不是单个 SKU 的孤立波动。

---

### 4.3 Potencial：客户购买潜力表

`Potencial` 表记录客户在不同产品家族或类别上的潜在购买能力。主要字段包括：

```
Id.Cliente              客户 ID
Familia                 产品家族或业务名称
Categoria Productos     产品类别
Potencial_H             客户购买潜力
```

这里的 `Potencial_H` 可以理解为企业内部对客户理论需求或商业潜力的估计。它不是模型预测结果，而是原始数据中已经提供的业务先验信息。

该字段非常关键，因为它可以帮助判断客户的实际购买量是否低于其潜在需求。例如，一个高潜力客户如果实际购买量很低，可能意味着该客户的需求尚未被充分捕获，或者部分需求流向了竞争对手。

不过，业务文档也提示需要关注数据质量问题，例如某些客户潜力数据可能缺失、不完整或存在录入误差。因此，潜力值应作为商业参考，而不是绝对真值。

---

### 4.4 Clientes：客户信息表

`Clientes` 表记录客户基础信息。主要字段包括：

```
Id. Cliente     客户 ID
Unnamed: 1      客户分组或 segment code
Provincia       客户所在省份
```

该表提供客户地理位置和潜在分组信息，可以用于区域分析、客户分层，以及后续商业触达策略设计。

例如，客户所在省份可以支持地图可视化或区域机会分析；客户 segment code 可能用于区分不同类型客户或诊所群体。

---

### 4.5 Campañas：促销活动表

`Campañas` 表记录促销活动信息。主要字段包括：

```
Campaña         活动名称
Fecha inicio   活动开始日期
Fecha fin      活动结束日期
```

促销活动是重要的上下文信息，因为客户购买量在促销期间可能出现短期上升或波动。如果不考虑促销因素，系统可能会错误地把促销导致的购买高峰解释为长期需求变化，也可能错误判断促销结束后的下降。因此，促销信息需要作为解释客户购买行为的重要背景。

---

## 5. 数据与问题中的关键挑战

该项目的数据和业务场景具有较强的真实工业数据特征，主要挑战包括：

第一，客户购买行为并不总是规律。尤其是技术型产品，购买行为可能与具体临床病例、医生专业方向或偶发需求有关，因此不能简单把“长时间未购买”判断为客户流失。

第二，竞争对手购买行为不可直接观测。Inibsa 只能看到客户从自己这里购买的记录，无法完整看到客户是否从竞争对手或其他渠道采购。因此，所谓竞争对手分流只能通过购买潜力、历史购买模式和实际购买差距间接推断。

第三，原始数据可能存在缺失、异常和不一致。业务文档明确指出，系统需要考虑客户历史不完整、产品变化或替换、客户购买不规律、促销、异常订单、断货或商业政策变化等因素。

第四，最终输出不能只是分析结果，而必须能进入销售流程。企业真正需要的是可以被销售代表、电话销售或营销自动化系统使用的商业信号，并且这些信号需要具备优先级和解释性。

---

## 6. 问题总结

综上，本项目需要解决的是一个 B2B 商业智能问题：如何从牙科诊所多年的购买历史中，识别不同产品家族下的补货需求、客户流失风险和潜在商业机会，并将这些发现转化为可解释、可排序、可执行的销售提醒。

该问题的难点不在于单纯预测一个数值，而在于将复杂、稀疏、带有业务噪声的交易数据转化为销售团队真正能使用的决策信息。最终系统需要服务于日常商业运营，帮助企业回答：

```
今天应该联系哪些客户？
为什么联系他们？
联系哪个产品家族相关？
应该由哪个渠道联系？
哪些客户最值得优先处理？
```

# 预期交付目标

本项目最终预期交付两个主要成果：一份项目展示材料，以及一个可运行的 Dashboard Demo。前者用于清晰说明项目背景、开发过程、技术路线与量化结果；后者用于展示系统如何在真实商业场景中辅助销售团队进行日常决策。

---

## 1. 项目展示 Slides

第一项交付物是一份结构清晰的项目展示 slides，用于向评委、sponsor 或团队成员说明整个项目的设计逻辑、开发过程和结果。

Slides 不只是展示最终界面，而是需要完整讲清楚：

```
我们解决了什么问题？
为什么这个问题重要？
我们如何处理原始数据？
我们设计了哪些功能模块？
我们如何验证模型和 baseline 是否有效？
最终系统如何帮助销售团队行动？
```

### Slides 预期内容

Slides 需要包括以下部分：

---

### 1.1 项目背景与问题定义

说明 Inibsa 当前面临的问题：

- 客户购买行为复杂；
- commodity products 和 technical products 的购买逻辑不同；
- 企业看不到竞争对手销售数据；
- 销售团队需要可解释、可排序、可执行的商业信号；
- 目标是从历史购买数据中生成 Smart Demand Signals。

---

### 1.2 原始数据集介绍

介绍项目使用的数据表：

```
Ventas      销售交易数据
Productos   产品层级与产品类型
Clientes    客户信息
Potencial   客户购买潜力
Campañas    促销活动信息
```

说明数据粒度和分析单位：

```
client_id × product_family × time
```

并说明为什么最终分析重点放在产品家族层级，而不是单个 SKU 层级。

---

### 1.3 系统整体 Pipeline

展示从原始数据到最终商业提醒的完整流程：

```
Raw Data
→ Data Cleaning
→ Feature Engineering
→ F1 / F2 / F3 Signal Detection
→ Alert Generation
→ Prioritization
→ Dashboard
```

这里建议用一张 pipeline 图，让评委快速理解系统架构。

---

### 1.4 功能模块设计

Slides 需要说明 Dashboard 中的核心功能模块：

```
F1 Replenishment Intelligence
F2 Lost Customer Risk
F3 Capture Opportunity / Competitor Leakage
F4 Commercial Action Queue
```

每个模块需要说明：

- 输入是什么；
- 解决什么业务问题；
- 输出什么类型的商业 signal；
- 如何进入最终 action queue。

---

### 1.5 方法与开发过程

需要简要说明每个模块的开发逻辑。

例如：

```
F1:
statistical baseline + GRU sequential model

F2:
lost customer risk baseline based on volume drop, frequency drop, silence duration, trend decline

F3:
potential gap, utilization ratio, capture window, competitor leakage proxy

F4:
priority score and operational routing
```

注意，这部分不需要过度强调模型复杂性，而是要突出：

```
business logic + explainability + operational usefulness
```

---

### 1.6 量化评估结果

Slides 中需要包含模型或 baseline 的量化结果，用来证明系统不是纯概念 demo。

例如 F1 可以展示：

```
AUROC
AUPRC
Precision@TopK
Recall@TopK
Lift@TopK
```

其中，重点推荐展示：

```
Precision@Top100 / Top500
Lift@Top100 / Top500
```

因为这些指标最能说明：

```
销售团队如果按照系统推荐的 Top list 行动，命中率是否比随机选择更高。
```

如果有 F2/F3 的回测结果，也可以展示对应的：

```
AUROC
AUPRC
Precision@TopK
Risk / Opportunity ranking distribution
```

---

### 1.7 图表展示

Slides 中应包含必要图表，使结果更直观。

建议包括：

```
1. 数据规模图
2. 产品类型分布图
3. Pipeline 架构图
4. F1 模型评估曲线，例如 ROC / PR curve
5. Priority distribution
6. Top alerts 示例
7. Dashboard 截图
8. 客户购买时间线示例
```

这些图表的作用是让评委快速看到：

- 数据是真实的；
- 系统是可运行的；
- 模型有量化验证；
- 输出是商业上可解释的。

---

### 1.8 限制与未来改进

Slides 最后需要说明系统当前的限制，例如：

- competitor leakage 只能间接推断；
- potential 数据可能存在噪声；
- technical products 购买行为稀疏；
- 当前 demo 尚未接入真实 CRM；
- feedback loop 需要真实销售结果数据进一步训练。

这部分很重要，因为 sponsor 明确重视对 limitation 和 risk 的理解。

## 2. Demo：可运行 Dashboard

第二项交付物是一个可运行的 Dashboard Demo，用于展示 Smart Demand Signals 如何从原始交易数据中生成可解释、可排序、可行动的商业提醒。

当前前端原型已经包含一个较完整的控制面板结构，包括顶部状态栏、Top 5 客户预警、客户潜力榜单、购买概率/忠诚度榜单、月度销售趋势图、产品类别销售图以及西班牙地图视图。页面目前使用静态 mock data 渲染，代码中也注明后续可接入 Pandas DataFrame 生成的数据。

后续需要将当前原型从通用的 `PharmaDash` 调整为更贴合本项目的：

```
Smart Demand Signals Dashboard
```

或：

```
Inibsa Commercial Intelligence Dashboard
```

当前页面中的医院、药房、肿瘤、心脏病等 mock 示例应替换为本项目真实业务语境，例如牙科诊所、产品家族、补货提醒、流失客户风险和潜在竞争分流机会。

---

## 2.1 Dashboard 总体定位

Dashboard 的定位不是普通销售数据可视化页面，而是一个面向销售团队和商业管理者的：

```
Commercial Intelligence Dashboard
```

它需要帮助用户回答：

```
今天最应该联系哪些客户？
为什么联系？
涉及哪个产品家族？
属于补货、流失风险，还是竞争机会？
优先级多高？
建议采取什么行动？
```

因此，Dashboard 的核心不是展示全部数据，而是展示经过模型与规则处理后的 **Top commercial actions**。

---

## 2.2 页面语言切换：English / Spanish

由于 sponsor 和现场环境可能主要使用西班牙语，而团队展示和技术说明可能使用英语，因此 Dashboard 应支持 **英语 / 西班牙语切换**。

建议在页面右上角加入语言切换按钮：

```
EN / ES
```

用户点击后，页面中的核心 UI 文案应切换语言。

### 示例

| English | Spanish |
| --- | --- |
| Smart Demand Signals | Señales Inteligentes de Demanda |
| Dashboard | Panel de Control |
| Top 5 Actions | Top 5 Acciones |
| Replenishment Intelligence | Inteligencia de Reposición |
| Lost Customer Risk | Riesgo de Cliente Perdido |
| Capture Opportunity | Oportunidad de Captura |
| Competitor Leakage | Fuga Potencial a Competencia |
| Recommended Action | Acción Recomendada |
| Reason | Motivo |
| Priority | Prioridad |
| Potential Value | Valor Potencial |
| Status | Estado |

语言切换不一定需要复杂后端，可以在前端维护一个 translation dictionary，例如：

```
consttranslations= {
  en: {
    dashboardTitle:"Smart Demand Signals",
    topAlerts:"Top 5 Actions",
    recommendedAction:"Recommended Action"
  },
  es: {
    dashboardTitle:"Señales Inteligentes de Demanda",
    topAlerts:"Top 5 Acciones",
    recommendedAction:"Acción Recomendada"
  }
}
```

这样可以快速实现 demo 级别的双语切换。

---

## 2.3 当前 Dashboard 已包含的核心元素

当前网页原型已经具备以下结构：

### 1. 顶部 Header

页面顶部包含：

```
Dashboard 名称
系统运行状态
实时时钟
当前日期
```

这部分可以保留，但建议将名称从 `PharmaDash` 改为 `Smart Demand Signals` 或 `Inibsa Intelligence Dashboard`。当前页面 header 已经包含系统状态和实时时钟，适合作为商业系统原型。

---

### 2. Top 5 Clientes en Alerta

当前页面最核心的模块是：

```
Top 5 Clientes en Alerta
```

该模块展示前 5 个高优先级客户，并支持点击展开。每条 alert 已经包含：

```
客户名称
预警类型
变化幅度或风险 badge
解释说明
推荐行动
排名原因 / 商业影响
```

这个结构非常符合 sponsor 对 actionable alert 和 explainability 的要求。当前 accordion 展开后已经展示 `Explicacion`、`Accion recomendada` 和 `Razon del ranking`，后续可以直接替换为真实模型输出。

建议将该模块命名为：

英文：

```
Today’s Top 5 Commercial Actions
```

西班牙语：

```
Top 5 Acciones Comerciales de Hoy
```

---

### 3. Top Potencial

当前页面包含：

```
Top Potencial
```

用于展示客户潜力排名。这个模块可以保留，并与 `Potencial_H` 数据对应。

建议改成：

英文：

```
Top Potential Accounts
```

西班牙语：

```
Cuentas con Mayor Potencial
```

该模块可以服务于 F3 Capture Opportunity / Competitor Leakage，因为高潜力但低实际购买的客户通常是重要商业机会。

---

### 4. Top Fidelidad

当前页面包含：

```
Top Fidelidad
```

并展示 `F_in` 概率。这个名称目前略微不准确，因为我们的 F1 更关注补货优先级，而不是单纯忠诚度。

建议改成：

英文：

```
Top Replenishment Priorities
```

西班牙语：

```
Prioridades de Reposición
```

该模块应接入 F1 输出，例如：

```
reorder_probability
expected_reorder_window
f1_final_score
priority_level
```

---

### 5. Monthly Sales Chart

当前页面包含：

```
Volumen de Ventas Mensual
```

展示 2025 与 2024 月度销售对比。这个图可以保留作为总体业务背景图，但建议标题改成：

英文：

```
Monthly Sales Trend
```

西班牙语：

```
Tendencia Mensual de Ventas
```

如果时间有限，该图可以继续使用 aggregated sales data；如果时间充足，也可以改成 monthly alerts 或 monthly opportunity value。

---

### 6. Sales by Category Chart

当前页面包含：

```
Ventas por Categoría
```

但 mock 数据里的类别如 `Oncologia`、`Cardiologia`、`Antibioticos` 与本项目不匹配。

应替换为真实产品家族或业务名称，例如：

```
Anestesia
Bioseguridad
Biomateriales
```

或者使用匿名 family code：

```
Familia C1
Familia C2
Familia T1
Familia T2
```

建议标题为：

英文：

```
Sales by Product Family
```

西班牙语：

```
Ventas por Familia de Producto
```

---

### 7. Spain Map

当前页面包含：

```
Mapa de Ventas — España
```

使用 Plotly 绘制西班牙地图和销售热点。这个模块非常适合保留。

后续可以从“销售额热点”升级为：

```
Regional Alert Map
```

或：

```
Opportunity / Risk Heatmap
```

可展示：

```
各省份 F1 补货机会数量
各省份 F2 lost customer risk 数量
各省份 F3 capture opportunity 金额
```

英文标题：

```
Regional Opportunity Map
```

西班牙语标题：

```
Mapa Regional de Oportunidades
```

---

## 2.4 需要补充的 Dashboard 元素

当前原型视觉结构已经比较完整，但为了更符合项目目标，还需要补充以下功能。

### 1. F1 / F2 / F3 模块切换

建议加入 tab 或侧边导航：

```
Overview
F1 Replenishment
F2 Lost Customers
F3 Capture Opportunities
F4 Action Queue
```

西班牙语：

```
Resumen
F1 Reposición
F2 Clientes Perdidos
F3 Oportunidades de Captura
F4 Cola de Acciones
```

这样可以让评委清楚看到你们不是只做一个通用 dashboard，而是围绕 sponsor 问题设计了多个商业智能模块。

---

### 2. F2 Lost Customer Risk

新增一个模块展示疑似流失客户：

英文：

```
Lost Customer Risk
```

西班牙语：

```
Riesgo de Cliente Perdido
```

字段建议：

```
Client
Product Family
Last Purchase Date
Days Since Last Purchase
Volume Drop
Frequency Drop
Lost Status
Priority
Reason
```

其中 `lost_status` 可以包括：

```
Likely Lost
At Risk
Early Warning
Stable
```

西班牙语：

```
Probablemente perdido
En riesgo
Alerta temprana
Estable
```

---

### 3. F3 Capture Opportunity / Competitor Leakage

新增一个模块展示潜在竞争分流或未捕获需求：

英文：

```
Capture Opportunity
```

西班牙语：

```
Oportunidad de Captura
```

字段建议：

```
Client
Product Family
Potential Value
Observed Value
Potential Gap
Utilization Ratio
Capture Score
Recommended Action
Reason
```

注意措辞要谨慎，不应直接说客户一定购买了竞争对手产品，而应使用：

```
Potential competitor leakage
Possible unmet demand
Capture opportunity
```

西班牙语可以写：

```
Fuga potencial a competencia
Demanda no capturada
Oportunidad de captura
```

---

### 4. F4 Commercial Action Queue

当前页面已经有 Top 5 alert，但还没有完整的操作队列状态。

建议增加：

```
Commercial Action Queue
```

西班牙语：

```
Cola de Acciones Comerciales
```

字段：

```
Alert ID
Client
Signal Type
Product Family
Priority
Owner
Recommended Channel
Status
Due Date
```

状态可以包括：

```
Pending
Assigned
Contacted
Resolved
False Positive
```

西班牙语：

```
Pendiente
Asignado
Contactado
Resuelto
Falso positivo
```

这个模块能体现系统可以进入真实销售流程，而不只是分析图表。

---

## 2.5 数据接入方式

当前网页使用 JavaScript 中的 placeholder arrays，例如 `alertasData`、`potencialData`、`fidelidadData` 等。后续可以将这些静态数据替换为模型 pipeline 输出的 JSON 文件。当前代码已经明确说明这些数据未来可以从 Pandas DataFrame 生成。

推荐的数据接入方式：

```
Python / Pandas
→ 生成 alerts.json
→ 前端 main.html 读取 JSON
→ 渲染 dashboard
```

这样不需要一开始搭建复杂后端 API，也可以实现可运行 demo。

如果时间充足，再升级为：

```
FastAPI backend
→ /api/alerts
→ /api/f1
→ /api/f2
→ /api/f3
→ frontend fetch API
```

其中 API 的意思是：前端网页通过固定接口向后端请求数据，后端返回 JSON，前端再展示。

---

## 2.6 Demo 最终展示目标

最终 Dashboard Demo 应该展示一个完整商业流程：

```
原始交易数据
→ 模型和规则生成商业信号
→ Dashboard 展示 Top actions
→ 用户查看原因
→ 用户看到推荐行动
→ 用户可以按优先级处理客户
```

评委看到的不是一个普通网页，而是一个：

```
AI-powered Commercial Intelligence Dashboard
```

它应该让 sponsor 直观看到：

```
销售团队可以每天打开这个系统，
看到最应该联系的客户，
理解为什么系统推荐他们，
并基于优先级采取行动。
```

下面是可以直接接到你们文档里的 **Method / Implementation Methodology 技术文档部分**。目前只覆盖：

1. 数据处理
2. F1 Replenishment Intelligence
3. F2 Lost Customer Risk
4. F3 Capture Opportunity / Competitor Leakage

不包含 Dashboard 实现、不包含最终结果展示。

---

# Methodology / 技术实现方法

本项目的方法部分围绕从原始数据到商业信号的生成流程展开。整体目标是将原始交易数据、产品信息、客户信息、购买潜力和促销活动信息转化为可用于 Dashboard 展示的结构化 alert 表。

当前实现重点包括四个部分：

```text
Stage 0: Data Preprocessing
F1: Replenishment Intelligence
F2: Lost Customer Risk
F3: Capture Opportunity / Competitor Leakage
```

整体处理逻辑如下：

```text
Raw Data
→ Data Cleaning
→ Data Integration
→ Weekly / Monthly Panel Construction
→ Feature Engineering
→ F1 / F2 / F3 Signal Generation
→ Priority Scoring
→ Explainable Alert Output
```

---

# 1. Data Preprocessing

## 1.1 原始数据输入

系统使用五个原始数据表：

```text
Ventas.csv
Productos.csv
Potencial.csv
Clientes.csv
Campañas.csv
```

其中：

| 数据表       | 作用                |
| --------- | ----------------- |
| Ventas    | 销售交易历史            |
| Productos | 产品层级、产品家族、产品类型    |
| Potencial | 客户在不同产品家族上的购买潜力   |
| Clientes  | 客户基础信息、地区、segment |
| Campañas  | 促销活动时间窗口          |

数据处理的核心目标是将这些分散的数据表整理成统一的分析数据结构，为 F1、F2 和 F3 模块提供输入。

---

## 1.2 字段标准化

由于不同表中的字段命名并不完全一致，首先需要进行字段标准化。所有客户、产品、时间和金额字段统一为 canonical schema。

示例：

```text
Id. Cliente / Id.Cliente → client_id
Id. Producto / Id.Prod   → product_id
Fecha                    → date
Unidades                 → units
Valores_H                → sales_value
Familia_H / Familia      → product_family
Bloque analítico         → product_block
Potencial_H              → potential_value
Provincia                → province
Unnamed: 1               → segment_code
```

其中：

```text
client_id
product_id
```

统一转为字符串类型，并去除首尾空格，避免 merge 时出现 ID 格式不一致问题。

日期字段统一解析为 `datetime` 格式。

---

## 1.3 产品家族映射

`Productos` 表中的产品家族使用匿名代码，例如：

```text
Familia C1
Familia C2
Familia T1
Familia T2
```

而 `Potencial` 表中的产品家族使用业务名称，例如：

```text
Anestesia
Bioseguridad
Biomateriales
```

由于二者不能直接匹配，需要建立一个产品家族映射表。

当前默认假设为：

```text
Familia C1 → Anestesia
Familia C2 → Bioseguridad
Familia T1 → Biomateriales
Familia T2 → Biomateriales
```

该映射在代码中应作为一个单独的 dictionary 保存，例如：

```python
MAP_FAMILY_TO_BUSINESS = {
    "Familia C1": "Anestesia",
    "Familia C2": "Bioseguridad",
    "Familia T1": "Biomateriales",
    "Familia T2": "Biomateriales"
}
```

该映射是一个业务假设，需要在后续与 sponsor 确认。因此，系统需要同时保留两个字段：

```text
product_family       原始匿名产品家族代码
product_family_biz   映射后的业务产品家族名称
```

其中：

```text
product_family
```

用于模型分组和产品类型判断；

```text
product_family_biz
```

用于与 `Potencial` 表进行匹配。

---

## 1.4 销售交易清洗

`Ventas` 表是整个系统的核心数据源。在清洗阶段需要处理以下问题。

### 缺失值处理

删除以下关键字段缺失的交易记录：

```text
client_id
product_id
date
```

这些字段缺失会导致无法进行客户、产品或时间维度分析。

---

### 负数交易处理

原始销售数据中可能存在负数数量或负数金额：

```text
units < 0
sales_value < 0
```

这些记录通常代表：

```text
退货
退款
订单修正
产品替换
```

因此，不应简单删除负数记录。

处理规则如下：

```text
is_return = True if units < 0 or sales_value < 0
```

在聚合时保留两种口径：

```text
net_units  = sum(units)
net_value  = sum(sales_value)

gross_units = sum(max(units, 0))
gross_value = sum(max(sales_value, 0))
```

对于补货周期计算，负数交易不应被视为真实补货事件，因此 F1 中的购买事件只使用：

```text
units > 0
```

---

### 重复记录处理

对以下字段完全相同的记录进行去重：

```text
Num.Fact
client_id
product_id
date
```

---

### 异常单价过滤

计算单价：

```text
unit_price = sales_value / units
```

如果出现极端异常值，例如：

```text
abs(unit_price) > 10000
```

则可视为录入错误并删除或单独标记。

---

## 1.5 主表合并

构建交易级别主表：

```text
df_master =
Ventas
LEFT JOIN Productos ON product_id
LEFT JOIN Clientes  ON client_id
```

合并后每一条交易记录应包含：

```text
client_id
product_id
date
units
sales_value
product_family
product_family_biz
product_block
category
province
segment_code
```

注意：`Potencial` 不建议直接 merge 到 transaction-level 表中，因为一名客户在一个产品家族上可能对应一个 potential 值，而交易表是多条交易记录。直接 merge 可能造成重复和行数膨胀。

因此，`Potencial` 应作为独立 lookup table 保存：

```text
df_potential:
client_id
product_family_biz
potential_value
```

后续在 client-family 粒度计算特征时再进行查找。

---

## 1.6 Weekly Panel 构建

F1 Replenishment Intelligence 使用 weekly panel 作为核心输入。

分析粒度为：

```text
client_id × product_family × week_start
```

其中 `week_start` 为 ISO week 的周一。

对每个客户-产品家族-周聚合以下字段：

```text
weekly_units      = sum(units where units > 0)
weekly_value      = sum(sales_value where sales_value > 0)
order_count       = number of unique invoices
return_units      = sum(abs(units) where units < 0)
had_purchase      = 1 if order_count > 0 else 0
```

为保证时间序列特征正确，需要对每个曾经发生过交易的：

```text
client_id × product_family
```

补齐完整周序列，从最早日期到数据结束日期。缺失周填充为：

```text
weekly_units = 0
weekly_value = 0
order_count = 0
return_units = 0
had_purchase = 0
```

补齐缺失周非常关键，否则 rolling mean、purchase interval 和 deep learning sequence input 都会产生错误。

---

## 1.7 Campaign Flag 构建

根据 `Campañas` 表，将每个 week 标记是否与促销活动重叠。

如果某一周：

```text
[week_start, week_start + 6 days]
```

与任一 campaign 时间窗口有交集，则：

```text
campaign_active = 1
```

否则：

```text
campaign_active = 0
```

该字段用于避免将促销活动导致的短期购买波动误判为长期购买模式变化。

---

## 1.8 Cold-start Clients

`Potencial` 表中可能存在部分客户在销售交易表中没有出现过。这类客户代表：

```text
有商业潜力
但当前没有历史购买记录
```

这类客户不适合用于 F1 补货预测，因为没有历史购买行为可用于推断补货周期。

因此，需要单独输出：

```text
df_cold_clients
```

这部分客户更适合用于 F3 Capture Opportunity 模块，而不是 F1。

---

# 2. F1 — Replenishment Intelligence

## 2.1 模块目标

F1 的目标是识别哪些客户在 commodity products 上可能即将需要补货。

F1 主要处理：

```text
product_block == "Commodities"
```

即具有重复购买和稳定消耗特征的产品家族。

业务问题可以表述为：

```text
某个客户在某个产品家族上，是否已经接近或超过其正常补货周期？
是否应该提醒销售团队联系该客户？
```

---

## 2.2 分析粒度

F1 的分析粒度为：

```text
client_id × product_family
```

时间粒度为：

```text
week
```

选择 weekly 而不是 daily 的原因是：

```text
daily 数据过于稀疏；
weekly 能保留补货节奏；
weekly 适合构造序列模型输入。
```

---

## 2.3 Seasonality-aware Statistical Baseline

F1 的基础方法是一个考虑季节性的统计 baseline。

核心思想是：

```text
不要只看客户全年平均购买周期；
应该考虑当前季度下该客户的正常购买波动。
```

例如，夏季可能存在假期效应，客户购买间隔变长是正常现象；而在正常运营季度，同样的沉默时间可能代表更高补货风险。

---

### 2.3.1 购买间隔计算

对每个：

```text
client_id × product_family
```

提取所有 `had_purchase == 1` 的 week_start。

按时间排序后计算连续购买间隔：

```text
interval_days[i] = purchase_date[i] - purchase_date[i-1]
```

每个 interval 根据结束日期所属季度打标签：

```text
Q1: Jan-Mar
Q2: Apr-Jun
Q3: Jul-Sep
Q4: Oct-Dec
```

---

### 2.3.2 分层统计与 fallback

为解决客户历史购买数据不足的问题，使用多层 fallback 机制。

Level A：

```text
client_id × product_family × quarter
```

用于计算该客户在该产品家族、该季度下的平均购买周期。

使用条件：

```text
n_purchases_cfq ≥ 3
```

Level B：

```text
client_id × product_family
```

用于计算该客户在该产品家族上的全年平均购买周期。

使用条件：

```text
n_purchases_cf ≥ 4
```

Level C：

```text
product_family × quarter
```

或：

```text
segment_code × product_family × quarter
```

作为最终 fallback。

该层代表同类产品或同类客户群体的平均补货周期。

---

### 2.3.3 补货延迟评分

设定 scoring date，例如最新数据之后的一周。

对每个客户-产品家族组合计算：

```text
last_purchase_date
days_since_last_purchase
expected_interval
expected_reorder_date
delay
```

其中：

```text
delay = days_since_last_purchase - expected_interval
```

如果：

```text
delay <= 0
```

说明客户尚未超过预期补货窗口。

如果：

```text
delay > 0
```

说明客户已经超过预期补货时间。

将 delay 进行标准化：

```text
seasonal_time_score = max(0, delay / std_interval)
```

其中 `std_interval` 来自 Level A/B/C 的对应 fallback 层，并设置最小值：

```text
std_interval = max(std_interval, 3 days)
```

防止标准差过小导致分数爆炸。

---

### 2.3.4 商业价值因子

补货优先级不应只由时间延迟决定，还需要考虑商业价值。

商业价值因子来自两部分：

```text
potential_value
historical_value_12m
```

其中：

```text
raw_value = max(potential_value, historical_value_12m)
```

由于商业价值分布通常高度偏斜，使用 log normalization：

```text
value_factor = minmax(log1p(raw_value))
```

最终 baseline 补货分数为：

```text
replenishment_score = seasonal_time_score × value_factor
```

---

### 2.3.5 Priority Level

根据 `replenishment_score` 对所有候选 alert 排序，并划分优先级：

```text
P1 Critical : top 5%
P2 High     : next 15%
P3 Medium   : next 30%
P4 Low      : remaining
```

如果：

```text
seasonal_time_score == 0
```

则标记为：

```text
On track
```

---

### 2.3.6 F1 Baseline 输出

F1 baseline 输出表包含：

```text
client_id
product_family
product_family_biz
province
current_quarter
last_purchase_date
days_since_last_purchase
expected_interval
expected_reorder_date
delay
seasonal_time_score
value_factor
replenishment_score
priority_level
confidence_level
reason
```

其中 `reason` 为模板化解释文本，例如：

```text
Client X has not ordered Anestesia in 42 days.
Their typical Q4 reorder cycle is 30 days.
This delay is 1.8 standard deviations beyond the expected pattern.
Because the client has high commercial value, priority is P1.
```

---

## 2.4 GRU Sequential Model

除统计 baseline 外，F1 还使用 GRU 构建深度序列模型。

GRU 的作用不是取代统计 baseline，而是提供一个基于历史购买序列的补充概率信号。

---

### 2.4.1 预测任务定义

将 F1 建模为 binary classification：

```text
给定过去 L 周购买行为，
预测未来 4 周内是否会再次购买该产品家族。
```

标签定义：

```text
y_t = 1 if had_purchase in weeks [t+1, t+2, t+3, t+4]
y_t = 0 otherwise
```

选择 4 周预测窗口的原因是：

```text
4 周是合理的销售触达提前期；
比预测具体购买日期更稳定；
适合转化为补货提醒。
```

---

### 2.4.2 输入特征

每个样本使用过去 12 周作为 lookback window。

时间序列特征包括：

```text
weekly_units
weekly_value
order_count
days_since_last_purchase
rolling_mean_units_4w
campaign_active
potential_gap_ratio
```

静态特征包括：

```text
log1p(potential_value)
segment_code
province
product_family
```

其中数值特征使用训练集统计量进行标准化，避免数据泄漏。

---

### 2.4.3 数据切分

采用时间切分，而不是随机切分：

```text
Train: 2021-04-01 → 2024-06-30
Val:   2024-07-01 → 2024-12-31
Test:  2025-01-01 → 2025-11-30
```

采用 time-based split 的原因是：

```text
业务场景中模型总是用过去预测未来；
随机切分会导致时间信息泄漏；
同一客户可以出现在 train/val/test 中，但时间不能混淆。
```

---

### 2.4.4 模型结构

GRU 模型结构如下：

```text
Input: 12-week sequence × feature_dim
GRU hidden_size = 32
Take last hidden state
Concatenate static features
MLP classifier
Output: reorder_probability
```

模型输出：

```text
reorder_probability ∈ [0, 1]
```

表示该客户在未来 4 周内复购该产品家族的概率。

---

### 2.4.5 评估指标

F1 的开发评估不以 accuracy 为主，因为未来购买事件可能存在类别不平衡。

使用以下指标：

```text
AUROC
AUPRC
Positive-class F1
Precision@TopK
Recall@TopK
Lift@TopK
Brier Score
```

其中：

```text
Precision@TopK
Lift@TopK
```

最能反映商业排序价值。

因为最终系统不是对所有客户做静态分类，而是生成优先联系列表。

---

### 2.4.6 F1 最终融合

统计 baseline 输出：

```text
replenishment_score
```

GRU 输出：

```text
reorder_probability
```

二者可以组合为最终 F1 分数：

```text
f1_final_score =
0.5 × normalized_replenishment_score
+
0.5 × reorder_probability
```

为了避免某一分数尺度主导最终排序，更稳妥的方式是使用 rank normalization：

```text
f1_final_score =
0.5 × rank_percentile(replenishment_score)
+
0.5 × rank_percentile(reorder_probability)
```

最终输出：

```text
client_id
product_family
reorder_probability
replenishment_score
f1_final_score
priority_level
reason
```

---

# 3. F2 — Lost Customer Risk

## 3.1 模块目标

F2 的目标是识别疑似流失客户或高流失风险客户。

F2 主要关注 technical products，即：

```text
product_block == "Productos Técnicos"
```

这类产品购买频率低、波动大，不能简单用“长时间没买”判断客户流失。

因此，F2 的问题定义为：

```text
客户过去购买过某个技术产品家族，
但最近购买频率、购买量或活跃度是否出现明显下降？
```

---

## 3.2 数据粒度

F2 推荐使用 monthly panel，而不是 weekly panel。

分析粒度为：

```text
client_id × product_family × month
```

原因是：

```text
technical products 购买频率低；
weekly 粒度过于稀疏；
monthly 更适合观察长期恶化趋势。
```

对每个客户-产品家族-月份聚合：

```text
monthly_units
monthly_value
order_count
had_purchase
```

同样需要补齐缺失月份为 0。

---

## 3.3 历史窗口与近期窗口

对每个客户-产品家族组合划分两个窗口：

```text
historical_window = 过去较长周期
recent_window     = 最近 3-6 个月
```

推荐设置：

```text
historical_window = 最近 24 个月中除去最近 6 个月
recent_window = 最近 6 个月
```

通过比较历史窗口和近期窗口，判断客户购买行为是否恶化。

---

## 3.4 F2 核心特征

### 3.4.1 Volume Drop

计算历史平均购买量和近期平均购买量：

```text
historical_avg_units
recent_avg_units
```

购买量下降比例：

```text
volume_drop_ratio =
max(0, historical_avg_units - recent_avg_units)
/
historical_avg_units
```

该指标反映客户购买量是否下降。

---

### 3.4.2 Frequency Drop

计算历史购买月份比例和近期购买月份比例：

```text
historical_purchase_rate =
months_with_purchase_historical / total_historical_months

recent_purchase_rate =
months_with_purchase_recent / total_recent_months
```

购买频率下降：

```text
frequency_drop_ratio =
max(0, historical_purchase_rate - recent_purchase_rate)
```

该指标反映客户是否从“经常购买”变成“不常购买”。

---

### 3.4.3 Silence Score

计算客户当前沉默时间是否超过历史正常沉默范围。

首先计算历史购买间隔，例如：

```text
historical_p90_interval
```

然后计算：

```text
days_since_last_purchase
```

沉默分数：

```text
silence_score =
days_since_last_purchase / historical_p90_interval
```

如果：

```text
silence_score > 1
```

表示当前沉默时间已经超过该客户历史上 90% 的正常间隔。

---

### 3.4.4 Trend Score

对近期月份购买量进行线性趋势拟合：

```text
monthly_units ~ time
```

如果 slope 为负，说明购买量存在下降趋势：

```text
trend_score = max(0, -trend_slope)
```

---

## 3.5 Lost Customer Score

将多个信号组合为 F2 风险分数：

```text
lost_customer_score =
0.35 × volume_drop_score
+
0.35 × frequency_drop_score
+
0.20 × silence_score_normalized
+
0.10 × trend_score_normalized
```

再加入商业价值因子：

```text
f2_priority_score =
lost_customer_score × value_factor
```

其中：

```text
value_factor = normalized log1p(max(potential_value, historical_12m_value))
```

---

## 3.6 Lost Status

根据 `lost_customer_score` 和不同特征组合，将客户标记为：

```text
Likely Lost
At Risk
Early Warning
Stable
```

示例规则：

```text
Likely Lost:
silence_score > 1.5 and recent_purchase_rate == 0

At Risk:
volume_drop_ratio > 0.5 or frequency_drop_ratio > 0.5

Early Warning:
negative trend but recent activity still exists

Stable:
no significant deterioration
```

---

## 3.7 F2 输出表

F2 输出表包括：

```text
client_id
province
product_family
product_family_biz
last_purchase_date
days_since_last_purchase
historical_avg_units
recent_avg_units
volume_drop_ratio
historical_purchase_rate
recent_purchase_rate
frequency_drop_ratio
historical_p90_interval
silence_score
trend_score
lost_customer_score
value_factor
f2_priority_score
priority_level
lost_status
confidence_level
reason
```

Reason 示例：

```text
Client X shows lost customer risk in Biomateriales.
Recent 6-month purchase volume is 62% below historical baseline.
Purchase frequency dropped from 0.42 to 0.10 months with orders.
The current silence period is 1.4 times longer than its historical normal range.
Priority is P1 due to high commercial value.
```

---

## 3.8 F2 评估方式

如果没有真实流失标签，可以通过历史回测构造 proxy label。

例如在某个观察点 t：

```text
y = 1 if client-family has no purchase in next 6 months
        OR next 6-month value drops > 60% vs historical baseline

y = 0 otherwise
```

评估指标：

```text
AUROC
AUPRC
Positive-class F1
Precision@TopK
Lift@TopK
```

其中 TopK 指标用于判断最高风险客户排序是否有效。

---

# 4. F3 — Capture Opportunity / Competitor Leakage

## 4.1 模块目标

F3 的目标是识别潜在商业机会，尤其是：

```text
高潜力但低实际购买的客户
```

这可能意味着：

```text
客户需求尚未被充分捕获；
部分需求可能流向竞争对手；
当前存在商业拓展机会。
```

需要注意，竞争对手购买数据不可直接观测，因此 F3 不应输出确定性判断：

```text
客户购买了竞争对手产品
```

而应输出更谨慎的商业信号：

```text
Potential competitor leakage
Possible unmet demand
Capture opportunity
```

---

## 4.2 分析粒度

F3 分析粒度为：

```text
client_id × product_family
```

时间窗口推荐使用：

```text
recent 12 months
recent 12 weeks
```

其中 12 个月用于长期潜力利用率分析，12 周用于近期 capture window 分析。

---

## 4.3 Potential Utilization Ratio

F3 的核心特征是客户潜力利用率。

定义：

```text
observed_value_12m = last 12-month observed purchase value
potential_value = potential table value
```

潜力利用率：

```text
utilization_ratio =
observed_value_12m / potential_value
```

潜力缺口：

```text
potential_gap =
max(0, potential_value - observed_value_12m)
```

如果：

```text
potential_value is high
utilization_ratio is low
```

说明该客户存在未捕获需求。

---

## 4.4 Recent Expected vs Observed Gap

为了生成更及时的商业机会信号，可以将 annual potential 转换为近期 expected value。

例如 12 周期望值：

```text
expected_12w_value =
potential_value / 52 × 12
```

近期实际购买：

```text
observed_12w_value =
sum(weekly_value over last 12 weeks)
```

近期缺口：

```text
recent_gap =
max(0, expected_12w_value - observed_12w_value)
```

该特征用于判断近期是否出现未捕获需求。

---

## 4.5 Promiscuous Customer Proxy

由于无法直接看到竞争对手购买，F3 使用间接信号构造 promiscuous customer proxy。

可能的信号包括：

```text
high potential
nonzero but low observed purchase
irregular purchase pattern
repeated under-utilization
```

一个简单的代理分数：

```text
promiscuity_score =
high_potential_score
× low_utilization_score
× intermittent_purchase_score
```

其中：

```text
low_utilization_score = 1 - utilization_ratio
```

`intermittent_purchase_score` 可以由购买间隔波动或购买活跃度不稳定性计算。

这类客户与完全没有购买记录的 cold-start client 不同。他们至少曾经购买过 Inibsa 产品，但购买量低于潜力，因此更可能存在 capture opportunity。

---

## 4.6 Capture Window Score

F3 不只需要判断谁有机会，还需要判断何时是触达窗口。

因此可以结合 F1 的补货信号：

```text
capture_window_score =
opportunity_score × replenishment_urgency
```

其中：

```text
opportunity_score
```

来自 potential gap 和 utilization ratio；

```text
replenishment_urgency
```

来自 F1 的补货窗口或时间延迟。

这表示：

```text
客户有潜力，
当前又接近补货时间，
因此是较好的商业捕获窗口。
```

---

## 4.7 Opportunity Score

F3 最终商业机会分数可定义为：

```text
opportunity_score =
0.40 × potential_gap_score
+
0.30 × low_utilization_score
+
0.20 × promiscuity_score
+
0.10 × capture_window_score
```

再乘以商业价值权重：

```text
f3_priority_score =
opportunity_score × value_factor
```

其中：

```text
value_factor = normalized log1p(potential_value)
```

---

## 4.8 Priority Level

按 `f3_priority_score` 排序，划分：

```text
P1 Critical : top 5%
P2 High     : next 15%
P3 Medium   : next 30%
P4 Low      : remaining
```

---

## 4.9 F3 输出表

F3 输出表包括：

```text
client_id
province
product_family
product_family_biz
potential_value
observed_value_12m
expected_12w_value
observed_12w_value
utilization_ratio
potential_gap
recent_gap
promiscuity_score
capture_window_score
opportunity_score
f3_priority_score
priority_level
opportunity_type
reason
```

`opportunity_type` 可以包括：

```text
High Potential Underutilization
Potential Competitor Leakage
Capture Window
Cold-start Opportunity
```

Reason 示例：

```text
Client X has high potential in Anestesia but only 22% utilization in the last 12 months.
The recent 12-week observed value is below the expected level based on annual potential.
This suggests possible unmet demand or competitor leakage.
Because the client is close to a replenishment window, this is ranked as a P1 capture opportunity.
```

---

## 4.10 F3 评估方式

F3 的真实 ground truth 较难获得，因为没有竞争对手购买数据。因此，评估更适合使用 proxy backtesting 和业务合理性指标。

可选评估方式包括：

### 未来购买增长标签

在观察点 t，如果未来 3-6 个月该客户购买额显著上升，则认为之前的 opportunity signal 有一定有效性。

```text
y = 1 if future_6m_value > recent_6m_value × 1.5
y = 0 otherwise
```

### TopK Opportunity Validation

评估模型排序前 K 个客户在未来是否出现购买增长：

```text
Precision@TopK
Lift@TopK
Average future value growth in TopK
```

### Business Plausibility Check

检查 Top opportunity 是否具有合理特征：

```text
high potential
low utilization
nonzero purchase history
recent underperformance
```

由于 F3 本身是 indirect inference，评估时需要明确说明：

```text
F3 does not directly observe competitor sales.
It evaluates potential unmet demand and possible leakage using indirect commercial signals.
```

---

# 5. 输出文件结构

当前 method 阶段建议输出以下文件：

```text
output/stage0/
    df_master.parquet
    df_weekly.parquet
    df_monthly.parquet
    df_potential.parquet
    df_cold_clients.parquet
    preprocessing_report.md

output/f1/
    f1_baseline_alerts.parquet
    f1_gru_predictions.parquet
    f1_combined_alerts.parquet
    f1_evaluation_report.md

output/f2/
    f2_lost_customer_alerts.parquet
    f2_diagnostics.md

output/f3/
    f3_capture_opportunity_alerts.parquet
    f3_diagnostics.md
```

---

# 6. Methodology Summary

当前方法设计可以概括为：

```text
Data Preprocessing:
将原始交易、产品、客户、潜力和促销数据统一为可分析面板。

F1:
针对 commodity products，结合季节性统计 baseline 和 GRU 序列模型，生成补货优先级。

F2:
针对 technical products，基于购买量下降、购买频率下降、异常沉默期和下降趋势，识别 lost customer risk。

F3:
基于 potential value 与 observed purchase 的差距，识别未捕获需求、潜在竞争分流和 capture opportunity。
```

方法设计的核心原则是：

```text
不仅输出模型分数，
还要输出可解释 reason、
商业优先级 priority、
以及可进入 Dashboard 的 alert 表。
```
Demo 前后端架构与解释层设计

在完成 F1、F2、F3 各个分析模块后，项目需要将模型与规则生成的结果展示在一个可交互的 Dashboard 中。为了让 Demo 不只是静态网页，而是更接近真实商业系统，我们计划采用一个相对模块化、可扩展、可动态更新的前后端架构。

整体思路是：

Data / Model Pipeline
→ Structured Alert Tables
→ Backend API
→ Gemini Explanation Layer
→ Frontend Dashboard

其中，数据处理与模型模块负责生成结构化商业信号；后端负责管理这些信号并提供接口；Gemini API 负责将结构化结果转化为自然语言解释；前端 Dashboard 负责展示、筛选、展开和交互。

1. 总体架构选择

我们计划采用：

Python FastAPI Backend
+ Frontend Dashboard
+ JSON-based Alert Data
+ Gemini Explanation Layer

选择 FastAPI 的原因是：

1. 与 Python 数据处理和模型 pipeline 兼容性高
2. 可以直接读取 parquet / csv / json 输出文件
3. 易于构建清晰的 API endpoint
4. 适合后续接入 Gemini API
5. 比纯静态网页更动态，也比完整企业系统更轻量

在当前 hackathon 阶段，系统不需要复杂数据库或完整 CRM 集成。后端可以先从本地生成的 JSON 或 parquet 文件读取结果，再提供给前端使用。这样既保持结构清晰，也避免开发复杂度过高。

2. 数据流设计

整个系统的数据流可以表示为：

Raw Data
→ Preprocessing
→ F1 / F2 / F3 Modules
→ Alert Tables
→ Unified Alert JSON
→ Backend API
→ Frontend Dashboard

F1、F2、F3 分别输出自己的 alert 表：

f1_combined_alerts.parquet
f2_lost_customer_alerts.parquet
f3_capture_opportunity_alerts.parquet

之后统一转换为一个标准化 alert 数据结构：

all_alerts.json

该文件将作为 Dashboard 的主要数据源。

3. 标准化 Alert Object

为了让前端能够统一展示不同模块的结果，每条 alert 需要转换为统一结构。

示例结构如下：

{
  "alert_id": "F1-000123",
  "module": "F1",
  "alert_type": "Replenishment Intelligence",
  "client_id": "10234",
  "province": "Barcelona",
  "product_family": "Familia C1",
  "product_family_biz": "Anestesia",
  "priority_level": "P1",
  "priority_score": 0.92,
  "urgency": "High",
  "recommended_action": "Contact this client within 7 days",
  "recommended_channel": "Telesales",
  "status": "Pending",

  "model_outputs": {
    "baseline_score": 0.88,
    "gru_probability": 0.81,
    "final_score": 0.92
  },

  "evidence": {
    "facts": [
      "42 days since last purchase",
      "Typical Q4 reorder interval is 30 days",
      "High commercial value"
    ]
  },

  "ai_summary": "",
  "ai_recommendation": ""
}

不同模块可以有不同的 model_outputs 和 evidence 字段。例如：

F1:
reorder_probability, expected_reorder_date, days_since_last_purchase

F2:
lost_customer_score, silence_score, volume_drop_ratio, lost_status

F3:
potential_value, observed_value, utilization_ratio, potential_gap

但前端只需要读取统一字段：

client_id
module
alert_type
priority_level
priority_score
reason
recommended_action
status

这样可以保证系统模块化。

4. Backend API 设计

后端使用 FastAPI 提供简单接口。

计划 endpoint 包括：

GET /api/overview
GET /api/alerts
GET /api/alerts/top5
GET /api/alerts/{alert_id}
GET /api/f1
GET /api/f2
GET /api/f3
POST /api/alerts/{alert_id}/status

各接口作用如下：

API	作用
/api/overview	返回首页 KPI 数据
/api/alerts	返回所有 alert
/api/alerts/top5	返回今日 Top 5 actions
/api/alerts/{alert_id}	返回某条 alert 的详细信息
/api/f1	返回 F1 补货提醒
/api/f2	返回 F2 lost customer risk
/api/f3	返回 F3 capture opportunities
/api/alerts/{alert_id}/status	更新 alert 状态

这样前端可以根据用户点击动态请求数据，而不是一次性写死在 HTML 中。

5. Frontend Dashboard 设计

前端可以基于当前已有的 main.html 原型继续修改。当前页面已经具备 Dashboard 的基本视觉结构，包括 Top 5 alerts、潜力榜单、趋势图、类别图和地图。

后续计划将其改造为：

Smart Demand Signals Dashboard

主要页面区域包括：

1. Executive Overview
2. Top 5 Commercial Actions
3. F1 Replenishment Intelligence
4. F2 Lost Customer Risk
5. F3 Capture Opportunity
6. F4 Commercial Action Queue
7. Regional Map
8. Explainability Panel

前端主要功能包括：

1. 展示今日 Top 5 actions
2. 按 F1 / F2 / F3 筛选 alert
3. 展示 priority level 和 score
4. 点击某条 alert 展开详情
5. 展示模型输出、证据字段和 AI 解释
6. 更新 alert 状态，例如 Pending / Contacted / Resolved
7. 支持 English / Spanish 语言切换
6. Gemini Explanation Layer

Gemini API 不用于决定 alert 是否生成，也不用于替代 F1、F2、F3 的模型判断。

Gemini 的作用是：

将结构化 alert 数据转化为销售团队容易理解的自然语言解释和行动建议。

也就是说：

F1 / F2 / F3 模型负责判断
Gemini 负责解释
Dashboard 负责展示

这样可以避免大模型凭空生成结论，也能保持系统的可追溯性。

7. Gemini Prompt 设计

每条 alert 可以根据结构化字段生成 prompt。

示例：

You are a commercial intelligence assistant for a dental product company.

Generate a concise sales-friendly explanation for the following alert.
Use only the structured data provided.
Do not invent facts.
If the evidence is indirect, mention uncertainty.

Alert:
- Module: F1 Replenishment Intelligence
- Client ID: 10234
- Product family: Anestesia
- Priority: P1
- Days since last purchase: 42
- Expected reorder interval: 30 days
- GRU reorder probability: 0.81
- Commercial value: high
- Recommended channel: Telesales

Output:
1. Short explanation
2. Recommended action
3. Reason for priority
4. Caveat or uncertainty

生成结果可以填入：

ai_summary
ai_recommendation
ai_caveat

然后前端在用户展开 alert 时展示。

8. English / Spanish Language Switch

由于团队技术说明可能使用英语，而 sponsor 和现场展示可能需要西班牙语，Dashboard 计划支持：

EN / ES

语言切换。

前端可以维护一个简单的 translation dictionary：

const translations = {
  en: {
    topActions: "Top 5 Commercial Actions",
    replenishment: "Replenishment Intelligence",
    lostCustomers: "Lost Customer Risk",
    captureOpportunity: "Capture Opportunity"
  },
  es: {
    topActions: "Top 5 Acciones Comerciales",
    replenishment: "Inteligencia de Reposición",
    lostCustomers: "Riesgo de Cliente Perdido",
    captureOpportunity: "Oportunidad de Captura"
  }
}

语言切换主要影响 UI 文案、模块标题和按钮文本。模型输出中的解释文本也可以通过 Gemini 分别生成英文或西班牙语版本。

9. 项目串联方式

最终系统计划按以下步骤串联：

1. 运行数据处理 pipeline
2. 生成 F1 / F2 / F3 alert tables
3. 合并为 all_alerts.json
4. 后端 FastAPI 读取 all_alerts.json
5. Gemini API 为 alert 生成解释文本
6. 前端 Dashboard 通过 API 获取数据
7. 用户在 Dashboard 中查看、筛选、展开和更新 alert
10. 计划阶段的实现优先级

为了控制开发复杂度，计划按以下优先级实现：

Priority 1:
- 生成统一 all_alerts.json
- FastAPI 提供 /api/alerts 和 /api/alerts/top5
- 前端展示 Top 5 actions
- 点击 alert 展开详情

Priority 2:
- 加入 F1 / F2 / F3 filter
- 加入 Gemini-generated explanation
- 加入 priority distribution 和地图

Priority 3:
- 加入 status update
- 加入 English / Spanish switch
- 加入更完整的 Commercial Action Queue
11. 设计原则

该 Demo 的核心原则是：

模型输出必须结构化；
解释文本必须基于结构化数据；
前端展示必须以商业行动为中心；
系统架构应保持轻量、模块化、可扩展。

一句话概括：

Data pipeline generates the signals.
Backend serves the signals.
Gemini explains the signals.
Dashboard operationalizes the signals.