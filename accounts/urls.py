# accounts/urls.py
from django.urls import path
from .views import signup_view, profile_edit, profile_view

urlpatterns = [
    # 👤 Kayıt olma
    path("signup/", signup_view, name="signup"),

    # 👤 Profil görüntüleme
    path("profile/", profile_view, name="profile"),

    # 👤 Profil düzenleme
    path("profile/edit/", profile_edit, name="profile_edit"),
]
