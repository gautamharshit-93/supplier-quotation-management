# Supplier Quotation Management

This project is a Streamlit-based procurement dashboard that helps a buyer compare supplier quotations against an RFQ (Request for Quotation), identify gaps, estimate cash outlay, answer document questions from the indexed content, and draft supplier emails.

It is designed to work in two modes:

- Local / no-API mode: works immediately with no external keys
- AI-assisted mode: uses OpenAI for better parsing, extraction, and multilingual Q&A when an API key is configured

The main idea is simple: upload one RFQ and multiple supplier quotations, then let the app normalize the data, compare it side-by-side, and show which supplier is more compliant and cheaper.

---

## 1. What problem this project solves

In real procurement workflows, suppliers send quotations in different formats:

- Excel sheets
- PDFs
- Word documents
- sometimes mixed English/Hindi text
- sometimes messy tables and inconsistent fields

A buyer needs to know:

- Which supplier quoted the lowest price for each item?
- What is the total cost from each supplier?
- Did the supplier miss any required items or required fields?
- Is the quote compliant with the RFQ?
- How much cash is needed upfront based on payment terms?
- Which document contains the answer to a question?
- What email should be sent to ask for missing information or award the order?

This project centralizes these tasks in one workflow.

---

## 2. High-level workflow

The user flow is:

1. Upload an RFQ file
2. Upload one or more supplier quotation files
3. Click Process documents
4. The app parses each file
5. It extracts structured data from each document
6. It compares quotations with the RFQ
7. It calculates totals, item-level prices, and gap scores
8. It builds a vector index for retrieval-based Q&A
9. It shows analysis tables and charts in the dashboard
10. It can generate email drafts for follow-up or award

This is implemented in [app.py](app.py), which is the main entry point.

---

## 3. How the app works in practice

### 3.1 Upload step

The UI in [app.py](app.py) uses Streamlit to show:

- an RFQ uploader
- a supplier quotation uploader
- a Process documents button

When the button is clicked, the app does the following:

- saves the uploaded files in the storage folder
- parses each file into raw text/tables
- extracts normalized fields like supplier, dates, item list, totals, terms, and warranty
- stores the processed results in memory for the session
- builds a local vector index for question answering

### 3.2 Parsing stage

The parser dispatches based on file extension in [src/parsers/__init__.py](src/parsers/__init__.py):

- .xlsx / .xls -> Excel parser
- .pdf -> PDF parser
- .docx / .doc -> Word parser

Each parser converts raw documents into a common structure such as:

- raw_text: flattened readable text
- tables: extracted tabular data if available
- sheets: Excel sheet rows if it is a workbook
- source: file path
- file_type: excel / pdf / docx

This standardization is critical, because all later modules expect a common document shape.

### 3.3 Extraction stage

The extraction intelligence lives in [src/extraction/rfq_extractor.py](src/extraction/rfq_extractor.py).

This module turns raw text and tables into a normalized procurement schema such as:

- supplier_name
- quotation_ref
- rfq_ref
- deadline_date
- currency
- items[]
- delivery_terms
- delivery_lead_time_days
- payment_terms
- warranty
- notes

Each item is normalized to include:

- item_name
- quantity
- unit
- unit_price
- total_price
- portion
- packaging

#### Without OpenAI

The project uses heuristic parsing based on:

- table headers
- row/column keys
- common keywords like Supplier, Item, Quantity, Unit Price, RFQ Ref, Deadline
- date normalization formats like DD/MM/YYYY or YYYY-MM-DD

This works well for structured documents, especially Excel and clearly formatted tables.

#### With OpenAI

If `OPENAI_API_KEY` is set, the app calls GPT to read raw text and return JSON that matches the procurement schema.

This is especially better for:

- messy PDFs
- mixed Hindi/English text
- inconsistent layouts
- free-form quotations

The local heuristic path is still used as a fallback if the LLM call fails.

---

## 4. Project architecture

### Main app entry

- [app.py](app.py): Streamlit UI and orchestrator

### Configuration

- [config.py](config.py): loads environment variables and central settings
- [.env.example](.env.example): template for optional API and cloud keys

### Storage layer

- [src/storage/local_storage.py](src/storage/local_storage.py): default storage backend
- [src/storage/azure_storage.py](src/storage/azure_storage.py): optional Azure upgrade path
- [src/storage/__init__.py](src/storage/__init__.py): abstracted backend selection

The storage layer saves:

- uploaded raw files
- processed record metadata
- local records database

### Parsers

- [src/parsers/excel_parser.py](src/parsers/excel_parser.py): parse Excel workbooks
- [src/parsers/pdf_parser.py](src/parsers/pdf_parser.py): parse PDFs locally or via LlamaParse
- [src/parsers/docx_parser.py](src/parsers/docx_parser.py): parse Word documents
- [src/parsers/__init__.py](src/parsers/__init__.py): route to the right parser

