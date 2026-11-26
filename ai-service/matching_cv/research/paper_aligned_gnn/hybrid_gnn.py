"""Paper-Aligned Hybrid GNN Architecture (GraphConv + Equation 2 Modified GAT + Concatenated Document Readout).

Reference:
Baghbanzadeh, A., & Wu, D. (2025). Resume-Job Compatibility Scoring Using Graph Neural Networks
and Large Language Models. ICIT 2025.
- Section 3.5: Compatibility Scoring via Graph Neural Networks.
- Equation (2): Modified GAT attention mechanism incorporating scalar proficiency edge weight w_ij.
- Section 4.1: Two-layer hybrid GNN setup.
- Section 4.7 & Figure 6: Resume skill attention scores for explainability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.data import Batch, HeteroData
from torch_geometric.nn import GraphConv
from torch_geometric.utils import softmax as pyg_softmax

from matching_cv.research.paper_aligned_gnn.schemas import DecisionClassification

ScoreScaleType = Literal["0_1", "0_100"]


@dataclass
class PaperAlignedGNNConfig:
    """
    Configuration for the Paper-Aligned Hybrid GNN.
    Explicitly separates PAPER_EXPLICIT architectural specifications from
    IMPLEMENTATION_ASSUMPTION hyperparameters not stated in the 6-page paper.
    """

    # PAPER_EXPLICIT: 2 GNN layers (Section 4.1)
    num_layers: int = 2

    # PROJECT_ADAPTATION: 768D SBERT input embeddings (vs 1536D/3072D OpenAI in paper)
    input_dim: int = 768

    # IMPLEMENTATION_ASSUMPTION: Hidden dimensions, heads, slope, dropout
    hidden_dim: int = 128
    num_heads: int = 1  # 1 head directly matches Equation (2); >1 averages across heads
    leaky_relu_slope: float = 0.2
    dropout: float = 0.1

    # PAPER_EXPLICIT: Concatenated document readout [h_resume || h_job] -> 2 * hidden_dim
    # IMPLEMENTATION_ASSUMPTION: MLP hidden layer widths
    mlp_hidden_dims: List[int] = field(default_factory=lambda: [128, 64])
    mlp_dropout: float = 0.1

    # Edge weight handling
    use_job_edge_weights: bool = True
    missing_job_weight_for_graphconv: float = 1.0  # Prevents zeroing out JD skills with '-' proficiency
    use_resume_edge_weights: bool = True
    missing_resume_weight_for_gat: float = 0.0
    use_value_weight_modulation: bool = False  # True in v3: modulates GAT value message by w_ij so depth survives 1-neighbor/shift-invariant softmax
    add_self_loops_in_gat: bool = False  # Strictly bipartite neighborhood N(i) by default

    # Score scale support ('0_1' matches Table 5 MSE=0.0020; '0_100' matches HR 0-100 scale)
    score_scale: ScoreScaleType = "0_1"

    # PROJECT_ADAPTATION: Intra-Skill Prerequisite Dependency Message Passing
    # Default False preserves 100% state_dict compatibility with v1 bipartite checkpoints.
    use_skill_dependency_edges: bool = False
    use_reverse_skill_dependency_edges: bool = True
    skill_dependency_gate_init: float = 0.15
    skill_dependency_mode: Literal[
        "light_sbert_diffusion",
        "modified_gat",
        "asymmetric_sbert_diffusion",
    ] = "light_sbert_diffusion"

    def get_decision_audit(self) -> Dict[str, DecisionClassification]:
        audit: Dict[str, DecisionClassification] = {
            "num_layers_2": "PAPER_EXPLICIT",
            "job_skill_graphconv": "PAPER_EXPLICIT",
            "resume_skill_modified_gat_eq2": "PAPER_EXPLICIT",
            "concat_resume_job_readout": "PAPER_EXPLICIT",
            "mlp_regression_mse": "PAPER_EXPLICIT",
            "input_dim_768_sbert": "PROJECT_ADAPTATION",
            "hidden_dim_and_mlp_widths": "IMPLEMENTATION_ASSUMPTION",
            "bidirectional_bipartite_message_flow": "IMPLEMENTATION_ASSUMPTION",
            "missing_job_weight_for_graphconv_fallback": "IMPLEMENTATION_ASSUMPTION",
        }
        if self.use_skill_dependency_edges:
            audit["skill_prerequisite_dependency_gat"] = "PROJECT_ADAPTATION"
        return audit


class PaperModifiedGATConv(nn.Module):
    """
    Exact implementation of Equation (2) from Baghbanzadeh & Wu (2025), Section 3.5:

        alpha_{ij} = exp(LeakyReLU(a^T [W h_i || W h_j || w_{ij}]))
                     / sum_{k in N(i)} exp(LeakyReLU(a^T [W h_i || W h_k || w_{ik}]))

    Where:
    - i is the target node receiving messages,
    - j in N(i) is a source neighbor connected to i with scalar proficiency weight w_{ij},
    - W is the linear feature transformation matrix,
    - a is the learnable attention vector of dimension (2 * head_dim + 1),
    - Updated representation for target node i:
          m_i = sum_{j in N(i)} alpha_{ij} (W h_j)
    """

    def __init__(
        self,
        in_channels: Union[int, Tuple[int, int]],
        out_channels: int,
        heads: int = 1,
        negative_slope: float = 0.2,
        dropout: float = 0.0,
        bias: bool = True,
        use_value_weight_modulation: bool = False,
    ) -> None:
        super().__init__()
        if isinstance(in_channels, int):
            self.in_channels_src = in_channels
            self.in_channels_dst = in_channels
        else:
            self.in_channels_src, self.in_channels_dst = in_channels

        self.out_channels = out_channels
        self.heads = heads
        self.negative_slope = negative_slope
        self.dropout = dropout
        self.use_value_weight_modulation = use_value_weight_modulation

        # Linear projection W: shared when src and dst dimensions match (exact Eq. 2),
        # or bipartite-aligned when dimensions differ.
        if self.in_channels_src == self.in_channels_dst:
            self.lin = nn.Linear(self.in_channels_src, heads * out_channels, bias=False)
            self.lin_src = self.lin
            self.lin_dst = self.lin
        else:
            self.lin = None
            self.lin_src = nn.Linear(self.in_channels_src, heads * out_channels, bias=False)
            self.lin_dst = nn.Linear(self.in_channels_dst, heads * out_channels, bias=False)

        # Attention parameter vector a in R^{heads x (2 * out_channels + 1)}
        # Partitioned explicitly into [a_dst (out_channels) || a_src (out_channels) || a_edge (1)]
        self.att = nn.Parameter(torch.empty(heads, 2 * out_channels + 1))

        # Optional proficiency-modulated value pathway (PROJECT_ADAPTATION v3):
        # Prevents scalar proficiency w_ij from cancelling out under 1-neighbor or shift-invariant softmax.
        if use_value_weight_modulation:
            self.val_weight_scale: Optional[nn.Parameter] = nn.Parameter(torch.tensor(0.5, dtype=torch.float32))
            self.val_weight_vec: Optional[nn.Parameter] = nn.Parameter(torch.empty(heads, out_channels))
        else:
            self.register_parameter("val_weight_scale", None)
            self.register_parameter("val_weight_vec", None)

        if bias:
            self.bias = nn.Parameter(torch.zeros(out_channels))
        else:
            self.register_parameter("bias", None)

        self.reset_parameters()

    def reset_parameters(self) -> None:
        if self.lin is not None:
            nn.init.xavier_uniform_(self.lin.weight)
        else:
            nn.init.xavier_uniform_(self.lin_src.weight)
            nn.init.xavier_uniform_(self.lin_dst.weight)
        nn.init.xavier_uniform_(self.att)
        if self.val_weight_scale is not None:
            nn.init.constant_(self.val_weight_scale, 0.5)
        if self.val_weight_vec is not None:
            nn.init.normal_(self.val_weight_vec, mean=0.0, std=0.05)
        if self.bias is not None:
            nn.init.zeros_(self.bias)

    def forward(
        self,
        x: Union[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]],
        edge_index: torch.Tensor,
        edge_weight: Optional[torch.Tensor] = None,
        return_attention_weights: bool = False,
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]]:
        """
        Compute Equation (2) attention and message aggregation over directed edges (src j -> dst i).
        Note on indexing convention:
        - In PyG, `edge_index[0]` is source node `j` (neighbor sending message) and
          `edge_index[1]` is target node `i` (node receiving message, over whose neighborhood N(i)
          the softmax normalization is computed).
        - In Equation (2), `[W h_i || W h_j || w_{ij}]` puts target `h_i` first, neighbor `h_j` second,
          and scalar weight `w_{ij}` third.
        """
        if isinstance(x, torch.Tensor):
            x_src = x
            x_dst = x
        else:
            x_src, x_dst = x

        num_src = x_src.size(0)
        num_dst = x_dst.size(0)
        device = x_dst.device
        dtype = x_dst.dtype

        if num_dst == 0:
            empty_out = torch.empty((0, self.out_channels), dtype=dtype, device=device)
            if return_attention_weights:
                return empty_out, (edge_index, torch.empty((0, self.heads), dtype=dtype, device=device))
            return empty_out

        if edge_index.numel() == 0 or num_src == 0:
            zero_out = torch.zeros((num_dst, self.out_channels), dtype=dtype, device=device)
            if self.bias is not None:
                zero_out = zero_out + self.bias
            if return_attention_weights:
                return zero_out, (edge_index, torch.empty((0, self.heads), dtype=dtype, device=device))
            return zero_out

        # Project node features: W h_j (src) and W h_i (dst)
        # Shape: [N, heads, out_channels]
        wh_src = self.lin_src(x_src).view(num_src, self.heads, self.out_channels)
        wh_dst = self.lin_dst(x_dst).view(num_dst, self.heads, self.out_channels)

        src_idx = edge_index[0]  # j in N(i)
        dst_idx = edge_index[1]  # i (target node)
        num_edges = edge_index.size(1)

        wh_j = wh_src[src_idx]  # [E, heads, out_channels]
        wh_i = wh_dst[dst_idx]  # [E, heads, out_channels]

        # Prepare scalar edge weight w_{ij} of shape [E, heads, 1]
        if edge_weight is None:
            w_ij = torch.zeros((num_edges, self.heads, 1), dtype=dtype, device=device)
        else:
            w_flat = edge_weight.view(-1, 1).to(dtype=dtype, device=device)
            if w_flat.size(0) != num_edges:
                raise ValueError(
                    f"edge_weight length ({w_flat.size(0)}) does not match num_edges ({num_edges})"
                )
            w_ij = w_flat.unsqueeze(1).expand(num_edges, self.heads, 1)

        # Concatenate [W h_i || W h_j || w_{ij}] -> shape [E, heads, 2 * out_channels + 1]
        cat_input = torch.cat([wh_i, wh_j, w_ij], dim=-1)

        # Compute dot product a^T [W h_i || W h_j || w_{ij}] -> shape [E, heads]
        raw_logits = (cat_input * self.att.unsqueeze(0)).sum(dim=-1)

        # Apply LeakyReLU as in Equation (2)
        e_ij = F.leaky_relu(raw_logits, negative_slope=self.negative_slope)

        # Normalize over k in N(i) (grouped by target index dst_idx = i)
        alpha = pyg_softmax(e_ij, index=dst_idx, num_nodes=num_dst)

        if self.training and self.dropout > 0.0:
            alpha_dropped = F.dropout(alpha, p=self.dropout, training=True)
        else:
            alpha_dropped = alpha

        # Weighted message m_{ij} = alpha_{ij} * value_msg -> shape [E, heads, out_channels]
        if (
            self.use_value_weight_modulation
            and self.val_weight_scale is not None
            and self.val_weight_vec is not None
        ):
            # Center around 0.55 (average real-CV weight) and smoothly bound both multiplicative
            # and additive modulation so proficiency shifts scores realistically (~0.15-0.25 span)
            # without distorting global regression calibration on average-proficiency CVs.
            centered_w = w_ij - 0.55  # [E, heads, 1]
            prof_scale = 1.0 + 0.30 * torch.tanh(self.val_weight_scale) * centered_w
            bounded_vec = 0.20 * torch.tanh(self.val_weight_vec).unsqueeze(0)
            val_msg = prof_scale * wh_j + centered_w * bounded_vec
            messages = alpha_dropped.unsqueeze(-1) * val_msg
        else:
            messages = alpha_dropped.unsqueeze(-1) * wh_j

        # Aggregate over j in N(i) into target node i
        out = torch.zeros((num_dst, self.heads, self.out_channels), dtype=dtype, device=device)
        out.index_add_(0, dst_idx, messages)

        # Average over heads (for heads=1, this is a no-op squeeze)
        out_mean = out.mean(dim=1)  # [num_dst, out_channels]

        if self.bias is not None:
            out_mean = out_mean + self.bias

        if return_attention_weights:
            return out_mean, (edge_index, alpha)
        return out_mean


class PaperBipartiteHybridLayer(nn.Module):
    """
    A single hybrid GNN layer for the Resume-Job-Skill bipartite graph (Section 3.5 & 4.1):
    - Job <-> Skill connections: updated via GraphConv.
    - Resume <-> Skill connections: updated via PaperModifiedGATConv (Equation 2).
    """

    def __init__(self, in_dim: int, out_dim: int, config: PaperAlignedGNNConfig) -> None:
        super().__init__()
        self.config = config
        self.in_dim = in_dim
        self.out_dim = out_dim

        # 1. Job <-> Skill GraphConv operators (Section 3.5 bullet 1)
        # Step 1 (Document -> Skill): in_dim -> out_dim
        self.job_to_skill_conv = GraphConv((in_dim, in_dim), out_dim, aggr="add")
        # Step 2 (Updated Skill -> Document): (out_dim, in_dim) -> out_dim
        self.skill_to_job_conv = GraphConv((out_dim, in_dim), out_dim, aggr="add")

        # 2. Resume <-> Skill Modified GAT operators (Section 3.5 bullet 2 & Equation 2)
        # Step 1 (Document -> Skill): (in_dim, in_dim) -> out_dim
        self.resume_to_skill_gat = PaperModifiedGATConv(
            in_channels=(in_dim, in_dim),
            out_channels=out_dim,
            heads=config.num_heads,
            negative_slope=config.leaky_relu_slope,
            dropout=config.dropout,
            use_value_weight_modulation=config.use_value_weight_modulation,
        )
        # Step 2 (Updated Skill -> Document): (out_dim, in_dim) -> out_dim
        self.skill_to_resume_gat = PaperModifiedGATConv(
            in_channels=(out_dim, in_dim),
            out_channels=out_dim,
            heads=config.num_heads,
            negative_slope=config.leaky_relu_slope,
            dropout=config.dropout,
            use_value_weight_modulation=config.use_value_weight_modulation,
        )

        # Residual self-projections when in_dim != out_dim
        self.res_proj_resume = nn.Linear(in_dim, out_dim) if in_dim != out_dim else nn.Identity()
        self.res_proj_job = nn.Linear(in_dim, out_dim) if in_dim != out_dim else nn.Identity()
        self.res_proj_skill = nn.Linear(in_dim, out_dim) if in_dim != out_dim else nn.Identity()

        self.norm_resume = nn.LayerNorm(out_dim)
        self.norm_job = nn.LayerNorm(out_dim)
        self.norm_skill = nn.LayerNorm(out_dim)
        self.act = nn.LeakyReLU(negative_slope=config.leaky_relu_slope)
        self.drop = nn.Dropout(config.dropout)

        # 3. Optional Intra-Skill Prerequisite Dependency Message Passing (PROJECT_ADAPTATION)
        # Supports three modes:
        # - 'light_sbert_diffusion': Parameter-efficient SBERT-cosine weighted DAG diffusion (v2).
        # - 'asymmetric_sbert_diffusion' (v3): Dedicated forward (prerequisite_to: foundation -> advanced)
        #   and reverse (prerequisite_of: advanced -> foundation) gates + directional relation bias
        #   vectors so the GNN cleanly distinguishes CV=Kubernetes/JD=Docker from CV=Docker/JD=Kubernetes.
        # - 'modified_gat': Full Equation (2) Modified GAT on skill prerequisite edges.
        self.dep_fwd_bias: Optional[nn.Parameter] = None
        self.dep_rev_bias: Optional[nn.Parameter] = None
        if config.use_skill_dependency_edges:
            if config.skill_dependency_mode == "modified_gat":
                self.skill_prereq_gat: Optional[PaperModifiedGATConv] = PaperModifiedGATConv(
                    in_channels=out_dim,
                    out_channels=out_dim,
                    heads=config.num_heads,
                    negative_slope=config.leaky_relu_slope,
                    dropout=config.dropout,
                    bias=False,
                )
                if config.use_reverse_skill_dependency_edges:
                    self.skill_prereq_rev_gat: Optional[PaperModifiedGATConv] = PaperModifiedGATConv(
                        in_channels=out_dim,
                        out_channels=out_dim,
                        heads=config.num_heads,
                        negative_slope=config.leaky_relu_slope,
                        dropout=config.dropout,
                        bias=False,
                    )
                else:
                    self.skill_prereq_rev_gat = None
                self.norm_skill_dep: Optional[nn.LayerNorm] = nn.LayerNorm(out_dim)
                self.dep_rev_gate: Optional[nn.Parameter] = None
            elif config.skill_dependency_mode == "asymmetric_sbert_diffusion":
                self.skill_prereq_gat = None
                self.skill_prereq_rev_gat = None
                self.norm_skill_dep = None
                self.dep_rev_gate = (
                    nn.Parameter(torch.tensor(float(config.skill_dependency_gate_init) + 0.6, dtype=torch.float32))
                    if config.use_reverse_skill_dependency_edges
                    else None
                )
                # Forward prerequisite_to uses gentle non-penalizing convex diffusion only;
                # Reverse prerequisite_of adds a bounded superseding credit vector.
                if config.use_reverse_skill_dependency_edges:
                    self.dep_rev_bias = nn.Parameter(torch.zeros(out_dim, dtype=torch.float32))
            else:
                self.skill_prereq_gat = None
                self.skill_prereq_rev_gat = None
                self.norm_skill_dep = None
                self.dep_rev_gate = (
                    nn.Parameter(torch.tensor(float(config.skill_dependency_gate_init) * 0.5, dtype=torch.float32))
                    if config.use_reverse_skill_dependency_edges
                    else None
                )
            self.dep_gate: Optional[nn.Parameter] = nn.Parameter(
                torch.tensor(float(config.skill_dependency_gate_init), dtype=torch.float32)
            )
        else:
            self.skill_prereq_gat = None
            self.skill_prereq_rev_gat = None
            self.dep_gate = None
            self.dep_rev_gate = None
            self.norm_skill_dep = None

    def _prepare_job_edge_weights(
        self,
        edge_attr: Optional[torch.Tensor],
        has_prof: Optional[torch.Tensor],
        num_edges: int,
        device: torch.device,
        dtype: torch.dtype,
    ) -> Optional[torch.Tensor]:
        if not self.config.use_job_edge_weights or num_edges == 0:
            return None
        if edge_attr is None or edge_attr.numel() == 0:
            return torch.full((num_edges,), self.config.missing_job_weight_for_graphconv, dtype=dtype, device=device)

        w = edge_attr.view(-1).clone().to(dtype=dtype, device=device)
        if has_prof is not None and has_prof.numel() == num_edges:
            missing_mask = ~has_prof.view(-1).to(device=device)
            w[missing_mask] = float(self.config.missing_job_weight_for_graphconv)
        return w

    def _prepare_resume_edge_weights(
        self,
        edge_attr: Optional[torch.Tensor],
        has_prof: Optional[torch.Tensor],
        num_edges: int,
        device: torch.device,
        dtype: torch.dtype,
    ) -> Optional[torch.Tensor]:
        if not self.config.use_resume_edge_weights or num_edges == 0:
            return torch.zeros((num_edges,), dtype=dtype, device=device)
        if edge_attr is None or edge_attr.numel() == 0:
            return torch.full((num_edges,), self.config.missing_resume_weight_for_gat, dtype=dtype, device=device)

        w = edge_attr.view(-1).clone().to(dtype=dtype, device=device)
        if has_prof is not None and has_prof.numel() == num_edges:
            missing_mask = ~has_prof.view(-1).to(device=device)
            w[missing_mask] = float(self.config.missing_resume_weight_for_gat)
        return w

    def forward(
        self,
        h_resume: torch.Tensor,
        h_job: torch.Tensor,
        h_skill: torch.Tensor,
        graph: HeteroData,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Dict[str, Any]]:
        """
        Execute one bipartite hybrid message-passing layer:
        1. Job -> Skill (GraphConv) and Resume -> Skill (Modified GAT Eq. 2) update skill nodes.
        2. Skill -> Job (GraphConv) updates job node.
        3. Skill -> Resume (Modified GAT Eq. 2) updates resume node and yields resume skill attention scores.
        """
        device = h_resume.device
        dtype = h_resume.dtype
        num_skills = h_skill.size(0)

        # Base residuals
        base_resume = self.res_proj_resume(h_resume)
        base_job = self.res_proj_job(h_job)
        base_skill = self.res_proj_skill(h_skill) if num_skills > 0 else torch.empty((0, self.out_dim), dtype=dtype, device=device)

        # Extract edge indices and attributes
        et_job_to_skill = ("job", "requires_skill", "skill")
        et_skill_to_job = ("skill", "required_by_job", "job")
        et_res_to_skill = ("resume", "has_skill", "skill")
        et_skill_to_res = ("skill", "in_resume", "resume")

        # --- 1. Update Skill Nodes from Job (GraphConv) and Resume (Modified GAT) ---
        skill_update = torch.zeros_like(base_skill)
        res_to_skill_alpha = torch.empty((0, self.config.num_heads), dtype=dtype, device=device)
        res_to_skill_ei = torch.empty((2, 0), dtype=torch.long, device=device)
        prereq_alpha = torch.empty((0, self.config.num_heads), dtype=dtype, device=device)
        prereq_ei = torch.empty((2, 0), dtype=torch.long, device=device)
        prereq_rev_alpha = torch.empty((0, self.config.num_heads), dtype=dtype, device=device)
        prereq_rev_ei = torch.empty((2, 0), dtype=torch.long, device=device)

        if num_skills > 0:
            if et_job_to_skill in graph.edge_types and graph[et_job_to_skill].edge_index.numel() > 0:
                ei_js = graph[et_job_to_skill].edge_index.to(device=device)
                ea_js = getattr(graph[et_job_to_skill], "edge_attr", None)
                hp_js = getattr(graph[et_job_to_skill], "edge_has_proficiency", None)
                w_js = self._prepare_job_edge_weights(ea_js, hp_js, ei_js.size(1), device, dtype)
                m_js = self.job_to_skill_conv((h_job, h_skill), ei_js, edge_weight=w_js)
                skill_update = skill_update + m_js

            if et_res_to_skill in graph.edge_types and graph[et_res_to_skill].edge_index.numel() > 0:
                ei_rs = graph[et_res_to_skill].edge_index.to(device=device)
                ea_rs = getattr(graph[et_res_to_skill], "edge_attr", None)
                hp_rs = getattr(graph[et_res_to_skill], "edge_has_proficiency", None)
                w_rs = self._prepare_resume_edge_weights(ea_rs, hp_rs, ei_rs.size(1), device, dtype)
                m_rs, (res_to_skill_ei, res_to_skill_alpha) = self.resume_to_skill_gat(
                    (h_resume, h_skill), ei_rs, edge_weight=w_rs, return_attention_weights=True
                )
                skill_update = skill_update + m_rs

            h_skill_pre = self.norm_skill(self.act(skill_update) + base_skill)

            # --- 1B. Intra-Skill Prerequisite Dependency Propagation (PROJECT_ADAPTATION) ---
            if self.config.use_skill_dependency_edges and self.dep_gate is not None:
                et_prereq_fwd = ("skill", "prerequisite_to", "skill")
                et_prereq_rev = ("skill", "prerequisite_of", "skill")

                if self.config.skill_dependency_mode == "modified_gat" and self.skill_prereq_gat is not None:
                    dep_msg = torch.zeros_like(h_skill_pre)
                    has_dep = False
                    if et_prereq_fwd in graph.edge_types and graph[et_prereq_fwd].edge_index.numel() > 0:
                        ei_pf = graph[et_prereq_fwd].edge_index.to(device=device)
                        ea_pf = getattr(graph[et_prereq_fwd], "edge_attr", None)
                        w_pf = (
                            ea_pf.view(-1).to(dtype=dtype, device=device)
                            if ea_pf is not None and ea_pf.numel() == ei_pf.size(1)
                            else torch.ones((ei_pf.size(1),), dtype=dtype, device=device)
                        )
                        m_pf, (prereq_ei, prereq_alpha) = self.skill_prereq_gat(
                            h_skill_pre, ei_pf, edge_weight=w_pf, return_attention_weights=True
                        )
                        dep_msg = dep_msg + m_pf
                        has_dep = True

                    if (
                        self.skill_prereq_rev_gat is not None
                        and et_prereq_rev in graph.edge_types
                        and graph[et_prereq_rev].edge_index.numel() > 0
                    ):
                        ei_pr = graph[et_prereq_rev].edge_index.to(device=device)
                        ea_pr = getattr(graph[et_prereq_rev], "edge_attr", None)
                        w_pr = (
                            ea_pr.view(-1).to(dtype=dtype, device=device)
                            if ea_pr is not None and ea_pr.numel() == ei_pr.size(1)
                            else torch.ones((ei_pr.size(1),), dtype=dtype, device=device)
                        )
                        m_pr = self.skill_prereq_rev_gat(h_skill_pre, ei_pr, edge_weight=w_pr)
                        dep_msg = dep_msg + m_pr
                        has_dep = True

                    if has_dep and self.norm_skill_dep is not None:
                        gate_scale = torch.tanh(self.dep_gate)
                        h_skill_next = self.drop(
                            self.norm_skill_dep(h_skill_pre + gate_scale * self.act(dep_msg))
                        )
                    else:
                        h_skill_next = self.drop(h_skill_pre)
                elif self.config.skill_dependency_mode == "asymmetric_sbert_diffusion":
                    # Asymmetric Directional Cross-Bridge SBERT-Weighted DAG Diffusion (v3):
                    # Activates strictly on CV-to-unmet-JD bridge edges (src in CV [mem != 1],
                    # dst is unmet JD [mem == 1]) when `membership_code` is available so dense
                    # intra-JD edges on GOOD_FIT candidates never leak penalty bias!
                    # - Forward bridge `prerequisite_to` (CV foundation u -> unmet JD advanced v,
                    #     e.g., CV=docker -> JD=kubernetes): gate lam_pf in (0, 0.5) + dep_fwd_bias.
                    # - Reverse bridge `prerequisite_of` (CV advanced v -> unmet JD foundation u,
                    #     e.g., CV=kubernetes -> JD=docker): gate lam_pr in (0, 0.65) + dep_rev_bias.
                    h_updated = h_skill_pre
                    mem_code = getattr(graph["skill"], "membership_code", None)
                    if mem_code is not None and mem_code.numel() == num_skills:
                        mem_code = mem_code.to(device=device)
                    else:
                        mem_code = None

                    if et_prereq_fwd in graph.edge_types and graph[et_prereq_fwd].edge_index.numel() > 0:
                        ei_pf_all = graph[et_prereq_fwd].edge_index.to(device=device)
                        ea_pf_all = getattr(graph[et_prereq_fwd], "edge_attr", None)
                        w_pf_all = (
                            ea_pf_all.view(-1).to(dtype=dtype, device=device).clamp(min=1e-4)
                            if ea_pf_all is not None and ea_pf_all.numel() == ei_pf_all.size(1)
                            else torch.ones((ei_pf_all.size(1),), dtype=dtype, device=device)
                        )
                        if mem_code is not None:
                            bridge_pf = (mem_code[ei_pf_all[0]] != 1) & (mem_code[ei_pf_all[1]] == 1)
                            ei_pf = ei_pf_all[:, bridge_pf]
                            w_pf = w_pf_all[bridge_pf]
                        else:
                            ei_pf = ei_pf_all
                            w_pf = w_pf_all

                        if ei_pf.numel() > 0:
                            dst_pf = ei_pf[1]
                            denom_pf = torch.zeros((num_skills,), dtype=dtype, device=device)
                            denom_pf.index_add_(0, dst_pf, w_pf)
                            has_in_pf = (denom_pf > 0).unsqueeze(-1)
                            alpha_pf = w_pf / denom_pf[dst_pf].clamp(min=1e-8)
                            prereq_ei = ei_pf
                            prereq_alpha = alpha_pf.unsqueeze(-1)
                            msg_pf = torch.zeros_like(h_skill_pre)
                            msg_pf.index_add_(0, dst_pf, alpha_pf.unsqueeze(-1) * h_skill_pre[ei_pf[0]])
                            # Gentle non-penalizing partial-credit diffusion in (0, 0.20)
                            lam_pf = 0.20 * torch.sigmoid(self.dep_gate)
                            blended_pf = (1.0 - lam_pf) * h_updated + lam_pf * msg_pf
                            h_updated = torch.where(has_in_pf, blended_pf, h_updated)

                    if (
                        self.dep_rev_gate is not None
                        and et_prereq_rev in graph.edge_types
                        and graph[et_prereq_rev].edge_index.numel() > 0
                    ):
                        ei_pr_all = graph[et_prereq_rev].edge_index.to(device=device)
                        ea_pr_all = getattr(graph[et_prereq_rev], "edge_attr", None)
                        w_pr_all = (
                            ea_pr_all.view(-1).to(dtype=dtype, device=device).clamp(min=1e-4)
                            if ea_pr_all is not None and ea_pr_all.numel() == ei_pr_all.size(1)
                            else torch.ones((ei_pr_all.size(1),), dtype=dtype, device=device)
                        )
                        if mem_code is not None:
                            bridge_pr = (mem_code[ei_pr_all[0]] != 1) & (mem_code[ei_pr_all[1]] == 1)
                            ei_pr = ei_pr_all[:, bridge_pr]
                            w_pr = w_pr_all[bridge_pr]
                        else:
                            ei_pr = ei_pr_all
                            w_pr = w_pr_all

                        if ei_pr.numel() > 0:
                            dst_pr = ei_pr[1]
                            denom_pr = torch.zeros((num_skills,), dtype=dtype, device=device)
                            denom_pr.index_add_(0, dst_pr, w_pr)
                            has_in_pr = (denom_pr > 0).unsqueeze(-1)
                            alpha_pr = w_pr / denom_pr[dst_pr].clamp(min=1e-8)
                            prereq_rev_ei = ei_pr
                            prereq_rev_alpha = alpha_pr.unsqueeze(-1)
                            msg_pr = torch.zeros_like(h_skill_pre)
                            msg_pr.index_add_(0, dst_pr, alpha_pr.unsqueeze(-1) * h_skill_pre[ei_pr[0]])
                            if self.dep_rev_bias is not None:
                                msg_pr = msg_pr + (0.50 * torch.tanh(self.dep_rev_bias)).unsqueeze(0)
                            lam_pr = 0.65 * torch.sigmoid(self.dep_rev_gate)
                            blended_pr = (1.0 - lam_pr) * h_updated + lam_pr * msg_pr
                            h_updated = torch.where(has_in_pr, blended_pr, h_updated)

                    h_skill_next = self.drop(h_updated)
                else:
                    # Norm-preserving Convex SBERT-Weighted DAG Diffusion (APPNP-style):
                    # For nodes with incoming prerequisite edges:
                    #   h_v' = (1 - lam) * h_v + lam * sum_{u -> v} alpha_{uv} * h_u
                    # where alpha_{uv} = w^{SBERT}_{uv} / sum_{k -> v} w^{SBERT}_{kv}
                    # and lam = 0.5 * sigmoid(dep_gate) in (0, 0.5).
                    # Preserves exact feature scale across JDs regardless of prerequisite density.
                    h_updated = h_skill_pre
                    if et_prereq_fwd in graph.edge_types and graph[et_prereq_fwd].edge_index.numel() > 0:
                        ei_pf = graph[et_prereq_fwd].edge_index.to(device=device)
                        ea_pf = getattr(graph[et_prereq_fwd], "edge_attr", None)
                        w_pf = (
                            ea_pf.view(-1).to(dtype=dtype, device=device).clamp(min=1e-4)
                            if ea_pf is not None and ea_pf.numel() == ei_pf.size(1)
                            else torch.ones((ei_pf.size(1),), dtype=dtype, device=device)
                        )
                        dst_pf = ei_pf[1]
                        denom_pf = torch.zeros((num_skills,), dtype=dtype, device=device)
                        denom_pf.index_add_(0, dst_pf, w_pf)
                        has_in_pf = (denom_pf > 0).unsqueeze(-1)
                        alpha_pf = w_pf / denom_pf[dst_pf].clamp(min=1e-8)
                        prereq_ei = ei_pf
                        prereq_alpha = alpha_pf.unsqueeze(-1)
                        msg_pf = torch.zeros_like(h_skill_pre)
                        msg_pf.index_add_(0, dst_pf, alpha_pf.unsqueeze(-1) * h_skill_pre[ei_pf[0]])
                        lam_pf = 0.5 * torch.sigmoid(self.dep_gate)
                        blended_pf = (1.0 - lam_pf) * h_updated + lam_pf * msg_pf
                        h_updated = torch.where(has_in_pf, blended_pf, h_updated)

                    if (
                        self.dep_rev_gate is not None
                        and et_prereq_rev in graph.edge_types
                        and graph[et_prereq_rev].edge_index.numel() > 0
                    ):
                        ei_pr = graph[et_prereq_rev].edge_index.to(device=device)
                        ea_pr = getattr(graph[et_prereq_rev], "edge_attr", None)
                        w_pr = (
                            ea_pr.view(-1).to(dtype=dtype, device=device).clamp(min=1e-4)
                            if ea_pr is not None and ea_pr.numel() == ei_pr.size(1)
                            else torch.ones((ei_pr.size(1),), dtype=dtype, device=device)
                        )
                        dst_pr = ei_pr[1]
                        denom_pr = torch.zeros((num_skills,), dtype=dtype, device=device)
                        denom_pr.index_add_(0, dst_pr, w_pr)
                        has_in_pr = (denom_pr > 0).unsqueeze(-1)
                        alpha_pr = w_pr / denom_pr[dst_pr].clamp(min=1e-8)
                        msg_pr = torch.zeros_like(h_skill_pre)
                        msg_pr.index_add_(0, dst_pr, alpha_pr.unsqueeze(-1) * h_skill_pre[ei_pr[0]])
                        lam_pr = 0.5 * torch.sigmoid(self.dep_rev_gate)
                        blended_pr = (1.0 - lam_pr) * h_updated + lam_pr * msg_pr
                        h_updated = torch.where(has_in_pr, blended_pr, h_updated)

                    h_skill_next = self.drop(h_updated)
            else:
                h_skill_next = self.drop(h_skill_pre)
        else:
            h_skill_next = base_skill

        # --- 2. Update Job Node from Updated Skills (GraphConv) ---
        if num_skills > 0 and et_skill_to_job in graph.edge_types and graph[et_skill_to_job].edge_index.numel() > 0:
            ei_sj = graph[et_skill_to_job].edge_index.to(device=device)
            ea_sj = getattr(graph[et_skill_to_job], "edge_attr", None)
            hp_sj = getattr(graph[et_skill_to_job], "edge_has_proficiency", None)
            w_sj = self._prepare_job_edge_weights(ea_sj, hp_sj, ei_sj.size(1), device, dtype)
            m_sj = self.skill_to_job_conv((h_skill_next, h_job), ei_sj, edge_weight=w_sj)
            h_job_next = self.drop(self.norm_job(self.act(m_sj) + base_job))
        else:
            h_job_next = self.norm_job(base_job)

        # --- 3. Update Resume Node from Updated Skills (Modified GAT Equation 2) ---
        skill_to_res_alpha = torch.empty((0, self.config.num_heads), dtype=dtype, device=device)
        skill_to_res_ei = torch.empty((2, 0), dtype=torch.long, device=device)

        if num_skills > 0 and et_skill_to_res in graph.edge_types and graph[et_skill_to_res].edge_index.numel() > 0:
            ei_sr = graph[et_skill_to_res].edge_index.to(device=device)
            ea_sr = getattr(graph[et_skill_to_res], "edge_attr", None)
            hp_sr = getattr(graph[et_skill_to_res], "edge_has_proficiency", None)
            w_sr = self._prepare_resume_edge_weights(ea_sr, hp_sr, ei_sr.size(1), device, dtype)
            m_sr, (skill_to_res_ei, skill_to_res_alpha) = self.skill_to_resume_gat(
                (h_skill_next, h_resume), ei_sr, edge_weight=w_sr, return_attention_weights=True
            )
            h_resume_next = self.drop(self.norm_resume(self.act(m_sr) + base_resume))
        else:
            h_resume_next = self.norm_resume(base_resume)

        layer_attn = {
            "skill_to_resume_edge_index": skill_to_res_ei,
            "skill_to_resume_alpha": skill_to_res_alpha,
            "resume_to_skill_edge_index": res_to_skill_ei,
            "resume_to_skill_alpha": res_to_skill_alpha,
            "skill_prerequisite_edge_index": prereq_ei,
            "skill_prerequisite_alpha": prereq_alpha,
            "skill_prerequisite_rev_edge_index": prereq_rev_ei,
            "skill_prerequisite_rev_alpha": prereq_rev_alpha,
        }
        return h_resume_next, h_job_next, h_skill_next, layer_attn


class PaperConcatenatedDocumentReadout(nn.Module):
    """
    Paper Section 3.5 Document Readout:
    "Final resume and job node embeddings are concatenated and passed through a
    Multi-Layer Perceptron (MLP) for regression."

        pair_repr = concat(resume_embedding, job_embedding)
    """

    def __init__(self, hidden_dim: int = 128) -> None:
        super().__init__()
        self.hidden_dim = hidden_dim
        self.output_dim = 2 * hidden_dim

    def forward(
        self, h_resume: torch.Tensor, h_job: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Args:
            h_resume: Tensor of shape [1, hidden_dim] or [B, hidden_dim]
            h_job: Tensor of shape [1, hidden_dim] or [B, hidden_dim]
        Returns:
            (resume_vec, job_vec, pair_repr) where pair_repr = concat(resume_vec, job_vec)
        """
        if h_resume.ndim == 2 and h_resume.size(0) == 1 and h_job.ndim == 2 and h_job.size(0) == 1:
            r_vec = h_resume.squeeze(0)
            j_vec = h_job.squeeze(0)
            pair_repr = torch.cat([r_vec, j_vec], dim=-1)
            return r_vec, j_vec, pair_repr

        pair_repr = torch.cat([h_resume, h_job], dim=-1)
        return h_resume, h_job, pair_repr


