from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi_another_jwt_auth import AuthJWT

from yourscript.application.auth.email_verification import (
    EmailVerificationInputDTO,
    EmailVerificationOutputDTO,
)
from yourscript.application.auth.get_user import GetUserOutputDTO, GetUserInputDTO

from yourscript.application.auth.sign_in import SignInInputDTO, SignInOutputDTO
from yourscript.application.auth.sign_up import SignUpInputDTO, SignUpOutputDTO
from yourscript.presentation.interactor_factory import InteractorFactory
from yourscript.presentation.schemas.auth import UserLoginSchema, UserRegisterSchema

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
        jwt_auth: AuthJWT = Depends(),
        ioc: InteractorFactory = Depends(),
):
    """Login endpoint"""

    async with ioc.sign_in() as interactor:
        response = await interactor(
            SignInInputDTO(email=auth_data.email, password=auth_data.password)
        )

    subject = response.user_id

    access = jwt_auth.create_access_token(subject=subject)

    jwt_auth.set_access_cookies(access)

    return response


@router.get("/whoami", response_model=GetUserOutputDTO)
async def get_user(
        jwt_auth: AuthJWT = Depends(),
        ioc: InteractorFactory = Depends(),
):
    """Get user endpoint"""

    jwt_auth.jwt_required()

    async with ioc.get_user(jwt=jwt_auth) as interactor:
        response = await interactor(
            GetUserInputDTO()
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
