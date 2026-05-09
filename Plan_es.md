# Contexto del Proyecto Smart Demand Signals y Descripcion del Problema

---

## 1. Contexto del Proyecto

Inibsa es una empresa farmaceutica y de productos medicos orientada al sector dental y sanitario. Sus clientes son principalmente B2B, como clinicas dentales. Este proyecto procede del reto de Inibsa en Interhack BCN 2026, cuyo tema es **Smart Demand Signals**: usar analisis de datos y sistemas inteligentes para convertir el historial de compra de los clientes en senales comerciales accionables. El reto esta relacionado con crecimiento sostenible, eficiencia comercial y optimizacion de recursos. El objetivo no es solo mejorar la ejecucion comercial, sino tambien asignar mejor el tiempo del equipo de ventas, reducir contactos de bajo valor y mejorar la cadena de suministro y las operaciones comerciales.

Inibsa cuenta con unas 6.000 clinicas dentales clientes y mas de cinco anos de datos historicos de ventas a nivel de cliente y producto. Esto permite analizar patrones de compra, identificar necesidades potenciales de reposicion, riesgo de perdida de clientes y oportunidades comerciales aun no capturadas.

La pregunta central es: **como identificar senales que requieren intervencion comercial a partir del historial de compras, y convertirlas en alertas que el equipo de ventas pueda entender, ordenar y ejecutar?**

En otras palabras, el sistema debe responder:

```text
Que cliente necesita atencion?
Con que familia de producto esta relacionado?
Por que necesita atencion?
Cuando se deberia contactar?
Que prioridad tiene?
```

---

## 2. Descripcion del Problema de Negocio

En los datos de ventas de Inibsa existen dos patrones de compra claramente diferentes.

El primer tipo son los **commodity products**: productos estandarizados y de compra recurrente, como anestesia, agujas, desinfeccion o productos de bioseguridad. Normalmente estan ligados al consumo diario de la clinica. El comportamiento de compra es relativamente estable, por lo que es adecuado analizar ciclos de reposicion, frecuencia de compra y brechas de demanda. Los clientes no dependen de Inibsa en el mismo grado: algunos compran poco u ocasionalmente, otros compran principalmente a Inibsa, y otros reparten compras entre Inibsa y competidores. Para estos productos, la pregunta clave es si existe una brecha entre la demanda real del cliente y la compra observada, y cuando es el momento adecuado para contactar y capturar mas demanda.

El segundo tipo son los **technical products**. Su comportamiento de compra es mas irregular y puede depender del tipo de caso clinico, la especialidad del doctor, la estructura de negocio de la clinica y la penetracion de competidores. Para estos productos, el foco no es solo predecir la proxima reposicion, sino detectar si el comportamiento de compra se deteriora de forma sostenida: menor frecuencia, menor volumen, ausencia prolongada de recompra o actividad anomala respecto al historial del cliente.

Por tanto, el challenge no consiste simplemente en predecir "si el cliente comprara". Debe distinguir el significado comercial de distintas senales segun el tipo de producto:

```text
Para commodity products:
enfocarse en necesidades de reposicion, demanda no satisfecha y oportunidades desviadas a competidores.

Para technical products:
enfocarse en si el cliente esta reduciendo compras, dejando de comprar o mostrando riesgo de perdida.
```

Una restriccion importante es que Inibsa no puede observar directamente si el cliente compro productos de competidores, ni ver completamente compras realizadas por canales indirectos. Por tanto, el sistema no puede concluir simplemente que "comprar menos significa perdida" o que "no comprar significa cambio a competidores". Debe inferir de forma indirecta usando patrones historicos, tipo de producto, potencial de compra y contexto.

---

## 3. Objetivos del Proyecto

El objetivo es disenar una solucion analitica que, con actualizacion diaria, identifique senales de intervencion comercial a nivel **cliente-familia de producto-momento temporal**. El sistema debe decidir si un cliente presenta una situacion accionable para una familia de producto y sugerir el momento adecuado de contacto.

La solucion debe producir alertas comerciales explicables y accionables, no solo una puntuacion o probabilidad de modelo. Cada alerta deberia incluir al menos:

```text
Cliente
Familia de producto
Motivo de la alerta
Momento recomendado de contacto
Prioridad
Canal recomendado
```

El sistema tambien debe ser trazable: debe explicar por que se genero una alerta y que variables, reglas o caracteristicas de datos intervinieron.

El proyecto tambien debe considerar el proceso comercial real posterior a una alerta: quien la gestiona, en que plazo y como se registra el resultado. Por tanto, no es solo una herramienta de analisis de datos; debe servir a un proceso de ventas real.

