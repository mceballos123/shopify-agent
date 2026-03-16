def build_payment_request(
    line_items: list[dict],
    shipping_label: str = "Standard Shipping",
    shipping_code: str = "standard",
    shipping_amount: str = "0.00",
    currency: str = "USD",
    locale: str = "EN",
) -> dict:
    """
    Build a ShopPayPaymentRequestInput from a list of line items.

    Each line_item dict should have:
      - label: str
      - quantity: int
      - price: str  (e.g. "29.99")
      - sku: str (optional)
      - image_url: str (optional)
    """
    shop_line_items = []
    subtotal = 0.0

    for item in line_items:
        qty = item["quantity"]
        price = item["price"]
        line_total = float(price) * qty
        subtotal += line_total

        shop_item = {
            "label": item["label"],
            "quantity": qty,
            "originalItemPrice": {"amount": price, "currencyCode": currency},
            "finalItemPrice": {"amount": price, "currencyCode": currency},
            "originalLinePrice": {"amount": str(line_total), "currencyCode": currency},
            "finalLinePrice": {"amount": str(line_total), "currencyCode": currency},
            "requiresShipping": True,
        }
        if "sku" in item:
            shop_item["sku"] = item["sku"]
        if "image_url" in item:
            shop_item["image"] = {"url": item["image_url"], "alt": item["label"]}

        shop_line_items.append(shop_item)

    shipping = float(shipping_amount)
    total = subtotal + shipping

    return {
        "lineItems": shop_line_items,
        "shippingLines": [
            {
                "label": shipping_label,
                "code": shipping_code,
                "amount": {"amount": shipping_amount, "currencyCode": currency},
            }
        ],
        "deliveryMethods": [
            {
                "code": shipping_code,
                "label": shipping_label,
                "amount": {"amount": shipping_amount, "currencyCode": currency},
                "deliveryExpectationLabel": "5-7 business days",
            }
        ],
        "subtotal": {"amount": f"{subtotal:.2f}", "currencyCode": currency},
        "total": {"amount": f"{total:.2f}", "currencyCode": currency},
        "totalShippingPrice": {
            "finalTotal": {"amount": shipping_amount, "currencyCode": currency},
        },
        "discountCodes": [],
        "locale": locale,
        "presentmentCurrency": currency,
    }