### Analysis modules

- [src/analysis/cost_comparison.py](src/analysis/cost_comparison.py): item-wise and supplier-wise comparison
- [src/analysis/gap_analysis.py](src/analysis/gap_analysis.py): compliance and missing-information gap checks
- [src/analysis/investment_calc.py](src/analysis/investment_calc.py): estimate upfront cash based on payment terms

### Vector store and chatbot

- [src/vectorstore/faiss_store.py](src/vectorstore/faiss_store.py): FAISS indexing and retrieval
- [src/chatbot/query_bot.py](src/chatbot/query_bot.py): RAG-style Q&A over indexed docs

### Email module

- [src/mailer/email_sender.py](src/mailer/email_sender.py): render and optionally send emails in English/Hindi

### Internationalization

- [src/utils/i18n.py](src/utils/i18n.py): English/Hindi UI text support

---

## 5. What the system does with the data

### 5.1 Cost comparison

Once quotations are extracted, the app compares them item by item.

For every supplier and every item, it reads:

- item_name
- quantity
- unit
- unit_price
- total_price

If total_price is not present but quantity and unit_price are present, it calculates:

- total_price = quantity × unit_price

This is done in [src/analysis/cost_comparison.py](src/analysis/cost_comparison.py).

The app then creates:

- item-wise comparison table
- supplier-wise total cost summary
- cheapest supplier per item
- total quoted cost per supplier
- bar charts for easy comparison

### 5.2 Gap analysis

The RFQ is treated as the required target, and each quotation is compared against it.

The logic in [src/analysis/gap_analysis.py](src/analysis/gap_analysis.py) checks:

- missing required items
- missing fields such as payment terms, delivery terms, warranty, lead time
- missing packaging or portion specifications
- comparison against the RFQ deadline

It creates a score called `gap_score`:

- each missing item adds weight
- each missing required field adds weight
- missing packaging/portion adds smaller penalties

Lower gap score = more complete and compliant quotation.

### 5.3 Investment analysis

The investment module in [src/analysis/investment_calc.py](src/analysis/investment_calc.py) estimates how much money must be paid upfront according to payment terms.

Example logic:

- if payment terms say “30% advance, balance on delivery”
- and the total quoted cost is 100,000
- then upfront_cash_required = 30,000
- balance_on_delivery = 70,000

If the advance percentage is not clearly specified, the project leaves it blank instead of guessing.

### 5.4 Query bot / RAG

The vector store indexes all parsed document text in [src/vectorstore/faiss_store.py](src/vectorstore/faiss_store.py).

Each document is split into chunks and stored in a FAISS vector database. The chatbot in [src/chatbot/query_bot.py](src/chatbot/query_bot.py):

- receives the user question
- finds similar chunks from the vector store
- retrieves the most relevant excerpts
- returns the answer using the retrieved content

#### Without OpenAI

It returns the retrieved source excerpts directly.

#### With OpenAI

It generates a more natural answer in English or Hindi using the retrieved context as grounding.

---

## 5.5 Dashboard output examples: what the user actually sees

The app is not just a backend engine; it renders several decision-support views in a Streamlit dashboard. These are the real tab outputs the screenshots show.

### 5.5.1 Cost comparison tab

This tab is the main pricing comparison view. It displays a long-form table with columns like:

- item_name
- supplier_name
- quantity
- unit
- unit_price
- total_price
- portion
- packaging

This is the raw itemized comparison output. A second visual table, called "Unit price by item × supplier", pivots the data so each supplier appears as a column per item. This is useful for quick comparison of price differences across suppliers.

Example from the app:

- Air Filter (OEM Specification): 355, 365, 350 across suppliers
- Engine Mount Assembly (OEM Grade): 1,795, 1,810, 1,780
- Shock Absorber: 2,125, 2,140, 2,100

The app also shows a total cost summary table and a bar chart for total quoted cost per supplier. In the screenshot, the supplier with the lowest total cost is ranked first and highlighted as the cheapest overall option.

### 5.5.2 Total quoted cost per supplier

This section aggregates all item prices by supplier. The application groups all item totals by `supplier_name` and sums them into a total cost:

- total_quoted_cost = sum of all item total_price values

This creates the supplier ranking visible in the dashboard. The bar chart makes it easy to compare total costs visually, while the table also shows:

- `savings_vs_cheapest`
- `rank`

This is important because a supplier may not be cheapest on every item but still be the best total value overall.

### 5.5.3 Cheapest supplier per item

This table identifies the lowest price supplier for each item. It is calculated by taking the minimum `unit_price` for each `item_name` and returning the supplier that supplied it.

