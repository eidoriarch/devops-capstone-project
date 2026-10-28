
"""
Account API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
"""
import os
import logging
from unittest import TestCase

from tests.factories import AccountFactory
from service.common import status
from service.models import db, Account, init_db
from service import talisman
from service.routes import app

DATABASE_URI = os.getenv(
    "DATABASE_URI",
    "postgresql://postgres:postgres@localhost:5432/postgres",
)

BASE_URL = "/accounts"
HTTPS_ENVIRON = {"wsgi.url_scheme": "https"}


######################################################################
# T E S T   C A S E S
######################################################################
class TestAccountService(TestCase):
    """Account Service Tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)

        # Disable HTTPS redirects during testing
        talisman.force_https = False

        init_db(app)

    @classmethod
    def tearDownClass(cls):
        """Runs once after all tests"""

    def setUp(self):
        """Runs before each test"""
        db.session.query(Account).delete()
        db.session.commit()
        self.client = app.test_client()

    def tearDown(self):
        """Runs after each test"""
        db.session.remove()

    ##################################################################
    # SECURITY HEADER TESTS
    ##################################################################

    def test_security_headers(self):
        """It should return the expected security headers over HTTPS"""
        response = self.client.get(
            "/",
            environ_overrides=HTTPS_ENVIRON,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(
            response.headers.get("X-Frame-Options"),
            "SAMEORIGIN",
        )
        self.assertEqual(
            response.headers.get("X-Content-Type-Options"),
            "nosniff",
        )
        self.assertEqual(
            response.headers.get("Content-Security-Policy"),
            "default-src 'self'; object-src 'none'",
        )
        self.assertEqual(
            response.headers.get("Referrer-Policy"),
            "strict-origin-when-cross-origin",
        )

    ##################################################################
    # HELPER METHODS
    ##################################################################

    def _create_accounts(self, count):
        """Factory method to create accounts in bulk"""
        accounts = []

        for _ in range(count):
            account = AccountFactory()
            response = self.client.post(
                BASE_URL,
                json=account.serialize(),
                content_type="application/json",
            )

            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                "Could not create test Account",
            )

            new_account = response.get_json()
            account.id = new_account["id"]
            accounts.append(account)

        return accounts

    ##################################################################
    # BASIC ENDPOINT TESTS
    ##################################################################

    def test_index(self):
        """It should get 200_OK from the Home Page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health(self):
        """It should be healthy"""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.get_json()
        self.assertEqual(data["status"], "OK")

    ##################################################################
    # CREATE ACCOUNT TESTS
    ##################################################################

    def test_create_account(self):
        """It should Create a new Account"""
        account = AccountFactory()

        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        location = response.headers.get("Location")
        self.assertIsNotNone(location)

        new_account = response.get_json()

        self.assertEqual(new_account["name"], account.name)
        self.assertEqual(new_account["email"], account.email)
        self.assertEqual(new_account["address"], account.address)
        self.assertEqual(
            new_account["phone_number"],
            account.phone_number,
        )
        self.assertEqual(
            new_account["date_joined"],
            str(account.date_joined),
        )

    def test_bad_request(self):
        """It should reject incomplete account data"""
        response = self.client.post(
            BASE_URL,
            json={"name": "not enough data"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_unsupported_media_type(self):
        """It should reject an unsupported media type"""
        account = AccountFactory()

        response = self.client.post(
            BASE_URL,
            data=account.serialize().__str__(),
            content_type="text/html",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )

    ##################################################################
    # READ ACCOUNT TESTS
    ##################################################################

    def test_get_account(self):
        """It should Read a single Account"""
        account = self._create_accounts(1)[0]

        response = self.client.get(
            f"{BASE_URL}/{account.id}",
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        data = response.get_json()
        self.assertEqual(data["id"], account.id)
        self.assertEqual(data["name"], account.name)
        self.assertEqual(data["email"], account.email)
        self.assertEqual(data["address"], account.address)
        self.assertEqual(
            data["phone_number"],
            account.phone_number,
        )

    def test_get_account_not_found(self):
        """It should return 404 when an Account is not found"""
        response = self.client.get(f"{BASE_URL}/0")

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    ##################################################################
    # LIST ACCOUNTS TESTS
    ##################################################################

    def test_get_account_list(self):
        """It should Get a list of Accounts"""
        self._create_accounts(5)

        response = self.client.get(
            BASE_URL,
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        data = response.get_json()
        self.assertEqual(len(data), 5)

    def test_get_account_list_no_accounts(self):
        """It should return an empty list when no Accounts exist"""
        response = self.client.get(
            BASE_URL,
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        data = response.get_json()
        self.assertEqual(data, [])

    ##################################################################
    # UPDATE ACCOUNT TESTS
    ##################################################################

    def test_update_account(self):
        """It should Update an existing Account"""
        account = self._create_accounts(1)[0]

        updated_data = account.serialize().copy()
        updated_data["name"] = "Updated Test Account"

        response = self.client.put(
            f"{BASE_URL}/{account.id}",
            json=updated_data,
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        data = response.get_json()
        self.assertEqual(data["id"], account.id)
        self.assertEqual(data["name"], "Updated Test Account")

    def test_update_account_not_found(self):
        """It should return 404 when updating a missing Account"""
        account = AccountFactory()

        response = self.client.put(
            f"{BASE_URL}/0",
            json=account.serialize(),
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    ##################################################################
    # DELETE ACCOUNT TESTS
    ##################################################################

    def test_delete_account(self):
        """It should Delete an existing Account"""
        account = self._create_accounts(1)[0]

        response = self.client.delete(
            f"{BASE_URL}/{account.id}",
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        response = self.client.get(f"{BASE_URL}/{account.id}")

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_delete_account_not_found(self):
        """It should return 404 when deleting a missing Account"""
        response = self.client.delete(f"{BASE_URL}/0")

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
