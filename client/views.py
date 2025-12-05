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
            raise status.HTTP_404_NOT_FOUND

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Get my client profile",
        operation_id="client_profile_retrieve",
        responses={200: ClientSerializer, 404: error_404}
    )
    def get(self, request):
        client = self.get_object()
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
        serializer = ClientUpdateSerializer(client, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ClientSerializer(client).data)


# ===========================
# CLIENTS BY ZONE (Very useful for operations)
# ===========================
class ClientByZoneView(APIView):
    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Get active clients in a zone",
        operation_id="clients_by_zone",
        manual_parameters=[
            openapi.Parameter(
                name="zone",
                in_=openapi.IN_QUERY,
                description="Zone identifier (exact match)",
                type=openapi.TYPE_STRING,
                required=True,
                example="Zone A1"
            ),
            openapi.Parameter(
                name="active_only",
                in_=openapi.IN_QUERY,
                description="Filter only active clients (default: true)",
                type=openapi.TYPE_BOOLEAN,
                required=False,
                example=True
            )
        ],
        responses={
            200: ClientListSerializer(many=True),
            400: openapi.Response("Missing zone parameter", examples={"application/json": {"error": "zone parameter is required"}})
        }
    )
    def get(self, request):
        zone = request.query_params.get("zone")
        if not zone:
            return Response({"error": "zone parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        queryset = Client.objects.filter(area_zone__iexact=zone.strip())
        
        # Optional filter for active only
        active_only = request.query_params.get("active_only", "true").lower() != "false"
        if active_only:
            queryset = queryset.filter(is_active=True)

        serializer = ClientListSerializer(queryset, many=True)
        return Response(serializer.data)


# ===========================
# CLIENT STATISTICS (Dashboard endpoint)
# ===========================
stats_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "total_clients": openapi.Schema(type=openapi.TYPE_INTEGER, description="Total registered clients"),
        "active_clients": openapi.Schema(type=openapi.TYPE_INTEGER),
        "inactive_clients": openapi.Schema(type=openapi.TYPE_INTEGER),
        "by_city": openapi.Schema(
            type=openapi.TYPE_OBJECT,
            additional_properties=openapi.Schema(type=openapi.TYPE_INTEGER),
            description="Count of clients per city"
        ),
        "by_property_type": openapi.Schema(
            type=openapi.TYPE_OBJECT,
            additional_properties=openapi.Schema(type=openapi.TYPE_INTEGER)
        ),
        "by_subscription_plan": openapi.Schema(
            type=openapi.TYPE_OBJECT,
            additional_properties=openapi.Schema(type=openapi.TYPE_INTEGER)
        ),
    },
    example={
        "total_clients": 1234,
        "active_clients": 1189,
        "inactive_clients": 45,
        "by_city": {"Accra": 890, "Kumasi": 344},
        "by_property_type": {"House": 780, "Apartment": 320, "Commercial": 134},
        "by_subscription_plan": {"Basic": 450, "Premium": 620, "Enterprise": 164}
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
        active = Client.objects.filter(is_active=True).count()

        # Dynamic aggregation (works even if choices change)
        from django.db.models import Count
        by_city = dict(
            Client.objects.values('city').annotate(count=Count('id')).values_list('city', 'count')
        )
        by_property = dict(
            Client.objects.values('property_type').annotate(count=Count('id')).values_list('property_type', 'count')
        )
        by_plan = dict(
            Client.objects.values('subscription_plan').annotate(count=Count('id')).values_list('subscription_plan', 'count')
        )

        return Response({
            "total_clients": total,
            "active_clients": active,
            "inactive_clients": total - active,
            "by_city": by_city or {},
            "by_property_type": by_property or {},
            "by_subscription_plan": by_plan or {},
        })