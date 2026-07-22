import os

from django.core.management.base import BaseCommand

from portal.models import User


class Command(BaseCommand):
    help = "Create the first Director account from environment variables, if configured."

    def handle(self, *args, **options):
        username = os.getenv("INITIAL_ADMIN_USERNAME", "").strip()
        password = os.getenv("INITIAL_ADMIN_PASSWORD", "")
        email = os.getenv("INITIAL_ADMIN_EMAIL", "").strip()
        if not username or not password:
            self.stdout.write("Initial admin variables not set; skipping account creation.")
            return
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Initial admin '{username}' already exists; no changes made.")
            return
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            role=User.Role.DIRECTOR,
            is_staff=True,
            is_superuser=True,
            must_change_password=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Created initial Director account: {user.username}"))
