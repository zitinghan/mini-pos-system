"""Authoritative integer-sen pricing, independent of HTTP and persistence."""
from dataclasses import dataclass
from collections.abc import Sequence


class PriceValidationError(ValueError):
    """The selected modifiers or monetary inputs are invalid."""


@dataclass(frozen=True)
class SelectionGroup:
    id: int
    name: str
    minimum: int
    maximum: int
    option_prices: dict[int, int]


@dataclass(frozen=True)
class Quote:
    unit_price: int
    line_total: int


def calculate_price(
    base_price: int,
    quantity: int,
    groups: Sequence[SelectionGroup],
    option_ids: Sequence[int],
) -> Quote:
    if type(base_price) is not int or base_price < 0:
        raise PriceValidationError('Invalid base price')
    if type(quantity) is not int or not 1 <= quantity <= 99:
        raise PriceValidationError('Quantity must be between 1 and 99')
    if any(type(identity) is not int for identity in option_ids):
        raise PriceValidationError('Invalid modifier for this item')
    if len(option_ids) != len(set(option_ids)):
        raise PriceValidationError('Duplicate modifier selection')

    prices: dict[int, int] = {}
    for group in groups:
        if not 0 <= group.minimum <= group.maximum:
            raise PriceValidationError('Invalid modifier group configuration')
        if prices.keys() & group.option_prices.keys():
            raise PriceValidationError('Modifier options cannot belong to multiple groups')
        prices.update(group.option_prices)
    if any(type(value) is not int or value < 0 for value in prices.values()):
        raise PriceValidationError('Invalid modifier price')
    if any(identity not in prices for identity in option_ids):
        raise PriceValidationError('Invalid modifier for this item')

    selected = set(option_ids)
    for group in groups:
        count = len(selected & group.option_prices.keys())
        if not group.minimum <= count <= group.maximum:
            raise PriceValidationError(
                f'{group.name}: choose {group.minimum}–{group.maximum} options'
            )
    unit_price = base_price + sum(prices[identity] for identity in option_ids)
    return Quote(unit_price=unit_price, line_total=unit_price * quantity)
