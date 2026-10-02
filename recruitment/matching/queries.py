from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from ..models import Application, CandidateProfile, Job


def open_jobs():
    return Job.objects.filter(status=Job.Status.OPEN, recruiter__is_active=True).filter(
        Q(deadline__isnull=True) | Q(deadline__gte=timezone.localdate())
    )


def eligible_profiles(job):
    applied = Application.objects.filter(candidate_id=OuterRef('user_id'), job=job).exclude(
        status='withdrawn'
    )
    return (
        CandidateProfile.objects.filter(user__is_active=True, user__role='candidate')
        .annotate(applied_to_job=Exists(applied))
        .filter(Q(discoverable=True) | Q(applied_to_job=True))
        .select_related('user')
    )
