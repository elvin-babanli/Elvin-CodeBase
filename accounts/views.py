"""
Authentication views: login, register, logout, profile, forgot password flow.
Production-ready: toast messages, full-screen auth pages, profile management.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_GET
from django.conf import settings
from django.utils import timezone

from .forms import (
    LoginForm,
    RegisterForm,
    ForgotPasswordForm,
    VerifyCodeForm,
    ResetPasswordForm,
    ProfileUpdateForm,
    PasswordChangeForm,
)
from .models import UserProfile, PasswordResetVerification
from .email import send_password_reset_code


def _auth_context(base=None):
    """Common context for auth pages. Add social URLs when configured."""
    ctx = base or {}
    ctx.setdefault("auth_page", True)
    try:
        from allauth.socialaccount.models import SocialApp
        from django.contrib.sites.models import Site
        site = Site.objects.get_current()
        ctx["social_google"] = None
        ctx["social_linkedin"] = None
        if SocialApp.objects.filter(provider="google", sites=site).exists():
            ctx["social_google"] = "/accounts/google/login/"
        if SocialApp.objects.filter(provider="linkedin_oauth2", sites=site).exists():
            ctx["social_linkedin"] = "/accounts/linkedin_oauth2/login/"
    except Exception:
        ctx["social_google"] = None
        ctx["social_linkedin"] = None
    return ctx


@require_GET
def dev_auto_login_view(request):
    """Dev only: auto-login as elvinbabanli0@gmail.com. Only when DEBUG=True."""
    if not getattr(settings, "DEBUG", False):
        return redirect("accounts:auth_login")
    user = User.objects.filter(email__iexact="elvinbabanli0@gmail.com").first()
    if not user:
        return redirect("accounts:auth_login")
    login(request, user)
    return redirect(reverse("home"))


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = LoginForm(request, data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            display_name = user.get_full_name() or user.email or user.username
            messages.success(request, f"Welcome back, {display_name}!")
            next_url = request.GET.get("next") or reverse("home")
            return redirect(next_url)
        else:
            try:
                from analytics.services.tracker import track_auth_event
                email_attempted = (request.POST.get("username") or "")[:254]
                track_auth_event(request, "login_failed", email_attempted=email_attempted, success=False)
            except Exception:
                pass

    # Ensure register success message shows when redirected with ?registered=1
    if request.method == "GET" and request.GET.get("registered") == "1":
        messages.success(
            request,
            "Account created successfully. Please sign in to continue.",
        )

    return render(
        request,
        "accounts/login.html",
        _auth_context({"form": form}),
    )


@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = RegisterForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()
        try:
            from analytics.services.tracker import track_auth_event
            track_auth_event(request, "register_success", user=user, success=True)
        except Exception:
            pass
        return redirect(reverse("accounts:auth_login") + "?registered=1")

    return render(
        request,
        "accounts/register.html",
        _auth_context({"form": form}),
    )


@require_http_methods(["GET", "POST"])
def logout_view(request):
    logout(request)
    messages.success(request, "Logout successful.")
    return redirect("accounts:auth_login")


# --- Forgot Password Flow ---

@require_http_methods(["GET", "POST"])
def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = ForgotPasswordForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            messages.error(request, "No account found with this email address.")
            return render(request, "accounts/forgot_password.html", _auth_context({"form": form}))

        try:
            verification = PasswordResetVerification.generate_code_for_email(email)
            ok = send_password_reset_code(email, verification.code)
        except Exception:
            messages.error(request, "We could not send the verification code. Please try again.")
            return render(request, "accounts/forgot_password.html", _auth_context({"form": form}))

        if not ok:
            messages.error(request, "We could not send the verification code. Please try again.")
            return render(request, "accounts/forgot_password.html", _auth_context({"form": form}))

        request.session["password_reset_email"] = email
        messages.success(request, "A 6-digit verification code has been sent to your email.")
        return redirect("accounts:auth_verify_code")

    return render(request, "accounts/forgot_password.html", _auth_context({"form": form}))


@require_http_methods(["GET", "POST"])
def verify_code_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    email = request.session.get("password_reset_email")
    if not email:
        messages.info(request, "Please enter your email first to request a verification code.")
        return redirect("accounts:auth_forgot_password")

    form = VerifyCodeForm(request.POST or None)

    if request.method == "POST":
        if "resend" in request.POST:
            verification = PasswordResetVerification.objects.filter(email__iexact=email).order_by("-created_at").first()
            if verification and not verification.is_expired:
                messages.info(request, "Please wait for the current code to expire before requesting a new one.")
            else:
                try:
                    new_v = PasswordResetVerification.generate_code_for_email(email)
                    ok = send_password_reset_code(email, new_v.code)
                except Exception:
                    ok = False
                if ok:
                    messages.success(request, "A new verification code has been sent.")
                else:
                    messages.error(request, "Could not send the code. Please try again.")
            return redirect("accounts:auth_verify_code")

        if form.is_valid():
            code = form.cleaned_data["code"]
            verification = (
                PasswordResetVerification.objects
                .filter(email__iexact=email, code=code)
                .order_by("-created_at")
                .first()
            )
            if not verification:
                messages.error(request, "Invalid verification code.")
            elif verification.is_expired:
                messages.error(request, "This code has expired. Please request a new one.")
            else:
                request.session["password_reset_verified"] = True
                request.session["password_reset_email"] = email
                verification.delete()
                return redirect("accounts:auth_reset_password")
            return render(request, "accounts/verify_code.html", _auth_context({"form": form, "email": email}))

    # Check if current code is expired (for UI hint)
    verification = PasswordResetVerification.objects.filter(email__iexact=email).order_by("-created_at").first()
    code_expired = verification.is_expired if verification else True

    return render(
        request,
        "accounts/verify_code.html",
        _auth_context({"form": form, "email": email, "code_expired": code_expired}),
    )


@require_http_methods(["GET", "POST"])
def reset_password_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    email = request.session.get("password_reset_email")
    verified = request.session.get("password_reset_verified")
    if not email or not verified:
        messages.info(request, "Please complete the verification step first.")
        return redirect("accounts:auth_forgot_password")

    user = get_object_or_404(User, email__iexact=email)
    form = ResetPasswordForm(user=user, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        del request.session["password_reset_email"]
        del request.session["password_reset_verified"]
        messages.success(request, "Your password has been reset. You can now sign in.")
        return redirect("accounts:auth_login")

    return render(request, "accounts/reset_password.html", _auth_context({"form": form}))


# --- Profile ---

@login_required
@require_http_methods(["GET", "POST"])
def profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile_form = ProfileUpdateForm(
        user=request.user,
        data=request.POST or None,
        instance=profile,
    )
    password_form = PasswordChangeForm(user=request.user, data=request.POST or None)

    if request.method == "POST":
        if "update_profile" in request.POST:
            if profile_form.is_valid():
                profile.birth_date = profile_form.cleaned_data.get("birth_date")
                profile.phone_number = profile_form.cleaned_data.get("phone_full", "")
                profile.save()
                request.user.first_name = (profile_form.cleaned_data.get("first_name") or "").strip()
                request.user.last_name = (profile_form.cleaned_data.get("last_name") or "").strip()
                request.user.save()
                messages.success(request, "Profile updated successfully.")
                return redirect("accounts:auth_profile")

        if "change_password" in request.POST:
            password_form = PasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(request, "Password changed successfully.")
                return redirect("accounts:auth_profile")

    return render(request, "accounts/profile.html", {
        "profile_form": profile_form,
        "password_form": password_form,
    })
