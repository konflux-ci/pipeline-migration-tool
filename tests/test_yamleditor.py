import pytest
import tempfile
import os
from textwrap import dedent

from pipeline_migration.yamleditor import remove_lines_from_file, insert_text_at_line


@pytest.fixture
def temp_file_with_content():
    """Create a temporary file with sample content for testing."""
    content = dedent("""\
        Line 1
        Line 2
        Line 3
        Line 4
        Line 5
        Line 6
        Line 7
        """)

    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
        f.write(content)
        temp_path = f.name

    yield temp_path

    # Cleanup
    try:
        os.unlink(temp_path)
    except OSError:
        pass


@pytest.fixture
def empty_temp_file():
    """Create an empty temporary file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
        temp_path = f.name

    yield temp_path

    # Cleanup
    try:
        os.unlink(temp_path)
    except OSError:
        pass


def read_file_content(file_path: str) -> str:
    """Helper function to read file content."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


class TestRemoveLinesFromFile:
    """Test cases for remove_lines_from_file function."""

    def test_remove_lines_from_middle(self, temp_file_with_content):
        """Test removing lines from the middle of the file."""
        remove_lines_from_file(temp_file_with_content, start_line=2, num_lines=2)

        expected = dedent("""\
            Line 1
            Line 2
            Line 5
            Line 6
            Line 7
            """)

        assert read_file_content(temp_file_with_content) == expected

    def test_remove_lines_from_beginning(self, temp_file_with_content):
        """Test removing lines from the beginning of the file."""
        remove_lines_from_file(temp_file_with_content, start_line=0, num_lines=2)

        expected = dedent("""\
            Line 3
            Line 4
            Line 5
            Line 6
            Line 7
            """)

        assert read_file_content(temp_file_with_content) == expected

    def test_remove_lines_from_end(self, temp_file_with_content):
        """Test removing lines from the end of the file."""
        remove_lines_from_file(temp_file_with_content, start_line=5, num_lines=2)

        expected = dedent("""\
            Line 1
            Line 2
            Line 3
            Line 4
            Line 5
            """)

        assert read_file_content(temp_file_with_content) == expected

    def test_remove_more_lines_than_exist(self, temp_file_with_content):
        """Test removing more lines than exist in the file."""
        remove_lines_from_file(temp_file_with_content, start_line=4, num_lines=10)

        expected = dedent("""\
            Line 1
            Line 2
            Line 3
            Line 4
            """)

        assert read_file_content(temp_file_with_content) == expected

    def test_remove_zero_lines(self, temp_file_with_content):
        """Test removing zero lines (should do nothing)."""
        original_content = read_file_content(temp_file_with_content)
        remove_lines_from_file(temp_file_with_content, start_line=2, num_lines=0)

        assert read_file_content(temp_file_with_content) == original_content

    def test_remove_all_lines(self, temp_file_with_content):
        """Test removing all lines from the file."""
        remove_lines_from_file(temp_file_with_content, start_line=0, num_lines=10)

        assert read_file_content(temp_file_with_content) == ""

    def test_invalid_start_line_negative(self, temp_file_with_content):
        """Test error when start_line is negative."""
        with pytest.raises(ValueError, match="start_line must be >= 0"):
            remove_lines_from_file(temp_file_with_content, start_line=-1, num_lines=1)

    def test_invalid_num_lines_negative(self, temp_file_with_content):
        """Test error when num_lines is negative."""
        with pytest.raises(ValueError, match="num_lines must be >= 0"):
            remove_lines_from_file(temp_file_with_content, start_line=0, num_lines=-1)

    def test_start_line_beyond_file_length(self, temp_file_with_content):
        """Test error when start_line is beyond file length."""
        with pytest.raises(ValueError, match="start_line \\(10\\) is beyond the file length \\(max index: 6\\)"):
            remove_lines_from_file(temp_file_with_content, start_line=10, num_lines=1)

    def test_file_not_found(self):
        """Test error when file doesn't exist."""
        with pytest.raises(FileNotFoundError, match="File 'nonexistent.txt' not found"):
            remove_lines_from_file("nonexistent.txt", start_line=1, num_lines=1)

    def test_remove_from_empty_file(self, empty_temp_file):
        """Test removing lines from an empty file."""
        with pytest.raises(ValueError, match="start_line \\(0\\) is beyond the file length \\(max index: -1\\)"):
            remove_lines_from_file(empty_temp_file, start_line=0, num_lines=1)


