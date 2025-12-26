from django.urls import path

from .views import (
    MinigameHighScoreView,
    MinigameLogDetailView,
    MinigameLogListCreateView,
    MinigameUserStatsView,
    QuestionPoolDetailView,
    QuestionPoolListCreateView,
    QuestionPoolMateIdListView,
)

app_name = 'minigames'

urlpatterns = [
    path('logs/', MinigameLogListCreateView.as_view(), name='minigame_log_list'),
    path('logs/<int:msgid>/', MinigameLogDetailView.as_view(),
         name='minigame_log_detail'),
    path('highscores/', MinigameHighScoreView.as_view(),
         name='minigame_high_scores'),
    path('user-stats/', MinigameUserStatsView.as_view(),
         name='minigame_user_stats'),

    # Question Pool APIs
    path('question-pool/mate-ids/', QuestionPoolMateIdListView.as_view(),
         name='question_pool_mate_ids'),
    path('question-pool/', QuestionPoolListCreateView.as_view(),
         name='question_pool_list'),
    path('question-pool/<str:mate_id>/',
         QuestionPoolDetailView.as_view(), name='question_pool_detail'),
]
