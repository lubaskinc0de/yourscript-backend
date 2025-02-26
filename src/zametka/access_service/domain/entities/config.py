from dataclasses import dataclass
from datetime import timedelta


@dataclass
class AccessTokenConfig:
    expires_after: timedelta


@dataclass
class UserConfirmationTokenConfig:
    expires_after: timedelta
