"""
entities.py -- curated lookup tables for entity resolution.

Three kinds of knowledge live here, all hand-checked against the graph on
2026-10-21 (238 Organisation nodes, 13 Country nodes):

  SAME_AS    canonical ref -> refs that are the SAME organisation published
             under a different identifier. Safe to merge upstream.
  AGENCY_OF  parent ref -> refs that are agencies/ministries/funds OF that
             parent. Must NOT be merged upstream (the client wants funder
             distinctions preserved) but a question about "the UK
             government" should cover them.
  ALIASES    normalised user phrase -> one ref (or, in AMBIGUOUS, several).

Same shape as ALIASES in src/resolve_orgs.py so the pipeline team can paste
the SAME_AS table into it.
"""

# IATI OrganisationType codelist
ORG_TYPES = {
    "10": "Government", "11": "Local Government", "15": "Other Public Sector",
    "21": "International NGO", "22": "National NGO", "23": "Regional NGO",
    "24": "Partner Country based NGO", "30": "Public Private Partnership",
    "40": "Multilateral", "60": "Foundation", "70": "Private Sector",
    "71": "Private Sector in Provider Country", "72": "Private Sector in Aid Recipient Country",
    "73": "Private Sector in Third Country", "80": "Academic, Training and Research",
    "90": "Other",
}

# refs that are not organisations at all; resolver returns them with a warning
PLACEHOLDERS = {
    "MU": "pooled 'Multilateral' funding placeholder used by WFP, not an organisation",
    "ODM": "'Other Directed Multilateral' placeholder used by WFP, not an organisation",
    "XM-DAC-998": "'Developing countries, unspecified' DAC recipient code, not an organisation",
    "name:Oxfam Donor(s)": "anonymised funder placeholder used by Oxfam GB",
    "name:Oxfam Partner(s)": "anonymised implementing-partner placeholder used by Oxfam GB",
    "1": "'UN Common Funds and Agencies' category code, not an organisation",
}

SAME_AS = {
    "XM-DAC-41140": ["name:UN World Food Programme (WFP)"],
    "XI-IATI-EC_ECHO": ["name:EU - ECHO (EC Humanitarian Aid Dept)"],
    "XM-DAC-41122": ["name:UN United Nations Children's Fund UNICEF"],
    "XM-DAC-41114": ["name:UN United Nations Development Programme"],
    "XM-DAC-41121": ["name:UN High Commissioner for Refugees UNHCR"],
    "XM-DAC-41301": ["name:UN Food & Agricultural Organisation"],
    "XM-DAC-47066": ["name:UN-Int Organization for Migration (IOM)"],
    "XM-DAC-41119": ["name:UN Population Fund"],
    "XM-DAC-44000": ["44000", "name:WB World Bank Trust Fund"],
    "XM-DAC-552": ["XM-DAC-46004"],                      # Asian Development Bank twice
    "XM-DAC-6-4": ["name:Italian Agency for Dev & Coop AICS"],
    "XM-DAC-21-1": ["name:Irish Government - Irish Aid"],
    "AU-5": ["name:Australian Govt - DFAT"],
    "XM-DAC-742": ["KR-GOV-010"],                        # Korea / Republic of Korea
    "XM-DAC-5": ["name:German Govt and Embassies"],
    "XM-DAC-4": ["name:French Government"],
    "XM-DAC-7": ["name:Netherlands Government"],
    "XM-DAC-3": ["name:Danish MFA & Embassies", "name:Danish Embassies"],
    "XM-DAC-349": ["name:HAITI Govt"],
    "FAROE ISLANDS": ["FRO"],
    "HOLY SEE": ["HOL"],
    "ANDORRA": ["AND"],
    "RWANDA": ["RWA"],
    "GLOBAL PARTNERSHIP FOR EDUCATION": ["GPE"],
}

