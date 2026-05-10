import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# ==========================================
# 1. DATA LOADING AND RECENCY FILTERING (2 YEARS)
# ==========================================
# Loading data from the original Excel sheets
sales = pd.read_excel('Datasets.xlsx', sheet_name='Ventas')
customers = pd.read_excel('Datasets.xlsx', sheet_name='Clientes')
products = pd.read_excel('Datasets.xlsx', sheet_name='Productos')
potential = pd.read_excel('Datasets.xlsx', sheet_name='Potencial')

sales['Fecha'] = pd.to_datetime(sales['Fecha'])
today = sales['Fecha'].max() + pd.Timedelta(days=1)

# RECENCY FILTER: We only use the last 2 years to calculate habits.
# This ensures the model isn't biased by behaviors from 4 or 5 years ago.
cutoff_date = today - pd.Timedelta(days=730)
recent_sales = sales[sales['Fecha'] >= cutoff_date].copy()

def get_period(dt):
    month = dt.month
    year = dt.year
    if month == 12: return 'Christmas'
    if month == 8: return 'Summer'
    # Easter logic for specific years
    if (year == 2024 and month == 3) or (year < 2024 and month == 4): return 'Easter'
    return 'Regular'

recent_sales['Period'] = recent_sales['Fecha'].apply(get_period)
current_period = get_period(today)

# ==========================================
# 2. GLOBAL CORPORATE CLUSTERING
# ==========================================
cust_agg = recent_sales.groupby('Id. Cliente').agg(
    total_val=('Valores_H', 'sum'),
    order_count=('Num.Fact', 'nunique'),
    unique_prods=('Id. Producto', 'nunique')
).reset_index()

pot_total = potential.groupby('Id.Cliente')['Potencial_H'].sum().reset_index().rename(columns={'Id.Cliente': 'Id. Cliente'})
cust_features = pd.merge(cust_agg, pot_total, on='Id. Cliente', how='left').fillna(0)

scaler = StandardScaler()
X_scaled = scaler.fit_transform(cust_features[['total_val', 'order_count', 'unique_prods', 'Potencial_H']])
kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
cust_features['Cluster'] = kmeans.fit_predict(X_scaled)

# ==========================================
# 3. DATA PRE-WASHING AND NORMALIZATION (CAPPING)
# ==========================================
recent_sales = recent_sales.sort_values(['Id. Cliente', 'Id. Producto', 'Fecha'])
recent_sales['delta_t'] = recent_sales.groupby(['Id. Cliente', 'Id. Producto'])['Fecha'].diff().dt.days

# CAPPING: We limit the gaps to a maximum of 180 days (6 months) for stats calculation.
# This prevents means from exploding due to very isolated purchases.
recent_sales['delta_t_norm'] = recent_sales['delta_t'].clip(upper=180)

# Stats for pre-washing
check_stats = recent_sales.dropna(subset=['delta_t_norm']).groupby(['Id. Cliente', 'Id. Producto'])['delta_t_norm'].agg(['mean', 'median', 'std']).reset_index()

# PRE-WASHING FILTER:
# We remove relationships where variability is chaotic (CV > 1.2) or there is strong asymmetry.
check_stats['is_outlier'] = np.where(
    check_stats['std'] > 0,
    (np.abs(check_stats['mean'] - check_stats['median']) > (0.5 * check_stats['std'])) | 
    ((check_stats['std'] / check_stats['mean']) > 1.2), 
    False
)

outlier_pairs = check_stats[check_stats['is_outlier'] == True][['Id. Cliente', 'Id. Producto']]
print(f"Relationships (Customer, Product) discarded due to noise: {len(outlier_pairs)}")

clean_sales = recent_sales.merge(outlier_pairs, on=['Id. Cliente', 'Id. Producto'], how='left', indicator=True)
clean_sales = clean_sales[clean_sales['_merge'] == 'left_only'].drop(columns=['_merge'])

# ==========================================
# 4. ROBUST SEASONAL STATISTICS
# ==========================================
# Individual Stats (Using MEDIAN for stability)
indiv_stats = clean_sales.dropna(subset=['delta_t_norm']).groupby(['Id. Cliente', 'Id. Producto', 'Period'])['delta_t_norm'].agg(
    mean='median', 
    std='std'
).reset_index()

# Overall mean of time between purchases per customer and product (for the TOP table)
customer_product_mean = (
    clean_sales.dropna(subset=['delta_t_norm'])
    .groupby(['Id. Cliente', 'Id. Producto'])['delta_t_norm']
    .mean()
    .reset_index()
    .rename(columns={'delta_t_norm': 'avg_delta_t_customer_product'})
)

