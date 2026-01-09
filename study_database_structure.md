
---

## 🔍 Шаг 1: Анализ структуры MS SQL через системные представления

Выполни следующие запросы **внутри контейнера `mssql-server`**, чтобы собрать метаданные.

### 1. Список всех таблиц и их схем
```sql
SELECT TABLE_SCHEMA, TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_SCHEMA, TABLE_NAME;
```

### 2. Столбцы, типы, вычисляемые ли?
```sql
SELECT 
    s.name AS schema_name,
    t.name AS table_name,
    c.name AS column_name,
    ty.name AS data_type,
    c.max_length,
    c.precision,
    c.scale,
    c.is_nullable,
    c.is_computed,
    cc.definition AS computed_definition
FROM sys.columns c
JOIN sys.tables t ON c.object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.types ty ON c.user_type_id = ty.user_type_id
LEFT JOIN sys.computed_columns cc ON c.object_id = cc.object_id AND c.column_id = cc.column_id
ORDER BY s.name, t.name, c.column_id;
```

> 🔥 Обрати внимание на:
> - `is_computed = 1`
> - `data_type IN ('hierarchyid', 'geography', 'money', 'uniqueidentifier', 'datetimeoffset', 'sql_variant')`

### 3. Внешние ключи
```sql
SELECT
    fk.name AS fk_name,
    s.name AS schema_name,
    t.name AS table_name,
    c.name AS column_name,
    rt.name AS referenced_table,
    rc.name AS referenced_column
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
JOIN sys.tables t ON fk.parent_object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.columns c ON fkc.parent_object_id = c.object_id AND fkc.parent_column_id = c.column_id
JOIN sys.tables rt ON fk.referenced_object_id = rt.object_id
JOIN sys.columns rc ON fkc.referenced_object_id = rc.object_id AND fkc.referenced_column_id = rc.column_id
ORDER BY s.name, t.name;
```

### 4. Триггеры
```sql
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    tr.name AS trigger_name,
    tr.is_disabled,
    m.definition AS trigger_definition
FROM sys.triggers tr
JOIN sys.tables t ON tr.parent_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.sql_modules m ON tr.object_id = m.object_id
WHERE tr.parent_class = 1;  -- только на таблицы
```

---

## ⚠️ Шаг 2: Идентификация проблемных типов (требуют обработки в Python)

| MS SQL тип | PostgreSQL аналог | Комментарий |
|-----------|-------------------|------------|
| `hierarchyid` | `TEXT` или `LTREE` (если расширение) | Лучше → `TEXT`, если не нужна иерархическая логика |
| `geography` / `geometry` | `GEOGRAPHY` (PostGIS) | Требует установки **PostGIS** в PostgreSQL |
| `money` / `smallmoney` | `NUMERIC(19,4)` | Не использовать `MONEY` в PG — он устарел |
| `uniqueidentifier` | `UUID` | В PG есть встроенный тип |
| `datetime2` | `TIMESTAMP` | Без часового пояса |
| `datetimeoffset` | `TIMESTAMPTZ` | С часовым поясом — полный аналог |
| `bit` | `BOOLEAN` | Прямая замена |
| `nvarchar(max)`, `varchar(max)` | `TEXT` | Всё → `TEXT` |
| `varbinary(max)`, `image` | `BYTEA` | Бинарные данные |
| `sql_variant` | ❌ Нет аналога | Нужно детектировать тип на лету → хранить как JSON или TEXT |
| Вычисляемые столбцы | ❌ Нет прямого аналога | Можно хранить как `GENERATED ALWAYS AS (...) STORED` в PG 12+ |

---

## 🐍 Шаг 3: Python-стратегия миграции

### Архитектура скрипта:

```text
migrate_aw/
├── config.py              # строка подключения
├── schema_inspector.py    # анализ структуры (DDL, FK, типы)
├── type_mapper.py         # конвертация типов
├── data_extractor.py      # выгрузка данных с обработкой
├── data_loader.py         # загрузка в PG
└── migrate.py             # main
```

### Ключевые правила обработки:

1. **Пропускать системные таблицы** (`sys.*`, `INFORMATION_SCHEMA`)
2. **Порядок загрузки** — учитывать FK: сначала родительские таблицы (`Person`, `Product`), потом дочерние (`SalesOrderHeader`, `SalesOrderDetail`)
3. **Обработка специальных типов**:
   ```python
   def convert_value(val, sql_type):
       if val is None:
           return None
       if sql_type == "hierarchyid":
           return str(val)  # например: "/1/3/2/"
       if sql_type == "uniqueidentifier":
           return str(val).lower()  # UUID
       if sql_type == "money":
           return float(val)
       if sql_type == "bit":
           return bool(val)
       if sql_type == "datetimeoffset":
           return val  # pyodbc возвращает datetime с tz — psycopg2 поймёт
       if isinstance(val, (bytes, bytearray)):
           return val  # для BYTEA
       return val
   ```
4. **Вычисляемые столбцы** — не мигрировать (или создавать как `STORED` в PG)
5. **Триггеры** — переписывать вручную (PG использует PL/pgSQL)

---

## 🧪 Пример: таблица `Sales.SalesOrderHeader`

Содержит:
- `rowguid` → `uniqueidentifier` → `UUID`
- `OrderDate` → `datetime` → `TIMESTAMP`
- `TotalDue` → `money` → `NUMERIC(19,4)`
- Вычисляемый столбец? Нет.
- FK на `Customer`, `SalesPerson`, `ShipMethod`
- Есть триггер `uSalesOrderHeader` (обновляет `SalesPerson`)

→ При миграции:
- Загрузить **только данные**
- Триггер **не переносится автоматически** — нужно вручную написать аналог в PG

---

## ✅ Рекомендуемый порядок действий

1. **Выполни запросы из Шага 1** → сохрани вывод в файлы (`tables.txt`, `columns.csv`, `fks.txt`, `triggers.sql`)
2. **Создай карту типов** → определи, какие таблицы содержат `hierarchyid`, `geography` и т.д.
3. **Напиши `type_mapper.py`** — функцию конвертации
4. **Напиши DDL-генератор** → создаёт `CREATE TABLE` для PG
5. **Напиши миграцию данных** → с обработкой значений
6. **Добавь восстановление FK** → после загрузки всех таблиц
7. **Вручную перепиши критичные триггеры**, если нужны

---

## 💡 Совет

Сфокусируйся сначала на **одной схеме** — например, `Person` или `Production`.  
Она уже содержит:
- `hierarchyid` в `Employee.OrganizationNode`
- `uniqueidentifier`
- FK
- Вычисляемые столбцы (в некоторых версиях)

Когда миграция одной схемы заработает — масштабируй на всё.

---

Хочешь — дам:
- Готовый `schema_inspector.py`
- Шаблон `migrate.py` с обработкой типов
- Скрипт генерации DDL для PostgreSQL

Скажи: **«Да, дай шаблон миграции»**.
