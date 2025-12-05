from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import RouteStop, Route

@receiver([post_save, post_delete], sender=RouteStop)
def update_route_on_stop_change(sender, instance, **kwargs):
    """
    Automatically updates total_distance_km, estimated_duration,
    completion_percent, and status of the parent Route whenever a RouteStop changes.
    """
    route = instance.route
    route.save()  # triggers Route.save() which recalculates everything


