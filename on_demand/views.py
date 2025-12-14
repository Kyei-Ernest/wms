from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from datetime import timedelta
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from geopy.distance import geodesic
from scheduled_request.models import ScheduledRequest

from .models import OnDemandRequest
from .serializers import (
    OnDemandRequestDetailSerializer,
    OnDemandRequestCreateSerializer,
    OnDemandRequestUpdateSerializer,
)
# Import your role-based permissions
from accounts.permissions import IsClient, IsCollector, IsCompany, IsSupervisor, IsCompanyCollector,IsPrivateCollector


class OnDemandRequestViewSet(viewsets.ModelViewSet):
    queryset = OnDemandRequest.objects.all()
    serializer_class = OnDemandRequestDetailSerializer

    

    def get_serializer_class(self):
        if self.action == 'create':
            return OnDemandRequestCreateSerializer
        elif self.action in ['update', 'partial_update', 'assign', 'start', 'complete', 'cancel', 'accept']:
            return OnDemandRequestUpdateSerializer
        return OnDemandRequestDetailSerializer

    def get_queryset(self):
        user = self.request.user
        qs = OnDemandRequest.objects.all()

        # Supervisor access
        if IsSupervisor().has_permission(self.request, self):
            supervisor = getattr(user, 'supervisor', None)
            company = getattr(supervisor, 'company', None) if supervisor else None
            return qs.filter(company=company) if company else qs.none()

        # Company access
        if IsCompany().has_permission(self.request, self):
            company_obj = getattr(user, 'company', None)
            return qs.filter(company=company_obj) if company_obj else qs.none()

        # Collector access
        if IsCollector().has_permission(self.request, self):
            collector = getattr(user, 'collector', None)
            return qs.filter(collector=collector) if collector else qs.none()

        # Private collector access
        if IsPrivateCollector().has_permission(self.request, self):
            collector = getattr(user, 'collector', None)
            return qs.filter(collector=collector) if collector else qs.none()

        # Client access
        if IsClient().has_permission(self.request, self):
            return qs.filter(client=user)

        # Default fallback: no access
        return qs.none()



    # ---------------------------
    # Workflow Actions
    # ---------------------------

    @swagger_auto_schema(
        method='post',
        operation_summary="Assign Collector (On-Demand)",
        operation_description="Supervisor only: Assign a collector to an on-demand request.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={'collector': openapi.Schema(type=openapi.TYPE_INTEGER, description="Collector ID")},
            required=['collector'],
        ),
    )
    @action(detail=True, methods=['post'], permission_classes=[IsSupervisor])
    def assign(self, request, pk=None):
        ondemand_request = self.get_object()
        serializer = OnDemandRequestUpdateSerializer(ondemand_request, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(request_status="assigned", accepted_at=timezone.now())
        return Response(OnDemandRequestDetailSerializer(ondemand_request).data)

    @swagger_auto_schema(
        method='post',
        operation_summary="Start On-Demand Request",
        operation_description="Collector marks on-demand request as in progress.",
    )
    @action(detail=True, methods=['post'], permission_classes=[IsCollector])
    def start(self, request, pk=None):
        ondemand_request = self.get_object()
        serializer = OnDemandRequestUpdateSerializer(
            ondemand_request, data={'request_status': 'in_progress'}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OnDemandRequestDetailSerializer(ondemand_request).data)

    @swagger_auto_schema(
        method='post',
        operation_summary="Complete On-Demand Request",
        operation_description="Collector completes request with GPS validation.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'latitude': openapi.Schema(type=openapi.TYPE_NUMBER, description="Collector latitude"),
                'longitude': openapi.Schema(type=openapi.TYPE_NUMBER, description="Collector longitude"),
                'bag_count': openapi.Schema(type=openapi.TYPE_INTEGER, description="Bag count collected"),
            },
            required=['latitude', 'longitude'],
        ),
    )
    @action(detail=True, methods=['post'], permission_classes=[IsCollector])
    def complete(self, request, pk=None):
        ondemand_request = self.get_object()
        collector = ondemand_request.collector

        if not collector:
            return Response({"detail": "Cannot complete request without an assigned collector."}, status=400)

        lat = request.data.get("latitude")
        lng = request.data.get("longitude")
        if lat is None or lng is None:
            return Response({"detail": "Latitude and longitude are required."}, status=400)

        collector.last_known_latitude = lat
        collector.last_known_longitude = lng
        collector.save()

        if ondemand_request.location:
            client_coords = (ondemand_request.location.y, ondemand_request.location.x)
            collector_coords = (float(lat), float(lng))
            distance_m = geodesic(client_coords, collector_coords).meters

            if distance_m > 300:
                return Response({"detail": "Completion rejected: collector too far (>300m)."}, status=400)
            elif distance_m > 100:
                request.data["request_status"] = "suspected"

        serializer = OnDemandRequestUpdateSerializer(ondemand_request, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            request_status=serializer.validated_data.get("request_status", "completed"),
            completed_at=timezone.now(),
        )
        return Response(OnDemandRequestDetailSerializer(ondemand_request).data)
    @swagger_auto_schema(
        method='post',
        operation_summary="Accept On-Demand Request",
        operation_description="Private collectors can accept available on-demand requests (status must be pending).",
    )
    @action(detail=True, methods=['post'], permission_classes=[IsPrivateCollector])
    def accept(self, request, pk=None):
        ondemand_request = self.get_object()

        # Only allow accepting if request is still pending
        if ondemand_request.request_status != "pending":
            return Response(
                {"detail": "Only pending requests can be accepted."},
                status=status.HTTP_400_BAD_REQUEST
            )

        collector = request.user.collector
        if not collector.is_private_collector:
            return Response(
                {"detail": "Only private collectors can accept offers."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Assign the request to this collector
        ondemand_request.collector = collector
        ondemand_request.request_status = "assigned"
        ondemand_request.accepted_at = timezone.now()
        ondemand_request.save()

        return Response(OnDemandRequestDetailSerializer(ondemand_request).data)
    
    
    @swagger_auto_schema(
        method='post',
        operation_summary="Cancel On-Demand Request",
        operation_description="Supervisor only: Cancel an on-demand request with reason.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={'cancellation_reason': openapi.Schema(type=openapi.TYPE_STRING)},
            required=['cancellation_reason'],
        ),
    )
    @action(detail=True, methods=['post'], permission_classes=[IsSupervisor])
    def cancel(self, request, pk=None):
        ondemand_request = self.get_object()
        serializer = OnDemandRequestUpdateSerializer(ondemand_request, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(request_status="cancelled", cancelled_at=timezone.now())
        return Response(OnDemandRequestDetailSerializer(ondemand_request).data)

    # ---------------------------
    # List & Summary Endpoints
    # ---------------------------

    @action(detail=False, methods=['get'], permission_classes=[IsSupervisor | IsCollector])
    def list_pending(self, request):
        qs = self.get_queryset().filter(request_status="pending")
        return Response(OnDemandRequestDetailSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], permission_classes=[IsSupervisor | IsCollector])
    def list_today(self, request):
        today = timezone.now().date()
        qs = self.get_queryset().filter(requested_at__date=today)
        return Response(OnDemandRequestDetailSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], permission_classes=[IsSupervisor | IsCollector])
    def list_by_collector(self, request):
        collector_id = request.query_params.get("collector_id")
        if not collector_id:
            return Response({"detail": "collector_id query parameter is required."}, status=400)
        qs = self.get_queryset().filter(collector_id=collector_id)
        return Response(OnDemandRequestDetailSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], permission_classes=[IsSupervisor])
    def list_by_company(self, request):
        company_id = request.query_params.get("company_id")
        if not company_id:
            return Response({"detail": "company_id query parameter is required."}, status=400)
        qs = self.get_queryset().filter(company_id=company_id)
        return Response(OnDemandRequestDetailSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], permission_classes=[IsSupervisor])
    def summary(self, request):
        company_id = request.query_params.get("company_id")
        if not company_id:
            return Response({"detail": "company_id query parameter is required."}, status=400)
        qs = self.get_queryset().filter(company_id=company_id)
        data = {
            "pending": qs.filter(request_status="pending").count(),
            "assigned": qs.filter(request_status="assigned").count(),
            "in_progress": qs.filter(request_status="in_progress").count(),
            "completed": qs.filter(request_status="completed").count(),
            "cancelled": qs.filter(request_status="cancelled").count(),
            "suspected": qs.filter(request_status="suspected").count(),
            "total": qs.count(),
        }
        return Response(data)

    @action(detail=False, methods=['get'], permission_classes=[IsSupervisor])
    def summary_timebound(self, request):
        company_id = request.query_params.get("company_id")
        if not company_id:
            return Response({"detail": "company_id query parameter is required."}, status=400)

        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        start_of_month = today.replace(day=1)

        def build_summary(qs):
            return {
                "pending": qs.filter(request_status="pending").count(),
                "assigned": qs.filter(request_status="assigned").count(),
                "in_progress": qs.filter(request_status="in_progress").count(),
                "completed": qs.filter(request_status="completed").count(),
                "cancelled": qs.filter(request_status="cancelled").count(),
                "suspected": qs.filter(request_status="suspected").count(),
                "total": qs.count(),
            }

        qs = self.get_queryset().filter(company_id=company_id)

        today_qs = qs.filter(requested_at__date=today)
        week_qs = qs.filter(requested_at__date__gte=start_of_week, requested_at__date__lte=today)
        month_qs = qs.filter(requested_at__date__gte=start_of_month, requested_at__date__lte=today)

        data = {
            "today": build_summary(today_qs),
            "week": build_summary(week_qs),
            "month": build_summary(month_qs),
        }
        return Response(data)
    @swagger_auto_schema(
        method='get',
        operation_summary="Collector Dashboard Summary (On-Demand)",
        operation_description="Collector only: Get counts of on-demand requests by status for a given collector.",
        manual_parameters=[
            openapi.Parameter(
                'collector_id',
                openapi.IN_QUERY,
                description="Collector ID",
                type=openapi.TYPE_INTEGER,
                required=True,
            )
        ],
    )
    @action(detail=False, methods=['get'], permission_classes=[IsCollector])
    def summary_collector(self, request):
        collector_id = request.query_params.get("collector_id")
        if not collector_id:
            return Response({"detail": "collector_id query parameter is required."}, status=400)

        qs = self.get_queryset().filter(collector_id=collector_id)

        data = {
            "pending": qs.filter(request_status="pending").count(),
            "assigned": qs.filter(request_status="assigned").count(),
            "in_progress": qs.filter(request_status="in_progress").count(),
            "completed": qs.filter(request_status="completed").count(),
            "cancelled": qs.filter(request_status="cancelled").count(),
            "suspected": qs.filter(request_status="suspected").count(),
            "total": qs.count(),
        }
        return Response(data)

    @swagger_auto_schema(
        method='get',
        operation_summary="Combined Company & Collector Summary (On-Demand)",
        operation_description="Supervisor only: Get counts of on-demand requests by status for both company and collector.",
        manual_parameters=[
            openapi.Parameter('company_id', openapi.IN_QUERY, description="Company ID", type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter('collector_id', openapi.IN_QUERY, description="Collector ID", type=openapi.TYPE_INTEGER, required=False),
        ],
    )
    @action(detail=False, methods=['get'], permission_classes=[IsSupervisor])
    def summary_all(self, request):
        company_id = request.query_params.get("company_id")
        collector_id = request.query_params.get("collector_id")

        if not company_id:
            return Response({"detail": "company_id query parameter is required."}, status=400)

        qs = self.get_queryset().filter(company_id=company_id)

        def build_summary(qs):
            return {
                "pending": qs.filter(request_status="pending").count(),
                "assigned": qs.filter(request_status="assigned").count(),
                "in_progress": qs.filter(request_status="in_progress").count(),
                "completed": qs.filter(request_status="completed").count(),
                "cancelled": qs.filter(request_status="cancelled").count(),
                "suspected": qs.filter(request_status="suspected").count(),
                "total": qs.count(),
            }

        company_summary = build_summary(qs)
        collector_summary = {}

        if collector_id:
            collector_qs = qs.filter(collector_id=collector_id)
            collector_summary = build_summary(collector_qs)

        data = {
            "company_summary": company_summary,
            "collector_summary": collector_summary if collector_id else None,
        }
        return Response(data)
    
    @swagger_auto_schema(
        operation_summary="Client request summary",
        operation_description="Client views aggregated stats of their own requests (on-demand or scheduled)."
    )
    @action(detail=False, methods=['get'], permission_classes=[IsClient])
    def my_summary(self, request):
        client = request.user.client
        ondemand_qs = OnDemandRequest.objects.filter(client=client)
        scheduled_qs = ScheduledRequest.objects.filter(client=client)

        summary = {
            "ondemand": {
                "total": ondemand_qs.count(),
                "completed": ondemand_qs.filter(request_status="completed").count(),
                "pending": ondemand_qs.filter(request_status="pending").count(),
                "cancelled": ondemand_qs.filter(request_status="cancelled").count(),
            },
            "scheduled": {
                "total": scheduled_qs.count(),
                "completed": scheduled_qs.filter(request_status="completed").count(),
                "pending": scheduled_qs.filter(request_status="pending").count(),
                "cancelled": scheduled_qs.filter(request_status="cancelled").count(),
            }
        }
        return Response(summary)
    
    @swagger_auto_schema(
        operation_summary="List client on-demand requests",
        operation_description="Client lists all their own on-demand requests."
    )
    @action(detail=False, methods=['get'], permission_classes=[IsClient])
    def my_requests(self, request):
        client = request.user.client
        qs = OnDemandRequest.objects.filter(client=client).order_by('-created_at')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)