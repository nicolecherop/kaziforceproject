import csv
from functools import wraps
from pathlib import Path
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .forms import RegisterForm, CandidateForm, RecruiterForm, JobForm, RequirementFormSet, ApplicationForm
from .matching import MatchingEngine, MatchingUnavailable, eligible_profiles, open_jobs
from .models import User, CandidateProfile, RecruiterProfile, Job, Skill, Occupation, Application, ApplicationEvent


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


@login_required
def catalogue_search(request):
    query = request.GET.get('q', '').strip()[:100]
    model = Occupation if request.GET.get('kind') == 'occupation' else Skill
    if len(query) < 2:
        return JsonResponse({'results': []})
    items = model.objects.filter(Q(preferred_label__icontains=query) | Q(alternative_labels__icontains=query))
    return JsonResponse({'results': [{'id': item.pk, 'label': item.preferred_label} for item in items.only('pk', 'preferred_label')[:25]]})


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
        messages.success(request, 'Welcome to KaziForce. Complete your profile to get started.')
        return redirect('profile')
    return render(request, 'registration/register.html', {'form': form})


@login_required
def dashboard(request):
    if request.user.is_staff:
        return redirect('admin:index')
    if request.user.role == 'candidate':
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        applications = request.user.applications.select_related('job')
        context = {'profile': profile, 'applications': applications[:4], 'application_count': applications.count(),
                   'shortlisted_count': applications.filter(status='shortlisted').count(), 'job_count': open_jobs().count()}
    else:
        jobs = request.user.jobs.all()
        applications = Application.objects.filter(job__recruiter=request.user).select_related('candidate', 'job')
        context = {'jobs': jobs[:5], 'job_count': jobs.filter(status='open').count(), 'application_count': applications.count(),
                   'shortlisted_count': applications.filter(status='shortlisted').count(), 'applications': applications[:5]}
    return render(request, 'recruitment/dashboard.html', context)


@login_required
def profile(request):
    candidate = request.user.role == 'candidate'
    model, form_class = (CandidateProfile, CandidateForm) if candidate else (RecruiterProfile, RecruiterForm)
    instance, _ = model.objects.get_or_create(user=request.user)
    form = form_class(request.POST or None, request.FILES or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile saved. New matches will use your latest information.')
        return redirect('profile')
    return render(request, 'recruitment/form.html', {'form': form, 'title': 'Your professional profile' if candidate else 'Your organisation',
                   'subtitle': 'Tell your story through the skills and experience you can demonstrate.' if candidate else 'Introduce the organisation you recruit for.',
                   'profile': instance, 'is_profile': True})


@login_required
def jobs(request):
    query = request.GET.get('q', '').strip()[:200]
    location = request.GET.get('location', '').strip()[:120]
    kind = request.GET.get('type', '')
    listing = open_jobs()
    if query:
        listing = listing.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(company__icontains=query))
    if location:
        listing = listing.filter(location__icontains=location)
    if kind:
        listing = listing.filter(employment_type=kind)
    page = Paginator(listing, 12).get_page(request.GET.get('page'))
    return render(request, 'recruitment/jobs.html', {'page_obj': page, 'q': query, 'location': location, 'kind': kind})


@role_required('recruiter')
def my_jobs(request):
    return render(request, 'recruitment/my_jobs.html', {'jobs': request.user.jobs.all()})


@role_required('recruiter')
def job_edit(request, pk=None):
    job = get_object_or_404(Job, pk=pk, recruiter=request.user) if pk else Job(recruiter=request.user)
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
    return render(request, 'recruitment/job_form.html', {'form': form, 'formset': formset, 'job': job, 'esco_ready': Skill.objects.exists()})


@login_required
def job_detail(request, pk):
    job = get_object_or_404(Job.objects.select_related('occupation').prefetch_related('requirements__skill'), pk=pk)
    owner = request.user.pk == job.recruiter_id
    application = Application.objects.filter(job=job, candidate=request.user).first()
    if job.status == 'draft' and not owner and not request.user.is_staff:
        raise PermissionDenied
    return render(request, 'recruitment/job_detail.html', {'job': job, 'owner': owner, 'application': application, 'form': ApplicationForm()})


@role_required('recruiter')
@require_POST
def job_close(request, pk):
    job = get_object_or_404(Job, pk=pk, recruiter=request.user)
    job.status = 'closed'
    job.save(update_fields=['status', 'updated_at'])
    messages.success(request, 'Job closed. Existing applications remain available.')
    return redirect('my_jobs')


@role_required('candidate')
@require_POST
def apply(request, pk):
    with transaction.atomic():
        job = get_object_or_404(Job.objects.select_for_update(), pk=pk)
        if not job.accepting_applications or not job.recruiter.is_active:
            messages.error(request, 'This job is no longer accepting applications.')
            return redirect('job_detail', pk=pk)
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        if not profile.skills_text.strip() or not profile.qualifications.strip():
            messages.error(request, 'Add your skills and qualifications before applying.')
            return redirect('profile')
        form = ApplicationForm(request.POST)
        if not form.is_valid():
            return render(request, 'recruitment/job_detail.html', {'job': job, 'form': form}, status=400)
        application, created = Application.objects.get_or_create(candidate=request.user, job=job, defaults={'cover_note': form.cleaned_data['cover_note']})
        if created:
            ApplicationEvent.objects.create(application=application, actor=request.user, status='submitted')
        messages.success(request, 'Application submitted.' if created else 'You already have an application for this job.')
    return redirect('applications')