The result is a useful shortlist for negotiation and buyer discussions. In the screenshot, this section shows the best supplier for each item, along with quantity and total price for that specific item.

### 5.5.4 Investment / cash outlay tab

This tab uses payment-term interpretation to estimate the upfront financial burden. It reads payment terms such as "30% advance, balance on delivery" and calculates:

- advance_payment_pct
- upfront_cash_required
- balance_on_delivery
- delivery_lead_time_days

If the app cannot clearly detect the percentage, it leaves the value as blank instead of guessing. This is intentional and reduces the chance of wrong financial estimates.

The screenshot shows a table with columns like:

- supplier_name
- total_quoted_cost
- payment_terms
- advance_payment_pct
- upfront_cash_required
- balance_on_delivery
- delivery_lead_time_days

This is the real cash-flow view for procurement planning.

### 5.5.5 Gap analysis tab

This tab shows which supplier quote is most compliant with the RFQ. The app compares the RFQ items against each supplier quote and highlights missing information.

The screenshot shows columns such as:

- supplier_name
- missing_items
- missing_fields
- items_missing_packaging
- items_missing_portion
- gap_score

Example output from the app:

- supplier with missing items like 1, 2, 3, 4, air filter, engine mount assembly, front brake disc, shock absorber
- missing fields such as Delivery terms, Payment terms, Warranty, Delivery lead time
- gap_score values such as 32 or 35

Lower `gap_score` means the supplier is more compliant with the RFQ.

### 5.5.6 Email tab

This tab is used to draft a follow-up email when the supplier is missing required information.

The screenshot demonstrates a real email workflow:

- supplier selected
- email type chosen (gap follow-up or award notification)
- supplier email address entered
- a generated Hindi subject and body with details of missing items and fields
- "Send / Save draft" button appears

This is where the app turns the analysis into action. Instead of a manual copy-paste workflow, the system prepares the message automatically using the RFQ reference and the missing gap details.

### 5.5.7 Final Summary tab

This tab combines the financial and compliance signals into a single decision-support ranking.

The underlying logic is:

- cost weight: 60%
- RFQ compliance weight: 40%

The app calculates a composite score and ranks the suppliers from best to worst. In the screenshot, the recommended supplier is the one with the lowest combined score.

The result is shown as a table with columns such as:

- supplier_name
- total_quoted_cost
- savings_vs_cheapest
- rank
- gap_score
- composite_score

The app also displays a recommendation banner such as:

> Recommended supplier: ABC Automotive Pvt. Ltd. Company: Varroc Engineering Limited — lowest combined score of total cost (60% weight) and RFQ compliance/completeness (40% weight).

This is explicitly described as a decision-support ranking, not an automatic award.

---

## 6. Local mode vs API mode

### Local / no-key mode

This works without any external credential.

Features available:

- upload files
- parse Excel, PDF, Word
- extract fields using structured heuristics
- compare supplier pricing
- compute totals and gap analysis
- estimate investment/cash outflow
- create local FAISS index
- ask questions against indexed documents
- draft emails in English and Hindi

Important note:

- no real email sending unless SMTP credentials are configured
- no AI-generated natural-language summary unless OpenAI is configured

### AI mode

When `OPENAI_API_KEY` is configured:

- extraction uses GPT JSON generation
- the query bot generates natural-language answers
- text is still grounded in the retrieved document chunks
- multimodal and mixed-language document handling becomes more robust

Other optional upgrades include:

- OpenAI embeddings via `EMBEDDINGS_MODE=openai`
- Azure Blob + Cosmos storage
- LlamaParse for better PDF parsing
- real SMTP email sending

---

## 7. Data flow, end-to-end

A typical run looks like this:

1. User uploads RFQ and quotations
2. [app.py](app.py) calls `save_uploaded_file()`
3. Files are stored under `data/uploads`
4. `parse_document()` chooses parser by extension
5. Raw text + tables are extracted
6. `extract_structured_data()` normalizes the document into procurement fields
7. The RFQ and quotations are saved as records in the local database JSON
8. The app builds item-wise and total-cost comparison tables
9. It compares RFQ requirements against each supplier quote
10. It stores the parsed text in a FAISS vector index
11. The chat Q&A agent can search this index
12. The dashboard renders charts, tables, and recommendation summaries
13. Optionally it generates emails for gap follow-up or award notification

---

## 8. How calculation logic works

### 8.1 Total cost per supplier

The app groups all item totals by supplier name:

- supplier_name
- total_quoted_cost = sum of all quoted item totals

This is computed in [src/analysis/cost_comparison.py](src/analysis/cost_comparison.py).

### 8.2 Cheapest supplier per item

For each item, the app selects the supplier with the minimum unit price:

