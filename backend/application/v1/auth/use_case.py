import datetime
import jwt

from typing import Optional

from sqlalchemy.exc import DBAPIError, IntegrityError

from .logic import (
    send_confirm_mail,
    create_verify_email_token,
    check_email_verification_token,
    validate_password,
)

from application.v1.exceptions.auth import JWTCheckError

from core.db import User

from .responses import (
    RegisterSuccessResponse,
    RegisterFailedResponse,
    VerifyEmailSuccessResponse,
    VerifyEmailFailedResponse,
    LoginSuccessResponse,
    LoginFailedResponse,
    RefreshSuccessResponse,
)

from .dto import RegisterInputDTO, VerificationInputDTO, LoginInputDTO

from adapters.repository.auth import AuthRepository

from adapters.repository.uow import UnitOfWork

from fastapi_jwt_auth import AuthJWT
from fastapi_mail import FastMail
from passlib.context import CryptContext
from starlette.background import BackgroundTasks

from core.settings import AuthSettings


async def register_user(
    dto: RegisterInputDTO,
    repository: AuthRepository,
    background_tasks: BackgroundTasks,
    pwd_context: CryptContext,
    mail_context: FastMail,
    auth_settings: AuthSettings,
    uow: UnitOfWork,
):
    """User register process"""

    user_password: str = dto.user_password

    validate_password(user_password)

    dto.user_password = User.hash_password(user_password, pwd_context)
    user_joined_at = datetime.datetime.utcnow()

    try:
        user: User = await repository.create_user(
            email=dto.user_email,
            password=dto.user_password,
            first_name=dto.user_first_name,
            last_name=dto.user_last_name,
            joined_at=user_joined_at,
        )

        await uow.commit()

        secret_key: str = auth_settings.secret_key
        algorithm: str = auth_settings.algorithm

        token: bytes = create_verify_email_token(secret_key, algorithm, user)

        send_confirm_mail(
            mail_context,
            dto.user_email,
            background_tasks,
            str(token),
        )

    except IntegrityError:
        return RegisterFailedResponse(
            details="This user already exists (or something wrong)", code=400,
        )

    except DBAPIError as exc:
        return RegisterFailedResponse(details=str(exc), code=400)
    return RegisterSuccessResponse()


async def user_verify_email(
    dto: VerificationInputDTO,
    repository: AuthRepository,
    auth_settings: AuthSettings,
    uow: UnitOfWork,
):
    auth_settings: AuthSettings  # type:ignore

    secret_key: str = auth_settings.secret_key
    algorithm: str = auth_settings.algorithm

    try:
        payload: dict[str, str | int | bool] = jwt.decode(
            dto.token, secret_key, algorithm
        )
        email: Optional[str] = payload.get("email")  # type:ignore

        user: User = await repository.get_user_by_email(email)

        check_email_verification_token(secret_key, algorithm, user, dto.token)

        await repository.make_user_active(user)

        await uow.commit()

    except JWTCheckError as exc:
        return VerifyEmailFailedResponse(details=str(exc), code=403)

    except jwt.DecodeError:
        return VerifyEmailFailedResponse(details="Error while decoding your token.", code=403)

    except DBAPIError as exc:
        return VerifyEmailFailedResponse(details=str(exc), code=400)

    return VerifyEmailSuccessResponse(email=payload.get("email"))


async def user_login(
    dto: LoginInputDTO,
    repository: AuthRepository,
    Authorize: AuthJWT,
    pwd_context: CryptContext,
):
    """Login user"""

    user: User = await repository.get_user_by_email(dto.user_email)

    if not user:
        return LoginFailedResponse(
            details=f"There is no users with email\n{dto.user_email}", code=400
        )

    if not user.is_active:
        return LoginFailedResponse(
            details="Confirm your email first, or you was banned :)", code=403
        )

    if not user.compare_passwords(dto.user_password, pwd_context):
        return LoginFailedResponse(details="Invalid credentials (check your password)", code=403)

    access_token = Authorize.create_access_token(subject=dto.user_email)
    refresh_token = Authorize.create_refresh_token(subject=dto.user_email)

    Authorize.set_access_cookies(access_token)
    Authorize.set_refresh_cookies(refresh_token)

    return LoginSuccessResponse()


async def token_refresh(Authorize: AuthJWT):
    """Refresh user access token"""

    current_user = Authorize.get_jwt_subject()
    new_access_token = Authorize.create_access_token(subject=current_user)

    Authorize.set_access_cookies(new_access_token)

    return RefreshSuccessResponse()
