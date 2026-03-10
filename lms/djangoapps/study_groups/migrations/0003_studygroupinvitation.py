"""
Migration for StudyGroupInvitation model.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('study_groups', '0002_studygroupstreak'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudyGroupInvitation',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('status', models.CharField(
                    choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('declined', 'Declined')],
                    default='pending',
                    max_length=10,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('responded_at', models.DateTimeField(blank=True, null=True)),
                ('group', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='invitations',
                    to='study_groups.studygroup',
                )),
                ('invited_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='sent_sg_invitations',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('invitee', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='received_sg_invitations',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'study_groups_studygroupinvitation',
                'ordering': ['-created_at'],
                'unique_together': {('group', 'invitee')},
            },
        ),
        migrations.AddIndex(
            model_name='studygroupinvitation',
            index=models.Index(fields=['group', 'status'], name='sg_invitation_group_status_idx'),
        ),
        migrations.AddIndex(
            model_name='studygroupinvitation',
            index=models.Index(fields=['invitee', 'status'], name='sg_invitation_invitee_idx'),
        ),
    ]
