from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Avg


def tcid_upload_path(instance, filename):
    # Dosyalar: media/ids/user_<id>/<filename>
    return f"ids/user_{instance.user_id}/{filename}"


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    # Mevcut alanlar
    license_date = models.DateField(null=True, blank=True)  # ehliyet veriliş tarihi
    phone = models.CharField(max_length=20, blank=True)

    # TC kimlik kartı görselleri
    tc_id_front = models.ImageField(upload_to=tcid_upload_path, null=True, blank=True)
    tc_id_back = models.ImageField(upload_to=tcid_upload_path, null=True, blank=True)

    # Kullanıcı puanı (tek değer; ortalama için Review'ları da kullanacağız)
    rating = models.FloatField(default=0, help_text="0 ile 5 arasında puan")

    def __str__(self):
        return f"{self.user.username} profile"

    @property
    def avg_rating(self) -> float:
        """Bu kullanıcının aldığı yorumlardan ortalama puan (1–5)."""
        agg = self.user.received_reviews.aggregate(a=Avg("rating"))
        return float(agg["a"] or 0)


class Review(models.Model):
    """
    Kullanıcılar arası yorum/puanlama.
    - reviewer: Yorumu yapan kullanıcı
    - reviewee: Yorumu alan kullanıcı (örn. ilan sahibi)
    - car: Yorumun ilişkilendirildiği ilan (opsiyonel değil; senaryoda gerekli)
    """
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="given_reviews",
    )
    reviewee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_reviews",
    )
    car = models.ForeignKey(
        "cars.Car",
        on_delete=models.CASCADE,
        related_name="reviews",
    )

    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        # Aynı kullanıcı aynı ilanda bir kez yorum yapabilsin
        constraints = [
            models.UniqueConstraint(
                fields=["reviewer", "car"],
                name="uniq_reviewer_per_car",
            )
        ]

    def __str__(self):
        return f"Review({self.rating}) {self.reviewer_id} -> {self.reviewee_id} / car#{self.car_id}"