class TestInsertTextAtLine:
    """Test cases for insert_text_at_line function."""

    def test_insert_single_line_at_beginning(self, temp_file_with_content):
        """Test inserting a single line at the beginning."""
        insert_text_at_line(temp_file_with_content, 0, "New Line 0")

        expected = dedent("""\
            New Line 0
            Line 1
            Line 2
            Line 3
            Line 4
            Line 5
            Line 6
            Line 7
            """)

        assert read_file_content(temp_file_with_content) == expected

    def test_insert_single_line_in_middle(self, temp_file_with_content):
        """Test inserting a single line in the middle."""
        insert_text_at_line(temp_file_with_content, 3, "New Line 3.5")

        expected = dedent("""\
            Line 1
            Line 2
            Line 3
            New Line 3.5
            Line 4
            Line 5
            Line 6
            Line 7
            """)

        assert read_file_content(temp_file_with_content) == expected

    def test_insert_multiple_lines(self, temp_file_with_content):
        """Test inserting multiple lines."""
        multiline_text = dedent("""\
            New Line A
            New Line B
            New Line C""")

        insert_text_at_line(temp_file_with_content, 2, multiline_text)

        expected = dedent("""\
            Line 1
            Line 2
            New Line A
            New Line B
            New Line C
            Line 3
            Line 4
            Line 5
            Line 6
            Line 7
            """)

        assert read_file_content(temp_file_with_content) == expected

    def test_insert_beyond_file_length(self, temp_file_with_content):
        """Test inserting beyond file length (should append)."""
        insert_text_at_line(temp_file_with_content, 10, "Appended Line")

        expected = dedent("""\
            Line 1
            Line 2
            Line 3
            Line 4
            Line 5
            Line 6
            Line 7
            Appended Line
            """)

        assert read_file_content(temp_file_with_content) == expected

    def test_replace_single_line(self, temp_file_with_content):
        """Test replacing a single line."""
        insert_text_at_line(temp_file_with_content, 2, "Replaced Line 3", replace=True)

        expected = dedent("""\
            Line 1
            Line 2
            Replaced Line 3
            Line 4
            Line 5
            Line 6
            Line 7
            """)

        assert read_file_content(temp_file_with_content) == expected

    def test_replace_multiple_lines(self, temp_file_with_content):
        """Test replacing multiple lines."""
        multiline_replacement = dedent("""\
            Replacement Line A
            Replacement Line B
            Replacement Line C""")

        insert_text_at_line(temp_file_with_content, 1, multiline_replacement, replace=True)

        expected = dedent("""\
            Line 1
            Replacement Line A
            Replacement Line B
            Replacement Line C
            Line 5
            Line 6
            Line 7
            """)

        assert read_file_content(temp_file_with_content) == expected

    def test_replace_beyond_file_length(self, temp_file_with_content):
        """Test replacing beyond file length (should raise error)."""
        with pytest.raises(ValueError, match="Cannot replace line 10: file only has 7 lines \\(max index: 6\\)"):
            insert_text_at_line(temp_file_with_content, 10, "Replacement", replace=True)

    def test_replace_exactly_at_end(self, temp_file_with_content):
        """Test replacing the last line."""
        insert_text_at_line(temp_file_with_content, 6, "New Last Line", replace=True)

        expected = dedent("""\
            Line 1
            Line 2
            Line 3
            Line 4
            Line 5
            Line 6
            New Last Line
            """)

        assert read_file_content(temp_file_with_content) == expected

    def test_insert_empty_text(self, temp_file_with_content):
        """Test inserting empty text."""
        original_content = read_file_content(temp_file_with_content)
        insert_text_at_line(temp_file_with_content, 2, "")

        # Should add just a newline
        expected = dedent("""\
            Line 1
            Line 2

            Line 3
            Line 4
            Line 5
            Line 6
            Line 7
            """)

        assert read_file_content(temp_file_with_content) == expected

    def test_insert_text_without_newline(self, temp_file_with_content):
        """Test inserting text without trailing newline (should add one)."""
        insert_text_at_line(temp_file_with_content, 2, "Text without newline")

        expected = dedent("""\
            Line 1
            Line 2
            Text without newline
            Line 3
            Line 4
            Line 5
            Line 6
            Line 7
            """)

        assert read_file_content(temp_file_with_content) == expected

    def test_invalid_line_number_negative(self, temp_file_with_content):
        """Test error when line_number is negative."""
        with pytest.raises(ValueError, match="line_number must be >= 0"):
            insert_text_at_line(temp_file_with_content, -1, "Text")

    def test_file_not_found_insert(self):
        """Test error when file doesn't exist for insertion."""
        with pytest.raises(FileNotFoundError, match="File 'nonexistent.txt' not found"):
            insert_text_at_line("nonexistent.txt", 1, "Text")

    def test_insert_into_empty_file(self, empty_temp_file):
        """Test inserting into an empty file."""
        insert_text_at_line(empty_temp_file, 0, "First Line")

        expected = "First Line\n"
        assert read_file_content(empty_temp_file) == expected

    def test_replace_in_empty_file(self, empty_temp_file):
        """Test replacing in an empty file (should raise error)."""
        with pytest.raises(ValueError, match="Cannot replace line 0: file only has 0 lines \\(max index: -1\\)"):
            insert_text_at_line(empty_temp_file, 0, "Text", replace=True)