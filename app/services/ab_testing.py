import hashlib
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class ABAssignment:
    user_id: int
    bucket: int
    strategy: str


def assign_strategy(user_id: int) -> ABAssignment:
    raw = f"{settings.ab_salt}:{user_id}".encode("utf-8")
    hashed = hashlib.sha256(raw).hexdigest()
    bucket = int(hashed[:8], 16) % 100

    if bucket < 34:
        strategy = "collaborative"
    elif bucket < 67:
        strategy = "content"
    else:
        strategy = "hybrid"
    return ABAssignment(user_id=user_id, bucket=bucket, strategy=strategy)
