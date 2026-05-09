# Smart Demand Signals Project Background and Problem Statement

---

## 1. Project Background

Inibsa is a pharmaceutical and medical products company serving the dental and healthcare sectors, mainly through B2B customers such as dental clinics. This project comes from the Interhack BCN 2026 Inibsa challenge, whose theme is **Smart Demand Signals**: using data analysis and intelligent systems to turn customers' historical purchasing behavior into actionable commercial signals. The challenge relates to sustainable growth, commercial efficiency, and resource optimization. Its goal is not only to improve sales execution, but also to allocate sales time more effectively, reduce low-value outreach, and improve supply-chain and commercial operations.

Inibsa has around 6,000 dental clinic customers and more than five years of sales history at customer and product levels. This creates the conditions to analyze customer purchase patterns and identify potential replenishment needs, customer churn risk, and commercial opportunities that have not yet been fully captured.

The core question is: **how can we identify commercial intervention signals from customer purchase history and convert them into alerts that the sales team can understand, rank, and act on?**

In other words, the system must answer:

```text
Which customer needs attention?
Which product family is involved?
Why does the customer need attention?
When should the customer be contacted?
How high is the priority?
```

---

## 2. Business Problem

Inibsa's sales data contains two clearly different product purchasing patterns.

The first type is **commodity products**: standardized consumables with relatively high repeat-purchase frequency, such as anesthesia, needles, disinfection, or biosafety products. These products are usually tied to daily clinic consumption. Customer behavior is relatively stable, so it is suitable for analyzing replenishment cycles, purchase frequency, and demand gaps. Customers differ in their dependence on Inibsa: some buy only occasionally or in small amounts, some mainly purchase from Inibsa, and others may split purchases between Inibsa and competitors. For these products, the key question is whether there is a gap between real customer demand and actual purchases, and when the right moment is to contact the customer and capture more demand.

The second type is **technical products**. Their purchasing behavior is less regular and may depend on clinical case types, dentists' specialties, clinic business structure, and competitor penetration. For these products, the focus is not simply to predict the next replenishment. The focus is to detect whether customer purchasing behavior is deteriorating over time: lower frequency, lower volume, no repeat purchase for a long period, or abnormal activity relative to that customer's historical pattern.

Therefore, the challenge is not just to predict "whether a customer will buy". It must distinguish the commercial meaning of different signals under different product types:

```text
For commodity products:
focus on replenishment needs, unmet demand, and competitor-diversion opportunities.

For technical products:
focus on whether customers are reducing purchases, stopping purchases, or showing churn risk.
```

A key constraint is that Inibsa cannot directly observe whether customers bought competitor products, nor can it fully see purchases through indirect channels. Therefore, the system cannot simply conclude that "buying less means churn" or "no purchase means a switch to competitors". Instead, it must infer indirectly from historical purchase patterns, product type, purchase potential, and contextual information.

---

## 3. Project Goals

The goal is to design an analytical solution that identifies commercial intervention signals at the **customer-product family-time point** level, updated daily. The system must decide whether a customer shows an actionable situation for a given product family and recommend an appropriate contact time.

The solution must output explainable and actionable commercial alerts, not only a model score or probability. Each alert should include at least:

```text
Customer
Product family
Alert reason
Recommended contact time
Priority
Recommended channel
```

The system must also be traceable: it should explain why an alert was generated and which variables, rules, or data features were involved.

The project also needs to consider the real commercial workflow after an alert is generated: who handles the alert, within what time frame, and how the outcome is recorded. This means the system is not only a data analysis tool; it must support a real sales process.

---

## 4. Raw Dataset Overview

The project data mainly consists of five tables covering transaction history, product information, customer information, customer potential, and campaign information. The overall data granularity supports analysis by customer, product, and time.

### 4.1 Ventas: Sales Transaction Data

`Ventas` is the core transaction table. It records historical purchases of products by customers on different dates. Main fields:

```text
Num.Fact        Invoice or order number
Fecha           Transaction date
Id. Cliente     Customer ID
Id. Producto    Product ID
Unidades        Purchased units
Valores_H       Sales amount
```

This table is the basis for building customer purchase time series. It supports analysis of purchase frequency, quantity, value, last purchase date, and historical purchase cycles.

Sales data may contain negative units or negative amounts, usually representing returns, refunds, adjustments, or replacements. Negative transactions should therefore not be treated as normal purchase events.

---

### 4.2 Productos: Product Information

`Productos` describes product hierarchy and product type. Main fields:

```text
Id.Prod             Product ID
Bloque analitico    Analytical product type
Categoria_H         Product category
Familia_H           Product family
```

This table maps individual SKUs in transactions to higher-level product families and distinguishes commodity products from technical products.

Product family is a very important analysis unit. Although raw transactions happen at SKU level, commercial alerts should usually be generated at product-family level because the sales team cares more about changes in a product group than isolated SKU fluctuations.

---

### 4.3 Potencial: Customer Purchase Potential

`Potencial` records each customer's potential purchasing capacity by product family or category. Main fields:

```text
Id.Cliente              Customer ID
Familia                 Product family or business name
Categoria Productos     Product category
Potencial_H             Customer purchase potential
```

`Potencial_H` can be understood as an internal estimate of theoretical demand or commercial potential. It is not a model prediction; it is business prior information already provided in the raw data.

This field is critical because it helps identify whether actual purchases are below potential demand. For example, if a high-potential customer buys very little, the customer's demand may not be fully captured, or part of the demand may be going to competitors.

However, the business documents also mention data quality issues, such as missing, incomplete, or incorrectly entered potential values. Potential should therefore be used as commercial reference, not as absolute truth.

---

### 4.4 Clientes: Customer Information

`Clientes` records basic customer information. Main fields:

```text
Id. Cliente     Customer ID
Unnamed: 1      Customer group or segment code
Provincia       Customer province
```

This table provides geography and possible segmentation, which can support regional analysis, customer stratification, and commercial outreach strategy.

For example, province can support map visualization or regional opportunity analysis; segment code may distinguish customer or clinic groups.

---

### 4.5 Campanas: Campaign Information

`Campanas` records promotion campaigns. Main fields:

```text
Campana         Campaign name
Fecha inicio   Campaign start date
Fecha fin      Campaign end date
```

