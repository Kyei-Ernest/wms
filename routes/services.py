from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance
from .models import Route, RouteStop
from client.models import Client

def auto_generate_stops(route):
    """
    Auto-generates stops for a route based on clients in the zone.
    - Finds clients within the zone boundary.
    - Orders stops by proximity to previous stop (simple nearest-neighbor).
    - Sets expected_minutes based on client property_type.
    """
    if not route.zone.boundary:
        raise ValueError("Zone must have a boundary to auto-generate stops.")

    # Find clients in zone (using geospatial contains)
    clients = Client.objects.filter(
        location__within=route.zone.boundary  # Assuming Client has PointField 'location'
    ).annotate(
        distance=Distance('location', route.zone.center_point)
    ).order_by('distance')  # Rough ordering by distance from center

    stops = []
    order = 1

    for client in clients:
        # Calculate expected time based on property_type (customize as needed)
        if client.property_type == 'residential':
            expected_minutes = 5
        elif client.property_type == 'commercial':
            expected_minutes = 10
        else:
            expected_minutes = 7


    stops = []
    order = 1
    for client in clients:
        stop = RouteStop(
            route=route,
            client=client,
            location=client.location,
            order=order,
            expected_minutes=expected_minutes,
            status='pending'
        )
        stops.append(stop)
        order += 1
    
    # Bulk create all stops at once (no signal here!)
    RouteStop.objects.bulk_create(stops)
    
    # ✅ NOW update metrics ONCE after all stops exist
    route.update_distance_and_duration()
    route.update_completion_status()
    route.save(update_fields=[
        'total_distance_km', 
        'estimated_duration', 
        'completion_percent', 
        'status'
    ])