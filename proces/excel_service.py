from typing import Union
from pathlib import Path
import openpyxl
from proces.models import (
    TiføjOrganisationsOpgave,
    FjernOrganisationsOpgave,
    LeverandørsSkiftOpgave,
    OrganisationsSkiftOpgave,
)

from typing import Union
from pathlib import Path
import openpyxl
from proces.models import (
    TiføjOrganisationsOpgave,
    FjernOrganisationsOpgave,
    LeverandørsSkiftOpgave,
    OrganisationsSkiftOpgave,
)

Opgave = Union[TiføjOrganisationsOpgave, FjernOrganisationsOpgave, LeverandørsSkiftOpgave, OrganisationsSkiftOpgave]


def afkode_excel(excel_sti: str | Path) -> tuple[list[TiføjOrganisationsOpgave], list[FjernOrganisationsOpgave], list[LeverandørsSkiftOpgave], list[OrganisationsSkiftOpgave]]:
    wb = openpyxl.load_workbook(excel_sti)

    tilføj = []
    for row in wb["Tilføj organisation"].iter_rows(min_row=2, values_only=True):
        cpr, organisation, *_ = row
        if cpr:
            tilføj.append(TiføjOrganisationsOpgave(cpr=str(cpr), organisation=str(organisation)))

    fjern = []
    for row in wb["Fjern organisation"].iter_rows(min_row=2, values_only=True):
        cpr, organisation, ophørsdato, *_ = row
        if cpr:
            fjern.append(FjernOrganisationsOpgave(cpr=str(cpr), organisation=str(organisation), ophørsdato=str(ophørsdato)))

    leverandørskift = []
    for row in wb["Leverandørskifte indsatser"].iter_rows(min_row=2, values_only=True):
        cpr, organisation_fra, organisation_til, ikrafttrædelsesdato, *_ = row
        if cpr:
            leverandørskift.append(LeverandørsSkiftOpgave(cpr=str(cpr), organisation_fra=str(organisation_fra), organisation_til=str(organisation_til), ikrafttrædelsesdato=str(ikrafttrædelsesdato)))

    organisationsskift = []
    for row in wb["Opgave organisationsskifte"].iter_rows(min_row=2, values_only=True):
        cpr, organisation_fra, organisation_til, *_ = row
        if cpr:
            organisationsskift.append(OrganisationsSkiftOpgave(cpr=str(cpr), organisation_fra=str(organisation_fra), organisation_til=str(organisation_til)))

    return tilføj, fjern, leverandørskift, organisationsskift

def find_excel_fil(mappe_sti: str | Path) -> str|Path:
    over_mappe = Path(mappe_sti)
    if not over_mappe.exists() or not over_mappe.is_dir():
        raise ValueError(f"Mappen findes ikke eller er ikke en mappe: {over_mappe}")
    
     # Find only direct child folders inside the provided path (not the path itself).
    mapper = [sti for sti in over_mappe.iterdir() if sti.is_dir()]
    
    if len(mapper) > 1:
        raise ValueError("Mere end en opgavemappe i hovedmappe")
    
    mappe = mapper[0]
    
    teskt_fil = [*mappe.glob("*.txt")]
    
    if len(teskt_fil) >= 1:
        return ""
    
    excel_fil = [*mappe.glob("*.xlsx"), *mappe.glob("*.xlsm")]
    if not excel_fil:
        return ""
    if len(excel_fil) > 1:
        raise ValueError("Mere end 1 excel-fil fundet")
    return excel_fil[0]

def hent_opgaveskift_organisationer(excel_sti: str | Path) -> list[str]:
    wb = openpyxl.load_workbook(excel_sti)
    organisationer = set()
    for row in wb["Opgave organisationsskifte"].iter_rows(min_row=2, values_only=True):
        cpr, organisation_fra, organisation_til, *_ = row
        if organisation_fra:
            organisationer.add(str(organisation_fra))
    return list(organisationer)
    