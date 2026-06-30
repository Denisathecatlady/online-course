from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Min
from django.shortcuts import render, get_object_or_404
from django.templatetags.static import static
from django.urls import reverse
from django.utils.text import slugify

from .models import Product, ProductVariant
import json


PRODUCT_COLOR_IMAGE_PATHS = {
    "samostatne-ocko": {
        "pastelove-ruzova": "img/shop/ocko-pres-rameno-ruzove.png",
        "seda": "img/shop/ocko-pres-rameno-sede.png",
    },
    "voditko-bez-ocka": {
        "pastelove-ruzova": "img/shop/voditko-bez-ocka-ruzove.png",
        "seda": "img/shop/voditko-bez-ocka-sede.png",
    },
    "voditko-s-poutkem": {
        "pastelove-ruzova": "img/shop/voditko-s-ockem-na-ruku-ruzove.png",
        "seda": "img/shop/voditko-s-ockem-na-ruku-sede.png",
    },
}

# Obrázky POUZE pro Výhodnou sadu (vodítko bez očka + samostatné očko).
# Klíč = slug barvy (slugify názvu barvy). Nepoužívá se nikde jinde než v sadě.
BUNDLE_COLOR_IMAGE_PATHS = {
    "pastelove-ruzova": "img/shop/ocko_plus_voditko_bo_ruzovy.png",
    "seda": "img/shop/ocko_plus_voditko_bo_sede.png",
}

PRODUCT_CARD_CONTENT = {
    "samostatne-ocko": {
        "eyebrow": "Základ",
        "teaser": "Rychle, jednoduše, volné ruce",
        "description": (
            "Chytré očko pro rychlé připnutí. Nezbytný doplněk k vodítku bez očka. "
            "Ideální pro každodenní vycházky pro naplnění potřeb psa."
        ),
        "features": [
            "Lehké a kompaktní",
            "Rychlé připnutí",
            "Ruční výroba",
        ],
        "button_theme": "sage",
        "image": "img/shop/ocko-pres-rameno-sede.png",
    },
    "voditko-bez-ocka": {
        "eyebrow": "Oblíbené",
        "badge": "Nejprodávanější",
        "teaser": "Maximálně odolné, protiskluzová úprava",
        "description": (
            "Vodítko, které vám nespálí ruce. Snadno se v ruce navíjí i odvíjí. "
            "K vodítku patří očko pro pohodlné užívání. Ručně vyráběné z odolného popruhu."
        ),
        "features": [
            "Omyvatelné",
            "Odolný materiál",
            "Volba barvy i délky",
        ],
        "button_theme": "accent",
        "image": "img/shop/voditko-bez-ocka-sede.png",
    },
    "voditko-s-poutkem": {
        "eyebrow": "Komplet",
        "teaser": "Tradiční provedení, různé barvy",
        "description": (
            "Ručně vyráběné vodítko s pevným poutkem. Funkční, odolné a "
            "vizuálně čisté. Pro prima procházky."
        ),
        "features": [
            "Ergonomické poutko",
            "Pevná karabina",
            "Prémiové materiály",
        ],
        "button_theme": "dark",
        "image": "img/shop/voditko-s-ockem-na-ruku-sede.png",
    },
}

BUNDLE_DISCOUNT_RATE = Decimal("0.10")

