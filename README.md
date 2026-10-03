# Complaint Triage RAG

A retrieval augmented system that reads free text customer complaints, works out which product and sub product each one is about, and stores it in a structured PostgreSQL database so it can be routed to the right team.

Built during the Headstarter AI Software Engineering Fellowship (2024).

## The problem

Customers rarely describe a problem in the company's own terms. A complaint like "you took money twice and the app won't let me dispute it" could belong to cards, payments or the mobile app. When complaints are vague, they get misfiled, bounce between teams and take longer to resolve. This project uses examples of already categorised complaints to classify new ones consistently, even when the wording is unclear.

## How it works

```
Labelled example complaints (JSON)
     │
     ▼
Embeddings (sentence-transformers all-MiniLM-L6-v2)  ──►  Pinecone vector index
                                                               │
New complaint ──► embed ──► retrieve 10 most similar examples ─┘
     │
     ▼
LLM (Qwen 2 7B Instruct via OpenRouter) with a strict output format:
     Product: ...
     Sub-product: ...
     Complaint: ...
     │
     ▼
Parse and validate fields  ──►  reject if any field is missing
     │
     ▼
PostgreSQL (products ► subproducts ► complaints)
```

1. **Retrieve.** The incoming complaint is embedded and compared against labelled examples in Pinecone, so the model sees how similar complaints were categorised before.
2. **Classify.** The model is constrained to a fixed three field format, which keeps its output predictable and machine readable.
3. **Validate.** Each field is extracted and checked. If the model leaves anything out, the complaint is rejected instead of being stored with bad data.
4. **Store.** Valid complaints are written to PostgreSQL through SQLAlchemy. New products and sub products are created automatically the first time they appear, so the category structure grows with the data.

## Data model

| Table | Key fields | Purpose |
| ----- | ---------- | ------- |
| `products` | id, name | Top level product categories |
| `subproducts` | id, product_id, name | Categories within each product |
| `complaints` | id, sub_product_id, complaint, created_at | Each stored complaint, linked to its category |

Because every complaint is linked to a product and sub product, the database supports reporting such as complaint volume by product or trends over time.

## API endpoints

| Method | Endpoint | What it does |
| ------ | -------- | ------------ |
| POST | `/rag` | Classify a complaint, store it and return the result |
| POST | `/stream_rag` | Same as above, with the response streamed |
| POST | `/ingest_json` | Upload labelled example complaints to the vector index |

Example request:

```
curl -X POST http://localhost:8000/rag \
  -H "Content-Type: application/json" \
  -d '{"query": "I was charged twice for the same purchase and the app will not let me raise a dispute"}'
```

Example response:

```
Product: Credit card
Sub-product: Billing dispute
Complaint: Customer was charged twice for one purchase and cannot raise a dispute in the app
```

## Tech stack

Python, FastAPI, Pinecone, PostgreSQL, SQLAlchemy, LangChain, sentence-transformers, OpenRouter (Qwen 2 7B Instruct), Uvicorn

## Running locally

1. Clone and install

```
git clone https://github.com/nwaniayo/complaint-triage-rag.git
cd complaint-triage-rag
pip install -r requirements.txt
```

2. Create a `.env` file

```
OPENROUTER_API_KEY=your_key
PINECONE_API_KEY=your_key
DATABASE_URL=postgresql://user:password@localhost:5432/complaints
```

3. Create a Pinecone index with dimension 384 (to match all-MiniLM-L6-v2).

4. Start the server. Tables are created automatically on startup.

```
uvicorn main:app --reload
```

5. Run `python test.py` to check the database connection and storage logic with a sample complaint.

## Possible improvements

* Measure classification accuracy against a held out set of labelled complaints
* Return a confidence score and send low confidence cases to a human reviewer
* Add priority scoring so urgent complaints, such as suspected fraud, are flagged first
