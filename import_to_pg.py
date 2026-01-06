import pandas as pd
from sqlalchemy import create_engine

# Загрузка из Parquet
df = pd.read_parquet('customers.parquet')

# Подключение к PostgreSQL
engine = create_engine(
    'postgresql://postgres:postgres@localhost:5432/retail_target'
)

# Загрузка в таблицу
df.to_sql('customers', engine, if_exists='append', index=False)
print("Import completed: customers table")

# Проверка
result = pd.read_sql("SELECT COUNT(*) FROM customers", engine)
print(f"Rows in PostgreSQL: {result.iloc[0, 0]}")