import os
from main import run_industry_pipeline

def main():
    print("=" * 60)
    print("  LOQO: News URL to broadcast screenplay")
    print("=" * 60)
    print("\nEnter a public news article URL. The pipeline scrapes text and images,")
    print("writes anchor narration, segments the package, and runs QA with retries.\n")

    url = input("News URL: ").strip()

    if not url:
        print("\nNo URL entered. Exiting.")
        return

    print("\nRunning pipeline (may take a minute depending on the site).\n")
    try:
        run_industry_pipeline(url)
        print("\n" + "=" * 60)
        print("Done. See final_broadcast_plan.json for structured output.")
        print("=" * 60)
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    main()
