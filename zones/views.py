from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Zone
from .serializers import (
    ZoneCreateSerializer,
    ZoneUpdateSerializer,
    ZoneListSerializer,
)

# Reusable error responses
error_400 = openapi.Response('Bad Request', examples={"application/json": {"detail": "Invalid data"}})
error_404 = openapi.Response('Not Found', examples={"application/json": {"detail": "Zone not found"}})

tag = ['Zones']

# -------------------------------
# CREATE ZONE
# -------------------------------
class ZoneCreateView(APIView):
    @swagger_auto_schema(
        tags=tag,
        operation_summary="Create a new zone",
        operation_id="create_zone",
        request_body=ZoneCreateSerializer,
        responses={
            201: ZoneListSerializer,
            400: error_400,
        }
    )
    def post(self, request):
        serializer = ZoneCreateSerializer(data=request.data)
        if serializer.is_valid():
            zone = serializer.save()
            return Response(ZoneListSerializer(zone).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -------------------------------
# UPDATE ZONE (PUT & PATCH)
# -------------------------------
class ZoneUpdateView(APIView):
    @swagger_auto_schema(
        tags=tag,
        operation_summary="Fully update a zone",
        operation_id="update_zone",
        request_body=ZoneUpdateSerializer,
        responses={200: ZoneListSerializer, 400: error_400, 404: error_404},
    )
    def put(self, request, zone_id):
        return self._update(request, zone_id, partial=False)

    @swagger_auto_schema(
        tags=tag,
        operation_summary="Partially update a zone",
        operation_id="partial_update_zone",
        request_body=ZoneUpdateSerializer,
        responses={200: ZoneListSerializer, 400: error_400, 404: error_404},
    )
    def patch(self, request, zone_id):
        return self._update(request, zone_id, partial=True)

    def _update(self, request, zone_id, partial=False):
        zone = get_object_or_404(Zone, zone_id=zone_id)
        serializer = ZoneUpdateSerializer(zone, data=request.data, partial=partial)
        if serializer.is_valid():
            zone = serializer.save()
            return Response(ZoneListSerializer(zone).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -------------------------------
# LIST / RETRIEVE
# -------------------------------
class ZoneListView(APIView):
    @swagger_auto_schema(
        tags=tag,
        operation_summary="List all zones",
        operation_id="list_zones",
        manual_parameters=[
            openapi.Parameter(
                'city',
                openapi.IN_QUERY,
                description="Filter zones by city name (case-insensitive)",
                type=openapi.TYPE_STRING,
                required=False,
                example="Accra"
            )
        ],
        responses={200: ZoneListSerializer(many=True)},
    )
    def get(self, request):
        city = request.query_params.get('city')
        queryset = Zone.objects.filter(city__iexact=city) if city else Zone.objects.all()
        serializer = ZoneListSerializer(queryset, many=True)
        return Response(serializer.data)


class ZoneDetailView(APIView):
    @swagger_auto_schema(
        tags=tag,
        operation_summary="Retrieve a single zone",
        operation_id="retrieve_zone",
        responses={200: ZoneListSerializer, 404: error_404},
    )
    def get(self, request, zone_id):
        zone = get_object_or_404(Zone, zone_id=zone_id)
        return Response(ZoneListSerializer(zone).data)

## ===========================
# POINT IN ZONE CHECK (BONUS & SUPER USEFUL)
# ===========================
point_request_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["lat", "lng"],
    properties={
        "lat": openapi.Schema(
            type=openapi.TYPE_NUMBER,
            description="Latitude",
            example=5.603718
        ),
        "lng": openapi.Schema(
            type=openapi.TYPE_NUMBER,
            description="Longitude",
            example=-0.187197
        )
    },
    example={"lat": 5.603718, "lng": -0.187197}
)

class PointInZoneView(APIView):
    @swagger_auto_schema(
        tags=tag,
        operation_summary="Check which zone(s) contain a coordinate",
        operation_id="point_in_zone",
        request_body=point_request_schema,
        responses={
            200: ZoneListSerializer(many=True),
            400: error_400
        }
    )
    def post(self, request):
        lat = request.data.get("lat")
        lng = request.data.get("lng")

        if not (isinstance(lat, (int, float)) and isinstance(lng, (int, float))):
            return Response(
                {"error": "lat and lng must be numbers"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Assuming your Zone model has a .contains_point(lat, lng) method
        zones = [
            zone for zone in Zone.objects.all()
            if zone.contains_point(lat, lng)
        ]

        serializer = ZoneListSerializer(zones, many=True)
        return Response(serializer.data)