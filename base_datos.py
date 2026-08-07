"""
Gestión de la base de datos SQLite local (almacen.db) para ERP Local.
Arquitectura minimalista con transacciones atómicas para Kárdex, Compras y Facturación POS.
"""

from __future__ import annotations

import sqlite3
import hashlib
import hmac
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Generator, Iterable, Optional
from werkzeug.security import check_password_hash, generate_password_hash

def obtener_ruta_db_usuario() -> Path:
    """
    Retorna la ruta de la base de datos en el directorio de datos del usuario
    para garantizar persistencia y base de datos virgen en nuevas instalaciones.
    """
    if os.environ.get("GESTION_ALMACEN_DB"):
        return Path(os.environ["GESTION_ALMACEN_DB"])
    
    if os.name == "nt":
        app_data = Path(os.getenv("APPDATA", Path.home())) / "GestionAlmacen"
    else:
        app_data = Path.home() / ".config" / "gestion-almacen"
    
    app_data.mkdir(parents=True, exist_ok=True)
    return app_data / "almacen.db"


DB_PATH = obtener_ruta_db_usuario()


@contextmanager
def conexion() -> Generator[sqlite3.Connection, None, None]:
    """Abre una conexión SQLite con row_factory dict-like y foreign keys activadas."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ejecutar(sql: str, params: Iterable[Any] = ()) -> int:
    with conexion() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.lastrowid or cur.rowcount


def _consultar(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    with conexion() as conn:
        return list(conn.execute(sql, tuple(params)))


def _consultar_uno(sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
    with conexion() as conn:
        return conn.execute(sql, tuple(params)).fetchone()


def inicializar_db() -> None:
    """Crea la estructura de tablas del ERP e incluye rutinas de migración."""
    with conexion() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")

        tablas_existentes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        if "compras" in tablas_existentes:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(compras)").fetchall()}
            if "numero_orden" not in cols:
                conn.execute("DROP TABLE IF EXISTS compras_detalles")
                conn.execute("ALTER TABLE compras RENAME TO legacy_compras")

        # Asegurar que compras_detalles se vuelva a crear si apunta a un legacy
        if "compras_detalles" in tablas_existentes:
            fk_list = conn.execute("PRAGMA foreign_key_list(compras_detalles)").fetchall()
            for fk in fk_list:
                if fk["table"] == "legacy_compras":
                    conn.execute("DROP TABLE compras_detalles")
                    break

        if "inventario" in tablas_existentes and "legacy_inventario" not in tablas_existentes:
            conn.execute("ALTER TABLE inventario RENAME TO legacy_inventario")

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS almacenes (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre    TEXT NOT NULL,
                ubicacion TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS productos (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo       TEXT NOT NULL UNIQUE,
                nombre       TEXT NOT NULL,
                precio_venta REAL NOT NULL DEFAULT 0 CHECK (precio_venta >= 0),
                stock_minimo INTEGER NOT NULL DEFAULT 5 CHECK (stock_minimo >= 0)
            );

            CREATE TABLE IF NOT EXISTS stock_bodega (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER NOT NULL,
                almacen_id  INTEGER NOT NULL,
                cantidad    INTEGER NOT NULL DEFAULT 0 CHECK (cantidad >= 0),
                FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE,
                FOREIGN KEY (almacen_id) REFERENCES almacenes(id) ON DELETE CASCADE,
                UNIQUE(producto_id, almacen_id)
            );

            CREATE TABLE IF NOT EXISTS kardex (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id     INTEGER NOT NULL,
                almacen_id      INTEGER NOT NULL,
                tipo_movimiento TEXT NOT NULL CHECK (tipo_movimiento IN ('ENTRADA', 'SALIDA', 'AJUSTE')),
                cantidad        INTEGER NOT NULL,
                costo_unitario  REAL NOT NULL DEFAULT 0 CHECK (costo_unitario >= 0),
                referencia      TEXT NOT NULL DEFAULT '',
                fecha           TEXT NOT NULL,
                FOREIGN KEY (producto_id) REFERENCES productos(id),
                FOREIGN KEY (almacen_id) REFERENCES almacenes(id)
            );

            CREATE TABLE IF NOT EXISTS compras (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_orden TEXT NOT NULL UNIQUE,
                proveedor    TEXT NOT NULL,
                almacen_id   INTEGER NOT NULL,
                estado       TEXT NOT NULL DEFAULT 'pendiente'
                             CHECK (estado IN ('pendiente', 'recibido', 'rechazado')),
                total        REAL NOT NULL DEFAULT 0,
                fecha        TEXT NOT NULL,
                FOREIGN KEY (almacen_id) REFERENCES almacenes(id)
            );

            CREATE TABLE IF NOT EXISTS compras_detalles (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                compra_id      INTEGER NOT NULL,
                producto_id    INTEGER NOT NULL,
                cantidad       INTEGER NOT NULL CHECK (cantidad > 0),
                costo_unitario REAL NOT NULL DEFAULT 0 CHECK (costo_unitario >= 0),
                subtotal       REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (compra_id) REFERENCES compras(id) ON DELETE CASCADE,
                FOREIGN KEY (producto_id) REFERENCES productos(id)
            );

            CREATE TABLE IF NOT EXISTS ventas (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_factura     TEXT NOT NULL UNIQUE,
                cliente_nombre     TEXT NOT NULL DEFAULT 'Cliente General',
                cliente_nit        TEXT NOT NULL DEFAULT '222222222222',
                cliente_email      TEXT NOT NULL DEFAULT '',
                almacen_id         INTEGER NOT NULL,
                usuario_id         INTEGER DEFAULT NULL,
                subtotal           REAL NOT NULL DEFAULT 0,
                iva_total          REAL NOT NULL DEFAULT 0,
                total              REAL NOT NULL DEFAULT 0,
                metodo_pago        TEXT NOT NULL DEFAULT 'Efectivo',
                estado             TEXT NOT NULL DEFAULT 'completada' CHECK (estado IN ('completada', 'anulada')),
                estado_electronico TEXT NOT NULL DEFAULT 'no_aplica' CHECK (estado_electronico IN ('no_aplica', 'pendiente', 'transmitido', 'error')),
                cufe               TEXT DEFAULT NULL,
                fecha              TEXT NOT NULL,
                FOREIGN KEY (almacen_id) REFERENCES almacenes(id),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            );

            CREATE TABLE IF NOT EXISTS ventas_detalles (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                venta_id            INTEGER NOT NULL,
                producto_id         INTEGER NOT NULL,
                cantidad            INTEGER NOT NULL CHECK (cantidad > 0),
                precio_unitario     REAL NOT NULL DEFAULT 0,
                impuesto_porcentaje REAL NOT NULL DEFAULT 19.0,
                subtotal            REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE,
                FOREIGN KEY (producto_id) REFERENCES productos(id)
            );

            CREATE TABLE IF NOT EXISTS activos_fijos (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo       TEXT NOT NULL UNIQUE,
                nombre       TEXT NOT NULL,
                num_serie    TEXT NOT NULL DEFAULT '',
                responsable  TEXT NOT NULL DEFAULT '',
                estado       TEXT NOT NULL DEFAULT 'activo'
                             CHECK (estado IN ('activo', 'en_mantenimiento', 'baja'))
            );

            CREATE TABLE IF NOT EXISTS usuarios (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre         TEXT NOT NULL,
                usuario        TEXT NOT NULL UNIQUE,
                password_hash  TEXT NOT NULL,
                rol            TEXT NOT NULL DEFAULT 'empleado'
                               CHECK (rol IN ('admin', 'empleado')),
                fecha_creacion TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS licencias (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                clave_licencia       TEXT NOT NULL UNIQUE,
                plan_meses           INTEGER NOT NULL DEFAULT 3,
                fecha_inicio         TEXT NOT NULL,
                fecha_vencimiento    TEXT NOT NULL,
                estado               TEXT NOT NULL DEFAULT 'ACTIVA' CHECK (estado IN ('ACTIVA', 'VENCIDA')),
                fecha_ultimo_chequeo TEXT NOT NULL
            );
            """
        )

        # Migraciones de columnas adicionales en ventas / ventas_detalles para Facturación Electrónica y RBAC
        cols_ventas = {col["name"] for col in conn.execute("PRAGMA table_info(ventas)").fetchall()}
        if "cliente_email" not in cols_ventas:
            conn.execute("ALTER TABLE ventas ADD COLUMN cliente_email TEXT NOT NULL DEFAULT ''")
        if "usuario_id" not in cols_ventas:
            conn.execute("ALTER TABLE ventas ADD COLUMN usuario_id INTEGER DEFAULT NULL")
        if "subtotal" not in cols_ventas:
            conn.execute("ALTER TABLE ventas ADD COLUMN subtotal REAL NOT NULL DEFAULT 0")
        if "iva_total" not in cols_ventas:
            conn.execute("ALTER TABLE ventas ADD COLUMN iva_total REAL NOT NULL DEFAULT 0")
        if "estado" not in cols_ventas:
            conn.execute("ALTER TABLE ventas ADD COLUMN estado TEXT NOT NULL DEFAULT 'completada'")
        if "estado_electronico" not in cols_ventas:
            conn.execute("ALTER TABLE ventas ADD COLUMN estado_electronico TEXT NOT NULL DEFAULT 'no_aplica'")
        if "cufe" not in cols_ventas:
            conn.execute("ALTER TABLE ventas ADD COLUMN cufe TEXT DEFAULT NULL")
        if "mensaje_error_electronico" not in cols_ventas:
            conn.execute("ALTER TABLE ventas ADD COLUMN mensaje_error_electronico TEXT DEFAULT NULL")

        cols_detalles = {col["name"] for col in conn.execute("PRAGMA table_info(ventas_detalles)").fetchall()}
        if "impuesto_porcentaje" not in cols_detalles:
            conn.execute("ALTER TABLE ventas_detalles ADD COLUMN impuesto_porcentaje REAL NOT NULL DEFAULT 19.0")

        # Semilla almacén por defecto si está vacía
        cnt_almacenes = conn.execute("SELECT COUNT(*) AS n FROM almacenes").fetchone()["n"]
        if cnt_almacenes == 0:
            conn.execute(
                "INSERT INTO almacenes (nombre, ubicacion) VALUES (?, ?)",
                ("Bodega Principal", "Sede Central"),
            )

        # Semilla usuario administrador por defecto si no existe ningún usuario
        cnt_usuarios = conn.execute("SELECT COUNT(*) AS n FROM usuarios").fetchone()["n"]
        if cnt_usuarios == 0:
            pass_hash = generate_password_hash("admin123")
            fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                """
                INSERT INTO usuarios (nombre, usuario, password_hash, rol, fecha_creacion)
                VALUES (?, ?, ?, 'admin', ?)
                """,
                ("Administrador Principal", "admin", pass_hash, fecha_ahora),
            )

        # Semilla licencia inicial de prueba (3 Meses) si no existe ninguna licencia
        cnt_licencias = conn.execute("SELECT COUNT(*) AS n FROM licencias").fetchone()["n"]
        if cnt_licencias == 0:
            ahora = datetime.now()
            fecha_inicio_str = ahora.strftime("%Y-%m-%d %H:%M:%S")
            vencimiento = ahora + timedelta(days=90)
            fecha_vencimiento_str = vencimiento.strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                """
                INSERT INTO licencias (clave_licencia, plan_meses, fecha_inicio, fecha_vencimiento, estado, fecha_ultimo_chequeo)
                VALUES (?, 3, ?, ?, 'ACTIVA', ?)
                """,
                ("LIC-TRIAL-3M-DEMO", fecha_inicio_str, fecha_vencimiento_str, fecha_inicio_str),
            )


        # Migrar datos de legacy_inventario si existe
        tablas_actuales = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "legacy_inventario" in tablas_actuales:
            filas_inv = conn.execute("SELECT * FROM legacy_inventario").fetchall()
            almacen_def = conn.execute("SELECT id FROM almacenes LIMIT 1").fetchone()
            almacen_id_def = almacen_def["id"] if almacen_def else 1

            for row in filas_inv:
                prod = conn.execute("SELECT id FROM productos WHERE codigo = ?", (row["codigo"],)).fetchone()
                if not prod:
                    cur = conn.execute(
                        "INSERT INTO productos (codigo, nombre, precio_venta, stock_minimo) VALUES (?, ?, ?, ?)",
                        (row["codigo"], row["nombre"], row["precio_unitario"], 5),
                    )
                    prod_id = cur.lastrowid
                else:
                    prod_id = prod["id"]

                target_almacen = row["almacen_id"] if "almacen_id" in row.keys() else almacen_id_def
                stk = conn.execute(
                    "SELECT id FROM stock_bodega WHERE producto_id = ? AND almacen_id = ?",
                    (prod_id, target_almacen),
                ).fetchone()
                if not stk:
                    conn.execute(
                        "INSERT INTO stock_bodega (producto_id, almacen_id, cantidad) VALUES (?, ?, ?)",
                        (prod_id, target_almacen, row["stock"]),
                    )

            conn.execute("DROP TABLE legacy_inventario")

        # Migrar datos de legacy_compras si existe
        if "legacy_compras" in tablas_actuales:
            almacen_def = conn.execute("SELECT id FROM almacenes LIMIT 1").fetchone()
            almacen_id_def = almacen_def["id"] if almacen_def else 1
            fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for idx, c in enumerate(conn.execute("SELECT * FROM legacy_compras").fetchall(), 1):
                num_ord = f"OC-MIG-{idx:04d}"
                subtot = float(c["cantidad"]) * float(c["precio_unitario"] or 0)
                cur_c = conn.execute(
                    "INSERT INTO compras (numero_orden, proveedor, almacen_id, estado, total, fecha) VALUES (?, ?, ?, ?, ?, ?)",
                    (num_ord, c["proveedor"], almacen_id_def, c["estado"], subtot, fecha_ahora),
                )
                c_id = cur_c.lastrowid
                p_exist = conn.execute("SELECT id FROM productos WHERE lower(nombre) = lower(?)", (c["item_descripcion"],)).fetchone()
                if p_exist:
                    pid = p_exist["id"]
                else:
                    cur_p = conn.execute(
                        "INSERT INTO productos (codigo, nombre, precio_venta, stock_minimo) VALUES (?, ?, ?, ?)",
                        (f"MIG-{idx:04d}", c["item_descripcion"], c["precio_unitario"], 5),
                    )
                    pid = cur_p.lastrowid

                conn.execute(
                    "INSERT INTO compras_detalles (compra_id, producto_id, cantidad, costo_unitario, subtotal) VALUES (?, ?, ?, ?, ?)",
                    (c_id, pid, c["cantidad"], c["precio_unitario"], subtot),
                )

            conn.execute("DROP TABLE legacy_compras")

        # Reactivar FK
        conn.execute("PRAGMA foreign_keys = ON")


