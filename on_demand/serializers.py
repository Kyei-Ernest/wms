from rest_framework import serializers
from django.contrib.gis.geos import Point
from .models import OnDemandRequest
from geopy.distance import geodesic



class OnDemandRequestListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing requests
    """
    client_name = serializers.CharField(source='client.user.get_full_name', read_only=True)
    collector_name = serializers.CharField(source='collector.user.get_full_name', read_only=True)

    class Meta:
        model = OnDemandRequest
        fields = [
            'request_id',
            'client',
            'client_name',
            'collector',
            'collector_name',
            'pickup_date',
            'pickup_time_slot',
            'area_zone',
            'city',
            'waste_type',
            'bag_count',
            'bin_size_liters',
            'quoted_price',
            'final_price',
            'payment_status',
            'request_status',
            'requested_at',
        ]
        read_only_fields = ['request_id', 'quoted_price', 'final_price', 'requested_at']


class OnDemandRequestDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for viewing a specific request
    """
    client_name = serializers.CharField(source='client.user.get_full_name', read_only=True)
    collector_name = serializers.CharField(source='collector.user.get_full_name', read_only=True)

    class Meta:
        model = OnDemandRequest
        fields = [
            'request_id',
            'client',
            'client_name',
            'collector',
            'collector_name',
            'pickup_date',
            'pickup_time_slot',
            'address_line1',
            'landmark',
            'area_zone',
            'city',
            'latitude',
            'longitude',
            
            'waste_type',
            'bag_count',
            'bin_size_liters',
            'special_instructions',
            'waste_image',
            'quoted_price',
            'final_price',
            'payment_status',
            'request_status',
            'requested_at',
            'accepted_at',
            'completed_at',
            'cancelled_at',
            'cancellation_reason',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['request_id', 'quoted_price', 'final_price', 'requested_at', 'created_at', 'updated_at']


class OnDemandRequestCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new requests
    """
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)

    class Meta:
        model = OnDemandRequest
        fields = [
            'client',
            'pickup_date',
            'pickup_time_slot',
            'address_line1',
            'landmark',
            #'area_zone',
            'city',
            'latitude',
            'longitude',
            'waste_type',
            'bag_count',
            'bin_size_liters',
            'special_instructions',
            'waste_image',
        ]

    def validate_waste_type(self, value):
        """
        Restrict hazardous/special waste types to company handling only
        """
        restricted_types = ['hazardous', 'sanitary', 'bulk', 'construction', 'e_waste']
        if value in restricted_types and not self.context['request'].user.is_company:
            raise serializers.ValidationError("This waste type can only be handled by companies.")
        return value

    def create(self, validated_data):
        # Build PointField from lat/long
        lat = validated_data.pop('latitude')
        lon = validated_data.pop('longitude')
        validated_data['location'] = Point(float(lon), float(lat))
        return OnDemandRequest.objects.create(**validated_data)



class OnDemandRequestUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating requests (assignment, acceptance, completion).
    Enforces status transitions and GPS-based completion rules.
    """

    class Meta:
        model = OnDemandRequest
        fields = [
            'collector',
            'request_status',
            'final_price',
            'payment_status',
            'waste_image',
            'cancellation_reason',
        ]

    def validate(self, data):
        instance = self.instance
        new_status = data.get('request_status', instance.request_status)

        # --- Status transition rules ---
        if instance.request_status == 'completed' and new_status not in ['completed']:
            raise serializers.ValidationError("Completed requests cannot be reverted.")

        if new_status == 'assigned' and not data.get('collector') and not instance.collector:
            raise serializers.ValidationError("Collector must be assigned when status is 'assigned'.")

        if new_status == 'in_progress' and not instance.collector:
            raise serializers.ValidationError("Cannot start request without an assigned collector.")

        if new_status == 'completed':
            # Must have collector
            if not instance.collector:
                raise serializers.ValidationError("Cannot complete request without a collector.")

            # Must have proof image
            if not instance.waste_image and not data.get('waste_image'):
                raise serializers.ValidationError("Completion requires a waste image as proof.")

            # Must be in progress before completion
            if instance.request_status != 'in_progress':
                raise serializers.ValidationError("Only requests in progress can be completed.")

            # --- GPS validation ---
            collector = instance.collector
            if collector.last_known_latitude is None or collector.last_known_longitude is None:
                raise serializers.ValidationError("Collector location not available.")

            client_point_coords = (instance.location.y, instance.location.x)  # (lat, lon)
            collector_point_coords = (
                float(collector.last_known_latitude),
                float(collector.last_known_longitude),
            )

            distance_m = geodesic(client_point_coords, collector_point_coords).meters

            if distance_m > 300:
                raise serializers.ValidationError(
                    "Completion rejected: collector too far from client (>300m)."
                )
            elif distance_m > 100:
                # Auto-flag suspected completion
                data['request_status'] = 'suspected'

        return data

