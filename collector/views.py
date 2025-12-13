from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
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
    examples={"application/json": {"error": "Invalid input or rule violation"}}
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
    """
    Register a new collector.

    Rules:
    - Private collectors (is_private_collector=True) can self-register and are active immediately.
    - Companies cannot create private collectors.
    - Non-private collectors must be created by an authenticated company account.
      The company's PK is auto-injected (frontend should not send company_id).
    - Non-private collectors start with status="pending_approval" until company approves.
    """

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Register a new collector",
        operation_description="""
        Register a new collector.

        - Private collectors: set `is_private_collector=true`. They are active immediately.
        - Company collectors: set `is_private_collector=false`. Must be created by a company account.
          Backend auto-injects company_id and sets status="pending_approval".
        - Companies cannot create private collectors.
        """,
        operation_id="collector_register",
        request_body=CollectorCreateSerializer,
        responses={201: CollectorListSerializer, 400: error_400}
    )
    def post(self, request):
        data = request.data.copy()
        is_private = data.get("is_private_collector", False)

        if is_private:
            if hasattr(request.user, "company"):
                return Response(
                    {"error": "Companies cannot create private collectors."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            data["company"] = None
            data["status"] = "active"
        else:
            if not hasattr(request.user, "company"):
                return Response(
                    {"error": "Only authenticated companies can create non-private collectors."},
                    status=status.HTTP_403_FORBIDDEN
                )
            data["company"] = request.user.company.pk
            data["status"] = "pending_approval"

        serializer = CollectorCreateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        collector = serializer.save()
        return Response(CollectorListSerializer(collector).data, status=status.HTTP_201_CREATED)


# ===========================
# LIST ALL COLLECTORS
# ===========================
class CollectorListView(APIView):
    """
    List all collectors in the system.
    Typically used by supervisors or admins.
    """

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
    """
    Authenticated collector can view and update their own profile.
    """

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
# COLLECTORS BY COMPANY
# ===========================
class CollectorsByCompanyView(APIView):
    """
    List all collectors belonging to a specific company.
    Private collectors are excluded.
    """

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Get collectors by company",
        operation_id="collectors_by_company",
        responses={200: CollectorListSerializer(many=True), 404: error_404}
    )
    def get(self, request, company_id):
        collectors = Collector.objects.filter(company_id=company_id, is_private_collector=False)
        if not collectors.exists():
            return Response({"detail": "No collectors found for this company."}, status=status.HTTP_404_NOT_FOUND)
        serializer = CollectorListSerializer(collectors, many=True)
        return Response(serializer.data)


# ===========================
# COLLECTORS BY SUPERVISOR
# ===========================
class CollectorsBySupervisorView(APIView):
    """
    List all collectors under a specific supervisor.
    """

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Get collectors by supervisor",
        operation_id="collectors_by_supervisor",
        responses={200: CollectorListSerializer(many=True), 404: error_404}
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
    """
    List all independent/private collectors.
    """

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="List all private collectors",
        operation_id="private_collectors_list",
        responses={200: CollectorListSerializer(many=True)}
    )
    def get(self, request):
        collectors = Collector.objects.filter(is_private_collector=True)
        serializer = CollectorListSerializer(collectors, many=True)
        return Response(serializer.data)


# ===========================
# COLLECTORS BY ZONE
# ===========================
class CollectorsByZoneView(APIView):
    """
    List collectors assigned to a specific zone.
    Optional query param `active=true` filters only active collectors.
    """

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Get collectors by zone",
        operation_id="collectors_by_zone",
        manual_parameters=[
            openapi.Parameter("zone", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Zone name", required=True),
            openapi.Parameter("active", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN, description="Filter active only", required=False)
        ],
        responses={200: CollectorListSerializer(many=True)}
    )
    def get(self, request):
        zone = request.query_params.get("zone")
        if not zone:
            return Response({"error": "zone parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        queryset = Collector.objects.filter(assigned_area_zone__iexact=zone.strip())
        if request.query_params.get("active") != "false":
            queryset = queryset.filter(is_active=True)

        serializer = CollectorListSerializer(queryset, many=True)
        return Response(serializer.data)


# ===========================
# COMPANY APPROVAL FLOW
# ===========================
class CollectorApprovalView(APIView):
    """
    Endpoint for companies to approve or reject pending collectors.

    Usage:
    - POST /collectors/{collector_id}/approval/
    - Request body must include {"action": "approve"} or {"action": "reject"}.

    Rules:
    - Only the authenticated company that owns the collector can approve/reject.
    - Approved collectors → status set to "active".
    - Rejected collectors → status set to "rejected".
    """

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Approve or reject a pending collector",
        operation_description="""
        Companies use this endpoint to approve or reject collectors who registered
        under their company but are currently in status="pending_approval".

        Request body:
        {
          "action": "approve"
        }
        or
        {
          "action": "reject"
        }

        Responses:
        - 200: Collector status updated successfully.
        - 400: Invalid action provided.
        - 404: Collector not found or not tied to this company.
        """,
        operation_id="collector_approval",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "action": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["approve", "reject"],
                    description="Action to perform on the pending collector"
                )
            },
            required=["action"]
        ),
        responses={200: CollectorListSerializer, 400: error_400, 404: error_404}
    )
    def post(self, request, collector_id):
        collector = get_object_or_404(Collector, pk=collector_id, company=request.user.company)
        action = request.data.get("action")

        if action == "approve":
            collector.status = "active"
            collector.save()
            return Response({"detail": "Collector approved."}, status=status.HTTP_200_OK)

        elif action == "reject":
            collector.status = "rejected"
            collector.save()
            return Response({"detail": "Collector rejected."}, status=status.HTTP_200_OK)

        return Response({"error": "Invalid action. Use 'approve' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)