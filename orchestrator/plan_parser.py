"""Plan parser for milestone markdown files.

Parses markdown plan files to extract Task objects for orchestrator execution.
Handles various markdown formats with lenient parsing.
"""

import re
from pathlib import Path

from orchestrator.models import Task


def parse_plan(plan_path: str | Path) -> list[Task]:
    """Parse a milestone plan file and extract tasks.

    Args:
        plan_path: Path to the markdown plan file

    Returns:
        List of Task objects extracted from the plan
    """
    plan_path = Path(plan_path)
    content = plan_path.read_text()

    # Extract milestone ID from first heading
    milestone_id = _extract_milestone_id(content)

    # Split content into task sections
    task_sections = _split_into_task_sections(content)

    tasks = []
    for section in task_sections:
        task = _parse_task_section(section, str(plan_path), milestone_id)
        if task:
            tasks.append(task)

    return tasks


def _extract_milestone_id(content: str) -> str:
    """Extract milestone ID from the plan content.

    Looks for patterns like:
    - # Milestone 2: Title
    - # M2: Title
    """
    # Match "Milestone N" or "M<N>" in first heading
    match = re.search(r"^#\s+(?:Milestone\s+)?(\d+|M\d+)", content, re.MULTILINE)
    if match:
        milestone_num = match.group(1)
        # Normalize to M<N> format
        if milestone_num.startswith("M"):
            return milestone_num
        return f"M{milestone_num}"
    return "M0"  # Default if not found


def _split_into_task_sections(content: str) -> list[str]:
    """Split content into individual task sections.

    Tasks are identified by headers like:
    - ## Task 2.1: Title
    - ### Task 2.1: Title
    """
    # Pattern to match task headers
    task_pattern = r"^#{2,3}\s+Task\s+\d+\.\d+:"

    # Find all task header positions
    matches = list(re.finditer(task_pattern, content, re.MULTILINE))

    if not matches:
        return []

    sections = []
    for i, match in enumerate(matches):
        start = match.start()
        # End is either next task or end of content
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections.append(content[start:end])

    return sections


def _parse_task_section(section: str, plan_file: str, milestone_id: str) -> Task | None:
    """Parse a single task section into a Task object."""
    # Extract task ID and title from header
    header_match = re.match(
        r"^#{2,3}\s+Task\s+(\d+\.\d+):\s*(.+?)$", section, re.MULTILINE
    )
    if not header_match:
        return None

    task_id = header_match.group(1)
    title = header_match.group(2).strip()

    # Extract file path (singular or plural)
    file_path = _extract_file_path(section)

    # Extract description
    description = _extract_description(section)

    # Extract acceptance criteria
    acceptance_criteria = _extract_acceptance_criteria(section)

    return Task(
        id=task_id,
        title=title,
        description=description,
        file_path=file_path,
        acceptance_criteria=acceptance_criteria,
        plan_file=plan_file,
        milestone_id=milestone_id,
    )


def _extract_file_path(section: str) -> str | None:
    """Extract file path from **File:** or **Files:** field."""
    # Try inline file path first (on same line)
    match = re.search(r"\*\*Files?:\*\*\s*`?([^\n`-]+)`?", section)
    if match:
        file_path = match.group(1).strip()
        if file_path:
            return file_path

    # Try bullet list after **Files:** (on following lines)
    bullet_match = re.search(r"\*\*Files?:\*\*\s*\n\s*-\s*`?([^\n`]+)`?", section)
    if bullet_match:
        return bullet_match.group(1).strip()

    return None


def _extract_description(section: str) -> str:
    """Extract description text from section."""
    # Look for **Description:** field
    desc_match = re.search(
        r"\*\*Description:\*\*\s*\n?(.*?)(?=\n\s*\*\*|\n\s*```|\n\s*-\s*\[|$)",
        section,
        re.DOTALL,
    )
    if desc_match:
        description = desc_match.group(1).strip()
        # Clean up any trailing content
        description = re.sub(r"\n\s*\*\*.*$", "", description, flags=re.DOTALL)
        return description

    # Fallback: use content after header, before any field markers
    lines = section.split("\n")
    desc_lines = []
    in_description = False

    for line in lines[1:]:  # Skip header
        if line.startswith("**") and ":" in line:
            if in_description:
                break
            continue
        if line.strip() and not line.startswith("-"):
            in_description = True
            desc_lines.append(line.strip())
        elif in_description and not line.strip():
            break

    return " ".join(desc_lines) if desc_lines else ""


def _extract_acceptance_criteria(section: str) -> list[str]:
    """Extract acceptance criteria from checkbox or bullet list."""
    criteria: list[str] = []

    # Find the acceptance criteria section
    ac_match = re.search(r"\*\*Acceptance Criteria:\*\*", section)
    if not ac_match:
        return criteria

    # Get content after the header
    after_header = section[ac_match.end() :]

    # Extract all list items (with or without checkboxes)
    # Match: - [ ] item, - [x] item, or - item
    pattern = r"^\s*-\s*(?:\[[ x]\]\s*)?(.+?)$"

    for match in re.finditer(pattern, after_header, re.MULTILINE):
        criterion = match.group(1).strip()
        if criterion and not criterion.startswith("**"):
            criteria.append(criterion)

    return criteria
