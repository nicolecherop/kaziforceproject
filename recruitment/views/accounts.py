from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render

from ..forms import RegisterForm
from ..matching import open_jobs
from ..models import Application, CandidateProfile, RecruiterProfile


def role_required(role):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.user.role != role:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


def home(request):
    return render(request, 'recruitment/home.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
            if user.role == 'candidate':
                CandidateProfile.objects.create(user=user)
            else:
                RecruiterProfile.objects.create(user=user)
        login(request, user)
        messages.success(
            request,
            'Welcome to KaziForce. Complete your profile to get started.',
        )
        return redirect('profile')
    return render(request, 'registration/register.html', {'form': form})


@login_required
def dashboard(request):
    if request.user.is_staff:
        return redirect('admin:index')
    if request.user.role == 'candidate':
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        applications = request.user.applications.select_related('job')
        context = {
            'profile': profile,
            'applications': applications[:4],
            'application_count': applications.count(),
            'shortlisted_count': applications.filter(status='shortlisted').count(),
            'job_count': open_jobs().count(),
        }
    else:
        jobs = request.user.jobs.all()
        applications = Application.objects.filter(
            job__recruiter=request.user
        ).select_related('candidate', 'job')
        context = {
            'jobs': jobs[:5],
            'job_count': jobs.filter(status='open').count(),
            'application_count': applications.count(),
            'shortlisted_count': applications.filter(status='shortlisted').count(),
            'applications': applications[:5],
        }
    return render(request, 'recruitment/dashboard.html', context)
