"""
Probar rutas en demoemision, api y factura .thefactoryhka.com.co
"""
import requests

domains = [
    "demoemision.thefactoryhka.com.co",
    "api.thefactoryhka.com.co",
    "factura.thefactoryhka.com.co"
]

paths = [
    "/ws/v1.0/Service.svc",
    "/ws/v1/Service.svc",
    "/ws/Service.svc",
    "/Service.svc",
    "/api/v1.0/Factura",
    "/api/v1/Factura",
    "/api/Factura",
    "/api/v1.0/Documentos/Factura",
    "/api/v1/Documentos/Factura",
    "/v1.0/Factura",
    "/v1/Factura",
    "/factura",
    "/ws",
    "/api"
]

for d in domains:
    for p in paths:
        url = f"https://{d}{p}"
        try:
            r = requests.post(url, json={"test": True}, timeout=3)
            if r.status_code != 404:
                print(f"POST {url} -> Status: {r.status_code}, Length: {len(r.content)}")
                print(f"   Header: {r.headers.get('content-type')}")
                print(f"   Snippet: {r.text[:200]}\n")
        except Exception as e:
            pass
