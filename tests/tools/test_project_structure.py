import unittest
import os


class TestProjectStructure(unittest.TestCase):
    """Test that the tools project structure is correctly created."""

    def test_tools_directory_exists(self):
        """Test that the tools directory exists."""
        tools_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'tools')
        self.assertTrue(os.path.exists(tools_dir))
        self.assertTrue(os.path.isdir(tools_dir))

    def test_tools_init_file_exists(self):
        """Test that the tools/__init__.py file exists."""
        init_file = os.path.join(os.path.dirname(__file__), '..', '..', 'tools', '__init__.py')
        self.assertTrue(os.path.exists(init_file))
        self.assertTrue(os.path.isfile(init_file))

    def test_tools_module_can_be_imported(self):
        """Test that the tools module can be imported."""
        try:
            import tools
            self.assertTrue(True)
        except ImportError:
            self.fail("tools module could not be imported")


if __name__ == '__main__':
    unittest.main()