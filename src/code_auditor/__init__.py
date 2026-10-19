"""White-box / code-aware ("embedded") analysis of an agent's source.

Goes a notch beyond the black-box behavioural probe: instead of judging what the
agent *says* over HTTP, it reads the agent's actual source and VERIFIES which
CPS 230 / CPS 234 controls are wired in, with file:line evidence.

Co-designed with codex + agy. Findings map to clause *relevance*, never a
compliance verdict; static inspection cannot establish operational effectiveness.
"""