---

## 4. Resumen del Dataset Original

Los datos del proyecto se componen principalmente de cinco tablas: historial de transacciones, informacion de productos, informacion de clientes, potencial de clientes e informacion de campanas. La granularidad permite analizar por cliente, producto y tiempo.

### 4.1 Ventas: Datos de Transacciones de Venta

`Ventas` es la tabla transaccional principal. Registra las compras historicas de productos por cliente y fecha. Campos principales:

```text
Num.Fact        Numero de factura u orden
Fecha           Fecha de transaccion
Id. Cliente     ID de cliente
Id. Producto    ID de producto
Unidades        Unidades compradas
Valores_H       Importe de ventas
```

Esta tabla es la base para construir series temporales de compra. Permite analizar frecuencia, cantidad, valor, ultima compra y ciclos historicos.

Puede haber cantidades o importes negativos, normalmente asociados a devoluciones, reembolsos, ajustes o sustituciones. No deben tratarse como compras normales.

---

### 4.2 Productos: Informacion de Producto

`Productos` describe la jerarquia y el tipo de producto. Campos:

```text
Id.Prod             ID de producto
Bloque analitico    Tipo analitico de producto
Categoria_H         Categoria de producto
Familia_H           Familia de producto
```

Sirve para mapear SKUs a familias de producto y distinguir commodity products de technical products.

La familia de producto es una unidad analitica clave. Aunque las transacciones ocurren a nivel SKU, las alertas comerciales suelen generarse a nivel familia, porque el equipo de ventas se centra en cambios de una categoria de producto, no en fluctuaciones aisladas de un SKU.

---

### 4.3 Potencial: Potencial de Compra del Cliente

`Potencial` registra la capacidad potencial de compra por cliente y familia o categoria. Campos:

```text
Id.Cliente              ID de cliente
Familia                 Familia o nombre de negocio
Categoria Productos     Categoria de producto
Potencial_H             Potencial de compra
```

`Potencial_H` es una estimacion interna de demanda teorica o potencial comercial. No es una prediccion del modelo, sino informacion de negocio ya incluida en los datos.

Es clave para juzgar si las compras reales estan por debajo de la demanda potencial. Por ejemplo, un cliente de alto potencial con compra real baja puede indicar demanda no capturada o demanda que fluye a competidores.

Sin embargo, los documentos de negocio mencionan posibles problemas de calidad: datos faltantes, incompletos o errores de entrada. Por ello, el potencial debe usarse como referencia comercial, no como verdad absoluta.

---

### 4.4 Clientes: Informacion de Clientes

`Clientes` contiene informacion basica del cliente. Campos:

```text
Id. Cliente     ID de cliente
Unnamed: 1      Grupo de cliente o codigo de segmento
Provincia       Provincia del cliente
```

Proporciona ubicacion geografica y posible segmentacion, utiles para analisis regional, estratificacion de clientes y estrategia de contacto.

Por ejemplo, la provincia permite visualizaciones en mapa o analisis regional de oportunidades; el codigo de segmento puede distinguir tipos de cliente o grupos de clinicas.

---

### 4.5 Campanas: Informacion de Promociones

`Campanas` registra promociones. Campos:

```text
Campana         Nombre de campana
Fecha inicio   Fecha de inicio
Fecha fin      Fecha de fin
```

Las promociones son contexto importante porque el volumen de compra puede subir o fluctuar temporalmente durante una campana. Sin esta informacion, el sistema podria interpretar erroneamente un pico promocional como cambio de demanda a largo plazo, o interpretar mal la caida posterior. Por eso, las campanas deben usarse como contexto al explicar el comportamiento de compra.

---

## 5. Retos Clave de Datos y Negocio

Primero, el comportamiento de compra no siempre es regular. En productos tecnicos, puede depender de casos clinicos, especialidad medica o demanda puntual. Un periodo largo sin compra no debe interpretarse automaticamente como perdida.

Segundo, las compras a competidores no son observables directamente. Inibsa solo ve las compras realizadas a Inibsa. La fuga a competidores debe inferirse indirectamente mediante potencial, patron historico y brecha de compra real.

Tercero, los datos pueden tener valores faltantes, anomalias e inconsistencias. Los documentos mencionan historial incompleto, cambios o sustituciones de producto, compras irregulares, promociones, pedidos anormales, roturas de stock y cambios de politica comercial.

