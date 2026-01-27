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
