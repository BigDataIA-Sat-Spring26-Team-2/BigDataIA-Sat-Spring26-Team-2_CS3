# Evidence Collection Report

## PE Org-AI-R Platform — Case Study 1 & 2

**Authors:** Prachi Pradhan, Samiksh Gupta, Siddharth Shukla

**Course:** Big Data and Intelligent Analytics — Northeastern University, Spring 2026

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Companies with documents | 10 |
| Total documents | 53 |
| Total chunks | 2,602 |
| Companies with signals | 10 |
| Total signals | 38 |
| Avg composite score | 42.9 |

---

## Documents by Company

| Ticker | Company | 10-K | 10-Q | 8-K | DEF 14A | Total Docs |
|--------|---------|------|------|-----|---------|------------|
| DE | Deere & Company | 2 | 2 | 2 | 2 | 8 |
| TGT | Target Corporation | 2 | 1 | 1 | 1 | 5 |
| JPM | JPMorgan Chase | 2 | 1 | 1 | 1 | 5 |
| HCA | HCA Healthcare | 2 | 1 | 1 | 1 | 5 |
| ADP | Automatic Data Processing | 2 | 1 | 1 | 1 | 5 |
| GS | Goldman Sachs | 2 | 1 | 1 | 1 | 5 |
| WMT | Walmart Inc. | 2 | 1 | 1 | 1 | 5 |
| CAT | Caterpillar Inc. | 2 | 1 | 1 | 1 | 5 |
| UNH | UnitedHealth Group | 2 | 1 | 1 | 1 | 5 |
| PAYX | Paychex Inc. | 2 | 1 | 1 | 1 | 5 |
| **Total** | | **20** | **11** | **11** | **11** | **53** |

---

## Chunks by Company

| Ticker | Company | Total Docs | Total Chunks | Total Words |
|--------|---------|------------|--------------|-------------|
| JPM | JPMorgan Chase | 5 | 665 | 661,532 |
| DE | Deere & Company | 8 | 391 | 390,757 |
| GS | Goldman Sachs | 5 | 241 | 235,839 |
| CAT | Caterpillar Inc. | 5 | 224 | 220,966 |
| HCA | HCA Healthcare | 5 | 222 | 222,271 |
| WMT | Walmart Inc. | 5 | 211 | 215,749 |
| UNH | UnitedHealth Group | 5 | 184 | 179,576 |
| ADP | Automatic Data Processing | 5 | 176 | 170,441 |
| TGT | Target Corporation | 5 | 152 | 153,001 |
| PAYX | Paychex Inc. | 5 | 136 | 137,692 |
| **Total** | | **53** | **2,602** | **2,587,824** |

---

## Sections Extracted by Filing Type

| Section | Filing Type | Chunk Count |
|---------|-------------|-------------|
| item_7_mda | 10-K | 848 |
| executive_compensation | DEF 14A | 485 |
| item_1a_risk_factors | 10-K | 417 |
| item_1a_risk_factors | 10-Q | 353 |
| item_2_mda | 10-Q | 179 |
| item_1_business | 10-K | 164 |
| executive_compensation | 10-Q | 63 |
| item_2_mda | 10-K | 34 |
| item_7_mda | 10-Q | 29 |
| item_8_01_other | 8-K | 20 |
| item_1a_risk_factors | 8-K | 9 |
| executive_compensation | 8-K | 1 |

---

## Say Scores (AI Rhetoric in SEC Filings)

Say Score measures AI keyword density in SEC filing text. Higher = more AI rhetoric.

| Rank | Ticker | Say Score (0-100) |
|------|--------|-------------------|
| 1 | ADP | 100.0 |
| 2 | PAYX | 93.7 |
| 3 | UNH | 93.1 |
| 4 | HCA | 76.1 |
| 5 | GS | 67.8 |
| 6 | WMT | 60.3 |
| 7 | TGT | 60.0 |
| 8 | CAT | 58.6 |
| 9 | DE | 47.1 |
| 10 | JPM | 44.9 |

---

## Do Scores (Actual AI Investment — External Signals)

Do Score = composite external signal score. Higher = more actual AI activity.

