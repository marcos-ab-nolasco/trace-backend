"""AI-powered extraction service for client information and template identification."""

import logging
from uuid import UUID

from src.db.models.briefing_template import BriefingTemplate
from src.schemas.briefing import ExtractedClientInfo, TemplateRecommendation
from src.services.ai.base import BaseAIService

logger = logging.getLogger(__name__)


class ExtractionService:
    """Service for extracting structured information using AI."""

    def __init__(self, ai_service: BaseAIService):
        """Initialize extraction service with AI provider.

        Args:
            ai_service: AI service instance (OpenAI, Anthropic, etc.)
        """
        self.ai_service = ai_service

    async def extract_client_info(
        self, message: str, architect_id: UUID, model: str = "gpt-4o-mini"
    ) -> ExtractedClientInfo:
        """Extract client information from architect message.

        Args:
            message: Raw message from architect containing client info
            architect_id: ID of the architect making the request
            model: AI model to use for extraction

        Returns:
            ExtractedClientInfo with extracted name, phone, project type, and confidence

        Raises:
            HTTPException: If AI service fails or returns invalid data
        """
        system_prompt = """Você é um assistente especializado em extrair informações de clientes
de mensagens de arquitetos brasileiros.

Sua tarefa é identificar:
1. Nome completo do cliente
2. Número de telefone (formato brasileiro: DDD + número)
3. Tipo de projeto (reforma, construcao, residencial, comercial, incorporacao)

REGRAS IMPORTANTES:
- Se alguma informação não estiver presente, retorne null para esse campo
- Normalize telefones removendo formatação: (11) 98765-4321 → 11987654321
- Se tiver +55 no início, mantenha: +55 11 98765-4321 → 5511987654321
- Para project_type, use EXATAMENTE um destes valores: reforma, construcao, residencial, comercial, incorporacao
- Avalie a confiança (0.0-1.0) baseado na clareza das informações
- Confiança alta (>0.9) apenas se todos os dados estiverem claramente presentes
- Confiança média (0.7-0.9) se faltarem alguns dados
- Confiança baixa (<0.7) se a mensagem for muito ambígua"""

        user_prompt = f"""Extraia as informações do cliente desta mensagem:

"{message}"

Retorne um JSON com: name (string ou null), phone (string ou null),
project_type (string ou null), confidence (float 0.0-1.0), raw_text (string da mensagem original)."""

        result = await self.ai_service.generate_structured_response(
            prompt=user_prompt,
            response_model=ExtractedClientInfo,
            model=model,
            system_prompt=system_prompt,
        )

        logger.info(
            f"Extracted client info: name={result.name}, phone={result.phone}, "
            f"type={result.project_type}, confidence={result.confidence}"
        )

        return result

    async def identify_template(
        self,
        project_description: str,
        available_templates: list[BriefingTemplate],
        model: str = "gpt-4o-mini",
    ) -> TemplateRecommendation:
        """Identify the most appropriate template for a project.

        Args:
            project_description: Description of the project (from extracted client info)
            available_templates: List of available templates to choose from
            model: AI model to use for identification

        Returns:
            TemplateRecommendation with template ID, category, confidence, and reasoning

        Raises:
            ValueError: If no templates are available
            HTTPException: If AI service fails
        """
        if not available_templates:
            raise ValueError("No templates available for identification")

        # Build template context for AI
        template_context = "Templates disponíveis:\n\n"
        for template in available_templates:
            template_context += f"- ID: {template.id}\n"
            template_context += f"  Nome: {template.name}\n"
            template_context += f"  Categoria: {template.category}\n"
            if template.description:
                template_context += f"  Descrição: {template.description}\n"
            template_context += "\n"

        system_prompt = """Você é um assistente especializado em classificar projetos de arquitetura
e recomendar templates de briefing apropriados.

Categorias disponíveis:
- reforma: Reformas e renovações de espaços existentes
- residencial: Construção de residências novas (casas, sobrados)
- comercial: Estabelecimentos comerciais (lojas, escritórios, restaurantes)
- incorporacao: Projetos de incorporação com múltiplas unidades (prédios, condomínios)

REGRAS:
- Analise a descrição do projeto cuidadosamente
- Escolha o template que melhor se adequa ao tipo de projeto
- Se a descrição mencionar "reforma", use template de reforma
- Se mencionar "construção nova" ou "casa nova", use residencial
- Se mencionar "loja" ou "comercial", use comercial
- Se mencionar "prédio" ou "múltiplas unidades", use incorporacao
- Avalie confiança baseado na clareza da descrição
- Forneça reasoning explicando sua escolha"""

        user_prompt = f"""Baseado nesta descrição de projeto:

"{project_description}"

{template_context}

Identifique o template mais apropriado e retorne um JSON com:
- template_id (UUID do template escolhido)
- category (categoria do template)
- confidence (float 0.0-1.0)
- reasoning (explicação da escolha)"""

        result = await self.ai_service.generate_structured_response(
            prompt=user_prompt,
            response_model=TemplateRecommendation,
            model=model,
            system_prompt=system_prompt,
        )

        logger.info(
            f"Identified template: id={result.template_id}, category={result.category}, "
            f"confidence={result.confidence}"
        )

        return result
