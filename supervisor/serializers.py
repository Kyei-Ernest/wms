from rest_framework import serializers
from django.db import IntegrityError
from django.contrib.auth.hashers import make_password

from accounts.models import User
from .models import Supervisor


class SupervisorSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Supervisor
        fields = ("first_name",
            "last_name",
            "company_username",
            "assigned_areas",
            "team_size",
            "photo_url",
            )

class SupervisorCreateSerializer(serializers.ModelSerializer):
    
    email = serializers.EmailField(
        write_only=True, required=False,
        allow_blank=True, allow_null=True
    )
    phone_number = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Supervisor
        fields = ["first_name", "last_name",
            "email", "phone_number", "password",
            "company_username", "assigned_areas",
            "team_size", "photo_url",
        ]
        read_only_fields = ["company_username"]

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

    # ------------------------------
    # CREATE SUPERVISOR + USER
    # ------------------------------
    def create(self, validated_data):
        
        email = validated_data.pop("email", None)
        phone_number = validated_data.pop("phone_number")
        password = validated_data.pop("password")

        # ----- CREATE USER -----
        try:
            user = User(
                phone_number=phone_number,
                email=email,
                role="supervisor"
            )
            user.password = make_password(password)
            user.save()
        except IntegrityError:
            raise serializers.ValidationError({
                "detail": "User with this phone number or email already exists."
            })

        # ----- CREATE SUPERVISOR -----
        supervisor = Supervisor.objects.create(
            user=user,
            **validated_data
        )

        return supervisor


class SupervisorListSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    phone_number = serializers.CharField(source="user.phone_number", read_only=True)

    class Meta:
        model = Supervisor
        fields = [
            "username", "phone_number",
            "company_username", "team_size",
            "assigned_areas", "is_active",
        ]


class SupervisorUpdateSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(source="user.is_active")

    class Meta:
        model = Supervisor
        fields = [
            "assigned_areas",
            "team_size",
            "photo_url",
            "is_active",
        ]

    def update(self, instance, validated_data):
        # Update user active status
        user_data = validated_data.pop("user", None)
        if user_data and "is_active" in user_data:
            instance.user.is_active = user_data["is_active"]
            instance.user.save()

        return super().update(instance, validated_data)

