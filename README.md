# IMS Games

Transparent, explainable, and extensible game score aggregation system.

## Overview

IMS Games aggregates game reviews from multiple sources with transparent algorithms, 
allowing users to understand and customize how scores are calculated.

## Quick Start

```bash
# Install Python dependencies
uv sync

# Initialize database and import data
uv run python scripts/build_all.py

# Install frontend dependencies
cd site && npm install

# Build static site
npm run build
```

## Tech Stack

- **Frontend**: Astro + React + TypeScript + Tailwind CSS
- **Data Processing**: Python 3.11+, pandas, SQLite
- **Deployment**: GitHub Pages via GitHub Actions
