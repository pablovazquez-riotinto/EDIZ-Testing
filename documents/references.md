# References

## KG-R1: Efficient and Transferable Agentic Knowledge-Graph RAG via Reinforcement Learning

### 1. The Core Idea

| Traditional KG-RAG | KG-R1 Approach |
|-------------------|-----------------|
| Multiple modules (retriever, planner, reasoner, responder) | Single agent integrates retrieval and reasoning |
| Each stage separately calls an LLM → high cost | One LLM interacts with a KG server in short cycles |
| Schema-specific, requires fine-tuning | Schema-agnostic, same logic works across graphs |
| Fixed prompts or supervised learning | Reinforcement learning teaches exploration and accuracy |

### 2. System Structure

```
                ┌──────────────────────────────┐
                │     Knowledge Graph Server    │
                │  • stores entities & triples  │
                │  • supports 4 basic actions   │
                │    1. get_tail_relations      │
                │    2. get_head_relations      │
                │    3. get_tail_entities       │
                │    4. get_head_entities       │
                └──────────────┬───────────────┘
                               │
                    (API interaction)
                               │
                ┌──────────────▼──────────────┐
                │        KG-R1 Agent          │
                │  • single LLM               │
                │  • uses <think> reasoning   │
                │  • issues <kg-query> calls  │
                │  • combines retrieved facts │
                │    into <answer> output     │
                └─────────────────────────────┘
```

### 3. How It Works — Reasoning Cycle

| Step | Action | Description |
|------|--------|-------------|
| 1 | Initialize prompt | Question + KG query instructions |
| 2 | Reasoning (<think>) | LLM analyses current context |
| 3 | KG query (<kg-query>) | Calls one of the 4 graph actions |
| 4 | Receive information | KG server returns entities or relations |
| 5 | Multi-turn exploration | Up to 7 turns of reasoning + retrieval |
| 6 | Generate final answer | Combines all retrieved facts inside <answer> |
| 7 | Reinforcement signal | Reward computed from correctness & efficiency |

Each "conversation" between the agent and the graph forms a traceable reasoning path.

### 4. Training with Reinforcement Learning

| Component | Function |
|-----------|----------|
| Algorithm | Group Relative Policy Optimization (GRPO) — a stable variant of PPO |
| Reward signals | (a) Local turn-level validity and retrieval success<br>(b) Global outcome accuracy (F1 on answer)<br>(c) Retrieval relevance |
| Learning objective | Maximize both answer quality and search efficiency |
| Effect | Model learns when to query, how deep to explore, and when to stop |

Efficiency gain: about 83% of tokens come from KG retrieval (cheap) and only ~13% from generation (expensive).

### 5. Why It Matters

| Advantage | Explanation |
|-----------|-------------|
| Single-Agent Simplicity | Removes the need for separate retriever and reasoner modules |
| Cross-Graph Transferability | Works on different KG schemas (Freebase, Wikidata, temporal) without retraining |
| Efficiency | Fewer tokens and LLM calls reduce cost and latency |
| Explainability | The <think> + <kg-query> trace shows exactly how each answer was derived |
| End-to-End Learning | The system learns reasoning strategies, not just text prediction |

### 6. Example Interaction (Simplified)

```
<think>Find who wrote the book "Ethics of AI".</think>
<kg-query>get_tail_relations("Ethics of AI")</kg-query>
<information>written_by: John Smith</information>
<think>Now find John's university affiliation.</think>
<kg-query>get_tail_entities("John Smith", "affiliated_with")</kg-query>
<information>University of Oxford</information>
<answer>John Smith, University of Oxford.</answer>
```

The reasoning trace itself explains how the model reached the final answer.

### 7. Key Results (from benchmarks)

| Dataset | Metric | Prior Multi-Module (avg) | KG-R1 (3-run avg) |
|---------|--------|--------------------------|-------------------|
| WebQSP | F1 / Hit@1 | 73.7 / 81.1 | 85.8 / 91.7 |
| ComplexWebQuestions | F1 / Hit@1 | 64.7 / 66.8 | 81.0 / 83.9 |
| Cross-Graph Transfer (avg) | F1 / Hit@1 | 68.2 / 68.2 | 74.1 / 79.4 |
| Efficiency | Tokens per query | 3–4K | ~1K (70% less) |

### 8. Conceptual Impact

**Before:**
Reasoning pipelines with multiple LLMs stitched together, schema-specific, high token cost.

**After:**
A unified agentic framework that can reason and retrieve across any graph with low cost, transparent logic, and transferable capability.

### 9. Potential Extensions

| Direction | Description |
|-----------|-------------|
| Industrial knowledge graphs | Apply the same agent to process networks, equipment hierarchies, or supply systems to trace causes and effects. |
| Hybrid reasoning | Combine graph traversal with text retrieval to answer multi-source questions. |
| Multi-agent cooperation | Use several KG-aware agents specialising in different domains that share graph context. |
| Real-time graph updates | Link the agent to dynamic KGs (e.g., IoT or live telemetry). |
| Energy-efficient RL | Optimise token use and retrieval depth together to minimise compute cost. |

### 10. Takeaway

KG-R1 shows that a single reinforcement-trained agent can learn to explore, reason, and answer questions over any structured knowledge graph.
It replaces complex multi-module pipelines with an efficient, explainable, and transferable framework for connected reasoning — a step toward practical, general-purpose graph-augmented intelligence.

### Citation

```bibtex
@article{kg_r1_2025,
  title={KG-R1: Efficient and Transferable Agentic KG-RAG via RL},
  author={[Authors]},
  journal={arXiv preprint arXiv:[ARXIV_ID]},
  year={2025}
}
```