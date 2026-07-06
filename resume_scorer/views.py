from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth.models import User
from rest_framework import status
from .models import ResumeScan
from .serializers import ResumeScanSerializer, SignupSerializer, UserSerializer
from .ats_engine import analyze_resume
import tempfile
import os


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def score_resume_view(request):
    resume_file = request.FILES.get('resume')
    job_description = request.data.get('job_description', '').strip()

    if not resume_file:
        return Response(
            {"error": "Resume file is required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        for chunk in resume_file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        result = analyze_resume(tmp_path, job_description if job_description else None)
    finally:
        os.remove(tmp_path)

    scan = ResumeScan.objects.create(
        user=request.user if request.user.is_authenticated else None,
        resume_file_name=resume_file.name,
        resume_text=result['resume_text'],
        job_description=job_description,
        score=result['overall_score'],
        matched_keywords=result['matched_keywords'],
        missing_keywords=result['missing_keywords'],
    )

    return Response({
        'id': scan.id,
        'resume_file_name': scan.resume_file_name,
        'overall_score': result['overall_score'],
        'quality_score': result['quality_score'],
        'jd_match_score': result['jd_match_score'],
        'quality_breakdown': result['quality_breakdown'],
        'section_scores': result['section_scores'],
        'matched_keywords': result['matched_keywords'],
        'missing_keywords': result['missing_keywords'],
        'semantic_similarity': result['semantic_similarity'],
        'suggestions': result['suggestions'],
        'has_jd': result['has_jd'],
        'created_at': scan.created_at,
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def history_view(request):
    scans = ResumeScan.objects.all().order_by('-created_at')[:20]
    serializer = ResumeScanSerializer(scans, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([AllowAny])
def signup_view(request):
    serializer = SignupSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response(UserSerializer(request.user).data)


@api_view(['POST'])
@permission_classes([AllowAny])
def google_auth_view(request):
    token = request.data.get('token')

    if not token:
        return Response(
            {"error": "Token is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        import urllib.request
        import json as json_lib

        url = f'https://oauth2.googleapis.com/tokeninfo?id_token={token}'
        with urllib.request.urlopen(url) as response:
            google_data = json_lib.loads(response.read())

        email = google_data.get('email')
        if not email:
            return Response(
                {"error": "Could not get email from Google", "google_data": google_data},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Handle duplicate username
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        try:
            user = User.objects.get(email=email)
            created = False
        except User.DoesNotExist:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=None
            )
            user.set_unusable_password()
            user.save()
            created = True

        if created:
            user.set_unusable_password()
            user.save()

        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        })

    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        return Response(
            {"error": f"Google token verification failed: {error_body}"},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {"error": f"Google authentication failed: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST
        )