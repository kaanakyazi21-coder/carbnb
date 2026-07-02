# cars/views.py
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count
from django.db import transaction
from django.utils.http import urlencode
from django.utils.formats import date_format


from .brand_data import MODELS, VARIANTS, BRANDS
from .models import Car, CarPhoto
from .forms import CarForm, CarSpecsForm, CarFeaturesForm

# ⬇️ EKLENDİ: Yorum/puan modeli
from accounts.models import Review

MIN_PHOTOS = 4
MAX_PHOTOS = 12
MAX_IMG_MB = 8  # MB

# --- yardımcı: eski değerleri normalize et (original/local_paint/painted/replaced -> o/l/b/d) ---
VALUE_ALIAS = {"original": "o", "local_paint": "l", "painted": "b", "replaced": "d", "o": "o", "l": "l", "b": "b", "d": "d"}

def _normalize_damage_map(data):
    if not isinstance(data, dict):
        return {}
    out = {}
    for k, v in data.items():
        code = VALUE_ALIAS.get(str(v).strip().lower())
        if code in {"o", "l", "b", "d"}:
            out[k] = code
    return out


# ---- helper: seçilen marka+model için varyant listesi ----
def _variants_for_brand_model(brand: str, model: str):
    variants = (VARIANTS.get(brand, {}) or {}).get(model, [])
    if variants:
        return variants

    qs = Car.objects.filter(is_active=True, brand=brand, model_name=model)
    engine_vals = list(qs.exclude(engine="").values_list("engine", flat=True).distinct())
    ver_names = list(
        qs.exclude(specs__version_name__isnull=True)
          .exclude(specs__version_name__exact="")
          .values_list("specs__version_name", flat=True)
          .distinct()
    )
    return sorted({v.strip() for v in (engine_vals + ver_names) if v and v.strip()})


@login_required
def car_list(request):
    q = (request.GET.get("q") or "").strip()
    brand = (request.GET.get("brand") or "").strip()
    model = (request.GET.get("model") or "").strip()
    variant = (request.GET.get("variant") or "").strip()

    cars = (
        Car.objects.filter(is_active=True)
        .select_related("specs", "features")
        .prefetch_related("photos")
        .order_by("-id")
    )

    if q:
        cars = cars.filter(
            Q(title__icontains=q)
            | Q(brand__icontains=q)
            | Q(model_name__icontains=q)
            | Q(city__icontains=q)
            | Q(district__icontains=q)
            | Q(engine__icontains=q)
            | Q(specs__version_name__icontains=q)
        )

    if brand:
        cars = cars.filter(brand=brand)
    if model:
        cars = cars.filter(model_name=model)
    if variant:
        cars = cars.filter(
            Q(title__icontains=variant)
            | Q(engine__icontains=variant)
            | Q(specs__version_name__icontains=variant)
        )

    brand_counts = (
        Car.objects.filter(is_active=True)
        .values("brand")
        .annotate(cnt=Count("id"))
    )
    count_map = {row["brand"]: row["cnt"] for row in brand_counts}

    brand_items = sorted(
        [
            {"code": code, "label": (label or code), "count": count_map.get(code, 0)}
            for code, label in BRANDS
            if code
        ],
        key=lambda x: x["label"].casefold(),
    )

    ctx = {
        "cars": cars,
        "q": q,
        "filter_brand": brand,
        "filter_model": model,
        "filter_variant": variant,
        "brand_items": brand_items,
        "show_edit": False,
    }
    return render(request, "cars/list.html", ctx)


@login_required
def my_cars(request):
    cars = (
        Car.objects.filter(owner=request.user)
        .select_related("specs", "features")
        .prefetch_related("photos")
        .order_by("-id")
    )
    return render(request, "cars/my_list.html", {
        "cars": cars,
        "show_edit": True,
    })