# ---------------------------------------------------------------------------
# Modulo: Almacenes / Bodegas
# ---------------------------------------------------------------------------

def listar_almacenes() -> list[sqlite3.Row]:
    return _consultar("SELECT * FROM almacenes ORDER BY nombre")


def crear_almacen(nombre: str, ubicacion: str = "") -> int:
    return _ejecutar(
        "INSERT INTO almacenes (nombre, ubicacion) VALUES (?, ?)",
        (nombre.strip(), ubicacion.strip()),
    )


# ---------------------------------------------------------------------------
# Modulo: Productos & Inventarios por Bodega
# ---------------------------------------------------------------------------

def listar_productos(almacen_id: Optional[int] = None) -> list[dict[str, Any]]:
    """Devuelve el catálogo de productos con stock desglosado o filtrado por almacén."""
    with conexion() as conn:
        if almacen_id:
            sql = """
            SELECT p.*,
                   COALESCE(sb.cantidad, 0) AS stock_total,
                   a.nombre AS almacen_nombre,
                   a.id AS almacen_id
            FROM productos p
            LEFT JOIN stock_bodega sb ON sb.producto_id = p.id AND sb.almacen_id = ?
            LEFT JOIN almacenes a ON a.id = ?
            ORDER BY p.nombre
            """
            rows = conn.execute(sql, (almacen_id, almacen_id)).fetchall()
        else:
            sql = """
            SELECT p.*,
                   COALESCE(SUM(sb.cantidad), 0) AS stock_total
            FROM productos p
            LEFT JOIN stock_bodega sb ON sb.producto_id = p.id
            GROUP BY p.id
            ORDER BY p.nombre
            """
            rows = conn.execute(sql).fetchall()

        resultado = []
        for r in rows:
            d = dict(r)
            d["alerta_stock"] = d["stock_total"] <= d["stock_minimo"]
            resultado.append(d)
        return resultado


