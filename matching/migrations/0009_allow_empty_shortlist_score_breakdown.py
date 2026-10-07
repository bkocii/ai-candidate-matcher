from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("matching", "0008_shortlistentry_discovery_signals"),
    ]

    operations = [
        migrations.AlterField(
            model_name="shortlistentry",
            name="score_breakdown",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