Campaigns are important context because customer purchase volume may temporarily increase or fluctuate during campaign periods. Without campaign context, the system may incorrectly interpret a promotion-driven spike as a long-term demand change, or incorrectly judge the post-campaign decline. Campaign information should therefore be used as background when explaining customer behavior.

---

## 5. Key Data and Business Challenges

The data and business setting have strong real-world industrial characteristics. The main challenges are:

First, customer purchasing behavior is not always regular. This is especially true for technical products, where purchases may depend on clinical cases, dentists' specialties, or occasional demand. A long period without purchase should not automatically be interpreted as customer churn.

Second, competitor purchases are not directly observable. Inibsa only sees customer purchases from Inibsa and cannot fully observe whether customers buy from competitors or other channels. Competitor leakage must therefore be inferred indirectly through purchase potential, historical purchase patterns, and actual purchase gaps.

Third, the raw data may contain missing values, anomalies, and inconsistencies. The business documents explicitly mention incomplete customer history, product changes or replacements, irregular purchasing, campaigns, unusual orders, stockouts, and commercial policy changes.

Fourth, the final output cannot be just an analytical result; it must enter the sales workflow. The company needs commercial signals that can be used by sales representatives, telesales, or marketing automation systems, with priority and explainability.

---

## 6. Problem Summary

This project solves a B2B commercial intelligence problem: how to use years of dental clinic purchase history to identify replenishment needs, churn risk, and potential commercial opportunities by product family, and convert those findings into explainable, ranked, actionable sales alerts.

The difficulty is not simply predicting a number. The difficulty is transforming complex, sparse, business-noisy transaction data into decision information that the sales team can actually use. The final system must support daily commercial operations and help answer:

```text
Which customers should be contacted today?
Why should they be contacted?
Which product family is involved?
Which channel should be used?
Which customers deserve priority?
```

# Expected Deliverables

The project is expected to deliver two main outcomes: a project presentation and a runnable Dashboard Demo. The presentation explains the project background, development process, technical route, and quantitative results. The demo shows how the system can support daily sales decisions in a real commercial setting.

---

## 1. Project Presentation Slides

The first deliverable is a clearly structured slide deck for judges, sponsors, or team members. The slides should explain the full project logic, development process, and results.

The slides should not only show the final interface. They need to clearly explain:

```text
What problem did we solve?
Why is this problem important?
How did we process the raw data?
Which functional modules did we design?
How did we validate whether the model and baseline are useful?
How does the final system help the sales team act?
```

### Expected Slide Content

---

### 1.1 Project Background and Problem Definition

Explain Inibsa's current problem:

- customer purchase behavior is complex;
- commodity products and technical products follow different purchasing logic;
- competitor sales data is invisible;
- the sales team needs explainable, ranked, actionable commercial signals;
- the goal is to generate Smart Demand Signals from historical purchase data.

---

### 1.2 Raw Dataset Introduction

Introduce the data tables:

```text
Ventas      Sales transaction data
Productos   Product hierarchy and product type
Clientes    Customer information
Potencial   Customer purchase potential
Campanas    Campaign information
```

Explain the data granularity and analysis unit:

```text
client_id x product_family x time
```

Also explain why the final analysis focuses on product-family level rather than individual SKU level.

---

### 1.3 Overall System Pipeline

Show the full flow from raw data to final commercial alerts:

```text
Raw Data
-> Data Cleaning
-> Feature Engineering
-> F1 / F2 / F3 Signal Detection
-> Alert Generation
-> Prioritization
-> Dashboard
```

A pipeline diagram is recommended so judges can quickly understand the system architecture.

---

### 1.4 Functional Module Design

The slides should explain the core Dashboard modules:

```text
F1 Replenishment Intelligence
F2 Lost Customer Risk
F3 Capture Opportunity / Competitor Leakage
F4 Commercial Action Queue
```

For each module, explain:

- what the input is;
- which business problem it solves;
- what type of commercial signal it outputs;
- how it enters the final action queue.

---

### 1.5 Method and Development Process

Briefly explain the development logic of each module.

For example:

```text
F1:
statistical baseline + GRU sequential model

F2:
lost customer risk baseline based on volume drop, frequency drop, silence duration, trend decline

F3:
potential gap, utilization ratio, capture window, competitor leakage proxy

F4:
priority score and operational routing
```

This section should not overemphasize model complexity. The key message should be:

```text
business logic + explainability + operational usefulness
```

---

### 1.6 Quantitative Evaluation Results

The slides should include quantitative model or baseline results to prove that the system is not only a concept demo.

For F1, show for example:

```text
AUROC
AUPRC
Precision@TopK
Recall@TopK
Lift@TopK
```

The recommended focus is:

```text
Precision@Top100 / Top500
Lift@Top100 / Top500
```

These metrics best show whether the sales team gets a higher hit rate by acting on the system's top list than by random selection.

If F2/F3 backtesting results are available, show corresponding:

```text
AUROC
AUPRC
Precision@TopK
Risk / Opportunity ranking distribution
```

---

### 1.7 Visualizations

Slides should include necessary charts to make results intuitive.

Recommended charts:

```text
1. Data scale chart
2. Product type distribution
3. Pipeline architecture diagram
4. F1 evaluation curves, such as ROC / PR curve
5. Priority distribution
6. Top alert examples
7. Dashboard screenshot
8. Example customer purchase timeline
```

These charts help judges quickly see that:

- the data is real;
- the system is runnable;
- the model has quantitative validation;
- the output is commercially explainable.

---

### 1.8 Limitations and Future Improvements

The slides should end with current limitations, for example:

- competitor leakage can only be inferred indirectly;
- potential data may contain noise;
- technical product purchases are sparse;
- the current demo is not connected to a real CRM;
- a feedback loop requires real sales outcome data for further training.

This section is important because the sponsor explicitly values understanding of limitations and risks.

## 2. Demo: Runnable Dashboard

The second deliverable is a runnable Dashboard Demo showing how Smart Demand Signals turn raw transaction data into explainable, ranked, actionable commercial alerts.

