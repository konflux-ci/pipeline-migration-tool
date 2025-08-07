import copy
import os
import tempfile
import textwrap
from pathlib import Path
from collections.abc import Sequence
from typing import Union, TypeAlias, Any
from io import StringIO


from pipeline_migration.utils import load_yaml, create_yaml_obj, YAMLStyle


YAMLPath: TypeAlias = Sequence[Union[int, str]]


class EditYAMLEntry:

    def __init__(self, yaml_file_path: Path, style: YAMLStyle | None = None):
        self.yaml_file_path = yaml_file_path
        self.style = style
        self._data = None

    @property
    def data(self):
        if self._data is None:
            self._data = load_yaml(self.yaml_file_path)
        return self._data

    @data.deleter
    def data(self):
        self._data = None

    def invalidate_yaml_data(self):
        del self.data

    def _get_path_stack(self, path: YAMLPath):
        path_stack: list[tuple[Any, int | str | None]] = []
        current_data = self.data
        for p in path:
            assert isinstance(p, (int, str))
            path_stack.append((current_data, p))
            current_data = current_data[p]
        path_stack.append((current_data, None))  # terminal node
        return path_stack

    def insert(self, path: YAMLPath, data: Any):
        """Insert data into mapping or sequence, parent node must be specified as path"""
        path_stack = self._get_path_stack(path)
        last_node, _ = path_stack[-1]

        # the same way as ruamel-yaml checks for it's objects; dict/list instance and `hasattr`
        assert isinstance(last_node, (dict, list)) and hasattr(last_node, "lc")

        yaml_str = self._gen_yaml_str(
            data, last_node.lc.col, seq_block=True if isinstance(last_node, list) else False
        )

        # Appending as last item
        lineno = 10000000000  # fallback if sibling doesn't exist, append to the end
        next_entry_line = self._get_next_entry_line(path_stack)
        if next_entry_line is not None:
            # insert before the next entry
            lineno = next_entry_line
        insert_text_at_line(
            self.yaml_file_path, lineno, yaml_str, validation_callback=post_test_yaml_validity
        )
        self.invalidate_yaml_data()

    def replace(self, path: YAMLPath, data: Any):
        path_stack = self._get_path_stack(path)
        last_node, _ = path_stack[-1]
        assert isinstance(last_node, (dict, list)) and hasattr(last_node, "lc")

        # replacing at the same position
        lineno = last_node.lc.line
        if self._is_parent_dict(path_stack):
            # dictionaries in ruamel are reporting 1 extra line
            lineno = max(lineno - 1, 0)

        # get indentation
        # ensure we are not at the root element
        # if it's root node, happy guess indentation is 0?
        col = 0
        seq_block = False
        if len(path_stack) > 1:
            # use indentation defined in the parent node
            parent_node, _ = path_stack[-2]
            assert isinstance(parent_node, (dict, list)) and hasattr(parent_node, "lc")
            col = parent_node.lc.col

            if isinstance(parent_node, list):
                seq_block = True

        yaml_str = self._gen_yaml_str(data, col, seq_block=seq_block)

        # first we need to remove old content, that could be
        # longer or shorter in matter of text lines
        next_entry_line = self._get_next_entry_line(path_stack)
        if next_entry_line is None:  # this means EOF
            remove_lines_num = -1
        else:
            remove_lines_num = next_entry_line - lineno

        insert_text_at_line(
            self.yaml_file_path,
            lineno,
            yaml_str,
            replace_lines=remove_lines_num,
            validation_callback=post_test_yaml_validity,
        )
        self.invalidate_yaml_data()

    def delete(self, path: YAMLPath):
        # TODO cascading deletions if parent is empty, or dump just empty dict/list

        path_stack = self._get_path_stack(path)
        last_node, _ = path_stack[-1]

        assert isinstance(last_node, (dict, list)) and hasattr(last_node, "lc")
        # removing from the node position
        lineno = last_node.lc.line
        if self._is_parent_dict(path_stack):
            # dictionaries in ruamel are reporting 1 extra line
            lineno = max(lineno - 1, 0)

        # remove old content till next element
        next_entry_line = self._get_next_entry_line(path_stack)
        if next_entry_line is None:  # this means EOF
            remove_lines_num = -1
        else:
            remove_lines_num = next_entry_line - lineno
        remove_lines_from_file(
            self.yaml_file_path,
            lineno,
            remove_lines_num,
            validation_callback=post_test_yaml_validity,
        )
        self.invalidate_yaml_data()

    def _is_parent_dict(self, path_stack):
        if len(path_stack) > 1:
            parent, _ = path_stack[-2]
            return isinstance(parent, dict)
        return False

    def _get_next_entry_line(self, path_stack):
        """find lineno where the next item in yaml starts"""
        path_stack = copy.copy(path_stack)

        def find_next_sibling(node, index):
            if isinstance(node, list):
                assert isinstance(index, int)
                if len(node) - 1 > index:
                    return node[index + 1]  # sibling is just next item in array
            elif isinstance(node, dict):
                # TODO: dict object doesn't return location of the key, but location of
                # the first value, thus, it cannot correctly guess the exact line
                # (there could be N newlines, we cannot just use -1)

                assert isinstance(index, str)
                # we rely on python dict feature that ordering is kept
                keys = tuple(node.keys())
                key_idx = keys.index(index)
                if len(keys) - 1 > key_idx:
                    return node[keys[key_idx + 1]]

            # other types cannot be used to find siblings
            # sibling doesn't exist
            return None

        while path_stack:
            current = path_stack.pop()
            node, index = current
            if index is None:
                # terminal element, we cannot find sibling from this level
                continue
            sibling = find_next_sibling(node, index)
            if sibling is None:
                # sibling doesn't exist, continue to next level
                continue

            assert hasattr(sibling, "lc")
            line = sibling.lc.line

            # if (parent) node is dict, ruamel reports line+1 for key, get the real position
            if isinstance(node, dict):
                line = max(line - 1, 0)

            return line

        return None  # cannot calculate, probably EOF

    def _gen_yaml_str(self, data: Any, col: int, seq_block=False) -> str:
        if seq_block:
            data = [data]
        yaml = create_yaml_obj(style=self.style)
        stream = StringIO()
        yaml.dump(
            data,
            stream=stream,
        )
        yaml_output = stream.getvalue()

        # Indent each line of the YAML output by the column position
        indented = textwrap.indent(yaml_output, " " * col)
        return indented


