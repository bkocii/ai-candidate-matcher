from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("outreach", "0002_outreach_workflow"),
    ]

    operations = [
        migrations.AlterField(
            model_name="outreachdraftaction",
            name="action_type",
            field=models.CharField(
                choices=[
                    ("email_app", "Open in email app"),
                    ("copy", "Copy"),
                    ("export", "Export"),
                ],
                max_length=20,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="outreachdraftaction",
            name="outreach_action_valid_type",
        ),
        migrations.AddConstraint(
            model_name="outreachdraftaction",
            constraint=models.CheckConstraint(
                condition=models.Q(action_type__in=["email_app", "copy", "export"]),
                name="outreach_action_valid_type",
            ),
        ),
    ]
