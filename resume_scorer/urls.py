from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import score_resume_view, history_view, signup_view, me_view, google_auth_view

urlpatterns = [
    path('score/', score_resume_view, name='score-resume'),
    path('history/', history_view, name='scan-history'),
    path('auth/signup/', signup_view, name='signup'),
    path('auth/login/', TokenObtainPairView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/me/', me_view, name='me'),
    path('auth/google/', google_auth_view, name='google-auth'),
]