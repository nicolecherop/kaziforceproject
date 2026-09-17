import secrets
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from recruitment.models import User, CandidateProfile, RecruiterProfile, Job, JobRequirement, Skill, Application, ApplicationEvent


class Command(BaseCommand):
    help = 'Create clearly labelled fictional demo data and private random credentials. Existing users are not modified.'

    @transaction.atomic
    def handle(self, **options):
        if User.objects.filter(username='demo_recruiter').exists():
            self.stdout.write('Demo accounts already exist; no existing data was changed.')
            return
        if not Skill.objects.exists():
            raise CommandError('Import ESCO before creating the demo so requirements use real concepts.')
        password = secrets.token_urlsafe(18)
        recruiter = User.objects.create_user('demo_recruiter', email='recruiter@kaziforce.example', password=password,
                                             first_name='Alex', last_name='Demo', role='recruiter')
        RecruiterProfile.objects.create(user=recruiter, company='KaziForce Demo Studio', description='Fictional organisation for capstone demonstrations.')
        roles = [
            ('Python Developer', 'Build and maintain web applications with Python, Django and SQL. Write software tests and collaborate with the team.', 'Python (computer programming)', ['Python', 'SQL', 'JavaScript']),
            ('Data Analyst', 'Analyse data using SQL, Python and statistics. Communicate findings and create reports.', 'SQL', ['SQL', 'Python', 'statistics']),
        ]
        jobs = []
        for title, description, main_skill, skill_names in roles:
            job = Job.objects.create(recruiter=recruiter, title=title, company='KaziForce Demo Studio', location='Nairobi / Hybrid',
                employment_type='full_time', description=description + '\nThis is a fictional capstone demonstration role.',
                qualifications='Computer science or related qualification', experience='Practical project experience', status='open')
            for name in skill_names:
                skill = Skill.objects.filter(preferred_label__iexact=name).first() or Skill.objects.filter(preferred_label__istartswith=name + ' (').first()
                if skill:
                    JobRequirement.objects.get_or_create(job=job, skill=skill, defaults={'priority': 5 if name in main_skill else 2})
            jobs.append(job)
        specialties = ['Python SQL Django', 'HTML CSS JavaScript', 'SQL Python statistics']
        for i, skills in enumerate(specialties, 1):
            username = 'demo_candidate' if i == 1 else f'demo_candidate_{i:02}'
            user = User.objects.create_user(username, email=f'candidate{i}@kaziforce.example', password=password,
                first_name=['Sam', 'Morgan', 'Taylor'][i-1], last_name='Demo')
            CandidateProfile.objects.create(user=user, headline='Software and data professional', location='Nairobi',
                summary='Fictional profile for demonstrating candidate-job matching.', skills_text=skills,
                qualifications='Computer science qualification', experience=f'Built practical projects using {skills}.', discoverable=True)
            if i == 1:
                app = Application.objects.create(candidate=user, job=jobs[0], cover_note='Demo application for the capstone walkthrough.')
                ApplicationEvent.objects.create(application=app, actor=user, status='submitted')
        private = settings.BASE_DIR / '.local'
        private.mkdir(exist_ok=True)
        lines = ['KaziForce fictional demo accounts', '', 'Recruiter: demo_recruiter', 'Candidate: demo_candidate', f'Demo password: {password}']
        if not User.objects.filter(is_superuser=True).exists():
            admin_password = secrets.token_urlsafe(24)
            User.objects.create_superuser('kaziforce_admin', email='admin@kaziforce.example', password=admin_password)
            lines += ['', 'Administrator: kaziforce_admin', f'Administrator password: {admin_password}']
        (private / 'demo-accounts.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self.stdout.write(self.style.SUCCESS('Created 3 fictional candidates, 2 jobs, and 1 demo application. Credentials saved privately in .local/demo-accounts.txt.'))
