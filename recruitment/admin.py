from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, CandidateProfile, RecruiterProfile, Job, JobRequirement, Skill, Occupation, Application, ApplicationEvent, MatchResult


@admin.register(User)
class KaziForceUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('KaziForce', {'fields': ('role',)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('KaziForce', {'fields': ('email', 'role')}),)
    list_display = ['username', 'email', 'role', 'is_active', 'is_staff']


class RequirementInline(admin.TabularInline):
    model = JobRequirement
    autocomplete_fields = ['skill']
    extra = 0


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'recruiter', 'status', 'deadline']
    list_filter = ['status']
    search_fields = ['title', 'company']
    inlines = [RequirementInline]


@admin.register(Skill, Occupation)
class TaxonomyAdmin(admin.ModelAdmin):
    search_fields = ['preferred_label', 'alternative_labels']
    list_display = ['preferred_label', 'version']


@admin.register(Application, ApplicationEvent, MatchResult)
class AuditAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(CandidateProfile)
admin.site.register(RecruiterProfile)
admin.site.site_header = 'KaziForce administration'
admin.site.site_title = 'KaziForce'
