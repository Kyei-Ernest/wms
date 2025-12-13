from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import RouteStop, Route

@receiver(post_save, sender=RouteStop)
def update_route_on_stop_change(sender, instance, created, **kwargs):
    # Skip if this is part of bulk creation
    if kwargs.get('raw', False):
        return
    
    if instance.route:
        route = instance.route
        route.update_completion_status()
        route.update_distance_and_duration()
        # Use update_fields to avoid re-triggering the full save logic
        route.save(update_fields=['total_distance_km', 'estimated_duration', 'completion_percent', 'status'])