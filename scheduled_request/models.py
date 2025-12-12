from django.db import models
from django.contrib.gis.db import models as gis_models
from django.utils import timezone


class ScheduledRequest(models.Model):
    REQUEST_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    # Core actors
    client = models.ForeignKey(
        'client.Client',
        on_delete=models.CASCADE,
        related_name='scheduled_requests'
    )
    company = models.ForeignKey(
        'waste_management_company.Company',
        on_delete=models.CASCADE,
        related_name='scheduled_requests'
    )
    collector = models.ForeignKey(
        'collector.Collector',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='scheduled_requests'
    )

    """# Future-proof: subscription link (optional for now)
    subscription = models.ForeignKey(
        'clients.Subscription',   # you’ll create this later
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='scheduled_requests'
    )"""

    # Scheduling details
    pickup_date = models.DateField()
    pickup_time_slot = models.CharField(max_length=50)  # e.g. "morning", "afternoon"
    recurrence = models.CharField(
        max_length=20,
        choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')],
        blank=True, null=True
    )

    # Location
    address_line1 = models.CharField(max_length=255)
    landmark = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    area_zone = models.CharField(max_length=100)
    location = gis_models.PointField(geography=True, null=True, blank=True)

    # Waste type choices
    WASTE_TYPE_CHOICES = [
        ('household', 'Household'),
        ('organic', 'Organic'),
        ('mixed', 'Mixed'),
        ('recyclable', 'Recyclable'),
        ('hazardous', 'Hazardous'),
        ('sanitary', 'Sanitary'),
        ('bulk', 'Bulk'),
        ('construction', 'Construction'),
        ('ewaste', 'E-Waste'),
    ]

    # Bin size choices (liters)
    BIN_SIZE_CHOICES = [
        (30, '30L Bin'),
        (60, '60L Bin'),
        (120, '120L Bin'),
        (240, '240L Bin'),
        (360, '360L Bin'),
        (660, '660L Bin'),
        (1100, '1100L Bin'),
    ]

    waste_type = models.CharField(
        max_length=50,
        choices=WASTE_TYPE_CHOICES
    )

    bin_size_liters = models.PositiveIntegerField(
        choices=BIN_SIZE_CHOICES
    )
    bag_count = models.PositiveIntegerField(default=0)

    # Status & timestamps
    request_status = models.CharField(
        max_length=20,
        choices=REQUEST_STATUS_CHOICES,
        default='pending'
    )
    requested_at = models.DateTimeField(default=timezone.now)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    cancellation_reason = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['pickup_date', 'pickup_time_slot']

    def __str__(self):
        return f"ScheduledRequest {self.id} for {self.client} on {self.pickup_date}"
