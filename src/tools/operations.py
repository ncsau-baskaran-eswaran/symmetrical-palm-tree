"""Tools for managing Critical Operations, Tolerance Levels, and Material Service Providers under CPS 230."""

from typing import Any, Dict, List


def get_mandatory_critical_operations(sector: str) -> Dict[str, Any]:
    """
    Returns the statutory baseline critical operations mandated by CPS 230 paragraph 35
    for a specific industry sector (banking, general_insurance, life_insurance, private_health, superannuation).
    """
    sector_lower = sector.lower().strip()
    
    mapping = {
        "banking": [
            "Payments",
            "Deposit-taking and deposit management",
            "Custody",
            "Settlements and clearing"
        ],
        "adi": [
            "Payments",
            "Deposit-taking and deposit management",
            "Custody",
            "Settlements and clearing"
        ],
        "general_insurance": [
            "Claims processing"
        ],
        "life_insurance": [
            "Claims processing"
        ],
        "insurance": [
            "Claims processing"
        ],
        "private_health_insurance": [
            "Claims processing"
        ],
        "superannuation": [
            "Investment management",
            "Fund administration"
        ],
        "rse": [
            "Investment management",
            "Fund administration"
        ]
    }

    all_entities_baseline = [
        "Customer enquiries",
        "Systems and IT infrastructure needed to support critical operations"
    ]

    matched_sector_ops = []
    for key, ops in mapping.items():
        if key in sector_lower:
            matched_sector_ops = ops
            break

    if not matched_sector_ops:
        matched_sector_ops = [
            "Payments / Core Transactions (if ADI)",
            "Claims Processing (if Insurer)",
            "Investment Management & Fund Administration (if Superannuation)"
        ]

    return {
        "sector": sector,
        "standard": "CPS 230",
        "clause": "Paragraph 35",
        "mandatory_sector_critical_operations": matched_sector_ops,
        "mandatory_cross_entity_critical_operations": all_entities_baseline,
        "required_tolerance_levels": [
            "Maximum period of time tolerating disruption (downtime / outage duration)",
            "Maximum extent of data loss accepted (data recovery point)",
            "Minimum service levels maintained while operating under alternative arrangements"
        ],
        "board_approval_mandate": "CPS 230 para 21 mandates that the Board must formally approve both the critical operations register and tolerance levels."
    }


def get_mandatory_material_service_providers(sector: str) -> Dict[str, Any]:
    """
    Returns the statutory baseline material service providers mandated by CPS 230 paragraph 49
    for a specific industry sector.
    """
    sector_lower = sector.lower().strip()

    mapping = {
        "banking": [
            "Credit assessment",
            "Funding and liquidity management",
            "Mortgage brokerage"
        ],
        "adi": [
            "Credit assessment",
            "Funding and liquidity management",
            "Mortgage brokerage"
        ],
        "general_insurance": [
            "Underwriting",
            "Claims management",
            "Insurance brokerage",
            "Reinsurance"
        ],
        "life_insurance": [
            "Underwriting",
            "Claims management",
            "Insurance brokerage",
            "Reinsurance"
        ],
        "insurance": [
            "Underwriting",
            "Claims management",
            "Insurance brokerage",
            "Reinsurance"
        ],
        "private_health_insurance": [
            "Underwriting",
            "Claims management",
            "Insurance brokerage",
            "Reinsurance"
        ],
        "superannuation": [
            "Fund administration",
            "Custodial services",
            "Investment management",
            "Arrangements with promoters and financial planners"
        ],
        "rse": [
            "Fund administration",
            "Custodial services",
            "Investment management",
            "Arrangements with promoters and financial planners"
        ]
    }

    all_entities_baseline = [
        "Risk management",
        "Core technology services (e.g. cloud hosting, core banking, policy admin systems)",
        "Internal audit"
    ]

    matched_msps = []
    for key, msps in mapping.items():
        if key in sector_lower:
            matched_msps = msps
            break

    if not matched_msps:
        matched_msps = [
            "Credit assessment, liquidity, mortgage brokerage (if ADI)",
            "Underwriting, claims management, reinsurance, brokerage (if Insurer)",
            "Fund admin, custodial, investment management (if Super)"
        ]

    return {
        "sector": sector,
        "standard": "CPS 230",
        "clause": "Paragraph 49",
        "mandatory_sector_msps": matched_msps,
        "mandatory_cross_entity_msps": all_entities_baseline,
        "annual_submission_mandate": "CPS 230 para 50 requires the complete MSP register to be submitted to APRA annually.",
        "contract_requirements": "All arrangements with MSPs must satisfy the formal contract requirements in paragraphs 53 and 54."
    }


def get_service_provider_contract_checklist() -> Dict[str, Any]:
    """
    Returns the mandatory contract terms required under CPS 230 paragraph 53,
    plus the statutory exemptions for non-traditional providers under paragraph 57 and Attachment.
    """
    return {
        "standard": "CPS 230",
        "clause": "Paragraph 53",
        "mandatory_contract_clauses": [
            "Specify the services covered and associated service levels (SLAs);",
            "Set out rights, responsibilities and expectations of each party, including asset ownership, data ownership and control, dispute resolution, audit access, liability and indemnity;",
            "Provisions ensuring the entity can meet legal and compliance obligations;",
            "Require notification by the service provider of its use of other material service providers (fourth parties / sub-contracting);",
            "Require that liability for any failure on the part of any sub-contractor remains the responsibility of the primary service provider;",
            "Force majeure provisions indicating which parts of the contract continue during a force majeure event;",
            "Termination provisions (right to terminate whole or parts of arrangement; for RSE licensees, termination if inconsistent with best financial interests of beneficiaries);",
            "Provisions allowing APRA access to documentation, data and information;",
            "Provisions allowing APRA the right to conduct an on-site visit to the service provider; and",
            "Provisions ensuring the service provider agrees not to impede APRA in fulfilling its duties as prudential regulator."
        ],
        "exempt_provider_categories_attachment": [
            "Government agencies (public sector bodies)",
            "Regulators (APRA, ASIC, ACCC)",
            "Central banks (Reserve Bank of Australia)",
            "Financial market exchanges (ASX, Chi-X / Cboe)",
            "Operators of clearing and settlement facilities (ASX Clear, superannuation clearing houses on SuperStream register)",
            "Operators of payment systems and schemes (NPP, EFTPOS, Visa, Mastercard)",
            "Financial messaging infrastructures (SWIFT, SuperStream gateways)"
        ],
        "exemption_conditions": "Exemption applies if provider falls within Attachment category AND uses standardised terms or lacks a formal negotiated agreement (para 57)."
    }
