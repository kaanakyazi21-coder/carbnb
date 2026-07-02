from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Max
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

import re
import json

from cars.models import Car
from .models import Conversation, Message


@login_required
def start_or_open(request, car_pk: int):
    car = get_object_or_404(
        Car.objects.select_related("owner"),
        pk=car_pk,
        is_active=True
    )
    if request.user == car.owner:
        messages.info(request, "Kendi ilanınıza mesaj göndermek yerine gelen kutusunu açtım.")
        return redirect("chat:inbox")

    conv, _created = Conversation.objects.get_or_create(
        car=car, owner=car.owner, renter=request.user
    )
    return redirect("chat:thread", pk=conv.pk)


@login_required
def inbox(request):
    convs = (
        Conversation.objects
        .filter(Q(owner=request.user) | Q(renter=request.user))
        .annotate(last_msg_at=Max("messages__created_at"))
        .order_by("-last_msg_at", "-updated_at")
        .select_related("car", "owner", "renter")
    )

    items = []
    for c in convs:
        other = c.renter if request.user == c.owner else c.owner
        unread = Message.objects.filter(conversation=c, is_read=False) \
                                .exclude(sender=request.user).count()
        items.append({"conv": c, "other": other, "unread": unread})

    return render(request, "chat/inbox.html", {"items": items})


@login_required
def thread(request, pk: int):
    conv = get_object_or_404(
        Conversation.objects.select_related("car", "owner", "renter"),
        pk=pk
    )

    if request.user not in (conv.owner, conv.renter):
        messages.error(request, "Bu konuşmayı görme yetkiniz yok.")
        return redirect("chat:inbox")

    if request.method == "POST":
        body = (request.POST.get("body") or "").strip()
        if not body:
            messages.error(request, "Mesaj boş olamaz.")
        else:
            Message.objects.create(conversation=conv, sender=request.user, body=body)
            conv.updated_at = timezone.now()
            conv.save(update_fields=["updated_at"])
            return redirect("chat:thread", pk=conv.pk)

    Message.objects.filter(conversation=conv, is_read=False).exclude(sender=request.user) \
        .update(is_read=True, read_at=timezone.now())

    msgs = conv.messages.select_related("sender")
    other = conv.other_side(request.user)

    return render(request, "chat/thread.html", {
        "conv": conv,
        "messages": msgs,
        "other": other,
        "car": conv.car,
        "unread_count": Message.objects.filter(conversation=conv, is_read=False).exclude(sender=request.user).count(),
    })


# =========================
# 🤖 Canlı Destek Botu API
# =========================

BRANDS = [
    "audi","bmw","citroen","dacia","fiat","ford","honda","hyundai","kia",
    "mercedes","nissan","opel","peugeot","porsche","renault","seat","toyota","volkswagen","vw"
]
MODELS_HINTS = [
    "corolla","clio","megane","focus","fiesta","civic","accord","auris",
    "passat","golf","tiguan","t-roc","polo","egea","doblo","kangoo",
    "3","5","7","x1","x3","4 series","3 series","c-class","e-class","a4","a3","qashqai","micra","octavia"
]

def detect_model_query(text: str) -> str | None:
    t = text.lower()
    tokens = []
    for b in BRANDS:
        if re.search(rf"\b{re.escape(b)}\b", t):
            tokens.append(b)
    for m in MODELS_HINTS:
        if re.search(rf"\b{re.escape(m)}\b", t):
            tokens.append(m)
    if tokens:
        return " ".join(tokens)
    single = re.findall(r"[a-zğüşöçı0-9\-]{3,}", t)
    if len(single) == 1:
        return single[0]
    return None


