"""
Gestión de la base de datos SQLite local (almacen.db).
Arquitectura minimalista: conexión por contexto y helpers tipados.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Iterable, Optional

DB_PATH = Path(__file__).resolve().parent / "almacen.db"


@contextmanager
def conexion() -> Generator[sqlite3.Connection, None, None]:
    """Abre una conexión SQLite con row_factory dict-like y la cierra al salir."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
    """Crea tablas e inserta un almacén por defecto si la BD está vacía."""
    with conexion() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS almacenes (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre    TEXT NOT NULL,
                ubicacion TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS inventario (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo          TEXT NOT NULL UNIQUE,
                nombre          TEXT NOT NULL,
                almacen_id      INTEGER NOT NULL,
                stock           INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
                precio_unitario REAL NOT NULL DEFAULT 0 CHECK (precio_unitario >= 0),
                FOREIGN KEY (almacen_id) REFERENCES almacenes(id)
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

            CREATE TABLE IF NOT EXISTS compras (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                proveedor        TEXT NOT NULL,
                item_descripcion TEXT NOT NULL,
                cantidad         INTEGER NOT NULL CHECK (cantidad > 0),
                precio_unitario  REAL NOT NULL DEFAULT 0 CHECK (precio_unitario >= 0),
                tipo_item        TEXT NOT NULL
                                 CHECK (tipo_item IN ('consumible', 'activo_fijo')),
                estado           TEXT NOT NULL DEFAULT 'pendiente'
                                 CHECK (estado IN ('pendiente', 'recibido', 'cancelado'))
            );
            """
        )
        # Migración: BD creadas antes de precio_unitario en compras
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(compras)").fetchall()
        }
        if "precio_unitario" not in cols:
            conn.execute(
                "ALTER TABLE compras ADD COLUMN precio_unitario REAL NOT NULL DEFAULT 0"
            )

        existe = conn.execute("SELECT COUNT(*) AS n FROM almacenes").fetchone()["n"]
        if existe == 0:
            conn.execute(
                "INSERT INTO almacenes (nombre, ubicacion) VALUES (?, ?)",
                ("Almacén Principal", "Sede central"),
            )


# ---------------------------------------------------------------------------
# Almacenes
# ---------------------------------------------------------------------------

def listar_almacenes() -> list[sqlite3.Row]:
    return _consultar("SELECT * FROM almacenes ORDER BY nombre")


def crear_almacen(nombre: str, ubicacion: str = "") -> int:
    return _ejecutar(
        "INSERT INTO almacenes (nombre, ubicacion) VALUES (?, ?)",
        (nombre.strip(), ubicacion.strip()),
    )


# ---------------------------------------------------------------------------
# Inventario
# ---------------------------------------------------------------------------

def listar_inventario() -> list[sqlite3.Row]:
    return _consultar(
        """
        SELECT i.*, a.nombre AS almacen_nombre
        FROM inventario i
        JOIN almacenes a ON a.id = i.almacen_id
        ORDER BY i.nombre
        """
    )


def crear_item_inventario(
    codigo: str,
    nombre: str,
    almacen_id: int,
    stock: int = 0,
    precio_unitario: float = 0.0,
) -> int:
    return _ejecutar(
        """
        INSERT INTO inventario (codigo, nombre, almacen_id, stock, precio_unitario)
        VALUES (?, ?, ?, ?, ?)
        """,
        (codigo.strip(), nombre.strip(), almacen_id, stock, precio_unitario),
    )


def ajustar_stock(item_id: int, delta: int) -> None:
    """Suma (o resta) unidades al stock. Lanza ValueError si el resultado sería negativo."""
    with conexion() as conn:
        fila = conn.execute(
            "SELECT stock FROM inventario WHERE id = ?", (item_id,)
        ).fetchone()
        if fila is None:
            raise ValueError("Ítem de inventario no encontrado.")
        nuevo = fila["stock"] + delta
        if nuevo < 0:
            raise ValueError("El stock no puede ser negativo.")
        conn.execute(
            "UPDATE inventario SET stock = ? WHERE id = ?", (nuevo, item_id)
        )


# ---------------------------------------------------------------------------
# Activos fijos
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
        (
            codigo.strip(),
            nombre.strip(),
            num_serie.strip(),
            responsable.strip(),
            estado,
        ),
    )


# ---------------------------------------------------------------------------
# Compras
# ---------------------------------------------------------------------------

def listar_compras() -> list[sqlite3.Row]:
    return _consultar("SELECT * FROM compras ORDER BY id DESC")


def crear_compra(
    proveedor: str,
    item_descripcion: str,
    cantidad: int,
    tipo_item: str,
    precio_unitario: float = 0.0,
) -> int:
    if tipo_item not in ("consumible", "activo_fijo"):
        raise ValueError("tipo_item debe ser 'consumible' o 'activo_fijo'.")
    if precio_unitario < 0:
        raise ValueError("El precio unitario no puede ser negativo.")
    return _ejecutar(
        """
        INSERT INTO compras
            (proveedor, item_descripcion, cantidad, precio_unitario, tipo_item, estado)
        VALUES (?, ?, ?, ?, ?, 'pendiente')
        """,
        (
            proveedor.strip(),
            item_descripcion.strip(),
            cantidad,
            precio_unitario,
            tipo_item,
        ),
    )


def marcar_compra_recibida(compra_id: int) -> None:
    """
    Marca la orden como 'recibido' y actualiza inventario o activos según tipo_item.
    - consumible  → incrementa / crea stock en el almacén principal
    - activo_fijo → registra N activos (uno por unidad) con código generado
    """
    with conexion() as conn:
        compra = conn.execute(
            "SELECT * FROM compras WHERE id = ?", (compra_id,)
        ).fetchone()
        if compra is None:
            raise ValueError("Orden de compra no encontrada.")
        if compra["estado"] != "pendiente":
            raise ValueError("Solo se pueden recibir órdenes pendientes.")

        tipo = compra["tipo_item"]
        desc = compra["item_descripcion"]
        cantidad = compra["cantidad"]
        precio = float(compra["precio_unitario"] or 0)

        if tipo == "consumible":
            almacen = conn.execute(
                "SELECT id FROM almacenes ORDER BY id LIMIT 1"
            ).fetchone()
            if almacen is None:
                raise ValueError("No hay almacenes configurados.")

            codigo = f"INV-{compra_id:04d}"
            existente = conn.execute(
                "SELECT id FROM inventario WHERE codigo = ?", (codigo,)
            ).fetchone()
            if existente:
                conn.execute(
                    """
                    UPDATE inventario
                    SET stock = stock + ?, precio_unitario = ?
                    WHERE id = ?
                    """,
                    (cantidad, precio, existente["id"]),
                )
            else:
                por_nombre = conn.execute(
                    """
                    SELECT id FROM inventario
                    WHERE lower(nombre) = lower(?) AND almacen_id = ?
                    """,
                    (desc, almacen["id"]),
                ).fetchone()
                if por_nombre:
                    conn.execute(
                        """
                        UPDATE inventario
                        SET stock = stock + ?, precio_unitario = ?
                        WHERE id = ?
                        """,
                        (cantidad, precio, por_nombre["id"]),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO inventario
                            (codigo, nombre, almacen_id, stock, precio_unitario)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (codigo, desc, almacen["id"], cantidad, precio),
                    )

        elif tipo == "activo_fijo":
            for i in range(1, cantidad + 1):
                codigo = f"AF-{compra_id:04d}-{i:03d}"
                conn.execute(
                    """
                    INSERT INTO activos_fijos
                        (codigo, nombre, num_serie, responsable, estado)
                    VALUES (?, ?, '', 'Pendiente asignación', 'activo')
                    """,
                    (codigo, desc),
                )
        else:
            raise ValueError(f"tipo_item desconocido: {tipo}")

        conn.execute(
            "UPDATE compras SET estado = 'recibido' WHERE id = ?",
            (compra_id,),
        )


# ---------------------------------------------------------------------------
# Resumen / dashboard
# ---------------------------------------------------------------------------

def resumen_dashboard() -> dict[str, int]:
    """Contadores para el panel de inicio."""
    with conexion() as conn:
        return {
            "almacenes": conn.execute("SELECT COUNT(*) FROM almacenes").fetchone()[0],
            "inventario": conn.execute("SELECT COUNT(*) FROM inventario").fetchone()[0],
            "stock_bajo": conn.execute(
                "SELECT COUNT(*) FROM inventario WHERE stock <= 5"
            ).fetchone()[0],
            "activos": conn.execute("SELECT COUNT(*) FROM activos_fijos").fetchone()[0],
            "activos_mantenimiento": conn.execute(
                "SELECT COUNT(*) FROM activos_fijos WHERE estado = 'en_mantenimiento'"
            ).fetchone()[0],
            "compras_pendientes": conn.execute(
                "SELECT COUNT(*) FROM compras WHERE estado = 'pendiente'"
            ).fetchone()[0],
            "compras_total": conn.execute("SELECT COUNT(*) FROM compras").fetchone()[0],
        }


if __name__ == "__main__":
    inicializar_db()
    print(f"Base de datos lista en: {DB_PATH}")
