from django.db import models


from django.contrib.auth import get_user_model

User = get_user_model()

class Supervisor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)
    company_username = models.CharField(max_length=150)
    assigned_areas = models.JSONField(default=list)
    team_size = models.IntegerField(default=0)
    photo_url = models.URLField(blank=True, null=True)

   
    def __str__(self):
        return f"Supervisor - {self.user.username}"
