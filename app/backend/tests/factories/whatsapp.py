"""WhatsApp-related factories for test data generation."""

import factory

from src.db.models.whatsapp_session import SessionStatus, WhatsAppSession
from tests.factories.base import AsyncSQLAlchemyFactory
from tests.factories.briefing import BriefingFactory
from tests.factories.clients import EndClientFactory


class WhatsAppSessionFactory(AsyncSQLAlchemyFactory):
    """Factory for creating WhatsAppSession instances."""

    class Meta:
        model = WhatsAppSession

    end_client = factory.SubFactory(EndClientFactory)
    end_client_id = factory.LazyAttribute(lambda o: o.end_client.id)
    briefing = factory.SubFactory(
        BriefingFactory,
        end_client=factory.SelfAttribute("..end_client"),
    )
    briefing_id = factory.LazyAttribute(lambda o: o.briefing.id if o.briefing else None)
    phone_number = factory.LazyAttribute(lambda o: o.end_client.phone)
    status = SessionStatus.ACTIVE.value
    meta = None

    class Params:
        # Trait: Active session (default)
        active = factory.Trait(status=SessionStatus.ACTIVE.value)

        # Trait: Closed session
        closed = factory.Trait(status=SessionStatus.CLOSED.value)

        # Trait: Expired session
        expired = factory.Trait(status=SessionStatus.EXPIRED.value)

        # Trait: Session without briefing
        no_briefing = factory.Trait(
            briefing=None,
            briefing_id=None,
        )
