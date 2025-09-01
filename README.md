# Artist Bio Generator

A modular Python package that uses the OpenAI Responses API to generate artist biographies from CSV-like input files. The package provides both a command-line interface and programmatic API for processing multiple artists concurrently with comprehensive logging, monitoring, and database persistence.

## 🚀 Features

- **CSV-like Input Processing**: Parse artist data from text files with support for comments and blank lines
- **OpenAI Responses API Integration**: Use reusable prompts for consistent bio generation
- **Comprehensive Logging**: Real-time progress tracking with visual progress bars and detailed statistics
- **Concurrent Processing**: Configurable worker limits for efficient API usage
- **Robust Error Handling**: Graceful failure handling with detailed error reporting
- **Multiple Output Formats**: Both stdout and JSONL file output
- **Dry Run Mode**: Test your input files without making API calls
- **Verbose Logging**: Debug-level logging for troubleshooting
- **Modular Architecture**: Clean separation of concerns with importable modules
- **Library API**: Use as a Python package in your own applications

## 📦 Package Structure

```
artist_bio_gen/
├── __init__.py          # Public API exports
├── main.py              # Main entry point
├── constants.py         # Configuration constants
├── models/              # Data models and structures
├── api/                 # OpenAI API integration
├── database/            # Database operations
├── core/                # Business logic (parsing, processing, output)
├── cli/                 # Command-line interface
└── utils/               # Shared utilities
```

### Module Responsibilities

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `api/` | OpenAI API integration | `create_openai_client()`, `call_openai_api()` |
| `database/` | PostgreSQL operations | `create_db_connection_pool()`, `update_artist_bio()`, `validate_database_url()` |
| `core/` | Business logic | `parse_input_file()`, `process_artists_concurrent()`, `write_jsonl_output()` |
| `cli/` | Command-line interface | `main()`, `create_argument_parser()` |
| `utils/` | Shared utilities | `setup_logging()`, `create_progress_bar()`, `apply_environment_defaults()` |
| `models/` | Data structures | `ArtistData`, `ApiResponse`, `ProcessingStats` |

## 📋 Requirements

- **Python**: 3.11 or higher
- **OpenAI API Access**: Valid API key and prompt ID
- **PostgreSQL Database**: For bio persistence (optional)
- **Python Packages**: Listed in `requirements.txt`

## 🛠️ Installation & Setup

### 1. **Clone or download the project files**

### 2. **Install Python dependencies:**

**Option A: Install all dependencies at once**
```bash
pip install -r requirements.txt
```

**Option B: Install dependencies individually**
```bash
# Core runtime dependencies
pip install "openai>=1.0.0"
pip install "psycopg[binary,pool]>=3.2.0"  # For database connectivity
pip install "python-dotenv>=1.0.0"         # For .env file support
pip install "tenacity>=8.0.0"              # For retry logic
pip install "aiohttp>=3.8.0"               # For async HTTP

# Development dependencies (optional)
pip install "pytest>=7.0.0"                # For running tests
pip install "black>=23.0.0"                # For code formatting
pip install "mypy>=1.0.0"                  # For type checking
```

**Note:** The `psycopg[binary,pool]` package is required for database functionality. The `[binary,pool]` extras provide:
- `binary`: Pre-compiled PostgreSQL adapter for better performance
- `pool`: Connection pooling support for concurrent database operations

3. **Set up environment variables:**
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   export DATABASE_URL="postgresql://username:password@localhost:5432/artist_bios"
   export OPENAI_PROMPT_ID="your-prompt-id-here"  # Optional
   export OPENAI_ORG_ID="your-org-id-here"        # Optional
   ```

   Or create a `.env.local` file:
   ```
   OPENAI_API_KEY=your-api-key-here
   DATABASE_URL=postgresql://username:password@localhost:5432/artist_bios
   OPENAI_PROMPT_ID=your-prompt-id-here
   OPENAI_ORG_ID=your-org-id-here
   ```

4. **Set up PostgreSQL database:**
   ```sql
   CREATE DATABASE artist_bios;
   
   -- Production table
   CREATE TABLE artists (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     name TEXT NOT NULL,
     bio TEXT,
     created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
     updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
   );
   
   -- Test table (optional, for --test-mode)
   CREATE TABLE test_artists (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     name VARCHAR(255) NOT NULL,
     bio TEXT,
     created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
     updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
   );
   ```

## 📖 Usage

### Basic Usage

```bash
python3 run_artists.py --input-file artists.csv --prompt-id your-prompt-id
```

### Command Line Options

| Option | Description | Default | Required |
|--------|-------------|---------|----------|
| `--input-file` | CSV-like text file path | - | ✅ |
| `--prompt-id` | OpenAI prompt ID | `OPENAI_PROMPT_ID` env var | ✅ |
| `--version` | Prompt version | None | ❌ |
| `--output` | JSONL output file path | `out.jsonl` | ❌ |
| `--max-workers` | Max concurrent requests | `4` | ❌ |
| `--enable-db` | Enable database bio updates | `False` | ❌ |
| `--test-mode` | Use test_artists table | `False` | ❌ |
| `--dry-run` | Parse inputs without API calls | `False` | ❌ |
| `--verbose` | Enable debug logging | `False` | ❌ |
| `--openai-api-key` | OpenAI API key | `OPENAI_API_KEY` env var | ❌ |
| `--openai-prompt-id` | OpenAI prompt ID | `OPENAI_PROMPT_ID` env var | ❌ |
| `--openai-org-id` | OpenAI organization ID | `OPENAI_ORG_ID` env var | ❌ |
| `--db-url` | Database URL | `DATABASE_URL` env var | ❌ |

### Configuration Precedence

The application loads configuration from multiple sources with the following precedence (highest to lowest):

1. **CLI arguments** (highest priority)
2. **OS environment variables**
3. **`.env.local` file** (if `python-dotenv` is installed)
4. **Defaults** (lowest priority)

**Example:**
```bash
# Environment variable
export OPENAI_API_KEY="env-key"

