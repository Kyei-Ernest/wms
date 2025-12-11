from rest_framework import serializers
from django.utils import timezone
from .models import CollectionRecord


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
        # Prefer stored duration_minutes; fall back to computed for legacy data
        if obj.duration_minutes is not None:
            return obj.duration_minutes
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
            'latitude',
            'longitude',
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
        if obj.duration_minutes is not None:
            return obj.duration_minutes
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
            'status',            # pending, in_progress, completed, skipped, cancelled, rejected
            'latitude',
            'longitude',
            'notes',
        ]

    def validate(self, data):
        # Route linkage implies scheduled
        if data.get('route') and data.get('collection_type') != 'scheduled':
            raise serializers.ValidationError("Collections linked to routes must be 'scheduled' type")

        # Require collector for any non-pending status
        if data.get('status') != 'pending' and not data.get('collector'):
            raise serializers.ValidationError("Collector is required for non-pending collections")

        # If completed, ensure waste data and evidence
        if data.get('status') == 'completed':
            if data.get('bag_count', 0) == 0 and not data.get('bin_size_liters'):
                raise serializers.ValidationError(
                    "Either bag_count or bin_size_liters is required for completed status"
                )
            if not data.get('photo_before') and not data.get('segregation_score'):
                # You can choose photo_after instead; tweak to your policy
                raise serializers.ValidationError(
                    "At least one evidence field (photo_before or segregation_score) is required for completed status"
                )

        return data

    def create(self, validated_data):
        route_stop = validated_data.get('route_stop')
        collection = CollectionRecord.objects.create(**validated_data)

        # Sync RouteStop status if linked
        if route_stop:
            status = collection.status
            if status == 'completed':
                route_stop.status = 'completed'
                route_stop.actual_end = timezone.now()
            elif status in ['skipped', 'cancelled', 'rejected']:
                # Map rejected to skipped or a dedicated status if your RouteStop supports it
                route_stop.status = 'skipped' if status in ['skipped', 'rejected'] else 'cancelled'
            elif status == 'in_progress':
                route_stop.status = 'in_progress'
                route_stop.actual_start = route_stop.actual_start or timezone.now()
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
            'status',   # pending, in_progress, completed, skipped, cancelled, rejected
            'latitude',
            'longitude',
            'notes',
        ]

    def validate_status(self, value):
        instance = self.instance
        if instance:
            # No reverting from completed to pending/in_progress
            if instance.status == 'completed' and value in ['pending', 'in_progress']:
                raise serializers.ValidationError("Cannot revert a completed collection to pending/in_progress")

            # Completed cannot become skipped/cancelled/rejected
            if instance.status == 'completed' and value in ['skipped', 'cancelled', 'rejected']:
                raise serializers.ValidationError("Cannot change a completed collection to skipped/cancelled/rejected")

        return value

    def validate(self, data):
        instance = self.instance
        new_status = data.get('status', instance.status)

        # If moving to completed, ensure data integrity
        if new_status == 'completed':
            bag_count = data.get('bag_count', instance.bag_count)
            bin_size = data.get('bin_size_liters', instance.bin_size_liters)
            if (bag_count or 0) == 0 and not bin_size:
                raise serializers.ValidationError(
                    "Either bag_count or bin_size_liters is required for completed status"
                )

            photo_before = data.get('photo_before', instance.photo_before)
            photo_after = data.get('photo_after', instance.photo_after)
            segregation_score = data.get('segregation_score', instance.segregation_score)
            if not photo_before and not photo_after and segregation_score is None:
                raise serializers.ValidationError(
                    "Provide at least one evidence: photo_before, photo_after, or segregation_score"
                )

        return data

    def update(self, instance, validated_data):
        old_status = instance.status
        new_status = validated_data.get('status', old_status)

        # Apply updates
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # If collection_end set, ensure duration_minutes saved by model's save()
        instance.save()

        # Sync RouteStop if linked and status changed
        if old_status != new_status and instance.route_stop:
            route_stop = instance.route_stop

            if new_status == 'completed':
                route_stop.status = 'completed'
                route_stop.actual_end = timezone.now()
            elif new_status == 'in_progress':
                route_stop.status = 'in_progress'
                route_stop.actual_start = route_stop.actual_start or timezone.now()
            elif new_status in ['skipped', 'rejected']:
                route_stop.status = 'skipped'
            elif new_status == 'cancelled':
                route_stop.status = 'cancelled'

            route_stop.save()

        return instance


class CollectionRecordBulkCreateSerializer(serializers.Serializer):
    """
    Serializer for bulk creating collections (e.g., for entire route)
    """
    route_id = serializers.IntegerField()
    collections = CollectionRecordCreateSerializer(many=True)

    def validate_route_id(self, value):
        from routes.models import Route
        try:
            Route.objects.get(route_id=value)
        except Route.DoesNotExist:
            raise serializers.ValidationError("Route does not exist")
        return value

    def create(self, validated_data):
        from routes.models import Route
        route = Route.objects.get(route_id=validated_data['route_id'])
        collections_data = validated_data['collections']

        created_collections = []
        for collection_data in collections_data:
            collection_data['route'] = route
            collection_data['collection_type'] = 'scheduled'
            # Default initial status for scheduled items
            collection_data.setdefault('status', 'pending')

            serializer = CollectionRecordCreateSerializer(data=collection_data)
            serializer.is_valid(raise_exception=True)
            collection = serializer.save()
            created_collections.append(collection)

        return created_collections


class CollectionRecordStatsSerializer(serializers.Serializer):
    """
    Serializer for collection statistics
    """
    total_collections = serializers.IntegerField()
    completed = serializers.IntegerField()
    skipped = serializers.IntegerField()
    pending = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    rejected = serializers.IntegerField()
    total_bags = serializers.IntegerField()
    avg_segregation_score = serializers.FloatField()
    avg_duration_minutes = serializers.FloatField()
