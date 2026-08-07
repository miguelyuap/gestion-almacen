"""
Escanear rutas de API en demofactura.thefactoryhka.com.co
"""
import requests

routes = [
    "/api/v1/factura",
    "/api/v1.0/factura",
    "/api/factura",
    "/api/v1/documentos",
    "/api/v1.0/documentos",
    "/api/v1/emision",
    "/api/v1.0/emision",
    "/api/v1/CargarCertificado",
    "/api/v1.0/CargarCertificado",
    "/api/v1/EstadoDocumento",
    "/api/v1.0/EstadoDocumento",
    "/ws/v1/Service.svc",
    "/ws/v1.0/Service.svc",
    "/ws/v1/Service.asmx",
    "/ws/v1.0/Service.asmx",
    "/ws/Service.svc",
    "/ws/Service.asmx",
    "/Service.svc",
    "/Service.asmx",
    "/ws/v1/factura",
    "/ws/v1.0/factura",
    "/myaccount/taxpayer",
]

base = "https://demofactura.thefactoryhka.com.co"

for r in routes:
    url = base + r
    try:
        res = requests.post(url, json={"test": 1}, timeout=3)
        print(f"POST {r} -> Status: {res.status_code}, Length: {len(res.content)}")
    except Exception as e:
        print(f"POST {r} -> Error: {e}")
