from django import forms
from django.forms import ModelForm
from .models import Car, CarSpecs, CarFeatures, PART_KEYS

import json

# Harita durum değerlerinin aliasları (girişte hepsini kabul et, DB'ye o/l/b/d yaz)
VALUE_ALIAS = {
    "original": "o", "local_paint": "l", "painted": "b", "replaced": "d",
    "o": "o", "l": "l", "b": "b", "d": "d",
}


def _comma_to_dot(v):
    if isinstance(v, str):
        return v.replace(",", ".")
    return v


class CarForm(ModelForm):
    class Meta:
        model = Car
        fields = [
            "title", "brand", "model_name", "year", "engine",
            "listing_date", "color", "fuel_type", "transmission",
            "kilometers", "daily_price",
            "body_type", "engine_cc", "power_hp",
            "location_text", "city", "district", "latitude", "longitude",
            "description",
            "damage_json", "damage_note",
        ]
        labels = {
            "title": "Başlık", "brand": "Marka", "model_name": "Model",
            "year": "Yıl", "engine": "Motor (ör. 1.6 TDI)",
            "listing_date": "İlan Tarihi", "color": "Renk",
            "fuel_type": "Yakıt", "transmission": "Vites",
            "kilometers": "Kilometre", "daily_price": "Günlük Fiyat (₺)",
            "body_type": "Gövde", "engine_cc": "Motor Hacmi (cc)", "power_hp": "Güç (HP)",
            "location_text": "Adres/Konum", "city": "İl", "district": "İlçe",
            "latitude": "Enlem", "longitude": "Boylam",
            "description": "Açıklama", "damage_note": "Hasar Notu",
        }
        widgets = {
            "listing_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "damage_json": forms.HiddenInput(),
            "damage_note": forms.Textarea(attrs={"rows": 2, "placeholder": "Örn: Sağ arka kapı ve çamurluk boyalı."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kilometers"].widget.attrs.update({"inputmode": "numeric", "min": "0", "step": "1"})
        self.fields["engine_cc"].widget.attrs.update({"inputmode": "numeric", "min": "0", "step": "1"})
        self.fields["power_hp"].widget.attrs.update({"inputmode": "numeric", "min": "0", "step": "1"})

    def clean_daily_price(self):
        v = _comma_to_dot(self.cleaned_data.get("daily_price"))
        return v

    # damage_json: JSON string/dict -> {model_key: 'o|l|b|d'}
    def clean_damage_json(self):
        raw = self.cleaned_data.get("damage_json")
        if not raw:
            return {}

        if isinstance(raw, dict):
            data = raw
        else:
            try:
                data = json.loads(raw)
            except Exception:
                raise forms.ValidationError("Hasar haritası verisi okunamadı.")

        clean = {}
        for k, v in (data or {}).items():
            if not isinstance(k, str):
                continue
            if k not in PART_KEYS:
                # sadece tanımlı parça anahtarlarını al
                continue
            code = VALUE_ALIAS.get(str(v).strip().lower())
            if code in {"o", "l", "b", "d"}:
                clean[k] = code
        return clean


class CarSpecsForm(ModelForm):
    class Meta:
        model = CarSpecs
        fields = [
            "version_name", "segment", "drive_type",
            "power_kw", "torque_nm", "top_speed_kmh", "accel_0_100_s",
            "cylinders", "valves", "turbo",
            "cons_city", "cons_highway", "cons_combined", "co2_g_km",
            "wheelbase_mm", "length_mm", "width_mm", "height_mm",
            "trunk_l", "doors", "tire_size",
            "weight_kg", "max_weight_kg",
        ]
        labels = {
            "version_name": "Versiyon Adı", "segment": "Segment", "drive_type": "Çekiş",
            "power_kw": "Güç (kW)", "torque_nm": "Tork (Nm)",
            "top_speed_kmh": "Son Sürat (km/s)", "accel_0_100_s": "0–100 (sn)",
            "cylinders": "Silindir Sayısı", "valves": "Valf Sayısı", "turbo": "Turbo",
            "cons_city": "Yakıt (Şehir içi) L/100km", "cons_highway": "Yakıt (Şehir dışı) L/100km",
            "cons_combined": "Yakıt (Ortalama) L/100km", "co2_g_km": "CO₂ (g/km)",
            "wheelbase_mm": "Dingil Mesafesi (mm)", "length_mm": "Uzunluk (mm)",
            "width_mm": "Genişlik (mm)", "height_mm": "Yükseklik (mm)",
            "trunk_l": "Bagaj Kapasitesi (L)", "doors": "Kapı Sayısı",
            "tire_size": "Lastik Boyutları", "weight_kg": "Boş Ağırlık (kg)", "max_weight_kg": "Maksimum Ağırlık (kg)",
        }
        widgets = {
            "accel_0_100_s": forms.NumberInput(attrs={"step": "0.1", "inputmode": "decimal"}),
            "cons_city": forms.NumberInput(attrs={"step": "0.1", "inputmode": "decimal"}),
            "cons_highway": forms.NumberInput(attrs={"step": "0.1", "inputmode": "decimal"}),
            "cons_combined": forms.NumberInput(attrs={"step": "0.1", "inputmode": "decimal"}),
        }

    def clean_accel_0_100_s(self):
        v = self.cleaned_data.get("accel_0_100_s")
        if isinstance(v, str):
            v = _comma_to_dot(v)
        return v

    def clean_cons_city(self):
        v = self.cleaned_data.get("cons_city")
        if isinstance(v, str):
            v = _comma_to_dot(v)
        return v

    def clean_cons_highway(self):
        v = self.cleaned_data.get("cons_highway")
        if isinstance(v, str):
            v = _comma_to_dot(v)
        return v

    def clean_cons_combined(self):
        v = self.cleaned_data.get("cons_combined")
        if isinstance(v, str):
            v = _comma_to_dot(v)
        return v


class CarFeaturesForm(ModelForm):
    class Meta:
        model = CarFeatures
        exclude = ["car"]
        labels = {
            # Güvenlik
            "abs": "ABS", "esp_vsa": "ESP/VSA", "bas": "BAS",
            "child_lock": "Çocuk Kilidi",
            "airbag_driver": "Sürücü Airbag",
            "airbag_passenger": "Yolcu Airbag",
            "isofix": "Isofix",
            "blind_spot": "Kör Nokta Uyarı",
            "night_vision": "Gece Görüş",
            "lane_assist": "Şerit Takip",
            "central_lock": "Merkezi Kilit",
            "hill_assist": "Yokuş Kalkış",
            "fatigue_detection": "Yorgunluk Tespit",

            # İç
            "hydraulic_steering": "Hidrolik Direksiyon",
            "electric_windows": "Elektrikli Camlar",
            "climate": "Klima",
            "heated_seats": "Isıtmalı Koltuk",
            "memory_seats": "Hafızalı Koltuk",
            "ventilated_seats": "Havalandırmalı Koltuk",
            "cruise_control": "Hız Sabitleyici",
            "cooled_glovebox": "Soğutmalı Torpido",
            "trip_computer": "Yol Bilgisayarı",
            "start_stop": "Start-Stop",
            "rear_camera": "Geri Kamera",

            # Dış
            "fog_lights": "Sis Farı",
            "led_headlights": "LED Far",
            "xenon_led": "Xenon/LED",
            "led_signature": "LED Gündüz Farı",
            "sunroof": "Sunroof",
            "panoramic_roof": "Panoramik Tavan",
            "roof_rails": "Tavan Rayı",
            "headlight_washers": "Far Yıkama",
            "alloy_wheels": "Alaşım Jant",
            "tow_hook": "Çeki Demiri",
            "park_sensor_front": "Ön Park Sensörü",
            "park_sensor_rear": "Arka Park Sensörü",
            "auto_park": "Otomatik Park",

            # Multimedya
            "android_auto": "Android Auto",
            "apple_carplay": "Apple CarPlay",
            "bluetooth": "Bluetooth",
            "usb_aux": "USB/AUX",
        }
