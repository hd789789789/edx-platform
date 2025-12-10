"""
URL routing for Study Groups API.
"""

from django.urls import path, re_path
from django.conf import settings

from .views import (
    StudyGroupListView,
    StudyGroupDetailView,
    StudyGroupMemberListView,
    StudyGroupMemberDetailView,
    AvailableGroupMembersListView,
    StudyGroupCommentListView,
    StudyGroupCommentDetailView,
    CommentReactionView,
    CommentAttachmentView,
    AttachmentDownloadView,
)

urlpatterns = [
    # Study Groups endpoints
    re_path(
        r'^courses/{}/study-groups/$'.format(settings.COURSE_ID_PATTERN),
        StudyGroupListView.as_view(),
        name='study-groups-list'
    ),
    path(
        'study-groups/<int:id>/',
        StudyGroupDetailView.as_view(),
        name='study-groups-detail'
    ),

    # Members endpoints
    path(
        'study-groups/<int:id>/members/',
        StudyGroupMemberListView.as_view(),
        name='study-groups-members-list'
    ),
    path(
        'study-groups/<int:id>/members/<int:user_id>/',
        StudyGroupMemberDetailView.as_view(),
        name='study-groups-members-detail'
    ),
    path(
        'study-groups/<int:id>/available-members/',
        AvailableGroupMembersListView.as_view(),
        name='study-groups-available-members'
    ),

    # Comments endpoints
    path(
        'study-groups/<int:id>/comments/',
        StudyGroupCommentListView.as_view(),
        name='study-groups-comments-list'
    ),
    path(
        'comments/<int:id>/',
        StudyGroupCommentDetailView.as_view(),
        name='study-groups-comments-detail'
    ),

    # Reactions endpoints
    path(
        'comments/<int:comment_id>/reactions/',
        CommentReactionView.as_view(),
        name='study-groups-comments-reactions'
    ),

    # Attachments endpoints
    path(
        'comments/<int:comment_id>/attachments/',
        CommentAttachmentView.as_view(),
        name='study-groups-comments-attachments'
    ),
    path(
        'attachments/<int:id>/download/',
        AttachmentDownloadView.as_view(),
        name='study-groups-attachments-download'
    ),
]
