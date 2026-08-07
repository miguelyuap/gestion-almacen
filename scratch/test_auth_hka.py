"""
Prueba de autenticación con Token Bearer e inspección de respuestas en The Factory HKA
"""
import requests

nit = "1020452250-8"
token = "z%864vFq9fSZ"

endpoints = [
    "https://api.thefactoryhka.com.co/v1/factura",
    "https://api.thefactoryhka.com.co/api/v1/factura",
    "https://demoemision.thefactoryhka.com.co/v1/factura",
    "https://demoemision.thefactoryhka.com.co/api/v1/factura",
    "https://factura.thefactoryhka.com.co/api/v1/factura",
]

headers_list = [
    {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    {"tokenEmpresa": token, "nitEmisor": nit, "Content-Type": "application/json"},
]

payload = {
    "nitEmisor": nit,
    "tokenEmpresa": token,
    "documento": {
        "tipoDocumento": "01",
        "numeroDocumento": "FAC-TEST-001"
    }
}

for url in endpoints:
    for h in headers_list:
        try:
            r = requests.post(url, json=payload, headers=h, timeout=4)
            print(f"POST {url} -> Status: {r.status_code}")
            print(f"   Headers: {r.headers}")
            print(f"   Snippet: {r.text[:300]}\n")
        except Exception as e:
            print(f"POST {url} -> Exception: {e}\n")
