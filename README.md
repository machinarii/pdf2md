# Book Cleaner CLI

A sophisticated Node.js/TypeScript CLI tool for automated book processing with AI-powered text cleanup. The system processes PDF/EPUB/TXT files through a multi-phase pipeline to generate embedding-ready text.

## Features

-   🔄 **Multi-Phase Pipeline**: 4 main phases with comprehensive text processing
-   🤖 **Local LLM**: Ollama integration (OpenAI-compatible `/v1` API)
-   🧹 **Deterministic Pre-LLM Cleanup**: Ligature/quote normalization, hyphen rejoining,
        header/footer dedup, OCR artifact fixes — runs before any LLM call to save tokens
-   📊 **Multiple Format Support**: PDF, EPUB, and TXT input formats
-   🔧 **Configuration Management**: YAML-based config with environment variable support
-   📝 **Tagged Logging**: Pino-based logging with component-specific log levels
-   🎯 **OCR Processing**: Tesseract integration with text comparison
-   📋 **Progress Tracking**: Real-time progress reporting with Rich output formatting

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd book-cleaner-cli

# Install dependencies
npm install

# Build the project
npm run build

# Install globally (optional)
npm install -g .
```

## Usage

### Basic Usage

```bash
# Process a book file
clean-book "Rudolf_Steiner#Goethes_Naturwissenschaftliche_Schriften#GA_1.pdf"

# Specify output directory
clean-book -o ./output "Author#Title.pdf"

# Enable verbose logging
clean-book -v "Author#Title.epub"

# Override author and title
clean-book -a "Custom Author" -t "Custom Title" "original_file.txt"
```

### Advanced Usage

```bash
# Run specific phases only
clean-book -p "data_loading,text_normalization" "book.pdf"

# Enable debug logging
clean-book -d "book.pdf"

# Set custom log level
clean-book -l debug "book.pdf"
```

### Filename Convention

Input files should follow the pattern: `<author>#<title>[#<book-index>].<extension>`

Examples:

-   `Rudolf_Steiner#Goethes_Naturwissenschaftliche_Schriften#GA_1.pdf`
-   `Jane_Doe#Sample_Book.epub`
-   `John_Smith#Another_Title#Vol_2.txt`

## Configuration

Configuration files are automatically loaded from the `configs/` directory based on the filename pattern:

-   `configs/<author>#<title>.config` - Book-specific configuration
-   `configs/default.config` - Default configuration

### Prerequisites

-   Node version matching `.nvmrc` (current LTS)
-   [Ollama](https://ollama.com) installed and running
-   Model pulled locally, e.g. `ollama pull qwen3:32b`

### Environment Variables

-   `OLLAMA_BASE_URL` - Ollama OpenAI-compatible endpoint (default: `http://localhost:11434/v1`)
-   `OLLAMA_MODEL` - Model name (default: `qwen3:32b`)
-   `OLLAMA_NUM_CTX` - Context window in tokens (default: `32768`)
-   `LOG_LEVEL` - Global log level (debug, info, warn, error, fatal)
-   `OUTPUT_DIR` - Default output directory
-   `CONFIG_DIR` - Configuration directory path

Example:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export OLLAMA_MODEL=qwen3:32b
export OLLAMA_NUM_CTX=32768
clean-book sample-book.txt
```

## Processing Phases

### Phase 1: Data Loading & Preprocessing

-   Text extraction from various formats
-   PDF OCR processing with comparison
-   **Deterministic text cleanup** (`TextCleanerService`) runs on every chunk before
    the LLM sees it: ligature / smart-quote normalization, hyphen-break rejoining,
    repeated header/footer removal, page-number stripping, OCR artifact fixes
-   Metadata generation
-   Chapter recognition
-   Footnote extraction

### Phase 2: Text Normalization & AI Cleaning

-   Heading normalization
-   Local LLM text cleanup via Ollama
-   Safe text replacements
-   Spell checking

### Phase 3: Evaluation & Analysis

-   Change analysis
-   Quality assessment
-   Processing statistics

### Phase 4: AI Enhancements (Future)

-   Person directory generation
-   Bibliography creation
-   Glossary generation

## Development

### Setup

```bash
# Install dependencies
npm install

# Run in development mode
npm run dev

# Run tests
npm test

# Run tests with coverage
npm run test:coverage

# Lint code
npm run lint

# Format code
npm run format
```

### Project Structure

```
book-cleaner-cli/
├── src/
│   ├── cli/           # CLI commands
│   ├── pipeline/      # Processing pipeline
│   ├── services/      # Core services
│   ├── utils/         # Utility functions
│   ├── types/         # TypeScript types
│   └── constants.ts   # Application constants
├── tests/             # Test files
├── configs/           # Configuration files
└── docs/              # Documentation
```

### Testing

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run specific test file
npm test -- FileUtils.test.ts
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## Architecture

The application follows a modular architecture with:

-   **Pipeline Manager**: Orchestrates the processing pipeline
-   **Phase System**: Extensible phase-based processing
-   **Service Layer**: Core business logic services
-   **Utility Layer**: Common utility functions
-   **Configuration Management**: Flexible configuration system
-   **Tagged Logging**: Component-specific logging

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:

-   Check the documentation in `/docs`
-   Review existing issues
-   Create a new issue with detailed information

## Roadmap

-   [ ] Additional file format support
-   [ ] Web interface
-   [ ] Batch processing
-   [ ] Cloud deployment options
-   [ ] Plugin system
-   [ ] Performance optimizations
