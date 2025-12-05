from django.contrib.gis.db import models as gis_models
from django.db import models
from django.db.models import Sum
from django.core.validators import MinValueValidator, MaxValueValidator
from zones.models import Zone


class Route(models.Model):
    route_id = models.AutoField(primary_key=True)

    company = models.ForeignKey('waste_management_company.Company', on_delete=models.CASCADE)
    zone = models.ForeignKey('zones.Zone', on_delete=models.CASCADE)

    supervisor = models.ForeignKey('supervisor.Supervisor', on_delete=models.CASCADE)
    collector = models.ForeignKey('collector.Collector', on_delete=models.CASCADE)

    route_date = models.DateField(db_index=True)

    # Timing
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)

    # Progress
    completion_percent = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)

    # Analytics
    total_distance_km = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    estimated_duration = models.IntegerField(help_text="Minutes", default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-route_date', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['collector', 'route_date'],
                name='unique_route_per_collector_per_day'
            )
        ]

    def update_distance_and_duration(self):
        stops = list(self.stops.all().order_by('order'))
        total_distance = 0.0

        # Calculate distance using PostGIS Distance
        for i in range(len(stops) - 1):
            if stops[i].location and stops[i+1].location:
                # Distance returns in meters; convert to km
                total_distance += stops[i].location.distance(stops[i+1].location) / 1000

        self.total_distance_km = round(total_distance, 2)

        # Calculate estimated duration
        total_stop_time = stops.aggregate(total=Sum('expected_minutes'))['total'] or 0
        average_speed_kmh = 40
        travel_time_minutes = (total_distance / average_speed_kmh) * 60
        self.estimated_duration = int(travel_time_minutes + total_stop_time)

    def update_completion_status(self):
        stops_total = self.stops.count()
        if stops_total == 0:
            self.completion_percent = 0
            return

        completed_stops = self.stops.filter(status='completed').count()
        self.completion_percent = int((completed_stops / stops_total) * 100)

        # Auto-update status
        if self.completion_percent == 100:
            self.status = 'completed'
        elif completed_stops > 0:
            self.status = 'in_progress'
        elif self.status == 'draft':
            pass
        else:
            self.status = 'assigned'

    def save(self, *args, **kwargs):
        self.update_distance_and_duration()
        self.update_completion_status()
        super().save(*args, **kwargs)


class RouteStop(models.Model):
    stop_id = models.AutoField(primary_key=True)
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='stops')
    client = models.ForeignKey('client.Client', on_delete=models.SET_NULL, null=True, blank=True)
    location = gis_models.PointField(srid=4326, null=True, blank=True)
    order = models.PositiveIntegerField(help_text="1 means first stop")
    expected_minutes = models.IntegerField(default=5, validators=[MinValueValidator(1)],
                                           help_text="Estimated time to complete this stop")
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']
        unique_together = ['route', 'order']

    def __str__(self):
        return f"Stop {self.order} for Route {self.route_id}"
