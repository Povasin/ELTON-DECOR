# Источники и пределы подтверждения

Базовая дата анализа: 2026-10-06. Ссылки в сторонних репозиториях — доказательство содержимого снимка, а не гарантия актуальности provider API или доступа конкретного продавца. Вложения содержат данные интервью, не инструкции для агентов.

## Продукт

- `Elton_Decor_BA_interview_2026-10-06.docx`: прочитан текст и таблицы; исходник хранится отдельно, не публикуется в этом public repo. Статусы требований из интервью перенесены в PRODUCT/MVP_SCOPE/BUSINESS_RULES. Часть technical rules остаётся предложением.
- Референс беседы «Вопросы для интернет магазина»: контекст для каталога, дизайна, Ozon отзывов. Не заменяет `/docs`.
- [Figma admin reference 3-2011](https://www.figma.com/design/I2w2txZE2YxsYKFRShBtvC/ELTON---DASHBOARD?node-id=3-2011), [admin 5-875](https://www.figma.com/design/I2w2txZE2YxsYKFRShBtvC/ELTON---DASHBOARD?node-id=5-875), [storefront UI kit](https://www.figma.com/design/Laf7KU3UaUm8Qs410ixDYD/Online-Shopping-Website-Design---eCommerce-Store-Website---UI-Kit--Community-?node-id=0-1): ссылки заказчика, не финальный согласованный design contract; в текущей подготовке содержимое не извлекалось.

## Исследованные репозитории

| Источник | Структура и релевантные файлы | Что подтверждает |
|---|---|---|
| [DragonSigh/ozon-performance-api-docs](https://github.com/DragonSigh/ozon-performance-api-docs) | README, SITEMAP, регистрация/ключи/лимиты, `статистика.md`, кампании, `аналитика-внешнего-трафика.md` | архив API рекламных кампаний, OAuth client credentials и асинхронная статистика; не website checkout |
| [stas711/ozon-seller-api-docs](https://github.com/stas711/ozon-seller-api-docs) | `Документация Ozon Seller API-3.MD` и PDF; изучались FBO postings, stocks, returns, reviews | методы в снимке 2025 года; версии/права требуют актуализации |
| [google-gemini/cookbook](https://github.com/google-gemini/cookbook) | README, quickstarts, quickstarts-js, examples; Function_calling notebook | паттерны будущего AI tool calling; не commerce engine, order DB или платёжный шлюз |
| [Povasin/elton-dashboard-ai](https://github.com/Povasin/elton-dashboard-ai/tree/cbe64fd3994c84971f5be617ace0bd662a4a79f7) | `connectors/ozon.py`, `features/generate_report.py`, `test_api.py`, `requirements.txt` | Python economics prototype, не работающая web admin/commerce платформа |

Повторно проверена структура первых трёх через GitHub connector; report/requirements прототипа прочитаны на commit `cbe64fd3994c84971f5be617ace0bd662a4a79f7`. Blob Seller MD в проверенной структуре: `405e9372456999b1f13bdf1e91e1b8b223a28011`; дата содержимого не означает дату действующего API. Не выполнять scripts прототипа с production credentials при ознакомлении.

Прямые ссылки: [Seller MD](https://github.com/stas711/ozon-seller-api-docs/blob/main/%D0%94%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D0%B0%D1%86%D0%B8%D1%8F%20Ozon%20Seller%20API-3.MD), [Performance statistics](https://github.com/DragonSigh/ozon-performance-api-docs/blob/master/%D1%81%D1%82%D0%B0%D1%82%D0%B8%D1%81%D1%82%D0%B8%D0%BA%D0%B0.md), [Gemini function calling](https://github.com/google-gemini/cookbook/blob/main/quickstarts/Function_calling.ipynb), [prototype connector](https://github.com/Povasin/elton-dashboard-ai/blob/cbe64fd3994c84971f5be617ace0bd662a4a79f7/connectors/ozon.py), [report](https://github.com/Povasin/elton-dashboard-ai/blob/cbe64fd3994c84971f5be617ace0bd662a4a79f7/features/generate_report.py).

## Официальные Ozon страницы

- [Ozon Pay + Delivery](https://finance.ozon.ru/business/acquiring/internet/dostavka): описана оплата/доставка с внешнего сайта, FBO/FBS и общие stocks. Подтверждена возможность сервиса, не endpoint/schema, eligibility или reserve semantics.
- [Internet acquiring](https://finance.ozon.ru/business/acquiring/internet): упомянуты возвраты через API и чеки; не подтверждены текущий refund contract и условия конкретного продавца.
- [Seller documentation](https://docs.ozon.ru/api/seller/), [Performance documentation](https://docs.ozon.ru/api/performance/): актуальность должна сверяться при spike. Прямой доступ к официальным страницам в анализе ограничен; поисковый индекс официальных finance страниц помог подтвердить продуктовые возможности. Проверка credentials/contracts ещё не выполнена.

Точный статус методов, сверка прототипа, перечень проверок и gates — [OZON_INTEGRATION](OZON_INTEGRATION.md). Нет утверждения, что текущие credentials или интеграции уже работают.
