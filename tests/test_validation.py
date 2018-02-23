import unittest

from sf_dia.validation import validate_writer_config
from tests.utils import get_valid_config


class TestValidation(unittest.TestCase):

    def test_user_id_range(self):
        writer_config = get_valid_config()["writer"]

        # This config should be valid.
        validate_writer_config(writer_config)

        writer_config["user_id"] = 10000
        validate_writer_config(writer_config)

        writer_config["user_id"] = 29999
        validate_writer_config(writer_config)

        with self.assertRaisesRegex(ValueError, "Provided user_id"):
            writer_config["user_id"] = 9999
            validate_writer_config(writer_config)

        with self.assertRaisesRegex(ValueError, "Provided user_id"):
            writer_config["user_id"] = 30000
            validate_writer_config(writer_config)

    def test_additional_fields(self):
        writer_config = get_valid_config()["writer"]

        with self.assertRaisesRegex(ValueError, "Received unexpected parameters"):
            writer_config["unexpected"] = "jup"
            validate_writer_config(writer_config)