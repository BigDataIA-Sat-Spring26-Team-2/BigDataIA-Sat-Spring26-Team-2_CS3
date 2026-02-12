from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import List, Union


def to_decimal(value: Union[float, int, str], places: int = 4) -> Decimal:
    
    try:
        dec_value = Decimal(str(value))
        quantizer = Decimal(10) ** -places
        return dec_value.quantize(quantizer, rounding=ROUND_HALF_UP)
    
    except (ValueError, InvalidOperation) as e:
        raise InvalidOperation(f"Cannot convert {value} to Decimal: {e}")


def clamp(
    value: Decimal,
    min_val: Decimal = Decimal(0),
    max_val: Decimal = Decimal(100)
) -> Decimal:
    return max(min_val, min(max_val, value))


def weighted_mean(values: List[Decimal], weights: List[Decimal]) -> Decimal:
    """    
    Formula:
        weighted_mean = Σ(value_i × weight_i) / Σ(weight_i)
    """
    if len(values) != len(weights):
        raise ValueError(
            f"values and weights must have same length "
            f"(got {len(values)} values, {len(weights)} weights)"
        )
    
    if not values:
        return Decimal("0")
    
    weighted_sum = sum(v * w for v, w in zip(values, weights))

    total_weight = sum(weights)
    
    if total_weight == 0:
        raise ZeroDivisionError("Sum of weights cannot be zero")
    
    mean = weighted_sum / total_weight
    
    return mean.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def weighted_std_dev(
    values: List[Decimal],
    weights: List[Decimal],
    mean: Decimal
) -> Decimal:
    """
    Formula:
        σ = sqrt( Σ(weight_i × (value_i - mean)²) / Σ(weight_i) )
    """
    if len(values) != len(weights):
        raise ValueError(
            f"values and weights must have same length "
            f"(got {len(values)} values, {len(weights)} weights)"
        )
    
    if not values:
        return Decimal("0")
    
    total_weight = sum(weights)
    
    if total_weight == 0:
        raise ZeroDivisionError("Sum of weights cannot be zero")
    
    variance_sum = sum(
        w * (v - mean) ** 2 
        for v, w in zip(values, weights)
    )
    
    variance = variance_sum / total_weight
    
    std_dev = Decimal(str(float(variance) ** 0.5))
    
    return std_dev.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def coefficient_of_variation(std_dev: Decimal, mean: Decimal) -> Decimal:
    """
    Formula:
        CV = σ / μ  (standard deviation / mean)
    """

    if mean == 0 or abs(mean) < Decimal("0.01"):
        return Decimal("0")
    
    cv = std_dev / mean
    
    return cv.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

