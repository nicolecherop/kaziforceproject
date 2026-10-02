from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import CandidateForm, RecruiterForm
from ..models import Application, CandidateProfile, RecruiterProfile


@login_required
def profile_edit(request):
    candidate = request.user.role == 'candidate'
    model, form_class = (
        (CandidateProfile, CandidateForm)
        if candidate
        else (RecruiterProfile, RecruiterForm)
    )
    instance, _ = model.objects.get_or_create(user=request.user)
    form = form_class(
        request.POST or None,
        request.FILES or None,
        instance=instance,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(
            request,
            'Profile saved. New matches will use your latest information.',
        )
        return redirect('profile')
    return render(
        request,
        'recruitment/form.html',
        {
            'form': form,
            'title': 'Your professional profile' if candidate else 'Your organisation',
            'subtitle': (
                'Tell your story through the skills and experience you can demonstrate.'
                if candidate
                else 'Introduce the organisation you recruit for.'
            ),
            'profile': instance,
            'is_profile': True,
        },
    )


def can_view_candidate(user, candidate):
    if user.is_staff or user.pk == candidate.user_id:
        return True
    if user.role != 'recruiter':
        return False
    valid_application = Application.objects.filter(
        candidate_id=candidate.user_id,
        job__recruiter=user,
    ).exclude(status='withdrawn')
    return candidate.discoverable or valid_application.exists()


@login_required
def candidate_detail(request, pk):
    profile = get_object_or_404(
        CandidateProfile,
        user_id=pk,
        user__is_active=True,
    )
    if not can_view_candidate(request.user, profile):
        raise PermissionDenied
    return render(request, 'recruitment/candidate_detail.html', {'profile': profile})


@login_required
def resume_download(request, pk):
    profile = get_object_or_404(
        CandidateProfile,
        user_id=pk,
        user__is_active=True,
    )
    if not can_view_candidate(request.user, profile):
        raise PermissionDenied
    if not profile.resume:
        return HttpResponse('No resume uploaded.', status=404)
    try:
        response = FileResponse(
            profile.resume.open('rb'),
            as_attachment=True,
            filename='resume' + Path(profile.resume.name).suffix,
        )
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except FileNotFoundError:
        return HttpResponse('Resume file is unavailable.', status=404)
