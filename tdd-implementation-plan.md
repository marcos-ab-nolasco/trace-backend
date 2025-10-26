---

🎯 MILESTONE 0: Modelagem Multitenant & Database Schema

Issue #1: Entidades Multitenant Core (Organization, Architect, EndClient)

TDD Approach:

- RED: Testes para Organization, Architect, EndClient models com relationships, UUIDs, timestamps
- GREEN: Implementar models com SQLAlchemy (Organization 1:N Architect, Architect 1:N EndClient)
- REFACTOR: Adicionar indexes, constraints, validações

Deliverables:

- src/db/models/organization.py (id, name, whatsapp_business_account_id, settings JSONB)
- src/db/models/architect.py (user_id FK, organization_id FK, phone, is_authorized)
- src/db/models/end_client.py (id, architect_id FK, name, phone, metadata JSONB)
- Alembic migration

---

Issue #2: Estender Conversation para Briefings

TDD Approach:

- RED: Testes para novos campos (conversation_type, whatsapp_context, briefing_id FK)
- GREEN: Adicionar campos ao Conversation model existente
- REFACTOR: Criar enums (ConversationType: WEB_CHAT, WHATSAPP_BRIEFING)

Deliverables:

- Modificar src/db/models/conversation.py com campos: conversation_type, end_client_id, briefing_id, whatsapp_context (JSONB)
- Alembic migration

---

🎯 MILESTONE 1: Sistema de Templates de Briefing

Issue #3: Models de Templates com Versionamento

TDD Approach:

- RED: Testes para BriefingTemplate, TemplateVersion, TemplateQuestion models
- GREEN: Implementar models com versionamento (soft delete, version number)
- REFACTOR: Adicionar validação de questões, ordenação

Deliverables:

- src/db/models/briefing_template.py (id, name, category, is_global, architect_id nullable, current_version)
- src/db/models/template_version.py (id, template_id FK, version_number, questions JSONB, created_at)
- Schemas em src/schemas/briefing.py
- Alembic migration

---

Issue #4: CRUD API para Templates

TDD Approach:

- RED: Testes API para listar templates globais, criar template customizado, editar (com versionamento)
- GREEN: Implementar endpoints /api/templates (GET/POST/PUT)
- REFACTOR: Service layer (src/services/template_service.py) com lógica de versionamento

Deliverables:

- src/api/templates.py com endpoints CRUD
- src/services/template_service.py (create, update com auto-versioning, get_active_version)
- Testes em tests/test_templates.py

---

🎯 MILESTONE 2: Integração WhatsApp Cloud API

Issue #5: Models WhatsApp (Account, Message, Session)

TDD Approach:

- RED: Testes para WhatsAppAccount, WhatsAppMessage, WhatsAppSession models
- GREEN: Implementar models com relacionamentos
- REFACTOR: Adicionar enums (MessageStatus, MessageDirection)

Deliverables:

- src/db/models/whatsapp_account.py (id, organization_id FK, phone_number_id, access_token, webhook_verify_token)
- src/db/models/whatsapp_message.py (id, session_id FK, wa_message_id, direction, status, content, timestamp)
- src/db/models/whatsapp_session.py (id, end_client_id FK, phone_number, status)
- Alembic migration

---

Issue #6: Webhook Receiver & Verification

TDD Approach:

- RED: Testes para webhook verification (GET) e message receiver (POST)
- GREEN: Implementar endpoint /api/webhooks/whatsapp com signature validation
- REFACTOR: Middleware para validação de token, logging

Deliverables:

- src/api/whatsapp_webhook.py (GET verification, POST message handler)
- src/services/whatsapp/webhook_handler.py (parse incoming messages)
- Settings: adicionar WHATSAPP_WEBHOOK_VERIFY_TOKEN em core/config.py
- Testes em tests/test_whatsapp_webhook.py

---

Issue #7: Service de Envio de Mensagens