@login_required
def car_create(request):
    if request.method == "POST":
        form = CarForm(request.POST)
        specs_form = CarSpecsForm(request.POST)
        features_form = CarFeaturesForm(request.POST)
        files = request.FILES.getlist("images")

        count = len(files)
        if count < MIN_PHOTOS or count > MAX_PHOTOS:
            messages.error(request, f"Lütfen {MIN_PHOTOS}-{MAX_PHOTOS} arası foto yükleyin (şu an {count}).")
            return render(request, "cars/create.html", {
                "form": form, "specs_form": specs_form, "features_form": features_form,
                "damage_init_json": json.dumps({})
            })

        for f in files:
            ctype = getattr(f, "content_type", "")
            if not ctype.startswith("image/"):
                messages.error(request, "Sadece resim dosyaları yükleyebilirsiniz.")
                return render(request, "cars/create.html", {
                    "form": form, "specs_form": specs_form, "features_form": features_form,
                    "damage_init_json": json.dumps({})
                })
            if f.size > MAX_IMG_MB * 1024 * 1024:
                messages.error(request, f"Her görsel en fazla {MAX_IMG_MB} MB olabilir.")
                return render(request, "cars/create.html", {
                    "form": form, "specs_form": specs_form, "features_form": features_form,
                    "damage_init_json": json.dumps({})
                })

        if form.is_valid() and specs_form.is_valid() and features_form.is_valid():
            with transaction.atomic():
                car = form.save(commit=False)
                car.owner = request.user
                car.save()

                specs = specs_form.save(commit=False)
                specs.car = car
                specs.save()

                features = features_form.save(commit=False)
                features.car = car
                features.save()

                for idx, f in enumerate(files):
                    CarPhoto.objects.create(
                        car=car, image=f, is_cover=(idx == 0), position=idx,
                    )

            messages.success(request, "İlan oluşturuldu.")
            if not car.is_active:
                return redirect("cars:car_update", pk=car.pk)
            return redirect("cars:car_detail", pk=car.pk)

        if not form.is_valid():
            messages.error(request, f"İlan formu hatalı: {form.errors.as_text()}")
        if not specs_form.is_valid():
            messages.error(request, f"Teknik özellikler hatalı: {specs_form.errors.as_text()}")
        if not features_form.is_valid():
            messages.error(request, f"Donanım formu hatalı: {features_form.errors.as_text()}")

        return render(request, "cars/create.html", {
            "form": form, "specs_form": specs_form, "features_form": features_form,
            "damage_init_json": json.dumps({})
        })

    else:
        form = CarForm()
        specs_form = CarSpecsForm()
        features_form = CarFeaturesForm()

    return render(request, "cars/create.html", {
        "form": form, "specs_form": specs_form, "features_form": features_form,
        "damage_init_json": json.dumps({})
    })


