from rest_framework import serializers
from .models import CollectionRecord

class CollectionRecordSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.user.get_full_name", read_only=True)
    collector_name = serializers.CharField(source="collector.user.get_full_name", read_only=True)
    route_id = serializers.IntegerField(source="route.route_id", read_only=True)
    stop_id = serializers.IntegerField(source="route_stop.stop_id", read_only=True)

    volume_description = serializers.SerializerMethodField()

    class Meta:
        model = CollectionRecord
        fields = [
            "collection_id",
            "client_name",
            "collector_name",
            "route_id",
            "stop_id",
            "collection_type",
            "scheduled_date",
            "collection_start",
            "collection_end",
            "collected_at",
            "status",
            "payment_method",
            "amount_paid",
            "bag_count",
            "bin_size_liters",
            "estimated_volume_liters",
            "waste_type",
            "photo_before",
            "photo_after",
            "segregation_score",
            "latitude",
            "longitude",
            "notes",
            "duration_minutes",
            "volume_description",
            "created_at",
            "updated_at",
        ]

    def get_volume_description(self, obj):
        return obj.get_volume_description()


class CollectionRecordCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectionRecord
        fields = [
            "payment_method",
            "amount_paid",
            "bag_count",
            "bin_size_liters",
            "estimated_volume_liters",
            "waste_type",
            "photo_before",
            "photo_after",
            "latitude",
            "longitude",
            "notes",
        ]

    def validate_amount_paid(self, value):
        if value < 0:
            raise serializers.ValidationError("Amount paid cannot be negative.")
        return value


class CollectionRecordSummarySerializer(serializers.Serializer):
    total = serializers.IntegerField()
    completed = serializers.IntegerField()
    pending = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    rejected = serializers.IntegerField()
