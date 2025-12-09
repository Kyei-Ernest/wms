from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiResponse,
    OpenApiExample,
)

from accounts.permissions import IsSupervisor
from .models import Route, RouteStop
from .serializers import (
    RouteSerializer,
    RouteCreateSerializer,
    RouteStopSerializer,
    RouteStatusUpdateSerializer,
)

@extend_schema_view(
    list=extend_schema(
        summary="List all routes",
        description="Retrieve a paginated list of all routes with nested stops included.",
        responses={200: RouteSerializer},
    ),
    retrieve=extend_schema(
        summary="Retrieve a route",
        description="Get full details of a single route, including stops and analytics.",
        responses={200: RouteSerializer},
    ),
)
class RouteViewSet(viewsets.ModelViewSet):
    """
    ViewSet responsible for managing waste collection routes.

    This class groups all route-related endpoints, including:
    - Listing routes
    - Retrieving individual routes
    - Creating new routes (with or without custom stop input)
    - Updating route status

    Although this is a ViewSet, each method contains its own endpoint-specific
    docstring, similar to APIView, for clarity and frontend developer guidance.
    """

    queryset = Route.objects.all().select_related(
        'company', 'zone', 'supervisor', 'collector'
    ).prefetch_related('stops')
    permission_classes = [IsSupervisor]

    def get_serializer_class(self):
        if self.action == 'create':
            return RouteCreateSerializer
        elif self.action == 'update_status':
            return RouteStatusUpdateSerializer
        return RouteSerializer

    # --------------------------
    # LIST ENDPOINT
    # --------------------------
    def list(self, request, *args, **kwargs):
        """
        list of all routes

        Retrieve a paginated list of all routes.
        
        **What this returns**
        - Basic route metadata (company, supervisor, collector, zone)
        - Computed analytics (distance, duration, completion percentage)
        - Nested stops for each route
        - Filtering and pagination handled by DRF

        **Frontend Usage**
        - Use this for dashboard displays
        - Good for showing supervisor route overviews
        """
        return super().list(request, *args, **kwargs)

    # --------------------------
    # RETRIEVE ENDPOINT
    # --------------------------
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a single route.

        Retrieve a single route by its ID.

        **What this returns**
        - Full route details
        - Ordered list of stops
        - Zone, collector, and supervisor info
        - Route analytics (completion %, distance, estimated time)

        **Frontend Usage**
        - Use for route detail screens
        - Needed to render full stop-by-stop maps or collector assignments
        """
        return super().retrieve(request, *args, **kwargs)

    # --------------------------
    # CREATE ENDPOINT
    # --------------------------
    @extend_schema(
        summary="Create a new route",
        description=(
            "Supervisor-only endpoint. Creates a new route. "
            "If no stops are provided, stops are automatically generated "
            "from clients inside the zone polygon."
        ),
        request=RouteCreateSerializer,
        responses={201: RouteSerializer},
    )
    def create(self, request, *args, **kwargs):
        """
        Create a new route

        Create a new route. This endpoint supports two behaviors:

        **1. Manual Stop Input (Supervisor specifies stops)**
        - Provided stops are validated for:
          - geographic correctness (inside zone)
          - correct ordering
          - valid client association
        - Returned route includes the stops exactly as provided.

        **2. Automatic Stop Generation**
        - If no stops are submitted:
            - System finds all clients whose coordinates lie inside the zone polygon.
            - Generates stops automatically with:
              - System-assigned order
              - Lat/Lon from the client
              - Initial "pending" status
            - Computes:
              - total route distance
              - estimated duration

        **Frontend Usage**
        - Use for assigning a collector to a set of clients.
        - Use for generating routes based on zone boundaries.

        **Returns**
        `201 Created` with a full serialized route including final stops.
        """
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        route = serializer.save()
        return Response(RouteSerializer(route).data, status=status.HTTP_201_CREATED)

    # --------------------------
    # CUSTOM ACTION: STATUS UPDATE
    # --------------------------
    @extend_schema(
        summary="Update route status",
        description=(
            "Supervisor-only endpoint. Allows status transitions with validation rules."
        ),
        request=RouteStatusUpdateSerializer,
        responses={
            200: OpenApiResponse(response=RouteSerializer),
            400: OpenApiResponse(description="Invalid status transition"),
        },
    )
    @action(detail=True, methods=['patch'], url_path='update-status')
    def update_status(self, request, pk=None):
        """
        Update the route's status

        Update the route's status following strict transition rules:

        **Allowed transitions**
        - draft → assigned, cancelled
        - assigned → in_progress, cancelled
        - in_progress → completed, cancelled
        - completed → ❌ cannot change
        - cancelled → ❌ cannot change

        **Validation**
        - Invalid transitions return HTTP 400.
        - Serializer handles the business logic.

        **Frontend Usage**
        - Use for workflow progression (assign → start → complete).
        - UI should grey out invalid transitions to prevent user mistakes.

        **Returns**
        The updated route serialized using `RouteSerializer`.
        """
        route = self.get_object()
        serializer = RouteStatusUpdateSerializer(route, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(RouteSerializer(route).data)


@extend_schema_view(
    list=extend_schema(
        summary="List all route stops",
        description="Retrieve all stops across all routes with client location details.",
        responses={200: RouteStopSerializer},
    ),
    retrieve=extend_schema(
        summary="Retrieve a route stop",
        description="Get full details of a single stop, including client and location.",
        responses={200: RouteStopSerializer},
    ),
)
class RouteStopViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing individual route stops.
    
    This includes:
    - Listing all stops
    - Retrieving single stops
    - Adding new stops to a route

    Each method contains an APIView-style endpoint-specific docstring.
    """

    queryset = RouteStop.objects.all().select_related('route', 'client')
    serializer_class = RouteStopSerializer
    permission_classes = [IsSupervisor]

    # --------------------------
    # LIST ENDPOINT
    # --------------------------
    def list(self, request, *args, **kwargs):
        """
        List all the stops across the system

        Fetch all stops across the system.

        **What this returns**
        - Each stop's client
        - Coordinates
        - Order in route
        - Status
        - Parent route ID

        **Frontend Usage**
        - Admin tables
        - Debug screens
        - Supervisor analytics
        """
        return super().list(request, *args, **kwargs)

    # --------------------------
    # RETRIEVE ENDPOINT
    # --------------------------
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve detailed information about a specific route stop.

        Retrieve detailed information about a specific route stop.

        Includes:
        - client info
        - lat/lon coordinates
        - assigned route
        - stop order
        - expected minutes (optional)
        """
        return super().retrieve(request, *args, **kwargs)

    # --------------------------
    # CREATE ENDPOINT
    # --------------------------
    @extend_schema(
        summary="Create a new route stop",
        description=(
            "Supervisor-only endpoint. Creates a new stop tied to a route. "
            "Coordinates must fall inside the route’s zone polygon."
        ),
        request=RouteStopSerializer,
        responses={201: RouteStopSerializer},
    )
    def perform_create(self, serializer):
        """
        Create a new stop inside a route.


        Create a new stop inside a route.

        **Validation**
        - Serializer ensures coordinates lie inside the route's zone polygon.
        - Ensures that the client exists.
        - Ensures correct ordering (if enforced).

        **Frontend Usage**
        - Adding extra visits after route creation.
        - Manual insertion of emergency stops.

        **Returns**
        A serialized route stop with all validated fields.
        """
        serializer.save()
