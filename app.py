"""
Servidor web Flask — Gestión de Almacén, Inventario, Activos y Compras.
HTMX maneja la navegación y mutaciones sin JavaScript propio.
"""

from __future__ import annotations

from flask import Flask, render_template, request, abort

import base_datos as db

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Páginas / navegación HTMX
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/vistas/inicio")
def vista_inicio():
    return render_template(
        "partials/inicio.html",
        resumen=db.resumen_dashboard(),
    )


@app.route("/vistas/activos")
def vista_activos():
    return render_template(
        "partials/tabla_activos.html",
        activos=db.listar_activos(),
    )


@app.route("/vistas/inventario")
def vista_inventario():
    return render_template(
        "partials/tabla_inventario.html",
        items=db.listar_inventario(),
        almacenes=db.listar_almacenes(),
    )


@app.route("/vistas/compras")
def vista_compras():
    return render_template(
        "partials/tabla_compras.html",
        compras=db.listar_compras(),
    )


@app.route("/vistas/almacenes")
def vista_almacenes():
    return render_template(
        "partials/tabla_almacenes.html",
        almacenes=db.listar_almacenes(),
    )


# ---------------------------------------------------------------------------
# Activos fijos
# ---------------------------------------------------------------------------

@app.post("/activos")
def crear_activo():
    try:
        db.crear_activo(
            codigo=request.form["codigo"],
            nombre=request.form["nombre"],
            num_serie=request.form.get("num_serie", ""),
            responsable=request.form.get("responsable", ""),
            estado=request.form.get("estado", "activo"),
        )
    except Exception as exc:
        abort(400, description=str(exc))
    return vista_activos()


# ---------------------------------------------------------------------------
# Inventario
# ---------------------------------------------------------------------------

@app.post("/inventario")
def crear_inventario():
    try:
        db.crear_item_inventario(
            codigo=request.form["codigo"],
            nombre=request.form["nombre"],
            almacen_id=int(request.form["almacen_id"]),
            stock=int(request.form.get("stock", 0)),
            precio_unitario=float(request.form.get("precio_unitario", 0) or 0),
        )
    except Exception as exc:
        abort(400, description=str(exc))
    return vista_inventario()


@app.post("/inventario/<int:item_id>/ajustar")
def ajustar_inventario(item_id: int):
    try:
        delta = int(request.form["delta"])
        db.ajustar_stock(item_id, delta)
    except ValueError as exc:
        abort(400, description=str(exc))
    except Exception as exc:
        abort(400, description=str(exc))
    return vista_inventario()


# ---------------------------------------------------------------------------
# Compras
# ---------------------------------------------------------------------------

@app.post("/compras")
def crear_compra():
    try:
        db.crear_compra(
            proveedor=request.form["proveedor"],
            item_descripcion=request.form["item_descripcion"],
            cantidad=int(request.form["cantidad"]),
            tipo_item=request.form["tipo_item"],
            precio_unitario=float(request.form.get("precio_unitario", 0) or 0),
        )
    except Exception as exc:
        abort(400, description=str(exc))
    return vista_compras()


@app.post("/compras/<int:compra_id>/recibir")
def recibir_compra(compra_id: int):
    """Marca la OC como recibida y actualiza inventario o activos fijos."""
    try:
        db.marcar_compra_recibida(compra_id)
    except ValueError as exc:
        abort(400, description=str(exc))
    return vista_compras()


# ---------------------------------------------------------------------------
# Almacenes
# ---------------------------------------------------------------------------

@app.post("/almacenes")
def crear_almacen():
    try:
        db.crear_almacen(
            nombre=request.form["nombre"],
            ubicacion=request.form.get("ubicacion", ""),
        )
    except Exception as exc:
        abort(400, description=str(exc))
    return vista_almacenes()


# ---------------------------------------------------------------------------
# Arranque
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    db.inicializar_db()
    app.run(debug=True, port=5000)
