from django.db import models, transaction
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, Group, Permission




class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ("client", "Client"),
        ("collector", "Collector"),
        ("supervisor", "Supervisor"),
        ("company", "Company"),
        ("admin", "Admin"),
    )

    PREFIXES = {
        "client": "CLT",
        "collector": "COL",
        "supervisor": "SUP",
        "company": "CMP",
        "admin": "ADM",
    }

    username = models.CharField(max_length=20, unique=True)
    phone_number = models.CharField(max_length=17, unique=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    profile_photo = models.URLField(blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["role"]

    


    def save(self, *args, **kwargs):
        if not self.username:
            prefix = self.PREFIXES.get(self.role, "USR")

            with transaction.atomic():
                last_user = (
                    User.objects.select_for_update()
                    .filter(username__startswith=prefix)
                    .order_by("-username")
                    .first()
                )

                if last_user:
                    last_number = int(last_user.username[len(prefix):])
                    new_number = last_number + 1
                else:
                    new_number = 1

                self.username = f"{prefix}{new_number:03d}"  # CLT001, SUP002, etc.

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} - ({self.role})"