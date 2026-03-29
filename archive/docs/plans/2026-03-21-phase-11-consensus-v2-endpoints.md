# Phase 11: Consensus V2 + Infrastructure + Endpoints

> **For agentic workers:** Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Consensus V2 engine with industry best practices, infrastructure modules for account management and execution history, and new API endpoints (batch, pipeline, health/detailed, smart/v2).

**Architecture:** Three independent workstreams executed in parallel. Consensus V2 builds HAC clustering + debate + cross-pollination on top of existing consensus engine. Infrastructure adds account pooling, round weighting, multi-model execution, peer review reranking. Endpoints expose new capabilities via FastAPI routes.

**Tech Stack:** Python 3.11+, FastAPI, unittest, dataclasses, pure Python (no sklearn/numpy)

---

## Workstream 1: Consensus V2 Core (Agent 1)

7 new modules in `src/gracekelly/core/`, each with test file.

### Task 1.1: HAC Clustering (`clustering_hac.py`)
**Files:** Create `src/gracekelly/core/clustering_hac.py`, `tests/test_clustering_hac.py`

Pure Python hierarchical agglomerative clustering (no sklearn).
- `hac_cluster(similarity_matrix, threshold=0.85) -> list[list[int]]` — returns clusters of response indices
- Uses single-linkage: merge closest pair until distance > threshold
- Input: NxN similarity matrix (list[list[float]]), output: list of clusters (list[list[int]])
- Tests: identical vectors → 1 cluster, orthogonal → N clusters, threshold edge cases, empty input

### Task 1.2: Cluster Confidence (`cluster_confidence.py`)
**Files:** Create `src/gracekelly/core/cluster_confidence.py`, `tests/test_cluster_confidence.py`

- `ClusterConfidenceResult(top_cluster_size, total_responses, confidence, is_unanimous)`
- `compute_cluster_confidence(clusters, similarity_matrix) -> ClusterConfidenceResult`
- Confidence = top_cluster_size / total * avg_intra_cluster_similarity
- Tests: unanimous (1.0), split (< 1.0), single response, empty

### Task 1.3: Cross-Pollination (`cross_pollination.py`)
**Files:** Create `src/gracekelly/core/cross_pollination.py`, `tests/test_cross_pollination.py`

MoA-inspired: share top cluster's answer with non-cluster responses for refinement.
- `build_cross_pollination_prompt(original_prompt, top_response, other_response) -> str`
- `cross_pollinate(original_prompt, responses, clusters, execute_fn) -> list[str]`
- Only pollinate non-top-cluster responses. Returns refined responses.
- Tests: all in one cluster → no pollination, split → refinement called

### Task 1.4: Debate Round (`debate_round.py`)
**Files:** Create `src/gracekelly/core/debate_round.py`, `tests/test_debate_round.py`

Devil's Advocate challenges the top response.
- `build_debate_prompt(original_prompt, top_response) -> str`
- `DebateResult(challenge, defense, improved_response)`
- `run_debate(original_prompt, top_response, execute_fn) -> DebateResult`
- Tests: debate produces challenge + defense, improved response not empty

### Task 1.5: Divergence Handling (`divergence.py`)
**Files:** Create `src/gracekelly/core/divergence.py`, `tests/test_divergence.py`

When consensus is low, take structured action.
- `DivergenceAction` enum: ACCEPT, DEBATE, EXPAND, ESCALATE
- `DivergenceResult(action, reason, extra_rounds_needed)`
- `assess_divergence(consensus_score, num_clusters, round_number, max_rounds) -> DivergenceResult`
- Rules: score ≥ 0.9 → ACCEPT, score ≥ 0.7 → DEBATE, round < max → EXPAND, else → ESCALATE
- Tests: all 4 action paths

### Task 1.6: Adaptive Parameters (`adaptive_params.py`)
**Files:** Create `src/gracekelly/core/adaptive_params.py`, `tests/test_adaptive_params.py`

