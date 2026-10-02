from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..forms import ApplicationForm, JobForm, RequirementFormSet
from ..matching import open_jobs
from ..models import Application, Job, RecruiterProfile, Skill
from .accounts import role_required


@login_required
def job_list(request):
    query = request.GET.get('q', '').strip()[:200]
    location = request.GET.get('location', '').strip()[:120]
    kind = request.GET.get('type', '')
    listing = open_jobs()
    if query:
        listing = listing.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(company__icontains=query)
        )
    if location:
        listing = listing.filter(location__icontains=location)
    if kind:
        listing = listing.filter(employment_type=kind)
    page = Paginator(listing, 12).get_page(request.GET.get('page'))
    return render(
        request,
        'recruitment/jobs.html',
        {'page_obj': page, 'q': query, 'location': location, 'kind': kind},
    )


@role_required('recruiter')
def my_jobs(request):
    return render(
        request,
        'recruitment/my_jobs.html',
        {'jobs': request.user.jobs.all()},
    )


@role_required('recruiter')
def job_create_or_edit(request, pk=None):
    job = (
        get_object_or_404(Job, pk=pk, recruiter=request.user)
        if pk
        else Job(recruiter=request.user)
    )
    initial = {}
    if not pk:
        recruiter, _ = RecruiterProfile.objects.get_or_create(user=request.user)
        initial['company'] = recruiter.company
    form = JobForm(request.POST or None, instance=job, initial=initial)
    formset = RequirementFormSet(request.POST or None, instance=job)
    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            form.save()
            formset.save()
        messages.success(request, 'Job and skill priorities saved.')
        return redirect('job_detail', pk=job.pk)
    return render(
        request,
        'recruitment/job_form.html',
        {
            'form': form,
            'formset': formset,
            'job': job,
            'esco_ready': Skill.objects.exists(),
        },
    )


@login_required
def job_detail(request, pk):
    job = get_object_or_404(
        Job.objects.select_related('occupation').prefetch_related('requirements__skill'),
        pk=pk,
    )
    owner = request.user.pk == job.recruiter_id
    application = Application.objects.filter(job=job, candidate=request.user).first()
    if job.status == 'draft' and not owner and not request.user.is_staff:
        raise PermissionDenied
    return render(
        request,
        'recruitment/job_detail.html',
        {
            'job': job,
            'owner': owner,
            'application': application,
            'form': ApplicationForm(),
        },
    )


@role_required('recruiter')
@require_POST
def job_close(request, pk):
    job = get_object_or_404(Job, pk=pk, recruiter=request.user)
    job.status = 'closed'
    job.save(update_fields=['status', 'updated_at'])
    messages.success(request, 'Job closed. Existing applications remain available.')
    return redirect('my_jobs')
