from rest_framework import serializers
from .models import CollectionRecord
from django.utils import timezone


class CollectionRecordListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing collections
    """
    client_name = serializers.CharField(source='client.user.get_full_name', read_only=True)
    client_phone = serializers.CharField(source='client.user.phone_number', read_only=True)
    collector_name = serializers.CharField(source='collector.user.get_full_name', read_only=True)
    route_id = serializers.IntegerField(source='route.route_id', read_only=True)
    duration_minutes = serializers.SerializerMethodField()
    volume_description = serializers.SerializerMethodField()
    
    class Meta:
        model = CollectionRecord
        fields = [
            'collection_id',
            'client',
            'client_name',
            'client_phone',
            'collector',
            'collector_name',
            'route_id',
            'collection_type',
            'scheduled_date',
            'collected_at',
            'bag_count',
            'bin_size_liters',
            'waste_type',
            'status',
            'segregation_score',
            'duration_minutes',
            'volume_description',
            'created_at',
        ]
        read_only_fields = ['collection_id', 'created_at', 'collected_at']
    
    def get_duration_minutes(self, obj):
        return obj.get_duration_minutes()
    
    def get_volume_description(self, obj):
        return obj.get_volume_description()


class CollectionRecordDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for viewing a specific collection
    """
    client_name = serializers.CharField(source='client.user.get_full_name', read_only=True)
    client_phone = serializers.CharField(source='client.user.phone_number', read_only=True)
    client_address = serializers.CharField(source='client.address_line1', read_only=True)
    collector_name = serializers.CharField(source='collector.user.get_full_name', read_only=True)
    collector_phone = serializers.CharField(source='collector.user.phone_number', read_only=True)
    route_id = serializers.IntegerField(source='route.route_id', read_only=True)
    route_date = serializers.DateField(source='route.route_date', read_only=True)
    duration_minutes = serializers.SerializerMethodField()
    volume_description = serializers.SerializerMethodField()
    location_verified = serializers.SerializerMethodField()
    
    class Meta:
        model = CollectionRecord
        fields = [
            'collection_id',
            'client',
            'client_name',
            'client_phone',
            'client_address',
            'collector',
            'collector_name',
            'collector_phone',
            'route',
            'route_id',
            'route_date',
            'route_stop',
            'collection_type',
            'scheduled_date',
            'collection_start',
            'collection_end',
            'collected_at',
            'bag_count',
            'bin_size_liters',
            'estimated_volume_liters',
            'waste_type',
            'photo_before',
            'photo_after',
            'segregation_score',
            'status',
            'gps_latitude',
            'gps_longitude',
            'notes',
            'duration_minutes',
            'volume_description',
            'location_verified',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'collection_id',
            'created_at',
            'updated_at',
            'collected_at',
        ]
    
    def get_duration_minutes(self, obj):
        return obj.get_duration_minutes()
    
    def get_volume_description(self, obj):
        return obj.get_volume_description()
    
    def get_location_verified(self, obj):
        return obj.verify_location()


class CollectionRecordCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new collections
    """
    class Meta:
        model = CollectionRecord
        fields = [
            'client',
            'collector',
            'route',
            'route_stop',
            'collection_type',
            'scheduled_date',
            'collection_start',
            'bag_count',
            'bin_size_liters',
            'estimated_volume_liters',
            'waste_type',
            'photo_before',
            'segregation_score',
            'status',
            'gps_latitude',
            'gps_longitude',
            'notes',
        ]
    
    def validate(self, data):
        """Custom validation"""
        # If route is provided, collection_type should be 'scheduled'
        if data.get('route') and data.get('collection_type') != 'scheduled':
            raise serializers.ValidationError(
                "Collections linked to routes must be 'scheduled' type"
            )
        
        # Ensure collector is provided (unless status is 'pending')
        if data.get('status') != 'pending' and not data.get('collector'):
            raise serializers.ValidationError(
                "Collector is required for non-pending collections"
            )
        
        # If status is 'collected', ensure we have waste data
        if data.get('status') == 'collected':
            if data.get('bag_count', 0) == 0 and not data.get('bin_size_liters'):
                raise serializers.ValidationError(
                    "Either bag_count or bin_size_liters is required for collected status"
                )
        
        return data
    
    def create(self, validated_data):
        """Create collection and link to route stop if applicable"""
        route_stop = validated_data.get('route_stop')
        collection = CollectionRecord.objects.create(**validated_data)
        
        # Update route stop status if linked
        if route_stop:
            if collection.status == 'collected':
                route_stop.status = 'completed'
            elif collection.status in ['missed', 'skipped']:
                route_stop.status = 'skipped'
            elif collection.status == 'rejected':
                route_stop.status = 'failed'
            route_stop.save()
        
        return collection


class CollectionRecordUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating existing collections
    """
    class Meta:
        model = CollectionRecord
        fields = [
            'collector',
            'collection_start',
            'collection_end',
            'bag_count',
            'bin_size_liters',
            'estimated_volume_liters',
            'waste_type',
            'photo_before',
            'photo_after',
            'segregation_score',
            'status',
            'gps_latitude',
            'gps_longitude',
            'notes',
        ]
    
    def validate_status(self, value):
        """Validate status transitions"""
        instance = self.instance
        if instance:
            # Can't change from 'collected' back to 'pending'
            if instance.status == 'collected' and value == 'pending':
                raise serializers.ValidationError(
                    "Cannot change status from 'collected' back to 'pending'"
                )
            
            # Can't change from 'collected' to 'missed'
            if instance.status == 'collected' and value in ['missed', 'skipped']:
                raise serializers.ValidationError(
                    "Cannot change collected items to missed/skipped"
                )
        
        return value
    
    def validate(self, data):
        """Custom validation for updates"""
        instance = self.instance
        new_status = data.get('status', instance.status)
        
        # If changing to 'collected', ensure we have required data
        if new_status == 'collected':
            bag_count = data.get('bag_count', instance.bag_count)
            bin_size = data.get('bin_size_liters', instance.bin_size_liters)
            
            if bag_count == 0 and not bin_size:
                raise serializers.ValidationError(
                    "Either bag_count or bin_size_liters is required for collected status"
                )
            
            # Should have at least one photo
            photo_before = data.get('photo_before', instance.photo_before)
            photo_after = data.get('photo_after', instance.photo_after)
            
            if not photo_before and not photo_after:
                raise serializers.ValidationError(
                    "At least one photo (before or after) is required for collected status"
                )
        
        return data
    
    def update(self, instance, validated_data):
        """Update collection and sync with route stop"""
        old_status = instance.status
        new_status = validated_data.get('status', old_status)
        
        # Update the collection
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update linked route stop if status changed
        if old_status != new_status and instance.route_stop:
            route_stop = instance.route_stop
            
            if new_status == 'collected':
                route_stop.status = 'completed'
                route_stop.actual_end = timezone.now()
            elif new_status in ['missed', 'skipped']:
                route_stop.status = 'skipped'
            elif new_status == 'rejected':
                route_stop.status = 'failed'
            
            route_stop.save()
        
        return instance


class CollectionRecordBulkCreateSerializer(serializers.Serializer):
    """
    Serializer for bulk creating collections (e.g., for entire route)
    """
    route_id = serializers.IntegerField()
    collections = CollectionRecordCreateSerializer(many=True)
    
    def validate_route_id(self, value):
        """Ensure route exists"""
        from routes.models import Route
        try:
            Route.objects.get(route_id=value)
        except Route.DoesNotExist:
            raise serializers.ValidationError("Route does not exist")
        return value
    
    def create(self, validated_data):
        """Bulk create collections for a route"""
        from routes.models import Route
        
        route = Route.objects.get(route_id=validated_data['route_id'])
        collections_data = validated_data['collections']
        
        created_collections = []
        for collection_data in collections_data:
            collection_data['route'] = route
            collection_data['collection_type'] = 'scheduled'
            
            serializer = CollectionRecordCreateSerializer(data=collection_data)
            if serializer.is_valid(raise_exception=True):
                collection = serializer.save()
                created_collections.append(collection)
        
        return created_collections


class CollectionRecordStatsSerializer(serializers.Serializer):
    """
    Serializer for collection statistics
    """
    total_collections = serializers.IntegerField()
    collected = serializers.IntegerField()
    missed = serializers.IntegerField()
    pending = serializers.IntegerField()
    rejected = serializers.IntegerField()
    total_bags = serializers.IntegerField()
    avg_segregation_score = serializers.FloatField()
    avg_duration_minutes = serializers.FloatField()