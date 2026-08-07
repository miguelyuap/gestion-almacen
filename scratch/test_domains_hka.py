"""
Probar DNS y disponibilidad de subdominios HKA Colombia Demo
"""
import socket
import requests

domains = [
    "demoemision.thefactoryhka.com.co",
    "emisiondemo.thefactoryhka.com.co",
    "demoemisionvp.thefactoryhka.com.co",
    "demoemision2.thefactoryhka.com.co",
    "demo-emision.thefactoryhka.com.co",
    "demo-emisionvp.thefactoryhka.com.co",
    "emisionvp.thefactoryhka.com.co",
    "emision.thefactoryhka.com.co",
    "demofactura.thefactoryhka.com.co",
    "factura.thefactoryhka.com.co",
    "api.thefactoryhka.com.co",
    "demoapi.thefactoryhka.com.co",
    "demo-api.thefactoryhka.com.co",
]

for d in domains:
    try:
        ip = socket.gethostbyname(d)
        print(f"Domain {d} -> IP: {ip}")
        try:
            r = requests.get(f"https://{d}", timeout=3)
            print(f" -> HTTPS status: {r.status_code}")
        except Exception as e:
            print(f" -> HTTPS error: {e}")
    except Exception:
        print(f"Domain {d} -> DNS No resuelto")
