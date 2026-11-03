from typing import Union
from pathlib import Path
import logging
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
            fjern.append(FjernOrganisationsOpgave(cpr=str(cpr), organisation=str(organisation), ophørsdato=ophørsdato))

    leverandørskift = []
    for row in wb["Leverandørskifte indsatser"].iter_rows(min_row=2, values_only=True):
        cpr, organisation_fra, organisation_til, ikrafttrædelsesdato, *_ = row
        if cpr:
            leverandørskift.append(LeverandørsSkiftOpgave(cpr=str(cpr), organisation_fra=str(organisation_fra), organisation_til=str(organisation_til), ikrafttrædelsesdato=ikrafttrædelsesdato))

    organisationsskift = []
    for row in wb["Opgave organisationsskifte"].iter_rows(min_row=2, values_only=True):
        cpr, organisation_fra, organisation_til, *_ = row
        if cpr:
            organisationsskift.append(OrganisationsSkiftOpgave(cpr=str(cpr), organisation_fra=str(organisation_fra), organisation_til=str(organisation_til)))

    return tilføj, fjern, leverandørskift, organisationsskift

def find_excel_fil(mappe_sti: str | Path, ignorer_tekst_fil: bool = False) -> str|Path:
    logger = logging.getLogger(__name__)

    over_mappe = Path(mappe_sti)
    if not over_mappe.exists() or not over_mappe.is_dir():
        raise ValueError(f"Mappen findes ikke eller er ikke en mappe: {over_mappe}")

    # Find only direct child folders inside the provided path (not the path itself).
    mapper = [sti for sti in over_mappe.iterdir() if sti.is_dir()]

    if len(mapper) > 1:
        logger.error("Mere end en mappe fundet, smider fejl og stopper")
        raise ValueError("Mere end en opgavemappe i hovedmappe")

    if len(mapper) == 0:
        logger.info("Ingen mappe fundet, går ud fra der ikke ligger nogle opgaver, stopper")
        return ""

    logger.info("Kun en mappe fundet")
    mappe = mapper[0]

    teskt_fil = [*mappe.glob("*.txt")]

    # Under kørsel ligger Indlæst.txt i mappen, men excel-filen skal stadig kunne findes
    if len(teskt_fil) >= 1 and not ignorer_tekst_fil:
        logger.info("Tekst fil fundet, derfor går vi udfra at opgaveløsning er igang/afsluttet på dette opgavesæt")
        return ""

    excel_fil = [*mappe.glob("*.xlsx"), *mappe.glob("*.xlsm")]
    if not excel_fil:
        return ""
    if len(excel_fil) > 1:
        raise ValueError("Mere end 1 excel-fil fundet")
    return excel_fil[0]

def find_tekst_fil(mappe_sti: str | Path) -> Path | None:
    over_mappe = Path(mappe_sti)
    if not over_mappe.exists() or not over_mappe.is_dir():
        raise ValueError(f"Mappen findes ikke eller er ikke en mappe: {over_mappe}")

    # Find only direct child folders inside the provided path (not the path itself).
    mapper = [sti for sti in over_mappe.iterdir() if sti.is_dir()]

    if len(mapper) > 1:
        raise ValueError("Mere end en opgavemappe i hovedmappe")

    if len(mapper) == 0:
        return None

    mappe = mapper[0]

    teskt_fil = [*mappe.glob("*.txt")]

    if len(teskt_fil) >= 1:
        return teskt_fil[0]
    else:
        return None

def hent_opgaveskift_organisationer(excel_sti: str | Path) -> list[str]:
    wb = openpyxl.load_workbook(excel_sti)
    organisationer = set()
    for row in wb["Opgave organisationsskifte"].iter_rows(min_row=2, values_only=True):
        cpr, organisation_fra, organisation_til, *_ = row
        if organisation_fra:
            organisationer.add(str(organisation_fra))
    return list(organisationer)
    