Tune consensus params by task type.
- `AdaptiveConsensusParams(consensus_target, max_rounds, min_responses, use_debate, use_cross_pollination)`
- `get_adaptive_params(task_type: TaskType) -> AdaptiveConsensusParams`
- coding → strict (target=0.95, debate=True), creative → loose (target=0.7, debate=False)
- Tests: each task type returns valid params, defaults work

### Task 1.7: Consensus V2 Executor (`consensus_v2.py`)
**Files:** Create `src/gracekelly/core/consensus_v2.py`, `tests/test_consensus_v2.py`

Full pipeline combining all V2 modules.
- `ConsensusV2Config(use_adaptive_params, use_debate, use_cross_pollination, use_cluster_confidence, use_divergence_handling)`
- `ConsensusV2Result(best_response, consensus_result, weighted_score, total_rounds, final_result)`
- `ConsensusExecutorV2(embeddings_client, config)` with `.execute(prompt, execute_fn) -> ConsensusV2Result`
- Pipeline: collect responses → embed → cluster (HAC) → confidence → divergence check → cross-pollinate if needed → debate if needed → return best
- Tests: basic execution, config flags toggle features, low consensus triggers debate

---

## Workstream 2: Infrastructure Modules (Agent 2)

6 new modules in `src/gracekelly/core/`, each with test file.

### Task 2.1: Account Loader (`account_loader.py`)
**Files:** Create `src/gracekelly/core/account_loader.py`, `tests/test_account_loader.py`

Load API accounts from JSON string.
- `AccountCredential(provider, account_id, api_key)`
- `load_accounts(json_string: str) -> list[AccountCredential]`
- `load_accounts_from_env(env_var: str = "GRACEKELLY_ACCOUNTS") -> list[AccountCredential]`
- Format: `[{"provider": "mistral", "account_id": "acct1", "api_key": "sk-..."}]`
- Tests: valid JSON, empty, malformed, missing fields, env var loading

### Task 2.2: Account Pool Manager (`account_pool_manager.py`)
**Files:** Create `src/gracekelly/core/account_pool_manager.py`, `tests/test_account_pool_manager.py`

Acquire → execute → release wrapper around AccountPool.
- `PooledExecutionResult(account_id, response, success)`
- `AccountPoolManager(pool, cooldown_seconds=60)`
- `.execute_with_account(provider, execute_fn, prompt) -> PooledExecutionResult`
- `.available_count(provider) -> int`
- Uses existing `AccountPool` from `core/account_pool.py`
- Tests: successful execution releases account, failed execution triggers cooldown, no accounts available

### Task 2.3: Execution History (`execution_history.py`)
**Files:** Create `src/gracekelly/core/execution_history.py`, `tests/test_execution_history.py`

In-memory execution history tracker.
- `ExecutionRecord(model_id, task_type, status, duration_ms, timestamp)`
- `ExecutionHistory` — thread-safe, with `.record()`, `.list_recent(limit)`, `.list_by_model()`, `.success_rate()`, `.avg_duration_ms()`, `.clear()`
- Tests: record + retrieve, filtering, success rate calculation, thread safety, empty history

### Task 2.4: Round Weighting (`round_weighting.py`)
**Files:** Create `src/gracekelly/core/round_weighting.py`, `tests/test_round_weighting.py`

Exponential decay weighting for consensus rounds.
- `WeightedScore(raw_score, weighted_score, total_weight, round_weights)`
- `round_weight(round_number, decay_base=0.8) -> float` — weight = decay_base ^ round_number
- `weighted_cluster_size(cluster_indices, response_rounds, decay_base) -> float`
- `consensus_score_weighted(top_cluster, all_indices, response_rounds, decay_base) -> WeightedScore`
- Tests: later rounds weigh less, decay_base=1.0 → equal weights, single round

