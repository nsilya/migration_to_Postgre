import pandas as pd
from sqlalchemy import create_engine
from urllib.parse import quote_plus

# Кодируем пароль
password = quote_plus("YourStrong@Passw0rd")
sql_url = f"mssql+pyodbc://sa:{password}@localhost:1433/RetailSource?driver=ODBC+Driver+17+for+SQL+Server"

sql_engine = create_engine(sql_url)
pg_engine = create_engine('postgresql://postgres:postgres@localhost:5432/retail_target')

# SQL Server
sql_df = pd.read_sql("SELECT * FROM dbo.customers ORDER BY id", sql_engine)
sql_checksum = sql_df.sum(numeric_only=True).sum()

# PostgreSQL
pg_df = pd.read_sql("SELECT * FROM customers ORDER BY id", pg_engine)
pg_checksum = pg_df.sum(numeric_only=True).sum()

print(f"SQL Server checksum: {sql_checksum}")
print(f"PostgreSQL checksum: {pg_checksum}")  # ← исправлено prcdint → print
print(f"Match: {sql_checksum == pg_checksum}")