PRODUCT_DETAIL_CONTENT = {
    "samostatne-ocko": {
        "badge": "Očko přes rameno",
        "copy": (
            "Samostatné očko přes rameno je praktický doplněk k vodítku bez očka. "
            "Hodí se, když chcete mít vodítko rychle k dispozici, pohodlně ho přehodit "
            "přes rameno a mít volné ruce při vedení psa."
        ),
        "highlights": [
            "Lehké a skladné",
            "Rychlé připnutí ke karabině",
            "Ručně vyráběné v Česku",
        ],
        "info_cards": [
            {
                "title": "K čemu slouží",
                "copy": (
                    "Očko doplní vodítko bez poutka a umožní pohodlnější nošení "
                    "nebo jistější držení v situacích, kdy potřebujete psa vést náročnější situací."
                ),
            },
            {
                "title": "Materiál",
                "copy": (
                    "Voděodolný Hexa popruh se snadno čistí a je odolný i při běžném "
                    "každodenním používání."
                ),
            },
            {
                "title": "Jak vybrat",
                "copy": (
                    "Vyberte stejnou barvu jako u vodítka. Pokud kupujete komplet, "
                    "výhodnější je sada vodítka bez očka a samostatného očka."
                ),
            },
        ],
    },
    "voditko-bez-ocka": {
        "badge": "Vodítko bez očka",
        "copy": (
            "Vodítko ukončené z obou stran karabinou. Jednu připnete k očku, druhou k postroji psa "
            "a máte volné ruce. Abyste se mohli těšit z vodítka co nejdéle, důležitá je správná "
            "kompletace a používání viz video (video nahraju na vimeo). Karabiny nejsou určeny k vláčení po zemi."
        ),
        "highlights": [
            "Volba délky a barvy",
            "Odolný voděodolný popruh",
            "Možnost výhodné sady s očkem",
        ],
        "info_cards": [
            {
                "title": "Pro koho je",
                "copy": "Pro majitele, kteří preferují vodítko na které se mohou spolehnout.",
            },
            {
                "title": "Materiál",
                "copy": "Hexa popruh je pevný, voděodolný a dobře se udržuje po procházkách v terénu.",
            },
            {
                "title": "Tip",
                "copy": "Ke stejné barvě můžete přidat samostatné očko a vytvořit zvýhodněný komplet.",
            },
        ],
    },
    "voditko-s-poutkem": {
        "badge": "Vodítko s poutkem",
        "copy": (
            "Klasické vodítko s pevným poutkem na ruku. Různé barvy, různé délky. Snadná údržba."
        ),
        "highlights": [
            "Pevné poutko na ruku",
            "Volba délky a barvy",
            "Ruční výroba",
        ],
        "info_cards": [
            {
                "title": "Pro koho je",
                "copy": "Pro běžné venčení a situace, kdy chcete mít vodítko pevně v ruce.",
            },
            {
                "title": "Materiál",
                "copy": "Voděodolný Hexa popruh se snadno čistí a je odolný i při běžném každodenním používání.",
            },
        ],
    },
}

SHOP_TESTIMONIALS = [
    {
        "quote": "„Vodítko drží perfektně, pes si zvykl hned. Konečně něco, co vypadá hezky a funguje.\"",
        "author": "Markéta K.",
    },
    {
        "quote": "„Objednal jsem na míru barvu i délku. Přišlo během týdne, kvalita je skvělá.\"",
        "author": "Tomáš B.",
    },
    {
        "quote": "„Třetí vodítko od CalmDog. Jednou koupíte a neřešíte. Doporučuji všem kamarádům.\"",
        "author": "Jana P.",
    },
]

SHOP_STATS = [
    {"value": "120+", "label": "Prodaných vodítek"},
    {"value": "100%", "label": "Ruční výroba"},
    {"value": "4.9★", "label": "Průměrné hodnocení"},
    {"value": "14 dnů", "label": "Na vrácení"},
]

SHOP_GALLERY = [
    {
        "image": "img/shop/pes-voditko-2.png",
        "alt": "Pes s obojkem v trávě",
    },
    {
        "image": "img/shop/pes-voditko-3.png",
        "alt": "Psovodka se psy při večerní procházce",
    },
]


def build_static_image_url(relative_path):
    return static(relative_path)


def get_default_product_image_url(product):
    image_path = PRODUCT_CARD_CONTENT.get(product.slug, {}).get("image")
    if image_path:
        return build_static_image_url(image_path)
    if product.image:
        return product.image.url
    return ""


def get_variant_image_url(product, color):
    image_path = PRODUCT_COLOR_IMAGE_PATHS.get(product.slug, {}).get(slugify(color.name))
    if image_path:
        return build_static_image_url(image_path)
    return get_default_product_image_url(product)


def get_bundle_image_url(leash_product, color):
    """Obrázek pro Výhodnou sadu podle barvy (jen v sadě).
    Když pro barvu nemáme fotku sady, použijeme původní fotku vodítka."""
    image_path = BUNDLE_COLOR_IMAGE_PATHS.get(slugify(color.name))
    if image_path:
        return build_static_image_url(image_path)
    return get_variant_image_url(leash_product, color)


def apply_bundle_discount(price):
    return (price * (Decimal("1.00") - BUNDLE_DISCOUNT_RATE)).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )


def build_bundle_card(products_by_slug):
    leash_product = products_by_slug.get("voditko-bez-ocka")
    loop_product = products_by_slug.get("samostatne-ocko")
    if not leash_product or not loop_product:
        return None

    length_labels = dict(ProductVariant.LENGTH_CHOICES)
    loop_variants_by_color = {}
    for variant in loop_product.variants.filter(
        is_active=True,
        stock__gt=0,
    ).select_related("color").order_by("price", "id"):
        loop_variants_by_color.setdefault(variant.color_id, variant)

    options = []
    seen_color_ids = set()
    leash_variants = leash_product.variants.filter(
        is_active=True,
        stock__gt=0,
    ).select_related("color").order_by("color__name", "price", "id")

    for leash_variant in leash_variants:
        if leash_variant.color_id in seen_color_ids:
            continue

        loop_variant = loop_variants_by_color.get(leash_variant.color_id)
        if not loop_variant:
            continue

        seen_color_ids.add(leash_variant.color_id)
        original_price = leash_variant.price + loop_variant.price
        length_label = (
            length_labels.get(leash_variant.length, f"{leash_variant.length} m")
            if leash_variant.length
            else ""
        )
        summary_parts = [leash_variant.color.name]
        if length_label:
            summary_parts.append(length_label)

        options.append({
            "color_name": leash_variant.color.name,
            "color_hex": leash_variant.color.hex_code or "#d9d9d9",
            "image_url": get_bundle_image_url(leash_product, leash_variant.color),
            "length_label": length_label,
            "summary": " - ".join(summary_parts),
            "primary_variant_id": leash_variant.id,
            "bundle_variant_id": loop_variant.id,
            "action_url": reverse("payments:add_bundle_to_cart", args=[leash_variant.id]),
            "original_price": original_price,
            "price": apply_bundle_discount(original_price),
        })

    if not options:
        return None

    # Výhodná sada se má načíst se šedou barvou; barvy se pak v šabloně
    # automaticky přepínají. Šedou proto dáme jako první (výchozí) možnost.
    options.sort(key=lambda o: 0 if slugify(o["color_name"]) == "seda" else 1)

    default_option = options[0]

    return {
        "title": "Výhodná sada",
        "badge": "Sleva 10 %",
        "teaser": "Vodítko bez očka + samostatné očko",
        "description": (
            "Vyberte barvu a přidejte rovnou obě části do košíku. "
            "Sada má shodnou barvu a zvýhodněnou cenu."
        ),
        "features": [
            "Vodítko bez očka",
            "Samostatné očko přes rameno",
            "O 10 % výhodnější komplet",
        ],
        "image_url": default_option["image_url"],
        "image_alt": "Výhodná sada vodítka bez očka a samostatného očka",
        "default_option": default_option,
        "options": options,
    }


def product_list(request):
    products = (
        Product.objects
        .filter(is_active=True)
        .prefetch_related("variants")
        .order_by("id")
    )
    products_by_slug = {product.slug: product for product in products}

    bundle_card = build_bundle_card(products_by_slug)
    product_cards = []
    for slug in ["samostatne-ocko", "voditko-bez-ocka", "voditko-s-poutkem"]:
        product = products_by_slug.get(slug)
        if not product:
            continue

        card_content = PRODUCT_CARD_CONTENT.get(slug, {})
        min_price = product.variants.filter(is_active=True).aggregate(value=Min("price"))["value"]
        available_colors = []
        seen_color_ids = set()

        for variant in product.variants.filter(is_active=True).select_related("color"):
            if variant.color_id in seen_color_ids:
                continue
            seen_color_ids.add(variant.color_id)
            available_colors.append({
                "name": variant.color.name,
                "hex_code": variant.color.hex_code or "#d9d9d9",
            })

        product_cards.append({
            "product": product,
            "price_from": min_price,
            "image_url": get_default_product_image_url(product),
            "available_colors": available_colors,
            **card_content,
        })

    return render(request, "shop/product_list.html", {
        "products": products,
        "bundle_card": bundle_card,
        "product_cards": product_cards,
        "hero_image_url": build_static_image_url("img/shop/pes-voditko-1.png"),
        "cta_image_url": build_static_image_url("img/shop/pes-voditko-2.png"),
        "hero_stats": SHOP_STATS,
        "gallery_images": [
            {
                **item,
                "image_url": build_static_image_url(item["image"]),
            }
            for item in SHOP_GALLERY
        ],
        "testimonials": SHOP_TESTIMONIALS,
    })


