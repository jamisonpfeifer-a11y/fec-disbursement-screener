# fec-disbursement-screener

A command-line screening tool that reads public campaign disbursement data from
the [openFEC API](https://api.open.fec.gov/developers/) and produces a **ranked
worklist for human review**.

> **A score is a lead, not a finding.** Everything this tool flags has a
> possible innocent explanation (legal fees to a firm with a common surname, an event held
> at a resort, a card payment whose purchases were itemized elsewhere). Output
> names real people and must be verified against the underlying filings before
> anything is said or published about anyone.

## What it does

**Module 1: vendor and transaction rules.** Each Schedule B disbursement is
checked against configurable categories (tobacco, luxury travel, personal
retail, entertainment, nightlife, vague high-dollar payments, large card-issuer
payments) and two payee-name checks:

- the payee shares the candidate's surname, and
- the payee shares the surname *and* looks like a campaign committee. This is
  reported separately because it is a different pattern from an ordinary payee.

Repeated hits in a category compound, with per-category caps so no single weak
signal can saturate a score. Shared-surname scores also scale with dollars.
Payees flagged across four or more committees (a conference venue, a card
issuer, a large vendor) are probably institutions, so their flags count at half
weight.

**Module 2: peer comparison.** Each candidate's spending shares by category
(catering, lodging, travel, consulting, shared-surname payees) are compared with peers
(office, state, party, incumbency, cycle) using median/MAD robust z-scores. Only
spending *above* peers counts, and the contribution is capped and floored so
tiny peer variance cannot produce absurd scores.

**Composite** = `1.0 × vendor score + 0.6 × peer score`.

False-positive controls that came out of testing on real data: whole-word
keyword matching, self-payment detection (personal-fund repayments, the
candidate's own committee, nicknames), contribution refunds, card issuers,
duplicate amendment records, hotel-chain names, and place names such as
"Sherman Oaks" that happen to contain a surname.

## Setup

```bash
git clone <this repo> && cd fec-disbursement-screener
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Free key: https://api.data.gov/signup/
export FEC_API_KEY="your-key"

# Rules: start from the example, then tune your own copy (it is git-ignored)
cp config/vendor_categories.example.yaml config/vendor_categories.yaml
```

If `config/vendor_categories.yaml` is missing the tool falls back to the example
rules and says so.

## Usage

```bash
# Screen every candidate matching the filters
python3 -m src.cli screen --cycle 2024 --office H --state CA

# One committee
python3 -m src.cli screen-committee --committee-id C00123456 --cycle 2024
```

Output: the top 10 are printed, and the full ranked report is written to
`output/screening_report_<timestamp>.json` with the flagged transactions and
peer anomalies behind each score.

## Data coverage and rate limits

The openFEC disbursements endpoint uses cursor (keyset) pagination: each
response carries the position of its last record, which must be sent with the
next request. It ignores page numbers. The client follows the cursor until the
committee's records are exhausted, so scores are based on every reported
disbursement in the cycle, not a sample.
`scripts/check_pagination.py` compares cached record counts with the API's
reported totals for each committee.

A full state screen is a lot of data (a large House committee can have around
10,000 transactions, or about 100 requests). The default api.data.gov key allows roughly 1,000
requests per hour, so a large screen will usually stop partway through. When it
does, it prints where it stopped and writes no report; downloaded data is
cached, so re-run the same command after the quota resets and it continues
where it left off. FEC will raise the limit on request (APIinfo@fec.gov).

Downloads are cached in `./cache`. Changing rules or scoring re-scores in
seconds with no API calls. `--refresh` forces a re-download.

## Tests

```bash
for f in tests/test_*.py; do python3 "$f" || break; done
```

Most tests are offline and need no key.

## Keeping the rules private

Publishing exact keywords and thresholds lets anyone route around them with
vaguer vendor names. The repository ships only `vendor_categories.example.yaml`;
keep your tuned `vendor_categories.yaml` out of version control (it is in
`.gitignore`).

## Limitations

- Only what filers report: descriptions are free text, and payee names can be
  inconsistent or wrong.
- A shared surname is only a name match. It says nothing about whether the
  payee and candidate are related, and common surnames match unrelated people.
- Peer groups are coarse; incumbents and challengers may spend very differently.
- Card-issuer payments hide the underlying purchases.
- It reads federal filings only.
- Scores reflect volume as well as behavior: committees with many transactions
  have more chances to trip a rule. Large, long-serving committees tend to rank
  higher for routine spending (conference venues, consultants, staff
  reimbursements). Treat the ranking as a reading order, not a measure of
  wrongdoing.

## License

MIT. See [LICENSE](LICENSE).