@login_required
def car_update(request, pk):
    car = get_object_or_404(
        Car.objects.select_related("specs", "features").prefetch_related("photos"),
        pk=pk,
        owner=request.user
    )
    specs_instance = getattr(car, "specs", None)
    features_instance = getattr(car, "features", None)

    if request.method == "POST":
        form = CarForm(request.POST, instance=car)
        specs_form = CarSpecsForm(request.POST, instance=specs_instance)
        features_form = CarFeaturesForm(request.POST, instance=features_instance)
        files = request.FILES.getlist("images")

        if form.is_valid() and specs_form.is_valid() and features_form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.is_active = True
                instance.listing_date = car.listing_date
                instance.save()
                form.save_m2m()

                specs = specs_form.save(commit=False)
                specs.car = car
                specs.save()

                feats = features_form.save(commit=False)
                feats.car = car
                feats.save()

                cover_choice = request.POST.get("cover")
                for photo in car.photos.all():
                    pos_str = request.POST.get(f"pos_{photo.id}")
                    if pos_str and pos_str.isdigit():
                        photo.position = int(pos_str)
                    if cover_choice and str(photo.id) == cover_choice:
                        photo.is_cover = True
                    else:
                        if cover_choice:
                            photo.is_cover = False
                    photo.save()

                if files:
                    existing = car.photos.count()
                    if existing + len(files) > MAX_PHOTOS:
                        messages.error(request, f"Toplam foto {MAX_PHOTOS}’i geçemez.")
                        photos = car.photos.all().order_by("position", "id")
                        variants = _variants_for_brand_model(
                            form.cleaned_data.get("brand") or car.brand,
                            form.cleaned_data.get("model_name") or car.model_name
                        )
                        return render(request, "cars/edit.html", {
                            "form": form, "specs_form": specs_form, "features_form": features_form,
                            "car": car, "photos": photos, "variants": variants,
                            "damage_init_json": json.dumps(_normalize_damage_map(form.cleaned_data.get("damage_json") or {})),
                        })

                    max_pos = max((p.position for p in car.photos.all()), default=-1)
                    start = max_pos + 1
                    for idx, f in enumerate(files):
                        ctype = getattr(f, "content_type", "")
                        if not ctype.startswith("image/"):
                            continue
                        CarPhoto.objects.create(car=car, image=f, position=start + idx)

            messages.success(request, "İlan güncellendi.")
            return redirect("cars:car_update", pk=car.pk)

        # Hatalı POST -> mevcut form verisi ile harita state’i
        if not form.is_valid():
            messages.error(request, f"İlan formu hatalı: {form.errors.as_text()}")
        if not specs_form.is_valid():
            messages.error(request, f"Teknik özellikler hatalı: {specs_form.errors.as_text()}")
        if not features_form.is_valid():
            messages.error(request, f"Donanım formu hatalı: {features_form.errors.as_text()}")

        photos = car.photos.all().order_by("position", "id")
        b = request.POST.get("brand") or car.brand
        m = request.POST.get("model_name") or car.model_name
        variants = _variants_for_brand_model(b, m)

        # POST edilen JSON’u ekrana geri ver
        try:
            posted = json.loads(request.POST.get("damage_json") or "{}")
        except Exception:
            posted = {}
        return render(request, "cars/edit.html", {
            "form": form, "specs_form": specs_form, "features_form": features_form,
            "car": car, "photos": photos, "variants": variants,
            "damage_init_json": json.dumps(_normalize_damage_map(posted)),
        })

    else:
        form = CarForm(instance=car)
        specs_form = CarSpecsForm(instance=specs_instance)
        features_form = CarFeaturesForm(instance=features_instance)

    photos = car.photos.all().order_by("position", "id")
    variants = _variants_for_brand_model(car.brand, car.model_name)
    return render(request, "cars/edit.html", {
        "form": form, "specs_form": specs_form, "features_form": features_form,
        "car": car, "photos": photos, "variants": variants,
        "damage_init_json": json.dumps(_normalize_damage_map(car.damage_json or {})),
    })


