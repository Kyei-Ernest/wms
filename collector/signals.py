"""from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Avg
from .models import CollectorRating


@receiver(post_save, sender=CollectorRating)
def update_collector_rating_on_save(sender, instance, created, **kwargs):
    ""
    Update collector's average rating when a rating is created or updated
    ""
    update_collector_average_rating(instance.collector)


@receiver(post_delete, sender=CollectorRating)
def update_collector_rating_on_delete(sender, instance, **kwargs):
    ""
    Update collector's average rating when a rating is deleted
    ""
    update_collector_average_rating(instance.collector)


def update_collector_average_rating(collector):
    ""
    Helper function to recalculate and update collector's average rating
    ""
    ratings = CollectorRating.objects.filter(collector=collector)
    
    if ratings.exists():
        avg_rating = ratings.aggregate(avg=Avg('rating'))['avg']
        collector.average_rating = round(avg_rating, 2)
    else:
        # No ratings, reset to 0
        collector.average_rating = 0.0
    
    # Use update_fields to avoid triggering other signals/logic
    collector.save(update_fields=['average_rating'])"""