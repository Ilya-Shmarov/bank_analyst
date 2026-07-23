import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from landing.sber_vs import build_sber_vs_landing


def _field(value):
    return {"display_value": value, "value": value, "raw_text": value}


class SberVsAlignmentTests(unittest.TestCase):
    def _write_fixture(self, tmp):
        rows = []
        banks = [
            ("bank_one", "Банк Один", 1),
            ("bank_two", "Банк Два с очень длинным названием программы", 2),
            ("bank_three", "Банк Три", 3),
        ]
        for bank_id, bank_name, bank_no in banks:
            for level_no in range(1, 5):
                rows.append({
                    "bank_id": bank_id,
                    "bank": bank_name,
                    "tier_id": f"{bank_id}_{level_no}",
                    "tier": (
                        f"Премиальная программа с длинным названием — уровень {level_no}"
                    ),
                    "segment": "0–3 млн ₽",
                    "scan_date": "2026-07-17T00:00:00",
                    "sources_ok": 1,
                    "score": {"total": bank_no + level_no / 10, "breakdown": {}},
                    "fields": {
                        "entry_conditions": _field(f"{bank_no + level_no} млн ₽"),
                        "service_cost": _field(f"{level_no} 990 ₽ в месяц"),
                        "lounge_access": _field(f"{level_no} посещений в месяц"),
                    },
                })
        comparison_json = Path(tmp) / "comparison_data.json"
        comparison_json.write_text(
            json.dumps({"schema_version": 1, "rows": rows}, ensure_ascii=False),
            encoding="utf-8",
        )
        output = Path(tmp) / "sber_vs.html"
        with patch("landing.sber_vs.premium_changes.load_changes", return_value=[]):
            build_sber_vs_landing(comparison_json, output)
        return output

    def test_comparison_header_and_rows_share_one_grid_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = self._write_fixture(tmp)
            html = output.read_text(encoding="utf-8")

        self.assertIn('<div class="cmp-attr-spacer" aria-hidden="true"></div>', html)
        self.assertNotIn("<colgroup>", html)
        self.assertIn("--compare-grid-template:", html)
        self.assertIn("grid-template-columns: var(--compare-grid-template);", html)
        self.assertIn(".cmp-table tr {\n  display: grid;", html)
        self.assertIn("cmp.style.setProperty('--compare-level-count'", html)
        self.assertIn("currencies.size > 1", html)
        self.assertIn("Страховые суммы указаны в разных валютах", html)
        self.assertIn(".cmp-attr-spacer { display: none; }", html)
        forbidden_offsets = ("translateX", ".cmp-head { margin-left", "#compare { margin-left")
        for token in forbidden_offsets:
            self.assertNotIn(token, html)

    def test_generated_fixture_covers_many_banks_levels_and_long_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = self._write_fixture(tmp)
            html = output.read_text(encoding="utf-8")
            payload = re.search(
                r'<script id="data" type="application/json">(.*?)</script>',
                html,
                flags=re.S,
            ).group(1)
            data = json.loads(payload)

        self.assertEqual(len(data), 3)
        self.assertTrue(all(len(bank["levels"]) == 4 for bank in data))
        self.assertTrue(all(
            level["entry_match"]["eligible"]
            for bank in data for level in bank["levels"]
        ))
        bank_one = next(bank for bank in data if bank["bank"] == "Банк Один")
        self.assertEqual(
            bank_one["levels"][1]["entry_match"]["min_amount"],
            3_000_000,
        )
        self.assertIn('class="pickers"', html)
        self.assertIn("'chip level-chip'", html)
        self.assertIn("очень длинным названием", html)

    def test_level_cards_align_with_table_columns_in_browser_if_available(self):
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Playwright is not installed")

        with tempfile.TemporaryDirectory() as tmp:
            output = self._write_fixture(tmp)
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch()
                    try:
                        page = browser.new_page(viewport={"width": 1440, "height": 900})
                        self._assert_alignment(page, output)
                        page.set_viewport_size({"width": 390, "height": 900})
                        self._assert_alignment(page, output, mobile=True)
                    finally:
                        browser.close()
            except PlaywrightError as exc:
                self.skipTest(f"Playwright browser is unavailable: {exc}")

    def test_recommendations_fill_second_and_third_banks_in_rank_order(self):
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Playwright is not installed")

        with tempfile.TemporaryDirectory() as tmp:
            output = self._write_fixture(tmp)
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch()
                    try:
                        page = browser.new_page(viewport={"width": 1440, "height": 900})
                        page.add_init_script(
                            "window.__scrolledSections = [];"
                            "const originalScrollIntoView = Element.prototype.scrollIntoView;"
                            "Element.prototype.scrollIntoView = function(options) {"
                            "  window.__scrolledSections.push(this.id);"
                            "  return originalScrollIntoView.call(this, options);"
                            "};"
                        )
                        page.goto(output.as_uri())
                        primary = page.locator('.picker[data-side="a"]')
                        primary.get_by_role(
                            "button", name="Банк Один", exact=True
                        ).click()
                        # Банк Один: level 2 has the 3 млн ₽ reference threshold.
                        primary.locator(".levels .level-chip").nth(1).click()

                        recommendations = page.locator(".recommendation-card")
                        self.assertEqual(recommendations.count(), 2)
                        page.wait_for_function(
                            "window.__scrolledSections.includes('recommendations')"
                        )
                        card_texts = recommendations.all_text_contents()
                        self.assertIn("Банк Два", card_texts[0])
                        self.assertIn("Точное совпадение", card_texts[0])
                        self.assertIn("Банк Три", card_texts[1])
                        self.assertIn("На 1 млн ₽ выше", card_texts[1])
                        self.assertFalse(page.locator("#compare").is_visible())

                        page.locator(".recommendation-card").nth(0).click()
                        self.assertIn(
                            "Банк Два",
                            page.locator('.picker[data-side="b"] .banks .active').inner_text(),
                        )
                        self.assertFalse(page.locator("#compare").is_visible())

                        page.locator(".recommendation-card:not(:disabled)").click()
                        self.assertIn(
                            "Банк Три",
                            page.locator('.picker[data-side="c"] .banks .active').inner_text(),
                        )
                        page.locator("#compare").wait_for(state="visible")

                        page.set_viewport_size({"width": 390, "height": 900})
                        has_overflow = page.locator("main.page").evaluate(
                            "(node) => node.scrollWidth > node.clientWidth"
                        )
                        self.assertFalse(has_overflow)
                    finally:
                        browser.close()
            except PlaywrightError as exc:
                self.skipTest(f"Playwright browser is unavailable: {exc}")

    def _assert_alignment(self, page, output, mobile=False):
        page.goto(output.as_uri())
        for side_n, level_n in enumerate((1, 2, 4), start=1):
            picker = page.locator(f'.picker[data-side="{chr(96 + side_n)}"]')
            picker.locator(".banks .chip").nth(side_n - 1).click()
            picker.locator(".levels .chip").nth(level_n - 1).click()

        page.locator("#compare").wait_for(state="visible")
        if mobile:
            # Mobile intentionally switches to stacked cards, so assert no horizontal
            # desync by checking every visible comparison cell uses full row width.
            widths = page.locator(".cmp-table tbody tr").first().locator("td").evaluate_all(
                "(cells) => cells.map((cell) => Math.round(cell.getBoundingClientRect().width))"
            )
            self.assertEqual(len(set(widths)), 1)
            return

        boxes = page.evaluate(
            """
            () => {
              const heads = [...document.querySelectorAll('.cmp-head .cmp-col')]
                .map((node) => node.getBoundingClientRect());
              const cells = [...document.querySelectorAll('.cmp-table tbody tr:first-child td')]
                .slice(1)
                .map((node) => node.getBoundingClientRect());
              return heads.map((head, i) => ({
                headLeft: head.left,
                headWidth: head.width,
                cellLeft: cells[i].left,
                cellWidth: cells[i].width
              }));
            }
            """
        )
        for box in boxes:
            self.assertLess(abs(box["headLeft"] - box["cellLeft"]), 1)
            self.assertLess(abs(box["headWidth"] - box["cellWidth"]), 1)


if __name__ == "__main__":
    unittest.main()
