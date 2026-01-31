import pytest
from uuid import uuid4
from pydantic import ValidationError

from app.models.company import CompanyCreate


def test_company_ticker_auto_uppercase():
    c = CompanyCreate(
        name="Test",
        ticker="abc",
        industry_id=uuid4(),
        position_factor=0.0,
    )
    assert c.ticker == "ABC"


def test_company_name_required():
    with pytest.raises(ValidationError):
        CompanyCreate(
            name="",
            ticker="ABC",
            industry_id=uuid4(),
            position_factor=0.0,
        )


def test_company_ticker_max_len():
    with pytest.raises(ValidationError):
        CompanyCreate(
            name="Test",
            ticker="ABCDEFGHIJK",  # 11
            industry_id=uuid4(),
            position_factor=0.0,
        )


def test_company_position_factor_range():
    with pytest.raises(ValidationError):
        CompanyCreate(
            name="Test",
            ticker="ABC",
            industry_id=uuid4(),
            position_factor=2.0,
        )
