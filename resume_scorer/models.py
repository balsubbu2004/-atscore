from django.db import models
from django.contrib.auth.models import User

class ResumeScan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scans', null=True, blank=True)
    resume_file_name = models.CharField(max_length=255)
    resume_text = models.TextField()
    job_description = models.TextField()
    score = models.IntegerField()
    matched_keywords = models.JSONField()
    missing_keywords = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.resume_file_name} - {self.score}%"