from django.db import models
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.contrib.gis.db.models import PointField
from django.contrib.gis.geos import Point


class OnDemandRequest(models.Model):
    """
    One-time waste collection requests without subscription.
    Pricing is based on bin size or bag count, adjusted by waste type multipliers.
    Location stored as lat/long and PointField for GIS queries.
    """

    request_id = models.AutoField(primary_key=True)

    client = models.ForeignKey(
        'client.Client',
        on_delete=models.CASCADE,
        related_name='on_demand_requests'
    )
    collector = models.ForeignKey(
        'collector.Collector',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='on_demand_requests'
    )

    # Pickup details
    pickup_date = models.DateField()
    TIME_SLOT_CHOICES = [
        ('morning', 'Morning (6 AM - 12 PM)'),
        ('afternoon', 'Afternoon (12 PM - 5 PM)'),
        ('evening', 'Evening (5 PM - 8 PM)'),
    ]
    pickup_time_slot = models.CharField(max_length=20, choices=TIME_SLOT_CHOICES)

    # Pickup location
    address_line1 = models.CharField(max_length=255)
    landmark = models.CharField(max_length=255, blank=True)
    area_zone = models.CharField(max_length=100)
    city = models.CharField(max_length=100)

    # Store both lat/long and PointField
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location = PointField(geography=True, null=True, blank=True, help_text="GIS point (lon, lat)")

    # Waste details
    bag_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    BIN_SIZE_CHOICES = [(120, '120L'), (240, '240L'), (360, '360L'), (660, '660L'), (1100, '1100L')]
    bin_size_liters = models.IntegerField(null=True, blank=True, choices=BIN_SIZE_CHOICES)

    WASTE_TYPES = [
        ('wet', 'Organic Waste'),
        ('mixed', 'Mixed Waste'),
        ('recyclable', 'Recyclable Waste'),
        ('e_waste', 'E-Waste'),
        ('bulk', 'Bulk Waste'),
        ('sanitary', 'Sanitary/Biomedical Waste'),
        ('hazardous', 'Hazardous Household Waste'),
        ('construction', 'Construction & Demolition Waste'),
        ('household', 'General Household Waste'),
    ]
    waste_type = models.CharField(max_length=20, choices=WASTE_TYPES)

    special_instructions = models.TextField(blank=True)

    # Image upload
    waste_image = models.ImageField(
        upload_to='on_demand/waste_images/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text="Photo of the waste provided by client"
    )

    # Pricing
    quoted_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Payment status
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')

    # Request status
    REQUEST_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('assigned', 'Assigned to Collector'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    ]
    request_status = models.CharField(max_length=20, choices=REQUEST_STATUS_CHOICES, default='pending')

    # Timestamps
    requested_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['client', '-requested_at']),
            models.Index(fields=['collector', 'request_status']),
            models.Index(fields=['pickup_date', 'request_status']),
            models.Index(fields=['area_zone', 'pickup_date']),
        ]

    def __str__(self):
        return f"OnDemand #{self.request_id} - {self.client.user.username} - {self.request_status}"

    def calculate_quoted_price(self):
        """
        Calculate price based on bin size or bag count, adjusted by waste type.
        """
        base_rate_per_bag = Decimal('20.00')   # GHS per bag
        base_rate_per_bin = {
            120: Decimal('25.00'),
            240: Decimal('40.00'),
            360: Decimal('60.00'),
            660: Decimal('100.00'),
            1100: Decimal('150.00'),
        }

        type_multipliers = {
            'wet': Decimal('1.0'),
            'mixed': Decimal('1.2'),
            'recyclable': Decimal('0.8'),
            'e_waste': Decimal('2.0'),
            'bulk': Decimal('1.5'),
            'sanitary': Decimal('1.3'),
            'hazardous': Decimal('2.5'),
            'construction': Decimal('1.8'),
            'household': Decimal('1.0'),
        }

        if self.bin_size_liters:
            base_price = base_rate_per_bin.get(self.bin_size_liters, Decimal('25.00'))
        else:
            base_price = base_rate_per_bag * Decimal(self.bag_count or 1)

        multiplier = type_multipliers.get(self.waste_type, Decimal('1.0'))
        return (base_price * multiplier).quantize(Decimal('0.01'))

    def save(self, *args, **kwargs):
        # Auto-set quoted price
        if not self.quoted_price:
            self.quoted_price = self.calculate_quoted_price()

        # Auto-populate PointField from lat/long if provided
        if self.latitude and self.longitude:
            self.location = Point(float(self.longitude), float(self.latitude))

        if self.request_status == 'cancelled' and not self.cancelled_at:
            self.cancelled_at = timezone.now()
        if self.request_status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()

        super().save(*args, **kwargs)

