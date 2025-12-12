"""
Migration for StudyGroupStreak model.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('study_groups', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudyGroupStreak',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('streak_length', models.IntegerField(default=0)),
                ('last_day_of_streak', models.DateField(blank=True, default=None, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('group', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='streak',
                    to='study_groups.studygroup'
                )),
            ],
            options={
                'db_table': 'study_groups_studygroupstreak',
                'unique_together': {('group',)},
            },
        ),
        migrations.AddIndex(
            model_name='studygroupstreak',
            index=models.Index(fields=['group'], name='study_group_streak_group_idx'),
        ),
        migrations.AddIndex(
            model_name='studygroupstreak',
            index=models.Index(fields=['last_day_of_streak'], name='study_group_streak_date_idx'),
        ),
    ]


