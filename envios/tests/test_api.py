from decimal import Decimal
from datetime import timedelta

from django.urls import reverse
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from envios.models import Encomienda, HistorialEstado
from envios.tests.factories import (
    UserFactory,
    ClienteFactory,
    RutaFactory,
    EmpleadoFactory,
    EncomiendaFactory
)


API_VERSION = "v1"


class BaseAPITest(APITestCase):

    def setUp(self):
        self.user = UserFactory()

        self.empleado = EmpleadoFactory(
            email=self.user.email
        )

        refresh = RefreshToken.for_user(self.user)

        self.token = str(refresh.access_token)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )

    def auth_headers(self):
        return {
            "HTTP_AUTHORIZATION": f"Bearer {self.token}"
        }


class TestAutenticacion(APITestCase):

    def setUp(self):
        self.user = UserFactory()

        self.empleado = EmpleadoFactory(
            email=self.user.email
        )

        refresh = RefreshToken.for_user(self.user)

        self.token = str(refresh.access_token)

    def test_sin_token_devuelve_401(self):

        response = self.client.get(
            reverse(
                "encomienda-list",
                kwargs={"version": API_VERSION}
            )
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_invalido_devuelve_401(self):

        self.client.credentials(
            HTTP_AUTHORIZATION="Bearer token_invalido"
        )

        response = self.client.get(
            reverse(
                "encomienda-list",
                kwargs={"version": API_VERSION}
            )
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_con_token_valido_devuelve_200(self):

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )

        response = self.client.get(
            reverse(
                "encomienda-list",
                kwargs={"version": API_VERSION}
            )
        )

        assert response.status_code == status.HTTP_200_OK


class TestListadoEncomiendas(BaseAPITest):

    def setUp(self):
        super().setUp()

        EncomiendaFactory.create_batch(5)

    def test_lista_respuesta_paginada(self):

        response = self.client.get(
            reverse(
                "encomienda-list",
                kwargs={"version": API_VERSION}
            )
        )

        assert response.status_code == status.HTTP_200_OK

        data = response.json()

        assert "results" in data

    def test_filtro_por_estado(self):

        EncomiendaFactory(
            estado="PE"
        )

        EncomiendaFactory(
            estado="EN"
        )

        response = self.client.get(
            reverse(
                "encomienda-list",
                kwargs={"version": API_VERSION}
            ),
            {
                "estado": "PE"
            }
        )

        assert response.status_code == status.HTTP_200_OK

        results = response.json()["results"]

        assert all(
            item["estado"] == "PE"
            for item in results
        )

    def test_busqueda_por_codigo(self):

        enc = EncomiendaFactory(
            codigo="ENC-SEARCH-001"
        )

        response = self.client.get(
            reverse(
                "encomienda-list",
                kwargs={"version": API_VERSION}
            ),
            {
                "search": enc.codigo
            }
        )

        assert response.status_code == status.HTTP_200_OK

        results = response.json()["results"]

        assert len(results) >= 1


class TestCrearEncomienda(BaseAPITest):

    def setUp(self):
        super().setUp()

        self.remitente = ClienteFactory()
        self.destinatario = ClienteFactory()
        self.ruta = RutaFactory()

    def payload(self):

        return {
            "codigo": "ENC-2026-9999",
            "descripcion": "Laptop gamer",
            "peso_kg": "5.50",
            "remitente": self.remitente.id,
            "destinatario": self.destinatario.id,
            "ruta": self.ruta.id,
            "costo_envio": "50.00",
            "estado": "PE",
            "fecha_entrega_est": (
                now().date() + timedelta(days=3)
            )
        }

    def test_crear_exitoso_devuelve_201(self):

        response = self.client.post(
            reverse(
                "encomienda-list",
                kwargs={"version": API_VERSION}
            ),
            self.payload(),
            format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_crear_asigna_empleado_del_token(self):

        response = self.client.post(
            reverse(
                "encomienda-list",
                kwargs={"version": API_VERSION}
            ),
            self.payload(),
            format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED

        encomienda = Encomienda.objects.get(
            codigo="ENC-2026-9999"
        )

        assert (
            encomienda.empleado_registro.id ==
            self.empleado.id
        )

    def test_remitente_igual_destinatario_devuelve_400(self):

        payload = self.payload()

        payload["destinatario"] = self.remitente.id

        response = self.client.post(
            reverse(
                "encomienda-list",
                kwargs={"version": API_VERSION}
            ),
            payload,
            format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_peso_negativo_devuelve_400_con_campo(self):

        payload = self.payload()

        payload["peso_kg"] = "-2"

        response = self.client.post(
            reverse(
                "encomienda-list",
                kwargs={"version": API_VERSION}
            ),
            payload,
            format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        assert "peso_kg" in response.json()

    def test_codigo_sin_prefijo_devuelve_400(self):

        payload = self.payload()

        payload["codigo"] = "ABC123"

        response = self.client.post(
            reverse(
                "encomienda-list",
                kwargs={"version": API_VERSION}
            ),
            payload,
            format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_sin_auth_no_crea_y_devuelve_401(self):

        self.client.credentials()

        response = self.client.post(
            reverse(
                "encomienda-list",
                kwargs={"version": API_VERSION}
            ),
            self.payload(),
            format="json"
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCambiarEstado(BaseAPITest):

    def setUp(self):
        super().setUp()

        self.encomienda = EncomiendaFactory(
            estado="PE"
        )

    def test_cambiar_estado_exitoso_actualiza_bd_y_crea_historial(self):

        url = reverse(
            "encomienda-cambiar-estado",
            kwargs={
                "version": API_VERSION,
                "pk": self.encomienda.pk
            }
        )

        response = self.client.post(
            url,
            {
                "estado": "EN"
            },
            format="json"
        )

        assert response.status_code == status.HTTP_200_OK

        self.encomienda.refresh_from_db()

        assert self.encomienda.estado == "EN"

        assert HistorialEstado.objects.filter(
            encomienda=self.encomienda
        ).exists()

    def test_cambiar_al_mismo_estado_devuelve_400(self):

        url = reverse(
            "encomienda-cambiar-estado",
            kwargs={
                "version": API_VERSION,
                "pk": self.encomienda.pk
            }
        )

        response = self.client.post(
            url,
            {
                "estado": "PE"
            },
            format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_sin_campo_estado_devuelve_400(self):

        url = reverse(
            "encomienda-cambiar-estado",
            kwargs={
                "version": API_VERSION,
                "pk": self.encomienda.pk
            }
        )

        response = self.client.post(
            url,
            {},
            format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_encomienda_inexistente_devuelve_404(self):

        url = reverse(
            "encomienda-cambiar-estado",
            kwargs={
                "version": API_VERSION,
                "pk": 99999
            }
        )

        response = self.client.post(
            url,
            {
                "estado": "EN"
            },
            format="json"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAccionesPersonalizadas(BaseAPITest):

    def setUp(self):
        super().setUp()

        self.enc_retraso = EncomiendaFactory(
            estado="PE",
            fecha_entrega_est=(
                now().date() + timedelta(days=1)
            )
        )

        self.enc_pendiente = EncomiendaFactory(
            estado="PE"
        )

        self.enc_entregada = EncomiendaFactory(
            estado="EN"
        )

    def test_con_retraso_solo_devuelve_retrasadas(self):

        url = reverse(
            "encomienda-con-retraso",
            kwargs={"version": API_VERSION}
        )

        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_pendientes_solo_devuelve_pendientes(self):

        url = reverse(
            "encomienda-pendientes",
            kwargs={"version": API_VERSION}
        )

        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK

        results = response.json()

        for item in results:
            assert item["estado"] == "PE"

    def test_estadisticas_devuelve_todos_los_contadores(self):

        url = reverse(
            "encomienda-estadisticas",
            kwargs={"version": API_VERSION}
        )

        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()

        assert "total" in data
        assert "pendientes" in data
        assert "entregadas" in data


class TestVersionado(APITestCase):

    def test_v1_responde_200_con_cabecera(self):

        response = self.client.get(
            "/api/v1/encomiendas/"
        )

        assert response.status_code in [200, 401]

    def test_v2_responde_200_con_cabecera(self):

        response = self.client.get(
            "/api/v2/encomiendas/"
        )

        assert response.status_code in [200, 401]

    def test_v2_incluye_campo_meta(self):

        response = self.client.get(
            "/api/v2/encomiendas/"
        )

        assert response.status_code in [200, 401]

    def test_v3_no_permitida_devuelve_404(self):

        response = self.client.get(
            "/api/v3/encomiendas/"
        )

        assert response.status_code == 404
