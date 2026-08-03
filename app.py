"""
Servidor web Flask — ERP Local para Gestión de Almacén, Kárdex, Compras y Facturación POS.
Sistema de autenticación y control de acceso basado en roles (Admin/Empleado).
"""

from __future__ import annotations

from functools import wraps
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    abort,
    make_response,
    g,
)

import base_datos as db

app = Flask(__name__)
app.secret_key = "erp_almacen_secret_key_local_desktop_2026"


# ---------------------------------------------------------------------------
# Inyección Global de Contexto (current_user para Jinja2)
# ---------------------------------------------------------------------------

@app.context_processor
def inject_user():
    user_id = session.get("user_id")
    if user_id:
        user = db.obtener_usuario_por_id(user_id)
        if user:
            return {"current_user": user}
    return {"current_user": None}


# ---------------------------------------------------------------------------
# Decoradores de Autenticación y Autorización (RBAC)
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id or not db.obtener_usuario_por_id(user_id):
            if request.headers.get("HX-Request"):
                response = make_response(render_template("login.html", error="Sesión expirada. Por favor ingresa de nuevo."))
                response.headers["HX-Redirect"] = url_for("login")
                return response
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get("user_id")
        user = db.obtener_usuario_por_id(user_id) if user_id else None
        if not user or user.get("rol") != "admin":
            if request.headers.get("HX-Request"):
                return "<div class='badge badge-danger' style='padding: 1rem; margin: 1rem 0;'>⚠️ Acceso Restringido: Esta acción requiere permisos de Administrador.</div>", 403
            abort(403, description="Acceso denegado. Se requieren permisos de Administrador.")
        return f(*args, **kwargs)
    return decorated_function


EXEMPT_LICENSE_ENDPOINTS = {
    "login",
    "logout",
    "pantalla_bloqueado",
    "activar_licencia",
    "static",
}


@app.before_request
def verificar_licencia_global():
    if request.endpoint in EXEMPT_LICENSE_ENDPOINTS or (request.endpoint and request.endpoint.startswith("static")):
        return None

    lic_status = db.obtener_estado_licencia()
    g.licencia_estado = lic_status

    if lic_status["estado"] == "VENCIDA" or lic_status["reloj_alterado"]:
        if request.headers.get("HX-Request"):
            response = make_response()
            response.headers["HX-Redirect"] = url_for("pantalla_bloqueado")
            return response
        return redirect(url_for("pantalla_bloqueado"))


# ---------------------------------------------------------------------------
# Autenticación: Login / Logout
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user_id") and db.obtener_usuario_por_id(session["user_id"]):
            return redirect(url_for("index"))
        return render_template("login.html")

    usuario_input = request.form.get("usuario", "")
    password_input = request.form.get("password", "")

    user = db.autenticar_usuario(usuario_input, password_input)
    if user:
        session["user_id"] = user["id"]
        session["user_name"] = user["nombre"]
        session["user_role"] = user["rol"]
        return redirect(url_for("index"))

    return render_template("login.html", error="Usuario o contraseña incorrectos.")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Páginas Principales / Navegación HTMX
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/vistas/inicio")
@login_required
def vista_inicio():
    return render_template(
        "partials/inicio.html",
        resumen=db.resumen_dashboard(),
    )


@app.route("/vistas/inventario")
@login_required
def vista_inventario():
    almacen_id_param = request.args.get("almacen_id")
    almacen_id = int(almacen_id_param) if almacen_id_param and almacen_id_param.isdigit() else None
    return render_template(
        "partials/tabla_inventario.html",
        productos=db.listar_productos(almacen_id),
        almacenes=db.listar_almacenes(),
        almacen_seleccionado=almacen_id,
    )


@app.route("/vistas/kardex")
@login_required
def vista_kardex():
    producto_id = request.args.get("producto_id", type=int)
    almacen_id = request.args.get("almacen_id", type=int)
    return render_template(
        "partials/kardex.html",
        kardex_list=db.listar_kardex(producto_id=producto_id, almacen_id=almacen_id, limit=100),
        productos=db.listar_productos(),
        almacenes=db.listar_almacenes(),
        producto_filtro=producto_id,
        almacen_filtro=almacen_id,
    )


