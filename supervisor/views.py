from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from drf_yasg.utils import swagger_auto_schema
from accounts.permissions import IsCompany

from .models import Supervisor
from .serializers import (
    SupervisorCreateSerializer,
    SupervisorListSerializer,
    SupervisorUpdateSerializer,
)


class SupervisorCreateView(APIView):
    """
    Create a new supervisor account.

    This endpoint registers a supervisor in two parts:
    - Creates a `User` record with role="supervisor"
    - Creates the `Supervisor` profile linked to a specific Waste Management Company

    ---
    ### Required Fields
    - phone_number  
    - password  
    - company  

    ### Optional Fields
    - email  
    - assigned_areas  
    - team_size  
    - photo_url  

    ### Validation Rules
    - Phone number must be unique  
    - Email (if provided) must be unique  
    - Gracefully handles duplicate user errors  

    ---
    ### Successful Response (201 CREATED)
    Returns `SupervisorListSerializer` output:
    ```json
    {
        "username": "SUP123",
        "phone_number": "0551234567",
        "assigned_areas": [],
        "team_size": 10,
        "is_active": true
    }
    ```

    ### Error Responses
    - **400 Bad Request**
      - Duplicate phone number or email  
      - Missing required fields  
      - Validation errors  
    """
    permission_classes = [IsCompany]
    @swagger_auto_schema(request_body=SupervisorCreateSerializer,
                         responses={201: SupervisorListSerializer})
    def post(self, request):
        serializer = SupervisorCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        supervisor = serializer.save(company_username=self.request.user.username)

        output = SupervisorListSerializer(supervisor)
        return Response(output.data, status=status.HTTP_201_CREATED)


class SupervisorListView(APIView):
    """
    Retrieve a list of all supervisors in the system.

    ---
    ### Response Fields (SupervisorListSerializer)
    - username  
    - phone_number  
    - company  
    - assigned_areas  
    - team_size  
    - is_active  

    ---
    ### Example Response (200 OK)
    ```json
    [
        {
            "username": "SUP001",
            "phone_number": "0551112222",
            "company": 3,
            "assigned_areas": ["North Ridge", "Osu"],
            "team_size": 8,
            "is_active": true
        },
        ...
    ]
    ```
    """

    @swagger_auto_schema(responses={200: SupervisorListSerializer(many=True)})
    def get(self, request):
        supervisors = Supervisor.objects.all()
        serializer = SupervisorListSerializer(supervisors, many=True)
        return Response(serializer.data)


class SupervisorProfileView(APIView):
    """
    Retrieve or update the authenticated supervisor's profile.

    ---
    ### Permissions
    - Requires authentication (`IsAuthenticated`)

    ---
    ### GET
    Returns the full profile of the logged-in supervisor.

    ### PUT / PATCH
    Updates the supervisor profile.
    - `PUT` → full update  
    - `PATCH` → partial update  

    ---
    ### Updatable Fields
    - assigned_areas
    - team_size
    - photo_url
    - is_active (from User model)

    ---
    ### Success Response (200 OK)
    Returns updated `SupervisorListSerializer` output.

    ### Error Responses
    - **400 Bad Request**
      - Invalid update fields
    - **404 Not Found**
      - No supervisor profile associated with the authenticated user
    """

    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(responses={200: SupervisorListSerializer})
    def get(self, request):
        try:
            supervisor = Supervisor.objects.get(user=request.user)
        except Supervisor.DoesNotExist:
            return Response({"error": "Supervisor profile not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = SupervisorListSerializer(supervisor)
        return Response(serializer.data)

    @swagger_auto_schema(request_body=SupervisorUpdateSerializer,
                         responses={200: SupervisorListSerializer})
    def put(self, request):
        return self._update(request)

    @swagger_auto_schema(request_body=SupervisorUpdateSerializer,
                         responses={200: SupervisorListSerializer})
    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial=False):
        try:
            supervisor = Supervisor.objects.get(user=request.user)
        except Supervisor.DoesNotExist:
            return Response({"error": "Supervisor profile not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = SupervisorUpdateSerializer(supervisor, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(SupervisorListSerializer(supervisor).data)
