-- AVISO (2026): borrador histórico. Nombres de tablas no coinciden con Django
-- (p. ej. item vs inventario_item). Use schema_from_django_migrations.sql +
-- docs/sql/00_bootstrap_core_tablas_postgresql.sql o pg_dump tras migrate.

-- Establece el esquema por defecto para esta pestaña
SET search_path TO public;

-- (Opcional) Si el esquema public no existiera (raro), lo crea
CREATE SCHEMA IF NOT EXISTS public;

-- Tipos enumerados
CREATE TYPE tipo_documento_venta AS ENUM (
    'FACTURA', 'BOLETA', 'NOTA_VENTA', 'RESUMEN_BOLETAS', 'GUIA_REMISION', 'NOTA_CREDITO_CLIENTE'
);

CREATE TYPE tipo_documento_compra AS ENUM (
    'FACTURA_COMPRA', 'NOTA_CREDITO_PROVEEDOR'
);

CREATE TYPE estado_documento AS ENUM ('BORRADOR', 'EMITIDO', 'ANULADO', 'PAGADO_PARCIAL', 'PAGADO');
CREATE TYPE tipo_movimiento_stock AS ENUM ('INGRESO', 'SALIDA', 'AJUSTE', 'TRANSFERENCIA');

-- ========== Administración / seguridad ==========
CREATE TABLE empresa (
    id                  SERIAL PRIMARY KEY,
    razon_social        VARCHAR(255) NOT NULL,
    ruc                 VARCHAR(20),
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    registro_aprobado   BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON COLUMN empresa.registro_aprobado IS 'FALSE = alta web pendiente de aprobación del operador de plataforma.';
COMMENT ON COLUMN empresa.razon_social IS 'Nombre del contribuyente en el sistema: PJ (RUC 20…) = razón social; PN (otro prefijo) = nombre en padrón o nombre completo del titular. perfil_usuario guarda al usuario administrador.';

CREATE TABLE sucursal (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    nombre      VARCHAR(120) NOT NULL,
    direccion   TEXT,
    activo      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE usuario (
    id                SERIAL PRIMARY KEY,
    empresa_id        INTEGER NOT NULL REFERENCES empresa(id),

    ruc               CHAR(11) UNIQUE,
    apellido_paterno  VARCHAR(50) NOT NULL,
    apellido_materno  VARCHAR(50) NOT NULL,
    nombre            VARCHAR(100) NOT NULL,

    email             VARCHAR(255) NOT NULL UNIQUE,
    password_hash     VARCHAR(255) NOT NULL,

    activo            BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_ruc_length CHECK (char_length(ruc) = 11)
);

CREATE TABLE rol (
    id     SERIAL PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL
);

CREATE TABLE usuario_rol (
    usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    rol_id     INTEGER NOT NULL REFERENCES rol(id) ON DELETE CASCADE,
    PRIMARY KEY (usuario_id, rol_id)
);

DO $perfil_usuario_django$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'auth_user'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'perfil_usuario'
    ) THEN
        CREATE TABLE perfil_usuario (
            id                   BIGSERIAL PRIMARY KEY,
            user_id              BIGINT NOT NULL UNIQUE REFERENCES auth_user(id) ON DELETE CASCADE,
            empresa_id           INTEGER NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
            sucursal_default_id  INTEGER REFERENCES sucursal(id) ON DELETE SET NULL,
            nombres              VARCHAR(120) NOT NULL DEFAULT '',
            apellido_paterno     VARCHAR(80) NOT NULL DEFAULT '',
            apellido_materno     VARCHAR(80) NOT NULL DEFAULT '',
            creado_en            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            actualizado_en       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    END IF;
END
$perfil_usuario_django$;

-- ========== Maestros: cliente / proveedor ==========
CREATE TABLE cliente (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    razon_social VARCHAR(255),
    documento   VARCHAR(20),
    email       VARCHAR(255),
    telefono    VARCHAR(40),
    activo      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE proveedor (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    razon_social VARCHAR(255) NOT NULL,
    documento   VARCHAR(20),
    activo      BOOLEAN NOT NULL DEFAULT TRUE
);

-- ========== Inventario ==========
CREATE TABLE categoria (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    nombre      VARCHAR(120) NOT NULL,
    padre_id    INTEGER REFERENCES categoria(id),
    activo      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE atributo (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    nombre      VARCHAR(80) NOT NULL
);

CREATE TABLE item (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    codigo      VARCHAR(50),
    nombre      VARCHAR(255) NOT NULL,
    categoria_id INTEGER REFERENCES categoria(id),
    unidad_medida VARCHAR(20) DEFAULT 'UND',
    activo      BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (empresa_id, codigo)
);

CREATE TABLE item_atributo_valor (
    item_id     INTEGER NOT NULL REFERENCES item(id) ON DELETE CASCADE,
    atributo_id INTEGER NOT NULL REFERENCES atributo(id),
    valor       VARCHAR(255) NOT NULL,
    PRIMARY KEY (item_id, atributo_id)
);

CREATE TABLE almacen (
    id          SERIAL PRIMARY KEY,
    sucursal_id INTEGER NOT NULL REFERENCES sucursal(id),
    nombre      VARCHAR(120) NOT NULL
);

CREATE TABLE stock (
    item_id     INTEGER NOT NULL REFERENCES item(id) ON DELETE CASCADE,
    almacen_id  INTEGER NOT NULL REFERENCES almacen(id) ON DELETE CASCADE,
    cantidad    NUMERIC(18,4) NOT NULL DEFAULT 0,
    PRIMARY KEY (item_id, almacen_id)
);

CREATE TABLE movimiento_stock (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    almacen_id  INTEGER NOT NULL REFERENCES almacen(id),
    tipo        tipo_movimiento_stock NOT NULL,
    referencia_tipo VARCHAR(50),
    referencia_id   INTEGER,
    fecha       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    usuario_id  INTEGER REFERENCES usuario(id)
);

CREATE TABLE movimiento_stock_linea (
    id                SERIAL PRIMARY KEY,
    movimiento_id     INTEGER NOT NULL REFERENCES movimiento_stock(id) ON DELETE CASCADE,
    item_id           INTEGER NOT NULL REFERENCES item(id),
    cantidad          NUMERIC(18,4) NOT NULL
);

CREATE TABLE lista_precio (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    nombre      VARCHAR(120) NOT NULL
);

CREATE TABLE lista_precio_item (
    lista_id    INTEGER NOT NULL REFERENCES lista_precio(id) ON DELETE CASCADE,
    item_id     INTEGER NOT NULL REFERENCES item(id) ON DELETE CASCADE,
    precio      NUMERIC(18,4) NOT NULL,
    PRIMARY KEY (lista_id, item_id)
);

-- ========== Ventas ==========
CREATE TABLE cotizacion (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    cliente_id  INTEGER REFERENCES cliente(id),
    numero      VARCHAR(30),
    fecha       DATE NOT NULL DEFAULT CURRENT_DATE,
    estado      estado_documento NOT NULL DEFAULT 'BORRADOR',
    total       NUMERIC(18,2) NOT NULL DEFAULT 0,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE cotizacion_linea (
    id            SERIAL PRIMARY KEY,
    cotizacion_id INTEGER NOT NULL REFERENCES cotizacion(id) ON DELETE CASCADE,
    item_id       INTEGER NOT NULL REFERENCES item(id),
    cantidad      NUMERIC(18,4) NOT NULL,
    precio_unit   NUMERIC(18,4) NOT NULL,
    subtotal      NUMERIC(18,2) NOT NULL
);

CREATE TABLE documento_venta (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    sucursal_id INTEGER REFERENCES sucursal(id),
    tipo        tipo_documento_venta NOT NULL,
    serie       VARCHAR(10),
    numero      VARCHAR(20),
    cliente_id  INTEGER REFERENCES cliente(id),
    fecha_emision DATE NOT NULL,
    estado      estado_documento NOT NULL DEFAULT 'BORRADOR',
    subtotal    NUMERIC(18,2) DEFAULT 0,
    igv         NUMERIC(18,2) DEFAULT 0,
    total       NUMERIC(18,2) DEFAULT 0,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (empresa_id, tipo, serie, numero)
);

CREATE TABLE documento_venta_linea (
    id                  SERIAL PRIMARY KEY,
    documento_venta_id  INTEGER NOT NULL REFERENCES documento_venta(id) ON DELETE CASCADE,
    item_id             INTEGER NOT NULL REFERENCES item(id),
    cantidad            NUMERIC(18,4) NOT NULL,
    precio_unit         NUMERIC(18,4) NOT NULL,
    subtotal            NUMERIC(18,2) NOT NULL
);

CREATE TABLE pedido (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    cliente_id  INTEGER REFERENCES cliente(id),
    origen      VARCHAR(30) DEFAULT 'MANUAL',
    estado      estado_documento NOT NULL DEFAULT 'BORRADOR',
    fecha       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE pedido_linea (
    id          SERIAL PRIMARY KEY,
    pedido_id   INTEGER NOT NULL REFERENCES pedido(id) ON DELETE CASCADE,
    item_id     INTEGER NOT NULL REFERENCES item(id),
    cantidad    NUMERIC(18,4) NOT NULL,
    precio_unit NUMERIC(18,4)
);

-- ========== Compras ==========
CREATE TABLE orden_compra (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    proveedor_id INTEGER NOT NULL REFERENCES proveedor(id),
    numero      VARCHAR(30),
    fecha       DATE NOT NULL,
    estado      estado_documento NOT NULL DEFAULT 'BORRADOR',
    total       NUMERIC(18,2) DEFAULT 0
);

CREATE TABLE orden_compra_linea (
    id              SERIAL PRIMARY KEY,
    orden_compra_id INTEGER NOT NULL REFERENCES orden_compra(id) ON DELETE CASCADE,
    item_id         INTEGER NOT NULL REFERENCES item(id),
    cantidad        NUMERIC(18,4) NOT NULL,
    precio_unit     NUMERIC(18,4) NOT NULL
);

CREATE TABLE documento_compra (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    tipo        tipo_documento_compra NOT NULL,
    proveedor_id INTEGER NOT NULL REFERENCES proveedor(id),
    serie       VARCHAR(10),
    numero      VARCHAR(20),
    fecha       DATE NOT NULL,
    estado      estado_documento NOT NULL DEFAULT 'BORRADOR',
    total       NUMERIC(18,2) DEFAULT 0,
    es_electronica BOOLEAN NOT NULL DEFAULT FALSE,
    hash_xml    VARCHAR(64)
);

CREATE TABLE documento_compra_linea (
    id                  SERIAL PRIMARY KEY,
    documento_compra_id INTEGER NOT NULL REFERENCES documento_compra(id) ON DELETE CASCADE,
    item_id             INTEGER NOT NULL REFERENCES item(id),
    cantidad            NUMERIC(18,4) NOT NULL,
    precio_unit         NUMERIC(18,4) NOT NULL,
    subtotal            NUMERIC(18,2) NOT NULL
);

CREATE TABLE gasto_recurrente (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    concepto    VARCHAR(255) NOT NULL,
    monto       NUMERIC(18,2) NOT NULL,
    periodicidad VARCHAR(20) NOT NULL,
    dia_ejecucion SMALLINT,
    activo      BOOLEAN NOT NULL DEFAULT TRUE,
    proxima_fecha DATE
);

-- ========== Tesorería ==========
CREATE TABLE cuenta_bancaria (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    banco       VARCHAR(100),
    numero      VARCHAR(40),
    moneda      VARCHAR(3) NOT NULL DEFAULT 'PEN',
    saldo       NUMERIC(18,2) DEFAULT 0
);

CREATE TABLE caja (
    id          SERIAL PRIMARY KEY,
    sucursal_id INTEGER NOT NULL REFERENCES sucursal(id),
    nombre      VARCHAR(80) NOT NULL
);

CREATE TABLE cobranza (
    id                  SERIAL PRIMARY KEY,
    empresa_id          INTEGER NOT NULL REFERENCES empresa(id),
    documento_venta_id  INTEGER REFERENCES documento_venta(id),
    monto_pendiente     NUMERIC(18,2) NOT NULL,
    monto_pagado        NUMERIC(18,2) NOT NULL DEFAULT 0,
    fecha_vencimiento   DATE,
    estado              VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE'
);

CREATE TABLE pago_recibido (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    cobranza_id INTEGER REFERENCES cobranza(id),
    monto       NUMERIC(18,2) NOT NULL,
    fecha       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metodo      VARCHAR(30) NOT NULL,
    cuenta_bancaria_id INTEGER REFERENCES cuenta_bancaria(id),
    caja_id     INTEGER REFERENCES caja(id),
    usuario_id  INTEGER REFERENCES usuario(id)
);

CREATE TABLE cronograma_pago (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    proveedor_id INTEGER REFERENCES proveedor(id),
    descripcion TEXT,
    monto       NUMERIC(18,2) NOT NULL,
    fecha_vencimiento DATE NOT NULL,
    estado      VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE'
);

CREATE TABLE conciliacion_bancaria (
    id          SERIAL PRIMARY KEY,
    cuenta_bancaria_id INTEGER NOT NULL REFERENCES cuenta_bancaria(id),
    periodo     VARCHAR(7) NOT NULL,
    saldo_libro NUMERIC(18,2),
    saldo_banco NUMERIC(18,2),
    cerrada     BOOLEAN NOT NULL DEFAULT FALSE
);


-- ========== Contabilidad ==========
CREATE TABLE plan_cuenta (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    codigo      VARCHAR(20) NOT NULL,
    nombre      VARCHAR(255) NOT NULL,
    tipo        VARCHAR(30) NOT NULL,
    activo      BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (empresa_id, codigo)
);
CREATE TABLE asiento_contable (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    fecha       DATE NOT NULL,
    glosa       TEXT,
    origen_tipo VARCHAR(50),
    origen_id   INTEGER,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE asiento_linea (
    id              SERIAL PRIMARY KEY,
    asiento_id      INTEGER NOT NULL REFERENCES asiento_contable(id) ON DELETE CASCADE,
    cuenta_id       INTEGER NOT NULL REFERENCES plan_cuenta(id),
    debe            NUMERIC(18,2) NOT NULL DEFAULT 0,
    haber           NUMERIC(18,2) NOT NULL DEFAULT 0
);

-- ========== Tareas / configuración ==========
CREATE TABLE tarea (
    id          SERIAL PRIMARY KEY,
    usuario_id  INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    titulo      VARCHAR(255) NOT NULL,
    descripcion TEXT,
    completada  BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_limite DATE
);

CREATE TABLE configuracion_sistema (
    clave       VARCHAR(100) NOT NULL,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    valor       JSONB NOT NULL,
    PRIMARY KEY (empresa_id, clave)
);

-- ========== Marca (catálogo por empresa) ==========

CREATE TABLE marca (
    id           SERIAL PRIMARY KEY,
    empresa_id   INTEGER NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    nombre       VARCHAR(120) NOT NULL,
    activo       BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_marca_nombre_por_empresa UNIQUE (empresa_id, nombre)
);

COMMENT ON TABLE marca IS 'Catálogo de marcas por empresa; opcional en item (marca_id NULL).';
COMMENT ON COLUMN marca.nombre IS 'Nombre comercial de la marca (único por empresa).';
COMMENT ON COLUMN marca.activo IS 'FALSE: no se sugiere en altas nuevas; los ítems históricos siguen enlazados.';

CREATE INDEX idx_marca_empresa_activo ON marca (empresa_id, activo);

ALTER TABLE item
    ADD COLUMN marca_id INTEGER REFERENCES marca(id) ON DELETE SET NULL;

COMMENT ON COLUMN item.marca_id IS 'Opcional. NULL = sin marca (típico en servicios).';

CREATE INDEX idx_item_marca ON item (marca_id) WHERE marca_id IS NOT NULL;

