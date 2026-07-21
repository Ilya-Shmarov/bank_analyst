# Source Policy for Bank Data

This file is a permanent project rule for `bank_analyst`. Parser changes, merge logic, JSON exports, Excel reports, and HTML landings must follow it.

## Main Rule

Do not invent, complete, infer, or transfer bank conditions without direct confirmation from an allowed source.

Every user-facing banking fact must have:

- bank;
- concrete tier;
- field;
- final value;
- source URL;
- source type;
- date checked;
- source fragment or raw text;
- reliability status.

If a fact is not found, store `sources.NOT_FOUND` in data and show `sources.NOT_FOUND_AVAILABLE` (`Не найдено в доступных источниках`) to users. Do not fill missing data with assumptions.

Forbidden:

- copying data from another tier;
- copying data from another bank;
- applying general bank text to every tier without explicit source confirmation;
- using Alfa Only facts for A-Club without explicit confirmation;
- using Premium facts for Private without explicit confirmation;
- mixing insurance facts into other benefits;
- treating marketing copy as a tariff fact;
- assigning `включено постоянно` or `опция на выбор` without confirmation;
- hiding source conflicts;
- replacing absent data with an invented value.

## Source Hierarchy

Use sources in this strict order.

The URLs registered in `scanner.sources.AUTHORITATIVE_SOURCE_URLS` are
authoritative. A lower-priority source, aggregator, generic keyword snippet, or
non-authoritative page must never override, block, or hide a value extracted
from an authoritative URL. Such disagreement is kept in provenance and conflict
notes, but the authoritative value remains publishable. Only another
authoritative source or a manually curated fact can create a blocking conflict.

### Priority 1: Official Bank Documents and Pages

Official bank PDFs, tariffs, terms, and product pages are the primary source. If an official source contains the needed value, that value is final.

Registered priority official URLs:

- Sber Premier landing: `https://www.sberbank.com/ru/person/sb_premier_new`
- Sber First landing: `https://www.sberbank.com/ru/person/new_sb1`
- Sber premium service: `https://www.sberbank.ru/common/img/uploaded/files/pdf/tarif_premobsl_06032026.pdf`
- Sber Private Banking: `https://www.sberbank.ru/common/img/uploaded/redirected/private/assets/tariff_sb_pb.pdf`
- Sber Private Banking landing: `https://sberpb.ru/`
- T-Bank Premium: `https://cdn.tbank.ru/static/documents/docs-terms-of-service-premium.pdf`
- T-Bank Private: `https://cdn.tbank.ru/static/documents/docs-terms-of-service-private.pdf`
- T-Bank Premium landing: `https://www.tbank.ru/tinkoff-premium/`
- T-Bank Private landing: `https://www.tbank.ru/private/`
- Ozon Bank Ultra: `https://cdn1.ozone.ru/s3/ob-landing/static/docs/ecom/products/rules/2026.05.18%20-%20Тариф%20Ultra.pdf`
- Ozon Bank products: `https://finance.ozon.ru/products`
- VTB Privilege: `https://www.vtb.ru/media-files/vtb.ru/sitepages/tarify/chastnim-licam/t-priv_pbu.pdf`
- VTB Prime+: `https://private.vtb.ru/media-files/private.vtb.ru/sitepages/promo/new-pu-pm/tarify_praym_plyus_01.10.2025.pdf`
- VTB Privilege landing: `https://www.vtb.ru/privilegia/`
- VTB Prime+ landing: `https://www.vtb.ru/privilegia/paket-prime/`
- Raiffeisen Bank: `https://www.raiffeisen.ru/common/img/uploaded/files/retail/package/tariffs_pakety_uslug.pdf`
- Raiffeisen Premium landing: `https://www.raiffeisen.ru/premium/`
- Gazprombank: `https://www.gazprombank.ru/upload/files/iblock/9ff/1ha4uno7pm7yti3z20ke9bdre727aog7/Tarify-po-predostavleniyu-fizicheskim-litsam-_-klientam-Banka-GPB-servisa-Gazprom-Bonus-_Premium_-_s-27.01.2026_.pdf`
- Gazprombank Premium landing: `https://www.gazprombank.ru/premium/`
- Gazprombank Private landing: `https://www.gazprombank.ru/private/`
- Alfa Only: `https://alfabank.servicecdn.ru/site-upload/c1/65/275/Tariffs_Alfa_Only_Card.pdf`
- Alfa Only landing: `https://alfabank.ru/everyday/package/premium/`
- A-Club landing: `https://alfabank.ru/a-club/`

Other already connected official bank pages and PDFs may be used when they match the concrete product and tier.

### Priority 2: PremiumBanking.info

Use PremiumBanking.info only when the official source is unavailable, does not contain the needed field, does not contain details for the concrete tier, or contains only general tariffs without privilege details.

Registered priority PremiumBanking.info URLs:

- Sber: `https://premiumbanking.info/sber`
- Alfa-Bank: `https://premiumbanking.info/alfabank`
- VTB: `https://premiumbanking.info/vtb`
- Gazprombank: `https://premiumbanking.info/gazprombank`
- Ozon Bank: `https://premiumbanking.info/ozon`
- Raiffeisen Bank: `https://premiumbanking.info/raiffeisen`
- T-Bank: `https://premiumbanking.info/tbank`