def postroj_na_miru(request):
    return render(request, "shop/postroj_na_miru.html")


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    variants = list(product.variants.filter(is_active=True).select_related("color"))
    length_labels = dict(ProductVariant.LENGTH_CHOICES)
    type_labels = dict(ProductVariant.TYPE_CHOICES)
    detail_content = PRODUCT_DETAIL_CONTENT.get(product.slug, {})
    bundle_companions = {}
    bundle_offer = None
    bundle_companion_is_primary = False

    if product.slug in {"voditko-bez-ocka", "samostatne-ocko"}:
        companion_slug = (
            "samostatne-ocko"
            if product.slug == "voditko-bez-ocka"
            else "voditko-bez-ocka"
        )
        companion_product = Product.objects.filter(slug=companion_slug, is_active=True).first()
        if companion_product:
            for variant in companion_product.variants.filter(
                is_active=True,
            ).select_related("color").order_by("price", "id"):
                bundle_companions.setdefault(variant.color_id, variant)
            bundle_companion_is_primary = product.slug == "samostatne-ocko"
            bundle_offer = {
                "title": "Výhodná sada - sleva 10 %",
                "heading": "Vodítko + Samostatné očko",
                "copy": (
                    "Chcete mít vodítko bez očka a současně i očko přes rameno? "
                    "Přidejte obě varianty do košíku jedním kliknutím se slevou 10 %."
                ),
            }

    unique_lengths = []
    seen_lengths = set()
    unique_types = []
    seen_types = set()
    unique_colors = []
    seen_colors = set()

    for variant in variants:
        if variant.length and variant.length not in seen_lengths:
            seen_lengths.add(variant.length)
            unique_lengths.append(variant.length)

        if variant.type and variant.type not in seen_types:
            seen_types.add(variant.type)
            unique_types.append(variant.type)

        if variant.color_id not in seen_colors:
            seen_colors.add(variant.color_id)
            unique_colors.append(variant.color)

    lengths = [
        {"value": length, "label": length_labels.get(length, f"{length} m")}
        for length in unique_lengths
    ]
    types = [
        {"value": type_value, "label": type_labels.get(type_value, type_value)}
        for type_value in unique_types
    ]
    colors = unique_colors

    variant_data = [
        {
            "id": v.id, 
            "length": v.length,
            "length_label": length_labels.get(v.length, f"{v.length} m") if v.length else "",
            "type": v.type,
            "type_label": type_labels.get(v.type, v.type) if v.type else "",
            "color": v.color.id,
            "color_name": v.color.name,
            "color_hex": v.color.hex_code,
            "image_url": get_variant_image_url(product, v.color),
            "price": float(v.price),
            "stock": v.stock,
            "bundle_primary_variant_id": (
                bundle_companions.get(v.color_id).id
                if bundle_companion_is_primary and bundle_companions.get(v.color_id)
                else v.id
            ),
            "bundle_variant_id": (
                v.id
                if bundle_companion_is_primary and bundle_companions.get(v.color_id)
                else (
                    bundle_companions.get(v.color_id).id
                    if bundle_companions.get(v.color_id)
                    else None
                )
            ),
            "bundle_variant_name": (
                bundle_companions.get(v.color_id).product.name
                if bundle_companions.get(v.color_id) else ""
            ),
            "bundle_price": (
                float(apply_bundle_discount(v.price + bundle_companions.get(v.color_id).price))
                if bundle_companions.get(v.color_id) else None
            ),
            "bundle_stock": (
                bundle_companions.get(v.color_id).stock
                if bundle_companions.get(v.color_id) else 0
            ),
        }
        for v in variants
    ]

    return render(request, "shop/product_detail.html", {
        "product": product,
        "detail_badge": detail_content.get("badge", "Vodítko"),
        "detail_copy": product.description or detail_content.get("copy", ""),
        "detail_highlights": detail_content.get("highlights", [
            "Ručně vyráběné",
            "Výběr variant na míru",
            "Bezpečné dokončení přes Stripe",
        ]),
        "detail_info_cards": detail_content.get("info_cards", []),
        "product_image_url": get_default_product_image_url(product),
        "lengths": lengths,
        "types": types,
        "colors": colors,
        "variants_json": json.dumps(variant_data),
        "has_lengths": len(lengths) > 0,
        "has_types": len(types) > 1,
        "bundle_offer": bundle_offer,
    })
