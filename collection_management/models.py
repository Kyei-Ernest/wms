from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class CollectionRecord(models.Model):
    """
    Immutable record of a waste collection tied to a route stop.
    Captures operational evidence, payment info, and audit data.
    """

    collection_id = models.AutoField(primary_key=True)

    # Relationships
    client = models.ForeignKey(
        'client.Client',
        on_delete=models.CASCADE,
        related_name='collections'
    )
    collector = models.ForeignKey(
        'collector.Collector',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='collections'
    )
    route = models.ForeignKey(
        'routes.Route',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='collections'
    )
    route_stop = models.OneToOneField(
        'routes.RouteStop',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='collection_record'
    )

    # Payment (collector indicates at completion)
    PAYMENT_CHOICES = [
        ('cash', 'Cash'),
        ('momo', 'Mobile Money'),
        ('bank', 'Bank Transfer'),
        ('later', 'Invoice Later'),
    ]
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_CHOICES,
        default='later',
        help_text="Payment method indicated by collector"
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Amount paid by client at collection"
    )

    # Collection type
    COLLECTION_TYPE_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('on_demand', 'On-Demand'),
    ]
    collection_type = models.CharField(max_length=20, choices=COLLECTION_TYPE_CHOICES)

    # Timestamps
    scheduled_date = models.DateField(help_text="Scheduled collection date")
    collection_start = models.DateTimeField(null=True, blank=True)
    collection_end = models.DateTimeField(null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)

    # Waste quantity
    bag_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    BIN_SIZE_CHOICES = [(120, '120L'), (240, '240L'), (360, '360L'), (660, '660L'), (1100, '1100L')]
    bin_size_liters = models.IntegerField(null=True, blank=True, choices=BIN_SIZE_CHOICES)
    estimated_volume_liters = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Waste type
    WASTE_TYPE_CHOICES = [
        ('mixed', 'Mixed Waste'),
        ('organic', 'Organic'),
        ('recyclable', 'Recyclable'),
        ('plastic', 'Plastic'),
        ('e-waste', 'E-Waste'),
        ('bulk', 'Bulk Waste'),
    ]
    waste_type = models.CharField(max_length=20, choices=WASTE_TYPE_CHOICES, default='mixed')

    # Photos
    photo_before = models.ImageField(upload_to='collections/photos/before/%Y/%m/%d/', null=True, blank=True)
    photo_after = models.ImageField(upload_to='collections/photos/after/%Y/%m/%d/', null=True, blank=True)

    # Quality score
    segregation_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    # Status (aligned with RouteStop)
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # GPS verification
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    notes = models.TextField(blank=True, null=True)

    # Audit
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # Derived metrics
    duration_minutes = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-collected_at', '-created_at']
        indexes = [
            models.Index(fields=['client', '-collected_at']),
            models.Index(fields=['collector', '-collected_at']),
            models.Index(fields=['route', 'status']),
            models.Index(fields=['scheduled_date', 'status']),
            models.Index(fields=['collection_type', 'status']),
        ]

    def __str__(self):
        return f"Collection #{self.collection_id} - {self.client.user.username} - {self.status}"

    def save(self, *args, **kwargs):
        # Auto-set collected_at and duration
        if self.status == 'completed' and not self.collected_at:
            self.collected_at = timezone.now()
        if self.collection_start and self.collection_end:
            delta = self.collection_end - self.collection_start
            self.duration_minutes = int(delta.total_seconds() / 60)
        super().save(*args, **kwargs)

    def get_volume_description(self):
        parts = []
        if self.bag_count:
            parts.append(f"{self.bag_count} bag{'s' if self.bag_count > 1 else ''}")
        if self.bin_size_liters:
            parts.append(f"{self.bin_size_liters}L bin")
        if self.estimated_volume_liters:
            parts.append(f"~{self.estimated_volume_liters}L")
        return ", ".join(parts) if parts else "No volume data"

    def verify_location(self, threshold_meters=100):
        """Check if GPS location matches client address within threshold."""
        if not (self.latitude and self.longitude and self.client.latitude and self.client.longitude):
            return None
        from math import radians, sin, cos, sqrt, atan2
        R = 6371000
        lat1, lon1 = radians(float(self.latitude)), radians(float(self.longitude))
        lat2, lon2 = radians(float(self.client.latitude)), radians(float(self.client.longitude))
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        return distance <= threshold_meters
