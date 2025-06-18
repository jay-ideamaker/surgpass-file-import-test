from django.urls import path
from .views import DocxUploadView

urlpatterns = [
    path('upload/', DocxUploadView.as_view(), name='docx-upload'),
]