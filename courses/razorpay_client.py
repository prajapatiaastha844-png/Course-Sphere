from django.conf import settings
import razorpay


def get_razorpay_client():
    """
    Returns an initialized Razorpay Client instance configured with
    the project's key ID and secret.
    """
    key_id = getattr(settings, "RAZORPAY_KEY_ID", "")
    key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")
    return razorpay.Client(auth=(key_id, key_secret))