@app.route("/vistas/compras")
@login_required
def vista_compras():
    return render_template(
        "partials/tabla_compras.html",
        compras=db.listar_compras(),
        productos=db.listar_productos(),
        almacenes=db.listar_almacenes(),
    )


@app.route("/vistas/compras/<int:compra_id>/detalle")
@login_required
def vista_detalle_compra(compra_id: int):
    compra = db.obtener_compra_con_detalles(compra_id)
    if not compra:
        abort(404, description="Orden de compra no encontrada.")
    return render_template("partials/detalle_compra.html", compra=compra)


@app.route("/vistas/facturacion")
@login_required
def vista_facturacion():
    return render_template(
        "partials/facturacion.html",
        productos=db.listar_productos(),
        almacenes=db.listar_almacenes(),
        ventas=db.listar_ventas(),
    )


@app.route("/vistas/almacenes")
@login_required
def vista_almacenes():
    return render_template(
        "partials/tabla_almacenes.html",
        almacenes=db.listar_almacenes(),
    )


@app.route("/vistas/activos")
@login_required
def vista_activos():
    return render_template(
        "partials/tabla_activos.html",
        activos=db.listar_activos(),
    )


@app.route("/vistas/usuarios")
@login_required
@admin_required
def vista_usuarios():
    return render_template(
        "partials/tabla_usuarios.html",
        usuarios=db.listar_usuarios(),
    )


@app.route("/vistas/licencia")
@login_required
def vista_licencia():
    return render_template(
        "partials/licencia.html",
        licencia=db.obtener_estado_licencia(),
    )


@app.route("/licencia/bloqueado")
def pantalla_bloqueado():
    lic_status = db.obtener_estado_licencia()
    return render_template("bloqueado.html", licencia=lic_status)


@app.post("/licencia/activar")
def activar_licencia():
    llave = request.form.get("llave_activacion", "")
    try:
        nueva_lic = db.activar_licencia_con_llave(llave)
        if request.headers.get("HX-Request"):
            response = make_response(render_template("partials/licencia.html", licencia=nueva_lic, exito="¡Licencia activada con éxito! Suscripción renovada."))
            response.headers["HX-Redirect"] = "/"
            return response
        return redirect(url_for("index"))
    except Exception as exc:
        error_msg = str(exc)
        lic_status = db.obtener_estado_licencia()
        if request.headers.get("HX-Request"):
            return render_template(
                "partials/licencia.html",
                licencia=lic_status,
                error=error_msg,
            )
        return render_template(
            "bloqueado.html",
            licencia=lic_status,
            error=error_msg,
        )


# ---------------------------------------------------------------------------
# Endpoints de Productos e Inventario
# ---------------------------------------------------------------------------

@app.post("/productos")
@login_required
def crear_producto():
    try:
        codigo = request.form["codigo"]
        nombre = request.form["nombre"]
        precio_venta = float(request.form.get("precio_venta", 0) or 0)
        stock_minimo = int(request.form.get("stock_minimo", 5) or 5)

        db.crear_producto(
            codigo=codigo,
            nombre=nombre,
            precio_venta=precio_venta,
            stock_minimo=stock_minimo,
        )
    except Exception as exc:
        abort(400, description=str(exc))
    return vista_inventario()


@app.post("/inventario/ajustar")
@login_required
@admin_required
def ajustar_inventario():
    try:
        producto_id = int(request.form["producto_id"])
        almacen_id = int(request.form["almacen_id"])
        tipo = request.form.get("tipo_movimiento", "AJUSTE").upper()
        cantidad = int(request.form["cantidad"])
        costo = float(request.form.get("costo_unitario", 0) or 0)
        referencia = request.form.get("referencia", "Ajuste manual")

        cantidad_delta = cantidad if tipo == "ENTRADA" else (-cantidad if tipo == "SALIDA" else cantidad)

        db.ajustar_stock_manual(
            producto_id=producto_id,
            almacen_id=almacen_id,
            cantidad_delta=cantidad_delta,
            tipo_movimiento=tipo,
            costo_unitario=costo,
            referencia=referencia,
        )
    except Exception as exc:
        abort(400, description=str(exc))
    return vista_inventario()


# ---------------------------------------------------------------------------
# Endpoints de Compras
# ---------------------------------------------------------------------------