The current frontend prototype already contains a fairly complete control-panel structure: a top status bar, Top 5 customer alerts, customer potential ranking, purchase probability/loyalty ranking, monthly sales trend chart, product category sales chart, and Spain map. The page currently renders static mock data, and the code notes that it can later connect to data generated from Pandas DataFrames.

The next step is to adapt the prototype from a generic `PharmaDash` into:

```text
Smart Demand Signals Dashboard
```

or:

```text
Inibsa Commercial Intelligence Dashboard
```

Mock examples such as hospitals, pharmacies, oncology, and cardiology should be replaced by the real business context of this project: dental clinics, product families, replenishment alerts, lost customer risk, and potential competitor-leakage opportunities.

---

## 2.1 Overall Dashboard Positioning

The Dashboard is not a general sales data visualization page. It is a:

```text
Commercial Intelligence Dashboard
```

for sales teams and commercial managers.

It should help users answer:

```text
Which customers should be contacted today?
Why should they be contacted?
Which product family is involved?
Is this replenishment, churn risk, or a capture opportunity?
How high is the priority?
What action should be taken?
```

Therefore, the core is not to display all data, but to display model- and rule-processed **Top commercial actions**.

---

## 2.2 Language Switch: English / Spanish

Because the sponsor and event environment may mainly use Spanish, while the team's technical explanation may use English, the Dashboard should support **English / Spanish switching**.

Add a language switch button in the top-right corner:

```text
EN / ES
```

When clicked, the main UI copy should switch language.

### Examples

| English | Spanish |
| --- | --- |
| Smart Demand Signals | Senales Inteligentes de Demanda |
| Dashboard | Panel de Control |
| Top 5 Actions | Top 5 Acciones |
| Replenishment Intelligence | Inteligencia de Reposicion |
| Lost Customer Risk | Riesgo de Cliente Perdido |
| Capture Opportunity | Oportunidad de Captura |
| Competitor Leakage | Fuga Potencial a Competencia |
| Recommended Action | Accion Recomendada |
| Reason | Motivo |
| Priority | Prioridad |
| Potential Value | Valor Potencial |
| Status | Estado |

The language switch does not require a complex backend. A frontend translation dictionary is enough for demo level:

```javascript
const translations = {
  en: {
    dashboardTitle: "Smart Demand Signals",
    topAlerts: "Top 5 Actions",
    recommendedAction: "Recommended Action"
  },
  es: {
    dashboardTitle: "Senales Inteligentes de Demanda",
    topAlerts: "Top 5 Acciones",
    recommendedAction: "Accion Recomendada"
  }
}
```

---

## 2.3 Core Elements Already Present in the Dashboard

The current web prototype already has the following structure:

### 1. Top Header

The top of the page contains:

```text
Dashboard name
System status
Real-time clock
Current date
```

This can be kept, but the name should be changed from `PharmaDash` to `Smart Demand Signals` or `Inibsa Intelligence Dashboard`. The current header already contains system status and a real-time clock, which fits a commercial system prototype.

---

### 2. Top 5 Clientes en Alerta

The current core module is:

```text
Top 5 Clientes en Alerta
```

It shows the top five high-priority customers and supports click-to-expand. Each alert already contains:

```text
Customer name
Alert type
Change magnitude or risk badge
Explanation
Recommended action
Ranking reason / commercial impact
```

This structure fits the sponsor's requirements for actionable alerts and explainability. The accordion already shows `Explicacion`, `Accion recomendada`, and `Razon del ranking`, so it can be directly replaced with real model output later.

Recommended name:

English:

```text
Today's Top 5 Commercial Actions
```

Spanish:

```text
Top 5 Acciones Comerciales de Hoy
```

---

### 3. Top Potencial

The current page contains:

```text
Top Potencial
```

This module can be kept and connected to `Potencial_H`.

Recommended name:

English:

```text
Top Potential Accounts
```

Spanish:

```text
Cuentas con Mayor Potencial
```

This module supports F3 Capture Opportunity / Competitor Leakage because high-potential but low-actual-purchase customers are important commercial opportunities.

---

### 4. Top Fidelidad

The current page contains:

```text
Top Fidelidad
```

and shows `F_in` probability. This name is slightly inaccurate because F1 focuses more on replenishment priority than simple loyalty.

Recommended name:

English:

```text
Top Replenishment Priorities
```

Spanish:

```text
Prioridades de Reposicion
```

This module should connect to F1 outputs such as:

```text
reorder_probability
expected_reorder_window
f1_final_score
priority_level
```

---

### 5. Monthly Sales Chart

The current page contains:

```text
Volumen de Ventas Mensual
```

showing 2025 vs. 2024 monthly sales. This chart can be kept as business context, but the title should become:

English:

```text
Monthly Sales Trend
```

Spanish:

```text
Tendencia Mensual de Ventas
```

If time is limited, the chart can continue using aggregated sales data. If there is more time, it can be changed to monthly alerts or monthly opportunity value.

---

### 6. Sales by Category Chart

The current page contains:

```text
Ventas por Categoria
```

but mock categories such as `Oncologia`, `Cardiologia`, and `Antibioticos` do not match this project.

They should be replaced by real product families or business names, for example:

```text
Anestesia
Bioseguridad
Biomateriales
```

or anonymous family codes:

```text
Familia C1
Familia C2
Familia T1
Familia T2
```

Recommended title:

English:

```text
Sales by Product Family
```

Spanish:

```text
Ventas por Familia de Producto
```

---

### 7. Spain Map

The current page contains:

```text
Mapa de Ventas - Espana
```

using Plotly to draw a map of Spain and sales hotspots. This module is very suitable to keep.

It can later be upgraded from "sales hotspot" to:

```text
Regional Alert Map
```

or:

```text
Opportunity / Risk Heatmap
```

It can show:

```text
Number of F1 replenishment opportunities by province
Number of F2 lost customer risks by province
F3 capture opportunity value by province
```

English title:

```text
Regional Opportunity Map
```

Spanish title:

```text
Mapa Regional de Oportunidades
```

---

## 2.4 Dashboard Elements to Add

The current prototype already has a solid visual structure, but the following features should be added to better match the project goals.

### 1. F1 / F2 / F3 Module Switch

Add tabs or side navigation:

```text
Overview
F1 Replenishment
F2 Lost Customers
F3 Capture Opportunities
F4 Action Queue
```

Spanish:

