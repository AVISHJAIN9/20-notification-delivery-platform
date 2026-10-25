import pytest
from templates.engine import TemplateEngine

def test_NTF_034_user_attribute_personalization():
    """
    NTF-034: User attribute personalization.
    Tests enriching notification templates with user profile attributes (tier, company, name).
    """
    template = "Dear {{user.first_name}}, as a valued {{user.tier}} member at {{user.company}}, enjoy 20% off {{product}}."
    context = {"product": "Enterprise Cloud"}
    user_profile = {
        "first_name": "Marcus",
        "tier": "Platinum",
        "company": "Nexus Corp"
    }

    rendered = TemplateEngine.personalize_content(template, context, user_profile)
    assert rendered == "Dear Marcus, as a valued Platinum member at Nexus Corp, enjoy 20% off Enterprise Cloud."
