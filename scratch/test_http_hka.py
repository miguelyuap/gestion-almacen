"""
Probar HTTP y HTTPS para WCF / SOAP / REST de The Factory HKA Colombia
"""
import requests

urls = [
    "http://demoemision.thefactoryhka.com.co/ws/v1.0/Service.svc?wsdl",
    "https://demoemision.thefactoryhka.com.co/ws/v1.0/Service.svc?wsdl",
    "http://demoemisionvp.thefactoryhka.com.co/ws/v1.0/Service.svc?wsdl",
    "http://demoemision.thefactoryhka.com.co/api/v1.0/Factura",
    "http://demofactura.thefactoryhka.com.co/ws/v1.0/Service.svc?wsdl",
    "http://demofactura.thefactoryhka.com.co/api/v1.0/Factura",
]

for url in urls:
    try:
        r = requests.get(url, timeout=4)
        print(f"GET {url} -> Status: {r.status_code}, Length: {len(r.content)}")
        if r.status_code == 200:
            print(f" -> Header content-type: {r.headers.get('content-type')}")
            print(f" -> Body: {r.text[:250]}\n")
    except Exception as e:
        print(f"GET {url} -> Error: {e}\n")
