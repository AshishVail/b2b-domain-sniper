
# B2B Domain Sniper

B2B Domain Sniper is an Apify Actor designed to collect and analyze publicly available website intelligence for business domains.

It helps identify business contact signals, website technologies, public recruitment indicators, and domain email configuration.

## Features

- Website crawling and page fetching
- Public email address extraction
- Email domain normalization
- MX record validation using DNS over HTTPS
- Website technology detection
- Public hiring and career-page detection
- Website content cleaning
- Lead signal and intent scoring
- Structured JSON result generation
- Usage and credit calculation

> Important: Detection and scoring are heuristic. An MX record does not prove that an individual mailbox exists, and hiring indicators do not guarantee that a position is currently open.

## Project Structure

```text
b2b-domain-sniper/
│
├── .actor/
│   ├── actor.json
│   ├── input_schema.json
│   └── Dockerfile
│
├── src/
│   ├── __main__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── fetcher.py
│   ├── crawler.py
│   ├── email_extractor.py
│   ├── mx_validator.py
│   ├── technology_detector.py
│   ├── hiring_detector.py
│   ├── intent_scorer.py
│   ├── content_cleaner.py
│   ├── result_builder.py
│   └── billing.py
│
├── tests/
│   ├── test_extraction.py
│   ├── test_detection.py
│   └── test_output.py
│
├── requirements.txt
├── pyproject.toml
├── .gitignore
└── README.md
```

## Requirements

- Python 3.10 or newer
- pip
- Apify account for deployment
- Apify CLI for local Actor execution

## Installation

Clone the repository:

```bash
git clone YOUR_REPOSITORY_URL
cd b2b-domain-sniper
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it.

Windows:

```bash
.venv\Scripts\activate
```

Linux / macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Install development dependencies:

```bash
pip install -e ".[dev]"
```

## Running Locally

Run the Python module:

```bash
python -m src
```

Alternatively, use the Apify CLI:

```bash
apify run
```

The Actor input is configured through:

```text
.actor/input_schema.json
```

Use the input fields defined in that schema.

## Running Tests

Run all tests:

```bash
pytest -v
```

Run a specific test file:

```bash
pytest tests/test_extraction.py -v
```

```bash
pytest tests/test_detection.py -v
```

```bash
pytest tests/test_output.py -v
```

## Core Modules

| Module | Responsibility |
|---|---|
| `fetcher.py` | Fetch website pages |
| `crawler.py` | Crawl website links |
| `email_extractor.py` | Extract public email addresses |
| `mx_validator.py` | Check email-domain DNS configuration |
| `technology_detector.py` | Detect website technologies |
| `hiring_detector.py` | Identify public hiring signals |
| `intent_scorer.py` | Calculate lead signal scores |
| `content_cleaner.py` | Clean website content |
| `result_builder.py` | Build structured JSON results |
| `billing.py` | Track usage and calculate estimated credits |

## Output

The result builder produces a structured JSON object containing sections such as:

- `success`
- `scan`
- `business`
- `website`
- `email_intelligence`
- `mx_validation`
- `technology_intelligence`
- `hiring_intelligence`
- `business_intelligence`
- `errors`

The exact output depends on the available website data and the arguments supplied to the result builder.

## Deployment

1. Log in to your Apify account.
2. Install and configure the Apify CLI.
3. Check the Actor configuration and input schema.
4. Run the Actor locally.
5. Verify the output and tests.
6. Push the Actor to Apify.

Example:

```bash
apify login
apify run
apify push
```

## Responsible Use

- Analyze only publicly accessible website information.
- Respect website terms, robots.txt policies, and applicable laws.
- Use reasonable crawl limits and request rates.
- Do not bypass authentication or access controls.
- Do not treat detected email addresses as verified personal inboxes.
- Do not use heuristic scores as proof of purchase intent.

## Billing Note

The current billing module calculates estimated usage credits. It does not independently charge customers or process payments.

Actual Apify billing integration and payment processing must be configured separately.

## License

MIT License