```text
Resumen
F1 Reposicion
F2 Clientes Perdidos
F3 Oportunidades de Captura
F4 Cola de Acciones
```

This helps judges see that the dashboard is not generic, but designed around the sponsor's commercial intelligence questions.

---

### 2. F2 Lost Customer Risk

Add a module showing suspected lost customers:

English:

```text
Lost Customer Risk
```

Spanish:

```text
Riesgo de Cliente Perdido
```

Suggested fields:

```text
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

`lost_status` can include:

```text
Likely Lost
At Risk
Early Warning
Stable
```

Spanish:

```text
Probablemente perdido
En riesgo
Alerta temprana
Estable
```

---

### 3. F3 Capture Opportunity / Competitor Leakage

Add a module showing possible competitor leakage or uncaptured demand:

English:

```text
Capture Opportunity
```

Spanish:

```text
Oportunidad de Captura
```

Suggested fields:

```text
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

Use cautious wording. Do not say a customer definitely bought competitor products. Use:

```text
Potential competitor leakage
Possible unmet demand
Capture opportunity
```

Spanish:

```text
Fuga potencial a competencia
Demanda no capturada
Oportunidad de captura
```

---

### 4. F4 Commercial Action Queue

The current page has Top 5 alerts but not a full operational queue.

Add:

```text
Commercial Action Queue
```

Spanish:

```text
Cola de Acciones Comerciales
```

Fields:

```text
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

Statuses:

```text
Pending
Assigned
Contacted
Resolved
False Positive
```

Spanish:

```text
Pendiente
Asignado
Contactado
Resuelto
Falso positivo
```

This module shows that the system can enter a real sales workflow, not only generate analytical charts.

---

## 2.5 Data Integration Approach

The current page uses placeholder JavaScript arrays such as `alertasData`, `potencialData`, and `fidelidadData`. These can later be replaced by JSON files generated from the model pipeline. The current code already states that the data can be generated from Pandas DataFrames.

Recommended approach:

```text
Python / Pandas
-> generate alerts.json
-> frontend main.html reads JSON
-> render dashboard
```

This avoids building a complex backend API at the start while still creating a runnable demo.

If time allows, upgrade to:

```text
FastAPI backend
-> /api/alerts
-> /api/f1
-> /api/f2
-> /api/f3
-> frontend fetch API
```

API means the frontend requests data from fixed backend endpoints, the backend returns JSON, and the frontend displays it.

---

## 2.6 Final Demo Goal

The final Dashboard Demo should show a complete commercial flow:

```text
Raw transaction data
-> models and rules generate commercial signals
-> Dashboard displays Top actions
-> user reviews the reasons
-> user sees the recommended action
-> user processes customers by priority
```

Judges should see not a normal web page, but an:

```text
AI-powered Commercial Intelligence Dashboard
```

It should make the sponsor immediately understand that:

```text
the sales team can open this system every day,
see the customers they should contact first,
understand why the system recommends them,
and act based on priority.
```

# Methodology / Technical Implementation

This methodology section focuses on the process that turns raw data into commercial signals. The overall goal is to transform raw transactions, product information, customer information, purchase potential, and campaign information into structured alert tables for Dashboard display.

The current implementation focuses on four parts:

```text
Stage 0: Data Preprocessing
F1: Replenishment Intelligence
F2: Lost Customer Risk
F3: Capture Opportunity / Competitor Leakage
```

Overall processing logic:

```text
Raw Data
-> Data Cleaning
-> Data Integration
-> Weekly / Monthly Panel Construction
-> Feature Engineering
-> F1 / F2 / F3 Signal Generation
-> Priority Scoring
-> Explainable Alert Output
```

---

# 1. Data Preprocessing

## 1.1 Raw Data Inputs

The system uses five raw data tables:

```text
Ventas.csv
Productos.csv
Potencial.csv
Clientes.csv
Campanas.csv
```

| Table | Role |
| --- | --- |
| Ventas | Sales transaction history |
| Productos | Product hierarchy, product family, product type |
| Potencial | Customer purchase potential by product family |
| Clientes | Basic customer information, region, segment |
| Campanas | Campaign time windows |

The goal is to organize these separate tables into unified analytical structures for F1, F2, and F3.

---

## 1.2 Field Standardization

Because field names differ across tables, the first step is to standardize them into a canonical schema.

Examples:

```text
Id. Cliente / Id.Cliente -> client_id
Id. Producto / Id.Prod   -> product_id
Fecha                    -> date
Unidades                 -> units
Valores_H                -> sales_value
Familia_H / Familia      -> product_family
Bloque analitico         -> product_block
Potencial_H              -> potential_value
Provincia                -> province
Unnamed: 1               -> segment_code
```

`client_id` and `product_id` should be converted to strings and stripped of leading/trailing spaces to avoid merge issues. Date fields should be parsed as `datetime`.

---

## 1.3 Product Family Mapping

Product families in `Productos` use anonymous codes:

```text
Familia C1
Familia C2
Familia T1
Familia T2
```

`Potencial` uses business names:

```text
Anestesia
Bioseguridad
Biomateriales
```

Because the two cannot be matched directly, create a product-family mapping table. Current default assumption:

```text
Familia C1 -> Anestesia
Familia C2 -> Bioseguridad
Familia T1 -> Biomateriales
Familia T2 -> Biomateriales
```

Save it as a separate dictionary:

```python
MAP_FAMILY_TO_BUSINESS = {
    "Familia C1": "Anestesia",
    "Familia C2": "Bioseguridad",
    "Familia T1": "Biomateriales",
    "Familia T2": "Biomateriales"
}
```

This mapping is a business assumption and should be confirmed with the sponsor. The system should keep both fields:

```text
product_family       Original anonymous product family code
product_family_biz   Mapped business product family name
```

`product_family` is used for model grouping and product type; `product_family_biz` is used to match `Potencial`.

---

## 1.4 Sales Transaction Cleaning

`Ventas` is the core data source. Cleaning should handle the following.

### Missing Values

Delete records missing:

```text
client_id
product_id
date
```

Without these fields, customer, product, or time analysis is impossible.

---

### Negative Transactions

Raw sales may contain negative units or values:

```text
units < 0
sales_value < 0
```

These usually represent:

```text
returns
refunds
order corrections
product replacements
```

Therefore, do not simply delete them.

Processing rule:

```text
is_return = True if units < 0 or sales_value < 0
```

Keep two aggregation views:

```text
net_units  = sum(units)
net_value  = sum(sales_value)

