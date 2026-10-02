"""Public view imports grouped by feature."""

from .accounts import dashboard, home, register, role_required
from .applications import (
    application_list,
    submit_application,
    update_application_status,
)
from .catalogue import catalogue_search
from .jobs import job_close, job_create_or_edit, job_detail, job_list, my_jobs
from .matches import candidate_rankings, job_recommendations, match_detail
from .profiles import candidate_detail, can_view_candidate, profile_edit, resume_download

# Compatibility names keep existing URL configuration and third-party imports working.
applications = application_list
application_status = update_application_status
apply = submit_application
jobs = job_list
job_edit = job_create_or_edit
profile = profile_edit
ranking = candidate_rankings
recommendations = job_recommendations

__all__ = [
    'application_list',
    'application_status',
    'applications',
    'apply',
    'candidate_detail',
    'candidate_rankings',
    'can_view_candidate',
    'catalogue_search',
    'dashboard',
    'home',
    'job_close',
    'job_create_or_edit',
    'job_detail',
    'job_edit',
    'job_list',
    'job_recommendations',
    'jobs',
    'match_detail',
    'my_jobs',
    'profile',
    'profile_edit',
    'ranking',
    'recommendations',
    'register',
    'resume_download',
    'role_required',
    'submit_application',
    'update_application_status',
]
