from datetime import timedelta
from django.contrib.gis.db import models as gis_models
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


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
    total_distance_km = models.DecimalField(max_digits=10, decimal_places=3, default=0)  # more precision
    estimated_duration = models.DurationField(default=timedelta)  # use DurationField for flexibility

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
        if len(stops) < 2:
            self.total_distance_km = 0
            self.estimated_duration = timedelta(minutes=0)
            return

        total_distance = 0.0
        for i in range(len(stops) - 1):
            # Get location from linked request if available
            loc1 = None
            loc2 = None

            if stops[i].ondemand_request and stops[i].ondemand_request.location:
                loc1 = stops[i].ondemand_request.location
            elif stops[i].scheduled_request and stops[i].scheduled_request.location:
                loc1 = stops[i].scheduled_request.location
            else:
                loc1 = stops[i].location  # fallback

            if stops[i+1].ondemand_request and stops[i+1].ondemand_request.location:
                loc2 = stops[i+1].ondemand_request.location
            elif stops[i+1].scheduled_request and stops[i+1].scheduled_request.location:
                loc2 = stops[i+1].scheduled_request.location
            else:
                loc2 = stops[i+1].location  # fallback

            if loc1 and loc2:
                total_distance += loc1.distance(loc2) / 1000  # meters → km

        self.total_distance_km = round(total_distance, 3)

        # Estimate duration = travel time + stop time
        total_stop_time = sum([s.expected_minutes for s in stops if s.expected_minutes])
        average_speed_kmh = 40  # configurable
        travel_time_minutes = (total_distance / average_speed_kmh) * 60

        total_minutes = travel_time_minutes + total_stop_time
        self.estimated_duration = timedelta(minutes=total_minutes)
        
    def update_completion_status(self):
        stops_total = self.stops.count()
        if stops_total == 0:
            self.completion_percent = 0
            return

        completed_stops = 0

        for stop in self.stops.all():
            # Check linked OnDemandRequest
            if stop.ondemand_request and stop.ondemand_request.request_status == "completed":
                completed_stops += 1
            # Check linked ScheduledRequest
            elif stop.scheduled_request and stop.scheduled_request.request_status == "completed":
                completed_stops += 1
            # Optional: if no request linked, fall back to stop.status
            elif stop.status == "completed":
                completed_stops += 1

        self.completion_percent = int((completed_stops / stops_total) * 100)

        # Auto-update route status, but preserve cancelled
        if self.status == 'cancelled':
            return
        if self.completion_percent == 100:
            self.status = 'completed'
        elif completed_stops > 0:
            self.status = 'in_progress'
        elif self.status == 'draft':
            pass
        else:
            self.status = 'assigned'

    

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)  # initial save
        self.update_distance_and_duration()
        self.update_completion_status()
        super().save(update_fields=['total_distance_km', 'estimated_duration', 'completion_percent', 'status'])




class RouteStop(models.Model):
    stop_id = models.AutoField(primary_key=True)
    route = models.ForeignKey('Route', on_delete=models.CASCADE, related_name='stops')

    # Link to either type of request
    ondemand_request = models.ForeignKey(
        'on_demand.OnDemandRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='route_stops'
    )
    scheduled_request = models.ForeignKey(
        'scheduled_request.ScheduledRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='route_stops'
    )

    # Route-specific metadata
    location = gis_models.PointField(srid=4326)
    order = models.PositiveIntegerField(help_text="1 means first stop in route")
    expected_minutes = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1)],
        help_text="Estimated time to complete this stop"
    )
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
        constraints = [
            models.UniqueConstraint(fields=['route', 'order'], name='unique_stop_order_per_route')
        ]

    def __str__(self):
        request_ref = (
            f"OnDemand #{self.ondemand_request_id}" if self.ondemand_request
            else f"Scheduled #{self.scheduled_request_id}" if self.scheduled_request
            else "Unlinked"
        )
        return f"Stop {self.order} for Route {self.route.route_id} ({request_ref})"
