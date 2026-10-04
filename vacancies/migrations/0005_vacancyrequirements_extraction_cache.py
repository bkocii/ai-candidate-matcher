from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vacancies", "0004_vacancyrequirements_role_family_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="vacancyrequirements",
            name="extraction_fingerprint",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name="vacancyrequirements",
            name="extraction_policy_version",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="vacancyrequirements",
            name="extraction_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
