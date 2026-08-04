from typing import Any
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string


def send_simple_email(subject: str, message: str, recipients: list[str], from_email: str | None = None):
    return send_mail(
        subject=subject,
        message=message,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=False,
    )


def send_html_email(
    subject: str,
    text_message: str,
    html_message: str,
    recipients: list[str],
    from_email: str | None = None,
):
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_message,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    email.attach_alternative(html_message, "text/html")
    email.send(fail_silently=False)


def send_html_template_email(
    *,
    subject: str,
    template_name: str,
    context: dict,
    recipients: list[str],
    from_email: str | None = None,
    text_fallback: str = "",
):
    if not recipients:
        return 0

    html_message = render_to_string(template_name, context)

    send_html_email(
        subject=subject,
        text_message=text_fallback or "Please view this email in HTML.",
        html_message=html_message,
        recipients=recipients,
        from_email=from_email,
    )

def send_email_change_otp(
    *,
    recipient: str,
    otp: str,
    first_name: str = "",
    new_email: str = "",
    expires_minutes: int = 10,
    app_name: str | None = None,
    from_email: str | None = None,
) -> int:
    """
    Send an OTP for confirming an account email-address change.

    Args:
        recipient:
            Email address that should receive the OTP.

        otp:
            Verification code.

        first_name:
            User's first name.

        new_email:
            Requested new email address.

        expires_minutes:
            OTP expiration time.

        app_name:
            Application name displayed in the email.

        from_email:
            Optional sender email override.
    """

    if not recipient:
        return 0

    resolved_app_name = (
        app_name
        or getattr(settings, "APP_NAME", None)
        or "Application"
    )

    context = {
        "app_name": resolved_app_name,
        "first_name": first_name or "there",
        "new_email": new_email or recipient,
        "otp": otp,
        "expires_minutes": expires_minutes,
    }

    return send_html_template_email(
        subject=f"{otp} is your {resolved_app_name} email verification code",
        template_name="smtp/email_change_otp.html",
        context=context,
        recipients=[recipient],
        from_email=from_email,
        text_fallback=(
            f"Your {resolved_app_name} email change verification code is "
            f"{otp}. This code expires in {expires_minutes} minutes. "
            "Do not share this code with anyone."
        ),
    )

def send_email_change_success_notifications(
    *,
    old_email: str,
    new_email: str,
    first_name: str = "",
    app_name: str | None = None,
    from_email: str | None = None,
) -> dict[str, int]:
    """
    Send email-change success notifications to both the previous and new
    email addresses.

    Returns:
        {
            "old_email": sent_count,
            "new_email": sent_count,
        }
    """

    resolved_app_name = (
        app_name
        or getattr(settings, "APP_NAME", None)
        or "Application"
    )

    results = {
        "old_email": 0,
        "new_email": 0,
    }

    if old_email:
        results["old_email"] = send_html_template_email(
            subject=f"Your {resolved_app_name} email address was changed",
            template_name="smtp/email_change_success.html",
            context={
                "app_name": resolved_app_name,
                "first_name": first_name or "there",
                "old_email": old_email,
                "new_email": new_email,
                "notification_type": "old_email",
            },
            recipients=[old_email],
            from_email=from_email,
            text_fallback=(
                f"The email address for your {resolved_app_name} account "
                f"was changed from {old_email} to {new_email}. "
                "If you did not make this change, contact support immediately."
            ),
        )

    if new_email:
        results["new_email"] = send_html_template_email(
            subject=f"Your new {resolved_app_name} email is confirmed",
            template_name="smtp/email_change_success.html",
            context={
                "app_name": resolved_app_name,
                "first_name": first_name or "there",
                "old_email": old_email,
                "new_email": new_email,
                "notification_type": "new_email",
            },
            recipients=[new_email],
            from_email=from_email,
            text_fallback=(
                f"{new_email} is now connected to your "
                f"{resolved_app_name} account."
            ),
        )

    return results