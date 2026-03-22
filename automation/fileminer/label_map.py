"""
Label-to-variable mapping dictionary and source priorities.

This dictionary IS the knowledge base. As new projects reveal new label
conventions, we add entries. Supports Catalan + Spanish variants.
"""

from __future__ import annotations

# Maps raw labels (uppercased for matching) -> report variable name
LABEL_TO_VARIABLE: dict[str, str] = {
    # Client / Promotor
    "CLIENT": "client_name",
    "CLIENTE": "client_name",
    "PROMOTOR": "client_name",
    "PROPIETARI": "client_name",
    "PROMOTOR/PROPIETARI": "client_name",
    "NOM CLIENT": "client_name",
    "NOMBRE CLIENTE": "client_name",

    # Contact
    "CONTACTE": "contact_name",
    "CONTACTO": "contact_name",
    "PERSONA DE CONTACTE": "contact_name",

    # NIF/CIF
    "NIF": "client_nif",
    "CIF": "client_nif",
    "DNI": "client_nif",
    "NIF/CIF": "client_nif",

    # Phone
    "TELÈFON": "client_phone",
    "TELÉFONO": "client_phone",
    "TLF": "client_phone",
    "TEL": "client_phone",
    "MÒBIL": "client_phone",
    "MÓVIL": "client_phone",

    # Email
    "EMAIL": "client_email",
    "CORREU": "client_email",
    "CORREU ELECTRÒNIC": "client_email",
    "CORREO": "client_email",
    "E-MAIL": "client_email",

    # Address / Location
    "ADREÇA OBRA": "street_address",
    "DIRECCIÓN OBRA": "street_address",
    "ADREÇA": "street_address",
    "DIRECCIÓ": "street_address",
    "DIRECCIÓN": "street_address",
    "EMPLAÇAMENT": "street_address",
    "EMPLAZAMIENTO": "street_address",
    "UBICACIÓ": "street_address",
    "UBICACIÓN": "street_address",

    # Municipality
    "MUNICIPI": "municipality",
    "MUNICIPIO": "municipality",
    "POBLACIÓ": "municipality",
    "POBLACIÓN": "municipality",
    "LOCALITAT": "municipality",
    "LOCALIDAD": "municipality",

    # Province
    "PROVÍNCIA": "province",
    "PROVINCIA": "province",

    # Access
    "ACCES A LA ZONA D'ESTUDI": "access_url",
    "ACCESO": "access_url",
    "ACCÉS": "access_url",
    "GOOGLE MAPS": "access_url",
    "ENLLAÇ": "access_url",
    "ENLACE": "access_url",

    # Architect
    "ARQUITECTE": "architect_name",
    "ARQUITECTO": "architect_name",
    "DIRECTOR D'OBRA": "architect_name",
    "DIRECTOR DE OBRA": "architect_name",

    # Architect company
    "DESPATX": "architect_company",
    "DESPACHO": "architect_company",
    "ESTUDI": "architect_company",
    "ESTUDIO": "architect_company",

    # Building
    "TIPUS EDIFICACIÓ": "building_type",
    "TIPO EDIFICACIÓN": "building_type",
    "TIPUS D'OBRA": "building_type",
    "TIPO DE OBRA": "building_type",
    "OBRA": "building_type",

    # Floors
    "PLANTES": "num_floors",
    "PLANTAS": "num_floors",
    "NOMBRE DE PLANTES": "num_floors",
    "NÚMERO DE PLANTAS": "num_floors",
    "Nº PLANTES": "num_floors",
    "Nº PLANTAS": "num_floors",
    "PB+": "num_floors",

    # Surfaces
    "SUPERFÍCIE PARCEL·LA": "superficie_parcela",
    "SUPERFICIE PARCELA": "superficie_parcela",
    "SUP. PARCEL·LA": "superficie_parcela",
    "SUPERFÍCIE CONSTRUÏDA": "superficie_construida",
    "SUPERFICIE CONSTRUIDA": "superficie_construida",
    "SUP. CONSTRUÏDA": "superficie_construida",

    # Expedient
    "EXPEDIENT": "expedient",
    "EXPEDIENTE": "expedient",
    "Nº EXPEDIENT": "expedient",
    "REF": "expedient",
    "REFERÈNCIA": "expedient",

    # Dates
    "DATA": "field_date",
    "FECHA": "field_date",
    "DATA CAMP": "field_date",
    "DATA INICI": "field_date",
    "FECHA CAMPO": "field_date",
}

# Source priority: lower number = more reliable = wins in competition
SOURCE_PRIORITY: dict[str, int] = {
    "user": 10,                     # Eva's manual edit -- always wins
    "planol_vision": 20,            # Claude vision reads actual document
    "sondeig_vision": 20,
    "dpsh_vision": 20,
    "coordenades_txt": 25,          # GPS field-measured
    "pressupost_pdf": 30,           # G3's own structured quote
    "icgc_api": 30,                 # Authoritative geodata
    "cadastre_api": 30,
    "dades_camp_excel": 35,         # Client-provided prep sheet
    "comanda_lab_excel": 35,
    "geocode_nominatim": 40,        # Derived, less precise
    "groq_llm": 42,                 # LLM extraction, between geocode and generic
    "content_email": 43,            # Email body text (addresses, contacts)
    "content_email_attachment": 44,  # Signals from files attached to emails
    "content_pdf": 45,              # Generic PDF text
    "content_docx": 45,             # Generic docx text
    "content_excel": 45,            # Generic Excel (not DADES)
    "content_text": 45,             # Generic text file
    "folder_name": 60,              # Last resort
}


def get_priority(source_type: str) -> int:
    """Get priority for a source type. Unknown sources get 50."""
    return SOURCE_PRIORITY.get(source_type, 50)
