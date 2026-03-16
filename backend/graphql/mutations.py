SESSION_CREATE_MUTATION = """
mutation shopPayPaymentRequestSessionCreate(
  $sourceIdentifier: String!
  $paymentRequest: ShopPayPaymentRequestInput!
) {
  shopPayPaymentRequestSessionCreate(
    sourceIdentifier: $sourceIdentifier
    paymentRequest: $paymentRequest
  ) {
    shopPayPaymentRequestSession {
      token
      sourceIdentifier
      checkoutUrl
      paymentRequest {
        subtotal { amount currencyCode }
        total { amount currencyCode }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

SESSION_SUBMIT_MUTATION = """
mutation shopPayPaymentRequestSessionSubmit(
  $token: String!
  $paymentRequest: ShopPayPaymentRequestInput!
  $idempotencyKey: String!
  $orderName: String
) {
  shopPayPaymentRequestSessionSubmit(
    token: $token
    paymentRequest: $paymentRequest
    idempotencyKey: $idempotencyKey
    orderName: $orderName
  ) {
    paymentRequestReceipt {
      token
      processingStatusType
    }
    userErrors {
      field
      message
    }
  }
}
"""
