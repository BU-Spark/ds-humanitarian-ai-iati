"""
Central configuration for the IATI Hunger Hotspots knowledge graph prototype.

Scope (per Brent's email, July 2026):
  - Orgs: Oxfam GB vs Oxfam America, with WFP as comparison
  - Theme: hunger-related activities
  - Geography: FAO-WFP Hunger Hotspots (June-November 2026 outlook, CE0155EN)
"""

# ---------------------------------------------------------------------------
# Publishers (IATI Registry CKAN publisher slugs)
# Verify with: python 01_download.py --find-publisher oxfam
# ---------------------------------------------------------------------------
PUBLISHERS = {
    "oxfamgb": {
        "label": "Oxfam GB",
        "org_ref": "GB-CHC-202918",
    },
    "oxfamus": {
        "label": "Oxfam America",
        "org_ref": "US-EIN-237069110",
    },
    "wfp": {
        "label": "World Food Programme",
        "org_ref": "XM-DAC-41140",
    },
}

# ---------------------------------------------------------------------------
# Hunger Hotspots geographies (June-Nov 2026 outlook), ISO 3166-1 alpha-2
# tier: 1 = highest concern, 2 = very high concern, 3 = hotspot
# ---------------------------------------------------------------------------
HOTSPOTS = {
    "SD": {"name": "Sudan",                            "tier": 1},
    "SS": {"name": "South Sudan",                      "tier": 1},
    "YE": {"name": "Yemen",                            "tier": 1},
    "PS": {"name": "Palestine",                        "tier": 1},
    "NG": {"name": "Nigeria",                          "tier": 1},
    "SO": {"name": "Somalia",                          "tier": 1},
    "AF": {"name": "Afghanistan",                      "tier": 2},
    "CD": {"name": "Democratic Republic of the Congo", "tier": 2},
    "HT": {"name": "Haiti",                            "tier": 2},
    "LB": {"name": "Lebanon",                          "tier": 3},
    "MG": {"name": "Madagascar",                       "tier": 3},
    "MM": {"name": "Myanmar",                          "tier": 3},
    "ML": {"name": "Mali",                             "tier": 3},
}

# Dataset short_names to always download regardless of the country
# heuristic (e.g. regional files with ambiguous 2-letter suffixes)
EXTRA_DATASETS = {"wfp-wa"}

# ---------------------------------------------------------------------------
# Hunger relevance filters
# ---------------------------------------------------------------------------

# OECD DAC 5-digit purpose codes (IATI sector vocabulary "1", or "2" prefixes)
HUNGER_DAC_CODES = {
    "12240",  # Basic nutrition
    "31110", "31120", "31130", "31140", "31150", "31161", "31162", "31163",
    "31164", "31165", "31166", "31181", "31182", "31191", "31192", "31193",
    "31194", "31195",  # Agriculture
    "31310", "31320", "31381", "31382", "31391",  # Fishing
    "43071",  # Food security policy & admin management
    "43072",  # Household food security programmes
    "43073",  # Food safety and quality
    "52010",  # Food assistance
    "72040",  # Emergency food assistance
    "72010",  # Material relief assistance and services (broad; toggle below)
}

# 3-digit DAC categories treated as hunger-relevant when publishers report
# at category level (vocabulary "2")
HUNGER_DAC_CATEGORIES = {"311", "313", "520"}

# Humanitarian Global Clusters (IATI sector vocabulary "10")
HUNGER_CLUSTER_CODES = {
    "6",   # Food Security
    "9",   # Nutrition
    "26512", "26513",  # OCHA FTS variants sometimes seen for FSC/Nutrition
}

# Whether 72010 (general material relief) counts as hunger-related.
# It is broad; keep False for a tighter prototype slice, True for recall.
INCLUDE_GENERAL_EMERGENCY = False

# Keyword fallback applied to title/description when an activity has no
# usable sector coding (case-insensitive, word-ish matching in parser)
HUNGER_KEYWORDS = [
    "food security", "food assistance", "food aid", "hunger", "famine",
    "nutrition", "malnutrition", "school feeding", "cash transfer",
    "agriculture", "agricultural", "livestock", "crop", "harvest",
    "food insecurity", "IPC", "emergency food", "livelihood", "food",
]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
GRAPH_DIR = ROOT / "data" / "graph"

REGISTRY_API = "https://iatiregistry.org/api/3/action"
