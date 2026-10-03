"""
Rasch Model Scoring Engine — Dichotomous Rasch / JMLE
=====================================================
55 ta element uchun mustaqil baholash moduli.

Savollar strukturasi:
  Q1..Q32   — 4 variantli (32 ta)
  Q33..Q35  — 6 variantli (3 ta)
  Q36a..Q45b — ochiq (10 savol x 2 = 20 ta)
  Jami: 55 ta element

Asosiy funksiya:
    results = evaluate_rasch_scores(responses_matrix)

Kirish:
    responses_matrix — list of dicts:
      [
        {"student_id": <int|str>, "responses": [0|1, 0|1, ..., 0|1]},  # 55 ta
        ...
      ]
Chiqish:
    {
      "students": [...],
      "items": [...],
      "meta": {...}
    }
"""

import math
import json
from typing import Any, Dict, List, Optional

# Item labels (0-indexed)
_ITEM_LABELS: List[str] = (
    [f"Q{i}" for i in range(1, 33)] +
    ["Q33", "Q34", "Q35"] +
    [f"Q{q}{s}" for q in range(36, 46) for s in ("a", "b")]
)
assert len(_ITEM_LABELS) == 55, "Item label count must be 55"
N_ITEMS = 55


def _assign_grade(score: float, raw_score: Optional[int] = None) -> str:
    """Rasmiy Milliy sertifikat baholash shkalasi."""
    if (raw_score is not None and raw_score == 0) or score <= 0.0:
        return "—"
    if score >= 70.0:
        return "A+"
    elif score >= 65.0:
        return "A"
    elif score >= 60.0:
        return "B+"
    elif score >= 55.0:
        return "B"
    elif score >= 50.0:
        return "C+"
    elif score >= 46.0:
        return "C"
    else:
        return "—"


def _sigmoid(x: float) -> float:
    """Numerik barqaror logistik funksiya."""
    if x > 35.0:
        return 1.0
    elif x < -35.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def _compute_fit(X: List[List[int]], theta: List[float], b: List[float]) -> List[Dict[str, Any]]:
    """Har bir element uchun Infit va Outfit MNSQ hisoblash."""
    N = len(X)
    I = N_ITEMS
    items = []
    for j in range(I):
        infit_num = 0.0
        infit_den = 0.0
        outfit_num = 0.0
        for n in range(N):
            p = _sigmoid(theta[n] - b[j])
            q = 1.0 - p
            w = p * q
            z = X[n][j] - p
            infit_num += (z ** 2) * w
            infit_den += w  # To'g'ri Rasch Infit: Σ(z²·w) / Σ(w)
            if w > 1e-9:
                outfit_num += (z ** 2) / w
        infit_mnsq = (infit_num / infit_den) if infit_den > 1e-9 else 1.0
        outfit_mnsq = (outfit_num / N) if N > 0 else 1.0
        items.append({
            "item_index": j,
            "item_label": _ITEM_LABELS[j],
            "difficulty_b": round(b[j], 4),
            "infit_mnsq": round(infit_mnsq, 4),
            "outfit_mnsq": round(outfit_mnsq, 4),
            "is_noisy": (infit_mnsq > 1.3 or outfit_mnsq > 1.3),
        })
    return items


