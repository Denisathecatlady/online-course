from pathlib import Path

from django.conf import settings
from django.db.models import Min
from django.shortcuts import render, get_object_or_404
from django.utils.text import slugify

from .models import Product, ProductVariant, Color
import json


PRODUCT_COLOR_IMAGE_FILES = {
    "samostatne-ocko": {
        "pastelove-ruzova": "ocko_pres_rameno_ruzove.png",
    },
    "voditko-bez-ocka": {
        "pastelove-ruzova": "voditko_bez_ocka_ruzove.png",
    },
    "voditko-s-poutkem": {
        "pastelove-ruzova": "voditko_s_ockem_na_ruku_ruzove.png",
        "seda": "voditko_s_ockem_na_ruku_sede.png",
    },
}

PRODUCT_CARD_CONTENT = {
    "samostatne-ocko": {
        "eyebrow": "Základ",
        "teaser": "Rychle, jednoduše, vždy po ruce",
        "description": (
            "Jednoduché očko pro rychlé připnutí. Ideální jako doplněk "
            "k hlavnímu vodítku nebo pro krátké vycházky."
        ),
        "features": [
            "Lehké a kompaktní",
            "Rychlé připnutí",
            "Ruční výroba",
        ],
        "button_theme": "sage",
        "image": "products/pes_voditko_2.png",
    },
    "voditko-bez-ocka": {
        "eyebrow": "Oblíbené",
        "badge": "Nejprodávanější",
        "teaser": "Minimalistické, maximálně odolné",
        "description": (
            "Vodítko bez poutka pro ty, kteří preferují přímé držení v ruce. "
            "Ručně vyráběné z odolného popruhu."
        ),
        "features": [
            "Přímé držení",
            "Odolný materiál",
            "Volba barvy i délky",
        ],
        "button_theme": "accent",
        "image": "products/pes_voditko_3.png",
    },
    "voditko-s-poutkem": {
        "eyebrow": "Komplet",
        "teaser": "Plný komfort, plná kontrola",
        "description": (
            "Ručně vyráběné vodítko s pevným poutkem. Funkční, odolné a "
            "vizuálně čisté. Pro každodenní procházky."
        ),
        "features": [
            "Ergonomické poutko",
            "Pevná karabina",
            "Prémiové materiály",
        ],
        "button_theme": "dark",
        "image": "products/pes_voditko_1.png",
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
        "image": "products/pes_voditko_2.png",
        "alt": "Pes s obojkem v trávě",
    },
    {
        "image": "products/pes_voditko_3.png",
        "alt": "Psovodka se psy při večerní procházce",
    },
]


def build_media_url(relative_path):
    return f"{settings.MEDIA_URL.rstrip('/')}/{relative_path.lstrip('/')}"


def get_variant_image_url(product, color):
    if not product.image:
        return ""

    product_images = PRODUCT_COLOR_IMAGE_FILES.get(product.slug, {})
    image_name = product_images.get(slugify(color.name))

    if image_name:
        image_path = Path(settings.MEDIA_ROOT) / "products" / image_name
        if image_path.exists():
            return f"{settings.MEDIA_URL}products/{image_name}"

    return product.image.url


def product_list(request):
    products = (
        Product.objects
        .filter(is_active=True)
        .prefetch_related("variants")
        .order_by("id")
    )
    products_by_slug = {product.slug: product for product in products}

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
            "image_url": product.image.url if product.image else build_media_url(card_content["image"]),
            "available_colors": available_colors,
            **card_content,
        })

    return render(request, "shop/product_list.html", {
        "products": products,
        "product_cards": product_cards,
        "hero_image_url": build_media_url("products/pes_voditko_1.png"),
        "cta_image_url": build_media_url("products/pes_voditko_2.png"),
        "hero_stats": SHOP_STATS,
        "gallery_images": [
            {
                **item,
                "image_url": build_media_url(item["image"]),
            }
            for item in SHOP_GALLERY
        ],
        "testimonials": SHOP_TESTIMONIALS,
    })


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    variants = list(product.variants.filter(is_active=True).select_related("color"))
    length_labels = dict(ProductVariant.LENGTH_CHOICES)
    type_labels = dict(ProductVariant.TYPE_CHOICES)
    bundle_companions = {}
    bundle_offer = None

    if product.slug == "voditko-bez-ocka":
        companion_product = Product.objects.filter(
            slug="samostatne-ocko",
            is_active=True,
        ).first()
        if companion_product:
            bundle_companions = {
                variant.color_id: variant
                for variant in companion_product.variants.filter(is_active=True).select_related("color")
            }
            bundle_offer = {
                "title": "Výhodná varianta",
                "copy": (
                    "Chceš mít vodítko bez očka a současně i očko přes rameno? "
                    "Přidej obě varianty do košíku jedním kliknutím."
                ),
                "companion_name": companion_product.name,
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
            "bundle_variant_id": bundle_companions.get(v.color_id).id if bundle_companions.get(v.color_id) else None,
            "bundle_variant_name": (
                bundle_companions.get(v.color_id).product.name
                if bundle_companions.get(v.color_id) else ""
            ),
            "bundle_price": (
                float(v.price + bundle_companions.get(v.color_id).price)
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
        "lengths": lengths,
        "types": types,
        "colors": colors,
        "variants_json": json.dumps(variant_data),
        "has_lengths": len(lengths) > 0,
        "has_types": len(types) > 1,
        "bundle_offer": bundle_offer,
    })
