| **Kỹ năng JD (`jd_skill_id`)** | **Kỹ năng CV (`matched`)** | **Alignment** | **$w_j$** | **$s\_{jd}$ (Yêu cầu)** | **$s\_{cv}$ (Thực tế)** | **Tháng HQ** | **$c\_{\text{evidence}}$** | **Gap** | **Priority** | **Chiến lược (Module 3)** |
| :----------------------------- | :------------------------- | :------------ | :-------- | :---------------------- | :---------------------- | :----------- | :------------------------- | :------ | :----------- | :------------------------ |
| `html_css` | `None` | MISSING | 0.05 | 3 | **1.00** | 0.0m | 0 | 1 | **0.030** | `LEARNING_AGILITY` |

Ký hiệu thường: $s_{jd}$, $c_{\text{evidence}}$. Dấu gạch dưới nguyên văn: $\text{file}\_\text{name}$.

```sql
SELECT html_css, s\_{jd}, '$w_j$' FROM report;
```

Code nội tuyến: `s\_{jd}`.

$$
\mathrm{Gap} = \frac{s_{jd} - s_{cv}}{s_{jd}}
$$
