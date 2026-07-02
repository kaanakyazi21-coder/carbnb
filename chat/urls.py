from django.urls import path
from . import views

app_name = "chat"

urlpatterns = [
    path("", views.inbox, name="inbox"),                       # /chat/
    path("start/<int:car_pk>/", views.start_or_open, name="start"),  # /chat/start/5/
    path("t/<int:pk>/", views.thread, name="thread"),          # /chat/t/12/
]
