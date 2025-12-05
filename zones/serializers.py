from rest_framework_gis.serializers import GeoFeatureModelSerializer
from django.contrib.gis.geos import Polygon
from .models import Zone

class ZoneCreateSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Zone
        geo_field = "boundary"   # Accept GeoJSON boundary
        fields = [
            "zone_code", "name", "description",
            "city", "district", "region",
            "parent_zone", "zone_type",
            "boundary", "center_point", "radius_meters",
            "population_density", "estimated_households",
            "service_fee_multiplier", "default_collection_days",
        ]
        read_only_fields = ["center_point"]

    def create(self, validated_data):
        boundary_data = validated_data.pop('boundary', None)
        if boundary_data:
            # Convert GeoJSON dict to Polygon
            coords = boundary_data.get('coordinates', [])
            # GeoJSON Polygon: [ [ [lng, lat], ... ] ] -> outer ring
            polygon = Polygon(coords[0])
            validated_data['boundary'] = polygon
        return super().create(validated_data)


class ZoneUpdateSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Zone
        geo_field = "boundary"
        fields = [
            "name", "description",
            "city", "district", "region",
            "parent_zone", "zone_type",
            "boundary", "center_point", "radius_meters",
            "population_density", "estimated_households",
            "service_fee_multiplier", "default_collection_days",
            "is_active",
        ]


class ZoneListSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Zone
        geo_field = "boundary"
        fields = [
            "zone_id", "zone_code",
            "name", "description",
            "city", "district", "region",
            "zone_type",
            "center_point",
            "radius_meters",
            "population_density",
            "estimated_households",
            "service_fee_multiplier",
            "default_collection_days",
            "is_active",
            "created_at", "updated_at",
        ]
