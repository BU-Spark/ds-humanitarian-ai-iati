"""Shared IATI code labels used by the reviewed graph notebooks and loader."""
TRANSACTION_TYPE = {"1": "Incoming Funds", "2": "Outgoing Commitment", "3": "Disbursement", "4": "Expenditure",
                    "5": "Interest Payment", "6": "Loan Repayment", "7": "Reimbursement", "8": "Purchase of Equity",
                    "9": "Sale of Equity", "10": "Credit Guarantee", "11": "Incoming Commitment",
                    "12": "Outgoing Pledge", "13": "Incoming Pledge"}

ORG_TYPE = {"10": "Government", "11": "Local Government", "15": "Other Public Sector", "21": "International NGO",
            "22": "National NGO", "23": "Regional NGO", "24": "Partner Country based NGO", "30": "Public Private Partnership",
            "40": "Multilateral", "60": "Foundation", "70": "Private Sector", "71": "Private Sector in Provider Country",
            "72": "Private Sector in Aid Recipient Country", "73": "Private Sector in Third Country",
            "80": "Academic, Training and Research", "90": "Other"}

SECTOR_VOCAB = {"1": "OECD DAC 5-digit", "2": "OECD DAC 3-digit", "7": "SDG Goal", "8": "SDG Target",
                "10": "Humanitarian Global Clusters", "99": "Reporting Organisation"}
