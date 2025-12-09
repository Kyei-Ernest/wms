from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator



from django.contrib.auth import get_user_model

User = get_user_model()


class Collector(models.Model):
    """
    Collector model supporting both:
    - Company-employed collectors
    - Independent/private collectors
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    @property
    def full_name(self):
        """Returns first + last name combined."""
        return f"{self.first_name} {self.last_name}".strip()


    # NEW: Supports company-employed or private collectors
    company = models.ForeignKey(
        'waste_management_company.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collectors'
    )

    # Supervisor applies only for company collectors
    supervisor = models.ForeignKey(
        'supervisor.Supervisor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collectors_under_supervision'
    )

    # If this is True → private collector (no company, no supervisor)
    is_private_collector = models.BooleanField(default=False)

    # ---- Fields you already had ----
    vehicle_number = models.CharField(max_length=50)
    vehicle_type = models.CharField(max_length=50)

    # This fits your "assigned_area_zone" but aligns naming with Client
    assigned_area_zone = models.CharField(max_length=100)


    # Part-time / Full-time / Contractor / PrivateCollector etc.
    employment_type = models.CharField(max_length=50)

    daily_wage_or_incentive_rate = models.DecimalField(
        max_digits=10, decimal_places=2
    )

    bank_account_details = models.TextField(blank=True, null=True)

    # ---- Performance ----
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    total_collections = models.IntegerField(default=0)

    # ---- Extra recommended operational data ----
    last_known_latitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        null=True, blank=True
    )
    last_known_longitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        null=True, blank=True
    )



    def __str__(self):
        col_type = "Private" if self.is_private_collector else "Company"
        return f"{self.user.username} - {col_type} Collector"

"""
class CollectorRating(models.Model):
    ""
    Client ratings and reviews for collectors
    Can be linked to either subscription collection or on-demand request
    ""
    rating_id = models.AutoField(primary_key=True)
    
    client = models.ForeignKey(
        'client.Client',
        on_delete=models.CASCADE,
        related_name='ratings_given'
    )
    
    collector = models.ForeignKey(
        'Collector',
        on_delete=models.CASCADE,
        related_name='ratings_received'
    )
    
    ""# Link to either collection record OR on-demand request
    collection_record = models.OneToOneField(
        'collections.CollectionRecord',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='rating',
        help_text="For subscription-based collections"
    )""
    
    on_demand_request = models.OneToOneField(
        'client.OnDemandRequest',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='rating',
        help_text="For one-time collection requests"
    )
    
    # Rating (1-5 stars)
    rating = models.IntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5)
        ],
        help_text="Rating from 1 to 5 stars"
    )
    
    review_text = models.TextField(
        blank=True,
        max_length=500,
        help_text="Optional review text"
    )
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['collector', '-created_at']),
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['rating']),
        ]
        # Ensure one rating per collection
        ""constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(collection_record__isnull=False, on_demand_request__isnull=True) |
                    models.Q(collection_record__isnull=True, on_demand_request__isnull=False)
                ),
                name='rating_must_link_to_one_source'
            )
        ]
    
    def __str__(self):
        source = f"Collection #{self.collection_record_id}" if self.collection_record else f"Request #{self.on_demand_request_id}"
        return f"{self.collector.user.username} - {self.rating}★ - {source}"
        ""
        """