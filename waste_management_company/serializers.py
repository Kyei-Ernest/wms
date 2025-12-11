from rest_framework import serializers
from django.db import transaction
from .models import User, Company
from django.contrib.auth import  authenticate
from django.contrib.auth.hashers import make_password





class CompanySerializer(serializers.ModelSerializer):

    # Flattening user fields
    username = serializers.CharField(source="user.username", read_only=True)
    phone_number = serializers.CharField(source="user.phone_number", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    profile_photo = serializers.ImageField(source="user.profile_photo", read_only=True)
    address = serializers.CharField(source="user.address", read_only=True)
    is_verified = serializers.BooleanField(source="user.is_verified", read_only=True)

    class Meta:
        model = Company
        fields = [
            "id",

            # USER FIELDS (flattened)
            "username",
            "phone_number",
            "email",
            "profile_photo",
            "address",
            "is_verified",

            # COMPANY FIELDS
            "company_name",
            "gst_number",
            "weighing_system",
            "working_days",
            "opening_time",
            "closing_time",
            "price_min",
            "price_max",
            "incentive_per_100_percent_route",
            "complaint_resolution_sla",
            "total_producers",
            "total_collectors",
            "operational_cities",
        ]



class CompanyCreateSerializer(serializers.Serializer):
    # USER FIELDS
    phone_number = serializers.CharField()
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    profile_photo = serializers.URLField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)

    # COMPANY FIELDS
    company_name = serializers.CharField()
    gst_number = serializers.CharField()
    #weighing_system = serializers.CharField()
    #incentive_per_100_percent_route = serializers.DecimalField(max_digits=10, decimal_places=2)
    complaint_resolution_sla = serializers.IntegerField()
    #total_producers = serializers.IntegerField(required=False, default=0)
    #total_collectors = serializers.IntegerField(required=False, default=0)
    operational_cities = serializers.ListField(child=serializers.CharField(), required=False)# List of working days (Mon–Sun)
    working_days = serializers.JSONField()

    # Simple working hours (same every day)
    opening_time = serializers.TimeField()
    closing_time = serializers.TimeField()

    # Price range numeric min/max
    price_min = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True
    )
    price_max = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True
    )

    # VALIDATION
    def validate(self, attrs):
        email = attrs.get("email")
        phone = attrs.get("phone_number")

        # Duplicate email
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "This email is already registered."})

        # Duplicate phone number
        if phone and User.objects.filter(phone_number=phone).exists():
            raise serializers.ValidationError({"phone_number": "This phone number is already registered."})
        
        

        return attrs


    def create(self, validated_data):
        with transaction.atomic():
            # Extract user fields
            user_fields = {
                "phone_number": validated_data.pop("phone_number"),
                "email": validated_data.pop("email", None),
                "profile_photo": validated_data.pop("profile_photo", None),
                "address": validated_data.pop("address", None),
                "role": "company"
            }

            # Create user (auto assigns username)
            user = User(**user_fields)
            user.password = make_password(validated_data.pop("password"))
            user.save()

            # Create company profile linked to user
            company = Company.objects.create(user=user, **validated_data)

            return company
        

    