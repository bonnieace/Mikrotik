from locust import HttpUser, task, between
import random
import string
import time

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase, k=length))

def random_phone():
    return f"07{random.randint(10000000, 99999999)}"

class APITestUser(HttpUser):
    wait_time = between(1, 3)  # Simulates a user thinking/clicking

    @task(5)
    def get_packages(self):
        self.client.get("/packages")

    @task(5)
    def get_payments(self):
        self.client.get("/payments")

    @task(2)
    def create_ppp_user(self):
        data = {
            "name": random_string(),
            "email": f"{random_string()}@test.com",
            "pppoe_username": random_string(),
            "pppoe_password": random_string(12),
            "mobile_number": random_phone(),
            "location": random.choice(["Block A", "Block B", "Block C"]),
            "apartment": random.choice(["1A", "2B", "3C"]),
            "profile": random.choice(["basic", "premium", "vip"])
        }
        self.client.post("/ppp_user", params=data)

    @task(1)
    def create_log(self):
        description = f"Automated test log {random_string(5)}"
        phone_number = random_phone()
        self.client.post("/log", params={"description": description, "phone_number": phone_number})

