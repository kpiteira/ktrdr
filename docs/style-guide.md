# KTRDR Documentation Style Guide

This style guide provides standards and conventions for creating consistent, high-quality documentation for the KTRDR project.

## General Principles

1. **Be Clear and Concise**: Use simple, direct language. Avoid jargon when possible, and define technical terms when they're necessary.

2. **Be Comprehensive**: Cover all aspects of the feature or component being documented.

3. **Be Accurate**: Ensure all information is correct and up-to-date.

4. **Be Consistent**: Follow the conventions in this guide for formatting, terminology, and structure.

5. **Be Helpful**: Focus on helping the reader accomplish their goals. Include examples and use cases.

## Document Structure

### Standard Sections

Most documentation files should include these sections:

1. **Title** (level 1 heading): Clear, descriptive title
2. **Overview**: Brief introduction and purpose
3. **Key Features** or **Functionality**: What it does and why it's useful
4. **Usage** or **Getting Started**: How to use it
5. **Examples**: Practical examples with code
6. **API Reference** (if applicable): Detailed reference information
7. **Troubleshooting** (if applicable): Common issues and solutions
8. **Related Resources**: Links to related documentation

### Headings

* Use title case for all headings (e.g., "Configuration Reference" not "Configuration reference")
* Use hierarchy appropriately (H1 for title, H2 for major sections, H3 for subsections, etc.)
* Don't skip levels (e.g., don't go from H1 to H3)
* Keep headings concise and descriptive

## Markdown Conventions

### Basic Formatting

* Use **bold** (`**bold**`) for emphasis or UI elements
* Use *italics* (`*italics*`) for new terms or slight emphasis
* Use `code formatting` (`` `code` ``) for code references, file names, and technical values

### Code Blocks

* Use fenced code blocks with language specification:

````
```python
# Python code example
print("Hello, world!")
```
````

* Use syntax highlighting by specifying the language after the opening fence
* For shell commands, use `bash` as the language
* For output, use plain text (no language specification)
* For configuration files, use the appropriate language (e.g., `yaml`, `json`)

### Lists

* Use ordered lists (1., 2., 3.) for sequential steps
* Use unordered lists (bullet points) for non-sequential items
* Be consistent with punctuation in lists (either all items end with a period or none do)

### Tables

* Use tables for structured data, parameters, or options:

```
| Name | Type | Description |
|------|------|-------------|
| item1 | string | Description of item1 |
| item2 | number | Description of item2 |
```

* Include header rows in all tables
* Align column content for readability

### Links

* Use descriptive link text:
  * Good: [Developer Setup Guide](../developer/setup.md)
  * Bad: [Click here](../developer/setup.md)

* For internal links, use relative paths
* For external links, include the full URL

## Writing Style

### Voice and Tone

* Use a professional, friendly tone
* Write in the present tense
* Use active voice rather than passive voice
* Address the reader directly using "you" rather than "the user"

### Terminology

* Be consistent with technical terms
* Use American English spelling
* Capitalize proper names (e.g., Python, Docker, Interactive Brokers)
* Use consistent capitalization for KTRDR components

### Common Term Guidelines

| Term | Usage |
|------|-------|
| KTRDR | Always all caps |
| DataFrame | Capital D and F |
| API | Always all caps |
| YAML | Always all caps |
| UI | Always all caps |
| CLI | Always all caps |
| fuzzy logic | Lowercase unless at the start of a sentence |
| indicator(s) | Lowercase unless at the start of a sentence |

## Code Examples

### Best Practices

* Keep examples simple and focused on a single concept
* Include comments to explain key points
* Make sure examples are correct and runnable
* Start with imports when necessary
* Use consistent variable naming
* Follow [PEP 8](https://peps.python.org/pep-0008/) guidelines

### Example Template

```python
# Import necessary modules
from ktrdr.module import Component

# Initialize the component with basic configuration
component = Component(param1="value", param2=42)

# Demonstrate main functionality
result = component.method()

# Show expected output
print(result)  # Expected output: {'key': 'value'}
```

## Images and Diagrams

* Use descriptive file names for images
* Include alt text for accessibility
* Keep diagrams simple and focused
* Use consistent visual style across diagrams
* Include captions for complex images

## Versioning

* Clearly indicate which version of KTRDR the documentation applies to
* Use notes, warnings, or callouts for version-specific features
* Update documentation when features change

## Additional Guidelines

### Warnings and Notes

Use blockquotes with specific prefixes for notes and warnings:

```
> **Note:** This is an important note that provides additional context.

> **Warning:** This highlights a potential issue or important caution.
```

### API Documentation

* Document all parameters and their types
* Include return values and their types
* Document exceptions that may be raised
* Provide examples of typical usage

### Command-Line Documentation

* Document all options and arguments
* Use a consistent format for command syntax
* Include examples for common use cases
* Document exit codes where applicable

## Documentation Review Checklist

Before submitting new documentation, check that it:

1. Follows the structure and formatting guidelines in this document
2. Contains no spelling or grammatical errors
3. Includes practical examples
4. Has been tested for technical accuracy
5. Uses consistent terminology
6. Includes all necessary sections
7. Has appropriate links to related documentation

## Example

Here's an example of well-formatted documentation following these guidelines:

```markdown
# Data Manager

## Overview

The DataManager is a core component of KTRDR that handles retrieving, storing, and managing historical price data.

## Key Features

* Transparent caching of historical data
* Automatic gap detection and filling
* Support for multiple data sources
* Efficient data storage and retrieval

## Usage

```python
from ktrdr.data import DataManager

# Initialize the DataManager
data_manager = DataManager()

# Load data for a specific symbol and timeframe
df = data_manager.load(
    symbol="AAPL",
    interval="1d",
    start="2023-01-01",
    end="2023-12-31"
)

# Display the data
print(df.head())
```

## Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| "No data found" error | Check that the symbol exists and that data is available for the specified date range |
| Gaps in data | Use the `repair()` method to automatically fill gaps |
```