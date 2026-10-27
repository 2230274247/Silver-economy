import unittest

from security_scan import violations


class SecurityScanTests(unittest.TestCase):
    def test_private_environment_file_is_rejected(self):
        self.assertTrue(violations(".env", "NAME=value"))
        self.assertTrue(violations("services/api/.env.local", "NAME=value"))

    def test_empty_example_is_allowed(self):
        self.assertEqual(violations(".env.example", "DEEPSEEK_API_KEY="), [])

    def test_secret_is_rejected_even_in_example(self):
        self.assertTrue(violations(".env.example", "KEY=" + "sk-" + "x" * 32))

    def test_private_data_file_is_rejected(self):
        self.assertTrue(violations("uploads/person.txt", "data"))
        self.assertTrue(violations("services/api/test.db", "data"))

    def test_regular_source_is_allowed(self):
        self.assertEqual(violations("services/api/app/main.py", "import fastapi"), [])

    def test_amap_key_assignment_is_rejected_without_rejecting_empty_config(self):
        fake = "a" * 32
        self.assertTrue(violations("config.py", 'amap_web_service_key="' + fake + '"'))
        self.assertTrue(
            violations("config.json", '{"AMAP_WEB_SERVICE_KEY":"' + fake + '"}')
        )
        self.assertEqual(violations(".env.example", "AMAP_WEB_SERVICE_KEY="), [])


if __name__ == "__main__":
    unittest.main()
