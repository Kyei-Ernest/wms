from datetime import timedelta
from accounts.permissions import IsClient, IsSupervisorOrCompanyAdmin, IsSupervisor
from rest_framework import status, viewsets, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from geopy.distance import geodesic
from django.contrib.gis.geos import Point
from django_filters.rest_framework import DjangoFilterBackend


from .models import ScheduledRequest
from .serializers import (
    ScheduledRequestDetailSerializer,
    ScheduledRequestCreateSerializer,
    ScheduledRequestUpdateSerializer,
)




class ScheduledRequestViewSet(viewsets.ModelViewSet):
    queryset = ScheduledRequest.objects.all()
    serializer_class = ScheduledRequestDetailSerializer

    # Enable filtering and searching
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['pickup_date', 'request_status', 'collector', 'company', 'client']
    search_fields = ['client__name', 'company__name', 'collector__name', 'city', 'area_zone']
    ordering_fields = ['pickup_date', 'pickup_time_slot', 'request_status', 'completed_at']
    ordering = ['pickup_date', 'pickup_time_slot']

    def get_serializer_class(self):
        if self.action in ['create']:
            return ScheduledRequestCreateSerializer
        elif self.action in ['update', 'partial_update', 'assign', 'start', 'complete', 'cancel']:
            return ScheduledRequestUpdateSerializer
        return ScheduledRequestDetailSerializer

    # ---------------------------
    # Custom Actions
    # ---------------------------

    @swagger_auto_schema(
        method='post',
        operation_summary="Assign Collector",
        operation_description="Supervisor only: Assign a collector to a scheduled request.",        
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'collector': openapi.Schema(type=openapi.TYPE_INTEGER, description="Collector ID"),
            },
            required=['collector'],
        ),
        responses={200: ScheduledRequestDetailSerializer},
    )
    @action(detail=True, methods=['post'], permission_classes = [IsSupervisor])
    def assign(self, request, pk=None):
        scheduled_request = self.get_object()
        serializer = ScheduledRequestUpdateSerializer(
            scheduled_request, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(request_status="assigned", accepted_at=timezone.now())
        return Response(ScheduledRequestDetailSerializer(scheduled_request).data)

    @swagger_auto_schema(
        method='post',
        operation_summary="Start Scheduled Request",
        operation_description="Mark a scheduled request as in progress.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'collector': openapi.Schema(type=openapi.TYPE_INTEGER, description="Collector ID (optional if already assigned)"),
            },
        ),
        responses={200: ScheduledRequestDetailSerializer},
    )
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        scheduled_request = self.get_object()
        serializer = ScheduledRequestUpdateSerializer(
            scheduled_request, data={'request_status': 'in_progress'}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ScheduledRequestDetailSerializer(scheduled_request).data)

    @swagger_auto_schema(
        method='post',
        operation_summary="Complete Scheduled Request",
        operation_description="Collector marks scheduled request as completed. Enforces GPS validation.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'latitude': openapi.Schema(type=openapi.TYPE_NUMBER, description="Collector latitude"),
                'longitude': openapi.Schema(type=openapi.TYPE_NUMBER, description="Collector longitude"),
                'bag_count': openapi.Schema(type=openapi.TYPE_INTEGER, description="Bag count collected"),
            },
            required=['latitude', 'longitude'],
        ),
        responses={200: ScheduledRequestDetailSerializer},
    )
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        scheduled_request = self.get_object()
        collector = scheduled_request.collector

        if not collector:
            return Response(
                {"detail": "Cannot complete request without an assigned collector."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update collector GPS
        lat = request.data.get("latitude")
        lng = request.data.get("longitude")
        if lat is None or lng is None:
            return Response(
                {"detail": "Latitude and longitude are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        collector.last_known_latitude = lat
        collector.last_known_longitude = lng
        collector.save()

        # GPS validation
        if scheduled_request.location:
            client_coords = (scheduled_request.location.y, scheduled_request.location.x)  # (lat, lon)
            collector_coords = (float(lat), float(lng))
            distance_m = geodesic(client_coords, collector_coords).meters

            if distance_m > 300:
                return Response(
                    {"detail": "Completion rejected: collector too far from client (>300m)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            elif distance_m > 100:
                # Auto-flag suspected completion
                request.data["request_status"] = "suspected"

        serializer = ScheduledRequestUpdateSerializer(
            scheduled_request, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(
            request_status=serializer.validated_data.get("request_status", "completed"),
            completed_at=timezone.now(),
        )
        return Response(ScheduledRequestDetailSerializer(scheduled_request).data)

    @swagger_auto_schema(
        method='post',
        operation_summary="Cancel Scheduled Request",
        operation_description="Cancel a scheduled request with reason.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'cancellation_reason': openapi.Schema(type=openapi.TYPE_STRING, description="Reason for cancellation"),
            },
            required=['cancellation_reason'],
        ),
        responses={200: ScheduledRequestDetailSerializer},
    )
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        scheduled_request = self.get_object()
        serializer = ScheduledRequestUpdateSerializer(
            scheduled_request, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(request_status="cancelled", cancelled_at=timezone.now())
        return Response(ScheduledRequestDetailSerializer(scheduled_request).data)
    
     # ---------------------------
    # Custom List Endpoints
    # ---------------------------

    @swagger_auto_schema(
        method='get',
        operation_summary="List Pending Scheduled Requests",
        operation_description="Retrieve all scheduled requests with status 'pending'.",
        responses={200: ScheduledRequestDetailSerializer(many=True)},
    )
    @action(detail=False, methods=['get'],permission_classes = [IsSupervisorOrCompanyAdmin])
    def list_pending(self, request):
        qs = self.get_queryset().filter(request_status="pending")
        serializer = ScheduledRequestDetailSerializer(qs, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='get',
        operation_summary="List Today's Scheduled Requests",
        operation_description="Retrieve all scheduled requests for today's date.",
        responses={200: ScheduledRequestDetailSerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def list_today(self, request):
        today = timezone.now().date()
        qs = self.get_queryset().filter(pickup_date=today)
        serializer = ScheduledRequestDetailSerializer(qs, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='get',
        operation_summary="List Scheduled Requests by Collector",
        operation_description="Retrieve all scheduled requests assigned to a given collector.",
        manual_parameters=[
            openapi.Parameter(
                'collector_id',
                openapi.IN_QUERY,
                description="Collector ID",
                type=openapi.TYPE_INTEGER,
                required=True,
            )
        ],
        responses={200: ScheduledRequestDetailSerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def list_by_collector(self, request):
        collector_id = request.query_params.get("collector_id")
        if not collector_id:
            return Response({"detail": "collector_id query parameter is required."}, status=400)
        qs = self.get_queryset().filter(collector_id=collector_id)
        serializer = ScheduledRequestDetailSerializer(qs, many=True)
        return Response(serializer.data)
    
    @swagger_auto_schema(
        method='get',
        operation_summary="List Scheduled Requests by Company",
        operation_description="Retrieve all scheduled requests for a given company.",
        manual_parameters=[
            openapi.Parameter(
                'company_id',
                openapi.IN_QUERY,
                description="Company ID",
                type=openapi.TYPE_INTEGER,
                required=True,
            )
        ],
        responses={200: ScheduledRequestDetailSerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def list_by_company(self, request):
        company_id = request.query_params.get("company_id")
        if not company_id:
            return Response({"detail": "company_id query parameter is required."}, status=400)
        qs = self.get_queryset().filter(company_id=company_id)
        serializer = ScheduledRequestDetailSerializer(qs, many=True)
        return Response(serializer.data)
    
    @swagger_auto_schema(
        method='get',
        operation_summary="Company Dashboard Summary",
        operation_description="Get counts of scheduled requests by status for a given company.",
        manual_parameters=[
            openapi.Parameter(
                'company_id',
                openapi.IN_QUERY,
                description="Company ID",
                type=openapi.TYPE_INTEGER,
                required=True,
            )
        ],
        responses={200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'pending': openapi.Schema(type=openapi.TYPE_INTEGER),
                'assigned': openapi.Schema(type=openapi.TYPE_INTEGER),
                'in_progress': openapi.Schema(type=openapi.TYPE_INTEGER),
                'completed': openapi.Schema(type=openapi.TYPE_INTEGER),
                'cancelled': openapi.Schema(type=openapi.TYPE_INTEGER),
                'suspected': openapi.Schema(type=openapi.TYPE_INTEGER),
                'total': openapi.Schema(type=openapi.TYPE_INTEGER),
            }
        )},
    )
    @action(detail=False, methods=['get'])
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
    
    @swagger_auto_schema(
        method='get',
        operation_summary="Company Time-Bounded Summary",
        operation_description="Get counts of scheduled requests by status for today, this week, and this month.",
        manual_parameters=[
            openapi.Parameter(
                'company_id',
                openapi.IN_QUERY,
                description="Company ID",
                type=openapi.TYPE_INTEGER,
                required=True,
            )
        ],
        responses={200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'today': openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'pending': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'assigned': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'in_progress': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'completed': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'cancelled': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'suspected': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                ),
                'week': openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'pending': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'assigned': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'in_progress': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'completed': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'cancelled': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'suspected': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                ),
                'month': openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'pending': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'assigned': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'in_progress': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'completed': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'cancelled': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'suspected': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                ),
            }
        )},
    )
    @action(detail=False, methods=['get'])
    def summary_timebound(self, request):
        company_id = request.query_params.get("company_id")
        if not company_id:
            return Response({"detail": "company_id query parameter is required."}, status=400)

        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())  # Monday
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

        today_qs = qs.filter(pickup_date=today)
        week_qs = qs.filter(pickup_date__gte=start_of_week, pickup_date__lte=today)
        month_qs = qs.filter(pickup_date__gte=start_of_month, pickup_date__lte=today)

        data = {
            "today": build_summary(today_qs),
            "week": build_summary(week_qs),
            "month": build_summary(month_qs),
        }
        return Response(data)
    
    @swagger_auto_schema(
        method='get',
        operation_summary="Collector Dashboard Summary",
        operation_description="Get counts of scheduled requests by status for a given collector.",
        manual_parameters=[
            openapi.Parameter(
                'collector_id',
                openapi.IN_QUERY,
                description="Collector ID",
                type=openapi.TYPE_INTEGER,
                required=True,
            )
        ],
        responses={200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'pending': openapi.Schema(type=openapi.TYPE_INTEGER),
                'assigned': openapi.Schema(type=openapi.TYPE_INTEGER),
                'in_progress': openapi.Schema(type=openapi.TYPE_INTEGER),
                'completed': openapi.Schema(type=openapi.TYPE_INTEGER),
                'cancelled': openapi.Schema(type=openapi.TYPE_INTEGER),
                'suspected': openapi.Schema(type=openapi.TYPE_INTEGER),
                'total': openapi.Schema(type=openapi.TYPE_INTEGER),
            }
        )},
    )
    @action(detail=False, methods=['get'])
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
        operation_summary="Combined Company & Collector Summary",
        operation_description="Get counts of scheduled requests by status for both company and collector in one response.",
        manual_parameters=[
            openapi.Parameter(
                'company_id',
                openapi.IN_QUERY,
                description="Company ID",
                type=openapi.TYPE_INTEGER,
                required=True,
            ),
            openapi.Parameter(
                'collector_id',
                openapi.IN_QUERY,
                description="Collector ID",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
        ],
        responses={200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'company_summary': openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'pending': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'assigned': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'in_progress': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'completed': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'cancelled': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'suspected': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                ),
                'collector_summary': openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'pending': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'assigned': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'in_progress': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'completed': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'cancelled': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'suspected': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                ),
            }
        )},
    )
    @action(detail=False, methods=['get'])
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
        operation_summary="List client scheduled requests",
        operation_description="Client lists all their own scheduled requests."
    )
    @action(detail=False, methods=['get'], permission_classes=[IsClient])
    def my_requests(self, request):
        client = request.user.client
        qs = ScheduledRequest.objects.filter(client=client).order_by('-created_at')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
