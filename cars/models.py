from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.http import urlencode
from django.db.models import Avg, Count  # ortalama/yorum sayısı için

FUEL_CHOICES = [
    ('gasoline', 'Benzin'),
    ('diesel', 'Dizel'),
    ('hybrid', 'Hybrid'),
    ('electric', 'Elektrik'),
]

TRANSMISSION_CHOICES = [
    ('manual', 'Düz'),
    ('automatic', 'Otomatik'),
]

BODY_CHOICES = [
    ('sedan', 'Sedan'),
    ('hatchback', 'Hatchback'),
    ('suv', 'SUV'),
    ('coupe', 'Coupe'),
    ('cabrio', 'Cabrio'),
    ('wagon', 'Station Wagon'),
    ('pickup', 'Pickup'),
    ('van', 'Van'),
    ('mpv', 'MPV/Minivan'),
]

COLOR_CHOICES = [
    ('white', 'Beyaz'), ('black', 'Siyah'), ('gray', 'Gri'), ('silver', 'Gümüş'),
    ('blue', 'Mavi'), ('red', 'Kırmızı'), ('green', 'Yeşil'), ('brown', 'Kahverengi'),
    ('beige', 'Bej'), ('yellow', 'Sarı'), ('orange', 'Turuncu'),
]

# ==== Boya/Hasar sabitleri (KANONİK) ====
# DB’de tutulan anahtarlar (EN) ve kısa durum kodları:
# o = orijinal, l = lokal boyalı, b = boyalı, d = değişen
PART_KEYS = [
    "hood", "roof", "trunk",
    "bumper_front", "bumper_rear",
    "fender_fl", "door_fl", "door_rl", "fender_rl",
    "fender_fr", "door_fr", "door_rr", "fender_rr",
]
PART_LABELS = {
    "hood": "Kaput",
    "roof": "Tavan",
    "trunk": "Bagaj",
    "bumper_front": "Ön Tampon",
    "bumper_rear": "Arka Tampon",
    "fender_fl": "Sol Ön Çamurluk",
    "door_fl": "Sol Ön Kapı",
    "door_rl": "Sol Arka Kapı",
    "fender_rl": "Sol Arka Çamurluk",
    "fender_fr": "Sağ Ön Çamurluk",
    "door_fr": "Sağ Ön Kapı",
    "door_rr": "Sağ Arka Kapı",
    "fender_rr": "Sağ Arka Çamurluk",
}
STATUS_LABELS = {"o": "Orijinal", "l": "Lokal Boyalı", "b": "Boyalı", "d": "Değişen"}
DEFAULT_DAMAGE_MAP = {k: "o" for k in PART_KEYS}


