"""Template and project type factories for test data generation."""

import factory

from src.db.models.briefing_template import BriefingTemplate
from src.db.models.information_requirement import InformationRequirement
from src.db.models.project_type import ProjectType
from src.db.models.template_version import TemplateVersion
from tests.factories.auth import ArchitectFactory
from tests.factories.base import AsyncSQLAlchemyFactory
from tests.factories.organization import OrganizationFactory


class ProjectTypeFactory(AsyncSQLAlchemyFactory):
    """Factory for creating ProjectType instances."""

    class Meta:
        model = ProjectType
        sqlalchemy_get_or_create = ("slug",)  # Get existing if slug already exists

    slug = factory.Sequence(lambda n: f"project_type_{n}")
    label = factory.LazyAttribute(lambda o: o.slug.replace("_", " ").title())
    description = factory.Faker("sentence")
    is_active = True

    class Params:
        # Common project types as traits - will reuse if already exist
        residencial = factory.Trait(
            slug="residencial",
            label="Residencial",
            description="Projetos residenciais (casas, apartamentos)",
        )
        reforma = factory.Trait(
            slug="reforma",
            label="Reforma",
            description="Reformas e renovações",
        )
        comercial = factory.Trait(
            slug="comercial",
            label="Comercial",
            description="Projetos comerciais",
        )


class InformationRequirementFactory(AsyncSQLAlchemyFactory):
    """Factory for creating InformationRequirement instances."""

    class Meta:
        model = InformationRequirement

    template_version = factory.SubFactory("tests.factories.templates.TemplateVersionFactory")
    template_id = factory.LazyAttribute(lambda o: o.template_version.id)
    field_name = factory.Sequence(lambda n: f"field_{n}")
    field_type = "text"
    required = True
    priority = 5
    description = factory.Faker("sentence")
    validation_rules = factory.Dict({})
    suggested_questions = factory.List([factory.Faker("sentence") for _ in range(2)])

    class Params:
        # Common field types as traits
        budget_field = factory.Trait(
            field_name="budget",
            field_type="number",
            required=True,
            priority=9,
            description="Client's budget for the project in BRL",
            validation_rules={"min": 0, "unit": "BRL"},
            suggested_questions=[
                "Qual é o seu orçamento para o projeto?",
                "Quanto você pretende investir neste projeto?",
            ],
        )
        timeline_field = factory.Trait(
            field_name="timeline",
            field_type="text",
            required=True,
            priority=8,
            description="Expected project timeline or deadline",
            validation_rules={},
            suggested_questions=[
                "Qual é o prazo desejado para conclusão?",
                "Quando você precisa que o projeto esteja pronto?",
            ],
        )
        property_type_field = factory.Trait(
            field_name="property_type",
            field_type="text",
            required=True,
            priority=10,
            description="Type of property (house, apartment, commercial, etc.)",
            validation_rules={},
            suggested_questions=[
                "Qual tipo de imóvel?",
                "O imóvel é casa ou apartamento?",
            ],
        )


class TemplateVersionFactory(AsyncSQLAlchemyFactory):
    """Factory for creating TemplateVersion instances."""

    class Meta:
        model = TemplateVersion

    template = factory.SubFactory("tests.factories.templates.BriefingTemplateFactory")
    template_id = factory.LazyAttribute(lambda o: o.template.id)
    version_number = 1
    change_description = None
    is_active = True
    is_current = False  # Set to True for current versions
    context_prompt = None


class BriefingTemplateFactory(AsyncSQLAlchemyFactory):
    """Factory for creating BriefingTemplate instances.

    NOTE: project_type should be passed from fixtures to avoid unique constraint
    violations when creating multiple templates in a single test.

    Use create_with_version_async() to create a template with a version.
    """

    class Meta:
        model = BriefingTemplate

    name = factory.Sequence(lambda n: f"Test Template {n}")
    category = "general"
    description = factory.Faker("sentence")
    is_global = True
    organization = None
    organization_id = None
    created_by = None
    created_by_architect_id = None
    project_type = None  # Should be passed from fixture
    project_type_id = factory.LazyAttribute(lambda o: o.project_type.id if o.project_type else None)

    @classmethod
    async def create_with_version_async(cls, version_kwargs: dict | None = None, **template_kwargs) -> "BriefingTemplate":  # type: ignore[name-defined]
        """Create a template with a version in one async operation.

        Args:
            version_kwargs: Kwargs for TemplateVersion (requirements, version_number, etc.)
            **template_kwargs: Kwargs for BriefingTemplate

        Returns:
            BriefingTemplate with current version set (via is_current flag)
        """
        from sqlalchemy.ext.asyncio import AsyncSession

        # Create template
        template = await cls.create_async(**template_kwargs)

        # Create version with is_current=True
        version_data = version_kwargs or {}
        version_data.setdefault("is_current", True)
        version = await TemplateVersionFactory.create_async(
            template=template,
            template_id=template.id,
            **version_data,
        )

        # Refresh template to get the version relationship
        session: AsyncSession = cls._meta.sqlalchemy_session
        await session.refresh(template)

        return template

    class Params:
        # Trait: Organization-specific template
        organization_template = factory.Trait(
            is_global=False,
            organization=factory.SubFactory(OrganizationFactory),
            organization_id=factory.LazyAttribute(lambda o: o.organization.id),
            created_by=factory.SubFactory(
                ArchitectFactory,
                organization=factory.SelfAttribute("..organization"),
            ),
            created_by_architect_id=factory.LazyAttribute(lambda o: o.created_by.id),
        )
