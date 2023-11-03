from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi_another_jwt_auth import AuthJWT

from application.auth.sign_up import SignUpInputDTO, SignUpOutputDTO
from application.auth.sign_in import SignInInputDTO, SignInOutputDTO

from application.auth.email_verification import (
    EmailVerificationInputDTO,
    EmailVerificationOutputDTO,
)
from application.auth.refresh_token import RefreshTokenInputDTO, RefreshTokenOutputDTO

from domain.entities.refresh_token import RefreshToken
from domain.value_objects.user_id import UserId

from presentation.interactor_factory import InteractorFactory
from presentation.schemas.auth import (
    UserRegisterSchema,
    UserLoginSchema,
)

router = APIRouter(
    prefix="/v1/auth",
    tags=["auth"],
    responses={404: {"description": "Not found"}},
)


@router.post("/sign-up", response_model=SignUpOutputDTO)
async def sign_up(
        user_data: UserRegisterSchema,
        background_tasks: BackgroundTasks,
        ioc: InteractorFactory = Depends(),
):
    """Register endpoint"""

    async with ioc.sign_up(background_tasks=background_tasks) as interactor:
        response = await interactor(
            SignUpInputDTO(
                user_email=user_data.email,
                user_password=user_data.password,
                user_first_name=user_data.first_name,
                user_last_name=user_data.last_name,
            )
        )

        return response


@router.post("/sign-in", response_model=SignInOutputDTO)
async def sign_in(
        auth_data: UserLoginSchema,
        jwt: AuthJWT = Depends(),
        ioc: InteractorFactory = Depends(),
):
    """Login endpoint"""

    async with ioc.sign_in(jwt) as interactor:
        response = await interactor(
            SignInInputDTO(email=auth_data.email, password=auth_data.password)
        )

        return response


@router.get("/verify/{token}", response_model=EmailVerificationOutputDTO)
async def email_verification(token: str, ioc: InteractorFactory = Depends()):
    """Email verification endpoint"""

    async with ioc.email_verification() as interactor:
        response = await interactor(
            EmailVerificationInputDTO(
                token=token,
            )
        )

        return response


@router.post("/refresh", response_model=RefreshTokenOutputDTO)
async def refresh_token(
        jwt: AuthJWT = Depends(),
        ioc: InteractorFactory = Depends(),
):
    """Refresh access token endpoint"""

    jwt.jwt_refresh_token_required()

    user_id: UserId = UserId(jwt.get_jwt_subject())

    async with ioc.refresh_token(jwt) as interactor:
        response = await interactor(
            RefreshTokenInputDTO(
                user_id=user_id,
                refresh=RefreshToken(token=jwt._token, user_id=user_id),
            )
        )

        return response
