# ERP Gestión Almacén — Sistema de Gestión Local, POS, Kárdex, Licencias y Reportes

Resumen completo y actualizado del estado actual del aplicativo **Gestión Almacén**.

---

## 🏛️ 1. Arquitectura y Tecnologías

* **Backend:** Python (Flask) con **SQLite en modo WAL** (`journal_mode = WAL` y 30s de timeout) para garantizar transacciones rápidas y prevenir bloqueos de base de datos (`database is locked`).
* **Frontend:** **htmx** (renderizado asíncrono ultra ligero sin recargar la página), **Jinja2** y **CSS Vanilla** modernizado con fuentes Google Fonts (*Inter* e *IBM Plex Mono* con alineación de números en columnas financieras).
* **Base de Datos Portátil en Datos de Usuario:** La base de datos `almacen.db` se almacena dinámicamente en:
  * **Windows:** `%APPDATA%\GestionAlmacen\almacen.db`
  * **Linux / macOS:** `~/.config/gestion-almacen/almacen.db`
  * *Al instalar en cualquier nueva PC, crea automáticamente la base de datos limpia con el esquema completo y el usuario administrador por defecto (`admin` / `admin123`).*
* **Empaquetado para PC:** Equipado con scripts de empaquetado PyInstaller (`build_desktop.py` y `run_app.py`) para generar un ejecutable portable `.exe` que levanta el servidor local y abre la ventana del navegador en `http://127.0.0.1:5000` de forma automática.

---

## 💼 2. Módulos y Funcionalidades del ERP

### 🔐 A. Autenticación y Control de Roles (RBAC)
* Sistema de login/logout con contraseñas encriptadas (`werkzeug.security`).
* Gestión de usuarios y permisos diferenciados entre **Administrador** (acceso total, anulaciones, ajustes de inventario y licencias) y **Empleado/Cajero** (uso del POS y operaciones diarias).
* Pantalla de login elegante y centrada (ancho máximo de 420px).

### 📦 B. Maestro de Productos e Inventarios por Bodega
* **Separación Estricta ERP:** Crear un producto en el catálogo NO altera las existencias de stock ni genera Kárdex. Todas las referencias nuevas nacen en **0** por defecto.
* **Actualización de Existencias:** Las existencias se incrementan únicamente mediante la Recepción de Órdenes de Compra o por Ajustes Manuales de Inventario.
* Control de stock multi-bodega con alertas de stock mínimo.

### 🛒 C. Facturación POS / Venta Rápida
* Terminal de caja con Buscador de Productos en Tiempo Real (Combobox Searchable).
* Desglose automático de IVA 19%, Subtotal y Total a pagar.
* **Validación de Stock en Tiempo Real:** Impide ventas con inventario negativo.
* Impresión de Tiquetes Térmicos de 80mm (`templates/ticket.html`).
* **Anulación de Facturas (Solo Admin):** Revierte automáticamente las existencias a la bodega correspondiente y genera asiento Kárdex de entrada.
* Estructura preparada para Facturación Electrónica DIAN (`cufe`, `estado_electronico`, `cliente_email`).

### 🚚 D. Órdenes de Compra y Recepción
* Creación de órdenes de compra en estado pendiente.
* Proceso de recepción que incrementa el stock de forma atómica y genera los asientos correspondientes en el Kárdex.

### 📊 E. Módulo de Reportes & Exportaciones (Excel & PDF)
* **Exportaciones a Excel (`openpyxl`):**
  * *Inventario Valorizado:* Stock, costo unitario, precio de venta y valor total.
  * *Historial de Ventas POS:* Detalle de clientes, NIT, subtotal, IVA y totales.
  * *Movimientos de Kárdex:* Asientos históricos de ENTRADA, SALIDA y AJUSTE.
  * Formato profesional con cabeceras estilizadas en azul corporativo (`#0F172A`), formato nativo COP (`$ #,##0.00`) y auto-ajuste de columnas.
* **Generación de PDF (`reportlab`):**
  * *Cierre Z de Caja del Día:* Resumen formal impreso con consolidado de recaudos (efectivo, tarjetas, transferencias), desglose de facturas y firmas de responsabilidad.

### 🔑 F. Sistema de Licencias & Control de Suscripción (3, 6 y 12 Meses)
* **Licencia Inicial de Prueba:** 90 días (3 meses) incluidos automáticamente en nuevas instalaciones.
* **Protección Anti-Tampering:** Si el usuario atrasa la fecha del reloj de Windows, la aplicación detecta la alteración y bloqua el acceso.
* **Renovación por Clave Criptográfica (HMAC-SHA256):** Generación y validación de claves offline (`LIC-3M-XXXX`, `LIC-6M-XXXX`, `LIC-12M-XXXX`).
* Incluye el script administrativo `generar_licencia.py` para emitir claves al recibir pagos de clientes.
* Pantalla de bloqueo `/licencia/bloqueado` con instrucciones de pago y caja de reactivación.

### 🖥️ G. Diseño Responsivo y Multi-Dispositivo
* **Diseño para PC:** Aprovecha el 100% de la pantalla en monitores estándar, Full HD y Ultra-Wide (tableros de KPI en 4 columnas fluidas).
* **Diseño para Celulares y Tablets:** Menú desplegable hamburguesa (`☰ Menú`), botones y campos táctiles (*Thumb-Friendly* de 42px+) y tablas con scroll suave.

---

## 🧪 3. Estado de Pruebas Automatizadas

Todas las suites de prueba integradas en el proyecto están 100% operativas y en verde:

```bash
python scratch/test_auth_flow.py      # ➔ Autenticación y RBAC (Éxito)
python scratch/test_erp_flow.py       # ➔ Catálogo, Compras, Kárdex e Inventario (Éxito)
python scratch/test_pos_module.py      # ➔ Facturación POS, IVA, Tiquetes y Anulación (Éxito)
python scratch/test_licencia_module.py # ➔ Licencias, renovaciones y Anti-Tampering (Éxito)
python scratch/test_reportes_module.py # ➔ Descargas de Excel y PDF (Éxito)
```

---

## 🚀 4. ¿Cómo Ejecutar o Compilar el Proyecto?

### Para ejecutar localmente:
```bash
python app.py
```
y abre `http://localhost:5000` en tu navegador.

**Credenciales por defecto:**
- **Usuario:** `admin`
- **Contraseña:** `admin123`

### Para empaquetar el ejecutable .exe para PC:
```bash
python build_desktop.py
```
Encontrarás la carpeta compilada lista para copiar y distribuir en `dist/GestionAlmacen/`.

### Para generar una clave de licencia cuando un cliente te pague:
```bash
python generar_licencia.py
```
O especificando la duración en meses (`3`, `6` o `12`):
```bash
python generar_licencia.py 6
```
