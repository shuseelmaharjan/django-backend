from django.db import models

class UserRole(models.TextChoices):
    SUPERADMIN = "superadmin", "superadmin"
    ADMIN = "admin", "admin"
    PRINCIPAL = "principal", "principal"
    VICE_PRINCIPAL = "vice_principal", "vice-principal"
    TEACHER = "teacher", "teacher"
    COORDINATOR = "coordinator", "coordinator"
    ACCOUNTANT = "accountant", "accountant"
    CASHIER = "cashier", "cashier"
    ADMISSIONS = "admissions", "admissions"
    REGISTRAR = "registrar", "registratar"
    LIBRARIAN = "librarian", "librarian"
    TRANSPORT = "transport", "transport_manager"
    HOSTEL = "hostel", "warden"
    IT = "it", "it_officer"
    OTHER = "other", "other"
    STUDENT = "student", "student"

class UserStatus(models.TextChoices):
    INVITED = "invited", "Invited"
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    LOCKED = "locked", "Locked"
    DELETED = "deleted", "Deleted"
    INACTIVE = "inactive", "Inactive"
    DRAFT = "draft", "Draft"



class StudentStatus(models.TextChoices):
    APPLICANT = "applicant", "Applicant"
    ENROLLED = "enrolled", "Enrolled"
    SUSPENDED = "suspended", "Suspended"
    GRADUATED = "graduated", "Graduated"
    ALUMNI = "alumni", "Alumni"


class GuardianType(models.TextChoices):
    FATHER = "father", "Father"
    MOTHER = "mother", "Mother"
    GRANDFATHER = "grandfather", "Grandfather"
    GRANDMOTHER = "grandmother", "Grandmother"
    UNCLE = "uncle", "Uncle"
    AUNT = "aunt", "Aunt"
    OTHER = "other", "Other"
    LOCAL_GUARDIAN = "local_guardian", "Local Guardian"


class AddressType(models.TextChoices):
    PERMANENT = "permanent", "Permanent"
    TEMPORARY = "temporary", "Temporary"

class StudentDocumentType(models.TextChoices):
    PHOTO = "photo", "Photo"
    BIRTH_CERTIFICATE = "birth_certificate", "Birth Certificate"
    CITIZENSHIP = "citizenship", "Citizenship"
    TC = "transfer_certificate", "Transfer Certificate (TC)"
    MARKSHEET = "marksheet", "Marksheet"
    CHARACTER_CERTIFICATE = "character_certificate", "Character Certificate"
    OTHER = "other", "Other"

class Currency(models.TextChoices):
    NPR = "NPR", "Nepalese Rupee"
    INR = "INR", "Indian Rupee"
    USD = "USD", "US Dollar"
    EUR = "EUR", "Euro"
    GBP = "GBP", "British Pound"
    JPY = "JPY", "Japanese Yen"
    CNY = "CNY", "Chinese Yuan"
    AUD = "AUD", "Australian Dollar"
    CAD = "CAD", "Canadian Dollar"
    CHF = "CHF", "Swiss Franc"

COUNTRY_DATA = [
    {
        "country": "Nepal",
        "country_code": "NP",
        "currency": "NPR",
        "dial_code": "+977",
        "phone_length": 10,
        "tel_length": 7,
        "tel-startswith": ["01"],
        "phone-startswith": ["98", "97"]
    },
    {
        "country": "India",
        "country_code": "IN",
        "currency": "INR",
        "dial_code": "+91",
        "phone_length": 10,
        "tel_length": 7,
    },
]