def obtener_producto(producto_id: int) -> Optional[dict[str, Any]]:
    with conexion() as conn:
        prod = conn.execute("SELECT * FROM productos WHERE id = ?", (producto_id,)).fetchone()
        if not prod:
            return None
        res = dict(prod)
        bodegas = conn.execute(
            """
            SELECT sb.*, a.nombre AS almacen_nombre
            FROM stock_bodega sb
            JOIN almacenes a ON a.id = sb.almacen_id
            WHERE sb.producto_id = ?
            """,
            (producto_id,),
        ).fetchall()
        res["bodegas"] = [dict(b) for b in bodegas]
        res["stock_total"] = sum(b["cantidad"] for b in res["bodegas"])
        return res


def crear_producto(
    codigo: str,
    nombre: str,
    precio_venta: float,
    stock_minimo: int = 5,
) -> int:
    """
    Registra únicamente la ficha maestra de un producto en el catálogo base.
    LÓGICA ERP: NO altera el stock en bodega ni genera movimientos de Kárdex.
    Las existencias se incrementan ÚNICAMENTE al recibir Órdenes de Compra o Ajustes Explícitos.
    """
    with conexion() as conn:
        cur = conn.execute(
            "INSERT INTO productos (codigo, nombre, precio_venta, stock_minimo) VALUES (?, ?, ?, ?)",
            (codigo.strip().upper(), nombre.strip(), max(0.0, precio_venta), max(0, stock_minimo)),
        )
        return cur.lastrowid