INTENT_RULES = [
    (r"\b(fiyat|ücret|ne kadar|kaça|günlük|haftalık|aylık)\b",
     "Fiyatlar tarih, konum ve araca göre değişir. İlan listesinde kırmızı fiyatı görürsünüz. İsterseniz aradığınız modeli yazın; uygun ilanları göstereyim."),
    (r"\b(ödeme|kredi kartı|nakit|taksit|ödeme yöntemi|kart|banka|havale|eft)\b",
     "Ödeme yöntemleri: kredi/banka kartı ve havale/EFT. Teslimde kart tercih edilir. Taksit imkanı bankanıza göre değişebilir. Depozito karttan bloke alınabilir."),
    (r"\b(depozito|teminat)\b",
     "Depozito çoğu araçta 5.000₺ civarındadır; hasarsız iade sonrası bankanıza bağlı olarak 1–3 iş gününde çözülür."),
    (r"\b(sigorta|kasko|mini hasar|rent-a-car)\b",
     "Araçlar rent-a-car kaskoludur. Lastik-cam-far kapsamı araca/poliçeye göre değişebilir. Hasarlarda poliçe şartları geçerlidir."),
    (r"\b(iptal|iade|cayma|rezervasyon iptal)\b",
     "Rezervasyonu 24 saat öncesine kadar ücretsiz iptal edebilirsiniz. Daha yakın iptallerde bir günlük ücret kesilebilir."),
    (r"\b(teslim|alım|iade|bırakma|drop ?off|pickup|teslimat)\b",
     "Sarıyer içi teslim ücretsizdir. Farklı lokasyonlarda ek ücret doğabilir. Araç dolu depoyla verilir; aynı şekilde iade beklenir."),
    (r"\b(yaş|ehliyet|şart|gerekli evrak|belge|ehliyet yılı)\b",
     "Gerekli evraklar: TC kimlik, en az 2 yıllık ehliyet ve geçerli bir kredi/banka kartı."),
    (r"\b(kilometre|km|limit)\b",
     "Günlük kilometre limiti ilan detayında yazar (genelde 300–400 km/gün). Limit aşımlarında km başı ücret uygulanır."),
    (r"\b(ek sürücü|ikinci sürücü|additional driver)\b",
     "Ek sürücü mümkündür; kimlik ve ehliyet bilgileri sözleşmeye eklenir."),
    (r"\b(uzat|rezervasyon uzatma|gecikme|geç teslim)\b",
     "Uzatma için teslim saatinden önce haber verin; uygunluk varsa uzatabiliriz."),
    (r"\b(fatura|e-?fatura|verg|kdv)\b",
     "Kurumsal kiralamalarda e-fatura kesilir. Bireysel kiralamalarda KDV fiyata dahildir."),
    (r"\b(hafta sonu|kampanya|indirim|promosyon)\b",
     "Dönemsel kampanyalar olabiliyor. Net fiyat için ilanlara bakabilir veya tarih/konum paylaşabilirsiniz."),
    (r"\b(uzun dönem|aylık kiralama|filo)\b",
     "Aylık/uzun dönem kiralamada özel fiyat sunabiliriz. İstediğiniz model ve yıllık/km beklentisini yazın."),
    (r"\b(ceza|trafik|hgs|ogs|köprü|otoyol)\b",
     "Trafik cezaları ve HGS/OGS geçişleri kiralayana aittir; sonradan yansıtılır."),
    # Kaza & Yol Yardım
    (r"\b(kaza|çarpış|hasar|tutanak|polis|rapor|çekici|yol yardımı|arız[a|e])\b",
     "Öncelikle geçmiş olsun. Herhangi bir kazada: 1) Güvenliği sağlayın ve gerekirse 112/155’i arayın. 2) Küçük hasarlarda kaza tespit tutanağı ve fotoğrafları alın. 3) Bizi hemen bilgilendirin; gerekirse yol yardım/çekici yönlendiririz. 4) Poliçe şartlarına göre işlem yapılır; sürücü kusuru ve raporlar önemlidir."),
]

FALLBACK = (
    "Size yardımcı olmak için buradayım. Marka/model (örn. 'Corolla', 'BMW 3') yazarsanız uygun ilanları gösteririm. "
    "Ödeme, depozito, teslimat, kaza/hasar, iptal gibi konularda da bilgi verebilirim."
)

def smart_reply(text: str) -> str:
    t = (text or "").lower()

    q = detect_model_query(t)
    if q:
        return (
            f"Şu modele/markaya bakabilirsiniz: **{q.title()}**.\n"
            f"👉 İlanlar: /cars/?q={q}"
        )

    for pattern, reply in INTENT_RULES:
        if re.search(pattern, t):
            return reply

    if re.search(r"\b(merhaba|selam|hi|hello)\b", t):
        return "Merhaba! Aradığınız araç/modeli yazabilir veya ödeme-depozito-teslimat-kaza gibi konuları sorabilirsiniz."
    if re.search(r"\b(teşekkür|sağ ol|thanks)\b", t):
        return "Rica ederim. Başka bir sorunuz varsa yazabilirsiniz."

    return FALLBACK


@csrf_exempt
def chat_bot_reply(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        data = json.loads(request.body.decode("utf-8"))
        user_text = (data.get("message") or "").strip()
    except Exception:
        user_text = ""
    reply = smart_reply(user_text)
    return JsonResponse({"reply": reply})
