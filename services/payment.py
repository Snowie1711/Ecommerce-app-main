import requests
import json
import os
import hmac
import hashlib
from datetime import datetime, timedelta
from flask import current_app

class PayOSAPI:
    """
    PayOS Payment API client for handling online payments
    """

    def __init__(self):
        self.api_key = os.environ.get('PAYOS_API_KEY') or current_app.config.get('PAYOS_API_KEY')
        self.client_id = os.environ.get('PAYOS_CLIENT_ID') or current_app.config.get('PAYOS_CLIENT_ID')
        self.checksum_key = os.environ.get('PAYOS_SECRET_KEY') or current_app.config.get('PAYOS_SECRET_KEY')
        self.api_base_url = os.environ.get('PAYOS_API_URL') or current_app.config.get('PAYOS_API_URL', 'https://api-merchant.payos.vn')

        if not self.api_key:
            current_app.logger.error("PayOS API Key is missing")
            raise ValueError("Missing PAYOS_API_KEY. Please set it in your environment or config.")
        if not self.client_id:
            current_app.logger.error("PayOS Client ID is missing")
            raise ValueError("Missing PAYOS_CLIENT_ID. Please set it in your environment or config.")
        if not self.checksum_key:
            current_app.logger.error("PayOS Secret Key is missing")
            raise ValueError("Missing PAYOS_SECRET_KEY. Please set it in your environment or config.")

        current_app.logger.info("PayOS API client initialized successfully")

    def create_payment(self, order_id, amount, description="Payment"):
        try:
            amount = int(amount)
            # Change: Use order_id directly as an integer instead of creating a string with timestamp
            order_code = int(order_id)  # PayOS requires orderCode to be numeric

            payment_data = {
                "orderCode": order_code,
                "amount": amount,
                "description": f"Order #{order_id}",  # Sửa để đồng bộ với phần `items.name`
                "returnUrl": "http://127.0.0.1:5000/payment/success",
                "cancelUrl": "http://127.0.0.1:5000/payment/cancel",
                "items": [
                    {
                    "name": f"Order #{order_id}",
                    "price": amount,
                "quantity": 1
                    }
                ]
            }

            # Create signature with the numeric orderCode
            signature_str = (
                f"amount={payment_data['amount']}"
                f"&cancelUrl={payment_data['cancelUrl']}"
                f"&description={payment_data['description']}"
                f"&orderCode={payment_data['orderCode']}"  # This now uses the numeric value
                f"&returnUrl={payment_data['returnUrl']}"
            )

            signature = hmac.new(
                self.checksum_key.encode('utf-8'),
                signature_str.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            current_app.logger.debug(f"Signature string: {signature_str}")
            current_app.logger.debug(f"Generated signature: {signature}")

            headers = {
                "Content-Type": "application/json",
                "x-client-id": self.client_id,
                "x-api-key": self.api_key,
                "x-signature": signature
            }

            response = requests.post(
                f"{self.api_base_url}/v2/payment-requests",
                headers=headers,
                json=payment_data,
                timeout=15
            )

            current_app.logger.info(f"PayOS response code: {response.status_code}")
            current_app.logger.info(f"PayOS response: {response.text}")

            response_data = response.json()
            if response.status_code == 200 and response_data.get('code') == '00':
                return {
                    'success': True,
                    'payment_url': response_data['data']['checkoutUrl'],
                    'payment_id': response_data['data']['paymentLinkId'],
                    'qr_code': response_data['data']['qrCode']
                }
            else:
                return {
                    'success': False,
                    'error': response_data.get('desc'),
                    'response': response_data
                }

        except Exception as e:
            current_app.logger.exception(f"Exception in PayOS payment creation: {str(e)}")
            return {'success': False, 'error': f"Exception: {str(e)}"}

    def _create_signature(self, data):
        try:
            if not self.checksum_key:
                current_app.logger.error("Cannot create signature: PayOS Secret Key is missing")
                return ""
            data_str = json.dumps(data, separators=(',', ':'), sort_keys=True)
            signature = hmac.new(
                self.checksum_key.encode('utf-8'),
                data_str.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            current_app.logger.debug(f"Generated PayOS signature: {signature[:10]}...{signature[-10:]} (masked)")
            return signature
        except Exception as e:
            current_app.logger.error(f"Error creating signature: {str(e)}")
            return ""

    def verify_payment(self, payment_id):
        try:
            headers = {
                "x-client-id": self.client_id,
                "x-api-key": self.api_key
            }
            endpoint = f"{self.api_base_url}/v2/payment-requests/{payment_id}"
            response = requests.get(endpoint, headers=headers)
            if response.status_code == 200:
                response_data = response.json()
                return {
                    'success': True,
                    'status': response_data.get('status'),
                    'payment_data': response_data
                }
            else:
                error_data = response.json() if response.content else {'message': 'Unknown error'}
                return {
                    'success': False,
                    'error': error_data.get('message', 'Payment verification failed'),
                    'status_code': response.status_code
                }
        except Exception as e:
            current_app.logger.exception(f"Exception in PayOS payment verification: {str(e)}")
            return {'success': False, 'error': f"Payment verification error: {str(e)}"}