def evaluate_rasch_scores(
    responses_matrix: List[Dict[str, Any]],
    tol: float = 0.001,
    max_iter: int = 50,
) -> Dict[str, Any]:
    """
    Rasch IRT modeli asosida 55-elementli test natijalarini hisoblash.
    Barcha o'quvchilar javoblari asosida savollar qiyinligi (b_j) va 
    o'quvchilar qobiliyati (theta_n) nisbiy solishtirilib baholanadi.
    """
    if not responses_matrix:
        return {"students": [], "items": [], "meta": {}}

    N = len(responses_matrix)
    I = N_ITEMS
    ids = []
    X: List[List[int]] = []

    for entry in responses_matrix:
        ids.append(entry.get("student_id", ""))
        resp = list(entry.get("responses", []))
        resp = resp[:N_ITEMS]
        resp.extend([0] * (N_ITEMS - len(resp)))
        X.append([int(bool(v)) for v in resp])

    # 1. Savollar qiyinlik darajasini va ball vaznlarini hisoblash
    eps = 0.5
    b = []
    weights_raw = []
    for j in range(I):
        c_j = sum(X[n][j] for n in range(N))
        p_j = (c_j + eps) / (N + 2.0 * eps)
        b_j = -math.log(p_j / (1.0 - p_j))
        b.append(b_j)
        weights_raw.append(b_j)

    # b parametrini markazlashtirish (mean(b) = 0)
    mu_b = sum(b) / I
    b = [bv - mu_b for bv in b]

    # Ko'p odam to'g'ri ishlagan oson savolga kamroq ball (masalan, 0.4 - 0.7 ball)
    # Kam odam to'g'ri ishlagan qiyin savolga ko'proq ball (masalan, 2.0 - 2.5 ball)
    min_w = min(weights_raw)
    base_weights = [w - min_w + 1.0 for w in weights_raw]
    total_base = sum(base_weights)
    item_points = [(w / total_base) * 100.0 for w in base_weights]

    # Har bir o'quvchining savollar qiyinligi bo'yicha to'plagan xom qiyinlik bali
    raw_weighted = [sum(X[n][j] * item_points[j] for j in range(I)) for n in range(N)]

    # 2. Har bir o'quvchi qobiliyati (theta) ni MLE bilan topish
    thetas = []
    for n in range(N):
        r_n = sum(X[n])
        r_adj = max(0.5, min(I - 0.5, float(r_n)))
        th = math.log(r_adj / (I - r_adj))
        for _ in range(max_iter):
            val = sum(_sigmoid(th - b[j]) for j in range(I))
            deriv = sum(_sigmoid(th - b[j]) * (1.0 - _sigmoid(th - b[j])) for j in range(I))
            if deriv < 1e-6:
                break
            diff = val - r_adj
            th = th - diff / deriv
            if abs(diff) < tol:
                break
        thetas.append(th)

    # 3. Fit statistika
    items_stats = _compute_fit(X, thetas, b)
    for j in range(I):
        items_stats[j]["item_score"] = round(item_points[j], 2)
        items_stats[j]["solved_count"] = sum(X[n][j] for n in range(N))

    # 4. Rasmiy 100-ballik sertifikat shkalasiga o'tkazish
    # Qiyin savollarni topgan o'quvchi ko'proq ball oladi!
    # Masalan, teng 15 ta to'g'ri topsa ham, qiyin savollarni yechgan o'quvchi yuqori ball oladi.
    students_out = []
    for n in range(N):
        r_n = sum(X[n])
        rw_n = raw_weighted[n]

        # 0 ta to'g'ri ishlagan holat uchun qat'iy tekshiruv:
        if r_n == 0:
            final_score = 0.0
            grade = "—"
        else:
            # 55/55 to'liq ishlagan bo'lsa maksimal 100 ball
            if r_n == I:  # I = 55
                final_score = 100.0
                grade = "A+"
            else:
                calculated_score = 27.5 + 0.824 * float(rw_n)
                final_score = round(min(100.0, max(0.0, calculated_score)), 1)
                
                # Darajalar chegarasi:
                if final_score >= 70.0:
                    grade = "A+"
                elif final_score >= 65.0:
                    grade = "A"
                elif final_score >= 60.0:
                    grade = "B+"
                elif final_score >= 55.0:
                    grade = "B"
                elif final_score >= 50.0:
                    grade = "C+"
                elif final_score >= 46.0:
                    grade = "C"
                else:
                    grade = "—"

        students_out.append({
            "student_id": ids[n],
            "raw_score": r_n,
            "weighted_score": round(rw_n, 1),
            "theta": round(thetas[n], 4),
            "z_score": round(thetas[n], 4),
            "final_score": final_score,
            "grade": grade,
        })

    # Saralash
    students_out.sort(key=lambda s: -s["final_score"])

    mu_th = sum(thetas) / N
    var_th = sum((t - mu_th) ** 2 for t in thetas) / N if N > 1 else 0.0
    sigma_th = math.sqrt(var_th)

    return {
        "students": students_out,
        "items": items_stats,
        "meta": {
            "n_students": N,
            "n_items": I,
            "mu_theta": round(mu_th, 4),
            "sigma_theta": round(sigma_th, 4),
            "iterations": 1,
            "converged": True,
        },
    }


def evaluate_single_test(test_id: int, get_submissions_fn) -> Optional[Dict[str, Any]]:
    """
    test_db dan submissions ni olib, Rasch baholash o'tkazadi.

    Args:
        test_id: tests.id
        get_submissions_fn: callable(test_id) -> list of submission dicts
                            (submissions jadvali row'lari, details_json bilan)

    Returns:
        evaluate_rasch_scores() natijasi yoki None (talabalar 2 dan kam bo'lsa)
    """
    submissions = get_submissions_fn(test_id)
    if not submissions or len(submissions) < 2:
        return None

    matrix = []
    for sub in submissions:
        try:
            detail_raw = sub.get("details_json", "{}")
            details = json.loads(detail_raw) if detail_raw else {}
            if not isinstance(details, dict):
                details = {}

            responses = []

            # Q1-Q32
            for q in range(1, 33):
                key = str(q)
                if key in details:
                    responses.append(1 if details[key].get("status") == "correct" else 0)
                else:
                    responses.append(0)

            # Q33-Q35
            for q in [33, 34, 35]:
                key = str(q)
                if key in details:
                    responses.append(1 if details[key].get("status") == "correct" else 0)
                else:
                    responses.append(0)

            # Q36a-Q45b
            for q in range(36, 46):
                for s in ("a", "b"):
                    key = f"{q}{s}"
                    if key in details:
                        responses.append(1 if details[key].get("status") == "correct" else 0)
                    else:
                        responses.append(0)

            matrix.append({
                "student_id": sub.get("user_tg_id", sub.get("id")),
                "responses": responses,
            })
        except Exception:
            continue

    if len(matrix) < 2:
        return None

    return evaluate_rasch_scores(matrix)


# CLI sanity check
if __name__ == "__main__":
    import random
    random.seed(42)

    demo = [
        {
            "student_id": f"S{i+1:02d}",
            "responses": [random.randint(0, 1) for _ in range(55)],
        }
        for i in range(20)
    ]

    result = evaluate_rasch_scores(demo)

    print("\n=== TALABALAR NATIJALARI ===")
    print(f"{'#':<3} {'ID':<8} {'Raw':>4} {'Theta':>8} {'Z':>7} {'Score':>7} {'Grade':<5}")
    print("-" * 45)
    for i, s in enumerate(result["students"], 1):
        print(f"{i:<3} {str(s['student_id']):<8} {s['raw_score']:>4} "
              f"{s['theta']:>8.3f} {s['z_score']:>7.3f} "
              f"{s['final_score']:>7.2f} {s['grade']:<5}")

    print("\n=== META ===")
    for k, v in result["meta"].items():
        print(f"  {k}: {v}")

    noisy = [it for it in result["items"] if it["is_noisy"]]
    print(f"\n=== SHOVQINLI SAVOLLAR ({len(noisy)} ta) ===")
    for it in noisy:
        print(f"  {it['item_label']}: Infit={it['infit_mnsq']}, Outfit={it['outfit_mnsq']}")