gross_units = sum(max(units, 0))
gross_value = sum(max(sales_value, 0))
```

For replenishment-cycle calculation, negative transactions should not be treated as real replenishment events. F1 purchase events should only use:

```text
units > 0
```

---

### Duplicate Records

Deduplicate exact matches on:

```text
Num.Fact
client_id
product_id
date
```

---

### Abnormal Unit Price Filtering

Calculate:

```text
unit_price = sales_value / units
```

Extreme values such as:

```text
abs(unit_price) > 10000
```

can be treated as data-entry errors and removed or flagged.

---

## 1.5 Master Table Merge

Build a transaction-level master table:

```text
df_master =
Ventas
LEFT JOIN Productos ON product_id
LEFT JOIN Clientes  ON client_id
```

After merging, each transaction should include:

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

`Potencial` should not be merged directly into the transaction-level table, because one customer-product family pair may have one potential value while the transaction table has many rows. Direct merging may duplicate rows.

Keep `Potencial` as an independent lookup:

```text
df_potential:
client_id
product_family_biz
potential_value
```

Use it later when computing features at client-family level.

---

## 1.6 Weekly Panel Construction

F1 uses a weekly panel as its core input.

Analysis granularity:

```text
client_id x product_family x week_start
```

where `week_start` is Monday of the ISO week.

Aggregate by customer-product family-week:

```text
weekly_units      = sum(units where units > 0)
weekly_value      = sum(sales_value where sales_value > 0)
order_count       = number of unique invoices
return_units      = sum(abs(units) where units < 0)
had_purchase      = 1 if order_count > 0 else 0
```

For each historical `client_id x product_family`, fill the complete weekly sequence from the earliest date to the data end date. Missing weeks become:

```text
weekly_units = 0
weekly_value = 0
order_count = 0
return_units = 0
had_purchase = 0
```

This is critical; otherwise rolling means, purchase intervals, and sequence-model inputs will be wrong.

---

## 1.7 Campaign Flag

Use `Campanas` to mark whether each week overlaps a campaign.

If:

```text
[week_start, week_start + 6 days]
```

overlaps any campaign window:

```text
campaign_active = 1
```

otherwise:

```text
campaign_active = 0
```

This prevents promotion-driven short-term fluctuations from being misread as long-term purchase-pattern changes.

---

## 1.8 Cold-start Clients

Some customers in `Potencial` may not appear in the sales table. They represent:

```text
commercial potential
but no historical purchase record
```

They are not suitable for F1 replenishment prediction because no purchase history exists. Output them separately:

```text
df_cold_clients
```

These customers fit F3 Capture Opportunity better than F1.

---

# 2. F1 - Replenishment Intelligence

## 2.1 Module Goal

F1 identifies which customers may soon need replenishment for commodity products:

```text
product_block == "Commodities"
```

Business question:

```text
For a customer-product family pair, is the customer close to or beyond the normal replenishment cycle?
Should the sales team be reminded to contact this customer?
```

---

## 2.2 Analysis Granularity

F1 granularity:

```text
client_id x product_family
```

Time granularity:

```text
week
```

Weekly is preferred over daily because:

```text
daily data is too sparse;
weekly preserves replenishment rhythm;
weekly is suitable for sequence model input.
```

---

## 2.3 Seasonality-aware Statistical Baseline

F1 uses a seasonality-aware statistical baseline.

Core idea:

```text
Do not only look at the customer's full-year average purchase cycle.
Consider normal purchase variation in the current quarter.
```

For example, summer vacation may naturally lengthen purchase intervals. The same silence duration in a normal operating quarter may imply higher replenishment risk.

### 2.3.1 Purchase Interval Calculation

For each:

```text
client_id x product_family
```

extract all `week_start` values where `had_purchase == 1`, sort them, and compute:

```text
interval_days[i] = purchase_date[i] - purchase_date[i-1]
```

Label each interval by the quarter of the ending date:

```text
Q1: Jan-Mar
Q2: Apr-Jun
Q3: Jul-Sep
Q4: Oct-Dec
```

### 2.3.2 Hierarchical Statistics and Fallback

Use multi-level fallback to handle insufficient customer history.

Level A:

```text
client_id x product_family x quarter
```

Condition:

```text
n_purchases_cfq >= 3
```

Level B:

```text
client_id x product_family
```

Condition:

```text
n_purchases_cf >= 4
```

Level C:

```text
product_family x quarter
```

or:

```text
segment_code x product_family x quarter
```

This final fallback represents the average replenishment cycle for similar products or customer segments.

### 2.3.3 Replenishment Delay Score

At a scoring date, such as the week after the latest data, calculate:

```text
last_purchase_date
days_since_last_purchase
expected_interval
expected_reorder_date
delay
```

where:

```text
delay = days_since_last_purchase - expected_interval
```

If `delay <= 0`, the customer is still within the expected replenishment window. If `delay > 0`, the customer is beyond the expected window.

Standardize delay:

```text
seasonal_time_score = max(0, delay / std_interval)
```

`std_interval` comes from the selected fallback level, with a minimum:

```text
std_interval = max(std_interval, 3 days)
```

to avoid exploding scores when the standard deviation is too small.

### 2.3.4 Commercial Value Factor

Replenishment priority should consider commercial value, not only time delay.

Value comes from:

```text
potential_value
historical_value_12m
```

Use:

```text
raw_value = max(potential_value, historical_value_12m)
```

Because commercial value is usually highly skewed:

```text
value_factor = minmax(log1p(raw_value))
```

Final baseline score:

```text
replenishment_score = seasonal_time_score x value_factor
```

### 2.3.5 Priority Level

Rank all candidate alerts by `replenishment_score`:

```text
P1 Critical : top 5%
P2 High     : next 15%
P3 Medium   : next 30%
P4 Low      : remaining
```

If:

```text
seasonal_time_score == 0
```

mark as:

```text
On track
```

### 2.3.6 F1 Baseline Output

F1 baseline output:

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

Example reason:

```text
Client X has not ordered Anestesia in 42 days.
Their typical Q4 reorder cycle is 30 days.
This delay is 1.8 standard deviations beyond the expected pattern.
Because the client has high commercial value, priority is P1.
```

---

## 2.4 GRU Sequential Model

Besides the statistical baseline, F1 uses a GRU sequence model.

The GRU does not replace the baseline. It provides an additional probability signal based on historical purchase sequences.

### 2.4.1 Prediction Task

Model F1 as binary classification:

```text
Given past L weeks of purchase behavior,
predict whether the customer will buy this product family again in the next 4 weeks.
```

Label:

```text
y_t = 1 if had_purchase in weeks [t+1, t+2, t+3, t+4]
y_t = 0 otherwise
```

The 4-week horizon is chosen because:

```text
it is a reasonable sales outreach lead time;
it is more stable than predicting the exact purchase date;
it can be converted into a replenishment alert.
```

### 2.4.2 Input Features

Each sample uses a 12-week lookback window.

Time-series features:

```text
weekly_units
weekly_value
order_count
days_since_last_purchase
rolling_mean_units_4w
campaign_active
potential_gap_ratio
```

Static features:

```text
log1p(potential_value)
segment_code
province
product_family
```

Numerical features should be standardized using training-set statistics to avoid data leakage.

### 2.4.3 Data Split

Use time-based split, not random split:

```text
Train: 2021-04-01 -> 2024-06-30
Val:   2024-07-01 -> 2024-12-31
Test:  2025-01-01 -> 2025-11-30
```

Reasons:

```text
the business setting always uses the past to predict the future;
random split causes temporal leakage;
the same customer may appear in train/val/test, but time cannot be mixed.
```

### 2.4.4 Model Structure

```text
Input: 12-week sequence x feature_dim
GRU hidden_size = 32
Take last hidden state
Concatenate static features
MLP classifier
Output: reorder_probability
```

Output:

```text
reorder_probability in [0, 1]
```

meaning the probability that the customer will repurchase the product family within the next 4 weeks.

### 2.4.5 Evaluation Metrics

F1 should not focus on accuracy because future purchase events may be imbalanced.

Use:

```text
AUROC
AUPRC
Positive-class F1
Precision@TopK
Recall@TopK
Lift@TopK
Brier Score
```

`Precision@TopK` and `Lift@TopK` best reflect commercial ranking value, because the system generates a prioritized contact list rather than a static classification for every customer.

### 2.4.6 Final F1 Fusion

Baseline output:

```text
replenishment_score
```

GRU output:

```text
reorder_probability
```

Combine them as:

```text
f1_final_score =
0.5 x normalized_replenishment_score
+
0.5 x reorder_probability
```

A more robust method is rank normalization:

```text
f1_final_score =
0.5 x rank_percentile(replenishment_score)
+
0.5 x rank_percentile(reorder_probability)
```

Final output:

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

# 3. F2 - Lost Customer Risk

## 3.1 Module Goal

F2 identifies suspected lost customers or customers with high churn risk.

F2 focuses mainly on technical products:

```text
product_block == "Productos Tecnicos"
```

These products have low frequency and high variability, so "no purchase for a long time" is not enough to declare churn.

F2 question:

```text
The customer previously bought a technical product family.
Have recent purchase frequency, volume, or activity clearly declined?
```

---

## 3.2 Data Granularity

F2 should use a monthly panel, not a weekly panel.

Granularity:

```text
client_id x product_family x month
```

Reasons:

```text
technical products have low purchase frequency;
weekly granularity is too sparse;
monthly is better for observing long-term deterioration.
```

Aggregate:

```text
monthly_units
monthly_value
order_count
had_purchase
```

Missing months should also be filled with zero.

---

## 3.3 Historical and Recent Windows

For each customer-product family pair:

```text
historical_window = longer past period
recent_window     = most recent 3-6 months
```

Recommended:

```text
historical_window = last 24 months excluding the most recent 6 months
recent_window = most recent 6 months
```

Compare the two windows to detect deterioration.

---

## 3.4 Core F2 Features

### 3.4.1 Volume Drop

```text
historical_avg_units
recent_avg_units
```

```text
volume_drop_ratio =
max(0, historical_avg_units - recent_avg_units)
/
historical_avg_units
```

This reflects whether purchase volume has declined.

### 3.4.2 Frequency Drop

```text
historical_purchase_rate =
months_with_purchase_historical / total_historical_months

