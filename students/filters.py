# students/filters.py
import django_filters
from .models import Student

class StudentFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    registration_no = django_filters.CharFilter(lookup_expr='icontains')
    institution = django_filters.CharFilter(lookup_expr='icontains')
    ward = django_filters.ChoiceFilter(choices=Student.WARD_CHOICES)
    education_level = django_filters.ChoiceFilter(choices=Student.EDUCATION_LEVEL_CHOICES)
    status = django_filters.ChoiceFilter(choices=Student.STATUS_CHOICES)
    sms_status = django_filters.ChoiceFilter(choices=Student.SMS_STATUS_CHOICES)
    year = django_filters.ChoiceFilter(choices=Student.YEAR_CHOICES)
    
    min_amount = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    max_amount = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    
    date_applied_after = django_filters.DateFilter(field_name='date_applied', lookup_expr='gte')
    date_applied_before = django_filters.DateFilter(field_name='date_applied', lookup_expr='lte')
    
    class Meta:
        model = Student
        fields = [
            'name', 'registration_no', 'institution', 'ward',
            'education_level', 'status', 'sms_status', 'year',
            'min_amount', 'max_amount', 'date_applied_after', 'date_applied_before'
        ]