from pathlib import Path
import csv
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = ROOT / "results" / "v7_2_2" / "model_scores.csv"
OUTPUT_DIR = ROOT / "docs" / "images"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_results():
    rows = []

    with INPUT_FILE.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            rows.append(
                {
                    "model": row["model"],
                    "overall": float(row["overall"]),
                    "vram": float(row["peak_vram_gib"]),
                    "research": float(row["Research"]),
                    "coding": float(row["Coding"]),
                    "data": float(row["Data"]),
                    "writer": float(row["Writer"]),
                    "ppt": float(row["PPT"]),
                    "critic": float(row["Critic"]),
                }
            )

    return rows


def generate_overall_chart(rows):
    rows = sorted(rows, key=lambda x: x["overall"])

    models = [row["model"] for row in rows]
    scores = [row["overall"] for row in rows]

    fig, ax = plt.subplots(figsize=(12, 8))

    bars = ax.barh(models, scores)

    ax.set_title("Local LLM Benchmark v7.2.2 - Overall Score")
    ax.set_xlabel("Overall Score")
    ax.set_xlim(0, 100)

    for bar, score in zip(bars, scores):
        ax.text(
            score + 1,
            bar.get_y() + bar.get_height() / 2,
            f"{score:.2f}",
            va="center",
            fontsize=9,
        )

    fig.tight_layout()

    output = OUTPUT_DIR / "overall_scores.png"
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)

    print(f"Created: {output}")

def generate_vram_vs_score_chart(rows):
    fig, ax = plt.subplots(figsize=(10, 7))

    vram = [row["vram"] for row in rows]
    scores = [row["overall"] for row in rows]

    ax.scatter(vram, scores, s=70)

    ax.set_title("Local LLM Benchmark v7.2.2 - VRAM vs Overall Score")
    ax.set_xlabel("Peak VRAM Usage (GiB)")
    ax.set_ylabel("Overall Score")
    ax.set_xlim(left=0)
    ax.set_ylim(0, 100)

    for row in rows:
        ax.annotate(
            row["model"],
            (row["vram"], row["overall"]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
        )

    fig.tight_layout()

    output = OUTPUT_DIR / "vram_vs_score.png"
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)

    print(f"Created: {output}")

def generate_category_chart(rows):
    top_rows = sorted(
        rows,
        key=lambda x: x["overall"],
        reverse=True
    )[:5]

    categories = [
        "research",
        "coding",
        "data",
        "writer",
        "ppt",
        "critic",
    ]

    category_labels = [
        "Research",
        "Coding",
        "Data",
        "Writer",
        "PPT",
        "Critic",
    ]

    x = list(range(len(categories)))
    width = 0.15

    fig, ax = plt.subplots(figsize=(12, 7))

    for i, row in enumerate(top_rows):
        values = [row[category] for category in categories]

        positions = [
            value + (i - 2) * width
            for value in x
        ]

        ax.bar(
            positions,
            values,
            width=width,
            label=row["model"],
        )

    ax.set_title(
        "Local LLM Benchmark v7.2.2 - Top 5 Category Scores"
    )
    ax.set_ylabel("Score")
    ax.set_ylim(0, 100)

    ax.set_xticks(x)
    ax.set_xticklabels(category_labels)

    ax.legend(
        fontsize=8,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=2,
    )

    fig.tight_layout()

    output = OUTPUT_DIR / "category_scores.png"
    fig.savefig(
        output,
        dpi=180,
        bbox_inches="tight",
    )

    plt.close(fig)

    print(f"Created: {output}")

def main():
    rows = load_results()

    generate_overall_chart(rows)
    generate_vram_vs_score_chart(rows)
    generate_category_chart(rows)


if __name__ == "__main__":
    main()