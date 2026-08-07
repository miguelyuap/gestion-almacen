"""
Script de Diagnóstico Directo e Integración para The Factory HKA Colombia (Ambiente Demo / Pruebas)
NIT: 1020452250-8
Clave Secreta / Token: $!53YPlhjg@y
"""

import os
import json
import logging
import requests
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Credenciales de integración Demo HKA
NIT_EMISOR = "1020452250-8"
CLAVE_SECRETA = "$!53YPlhjg@y"

# Endpoints oficiales de pruebas HKA Colombia (REST & SOAP)
ENDPOINTS_HKA = [
    {
        "nombre": "REST API v1.0 (Predeterminado Integración)",
        "url": "https://demoemision.thefactoryhka.com.co/api/v1.0/Factura",
        "tipo": "REST"
    },
    {
        "nombre": "REST Portal HKA Colombia",
        "url": "https://demofactura.thefactoryhka.com.co/api/v1.0/Factura",
        "tipo": "REST"
    },
    {
        "nombre": "SOAP WCF Service v1.0 (Validación Previa DIAN)",
        "url": "https://demoemisionvp.thefactoryhka.com.co/ws/v1.0/Service.svc",
        "tipo": "SOAP"
    }
]


def construir_payload_json_factura(numero_doc: str = "SETT-990001") -> Dict[str, Any]:
    """
    Construye el JSON exacto exigido por The Factory HKA Colombia (Validación Previa DIAN).
    """
    return {
        "nitEmisor": NIT_EMISOR,
        "tokenEmpresa": CLAVE_SECRETA,
        "tokenPassword": CLAVE_SECRETA,
        "documento": {
            "tipoDocumento": "01",  # Factura Electrónica de Venta
            "numeroDocumento": numero_doc,
            "fechaEmision": "2026-08-06",
            "horaEmision": "12:00:00-05:00",
            "moneda": "COP",
            "tipoOperacion": "10",  # Estandar DIAN
            "formaPago": "1",        # 1 = Contado
            "metodoPago": "10",       # 10 = Efectivo
            "adquiriente": {
                "tipoIdentificacion": "13",  # 13 = Cédula de Ciudadanía
                "numeroIdentificacion": "222222222222",
                "nombreRazonSocial": "Consumidor Final Pruebas",
                "email": "facturacion@ejemplo.com"
            },
            "totales": {
                "subtotal": 100000.0,
                "ivaTotal": 19000.0,
                "totalPagar": 119000.0
            },
            "items": [
                {
                    "lineaId": 1,
                    "codigoProducto": "PROD-TEST-01",
                    "descripcion": "Producto de Prueba Integracion HKA",
                    "cantidad": 1.0,
                    "precioUnitario": 100000.0,
                    "subtotal": 100000.0,
                    "impuestos": [
                        {
                            "codigoImpuesto": "01",  # IVA
                            "porcentaje": 19.0,
                            "baseImponible": 100000.0,
                            "montoImpuesto": 19000.0
                        }
                    ],
                    "totalLinea": 119000.0
                }
            ]
        }
    }


def ejecutar_diagnostico():
    print("=" * 70)
    print("DIAGNOSTICO DE CONEXION REST / SOAP -- THE FACTORY HKA COLOMBIA")
    print(f"NIT Emisor: {NIT_EMISOR}")
    print(f"Token:      {CLAVE_SECRETA[:3]}...{CLAVE_SECRETA[-2:]}")
    print("=" * 70)

    payload = construir_payload_json_factura()
    headers_rest = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {CLAVE_SECRETA}",
        "tokenEmpresa": CLAVE_SECRETA,
        "nitEmisor": NIT_EMISOR
    }

    for ep in ENDPOINTS_HKA:
        print(f"\nProbando Endpoint: {ep['nombre']}")
        print(f"   URL: {ep['url']}")
        
        try:
            if ep["tipo"] == "REST":
                response = requests.post(ep["url"], json=payload, headers=headers_rest, timeout=8)
            else:
                # Petición SOAP básica de estado
                soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                  <soap:Body>
                    <EstadoDocumento xmlns="http://tempuri.org/">
                      <tokenEmpresa>{CLAVE_SECRETA}</tokenEmpresa>
                      <tokenPassword>{CLAVE_SECRETA}</tokenPassword>
                      <datosDocumento>
                        <numeroDocumento>SETT-990001</numeroDocumento>
                      </datosDocumento>
                    </EstadoDocumento>
                  </soap:Body>
                </soap:Envelope>"""
                headers_soap = {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": "http://tempuri.org/IService/EstadoDocumento"}
                response = requests.post(ep["url"], data=soap_body, headers=headers_soap, timeout=8)

            print(f"   Status Code: {response.status_code}")
            
            if response.status_code in (200, 201):
                print("   [OK] RESPUESTA EXITOSA DE LA API (HTTP 200/201)")
                try:
                    res_json = response.json()
                    print(f"   CUFE Generado: {res_json.get('cufe') or res_json.get('cunfe') or 'N/A'}")
                    print(f"   Mensaje HKA:   {res_json.get('mensaje') or res_json.get('message') or res_json}")
                except Exception:
                    print(f"   Raw Body: {response.text[:300]}")
            else:
                print(f"   [!] Respuesta servidor: {response.status_code}")
                print(f"   Cuerpo de respuesta: {response.text[:250]}")

        except requests.Timeout:
            print("   [X] Error: Timeout de conexion (Servidor de HKA no respondio en 8s).")
        except requests.RequestException as err:
            print(f"   [X] Error de red / conexion: {err}")

    print("\n" + "=" * 70)
    print("Diagnóstico completado.")
    print("=" * 70)


if __name__ == "__main__":
    ejecutar_diagnostico()