- item_name
- supplier_name
- best_unit_price

### 8.3 Gap score

Gap score is a weighted comparison between required RFQ items and supplier responses.

The formula is essentially:

- missing items × 3
- missing required fields
- missing packaging records
- missing portion details

This creates a simple numeric compliance ranking.

### 8.4 Final recommendation

The final summary tab uses a composite score:

- 60% weight on cost
- 40% weight on gap/compliance

This is meant as decision support, not a final award decision.

---

## 9. Storage and persistence

The project stores documents in the local `data/` folder by default:

- `data/uploads` - raw uploaded files
- `data/processed` - processed data/output area
- `data/vector_index` - FAISS index
- `data/db/records.json` - local record metadata store

This is configured in [config.py](config.py).

The code supports an Azure upgrade path via [src/storage/azure_storage.py](src/storage/azure_storage.py), but the default is local storage for zero-setup operation.

---

## 10. Email system

The email module [src/mailer/email_sender.py](src/mailer/email_sender.py) can:

- build a missing-information request email
- build an award notification email
- send via SMTP if configured
- otherwise return a draft instead of sending

It supports both English and Hindi content.

This is useful because after gap analysis, the user may want to ask a supplier to provide missing documentation or confirm an item.

---

## 11. Sample data

The project includes sample demo files in [sample_data/generate_sample_data.py](sample_data/generate_sample_data.py).

Running this script creates:

- sample RFQ Excel file
- sample supplier quotation Excel file
- sample supplier quotation Word file
- sample supplier quotation PDF file

This allows the app to be tested immediately without preparing actual procurement data.

---

## 12. Setup and run

### Prerequisites

- Python 3.10+
- pip

### Install dependencies

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Optional demo data

```bash
python sample_data/generate_sample_data.py
```

### Optional environment setup

```bash
cp .env.example .env
```

Then edit `.env` for optional configuration such as:

- `OPENAI_API_KEY`
- `SMTP_USERNAME` / `SMTP_PASSWORD`
- `STORAGE_BACKEND`
- `AZURE_*` values
- `LLAMA_CLOUD_API_KEY` for optional cloud parsing

### Run the app

```bash
streamlit run app.py
```

Then open the local Streamlit URL and upload the sample RFQ + supplier quotations.

---

## 13. Dependencies used in the project

From [requirements.txt](requirements.txt), the app relies on libraries such as:

- Streamlit for the dashboard UI
- pandas for tabular analysis
- openpyxl for Excel parsing
- python-docx for Word files
- pdfplumber for PDF extraction
- langchain and FAISS for vector search
- sentence-transformers for local embeddings
- openai for optional AI features
- plotly for charts

This gives the project a practical AI + analytics stack without requiring a heavy backend.

---

## 14. Important design principles

### Modular design

Each concern has a dedicated module:

- parsing
- extraction
- analysis
- storage
- vector retrieval
- email generation
- UI

This keeps the code easier to maintain and extend.

### No-API-safe by default

The project is intentionally designed to work even if no API key is set.

This makes it useful for demos, local testing, and environments where users do not want cloud dependencies.

### AI upgrade path

The code is structured so the system can upgrade later without rewriting the whole app:

- switch extraction to GPT
- switch embeddings to OpenAI
- switch storage to Azure
- enable real SMTP sending

---

## 15. Best practices and limitations

### Strengths

- Works immediately with local files
- Handles common procurement document layouts
- Good for side-by-side negotiation comparisons
- Useful for internal decision support
- Works in English/Hindi UI and some multilingual document support

### Limitations

- Heuristic extraction may miss unusual layouts or unstructured PDFs
- OCR-like or highly noisy documents may need AI extraction for better accuracy
- Final recommendation should still be reviewed by a human before approving a supplier
- Payment questions or ambiguous terms are left blank rather than guessed when unclear

---

## 16. Summary

This system is a complete RFQ-to-quotation decision support tool in one Streamlit app.

It does the following:

- accepts procurement docs
- parses them reliably
- extracts structured data
- compares prices across suppliers
- checks compliance against the RFQ
- estimates cash outlay and advance payment needs
- answers questions using the indexed documents
- supports bilingual workflow and email drafting

In short, it helps procurement teams move from messy supplier documents to a structured, comparable, and decision-ready view.

---

## 17. Quick start checklist

1. Create virtual environment
2. Install dependencies
3. Generate sample data (optional)
4. Run `streamlit run app.py`
5. Upload an RFQ and quotations
6. Click Process documents
7. Review cost comparison, gap analysis, investment, chatbot, and email tabs
8. Add OpenAI / SMTP / Azure only when needed for stronger features

This project is built to be practical, transparent, and usable without any cloud setup, while still allowing advanced AI features when the user adds API keys.
