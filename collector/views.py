from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.shortcuts import get_object_or_404
from .models import Collector
from .serializers import (
    CollectorCreateSerializer,
    CollectorListSerializer,
    CollectorUpdateSerializer,
)

# ===========================
# REUSABLE SCHEMAS & RESPONSES
# ===========================
error_400 = openapi.Response(
    description="Bad Request",
    examples={"application/json": {"phone_number": ["This phone number is already in use."]}}
)
error_404 = openapi.Response(
    description="Not Found",
    examples={"application/json": {"detail": "No collectors found matching the criteria."}}
)

TAGS = ["Collectors"]


# ===========================
# CREATE COLLECTOR
# ===========================
class CollectorCreateView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Register a new collector",
        operation_id="collector_register",
        request_body=CollectorCreateSerializer,
        responses={
            201: openapi.Response("Collector created successfully", CollectorListSerializer),
            400: error_400,
        }
    )
    def post(self, request):
        serializer = CollectorCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        collector = serializer.save()
        return Response(CollectorListSerializer(collector).data, status=status.HTTP_201_CREATED)


# ===========================
# LIST ALL COLLECTORS
# ===========================
class CollectorListView(APIView):
    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="List all collectors",
        operation_id="collector_list",
        responses={200: CollectorListSerializer(many=True)}
    )
    def get(self, request):
        collectors = Collector.objects.all()
        serializer = CollectorListSerializer(collectors, many=True)
        return Response(serializer.data)


# ===========================
# COLLECTOR PROFILE (My Profile)
# ===========================
class CollectorProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return get_object_or_404(Collector, user=self.request.user)

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Get my collector profile",
        operation_id="collector_profile_retrieve",
        responses={200: CollectorListSerializer, 404: error_404}
    )
    def get(self, request):
        collector = self.get_object()
        return Response(CollectorListSerializer(collector).data)

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Fully update my profile",
        operation_id="collector_profile_update",
        request_body=CollectorUpdateSerializer,
        responses={200: CollectorListSerializer, 400: error_400, 404: error_404}
    )
    def put(self, request):
        return self._update(request, partial=False)

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Partially update my profile",
        operation_id="collector_profile_partial_update",
        request_body=CollectorUpdateSerializer,
        responses={200: CollectorListSerializer, 400: error_400, 404: error_404}
    )
    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial=False):
        collector = self.get_object()
        serializer = CollectorUpdateSerializer(collector, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CollectorListSerializer(collector).data)


# ===========================
# COLLECTORS BY COMPANY (Path param)
# ===========================
class CollectorsByCompanyView(APIView):
    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Get collectors by company",
        operation_id="collectors_by_company",
        responses={
            200: CollectorListSerializer(many=True),
            404: error_404
        }
    )
    def get(self, request, company_id):
        collectors = Collector.objects.filter(company_id=company_id, is_private_collector=False)
        if not collectors.exists():
            return Response({"detail": "No collectors found for this company."}, status=status.HTTP_404_NOT_FOUND)
        serializer = CollectorListSerializer(collectors, many=True)
        return Response(serializer.data)


# ===========================
# COLLECTORS BY SUPERVISOR (Path param)
# ===========================
class CollectorsBySupervisorView(APIView):
    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Get collectors by supervisor",
        operation_id="collectors_by_supervisor",
        responses={
            200: CollectorListSerializer(many=True),
            404: error_404
        }
    )
    def get(self, request, supervisor_id):
        collectors = Collector.objects.filter(supervisor_id=supervisor_id)
        if not collectors.exists():
            return Response({"detail": "No collectors found under this supervisor."}, status=status.HTTP_404_NOT_FOUND)
        serializer = CollectorListSerializer(collectors, many=True)
        return Response(serializer.data)


# ===========================
# PRIVATE COLLECTORS ONLY
# ===========================
class PrivateCollectorsListView(APIView):
    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="List all private (independent) collectors",
        operation_id="private_collectors_list",
        responses={200: CollectorListSerializer(many=True)}
    )
    def get(self, request):
        collectors = Collector.objects.filter(is_private_collector=True)
        serializer = CollectorListSerializer(collectors, many=True)
        return Response(serializer.data)


# ===========================
# BONUS: Collectors by Zone + Active Status (Super useful for routing!)
# ===========================
class CollectorsByZoneView(APIView):
    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Get collectors assigned to a zone",
        operation_id="collectors_by_zone",
        manual_parameters=[
            openapi.Parameter("zone", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Zone name", required=True, example="East Legon Zone"),
            openapi.Parameter("active", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN, description="Filter active only", required=False)
        ],
        responses={200: CollectorListSerializer(many=True)}
    )
    def get(self, request):
        zone = request.query_params.get("zone")
        if not zone:
            return Response({"error": "zone parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        queryset = Collector.objects.filter(assigned_area_zone__iexact=zone.strip())

        if request.query_params.get("active") == "false":
            pass  # include inactive
        else:
            queryset = queryset.filter(is_active=True)

        serializer = CollectorListSerializer(queryset, many=True)
        return Response(serializer.data)