class Car(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cars')
    title = models.CharField(max_length=120)
    brand = models.CharField(max_length=64)
    model_name = models.CharField(max_length=64)

    year = models.PositiveIntegerField()
    engine = models.CharField(max_length=64, blank=True)  # örn: 1.6 TDI

    # Tarih / temel nitelikler
    listing_date = models.DateField(default=timezone.localdate)
    power_hp = models.PositiveIntegerField(null=True, blank=True, help_text="Motor gücü (HP)")
    engine_cc = models.PositiveIntegerField(null=True, blank=True, help_text="Motor hacmi (cc)")
    body_type = models.CharField(max_length=16, choices=BODY_CHOICES, default='sedan')
    color = models.CharField(max_length=16, choices=COLOR_CHOICES, default='white')

    fuel_type = models.CharField(max_length=16, choices=FUEL_CHOICES, default='gasoline')
    transmission = models.CharField(max_length=16, choices=TRANSMISSION_CHOICES, default='automatic')

    # KM / durum
    kilometers = models.PositiveIntegerField("KM", default=0)

    # Günlük fiyat (TL, 2 ondalık)
    daily_price = models.DecimalField(
        "Günlük Fiyat (₺)",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('99999999.99'))],
    )

    # Konum / adres
    location_text = models.CharField("Adres/Konum", max_length=255)
    city = models.CharField("İl", max_length=64, blank=True)
    district = models.CharField("İlçe", max_length=64, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, help_text="Enlem (örn: 41.0082)")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True, help_text="Boylam (örn: 28.9784)")

    description = models.TextField(blank=True)

    # Boya/hasar haritası – KANONİK biçim: {"door_fr": "b", ...}
    damage_json = models.JSONField("Boya/Parça Durumu", default=dict, blank=True)
    damage_note = models.TextField("Hasar Notu", blank=True)

    # Durum / zaman damgaları
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"{self.title} ({self.brand} {self.model_name})"

    # --- İlan sahibi / puan yardımcıları ---
    @property
    def owner_profile(self):
        return getattr(self.owner, "profile", None)

    @property
    def owner_avg_rating(self) -> float:
        agg = self.owner.received_reviews.aggregate(avg=Avg("rating"))
        avg = agg.get("avg") or 0
        return float(Decimal(str(avg)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) if avg else 0.0

    @property
    def owner_reviews_count(self) -> int:
        agg = self.owner.received_reviews.aggregate(cnt=Count("id"))
        return agg.get("cnt") or 0

    # --- Foto ---
    @property
    def cover_photo(self):
        cp = self.photos.filter(is_cover=True).first()
        return cp or self.photos.order_by('position', 'id').first()

    @property
    def cover_url(self):
        p = self.cover_photo
        return p.image.url if p else None

    # --- Fiyat alias ---
    @property
    def price_per_day(self):
        return self.daily_price

    # --- Maps linki ---
    @property
    def map_url(self):
        if self.latitude is not None and self.longitude is not None:
            return f"https://www.google.com/maps?q={self.latitude},{self.longitude}"
        if self.location_text:
            qs = urlencode({"q": self.location_text})
            return f"https://www.google.com/maps?{qs}"
        elif self.district or self.city:
            query = " ".join(filter(None, [self.district, self.city]))
            if query:
                qs = urlencode({"q": query})
                return f"https://www.google.com/maps?{qs}"
        return ""

    # --- location_text -> ilçe/il basit ayrıştırma ---
    def _guess_city_district(self):
        text = (self.location_text or "").strip()
        if not text:
            return None, None
        if "," in text:
            parts = [p.strip() for p in text.split(",") if p.strip()]
        else:
            parts = [p.strip() for p in text.split() if p.strip()]
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        return None, None

    def save(self, *args, **kwargs):
        # İl/İlçe boşsa location_text’ten tahmin et
        if (not self.city or not self.district) and self.location_text:
            d, c = self._guess_city_district()
            if not self.district and d:
                self.district = d
            if not self.city and c:
                self.city = c

        # Fiyatı iki ondalığa sabitle
        if isinstance(self.daily_price, (int, float, Decimal)):
            self.daily_price = (Decimal(self.daily_price)
                                .quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

        super().save(*args, **kwargs)

    # -------- Boya/Hasar yardımcıları --------
    @property
    def damage_items(self):
        """
        Orijinal dışındaki parçaları döndürür:
        [{'key':'door_fr','label':'Sağ Ön Kapı','code':'b','status':'Boyalı'}, ...]
        """
        data = self.damage_json or {}
        out = []
        for key in PART_KEYS:
            code = data.get(key, "o")
            if code != "o":
                out.append({
                    "key": key,
                    "label": PART_LABELS.get(key, key),
                    "code": code,
                    "status": STATUS_LABELS.get(code, code),
                })
        order = {"d": 0, "b": 1, "l": 2}
        out.sort(key=lambda x: order.get(x["code"], 9))
        return out

    @property
    def damage_counts(self):
        """ {'o':N,'l':N,'b':N,'d':N} """
        data = self.damage_json or {}
        cnt = {"o": 0, "l": 0, "b": 0, "d": 0}
        for key in PART_KEYS:
            cnt[data.get(key, "o")] = cnt.get(data.get(key, "o"), 0) + 1
        return cnt

    @property
    def damage_grouped(self):
        """ {'d':[labels], 'b':[labels], 'l':[labels]} """
        g = {"d": [], "b": [], "l": []}
        for it in self.damage_items:
            g[it["code"]].append(it["label"])
        return g


class CarPhoto(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='car_photos/')
    is_cover = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'id']

    def __str__(self):
        return f"Car#{self.car_id} Photo#{self.id} (pos={self.position}{', cover' if self.is_cover else ''})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_cover:
            CarPhoto.objects.filter(car=self.car, is_cover=True).exclude(pk=self.pk).update(is_cover=False)


# ---------- Teknik özellikler ----------
SEGMENT_CHOICES = [
    ('A', 'A'), ('B', 'B'), ('C', 'C'),
    ('D', 'D'), ('E', 'E'), ('F', 'F'),
    ('S', 'S (Spor/Lüks)'),
]

DRIVE_CHOICES = [
    ('FWD', 'Önden Çekiş (FWD)'),
    ('RWD', 'Arkadan İtiş (RWD)'),
    ('AWD', '4x4 / AWD'),
]


class CarSpecs(models.Model):
    car = models.OneToOneField(Car, on_delete=models.CASCADE, related_name="specs")

    # TEKNİK ÖZELLİKLER
    version_name = models.CharField("Versiyon Adı", max_length=100, blank=True)
    segment = models.CharField("Segment", max_length=2, choices=SEGMENT_CHOICES, blank=True)
    power_kw = models.PositiveIntegerField("Güç (kW)", null=True, blank=True)
    torque_nm = models.PositiveIntegerField("Tork (Nm)", null=True, blank=True)
    drive_type = models.CharField("Çekiş", max_length=3, choices=DRIVE_CHOICES, blank=True)
    weight_kg = models.PositiveIntegerField("Boş Ağırlık (kg)", null=True, blank=True)
    max_weight_kg = models.PositiveIntegerField("Maksimum Ağırlık (kg)", null=True, blank=True)
    top_speed_kmh = models.PositiveIntegerField("Son Sürat (km/s)", null=True, blank=True)
    accel_0_100_s = models.DecimalField("0-100 (sn)", max_digits=4, decimal_places=1, null=True, blank=True)
    co2_g_km = models.PositiveIntegerField("CO₂ (g/km)", null=True, blank=True)

    # MOTOR DETAY
    cylinders = models.PositiveIntegerField("Silindir Sayısı", null=True, blank=True)
    valves = models.PositiveIntegerField("Valf Sayısı", null=True, blank=True)
    turbo = models.BooleanField("Turbo", default=False)

    # EKONOMİ
    cons_city = models.DecimalField("Yakıt (Şehir İçi) Lt/100km", max_digits=4, decimal_places=1, null=True, blank=True)
    cons_highway = models.DecimalField("Yakıt (Şehir Dışı) Lt/100km", max_digits=4, decimal_places=1, null=True, blank=True)
    cons_combined = models.DecimalField("Yakıt (Ortalama) Lt/100km", max_digits=4, decimal_places=1, null=True, blank=True)

    # BOYUTLAR
    wheelbase_mm = models.PositiveIntegerField("Dingil Mesafesi (mm)", null=True, blank=True)
    length_mm = models.PositiveIntegerField("Uzunluk (mm)", null=True, blank=True)
    width_mm = models.PositiveIntegerField("Genişlik (mm)", null=True, blank=True)
    height_mm = models.PositiveIntegerField("Yükseklik (mm)", null=True, blank=True)
    trunk_l = models.PositiveIntegerField("Bagaj Kapasitesi (L)", null=True, blank=True)
    doors = models.PositiveIntegerField("Kapı Sayısı", null=True, blank=True)
    tire_size = models.CharField("Lastik Boyutları", max_length=50, blank=True)

    class Meta:
        verbose_name = "Teknik Özellik"
        verbose_name_plural = "Teknik Özellikler"

    def __str__(self):
        return f"Specs for {self.car_id}"


# ---------- Donanım / Özellikler ----------
class CarFeatures(models.Model):
    car = models.OneToOneField(Car, on_delete=models.CASCADE, related_name='features')

    # Güvenlik
    abs = models.BooleanField(default=False)
    esp_vsa = models.BooleanField(default=False)
    bas = models.BooleanField(default=False)
    child_lock = models.BooleanField(default=False)
    airbag_driver = models.BooleanField(default=False)
    airbag_passenger = models.BooleanField(default=False)
    isofix = models.BooleanField(default=False)
    blind_spot = models.BooleanField(default=False)
    night_vision = models.BooleanField(default=False)
    lane_assist = models.BooleanField(default=False)
    central_lock = models.BooleanField(default=False)
    hill_assist = models.BooleanField(default=False)
    fatigue_detection = models.BooleanField(default=False)

    # İç Donanım
    hydraulic_steering = models.BooleanField(default=False)
    electric_windows = models.BooleanField(default=False)
    climate = models.BooleanField(default=False)
    heated_seats = models.BooleanField(default=False)
    memory_seats = models.BooleanField(default=False)
    ventilated_seats = models.BooleanField(default=False)
    cruise_control = models.BooleanField(default=False)
    cooled_glovebox = models.BooleanField(default=False)
    trip_computer = models.BooleanField(default=False)
    start_stop = models.BooleanField(default=False)
    rear_camera = models.BooleanField(default=False)

    # Dış Donanım
    fog_lights = models.BooleanField(default=False)
    led_headlights = models.BooleanField(default=False)
    xenon_led = models.BooleanField(default=False)
    led_signature = models.BooleanField(default=False)
    sunroof = models.BooleanField(default=False)
    panoramic_roof = models.BooleanField(default=False)
    roof_rails = models.BooleanField(default=False)
    headlight_washers = models.BooleanField(default=False)
    alloy_wheels = models.BooleanField(default=False)
    tow_hook = models.BooleanField(default=False)
    park_sensor_front = models.BooleanField(default=False)
    park_sensor_rear = models.BooleanField(default=False)
    auto_park = models.BooleanField(default=False)

    # Multimedya
    android_auto = models.BooleanField(default=False)
    apple_carplay = models.BooleanField(default=False)
    bluetooth = models.BooleanField(default=False)
    usb_aux = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Donanım"
        verbose_name_plural = "Donanımlar"

    def __str__(self):
        return f"Car#{self.car_id} features"
