import pytest
from templates.engine import TemplateEngine

def test_NTF_033_variable_substitution():
    """
    NTF-033: Variable substitution.
    Validates token replacement with single/nested variables and unmatched token preservation.
    """
    template = "Hello {{name}}, your balance is ${{balance}}. Status: {{status}}."
    context = {
        "name": "Sarah",
        "balance": 150.75,
        "status": "Active"
    }

    rendered = TemplateEngine.substitute_variables(template, context)
    assert rendered == "Hello Sarah, your balance is $150.75. Status: Active."

    # Test nested property lookup
    nested_template = "Deploy {{service.name}} to {{service.env}} on cluster {{cluster}}."
    nested_context = {
        "service": {"name": "auth-service", "env": "prod-us-east"},
        "cluster": "k8s-01"
    }
    rendered_nested = TemplateEngine.substitute_variables(nested_template, nested_context)
    assert rendered_nested == "Deploy auth-service to prod-us-east on cluster k8s-01."
