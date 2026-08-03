"""
Script de arranque para la versión ejecutable de escritorio de gestion-almacen.
- Resuelve rutas para PyInstaller (sys._MEIPASS).
- Inicializa la base de datos SQLite virgen en el directorio del usuario.
- Levanta el servidor Flask local en segundo plano.
- Abre automáticamente la aplicación en el navegador predeterminado.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Resolver ruta base para PyInstaller bundle vs ejecución directa
if getattr(sys, "frozen", False):
    # Ejecutable de PyInstaller
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent

# Importar app y base de datos
sys.path.insert(0, str(BASE_DIR))
import base_datos as db
from app import app

# Configurar carpetas de plantillas y estáticos dinámicamente
app.template_folder = str(BASE_DIR / "templates")
app.static_folder = str(BASE_DIR / "static")


def abrir_navegador():
    """Abre automáticamente la URL de la aplicación en el navegador por defecto tras 1.2 segundos."""
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:5000")


def main():
    print("=========================================================")
    print("   ERP LOCAL — GESTION DE ALMACEN (Escritorio PC)        ")
    print("=========================================================")
    
    # 1. Inicializar base de datos virgen si es la primera ejecución
    print(f"[BD] Base de Datos configurada en: {db.DB_PATH}")
    db.inicializar_db()
    print("[BD] Base de datos SQLite verificada e inicializada.")

    # 2. Abrir el navegador en segundo plano
    threading.Thread(target=abrir_navegador, daemon=True).start()

    # 3. Iniciar servidor Flask local
    print("[OK] Servidor iniciado en http://127.0.0.1:5000")
    print("[INFO] Cierre esta ventana de terminal para apagar la aplicación.")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