class PaperMLPRegressionHead(nn.Module):
    """
    MLP regression head mapping `pair_repr = concat(resume_embedding, job_embedding)`
    to a scalar compatibility score.
    """

    def __init__(self, in_dim: int, hidden_dims: List[int], dropout: float = 0.1) -> None:
        super().__init__()
        layers: List[nn.Module] = []
        curr = in_dim
        for h_dim in hidden_dims:
            layers.append(nn.Linear(curr, h_dim))
            layers.append(nn.LeakyReLU(0.2))
            layers.append(nn.Dropout(dropout))
            curr = h_dim
        layers.append(nn.Linear(curr, 1))
        self.mlp = nn.Sequential(*layers)

    def forward(self, pair_repr: torch.Tensor) -> torch.Tensor:
        if pair_repr.ndim == 1:
            return self.mlp(pair_repr.unsqueeze(0)).squeeze(0)
        return self.mlp(pair_repr)


class PaperAlignedHybridGNN(nn.Module):
    """
    Isolated Paper-Aligned Hybrid GNN (Baghbanzadeh & Wu, ICIT 2025).

    Architecture:
    - Input node embeddings: 'resume' [B, input_dim], 'job' [B, input_dim], 'skill' [N_skill, input_dim].
    - 2 Bipartite Hybrid Layers:
        - GraphConv on Job <-> Skill edges.
        - Modified GAT (Equation 2) on Resume <-> Skill edges with proficiency edge weights.
    - Readout:
        - `pair_repr = concat(resume_embedding, job_embedding)` ([2 * hidden_dim]).
    - MLP Regression Head:
        - Predicts compatibility score trained with MSE loss.
    """

    def __init__(self, config: Optional[PaperAlignedGNNConfig] = None) -> None:
        super().__init__()
        self.config = config or PaperAlignedGNNConfig()

        # Build L=2 hybrid layers (Layer 0: input_dim -> hidden_dim, Layer 1+: hidden_dim -> hidden_dim)
        self.layers = nn.ModuleList()
        for l_idx in range(self.config.num_layers):
            in_d = self.config.input_dim if l_idx == 0 else self.config.hidden_dim
            out_d = self.config.hidden_dim
            self.layers.append(PaperBipartiteHybridLayer(in_d, out_d, self.config))

        self.readout = PaperConcatenatedDocumentReadout(self.config.hidden_dim)
        self.head = PaperMLPRegressionHead(
            in_dim=self.readout.output_dim,
            hidden_dims=self.config.mlp_hidden_dims,
            dropout=self.config.mlp_dropout,
        )

    def forward(self, graph: HeteroData) -> Dict[str, Any]:
        """
        Execute forward pass on a Paper-Aligned HeteroData (or batched HeteroData) graph.
        Returns raw_score, bounded_score, scale metadata, document embeddings, and Figure 6
        skill attention scores.
        """
        if not isinstance(graph, HeteroData):
            raise TypeError(f"Expected PyG HeteroData, got {type(graph)}")

        h_resume = graph["resume"].x.to(dtype=torch.float32)
        h_job = graph["job"].x.to(dtype=torch.float32)
        if "skill" in graph.node_types and hasattr(graph["skill"], "x") and graph["skill"].x is not None:
            h_skill = graph["skill"].x.to(dtype=torch.float32)
        else:
            h_skill = torch.empty((0, self.config.input_dim), dtype=torch.float32, device=h_resume.device)

        layer_attentions: List[Dict[str, Any]] = []
        for layer in self.layers:
            h_resume, h_job, h_skill, attn_info = layer(h_resume, h_job, h_skill, graph)
            layer_attentions.append(attn_info)

        r_emb, j_emb, pair_repr = self.readout(h_resume, h_job)
        raw_score = self.head(pair_repr)

        # Bound score explicitly according to configured scale ('0_1' or '0_100')
        if self.config.score_scale == "0_100":
            bounded_score = torch.clamp(raw_score, min=0.0, max=100.0)
            scale_bounds = {"min": 0.0, "max": 100.0, "scale": "0_100"}
        else:
            bounded_score = torch.clamp(raw_score, min=0.0, max=1.0)
            scale_bounds = {"min": 0.0, "max": 1.0, "scale": "0_1"}

        # Extract final-layer resume skill attention weights (Figure 6 interpretability)
        final_attn = layer_attentions[-1] if layer_attentions else {}
        skill_to_res_alpha = final_attn.get("skill_to_resume_alpha")
        skill_to_res_ei = final_attn.get("skill_to_resume_edge_index")

        resume_skill_attention_map: Dict[str, float] = {}
        resume_skill_canonical_attention_map: Dict[str, float] = {}
        if (
            skill_to_res_alpha is not None
            and skill_to_res_ei is not None
            and skill_to_res_alpha.numel() > 0
            and hasattr(graph["skill"], "node_ids")
        ):
            skill_ids = graph["skill"].node_ids
            canonical_ids = getattr(graph["skill"], "canonical_ids", None)
            # Only build string dict for single-graph inference where skill_ids is a flat list of strings
            if isinstance(skill_ids, list) and (not skill_ids or isinstance(skill_ids[0], str)):
                alpha_mean = skill_to_res_alpha.mean(dim=-1).detach().cpu().tolist()
                src_indices = skill_to_res_ei[0].detach().cpu().tolist()
                for s_idx, a_val in zip(src_indices, alpha_mean):
                    if 0 <= s_idx < len(skill_ids):
                        resume_skill_attention_map[skill_ids[s_idx]] = round(float(a_val), 6)
                        if isinstance(canonical_ids, list) and s_idx < len(canonical_ids):
                            resume_skill_canonical_attention_map[canonical_ids[s_idx]] = round(float(a_val), 6)

        # Extract final-layer skill prerequisite dependency attention weights (explainability)
        prereq_alpha_final = final_attn.get("skill_prerequisite_alpha")
        prereq_ei_final = final_attn.get("skill_prerequisite_edge_index")
        skill_dependency_attention_map: Dict[str, float] = {}
        if (
            prereq_alpha_final is not None
            and prereq_ei_final is not None
            and prereq_alpha_final.numel() > 0
            and hasattr(graph["skill"], "node_ids")
        ):
            skill_ids = graph["skill"].node_ids
            canonical_ids = getattr(graph["skill"], "canonical_ids", None)
            if isinstance(skill_ids, list) and (not skill_ids or isinstance(skill_ids[0], str)):
                p_alpha_mean = prereq_alpha_final.mean(dim=-1).detach().cpu().tolist()
                p_src_idx = prereq_ei_final[0].detach().cpu().tolist()
                p_dst_idx = prereq_ei_final[1].detach().cpu().tolist()
                for s_i, d_i, a_v in zip(p_src_idx, p_dst_idx, p_alpha_mean):
                    if 0 <= s_i < len(skill_ids) and 0 <= d_i < len(skill_ids):
                        s_label = canonical_ids[s_i] if isinstance(canonical_ids, list) and s_i < len(canonical_ids) else skill_ids[s_i]
                        d_label = canonical_ids[d_i] if isinstance(canonical_ids, list) and d_i < len(canonical_ids) else skill_ids[d_i]
                        skill_dependency_attention_map[f"{s_label}->{d_label}"] = round(float(a_v), 6)

        return {
            "raw_score": raw_score,
            "bounded_score": bounded_score,
            "score_scale": self.config.score_scale,
            "scale_bounds": scale_bounds,
            "resume_embedding": r_emb,
            "job_embedding": j_emb,
            "pair_representation": pair_repr,
            "skill_embeddings": h_skill,
            "layer_attentions": layer_attentions,
            "resume_skill_attention_map": resume_skill_attention_map,
            "resume_skill_canonical_attention_map": resume_skill_canonical_attention_map,
            "skill_dependency_attention_map": skill_dependency_attention_map,
            "decision_audit": self.config.get_decision_audit(),
        }


