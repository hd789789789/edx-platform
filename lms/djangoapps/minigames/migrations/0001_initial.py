from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='MinigameLog',
            fields=[
                ('msgid', models.BigAutoField(primary_key=True, serialize=False)),
                ('msgtype', models.CharField(max_length=64)),
                ('key', models.CharField(max_length=128, db_index=True)),
                ('tsms', models.BigIntegerField()),
                ('user', models.CharField(max_length=255, db_index=True)),
                ('payload', models.JSONField()),
            ],
            options={
                'db_table': 'minigame_logs',
                'ordering': ['-tsms'],
            },
        ),
    ]
