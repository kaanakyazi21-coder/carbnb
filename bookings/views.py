from datetime import datetime, date
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from cars.models import Car
from .models import Booking


@login_required
def booking_create(request, car_id):
    car = get_object_or_404(Car, pk=car_id, is_active=True)
    if request.method == 'POST':
        try:
            start = datetime.strptime(request.POST['start_date'], '%Y-%m-%d').date()
            end = datetime.strptime(request.POST['end_date'], '%Y-%m-%d').date()
        except Exception:
            messages.error(request, "Tarih formatı hatalı.")
            return redirect('car_detail', pk=car_id)

        if start >= end:
            messages.error(request, "Bitiş tarihi başlangıçtan sonra olmalı.")
            return redirect('car_detail', pk=car_id)

        # === EHLİYET DOĞRULAMA: min 3 yıl ===
        profile = getattr(request.user, "profile", None)
        if not profile or not profile.license_date:
            messages.error(request, "Rezervasyon için ehliyet tarihinizi profilinizde belirtmelisiniz.")
            # Profil düzenleme sayfasına yönlendir (hesap/urls.py'da 'profile_edit' route'u eklemiştik)
            return redirect('profile_edit')

        today = date.today()
        try:
            three_years_ago = today.replace(year=today.year - 3)
        except ValueError:
            # 29 Şubat vb. durumlar için güvenli düzeltme
            three_years_ago = today.replace(month=2, day=28, year=today.year - 3)

        if profile.license_date > three_years_ago:
            messages.error(request, "Ehliyetinizin üzerinden en az 3 yıl geçmiş olmalı.")
            return redirect('car_detail', pk=car_id)
        # === /EHLİYET DOĞRULAMA ===

        # çakışma: paid veya pending rezervasyonlarla
        overlap = car.bookings.filter(
            status__in=['paid', 'pending'],
            start_date__lt=end,
            end_date__gt=start
        ).exists()
        if overlap:
            messages.error(request, "Bu tarihlerde araç uygun değil.")
            return redirect('car_detail', pk=car_id)

        days = (end - start).days
        total = Decimal(days) * car.daily_price

        booking = Booking.objects.create(
            car=car,
            renter=request.user,
            start_date=start,
            end_date=end,
            days=days,
            total_price=total
        )
        return redirect('payment_page', booking_id=booking.id)

    return redirect('car_detail', pk=car_id)


@login_required
def payment_page(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id, renter=request.user, status='pending')
    return render(request, 'bookings/payment.html', {'booking': booking})


@login_required
def payment_done(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id, renter=request.user, status='pending')
    booking.status = 'paid'
    booking.save()
    messages.success(request, "Ödeme alındı, rezervasyon onaylandı!")
    return render(request, 'bookings/paid.html', {'booking': booking})
