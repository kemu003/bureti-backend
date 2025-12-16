# students/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone

class Student(models.Model):
    EDUCATION_LEVEL_CHOICES = [
        ('high_school', 'High School'),
        ('college', 'College'),
        ('university', 'University'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('disbursed', 'Disbursed'),
        ('rejected', 'Rejected'),
    ]
    
    SMS_STATUS_CHOICES = [
        ('not_sent', 'Not Sent'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('partial', 'Partial'),
    ]
    
    YEAR_CHOICES = [
        ('Form 1', 'Form 1'),
        ('Form 2', 'Form 2'),
        ('Form 3', 'Form 3'),
        ('Form 4', 'Form 4'),
        ('1st Year', '1st Year'),
        ('2nd Year', '2nd Year'),
        ('3rd Year', '3rd Year'),
        ('4th Year', '4th Year'),
    ]
    
    WARD_CHOICES = [
        ('Chebunyo', 'Chebunyo'),
        ('Cheborge', 'Cheborge'),
        ('Kapkugerwet', 'Kapkugerwet'),
        ('Kimugu', 'Kimugu'),
        ('Kipreres', 'Kipreres'),
        ('Tendeno', 'Tendeno'),
    ]
    
    # Personal Information
    name = models.CharField(max_length=200)
    registration_no = models.CharField(
        max_length=50,  # Changed back to 50
        unique=True,    # Still unique, but now user-provided
        help_text="Student's school registration/admission number"
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    guardian_phone = models.CharField(max_length=20)
    
    # Education Information
    education_level = models.CharField(max_length=20, choices=EDUCATION_LEVEL_CHOICES)
    institution = models.CharField(max_length=200)
    course = models.CharField(max_length=200, blank=True)
    year = models.CharField(max_length=20, choices=YEAR_CHOICES)
    
    # Allocation Information
    ward = models.CharField(max_length=50, choices=WARD_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Status Tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sms_status = models.CharField(max_length=20, choices=SMS_STATUS_CHOICES, default='not_sent')
    
    # SMS Tracking
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    sms_sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_sent_students'
    )
    
    # Rejection tracking
    rejection_reason = models.TextField(blank=True, null=True)
    
    # Dates
    date_applied = models.DateTimeField(default=timezone.now)
    date_processed = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='students_created'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='students_updated'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Student'
        verbose_name_plural = 'Students'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['education_level']),
            models.Index(fields=['ward']),
            models.Index(fields=['sms_status']),
            models.Index(fields=['date_applied']),
            models.Index(fields=['registration_no']),  # Added for faster lookups
        ]
    
    def __str__(self):
        return f"{self.name} - {self.registration_no}"
    
    def save(self, *args, **kwargs):
        # For high school students, ensure course is empty
        if self.education_level == 'high_school':
            self.course = ''
        
        # Set date_processed if status is approved/disbursed/rejected and not already set
        if self.status in ['approved', 'disbursed', 'rejected'] and not self.date_processed:
            self.date_processed = timezone.now()
        
        super().save(*args, **kwargs)
    
    def get_education_level_display(self):
        """Get human-readable education level"""
        return dict(self.EDUCATION_LEVEL_CHOICES).get(self.education_level, self.education_level)
    
    def get_status_display(self):
        """Get human-readable status"""
        return dict(self.STATUS_CHOICES).get(self.status, self.status)
    
    def get_sms_status_display(self):
        """Get human-readable SMS status"""
        return dict(self.SMS_STATUS_CHOICES).get(self.sms_status, self.sms_status)
    
    def get_year_display(self):
        """Get human-readable year"""
        return dict(self.YEAR_CHOICES).get(self.year, self.year)
    
    def get_ward_display(self):
        """Get human-readable ward"""
        return dict(self.WARD_CHOICES).get(self.ward, self.ward)
    
    @classmethod
    def get_statistics(cls):
        """Get comprehensive statistics about students"""
        from django.db.models import Sum, Count, Q
        
        stats = {
            'total': cls.objects.count(),
            'pending': cls.objects.filter(status='pending').count(),
            'approved': cls.objects.filter(status='approved').count(),
            'disbursed': cls.objects.filter(status='disbursed').count(),
            'rejected': cls.objects.filter(status='rejected').count(),
            'total_amount': cls.objects.aggregate(total=Sum('amount'))['total'] or 0,
        }
        
        # Education level statistics
        education_stats = {}
        for code, name in cls.EDUCATION_LEVEL_CHOICES:
            education_stats[name] = cls.objects.filter(education_level=code).count()
        
        # Ward statistics
        ward_stats = {}
        for code, name in cls.WARD_CHOICES:
            ward_stats[name] = cls.objects.filter(ward=code).count()
        
        # SMS statistics
        sms_stats = {
            'sent': cls.objects.filter(sms_status='sent').count(),
            'failed': cls.objects.filter(sms_status='failed').count(),
            'not_sent': cls.objects.filter(sms_status='not_sent').count(),
            'partial': cls.objects.filter(sms_status='partial').count(),
        }
        
        stats['education_stats'] = education_stats
        stats['ward_stats'] = ward_stats
        stats['sms_stats'] = sms_stats
        
        return stats
    
    def can_send_sms(self):
        """Check if SMS can be sent to this student"""
        if not self.phone and not self.guardian_phone:
            return False, "No phone number available"
        
        if self.status != 'approved':
            return False, "Student must be approved to send SMS"
        
        if self.sms_status == 'sent':
            return False, "SMS already sent"
        
        return True, "OK"
    
    def mark_sms_sent(self, user=None):
        """Mark SMS as sent"""
        self.sms_status = 'sent'
        self.sms_sent_at = timezone.now()
        if user:
            self.sms_sent_by = user
        self.save()
    
    def mark_sms_failed(self):
        """Mark SMS as failed"""
        self.sms_status = 'failed'
        self.save()
    
    def approve(self, user=None):
        """Approve student"""
        self.status = 'approved'
        self.date_processed = timezone.now()
        if user:
            self.updated_by = user
        self.save()
    
    def reject(self, reason, user=None):
        """Reject student"""
        self.status = 'rejected'
        self.date_processed = timezone.now()
        self.rejection_reason = reason
        if user:
            self.updated_by = user
        self.save()