recent_purchase_rate =
months_with_purchase_recent / total_recent_months
```

```text
frequency_drop_ratio =
max(0, historical_purchase_rate - recent_purchase_rate)
```

This reflects whether the customer moved from frequent purchase to infrequent purchase.

### 3.4.3 Silence Score

Calculate whether current silence exceeds the historical normal range.

First compute:

```text
historical_p90_interval
```

Then:

```text
days_since_last_purchase
```

```text
silence_score =
days_since_last_purchase / historical_p90_interval
```

If `silence_score > 1`, current silence is longer than 90% of the customer's historical normal intervals.

### 3.4.4 Trend Score

Fit a linear trend to recent monthly units:

```text
monthly_units ~ time
```

If slope is negative:

```text
trend_score = max(0, -trend_slope)
```

---

## 3.5 Lost Customer Score

Combine signals:

```text
lost_customer_score =
0.35 x volume_drop_score
+
0.35 x frequency_drop_score
+
0.20 x silence_score_normalized
+
0.10 x trend_score_normalized
```

Add commercial value:

```text
f2_priority_score =
lost_customer_score x value_factor
```

where:

```text
value_factor = normalized log1p(max(potential_value, historical_12m_value))
```

---

## 3.6 Lost Status

Label customers as:

```text
Likely Lost
At Risk
Early Warning
Stable
```

Example rules:

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

## 3.7 F2 Output Table

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

Example reason:

```text
Client X shows lost customer risk in Biomateriales.
Recent 6-month purchase volume is 62% below historical baseline.
Purchase frequency dropped from 0.42 to 0.10 months with orders.
The current silence period is 1.4 times longer than its historical normal range.
Priority is P1 due to high commercial value.
```

---

## 3.8 F2 Evaluation

If no true churn labels exist, build proxy labels through backtesting.

At observation point t:

```text
y = 1 if client-family has no purchase in next 6 months
        OR next 6-month value drops > 60% vs historical baseline

