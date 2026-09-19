from locust import HttpUser, task, between
import os


TEST_EMAIL = os.getenv("TEST_EMAIL", "loadtest@example.com")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "Test@12345")


class SaaSUser(HttpUser):
    """One virtual SaaS user: login once, then call authenticated APIs."""

    wait_time = between(1, 3)

    def on_start(self):
        # OAuth2PasswordRequestForm expects form data, not JSON.
        with self.client.post(
            "/api/users/login",
            data={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD,
            },
            name="POST /api/users/login",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"login failed: HTTP {response.status_code}")
                self.token = None
                return

            data = response.json()
            self.token = data.get("access_token")
            if not self.token:
                response.failure("login succeeded but access_token is missing")

        self.headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(5)
    def get_me(self):
        if not self.token:
            return
        self.client.get(
            "/api/users/me",
            headers=self.headers,
            name="GET /api/users/me",
        )

    @task(3)
    def get_wallet(self):
        if not self.token:
            return
        self.client.get(
            "/api/wallet/",
            headers=self.headers,
            name="GET /api/wallet/",
        )

    @task(2)
    def get_api_keys(self):
        if not self.token:
            return
        self.client.get(
            "/api/keys/",
            headers=self.headers,
            name="GET /api/keys/",
        )
