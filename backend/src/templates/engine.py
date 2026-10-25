"""
Template and Personalization Engine (NTF-028, NTF-029, NTF-033, NTF-034, NTF-041).
Provides:
- Template registry and version management.
- Double curly brace variable substitution with missing key reporting.
- User attribute personalization.
- Subject generation and length enforcement.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
import re
import uuid
from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.store import TemplateRecord, TemplateSchema, NotificationStoreManager


class TemplateEngine:
    _sandbox_env = SandboxedEnvironment()

    def __init__(self, session: AsyncSession):
        self.session = session
        self.store = NotificationStoreManager(session)

    @classmethod
    def render_template_text(cls, template_str: Optional[str], context: Dict[str, Any]) -> str:
        """
        Renders dynamic template blocks (conditionals, loops) safely via SandboxedEnvironment (NTF-039).
        Protects against SSTI.
        """
        if not template_str:
            return ""
        template = cls._sandbox_env.from_string(template_str)
        return template.render(**context)

    async def register_template(
        self,
        template_id: str,
        tenant_id: str,
        name: str,
        channel: str,
        body_template: str,
        subject_template: Optional[str] = None,
        language: str = "en",
        version: int = 1
    ) -> TemplateSchema:
        """
        Registers or updates a template in the template registry (NTF-028, NTF-029, NTF-037).
        """
        return await self.store.create_template(
            template_id=template_id,
            tenant_id=tenant_id,
            name=name,
            channel=channel,
            body_template=body_template,
            subject_template=subject_template,
            language=language,
            version=version
        )

    async def get_template_version(
        self,
        tenant_id: str,
        name: str,
        version: Optional[int] = None
    ) -> Optional[TemplateSchema]:
        """
        Retrieves a specific or latest active version of a template (NTF-029).
        """
        return await self.store.get_template(tenant_id, name, version)

    async def select_template(
        self,
        tenant_id: str,
        name: str,
        channel: Optional[str] = None,
        version: Optional[int] = None,
        language: Optional[str] = None
    ) -> Optional[TemplateSchema]:
        """
        Dynamically selects template based on tenant, template name, channel, version, and language fallback chain (NTF-017, NTF-037).
        """
        if language:
            chain = [language]
            if "-" in language:
                chain.append(language.split("-")[0])
            if "en" not in chain:
                chain.append("en")
            for lang in chain:
                tmpl = await self.store.get_template(
                    tenant_id=tenant_id,
                    name=name,
                    version=version,
                    channel=channel,
                    language=lang
                )
                if tmpl:
                    return tmpl
            return None
        return await self.store.get_template(tenant_id, name, version=version, channel=channel)

    async def approve_template(
        self,
        tenant_id: str,
        template_id: str,
        actor: str,
        role: str
    ) -> TemplateSchema:
        """
        Approves a template, verifying role and enforcing state machine transitions (NTF-030).
        """
        if role not in ("admin", "template_approver"):
            raise PermissionError(f"Unauthorized role '{role}' for template approval")

        stmt = select(TemplateRecord).where(
            TemplateRecord.id == template_id,
            TemplateRecord.tenant_id == tenant_id
        )
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            raise ValueError(f"Template '{template_id}' not found for tenant '{tenant_id}'")

        if rec.status not in ("DRAFT", "PENDING_APPROVAL"):
            raise ValueError(f"Illegal transition: cannot approve template with status '{rec.status}'")

        now = datetime.now(timezone.utc)
        rec.status = "APPROVED"
        rec.is_active = True
        rec.approved_by = actor
        rec.approved_at = now
        await self.session.commit()

        # Audit log entry
        audit_id = f"aud_{uuid.uuid4().hex[:16]}"
        await self.store.record_audit_event(
            audit_id=audit_id,
            tenant_id=tenant_id,
            actor=actor,
            action="TEMPLATE_APPROVED",
            resource_type="template",
            resource_id=template_id,
            details={"version": rec.version, "role": role}
        )

        return TemplateSchema.model_validate(rec)

    async def deactivate_template(
        self,
        tenant_id: str,
        template_id: str,
        actor: str,
        role: str
    ) -> TemplateSchema:
        """
        Deactivates a template, enforcing role check and writing audit entry (NTF-032).
        """
        if role not in ("admin", "template_approver", "developer"):
            raise PermissionError(f"Unauthorized role '{role}' for template deactivation")

        stmt = select(TemplateRecord).where(
            TemplateRecord.id == template_id,
            TemplateRecord.tenant_id == tenant_id
        )
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            raise ValueError(f"Template '{template_id}' not found for tenant '{tenant_id}'")

        if rec.status == "DEACTIVATED" or not rec.is_active:
            raise ValueError(f"Template '{template_id}' is already DEACTIVATED")

        now = datetime.now(timezone.utc)
        rec.status = "DEACTIVATED"
        rec.is_active = False
        rec.deactivated_by = actor
        rec.deactivated_at = now
        await self.session.commit()

        # Audit log entry
        audit_id = f"aud_{uuid.uuid4().hex[:16]}"
        await self.store.record_audit_event(
            audit_id=audit_id,
            tenant_id=tenant_id,
            actor=actor,
            action="TEMPLATE_DEACTIVATED",
            resource_type="template",
            resource_id=template_id,
            details={"version": rec.version, "role": role}
        )

        return TemplateSchema.model_validate(rec)

    @staticmethod
    def substitute_variables(template_str: Optional[str], context: Dict[str, Any]) -> str:
        """
        Replaces {{variable_name}} tokens with values from context (NTF-033).
        Preserves un-matched tokens or sets default if missing.
        """
        if not template_str:
            return ""

        def replacer(match):
            key = match.group(1).strip()
            # Support nested dict lookup: user.name -> context["user"]["name"]
            parts = key.split(".")
            curr = context
            for p in parts:
                if isinstance(curr, dict) and p in curr:
                    curr = curr[p]
                else:
                    return match.group(0)  # Keep raw token if missing
            return str(curr)

        return re.sub(r"\{\{\s*([a-zA-Z0-9_\.]+)\s*\}\}", replacer, template_str)

    @classmethod
    def personalize_content(
        cls,
        template_str: str,
        context: Dict[str, Any],
        user_profile: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Merges notification context with user profile attributes for personalization (NTF-034).
        """
        merged = dict(context)
        if user_profile:
            merged["user"] = user_profile
            # Also merge top-level user fields for convenience if not shadowed
            for k, v in user_profile.items():
                if k not in merged:
                    merged[k] = v

        return cls.substitute_variables(template_str, merged)

    @classmethod
    def generate_subject(
        cls,
        subject_template: Optional[str],
        context: Dict[str, Any],
        user_profile: Optional[Dict[str, Any]] = None,
        max_length: int = 150
    ) -> str:
        """
        Renders dynamic subject line with variable substitution and length truncation (NTF-041).
        """
        if not subject_template:
            return ""

        rendered = cls.personalize_content(subject_template, context, user_profile)
        # Normalize whitespace
        clean_subject = " ".join(rendered.split())
        if len(clean_subject) > max_length:
            return clean_subject[:max_length - 3] + "..."
        return clean_subject

    async def render(
        self,
        tenant_id: str,
        name: str,
        context: Dict[str, Any],
        user_profile: Optional[Dict[str, Any]] = None,
        version: Optional[int] = None
    ) -> Tuple[str, str]:
        """
        Full render helper returning (rendered_subject, rendered_body).
        """
        tmpl = await self.get_template_version(tenant_id, name, version)
        if not tmpl:
            raise ValueError(f"Template '{name}' not found for tenant '{tenant_id}'")

        subject = self.generate_subject(tmpl.subject_template, context, user_profile)
        body = self.personalize_content(tmpl.body_template, context, user_profile)
        return subject, body
