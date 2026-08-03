"""
Script de automatización de compilación PyInstaller para gestion-almacen:
Genera una carpeta portable o ejecutable autosuficiente para PC (Windows / Linux).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def compilar_ejecutable():
    print("=========================================================")
    print("   COMPILADOR DE EJECUTABLE ESCRITORIO (PyInstaller)   ")
    print("=========================================================")

    # 1. Verificar si PyInstaller está instalado
    try:
        import PyInstaller
        print(f"[OK] PyInstaller detectado (Versión: {PyInstaller.__version__})")
    except ImportError:
        print("[INFO] PyInstaller no está instalado. Instalando...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 2. Definir separador de datos según SO
    separator = ";" if os.name == "nt" else ":"

    add_templates = f"templates{separator}templates"
    add_static = f"static{separator}static"

    # 3. Construir comando PyInstaller
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--name=GestionAlmacen",
        f"--add-data={add_templates}",
        f"--add-data={add_static}",
        "run_app.py",
    ]

    print("\n[INFO] Ejecutando comando de compilación:")
    print(" ".join(cmd))
    print("\nCompilando... Por favor espere...")

    res = subprocess.run(cmd, cwd=str(BASE_DIR))
    if res.returncode == 0:
        dist_dir = BASE_DIR / "dist" / "GestionAlmacen"
        exe_name = "GestionAlmacen.exe" if os.name == "nt" else "GestionAlmacen"
        exe_path = dist_dir / exe_name

        print("\n=========================================================")
        print("   ¡COMPILACION COMPLETADA CON EXITO!                    ")
        print("=========================================================")
        print(f"Ubicación del ejecutable generado: {exe_path}")
        print("\nPara distribuir a otro PC:")
        print(f"1. Copie la carpeta completa: {dist_dir}")
        print(f"2. Ejecute el archivo: {exe_name}")
        print("3. La base de datos virgen se creará automáticamente en la primera ejecución.")
    else:
        print("\n[ERROR] Ocurrió un problema durante la compilación con PyInstaller.")


if __name__ == "__main__":
    compilar_ejecutable()
