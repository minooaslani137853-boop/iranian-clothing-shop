"""Gateway boundary. No card fields or card data belong in this application."""
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol


class PaymentError(Exception):
    pass


@dataclass(frozen=True)
class PaymentRequest:
    amount_toman: int
    idempotency_key: str


@dataclass(frozen=True)
class PaymentReceipt:
    provider: str
    reference: str
    amount_toman: int


class PaymentGateway(Protocol):
    def pay(self, request: PaymentRequest) -> PaymentReceipt:
        """Return a verified receipt or raise PaymentError. Must be idempotent."""
        ...


class MockGateway:
    def pay(self, request: PaymentRequest) -> PaymentReceipt:
        if request.amount_toman < 0:
            raise PaymentError('Invalid amount')
        reference = 'MOCK-' + sha256(request.idempotency_key.encode()).hexdigest()[:24]
        return PaymentReceipt('mock', reference, request.amount_toman)