# Group Stats (Using MEDIAN)
group_deltas = pd.merge(clean_sales.dropna(subset=['delta_t_norm']), cust_features[['Id. Cliente', 'Cluster']], on='Id. Cliente')
group_stats = group_deltas.groupby(['Cluster', 'Id. Producto', 'Period'])['delta_t_norm'].agg(
    mean_gr='median', 
    std_gr='std'
).reset_index()

# ==========================================
# 5. GRADING AND CATEGORIZATION CALCULATION
# ==========================================
last_purchase = recent_sales.groupby(['Id. Cliente', 'Id. Producto'])['Fecha'].max().reset_index()
last_purchase['current_delta_t'] = (today - last_purchase['Fecha']).dt.days
global_counts = recent_sales.groupby(['Id. Cliente', 'Id. Producto']).size().reset_index(name='total_purchases')

results = pd.merge(last_purchase, global_counts, on=['Id. Cliente', 'Id. Producto'], how='left')
results = pd.merge(results, indiv_stats[indiv_stats['Period'] == current_period], on=['Id. Cliente', 'Id. Producto'], how='left')
results = pd.merge(results, customer_product_mean, on=['Id. Cliente', 'Id. Producto'], how='left')
results = pd.merge(results, cust_features[['Id. Cliente', 'Cluster']], on='Id. Cliente', how='left')
results = pd.merge(results, group_stats[group_stats['Period'] == current_period], on=['Cluster', 'Id. Producto'], how='left')

# Mapping Potential and Categories
prod_map = products[['Id.Prod', 'Categoria_H']].rename(columns={'Id.Prod': 'Id. Producto', 'Categoria_H': 'Category'})
pot_map = potential[['Id.Cliente', 'Categoria Productos', 'Potencial_H']].rename(columns={'Id.Cliente': 'Id. Cliente', 'Categoria Productos': 'Category'})
results = pd.merge(results, prod_map, on='Id. Producto', how='left')
results = pd.merge(results, pot_map, on=['Id. Cliente', 'Category'], how='left')
results['Potencial_H'] = results['Potencial_H'].fillna(0)

def calculate_model_logic_final(row):
    MAX_ACTIONABLE = 180 # Absolute 6-month wall
    
    is_new_global = (row['total_purchases'] == 1)
    is_mono_period = pd.isna(row['mean'])
    
    # --- DETERMINE DYNAMIC CHURN THRESHOLD (3X MEAN) ---
    if not is_mono_period:
        threshold = row['mean'] * 3
    elif not pd.isna(row['mean_gr']):
        threshold = row['mean_gr'] * 3
    else:
        threshold = MAX_ACTIONABLE

    # Threshold has a floor of 45 days and a ceiling of 180
    churn_threshold = min(max(threshold, 45), MAX_ACTIONABLE)

    # --- F_IN CALCULATION (Stable) ---
    term_indiv = 0 if is_mono_period else (row['current_delta_t'] / max(1, row['mean']))
    term_group = 0 if pd.isna(row['mean_gr']) else (row['current_delta_t'] / max(1, row['mean_gr']))
    f_in = term_indiv + term_group

    # --- HIERARCHICAL CLASSIFICATION ---
    # 1. Absolute Security Filter
    if row['current_delta_t'] > MAX_ACTIONABLE or row['current_delta_t'] > churn_threshold:
        status = 'Lost Customer'
        f_in = 0
    # 2. Other categories
    elif is_new_global:
        status = 'Retention (1st historic purchase)'
    elif is_mono_period:
        status = 'Out-of-period / Holiday behavior'
    elif f_in > 3: # Urgency threshold based on medians
        status = 'Retention (Seasonal Inactive)'
    else:
        status = 'Habitual'
        
    return pd.Series([f_in, status])

results[['F_in', 'Status']] = results.apply(calculate_model_logic_final, axis=1)
results['Grading'] = results['F_in'] * results['Potencial_H']

# ==========================================
# 6. EXPORT AND CLEAN TOP 10
# ==========================================
results.to_csv('Resultados_Gradacion_Final.csv', index=False)

print(f"--- Analysis Finished ---")
print(results['Status'].value_counts())

# Show Top 10 Customers with Real Opportunity
active_df = results[results['Status'] != 'Lost Customer']
top_10 = active_df.sort_values(by='Grading', ascending=False).head(10)
print("-" * 90)
print("TOP 10 ACTIONABLE OPPORTUNITIES (No 'ghosts' over 180 days)")
print(top_10[['Id. Cliente', 'Id. Producto', 'current_delta_t', 'avg_delta_t_customer_product', 'mean_gr', 'Grading']].to_string(index=False))