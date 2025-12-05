from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.db import transaction

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Route, RouteStop
from .serializers import (
    RouteListSerializer,
    RouteDetailSerializer,
    RouteCreateSerializer,
    RouteUpdateSerializer,
    RouteStopSerializer,
    RouteStopCreateSerializer,
    RouteStopUpdateSerializer,
)


class RouteViewSet(viewsets.ModelViewSet):
    """
    Manage waste collection routes.

    Key Features:
    - Create routes with optional stop lists
    - Retrieve detailed route information including stops
    - Update route metadata, status, and performance fields
    - Start and complete real-time route execution
    - Fetch all stops belonging to a route
    """

    queryset = Route.objects.all().select_related(
        'company', 'zone', 'supervisor__user', 'collector__user'
    ).prefetch_related('stops')

    def get_serializer_class(self):
        if self.action == 'list':
            return RouteListSerializer
        if self.action == 'retrieve':
            return RouteDetailSerializer
        if self.action == 'create':
            return RouteCreateSerializer
        if self.action in ['update', 'partial_update']:
            return RouteUpdateSerializer
        return RouteDetailSerializer

    # -------------------------------------------
    # LIST ROUTES
    # -------------------------------------------
    @swagger_auto_schema(
        operation_summary="List all routes",
        operation_description=(
            "Returns a list of all waste collection routes in the system. "
            "Includes basic route metadata such as date, supervisor, collector, status, "
            "and summary statistics."
        ),
        responses={200: RouteListSerializer(many=True)},
        tags=["Routes"]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    # -------------------------------------------
    # CREATE ROUTE
    # -------------------------------------------
    @swagger_auto_schema(
        operation_summary="Create a new route",
        operation_description=(
            "Creates a new waste collection route. "
            "You may optionally include a list of stops during creation. "
            "The route will be initialized with 'draft' status."
        ),
        request_body=RouteCreateSerializer,
        responses={201: RouteDetailSerializer},
        tags=["Routes"]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    # -------------------------------------------
    # RETRIEVE ROUTE DETAILS
    # -------------------------------------------
    @swagger_auto_schema(
        operation_summary="Retrieve route details",
        operation_description=(
            "Returns full details of a route including its assigned collector, "
            "supervisor, zone, company, metadata, and all associated stops."
        ),
        responses={200: RouteDetailSerializer},
        tags=["Routes"]
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    # -------------------------------------------
    # UPDATE ROUTE
    # -------------------------------------------
    @swagger_auto_schema(
        operation_summary="Update a route",
        operation_description=(
            "Updates route metadata such as timings, status, assigned personnel, "
            "or additional notes. Does not modify associated stops."
        ),
        request_body=RouteUpdateSerializer,
        responses={200: RouteDetailSerializer},
        tags=["Routes"]
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    # -------------------------------------------
    # START ROUTE
    # -------------------------------------------
    @swagger_auto_schema(
        method='post',
        operation_summary="Start a route",
        operation_description=(
            "Marks the route as 'in_progress' and stores the actual starting timestamp. "
            "Used when the collector begins the route in real-time."
        ),
        responses={200: openapi.Response("Route started successfully")},
        tags=["Routes"]
    )
    @action(detail=True, methods=['post'])
    def start_route(self, request, pk=None):
        route = self.get_object()
        route.status = 'in_progress'
        route.actual_start = timezone.now()
        route.save()
        return Response({"message": "Route started"}, status=200)

    # -------------------------------------------
    # END ROUTE
    # -------------------------------------------
    @swagger_auto_schema(
        method='post',
        operation_summary="Complete a route",
        operation_description=(
            "Marks a route as 'completed' and sets the actual end timestamp. "
            "Useful when a collector finishes all route tasks."
        ),
        responses={200: openapi.Response("Route completed successfully")},
        tags=["Routes"]
    )
    @action(detail=True, methods=['post'])
    def end_route(self, request, pk=None):
        route = self.get_object()
        route.status = 'completed'
        route.actual_end = timezone.now()
        route.save()
        return Response({"message": "Route completed"}, status=200)

    # -------------------------------------------
    # LIST ALL STOPS FOR ROUTE
    # -------------------------------------------
    @swagger_auto_schema(
        method='get',
        operation_summary="List all stops in a route",
        operation_description=(
            "Returns all stops associated with a specific route in their defined order. "
            "Includes coordinates, expected duration, and status for each stop."
        ),
        responses={200: RouteStopSerializer(many=True)},
        tags=["Routes"]
    )
    @action(detail=True, methods=['get'])
    def stops(self, request, pk=None):
        route = self.get_object()
        serializer = RouteStopSerializer(route.stops.all(), many=True)
        return Response(serializer.data, status=200)


class RouteStopViewSet(viewsets.ModelViewSet):
    """
    Manage stops within routes.

    Key Features:
    - Create stops with coordinates and timing
    - Update stop information
    - Reorder stops within a route
    - Mark a stop as completed in real-time
    """

    queryset = RouteStop.objects.all().select_related('route', 'client__user')

    def get_serializer_class(self):
        if self.action == 'create':
            return RouteStopCreateSerializer
        if self.action in ['update', 'partial_update']:
            return RouteStopUpdateSerializer
        return RouteStopSerializer

    # -------------------------------------------
    # CREATE STOP
    # -------------------------------------------
    @swagger_auto_schema(
        operation_summary="Create a route stop",
        operation_description=(
            "Creates a new stop assigned to a specific route. "
            "Includes GPS coordinates, expected duration, and client details."
        ),
        request_body=RouteStopCreateSerializer,
        responses={201: RouteStopSerializer},
        tags=["Route Stops"]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    # -------------------------------------------
    # UPDATE STOP
    # -------------------------------------------
    @swagger_auto_schema(
        operation_summary="Update a stop",
        operation_description=(
            "Updates metadata of a stop such as its coordinates, expected duration, "
            "or notes. Useful for route optimization."
        ),
        request_body=RouteStopUpdateSerializer,
        responses={200: RouteStopSerializer},
        tags=["Route Stops"]
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    # -------------------------------------------
    # REORDER STOPS
    # -------------------------------------------
    reorder_schema = openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'route_id': openapi.Schema(type=openapi.TYPE_INTEGER),
            'order': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'stop_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'order': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                )
            )
        }
    )

    @swagger_auto_schema(
        method='post',
        operation_summary="Reorder route stops",
        operation_description=(
            "Changes the order of multiple stops within a route. "
            "Takes a list of stop IDs with their new order positions."
        ),
        request_body=reorder_schema,
        responses={200: openapi.Response("Stop order updated successfully")},
        tags=["Route Stops"]
    )
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def reorder(self, request):
        route_id = request.data.get("route_id")
        order_list = request.data.get("order")

        if not route_id or not order_list:
            return Response(
                {"error": "route_id and order list required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        for item in order_list:
            stop = RouteStop.objects.get(stop_id=item['stop_id'], route_id=route_id)
            stop.order = item['order']
            stop.save()

        return Response({"message": "Stop order updated"}, status=200)

    # -------------------------------------------
    # COMPLETE STOP
    # -------------------------------------------
    @swagger_auto_schema(
        method='post',
        operation_summary="Mark stop as completed",
        operation_description=(
            "Marks a stop as completed and sets the actual completion timestamp. "
            "Used by collectors during real-time waste pickup."
        ),
        responses={200: openapi.Response("Stop marked completed")},
        tags=["Route Stops"]
    )
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        stop = self.get_object()
        stop.status = 'completed'
        stop.actual_end = timezone.now()
        stop.save()
        return Response({"message": "Stop completed"}, status=200)
