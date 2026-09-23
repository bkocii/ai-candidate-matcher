from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("vacancies", "0002_vacancy_deletion_metadata")]

    operations = [
        migrations.AddField(
            model_name="vacancyrequirements",
            name="source_content_type",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="vacancyrequirements",
            name="source_original_filename",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="vacancyrequirements",
            name="source_sha256",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
