import uuid
import re
from pathlib import Path
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        CANDIDATE = 'candidate', 'Candidate'
        RECRUITER = 'recruiter', 'Recruiter'
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.CANDIDATE)
    email = models.EmailField(unique=True)

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)


def resume_path(instance, filename):
    return f'resumes/{instance.user_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


class CandidateProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='candidate_profile')
    headline = models.CharField(max_length=180, blank=True)
    location = models.CharField(max_length=120, blank=True)
    summary = models.TextField(blank=True, max_length=6000)
    skills_text = models.TextField(blank=True, max_length=6000)
    qualifications = models.TextField(blank=True, max_length=6000)
    certifications = models.TextField(blank=True, max_length=6000)
    experience = models.TextField(blank=True, max_length=10000)
    portfolio_url = models.URLField(blank=True)
    resume = models.FileField(upload_to=resume_path, blank=True)
    resume_text = models.TextField(blank=True, max_length=30000)
    discoverable = models.BooleanField(default=False, help_text='Allow recruiters to include your profile in candidate searches.')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    def matching_text(self):
        # Names, contact information and location are deliberately excluded.
        text = '\n'.join([self.headline, self.summary, self.skills_text, self.qualifications,
                          self.certifications, self.experience, self.resume_text])
        for value in [self.user.get_full_name(), self.user.email, self.location]:
            if len(value.strip()) >= 3:
                text = re.sub(r'(?<!\w)' + re.escape(value.strip()) + r'(?!\w)', ' ', text, flags=re.IGNORECASE)
        text = re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b', ' ', text)
        return re.sub(r'(?<!\w)\+?\d[\d\s()-]{7,}\d(?!\w)', ' ', text)

    @property
    def completion(self):
        fields = [self.headline, self.summary, self.skills_text, self.qualifications, self.experience]
        return sum(bool(f.strip()) for f in fields) * 20


class RecruiterProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='recruiter_profile')
    company = models.CharField(max_length=180)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True, max_length=6000)

    def __str__(self):
        return self.company


class Skill(models.Model):
    uri = models.URLField(unique=True, max_length=300)
    preferred_label = models.CharField(max_length=300)
    alternative_labels = models.TextField(blank=True)
    description = models.TextField(blank=True)
    version = models.CharField(max_length=30, default='1.2.1')

    class Meta:
        ordering = ['preferred_label']

    def __str__(self):
        return self.preferred_label


class Occupation(models.Model):
    uri = models.URLField(unique=True, max_length=300)
    preferred_label = models.CharField(max_length=300)
    alternative_labels = models.TextField(blank=True)
    version = models.CharField(max_length=30, default='1.2.1')

    class Meta:
        ordering = ['preferred_label']

    def __str__(self):
        return self.preferred_label


class Job(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        OPEN = 'open', 'Open'
        CLOSED = 'closed', 'Closed'
    recruiter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='jobs')
    title = models.CharField(max_length=180)
    company = models.CharField(max_length=180)
    location = models.CharField(max_length=120)
    employment_type = models.CharField(max_length=30, choices=[('full_time', 'Full time'), ('part_time', 'Part time'), ('contract', 'Contract'), ('internship', 'Internship')])
    description = models.TextField(max_length=12000)
    qualifications = models.TextField(blank=True, max_length=6000)
    certifications = models.TextField(blank=True, max_length=6000)
    experience = models.TextField(blank=True, max_length=6000)
    occupation = models.ForeignKey(Occupation, null=True, blank=True, on_delete=models.SET_NULL)
    deadline = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def accepting_applications(self):
        return self.status == self.Status.OPEN and (not self.deadline or self.deadline >= timezone.localdate())

    def matching_text(self):
        return '\n'.join([self.title, self.description, self.qualifications, self.certifications, self.experience])


class JobRequirement(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='requirements')
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT)
    priority = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    essential = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['job', 'skill'], name='unique_job_skill'),
                       models.CheckConstraint(condition=models.Q(priority__gte=1, priority__lte=5), name='priority_range')]


class Application(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = 'submitted', 'Submitted'
        REVIEWING = 'reviewing', 'Under review'
        SHORTLISTED = 'shortlisted', 'Shortlisted'
        REJECTED = 'rejected', 'Not selected'
        HIRED = 'hired', 'Hired'
        WITHDRAWN = 'withdrawn', 'Withdrawn'
    candidate = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    cover_note = models.TextField(blank=True, max_length=4000)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.SUBMITTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['candidate', 'job'], name='unique_application')]


class ApplicationEvent(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='events')
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=15, choices=Application.Status.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class MatchResult(models.Model):
    candidate = models.ForeignKey(User, on_delete=models.CASCADE, related_name='matches')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='matches')
    score = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    matched_skills = models.JSONField(default=list)
    missing_skills = models.JSONField(default=list)
    explanation = models.JSONField(default=dict)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['candidate', 'job'], name='unique_match')]
