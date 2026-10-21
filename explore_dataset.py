import sqlite3
import pandas as pd

conn = sqlite3.connect("chinook.db")
cursor = conn.cursor()

# 1. Listar todas las tablas
tablas = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
print("=== TABLAS ===")
print(tablas)
print()

# 2. Para cada tabla: columnas, tipos, y número de filas
for tabla in tablas["name"]:
    print(f"=== {tabla} ===")
    
    # Columnas y tipos
    columnas = pd.read_sql_query(f"PRAGMA table_info({tabla});", conn)
    print(columnas[["name", "type"]])
    
    # Número de filas
    num_filas = pd.read_sql_query(f"SELECT COUNT(*) AS total FROM {tabla};", conn)
    print(f"Filas: {num_filas['total'][0]}")
    
    # Claves foráneas (relaciones con otras tablas)
    claves_foraneas = pd.read_sql_query(f"PRAGMA foreign_key_list({tabla});", conn)
    if not claves_foraneas.empty:
        print("Relaciones (claves foráneas):")
        print(claves_foraneas[["from", "table", "to"]])
    
    print()

conn.close()