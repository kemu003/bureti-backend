# students/views.py - Update the SMS sending methods
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.http import HttpResponse
from django.utils import timezone
import csv
import logging

from .models import Student
from .serializers import StudentSerializer
from .permissions import IsAdminOrCommittee
from .filters import StudentFilter
from .sms import send_sms_notification, get_sms_balance

logger = logging.getLogger(__name__)

class StudentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing students
    Only accessible by admin or committee members
    """
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrCommittee]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = StudentFilter
    search_fields = ['name', 'registration_no', 'institution', 'phone', 'guardian_phone']
    ordering_fields = ['name', 'date_applied', 'amount', 'status']
    ordering = ['-date_applied']
    
    def get_queryset(self):
        # Filter by status if provided
        status_param = self.request.query_params.get('status', None)
        if status_param:
            return self.queryset.filter(status=status_param)
        return self.queryset
    
    @action(detail=True, methods=['put'])
    def approve(self, request, pk=None):
        """
        Approve a student allocation
        """
        student = self.get_object()
        
        if student.status == 'approved':
            return Response(
                {"detail": "Student is already approved."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        student.status = 'approved'
        student.date_processed = timezone.now()
        student.updated_by = request.user
        student.save()
        
        serializer = self.get_serializer(student)
        return Response(serializer.data)
    
    @action(detail=True, methods=['put'])
    def reject(self, request, pk=None):
        """
        Reject a student allocation
        """
        student = self.get_object()
        reason = request.data.get('reason', '')
        
        if not reason:
            return Response(
                {"reason": "Rejection reason is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        student.status = 'rejected'
        student.date_processed = timezone.now()
        student.rejection_reason = reason
        student.updated_by = request.user
        student.save()
        
        serializer = self.get_serializer(student)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def send_sms(self, request, pk=None):
        """
        Send SMS notification to student
        Sends to both student and guardian phones when available
        """
        student = self.get_object()
        
        # Check if student has any phone number
        if not student.phone and not student.guardian_phone:
            return Response(
                {'error': 'No phone number available for this student'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determine which phone numbers to send to
        phones_to_send = []
        
        if student.phone:
            phones_to_send.append(('student', student.phone))
        
        if student.guardian_phone:
            phones_to_send.append(('guardian', student.guardian_phone))
        
        # Remove duplicates (in case phone and guardian_phone are the same)
        unique_phones = {}
        for phone_type, phone_number in phones_to_send:
            if phone_number not in unique_phones:
                unique_phones[phone_number] = phone_type
            else:
                # If already exists, update type to include both
                existing_type = unique_phones[phone_number]
                if phone_type not in existing_type:
                    unique_phones[phone_number] = f"{existing_type}/{phone_type}"
        
        # Create the message
        custom_message = request.data.get('message')
        if custom_message:
            message = custom_message
        else:
            message = f"Dear {student.name}, you have been awarded {student.amount:,.2f} KES CDF bursary for your studies at {student.institution}. Congratulations! - Bureti CDF"
        
        results = []
        success_count = 0
        failure_count = 0
        
        # Send SMS to each unique phone number
        for phone_number, phone_type in unique_phones.items():
            logger.info(f"Sending SMS to {phone_type} phone: {phone_number} for student {student.id}")
            
            try:
                success, details = send_sms_notification(
                    phone_number, 
                    message, 
                    student_id=student.id
                )
                
                if success:
                    results.append({
                        'phone': phone_number,
                        'type': phone_type,
                        'status': 'success',
                        'details': details
                    })
                    success_count += 1
                else:
                    results.append({
                        'phone': phone_number,
                        'type': phone_type,
                        'status': 'failed',
                        'error': details
                    })
                    failure_count += 1
                    
            except Exception as e:
                logger.error(f"Error sending SMS to {phone_number}: {str(e)}")
                results.append({
                    'phone': phone_number,
                    'type': phone_type,
                    'status': 'failed',
                    'error': str(e)
                })
                failure_count += 1
        
        # Update student SMS status based on results
        if success_count > 0:
            if failure_count == 0:
                student.sms_status = 'sent'
            else:
                student.sms_status = 'partial'  # You might want to add this status
        else:
            student.sms_status = 'failed'
        
        student.sms_sent_at = timezone.now()
        student.sms_sent_by = request.user
        student.save()
        
        # Prepare response
        if success_count > 0:
            response_data = {
                "success": True,
                "message": f"SMS sent to {success_count} phone(s). {failure_count} failed.",
                "student_id": student.id,
                "total_phones": len(unique_phones),
                "success_count": success_count,
                "failure_count": failure_count,
                "results": results,
                "sms_status": student.sms_status
            }
            
            if failure_count > 0:
                return Response(response_data, status=status.HTTP_207_MULTI_STATUS)
            else:
                return Response(response_data)
        else:
            return Response({
                "success": False,
                "error": "Failed to send SMS to any phone number",
                "student_id": student.id,
                "results": results,
                "sms_status": student.sms_status
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def bulk_send_sms(self, request):
        """
        Send SMS to multiple approved students
        Sends to both student and guardian phones when available
        """
        try:
            # Get student IDs from request
            student_ids = request.data.get('student_ids', [])
            custom_message = request.data.get('message', '')
            
            if not student_ids:
                return Response(
                    {"detail": "No student IDs provided."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get approved students
            students = self.get_queryset().filter(
                id__in=student_ids,
                status='approved'
            )
            
            if not students.exists():
                return Response({
                    "success": True,
                    "message": "No approved students found with the provided IDs."
                })
            
            overall_success = 0
            overall_failure = 0
            student_results = []
            
            for student in students:
                student_phones_sent = 0
                student_phones_failed = 0
                phone_results = []
                
                # Determine which phone numbers to send to
                phones_to_send = []
                
                if student.phone:
                    phones_to_send.append(('student', student.phone))
                
                if student.guardian_phone:
                    phones_to_send.append(('guardian', student.guardian_phone))
                
                # Remove duplicates
                unique_phones = {}
                for phone_type, phone_number in phones_to_send:
                    if phone_number not in unique_phones:
                        unique_phones[phone_number] = phone_type
                    else:
                        existing_type = unique_phones[phone_number]
                        if phone_type not in existing_type:
                            unique_phones[phone_number] = f"{existing_type}/{phone_type}"
                
                # Skip if no phones
                if not unique_phones:
                    student_results.append({
                        'student_id': student.id,
                        'name': student.name,
                        'status': 'failed',
                        'error': 'No phone numbers available'
                    })
                    overall_failure += 1
                    continue
                
                # Create message for this student
                message = custom_message or f"Dear {student.name}, you have been awarded {student.amount:,} KES CDF bursary for your studies at {student.institution}. Congratulations! - Bureti CDF"
                
                # Send SMS to each unique phone number
                for phone_number, phone_type in unique_phones.items():
                    try:
                        success, details = send_sms_notification(
                            phone_number, 
                            message, 
                            student_id=student.id
                        )
                        
                        if success:
                            phone_results.append({
                                'phone': phone_number,
                                'type': phone_type,
                                'status': 'success'
                            })
                            student_phones_sent += 1
                        else:
                            phone_results.append({
                                'phone': phone_number,
                                'type': phone_type,
                                'status': 'failed',
                                'error': details
                            })
                            student_phones_failed += 1
                            
                    except Exception as e:
                        logger.error(f"Error sending SMS to student {student.id}: {str(e)}")
                        phone_results.append({
                            'phone': phone_number,
                            'type': phone_type,
                            'status': 'failed',
                            'error': str(e)
                        })
                        student_phones_failed += 1
                
                # Update student status based on results
                if student_phones_sent > 0:
                    if student_phones_failed == 0:
                        student.sms_status = 'sent'
                    else:
                        student.sms_status = 'partial'
                    overall_success += 1
                else:
                    student.sms_status = 'failed'
                    overall_failure += 1
                
                student.sms_sent_at = timezone.now()
                student.sms_sent_by = request.user
                student.save()
                
                # Add to student results
                student_results.append({
                    'student_id': student.id,
                    'name': student.name,
                    'status': 'sent' if student_phones_sent > 0 else 'failed',
                    'phones_sent': student_phones_sent,
                    'phones_failed': student_phones_failed,
                    'phone_results': phone_results
                })
            
            return Response({
                "success": True,
                "message": f"Bulk SMS operation completed. Success: {overall_success}, Failed: {overall_failure}",
                "total_students": len(student_ids),
                "success_count": overall_success,
                "failure_count": overall_failure,
                "results": student_results
            })
            
        except Exception as e:
            logger.error(f"Error in bulk_send_sms: {str(e)}")
            return Response(
                {"detail": f"Internal server error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def sms_balance(self, request):
        """
        Get SMS balance from provider
        """
        try:
            balance = get_sms_balance()
            
            return Response({
                "success": True,
                "balance": balance,
            })
                
        except Exception as e:
            logger.error(f"Error getting SMS balance: {str(e)}")
            return Response(
                {"detail": f"Internal server error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """
        Export students data to CSV
        """
        students = self.filter_queryset(self.get_queryset())
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="students-{timezone.now().date()}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Name', 'Registration No', 'Phone', 'Guardian Phone',
            'Education Level', 'Institution', 'Course', 'Year', 'Ward',
            'Amount', 'Status', 'SMS Status', 'Date Applied', 'Date Processed'
        ])
        
        for student in students:
            writer.writerow([
                student.id,
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
                student.date_processed.strftime('%Y-%m-%d') if student.date_processed else ''
            ])
        
        return response
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get student statistics
        """
        stats = Student.get_statistics()
        
        # Add ward distribution
        wards = {}
        for ward_code, ward_name in Student.WARD_CHOICES:
            count = Student.objects.filter(ward=ward_code).count()
            if count > 0:
                wards[ward_name] = count
        
        # Add SMS statistics
        sms_stats = {
            'sent': Student.objects.filter(sms_status='sent').count(),
            'failed': Student.objects.filter(sms_status='failed').count(),
            'not_sent': Student.objects.filter(sms_status='not_sent').count(),
            'partial': Student.objects.filter(sms_status='partial').count(),
        }
        
        # Add education level distribution
        education_stats = {}
        for level_code, level_name in Student.EDUCATION_LEVEL_CHOICES:
            count = Student.objects.filter(education_level=level_code).count()
            education_stats[level_name] = count
        
        # Add phone statistics
        phone_stats = {
            'has_student_phone': Student.objects.filter(phone__isnull=False).exclude(phone='').count(),
            'has_guardian_phone': Student.objects.filter(guardian_phone__isnull=False).exclude(guardian_phone='').count(),
            'has_both_phones': Student.objects.filter(
                phone__isnull=False, 
                guardian_phone__isnull=False
            ).exclude(phone='', guardian_phone='').count(),
            'has_no_phones': Student.objects.filter(
                phone__isnull=True, 
                guardian_phone__isnull=True
            ).count() + Student.objects.filter(phone='', guardian_phone='').count(),
        }
        
        stats['wards'] = wards
        stats['sms_statistics'] = sms_stats
        stats['education_statistics'] = education_stats
        stats['phone_statistics'] = phone_stats
        
        return Response(stats)