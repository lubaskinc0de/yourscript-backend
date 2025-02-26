import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from zametka.access_service.application.common.interactor import Interactor
from zametka.access_service.application.common.token_sender import TokenSender
from zametka.access_service.application.common.uow import UoW
from zametka.access_service.application.common.user_gateway import UserSaver
from zametka.access_service.application.dto import (
    UserConfirmationTokenDTO,
    UserDTO,
)
from zametka.access_service.domain.common.entities.timed_user_token import (
    TimedTokenMetadata,
)
from zametka.access_service.domain.common.services.password_hasher import PasswordHasher
from zametka.access_service.domain.common.value_objects.timed_token_id import (
    TimedTokenId,
)
from zametka.access_service.domain.entities.config import (
    UserConfirmationTokenConfig,
)
from zametka.access_service.domain.entities.confirmation_token import (
    UserConfirmationToken,
)
from zametka.access_service.domain.entities.user import User
from zametka.access_service.domain.value_objects.expires_in import ExpiresIn
from zametka.access_service.domain.value_objects.user_email import UserEmail
from zametka.access_service.domain.value_objects.user_id import UserId
from zametka.access_service.domain.value_objects.user_raw_password import (
    UserRawPassword,
)


@dataclass(frozen=True)
class CreateUserInputDTO:
    email: str
    password: str


class CreateUser(Interactor[CreateUserInputDTO, UserDTO]):
    def __init__(
        self,
        user_gateway: UserSaver,
        token_sender: TokenSender,
        uow: UoW,
        config: UserConfirmationTokenConfig,
        password_hasher: PasswordHasher,
    ):
        self.uow = uow
        self.token_sender = token_sender
        self.user_gateway = user_gateway
        self.config = config
        self.ph = password_hasher

    async def __call__(self, data: CreateUserInputDTO) -> UserDTO:
        email = UserEmail(data.email)
        raw_password = UserRawPassword(data.password)
        user_id = UserId(value=uuid4())

        user = User.create_with_raw_password(
            user_id,
            email,
            raw_password,
            self.ph,
        )

        user_dto = await self.user_gateway.save(user)
        await self.uow.commit()

        now = datetime.now(tz=UTC)
        expires_in = ExpiresIn(now + self.config.expires_after)
        metadata = TimedTokenMetadata(uid=user.user_id, expires_in=expires_in)

        token_id = TimedTokenId(uuid4())
        token = UserConfirmationToken(metadata, token_id)
        token_dto = UserConfirmationTokenDTO(
            uid=token.uid.to_raw(),
            expires_in=token.expires_in.to_raw(),
            token_id=token_id.to_raw(),
        )

        await self.token_sender.send(token_dto, user)

        logging.info("Uid=%s created.", str(user_id.to_raw()))

        return user_dto
