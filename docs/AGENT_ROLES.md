# Роли и границы агентов

Статус: рабочая модель подготовки и дальнейшей разработки. Пять профилей в одном репозитории; девять строк ниже — области ответственности, а не девять приложений или постоянных ботов.

## Специализированные роли

| Агент | Что делает | Что не делает | Профиль MVP |
|---|---|---|---|
| Product / BA | требования, user stories, MVP scope, правила, acceptance criteria | не пишет production-код | BA |
| Solution Architect | архитектура, БД, API contracts, Ozon integration layer, ADR | не меняет бизнес-требования самостоятельно | Architect |
| Frontend | Next.js, каталог, карточка, корзина, ЛК; UI админки | не обращается к Ozon API напрямую и не принимает финансовые решения | Frontend |
| Backend | API, PostgreSQL, auth, корзина, заказы, bundles | не меняет UI | Backend/Ozon |
| Ozon Integration | Seller/Performance, FBO, остатки, отзывы; Pay/Delivery после contract gate | не пишет core business logic и не выдаёт архив за актуальный API | Backend/Ozon |
| Admin / Analytics | Elton Dashboard, метрики, заказы, возвраты | не вмешивается в storefront | Frontend для admin UI; Backend/Ozon для API/расчётов |
| QA | тест-кейсы, integration/e2e, баги, evidence | не переписывает архитектуру самостоятельно | QA/DevOps |
| DevOps / Security | CI/CD, secrets, deploy, logs, backup, права доступа | не меняет бизнес-логику | QA/DevOps |
| SEO | URL, metadata, schema.org, sitemap, категории | не занимается дизайном | Frontend, с BA review контента |

## Владельцы общих файлов

| Область | Основной владелец | Необходимый review |
|---|---|---|
| PRODUCT, MVP_SCOPE, BUSINESS_RULES | BA | заказчик для новых требований; Architect для последствий |
| ARCHITECTURE, DATABASE, API, DECISIONS | Architect | Backend/Ozon; BA при влиянии на требования |
| OZON_INTEGRATION | Architect для контрактов; Backend/Ozon для фактических результатов spike | QA/DevOps и BA для business impact |
| apps/storefront, apps/admin, packages/ui | Frontend | QA/DevOps; Architect для границ API |
| apps/api, packages/database, packages/ozon, packages/analytics | Backend/Ozon | Architect, QA/DevOps |
| QA, SECURITY, DEPLOYMENT, future CI | QA/DevOps | владелец компонента; Architect для topology |

Профиль с двумя областями назначает одну подзадачу и один набор файлов за раз. Core service и Ozon adapter остаются разными модулями даже при одном исполнителе. Локальные профили не являются GitHub пользователями; CODEOWNERS нельзя заполнять выдуманными аккаунтами.

## Передача результата

Каждая передача включает: цель, requirement IDs, commit документов, контракты, изменённые файлы, проверку с результатом, открытые вопросы и следующий владелец. См. [WORKFLOW](WORKFLOW.md) и шаблон PR.
