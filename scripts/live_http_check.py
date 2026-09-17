"""Check the actual local HTTP server with fictional demo credentials and CSRF."""
import http.cookiejar
import json
import os
from pathlib import Path
import re
import sys
from time import perf_counter
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor, Request

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from recruitment.models import Job

base = 'http://127.0.0.1:8000'
credentials = (root / '.local/demo-accounts.txt').read_text(encoding='utf-8')
password = next(line.split(': ', 1)[1] for line in credentials.splitlines() if line.startswith('Demo password: '))
opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
records = []


def get(path):
    start = perf_counter()
    with opener.open(base + path, timeout=120) as response:
        text = response.read().decode('utf-8')
        assert response.status == 200
    return text, round((perf_counter()-start)*1000, 2)


def token(text):
    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', text)
    assert match, 'CSRF token missing'
    return match.group(1)


for username in ['demo_candidate', 'demo_recruiter']:
    html, _ = get('/login/')
    data = urlencode({'username': username, 'password': password, 'csrfmiddlewaretoken': token(html)}).encode()
    with opener.open(Request(base + '/login/', data=data, headers={'Referer': base + '/login/'}), timeout=120) as response:
        assert response.geturl() == base + '/dashboard/', 'Demo login did not reach dashboard'
        response.read()
    if username == 'demo_candidate':
        for stage in ['first_request', 'warm_request']:
            html, elapsed = get('/recommendations/')
            assert 'Your top job matches' in html
            records.append({'page': 'recommendations', 'stage': stage, 'status': 200, 'elapsed_ms': elapsed})
    else:
        job = Job.objects.filter(recruiter__username=username).last()
        html, elapsed = get(f'/jobs/{job.pk}/ranking/')
        assert 'Top candidates' in html
        records.append({'page': 'ranking', 'stage': 'warm_request', 'status': 200, 'elapsed_ms': elapsed})
    data = urlencode({'csrfmiddlewaretoken': token(html)}).encode()
    with opener.open(Request(base + '/logout/', data=data, headers={'Referer': base + '/dashboard/'}), timeout=120) as response:
        assert response.geturl() == base + '/'
        response.read()

report = {'checks': records, 'csrf_login_logout': 'passed', 'note': 'Actual localhost HTTP requests using fictional demo accounts; not a browser visual review.'}
(root / '.local/live-http-results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
