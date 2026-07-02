# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .forms import SignupForm, ProfileForm
from .models import Profile


def signup_view(request):
    """
    Kayıt ekranı:
    - username, email, password1/2
    - license_date (>= 2 yıl), tc_id_front/back (image)
    """
    if request.method == "POST":
        form = SignupForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            # Profil yoksa oluştur
            Profile.objects.get_or_create(user=user)

            messages.success(request, "✅ Kayıt başarılı! Giriş yapabilirsiniz.")
            # allauth kullanıldığı için login adı:
            return redirect("account_login")
        else:
            messages.error(request, "❌ Lütfen formdaki hataları düzeltin.")
    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})


@login_required
def profile_view(request):
    """
    Kullanıcının profil sayfası:
    - Ad Soyad / e-mail / telefon
    - 5 yıldız üzerinden puan (tıklanıp kaydedilebilir)
    """
    profile, _ = Profile.objects.get_or_create(user=request.user)

    # Yıldız tıklamasıyla gelen puanı kaydet
    if request.method == "POST":
        try:
            new_rating = int(request.POST.get("rating", 0))
            if 0 <= new_rating <= 5:
                profile.rating = new_rating
                profile.save(update_fields=["rating"])
                messages.success(request, "✅ Puanınız kaydedildi.")
            else:
                messages.error(request, "❌ Puan 0–5 arası olmalıdır.")
        except (TypeError, ValueError):
            messages.error(request, "❌ Geçersiz puan değeri.")
        return redirect("profile")  # Post/Redirect/Get

    # Görünüm için değerleri hazırla
    rating = float(profile.rating or 0)
    rating = max(0, min(5, rating))
    full = int(rating)
    half = 1 if (rating - full) >= 0.5 and full < 5 else 0
    empty = 5 - full - half
    stars = {"full": full, "half": half, "empty": empty}

    context = {
        "profile": profile,
        "rating": rating,  # template'te radio 'checked' için kullanılıyor
        "stars": stars,
    }
    return render(request, "accounts/profile.html", context)


@login_required
def profile_edit(request):
    """
    Profil düzenleme:
    - license_date, phone
    - tc_id_front/back güncellenebilir
    """
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Profiliniz güncellendi.")
            return redirect("profile_edit")
        else:
            messages.error(request, "❌ Lütfen hataları düzeltin.")
    else:
        form = ProfileForm(instance=profile)

    return render(request, "accounts/profile_edit.html", {"form": form})
