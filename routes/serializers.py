from rest_framework import serializers
from django.contrib.gis.geos import Point
from django.contrib.gis.geos import Point
from client.models import Client
from .models import Route, RouteStop


class RouteStopSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(write_only=True, required=False)
    longitude = serializers.FloatField(write_only=True, required=False)

    class Meta:
        model = RouteStop
        fields = [
            'stop_id', 'order', 'client', 'status',
            'expected_minutes', 'actual_start', 'actual_end',
            'notes', 'latitude', 'longitude', 'location',
        ]
        read_only_fields = ['stop_id', 'location']

    def validate(self, data):
        lat, lon = data.get('latitude'), data.get('longitude')
        if (lat is None) ^ (lon is None):
            raise serializers.ValidationError("Both latitude and longitude must be provided together.")

        # If lat/lon provided, check zone boundary
        if lat is not None and lon is not None:
            route = self.context.get('route') or self.instance.route if self.instance else None
            if route and route.zone:
                point = Point(lon, lat, srid=4326)
                if not route.zone.boundary.contains(point):
                    raise serializers.ValidationError(
                        f"Stop at ({lat}, {lon}) is outside the zone boundary: {route.zone.name}"
                    )
        return data

    def create(self, validated_data):
        lat, lon = validated_data.pop('latitude', None), validated_data.pop('longitude', None)
        if lat is not None and lon is not None:
            validated_data['location'] = Point(lon, lat, srid=4326)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        lat, lon = validated_data.pop('latitude', None), validated_data.pop('longitude', None)
        if lat is not None and lon is not None:
            validated_data['location'] = Point(lon, lat, srid=4326)
        return super().update(instance, validated_data)


class RouteSerializer(serializers.ModelSerializer):
    stops = RouteStopSerializer(many=True, read_only=True)

    class Meta:
        model = Route
        fields = [
            'route_id', 'company', 'zone', 'supervisor', 'collector',
            'route_date', 'start_time', 'end_time',
            'actual_start', 'actual_end',
            'completion_percent', 'status',
            'total_distance_km', 'estimated_duration',
            'created_at', 'updated_at',
            'stops',
        ]
        read_only_fields = ['completion_percent', 'total_distance_km', 'estimated_duration']


class RouteCreateSerializer(serializers.ModelSerializer):
    stops = serializers.ListField(child=serializers.DictField(), required=False)

    class Meta:
        model = Route
        fields = ['company', 'zone', 'supervisor', 'collector', 'route_date', 'status', 'stops']

    def create(self, validated_data):
        stops_data = validated_data.pop('stops', [])
        route = Route.objects.create(**validated_data)

        if not stops_data:
            # Automatically generate stops from clients inside the zone
            zone = route.zone
            clients_in_zone = Client.objects.filter(location__within=zone.boundary)

            if not clients_in_zone.exists():
                raise serializers.ValidationError(
                    f"No clients found inside zone {zone.name}. Cannot auto-generate stops."
                )

            for idx, client in enumerate(clients_in_zone, start=1):
                RouteStop.objects.create(
                    route=route,
                    client=client,
                    order=idx,
                    expected_minutes=5,
                    location=client.location,
                    status='pending'
                )
        else:
            # Manual stop creation with validation
            for idx, stop_data in enumerate(stops_data, start=1):
                lat, lon = stop_data.pop('latitude', None), stop_data.pop('longitude', None)
                if lat is not None and lon is not None:
                    point = Point(lon, lat, srid=4326)
                    if not route.zone.boundary.contains(point):
                        raise serializers.ValidationError(
                            f"Stop at ({lat}, {lon}) is outside the zone boundary: {route.zone.name}"
                        )
                    stop_data['location'] = point
                RouteStop.objects.create(route=route, order=idx, **stop_data)

        return route


class RouteStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = ['status']

    def validate_status(self, value):
        instance = self.instance
        valid_transitions = {
            'draft': ['assigned', 'cancelled'],
            'assigned': ['in_progress', 'cancelled'],
            'in_progress': ['completed', 'cancelled'],
            'completed': [],
            'cancelled': [],
        }
        if value not in valid_transitions.get(instance.status, []):
            raise serializers.ValidationError(
                f"Invalid status transition from {instance.status} to {value}."
            )
        return value

    """
    Serializer for updating individual stops
    """
    latitude = serializers.FloatField(required=False, allow_null=True, write_only=True)
    longitude = serializers.FloatField(required=False, allow_null=True, write_only=True)
    
    class Meta:
        model = RouteStop
        fields = [
            'order',
            'expected_minutes',
            'actual_start',
            'actual_end',
            'status',
            'notes',
            'latitude',
            'longitude',
        ]
    
    def update(self, instance, validated_data):
        """Update stop with Point field from lat/lng if provided"""
        from django.contrib.gis.geos import Point
        
        latitude = validated_data.pop('latitude', None)
        longitude = validated_data.pop('longitude', None)
        
        if latitude is not None and longitude is not None:
            instance.location = Point(longitude, latitude, srid=4326)
        
        return super().update(instance, validated_data)