from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from cars.views import car_list
from chat.views import chat_bot_reply   # 👈 bot view import edildi

urlpatterns = [
    path("admin/", admin.site.urls),

    # 🏠 Ana sayfa -> ilan listesi
    path("", car_list, name="home"),

    # 🔐 allauth (sosyal / hesap işlemleri)
    path("accounts/", include("allauth.urls")),

    # 👤 accounts app'in url'leri (profil vb.)
    path("users/", include("accounts.urls")),

    # 🚗 Uygulamalar
    path("cars/", include("cars.urls")),
    path("bookings/", include("bookings.urls")),

    # 💬 Yeni chat uygulaması
    path("chat/", include("chat.urls", namespace="chat")),

    # 🤖 Canlı destek bot endpoint
    path("api/bot/", chat_bot_reply, name="chat_bot_reply"),
]

# 🖼 Debug modunda media/static dosyaları
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
