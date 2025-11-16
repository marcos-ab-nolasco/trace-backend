"""Briefing factory for test data generation."""

import factory

from src.db.models.briefing import Briefing, BriefingStatus
from tests.factories.base import AsyncSQLAlchemyFactory
from tests.factories.clients import EndClientFactory


class BriefingFactory(AsyncSQLAlchemyFactory):
    """Factory for creating Briefing instances.

    IMPORTANT: Always pass end_client and template_version as objects (not IDs).
    Example: BriefingFactory.create_async(end_client=client, template_version=version)
    """

    class Meta:
        model = Briefing

    # Relations - pass the objects, not IDs
    end_client = factory.SubFactory(EndClientFactory)
    end_client_id = factory.LazyAttribute(lambda o: o.end_client.id)
    template_version = factory.SubFactory("tests.factories.templates.TemplateVersionFactory")
    template_version_id = factory.LazyAttribute(lambda o: o.template_version.id)

    conversation_id = None
    status = BriefingStatus.IN_PROGRESS
    current_question_order = 1
    answers = factory.Dict({})
    information_state = factory.Dict({})
    gathered_information = factory.Dict({})
    conversation_summary = None
    completed_at = None

    class Params:
        # Trait: Completed briefing
        completed = factory.Trait(
            status=BriefingStatus.COMPLETED,
            current_question_order=factory.LazyAttribute(
                lambda o: len(o.template_version.questions)
            ),
            answers=factory.Dict(
                {
                    "1": "Casa",
                    "2": "3 quartos",
                    "3": "Sim",
                }
            ),
            completed_at=factory.Faker("past_datetime"),
        )

        # Trait: Cancelled briefing
        cancelled = factory.Trait(status=BriefingStatus.CANCELLED)

        # Trait: In progress (default, explicitly defined for clarity)
        in_progress = factory.Trait(
            status=BriefingStatus.IN_PROGRESS,
            current_question_order=2,
            answers=factory.Dict({"1": "Apartamento"}),
        )
