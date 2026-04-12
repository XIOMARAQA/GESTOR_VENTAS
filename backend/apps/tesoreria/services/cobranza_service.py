from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.tesoreria.models import Cobranza, EstadoCobranza, PagoRecibido
from apps.ventas.models import CondicionPagoDocumento, DocumentoVenta, EstadoDocumento


class CobranzaService:
    @staticmethod
    @transaction.atomic
    def crear_desde_documento(
        documento: DocumentoVenta,
        *,
        usuario=None,
    ) -> Cobranza | None:
        """
        Al emitir venta: cuenta por cobrar.
        - CONTADO: cobranza en PAGADO con monto_pagado = total (cobro implicito); registra PagoRecibido.
        - CREDITO: PENDIENTE, monto_pagado 0, vencimiento según documento.
        """
        if documento.estado != EstadoDocumento.EMITIDO:
            return None
        existe = Cobranza.objects.filter(documento_venta=documento).exists()
        if existe:
            return Cobranza.objects.get(documento_venta=documento)

        total = documento.total
        if documento.condicion_pago == CondicionPagoDocumento.CREDITO:
            cob = Cobranza.objects.create(
                empresa=documento.empresa,
                documento_venta=documento,
                monto_total=total,
                monto_pagado=Decimal("0"),
                fecha_vencimiento=documento.fecha_vencimiento,
                estado=EstadoCobranza.PENDIENTE,
            )
            return cob

        cob = Cobranza.objects.create(
            empresa=documento.empresa,
            documento_venta=documento,
            monto_total=total,
            monto_pagado=total,
            fecha_vencimiento=documento.fecha_emision,
            estado=EstadoCobranza.PAGADO,
        )
        PagoRecibido.objects.create(
            empresa=documento.empresa,
            cobranza=cob,
            monto=total,
            metodo="CONTADO",
            usuario=usuario,
        )
        return cob

    @staticmethod
    @transaction.atomic
    def registrar_pago(cobranza: Cobranza, monto, usuario=None, metodo: str | None = None) -> None:
        if monto <= 0:
            raise ValueError("El monto del pago debe ser mayor que cero.")
        pendiente = cobranza.monto_total - cobranza.monto_pagado
        if monto > pendiente:
            raise ValueError("El pago excede el saldo pendiente.")
        cobranza.monto_pagado += monto
        if cobranza.monto_pagado >= cobranza.monto_total:
            cobranza.estado = EstadoCobranza.PAGADO
        else:
            cobranza.estado = EstadoCobranza.PAGADO_PARCIAL
        cobranza.save(update_fields=["monto_pagado", "estado", "actualizado_en"])
        metodo_norm = (metodo or "REGISTRO_MANUAL").strip().upper() or "REGISTRO_MANUAL"
        if len(metodo_norm) > 30:
            metodo_norm = metodo_norm[:30]
        PagoRecibido.objects.create(
            empresa=cobranza.empresa,
            cobranza=cobranza,
            monto=monto,
            metodo=metodo_norm,
            usuario=usuario,
        )

    @staticmethod
    @transaction.atomic
    def revertir_pago(pago: PagoRecibido) -> None:
        """
        Elimina un pago recibido y descuenta su monto de la cobranza.
        Útil si se registró un cobro por error.
        """
        cob = pago.cobranza
        if cob is None:
            raise ValueError("Este pago no está vinculado a una cobranza; no se puede revertir desde aquí.")
        monto = pago.monto
        if cob.monto_pagado < monto:
            raise ValueError("Inconsistencia: el total cobrado es menor que el monto de este pago.")
        cob.monto_pagado -= monto
        if cob.monto_pagado < Decimal("0"):
            cob.monto_pagado = Decimal("0")

        if cob.monto_pagado <= 0:
            today = timezone.now().date()
            if cob.fecha_vencimiento and cob.fecha_vencimiento < today:
                cob.estado = EstadoCobranza.VENCIDO
            else:
                cob.estado = EstadoCobranza.PENDIENTE
        elif cob.monto_pagado < cob.monto_total:
            cob.estado = EstadoCobranza.PAGADO_PARCIAL
        else:
            cob.estado = EstadoCobranza.PAGADO

        cob.save(update_fields=["monto_pagado", "estado", "actualizado_en"])
        pago.delete()