@login_required
# --- SAHIBINDEN STIL DETAY ---
@login_required
def car_detail(request, pk):
    car = get_object_or_404(
        Car.objects.select_related("specs", "features", "owner__profile").prefetch_related("photos"),
        pk=pk, is_active=True
    )

    # ---- Fotoğraflar (kapak başa)
    photos_qs = list(car.photos.all())
    photos = sorted(
        photos_qs,
        key=lambda p: (
            0 if getattr(p, "is_cover", False) else 1,
            getattr(p, "position", 9999),
            p.id
        )
    )
    cover = photos[0] if photos else None

    # ---- İlişkiler
    specs    = getattr(car, "specs", None)
    features = getattr(car, "features", None)

    # ---- Yardımcılar
    def disp(val, default=""):
        return val if (val not in [None, ""]) else default

    def body_disp():
        return car.get_body_type_display() if hasattr(car, "get_body_type_display") else disp(getattr(car, "body_type", ""))

    def fuel_disp():
        return car.get_fuel_type_display() if hasattr(car, "get_fuel_type_display") else disp(getattr(car, "fuel_type", ""))

    def trans_disp():
        return car.get_transmission_display() if hasattr(car, "get_transmission_display") else disp(getattr(car, "transmission", ""))

    def color_disp():
        return car.get_color_display() if hasattr(car, "get_color_display") else disp(getattr(car, "color", ""))

    # ---- Model satırı: motor + versiyon
    model_line = " ".join(filter(None, [disp(getattr(car, "engine", "")), disp(getattr(specs, "version_name", ""))]))

    # (varsa) Seri alanı
    series_text = disp(getattr(car, "series", ""))

    # ---- Sağ bilgi tablosu
    info_rows = [
        ("İlan No", car.pk),
        ("İlan Tarihi", disp(getattr(car, "listing_date", ""))),
        ("Marka", disp(getattr(car, "brand", ""))),
        ("Seri", series_text),
        ("Model", model_line),
        ("Yıl", disp(getattr(car, "year", ""))),
        ("Yakıt Tipi", fuel_disp()),
        ("Vites", trans_disp()),
        ("Araç Durumu", "İkinci El"),
        ("KM", f"{int(getattr(car, 'kilometers', 0)):,}".replace(",", ".")),
        ("Kasa Tipi", body_disp()),
        ("Motor Gücü", f"{getattr(car, 'power_hp', '')} hp" if getattr(car, "power_hp", None) else ""),
        ("Motor Hacmi", f"{getattr(car, 'engine_cc', '')} cc" if getattr(car, "engine_cc", None) else ""),
        ("Çekiş", {"FWD": "Önden Çekiş", "RWD": "Arkadan İtiş", "AWD": "4x4 / AWD"}.get(getattr(specs, "drive_type", ""), "Önden Çekiş")),
        ("Renk", color_disp()),
        ("Garanti", "—"),
        ("Ağır Hasar Kayıtlı", "Hayır"),
        ("Plaka / Uyruk", "Türkiye (TR) Plakalı"),
        ("Kimden", "Sahibinden"),
        ("Takas", "—"),
    ]

    # ---- Açıklama (satır satır)
    description_lines = [l.strip() for l in (getattr(car, "description", "") or "").splitlines() if l.strip()]

    # ---- Boyalı/Değişen
    grouped = getattr(car, "damage_grouped", None) or {"d": [], "b": [], "l": []}

    # ---- Donanım grupları (alan adların farklıysa True/False maplerini buna göre değiştir)
    feature_groups = {
        "Güvenlik": [
            ("ABS", getattr(features, "abs", False)),
            ("ESP / VSA", getattr(features, "esp_vsa", False)),
            ("BAS", getattr(features, "bas", False)),
            ("Hava Yastığı (Sürücü)", getattr(features, "airbag_driver", False)),
            ("Hava Yastığı (Yolcu)", getattr(features, "airbag_passenger", False)),
            ("Isofix", getattr(features, "isofix", False)),
            ("Merkezi Kilit", getattr(features, "central_lock", False)),
            ("Kör Nokta Uyarı", getattr(features, "blind_spot", False)),
            ("Gece Görüş", getattr(features, "night_vision", False)),
            ("Şerit Takip", getattr(features, "lane_assist", False)),
            ("Yokuş Kalkış Desteği", getattr(features, "hill_assist", False)),
            ("Yorgunluk Tespit", getattr(features, "fatigue_detection", False)),
        ],
        "İç Donanım": [
            ("Hidrolik Direksiyon", getattr(features, "hydraulic_steering", False)),
            ("Elektrikli Camlar", getattr(features, "electric_windows", False)),
            ("Klima", getattr(features, "climate", False)),
            ("Cruise Control", getattr(features, "cruise_control", False)),
            ("Geri Görüş Kamerası", getattr(features, "rear_camera", False)),
            ("Start / Stop", getattr(features, "start_stop", False)),
            ("Soğutmalı Torpido", getattr(features, "cooled_glovebox", False)),
            ("Yol Bilgisayarı", getattr(features, "trip_computer", False)),
            ("Isıtmalı Koltuk", getattr(features, "heated_seats", False)),
            ("Hafızalı Koltuk", getattr(features, "memory_seats", False)),
            ("Havalandırmalı Koltuk", getattr(features, "ventilated_seats", False)),
        ],
        "Dış Donanım": [
            ("Far (Sis)", getattr(features, "fog_lights", False)),
            ("LED Far", getattr(features, "led_headlights", False)),
            ("Xenon/LED", getattr(features, "xenon_led", False)),
            ("LED İmza", getattr(features, "led_signature", False)),
            ("Sunroof", getattr(features, "sunroof", False)),
            ("Panoramik Tavan", getattr(features, "panoramic_roof", False)),
            ("Tavan Rayı", getattr(features, "roof_rails", False)),
            ("Far Yıkama", getattr(features, "headlight_washers", False)),
            ("Alaşımlı Jant", getattr(features, "alloy_wheels", False)),
            ("Çeki Demiri", getattr(features, "tow_hook", False)),
            ("Park Sensörü (Ön)", getattr(features, "park_sensor_front", False)),
            ("Park Sensörü (Arka)", getattr(features, "park_sensor_rear", False)),
            ("Oto Park", getattr(features, "auto_park", False)),
        ],
        "Multimedya": [
            ("Android Auto", getattr(features, "android_auto", False)),
            ("Apple CarPlay", getattr(features, "apple_carplay", False)),
            ("Bluetooth", getattr(features, "bluetooth", False)),
            ("USB / AUX", getattr(features, "usb_aux", False)),
        ],
    }

    # ---- Satıcı bilgisi
    owner   = car.owner
    profile = getattr(owner, "profile", None)

    def _full_name(u):
        try:
            n = u.get_full_name()
            return n.strip() if n and n.strip() else u.username
        except Exception:
            return u.username

    seller_fullname = _full_name(owner)
    seller_phone = (
        getattr(profile, "phone", None)
        or getattr(car, "contact_phone", None)
        or getattr(owner, "phone", None)
        or "—"
    )
    seller_since = date_format(getattr(owner, "date_joined", None), "F Y", use_l10n=True) if getattr(owner, "date_joined", None) else "—"

    # ---- Harita (link + embed) — sağlam fallback
    lat = getattr(car, "latitude", None)
    lng = getattr(car, "longitude", None)
    addr_parts = [
        disp(getattr(car, "address", "")),
        disp(getattr(car, "district", "")),
        disp(getattr(car, "city", "")),
        disp(getattr(car, "location_text", "")),
    ]
    q_text = " ".join([p for p in addr_parts if p])

    if lat is not None and lng is not None:
        map_embed_url = f"https://www.google.com/maps?q={lat},{lng}&z=15&output=embed"
        map_url       = f"https://www.google.com/maps?q={lat},{lng}"
    elif q_text:
        qs = urlencode({"q": q_text})
        map_embed_url = f"https://www.google.com/maps?{qs}&output=embed"
        map_url       = f"https://www.google.com/maps?{qs}"
    else:
        map_embed_url = ""
        map_url       = ""

    # ---- Context
    context = {
        "car": car,
        "photos": photos,
        "cover": cover,

        "info_rows": info_rows,
        "description_lines": description_lines,
        "grouped": grouped,
        "feature_groups": feature_groups,

        # Fiyat çubuğu için
        "price_text": f"{getattr(car, 'daily_price', 0):,.0f} TL".replace(",", "."),

        # Konum
        "map_url": map_url,
        "map_embed_url": map_embed_url,

        # Satıcı kartı
        "seller_fullname": seller_fullname,
        "seller_phone": seller_phone,
        "seller_since": seller_since,

        # opsiyonel: seri
        "series_text": series_text,
    }
    return render(request, "cars/detail_sb.html", context)