Analyze the `Премиальные уровни` section and related level blocks first: level conditions, business lounges, taxi, restaurants, insurance, always-included privileges, selectable options, selection rules, and other privileges.

Do not use reviews, user comments, advertising blocks, FAQ, or news as tariff facts.

### Priority 3: Other Existing Sources

Other project sources are allowed only when priority 1 and priority 2 do not provide the fact. These facts must carry lower reliability and should be surfaced for manual review when needed.

## Fallback Algorithm

For every field:

1. Check the official bank source.
2. If the official source is available and the field is found, use the official value.
3. If the official source is available but the field is missing, check PremiumBanking.info and record that the official source did not contain the field.
4. If the official source is unavailable, record the access error, then check PremiumBanking.info.
5. If priority 1 and priority 2 do not provide the value, check priority 3 sources.
6. If no value is found, store `Не найдено в доступных источниках` for display, add the field to manual review, and do not invent a value.

## Source Conflicts

If an official source and PremiumBanking.info disagree:

- choose the official value;
- do not mix values;
- do not choose silently;
- preserve both values;
- preserve both URLs;
- log the conflict.

The Excel workbook must include or update the `Конфликты источников` sheet with bank, tier, field, official value, official URL, PBI value, PBI URL, selected value, selection reason, and check date where those values are available.

## Strict Tier Binding

Every fact must be tied to a concrete key:

    (bank_id, tier_id, field_id)

Every benefit must be tied to:

    (bank_id, tier_id, benefit_id)

Never merge by bank only. Do not copy data from neighboring levels. Do not apply Private facts to Premium products. Do not assume `applies_to_all_tiers` unless a source explicitly confirms it. If a benefit truly applies to every tier, store `applies_to_all_tiers = true` with source confirmation.

## JSON Is the Source for Landing

The data chain is:

    priority sources -> parsing -> normalization -> comparison_data.json -> sber_vs_banks.html
                                      \-> competitor_analysis.xlsx

The Sber VS HTML landing must take user-facing bank data only from `output/comparison_data.json`. The HTML generator must not read `competitor_analysis.xlsx`, re-fetch sites, parse raw PDFs, invent conditions, merge levels, classify insurance text, create absent privileges, or change the meaning of JSON values.

The Excel workbook is a human-readable report generated from the same scan history; it is not the source of truth for HTML.

If JSON has no value, HTML shows `Не найдено в доступных источниках`.

## Data Categories

Facts must stay in the correct category:

- Условия входа;
- Стоимость обслуживания;
- Бизнес-залы;
- Кэшбэк;
- Вклады / накопительные счета;
- Такси;
- Рестораны;
- Страхование;
- Консьерж;
- Другие привилегии;
- Правила выбора.

Insurance risks must stay only in `Страхование`.

Do not add these to `Другие привилегии`:

- visa risks;
- flight delay or cancellation;
- baggage loss;
- medical insurance expenses;
- skiing;
- snowboarding;
- assistance;
- insured sum;
- trip duration.

The bank option `Здоровье — телемедицина, анализы, исследования` is a bank option, not insurance.

## Benefit Recognition Catalog

The parser may keep a catalog of known privilege and option names, for example `Only Assist`, `Smart Reading`, `SimplePrivé`, `Медицинский консьерж`, `СберПрайм`, or `Okko`.

This catalog is only a recognition aid. It is not an etalon of values, not a source of facts, and not a fallback source. It may be used only to classify and normalize text fragments that were already extracted from an allowed source for a concrete `(bank_id, tier_id, field_id)` key.

The catalog must not:

- create a missing privilege;
- fill `NOT_FOUND`;
- copy a privilege between tiers;
- copy a privilege between Alfa Only and A-Club;
- assign availability, limits, dates, amounts, or included/excluded status;
- override official or PremiumBanking.info text.

If a known privilege name is absent from the allowed source for the concrete tier, the final value remains `sources.NOT_FOUND` or the source-provided value.

## Ambiguous Text

If source text is ambiguous:

- preserve `raw_text`;
- assign status `unknown`;
- add to manual review;
- do not show it as a confirmed fact.

## Source Availability Metadata

For every priority URL, preserve where possible:

- `last_checked_at`;
- HTTP status or fetch result;
- content hash;
- source type;
- parse status;
- parse error;
- number of extracted tiers;
- number of extracted facts.

An unavailable source must not crash the full scan. Continue through fallback.

## Required Tests

The project must keep regression tests for:

- `test_official_source_has_priority`;
- `test_pbi_used_when_official_field_missing`;
- `test_pbi_used_when_official_source_unavailable`;
- `test_no_value_invented_when_sources_empty`;
- `test_every_fact_has_source_url`;
- `test_every_fact_has_tier_id`;
- `test_no_cross_tier_fallback`;
- `test_no_cross_bank_fallback`;
- `test_html_uses_json_only`;
- `test_source_conflict_is_logged`;
- `test_unknown_status_for_ambiguous_fact`;
- `test_insurance_not_in_other_benefits`;
- `test_all_priority_urls_registered`;
- `test_source_priority_order`.

## Publisher Rule

Do not change `publisher.py` or the GitHub Pages publishing mechanism when implementing this policy.
