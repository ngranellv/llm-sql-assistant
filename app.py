import sqlite3
import pandas as pd

conn = sqlite3.connect("chinook.db")

query = """ SELECT FirstName AS Nombre, LastName AS Apellido
FROM Employee;
"""
resultado = pd.read_sql_query(query, conn)
print(resultado)

conn.close()