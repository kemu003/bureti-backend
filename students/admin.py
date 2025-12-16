# students/admin.py
from django.contrib import admin
from .models import Student
import csv
from django.http import HttpResponse

class StudentAdmin(admin.ModelAdmin):
    list_display = ['name', 'registration_no', 'institution', 'ward','phone',            # Add this
    'guardian_phone', 'amount', 'status', 'sms_status']
    list_filter = ['status', 'sms_status', 'education_level', 'ward', 'year']
    search_fields = ['name', 'registration_no', 'institution', 'phone', 'guardian_phone']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    actions = ['export_as_csv', 'approve_selected', 'reject_selected', 'send_sms_selected']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('name', 'registration_no', 'phone', 'guardian_phone')
        }),
        ('Education Information', {
            'fields': ('education_level', 'institution', 'course', 'year')
        }),
        ('Allocation Information', {
            'fields': ('ward', 'amount', 'status', 'sms_status')
        }),
        ('Dates', {
            'fields': ('date_applied', 'date_processed')
        }),
        ('Audit Information', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="students.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Registration No', 'Phone', 'Guardian Phone',
            'Education Level', 'Institution', 'Course', 'Year', 'Ward',
            'Amount', 'Status', 'SMS Status', 'Date Applied', 'Date Processed'
        ])
        
        for student in queryset:
            writer.writerow([
                student.name,
                student.registration_no,
                student.phone or '',
                student.guardian_phone,
                student.get_education_level_display(),
                student.institution,
                student.course,
                student.year,
                student.ward,
                student.amount,
                student.get_status_display(),
                student.get_sms_status_display(),
                student.date_applied.strftime('%Y-%m-%d'),
                student.date_processed.strftime('%Y-%m-%d') if student.date_processed else '',
            ])
        
        return response
    
    export_as_csv.short_description = "Export selected students as CSV"
    
    def approve_selected(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='approved')
        self.message_user(request, f"{updated} students approved.")
    
    approve_selected.short_description = "Approve selected students"
    
    def reject_selected(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='rejected')
        self.message_user(request, f"{updated} students rejected.")
    
    reject_selected.short_description = "Reject selected students"
    
    def send_sms_selected(self, request, queryset):
        from .sms import send_sms_notification
        sent = 0
        failed = 0
        
        for student in queryset:
            if student.status == 'approved' and student.sms_status == 'not_sent':
                # Use guardian phone if student phone not available
                phone = student.phone or student.guardian_phone
                if phone:
                    message = f"Dear {student.name}, you have been awarded KES {student.amount:,} CDF bursary for your studies at {student.institution}. Congratulations! - Bureti CDF"
                    success = send_sms_notification(phone, message, student.id)
                    if success:
                        student.sms_status = 'sent'
                        student.save()
                        sent += 1
                    else:
                        failed += 1
        
        self.message_user(request, f"SMS sent: {sent}, Failed: {failed}")
    
    send_sms_selected.short_description = "Send SMS to selected students"

admin.site.register(Student, StudentAdmin)