from django.urls import path

from . import views as v

urlpatterns = [
    path("profile", v.profile),
    path("statements", v.statements),
    path("statements/<int:sid>", v.statement_detail),
    path("transactions", v.transactions),
    path("transactions/<int:tid>", v.transaction_detail),
    path("invoices", v.invoices),
    path("invoices/<int:iid>", v.invoice_detail),
    path("position", v.position),
    path("what-if", v.what_if),
    path("export", v.export),
    path("delete", v.delete_account),
]
