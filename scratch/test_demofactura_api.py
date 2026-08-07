"""
Prueba de emisión en demofactura.thefactoryhka.com.co/api/v1/factura
"""
import requests
import json

url_base = "https://demofactura.thefactoryhka.com.co/api/v1"

nit = "1020452250-8"
token = "z%864vFq9fSZ"

endpoints = [
    f"{url_base}/factura",
    f"{url_base}/Documentos/Factura",
    f"{url_base}/CargarDocumento",
    "https://demofactura.thefactoryhka.com.co/api/v1.0/Factura",
]

payload = {
    "nitEmisor": nit,
    "tokenEmpresa": token,
    "tokenPassword": token,
    "documento": {
        "tipoDocumento": "01",
        "numeroDocumento": "FAC-DEMO-001",
        "fechaEmision": "2026-08-04",
        "horaEmision": "12:00:00",
        "moneda": "COP",
        "formaPago": "1",
        "metodoPago": "10",
        "adquiriente": {
            "tipoIdentificacion": "13",
            "numeroIdentificacion": "222222222222",
            "nombreRazonSocial": "Consumidor Final",
            "email": "test@ejemplo.com"
        },
        "totales": {
            "subtotal": 10000.0,
            "ivaTotal": 1900.0,
            "totalPagar": 11900.0
        },
        "items": [
            {
                "lineaId": 1,
                "codigoProducto": "P001",
                "descripcion": "Prueba Directa HKA",
                "cantidad": 1.0,
                "precioUnitario": 10000.0,
                "subtotal": 10000.0,
                "impuestos": [
                    {
                        "codigoImpuesto": "01",
                        "porcentaje": 19.0,
                        "baseImponible": 10000.0,
                        "montoImpuesto": 1900.0
                    }
                ],
                "totalLinea": 11900.0
            }
        ]
    }
}

headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Authorization": f"Bearer {token}"
}

for ep in endpoints:
    print(f"Probando: {ep}")
    try:
        r = requests.post(ep, json=payload, headers=headers, timeout=6)
        print(f" -> Status: {r.status_code}")
        print(f" -> Content-Type: {r.headers.get('content-type')}")
        print(f" -> Text: {r.text[:400]}\n")
    except Exception as e:
        print(f" -> Error: {e}\n")
