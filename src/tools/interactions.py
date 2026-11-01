"""Analysis of interactions and intersections between CPS 230 and CPS 234."""

from typing import Any, Dict


def get_cps230_cps234_interaction_analysis() -> Dict[str, Any]:
    """
    Detailed mapping and operational interaction guide between CPS 230 (Operational Risk)
    and CPS 234 (Information Security).
    """
    return {
        "title": "APRA Prudential Standards Interaction: CPS 230 vs CPS 234",
        "overview": (
            "While CPS 234 focuses on protecting information assets against cyber and security threats, "
            "CPS 230 focuses on maintaining operational resilience, continuity of critical operations, "
            "and service provider arrangements. In practice, technology and third parties cross both standards."
        ),
        "key_intersections": [
            {
                "domain": "Technology & Cyber Risk",
                "cps_230_reference": "Paragraph 24: Entity must maintain sound IT capability and expressly 'meet the requirements for information security in Prudential Standard CPS 234'.",
                "cps_234_reference": "Whole standard: Information security capability, asset classification, preventative/detective controls, and testing.",
                "operational_guidance": "A failure in CPS 234 controls is directly an operational risk management failure under CPS 230."
            },
            {
                "domain": "Incident Reporting & De-duplication",
                "cps_230_reference": "Paragraph 32 (72h reporting) & Footnote 11.",
                "cps_234_reference": "Paragraph 35 (72h incident reporting).",
                "operational_guidance": (
                    "Footnote 11 of CPS 230 provides an explicit de-duplication safe harbor: An information security "
                    "incident already notified to APRA under CPS 234 (para 35) does NOT need to be separately reported "
                    "under CPS 230 (para 32). HOWEVER, if that same cyber incident causes an operational outage exceeding "
                    "tolerance levels for a critical operation, a 24-hour notification under CPS 230 para 41 remains MANDATORY."
                )
            },
            {
                "domain": "Third-Party & Vendor Oversight",
                "cps_230_reference": "Paragraphs 46 to 61: Material service providers (MSPs), fourth parties, formal contracts with APRA audit rights, annual MSP register.",
                "cps_234_reference": "Paragraphs 16, 20, 22, 28, 32, 34: Assessing third-party info sec capability, classifying third-party assets, evaluating control design, testing, and internal audit assurance.",
                "operational_guidance": (
                    "When onboarding a cloud provider or SaaS vendor: CPS 230 governs the commercial contract, "
                    "subcontracting liabilities, and business continuity tolerance. CPS 234 governs the technical controls, "
                    "SOC2 / ISO 27001 assurance reviews, penetration testing assessments, and asset classification."
                )
            },
            {
                "domain": "Asset Classification vs Tolerance Levels",
                "cps_230_reference": "Paragraph 37: Tolerance levels (Downtime duration, Data loss accepted, Minimum service level).",
                "cps_234_reference": "Paragraph 20: Information asset classification by Criticality (availability loss) and Sensitivity (confidentiality/integrity loss).",
                "operational_guidance": (
                    "CPS 234 'criticality' (availability) directly informs the CPS 230 'maximum acceptable downtime'. "
                    "CPS 234 'sensitivity' directly informs the CPS 230 'maximum data loss' and integrity safeguards."
                )
            },
            {
                "domain": "Internal Audit",
                "cps_230_reference": "Paragraph 61: Internal audit review of outsourced critical operations.",
                "cps_234_reference": "Paragraphs 32-34: Internal audit review of information security controls and third-party control assurance.",
                "operational_guidance": "Internal audit plans must cover both operational resilience/contracting and technical cyber security controls."
            }
        ]
    }