TDD Approach:

- RED: Testes para envio de mensagens via Cloud API (text, template messages)
- GREEN: Implementar WhatsAppService.send_message() com httpx
- REFACTOR: Retry logic, error handling, rate limiting

Deliverables:

- src/services/whatsapp/whatsapp_service.py (send_message, send_template, mark_as_read)
- Integração com WhatsApp Cloud API (Graph API)
- Testes unitários com httpx mock em tests/test_whatsapp_service.py

---

🎯 MILESTONE 3: IA para Interpretação e Orquestração

Issue #8: Extração de Dados via IA (Cliente Final + Template)

TDD Approach:

- RED: Testes para extrair de mensagem do arquiteto: nome cliente, telefone, tipo projeto
- GREEN: Implementar BriefingAIService.extract_client_info() usando AI provider
- REFACTOR: Structured output, validação com Pydantic

Deliverables:

- src/services/briefing/extraction_service.py (extract_client_info, identify_template)
- Prompt engineering para extração estruturada
- Testes com mocked AI responses em tests/test_extraction_service.py

---

Issue #9: Orquestração Conversacional de Briefing

TDD Approach:

- RED: Testes para state machine (próxima pergunta, validar resposta, concluir briefing)
- GREEN: Implementar BriefingOrchestrator com gerenciamento de estado
- REFACTOR: Persistência de estado em Redis, tratamento de interrupções

Deliverables:

- src/services/briefing/orchestrator.py (next_question, process_answer, complete_briefing)
- src/db/models/briefing.py (id, end_client_id FK, template_version_id FK, status, answers JSONB)
- Schemas BriefingCreate, BriefingAnswer em src/schemas/briefing.py
- Alembic migration

---

🎯 MILESTONE 4: Fluxo de Briefing End-to-End

Issue #10: Endpoint para Iniciar Briefing via WhatsApp

TDD Approach:

- RED: Testes para fluxo: arquiteto envia msg → sistema cria/atualiza EndClient → inicia conversa
- GREEN: Implementar endpoint /api/briefings/start-from-whatsapp
- REFACTOR: Transações atômicas, error handling

Deliverables:

- src/api/briefings.py (POST /start-from-whatsapp)
- Integração: ExtractionService → EndClient CRUD → OrchestrationService → WhatsAppService
- Testes de integração em tests/test_briefing_flow.py

---

Issue #11: Persistência de Respostas e Analytics Básico

TDD Approach:

- RED: Testes para salvar respostas, identificar insights extras, calcular métricas
- GREEN: Implementar lógica de save_answer com extração de observações não esperadas
- REFACTOR: Analytics service (tempo médio, taxa de conclusão)

Deliverables:

- src/services/briefing/persistence_service.py (save_answer, extract_unexpected_insights)
- src/db/models/briefing_analytics.py (id, briefing_id FK, metrics JSONB, observations TEXT)
- Alembic migration

---

🎯 MILESTONE 5: Analytics e Relatórios

Issue #12: Métricas e Dashboard Data

TDD Approach:

- RED: Testes para agregação de métricas (briefings por período, tempo médio, etc.)
- GREEN: Implementar queries com SQLAlchemy para analytics
- REFACTOR: Caching com Redis

Deliverables:

- src/services/analytics_service.py (get_architect_metrics, get_template_performance)
- Endpoints em src/api/analytics.py

---

Issue #13: Geração de Relatórios PDF

TDD Approach:

- RED: Testes para geração de PDF com dados do briefing
- GREEN: Implementar PDFReportService usando ReportLab ou WeasyPrint
- REFACTOR: Templates HTML com Jinja2, estilos customizáveis

Deliverables:

- src/services/pdf_report_service.py (generate_briefing_report)
- Template HTML em src/templates/briefing_report.html
- Endpoint GET /api/briefings/{id}/report.pdf
- Testes em tests/test_pdf_report.py