Cuarto, la salida final no puede ser solo un resultado analitico. Debe entrar en el flujo de ventas. La empresa necesita senales comerciales utilizables por representantes, televentas o automatizacion de marketing, con prioridad y explicabilidad.

---

## 6. Resumen del Problema

El proyecto resuelve un problema de inteligencia comercial B2B: como usar anos de historial de compra de clinicas dentales para identificar necesidades de reposicion, riesgo de perdida y oportunidades comerciales por familia de producto, y convertirlas en alertas explicables, ordenadas y accionables.

La dificultad no esta solo en predecir un numero, sino en transformar datos transaccionales complejos, dispersos y con ruido de negocio en informacion de decision util para ventas. El sistema final debe apoyar la operacion diaria y responder:

```text
Que clientes deberian contactarse hoy?
Por que contactarlos?
Con que familia de producto?
Por que canal?
Que clientes tienen mayor prioridad?
```

# Objetivos de Entrega Esperados

El proyecto debe entregar dos resultados principales: una presentacion del proyecto y un Dashboard Demo ejecutable. La presentacion explica contexto, proceso de desarrollo, ruta tecnica y resultados cuantitativos. El demo muestra como el sistema ayuda al equipo comercial en decisiones diarias.

---

## 1. Slides de Presentacion

La primera entrega es un deck claro para jueces, sponsor o equipo. Debe explicar la logica, el desarrollo y los resultados.

Debe responder:

```text
Que problema resolvemos?
Por que es importante?
Como tratamos los datos originales?
Que modulos funcionales disenamos?
Como validamos modelos y baselines?
Como ayuda el sistema final al equipo de ventas?
```

### Contenido Esperado

### 1.1 Contexto y Definicion del Problema

Explicar que Inibsa enfrenta:

- comportamiento de compra complejo;
- logicas distintas para commodity products y technical products;
- ausencia de datos de competidores;
- necesidad de senales comerciales explicables, ordenadas y accionables;
- objetivo de generar Smart Demand Signals desde historicos de compra.

### 1.2 Dataset Original

Tablas:

```text
Ventas      Datos de ventas
Productos   Jerarquia y tipo de producto
Clientes    Informacion de clientes
Potencial   Potencial de compra
Campanas    Informacion de promociones
```

Unidad de analisis:

```text
client_id x product_family x time
```

Tambien explicar por que se trabaja a nivel familia de producto y no SKU.

### 1.3 Pipeline General

```text
Raw Data
-> Data Cleaning
-> Feature Engineering
-> F1 / F2 / F3 Signal Detection
-> Alert Generation
-> Prioritization
-> Dashboard
```

Se recomienda una figura de pipeline para explicar la arquitectura.

### 1.4 Modulos Funcionales

```text
F1 Replenishment Intelligence
F2 Lost Customer Risk
F3 Capture Opportunity / Competitor Leakage
F4 Commercial Action Queue
```

Para cada modulo:

- entrada;
- problema de negocio;
- tipo de senal producida;
- como entra en la action queue.

### 1.5 Metodo y Desarrollo

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

El mensaje clave:

```text
business logic + explainability + operational usefulness
```

### 1.6 Evaluacion Cuantitativa

Para F1:

```text
AUROC
AUPRC
Precision@TopK
Recall@TopK
Lift@TopK
```

Destacar:

```text
Precision@Top100 / Top500
Lift@Top100 / Top500
```

porque muestran si actuar sobre la lista recomendada mejora frente a elegir clientes al azar.

Si hay backtesting de F2/F3:

```text
AUROC
AUPRC
Precision@TopK
Risk / Opportunity ranking distribution
```

### 1.7 Graficos

Incluir:

```text
1. Escala de datos
2. Distribucion de tipos de producto
3. Arquitectura pipeline
4. Curvas ROC / PR de F1
5. Distribucion de prioridades
6. Ejemplos de top alerts
7. Captura del Dashboard
8. Timeline de compra de un cliente
```

Estos graficos muestran que los datos son reales, el sistema funciona, existe validacion cuantitativa y las salidas son explicables.

### 1.8 Limitaciones y Mejoras

Mencionar:

- competitor leakage solo se infiere indirectamente;
- `potential` puede tener ruido;
- los technical products son dispersos;
- el demo aun no se integra con un CRM real;
- el feedback loop necesita resultados reales de ventas.

Esta parte es importante porque el sponsor valora entender limitaciones y riesgos.

## 2. Demo: Dashboard Ejecutable

La segunda entrega es un Dashboard Demo que muestra como Smart Demand Signals genera alertas comerciales explicables, ordenadas y accionables a partir de transacciones.