def ajustar_stock_manual(
    producto_id: int,
    almacen_id: int,
    cantidad_delta: int,
    tipo_movimiento: str = "AJUSTE",
    costo_unitario: float = 0.0,
    referencia: str = "Ajuste de Inventario",
) -> None:
    """Ajusta o registra entrada/salida manual en bodega actualizando stock y Kárdex."""
    with conexion() as conn:
        stk = conn.execute(
            "SELECT cantidad FROM stock_bodega WHERE producto_id = ? AND almacen_id = ?",
            (producto_id, almacen_id),
        ).fetchone()

        stock_actual = stk["cantidad"] if stk else 0
        nuevo_stock = stock_actual + cantidad_delta
        if nuevo_stock < 0:
            raise ValueError(f"El stock en esta bodega no puede ser negativo (Stock actual: {stock_actual}).")

        if stk:
            conn.execute(
                "UPDATE stock_bodega SET cantidad = ? WHERE producto_id = ? AND almacen_id = ?",
                (nuevo_stock, producto_id, almacen_id),
            )
        else:
            conn.execute(
                "INSERT INTO stock_bodega (producto_id, almacen_id, cantidad) VALUES (?, ?, ?)",
                (producto_id, almacen_id, nuevo_stock),
            )

        fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tipo = tipo_movimiento.upper()
        if tipo not in ("ENTRADA", "SALIDA", "AJUSTE"):
            tipo = "AJUSTE"

        conn.execute(
            """
            INSERT INTO kardex (producto_id, almacen_id, tipo_movimiento, cantidad, costo_unitario, referencia, fecha)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (producto_id, almacen_id, tipo, abs(cantidad_delta), max(0.0, costo_unitario), referencia.strip(), fecha_ahora),
        )


# ---------------------------------------------------------------------------
# Modulo: Kárdex
# ---------------------------------------------------------------------------

def listar_kardex(
    producto_id: Optional[int] = None,
    almacen_id: Optional[int] = None,
    limit: int = 100,
) -> list[sqlite3.Row]:
    params: list[Any] = []
    where_clauses = []

    if producto_id:
        where_clauses.append("k.producto_id = ?")
        params.append(producto_id)
    if almacen_id:
        where_clauses.append("k.almacen_id = ?")
        params.append(almacen_id)

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    params.append(limit)

    sql = f"""
    SELECT k.*, p.nombre AS producto_nombre, p.codigo AS producto_codigo, a.nombre AS almacen_nombre
    FROM kardex k
    JOIN productos p ON p.id = k.producto_id
    JOIN almacenes a ON a.id = k.almacen_id
    {where_sql}
    ORDER BY k.id DESC
    LIMIT ?
    """
    return _consultar(sql, params)


# ---------------------------------------------------------------------------
# Modulo: Compras & Órdenes de Compra
# ---------------------------------------------------------------------------

def listar_compras() -> list[sqlite3.Row]:
    return _consultar(
        """
        SELECT c.*, a.nombre AS almacen_nombre
        FROM compras c
        JOIN almacenes a ON a.id = c.almacen_id
        ORDER BY c.id DESC
        """
    )


def obtener_compra_con_detalles(compra_id: int) -> Optional[dict[str, Any]]:
    with conexion() as conn:
        compra = conn.execute(
            """
            SELECT c.*, a.nombre AS almacen_nombre
            FROM compras c
            JOIN almacenes a ON a.id = c.almacen_id
            WHERE c.id = ?
            """,
            (compra_id,),
        ).fetchone()
        if not compra:
            return None

        detalles = conn.execute(
            """
            SELECT cd.*, p.nombre AS producto_nombre, p.codigo AS producto_codigo
            FROM compras_detalles cd
            JOIN productos p ON p.id = cd.producto_id
            WHERE cd.compra_id = ?
            """,
            (compra_id,),
        ).fetchall()

        res = dict(compra)
        res["detalles"] = [dict(d) for d in detalles]
        return res


def crear_orden_compra(
    proveedor: str,
    almacen_id: int,
    items: list[dict[str, Any]],
) -> int:
    """
    Crea una Orden de Compra en estado 'pendiente'.
    `items` debe ser una lista de dicts: [{'producto_id': int, 'cantidad': int, 'costo_unitario': float}]
    """
    if not items:
        raise ValueError("La orden de compra debe incluir al menos un producto.")

    fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with conexion() as conn:
        num_count = conn.execute("SELECT COUNT(*) FROM compras").fetchone()[0] + 1
        numero_orden = f"OC-{num_count:05d}"

        total_orden = 0.0
        detalles_procesados = []

        for it in items:
            p_id = int(it["producto_id"])
            cant = int(it["cantidad"])
            costo = float(it["costo_unitario"])
            if cant <= 0:
                raise ValueError("La cantidad debe ser mayor a 0.")
            subtotal = cant * costo
            total_orden += subtotal
            detalles_procesados.append((p_id, cant, costo, subtotal))

        cur = conn.execute(
            """
            INSERT INTO compras (numero_orden, proveedor, almacen_id, estado, total, fecha)
            VALUES (?, ?, ?, 'pendiente', ?, ?)
            """,
            (numero_orden, proveedor.strip(), almacen_id, total_orden, fecha_ahora),
        )
        compra_id = cur.lastrowid

        for p_id, cant, costo, subtotal in detalles_procesados:
            conn.execute(
                """
                INSERT INTO compras_detalles (compra_id, producto_id, cantidad, costo_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?)
                """,
                (compra_id, p_id, cant, costo, subtotal),
            )

        return compra_id


def cambiar_estado_compra(compra_id: int, nuevo_estado: str) -> None:
    """
    Cambia el estado de la compra. Si cambia a 'recibido', realiza la entrada atómica a stock y Kárdex.
    """
    nuevo_estado = nuevo_estado.lower()
    if nuevo_estado not in ("recibido", "rechazado", "cancelado"):
        raise ValueError("Estado no válido.")

    with conexion() as conn:
        compra = conn.execute("SELECT * FROM compras WHERE id = ?", (compra_id,)).fetchone()
        if not compra:
            raise ValueError("Orden de compra no encontrada.")

        if compra["estado"] != "pendiente":
            raise ValueError(f"No se puede cambiar el estado de una orden que ya está '{compra['estado']}'.")

        if nuevo_estado == "recibido":
            detalles = conn.execute(
                "SELECT * FROM compras_detalles WHERE compra_id = ?", (compra_id,)
            ).fetchall()

            almacen_id = compra["almacen_id"]
            fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for det in detalles:
                prod_id = det["producto_id"]
                cant = det["cantidad"]
                costo = det["costo_unitario"]

                stk = conn.execute(
                    "SELECT cantidad FROM stock_bodega WHERE producto_id = ? AND almacen_id = ?",
                    (prod_id, almacen_id),
                ).fetchone()

                if stk:
                    conn.execute(
                        "UPDATE stock_bodega SET cantidad = cantidad + ? WHERE producto_id = ? AND almacen_id = ?",
                        (cant, prod_id, almacen_id),
                    )
                else:
                    conn.execute(
                        "INSERT INTO stock_bodega (producto_id, almacen_id, cantidad) VALUES (?, ?, ?)",
                        (prod_id, almacen_id, cant),
                    )

                conn.execute(
                    """
                    INSERT INTO kardex (producto_id, almacen_id, tipo_movimiento, cantidad, costo_unitario, referencia, fecha)
                    VALUES (?, ?, 'ENTRADA', ?, ?, ?, ?)
                    """,
                    (prod_id, almacen_id, cant, costo, f"Recepción {compra['numero_orden']}", fecha_ahora),
                )

        conn.execute("UPDATE compras SET estado = ? WHERE id = ?", (nuevo_estado, compra_id))


# ---------------------------------------------------------------------------
# Modulo: Facturación Local / Ventas POS
# ---------------------------------------------------------------------------

def listar_ventas(limite: int = 50) -> list[sqlite3.Row]:
    return _consultar(
        """
        SELECT v.*, a.nombre AS almacen_nombre, u.nombre AS cajero_nombre
        FROM ventas v
        JOIN almacenes a ON a.id = v.almacen_id
        LEFT JOIN usuarios u ON u.id = v.usuario_id
        ORDER BY v.id DESC
        LIMIT ?
        """,
        (limite,),
    )


def obtener_venta_con_detalles(venta_id: int) -> Optional[dict[str, Any]]:
    with conexion() as conn:
        venta = conn.execute(
            """
            SELECT v.*, a.nombre AS almacen_nombre, u.nombre AS cajero_nombre
            FROM ventas v
            JOIN almacenes a ON a.id = v.almacen_id
            LEFT JOIN usuarios u ON u.id = v.usuario_id
            WHERE v.id = ?
            """,
            (venta_id,),
        ).fetchone()
        if not venta:
            return None

        detalles = conn.execute(
            """
            SELECT vd.*, p.nombre AS producto_nombre, p.codigo AS producto_codigo
            FROM ventas_detalles vd
            JOIN productos p ON p.id = vd.producto_id
            WHERE vd.venta_id = ?
            """,
            (venta_id,),
        ).fetchall()

        res = dict(venta)
        res["detalles"] = [dict(d) for d in detalles]
        return res


def procesar_venta_pos(
    almacen_id: int,
    cliente_nombre: str,
    cliente_nit: str,
    items: list[dict[str, Any]],
    metodo_pago: str = "Efectivo",
    cliente_email: str = "",
    usuario_id: int | None = None,
) -> int:
    """
    Procesa de manera atómica una venta de mostrador (POS):
    1. Valida disponibilidad de stock por producto en la bodega especificada.
    2. Calcula subtotal e IVA (19%) por ítem.
    3. Resta existencias de stock_bodega.
    4. Registra la venta (con datos para Facturación Electrónica) y sus renglones.
    5. Genera los registros de Kárdex tipo SALIDA.
    """
    if not items:
        raise ValueError("La venta debe incluir al menos un producto.")

    fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with conexion() as conn:
        detalles_procesados = []
        total_venta = 0.0
        subtotal_venta = 0.0
        iva_total_venta = 0.0

        for it in items:
            p_id = int(it["producto_id"])
            cant = int(it["cantidad"])
            if cant <= 0:
                raise ValueError("La cantidad a vender debe ser mayor a 0.")

            prod = conn.execute("SELECT * FROM productos WHERE id = ?", (p_id,)).fetchone()
            if not prod:
                raise ValueError(f"Producto ID {p_id} no existe.")

            stk = conn.execute(
                "SELECT cantidad FROM stock_bodega WHERE producto_id = ? AND almacen_id = ?",
                (p_id, almacen_id),
            ).fetchone()

            stock_disponible = stk["cantidad"] if stk else 0
            if stock_disponible < cant:
                raise ValueError(
                    f"Stock insuficiente para '{prod['nombre']}' en esta bodega. Disponible: {stock_disponible}, Requerido: {cant}."
                )

            precio = float(it.get("precio_unitario") or prod["precio_venta"])
            impuesto_pct = float(it.get("impuesto_porcentaje") or 19.0)
            
            linea_total = cant * precio
            linea_subtotal = linea_total / (1.0 + (impuesto_pct / 100.0)) if impuesto_pct > 0 else linea_total
            linea_iva = linea_total - linea_subtotal

            total_venta += linea_total
            subtotal_venta += linea_subtotal
            iva_total_venta += linea_iva

            detalles_procesados.append((p_id, cant, precio, impuesto_pct, linea_total))

        cnt_ventas = conn.execute("SELECT COUNT(*) FROM ventas").fetchone()[0] + 1
        numero_factura = f"FAC-{cnt_ventas:06d}"

        cur = conn.execute(
            """
            INSERT INTO ventas (
                numero_factura, cliente_nombre, cliente_nit, cliente_email,
                almacen_id, usuario_id, subtotal, iva_total, total, metodo_pago,
                estado, estado_electronico, fecha
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completada', 'no_aplica', ?)
            """,
            (
                numero_factura,
                cliente_nombre.strip() or "Cliente General",
                cliente_nit.strip() or "222222222222",
                cliente_email.strip(),
                almacen_id,
                usuario_id,
                round(subtotal_venta, 2),
                round(iva_total_venta, 2),
                round(total_venta, 2),
                metodo_pago,
                fecha_ahora,
            ),
        )
        venta_id = cur.lastrowid

        for p_id, cant, precio, impuesto_pct, linea_total in detalles_procesados:
            conn.execute(
                """
                INSERT INTO ventas_detalles (venta_id, producto_id, cantidad, precio_unitario, impuesto_porcentaje, subtotal)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (venta_id, p_id, cant, precio, impuesto_pct, round(linea_total, 2)),
            )

            conn.execute(
                "UPDATE stock_bodega SET cantidad = cantidad - ? WHERE producto_id = ? AND almacen_id = ?",
                (cant, p_id, almacen_id),
            )

            conn.execute(
                """
                INSERT INTO kardex (producto_id, almacen_id, tipo_movimiento, cantidad, costo_unitario, referencia, fecha)
                VALUES (?, ?, 'SALIDA', ?, 0, ?, ?)
                """,
                (p_id, almacen_id, cant, f"Venta {numero_factura}", fecha_ahora),
            )

        return venta_id


def anular_factura(factura_id: int, usuario_id: int | None = None) -> bool:
    """
    Anula una factura/venta procesada, devolviendo el stock de cada ítem
    a la bodega correspondiente y registrando la reversión en el Kárdex.
    """
    fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with conexion() as conn:
        venta = conn.execute("SELECT * FROM ventas WHERE id = ?", (factura_id,)).fetchone()
        if not venta:
            raise ValueError(f"Factura ID {factura_id} no existe.")

        if venta["estado"] == "anulada":
            raise ValueError(f"La factura {venta['numero_factura']} ya se encuentra anulada.")

        conn.execute(
            "UPDATE ventas SET estado = 'anulada' WHERE id = ?",
            (factura_id,),
        )

        detalles = conn.execute(
            "SELECT * FROM ventas_detalles WHERE venta_id = ?", (factura_id,)
        ).fetchall()

        for d in detalles:
            p_id = d["producto_id"]
            cant = d["cantidad"]
            almacen_id = venta["almacen_id"]

            conn.execute(
                "UPDATE stock_bodega SET cantidad = cantidad + ? WHERE producto_id = ? AND almacen_id = ?",
                (cant, p_id, almacen_id),
            )

            conn.execute(
                """
                INSERT INTO kardex (producto_id, almacen_id, tipo_movimiento, cantidad, costo_unitario, referencia, fecha)
                VALUES (?, ?, 'ENTRADA', ?, 0, ?, ?)
                """,
                (p_id, almacen_id, cant, f"Anulacion Venta {venta['numero_factura']}", fecha_ahora),
            )

        return True


def actualizar_estado_electronico_venta(
    venta_id: int,
    estado_electronico: str,
    cufe: Optional[str] = None,
    mensaje_error: Optional[str] = None,
) -> None:
    """Actualiza el estado de la factura electrónica, CUFE y mensaje de error en SQLite."""
    with conexion() as conn:
        try:
            conn.execute(
                """
                UPDATE ventas
                SET estado_electronico = ?,
                    cufe = COALESCE(?, cufe),
                    mensaje_error_electronico = ?
                WHERE id = ?
                """,
                (estado_electronico, cufe, mensaje_error, venta_id),
            )
        except sqlite3.IntegrityError:
            # Fallback para esquemas legacy con CHECK estricto: asigna 'pendiente' preservando el mensaje_error_electronico
            estado_fallback = "pendiente" if estado_electronico == "error" else estado_electronico
            conn.execute(
                """
                UPDATE ventas
                SET estado_electronico = ?,
                    cufe = COALESCE(?, cufe),
                    mensaje_error_electronico = ?
                WHERE id = ?
                """,
                (estado_fallback, cufe, mensaje_error, venta_id),
            )



# ---------------------------------------------------------------------------
# Modulo: Activos Fijos (Legacy Support)
# ---------------------------------------------------------------------------

def listar_activos() -> list[sqlite3.Row]:
    return _consultar("SELECT * FROM activos_fijos ORDER BY nombre")


def crear_activo(
    codigo: str,
    nombre: str,
    num_serie: str = "",
    responsable: str = "",
    estado: str = "activo",
) -> int:
    return _ejecutar(
        """
        INSERT INTO activos_fijos (codigo, nombre, num_serie, responsable, estado)
        VALUES (?, ?, ?, ?, ?)
        """,
        (codigo.strip(), nombre.strip(), num_serie.strip(), responsable.strip(), estado),
    )


# ---------------------------------------------------------------------------
# Resumen / Dashboard KPIs
# ---------------------------------------------------------------------------

def resumen_dashboard() -> dict[str, Any]:
    """Resumen consolidado para el panel principal de control ERP."""
    with conexion() as conn:
        almacenes_count = conn.execute("SELECT COUNT(*) FROM almacenes").fetchone()[0]
        productos_count = conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0]

        stock_bajo = conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT p.id
                FROM productos p
                LEFT JOIN stock_bodega sb ON sb.producto_id = p.id
                GROUP BY p.id
                HAVING COALESCE(SUM(sb.cantidad), 0) <= p.stock_minimo
            )
            """
        ).fetchone()[0]

        compras_pendientes = conn.execute("SELECT COUNT(*) FROM compras WHERE estado = 'pendiente'").fetchone()[0]
        ventas_hoy = conn.execute(
            "SELECT COALESCE(SUM(total), 0) FROM ventas WHERE date(fecha) = date('now', 'localtime')"
        ).fetchone()[0]

        valor_inventario = conn.execute(
            """
            SELECT COALESCE(SUM(sb.cantidad * p.precio_venta), 0)
            FROM stock_bodega sb
            JOIN productos p ON p.id = sb.producto_id
            """
        ).fetchone()[0]

        kardex_reciente = _consultar(
            """
            SELECT k.*, p.nombre AS producto_nombre, a.nombre AS almacen_nombre
            FROM kardex k
            JOIN productos p ON p.id = k.producto_id
            JOIN almacenes a ON a.id = k.almacen_id
            ORDER BY k.id DESC
            LIMIT 5
            """
        )

        return {
            "almacenes": almacenes_count,
            "productos": productos_count,
            "stock_bajo": stock_bajo,
            "compras_pendientes": compras_pendientes,
            "ventas_hoy": ventas_hoy,
            "valor_inventario": valor_inventario,
            "kardex_reciente": kardex_reciente,
        }


# ---------------------------------------------------------------------------
# Modulo: Usuarios y Autenticación
# ---------------------------------------------------------------------------

def autenticar_usuario(usuario_str: str, password_plana: str) -> Optional[dict[str, Any]]:
    """Verifica el usuario y contraseña. Devuelve dict del usuario si es válido, de lo contrario None."""
    with conexion() as conn:
        u = conn.execute(
            "SELECT * FROM usuarios WHERE lower(usuario) = lower(?)",
            (usuario_str.strip(),),
        ).fetchone()
        if not u:
            return None
        if check_password_hash(u["password_hash"], password_plana):
            user_dict = dict(u)
            user_dict.pop("password_hash", None)
            return user_dict
        return None


def obtener_usuario_por_id(usuario_id: int) -> Optional[dict[str, Any]]:
    with conexion() as conn:
        u = conn.execute("SELECT id, nombre, usuario, rol, fecha_creacion FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        return dict(u) if u else None


def crear_usuario(
    nombre: str,
    usuario: str,
    password_plana: str,
    rol: str = "empleado",
) -> int:
    rol = rol.lower()
    if rol not in ("admin", "empleado"):
        raise ValueError("Rol no válido. Debe ser 'admin' o 'empleado'.")
    if not password_plana or len(password_plana.strip()) < 4:
        raise ValueError("La contraseña debe tener al menos 4 caracteres.")

    pass_hash = generate_password_hash(password_plana.strip())
    fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return _ejecutar(
        """
        INSERT INTO usuarios (nombre, usuario, password_hash, rol, fecha_creacion)
        VALUES (?, ?, ?, ?, ?)
        """,
        (nombre.strip(), usuario.strip().lower(), pass_hash, rol, fecha_ahora),
    )


def listar_usuarios() -> list[dict[str, Any]]:
    with conexion() as conn:
        rows = conn.execute("SELECT id, nombre, usuario, rol, fecha_creacion FROM usuarios ORDER BY nombre").fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Control Criptográfico de Licencias y Suscripción (3, 6, 12 Meses)
# ---------------------------------------------------------------------------

SECRET_LICENSE_SALT = "ERP_ALMACEN_SALT_LICENSE_2026_SECURE_KEY"


def generar_llave_activacion(plan_meses: int, secreto: str = SECRET_LICENSE_SALT) -> str:
    """
    Genera una clave criptográfica válida de activación para 3, 6 o 12 meses.
    Formato: LIC-3M-XXXX-XXXX, LIC-6M-XXXX-XXXX, LIC-12M-XXXX-XXXX.
    """
    if plan_meses not in (3, 6, 12):
        raise ValueError("El plan debe ser de 3, 6 o 12 meses.")
    
    msg = f"PLAN_{plan_meses}M_VALID_LICENSE".encode("utf-8")
    signature = hmac.new(secreto.encode("utf-8"), msg, hashlib.sha256).hexdigest().upper()
    
    code1 = signature[:4]
    code2 = signature[4:8]
    return f"LIC-{plan_meses}M-{code1}-{code2}"


def validar_llave_activacion(llave_texto: str, secreto: str = SECRET_LICENSE_SALT) -> int:
    """
    Valida la firma de una clave de activación.
    Retorna el número de meses (3, 6 o 12) si es válida, o lanza ValueError si es inválida.
    """
    llave_limpia = llave_texto.strip().upper()
    partes = llave_limpia.split("-")
    if len(partes) < 4 or partes[0] != "LIC":
        raise ValueError("Formato de clave de activación inválido. Ejemplo: LIC-6M-A1B2-C3D4.")
    
    plan_str = partes[1]
    if not plan_str.endswith("M"):
        raise ValueError("Plan no reconocido en la clave de activación.")
    
    try:
        plan_meses = int(plan_str[:-1])
    except ValueError:
        raise ValueError("Número de meses no válido en la clave.")
    
    llave_esperada = generar_llave_activacion(plan_meses, secreto)
    if llave_limpia != llave_esperada:
        raise ValueError("Clave de activación incorrecta o no válida para este sistema.")
    
    return plan_meses


def obtener_estado_licencia() -> dict[str, Any]:
    """
    Consulta y evalúa el estado actual de la licencia del software.
    Retorna información de días restantes, estado, alerta y prevención contra atraso de reloj.
    """
    fecha_actual_dt = datetime.now()
    fecha_actual_str = fecha_actual_dt.strftime("%Y-%m-%d %H:%M:%S")

    with conexion() as conn:
        lic = conn.execute("SELECT * FROM licencias ORDER BY id DESC LIMIT 1").fetchone()
        if not lic:
            inicializar_db()
            lic = conn.execute("SELECT * FROM licencias ORDER BY id DESC LIMIT 1").fetchone()

        fecha_venc_dt = datetime.strptime(lic["fecha_vencimiento"], "%Y-%m-%d %H:%M:%S")
        fecha_ultimo_chequeo_dt = datetime.strptime(lic["fecha_ultimo_chequeo"], "%Y-%m-%d %H:%M:%S")

        # Chequeo Anti-Tampering (Reloj del sistema atrasado más de 10 minutos)
        reloj_alterado = (fecha_actual_dt < (fecha_ultimo_chequeo_dt - timedelta(minutes=10)))

        # Evaluación de vencimiento
        dias_restantes = (fecha_venc_dt - fecha_actual_dt).days

        nuevo_estado = lic["estado"]
        if fecha_actual_dt >= fecha_venc_dt or reloj_alterado:
            nuevo_estado = "VENCIDA"

        # Actualizar último chequeo y estado en BD
        if nuevo_estado != lic["estado"] or fecha_actual_dt > fecha_ultimo_chequeo_dt:
            conn.execute(
                "UPDATE licencias SET estado = ?, fecha_ultimo_chequeo = ? WHERE id = ?",
                (nuevo_estado, fecha_actual_str, lic["id"]),
            )

        return {
            "id": lic["id"],
            "clave_licencia": lic["clave_licencia"],
            "plan_meses": lic["plan_meses"],
            "fecha_inicio": lic["fecha_inicio"],
            "fecha_vencimiento": lic["fecha_vencimiento"],
            "estado": nuevo_estado,
            "dias_restantes": max(0, dias_restantes),
            "alerta_expiracion": (dias_restantes <= 10 and nuevo_estado != "VENCIDA"),
            "reloj_alterado": reloj_alterado,
        }


def activar_licencia_con_llave(llave_texto: str) -> dict[str, Any]:
    """
    Procesa e ingresa una nueva clave de activación extendiendo la vigencia por 3, 6 o 12 meses.
    """
    plan_meses = validar_llave_activacion(llave_texto)
    dias_a_sumar = plan_meses * 30 if plan_meses in (3, 6) else 365
    ahora_dt = datetime.now()
    ahora_str = ahora_dt.strftime("%Y-%m-%d %H:%M:%S")

    with conexion() as conn:
        lic = conn.execute("SELECT * FROM licencias ORDER BY id DESC LIMIT 1").fetchone()
        if lic and lic["estado"] == "ACTIVA":
            fecha_base_dt = max(ahora_dt, datetime.strptime(lic["fecha_vencimiento"], "%Y-%m-%d %H:%M:%S"))
        else:
            fecha_base_dt = ahora_dt

        nueva_venc_dt = fecha_base_dt + timedelta(days=dias_a_sumar)
        nueva_venc_str = nueva_venc_dt.strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            """
            INSERT INTO licencias (clave_licencia, plan_meses, fecha_inicio, fecha_vencimiento, estado, fecha_ultimo_chequeo)
            VALUES (?, ?, ?, ?, 'ACTIVA', ?)
            """,
            (llave_texto.strip().upper(), plan_meses, ahora_str, nueva_venc_str, ahora_str),
        )

    return obtener_estado_licencia()



if __name__ == "__main__":
    inicializar_db()
    print(f"Base de datos ERP inicializada en: {DB_PATH}")

