"""User and administrator support-ticket workflows."""

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string

from dataio.services.authorization import ADMINISTRATOR, is_role

from .forms import AdminTicketUpdateForm, SupportTicketForm
from .models import SupportTicket

logger = logging.getLogger(__name__)


def _tickets():
    return SupportTicket.objects.select_related(
        "requester",
        "asset__model__manufacturer",
        "asset__assigned_employee",
        "assigned_to",
    )


def _send_email(subject, recipient, template_base, context):
    if not recipient:
        return
    text = render_to_string(f"support/email/{template_base}.txt", context)
    html = render_to_string(f"support/email/{template_base}.html", context)
    message = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    message.attach_alternative(html, "text/html")
    try:
        message.send()
    except Exception:
        logger.exception("Support ticket email delivery failed for %s", context["ticket"].reference)


def _notify_ticket_created(request, ticket):
    context = {
        "ticket": ticket,
        "ticket_url": request.build_absolute_uri(
            redirect("assets:ticket-detail", reference=ticket.reference).url
        ),
    }
    _send_email(
        f"{ticket.reference} · Support ticket received",
        ticket.requester.email,
        "ticket_created",
        context,
    )
    admin_emails = (
        get_user_model()
        .objects.filter(Q(is_superuser=True) | Q(groups__name=ADMINISTRATOR), is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
        .distinct()
    )
    admin_url = request.build_absolute_uri(redirect("assets:ticket-admin-detail", reference=ticket.reference).url)
    for email in admin_emails:
        _send_email(
            f"{ticket.reference} · New {ticket.get_priority_display()} ticket",
            email,
            "ticket_admin_alert",
            {"ticket": ticket, "ticket_url": admin_url},
        )


@login_required
def ticket_create(request):
    form = SupportTicketForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        ticket = form.save()
        _notify_ticket_created(request, ticket)
        messages.success(request, f"Ticket {ticket.reference} was raised successfully. We sent you a confirmation email.")
        return redirect("dashboard")
    return render(request, "support/ticket_form.html", {"form": form})


@login_required
def ticket_list(request):
    tickets = _tickets().filter(requester=request.user)
    return render(request, "support/ticket_list.html", {"tickets": tickets})


@login_required
def ticket_detail(request, reference):
    ticket = get_object_or_404(_tickets(), reference=reference)
    if ticket.requester_id != request.user.pk and not is_role(request.user, ADMINISTRATOR):
        raise PermissionDenied
    return render(request, "support/ticket_detail.html", {"ticket": ticket})


@login_required
def ticket_admin_list(request):
    if not is_role(request.user, ADMINISTRATOR):
        raise PermissionDenied
    tickets = _tickets()
    status = request.GET.get("status", "")
    priority = request.GET.get("priority", "")
    query = request.GET.get("q", "").strip()
    if status in dict(SupportTicket.Status.choices):
        tickets = tickets.filter(status=status)
    if priority in dict(SupportTicket.Priority.choices):
        tickets = tickets.filter(priority=priority)
    if query:
        tickets = tickets.filter(
            Q(reference__icontains=query)
            | Q(asset__asset_tag__icontains=query)
            | Q(asset__serial_number__icontains=query)
            | Q(requester__username__icontains=query)
        )
    page = Paginator(tickets, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "support/admin_ticket_list.html",
        {
            "tickets": page,
            "page_obj": page,
            "status_choices": SupportTicket.Status.choices,
            "priority_choices": SupportTicket.Priority.choices,
            "filters": {"status": status, "priority": priority, "q": query},
        },
    )


@login_required
def ticket_admin_detail(request, reference):
    if not is_role(request.user, ADMINISTRATOR):
        raise PermissionDenied
    ticket = get_object_or_404(_tickets(), reference=reference)
    previous_status = ticket.status
    form = AdminTicketUpdateForm(request.POST or None, instance=ticket)
    if request.method == "POST" and form.is_valid():
        ticket = form.save()
        if ticket.status != previous_status:
            _send_email(
                f"{ticket.reference} · Status updated to {ticket.get_status_display()}",
                ticket.requester.email,
                "ticket_updated",
                {
                    "ticket": ticket,
                    "ticket_url": request.build_absolute_uri(
                        redirect("assets:ticket-detail", reference=ticket.reference).url
                    ),
                },
            )
        messages.success(request, f"Ticket {ticket.reference} was updated.")
        return redirect("assets:ticket-admin-detail", reference=ticket.reference)
    return render(request, "support/admin_ticket_detail.html", {"ticket": ticket, "form": form})