def post_test_yaml_validity(path):
    """Validate if update yaml is valid

    Given how this tool operates, it may happen that generated YAML isn't valid.
    Rather fail early than provide false positive success.
    """
    try:
        load_yaml(path)
    except Exception as e:
        raise RuntimeError("post-check: generated YAML is not valid") from e


def remove_lines_from_file(
    file_path: Path, start_line: int, num_lines: int, validation_callback=None
) -> None:
    """
    Remove a block of text from a file without loading the entire file into memory.

    Args:
        file_path (Path): Path to the file to modify
        start_line (int): Line number where removal should start (0-indexed)
        num_lines (int): Number of lines to remove (negative value mean till EOF)

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If start_line or num_lines are invalid
        IOError: If there's an error reading or writing the file
    """
    if start_line < 0:
        raise ValueError("start_line must be >= 0")

    if num_lines == 0:
        return  # Nothing to remove

    # start_line is already 0-indexed
    start_index = start_line

    end_index = start_index + num_lines
    if num_lines < 0:  # till EOF
        end_index = -1

    # Create a temporary file in the same directory as the original
    temp_dir = os.path.dirname(file_path) or "."
    temp_fd, temp_path = tempfile.mkstemp(dir=temp_dir, text=True)

    try:
        with (
            os.fdopen(temp_fd, "w", encoding="utf-8") as temp_file,
            open(file_path, "r", encoding="utf-8") as original_file,
        ):
            current_line = 0

            for line in original_file:
                # Copy lines before the removal range
                if current_line < start_index:
                    temp_file.write(line)
                # Skip lines in the removal range
                elif current_line < end_index or end_index < 0:  # till EOF
                    pass  # Skip this line
                # Copy lines after the removal range
                else:
                    temp_file.write(line)

                current_line += 1

            # Check if start_line was beyond the file length
            if start_index >= current_line:
                raise ValueError(
                    f"start_line ({start_line}) is beyond the file "
                    f"length (max index: {current_line - 1})"
                )

        if validation_callback is not None:
            validation_callback(temp_path)

        # Atomically replace the original file with the temporary file
        os.replace(temp_path, file_path)

    except Exception:
        # Clean up temporary file if something went wrong
        try:
            os.unlink(temp_path)
        except OSError:
            pass  # Ignore cleanup errors
        raise


def insert_text_at_line(
    file_path: Path,
    line_number: int,
    text_to_insert: str,
    replace_lines: int = 0,
    validation_callback=None,
) -> None:
    """
    Insert or replace multiline text at a specified line number.

    Args:
        file_path(Path): Path to the file to modify
        line_number (int): Line number where text should be inserted (0-indexed)
        text_to_insert (str): Text to insert or replace with (can be multiline)
        replace_lines (int): If positive value is defined replace
                       a number of lines equal to the specified value.
                       (Default 0, no replacing)

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If line_number is invalid
        IOError: If there's an error reading or writing the file
    """
    if line_number < 0:
        raise ValueError("line_number must be >= 0")

    # line_number is already 0-indexed
    insert_index = line_number

    # Ensure text_to_insert ends with newline if it doesn't already
    if text_to_insert is not None and not text_to_insert.endswith("\n"):
        text_to_insert += "\n"

    # Create a temporary file in the same directory as the original
    temp_dir = os.path.dirname(file_path) or "."
    temp_fd, temp_path = tempfile.mkstemp(dir=temp_dir, text=True)

    try:
        with (
            os.fdopen(temp_fd, "w", encoding="utf-8") as temp_file,
            open(file_path, "r", encoding="utf-8") as original_file,
        ):
            current_line = 0
            replacing_lines_in_progress = 0

            for line in original_file:
                if replacing_lines_in_progress > 0:
                    replacing_lines_in_progress -= 1
                    current_line += 1
                    continue

                if current_line == insert_index:
                    # Write the new text
                    temp_file.write(text_to_insert)
                    if replace_lines > 0:
                        # one line is removed as part of this (with continue statement)
                        replacing_lines_in_progress = replace_lines - 1
                        current_line += 1
                        continue
                    elif replace_lines < 0:
                        # replacing till EOF
                        current_line += 1  # increase counter before break, so we don't insert again
                        break

                    temp_file.write(line)
                else:
                    # Copy the original line
                    temp_file.write(line)

                current_line += 1

            # Handle case where line_number is beyond file length, append at the end
            if current_line <= insert_index:
                temp_file.write(text_to_insert)

        if validation_callback is not None:
            validation_callback(temp_path)

        # Atomically replace the original file with the temporary file
        os.replace(temp_path, file_path)

    except Exception:
        # Clean up temporary file if something went wrong
        try:
            os.unlink(temp_path)
        except OSError:
            pass  # Ignore cleanup errors
        raise
