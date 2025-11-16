"""Template and project type factories for test data generation."""

import factory

from src.db.models.briefing_template import BriefingTemplate
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


class TemplateVersionFactory(AsyncSQLAlchemyFactory):
    """Factory for creating TemplateVersion instances."""

    class Meta:
        model = TemplateVersion

    template = factory.SubFactory("tests.factories.templates.BriefingTemplateFactory")
    template_id = factory.LazyAttribute(lambda o: o.template.id)
    version_number = 1
    questions = factory.LazyFunction(
        lambda: [
            {
                "order": 1,
                "question": "Qual tipo de imóvel?",
                "type": "text",
                "required": True,
            },
            {
                "order": 2,
                "question": "Quantos quartos?",
                "type": "text",
                "required": True,
            },
            {
                "order": 3,
                "question": "Possui terreno?",
                "type": "text",
                "required": True,
            },
        ]
    )
    change_description = None
    is_active = True
    context_prompt = None

    class Params:
        # Trait: Version with conditional questions
        with_conditions = factory.Trait(
            questions=factory.LazyFunction(
                lambda: [
                    {
                        "order": 1,
                        "question": "Qual tipo de projeto?",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "order": 2,
                        "question": "É reforma?",
                        "type": "boolean",
                        "required": True,
                    },
                    {
                        "order": 3,
                        "question": "Qual o escopo da reforma?",
                        "type": "text",
                        "required": True,
                        "condition": {"question_order": 2, "expected": "sim"},
                    },
                ]
            )
        )


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
    current_version_id = None

    @classmethod
    async def create_with_version_async(cls, version_kwargs: dict | None = None, **template_kwargs) -> "BriefingTemplate":  # type: ignore[name-defined]
        """Create a template with a version in one async operation.

        Args:
            version_kwargs: Kwargs for TemplateVersion (questions, version_number, etc.)
            **template_kwargs: Kwargs for BriefingTemplate

        Returns:
            BriefingTemplate with current_version set
        """
        from sqlalchemy.ext.asyncio import AsyncSession

        # Create template
        template = await cls.create_async(**template_kwargs)

        # Create version
        version_data = version_kwargs or {}
        version = await TemplateVersionFactory.create_async(
            template=template,
            template_id=template.id,
            **version_data,
        )

        # Update template's current_version_id
        session: AsyncSession = cls._meta.sqlalchemy_session
        template.current_version_id = version.id
        session.add(template)
        await session.commit()
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
