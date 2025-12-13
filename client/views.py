from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Client
from .serializers import (
    ClientCreateSerializer,
    ClientSerializer,
    ClientListSerializer,
    ClientUpdateSerializer,
)

# ===========================
# REUSABLE SCHEMAS & RESPONSES
# ===========================
error_400 = openapi.Response(
    description="Bad Request",
    examples={"application/json": {"phone_number": ["This phone number is already registered."]}}
)
error_404 = openapi.Response(
    description="Not Found",
    examples={"application/json": {"error": "Client profile not found"}}
)

TAGS = ["Clients"]


# ===========================
# CLIENT REGISTRATION
# ===========================
class ClientCreateView(APIView):
    """
    Register a new client account.
    Creates a User (role=client) + linked Client profile.
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Register a new client",
        operation_id="client_register",
        request_body=ClientCreateSerializer,
        responses={
            201: openapi.Response("Client created successfully", ClientSerializer),
            400: error_400,
        }
    )
    def post(self, request):
        serializer = ClientCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client = serializer.save()
        output = ClientSerializer(client).data
        return Response(output, status=status.HTTP_201_CREATED)


# ===========================
# LIST ALL CLIENTS (Admin/Staff)
# ===========================
class ClientListView(APIView):
    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="List all clients",
        operation_id="client_list",
        responses={200: ClientListSerializer(many=True)}
    )
    def get(self, request):
        clients = Client.objects.all()
        serializer = ClientListSerializer(clients, many=True)
        return Response(serializer.data)


# ===========================
# CLIENT PROFILE (Me)
# ===========================
class ClientProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        try:
            return Client.objects.get(user=self.request.user)
        except Client.DoesNotExist:
            return None

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Get my client profile",
        operation_id="client_profile_retrieve",
        responses={200: ClientSerializer, 404: error_404}
    )
    def get(self, request):
        client = self.get_object()
        if not client:
            return Response({"error": "Client profile not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(ClientSerializer(client).data)

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Fully update my profile",
        operation_id="client_profile_update",
        request_body=ClientUpdateSerializer,
        responses={200: ClientSerializer, 400: error_400, 404: error_404}
    )
    def put(self, request):
        return self._update(request, partial=False)

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Partially update my profile",
        operation_id="client_profile_partial_update",
        request_body=ClientUpdateSerializer,
        responses={200: ClientSerializer, 400: error_400, 404: error_404}
    )
    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial=False):
        client = self.get_object()
        if not client:
            return Response({"error": "Client profile not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = ClientUpdateSerializer(client, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ClientSerializer(client).data)


# ===========================
# CLIENT STATISTICS (Dashboard endpoint)
# ===========================
stats_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "total_clients": openapi.Schema(type=openapi.TYPE_INTEGER, description="Total registered clients"),
        "active_clients": openapi.Schema(type=openapi.TYPE_INTEGER),
        "inactive_clients": openapi.Schema(type=openapi.TYPE_INTEGER),
    },
    example={
        "total_clients": 1234,
        "active_clients": 1189,
        "inactive_clients": 45,
    }
)

class ClientStatisticsView(APIView):
    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Client statistics dashboard",
        operation_id="client_statistics",
        responses={200: stats_response_schema}
    )
    def get(self, request):
        total = Client.objects.count()
        active = Client.objects.filter(user__is_active=True).count()

        return Response({
            "total_clients": total,
            "active_clients": active,
            "inactive_clients": total - active,
        })
