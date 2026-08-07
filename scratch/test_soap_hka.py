"""
Prueba SOAP a Service.svc de The Factory HKA Colombia
"""
import requests

soap_env = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <EstadoDocumento xmlns="http://tempuri.org/">
      <tokenEmpresa>z%864vFq9fSZ</tokenEmpresa>
      <tokenPassword>z%864vFq9fSZ</tokenPassword>
      <datosDocumento>
        <numeroDocumento>FAC-000001</numeroDocumento>
      </datosDocumento>
    </EstadoDocumento>
  </soap:Body>
</soap:Envelope>"""

urls = [
    "https://demoemision.thefactoryhka.com.co/ws/v1.0/Service.svc",
    "https://demofactura.thefactoryhka.com.co/ws/v1.0/Service.svc",
    "https://demoemision.thefactoryhka.com.co/ws/v1/Service.svc",
]

headers = {
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction": "http://tempuri.org/IService/EstadoDocumento"
}

for u in urls:
    print(f"POST SOAP to {u}...")
    try:
        r = requests.post(u, data=soap_env, headers=headers, timeout=5)
        print(f" -> Status: {r.status_code}")
        print(f" -> Response: {r.text[:300]}\n")
    except Exception as e:
        print(f" -> Error: {e}\n")
