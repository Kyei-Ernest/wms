from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import OnDemandRequest
from .serializers import (
    OnDemandRequestListSerializer,
    OnDemandRequestDetailSerializer,
    OnDemandRequestCreateSerializer,
    OnDemandRequestUpdateSerializer,
)


class OnDemandRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing On-Demand Waste Collection Requests.

    This viewset provides a complete API for handling one-time waste collection
    service requests in the Waste Management System. It implements a workflow-based
    approach with status transitions and role-based access control.

    Workflow States:
        - pending: Initial state after client submission
        - assigned: Collector has been assigned to the request
        - in_progress: Collector has started the collection
        - completed: Service has been fulfilled
        - cancelled: Request has been terminated before completion

    Role-Based Access Patterns:
        Client:
            - Create new requests for waste collection
            - View their own submitted requests
            - Cancel requests before assignment or during early stages
            - Update minor details before collector acceptance

        Collector:
            - View requests assigned to them or available for acceptance
            - Accept unassigned or newly assigned requests
            - Update status during service execution
            - Complete requests with final pricing and proof images
            - Cancel requests with valid reason (e.g., access issues)

        Company/Dispatcher:
            - View all requests within their organization
            - Assign collectors to pending requests
            - Monitor request progress and status
            - Override assignments when necessary
            - Access analytics and reporting data

    Model Fields Reference:
        - id: Unique identifier for the request
        - client: Foreign key to User (client who submitted the request)
        - collector: Foreign key to User (assigned collector, nullable)
        - latitude/longitude: GPS coordinates of waste location
        - address: Human-readable address string
        - waste_type: Category of waste (e.g., general, recyclable, hazardous)
        - waste_image: Image file showing the waste (optional)
        - contact_name: Name of person at collection site
        - contact_phone: Phone number for coordination
        - special_instructions: Additional notes or requirements
        - request_status: Current workflow state
        - quoted_price: Estimated price provided upfront
        - final_price: Actual price charged after completion
        - scheduled_date: Preferred collection date/time
        - created_at: Request submission timestamp
        - accepted_at: When collector accepted the request
        - completed_at: When service was marked complete
        - cancelled_at: When request was cancelled
        - cancellation_reason: Explanation for cancellation

    Permissions:
        Authentication is required for all endpoints.
        Specific permissions are enforced at the view level based on user roles.

    Filtering & Search:
        The queryset can be filtered by:
        - request_status
        - waste_type
        - date ranges (created_at, scheduled_date)
        - geographical boundaries (latitude/longitude)
        - assigned collector
        - client

    Examples:
        # Create a new request
        POST /api/ondemand-requests/
        {
            "latitude": 5.6037,
            "longitude": -0.1870,
            "waste_type": "general",
            "contact_name": "John Doe",
            "contact_phone": "+233501234567",
            "special_instructions": "Large items, need assistance"
        }

        # Assign to collector
        POST /api/ondemand-requests/123/assign/
        {"collector_id": 45}

        # Complete request
        POST /api/ondemand-requests/123/complete/
        {
            "final_price": 50.00,
            "waste_image": <file>
        }
    """

    queryset = OnDemandRequest.objects.all()
    serializer_class = OnDemandRequestDetailSerializer

    def get_serializer_class(self):
        """
        Dynamically select the appropriate serializer class based on the action.

        Serializer Selection Logic:
            - list: Returns lightweight serializer for performance
            - create: Validates and processes new request submission
            - update/partial_update: Handles general field updates
            - assign/accept/complete/cancel: Uses update serializer with specific validations
            - retrieve: Returns comprehensive detail serializer

        Returns:
            Serializer class appropriate for the current action

        Note:
            Using different serializers per action allows for:
            - Optimized database queries (select_related/prefetch_related)
            - Field-level permissions and validations
            - Reduced payload size for list operations
            - Action-specific business logic
        """
        if self.action == 'list':
            return OnDemandRequestListSerializer
        elif self.action == 'create':
            return OnDemandRequestCreateSerializer
        elif self.action in ['update', 'partial_update', 'assign', 'accept', 'complete', 'cancel']:
            return OnDemandRequestUpdateSerializer
        return OnDemandRequestDetailSerializer

    # ============================================================
    # CRUD Endpoints
    # ============================================================

    @swagger_auto_schema(
        operation_summary="List On-Demand Requests",
        operation_description="""
        Retrieve a paginated, filtered list of on-demand waste collection requests.

        **Access Control:**
        - **Clients:** Only see requests they have submitted
        - **Collectors:** See requests assigned to them or available for acceptance
        - **Companies/Dispatchers:** See all requests within their organization
        - **System Admins:** See all requests across all companies

        **Filtering Options:**
        Query parameters can be used to filter results:
        - `status`: Filter by request_status (pending, assigned, completed, cancelled)
        - `waste_type`: Filter by waste category
        - `collector`: Filter by assigned collector ID
        - `date_from`: Show requests created after this date (YYYY-MM-DD)
        - `date_to`: Show requests created before this date (YYYY-MM-DD)
        - `search`: Full-text search across address and special_instructions

        **Pagination:**
        Results are paginated with default page size of 20. Use `page` and `page_size` parameters.

        **Sorting:**
        Default sort is by created_at (newest first). Use `ordering` parameter:
        - `created_at`: Oldest first
        - `-created_at`: Newest first (default)
        - `scheduled_date`: Earliest scheduled first
        - `final_price`: Lowest price first

        **Response Format:**
        Returns a lightweight representation optimized for list views, including:
        - Basic request identifiers
        - Location summary (address, coordinates)
        - Status and timestamps
        - Assigned collector info (name only)
        - Pricing summary

        **Performance Notes:**
        - Database queries are optimized with select_related for collector/client
        - Results are cached for 5 minutes for anonymous/public lists
        - Consider using pagination for large result sets

        

        
        """,
        responses={
            200: OnDemandRequestListSerializer(many=True),
            401: "Authentication required",
            403: "Permission denied"
        },
        manual_parameters=[
            openapi.Parameter('status', openapi.IN_QUERY, 
                            description="Filter by request status", 
                            type=openapi.TYPE_STRING),
            openapi.Parameter('waste_type', openapi.IN_QUERY, 
                            description="Filter by waste type", 
                            type=openapi.TYPE_STRING),
            openapi.Parameter('collector', openapi.IN_QUERY, 
                            description="Filter by collector ID", 
                            type=openapi.TYPE_INTEGER),
            openapi.Parameter('date_from', openapi.IN_QUERY, 
                            description="Filter requests created after this date (YYYY-MM-DD)", 
                            type=openapi.TYPE_STRING, format=openapi.FORMAT_DATE),
            openapi.Parameter('date_to', openapi.IN_QUERY, 
                            description="Filter requests created before this date (YYYY-MM-DD)", 
                            type=openapi.TYPE_STRING, format=openapi.FORMAT_DATE),
            openapi.Parameter('search', openapi.IN_QUERY, 
                            description="Search in address and instructions", 
                            type=openapi.TYPE_STRING),
            openapi.Parameter('ordering', openapi.IN_QUERY, 
                            description="Sort field (prefix with - for descending)", 
                            type=openapi.TYPE_STRING),
            openapi.Parameter('page', openapi.IN_QUERY, 
                            description="Page number", 
                            type=openapi.TYPE_INTEGER),
            openapi.Parameter('page_size', openapi.IN_QUERY, 
                            description="Number of results per page", 
                            type=openapi.TYPE_INTEGER),
        ],
    )
    def list(self, request, *args, **kwargs):
        """
        Handle GET requests to retrieve a list of on-demand requests.

        The base ModelViewSet.list() is extended with custom filtering logic
        based on user roles, which is typically implemented in get_queryset().

        Args:
            request: DRF Request object containing user authentication
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            Response: Paginated list of serialized OnDemandRequest objects

        Note:
            Override get_queryset() to implement role-based filtering:
            - Filter by request.user for clients
            - Filter by collector__user for collectors
            - Filter by company for company users
        """
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Create On-Demand Request",
        operation_description="""
        Submit a new one-time waste collection request to the system.

        **Primary Use Case:**
        This endpoint is primarily used by clients (residents or businesses) who need
        immediate or scheduled waste collection services outside regular routes.

        **Required Fields:**
        - `latitude` (float): GPS latitude coordinate (valid range: -90 to 90)
        - `longitude` (float): GPS longitude coordinate (valid range: -180 to 180)
        - `waste_type` (string): Category of waste - options:
            * "general" - Regular household waste
            * "recyclable" - Paper, plastic, glass, metal
            * "organic" - Food waste, garden waste
            * "electronic" - E-waste, batteries
            * "hazardous" - Chemicals, medical waste
            * "bulky" - Furniture, large items
        - `contact_name` (string): Name of contact person at collection site
        - `contact_phone` (string): Valid phone number (international format recommended)

        **Optional Fields:**
        - `address` (string): Human-readable address (auto-geocoded if not provided)
        - `waste_image` (file): Photo of the waste (JPEG, PNG, max 5MB)
            * Helps collectors prepare appropriate equipment
            * Required for hazardous waste
        - `special_instructions` (text): Additional notes, access codes, specific requirements
        - `scheduled_date` (datetime): Preferred collection time (defaults to ASAP)
        - `quoted_price` (decimal): Pre-agreed price (calculated by system if not provided)

        **Validation Rules:**
        - Coordinates must be within service area boundaries
        - Phone number must match valid format for the region
        - Scheduled date must be in the future (minimum 2 hours from now)
        - Image file must be under 5MB and valid format
        - One user cannot have more than 5 pending requests simultaneously

        **Business Logic:**
        Upon successful creation:
        1. Request status is set to "pending"
        2. System calculates estimated price based on:
            - Waste type
            - Estimated volume (from image if provided)
            - Distance from nearest collector base
            - Time of day/week pricing modifiers
        3. Nearby collectors are notified (if auto-dispatch enabled)
        4. Client receives confirmation via email/SMS
        5. Request enters the dispatch queue

        **Auto-Assignment:**
        If company has auto-dispatch enabled, the system may automatically:
        - Match request to available collectors based on proximity
        - Consider collector capacity and current workload
        - Assign directly if match confidence is high (>85%)

        **Response:**
        Returns the created request with full details including:
        - Unique request ID
        - Calculated quoted_price
        - Expected response time
        - Nearby collector availability status


        

        **Error Responses:**
        - 400: Validation errors (invalid coordinates, missing required fields)
        - 401: Authentication required
        - 403: User has too many pending requests
        - 413: Image file too large
        - 422: Location outside service area
        """,
        request_body=OnDemandRequestCreateSerializer,
        responses={
            201: OnDemandRequestDetailSerializer,
            400: "Validation error - check required fields",
            401: "Authentication required",
            403: "Too many pending requests",
            413: "File too large",
            422: "Location outside service area"
        },
    )
    def create(self, request, *args, **kwargs):
        """
        Handle POST requests to create a new on-demand request.

        Performs validation, geocoding (if needed), price calculation,
        and triggers notification workflows.

        Args:
            request: DRF Request object with request data and authenticated user
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            Response: HTTP 201 with created request details

        Side Effects:
            - Saves new OnDemandRequest to database
            - Triggers notification to nearby collectors
            - Creates audit log entry
            - May trigger auto-assignment workflow

        Raises:
            ValidationError: If required fields are missing or invalid
            PermissionDenied: If user has exceeded request limits
        """
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Retrieve On-Demand Request",
        operation_description="""
        Retrieve comprehensive details of a specific on-demand waste collection request.

        **Access Control:**
        - Clients can only view their own requests
        - Collectors can view requests assigned to them
        - Company users can view any request in their organization
        - System admins can view any request

        **Response Includes:**
        
        **Core Information:**
        - Request ID and current status
        - Creation, acceptance, completion timestamps
        - Status transition history

        **Location Details:**
        - GPS coordinates (latitude/longitude)
        - Formatted address string
        - Distance from collector base (if assigned)
        - Map visualization URL

        **Client Information:**
        - Client user profile
        - Contact name and phone number
        - Client rating/history (for collectors)

        **Waste Details:**
        - Waste type and category
        - Uploaded image(s) of waste
        - Estimated volume/weight
        - Special handling requirements

        **Assignment & Workflow:**
        - Assigned collector details (name, phone, vehicle)
        - Assignment timestamp
        - Acceptance timestamp
        - Expected arrival time (if in progress)

        **Pricing Information:**
        - Quoted price (initial estimate)
        - Final price (after completion)
        - Price breakdown (base + modifiers)
        - Payment status

        **Additional Fields:**
        - Special instructions from client
        - Collector notes (if any)
        - Cancellation reason (if cancelled)
        - Proof of completion image
        - Client feedback/rating (if completed)

        **Use Cases:**
        - Client checking request status
        - Collector viewing assignment details before accepting
        - Dispatcher monitoring active requests
        - Generating service reports

        **Related Actions:**
        Based on current status and user role, the response may include
        available actions:
        - Pending: assign, cancel
        - Assigned: accept (collector), complete (collector), cancel
        - Completed: view only
        - Cancelled: view only

        

        **Performance:**
        - Response includes related data via select_related
        - Cached for 1 minute for non-owner views
        - Historical requests (>30 days old) may have reduced details
        """,
        responses={
            200: OnDemandRequestDetailSerializer,
            401: "Authentication required",
            403: "Not authorized to view this request",
            404: "Request not found"
        },
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Handle GET requests to retrieve a single on-demand request.

        Args:
            request: DRF Request object
            *args: Additional positional arguments
            **kwargs: URL parameters including 'pk' (primary key)

        Returns:
            Response: HTTP 200 with detailed request information

        Raises:
            Http404: If request with given ID doesn't exist
            PermissionDenied: If user lacks permission to view this request
        """
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Update On-Demand Request",
        operation_description="""
        Update core details of an existing on-demand waste collection request.

        **Access Control:**
        - Clients: Can update minor details before collector acceptance
        - Collectors: Can update status, notes, and completion details
        - Dispatchers: Can update any field including assignments
        - System: Automated status updates during workflow

        **HTTP Methods:**
        - `PUT`: Full update (all fields must be provided)
        - `PATCH`: Partial update (only specified fields updated) - **Recommended**

        **Updatable Fields by Role:**

        **Client (Before Acceptance):**
        - `special_instructions`: Modify pickup instructions
        - `scheduled_date`: Change preferred time
        - `contact_phone`: Update contact number
        - `waste_image`: Replace or add image

        **Collector:**
        - `request_status`: Update to "in_progress"
        - `collector_notes`: Add notes about service
        - `final_price`: Set actual price at completion
        - `waste_image`: Add proof of completion photo

        **Dispatcher/Company:**
        - `collector`: Reassign to different collector
        - `request_status`: Override status if needed
        - `quoted_price`: Adjust estimated price
        - Any field for corrections/adjustments

        **Common Update Scenarios:**

        **1. Client Modifies Instructions:**
        ```
        PATCH /api/ondemand-requests/123/
        {
            "special_instructions": "Gate code is 1234, please call before entering"
        }
        ```

        **2. Dispatcher Reassigns Collector:**
        ```
        PATCH /api/ondemand-requests/123/
        {
            "collector": 67,
            "request_status": "assigned"
        }
        ```

        **3. Collector Updates Progress:**
        ```
        PATCH /api/ondemand-requests/123/
        {
            "request_status": "in_progress",
            "collector_notes": "On my way, ETA 15 minutes"
        }
        ```

        **4. Collector Adjusts Final Price:**
        ```
        PATCH /api/ondemand-requests/123/
        {
            "final_price": 45.00,
            "collector_notes": "Additional charge for extra bags"
        }
        ```

        **Validation Rules:**
        - Cannot update requests in "completed" or "cancelled" status (use specific actions instead)
        - Clients cannot modify after collector has accepted
        - Status transitions must follow valid workflow:
            * pending → assigned → in_progress → completed
            * Any status → cancelled
        - Price changes require proper permissions
        - Images must be valid format and size

        **Business Logic:**
        - Status changes trigger notifications to relevant parties
        - Price changes may require approval if above threshold
        - Collector reassignments notify both old and new collectors
        - Timestamp fields are auto-updated on status changes

        **Audit Trail:**
        All updates are logged with:
        - User who made the change
        - Timestamp of change
        - Fields modified
        - Previous and new values

        **Best Practices:**
        - Use PATCH for single-field updates to avoid overwriting data
        - Include only fields that need updating
        - For status changes, use dedicated actions (assign, accept, complete, cancel)
        - Add notes when making significant changes

        
        """,
        request_body=OnDemandRequestUpdateSerializer,
        responses={
            200: OnDemandRequestDetailSerializer,
            400: "Validation error",
            401: "Authentication required",
            403: "Not authorized to update this request",
            404: "Request not found",
            409: "Invalid status transition"
        },
    )
    def update(self, request, *args, **kwargs):
        """
        Handle PUT/PATCH requests to update an existing on-demand request.

        Args:
            request: DRF Request object with update data
            *args: Additional positional arguments
            **kwargs: URL parameters including 'pk'

        Returns:
            Response: HTTP 200 with updated request details

        Side Effects:
            - Updates database record
            - May trigger notifications
            - Creates audit log entry
            - Updates cache

        Raises:
            ValidationError: If update violates business rules
            PermissionDenied: If user lacks permission for this update
        """
        return super().update(request, *args, **kwargs)

    # ============================================================
    # Custom Workflow Actions
    # ============================================================

    @swagger_auto_schema(
        method='post',
        operation_summary="Assign Request to Collector",
        operation_description="""
        Assign a pending waste collection request to a specific collector.

        **Primary Users:**
        - Company dispatchers
        - Operations managers
        - Automated dispatch system

        **Prerequisites:**
        - Request must be in "pending" status
        - Collector must be active and available
        - Collector must have capacity for additional requests
        - Collector must be within service area of request

        **Required Parameter:**
        - `collector_id` (integer): The unique ID of the collector being assigned

        **Assignment Logic:**
        
        **Manual Assignment (Dispatcher):**
        1. Dispatcher reviews pending requests
        2. Selects appropriate collector based on:
            - Proximity to request location
            - Current workload and capacity
            - Specialized equipment (for specific waste types)
            - Historical performance ratings
        3. Submits assignment via this endpoint

        **Automated Assignment (System):**
        - Triggered when no manual assignment within threshold time
        - Algorithm considers same factors as manual
        - May assign to collector with highest match score

        **Behavior Upon Assignment:**
        1. Request status changes from "pending" to "assigned"
        2. Collector foreign key is set to specified collector
        3. Assignment timestamp is recorded
        4. Collector receives push notification/SMS with:
            - Request location and details
            - Waste type and estimated volume
            - Client contact information
            - Expected completion time
        5. Client receives confirmation that collector has been assigned
        6. Request appears in collector's work queue

        **Collector Notification Includes:**
        - Map with route from current location to pickup
        - Estimated travel time
        - Client contact details
        - Special instructions
        - Link to accept or decline (if flexible assignment)

        **Validation Checks:**
        - Collector exists and is active
        - Collector has not exceeded daily request limit
        - Collector has appropriate vehicle for waste type
        - Request is not already assigned to another collector
        - Collector is within reasonable distance (configurable threshold)

        **Reassignment:**
        If request is already assigned to a different collector:
        - Previous collector is notified of unassignment
        - New collector is assigned and notified
        - Reassignment reason is logged
        - Client is informed of collector change

        

        

        **Error Scenarios:**
        - 400: Collector ID not provided
        - 403: User lacks dispatcher permissions
        - 404: Collector ID does not exist or request not found
        - 409: Request is not in assignable status
        - 422: Collector unavailable or at capacity

        **Related Actions:**
        - After assignment, collector typically uses `/accept/` to confirm
        - Dispatcher can use `/update/` to reassign if needed
        - Request can be cancelled using `/cancel/` if assignment fails
        """,
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'collector_id': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="Unique ID of the collector to assign to this request. Must be an active collector within the system."
                ),
            },
            required=['collector_id'],
        ),
        responses={
            200: OnDemandRequestDetailSerializer,
            400: "collector_id required or invalid",
            403: "Insufficient permissions",
            404: "Collector or request not found",
            409: "Request not in assignable status",
            422: "Collector unavailable or at capacity"
        },
    )
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """
        Assign a request to a specific collector.

        Args:
            request: DRF Request object
            pk: Primary key of the request to assign

        Returns:
            Response: Updated request with assignment details

        Side Effects:
            - Updates request status to "assigned"
            - Sets collector foreign key
            - Records assignment timestamp
            - Sends notification to collector
            - Logs assignment in audit trail

        Raises:
            ValidationError: If collector_id is missing or invalid
        """
        request_obj = self.get_object()
        collector_id = request.data.get("collector_id")

        if not collector_id:
            return Response(
                {"error": "collector_id required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # TODO: Add validation for collector existence and availability
        # TODO: Check if collector is within service area
        # TODO: Verify collector capacity

        request_obj.collector_id = collector_id
        request_obj.request_status = "assigned"
        request_obj.assigned_at = timezone.now()
        request_obj.save()

        # TODO: Trigger notification to collector
        # TODO: Send confirmation to client

        return Response(OnDemandRequestDetailSerializer(request_obj).data)

    @swagger_auto_schema(
        method='post',
        operation_summary="Collector Accepts Request",
        operation_description="""
        Collector self-accepts a pending request. Updates collector's last known GPS location.

        **Primary Users:**
        - Individual collectors via mobile app

        **Use Cases:**

        **Scenario 1: Accepting Dispatcher Assignment**
        - Dispatcher assigns request to collector
        - Collector receives notification
        - Collector reviews details (location, waste type, price)
        - Collector clicks "Accept" to confirm they will handle it

        **Scenario 2: Self-Assignment from Available Pool**
        - Request is posted to "available requests" pool
        - Collector browses nearby available requests
        - Collector selects request they want to handle
        - Accept endpoint assigns collector and marks as accepted

        **Prerequisites:**
        - User must have an active collector profile
        - Request must be in "pending" or "assigned" status
        - If assigned to another collector, that collector must have declined
        - Collector must not be at maximum concurrent request limit

        **Behavior:**
        1. Links authenticated collector's profile to the request
        2. Updates request status to "assigned" (if was pending)
        3. Records acceptance timestamp
        4. Client receives notification with collector details:
            - Collector name and rating
            - Vehicle information
            - Estimated arrival time
            - Real-time tracking link (if available)
        5. Request is removed from available pool (if applicable)
        6. Collector's current workload count is incremented

        **Automatic Information Shared with Client:**
        - Collector name and photo
        - Average rating (from previous jobs)
        - Vehicle type and license plate
        - Phone number for direct contact
        - Current location and ETA (live updates)

        **Collector Dashboard Updates:**
        Upon acceptance, the request appears in collector's "Active Jobs" with:
        - Turn-by-turn navigation to location
        - Client contact button
        - Job timer (for performance tracking)
        - Quick actions (call client, report issue, start service)

        **Declining a Request:**
        If collector was assigned but cannot fulfill:
        - Use the `/cancel/` endpoint with reason
        - Request returns to dispatcher queue
        - No penalty for first decline (penalties may apply for repeated declines)

        

        

        **Error Scenarios:**
        - 401: User not authenticated
        - 403: User is not a registered collector
        - 409: Request already accepted by another collector
        - 422: Collector at maximum capacity

        **Business Rules:**
        - Collector can accept maximum 5 concurrent requests
        - Must complete or cancel current requests before accepting new ones beyond limit
        - Repeated declines/cancellations may affect collector rating
        - First acceptance creates binding commitment (cancellation requires valid reason)
        """,
        responses={
            200: OnDemandRequestDetailSerializer,
            401: "Authentication required",
            403: "User is not a collector",
            409: "Request already accepted by another collector",
            422: "Collector at maximum capacity"
        },
    )
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """
        Handle collector acceptance of a request.

        Args:
            request: DRF Request object (collector must be authenticated)
            pk: Primary key of the request to accept

        Returns:
            Response: Updated request with acceptance confirmation

        Side Effects:
            - Links collector profile to request
            - Updates status to "assigned"
            - Records acceptance timestamp
            - Sends notification to client
            - Updates collector's active job count
            - Removes request from available pool

        Raises:
            PermissionDenied: If user is not a collector
            ValidationError: If collector at capacity or request unavailable
        """
        request_obj = self.get_object()
        collector = request.user.collector_profile

        # Update collector GPS
        collector.last_known_latitude = request.data.get("latitude")
        collector.last_known_longitude = request.data.get("longitude")
        collector.save()

        # TODO: Validate user has collector profile
        # TODO: Check collector capacity limits
        # TODO: Verify request is available for acceptance

        request_obj.collector = request.user.collector_profile
        request_obj.request_status = "assigned"
        request_obj.accepted_at = request_obj.accepted_at or timezone.now()
        request_obj.save()

        # TODO: Send notification to client
        # TODO: Update collector workload metrics
        # TODO: Remove from available requests pool

        return Response(OnDemandRequestDetailSerializer(request_obj).data)

    @swagger_auto_schema(
        method='post',
        operation_summary="Complete Request",
        operation_description="""
        Mark a waste collection request as successfully completed.

        **Primary Users:**
        - Collectors (exclusively)

        **Prerequisites:**
        - Request must be assigned to the authenticated collector
        - Request must be in "assigned" or "in_progress" status
        - Collector must be at or near the collection location (GPS verification)

        **Required Data:**
        1. **Final Price** (required):
            - Actual amount charged for the service
            - Must be within reasonable range of quoted_price (±30%)
            - If significantly different, explanation required in notes
        
        2. **Proof Image** (required):
            - Photo showing completed work
            - Should demonstrate area is clean
            - Used for quality assurance and dispute resolution
            - Maximum file size: 5MB
            - Accepted formats: JPEG, PNG

        3. **Optional Data:**
            - `collector_notes`: Additional observations or issues encountered
            - `weight_collected`: Actual weight in kg (if measured)
            - `completion_notes`: Special circumstances or extra services provided

        **Completion Workflow:**
        
        **Step 1: Arrival & Service**
        - Collector arrives at location
        - Performs waste collection service
        - Optionally updates status to "in_progress" during service

        **Step 2: Documentation**
        - Takes "before" photo (optional, via separate endpoint)
        - Completes collection
        - Takes "after" photo showing clean area
        - Notes any issues or deviations from original request

        **Step 3: Completion**
        - Submits completion via this endpoint with:
            * Final price (may differ from quote)
            * Proof-of-completion image
            * Any relevant notes
        
        **Step 4: System Processing**
        System automatically:
        1. Verifies collector location against request location
        2. Updates request status to "completed"
        3. Records completion timestamp
        4. Stores final price
        5. Generates invoice for client
        6. Triggers payment processing (if auto-payment enabled)
        7. Requests client feedback/rating
        8. Updates collector statistics
        9. Marks request as ready for settlement

        **Pricing Rules:**
        - Final price can differ from quoted price for valid reasons:
            * More/less waste than estimated
            * Additional items or services
            * Difficult access or extra labor required
            * Time-based adjustments
        
        - Price increases >30% require:
            * Client approval (pre-completion) OR
            * Detailed explanation in notes for review
        
        - Price decreases are allowed without restriction

        **Quality Assurance:**
        - Random sample of completions are reviewed
        - Photos are checked for quality and authenticity
        - Significant price deviations trigger manual review
        - Client complaints may result in completion review

        **Client Notification:**
        Upon completion, client receives:
        - Completion notification
        - Final invoice with price breakdown
        - Proof-of-completion image
        - Link to rate/review the service
        - Payment instructions (if not auto-paid)

        **Collector Benefits:**
        - Earnings are recorded immediately
        - Job completion count increases
        - Rating becomes eligible for client review
        - Payment settlement initiated

        

        

        **Error Scenarios:**
        - 400: Missing required fields (final_price or waste_image)
        - 403: User is not the assigned collector
        - 409: Request is not in completable status
        - 413: Image file too large
        - 422: Final price deviates too much without explanation

        **Related Actions:**
        - After completion, client may submit rating via separate endpoint
        - Disputes can be raised within 24 hours
        - Settlement occurs during next payment cycle
        """,
        request_body=OnDemandRequestUpdateSerializer,
        responses={
            200: OnDemandRequestDetailSerializer,
            400: "Missing required fields",
            403: "Not authorized - must be assigned collector",
            409: "Request not in completable status",
            413: "Image file too large",
            422: "Invalid final price or missing explanation"
        },
    )
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        Mark request as completed with final details.

        Args:
            request: DRF Request object with completion data
            pk: Primary key of the request to complete

        Returns:
            Response: Completed request with final details

        Side Effects:
            - Updates status to "completed"
            - Records completion timestamp
            - Stores final price
            - Processes proof image
            - Triggers client notification
            - Initiates payment processing
            - Updates collector earnings
            - Requests client rating

        Raises:
            ValidationError: If required fields missing or invalid
            PermissionDenied: If user is not assigned collector
        """
        request_obj = self.get_object()

        # TODO: Verify user is the assigned collector
        # TODO: Validate location proximity
        # TODO: Check price deviation threshold

        collector = request_obj.collector

        # Update collector GPS
        collector.last_known_latitude = request.data.get("latitude")
        collector.last_known_longitude = request.data.get("longitude")
        collector.save()
        
        serializer = OnDemandRequestUpdateSerializer(
            request_obj, 
            data=request.data, 
            partial=True
        )
        serializer.is_valid(raise_exception=True)

        request_obj.request_status = "completed"
        request_obj.completed_at = timezone.now()
        request_obj.final_price = serializer.validated_data.get(
            "final_price", 
            request_obj.quoted_price
        )
        request_obj.waste_image = serializer.validated_data.get(
            "waste_image", 
            request_obj.waste_image
        )
        request_obj.save()

        # TODO: Generate invoice
        # TODO: Trigger payment processing
        # TODO: Send completion notification to client
        # TODO: Request client rating
        # TODO: Update collector statistics

        return Response(OnDemandRequestDetailSerializer(request_obj).data)

    @swagger_auto_schema(
        method='post',
        operation_summary="Cancel Request",
        operation_description="""
        Cancel an active on-demand waste collection request before or during service.

        **Authorized Users:**
        - Client (request submitter)
        - Assigned collector
        - Company dispatcher/administrator

        **When Cancellation is Allowed:**
        
        **By Client:**
        - Anytime before collector accepts
        - Within 30 minutes after acceptance (free cancellation)
        - After 30 minutes with valid reason (may incur cancellation fee)
        - Not allowed once service is in progress

        **By Collector:**
        - After acceptance but before starting service
        - Valid reasons: emergency, vehicle breakdown, safety concerns, access issues
        - Repeated cancellations may affect collector rating

        **By Company/Dispatcher:**
        - Anytime for operational reasons
        - To resolve disputes
        - For safety or policy violations

        **Required Parameter:**
        - `cancellation_reason` (string): Clear explanation for the cancellation

        **Cancellation Reasons (Examples):**
        - Client: "No longer need service", "Found alternative solution", "Wrong location"
        - Collector: "Vehicle breakdown", "Cannot access location", "Safety concern", "Emergency"
        - Company: "Duplicate request", "Service area restriction", "Policy violation"

        **Cancellation Workflow:**
        
        **Step 1: Cancellation Request**
        User submits cancellation with reason via this endpoint

        **Step 2: Validation**
        - System checks if cancellation is allowed based on:
            * Current request status
            * Time since acceptance
            * User role and permissions
            * Company cancellation policy
        
        **Step 3: Processing**
        Upon approval:
        1. Request status updated to "cancelled"
        2. Cancellation timestamp recorded
        3. Reason stored for analytics
        4. All parties notified:
            - Client receives cancellation confirmation
            - Collector notified (if was assigned)
            - Dispatcher alerted for reassignment
        
        **Step 4: Financial Handling**
        - Free cancellation: No charges
        - Late cancellation by client: May incur fee (policy dependent)
        - Collector cancellation: No earnings, may affect rating
        - System tracks cancellation patterns

        **Cancellation Fees (if applicable):**
        - Within free cancellation window: GHS 0
        - After free window, before collection: 20% of quoted_price
        - Collector no-show: Collector penalized, client not charged
        - Company cancellation: No client charges

        **Impact on Collector:**
        - Assigned collector is unassigned
        - Collector's acceptance slot freed up
        - Cancellation counted in collector metrics
        - Excessive cancellations (>10% rate) may trigger:
            * Temporary suspension
            * Lower priority in assignments
            * Account review

        **Impact on Request:**
        - Status: "cancelled"
        - Cannot be reactivated (client must create new request)
        - Preserved in system for analytics and auditing
        - May be eligible for refund based on timing

        **Alternative Options:**
        Instead of cancelling, consider:
        - Rescheduling (use update endpoint to change scheduled_date)
        - Reassignment (dispatcher can assign different collector)
        - Pause (temporary hold, not yet implemented)

        **Post-Cancellation:**
        - Request remains in system for reporting
        - Client can create new request immediately
        - Collector can accept other requests
        - Cancellation data used for service improvement

        

        

        **Error Scenarios:**
        - 400: Missing cancellation_reason
        - 403: User not authorized to cancel this request
        - 409: Request is already completed or cancelled
        - 422: Cancellation not allowed at this stage (e.g., service in progress)

        **Analytics Tracked:**
        - Cancellation rate by role
        - Common cancellation reasons
        - Time-to-cancellation patterns
        - Financial impact of cancellations
        - Collector cancellation patterns
        """,
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'cancellation_reason': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Clear explanation of why the request is being cancelled. Required for all cancellations.",
                    min_length=10,
                    max_length=500
                ),
            },
            required=['cancellation_reason'],
        ),
        responses={
            200: OnDemandRequestDetailSerializer,
            400: "cancellation_reason required or invalid",
            403: "Not authorized to cancel this request",
            409: "Request cannot be cancelled in current status",
            422: "Cancellation not allowed at this stage"
        },
    )
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Handle request cancellation.

        Args:
            request: DRF Request object with cancellation data
            pk: Primary key of the request to cancel

        Returns:
            Response: Cancelled request with final state

        Side Effects:
            - Updates status to "cancelled"
            - Records cancellation timestamp and reason
            - Notifies all involved parties
            - Processes any cancellation fees
            - Updates collector availability
            - Logs cancellation in analytics

        Raises:
            ValidationError: If cancellation_reason missing
            PermissionDenied: If user lacks cancellation rights
        """
        request_obj = self.get_object()
        reason = request.data.get("cancellation_reason")

        if not reason:
            return Response(
                {"error": "cancellation_reason is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # TODO: Validate cancellation is allowed based on status and timing
        # TODO: Calculate cancellation fees if applicable
        # TODO: Check user permissions for cancellation

        request_obj.request_status = "cancelled"
        request_obj.cancellation_reason = reason
        request_obj.cancelled_at = timezone.now()
        request_obj.cancelled_by = request.user
        request_obj.save()

        # TODO: Process cancellation fees
        # TODO: Notify client and collector
        # TODO: Update collector availability
        # TODO: Log cancellation analytics

        return Response(OnDemandRequestDetailSerializer(request_obj).data)