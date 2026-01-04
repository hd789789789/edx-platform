from django.urls import path
from .views import (
    QuestionBankListCreateAPIView,
    QuestionBankRetrieveUpdateDeleteAPIView,
    QuestionBankRandomAPIView,
)

urlpatterns = [
    path("", QuestionBankListCreateAPIView.as_view(), name="question_bank_list_create"),
    path("random/", QuestionBankRandomAPIView.as_view(), name="question_bank_random"),
    path("<str:code>/", QuestionBankRetrieveUpdateDeleteAPIView.as_view(), name="question_bank_rud_by_code"),
]


