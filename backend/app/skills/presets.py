"""Skill presets — maps old profile keys to granular skill keys."""

PRESETS = {
    "web": ["react_nextjs", "tailwind_css", "typescript_strict"],
    "backend": ["fastapi_backend", "postgresql_data", "celery_async"],
    "fullstack": ["react_nextjs", "typescript_strict", "fastapi_backend", "postgresql_data", "api_contract_first"],
    "devops": ["docker_k8s", "terraform_iac", "github_actions_ci"],
    "mobile_ios": ["swift_swiftui"],
    "mobile_android": ["kotlin_compose"],
    "data": ["dbt_sql", "airflow_pipelines", "snowflake_warehouse"],
}

# All curated skills with their data — used by the seed migration
SEED_SKILLS = [
    {
        "key": "react_nextjs",
        "name": "React & Next.js",
        "description": "React components, Next.js App Router, server components, data fetching",
        "category": "frontend",
        "stack_chips": ["React", "Next.js"],
        "system_prompt": (
            "You are an expert in React and Next.js 14 App Router.\n\n"
            "Standards:\n"
            "- Accessibility: semantic HTML, ARIA labels, keyboard navigation\n"
            "- Performance: minimise LCP, eliminate CLS, lazy-load images\n"
            "- Component composition: small focused components with explicit props\n"
            "- Data fetching: Next.js fetch with cache/revalidate. Never fetch in useEffect when a server component can do it\n"
            "- Error boundaries: wrap async client components. Handle loading and error states explicitly\n"
            "- State: prefer React Server Components. Use client state only when interactivity requires it"
        ),
        "allowed_extensions": [".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".json"],
        "allowed_dirs": ["frontend/", "src/", "components/", "pages/", "app/", "hooks/", "utils/", "lib/", "features/"],
        "context_priorities": [".tsx", ".ts", ".jsx"],
    },
    {
        "key": "tailwind_css",
        "name": "Tailwind CSS",
        "description": "Tailwind utility classes, responsive design, design tokens",
        "category": "frontend",
        "stack_chips": ["Tailwind"],
        "system_prompt": (
            "Tailwind CSS standards:\n"
            "- Use utility classes only. No inline styles unless the value is dynamic\n"
            "- Responsive: mobile-first with sm/md/lg breakpoints\n"
            "- Dark mode: use dark: variant consistently\n"
            "- Avoid @apply — prefer utility classes in JSX"
        ),
        "allowed_extensions": [".ts", ".tsx", ".jsx", ".css", ".html"],
        "allowed_dirs": ["frontend/", "src/", "components/", "styles/", "app/"],
        "context_priorities": [".tsx", ".css"],
    },
    {
        "key": "typescript_strict",
        "name": "TypeScript (Strict)",
        "description": "Type safety, zero any types, explicit return types",
        "category": "frontend",
        "stack_chips": ["TypeScript"],
        "system_prompt": (
            "TypeScript standards:\n"
            "- Zero `any` types. Use `unknown` and narrow with type guards\n"
            "- Explicit return types on all exported functions and hooks\n"
            "- Use discriminated unions for state machines\n"
            "- Prefer `interface` for object shapes, `type` for unions/intersections"
        ),
        "allowed_extensions": [".ts", ".tsx", ".js", ".jsx", ".json"],
        "allowed_dirs": ["frontend/", "src/", "lib/", "utils/", "types/"],
        "context_priorities": [".ts", ".tsx"],
    },
    {
        "key": "fastapi_backend",
        "name": "FastAPI Backend",
        "description": "FastAPI endpoints, async patterns, request validation, error handling",
        "category": "backend",
        "stack_chips": ["Python", "FastAPI"],
        "system_prompt": (
            "You are an expert in Python and FastAPI.\n\n"
            "Standards:\n"
            "- Idempotency: all write endpoints safe to call twice. Use upserts over inserts\n"
            "- Error handling: raise domain-specific exceptions with clear messages. Structured error responses\n"
            "- Async correctness: async/await throughout. Never block inside async functions\n"
            "- Security: validate all input at the API boundary. Parameterise all SQL\n"
            "- Secrets: never log credentials or PII. Environment variables only"
        ),
        "allowed_extensions": [".py", ".toml", ".cfg", ".yaml", ".yml", ".json", ".env.example"],
        "allowed_dirs": ["app/", "backend/", "api/", "schemas/", "services/", "tests/"],
        "context_priorities": [".py"],
    },
    {
        "key": "postgresql_data",
        "name": "PostgreSQL",
        "description": "Schema design, migrations, query optimisation, indexes",
        "category": "backend",
        "stack_chips": ["PostgreSQL"],
        "system_prompt": (
            "PostgreSQL standards:\n"
            "- Schema migrations: never drop/rename columns in one migration. Add nullable first, backfill, then constrain\n"
            "- Query optimisation: index every FK and every WHERE column. Avoid N+1 — use joins or eager loading\n"
            "- Always include a migration for schema changes. Never modify models without corresponding Alembic migration"
        ),
        "allowed_extensions": [".py", ".sql", ".yaml", ".yml"],
        "allowed_dirs": ["models/", "alembic/", "migrations/", "backend/"],
        "context_priorities": [".py", ".sql"],
    },
    {
        "key": "celery_async",
        "name": "Celery & Redis",
        "description": "Background tasks, task queues, beat scheduling",
        "category": "backend",
        "stack_chips": ["Celery", "Redis"],
        "system_prompt": (
            "Celery standards:\n"
            "- Use Celery for anything >500ms. Store task state in DB, not just Celery\n"
            "- Tasks must be idempotent — safe to retry\n"
            "- Use beat scheduler for recurring tasks, not sleep loops"
        ),
        "allowed_extensions": [".py", ".yaml", ".yml"],
        "allowed_dirs": ["backend/", "app/", "workers/", "tasks/", "pipeline/"],
        "context_priorities": [".py"],
    },
    {
        "key": "api_contract_first",
        "name": "API Contract First",
        "description": "End-to-end type safety, API contracts, frontend-backend consistency",
        "category": "fullstack",
        "stack_chips": ["API Design"],
        "system_prompt": (
            "Full-stack API standards:\n"
            "- API contract first: define endpoint shape before writing either side\n"
            "- End-to-end type safety: response shapes must match frontend TypeScript interfaces\n"
            "- Naming: snake_case on Python, camelCase in TypeScript, mapped at the boundary\n"
            "- CORS: known origins only. All routes behind auth middleware\n"
            "- Avoid duplication: if logic runs on both sides, put it on the server"
        ),
        "allowed_extensions": [".ts", ".tsx", ".py", ".json", ".yaml"],
        "allowed_dirs": ["frontend/", "backend/", "app/", "api/", "lib/", "schemas/"],
        "context_priorities": [".ts", ".py"],
    },
    {
        "key": "docker_k8s",
        "name": "Docker & Kubernetes",
        "description": "Containerisation, orchestration, Helm charts",
        "category": "devops",
        "stack_chips": ["Docker", "Kubernetes"],
        "system_prompt": (
            "Docker/K8s standards:\n"
            "- Immutable infrastructure: never SSH to make changes. All changes through code\n"
            "- Rollback safety: every deployment needs a tested rollback path\n"
            "- Health checks and readiness probes on every service\n"
            "- Security scanning: image vulnerability scanning in CI"
        ),
        "allowed_extensions": [".yaml", ".yml", ".json", ".sh", ".dockerfile", "Dockerfile", ".toml"],
        "allowed_dirs": ["docker/", "k8s/", "helm/", "charts/", "deploy/", "infra/"],
        "context_priorities": [".yaml", ".yml", "Dockerfile"],
    },
    {
        "key": "terraform_iac",
        "name": "Terraform",
        "description": "Infrastructure as code, state management, modules",
        "category": "devops",
        "stack_chips": ["Terraform"],
        "system_prompt": (
            "Terraform standards:\n"
            "- Least-privilege IAM: only the permissions needed. No wildcard actions\n"
            "- Idempotency: all scripts safely re-runnable. Use plan output to gate applies\n"
            "- Cost awareness: tag every resource. Use spot instances where tolerable\n"
            "- State: remote backend with locking. Never edit state files manually"
        ),
        "allowed_extensions": [".tf", ".tfvars", ".json"],
        "allowed_dirs": ["infra/", "terraform/", "modules/"],
        "context_priorities": [".tf"],
    },
    {
        "key": "github_actions_ci",
        "name": "GitHub Actions CI",
        "description": "CI/CD pipelines, workflow automation",
        "category": "devops",
        "stack_chips": ["GitHub Actions"],
        "system_prompt": (
            "GitHub Actions standards:\n"
            "- Secret management: use repository/org secrets, never hardcode\n"
            "- Caching: cache dependencies (node_modules, pip) to speed up builds\n"
            "- Matrix builds for cross-platform/version testing\n"
            "- Fail fast on security scans and linting"
        ),
        "allowed_extensions": [".yaml", ".yml", ".json", ".sh"],
        "allowed_dirs": [".github/", "scripts/", "ci/"],
        "context_priorities": [".yaml", ".yml"],
    },
    {
        "key": "swift_swiftui",
        "name": "Swift & SwiftUI",
        "description": "iOS app development, SwiftUI, Combine, navigation",
        "category": "mobile",
        "stack_chips": ["Swift", "SwiftUI"],
        "system_prompt": (
            "Swift/SwiftUI standards:\n"
            "- Use SwiftUI for all new screens. UIKit only for unavoidable system APIs\n"
            "- MVVM architecture: ObservableObject viewmodels, @Published properties\n"
            "- Structured concurrency: async/await over completion handlers\n"
            "- Accessibility: VoiceOver labels on all interactive elements"
        ),
        "allowed_extensions": [".swift", ".json", ".plist"],
        "allowed_dirs": ["ios/", "Sources/", "Views/", "Models/", "ViewModels/"],
        "context_priorities": [".swift"],
    },
    {
        "key": "kotlin_compose",
        "name": "Kotlin & Jetpack Compose",
        "description": "Android app development, Compose UI, ViewModels",
        "category": "mobile",
        "stack_chips": ["Kotlin", "Jetpack Compose"],
        "system_prompt": (
            "Kotlin/Compose standards:\n"
            "- Jetpack Compose for all new UI. XML layouts only for legacy\n"
            "- MVVM with ViewModel + StateFlow/SharedFlow\n"
            "- Coroutines for async: viewModelScope for UI, Dispatchers.IO for I/O\n"
            "- Room for local persistence with proper migration support"
        ),
        "allowed_extensions": [".kt", ".kts", ".xml", ".json"],
        "allowed_dirs": ["android/", "app/src/", "ui/", "data/", "domain/"],
        "context_priorities": [".kt", ".kts"],
    },
    {
        "key": "dbt_sql",
        "name": "dbt & SQL",
        "description": "Data transformations, SQL modelling, testing",
        "category": "data",
        "stack_chips": ["dbt", "SQL"],
        "system_prompt": (
            "dbt/SQL standards:\n"
            "- Naming: staging models prefix stg_, intermediate int_, marts no prefix\n"
            "- Materialisation: views for staging, tables for marts, incremental for large\n"
            "- Testing: not_null + unique on every primary key. Referential integrity tests\n"
            "- Documentation: every model and column documented in schema.yml"
        ),
        "allowed_extensions": [".sql", ".yml", ".yaml", ".py"],
        "allowed_dirs": ["models/", "dbt/", "transforms/", "macros/", "tests/"],
        "context_priorities": [".sql", ".yml"],
    },
    {
        "key": "airflow_pipelines",
        "name": "Apache Airflow",
        "description": "DAG design, task dependencies, scheduling",
        "category": "data",
        "stack_chips": ["Airflow"],
        "system_prompt": (
            "Airflow standards:\n"
            "- DAGs must be idempotent and re-runnable for any execution date\n"
            "- Use TaskFlow API (@task decorator) for Python tasks\n"
            "- Connections and variables stored in Airflow, not hardcoded\n"
            "- Keep DAG files lightweight — import heavy logic from separate modules"
        ),
        "allowed_extensions": [".py", ".yaml", ".yml"],
        "allowed_dirs": ["dags/", "plugins/", "airflow/"],
        "context_priorities": [".py"],
    },
    {
        "key": "snowflake_warehouse",
        "name": "Snowflake",
        "description": "Data warehouse, cost optimisation, roles",
        "category": "data",
        "stack_chips": ["Snowflake"],
        "system_prompt": (
            "Snowflake standards:\n"
            "- Cost: use transient tables for staging. Set auto-suspend on warehouses\n"
            "- Security: role-based access. Never share credentials across environments\n"
            "- Clustering keys for large tables queried by specific columns\n"
            "- Time travel: use for recovery, not as a backup strategy"
        ),
        "allowed_extensions": [".sql", ".py", ".yaml", ".yml"],
        "allowed_dirs": ["models/", "dbt/", "warehouse/", "sql/"],
        "context_priorities": [".sql"],
    },
]
