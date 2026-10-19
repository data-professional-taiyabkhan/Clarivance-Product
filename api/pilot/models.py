"""Pilot data: one person's tax profile, uploaded statements, transactions and unpaid invoices."""
from datetime import date

from django.conf import settings
from django.db import models

from clarivance_engine.ingest import CATEGORIES

CATEGORY_CHOICES = list(CATEGORIES.items())


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    name = models.CharField(max_length=120, blank=True)
    business_name = models.CharField(max_length=120, blank=True)
    trade = models.CharField(max_length=120, blank=True)
    business_type = models.CharField(max_length=20, default="sole_trader",
                                     choices=[("sole_trader", "Sole trader"), ("limited_company", "Limited company"),
                                              ("partnership", "Partnership")])
    trading_since = models.DateField(default=date(2025, 4, 6))
    last_year_bill = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_towards_this_year = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_year_balance_owed = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cash_override = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    confidence = models.FloatField(default=0.8)
    profile_done = models.BooleanField(default=False)
    accepted_terms_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Statement(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="statements")
    filename = models.CharField(max_length=200)
    business_only = models.BooleanField(default=True)
    rows = models.PositiveIntegerField(default=0)
    imported = models.PositiveIntegerField(default=0)
    duplicates = models.PositiveIntegerField(default=0)
    first_day = models.DateField(null=True)
    last_day = models.DateField(null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]


class Transaction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions")
    statement = models.ForeignKey(Statement, on_delete=models.CASCADE, related_name="transactions")
    fingerprint = models.CharField(max_length=40)
    day = models.DateField()
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance = models.DecimalField(max_digits=14, decimal_places=2, null=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    client = models.CharField(max_length=120, blank=True)
    user_edited = models.BooleanField(default=False)

    class Meta:
        ordering = ["-day", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "fingerprint"], name="uniq_txn_per_user")]
        indexes = [models.Index(fields=["user", "day"])]


class OpenInvoice(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="open_invoices")
    client = models.CharField(max_length=120)
    reference = models.CharField(max_length=60, blank=True)
    issued = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["issued"]