def convert_score_scale(
    score: Union[float, torch.Tensor],
    from_scale: ScoreScaleType,
    to_scale: ScoreScaleType,
) -> Union[float, torch.Tensor]:
    """
    Explicitly convert compatibility scores between [0, 1] and [0, 100] without silent mixing.
    """
    if from_scale == to_scale:
        return score
    if from_scale == "0_1" and to_scale == "0_100":
        return score * 100.0
    if from_scale == "0_100" and to_scale == "0_1":
        return score / 100.0
    raise ValueError(f"Unsupported scale conversion: {from_scale} -> {to_scale}")


def compute_paper_tolerance_accuracy(
    predicted_scores: Union[List[float], torch.Tensor],
    target_scores: Union[List[float], torch.Tensor],
    scale: ScoreScaleType = "0_100",
    tolerance_points_on_100: float = 5.0,
) -> float:
    """
    Compute Equation (1) & Equation (3) from Baghbanzadeh & Wu (2025):
        Accuracy = (1 / N) * sum_{i=1}^N 1(|PG_i - TG_i| <= 5)  [on 0-100 scale]
    """
    pred_t = torch.as_tensor(predicted_scores, dtype=torch.float32).view(-1)
    targ_t = torch.as_tensor(target_scores, dtype=torch.float32).view(-1)
    if pred_t.numel() == 0:
        return 0.0
    if scale == "0_1":
        tol = tolerance_points_on_100 / 100.0
    else:
        tol = tolerance_points_on_100
    within = (torch.abs(pred_t - targ_t) <= tol + 1e-6).to(dtype=torch.float32)
    return float(within.mean().item())
