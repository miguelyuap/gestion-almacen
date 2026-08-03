"""
Generador Administrativo de Claves de Licencia para gestion-almacen.
Uso: Ejecute este script para emitir claves oficiales de renovación (3, 6 o 12 meses) al recibir pagos de clientes.
"""

from __future__ import annotations

import sys
import base_datos as db


def main():
    print("=========================================================")
    print("   GENERADOR ADMINISTRATIVO DE LICENCIAS (ERP ALMACÉN)   ")
    print("=========================================================")

    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        plan = int(sys.argv[1])
    else:
        print("\nSeleccione el plan a renovar:")
        print(" 1) 3 Meses")
        print(" 2) 6 Meses")
        print(" 3) 12 Meses (1 Año)")
        opcion = input("\nIngrese la opción (1, 2 o 3): ").strip()
        
        opciones_map = {"1": 3, "2": 6, "3": 12}
        plan = opciones_map.get(opcion, 3)

    try:
        clave = db.generar_llave_activacion(plan)
        print("\n---------------------------------------------------------")
        print(f"  PLAN CONTRATADO: {plan} MESES")
        print(f"  CLAVE DE ACTIVACIÓN:  {clave}")
        print("---------------------------------------------------------")
        print("\nCopie esta clave y envíela al cliente por WhatsApp o correo.")
        print("El cliente solo debe ingresarla en la pantalla de activación para renovar.")
    except Exception as exc:
        print(f"\n[ERROR] No se pudo generar la clave: {exc}")


if __name__ == "__main__":
    main()