El prototipo frontend actual ya tiene una estructura completa: barra superior, Top 5 clientes en alerta, ranking de potencial, ranking de probabilidad/lealtad, tendencia mensual, ventas por categoria y mapa de Espana. Actualmente usa mock data estatico, con indicacion de que luego se puede conectar a datos generados con Pandas.

Debe pasar de un `PharmaDash` generico a:

```text
Smart Demand Signals Dashboard
```

o:

```text
Inibsa Commercial Intelligence Dashboard
```

Los ejemplos mock de hospitales, farmacias, oncologia o cardiologia deben sustituirse por clinicas dentales, familias de producto, alertas de reposicion, riesgo de perdida y oportunidades de fuga potencial a competencia.

---

## 2.1 Posicionamiento del Dashboard

No es una visualizacion general de ventas, sino un:

```text
Commercial Intelligence Dashboard
```

para ventas y managers comerciales.

Debe responder:

```text
Que clientes contactar hoy?
Por que?
Que familia de producto?
Es reposicion, riesgo de perdida u oportunidad de captura?
Que prioridad?
Que accion se recomienda?
```

El foco son las **Top commercial actions**, no todos los datos.

---

## 2.2 Cambio de Idioma: English / Spanish

El Dashboard debe soportar **ingles / espanol**.

Boton recomendado:

```text
EN / ES
```

Ejemplos:

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

Puede implementarse con un diccionario frontend:

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

## 2.3 Elementos Actuales del Dashboard

### 1. Header Superior

Incluye:

```text
Nombre del Dashboard
Estado del sistema
Reloj en tiempo real
Fecha actual
```

Debe renombrarse de `PharmaDash` a `Smart Demand Signals` o `Inibsa Intelligence Dashboard`.

### 2. Top 5 Clientes en Alerta

Modulo actual:

```text
Top 5 Clientes en Alerta
```

Incluye:

```text
Nombre del cliente
Tipo de alerta
Magnitud de cambio o badge de riesgo
Explicacion
Accion recomendada
Razon del ranking / impacto comercial
```

Encaja con los requisitos de actionable alert y explainability. Puede renombrarse:

English:

```text
Today's Top 5 Commercial Actions
```

Spanish:

```text
Top 5 Acciones Comerciales de Hoy
```

### 3. Top Potencial

Modulo:

```text
Top Potencial
```

Conectarlo con `Potencial_H`.

English:

```text
Top Potential Accounts
```

Spanish:

```text
Cuentas con Mayor Potencial
```

Sirve para F3, porque clientes de alto potencial y baja compra real suelen ser oportunidades.

### 4. Top Fidelidad

El nombre no es ideal, porque F1 trata prioridad de reposicion, no solo lealtad.

English:

```text
Top Replenishment Priorities
```

Spanish:

```text
Prioridades de Reposicion
```

Debe usar salidas F1:

```text
reorder_probability
expected_reorder_window
f1_final_score
priority_level
```

### 5. Monthly Sales Chart

Renombrar:

English:

```text
Monthly Sales Trend
```

Spanish:

```text
Tendencia Mensual de Ventas
```

Puede mantener ventas agregadas o cambiarse a alertas mensuales / valor de oportunidad.

### 6. Sales by Category Chart

Sustituir mock categories por:

```text
Anestesia
Bioseguridad
Biomateriales
```

o:

```text
Familia C1
Familia C2
Familia T1
Familia T2
```

Titulo:

English:

```text
Sales by Product Family
```

Spanish:

```text
Ventas por Familia de Producto
```

### 7. Spain Map

Mantener y evolucionar de mapa de ventas a:

```text
Regional Alert Map
```

o:

```text
Opportunity / Risk Heatmap
```

Puede mostrar:

```text
numero de oportunidades F1 por provincia
numero de riesgos F2 por provincia
valor de oportunidad F3 por provincia
```

Titulos:

```text
Regional Opportunity Map
Mapa Regional de Oportunidades
```

---

## 2.4 Elementos a Anadir

### 1. Cambio de Modulo F1 / F2 / F3

Tabs o navegacion lateral:

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

### 2. F2 Lost Customer Risk

Modulo:

```text
Lost Customer Risk
Riesgo de Cliente Perdido
```

Campos:

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

Estados:

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

### 3. F3 Capture Opportunity / Competitor Leakage

Modulo:

```text
Capture Opportunity
Oportunidad de Captura
```

Campos:

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

Usar lenguaje prudente:

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