y = 0 otherwise
```

Metrics:

```text
AUROC
AUPRC
Positive-class F1
Precision@TopK
Lift@TopK
```

TopK metrics evaluate whether the ranking of highest-risk customers is useful.

---

# 4. F3 - Capture Opportunity / Competitor Leakage

## 4.1 Module Goal

F3 identifies commercial opportunities, especially:

```text
high-potential customers with low actual purchase
```

This may mean:

```text
customer demand has not been fully captured;
part of demand may go to competitors;
there is a current commercial expansion opportunity.
```

Because competitor purchase data is not observable, F3 should not output a deterministic claim such as:

```text
the customer bought competitor products
```

It should use cautious signals:

```text
Potential competitor leakage
Possible unmet demand
Capture opportunity
```

---

## 4.2 Analysis Granularity

```text
client_id x product_family
```

Recommended windows:

```text
recent 12 months
recent 12 weeks
```

Twelve months supports long-term potential utilization analysis; twelve weeks supports recent capture-window analysis.

---

## 4.3 Potential Utilization Ratio

Core F3 feature:

```text
observed_value_12m = last 12-month observed purchase value
potential_value = potential table value
```

```text
utilization_ratio =
observed_value_12m / potential_value
```

```text
potential_gap =
max(0, potential_value - observed_value_12m)
```

If potential is high and utilization is low, the customer has uncaptured demand.

---

## 4.4 Recent Expected vs Observed Gap

Convert annual potential into recent expected value:

```text
expected_12w_value =
potential_value / 52 x 12
```

Recent actual purchase:

```text
observed_12w_value =
sum(weekly_value over last 12 weeks)
```

Recent gap:

```text
recent_gap =
max(0, expected_12w_value - observed_12w_value)
```

This feature detects timely uncaptured demand.

---

## 4.5 Promiscuous Customer Proxy

Because competitor purchases are invisible, F3 builds an indirect promiscuous-customer proxy.

Possible signals:

```text
high potential
nonzero but low observed purchase
irregular purchase pattern
repeated under-utilization
```

Simple proxy:

```text
promiscuity_score =
high_potential_score
x low_utilization_score
x intermittent_purchase_score
```

where:

```text
low_utilization_score = 1 - utilization_ratio
```

`intermittent_purchase_score` can be computed from purchase interval volatility or unstable purchase activity.

These customers differ from cold-start clients. They have bought from Inibsa before but buy below potential, making them more likely capture opportunities.

---

## 4.6 Capture Window Score

F3 should identify not only who has an opportunity, but when the outreach window is good.

Combine with F1:

```text
capture_window_score =
opportunity_score x replenishment_urgency
```

where `opportunity_score` comes from potential gap and utilization ratio, and `replenishment_urgency` comes from the F1 replenishment window or time delay.

Meaning:

```text
the customer has potential,
and is currently close to replenishment,
so this is a good commercial capture window.
```

---

## 4.7 Opportunity Score

```text
opportunity_score =
0.40 x potential_gap_score
+
0.30 x low_utilization_score
+
0.20 x promiscuity_score
+
0.10 x capture_window_score
```

Then:

```text
f3_priority_score =
opportunity_score x value_factor
```

where:

```text
value_factor = normalized log1p(potential_value)
```

---

## 4.8 Priority Level

Rank by `f3_priority_score`:

```text
P1 Critical : top 5%
P2 High     : next 15%
P3 Medium   : next 30%
P4 Low      : remaining
```

---

## 4.9 F3 Output Table

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

`opportunity_type` can include:

```text
High Potential Underutilization
Potential Competitor Leakage
Capture Window
Cold-start Opportunity
```

Example reason:

```text
Client X has high potential in Anestesia but only 22% utilization in the last 12 months.
The recent 12-week observed value is below the expected level based on annual potential.
This suggests possible unmet demand or competitor leakage.
Because the client is close to a replenishment window, this is ranked as a P1 capture opportunity.
```

---

## 4.10 F3 Evaluation

True ground truth is difficult because competitor purchase data is unavailable. Evaluation should use proxy backtesting and business plausibility metrics.

### Future Purchase Growth Label

At observation point t, if future 3-6 month purchase value increases significantly, the previous opportunity signal has some validity.

```text
y = 1 if future_6m_value > recent_6m_value x 1.5
y = 0 otherwise
```

### TopK Opportunity Validation

Evaluate whether top K customers later show purchase growth:

```text
Precision@TopK
Lift@TopK
Average future value growth in TopK
```

### Business Plausibility Check

Check whether top opportunities have reasonable characteristics:

```text
high potential
low utilization
nonzero purchase history
recent underperformance
```

Because F3 is indirect inference, evaluation should state:

```text
F3 does not directly observe competitor sales.
It evaluates potential unmet demand and possible leakage using indirect commercial signals.
```

---

# 5. Output File Structure

Recommended outputs for the methodology stage:

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

```text
Data Preprocessing:
unify raw transaction, product, customer, potential, and campaign data into analytical panels.

F1:
for commodity products, combine a seasonality-aware statistical baseline and a GRU sequence model to generate replenishment priorities.

F2:
for technical products, identify lost customer risk based on volume drop, frequency drop, abnormal silence, and downward trend.

