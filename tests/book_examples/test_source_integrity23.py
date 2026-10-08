import unittest

from tests.book_examples.helpers23 import EXAMPLES, REPOSITORY


class SourceIntegrityTests(unittest.TestCase):
    def test_complete_topology_model_is_byte_identical_to_archive(self):
        self.assertEqual((REPOSITORY / "core" / "book_examples" / "chapter03" / "topologies.py").read_bytes(),
                         (EXAMPLES / "archive" / "03" / "03-05.py").read_bytes())
