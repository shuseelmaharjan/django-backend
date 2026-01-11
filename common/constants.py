from django.db import models


class UserStatus(models.TextChoices):
    INVITED = "invited", "Invited"
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    LOCKED = "locked", "Locked"
    DELETED = "deleted", "Deleted"


class ScopeType(models.TextChoices):
    GLOBAL = "global", "Global"
    SCHOOL = "school", "School"
    CAMPUS = "campus", "Campus"
    CLASS = "class", "Class"
    SECTION = "section", "Section"
    STUDENT = "student", "Student"


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

# ---------- Enumerations ----------

class FeeFrequency(models.TextChoices):
    ONE_TIME = "one_time", "One Time"
    MONTHLY = "monthly", "Monthly"
    ANNUAL = "annual", "Annual"
    TERM = "term", "Per Term"
    EXAM = "exam", "Exam"
    CUSTOM = "custom", "Custom"


class FeeCalcType(models.TextChoices):
    FIXED = "fixed", "Fixed Amount"
    PER_UNIT = "per_unit", "Per Unit"  # e.g. per subject, per trip, per credit


class TargetType(models.TextChoices):
    SCHOOL = "school", "School"
    CLASS = "class", "Class"
    SECTION = "section", "Section"
    STUDENT = "student", "Student"  # exceptional cases / overrides


class ChargeStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    INVOICED = "invoiced", "Invoiced"
    PAID = "paid", "Paid"
    WAIVED = "waived", "Waived"
    CANCELLED = "cancelled", "Cancelled"

class StaffType(models.TextChoices):
    ADMIN = "admin", "Admin"
    PRINCIPAL = "principal", "Principal"
    VICE_PRINCIPAL = "vice_principal", "Vice Principal"
    TEACHER = "teacher", "Teacher"
    COORDINATOR = "coordinator", "Coordinator"
    ACCOUNTANT = "accountant", "Accountant"
    CASHIER = "cashier", "Cashier"
    ADMISSIONS = "admissions", "Admissions Officer"
    REGISTRAR = "registrar", "Registrar"
    LIBRARIAN = "librarian", "Librarian"
    TRANSPORT = "transport", "Transport Manager"
    HOSTEL = "hostel", "Hostel/Warden"
    IT = "it", "IT/Admin"
    OTHER = "other", "Other"

class EmploymentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    RESIGNED = "resigned", "Resigned"
    TERMINATED = "terminated", "Terminated"

class StaffAttendanceStatus(models.TextChoices):
    PRESENT = "present", "Present"
    ABSENT = "absent", "Absent"
    LATE = "late", "Late"
    HALF_DAY = "half_day", "Half Day"
    ON_LEAVE = "on_leave", "On Leave"
    HOLIDAY = "holiday", "Holiday"

class SalaryComponentType(models.TextChoices):
    EARNING = "earning", "Earning"
    DEDUCTION = "deduction", "Deduction"


class PayrollStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    GENERATED = "generated", "Generated"
    APPROVED = "approved", "Approved"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"


COUNTRY_DATA = [
    {
        "country": "Nepal",
        "country_code": "NP",
        "currency": "NPR",
        "dial_code": "+977",
        "phone_length": 10,
        "tel_length": 7,
    },
    {
        "country": "India",
        "country_code": "IN",
        "currency": "INR",
        "dial_code": "+91",
        "phone_length": 10,
        "tel_length": 7,
    },
    {
        "country": "United States",
        "country_code": "US",
        "currency": "USD",
        "dial_code": "+1",
        "phone_length": 10,
        "tel_length": 7,
    },
    {
        "country": "Canada",
        "country_code": "CA",
        "currency": "CAD",
        "dial_code": "+1",
        "phone_length": 10,
        "tel_length": 7,
    },
    {
        "country": "Australia",
        "country_code": "AU",
        "currency": "AUD",
        "dial_code": "+61",
        "phone_length": 9,
        "tel_length": 6,
    },
]