from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('minigames', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuestionPool',
            fields=[
                ('mate_id', models.CharField(max_length=255,
                 primary_key=True, serialize=False, unique=True)),
                ('cat_list', models.JSONField(help_text='Array of category IDs')),
                ('mate_meta', models.JSONField(help_text='Material metadata')),
                ('mate_content', models.JSONField(help_text='Material content')),
                ('status', models.IntegerField(default=1,
                 help_text='Status: 0=deleted, 1=active, 2=review, etc.')),
            ],
            options={
                'db_table': 'question_pool',
                'ordering': ['mate_id'],
            },
        ),
    ]
