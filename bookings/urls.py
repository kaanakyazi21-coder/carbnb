from django.urls import path
from .views import booking_create, payment_page, payment_done

urlpatterns = [
    path('create/<int:car_id>/', booking_create, name='booking_create'),
    path('pay/<int:booking_id>/', payment_page, name='payment_page'),
    path('done/<int:booking_id>/', payment_done, name='payment_done'),
]
