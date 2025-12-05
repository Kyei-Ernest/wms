from rest_framework import serializers
from .models import Route, RouteStop


class RouteStopSerializer(serializers.ModelSerializer):
    """
    Serializer for individual route stops
    """
    client_name = serializers.CharField(source='client.user.get_full_name', read_only=True)
    client_phone = serializers.CharField(source='client.user.phone_number', read_only=True)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    
    class Meta:
        model = RouteStop
        fields = [
            'stop_id',
            'client',
            'client_name',
            'client_phone',
            'location',
            'latitude',
            'longitude',
            'order',
            'expected_minutes',
            'actual_start',
            'actual_end',
            'status',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['stop_id', 'created_at', 'updated_at']
    
    def get_latitude(self, obj):
        """Extract latitude from Point field"""
        if obj.location:
            return obj.location.y
        return None
    
    def get_longitude(self, obj):
        """Extract longitude from Point field"""
        if obj.location:
            return obj.location.x
        return None


class RouteStopCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating route stops
    """
    latitude = serializers.FloatField(required=False, allow_null=True, write_only=True)
    longitude = serializers.FloatField(required=False, allow_null=True, write_only=True)
    
    class Meta:
        model = RouteStop
        fields = [
            'client',
            'latitude',
            'longitude',
            'order',
            'expected_minutes',
            'status',
            'notes',
        ]
    
    def create(self, validated_data):
        """Create stop with Point field from lat/lng"""
        from django.contrib.gis.geos import Point
        
        latitude = validated_data.pop('latitude', None)
        longitude = validated_data.pop('longitude', None)
        
        if latitude and longitude:
            validated_data['location'] = Point(longitude, latitude, srid=4326)
        
        return super().create(validated_data)


class RouteListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing routes
    """
    company_name = serializers.CharField(source='company.company_name', read_only=True)
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    zone_code = serializers.CharField(source='zone.zone_code', read_only=True)
    supervisor_name = serializers.CharField(source='supervisor.user.get_full_name', read_only=True)
    collector_name = serializers.CharField(source='collector.user.get_full_name', read_only=True)
    stop_count = serializers.IntegerField(source='stops.count', read_only=True)
    
    class Meta:
        model = Route
        fields = [
            'route_id',
            'company',
            'company_name',
            'zone',
            'zone_name',
            'zone_code',
            'supervisor',
            'supervisor_name',
            'collector',
            'collector_name',
            'route_date',
            'start_time',
            'end_time',
            'completion_percent',
            'status',
            'total_distance_km',
            'estimated_duration',
            'stop_count',
            'created_at',
        ]
        read_only_fields = ['route_id', 'created_at', 'completion_percent', 'total_distance_km', 'estimated_duration']


class RouteDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for single route with all stops
    """
    company_name = serializers.CharField(source='company.company_name', read_only=True)
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    zone_code = serializers.CharField(source='zone.zone_code', read_only=True)
    supervisor_name = serializers.CharField(source='supervisor.user.get_full_name', read_only=True)
    collector_name = serializers.CharField(source='collector.user.get_full_name', read_only=True)
    collector_phone = serializers.CharField(source='collector.user.phone_number', read_only=True)
    stops = RouteStopSerializer(many=True, read_only=True)
    
    class Meta:
        model = Route
        fields = [
            'route_id',
            'company',
            'company_name',
            'zone',
            'zone_name',
            'zone_code',
            'supervisor',
            'supervisor_name',
            'collector',
            'collector_name',
            'collector_phone',
            'route_date',
            'start_time',
            'end_time',
            'actual_start',
            'actual_end',
            'completion_percent',
            'status',
            'total_distance_km',
            'estimated_duration',
            'stops',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'route_id',
            'created_at',
            'updated_at',
            'completion_percent',
            'total_distance_km',
            'estimated_duration',
            'actual_start',
            'actual_end',
        ]


class RouteCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating routes
    """
    stops = RouteStopCreateSerializer(many=True, required=False)
    
    class Meta:
        model = Route
        fields = [
            'company',
            'zone',
            'supervisor',
            'collector',
            'route_date',
            'start_time',
            'end_time',
            'status',
            'stops',
        ]
    
    def create(self, validated_data):
        """Create route with stops"""
        stops_data = validated_data.pop('stops', [])
        
        route = Route.objects.create(**validated_data)
        
        # Create stops
        for stop_data in stops_data:
            RouteStop.objects.create(route=route, **stop_data)
        
        return route


class RouteUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating routes
    """
    class Meta:
        model = Route
        fields = [
            'zone',
            'supervisor',
            'collector',
            'route_date',
            'start_time',
            'end_time',
            'actual_start',
            'actual_end',
            'status',
        ]
    
    def validate_status(self, value):
        """Validate status transitions"""
        instance = self.instance
        if instance:
            # Can't go backwards in status
            status_order = ['draft', 'assigned', 'in_progress', 'completed']
            if value in status_order and instance.status in status_order:
                current_index = status_order.index(instance.status)
                new_index = status_order.index(value)
                if new_index < current_index and value != 'cancelled':
                    raise serializers.ValidationError(
                        f"Cannot change status from '{instance.status}' to '{value}'"
                    )
        return value


class RouteStopUpdateSerializer(serializers.ModelSerializer):
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