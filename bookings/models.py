from django.db import models
from django.conf import settings

class Booking(models.Model):
    STATUS = [('pending','Beklemede'), ('paid','Ödendi'), ('cancelled','İptal')]
    car = models.ForeignKey('cars.Car', on_delete=models.CASCADE, related_name='bookings')
    renter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rentals')
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.PositiveIntegerField()
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=12, choices=STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.car} / {self.start_date} → {self.end_date}"
