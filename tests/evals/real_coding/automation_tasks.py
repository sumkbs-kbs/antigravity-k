from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AutomationTask:
    task_id: str
    difficulty: str
    prompt: str
    setup_files: dict[str, str]
    verify: str


TASKS: tuple[AutomationTask, ...] = (
    AutomationTask(
        task_id="create_file",
        difficulty="easy",
        prompt=(
            "Create a file named config.json with valid JSON containing keys "
            '"name" set to "app" and "version" set to "1.0.0".'
        ),
        setup_files={},
        verify=(
            "import json\n"
            "d = json.load(open('config.json'))\n"
            "assert d['name'] == 'app'\n"
            "assert d['version'] == '1.0.0'\n"
        ),
    ),
    AutomationTask(
        task_id="write_csv",
        difficulty="easy",
        prompt=(
            "Create a file data.csv with a header row 'id,name,score' followed "
            "by exactly three data rows: (1,Alice,90), (2,Bob,85), (3,Carol,95)."
        ),
        setup_files={},
        verify=(
            "lines = open('data.csv').read().strip().split('\\n')\n"
            "assert lines[0] == 'id,name,score'\n"
            "assert len(lines) == 4\n"
            "assert 'Alice' in lines[1] and '90' in lines[1]\n"
            "assert 'Carol' in lines[3] and '95' in lines[3]\n"
        ),
    ),
    AutomationTask(
        task_id="modify_file",
        difficulty="medium",
        prompt=(
            "The file settings.txt exists with content. Append a new line "
            "'debug=true' to the end of it without removing existing content."
        ),
        setup_files={"settings.txt": "host=localhost\nport=8080\n"},
        verify=(
            "text = open('settings.txt').read()\n"
            "assert 'host=localhost' in text\n"
            "assert 'port=8080' in text\n"
            "assert 'debug=true' in text\n"
        ),
    ),
    AutomationTask(
        task_id="transform_data",
        difficulty="medium",
        prompt=(
            "A file numbers.json exists containing a JSON object with key "
            '"values" mapping to a list of integers. Create a new file '
            'sums.json containing a JSON object with key "total" set to the '
            'sum of those integers and key "count" set to how many there '
            "were."
        ),
        setup_files={"numbers.json": '{"values": [10, 20, 5, 15]}'},
        verify=(
            "import json\n"
            "src = json.load(open('numbers.json'))\n"
            "out = json.load(open('sums.json'))\n"
            "assert out['total'] == sum(src['values'])\n"
            "assert out['count'] == len(src['values'])\n"
        ),
    ),
    AutomationTask(
        task_id="reorganize_files",
        difficulty="hard",
        prompt=(
            "Three files exist: a.txt, b.txt, c.txt. Create a directory named "
            "'archive' and move all three files into it. The original files "
            "must no longer exist in the current directory."
        ),
        setup_files={"a.txt": "alpha", "b.txt": "bravo", "c.txt": "charlie"},
        verify=(
            "from pathlib import Path\n"
            "assert not Path('a.txt').exists() and not Path('b.txt').exists() and not Path('c.txt').exists()\n"
            "d = Path('archive')\n"
            "assert d.is_dir()\n"
            "assert (d / 'a.txt').is_file() and (d / 'b.txt').is_file() and (d / 'c.txt').is_file()\n"
            "assert (d / 'a.txt').read_text() == 'alpha'\n"
        ),
    ),
    AutomationTask(
        task_id="merge_logs",
        difficulty="hard",
        prompt=(
            "Two log files exist: error.log and access.log. Create a combined "
            "file all.log that contains every line from both files, with "
            "error.log lines first then access.log lines, and prefix each line "
            "with its source: 'ERROR: ' for error.log lines, 'ACCESS: ' for "
            "access.log lines."
        ),
        setup_files={"error.log": "disk full\ntimeout\n", "access.log": "GET /\nPOST /login\n"},
        verify=(
            "lines = open('all.log').read().strip().split('\\n')\n"
            "assert lines[0] == 'ERROR: disk full'\n"
            "assert lines[1] == 'ERROR: timeout'\n"
            "assert lines[2] == 'ACCESS: GET /'\n"
            "assert lines[3] == 'ACCESS: POST /login'\n"
            "assert len(lines) == 4\n"
        ),
    ),
)
