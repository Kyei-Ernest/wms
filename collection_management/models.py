# collections/models.py

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class CollectionRecord(models.Model):
    """
    Records of waste collections - both subscription-based and on-demand
    Adapted for Ghana's waste management practices
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
        null=True,
        blank=True,
        related_name='collections'
    )
    
    route = models.ForeignKey(
        'routes.Route',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collections',
        help_text="For subscription-based scheduled collections"
    )
    
    route_stop = models.OneToOneField(
        'routes.RouteStop',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collection_record',
        help_text="Links to specific stop in route"
    )

    payment_method = models.CharField(                 
        max_length=20,
        choices=[('cash', 'Cash'), ('momo', 'Mobile Money'), ('bank', 'Bank Transfer'), ('later', 'Invoice Later')],
        default='later'
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # on_demand_request = models.OneToOneField(
    #     'clients.OnDemandRequest',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='collection_record'
    # )
    
    # Collection type
    COLLECTION_TYPE_CHOICES = [
        ('scheduled', 'Scheduled Collection'),
        ('on_demand', 'On-Demand Collection'),
        ('emergency', 'Emergency Collection'),
    ]
    collection_type = models.CharField(
        max_length=20,
        choices=COLLECTION_TYPE_CHOICES
    )
    
    # Timestamps
    scheduled_date = models.DateField(
        help_text="Scheduled collection date"
    )
    
    collection_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When collector arrived"
    )
    
    collection_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When collection completed"
    )
    
    collected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Actual collection timestamp"
    )
    
    # Waste quantity - Ghana reality (volume/bag based)
    bag_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of waste bags collected"
    )
    
    BIN_SIZE_CHOICES = [
        (120, '120 Liters'),
        (240, '240 Liters'),
        (360, '360 Liters'),
        (660, '660 Liters'),
        (1100, '1100 Liters'),
    ]
    bin_size_liters = models.IntegerField(
        null=True,
        blank=True,
        choices=BIN_SIZE_CHOICES,
        help_text="Standard bin size if applicable"
    )
    
    estimated_volume_liters = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Estimated volume in liters"
    )
    
    # Waste type
    WASTE_TYPE_CHOICES = [
        ('mixed', 'Mixed Waste'),
        ('organic', 'Organic/Wet Waste'),
        ('recyclable', 'Recyclable'),
        ('plastic', 'Plastic'),
        ('e-waste', 'E-Waste'),
        ('bulk', 'Bulk Waste'),
    ]
    waste_type = models.CharField(
        max_length=20,
        choices=WASTE_TYPE_CHOICES,
        default='mixed'
    )
    
    # Photos
    photo_before = models.ImageField(
        upload_to='collections/photos/before/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text="Photo before collection"
    )
    
    photo_after = models.ImageField(
        upload_to='collections/photos/after/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text="Photo after collection"
    )
    
    # Quality score
    segregation_score = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Waste segregation quality (0-100)"
    )
    
    # Status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('collected', 'Collected'),
        ('missed', 'Missed'),
        ('rejected', 'Rejected - Poor Segregation'),
        ('partial', 'Partial Collection'),
        ('skipped', 'Skipped'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # GPS verification
    gps_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="GPS location where collection occurred"
    )
    
    gps_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="GPS location where collection occurred"
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes or issues"
    )
    
    # Audit
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
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
        # Auto-set collected_at when status becomes 'collected'
        if self.status == 'collected' and not self.collected_at:
            self.collected_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def get_duration_minutes(self):
        """Calculate collection duration in minutes"""
        if self.collection_start and self.collection_end:
            delta = self.collection_end - self.collection_start
            return int(delta.total_seconds() / 60)
        return None
    
    def get_volume_description(self):
        """Human-readable volume description"""
        parts = []
        
        if self.bag_count:
            parts.append(f"{self.bag_count} bag{'s' if self.bag_count > 1 else ''}")
        
        if self.bin_size_liters:
            parts.append(f"{self.bin_size_liters}L bin")
        
        if self.estimated_volume_liters:
            parts.append(f"~{self.estimated_volume_liters}L")
        
        return ", ".join(parts) if parts else "No volume data"
    
    def verify_location(self):
        """Check if GPS location matches client address"""
        if not (self.gps_latitude and self.gps_longitude):
            return None
        
        if not (self.client.latitude and self.client.longitude):
            return None
        
        # Calculate distance
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371000  # Earth radius in meters
        
        lat1 = radians(float(self.gps_latitude))
        lon1 = radians(float(self.gps_longitude))
        lat2 = radians(float(self.client.latitude))
        lon2 = radians(float(self.client.longitude))
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        # Within 100 meters is acceptable
        return distance <= 100