from django.shortcuts import render, get_object_or_404
from .models import Product, ProductVariant, Color
import json


def product_list(request):
    products = Product.objects.filter(is_active=True)

    return render(request, "shop/product_list.html", {
        "products": products
    })


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    variants = list(product.variants.filter(is_active=True).select_related("color"))
    length_labels = dict(ProductVariant.LENGTH_CHOICES)
    type_labels = dict(ProductVariant.TYPE_CHOICES)

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
            "price": float(v.price),
            "stock": v.stock,
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
    })
