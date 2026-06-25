import re
from datetime import datetime
from typing import Literal, Annotated, Union
from pydantic import BaseModel, Field, field_validator


def _normaliser_dato(v) -> str:
    if isinstance(v, datetime):
        return v.strftime("%d-%m-%Y")
    s = str(v)
    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%d-%m-%Y")
        except ValueError:
            continue
    raise ValueError(f"Ukendt datoformat: {v}")


class Borger(BaseModel):
    cpr: str

    @field_validator("cpr")
    @classmethod
    def validate_cpr(cls, v: str) -> str:
        if not v:
            raise ValueError("CPR må ikke være tomt")
        digits = v.replace("-", "")
        if not re.fullmatch(r"\d{10}", digits):
            raise ValueError("CPR skal være 10 cifre (DDMMYYXXXX)")
        return v


class TiføjOrganisationsOpgave(Borger):
    type: Literal["tilføj"] = "tilføj"
    organisation: str

class FjernOrganisationsOpgave(Borger):
    type: Literal["fjern"] = "fjern"
    organisation: str
    ophørsdato: str

    @field_validator("ophørsdato", mode="before")
    @classmethod
    def normaliser_ophørsdato(cls, v) -> str:
        return _normaliser_dato(v)

class LeverandørsSkiftOpgave(Borger):
    type: Literal["leverandørskift"] = "leverandørskift"
    organisation_fra: str
    organisation_til: str
    ikrafttrædelsesdato: str

    @field_validator("ikrafttrædelsesdato", mode="before")
    @classmethod
    def normaliser_ikrafttrædelsesdato(cls, v) -> str:
        return _normaliser_dato(v)

class OrganisationsSkiftOpgave(Borger):
    type: Literal["organisationsskift"] = "organisationsskift"
    organisation_fra: str
    organisation_til: str