AGENCY_OF = {
    "XM-DAC-12": ["XM-DAC-12-1", "name:UK - Scottish Government"],          # United Kingdom
    "XM-DAC-302": ["name:USAID - Bureau for Hum Ass (ex OFDA)",             # United States
                   "name:US - Bureau of Pop, Ref, &  Migration"],
    "XM-DAC-918-1": ["XI-IATI-EC_ECHO", "XI-IATI-EC_DEVCO", "XI-IATI-EC_NEAR",   # European Commission
                     "name:EU - Food Security", "name:EU - European Development Fund",
                     "name:EU - Cofinancing", "name:EU - EIDHR", "name:EU - Non-State Actors & LAs",
                     "name:EU - European Neighbourhood & Partnershp",
                     "name:EU Trust Fund in Response to Syria Cris"],
    "XM-DAC-5": ["XM-DAC-5-7", "DE-1", "name:Deutsche Gesellschaft für Int - GIZ"],   # Germany
    "XM-DAC-701": ["XM-DAC-701-2"],                                         # Japan
    "XM-DAC-301": ["CA-3"],                                                 # Canada
    "XM-DAC-4": ["FR-6"],                                                   # France
    "XM-DAC-10": ["name:Swedish Int'l Development Cooperation"],            # Sweden / Sida
    "XM-DAC-11": ["name:Swiss Agency for Dev and Co-op"],                   # Switzerland / SDC
    "XM-DAC-1": ["name:Austrian Development Agency"],                       # Austria
    "XM-DAC-801": ["AU-5"],                                                 # Australia / DFAT
    "XM-DAC-820": ["NZ-1"],                                                 # New Zealand
    "XM-DAC-21": ["XM-DAC-21-1"],                                           # Ireland
    "XM-DAC-50": ["XM-DAC-50-21", "ES-DIR3-E04585801"],                     # Spain
    "XM-DAC-6": ["XM-DAC-6-4"],                                             # Italy
    "XM-DAC-2": ["XM-DAC-2-10"],                                            # Belgium
    "XM-DAC-255": ["name:Govt of Mali  - DNPSES"],                          # Mali
    "XM-DAC-44000": ["XM-DAC-62", "XM-DAC-77", "XM-DAC-70", "XM-DAC-72"],   # World Bank Group
    "name:UN Office for the Co-ord of Hum Affairs": ["XM-OCHA-CBPF", "XM-OCHA-CERF"],  # OCHA pooled funds
}

# normalised phrase -> ref. Keys must be in normalise() form (see resolve_entity).
ALIASES = {
    # publishers
    "wfp": "XM-DAC-41140", "world food programme": "XM-DAC-41140",
    "world food program": "XM-DAC-41140", "un world food programme": "XM-DAC-41140",
    "un wfp": "XM-DAC-41140",
    "oxfam gb": "GB-CHC-202918", "oxfam great britain": "GB-CHC-202918", "oxfam uk": "GB-CHC-202918",
    "oxfam america": "US-EIN-23-7069110", "oxfam us": "US-EIN-23-7069110", "oxfam usa": "US-EIN-23-7069110",
    "oxfam novib": "NL-KVK-27108436", "oxfam netherlands": "NL-KVK-27108436",
    # governments and their agencies
    "uk": "XM-DAC-12", "united kingdom": "XM-DAC-12", "uk government": "XM-DAC-12",
    "british government": "XM-DAC-12", "great britain": "XM-DAC-12", "hmg": "XM-DAC-12",
    "fcdo": "XM-DAC-12-1", "dfid": "XM-DAC-12-1",
    "foreign commonwealth and development office": "XM-DAC-12-1",
    "department for international development": "XM-DAC-12-1",
    "us": "XM-DAC-302", "usa": "XM-DAC-302", "united states": "XM-DAC-302",
    "us government": "XM-DAC-302", "united states of america": "XM-DAC-302",
    "usaid": "name:USAID - Bureau for Hum Ass (ex OFDA)", "ofda": "name:USAID - Bureau for Hum Ass (ex OFDA)",
    "bha": "name:USAID - Bureau for Hum Ass (ex OFDA)",
    "prm": "name:US - Bureau of Pop, Ref, &  Migration",
    "eu": "XM-DAC-918-1", "european union": "XM-DAC-918-1", "european commission": "XM-DAC-918-1",
    "ec": "XM-DAC-918-1",
    "echo": "XI-IATI-EC_ECHO", "dg echo": "XI-IATI-EC_ECHO",
    "sida": "name:Swedish Int'l Development Cooperation",
    "sdc": "name:Swiss Agency for Dev and Co-op",
    "giz": "name:Deutsche Gesellschaft für Int - GIZ", "bmz": "DE-1",
    "german federal foreign office": "XM-DAC-5-7", "auswartiges amt": "XM-DAC-5-7",
    "dfat": "AU-5", "global affairs canada": "CA-3", "gac": "CA-3",
    "mofa japan": "XM-DAC-701-2", "japan mofa": "XM-DAC-701-2",
    "irish aid": "XM-DAC-21-1", "aecid": "XM-DAC-50-21", "aics": "XM-DAC-6-4",
    "south korea": "XM-DAC-742", "republic of korea": "XM-DAC-742",
    "netherlands": "XM-DAC-7", "the netherlands": "XM-DAC-7",
    # multilaterals
    "unicef": "XM-DAC-41122", "undp": "XM-DAC-41114", "unhcr": "XM-DAC-41121",
    "fao": "XM-DAC-41301", "iom": "XM-DAC-47066", "unfpa": "XM-DAC-41119",
    "who": "XM-DAC-928", "ilo": "name:UN International Labour Organisation ILO",
    "unops": "name:UN Office Fr Proj Svces (UNOPS)",
    "ocha": "name:UN Office for the Co-ord of Hum Affairs",
    "cerf": "XM-OCHA-CERF", "cbpf": "XM-OCHA-CBPF",
    "world bank": "XM-DAC-44000", "wb": "XM-DAC-44000", "world bank group": "XM-DAC-44000",
    "ibrd": "XM-DAC-62", "ida": "XM-DAC-77",
    "adb": "XM-DAC-552", "asian development bank": "XM-DAC-552", "afdb": "XM-DAC-46002",
    "gates foundation": "DAC-1601", "bmgf": "DAC-1601", "bill and melinda gates foundation": "DAC-1601",
    "multilateral": "MU",
    # NGOs
    "dec": "GB-CHC-1062638", "disasters emergency committee": "GB-CHC-1062638",
    "irc": "name:International Rescue Committee (IRC)",
    "nrc": "name:Norwegian Refugee Council (NRC)",
    "drc": "name:Danish Refugee Council",       # as an ORGANISATION; as a country DRC = CD
    "care": "name:CARE International UK",
    "msf": None,  # not in graph; resolver reports no_results with this hint
}

