from catalog import GitHub, failure_issue, ROOT
import os
if not (ROOT/".health-reported").exists():
    failure_issue(GitHub(), ["Falló el proceso. Revisa Actions; el catálogo publicado permanece intacto."], kind="publication" if os.environ.get("GITHUB_WORKFLOW","").startswith("Publish") else "discovery")
