# Báo Cáo Thực Nghiệm Lại Mô-đun 1 — Kiến Trúc Tách Bạch (`v4 Semantic-Importance`)

Toàn bộ thực nghiệm chạy **100% local trên CPU** (`0` request OpenRouter/LLM API, chi phí `$0`, tổng thời gian `1066.82s`), sử dụng đúng tập dữ liệu và giao thức đã khóa (`80 train / 20 val / 112 locked test`, `5 seed cố định: 42, 102, 202, 302, 402`).

- Script tái lập: `run_m1_v4_experiment.py`
- Dữ liệu JSON đầy đủ: `results_summary.json`
- Kiểm toán trọng số JSI-v1 ($w_j$): `jsi_weights_audit.json`
- Đồ thị tái trọng số `v4`: `graphs/{train,val,test}_graphs_v4.pt`
- Checkpoints 5 seed × 4 cấu hình: `checkpoints/*.pt`

## 1. Bảng kết quả chính (Validation 20 cặp & Test độc lập 112 cặp / 14 JD)

| Nhóm | Cấu hình | Val MAE (20) | Test MAE ↓ (112) | Test NDCG@5 ↑ (112) | Test Spearman ↑ (112) | Asym With-Rel ↑ (30) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| Đối chứng | SBERT cosine | 21.18 | 29.66 | 0.6425 | 0.0357 | — |
| Đối chứng | SBERT + Ridge ($\alpha=1.0$) | 12.95 | 21.75 | 0.6514 | 0.0566 | — |
| Mới (`v4`) | GNN – Bipartite ($w_j$) | 10.09 ± 0.27 | 19.87 ± 1.36 | 0.8349 ± 0.0150 | 0.5347 ± 0.0380 | 42.0% (+0.0003) |
| Mới (`v4`) | GNN – Dependency ($w_j$, 1 chiều) | 10.22 ± 0.40 | 19.73 ± 1.04 | 0.8212 ± 0.0156 | 0.5184 ± 0.0467 | 34.0% (+0.0076) |
| Mới (`v4`) | **GNN – Full (`v4`, $w_j$ + bất đối xứng)** | **10.34 ± 0.55** | **20.40 ± 1.18** | **0.8275 ± 0.0052** | **0.5244 ± 0.0246** | **80.0% (+0.3289)** |
| Ablation (`v4`) | GNN – Full (không $w_j$, đồng nhất 1.0) | 10.69 ± 0.65 | 19.40 ± 1.74 | 0.8438 ± 0.0139 | 0.5504 ± 0.0238 | 60.0% (+0.3167) |
| Tham chiếu cũ | Old GNN v1 – Bipartite (proficiency) | 10.03 ± 0.37 | 20.13 ± 1.04 | 0.8124 ± 0.0280 | 0.5003 ± 0.0643 | 60.0% (+0.0004) |
| Tham chiếu cũ | Old GNN v2 – Dependency (proficiency) | 10.02 ± 0.21 | 18.85 ± 0.47 | 0.8269 ± 0.0154 | 0.5443 ± 0.0363 | 70.0% (+0.0279) |
| Tham chiếu cũ | Old GNN v3 – Full (proficiency) | 10.08 ± 0.49 | 19.64 ± 1.06 | 0.8223 ± 0.0158 | 0.5061 ± 0.0331 | 60.0% (+0.2723) |

## 2. Phân tích độ nhạy trên 82/112 cặp có đủ cạnh kỹ năng CV (`cv_edges > 0`)

| Cấu hình | Macro-MAE ↓ (82) | Macro-NDCG@5 ↑ (82) | Macro-Spearman ↑ (82) | Pooled RMSE ↓ (82) |
| :--- | :---: | :---: | :---: | :---: |
| SBERT cosine | 26.66 | 0.8535 | 0.3858 | 31.78 |
| SBERT + Ridge ($\alpha=1.0$) | 17.41 | 0.8585 | 0.3696 | 21.57 |
| GNN `v4` – Bipartite | 18.05 ± 1.00 | 0.9223 ± 0.0161 | 0.5390 ± 0.0636 | 24.08 ± 1.92 |
| GNN `v4` – Dependency | 17.97 ± 0.75 | 0.9155 ± 0.0215 | 0.5410 ± 0.0540 | 24.21 ± 1.49 |
| **GNN `v4` – Full** | 18.29 ± 0.81 | **0.9129 ± 0.0086** | **0.5366 ± 0.0360** | 24.55 ± 1.56 |
| GNN `v4` – Full (không $w_j$) | 17.45 ± 1.34 | 0.9259 ± 0.0224 | 0.6000 ± 0.0851 | 23.22 ± 2.33 |
| Old GNN v3 – Full | 17.46 ± 0.61 | 0.8985 ± 0.0138 | 0.5038 ± 0.0562 | — |

## 3. Bootstrap ghép cặp trên 14 cụm JD (`GNN v4 – Full` trừ đối chứng)

- vs `SBERT cosine`: $\Delta\text{MAE} = -9.26$ `[-15.63, -2.30]` (10/14), $\Delta\text{NDCG@5} = +0.1850$ `[+0.0533, +0.3299]` (10/14), $\Delta\text{Spearman} = +0.4886$ `[+0.1601, +0.8196]` (11/14).
- vs `SBERT + Ridge`: $\Delta\text{MAE} = -1.34$ `[-3.23, +0.67]` (10/14), $\Delta\text{NDCG@5} = +0.1762$ `[+0.0568, +0.3081]` (10/14), $\Delta\text{Spearman} = +0.4677$ `[+0.1658, +0.7754]` (10/14).
- vs `Old GNN v3 – Full`: $\Delta\text{MAE} = +0.76$ `[+0.03, +1.41]` (3/14), $\Delta\text{NDCG@5} = +0.0053$ `[-0.0204, +0.0359]` (9/14), $\Delta\text{Spearman} = +0.0183$ `[-0.0458, +0.0714]` (10/14).
