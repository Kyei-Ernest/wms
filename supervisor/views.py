from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

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

    Must be an authenticated Waste management company to create supervisor account.

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
    Handles retrieval and update of the authenticated supervisor's profile.
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.IsAuthenticated()]
        elif self.request.method == "PUT":
            return [permissions.IsAuthenticated()]
        elif self.request.method == "PATCH":
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    # -----------------------------
    # GET /supervisor/profile/
    # -----------------------------
    @swagger_auto_schema(
        operation_summary="Retrieve Supervisor Profile",
        operation_description="""
        Returns the complete profile of the authenticated supervisor.

        **Permissions:**  
        - Requires authentication (`IsAuthenticated`) as supervisor

        **Success Response:**
        - `200 OK` → SupervisorListSerializer data

        **Error Responses:**
        - `404 Not Found` → Profile does not exist
        """,
        responses={
            200: SupervisorListSerializer,
            404: openapi.Response(description="Supervisor profile not found"),
        },
    )
    def get(self, request):
        try:
            supervisor = Supervisor.objects.get(user=request.user)
        except Supervisor.DoesNotExist:
            return Response(
                {"error": "Supervisor profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SupervisorListSerializer(supervisor)
        return Response(serializer.data)

    # -----------------------------
    # PUT /supervisor/profile/
    # -----------------------------
    @swagger_auto_schema(
        operation_summary="Update Supervisor Profile (Full Update)",
        operation_description="""
        Fully updates the supervisor's profile.

        **Permissions:**  
        - Requires authentication (`IsAuthenticated`) as supervisor

        **Use When:**  
        - You want to update **all** fields.

        **Updatable Fields:**
        - assigned_areas  
        - team_size  
        - photo_url  
        - is_active (from User model)

        **Success Response:**
        - `200 OK`

        **Error Responses:**
        - `400 Bad Request` → Invalid fields
        - `404 Not Found` → Profile missing
        """,
        request_body=SupervisorUpdateSerializer,
        responses={
            200: SupervisorListSerializer,
            400: "Bad Request",
            404: "Supervisor profile not found",
        },
    )
    
    def put(self, request):
        return self._update(request)

    # -----------------------------
    # PATCH /supervisor/profile/
    # -----------------------------
    @swagger_auto_schema(
        operation_summary="Partially Update Supervisor Profile",
        operation_description="""
        Partially updates supervisor fields.  

        **Permissions:**  
        - Requires authentication (`IsAuthenticated`) as supervisor

        Only send the fields you want to update.

        **Success Response:**
        - `200 OK`

        **Error Responses:**
        - `400 Bad Request`
        - `404 Not Found`
        """,
        request_body=SupervisorUpdateSerializer,
        responses={
            200: SupervisorListSerializer,
            400: "Bad Request",
            404: "Supervisor profile not found",
        },
    )
    def patch(self, request):
        return self._update(request, partial=True)

    # -----------------------------
    # Internal Update Logic
    # -----------------------------
    def _update(self, request, partial=False):
        try:
            supervisor = Supervisor.objects.get(user=request.user)
        except Supervisor.DoesNotExist:
            return Response(
                {"error": "Supervisor profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SupervisorUpdateSerializer(
            supervisor,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(SupervisorListSerializer(supervisor).data)
