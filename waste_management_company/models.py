from django.db import models

from django.contrib.auth import get_user_model

User = get_user_model()
  

# COMPANY MODEL (PROFILE)
class Company(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    company_name = models.CharField(max_length=255)
    gst_number = models.CharField(max_length=100)  
    logo_url = models.URLField(blank=True, null=True)

    weighing_system = models.CharField(max_length=50)

    incentive_per_100_percent_route = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    complaint_resolution_sla = models.IntegerField(help_text="SLA in hours")

    total_producers = models.IntegerField(default=0)
    total_collectors = models.IntegerField(default=0)
    operational_cities = models.JSONField(default=list)

    

    # List of working days (Mon–Sun)
    working_days = models.JSONField(default=list)

    # Simple working hours (same every day)
    opening_time = models.TimeField()
    closing_time = models.TimeField()

    # Price range numeric min/max
    price_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    price_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
 
   
    def clean(self):
        if self.closing_time <= self.opening_time:
            raise ValidationError("Closing time must be later than opening time.")


    def __str__(self):
        return self.company_name


