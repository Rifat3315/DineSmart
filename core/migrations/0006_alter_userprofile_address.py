from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_userprofile'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name='userprofile',
                    name='address',
                    field=models.CharField(
                        blank=True,
                        db_column='default_address',
                        max_length=255,
                    ),
                ),
            ],
        ),
    ]