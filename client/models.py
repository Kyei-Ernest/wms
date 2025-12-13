from django.db import models
from decimal import Decimal
from django.contrib.gis.db import models as gis_models

from django.contrib.auth import get_user_model


from django.conf import settings

User = get_user_model()



class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)

    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)

    alternate_phone = models.CharField(max_length=17, blank=True, null=True)
     
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    segregation_compliance_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    registration_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.phone_number})"





    