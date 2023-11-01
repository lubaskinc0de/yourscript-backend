from datetime import datetime, timedelta

from fastapi_mail import FastMail, MessageSchema, MessageType
from jinja2 import Environment

from starlette.background import BackgroundTasks

from application.common.adapters import MailTokenSender, JWTOperations

from domain.entities.user import User
from domain.value_objects.token import Token


# def _get_token_link(token: str) -> str:
#     # TODO: make it better
#     return "/v1/auth/verify/{}".format(token)  # how make it better? temp solution


def get_message_schema(subject: str, to_email: str, html: str) -> MessageSchema:
    message_schema = MessageSchema(
        subject=subject,
        recipients=[to_email],
        body=html,
        subtype=MessageType.html,
    )

    return message_schema


class MailTokenSenderImpl(MailTokenSender):
    """MailTokenSenderInterface implementation"""

    mail: FastMail
    background_tasks: BackgroundTasks
    token_link: str

    def __init__(
        self,
        mail: FastMail,
        background_tasks: BackgroundTasks,
        jinja: Environment,
        token_link: str,
    ) -> None:
        self._mail = mail
        self._background_tasks = background_tasks
        self._jinja = jinja
        self._token_link = token_link

    def _render_html(self, token: str) -> str:
        template = self._jinja.get_template("confirmation-mail.html")

        rendered: str = template.render(token_link=self._token_link)

        return rendered

    def send(self, token: str, subject: str, to_email: str) -> None:
        """Send email token to the user"""

        html = self._render_html(token)

        self._background_tasks.add_task(
            self._mail.send_message,
            get_message_schema(subject=subject, html=html, to_email=to_email),
            template_name="confirmation-mail",
        )

    def create(
        self, secret_key: str, algorithm: str, user: User, jwt: JWTOperations
    ) -> Token:
        exp: datetime = (datetime.now() + timedelta(minutes=5)).utcnow()

        payload = {
            "user_id": user.user_id,
            "exp": exp,
            "user_is_active": user.is_active,
        }

        token: str = jwt.encode(payload, secret_key, algorithm)

        return Token(token)
