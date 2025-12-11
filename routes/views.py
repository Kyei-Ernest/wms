from datetime import timezone
from collection_management.models import CollectionRecord
from collection_management.serializers import CollectionRecordListSerializer
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiResponse,
    OpenApiExample,
)

from accounts.permissions import IsCollector, IsSupervisor
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
    

    @extend_schema(
        summary="Start a route",
        description=(
            "Starts a specific route if it is currently in either 'assigned' or 'draft' status. "
            "This action sets the actual start time, moves the route into 'in_progress', "
            "and updates all stops from 'pending' to 'in_progress'.\n\n"
            "**Permissions:**\n"
            "- Only users allowed by `CanStartRoute` can start the route.\n"
            "- Typically: supervisor or the assigned collector."
        ),
        responses={
            200: OpenApiResponse(
                response=RouteSerializer,
                description="Route successfully started."
            ),
            400: OpenApiResponse(
                description="Invalid status transition. Route cannot be started."
            ),
            403: OpenApiResponse(
                description="Not authorized to start this route."
            ),
        },
        examples=[
            {
                "name": "Valid start request",
                "value": {},
                "request_only": True
            },
            {
                "name": "Successful start response",
                "value": {
                    "route_id": 101,
                    "status": "in_progress",
                    "actual_start": "2025-12-09T14:30:15Z",
                    "stops": [
                        {"stop_id": 1, "status": "in_progress"},
                        {"stop_id": 2, "status": "in_progress"}
                    ]
                },
                "response_only": True
            }
        ]
    )
    @action(
        detail=True,
        methods=['post'],
        url_path='start',
        permission_classes=[IsCollector]   
    )
    def start_route(self, request, pk=None):
        """
        Start a specific route.

        This endpoint allows authorized users to initiate a waste collection route.
        Once called, the following operations occur:

        1. **Validation**  
        - The route must currently be in either `"assigned"` or `"draft"` status.
        - Any other state (e.g., `in_progress`, `completed`, `cancelled`) will
            result in a `400 Bad Request`.

        2. **Route Updates**  
        - Sets `actual_start` to the current timestamp.
        - Changes the route status to `"in_progress"`.

        3. **Stop Updates**  
        - All stops with status `"pending"` are automatically updated to `"in_progress"`.

        **Permissions:**  
        This action uses a dedicated permission class (`CanStartRoute`), meaning it
        applies *only to this endpoint* and not the entire ViewSet.

        Returns the complete serialized route after updates.
        """
        route = self.get_object()

        # Validate status transition
        if route.status not in ["assigned", "draft"]:
            return Response(
                {"error": "Route cannot be started from the current status."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Perform state update
        route.actual_start = timezone.now()
        route.status = "in_progress"
        route.save(update_fields=["actual_start", "status"])

        # Update pending stops
        route.stops.filter(status="pending").update(status="in_progress")

        return Response(RouteSerializer(route).data, status=status.HTTP_200_OK)


    @extend_schema(
    summary="Automatically close a completed route",
    description=(
        "Supervisor-only endpoint. This action finalizes a route **only if all stops "
        "on the route have already been completed**. The system performs several "
        "automatic tasks:\n\n"
        "1. Validates that no stop is still in `pending` or `in_progress`.\n"
        "2. Marks the route as `completed` and records the actual end time.\n"
        "3. Calculates incentives for the collector using a base rate per stop and a "
        "distance-based bonus.\n"
        "4. Updates the collector’s incentive balance.\n"
        "5. Returns a detailed summary including distance, total stops, completion "
        "time, and incentive awarded."
    ),
    request=None,
    responses={
        200: OpenApiResponse(
            description="Route closed successfully with auto-calculated metrics.",
            examples=[
                OpenApiExample(
                    "Successful auto-close",
                    value={
                        "message": "Route auto-closed",
                        "summary": {
                            "route_id": 101,
                            "distance_km": 12.4,
                            "stops_completed": 18,
                            "time_spent_minutes": 95.0,
                            "incentive_awarded": 220.5
                        },
                    },
                )
            ],
        ),
        400: OpenApiResponse(
            description="Cannot close the route because one or more stops are unfinished.",
            examples=[
                OpenApiExample(
                    "Unfinished stops error",
                    value={"error": "Route cannot be closed until all stops are completed."},
                )
            ],
        ),
    },
    )
    @action(
        detail=True,
        methods=['post'],
        url_path='auto-close',
        #permission_classes=[IsSupervisor]  
    )
    def auto_close(self, request, pk=None):
        """
        Automatically finalizes a route after all stops are completed.

        This endpoint ensures all route stops have reached a `completed` state
        before closing the route. It then marks the route as completed, sets the
        actual end time, calculates incentives for the collector using a combination
        of per-stop and distance-based bonuses, updates the collector’s incentive
        balance, and returns a detailed route summary.
        """
        route = self.get_object()

        # 1. Ensure all stops are completed
        if route.stops.filter(status__in=["pending", "in_progress"]).exists():
            return Response(
                {"error": "Route cannot be closed until all stops are completed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Update route status
        route.status = "completed"
        route.actual_end = timezone.now()
        route.save(update_fields=["status", "actual_end"])

        # 3. Calculate incentives
        completed_stops = route.stops.filter(status="completed").count()
        base_rate = 10
        bonus_rate = 0.5
        incentive = (completed_stops * base_rate) + (route.total_distance_km * bonus_rate)

        collector = route.collector
        collector.incentive_balance = getattr(collector, "incentive_balance", 0) + incentive
        collector.save(update_fields=["incentive_balance"])

        # 4. Summary
        summary = {
            "route_id": route.route_id,
            "distance_km": route.total_distance_km,
            "stops_completed": completed_stops,
            "time_spent_minutes": (
                (route.actual_end - route.actual_start).total_seconds() / 60
                if route.actual_start else None
            ),
            "incentive_awarded": incentive,
        }

        return Response(
            {"message": "Route auto-closed", "summary": summary},
            status=status.HTTP_200_OK
        )


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



    @extend_schema(
        summary="Complete a route stop",
        description=(
            "Marks a specific stop as completed and automatically generates a collection record. "
            "This action can only be performed when the stop is currently in the `in_progress` state.\n\n"
            "**What this endpoint does:**\n"
            "1. Validates the stop state.\n"
            "2. Marks the stop as `completed` and records the actual end time.\n"
            "3. Creates a `CollectionRecord` for tracking the waste collection event.\n"
            "4. Updates the parent route’s completion percentage.\n"
            "5. Updates collector performance stats.\n"
            "6. Optionally recalculates the client’s segregation compliance score.\n\n"
            "**Permissions:**\n"
            "Use a custom permission class if only collectors should complete stops.\n\n"
            "**Typical Use Case:**\n"
            "Collectors call this endpoint after finishing service at a client location, "
            "submitting details like bag count, bin size, waste type, and segregation score."
        ),
        request={
            "application/json": OpenApiExample(
                "Complete stop payload",
                value={
                    "bag_count": 3,
                    "bin_size_liters": 120,
                    "waste_type": "mixed",
                    "segregation_score": 75
                },
                request_only=True,
            )
        },
        responses={
            201: OpenApiResponse(
                response=CollectionRecordListSerializer,
                description="Stop completed and collection record created."
            ),
            400: OpenApiResponse(description="Stop is not in progress."),
            403: OpenApiResponse(description="Permission denied."),
        },
        examples=[
            OpenApiExample(
                "Successful completion response",
                value={
                    "record_id": 501,
                    "client": 2001,
                    "collector": 45,
                    "route": 101,
                    "collection_type": "regular",
                    "scheduled_date": "2025-12-09",
                    "collected_at": "2025-12-09T16:24:55Z",
                    "bag_count": 3,
                    "bin_size_liters": 120,
                    "waste_type": "mixed",
                    "segregation_score": 75,
                    "status": "completed"
                },
                response_only=True,
            )
        ]
    )
    @action(
        detail=True,
        methods=['post'],
        url_path='complete',
        permission_classes=[IsCollector]  
    )
    def complete_stop(self, request, pk=None):
        """
        Complete a waste collection stop.

        This endpoint finalizes a specific stop within a route and logs a full
        collection record. It is typically called by the collector after servicing
        a client's location.

        **Workflow executed by this endpoint:**

        1. **Status Validation**  
        Ensures the stop is currently in the `in_progress` state.  
        Stops in any other state (`pending`, `completed`, `cancelled`) will
        return a `400 Bad Request`.

        2. **Stop Update**  
        - Sets the stop status to `completed`.  
        - Records the `actual_end` timestamp.

        3. **Collection Record Creation**  
        Captures essential waste collection details such as:  
        - bag count  
        - bin size  
        - waste type  
        - collector  
        - route  
        - segregation score  
        These records are used for analytics and client/collector evaluation.

        4. **Route Progress Update**  
        Recalculates the route's completion percentage based on the number of
        completed stops.

        5. **Collector Stats Update**  
        Increments long-term performance metrics such as total collections.

        6. **Client Segregation Compliance**  
        If provided, updates the client's segregation compliance percentage using
        a rolling average.

        **Returns:**  
        A serialized `CollectionRecord` representing the completed collection event,
        along with all associated details.

        **Response Status:**  
        - `201 Created` on success  
        - `400` if the stop is not in progress  
        - `403` if permissions are applied and user is unauthorized
        """
        stop = self.get_object()
        route = stop.route
        collector = route.collector
        client = stop.client

        if stop.status != "in_progress":
            return Response(
                {"error": "Stop must be in progress to complete."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Update stop status
        stop.status = "completed"
        stop.actual_end = timezone.now()
        stop.save(update_fields=["status", "actual_end"])

        # 2. Create CollectionRecord
        record = CollectionRecord.objects.create(
            client=client,
            collector=collector,
            route=route,
            collection_type="regular",
            scheduled_date=route.route_date,
            collected_at=timezone.now(),
            bag_count=request.data.get("bag_count", 0),
            bin_size_liters=request.data.get("bin_size_liters", 0),
            waste_type=request.data.get("waste_type", "mixed"),
            status="completed",
            segregation_score=request.data.get("segregation_score", None),
        )

        # 3. Update route completion percent
        total_stops = route.stops.count()
        completed_stops = route.stops.filter(status="completed").count()
        route.completion_percent = round((completed_stops / total_stops) * 100, 2)
        route.save(update_fields=["completion_percent"])

        # 4. Update collector stats
        collector.total_collections = getattr(collector, "total_collections", 0) + 1
        collector.save(update_fields=["total_collections"])

        # 5. Update client segregation compliance
        if record.segregation_score is not None:
            client.segregation_compliance_percent = (
                (client.segregation_compliance_percent + record.segregation_score) / 2
            )
            client.save(update_fields=["segregation_compliance_percent"])

        return Response(
            CollectionRecordListSerializer(record).data,
            status=status.HTTP_201_CREATED
        )