F3:
identify uncaptured demand, potential competitor leakage, and capture opportunities from the gap between potential value and observed purchase.
```

Core principles:

```text
Do not only output model scores.
Also output explainable reasons,
commercial priorities,
and alert tables that can enter the Dashboard.
```

# Demo Backend/Frontend Architecture and Explanation Layer

After F1, F2, and F3 are complete, the project needs to display model- and rule-generated results in an interactive Dashboard. To make the Demo closer to a real commercial system rather than a static page, we plan to use a modular, extensible, dynamically updatable backend/frontend architecture.

Overall flow:

```text
Data / Model Pipeline
-> Structured Alert Tables
-> Backend API
-> Gemini Explanation Layer
-> Frontend Dashboard
```

The data and model modules generate structured commercial signals; the backend manages and serves these signals; the Gemini API turns structured results into natural-language explanations; the frontend Dashboard displays, filters, expands, and interacts with them.

## 1. Overall Architecture Choice

We plan to use:

```text
Python FastAPI Backend
+ Frontend Dashboard
+ JSON-based Alert Data
+ Gemini Explanation Layer
```

Reasons for choosing FastAPI:

1. High compatibility with Python data processing and model pipelines.
2. It can directly read parquet / csv / json output files.
3. It is easy to build clear API endpoints.
4. It is suitable for integrating the Gemini API later.
5. It is more dynamic than a static webpage and lighter than a full enterprise system.

At the hackathon stage, the system does not need a complex database or full CRM integration. The backend can first read locally generated JSON or parquet results and serve them to the frontend. This keeps the architecture clean and avoids excessive development complexity.

## 2. Data Flow Design

```text
Raw Data
-> Preprocessing
-> F1 / F2 / F3 Modules
-> Alert Tables
-> Unified Alert JSON
-> Backend API
-> Frontend Dashboard
```

F1, F2, and F3 output separate alert tables:

```text
f1_combined_alerts.parquet
f2_lost_customer_alerts.parquet
f3_capture_opportunity_alerts.parquet
```

Then they are converted into one standardized alert structure:

```text
all_alerts.json
```

This file is the main Dashboard data source.

## 3. Standardized Alert Object

To let the frontend display different modules uniformly, each alert should use a shared structure:

```json
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
```

Different modules can have different `model_outputs` and `evidence` fields:

```text
F1:
reorder_probability, expected_reorder_date, days_since_last_purchase

F2:
lost_customer_score, silence_score, volume_drop_ratio, lost_status

F3:
potential_value, observed_value, utilization_ratio, potential_gap
```

But the frontend only needs common fields:

```text
client_id
module
alert_type
priority_level
priority_score
reason
recommended_action
status
```

This keeps the system modular.

## 4. Backend API Design

FastAPI endpoints:

```text
GET /api/overview
GET /api/alerts
GET /api/alerts/top5
GET /api/alerts/{alert_id}
GET /api/f1
GET /api/f2
GET /api/f3
POST /api/alerts/{alert_id}/status
```

| API | Purpose |
| --- | --- |
| /api/overview | Return homepage KPI data |
| /api/alerts | Return all alerts |
| /api/alerts/top5 | Return today's Top 5 actions |
| /api/alerts/{alert_id} | Return one alert's details |
| /api/f1 | Return F1 replenishment alerts |
| /api/f2 | Return F2 lost customer risk |
| /api/f3 | Return F3 capture opportunities |
| /api/alerts/{alert_id}/status | Update alert status |

This lets the frontend request data dynamically based on user actions instead of hard-coding everything in HTML.

## 5. Frontend Dashboard Design

The frontend can continue from the existing `main.html` prototype. It already has the basic Dashboard visual structure: Top 5 alerts, potential ranking, trend chart, category chart, and map.

Planned transformation:

```text
Smart Demand Signals Dashboard
```

Main page areas:

1. Executive Overview
2. Top 5 Commercial Actions
3. F1 Replenishment Intelligence
4. F2 Lost Customer Risk
5. F3 Capture Opportunity
6. F4 Commercial Action Queue
7. Regional Map
8. Explainability Panel

Main frontend features:

1. Show today's Top 5 actions.
2. Filter alerts by F1 / F2 / F3.
3. Show priority level and score.
4. Expand an alert on click.
5. Show model outputs, evidence fields, and AI explanations.
6. Update alert status, such as Pending / Contacted / Resolved.
7. Support English / Spanish language switching.

## 6. Gemini Explanation Layer

The Gemini API is not used to decide whether alerts are generated and does not replace F1, F2, or F3 model logic.

Gemini's role is:

```text
turn structured alert data into natural-language explanations and action recommendations that the sales team can easily understand.
```

In short:

```text
F1 / F2 / F3 models decide.
Gemini explains.
Dashboard displays.
```

This avoids unsupported LLM conclusions and keeps the system traceable.

## 7. Gemini Prompt Design

Each alert can generate a prompt from structured fields:

```text
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
```

The generated result can fill:

```text
ai_summary
ai_recommendation
ai_caveat
```

and the frontend displays it when the user expands an alert.

## 8. English / Spanish Language Switch

Because technical explanation may use English while the sponsor and event presentation may need Spanish, the Dashboard should support:

```text
EN / ES
```

The frontend can maintain a simple translation dictionary:

```javascript
const translations = {
  en: {
    topActions: "Top 5 Commercial Actions",
    replenishment: "Replenishment Intelligence",
    lostCustomers: "Lost Customer Risk",
    captureOpportunity: "Capture Opportunity"
  },
  es: {
    topActions: "Top 5 Acciones Comerciales",
    replenishment: "Inteligencia de Reposicion",
    lostCustomers: "Riesgo de Cliente Perdido",
    captureOpportunity: "Oportunidad de Captura"
  }
}
```

The switch mainly affects UI copy, module titles, and button text. Gemini can also generate explanations separately in English or Spanish.

## 9. Project Integration

Final system steps:

1. Run the data processing pipeline.
2. Generate F1 / F2 / F3 alert tables.
3. Merge into `all_alerts.json`.
4. FastAPI backend reads `all_alerts.json`.
5. Gemini API generates explanation text for alerts.
6. Frontend Dashboard retrieves data through APIs.
7. Users view, filter, expand, and update alerts in the Dashboard.

## 10. Implementation Priorities

To control complexity:

Priority 1:

- generate unified `all_alerts.json`;
- FastAPI provides `/api/alerts` and `/api/alerts/top5`;
- frontend displays Top 5 actions;
- clicking an alert expands details.

Priority 2:

- add F1 / F2 / F3 filter;
- add Gemini-generated explanations;
- add priority distribution and map.

Priority 3:

- add status updates;
- add English / Spanish switch;
- add a more complete Commercial Action Queue.

## 11. Design Principles

Core principles:

```text
model outputs must be structured;
explanation text must be based on structured data;
frontend display must focus on commercial actions;
architecture should remain lightweight, modular, and extensible.
```

One-sentence summary:

```text
Data pipeline generates the signals.
Backend serves the signals.
Gemini explains the signals.
Dashboard operationalizes the signals.
```
