from django.contrib import admin

from fees.models import (
    FeeAdvanceApplication,
    FeeAdvanceCredit,
    FeeAuditEvent,
    FeeConfiguration,
    FeeDocumentSequence,
    FeeHead,
    FeeInclude,
    FeeIncludeAudit,
    FeeInvoice,
    FeeInvoiceAdjustment,
    FeeInvoiceLine,
    FeePayment,
    FeePaymentAllocation,
    FeePaymentReversal,
    FeeStructure,
    StudentFeeConcession,
    StudentFeeWallet,
)


@admin.register(FeeHead)
class FeeHeadAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "group", "is_active")
    search_fields = ("code", "name")
    list_filter = ("group", "is_active")


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ("school", "fee_head", "scope", "period", "amount", "status")
    list_filter = ("school", "scope", "period", "status")
    search_fields = ("fee_head__name", "fee_head__code", "school__name")
    readonly_fields = ("definition_key",)


class InvoiceLineInline(admin.TabularInline):
    model = FeeInvoiceLine
    extra = 0
    can_delete = False
    readonly_fields = [field.name for field in FeeInvoiceLine._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(FeeInvoice)
class FeeInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number", "school", "student", "period_start", "period_end", "total_amount",
        "paid_amount", "due_amount", "status",
    )
    list_filter = ("school", "status", "invoice_date", "due_date")
    search_fields = ("invoice_number", "student__first_name", "student__last_name", "student__registration_no")
    inlines = [InvoiceLineInline]
    readonly_fields = [field.name for field in FeeInvoice._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PaymentAllocationInline(admin.TabularInline):
    model = FeePaymentAllocation
    extra = 0
    can_delete = False
    readonly_fields = [field.name for field in FeePaymentAllocation._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "school", "student", "paid_at", "amount", "payment_method", "status")
    list_filter = ("school", "status", "payment_method", "paid_at")
    search_fields = ("receipt_number", "external_reference", "student__registration_no", "student__phone")
    inlines = [PaymentAllocationInline]
    readonly_fields = [field.name for field in FeePayment._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StudentFeeConcession)
class StudentFeeConcessionAdmin(admin.ModelAdmin):
    list_display = ("student", "kind", "calculation", "value", "frequency", "status", "valid_from", "valid_until")
    list_filter = ("school", "kind", "calculation", "frequency", "status")
    search_fields = ("student__first_name", "student__last_name", "student__registration_no", "reason")
    readonly_fields = [field.name for field in StudentFeeConcession._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StudentFeeWallet)
class StudentFeeWalletAdmin(admin.ModelAdmin):
    list_display = ("student", "batch", "academic_class", "total_due", "advance_balance", "last_reconciled_at")
    readonly_fields = [field.name for field in StudentFeeWallet._meta.fields]


class ImmutableRecordAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for model in [
    FeeConfiguration,
    FeeDocumentSequence,
    FeeIncludeAudit,
    FeeInvoiceAdjustment,
    FeeAdvanceCredit,
    FeeAdvanceApplication,
    FeePaymentReversal,
    FeeAuditEvent,
]:
    admin.site.register(model, ImmutableRecordAdmin)

# FeeInclude remains operational configuration rather than a posted financial record.
admin.site.register(FeeInclude)
