from datetime import datetime
from kmd_nexus_client import NexusClientManager
from kmd_nexus_client.tree_helpers import filter_by_path
from proces.models import TiføjOrganisationsOpgave, FjernOrganisationsOpgave, LeverandørsSkiftOpgave, OrganisationsSkiftOpgave
from odk_tools.reporting import report
from odk_tools.tracking import Tracker
from automation_server_client import WorkItemError
import logging

procesnavn = "Flyt borger i Nexus"

class NexusService:
    def __init__(
        self,
        nexus: NexusClientManager,
        tracker: Tracker
        ):
        self.nexus = nexus
        self.tracker = tracker
    
    
        
    def hent_borger(self, cpr:str) -> dict:
        logger = logging.getLogger(__name__)
        borger = self.nexus.borgere.hent_borger(cpr)
        
        if borger is None:
            
            raise ValueError("Borger ikke fundet")
        
        return borger
    
    def hent_aktiviteter(self, organisationsnavne: list[str]) -> list[dict]:
        logger = logging.getLogger(__name__)
        aktiviteter = []
        
        logging.info("Henter aktivitetslister")
        for organisationsnavn in organisationsnavne:
            organisation = self.nexus.organisationer.hent_organisation_ved_navn(organisationsnavn)
        
            aktivtetsliste = self.nexus.aktivitetslister.hent_aktivitetsliste("Opgaver: Robot - 1 måned tilbage og 1 år frem", organisation, None)
        
            if aktivtetsliste is None:
                logger.info(f"Ingen aktitetsliste fundet for {organisationsnavn}")
                continue
            else:
                logger.info(f"Aktitviteter fundet for {organisationsnavn}")
                aktiviteter.extend(aktivtetsliste)
        
        return aktiviteter
    
    def tilføj_organisation(self, opgave: TiføjOrganisationsOpgave):
        logger = logging.getLogger(__name__)
        borger = self.hent_borger(opgave.cpr)
        
        logger.info("Påbegynder 'tilføjelse af organisation' opgave")
        
        organisation = self.nexus.organisationer.hent_organisation_ved_navn(opgave.organisation)
        
        if organisation is None:
            logger.error(f"Kunne ikke hente organisationen: {opgave.organisation}")
            raise WorkItemError("Organisation ikke fundet")
        
        if not self.nexus.organisationer.tilføj_borger_til_organisation(borger, organisation):
            logger.error(f"Fejl, kunne ikke tilføje organisation {opgave.organisation} til borger")
            raise WorkItemError("Kunne ikke tilføje borger til organisation")

        logger.info("Organisation tilføjet, afregner opgave")
        self.tracker.track_task(procesnavn)
    
    def fjern_organisation(self, opgave: FjernOrganisationsOpgave):
        logger = logging.getLogger(__name__)
        borger = self.hent_borger(opgave.cpr)
        
        logger.info("Påbegynder 'fjernelse af organisation' opgave")
        
        borgers_organisationer = self.nexus.organisationer.hent_organisationer_for_borger(borger, True)
        
        organisation = next((org for org in borgers_organisationer if org == opgave.organisation), None)
        
        if organisation is None:
            logger.info("Organisation fandtes ikke på borger, alt godt")
            return
        
        if not self.nexus.organisationer.opdater_borger_organisations_relation(organisation, datetime.strptime(opgave.ophørsdato, "%d-%m-%Y").date(), False):
            logger.error(f"Fejl, kunne ikek fjerne organisation fra borger. Organsisation: {opgave.organisation}")
            raise WorkItemError("Kunne ikke fjerne oragnisationsrelation fra borger")
        
        logger.info("Organisation fjernet, afregner opgave")
        self.tracker.track_task(procesnavn)
    
    def håndter_indsats_flyt(self, opgave: LeverandørsSkiftOpgave, indsats_referencer: list[dict]):
        logger = logging.getLogger(__name__)
        
        
        for indsats_reference in indsats_referencer:
        
            indsats = self.nexus.indsatser.hent_indsats(indsats_reference)
                    
            #Hvis det ikke er den korrekte organisation forsættes til næste indsats
            supplier = next((elem["supplier"] for elem in indsats["currentElements"] if "supplier" in elem), None)
            if supplier is None or supplier["name"] != opgave.organisation_fra:
                continue
            
            #Findes slutdato feltet ikke forsættes til næste indsats
            basketGrantEndDate = next((elem["basketGrantEndDate"] for elem in indsats["currentElements"] if "basketGrantEndDate" in elem), None)
            if basketGrantEndDate is None:
                continue
            
            indsats_dato = basketGrantEndDate["Date"]
            
            #Hvis der er slutdato, som er overskredet forsættes til næste indsats
            if indsats_dato is not None and datetime.strptime(indsats_dato, "%Y-%m-%d").date() < datetime.today().date():
                continue
            
            try:
                logger.info(f"Flytter indsats {indsats["name"]} til {opgave.organisation_til}")    
                self.nexus.indsatser.rediger_indsats(
                    indsats,
                    {
                        "entyDate": opgave.ikrafttrædelsesdato,
                        "billingStartDate": opgave.ikrafttrædelsesdato,
                        "supplier": opgave.organisation_til
                    },
                    "Ændr fremtidigt"
                )
            except Exception as e:
                logger.error(f"Fejl, kunne ikke flytte indsats {indsats["name"]} til {opgave.organisation_til}. Fejlen: {e}")
                report(
                    "flyt-borger-i-nexus",
                    "Fejl",
                    {
                        "Cpr": opgave.cpr,
                        "Indsatsnavn": indsats["name"],
                        "Fejlbesked": e
                    }
                )
            
            logger.info("Indsats flyttet, afregner")
            self.tracker.track_task(procesnavn)
    
    def flyt_indsatser_og_indsatspakker(self, opgave: LeverandørsSkiftOpgave):
        logger = logging.getLogger(__name__)
        borger = self.hent_borger(opgave.cpr)
        
        logger.info("Påbegynder 'Leverandørskift(flytning af indsatser)' opgave")
                
        visning = self.nexus.borgere.hent_visning(borger, "- Alt")
        
        if visning is None:
            logger.error(f"Fejl, kunne ikke hente visning for borger {opgave.cpr}")
            raise WorkItemError("Visning kunne ikke hentes på borger")
                
        referencer = self.nexus.borgere.hent_referencer(visning)
                
        indsats_referencer = filter_by_path(
            referencer,
            "/Ældre og sundhedsfagligt grundforløb/patientPathwayReference/Indsatser/basketGrantReference",
            True
        )
                
        indsatspakke_referencer = filter_by_path(
            referencer,
            "/Ældre og sundhedsfagligt grundforløb/patientPathwayReference/Indsatser/basketGrantPackageReference",
            True
        )               
        
        indsats_referencer = self.nexus.indsatser.filtrer_indsats_referencer(indsats_referencer, True)
        
        indsatspakke_referencer = self.nexus.indsatser.filtrer_indsats_referencer(indsatspakke_referencer, True, inkluder_indsatspakker=True)
        
        if indsats_referencer is not None and indsats_referencer != []:
            logger.info("Indsatser fundet for borger, påbegynder flytning af indsatser")
            self.håndter_indsats_flyt(opgave, indsats_referencer)
        if indsatspakke_referencer is not None and indsatspakke_referencer != []:
            logger.info("Indsatspakker fundet for borger, påbegynder flytning af pakker")
            self.håndter_indsats_flyt(opgave, indsatspakke_referencer)
    
    def flyt_opgaver(self, opgave:OrganisationsSkiftOpgave, aktiviteter:list[dict]):
        logger = logging.getLogger(__name__)
        
        logger.info("Påbegynder 'organisationsskift for opgaver' opgave")
        
        relevante_aktiviter = [a for a in aktiviteter if any(p["patientIdentifier"]["identifier"] == opgave.cpr for p in a["patients"])]
        
        if relevante_aktiviter == []:
            logger.info("Ingen relevante aktiviter fundet for borger")
            return
        
        for aktivitet in relevante_aktiviter:
            opgave_endpoint: str = aktivitet["_links"]["self"]["href"]
            nexus_opgave = self.nexus.nexus_client.get(opgave_endpoint).json()
            
            if nexus_opgave["organizationAssignee"]["displayName"] != opgave.organisation_fra:
                continue
            
            mulige_organisationer = self.nexus.nexus_client.get(nexus_opgave["_links"]["availableOrganizationAssignees"]["href"]).json()
            
            organisation = next((org for org in mulige_organisationer if org["name"] == opgave.organisation_til), None)
            
            if organisation is None:
                logger.info(f"Ønsker organisation: {opgave.organisation_til} ikke fundet som mulighed at flytte opgave til, sender til rapport og foræstter til næste opgave")
                report(
                    "flyt-borger-i-nexus",
                    "Fejl-flyt opgave",
                    {
                        "Cpr": opgave.cpr,
                        "Opgavenavn": nexus_opgave["name"],
                        "Fejlbesked": "Den ønskede organisation var "
                    }
                )
                continue
            
            nexus_opgave["organizationAssignee"] = {}
            nexus_opgave["organizationAssignee"]["organizationId"] = organisation["id"]
            nexus_opgave["organizationAssignee"]["displayName"] = organisation["name"]
            try:
                nexus_opgave = self.nexus.opgaver.rediger_opgave(nexus_opgave)
            except Exception as e:
               logger.error(f"Fejl: {e}")
            
            self.tracker.track_task(procesnavn)