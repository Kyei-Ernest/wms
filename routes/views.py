from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema

from .models import Route,RouteStop
from .serializers import RouteSerializer, RouteStopSerializer
from accounts.permissions import IsSupervisor, IsCompanyCollector
from collection_management.models import CollectionRecord
from collection_management.serializers import CollectionRecordCreateSerializer, CollectionRecordSerializer
class RouteViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing company collector routes.
    - Supervisors: create, assign, view, and summarize routes.
    - Collectors: start and complete assigned routes.
    """

    queryset = Route.objects.all()
    serializer_class = RouteSerializer

    # --- Basic CRUD endpoints ---
    @swagger_auto_schema(
        operation_summary="List all routes",
        operation_description="Returns a list of all routes accessible to the user. Supervisors see company routes, collectors see their own.",
        tags=["Routes"]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Retrieve a route",
        operation_description="Returns detailed information about a single route, including stops and progress.",
        tags=["Routes"]
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Create a route",
        operation_description="Supervisor creates a new route for a collector. Requires company, zone, supervisor, collector, and route_date.",
        tags=["Routes"]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Update a route",
        operation_description="Supervisor updates route details (e.g., timings, zone, collector).",
        tags=["Routes"]
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Delete a route",
        operation_description="Supervisor deletes a route. Typically used for draft or cancelled routes.",
        tags=["Routes"]
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_summary="Update a route (partial)",
        operation_description=(
            "Supervisor updates route details using PATCH. "
            "Only the provided fields will be updated. "
            "Typical use cases: adjusting start/end times, reassigning collector, "
            "or updating zone information."
        ),
        tags=["Routes"],
        request_body=RouteSerializer,
        responses={200: RouteSerializer}
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    # --- Custom actions ---
    @swagger_auto_schema(
        operation_summary="Route summary (timebound)",
        operation_description="Supervisor views aggregated route stats for today, this week, and this month.",
        tags=["Routes"]
    )
    @action(detail=False, methods=['get'], permission_classes=[IsSupervisor])
    def summary_timebound(self, request):
        supervisor = request.user.supervisor
        today = timezone.now().date()
        qs = self.get_queryset().filter(supervisor=supervisor)

        summary = {
            "today": {
                "routes": qs.filter(route_date=today).count(),
                "completed": qs.filter(route_date=today, status="completed").count(),
                "in_progress": qs.filter(route_date=today, status="in_progress").count(),
            }
        }
        return Response(summary)

    @swagger_auto_schema(
        operation_summary="Start a route",
        operation_description="Collector marks the route as in progress and sets actual_start timestamp.",
        tags=["Routes"]
    )
    @action(detail=True, methods=['post'], permission_classes=[IsCompanyCollector])
    def start(self, request, pk=None):
        route = self.get_object()
        route.status = "in_progress"
        route.actual_start = timezone.now()
        route.save()
        return Response(self.get_serializer(route).data)

    @swagger_auto_schema(
        operation_summary="Complete a route",
        operation_description="Collector marks the route as completed and sets actual_end timestamp. Completion percent auto-updates.",
        tags=["Routes"]
    )
    @action(detail=True, methods=['post'], permission_classes=[IsCompanyCollector])
    def complete(self, request, pk=None):
        route = self.get_object()
        route.status = "completed"
        route.actual_end = timezone.now()
        route.update_completion_status()
        route.save()
        return Response(self.get_serializer(route).data)   


class RouteStopViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing stops within a route.
    - Collectors: start and complete stops.
    - Supervisors: skip or mark stops as failed.
    """

    queryset = RouteStop.objects.all()
    serializer_class = RouteStopSerializer

    # --- Basic CRUD endpoints ---
    @swagger_auto_schema(
        operation_summary="List all route stops",
        operation_description="Returns a list of all stops. Supervisors can view all stops in their company routes; collectors see their assigned stops.",
        tags=["RouteStops"]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Retrieve a route stop",
        operation_description="Returns detailed information about a single stop, including linked request details.",
        tags=["RouteStops"]
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Create a route stop",
        operation_description="Supervisor creates a new stop in a route. Typically links to an OnDemandRequest or ScheduledRequest.",
        tags=["RouteStops"]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Update a route stop",
        operation_description="Supervisor updates stop details (e.g., order, expected_minutes, notes).",
        tags=["RouteStops"]
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_summary="Update a route stop (partial)",
        operation_description=(
            "Supervisor updates stop details using PATCH. "
            "Only the provided fields will be updated. "
            "Typical use cases: changing stop order, adjusting expected_minutes, "
            "or adding notes."
        ),
        tags=["RouteStops"],
        request_body=RouteStopSerializer,
        responses={200: RouteStopSerializer}
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Delete a route stop",
        operation_description="Supervisor deletes a stop from a route. Typically used for draft or cancelled routes.",
        tags=["RouteStops"]
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    # --- Custom actions ---
    @swagger_auto_schema(
        operation_summary="Start a stop",
        operation_description="Collector marks the stop as in progress and sets actual_start timestamp.",
        tags=["RouteStops"]
    )
    @action(detail=True, methods=['post'], permission_classes=[IsCompanyCollector])
    def start(self, request, pk=None):
        stop = self.get_object()
        stop.status = "in_progress"
        stop.actual_start = timezone.now()
        stop.save()
        return Response(self.get_serializer(stop).data)

    @swagger_auto_schema(
        operation_summary="Complete a stop",
        operation_description="Collector marks the stop as completed and sets actual_end timestamp.",
        tags=["RouteStops"]
    )
    @action(detail=True, methods=['post'], permission_classes=[IsCompanyCollector])
    def complete(self, request, pk=None):
        """
        Collector completes a stop.
        - Marks stop as completed
        - Creates or updates a CollectionRecord with payment, photos, GPS, and waste data
        """
        stop = self.get_object()
        stop.status = "completed"
        stop.actual_end = timezone.now()
        stop.save()

        # Create or update CollectionRecord
        record, created = CollectionRecord.objects.get_or_create(route_stop=stop, defaults={
            "client": stop.ondemand_request.client if stop.ondemand_request else stop.scheduled_request.client,
            "collector": stop.route.collector,
            "route": stop.route,
            "collection_type": "on_demand" if stop.ondemand_request else "scheduled",
            "scheduled_date": stop.route.route_date,
            "collection_start": stop.actual_start,
            "collection_end": stop.actual_end,
            "status": "completed",
        })

        # Update with collector input
        serializer = CollectionRecordCreateSerializer(record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(status="completed", collected_at=timezone.now())

        return Response(CollectionRecordSerializer(record).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Skip a stop",
        operation_description="Supervisor marks the stop as skipped. Useful when a client is unavailable or request is cancelled.",
        tags=["RouteStops"]
    )
    @action(detail=True, methods=['post'], permission_classes=[IsSupervisor])
    def skip(self, request, pk=None):
        stop = self.get_object()
        stop.status = "skipped"
        stop.save()
        return Response(self.get_serializer(stop).data)

    @swagger_auto_schema(
        operation_summary="Fail a stop",
        operation_description="Supervisor marks the stop as failed. Useful when a collection attempt was unsuccessful.",
        tags=["RouteStops"]
    )
    @action(detail=True, methods=['post'], permission_classes=[IsSupervisor])
    def fail(self, request, pk=None):
        stop = self.get_object()
        stop.status = "failed"
        stop.save()
        return Response(self.get_serializer(stop).data)