# students/sms.py
import requests
import logging
import re
import json
from django.conf import settings

logger = logging.getLogger(__name__)

def clean_phone_number(phone_number):
    """
    Clean and format Kenyan phone numbers to 2547XXXXXXXX format
    Blessed Texts accepts: 722XXXXXX, 0722XXXXXX, or 254722XXXXXX
    Returns: (cleaned_number, error_message)
    """
    if not phone_number:
        return None, "Phone number is empty"
    
    # Remove all non-digit characters
    digits = re.sub(r'[^\d]', '', str(phone_number))
    
    # Convert to 2547XXXXXXXX format
    if digits.startswith('2547') and len(digits) == 12:
        return digits, None  # Already correct
    
    elif digits.startswith('07') and len(digits) == 10:
        return '254' + digits[1:], None  # 07XXXXXXXX → 2547XXXXXXXX
    
    elif digits.startswith('7') and len(digits) == 9:
        return '254' + digits, None  # 7XXXXXXXX → 2547XXXXXXXX
    
    elif digits.startswith('+2547') and len(digits) == 13:
        return digits[1:], None  # +2547XXXXXXXX → 2547XXXXXXXX
    
    else:
        return None, f"Invalid phone format. Must be: 7XXXXXXXX, 07XXXXXXXX, or 2547XXXXXXXX"

def send_sms_notification(phone_number, message, student_id=None):
    """
    Send SMS notification using configured provider
    Returns: (success, response_data)
    """
    # Clean and format phone number
    formatted_number, error = clean_phone_number(phone_number)
    
    if error:
        logger.error(f"[SMS ERROR] Phone validation failed: {error}")
        return False, f"Phone validation failed: {error}"
    
    logger.info(f"[SMS PREP] Phone: {formatted_number}, Student ID: {student_id}")
    
    # Get SMS provider from settings
    sms_provider = getattr(settings, 'SMS_PROVIDER', 'log')
    
    if sms_provider == 'blessed_texts':
        return send_via_blessed_texts(formatted_number, message, student_id)
    else:
        # Log mode (for development)
        logger.info(f"[SMS LOG] To: {formatted_number}, Message: {message}")
        return True, "Running in LOG mode"

def send_via_blessed_texts(phone_number, message, student_id=None):
    """
    Send SMS via Blessed Texts API
    API endpoint: https://sms.blessedtexts.com/api/sms/v1/sendsms
    """
    api_key = getattr(settings, 'BLESSED_TEXTS_API_KEY', '')
    sender_id = getattr(settings, 'BLESSED_TEXTS_SENDER_ID', 'XpressKard')
    
    if not api_key:
        return False, "Blessed Texts API key not configured"
    
    # Validate phone format
    if not (phone_number.startswith('2547') and len(phone_number) == 12):
        return False, f"Invalid phone format. Must be 2547XXXXXXXX"
    
    # Truncate message if too long
    if len(message) > 160:
        message = message[:157] + "..."
        logger.warning(f"Message truncated to 160 characters")
    
    # API endpoint
    api_url = "https://sms.blessedtexts.com/api/sms/v1/sendsms"
    
    # Payload according to Blessed Texts documentation
    payload = {
        'api_key': api_key,
        'sender_id': sender_id,
        'message': message,
        'phone': phone_number
    }
    
    try:
        response = requests.post(api_url, json=payload, timeout=30)
        
        if response.status_code == 200:
            try:
                data = response.json()
                
                # Check if response is a list (successful sends return list)
                if isinstance(data, list) and len(data) > 0:
                    if data[0].get('status_code') == '1000':
                        logger.info(f"SMS sent successfully. Message ID: {data[0].get('message_id')}")
                        return True, data
                    else:
                        error_msg = data[0].get('status_desc', 'Unknown error')
                        return False, error_msg
                
                # Check if response is a dict with status_code
                elif isinstance(data, dict) and data.get('status_code') == '1000':
                    logger.info(f"SMS sent successfully")
                    return True, data
                
                else:
                    return False, f"Unexpected response: {data}"
                    
            except json.JSONDecodeError:
                return False, f"Invalid JSON response: {response.text}"
        else:
            return False, f"HTTP {response.status_code}: {response.text}"
            
    except requests.exceptions.Timeout:
        return False, "Request timeout"
    except requests.exceptions.ConnectionError:
        return False, "Connection error"
    except Exception as e:
        return False, f"Error: {str(e)}"

def get_sms_balance():
    """
    Get SMS balance from Blessed Texts API
    API endpoint: https://sms.blessedtexts.com/api/sms/v1/credit-balance
    """
    sms_provider = getattr(settings, 'SMS_PROVIDER', 'log')
    
    if sms_provider != 'blessed_texts':
        return {"balance": 49, "status": "log_mode"}
    
    api_key = getattr(settings, 'BLESSED_TEXTS_API_KEY', '')
    
    if not api_key:
        return {"error": "API key not configured"}
    
    api_url = "https://sms.blessedtexts.com/api/sms/v1/credit-balance"
    payload = {'api_key': api_key}
    
    try:
        response = requests.post(api_url, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status_code') == '1000':
                return {
                    'balance': data.get('balance'),
                    'status': 'success',
                    'status_code': '1000'
                }
            else:
                return {'error': data.get('status_desc', 'Unknown error')}
        else:
            return {'error': f"HTTP {response.status_code}"}
            
    except Exception as e:
        return {'error': str(e)}