"""Briefing factory for test data generation."""

from datetime import UTC, datetime

import factory

from src.db.models.briefing import Briefing, BriefingStatus
from src.db.models.conversation_message import ConversationMessage
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

    status = BriefingStatus.IN_PROGRESS
    information_state = factory.Dict({})
    gathered_information = factory.Dict({})
    conversation_summary = None
    completed_at = None

    class Params:
        # Trait: Completed briefing
        completed = factory.Trait(
            status=BriefingStatus.COMPLETED,
            gathered_information=factory.Dict(
                {
                    "property_type": {
                        "value": "Casa",
                        "confidence": 0.95,
                        "source_message_id": None,
                        "extracted_at": None,
                        "corrected": False,
                        "previous_value": None,
                    },
                    "rooms": {
                        "value": "3 quartos",
                        "confidence": 0.92,
                        "source_message_id": None,
                        "extracted_at": None,
                        "corrected": False,
                        "previous_value": None,
                    },
                }
            ),
            information_state=factory.Dict(
                {
                    "property_type": {"status": "collected", "confidence": 0.95},
                    "rooms": {"status": "collected", "confidence": 0.92},
                }
            ),
            completed_at=factory.Faker("past_datetime"),
        )

        # Trait: Cancelled briefing
        cancelled = factory.Trait(status=BriefingStatus.CANCELLED)

        # Trait: In progress (default, explicitly defined for clarity)
        in_progress = factory.Trait(
            status=BriefingStatus.IN_PROGRESS,
            gathered_information=factory.Dict(
                {
                    "property_type": {
                        "value": "Apartamento",
                        "confidence": 0.88,
                        "source_message_id": None,
                        "extracted_at": None,
                        "corrected": False,
                        "previous_value": None,
                    }
                }
            ),
            information_state=factory.Dict(
                {"property_type": {"status": "collected", "confidence": 0.88}}
            ),
        )


class ConversationMessageFactory(AsyncSQLAlchemyFactory):
    """Factory for creating ConversationMessage instances."""

    class Meta:
        model = ConversationMessage

    briefing = factory.SubFactory(BriefingFactory)
    briefing_id = factory.LazyAttribute(lambda o: o.briefing.id)

    role = "user"
    content = factory.Faker("sentence")

    extracted_info = None
    ai_metadata = None
    embedding_id = None

    timestamp = factory.LazyFunction(lambda: datetime.now(UTC))

    class Params:
        # Trait: Assistant message with AI metadata
        assistant_message = factory.Trait(
            role="assistant",
            content=factory.Faker("paragraph"),
            ai_metadata=factory.Dict(
                {
                    "intent": "ask_question",
                    "intent_confidence": 0.94,
                    "reasoning": "Gathering project requirements",
                    "decision_type": "ask_question",
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "tokens_used": 245,
                    "processing_time_ms": 850,
                }
            ),
        )

        # Trait: User message with extracted info
        user_with_extraction = factory.Trait(
            role="user",
            extracted_info=factory.Dict(
                {
                    "fields": {"budget": "100000", "timeline": "3 months"},
                    "confidence_scores": {"budget": 0.95, "timeline": 0.88},
                    "extraction_method": "gpt-4o-mini",
                }
            ),
        )
