
from django.db import migrations


def create_periodic_task(apps, schema_editor):
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    schedule, _ = IntervalSchedule.objects.get_or_create(
        every=1, period="hours"  # was IntervalSchedule.HOURS — not available on historical model
    )
    PeriodicTask.objects.get_or_create(
        name="Sweep expired invitations",
        task="apps.organizations.tasks.sweep_expired_invitations",
        interval=schedule,
    )


def remove_periodic_task(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="Sweep expired invitations").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0003_organizationinvitation"),  # ← use the real filename here, no .py
        ("django_celery_beat", "0001_initial"),
    ]
    operations = [
        migrations.RunPython(create_periodic_task, remove_periodic_task),
    ]