### Task 2.5: Multi-Model Executor (`multi_model.py`)
**Files:** Create `src/gracekelly/core/multi_model.py`, `tests/test_multi_model.py`

Round-robin execution across multiple providers.
- `MultiModelExecutor(adapters: dict[str, adapter], model_specs: list[ModelSpec])`
- `.execute_all(prompt, plan, reasoning) -> list[str]` — returns responses from all models
- `.execute_round_robin(prompt, plan, reasoning, count) -> list[str]` — distribute count requests across models
- Tests: single model, multiple models, failed model skipped, empty adapters

### Task 2.6: Peer Review Reranker (`peer_review_reranker.py`)
**Files:** Create `src/gracekelly/core/peer_review_reranker.py`, `tests/test_peer_review_reranker.py`

LLM Council-inspired Borda count reranking.
- `PeerRanking(response_index, score, rank)`
- `build_review_prompt(original_prompt, responses: list[str]) -> str` — anonymized review prompt
- `parse_rankings(review_output: str, num_responses: int) -> list[int]` — extract ranking from LLM output
- `rerank_cluster(responses, rankings_list: list[list[int]]) -> list[PeerRanking]` — Borda count
- Tests: clear winner, tie handling, single response, malformed ranking fallback

---

## Workstream 3: Endpoints + Wiring (Agent 3)

4 new route files + tests + main.py wiring.

### Task 3.1: Batch Route (`api/routes/batch.py`)
**Files:** Create `src/gracekelly/api/routes/batch.py`, `tests/test_batch_route.py`

POST /api/v1/batch — execute multiple prompts.
- `BatchRequest(prompts: list[str], model: str = "mistral-small")`
- `BatchItemResponse(prompt, answer, status)`
- `BatchResponse(results: list[BatchItemResponse], total, succeeded, failed)`
- Tests: single prompt, multiple prompts, invalid model

### Task 3.2: Pipeline Route (`api/routes/pipeline.py`)
**Files:** Create `src/gracekelly/api/routes/pipeline.py`, `tests/test_pipeline_route.py`

POST /api/v1/pipeline — classify → resolve → execute → return with metadata.
- `PipelineRequest(prompt, model, reliability_level)`
- `PipelineResponse(answer, task_type, pattern_used, reliability_level, total_llm_calls, model_id)`
- Similar to smart.py but pipeline-focused (no decomposition/roles for simplicity)
- Tests: basic execution, task type detection, reliability level override

### Task 3.3: Health Detailed (`api/routes/health_detailed.py`)
**Files:** Create `src/gracekelly/api/routes/health_detailed.py`, `tests/test_health_detailed.py`

GET /api/v1/health/detailed — adapter status, embeddings status, uptime.
- `AdapterStatus(name, status)`
- `EmbeddingsStatus(status, cache_size)`
- `DetailedHealthResponse(status, uptime_seconds, adapters, embeddings, total_adapters)`
- Tests: all adapters with keys → healthy, no keys → degraded, no embeddings

### Task 3.4: Smart V2 Route (`api/routes/smart_v2.py`)
**Files:** Create `src/gracekelly/api/routes/smart_v2.py`, `tests/test_smart_v2_route.py`

POST /api/v1/smart/v2 — smart with consensus details.
- Extends SmartResponse with: consensus_status, consensus_score, cluster_confidence, dissenting_views
- Uses existing ConsensusExecutor (not V2 — V2 integration comes after merge)
- Tests: basic 200, v2 fields present, consensus fields populated on high reliability

### Task 3.5: Wire All Routes
**Files:** Modify `src/gracekelly/main.py`

Add imports + include_router for: batch, pipeline, health_detailed, smart_v2.
Move Codex tasks 150-170 to done/. Update Codex README.

---

## Post-Merge: Integration

After all 3 workstreams complete:
1. Upgrade smart_v2.py to use ConsensusExecutorV2
2. Run full test suite
3. Commit everything
