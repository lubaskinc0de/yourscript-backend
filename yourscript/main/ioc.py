from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi_mail import FastMail
from jinja2 import Environment
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from starlette.background import BackgroundTasks

from application.auth.email_verification import EmailVerification
from application.auth.refresh_token import RefreshTokenInteractor
from application.auth.sign_in import SignIn
from domain.services.refresh_token_service import RefreshTokenService
from domain.services.script_service import ScriptService
from domain.services.user_service import UserService

from application.common.adapters import JWT
from application.script.script_interactor import ScriptInteractor

from application.auth.sign_up import SignUp

from infrastructure.adapters.auth.jwtops import JWTOperationsImpl
from infrastructure.adapters.auth.mailer import MailTokenSenderImpl
from infrastructure.adapters.auth.password_hasher import PasswordHasherImpl
from infrastructure.config_loader import AuthSettings

from presentation.interactor_factory import (
    InteractorFactory,
    InteractorPicker,
    GInputDTO,
    GOutputDTO,
    InteractorCallable,
)

from infrastructure.db.provider import (
    get_script_repository,
    get_auth_repository,
    get_uow,
    get_token_repository,
)


class IoC(InteractorFactory):
    _session_factory: async_sessionmaker
    _script_service: ScriptService

    def __init__(
        self,
        session_factory: async_sessionmaker,
        auth_settings: AuthSettings,
        mailer: FastMail,
        jinja_env: Environment,
        token_link: str,
    ):
        self._session_factory = session_factory

        self._script_service = ScriptService()
        self._user_service = UserService()
        self._token_service = RefreshTokenService()
        self._password_hasher = PasswordHasherImpl()
        self._jwt_ops = JWTOperationsImpl()

        self._auth_settings: AuthSettings = auth_settings

        self._secret_key = self._auth_settings.secret_key
        self._algorithm: str = self._auth_settings.algorithm

        self._mailer = mailer
        self._jinja_env = jinja_env

        self._token_link = token_link

    def _construct_script_interactor(
        self, session: AsyncSession, jwt: JWT
    ) -> ScriptInteractor:
        script_repository = get_script_repository(session)
        auth_repository = get_auth_repository(session)
        uow = get_uow(session)
        service = self._script_service

        return ScriptInteractor(
            script_repository=script_repository,
            auth_repository=auth_repository,
            uow=uow,
            service=service,
            jwt=jwt,
        )

    @asynccontextmanager
    async def pick_script_interactor(
        self, jwt: JWT, picker: InteractorPicker[GInputDTO, GOutputDTO]
    ) -> AsyncIterator[InteractorCallable[GInputDTO, GOutputDTO]]:
        async with self._session_factory() as session:
            interactor = self._construct_script_interactor(session, jwt)
            yield picker(interactor)

    @asynccontextmanager
    async def sign_up(self, background_tasks: BackgroundTasks) -> AsyncIterator[SignUp]:
        async with self._session_factory() as session:
            interactor = SignUp(
                repository=get_auth_repository(session),
                pwd_context=self._password_hasher,
                token_sender=MailTokenSenderImpl(
                    jinja=self._jinja_env,
                    mail=self._mailer,
                    background_tasks=background_tasks,
                    token_link=self._token_link,
                ),
                secret_key=self._secret_key,
                algorithm=self._algorithm,
                jwt_ops=self._jwt_ops,
                service=self._user_service,
                uow=get_uow(session),
            )

            yield interactor

    @asynccontextmanager
    async def sign_in(self, jwt: JWT) -> AsyncIterator[SignIn]:
        async with self._session_factory() as session:
            interactor = SignIn(
                repository=get_auth_repository(session),
                pwd_context=self._password_hasher,
                uow=get_uow(session),
                jwt=jwt,
                token_repository=get_token_repository(session),
                token_service=self._token_service,
            )

            yield interactor

    @asynccontextmanager
    async def refresh_token(self, jwt: JWT) -> AsyncIterator[RefreshTokenInteractor]:
        async with self._session_factory() as session:
            interactor = RefreshTokenInteractor(
                uow=get_uow(session),
                jwt=jwt,
                token_repository=get_token_repository(session),
                auth_repository=get_auth_repository(session),
            )

            yield interactor

    @asynccontextmanager
    async def email_verification(self) -> AsyncIterator[EmailVerification]:
        async with self._session_factory() as session:
            interactor = EmailVerification(
                repository=get_auth_repository(session),
                uow=get_uow(session),
                jwt_ops=self._jwt_ops,
                secret_key=self._secret_key,
                algorithm=self._algorithm,
            )

            yield interactor