| Rank | Ticker | Company | Hiring (30%) | Innovation (25%) | Digital (25%) | Leadership (20%) | Do Score | Signals |
|------|--------|---------|-------------|-----------------|--------------|-----------------|----------|---------|
| 1 | WMT | Walmart Inc. | 88.7 | 80.0 | 65.0 | 26.7 | **68.2** | 4 |
| 2 | UNH | UnitedHealth Group | 92.9 | 80.0 | 22.5 | 64.1 | **66.3** | 4 |
| 3 | GS | Goldman Sachs | 79.6 | 40.0 | 55.0 | 46.9 | **57.0** | 4 |
| 4 | JPM | JPMorgan Chase | 90.0 | 30.0 | 22.5 | 41.7 | **48.5** | 4 |
| 5 | DE | Deere & Company | 55.8 | 80.0 | 22.5 | 7.5 | **43.9** | 4 |
| 6 | HCA | HCA Healthcare | 81.1 | 0.0 | 32.5 | 39.0 | **40.2** | 4 |
| 7 | CAT | Caterpillar Inc. | 53.4 | 80.0 | 0.0 | 7.5 | **37.5** | 4 |
| 8 | TGT | Target Corporation | 60.6 | 0.0 | 32.5 | 35.4 | **33.4** | 3 |
| 9 | ADP | Automatic Data Processing | 66.4 | 15.0 | 22.5 | 12.6 | **31.8** | 4 |
| 10 | PAYX | Paychex Inc. | 72.4 | 0.0 | 0.0 | 33.5 | **28.4** | 3 |

---

## Say-Do Gap Analysis

Gap = Say Score - Do Score. Positive gap means company talks more than it does. Negative gap means company does more than it talks.

| Rank | Ticker | Say Score | Do Score | Gap (Say - Do) | Assessment |
|------|--------|-----------|----------|----------------|------------|
| 1 | ADP | 100.0 | 31.8 | +68.2 | Overstating AI |
| 2 | PAYX | 93.7 | 28.4 | +65.3 | Overstating AI |
| 3 | HCA | 76.1 | 40.2 | +35.8 | Overstating AI |
| 4 | UNH | 93.1 | 66.3 | +26.8 | Overstating AI |
| 5 | TGT | 60.0 | 33.4 | +26.6 | Overstating AI |
| 6 | CAT | 58.6 | 37.5 | +21.1 | Overstating AI |
| 7 | GS | 67.8 | 57.0 | +10.8 | More talk than action |
| 8 | DE | 47.1 | 43.9 | +3.2 | Balanced |
| 9 | JPM | 44.9 | 48.5 | -3.6 | Balanced |
| 10 | WMT | 60.3 | 68.2 | -7.9 | Quiet builder |

---

## Sector Analysis

| Rank | Sector | Avg Hiring | Avg Innovation | Avg Digital | Avg Leadership | Avg Composite | Companies |
|------|--------|-----------|----------------|-------------|----------------|---------------|-----------|
| 1 | Healthcare | 87.0 | 40.0 | 27.5 | 51.5 | **53.3** | 2 |
| 2 | Retail | 74.7 | 40.0 | 48.8 | 31.1 | **50.8** | 2 |
| 3 | Professional Services | 69.7 | 57.5 | 25.0 | 25.9 | **46.7** | 4 |
| 4 | Manufacturing | 69.7 | 57.5 | 25.0 | 25.9 | **46.7** | 4 |
| 5 | Technology | 69.7 | 57.5 | 25.0 | 25.9 | **46.7** | 4 |
| 6 | Financial | 69.7 | 57.5 | 25.0 | 25.9 | **46.7** | 4 |
| 7 | Services | 69.4 | 7.5 | 11.2 | 23.1 | **30.1** | 2 |

---

## Latest Signals Detail

