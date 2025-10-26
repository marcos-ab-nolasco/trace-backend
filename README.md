# fullstack-next-fast-template

Template fullstack (FastAPI + Next.js) com foco em integrações de IA, pensado para ser customizável e fácil de colocar em produção.

## Stack

- **Backend:** FastAPI (Python 3.11), autenticação JWT, SQLAlchemy assíncrono, Alembic para migrações.
- **Frontend:** Next.js 15 (App Router), React 19, Tailwind CSS, Vitest + Testing Library.
- **Infra:** uv para gerenciar o virtualenv Python, pnpm para o frontend, Docker Compose para orquestração opcional, GitHub Actions para lint + testes.

## Pré-requisitos

- Python 3.11 com `uv` instalado.
- Node.js 20 + `pnpm` 10.
- Postgres e Redis locais (para o modo manual) **ou** Docker Desktop/Podman (para Compose).
- `make`, `docker` e `docker compose` disponíveis no PATH.

## Setup Inicial (após clonar)

1. Crie o ambiente virtual do backend:
   ```bash
   cd app/backend
   uv venv .venv
   uv sync --extra dev
   ```
2. Copie a configuração base: `cp .env.example .env` (ajuste variáveis conforme necessário).
3. Garanta que `app/frontend` tenha o lock atualizado: `pnpm install`.
4. Exponha as variáveis necessárias (`DATABASE_URL`, `REDIS_URL`, chaves de IA etc.) no `.env` raiz. Esse arquivo é lido tanto pelo backend quanto pelos workflows/docker.

### Provedores de IA

- `OPENAI_API_KEY` e `ANTHROPIC_API_KEY` habilitam as integrações com OpenAI e Anthropic, respectivamente. Sem essas chaves, o backend mantém o fluxo local e responde com um aviso indicando que o provedor não está configurado (útil para desenvolvimento offline).
- As opções disponíveis no frontend são carregadas dinamicamente a partir do backend (`GET /chat/providers`), assim você só vê os provedores realmente suportados.

## Desenvolvimento Local (modo manual)

Fluxo atual que sigo no dia a dia:

1. **Terminal 1 – Frontend**
   ```bash
   cd app/frontend
   pnpm dev
   ```
2. **Terminal 2 – Backend**
   ```bash
   source app/backend/.venv/bin/activate
   python app/backend/run.py  # o launch.json do VS Code chama esse script
   ```
3. Postgres e Redis já rodam localmente (fora do projeto). Basta apontar `DATABASE_URL` e `REDIS_URL` no `.env`.
4. Ajuste as portas no `.env` caso já estejam ocupadas. O backend expõe em `BACKEND_PORT=8000` e o frontend em `3000`.

## Desenvolvimento com Docker Compose

Quando preciso validar no Compose, deixo o `.env` com portas distintas (ex.: `8001` / `3001`) e aponto o host para o nome do serviço (`postgres`, `redis`). A partir da raiz do projeto:

```bash
make docker-build   # builda backend + frontend + dependências
make docker-up      # sobe backend, frontend, postgres, redis, etc.
make docker-logs    # acompanha logs agregados
make docker-down    # encerra todos os serviços
```

Esses comandos usam os Dockerfiles de `infrastructure/docker/` e sobrescrevem as conexões com base no `.env` vinculado ao Compose.

## Migrações e Banco de Dados

- Criação de migração:
  ```bash
  cd app/backend
  alembic revision --autogenerate -m "minha_migracao"
  ```
- Aplicação local:
  ```bash
  cd app/backend
  alembic upgrade head
  ```
- Depois de validar localmente, executo os alvos equivalentes no Compose:
  ```bash
  make docker-migrate
  ```

As migrações são criadas/executadas localmente antes de testar no Compose, garantindo que o fluxo funcione com o Postgres real.

## Tipagem (OpenAPI → Frontend)

- O frontend consome tipos gerados automaticamente a partir do schema OpenAPI exposto pelo backend.
- Com o backend rodando (ex.: `python app/backend/run.py` ouvindo em `http://localhost:8000`), execute:
  ```bash
  make generate-types
  ```
  ou diretamente `sh scripts/generate-types.sh`.
- O script baixa `openapi.json` em `app/frontend/types` e atualiza `types/api.ts`. Depois do refresh, basta reiniciar o servidor do Next.js para refletir os tipos.

## Qualidade e Pipeline

Cada branch representa uma feature. O checklist antes de abrir PR é:

1. Desenvolvimento manual funcionando (frontend + backend locais).
2. Revisão rápida de segurança (tokens, permissões, erros controlados).
3. Testes unitários relevantes:
   ```bash
   make test-backend
   make test-frontend
   ```
4. Lint e type-check:
   ```bash
   make lint
   ```
5. Validar Docker Compose se a mudança impactar infra.
6. A branch só é mergeada se a pipeline do GitHub Actions estiver verde.

## Versionamento & Roadmap

- Estratégia de versionar backend, frontend e app de forma independente ainda em avaliação.
- Próximas melhorias: refinar logs, observabilidade/monitoramento e documentar o plano de versionamento.

## Apêndice / Notas

Template em desenvolvimento para aplicações fullstack integradas com IA, feito para ser customizável e facilmente colocado em produção.
