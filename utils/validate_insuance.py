import os
import json
import aiohttp
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

async def check_insurance_eligibility(
    first_name: str, 
    last_name: str, 
    insurance_id: str, 
    date_of_birth: str,
    retry_count: int = 0
) -> Dict[str, Any]:
    """
    Make a call to the Stedi API to check insurance eligibility.
    
    Args:
        first_name: Patient's first name
        last_name: Patient's last name
        insurance_id: Patient's insurance ID
        date_of_birth: Patient's date of birth (YYYYMMDD format)
        retry_count: Current retry attempt count
        
    Returns:
        Dictionary containing the API response or error information
    """
    try:
        payload = {
            "controlNumber": "112233445",
            "tradingPartnerServiceId": "60054",  # Note: Changed this to match your curl example
            "provider": {
                "organizationName": "Provider Name",
                "npi": "1999999984"
            },
            "subscriber": {
                "firstName": first_name,
                "lastName": last_name,
                "memberId": insurance_id,
                "dateOfBirth": date_of_birth,
            },
            "encounter": {
                "serviceTypeCodes": ["30"]
            }
        }
        
        api_key = os.getenv("STEDI_API_KEY")
        if not api_key:
            logger.error("Missing STEDI_API_KEY in .env")
            return {
                "success": False,
                "error_type": "configuration_error",
                "message": "System configuration error. Check .env and try again later."
            }
        
        stedi_api_url = 'https://healthcare.us.stedi.com/2024-04-01/change/medicalnetwork/eligibility/v3'

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Key {api_key}"
        }
        
        logger.info(f"Sending request to Stedi API for patient {first_name} {last_name}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(stedi_api_url, json=payload, headers=headers) as response:
                response_text = await response.text()
                
                try:
                    response_data = json.loads(response_text)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {response_text}")
                    return {
                        "success": False,
                        "error_type": "json_error",
                        "status_code": response.status,
                        "message": "Failed to parse API response"
                    }
                
                if response.status != 200:
                    logger.error(f"Stedi API error: Status {response.status}, {response_text}")
                    return {
                        "success": False,
                        "error_type": "api_error",
                        "status_code": response.status,
                        "message": f"API error: {response_data.get('message', response_text)}"
                    }
                
                return {
                    "success": True,
                    "data": response_data
                }
                
    except Exception as e:
        logger.error(f"Error checking eligibility: {str(e)}")
        return {
            "success": False,
            "error_type": "exception",
            "message": str(e)
        }



def validate_insurance_eligibility(response_data, retry_count=0):
    result = {
        "is_valid": True,
        "active_insurance": False,
        "has_office_visit_coverage": False,
        "network_status": "unknown",
        "copay_amount": None,
        "message": "",
        "needs_representative": False,
        "retry_validation": False
    }
    
    # Option 1: Check if response is valid
    if "subscriber" not in response_data or not response_data["subscriber"]:
        result["is_valid"] = False
        if retry_count <= 1:
            result["message"] = "I'm having trouble verifying your insurance."
            result["retry_validation"] = True
        else:
            result["message"] = "I wasn't able to validate your insurance after retrying. I'll connect you to a representative."
            result["needs_representative"] = True
        return result
    
    if "planStatus" not in response_data or not response_data["planStatus"]:
        result["is_valid"] = False
        if retry_count <= 1:
            result["message"] = "I'm having trouble finding your plan information. Let's try again with your insurance details."
            result["retry_validation"] = True
        else:
            result["message"] = "I wasn't able to find your plan information after retrying. I'll connect you to a representative."
            result["needs_representative"] = True
        return result
    
    if "errors" in response_data and response_data["errors"]:
        result["is_valid"] = False
        if retry_count <= 1:
            result["message"] = "There seems to be an issue with the insurance verification. Let's try again with your information."
            result["retry_validation"] = True
        else:
            result["message"] = "I'm still encountering errors verifying your insurance. I'll connect you to a representative."
            result["needs_representative"] = True
        return result
    
    # Option 2: Check if insurance is active
    has_active_coverage = False
    for plan in response_data.get("planStatus", []):
        # Check if service type code "30" (Health Benefit Plan Coverage) exists
        if "30" in plan.get("serviceTypeCodes", []):
            # Check if status is "Active Coverage" or statusCode is "1"
            if plan.get("status") == "Active Coverage" or plan.get("statusCode") == "1":
                has_active_coverage = True
                result["active_insurance"] = True
                break
    
    if not has_active_coverage:
        result["message"] = "Your insurance appears to be inactive. I'll connect you to a representative."
        result["needs_representative"] = True
        return result
    
    # Option 3: Check for office visit copay in benefitsInformation
    office_visit_copay = None
    for benefit in response_data.get("benefitsInformation", []):
        # Look for service type "98" (Professional/Physician Visit - Office)
        if "98" in benefit.get("serviceTypeCodes", []):
            # Check for code "B" (copay)
            if benefit.get("code") == "B":
                office_visit_copay = benefit
                result["has_office_visit_coverage"] = True
                result["copay_amount"] = benefit.get("benefitAmount")
                break
    
    if not result["has_office_visit_coverage"]:
        result["message"] = "I couldn't find your coverage details for office visits. I'll transfer you to a representative."
        result["needs_representative"] = True
        return result
    
    # Option 4: Determine network status
    if office_visit_copay:
        network_indicator = office_visit_copay.get("inPlanNetworkIndicator")
        network_code = office_visit_copay.get("inPlanNetworkIndicatorCode")
        
        if network_code == "Y" or network_indicator == "Yes":
            result["network_status"] = "in-network"
            result["message"] = f"Your copay for in-network office visits is ${result['copay_amount']} dollars."
        elif network_code == "N" or network_indicator == "No":
            result["network_status"] = "out-of-network"
            result["message"] = "You have office visit coverage, but this provider is out-of-network under your plan."
        else:
            result["network_status"] = "unknown"
            result["message"] = "Your insurance doesn't specify if this provider is in-network. I'll connect you to a representative."
            result["needs_representative"] = True
    
    return result
