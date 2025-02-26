import argon2
from aiosmtplib import SMTP
from dishka import (
    AnyOf,
    AsyncContainer,
    Provider,
    Scope,
    from_context,
    make_async_container,
    provide,
)
from fastapi import Request
from jinja2 import Environment, PackageLoader, select_autoescape

from zametka.access_service.application.authorize import Authorize
from zametka.access_service.application.common.event import EventEmitter
from zametka.access_service.application.common.id_provider import (
    IdProvider,
)
from zametka.access_service.application.common.token_sender import TokenSender
from zametka.access_service.application.common.uow import UoW
from zametka.access_service.application.common.user_gateway import (
    UserReader,
    UserSaver,
)
from zametka.access_service.application.create_user import CreateUser
from zametka.access_service.application.delete_user import DeleteUser
from zametka.access_service.application.get_user import GetUser
from zametka.access_service.application.verify_email import VerifyEmail
from zametka.access_service.bootstrap.conf import (
    load_all_config,
)
from zametka.access_service.domain.common.services.access_service import AccessService
from zametka.access_service.domain.common.services.password_hasher import PasswordHasher
from zametka.access_service.domain.entities.access_token import AccessToken
from zametka.access_service.domain.entities.config import (
    AccessTokenConfig,
    UserConfirmationTokenConfig,
)
from zametka.access_service.domain.services.token_access_service import (
    TokenAccessService,
)
from zametka.access_service.infrastructure.auth.password_hasher import (
    ArgonPasswordHasher,
)
from zametka.access_service.infrastructure.email.aio_email_client import (
    AioSMTPEmailClient,
)
from zametka.access_service.infrastructure.email.config import (
    ConfirmationEmailConfig,
    SMTPConfig,
)
from zametka.access_service.infrastructure.email.email_token_sender import (
    EmailTokenSender,
)
from zametka.access_service.infrastructure.event_bus.event_emitter import (
    EventEmitterImpl,
)
from zametka.access_service.infrastructure.gateway.user import UserGatewayImpl
from zametka.access_service.infrastructure.id_provider import (
    TokenIdProvider,
)
from zametka.access_service.infrastructure.jwt.access_token_processor import (
    AccessTokenProcessor,
)
from zametka.access_service.infrastructure.jwt.config import JWTConfig
from zametka.access_service.infrastructure.jwt.confirmation_token_processor import (
    ConfirmationTokenProcessor,
)
from zametka.access_service.infrastructure.jwt.jwt_processor import (
    JWTProcessor,
    PyJWTProcessor,
)
from zametka.access_service.infrastructure.message_broker.config import (
    AMQPConfig,
)
from zametka.access_service.infrastructure.persistence.config import DBConfig
from zametka.access_service.infrastructure.persistence.provider import (
    get_async_session,
    get_async_sessionmaker,
    get_engine,
)
from zametka.access_service.infrastructure.persistence.uow import SAUnitOfWork
from zametka.access_service.presentation.error_message import ErrorMessage
from zametka.access_service.presentation.http.auth.config import TokenAuthConfig
from zametka.access_service.presentation.http.auth.token_auth import TokenAuth


def gateway_provider() -> Provider:
    provider = Provider()

    provider.provide(
        UserGatewayImpl,
        scope=Scope.REQUEST,
        provides=AnyOf[UserReader, UserSaver],
    )
    provider.provide(SAUnitOfWork, scope=Scope.REQUEST, provides=UoW)

    return provider


def db_provider() -> Provider:
    provider = Provider()

    provider.provide(get_engine, scope=Scope.APP)
    provider.provide(get_async_sessionmaker, scope=Scope.APP)
    provider.provide(get_async_session, scope=Scope.REQUEST)

    return provider


def interactor_provider() -> Provider:
    provider = Provider()

    provider.provide(CreateUser, scope=Scope.REQUEST)
    provider.provide(DeleteUser, scope=Scope.REQUEST)
    provider.provide(GetUser, scope=Scope.REQUEST)
    provider.provide(Authorize, scope=Scope.REQUEST)
    provider.provide(VerifyEmail, scope=Scope.REQUEST)

    return provider