### 4. F4 Commercial Action Queue

Agregar:

```text
Commercial Action Queue
Cola de Acciones Comerciales
```

Campos:

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

Estados:

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

---

## 2.5 Integracion de Datos

El prototipo usa arrays JavaScript como `alertasData`, `potencialData` y `fidelidadData`. Se pueden sustituir por JSON generado por el pipeline.

Recomendado:

```text
Python / Pandas
-> generar alerts.json
-> frontend main.html lee JSON
-> render dashboard
```

Si hay tiempo:

```text
FastAPI backend
-> /api/alerts
-> /api/f1
-> /api/f2
-> /api/f3
-> frontend fetch API
```

---

## 2.6 Objetivo Final del Demo

Flujo:

```text
Datos transaccionales
-> modelos y reglas generan senales
-> Dashboard muestra Top actions
-> usuario revisa motivos
-> usuario ve accion recomendada
-> usuario gestiona clientes por prioridad
```

El jurado debe ver un:

```text
AI-powered Commercial Intelligence Dashboard
```

Que demuestre:

```text
el equipo de ventas puede abrirlo cada dia,
ver los clientes mas importantes,
entender por que se recomiendan,
y actuar segun prioridad.
```

# Metodologia / Implementacion Tecnica

Esta seccion describe como convertir datos originales en senales comerciales estructuradas para el Dashboard.

Partes principales:

```text
Stage 0: Data Preprocessing
F1: Replenishment Intelligence
F2: Lost Customer Risk
F3: Capture Opportunity / Competitor Leakage
```

Flujo:

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

## 1.1 Entradas

```text
Ventas.csv
Productos.csv
Potencial.csv
Clientes.csv
Campanas.csv
```

| Tabla | Funcion |
| --- | --- |
| Ventas | Historial de ventas |
| Productos | Jerarquia, familia y tipo |
| Potencial | Potencial por cliente y familia |
| Clientes | Informacion basica, region, segmento |
| Campanas | Ventanas de promocion |

El objetivo es convertir tablas separadas en estructuras analiticas para F1, F2 y F3.

## 1.2 Estandarizacion de Campos

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

`client_id` y `product_id` se convierten a string y se limpian espacios. Fechas a `datetime`.

## 1.3 Mapeo de Familias

En `Productos`:

```text
Familia C1
Familia C2
Familia T1
Familia T2
```

En `Potencial`:

```text
Anestesia
Bioseguridad
Biomateriales
```

Suposicion inicial:

```text
Familia C1 -> Anestesia
Familia C2 -> Bioseguridad
Familia T1 -> Biomateriales
Familia T2 -> Biomateriales
```

```python
MAP_FAMILY_TO_BUSINESS = {
    "Familia C1": "Anestesia",
    "Familia C2": "Bioseguridad",
    "Familia T1": "Biomateriales",
    "Familia T2": "Biomateriales"
}
```

Guardar:

```text
product_family       Codigo anonimo original
product_family_biz   Nombre de negocio mapeado
```

## 1.4 Limpieza de Ventas

### Valores Faltantes

Eliminar si faltan:

```text
client_id
product_id
date
```

### Transacciones Negativas

```text
units < 0
sales_value < 0
```

Representan devoluciones, reembolsos, correcciones o sustituciones.

```text
is_return = True if units < 0 or sales_value < 0
```

Mantener:

```text
net_units  = sum(units)
net_value  = sum(sales_value)

gross_units = sum(max(units, 0))
gross_value = sum(max(sales_value, 0))
```

Para F1, eventos de compra:

```text
units > 0
```

### Duplicados

Deduplicar por:

```text
Num.Fact
client_id
product_id
date
```

### Precio Unitario Anomalo

```text
unit_price = sales_value / units
```

Si:

```text
abs(unit_price) > 10000
```

marcar o eliminar.

## 1.5 Tabla Maestra

```text
df_master =
Ventas
LEFT JOIN Productos ON product_id
LEFT JOIN Clientes  ON client_id
```

Campos:

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

No mezclar `Potencial` a nivel transaccion para evitar duplicacion. Mantener:

```text
df_potential:
client_id
product_family_biz
potential_value
```

## 1.6 Weekly Panel

Granularidad F1:

```text
client_id x product_family x week_start
```

Agregar:

```text
weekly_units      = sum(units where units > 0)
weekly_value      = sum(sales_value where sales_value > 0)
order_count       = number of unique invoices
return_units      = sum(abs(units) where units < 0)
had_purchase      = 1 if order_count > 0 else 0
```

