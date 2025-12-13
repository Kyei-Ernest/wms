from rest_framework import serializers
from django.contrib.gis.geos import Point
from django.contrib.gis.geos import Point
from client.models import Client
from .models import Route, RouteStop
from on_demand.serializers import OnDemandRequestDetailSerializer
from scheduled_request.serializers import ScheduledRequestDetailSerializer


class RouteStopSerializer(serializers.ModelSerializer):
    # Nested request serializers
    ondemand_request = OnDemandRequestDetailSerializer(read_only=True)
    scheduled_request = ScheduledRequestDetailSerializer(read_only=True)

    # Derived fields for clarity
    request_type = serializers.SerializerMethodField()
    request_status = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()

    class Meta:
        model = RouteStop
        fields = [
            "stop_id",
            "order",
            "location",
            "expected_minutes",
            "actual_start",
            "actual_end",
            "status",
            "notes",
            "ondemand_request",
            "scheduled_request",
            "request_type",
            "request_status",
            "client_name",
        ]

    def get_request_type(self, obj):
        if obj.ondemand_request:
            return "OnDemand"
        elif obj.scheduled_request:
            return "Scheduled"
        return None

    def get_request_status(self, obj):
        if obj.ondemand_request:
            return obj.ondemand_request.request_status
        elif obj.scheduled_request:
            return obj.scheduled_request.request_status
        return obj.status  # fallback to stop status

    def get_client_name(self, obj):
        if obj.ondemand_request and obj.ondemand_request.client:
            return obj.ondemand_request.client.full_name
        elif obj.scheduled_request and obj.scheduled_request.client:
            return obj.scheduled_request.client.full_name
        return None


class RouteSerializer(serializers.ModelSerializer):
    stops = RouteStopSerializer(many=True, read_only=True)

    # Derived fields for clarity
    total_stops = serializers.SerializerMethodField()
    completed_stops = serializers.SerializerMethodField()
    collector_name = serializers.SerializerMethodField()
    supervisor_name = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = [
            "route_id",
            "company",
            "zone",
            "supervisor",
            "collector",
            "route_date",
            "start_time",
            "end_time",
            "actual_start",
            "actual_end",
            "completion_percent",
            "status",
            "total_distance_km",
            "estimated_duration",
            "created_at",
            "updated_at",
            "total_stops",
            "completed_stops",
            "collector_name",
            "supervisor_name",
            "stops",
        ]

    def get_total_stops(self, obj):
        return obj.stops.count()

    def get_completed_stops(self, obj):
        return obj.stops.filter(status="completed").count()

    def get_collector_name(self, obj):
        return obj.collector.full_name if obj.collector else None

    def get_supervisor_name(self, obj):
        return obj.supervisor.user.get_full_name() if obj.supervisor else None

