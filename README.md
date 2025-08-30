# Artist Bio Generator

A Python script that uses the OpenAI Responses API to generate artist biographies from CSV-like input files. The script processes multiple artists concurrently, provides comprehensive logging and monitoring, and outputs results in both stdout and JSONL formats.

## 🚀 Features

- **CSV-like Input Processing**: Parse artist data from text files with support for comments and blank lines
- **OpenAI Responses API Integration**: Use reusable prompts for consistent bio generation
- **Comprehensive Logging**: Real-time progress tracking with visual progress bars and detailed statistics
- **Concurrent Processing**: Configurable worker limits for efficient API usage
- **Robust Error Handling**: Graceful failure handling with detailed error reporting
- **Multiple Output Formats**: Both stdout and JSONL file output
- **Dry Run Mode**: Test your input files without making API calls
- **Verbose Logging**: Debug-level logging for troubleshooting

## 📋 Requirements

- Python 3.11+
- OpenAI API key
- Valid OpenAI prompt ID
- PostgreSQL database (for bio persistence)

## 🛠️ Installation

1. **Clone or download the project files**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   export OPENAI_PROMPT_ID="your-prompt-id-here"  # Optional
   export DATABASE_URL="postgresql://username:password@localhost:5432/artist_bios"
   ```

   Or create a `.env.local` file:
   ```
   OPENAI_API_KEY=your-api-key-here
   OPENAI_PROMPT_ID=your-prompt-id-here
   DATABASE_URL=postgresql://username:password@localhost:5432/artist_bios
   ```

4. **Set up PostgreSQL database:**
   ```sql
   CREATE DATABASE artist_bios;
   CREATE TABLE artists (
     id UUID PRIMARY KEY,
     name TEXT NOT NULL,
     bio TEXT
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
| `--dry-run` | Parse inputs without API calls | `False` | ❌ |
| `--verbose` | Enable debug logging | `False` | ❌ |

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

**Verbose logging for debugging:**
```bash
python3 run_artists.py --input-file artists.csv --prompt-id prompt_123 --verbose
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
