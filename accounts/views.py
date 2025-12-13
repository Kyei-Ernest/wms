from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from collector.models import Collector
from collector.serializers import CollectorSerializer
from supervisor.models import Supervisor
from supervisor.serializers import SupervisorSerializer
from client.models import Client
from client.serializers import ClientSerializer
from waste_management_company.models import Company
from waste_management_company.serializers import CompanySerializer
from accounts.serializers import LoginSerializer, TokenRefreshCustomSerializer


# ============================================================
# ENUMS & COMMON SCHEMAS
# ============================================================

ROLE_ENUM = openapi.Schema(
    type=openapi.TYPE_STRING,
    description="System user role",
    enum=["client", "company", "collector", "supervisor", "admin"]
)

error_400 = openapi.Response(
    description="Bad Request – validation or authentication error",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "error": openapi.Schema(type=openapi.TYPE_STRING),
            "detail": openapi.Schema(type=openapi.TYPE_STRING),
        }
    ),
    examples={
        "application/json": {
            "error": "Invalid credentials",
            "detail": "Phone number, email, or password is incorrect."
        }
    }
)

error_403 = openapi.Response(
    description="Forbidden – account inactive or blocked",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "detail": openapi.Schema(type=openapi.TYPE_STRING)
        }
    ),
    examples={
        "application/json": {
            "detail": "Account is inactive."
        }
    }
)


# ============================================================
# ROLE-SPECIFIC PROFILE SCHEMAS
# ============================================================

client_profile_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    description="Client profile information",
    properties={
        "id": openapi.Schema(type=openapi.TYPE_INTEGER),
        "city": openapi.Schema(type=openapi.TYPE_STRING),
        "property_type": openapi.Schema(type=openapi.TYPE_STRING),
    }
)

company_profile_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    description="Waste management company profile",
    properties={
        "id": openapi.Schema(type=openapi.TYPE_INTEGER),
        "company_name": openapi.Schema(type=openapi.TYPE_STRING),
        "registration_number": openapi.Schema(type=openapi.TYPE_STRING),
    }
)

collector_profile_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    description="Collector profile information",
    properties={
        "id": openapi.Schema(type=openapi.TYPE_INTEGER),
        "first_name": openapi.Schema(type=openapi.TYPE_STRING),
        "last_name": openapi.Schema(type=openapi.TYPE_STRING),
    }
)

supervisor_profile_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    description="Supervisor profile information",
    properties={
        "id": openapi.Schema(type=openapi.TYPE_INTEGER),
        "company_username": openapi.Schema(type=openapi.TYPE_STRING),
        "assigned_areas": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Items(type=openapi.TYPE_STRING)
        ),
    }
)


# ============================================================
# LOGIN RESPONSE SCHEMA
# ============================================================

login_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    description="Successful authentication response",
    properties={
        "message": openapi.Schema(
            type=openapi.TYPE_STRING,
            example="Login successful"
        ),
        "user": openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="User primary key"
                ),
                "phone_number": openapi.Schema(type=openapi.TYPE_STRING),
                "email": openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
                "role": ROLE_ENUM,
                "is_active": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "profile": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description="Role-specific profile data",
                    oneOf=[
                        client_profile_schema,
                        company_profile_schema,
                        collector_profile_schema,
                        supervisor_profile_schema,
                    ]
                )
            }
        ),
        "tokens": openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "refresh": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="JWT refresh token"
                ),
                "access": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="JWT access token"
                )
            }
        )
    }
)

TAGS = ["Authentication"]


# ============================================================
# LOGIN
# ============================================================

class LoginView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Authenticate user",
        operation_description=(
            "Authenticates a user using phone number, email, or username "
            "and returns JWT access & refresh tokens along with role-based profile data."
        ),
        operation_id="auth_login",
        request_body=LoginSerializer,
        responses={
            200: openapi.Response("Login successful", login_response_schema),
            400: error_400,
            403: error_403,
        }
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        if not user.is_active:
            return Response(
                {"detail": "Account is inactive."},
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Login successful",
            "user": {
                "id": user.id,
                "phone_number": user.phone_number,
                "email": user.email or None,
                "role": user.role,
                "is_active": user.is_active,
                "profile": self.get_profile(user),
            },
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)

    def get_profile(self, user):
        if user.role == "client":
            return ClientSerializer(
                Client.objects.filter(user=user).first()
            ).data if Client.objects.filter(user=user).exists() else {}

        if user.role == "company":
            return CompanySerializer(
                Company.objects.filter(user=user).first()
            ).data if Company.objects.filter(user=user).exists() else {}

        if user.role == "collector":
            return CollectorSerializer(
                Collector.objects.filter(user=user).first()
            ).data if Collector.objects.filter(user=user).exists() else {}

        if user.role == "supervisor":
            return SupervisorSerializer(
                Supervisor.objects.filter(user=user).first()
            ).data if Supervisor.objects.filter(user=user).exists() else {}

        return {}


# ============================================================
# TOKEN REFRESH
# ============================================================

class TokenRefreshView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Refresh JWT tokens",
        operation_description=(
            "Generates a new access token using a valid refresh token. "
            "A new refresh token is returned if rotation is enabled."
        ),
        operation_id="auth_token_refresh",
        request_body=TokenRefreshCustomSerializer,
        responses={
            200: openapi.Response(
                "Tokens refreshed successfully",
                openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "access": openapi.Schema(type=openapi.TYPE_STRING),
                        "refresh": openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: error_400,
        }
    )
    def post(self, request):
        serializer = TokenRefreshCustomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


# ============================================================
# LOGOUT
# ============================================================

logout_request_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["refresh"],
    properties={
        "refresh": openapi.Schema(
            type=openapi.TYPE_STRING,
            description="Refresh token to be blacklisted"
        ),
        "access": openapi.Schema(
            type=openapi.TYPE_STRING,
            description="Optional access token to invalidate"
        ),
    }
)

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Logout user",
        operation_description=(
            "Invalidates the provided refresh token by blacklisting it. "
            "Optionally invalidates the access token if supported."
        ),
        operation_id="auth_logout",
        request_body=logout_request_schema,
        responses={
            200: openapi.Response(
                "Logout successful",
                openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "message": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example="Logout successful. Tokens invalidated."
                        )
                    }
                )
            ),
            400: error_400,
        }
    )
    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"error": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {"error": "Invalid or already blacklisted refresh token."},
                status=status.HTTP_400_BAD_REQUEST
            )

        access_token = request.data.get("access")
        if access_token:
            try:
                AccessToken(access_token).blacklist()
            except Exception:
                pass

        return Response(
            {"message": "Logout successful. Tokens invalidated."},
            status=status.HTTP_200_OK
        )
