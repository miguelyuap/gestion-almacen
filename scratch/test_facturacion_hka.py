"""
Suite de Pruebas Automatizadas para el Módulo de Facturación Electrónica DIAN con The Factory HKA.
Verifica mapeo de JSON, simulación de respuestas (éxito y error), persistencia en SQLite
y preservación atómica de ventas locales.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Añadir el directorio raíz al path para importar módulos locales
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

import base_datos as db
import facturacion_hka


class TestFacturacionHKA(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.DB_PATH = root_dir / "scratch" / "test_hka_almacen.db"
        if db.DB_PATH.exists():
            try:
                db.DB_PATH.unlink()
            except Exception:
                pass
        db.inicializar_db()

    def setUp(self):
        # Preparar un producto con stock en la bodega principal
        almacenes = db.listar_almacenes()
        self.almacen_id = almacenes[0]["id"]
        
        try:
            self.producto_id = db.crear_producto("HKA-001", "Impresora Térmica POS", 250000.0)
        except Exception:
            prods = db.listar_productos()
            self.producto_id = [p["id"] for p in prods if p["codigo"] == "HKA-001"][0]

        # Ingresar stock inicial
        db.ajustar_stock_manual(
            producto_id=self.producto_id,
            almacen_id=self.almacen_id,
            cantidad_delta=10,
            tipo_movimiento="ENTRADA",
            costo_unitario=180000.0,
            referencia="Stock Prueba HKA"
        )

    def test_01_mapeo_json_hka(self):
        # Crear una venta local
        items = [{
            "producto_id": self.producto_id,
            "cantidad": 2,
            "precio_unitario": 250000.0,
            "impuesto_porcentaje": 19.0
        }]
        
        venta_id = db.procesar_venta_pos(
            almacen_id=self.almacen_id,
            cliente_nombre="Empresa Prueba S.A.S.",
            cliente_nit="900999888-1",
            cliente_email="contabilidad@prueba.com",
            items=items,
            metodo_pago="Tarjeta"
        )

        venta = db.obtener_venta_con_detalles(venta_id)
        payload = facturacion_hka.mapear_venta_a_json_hka(venta)

        self.assertEqual(payload["nitEmisor"], "1020452250-8")
        self.assertEqual(payload["documento"]["adquiriente"]["numeroIdentificacion"], "900999888-1")
        self.assertEqual(payload["documento"]["adquiriente"]["email"], "contabilidad@prueba.com")
        self.assertEqual(payload["documento"]["metodoPago"], "48")  # Tarjeta
        self.assertEqual(len(payload["documento"]["items"]), 1)
        self.assertEqual(payload["documento"]["totales"]["totalPagar"], 500000.0)

    @patch("facturacion_hka.requests.post")
    def test_02_emision_exitosa_guarda_cufe(self, mock_post):
        # Configurar mock de respuesta exitosa de The Factory HKA
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"codigo":"200","mensaje":"Documento Aprobado","cufe":"CUFE-TEST-ABC123XYZ789"}'
        mock_response.json.return_value = {
            "codigo": "200",
            "mensaje": "Documento Aprobado",
            "cufe": "CUFE-TEST-ABC123XYZ789"
        }
        mock_post.return_value = mock_response

        items = [{
            "producto_id": self.producto_id,
            "cantidad": 1,
            "precio_unitario": 250000.0,
            "impuesto_porcentaje": 19.0
        }]
        venta_id = db.procesar_venta_pos(
            almacen_id=self.almacen_id,
            cliente_nombre="Cliente Exito",
            cliente_nit="1020304050",
            items=items
        )

        resultado = facturacion_hka.enviar_factura_electronica_hka(venta_id)
        
        self.assertTrue(resultado["exito"])
        self.assertEqual(resultado["cufe"], "CUFE-TEST-ABC123XYZ789")

        # Verificar actualización en SQLite
        venta_db = db.obtener_venta_con_detalles(venta_id)
        self.assertEqual(venta_db["estado_electronico"], "transmitido")
        self.assertEqual(venta_db["cufe"], "CUFE-TEST-ABC123XYZ789")

    @patch("facturacion_hka.requests.post")
    def test_03_rechazo_api_no_pierde_venta_local(self, mock_post):
        # Configurar mock de respuesta de rechazo por validación
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.content = b'{"codigo":"400","mensaje":"Error en NIT del cliente"}'
        mock_response.json.return_value = {
            "codigo": "400",
            "mensaje": "Error en NIT del cliente"
        }
        mock_post.return_value = mock_response

        items = [{
            "producto_id": self.producto_id,
            "cantidad": 1,
            "precio_unitario": 250000.0,
            "impuesto_porcentaje": 19.0
        }]
        venta_id = db.procesar_venta_pos(
            almacen_id=self.almacen_id,
            cliente_nombre="Cliente Con Error",
            cliente_nit="NIT_INVALIDO",
            items=items
        )

        resultado = facturacion_hka.enviar_factura_electronica_hka(venta_id)

        self.assertFalse(resultado["exito"])
        self.assertIn("Error en NIT del cliente", resultado["mensaje"])

        # Verificar que la venta local PERMANECE registrada en la base de datos
        venta_db = db.obtener_venta_con_detalles(venta_id)
        self.assertIsNotNone(venta_db)
        self.assertEqual(venta_db["estado"], "completada")
        self.assertEqual(venta_db["estado_electronico"], "error")
        self.assertIn("Error en NIT del cliente", venta_db["mensaje_error_electronico"])


if __name__ == "__main__":
    unittest.main()
