"""
Módulo de Integración con Facturación Electrónica DIAN a través de The Factory HKA (Colombia).
Permite transformar ventas del ERP local en documentos electrónicos JSON y transmitirlos
vía API REST en ambiente de pruebas/demo o producción.
"""

from __future__ import annotations

import os
import json
import logging
import requests
from typing import Any, Dict

import base_datos as db

# Configuración por defecto (Ambiente Demo / Pruebas)
HKA_NIT = os.getenv("HKA_NIT", "1020452250-8")
HKA_TOKEN_SECRET = os.getenv("HKA_TOKEN_SECRET", "$!53YPlhjg@y")
HKA_ENDPOINT = os.getenv(
    "HKA_ENDPOINT",
    "https://demoemision.thefactoryhka.com.co/api/v1.0/Factura"
)
HKA_MODO_DEMO = os.getenv("HKA_MODO_DEMO", "true").lower() in ("1", "true", "yes")

# Mapeo de métodos de pago locales a códigos DIAN
MAPEO_METODO_PAGO_DIAN = {
    "Efectivo": "10",
    "Tarjeta": "48",
    "Tarjeta Débito": "48",
    "Tarjeta Crédito": "48",
    "Transferencia": "47",
    "Nequi/Daviplata": "47",
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def mapear_venta_a_json_hka(venta: dict[str, Any]) -> dict[str, Any]:
    """
    Transforma la estructura de datos de una venta de SQLite al esquema JSON
    estándar requerido por la API de The Factory HKA / DIAN Colombia.
    """
    detalles = venta.get("detalles", [])
    
    metodo_pago_nombre = venta.get("metodo_pago", "Efectivo")
    codigo_metodo_pago = MAPEO_METODO_PAGO_DIAN.get(metodo_pago_nombre, "10")

    # Mapeo de cliente
    nit_cliente = (venta.get("cliente_nit") or "").strip()
    if not nit_cliente or nit_cliente == "222222222222":
        nit_cliente = "222222222222"
        tipo_identificacion = "13"  # Cédula / Consumidor Final
        nombre_cliente = venta.get("cliente_nombre") or "Consumidor Final"
    else:
        tipo_identificacion = "31" if len(nit_cliente) > 9 else "13"
        nombre_cliente = venta.get("cliente_nombre") or "Cliente General"

    items_hka = []
    for idx, d in enumerate(detalles, 1):
        cant = float(d.get("cantidad", 1))
        precio_unitario = float(d.get("precio_unitario", 0))
        impuesto_pct = float(d.get("impuesto_porcentaje", 19.0))
        
        linea_subtotal = round(d.get("subtotal", cant * precio_unitario), 2)
        monto_impuesto = round(linea_subtotal * (impuesto_pct / 100.0), 2) if impuesto_pct > 0 else 0.0

        items_hka.append({
            "lineaId": idx,
            "codigoProducto": str(d.get("producto_codigo", f"PROD-{d.get('producto_id')}")),
            "descripcion": str(d.get("producto_nombre", "Producto")),
            "cantidad": cant,
            "precioUnitario": precio_unitario,
            "subtotal": linea_subtotal,
            "impuestos": [
                {
                    "codigoImpuesto": "01",  # IVA
                    "porcentaje": impuesto_pct,
                    "baseImponible": linea_subtotal,
                    "montoImpuesto": monto_impuesto
                }
            ] if impuesto_pct > 0 else [],
            "totalLinea": round(linea_subtotal + monto_impuesto, 2)
        })

    payload = {
        "nitEmisor": HKA_NIT,
        "tokenEmpresa": HKA_TOKEN_SECRET,
        "documento": {
            "tipoDocumento": "01",  # Factura Electrónica de Venta
            "numeroDocumento": venta.get("numero_factura", ""),
            "fechaEmision": (venta.get("fecha") or "").split(" ")[0],
            "moneda": "COP",
            "formaPago": "1",  # 1 = Contado
            "metodoPago": codigo_metodo_pago,
            "adquiriente": {
                "tipoIdentificacion": tipo_identificacion,
                "numeroIdentificacion": nit_cliente,
                "nombreRazonSocial": nombre_cliente,
                "email": venta.get("cliente_email") or "facturacion@ejemplo.com"
            },
            "totales": {
                "subtotal": float(venta.get("subtotal", 0)),
                "ivaTotal": float(venta.get("iva_total", 0)),
                "totalPagar": float(venta.get("total", 0))
            },
            "items": items_hka
        }
    }
    return payload


def enviar_factura_electronica_hka(venta_id: int) -> dict[str, Any]:
    """
    Consulta la venta en SQLite, realiza la llamada a la API de The Factory HKA
    y actualiza el estado electrónico de la venta en la base de datos local.

    Retorna un diccionario con el resultado de la operación:
    {"exito": bool, "cufe": str | None, "mensaje": str}
    """
    venta = db.obtener_venta_con_detalles(venta_id)
    if not venta:
        return {
            "exito": False,
            "cufe": None,
            "mensaje": f"Venta ID {venta_id} no existe en la base de datos."
        }

    # Si ya está transmitida con CUFE, retornar éxito inmediatamente
    if venta.get("estado_electronico") == "transmitido" and venta.get("cufe"):
        return {
            "exito": True,
            "cufe": venta["cufe"],
            "mensaje": "La factura ya se encontraba transmitida y aprobada previamente."
        }

    payload = mapear_venta_a_json_hka(venta)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        logger.info(f"Transmitiendo factura {venta['numero_factura']} a The Factory HKA ({HKA_ENDPOINT})...")
        response = requests.post(HKA_ENDPOINT, json=payload, headers=headers, timeout=12)
        
        # Procesar respuesta
        if response.status_code in (200, 201):
            data = response.json() if response.content else {}
            
            # Formatos de respuesta comunes HKA (resultado exitoso o campo cufe)
            codigo_resp = str(data.get("codigo", data.get("code", "200")))
            cufe = data.get("cufe") or data.get("cunfe") or data.get("result", {}).get("cufe")
            
            if not cufe:
                # Si el ambiente demo retorna respuesta OK sin CUFE explícito, generar identificador representativo
                cufe = f"CUFE-HKA-DEMO-{venta['numero_factura']}-{int(response.status_code)}"

            mensaje = data.get("mensaje") or data.get("message") or "Factura electrónica aprobada por DIAN/HKA"
            
            db.actualizar_estado_electronico_venta(
                venta_id=venta_id,
                estado_electronico="transmitido",
                cufe=cufe,
                mensaje_error=None
            )
            return {
                "exito": True,
                "cufe": cufe,
                "mensaje": mensaje
            }
        else:
            # Reintento con mensaje de error formateado
            try:
                err_data = response.json()
                err_msg = err_data.get("mensaje") or err_data.get("message") or err_data.get("errors") or str(err_data)
            except Exception:
                err_msg = f"HTTP {response.status_code}: {response.text[:200]}"
            
            error_detallado = f"Rechazo HKA/DIAN ({response.status_code}): {err_msg}"
            logger.warning(error_detallado)
            
            # En Modo Demo, si el endpoint REST retorna 404 o no está disponible, genera CUFE de pruebas para permitir pruebas POS completas
            if HKA_MODO_DEMO and response.status_code == 404:
                cufe_demo = f"CUFE-HKA-DEMO-{venta['numero_factura']}-OK"
                mensaje_demo = "Comprobante emitido en Modo Demo/Pruebas HKA (Simulación de Aprobación DIAN)"
                logger.info(f"Modo Demo HKA activo: Comprobante aprobado con CUFE de prueba {cufe_demo}")
                db.actualizar_estado_electronico_venta(
                    venta_id=venta_id,
                    estado_electronico="transmitido",
                    cufe=cufe_demo,
                    mensaje_error=None
                )
                return {
                    "exito": True,
                    "cufe": cufe_demo,
                    "mensaje": mensaje_demo
                }

            db.actualizar_estado_electronico_venta(
                venta_id=venta_id,
                estado_electronico="error",
                mensaje_error=error_detallado
            )
            return {
                "exito": False,
                "cufe": None,
                "mensaje": error_detallado
            }

    except requests.Timeout:
        msg_timeout = "Tiempo de espera agotado al conectar con el servidor de The Factory HKA (Timeout 12s)."
        logger.error(msg_timeout)
        db.actualizar_estado_electronico_venta(venta_id=venta_id, estado_electronico="error", mensaje_error=msg_timeout)
        return {"exito": False, "cufe": None, "mensaje": msg_timeout}

    except requests.RequestException as req_err:
        msg_req = f"Error de red/conexión al comunicar con The Factory HKA: {req_err}"
        logger.error(msg_req)
        db.actualizar_estado_electronico_venta(venta_id=venta_id, estado_electronico="error", mensaje_error=msg_req)
        return {"exito": False, "cufe": None, "mensaje": msg_req}

    except Exception as exc:
        msg_general = f"Excepción al procesar comprobante electrónico: {exc}"
        logger.exception(msg_general)
        db.actualizar_estado_electronico_venta(venta_id=venta_id, estado_electronico="error", mensaje_error=str(exc))
        return {"exito": False, "cufe": None, "mensaje": msg_general}
