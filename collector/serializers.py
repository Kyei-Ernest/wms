from rest_framework import serializers
from django.db import IntegrityError
from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model

from .models import Collector
from waste_management_company.models import Company
from supervisor.models import Supervisor

User = get_user_model()


class CollectorCreateSerializer(serializers.ModelSerializer):
    # Incoming user fields
    email = serializers.EmailField(write_only=True, required=False, allow_null=True, allow_blank=True)
    phone_number = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Collector
        fields = [
            # USER FIELDS
            "email", "phone_number", "password",

            # COLLECTOR FIELDS
            "company",
            "supervisor",
            "is_private_collector",
            "vehicle_number",
            "vehicle_type",
            "assigned_area_zone",
            "employment_type",
            "daily_wage_or_incentive_rate",
            "bank_account_details",
        ]

    # VALIDATION
    def validate(self, attrs):
        email = attrs.get("email")
        phone = attrs.get("phone_number")
        company = attrs.get("company")
        supervisor = attrs.get("supervisor")
        is_private = attrs.get("is_private_collector")

        # Unique email
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "This email is already registered."})

        # Unique phone number
        if phone and User.objects.filter(phone_number=phone).exists():
            raise serializers.ValidationError({"phone_number": "This phone number is already registered."})

        # Private collector MUST NOT have company or supervisor
        if is_private:
            if company is not None:
                raise serializers.ValidationError({"company": "Private collectors cannot be assigned to a company."})
            if supervisor is not None:
                raise serializers.ValidationError({"supervisor": "Private collectors cannot have supervisors."})

        # Company collector MUST have company
        if not is_private and company is None:
            raise serializers.ValidationError({"company": "Company-employed collectors must have a company."})

        # If supervisor is provided, it must belong to same company
        if supervisor and company and supervisor.company_id != company.id:
            raise serializers.ValidationError({
                "supervisor": "Supervisor must belong to the same company as this collector."
            })

        return attrs

    # CREATE LOGIC (User + Collector)
    def create(self, validated_data):
        email = validated_data.pop("email", None)
        phone_number = validated_data.pop("phone_number")
        password = validated_data.pop("password")

        try:
            # CREATE USER
            user = User(
                phone_number=phone_number,
                email=email,
                role="collector"
            )
            user.password = make_password(password)
            user.save()
        except IntegrityError:
            raise serializers.ValidationError({
                "detail": "Collector with this phone number or email already exists."
            })

        # CREATE COLLECTOR PROFILE
        collector = Collector.objects.create(
            user=user,
            **validated_data
        )

        return collector

class CollectorListSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    phone_number = serializers.CharField(source="user.phone_number", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = Collector
        fields = [
            "username",
            "phone_number",
            "company_name",
            "is_private_collector",
            "vehicle_number",
            "vehicle_type",
            "assigned_area_zone",
            "employment_type",
            "daily_wage_or_incentive_rate",
            "average_rating",
            "total_collections",
            "is_active",
        ]

class CollectorUpdateSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(source="user.is_active", required=False)

    class Meta:
        model = Collector
        fields = [
            "vehicle_number",
            "vehicle_type",
            "assigned_area_zone",
            "employment_type",
            "daily_wage_or_incentive_rate",
            "bank_account_details",
            "last_known_latitude",
            "last_known_longitude",
            "is_active",
        ]

    def validate(self, data):
        lat = data.get("last_known_latitude")
        lon = data.get("last_known_longitude")

        # lat & lon must come together  
        if (lat and not lon) or (lon and not lat):
            raise serializers.ValidationError("Latitude and longitude must both be provided.")
        return data

    def update(self, instance, validated_data):
        # Update user.is_active if provided
        user_data = validated_data.pop("user", None)
        if user_data:
            for attr, value in user_data.items():
                setattr(instance.user, attr, value)
            instance.user.save()

        return super().update(instance, validated_data)
