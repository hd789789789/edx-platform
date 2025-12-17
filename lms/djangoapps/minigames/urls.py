from django.urls import path

from .views import (
    MinigameHighScoreView,
    MinigameLogDetailView,
    MinigameLogListCreateView,
    MinigameUserStatsView,
)

app_name = 'minigames'

urlpatterns = [
    path('logs/', MinigameLogListCreateView.as_view(), name='minigame_log_list'),
    path('logs/<int:msgid>/', MinigameLogDetailView.as_view(), name='minigame_log_detail'),
    path('highscores/', MinigameHighScoreView.as_view(), name='minigame_high_scores'),
    path('user-stats/', MinigameUserStatsView.as_view(), name='minigame_user_stats'),
]


