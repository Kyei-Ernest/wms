from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, serializers
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Company
from .serializers import CompanyCreateSerializer, CompanySerializer


# JWT tokens serializer
class TokensSerializer(serializers.Serializer):
    refresh = serializers.CharField()
    access = serializers.CharField()


# Wrapper serializer for Swagger
class CompanyWithTokensSerializer(serializers.Serializer):
    company = CompanySerializer()
    tokens = TokensSerializer()


# Error responses
error_400 = openapi.Response(
    description="Bad Request",
    examples={"application/json": {"phone_number": ["A company with this phone number already exists."]}}
)
error_404 = openapi.Response(
    description="Not Found",
    examples={"application/json": {"error": "Company profile not found"}}
)

TAGS = ["Companies"]


# Helper: Generate JWT tokens
def generate_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


# Company registration
class CompanyRegisterView(APIView):
    """
    Register a new company account.
    Creates a User (role=company) + linked Company profile.
    Returns company data + JWT tokens on success.
    """
    authentication_classes = []  # Public endpoint
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Register a new company",
        operation_id="company_register",
        request_body=CompanyCreateSerializer,
        responses={
            201: openapi.Response(
                description="Company created successfully",
                schema=CompanyWithTokensSerializer
            ),
            400: error_400,
        }
    )
    def post(self, request):
        serializer = CompanyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = serializer.save()
        tokens = generate_tokens(company.user)

        response_data = {
            "company": CompanySerializer(company).data,
            "tokens": tokens
        }

        return Response(response_data, status=status.HTTP_201_CREATED)


class CompanyListView(APIView):
    """
    List all companies in the system.
    Public endpoint — no authentication needed.
    """
    authentication_classes = []  
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="List all companies",
        operation_id="company_list",
        responses={
            200: openapi.Response(
                description="List of companies",
                schema=CompanySerializer(many=True)
            )
        }
    )
    def get(self, request):
        companies = Company.objects.all()
        serializer = CompanySerializer(companies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
# Company profile (GET + UPDATE)
class CompanyProfileView(APIView):
    """
    Retrieve or update the authenticated company's profile.
    Only accessible to logged-in company users.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Helper to get company or return 404"""
        try:
            return Company.objects.get(user=self.request.user)
        except Company.DoesNotExist:
            raise status.HTTP_404_NOT_FOUND

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Get company profile",
        operation_id="company_profile_retrieve",
        responses={
            200: CompanySerializer,
            404: error_404,
        }
    )
    def get(self, request):
        company = self.get_object()
        serializer = CompanySerializer(company)
        return Response(serializer.data)

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Fully update company profile",
        operation_id="company_profile_update",
        request_body=CompanySerializer,
        responses={
            200: CompanySerializer,
            400: error_400,
            404: error_404,
        }
    )
    def put(self, request):
        return self._update_profile(request, partial=False)

    @swagger_auto_schema(
        tags=TAGS,
        operation_summary="Partially update company profile",
        operation_id="company_profile_partial_update",
        request_body=CompanySerializer,
        responses={
            200: CompanySerializer,
            400: error_400,
            404: error_404,
        }
    )
    def patch(self, request):
        return self._update_profile(request, partial=True)

    def _update_profile(self, request, partial=False):
        company = self.get_object()
        serializer = CompanySerializer(company, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CompanySerializer(company).data)
