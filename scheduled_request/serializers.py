from rest_framework import serializers
from .models import ScheduledRequest
from django.contrib.gis.geos import Point



class ScheduledRequestDetailSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    collector_name = serializers.CharField(source='collector.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)

    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = ScheduledRequest
        fields = [
            'id',
            'client',
            'client_name',
            'company',
            'company_name',
            'collector',
            'collector_name',
            #'subscription',
            'pickup_date',
            'pickup_time_slot',
            'recurrence',
            'address_line1',
            'landmark',
            'city',
            #'area_zone',
            'latitude',
            'longitude',
            'waste_type',
            'bin_size_liters',
            'bag_count',
            'request_status',
            'requested_at',
            'accepted_at',
            'completed_at',
            'cancelled_at',
            'cancellation_reason',
        ]

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None




class ScheduledRequestCreateSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(write_only=True)
    longitude = serializers.FloatField(write_only=True)

    class Meta:
        model = ScheduledRequest
        fields = [
            'client',
            'company',
            'collector',
            #'subscription',
            'pickup_date',
            'pickup_time_slot',
            'recurrence',
            'address_line1',
            'landmark',
            'city',
            #'area_zone',
            'latitude',
            'longitude',
            'waste_type',
            'bin_size_liters',
            'bag_count',
        ]

    def create(self, validated_data):
        lat = validated_data.pop('latitude')
        lng = validated_data.pop('longitude')
        validated_data['location'] = Point(lng, lat)  # Point(x=lon, y=lat)
        return super().create(validated_data)

class ScheduledRequestUpdateSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(write_only=True, required=False)
    longitude = serializers.FloatField(write_only=True, required=False)

    class Meta:
        model = ScheduledRequest
        fields = [
            'collector',
            'request_status',
            'cancellation_reason',
            'pickup_date',
            'pickup_time_slot',
            'latitude',
            'longitude',
        ]

    def update(self, instance, validated_data):
        lat = validated_data.pop('latitude', None)
        lng = validated_data.pop('longitude', None)
        if lat is not None and lng is not None:
            instance.location = Point(lng, lat)
        return super().update(instance, validated_data)

