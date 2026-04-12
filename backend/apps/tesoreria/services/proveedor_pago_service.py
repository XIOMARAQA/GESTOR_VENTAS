from decimal import Decimal

from django.db import transaction

from apps.tesoreria.models import (
    CronogramaPago,
    EstadoCronogramaPago,
    PagoRealizadoProveedor,
)


class ProveedorPagoService:
    @staticmethod
    @transaction.atomic
    def registrar_pago_cronograma(
        cronograma: CronogramaPago,
        monto,
        *,
        usuario=None,
        metodo: str | None = None,
    ) -> PagoRealizadoProveedor:
        if cronograma.estado != EstadoCronogramaPago.PENDIENTE:
            raise ValueError("La obligación no está pendiente.")
        if monto <= 0:
            raise ValueError("El monto del pago debe ser mayor que cero.")
        monto_dec = monto if isinstance(monto, Decimal) else Decimal(str(monto))
        if monto_dec != cronograma.monto:
            raise ValueError("El monto debe coincidir con el total de la obligación.")
        metodo_norm = (metodo or "REGISTRO_MANUAL").strip().upper() or "REGISTRO_MANUAL"
        if len(metodo_norm) > 30:
            metodo_norm = metodo_norm[:30]
        pago = PagoRealizadoProveedor.objects.create(
            empresa=cronograma.empresa,
            cronograma_pago=cronograma,
            monto=monto_dec,
            metodo=metodo_norm,
            usuario=usuario,
        )
        cronograma.estado = EstadoCronogramaPago.PAGADO
        cronograma.save(update_fields=["estado", "actualizado_en"])
        return pago

    @staticmethod
    @transaction.atomic
    def revertir_pago(pago: PagoRealizadoProveedor) -> None:
        cronograma = pago.cronograma_pago
        cronograma.estado = EstadoCronogramaPago.PENDIENTE
        cronograma.save(update_fields=["estado", "actualizado_en"])
        pago.delete()

    @staticmethod
    @transaction.atomic
    def revertir_obligacion_pagada(cronograma: CronogramaPago) -> None:
        """Desde Cuentas por pagar: elimina registro de pago si existe, o solo baja estado (datos legacy)."""
        if cronograma.estado != EstadoCronogramaPago.PAGADO:
            raise ValueError("Solo las obligaciones pagadas pueden volver a pendiente.")
        pago = (
            PagoRealizadoProveedor.objects.filter(cronograma_pago=cronograma)
            .order_by("-id")
            .first()
        )
        if pago:
            ProveedorPagoService.revertir_pago(pago)
        else:
            cronograma.estado = EstadoCronogramaPago.PENDIENTE
            cronograma.save(update_fields=["estado", "actualizado_en"])