# CLI override (takes precedence)
python3 run_artists.py --input-file artists.csv --openai-api-key "cli-key"
# Uses "cli-key" instead of "env-key"
```

### Examples

**Basic processing:**
```bash
python3 run_artists.py --input-file example_artists.csv --prompt-id prompt_123
```

**With custom output file and more workers:**
```bash
python3 run_artists.py --input-file artists.csv --prompt-id prompt_123 --output results.jsonl --max-workers 8
```

**Dry run to test your input file:**
```bash
python3 run_artists.py --input-file artists.csv --prompt-id prompt_123 --dry-run
```

**Using CLI configuration overrides:**
```bash
python3 run_artists.py --input-file artists.csv \
    --openai-api-key "sk-proj-abc123..." \
    --db-url "postgresql://user:pass@host:5432/db" \
    --openai-prompt-id "prompt_456"
```

**Production run with organization ID:**
```bash
python3 run_artists.py --input-file artists.csv \
    --openai-org-id "org-123" \
    --enable-db \
    --max-workers 6
```

**Verbose logging for debugging:**
```bash
python3 run_artists.py --input-file artists.csv --prompt-id prompt_123 --verbose
```

**With database updates enabled:**
```bash
python3 run_artists.py --input-file artists.csv --prompt-id prompt_123 --enable-db --verbose
```

**Testing with test database table:**
```bash
python3 run_artists.py --input-file test_artists.csv --prompt-id prompt_123 --enable-db --test-mode --verbose
```

### Library Usage

The package can be imported and used programmatically in your Python applications:

**Basic parsing and processing:**
```python
from artist_bio_gen import parse_input_file, process_artists_concurrent
from artist_bio_gen import create_openai_client, setup_logging

# Setup logging
setup_logging(verbose=True)

# Parse input file
result = parse_input_file("artists.csv")
print(f"Found {len(result.artists)} artists")

# Create OpenAI client
client = create_openai_client()

# Process artists (requires proper environment setup)
responses = process_artists_concurrent(
    result.artists, 
    client, 
    "your-prompt-id",
    max_workers=4
)
```

**Database operations:**
```python
from artist_bio_gen import create_db_connection_pool, update_artist_bio
from artist_bio_gen import validate_database_url

# Validate database URL
if validate_database_url("postgresql://user:pass@localhost/db"):
    # Create connection pool
    pool = create_db_connection_pool("postgresql://user:pass@localhost/db")
    
    # Update artist bio in database
    update_artist_bio(pool, "artist-uuid", "Generated biography text")
```

**Custom processing pipeline:**
```python
from artist_bio_gen import parse_input_file, write_jsonl_output
from artist_bio_gen.models import ApiResponse

# Parse input
result = parse_input_file("input.csv") 

# Process with your own logic
responses = []
for artist in result.artists:
    # Your custom processing logic here
    response = ApiResponse(
        artist_id=artist.artist_id,
        artist_name=artist.name,
        artist_data=artist.data,
        response_text="Your generated bio",
        response_id="response-123",
        response_created_at=1234567890
    )
    responses.append(response)

# Output results
write_jsonl_output(responses, "output.jsonl")
```

## 📝 Input File Format

The input file should be a CSV-like text file with the following format:

```
# This is a comment line (starts with #)
# Blank lines are also ignored

Taylor Swift,Pop singer-songwriter known for autobiographical lyrics and genre evolution
Drake,Canadian rapper and singer from Toronto
Billie Eilish,Alternative pop artist known for whisper vocals and dark themes

# Another comment
The Weeknd,R&B and pop artist with atmospheric production
BTS,Korean boy band that popularized K-pop globally

Artist with no additional data,
```

**Format Rules:**
- Each line should contain: `artist_name,artist_data`
- Lines starting with `#` are comments and will be skipped
- Blank lines are ignored
- `artist_name` is required, `artist_data` is optional
- Whitespace is automatically trimmed from both fields
- UTF-8 encoding is supported