@login_required
def applications(request):
    items = Application.objects.filter(candidate=request.user) if request.user.role == 'candidate' else Application.objects.filter(job__recruiter=request.user)
    items = items.select_related('job', 'candidate').prefetch_related('events')
    status = request.GET.get('status', '')
    if status:
        items = items.filter(status=status)
    return render(request, 'recruitment/applications.html', {'applications': items, 'statuses': Application.Status.choices, 'filter_status': status})


TRANSITIONS = {'submitted': {'reviewing', 'shortlisted', 'rejected'}, 'reviewing': {'shortlisted', 'rejected'},
               'shortlisted': {'hired', 'rejected'}, 'rejected': set(), 'hired': set(), 'withdrawn': set()}


@login_required
@require_POST
def application_status(request, pk):
    with transaction.atomic():
        application = get_object_or_404(Application.objects.select_for_update().select_related('job'), pk=pk)
        status = request.POST.get('status')
        if request.user.pk == application.candidate_id:
            valid = status == 'withdrawn' and application.status in {'submitted', 'reviewing', 'shortlisted'}
        elif request.user.pk == application.job.recruiter_id:
            valid = status in TRANSITIONS.get(application.status, set())
        else:
            raise PermissionDenied
        if not valid:
            messages.error(request, 'That status change is not available.')
        else:
            application.status = status
            application.save(update_fields=['status', 'updated_at'])
            ApplicationEvent.objects.create(application=application, actor=request.user, status=status)
            messages.success(request, 'Application status updated.')
    return redirect('applications')


@role_required('candidate')
def recommendations(request):
    profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
    error, results = '', []
    try:
        if profile.matching_text().strip():
            results = MatchingEngine().recommendations(profile)
        else:
            error = 'Complete your profile to see your job recommendations.'
    except MatchingUnavailable as exc:
        error = str(exc)
    return render(request, 'recruitment/matches.html', {'results': results, 'error': error, 'candidate_mode': True,
                  'title': 'Your top job matches', 'subtitle': 'Up to 10 open roles, ranked against your current profile.'})


@role_required('recruiter')
def ranking(request, pk):
    job = get_object_or_404(Job, pk=pk, recruiter=request.user)
    error, results = '', []
    try:
        results = MatchingEngine().candidates(job)
    except MatchingUnavailable as exc:
        error = str(exc)
    if request.GET.get('format') == 'csv' and not error:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="kaziforce-job-{job.pk}-top10.csv"'
        writer = csv.writer(response)
        writer.writerow(['Rank', 'Candidate', 'Compatibility (%)', 'Matched skills', 'Missing skills'])
        def safe(value):
            value = str(value)
            return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value
        for i, result in enumerate(results, 1):
            writer.writerow([i, safe(str(result['candidate'])), result['score'], safe('; '.join(s['label'] for s in result['matched_skills'])), safe('; '.join(s['label'] for s in result['missing_skills']))])
        return response
    return render(request, 'recruitment/matches.html', {'results': results, 'error': error, 'job': job,
                  'title': 'Top candidates', 'subtitle': job.title + ' at ' + job.company})


@role_required('candidate')
def match_detail(request, pk):
    job = get_object_or_404(open_jobs(), pk=pk)
    profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
    error, results = '', []
    try:
        # Same corpus as recommendations ensures the detail score agrees with that list.
        results = [r for r in MatchingEngine().rank(open_jobs().select_related('occupation'), [profile], ranking_context='job recommendations') if r['job'].pk == pk]
    except MatchingUnavailable as exc:
        error = str(exc)
    return render(request, 'recruitment/matches.html', {'results': results, 'error': error, 'candidate_mode': True,
                  'title': 'Your compatibility', 'subtitle': job.title + ' at ' + job.company})


def can_view_candidate(user, candidate):
    if user.is_staff or user.pk == candidate.user_id:
        return True
    if user.role != 'recruiter':
        return False
    return candidate.discoverable or Application.objects.filter(candidate_id=candidate.user_id, job__recruiter=user).exclude(status='withdrawn').exists()


@login_required
def candidate_detail(request, pk):
    profile = get_object_or_404(CandidateProfile, user_id=pk, user__is_active=True)
    if not can_view_candidate(request.user, profile):
        raise PermissionDenied
    return render(request, 'recruitment/candidate_detail.html', {'profile': profile})


@login_required
def resume_download(request, pk):
    profile = get_object_or_404(CandidateProfile, user_id=pk, user__is_active=True)
    if not can_view_candidate(request.user, profile):
        raise PermissionDenied
    if not profile.resume:
        return HttpResponse('No resume uploaded.', status=404)
    try:
        response = FileResponse(profile.resume.open('rb'), as_attachment=True, filename='resume' + Path(profile.resume.name).suffix)
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except FileNotFoundError:
        return HttpResponse('Resume file is unavailable.', status=404)
