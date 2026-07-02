# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from datetime import date, timedelta

from .models import Profile

User = get_user_model()

MAX_IMG_MB = 5

def validate_image_file(f):
    if not f:
        return
    size_mb = f.size / (1024 * 1024)
    if size_mb > MAX_IMG_MB:
        raise forms.ValidationError(f"Görsel {MAX_IMG_MB} MB’ı aşamaz.")
    ctype = getattr(f, "content_type", "")
    if not ctype or not ctype.startswith("image/"):
        raise forms.ValidationError("Lütfen geçerli bir resim dosyası (jpg/png) yükleyin.")


class SignupForm(UserCreationForm):
    username = forms.CharField(
        label="Kullanıcı adı",
        help_text="Sadece harf, rakam ve @/./+/-/_ karakterleri."
    )
    email = forms.EmailField(label="E-posta", required=True)

    password1 = forms.CharField(
        label="Şifre",
        widget=forms.PasswordInput,
        help_text="En az 8 karakter olmalı; sık kullanılan şifrelerden kaçının."
    )
    password2 = forms.CharField(
        label="Şifre (tekrar)",
        widget=forms.PasswordInput,
        help_text="Şifre ile aynı olmalı."
    )

    license_date = forms.DateField(
        label="Ehliyet veriliş tarihi",
        required=True,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="En az 2 yıl önce olmalı."
    )
    tc_id_front = forms.ImageField(label="TC kimlik (ön yüz)", required=True)
    tc_id_back  = forms.ImageField(label="TC kimlik (arka yüz)", required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")
        help_texts = {
            "username": "",  # Django'nun uzun İngilizce yardım metnini gizle
        }

    # --- Validasyonlar ---
    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Bu e-posta zaten kayıtlı.")
        return email

    def clean_license_date(self):
        d = self.cleaned_data["license_date"]
        if d > date.today():
            raise forms.ValidationError("Gelecek tarih olamaz.")
        if d > date.today() - timedelta(days=365*2):
            raise forms.ValidationError("Ehliyet en az 2 yıllık olmalı.")
        return d

    def clean_tc_id_front(self):
        f = self.cleaned_data.get("tc_id_front")
        validate_image_file(f)
        return f

    def clean_tc_id_back(self):
        f = self.cleaned_data.get("tc_id_back")
        validate_image_file(f)
        return f

    def save(self, commit=True):
        user = super().save(commit=commit)
        if not commit:
            user.save()
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.license_date = self.cleaned_data["license_date"]
        profile.tc_id_front = self.cleaned_data["tc_id_front"]
        profile.tc_id_back  = self.cleaned_data["tc_id_back"]
        profile.save()
        return user


class ProfileForm(forms.ModelForm):
    license_date = forms.DateField(
        label="Ehliyet veriliş tarihi",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="En az 2 yıl önce olmalı."
    )
    phone = forms.CharField(label="Telefon", required=False)
    tc_id_front = forms.ImageField(label="TC kimlik (ön yüz)", required=False)
    tc_id_back  = forms.ImageField(label="TC kimlik (arka yüz)", required=False)

    class Meta:
        model = Profile
        fields = ["license_date", "phone", "tc_id_front", "tc_id_back"]

    def clean_license_date(self):
        d = self.cleaned_data.get("license_date")
        if d:
            if d > date.today():
                raise forms.ValidationError("Gelecek tarih olamaz.")
            if d > date.today() - timedelta(days=365*2):
                raise forms.ValidationError("Ehliyet en az 2 yıllık olmalı.")
        return d

    def clean_tc_id_front(self):
        f = self.cleaned_data.get("tc_id_front")
        validate_image_file(f)
        return f

    def clean_tc_id_back(self):
        f = self.cleaned_data.get("tc_id_back")
        validate_image_file(f)
        return f
