
from abc import ABC, abstractmethod
from typing import List
import structlog

from app.models.leadership import ExecutiveProfile

logger = structlog.get_logger(__name__)


class BaseLeadershipCollector(ABC):
    """Base class for leadership data collectors"""
    
    def __init__(self, source_name: str, weight: float):
        self.source_name = source_name
        self.weight = weight
        self.logger = logger.bind(collector=source_name)
    
    @abstractmethod
    async def collect_leadership_data(
        self,
        company_name: str,
        ticker: str
    ) -> List[ExecutiveProfile]:
        """
        Collect executive profiles from this source.
        
        Args:
            company_name: Full company name (e.g., "JPMorgan Chase")
            ticker: Stock ticker (e.g., "JPM")
            
        Returns:
            List of ExecutiveProfile objects
        """
        pass
    
    @abstractmethod
    async def close(self):
        """Cleanup resources (HTTP clients, etc.)"""
        pass