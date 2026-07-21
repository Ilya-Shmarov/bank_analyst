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
MAX_STRUCTURED_VALUE_LEN = 900


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
        (("такси", "трансфер"), "taxi"),
        (("ресторан", "кафе"), "restaurants"),
        (("страхов",), "insurance"),
        (("кэшбэк", "кешбэк", "бонус"), "cashback"),
        (("вклад", "накопительн", "ставк"), "deposits"),
        (("консьерж",), "concierge"),
        (("перевод", "платеж"), "transfers_payments"),
        (("снятие", "налич"), "cash_withdrawal"),
        (("supreme",), "supreme"),
        (("авто",), "auto"),
        (("всегда включ", "постоянно включ"), "always_included_options"),
        (("привилегии на выбор", "опци", "на выбор"), "selectable_options"),
        (("другие привилегии", "прочие привилегии"), "ecosystem"),
        (("услови", "остатк", "учет", "оборот"), "entry_conditions"),
        (("пакет", "позиционир"), "positioning"),
    ]
    SKIP_LABELS = ("брокер", "описание на сайте", "рейтинг", "отзыв")
    OVERVIEW_HEADINGS = (
        "Сбер", "Альфа-Банк", "ВТБ", "Газпромбанк", "Ozon банк",
        "Озон банк", "Райффайзен", "Т-Банк",
    )
    OVERVIEW_STOP_PREFIXES = (
        "Посещение бизнес-залов", "Компенсация ресторанов",
        "Компенсация такси", "Как работает", "Таблица уровней",
        "New Вопросы", "Вопросы и ответы", "Последние изменения",
        "Список премиальных", "Отзывы", "Оценить ",
    )
    OVERVIEW_FIELD_LABELS = (
        "Привилегии на выбор", "Всегда включено:", "Дополнительно на выбор:",
        "Доступно на выбор:", "Преференции", "Бизнес-залы", "Рестораны",
        "Такси", "Трансфер", "Страховка", "Переводы", "Платежи",
        "Снятие наличных", "Supreme", "Другие привилегии",
    )
    # Semantic hints for overview pages where the heading is repeated for
    # several thresholds. If a hinted block is absent, the source contributes
    # NOT_FOUND and the level-specific PBI URL remains the fallback.
    OVERVIEW_TIER_HINTS = {
        "alfa_only_1": (("альфа-банк - alfa only", "2990 ₽ в мес"),),
        "alfa_only_2": (("альфа-банк - alfa only", "за 3 млн ₽"),),
        "alfa_only_3": (("альфа-банк - alfa only", "за 6 млн ₽"),),
        "alfa_only_4": (("альфа-банк - alfa only", "за 12 млн ₽"),),
        "alfa_aclub": (("альфа-банк - а-клуб",), ("альфа-банк - a-club",)),
        "vtb_privilege_1": (("втб - привилегия", "3990 ₽ в мес"),),
        "vtb_privilege_2": (("втб - привилегия", "за 2.5 млн ₽"),),
        "vtb_privilege_3": (("втб - привилегия", "за 6 млн ₽"),),
        "vtb_privilege_4": (("втб - привилегия", "за 10 млн ₽"),),
        "vtb_prime_5": (("втб - прайм+", "16667 ₽ в мес"),),
        "vtb_prime_6": (("втб - прайм+", "за 15 млн ₽"),),
        "vtb_prime_7": (("втб - прайм+", "за 50 млн ₽"),),
        "vtb_prime_8": (("втб - прайм+", "за 100 млн ₽"),),
        "gpb_premium_1": (("газпромбанк - премиум", "за 2.5 млн ₽"),),
        "gpb_premium_2": (("газпромбанк - премиум", "за 6 млн ₽"),),
        "gpb_premium_3": (("газпромбанк - премиум", "за 12 млн ₽"),),
        "gpb_private": (("газпромбанк - private",),),
        "ozonbank_ultra_bronze": (("ultra bronze",),),
        "ozonbank_ultra_silver": (("ultra silver",),),
        "ozonbank_ultra_gold": (("ultra gold",),),
        "ozonbank_ultra_platinum": (("ultra platinum",),),
        "raif_premium_1": (("райффайзен - premium", "2500 ₽ в мес"),),
        "raif_premium_2": (("райффайзен - premium", "траты 150 тыс ₽"),),
        "raif_premium_3": (("райффайзен - premium", "за 1.5 млн ₽"),),
        "raif_premium_4": (("райффайзен - premium", "за 5 млн ₽"),),
        "tbank_bronze": (("т-банк - bronze",),),
        "tbank_silver": (("т-банк - silver",),),
        "tbank_gold": (("т-банк - gold",),),
        "tbank_diamond": (("т-банк - diamond",),),
        "tbank_private_30": (("т-банк - private", "за 30 млн ₽"),),
        "tbank_private_55": (("т-банк - private", "за 55 млн ₽"),),
        "tbank_private_100": (("т-банк - private", "за 100 млн ₽"),),
    }

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
                value = self._dd_value(dd)
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
            self._finalize_derived_fields(result)
            self._reconcile_option_availability(result)
        else:
            self._extract_overview_section(result, html_to_text(html), tier, bank)
        return result

    # Детали, которые ПБИ прячет внутри сводных блоков («Другие привилегии»
    # и т.п.) — вытаскиваем в профильные поля, чтобы они не терялись
    EMBEDDED_RULES = [
        # Консьерж фиксируем только по явным названиям сервиса; общий шаблон
        # захватывал соседние строки вроде "консьерж Cервис appoint".
        ("concierge", r"(?:АМА\s+консьерж|консьерж(?:-сервис)?\s+(?:Aspire|Pb Service|PRIME|Only Assist))"),
        # повышенный курс обмена бонусов
        ("cashback", r"обмен \d+ бонус\w*[^;|]{0,60}"),
        # опция «Авто» с составом
        ("auto", r"опция «Авто»[^)]{0,180}\)"),
        ("taxi", r"опция «Такси»[^)]{0,180}\)"),
        ("restaurants", r"опция «Рестораны?»[^)]{0,180}\)"),
        ("selectable_options", r"опция «[^»]+»[^)]{0,180}\)"),
        ("always_included_options", r"опция «[^»]+»[^)]{0,180}\(всегда включен[ао]\)"),
        # карточные условия: металл, лимиты переводов/снятия, выпуск
        ("transfers_payments", r"(?:перевод|плат[её]ж)\w{0,3} (?:без комиссии |до )[^;|.]{0,80}"),
        ("transfers_payments", r"лимит\w{0,3}[^;|.]{0,25}перевод\w*[^;|.]{0,60}"),
        ("cash_withdrawal", r"снят\w{0,3} наличн\w*[^;|.]{0,80}"),
        ("cash_withdrawal", r"лимит\w{0,3}[^;|.]{0,25}снят\w*[^;|.]{0,60}"),
        ("supreme", r"(?:Mir|Мир)\s+Supreme[^;|.]{0,100}"),
        ("supreme", r"Supreme[^;|.]{0,100}"),
        ("card_terms", r"металлическ\w{0,4} (?:сбер)?карт\w{0,4}[^;|.]{0,80}"),
        ("card_terms", r"лимит\w{0,3}[^;|.]{0,25}(?:перевод|снят)\w*[^;|.]{0,50}"),
        ("card_terms", r"перевод\w{0,3} (?:без комиссии |до )[^;|.]{0,60}"),
        ("card_terms", r"(?:выпуск|перевыпуск) карт\w{0,3}[^;|.]{0,60}"),
    ]

    @staticmethod
    def _dd_value(dd) -> str:
        items = [
            normalize_text(li.get_text(" ", strip=True))
            for li in dd.find_all("li")
            if normalize_text(li.get_text(" ", strip=True))
        ]
        if items:
            return " | ".join(items)
        return normalize_text(dd.get_text(" | ", strip=True))

    def _extract_overview_section(self, result: dict, text: str, tier: dict, bank: dict):
        block = self._overview_block(text, tier, bank)
        if not block:
            return
        lines = [normalize_text(line) for line in block.splitlines()
                 if normalize_text(line) and normalize_text(line) != "* * *"]
        if not lines:
            return

        heading = lines[0]
        conditions = self._lines_between(
            lines, 1, self.OVERVIEW_FIELD_LABELS)
        conditions = self._join_amount_continuations(conditions)
        if conditions:
            result["positioning"] = normalize_text(f"{bank['name']} — {heading}")[:MAX_VALUE_LEN]
            result["entry_conditions"] = " ; ".join(conditions)[:MAX_STRUCTURED_VALUE_LEN]
            fee = re.search(r"\d[\d\s]*₽\s+в\s+мес", result["entry_conditions"])
            if fee:
                result["service_cost"] = normalize_text(fee.group(0))

        selection_rule = self._value_after_label(lines, "Привилегии на выбор")
        if selection_rule:
            result["selection_rules"] = selection_rule[:MAX_STRUCTURED_VALUE_LEN]
        preferences = self._label_values(lines, "Преференции")
        if preferences:
            self._append(result, "selection_rules", "Преференции: " + " ; ".join(preferences))

        always = [
            self._mark_always_included(item)
            for item in self._section_items(
                lines, "Всегда включено:", "Дополнительно на выбор:"
            )
        ]
        selectable = self._section_items(lines, "Дополнительно на выбор:", "Страховка")
        selectable += self._section_items(lines, "Доступно на выбор:", "Страховка")
        insurance = self._lines_after_label_until(lines, "Страховка", "Другие привилегии")
        ecosystem = self._lines_after_label_until_any(
            lines, "Другие привилегии", self._section_end_labels("Другие привилегии"))

        self._set_joined(result, "lounge_access", self._label_values(lines, "Бизнес-залы"))
        self._set_joined(result, "restaurants", self._label_values(lines, "Рестораны"))
        taxi_values = self._label_values(lines, "Такси") + self._label_values(lines, "Трансфер")
        self._set_joined(result, "taxi", taxi_values)
        transfer_values = self._label_values(lines, "Переводы") + self._label_values(lines, "Платежи")
        self._set_joined(result, "transfers_payments", transfer_values)
        self._set_joined(result, "cash_withdrawal", self._label_values(lines, "Снятие наличных"))
        self._set_joined(result, "supreme", self._label_values(lines, "Supreme"))
        self._set_joined(result, "always_included_options", always)
        self._set_joined(result, "selectable_options", selectable)
        self._set_joined(result, "insurance", insurance)
        self._set_joined(result, "ecosystem", ecosystem)

        self._assign_level_options(result, always, always_included=True)
        self._assign_level_options(result, selectable, always_included=False)
        self._extract_embedded(result, block)
        self._finalize_derived_fields(result)
        self._reconcile_option_availability(result)

    def _overview_block(self, text: str, tier: dict, bank: dict) -> str:
        blocks = self._overview_blocks(text)
        if not blocks:
            return self._level_block(text, tier)

        tier_id = tier.get("tier_id", "")
        hints = self.OVERVIEW_TIER_HINTS.get(tier_id, ())
        for hint_group in hints:
            for block in blocks:
                searchable = self._match_text(block)
                if all(self._match_text(hint) in searchable for hint in hint_group):
                    return block
        if hints:
            return ""

        if bank.get("id") == "sber":
            return self._level_block(text, tier)

        tier_terms = self._tier_terms(tier)
        scored = []
        for block in blocks:
            searchable = self._match_text(block)
            score = sum(1 for term in tier_terms if term in searchable)
            if score:
                scored.append((score, block))
        if not scored:
            return ""
        scored.sort(key=lambda item: item[0], reverse=True)
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            return ""
        return scored[0][1]

    def _overview_blocks(self, text: str) -> list[str]:
        lines = [normalize_text(line) for line in text.splitlines()
                 if normalize_text(line)]
        starts = [
            idx for idx, line in enumerate(lines)
            if self._is_overview_heading(line)
        ]
        blocks = []
        for pos, start in enumerate(starts):
            next_start = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
            end = next_start
            for idx in range(start + 1, next_start):
                if any(lines[idx].startswith(prefix)
                       for prefix in self.OVERVIEW_STOP_PREFIXES):
                    end = idx
                    break
            if end > start + 1:
                blocks.append("\n".join(lines[start:end]))
        return blocks

    def _is_overview_heading(self, line: str) -> bool:
        if " – " not in line and " - " not in line:
            return False
        return any(line.startswith(prefix) for prefix in self.OVERVIEW_HEADINGS)

    @staticmethod
    def _match_text(text: str) -> str:
        return normalize_text(text).lower().replace("–", "-").replace("\xa0", " ")

    @staticmethod
    def _tier_terms(tier: dict) -> list[str]:
        raw = " ".join((tier.get("tier_id", ""), tier.get("tier_name", "")))
        text = normalize_text(raw).lower().replace("_", " ").replace("–", " ")
        aliases = {
            "aclub": "а-клуб",
            "a club": "а-клуб",
            "raif": "райффайзен",
            "gpb": "газпромбанк",
            "ozonbank": "ozon",
        }
        terms = set()
        for token in re.split(r"[^a-zа-яё0-9+.-]+", text):
            if len(token) >= 4 and not token.isdigit():
                terms.add(aliases.get(token, token))
        return sorted(terms, key=len, reverse=True)

    @staticmethod
    def _level_block(text: str, tier: dict) -> str:
        level_match = re.search(r"(?:уровень|level)[^\d]{0,8}(\d+)",
                                tier.get("tier_name", ""), flags=re.IGNORECASE)
        if not level_match:
            level_match = re.search(r"_(\d+)$", tier.get("tier_id", ""))
        if not level_match:
            return ""
        level = level_match.group(1)
        pattern = rf"Сбер\s+[–-]\s+Уровень\s*{level}\b"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            return ""
        tail = text[match.end():]
        stops = []
        next_match = re.search(r"\n\s*Сбер\s+[–-]\s+Уровень\s*\d+\b",
                               tail, flags=re.IGNORECASE)
        if next_match:
            stops.append(next_match.start())
        section_match = re.search(
            r"\n\s*(?:Посещение бизнес-залов|Компенсация ресторанов|"
            r"Компенсация такси|Как работает|Таблица уровней)",
            tail,
            flags=re.IGNORECASE,
        )
        if section_match:
            stops.append(section_match.start())
        end = match.end() + min(stops) if stops else len(text)
        return text[match.start():end]

    @staticmethod
    def _lines_between(lines: list[str], start_idx: int,
                       stop_labels: tuple[str, ...]) -> list[str]:
        out = []
        for line in lines[start_idx:]:
            if any(line.startswith(label) for label in stop_labels):
                break
            out.append(line)
        return out

    @staticmethod
    def _join_amount_continuations(lines: list[str]) -> list[str]:
        out = []
        for line in lines:
            if out and out[-1].endswith("за") and re.match(r"^\d", line):
                out[-1] = f"{out[-1]} {line}"
            else:
                out.append(line)
        return out

    @staticmethod
    def _value_after_label(lines: list[str], label: str) -> str:
        for idx, line in enumerate(lines):
            if line == label and idx + 1 < len(lines):
                nxt = lines[idx + 1]
                return "" if nxt.endswith(":") else nxt
        return ""

    def _label_values(self, lines: list[str], label: str) -> list[str]:
        return self._lines_after_label_until_any(
            lines, label, self.OVERVIEW_FIELD_LABELS)

    def _section_items(self, lines: list[str], start_label: str,
                       end_label: str) -> list[str]:
        raw = self._lines_after_label_until(lines, start_label, end_label)
        return [line for line in raw if line not in {"—", "-"}]

    @staticmethod
    def _lines_after_label_until(lines: list[str], start_label: str,
                                 end_label: str) -> list[str]:
        out = []
        active = False
        for line in lines:
            if line == start_label:
                active = True
                continue
            if active and line.startswith(end_label):
                break
            if active:
                out.append(line)
        return out

    @staticmethod
    def _lines_after_label_until_any(lines: list[str], start_label: str,
                                     end_labels: tuple[str, ...]) -> list[str]:
        out = []
        active = False
        for line in lines:
            if line == start_label:
                active = True
                continue
            if active and any(line.startswith(label) and line != start_label
                              for label in end_labels):
                break
            if active and line not in {"—", "-", "* * *"}:
                out.append(line)
        return out

    @classmethod
    def _section_end_labels(cls, start_label: str) -> tuple[str, ...]:
        """Return overview labels that can close a section.

        Some list items begin with words that are also field labels, e.g.
        Gazprombank Private has "Безлимит бизнес-залов" inside "Другие
        привилегии". For that section, only labels that naturally follow it
        should stop collection; otherwise the first benefit truncates the list.
        """
        if start_label == "Другие привилегии":
            return tuple(
                label for label in cls.OVERVIEW_FIELD_LABELS
                if label not in {"Бизнес-залы", "Рестораны", "Такси", "Трансфер"}
            )
        return cls.OVERVIEW_FIELD_LABELS

    def _set_joined(self, result: dict, field_id: str, values: list[str]):
        cleaned = [v for v in values if v and v not in {"—", "-"}]
        if cleaned:
            self._append(result, field_id, " ; ".join(cleaned))

    def _extract_lounge_option(self, result: dict, text: str):
        matches = []
        for m in re.finditer(r"опция «Бизнес-залы»[^;]*", text, re.IGNORECASE):
            matches.append(normalize_text(m.group(0)))
        if matches:
            self._append(result, "lounge_access", " ; ".join(matches))

    def _assign_level_options(self, result: dict, items: list[str],
                              always_included: bool):
        target = "always_included_options" if always_included else "selectable_options"
        for item in items:
            if always_included:
                item = self._mark_always_included(item)
            self._append(result, target, item)
            low = item.lower()
            if "бизнес-зал" in low or "бз" in low:
                self._append(result, "lounge_access", item)
            if ("такси" in low or "трансфер" in low
                    or "ресторан" in low or "кафе" in low):
                self._assign_transport(result, item)
            if "авто" in low:
                self._append(result, "auto", item)

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
                joined = " ; ".join(matches)[:MAX_STRUCTURED_VALUE_LEN]
                if result[field_id] == NOT_FOUND:
                    result[field_id] = joined
                elif joined.lower() not in result[field_id].lower():
                    result[field_id] = (result[field_id] + " ; " + joined)[:MAX_STRUCTURED_VALUE_LEN]

        self._extract_options_from_text(result, text)

        # Отсутствие услуги НЕ выводим из молчания источника: страница уровня
        # ПБИ не всегда перечисляет консьерж и т.п. (ложные «нет» были у
        # Т-Банка и Альфы). Отсутствие фиксируется только верифицированной
        # записью в scanner/curated.py (значение «—» с обоснованием).

    def _assign(self, result: dict, label: str, value: str):
        low = label.lower()
        if any(m in low for m in self.SKIP_LABELS):
            return
        if self._is_transport_label(low):
            self._assign_transport(result, value)
            return
        for markers, field_id in self.LABEL_MAP:
            if any(m in low for m in markers):
                break
        else:
            field_id = "other_notes"
            value = f"{label}: {value}"
        if field_id == "entry_conditions" and self._is_balance_accounting_note(value):
            return
        if field_id == "selectable_options":
            self._assign_options(result, value)
            return
        entry = value[:MAX_STRUCTURED_VALUE_LEN]
        if result[field_id] == NOT_FOUND:
            result[field_id] = entry
        else:
            result[field_id] = (result[field_id] + " ; " + entry)[:MAX_STRUCTURED_VALUE_LEN]

    @staticmethod
    def _is_balance_accounting_note(value: str) -> bool:
        """Skip PBI accounting-mode labels that are not entry thresholds."""
        normalized = normalize_text(value).lower()
        return normalized in {
            "минимальный остаток",
            "среднемесячный остаток",
        }

    @staticmethod
    def _is_transport_label(label: str) -> bool:
        has_taxi = "такси" in label or "трансфер" in label
        has_rest = "ресторан" in label or "кафе" in label
        return has_taxi and has_rest

    def _assign_transport(self, result: dict, value: str):
        self._append(result, "taxi_restaurants", value)
        taxi_parts, restaurant_parts = self._split_transport(value)
        for part in taxi_parts:
            self._append(result, "taxi", part)
        for part in restaurant_parts:
            self._append(result, "restaurants", part)

    def _split_transport(self, value: str) -> tuple[list[str], list[str]]:
        parts = [p.strip(" ;|") for p in re.split(r"\s+\|\s+|;\s*", value) if p.strip(" ;|")]
        taxi_parts, restaurant_parts = [], []
        for part in parts:
            low = part.lower()
            if "такси" in low or "трансфер" in low:
                taxi_parts.append(part)
            if ("ресторан" in low or "кафе" in low or "чек" in low
                    or "вылет" in low or "прил" in low):
                restaurant_parts.append(part)
        if not taxi_parts:
            taxi_parts = self._regex_transport(value, r"[^.|;]*такси[^.|;]*")
        if not restaurant_parts:
            restaurant_parts = self._regex_transport(
                value, r"[^.|;]*(?:ресторан|кафе|чек|вылет|прил[её]т)[^.|;]*")
        return taxi_parts[:3], restaurant_parts[:3]

    @staticmethod
    def _regex_transport(value: str, pattern: str) -> list[str]:
        found = []
        seen = set()
        for match in re.finditer(pattern, value, flags=re.IGNORECASE):
            snippet = normalize_text(match.group(0).strip(" |;"))
            if snippet and snippet.lower() not in seen:
                seen.add(snippet.lower())
                found.append(snippet)
        return found

    def _assign_options(self, result: dict, value: str):
        self._append(result, "selectable_options", value)
        rule = self._extract_selection_rule(value)
        if rule:
            self._append(result, "selection_rules", rule)
        self._extract_options_from_text(result, value)

    def _extract_options_from_text(self, result: dict, text: str):
        for match in re.finditer(r"Опция «([^»]+)»\s*\(([^)]{1,220})\)",
                                 text, flags=re.IGNORECASE):
            name = normalize_text(match.group(1))
            details = normalize_text(match.group(2))
            option_text = f"Опция «{name}» ({details})"
            is_always = "всегда включ" in details.lower()
            if is_always:
                self._append(result, "always_included_options", option_text)
            else:
                self._append(result, "selectable_options", option_text)
            low_name = name.lower()
            if "такси" in low_name:
                self._append(result, "taxi", option_text)
            elif "ресторан" in low_name or "кафе" in low_name:
                self._append(result, "restaurants", option_text)
            elif "авто" in low_name:
                self._append(result, "auto", option_text)

    @staticmethod
    def _extract_selection_rule(text: str) -> str:
        lowered = text.lower()
        blocked = ("бонус", "обмен", "менеджер", "инвест", "очеред", "запис")
        patterns = [
            r"(?:можно\s+)?выбрать\s+\d+[^.;|]{0,80}",
            r"\d+\s+опци[ия][^.;|]{0,80}на выбор",
            r"раз в месяц[^.;|]{0,100}(?:опци|выбор|выбрать)[^.;|]{0,80}",
            r"выбранная опция[^.;|]{0,100}",
            r"(?:изменить|поменять)[^.;|]{0,80}(?:выбор|опци)[^.;|]{0,80}",
        ]
        for pattern in patterns:
            match = re.search(pattern, lowered, flags=re.IGNORECASE)
            if match:
                candidate = text[match.start():match.end()]
                if any(word in candidate.lower() for word in blocked):
                    continue
                return normalize_text(candidate)
        return ""

    def _finalize_derived_fields(self, result: dict):
        if result["taxi_restaurants"] == NOT_FOUND:
            parts = [result.get("taxi"), result.get("restaurants")]
            present = [p for p in parts if p and p != NOT_FOUND]
            if present:
                result["taxi_restaurants"] = " ; ".join(present)[:MAX_STRUCTURED_VALUE_LEN]
        for field_id in ("taxi", "restaurants", "auto"):
            value = result.get(field_id, NOT_FOUND)
            if value != NOT_FOUND and "опция" in value.lower():
                target = ("always_included_options"
                          if "всегда включ" in value.lower()
                          else "selectable_options")
                self._append(result, target, value)

    def _reconcile_option_availability(self, result: dict):
        """Prefer explicit source sections over generic "опция" mentions."""
        always = result.get("always_included_options", NOT_FOUND)
        selectable = result.get("selectable_options", NOT_FOUND)
        if always == NOT_FOUND or selectable == NOT_FOUND:
            return
        always_names = self._option_names(always)
        if not always_names:
            return
        kept = []
        for part in self._split_option_parts(selectable):
            names = self._option_names(part)
            if names and names <= always_names:
                continue
            kept.append(part)
        result["selectable_options"] = (
            " ; ".join(kept)[:MAX_STRUCTURED_VALUE_LEN] if kept else NOT_FOUND
        )

    @staticmethod
    def _mark_always_included(item: str) -> str:
        if "опция" not in item.lower() or "всегда включ" in item.lower():
            return item
        return f"{item} (всегда включена)"

    @staticmethod
    def _option_names(text: str) -> set[str]:
        return {
            normalize_text(match.group(1)).lower().replace("ё", "е")
            for match in re.finditer(r"опция «([^»]+)»", text, re.IGNORECASE)
        }

    @staticmethod
    def _split_option_parts(text: str) -> list[str]:
        return [
            normalize_text(part)
            for part in re.split(r"\s+\|\s+|;\s*", text)
            if normalize_text(part)
        ]

    @staticmethod
    def _append(result: dict, field_id: str, value: str):
        entry = normalize_text(value)[:MAX_STRUCTURED_VALUE_LEN]
        if not entry:
            return
        current = result.get(field_id, NOT_FOUND)
        if current == NOT_FOUND:
            result[field_id] = entry
        elif entry.lower() not in current.lower():
            result[field_id] = (current + " ; " + entry)[:MAX_STRUCTURED_VALUE_LEN]


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
            source_id in {"pbi", "pbi_level"} or "premiumbanking.info" in source_url):
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
