from django.urls import path
from .views import upload_file, preview_file

urlpatterns = [
    path('upload-file/', upload_file, name='upload_excel'),
    path('preview-file/', preview_file, name='preview_file'),
]