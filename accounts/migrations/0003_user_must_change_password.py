from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_user_is_platform_owner")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="must_change_password",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Blocks normal application access until a managed account "
                    "replaces its temporary password."
                ),
            ),
        )
    ]
