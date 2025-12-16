# students/serializers.py
import re
from rest_framework import serializers
from .models import Student
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import IntegrityError

User = get_user_model()

class StudentSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    updated_by = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = Student
        fields = [
            'id', 'name', 'registration_no', 'phone', 'guardian_phone',
            'education_level', 'institution', 'course', 'year', 'ward',
            'amount', 'status', 'sms_status', 'date_applied', 'date_processed',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 
            'created_by', 'updated_by', 'date_applied'
        ]
        extra_kwargs = {
            'registration_no': {'required': True},  # Now required
            'guardian_phone': {'required': True},
            'institution': {'required': True},
            'ward': {'required': True},
            'amount': {'required': True},
            'date_processed': {'required': False},
        }
    
    def validate_registration_no(self, value):
        """Validate that registration number is unique"""
        # Check if another student already has this registration number
        # Exclude current instance during updates
        if self.instance:
            if Student.objects.filter(registration_no=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError(
                    f"Registration number '{value}' already exists for another student."
                )
        else:
            # For new students, check if it exists
            if Student.objects.filter(registration_no=value).exists():
                raise serializers.ValidationError(
                    f"Registration number '{value}' already exists."
                )
        return value
    
    def validate_phone(self, value):
        """Validate and format student phone number for Blessed Texts"""
        if not value:
            return value
        
        cleaned = self._format_phone_for_sms(value)
        if not cleaned:
            raise serializers.ValidationError(
                "Invalid phone number. Valid formats: 07XXXXXXXX, 7XXXXXXXX, 2547XXXXXXXX"
            )
        
        return cleaned
    
    def validate_guardian_phone(self, value):
        """Validate and format guardian phone number for Blessed Texts"""
        if not value:
            raise serializers.ValidationError("Guardian phone number is required")
        
        cleaned = self._format_phone_for_sms(value)
        if not cleaned:
            raise serializers.ValidationError(
                "Invalid guardian phone number. Valid formats: 07XXXXXXXX, 7XXXXXXXX, 2547XXXXXXXX"
            )
        
        return cleaned
    
    def _format_phone_for_sms(self, phone):
        """Convert phone to 2547XXXXXXXX format for Blessed Texts"""
        if not phone:
            return None
        
        # Remove all non-digit characters
        digits = re.sub(r'[^\d]', '', str(phone))
        
        # Convert to 2547XXXXXXXX format
        if digits.startswith('2547') and len(digits) == 12:
            return digits  # Already correct
            
        elif digits.startswith('07') and len(digits) == 10 and digits[1] == '7':
            return '254' + digits[1:]  # 07XXXXXXXX → 2547XXXXXXXX
            
        elif digits.startswith('7') and len(digits) == 9:
            return '254' + digits  # 7XXXXXXXX → 2547XXXXXXXX
            
        # Also handle +254 format
        elif digits.startswith('254') and len(digits) == 12:
            return digits
            
        else:
            return None
    
    def validate(self, data):
        """Main validation method"""
        education_level = data.get('education_level')
        
        # Ensure course is empty for high school students
        if education_level == 'high_school':
            data['course'] = ''
        
        # Validate amount
        amount = data.get('amount')
        if amount is not None and amount <= 0:
            raise serializers.ValidationError({"amount": "Amount must be greater than 0"})
        
        # Validate phone and guardian phone don't match
        phone = data.get('phone')
        guardian_phone = data.get('guardian_phone')
        
        if phone and guardian_phone and phone == guardian_phone:
            raise serializers.ValidationError({
                'phone': "Student phone and guardian phone cannot be the same",
                'guardian_phone': "Student phone and guardian phone cannot be the same"
            })
        
        return data
    
    def validate_year(self, value):
        """Validate year based on education level"""
        education_level = None
        
        # Get education level from instance (update) or initial data (create)
        if self.instance and hasattr(self.instance, 'education_level'):
            education_level = self.instance.education_level
        else:
            education_level = self.initial_data.get('education_level')
        
        if not education_level:
            return value
        
        if education_level == 'high_school':
            valid_years = ['Form 1', 'Form 2', 'Form 3', 'Form 4']
            if value not in valid_years:
                raise serializers.ValidationError(
                    f"For high school, year must be one of: {', '.join(valid_years)}"
                )
        elif education_level in ['college', 'university']:
            valid_years = ['1st Year', '2nd Year', '3rd Year', '4th Year']
            if value not in valid_years:
                raise serializers.ValidationError(
                    f"For college/university, year must be one of: {', '.join(valid_years)}"
                )
        
        return value
    
    def validate_course(self, value):
        """Validate course based on education level"""
        education_level = None
        
        # Get education level from instance (update) or initial data (create)
        if self.instance and hasattr(self.instance, 'education_level'):
            education_level = self.instance.education_level
        else:
            education_level = self.initial_data.get('education_level')
        
        if not education_level:
            return value
        
        if education_level == 'high_school' and value:
            raise serializers.ValidationError("Course should be empty for high school students")
        elif education_level in ['college', 'university'] and not value:
            raise serializers.ValidationError("Course is required for college/university students")
        
        return value
    
    def create(self, validated_data):
        request = self.context.get('request')
        
        # Set created_by to current user if available
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        
        # Set date_applied to current time
        validated_data['date_applied'] = timezone.now()
        
        try:
            # Create the student instance
            instance = super().create(validated_data)
            return instance
        except IntegrityError as e:
            if 'registration_no' in str(e):
                raise serializers.ValidationError({
                    'registration_no': f'Registration number "{validated_data.get("registration_no")}" already exists.'
                })
            raise
    
    def update(self, instance, validated_data):
        request = self.context.get('request')
        
        # Set updated_by to current user if available
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['updated_by'] = request.user
        
        # Update course for high school students
        if validated_data.get('education_level') == 'high_school':
            validated_data['course'] = ''
        
        return super().update(instance, validated_data)


class StudentExportSerializer(serializers.ModelSerializer):
    education_level_display = serializers.CharField(source='get_education_level_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    sms_status_display = serializers.CharField(source='get_sms_status_display', read_only=True)
    ward_display = serializers.CharField(source='get_ward_display', read_only=True)
    year_display = serializers.CharField(source='get_year_display', read_only=True)
    
    class Meta:
        model = Student
        fields = [
            'name', 'registration_no', 'phone', 'guardian_phone',
            'education_level', 'education_level_display', 'institution', 
            'course', 'year', 'year_display', 'ward', 'ward_display', 
            'amount', 'status', 'status_display',
            'sms_status', 'sms_status_display', 'date_applied', 'date_processed'
        ]


class StudentImportSerializer(serializers.ModelSerializer):
    """Serializer for importing students from CSV/Excel"""
    class Meta:
        model = Student
        fields = [
            'name', 'registration_no', 'phone', 'guardian_phone', 'education_level', 
            'institution', 'course', 'year', 'ward', 'amount'
        ]
    
    def validate(self, data):
        # Basic validation for import
        if not data.get('guardian_phone'):
            raise serializers.ValidationError({
                'guardian_phone': 'Guardian phone is required for import'
            })
        
        if not data.get('institution'):
            raise serializers.ValidationError({
                'institution': 'Institution is required for import'
            })
        
        if not data.get('registration_no'):
            raise serializers.ValidationError({
                'registration_no': 'Registration number is required for import'
            })
        
        return data


class StudentStatisticsSerializer(serializers.Serializer):
    """Serializer for student statistics"""
    total = serializers.IntegerField()
    pending = serializers.IntegerField()
    approved = serializers.IntegerField()
    disbursed = serializers.IntegerField()
    rejected = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    def to_representation(self, instance):
        """Convert statistics to readable format"""
        representation = super().to_representation(instance)
        representation['total_amount_formatted'] = f"KSh {representation['total_amount']:,.2f}"
        return representation


class StudentStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating student status"""
    status = serializers.ChoiceField(choices=Student.STATUS_CHOICES)
    date_processed = serializers.DateTimeField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        # If status is changed to disbursed, date_processed should be set
        if data.get('status') == 'disbursed' and not data.get('date_processed'):
            data['date_processed'] = timezone.now()
        return data