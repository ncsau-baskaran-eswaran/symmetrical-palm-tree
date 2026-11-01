# Deploying Guardian for a client engagement

This guide covers running Guardian for one client, to red-team an agent NCS has built on that client's estate. For
NCS's own shared instance (development, demos, scenario writing, testing before handover) see "Shared NCS instance"
in the [README](../README.md).

## Deployment model

One Guardian codebase and container image, deployed as **one instance per client engagement**, scoped to that
client's industries with `GUARDIAN_SECTORS`.

- The instance runs in or next to the client's environment, so it reaches the agent's test endpoint without opening a
  path from NCS's network, and test traffic and results stay inside the client's boundary.
- Each engagement has its own tokens, judge credentials, logs and reports, so one client's results never sit with
  another's.
- The scope makes the client's industry the default everywhere: red-team tools use it when a call names no industry,
  and an audit whose role name does not identify an industry is screened against it.

A `sector` passed on an individual call still overrides the scope for that call. Name the client's industry on calls
anyway; the scope is the safety net, not the only control.

## Before you deploy

| Check | What is needed |
| :--- | :--- |
| Authorisation | Written client approval naming the agent endpoints to probe (test or staging only), the dates and who runs the tests. Probes send real adversarial prompts. |
| Contract wording | The responsibility wording in the README ("Responsibility and use") is in the SOW: findings are a testing aid, the client validates them and owns compliance and any regulator notification. |
| Judge provider | The judge sends agent replies to the model provider. Agree with the client whether NCS's Azure AI Foundry (Australia East) is acceptable or the client's own Azure tenant is used, and record it (privacy and, for APRA-regulated clients, CPS 230 service provider considerations). |
| Network | The instance can reach the agent's test endpoint; private or loopback targets need the probe allow-list. It should not be reachable from outside the client's network. |
| Retention | Agree how long probe results and reports are kept and who deletes them when the engagement ends. |

## Base settings

```bash
GUARDIAN_SECTORS=<see the industry table below>
GUARDIAN_TOOLSETS=core,reference,redteam
GUARDIAN_JUDGE_PROVIDER=azure_ai/gpt-5-6-sol
GUARDIAN_JUDGE_WHEN=always
AZURE_AI_API_BASE=...            # the agreed Azure AI Foundry endpoint
AZURE_AI_API_KEY=...
GUARDIAN_STATE=<client's main state, e.g. VIC>
GUARDIAN_REDACT=1                # default; keep customer PII masked in results
```

Run it with the container (`Dockerfile.http`) and one bearer token per person or tool, as in the README's "One server
for the team" and "Remote deployment" sections. Check the scope with `list_domains`: its `server_scope` field shows the
industries the instance is locked to.

## By industry

| Client | `GUARDIAN_SECTORS` | Screening | Coverage to confirm with the client |
| :--- | :--- | :--- | :--- |
| General insurer | `gi` | Rules plus judge | National. GI Code redraft due late 2026. |
| Life insurer | `life` | Rules plus judge | National. Life Code clause numbers. |
| Health fund | `phi` | Rules plus judge | National. |
| Insurance group | `insurance` (or e.g. `gi,life`) | Rules plus judge | As above. |
| Bank (ADI) | `banking` | Banking rules plus judge | National. Banking Act and APS standards not loaded; scams framework not yet in force for banks. |
| Bank with an insurance arm | `banking,gi` | Rules plus judge | Both of the above. |
| Super fund (RSE licensee) | `superannuation` | Judge only | SIS Act, SPS 515, SPS 530, RG 271, CPS 230/234. SIS Regulations and Corporations Act product rules not loaded. |
| Energy retailer | `energy_retail` | Judge only | Deepest for Victoria (EIA, Energy Retail Code). NECF states rest on the NERL; the National Energy Retail Rules are not cited yet. |
| Telco | `telecommunications` | Judge only | National (ACMA standards, TCP Code). The family violence industry standard is not covered. |
| Water utility | `water` | Judge only | Victoria and Sydney Water only. Other NSW utilities and other states are not covered. |
| Commonwealth agency | `public_sector` | Judge only | Commonwealth only (Privacy Act, FOI Act, ART Act, Ombudsman guide). State agencies are not covered. |
| Retail or e-commerce | `commercial` | Judge only | ACL, Spam Act, Privacy Act. A small business under the Privacy Act threshold may be outside the APPs. |

"Judge only" industries have no deterministic rules: without a configured judge every probe returns `NOT_SCREENED`,
and every finding is a REVIEW flag for a person to confirm. Each industry's full list of known gaps is in
`list_domains`; share the relevant ones with the client before testing so the scope of the run is clear.

## Running the engagement

1. `list_domains`: confirm `server_scope` and read the industry's known gaps.
2. `get_red_team_scenarios()`: the scoped industry's scenarios (add `attack_category` to narrow them).
3. `probe_external_agent(target_url=..., auth_token=...)`: runs the scenarios against the agent's test endpoint and
   returns the report. Re-run after each fix to the agent.
4. `audit_agent_for_regulatory_breach(...)` with `prior_turns`: screen transcripts from the client's own testing.
5. A person reviews every REVIEW flag against the cited provision before the report goes to the client's risk and
   compliance team.

## Ending the engagement

- Revoke the instance's bearer tokens and the judge key issued for the engagement.
- Delete or hand over probe results and reports as agreed under Retention.
- Remove the instance and any network access created for it.