Completar semanas faltantes con ceros:

```text
weekly_units = 0
weekly_value = 0
order_count = 0
return_units = 0
had_purchase = 0
```

## 1.7 Campaign Flag

Si una semana:

```text
[week_start, week_start + 6 days]
```

se cruza con una campana:

```text
campaign_active = 1
```

si no:

```text
campaign_active = 0
```

## 1.8 Cold-start Clients

Clientes en `Potencial` sin ventas historicas:

```text
tienen potencial comercial
pero no historial de compra
```

Salida:

```text
df_cold_clients
```

Son mas adecuados para F3 que para F1.

---

# 2. F1 - Replenishment Intelligence

## 2.1 Objetivo

Identificar clientes que pueden necesitar reposicion en:

```text
product_block == "Commodities"
```

Pregunta:

```text
El cliente esta cerca o por encima de su ciclo normal de reposicion?
Debe ventas contactarlo?
```

## 2.2 Granularidad

```text
client_id x product_family
week
```

Weekly se elige porque:

```text
daily es demasiado disperso;
weekly conserva el ritmo;
weekly sirve para modelos secuenciales.
```

## 2.3 Baseline Estadistico con Estacionalidad

Idea:

```text
No mirar solo el promedio anual.
Considerar la variacion normal del trimestre actual.
```

### 2.3.1 Intervalos de Compra

Para cada `client_id x product_family`, extraer semanas con compra y calcular:

```text
interval_days[i] = purchase_date[i] - purchase_date[i-1]
```

Etiquetar por trimestre:

```text
Q1: Jan-Mar
Q2: Apr-Jun
Q3: Jul-Sep
Q4: Oct-Dec
```

### 2.3.2 Fallback Jerarquico

Level A:

```text
client_id x product_family x quarter
n_purchases_cfq >= 3
```

Level B:

```text
client_id x product_family
n_purchases_cf >= 4
```

Level C:

```text
product_family x quarter
```

o:

```text
segment_code x product_family x quarter
```

### 2.3.3 Delay Score

Calcular:

```text
last_purchase_date
days_since_last_purchase
expected_interval
expected_reorder_date
delay
```

```text
delay = days_since_last_purchase - expected_interval
```

```text
seasonal_time_score = max(0, delay / std_interval)
std_interval = max(std_interval, 3 days)
```

### 2.3.4 Factor de Valor Comercial

```text
raw_value = max(potential_value, historical_value_12m)
value_factor = minmax(log1p(raw_value))
```

```text
replenishment_score = seasonal_time_score x value_factor
```

### 2.3.5 Priority Level

```text
P1 Critical : top 5%
P2 High     : next 15%
P3 Medium   : next 30%
P4 Low      : remaining
```

Si `seasonal_time_score == 0`, marcar:

```text
On track
```

### 2.3.6 Salida F1 Baseline

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

## 2.4 Modelo Secuencial GRU

El GRU complementa el baseline con una probabilidad basada en secuencias historicas.

### 2.4.1 Tarea

```text
Dadas L semanas pasadas,
predecir si habra compra en las proximas 4 semanas.
```

```text
y_t = 1 if had_purchase in weeks [t+1, t+2, t+3, t+4]
y_t = 0 otherwise
```

### 2.4.2 Features

Lookback de 12 semanas.

```text
weekly_units
weekly_value
order_count
days_since_last_purchase
rolling_mean_units_4w
campaign_active
potential_gap_ratio
```

Estaticas:

```text
log1p(potential_value)
segment_code
province
product_family
```

### 2.4.3 Split Temporal

```text
Train: 2021-04-01 -> 2024-06-30
Val:   2024-07-01 -> 2024-12-31
Test:  2025-01-01 -> 2025-11-30
```

### 2.4.4 Estructura

```text
Input: 12-week sequence x feature_dim
GRU hidden_size = 32
Take last hidden state
Concatenate static features
MLP classifier
Output: reorder_probability
```

### 2.4.5 Metricas

```text
AUROC
AUPRC
Positive-class F1
Precision@TopK
Recall@TopK
Lift@TopK
Brier Score
```

### 2.4.6 Fusion Final

```text
f1_final_score =
0.5 x rank_percentile(replenishment_score)
+
0.5 x rank_percentile(reorder_probability)
```

Salida:

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

## 3.1 Objetivo

Identificar clientes probablemente perdidos o en alto riesgo, especialmente para:

```text
product_block == "Productos Tecnicos"
```

Pregunta:

```text
El cliente compro antes una familia tecnica.
Han caido recientemente frecuencia, volumen o actividad?
```

