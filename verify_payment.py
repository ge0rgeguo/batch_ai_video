import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def verify_payment_flow():
    # 1. Login
    print("1. Logging in...")
    s = requests.Session()
    # Create a new user for testing
    mobile = "13911112222"
    # Send code
    s.post(f"{BASE_URL}/api/mobile/send-code", json={"mobile": mobile, "scene": "login"})
    # Verify code (mock code is 123456)
    res = s.post(f"{BASE_URL}/api/mobile/verify", json={"mobile": mobile, "code": "123456", "scene": "login"})
    if res.status_code != 200:
        print("Login failed:", res.text)
        sys.exit(1)
    
    user_data = res.json()["data"]
    user_id = user_data["user_id"]
    initial_credits = user_data["credits"]
    print(f"Logged in as {user_id}, credits: {initial_credits}")

    # 2. Create Recharge Order
    print("2. Creating recharge order...")
    res = s.post(f"{BASE_URL}/api/recharge/orders", json={
        "amount": 10.0,
        "payment_method": "alipay"
    })
    if res.status_code != 200:
        print("Create order failed:", res.text)
        sys.exit(1)
    
    order_data = res.json()["data"]
    order_id = order_data["order_id"]
    print(f"Order created: {order_id}")

    # 3. Check Status (Pending)
    print("3. Checking status (should be pending)...")
    res = s.get(f"{BASE_URL}/api/recharge/orders/{order_id}/status")
    status = res.json()["data"]["status"]
    if status != "pending":
        print(f"Unexpected status: {status}")
        sys.exit(1)
    print("Status is pending.")

    # 4. Mock Pay
    print("4. Executing Mock Pay...")
    res = s.post(f"{BASE_URL}/api/mock/pay/{order_id}")
    if res.status_code != 200:
        print("Mock pay failed:", res.text)
        sys.exit(1)
    print("Mock pay success.")

    # 5. Check Status (Paid)
    print("5. Checking status (should be paid)...")
    res = s.get(f"{BASE_URL}/api/recharge/orders/{order_id}/status")
    status = res.json()["data"]["status"]
    if status != "paid":
        print(f"Unexpected status: {status}")
        sys.exit(1)
    print("Status is paid.")

    # 6. Verify Credits
    print("6. Verifying credits increased...")
    res = s.get(f"{BASE_URL}/api/me")
    new_credits = res.json()["data"]["credits"]
    expected_credits = initial_credits + 100 # 10.0 -> 100 credits
    if new_credits != expected_credits:
        print(f"Credits mismatch! Expected {expected_credits}, got {new_credits}")
        sys.exit(1)
    print(f"Credits verified: {new_credits}")

    print("\n✅ Payment Flow Verified Successfully!")

if __name__ == "__main__":
    verify_payment_flow()
