from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Empresa(models.Model):
    id = models.BigAutoField(primary_key=True)
    razon_social = models.CharField(
        max_length=255,
        help_text=(
            "Nombre mostrado del contribuyente: persona jurídica = razón social (RUC suele iniciar en 20); "
            "persona natural = nombre completo en padrón o el armado con el titular del registro."
        ),
    )
    ruc = models.CharField(max_length=11, blank=True, db_index=True)
    # Persona natural (RUC distinto de 20…): titular del RUC en columnas propias. En PJ quedan vacíos.
    apellido_paterno = models.CharField(max_length=80, blank=True, default="")
    apellido_materno = models.CharField(max_length=80, blank=True, default="")
    nombres = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Nombres de pila del contribuyente (persona natural).",
    )
    telefono_contacto = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="Teléfono para seguimiento comercial del registro / contacto principal.",
    )
    activo = models.BooleanField(default=True)
    registro_aprobado = models.BooleanField(
        default=True,
        help_text="False = registro web pendiente de aprobación por superusuario.",
    )
    fecha_registro_aprobado = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Momento en que un superusuario aprobó el registro web (si aplica).",
    )
    logo_comprobante = models.FileField(
        upload_to="logos_comprobante/%Y/%m/",
        blank=True,
        null=True,
        help_text="Logo en comprobantes (recomendado máx. 430×150 px; PNG o JPG).",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "empresa"
        constraints = [
            models.UniqueConstraint(
                fields=["ruc"],
                name="uniq_empresa_ruc_no_vacio",
                condition=~models.Q(ruc=""),
            ),
        ]

    def __str__(self):
        return self.razon_social


class Sucursal(models.Model):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="sucursales"
    )
    nombre = models.CharField(max_length=120)
    direccion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "sucursal"

    def __str__(self):
        return f"{self.nombre} ({self.empresa})"


class Cliente(models.Model):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="clientes"
    )
    razon_social = models.CharField(max_length=255, blank=True)
    documento = models.CharField(max_length=20, blank=True, db_index=True)
    email = models.EmailField(blank=True)
    direccion = models.TextField(blank=True)
    telefono = models.CharField(max_length=40, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "cliente"
        ordering = ["razon_social"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "documento"],
                name="uniq_cliente_documento_por_empresa",
                condition=~models.Q(documento=""),
            ),
        ]

    def __str__(self):
        return self.razon_social or self.documento or str(self.id)


class Proveedor(models.Model):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="proveedores"
    )
    razon_social = models.CharField(max_length=255)
    documento = models.CharField(max_length=20, blank=True, db_index=True)
    email = models.EmailField(blank=True)
    direccion = models.TextField(blank=True)
    telefono = models.CharField(max_length=40, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "proveedor"
        ordering = ["razon_social"]

    def __str__(self):
        return self.razon_social


class Vendedor(models.Model):
    """Vendedor por empresa (maestro para comprobantes y reportes)."""

    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="vendedores"
    )
    dni = models.CharField(max_length=20, blank=True, db_index=True)
    apellido_paterno = models.CharField(max_length=80, blank=True)
    apellido_materno = models.CharField(max_length=80, blank=True)
    nombres = models.CharField(max_length=120, blank=True)
    sucursal = models.ForeignKey(
        "Sucursal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendedores",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "vendedor"
        ordering = ["apellido_paterno", "apellido_materno", "nombres"]

    def nombre_completo(self) -> str:
        parts = [self.apellido_paterno, self.apellido_materno, self.nombres]
        s = " ".join(p.strip() for p in parts if p and str(p).strip())
        return s or (self.dni or "").strip() or str(self.pk)

    def __str__(self):
        return self.nombre_completo()


class PerfilUsuario(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil_gestor",
    )
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="usuarios_perfil"
    )
    sucursal_default = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios_default",
    )
    nombres = models.CharField(max_length=120, blank=True)
    apellido_paterno = models.CharField(max_length=80, blank=True)
    apellido_materno = models.CharField(max_length=80, blank=True)

    class Meta:
        db_table = "perfil_usuario"

    def __str__(self):
        return f"{self.user.get_username()} @ {self.empresa}"


class Usuario(models.Model):
    """
    Tabla de negocio `usuario` (PostgreSQL / visibilidad en DBeaver).
    El login sigue usando Django `User`; `password_hash` replica el hash de `User.password`.
    """

    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="usuarios_legacy",
        db_column="empresa_id",
    )
    ruc = models.CharField(max_length=11, unique=True, db_index=True)
    apellido_paterno = models.CharField(max_length=50)
    apellido_materno = models.CharField(max_length=50)
    nombre = models.CharField(max_length=100)
    email = models.EmailField(max_length=255, unique=True)
    password_hash = models.CharField(max_length=255)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "usuario"

    def __str__(self):
        return self.email


class NotificacionUsuario(TimeStampedModel):
    """Aviso in-app por usuario (superusuario: nuevas empresas; cliente: bienvenida / rechazo)."""

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificaciones_gestor",
    )
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField()
    leida = models.BooleanField(default=False)
    categoria = models.CharField(max_length=40, blank=True, db_index=True)

    class Meta:
        db_table = "notificacion_usuario"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.titulo} → {self.user_id}"
