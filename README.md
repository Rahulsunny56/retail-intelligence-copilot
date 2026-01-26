# 🚀 Project Overview

Retail Intelligence Copilot is an end-to-end, production-style AI system that transforms raw retail transaction data into actionable, business-ready promotion recommendations using modern data engineering, retrieval-augmented generation (RAG), and agentic AI.

The project simulates how a real retail or e-commerce organization would design an intelligent promotion engine—one that understands vague user intent (e.g., “avocado”), maps it to canonical products, analyzes historical purchasing behavior, and generates explainable promotional bundles that maximize basket size and customer value.

Rather than relying on a single LLM prompt, the system is built as a multi-agent workflow with explicit feature engineering, ranking logic, and business constraints. Every recommendation is grounded in real transactional data and backed by measurable signals such as reorder rates, co-purchase strength, and sales velocity.

# 🛒 Retail Intelligence Copilot (Agentic AI + RAG + Promotions)

An end-to-end **agentic AI retail intelligence platform** that combines **data engineering, feature stores, retrieval-augmented generation (RAG), multi-agent decisioning, promotion optimization, and API/UI delivery** using real-world retail data.

This project simulates how modern retailers (Instacart, Walmart, Amazon Fresh, Kroger, etc.) build **AI-powered product discovery, recommendations, and promotional intelligence systems**.

---

## 🚀 What This Project Does

- Ingests **real retail transaction data (Instacart)** into a relational warehouse
- Builds **analytics-grade feature tables** (SKU velocity, basket affinity)
- Creates **RAG pipelines** for semantic product understanding
- Implements **multi-agent workflows** using LangGraph
- Generates **promotion bundles** with business logic (themes, offers, placements)
- Exposes results via **FastAPI endpoints**
- Tracks experiments with **MLflow**
- Provides a **UI for demo and storytelling**
- Is fully version-controlled and production-structured

---
## 🧱 High-Level Architecture

<pre>
Instacart Dataset (CSV)
        |
        v
PostgreSQL (Warehouse)
        |
        |── Feature Tables (SQL)
        |      ├─ SKU Velocity
        |      └─ Basket Affinity
        |
        |── RAG Documents (Parquet)
        |
        v
Vector Store (Chroma)
        |
        v
Agentic AI Layer (LangGraph)
        ├─ Product Discovery Agent
        ├─ Recommendation Agent
        └─ Promotion Agent
        |
        v
FastAPI
        ├─ REST API
        └─ Simple UI
</pre>

## ▶️ How to Run the Project
- docker compose up -d
- uvicorn api.main:app --reload --port 8000

# ✅ UI OUTPUT
<img width="2008" height="1578" alt="image" src="https://github.com/user-attachments/assets/8e33fff7-dd6b-459b-a183-0c0214c8e91c" />

## 🎯 Key Takeaways

- This project demonstrates:
- End-to-end AI system design
- Real feature engineering (not embeddings only)
- RAG in a production context
- Agentic AI workflows (LangGraph)
- Business-aware promotion logic
- API + observability (MLflow)
- Clean engineering practices

# 👤 Author

Rahul Uplanchiwar
Data Engineer / AI Engineer
California, USA

## 🔮 Future Extensions

- A/B testing promo lift
- Real-time streaming (Kafka)
- User segmentation
- Reinforcement learning for promotions
- Cloud deployment (AWS / Azure / GCP)




       
