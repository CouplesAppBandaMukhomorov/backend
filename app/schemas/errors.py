from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"detail": "You are already in a couple", "code": "already_in_couple"},
                {"detail": "Invalid or expired token", "code": "invalid_token"},
                {"detail": "No Google calendar is linked to this couple", "code": "calendar_not_linked"},
            ]
        }
    )

    detail: str = Field(
        description=(
            "Человекочитаемое пояснение для логов и отладки. Текст технический и на английском, "
            "показывать его пользователю не нужно."
        ),
        examples=["Invalid or expired token"],
    )
    code: str = Field(
        description=(
            "Машиночитаемый код ошибки — по нему нужно ветвить логику на фронте. "
            "Полный список кодов с расшифровкой приведён в описании API, а также в "
            "расширении `x-error-codes` этой схемы."
        ),
        examples=["invalid_token"],
    )


class ValidationErrorItem(BaseModel):
    loc: list[str | int] = Field(
        description="Путь до поля, которое не прошло валидацию.",
        examples=[["body", "start", "date_time"]],
    )
    msg: str = Field(
        description="Описание проблемы.",
        examples=["Input should be a valid datetime"],
    )
    type: str = Field(
        description="Машинный тип ошибки Pydantic.",
        examples=["datetime_parsing"],
    )


class ValidationErrorResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "detail": "Validation error",
                    "code": "validation_error",
                    "errors": [
                        {
                            "loc": ["body", "end"],
                            "msg": "Value error, 'end' must define exactly one of 'date' or 'date_time'",
                            "type": "value_error",
                        }
                    ],
                }
            ]
        }
    )

    detail: str = Field(description="Всегда `Validation error`.", examples=["Validation error"])
    code: str = Field(description="Всегда `validation_error`.", examples=["validation_error"])
    errors: list[ValidationErrorItem] = Field(
        description="Список полей, которые не прошли валидацию."
    )
