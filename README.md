# Flyt borger i KMD Nexus

Automatiserer flytning af borgere i KMD Nexus ved at læse opgaver fra en Excel-fil og udføre organisations- og leverandørskift for borgere baseret på CPR-nummer.

## Hvad gør robotten?

1. Finder og læser en Excel-fil i den angivne mappe (standard: `test_filer`).
2. Afkoder Excel-filen og udtrækker fire typer opgaver: tilføj organisation, fjern organisation, leverandørskift og organisationsskift.
3. Opretter en `Indlæst.txt`-markørfil og fylder arbejdskøen med opgaverne (ved `--queue`).
4. Behandler hver opgave i arbejdskøen:
   - **tilføj** – tilføjer borgeren til en organisation i Nexus.
   - **fjern** – sætter en ophørsdato på borgerens organisationsrelation.
   - **leverandørskift** – flytter borgerens aktive indsatser og indsatspakker fra én leverandør til en anden med ny ikrafttrædelsesdato.
   - **organisationsskift** – reassignerer borgerens Nexus-opgaver fra én organisation til en anden.
5. Rapporterer fejl via odk_tools-rapportering og logger dem i arbejdskøen som fejlede items.
6. Omdøber `Indlæst.txt` til `Kørsel Gennemført.txt` når alle opgaver er behandlet.

## Forudsætninger

- Python ≥ 3.13
- [`uv`](https://docs.astral.sh/uv/) til pakkehåndtering
- Adgang til **Automation Server** (arbejdskø)
- Adgang til **KMD Nexus** (produktion)
- Adgang til **Odense SQL Server**

## Installation

```sh
uv sync
```

## Konfiguration

Credentials registreres i Automation Server:

- `KMD Nexus - produktion`
- `Odense SQL Server`

| Miljøvariabel | Beskrivelse |
|---|---|
| `ATS_URL` | URL til Automation Server API (f.eks. `http://localhost/api`) |
| `ATS_TOKEN` | Bearer token til autentificering mod Automation Server |
| `ATS_WORKQUEUE_OVERRIDE` | Overstyr arbejdskø-ID (valgfri) |

## Kørsel

```sh
uv run python main.py --queue --folder-path <sti-til-mappe>   # Fyld arbejdskøen
uv run python main.py --folder-path <sti-til-mappe>           # Behandl arbejdskøen
```

Mappen med Excel-filen angives via `--folder-path` (standard: `test_filer`).

## Afhængigheder

| Pakke | Formål |
|---|---|
| `automation-server-client` | Klient til Automation Server – håndterer arbejdskø, credentials og workitems |
| `kmd-nexus-client` | Klient til KMD Nexus – tilgår borgere, organisationer, indsatser, indsatspakker og opgaver |
| `odk-tools` | Hjælpeværktøjer til fejlrapportering og opgavesporing |
| `openpyxl` | Læser Excel-filer med opgavedata |

## GDPR og sikkerhed

CPR-numre behandles for alle borgere der flyttes. CPR bruges til opslag og identifikation i KMD Nexus og indgår i fejlrapporter. Fejlrapporter sendes via odk_tools-rapportering og er tilgængelige for de medarbejdere der har adgang hertil.
