from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from client.models import Client
from client.serializers import ClientSerializer
from waste_management_company.models import Company
from waste_management_company.serializers import CompanySerializer
from accounts.serializers import LoginSerializer, TokenRefreshCustomSerializer


# ===========================
# REUSABLE SCHEMAS
# ===========================
error_400 = openapi.Response(
    description="Bad Request",
    examples={"application/json": {"error": "Invalid credentials"}}
)
error_403 = openapi.Response(
    description="Forbidden",
    examples={"application/json": {"detail": "Account is inactive."}}
)

# Profile schema (dynamic per role)
profile_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    description="Role-specific profile data (Client or Company)",
    example={
        "client": {"user_id": "CLT000001", "city": "Accra", "property_type": "House"},
        "company": {"company_id": "CMP000001", "company_name": "EcoWaste Ltd"}
    }
)

# Full login response schema
login_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "message": openapi.Schema(type=openapi.TYPE_STRING, example="Login successful"),
        "user": openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                "phone_number": openapi.Schema(type=openapi.TYPE_STRING),
                "email": openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
                "role": openapi.Schema(type=openapi.TYPE_STRING, enum=["client", "company", "collector", "admin"]),
                "is_active": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "profile": profile_schema
            }
        ),
        "tokens": openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "refresh": openapi.Schema(type=openapi.TYPE_STRING),
                "access": openapi.Schema(type=openapi.TYPE_STRING)
            }
        )
    }
)

TAGS = ["Authentication"]


# ===========================
# LOGIN
# ===========================
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Login with phone/email/ID",
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
            return Response({"detail": "Account is inactive."}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        profile_data = self.get_profile(user)

        return Response({
            "message": "Login successful",
            "user": {
                "id": user.id,
                "phone_number": user.phone_number,
                "email": user.email or None,
                "role": user.role,
                "is_active": user.is_active,
                "profile": profile_data,
            },
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)

    def get_profile(self, user):
        role = user.role
        if role == "client":
            try:
                profile = Client.objects.get(user=user)
                return ClientSerializer(profile).data
            except Client.DoesNotExist:
                return {}
        elif role == "company":
            try:
                profile = Company.objects.get(user=user)
                return CompanySerializer(profile).data
            except Company.DoesNotExist:
                return {}
        return {}


# ===========================
# TOKEN REFRESH
# ===========================
class TokenRefreshView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Refresh access token",
        operation_id="auth_token_refresh",
        request_body=TokenRefreshCustomSerializer,
        responses={
            200: openapi.Response(
                "New tokens issued",
                openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "access": openapi.Schema(type=openapi.TYPE_STRING, description="New access token"),
                        "refresh": openapi.Schema(type=openapi.TYPE_STRING, description="New refresh token (if rotation enabled)")
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


# ===========================
# LOGOUT (Blacklist Tokens)
# ===========================
logout_request_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["refresh"],
    properties={
        "refresh": openapi.Schema(type=openapi.TYPE_STRING, description="Refresh token to blacklist"),
        "access": openapi.Schema(type=openapi.TYPE_STRING, description="Optional: access token to invalidate")
    },
    example={"refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.x...", "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.y..."}
)

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Logout and blacklist tokens",
        operation_id="auth_logout",
        request_body=logout_request_schema,
        responses={
            200: openapi.Response("Logout successful", openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={"message": openapi.Schema(type=openapi.TYPE_STRING, example="Logout successful. Tokens invalidated.")}
            )),
            400: error_400
        }
    )
    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response({"error": "Invalid or already used refresh token."}, status=status.HTTP_400_BAD_REQUEST)

        # Optional: blacklist access token (requires custom AccessToken with blacklist support)
        access_token = request.data.get("access")
        if access_token:
            try:
                AccessToken(access_token).blacklist()
            except Exception:
                pass  # Ignore if not supported

        return Response({"message": "Logout successful. Tokens invalidated."}, status=status.HTTP_200_OK)