## 3.2 Granularidad

```text
client_id x product_family x month
```

Monthly es mejor porque productos tecnicos son dispersos.

Agregar:

```text
monthly_units
monthly_value
order_count
had_purchase
```

## 3.3 Ventanas

```text
historical_window = ultimos 24 meses excluyendo los ultimos 6
recent_window = ultimos 6 meses
```

## 3.4 Features

### Volume Drop

```text
volume_drop_ratio =
max(0, historical_avg_units - recent_avg_units)
/
historical_avg_units
```

### Frequency Drop

```text
historical_purchase_rate =
months_with_purchase_historical / total_historical_months

recent_purchase_rate =
months_with_purchase_recent / total_recent_months

frequency_drop_ratio =
max(0, historical_purchase_rate - recent_purchase_rate)
```

### Silence Score

```text
silence_score =
days_since_last_purchase / historical_p90_interval
```

### Trend Score

```text
monthly_units ~ time
trend_score = max(0, -trend_slope)
```

## 3.5 Lost Customer Score

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

```text
f2_priority_score =
lost_customer_score x value_factor
```

## 3.6 Lost Status

```text
Likely Lost
At Risk
Early Warning
Stable
```

Reglas:

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

## 3.7 Salida F2

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

## 3.8 Evaluacion F2

Proxy label:

```text
y = 1 if client-family has no purchase in next 6 months
        OR next 6-month value drops > 60% vs historical baseline

y = 0 otherwise
```

Metricas:

```text
AUROC
AUPRC
Positive-class F1
Precision@TopK
Lift@TopK
```

---

# 4. F3 - Capture Opportunity / Competitor Leakage

## 4.1 Objetivo

Identificar oportunidades comerciales, especialmente:

```text
clientes de alto potencial con baja compra real
```

Puede indicar demanda no capturada, posible fuga a competidores u oportunidad de expansion.

No afirmar:

```text
el cliente compro a competidores
```

Usar:

```text
Potential competitor leakage
Possible unmet demand
Capture opportunity
```

## 4.2 Granularidad

```text
client_id x product_family
recent 12 months
recent 12 weeks
```

## 4.3 Potential Utilization Ratio

```text
observed_value_12m = last 12-month observed purchase value
potential_value = potential table value

utilization_ratio =
observed_value_12m / potential_value

potential_gap =
max(0, potential_value - observed_value_12m)
```

## 4.4 Recent Expected vs Observed Gap

```text
expected_12w_value =
potential_value / 52 x 12

observed_12w_value =
sum(weekly_value over last 12 weeks)

recent_gap =
max(0, expected_12w_value - observed_12w_value)
```

## 4.5 Promiscuous Customer Proxy

Senales:

```text
high potential
nonzero but low observed purchase
irregular purchase pattern
repeated under-utilization
```

```text
promiscuity_score =
high_potential_score
x low_utilization_score
x intermittent_purchase_score
```

## 4.6 Capture Window Score

```text
capture_window_score =
opportunity_score x replenishment_urgency
```

Significa que el cliente tiene potencial y esta cerca de una ventana de reposicion.

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

f3_priority_score =
opportunity_score x value_factor
```

## 4.8 Priority Level

```text
P1 Critical : top 5%
P2 High     : next 15%
P3 Medium   : next 30%
P4 Low      : remaining
```

## 4.9 Salida F3

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

`opportunity_type`:

```text
High Potential Underutilization
Potential Competitor Leakage
Capture Window
Cold-start Opportunity
```

## 4.10 Evaluacion F3

No hay ground truth directo de competidores. Usar backtesting proxy y plausibilidad de negocio.

### Future Purchase Growth Label

```text
y = 1 if future_6m_value > recent_6m_value x 1.5
y = 0 otherwise
```

### TopK Opportunity Validation

```text
Precision@TopK
Lift@TopK
Average future value growth in TopK
```

### Business Plausibility Check

```text
high potential
low utilization
nonzero purchase history
recent underperformance
```

Declarar:

```text
F3 does not directly observe competitor sales.
It evaluates potential unmet demand and possible leakage using indirect commercial signals.
```

---

# 5. Estructura de Archivos de Salida

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

# 6. Resumen de Metodologia

```text
Data Preprocessing:
unificar transacciones, productos, clientes, potencial y campanas en paneles analiticos.

F1:
para commodity products, combinar baseline estadistico estacional y GRU para generar prioridades de reposicion.

