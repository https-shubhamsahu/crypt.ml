from __future__ import annotations


def main() -> None:
    try:
        import nltk
    except ImportError:
        print("NLTK is not installed. Run: pip install -r requirements.txt")
        return

    packages = ["punkt", "stopwords", "wordnet", "omw-1.4"]
    for package in packages:
        nltk.download(package, quiet=False)

    print("NLP setup complete. Downloaded NLTK resources:", ", ".join(packages))


if __name__ == "__main__":
    main()
