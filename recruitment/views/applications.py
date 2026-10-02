from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..forms import ApplicationForm
from ..models import Application, ApplicationEvent, CandidateProfile, Job
from .accounts import role_required


APPLICATION_TRANSITIONS = {
    'submitted': {'reviewing', 'shortlisted', 'rejected'},
    'reviewing': {'shortlisted', 'rejected'},
    'shortlisted': {'hired', 'rejected'},
    'rejected': set(),
    'hired': set(),
    'withdrawn': set(),
}


@role_required('candidate')
@require_POST
def submit_application(request, pk):
    with transaction.atomic():
        job = get_object_or_404(Job.objects.select_for_update(), pk=pk)
        if not job.accepting_applications or not job.recruiter.is_active:
            messages.error(request, 'This job is no longer accepting applications.')
            return redirect('job_detail', pk=pk)
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        if not profile.skills_text.strip() or not profile.qualifications.strip():
            messages.error(
                request,
                'Add your skills and qualifications before applying.',
            )
            return redirect('profile')
        form = ApplicationForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                'recruitment/job_detail.html',
                {'job': job, 'form': form},
                status=400,
            )
        application, created = Application.objects.get_or_create(
            candidate=request.user,
            job=job,
            defaults={'cover_note': form.cleaned_data['cover_note']},
        )
        if created:
            ApplicationEvent.objects.create(
                application=application,
                actor=request.user,
                status='submitted',
            )
        messages.success(
            request,
            'Application submitted.'
            if created
            else 'You already have an application for this job.',
        )
    return redirect('applications')


@login_required
def application_list(request):
    if request.user.role == 'candidate':
        items = Application.objects.filter(candidate=request.user)
    else:
        items = Application.objects.filter(job__recruiter=request.user)
    items = items.select_related('job', 'candidate').prefetch_related('events')
    status = request.GET.get('status', '')
    if status:
        items = items.filter(status=status)
    return render(
        request,
        'recruitment/applications.html',
        {
            'applications': items,
            'statuses': Application.Status.choices,
            'filter_status': status,
        },
    )


@login_required
@require_POST
def update_application_status(request, pk):
    with transaction.atomic():
        application = get_object_or_404(
            Application.objects.select_for_update().select_related('job'),
            pk=pk,
        )
        status = request.POST.get('status')
        if request.user.pk == application.candidate_id:
            valid = status == 'withdrawn' and application.status in {
                'submitted',
                'reviewing',
                'shortlisted',
            }
        elif request.user.pk == application.job.recruiter_id:
            valid = status in APPLICATION_TRANSITIONS.get(application.status, set())
        else:
            raise PermissionDenied
        if not valid:
            messages.error(request, 'That status change is not available.')
        else:
            application.status = status
            application.save(update_fields=['status', 'updated_at'])
            ApplicationEvent.objects.create(
                application=application,
                actor=request.user,
                status=status,
            )
            messages.success(request, 'Application status updated.')
    return redirect('applications')