@app.post("/compras")
@login_required
def crear_compra():
    try:
        proveedor = request.form["proveedor"]
        almacen_id = int(request.form["almacen_id"])
        
        prod_ids = request.form.getlist("producto_id[]")
        cantidades = request.form.getlist("cantidad[]")
        costos = request.form.getlist("costo_unitario[]")

        items = []
        for p_id, cant, costo in zip(prod_ids, cantidades, costos):
            if p_id and cant:
                items.append({
                    "producto_id": int(p_id),
                    "cantidad": int(cant),
                    "costo_unitario": float(costo or 0),
                })

        db.crear_orden_compra(
            proveedor=proveedor,
            almacen_id=almacen_id,
            items=items,
        )
    except Exception as exc:
        abort(400, description=str(exc))
    return vista_compras()


@app.post("/compras/<int:compra_id>/estado")
@login_required
@admin_required
def cambiar_estado_compra(compra_id: int):
    try:
        nuevo_estado = request.form["estado"]
        db.cambiar_estado_compra(compra_id, nuevo_estado)
    except Exception as exc:
        abort(400, description=str(exc))
    return vista_compras()


# ---------------------------------------------------------------------------
# Endpoints de Facturación Local / POS
# ---------------------------------------------------------------------------

@app.post("/facturas/crear")
@login_required
def crear_factura_pos():
    try:
        almacen_id = int(request.form["almacen_id"])
        cliente_nombre = request.form.get("cliente_nombre", "Cliente General")
        cliente_nit = request.form.get("cliente_nit", "222222222222")
        cliente_email = request.form.get("cliente_email", "")
        metodo_pago = request.form.get("metodo_pago", "Efectivo")

        prod_ids = request.form.getlist("producto_id[]")
        cantidades = request.form.getlist("cantidad[]")
        precios = request.form.getlist("precio_unitario[]")

        items = []
        for p_id, cant, prec in zip(prod_ids, cantidades, precios):
            if p_id and cant:
                items.append({
                    "producto_id": int(p_id),
                    "cantidad": int(cant),
                    "precio_unitario": float(prec or 0),
                    "impuesto_porcentaje": 19.0,
                })

        usr_id = g.usuario_actual["id"] if hasattr(g, "usuario_actual") and g.usuario_actual else None

        db.procesar_venta_pos(
            almacen_id=almacen_id,
            cliente_nombre=cliente_nombre,
            cliente_nit=cliente_nit,
            cliente_email=cliente_email,
            items=items,
            metodo_pago=metodo_pago,
            usuario_id=usr_id,
        )
        
        return vista_facturacion()
    except Exception as exc:
        abort(400, description=str(exc))


@app.post("/facturas/<int:venta_id>/anular")
@login_required
@admin_required
def anular_factura_pos(venta_id: int):
    try:
        usr_id = g.usuario_actual["id"] if hasattr(g, "usuario_actual") and g.usuario_actual else None
        db.anular_factura(venta_id, usuario_id=usr_id)
        return vista_facturacion()
    except Exception as exc:
        abort(400, description=str(exc))


@app.route("/facturas/<int:venta_id>/ticket")
@login_required
def ver_ticket_factura(venta_id: int):
    venta = db.obtener_venta_con_detalles(venta_id)
    if not venta:
        abort(404, description="Factura no encontrada.")
    return render_template("ticket.html", venta=venta)


# ---------------------------------------------------------------------------
# Endpoints de Almacenes, Activos Fijos y Usuarios
# ---------------------------------------------------------------------------

@app.post("/almacenes")
@login_required
@admin_required
def crear_almacen():
    try:
        db.crear_almacen(
            nombre=request.form["nombre"],
            ubicacion=request.form.get("ubicacion", ""),
        )
    except Exception as exc:
        abort(400, description=str(exc))
    return vista_almacenes()


@app.post("/activos")
@login_required
@admin_required
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


@app.post("/usuarios")
@login_required
@admin_required
def crear_usuario():
    try:
        db.crear_usuario(
            nombre=request.form["nombre"],
            usuario=request.form["usuario"],
            password_plana=request.form["password"],
            rol=request.form.get("rol", "empleado"),
        )
    except Exception as exc:
        abort(400, description=str(exc))
    return vista_usuarios()


# ---------------------------------------------------------------------------
# Arranque del Servidor
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    db.inicializar_db()
    app.run(debug=True, port=5000)
