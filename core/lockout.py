"""Response for a locked-out login (django-axes AXES_LOCKOUT_CALLABLE).

Renders the same login page and error as a wrong password, so a locked account can't be
told apart from a bad guess or a non-existent user (REQ-AUTH-002).
"""

from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import AuthenticationForm
from django.forms.forms import NON_FIELD_ERRORS
from django.forms.utils import ErrorDict
from django.shortcuts import render
from django.urls import reverse


def lockout_response(request, original_response=None, credentials=None):
    next_url = request.POST.get("next", request.GET.get("next", ""))
    if request.path == reverse("admin:login"):
        form_class, template = AdminAuthenticationForm, "admin/login.html"
        context = {**admin.site.each_context(request), "title": "Log in", "app_path": request.path}
        next_url = next_url or reverse("admin:index")  # as AdminSite.login does
    else:
        form_class, template = AuthenticationForm, "registration/login.html"
        context = {}

    username = (credentials or {}).get("username") or request.POST.get("username", "")
    # Unbound form with the error set directly: binding it would run authenticate() again.
    form = form_class(request, initial={"username": username})
    message = form.error_messages["invalid_login"] % {"username": form.username_field.verbose_name}
    form._errors = ErrorDict({NON_FIELD_ERRORS: form.error_class([message])})

    context.update(form=form, next=next_url)
    return render(request, template, context)