@login_required
def brand_models_api(request):
    brand = request.GET.get("brand", "")
    return JsonResponse({"models": MODELS.get(brand, [])})


@login_required
def browse_models(request, brand: str):
    models = MODELS.get(brand, []) or []
    from collections import Counter
    cnt = Counter(
        Car.objects.filter(is_active=True, brand=brand).values_list("model_name", flat=True)
    )
    items = [{"model_name": m, "count": cnt.get(m, 0)} for m in models]
    return render(request, "cars/browse_models.html", {"brand": brand, "models": items})


@login_required
def browse_variants(request, brand: str, model: str):
    variants = _variants_for_brand_model(brand, model)
    items = []
    for v in variants:
        c = (
            Car.objects.filter(is_active=True, brand=brand, model_name=model)
              .filter(Q(title__icontains=v) | Q(engine__icontains=v) | Q(specs__version_name__icontains=v))
              .count()
        )
        items.append({"variant": v, "count": c})
    return render(request, "cars/browse_variants.html", {"brand": brand, "model": model, "variants": items})


@login_required
def variants_api(request):
    brand = request.GET.get("brand") or ""
    model = request.GET.get("model") or ""
    variants = _variants_for_brand_model(brand, model)
    return JsonResponse({"variants": variants})


@login_required
def checkout(request, pk):
    car = get_object_or_404(Car, pk=pk, is_active=True)
    photos = car.photos.order_by("position", "id")
    return render(request, "cars/checkout.html", {"car": car, "photos": photos})
