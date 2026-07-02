import os
from django.apps import AppConfig
from django.conf import settings

class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "common"

    def ready(self):
        # sadece DEBUG modunda ve ana reloader sürecinde çalışsın
        if settings.DEBUG and (os.environ.get("RUN_MAIN") == "true" or os.environ.get("DJANGO_RUN_MAIN") == "true"):
            try:
                from django.contrib.sessions.models import Session
                Session.objects.all().delete()  # tüm oturumları sil
            except Exception:
                pass
