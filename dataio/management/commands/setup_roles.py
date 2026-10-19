from django.core.management.base import BaseCommand

from dataio.services.authorization import configure_role_groups


class Command(BaseCommand):
    help = "Create or refresh the Administrator, IT Staff, and Viewer groups."

    def handle(self, *args, **options):
        groups = configure_role_groups()
        for name, group in groups.items():
            self.stdout.write(
                self.style.SUCCESS(
                    f"{name}: {group.permissions.count()} permissions configured"
                )
            )
