<template>
  <div class="card">
    <h2>Punto de venta (POS)</h2>
    <p class="muted">
      Flujo operativo: creación rápida de <code>documento_venta</code> + líneas y emisión (descuenta
      <code>stock</code> y genera <code>cobranza</code>). Pantalla en construcción; usa la API
      <code>POST /api/v1/ventas/documentos/</code> y <code>.../emitir/</code>.
    </p>
  </div>
</template>

<style scoped>
.card {
  background: #fff;
  border-radius: 10px;
  padding: 1.25rem;
  max-width: 40rem;
  box-shadow: 0 1px 3px rgb(15 23 42 / 10%);
}
h2 {
  margin-top: 0;
}
.muted {
  color: #64748b;
  line-height: 1.5;
  font-size: 0.9rem;
}
code {
  background: #f1f5f9;
  padding: 0.1rem 0.3rem;
  border-radius: 4px;
  font-size: 0.8rem;
}
</style>
