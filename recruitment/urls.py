from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path('catalogue/search/', views.catalogue_search, name='catalogue_search'),
    path('', views.home, name='home'), path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(), name='login'), path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('password/change/', auth_views.PasswordChangeView.as_view(template_name='recruitment/password_form.html', success_url='/dashboard/'), name='password_change'),
    path('dashboard/', views.dashboard, name='dashboard'), path('profile/', views.profile, name='profile'),
    path('jobs/', views.jobs, name='jobs'), path('jobs/mine/', views.my_jobs, name='my_jobs'),
    path('jobs/new/', views.job_edit, name='job_create'), path('jobs/<int:pk>/', views.job_detail, name='job_detail'),
    path('jobs/<int:pk>/edit/', views.job_edit, name='job_edit'), path('jobs/<int:pk>/close/', views.job_close, name='job_close'),
    path('jobs/<int:pk>/apply/', views.apply, name='apply'), path('jobs/<int:pk>/ranking/', views.ranking, name='ranking'),
    path('jobs/<int:pk>/match/', views.match_detail, name='match_detail'), path('recommendations/', views.recommendations, name='recommendations'),
    path('applications/', views.applications, name='applications'), path('applications/<int:pk>/status/', views.application_status, name='application_status'),
    path('candidates/<int:pk>/', views.candidate_detail, name='candidate_detail'), path('candidates/<int:pk>/resume/', views.resume_download, name='resume_download'),
]
