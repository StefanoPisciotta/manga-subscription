"""Amazon flow: search -> product selection -> validation -> 1-click checkout.

Selectors verified by hand: 2026-05-22.
- SERP: title in `h2 span` (NOT `h2 a span`; Amazon removed the `<a>` as the
  parent of the h2 in some markup variants), link via `a.a-link-normal[href*='/dp/']`.
- Product page: `#productTitle`, price `span.a-price span.a-offscreen`.
If validation starts failing again, update the selectors here.

Note: the Italian string literals below (binding terms, availability words,
detail-row keys, the order-number regex) are matched against the live amazon.it
page content and must NOT be translated.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from playwright.sync_api import BrowserContext, Page, TimeoutError as PWTimeout

from src.config import SCREENSHOTS_DIR

log = logging.getLogger(__name__)

AMAZON_BASE = "https://www.amazon.it"
SEARCH_URL = AMAZON_BASE + "/s?k={query}&i=stripbooks"

REQUIRED_TITLE_TOKENS = ["one piece", "new edition"]
# One Piece New Edition is published by Star Comics in Italy.
# "panini" is kept as a fallback in case the publisher changes.
ALLOWED_PUBLISHERS = ["star comics", "panini"]
# amazon.it page values — do not translate.
REQUIRED_BINDING_TOKENS = ["copertina flessibile", "tankobon", "brossura"]


class ValidationError(RuntimeError):
    pass


@dataclass
class Product:
    url: str
    title: str
    price_eur: float
    publisher: str
    binding: str
    in_stock: bool


def _screenshot(page: Page, label: str) -> Path:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    path = SCREENSHOTS_DIR / f"{ts}-{label}.png"
    page.screenshot(path=str(path), full_page=True)
    log.info("Screenshot saved: %s", path)
    return path


def _accept_cookies_if_present(page: Page) -> None:
    for selector in ("#sp-cc-accept", "input[name='accept']"):
        try:
            page.locator(selector).click(timeout=2000)
            log.info("Cookie banner accepted (%s)", selector)
            return
        except PWTimeout:
            continue


def _parse_price(text: str) -> float | None:
    match = re.search(r"(\d+)[.,](\d{2})", text.replace("\xa0", " "))
    if not match:
        return None
    return float(f"{match.group(1)}.{match.group(2)}")


def search_volume(context: BrowserContext, query: str) -> Page:
    page = context.new_page()
    log.info("Opening search: %s", query)
    page.goto(SEARCH_URL.format(query=quote_plus(query)), wait_until="domcontentloaded", timeout=60_000)
    _accept_cookies_if_present(page)
    page.wait_for_selector("div.s-main-slot", timeout=30_000)
    return page


def _extract_title(item) -> str:
    """Amazon SERP has markup variants: try selectors in cascade."""
    for sel in ("h2 span", "h2 a span", "h2"):
        loc = item.locator(sel)
        if loc.count() > 0:
            try:
                text = loc.first.inner_text(timeout=2_500).strip()
                if text:
                    return text
            except PWTimeout:
                continue
    return ""


def _extract_href(item) -> str:
    for sel in (
        "h2 a",
        "a.a-link-normal.s-line-clamp-2",
        "a.a-link-normal[href*='/dp/']",
    ):
        loc = item.locator(sel)
        if loc.count() > 0:
            href = loc.first.get_attribute("href")
            if href:
                return href
    return ""


def open_first_relevant_result(search_page: Page, volume: int) -> Page:
    candidates = search_page.locator("div.s-main-slot div[data-component-type='s-search-result']")
    count = candidates.count()
    log.info("Results found: %d", count)

    vol_pattern = re.compile(rf"\b(?:vol\.?|volume|n\.?|tomo)\s*0*{volume}\b", re.IGNORECASE)

    skipped: list[str] = []
    for i in range(min(count, 15)):
        item = candidates.nth(i)
        title = _extract_title(item)
        if not title:
            skipped.append(f"[{i}] empty title")
            continue
        title_l = title.lower()
        if not all(tok in title_l for tok in REQUIRED_TITLE_TOKENS):
            skipped.append(f"[{i}] title tokens: {title!r}")
            continue
        if not vol_pattern.search(title_l):
            skipped.append(f"[{i}] no match vol.{volume}: {title!r}")
            continue

        href = _extract_href(item)
        if not href:
            skipped.append(f"[{i}] missing href: {title!r}")
            continue
        url = href if href.startswith("http") else AMAZON_BASE + href
        log.info("Opening candidate product: %s", title)
        product_page = search_page.context.new_page()
        product_page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        return product_page

    detail = " | ".join(skipped[:10])
    raise ValidationError(
        f"No relevant result for vol. {volume} in the first {count} hits. Skipped: {detail}"
    )


def _extract_price(page: Page) -> float | None:
    """Extract the price to pay.

    Cases:
    - Full price: the `priceToPay .a-offscreen` span holds the price.
    - Discounted price: `priceToPay .a-offscreen` is empty (whitespace) and the
      price is in the `a-price-whole` + `a-price-fraction` spans; the struck-out
      `basisprice-value` span (data-a-strike=true) holds the list price — to be
      EXCLUDED.

    Strategy: look for the `priceToPay` or `apex-pricetopay-value` element and
    rebuild the price from `a-price-whole`/`a-price-fraction`. If absent, fall
    back to non-struck `.a-offscreen` spans.
    """
    extracted = page.evaluate(
        """
        () => {
            const containers = document.querySelectorAll(
                'span.priceToPay, span.apex-pricetopay-value'
            );
            for (const c of containers) {
                const whole = c.querySelector('.a-price-whole');
                const frac = c.querySelector('.a-price-fraction');
                if (whole) {
                    // a-price-whole often includes the decimal separator as
                    // <span class="a-price-decimal">,</span>, so we strip it.
                    const w = whole.textContent.replace(/[^0-9]/g, '');
                    const f = frac ? frac.textContent.replace(/[^0-9]/g, '') : '00';
                    if (w) return { source: 'priceToPay-whole', text: `${w},${f}` };
                }
                const off = c.querySelector('.a-offscreen');
                if (off && off.textContent.trim()) {
                    return { source: 'priceToPay-offscreen', text: off.textContent.trim() };
                }
            }
            // Fallback: take the first NON-struck a-price with a valid .a-offscreen.
            const all = document.querySelectorAll('span.a-price');
            for (const p of all) {
                if (p.getAttribute('data-a-strike') === 'true') continue;
                const off = p.querySelector('.a-offscreen');
                if (off && off.textContent.trim()) {
                    return { source: 'fallback-non-strike', text: off.textContent.trim() };
                }
            }
            return null;
        }
        """
    )
    if not extracted:
        return None
    price = _parse_price(extracted["text"])
    if price is not None:
        log.info("Price read via %s: %r -> %.2f", extracted["source"], extracted["text"], price)
    return price


def _extract_detail(page: Page, key_substrings: list[str]) -> str:
    """Find a detail-bullets row whose key contains one of the substrings."""
    rows = page.locator(
        "#detailBullets_feature_div li, #productDetails_detailBullets_sections1 tr, "
        "#productDetailsTable li"
    )
    for i in range(rows.count()):
        raw = rows.nth(i).inner_text().replace("\xa0", " ").replace("‏", "").replace("‎", "").strip()
        low = raw.lower()
        if any(k in low for k in key_substrings):
            # Format: "Key : Value" or "Key\tValue"
            for sep in (":", "\t"):
                if sep in raw:
                    return raw.split(sep, 1)[-1].strip()
            return raw
    return ""


def extract_product(page: Page) -> Product:
    page.wait_for_selector("#productTitle", timeout=30_000)
    title = page.locator("#productTitle").inner_text().strip()

    # Give the (lazy) price block time to render.
    try:
        page.wait_for_selector("#corePrice_feature_div, #corePriceDisplay_desktop_feature_div", timeout=10_000)
    except PWTimeout:
        log.warning("No price block found in the known selectors, proceeding anyway")

    price = _extract_price(page)
    if price is None:
        raise ValidationError("Price not extractable from the product page")

    # Detail-row keys are matched against the amazon.it page — do not translate.
    publisher = _extract_detail(page, ["editore", "publisher"])

    # Binding: first try the subtitle (e.g. "Copertina flessibile – date"),
    # then fall back to the detail bullets.
    binding = ""
    sub_loc = page.locator("#productSubtitle")
    if sub_loc.count() > 0:
        binding = sub_loc.first.inner_text().split("–")[0].split("-")[0].strip()
    if not binding:
        binding = _extract_detail(page, ["copertina", "rilegatura", "formato"])

    availability = ""
    avail_loc = page.locator("#availability")
    if avail_loc.count() > 0:
        availability = avail_loc.first.inner_text().strip().lower()
    # "non disponibile" / "esaurito" are amazon.it page values — do not translate.
    in_stock = bool(availability) and "non disponibile" not in availability and "esaurito" not in availability

    return Product(
        url=page.url,
        title=title,
        price_eur=price,
        publisher=publisher,
        binding=binding,
        in_stock=in_stock,
    )


def validate(product: Product, volume: int, max_price_eur: float) -> None:
    errors: list[str] = []
    title_l = product.title.lower()
    for tok in REQUIRED_TITLE_TOKENS:
        if tok not in title_l:
            errors.append(f"title does not contain '{tok}': {product.title!r}")
    if not re.search(rf"\b(?:vol\.?|n\.?|tomo)\s*0*{volume}\b", title_l):
        errors.append(f"title does not contain 'vol. {volume}': {product.title!r}")
    pub_l = product.publisher.lower()
    if not any(p in pub_l for p in ALLOWED_PUBLISHERS):
        errors.append(f"unrecognized publisher (expected one of {ALLOWED_PUBLISHERS}): {product.publisher!r}")
    if not any(tok in product.binding.lower() for tok in REQUIRED_BINDING_TOKENS):
        errors.append(f"binding is not a paper format: {product.binding!r}")
    if product.price_eur > max_price_eur:
        errors.append(f"price {product.price_eur:.2f} EUR > threshold {max_price_eur:.2f} EUR")
    if not product.in_stock:
        errors.append("product not available")
    if errors:
        raise ValidationError("Validation failed:\n - " + "\n - ".join(errors))


def go_to_buy_now_review(page: Page) -> Path:
    """Click 'Buy now' (1-click) and stop on the order review page."""
    buy_now = page.locator("#buy-now-button")
    if buy_now.count() == 0:
        raise ValidationError("'Buy now' button not found (1-click unavailable?)")
    log.info("Clicking 'Buy now'")
    buy_now.first.click()
    # The 1-click confirmation page has 'placeYourOrder' as the final button.
    page.wait_for_selector("#placeYourOrder, input[name='placeYourOrder1'], #turbo-checkout-pyo-button", timeout=60_000)
    return _screenshot(page, "review")


def place_order(page: Page) -> str | None:
    """Confirm the order. Returns the order id if extractable from the thank-you page."""
    for sel in ("#turbo-checkout-pyo-button", "#placeYourOrder", "input[name='placeYourOrder1']"):
        loc = page.locator(sel)
        if loc.count() > 0:
            log.info("Clicking order confirmation: %s", sel)
            loc.first.click()
            break
    else:
        raise ValidationError("Order confirmation button not found")

    page.wait_for_load_state("domcontentloaded", timeout=60_000)
    _screenshot(page, "order-placed")

    body = page.content().lower()
    # Matches the Italian thank-you page ("ordine n. ...") — do not translate.
    order_match = re.search(r"ordine\s+n[°\.\s]*([0-9-]{10,})", body)
    return order_match.group(1) if order_match else None
