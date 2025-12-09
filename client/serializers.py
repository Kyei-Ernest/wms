from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from .models import Client
from .models import Client
from django.contrib.auth.hashers import make_password



User = get_user_model()


# USER BASE SERIALIZER (General Info)
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "username"
            "phone_number",
            "email",
            "role",
            "profile_photo",
            "address",
            "is_verified",
            "created_at",
        ]
        read_only_fields = ["username","created_at"]



class ClientSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)

    class Meta:
        model = Client
        fields = ["first_name", "last_name",
            "username","phone_number",
            "alternate_phone", "address_line1", "landmark",
            "area_zone", "city", "property_type",
            "preferred_collection_time", "latitude", "longitude",
            "wallet_balance", "subscription_plan",
            "segregation_compliance_percent",
            "is_active", "registration_date",
        ]
        read_only_fields = ["username", "wallet_balance", "registration_date"]



class ClientCreateSerializer(serializers.ModelSerializer):
    # Incoming user data
    email = serializers.EmailField(write_only=True, required=False, allow_null=True, allow_blank=True)
    phone_number = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Client
        fields = ["first_name", "last_name",
            "email", "phone_number", "password"
    
        ]

    # VALIDATION (Graceful errors)
    def validate(self, attrs):
        email = attrs.get("email")
        phone = attrs.get("phone_number")

        # Check duplicate email
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "This email is already registered."})

        # Check duplicate phone number
        if phone and User.objects.filter(phone_number=phone).exists():
            raise serializers.ValidationError({"phone_number": "This phone number is already registered."})

        return attrs

    # CREATE USER + CLIENT SAFE
    def create(self, validated_data):
        email = validated_data.pop("email", None)
        phone_number = validated_data.pop("phone_number")
        password = validated_data.pop("password")

        try:
            # ------ CREATE USER ------
            user = User(
                phone_number=phone_number,
                email=email,
                role="client"
            )
            user.password = make_password(password)
            user.save()

        except IntegrityError:
            raise serializers.ValidationError({
                "detail": "User with this phone number or email already exists."
            })

        # ------ CREATE CLIENT ------
        client = Client.objects.create(
            user=user,
            **validated_data
        )

        return client



class ClientListSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Client
        fields = [
            "username", "area_zone", "city",
            "property_type", "subscription_plan",
            "is_active", "registration_date",
        ]



class ClientUpdateSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(source="user.is_active")
    class Meta:
        model = Client
        fields = ["first_name","last_name",
            "alternate_phone", "address_line1", "landmark",
            "area_zone", "city", "latitude", "longitude",
            "preferred_collection_time", "is_active",
        ]

    def validate(self, data):
        # lat & lon must come together
        lat, lon = data.get("latitude"), data.get("longitude")
        if (lat and not lon) or (lon and not lat):
            raise serializers.ValidationError("Latitude and longitude must both be provided.")
        return data


