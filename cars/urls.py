from django.urls import path
from . import views

app_name = "cars"

urlpatterns = [
    # Genel liste
    path("", views.car_list, name="car_list"),

    # İlanlarım
    path("ilanlarim/", views.my_cars, name="my_cars"),

    # İlan oluşturma
    path("create/", views.car_create, name="car_create"),

    # İlan düzenleme
    path("update/<int:pk>/", views.car_update, name="car_update"),
    path("<int:pk>/edit/", views.car_update, name="car_update_legacy"),  # eski URL

    # Marka → Model → Varyant sayfaları
    path("brand/<str:brand>/", views.browse_models, name="cars_by_brand_models"),
    path("brand/<str:brand>/<str:model>/", views.browse_variants, name="cars_by_brand_variants"),

    # AJAX/JSON API’leri (formlarda kullanılıyor)
    path("api/brand-models/", views.brand_models_api, name="brand_models_api"),
    path("api/variants/", views.variants_api, name="variants_api"),

    # (İsteğe bağlı legacy alias’lar)
    path("brand-models-api/", views.brand_models_api, name="brand_models_api_legacy"),
    path("variants-api/", views.variants_api, name="variants_api_legacy"),

    # Detay
    path("<int:pk>/", views.car_detail, name="car_detail"),

    # Ödeme (placeholder)
    path("checkout/<int:pk>/", views.checkout, name="checkout"),
]
