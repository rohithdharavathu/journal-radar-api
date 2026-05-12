RATES_TO_USD = {
    'USD': 1.0,
    'EUR': 1.08,
    'GBP': 1.27,
    'CHF': 1.13,
    'JPY': 0.0067,
    'AUD': 0.65,
    'CAD': 0.74,
    'CNY': 0.14,
    'INR': 0.012,
    'BRL': 0.20,
    'KRW': 0.00075,
    'SEK': 0.096,
    'NOK': 0.095,
    'DKK': 0.145,
    'SGD': 0.74,
}


def to_usd(amount: float, currency: str) -> float | None:
    """Convert amount in given currency to USD using hardcoded rates."""
    if not amount or not currency:
        return None
    rate = RATES_TO_USD.get(currency.upper())
    if rate is None:
        return None
    return round(amount * rate, 2)
