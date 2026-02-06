# streamlit_ui/utils/api_client.py
import requests
from typing import Dict, Any, Optional, List
import streamlit as st
from datetime import datetime

class APIClient:
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or st.session_state.get("api_base", "http://127.0.0.1:8000/api/v1")
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            st.error(f"API Error ({response.status_code}): {response.text}")
            return {}
        except requests.exceptions.RequestException as e:
            st.error(f"Connection Error: {str(e)}")
            return {}
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health status"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return self._handle_response(response)
        except:
            return {"status": "offline"}
    
    def get_companies(self, page: int = 1, page_size: int = 100, industry_id: str = None) -> Dict[str, Any]:
        """Get all companies with pagination"""
        params = {"page": page, "page_size": page_size}
        if industry_id:
            params["industry_id"] = industry_id
        
        response = requests.get(f"{self.base_url}/companies", params=params, timeout=10)
        return self._handle_response(response)
    
    def get_company(self, company_id: str) -> Dict[str, Any]:
        """Get a specific company by ID"""
        response = requests.get(f"{self.base_url}/companies/{company_id}", timeout=10)
        return self._handle_response(response)
    
    def create_company(self, name: str, ticker: str, industry_id: str, position_factor: float = 0.0) -> Dict[str, Any]:
        """Create a new company"""
        data = {
            "name": name,
            "ticker": ticker,
            "industry_id": industry_id,
            "position_factor": position_factor
        }
        response = requests.post(f"{self.base_url}/companies", json=data, timeout=10)
        return self._handle_response(response)
    
    def get_industries(self, page: int = 1, page_size: int = 100) -> Dict[str, Any]:
        """Get all industries"""
        params = {"page": page, "page_size": page_size}
        response = requests.get(f"{self.base_url}/industries", params=params, timeout=10)
        return self._handle_response(response)
    
    def get_company_signals(self, company_id: str, category: str = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Get signals for a specific company"""
        params = {"page": page, "page_size": page_size}
        if category:
            params["category"] = category
        
        response = requests.get(
            f"{self.base_url}/signals/companies/{company_id}",
            params=params,
            timeout=10
        )
        return self._handle_response(response)
    
    def get_signal_summary(self, company_id: str) -> Dict[str, Any]:
        """Get aggregated signal summary for a company"""
        response = requests.get(
            f"{self.base_url}/signals/companies/{company_id}/summary",
            timeout=10
        )
        return self._handle_response(response)
    
    def collect_job_signals(
        self, 
        company_id: str, 
        company_name: str, 
        max_results: int = 20
    ) -> Dict[str, Any]:
        """Trigger job signal collection for a company"""
        params = {
            "company_id": company_id,
            "company_name": company_name,
            "max_results": max_results
        }
        response = requests.post(
            f"{self.base_url}/signals/collect-job-signals",
            params=params,
            timeout=300  
        )
        return self._handle_response(response)
    
    def refresh_signal_summary(self, company_id: str) -> Dict[str, Any]:
        """Recalculate signal summary for a company"""
        response = requests.post(
            f"{self.base_url}/signals/companies/{company_id}/summary/refresh",
            timeout=10
        )
        return self._handle_response(response)
    
    def get_assessments(
        self, 
        company_id: str = None,
        page: int = 1, 
        page_size: int = 20,
        status: str = None,
        assessment_type: str = None
    ) -> Dict[str, Any]:
        """Get assessments with filters"""
        params = {"page": page, "page_size": page_size}
        if company_id:
            params["company_id"] = company_id
        if status:
            params["status"] = status
        if assessment_type:
            params["assessment_type"] = assessment_type
        
        response = requests.get(f"{self.base_url}/assessments", params=params, timeout=10)
        return self._handle_response(response)
    
    def get_assessment(self, assessment_id: str) -> Dict[str, Any]:
        """Get assessment with dimension scores"""
        response = requests.get(f"{self.base_url}/assessments/{assessment_id}", timeout=10)
        return self._handle_response(response)
    
    def get_company_by_ticker(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Find company by ticker symbol"""
        companies_data = self.get_companies(page_size=100)
        if companies_data and "items" in companies_data:
            for company in companies_data["items"]:
                if company.get("ticker", "").upper() == ticker.upper():
                    return company
        return None
    
    def get_or_create_company(
        self, 
        ticker: str, 
        name: str, 
        sector: str = "Manufacturing"
    ) -> Optional[str]:
        """Get existing company or create new one, returns company_id"""
        # Try to find existing company
        existing = self.get_company_by_ticker(ticker)
        if existing:
            return existing.get("id")
        
        # Get industry ID for sector
        industries = self.get_industries()
        if not industries or "items" not in industries:
            st.error(f"Failed to get industries")
            return None
        
        industry_id = None
        for industry in industries["items"]:
            if industry.get("sector", "").lower() == sector.lower():
                industry_id = industry.get("id")
                break
        
        if not industry_id:
            st.error(f"No industry found for sector: {sector}")
            return None
        
        # Create new company
        result = self.create_company(
            name=name,
            ticker=ticker,
            industry_id=industry_id,
            position_factor=0.0
        )
        
        if result and "id" in result:
            return result["id"]
        
        return None
    

    def collect_job_signals(
        self, 
        company_id: str, 
        company_name: str, 
        max_results: int = 20
    ) -> Dict[str, Any]:
        """Trigger job signal collection for a company"""
        params = {
            "company_id": company_id,
            "company_name": company_name,
            "max_results": max_results
        }
        response = requests.post(
            f"{self.base_url}/signals/collect-job-signals",
            params=params,
            timeout=300  # 5 minutes - job scraping can be slow
        )
        return self._handle_response(response)
    
    def collect_tech_signals(
        self,
        company_id: str,
        company_name: str,
        ticker: str
    ) -> Dict[str, Any]:
        """Trigger tech stack signal collection"""
        params = {
            "company_id": company_id,
            "company_name": company_name,
            "ticker": ticker
        }
        response = requests.post(
            f"{self.base_url}/signals/collect-tech-signals",
            params=params,
            timeout=120  # 2 minutes
        )
        return self._handle_response(response)
    
    def collect_patent_signals(
        self,
        company_id: str,
        assignee: str,
        years: int = 5
    ) -> Dict[str, Any]:
        """Trigger patent signal collection (queued as background task)"""
        params = {
            "company_id": company_id,
            "assignee": assignee,
            "years": years
        }
        response = requests.post(
            f"{self.base_url}/signals/collect-patent-signals",
            params=params,
            timeout=60  # Quick response (queued)
        )
        return self._handle_response(response)
    
    def collect_leadership_signals(
        self,
        company_id: str,
        ticker: str,
        company_name: str
    ) -> Dict[str, Any]:
        """Trigger leadership signal collection"""
        params = {
            "company_id": company_id,
            "ticker": ticker,
            "company_name": company_name
        }
        response = requests.post(
            f"{self.base_url}/signals/collect-leadership-signals",
            params=params,
            timeout=120  # 2 minutes
        )
        return self._handle_response(response)