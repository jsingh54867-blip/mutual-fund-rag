Task:
Build a small Retrieval-Augmented Generation (RAG) FAQ chatbot that answers facts-only questions about mutual fund schemes using only official public sources.

📌 Objective

Create a chatbot that:

Answers factual queries only about mutual fund schemes
Uses a RAG pipeline (retrieval + LLM generation)
Includes exactly one source link per answer
Refuses advice/opinion-based queries
🧾 Functional Requirements
1. Scope
Select 1 AMC (Asset Management Company)
Select 3–5 schemes under that AMC, ensuring diversity:
1 Large-cap fund
1 Flexi-cap fund
1 ELSS fund
2. Data Collection
Collect 15–25 official public URLs only from:
AMC website (scheme pages, FAQs, factsheets, KIM/SID)
Association of Mutual Funds in India
Securities and Exchange Board of India
Allowed content:
Expense ratio
Exit load
Minimum SIP / investment
Lock-in (ELSS)
Riskometer
Benchmark
Statement download / tax documents
❌ Do NOT use:
Blogs
News sites
Third-party aggregators
3. Chatbot Capabilities

The assistant must answer questions like:

“What is the expense ratio of [scheme]?”
“What is the lock-in period for ELSS?”
“What is the minimum SIP amount?”
“What is the exit load?”
“What is the benchmark or riskometer?”
“How do I download a capital gains statement?”
4. Response Rules

Each response must:

Be ≤ 3 sentences
Be factually grounded in retrieved content
Include:
Clear answer
Exactly one source link
Line: Last updated from sources: <date if available>
5. Refusal Behavior

If the query asks for:

Advice (e.g., “Should I invest?”)
Comparison (e.g., “Which is better?”)
Performance/returns calculation

Respond with:

“I can only provide factual information about mutual fund schemes. I cannot offer investment advice.”

Also include one relevant official educational link (AMC/AMFI/SEBI).

6. Technical Requirements
Use RAG architecture:
Document loader (web/PDF)
Chunking
Embeddings
Vector database (FAISS / Chroma)
Retriever (top-k results)
LLM for answer generation
Add guardrails:
Query classification (fact vs advice)
Ensure answer is only from retrieved context
Force inclusion of one citation link
7. UI Requirements (Minimal)
Simple interface with:

Welcome message:

“Ask me factual questions about mutual funds. Facts-only. No investment advice.”

3 example queries
Input box + response display
🚫 Constraints
Public sources only
No PII collection (PAN, Aadhaar, phone, email, OTP, etc.)
No return calculations or performance claims
No hallucination—must rely strictly on retrieved documents
📦 Deliverables to Generate
Working prototype (Streamlit / notebook / simple web app)
Source list file (CSV or Markdown) with 15–25 URLs
README.md including:
Setup instructions
Selected AMC + schemes
Known limitations
Sample Q&A file:
5–10 queries with answers + source links
Disclaimer text used in UI
🧪 Success Criteria
Every answer includes exactly one valid source link
No advice is given
Answers are concise and accurate
Only official sources are used
System handles refusals correctly
🧠 Implementation Hint (Important)
Use strict prompting like:
“Answer ONLY from the provided context”
“If answer not found, say you don’t know”
Post-process output to ensure:
Exactly one link
Sentence limit
Refusal compliance