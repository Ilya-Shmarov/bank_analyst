# -*- coding: utf-8 -*-
"""
Извлечение структурированных данных из HTML.

Базовый механизм — GenericParser: превращает страницу в текст и по
ключевым словам каждого поля вытаскивает релевантные фрагменты-цитаты.
Мы сознательно храним цитаты из источника, а не "додуманные" значения:
если по полю ничего не нашлось — ставим "не найдено" (см. ограничения ТЗ).

Для конкретного банка можно зарегистрировать специализированный парсер:
    PARSER_REGISTRY["tbank"] = TBankParser()
— тогда ядро трогать не нужно.
"""

import re

from bs4 import BeautifulSoup

from scanner.sources import (
    BANK_FIELDS,
    LIFESTYLE_BANK_OVERLAP_JOBS,
    LIFESTYLE_FIELDS,
    NOT_FOUND,
)

# Максимум фрагментов на поле и максимальная длина одного фрагмента
MAX_SNIPPETS = 3
MAX_SNIPPET_LEN = 300
MAX_VALUE_LEN = 450


def normalize_text(text: str) -> str:
    """Чистим неразрывные пробелы и битые entity вида '&nbsp' без ';'."""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")
                  .replace("&nbsp;", " ").replace("&nbsp", " ")).strip()


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    lines = [normalize_text(ln) for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


def _split_sentences(text: str) -> list:
    # Грубое разбиение: по предложениям и по строкам вёрстки
    chunks = re.split(r"(?<=[.!?])\s+|\n", text)
    return [c.strip() for c in chunks if len(c.strip()) >= 15]


def extract_snippets(text: str, keywords: list) -> str:
    """Возвращает до MAX_SNIPPETS фрагментов текста, содержащих ключевые слова."""
    sentences = _split_sentences(text)
    found = []
    seen = set()
    lowered_keywords = [k.lower() for k in keywords]
    for sentence in sentences:
        low = sentence.lower()
        if any(k in low for k in lowered_keywords):
            snippet = sentence[:MAX_SNIPPET_LEN]
            key = snippet.lower()
            if key not in seen:
                seen.add(key)
                found.append(snippet)
        if len(found) >= MAX_SNIPPETS:
            break
    return " | ".join(found) if found else NOT_FOUND


class GenericParser:
    """Извлечение по ключевым словам. Подходит как fallback для любого источника."""

    def parse(self, html: str, tier: dict, bank: dict) -> dict:
        text = html_to_text(html)
        fields = LIFESTYLE_FIELDS if bank["type"] == "lifestyle" else BANK_FIELDS
        result = {}
        for field_id, spec in fields.items():
            result[field_id] = extract_snippets(text, spec["keywords"])

        if bank["type"] == "lifestyle":
            result["bank_overlap"] = self._detect_overlaps(result)
        return result

    @staticmethod
    def _detect_overlaps(result: dict) -> str:
        """Пересечения с банковскими привилегиями: перечисляем джобы,
        по которым подписка реально что-то предлагает (поле не пустое)."""
        overlaps = [
            job_desc
            for field_id, job_desc in LIFESTYLE_BANK_OVERLAP_JOBS.items()
            if result.get(field_id) and result[field_id] != NOT_FOUND
        ]
        return "; ".join(overlaps) if overlaps else NOT_FOUND


class PremiumBankingInfoParser:
    """Структурированный парсер страниц уровня на premiumbanking.info.

    Страницы устроены как definition list (dt = название атрибута,
    dd = значение). Маппим подписи dt на наши поля по ключевым словам подписи;
    не распознанные подписи складываем в 'Прочее', чтобы не терять данные.
    """

    # (маркеры в подписи dt) -> field_id; проверяются по порядку
    LABEL_MAP = [
        # "ценность" — раньше "страхов": подпись "Ценность без БЗ и страховки"
        # должна попадать в оценку ценности, а не в страхование
        (("ценность",), "aggregator_value"),
        (("бизнес-зал",), "lounge_access"),
        (("ресторан", "такси", "трансфер", "кафе"), "taxi_restaurants"),
        (("страхов",), "insurance"),
        (("кэшбэк", "кешбэк", "бонус"), "cashback"),
        (("вклад", "накопительн", "ставк"), "deposits"),
        (("консьерж",), "concierge"),
        (("авто",), "auto"),
        (("привилегии на выбор", "опци"), "addons"),
        (("другие привилегии", "прочие привилегии"), "ecosystem"),
        (("услови", "остатк", "учет", "оборот"), "entry_conditions"),
        (("пакет", "позиционир"), "positioning"),
    ]
    SKIP_LABELS = ("брокер", "описание на сайте")

    def parse(self, html: str, tier: dict, bank: dict) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        result = {field_id: NOT_FOUND for field_id in BANK_FIELDS}

        # Заголовок уровня (h1/h3) — самое точное позиционирование
        h1 = soup.find("h1")
        h3 = h1.find_next("h3") if h1 else None
        title_parts = [normalize_text(h.get_text(" ", strip=True))
                       for h in (h1, h3) if h]
        if title_parts:
            result["positioning"] = " — ".join(title_parts)[:MAX_VALUE_LEN]

        dl_found = False
        for dl in soup.find_all("dl"):
            for dt in dl.find_all("dt"):
                dd = dt.find_next_sibling("dd")
                if dd is None:
                    continue
                label = normalize_text(dt.get_text(" ", strip=True))
                value = normalize_text(dd.get_text(" | ", strip=True))
                if not label or not value:
                    continue
                dl_found = True
                self._assign(result, label, value)

        # Стоимость обслуживания часто указана внутри условий ("... ₽ в мес")
        if result["service_cost"] == NOT_FOUND and result["entry_conditions"] != NOT_FOUND:
            fee = re.search(r"\d[\d\s]*₽ в мес", result["entry_conditions"])
            if fee:
                result["service_cost"] = fee.group(0)

        if dl_found:
            self._extract_embedded(result, html_to_text(html))
        return result

    # Детали, которые ПБИ прячет внутри сводных блоков («Другие привилегии»
    # и т.п.) — вытаскиваем в профильные поля, чтобы они не терялись
    EMBEDDED_RULES = [
        # консьерж с названием сервиса: "консьерж Aspire", "Консьерж Pb Service"
        ("concierge", r"консьерж(?:-сервис)?\s+[A-Za-zА-ЯЁ][\w .]{1,30}"),
        # повышенный курс обмена бонусов
        ("cashback", r"обмен \d+ бонус\w*[^;|]{0,60}"),
        # опция «Авто» с составом
        ("auto", r"опция «Авто»[^)]{0,140}\)"),
        # карточные условия: металл, лимиты переводов/снятия, выпуск
        ("card_terms", r"металлическ\w{0,4} (?:сбер)?карт\w{0,4}[^;|.]{0,80}"),
        ("card_terms", r"лимит\w{0,3}[^;|.]{0,25}(?:перевод|снят)\w*[^;|.]{0,50}"),
        ("card_terms", r"перевод\w{0,3} (?:без комиссии |до )[^;|.]{0,60}"),
        ("card_terms", r"(?:выпуск|перевыпуск) карт\w{0,3}[^;|.]{0,60}"),
    ]

    def _extract_embedded(self, result: dict, text: str):
        for field_id, pattern in self.EMBEDDED_RULES:
            matches = []
            seen = set()
            for m in re.finditer(pattern, text, re.IGNORECASE):
                snippet = normalize_text(m.group(0))
                if snippet.lower() not in seen:
                    seen.add(snippet.lower())
                    matches.append(snippet)
                if len(matches) >= 2:
                    break
            if matches:
                joined = " ; ".join(matches)[:MAX_VALUE_LEN]
                if result[field_id] == NOT_FOUND:
                    result[field_id] = joined
                elif joined.lower() not in result[field_id].lower():
                    result[field_id] = (result[field_id] + " ; " + joined)[:MAX_VALUE_LEN * 2]

        # Отсутствие услуги НЕ выводим из молчания источника: страница уровня
        # ПБИ не всегда перечисляет консьерж и т.п. (ложные «нет» были у
        # Т-Банка и Альфы). Отсутствие фиксируется только верифицированной
        # записью в scanner/curated.py (значение «—» с обоснованием).

    def _assign(self, result: dict, label: str, value: str):
        low = label.lower()
        if any(m in low for m in self.SKIP_LABELS):
            return
        for markers, field_id in self.LABEL_MAP:
            if any(m in low for m in markers):
                break
        else:
            field_id = "other_notes"
            value = f"{label}: {value}"
        entry = value[:MAX_VALUE_LEN]
        if result[field_id] == NOT_FOUND:
            result[field_id] = entry
        else:
            result[field_id] = (result[field_id] + " ; " + entry)[:MAX_VALUE_LEN * 2]


# Реестр специализированных парсеров: bank_id -> parser.
PARSER_REGISTRY = {}

_default_parser = GenericParser()
_pbi_parser = PremiumBankingInfoParser()


def parse_source(html: str, tier: dict, bank: dict, source_id: str,
                 source_url: str = "") -> tuple:
    """Парсит один источник тира. Возвращает (fields, quality):
    quality="structured" — структурированный парсер (dt/dd ПБИ),
    quality="snippet" — цитаты по ключевым словам (GenericParser)."""
    if bank["type"] != "lifestyle" and (
            source_id == "pbi" or "premiumbanking.info" in source_url):
        return _pbi_parser.parse(html, tier, bank), "structured"
    parser = PARSER_REGISTRY.get(bank["id"], _default_parser)
    return parser.parse(html, tier, bank), "snippet"


def empty_result(bank: dict) -> dict:
    """Результат для недоступного источника: все поля 'не найдено'."""
    fields = LIFESTYLE_FIELDS if bank["type"] == "lifestyle" else BANK_FIELDS
    result = {field_id: NOT_FOUND for field_id in fields}
    if bank["type"] == "lifestyle":
        result["bank_overlap"] = NOT_FOUND
    return result