| Ticker | Category | Source | Score | Confidence | Raw Value |
|--------|----------|--------|-------|------------|-----------|
| UNH | technology_hiring | LinkedIn_Indeed | 92.9 | 0.95 | 50/54 highly AI-relevant jobs (avg relevance: 0.87) |
| JPM | technology_hiring | LinkedIn_Indeed | 90.0 | 0.95 | 129/140 highly AI-relevant jobs (avg relevance: 0.74) |
| WMT | technology_hiring | LinkedIn_Indeed | 88.7 | 0.95 | 79/88 highly AI-relevant jobs (avg relevance: 0.74) |
| HCA | technology_hiring | LinkedIn_Indeed | 81.1 | 0.95 | 47/58 highly AI-relevant jobs (avg relevance: 0.62) |
| CAT | innovation_activity | google_patents | 80.0 | 0.90 | 17 AI patents (CPC G06N, last 5y window) |
| DE | innovation_activity | google_patents | 80.0 | 0.90 | 22 AI patents (CPC G06N, last 5y window) |
| WMT | innovation_activity | google_patents | 80.0 | 0.90 | 60 AI patents (CPC G06N, last 5y window) |
| UNH | innovation_activity | google_patents | 80.0 | 0.90 | 30 AI patents (CPC G06N, last 5y window) |
| GS | technology_hiring | LinkedIn_Indeed | 79.6 | 0.95 | 75/96 highly AI-relevant jobs (avg relevance: 0.64) |
| PAYX | technology_hiring | LinkedIn_Indeed | 72.4 | 0.51 | 1/1 highly AI-relevant jobs (avg relevance: 0.52) |
| ADP | technology_hiring | LinkedIn_Indeed | 66.4 | 0.69 | 11/19 highly AI-relevant jobs (avg relevance: 0.58) |
| WMT | digital_presence | tech_stack_scrape | 65.0 | 0.85 | 4 AI technologies detected from 7 seed sources (ticker=WMT) |
| UNH | leadership_signals | company_website | 64.1 | 0.60 | 2 executives analyzed |
| TGT | technology_hiring | LinkedIn_Indeed | 60.6 | 0.95 | 50/99 highly AI-relevant jobs (avg relevance: 0.51) |
| DE | technology_hiring | LinkedIn_Indeed | 55.8 | 0.81 | 14/31 highly AI-relevant jobs (avg relevance: 0.43) |
| GS | digital_presence | tech_stack_scrape | 55.0 | 0.85 | 3 AI technologies detected from 3 seed sources (ticker=GS) |
| CAT | technology_hiring | LinkedIn_Indeed | 53.4 | 0.95 | 31/79 highly AI-relevant jobs (avg relevance: 0.49) |
| GS | leadership_signals | company_website | 46.9 | 0.75 | 5 executives analyzed |
| JPM | leadership_signals | company_website | 41.7 | 0.90 | 8 executives analyzed |
| GS | innovation_activity | google_patents | 40.0 | 0.90 | 4 AI patents (CPC G06N, last 5y window) |
| HCA | leadership_signals | company_website | 39.0 | 0.70 | 4 executives analyzed |
| TGT | leadership_signals | company_website | 35.4 | 0.95 | 11 executives analyzed |
| PAYX | leadership_signals | company_website | 33.5 | 0.75 | 5 executives analyzed |
| HCA | digital_presence | tech_stack_scrape | 32.5 | 0.85 | 2 AI technologies detected from 2 seed sources (ticker=HCA) |
| TGT | digital_presence | tech_stack_scrape | 32.5 | 0.85 | 2 AI technologies detected from 4 seed sources (ticker=TGT) |
| JPM | innovation_activity | google_patents | 30.0 | 0.90 | 4 AI patents (CPC G06N, last 5y window) |
| WMT | leadership_signals | company_website | 26.7 | 0.95 | 45 executives analyzed |
| ADP | digital_presence | tech_stack_scrape | 22.5 | 0.85 | 1 AI technologies detected from 2 seed sources (ticker=ADP) |
| JPM | digital_presence | tech_stack_scrape | 22.5 | 0.85 | 1 AI technologies detected from 3 seed sources (ticker=JPM) |
| UNH | digital_presence | tech_stack_scrape | 22.5 | 0.85 | 1 AI technologies detected from 3 seed sources (ticker=UNH) |
| DE | digital_presence | tech_stack_scrape | 22.5 | 0.85 | 1 AI technologies detected from 2 seed sources (ticker=DE) |
| ADP | innovation_activity | google_patents | 15.0 | 0.90 | 1 AI patents (CPC G06N, last 5y window) |
| ADP | leadership_signals | company_website | 12.6 | 0.95 | 12 executives analyzed |
| DE | leadership_signals | company_website | 7.5 | 0.55 | 1 executives analyzed |
| CAT | leadership_signals | company_website | 7.5 | 0.55 | 1 executives analyzed |
| PAYX | digital_presence | tech_stack_scrape | 0.0 | 0.50 | 0 AI technologies detected from 1 seed sources (ticker=PAYX) |
| HCA | innovation_activity | google_patents | 0.0 | 0.90 | 0 AI patents (CPC G06N, last 5y window) |
| CAT | digital_presence | tech_stack_scrape | 0.0 | 0.50 | 0 AI technologies detected from 1 seed sources (ticker=CAT) |

---

## Key Findings

### Top 3 Companies by Do Score (Actual AI Investment)

1. **WMT** — Do Score: 68.2
2. **UNH** — Do Score: 66.3
3. **GS** — Do Score: 57.0

### Bottom 3 Companies by Do Score

1. **TGT** — Do Score: 33.4
2. **ADP** — Do Score: 31.8
3. **PAYX** — Do Score: 28.4

### Top 3 Companies by Say Score (AI Rhetoric)

1. **ADP** — Say Score: 100.0
2. **PAYX** — Say Score: 93.7
3. **UNH** — Say Score: 93.1

### Biggest Say-Do Gaps (Potential Overstaters)

1. **ADP** — Say: 100.0, Do: 31.8, Gap: +68.2
2. **PAYX** — Say: 93.7, Do: 28.4, Gap: +65.3
3. **HCA** — Say: 76.1, Do: 40.2, Gap: +35.8

### Quiet Builders (Do > Say)

1. **WMT** — Say: 60.3, Do: 68.2, Gap: -7.9
2. **JPM** — Say: 44.9, Do: 48.5, Gap: -3.6
3. **DE** — Say: 47.1, Do: 43.9, Gap: +3.2

---

*Report generated from Snowflake database and SEC filing analysis.*