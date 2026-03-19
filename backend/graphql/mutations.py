CART_FRAGMENT = """
fragment CartFields on Cart {
  id
  checkoutUrl
  createdAt
  updatedAt
  totalQuantity
  note
  lines(first: 250) {
    edges {
      node {
        id
        quantity
        merchandise {
          ... on ProductVariant {
            id
            title
            price {
              amount
              currencyCode
            }
            product {
              title
              handle
            }
            image {
              url
              altText
            }
          }
        }
        attributes {
          key
          value
        }
      }
    }
  }
  cost {
    totalAmount {
      amount
      currencyCode
    }
    subtotalAmount {
      amount
      currencyCode
    }
    totalTaxAmount {
      amount
      currencyCode
    }
    totalDutyAmount {
      amount
      currencyCode
    }
  }
  buyerIdentity {
    email
    phone
    countryCode
  }
  attributes {
    key
    value
  }
}
"""

CART_CREATE_MUTATION = (
    CART_FRAGMENT
    + """
mutation cartCreate($input: CartInput!) {
  cartCreate(input: $input) {
    cart {
      ...CartFields
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""
)

CART_LINES_ADD_MUTATION = (
    CART_FRAGMENT
    + """
mutation cartLinesAdd($cartId: ID!, $lines: [CartLineInput!]!) {
  cartLinesAdd(cartId: $cartId, lines: $lines) {
    cart {
      ...CartFields
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""
)

CART_LINES_UPDATE_MUTATION = (
    CART_FRAGMENT
    + """
mutation cartLinesUpdate($cartId: ID!, $lines: [CartLineUpdateInput!]!) {
  cartLinesUpdate(cartId: $cartId, lines: $lines) {
    cart {
      ...CartFields
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""
)

CART_LINES_REMOVE_MUTATION = (
    CART_FRAGMENT
    + """
mutation cartLinesRemove($cartId: ID!, $lineIds: [ID!]!) {
  cartLinesRemove(cartId: $cartId, lineIds: $lineIds) {
    cart {
      ...CartFields
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""
)

CART_BUYER_IDENTITY_UPDATE_MUTATION = (
    CART_FRAGMENT
    + """
mutation cartBuyerIdentityUpdate($cartId: ID!, $buyerIdentity: CartBuyerIdentityInput!) {
  cartBuyerIdentityUpdate(cartId: $cartId, buyerIdentity: $buyerIdentity) {
    cart {
      ...CartFields
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""
)

CART_ATTRIBUTES_UPDATE_MUTATION = (
    CART_FRAGMENT
    + """
mutation cartAttributesUpdate($cartId: ID!, $attributes: [AttributeInput!]!) {
  cartAttributesUpdate(cartId: $cartId, attributes: $attributes) {
    cart {
      ...CartFields
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""
)
