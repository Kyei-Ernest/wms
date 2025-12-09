from django.db import models
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.contrib.gis.db import models as gis_models

from django.contrib.auth import get_user_model

User = get_user_model()



class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)

    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)

    alternate_phone = models.CharField(max_length=17, blank=True, null=True)
    address_line1 = models.CharField(max_length=255)
    landmark = models.CharField(max_length=255, blank=True)
    area_zone = models.CharField(max_length=100)
    city = models.CharField(max_length=100)

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    property_type = models.CharField(max_length=20)
    subscription_plan = models.CharField(max_length=20)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    preferred_collection_time = models.TimeField(null=True, blank=True)

    segregation_compliance_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    registration_date = models.DateTimeField(auto_now_add=True)
    location = gis_models.PointField(srid=4326, null=True, blank=True, geography=True)  # Add this

    def save(self, *args, **kwargs):
        if self.latitude is not None and self.longitude is not None:
            from django.contrib.gis.geos import Point
            self.location = Point(float(self.longitude), float(self.latitude))
        super().save(*args, **kwargs)


"""

class WalletTransaction(models.Model):
    ""
    Tracks all wallet balance changes for clients
    ""
    transaction_id = models.AutoField(primary_key=True)
    
    client = models.ForeignKey(
        'Client',
        on_delete=models.CASCADE,
        related_name='wallet_transactions'
    )
    
    TRANSACTION_TYPE_CHOICES = [
        ('credit', 'Credit/Top-up'),
        ('debit', 'Debit/Payment'),
        ('refund', 'Refund'),
        ('adjustment', 'Manual Adjustment'),
    ]
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    
    # Amount (positive for credit, negative for debit)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Positive for credit, negative for debit"
    )
    
    # Balance tracking
    balance_before = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Related transactions
    "" related_subscription_payment = models.ForeignKey(
            'subscriptions.SubscriptionPayment',
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            related_name='wallet_transactions'
        )""
    
    related_on_demand_request = models.ForeignKey(
        'OnDemandRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_transactions'
    )
    
    # Payment details
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        help_text="Card, Bank Transfer, Cash, Momo."
    )
    transaction_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="External payment gateway reference"
    )
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('reversed', 'Reversed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    
    description = models.TextField(blank=True)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['transaction_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.client.user.username} - {self.transaction_type} - {self.amount}"


class OnDemandRequest(models.Model):
    ""
    One-time waste collection requests without subscription
    ""
    request_id = models.AutoField(primary_key=True)
    
    client = models.ForeignKey(
        'Client',
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
    
    # Pickup location (can be different from client's registered address)
    address_line1 = models.CharField(max_length=255)
    landmark = models.CharField(max_length=255, blank=True)
    area_zone = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Waste details
    estimated_weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    WASTE_TYPE_CHOICES = [
        ('dry', 'Dry Waste'),
        ('wet', 'Wet Waste'),
        ('mixed', 'Mixed Waste'),
        ('recyclable', 'Recyclable'),
        ('e-waste', 'E-Waste'),
        ('bulk', 'Bulk Waste'),
    ]
    waste_type = models.CharField(max_length=20, choices=WASTE_TYPE_CHOICES)
    
    special_instructions = models.TextField(blank=True)
    
    # Pricing
    quoted_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Price quoted to client"
    )
    
    final_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Final price after collection (may differ if weight varies)"
    )
    
    # Payment status
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )
    
    # Request status
    REQUEST_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('assigned', 'Assigned to Collector'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]
    request_status = models.CharField(
        max_length=20,
        choices=REQUEST_STATUS_CHOICES,
        default='pending'
    )
    
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
        return f"Request #{self.request_id} - {self.client.user.username} - {self.request_status}"
    
    def calculate_quoted_price(self):
        ""
        Calculate price based on weight and waste type
        Override this method with your pricing logic
        ""
        base_rate = Decimal('50.00')  # Base rate per kg
        
        type_multipliers = {
            'dry': Decimal('1.0'),
            'wet': Decimal('1.0'),
            'mixed': Decimal('1.2'),
            'recyclable': Decimal('0.8'),
            'e-waste': Decimal('2.0'),
            'bulk': Decimal('1.5'),
        }
        
        multiplier = type_multipliers.get(self.waste_type, Decimal('1.0'))
        return (base_rate * self.estimated_weight_kg * multiplier).quantize(Decimal('0.01'))
    
    def save(self, *args, **kwargs):
        # Auto-calculate quoted price if not set
        if not self.quoted_price and self.estimated_weight_kg:
            self.quoted_price = self.calculate_quoted_price()
        
        super().save(*args, **kwargs)
  


    """