from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404

from .models import QuestionBank
from .serializers import QuestionBankSerializer
from django.db.models import Count
import random
import math


class QuestionBankListCreateAPIView(APIView):
    """
    GET: list all or if ?code=... given, return the single item
    POST: create new question
    """
    permission_classes = (AllowAny,)

    def get(self, request):
        code = request.GET.get("q_code") or request.GET.get("code")
        if code:
            obj = get_object_or_404(QuestionBank, q_code=code)
            serializer = QuestionBankSerializer(obj)
            return Response(serializer.data)
        queryset = QuestionBank.objects.all()

        # Filters (updated to new schema)
        q_type = request.GET.get("q_type")
        if q_type:
            queryset = queryset.filter(q_type=q_type)
        taxo_subject = request.GET.get("taxo_subject")
        if taxo_subject:
            queryset = queryset.filter(taxo_subject=taxo_subject)
        difficulty = request.GET.get("q_difficulty")
        if difficulty:
            queryset = queryset.filter(q_difficulty=difficulty)

        # Pagination params
        try:
            page = int(request.GET.get("page", 1))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = int(request.GET.get("page_size", 20))
        except (TypeError, ValueError):
            page_size = 20
        # enforce limits
        if page < 1:
            page = 1
        max_page_size = 500
        if page_size < 1:
            page_size = 1
        if page_size > max_page_size:
            page_size = max_page_size

        total = queryset.count()
        if total == 0:
            return Response(
                {
                    "count": 0,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": 0,
                    "next_page": None,
                    "previous_page": None,
                    "results": [],
                }
            )

        total_pages = math.ceil(total / page_size)
        if page > total_pages:
            page = total_pages

        start = (page - 1) * page_size
        end = start + page_size
        page_qs = queryset.order_by("q_id")[start:end]

        serializer = QuestionBankSerializer(page_qs, many=True)
        next_page = page + 1 if page < total_pages else None
        previous_page = page - 1 if page > 1 else None

        return Response(
            {
                "count": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "next_page": next_page,
                "previous_page": previous_page,
                "results": serializer.data,
            }
        )

    def post(self, request):
        serializer = QuestionBankSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class QuestionBankRetrieveUpdateDeleteAPIView(generics.GenericAPIView):
    """
    PUT /api/question_bank/<code>/  -> update by code
    DELETE /api/question_bank/<code>/ -> delete by code
    """
    serializer_class = QuestionBankSerializer
    permission_classes = (AllowAny,)
    lookup_field = "code"

    def get_object(self):
        code = self.kwargs.get("code")
        return get_object_or_404(QuestionBank, q_code=code)

    def put(self, request, code):
        obj = self.get_object()
        serializer = self.get_serializer(obj, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request, code):
        obj = self.get_object()
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, code):
        obj = self.get_object()
        obj.delete()
        return Response({"message": "Successfully"}, status=status.HTTP_200_OK)


class QuestionBankRandomAPIView(APIView):
    """
    GET: return random questions, supports filters:
      - quantity (int)
      - question_type
      - category
      - difficulty
    """
    permission_classes = (AllowAny,)

    def get(self, request):
        # quantity is the desired number of items per page if page_size not provided
        try:
            quantity = request.GET.get("quantity")
            quantity = int(quantity) if quantity is not None else None
        except (TypeError, ValueError):
            return Response({"message": "quantity must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        # enforce maximum allowed quantity
        max_allowed = 100
        if quantity is not None and quantity > max_allowed:
            return Response({"message": f"quantity cannot be greater than {max_allowed}"}, status=status.HTTP_400_BAD_REQUEST)

        queryset = QuestionBank.objects.all()
        q_type = request.GET.get("q_type")
        if q_type:
            queryset = queryset.filter(q_type=q_type)
        taxo_subject = request.GET.get("taxo_subject")
        if taxo_subject:
            queryset = queryset.filter(taxo_subject=taxo_subject)
        difficulty = request.GET.get("q_difficulty")
        if difficulty:
            queryset = queryset.filter(q_difficulty=difficulty)

        # Pagination params (same behavior as list)
        try:
            page = int(request.GET.get("page", 1))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = request.GET.get("page_size")
            page_size = int(page_size) if page_size is not None else None
        except (TypeError, ValueError):
            page_size = None

        # If quantity provided and page_size not provided, use quantity as page_size
        if page_size is None:
            page_size = quantity if quantity is not None else 1

        # validate page and page_size
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 1
        # enforce max page_size
        if page_size > max_allowed:
            return Response({"message": f"page_size cannot be greater than {max_allowed}"}, status=status.HTTP_400_BAD_REQUEST)

        total = queryset.count()
        if total == 0:
            return Response(
                {
                    "count": 0,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": 0,
                    "next_page": None,
                    "previous_page": None,
                    "results": [],
                }
            )

        total_pages = math.ceil(total / page_size)
        if page > total_pages:
            page = total_pages

        start = (page - 1) * page_size
        end = start + page_size

        # Randomize order and slice for the requested page
        random_qs = list(queryset.order_by('?')[start:end])
        serializer = QuestionBankSerializer(random_qs, many=True)

        next_page = page + 1 if page < total_pages else None
        previous_page = page - 1 if page > 1 else None

        return Response(
            {
                "count": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "next_page": next_page,
                "previous_page": previous_page,
                "results": serializer.data,
            }
        )
