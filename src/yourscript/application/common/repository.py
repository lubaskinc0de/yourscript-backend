from abc import ABC, abstractmethod
from typing import Optional

from yourscript.domain.entities.refresh_token import RefreshToken
from yourscript.domain.entities.script import Script
from yourscript.domain.entities.user import DBUser, User
from yourscript.domain.value_objects.script_id import ScriptId
from yourscript.domain.value_objects.user_id import UserId


class AbstractRepository(ABC):
    """Abstract implementation of SA repository"""

    def __init__(self, session) -> None:
        self.session = session


class AuthRepository(AbstractRepository):
    """User repository interface"""

    @abstractmethod
    async def create(self, user: User) -> User:
        """Create user"""

    @abstractmethod
    async def get(self, user_id: UserId) -> DBUser:
        """Get user by id"""

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[DBUser]:
        """Get user by email"""

    @abstractmethod
    async def set_active(self, user_id: UserId) -> None:
        """Set user active"""


class ScriptRepository(AbstractRepository):
    """Script repository interface"""

    @abstractmethod
    async def create(self, script: Script) -> Script:
        """Create script"""

    @abstractmethod
    async def get(self, script_id: ScriptId) -> Optional[Script]:
        """Get script by id"""

    @abstractmethod
    async def update(self, script_id: ScriptId, script: Script) -> Script:
        """Update script"""

    @abstractmethod
    async def delete(self, script_id: ScriptId) -> None:
        """Delete script"""


class RefreshTokenRepository(AbstractRepository):
    """Refresh token repository interface"""

    @abstractmethod
    async def create(self, refresh_token: RefreshToken) -> RefreshToken:
        """Create refresh token instance"""

    @abstractmethod
    async def delete(self, user_id: UserId) -> None:
        """Delete user tokens"""

    @abstractmethod
    async def exists(self, token: RefreshToken) -> bool:
        """Is token exists"""
