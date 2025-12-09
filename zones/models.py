from django.contrib.gis.db import models as gis_models
from django.db import models
from django.core.validators import MinValueValidator


class Zone(models.Model):
    """
    Global geographic service zones with geospatial boundaries.
    Reusable by any company. Requires PostGIS extension.
    """
    zone_id = models.AutoField(primary_key=True)

    # Identification
    zone_code = models.CharField(
        max_length=20,
        unique=True,   # Now globally unique
        help_text="Unique zone code (e.g., ACC-OSU-01)"
    )
    name = models.CharField(
        max_length=100,
        help_text="Human-readable zone name (e.g., Osu Residential)"
    )
    description = models.TextField(blank=True)

    # Location hierarchy
    city = models.CharField(max_length=100)
    district = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)

    # Parent zone (hierarchical zone structure)
    parent_zone = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sub_zones'
    )

    # Zone characteristics
    ZONE_TYPE_CHOICES = [
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('industrial', 'Industrial'),
        ('mixed', 'Mixed Use'),
        ('institutional', 'Institutional'),
    ]
    zone_type = models.CharField(
        max_length=20,
        choices=ZONE_TYPE_CHOICES,
        default='residential'
    )

    # Geospatial fields
    boundary = gis_models.PolygonField(
        help_text="Polygon defining zone boundaries (GeoJSON/WKT)"
    )

    center_point = gis_models.PointField(
        null=False,
        blank=True,
        help_text="Center point of zone (auto-calculated if not provided)"
    )

    # Optional circular radius
    radius_meters = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Radius in meters (for circular zones only)"
    )

    # Operational data
    population_density = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low (<50 people/hectare)'),
            ('medium', 'Medium (50-150 people/hectare)'),
            ('high', 'High (>150 people/hectare)')
        ],
        default='medium'
    )

    estimated_households = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )

    # Pricing
    service_fee_multiplier = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=1.0,
        validators=[MinValueValidator(0.1)],
        help_text="Multiplier for base service fees"
    )

    # Collection days
    default_collection_days = models.JSONField(
        default=list,
        blank=True,
        help_text="Default collection days (e.g. ['monday', 'thursday'])"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the zone is actively serviced"
    )

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['city', 'name']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['city', 'zone_type']),
            models.Index(fields=['zone_code']),
        ]
        # Spatial index is automatically created in GIS models

    def __str__(self):
        return f"{self.zone_code} - {self.name}"

    def save(self, *args, **kwargs):
        """Auto-calculate center_point if not provided."""
        if not self.center_point and self.boundary:
            self.center_point = self.boundary.centroid
        super().save(*args, **kwargs)

    def get_area_km2(self):
        """Calculate area in square kilometers."""
        if self.boundary:
            boundary_transformed = self.boundary.transform(32630, clone=True)
            area_m2 = boundary_transformed.area
            return round(area_m2 / 1_000_000, 2)
        return 0

    def contains_point(self, latitude, longitude):
        """Check if latitude/longitude is inside the zone."""
        from django.contrib.gis.geos import Point
        point = Point(longitude, latitude, srid=4326)
        return self.boundary.contains(point)

    def distance_to_point(self, latitude, longitude):
        """Distance in meters from zone center to a point."""
        from django.contrib.gis.geos import Point
        if self.center_point:
            point = Point(longitude, latitude, srid=4326)
            center_t = self.center_point.transform(32630, clone=True)
            point_t = point.transform(32630, clone=True)
            return round(center_t.distance(point_t), 2)
        return None
