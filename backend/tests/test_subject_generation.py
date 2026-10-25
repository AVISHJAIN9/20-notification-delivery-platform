import pytest
from templates.engine import TemplateEngine

def test_NTF_041_subject_generation():
    """
    NTF-041: Subject generation.
    Tests rendering dynamic subjects with variable replacement and character length enforcement.
    """
    subject_tmpl = "Action Required: {{incident.severity}} incident on {{incident.service}}"
    context = {
        "incident": {"severity": "SEV-1", "service": "payment-gateway"}
    }

    subject = TemplateEngine.generate_subject(subject_tmpl, context, max_length=100)
    assert subject == "Action Required: SEV-1 incident on payment-gateway"

    # Test truncation when exceeding max_length
    long_tmpl = "Alert: " + ("Very long warning text " * 10)
    truncated = TemplateEngine.generate_subject(long_tmpl, {}, max_length=50)
    assert len(truncated) <= 50
    assert truncated.endswith("...")
