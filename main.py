import asyncio
import logging
import os
import sys
import argparse
from pathlib import Path

from automation_server_client import AutomationServer, Workqueue, WorkItemError, Credential, WorkItemStatus
from kmd_nexus_client import NexusClientManager
from odk_tools.reporting import report
from odk_tools.tracking import Tracker

from proces.models import LeverandørsSkiftOpgave, OrganisationsSkiftOpgave, FjernOrganisationsOpgave, TiføjOrganisationsOpgave
from itertools import chain
from proces.excel_service import find_excel_fil, find_tekst_fil, afkode_excel, hent_opgaveskift_organisationer
from proces.nexus_service import NexusService

nexus: NexusClientManager
tracker: Tracker
nexus_service: NexusService

procesnavn = "Flyt borger i Nexus"

async def populate_queue(workqueue: Workqueue, mappe_sti: str|Path):
    logger = logging.getLogger(__name__)

    excel_fil_sti = find_excel_fil(mappe_sti, ignorer_tekst_fil=True)

    if excel_fil_sti == "":
        return

    mappe = Path(excel_fil_sti).parent
    if (mappe / "Indlæst.txt").exists() or (mappe / "Kørsel Gennemført.txt").exists():
        logger.info("Indlæst.txt eller Kørsel Gennemført.txt fundet, stopper")
        return

    tilføj_opgaver, fjern_opgaver, leverandskift_opgaver, organisationsskift_opgaver = afkode_excel(excel_fil_sti)

    Path(excel_fil_sti).parent.joinpath("Indlæst.txt").write_text("", encoding="utf-8")

    for opgave in tilføj_opgaver:
        workqueue.add_item(opgave.model_dump(), opgave.cpr)

    for opgave in fjern_opgaver:
        workqueue.add_item(opgave.model_dump(), opgave.cpr)

    for opgave in leverandskift_opgaver:
        workqueue.add_item(opgave.model_dump(), opgave.cpr)

    for opgave in organisationsskift_opgaver:
        workqueue.add_item(opgave.model_dump(), opgave.cpr)


async def process_workqueue(workqueue: Workqueue, mappe_sti: str|Path):
    logger = logging.getLogger(__name__)
        
    aktiviteter = []

    for item in workqueue:
        with item:
            data = item.data  # Item data deserialized from json as dict
            try:              
                match data["type"]:
                    case "tilføj":
                        opgave = TiføjOrganisationsOpgave.model_validate(data)
                        nexus_service.tilføj_organisation(opgave)                                                        
                    case "fjern":
                        opgave = FjernOrganisationsOpgave.model_validate(data)
                        nexus_service.fjern_organisation(opgave)
                    case "leverandørskift":
                        opgave = LeverandørsSkiftOpgave.model_validate(data)
                                               
                        nexus_service.flyt_indsatser_og_indsatspakker(opgave)
                    case "organisationsskift":
                        opgave = OrganisationsSkiftOpgave.model_validate(data)
                        
                        if aktiviteter == []:
                            excel_fil_sti = find_excel_fil(mappe_sti, ignorer_tekst_fil=True)
                            organisationsnavne = hent_opgaveskift_organisationer(excel_fil_sti)

                            aktiviteter = nexus_service.hent_aktiviteter(organisationsnavne)
                        
                        nexus_service.flyt_opgaver(opgave, aktiviteter)                                         
                    case _:
                        raise WorkItemError(f"Ukendt opgavetype: {data['type']}")
            except WorkItemError as e:
                
                report(
                    "flyt-borger-i-nexus",
                    "Fejl",
                    {
                        "Cpr": data["cpr"],
                        "Fejl": str(e)
                    }
                )
                # A WorkItemError represents a soft error that indicates the item should be passed to manual processing or a business logic fault
                logger.error(f"Error processing item: {data}. Error: {str(e)}")
                item.fail(str(e))
                
    #Håndter overskriv fil og lig ny fil, omkring opgave gennemført
    tekst_fil = find_tekst_fil(mappe_sti)

    if tekst_fil is not None and tekst_fil.name == "Indlæst.txt":
        tekst_fil.rename(tekst_fil.parent / "Kørsel Gennemført.txt")

    #Marker gennemført på rapport
    report(
        "flyt-borger-i-nexus",
        "Kørsel gennemført",
        {
            "Kørsel gennemført": "Kørsel afsluttet"
        }
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # ATS' log-handler sender hver logbesked til serveren med httpx, som selv logger
    # hvert kald på INFO. Det giver en endeløs kæde af POST /audit-logs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()
    
    parser = argparse.ArgumentParser(description=procesnavn)
    
    parser.add_argument(
        "--queue",
        action="store_true"
    )
    
    parser.add_argument(
        "--folder-path",
        type=Path,
        default=None,
        help="Kan også angives med miljøvariablen FOLDER_PATH",
    )

    args = parser.parse_args()

    mappe_sti = args.folder_path or os.environ.get("FOLDER_PATH")
    if not mappe_sti:
        sys.exit("--folder-path (eller FOLDER_PATH) skal angives")

    # Initialize external systems for automation here..
    nexus_credential = Credential.get_credential("KMD Nexus - produktion")
    tracking_credential = Credential.get_credential("Odense SQL Server")
    
    nexus = NexusClientManager(
        nexus_credential.data["instance"],
        nexus_credential.username or "",
        nexus_credential.password or "",
    )
    
    tracker = Tracker(
        username=tracking_credential.username or "",
        password=tracking_credential.password or ""
    )
    
    nexus_service = NexusService(
        nexus,
        tracker
    )

    # Queue management
    if args.queue:
        workqueue.clear_workqueue(WorkItemStatus.NEW)
        asyncio.run(populate_queue(workqueue, mappe_sti))
        exit(0)

    # Process workqueue
    asyncio.run(process_workqueue(workqueue, mappe_sti))