## 📊 Output Formats

### Stdout Output
The generated bio text is printed to stdout for each successful artist:
```
Taylor Swift is a renowned pop singer-songwriter known for her autobiographical lyrics and genre evolution...
Drake is a Canadian rapper and singer from Toronto who has become one of the most successful artists...
```

### JSONL Output
Complete records are written to the specified JSONL file:
```json
{"artist_name": "Taylor Swift", "artist_data": "Pop singer-songwriter known for autobiographical lyrics and genre evolution", "request": {"prompt_id": "prompt_123", "variables": {"artist_name": "Taylor Swift", "artist_data": "Pop singer-songwriter known for autobiographical lyrics and genre evolution"}}, "response_text": "Taylor Swift is a renowned pop singer-songwriter...", "response_id": "resp_abc123", "created": 1234567890, "error": null}
```

## 📈 Logging and Monitoring

The script provides comprehensive logging with:

### Progress Tracking
```
[███████████████░░░░░░░░░░░░░░░] [  5/  6] ( 83.3%) ✅ Taylor Swift - SUCCESS (2.50s)
```

### Processing Summary
```
======================================================================
PROCESSING SUMMARY
======================================================================
End time: 2025-08-29 08:16:30
Total duration: 2.50 seconds (0:00:02)

INPUT STATISTICS:
  Total artists processed: 6
  Skipped lines (comments/blanks): 9
  Error lines (invalid data): 0

API CALL STATISTICS:
  Successful calls: 6
  Failed calls: 0
  Success rate: 100.0%

PERFORMANCE STATISTICS:
  Average time per artist: 0.42s
  API calls per second: 2.40
  Processing efficiency: 100.0%
======================================================================
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Run all tests
python3 run_tests.py

# Run specific test categories
python3 run_tests.py test_input_parser.py       # Input parsing tests
python3 run_tests.py test_logging_monitoring.py # Logging and monitoring tests
python3 run_tests.py test_run_artists.py        # CLI and main function tests
python3 run_tests.py test_example_data.py       # Data validation tests
```

## 📁 Project Structure

```
artist-bio-gen/
├── run_artists.py              # Main script
├── requirements.txt            # Python dependencies
├── example_artists.csv         # Example input file
├── README.md                   # This file
├── run_tests.py                # Test runner
└── tests/                      # Test suite
    ├── test_input_parser.py       # Input parsing tests
    ├── test_logging_monitoring.py # Logging tests
    ├── test_run_artists.py        # CLI tests
    └── test_example_data.py       # Data validation tests
```

## 🔧 Development

### Dependencies

**Core Dependencies:**
- `openai>=1.0.0` - OpenAI Python SDK
- `aiohttp>=3.8.0` - For async HTTP requests
- `tenacity>=8.0.0` - For retry logic
- `python-dotenv>=1.0.0` - Environment variable management
- `psycopg3[binary]>=3.1.0` - PostgreSQL database adapter

**Development Dependencies:**
- `pytest>=7.0.0` - Testing framework
- `pytest-asyncio>=0.21.0` - Async testing support
- `black>=23.0.0` - Code formatting
- `mypy>=1.0.0` - Type checking

### Code Quality

The project includes:
- **Type hints** throughout the codebase
- **Comprehensive docstrings** for all functions
- **Extensive test coverage** (84 test cases)
- **Error handling** for all major scenarios
- **Logging** at appropriate levels

## 🚨 Error Handling

The script handles various error scenarios:

- **File not found**: Clear error message with file path
- **Invalid encoding**: UTF-8 validation with helpful error details
- **Empty artist names**: Warning logged, line skipped
- **API failures**: Individual artist failures don't stop processing
- **Network issues**: Detailed error logging for troubleshooting
- **Missing environment variables**: Clear setup instructions

## 📋 TODO / Roadmap

**Completed:**
- ✅ Project structure and CLI
- ✅ Input file parsing
- ✅ OpenAI API integration
- ✅ Comprehensive logging and monitoring
- ✅ Testing framework
- ✅ Documentation

**In Progress:**
- 🔄 Enhanced error handling

**Planned:**
- ⏳ Concurrent processing with asyncio
- ⏳ Retry logic with exponential backoff
- ⏳ JSONL output file generation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is open source. Please check the license file for details.

## 🆘 Support

If you encounter issues:

1. **Check the logs** - Use `--verbose` flag for detailed debugging
2. **Test your input** - Use `--dry-run` to validate your input file
3. **Verify API setup** - Ensure your OpenAI API key and prompt ID are correct
4. **Run tests** - Use `python3 run_tests.py` to verify the installation

## 📞 Example Session

```bash
# Test the example data
python3 run_artists.py --input-file example_artists.csv --prompt-id test_prompt --dry-run

# Process with verbose logging
python3 run_artists.py --input-file example_artists.csv --prompt-id your-prompt-id --verbose

# Check results
cat out.jsonl
```

---

**Happy bio generating! 🎵✨**