# phrases that legitimately mean several organisations
AMBIGUOUS = {
    "oxfam": {"candidates": ["GB-CHC-202918", "US-EIN-23-7069110", "NL-KVK-27108436"],
              "note": "Oxfam has 19 affiliates in the graph; the two IATI publishers are Oxfam GB and Oxfam America"},
    "save the children": {"candidates": ["name:Save the Children International", "name:Save the Children (UK)"],
                          "note": "two distinct Save the Children entities are published"},
    "acf": {"candidates": ["name:Action Against Hunger (ACF)", "name:ACF Spain"],
            "note": "two Action Against Hunger affiliates are published"},
    "action against hunger": {"candidates": ["name:Action Against Hunger (ACF)", "name:ACF Spain"],
                              "note": "two Action Against Hunger affiliates are published"},
}

# ---------------------------------------------------------------- countries --
ISO3_TO_ISO2 = {
    "SDN": "SD", "SSD": "SS", "YEM": "YE", "PSE": "PS", "NGA": "NG", "SOM": "SO",
    "AFG": "AF", "COD": "CD", "HTI": "HT", "LBN": "LB", "MDG": "MG", "MMR": "MM", "MLI": "ML",
}
COUNTRY_ALIASES = {
    "drc": "CD", "dr congo": "CD", "democratic republic of congo": "CD",
    "democratic republic of the congo": "CD", "congo kinshasa": "CD", "congo drc": "CD", "rdc": "CD",
    "congo": "CD",
    "palestine": "PS", "state of palestine": "PS", "gaza": "PS", "west bank": "PS",
    "occupied palestinian territory": "PS", "opt": "PS", "west bank and gaza": "PS", "palestinian territories": "PS",
    "burma": "MM", "myanmar burma": "MM",
    "south sudan": "SS", "sudan": "SD",   # exact names; listed so "sudan" never fuzzes to South Sudan
    "haiti": "HT", "yemen": "YE", "somalia": "SO", "nigeria": "NG", "afghanistan": "AF",
    "lebanon": "LB", "madagascar": "MG", "myanmar": "MM", "mali": "ML",
}
