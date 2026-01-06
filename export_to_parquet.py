import pyodbc
import pandas as pd
import time

# Ждём, пока SQL Server будет готов
max_retries = 10
for i in range(max_retries):
    try:
        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER=localhost;'
            'DATABASE=RetailSource;'
            'UID=sa;'
            'PWD=YourStrong@Passw0rd;'
            'Connect Timeout=30;'
        )
        print("Connected to SQL Server")
        break
    except Exception as e:
        print(f"Attempt {i+1} failed: {e}")
        time.sleep(5)
else:
    raise Exception("Could not connect to SQL Server")

# Загрузка данных
df = pd.read_sql("""
    SELECT 
        id,
        name,
        email,
        created_at,
        is_active,
        notes
    FROM dbo.customers
    ORDER BY id
""", conn)

# Сохранение в Parquet
df.to_parquet('data/customers.parquet', index=False)
print("Export completed: data/customers.parquet")

conn.close()