F2:
para technical products, detectar riesgo de perdida mediante caida de volumen, caida de frecuencia, silencio anomalo y tendencia negativa.

F3:
identificar demanda no capturada, posible fuga a competidores y oportunidades de captura usando la brecha entre potencial y compra observada.
```

Principio:

```text
No solo producir puntuaciones.
Tambien producir motivos explicables,
prioridad comercial,
y tablas de alertas para el Dashboard.
```

# Arquitectura Frontend/Backend del Demo y Capa de Explicacion

Tras completar F1, F2 y F3, los resultados deben mostrarse en un Dashboard interactivo. Para que el Demo no sea una pagina estatica, se propone una arquitectura modular y extensible.

```text
Data / Model Pipeline
-> Structured Alert Tables
-> Backend API
-> Gemini Explanation Layer
-> Frontend Dashboard
```

## 1. Arquitectura General

```text
Python FastAPI Backend
+ Frontend Dashboard
+ JSON-based Alert Data
+ Gemini Explanation Layer
```

FastAPI se elige porque:

1. encaja con pipelines Python;
2. lee parquet / csv / json;
3. permite endpoints claros;
4. facilita integrar Gemini API;
5. es mas dinamico que HTML estatico y mas ligero que un sistema empresarial completo.

## 2. Flujo de Datos

```text
Raw Data
-> Preprocessing
-> F1 / F2 / F3 Modules
-> Alert Tables
-> Unified Alert JSON
-> Backend API
-> Frontend Dashboard
```

Salidas:

```text
f1_combined_alerts.parquet
f2_lost_customer_alerts.parquet
f3_capture_opportunity_alerts.parquet
```

Unificacion:

```text
all_alerts.json
```

## 3. Alert Object Estandarizado

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

Campos comunes para frontend:

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

## 4. Backend API

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

| API | Funcion |
| --- | --- |
| /api/overview | KPIs de inicio |
| /api/alerts | Todas las alertas |
| /api/alerts/top5 | Top 5 acciones de hoy |
| /api/alerts/{alert_id} | Detalle de una alerta |
| /api/f1 | Alertas F1 |
| /api/f2 | Riesgo F2 |
| /api/f3 | Oportunidades F3 |
| /api/alerts/{alert_id}/status | Actualizar estado |

## 5. Frontend Dashboard

Continuar desde `main.html`.

Areas:

1. Executive Overview
2. Top 5 Commercial Actions
3. F1 Replenishment Intelligence
4. F2 Lost Customer Risk
5. F3 Capture Opportunity
6. F4 Commercial Action Queue
7. Regional Map
8. Explainability Panel

Funciones:

1. mostrar Top 5 actions;
2. filtrar F1 / F2 / F3;
3. mostrar prioridad y score;
4. expandir alertas;
5. mostrar outputs, evidencias y explicacion AI;
6. actualizar status;
7. soportar EN / ES.

## 6. Gemini Explanation Layer

Gemini no decide alertas ni sustituye F1/F2/F3. Su funcion es convertir datos estructurados en explicaciones y recomendaciones entendibles para ventas.

```text
F1 / F2 / F3 models decide.
Gemini explains.
Dashboard displays.
```

## 7. Prompt Gemini

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

Campos:

```text
ai_summary
ai_recommendation
ai_caveat
```

## 8. Cambio English / Spanish

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

Gemini tambien puede generar explicaciones en ingles o espanol.

## 9. Integracion del Proyecto

1. Ejecutar pipeline de datos.
2. Generar alert tables F1 / F2 / F3.
3. Fusionar en `all_alerts.json`.
4. FastAPI lee `all_alerts.json`.
5. Gemini genera explicaciones.
6. Frontend obtiene datos por API.
7. Usuarios ven, filtran, expanden y actualizan alertas.

## 10. Prioridades de Implementacion

Priority 1:

- generar `all_alerts.json`;
- FastAPI: `/api/alerts` y `/api/alerts/top5`;
- frontend muestra Top 5 actions;
- click expande detalle.

Priority 2:

- filtro F1 / F2 / F3;
- explicacion generada por Gemini;
- distribucion de prioridades y mapa.

Priority 3:

- status update;
- switch English / Spanish;
- Commercial Action Queue completa.

## 11. Principios de Diseno

```text
model outputs must be structured;
explanation text must be based on structured data;
frontend display must focus on commercial actions;
architecture should remain lightweight, modular, and extensible.
```

Resumen:

```text
Data pipeline generates the signals.
Backend serves the signals.
Gemini explains the signals.
Dashboard operationalizes the signals.
```
