from django.conf import settings
from django.db import models
from django.utils import timezone
from cars.models import Car

User = settings.AUTH_USER_MODEL


class Conversation(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name="conversations")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_conversations")
    renter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="rented_conversations")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("car", "owner", "renter")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.car.title} | {self.owner} ↔ {self.renter}"

    def other_side(self, user):
        return self.renter if user == self.owner else self.owner


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    body = models.TextField(max_length=2000)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Msg by {self.sender} at {self.created_at:%Y-%m-%d %H:%M}"
