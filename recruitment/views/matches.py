import csv

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from ..matching import MatchingEngine, MatchingUnavailable, open_jobs
from ..models import CandidateProfile, Job
from .accounts import role_required


@role_required('candidate')
def job_recommendations(request):
    profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
    error, results = '', []
    try:
        if profile.matching_text().strip():
            results = MatchingEngine().recommendations(profile)
        else:
            error = 'Complete your profile to see your job recommendations.'
    except MatchingUnavailable as exc:
        error = str(exc)
    return render(
        request,
        'recruitment/matches.html',
        {
            'results': results,
            'error': error,
            'candidate_mode': True,
            'title': 'Your top job matches',
            'subtitle': 'Up to 10 open roles, ranked against your current profile.',
        },
    )


def safe_csv_value(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value


@role_required('recruiter')
def candidate_rankings(request, pk):
    job = get_object_or_404(Job, pk=pk, recruiter=request.user)
    error, results = '', []
    try:
        results = MatchingEngine().candidates(job)
    except MatchingUnavailable as exc:
        error = str(exc)
    if request.GET.get('format') == 'csv' and not error:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = (
            f'attachment; filename="kaziforce-job-{job.pk}-top10.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(
            ['Rank', 'Candidate', 'Compatibility (%)', 'Matched skills', 'Missing skills']
        )
        for index, result in enumerate(results, 1):
            writer.writerow(
                [
                    index,
                    safe_csv_value(str(result['candidate'])),
                    result['score'],
                    safe_csv_value(
                        '; '.join(skill['label'] for skill in result['matched_skills'])
                    ),
                    safe_csv_value(
                        '; '.join(skill['label'] for skill in result['missing_skills'])
                    ),
                ]
            )
        return response
    return render(
        request,
        'recruitment/matches.html',
        {
            'results': results,
            'error': error,
            'job': job,
            'title': 'Top candidates',
            'subtitle': job.title + ' at ' + job.company,
        },
    )


@role_required('candidate')
def match_detail(request, pk):
    job = get_object_or_404(open_jobs(), pk=pk)
    profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
    error, results = '', []
    try:
        ranked = MatchingEngine().rank(
            open_jobs().select_related('occupation'),
            [profile],
            ranking_context='job recommendations',
        )
        results = [result for result in ranked if result['job'].pk == pk]
    except MatchingUnavailable as exc:
        error = str(exc)
    return render(
        request,
        'recruitment/matches.html',
        {
            'results': results,
            'error': error,
            'candidate_mode': True,
            'title': 'Your compatibility',
            'subtitle': job.title + ' at ' + job.company,
        },
    )