def infrastructure_provider() -> Provider:
    provider = Provider()

    provider.provide(EventEmitterImpl, scope=Scope.REQUEST, provides=EventEmitter)
    provider.provide(PyJWTProcessor, scope=Scope.APP, provides=JWTProcessor)
    provider.provide(ConfirmationTokenProcessor, scope=Scope.APP)
    provider.provide(AccessTokenProcessor, scope=Scope.APP)

    return provider


def presentation_provider() -> Provider:
    provider = Provider()

    provider.provide(ErrorMessage, scope=Scope.APP)

    return provider


def service_provider() -> Provider:
    provider = Provider()

    provider.provide(TokenAccessService, scope=Scope.REQUEST, provides=AccessService)
    provider.provide(
        lambda: ArgonPasswordHasher(argon2.PasswordHasher()),
        scope=Scope.APP,
        provides=PasswordHasher,
    )

    return provider


def config_provider() -> Provider:
    provider = Provider()
    config = load_all_config()

    provider.provide(lambda: config.db, scope=Scope.APP, provides=DBConfig)
    provider.provide(lambda: config.smtp, scope=Scope.APP, provides=SMTPConfig)
    provider.provide(lambda: config.amqp, scope=Scope.APP, provides=AMQPConfig)
    provider.provide(
        lambda: config.email,
        scope=Scope.APP,
        provides=ConfirmationEmailConfig,
    )
    provider.provide(lambda: config.jwt, scope=Scope.APP, provides=JWTConfig)
    provider.provide(
        lambda: config.token_auth,
        scope=Scope.APP,
        provides=TokenAuthConfig,
    )
    provider.provide(
        lambda: config.access_token,
        scope=Scope.APP,
        provides=AccessTokenConfig,
    )
    provider.provide(
        lambda: config.confirmation_token,
        scope=Scope.APP,
        provides=UserConfirmationTokenConfig,
    )

    return provider


class HTTPProvider(Provider):
    request = from_context(provides=Request, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST)
    def get_token_auth(
        self,
        request: Request,
        token_processor: AccessTokenProcessor,
        token_auth_config: TokenAuthConfig,
    ) -> TokenAuth:
        token_auth = TokenAuth(
            req=request,
            config=token_auth_config,
            token_processor=token_processor,
        )

        return token_auth

    @provide(scope=Scope.REQUEST)
    def get_access_token(self, token_auth: TokenAuth) -> AccessToken:
        token = token_auth.get_access_token()
        return token

    @provide(scope=Scope.REQUEST)
    def get_idp(
        self,
        token_auth: TokenAuth,
        access_service: AccessService,
        user_gateway: UserReader,
    ) -> IdProvider:
        token = token_auth.get_access_token()
        id_provider = TokenIdProvider(
            token=token,
            access_service=access_service,
            user_gateway=user_gateway,
        )

        return id_provider

    @provide(scope=Scope.APP)
    def get_token_sender(
        self,
        config: SMTPConfig,
        email_config: ConfirmationEmailConfig,
        token_processor: ConfirmationTokenProcessor,
    ) -> TokenSender:
        jinja_env: Environment = Environment(
            loader=PackageLoader(email_config.template_path),
            autoescape=select_autoescape(),
        )
        email_client = AioSMTPEmailClient(
            SMTP(
                hostname=config.host,
                port=config.port,
                username=config.user,
                password=config.password,
                use_tls=config.use_tls,
            ),
        )
        token_sender = EmailTokenSender(
            email_client,
            jinja_env,
            config=email_config,
            token_processor=token_processor,
        )

        return token_sender


def setup_providers() -> list[Provider]:
    providers = [
        gateway_provider(),
        db_provider(),
        interactor_provider(),
        infrastructure_provider(),
        config_provider(),
        service_provider(),
        presentation_provider(),
    ]
    return providers


def setup_di() -> AsyncContainer:
    providers = setup_providers()
    container = make_async_container(*providers)

    return container


def setup_http_di() -> AsyncContainer:
    providers = setup_providers()
    providers += [HTTPProvider()]

    container = make_async_container(*providers)
    return container
