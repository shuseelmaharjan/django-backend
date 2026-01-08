from rest_framework.routers import DefaultRouter
from billing.views import InvoiceViewSet, PaymentViewSet, ReceiptViewSet

router = DefaultRouter()
router.register(r"v1/invoices", InvoiceViewSet, basename="invoices")
router.register(r"v1/payments", PaymentViewSet, basename="payments")
router.register(r"v1/receipts", ReceiptViewSet, basename="receipts")

urlpatterns = router.urls
